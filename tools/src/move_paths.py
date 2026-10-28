#!/usr/bin/env python3
"""Move tracked files with `git mv` and re-point every reference to them in the tracked text files.

    move-paths OLD NEW                          a dry run: what would move and every edit, file by file
    move-paths --table FILE                     the same for a table of moves
    move-paths ... --apply                      move and rewrite
    move-paths ... --frozen-ok FILE --apply     and re-point the links of this archived file too
    python3 move_paths.py ...                   from the kit, without installing

OLD is a tracked file, or a folder whose tracked files all move with it. The table holds one move a line, OLD and NEW
separated by a tab (or by spaces, when neither path has one), and an optional third column `no` for a file whose own
content is never edited (a run's raw output); a line starting with # is a comment.

What it rewrites, in every tracked text file (Markdown, scripts and code, YAML, TOML, HTML, --also for more):
  * a Markdown link, or an HTML href or src, whose target is a moved file or folder, or that sits in a moved file so
    its relative target changes; the anchor is kept, and in a live file a link whose text is its old path shows the
    new one;
  * a path written relative to the file (./x, ../x) that names a moved file or folder;
  * a path written from the top of the repository holding the file that names a moved file, or a moved folder
    followed by a slash (a folder at the top is matched only with its slash, so the bare word in prose is left
    alone); a path followed by more path characters is another path (x.txt in x.txt.gz).
It reports, and leaves alone, every other mention of a moved file's name in a live file: a bare name in prose, or a
script finding a sibling by its own folder, which a move into another folder breaks. Read that list before applying.

The archive (archive/ at each repository's top, or --archive) is frozen: nothing in it is edited, its log included,
and a link inside it that a move kills is reported as information. --frozen-ok FILE names an archived file whose link
targets may be re-pointed (its prose never), and only when the staged archive log holds a new row in its Changes table
naming that file, the row the archive's rule asks of every change to an archived file; moving an archived file is
such a change too. A file moved into the archive is not edited: archiving changes nothing in it but its stamp.

--apply refuses, before anything moves, when a file it would write has changes not staged (the undo is a checkout,
which would take them too), when a move crosses from one repository into another, or when an archived file would
change without its row. Exit 0 on a dry run or an applied plan, 1 on a refusal, 2 on a bad argument or table.
Standard library only; the archive's rows are read with airone-archive's checker when it is installed.
"""

import argparse
import posixpath
import re
import sys
from dataclasses import dataclass, field

import airone_tree as at

try:  # The archive's own reading of its log, when its package is installed; the fallback below reads the same rows.
    import check_archive as _archive
    ROW_READER = "the archive's checker (airone-archive)"
except ImportError:  # pragma: no cover - depends on the environment
    _archive = None
    ROW_READER = "move-paths' own reading of the Changes table (airone-archive is not installed)"

TEXT_SUFFIXES = (".md", ".markdown", ".py", ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd", ".yml",
                 ".yaml", ".toml", ".html", ".htm", ".cfg", ".ini", ".mk", ".rs", ".go", ".js", ".mjs", ".cjs",
                 ".ts", ".jl", ".rb", ".pl", ".lua", ".c", ".h", ".cc", ".cpp", ".hpp", ".java", ".kt", ".r")
TEXT_NAMES = ("Makefile", "Dockerfile", "Justfile")
PATH_CHAR = r"[A-Za-z0-9_.@/-]"
LINK_RE = re.compile(r"(\[(?:[^\[\]]|\[[^\[\]]*\])*\]\()(<[^>\n]*>|[^()\s]+)((?:\s+\"[^\"\n]*\")?\))")
ATTR_RE = re.compile(r"""\b(?:href|src)\s*=\s*(["'])([^"'\s]+)\1""", re.I)
RELATIVE_RE = re.compile(r"(?<![A-Za-z0-9_.@/])((?:\.\.?/)+[A-Za-z0-9_.@-][A-Za-z0-9_.@/-]*)")
ARCHIVE_OWN_LIVE = ("README.md",)


class Refusal(Exception):
    """The plan cannot be applied: exit 1, nothing moved."""


# ---------------------------------------------------------------- the archive's log

