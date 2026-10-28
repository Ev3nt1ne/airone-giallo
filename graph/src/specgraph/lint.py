"""The lint: the graph file's form, checked rule by rule. Whether a node holds is the engine's, reported apart.

Rule index (the full text is in docs/spec-graph.md):
  L-1 grammar, uniqueness, statuses, edge types, endpoints     L-2 no family prefix is a prefix of another
  L-3 an assertion argued from premises names them               L-6 fingerprint drift
  L-7 no circular argument, place by place                      L-8 orphans (warning)
  L-9 what is taken as given is dated and watched                W0 relations join the kinds they allow
  W1 domains where the kind asks for one                        W2 a requirement's domain covers its user's
  W4 a decision says what it is for                             W5 validated claims have a check (a count)
  W6 evidence names its system                                   W7 the temporary orphan exemption names kinds
  W10 kind and support                                           W11 `where` resolves
"""
import datetime
import re
from pathlib import Path

from .engine import DEFAULT_OUTSIDE, Logic, build_indexes, grid_of, node_domains
from .places import DomainError
from .registry import GONE, fingerprint
from .where import Forms, check_where

STATUSES = {"active", "candidate", "suspect", "open", "retired", "superseded"}   # declared, never truth


def kinds_of(meta, names):
    """A relation's kind list with `assertion` expanded to every assertion kind."""
    out = set()
    for k in names:
        out |= set(meta.get("assertion_kinds", [])) if k == "assertion" else {k}
    return out


