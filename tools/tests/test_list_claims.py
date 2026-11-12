"""Tests for claims: the mechanical claims settled against git, the graph file and the status file, the rest listed,
and what is read where."""

import contextlib
import io
import os
import subprocess

import pytest

import airone_tree as at
import list_claims as lc
from conftest import ENV, run_tool

GRAPH = """meta:
  profile: lite
  prefixes: [REQ, ASM, CHO]
  slug_prefixes: [CHO]
  id_digits: [2, 3]
nodes:
  - {id: REQ-01, kind: requirement, statement: "A saved note survives a crash."}
  - id: CHO-plain-text
    kind: decision
edges: []
"""
STATUS = """# Status

```status-meta
families:
  APP: the application
```

| ID | Kind | Title | Reason | Owner | Trigger or question | Opened |
|---|---|---|---|---|---|---|
| `APP-001` | defect | A crash loses the title | [design](design.md) | owner | - | 2026-03-01 |
"""
CLOSED = """| ID | Kind | Title | Outcome | Chosen | Reopen if | Reason | Closed |
|---|---|---|---|---|---|---|---|
| `APP-002` | decision | Format | done | text | never | [design](design.md) | 2026-03-02 |
"""
SPEC = "# Spec\n\n## 2. The format\n\n### 2.1 Fields\n\n## 3 Saving\n"


def setup(repo):
    repo.write({"graph.yml": GRAPH, "ai-docs/status.md": STATUS, "ai-docs/closed.md": CLOSED, "docs/spec.md": SPEC})
    return repo.commit("start")


