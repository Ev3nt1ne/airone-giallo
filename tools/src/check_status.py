#!/usr/bin/env python3
"""Check a project's status file and its closed file, and print the next free ID in each family.

    check-status STATUS [CLOSED] [--graph GRAPH]              installed, by uv tool install <airone-giallo>/tools
    python3 check_status.py STATUS [CLOSED] [--graph GRAPH]   from the clone, without installing

STATUS holds the open items and the `status-meta` block that declares the families; CLOSED holds the closed
items. With --graph, every citation of a graph node is checked against the specification graph's file, and
the graph file is checked for citations of items. Exits 1 on any error, 2 when a file cannot be read. Standard
library only, so it runs wherever Python 3.10 does.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

KINDS = ("decision", "question", "defect", "enhancement", "chore")
# A section heading of the status file, lower-cased and stripped of everything but letters and spaces, gives its status.
SECTIONS = {
    "awaiting your decision": "awaiting",
    "accepted not yet built": "accepted",
    "deferred with a trigger": "deferred",
}
OUTCOMES = ("done", "superseded", "withdrawn")
OPEN_COLUMNS = ("id", "kind", "title", "reason", "owner", "trigger or question", "opened")
CLOSED_COLUMNS = ("id", "kind", "title", "outcome", "chosen", "reopen if", "reason", "closed")
NEEDS_TRIGGER = ("awaiting", "deferred")

CODE = r"[A-Z][A-Z0-9]{1,4}"
FAMILY_RE = re.compile(rf"^{CODE}(?:-{CODE})?$")
ID_SHAPE_RE = re.compile(rf"^({CODE}(?:-{CODE})?)-([0-9]+)$")
COUNTER_RE = re.compile(r"^[0-9]{3,}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
LINK_RE = re.compile(r"\[[^\]]+\]\([^)\s]+\)")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*([^`\s]*)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
EMPTY = ("", "-", "—")


@dataclass
class Row:
    path: str
    line: int
    section: str  # the status for an open row, "closed" for a closed one
    cells: dict

    @property
    def id(self):
        return self.cells["id"].strip("` ")


@dataclass
class Doc:
    path: str
    rows: list = field(default_factory=list)
    mentions: list = field(default_factory=list)  # (line, code span text)
    meta: list = field(default_factory=list)  # (line, text) of each status-meta block
    own_ids: set = field(default_factory=set)  # (line, ID) of each item row's own ID cell, not a citation


def normalise(text):
    return " ".join(re.sub(r"[^a-z ]", " ", text.lower()).split())


def split_row(line):
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") and not s.endswith("\\|") else s
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def is_separator(cells):
    return all(re.fullmatch(r":?-+:?", c) for c in cells)


def read_doc(path, closed, errors):
    """Parse one file: its item tables, its code spans and its meta blocks; structural errors go to `errors`."""
    doc = Doc(str(path))
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    fence, meta_start, meta_lines = None, None, []
    heading = None
    expected = CLOSED_COLUMNS if closed else OPEN_COLUMNS
    i = 0
    while i < len(lines):
        line, n = lines[i], i + 1
        m = FENCE_RE.match(line)
        # A fence closes on a line of its own character only, at least as long as the one that opened it.
        closes = fence is not None and set(line.strip()) == {fence[0]} and len(line.strip()) >= len(fence)
        if (fence is None and m) or closes:
            if fence is None:
                fence = m.group(1)
                if m.group(2) == "status-meta":
                    meta_start, meta_lines = n, []
            else:
                if meta_start is not None:
                    doc.meta.append((meta_start, meta_lines))
                fence, meta_start = None, None
            i += 1
            continue
        if fence is not None:
            if meta_start is not None:
                meta_lines.append((n, line))
            i += 1
            continue
        if line.lstrip().startswith("|"):
            table = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                table.append((i + 1, split_row(lines[i])))
                add_mentions(doc, i + 1, lines[i])
                i += 1
            read_table(doc, table, heading, closed, expected, errors)
            continue
        add_mentions(doc, n, line)
        h = HEADING_RE.match(line)
        if h:
            heading = h.group(1).strip()
        i += 1
    if fence is not None:
        errors.append(f"{path}: a code fence is never closed")
    return doc


def add_mentions(doc, n, line):
    for span in CODE_SPAN_RE.findall(line):
        doc.mentions.append((n, span.strip()))


def read_table(doc, table, heading, closed, expected, errors):
    (n, header) = table[0]
    if normalise(header[0]) != "id":
        return  # not an item table: a table of families, of columns, of anything else
    where = f"{doc.path}:{n}"
    body = table[1:]
    if body and is_separator(body[0][1]):
        body = body[1:]
    for line, cells in body:
        doc.own_ids.add((line, cells[0].strip("` ")))
    if tuple(normalise(c) for c in header) != expected:
        errors.append(f"{where}: an item table's columns must be: {' | '.join(expected)}")
        return
    if closed:
        section = "closed"
    else:
        section = SECTIONS.get(normalise(heading or ""))
        if section is None:
            errors.append(f"{where}: an item table under '{heading}', which is not a status section "
                          f"({', '.join(SECTIONS)}); a closed item belongs in the closed file")
            return
    for line, cells in body:
        if len(cells) != len(expected):
            errors.append(f"{doc.path}:{line}: {len(cells)} cells where the table has {len(expected)}")
            continue
        doc.rows.append(Row(doc.path, line, section, dict(zip(expected, cells))))


def read_families(doc, errors):
    if not doc.meta:
        errors.append(f"{doc.path}: no ```status-meta block declaring the families")
        return {}
    if len(doc.meta) > 1:
        errors.append(f"{doc.path}:{doc.meta[1][0]}: a second status-meta block; there is one")
    families, in_families = {}, False
    for n, line in doc.meta[0][1]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            key = line.split(":", 1)[0].strip()
            in_families = key == "families"
            if not in_families:
                errors.append(f"{doc.path}:{n}: unknown key '{key}' in status-meta; it holds families:")
            continue
        if not in_families:
            continue
        code, _, meaning = line.strip().partition(":")
        code = code.strip()
        if not FAMILY_RE.match(code):
            errors.append(f"{doc.path}:{n}: '{code}' is not a family code: 2 to 5 capitals or digits, starting "
                          f"with a capital, or two such codes joined by a hyphen")
        elif code in families:
            errors.append(f"{doc.path}:{n}: family {code} declared twice")
        else:
            families[code] = meaning.strip()
    if not families and not any("family code" in e for e in errors):
        errors.append(f"{doc.path}:{doc.meta[0][0]}: the status-meta block declares no family")
    return families


def read_graph(path):
    """The graph's ID prefixes and node IDs, and the lines outside its meta, read from the graph file's text."""
    prefixes, ids, body = set(), set(), []
    section = None
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        top = re.match(r"^([A-Za-z_]+):", line)
        if top:
            section = top.group(1)
        if section == "meta":
            m = re.match(r"^\s+(?:prefixes|slug_prefixes):\s*\[(.*)\]", line)
            if m:
                prefixes.update(p.strip().strip("'\"") for p in m.group(1).split(",") if p.strip())
            continue
        body.append((n, line))
        if section == "nodes":
            for m in re.finditer(r"(?:^|[{,\s-])id:\s*['\"]?([A-Za-z0-9][A-Za-z0-9_.-]*)", line):
                ids.add(m.group(1))
    return prefixes, ids, body


def parse_id(text, families):
    """(family, counter) when `text` is an ID of a declared family, else None."""
    m = ID_SHAPE_RE.match(text)
    if m and m.group(1) in families:
        return m.group(1), m.group(2)
    return None


def has_text(cell):
    return cell.strip() not in EMPTY


def check_row(row, families, errors):
    where = f"{row.path}:{row.line}: {row.id or '(no ID)'}"
    m = ID_SHAPE_RE.match(row.id)
    if not m:
        errors.append(f"{where}: not an ID of the form FAMILY-nnn")
        return False
    if m.group(1) not in families:
        errors.append(f"{where}: family {m.group(1)} is not declared in the status-meta block")
        return False
    if not COUNTER_RE.match(m.group(2)) or int(m.group(2)) == 0:
        errors.append(f"{where}: the counter is three digits or more, from 001")
        return False
    c = row.cells
    if c["kind"].strip() not in KINDS:
        errors.append(f"{where}: kind '{c['kind'].strip()}' is not one of {', '.join(KINDS)}")
    if not has_text(c["title"]):
        errors.append(f"{where}: no title")
    if not LINK_RE.search(c["reason"]):
        errors.append(f"{where}: the reason column holds no link to where the reason lives")
    if row.section == "closed":
        if c["outcome"].strip() not in OUTCOMES:
            errors.append(f"{where}: outcome '{c['outcome'].strip()}' is not one of {', '.join(OUTCOMES)}")
        if not has_text(c["chosen"]):
            errors.append(f"{where}: a closed item says what was chosen")
        check_date(where, "closed", c["closed"], errors)
    else:
        if not has_text(c["owner"]):
            errors.append(f"{where}: an open item has an owner")
        if row.section in NEEDS_TRIGGER and not has_text(c["trigger or question"]):
            what = "a deferred item has a trigger" if row.section == "deferred" else \
                "an item awaiting a decision states the question"
            errors.append(f"{where}: {what}")
        check_date(where, "opened", c["opened"], errors)
    return True


def check_date(where, column, cell, errors):
    text = cell.strip()
    try:
        ok = bool(DATE_RE.match(text)) and date.fromisoformat(text) is not None
    except ValueError:
        ok = False
    if not ok:
        errors.append(f"{where}: {column} '{text}' is not a date YYYY-MM-DD")


def check(status_path, closed_path=None, graph_path=None):
    """Return (errors, next IDs by family, notes)."""
    errors, notes = [], []
    status = read_doc(status_path, False, errors)
    closed = read_doc(closed_path, True, errors) if closed_path else Doc("")
    families = read_families(status, errors)
    if not closed_path:
        notes.append("no closed file given: the next IDs count the status file only")

    seen = {}
    for row in status.rows + closed.rows:
        if not check_row(row, families, errors):
            continue
        if row.id in seen:
            first = seen[row.id]
            if (first.section == "closed") != (row.section == "closed"):
                errors.append(f"{first.path}:{first.line}: {row.id} is closed ({row.path}:{row.line}) and still "
                              f"in the status file; a closed item lives in the closed file only")
            else:
                errors.append(f"{row.path}:{row.line}: {row.id} is used again (first at {first.path}:"
                              f"{first.line}); an ID is never reused")
        else:
            seen[row.id] = row

    graph_prefixes, graph_ids, graph_body = read_graph(graph_path) if graph_path else (set(), set(), [])
    shared = [code for code in families if code.split("-")[0] in graph_prefixes]
    for code in shared:
        errors.append(f"{status.path}: family {code} is also a family of the graph; a "
                      f"citation of either would be ambiguous")

    highest = {code: 0 for code in families}
    for row in seen.values():
        family, counter = parse_id(row.id, families)
        highest[family] = max(highest[family], int(counter))
    for doc in (status, closed):
        for n, span in doc.mentions:
            if (n, span) in doc.own_ids:
                continue
            parsed = parse_id(span, families)
            if parsed:
                family, counter = parsed
                if not COUNTER_RE.match(counter):
                    errors.append(f"{doc.path}:{n}: `{span}` is not a well-formed ID: the counter is three digits")
                    continue
                highest[family] = max(highest[family], int(counter))
                if span not in seen:
                    errors.append(f"{doc.path}:{n}: `{span}` cites an item that is in neither file")
            elif graph_path and span.split("-")[0] in graph_prefixes and "-" in span:
                if span not in graph_ids:
                    errors.append(f"{doc.path}:{n}: `{span}` cites a graph node that is not in {graph_path}")

    for row in closed.rows:
        if row.cells.get("outcome", "").strip() == "superseded":
            successors = [s for s in CODE_SPAN_RE.findall(row.cells["chosen"])
                          if parse_id(s, families) and s != row.id]
            if not successors:
                errors.append(f"{row.path}:{row.line}: {row.id} is superseded and names no item that "
                              f"supersedes it")

    for n, line in graph_body:
        for code in (c for c in families if c not in shared):
            for m in re.finditer(rf"\b{re.escape(code)}-[0-9]+\b", line):
                errors.append(f"{graph_path}:{n}: the graph cites the item {m.group(0)}; an item may cite a "
                              f"node, a node never cites an item")

    next_ids = {code: f"{code}-{highest[code] + 1:03d}" for code in families}
    return errors, next_ids, (status, closed, notes)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check a status file and its closed file; print the next free IDs.")
    parser.add_argument("status", help="the status file: open items and the status-meta block")
    parser.add_argument("closed", nargs="?", help="the closed file")
    parser.add_argument("--graph", metavar="GRAPH", help="the specification graph's file (graph.yml)")
    args = parser.parse_args(argv)
    try:
        errors, next_ids, (status, closed, notes) = check(args.status, args.closed, args.graph)
    except OSError as e:
        print(f"cannot read {e.filename}: {e.strerror}", file=sys.stderr)
        return 2
    for e in errors:
        print(f"error: {e}")
    summary = f"{status.path}: {len(status.rows)} open item(s)"
    if args.closed:
        summary += f"; {closed.path}: {len(closed.rows)} closed item(s)"
    print(summary)
    for note in notes:
        print(f"note: {note}")
    if next_ids:
        print("next free ID per family:")
        for code, nid in next_ids.items():
            print(f"  {nid}")
    print(f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
