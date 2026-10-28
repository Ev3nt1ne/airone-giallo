"""The two shipped profiles: `init` writes them; an empty one lints clean; the README's example lints clean in the
lite profile and, unchanged, under the full profile's meta (a lite graph grows into a full one without migration)."""
import re
import tempfile
from pathlib import Path

import yaml

from specgraph import cli
from helpers import call

README = Path(__file__).resolve().parent.parent / "README.md"


def readme_block(name):
    """The fenced block of the README that follows the line naming a file ('<name>:')."""
    m = re.search(r"`" + re.escape(name) + r"`[^\n]*\n+```[a-z]*\n(.*?)```", README.read_text(), re.S)
    assert m, f"no block for {name} in the README"
    return m.group(1)


def test_init_writes_each_profile_and_it_lints_clean(tmp_path):
    for profile in ("lite", "full"):
        p = tmp_path / f"{profile}.yml"
        code, out = call(["init", "--profile", profile, "--graph", str(p)])
        assert code == 0 and p.exists()
        assert yaml.safe_load(p.read_text())["meta"]["profile"] == profile
        code, out = call(["lint", "--graph", str(p)])
        assert code == 0 and "0 error(s), 0 warning(s)" in out, out


def test_init_never_overwrites(tmp_path):
    p = tmp_path / "graph.yml"
    p.write_text("keep me")
    code, out = call(["init", "--graph", str(p)])
    assert code == 1 and p.read_text() == "keep me"


def test_the_lite_profile_is_a_subset_of_the_full_one():
    lite = yaml.safe_load(cli.profile_text("lite"))["meta"]
    full = yaml.safe_load(cli.profile_text("full"))["meta"]
    for key in ("prefixes", "assertion_kinds", "other_kinds", "supports", "domain_kinds"):
        assert set(lite[key]) <= set(full[key]), key
    for rel, ends in lite["relations"].items():
        for side in ("from", "to"):
            assert set(ends[side]) <= set(full["relations"][rel][side]) | ({"assertion"} & set(ends[side])), rel


def _readme_registry(d, meta):
    nodes_edges = yaml.safe_load(readme_block("nodes and edges"))
    reg = Path(d) / "graph.yml"
    text = "meta: " + yaml.safe_dump(meta, default_flow_style=True, width=10**6)
    text += readme_block("nodes and edges")
    reg.write_text(text)
    (Path(d) / "design.md").write_text(readme_block("design.md"))
    return reg, nodes_edges


def test_the_readme_example_lints_clean_in_lite_and_full():
    for profile in ("lite", "full"):
        meta = yaml.safe_load(cli.profile_text(profile))["meta"]
        with tempfile.TemporaryDirectory() as d:
            reg, data = _readme_registry(d, meta)
            assert len(data["nodes"]) == 5
            call(["lint", "--graph", str(reg), "--fix"])
            code, out = call(["lint", "--graph", str(reg), "--today", "2026-11-01"])
            assert code == 0 and "0 error(s), 0 warning(s)" in out, (profile, out)
            assert "0 assertion(s) fail somewhere, 0 more not argued yet somewhere; 0 threat(s) undefended" in out
            code, out = call(["lint", "--graph", str(reg), "--what-if", "ASM-01", "--today", "2026-11-01"])
            assert "UNSATISFIED — every satisfier lost (DEC-journal)" in out, out
