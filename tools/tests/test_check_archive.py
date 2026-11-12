"""Tests for check_archive.py, on invented archives in temporary git repositories with real commits; the committer's
date is set through the environment, so a stamp can be compared with the commit that moved its file in.

Run from the tools' folder: pytest
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

import check_archive as ca
from conftest import ENV, GIT, PASSED

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
TEMPLATES = HERE.parents[1] / "skills" / "setup" / "templates" / "tree" / "archive"

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

DAY1, DAY2 = "2026-03-01T10:00:00+00:00", "2026-03-05T09:00:00+00:00"
GLOSSARY = "`docs/glossary.md`"


def doc(stamp=DAY1, body="The register holds the work.\nA stage is a phase of the plan.\n"):
    head = "---\ntitle: An old design\n" + (f"archived: {stamp}\n" if stamp else "") + "---\n\n"
    return head + "# An old design\n\n" + body


def change(file, commit="`HEAD`", day="2026-03-06", what="a link rebuilt after a move", why="the owner, at the move"):
    return f"| {day} | `{file}` | {what} | {why} | {commit} |"


def conflict(when, kind="renamed", old="the register", now="the status file", where=GLOSSARY):
    return f"| {when} | {kind} | {old} | {now} | {where} |"


def log(changes=(), conflicts=()):
    """The setup's template, with rows inserted under each table's header, newest first as given."""
    lines = (TEMPLATES / "LOG.md").read_text(encoding="utf-8").split("\n")
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        if i and lines[i - 1].startswith("| Date | File |") and line.startswith("|---"):
            out += list(changes)
        if i and lines[i - 1].startswith("| Date | Kind |") and line.startswith("|---"):
            out += list(conflicts)
    return "\n".join(out)


class Repo:
    """A project folder with an archive, a glossary and a git repository; every commit dated as asked."""

    def __init__(self, root, git=True):
        self.root, self.archive = root, root / "archive"
        self.archive.mkdir(parents=True)
        self.write("docs/glossary.md", "# Glossary\n")
        self.write("archive/README.md", "# The archive\n\nThe register was here.\n")
        self.write("archive/LOG.md", log())
        if git:
            self.git("init", "-q")
            self.commit("start", DAY1)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def git(self, *args, when=DAY1):
        env = dict(ENV, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
        p = subprocess.run(["git", *args], cwd=self.root, env=env, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        return p.stdout

    def commit(self, message, when):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message, when=when)

    def archive_file(self, name, when, stamp=None, body=None):
        """Write a live document, then move it into the archive with its stamp in one commit dated `when`."""
        self.write(f"docs/{name}", doc(stamp=None, **({"body": body} if body else {})))
        self.commit(f"write {name}", "2026-02-01T08:00:00+00:00")
        self.git("mv", f"docs/{name}", f"archive/{name}")
        moved = self.archive / name
        moved.write_text(moved.read_text().replace("---\ntitle:", f"---\narchived: {stamp or when}\ntitle:", 1))
        self.commit(f"archive {name}", when)


def run(repo, now=None):
    return ca.check(repo.archive, now=now)


def only_error(errors, *words):
    assert len(errors) == 1, errors
    for w in words:
        assert w in errors[0], errors[0]


def cli(*args, cwd):
    return subprocess.run([sys.executable, str(SRC / "check_archive.py"), *args], cwd=cwd, capture_output=True,
                          text=True)


# --- the check: stamps ---------------------------------------------------------------------------------------------

@needs_git
def test_a_clean_archive_passes(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY1)
    repo.archive_file("review.md", DAY2)
    errors, notes, not_run, summary = run(repo)
    assert (errors, notes, not_run) == ([], [], [])
    assert "2 archived file(s)" in summary


@needs_git
def test_the_template_passes_and_the_command_exits_zero(tmp_path):
    repo = Repo(tmp_path)
    r = cli(cwd=repo.root)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 error(s)" in r.stdout and "NOT RUN" not in r.stdout


@needs_git
def test_a_missing_stamp_is_an_error(tmp_path):
    repo = Repo(tmp_path)
    repo.write("archive/old.md", doc(stamp=None))
    repo.commit("archive old.md without its stamp", DAY1)
    only_error(run(repo)[0], "old.md", "no `archived:` stamp")


@needs_git
def test_a_stamp_not_in_the_frontmatter_form_is_an_error(tmp_path):
    repo = Repo(tmp_path)
    repo.write("archive/old.md", doc(stamp="2026-03-01"))
    repo.commit("archive old.md", DAY1)
    only_error(run(repo)[0], "old.md", "is not a time")


@needs_git
def test_a_stamp_that_disagrees_with_git_is_an_error_naming_both(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY2, stamp=DAY1)
    only_error(run(repo)[0], "design.md", DAY1, DAY2)


@needs_git
def test_a_stamp_written_before_midnight_and_committed_after_agrees(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("late.md", "2026-03-02T00:10:00+00:00", stamp="2026-03-01T23:50:00+00:00")
    repo.archive_file("later.md", "2026-03-03T00:10:00+00:00", stamp="2026-03-01T23:50:00+00:00")
    only_error(run(repo)[0], "later.md")


@needs_git
def test_a_rename_inside_the_archive_keeps_the_time_the_file_entered_it(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY1)
    repo.git("mv", "archive/design.md", "archive/design-v1.md")
    repo.write("archive/LOG.md", log([change("design-v1.md", what="renamed from design.md")]))
    repo.commit("rename design.md inside the archive", DAY2)
    assert run(repo)[0] == []


@needs_git
def test_a_file_being_archived_is_compared_with_now(tmp_path):
    repo = Repo(tmp_path)
    now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    repo.write("archive/today.md", doc(stamp="2026-04-01T11:58:00+00:00"))
    repo.write("archive/stale.md", doc(stamp=DAY1))
    repo.git("add", "-A")
    only_error(run(repo, now=now)[0], "stale.md", "the commit being made")


@needs_git
def test_a_file_whose_name_is_not_ascii_is_read_by_its_name(tmp_path):
    # git quotes such a name in its output unless told not to; the check still finds the file tracked and compared.
    repo = Repo(tmp_path)
    repo.archive_file("café.md", DAY1)
    repo.archive_file("naïve.md", DAY2, stamp=DAY1)
    errors, notes, _, _ = run(repo)
    assert notes == [], notes
    only_error(errors, "naïve.md", DAY1, DAY2)


@needs_git
def test_a_rename_inside_the_archive_of_a_file_whose_name_is_not_ascii_is_followed(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("café.md", DAY1)
    repo.git("mv", "archive/café.md", "archive/café-v1.md")
    repo.write("archive/LOG.md", log([change("café-v1.md", what="renamed from café.md")]))
    repo.commit("rename café.md inside the archive", DAY2)
    assert run(repo)[:2] == ([], [])


@needs_git
def test_an_untracked_file_is_noted_not_compared(tmp_path):
    repo = Repo(tmp_path)
    repo.write("archive/loose.md", doc(stamp=DAY1))
    errors, notes, _, _ = run(repo)
    assert errors == [] and any("loose.md" in n and "not tracked" in n for n in notes)


# --- the check: staged changes and their rows -----------------------------------------------------------------------

@needs_git
def test_a_staged_edit_without_its_row_is_an_error(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY1)
    path = repo.archive / "design.md"
    path.write_text(path.read_text().replace("The register", "The status file"))
    repo.git("add", "-A")
    only_error(run(repo)[0], "archive/design.md", "modified", "no new row")


@needs_git
def test_a_staged_edit_with_its_new_row_passes(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY1)
    path = repo.archive / "design.md"
    path.write_text(path.read_text().replace("The register", "The status file"))
    repo.write("archive/LOG.md", log([change("design.md")]))
    repo.git("add", "-A")
    assert run(repo)[0] == []


@needs_git
def test_an_old_row_naming_the_file_does_not_cover_a_new_edit(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY1)
    repo.write("archive/LOG.md", log([change("design.md", commit="`a1b2c3d`")]))
    repo.commit("record an earlier change", DAY2)
    path = repo.archive / "design.md"
    path.write_text(path.read_text() + "\nOne more line.\n")
    repo.git("add", "-A")
    only_error(run(repo)[0], "design.md", "no new row")


@needs_git
def test_the_row_must_be_staged_not_only_written(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY1)
    path = repo.archive / "design.md"
    path.write_text(path.read_text() + "\nOne more line.\n")
    repo.git("add", "archive/design.md")
    repo.write("archive/LOG.md", log([change("design.md")]))
    only_error(run(repo)[0], "design.md", "no new row")


@needs_git
def test_a_row_may_name_the_file_with_the_archive_folder(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY1)
    path = repo.archive / "design.md"
    path.write_text(path.read_text() + "\nOne more line.\n")
    repo.write("archive/LOG.md", log([change("archive/design.md")]))
    repo.git("add", "-A")
    assert run(repo)[0] == []


@needs_git
def test_a_staged_deletion_needs_its_row(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY1)
    repo.git("rm", "-q", "archive/design.md")
    only_error(run(repo)[0], "archive/design.md", "deleted")
    repo.write("archive/LOG.md", log([change("design.md", what="removed: a copy of review.md")]))
    repo.git("add", "-A")
    assert run(repo)[0] == []


@needs_git
def test_a_staged_rename_needs_its_row(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY1)
    repo.git("mv", "archive/design.md", "archive/design-v1.md")
    only_error(run(repo)[0], "archive/design.md -> archive/design-v1.md", "renamed")
    repo.write("archive/LOG.md", log([change("design-v1.md", what="renamed from design.md")]))
    repo.git("add", "-A")
    assert run(repo)[0] == []


@needs_git
def test_a_staged_rename_of_a_file_whose_name_is_not_ascii_names_both_and_needs_its_row(tmp_path):
    repo = Repo(tmp_path)
    repo.archive_file("café.md", DAY1)
    repo.git("mv", "archive/café.md", "archive/café-v1.md")
    only_error(run(repo)[0], "archive/café.md -> archive/café-v1.md", "renamed")
    repo.write("archive/LOG.md", log([change("café-v1.md", what="renamed from café.md")]))
    repo.git("add", "-A")
    assert run(repo)[0] == []


@needs_git
def test_the_log_and_the_index_are_exempt(tmp_path):
    repo = Repo(tmp_path)
    repo.write("archive/README.md", "# The archive\n\nRewritten.\n")
    repo.write("archive/LOG.md", log(conflicts=[conflict(DAY2)]))
    repo.git("add", "-A")
    errors, notes, _, summary = run(repo)
    assert errors == [] and notes == []
    assert "0 archived file(s)" in summary


@needs_git
def test_an_archived_readme_in_a_subfolder_is_an_archived_file(tmp_path):
    repo = Repo(tmp_path)
    repo.write("archive/old-site/README.md", doc(stamp=None))
    repo.commit("archive a folder", DAY1)
    only_error(run(repo)[0], "old-site/README.md", "no `archived:` stamp")


# --- the check: the log's tables -----------------------------------------------------------------------------------

@needs_git
def test_conflict_rows_that_parse_pass(tmp_path):
    repo = Repo(tmp_path)
    repo.write("archive/LOG.md", log(conflicts=[
        conflict(DAY2, kind="**reused**", old='"stage": a phase', now='"stage": an environment'),
        conflict(DAY1, where="[the glossary](../docs/glossary.md#stage)"),
        conflict("2026-02-01T10:00:00+00:00", where="https://example.com/terms")]))
    repo.commit("log", DAY2)
    assert run(repo)[0] == []


@needs_git
@pytest.mark.parametrize("row, words", [
    pytest.param(conflict(DAY1, kind="retired"), ("kind 'retired'", "renamed, reused"), id="bad-kind"),
    pytest.param(conflict(DAY1, where="`docs/terms.md`"), ("docs/terms.md", "does not exist"), id="missing-path"),
    pytest.param(conflict(DAY1, where="[terms](terms.md)"), ("terms.md", "does not exist"), id="missing-link"),
    pytest.param(conflict(DAY1, where=""), ("no place",), id="no-place"),
    pytest.param(conflict("2026-03-01"), ("is not a time",), id="a-day-not-a-time"),
    pytest.param(conflict("2026-03-01T10:00:00+02:00"), ("is not a time",), id="another-offset"),
    pytest.param(conflict(DAY1, now=""), ("the now column is empty",), id="empty-now"),
    pytest.param(conflict(DAY1).rstrip("|").rsplit("|", 1)[0] + "|", ("4 cells where the table has 5",),
                 id="a-cell-short"),
])
def test_a_bad_conflict_row_is_an_error(tmp_path, row, words):
    repo = Repo(tmp_path)
    repo.write("archive/LOG.md", log(conflicts=[row]))
    repo.commit("log", DAY2)
    only_error(run(repo)[0], *words)


@needs_git
@pytest.mark.parametrize("row, words", [
    pytest.param(change("design.md", commit="`the last one`"), ("neither a commit hash nor HEAD",), id="bad-commit"),
    pytest.param(change("design.md", day="March 6"), ("is not a date",), id="bad-date"),
    pytest.param(change("design.md", why=""), ("why and who decided column is empty",), id="empty-why"),
])
def test_a_bad_change_row_is_an_error(tmp_path, row, words):
    repo = Repo(tmp_path)
    repo.write("archive/LOG.md", log([row]))
    repo.commit("log", DAY2)
    only_error(run(repo)[0], *words)


@needs_git
def test_a_missing_log_or_table_is_an_error(tmp_path):
    repo = Repo(tmp_path)
    (repo.archive / "LOG.md").unlink()
    only_error(run(repo)[0], "no log")
    repo.write("archive/LOG.md", log().split("## Vocabulary")[0])
    only_error(run(repo)[0], "no conflicts table")


@needs_git
def test_the_example_rows_in_comments_are_not_rows(tmp_path):
    repo = Repo(tmp_path)
    text = (repo.archive / "LOG.md").read_text()
    assert text.count("<!-- An example row") == 2
    errors, _, _, summary = run(repo)
    assert errors == [] and "0 change(s), 0 conflict(s)" in summary


@needs_git
def test_a_row_cut_off_from_its_table_is_an_error(tmp_path):
    repo = Repo(tmp_path)
    text = log(conflicts=[conflict(DAY2)]).replace("|---|---|---|---|---|\n| 2026-03-05", "|---|---|---|---|---|\n\n"
                                                                                       "| 2026-03-05")
    repo.write("archive/LOG.md", text)
    repo.commit("log", DAY2)
    only_error(run(repo)[0], "a row outside its table")


# --- read ----------------------------------------------------------------------------------------------------------

def read_out(repo, rel, capsys):
    code = ca.main(["--archive", str(repo.archive), "read", str(repo.archive / rel)])
    return code, capsys.readouterr().out


@needs_git
def test_read_lists_the_conflicts_after_the_freeze_oldest_first_with_reused_marked(tmp_path, capsys):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", "2026-03-05T12:00:00+00:00")
    repo.write("archive/LOG.md", log(conflicts=[
        conflict("2026-04-01T10:00:00+00:00", kind="reused", old='"stage": a phase', now='"stage": an environment'),
        conflict("2026-03-05T12:30:00+00:00", old="registry.yml", now="graph.yml"),
        conflict("2026-03-05T11:30:00+00:00", old="the ledger", now="the status file"),
        conflict("2026-03-05T12:00:00+00:00", old="the roster", now="the team file"),
        conflict("2026-02-01T10:00:00+00:00", old="hands-off", now="Conductor")]))
    code, out = read_out(repo, "design.md", capsys)
    assert code == 0, out
    assert "archived 2026-03-05T12:00:00+00:00" in out
    listed = [ln for ln in out.splitlines() if ln.startswith("  ")]
    assert len(listed) == 2, out
    assert "registry.yml" in listed[0] and "renamed" in listed[0]
    assert '"stage": a phase' in listed[1] and "REUSED" in listed[1]
    for absent in ("the ledger", "the roster", "hands-off"):
        assert absent not in out


@needs_git
def test_read_says_when_no_conflict_applies(tmp_path, capsys):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY2)
    repo.write("archive/LOG.md", log(conflicts=[conflict(DAY1)]))
    code, out = read_out(repo, "design.md", capsys)
    assert code == 0 and "no conflicts apply" in out


@needs_git
def test_read_takes_the_time_from_git_when_the_stamp_is_missing(tmp_path, capsys):
    repo = Repo(tmp_path)
    repo.write("archive/old.md", doc(stamp=None))
    repo.commit("archive old.md", DAY2)
    repo.write("archive/LOG.md", log(conflicts=[conflict("2026-03-06T10:00:00+00:00"), conflict(DAY1)]))
    code, out = read_out(repo, "old.md", capsys)
    assert code == 0 and f"git says it entered the archive {DAY2}" in out
    assert out.count("  2026-") == 1


def test_read_lists_every_conflict_and_exits_one_when_the_freeze_is_unknown(tmp_path, capsys):
    repo = Repo(tmp_path, git=False)
    repo.write("archive/old.md", doc(stamp=None))
    repo.write("archive/LOG.md", log(conflicts=[conflict(DAY2), conflict(DAY1)]))
    code, out = read_out(repo, "old.md", capsys)
    assert code == 1 and "unknown" in out and out.count("  2026-") == 2


@needs_git
def test_read_finds_the_archive_from_the_files_path_when_none_is_named(tmp_path, capsys):
    """Each repository has its own archive; `read` run from the workspace root on a file in the public repository's
    archive takes that archive, the nearest folder above the file holding a log, without --archive."""
    repo = Repo(tmp_path / "nido")
    public = Repo(tmp_path / "nido" / "inkwell")
    public.archive_file("design.md", DAY2)
    public.write("archive/LOG.md", log(conflicts=[conflict("2026-03-07T10:00:00+00:00")]))
    repo.write("archive/LOG.md", log(conflicts=[conflict(DAY1, old="the root's word")]))
    cwd = os.getcwd()
    os.chdir(repo.root)
    try:
        code = ca.main(["read", "inkwell/archive/design.md"])
    finally:
        os.chdir(cwd)
    out = capsys.readouterr().out
    assert code == 0 and "the register" in out and "the root's word" not in out, out
    # A file in no archive is refused with the default archive's name, as before.
    assert ca.main(["read", str(repo.root / "docs" / "glossary.md")]) == 2


def test_read_refuses_a_file_outside_the_archive(tmp_path, capsys):
    repo = Repo(tmp_path, git=False)
    assert ca.main(["--archive", str(repo.archive), "read", str(repo.root / "docs" / "glossary.md")]) == 2
    assert ca.main(["--archive", str(repo.archive), "read", str(repo.archive / "LOG.md")]) == 2


# --- rename --------------------------------------------------------------------------------------------------------

@needs_git
def test_rename_lists_every_whole_word_hit_with_the_stamp_and_changes_nothing(tmp_path, capsys):
    repo = Repo(tmp_path)
    repo.archive_file("design.md", DAY1, body="The Register holds the work.\nThe registers are elsewhere.\n")
    repo.archive_file("review.md", DAY2, body="Nothing here.\nWe asked the register.\n")
    repo.write("archive/LOG.md", log(conflicts=[conflict(DAY1, old="the register")]))
    before = {p: p.read_bytes() for p in repo.archive.rglob("*")}
    code = ca.main(["--archive", str(repo.archive), "rename", "register"])
    out = capsys.readouterr().out
    assert code == 0
    assert f"design.md (archived {DAY1})" in out and f"review.md (archived {DAY2})" in out
    assert "design.md:8: The Register holds the work." in out
    assert "review.md:9: We asked the register." in out
    assert "registers" not in out and "LOG.md" not in out
    assert "README.md:3: The register was here." in out
    assert out.count("change it:") == 3 and out.count("or leave it:") == 3
    assert "3 line(s) in 3 file(s)" in out
    assert {p: p.read_bytes() for p in repo.archive.rglob("*")} == before


def test_rename_with_no_hit_says_so_and_exits_zero(tmp_path, capsys):
    repo = Repo(tmp_path, git=False)
    repo.write("archive/design.md", doc())
    assert ca.main(["--archive", str(repo.archive), "rename", "ledger"]) == 0
    assert "no occurrence of 'ledger'" in capsys.readouterr().out


# --- without git, and the command ------------------------------------------------------------------------------------

def test_outside_a_repository_the_git_checks_are_not_run(tmp_path, capsys):
    repo = Repo(tmp_path, git=False)
    repo.write("archive/design.md", doc())
    errors, notes, not_run, _ = run(repo)
    assert errors == [] and len(not_run) == 1 and "not inside a git repository" in not_run[0]
    # A check that did not run is not a check that passed: the exit code says so.
    assert ca.main(["--archive", str(repo.archive)]) == 1
    out = capsys.readouterr().out
    assert "NOT RUN" in out and "1 check(s) not run" in out


def test_without_the_git_binary_the_git_checks_are_not_run(tmp_path, monkeypatch):
    repo = Repo(tmp_path, git=False)
    repo.write("archive/design.md", doc(stamp=None))
    monkeypatch.setattr(ca.shutil, "which", lambda name: None)
    errors, _, not_run, _ = run(repo)
    only_error(errors, "no `archived:` stamp")
    assert not_run and "git is not installed" in not_run[0]


@needs_git
def test_the_command_exits_one_on_an_error_and_two_on_bad_arguments(tmp_path):
    repo = Repo(tmp_path)
    repo.write("archive/old.md", doc(stamp=None))
    assert cli(cwd=repo.root).returncode == 1
    assert cli("--archive", "nowhere", cwd=repo.root).returncode == 2
    assert cli("read", cwd=repo.root).returncode == 2
    assert cli("shred", cwd=repo.root).returncode == 2
    r = cli("read", "archive/old.md", "--archive", "archive", cwd=repo.root)
    assert r.returncode == 1 and "unknown" in r.stdout, r.stdout + r.stderr
    repo.write("archive/old.md", doc())
    r = cli("read", "archive/old.md", "--archive", "archive", cwd=repo.root)
    assert r.returncode == 0 and "no conflicts apply" in r.stdout, r.stdout + r.stderr


def test_the_package_command_names_the_checker_main():
    tomllib = pytest.importorskip("tomllib")
    meta = tomllib.loads((HERE.parent / "pyproject.toml").read_text(encoding="utf-8"))
    module, _, func = meta["project"]["scripts"]["check-archive"].partition(":")
    layout = meta["tool"]["setuptools"]
    assert module in layout["py-modules"]
    assert (HERE.parent / layout["package-dir"][""] / f"{module}.py") == SRC / "check_archive.py"
    assert callable(getattr(ca, func, None))


def test_a_tests_subprocess_gets_the_named_variables_and_no_others():
    # The tests give git and the tools the variables named in conftest and the git ones they set; nothing else of
    # the machine's environment (a token, a remote's address) reaches a subprocess.
    assert set(ENV) <= set(PASSED) | set(GIT) and ENV.items() >= GIT.items()
