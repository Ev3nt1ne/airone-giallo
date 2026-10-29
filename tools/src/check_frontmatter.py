#!/usr/bin/env python3
"""Hold the tracked Markdown documents to the frontmatter of the `markdown-docs` skill, and the documents being
committed to its two dates: `created` never moves, `updated` moves with every change.

    check-frontmatter                    the staged documents, against HEAD (the pre-commit hook's call)
    check-frontmatter --range A..B       the documents changed between two revisions, B's text against A's
    check-frontmatter --all              every tracked document, its block only
    python3 check_frontmatter.py ...     from the clone, without installing

Every document carries a block opening the file with `title`, `description`, `type`, `created` (YYYY-MM-DD) and
`updated` (YYYY-MM-DDTHH:MM:SS+00:00, not before `created`); a `status`, when present, is one of the lifecycle values
(--statuses), a `type` one of --types when that is given, `tags` a list without repeats; `archived` appears only in
the archive. In the body, outside code, the change-of-plan marker keeps its one meaning: it stands beside the words
CHANGE OF PLAN, on the heading it marks or in a legend that names it (--no-markers turns this off, for a project
with its own markers). For a document changed against the earlier text (staged, or in the range), `created`
is the same and `updated` is later whenever anything else in the file changed; a renamed document is compared with
its old path, a new one is checked for its block only.

Not checked: the agent layer (AGENTS.md and CLAUDE.md anywhere, RATIONALE.md and .claude/ at a repository's top),
the owner's notes (human-docs/), the sources' manifest (sources/), the forge's templates (.github/), and anything
--exempt names. In the archive (archive/ at a repository's top, or --archive) a document carries only its `archived:`
stamp in the time form, and nothing else is checked there; its own README.md and LOG.md are documents like any other.

Exit 1 on a finding, 2 on a bad argument or a repository that cannot be read. Standard library only.
"""

import argparse
import fnmatch
import posixpath
import re
import sys
from datetime import date, datetime

import airone_tree as at

REQUIRED = ("title", "description", "type", "created", "updated")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
TIME_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+00:00$")
TIME_FORM = "YYYY-MM-DDTHH:MM:SS+00:00"
STATUSES = ("active", "closed", "superseded")
# Exempt anywhere, by name; and at the top of each repository, by path.
EXEMPT_NAMES = ("AGENTS.md", "CLAUDE.md")
EXEMPT_TOP = ("RATIONALE.md", ".claude/", "human-docs/", "sources/", ".github/")
ARCHIVE_OWN = ("README.md", "LOG.md")
PLAN_MARK = "\U0001F53B"


def valid_date(text):
    if not DATE_RE.match(text or ""):
        return False
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def valid_time(text):
    if not TIME_RE.match(text or ""):
        return False
    try:
        datetime.strptime(text[:19], "%Y-%m-%dT%H:%M:%S")
        return True
    except ValueError:
        return False


class Scope:
    """Which documents are checked, and which are archived."""

    def __init__(self, subs, archives=None, exempt=()):
        self.tops = [""] + list(subs)
        self.archives = [a.strip("/") for a in archives] if archives else [at.join(t, "archive") for t in self.tops]
        self.exempt = list(exempt)

    def archive_of(self, path):
        for a in self.archives:
            if at.under(path, a) and path != a:
                return a
        return None

    def kind(self, path):
        """'document', 'archived', or None when the file is not checked."""
        if not path.lower().endswith((".md", ".markdown")):
            return None
        if posixpath.basename(path) in EXEMPT_NAMES:
            return None
        for pattern in self.exempt:
            p = pattern.strip("/")
            if fnmatch.fnmatch(path, pattern) or at.under(path, p):
                return None
        for t in self.tops:
            for e in EXEMPT_TOP:
                rel = at.join(t, e.rstrip("/"))
                if (e.endswith("/") and at.under(path, rel)) or path == rel:
                    return None
        a = self.archive_of(path)
        if a is not None:
            return "document" if path[len(a) + 1:] in ARCHIVE_OWN else "archived"
        return "document"