class Result:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def check_schema(meta, nodes, edges, byid, out, inc, errors, warnings, backfill):
    """W0, W1, W2, W4, W5, W6, W10. Returns (grid, {id: domain}) for the nodes that carry a domain."""
    grid = grid_of(meta)
    rel = meta.get("relations", {}) or {}
    assertion_kinds = set(meta.get("assertion_kinds", []))
    all_kinds = assertion_kinds | set(meta.get("other_kinds", []))
    domain_kinds = set(meta.get("domain_kinds", []))
    live = [n for n in nodes if n.get("status", "active") not in GONE]
    kind = {n["id"]: n.get("kind") for n in nodes}
    dom = node_domains(nodes, grid, errors)

    def edge_dom(e):
        if "domain" in e:
            return grid.domain(e["domain"])
        return dom.get(e["from"])

    # W10: every live node says what it is (`kind`), and an assertion how it comes to hold (`support`)
    for n in live:
        k, sp = n.get("kind"), n.get("support")
        if k not in all_kinds:
            errors.append(f"W10 {n['id']} has no kind, or one not in meta's kinds: {k}")
        elif k in assertion_kinds and sp not in set(meta.get("supports", [])):
            errors.append(f"W10 {n['id']} is an assertion ({k}) with no support, or one not in meta.supports: {sp}")
        elif k not in assertion_kinds and sp is not None:
            errors.append(f"W10 {n['id']} is a {k}, which carries no support")

    # W0: every edge joins kinds its relation allows; `satisfies` ends at a node that needs a satisfier; an edge's
    # domain lies within its source's
    for e in edges:
        if e["from"] not in byid or e["to"] not in byid:
            continue
        r = rel.get(e["type"])
        fk, tk = kind.get(e["from"]), kind.get(e["to"])
        if r is not None:
            if r.get("same") and fk != tk:
                errors.append(f"W0 {e['type']} joins two nodes of one kind: {e['from']} -> {e['to']}")
            if "from" in r and fk not in kinds_of(meta, r["from"]):
                errors.append(f"W0 {e['type']} may not start at a {fk}: {e['from']} -> {e['to']}")
            if "to" in r and tk not in kinds_of(meta, r["to"]):
                errors.append(f"W0 {e['type']} may not end at a {tk}: {e['from']} -> {e['to']}")
        if e["type"] == "satisfies" and byid[e["to"]].get("support") != "satisfier":
            errors.append(f"W0 {e['from']} satisfies {e['to']}, whose support is not `satisfier`: "
                          "the engine would not read it")
        if "domain" in e:
            try:
                ed = grid.domain(e["domain"])
            except DomainError as ex:
                errors.append(f"W0 edge {e['from']} -> {e['to']} has an unreadable domain: {ex}")
                continue
            src = dom.get(e["from"])
            if src is None or not ed <= src:
                errors.append(f"W0 edge {e['from']} {e['type']} {e['to']}: its domain is not within {e['from']}'s")

    # W1: where there are axes, a node of a kind that says where it holds has a domain; a kind that does not, none
    for n in live:
        k = n.get("kind")
        if k in domain_kinds and "domain" not in n and grid.axes:
            errors.append(f"W1 {n['id']} has no domain: every {k} says where it holds")
        elif k in all_kinds and k not in domain_kinds and "domain" in n:
            errors.append(f"W1 {n['id']} is a {k}, which carries no domain")

    # W2: requires(x, y) => every place of the edge's domain is covered by y's
    for e in edges:
        if e["type"] != "requires":
            continue
        try:
            dx = edge_dom(e)
        except DomainError:
            continue
        dy = dom.get(e["to"])
        if dx is None or dy is None:
            continue
        bad = sorted(x for x in dx if not grid.covers(dy, x))
        if bad:
            errors.append(f"W2 {e['from']} requires {e['to']}, which does not hold on {', '.join(bad)}")

    # W4: every decision says what it is for (what it satisfies or mitigates)
    for n in live:
        if n.get("kind") == "decision" and not any(t in ("satisfies", "mitigates") for t, _ in out.get(n["id"], [])):
            errors.append(f"W4 {n['id']} has no justification: a decision says what it satisfies or mitigates")

    # W5: an assertion argued from its premises and declared validated (not `candidate`) has evidence or a check
    for n in live:
        if n.get("support") == "premises" and n.get("status", "active") != "candidate":
            if not any(t in ("verified-by", "evidenced-by") for t, _ in out.get(n["id"], [])):
                backfill["W5 claim without check"].append(n["id"])

    # W6: evidence something rests on names the system that produced it and requires an assertion taken as given
    # that this system stands for its places
    for n in live:
        nid = n["id"]
        if n.get("kind") != "evidence" or not inc.get(nid):
            continue
        given = [to for t, to in out.get(nid, []) if t == "requires" and to in byid
                 and byid[to].get("support") == "given"]
        ok = bool(n.get("system")) and any(
            nid not in dom or (to in dom and dom[nid] <= dom[to]) for to in given)
        if not ok:
            errors.append(f"W6 {nid} names no system, or no assumption taken as given that its system stands "
                          "for its places")
    return grid, dom


def id_pattern(meta):
    """The ID grammar from meta: `PREFIX-NN` for numbered families (`id_digits`, default 2 to 3 digits),
    `PREFIX-slug` for the families in `slug_prefixes`."""
    lo, hi = (meta.get("id_digits") or [2, 3])[:2]
    slugs = set(meta.get("slug_prefixes", []) or [])
    numbered = [p for p in meta.get("prefixes", []) or [] if p not in slugs]
    parts = []
    if numbered:
        parts.append(r"^(" + "|".join(numbered) + r")-[0-9]{" + f"{lo},{hi}" + r"}$")
    if slugs:
        parts.append(r"^(" + "|".join(sorted(slugs)) + r")-[a-z0-9][a-z0-9-]*$")
    return re.compile("|".join(parts) if parts else r"(?!)")