def claims(repo, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = lc.main(["--root", str(repo.root), *args])
    return code, buf.getvalue()


def test_the_resolvers_settle_what_exists_and_fail_what_does_not(repo):
    head = setup(repo)
    repo.write({"docs/note.md": (f"Landed in {head[:9]}, not in 0badc0de1.\n"
                                 "REQ-01 holds, REQ-99 does not; CHO-plain-text holds, CHO-markdown does not.\n"
                                 "APP-001 is open, APP-002 closed, APP-009 nowhere.\n")}).stage()
    code, out = claims(repo)
    assert code == 1, out
    assert f"resolved: hash {head[:9]}" in out
    assert "unknown: hash 0badc0de1" in out
    assert "unknown: graph id REQ-99, graph id CHO-markdown" in out
    assert "resolved: graph id REQ-01, graph id CHO-plain-text" in out
    assert "resolved: status id APP-001, status id APP-002" in out and "unknown: status id APP-009" in out
    assert "4 failed a mechanical check" in out
    assert "number 01" not in out and "number 001" not in out                  # an identifier is not a number


def test_families_come_from_the_files(repo):
    setup(repo)
    repo.write({"docs/note.md": "ZZZ-01 and RFC-123 and BUG-001 are not families here.\n"}).stage()
    code, out = claims(repo)
    assert code == 0 and "graph id" not in out and "status id" not in out


def test_sections_against_the_named_document_or_a_given_one(repo):
    setup(repo)
    repo.write({"docs/note.md": ("See [the spec](spec.md) §2 and §2.1 and §9.\n"
                                 "As `docs/spec.md` §3 says.\n"
                                 "A bare §2.1 here.\n")}).stage()
    code, out = claims(repo)
    assert code == 0, out
    assert "section §2 [a heading in docs/spec.md" in out and "section §2.1 [a heading in docs/spec.md" in out
    assert "section §9 [NO heading 9 in docs/spec.md]" in out
    assert "section §3 [a heading in docs/spec.md" in out
    assert "section §2.1 [NO heading 2.1 in docs/note.md]" in out              # the line's own file
    code, out = claims(repo, "--message", str(_message(repo, "As said in §2.1.\n")))
    assert "section §2.1 [which document?]" in out
    code, out = claims(repo, "--message", str(_message(repo, "As said in §2.1.\n")), "--doc", "docs/spec.md")
    assert "section §2.1 [a heading in docs/spec.md" in out


def _message(repo, text):
    path = repo.root.parent / "message.txt"
    path.write_text(text)
    return path


def test_numbers_quotations_and_completeness_words_are_listed(repo):
    setup(repo)
    code, out = claims(repo, "--message", str(_message(
        repo, 'Every one of the 16 tests "was mutation-checked" on 2026-03-01; none failed, at 3.5%.\n')))
    assert code == 0
    assert "number 16" in out and "number 3.5%" in out and "number 2026" not in out
    assert "quote was mutation-checked" in out
    assert "completeness Every" in out and "completeness none" in out


def test_in_code_only_comment_lines_are_read(repo):
    setup(repo)
    repo.write({"src/a.py": "x = 16  # not a comment line\n# all 3 cases, REQ-77\nvalue = 'every'\n",
                "conf.toml": "n = 4\n# every 2 hours\n"}).stage()
    code, out = claims(repo)
    assert code == 1
    assert "src/a.py:2" in out and "src/a.py:1" not in out and "src/a.py:3" not in out
    assert "conf.toml:2" in out and "conf.toml:1" not in out


def test_a_file_whose_name_is_not_ascii_is_read_by_its_name(repo):
    # git quotes such a name in a diff's header unless told not to; its lines are still read, under the name.
    setup(repo)
    repo.write({"docs/café.md": "REQ-99 does not exist.\n", "docs/über/naïve.md": "REQ-01 holds.\n"}).stage()
    code, out = claims(repo)
    assert code == 1, out
    assert "FAIL docs/café.md:1" in out and "ok docs/über/naïve.md:1" in out, out


@pytest.mark.skipif(os.name != "posix", reason="the names hold characters Windows refuses in a file name")
def test_a_path_from_git_reads_as_git_prints_it_with_quote_path_off(repo):
    # The tools read git's default output; each path must come back as git prints it with core.quotePath off: the
    # non-ASCII ones unquoted, the ones git quotes either way (a double quote, a tab, a backslash) still quoted.
    names = ["plain.md", "café.md", "über/naïve note.md", 'say "é".md', "back\\303slash é.md", "tab\té.md"]
    repo.write({n: "x\n" for n in names}).stage()
    off = dict(ENV, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.quotePath", GIT_CONFIG_VALUE_0="off")

    def paths(env):
        """The paths of the tracked files, and those of a diff's headers with what git writes after them."""
        def run(*args):
            return subprocess.run(["git", *args], cwd=repo.root, env=env, capture_output=True, text=True,
                                  check=True).stdout.splitlines()
        return run("ls-files") + [h[4:] for h in run("diff", "--cached", "-U0", "--no-color") if h.startswith("+++ ")]

    default, quote_path_off = paths(ENV), paths(off)
    assert len(default) == 2 * len(names) and default != quote_path_off
    assert [at.git_path(p) for p in default] == quote_path_off


def test_a_line_keeps_its_number_in_the_file(repo):
    setup(repo)
    repo.write({"docs/x.md": "one\ntwo\nthree\nfour\n"}).commit()
    repo.write({"docs/x.md": "one\ntwo\nREQ-01 holds.\nthree\nfour\nREQ-99 does not.\n"}).stage()
    code, out = claims(repo)
    assert code == 1 and "ok docs/x.md:3" in out and "FAIL docs/x.md:6" in out


def test_a_range(repo):
    first = setup(repo)
    repo.write({"docs/x.md": "REQ-42 is new.\n"})
    repo.commit("add")
    code, out = claims(repo, "--range", f"{first}..HEAD")
    assert code == 1 and "unknown: graph id REQ-42" in out and "docs/x.md:1" in out


def test_a_hash_of_something_else_than_a_commit_is_unknown(repo):
    setup(repo)
    blob = repo.git("rev-parse", "HEAD:graph.yml").strip()[:12]
    code, out = claims(repo, "--message", str(_message(repo, f"The graph's blob is {blob}; 20260301 is a date.\n")))
    assert code == 1 and f"unknown: hash {blob}" in out
    assert "number 20260301" in out and "hash 20260301" not in out             # all digits: not read as a hash


def test_the_known_false_positive_a_hex_run_that_is_not_a_commit(repo):
    setup(repo)
    code, out = claims(repo, "--message", str(_message(repo, "The state root is 856b2698ff.\n")))
    assert code == 1 and "unknown: hash 856b2698ff" in out


def test_without_the_files_the_identifiers_are_not_resolved(repo):
    repo.write({"README.md": "x\n"}).commit()
    repo.write({"docs/x.md": "REQ-01 and APP-001.\n"}).stage()
    code, out = claims(repo)
    assert code == 0
    assert "note: graph identifiers not resolved" in out and "note: status identifiers not resolved" in out


def test_the_command_and_its_bad_arguments(repo, tmp_path):
    setup(repo)
    repo.write({"docs/x.md": "REQ-99.\n"}).stage()
    code, out, _ = run_tool("list_claims", cwd=repo.root)
    assert code == 1 and "FAIL docs/x.md:1" in out
    assert run_tool("list_claims", "--graph", "nowhere.yml", cwd=repo.root)[0] == 2
    assert run_tool("list_claims", "--message", "nowhere.txt", cwd=repo.root)[0] == 2
    assert run_tool("list_claims", "--range", "nope..HEAD", cwd=repo.root)[0] == 2
    plain = tmp_path / "plain"
    plain.mkdir()
    assert run_tool("list_claims", cwd=plain)[0] == 2
