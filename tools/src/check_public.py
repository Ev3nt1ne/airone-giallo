#!/usr/bin/env python3
"""check-public: the gate a public repository's commits and pushes go through when the project's history stays private.

    check-public --staged [--root DIR] [--message TEXT]      what the first commit would hold
    check-public --pre-push REMOTE URL [--root DIR]          what a push sends; the refs come on standard input

The public repository sits inside a private one, the setup's private-history direction. The private side keeps two
lists the public side never holds: `public-paths.txt`, which gives each of the project's paths a side, and
`public-markers.txt`, the owner's words that must never be published. They are found at the private repository's
root (`--private-root`, or the superproject, or the parent folder whose `.gitmodules` names this one), or named with
`--sides` and `--markers`.

A rule is a word and a path from the project's root, a folder ending in `/`: `public` goes into the public
repository, `private` stays, and `local` is an ignored entry under a public path that travels with it and stays
ignored there. `public SRC -> DEST` publishes SRC under another name. `setup FILE` is a file the setup itself wrote on
the public side, one line per file; an explicit `private` rule wins over it. The longest matching path wins, and a
path no rule covers is private. A line `old-email-ok yes` is the owner's yes to an identity the old history used.

What fails the gate: a path not declared public; an agent tool's file (`.claude/`, `.mcp.json`, `AGENTS.md`,
`CLAUDE.md`, at any depth); a marker in a path, a file, a ref's name, an identity or a message; a finding of the
secret scan, gitleaks, which is required and never reimplemented, or a gitleaks configuration in the public folder
that is not tracked; an ignored entry inside the public folder that is not `local` or holds a `private` path, a
`local` one not ignored by the public repository's own tracked rules, an untracked file inside it; the identity of the
old history. Images and binary files are listed for a person, not read; a text file over 1 MiB is read and listed.

With --pre-push the gate judges every object the push adds to the remote: every new blob's content, every path of
every new commit's tree, every new commit and annotated tag (message, author, committer, tagger), and each pushed
ref's name. Git runs with replace refs off (GIT_NO_REPLACE_OBJECTS=1) in every mode, so a replace ref cannot hide
what is sent.

Exit 0 clean, 1 on a finding or a scan that could not run, 2 on a bad argument or a list that cannot be read.
Standard library only, plus the gitleaks command.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import airone_tree as at

Usage = at.Usage
SIDES_FILE = "public-paths.txt"
MARKERS_FILE = "public-markers.txt"
WORDS = ("public", "private", "local")
AGENT_DIRS = (".claude",)
AGENT_NAMES = ("AGENTS.md", "CLAUDE.md", ".mcp.json")
# The lines the setup writes into the public repository's .gitignore: a session opened in the public folder creates
# the agent tool's files, and an ignore rule stops them at `git add`, before the gate has to.
AGENT_IGNORE = (".claude/", ".mcp.json", "AGENTS.md", "CLAUDE.md")
GITLEAKS_FILES = (".gitleaks.toml", ".gitleaksignore")
IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".ico", ".heic", ".avif", ".pdf")
LARGE = 1 << 20
INSTALL = ("gitleaks is not installed, so the secret scan cannot run; install it (https://github.com/gitleaks/gitleaks: "
           "a release binary, `brew install gitleaks`, or `go install github.com/zricethezav/gitleaks/v8@latest`), "
           "then run again")


_LOCAL_VARS = []


def local_env_vars():
    """The variables git sets for the repository a hook runs in (GIT_DIR among them), as git itself lists them. A hook
    run from a linked worktree gets an absolute GIT_DIR, which would turn every `git -C <another repository>` of the
    gate back to the public one."""
    if not _LOCAL_VARS:
        exe = shutil.which("git")
        out = subprocess.run([exe, "rev-parse", "--local-env-vars"], capture_output=True, text=True).stdout if exe \
            else ""
        _LOCAL_VARS.extend(out.split() or ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                                           "GIT_OBJECT_DIRECTORY", "GIT_PREFIX", "GIT_CONFIG_PARAMETERS"])
    return _LOCAL_VARS


def env():
    """Every git and gitleaks run of the gate: the repository named by `-C`, never one inherited from the hook's
    environment; replace refs off, so what is judged is what is sent; and no gitleaks configuration from the
    environment."""
    drop = set(local_env_vars())
    return {**{k: v for k, v in os.environ.items() if not k.startswith("GITLEAKS_") and k not in drop},
            "GIT_NO_REPLACE_OBJECTS": "1"}


# ---------------------------------------------------------------- the sides

def covers(rule, path):
    """Whether a rule's path covers a path; a folder's path ends in '/', and covers what is under it."""
    if rule.endswith("/"):
        return path.startswith(rule) or path.rstrip("/") + "/" == rule
    return path.rstrip("/") == rule


ARROW = " -> "


def unsafe_part(path):
    """The first component of a path that may not be written anywhere (empty, '.', '..', a '.git' folder), or None."""
    for part in path.rstrip("/").split("/"):
        if part in ("", ".", "..") or part.casefold() == ".git":
            return part or "an empty name"
    return None


def clean_path(path):
    return bool(path) and not path.startswith("/") and unsafe_part(path) is None and ARROW not in path


class Sides:
    """The side of each of the project's paths. `words` maps a path to public, private or local; `dests` a public
    path published under another name to that name; `setup` holds the files the setup wrote on the public side."""

    def __init__(self, words=None, dests=None, setup=(), old_email_ok=False):
        self.words, self.dests = dict(words or {}), dict(dests or {})
        self.setup, self.old_email_ok = set(setup), old_email_ok

    @classmethod
    def parse(cls, text, where=SIDES_FILE):
        sides = cls()
        for n, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            word, _, rest = line.partition(" ")
            if word == "old-email-ok":
                sides.old_email_ok = rest.strip() == "yes"
                continue
            path, sep, dest = rest.strip().partition(ARROW)
            try:
                sides.add(word, path.strip(), dest.strip() if sep else None)
            except Usage as ex:
                raise Usage(f"{where}: line {n}: {ex}") from None
        sides.check()
        return sides

    @classmethod
    def from_answers(cls, answers):
        """From the setup's `sides` answer, {path: "public" | "private" | "local" | "public as DEST"}: the path is the
        key, so a path holding the word `as` is never mistaken for a rename."""
        sides = cls()
        for path, value in answers.items():
            word, sep, dest = value.partition(" as ")
            sides.add(word.strip(), path, dest.strip() if sep else None)
        sides.check()
        return sides

    def add(self, word, path, dest=None):
        sep = dest is not None
        if word == "setup":
            if sep or not clean_path(path) or path.endswith("/"):
                raise Usage(f"`setup` names one file the setup wrote, never a folder: {path!r}")
            self.setup.add(path)
            return
        if word not in WORDS or not path:
            raise Usage(f"a rule is `public`, `private` or `local`, then a path: {f'{word} {path}'.strip()!r}")
        if not clean_path(path):
            raise Usage(f"a path from the project's root, without '/' first, '..', a '.git' folder or "
                        f"'{ARROW.strip()}': {path!r}")
        if sep:
            if word != "public":
                raise Usage(f"only a public path takes another name: {word} {path}{ARROW}{dest}")
            if not clean_path(dest) or path.endswith("/") != dest.endswith("/"):
                raise Usage(f"the public name of {path} must be a path of the same kind, from the root: {dest!r}")
            self.dests[path] = dest
        self.words[path] = word

    def check(self):
        """Two sources for one public path are refused: two renames onto one name, or a rename onto, inside or over
        a path another public rule publishes."""
        public = [(p, self.dests.get(p, p)) for p, w in self.words.items() if w == "public"]
        for i, (src_a, dst_a) in enumerate(public):
            for src_b, dst_b in public[i + 1:]:
                renamed = src_a in self.dests or src_b in self.dests
                if renamed and (covers(dst_a, dst_b) or covers(dst_b, dst_a)):
                    raise Usage(f"two sources for one public path: {src_a} and {src_b} both publish {dst_b}")

    def side_of(self, path, words=WORDS):
        """The word of the longest rule covering the path, among `words`; None when no rule does (private)."""
        best = None
        for rule, word in self.words.items():
            if word in words and covers(rule, path) and (best is None or len(rule) > len(best)):
                best = rule
        return self.words[best] if best else None

    def ignored_side(self, path):
        """An ignored entry is never public: only a `local` or `private` rule speaks for it; no rule means private."""
        return self.side_of(path, ("private", "local"))

    def dest(self, path):
        """Where a path of the project sits on the public side."""
        best = None
        for rule in self.dests:
            if covers(rule, path) and (best is None or len(rule) > len(best)):
                best = rule
        if best is None:
            return path
        return self.dests[best] if not best.endswith("/") else self.dests[best] + path[len(best):]

    def public_view(self):
        """The same sides, as paths of the public repository: what moves keeps its rules under its public name, and a
        private rule that no public path holds does not reach the public side at all."""
        view = Sides(setup=self.setup, old_email_ok=self.old_email_ok)
        for path, word in self.words.items():
            if word == "public" or self.side_of(path, ("public",)) is not None:
                view.words[self.dest(path)] = word
            elif word == "private" and any(covers(path, s) for s in self.setup):
                view.words[path] = word  # an explicit private rule wins over the setup's own lines
        return view

    def declared_public(self, path):
        """A path of the public repository: public by its rule, or a file the setup wrote that no private rule
        holds."""
        side = self.side_of(path)
        return side == "public" or (path in self.setup and side != "private")

    def text(self):
        lines = ["# Airone Giallo: the side of each of this project's own paths. One rule a line: public, private or",
                 "# local, then a path from the project's root, a folder ending in /; `public SRC -> DEST` publishes",
                 "# SRC under another name. The longest matching path wins; a path no rule covers is private. local:",
                 "# an ignored entry under a public path that travels with it and stays ignored there. setup: a file",
                 "# the setup wrote on the public side. Read by the setup and by check-public, the pre-push gate.",
                 f"# Beside it, {MARKERS_FILE}: the owner's words that must never be published, one a line. Every",
                 "# non-empty line there is a marker, verbatim; that file has no comments."]
        lines += ["old-email-ok yes"] if self.old_email_ok else []
        lines += [f"{w} {p}" + (f"{ARROW}{self.dests[p]}" if p in self.dests else "") for p, w in sorted(self.words.items())]
        lines += [f"setup {p}" for p in sorted(self.setup)]
        return "\n".join(lines) + "\n"


MARKER_MIN = 3


def markers_from(lines, where=MARKERS_FILE):
    """The markers, as the setup's gates and the push gate both read them: each line stripped of the whitespace around
    it, the empty ones dropped, no comment syntax (a marker may begin with '#'). A marker that folds to fewer than
    MARKER_MIN characters would match nothing, or nearly every text, while the output counted it, and is refused."""
    markers = [ln.strip() for ln in lines if ln.strip()]
    for n, m in enumerate(markers, 1):
        if len(fold(m)) < MARKER_MIN:
            raise Usage(f"{where}: marker {n} folds to {len(fold(m))} character(s), fewer than {MARKER_MIN} (case, "
                        "whitespace, hyphens, underscores and dots are ignored), so it would match nothing or nearly "
                        "everything; write it longer, or take it out")
    return markers


def read_markers(data, where=MARKERS_FILE):
    """The markers file's content, bytes or text: UTF-8, a byte-order mark at its start dropped, its lines ending in
    LF or CRLF."""
    text = data.decode("utf-8-sig") if isinstance(data, bytes) else data.removeprefix("\ufeff")
    return markers_from(text.split("\n"), where)


def read_markers_file(path):
    """The markers file, read the one way the setup and the push gate read it."""
    try:
        return read_markers(Path(path).read_bytes(), str(path))
    except UnicodeDecodeError as ex:
        raise Usage(f"{path}: not UTF-8 ({ex.reason} at byte {ex.start}); save it as UTF-8") from None


def is_agent_file(path):
    """The agent tool's files, matched without regard to case: on a file system that ignores case, `claude.md` is
    `CLAUDE.md`."""
    parts = [p.casefold() for p in PurePosixPath(path).parts]
    return any(p in (d.casefold() for d in AGENT_DIRS) for p in parts) or \
        parts[-1] in (n.casefold() for n in AGENT_NAMES)


def case_blind(pattern):
    """An ignore pattern that matches whatever the case of its letters: `CLAUDE.md` gives `[Cc][Ll]…[Dd]`."""
    return "".join(f"[{c.upper()}{c.lower()}]" if c.isalpha() else c for c in pattern)


# ---------------------------------------------------------------- the judgement

@dataclass
class Report:
    parts: list = field(default_factory=list)    # one line per part of the gate, what it checked
    errors: list = field(default_factory=list)
    listed: list = field(default_factory=list)

    def error(self, text):
        if text not in self.errors:
            self.errors.append(text)

    def print(self, out=None):
        out = out or sys.stdout
        for line in self.parts:
            print(line, file=out)
        print("images, binary files and files over 1 MiB, listed, not read: " + (", ".join(self.listed) or "none"),
              file=out)
        for e in self.errors:
            print(f"error: {e}", file=out)
        print(f"{len(self.errors)} error(s)", file=out)


SEPARATORS = "-_."


def folded_with_lines(text):
    """The text in the form markers are matched in, with the line each of its characters comes from: case ignored,
    and every whitespace character (line breaks, tabs, no-break spaces included), hyphen, underscore and dot
    removed, so a name written as a slug or wrapped across lines still holds it. Plain text, never a pattern; letters
    that only look alike, and accented ones, are not folded."""
    chars, lines, n = [], [], 1
    for c in text:
        if c == "\n":
            n += 1
        if c.isspace() or c in SEPARATORS:
            continue
        for f in c.casefold():
            chars.append(f)
            lines.append(n)
    return "".join(chars), lines


def fold(text):
    return folded_with_lines(text)[0]


def marker_hits(text, markers):
    """(marker number, line number) for each place a marker starts, both sides folded, over the whole text."""
    body, lines = folded_with_lines(text)
    for i, marker in enumerate(markers, 1):
        m = fold(marker)
        if not m:
            continue
        seen, at = set(), body.find(m)
        while at != -1:
            if lines[at] not in seen:
                seen.add(lines[at])
                yield i, lines[at]
            at = body.find(m, at + 1)


def judge_paths(report, paths, view, markers, where="", refused=None):
    """The allow-list, the agent tool's files and the markers, over paths of the public repository; the paths refused
    as undeclared are added to `refused` when it is given."""
    undeclared = agent = 0
    for path in paths:
        part = unsafe_part(path)
        if part is not None:
            report.error(f"{where}{path}: a path with {part!r} in it, which nothing may publish or write")
        if is_agent_file(path):
            agent += 1
            report.error(f"{where}{path}: the agent tool's file, never public")
        elif not view.declared_public(path):
            undeclared += 1
            if refused is not None:
                refused.add(path)
            side = view.side_of(path)
            report.error(f"{where}{path}: not declared public ({'declared ' + side if side else 'no rule: private'})")
        for i, _ in marker_hits(path, markers):
            report.error(f"marker {i}: in the path {where}{path}")
    return undeclared, agent


def judge_content(report, path, data, markers):
    """The markers over a file's text; an image, a binary file or a large one is listed instead of read."""
    binary = b"\0" in data[:8000]
    if path.lower().endswith(IMAGES) or binary or len(data) > LARGE:
        report.listed.append(f"{path} ({len(data)} B)")
    if not binary:
        for i, n in marker_hits(data.decode("utf-8", errors="replace"), markers):
            report.error(f"marker {i}: {path}:{n}")


