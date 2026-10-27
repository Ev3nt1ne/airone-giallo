"""Preview, then apply, one batch of changes to the registry; and compare a past revision with the working file.

A batch is a YAML file with an optional `name`, an optional `whatif` and an `ops` list of operations on the
registry's one-line entries (one node or one edge per line, in YAML flow style):

    - {op: add_node, after: ID, line: "{id: ..., ...}"}        inserted after node ID's line
    - {op: set_statement, id: ID, statement: "..."}
    - {op: set_domain, id: ID, domain: "[Z2.PROD]"}           the node's domain, written as in the registry
    - {op: set_fields, id: ID, fields: "kind: goal, support: satisfier"}   inserted after the node's `id`
    - {op: drop_status, id: ID}                               the node becomes active
    - {op: set_status, id: ID, status: candidate}
    - {op: remove_edge, from: A, type: T, to: B}
    - {op: add_edge, after_edge: [A, T, B], line: "{from: ..., type: ..., to: ..., why: \"...\"}"}
    - {op: replace_text, old: "...", new: "..."}              an exact text, found once (the meta block)

The preview prints the lint's verdict on the changed copy (fingerprints refreshed), every node whose outcome changes
on some place, the batch's TIER, and the cascade (--what-if) of each node the batch touches. A batch with
`whatif: false` (a schema change touching most nodes) instead compares, node by node, whether the engine reads it as
needing a satisfier, before and after.

The tier is read from the operations and the outcomes, never declared:
    A  additive: only new nodes, none a decision, and edges that each touch a new node; no existing node changes
       outcome on any place. Nothing decided can move, so it may be applied directly (--apply --additive).
    B  neutral links: only new `verified-by`, `evidenced-by` or `awaits` edges between existing nodes, and no
       outcome moves. Harmless to the argument, but each says something about content: confirm them as one list.
    -  everything else (an existing node's statement, domain, kind, support or status; an edge removed; a node
       retired; a new decision; any outcome that moves): review this change on its own before applying it.
"""
import io
import re
import subprocess
import tempfile
from collections import defaultdict
from contextlib import redirect_stdout
from pathlib import Path

import yaml

from .engine import read_as_logic
from .lint import report_cascade, run_lint, summary_lines, where_root
from .registry import fix_fingerprints, load, read_registry
from . import view

NEUTRAL_EDGES = ("verified-by", "evidenced-by", "awaits")

TIER_TEXT = {
    "A": "A, additive: new nodes (none a decision) and edges touching them, no existing outcome moves; "
         "it may be applied directly (--apply --additive) and reported.",
    "B": "B, neutral links between existing nodes: confirm them as one list, then --apply.",
    "-": "review: this change can move what was decided; review it on its own, then --apply and compare the "
         "actual change with this preview.",
}


def edge_re(a, t, b):
    return re.compile(r"^  - \{from: " + re.escape(a) + r", type: " + re.escape(t) + r", to: " + re.escape(b)
                      + r"[,}]")


def node_re(nid):
    return re.compile(r"^  - \{id: " + re.escape(nid) + r", ")


class BatchError(SystemExit):
    pass


def apply_ops(text, ops):
    for op in ops:
        if op["op"] == "replace_text":
            if text.count(op["old"]) != 1:
                raise BatchError(f"replace_text: {text.count(op['old'])} matches, expected 1: {op['old']!r}")
            text = text.replace(op["old"], op["new"])
    ops = [op for op in ops if op["op"] != "replace_text"]
    lines = text.split("\n")

    def find(rx, what):
        hits = [i for i, l in enumerate(lines) if rx.search(l)]
        if len(hits) != 1:
            raise BatchError(f"{what}: {len(hits)} matching lines, expected 1")
        return hits[0]

    def sub(nid, pattern, repl, what):
        i = find(node_re(nid), f"node {nid}")
        new, n = re.subn(pattern, repl, lines[i], count=1)
        if n != 1:
            raise BatchError(f"no {what} on {nid}")
        lines[i] = new

    for op in ops:
        k = op["op"]
        if k == "add_node":
            i = find(node_re(op["after"]), f"node {op['after']}")
            lines.insert(i + 1, "  - " + op["line"])
        elif k == "set_statement":
            sub(op["id"], r'statement: "[^"]*"', lambda m: 'statement: "' + op["statement"] + '"', "statement")
        elif k == "set_domain":
            sub(op["id"], r"domain: \[[^\]]*\]", lambda m: "domain: " + op["domain"], "domain")
        elif k == "set_fields":
            sub(op["id"], r"^(  - \{id: [^,]+, )", lambda m: m.group(1) + op["fields"] + ", ", "id")
        elif k == "drop_status":
            sub(op["id"], r", status: [a-z]+", "", "status")
        elif k == "set_status":
            sub(op["id"], r"status: [a-z]+", lambda m: "status: " + op["status"], "status")
        elif k == "remove_edge":
            del lines[find(edge_re(op["from"], op["type"], op["to"]), f"edge {op}")]
        elif k == "add_edge":
            i = find(edge_re(*op["after_edge"]), f"edge {op['after_edge']}")
            lines.insert(i + 1, "  - " + op["line"])
        else:
            raise BatchError(f"unknown op {k}")
    return "\n".join(lines)


