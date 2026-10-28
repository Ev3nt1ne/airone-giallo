#!/usr/bin/env python3
"""List the claims a change makes, so each can be checked against its source; settle the mechanical ones.

    claims                          the staged changes
    claims --range A..B             the lines a range of commits added
    claims --message FILE           a commit message, or any text, read as prose
    python3 list_claims.py ...      from the kit, without installing

The hard part of checking a change claim by claim is listing the claims: re-reading one's own text finds coherence,
not truth. This reads the added lines and sorts what it finds:

  settled here    commit hashes (`git cat-file`); graph identifiers, against the graph file (the families from its
                  `meta`, every node by its id); status identifiers, against the status file and the closed file (the
                  families from the `status-meta` block); section references (§4, §4.2), that a heading of that
                  number exists in the document the line names, or in a --doc
  listed for you  numbers, quotations, and the completeness words (all, every, each, none, only, never, always),
                  each with its line

In prose (Markdown, text, the message) every added line is read; in code and configuration only comment lines, since
a number in code is the tests' business and a number in a comment is a claim. A helper, not a gate: an empty list
means nothing matched a pattern, not that the change is true; numbers written as words, docstrings and claims in
none of these shapes are the reader's. Relative links are check-links' job.

Known false positive: a run of 7 to 40 hexadecimal digits with a letter and a digit in it is read as a commit hash, so
a hash that is not a commit (a checksum, a content hash) reports as unknown. Read each failure before believing it.

Exit 1 when a mechanical check failed (an unknown hash or identifier), 2 on a bad argument; else 0, whatever was
listed. Standard library only: the graph file and the status file are read as text.
"""

import argparse
import posixpath
import re
import sys
from pathlib import Path

import airone_tree as at

SHA_RE = re.compile(r"(?<![0-9A-Za-z_])[0-9a-f]{7,40}(?![0-9A-Za-z_])")
SECTION_RE = re.compile(r"§\s?([0-9]+(?:\.[0-9]+)*)")
DATE_RE = re.compile(r"\b[0-9]{4}-[0-9]{2}-[0-9]{2}(?:T[0-9:]+(?:[+-][0-9:]+|Z)?)?\b")
NUMBER_RE = re.compile(r"(?<![\w.])[-−+]?[0-9][0-9 ,]*(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?%?")
QUOTE_RE = re.compile(r"[“\"]([^”\"]{6,}?)[”\"]")
COMPLETE_RE = re.compile(r"\b(all|every|each|none|only|never|always)\b", re.I)
DOC_RE = re.compile(r"\]\(([^)\s#]+\.md)(?:#[^)]*)?\)|`([^`\s]+\.md)`")
COMMENT_PREFIXES = ("#", "//", "--", "/*", "*", ";", "<!--", "%", "REM ", "rem ")
PROSE_SUFFIXES = (".md", ".markdown", ".txt", ".rst")
STATUS_CODE = r"[A-Z][A-Z0-9]{1,4}(?:-[A-Z][A-Z0-9]{1,4})?"


# ---------------------------------------------------------------- the sources

def graph_families(path):
    """(numbered families, slug families, (lo, hi) digits, node ids) from the graph file's text, read without a YAML
    parser: the `meta` block's prefixes, slug_prefixes and id_digits, and every `id:` under `nodes`."""
    prefixes, slugs, digits, ids = [], [], (2, 3), set()
    section = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        top = re.match(r"^([A-Za-z_]+):", line)
        if top:
            section = top.group(1)
        if section == "meta":
            m = re.match(r"^\s+(prefixes|slug_prefixes|id_digits):\s*\[(.*)\]", line)
            if m:
                values = [v.strip().strip("'\"") for v in m.group(2).split(",") if v.strip()]
                if m.group(1) == "prefixes":
                    prefixes = values
                elif m.group(1) == "slug_prefixes":
                    slugs = values
                else:
                    digits = tuple(int(v) for v in values[:2])
        elif section == "nodes":
            for m in re.finditer(r"(?:^|[{,\s-])id:\s*['\"]?([A-Za-z0-9][A-Za-z0-9_.-]*)", line):
                ids.add(m.group(1))
    numbered = [p for p in prefixes if p not in slugs]
    return numbered, [s for s in slugs if s in prefixes] or slugs, digits, ids


def status_families(path):
    """The family codes the `status-meta` block declares."""
    families, inside, in_families = [], False, False
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if re.match(r"^\s*(`{3,}|~{3,})\s*status-meta\s*$", line):
            inside = True
            continue
        if inside and re.match(r"^\s*(`{3,}|~{3,})\s*$", line):
            break
        if not inside or not line.strip():
            continue
        if not line[0].isspace():
            in_families = line.split(":", 1)[0].strip() == "families"
            continue
        if in_families:
            code = line.strip().split(":", 1)[0].strip()
            if re.fullmatch(STATUS_CODE, code):
                families.append(code)
    return families


