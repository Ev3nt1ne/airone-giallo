"""Tests for check_status.py, on invented status files written to a temporary folder.

Run from the tools' folder: pytest
"""

import subprocess
import sys
from pathlib import Path

import pytest

import check_status as cr

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
TEMPLATES = HERE.parents[1] / "skills" / "setup" / "templates" / "tree" / "ai-docs"

META = """```status-meta
families:
  APP: the application
  DOC: the documentation
```
"""
OPEN_HEAD = "| ID | Kind | Title | Reason | Owner | Trigger or question | Opened |\n|---|---|---|---|---|---|---|\n"
CLOSED_HEAD = ("| ID | Kind | Title | Outcome | Chosen | Reopen if | Reason | Closed |\n"
               "|---|---|---|---|---|---|---|---|\n")
LINK = "[design.md](design.md)"


def row(id_, kind="enhancement", title="Export to CSV", reason=LINK, owner="owner", trigger="", opened="2026-01-05"):
    return f"| `{id_}` | {kind} | {title} | {reason} | {owner} | {trigger} | {opened} |\n"


def closed_row(id_, kind="decision", title="Storage format", outcome="done", chosen="JSON lines, one per record",
               reopen="", reason=LINK, closed="2026-01-09"):
    return f"| `{id_}` | {kind} | {title} | {outcome} | {chosen} | {reopen} | {reason} | {closed} |\n"


def status(awaiting="", accepted="", deferred="", meta=META, extra=""):
    return (f"# Status\n\n{meta}\n## Awaiting your decision\n\n{OPEN_HEAD}{awaiting}\n"
            f"## Accepted, not yet built\n\n{OPEN_HEAD}{accepted}\n"
            f"## Deferred, with a trigger\n\n{OPEN_HEAD}{deferred}\n{extra}")


def closed(rows=""):
    return f"# Closed items\n\n{CLOSED_HEAD}{rows}"


def run(tmp_path, sta, clo=None, graph=None):
    """Write the files given and check them; return the errors and the next IDs."""
    paths = {}
    for name, text in (("status.md", sta), ("closed.md", clo), ("graph.yml", graph)):
        if text is not None:
            paths[name] = tmp_path / name
            paths[name].write_text(text, encoding="utf-8")
    errors, next_ids, _ = cr.check(*(str(paths[k]) if k in paths else None
                                     for k in ("status.md", "closed.md", "graph.yml")))
    return errors, next_ids


def only_error(errors, *words):
    assert len(errors) == 1, errors
    for w in words:
        assert w in errors[0], errors[0]


GRAPH = """meta:
  version: 1
  prefixes: [DEC, REQ]
  slug_prefixes: [DEC]
nodes:
  - {id: REQ-01, kind: requirement, support: satisfier, statement: "A saved file survives a crash.", where: "d.md"}
  - {id: DEC-journal, kind: decision, support: chosen, statement: "Write a journal first.", where: "d.md"}
edges:
  - {from: DEC-journal, type: satisfies, to: REQ-01}
"""


# --- a valid status file, and the next IDs ------------------------------------------------------------------------

def test_valid_pair_passes(tmp_path):
    errors, _ = run(tmp_path, status(awaiting=row("APP-001", kind="decision", trigger="CSV or JSON?"),
                                       accepted=row("APP-002"),
                                       deferred=row("DOC-001", kind="chore", trigger="the first release")),
                    closed(closed_row("APP-003")))
    assert errors == []


def test_next_id_counts_the_closed_file(tmp_path):
    errors, next_ids = run(tmp_path, status(accepted=row("APP-002")), closed(closed_row("APP-007")))
    assert errors == []
    assert next_ids == {"APP": "APP-008", "DOC": "DOC-001"}


def test_next_id_counts_an_id_written_without_backticks(tmp_path):
    errors, next_ids = run(tmp_path, status(accepted=row("APP-002").replace("`APP-002`", "APP-002")), closed())
    assert errors == []
    assert next_ids["APP"] == "APP-003"


def test_a_gap_is_not_an_error(tmp_path):
    errors, next_ids = run(tmp_path, status(accepted=row("APP-001") + row("APP-005")), closed())
    assert errors == []
    assert next_ids["APP"] == "APP-006"


def test_the_templates_pass_once_a_family_is_declared(tmp_path):
    sta = (TEMPLATES / "status.md").read_text(encoding="utf-8")
    sta = "\n".join("  APP: the application" if line.startswith("  <CODE>:") else line for line in sta.split("\n"))
    clo = (TEMPLATES / "closed.md").read_text(encoding="utf-8")
    errors, next_ids = run(tmp_path, sta, clo)
    assert errors == []
    assert next_ids == {"APP": "APP-001"}


# --- IDs ----------------------------------------------------------------------------------------------------------

