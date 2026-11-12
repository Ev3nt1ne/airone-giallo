"""Tests for scaffold.py, each on a throwaway project folder made by pytest.

Run from the repository's root: pytest skills/setup/tests
The full install needs `specgraph` importable (pip install -e graph); without it that test is skipped, and the test
of the graph step's refusal still runs.
"""

import errno
import importlib.util
import json
import os
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
    "invariants": ["**A saved note survives a crash.** The editor writes each note to a new file and renames it over "
                   "the old one, so a crash leaves one version whole and never half of one. A change that writes in "
                   "place loses notes silently, and only when a crash hits mid-write."],
    "mode": "four-hands",
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
           "ai-docs/guides/README.md", "archive/README.md", "archive/LOG.md", "human-docs/README.md",
           "sources/README.md", "graph.yml")
# The file that shows where each rung landed.
RUNG_FILE = {"docs": "docs/README.md", "plan": "plan/README.md", "ai-docs": "ai-docs/status.md"}

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


def document_checks(folder, cut, public=None):
    """Stage what the setup wrote, as the skill's §4 says, then run Airone Giallo's two document checks from the
    workspace root as a script from the clone: (exit code, output) of each."""
    if not (folder / ".git").exists():
        git("init", "-q", cwd=folder)
    if public:
        assert git("add", "-A", cwd=folder / public).returncode == 0
        assert git("add", "-A", "--", ".", f":!{public}", cwd=folder).returncode == 0
    else:
        assert git("add", "-A", cwd=folder).returncode == 0
    tools = sc.REPO / "tools" / "src"
    out = {}
    for name, args in (("check_links", ["--cut", cut] + (["--public", public] if public else [])),
                       ("check_frontmatter", ["--all"])):
        p = subprocess.run([sys.executable, str(tools / f"{name}.py"), *args], cwd=folder, capture_output=True,
                           text=True)
        out[name] = (p.returncode, p.stdout + p.stderr)
        # A check that read nothing passes vacuously: the documents the setup wrote are in what it read.
        read = re.search(r"(\d+) (?:Markdown file|document)\(s\)", p.stdout)
        assert read and int(read.group(1)) >= 8, (name, p.stdout + p.stderr)
    return out


def agents(folder):
    return (folder / "AGENTS.md").read_text(encoding="utf-8")


def rows(out):
    """The report's file lines, (status, path, detail), whatever section they sit in."""
    return [(m[1], m[2], m[3]) for m in re.finditer(r"^ {4}([A-Z]+) +(\S+) *(.*)$", out, re.M)]


def section(out, title):
    """The lines of the report's section whose heading starts with `title`, up to the next section."""
    m = re.search(rf"^{re.escape(title)}.*\n((?:(?: .*)?\n)*?)(?=\S|\Z)", out + "\n", re.M)
    assert m, (title, out)
    return m.group(1)


# A generic old instruction file of about 5 KB, in sections, as a project might have one.
OLD_FILE = "# Inkwell: notes for agents\n" + "".join(
    f"\n## {title}\n\n" + (line + " ") * 14 + "\n" for title, line in (
        ("Commands", "Run the tests with `make test` and the linter with `make lint` before every commit."),
        ("Layout", "The editor lives in `app/`, the note format in `app/format.py`, fixtures in `tests/`."),
        ("Saving", "A saved note is written to a new file and renamed over the old one, so a crash never halves it."),
        ("Release", "Release with `make release` from a clean tree, after the tests pass."),
        ("Style", "Prefer small functions, and name a test for the behaviour it checks.")))


def unstamped(backup):
    """The backup's bytes without the stamp block the setup adds, which must be the original's."""
    data = backup.read_bytes()
    assert data.startswith(b"---\narchived: "), data[:40]
    return data[data.index(b"\n---\n") + 5:]