def run_lint(meta, nodes, edges, *, root, today=None, fixing=False):
    """Every check. Returns a Result with errors, warnings, backfill, drifted, logic, grid, dom, byid."""
    byid, out, inc = build_indexes(nodes, edges)
    errors, warnings = [], []

    # L-1: grammar, uniqueness, statuses, edge types, endpoints; `open` names the work item that clears it
    slugs = set(meta.get("slug_prefixes", []) or [])
    prefixes = list(meta.get("prefixes", []) or [])
    id_re = id_pattern(meta)
    seen = set()
    for n in nodes:
        if not id_re.match(str(n["id"])):
            errors.append(f"L-1 bad id grammar: {n['id']}")
        if n["id"] in seen:
            errors.append(f"L-1 duplicate id: {n['id']}")
        seen.add(n["id"])
        if n.get("status", "active") not in STATUSES:
            errors.append(f"L-1 bad status on {n['id']}: {n.get('status')}")
        elif n.get("status") == "open" and not n.get("homed_by"):
            errors.append(f"L-1 status `open` marks a condition waiting on its work item; {n['id']} names no `homed_by`")
    edge_types = set(meta.get("edge_types") or (meta.get("relations") or {}).keys())
    for e in edges:
        if e["type"] not in edge_types:
            errors.append(f"L-1 bad edge type: {e}")
        for end in (e["from"], e["to"]):
            if end not in byid:
                errors.append(f"L-1 dangling edge endpoint: {end} in {e}")
    for p_ in slugs - set(prefixes):
        errors.append(f"L-1 meta.slug_prefixes names {p_}, which is not in meta.prefixes")

    # L-2: prefix closure (no prefix is a prefix of another)
    for a in prefixes:
        for b in prefixes:
            if a != b and b.startswith(a):
                errors.append(f"L-2 prefix collision: {a} prefixes {b}")

    live = [n for n in nodes if n.get("status", "active") not in GONE]
    # L-3: an assertion argued from its premises names them
    for n in live:
        if n.get("support") == "premises" and not any(t == "requires" for t, _ in out.get(n["id"], [])):
            errors.append(f"L-3 {n['id']} is argued from its premises and states none (no `requires` edge)")

    # L-6: fingerprint drift
    drifted = []
    for n in nodes:
        fp = fingerprint(n["statement"])
        if "fingerprint" in n and str(n["fingerprint"]) != fp:
            drifted.append(n["id"])
        elif "fingerprint" not in n and not fixing:
            warnings.append(f"L-6 {n['id']} has no fingerprint (run --fix)")
    if drifted:
        errors.append(f"L-6 {len(drifted)} node(s) changed — re-review the cascade above, then run --fix")

    # L-8: orphans (no edge at all), a warning; records and justifications are outside the argument; single nodes
    # in meta.orphan_ok with a reason; kinds in meta.orphan_exempt while they are being linked (W7)
    outside = set(meta.get("outside_kinds", DEFAULT_OUTSIDE) or [])
    kinds = set(meta.get("assertion_kinds", [])) | set(meta.get("other_kinds", []))
    ok = meta.get("orphan_ok") or {}
    for nid, why in ok.items():
        if nid not in byid:
            errors.append(f"L-8 meta.orphan_ok names {nid}, which is not a node")
        elif not str(why or "").strip():
            errors.append(f"L-8 meta.orphan_ok gives {nid} no reason")
        elif nid in out or nid in inc:
            warnings.append(f"L-8 {nid} has an edge now: remove it from meta.orphan_ok")
    exempt = set(meta.get("orphan_exempt", []) or [])

    def asked(n):
        return n.get("kind") not in outside and n["id"] not in ok

    for n in live:
        nid = n["id"]
        if nid not in out and nid not in inc and asked(n) and n.get("kind") not in exempt:
            warnings.append(f"L-8 orphan node: {nid}")
    # W7: the temporary list names kinds, and only while one of its nodes is still unlinked
    for k in sorted(exempt):
        if k not in kinds or k in outside:
            errors.append(f"W7 meta.orphan_exempt names {k}, which is not a kind in the argument")
        elif not any(n.get("kind") == k and asked(n) and n["id"] not in out and n["id"] not in inc for n in live):
            warnings.append(f"W7 {k} has no orphan left: remove it from meta.orphan_exempt")

    # L-9: what is taken as given carries the date it was last confirmed and how many days it may go unchecked
    today = today or datetime.date.today()
    for n in live:
        if n.get("support") != "given":
            continue
        rev, watch = n.get("reviewed"), n.get("watch")
        try:
            rev = rev if isinstance(rev, datetime.date) else datetime.date.fromisoformat(str(rev))
            watch = int(watch)
        except (TypeError, ValueError):
            errors.append(f"L-9 {n['id']} is taken as given and needs `reviewed: YYYY-MM-DD` and `watch: <days>`")
            continue
        due = rev + datetime.timedelta(days=watch)
        if today > due:
            warnings.append(f"L-9 {n['id']} last reviewed {rev}, due {due}: is it still true of the world?")

    # W11: `where` resolves under root
    forms = Forms(meta)
    for n in live:
        problems, named = check_where(n.get("where", ""), root, forms)
        if not named:
            warnings.append(f"W11 {n['id']}: `where` names no document: {n.get('where')!r}")
        for kind_, tok in problems:
            what = {"file": "names a document that does not resolve",
                    "section": "cites a section no heading starts with",
                    "id": "cites an ID the document does not contain"}[kind_]
            errors.append(f"W11 {n['id']}: `where` {what}: {tok} (in {n.get('where')!r})")

    backfill = {"W5 claim without check": []}
    grid, dom = check_schema(meta, nodes, edges, byid, out, inc, errors, warnings, backfill)
    logic = Logic(meta, nodes, edges, byid, grid, dom)

    # L-7: no circular argument, place by place; a node depends on what it requires, on what satisfies it, and
    # on the defenders of the threats that obstruct it
    cycles = {}
    for el in logic.elements:
        _, rel = logic.at(el)
        dep = {}
        for frm, to in rel.get("requires", []):
            dep.setdefault(frm, []).append(to)
        for frm, to in rel.get("satisfies", []):
            dep.setdefault(to, []).append(frm)
        defenders = {}
        for frm, to in rel.get("mitigates", []):
            defenders.setdefault(to, []).append(frm)
        for frm, to in rel.get("obstructs", []):
            dep.setdefault(to, []).extend(defenders.get(frm, []))
        color = {}

        def dfs(u, stack):
            color[u] = 1
            stack.append(u)
            for v in dep.get(u, []):
                if color.get(v) == 1:
                    cyc = stack[stack.index(v):] + [v]
                    cycles.setdefault(frozenset(cyc), (cyc, set()))[1].add(el)
                elif not color.get(v):
                    dfs(v, stack)
            stack.pop()
            color[u] = 2
        for u in list(dep):
            if not color.get(u):
                dfs(u, [])
    for cyc, els in cycles.values():
        errors.append(f"L-7 circular argument: {' -> '.join(cyc)} (on {', '.join(sorted(els))})")

    return Result(errors=errors, warnings=warnings, backfill=backfill, drifted=drifted, logic=logic, grid=grid,
                  dom=dom, byid=byid)