def outcomes(path):
    reg = read_registry(Path(path))
    lg = read_as_logic(reg["meta"], reg["nodes"], reg["edges"])
    return {(n, e): view.outcome(lg, n, e)[0] for e in lg.elements for n in lg.at(e)[0]}


def touched(ops):
    ids = set()
    for op in ops:
        for key in ("id", "from", "to", "after"):
            if key in op and op["op"] not in ("add_node", "replace_text"):
                ids.add(op[key])
        if op["op"] in ("add_node", "add_edge"):
            ids |= set(re.findall(r"(?:id|from|to): ([A-Za-z0-9-]+)", op["line"]))
    return sorted(ids)


def tier(ops, moved_ids, new_text):
    """'A', 'B' or '-', from the operations, the ids whose outcome the preview moved, and the registry as it would
    be (to read each new node's kind)."""
    kinds = {op["op"] for op in ops}
    new_nodes = set()
    for op in ops:
        if op["op"] == "add_node":
            m = re.search(r"\{id: ([A-Za-z0-9-]+),", op["line"])
            if m:
                new_nodes.add(m.group(1))
    if kinds <= {"add_node", "add_edge"} and new_nodes:
        for nid in new_nodes:
            line = next((l for l in new_text.split("\n") if node_re(nid).search(l)), "")
            if re.search(r"kind: decision\b", line):
                return "-"
        for op in ops:
            if op["op"] == "add_edge":
                ends = set(re.findall(r"(?:from|to): ([A-Za-z0-9-]+)", op["line"]))
                if not ends & new_nodes:
                    return "-"
        return "A" if set(moved_ids) <= new_nodes else "-"
    if kinds == {"add_edge"}:
        for op in ops:
            if not re.search(r"type: (" + "|".join(NEUTRAL_EDGES) + r")\b", op["line"]):
                return "-"
        return "B" if not moved_ids else "-"
    return "-"


def review_occasions(before, after):
    """The nodes a batch makes newly hold on a place where some threat is undefended after it: the engine shows the
    graph consistent there, only a review says whether the new support is enough. {node: sorted places}."""
    undefended = {e for (n, e), o in after.items() if o == "undefended"}
    out = {}
    for (n, e), o in after.items():
        if o == "holds" and before.get((n, e), "absent") != "holds" and e in undefended:
            out.setdefault(n, []).append(e)
    return {n: sorted(es) for n, es in out.items()}


def moved_outcomes(before, after):
    moved = defaultdict(lambda: defaultdict(list))
    for k in set(before) | set(after):
        b, a = before.get(k, "absent"), after.get(k, "absent")
        if b != a:
            moved[k[0]][f"{b} -> {a}"].append(k[1])
    return moved


def print_moved(moved):
    print(f"2. outcomes that change: {len(moved)} node(s)")
    for n in sorted(moved):
        for change, es in sorted(moved[n].items()):
            print(f"   {n:<24} {change} on {', '.join(sorted(es))}")


def lint_file(path, root, today=None):
    meta, nodes, edges = load(path)
    return run_lint(meta, nodes, edges, root=root, today=today), nodes, edges


def _fixed_copy(d, text):
    copy = Path(d) / "registry.yml"
    copy.write_text(text, encoding="utf-8")
    fix_fingerprints(copy, load(copy)[1])
    return copy


