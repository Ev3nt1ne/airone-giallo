"""The engine against a brute-force reference on random graphs.

The reference reads the holding rule as a monotone operator on sets of assertions and takes its least fixpoint the
long way: the intersection of every set the operator does not leave (Knaster and Tarski), by enumerating every subset.
It shares no code with the engine's iteration. Run once pessimistic (what holds) and once optimistic (what would hold
if every hole were filled); the difference is 'not argued yet'. Random graphs carry cycles, threats, open questions,
retired nodes, and domains and edge domains on a small grid with an interface axis and an ordered axis.
"""
import itertools
import random

import pytest

from specgraph.engine import read_as_logic

ASSERTION_KINDS = ["requirement", "goal", "decision", "assumption"]
META = {"assertion_kinds": ASSERTION_KINDS,
        "axes": [{"name": "side", "values": ["A", "B"], "interfaces": True},
                 {"name": "step", "values": ["S1", "S2", "S3"], "ordered": True}]}
SUPPORT = {"requirement": "satisfier", "goal": "premises", "decision": "chosen", "assumption": "given"}


def random_graph(rng, n_assertions):
    cells = [f"{a}.{s}" for a in ("A", "B") for s in ("S1", "S2", "S3")]

    def domain():
        r = rng.random()
        if r < 0.4:
            return None
        if r < 0.5:
            return ["A.S1~B.S1"] if rng.random() < 0.5 else ["A.S1>S2"]
        return sorted(rng.sample(cells, rng.randint(2, 6)))

    nodes = []
    for i in range(n_assertions):
        k = rng.choice(ASSERTION_KINDS)
        n = {"id": f"N{i}", "kind": k, "support": SUPPORT[k]}
        if rng.random() < 0.3:
            n["support"] = "satisfier"
        nodes.append(n)
    nodes += [{"id": f"T{i}", "kind": "threat"} for i in range(rng.randint(0, 2))]
    nodes += [{"id": f"Q{i}", "kind": "question"} for i in range(rng.randint(0, 1))]
    for n in nodes:
        d = domain()
        if d:
            n["domain"] = d
        if rng.random() < 0.05:
            n["status"] = "retired"
    a = [n["id"] for n in nodes if n["kind"] in ASSERTION_KINDS]
    sat = [n["id"] for n in nodes if n.get("support") == "satisfier"]
    t = [n["id"] for n in nodes if n["kind"] == "threat"]
    q = [n["id"] for n in nodes if n["kind"] == "question"]
    edges = []
    for _ in range(rng.randint(n_assertions, 2 * n_assertions + 2)):
        r = rng.random()
        if r < 0.45:
            e = {"from": rng.choice(a), "type": "requires", "to": rng.choice(a)}
        elif r < 0.75 and sat:
            e = {"from": rng.choice(a), "type": "satisfies", "to": rng.choice(sat)}
        elif r < 0.85 and t:
            e = {"from": rng.choice(t), "type": "obstructs", "to": rng.choice(a)}
        elif r < 0.95 and t:
            e = {"from": rng.choice(a), "type": "mitigates", "to": rng.choice(t)}
        elif q:
            e = {"from": rng.choice(a + t), "type": "awaits", "to": rng.choice(q)}
        else:
            continue
        if e["from"] == e["to"]:
            continue
        if rng.random() < 0.1:
            e["domain"] = sorted(rng.sample(cells, 3))
        edges.append(e)
    return nodes, edges


def reference(lg, nodes, edges, e):
    """{node: outcome} at place e, computed from the graph by enumeration."""
    grid = lg.grid
    byid = {n["id"]: n for n in nodes}
    dom = {n["id"]: grid.domain(n["domain"]) for n in nodes if "domain" in n}
    live = {n["id"] for n in nodes if n.get("status") not in ("retired", "superseded")}
    present = {n for n in live if n not in dom or grid.covers(dom[n], e)}
    counted = []
    for x in edges:
        d = grid.domain(x["domain"]) if x.get("domain") else dom.get(x["from"])
        if x["from"] in present and (d is None or grid.covers(d, e)) and (x["type"] == "requires" or x["to"] in present):
            counted.append((x["from"], x["type"], x["to"]))
    A = sorted(n for n in present if byid[n]["kind"] in ASSERTION_KINDS)
    waiting = {f for f, t, _ in counted if t == "awaits"}

    def ends(f, typ):
        return [b for a, t, b in counted if a == f and t == typ]

    def starts(to, typ):
        return [a for a, t, b in counted if b == to and t == typ]

    def defended(x, S, opt):
        if x in waiting:
            return opt
        ds = starts(x, "mitigates")
        return any(d in S for d in ds) or (opt and not ds)

    def F(S, opt):
        out = set()
        for n in A:
            if n in waiting and not opt:
                continue
            if not all(r in S or (opt and r not in present) for r in ends(n, "requires")):
                continue
            s = starts(n, "satisfies")
            if byid[n].get("support") == "satisfier" and not (any(x in S for x in s) or (opt and not s)):
                continue
            if not all(defended(x, S, opt) for x in starts(n, "obstructs")):
                continue
            out.add(n)
        return out

    def lfp(opt):
        closed = [set(S) for k in range(len(A) + 1) for S in itertools.combinations(A, k) if F(set(S), opt) <= set(S)]
        return set.intersection(*closed)

    holds, maybe = lfp(False), lfp(True)
    out = {}
    for n in present:
        k = byid[n]["kind"]
        if k in ASSERTION_KINDS:
            out[n] = "holds" if n in holds else "not argued yet" if n in maybe else "fails"
        elif k == "threat":
            out[n] = "defended" if n not in waiting and any(d in holds for d in starts(n, "mitigates")) else "undefended"
        else:
            out[n] = None
    return out


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_engine_agrees_with_brute_force(seed):
    rng = random.Random(seed)
    compared = moved = 0
    for _ in range(25):
        nodes, edges = random_graph(rng, rng.randint(4, 8))
        lg = read_as_logic(META, nodes, edges)
        for e in lg.elements:
            want = reference(lg, nodes, edges, e)
            got = {n: lg.outcome(n, e) for n in want}
            assert got == want, (seed, e, nodes, edges)
            compared += len(want)
            moved += sum(1 for o in want.values() if o not in ("holds", "defended", None))
    assert compared > 1000 and moved > 100        # the graphs exercise more than the trivial case


@pytest.mark.parametrize("seed", [4, 5])
def test_every_assertion_that_does_not_hold_has_a_reason(seed):
    rng = random.Random(seed)
    for _ in range(25):
        nodes, edges = random_graph(rng, rng.randint(4, 8))
        lg = read_as_logic(META, nodes, edges)
        for e in lg.elements:
            for n in sorted(lg.at(e)[0]):
                if lg.is_assertion(n):
                    held = lg.outcome(n, e) == "holds"
                    assert held == (not lg.why_not(n, e)), (n, e)