def engine_summary(logic):
    """How many assertions fail, or are not argued yet, on some place, and how many threats are undefended there."""
    fails, open_, undefended = set(), set(), set()
    for e in logic.elements:
        for n in logic.at(e)[0]:
            o = logic.outcome(n, e)
            if o == "fails":
                fails.add(n)
            elif o == "not argued yet":
                open_.add(n)
            elif o == "undefended":
                undefended.add(n)
    return (f"{len(fails)} assertion(s) fail somewhere, {len(open_ - fails)} more not argued yet somewhere; "
            f"{len(undefended)} threat(s) undefended somewhere")


def short_places(logic, nid, elems):
    """The places of a report line, written short: only those in the node's own domain when there are any; every
    cell as "every cell"; with two axes or more, every cell of one first-axis value as `V.*`."""
    own = logic.dom.get(nid)
    shown = (elems & own) if own and elems & own else elems
    cells = shown & logic.cells
    rest = sorted(shown - cells)
    if cells == logic.cells:
        return ", ".join(["every cell"] + rest)
    axes = logic.grid.axes
    if len(axes) < 2:
        return ", ".join(sorted(cells) + rest)
    per_value = len(logic.cells) // len(axes[0].values)
    words = []
    for v in sorted(axes[0].values):
        mine = {c for c in cells if c.split(".")[0] == v}
        if mine and len(mine) == per_value:
            words.append(v + ".*" * (len(axes) - 1))
        else:
            words += sorted(mine)
    return ", ".join(words + rest)


