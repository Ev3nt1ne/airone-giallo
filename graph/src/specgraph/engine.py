"""The graph read as logic, place by place.

On each place an ASSERTION holds when everything it `requires` holds; if its support is `satisfier`, one of its
satisfiers holds; every threat that `obstructs` it is defended; and it `awaits` no open question there. A THREAT is
defended where it awaits no open question and one of its defenders (`mitigates`) holds. `requires` is AND,
`satisfies` is OR: a satisfier, together with what its target requires, is enough for the target, as a defender is
against its threat. An assertion that does not hold is NOT ARGUED YET when it would hold if every open question were
answered, every assertion still without a satisfier satisfied, every threat still without a defender defended, and
every required node absent from the place held; otherwise it FAILS. Both are least fixpoints, so an assertion
supported only through itself fails. What holds is computed from the graph, never read from a status. Evidence
stands where everything it requires holds; questions, checks, records and justifications carry no truth value.
"""
from .places import DomainError, Grid
from .registry import GONE

DEFAULT_OUTSIDE = ["record", "justification"]   # kinds outside the argument: nothing rests on them


def grid_of(meta):
    return Grid(meta.get("axes") or [])


def node_domains(nodes, grid, errors=None):
    """{id: set of places} for every node that carries a domain; an unreadable domain is reported (W1)."""
    dom = {}
    for n in nodes:
        if "domain" in n:
            try:
                dom[n["id"]] = grid.domain(n["domain"])
            except DomainError as ex:
                if errors is not None:
                    errors.append(f"W1 {n['id']} has an unreadable domain: {ex}")
    return dom


