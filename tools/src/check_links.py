#!/usr/bin/env python3
"""Resolve every relative link in the tracked Markdown files, check each anchor against the target's headings, and
hold the documents to the kit's ladder and its archive.

    check-links                              dead links and anchors, the archive's rules
    check-links --cut RUNG                   and the ladder, in one repository
    check-links --public DIR [--cut RUNG]    and the ladder, DIR being the public repository's folder
    python3 check_links.py ...               from the kit, without installing

The tracked tree is what `git ls-files` lists at the repository's top, with the files of every nested repository (a
submodule, as the two-repository form nests the public one) under its folder. A link resolves when its target is a
tracked file, or a folder holding one: a file present here but not tracked is a dead link in every other clone. A
link starting with `/` is read from the top of the repository holding the file. An anchor is checked when the target
is a Markdown file: it must be a heading's anchor, as forges make them, or an HTML id.

The ladder (the `doc-discipline` skill): 1 docs/, 2 graph.yml, 3 plan/, 4 ai-docs/, 5 the agent layer (AGENTS.md,
CLAUDE.md, RATIONALE.md, .claude/). With --cut, the rungs up to RUNG are public and the rest private; with --public
DIR, everything in DIR is public, everything outside it private, and the rungs up to the cut (plan by default) sit
inside DIR. A link, or a path written in backticks, from a public file to a private one is an error. A citation of a
higher rung from a lower one is a warning: the ladder lets a rung cite only those at or below it. --rung
NAME=PATH[,PATH...] places a rung elsewhere, each path from the workspace root.

The archive is not on the ladder: each repository has its own, archive/ at its top (or where --archive puts it), on
that repository's side, and it is frozen: a dead link or anchor inside it is information, counted and never an
error. A live document citing a file inside it is a warning: the archive is cited as a category at most, the folder
or its README or LOG.

Exit 1 on any error, 2 on a bad argument or a tree that cannot be read. Standard library only.
"""

import argparse
import fnmatch
import posixpath
import re
import sys
from dataclasses import dataclass, field

import airone_tree as at

RUNGS = ("docs", "graph", "plan", "ai-docs", "agent")
CUTS = ("none",) + RUNGS[:-1] + ("all",)
DEFAULT_PATHS = {"docs": ["docs/"], "graph": ["graph.yml"], "plan": ["plan/"], "ai-docs": ["ai-docs/"],
                 "agent": ["AGENTS.md", "CLAUDE.md", "RATIONALE.md", ".claude/"]}
# The archive's own files, which a live document may cite: the folder is the category.
ARCHIVE_OWN = ("", "README.md", "LOG.md")
# A path written in backticks: no spaces, at least one slash or a file extension, nothing that reads as code.
WRITTEN_RE = re.compile(r"^(?:\.{1,2}/)*[A-Za-z0-9_.@-][A-Za-z0-9_.@/-]*$")


@dataclass
class Ladder:
    """Where each rung sits and which side a path is on; built from the arguments."""
    cut: str
    public_dir: str            # '' in the one-repository form
    paths: dict                # rung -> [paths from the workspace root; a folder ends with /]

    def rung_of(self, path):
        best, rung = -1, None
        for name, places in self.paths.items():
            for p in places:
                folder = p.endswith("/")
                p = p.rstrip("/")
                if (path == p or (folder and path.startswith(p + "/"))) and len(p) > best:
                    best, rung = len(p), name
        return rung

    def number(self, rung):
        return RUNGS.index(rung) + 1

    def public(self, path):
        """True, False, or None when the path's side is not known (outside every rung, in the one-repository
        form)."""
        if self.public_dir:
            return at.under(path, self.public_dir)
        rung = self.rung_of(path)
        if rung is None:
            return None
        return self.number(rung) <= CUTS.index(self.cut)


def build_ladder(args):
    if args.cut is None and args.public is None:
        if args.rung:
            raise at.Usage("--rung places a rung of the ladder; give --cut or --public too")
        return None
    cut = args.cut or "plan"
    if cut not in CUTS:
        raise at.Usage(f"--cut {cut}: one of {', '.join(CUTS)}")
    public_dir = (args.public or "").strip("/")
    paths = {}
    for rung in RUNGS:
        inside = public_dir and rung != "agent" and RUNGS.index(rung) + 1 <= CUTS.index(cut)
        paths[rung] = [f"{public_dir}/{p}" if inside else p for p in DEFAULT_PATHS[rung]]
    for spec in args.rung or []:
        name, sep, value = spec.partition("=")
        if not sep or name not in RUNGS or not value.strip():
            raise at.Usage(f"--rung {spec}: NAME=PATH[,PATH...], NAME one of {', '.join(RUNGS)}")
        paths[name] = [p.strip().removeprefix("./") for p in value.split(",") if p.strip()]
    return Ladder(cut, public_dir, paths)


