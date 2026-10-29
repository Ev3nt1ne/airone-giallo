"""Tests for check-links: dead links and anchors in the tracked tree, the archive's rules, and the ladder in both
forms."""

import contextlib
import io

import check_links as cl
from conftest import run_tool

FM = "---\ntitle: x\n---\n\n"


def check(repo, *args):
    """(exit code, errors, warnings, archived) through main(), the printed lines sorted by kind."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cl.main(["--root", str(repo.root), *args])
    lines = buf.getvalue().splitlines()

    def pick(prefix):
        return [line[len(prefix):] for line in lines if line.startswith(prefix)]

    return code, pick("error: "), pick("warning: "), pick("archived: ")


def only(items, *words):
    assert len(items) == 1, items
    for w in words:
        assert w in items[0], items[0]


# --- dead links and anchors ------------------------------------------------------------------------------------------

def test_a_clean_tree_passes(repo):
    repo.write({
        "docs/spec.md": FM + "# Spec\n\n## 2. The format\n\n## The format\n\n## `save()` and *load*\n\n"
                             "Setext title\n============\n\n<a id=\"pinned\"></a>\n",
        "docs/notes.md": "See [the spec](spec.md), [its format](spec.md#2-the-format), [the second](spec.md#the-format),"
                         " [the code](spec.md#save-and-load), [setext](spec.md#setext-title), [pinned](spec.md#pinned),"
                         " [here](#notes), [the folder](../plan/), [from the top](/docs/spec.md),"
                         " [a site](https://example.com/x.md), [mail](mailto:a@example.com),"
                         " ![a picture](img/a.png), [a script](../run.sh#L3), [spaced](<spec.md>).\n\n# Notes\n",
        "docs/img/a.png": "png", "plan/plan.md": FM, "run.sh": "echo\n",
    }).commit()
    code, errors, warnings, archived = check(repo)
    assert (code, errors, warnings, archived) == (0, [], [], [])


def test_a_dead_link_is_an_error_and_the_command_exits_one(repo):
    repo.write({"docs/a.md": "See [b](b.md) and [c](c.md).\n", "docs/b.md": "# B\n"}).commit()
    code, out, _ = run_tool("check_links", cwd=repo.root)
    assert code == 1
    assert "error: docs/a.md:1: dead link c.md" in out and "1 error(s)" in out


def test_a_target_present_but_not_tracked_is_dead(repo):
    repo.write({"docs/a.md": "See [the machine](../local-machine.md).\n"}).commit()
    repo.write({"local-machine.md": "# This machine\n"})
    code, errors, _, _ = check(repo)
    assert code == 1
    only(errors, "local-machine.md", "not tracked")


def test_a_staged_file_counts_as_tracked(repo):
    repo.write({"docs/a.md": "See [new](new.md).\n"}).commit()
    repo.write({"docs/new.md": "# New\n"}).stage()
    assert check(repo)[0] == 0


def test_a_dead_anchor_is_an_error_and_a_non_markdown_anchor_is_not_checked(repo):
    repo.write({"docs/a.md": "[gone](b.md#gone) [ok](b.md#kept) [line](../run.sh#L9) [self](#nowhere)\n# A\n",
                "docs/b.md": "## Kept\n", "run.sh": "echo\n"}).commit()
    code, errors, _, _ = check(repo)
    assert code == 1 and len(errors) == 2, errors
    assert any("b.md#gone" in e and "dead anchor" in e for e in errors)
    assert any("#nowhere" in e for e in errors)


def test_a_repeated_heading_takes_a_number(repo):
    repo.write({"docs/a.md": "# Notes\n\n## Notes\n\n[first](#notes) [second](#notes-1) [third](#notes-2)\n"})
    repo.commit()
    code, errors, _, _ = check(repo)
    only(errors, "#notes-2")


def test_links_in_code_and_comments_are_not_links(repo):
    repo.write({"docs/a.md": "```\n[x](gone.md)\n```\n\n`[y](gone.md)`\n\n<!-- [z](gone.md) -->\n\n"
                             "<!--\n[w](gone.md)\n-->\n"}).commit()
    assert check(repo)[:2] == (0, [])


def test_a_link_that_climbs_out_of_the_repository_is_dead(repo):
    repo.write({"a.md": "[out](../../elsewhere.md)\n"}).commit()
    only(check(repo)[1], "climbs out")


# --- the archive -----------------------------------------------------------------------------------------------------

def test_a_dead_link_inside_the_archive_is_information(repo):
    repo.write({"archive/old.md": "[gone](../docs/gone.md) [anchor](old.md#nowhere)\n",
                "docs/a.md": FM + "# A\n"}).commit()
    code, out, _ = run_tool("check_links", cwd=repo.root)
    assert code == 0, out
    assert "archived: archive/old.md:1: dead link ../docs/gone.md" in out
    assert "2 dead link(s) inside the archive, information only" in out and "0 error(s)" in out


def test_a_live_document_citing_an_archived_file_is_a_warning(repo):
    repo.write({"archive/old.md": "# Old\n", "archive/README.md": "# The archive\n", "archive/LOG.md": "# Log\n",
                "docs/a.md": "[old](../archive/old.md), `archive/old.md`, [the archive](../archive/),"
                             " [its index](../archive/README.md), `archive/LOG.md`\n"}).commit()
    code, errors, warnings, _ = check(repo)
    assert code == 0 and errors == []
    assert len(warnings) == 2 and all("archive/old.md" in w and "category" in w for w in warnings), warnings


def test_the_archive_in_a_nested_repository_is_its_own(repo):
    repo.nest("pub", {"archive/old.md": "[gone](gone.md)\n", "README.md": "# Pub\n"})
    repo.write({"a.md": "# A\n"}).commit()
    code, errors, _, archived = check(repo)
    assert code == 0 and errors == [] and len(archived) == 1


# --- the ladder, one repository --------------------------------------------------------------------------------------

def ladder_tree(repo):
    repo.write({
        "docs/spec.md": "[status](../ai-docs/status.md) and `ai-docs/status.md`, [the plan](../plan/plan.md)\n",
        "plan/plan.md": "[spec](../docs/spec.md) and `graph.yml`\n",
        "graph.yml": "meta: {}\n",
        "ai-docs/status.md": "[spec](../docs/spec.md) [plan](../plan/plan.md) [rules](../AGENTS.md) [old](../archive/x.md)\n",
        "AGENTS.md": "[status](ai-docs/status.md) [spec](docs/spec.md) [old](archive/x.md)\n",
        "archive/x.md": "[status](../ai-docs/status.md)\n",
        "README.md": "[status](ai-docs/status.md)\n",
    }).commit()


def test_with_a_cut_a_public_file_citing_a_private_one_is_an_error(repo):
    ladder_tree(repo)
    code, errors, warnings, _ = check(repo, "--cut", "plan")
    assert code == 1
    assert len(errors) == 2 and all(e.startswith("docs/spec.md:1: the ladder: a public file") for e in errors)
    assert any("links to ../ai-docs/status.md" in e for e in errors)
    assert any("names `ai-docs/status.md`" in e for e in errors)
    # Citing upward on one side is a warning; the agent layer cites everything; the AI documents' rung may cite the
    # agent layer only with a warning.
    assert any("docs/spec.md:1: the ladder: rung 1 (docs) links to rung 3 (plan)" in w for w in warnings)
    assert any("ai-docs/status.md:1: the ladder: rung 4 (ai-docs) links to rung 5 (agent)" in w for w in warnings)
    assert not any(w.startswith("AGENTS.md") and "the ladder" in w for w in warnings)
    # An archived file cited from a lower rung is the archive's warning, never the ladder's as well.
    assert [w for w in warnings if "archive/x.md" in w and w.startswith("ai-docs")] == [
        w for w in warnings if w.startswith("ai-docs/status.md:1: links to ../archive/x.md, inside the archive")]
    assert len([w for w in warnings if "archive/x.md" in w and w.startswith("ai-docs")]) == 1
    # A file outside every rung (README.md here) has no known side.
    assert not any(e.startswith("README.md") for e in errors)


def test_the_cut_moves_the_side(repo):
    ladder_tree(repo)
    code, errors, warnings, _ = check(repo, "--cut", "ai-docs")
    # The agent layer is private at this cut; the archive is off the ladder, so in one repository it has no side and
    # citing a file in it is the archive's own warning, never the ladder's error.
    only(errors, "ai-docs/status.md:1: the ladder", "../AGENTS.md")
    assert any("../archive/x.md" in w and "category" in w for w in warnings)
    code, errors, _, _ = check(repo, "--cut", "all")
    assert code == 0 and errors == []
    code, errors, _, _ = check(repo, "--cut", "docs")
    assert {e.split(":")[0] for e in errors} == {"docs/spec.md"}
    assert any("plan/plan.md" in e for e in errors)  # the plan is private now


def test_a_rung_can_be_placed_elsewhere(repo):
    repo.write({"documentation/spec.md": "[status](../ai-docs/status.md)\n", "ai-docs/status.md": "# S\n"}).commit()
    assert check(repo, "--cut", "plan")[1] == []
    code, errors, _, _ = check(repo, "--cut", "plan", "--rung", "docs=documentation/")
    only(errors, "documentation/spec.md", "the ladder")


def test_the_archive_can_be_placed_elsewhere_and_is_not_a_rung(repo):
    """--archive names the frozen folder; a folder named archive/ elsewhere is then live, and --rung does not know the
    archive, since it is not on the ladder."""
    repo.write({"attic/old.md": "[gone](../docs/gone.md)\n", "archive/tools.md": "[gone](gone.md)\n",
                "docs/a.md": "[old](../attic/old.md)\n"}).commit()
    code, errors, warnings, archived = check(repo)
    assert code == 1 and len(errors) == 1 and "attic/old.md" in errors[0] and len(archived) == 1
    code, errors, warnings, archived = check(repo, "--archive", "attic/")
    assert code == 1 and len(errors) == 1 and "archive/tools.md" in errors[0]
    assert len(archived) == 1 and "attic/old.md" in archived[0]
    only(warnings, "docs/a.md", "attic/old.md", "category")
    assert run_tool("check_links", "--cut", "plan", "--rung", "archive=attic/", cwd=repo.root)[0] == 2


# --- the ladder, two repositories ------------------------------------------------------------------------------------

def test_with_a_public_folder_nothing_in_it_cites_outside_it(repo):
    repo.nest("pub", {
        "docs/spec.md": "# Spec\n\n[status](../../ai-docs/status.md), `ai-docs/status.md`, [plan](/plan/plan.md),"
                        " `docs/spec.md`, `pub/docs/spec.md`\n",
        "plan/plan.md": "[spec](../docs/spec.md#spec) `graph.yml`\n",
        "graph.yml": "meta: {}\n",
        "README.md": "[the notes](../human-docs/n.md)\n",
    })
    repo.write({"ai-docs/status.md": "[spec](../pub/docs/spec.md#spec) `pub/plan/plan.md`\n",
                "human-docs/n.md": "notes\n"}).commit()
    code, errors, warnings, _ = check(repo, "--public", "pub")
    assert code == 1
    assert sorted(e.split(":")[0] for e in errors) == ["pub/README.md", "pub/docs/spec.md", "pub/docs/spec.md"]
    assert all("the ladder: a public file" in e for e in errors)
    # The root-relative link resolved from the public repository's top; the private side cites the public freely.
    assert not any(e.startswith("ai-docs") for e in errors)


def test_a_written_path_is_read_from_its_own_repository_first(repo):
    repo.nest("pub", {"docs/spec.md": "# Spec\n", "README.md": "Start at `docs/spec.md`.\n"})
    repo.write({"docs/spec.md": "# an older private copy\n"}).commit()
    assert check(repo, "--public", "pub")[1] == []


def test_a_submodule_declared_but_not_yet_committed_is_read(repo):
    repo.write({"a.md": "# A\n"}).commit()
    repo.nest("pub", {"docs/a.md": "[gone](gone.md)\n"})
    code, errors, _, _ = check(repo)
    only(errors, "pub/docs/a.md", "dead link gone.md")


def test_the_command_takes_the_public_folder_and_the_cut(repo):
    repo.nest("pub", {"docs/a.md": "[status](../../ai-docs/status.md)\n"})
    repo.write({"ai-docs/status.md": "# S\n"}).commit()
    code, out, _ = run_tool("check_links", "--public", "pub", "--cut", "plan", cwd=repo.root)
    assert code == 1 and "the ladder: a public file links to ../../ai-docs/status.md" in out
    assert "public side pub/" in out


# --- arguments -------------------------------------------------------------------------------------------------------

def test_bad_arguments_exit_two(repo, tmp_path):
    repo.write({"a.md": "# A\n"}).commit()
    for args in (["--cut", "middle"], ["--public", "nowhere"], ["--rung", "docs=documentation/"],
                 ["--cut", "plan", "--rung", "docs"], ["--cut", "plan", "--rung", "attic=x/"]):
        assert run_tool("check_links", *args, cwd=repo.root)[0] == 2, args
    outside = tmp_path / "plain"
    outside.mkdir()
    code, _, err = run_tool("check_links", cwd=outside)
    assert code == 2 and "not inside a git repository" in err


def test_the_slug_follows_the_forges(repo):
    assert cl.at.slug("2. The `save()` path, *again*") == "2-the-save-path-again"
    assert cl.at.slug("Ünïcode & symbols §4") == "ünïcode--symbols-4"
    assert cl.at.slug("snake_case [a link](x.md)") == "snake_case-a-link"
    assert cl.at.slug("_Emphasis_ and __strong__") == "emphasis-and-strong"


def test_an_exempt_folder_is_not_scanned_as_a_source(repo):
    """A template's links resolve only once it is written into a project: --exempt keeps it out of the scan, while a
    dead link elsewhere is still an error, and the exempt file is still a valid target."""
    repo.write({
        "templates/tree/README.md": FM + "# Index\n\nSee [the status file](status.md).\n",
        "docs/notes.md": FM + "See [the template](../templates/tree/README.md) and [a dead one](missing.md).\n",
    }).commit()
    code, errors, warnings, archived = check(repo)
    assert code == 1 and len(errors) == 2
    code, errors, warnings, archived = check(repo, "--exempt", "templates/")
    assert code == 1 and len(errors) == 1 and "missing.md" in errors[0]
    code, errors, warnings, archived = check(repo, "--exempt", "templates/*/README.md")
    assert len(errors) == 1