def judge_files(report, files, view, markers):
    """The paths and the content of (path, bytes) pairs, with a line for each part."""
    undeclared, agent = judge_paths(report, [p for p, _ in files], view, markers)
    for path, data in files:
        judge_content(report, path, data, markers)
    report.parts.append(f"declared public: {len(files) - undeclared - agent} of {len(files)} file(s)")
    report.parts.append(f"the agent tool's files: {agent or 'none'}")


def judge_words(report, what, text, markers):
    for i, _ in marker_hits(text, markers):
        report.error(f"marker {i}: in {what}")


def markers_part(report, markers):
    found = any(e.startswith("marker ") for e in report.errors)
    report.parts.append("markers: none were given" if not markers else
                        f"markers: {len(markers)} given" + ("" if found else ", none found"))


def judge_identity(report, identities, old_emails, ok):
    bad = sorted({e for _, e in identities if e in old_emails})
    if bad and not ok:
        report.error("identity: the old history's e-mail would sign the public commits; answer another, or give "
                     "the owner's yes (old-email-ok)")
    report.parts.append("identity: " + ("an e-mail of the old history, with the owner's yes" if bad and ok else
                                        "an e-mail of the old history" if bad else "not an e-mail of the old history"))


def gitleaks(args, root, config=None):
    """Run gitleaks with replace refs off, an explicit configuration or none, and no ignore file of the scanned tree;
    (ran, findings as 'rule in path:line', note). A scan that did not run is never a clean one."""
    exe = shutil.which("gitleaks")
    if exe is None:
        return False, [], INSTALL
    folder = tempfile.mkdtemp(prefix="check-public-")
    try:
        os.chmod(folder, 0o700)
        report = Path(folder) / "report.json"
        nothing = Path(folder) / "no-ignore"
        nothing.mkdir()
        extra = ["--config", str(config)] if config else []
        p = subprocess.run([exe, *args, *extra, "--gitleaks-ignore-path", str(nothing), "--no-banner", "--redact",
                            "--exit-code", "1", "--report-format", "json", "--report-path", str(report)],
                           capture_output=True, text=True, env=env())
        try:
            found = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            found = None
        if p.returncode not in (0, 1) or not isinstance(found, list):
            last = (p.stderr.strip().splitlines() or ["no output"])[-1]
            return False, [], f"gitleaks did not run (exit {p.returncode}, no report): {last}"
        hits = []
        for f in found:
            name = f.get("File", "")
            try:
                name = str(Path(name).relative_to(root))
            except ValueError:
                pass
            hits.append(f"{f.get('RuleID')} in {name}:{f.get('StartLine')}"
                        + (f" (commit {f['Commit'][:10]})" if f.get("Commit") else ""))
        return True, hits, ""
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def judge_secrets(report, ran, hits, note, what):
    if not ran:
        report.error(note)
        report.parts.append(f"gitleaks: did not run on {what}")
        return
    for h in hits:
        report.error(f"gitleaks: {h}")
    report.parts.append(f"gitleaks: ran on {what}, {len(hits)} finding(s)")


