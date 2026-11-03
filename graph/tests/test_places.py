"""Places from axes: none, one, two; the cell, interface and transition forms; and how a domain covers a place."""
import pytest

from specgraph.engine import read_as_logic
from specgraph.places import ALL, DomainError, Grid
from helpers import AXES, LITE

ZONE = {"name": "zone", "values": ["Z1", "Z2", "Z3"], "interfaces": True}
STAGE = {"name": "stage", "values": ["DEV", "BETA", "PROD", "SCALE"], "ordered": True}


class TestZeroAxes:
    def test_one_place(self):
        g = Grid([])
        assert g.places() == {ALL}
        assert g.everywhere() == {ALL}
        assert g.domain(["all"]) == {ALL}
        with pytest.raises(DomainError):
            g.domain(["Z1"])

    def test_the_engine_is_the_plain_holding_rule(self):
        # no axes, no domains: a requirement holds when its satisfier and what it requires hold, and an obstructing
        # threat is defended
        meta = dict(LITE)
        nodes = [{"id": "REQ-01", "kind": "requirement", "support": "satisfier"},
                 {"id": "DEC-daylight", "kind": "decision", "support": "chosen"},
                 {"id": "ASM-01", "kind": "assumption", "support": "given"},
                 {"id": "ATK-01", "kind": "threat"},
                 {"id": "DEC-blind-stop", "kind": "decision", "support": "chosen"}]
        edges = [{"from": "DEC-daylight", "type": "satisfies", "to": "REQ-01"},
                 {"from": "REQ-01", "type": "requires", "to": "ASM-01"},
                 {"from": "ATK-01", "type": "obstructs", "to": "REQ-01"}]
        lg = read_as_logic(meta, nodes, edges)
        assert lg.elements == [ALL]
        assert lg.outcome("REQ-01", ALL) == "not argued yet"          # the threat has no defender yet
        lg = read_as_logic(meta, nodes, edges + [{"from": "DEC-blind-stop", "type": "mitigates", "to": "ATK-01"}])
        assert lg.outcome("REQ-01", ALL) == "holds"
        assert lg.outcome("ATK-01", ALL) == "defended"


class TestOneAxis:
    def test_ordered(self):
        g = Grid([dict(STAGE)])
        assert g.everywhere() == {"DEV", "BETA", "PROD", "SCALE"}
        assert g.places() - g.everywhere() == {"DEV>BETA", "BETA>PROD", "PROD>SCALE"}
        assert g.domain(["*"]) == g.everywhere()
        assert g.sides("BETA>PROD") == {"BETA", "PROD"}

    def test_interfaces(self):
        g = Grid([dict(ZONE)])
        assert g.places() - g.everywhere() == {"Z1~Z2", "Z1~Z3", "Z2~Z3"}
        assert g.domain(["Z3~Z1"]) == {"Z1~Z3"}                     # written either way, named low to high

    def test_neither(self):
        g = Grid([{"name": "edition", "values": ["FREE", "PRO"]}])
        assert g.places() == {"FREE", "PRO"}
        with pytest.raises(DomainError):
            g.domain(["FREE~PRO"])
        with pytest.raises(DomainError):
            g.domain(["FREE>PRO"])


class TestTwoAxes:
    def test_a_three_by_four_grid_with_interfaces_and_an_ordered_axis_has_33_places(self):
        g = Grid(AXES)
        places = g.places()
        cells = g.everywhere()
        assert len(cells) == 12
        assert len({p for p in places if "~" in p}) == 12            # 3 pairs of zones on each of 4 stages
        assert len({p for p in places if ">" in p}) == 9             # 3 steps up for each of 3 zones
        assert len(places) == 33

    def test_axis_order_names_the_cell(self):
        g = Grid([STAGE, ZONE])                                       # the same axes, the other order
        assert "BETA.Z2" in g.everywhere()
        assert "BETA.Z1~BETA.Z2" in g.places()
        assert "BETA.Z2>PROD" in g.places()
        assert g.sides("BETA.Z2>PROD") == {"BETA.Z2", "PROD.Z2"}
        assert len(g.places()) == 33

    def test_wildcards(self):
        g = Grid(AXES)
        assert g.domain(["Z2.*"]) == {"Z2.DEV", "Z2.BETA", "Z2.PROD", "Z2.SCALE"}
        assert g.domain(["*.BETA"]) == {"Z1.BETA", "Z2.BETA", "Z3.BETA"}
        assert g.domain(["all"]) == g.everywhere()

    def test_a_value_names_one_axis(self):
        with pytest.raises(DomainError):
            Grid([{"name": "a", "values": ["X", "Y"]}, {"name": "b", "values": ["Y", "Z"]}])


class TestInterfaceForms:
    g = Grid(AXES)

    def test_an_interface_joins_two_values_of_the_interfaces_axis_on_the_same_other_values(self):
        assert self.g.domain(["Z1.PROD~Z2.PROD"]) == {"Z1.PROD~Z2.PROD"}
        assert self.g.domain(["Z2.PROD~Z1.PROD"]) == {"Z1.PROD~Z2.PROD"}
        assert self.g.domain(["Z1.*~Z2.*"]) == {f"Z1.{s}~Z2.{s}" for s in ("DEV", "BETA", "PROD", "SCALE")}

    @pytest.mark.parametrize("tok, says", [
        ("Z1.PROD~Z1.PROD", "an interface joins two different zones"),
        ("*.PROD~Z2.PROD", "an interface joins two different zones"),
        ("Z1.BETA~Z2.PROD", "an interface stays on one stage"),
        ("Z1.BETA~Z1.PROD", "an interface joins two different zones"),     # stage has no interfaces
    ])
    def test_malformed(self, tok, says):
        with pytest.raises(DomainError, match=says):
            self.g.domain([tok])

    def test_covers(self):
        d = self.g.domain(["Z2.PROD"])
        assert self.g.covers(d, "Z1.PROD~Z2.PROD")                     # a cell is read on its boundaries
        assert not self.g.covers(d, "Z1.BETA~Z2.BETA")
        assert self.g.covers(self.g.domain(["Z1.PROD~Z2.PROD"]), "Z2.PROD")   # a boundary rule on either side
        assert not self.g.covers(self.g.domain(["Z1.PROD~Z2.PROD"]), "Z3.PROD")


class TestTransitionForms:
    g = Grid(AXES)

    def test_a_transition_moves_one_value_up_an_ordered_axis(self):
        assert self.g.domain(["Z2.BETA>PROD"]) == {"Z2.BETA>PROD"}
        assert self.g.domain(["*.BETA>PROD"]) == {"Z1.BETA>PROD", "Z2.BETA>PROD", "Z3.BETA>PROD"}
        assert self.g.sides("Z2.BETA>PROD") == {"Z2.BETA", "Z2.PROD"}

    @pytest.mark.parametrize("tok", ["Z2.PROD>BETA", "Z2.DEV>PROD", "Z2.*>PROD", "Z2.BETA>Z3", "Z2.BETA>NOPE"])
    def test_malformed(self, tok):
        with pytest.raises(DomainError, match="a transition joins two adjacent"):
            self.g.domain([tok])

    def test_covers(self):
        assert self.g.covers(self.g.domain(["Z2.BETA"]), "Z2.BETA>PROD")
        assert self.g.covers(self.g.domain(["Z2.PROD"]), "Z2.BETA>PROD")
        assert not self.g.covers(self.g.domain(["Z1.PROD"]), "Z2.BETA>PROD")
        assert self.g.covers(self.g.domain(["Z2.BETA>PROD"]), "Z2.PROD")