def changes_rows(text):
    """The Changes table's rows of an archive log: [(the row's text, its File cell)], read outside code fences and
    HTML comments, where the log's template keeps its example rows."""
    if _archive is not None:
        return [(r.text, r.cells["file"]) for r in _archive.read_log(text or "", "log").changes]
    rows, in_table = [], False
    fence, comment = None, False
    for line in (text or "").splitlines():
        if comment or line.lstrip().startswith("<!--"):
            comment = "-->" not in line
            in_table = False
            continue
        m = at.FENCE_RE.match(line)
        if m and fence is None:
            fence = m.group(1)
            continue
        if fence is not None:
            if line.strip().startswith(fence):
                fence = None
            continue
        s = line.strip()
        if not s.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", s.strip("|"))]
        names = [" ".join(re.sub(r"[^a-z ]", " ", c.lower()).split()) for c in cells]
        if names[:2] == ["date", "file"]:
            in_table = True
            continue
        if in_table and not all(re.fullmatch(r":?-+:?", c) for c in cells) and len(cells) >= 2:
            rows.append((s, cells[1]))
    return rows


def row_names(cell, paths):
    if _archive is not None:
        return _archive.names(cell, paths)
    values = re.findall(r"`([^`\n]+)`", cell) + re.findall(r"\]\(([^)\s]+)", cell) or [cell.strip().strip("*_`")]
    return any(v.strip().split("#", 1)[0].removeprefix("./") in paths for v in values)


# ---------------------------------------------------------------- the plan

@dataclass
class Edit:
    file: str
    line: int
    kind: str
    before: str
    after: str


