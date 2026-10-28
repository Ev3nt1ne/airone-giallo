"""Tests for move-paths, on a throwaway repository with known answers: what is rewritten and how, what is left and
reported, the archive's guard and its log, and the refusals."""

import contextlib
import importlib.util
import io
import subprocess
from pathlib import Path

import pytest

import move_paths as mp
from conftest import Repo, run_tool

KIT = Path(__file__).resolve().parents[2]
P = "plan/phase-9"
FILES = {
    # a note that stays, linking to what moves
    f"{P}/notes.md": ("Run [the script](build.sh), read [its output](runs.txt#top), the [laptop runs](runs-laptop.txt),"
                      " the [samples](samples/), one [sample](samples/f.txt), and [the plan](../plan.md).\n"
                      "Bare name: build.sh; and runs.txt.gz is another file.\n"
                      "Shown: [`samples/g.txt`](samples/g.txt) and [`build.sh`](build.sh).\n"),
    "plan/plan.md": "# Plan\n",
    # a script that moves, naming its output by its path from the top and by its own folder
    f"{P}/build.sh": 'OUT=${OUT:-plan/phase-9/runs.txt}\ncat "$(dirname "$0")/runs.txt"\n',
    # a note that moves with it: its own links follow
    f"{P}/build-notes.md": "See [the plan](../plan.md) and [the notes](notes.md).\n",
    # raw output naming its old path: never edited
    f"{P}/runs.txt": "written by plan/phase-9/build.sh to plan/phase-9/runs.txt\n",
    f"{P}/runs-laptop.txt": "laptop\n",
    f"{P}/runs.txt.gz": "",
    f"{P}/samples/f.txt": "f\n",
    f"{P}/samples/g.txt": "g\n",
    f"{P}/samples/m.yaml": "by: plan/phase-9/build.sh\n",
    # live files elsewhere
    "docs/h.md": ("See [x](../plan/phase-9/build.sh) and plan/phase-9/build.sh, plan/phase-9/samples/ too, and"
                  " ../plan/phase-9/build.sh.\n"
                  "Shown: [`../plan/phase-9/build.sh`](../plan/phase-9/build.sh), [`build.sh`](../plan/phase-9/build.sh).\n"
                  '<img src="../plan/phase-9/samples/f.txt">\n'),
    "AGENTS.md": "Probe: [`build.sh`](plan/phase-9/build.sh); the plan/ folder, the plan itself.\n",
    "ci/checks.yml": "run: plan/phase-9/build.sh at 4\nkeep: plan/phase-9/runs.txt.gz\n",
    "ci/run.toml": 'script = "./plan/phase-9/build.sh"\n',
    "site/index.html": '<a href="../plan/phase-9/build-notes.md">notes</a>\n',
    "data/elsewhere.txt": "plan/phase-9/build.sh\n",
    # the archive
    "archive/LOG.md": ("# Log\n\n## Changes made to archived files\n\n"
                       "| Date | File | What | Why, and who decided | Commit |\n|---|---|---|---|---|\n\n"
                       "## Vocabulary conflicts left uncorrected\n\n"
                       "| Date | Kind | Old | Now | Where the current meaning is defined |\n|---|---|---|---|---|\n"),
    "archive/README.md": "The [log](LOG.md); [the script](../plan/phase-9/build.sh).\n",
    "archive/r.md": "Ran [it](../plan/phase-9/build.sh); see plan/phase-9/build.sh.\n",
    "archive/s.md": "Also [`../plan/phase-9/build.sh`](../plan/phase-9/build.sh).\n",
    "archive/t.md": "Only [the notes](../plan/phase-9/notes.md), which stay.\n",
}
F = f"{P}/measurements"
TABLE = [
    (f"{P}/build.sh", f"{F}/scripts/build.sh", ""),
    (f"{P}/build-notes.md", f"{F}/build-notes.md", ""),
    (f"{P}/runs.txt", f"{F}/runs/runs.txt", "no"),
    (f"{P}/runs-laptop.txt", f"{F}/runs/runs-laptop.txt", "no"),
    (f"{P}/samples", f"{F}/samples", "no"),
]


