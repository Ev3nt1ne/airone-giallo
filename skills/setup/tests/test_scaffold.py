"""Tests for scaffold.py, each on a throwaway project folder made by pytest.

Run from the repository's root: pytest skills/setup/tests
The full install needs `specgraph` importable (pip install -e graph); without it that test is skipped, and the test
of the graph step's refusal still runs.
"""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCAFFOLD = HERE.parent / "scaffold.py"
_spec = importlib.util.spec_from_file_location("scaffold", SCAFFOLD)
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)

# The full install: every piece, every map row, every optional rule. Invented values.
FULL = {
    "name": "Inkwell", "purpose": "a note editor whose saved notes survive a crash, for people who write offline",
    "invariants": ["a saved note survives a crash: otherwise silent data loss"], "mode": "hands-on",
    "layout": "umbrella", "graph": "lite", "status": True,
    "families": {"APP": "the application", "DOC": "the documentation"}, "handoff": True,
    "outward": "free", "attribution": "Co-Authored-By: An Agent <agent@example.com>",
    "reserved": ["the file format", "anything that changes the save path"], "opinionated": True,
    "claude_code_version": "2.9.0", "model": "example-model-1", "spec": "`docs/design.md`",
    "plan": "`docs/plan.md`; gates `G1` to `G3`", "glossary": "`docs/glossary.md`", "findings": "`docs/findings/`",
    "owner_notes": "`notes/`", "frozen": ["docs/archive/"], "copies": ["vendor/"], "checks": "`pytest`",
    "prune_after": "three months",
    "machine": {"resources": "8 cores, 16 GB", "load": "nothing else", "limits": "one run at a time",
                "timings": "yes"},
}
MINIMAL = {"name": "Inkwell", "purpose": "a small note editor", "mode": "hands-off", "status": False,
           "handoff": False}

HANDS_ON_ONLY = ("After building, list the choices", "Never narrow the scope",
                 "bring both rationales, the code's and the tool's", "Before adding beside what exists")
HANDS_OFF_ONLY = ("The owner sets the direction and seldom the detail",)


def install(folder, answers, *flags, capsys=None):
    path = folder.parent / f"{folder.name}-answers.json"
    path.write_text(json.dumps(answers), encoding="utf-8")
    rc = sc.main(["--answers", str(path), "--target", str(folder), *flags])
    out = capsys.readouterr().out if capsys else ""
    return rc, out


def project(tmp_path, name="project"):
    folder = tmp_path / name
    folder.mkdir()
    return folder