# ---------------------------------------------------------------- reading a repository

def run_git(root, *args, check=True, stdin=None, binary=False, allowed=(0,)):
    """Run git with replace refs off. A failure is an error (exit 2 for the command), never an empty answer, unless
    the caller names the exit codes that are answers (`allowed`) or takes the result whole (`check=False`) and says
    why. Text is read as UTF-8 with undecodable bytes kept, so a path that is not UTF-8 is a name, never a crash."""
    exe = shutil.which("git")
    if exe is None:
        raise Usage("git is not installed")
    kw = {} if binary else {"text": True, "encoding": "utf-8", "errors": "surrogateescape"}
    p = subprocess.run([exe, "-c", "core.quotepath=off", "-C", str(root), *args], capture_output=True, input=stdin,
                       env=env(), **kw)
    if check and p.returncode not in allowed:
        err = p.stderr if not binary else p.stderr.decode(errors="replace")
        raise Usage(f"git {' '.join(args)} failed in {root} (exit {p.returncode}): {err.strip()}")
    return p


def git(root, *args, check=True, allowed=(0,)):
    return run_git(root, *args, check=check, allowed=allowed).stdout


def blobs(root, oids):
    """{oid: bytes} through one `git cat-file --batch`; a missing object is an error, never an empty file."""
    if not oids:
        return {}
    out = run_git(root, "cat-file", "--batch", stdin=("\n".join(oids) + "\n").encode(), binary=True).stdout
    pos, data = 0, {}
    while pos < len(out):
        nl = out.index(b"\n", pos)
        head = out[pos:nl].decode().split()
        if len(head) < 3:
            raise Usage(f"git cat-file: object {head[0] if head else '?'} is missing from {root}")
        size = int(head[2])
        data[head[0]] = out[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
    return data


def split_z(text):
    return [x for x in text.split("\0") if x]


def top_of(start):
    """The top folder of the repository holding `start`, asked without the git variables a hook inherits: a push run
    from inside the `.git` folder, or with GIT_WORK_TREE set, still names the repository the hook belongs to."""
    p = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                       env=env())
    if p.returncode != 0 or not p.stdout.strip():
        raise Usage(f"{Path(start).resolve()} is not inside a git repository's working tree")
    return Path(p.stdout.strip()).resolve()


