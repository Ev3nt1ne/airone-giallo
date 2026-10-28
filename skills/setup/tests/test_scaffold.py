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

# The full install: every piece, every map row, every optional rule, in the default two-repository form with the
# contributors' file. Invented values.
FULL = {
    "name": "Inkwell", "purpose": "a note editor whose saved notes survive a crash, for people who write offline",
    "invariants": ["a saved note survives a crash: otherwise silent data loss"], "mode": "four-hands",
    "cut": "plan", "agent_layer": "both", "graph": "lite", "status": True,
    "families": {"APP": "the application", "DOC": "the documentation"}, "handoff": True,
    "outward": "free", "attribution": "Co-Authored-By: An Agent <agent@example.com>",
    "reserved": ["the file format", "anything that changes the save path"], "opinionated": True,
    "claude_code_version": "2.9.0", "model": "example-model-1", "spec": "`inkwell/docs/design.md`",
    "plan": "`inkwell/plan/plan.md`; milestones `M1` to `M3`", "frozen": ["inkwell/docs/old/"],
    "copies": ["inkwell/vendor/"], "checks": "`pytest`", "prune_after": "three months",
    "machine": {"resources": "8 cores, 16 GB", "load": "nothing else", "limits": "one run at a time",
                "timings": "yes"},
}
# One private repository, nothing optional: no git needed, nothing nested.
MINIMAL = {"name": "Inkwell", "purpose": "a small note editor", "mode": "conductor", "cut": "none", "status": False,
           "handoff": False}
FAMILIES = {"APP": "the application"}

FOUR_HANDS_ONLY = ("After building, list the choices", "Never narrow the scope",
                   "bring both rationales, the code's and the tool's", "Before adding beside what exists")
CONDUCTOR_ONLY = ("The owner sets the direction and seldom the detail",)
# Every record the scaffold may write, from the workspace root of a one-repository install.
RECORDS = ("RATIONALE.md", "ai-docs/README.md", "ai-docs/status.md", "ai-docs/closed.md", "ai-docs/handoff/current.md",
           "ai-docs/handoff/log-stage-1.md", "ai-docs/design/README.md", "ai-docs/findings/README.md",
           "ai-docs/guides/README.md", "archive/README.md", "human-docs/README.md", "sources/README.md", "graph.yml")
# The file that shows where each rung landed.
RUNG_FILE = {"docs": "docs/README.md", "plan": "plan/README.md", "ai-docs": "ai-docs/status.md",
             "archive": "archive/README.md"}

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


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


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def workspace(tmp_path, name="nido", public="inkwell"):
    """A private workspace that is a git repository, with the public repository's folder a work tree of its own, as
    `git submodule add` leaves it."""
    root = project(tmp_path, name)
    git("init", "-q", cwd=root)
    (root / public).mkdir()
    git("init", "-q", cwd=root / public)
    (root / ".gitmodules").write_text(f'[submodule "{public}"]\n\tpath = {public}\n\turl = ../{public}.git\n')
    return root


