#!/usr/bin/env python3
"""Check a project's archive: the freeze stamp of every archived file, the log row of every change made to one, and
the table of vocabulary conflicts; and, for a session, which conflicts apply to a file and where a word occurs.

    check-archive [--archive DIR]               the check, run by the hook and in CI
    check-archive [--archive DIR] read FILE     FILE's freeze stamp and the conflicts dated after it, oldest first
    check-archive [--archive DIR] rename WORD   every line of the archive holding WORD, with each file's stamp
    python3 check_archive.py ...                from the kit, without installing

DIR is the archive folder, `archive` by default; its log is DIR/LOG.md. The check exits 1 on any failure; `read`
exits 1 when the file's freeze time or a conflict's time cannot be read; `rename` changes nothing and exits 0 whether
or not it finds the word. Every verb exits 2 on bad arguments or a file that cannot be read. Where git is missing,
or the archive is not in a repository, the checks that need it are reported as not run, and the exit code is 1: a
check that did not run is not a check that passed. Standard library only, so it
runs wherever Python 3.10 does.
"""

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

LOG, INDEX = "LOG.md", "README.md"  # the archive's own files, at its top: not archived documents
CHANGES = ("date", "file", "what", "why and who decided", "commit")
CONFLICTS = ("date", "kind", "old", "now", "where the current meaning is defined")
KINDS = ("renamed", "reused")
# A change to an archived file, as `git diff --name-status` letters it; an added file is an archiving, not a change.
CHANGE_LETTERS = {"M": "modified", "D": "deleted", "R": "renamed", "T": "changed type"}
# The kit's timestamp, the form of the frontmatter's `updated:`: one offset, so the text sorts as the time does.
TIME_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+00:00$")
TIME_FORM = "YYYY-MM-DDTHH:MM:SS+00:00"
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
COMMIT_RE = re.compile(r"^(HEAD|[0-9a-f]{7,40})$")
# How far a freeze stamp may precede the commit that moved its file in: written before midnight, committed after.
TOLERANCE = timedelta(days=1)
LINK_RE = re.compile(r"\]\(([^)\s]+)")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
EMPTY = ("", "-", "—")


class Usage(Exception):
    """A bad argument, or a file that cannot be read: exit 2."""


# ---------------------------------------------------------------- reading the files