def row(file):
    return f"| 2026-03-02 | `{file}` | a link re-pointed after a move | the owner, at the move | `HEAD` |"


def with_rows(*files):
    text = FILES["archive/LOG.md"]
    head = "| Date | File | What | Why, and who decided | Commit |\n|---|---|---|---|---|\n"
    return text.replace(head, head + "".join(row(f) + "\n" for f in files))


@pytest.fixture
def tree(repo):
    repo.write(FILES)
    (repo.root / f"{P}/build.sh").chmod(0o755)
    repo.commit()
    table = repo.root.parent / "moves.tsv"
    table.write_text("# a comment\n" + "".join(f"{o}\t{n}" + (f"\t{e}" if e else "") + "\n" for o, n, e in TABLE))
    repo.table = table
    return repo


def plan(repo, frozen_ok=(), archives=("archive",)):
    files, subs = mp.at.tracked(repo.root)
    moves, keep = mp.expand(mp.read_table(repo.table), files)
    p = mp.Plan(repo.root, moves, keep, files, subs, list(archives), set(frozen_ok))
    p.build()
    return p


def status(repo):
    return subprocess.run(["git", "status", "--short"], cwd=repo.root, capture_output=True, text=True).stdout


def test_a_dry_run_changes_nothing(tree):
    before = {p: tree.read(p) for p in FILES}
    code, out, _ = run_tool("move_paths", "--table", str(tree.table), cwd=tree.root)
    assert code == 0, out
    assert "dry run: nothing changed" in out
    assert {p: tree.read(p) for p in FILES} == before and status(tree) == ""


def test_apply_moves_and_rewrites(tree):
    code, out, _ = run_tool("move_paths", "--table", str(tree.table), "--apply", cwd=tree.root)
    assert code == 0, out
    note = tree.read(f"{P}/notes.md")
    assert "[the script](measurements/scripts/build.sh)" in note
    assert "[its output](measurements/runs/runs.txt#top)" in note                 # the anchor kept
    assert "[laptop runs](measurements/runs/runs-laptop.txt)" in note             # a name sharing a prefix
    assert "[samples](measurements/samples/)" in note                             # a folder moved whole
    assert "[sample](measurements/samples/f.txt)" in note
    assert "[the plan](../plan.md)" in note                                       # not moved: unchanged
    assert ("Shown: [`measurements/samples/g.txt`](measurements/samples/g.txt) "
            "and [`build.sh`](measurements/scripts/build.sh).") in note           # an old path shown is updated
    assert "Bare name: build.sh; and runs.txt.gz is another file." in note        # a bare name stays
    # a moved file's own links follow its new place
    assert tree.read(f"{F}/build-notes.md") == "See [the plan](../../plan.md) and [the notes](../notes.md).\n"
    # a moved script: its path from the top is rewritten, its own-folder lookup is not
    assert tree.read(f"{F}/scripts/build.sh") == ('OUT=${OUT:-plan/phase-9/measurements/runs/runs.txt}\n'
                                                  'cat "$(dirname "$0")/runs.txt"\n')
    assert (tree.root / f"{F}/scripts/build.sh").stat().st_mode & 0o100           # still executable
    # raw output and data: untouched
    assert tree.read(f"{F}/runs/runs.txt") == FILES[f"{P}/runs.txt"]
    assert tree.read(f"{F}/samples/m.yaml") == FILES[f"{P}/samples/m.yaml"]
    assert tree.read("data/elsewhere.txt") == FILES["data/elsewhere.txt"]
    # live files elsewhere: links, paths from the top, relative paths, HTML
    assert tree.read("docs/h.md") == (
        "See [x](../plan/phase-9/measurements/scripts/build.sh) and plan/phase-9/measurements/scripts/build.sh,"
        " plan/phase-9/measurements/samples/ too, and ../plan/phase-9/measurements/scripts/build.sh.\n"
        "Shown: [`../plan/phase-9/measurements/scripts/build.sh`](../plan/phase-9/measurements/scripts/build.sh),"
        " [`build.sh`](../plan/phase-9/measurements/scripts/build.sh).\n"
        '<img src="../plan/phase-9/measurements/samples/f.txt">\n')
    assert tree.read("AGENTS.md") == ("Probe: [`build.sh`](plan/phase-9/measurements/scripts/build.sh); the plan/ "
                                      "folder, the plan itself.\n")
    assert tree.read("ci/checks.yml") == ("run: plan/phase-9/measurements/scripts/build.sh at 4\n"
                                          "keep: plan/phase-9/runs.txt.gz\n")
    assert tree.read("ci/run.toml") == 'script = "./plan/phase-9/measurements/scripts/build.sh"\n'
    assert tree.read("site/index.html") == '<a href="../plan/phase-9/measurements/build-notes.md">notes</a>\n'
    # the archive: nothing in it edited; its index is a live file
    for f in ("archive/r.md", "archive/s.md", "archive/t.md", "archive/LOG.md"):
        assert tree.read(f) == FILES[f], f
    assert tree.read("archive/README.md") == ("The [log](LOG.md); [the script]"
                                              "(../plan/phase-9/measurements/scripts/build.sh).\n")
    assert f"R  {P}/runs.txt -> {F}/runs/runs.txt" in status(tree)                # git sees the rename