def archive_checks(folder, public=None):
    """check-archive and check-frontmatter, run as scripts from the clone on what is staged; in the two-repository
    form the public folder is staged on its own and left out of the workspace's index, as `document_checks` does."""
    if not (folder / ".git").exists():
        git("init", "-q", cwd=folder)
    if public:
        assert git("add", "-A", cwd=folder / public).returncode == 0
        assert git("add", "-A", "--", ".", f":!{public}", cwd=folder).returncode == 0
    else:
        assert git("add", "-A", cwd=folder).returncode == 0
    archives = [f"{public}/archive"] if public else []
    tools = sc.REPO / "tools" / "src"
    out = []
    for args in [["check_archive.py"]] + [["check_archive.py", "--archive", a] for a in archives] + \
            [["check_frontmatter.py", "--all"]]:
        proc = subprocess.run([sys.executable, str(tools / args[0]), *args[1:]], cwd=folder, capture_output=True,
                              text=True)
        out.append((args, proc.returncode, proc.stdout + proc.stderr))
    return out


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
                "ai-docs/guides/README.md", "archive/README.md", "archive/LOG.md", "human-docs/README.md",
                "sources/README.md", "inkwell/AGENTS.md", "inkwell/CLAUDE.md", "inkwell/docs/README.md",
                "inkwell/docs/glossary.md", "inkwell/graph.yml", "inkwell/plan/README.md", "inkwell/.ignore",
                "inkwell/archive/README.md", "inkwell/archive/LOG.md"):
        assert (folder / rel).is_file(), rel
    assert (folder / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    for path in folder.rglob("*"):
        if path.is_file() and ".git" not in path.parts and path.suffix in (".md", ".yml", ""):
            assert "{{" not in path.read_text(encoding="utf-8"), path
    # No code of Airone Giallo is copied into the project: the checks are its commands.
    assert not [p for p in folder.rglob("*.py")]
    checker = subprocess.run([sys.executable, str(sc.REPO / "tools" / "src" / "check_status.py"),
                              "ai-docs/status.md", "ai-docs/closed.md", "--graph", "inkwell/graph.yml"],
                             cwd=folder, capture_output=True, text=True)
    assert checker.returncode == 0, checker.stdout + checker.stderr
    assert "APP-001" in checker.stdout and "DOC-001" in checker.stdout
    lint = subprocess.run([sys.executable, "-m", "specgraph", "lint", "--graph", "inkwell/graph.yml"],
                          cwd=folder, capture_output=True, text=True)
    assert lint.returncode == 0 and "0 error(s)" in lint.stdout, lint.stdout + lint.stderr
    # Each repository's archive passes its checker, the public one named from the workspace root.
    for args in ([], ["--archive", "inkwell/archive"]):
        archive = subprocess.run([sys.executable, str(sc.REPO / "tools" / "src" / "check_archive.py"), *args],
                                 cwd=folder, capture_output=True, text=True)
        assert archive.returncode == 0 and "0 error(s)" in archive.stdout, (args, archive.stdout + archive.stderr)
    assert dead_links(folder) == []
    # No path is written with a doubled slash; a URL's own is the only one.
    for path in folder.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            text = re.sub(r"[a-z][a-z0-9+.-]*://", "", path.read_text(encoding="utf-8"))
            assert "//" not in text, path
    text = agents(folder)
    assert "its archive's `LOG.md`" in flat(text) and "`archive/` and `inkwell/archive/`, each repository's own" in text
    for row in ("`inkwell/docs/design.md`", "`inkwell/graph.yml`", "`ai-docs/status.md`",
                "`ai-docs/handoff/current.md`", "`inkwell/docs/glossary.md`", "`ai-docs/design/`",
                "`ai-docs/findings/`", "`ai-docs/guides/`", "`human-docs/`", "`sources/README.md`",
                "`APP`, `DOC`", "`specgraph lint --graph inkwell/graph.yml`",
                "`check-status ai-docs/status.md ai-docs/closed.md --graph inkwell/graph.yml`", "`check-archive`",
                "`check-archive --archive inkwell/archive`", "Never edited: `archive/`, `inkwell/archive/`",
                "`check-archive read <file>` before reading one", "`check-links --public inkwell --cut plan`",
                "`check-frontmatter`, in the repository being committed", "`pytest`"):
        assert row in text, row
    assert "[to fill" not in text
    assert "check-status ai-docs/status.md ai-docs/closed.md" in (folder / "ai-docs/status.md").read_text()
    # The contributors' file names its own archive's check and the two document checks, run inside the public
    # repository alone.
    contributors = (folder / "inkwell" / "AGENTS.md").read_text()
    assert "`check-archive`; `check-links`; `check-frontmatter`; `pytest`" in contributors
    # What the setup wrote passes Airone Giallo's own document checks, the ladder included.
    for name, (code, output) in document_checks(folder, "plan", "inkwell").items():
        assert code == 0 and "0 error(s)" in output, (name, output)


def test_minimal_install_writes_only_the_core(tmp_path, capsys):
    folder = project(tmp_path)
    rc, out = install(folder, MINIMAL, capsys=capsys)
    assert rc == 0, out
    written = sorted(str(p) for p in tree(folder))
    assert written == [".gitignore", ".ignore", "AGENTS.md", "CLAUDE.md", "RATIONALE.md", "ai-docs/README.md",
                       "ai-docs/design/README.md", "ai-docs/findings/README.md", "ai-docs/guides/README.md",
                       "archive/LOG.md", "archive/README.md", "docs/README.md", "docs/glossary.md",
                       "docs/invariants.md", "human-docs/README.md", "local-machine.md", "plan/README.md", "sources/README.md"]
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
    rc, out = install(folder, dict(MINIMAL, cut=cut, status=True, families=FAMILIES, handoff=True), capsys=capsys)
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
    for rel in ("AGENTS.md", "CLAUDE.md", "RATIONALE.md", "local-machine.md"):
        assert (folder / rel).is_file() and not (folder / "inkwell" / rel).exists(), rel
    # The archive is not a rung: each repository has its own at its top, with its log and its .ignore, whatever the
    # cut; the workspace's own is always private and named in the allowlist.
    tops = [folder, folder / "inkwell"] if form == "two" else [folder]
    for top in tops:
        for rel in (".ignore", "archive/README.md", "archive/LOG.md"):
            assert (top / rel).is_file(), (top, rel)
        assert "This repository's archive" in (top / "archive" / "README.md").read_text()
    if form == "two":
        assert "!/archive/" in (folder / ".gitignore").read_text().splitlines()
    else:
        assert not (folder / "inkwell").exists()
    a = dict(sc.DEFAULTS, **MINIMAL)
    a.update(cut=cut, graph="lite")
    sc.validate(a)
    graph = sc.context(a, sc.Layout.of(a), lambda rel: folder / rel)["graph_file"]
    assert graph == ("inkwell/graph.yml" if form == "two" and last_public >= 2 else "graph.yml")
    words = flat(agents(folder))
    expected = {"all": "everything is public", "none": "everything is private"}.get(
        cut, f"the public side ends at {sc.RUNG_NAMES.get(cut)}")
    assert expected in words and "(`doc-discipline` §1)" in words
    assert "`check-archive read <file>` before reading one" in words and "`check-archive`" in words
    assert ("`check-archive --archive inkwell/archive`" in words) == (form == "two")
    assert ("each repository's `archive/` is on its repository's side" in words) == (form == "two")
    for top in tops:
        assert "`check-archive read <file>`" in flat((top / "archive" / "README.md").read_text())
    # The links' check holds the sides to this cut; the tree the setup wrote passes it and the frontmatter's.
    links = f"check-links --public inkwell --cut {cut}" if form == "two" else f"check-links --cut {cut}"
    assert f"`{links}`" in words and "`check-frontmatter`" in words
    for name, (code, output) in document_checks(folder, cut, "inkwell" if form == "two" else None).items():
        assert code == 0 and "0 error(s)" in output, (cut, name, output)
        # The handoff's state names nothing above its rung, so no cut finds a citation in it to warn about.
        assert "handoff/" not in output, (cut, name, output)


@needs_git
def test_the_two_repository_form_refuses_without_the_public_repository(tmp_path, capsys):
    answers = dict(MINIMAL, cut="plan")
    missing = project(tmp_path, "missing")
    git("init", "-q", cwd=missing)
    rc, out = install(missing, answers, capsys=capsys)
    # The refusal says how the owner's folder comes in: moved whole, then registered where it is.
    assert rc == 1 and "REFUSED" in out and "mv <the folder> inkwell" in out
    assert "git submodule add <its URL, or ./inkwell without one> inkwell" in out
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
    assert rc == 1 and "docs/ (README, glossary, invariants)" in section(out, "Your repository:")
    assert "the real run would stop here" in out and "mv <the folder> inkwell" in out
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


@needs_git
def test_each_repository_gets_its_own_ignore_file_beside_its_archive(tmp_path, capsys):
    """A contributor who clones the public repository alone has no workspace above it: its own .ignore keeps its
    archive out of their searches too."""
    folder = workspace(tmp_path)
    assert install(folder, dict(MINIMAL, cut="plan"), capsys=capsys)[0] == 0
    assert (folder / ".ignore").read_text() == "archive/\n"
    assert (folder / "inkwell" / ".ignore").read_text() == "archive/\n"


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
    for absent in ("ai-docs", "archive/", "human-docs", "sources", "RATIONALE", "local-machine", "inkwell/", "owner"):
        assert absent not in text, absent
    # The public repository's own archive is checked from its root, so the contributors' checks name the command bare.
    for present in ("`docs/`", "`docs/glossary.md`", "`plan/`", "`check-archive`;", "`pytest`",
                    "handed to the person you work for"):
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


@needs_git
def test_the_workspace_agents_file_says_sessions_open_at_the_root_and_where_airone_giallo_comes_from(tmp_path, capsys):
    two, both, one = workspace(tmp_path, "two"), workspace(tmp_path, "both"), project(tmp_path, "one")
    answers = dict(MINIMAL, cut="plan", status=True, families=FAMILIES, invariants=FULL["invariants"])
    assert install(two, answers, capsys=capsys)[0] == 0
    assert install(both, dict(answers, agent_layer="both"), capsys=capsys)[0] == 0
    assert install(one, dict(MINIMAL, graph="lite"), capsys=capsys)[0] in (0, 1)  # the graph step may be skipped
    two_text, both_text, one_text = flat(agents(two)), flat(agents(both)), flat(agents(one))
    assert "never inside `inkwell/`**, where no instruction file exists" in two_text
    assert "whose own `AGENTS.md` is the contributors' short one" in both_text
    assert "Sessions open here" not in one_text
    # The opening paragraph names where the skills and the commands in use come from, and nothing else's.
    assert "https://github.com/Ev3nt1ne/airone-giallo" in two_text and "`/airone-giallo:<skill>`" in two_text
    assert "(`check-status`, `check-archive`, `check-links` and `check-frontmatter`)" in two_text
    assert "(`specgraph`, `check-archive`, `check-links` and `check-frontmatter`)" in one_text


def paragraphs_after_title(text):
    """The paragraphs of a document's body after its `# ` title, whitespace flattened."""
    body = text.split("\n# ", 1)[1].split("\n", 1)[1]
    return [flat(p) for p in body.strip().split("\n\n")]


def test_invariants_live_in_their_own_file_which_agents_md_imports(tmp_path, capsys):
    folder = project(tmp_path)
    assert install(folder, MINIMAL, capsys=capsys)[0] == 0
    text = agents(folder)
    # AGENTS.md holds no invariant and no section for them; its opening no longer lists any.
    assert re.findall(r"^## (.+)$", text, re.M) == ["The map", "The rules"]
    assert "nvariant" not in text.split("\n\n")[1]
    # The file is loaded, not merely linked: an `@` import outside a code span, the path ended by a space, which is
    # where Claude Code ends it. The link names it for a tool that does not follow imports, and check-links checks it.
    assert re.search(r"(?<!`)@docs/invariants\.md\s", text), text
    assert "[`docs/invariants.md`](docs/invariants.md)" in text
    flat_text = flat(text)
    assert ("propose it to the owner in prose (the rule, why it holds, what breaks if a change violates it), and write "
            "it into that file only on their yes") in flat_text
    assert "told rather than asked" not in flat_text
    assert "of a file that steers later sessions: this one, `CLAUDE.md`, `docs/invariants.md`, the skills" in flat_text
    assert "| `docs/invariants.md`, loaded into every session |" in text
    # CLAUDE.md stays one line: the import chain is CLAUDE.md, AGENTS.md, the invariants file.
    assert (folder / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    # The file says what an entry holds and that none is recorded yet: a fact, not a slot the setup's grep would list.
    invariants = (folder / "docs" / "invariants.md").read_text()
    assert invariants.startswith("---\ntitle: Invariants\n") and "<YYYY" not in invariants
    assert paragraphs_after_title(invariants)[-1] == "No invariant is recorded yet."
    assert "to fill" not in invariants and "[to fill: each invariant" not in text


def test_invariants_carried_over_are_written_into_the_file_as_given(tmp_path, capsys):
    folder = project(tmp_path)
    carried = [FULL["invariants"][0],
               "**A note's ID is never reused.** IDs come from a counter stored beside the notes and only ever "
               "incremented. A change that reuses a deleted note's ID makes an old link open the wrong note."]
    assert install(folder, dict(MINIMAL, invariants=carried), capsys=capsys)[0] == 0
    invariants = (folder / "docs" / "invariants.md").read_text()
    # What the file holds first, then each invariant as its own paragraph, in the order given and in its own words.
    assert paragraphs_after_title(invariants)[1:] == carried
    assert "No invariant is recorded yet" not in invariants
    assert "A saved note" not in agents(folder)
    for line in invariants.splitlines():
        assert len(line) <= sc.WIDTH or line.startswith("description:"), line


@needs_git
def test_in_two_repositories_the_invariants_are_public_and_imported_from_the_workspace_root(tmp_path, capsys):
    # The file is on rung 1, so it follows docs/ into the public folder; the import is relative to AGENTS.md, at the
    # workspace root, where sessions open. The contributors' file names none: it has another purpose.
    folder = workspace(tmp_path)
    assert install(folder, dict(FULL, graph="none"), capsys=capsys)[0] == 0
    assert re.search(r"(?<!`)@inkwell/docs/invariants\.md\s", agents(folder))
    assert FULL["invariants"][0] in flat((folder / "inkwell" / "docs" / "invariants.md").read_text())
    assert not (folder / "docs" / "invariants.md").exists()
    assert "nvariant" not in (folder / "inkwell" / "AGENTS.md").read_text()


def test_a_projects_own_invariants_file_is_kept_and_carried_ones_have_nowhere_to_go(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / "docs").mkdir()
    (folder / "docs" / "invariants.md").write_text("the project's own invariants\n")
    rc, out = install(folder, dict(MINIMAL, handoff=True), capsys=capsys)
    assert rc == 0, out
    assert (folder / "docs" / "invariants.md").read_text() == "the project's own invariants\n"
    assert re.search(r"KEPT +docs/invariants.md +the project's own invariants file exists", out), out
    # The first state does not say "none" over a file it did not write.
    state = flat((folder / "ai-docs" / "handoff" / "current.md").read_text())
    assert "**Invariants**: as `docs/invariants.md` states them" in state
    # Paragraphs carried over would be lost in silence: the run stops before writing, and so does the dry run's verdict.
    again = project(tmp_path, "again")
    (again / "docs").mkdir()
    (again / "docs" / "invariants.md").write_text("the project's own invariants\n")
    before = tree(again)
    answers = dict(MINIMAL, invariants=[FULL["invariants"][0]])
    rc, out = install(again, answers, "--dry-run", capsys=capsys)
    assert rc == 1 and "the real run would stop here" in out and "docs/invariants.md exists" in out
    rc, out = install(again, answers, capsys=capsys)
    assert rc == 1 and "REFUSED" in out and "no file to go into" in out
    assert tree(again) == before


def test_the_map_gives_each_home_of_a_decision_its_part(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sc, "specgraph_command", lambda: None)
    folder = project(tmp_path)
    install(folder, dict(MINIMAL, graph="lite"), capsys=capsys)
    rows = {ln.split(" | ")[-1].strip(" |"): ln for ln in agents(folder).splitlines() if ln.startswith("| ")}
    assert "where a new decision is written" in rows["`docs/`"]
    assert "a node for each recorded decision that something technical rests on" in rows["`graph.yml`"]
    assert "on the way to a decision; they stay here once it is recorded" in rows["`ai-docs/design/`"]
    text = flat(agents(folder))
    assert "put a project decision to the owner as an explanation, never a menu" in text
    assert "A permission covers the purpose it was given for, and nothing else" in text
    assert "owner's go to them" not in text and "A leave covers" not in text


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
    assert "Airone Giallo's author" not in agents(plain)
    assert "Airone Giallo's author" in agents(off_mode) and "Comments state invariants" not in agents(off_mode)
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
def test_no_prose_line_is_longer_than_the_width(tmp_path, capsys):
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
    # The first line says nothing has been written; the owner's repository comes first, then the new workspace, and
    # the new files are grouped by folder.
    assert out.splitlines()[0] == "DRY RUN: nothing has been written yet."
    public, workspace_part = section(out, "Your repository:"), section(out, "The workspace:")
    assert out.index("Your repository:") < out.index("The workspace:")
    assert re.search(r"^Your repository: .*/inkwell \(public\)$", out, re.M) and "The workspace: " in out
    first, folders = re.search(r"  New files\n    CREATE   (.*)\n    CREATE   (.*)\n", public).groups()
    assert set(first.split(", ")) == {".ignore", "AGENTS.md", "CLAUDE.md", "graph.yml"}, first
    assert "docs/ (README, glossary, invariants)" in folders and "archive/ (README, LOG)" in folders
    assert "AGENTS.md, CLAUDE.md, RATIONALE.md, local-machine.md" in workspace_part
    assert "ai-docs/ (README, status, closed, handoff/current, " in workspace_part
    assert "WOULD" not in out and "FORM" not in out


def test_a_dry_run_in_one_repository_writes_nothing_either(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / ".gitignore").write_text("build/\n")
    (folder / ".ignore").write_text("target/\n")
    before = tree(folder)
    rc, out = install(folder, dict(MINIMAL, status=True, families=FAMILIES, handoff=True), "--dry-run",
                      capsys=capsys)
    assert rc == 0, out
    assert tree(folder) == before
    have = section(out, "Your repository:")
    assert re.search(r"^  Files you have\n(?:    .*\n)*    APPEND +\.ignore +1 line: archive/$", have, re.M), out
    assert re.search(r"^  New files\n    CREATE   AGENTS.md, CLAUDE.md, RATIONALE.md, local-machine.md", have,
                     re.M), out


def test_a_dry_run_names_what_it_would_replace_and_keep_and_the_real_run_what_it_did(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / "local-machine.md").write_text("the old machine file\n")
    (folder / "RATIONALE.md").write_text("the project's own rationale\n")
    rc, out = install(folder, MINIMAL, "--force", "--dry-run", capsys=capsys)
    assert rc == 0, out
    lines = rows(out)
    found = [r[:2] for r in lines]
    assert ("REPLACE", "local-machine.md") in found and ("KEEP", "RATIONALE.md") in found
    assert {st for st, _, _ in lines} <= {"CREATE", "REPLACE", "APPEND", "KEEP"}, out
    # The real run keeps its status first, whether each step happened, and lists every file.
    rc, out = install(folder, MINIMAL, "--force", capsys=capsys)
    assert rc == 0, out
    assert "DRY RUN" not in out and out.splitlines()[0].startswith("FORM")
    lines = rows(out)
    found = [r[:2] for r in lines]
    assert ("DONE", "local-machine.md") in found and ("KEPT", "RATIONALE.md") in found
    assert {st for st, _, _ in lines} <= {"DONE", "KEPT"} and ("DONE", "docs/glossary.md") in [r[:2] for r in lines]


def test_an_existing_file_stops_the_whole_run(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / "local-machine.md").write_text("the machine as it was\n")
    before = tree(folder)
    rc, out = install(folder, MINIMAL, capsys=capsys)
    assert rc == 1
    assert "REFUSED" in out and "local-machine.md" in out
    assert tree(folder) == before


def test_an_old_instruction_file_is_backed_up_then_replaced_or_removed_in_one_repository(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / "CLAUDE.md").write_text(OLD_FILE)
    (folder / ".claude").mkdir()
    (folder / ".claude" / "CLAUDE.md").write_text("---\ntitle: x\n---\nmore rules\n")
    before = tree(folder)
    answers = dict(MINIMAL, carry=['"Commands" → ai-docs/guides/', '"Style" → AGENTS.md'])
    rc, out = install(folder, answers, "--dry-run", capsys=capsys)
    assert rc == 0 and tree(folder) == before, out
    have = [r[:2] for r in rows(section(out, "Your repository:"))]
    assert have[:4] == [("BACKUP", "CLAUDE.md"), ("REPLACE", "CLAUDE.md"), ("BACKUP", ".claude/CLAUDE.md"),
                        ("REMOVE", ".claude/CLAUDE.md")] or have[:4] == [
        ("BACKUP", ".claude/CLAUDE.md"), ("REMOVE", ".claude/CLAUDE.md"), ("BACKUP", "CLAUDE.md"),
        ("REPLACE", "CLAUDE.md")], have
    assert "unchanged, to archive/CLAUDE-before-setup.md" in out
    # The carry-over is a section of its own, after the repository's.
    assert "\nCarried over after the run, as you confirmed\n    \"Commands\" → ai-docs/guides/" in out
    assert out.index("Your repository:") < out.index("Carried over after the run")
    # The real run needs no --force: nothing is lost, since the backup is checked before the file is touched.
    rc, out = install(folder, answers, capsys=capsys)
    assert rc == 0, out
    assert (folder / "CLAUDE.md").read_text() == "@AGENTS.md\n" and not (folder / ".claude" / "CLAUDE.md").exists()
    assert unstamped(folder / "archive" / "CLAUDE-before-setup.md") == OLD_FILE.encode()
    # A file with a frontmatter of its own gets only the stamp line inside it.
    nested = (folder / "archive" / "dot-claude-CLAUDE-before-setup.md").read_bytes()
    assert re.fullmatch(rb"---\narchived: [0-9T:+-]+\ntitle: x\n---\nmore rules\n", nested), nested
    assert "backed up to archive/CLAUDE-before-setup.md, its bytes read back and compared" in out
    assert '"Style" → AGENTS.md' in out
    for args, code, output in archive_checks(folder):
        assert code == 0 and "0 error(s)" in output, (args, output)


@needs_git
def test_in_two_repositories_the_old_file_is_backed_up_in_the_workspace_and_removed_from_the_public_folder(
        tmp_path, capsys):
    folder = workspace(tmp_path)
    (folder / "inkwell" / "CLAUDE.md").write_text(OLD_FILE)
    answers = dict(MINIMAL, cut="plan", status=True, families=FAMILIES)
    rc, out = install(folder, answers, "--dry-run", capsys=capsys)
    assert rc == 0, out
    have = [r[:2] for r in rows(section(out, "Your repository:"))]
    assert have[:2] == [("BACKUP", "CLAUDE.md"), ("REMOVE", "CLAUDE.md")], have
    assert "unchanged, to the workspace's archive/CLAUDE-before-setup.md" in out
    rc, out = install(folder, answers, capsys=capsys)
    assert rc == 0, out
    # The backup is private, in the workspace's archive; the public folder keeps no instruction file, so the rule that
    # sessions open at the root, where no instruction file exists, holds.
    assert unstamped(folder / "archive" / "CLAUDE-before-setup.md") == OLD_FILE.encode()
    assert not (folder / "inkwell" / "archive" / "CLAUDE-before-setup.md").exists()
    assert not [n for n in sc.OLD_INSTRUCTIONS if (folder / "inkwell" / n).exists()]
    assert "never inside `inkwell/`**, where no instruction file exists" in flat(agents(folder))
    for args, code, output in archive_checks(folder, "inkwell"):
        assert code == 0 and "0 error(s)" in output, (args, output)
    # With the contributors' files, the old one is backed up and replaced by theirs.
    both = workspace(tmp_path, "both")
    (both / "inkwell" / "CLAUDE.md").write_text(OLD_FILE)
    rc, out = install(both, dict(answers, agent_layer="both"), capsys=capsys)
    assert rc == 0, out
    assert (both / "inkwell" / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    assert unstamped(both / "archive" / "CLAUDE-before-setup.md") == OLD_FILE.encode()


def agent_tool_files(folder):
    """A public folder with the agent tool's files: settings, a command, an MCP file, and an old nested CLAUDE.md."""
    (folder / ".claude" / "commands").mkdir(parents=True)
    (folder / ".claude" / "settings.json").write_text('{"permissions": {"allow": ["Bash(make test)"]}}\n')
    (folder / ".claude" / "commands" / "x.md").write_text("---\ndescription: run the tests\n---\nRun make test.\n")
    (folder / ".claude" / "CLAUDE.md").write_text("old nested rules\n")
    (folder / ".mcp.json").write_text('{"mcpServers": {}}\n')


@needs_git
def test_in_two_repositories_the_agent_tools_files_move_to_the_workspace_root(tmp_path, capsys):
    folder = workspace(tmp_path)
    agent_tool_files(folder / "inkwell")
    answers = dict(MINIMAL, cut="plan", status=True, families=FAMILIES)
    rc, out = install(folder, answers, "--dry-run", capsys=capsys)
    assert rc == 0, out
    have = [r[:2] for r in rows(section(out, "Your repository:"))]
    # The old nested CLAUDE.md is the old-file step's, done first; then the folder and the MCP file move, as two lines.
    assert have[:4] == [("BACKUP", ".claude/CLAUDE.md"), ("REMOVE", ".claude/CLAUDE.md"), ("MOVE", ".claude/"),
                        ("MOVE", ".mcp.json")], have
    rc, out = install(folder, answers, capsys=capsys)
    assert rc == 0, out
    assert not (folder / "inkwell" / ".claude").exists() and not (folder / "inkwell" / ".mcp.json").exists()
    assert sorted(str(p.relative_to(folder)) for p in (folder / ".claude").rglob("*") if p.is_file()) == [
        ".claude/commands/x.md", ".claude/settings.json"]
    assert (folder / ".mcp.json").read_text() == '{"mcpServers": {}}\n'
    assert (folder / "archive" / "dot-claude-CLAUDE-before-setup.md").is_file()
    # What moved in stays tracked, now on the private side; only the personal settings file stays out.
    lines = (folder / ".gitignore").read_text().splitlines()
    assert "!/.claude/" in lines and "/.claude/settings.local.json" in lines and "!/.mcp.json" in lines
    assert "/.claude/*" not in lines
    for rel in (".claude/settings.json", ".claude/commands/x.md", ".mcp.json"):
        assert git("check-ignore", "-q", rel, cwd=folder).returncode == 1, rel
    # With the contributors' files the move still applies: their layer is the short file, the rest stays private.
    both = workspace(tmp_path, "both")
    agent_tool_files(both / "inkwell")
    assert install(both, dict(answers, agent_layer="both"), capsys=capsys)[0] == 0
    assert (both / ".claude" / "settings.json").is_file() and not (both / "inkwell" / ".claude").exists()
    # A `.claude/` holding only an old CLAUDE.md has nothing else to move.
    bare = workspace(tmp_path, "bare")
    (bare / "inkwell" / ".claude").mkdir()
    (bare / "inkwell" / ".claude" / "CLAUDE.md").write_text("old nested rules\n")
    rc, out = install(bare, answers, "--dry-run", capsys=capsys)
    assert rc == 0 and "MOVE     .claude" not in out, out


@needs_git
def test_the_agent_tools_files_never_move_over_the_workspaces_own(tmp_path, capsys):
    folder = workspace(tmp_path)
    agent_tool_files(folder / "inkwell")
    (folder / ".mcp.json").write_text("the workspace's own\n")
    before = tree(folder)
    rc, out = install(folder, dict(MINIMAL, cut="plan", status=True, families=FAMILIES), capsys=capsys)
    assert rc == 1 and "REFUSED  the workspace already has these" in out and "inkwell/.mcp.json →" in out, out
    assert "Merge each pair by hand with the owner" in out
    assert tree(folder) == before


def test_in_one_repository_the_agent_tools_files_stay_where_they_are(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / ".claude").mkdir()
    (folder / ".claude" / "settings.json").write_text("{}\n")
    (folder / ".mcp.json").write_text("{}\n")
    rc, out = install(folder, MINIMAL, capsys=capsys)
    assert rc == 0 and "MOVE" not in out, out
    assert (folder / ".claude" / "settings.json").is_file() and (folder / ".mcp.json").is_file()


@needs_git
def test_across_file_systems_the_agent_tools_files_are_copied_compared_then_removed(tmp_path, capsys, monkeypatch):
    real = os.rename

    def no_rename(src, dst):
        if Path(src).name in (".claude", ".mcp.json"):
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return real(src, dst)
    monkeypatch.setattr(sc.os, "rename", no_rename)
    folder = workspace(tmp_path)
    agent_tool_files(folder / "inkwell")
    rc, out = install(folder, dict(MINIMAL, cut="plan", status=True, families=FAMILIES), capsys=capsys)
    assert rc == 0, out
    assert (folder / ".claude" / "commands" / "x.md").is_file() and (folder / ".mcp.json").is_file()
    assert not (folder / "inkwell" / ".claude").exists() and not (folder / "inkwell" / ".mcp.json").exists()


@needs_git
def test_the_agent_tools_folder_stays_when_its_old_claude_md_could_not_be_backed_up(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sc, "write_backup", lambda path, data: (path.parent.mkdir(parents=True, exist_ok=True),
                                                                path.write_bytes(data[:-1])))
    folder = workspace(tmp_path)
    agent_tool_files(folder / "inkwell")
    rc, out = install(folder, dict(MINIMAL, cut="plan", status=True, families=FAMILIES), capsys=capsys)
    assert rc == 1 and ("FAILED", ".claude/") in [r[:2] for r in rows(out)], out
    assert (folder / "inkwell" / ".claude" / "CLAUDE.md").is_file() and not (folder / ".claude").exists()


def test_an_old_file_is_left_as_it_was_when_its_backup_does_not_read_back(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sc, "write_backup", lambda path, data: (path.parent.mkdir(parents=True, exist_ok=True),
                                                                path.write_bytes(data[:-1])))
    folder = project(tmp_path)
    (folder / "CLAUDE.md").write_text(OLD_FILE)
    rc, out = install(folder, MINIMAL, capsys=capsys)
    assert rc == 1 and "SETUP INCOMPLETE" in out, out
    assert ("FAILED", "CLAUDE.md") in [r[:2] for r in rows(out)]
    assert (folder / "CLAUDE.md").read_text() == OLD_FILE


def test_a_backup_is_never_written_over(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / "CLAUDE.md").write_text(OLD_FILE)
    (folder / "archive").mkdir()
    (folder / "archive" / "CLAUDE-before-setup.md").write_text("an earlier backup\n")
    before = tree(folder)
    rc, out = install(folder, MINIMAL, "--force", capsys=capsys)
    assert rc == 1 and "REFUSED" in out and "archive/CLAUDE-before-setup.md" in out, out
    assert tree(folder) == before


@needs_git
def test_the_two_repository_setup_runs_where_the_folder_is_and_the_move_comes_last(tmp_path, capsys):
    """The ruled order, as one session started in the owner's folder would run it: the dry run, the workspace, the real
    run and the public commit while the folder is where it was; then only commands with absolute paths: the move, the
    registration in place, the workspace's commit."""
    who = ("-c", "user.email=agent@example.com", "-c", "user.name=Agent")
    source = project(tmp_path, "notes")
    git("init", "-q", cwd=source)
    (source / ".gitignore").write_text("node_modules/\n")
    (source / "CLAUDE.md").write_text(OLD_FILE)
    (source / "app.py").write_text("x = 1\n")
    assert git("add", "-A", cwd=source).returncode == 0
    assert git(*who, "commit", "-qm", "the project", cwd=source).returncode == 0
    (source / "node_modules").mkdir()
    (source / "node_modules" / "x").write_text("a dependency\n")
    before = tree(source)
    nido = tmp_path / "notes-nido"
    answers = dict(MINIMAL, cut="plan", status=True, families=FAMILIES, handoff=True, move_from=str(source),
                   carry=['"Commands" → ai-docs/guides/', '"Style" → AGENTS.md'])
    rc, out = install(nido, answers, "--dry-run", capsys=capsys)
    assert rc == 0 and tree(source) == before and not nido.exists(), out
    lines = out.splitlines()
    assert lines[0] == "DRY RUN: nothing has been written yet."
    # The move and the workspace each take a short line, their explanation indented below it.
    assert lines[2] == f"MOVE     {source} → {nido / 'notes'}   (the last step)", lines[2]
    assert lines[3] == (" " * 9 + "your whole folder becomes the public side, ignored files included; the session "
                        "moves it after the real run and the checks"), lines[3]
    assert lines[4] == f"CREATE   {nido}   (before the real run)", lines[4]
    assert lines[5].startswith(" " * 9 + "the new private workspace, a new repository"), lines[5]
    # The public side is written where the folder is now; its header names that place and repeats no move.
    assert f"\nYour repository: {source} (public)\n" in out and "moved last" not in out
    # The carry-over comes last, after both repositories.
    assert out.index("The workspace:") < out.index("Carried over after the run, as you confirmed")
    # The session creates the workspace; the real run writes the workspace's files there and the public ones into the
    # folder where it still is.
    assert git("init", "-q", str(nido), cwd=tmp_path).returncode == 0
    rc, out = install(nido, answers, capsys=capsys)
    assert rc == 0, out
    assert not (nido / "notes").exists() and (source / "docs" / "invariants.md").is_file()
    assert not (source / "CLAUDE.md").exists() and (source / "node_modules" / "x").is_file()
    assert unstamped(nido / "archive" / "CLAUDE-before-setup.md") == OLD_FILE.encode()
    assert "!/notes" in (nido / ".gitignore").read_text().splitlines()
    # A session that opens before the carry-over is done finds it as its first step.
    state = flat((nido / "ai-docs" / "handoff" / "current.md").read_text())
    assert ("Finish carrying over the old instruction file from the backup of the old CLAUDE.md in the archive, each "
            'part to the place confirmed at setup, and delete each line here once its part is carried: "Commands" → '
            'ai-docs/guides/; "Style" → AGENTS.md.') in state, state
    # The public commit, in the folder; then the move and what follows it, with absolute paths only.
    assert git("add", "-A", cwd=source).returncode == 0
    assert git(*who, "commit", "-qm", "Install Airone Giallo", cwd=source).returncode == 0
    head = git("rev-parse", "HEAD", cwd=source).stdout.strip()
    shutil.move(str(source), str(nido / "notes"))
    added = git("-C", str(nido), "submodule", "add", "./notes", "notes", cwd=tmp_path)
    assert added.returncode == 0 and "Adding existing repo at 'notes'" in added.stdout + added.stderr, added
    assert git("-C", str(nido), "add", "-A", cwd=tmp_path).returncode == 0
    assert git(*who, "-C", str(nido), "commit", "-qm", "Install Airone Giallo; add notes", cwd=tmp_path).returncode == 0
    # Both repositories clean, the gitlink at the public commit, the ignored file kept, every check clean.
    assert git("-C", str(nido), "status", "--short", cwd=tmp_path).stdout == ""
    assert git("-C", str(nido / "notes"), "status", "--short", cwd=tmp_path).stdout == ""
    assert git("-C", str(nido), "ls-tree", "HEAD", "notes", cwd=tmp_path).stdout.split()[2] == head
    assert (nido / "notes" / "node_modules" / "x").read_text() == "a dependency\n"
    tools = sc.REPO / "tools" / "src"
    for script, args in (("check_links.py", ["--public", "notes", "--cut", "plan"]), ("check_archive.py", []),
                         ("check_archive.py", ["--archive", "notes/archive"]), ("check_frontmatter.py", ["--all"]),
                         ("check_status.py", ["ai-docs/status.md", "ai-docs/closed.md"])):
        proc = subprocess.run([sys.executable, str(tools / script), *args], cwd=nido, capture_output=True, text=True)
        assert proc.returncode == 0 and "0 error(s)" in proc.stdout, (script, args, proc.stdout + proc.stderr)
        assert "warning:" not in proc.stdout, (script, proc.stdout)


def test_a_second_run_stops_naming_the_taken_backup_and_what_to_do(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / "CLAUDE.md").write_text(OLD_FILE)
    assert install(folder, MINIMAL, capsys=capsys)[0] == 0
    before = tree(folder)
    rc, out = install(folder, MINIMAL, "--force", capsys=capsys)
    assert rc == 1 and "archive/CLAUDE-before-setup.md, the backup CLAUDE.md would get" in out, out
    assert "A second run of the setup on the same project is not handled" in out and "git stash -u" in out
    assert tree(folder) == before




def test_force_replaces_the_instructions_and_keeps_every_record(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sc, "specgraph_command", lambda: None)  # an existing graph file is kept before the step
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


def test_an_existing_docs_or_plan_folder_gets_no_index_and_docs_gets_its_missing_glossary(tmp_path, capsys):
    folder = project(tmp_path)
    (folder / "docs").mkdir()
    (folder / "docs" / "spec.md").write_text("the specification\n")
    (folder / "plan").mkdir()
    rc, out = install(folder, MINIMAL, capsys=capsys)
    assert rc == 0, out
    assert sorted(p.name for p in (folder / "docs").iterdir()) == ["glossary.md", "invariants.md", "spec.md"]
    assert (folder / "docs" / "spec.md").read_text() == "the specification\n"
    assert list((folder / "plan").iterdir()) == []
    assert re.search(r"KEPT +docs/ +the folder exists", out) and re.search(r"KEPT +plan/ ", out)
    assert "What a term means | `docs/glossary.md`" in agents(folder)
    # A glossary already there is kept, and does not stop the run.
    (folder / "docs" / "glossary.md").write_text("the project's glossary\n")
    (folder / "AGENTS.md").unlink()
    (folder / "CLAUDE.md").unlink()
    rc, out = install(folder, MINIMAL, "--force", capsys=capsys)
    assert rc == 0, out
    assert (folder / "docs" / "glossary.md").read_text() == "the project's glossary\n"
    assert re.search(r"KEPT +docs/glossary.md +the glossary exists", out)
    # An answered glossary elsewhere: none is written into docs/.
    other = project(tmp_path, "other")
    (other / "docs").mkdir()
    rc, out = install(other, dict(MINIMAL, glossary="`terms.md`"), capsys=capsys)
    assert rc == 0, out
    assert not (other / "docs" / "glossary.md").exists()


def test_every_written_document_carries_frontmatter_except_the_owners_notes_and_the_manifest(tmp_path, capsys):
    folder = project(tmp_path)
    assert install(folder, dict(MINIMAL, status=True, families=FAMILIES, handoff=True), capsys=capsys)[0] == 0
    exempt = {"AGENTS.md", "CLAUDE.md", "RATIONALE.md", "local-machine.md", "human-docs/README.md",
              "sources/README.md"}
    for md in folder.rglob("*.md"):
        rel = str(md.relative_to(folder))
        if rel in exempt:
            continue
        head = md.read_text().split("\n---\n", 1)[0]
        assert head.startswith("---\n"), rel
        # The handoff's template, the skill's own, carries no tags; every index and the glossary do.
        keys = ("title:", "description:", "type:", "created:", "updated:") + (() if "handoff/" in rel else ("tags:",))
        for key in keys:
            assert f"\n{key}" in head, (rel, key)
        assert "<YYYY" not in head, rel


def test_the_handoffs_first_log_is_the_handoff_log_not_the_archives(tmp_path, capsys):
    folder = project(tmp_path)
    rc, out = install(folder, dict(MINIMAL, handoff=True, stage="set-up"), capsys=capsys)
    assert rc == 0, out
    log = (folder / "ai-docs" / "handoff" / "log-set-up.md").read_text()
    assert "\ntitle: Handoff log, set-up\n" in log and "\n# Handoff log, set-up\n" in log
    assert log != (folder / "archive" / "LOG.md").read_text()


def template_headings(block):
    text = sc.HANDOFF_TEMPLATE.read_text()
    return re.findall(r"^## (.+)$", re.findall(r"^```markdown\n(.*?)^```$", text, re.M | re.S)[block], re.M)


def test_the_handoffs_first_state_is_what_the_setup_knows_not_a_blank_form(tmp_path, capsys):
    folder = project(tmp_path)
    rc, out = install(folder, dict(MINIMAL, status=True, families=FAMILIES, handoff=True, stage="set-up"),
                      capsys=capsys)
    assert rc == 0, out
    state = (folder / "ai-docs" / "handoff" / "current.md").read_text()
    log = (folder / "ai-docs" / "handoff" / "log-set-up.md").read_text()
    # The template's blank form wrote its slots into both files.
    assert "[to fill" not in state and "[to fill" not in log
    # The template keeps the shape: its sections, in its order.
    assert re.findall(r"^## (.+)$", state, re.M) == template_headings(0)
    text = flat(state)
    assert "Written at the close of session setup, " in text and "The log: [log-set-up.md](log-set-up.md)" in text
    # The log starts with no entry, so the banner points to none.
    assert "newest entry" not in text and "[log-set-up.md](log-set-up.md), no entry yet" in text
    # The checks run after the script: the state says so, and claims no result.
    assert "**Checks**: not run when the setup wrote this file" in text and "error" not in text
    assert "**The cut**: `none`, so one private repository" in text
    assert "the status file `ai-docs/status.md`" in text and "the first for the stage `set-up`" in text
    assert "no specification graph" in text
    assert "**The optional tools**: the status file `ai-docs/status.md`" in text
    # No invariant was carried over, so the state says there is none rather than pointing to one.
    assert "**Invariants**: none recorded yet in `docs/invariants.md`." in text
    assert ("**For the owner**: the slots the setup left unanswered in the instruction file and the machine file."
            in text)
    for empty in ("**Unexplained**: none.", "**Deferred**: none.", "**Runs in flight**: none.",
                  "None: this state quotes no figure."):
        assert empty in text, empty
    # The log keeps its head and drops the template's blank entry: the first close writes the first entry.
    assert "\n# Handoff log, set-up\n" in log and not re.search(r"^## ", log, re.M)
    assert template_headings(1) and "## " + template_headings(1)[0] not in log


@needs_git
def test_the_handoffs_first_state_with_every_answer_given_leaves_nothing_open(tmp_path, capsys):
    folder = workspace(tmp_path)
    assert install(folder, dict(FULL, graph="none"), capsys=capsys)[0] == 0
    text = flat((folder / "ai-docs" / "handoff" / "current.md").read_text())
    assert "**For the owner**: none." in text
    assert ("**Invariants**: as `inkwell/docs/invariants.md` states them; no test is recorded yet as guarding one."
            in text)
    assert "Agree the first piece of work with the owner, and record it in `ai-docs/status.md`." in text
    assert "**The cut**: `plan`, so two repositories" in text


def test_a_handoff_template_whose_sections_changed_stops_the_install(tmp_path, capsys, monkeypatch):
    changed = tmp_path / "handoff-template.md"
    changed.write_text(sc.HANDOFF_TEMPLATE.read_text().replace(
        "## 6. Where the numbers come from", "## 6. Where the numbers come from\n\n## 7. A section added", 1))
    monkeypatch.setattr(sc, "HANDOFF_TEMPLATE", changed)
    folder = project(tmp_path)
    rc, out = install(folder, dict(MINIMAL, handoff=True), capsys=capsys)
    assert rc == 1 and "cannot prepare the install" in out and "7. A section added" in out
    assert tree(folder) == {}


def test_the_projects_own_checks_show_a_slot_until_answered(tmp_path, capsys):
    bare, told = project(tmp_path, "bare"), project(tmp_path, "told")
    install(bare, dict(MINIMAL, status=True, families=FAMILIES), capsys=capsys)
    install(told, dict(MINIMAL, status=True, families=FAMILIES, checks="`pytest`"), capsys=capsys)
    row = [ln for ln in agents(bare).splitlines() if ln.startswith("| How a session opens")][0]
    assert "`check-status" in row and "`check-archive`" in row
    assert "`check-links --cut none`" in row and "`check-frontmatter`" in row
    assert row.endswith("[to fill: the project's own test and lint commands] |")
    row = [ln for ln in agents(told).splitlines() if ln.startswith("| How a session opens")][0]
    assert row.endswith("`pytest` |") and "to fill" not in row


def test_the_graph_step_is_reported_skipped_when_specgraph_is_missing(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sc, "specgraph_command", lambda: None)
    folder = project(tmp_path)
    rc, out = install(folder, dict(MINIMAL, graph="lite"), capsys=capsys)
    assert rc == 1
    assert re.search(r"SKIPPED +graph.yml", out) and "SETUP INCOMPLETE" in out
    assert not (folder / "graph.yml").exists()


def without_the_module(monkeypatch):
    """specgraph made un-importable from this interpreter, whatever it has installed."""
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a, **k: None if name.split(".")[0] == "specgraph" else real(name, *a, **k))


def path_of(monkeypatch, folder, keep=False):
    """PATH made to start at folder, or to be folder alone, so a specgraph elsewhere on it is not found."""
    folder.mkdir()
    monkeypatch.setenv("PATH", os.pathsep.join([str(folder), os.environ["PATH"]]) if keep else str(folder))
    return folder


def fake_specgraph(bin_dir):
    """A specgraph command that writes a graph file carrying a marker the real one never writes."""
    fake = bin_dir / "specgraph"
    fake.write_text("#!/bin/sh\nprintf 'meta:\\n  made-by: fake specgraph %s\\n' \"$*\" > graph.yml\n")
    fake.chmod(0o755)


@pytest.mark.skipif(os.name != "posix", reason="the fake command is a shell script")
def test_the_graph_step_runs_the_command_on_path_when_the_module_is_not_importable(tmp_path, capsys, monkeypatch):
    # A tool installer (uv tool, pipx) puts the command on PATH and keeps the module out of every other Python.
    without_the_module(monkeypatch)
    fake_specgraph(path_of(monkeypatch, tmp_path / "bin", keep=True))
    folder = project(tmp_path)
    rc, out = install(folder, dict(MINIMAL, graph="lite"), capsys=capsys)
    assert rc == 0, out
    assert re.search(r"DONE +graph.yml", out), out
    assert "made-by: fake specgraph init --profile lite --graph graph.yml" in (folder / "graph.yml").read_text()


def test_the_graph_step_is_skipped_naming_the_install_when_neither_command_nor_module_exists(tmp_path, capsys,
                                                                                         monkeypatch):
    without_the_module(monkeypatch)
    path_of(monkeypatch, tmp_path / "empty-bin")
    folder = project(tmp_path)
    rc, out = install(folder, dict(MINIMAL, graph="lite"), capsys=capsys)
    assert rc == 1
    line = [ln for ln in out.splitlines() if re.match(r" *SKIPPED +graph.yml", ln)][0]
    assert f"uv tool install {sc.REPO / 'graph'}" in line and "pipx install" in line, line
    assert "pip install <airone-giallo>" not in line
    assert not (folder / "graph.yml").exists()


def test_the_graph_step_falls_back_to_the_module_when_no_command_is_on_path(tmp_path, capsys, monkeypatch):
    pytest.importorskip("specgraph")
    path_of(monkeypatch, tmp_path / "empty-bin")
    folder = project(tmp_path)
    rc, out = install(folder, dict(MINIMAL, graph="lite"), capsys=capsys)
    assert rc == 0, out
    assert re.search(r"DONE +graph.yml", out), out
    graph = (folder / "graph.yml").read_text()
    assert "meta:" in graph and "fake" not in graph


@pytest.mark.skipif(os.name != "posix", reason="the fake command is a shell script")
def test_the_graph_step_prefers_the_command_on_path_to_the_importable_module(tmp_path, capsys, monkeypatch):
    # The command is what the owner's shell runs; the module may be an older copy in this interpreter.
    pytest.importorskip("specgraph")
    fake_specgraph(path_of(monkeypatch, tmp_path / "bin", keep=True))
    folder = project(tmp_path)
    rc, out = install(folder, dict(MINIMAL, graph="lite"), capsys=capsys)
    assert rc == 0, out
    assert "made-by: fake specgraph init --profile lite --graph graph.yml" in (folder / "graph.yml").read_text()


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
    {"cut": "archive"},
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
    {"move_from": "/somewhere/notes"},
    {"invariants": ["   "]},
])
def test_invalid_answers_exit_two_and_write_nothing(tmp_path, capsys, bad):
    folder = project(tmp_path)
    rc, _ = install(folder, dict(MINIMAL, **bad), capsys=capsys)
    assert rc == 2
    assert tree(folder) == {}