def status_items(paths):
    """Every item ID that heads a table row of the status file or the closed file."""
    ids = set()
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*\|\s*`?([A-Z][A-Z0-9-]*-[0-9]{3,})`?\s*\|", line)
            if m:
                ids.add(m.group(1))
    return ids


class Context:
    """What the claims are resolved against; each part is optional, and a part that is missing is said so."""

    def __init__(self, root, graph=None, status=None, closed=None, docs=()):
        self.root = root
        self.notes = []
        self.graph_re, self.graph_ids = None, set()
        if graph and Path(graph).is_file():
            numbered, slugs, (lo, hi), self.graph_ids = graph_families(graph)
            parts = []
            if numbered:
                parts.append(r"(?:" + "|".join(map(re.escape, numbered)) + r")-[0-9]{" + f"{lo},{hi}" + r"}")
            if slugs:
                parts.append(r"(?:" + "|".join(map(re.escape, slugs)) + r")-[a-z0-9]+(?:-[a-z0-9]+)*")
            if parts:
                self.graph_re = re.compile(r"(?<![\w-])(?:" + "|".join(parts) + r")(?![\w-])")
        else:
            self.notes.append(f"graph identifiers not resolved: no graph file at {graph}" if graph else
                              "graph identifiers not resolved: no graph file given or found")
        self.status_re, self.status_ids = None, set()
        if status and Path(status).is_file():
            families = status_families(status)
            items = [status] + ([closed] if closed and Path(closed).is_file() else [])
            self.status_ids = status_items(items)
            if families:
                self.status_re = re.compile(r"(?<![\w-])(?:" + "|".join(map(re.escape, families)) +
                                            r")-[0-9]{3,}(?![\w-])")
            else:
                self.notes.append(f"status identifiers not resolved: {status} declares no family")
        else:
            self.notes.append(f"status identifiers not resolved: no status file at {status}" if status else
                              "status identifiers not resolved: no status file given or found")
        self.docs = list(docs)
        self._sections = {}

    def sha(self, token):
        p = at.git(self.root, "cat-file", "-t", token)
        return p.returncode == 0 and p.stdout.strip() == "commit"

    def sections(self, doc):
        """The numbers that open a heading of the document, or None when it cannot be read."""
        if doc not in self._sections:
            try:
                text = (self.root / doc).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                self._sections[doc] = None
                return None
            numbers = set()
            for _, heading in at.headings(text):
                m = re.match(r"^§?\s*([0-9]+(?:\.[0-9]+)*)\.?(?:\s|$)", heading)
                if m:
                    numbers.add(m.group(1))
            self._sections[doc] = numbers
        return self._sections[doc]


# ---------------------------------------------------------------- reading the change

def added_lines(diff):
    """(path, line number, text) of every line a unified diff without context (-U0) adds."""
    path, n = None, 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else None
        elif raw.startswith("@@"):
            m = re.search(r"\+([0-9]+)", raw)
            n = int(m.group(1)) if m else 0
        elif raw.startswith("+") and path:
            yield path, n, raw[1:]
            n += 1


def is_scanned(path, text):
    if path == "<message>" or path.lower().endswith(PROSE_SUFFIXES):
        return True
    return text.lstrip().startswith(COMMENT_PREFIXES)


def claims_in(path, text, ctx):
    """(kind, excerpt, verdict) for each claim of one line; the verdict is 'ok', 'FAIL', 'check' or a note."""
    masked = text
    for m in SHA_RE.finditer(text):
        token = m.group(0)
        if re.search(r"[a-f]", token) and re.search(r"[0-9]", token):
            yield "hash", token, "ok" if ctx.sha(token) else "FAIL"
            masked = masked.replace(token, " ")
    for rx, ids, kind in ((ctx.graph_re, ctx.graph_ids, "graph id"), (ctx.status_re, ctx.status_ids, "status id")):
        if rx is None:
            continue
        for m in rx.finditer(masked):
            yield kind, m.group(0), "ok" if m.group(0) in ids else "FAIL"
        masked = rx.sub(" ", masked)
    named = [a or b for a, b in DOC_RE.findall(text)]
    for m in SECTION_RE.finditer(masked):
        number = m.group(1)
        docs = [resolve_doc(ctx, path, d) for d in named] if named else list(ctx.docs)
        if not docs and path.lower().endswith((".md", ".markdown")):
            docs = [path]
        found = [d for d in docs if d and (ctx.sections(d) or set()) >= {number}]
        if found:
            yield "section", f"§{number}", f"check (a heading in {found[0]}; not that it says what is claimed)"
        elif docs:
            yield "section", f"§{number}", f"check: NO heading {number} in {', '.join(d or '?' for d in docs)}"
        else:
            yield "section", f"§{number}", "check (which document?)"
    masked = SECTION_RE.sub(" ", masked)
    masked = DATE_RE.sub(" ", masked)
    for m in QUOTE_RE.finditer(text):
        yield "quote", m.group(1)[:70], "check"
    for m in NUMBER_RE.finditer(masked):
        token = m.group(0).strip(" ,")
        if token:
            yield "number", token, "check"
    for m in COMPLETE_RE.finditer(text):
        yield "completeness", m.group(0), "check"