def test_a_reused_id_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001") + row("APP-001", title="Import from CSV")), closed())
    only_error(errors, "APP-001", "never reused")


def test_a_closed_item_still_in_the_status_file_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001")), closed(closed_row("APP-001")))
    only_error(errors, "APP-001", "closed file only")


def test_an_id_reused_inside_the_closed_file_is_a_reuse(tmp_path):
    errors, _ = run(tmp_path, status(), closed(closed_row("APP-001") + closed_row("APP-001")))
    only_error(errors, "never reused")


def test_an_undeclared_family_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("WEB-001")), closed())
    only_error(errors, "WEB", "not declared")


def test_a_two_digit_counter_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-01")), closed())
    only_error(errors, "three digits")


def test_a_counter_of_zero_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-000")), closed())
    only_error(errors, "from 001")


def test_an_id_that_is_not_an_id_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("export")), closed())
    only_error(errors, "FAMILY-nnn")


def test_a_two_part_family_is_accepted(tmp_path):
    meta = "```status-meta\nfamilies:\n  WEB-API: the web service's interface\n```\n"
    errors, next_ids = run(tmp_path, status(accepted=row("WEB-API-004"), meta=meta), closed())
    assert errors == []
    assert next_ids == {"WEB-API": "WEB-API-005"}


def test_a_citation_of_an_item_in_neither_file_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001", title="Follows `APP-009`")), closed())
    only_error(errors, "APP-009", "neither file")


def test_a_cited_number_is_never_handed_out(tmp_path):
    errors, next_ids = run(tmp_path, status(accepted=row("APP-001", title="Follows `APP-009`")), closed())
    only_error(errors, "APP-009", "neither file")
    assert next_ids["APP"] == "APP-010"


# --- the meta block -----------------------------------------------------------------------------------------------

def test_no_meta_block_is_an_error(tmp_path):
    errors, next_ids = run(tmp_path, status(meta=""), closed())
    only_error(errors, "status-meta")
    assert next_ids == {}


def test_an_invalid_family_code_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(meta="```status-meta\nfamilies:\n  app: lower case\n```\n"), closed())
    only_error(errors, "'app'", "not a family code")


def test_a_family_declared_twice_is_an_error(tmp_path):
    meta = "```status-meta\nfamilies:\n  APP: one\n  APP: two\n```\n"
    errors, _ = run(tmp_path, status(meta=meta), closed())
    only_error(errors, "declared twice")


def test_an_unknown_meta_key_is_an_error(tmp_path):
    meta = "```status-meta\nfamilies:\n  APP: one\nfamilys:\n  DOC: two\n```\n"
    errors, _ = run(tmp_path, status(meta=meta), closed())
    only_error(errors, "unknown key 'familys'")


# --- rows ---------------------------------------------------------------------------------------------------------

def test_an_open_item_without_an_owner_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001", owner="")), closed())
    only_error(errors, "owner")


def test_a_deferred_item_without_a_trigger_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(deferred=row("APP-001", trigger="—")), closed())
    only_error(errors, "trigger")


def test_an_item_awaiting_a_decision_states_its_question(tmp_path):
    errors, _ = run(tmp_path, status(awaiting=row("APP-001", kind="decision")), closed())
    only_error(errors, "question")


def test_an_accepted_item_needs_no_trigger(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001", trigger="")), closed())
    assert errors == []


def test_an_unknown_kind_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001", kind="feature")), closed())
    only_error(errors, "kind 'feature'")


def test_a_reason_without_a_link_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001", reason="see the design")), closed())
    only_error(errors, "no link")


def test_an_impossible_date_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001", opened="2026-02-30")), closed())
    only_error(errors, "opened", "not a date")


def test_a_row_with_too_few_cells_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted="| `APP-001` | chore | Tidy |\n"), closed())
    only_error(errors, "3 cells")


def test_an_escaped_pipe_stays_inside_its_cell(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001", title="Read `a \\| b`")), closed())
    assert errors == []


# --- sections and tables ------------------------------------------------------------------------------------------

def test_an_item_table_under_an_unknown_heading_is_an_error(tmp_path):
    extra = f"## In progress\n\n{OPEN_HEAD}{row('APP-001')}"
    errors, _ = run(tmp_path, status(extra=extra), closed())
    only_error(errors, "'In progress'", "not a status section")


def test_a_marker_in_a_status_heading_is_allowed(tmp_path):
    sta = status(deferred=row("APP-001", trigger="a user asks")).replace("## Deferred", "## 🧭 Deferred")
    errors, _ = run(tmp_path, sta, closed())
    assert errors == []


def test_an_item_table_with_the_wrong_columns_is_an_error(tmp_path):
    sta = status().replace("| Owner |", "| Who |", 1)
    errors, _ = run(tmp_path, sta, closed())
    only_error(errors, "columns must be")


def test_a_table_that_is_not_an_item_table_is_ignored(tmp_path):
    errors, _ = run(tmp_path, status(extra="| Column | Holds |\n|---|---|\n| Kind | what it is |\n"), closed())
    assert errors == []


def test_a_table_inside_a_code_fence_is_not_read(tmp_path):
    extra = f"```markdown\n## In progress\n\n{OPEN_HEAD}{row('APP-001')}```\n"
    errors, next_ids = run(tmp_path, status(extra=extra), closed())
    assert errors == []
    assert next_ids["APP"] == "APP-001"



def test_a_longer_fence_is_closed_only_by_one_as_long(tmp_path):
    example = f"````markdown\n```markdown\n## In progress\n\n{OPEN_HEAD}{row('APP-001')}```\n````\n"
    errors, next_ids = run(tmp_path, status(extra=example), closed())
    assert errors == []
    assert next_ids["APP"] == "APP-001"


# --- the closed file ----------------------------------------------------------------------------------------------

def test_an_unknown_outcome_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(), closed(closed_row("APP-001", outcome="finished")))
    only_error(errors, "outcome 'finished'")