def private_root_of(root):
    """The private repository the public one sits in: the superproject, or the parent whose .gitmodules names it.
    Both lookups may fail harmlessly: each failure only moves on to the next way, and the last one refuses."""
    sup = git(root, "rev-parse", "--show-superproject-working-tree", check=False).strip()
    if sup:
        return Path(sup)
    parent = root.parent
    modules = parent / ".gitmodules"
    if modules.is_file():
        q = run_git(parent, "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$", allowed=(0, 1))
        if any(line.split(" ", 1)[1].strip() == root.name for line in q.stdout.splitlines()):
            return parent
    raise Usage(f"{root} sits in no private repository: run the gate from inside the public repository, or give "
                "--private-root, or --sides and --markers")


def old_emails(private):
    """Every e-mail of the private history; a history that cannot be read stops the gate (exit 2), since an empty
    answer would let the old e-mail through."""
    return set(split_z(git(private, "log", "--all", "--format=%ae%x00%ce").replace("\n", "\0")))


def identities(root):
    """The identities the next commit may take: the configured ones and what git will actually use."""
    out = []
    # `git config` exits 1 when the key is unset, an answer; any other exit is an error.
    name = git(root, "config", "user.name", allowed=(0, 1)).strip()
    email = git(root, "config", "user.email", allowed=(0, 1)).strip()
    if name or email:
        out.append((name, email))
    for var in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        # Harmless when it fails: git var fails only when git has no identity at all, and then no commit can be made
        # for the gate to let through.
        ident = git(root, "var", var, check=False).strip()
        if "<" in ident:
            out.append((ident.split("<")[0].strip(), ident.split("<", 1)[1].split(">")[0]))
    return out


