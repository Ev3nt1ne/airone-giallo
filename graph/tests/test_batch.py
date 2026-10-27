"""The batch tool's tier: what the preview reads as additive (A), as neutral links (B), and as needing review (-),
from known operations and outcomes; the review occasions; and one preview and apply on a real file."""
import tempfile
from pathlib import Path

from specgraph import batch as gb
from helpers import call

NEW_ATK = {"op": "add_node", "after": "ATK-01",
           "line": '{id: ATK-99, kind: threat, statement: "x", where: "spec.md §1", domain: [all], fingerprint: "00000000"}'}
NEW_DEC = {"op": "add_node", "after": "DEC-a",
           "line": '{id: DEC-new, kind: decision, support: chosen, statement: "x", where: "spec.md §1", domain: [all], '
                   'fingerprint: "00000000"}'}
EDGE_TO_NEW = {"op": "add_edge", "after_edge": ["A", "requires", "B"], "line": "{from: ATK-99, type: obstructs, to: REQ-01}"}
EDGE_OLD_OLD = {"op": "add_edge", "after_edge": ["A", "requires", "B"], "line": "{from: GOAL-01, type: requires, to: ASM-01}"}
VERIFIED = {"op": "add_edge", "after_edge": ["A", "requires", "B"], "line": "{from: GOAL-01, type: verified-by, to: CHK-01}"}


def text_with(*ops):
    """The registry as it would read after OPS: enough of a node line for tier() to find each new node's kind."""
    return "\n".join("  - " + op["line"] for op in ops if op["op"] == "add_node")


class TestTier:
    def test_additive(self):
        ops = [NEW_ATK, EDGE_TO_NEW]
        assert gb.tier(ops, {"ATK-99"}, text_with(*ops)) == "A"      # only the new node's outcome moved
        assert gb.tier(ops, set(), text_with(*ops)) == "A"

    def test_a_moved_existing_outcome_needs_review(self):
        ops = [NEW_ATK, EDGE_TO_NEW]
        assert gb.tier(ops, {"ATK-99", "REQ-01"}, text_with(*ops)) == "-"

    def test_a_new_decision_needs_review(self):
        ops = [NEW_DEC, {"op": "add_edge", "after_edge": ["A", "requires", "B"],
                         "line": "{from: DEC-new, type: satisfies, to: REQ-02}"}]
        assert gb.tier(ops, {"DEC-new"}, text_with(*ops)) == "-"

    def test_an_edge_between_existing_nodes_is_not_additive(self):
        ops = [NEW_ATK, EDGE_OLD_OLD]
        assert gb.tier(ops, set(), text_with(*ops)) == "-"

    def test_neutral_links(self):
        assert gb.tier([VERIFIED], set(), "") == "B"
        assert gb.tier([VERIFIED, EDGE_OLD_OLD], set(), "") == "-"     # requires is not a neutral link
        assert gb.tier([VERIFIED], {"GOAL-01"}, "") == "-"              # an outcome moved

    def test_any_edit_needs_review(self):
        for op in ({"op": "set_statement", "id": "GOAL-01", "statement": "y"},
                   {"op": "set_domain", "id": "GOAL-01", "domain": "[all]"},
                   {"op": "drop_status", "id": "GOAL-01"}, {"op": "remove_edge", "from": "A", "type": "requires", "to": "B"},
                   {"op": "replace_text", "old": "a", "new": "b"}):
            assert gb.tier([NEW_ATK, op], set(), text_with(NEW_ATK)) == "-", op["op"]
        assert gb.tier([], set(), "") == "-"


class TestOccasions:
    def test_newly_holding_where_a_threat_is_undefended(self):
        before = {("REQ-01", "Z1.BETA"): "not argued yet", ("REQ-01", "Z2.BETA"): "not argued yet",
                  ("ATK-01", "Z1.BETA"): "undefended", ("ATK-01", "Z2.BETA"): "defended", ("GOAL-01", "Z1.BETA"): "holds"}
        after = {**before, ("REQ-01", "Z1.BETA"): "holds", ("REQ-01", "Z2.BETA"): "holds", ("DEC-new", "Z1.BETA"): "holds"}
        assert gb.review_occasions(before, after) == {"REQ-01": ["Z1.BETA"], "DEC-new": ["Z1.BETA"]}
        # nothing newly holds: no occasion; a place with every threat defended: no occasion
        assert gb.review_occasions(after, after) == {}
        assert gb.review_occasions(before, {**before, ("REQ-01", "Z2.BETA"): "holds"}) == {}


REGISTRY = """meta: {prefixes: [DEC, REQ, ASM, ATK], slug_prefixes: [DEC], axes: [],
  assertion_kinds: [requirement, assumption, decision], other_kinds: [threat],
  supports: [given, chosen, premises, satisfier], domain_kinds: [requirement, assumption, decision, threat],
  relations: {requires: {from: [assertion], to: [requirement, assumption, decision]},
    satisfies: {from: [decision, requirement], to: [requirement]}, mitigates: {from: [decision, requirement], to: [threat]},
    obstructs: {from: [threat], to: [requirement]}}}
nodes:
  - {id: REQ-01, kind: requirement, support: satisfier, statement: "A saved file survives a crash.", where: "spec.md §1"}
  - {id: DEC-journal, kind: decision, support: chosen, statement: "Writes go through a journal.", where: "spec.md §1"}
edges:
  - {from: DEC-journal, type: satisfies, to: REQ-01}
"""


class TestPreviewAndApply:
    def setup_registry(self, d):
        p = Path(d) / "registry.yml"
        p.write_text(REGISTRY)
        (Path(d) / "spec.md").write_text("# Spec\n\n## 1. One\n")
        call(["lint", "--registry", str(p), "--fix"])
        return p

    def test_an_additive_batch_is_read_as_a_and_applied(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.setup_registry(d)
            b = Path(d) / "b.yml"
            b.write_text('ops:\n  - {op: add_node, after: DEC-journal, line: \'{id: ATK-01, kind: threat, statement: "Power is '
                         'cut mid-write.", where: "spec.md §1"}\'}\n'
                         '  - {op: add_edge, after_edge: [DEC-journal, satisfies, REQ-01], line: "{from: DEC-journal, type: '
                         'mitigates, to: ATK-01}"}\n')
            code, out = call(["batch", str(b), "--registry", str(p)])
            assert "tier A, additive" in out
            assert "ATK-01" in out.split("2. outcomes that change")[1]      # the new node's outcome appears
            assert "ATK-01" not in p.read_text()                             # a preview writes nothing
            code, out = call(["batch", str(b), "--registry", str(p), "--apply", "--additive"])
            assert "applied 2 operations" in out and code == 0, out
            assert "ATK-01" in p.read_text()

    def test_a_batch_that_moves_an_outcome_is_refused_as_additive(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.setup_registry(d)
            b = Path(d) / "b.yml"
            b.write_text("ops:\n  - {op: remove_edge, from: DEC-journal, type: satisfies, to: REQ-01}\n")
            code, out = call(["batch", str(b), "--registry", str(p)])
            assert "REQ-01                   holds -> not argued yet on all" in out
            assert "tier review" in out
            code, out = call(["batch", str(b), "--registry", str(p), "--apply", "--additive"])
            assert code == 1 and "--additive refused" in out
            assert "satisfies" in p.read_text()
