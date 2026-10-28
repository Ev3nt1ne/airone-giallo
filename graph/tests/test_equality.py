"""Proof of equality against a reference graph file, run only when the two variables below are set.

    SPECGRAPH_EQUALITY_REGISTRY   a graph file
    SPECGRAPH_EQUALITY_CONFIG     a YAML file: `axes` (the axes to read the graph file with), `meta` (keys that replace
                                  the graph file's own), `root` (where `where` resolves), `today` (for L-9), and
                                  `reference` (a JSON file with what another implementation computed on the same file)

The reference holds the places, every node's outcome and reasons on every place, the lint's findings and, when
present, the cascade of every node. This module compares; it knows nothing of where the reference came from.
"""
import datetime
import json
import os
from pathlib import Path

import pytest
import yaml

from specgraph.lint import engine_summary, run_lint
from specgraph.graph_file import load

GRAPH_PATH = os.environ.get("SPECGRAPH_EQUALITY_REGISTRY")
CFG = os.environ.get("SPECGRAPH_EQUALITY_CONFIG")
pytestmark = pytest.mark.skipif(not (GRAPH_PATH and CFG),
                                reason="SPECGRAPH_EQUALITY_REGISTRY and SPECGRAPH_EQUALITY_CONFIG unset")


@pytest.fixture(scope="module")
def case():
    cfg = yaml.safe_load(Path(CFG).read_text())
    meta, nodes, edges = load(GRAPH_PATH)
    meta = dict(meta)
    meta.update(cfg.get("meta") or {})
    meta["axes"] = cfg.get("axes") or []
    today = datetime.date.fromisoformat(str(cfg["today"])) if cfg.get("today") else None
    res = run_lint(meta, nodes, edges, root=Path(cfg["root"]), today=today)
    ref = json.loads(Path(cfg["reference"]).read_text())
    return res, ref


def test_same_places(case):
    res, ref = case
    assert res.logic.elements == ref["places"]


def test_same_outcome_for_every_node_on_every_place(case):
    res, ref = case
    lg = res.logic
    mine = {n: {e: lg.outcome(n, e) for e in lg.elements} for n in sorted(lg.byid)}
    diff = [(n, e, ref["outcomes"].get(n, {}).get(e), o) for n, row in mine.items() for e, o in row.items()
            if ref["outcomes"].get(n, {}).get(e) != o]
    assert not diff, f"{len(diff)} (node, place) pairs differ, first: {diff[:5]}"
    assert set(mine) == set(ref["outcomes"])


def test_same_reasons(case):
    res, ref = case
    lg = res.logic
    diff = [(n, e) for n in sorted(lg.byid) for e in lg.elements
            if lg.why_not(n, e) != ref["why_not"].get(n, {}).get(e, [])]
    assert not diff, f"{len(diff)} (node, place) pairs give other reasons, first: {diff[:5]}"


def test_same_lint_findings(case):
    res, ref = case
    assert sorted(res.errors) == sorted(ref["errors"])
    assert sorted(res.warnings) == sorted(ref["warnings"])
    assert {k: sorted(v) for k, v in res.backfill.items()} == {k: sorted(v) for k, v in ref["backfill"].items()}
    assert engine_summary(res.logic) == ref["summary"]


def test_same_cascades(case):
    res, ref = case
    if "what_if" not in ref:
        pytest.skip("the reference carries no cascades")
    lg = res.logic
    diff = []
    for nid, want in ref["what_if"].items():
        got = lg.what_if({nid})
        got = {s: {n: {r: sorted(es) for r, es in rs.items()} for n, rs in v.items()} for s, v in got.items()}
        if got != want:
            diff.append(nid)
    assert not diff, f"{len(diff)} cascades differ, first: {diff[:5]}"