def parse_time(text):
    """The datetime of a stamp in the kit's form, or None."""
    text = text.strip()
    if not TIME_RE.match(text):
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def parse_date(text):
    text = text.strip()
    if not DATE_RE.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def frontmatter(text):
    """The leading frontmatter's fields as text, or None when the file opens with none."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip("'\"")
    return None


def stamp_of(path):
    """(the `archived:` stamp's text or None, its datetime or None)."""
    fields = frontmatter(read_text(path)) or {}
    text = fields.get("archived")
    return text, parse_time(text) if text else None


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise Usage(f"cannot read {path}: {getattr(e, 'strerror', None) or e}") from e


def normalise(text):
    return " ".join(re.sub(r"[^a-z ]", " ", text.lower()).split())


def split_row(line):
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") and not s.endswith("\\|") else s
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def is_separator(cells):
    return all(re.fullmatch(r":?-+:?", c) for c in cells)


@dataclass
class Row:
    line: int
    text: str
    cells: dict


@dataclass
class Log:
    path: str
    changes: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    tables: set = field(default_factory=set)


def read_log(text, path):
    """The log's two tables, read outside code fences and HTML comments (where the template keeps its example rows);
    a table whose header opens with Date is one of the two, and anything else is prose."""
    log = Log(path)
    lines = text.splitlines()
    fence, comment, i = None, False, 0
    while i < len(lines):
        line = lines[i]
        if comment:
            comment = "-->" not in line
            i += 1
            continue
        m = FENCE_RE.match(line)
        if fence is None and m:
            fence = m.group(1)
        elif fence is not None and set(line.strip()) == {fence[0]} and len(line.strip()) >= len(fence):
            fence = None
        elif fence is None and line.lstrip().startswith("<!--"):
            comment = "-->" not in line
        elif fence is None and line.lstrip().startswith("|"):
            table = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                table.append((i + 1, lines[i], split_row(lines[i])))
                i += 1
            read_table(log, table)
            continue
        i += 1
    return log


def read_table(log, table):
    n, _, header = table[0]
    columns = tuple(normalise(c) for c in header)
    if not columns or columns[0] != "date":
        # A row cut off from its header by a blank line or a comment is read as nothing by Markdown: say so.
        if parse_date(plain(header[0])[:10]):
            log.errors.append(f"{log.path}:{n}: a row outside its table: a blank line or a comment separates it "
                              f"from the table's header")
        return
    if columns == CHANGES:
        kind, rows = "changes", log.changes
    elif columns == CONFLICTS:
        kind, rows = "conflicts", log.conflicts
    else:
        log.errors.append(f"{log.path}:{n}: a table opening with Date has the columns of neither of the log's tables: "
                          f"{' | '.join(CHANGES)}, or {' | '.join(CONFLICTS)}")
        return
    if kind in log.tables:
        log.errors.append(f"{log.path}:{n}: a second {kind} table; the log has one")
    log.tables.add(kind)
    body = table[1:]
    if body and is_separator(body[0][2]):
        body = body[1:]
    for line, text, cells in body:
        if len(cells) != len(columns):
            log.errors.append(f"{log.path}:{line}: {len(cells)} cells where the table has {len(columns)}")
            continue
        rows.append(Row(line, text.strip(), dict(zip(columns, cells))))


def plain(cell):
    """A cell's value without Markdown emphasis or backticks."""
    return cell.strip().strip("*_`").strip()


def has_text(cell):
    return cell.strip() not in EMPTY


def check_log(log, root):
    """The rows' own rules; `root` is the folder holding the archive, from which a definition's path is read."""
    errors = list(log.errors)
    for kind in ("changes", "conflicts"):
        if kind not in log.tables:
            errors.append(f"{log.path}: no {kind} table, with the columns "
                          f"{' | '.join(CHANGES if kind == 'changes' else CONFLICTS)}")
    for row in log.changes:
        c, where = row.cells, f"{log.path}:{row.line}"
        if not parse_date(c["date"]):
            errors.append(f"{where}: date '{c['date']}' is not a date YYYY-MM-DD")
        for col in ("file", "what", "why and who decided"):
            if not has_text(c[col]):
                errors.append(f"{where}: the {col} column is empty")
        if not COMMIT_RE.match(plain(c["commit"])):
            errors.append(f"{where}: commit '{c['commit']}' is neither a commit hash nor HEAD (the commit that adds "
                          f"the row)")
    for row in log.conflicts:
        c, where = row.cells, f"{log.path}:{row.line}"
        if not parse_time(c["date"]):
            errors.append(f"{where}: date '{c['date']}' is not a time {TIME_FORM}")
        if plain(c["kind"]).lower() not in KINDS:
            errors.append(f"{where}: kind '{c['kind']}' is not one of {', '.join(KINDS)}")
        for col in ("old", "now"):
            if not has_text(c[col]):
                errors.append(f"{where}: the {col} column is empty")
        problem = definition_problem(c["where the current meaning is defined"], Path(log.path).parent, root)
        if problem:
            errors.append(f"{where}: {problem}")
    return errors


def definition_problem(cell, log_dir, root):
    """Why the cell does not name where the current meaning is defined, or None: a URL, a link from the log, or a
    path from the folder holding the archive."""
    link, span = LINK_RE.search(cell), CODE_SPAN_RE.search(cell)
    target, base = (link.group(1), log_dir) if link else (span.group(1) if span else plain(cell), root)
    target = target.strip()
    if not has_text(target):
        return "no place where the current meaning is defined"
    if URL_RE.match(target):
        return None
    path = target.split("#", 1)[0]
    if not path or not (base / path).exists():
        return f"where-defined '{target}' does not exist (a path from {root}, a link from the log, or a URL)"
    return None


# ---------------------------------------------------------------- git

class Git:
    """The repository holding the archive, read with plain git commands; `why` says why it is not there."""

    def __init__(self, archive):
        self.top, self.why = None, None
        binary = shutil.which("git")
        if binary is None:
            self.why = "git is not installed"
            return
        self.binary = binary
        p = subprocess.run([binary, "rev-parse", "--show-toplevel"], cwd=archive, capture_output=True, text=True)
        if p.returncode != 0:
            self.why = f"{archive} is not inside a git repository"
            return
        self.top = Path(p.stdout.strip()).resolve()
        rel = Path(archive).resolve().relative_to(self.top).as_posix()
        self.prefix = "" if rel == "." else rel + "/"

    def run(self, *args):
        return subprocess.run([self.binary, "-c", "core.quotepath=off", *args], cwd=self.top, capture_output=True,
                              text=True)

    def under(self, path):
        return path.startswith(self.prefix)

    def tracked(self):
        p = self.run("ls-files", "--", self.prefix or ".")
        return set(p.stdout.splitlines()) if p.returncode == 0 else set()

    def staged(self):
        """[(letter, old path, new path)] of the staged changes under the archive, renames detected inside it."""
        p = self.run("diff", "--cached", "-M", "--name-status", "--", self.prefix or ".")
        out = []
        for line in p.stdout.splitlines():
            parts = line.split("\t")
            letter = parts[0][:1]
            out.append((letter, parts[1], parts[-1]))
        return out

    def entered(self, path):
        """When the file at `path` last entered the archive: the commit that added it there, or moved it there from
        outside, following its renames inside the archive (`--follow` traces a file through renames and copies, and
        reads an identical file as a copy). None when git has no such commit."""
        p = self.run("log", "--follow", "-M", "--name-status", "--format=%x01%cI", "--", path)
        for block in p.stdout.split("\x01")[1:]:
            lines = [ln for ln in block.splitlines() if ln.strip()]
            if len(lines) < 2:
                continue
            when = datetime.fromisoformat(lines[0].strip())
            parts = lines[1].split("\t")
            letter, old, new = parts[0][:1], parts[1], parts[-1]
            if not self.under(new):
                return None
            # A copy is a new file, wherever it was copied from; only a rename inside the archive is followed on.
            if letter in "AC" or (letter == "R" and not self.under(old)):
                return when
        return None

    def show(self, spec):
        p = self.run("show", spec)
        return p.stdout if p.returncode == 0 else None


def agrees(stamp, entered):
    """A stamp agrees with the time its file entered the archive when both fall on the same day, or the stamp
    precedes it by less than TOLERANCE."""
    s, e = stamp.astimezone(timezone.utc), entered.astimezone(timezone.utc)
    return s.date() == e.date() or timedelta(0) <= e - s < TOLERANCE


def fmt(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


# ---------------------------------------------------------------- the verbs

def archived_files(archive):
    """Every Markdown file under the archive but its own log and index."""
    return sorted(p for p in archive.rglob("*.md")
                  if p.is_file() and p.relative_to(archive).as_posix() not in (LOG, INDEX))


def names(cell, paths):
    """Whether a Changes row's File cell names one of `paths`: a file's path inside the archive, or from the folder
    holding it, or from the repository's top."""
    values = CODE_SPAN_RE.findall(cell) + LINK_RE.findall(cell) or [plain(cell)]
    return any(v.strip().split("#", 1)[0].removeprefix("./") in paths for v in values)


def check(archive, now=None):
    """Return (errors, notes, not_run, summary)."""
    now = now or datetime.now(timezone.utc)
    errors, notes, not_run = [], [], []
    root = archive.parent
    log_path = archive / LOG
    if log_path.is_file():
        log = read_log(read_text(log_path), str(log_path))
        errors += check_log(log, root)
    else:
        log = Log(str(log_path))
        errors.append(f"{log_path}: the archive has no log; start it from the kit's archive/templates/LOG.md")

    files = archived_files(archive)
    stamps = {}
    for path in files:
        text, when = stamp_of(path)
        if text is None:
            errors.append(f"{path}: no `archived:` stamp in its frontmatter; the commit that moved it into the "
                          f"archive writes one, {TIME_FORM}")
        elif when is None:
            errors.append(f"{path}: archived '{text}' is not a time {TIME_FORM}")
        else:
            stamps[path] = when

    git = Git(archive)
    if git.top is None:
        not_run.append(f"the stamps against git, and the staged changes against the log: {git.why}")
    else:
        tracked = git.tracked()
        staged = git.staged()
        being_added = {new for letter, _, new in staged if letter == "A"}
        for path, when in stamps.items():
            rel = git.prefix + path.relative_to(archive).as_posix()
            if rel in being_added:
                entered, what = now, "the commit being made, which adds it"
            elif rel in tracked:
                entered, what = git.entered(rel), "the commit that moved it into the archive"
                if entered is None:
                    notes.append(f"{path}: git has no commit that moved it into the archive; its stamp is not "
                                 f"compared")
                    continue
            else:
                notes.append(f"{path}: not tracked by git; its stamp is not compared")
                continue
            if not agrees(when, entered):
                errors.append(f"{path}: archived {fmt(when)}, but {what} is dated {fmt(entered)}; the stamp is "
                              f"the time the file entered the archive")
        changes = [(letter, old, new) for letter, old, new in staged if letter in CHANGE_LETTERS
                   and not {old[len(git.prefix):], new[len(git.prefix):]} & {LOG, INDEX}]
        if changes:
            staged_log = git.show(f":{git.prefix}{LOG}")
            head_log = git.show(f"HEAD:{git.prefix}{LOG}") or ""
            old_rows = [r.text for r in read_log(head_log, "HEAD").changes]
            new_rows = []
            for r in read_log(staged_log or "", "staged").changes:
                if r.text in old_rows:
                    old_rows.remove(r.text)
                else:
                    new_rows.append(r)
            for letter, old, new in changes:
                paths = {q for p in (old, new) if git.under(p)
                         for q in (p, p[len(git.prefix):], f"{archive.name}/{p[len(git.prefix):]}")}
                if not any(names(r.cells["file"], paths) for r in new_rows):
                    shown = old if old == new else f"{old} -> {new}"
                    errors.append(f"{shown}: {CHANGE_LETTERS[letter]} in the commit being made, and no new row of "
                                  f"the staged {git.prefix}{LOG}'s Changes table names it (Commit: HEAD)")
    summary = (f"{archive}: {len(files)} archived file(s); {LOG}: {len(log.changes)} change(s), "
               f"{len(log.conflicts)} conflict(s)")
    return errors, notes, not_run, summary


def inside(archive, file):
    try:
        return Path(file).resolve().relative_to(archive.resolve()).as_posix()
    except ValueError:
        raise Usage(f"{file} is not under the archive {archive}; name the archive with --archive") from None


def read(archive, file):
    """Print the file's freeze stamp and the conflicts dated after it; return the exit code."""
    rel = inside(archive, file)
    if rel in (LOG, INDEX) or not Path(file).is_file():
        raise Usage(f"{file} is not an archived file")
    text, frozen = stamp_of(file)
    log = read_log(read_text(archive / LOG), str(archive / LOG))
    code = 0
    if frozen is not None:
        print(f"{file}: archived {fmt(frozen)}")
    else:
        git = Git(archive)
        entered = git.entered(git.prefix + rel) if git.top else None
        if entered is not None:
            frozen = entered
            print(f"{file}: no valid `archived:` stamp; git says it entered the archive {fmt(entered)}")
        else:
            print(f"{file}: its freeze time is unknown (no valid `archived:` stamp, and none from git): every "
                  f"conflict below may apply")
            code = 1
    rows = []
    for row in log.conflicts:
        when = parse_time(row.cells["date"])
        if when is None:
            print(f"error: {log.path}:{row.line}: date '{row.cells['date']}' is not a time {TIME_FORM}; "
                  f"run check-archive")
            code = 1
        elif frozen is None or when > frozen:
            rows.append((when, row))
    if not rows:
        print("no conflicts apply")
        return code
    print("conflicts dated after it, oldest first; a REUSED word reads as a word, with the wrong meaning:")
    for when, row in sorted(rows, key=lambda r: r[0]):
        c = row.cells
        kind = "REUSED" if plain(c["kind"]).lower() == "reused" else plain(c["kind"]).lower()
        print(f"  {fmt(when)}  {kind:<7}  {c['old']}  ->  {c['now']}  "
              f"(defined in {c['where the current meaning is defined']})")
    return code


def rename(archive, word):
    """Print every line of the archive holding the word, file by file, and the two outcomes for each file."""
    if not word.strip():
        raise Usage("rename needs a word")
    pattern = re.compile(rf"(?<!\w){re.escape(word.strip())}(?!\w)", re.I)
    hits, hit_files = 0, 0
    files = [p for p in sorted(archive.rglob("*.md")) if p.is_file() and p.relative_to(archive).as_posix() != LOG]
    for path in files:
        found = [(n, line) for n, line in enumerate(read_text(path).splitlines(), 1) if pattern.search(line)]
        if not found:
            continue
        _, when = stamp_of(path)
        print(f"{path} ({f'archived {fmt(when)}' if when else 'no valid `archived:` stamp'})")
        for n, line in found:
            print(f"  {path}:{n}: {line.strip()}")
        print("  change it: edit these lines, and in the same commit add a row to the log's Changes table naming "
              "the file, Commit HEAD")
        print("  or leave it: the conflicts row of this rename covers it, since the file was frozen before it")
        hits, hit_files = hits + len(found), hit_files + 1
    if hits:
        print(f"{hits} line(s) in {hit_files} file(s); nothing was changed")
    else:
        print(f"no occurrence of '{word.strip()}' in {archive} (the log aside): no archived file needs a ruling")
    return 0


def parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--archive", metavar="DIR", default=argparse.SUPPRESS,
                        help="the archive folder (default: archive)")
    p = argparse.ArgumentParser(description="Check the archive and its log; read a file's conflicts; find a word.",
                                parents=[common])
    p.set_defaults(verb=None)
    verbs = p.add_subparsers(dest="verb", metavar="{read,rename}")
    r = verbs.add_parser("read", parents=[common], help="the freeze stamp of FILE and the conflicts dated after it")
    r.add_argument("file", metavar="FILE")
    n = verbs.add_parser("rename", parents=[common], help="every line of the archive holding WORD")
    n.add_argument("word", metavar="WORD")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    archive = Path(getattr(args, "archive", "archive"))
    try:
        if not archive.is_dir():
            raise Usage(f"no archive folder at {archive}; name it with --archive")
        if args.verb == "read":
            return read(archive, args.file)
        if args.verb == "rename":
            return rename(archive, args.word)
        errors, notes, not_run, summary = check(archive)
    except Usage as e:
        print(e, file=sys.stderr)
        return 2
    for e in errors:
        print(f"error: {e}")
    for n in notes:
        print(f"note: {n}")
    for n in not_run:
        print(f"NOT RUN: {n}")
    print(summary)
    print(f"{len(errors)} error(s)" + (f"; {len(not_run)} check(s) not run" if not_run else ""))
    return 1 if errors or not_run else 0


if __name__ == "__main__":
    sys.exit(main())
