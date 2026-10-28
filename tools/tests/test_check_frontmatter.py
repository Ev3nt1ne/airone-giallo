"""Tests for check-frontmatter: the block's fields and forms, the markers, the scope and the archive, and the two
dates compared against HEAD or across a range."""

import contextlib
import io

import check_frontmatter as cf
from conftest import run_tool

CREATED, UPDATED = "2026-03-01", "2026-03-02T10:00:00+00:00"


def doc(body="The body.\n", **fields):
    values = {"title": "Saving", "description": "How a save survives a crash.", "type": "design",
              "created": CREATED, "updated": UPDATED}
    values.update(fields)
    head = "".join(f"{k}: {v}\n" for k, v in values.items() if v is not None)
    return f"---\n{head}---\n\n# Saving\n\n{body}"


def check(repo, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cf.main(["--root", str(repo.root), *args])
    return code, [line[len("error: "):] for line in buf.getvalue().splitlines() if line.startswith("error: ")]


def only(errors, *words):
    assert len(errors) == 1, errors
    for w in words:
        assert w in errors[0], errors[0]


RULES = cf.Rules()


# --- the block -------------------------------------------------------------------------------------------------------

def test_a_complete_block_passes():
    assert RULES.document("d.md", doc(status="active", tags="[saving, journal]")) == []
    assert RULES.document("d.md", doc(tags=None) .replace("type: design\n", "type: design\ntags:\n  - a\n  - b\n")) == []


def test_no_block_or_an_unclosed_one():
    only(RULES.document("d.md", "# Saving\n"), "no frontmatter block")
    only(RULES.document("d.md", "---\ntitle: x\n# never closed\n"), "no frontmatter block")


def test_each_required_field():
    for key in cf.REQUIRED:
        only(RULES.document("d.md", doc(**{key: None})), f"no `{key}:`")
    only(RULES.document("d.md", doc(title='""')), "`title:` is empty")


def test_the_dates_forms():
    only(RULES.document("d.md", doc(created="2026-03-01T10:00:00+00:00")), "`created:`", "not a date")
    only(RULES.document("d.md", doc(created="2026-02-30")), "`created:`", "not a date")
    only(RULES.document("d.md", doc(updated="2026-03-02")), "`updated:`", "not a time")
    only(RULES.document("d.md", doc(updated="2026-03-02T10:00:00+01:00")), "`updated:`", "not a time")
    only(RULES.document("d.md", doc(updated="2026-03-02T25:00:00+00:00")), "`updated:`", "not a time")
    only(RULES.document("d.md", doc(created="2026-03-05")), "is before `created:`")


def test_status_type_and_tags():
    only(RULES.document("d.md", doc(status="done")), "`status:`", "active, closed, superseded")
    assert cf.Rules(statuses=("live", "dead")).document("d.md", doc(status="live")) == []
    only(cf.Rules(types=("index", "log")).document("d.md", doc()), "`type:` 'design'")
    only(RULES.document("d.md", doc(tags="saving")), "not a list")
    only(RULES.document("d.md", doc(tags="[a, , b]")), "empty tag")
    only(RULES.document("d.md", doc(tags="[a, b, a]")), "repeats a")


def test_an_archived_stamp_outside_the_archive():
    only(RULES.document("d.md", doc(archived="2026-03-01T10:00:00+00:00")), "`archived:` outside the archive")


def test_the_change_of_plan_marker_keeps_its_one_meaning():
    good = doc(body="## \U0001F53B CHANGE OF PLAN: the journal goes\n\n| \U0001F53B | **Change of plan** |\n"
                    "\n```\n\U0001F53B in a fence\n```\n\n`\U0001F53B` in code\n\n\u270F\uFE0F it was two files.\n")
    assert RULES.document("d.md", good) == []
    only(RULES.document("d.md", doc(body="We changed course \U0001F53B here.\n")), "change-of-plan marker")
    only(RULES.document("d.md", doc(body="## \U0001F53B New plan\n")), "change-of-plan marker")
    only(RULES.document("d.md", doc(body="> \U0001F53B Superseded by the spec.\n")), "change-of-plan marker")
    assert cf.Rules(markers=False).document("d.md", doc(body="> \U0001F53B Superseded.\n")) == []


# --- the scope and the archive ---------------------------------------------------------------------------------------

def test_what_is_not_checked(repo):
    bare = "# no block\n"
    repo.write({"AGENTS.md": bare, "CLAUDE.md": bare, "RATIONALE.md": bare, ".claude/skills/x/SKILL.md": bare,
                "human-docs/n.md": bare, "sources/README.md": bare, ".github/ISSUE_TEMPLATE/bug.md": bare,
                "runs/out.md": bare, "notes.txt": bare, "docs/ok.md": doc()}).commit()
    assert check(repo, "--all", "--exempt", "runs/") == (0, [])
    code, errors = check(repo, "--all")
    only(errors, "runs/out.md")


def test_the_scope_holds_in_a_nested_repository(repo):
    repo.nest("pub", {"docs/a.md": "# no block\n", "AGENTS.md": "# contributors\n", "human-docs/n.md": "x\n"})
    repo.write({"ai-docs/b.md": doc()}).commit()
    code, errors = check(repo, "--all")
    only(errors, "pub/docs/a.md", "no frontmatter")


def test_the_archive_holds_only_its_stamp(repo):
    repo.write({
        "archive/good.md": "---\narchived: 2026-03-01T10:00:00+00:00\n---\n\nno title, no dates\n",
        "archive/none.md": "---\ntitle: x\n---\n",
        "archive/day.md": "---\narchived: 2026-03-01\n---\n",
        "archive/README.md": doc(), "archive/LOG.md": "# Log without a block\n",
    }).commit()
    code, errors = check(repo, "--all")
    assert code == 1 and len(errors) == 3, errors
    assert any(e.startswith("archive/none.md") and "no `archived:` stamp" in e for e in errors)
    assert any(e.startswith("archive/day.md") and "not a time" in e for e in errors)
    assert any(e.startswith("archive/LOG.md") and "no frontmatter" in e for e in errors)


def test_the_archive_can_be_named(repo):
    repo.write({"attic/old.md": "# no stamp\n", "archive/x.md": doc()}).commit()
    code, errors = check(repo, "--all", "--archive", "attic")
    only(errors, "attic/old.md", "no `archived:` stamp")


# --- the dates, against HEAD -----------------------------------------------------------------------------------------

def test_a_staged_change_without_a_new_stamp_is_refused_and_with_one_passes(repo):
    repo.write({"docs/a.md": doc()}).commit()
    repo.write({"docs/a.md": doc(body="Edited.\n")}).stage()
    code, errors = check(repo)
    only(errors, "docs/a.md", f"still reads {UPDATED}")
    repo.write({"docs/a.md": doc(body="Edited.\n", updated="2026-03-03T09:00:00+00:00")}).stage()
    assert check(repo) == (0, [])


def test_a_frontmatter_change_needs_the_stamp_too(repo):
    repo.write({"docs/a.md": doc()}).commit()
    repo.write({"docs/a.md": doc(title="Saving, again")}).stage()
    only(check(repo)[1], "still reads")


def test_the_stamp_never_moves_backwards_and_created_never_moves(repo):
    repo.write({"docs/a.md": doc()}).commit()
    repo.write({"docs/a.md": doc(body="Edited.\n", updated="2026-03-01T09:00:00+00:00")}).stage()
    only(check(repo)[1], "moved backwards")
    repo.write({"docs/a.md": doc(created="2026-02-01", updated="2026-03-03T09:00:00+00:00")}).stage()
    only(check(repo)[1], "`created:` moved from 2026-03-01 to 2026-02-01")


def test_a_renamed_document_is_compared_with_its_old_path(repo):
    repo.write({"docs/a.md": doc()}).commit()
    repo.git("mv", "docs/a.md", "docs/b.md")
    assert check(repo) == (0, [])
    repo.write({"docs/b.md": doc(created="2026-01-01")}).stage()
    errors = check(repo)[1]
    assert any("docs/b.md" in e and "`created:` moved" in e for e in errors), errors


def test_a_new_document_is_checked_for_its_block_only(repo):
    repo.write({"docs/a.md": doc()}).commit()
    repo.write({"docs/new.md": doc(), "docs/bad.md": "# none\n"}).stage()
    only(check(repo)[1], "docs/bad.md", "no frontmatter")


def test_the_first_commit_has_nothing_to_compare(repo):
    repo.write({"docs/a.md": doc(), "docs/bad.md": doc(updated="yesterday")}).stage()
    only(check(repo)[1], "docs/bad.md", "not a time")


def test_only_staged_documents_are_read(repo):
    repo.write({"docs/a.md": doc()}).commit()
    repo.write({"docs/a.md": doc(body="Edited, not staged.\n")})
    assert check(repo) == (0, [])


def test_a_staged_archived_file_is_held_to_its_stamp_only(repo):
    repo.write({"docs/a.md": doc()}).commit()
    repo.write({"archive/old.md": "---\ntitle: x\n---\n"}).stage()
    only(check(repo)[1], "archive/old.md", "stamp")


def test_a_range_compares_its_two_ends(repo):
    repo.write({"docs/a.md": doc()})
    first = repo.commit()
    repo.write({"docs/a.md": doc(body="Edited.\n")})
    repo.commit()
    code, errors = check(repo, "--range", f"{first}..HEAD")
    only(errors, "docs/a.md", "still reads")
    assert check(repo, "--range", f"{first}..{first}") == (0, [])


# --- the command -----------------------------------------------------------------------------------------------------

def test_the_command_exits_one_on_a_finding_and_two_on_a_bad_argument(repo, tmp_path):
    repo.write({"docs/a.md": doc(), "docs/b.md": "# none\n"}).commit()
    code, out, _ = run_tool("check_frontmatter", "--all", cwd=repo.root)
    assert code == 1 and "error: docs/b.md: no frontmatter" in out and "1 error(s)" in out
    assert run_tool("check_frontmatter", cwd=repo.root)[0] == 0
    assert run_tool("check_frontmatter", "--range", "nothing", cwd=repo.root)[0] == 2
    assert run_tool("check_frontmatter", "--range", "nope..HEAD", cwd=repo.root)[0] == 2
    plain = tmp_path / "plain"
    plain.mkdir()
    assert run_tool("check_frontmatter", "--all", cwd=plain)[0] == 2