def test_every_edit_is_reported_with_its_line(tree):
    out = io.StringIO()
    plan(tree).report(out)
    text = out.getvalue()
    assert f"link        docs/h.md:1: ../plan/phase-9/build.sh -> ../plan/phase-9/measurements/scripts/build.sh" in text
    assert "path        ci/checks.yml:1: plan/phase-9/build.sh -> plan/phase-9/measurements/scripts/build.sh" in text
    assert f"folder {P}/samples/ -> {F}/samples/" in text


def test_the_archives_dead_links_and_the_mentions_are_reported(tree):
    p = plan(tree)
    assert sorted((f, t) for f, _, t in p.dead_frozen) == [("archive/r.md", "../plan/phase-9/build.sh"),
                                                          ("archive/s.md", "../plan/phase-9/build.sh")]
    found = {(f, w) for f, _, w in p.mentions}
    assert (f"{P}/notes.md", "build.sh") in found                                 # a bare name in prose
    assert (f"{P}/build.sh", "/runs.txt") in found                                # the own-folder lookup
    assert (f"{P}/notes.md", "runs.txt") not in found                             # .gz is another file
    assert not {f for f, _ in found if f.startswith("archive/") and f != "archive/README.md"}
    assert "docs/h.md" not in {f for f, w in found if "/" in w}                   # its paths were rewritten
    assert p.refusals == []


def test_a_frozen_file_is_re_pointed_with_its_row_and_its_prose_kept(tree):
    tree.write({"archive/LOG.md": with_rows("r.md")}).stage()
    code, out, _ = run_tool("move_paths", "--table", str(tree.table), "--frozen-ok", "archive/r.md", "--apply",
                            cwd=tree.root)
    assert code == 0, out
    assert tree.read("archive/r.md") == ("Ran [it](../plan/phase-9/measurements/scripts/build.sh); see "
                                         "plan/phase-9/build.sh.\n")
    assert tree.read("archive/s.md") == FILES["archive/s.md"]


def test_a_frozen_file_without_its_row_is_refused_and_nothing_moves(tree):
    code, out, _ = run_tool("move_paths", "--table", str(tree.table), "--frozen-ok", "archive/r.md", "--apply",
                            cwd=tree.root)
    assert code == 1
    assert "REFUSED: archive/r.md is archived and this plan changes it" in out
    assert (tree.root / f"{P}/build.sh").exists() and status(tree) == ""


