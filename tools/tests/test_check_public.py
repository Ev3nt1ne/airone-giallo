"""Tests for check-public: the gate a public repository's first commit and every push go through, on a private
repository with a public one nested in it, as the setup's private-history direction leaves them. The push tests go
through `git push` to a bare remote, with the setup's own pre-push hook installed, the way an owner pushes."""

import os
import random
import shutil
import string
import subprocess
import sys

import pytest

import check_public as cp
from conftest import ENV, SRC, Repo

needs_gitleaks = pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks is not installed")

OLD = dict(GIT_AUTHOR_NAME="Wren Halloway", GIT_AUTHOR_EMAIL="wren@private.example",
           GIT_COMMITTER_NAME="Wren Halloway", GIT_COMMITTER_EMAIL="wren@private.example")
SIDES = "public app/\npublic README.md\nprivate app/fixtures/\nlocal app/.env\n"
MARKERS = "Wren Halloway\nprivate.example\n"
HOOK = SRC.parent.parent / "skills" / "setup" / "templates" / "pre-push"


def token():
    """The shape of a GitHub token, made at run time so no file of this repository holds one."""
    return "ghp_" + "".join(random.choice(string.ascii_letters + string.digits) for _ in range(36))


def git(root, *args, env=None):
    p = subprocess.run(["git", "-C", str(root), *args], env=env or ENV, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def pair(tmp_path, sides=SIDES, markers=MARKERS):
    """A private repository with an old history, and inside it a new public one with its files staged and the
    `local` file ignored by its own rules."""
    private = Repo(tmp_path / "larder")
    private.write({"docs/notes.md": "# Notes\n", "app/main.py": "x = 1\n"})
    env = dict(ENV, **OLD)
    git(private.root, "add", "-A", env=env)
    git(private.root, "commit", "-q", "-m", "old history", env=env)
    private.write({"public-paths.txt": sides, "public-markers.txt": markers})
    public = private.root / "public"
    public.mkdir()
    git(public, "init", "-q", "-b", "main")
    git(public, "config", "user.name", "Wren")
    git(public, "config", "user.email", "wren@users.noreply.example")
    (private.root / ".gitmodules").write_text('[submodule "public"]\n\tpath = public\n\turl = ./public\n')
    for rel, text in {"app/main.py": "def main():\n    return 1\n", "app/.gitignore": ".env\n",
                      "README.md": "# Larder\n", "app/.env": "TOKEN=x\n"}.items():
        (public / rel).parent.mkdir(parents=True, exist_ok=True)
        (public / rel).write_text(text, encoding="utf-8")
    git(public, "add", "-A")
    return private.root, public


def gate(public, *args, env=None):
    p = subprocess.run([sys.executable, str(SRC / "check_public.py"), "--root", str(public), *args],
                       env=env or ENV, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def put(public, rel, text, stage=True):
    (public / rel).parent.mkdir(parents=True, exist_ok=True)
    (public / rel).write_text(text, encoding="utf-8")
    if stage:
        git(public, "add", "-A")


def commit(public, message, env=None):
    git(public, "add", "-A", env=env)
    git(public, "commit", "-q", "-m", message, env=env)


def remote(tmp_path, public):
    """A bare remote, the setup's hook in the public repository, and `check-public` on the PATH: (env, remote)."""
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(bare))
    git(public, "remote", "add", "origin", str(bare))
    hook = public / ".git" / "hooks" / "pre-push"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(HOOK.read_text(encoding="utf-8"), encoding="utf-8")
    hook.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    wrapper = bin_dir / "check-public"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{SRC / "check_public.py"}" "$@"\n')
    wrapper.chmod(0o755)
    return dict(ENV, PATH=f"{bin_dir}{os.pathsep}{ENV['PATH']}"), bare


def push(public, env, *refs):
    p = subprocess.run(["git", "-C", str(public), "push", "origin", *refs], env=env, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def on_remote(bare, ref):
    return subprocess.run(["git", "-C", str(bare), "rev-parse", "--verify", "-q", ref], env=ENV,
                          capture_output=True, text=True).returncode == 0


def first_push(tmp_path, sides=SIDES):
    """The public repository with its first commit pushed through the gate; (public, env, bare)."""
    _, public = pair(tmp_path, sides=sides)
    git(public, "commit", "-q", "-m", "First public state")
    env, bare = remote(tmp_path, public)
    rc, out = push(public, env, "main")
    assert rc == 0, out
    return public, env, bare


# ---------------------------------------------------------------- the allow-list itself

def test_the_longest_matching_path_wins_and_no_rule_means_private():
    sides = cp.Sides.parse(SIDES)
    assert sides.old_email_ok is False
    assert sides.side_of("app/main.py") == "public"
    assert sides.side_of("app/fixtures/a.json") == "private"
    assert sides.side_of("app/.env") == "local"
    assert sides.side_of("docs/notes.md") is None
    assert sides.side_of("application.py") is None, "a folder's rule covers only what is under it"


def test_the_order_of_the_lines_never_changes_a_side():
    sides = cp.Sides.parse("\n".join(reversed(SIDES.splitlines())))
    assert sides.side_of("app/fixtures/a.json") == "private"


@pytest.mark.parametrize("bad", ["publik app/", "public /app/", "public ../app/", "cut sideways", "public",
                                 "private a.md -> b.md", "public a.md -> ../b.md", "setup docs/"])
def test_a_malformed_line_is_refused_naming_it(bad):
    with pytest.raises(cp.Usage, match="line 1"):
        cp.Sides.parse(bad + "\n")


def test_a_public_path_can_take_another_name_on_the_public_side():
    sides = cp.Sides.parse("public app/\npublic README.public.md -> README.md\nprivate README.md\n"
                           "public site/ -> web/\nprivate site/drafts/\n")
    assert sides.dest("README.public.md") == "README.md" and sides.dest("app/x.py") == "app/x.py"
    assert sides.dest("site/index.html") == "web/index.html"
    view = sides.public_view()
    assert view.declared_public("README.md") and view.declared_public("web/index.html")
    assert not view.declared_public("README.public.md") and not view.declared_public("web/drafts/a.md")


@pytest.mark.parametrize("written", ["wren-halloway", "wren_halloway", "WrenHalloway", "wren.halloway",
                                     "WREN HALLOWAY", "notes-of-wren--halloway"])
def test_a_marker_matches_with_spaces_hyphens_underscores_and_dots_ignored(written):
    assert list(cp.marker_hits(f"x = '{written}'\n", ["Wren Halloway"])) == [(1, 1)]


@pytest.mark.parametrize("text, line", [("kept by Wren\nHalloway and friends\n", 1), ("x\nContact: Wren\tHalloway\n", 2),
                                        ("Wren Halloway\n", 1), ("Wren \r\n  Halloway\n", 1)])
def test_a_marker_matches_across_any_whitespace_and_is_placed_where_it_starts(text, line):
    assert (1, line) in list(cp.marker_hits(text, ["Wren Halloway"]))


def test_look_alike_letters_and_accents_are_not_folded_as_the_readme_says():
    assert list(cp.marker_hits("Wren Hallóway\n", ["Wren Halloway"])) == []


def test_every_non_empty_line_of_the_markers_file_is_a_marker_verbatim():
    assert cp.read_markers("#larder-deals\nWren Halloway\n\n# a heading?\n") == \
        ["#larder-deals", "Wren Halloway", "# a heading?"]


@pytest.mark.parametrize("marker", ["--", "...", "._-"])
def test_a_marker_that_folds_to_nothing_is_refused(marker):
    with pytest.raises(cp.Usage, match="fewer than 3"):
        cp.read_markers(f"{marker}\n")


def test_a_path_holding_the_word_as_is_one_path_since_the_file_renames_with_an_arrow():
    sides = cp.Sides.parse("public notes as of may.md\npublic README.public.md -> README.md\n")
    assert sides.side_of("notes as of may.md") == "public" and sides.dest("notes as of may.md") == "notes as of may.md"
    assert sides.dest("README.public.md") == "README.md"
    assert cp.Sides.parse(sides.text()).dests == sides.dests


@pytest.mark.parametrize("line", ["public x.md -> .git/hooks/pre-push", "public .git/config", "public a -> b -> c.md"])
def test_a_git_folder_or_a_second_arrow_in_a_path_is_refused(line):
    with pytest.raises(cp.Usage, match="line 1"):
        cp.Sides.parse(line + "\n")


def test_a_short_marker_hits_inside_longer_words_and_other_words_do_not():
    assert list(cp.marker_hits("the wrench\n", ["wren"])) == [(1, 1)]
    assert list(cp.marker_hits("a warren of halls\n", ["Wren Halloway"])) == []


@pytest.mark.parametrize("text", ["public a.md -> b.md\npublic c.md -> b.md\n", "public b.md\npublic a.md -> b.md\n",
                                  "public app/\npublic x.md -> app/x.md\n"])
def test_two_sources_for_one_public_path_are_refused(text):
    with pytest.raises(cp.Usage, match="two sources"):
        cp.Sides.parse(text)


def test_the_setups_own_files_are_declared_one_by_one_and_a_private_rule_wins_over_them():
    view = cp.Sides.parse("public app/\nsetup docs/glossary.md\nsetup archive/LOG.md\nprivate archive/\n").public_view()
    assert view.declared_public("docs/glossary.md")
    assert not view.declared_public("docs/other.md"), "the setup declares files, never a folder"
    assert not view.declared_public("archive/LOG.md"), "an explicit private rule wins over the setup's line"


# ---------------------------------------------------------------- the gate on what is staged

@needs_gitleaks
def test_a_clean_staged_tree_passes_and_says_what_it_checked(tmp_path):
    _, public = pair(tmp_path)
    rc, out = gate(public, "--staged")
    assert rc == 0, out
    for part in ("declared public", "agent tool's files", "markers", "gitleaks", "ignore", "identity",
                 "listed, not read"):
        assert part in out, (part, out)


@needs_gitleaks
def test_an_undeclared_file_stops_the_gate(tmp_path):
    _, public = pair(tmp_path)
    put(public, "notes/todo.md", "later\n")
    rc, out = gate(public, "--staged")
    assert rc == 1 and "notes/todo.md" in out and "not declared public" in out, out


@needs_gitleaks
def test_files_under_the_setups_folders_need_their_own_line_and_a_private_rule_wins(tmp_path):
    _, public = pair(tmp_path, sides=SIDES + "setup docs/glossary.md\nprivate docs/internal/\n")
    put(public, "docs/glossary.md", "# Glossary\n")
    rc, out = gate(public, "--staged")
    assert rc == 0, out
    put(public, "docs/internal/contract.md", "terms\n")
    put(public, "archive/private/notes.md", "notes\n")
    rc, out = gate(public, "--staged")
    assert rc == 1 and "docs/internal/contract.md" in out and "archive/private/notes.md" in out, out


@needs_gitleaks
def test_a_marker_stops_the_gate_named_by_its_number_and_place_never_its_words(tmp_path):
    _, public = pair(tmp_path)
    put(public, "app/main.py", "# kept by Wren Halloway\n")
    rc, out = gate(public, "--staged")
    assert rc == 1 and "marker 1" in out and "app/main.py:1" in out, out
    assert "Wren Halloway" not in out


@needs_gitleaks
def test_a_marker_in_the_identity_or_the_message_stops_the_gate(tmp_path):
    _, public = pair(tmp_path)
    rc, out = gate(public, "--staged", "--message", "First state, from wren@private.example")
    assert rc == 1 and "marker 2" in out and "message" in out, out
    git(public, "config", "user.name", "Wren Halloway")
    rc, out = gate(public, "--staged")
    assert rc == 1 and "identity" in out, out


@needs_gitleaks
def test_an_empty_markers_list_is_said(tmp_path):
    _, public = pair(tmp_path, markers="")
    rc, out = gate(public, "--staged")
    assert rc == 0 and "markers: none were given" in out, out


@needs_gitleaks
def test_a_secret_stops_the_gate(tmp_path):
    _, public = pair(tmp_path)
    put(public, "app/config.py", f"TOKEN = '{token()}'\n")
    rc, out = gate(public, "--staged")
    assert rc == 1 and "gitleaks" in out and "app/config.py" in out, out


@needs_gitleaks
@pytest.mark.parametrize("rel", [".claude/settings.json", "AGENTS.md", "app/CLAUDE.md", ".mcp.json",
                                 ".Claude/settings.json", "app/claude.md", "Agents.md", ".MCP.json"])
def test_an_agent_tools_file_stops_the_gate(tmp_path, rel):
    _, public = pair(tmp_path, sides=SIDES + "public .claude/\npublic AGENTS.md\npublic .mcp.json\n")
    put(public, rel, "{}\n")
    rc, out = gate(public, "--staged")
    assert rc == 1 and rel in out and "agent tool" in out, out


@needs_gitleaks
def test_a_local_entry_must_stay_ignored_by_the_public_repositorys_own_rules(tmp_path):
    _, public = pair(tmp_path)
    (public / "app" / ".gitignore").write_text("# nothing\n")
    git(public, "add", "-A")
    rc, out = gate(public, "--staged")
    assert rc == 1 and "app/.env" in out, out


@needs_gitleaks
def test_a_local_entry_ignored_only_by_an_unpublished_rule_stops_the_gate(tmp_path):
    _, public = pair(tmp_path)
    (public / "app" / ".gitignore").write_text("# nothing\n")
    (public / ".git" / "info" / "exclude").write_text("app/.env\n")
    git(public, "add", "-A")
    rc, out = gate(public, "--staged")
    assert rc == 1 and "app/.env" in out and "ignored only by" in out, out


@needs_gitleaks
def test_an_ignored_entry_without_the_word_local_stops_the_gate(tmp_path):
    _, public = pair(tmp_path)
    put(public, "app/.gitignore", ".env\nbackups/\n")
    put(public, "app/backups/dump.sql", "rows\n", stage=False)
    rc, out = gate(public, "--staged")
    assert rc == 1 and "app/backups/" in out and "private" in out, out


@needs_gitleaks
def test_a_private_file_inside_a_local_folder_stops_the_gate(tmp_path):
    _, public = pair(tmp_path, sides=SIDES + "local app/cache/\nprivate app/cache/keys.txt\n")
    put(public, "app/.gitignore", ".env\ncache/\n")
    put(public, "app/cache/index.bin", "cache\n", stage=False)
    rc, out = gate(public, "--staged")
    assert rc == 0, out
    put(public, "app/cache/keys.txt", "secret keys\n", stage=False)
    rc, out = gate(public, "--staged")
    assert rc == 1 and "app/cache/keys.txt" in out, out


@needs_gitleaks
def test_an_untracked_file_inside_the_public_folder_stops_the_gate(tmp_path):
    _, public = pair(tmp_path)
    put(public, "app/scratch.txt", "later\n", stage=False)
    rc, out = gate(public, "--staged")
    assert rc == 1 and "app/scratch.txt" in out, out


@needs_gitleaks
def test_the_old_historys_e_mail_stops_the_gate_unless_the_owner_said_yes(tmp_path):
    _, public = pair(tmp_path, markers="")
    git(public, "config", "user.email", "wren@private.example")
    rc, out = gate(public, "--staged")
    assert rc == 1 and "old history" in out, out
    rc, out = gate(public, "--staged", "--sides", str(tmp_path / "larder" / "public-paths.txt"), "--old-email-ok")
    assert rc == 0, out


@needs_gitleaks
def test_images_and_binary_files_are_listed_not_read(tmp_path):
    _, public = pair(tmp_path)
    (public / "app" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0Wren Halloway")
    git(public, "add", "-A")
    rc, out = gate(public, "--staged")
    assert rc == 0 and "app/logo.png" in out and "listed, not read" in out, out


def test_without_gitleaks_the_gate_fails_naming_the_install(tmp_path):
    _, public = pair(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "git").symlink_to(shutil.which("git"))
    rc, out = gate(public, "--staged", env=dict(ENV, PATH=str(bin_dir)))
    assert rc == 1 and "gitleaks is not installed" in out and "install" in out, out


@pytest.mark.parametrize("code", [0, 1])
def test_a_gitleaks_that_writes_no_report_did_not_run_and_fails_the_gate(tmp_path, code):
    _, public = pair(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "gitleaks"
    fake.write_text(f"#!/bin/sh\nexit {code}\n")
    fake.chmod(0o755)
    rc, out = gate(public, "--staged", env=dict(ENV, PATH=f"{bin_dir}{os.pathsep}{ENV['PATH']}"))
    assert rc == 1 and "did not run" in out, out


@needs_gitleaks
def test_an_untracked_gitleaks_configuration_fails_the_gate_and_a_tracked_one_is_said(tmp_path):
    _, public = pair(tmp_path)
    put(public, "app/config.py", f"TOKEN = '{token()}'\n")
    (public / ".gitleaks.toml").write_text("[allowlist]\npaths = ['.*']\n")
    rc, out = gate(public, "--staged")
    assert rc == 1 and ".gitleaks.toml" in out and "untracked" in out, out
    _, public = pair(tmp_path / "second", sides=SIDES + "public .gitleaks.toml\n")
    put(public, ".gitleaks.toml", '[extend]\nuseDefault = true\n')
    rc, out = gate(public, "--staged")
    assert rc == 0 and "the repository's own .gitleaks.toml is in effect" in out, out


def test_the_lists_are_found_on_the_private_side_and_their_absence_is_a_usage_error(tmp_path):
    private, public = pair(tmp_path)
    (private / "public-paths.txt").unlink()
    rc, out = gate(public, "--staged")
    assert rc == 2 and "public-paths.txt" in out, out


# ---------------------------------------------------------------- the pre-push hook: every object a push sends

@needs_gitleaks
def test_a_clean_push_lands(tmp_path):
    public, env, bare = first_push(tmp_path)
    assert on_remote(bare, "refs/heads/main")


@needs_gitleaks
def test_a_marker_added_then_removed_inside_the_pushed_range_stops_the_push(tmp_path):
    public, env, bare = first_push(tmp_path)
    put(public, "app/main.py", "# kept by Wren Halloway\n")
    commit(public, "a note")
    put(public, "app/main.py", "def main():\n    return 1\n")
    commit(public, "the note removed")
    rc, out = push(public, env, "main")
    assert rc != 0 and "marker 1" in out, out


@needs_gitleaks
def test_a_secret_committed_then_removed_inside_the_pushed_range_stops_the_push(tmp_path):
    public, env, bare = first_push(tmp_path)
    put(public, "app/config.py", f"TOKEN = '{token()}'\n")
    commit(public, "config")
    git(public, "rm", "-q", "app/config.py")
    commit(public, "config removed")
    rc, out = push(public, env, "main")
    assert rc != 0 and "gitleaks" in out, out


@needs_gitleaks
@pytest.mark.parametrize("what", ["secret", "marker"])
def test_content_that_only_a_merge_commit_brings_stops_the_push(tmp_path, what):
    public, env, bare = first_push(tmp_path)
    git(public, "checkout", "-q", "-b", "side")
    put(public, "app/side.py", "s = 1\n")
    commit(public, "side")
    git(public, "checkout", "-q", "main")
    put(public, "app/main.py", "def main():\n    return 2\n")
    commit(public, "main")
    git(public, "merge", "-q", "--no-commit", "side")
    put(public, "app/config.py", f"TOKEN = '{token()}'\n" if what == "secret" else "# by Wren Halloway\n")
    git(public, "commit", "-q", "-m", "merge side")
    rc, out = push(public, env, "main")
    assert rc != 0 and ("gitleaks" in out if what == "secret" else "marker 1" in out), out


@needs_gitleaks
def test_an_undeclared_file_added_then_removed_inside_the_pushed_range_stops_the_push(tmp_path):
    public, env, bare = first_push(tmp_path)
    put(public, "notes/prices.md", "supplier prices: 4.20 per kilo\n")
    commit(public, "notes")
    git(public, "rm", "-q", "-r", "notes")
    commit(public, "drop notes")
    rc, out = push(public, env, "main")
    assert rc != 0 and "notes/prices.md" in out and "not declared public" in out, out


@needs_gitleaks
def test_an_annotated_tags_message_and_tagger_and_a_refs_name_are_judged(tmp_path):
    public, env, bare = first_push(tmp_path)
    git(public, "tag", "-a", "v1", "-m", "release by Wren Halloway")
    rc, out = push(public, env, "v1")
    assert rc != 0 and "marker 1" in out and "tag" in out, out
    git(public, "tag", "-a", "v2", "-m", "a tag", env=dict(env, GIT_COMMITTER_EMAIL="wren@private.example"))
    rc, out = push(public, env, "v2")
    assert rc != 0 and "old history" in out, out
    # A ref's name holds a marker as the gate matches markers, as plain text without case.
    git(public, "checkout", "-q", "-b", "notes-private.example")
    rc, out = push(public, env, "notes-private.example")
    assert rc != 0 and "marker 2" in out and "ref name" in out, out
    assert not on_remote(bare, "refs/tags/v1") and not on_remote(bare, "refs/heads/notes-private.example")


@needs_gitleaks
def test_a_marker_written_as_a_slug_stops_the_gate_and_the_push(tmp_path):
    _, public = pair(tmp_path)
    put(public, "app/main.py", "# kept by WrenHalloway\n")
    rc, out = gate(public, "--staged")
    assert rc == 1 and "marker 1" in out and "app/main.py:1" in out, out
    public, env, bare = first_push(tmp_path / "push")
    git(public, "checkout", "-q", "-b", "wren-halloway-notes")  # the review's own branch name
    rc, out = push(public, env, "wren-halloway-notes")
    assert rc != 0 and "marker 1" in out and "ref name" in out, out
    git(public, "checkout", "-q", "main")
    git(public, "mv", "app/main.py", "app/wren-halloway-lib.py")  # the review's own rename, on this fixture's file
    commit(public, "rename")
    rc, out = push(public, env, "main")
    assert rc != 0 and "marker 1" in out and "in the path" in out, out


@needs_gitleaks
def test_a_path_a_rule_made_private_after_it_was_pushed_says_only_a_new_history_can_go(tmp_path):
    public, env, bare = first_push(tmp_path)
    larder = tmp_path / "larder"
    with open(larder / "public-paths.txt", "a", encoding="utf-8") as f:
        f.write("private README.md\n")
    put(public, "app/main.py", "def main():\n    return 4\n")
    commit(public, "an ordinary change")
    rc, out = push(public, env, "main")
    assert rc != 0 and "README.md" in out, out
    said = [ln for ln in out.splitlines() if "only a new history" in ln]
    assert len(said) == 1 and "README.md" in said[0] and "already" in said[0], out


def tree_with(public, files):
    """A tree object holding these files, built without touching the index or the working tree."""
    entries = []
    for rel, text in files.items():
        oid = subprocess.run(["git", "-C", str(public), "hash-object", "-w", "--stdin"], input=text, env=ENV,
                             capture_output=True, text=True).stdout.strip()
        entries.append((rel, oid))
    index = public / ".git" / "scratch-index"
    for rel, oid in entries:
        subprocess.run(["git", "-C", str(public), "update-index", "--add", "--cacheinfo", f"100644,{oid},{rel}"],
                       env=dict(ENV, GIT_INDEX_FILE=str(index)), check=True)
    tree = subprocess.run(["git", "-C", str(public), "write-tree"], env=dict(ENV, GIT_INDEX_FILE=str(index)),
                          capture_output=True, text=True).stdout.strip()
    index.unlink()
    return tree


@needs_gitleaks
def test_a_tag_pointing_at_a_tree_has_every_path_judged(tmp_path):
    public, env, bare = first_push(tmp_path)
    tree = tree_with(public, {"notes/prices.md": "4.20\n", "CLAUDE.md": "rules\n", "wren-halloway.txt": "x\n"})
    rc, out = push(public, env, f"{tree}:refs/tags/snap")
    assert rc != 0 and "notes/prices.md" in out and "CLAUDE.md" in out and "marker 1" in out, out
    git(public, "tag", "-a", "snap2", "-m", "a snapshot", tree)
    rc, out = push(public, env, "snap2")
    assert rc != 0 and "notes/prices.md" in out, out
    assert not on_remote(bare, "refs/tags/snap") and not on_remote(bare, "refs/tags/snap2")


@needs_gitleaks
@pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen is not installed")
def test_a_signed_tags_text_carried_in_a_merge_commits_header_is_judged(tmp_path):
    public, env, bare = first_push(tmp_path)
    key = tmp_path / "key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    signing = ["-c", "gpg.format=ssh", "-c", f"user.signingkey={key}"]
    git(public, "checkout", "-q", "-b", "feature")
    put(public, "app/feature.py", "f = 1\n")
    commit(public, "feature")
    git(public, *signing, "-c", "user.name=Wren", "-c", "user.email=wren@users.noreply.example", "tag", "-s",
        "v-feat", "-m", "feature by Wren Halloway", env=dict(env, GIT_COMMITTER_NAME="Wren Halloway",
                                                             GIT_COMMITTER_EMAIL="wren@private.example"))
    git(public, "checkout", "-q", "main")
    git(public, "merge", "-q", "--no-ff", "-m", "merge the feature", "v-feat")
    assert "mergetag" in git(public, "cat-file", "commit", "HEAD")
    rc, out = push(public, env, "main")
    assert rc != 0 and "marker 1" in out and "old history" in out, out


@needs_gitleaks
def test_a_remote_recreated_under_the_same_name_has_everything_judged_again(tmp_path):
    public, env, bare = first_push(tmp_path)
    put(public, "app/kiwi.py", "fruit = 'kiwi'\n")
    commit(public, "kiwi")
    assert push(public, env, "main")[0] == 0
    with open(tmp_path / "larder" / "public-markers.txt", "a", encoding="utf-8") as f:
        f.write("kiwi\n")
    shutil.rmtree(bare)
    git(tmp_path, "init", "-q", "--bare", str(bare))
    rc, out = push(public, env, "main")
    assert rc != 0 and "marker 3" in out, out


@needs_gitleaks
def test_a_failing_read_of_the_old_history_stops_the_push(tmp_path):
    public, env, bare = first_push(tmp_path)
    (tmp_path / "larder" / ".git" / "refs" / "heads" / "broken").write_text("1" * 40 + "\n")
    put(public, "app/x.py", "x = 1\n")
    commit(public, "x")
    rc, out = push(public, env, "main")
    assert rc != 0 and "log" in out, out


@needs_gitleaks
def test_a_tree_entry_named_dot_dot_never_writes_outside_the_gates_folder(tmp_path):
    public, env, bare = first_push(tmp_path)
    blob = subprocess.run(["git", "-C", str(public), "hash-object", "-w", "--stdin"], input="escaped\n", env=ENV,
                          capture_output=True, text=True).stdout.strip()
    tree = subprocess.run(["git", "-C", str(public), "mktree"], input=f"100644 blob {blob}\tescaped.txt\n", env=ENV,
                          capture_output=True, text=True).stdout.strip()
    for _ in range(3):
        tree = subprocess.run(["git", "-C", str(public), "mktree"], input=f"040000 tree {tree}\t..\n", env=ENV,
                              capture_output=True, text=True).stdout.strip()
    head = git(public, "rev-parse", "HEAD").strip()
    crafted = subprocess.run(["git", "-C", str(public), "commit-tree", tree, "-p", head, "-m", "crafted"], env=ENV,
                             capture_output=True, text=True).stdout.strip()
    tmpd = tmp_path / "tmpd"
    tmpd.mkdir()
    rc, out = push(public, dict(env, TMPDIR=str(tmpd)), f"{crafted}:refs/heads/main")
    assert rc != 0 and ".." in out, out
    assert not list(tmpd.rglob("escaped.txt")) and not (tmp_path / "escaped.txt").exists()


@needs_gitleaks
def test_a_path_that_is_not_utf_8_is_reported_never_a_traceback(tmp_path):
    public, env, bare = first_push(tmp_path)
    name = os.fsdecode(b"app/caf\xe9.txt")
    (public / name).write_text("x\n")
    commit(public, "a latin-1 name")
    rc, out = push(public, env, "main")
    assert "Traceback" not in out, out


@needs_gitleaks
def test_a_rename_onto_a_path_that_holds_a_marker_stops_the_push(tmp_path):
    public, env, bare = first_push(tmp_path)
    git(public, "mv", "app/main.py", "app/private.example.py")
    commit(public, "rename")
    rc, out = push(public, env, "main")
    assert rc != 0 and "marker 2" in out and "in the path" in out, out


@needs_gitleaks
def test_an_agent_tools_file_in_a_path_with_a_space_stops_the_push(tmp_path):
    public, env, bare = first_push(tmp_path)
    put(public, "app/my notes/CLAUDE.md", "rules\n")
    commit(public, "notes")
    git(public, "rm", "-q", "-r", "app/my notes")
    commit(public, "notes removed")
    rc, out = push(public, env, "main")
    assert rc != 0 and "app/my notes/CLAUDE.md" in out and "agent tool" in out, out


@needs_gitleaks
def test_a_marker_that_begins_with_a_hash_is_a_marker_for_the_push_too(tmp_path):
    public, env, bare = first_push(tmp_path)
    with open(tmp_path / "larder" / "public-markers.txt", "a", encoding="utf-8") as f:
        f.write("#larder-deals\n")
    put(public, "app/prices.py", "# See #larder-deals for prices\n")
    commit(public, "prices")
    rc, out = push(public, env, "main")
    assert rc != 0 and "marker 3" in out, out


@needs_gitleaks
def test_object_ids_in_a_commits_headers_are_not_text_anyone_wrote(tmp_path):
    public, env, bare = first_push(tmp_path)
    put(public, "app/next.py", "n = 1\n")
    git(public, "add", "-A")
    tree = git(public, "write-tree").strip()
    parent = git(public, "rev-parse", "HEAD").strip()
    with open(tmp_path / "larder" / "public-markers.txt", "a", encoding="utf-8") as f:
        f.write(f"{tree[:9]}\n{parent[:9]}\n")
    commit(public, "next")
    rc, out = push(public, env, "main")
    assert rc == 0, out
    put(public, "app/later.py", f"# a note on {tree[:9]}\n")
    commit(public, "the same characters written by someone are a marker")
    rc, out = push(public, env, "main")
    assert rc != 0 and "marker 3" in out, out


@needs_gitleaks
@pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen is not installed")
def test_a_signature_block_is_not_text_anyone_wrote(tmp_path):
    public, env, bare = first_push(tmp_path)
    key = tmp_path / "key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    put(public, "app/signed.py", "s = 1\n")
    git(public, "add", "-A")
    git(public, "-c", "gpg.format=ssh", "-c", f"user.signingkey={key}", "commit", "-q", "-S", "-m", "signed")
    raw = git(public, "cat-file", "commit", "HEAD")
    block = [ln.strip() for ln in raw.split("-----BEGIN SSH SIGNATURE-----", 1)[1].splitlines()[1:3]]
    piece = next(w for w in ("".join(block)[i:i + 10] for i in range(0, 40)) if w.isalnum())
    with open(tmp_path / "larder" / "public-markers.txt", "a", encoding="utf-8") as f:
        f.write(piece + "\n")
    rc, out = push(public, env, "main")
    assert rc == 0, out


SIGNED = ["-----BEGIN PGP SIGNATURE-----", "", "iQEzBAABCAAdFiEEbeadedfacade0000", "=abcd",
          "-----END PGP SIGNATURE-----"]


def raw_judged(raw, markers):
    report = cp.Report()
    cp.judge_raw(report, "commit 0123456789", raw, markers, set(), True)
    return report.errors


def test_a_merge_commits_mergetag_is_parsed_as_a_tag_its_object_id_left_out_its_message_read_whole():
    """A `mergetag` header's value is a tag object: its `object` id is left out, and its message is read whole,
    the signature git appends to it included, and lines that begin with `parent ` or `tree ` too."""
    mergetag = ["mergetag object beadedface0123456789abcdef0123456789abcd", " type commit", " tag v1",
                " tagger Ann <ann@example.com> 1700000000 +0000", " ", " the release, said by its tag",
                " parent company notes"] + [" " + ln for ln in SIGNED]
    raw = "\n".join(["tree 0123456789abcdef0123456789abcdef01234567", "parent 0123456789abcdef0123456789abcdef01234567",
                     "author Ann <ann@example.com> 1700000000 +0000",
                     "committer Ann <ann@example.com> 1700000000 +0000", *mergetag, "", "Merge tag v1", ""])
    assert raw_judged(raw, ["beadedface"]) == []
    for marker in ("said by its tag", "parent company", "facade"):
        assert any("headers" in e for e in raw_judged(raw, [marker])), marker


def test_only_real_id_headers_are_left_out_and_the_gpgsig_header():
    raw = "\n".join(["tree 0123456789abcdef0123456789abcdef01234567", "parent Wren Halloway",
                     "author Ann <ann@example.com> 1700000000 +0000",
                     "committer Ann <ann@example.com> 1700000000 +0000",
                     "gpgsig -----BEGIN SSH SIGNATURE-----", " U1NIU0lHbeadedfacade", " -----END SSH SIGNATURE-----",
                     "", "a message", ""])
    assert raw_judged(raw, ["beadedfacade", "0123456789abcdef"]) == []
    assert any("headers" in e for e in raw_judged(raw, ["Wren Halloway"])), "a parent that is no id is read"


@pytest.mark.parametrize("message", [
    ["the notes", *SIGNED[:2], "signed by Wren Halloway", *SIGNED[2:]],
    ["-----BEGIN SIGNATURE-----", "and the rest is notes from Wren Halloway's review."],
    ["tree of the deal: Wren Halloway"],
])
def test_a_message_is_read_whole_whatever_it_holds(message):
    for kind, head in (("commit", ["tree 0123456789abcdef0123456789abcdef01234567",
                                   "author Ann <ann@example.com> 1700000000 +0000",
                                   "committer Ann <ann@example.com> 1700000000 +0000"]),
                       ("tag", ["object 0123456789abcdef0123456789abcdef01234567", "type commit", "tag v1",
                                "tagger Ann <ann@example.com> 1700000000 +0000"])):
        raw = "\n".join(head + [""] + message + [""])
        assert any("message" in e for e in raw_judged(raw, ["Wren Halloway"])), (kind, message)


@needs_gitleaks
def test_a_marker_inside_signature_armor_in_a_commit_message_stops_the_push(tmp_path):
    public, env, bare = first_push(tmp_path)
    put(public, "app/sig.py", "s = 2\n")
    commit(public, "notes\n\n-----BEGIN PGP SIGNATURE-----\nsigned by Wren Halloway <wren@private.example>\n"
                   "-----END PGP SIGNATURE-----\n")
    rc, out = push(public, env, "main")
    assert rc != 0 and "marker 1" in out and "message" in out, out


@needs_gitleaks
@pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen is not installed")
def test_a_merged_signed_tags_lines_that_begin_like_id_headers_are_read(tmp_path):
    public, env, bare = first_push(tmp_path)
    key = tmp_path / "key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    git(public, "checkout", "-q", "-b", "side")
    put(public, "app/side.py", "side = 1\n")
    commit(public, "side")
    git(public, "-c", "gpg.format=ssh", "-c", f"user.signingkey={key}", "tag", "-s", "mt1", "-m",
        "Release for the shop\n\nparent company notes for Wren Halloway\nobject of the deal: private.example")
    git(public, "checkout", "-q", "main")
    git(public, "merge", "-q", "--no-ff", "-m", "merge the side branch", "mt1")
    assert "mergetag" in git(public, "cat-file", "commit", "HEAD")
    rc, out = push(public, env, "main")
    assert rc != 0 and "marker 1" in out and "marker 2" in out, out


@needs_gitleaks
@pytest.mark.parametrize("data", [b"\xef\xbb\xbfWren Halloway\nprivate.example\n",
                                  b"Wren Halloway\r\nprivate.example\r\n", b"  Wren Halloway  \n\tprivate.example\n"])
def test_the_markers_file_is_read_whatever_its_bom_line_ends_and_surrounding_spaces(tmp_path, data):
    public, env, bare = first_push(tmp_path)
    (tmp_path / "larder" / "public-markers.txt").write_bytes(data)
    put(public, "README.md", "# Larder\n\nkept by Wren Halloway\n")
    commit(public, "credit")
    rc, out = push(public, env, "main")
    assert rc != 0 and "markers: 2 given" in out and "marker 1: README.md" in out, out


def test_the_markers_reader_drops_a_bom_handles_crlf_and_strips_each_line():
    assert cp.read_markers(b"\xef\xbb\xbfWren Halloway\r\n  #larder-deals \r\n\r\n \n") == \
        ["Wren Halloway", "#larder-deals"]
    assert cp.read_markers("\ufeffWren Halloway\n") == ["Wren Halloway"]


@pytest.mark.parametrize("marker", ["ab", "a-b", "x", "A. B"])
def test_a_marker_that_folds_to_fewer_than_three_characters_is_refused(marker):
    with pytest.raises(cp.Usage, match="fewer than 3"):
        cp.read_markers(f"Wren Halloway\n{marker}\n")


@needs_gitleaks
@pytest.mark.parametrize("how", ["inside-the-git-folder", "git-work-tree-set"])
def test_the_push_is_judged_for_its_content_wherever_it_is_run_from(tmp_path, how):
    public, env, bare = first_push(tmp_path)
    put(public, "README.md", "# Larder\n\nkept by Wren Halloway\n")
    commit(public, "credit")
    if how == "inside-the-git-folder":
        where, extra = public / ".git", {}
    else:
        where, extra = public, {"GIT_WORK_TREE": str(tmp_path / "larder")}
    p = subprocess.run(["git", "-C", str(where), "push", "origin", "main"], env=dict(env, **extra),
                       capture_output=True, text=True)
    out = p.stdout + p.stderr
    assert p.returncode != 0 and "marker 1: README.md" in out, out


@needs_gitleaks
def test_a_short_marker_in_the_file_stops_the_push_with_a_message(tmp_path):
    public, env, bare = first_push(tmp_path)
    with open(tmp_path / "larder" / "public-markers.txt", "a", encoding="utf-8") as f:
        f.write("ab\n")
    put(public, "app/next.py", "n = 1\n")
    commit(public, "next")
    rc, out = push(public, env, "main")
    assert rc != 0 and "marker 3" in out and "fewer than 3" in out, out


@needs_gitleaks
def test_a_replace_ref_does_not_hide_what_is_pushed(tmp_path):
    public, env, bare = first_push(tmp_path)
    base = git(public, "rev-parse", "HEAD").strip()
    put(public, "app/main.py", "def main():\n    return 3\n")
    commit(public, "clean")
    clean = git(public, "rev-parse", "HEAD").strip()
    git(public, "reset", "-q", "--hard", base)
    put(public, "app/main.py", "# by Wren Halloway\n")
    commit(public, "bad")
    bad = git(public, "rev-parse", "HEAD").strip()
    git(public, "replace", bad, clean)  # the local view now shows the clean commit where the bad one is
    rc, out = push(public, env, "main")
    assert rc != 0 and "marker 1" in out, out


@needs_gitleaks
def test_an_untracked_gitleaks_configuration_in_the_public_folder_stops_the_push(tmp_path):
    public, env, bare = first_push(tmp_path)
    (public / ".gitleaks.toml").write_text("[allowlist]\npaths = ['.*']\n")
    (public / ".git" / "info" / "exclude").write_text(".gitleaks.toml\n")
    put(public, "app/config.py", f"TOKEN = '{token()}'\n")
    commit(public, "config")
    rc, out = push(public, env, "main")
    assert rc != 0 and ".gitleaks.toml" in out, out


@needs_gitleaks
def test_a_deleted_branch_pushes_nothing_to_judge(tmp_path):
    public, env, bare = first_push(tmp_path)
    git(public, "checkout", "-q", "-b", "old")
    assert push(public, env, "old")[0] == 0
    rc, out = push(public, env, ":old")
    assert rc == 0 and not on_remote(bare, "refs/heads/old"), out


def test_the_hook_run_by_hand_outside_the_public_folder_says_where_it_must_run(tmp_path):
    public, _ = pair(tmp_path)
    hook = public / ".git" / "hooks" / "pre-push"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(HOOK.read_text(encoding="utf-8"), encoding="utf-8")
    hook.chmod(0o755)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    p = subprocess.run([str(hook), "origin", "x"], cwd=elsewhere, env=ENV, capture_output=True, text=True, input="")
    lines = (p.stdout + p.stderr).strip().splitlines()
    assert p.returncode != 0 and len(lines) == 1 and str(public) in lines[0], lines