@dataclass
class Report:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    frozen: list = field(default_factory=list)      # dead links inside the archive: information
    files: int = 0
    checked: int = 0
    external: int = 0


class Tree:
    def __init__(self, root, ladder, archive_dirs):
        self.root, self.ladder = root, ladder
        self.files, self.subs = at.tracked(root)
        self.file_set = set(self.files)
        self.folders = at.folders_of(self.files)
        if archive_dirs is None:
            archive_dirs = [at.join(r, "archive") for r in [""] + self.subs]
        self.archives = [a.strip("/") for a in archive_dirs]
        self._text, self._anchors = {}, {}

    def exists(self, path):
        return path in self.file_set or path in self.folders

    def text(self, path):
        if path not in self._text:
            try:
                self._text[path] = (self.root / path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                self._text[path] = None
        return self._text[path]

    def anchors(self, path):
        if path not in self._anchors:
            text = self.text(path)
            self._anchors[path] = at.anchors(text) if text is not None else None
        return self._anchors[path]

    def archive_of(self, path):
        for a in self.archives:
            if at.under(path, a):
                return a
        return None

    def base(self, path):
        """The repository holding the file: where a link starting with / and a written path are read from."""
        return at.repo_of(path, self.subs)


def resolve(tree, src, path):
    """The tracked path a link's path names, from the file `src`; None when it climbs out of the workspace."""
    if path.startswith("/"):
        return at.join(tree.base(src), path.lstrip("/"))
    return at.join(posixpath.dirname(src), path)


def written_paths(tree, src, line):
    """(text, tracked path) of every path written in backticks on the line that names something tracked: read from
    the file's own folder when it opens with ./ or ../, else from the top of the repository holding the file, then
    from the workspace root."""
    out = []
    for span in at.code_spans(line):
        span = span.rstrip(".,;:")
        if not WRITTEN_RE.match(span) or ("/" not in span and "." not in span.strip(".")):
            continue
        candidates = []
        if span.startswith(("./", "../")):
            candidates.append(resolve(tree, src, span))
        else:
            candidates += [at.join(tree.base(src), span), at.normal(span)]
        for c in candidates:
            if c is not None and c != "" and tree.exists(c.rstrip("/")):
                out.append((span, c.rstrip("/")))
                break
    return out


def place(tree, path):
    rung = tree.ladder.rung_of(path) if tree.ladder else None
    return f"{path} (rung {tree.ladder.number(rung)}, {rung})" if rung else path


def judge(tree, report, src, n, shown, target, how):
    """The ladder's and the archive's rules on one citation from `src` to the tracked `target`."""
    where = f"{src}:{n}"
    src_archive = tree.archive_of(src)
    if src_archive is not None:
        return
    archive = tree.archive_of(target)
    if archive is not None:
        inner = target[len(archive):].strip("/")
        if inner not in ARCHIVE_OWN:
            report.warnings.append(f"{where}: {how} {shown}, inside the archive: a live document cites the archive "
                                   f"as a category at most")
    ladder = tree.ladder
    if ladder is None:
        return
    if ladder.public(src) and ladder.public(target) is False:
        report.errors.append(f"{where}: the ladder: a public file {how} {shown}, on the private side: "
                             f"{place(tree, target)}")
        return
    # The agent layer is the top rung, so nothing is above it; the archive is off the ladder, judged above.
    a, b = ladder.rung_of(src), ladder.rung_of(target)
    if a and b and ladder.number(b) > ladder.number(a):
        report.warnings.append(f"{where}: the ladder: rung {ladder.number(a)} ({a}) {how} rung {ladder.number(b)} "
                               f"({b}), above it: {shown}")


def check_file(tree, report, src):
    text = tree.text(src)
    if text is None:
        report.errors.append(f"{src}: cannot be read as UTF-8 text")
        return
    frozen = tree.archive_of(src) is not None
    for link in at.links(text):
        target = link.target
        if not target or at.is_external(target):
            report.external += 1
            continue
        path, anchor = at.split_target(target)
        report.checked += 1
        where = f"{src}:{link.line}"
        dead = None
        if not path:
            resolved = src
        else:
            resolved = resolve(tree, src, path)
            if resolved is None:
                dead = f"dead link {target}: it climbs out of the repository"
            elif not tree.exists(resolved.rstrip("/")):
                hint = " (present here, but not tracked: dead in every other clone)" \
                    if (tree.root / resolved).exists() else ""
                dead = f"dead link {target}{hint}"
            resolved = resolved.rstrip("/") if resolved is not None else None
        if dead is None and anchor and resolved in tree.file_set and resolved.lower().endswith((".md", ".markdown")):
            names = tree.anchors(resolved)
            if names is not None and anchor not in names and anchor.lower() not in names:
                dead = f"dead anchor {target}: no heading of {resolved} has the anchor #{anchor}"
        if dead:
            (report.frozen if frozen else report.errors).append(f"{where}: {dead}")
            continue
        if resolved != src:
            judge(tree, report, src, link.line, target, resolved, "links to")
    if not frozen:
        for n, line in at.prose_lines(text):
            for shown, path in written_paths(tree, src, line):
                if path != src:
                    judge(tree, report, src, n, f"`{shown}`", path, "names")


def exempted(path, patterns):
    """A source matching an --exempt pattern (a glob, or a folder it is under) is not scanned: its links are meant to
    resolve somewhere else, as a template's do once it is written into a project."""
    for pattern in patterns:
        p = pattern.strip("/")
        if fnmatch.fnmatch(path, pattern) or at.under(path, p):
            return True
    return False


def check(root, ladder=None, archive_dirs=None, exempt=()):
    tree = Tree(root, ladder, archive_dirs)
    report = Report()
    for src in tree.files:
        if src.lower().endswith((".md", ".markdown")) and not exempted(src, exempt):
            report.files += 1
            check_file(tree, report, src)
    return report, tree


def parser():
    p = argparse.ArgumentParser(description="Resolve the relative links of the tracked Markdown files; hold them to "
                                            "the ladder and the archive's rules.")
    p.add_argument("--cut", metavar="RUNG", help=f"the last public rung: {', '.join(CUTS)}")
    p.add_argument("--public", metavar="DIR", help="the public repository's folder, in the two-repository form")
    p.add_argument("--rung", metavar="NAME=PATH", action="append",
                   help="place a rung elsewhere: paths from the workspace root, comma-separated; repeatable")
    p.add_argument("--archive", metavar="DIR", action="append",
                   help="the archive folder, from the root; repeatable (default: archive/ at each repository's top)")
    p.add_argument("--root", metavar="DIR", help="the repository to check (default: the one holding the current "
                                                 "folder)")
    p.add_argument("--exempt", metavar="PATH", action="append", default=[],
                   help="a folder or a glob whose files are not scanned as sources (repeatable): templates whose links "
                        "resolve only once written elsewhere")
    p.add_argument("--quiet", action="store_true", help="print the errors and the totals, not the warnings or the "
                                                        "archive's dead links")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        ladder = build_ladder(args)
        root = at.top(args.root or ".")
        if ladder and ladder.public_dir and not (root / ladder.public_dir).is_dir():
            raise at.Usage(f"--public {ladder.public_dir}: no such folder in {root}")
        report, tree = check(root, ladder, args.archive, args.exempt)
    except at.Usage as e:
        print(e, file=sys.stderr)
        return 2
    for e in report.errors:
        print(f"error: {e}")
    if not args.quiet:
        for w in report.warnings:
            print(f"warning: {w}")
        for f in report.frozen:
            print(f"archived: {f}")
    form = ""
    if ladder:
        form = (f"; the ladder: public side {ladder.public_dir}/" if ladder.public_dir
                else f"; the ladder: cut after {ladder.cut}")
    print(f"check-links: {report.files} Markdown file(s), {report.checked} relative link(s), {report.external} "
          f"external skipped{form}")
    if report.frozen:
        print(f"{len(report.frozen)} dead link(s) inside the archive, information only: the archive is frozen, and "
              f"a link in it is rebuilt only with a row in its log")
    print(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