def test_a_row_already_committed_is_not_a_new_row(tree):
    tree.write({"archive/LOG.md": with_rows("r.md")})
    tree.commit("an older change to r.md")
    p = plan(tree, frozen_ok={"archive/r.md"})
    assert any("archive/r.md" in r for r in p.refusals)


def test_a_row_naming_another_file_does_not_count(tree):
    tree.write({"archive/LOG.md": with_rows("s.md")}).stage()
    p = plan(tree, frozen_ok={"archive/r.md"})
    assert any("archive/r.md" in r for r in p.refusals)


def test_moving_an_archived_file_needs_its_row(repo):
    repo.write({"archive/LOG.md": FILES["archive/LOG.md"], "archive/old.md": "# Old\n"}).commit()
    code, out, _ = run_tool("move_paths", "archive/old.md", "archive/2026/old.md", "--apply", cwd=repo.root)
    assert code == 1 and "needs --frozen-ok" in out
    code, out, _ = run_tool("move_paths", "archive/old.md", "archive/2026/old.md", "--frozen-ok", "archive/old.md",
                            "--apply", cwd=repo.root)
    assert code == 1 and "no new row" in out
    repo.write({"archive/LOG.md": with_rows("2026/old.md")}).stage()       # a row naming where it goes counts too
    code, out, _ = run_tool("move_paths", "archive/old.md", "archive/2026/old.md", "--frozen-ok", "archive/old.md",
                            cwd=repo.root)
    assert code == 0, out
    repo.write({"archive/LOG.md": with_rows("old.md")}).stage()
    code, out, _ = run_tool("move_paths", "archive/old.md", "archive/2026/old.md", "--frozen-ok", "archive/old.md",
                            "--apply", cwd=repo.root)
    assert code == 0, out
    assert (repo.root / "archive/2026/old.md").is_file()


def test_a_file_moved_into_the_archive_is_not_edited(repo):
    repo.write({"docs/a.md": "[b](b.md)\n", "docs/b.md": "# B\n", "docs/c.md": "[a](a.md)\n"}).commit()
    code, out, _ = run_tool("move_paths", "docs/a.md", "archive/a.md", "--apply", cwd=repo.root)
    assert code == 0, out
    assert repo.read("archive/a.md") == "[b](b.md)\n"                             # its link left as it was
    assert repo.read("docs/c.md") == "[a](../archive/a.md)\n"
    assert "`archived:` stamp by hand" in out


def test_both_readings_of_the_log_agree(tree, monkeypatch):
    """The archive's checker, read from the kit when it is there, and the fallback give the same verdicts."""
    source = KIT / "archive" / "tools" / "check_archive.py"
    if not source.is_file():
        pytest.skip("the archive's checker is not beside the tools")
    spec = importlib.util.spec_from_file_location("check_archive", source)
    archive = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(archive)
    head = "| Date | File | What | Why, and who decided | Commit |\n|---|---|---|---|---|\n"
    hidden = with_rows("r.md").replace(head, "<!-- an example, a table of its own:\n" + head + row("s.md") +
                                       "\n-->\n\n" + head)
    tree.write({"archive/LOG.md": hidden}).stage()
    verdicts = []
    for reader in (archive, None):
        monkeypatch.setattr(mp, "_archive", reader)
        verdicts.append((plan(tree, frozen_ok={"archive/r.md"}).refusals,
                         plan(tree, frozen_ok={"archive/r.md", "archive/s.md"}).refusals))
    assert verdicts[0] == verdicts[1]
    # r.md has its row; the row naming s.md is an example table inside a comment, which neither reading counts
    assert verdicts[0][0] == [] and len(verdicts[0][1]) == 1 and "archive/s.md" in verdicts[0][1][0]


def test_a_folder_at_the_top_is_matched_only_with_its_slash(repo):
    repo.write({"plan/a.md": "# A\n", "docs/x.md": "The plan/ folder holds plan/a.md; the plan is short.\n",
                "README.md": "See [the plan](plan/a.md).\n"}).commit()
    code, out, _ = run_tool("move_paths", "plan", "roadmap", "--apply", cwd=repo.root)
    assert code == 0, out
    assert repo.read("docs/x.md") == "The roadmap/ folder holds roadmap/a.md; the plan is short.\n"
    assert repo.read("README.md") == "See [the plan](roadmap/a.md).\n"