def resolve_doc(ctx, path, doc):
    """A document a line names, from the line's own file, else from the top."""
    if path not in ("<message>",):
        here = at.join(posixpath.dirname(path), doc)
        if here and (ctx.root / here).is_file():
            return here
    return at.normal(doc.lstrip("/"))


def report(lines, ctx, out=None):
    """Print one entry per line that makes a claim; return the count of mechanical failures."""
    out = out or sys.stdout
    failed, total, kinds = 0, 0, {}
    for path, n, text in lines:
        if not is_scanned(path, text):
            continue
        found = list(claims_in(path, text, ctx))
        if not found:
            continue
        total += len(found)
        bad = [f"{k} {e}" for k, e, v in found if v == "FAIL"]
        todo = [f"{k} {e}" + ("" if v == "check" else f" [{v.removeprefix('check').strip(' :()')}]")
                for k, e, v in found if v not in ("ok", "FAIL")]
        good = [f"{k} {e}" for k, e, v in found if v == "ok"]
        failed += len(bad)
        for k, _, _ in found:
            kinds[k] = kinds.get(k, 0) + 1
        print(f"{'FAIL' if bad else 'check' if todo else 'ok'} {path}:{n}", file=out)
        if bad:
            print(f"    unknown: {', '.join(bad)}", file=out)
        if good:
            print(f"    resolved: {', '.join(good)}", file=out)
        if todo:
            print(f"    to check: {'; '.join(todo)}", file=out)
        print(f"    | {text.strip()[:160]}", file=out)
    for note in ctx.notes:
        print(f"note: {note}", file=out)
    listed = ", ".join(f"{k} {v}" for k, v in sorted(kinds.items()))
    print(f"\nclaims: {total} listed{f' ({listed})' if listed else ''}; {failed} failed a mechanical check", file=out)
    return failed


def parser():
    p = argparse.ArgumentParser(description="List the claims a change makes; settle the mechanical ones.")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--range", metavar="A..B", help="the lines a range of commits added")
    src.add_argument("--message", metavar="FILE", help="a commit message or any text, read as prose")
    p.add_argument("--graph", metavar="FILE", help="the graph file (default: graph.yml, when present)")
    p.add_argument("--status", metavar="FILE", help="the status file (default: ai-docs/status.md, when present)")
    p.add_argument("--closed", metavar="FILE", help="the closed file (default: closed.md beside the status file)")
    p.add_argument("--doc", metavar="FILE", action="append", default=[],
                   help="a document whose headings a bare § reference is checked against; repeatable")
    p.add_argument("--root", metavar="DIR", help="the repository (default: the one holding the current folder)")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        root = at.top(args.root or ".")
        graph = args.graph or ("graph.yml" if (root / "graph.yml").is_file() else None)
        status = args.status or ("ai-docs/status.md" if (root / "ai-docs/status.md").is_file() else None)
        closed = args.closed or (str(Path(status).parent / "closed.md") if status else None)

        def here(p):
            return str(root / p) if p and not Path(p).is_absolute() else p

        for opt, value in (("--graph", args.graph), ("--status", args.status), ("--closed", args.closed)):
            if value and not Path(here(value)).is_file():
                raise at.Usage(f"{opt} {value}: no such file")
        ctx = Context(root, here(graph), here(status), here(closed), [at.normal(d) for d in args.doc])
        if args.message:
            try:
                text = Path(args.message).read_text(encoding="utf-8")
            except OSError as e:
                raise at.Usage(f"cannot read {args.message}: {e.strerror}") from e
            lines = [("<message>", i, t) for i, t in enumerate(text.splitlines(), 1)]
        else:
            cmd = ["diff", "-U0", "--no-color", "--no-ext-diff"]
            cmd += [args.range] if args.range else ["--cached"]
            p = at.git(root, *cmd)
            if p.returncode != 0:
                raise at.Usage(f"git {' '.join(cmd)}: {p.stderr.strip()}")
            lines = list(added_lines(p.stdout))
    except at.Usage as e:
        print(e, file=sys.stderr)
        return 2
    return 1 if report(lines, ctx) else 0


if __name__ == "__main__":
    sys.exit(main())