class Rules:
    def __init__(self, statuses=STATUSES, types=None, markers=True):
        self.statuses, self.types, self.markers = tuple(statuses), tuple(types or ()), markers

    def document(self, path, text):
        """The findings on one document's text."""
        fm = at.frontmatter(text)
        if fm is None:
            return [f"{path}: no frontmatter block opening the file (--- on the first line, closed by a second ---)"]
        out = []
        f = fm.fields
        for key in REQUIRED:
            if not f.get(key, "").strip():
                out.append(f"{path}: no `{key}:`" if key not in f else f"{path}: `{key}:` is empty")
        created, updated = f.get("created", ""), f.get("updated", "")
        if created and not valid_date(created):
            out.append(f"{path}:{fm.lines['created']}: `created:` {created!r} is not a date YYYY-MM-DD")
        if updated and not valid_time(updated):
            out.append(f"{path}:{fm.lines['updated']}: `updated:` {updated!r} is not a time {TIME_FORM}")
        elif updated and valid_date(created) and updated[:10] < created:
            out.append(f"{path}:{fm.lines['updated']}: `updated:` {updated} is before `created:` {created}")
        if "status" in f and f["status"] not in self.statuses:
            out.append(f"{path}:{fm.lines['status']}: `status:` {f['status']!r} is not one of "
                       f"{', '.join(self.statuses)}")
        if self.types and f.get("type") and f["type"] not in self.types:
            out.append(f"{path}:{fm.lines['type']}: `type:` {f['type']!r} is not one of {', '.join(self.types)}")
        if "tags" in f:
            out += self.tags(path, fm)
        if "archived" in f:
            out.append(f"{path}:{fm.lines['archived']}: `archived:` outside the archive; the stamp is written when a "
                       f"file moves into it")
        if self.markers:
            out += self.marker_forms(path, text)
        return out

    def tags(self, path, fm):
        value, where = fm.raw["tags"].strip(), f"{path}:{fm.lines['tags']}"
        if not (value.startswith("[") and value.endswith("]")):
            return [f"{where}: `tags:` is not a list: [a, b]"]
        items = [t.strip().strip("'\"") for t in value[1:-1].split(",")] if value[1:-1].strip() else []
        out = []
        if any(not t for t in items):
            out.append(f"{where}: `tags:` holds an empty tag")
        repeated = sorted({t for t in items if t and items.count(t) > 1})
        if repeated:
            out.append(f"{where}: `tags:` repeats {', '.join(repeated)}")
        return out

    def marker_forms(self, path, text):
        """The change-of-plan marker used for anything else (a superseded note, a warning) reads as a change of plan
        to every reader who scans for it; the other markers carry no word to check them by."""
        out = []
        for n, line in at.prose_lines(text):
            line = at.mask_code(line)
            if PLAN_MARK in line and "change of plan" not in line.lower():
                out.append(f"{path}:{n}: the change-of-plan marker stands only beside the words CHANGE OF PLAN, "
                           f"on the heading it marks or in a legend")
        return out

    def archived(self, path, text):
        fm = at.frontmatter(text)
        stamp = fm.fields.get("archived") if fm else None
        if stamp is None:
            return [f"{path}: no `archived:` stamp in its frontmatter; the commit that moves a file into the archive "
                    f"writes one, {TIME_FORM}"]
        if not valid_time(stamp):
            return [f"{path}:{fm.lines['archived']}: `archived:` {stamp!r} is not a time {TIME_FORM}"]
        return []

    def changed(self, path, new, old):
        """The findings on a document against its earlier text."""
        out = self.document(path, new)
        nf, of = at.frontmatter(new), at.frontmatter(old)
        if nf is None or of is None:
            return out
        nc, oc = nf.fields.get("created"), of.fields.get("created")
        if oc is not None and nc != oc:
            out.append(f"{path}: `created:` moved from {oc} to {nc}; it is written once and never changes, not on a "
                       f"move or a rewrite")
        nu, ou = nf.fields.get("updated"), of.fields.get("updated")
        if without_updated(new) != without_updated(old) and nu == ou:
            out.append(f"{path}: the document changed and `updated:` still reads {ou}; set it in the same commit: "
                       f"date -u +%Y-%m-%dT%H:%M:%S+00:00")
        elif valid_time(nu) and valid_time(ou) and nu < ou:
            out.append(f"{path}: `updated:` moved backwards, from {ou} to {nu}")
        return out


def without_updated(text):
    """The text with the frontmatter's `updated:` line taken out: what a change to the document is measured on."""
    lines = text.splitlines()
    end = at.frontmatter_end(lines)
    if end is None:
        return text
    return "\n".join(line for i, line in enumerate(lines) if not (0 < i < end and line.startswith("updated:")))