def test_a_file_at_the_top_is_a_mention_unless_linked(repo):
    repo.write({"NOTES.md": "# N\n", "docs/x.md": "NOTES.md, and [the notes](../NOTES.md).\n"}).commit()
    code, out, _ = run_tool("move_paths", "NOTES.md", "docs/notes.md", "--apply", cwd=repo.root)
    assert code == 0, out
    assert repo.read("docs/x.md") == "NOTES.md, and [the notes](notes.md).\n"
    assert "docs/x.md:1: NOTES.md" in out


def test_a_nested_repository_writes_its_paths_from_its_own_top(repo):
    repo.nest("pub", {"docs/a.md": "# A\n", "docs/b.md": "See docs/a.md and [a](a.md).\n"})
    repo.write({"ai-docs/s.md": "See pub/docs/a.md and [a](../pub/docs/a.md).\n"}).commit()
    code, out, _ = run_tool("move_paths", "pub/docs/a.md", "pub/docs/spec.md", "--apply", cwd=repo.root)
    assert code == 0, out
    assert repo.read("pub/docs/b.md") == "See docs/spec.md and [a](spec.md).\n"
    assert repo.read("ai-docs/s.md") == "See pub/docs/spec.md and [a](../pub/docs/spec.md).\n"
    assert "R  docs/a.md -> docs/spec.md" in subprocess.run(["git", "status", "--short"], cwd=repo.root / "pub",
                                                            capture_output=True, text=True).stdout


def test_the_refusals(tree):
    def refused(*args):
        code, out, _ = run_tool("move_paths", *args, cwd=tree.root)
        return code, out

    assert refused("plan/nope.md", "plan/x.md")[0] == 1                         # not tracked
    code, out = refused(f"{P}/build.sh", f"{P}/notes.md")
    assert code == 1 and "already exists" in out
    tree.write({".gitmodules": '[submodule "pub"]\n\tpath = pub\n\turl = ../pub.git\n'})
    Repo(tree.root / "pub").write({"x.md": "x\n"}).commit()
    code, out = refused(f"{P}/build-notes.md", "pub/notes.md", "--apply")
    assert code == 1 and "crosses from one repository into another" in out
    code, out = refused("--table", str(tree.table), "--frozen-ok", "docs/h.md")
    assert code == 1 and "--frozen-ok takes a tracked file inside the archive" in out


def test_changes_not_staged_stop_the_apply(tree):
    tree.write({"docs/h.md": FILES["docs/h.md"] + "an edit in progress\n"})
    code, out, _ = run_tool("move_paths", "--table", str(tree.table), "--apply", cwd=tree.root)
    assert code == 1 and "changes not staged in docs/h.md" in out
    assert (tree.root / f"{P}/build.sh").exists()


def test_bad_tables_and_arguments_exit_two(tree):
    for bad in ("only-one-column\n", f"{P}/build.sh\tx\tmaybe\n", f"{P}/build.sh\ta\n{P}/build.sh\tb\n",
                "../out.md\tx.md\n"):
        tree.table.write_text(bad)
        assert run_tool("move_paths", "--table", str(tree.table), cwd=tree.root)[0] == 2, bad
    assert run_tool("move_paths", "one", cwd=tree.root)[0] == 2
    assert run_tool("move_paths", "a", "b", "--table", str(tree.table), cwd=tree.root)[0] == 2


def test_a_table_may_separate_with_spaces(tree):
    tree.table.write_text(f"{P}/build-notes.md   {F}/build-notes.md\n")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert mp.main(["--table", str(tree.table), "--root", str(tree.root)]) == 0
    assert f"move {P}/build-notes.md -> {F}/build-notes.md" in out.getvalue()