def report_cascade(logic, start_ids, elements=None):
    """The cascade report, as lines."""
    lines = []
    found = logic.what_if(set(start_ids), elements)
    for nid, reasons in found["start"].items():
        for reason, elems in reasons.items():
            lines.append(f"  note: {nid}, on {short_places(logic, nid, elems)}: {reason}")
    if not any(v for k, v in found.items() if k != "start"):
        if found["start"]:
            lines.append("  cascade: nothing changes downstream — where something rests on it, it does not hold now")
        else:
            lines.append("  cascade: nothing downstream — no proposition rests on this node")
        return lines
    titles = (
        ("fails", "fail there, suspect until re-reviewed (the failure spreads)"),
        ("warned", "still hold, on fewer legs: warning (stops there)"),
        ("flagged", "flagged for re-review (stops there): lost backing, or what they rest on or await changed"),
        ("before", "rest on it but did not hold there before the change (not counted)"),
    )
    lines.append(f"  cascade: {len(found['fails'])} node(s) {titles[0][1]}:")
    for key, title in titles:
        if key != "fails":
            if not found[key]:
                continue
            lines.append(f"  {len(found[key])} node(s) {title}:")
        for nid, reasons in found[key].items():
            for reason, elems in reasons.items():
                lines.append(f"    {nid:<22} [{reason}] on {short_places(logic, nid, elems)}")
            lines.append(f"    {'':<22}  \"{logic.byid[nid]['statement']}\"")
    return lines


def what_if_lines(res, target):
    """--what-if from a node or from a place token: (lines, exit code or None)."""
    logic, byid, grid, dom = res.logic, res.byid, res.grid, res.dom
    if target in byid:
        return ([f"\n=== WHAT-IF: {target} is revised/retired ===", f"    ({byid[target]['statement']})"]
                + report_cascade(logic, [target])), None
    try:
        elems = grid.domain([target])
    except DomainError as ex:
        return [f"not a node and not a place: {target} ({ex})"], 2
    every = grid.everywhere()
    start = [nid for nid, d in dom.items() if any(grid.covers(d, x) for x in elems)]
    specific = [nid for nid in start if not every <= dom[nid]]
    general = [nid for nid in start if every <= dom[nid]]
    lines = [f"\n=== WHAT-IF: what we believe about {target} changes ===",
             f"  holding there ({len(specific)} specific, {len(general)} on every cell):"]
    for nid in specific:
        lines.append(f"    {nid:<22} {byid[nid]['statement'][:100]}")
    if general:
        lines.append(f"    on every cell: {', '.join(general)}")
    if not start:
        lines.append("    (no node carries a domain covering it yet)")
    else:
        lines += report_cascade(logic, start, sorted(elems))
    return lines, None


def summary_lines(res, n_nodes, n_edges, prog="lint"):
    lines = [f"\n{n_nodes} nodes, {n_edges} edges"]
    lines += [f"  WARN  {w}" for w in res.warnings]
    lines += [f"  ERROR {e}" for e in res.errors]
    bf = ", ".join(f"{k} {len(v)}" for k, v in res.backfill.items())
    lines.append(f"  backfill (schema, not warnings): {bf}")
    lines.append(f"  engine (computed, not warnings): {engine_summary(res.logic)}")
    lines.append(f"{prog}: {len(res.errors)} error(s), {len(res.warnings)} warning(s)")
    return lines


def where_root(registry_path, root=None):
    return Path(root).resolve() if root else Path(registry_path).resolve().parent
