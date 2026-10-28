"""The read side: look the graph up before saying anything about it. Read-only.

Each node is printed with its kind, declared status, domain, statement and `where`, what the engine computes for it
on each place of its domain, then every edge that leaves it and every edge that reaches it, with the other end's
statement and the edge's `why` where one is recorded. A domain says where a node is meant to hold; whether it holds
there is computed from the graph, never declared.
"""
import re
import sys

from .engine import grid_of, read_as_logic
from .places import DomainError

# how `why` reads a node's outgoing edges
WHY = [
    ("justification (what it is chosen to make hold or to defeat)", ("satisfies", "mitigates")),
    ("obstructs (what it defeats unless one of its defenders holds)", ("obstructs",)),
    ("requires (what must hold for it to hold)", ("requires",)),
    ("checks (what would show it false, what supports it)", ("verified-by", "evidenced-by")),
    ("awaits (open problems its argument depends on)", ("awaits",)),
]

ORDER = ("holds", "not argued yet", "fails", "defended", "undefended", "stands", "does not stand")


def short(text, width=110):
    return text if len(text) <= width else text[: width - 1] + "…"


def fmt_domain(n):
    d = n.get("domain")
    return "domain: " + (", ".join(d) if isinstance(d, list) else str(d)) if d else "domain: (none)"


def outcome(logic, nid, e):
    """(outcome, what keeps it from holding) at e; for a threat, what defends it or why nothing does."""
    o = logic.outcome(nid, e)
    if logic.kind(nid) == "threat":
        held, other = logic.defence(nid, e)
        if held:
            return o, (f"by {', '.join(held)}",)
        opens = sorted(to for frm, to in logic.at(e)[1].get("awaits", []) if frm == nid)
        return o, ((f"no defender holds ({', '.join(other)})" if other else "no defender")
                   + (f"; awaits {', '.join(opens)}" if opens else ""),)
    return o, tuple(logic.why_not(nid, e))


def computed(logic, nid, reasons):
    """What the engine computes for nid on each place it is present, grouped by outcome (and, with `reasons`, by
    what keeps it from holding, or for a threat by what defends it)."""
    if nid not in logic.live:
        return ["computed: not read as logic (retired or superseded)"]
    if not logic.is_assertion(nid) and logic.kind(nid) not in ("threat", "evidence"):
        return [f"computed: nothing (a {logic.kind(nid)} carries no truth value)"]
    places = [e for e in logic.elements if logic.present(nid, e)]
    where = "every place of its domain" if nid in logic.dom else "every place (it has no domain)"
    groups = {}
    for e in places:
        o, why = outcome(logic, nid, e)
        groups.setdefault((o, why if reasons else ()), []).append(e)
    if len({o for o, _ in groups}) == 1 and not reasons:
        o = next(iter(groups))[0]
        return [f"computed: {o} on {where} ({len(places)} places, boundaries included)"]
    lines = ["computed:"]
    for (o, why), es in sorted(groups.items(), key=lambda kv: (ORDER.index(kv[0][0]), kv[1])):
        lines.append(f"  {o} on {', '.join(es)}" + (f": {'; '.join(why)}" if why else ""))
    return lines


def show(nid, nodes, edges, logic):
    n = nodes[nid]
    print(f"{nid}  [{n.get('kind')}, {n.get('status', 'active')}]  {n.get('where', '')}")
    print(f"    {fmt_domain(n)}")
    for line in computed(logic, nid, reasons=False):
        print(f"    {line}")
    print(f"    {n.get('statement', '')}")
    for e in edges:
        dom = f" (on {', '.join(e['domain'])})" if e.get("domain") else ""
        why = f"\n        why: {e['why']}" if e.get("why") else ""
        if e["from"] == nid:
            other = nodes.get(e["to"], {}).get("statement", "?")
            print(f"    → {e['type']} {e['to']}{dom}: {short(other)}{why}")
        if e["to"] == nid:
            other = nodes.get(e["from"], {}).get("statement", "?")
            print(f"    ← {e['from']} {e['type']} it{dom}: {short(other)}{why}")
    print()


def neighbourhood(nid, edges, depth):
    """The nodes within DEPTH edges of nid, either direction, and the edges among them."""
    seen, frontier = {nid}, {nid}
    for _ in range(depth):
        nxt = set()
        for e in edges:
            if e["from"] in frontier:
                nxt.add(e["to"])
            if e["to"] in frontier:
                nxt.add(e["from"])
        frontier = nxt - seen
        seen |= nxt
    return seen, [e for e in edges if e["from"] in seen and e["to"] in seen]


def worst(logic, nid):
    """The node's worst outcome over the places it is present, or None for a kind without one."""
    outs = [logic.outcome(nid, e) for e in logic.elements if logic.present(nid, e)]
    outs = [o for o in outs if o]
    return max(outs, key=ORDER.index) if outs else None