@dataclass
class Plan:
    root: object
    moves: dict                       # old path -> new path, from the workspace root
    keep_content: set                 # old paths whose own content is never edited
    files: list
    subs: list
    archives: list
    frozen_ok: set
    also: tuple = ()
    folders: dict = field(default_factory=dict)
    texts: dict = field(default_factory=dict)     # file (old path) -> new text
    edits: list = field(default_factory=list)
    dead_frozen: list = field(default_factory=list)
    mentions: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    # -- where things are

    def archive_of(self, path):
        for a in self.archives:
            if at.under(path, a) and path != a:
                return a
        return None

    def frozen(self, path):
        a = self.archive_of(path)
        return a is not None and path[len(a) + 1:] not in ARCHIVE_OWN_LIVE

    def new_path(self, path):
        """Where a file or folder is after the moves, or None when it stays."""
        if path in self.moves:
            return self.moves[path]
        for old, new in self.folders.items():
            if path == old:
                return new
            if path.startswith(old + "/"):
                return new + path[len(old):]
        return None

    def is_text(self, path):
        name = posixpath.basename(path)
        if name.lower().endswith(TEXT_SUFFIXES + tuple(self.also)) or name in TEXT_NAMES:
            return True
        if "." not in name:
            try:
                with open(self.root / path, "rb") as f:
                    return f.read(2) == b"#!"
            except OSError:
                return False
        return False

    # -- building

    def build(self):
        tracked = set(self.files)
        for old, new in self.moves.items():
            if old not in tracked:
                self.refusals.append(f"not a tracked file: {old}")
            if new in tracked or (self.root / new).exists():
                self.refusals.append(f"already exists: {new}")
            if at.repo_of(old, self.subs) != at.repo_of(new, self.subs):
                self.refusals.append(f"{old} -> {new} crosses from one repository into another: git mv cannot carry "
                                     f"it, and its history would not follow; move it by hand")
        if len(set(self.moves.values())) != len(self.moves):
            self.refusals.append("two files would move to the same path")
        self.folders = folder_moves(self.moves, self.files)
        for f in sorted(self.frozen_ok):
            if f not in tracked or self.archive_of(f) is None:
                self.refusals.append(f"--frozen-ok takes a tracked file inside the archive: {f}")
        for old in self.moves:
            if self.frozen(old) and old not in self.frozen_ok:
                self.refusals.append(f"{old} is archived: moving it changes it, so it needs --frozen-ok and its row "
                                     f"in the archive's log")
        for old, new in self.moves.items():
            if self.archive_of(new) is not None and self.archive_of(old) is None:
                self.notes.append(f"{new}: archived by this move; its content is left as it is, and its frontmatter "
                                  f"gets the `archived:` stamp by hand in the same commit")
        names = sorted({posixpath.basename(o) for o in self.moves}, key=len, reverse=True)
        name_re = re.compile(r"(?<![A-Za-z0-9_.@-])(" + "|".join(re.escape(n) for n in names) +
                             r")(?![A-Za-z0-9_-]|\.[A-Za-z0-9])") if names else None
        for f in self.files:
            if f in self.moves and f in self.keep_content:
                continue
            if not self.is_text(f):
                continue
            arriving = f in self.moves and self.archive_of(self.moves[f]) is not None and self.archive_of(f) is None
            if arriving:
                continue
            try:
                text = (self.root / f).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            new = self.rewrite(f, text)
            if not self.frozen(f) and name_re is not None:
                self.find_mentions(f, new, name_re)
            if new != text:
                self.texts[f] = new
        self.check_rows()

    def rewrite(self, f, text):
        """The file's text with every reference re-pointed; each edit is recorded."""
        frozen = self.frozen(f)
        if frozen and f not in self.frozen_ok:
            self.find_dead(f, text)
            return text
        spans = []          # (start, end, replacement, kind, before)
        taken = []

        def free(s, e):
            return all(e <= a or s >= b for a, b in taken)

        def add(s, e, new, kind, before):
            if free(s, e):
                taken.append((s, e))
                if new != before:
                    spans.append((s, e, new, kind, before))

        markdown = f.lower().endswith((".md", ".markdown"))
        if markdown:
            for m in LINK_RE.finditer(text):
                target = m.group(2)
                new = self.relink(f, target.strip("<>"))
                if new is None:
                    add(m.start(2), m.end(2), target, "link", target)
                    continue
                new = f"<{new}>" if target.startswith("<") else new
                add(m.start(2), m.end(2), new, "frozen link" if frozen else "link", target)
                shown = m.group(1)[1:-2]
                path = target.strip("<>").partition("#")[0]
                if not frozen and "/" in path and shown.strip("`") == path and free(m.start(1), m.end(1)):
                    add(m.start(1) + 1, m.end(1) - 2, shown.replace(path, new.strip("<>").partition("#")[0]),
                        "link text", shown)
        if markdown or f.lower().endswith((".html", ".htm")):
            for m in ATTR_RE.finditer(text):
                new = self.relink(f, m.group(2))
                if new is not None:
                    add(m.start(2), m.end(2), new, "frozen link" if frozen else "link", m.group(2))
        if not frozen:
            for m in RELATIVE_RE.finditer(text):
                token = m.group(1).rstrip(".,;:")
                new = self.relative(f, token)
                if new is not None:
                    add(m.start(1), m.start(1) + len(token), new, "path", token)
            base = at.repo_of(f, self.subs)
            pattern = self.rooted_pattern(base)
            if pattern is not None:
                for m in pattern.finditer(text):
                    old = at.join(base, m.group(1))
                    new = self.new_path(old)
                    if new is not None:
                        add(m.start(1), m.end(1), new[len(base) + 1:] if base else new, "path", m.group(1))
        out = text
        for s, e, new, kind, before in sorted(spans, reverse=True):
            out = out[:s] + new + out[e:]
        for s, e, new, kind, before in sorted(spans):
            self.edits.append(Edit(f, text.count("\n", 0, s) + 1, kind, before, new))
        return out

    def rooted_pattern(self, base):
        """The written-from-the-top paths of the moved files and folders, as the files of the repository at `base`
        write them."""
        olds = []
        for old in list(self.moves) + list(self.folders):
            if not at.under(old, base) or old == base:
                continue
            rel = old[len(base) + 1:] if base else old
            folder = old in self.folders
            if "/" in rel or folder:
                # a file at the top is written as its bare name, which a mention of any file so named shares:
                # it is left to the mentions; a folder at the top is matched with its slash only
                olds.append((rel, folder))
        if not olds:
            return None
        parts = []
        for rel, folder in sorted(olds, key=lambda x: len(x[0]), reverse=True):
            if folder:
                # a folder at the top only with its slash; a deeper one also bare, at the end of a path
                tail = r"(?=/)" if "/" not in rel else r"(?=/|(?![A-Za-z0-9_.@-]))"
            else:
                tail = r"(?![A-Za-z0-9_@-]|[./][A-Za-z0-9_])"
            parts.append(re.escape(rel) + tail)
        # Before a path, a letter, a digit, `_`, `.` or `/` would make it a longer path, another one; a hyphen does
        # not (a shell default, `${OUT:-plan/x.txt}`).
        return re.compile(r"(?<![A-Za-z0-9_.@/])(" + "|".join(parts) + ")")

    def relink(self, f, target):
        """A link target re-pointed from the file `f`, or None when it is not a path in the tree or does not
        change."""
        if not target or at.is_external(target) or target.startswith("#"):
            return None
        path, sep, anchor = target.partition("#")
        if not path:
            return None
        base = at.repo_of(f, self.subs)
        if path.startswith("/"):
            resolved = at.join(base, path.lstrip("/"))
            if resolved is None:
                return None
            moved = self.new_path(resolved)
            if moved is None:
                return None
            return "/" + (moved[len(base) + 1:] if base else moved) + (sep + anchor)
        return self.repoint(f, path, sep + anchor)

    def relative(self, f, token):
        """A path written relative (./x, ../x) re-pointed when what it names moved. Read from the file's folder; a
        ./x that names nothing moved from there is read from the top of the file's repository, as a script run from
        the top writes it. Unlike a link, it is not re-based when only the file moves: in a script its base may be
        the folder the script runs in, so that case is left to the mentions."""
        new = self.repoint(f, token, "", follow_file=False)
        if new is None and token.startswith("./"):
            base = at.repo_of(f, self.subs)
            moved = self.new_path(at.join(base, token[2:]) or "")
            if moved is not None:
                new = "./" + (moved[len(base) + 1:] if base else moved)
        return new

    def repoint(self, f, path, suffix, follow_file=True):
        old_dir = posixpath.dirname(f)
        new_dir = posixpath.dirname(self.new_path(f) or f) if follow_file else old_dir
        resolved = at.join(old_dir, path)
        if resolved is None:
            return None
        moved = self.new_path(resolved.rstrip("/"))
        if moved is None and (new_dir == old_dir or not follow_file):
            return None
        if moved is None and not self.exists(resolved.rstrip("/")):
            return None
        dest = moved or resolved.rstrip("/")
        rel = posixpath.relpath(dest, new_dir or ".")
        if path.endswith("/") and not rel.endswith("/"):
            rel += "/"
        if path.startswith("./") and not rel.startswith("."):
            rel = "./" + rel
        new = rel + suffix
        return new if new != path + suffix else None

    def exists(self, path):
        if not hasattr(self, "_known"):
            self._known = set(self.files) | at.folders_of(self.files)
        return path in self._known

    def find_dead(self, f, text):
        """The links of a frozen file that a move would kill: reported, never repaired without its row."""
        for link in at.links(text):
            if at.is_external(link.target) or not link.target or link.target.startswith("#"):
                continue
            path, _ = at.split_target(link.target)
            resolved = at.join(posixpath.dirname(f), path)
            if resolved is not None and self.new_path(resolved.rstrip("/")) is not None:
                self.dead_frozen.append((f, link.line, link.target))

    def find_mentions(self, f, text, name_re):
        new_paths = set(self.moves.values())
        for m in name_re.finditer(text):
            start = m.start()
            while start > 0 and re.match(PATH_CHAR, text[start - 1]):
                start -= 1
            whole = text[start:m.end()].lstrip("-")
            here = posixpath.dirname(self.new_path(f) or f)
            base = at.repo_of(f, self.subs)
            if whole in new_paths or at.join(here, whole) in new_paths or at.join(base, whole) in new_paths:
                continue
            self.mentions.append((f, text.count("\n", 0, m.start()) + 1, whole))

    def check_rows(self):
        """Every archived file this plan changes needs a new row in its archive's staged log."""
        changed = {f for f in self.texts if self.frozen(f)} | {o for o in self.moves if self.frozen(o)}
        for f in sorted(changed):
            archive = self.archive_of(f)
            repo = at.repo_of(archive, self.subs)
            log = at.join(archive, "LOG.md")
            rel_log = log[len(repo) + 1:] if repo else log
            staged = show(self.root / repo if repo else self.root, f":{rel_log}")
            head = show(self.root / repo if repo else self.root, f"HEAD:{rel_log}")
            old = [t for t, _ in changes_rows(head)]
            new = []
            for text, cell in changes_rows(staged):
                if text in old:
                    old.remove(text)
                else:
                    new.append(cell)
            # the row may name the file where it was or, for a file moved inside the archive, where it goes
            paths = set()
            for p in {f, self.moves.get(f, f)}:
                if self.archive_of(p) == archive:
                    inner = p[len(archive) + 1:]
                    paths |= {p, inner, f"{posixpath.basename(archive)}/{inner}", p[len(repo) + 1:] if repo else p}
            if not any(row_names(cell, paths) for cell in new):
                self.refusals.append(f"{f} is archived and this plan changes it: the staged {log} has no new row in "
                                     f"its Changes table naming it (rows read by {ROW_READER})")

    # -- output

    def report(self, out):
        print(f"moves: {len(self.moves)} file(s); whole folders: {len(self.folders)}", file=out)
        for old, new in sorted(self.moves.items()):
            print(f"  move {old} -> {new}", file=out)
        for old, new in sorted(self.folders.items()):
            print(f"  folder {old}/ -> {new}/", file=out)
        print(f"edits: {len(self.edits)} in {len(self.texts)} file(s)", file=out)
        for e in self.edits:
            print(f"  {e.kind:11} {e.file}:{e.line}: {e.before} -> {e.after}", file=out)
        if self.dead_frozen:
            print(f"archived links this move leaves dead, information only: {len(self.dead_frozen)}", file=out)
            for f, n, t in self.dead_frozen:
                print(f"  {f}:{n}: {t}", file=out)
        print(f"mentions left as they are: {len(self.mentions)}", file=out)
        for f, n, whole in self.mentions:
            print(f"  {f}:{n}: {whole}", file=out)
        for note in self.notes:
            print(f"note: {note}", file=out)
        for r in self.refusals:
            print(f"REFUSED: {r}", file=out)

    def apply(self):
        if self.refusals:
            raise Refusal(f"{len(self.refusals)} refusal(s); nothing was moved")
        dirty = []
        for f in sorted(set(self.texts) | set(self.moves)):
            repo = at.repo_of(f, self.subs)
            rel = f[len(repo) + 1:] if repo else f
            p = at.git(self.root / repo if repo else self.root, "diff", "--name-only", "--", rel)
            if p.stdout.strip():
                dirty.append(f)
        if dirty:
            raise Refusal(f"changes not staged in {', '.join(dirty)}: stage or commit them first, so a checkout can "
                          f"undo this run alone; nothing was moved")
        for old, new in self.moves.items():
            repo = at.repo_of(old, self.subs)
            cwd = self.root / repo if repo else self.root
            (self.root / new).parent.mkdir(parents=True, exist_ok=True)
            strip = (lambda p: p[len(repo) + 1:]) if repo else (lambda p: p)
            at.git(cwd, "mv", strip(old), strip(new), check=True)
        for old, text in self.texts.items():
            # written in place, so a script keeps its mode
            (self.root / (self.moves.get(old) or old)).write_text(text, encoding="utf-8")


