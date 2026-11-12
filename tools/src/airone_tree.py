"""What the tools share: the tracked tree read through git, nested repositories included, and the parts of a Markdown
file a check reads (frontmatter, headings and their anchors, links, code spans), outside code fences and HTML
comments. Standard library only.
"""

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote


class Usage(Exception):
    """A bad argument, or a tree that cannot be read: exit 2."""


# ---------------------------------------------------------------- git and the tracked tree

def git(root, *args, check=False):
    """Run git in `root`; the CompletedProcess, or Usage when git is missing or `check` and it failed."""
    binary = shutil.which("git")
    if binary is None:
        raise Usage("git is not installed")
    p = subprocess.run([binary, *args], cwd=root, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise Usage(f"git {' '.join(args)} failed in {root}: {p.stderr.strip()}")
    return p


# A path in git's line output (-z output is never quoted): git puts a path in double quotes when it holds a control
# character, a double quote, a backslash or a byte above 0x7f, each written as a C escape, the bytes above 0x7f as
# three octal digits; core.quotePath off leaves those bytes alone and quotes the rest as before.
QUOTED_PATH_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
ESCAPE_RE = re.compile(r"((?:\\[23][0-7]{2})+)|\\.")


def _high_bytes(m):
    """A run of octal escapes of bytes above 0x7f, decoded as the UTF-8 text they spell; any other escape, as is."""
    return bytes(int(o, 8) for o in m[1].split("\\")[1:]).decode("utf-8") if m[1] else m[0]


def git_path(text):
    """A path as git's line output prints it, the way it prints it with core.quotePath off: a path quoted only for its
    bytes above 0x7f comes back unquoted and decoded; one quoted for another reason keeps its quotes and other escapes;
    what follows the closing quote (the tab git puts after a name with a space in a diff's header) stays."""
    m = QUOTED_PATH_RE.match(text)
    if m is None:
        return text
    body = ESCAPE_RE.sub(_high_bytes, m[1])
    return (f'"{body}"' if "\\" in body else body) + text[m.end():]


def top(start="."):
    """The top folder of the repository holding `start`."""
    p = git(start, "rev-parse", "--show-toplevel")
    if p.returncode != 0:
        raise Usage(f"{Path(start).resolve()} is not inside a git repository")
    return Path(p.stdout.strip()).resolve()


def nested(root):
    """The folders of the repositories nested in `root` that are work trees of their own: every gitlink in the index
    and every path `.gitmodules` declares, so a submodule added but not yet committed is read too."""
    found = set()
    p = git(root, "ls-files", "-s", "-z")
    for entry in p.stdout.split("\0"):
        if entry.startswith("160000 "):
            found.add(entry.split("\t", 1)[1])
    if (root / ".gitmodules").is_file():
        q = git(root, "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$")
        for line in q.stdout.splitlines():
            found.add(line.split(" ", 1)[1].strip())
    return sorted(d.strip("/") for d in found if (root / d / ".git").exists())


def tracked(root):
    """(every tracked file as a path from `root`, the nested repositories' folders); a nested repository's files are
    listed with its folder in front, as they sit in the workspace."""
    p = git(root, "ls-files", "-z", check=True)
    files = [f for f in p.stdout.split("\0") if f]
    subs = nested(root)
    gitlinks = set(subs)
    files = [f for f in files if f not in gitlinks]
    for sub in subs:
        q = git(root / sub, "ls-files", "-z")
        files += [f"{sub}/{f}" for f in q.stdout.split("\0") if f]
    return sorted(set(files)), subs


def folders_of(files):
    """Every folder that holds a tracked file, as a path from the root; '' is the root itself."""
    out = {""}
    for f in files:
        parts = f.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            out.add("/".join(parts[:i]))
    return out


def repo_of(path, subs):
    """The folder of the innermost repository holding `path`: a nested one's folder, or '' for the workspace."""
    best = ""
    for sub in subs:
        if (path == sub or path.startswith(sub + "/")) and len(sub) > len(best):
            best = sub
    return best


def under(path, folder):
    """Whether `path` is `folder` or inside it; folder '' holds everything."""
    folder = folder.strip("/")
    return not folder or path == folder or path.startswith(folder + "/")


def normal(path):
    """A path from the root with `.` and `..` resolved; None when it climbs out of the root."""
    parts = []
    for part in PurePosixPath(path).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def join(folder, rel):
    return normal(f"{folder}/{rel}" if folder else rel)


# ---------------------------------------------------------------- Markdown

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
ATX_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1")
# An inline link or image: the target runs to the closing parenthesis, one level of nested parentheses allowed; a
# title in quotes after it is dropped.
INLINE_RE = re.compile(r"(!?\[(?:[^\[\]]|\[[^\[\]]*\])*\]\()(\s*(?:<[^>\n]*>|(?:[^()\s]|\([^()\s]*\))*)"
                       r"(?:\s+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^()\n]*\)))?\s*)(\))")
REFDEF_RE = re.compile(r"^ {0,3}\[[^\]\n]+\]:[ \t]*(<[^>\n]*>|\S+)")
HTML_ANCHOR_RE = re.compile(r"<a\s[^>]*?\b(?:name|id)\s*=\s*[\"']([^\"']+)[\"']", re.I)
HTML_ID_RE = re.compile(r"<[a-z][^>]*?\bid\s*=\s*[\"']([^\"']+)[\"']", re.I)
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def frontmatter_end(lines):
    """The index of the line closing a leading frontmatter block, or None when the file opens with none."""
    if not lines or lines[0].rstrip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip() in ("---", "..."):
            return i
    return None


def prose_lines(text):
    """(line number, line) for every line a reader sees as prose: outside the frontmatter, code fences and HTML
    comments. A comment's text and a fence's are examples, never citations."""
    lines = text.splitlines()
    end = frontmatter_end(lines)
    start = end + 1 if end is not None else 0
    fence, comment = None, False
    for i in range(start, len(lines)):
        line = lines[i]
        if comment:
            if "-->" in line:
                comment = False
                rest = line.split("-->", 1)[1]
                if rest.strip():
                    yield i + 1, rest
            continue
        m = FENCE_RE.match(line)
        if fence is None and m:
            fence = m.group(1)
            continue
        if fence is not None:
            s = line.strip()
            if s and set(s) == {fence[0]} and len(s) >= len(fence):
                fence = None
            continue
        if "<!--" in line:
            before, after = line.split("<!--", 1)
            if "-->" in after:
                line = before + after.split("-->", 1)[1]
            else:
                comment = True
                line = before
            if not line.strip():
                continue
        yield i + 1, line


def mask_code(line):
    """The line with every code span blanked, so a link written inside backticks is not read as one."""
    return CODE_SPAN_RE.sub(lambda m: " " * len(m.group(0)), line)


def code_spans(line):
    return [m.group(2).strip() for m in CODE_SPAN_RE.finditer(line)]


@dataclass
class Link:
    line: int
    target: str      # as written, without angle brackets or a title
    kind: str        # "link", "image" or "reference"


def links(text):
    """Every inline link, image and reference definition outside code."""
    out = []
    for n, line in prose_lines(text):
        masked = mask_code(line)
        m = REFDEF_RE.match(masked)
        if m:
            out.append(Link(n, clean_target(m.group(1)), "reference"))
            continue
        for m in INLINE_RE.finditer(masked):
            out.append(Link(n, clean_target(m.group(2)), "image" if m.group(1).startswith("!") else "link"))
    return out


def clean_target(raw):
    raw = raw.strip()
    if raw.startswith("<") and ">" in raw:
        return raw[1:raw.index(">")].strip()
    return re.split(r"\s+", raw, 1)[0] if raw else raw


def is_external(target):
    """A URL or any other scheme (mailto:, a forge's own): not a path in the tree."""
    return bool(SCHEME_RE.match(target)) or target.startswith("//")


def split_target(target):
    """(path, anchor or None) of a relative link target, the path URL-decoded."""
    path, sep, anchor = target.partition("#")
    path = path.split("?", 1)[0]
    return unquote(path), (unquote(anchor) if sep else None)


def slug(heading):
    """The anchor a forge gives a heading: the rendered text lower-cased, every character but letters, digits,
    spaces, hyphens and underscores dropped, spaces turned to hyphens. GitHub's and GitLab's rule for the common
    case: a link keeps its text, and an underscore of emphasis goes while one inside a word stays."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"(?<!\w)_+|_+(?!\w)", "", text)  # emphasis; an underscore inside a word stays
    text = "".join(c for c in text.strip().lower() if c.isalnum() or c in "-_ ")
    return text.replace(" ", "-")


def anchors(text):
    """Every anchor a link may name in this file: each heading's slug, a repeated one numbered -1, -2 as forges do,
    and every HTML id or name."""
    seen, out = {}, set()
    prev = None
    for n, line in prose_lines(text):
        heading = None
        m = ATX_RE.match(line)
        if m:
            heading = m.group(2) or ""
        elif prev is not None and SETEXT_RE.match(line) and prev.strip() and not ATX_RE.match(prev) \
                and not prev.lstrip().startswith(("|", "-", "*", ">")):
            heading = prev.strip()
        prev = line
        if heading is not None:
            base = slug(heading)
            count = seen.get(base, 0)
            out.add(base if count == 0 else f"{base}-{count}")
            seen[base] = count + 1
        for rx in (HTML_ANCHOR_RE, HTML_ID_RE):
            out.update(rx.findall(line))
    return out


def headings(text):
    """(line, text) of every ATX heading outside code."""
    return [(n, (m.group(2) or "").strip()) for n, line in prose_lines(text) for m in [ATX_RE.match(line)] if m]


# ---------------------------------------------------------------- frontmatter

@dataclass
class Frontmatter:
    fields: dict      # key -> the value's text, quotes stripped; a block list's items joined into a flow list
    raw: dict         # key -> the value's text as written
    lines: dict       # key -> line number
    end: int          # the closing line's index


def frontmatter(text):
    """The leading frontmatter block, or None when the file opens with none or never closes it."""
    lines = text.splitlines()
    end = frontmatter_end(lines)
    if end is None:
        return None
    fields, raw, where, last = {}, {}, {}, None
    for i in range(1, end):
        line = lines[i]
        m = re.match(r"^([A-Za-z_][\w-]*):(?:\s+(.*?))?\s*$", line)
        if m:
            last = m.group(1)
            value = m.group(2) or ""
            value = re.sub(r"\s+#.*$", "", value) if not value.startswith(("'", '"')) else value
            raw[last] = value
            fields[last] = value.strip().strip("'\"")
            where[last] = i + 1
            continue
        item = re.match(r"^\s+-\s+(.*?)\s*$", line)
        if item and last is not None and not raw[last]:
            raw.setdefault(f"{last}[]", [])
            raw[f"{last}[]"].append(item.group(1))
    for key in [k for k in raw if k.endswith("[]")]:
        name = key[:-2]
        fields[name] = "[" + ", ".join(raw[key]) + "]"
        raw[name] = fields[name]
        del raw[key]
    return Frontmatter(fields, raw, where, end)