class Logic:
    """The places are every place of the grid. A node is present on a place its domain covers (a node without a
    domain is present everywhere), and an edge counts there when its source is present, its domain (its own, else
    its source's) covers the place and, but for `requires`, its target is present."""

    def __init__(self, meta, nodes, edges, byid, grid, dom):
        self.byid, self.dom, self.grid = byid, dom, grid
        self.assertion_kinds = set(meta.get("assertion_kinds", []))
        self.live = {n["id"] for n in nodes if n.get("status", "active") not in GONE}
        self.edges = []
        for e in edges:
            try:
                d = grid.domain(e["domain"]) if e.get("domain") else dom.get(e["from"])
            except DomainError:
                d = dom.get(e["from"])
            self.edges.append((e["from"], e["type"], e["to"], d))
        self.elements = sorted(grid.places())
        self.cells = grid.everywhere()
        self._at, self._state = {}, {}

    def covers(self, d, e):
        return self.grid.covers(d, e)

    def kind(self, nid):
        return self.byid[nid].get("kind")

    def is_assertion(self, nid):
        return self.kind(nid) in self.assertion_kinds

    def needs_satisfier(self, nid):
        return self.byid[nid].get("support") == "satisfier"

    def present(self, nid, e):
        return nid in self.live and (nid not in self.dom or self.covers(self.dom[nid], e))

    def at(self, e):
        """The nodes present at e and the edges that count there, by relation."""
        if e not in self._at:
            present = {n for n in self.live if self.present(n, e)}
            rel = {}
            for frm, typ, to, d in self.edges:
                if frm in present and (d is None or self.covers(d, e)) and (typ == "requires" or to in present):
                    rel.setdefault(typ, []).append((frm, to))
            self._at[e] = (present, rel)
        return self._at[e]

    def links(self, e):
        """(requires, satisfiers, waiting) at e."""
        _, rel = self.at(e)
        req, sat = {}, {}
        for frm, to in rel.get("requires", []):
            req.setdefault(frm, []).append(to)
        for frm, to in rel.get("satisfies", []):
            sat.setdefault(to, []).append(frm)
        waiting = {frm for frm, _ in rel.get("awaits", [])}
        return req, sat, waiting

    def threats(self, e):
        """(obstructs, defenders) at e: the threats against each node present there, and each threat's defenders."""
        _, rel = self.at(e)
        obs, mit = {}, {}
        for frm, to in rel.get("obstructs", []):
            obs.setdefault(to, []).append(frm)
        for frm, to in rel.get("mitigates", []):
            mit.setdefault(to, []).append(frm)
        return obs, mit

    def state(self, e, forced=frozenset()):
        """(holds, not_argued) at e over the assertions present there, with the `forced` assertions made to fail and
        the `forced` threats left undefended."""
        present, _ = self.at(e)
        req, sat, waiting = self.links(e)
        obs, mit = self.threats(e)
        assertions = {n for n in present if self.is_assertion(n)}

        def defended(x, h, optimistic):
            if x in forced:
                return False
            if x in waiting:
                return optimistic
            ds = mit.get(x, [])
            return any(d in h for d in ds) or (optimistic and not ds)

        def fix(optimistic):
            h = set()
            changed = True
            while changed:
                changed = False
                for n in assertions - h - forced:
                    if n in waiting and not optimistic:
                        continue
                    if not all(r in h or (optimistic and r not in present) for r in req.get(n, [])):
                        continue
                    if self.needs_satisfier(n) and not (any(s in h for s in sat.get(n, []))
                                                         or (optimistic and not sat.get(n))):
                        continue
                    if not all(defended(x, h, optimistic) for x in obs.get(n, [])):
                        continue
                    h.add(n)
                    changed = True
            return h
        holds = fix(False)
        return holds, fix(True) - holds

    def _states(self, e):
        if e not in self._state:
            self._state[e] = self.state(e)
        return self._state[e]

    def outcome(self, nid, e):
        """On e: an assertion 'holds', is 'not argued yet' or 'fails'; a threat is 'defended' or 'undefended';
        evidence 'stands' or 'does not stand'; None for the other kinds, and where the node is not present."""
        if not self.present(nid, e):
            return None
        h, u = self._states(e)
        if self.is_assertion(nid):
            return "holds" if nid in h else "not argued yet" if nid in u else "fails"
        k = self.kind(nid)
        if k == "threat":
            return "defended" if self.defence(nid, e)[0] else "undefended"
        if k == "evidence":
            req, _, _ = self.links(e)
            return "stands" if all(r in h for r in req.get(nid, [])) else "does not stand"
        return None

    def why_not(self, nid, e):
        """What keeps an assertion from holding at e, one phrase each; empty where it holds or is absent."""
        if not self.is_assertion(nid) or self.outcome(nid, e) in (None, "holds"):
            return []
        req, sat, waiting = self.links(e)
        out = []
        if nid in waiting:
            qs = sorted(to for frm, to in self.at(e)[1].get("awaits", []) if frm == nid)
            out.append(f"awaits {', '.join(qs)}")
        for r in req.get(nid, []):
            o = self.outcome(r, e)
            if o not in ("holds", None):
                out.append(f"requires {r} ({o})")
        for r in self.required_absent(nid, e):
            out.append(f"requires {r}, not stated for this place")
        for r in self.required_gone(nid, e):
            out.append(f"requires {r}, which is {self.byid[r].get('status')}")
        if self.needs_satisfier(nid):
            s = sat.get(nid, [])
            if not s:
                out.append("no satisfier yet")
            elif not any(self.outcome(x, e) == "holds" for x in s):
                out.append("no satisfier holds (" + ", ".join(f"{x} {self.outcome(x, e)}" for x in sorted(s)) + ")")
        obs, mit = self.threats(e)
        for x in sorted(obs.get(nid, [])):
            held, other = self.defence(x, e)
            if not held:
                if x in waiting:
                    out.append(f"obstructed by {x}, whose defence awaits an open question")
                elif not mit.get(x):
                    out.append(f"obstructed by {x}, no defender yet")
                else:
                    out.append(f"obstructed by {x}, no defender holds ({', '.join(other)})")
        return out

    def required_absent(self, nid, e):
        """What nid requires that is not stated for e (the edge counts there, its target is absent)."""
        out = []
        for frm, typ, to, d in self.edges:
            if frm == nid and typ == "requires" and self.present(nid, e) and (d is None or self.covers(d, e)) \
                    and not self.present(to, e) and to in self.live:
                out.append(to)
        return out

    def required_gone(self, nid, e):
        """What nid requires at e that is retired or superseded: never read as logic, so never held."""
        return [to for frm, typ, to, d in self.edges
                if frm == nid and typ == "requires" and self.present(nid, e) and (d is None or self.covers(d, e))
                and to in self.byid and to not in self.live]

    def defence(self, nid, e):
        """(defenders that hold at e, the other defenders there with their outcome) for a threat; none hold where
        the threat awaits an open question."""
        _, rel = self.at(e)
        _, _, waiting = self.links(e)
        ds = sorted(frm for frm, to in rel.get("mitigates", []) if to == nid)
        h, _ = self._states(e)
        held = [] if nid in waiting else [d for d in ds if d in h]
        return held, [f"{d} {self.outcome(d, e)}" for d in ds if d not in held]

    def what_if(self, starts, elements=None):
        """What changing `starts` does, per place. An assertion is made to fail; a threat's defence is set aside;
        for a question, evidence or a check, what rests on it is flagged. Returns {section: {node: {reason:
        places}}} with the sections fails, warned, flagged, before (reached, but not holding there before the
        change) and start (where a start node itself did not hold, or a threat was undefended)."""
        found = {k: {} for k in ("fails", "warned", "flagged", "before", "start")}

        def put(section, nid, reason, e):
            found[section].setdefault(nid, {}).setdefault(reason, set()).add(e)

        for e in elements or self.elements:
            present, rel = self.at(e)
            s = {n for n in starts if n in present}
            if not s:
                continue
            forced = frozenset(n for n in s if self.is_assertion(n) or self.kind(n) == "threat")
            h0, u0 = self.state(e)
            h1, u1 = self.state(e, forced)
            req, sat, waiting = self.links(e)
            obs, mit = self.threats(e)
            lost = (h0 - h1) | (forced & h0)

            def defended_in(x, h):
                return x not in forced and x not in waiting and any(d in h for d in mit.get(x, []))

            def defended_before(x):
                return x not in waiting and any(d in h0 for d in mit.get(x, []))

            for n in sorted(s):
                if self.is_assertion(n) and n not in h0:
                    put("start", n, "fails there already" if n not in u0 else "not argued yet there", e)
                elif self.kind(n) == "threat" and not defended_before(n):
                    put("start", n, "undefended there already", e)

            deps = {}
            for frm, to in rel.get("requires", []):
                deps.setdefault(to, set()).add(frm)
            for frm, to in rel.get("satisfies", []):
                deps.setdefault(frm, set()).add(to)
            for target, xs in obs.items():
                for x in xs:
                    deps.setdefault(x, set()).add(target)
                    for d in mit.get(x, []):
                        deps.setdefault(d, set()).add(target)
            reached, todo = set(), list(forced)
            while todo:
                for d in deps.get(todo.pop(), ()):
                    if d not in reached and d not in forced and d not in h1:
                        reached.add(d)
                        todo.append(d)

            for n in sorted((h0 - h1) - forced):
                gone = [r for r in req.get(n, []) if r in lost]
                bared = [x for x in obs.get(n, []) if defended_before(x) and not defended_in(x, h1)]
                if gone:
                    r = gone[0]
                    put("fails", n, f"requires {r}" + ("" if r in s else " (now not argued yet)" if r in u1
                                                         else " (failed)"), e)
                elif bared:
                    x = bared[0]
                    why = "its defence set aside" if x in forced else \
                        f"defender {', '.join(sorted(d for d in mit.get(x, []) if d in lost))} lost"
                    put("fails", n, f"obstructed by {x}: {why}"
                                    + ("; left, not argued yet" if any(d in u1 for d in mit.get(x, [])) else ""), e)
                elif n in u1:
                    put("fails", n, "no satisfier holds; what is left is not argued yet", e)
                else:
                    put("fails", n, "UNSATISFIED — every satisfier lost ("
                                    + ", ".join(sorted(x for x in sat.get(n, []) if x in lost)) + ")", e)
            for n in sorted(reached - s - (h0 - h1)):
                if self.is_assertion(n) and n not in h0:
                    put("before", n, "fails there already" if n not in u0 else "not argued yet there", e)
            for n in sorted(h1 - forced):
                legs = [x for x in sat.get(n, []) if x in lost]
                if legs:
                    kept = sorted(x for x in sat[n] if x in h1)
                    put("warned", n, f"satisfier {', '.join(legs)} lost (others remain: {', '.join(kept)})", e)
            for t, ds in sorted(mit.items()):
                legs = [d for d in ds if d in lost]
                if legs and t not in forced and t not in waiting:
                    kept = sorted(d for d in ds if d in h1)
                    if kept:
                        put("warned", t, f"defender {', '.join(legs)} lost (others remain: {', '.join(kept)})", e)
                    else:
                        open_ = sorted(d for d in ds if d in u1)
                        left = f"; left, not argued yet: {', '.join(open_)}" if open_ else ", none remains"
                        put("flagged", t, f"UNDEFENDED — defender {', '.join(legs)} lost{left}", e)
            changed = {n for n in s if not self.is_assertion(n) and self.kind(n) != "threat"} | lost
            sunk = {frm for frm, to in rel.get("requires", []) if to in lost and not self.is_assertion(frm)}
            for frm, to in rel.get("requires", []):
                if frm in sunk and to in lost:
                    put("flagged", frm, f"rests on {to}, lost", e)
            for kind_, word in (("evidenced-by", "evidence"), ("verified-by", "check")):
                for frm, to in rel.get(kind_, []):
                    if (to in changed or to in sunk) and frm not in forced and (frm in h1 or frm in u0):
                        put("flagged", frm, f"{word} {to} lost", e)
            for frm, to in rel.get("awaits", []):
                if to in s and frm not in forced:
                    put("flagged", frm, f"awaits {to}, which changed: re-review", e)
        return found


def build_indexes(nodes, edges):
    byid = {n["id"]: n for n in nodes}
    out, inc = {}, {}
    for e in edges:
        out.setdefault(e["from"], []).append((e["type"], e["to"]))
        inc.setdefault(e["to"], []).append((e["type"], e["from"]))
    return byid, out, inc


def read_as_logic(meta, nodes, edges):
    """The Logic of a graph file, for tools that only read it; the schema's findings are dropped."""
    byid, _, _ = build_indexes(nodes, edges)
    grid = grid_of(meta)
    return Logic(meta, nodes, edges, byid, grid, node_domains(nodes, grid))