def show(cwd, spec):
    p = at.git(cwd, "show", spec)
    return p.stdout if p.returncode == 0 else None


def folder_moves(moves, files):
    """The folders whose every tracked file moves to one new folder, keeping the rest of its path."""
    out = {}
    candidates = set()
    for old in moves:
        d = posixpath.dirname(old)
        while d:
            candidates.add(d)
            d = posixpath.dirname(d)
    for d in candidates:
        inside = [f for f in files if f.startswith(d + "/")]
        if not inside or any(f not in moves for f in inside):
            continue
        rest = inside[0][len(d) + 1:]
        target = moves[inside[0]]
        if not target.endswith("/" + rest):
            continue
        new_dir = target[: -len(rest) - 1]
        if all(moves[f] == new_dir + "/" + f[len(d) + 1:] for f in inside):
            out[d] = new_dir
    return out


def read_table(path):
    """(moves, keep_content) from a table file."""
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError as e:
        raise at.Usage(f"cannot read {path}: {e.strerror}") from e
    pairs = []
    for n, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t") if "\t" in line else line.split()
        parts = [p.strip() for p in parts]
        if len(parts) not in (2, 3) or (len(parts) == 3 and parts[2] not in ("yes", "no")):
            raise at.Usage(f"{path}:{n}: expected OLD<TAB>NEW, and optionally <TAB>no; got {line!r}")
        pairs.append((parts[0], parts[1], len(parts) == 3 and parts[2] == "no", f"{path}:{n}"))
    return pairs