def untracked_gitleaks_files(report, root, tracked):
    """A gitleaks configuration that sits in the public folder without being tracked would reconfigure the scan from
    the working tree: a stop. A tracked one is in effect, and said."""
    for name in GITLEAKS_FILES:
        if (root / name).exists() and name not in tracked:
            report.error(f"{name}: an untracked gitleaks configuration in the public folder; the gate's scan cannot be "
                         "configured from the working tree: commit it with the owner's yes, or remove it")


def ignore_source(root, path):
    """The file whose rule ignores a path ('' when none does); git's own exclude file and the global one count as
    files too, and are never a tracked rule of the public repository."""
    # check-ignore exits 1 when nothing ignores the path, an answer; any other exit is an error.
    return git(root, "check-ignore", "-v", "--no-index", "--", path, allowed=(0, 1)).split(":", 1)[0]


def expand(root, entry):
    """The files physically under an ignored folder entry, as paths from the root."""
    base = root / entry.rstrip("/")
    if not base.is_dir():
        return [entry]
    return sorted(str(p.relative_to(root)).replace(os.sep, "/") for p in base.rglob("*") if p.is_file())


def staged(root, sides, markers, olds, message=""):
    """The gate on what the next commit of the public repository would hold. `sides` is the project's Sides."""
    report = Report()
    view = sides.public_view()
    entries = [e.split("\t", 1) for e in split_z(git(root, "ls-files", "-s", "-z"))]
    paths = {path: head.split()[1] for head, path in entries}
    data = blobs(root, sorted(set(paths.values())))
    judge_files(report, [(p, data[o]) for p, o in sorted(paths.items())], view, markers)
    for name, email in identities(root):
        judge_words(report, "the identity", f"{name} <{email}>", markers)
    if message:
        judge_words(report, "the commit message", message, markers)
    markers_part(report, markers)
    untracked_gitleaks_files(report, root, paths)
    for name in GITLEAKS_FILES:
        if name in paths and (root / name).is_file() and (root / name).read_bytes() != data[paths[name]]:
            report.error(f"{name}: changed in the working tree since it was staged; stage it or restore it")
    # The staged files are scanned as a copy in a private folder, as a push's are: `gitleaks git` reports a clean
    # scan when git fails inside it, which the gate could not tell from a clean tree.
    folder = tempfile.mkdtemp(prefix="check-public-staged-")
    try:
        os.chmod(folder, 0o700)
        export = (Path(folder) / "files").resolve()
        export.mkdir()
        for path, oid in paths.items():
            dest = export / path
            if unsafe_part(path) is not None or not dest.resolve().is_relative_to(export):
                dest = export / "unsafe-names" / oid
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data[oid])
        config = None
        if ".gitleaks.toml" in paths:
            config = Path(folder) / "gitleaks.toml"
            config.write_bytes(data[paths[".gitleaks.toml"]])
            report.parts.append("gitleaks: the repository's own .gitleaks.toml is in effect, as tracked")
        ran, hits, note = gitleaks(["dir", str(export)], export, config)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    judge_secrets(report, ran, hits, note, f"the {len(paths)} staged file(s)")
    judge_inside(report, root, view, paths)
    judge_identity(report, identities(root), olds, sides.old_email_ok)
    return report