def check_one(rules, scope, path, new, old):
    kind = scope.kind(path)
    if kind is None:
        return []
    if kind == "archived":
        return rules.archived(path, new)
    return rules.document(path, new) if old is None else rules.changed(path, new, old)


def show(root, spec):
    p = at.git(root, "show", spec)
    return p.stdout if p.returncode == 0 else None


def changes(root, old_rev, new_rev):
    """[(path, old path or None)] of the Markdown files added, modified, renamed or copied: staged against HEAD
    when new_rev is None, else between the two revisions."""
    args = ["diff", "--name-status", "-M", "-z", "--diff-filter=ACMR"]
    args += ["--cached"] if new_rev is None else [old_rev, new_rev]
    p = at.git(root, *args)
    if p.returncode != 0:
        raise at.Usage(f"git {' '.join(args)}: {p.stderr.strip()}")
    parts = [x for x in p.stdout.split("\0") if x != ""]
    out, i = [], 0
    while i < len(parts):
        letter = parts[i][:1]
        if letter in "RC":
            old, new = parts[i + 1], parts[i + 2]
            out.append((new, old if letter == "R" else None))
            i += 3
        else:
            path = parts[i + 1]
            out.append((path, None if letter == "A" else path))
            i += 2
    return out


def run(root, mode, rules, scope_args, rev_range=None):
    """Return (findings, how many documents were read, what was read)."""
    files, subs = at.tracked(root)
    scope = Scope(subs, *scope_args)
    findings, count = [], 0
    if mode == "all":
        for path in files:
            if scope.kind(path) is None:
                continue
            try:
                text = (root / path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                findings.append(f"{path}: cannot be read as UTF-8 text: {e}")
                continue
            count += 1
            findings += check_one(rules, scope, path, text, None)
        return findings, count, "every tracked document"
    if mode == "staged":
        has_head = at.git(root, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
        base, new_spec = ("HEAD" if has_head else None), (lambda p: f":{p}")
        pairs = changes(root, None, None) if has_head else [(p, None) for p in staged_new(root)]
        what = "the staged documents"
    else:
        a, sep, b = rev_range.partition("..")
        if not sep or not a:
            raise at.Usage(f"--range {rev_range}: A..B, two revisions")
        b = b or "HEAD"
        base, new_spec = a, (lambda p, b=b: f"{b}:{p}")
        pairs = changes(root, a, b)
        what = f"the documents changed in {a}..{b}"
    for path, old_path in pairs:
        if scope.kind(path) is None:
            continue
        new = show(root, new_spec(path))
        if new is None:
            continue
        old = show(root, f"{base}:{old_path}") if base and old_path else None
        count += 1
        findings += check_one(rules, scope, path, new, old)
    return findings, count, what


def staged_new(root):
    """Before the first commit, every file in the index is new."""
    return [x for x in at.git(root, "ls-files", "-z").stdout.split("\0") if x]


def parser():
    p = argparse.ArgumentParser(description="Hold the Markdown documents to their frontmatter and its two dates.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="every tracked document, its block only")
    mode.add_argument("--range", metavar="A..B", help="the documents changed between two revisions")
    p.add_argument("--archive", metavar="DIR", action="append",
                   help="the archive folder, from the root; repeatable (default: archive/ at each repository's top)")
    p.add_argument("--exempt", metavar="PATH", action="append", default=[],
                   help="a folder or a glob, from the root, not checked; repeatable")
    p.add_argument("--statuses", metavar="A,B", help=f"the lifecycle values (default: {','.join(STATUSES)})")
    p.add_argument("--types", metavar="A,B", help="the document types the project fixed (default: any)")
    p.add_argument("--no-markers", action="store_true", help="do not check the change-of-plan marker's use")
    p.add_argument("--root", metavar="DIR", help="the repository (default: the one holding the current folder)")
    return p


def main(argv=None):
    args = parser().parse_args(argv)

    def listed(text):
        return [x.strip() for x in text.split(",") if x.strip()] if text else None

    rules = Rules(listed(args.statuses) or STATUSES, listed(args.types), not args.no_markers)
    mode = "all" if args.all else "range" if args.range else "staged"
    try:
        root = at.top(args.root or ".")
        findings, count, what = run(root, mode, rules, (args.archive, args.exempt), args.range)
    except at.Usage as e:
        print(e, file=sys.stderr)
        return 2
    for f in findings:
        print(f"error: {f}")
    print(f"check-frontmatter: {count} document(s) read, {what}")
    print(f"{len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