def expand(pairs, files):
    """Each move of a folder becomes the moves of its tracked files."""
    tracked = set(files)
    moves, keep = {}, set()
    for old, new, no_edit, where in pairs:
        old, new = at.normal(old.rstrip("/")), at.normal(new.rstrip("/"))
        if not old or not new:
            raise at.Usage(f"{where}: a path climbs out of the repository, or is empty")
        if old in tracked:
            items = [(old, new)]
        else:
            inside = [f for f in files if f.startswith(old + "/")]
            if not inside:
                items = [(old, new)]   # refused at build: not tracked
            else:
                items = [(f, new + f[len(old):]) for f in inside]
        for o, n in items:
            if o in moves:
                raise at.Usage(f"{where}: {o} is moved twice")
            moves[o] = n
            if no_edit:
                keep.add(o)
    return moves, keep


def parser():
    p = argparse.ArgumentParser(description="Move tracked files and re-point every reference to them; a dry run "
                                            "unless --apply.")
    p.add_argument("paths", nargs="*", metavar="OLD NEW", help="one move: the old path and the new one")
    p.add_argument("--table", metavar="FILE", help="a table of moves, one OLD<TAB>NEW[<TAB>no] a line")
    p.add_argument("--apply", action="store_true", help="move and rewrite; without it nothing is changed")
    p.add_argument("--frozen-ok", metavar="FILE", action="append", default=[],
                   help="an archived file whose links may be re-pointed, given its row in the staged log; repeatable")
    p.add_argument("--archive", metavar="DIR", action="append",
                   help="the archive folder, from the root; repeatable (default: archive/ at each repository's top)")
    p.add_argument("--also", metavar=".EXT", action="append", default=[],
                   help="another suffix of text files to rewrite (.json, .txt); repeatable")
    p.add_argument("--root", metavar="DIR", help="the repository (default: the one holding the current folder)")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.table and args.paths:
            raise at.Usage("give OLD NEW or --table, not both")
        if not args.table and len(args.paths) != 2:
            raise at.Usage("give OLD NEW, or --table FILE")
        root = at.top(args.root or ".")
        files, subs = at.tracked(root)
        pairs = read_table(args.table) if args.table else [(args.paths[0], args.paths[1], False, "arguments")]
        moves, keep = expand(pairs, files)
        archives = [a.strip("/") for a in args.archive] if args.archive else \
            [at.join(t, "archive") for t in [""] + subs]
        plan = Plan(root, moves, keep, files, subs, archives,
                    {at.normal(f) for f in args.frozen_ok}, tuple(s.lower() for s in args.also))
        plan.build()
    except at.Usage as e:
        print(e, file=sys.stderr)
        return 2
    plan.report(sys.stdout)
    if not args.apply:
        print("dry run: nothing changed" + ("; --apply would refuse" if plan.refusals else "; --apply to do it"))
        return 1 if plan.refusals else 0
    try:
        plan.apply()
    except Refusal as e:
        print(f"refused: {e}")
        return 1
    except at.Usage as e:
        print(e, file=sys.stderr)
        return 2
    print("applied: review with git status and git diff; git checkout and git reset undo it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