def judge_inside(report, root, view, tracked):
    """What sits inside the public folder without being staged: ignored entries must be `local`, hold no private
    path, and be ignored by the public repository's own tracked rules; anything untracked and not ignored would be
    private material left inside."""
    ignored = split_z(git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z"))
    for entry in ignored:
        if view.ignored_side(entry) != "local":
            report.error(f"{entry}: ignored inside the public folder without the word local: private material "
                         "physically inside the public repository")
            continue
        if entry.endswith("/") and any(w == "private" and covers(entry, r) and r != entry
                                       for r, w in view.words.items()):
            for f in expand(root, entry):
                if view.ignored_side(f) == "private":
                    report.error(f"{f}: private, inside the local entry {entry} in the public folder")
        # A folder ignored as a whole answers for a file under it; a folder whose files are ignored one by one
        # answers file by file.
        probes = [entry + ".probe"] if entry.endswith("/") else [entry]
        if entry.endswith("/") and ignore_source(root, probes[0]) not in tracked:
            probes = expand(root, entry)
        for probe in probes:
            source = ignore_source(root, probe)
            if source not in tracked:
                report.error(f"{entry}: local, but ignored only by {source or 'nothing'}, not by a tracked rule of "
                             "the public repository")
                break
    for rule, word in view.words.items():
        if word == "local" and any(covers(rule, p) for p in tracked):
            report.error(f"{rule}: declared local, but tracked")
    for entry in split_z(git(root, "ls-files", "--others", "--exclude-standard", "-z")):
        report.error(f"{entry}: untracked inside the public folder, neither staged nor ignored")
    locals_ = [r for r, w in view.words.items() if w == "local"]
    report.parts.append(f"ignore: {len(ignored)} ignored entr{'y' if len(ignored) == 1 else 'ies'} inside, "
                        f"{len(locals_)} local rule(s)")


def object_types(root, oids):
    if not oids:
        return {}
    out = run_git(root, "cat-file", "--batch-check=%(objectname) %(objecttype)", stdin="\n".join(oids) + "\n").stdout
    return dict(line.split() for line in out.splitlines() if not line.endswith(" missing"))


def exists(root, spec):
    """Whether an object is in the repository. `cat-file -e` answers only yes or no, and a failure reads as 'not
    there': every use below only widens what the gate reads, or drops an extra line of explanation, on that answer."""
    return run_git(root, "cat-file", "-e", spec, check=False).returncode == 0


ID_HEADER = re.compile(r"(tree|parent|object) [0-9a-f]{40}(?:[0-9a-f]{24})?")
SIGNATURE_HEADERS = ("gpgsig", "gpgsig-sha256")


def object_text(raw):
    """(headers, message) of a commit's or a tag's raw text, parsed as git writes it: the headers run to the first
    blank line, each a name, a space and a value, a value going on over the lines that begin with a space; the message
    is the rest, whole, whatever it holds. Left out of the headers: the values of `tree`, `parent` and `object` that
    are object ids, and the `gpgsig` and `gpgsig-sha256` headers (the signature git writes for a commit). A `mergetag`
    header's value is a tag object, parsed by this same function: its own headers and its message are kept, its
    `object` id left out."""
    head, _, message = raw.partition("\n\n")
    headers = []
    for line in head.split("\n") if head else []:
        if line.startswith(" ") and headers:
            headers[-1].append(line[1:])
        else:
            headers.append([line])
    kept = []
    for value_lines in headers:
        first = value_lines[0]
        name = first.split(" ", 1)[0]
        if name in SIGNATURE_HEADERS:
            continue
        if len(value_lines) == 1 and ID_HEADER.fullmatch(first):
            continue
        if name == "mergetag":
            inner_head, inner_message = object_text("\n".join([first[len("mergetag "):]] + value_lines[1:]))
            kept += ["mergetag", inner_head, inner_message]
            continue
        kept.append("\n".join(value_lines))
    return "\n".join(kept), message


def judge_raw(report, what, raw, markers, olds, ok):
    """The markers and the old history's e-mails over what was written in a commit's or tag's text: its headers (a
    merge commit's `mergetag` carries a tag's tagger and message) and its whole message, each named in the error.
    Object ids and a commit's signature header are left out, since nobody wrote them."""
    head, message = object_text(raw)
    judge_words(report, f"{what}'s headers", head, markers)
    judge_words(report, f"{what}'s message", message, markers)
    if not ok:
        low = (head + "\n" + message).casefold()
        if any(e and e.casefold() in low for e in olds):
            report.error(f"{what}: holds the old history's e-mail")


def pre_push(root, remote, refs, sides, markers, olds):
    """The gate on what a push sends: every object it adds to the remote, and each pushed ref's name."""
    report = Report()
    view = sides.public_view()
    tips, exclude, ref_names = [], [], set()
    for line in refs:
        fields = line.split()
        if len(fields) != 4:
            continue
        local_ref, local, remote_ref, remote_sha = fields
        if set(local) == {"0"}:
            continue  # a deletion sends nothing
        tips.append(local)
        ref_names |= {local_ref, remote_ref}
        if set(remote_sha) != {"0"} and exists(root, remote_sha):
            exclude.append(remote_sha)
    if not tips:
        report.parts.append("nothing to push but deletions")
        return report
    for name in sorted(ref_names):
        judge_words(report, f"the ref name {name}", name, markers)
    # The objects the push adds: reachable from the pushed ids and not from the ids the remote says, on standard input,
    # that it holds. Remote-tracking refs say what the remote held once, not what it holds now, and are not believed:
    # a new branch is judged whole.
    names = {}
    for line in git(root, "rev-list", "--objects", *tips, "--not", *exclude).splitlines():
        oid, _, path = line.partition(" ")
        names.setdefault(oid, path)
    # Whatever a pushed id peels to is judged: each tag on the way, and a tree or blob it names at the end, whole.
    final = []
    for tip in tips:
        oid = tip
        while object_types(root, [oid]).get(oid) == "tag":
            if oid not in exclude:
                names.setdefault(oid, "")
            oid = git(root, "cat-file", "tag", oid).split("\n", 1)[0].split()[1]
        final.append(oid)
    types = object_types(root, list(names) + final)
    commits = [o for o in names if types.get(o) == "commit"]
    tags = [o for o in names if types.get(o) == "tag"]
    new_blobs = [o for o in names if types.get(o) == "blob"]
    refused = set()
    for c in commits:
        judge_raw(report, f"commit {c[:10]}", git(root, "cat-file", "commit", c), markers, olds, sides.old_email_ok)
        judge_paths(report, split_z(git(root, "ls-tree", "-r", "-z", "--name-only", c)), view, markers,
                    where=f"commit {c[:10]}: ", refused=refused)
    for t in tags:
        judge_raw(report, f"tag {t[:10]}", git(root, "cat-file", "tag", t), markers, olds, sides.old_email_ok)
    for oid in final:
        if types.get(oid) == "tree" and oid not in exclude:
            judge_paths(report, split_z(git(root, "ls-tree", "-r", "-z", "--name-only", oid)), view, markers,
                        where=f"tree {oid[:10]}: ", refused=refused)
    # A path refused now that commits the remote already holds carry too: a rule made it private after it was
    # pushed. Every new commit built on them still publishes it, and only a new history without them can go.
    held = set()
    for old in exclude:
        if exists(root, f"{old}^{{commit}}"):
            held |= set(split_z(git(root, "ls-tree", "-r", "-z", "--name-only", f"{old}^{{commit}}")))
    for path in sorted(refused & held):
        report.error(f"{path}: already in commits the remote holds, and a rule made it private after: those commits "
                     "publish it, and only a new history without them can be pushed")
    data = blobs(root, new_blobs)
    for oid in new_blobs:
        judge_content(report, names.get(oid) or oid, data[oid], markers)
    markers_part(report, markers)
    untracked_gitleaks_files(report, root, set(split_z(git(root, "ls-files", "-z"))))
    # The secret scan reads exactly the new blobs, exported to a private folder, with the configuration the pushed
    # commits track, if any, and never one from the working tree. A tip that is no commit tracks no configuration.
    configs = set()
    for tip in tips:
        if exists(root, f"{tip}^{{commit}}:.gitleaks.toml"):
            configs.add(git(root, "rev-parse", f"{tip}^{{commit}}:.gitleaks.toml").strip())
    folder = tempfile.mkdtemp(prefix="check-public-push-")
    try:
        os.chmod(folder, 0o700)
        export = (Path(folder) / "blobs").resolve()
        export.mkdir()
        for oid in new_blobs:
            name = names.get(oid) or oid
            if unsafe_part(name) is not None:
                report.error(f"{name}: a path with {unsafe_part(name)!r} in it, which nothing may publish or write; "
                             "its content is scanned under its object id")
                name = oid
            dest = export / oid[:12] / name
            if not dest.resolve().is_relative_to(export):
                report.error(f"{name}: a path that leads out of the scan's folder; scanned under its object id")
                dest = export / oid[:12] / oid
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data[oid])
        config = None
        if len(configs) > 1:
            report.error("the pushed refs track different .gitleaks.toml files; push them one at a time")
        elif configs:
            config = Path(folder) / "gitleaks.toml"
            config.write_bytes(blobs(root, list(configs))[next(iter(configs))])
            report.parts.append("gitleaks: the repository's own .gitleaks.toml is in effect, as tracked")
        ran, hits, note = gitleaks(["dir", str(export)], export, config)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    judge_secrets(report, ran, hits, note, f"the {len(new_blobs)} new blob(s)")
    report.parts.append(f"pushed: {len(commits)} new commit(s), {len(tags)} annotated tag(s), {len(new_blobs)} new "
                        f"blob(s), on {len(tips)} ref(s)")
    return report