def test_a_closed_item_says_what_was_chosen(tmp_path):
    errors, _ = run(tmp_path, status(), closed(closed_row("APP-001", chosen="")))
    only_error(errors, "chosen")


def test_a_superseded_item_names_its_successor(tmp_path):
    errors, _ = run(tmp_path, status(), closed(closed_row("APP-001", outcome="superseded", chosen="split")))
    only_error(errors, "names no item")


def test_a_superseded_item_naming_itself_is_not_enough(tmp_path):
    errors, _ = run(tmp_path, status(), closed(closed_row("APP-001", outcome="superseded",
                                                           chosen="see `APP-001`")))
    only_error(errors, "names no item")


def test_without_a_closed_file_a_note_says_so(tmp_path):
    r = tmp_path / "status.md"
    r.write_text(status(), encoding="utf-8")
    _, _, (_, _, notes) = cr.check(str(r))
    assert any("status file only" in n for n in notes)


# --- the graph ----------------------------------------------------------------------------------------------------

def test_a_graph_citation_without_the_graph_is_allowed(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001", title="Meets `REQ-09`")), closed())
    assert errors == []


def test_a_graph_citation_of_a_node_that_exists_passes(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001", title="Meets `REQ-01` by `DEC-journal`")),
                    closed(), GRAPH)
    assert errors == []


def test_a_graph_citation_of_a_missing_node_is_an_error(tmp_path):
    errors, _ = run(tmp_path, status(accepted=row("APP-001", title="Meets `REQ-09`")), closed(), GRAPH)
    only_error(errors, "REQ-09", "graph node")


def test_a_node_citing_an_item_is_an_error(tmp_path):
    graph = GRAPH.replace("Write a journal first.", "Write a journal first, as APP-001 builds.")
    errors, _ = run(tmp_path, status(accepted=row("APP-001")), closed(), graph)
    only_error(errors, "APP-001", "never cites an item")


def test_a_family_shared_with_the_graph_is_an_error(tmp_path):
    meta = "```status-meta\nfamilies:\n  REQ: requests\n```\n"
    errors, _ = run(tmp_path, status(meta=meta), closed(), GRAPH)
    only_error(errors, "REQ", "ambiguous")


# --- the command --------------------------------------------------------------------------------------------------

def test_the_command_exits_one_on_an_error_and_zero_when_clean(tmp_path):
    bad, good = tmp_path / "bad.md", tmp_path / "good.md"
    bad.write_text(status(accepted=row("APP-001", owner="")), encoding="utf-8")
    good.write_text(status(accepted=row("APP-001")), encoding="utf-8")
    script = str(SRC / "check_status.py")
    r_bad = subprocess.run([sys.executable, script, str(bad)], capture_output=True, text=True)
    r_good = subprocess.run([sys.executable, script, str(good)], capture_output=True, text=True)
    assert r_bad.returncode == 1, r_bad.stdout
    assert r_good.returncode == 0, r_good.stdout
    assert "APP-002" in r_good.stdout


def test_the_command_exits_two_when_a_file_cannot_be_read(tmp_path):
    r = subprocess.run([sys.executable, str(SRC / "check_status.py"), str(tmp_path / "absent.md")],
                       capture_output=True, text=True)
    assert r.returncode == 2


def test_the_package_command_names_the_checker_main():
    tomllib = pytest.importorskip("tomllib")
    meta = tomllib.loads((HERE.parent / "pyproject.toml").read_text(encoding="utf-8"))
    module, _, func = meta["project"]["scripts"]["check-status"].partition(":")
    layout = meta["tool"]["setuptools"]
    assert module in layout["py-modules"]
    assert (HERE.parent / layout["package-dir"][""] / f"{module}.py") == SRC / "check_status.py"
    assert callable(getattr(cr, func, None))