def run(batch_path, registry, root=None, apply=False, additive=False, today=None):
    batch = yaml.safe_load(Path(batch_path).read_text(encoding="utf-8"))
    ops = batch["ops"]
    reg = Path(registry)
    root = where_root(reg, root)
    new_text = apply_ops(reg.read_text(encoding="utf-8"), ops)
    if additive:
        with tempfile.TemporaryDirectory() as d:
            copy = _fixed_copy(d, new_text)
            before, after = outcomes(reg), outcomes(copy)
        moved_ids = {k[0] for k in set(before) | set(after) if before.get(k, "absent") != after.get(k, "absent")}
        t = tier(ops, moved_ids, new_text)
        if t != "A":
            raise BatchError(f"--additive refused: the preview reads this batch as tier {t}, not A ({TIER_TEXT[t]})")
    if apply:
        reg.write_text(new_text, encoding="utf-8")
        res, nodes, _ = lint_file(reg, root, today)          # before the fix: L-6 names the changed statements
        drifted = res.drifted
        fix_fingerprints(reg, nodes)
        res, nodes, edges = lint_file(reg, root, today)
        print(f"applied {len(ops)} operations to {reg.name} and refreshed fingerprints")
        print("   " + (f"statements changed: {', '.join(drifted)}" if drifted else "no statement changed"))
        print("   " + summary_lines(res, len(nodes), len(edges))[-1])
        return 1 if res.errors else 0
    with tempfile.TemporaryDirectory() as d:
        copy = _fixed_copy(d, new_text)
        res, nodes, edges = lint_file(copy, root, today)
        verdict = [f"ERROR {e}" for e in res.errors] + [summary_lines(res, len(nodes), len(edges))[-1]]
        print(f"batch {batch.get('name', batch_path)}: {len(ops)} operations")
        print("1. the lint on the changed copy:\n   " + "\n   ".join(verdict))
        before, after = outcomes(reg), outcomes(copy)
        moved = moved_outcomes(before, after)
        print_moved(moved)
        t = tier(ops, set(moved), new_text)
        print(f"   tier {TIER_TEXT[t]}")
        occasions = review_occasions(before, after)
        if occasions:
            print(f"   review occasions: {len(occasions)} node(s) newly hold where a threat is undefended")
            for n, es in sorted(occasions.items()):
                print(f"     {n:<24} on {', '.join(es)}")
        if batch.get("whatif", True) is False:
            def readings(path):
                r = read_registry(path)
                lg = read_as_logic(r["meta"], r["nodes"], r["edges"])
                return {n: lg.needs_satisfier(n) for n in lg.live}
            r0, r1 = readings(reg), readings(copy)
            differ = sorted(n for n in r0.keys() | r1.keys() if r0.get(n) != r1.get(n))
            print(f"3. the engine's reading of each live node (needs a satisfier or not): {len(r0)} before, "
                  f"{len(r1)} after; differ on {differ or 'none'}")
            return 0
        print("3. --what-if on the changed copy, for each node the batch touches")
        for nid in touched(ops):
            if nid not in res.byid:
                continue
            body = [f"=== WHAT-IF: {nid} is revised/retired ===", f"    ({res.byid[nid]['statement']})"]
            body += report_cascade(res.logic, [nid])
            print("   " + "\n   ".join(body))
    return 0


def actual(rev, registry):
    """The change a past batch made: outcomes on every place, the registry at a git revision against the working
    file, printed as the preview prints its section 2, so the two can be compared line by line."""
    reg = Path(registry).resolve()
    top = subprocess.run(["git", "-C", str(reg.parent), "rev-parse", "--show-toplevel"], capture_output=True,
                         text=True, check=True).stdout.strip()
    rel = reg.relative_to(Path(top).resolve()).as_posix()
    old_text = subprocess.run(["git", "-C", top, "show", f"{rev}:{rel}"], capture_output=True, text=True,
                              check=True).stdout
    with tempfile.TemporaryDirectory() as d:
        old = Path(d) / "registry.yml"
        old.write_text(old_text, encoding="utf-8")
        before, after = outcomes(old), outcomes(reg)
    print_moved(moved_outcomes(before, after))
    return 0


def capture(fn, *a, **kw):
    """Run fn and return (its result, what it printed)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        r = fn(*a, **kw)
    return r, buf.getvalue()