# ---------------------------------------------------------------- the command

def load_lists(root, args):
    private = Path(args.private_root).resolve() if args.private_root else None
    sides_file = Path(args.sides) if args.sides else None
    marks = Path(args.markers) if args.markers else None
    if not (sides_file and marks) or private is None:
        private = private or private_root_of(root)
        sides_file = sides_file or private / SIDES_FILE
        marks = marks or private / MARKERS_FILE
    for f in (sides_file, marks):
        if not f.is_file():
            raise Usage(f"{f} is not there: the private side keeps {SIDES_FILE} and {MARKERS_FILE}")
    sides = Sides.parse(sides_file.read_text(encoding="utf-8"), str(sides_file))
    sides.old_email_ok = sides.old_email_ok or args.old_email_ok
    return sides, read_markers_file(marks), old_emails(private)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="judge what the next commit would hold")
    mode.add_argument("--pre-push", nargs="*", metavar="ARG", help="judge what a push sends (git's hook arguments, "
                      "the remote's name and URL; the refs on standard input)")
    p.add_argument("--root", default=".", help="the public repository (default: the current folder's)")
    p.add_argument("--private-root", help="the private repository holding the lists")
    p.add_argument("--sides", help=f"the allow-list (default: {SIDES_FILE} at the private root)")
    p.add_argument("--markers", help=f"the markers (default: {MARKERS_FILE} at the private root)")
    p.add_argument("--message", default="", help="the commit message the staged files will get")
    p.add_argument("--old-email-ok", action="store_true", help="the owner's yes to the old history's e-mail")
    args = p.parse_args(argv)
    # A path that is not UTF-8 is printed with its bytes escaped, never as a crash.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    try:
        root = top_of(args.root)
        sides, markers, olds = load_lists(root, args)
        if args.staged:
            report = staged(root, sides, markers, olds, args.message)
        else:
            remote = args.pre_push[0] if args.pre_push else ""
            report = pre_push(root, remote, sys.stdin.read().splitlines(), sides, markers, olds)
    except Usage as ex:
        print(f"check-public: {ex}", file=sys.stderr)
        return 2
    print(f"check-public: {'the staged tree' if args.staged else 'the push'} of {root}")
    report.print()
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
