"""The lint's rules (L-1 … L-9, W0 … W11), the engine and its cascade (from a node and from a place), and the read
side's view of what the engine computes.

Each rule is run on a small throwaway registry twice: once with the defect it exists to catch (it must fire) and
once corrected (it must stay silent), so a rule that always fires or never fires fails here.
"""
import tempfile
from pathlib import Path

import yaml

from specgraph.engine import read_as_logic
from helpers import META, call, edge, graph, node, report, run, section, write


def row(nid, reason):
    """One line of a cascade report, as the report pads it."""
    return f"{nid:<22} [{reason}]"


class TestSchemaRules:
    def test_w0_typing_by_kind(self):
        nodes = [node("GOAL-01", ["all"]), node("ATK-01", ["all"]), node("ASM-01", ["all"])]
        base = [edge("GOAL-01", "requires", "ASM-01")]
        code, out = run(nodes, base + [edge("ATK-01", "mitigates", "GOAL-01")])
        assert "W0 mitigates may not start at a threat" in out
        assert code == 1
        code, out = run(nodes, base + [edge("GOAL-01", "mitigates", "ATK-01")])
        assert "W0" not in out

    def test_w0_reads_the_kind_not_the_family(self):
        # a decision under the QST family may satisfy; an assumption under the EXP family may be required
        nodes = [node("QST-01", ["all"], kind="decision", support="chosen"), node("REQ-01", ["all"]),
                 node("EXP-01", ["all"], kind="assumption", support="given"), node("GOAL-01", ["all"])]
        edges = [edge("QST-01", "satisfies", "REQ-01"), edge("GOAL-01", "requires", "EXP-01")]
        code, out = run(nodes, edges)
        assert "W0" not in out
        assert code == 0
        nodes[0] = node("QST-01", ["all"])          # a question cannot satisfy
        code, out = run(nodes, edges)
        assert "W0 satisfies may not start at a question: QST-01 -> REQ-01" in out

    def test_w0_satisfies_only_what_needs_a_satisfier(self):
        nodes = [node("DEC-a", ["all"]), node("GOAL-01", ["all"]), node("ASM-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("DEC-a", "satisfies", "GOAL-01")]
        code, out = run(nodes, edges)
        assert "W0 DEC-a satisfies GOAL-01, whose support is not `satisfier`" in out
        assert code == 1
        nodes[1] = node("GOAL-01", ["all"], support="satisfier")
        code, out = run(nodes, edges)
        assert "W0" not in out

    def test_w0_edge_domain_within_source(self):
        nodes = [node("GOAL-01", ["Z1.*"]), node("ASM-01", ["all"])]
        code, out = run(nodes, [edge("GOAL-01", "requires", "ASM-01", domain=["Z2.BETA"])])
        assert "its domain is not within GOAL-01's" in out
        code, out = run(nodes, [edge("GOAL-01", "requires", "ASM-01", domain=["Z1.SCALE"])])
        assert "W0" not in out

    def test_w1_a_node_says_where_it_holds(self):
        code, out = run([node("ASM-01")], [])
        assert "W1 ASM-01 has no domain: every assumption says where it holds" in out
        assert code == 1
        code, out = run([node("ASM-01", ["Z2.BETA"])], [])
        assert "W1" not in out
        assert code == 0
        # an objective, a record and a retired node are not asked for one
        code, out = run([node("REC-01"), node("OBJ-01"), node("DEC-y", status="retired", kind=None, support=None)], [])
        assert "W1" not in out
        # a record carries none
        code, out = run([node("REC-01", ["all"])], [])
        assert "W1 REC-01 is a record, which carries no domain" in out

    def test_w1_unreadable_domain(self):
        code, out = run([node("DEC-x", ["Z4.BETA"])], [])
        assert "unreadable domain" in out

    def test_w2_inclusion(self):
        nodes = [node("GOAL-01", ["Z1.*"]), node("ASM-01", ["Z2.*"])]
        code, out = run(nodes, [edge("GOAL-01", "requires", "ASM-01")])
        assert "ERROR W2 GOAL-01 requires ASM-01, which does not hold on Z1.BETA" in out
        assert code == 1
        nodes[1]["domain"] = ["all"]
        code, out = run(nodes, [edge("GOAL-01", "requires", "ASM-01")])
        assert "W2" not in out

    def test_w2_edge_domain_narrows(self):
        nodes = [node("GOAL-01", ["Z1.*", "Z2.SCALE"]), node("REQ-01", ["Z1.*"]), node("DEC-a", ["Z1.*"])]
        edges = [edge("DEC-a", "satisfies", "REQ-01")]
        code, out = run(nodes, edges + [edge("GOAL-01", "requires", "REQ-01")])
        assert "does not hold on Z2.SCALE" in out
        code, out = run(nodes, edges + [edge("GOAL-01", "requires", "REQ-01", domain=["Z1.*"])])
        assert "W2" not in out

    def test_status_is_declared_never_truth(self):
        code, out = run([node("REQ-01", ["all"], status="unsatisfied")], [])
        assert "L-1 bad status on REQ-01: unsatisfied" in out
        code, out = run([node("REQ-01", ["all"], status="open")], [])
        assert "L-1 status `open` marks a gate condition until its work item closes; REQ-01 names no `homed_by`" in out
        code, out = run([node("REQ-01", ["all"], status="open", homed_by="the next release")], [])
        assert "L-1" not in out

    def test_w10_kind_and_support(self):
        code, out = run([node("REQ-01", ["all"], kind=None, support=None)], [])
        assert "W10 REQ-01 has no kind" in out
        code, out = run([node("REQ-01", ["all"], support=None)], [])
        assert "W10 REQ-01 is an assertion (requirement) with no support" in out
        code, out = run([node("ATK-01", ["all"], support="chosen")], [])
        assert "W10 ATK-01 is a threat, which carries no support" in out
        code, out = run([node("REQ-01", ["all"])], [])
        assert "W10" not in out

    def test_nothing_rests_on_a_record(self):
        nodes = [node("DEC-a", ["all"]), node("DEC-r", kind="record", support=None), node("REQ-01", ["all"])]
        code, out = run(nodes, [edge("DEC-a", "satisfies", "REQ-01"), edge("DEC-a", "requires", "DEC-r")])
        assert "W0 requires may not end at a record: DEC-a -> DEC-r" in out
        assert code == 1
        # a record may rest on an assertion; it is not asked for edges
        nodes.append(node("REC-01"))
        code, out = run(nodes, [edge("DEC-a", "satisfies", "REQ-01"), edge("REC-01", "requires", "REQ-01")])
        assert "W0" not in out
        assert "L-8 orphan node: DEC-r" not in out
        assert code == 0

    def test_l9_what_is_taken_as_given_is_dated_and_watched(self):
        nodes = [node("ASM-01", ["all"])]
        code, out = run(nodes, [], "--today", "2025-01-09")      # 365 days after: due, not past
        assert "L-9" not in out
        code, out = run(nodes, [], "--today", "2025-01-10")
        assert "L-9 ASM-01 last reviewed 2024-01-10, due 2025-01-09" in out
        code, out = run([node("ASM-01", ["all"], watch=None)], [])
        assert "ERROR L-9 ASM-01 is taken as given and needs" in out
        assert code == 1
        code, out = run([node("ASM-01", ["all"], status="retired")], [], "--today", "2030-01-01")
        assert "L-9" not in out
        # by support, not by family: an assumption under EXP is asked; an ASM argued from premises is not
        exp = node("EXP-01", ["all"], kind="assumption", support="given")
        del exp["reviewed"], exp["watch"]
        code, out = run([exp], [])
        assert "ERROR L-9 EXP-01 is taken as given" in out
        code, out = run([node("ASM-02", ["all"], kind="requirement", support="premises"), node("ASM-01", ["all"])],
                        [edge("ASM-02", "requires", "ASM-01")])
        assert "L-9 ASM-02" not in out

    def test_w4_decision_needs_why(self):
        nodes = [node("DEC-a", ["all"]), node("REQ-01", ["all"])]
        code, out = run(nodes, [])
        assert "ERROR W4 DEC-a has no justification" in out
        assert code == 1
        code, out = run(nodes, [edge("DEC-a", "satisfies", "REQ-01")])
        assert "W4" not in out
        # by kind, not by family
        code, out = run([node("QST-01", ["all"], kind="decision", support="chosen")], [])
        assert "ERROR W4 QST-01 has no justification" in out

    def test_w6_evidence_names_its_system(self):
        nodes = [node("EVD-01", ["Z2.BETA"]), node("ASM-01", ["Z2.BETA", "Z2.PROD"]), node("GOAL-01", ["Z2.BETA"])]
        edges = [edge("EVD-01", "requires", "ASM-01"), edge("GOAL-01", "requires", "ASM-01"),
                 edge("GOAL-01", "evidenced-by", "EVD-01")]
        code, out = run(nodes, edges[:2])                  # evidence nothing rests on is not asked
        assert "W6" not in out
        code, out = run(nodes, edges)
        assert "ERROR W6 EVD-01 names no system" in out
        assert code == 1
        nodes[0]["system"] = "a load test on one machine"
        code, out = run(nodes, edges)
        assert "W6" not in out
        nodes[1]["domain"] = ["Z2.PROD"]            # the assumption no longer covers the evidence
        code, out = run(nodes, edges)
        assert "ERROR W6 EVD-01 names no system" in out
        # what the evidence stands on must be taken as given, whatever its family
        nodes[1] = node("ASM-01", ["Z2.BETA", "Z2.PROD"], kind="requirement", support="premises")
        code, out = run(nodes + [node("ASM-02", ["all"])], edges + [edge("ASM-01", "requires", "ASM-02")])
        assert "ERROR W6 EVD-01 names no system" in out

    def test_l3_premises_are_named(self):
        code, out = run([node("GOAL-01", ["all"])], [])
        assert "ERROR L-3 GOAL-01 is argued from its premises and states none" in out
        code, out = run([node("GOAL-01", ["all"]), node("ASM-01", ["all"])], [edge("GOAL-01", "requires", "ASM-01")])
        assert "L-3" not in out
        # by support: a REQ argued from its premises is asked too
        code, out = run([node("REQ-01", ["all"], support="premises")], [])
        assert "ERROR L-3 REQ-01" in out

    def test_a_duplicate_key_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = write(dict(META, orphan_ok={}), [node("ASM-01", ["all"])], [], d)
            text = p.read_text().replace("  statement:", "  where: twice\n  statement:", 1)
            p.write_text(text)
            code, out = call(["lint", "--registry", str(p)])
        assert "ERROR L-1 registry.yml cannot be read" in out
        assert "duplicate key 'where'" in out
        assert code == 1

    def test_fix_leaves_one_fingerprint(self):
        # a placeholder written before another field is replaced, not kept beside the real one
        text = ('meta: ' + yaml.safe_dump(dict(META, orphan_ok={}), default_flow_style=True).strip() + '\n'
                'nodes:\n'
                '  - {id: ASM-01, kind: assumption, support: given, statement: "s", where: "w", '
                'domain: [all], reviewed: 2024-01-10, watch: 365, fingerprint: "00000000", note: "n"}\n'
                'edges: []\n')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "registry.yml"
            p.write_text(text)
            call(["lint", "--registry", str(p), "--fix"])
            line = [l for l in p.read_text().splitlines() if "ASM-01" in l][0]
            code, out = call(["lint", "--registry", str(p), "--today", "2024-06-01"])
        assert line.count("fingerprint") == 1
        assert line.endswith('fingerprint: "043a7187"}'), line
        assert "ERROR" not in out


class TestBackfillCounts:
    @staticmethod
    def count(out, label):
        line = [l for l in out.splitlines() if "backfill" in l][0]
        return int(line.split(label)[1].split(",")[0])

    def test_w5_claim_needs_check(self):
        nodes = [node("GOAL-01", ["all"]), node("ASM-01", ["all"]), node("CHK-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01")]
        code, out = run(nodes, edges)
        assert self.count(out, "W5 claim without check ") == 1
        code, out = run(nodes, edges + [edge("GOAL-01", "verified-by", "CHK-01")])
        assert self.count(out, "W5 claim without check ") == 0
        nodes[0]["status"] = "candidate"           # not declared validated: not counted
        code, out = run(nodes, edges)
        assert self.count(out, "W5 claim without check ") == 0

    def test_w7_exemption_list_names_kinds(self):
        nodes = [node("DEC-a", ["all"])]
        code, out = run(nodes, [], orphan_exempt=["decision"])
        assert "L-8 orphan node: DEC-a" not in out
        code, out = run(nodes, [], orphan_exempt=[])
        assert "L-8 orphan node: DEC-a" in out
        nodes[0]["status"] = "retired"            # kept for its ID: no edge is expected
        code, out = run(nodes, [], orphan_exempt=[])
        assert "L-8 orphan node: DEC-a" not in out
        code, out = run([node("ASM-01", ["all"])], [], orphan_exempt=["DEC"])
        assert "W7 meta.orphan_exempt names DEC, which is not a kind in the argument" in out
        code, out = run([node("ASM-01", ["all"])], [], orphan_exempt=["record"])
        assert "W7 meta.orphan_exempt names record, which is not a kind in the argument" in out

    def test_w7_a_linked_kind_leaves_the_list(self):
        nodes = [node("DEC-a", ["all"]), node("REQ-01", ["all"])]
        code, out = run(nodes, [edge("DEC-a", "satisfies", "REQ-01")], orphan_exempt=["decision"])
        assert "W7 decision has no orphan left" in out
        code, out = run(nodes, [], orphan_exempt=["decision"])
        assert "W7" not in out

    def test_l8_records_and_justifications_are_outside_the_argument(self):
        code, out = run([node("REC-01"), node("JUS-01")], [], orphan_exempt=[])
        assert "L-8" not in out
        code, out = run([node("REC-01", ["all"], kind="assumption", support="given")], [], orphan_exempt=[])
        assert "L-8 orphan node: REC-01" in out

    def test_l8_single_exemptions_carry_a_reason(self):
        nodes = [node("ATK-10", ["all"]), node("GOAL-01", ["all"]), node("ASM-01", ["all"])]
        base = [edge("GOAL-01", "requires", "ASM-01")]
        code, out = run(nodes, base, orphan_exempt=[], orphan_ok={"ATK-10": "nothing in the design answers it"})
        assert "L-8" not in out
        code, out = run(nodes, base, orphan_exempt=[])
        assert "L-8 orphan node: ATK-10" in out
        code, out = run(nodes, base, orphan_exempt=[], orphan_ok={"ATK-10": ""})
        assert "L-8 meta.orphan_ok gives ATK-10 no reason" in out
        assert code == 1
        code, out = run(nodes, base, orphan_exempt=[], orphan_ok={"ATK-12": "a reason"})
        assert "L-8 meta.orphan_ok names ATK-12, which is not a node" in out
        code, out = run(nodes, base + [edge("GOAL-01", "mitigates", "ATK-10")], orphan_exempt=[],
                        orphan_ok={"ATK-10": "a reason"})
        assert "L-8 ATK-10 has an edge now: remove it from meta.orphan_ok" in out


class TestCascade:
    def test_place_what_if(self):
        nodes = [node("GOAL-01", ["Z2.BETA", "Z2.PROD"]), node("ASM-01", ["all"]), node("DEC-a", ["Z1.SCALE"]),
                 node("REQ-01", ["Z1.SCALE"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("DEC-a", "satisfies", "REQ-01")]
        code, out = run(nodes, edges, "--what-if", "Z2.BETA")
        assert "1 specific, 1 on every cell" in out
        assert "GOAL-01" in out
        assert "DEC-a " not in out.split("holding there")[1].split("cascade")[0]

    def test_boundary_what_if_reaches_side_nodes(self):
        nodes = [node("GOAL-01", ["Z1.PROD~Z2.PROD"]), node("ASM-01", ["Z2.PROD"]), node("ASM-02", ["Z1.PROD"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("GOAL-01", "requires", "ASM-02")]
        code, out = run(nodes, edges, "--what-if", "Z2.PROD")
        holding = out.split("holding there")[1].split("cascade:")[0]
        assert "GOAL-01" in holding

    def test_w2_cell_rests_on_boundary_rule(self):
        nodes = [node("GOAL-01", ["Z2.PROD"]), node("REQ-01", ["Z1.PROD~Z2.PROD"]),
                 node("DEC-a", ["Z1.PROD~Z2.PROD"])]
        edges = [edge("GOAL-01", "requires", "REQ-01"), edge("DEC-a", "satisfies", "REQ-01")]
        code, out = run(nodes, edges)
        assert "W2" not in out
        nodes[1]["domain"] = ["Z1.SCALE~Z2.SCALE"]
        nodes[2]["domain"] = ["Z1.SCALE~Z2.SCALE"]
        code, out = run(nodes, edges)
        assert "W2 GOAL-01 requires REQ-01, which does not hold on Z2.PROD" in out

    def test_place_cascade_walks_only_edges_holding_there(self):
        # GOAL-01 and REQ-01 are not present at Z1.DEV; they must not be reported from there just because they rest
        # on nodes that hold everywhere. A record carries no domain and rests on ASM-01: it is flagged there.
        nodes = [node("ASM-01", ["all"]), node("GOAL-01", ["Z1.PROD"]), node("REQ-01", ["Z2.*"]),
                 node("DEC-a", ["all"]), node("REC-01")]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("DEC-a", "satisfies", "REQ-01"),
                 edge("REC-01", "requires", "ASM-01")]
        code, out = run(nodes, edges, "--what-if", "Z1.DEV")
        cascade = report(out)
        assert "GOAL-01" not in cascade
        assert "REQ-01" not in cascade
        assert row("REC-01", "rests on ASM-01, lost") in section(out, "flagged")

    def test_every_place_is_evaluated(self):
        # the places are the grid's, not the ones some domain happens to name: an interface nothing names is still a
        # place where a node holding on its sides is read
        nodes = [node("DEC-a", ["all"]), node("REQ-01", ["all"])]
        lg = read_as_logic(dict(META), nodes, [edge("DEC-a", "satisfies", "REQ-01")])
        assert len(lg.elements) == 33
        assert lg.outcome("REQ-01", "Z2.BETA~Z3.BETA") == "holds"


class TestOpenQuestions:
    """`awaits`: where the link counts the node is at best not argued yet, a threat undefended, and answering or
    changing the question flags it."""

    def test_a_node_awaiting_a_question_is_not_argued_yet(self):
        nodes = [node("GOAL-01", ["all"]), node("ASM-01", ["all"]), node("QST-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01")]
        out = graph(nodes, edges, "why", "GOAL-01")
        assert "computed:" in out
        assert "not argued yet" not in out
        out = graph(nodes, edges + [edge("GOAL-01", "awaits", "QST-01", domain=["Z2.BETA"])], "why", "GOAL-01")
        import re
        assert re.search(r"not argued yet on [^\n]*\bZ2\.BETA,[^\n]*: awaits QST-01", out)
        assert re.search(r"holds on [^\n]*Z2\.PROD", out)

    def test_a_threat_awaiting_a_question_is_undefended(self):
        nodes = [node("ATK-01", ["Z2.BETA"]), node("DEC-a", ["Z2.BETA"]), node("QST-01", ["Z2.BETA"])]
        edges = [edge("DEC-a", "mitigates", "ATK-01")]
        assert "computed: defended" in graph(nodes, edges, "show", "ATK-01")
        assert "computed: undefended" in graph(nodes, edges + [edge("ATK-01", "awaits", "QST-01")], "show", "ATK-01")

    def test_what_a_threat_awaiting_a_question_obstructs_is_not_argued_yet(self):
        import re
        nodes = [node("ATK-01", ["Z2.BETA"]), node("DEC-a", ["Z2.BETA"]), node("QST-01", ["Z2.BETA"]),
                 node("DEC-b", ["Z2.BETA"]), node("REQ-01", ["Z2.BETA"])]
        edges = [edge("DEC-a", "mitigates", "ATK-01"), edge("DEC-b", "satisfies", "REQ-01"),
                 edge("ATK-01", "obstructs", "REQ-01")]
        out = graph(nodes, edges, "why", "REQ-01")
        assert "holds on" in out
        assert "not argued yet" not in out
        out = graph(nodes, edges + [edge("ATK-01", "awaits", "QST-01")], "why", "REQ-01")
        assert re.search(r"not argued yet on [^\n]*\bZ2\.BETA,[^\n]*: obstructed by ATK-01, whose defence awaits an "
                         r"open question", out)

    def test_a_changed_question_flags_what_awaits_it(self):
        nodes = [node("REQ-01", ["all"]), node("QST-01", ["all"]), node("GOAL-01", ["all"])]
        edges = [edge("REQ-01", "awaits", "QST-01"), edge("GOAL-01", "requires", "REQ-01")]
        code, out = run(nodes, edges, "--what-if", "QST-01")
        assert row("REQ-01", "awaits QST-01, which changed: re-review") in section(out, "flagged")
        assert "cascade: 0 node(s) fail" in out
        code, out = run(nodes, edges[1:], "--what-if", "QST-01")
        assert "nothing downstream" in out


class TestCircularity:
    def test_l7_reads_satisfies_against_requires(self):
        # GOAL-01 needs REQ-01, and REQ-01 holds only because of GOAL-01: a circle, though both edges leave GOAL-01
        nodes = [node("ASM-01", ["all"]), node("GOAL-01", ["all"]), node("REQ-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("GOAL-01", "satisfies", "REQ-01")]
        code, out = run(nodes, edges)
        assert "L-7" not in out
        code, out = run(nodes, edges + [edge("GOAL-01", "requires", "REQ-01")])
        assert "ERROR L-7 circular argument: GOAL-01 -> REQ-01 -> GOAL-01" in out
        assert code == 1

    def test_l7_is_checked_place_by_place(self):
        # the two halves of the circle hold on places that share no boundary: no place has the circle
        nodes = [node("ASM-01", ["all"]), node("GOAL-01", ["all"]), node("REQ-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("GOAL-01", "satisfies", "REQ-01", domain=["Z1.PROD"]),
                 edge("GOAL-01", "requires", "REQ-01", domain=["Z2.SCALE"])]
        code, out = run(nodes, edges)
        assert "L-7" not in out
        edges[2]["domain"] = ["Z1.PROD"]
        code, out = run(nodes, edges)
        assert "L-7 circular argument: GOAL-01 -> REQ-01 -> GOAL-01 (on Z1.BETA>PROD, Z1.PROD," in out


class TestCascadeRule:
    """A necessary link fails and spreads; a sufficient link fails and spreads once every supporter has failed,
    judged when nothing more fails, and otherwise warns; a supporting link flags; a warning or a flag stops where it
    lands; defenders warn or flag their threat, checks flag their claim. Place by place, on what the graph makes
    hold rather than on declared statuses."""

    def test_necessary_fails_and_spreads(self):
        nodes = [node("ASM-01", ["all"]), node("GOAL-01", ["all"]), node("GOAL-02", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("GOAL-02", "requires", "GOAL-01")]
        code, out = run(nodes, edges, "--what-if", "ASM-01")
        failed = section(out, "fail")
        assert row("GOAL-01", "requires ASM-01") + " on every cell" in failed
        assert row("GOAL-02", "requires GOAL-01 (failed)") + " on every cell" in failed

    def test_sufficient_every_supporter_lost_fails_and_spreads(self):
        nodes = [node("DEC-a", ["all"]), node("REQ-01", ["all"]), node("GOAL-01", ["all"])]
        edges = [edge("DEC-a", "satisfies", "REQ-01"), edge("GOAL-01", "requires", "REQ-01")]
        code, out = run(nodes, edges, "--what-if", "DEC-a")
        failed = section(out, "fail")
        assert row("REQ-01", "UNSATISFIED — every satisfier lost (DEC-a)") in failed
        assert row("GOAL-01", "requires REQ-01 (failed)") in failed

    def test_sufficient_judged_when_nothing_more_fails(self):
        # DEC-a fails at the first step, GOAL-01 at the second: REQ-01 loses both and fails, not a warning
        nodes = [node("ASM-01", ["all"]), node("DEC-a", ["all"]), node("GOAL-01", ["all"]),
                 node("GOAL-02", ["all"]), node("REQ-01", ["all"])]
        edges = [edge("DEC-a", "requires", "ASM-01"), edge("GOAL-02", "requires", "ASM-01"),
                 edge("GOAL-01", "requires", "GOAL-02"), edge("DEC-a", "satisfies", "REQ-01"),
                 edge("GOAL-01", "satisfies", "REQ-01")]
        code, out = run(nodes, edges, "--what-if", "ASM-01")
        assert row("REQ-01", "UNSATISFIED — every satisfier lost (DEC-a, GOAL-01)") in section(out, "fail")
        assert "REQ-01" not in section(out, "still hold")

    def test_sufficient_some_supporters_left_warns_and_stops(self):
        nodes = [node("DEC-a", ["all"]), node("DEC-b", ["all"]), node("REQ-01", ["all"]), node("GOAL-01", ["all"])]
        edges = [edge("DEC-a", "satisfies", "REQ-01"), edge("DEC-b", "satisfies", "REQ-01"),
                 edge("GOAL-01", "requires", "REQ-01")]
        code, out = run(nodes, edges, "--what-if", "DEC-a")
        assert row("REQ-01", "satisfier DEC-a lost (others remain: DEC-b)") in section(out, "still hold")
        assert "cascade: 0 node(s) fail" in out
        assert "GOAL-01 " not in report(out)

    def test_supporting_evidence_flags_and_stops(self):
        nodes = [node("ASM-01", ["all"]), node("EVD-01", ["all"]), node("GOAL-01", ["all"]), node("GOAL-02", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("GOAL-01", "evidenced-by", "EVD-01"),
                 edge("GOAL-02", "requires", "GOAL-01")]
        code, out = run(nodes, edges, "--what-if", "EVD-01")
        assert row("GOAL-01", "evidence EVD-01 lost") in section(out, "flagged")
        assert "cascade: 0 node(s) fail" in out
        assert "GOAL-02" not in report(out)

    def test_evidence_falls_with_its_assumption(self):
        # EVD-01 stands for the system only while ASM-02 holds: losing ASM-02 flags the evidence and the goal it backs
        nodes = [node("ASM-01", ["all"]), node("ASM-02", ["all"]), node("EVD-01", ["all"], system="a model"),
                 node("GOAL-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("GOAL-01", "evidenced-by", "EVD-01"),
                 edge("EVD-01", "requires", "ASM-02")]
        code, out = run(nodes, edges, "--what-if", "ASM-02")
        flagged = section(out, "flagged")
        assert row("EVD-01", "rests on ASM-02, lost") in flagged
        assert row("GOAL-01", "evidence EVD-01 lost") in flagged
        assert "cascade: 0 node(s) fail" in out

    def test_a_record_is_flagged_for_what_it_lost_only(self):
        nodes = [node("ASM-01", ["all"]), node("ASM-02", ["all"]), node("REC-01")]
        edges = [edge("REC-01", "requires", "ASM-01"), edge("REC-01", "requires", "ASM-02")]
        code, out = run(nodes, edges, "--what-if", "ASM-01")
        flagged = section(out, "flagged")
        assert row("REC-01", "rests on ASM-01, lost") in flagged
        assert "ASM-02" not in flagged

    def test_check_flags_its_claim(self):
        nodes = [node("ASM-01", ["all"]), node("GOAL-01", ["all"]), node("CHK-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("GOAL-01", "verified-by", "CHK-01")]
        code, out = run(nodes, edges, "--what-if", "CHK-01")
        assert row("GOAL-01", "check CHK-01 lost") in section(out, "flagged")

    def test_defender_lost_warns_then_flags_the_threat(self):
        nodes = [node("ASM-01", ["all"]), node("GOAL-01", ["all"]), node("GOAL-02", ["all"]),
                 node("ATK-01", ["all"]), node("REQ-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("GOAL-02", "requires", "ASM-01"),
                 edge("GOAL-01", "mitigates", "ATK-01"), edge("GOAL-02", "mitigates", "ATK-01")]
        code, out = run(nodes, edges, "--what-if", "GOAL-01")
        assert row("ATK-01", "defender GOAL-01 lost (others remain: GOAL-02)") in section(out, "still hold")
        code, out = run(nodes, edges[:3], "--what-if", "GOAL-01")
        assert row("ATK-01", "UNDEFENDED — defender GOAL-01 lost, none remains") in section(out, "flagged")
        # the other defender is not argued yet (it rests on a requirement nothing satisfies): named as such
        code, out = run(nodes, edges + [edge("GOAL-02", "requires", "REQ-01")], "--what-if", "GOAL-01")
        assert row("ATK-01", "UNDEFENDED — defender GOAL-01 lost; left, not argued yet: GOAL-02") \
            in section(out, "flagged")

    def test_fails_only_where_the_edge_holds(self):
        nodes = [node("ASM-01", ["all"]), node("GOAL-01", ["Z1.*"])]
        edges = [edge("GOAL-01", "requires", "ASM-01", domain=["Z1.PROD"])]
        code, out = run(nodes, edges, "--what-if", "ASM-01")
        assert row("GOAL-01", "requires ASM-01") + " on Z1.PROD\n" in section(out, "fail") + "\n"

    def test_each_cell_has_its_own_satisfiers(self):
        # one satisfier per stage: losing the beta stage's leaves the requirement with nothing there, though the
        # other satisfier still holds it elsewhere
        nodes = [node("REQ-01", ["Z2.BETA", "Z2.SCALE"]), node("DEC-a", ["Z2.BETA", "Z2.SCALE"]),
                 node("DEC-b", ["Z2.BETA", "Z2.SCALE"])]
        edges = [edge("DEC-a", "satisfies", "REQ-01", domain=["Z2.BETA"]),
                 edge("DEC-b", "satisfies", "REQ-01", domain=["Z2.SCALE"])]
        code, out = run(nodes, edges, "--what-if", "DEC-a")
        assert row("REQ-01", "UNSATISFIED — every satisfier lost (DEC-a)") + " on Z2.BETA" in section(out, "fail")
        assert "REQ-01" not in section(out, "still hold")

    def test_a_satisfier_that_does_not_hold_is_no_leg(self):
        # DEC-b is declared active but rests on a requirement nothing satisfies: it is not argued yet, so losing
        # DEC-a leaves REQ-01 with no satisfier that holds, not "on fewer legs"
        nodes = [node("DEC-a", ["all"]), node("DEC-b", ["all"]), node("REQ-01", ["all"]), node("REQ-02", ["all"])]
        edges = [edge("DEC-a", "satisfies", "REQ-01"), edge("DEC-b", "satisfies", "REQ-01"),
                 edge("DEC-b", "requires", "REQ-02")]
        code, out = run(nodes, edges, "--what-if", "DEC-a")
        assert row("REQ-01", "no satisfier holds; what is left is not argued yet") in section(out, "fail")
        assert "REQ-01" not in section(out, "still hold")

    def test_not_argued_yet_is_not_a_failure(self):
        nodes = [node("ASM-01", ["all"]), node("GOAL-01", ["all"]), node("REQ-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("GOAL-01", "requires", "REQ-01")]
        code, out = run(nodes, edges, "--what-if", "ASM-01")
        assert "cascade: 0 node(s) fail" in out
        assert row("GOAL-01", "not argued yet there") in section(out, "did not hold")

    def test_a_required_node_absent_from_a_place_is_not_argued_yet(self):
        nodes = [node("GOAL-01", ["all"]), node("ASM-01", ["Z2.*"])]
        lg = read_as_logic(dict(META), nodes, [edge("GOAL-01", "requires", "ASM-01")])
        assert lg.outcome("GOAL-01", "Z2.BETA") == "holds"
        assert lg.outcome("GOAL-01", "Z1.BETA") == "not argued yet"
        assert lg.why_not("GOAL-01", "Z1.BETA") == ["requires ASM-01, not stated for this place"]

    def test_a_start_that_does_not_hold_is_said(self):
        nodes = [node("GOAL-01", ["all"]), node("REQ-01", ["all"]), node("ATK-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "REQ-01"), edge("GOAL-01", "mitigates", "ATK-01")]
        code, out = run(nodes, edges, "--what-if", "GOAL-01")
        assert "note: GOAL-01, on every cell: not argued yet there" in out
        assert "cascade: nothing changes downstream — where something rests on it, it does not hold now" in out

    def test_what_still_holds_shields_what_rests_on_it(self):
        # REQ-01 keeps DEC-b, so GOAL-01, which rests on it (and on a requirement nothing satisfies), is not listed
        nodes = [node("DEC-a", ["all"]), node("DEC-b", ["all"]), node("REQ-01", ["all"]),
                 node("REQ-02", ["all"]), node("GOAL-01", ["all"])]
        edges = [edge("DEC-a", "satisfies", "REQ-01"), edge("DEC-b", "satisfies", "REQ-01"),
                 edge("GOAL-01", "requires", "REQ-01"), edge("GOAL-01", "requires", "REQ-02")]
        code, out = run(nodes, edges, "--what-if", "DEC-a")
        assert "REQ-01" in section(out, "still hold")
        assert "GOAL-01" not in report(out)

    def test_support_through_itself_fails(self):
        # GOAL-01 holds only if REQ-01 does, and REQ-01 only because of GOAL-01: neither holds
        nodes = [node("ASM-01", ["all"]), node("GOAL-01", ["all"]), node("REQ-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("GOAL-01", "requires", "REQ-01"),
                 edge("GOAL-01", "satisfies", "REQ-01")]
        code, out = run(nodes, edges, "--what-if", "ASM-01")
        assert row("GOAL-01", "fails there already") in section(out, "did not hold")


class TestSupport:
    def test_support_not_family_decides(self):
        # REQ-01 argued from its premises holds without a satisfier; GOAL-01 declared to need one does not
        nodes = [node("ASM-01", ["all"]), node("REQ-01", ["all"], support="premises"),
                 node("GOAL-01", ["all"], support="satisfier")]
        edges = [edge("REQ-01", "requires", "ASM-01"), edge("GOAL-01", "requires", "ASM-01")]
        out = graph(nodes, edges, "at", "Z2.BETA")
        held, open_ = out.split("  not argued yet (1)")
        assert "REQ-01" in held
        assert "GOAL-01" in open_
        assert "↳ no satisfier yet" in open_


class TestObstruction:
    """A threat that obstructs a node keeps it from holding until one of its defenders holds."""

    @staticmethod
    def base(defenders=("GOAL-02",)):
        nodes = [node("DEC-a", ["all"]), node("REQ-01", ["all"]), node("GOAL-01", ["all"]), node("ATK-01", ["all"]),
                 node("ASM-01", ["all"]), node("ASM-02", ["all"])]
        edges = [edge("DEC-a", "satisfies", "REQ-01"), edge("GOAL-01", "requires", "REQ-01"),
                 edge("ATK-01", "obstructs", "REQ-01")]
        for i, d in enumerate(defenders):
            nodes.append(node(d, ["all"]))
            edges += [edge(d, "mitigates", "ATK-01"), edge(d, "requires", f"ASM-0{i + 1}")]
        return nodes, edges

    def test_no_defender_yet_is_not_argued_yet(self):
        nodes, edges = self.base(defenders=())
        out = graph(nodes, edges, "at", "Z2.BETA")
        assert "↳ obstructed by ATK-01, no defender yet" in out
        open_ = out.split("  not argued yet (2)")[1]
        assert "REQ-01" in open_
        assert "GOAL-01" in open_

    def test_a_defence_lost_fails_the_target_and_spreads(self):
        nodes, edges = self.base()
        code, out = run(nodes, edges, "--what-if", "ASM-01")
        fails = section(out, "fail there")
        assert row("REQ-01", "obstructed by ATK-01: defender GOAL-02 lost") in fails
        assert row("GOAL-01", "requires REQ-01 (failed)") in fails
        assert "UNDEFENDED — defender GOAL-02 lost" in out

    def test_a_defender_left_keeps_the_target(self):
        nodes, edges = self.base(defenders=("GOAL-02", "GOAL-03"))
        code, out = run(nodes, edges, "--what-if", "ASM-01")
        assert "REQ-01" not in section(out, "fail there")
        assert "defender GOAL-02 lost (others remain: GOAL-03)" in out

    def test_what_rests_on_a_defence_is_listed_where_it_did_not_hold(self):
        nodes, edges = self.base()
        nodes = [n for n in nodes if n["id"] != "DEC-a"]
        edges = [e for e in edges if e["from"] != "DEC-a"]
        code, out = run(nodes, edges, "--what-if", "GOAL-02")
        assert row("REQ-01", "not argued yet there") in section(out, "did not hold")

    def test_a_defence_resting_on_its_target_is_circular(self):
        nodes, edges = self.base()
        edges.append(edge("GOAL-02", "requires", "REQ-01"))
        code, out = run(nodes, edges)
        assert "L-7 circular argument" in out
        code, out = run(*self.base())
        assert "L-7" not in out

    def test_a_threat_changed_sets_its_defence_aside(self):
        nodes, edges = self.base()
        code, out = run(nodes, edges, "--what-if", "ATK-01")
        fails = section(out, "fail there")
        assert row("REQ-01", "obstructed by ATK-01: its defence set aside") in fails
        assert row("GOAL-01", "requires REQ-01 (failed)") in fails
        nodes, edges = self.base(defenders=())
        code, out = run(nodes, edges, "--what-if", "ATK-01")
        assert "note: ATK-01, on every cell: undefended there already" in out


class TestGraphView:
    """The read side shows what the engine computes, not what a domain or a status declares."""

    def test_at_groups_by_what_holds_there(self):
        # REQ-01 has a satisfier; REQ-02 none yet; GOAL-01 rests on REQ-02; DEC-old is retired
        nodes = [node("DEC-a", ["Z2.BETA"]), node("REQ-01", ["Z2.BETA"]), node("REQ-02", ["Z2.BETA"]),
                 node("GOAL-01", ["Z2.BETA"]), node("DEC-old", ["Z2.BETA"], status="retired")]
        edges = [edge("DEC-a", "satisfies", "REQ-01"), edge("GOAL-01", "requires", "REQ-02")]
        out = graph(nodes, edges, "at", "Z2.BETA")
        assert "computed there: 2 holds, 2 not argued yet, 0 fails" in out
        held, open_ = out.split("  not argued yet (2)")
        assert "DEC-a" in held
        assert "REQ-01" in held
        assert "GOAL-01" not in held
        assert "↳ requires REQ-02 (not argued yet)" in open_
        assert "↳ no satisfier yet" in open_
        assert "DEC-old" in open_.split("no truth value")[1]

    def test_a_failure_is_said_with_its_cause(self):
        # GOAL-01 and GOAL-02 rest on each other, so neither holds; REQ-01's only satisfier is GOAL-01
        nodes = [node("GOAL-01", ["Z2.BETA"], kind="requirement"), node("GOAL-02", ["Z2.BETA"]),
                 node("REQ-01", ["Z2.BETA"])]
        edges = [edge("GOAL-01", "requires", "GOAL-02"), edge("GOAL-02", "requires", "GOAL-01"),
                 edge("GOAL-01", "satisfies", "REQ-01")]
        out = graph(nodes, edges, "at", "Z2.BETA")
        assert "computed there: 0 holds, 0 not argued yet, 3 fails" in out
        assert "↳ no satisfier holds (GOAL-01 fails)" in out
        assert "↳ requires GOAL-02 (fails)" in out

    def test_why_says_where_it_holds_and_why_not(self):
        import re
        nodes = [node("DEC-a", ["Z2.BETA"]), node("REQ-01", ["Z2.BETA", "Z2.PROD"])]
        edges = [edge("DEC-a", "satisfies", "REQ-01")]
        out = graph(nodes, edges, "why", "REQ-01")
        assert re.search(r"\n      holds on [^\n]*\bZ2\.BETA\b", out)
        assert re.search(r"\n      not argued yet on [^\n]*\bZ2\.PROD\b[^\n]*: no satisfier yet", out)
        assert "computed: holds on every place of its domain" in graph(nodes, edges, "show", "DEC-a")

    def test_a_threat_is_read_by_its_defence(self):
        # ATK-01's defender rests on a requirement nothing satisfies; ATK-02 has none and awaits QST-01;
        # DEC-a defends ATK-03
        nodes = [node("ATK-01", ["Z2.BETA"]), node("ATK-02", ["Z2.BETA"]), node("ATK-03", ["Z2.BETA"]),
                 node("GOAL-01", ["Z2.BETA"]), node("REQ-01", ["Z2.BETA"]), node("DEC-a", ["Z2.BETA"]),
                 node("QST-01", ["Z2.BETA"])]
        edges = [edge("GOAL-01", "mitigates", "ATK-01"), edge("GOAL-01", "requires", "REQ-01"),
                 edge("ATK-02", "awaits", "QST-01"), edge("DEC-a", "mitigates", "ATK-03")]
        out = graph(nodes, edges, "at", "Z2.BETA")
        assert "1 defended, 2 undefended" in out
        assert "↳ no defender holds (GOAL-01 not argued yet)" in out
        assert "↳ no defender; awaits QST-01" in out
        assert "ATK-03" in out.split("  defended (1)")[1].split("  undefended (2)")[0]
        assert "computed: defended on every place of its domain" in graph(nodes, edges, "show", "ATK-03")

    def test_a_threat_is_known_by_its_kind(self):
        # one family, two kinds: a record carries no truth value; a threat is read by its defence
        nodes = [node("ATK-10", kind="record"), node("ATK-11", ["Z2.BETA"])]
        assert "1 undefended" in graph(nodes, [], "at", "Z2.BETA")
        assert "computed: nothing (a record carries no truth value)" in graph(nodes, [], "show", "ATK-10")


class TestWhere:
    """W11: a node's `where` names a document under the registry's folder, and every section and ID it cites is there."""

    def test_a_resolving_where_is_silent(self):
        code, out = run([node("ATK-01", ["all"], where="spec.md §1 ATK-01"),
                         node("GOAL-01", ["all"], where="spec.md §1.2/§7; spec.md #7")],
                        [edge("GOAL-01", "mitigates", "ATK-01")])
        assert "W11" not in out

    def test_a_missing_document_is_an_error(self):
        code, out = run([node("ATK-01", ["all"], where="missing.md §1")], [])
        assert "W11 ATK-01: `where` names a document that does not resolve: missing.md" in out
        assert code == 1

    def test_a_missing_section_is_an_error(self):
        code, out = run([node("ATK-01", ["all"], where="spec.md §1.3")], [])
        assert "W11 ATK-01: `where` cites a section no heading starts with: §1.3" in out
        assert code == 1
        code, out = run([node("ATK-01", ["all"], where="spec.md §1.2")], [])
        assert "W11" not in out

    def test_a_missing_id_is_an_error_and_prose_is_not_read(self):
        code, out = run([node("ATK-01", ["all"], where="spec.md §1 ATK-02 (the second threat)")], [])
        assert "W11 ATK-01: `where` cites an ID the document does not contain: ATK-02" in out
        assert out.count("W11") == 1      # the prose words are not looked up
        assert code == 1
        code, out = run([node("ATK-01", ["all"], where="spec.md §1.2/ATK-01")], [])
        assert "W11" not in out           # an ID after the slash is an ID, not a section

    def test_a_bold_lead_and_a_numbered_item_are_sections(self):
        code, out = run([node("ATK-01", ["all"], where="spec.md §8.3; spec.md §7.2")], [])
        assert "W11" not in out
        code, out = run([node("ATK-01", ["all"], where="spec.md §8.4")], [])
        assert "W11 ATK-01: `where` cites a section no heading starts with: §8.4" in out
        code, out = run([node("ATK-01", ["all"], where="spec.md §7.3")], [])
        assert "W11 ATK-01: `where` cites a section no heading starts with: §7.3" in out
        code, out = run([node("ATK-01", ["all"], where="spec.md §1.1")], [])   # an item counts under its own heading
        assert "§1.1" in out

    def test_no_document_named_is_a_warning(self):
        code, out = run([node("ATK-01", ["all"], where="implicit")], [])
        assert "WARN  W11 ATK-01: `where` names no document" in out
        assert code == 0

    def test_an_alias_a_folder_and_a_prefix_resolve(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "design.md").write_text("# A\n\n## 4. Four\n\n### 4.11 Eleven\n")
            (root / "notes" / "parts").mkdir(parents=True)
            (root / "notes" / "parts" / "part-10-testing.md").write_text("# P\n\n### 10.A — Catalog\n")
            (root / "notes" / "parts" / "part-00").mkdir()
            (root / "notes" / "parts" / "part-00" / "README.md").write_text("# R\n\nREQ-08 sizes\n")
            (root / "notes" / "parts" / "part-03").mkdir()
            (root / "notes" / "parts" / "part-03" / "n3-m.md").write_text("# M\n\n## 1. One\n")
            (root / "notes" / "parts" / "part-03" / "n3-m" / "log").mkdir(parents=True)
            (root / "notes" / "parts" / "part-03" / "n3-m" / "log" / "22.md").write_text("## 22. B\n")
            nodes = [node("ATK-01", ["all"], where="design.md §4.11/§4"),
                     node("ATK-02", ["all"], where="notes/parts/part-10 §10.A"),
                     node("ATK-03", ["all"], where="notes/parts/part-00 REQ-08"),
                     node("ATK-04", ["all"], where="notes/parts/part-03/n3-m §22")]
            forms = dict(META["where_forms"], folder_files=["README.md", "log/*.md"])
            meta = dict(META, orphan_ok={}, where_aliases={"design.md": "docs/design.md"}, where_forms=forms)
            p = write(meta, nodes, [], d)
            code, out = call(["lint", "--registry", str(p)])
            assert "W11" not in out
            # a copy of the registry elsewhere resolves under --root, as the batch tool's copies do
            with tempfile.TemporaryDirectory() as d2:
                p2 = write(meta, nodes, [], d2)
                assert "W11 ATK-02" in call(["lint", "--registry", str(p2)])[1]
                assert "W11" not in call(["lint", "--registry", str(p2), "--root", str(root)])[1]
            # the alias is read from meta: without it, design.md does not resolve
            p = write(dict(META, orphan_ok={}, where_aliases={}), nodes[:1], [], d)
            code, out = call(["lint", "--registry", str(p)])
            assert "W11 ATK-01: `where` names a document that does not resolve: design.md" in out


class TestDraw:
    def test_draw_prints_the_neighbourhood_with_relations_and_outcomes(self):
        nodes = [node("GOAL-01", ["all"]), node("ASM-01", ["all"]), node("ATK-01", ["all"]), node("REQ-01", ["all"]),
                 node("DEC-x", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01"), edge("GOAL-01", "mitigates", "ATK-01"),
                 edge("ATK-01", "obstructs", "REQ-01"), edge("DEC-x", "satisfies", "REQ-01")]
        out = graph(nodes, edges, "draw", "GOAL-01", "--depth", "1")
        assert "graph LR" in out
        assert "GOAL_01 -->|requires| ASM_01" in out
        assert "GOAL_01 -->|mitigates| ATK_01" in out
        assert "REQ_01" not in out            # two edges away: outside depth 1
        assert "assumption: holds" in out      # ASM-01, taken as given
        out = graph(nodes, edges, "draw", "GOAL-01", "--dot")
        assert "digraph" in out
        assert '"ATK-01" -> "REQ-01" [label="obstructs"]' in out   # depth 2 reaches it
        assert '"DEC-x"' not in out                                  # three edges away
        out = graph(nodes, edges, "draw", "GOAL-01", "--dot", "--depth", "3")
        assert '"DEC-x" -> "REQ-01" [label="satisfies"]' in out


class TestEdgeWhy:
    def test_show_prints_an_edge_why(self):
        nodes = [node("GOAL-01", ["all"]), node("ASM-01", ["all"])]
        edges = [edge("GOAL-01", "requires", "ASM-01", why="the goal leans on the assumption")]
        assert "why: the goal leans on the assumption" in graph(nodes, edges, "show", "GOAL-01")
        assert "why: the goal leans on the assumption" in graph(nodes, edges, "why", "GOAL-01")
        code, out = run(nodes, edges, "--today", "2024-06-01")
        assert code == 0, out


class TestWhereFormsFromMeta:
    """What counts as an ID and which files a folder reads are the registry's data, not the lint's."""

    def test_the_id_form_is_read_from_meta(self):
        nodes = [node("ATK-01", ["all"], where="spec.md §1 #12")]
        code, out = run(nodes, [])
        assert "W11" not in out                                # by default '#12' is prose
        forms = dict(META["where_forms"], id=r"^#[0-9]+$")
        code, out = run(nodes, [], where_forms=forms)
        assert "W11 ATK-01: `where` cites an ID the document does not contain: #12" in out
        code, out = run([node("ATK-01", ["all"], where="spec.md §1 #7")], [], where_forms=forms)
        assert "W11" not in out

    def test_the_files_a_folder_reads_are_read_from_meta(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "notes" / "log").mkdir(parents=True)
            (Path(d) / "notes" / "README.md").write_text("# Notes\n\n## 1. One\n")
            (Path(d) / "notes" / "log" / "5.md").write_text("## 5. Five\n")
            nodes = [node("ATK-01", ["all"], where="notes/ §5")]
            p = write(dict(META, orphan_ok={}), nodes, [], d)
            assert "W11 ATK-01: `where` cites a section no heading starts with: §5" in call(["lint", "--registry", str(p)])[1]
            forms = dict(META["where_forms"], folder_files=["README.md", "log/*.md"])
            p = write(dict(META, orphan_ok={}, where_forms=forms), nodes, [], d)
            assert "W11" not in call(["lint", "--registry", str(p)])[1]