def tree(folder):
    """Every file under the folder with its bytes, git's own folders aside: what a run that writes nothing must leave
    equal."""
    return {p.relative_to(folder): p.read_bytes() for p in sorted(folder.rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(folder).parts}


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


def flat(text):
    return " ".join(text.split())


# ---------------------------------------------------------------- whole installs

@needs_git
def test_full_install_writes_every_piece_and_passes_its_own_checks(tmp_path, capsys):
    pytest.importorskip("specgraph")
    folder = workspace(tmp_path)
    rc, out = install(folder, FULL, capsys=capsys)
    assert rc == 0, out
    for rel in ("AGENTS.md", "CLAUDE.md", "RATIONALE.md", "local-machine.md", ".gitignore", ".ignore",
                "ai-docs/README.md", "ai-docs/status.md", "ai-docs/closed.md", "ai-docs/handoff/current.md",
                "ai-docs/handoff/log-stage-1.md", "ai-docs/design/README.md", "ai-docs/findings/README.md",
                "ai-docs/guides/README.md", "archive/README.md", "human-docs/README.md", "sources/README.md",
                "inkwell/AGENTS.md", "inkwell/CLAUDE.md", "inkwell/docs/README.md", "inkwell/docs/glossary.md",
                "inkwell/graph.yml", "inkwell/plan/README.md"):
        assert (folder / rel).is_file(), rel
    assert (folder / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    for path in folder.rglob("*"):
        if path.is_file() and ".git" not in path.parts and path.suffix in (".md", ".yml", ""):
            assert "{{" not in path.read_text(encoding="utf-8"), path
    # No kit code is copied into the project: the checks are the kit's commands.
    assert not [p for p in folder.rglob("*.py")]
    checker = subprocess.run([sys.executable, str(sc.KIT / "status" / "tools" / "check_status.py"),
                              "ai-docs/status.md", "ai-docs/closed.md", "--graph", "inkwell/graph.yml"],
                             cwd=folder, capture_output=True, text=True)
    assert checker.returncode == 0, checker.stdout + checker.stderr
    assert "APP-001" in checker.stdout and "DOC-001" in checker.stdout
    lint = subprocess.run([sys.executable, "-m", "specgraph", "lint", "--registry", "inkwell/graph.yml"],
                          cwd=folder, capture_output=True, text=True)
    assert lint.returncode == 0 and "0 error(s)" in lint.stdout, lint.stdout + lint.stderr
    assert dead_links(folder) == []
    text = agents(folder)
    for row in ("`inkwell/docs/design.md`", "`inkwell/graph.yml`", "`ai-docs/status.md`",
                "`ai-docs/handoff/current.md`", "`inkwell/docs/glossary.md`", "`ai-docs/design/`",
                "`ai-docs/findings/`", "`ai-docs/guides/`", "`archive/`", "`human-docs/`", "`sources/README.md`",
                "`APP`, `DOC`", "`specgraph lint --registry inkwell/graph.yml`",
                "`check-status ai-docs/status.md ai-docs/closed.md --graph inkwell/graph.yml`", "`pytest`"):
        assert row in text, row
    assert "[to fill" not in text
    assert "check-status ai-docs/status.md ai-docs/closed.md" in (folder / "ai-docs/status.md").read_text()


def test_minimal_install_writes_only_the_core(tmp_path, capsys):
    folder = project(tmp_path)
    rc, out = install(folder, MINIMAL, capsys=capsys)
    assert rc == 0, out
    written = sorted(str(p) for p in tree(folder))
    assert written == [".gitignore", ".ignore", "AGENTS.md", "CLAUDE.md", "RATIONALE.md", "ai-docs/README.md",
                       "ai-docs/design/README.md", "ai-docs/findings/README.md", "ai-docs/guides/README.md",
                       "archive/README.md", "docs/README.md", "docs/glossary.md", "human-docs/README.md",
                       "local-machine.md", "plan/README.md", "sources/README.md"]
    text = agents(folder)
    for absent in ("status.md", "handoff/", "specgraph", "graph.yml", "Identifier", "check-status"):
        assert absent not in text, absent
    assert dead_links(folder) == []


@needs_git
def test_the_machine_file_is_ignored_by_git(tmp_path, capsys):
    folder = project(tmp_path)
    git("init", "-q", cwd=folder)
    rc, _ = install(folder, MINIMAL, capsys=capsys)
    assert rc == 0
    assert git("check-ignore", "local-machine.md", cwd=folder).stdout.strip() == "local-machine.md"


# ---------------------------------------------------------------- the ladder, the cut and the sides

@needs_git
@pytest.mark.parametrize("cut", sc.CUTS)
def test_the_cut_puts_each_rung_on_its_side(tmp_path, capsys, cut):
    form = sc.form_of(cut)
    folder = workspace(tmp_path) if form == "two" else project(tmp_path)
    rc, out = install(folder, dict(MINIMAL, cut=cut, status=True, families=FAMILIES), capsys=capsys)
    assert rc == 0, out
    last_public = sc.CUTS.index(cut)
    for n, rung in enumerate(sc.RUNGS, start=1):
        if rung not in RUNG_FILE:
            continue
        nested = form == "two" and n <= last_public
        here = folder / "inkwell" / RUNG_FILE[rung] if nested else folder / RUNG_FILE[rung]
        there = folder / RUNG_FILE[rung] if nested else folder / "inkwell" / RUNG_FILE[rung]
        assert here.is_file() and not there.exists(), rung
        if form == "two":
            # A private rung is named in the allowlist; a public one is inside the gitlink and never named.
            assert (f"!/{rung}/" in (folder / ".gitignore").read_text().splitlines()) == (not nested), rung
    for rel in ("AGENTS.md", "CLAUDE.md", "RATIONALE.md", "local-machine.md", ".ignore"):
        assert (folder / rel).is_file() and not (folder / "inkwell" / rel).exists(), rel
    a = dict(sc.DEFAULTS, **MINIMAL)
    a.update(cut=cut, graph="lite")
    sc.validate(a)
    graph = sc.context(a, sc.Layout.of(a), folder)["graph_file"]
    assert graph == ("inkwell/graph.yml" if form == "two" and last_public >= 2 else "graph.yml")
    words = flat(agents(folder))
    expected = {"all": "everything is public", "none": "everything is private"}.get(
        cut, f"the public side ends at {sc.RUNG_NAMES.get(cut)}")
    assert expected in words and "(`doc-discipline` §1)" in words


@needs_git
def test_the_two_repository_form_refuses_without_the_public_repository(tmp_path, capsys):
    answers = dict(MINIMAL, cut="plan")
    missing = project(tmp_path, "missing")
    git("init", "-q", cwd=missing)
    rc, out = install(missing, answers, capsys=capsys)
    assert rc == 1 and "REFUSED" in out and "git submodule add <its URL> inkwell" in out
    assert tree(missing) == {}
    # A plain folder of the workspace is not a repository of its own.
    plain = project(tmp_path, "plain")
    git("init", "-q", cwd=plain)
    (plain / "inkwell").mkdir()
    rc, out = install(plain, answers, capsys=capsys)
    assert rc == 1 and "not a git work tree of its own" in out
    # A nested clone that is a repository of its own but not declared in .gitmodules: the owner ruled submodule, no
    # plain clone, because the workspace must record which public commit its documents refer to.
    nested = project(tmp_path, "nested")
    git("init", "-q", cwd=nested)
    (nested / "inkwell").mkdir()
    git("init", "-q", cwd=nested / "inkwell")
    rc, out = install(nested, answers, capsys=capsys)
    assert rc == 1 and "not a submodule of this workspace" in out and "git submodule add" in out
    assert tree(nested) == {}
    assert tree(plain) == {}
    # The dry run still shows the tree, and says the real run would stop.
    rc, out = install(missing, answers, "--dry-run", capsys=capsys)
    assert rc == 1 and re.search(r"WOULD +inkwell/docs/README.md", out) and "the real run would stop here" in out
    assert tree(missing) == {}


@needs_git
def test_the_private_workspace_gitignore_is_an_allowlist(tmp_path, capsys):
    folder = workspace(tmp_path)
    rc, out = install(folder, dict(MINIMAL, cut="plan", status=True, families=FAMILIES, handoff=True),
                      capsys=capsys)
    assert rc == 0, out
    rules = [ln for ln in (folder / ".gitignore").read_text().splitlines() if ln and not ln.startswith("#")]
    assert rules[0] == "/*"
    assert [ln for ln in rules if "inkwell" in ln] == ["!/inkwell"]
    assert not [ln for ln in rules if "local-machine" in ln]
    (folder / "sources" / "paper.pdf").write_text("bytes")
    (folder / "stray.log").write_text("output")
    for path in ("local-machine.md", "sources/paper.pdf", "stray.log"):
        assert git("check-ignore", "-q", path, cwd=folder).returncode == 0, path
    for path in ("AGENTS.md", "CLAUDE.md", "RATIONALE.md", ".ignore", ".gitignore", "ai-docs/status.md",
                 "ai-docs/handoff/current.md", "archive/README.md", "human-docs/README.md", "sources/README.md",
                 "inkwell"):
        assert git("check-ignore", "-q", path, cwd=folder).returncode == 1, path


def test_the_archive_is_kept_out_of_search_by_dot_ignore(tmp_path, capsys):
    fresh, other = project(tmp_path, "fresh"), project(tmp_path, "other")
    assert install(fresh, MINIMAL, capsys=capsys)[0] == 0
    assert (fresh / ".ignore").read_text() == "archive/\n"
    (other / ".ignore").write_text("target/")  # no final newline
    install(other, MINIMAL, capsys=capsys)
    install(other, MINIMAL, "--force", capsys=capsys)
    assert (other / ".ignore").read_text().splitlines() == ["target/", "archive/"]


def test_the_ai_docs_tree_has_its_five_places_and_their_readmes(tmp_path, capsys):
    folder = project(tmp_path)
    assert install(folder, dict(MINIMAL, status=True, families=FAMILIES, handoff=True), capsys=capsys)[0] == 0
    index = flat((folder / "ai-docs" / "README.md").read_text())
    for name in ("[status.md](status.md)", "[closed.md](closed.md)", "[handoff/](handoff/current.md)",
                 "[design/]", "[findings/]", "[guides/]"):
        assert name in index, name
    for place, question in (("design", "what did we decide, and why?"), ("findings", "what did we observe?"),
                            ("guides", "how do we do x here?")):
        assert question in index.lower(), place
        assert question in flat((folder / "ai-docs" / place / "README.md").read_text()).lower(), place
    for readme in folder.rglob("README.md"):
        assert "<YYYY" not in readme.read_text(), readme
    assert "Frozen." in (folder / "archive" / "README.md").read_text()
    assert dead_links(folder) == []
    bare = project(tmp_path, "bare")
    install(bare, MINIMAL, capsys=capsys)
    assert "status.md" not in (bare / "ai-docs" / "README.md").read_text()


@needs_git
def test_the_sources_manifest_and_its_ignore_lines_on_each_side(tmp_path, capsys):
    one = project(tmp_path, "one")
    install(one, MINIMAL, capsys=capsys)
    manifest = (one / "sources" / "README.md").read_text()
    assert "| URL | Fetched | Licence | Hash | File |" in manifest and "cites the URL" in flat(manifest)
    assert [ln for ln in (one / ".gitignore").read_text().splitlines() if "sources" in ln and not
            ln.startswith("#")] == ["/sources/*", "!/sources/README.md"]
    two = workspace(tmp_path, "two")
    rc, out = install(two, dict(MINIMAL, cut="plan", sources="public", human_docs="public"), capsys=capsys)
    assert rc == 0, out
    assert (two / "inkwell" / "sources" / "README.md").is_file() and not (two / "sources").exists()
    assert (two / "inkwell" / "human-docs" / "README.md").is_file() and not (two / "human-docs").exists()
    root = (two / ".gitignore").read_text()
    assert "sources" not in root and "human-docs" not in root
    public = two / "inkwell"
    (public / "sources" / "paper.pdf").write_text("bytes")
    assert git("check-ignore", "-q", "sources/paper.pdf", cwd=public).returncode == 0
    assert git("check-ignore", "-q", "sources/README.md", cwd=public).returncode == 1


@needs_git
def test_agent_layer_both_writes_a_contributors_file_citing_only_public_rungs(tmp_path, capsys):
    both, private = workspace(tmp_path, "both"), workspace(tmp_path, "private")
    answers = dict(MINIMAL, cut="plan", status=True, families=FAMILIES, handoff=True, checks="`pytest`")
    assert install(both, dict(answers, agent_layer="both"), capsys=capsys)[0] == 0
    assert install(private, answers, capsys=capsys)[0] == 0
    assert not (private / "inkwell" / "AGENTS.md").exists()
    assert (both / "inkwell" / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    text = (both / "inkwell" / "AGENTS.md").read_text()
    for absent in ("ai-docs", "archive", "human-docs", "sources", "RATIONALE", "local-machine", "inkwell/", "owner"):
        assert absent not in text, absent
    for present in ("`docs/`", "`docs/glossary.md`", "`plan/`", "`pytest`", "handed to the person you work for"):
        assert present in flat(text), present
    assert "the contributors' `inkwell/AGENTS.md` cites only the public rungs" in flat(agents(both))
    assert dead_links(both / "inkwell") == []


@needs_git
@pytest.mark.parametrize("cut", ["all", "none"])
def test_the_one_repository_forms_nest_nothing_and_append_their_ignore_lines(tmp_path, capsys, cut):
    folder = project(tmp_path)
    git("init", "-q", cwd=folder)
    rc, out = install(folder, dict(MINIMAL, cut=cut, status=True, families=FAMILIES, handoff=True), capsys=capsys)
    assert rc == 0, out
    assert out.startswith("FORM     one " + ("public" if cut == "all" else "private") + " repository")
    lines = (folder / ".gitignore").read_text().splitlines()
    assert "/*" not in lines and "/local-machine.md" in lines
    rationale = flat((folder / "RATIONALE.md").read_text())
    if cut == "all":
        # A private element in a public repository stays on this device.
        assert "/sources/" in lines and "/human-docs/" in lines
        assert git("check-ignore", "-q", "human-docs/README.md", cwd=folder).returncode == 0
        assert "everything is public" in flat(agents(folder))
        assert "The owner's words" not in rationale and "no quotation" in rationale
    else:
        assert "/sources/*" in lines and "!/sources/README.md" in lines and "/human-docs/" not in lines
        assert git("check-ignore", "-q", "sources/README.md", cwd=folder).returncode == 1
        assert "everything is private" in flat(agents(folder))
        assert "The owner's words" in rationale


# ---------------------------------------------------------------- what the answers change

def test_conductor_and_four_hands_write_different_rules(tmp_path, capsys):
    on, off = project(tmp_path, "on"), project(tmp_path, "off")
    assert install(on, dict(MINIMAL, mode="four-hands"), capsys=capsys)[0] == 0
    assert install(off, dict(MINIMAL, mode="conductor"), capsys=capsys)[0] == 0
    on_text, off_text = " ".join(agents(on).split()), " ".join(agents(off).split())
    for phrase in FOUR_HANDS_ONLY:
        assert phrase in on_text and phrase not in off_text, phrase
    for phrase in CONDUCTOR_ONLY:
        assert phrase in off_text and phrase not in on_text, phrase


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
    install(on_mode, dict(MINIMAL, opinionated=True, mode="four-hands"), capsys=capsys)
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


@needs_git
def test_no_prose_line_is_longer_than_the_kit_width(tmp_path, capsys):
    folder = workspace(tmp_path)
    assert install(folder, dict(FULL, graph="none"), capsys=capsys)[0] == 0
    for name in ("AGENTS.md", "RATIONALE.md", "inkwell/AGENTS.md"):
        for line in (folder / name).read_text().splitlines():
            if not line.startswith("|"):
                assert len(line) <= sc.WIDTH, line


# ---------------------------------------------------------------- what the script refuses

@needs_git
def test_a_dry_run_writes_nothing(tmp_path, capsys):
    folder = workspace(tmp_path)
    before = tree(folder)
    rc, out = install(folder, FULL, "--dry-run", capsys=capsys)
    assert rc == 0, out
    assert tree(folder) == before
    assert not (folder / "ai-docs").exists() and not (folder / "inkwell" / "docs").exists()
    for rel in ("AGENTS.md", ".gitignore", "ai-docs/status.md", "inkwell/AGENTS.md", "inkwell/graph.yml"):
        assert re.search(rf"WOULD +{re.escape(rel)} ", out), rel
    assert "nothing was written" in out


def test_a_dry_run_in_one_repository_writes_nothing_either(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / ".gitignore").write_text("build/\n")
    (folder / ".ignore").write_text("target/\n")
    before = tree(folder)
    rc, out = install(folder, dict(MINIMAL, status=True, families=FAMILIES, handoff=True), "--dry-run",
                      capsys=capsys)
    assert rc == 0, out
    assert tree(folder) == before
    assert re.search(r"WOULD +\.ignore +append: archive/", out)


def test_an_existing_file_stops_the_whole_run(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / "AGENTS.md").write_text("the project's own rules\n")
    before = tree(folder)
    rc, out = install(folder, MINIMAL, capsys=capsys)
    assert rc == 1
    assert "REFUSED" in out and "AGENTS.md" in out
    assert tree(folder) == before


def test_force_replaces_the_instructions_and_keeps_every_record(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sc, "specgraph_available", lambda: False)  # an existing graph file is kept before the step
    folder = project(tmp_path)
    (folder / "AGENTS.md").write_text("old rules\n")
    for rel in RECORDS:
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(f"the project's own {rel}\n")
    rc, out = install(folder, dict(MINIMAL, status=True, families=FAMILIES, handoff=True, graph="lite"), "--force",
                      capsys=capsys)
    assert rc == 0, out
    assert agents(folder).startswith("# Inkwell")
    for rel in RECORDS:
        assert (folder / rel).read_text() == f"the project's own {rel}\n", rel
        assert re.search(rf"KEPT +{re.escape(rel)} ", out), rel


def test_an_existing_docs_or_plan_folder_is_never_touched(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / "docs").mkdir()
    (folder / "docs" / "spec.md").write_text("the specification\n")
    (folder / "plan").mkdir()
    rc, out = install(folder, MINIMAL, capsys=capsys)
    assert rc == 0, out
    assert sorted(p.name for p in (folder / "docs").iterdir()) == ["spec.md"]
    assert list((folder / "plan").iterdir()) == []
    assert re.search(r"KEPT +docs/ +the folder exists", out) and re.search(r"KEPT +plan/ ", out)
    # With no glossary to point at, the map shows the slot instead of a path that does not exist.
    assert "What a term means | [to fill: the glossary's path]" in agents(folder)


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
    rc, _ = install(folder, dict(MINIMAL, mode="conductor"), "--mode", "four-hands", capsys=capsys)
    assert rc == 0
    assert FOUR_HANDS_ONLY[0] in " ".join(agents(folder).split())


@pytest.mark.parametrize("bad", [
    {"status": True, "families": {}},
    {"status": True, "families": {"app": "lower case"}},
    {"attribution": "Signed-off-by: x"},
    {"mode": "both"},
    {"name": 7},
    {"handoff": "no"},
    {"cut": "half"},
    {"layout": "single"},
    {"docs_dir": "docs"},
    {"human_docs": "public"},
    {"sources": "shared"},
    {"agent_layer": "both"},
    {"agent_layer": "public", "cut": "plan"},
    {"agent_layer": "private", "cut": "all"},
    {"public_dir": "inkwell"},
    {"public_dir": "ai-docs", "cut": "plan"},
    {"public_dir": "a/b", "cut": "plan"},
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