# ---------------------------------------------------------------- the skill's own text

def test_the_skills_questions_are_labelled_and_every_reference_names_a_question_that_exists():
    text = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
    flat_text = flat(text)
    # One table: each question carries its label, and the groups are labels for the reader, not headings or rounds.
    labelled = re.findall(r"^\| ([A-Z]\d) · ([^|]+?) \| ", text, re.M)
    ids = [i for i, _ in labelled]
    assert ids == ["A1", "A2", "A3", "B1", "C1", "C2", "C3", "D1"], ids
    assert not re.search(r"^#+ [A-Z]\. ", text, re.M)
    # The first message holds the findings and the old file's step only; each later one a single group, in one fixed
    # run, the two questions with the most to read alone.
    assert ("The first message holds only the opening findings** and, when the repository has an old instruction "
            "file, that file's step (below); no question of any group") in flat_text
    assert "Each later message holds questions of one group only, never of two**" in flat_text
    assert "in this run: A1, A2 and A3; B1; C1 and C2; C3; D1; then the dry run (§3)" in flat_text
    assert "B1 and C3 have the most to read, so each comes alone" in flat_text
    assert "There is no fixed number per message" not in flat_text and "rounds of one to four" not in text
    # One principle for proposing: drafts where the repository gives grounds, only the confirmed written, no grounds
    # said plainly.
    assert ("Propose whenever the repository gives grounds, write only what the owner confirmed, and say plainly when "
            "there are no grounds.") in flat_text
    row = {i: re.search(rf"^\\| {i} · .*$", text, re.M).group(0) for i in ("A1", "C1")}
    assert "drafts of both, taken from the README, the old instruction file or the repository's name" in row["A1"]
    assert "no default: both are the owner's words" not in text
    assert "no default: the repository cannot show how the owner works" in row["C1"]
    assert "propose families from the areas of work found in the repository" in flat_text
    assert "write only those the owner confirms; never take them from memory or from another project" in flat_text
    assert "never fill them from anything but the owner's answer" not in flat_text
    # Every question has one frame of four named parts, filled from the repository: the shape is fixed, the words are
    # not. Each part has a length, and a message holds one thing outside its frames. A pending question is reminded in
    # a line, never re-asked.
    assert ("**Every question has the same frame, and the agent writes what goes in it from this repository.** The "
            "question's label in bold on a line of its own, never as a heading, then four parts, each opened by its "
            "name in bold and a colon, in this order:") in flat_text
    parts = re.findall(r"^  - \*\*([A-Z][a-z ]+)\*\*: ", text, re.M)
    assert parts == ["What it is", "Options", "Suggestion", "Watch out"], parts
    assert "is explained in a few words where it first appears: the owner has not read this skill" in flat_text
    assert "**Watch out**: only when this repository warrants it, what an option would expose, break or destroy here" \
        in flat_text and "Absent otherwise." in flat_text
    assert "**Each part is short, and says a thing once.**" in flat_text
    assert ("What it is, two sentences, or one line for each thing it has to explain; Options, one line an option, "
            "saying what the option does for the owner and nothing a part above already said; Suggestion, one line "
            "for each thing the owner decides; Watch out, two lines.") in flat_text
    assert "a question takes about a hundred words, and A2 and B1 about two hundred beside B1's table" in flat_text
    assert ("An answer that takes an option a Watch out warned about is met that way, with what it means now and what "
            "the owner can do, and is not argued again.") in flat_text
    assert "A message does not say what was checked, sum up the answers or announce the next message." in flat_text
    assert "Say each question in three parts" not in flat_text and "add nothing around them" not in flat_text
    assert "the words written for it below" not in flat_text
    assert ("| Question | What it is, its terms in plain words | The options | Recommend, and why | What the answer "
            "changes |") in text
    assert "neither is said to the owner unless they ask" in flat_text
    assert ("reminded in one line at the end of the next message** (`Still open: A2 families`), never asked again "
            "in full") in flat_text
    # The opening findings hold only what the owner must confirm or what changes an answer.
    assert ("only what stops the setup and the facts it will write that no question asks (§2), one line each; details "
            "only when asked") in flat_text
    assert "**The opening findings** have a frame too, two parts under their names in bold:" in flat_text
    assert "- **What I found**: one line per fact the repository has" in flat_text
    assert "A kind the repository lacks gets no line" in flat_text
    assert "- **Watch out**: only when warranted, two lines at most each: what stops the setup" in flat_text
    assert "what in this repository the questions will turn on" in flat_text
    assert "The message starts at What I found." in flat_text
    # A2 proposes the families and B1 asks its three smaller choices in the question itself, so neither costs a round.
    assert "ask for the families in their own question" not in flat_text
    assert "proposed beside the status file, they cost the owner no round of their own" in flat_text
    assert ("The three smaller choices are always asked, in one line with their suggestion, whatever cut is suggested") \
        in flat_text
    assert "B1's Watch out says what in this repository a cut would make public" in flat_text
    assert "Before asking B1" not in flat_text
    assert "C3 and D1 have no frame: each is said under its label in the words given here." in flat_text
    # No reference by the old numbers is left, and every reference outside the table names a question that exists.
    assert not re.search(r"\bquestions? \d", text)
    prose = "\n".join(ln for ln in text.splitlines() if not ln.startswith("|"))
    refs = set(re.findall(r"\b([A-Z]\d)\b", prose))
    assert refs and refs <= set(ids), refs
    rows = dict(zip(ids, re.findall(r"^\| [A-Z]\d · .*$", text, re.M)))
    assert rows["C2"].startswith("| C2 · What the agent sends out on your behalf | Pushes, tags, releases, issues, "
                                 "pull requests, comments, posts")
    assert "(`outward`, `attribution`)" in rows["C2"] and "`gated`" in rows["C2"]
    assert "becomes one sentence in AGENTS.md" in rows["C3"] and "keeps some by number" in rows["C3"]
    # C3's rule for the agent: no candidate the session skill leaves to the owner everywhere; one an earlier answer
    # covers is named with that answer.
    assert ("Do not propose an action that `session` §2 already leaves to the owner in every project (scope, "
            "priorities, cost, anything irreversible or public, a change to a recorded ruling)") in rows["C3"]
    assert "already covered by B1 or C2, say which" in rows["C3"] and "none that §2 or C2" not in rows["C3"]
    # What the owner reads for C3, as ruled; the candidates are found in each repository, so no sample is in the skill.
    assert ('"Actions I always ask you about first. You already decided which parts of the repository are public (B1), '
            "and what I may send out under your name (C2). Here you can name actions in this repository that I must "
            "never take on my own; your list becomes one line in AGENTS.md. From the repository, these look worth "
            "naming: [the candidates, one line each with why; when one is already covered by an earlier answer, say "
            'which]. Keep any by number, add your own, or answer none."') in flat_text
    for sample in ("new dependency", "live database", "passwords"):
        assert sample not in text, sample
    # The old instruction file has its own step before A1, which replaced the invariants question: its sections each
    # get a place, confirmed once; the frame is the skill's, the lines are filled at each run.
    assert rows["A3"].startswith("| A3 · This machine |") and "nvariants already written" not in text
    unquoted = flat(re.sub(r"^> ?", "", text, flags=re.M))
    step = unquoted[unquoted.index("**The old instruction file, before A1.**"):
                    unquoted.index("The table gives each question's matter")]
    assert "no two lines share a section and a place" in step
    assert "the owner confirms or changes any line, once, and it is not asked again" in step
    assert ("Your existing CLAUDE.md. The setup replaces it with a one-line `@AGENTS.md`, and each part of it is "
            "carried to where Airone Giallo keeps that kind of thing.") in step
    assert "\n> Your CLAUDE.md is backed up, unchanged, as `archive/CLAUDE-before-setup.md`.\n" in text
    assert ('Here is where each part would go: [numbered, one line per section: "<section>" → <place>]. Confirm, or '
            "change any line.") in step
    assert "removes the file from the public folder after backing it up in the workspace's archive" in step
    for place in ("`AGENTS.md`: rules for how agents work here", "`docs/invariants.md`: rules the code depends on",
                  "`docs/`: what the system is", "`ai-docs/guides/`: how a thing is done here",
                  "the status file or `plan/`: open work", "`RATIONALE.md`: where a rule came from",
                  "dropped: what no longer holds, with why", "elsewhere: a place the agent names, with why"):
        assert place in step, place
    assert "Never place as an invariant what the file does not state as one" in step
    # The two-repository form moves the owner's folder whole, registered in place, as the setup's last act: one
    # session, started in the folder, and nothing after the move but commands with absolute paths.
    assert "moves, whole, into a new workspace, and the move is the setup's last act" in flat_text
    assert "A Claude Code session is bound to the folder it started in" in flat_text
    last = text[text.index("**In the two-repository form the move comes last**"):text.index("## 5.")]
    commands = re.search(r"```sh\n(.*?)```", last, re.S).group(1).splitlines()
    assert commands[0] == "mv <dir>/<folder> <dir>/<folder>-nido/<folder>", commands
    assert all(c.startswith(("mv <dir>/", "git -C <dir>/", "check-links --root <dir>/")) for c in commands), commands
    assert "never `git submodule absorbgitdirs`" in flat_text
    assert "stale copy" not in text and "second clone" not in text
    assert "new session opened at" not in text and "ANSWERS.json and the prompt" not in text
    assert "telling them to open the next session at `<folder>-nido`" in flat(last)
    # The carry-over is pending work in the handoff until each part is carried.
    assert "delete that line from the handoff's next step" in flat_text
    # The agent tool's files: their own step in the two-repository form, never the old-file step's, kept plain.
    agent = flat_text[flat_text.index("**In the two-repository form the agent tool's files move to the workspace's "
                                      "root.**"):flat_text.index("**Any other existing file stops")]
    assert "`.claude/` (settings, commands, agents, skills) or `.mcp.json`" in agent
    assert "before the folder itself moves" in agent
    assert "a `.claude/CLAUDE.md` in it is the old instruction file's, backed up and removed first, so it never moves" \
        in agent
    assert "The same holds with `agent_layer: both`" in agent
    assert "already at the workspace's root stops the run" in agent
    assert "In the one-repository forms they stay where they are" in agent
    assert "moves nothing of the owner's but the agent tool's `.claude/` and `.mcp.json`" in flat_text
    # The one thing the script deletes: an old instruction file whose backup read back equal to it.
    assert ("deletes nothing but an old instruction file of the owner's repository once its backup has been read back "
            "equal to it") in flat_text
    # D1 is a closed box: its row and its paragraph say nothing of what the layer holds or how many rules it has.
    for inside in ("omment", "fix", "rreversible", "three", "two", "Four-Hands", "Conductor"):
        assert inside not in rows["D1"], inside
    assert "**D1 is a closed box.**" in text
    assert "without describing what the rules say or how many there are" in flat_text
    assert "saying that without a yes they are left out" in flat_text
    # The setup's close lists its own choices whatever the mode.
    assert "Then, in either mode, list for the owner the choices the setup made that they did not" in flat_text
    # Every word the script starts a report line with is explained where the skill shows the two runs.
    runs = text[text.index("1. The dry run, which writes nothing"):text.index("What it writes, the dry run lists")]
    for word in ("CREATE", "REPLACE", "APPEND", "KEEP", "BACKUP", "REMOVE", "MOVE", "DONE", "KEPT", "SKIPPED",
                 "FAILED"):
        assert f"`{word}`" in runs, word


# ---------------------------------------------------------------- the template syntax

def test_render_values_sections_and_standalone_tags():
    text = "a {{x}}\n{{#on}}\nkept\n{{/on}}\n{{#off}}\ndropped\n{{/off}}\n{{^off}}inverse{{/off}} {{items}}\n"
    assert sc.render(text, {"x": "1", "on": True, "off": "", "items": ["p", "q"]}) == "a 1\nkept\ninverse p, q\n"


def test_render_refuses_a_slot_with_no_answer():
    with pytest.raises(KeyError):
        sc.render("{{missing}}", {})
    with pytest.raises(KeyError):
        sc.render("{{#missing}}x{{/missing}}", {})