def draw(nid, nodes, edges, logic, depth, dot):
    """The neighbourhood as a Mermaid diagram, or Graphviz with dot; each edge labelled with its relation, each
    node with its kind and its worst outcome."""
    ids, es = neighbourhood(nid, edges, depth)
    label = {}
    for i in sorted(ids):
        n = nodes[i]
        o = worst(logic, i)
        label[i] = f"{i}\n{n.get('kind', '?')}" + (f": {o}" if o else "")
    lines = []
    if dot:
        lines.append("digraph graph_ {")
        lines.append("  rankdir=LR; node [shape=box, fontname=Helvetica, fontsize=10];")
        for i in sorted(ids):
            style = " style=bold" if i == nid else ""
            lines.append(f'  "{i}" [label="{label[i]}"{style}];')
        for e in es:
            lines.append(f'  "{e["from"]}" -> "{e["to"]}" [label="{e["type"]}"];')
        lines.append("}")
    else:
        lines.append("graph LR")
        key = {i: re.sub(r"[^A-Za-z0-9]", "_", i) for i in ids}
        for i in sorted(ids):
            text = label[i].replace("\n", "<br/>")
            lines.append(f'  {key[i]}["{text}"]')
        for e in es:
            lines.append(f"  {key[e['from']]} -->|{e['type']}| {key[e['to']]}")
        lines.append(f"  style {key[nid]} stroke-width:3px")
    print("\n".join(lines))


def run(mode, args, data, graph_file_name, at=None, depth=2, dot=False):
    """One read-side command; returns the exit code."""
    meta = data.get("meta", {})
    grid = grid_of(meta)
    nodes = {n["id"]: n for n in data["nodes"]}
    edges = data.get("edges") or []
    logic = read_as_logic(meta, data["nodes"], edges)

    def holds_on(n, elems):
        try:
            d = grid.domain(n["domain"]) if n.get("domain") else (grid.everywhere() if not grid.axes else set())
        except DomainError:
            return False
        return any(grid.covers(d, x) for x in elems)

    if mode == "at" or at:
        token = at or args[0]
        try:
            elems = grid.domain([token])
        except DomainError as ex:
            print(f"not a place: {token} ({ex})", file=sys.stderr)
            return 2

    if mode == "at":
        hits = [nid for nid, n in nodes.items() if holds_on(n, elems)]
        dkinds = set(meta.get("domain_kinds", []))
        unplaced = sum(1 for nid, n in nodes.items() if n.get("kind") in dkinds and "domain" not in n
                       and nid in logic.live) if grid.axes else 0
        note = f"; {unplaced} node(s) have no domain, which the lint reports (W1)" if unplaced else ""
        groups, why = {}, {}
        for h in hits:
            outs = {e: outcome(logic, h, e) for e in sorted(elems) if logic.present(h, e)}
            if not outs or all(o is None for o, _ in outs.values()):
                groups.setdefault("no truth value (a question, check, record or justification), or not live",
                                  []).append(h)
                continue
            w = max((o for o, _ in outs.values()), key=ORDER.index)
            groups.setdefault(w, []).append(h)
            by = {}
            for e, (o, r) in outs.items():
                if o not in ("holds", "defended"):
                    by.setdefault("; ".join(r), []).append(e)
            why[h] = [(f"on {', '.join(es)}: " if len(elems) > 1 else "") + r for r, es in by.items()]
        counts = ", ".join(f"{len(groups.get(o, []))} {o}" for o in ORDER if o in ORDER[:3] or groups.get(o))
        print(f"on {args[0]}: {len(hits)} node(s) whose domain covers it{note}; computed there: {counts}")
        for g in [o for o in ORDER if o in groups] + [g for g in groups if g not in ORDER]:
            print(f"  {g} ({len(groups[g])})")
            for t in sorted({str(nodes[h].get('kind')) for h in groups[g]}):
                print(f"    {t}")
                for h in groups[g]:
                    if str(nodes[h].get("kind")) == t:
                        print(f"      {h:<22} {short(nodes[h]['statement'], 100)}")
                        for r in why.get(h, []):
                            print(f"      {'':<22} ↳ {r}")
        return 0

    if mode == "draw":
        if args[0] not in nodes:
            print(f"not in the graph: {args[0]}", file=sys.stderr)
            return 1
        draw(args[0], nodes, edges, logic, depth, dot)
        return 0

    if mode == "why":
        nid = args[0]
        if nid not in nodes:
            print(f"not in the graph: {nid}", file=sys.stderr)
            return 1
        n = nodes[nid]
        print(f"{nid}  [{n.get('kind')}, {n.get('status', 'active')}]  {n.get('where', '')}")
        print(f"    {n.get('statement', '')}")
        print(f"    {fmt_domain(n)}")
        for line in computed(logic, nid, reasons=True):
            print(f"    {line}")
        for label, types in WHY:
            outs = [e for e in edges if e["from"] == nid and e["type"] in types]
            print(f"  {label}:")
            if not outs:
                print("    (none recorded)")
            for e in outs:
                dom = f" (on {', '.join(e['domain'])})" if e.get("domain") else ""
                print(f"    {e['type']} {e['to']}{dom}: {short(nodes.get(e['to'], {}).get('statement', '?'))}"
                      + (f"\n        why: {e['why']}" if e.get("why") else ""))
        ins = [e for e in edges if e["to"] == nid]
        print(f"  rests on it ({len(ins)}): " + (", ".join(f"{e['from']} {e['type']}" for e in ins) or "nothing"))
        return 0

    if mode == "near":
        words = [w.lower() for w in args]
        hits = [nid for nid, n in nodes.items()
                if all(w in f"{nid} {n.get('statement', '')} {n.get('where', '')}".lower() for w in words)
                and (at is None or holds_on(n, elems))]
    else:
        missing = [a for a in args if a not in nodes]
        if missing:
            print(f"not in the graph: {', '.join(missing)}", file=sys.stderr)
            return 1
        hits = args
    if not hits:
        print(f"no node matches {' '.join(args)!r}{' at ' + at if at else ''} ({graph_file_name}, {len(nodes)} nodes)")
        return 1
    for nid in hits:
        show(nid, nodes, edges, logic)
    print(f"{len(hits)} node(s)")
    return 0