def tree(folder):
    """Every file under the folder with its bytes: what a run that writes nothing must leave equal."""
    return {p.relative_to(folder): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def dead_links(folder):
    """The dead-link check of markdown-docs §6: every relative link target outside a fenced block must exist."""
    dead = []
    for md in folder.rglob("*.md"):
        fenced = False
        for line in md.read_text(encoding="utf-8").splitlines():
            if re.match(r"^ *```", line):
                fenced = not fenced
                continue
            if fenced:
                continue
            for target in re.findall(r"\]\(([^)]+)\)", line):
                target = re.split(r"[ #]", target)[0]
                if not target or re.match(r"^[a-z]+:", target):
                    continue
                if not (md.parent / target).exists():
                    dead.append(f"{md.relative_to(folder)} -> {target}")
    return dead


def agents(folder):
    return (folder / "AGENTS.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- whole installs

def test_full_install_writes_every_piece_and_passes_its_own_checks(tmp_path, capsys):
    pytest.importorskip("specgraph")
    folder = project(tmp_path)
    rc, out = install(folder, FULL, capsys=capsys)
    assert rc == 0, out
    for rel in ("AGENTS.md", "CLAUDE.md", "RATIONALE.md", "local-machine.md", ".gitignore", "docs/status.md",
                "docs/closed.md", "tools/check_status.py", "handoff/current.md", "handoff/log-stage-1.md",
                "graph.yml"):
        assert (folder / rel).is_file(), rel
    assert (folder / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix in (".md", ".yml", ""):
            assert "{{" not in path.read_text(encoding="utf-8"), path
    checker = subprocess.run([sys.executable, "tools/check_status.py", "docs/status.md", "docs/closed.md",
                              "--graph", "graph.yml"], cwd=folder, capture_output=True, text=True)
    assert checker.returncode == 0, checker.stdout + checker.stderr
    assert "APP-001" in checker.stdout and "DOC-001" in checker.stdout
    lint = subprocess.run([sys.executable, "-m", "specgraph", "lint"], cwd=folder, capture_output=True, text=True)
    assert lint.returncode == 0 and "0 error(s)" in lint.stdout, lint.stdout + lint.stderr
    assert dead_links(folder) == []
    text = agents(folder)
    for row in ("`docs/design.md`", "`docs/status.md`", "`handoff/current.md`", "`docs/glossary.md`",
                "`docs/findings/`", "`APP`, `DOC`", "`specgraph lint`", "--graph graph.yml", "`pytest`"):
        assert row in text, row
    assert "[to fill" not in text


def test_minimal_install_writes_only_the_core(tmp_path, capsys):
    folder = project(tmp_path)
    rc, out = install(folder, MINIMAL, capsys=capsys)
    assert rc == 0, out
    written = sorted(str(p) for p in tree(folder))
    assert written == [".gitignore", "AGENTS.md", "CLAUDE.md", "RATIONALE.md", "local-machine.md"]
    text = agents(folder)
    for absent in ("status.md", "handoff/", "specgraph", "graph.yml", "Identifier"):
        assert absent not in text, absent
    assert dead_links(folder) == []


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_the_machine_file_is_ignored_by_git(tmp_path, capsys):
    folder = project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=folder, check=True)
    rc, _ = install(folder, MINIMAL, capsys=capsys)
    assert rc == 0
    ignored = subprocess.run(["git", "check-ignore", "local-machine.md"], cwd=folder, capture_output=True, text=True)
    assert ignored.stdout.strip() == "local-machine.md"


# ---------------------------------------------------------------- what the answers change

def test_hands_on_and_hands_off_write_different_rules(tmp_path, capsys):
    on, off = project(tmp_path, "on"), project(tmp_path, "off")
    assert install(on, dict(MINIMAL, mode="hands-on"), capsys=capsys)[0] == 0
    assert install(off, dict(MINIMAL, mode="hands-off"), capsys=capsys)[0] == 0
    on_text, off_text = " ".join(agents(on).split()), " ".join(agents(off).split())
    for phrase in HANDS_ON_ONLY:
        assert phrase in on_text and phrase not in off_text, phrase
    for phrase in HANDS_OFF_ONLY:
        assert phrase in off_text and phrase not in on_text, phrase


def test_an_umbrella_gets_the_rule_on_sides_and_one_repository_does_not(tmp_path, capsys):
    single, umbrella = project(tmp_path, "single"), project(tmp_path, "umbrella")
    install(single, MINIMAL, capsys=capsys)
    install(umbrella, dict(MINIMAL, layout="umbrella"), capsys=capsys)
    assert "gets its side" not in agents(single)
    assert "gets its side" in agents(umbrella)
    assert "private side" in (umbrella / "RATIONALE.md").read_text()


def test_outward_acts_gated_or_free_with_the_trailer(tmp_path, capsys):
    gated, free = project(tmp_path, "gated"), project(tmp_path, "free")
    install(gated, MINIMAL, capsys=capsys)
    install(free, dict(MINIMAL, outward="free", attribution="Signed-off-by: Someone"), capsys=capsys)
    g, f = " ".join(agents(gated).split()), " ".join(agents(free).split())
    assert "handed to the owner, who sends them" in g and "and reported" not in g
    assert "`Signed-off-by: Someone` and reported" in f and "handed to the owner" not in f


def test_the_opinionated_layer_is_off_unless_asked(tmp_path, capsys):
    plain, off_mode, on_mode = (project(tmp_path, n) for n in ("plain", "off", "on"))
    install(plain, MINIMAL, capsys=capsys)
    install(off_mode, dict(MINIMAL, opinionated=True), capsys=capsys)
    install(on_mode, dict(MINIMAL, opinionated=True, mode="hands-on"), capsys=capsys)
    assert "kit author's rules" not in agents(plain)
    assert "kit author's rules" in agents(off_mode) and "Comments state invariants" not in agents(off_mode)
    assert "Comments state invariants" in agents(on_mode)


def test_an_unanswered_slot_is_visible_and_an_answered_one_is_filled(tmp_path, capsys):
    bare, told = project(tmp_path, "bare"), project(tmp_path, "told")
    install(bare, MINIMAL, capsys=capsys)
    install(told, dict(MINIMAL, claude_code_version="2.9.0", model="example-model-1"), capsys=capsys)
    assert "Claude Code [to fill: version] and model [to fill: model]" in " ".join(agents(bare).split())
    assert "Claude Code 2.9.0 and model example-model-1" in " ".join(agents(told).split())
    assert "[to fill: cores" in (bare / "local-machine.md").read_text()


# ---------------------------------------------------------------- the file's shape

def test_the_first_rule_is_challenge_correct_confirm(tmp_path, capsys):
    folder = project(tmp_path)
    install(folder, MINIMAL, capsys=capsys)
    rules = [ln for ln in agents(folder).splitlines() if ln.startswith(("- ", "**"))]
    assert rules[0].startswith("**Challenge, correct, confirm.**")


def test_no_prose_line_is_longer_than_the_kit_width(tmp_path, capsys):
    folder = project(tmp_path)
    install(folder, dict(FULL, graph="none"), capsys=capsys)
    for name in ("AGENTS.md", "RATIONALE.md"):
        for line in (folder / name).read_text().splitlines():
            if not line.startswith("|"):
                assert len(line) <= sc.WIDTH, line


# ---------------------------------------------------------------- what the script refuses

def test_a_dry_run_writes_nothing(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / ".gitignore").write_text("build/\n")
    before = tree(folder)
    rc, out = install(folder, FULL, "--dry-run", capsys=capsys)
    assert rc == 0, out
    assert tree(folder) == before
    assert "WOULD    AGENTS.md" in out and "nothing was written" in out


def test_an_existing_file_stops_the_whole_run(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / "AGENTS.md").write_text("the project's own rules\n")
    before = tree(folder)
    rc, out = install(folder, MINIMAL, capsys=capsys)
    assert rc == 1
    assert "REFUSED" in out and "AGENTS.md" in out
    assert tree(folder) == before


def test_force_replaces_the_instructions_and_keeps_the_records(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / "AGENTS.md").write_text("old rules\n")
    (folder / "docs").mkdir()
    (folder / "docs" / "status.md").write_text("a status file full of items\n")
    rc, out = install(folder, dict(MINIMAL, status=True, families={"APP": "the application"}), "--force",
                      capsys=capsys)
    assert rc == 0, out
    assert agents(folder).startswith("# Inkwell")
    assert (folder / "docs" / "status.md").read_text() == "a status file full of items\n"
    assert re.search(r"KEPT +docs/status.md", out)


def test_the_graph_step_is_reported_skipped_when_specgraph_is_missing(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sc, "specgraph_available", lambda: False)
    folder = project(tmp_path)
    rc, out = install(folder, dict(MINIMAL, graph="lite"), capsys=capsys)
    assert rc == 1
    assert re.search(r"SKIPPED +graph.yml", out) and "SETUP INCOMPLETE" in out
    assert not (folder / "graph.yml").exists()


def test_the_gitignore_line_is_appended_once(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / ".gitignore").write_text("build/")  # no final newline
    install(folder, MINIMAL, capsys=capsys)
    install(folder, MINIMAL, "--force", capsys=capsys)
    lines = (folder / ".gitignore").read_text().splitlines()
    assert lines[0] == "build/"
    assert lines.count("/local-machine.md") == 1


def test_a_flag_overrides_the_answers_file(tmp_path, capsys):
    folder = project(tmp_path)
    rc, _ = install(folder, dict(MINIMAL, mode="hands-off"), "--mode", "hands-on", capsys=capsys)
    assert rc == 0
    assert HANDS_ON_ONLY[0] in " ".join(agents(folder).split())


@pytest.mark.parametrize("bad", [
    {"status": True, "families": {}},
    {"status": True, "families": {"app": "lower case"}},
    {"attribution": "Signed-off-by: x"},
    {"mode": "both"},
    {"name": 7},
    {"handoff": "no"},
])
def test_invalid_answers_exit_two_and_write_nothing(tmp_path, capsys, bad):
    folder = project(tmp_path)
    rc, _ = install(folder, dict(MINIMAL, **bad), capsys=capsys)
    assert rc == 2
    assert tree(folder) == {}


# ---------------------------------------------------------------- the template syntax

def test_render_values_sections_and_standalone_tags():
    text = "a {{x}}\n{{#on}}\nkept\n{{/on}}\n{{#off}}\ndropped\n{{/off}}\n{{^off}}inverse{{/off}} {{items}}\n"
    assert sc.render(text, {"x": "1", "on": True, "off": "", "items": ["p", "q"]}) == "a 1\nkept\ninverse p, q\n"


def test_render_refuses_a_slot_with_no_answer():
    with pytest.raises(KeyError):
        sc.render("{{missing}}", {})
    with pytest.raises(KeyError):
        sc.render("{{#missing}}x{{/missing}}", {})
