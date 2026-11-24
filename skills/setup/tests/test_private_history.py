"""Tests for the two-repository form when a project's history stays private (`history: private`).

The owner's folder stays where it is and becomes the private repository, its history kept; the public repository is
born inside it from one first commit, made only after a gate (the declared public paths, the owner's markers, a secret
scan, the agent tool's files, the ignore rules) has passed on what is staged for it. The project here is synthetic,
built by the tests: several commits, a private file present only in an early commit, an annotated tag, a replace ref,
an ignored secret file and an ignored private folder under public paths, the agent tool's settings, and a private
script importing public code.

Run from the repository's root: pytest skills/setup/tests. The tests that run the gate need gitleaks; without it they
are skipped, and the test of the gate's refusal without gitleaks still runs.
"""

import importlib.util
import json
import os
import random
import shutil
import string
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
SCAFFOLD = HERE.parent / "scaffold.py"
REPO = HERE.parent.parent.parent

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
needs_gitleaks = pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks is not installed")

OLD_AUTHOR = ("Wren Halloway", "wren@private.example")
PUBLIC_AUTHOR = "Wren <wren@users.noreply.example>"
MARKERS = ["Wren Halloway", "private.example"]
# The project's own paths and their sides; anything unnamed is private.
SIDES = {"app/": "public", "app/cache/": "local", "server/": "public", "server/.env": "local",
         "server/backups/": "private", "README.md": "public"}
ANSWERS = {"name": "Larder", "purpose": "a recipe book for people who cook for others", "mode": "conductor",
           "cut": "docs", "status": False, "handoff": False, "history": "private", "public_dir": "public",
           "sides": SIDES, "markers": MARKERS, "public_author": PUBLIC_AUTHOR}
# The project's files the public repository must track, and nothing else of the project's.
PUBLIC_FILES = {"README.md", "app/main.py", "app/lib.mjs", "server/main.py", "server/.gitignore"}
# What the setup itself may add on the public side with cut docs: its rung, its archive, its ignore files.
KIT_PUBLIC = ("docs/", "archive/", ".ignore", ".gitignore")
AGENT_NAMES = (".claude/", ".mcp.json", "AGENTS.md", "CLAUDE.md")


def run(*argv, cwd=None, env=None, stdin=None):
    return subprocess.run([str(a) for a in argv], cwd=cwd, env=env, capture_output=True, text=True, input=stdin)


def git(repo, *args, env=None):
    return run("git", "-C", repo, *args, env=env)


def lines(repo, *args, env=None):
    return [ln for ln in git(repo, *args, env=env).stdout.splitlines() if ln]


def token():
    """A string of the shape a GitHub personal token has, made at run time so no file of this repository holds one."""
    return "ghp_" + "".join(random.choice(string.ascii_letters + string.digits) for _ in range(36))


def home_env(home, path=None):
    """The environment every command runs in: a home of the test's own, so neither the user's git identity nor their
    agent tool's folder is read or written."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "XDG_"))}
    env.update(HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
    if path is not None:
        env["PATH"] = path
    return env


def make_home(base):
    """A home with the agent tool's per-path folder of the project, as a user who worked on it has one."""
    home = base / "home"
    projects = home / ".claude" / "projects" / "-some-key-of-the-project"
    projects.mkdir(parents=True)
    (projects / "session.jsonl").write_text('{"cwd": "the project"}\n', encoding="utf-8")
    (projects / "memory").mkdir()
    return home


def commit(root, message, env, email=None):
    assert git(root, "add", "-A", env=env).returncode == 0
    done = git(root, "-c", f"user.name={OLD_AUTHOR[0]}", "-c", f"user.email={email or OLD_AUTHOR[1]}", "commit", "-q",
               "-m", message, env=env)
    assert done.returncode == 0, done.stderr


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def history_project(base, env, name="larder", first_email=None):
    """The owner's project, with a history that must stay private. `first_email` signs the first commit only, which
    the replace ref below hides."""
    root = base / name
    root.mkdir()
    assert git(root, "init", "-q", "-b", "main", env=env).returncode == 0
    write(root, "README.md", "# Larder\n\nA recipe book.\n")
    write(root, "app/main.py", "def main():\n    return 'larder'\n")
    write(root, "app/lib.mjs", "export const portions = 4\n")
    write(root, "docs/notes.md", "# Notes\n\nWhat the suppliers charge.\n")
    write(root, "early-private.txt", "the supplier's prices, never public\n")
    write(root, ".gitignore", "app/cache/\nserver/backups/\nserver/tmp/\n.claude/settings.local.json\n")
    commit(root, "First state", env, email=first_email)
    git(root, "rm", "-q", "early-private.txt", env=env)
    write(root, "AGENTS.md", "# Larder\n\nRules for the agents.\n")
    write(root, ".claude/settings.json", '{"permissions": {}}\n')
    write(root, "tools/export.mjs", "import { portions } from '../app/lib.mjs'\nconsole.log(portions)\n")
    commit(root, "Agent layer and an export script", env)
    git(root, "-c", f"user.name={OLD_AUTHOR[0]}", "-c", f"user.email={OLD_AUTHOR[1]}", "tag", "-a", "v0.1", "-m",
        "first tag", env=env)
    write(root, "server/main.py", "PORT = 8000\n")
    write(root, "server/.gitignore", ".env\n")
    commit(root, "The server", env)
    second = lines(root, "rev-list", "--max-count=1", "--skip=1", "HEAD", env=env)[0]
    assert git(root, "-c", f"user.name={OLD_AUTHOR[0]}", "-c", f"user.email={OLD_AUTHOR[1]}", "replace", "--graft",
               second, env=env).returncode == 0
    # Ignored: a secret under a public path, a private folder under a public path, a cache, the personal settings.
    write(root, "server/.env", f"API_TOKEN={token()}\n")
    write(root, "server/backups/dump.sql", "the real rows\n")
    write(root, "app/cache/index.bin", "cache\n")
    write(root, "app/cache/keys.txt", "the cache's keys\n")
    write(root, "server/tmp/session.txt", "an ignored entry under a public path, with no rule\n")
    write(root, ".claude/settings.local.json", "{}\n")
    assert git(root, "status", "--porcelain", env=env).stdout == "", "the fixture must start clean"
    return root


def scaffold(root, answers, *flags, env):
    path = root.parent / f"{root.name}-answers.json"
    path.write_text(json.dumps(answers), encoding="utf-8")
    proc = run(sys.executable, SCAFFOLD, "--answers", path, "--target", root, *flags, env=env)
    return proc.returncode, proc.stdout + proc.stderr


def tree(folder):
    return {p.relative_to(folder): p.read_bytes() for p in sorted(folder.rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(folder).parts}


def old_history(root, env):
    """The old repository's commits, tags, and the objects only its history holds (not in its last tree)."""
    objects = {x.split()[0] for x in lines(root, "--no-replace-objects", "rev-list", "--all", "--objects", env=env)}
    head = {x.split()[2] for x in lines(root, "ls-tree", "-r", "-t", "HEAD", env=env)}
    head.add(git(root, "rev-parse", "HEAD^{tree}", env=env).stdout.strip())
    return SimpleNamespace(commits=set(lines(root, "--no-replace-objects", "rev-list", "--all", env=env)),
                           refs=set(lines(root, "for-each-ref", "--format=%(refname) %(objectname)", env=env)),
                           history_only=objects - head)


def do_split(base, answers=ANSWERS):
    """The whole private direction, as the session runs it: the dry run, the real run, the first commit."""
    home = make_home(base)
    env = home_env(home)
    root = history_project(base, env)
    before = old_history(root, env)
    claude_before = tree(home / ".claude")
    steps = {}
    for step, flags in (("dry", ("--dry-run",)), ("real", ()), ("commit", ("--first-commit",))):
        steps[step] = scaffold(root, answers, *flags, env=env)
        if steps[step][0] != 0:
            break
    return SimpleNamespace(root=root, public=root / answers["public_dir"], env=env, home=home, before=before,
                           claude_before=claude_before, steps=steps)


def split_done(s):
    """Fail with the step that stopped, its exit code and its output: the reason a test of the result fails."""
    for step in ("dry", "real", "commit"):
        rc, out = s.steps.get(step, (None, "not reached"))
        assert rc == 0, f"the {step} step exited {rc}:\n{out}"


@pytest.fixture(scope="module")
def split(tmp_path_factory):
    if shutil.which("gitleaks") is None:
        pytest.skip("gitleaks is not installed")
    return do_split(tmp_path_factory.mktemp("split"))


# ---------------------------------------------------------------- the dry run

@needs_gitleaks
def test_the_dry_run_keeps_the_folder_creates_the_public_repository_inside_and_writes_nothing(tmp_path):
    home = make_home(tmp_path)
    env = home_env(home)
    root = history_project(tmp_path, env)
    before = tree(root)
    rc, out = scaffold(root, ANSWERS, "--dry-run", env=env)
    assert rc == 0, out
    assert "KEEP" in out and "the private repository, its history kept" in out, out
    assert "CREATE" in out and "a new repository, empty history" in out, out
    for path in ("app/", "server/", "README.md"):
        assert f"MOVE     {path}" in out, (path, out)
    assert "STAYS    server/backups/" in out, out
    assert tree(root) == before and not (root / "public").exists()


@needs_gitleaks
def test_the_dry_run_lists_a_private_script_that_imports_public_code(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    rc, out = scaffold(root, ANSWERS, "--dry-run", env=env)
    assert rc == 0, out
    assert "tools/export.mjs" in out and "../app/lib.mjs" in out, out


@needs_gitleaks
def test_the_gate_on_a_clean_project_passes_and_names_what_it_checked(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    rc, out = scaffold(root, ANSWERS, "--dry-run", env=env)
    assert rc == 0, out
    for part in ("gitleaks", "markers", "declared public", "ignore"):
        assert part in out, (part, out)


# ---------------------------------------------------------------- the result: the acceptance lines the kit guarantees

def test_line_1_no_object_of_the_old_history_reaches_the_public_repository(split):
    split_done(split)
    # Every object only the old history holds, looked up in the public repository's object store, reachable or not.
    present = run("git", "-C", split.public, "--no-replace-objects", "cat-file", "--batch-check", env=split.env,
                  stdin="\n".join(sorted(split.before.history_only)) + "\n").stdout
    found = [ln for ln in present.splitlines() if not ln.endswith(" missing")]
    assert found == [], found
    assert not set(lines(split.public, "rev-list", "--all", env=split.env)) & split.before.commits
    assert lines(split.public, "for-each-ref", "--format=%(refname)", env=split.env) == ["refs/heads/main"]


def test_line_2_the_public_repository_tracks_exactly_the_declared_paths(split):
    split_done(split)
    tracked = set(lines(split.public, "ls-files", env=split.env))
    project = {f for f in tracked if not f.startswith(KIT_PUBLIC)}
    assert project == PUBLIC_FILES, project ^ PUBLIC_FILES
    assert "docs/notes.md" not in tracked and "tools/export.mjs" not in tracked


def test_line_3_no_private_entry_sits_inside_the_public_folder(split):
    split_done(split)
    assert (split.root / "server" / "backups" / "dump.sql").read_text() == "the real rows\n"
    assert not (split.public / "server" / "backups").exists()
    assert (split.root / ".claude" / "settings.local.json").exists() and not (split.public / ".claude").exists()
    inside = lines(split.public, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory",
                   env=split.env)
    assert sorted(inside) == ["app/cache/", "server/.env"], inside
    assert lines(split.public, "ls-files", "--others", "--exclude-standard", env=split.env) == []


def test_line_4_every_ignored_entry_in_the_public_folder_is_ignored_by_its_own_tracked_rules(split):
    split_done(split)
    tracked = set(lines(split.public, "ls-files", env=split.env))
    for entry in ("app/cache/index.bin", "server/.env"):
        out = git(split.public, "check-ignore", "-v", "--no-index", entry, env=split.env).stdout
        source = out.split(":", 1)[0]
        assert source in tracked, (entry, out)


def test_line_5_no_agent_tool_file_is_on_the_public_side(split):
    split_done(split)
    ever = set(lines(split.public, "log", "--all", "--name-only", "--format=", env=split.env))
    ever |= set(lines(split.public, "ls-files", env=split.env))
    assert not [f for f in ever if f.startswith(AGENT_NAMES) or f in AGENT_NAMES]
    # They stay on the private side, tracked as they were.
    assert {"AGENTS.md", ".claude/settings.json"} <= set(lines(split.root, "ls-files", env=split.env))


def test_line_8_the_public_commits_carry_the_public_author_never_the_old_e_mail(split):
    split_done(split)
    used = set(lines(split.public, "log", "--all", "--format=%an <%ae>%n%cn <%ce>", env=split.env))
    assert used == {PUBLIC_AUTHOR}, used
    assert git(split.public, "config", "user.email", env=split.env).stdout.strip() != OLD_AUTHOR[1]


def test_line_9_the_private_repository_keeps_its_whole_history_and_both_are_clean(split):
    split_done(split)
    assert split.before.commits <= set(lines(split.root, "--no-replace-objects", "rev-list", "--all", env=split.env))
    refs = set(lines(split.root, "for-each-ref", "--format=%(refname) %(objectname)", env=split.env))
    # The tags and the replace refs stay as they were; a branch moves on only by the private commit on top of it.
    kept = {r for r in split.before.refs if not r.startswith("refs/heads/")}
    assert kept <= refs, kept - refs
    for ref in split.before.refs - kept:
        name, old = ref.split()
        assert git(split.root, "merge-base", "--is-ancestor", old, name, env=split.env).returncode == 0, ref
    assert any(r.startswith("refs/replace/") for r in refs) and any(r.startswith("refs/tags/v0.1") for r in refs)
    assert git(split.root, "status", "--porcelain", env=split.env).stdout == ""
    assert git(split.public, "status", "--porcelain", env=split.env).stdout == ""


def test_line_13_the_public_repository_has_a_pre_push_hook_that_runs_the_gate(split):
    split_done(split)
    hook = split.public / ".git" / "hooks" / "pre-push"
    assert hook.is_file() and os.access(hook, os.X_OK)
    assert "check-public" in hook.read_text(encoding="utf-8")


def test_line_14_the_private_repository_holds_the_public_folder_as_a_submodule_only(split):
    split_done(split)
    entries = lines(split.root, "ls-files", "-s", env=split.env)
    gitlinks = [e for e in entries if e.split("\t", 1)[1] == "public"]
    assert len(gitlinks) == 1 and gitlinks[0].startswith("160000 "), gitlinks
    assert not [e for e in entries if e.split("\t", 1)[1].startswith("public/")]
    modules = git(split.root, "config", "-f", ".gitmodules", "--get-regexp", r"submodule\..*\.path", env=split.env)
    assert modules.stdout.split()[-1] == "public", modules.stdout


def test_the_kit_touches_nothing_under_the_users_agent_tool_folder(split):
    split_done(split)
    assert tree(split.home / ".claude") == split.claude_before


def test_the_private_script_importing_public_code_stays_private(split):
    split_done(split)
    assert "tools/export.mjs" in lines(split.root, "ls-files", env=split.env)


# ---------------------------------------------------------------- the gate stops the first commit

def plant_and_commit(root, rel, text, env):
    write(root, rel, text)
    commit(root, f"Plant {rel}", env)


@needs_gitleaks
@pytest.mark.parametrize("planted", ["secret", "marker"])
def test_a_planted_secret_or_marker_stops_the_setup_before_anything_is_written(tmp_path, planted):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    text = f"TOKEN = '{token()}'\n" if planted == "secret" else f"# kept by {MARKERS[0]}\n"
    plant_and_commit(root, "app/config.py", text, env)
    before = tree(root)
    head = git(root, "rev-parse", "HEAD", env=env).stdout
    rc, out = scaffold(root, ANSWERS, env=env)
    assert rc == 1 and "REFUSED" in out and "the gate" in out, out
    assert "app/config.py" in out, out
    assert tree(root) == before and not (root / "public").exists()
    assert git(root, "rev-parse", "HEAD", env=env).stdout == head
    rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
    assert rc == 1 and not (root / "public" / ".git").exists(), out


@needs_gitleaks
def test_an_empty_markers_list_is_accepted_only_as_given_and_the_gate_says_so(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    rc, out = scaffold(root, dict(ANSWERS, markers=[]), "--dry-run", env=env)
    assert rc == 0, out
    assert "markers: none were given" in out, out


def test_without_gitleaks_the_setup_refuses_naming_the_install_and_writes_nothing(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "git").symlink_to(shutil.which("git"))
    before = tree(root)
    rc, out = scaffold(root, ANSWERS, env=home_env(env["HOME"], path=str(bin_dir)))
    assert rc == 1, out
    assert "gitleaks is not installed" in out and "install" in out, out
    assert tree(root) == before and not (root / "public").exists()


@needs_gitleaks
def test_the_first_commit_is_refused_when_the_staged_tree_changed_after_the_gate(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    rc, out = scaffold(root, ANSWERS, env=env)
    assert rc == 0, out
    write(root / "public", "app/late.py", f"# {MARKERS[0]}\n")
    git(root / "public", "add", "app/late.py", env=env)
    rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
    assert rc == 1 and "REFUSED" in out, out
    assert git(root / "public", "rev-parse", "--verify", "HEAD", env=env).returncode != 0


@needs_gitleaks
def test_the_pre_push_hook_stops_a_push_that_carries_a_marker(tmp_path):
    s = do_split(tmp_path)
    split_done(s)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "check-public"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{REPO / "tools" / "src" / "check_public.py"}" "$@"\n')
    wrapper.chmod(0o755)
    env = home_env(s.home, path=f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    write(s.public, "app/later.py", f"# {MARKERS[0]}\n")
    git(s.public, "add", "-A", env=env)
    git(s.public, "commit", "-q", "-m", "later", env=env)
    head = git(s.public, "rev-parse", "HEAD", env=env).stdout.strip()
    hook = run(s.public / ".git" / "hooks" / "pre-push", "origin", "../nowhere.git", cwd=s.public, env=env,
               stdin=f"refs/heads/main {head} refs/heads/main {'0' * 40}\n")
    assert hook.returncode != 0, hook.stdout + hook.stderr


@needs_gitleaks
def test_a_marker_added_then_removed_inside_the_pushed_range_stops_the_push(tmp_path):
    s = do_split(tmp_path)
    split_done(s)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "check-public"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{REPO / "tools" / "src" / "check_public.py"}" "$@"\n')
    wrapper.chmod(0o755)
    env = home_env(s.home, path=f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    first = git(s.public, "rev-parse", "HEAD", env=env).stdout.strip()
    for text, message in ((f"# {MARKERS[0]}\n", "a note"), ("# a note\n", "the note reworded")):
        write(s.public, "app/later.py", text)
        git(s.public, "add", "-A", env=env)
        git(s.public, "commit", "-q", "-m", message, env=env)
    head = git(s.public, "rev-parse", "HEAD", env=env).stdout.strip()
    assert MARKERS[0] not in (s.public / "app" / "later.py").read_text()
    hook = run(s.public / ".git" / "hooks" / "pre-push", "origin", "../nowhere.git", cwd=s.public, env=env,
               stdin=f"refs/heads/main {head} refs/heads/main {first}\n")
    assert hook.returncode != 0 and "marker 1" in hook.stdout, hook.stdout + hook.stderr


@needs_gitleaks
def test_with_cut_none_the_public_repository_holds_only_the_projects_public_paths(tmp_path):
    s = do_split(tmp_path, dict(ANSWERS, cut="none"))
    split_done(s)
    tracked = set(lines(s.public, "ls-files", env=s.env))
    assert tracked == PUBLIC_FILES | {".gitignore"}, tracked
    # Every file the setup writes stays private, at the root of the owner's folder.
    assert {"AGENTS.md", "ai-docs/README.md", "archive/LOG.md"} <= set(lines(s.root, "ls-files", env=s.env))


def test_a_folder_with_commits_handed_over_for_two_repositories_needs_the_history_answer(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    answers = {k: v for k, v in ANSWERS.items() if k not in ("history", "sides", "markers", "public_author")}
    rc, out = scaffold(root, answers, "--dry-run", env=env)
    assert rc == 2 and "'history' is required" in out, out


@needs_gitleaks
def test_an_ignored_entry_under_a_public_path_with_no_rule_stays_private_where_it_is(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    rc, out = scaffold(root, ANSWERS, "--dry-run", env=env)
    assert rc == 0 and "STAYS    server/tmp/" in out and "no rule: private" in out, out


def test_no_rule_keeps_an_ignored_entry_where_it_is_after_the_split(split):
    split_done(split)
    assert (split.root / "server" / "tmp" / "session.txt").is_file()
    assert not (split.public / "server" / "tmp").exists()


@needs_gitleaks
def test_the_first_commit_is_refused_when_the_staged_tree_changed_even_with_nothing_the_gate_would_find(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    rc, out = scaffold(root, ANSWERS, env=env)
    assert rc == 0, out
    write(root / "public", "app/late.py", "x = 2\n")
    git(root / "public", "add", "app/late.py", env=env)
    rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
    assert rc == 1 and "not what the gate passed" in out, out
    assert git(root / "public", "rev-parse", "--verify", "HEAD", env=env).returncode != 0


@needs_gitleaks
def test_a_local_entry_never_becomes_tracked(split):
    split_done(split)
    tracked = set(lines(split.public, "ls-files", env=split.env))
    assert not {f for f in tracked if f.startswith(("app/cache/", "server/.env"))}
    assert (split.public / "server" / ".env").read_text().startswith("API_TOKEN=")


# ---------------------------------------------------------------- round 4: the review's findings and the gaps

def gate_on_path(tmp_path):
    """A PATH with `check-public` on it, as an installed one would be."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    wrapper = bin_dir / "check-public"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{REPO / "tools" / "src" / "check_public.py"}" "$@"\n')
    wrapper.chmod(0o755)
    return f"{bin_dir}{os.pathsep}{os.environ['PATH']}"


def state(root, env):
    """What an undo must give back: every file with its bytes (the ignored ones too), the index, the status."""
    files = {p.relative_to(root): (p.read_bytes() if not p.is_symlink() else str(os.readlink(p)).encode())
             for p in sorted(root.rglob("*")) if (p.is_file() or p.is_symlink()) and ".git" not in p.relative_to(root).parts}
    folders = {p.relative_to(root) for p in root.rglob("*") if p.is_dir() and not p.is_symlink()
               and ".git" not in p.relative_to(root).parts}
    return files, folders, git(root, "ls-files", "-s", env=env).stdout, \
        git(root, "status", "--porcelain", env=env).stdout


@needs_gitleaks
def test_a_first_commit_that_fails_midway_has_its_hook_already_and_a_rerun_completes_it(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 0
    blocker = root / ".git" / "hooks" / "pre-commit"
    blocker.write_text("#!/bin/sh\necho 'private lint failed' >&2\nexit 1\n")
    blocker.chmod(0o755)
    rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
    assert rc == 1 and "private lint failed" in out, out
    hook = root / "public" / ".git" / "hooks" / "pre-push"
    assert hook.is_file() and os.access(hook, os.X_OK), "the public commit exists, so its hook must too"
    blocker.unlink()
    rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
    assert rc == 0, out
    assert git(root, "status", "--porcelain", env=env).stdout == ""
    assert git(root / "public", "status", "--porcelain", env=env).stdout == ""
    assert lines(root / "public", "rev-list", "--count", "HEAD", env=env) == ["1"]


@needs_gitleaks
@pytest.mark.parametrize("how", ["global", "included"])
def test_a_hooks_path_in_effect_is_refused_before_anything_is_written_with_the_command(tmp_path, how):
    home = make_home(tmp_path)
    hooks = tmp_path / "global-hooks"
    if how == "global":
        (home / ".gitconfig").write_text(f"[core]\n\thooksPath = {hooks}\n")
    else:
        (home / ".gitconfig-hooks").write_text(f"[core]\n\thooksPath = {hooks}\n")
        (home / ".gitconfig").write_text(f"[include]\n\tpath = {home / '.gitconfig-hooks'}\n")
    env = home_env(home)
    root = history_project(tmp_path, env)
    before = tree(root)
    rc, out = scaffold(root, ANSWERS, env=env)
    assert rc == 1 and "core.hooksPath" in out and "--unset core.hooksPath" in out, out
    assert tree(root) == before and not (root / "public").exists()


@needs_gitleaks
def test_a_hooks_path_set_in_the_public_repository_before_the_first_commit_is_refused(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 0
    git(root / "public", "config", "core.hooksPath", str(tmp_path / "elsewhere"), env=env)
    rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
    assert rc == 1 and "core.hooksPath" in out and "--unset core.hooksPath" in out, out
    assert git(root / "public", "rev-parse", "--verify", "-q", "HEAD", env=env).returncode != 0
    assert git(root / "public", "config", "--local", "core.hooksPath", env=env).stdout.strip() == \
        str(tmp_path / "elsewhere"), "the setup leaves the public repository's configuration alone"


@needs_gitleaks
@pytest.mark.parametrize("where", ["worktree-config", "environment"])
def test_the_hooks_path_refusal_names_the_command_that_unsets_it_where_it_is_set(tmp_path, where):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 0
    public = root / "public"
    if where == "worktree-config":
        git(public, "config", "extensions.worktreeConfig", "true", env=env)
        git(public, "config", "--worktree", "core.hooksPath", str(tmp_path / "elsewhere"), env=env)
        rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
        assert rc == 1 and f"git -C {public} config --worktree --unset core.hooksPath" in out, out
        git(public, "config", "--worktree", "--unset", "core.hooksPath", env=env)
        rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
        assert rc == 0, out
    else:
        env = dict(env, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.hooksPath",
                   GIT_CONFIG_VALUE_0=str(tmp_path / "elsewhere"))
        rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
        assert rc == 1 and "GIT_CONFIG_" in out and "--unset" not in out, out


@needs_gitleaks
def test_after_absorbgitdirs_the_hook_names_the_cause_and_the_way_out_and_the_way_out_works(tmp_path):
    s = do_split(tmp_path)
    split_done(s)
    env = home_env(s.home, path=gate_on_path(tmp_path))
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(bare), env=env)
    git(s.public, "remote", "add", "origin", str(bare), env=env)
    assert git(s.root, "submodule", "absorbgitdirs", env=env).returncode == 0
    write(s.public, "app/later.py", f"# {MARKERS[0]}\n")
    git(s.public, "add", "-A", env=env)
    git(s.public, "commit", "-q", "-m", "later", env=env)
    pushed = run("git", "-C", s.public, "push", "origin", "main", env=env)
    said = pushed.stdout + pushed.stderr
    assert pushed.returncode != 0 and "absorbgitdirs" in said, said
    way_out = [ln.strip() for ln in said.splitlines() if ln.strip().startswith("way out: ")]
    assert way_out, said
    # Run where the owner stands after the refused push: inside the public folder.
    ran = run("sh", "-c", way_out[0][len("way out: "):], cwd=s.public, env=env)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    pushed = run("git", "-C", s.public, "push", "origin", "main", env=env)
    assert pushed.returncode != 0 and "marker 1" in pushed.stdout + pushed.stderr, pushed.stdout + pushed.stderr


@needs_gitleaks
def test_a_push_from_a_linked_worktree_of_the_public_repository_goes_through_the_gate(tmp_path):
    s = do_split(tmp_path)
    split_done(s)
    env = home_env(s.home, path=gate_on_path(tmp_path))
    assert git(s.public, "config", "--local", "--get", "core.hooksPath", env=env).returncode == 1
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(bare), env=env)
    git(s.public, "remote", "add", "origin", str(bare), env=env)
    assert run("git", "-C", s.public, "push", "origin", "main", env=env).returncode == 0
    worktree = tmp_path / "feature-worktree"
    assert git(s.public, "worktree", "add", "-q", str(worktree), "-b", "feat", env=env).returncode == 0
    write(worktree, "app/later.py", f"# {MARKERS[0]}\n")
    git(worktree, "add", "-A", env=env)
    git(worktree, "commit", "-q", "-m", "later", env=env)
    pushed = run("git", "-C", worktree, "push", "origin", "feat", env=env)
    assert pushed.returncode != 0 and "marker 1" in pushed.stdout + pushed.stderr, pushed.stdout + pushed.stderr
    write(worktree, "app/later.py", "later = 1\n")
    git(worktree, "commit", "-q", "--amend", "-a", "-m", "later", env=env)
    clean = run("git", "-C", worktree, "push", "origin", "feat", env=env)
    assert clean.returncode == 0, clean.stdout + clean.stderr


@needs_gitleaks
def test_a_real_push_goes_through_the_gate_the_setup_installed(tmp_path):
    s = do_split(tmp_path)
    split_done(s)
    env = home_env(s.home, path=gate_on_path(tmp_path))
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(bare), env=env)
    git(s.public, "remote", "add", "origin", str(bare), env=env)
    first = run("git", "-C", s.public, "push", "origin", "main", env=env)
    assert first.returncode == 0, first.stdout + first.stderr
    write(s.public, "app/later.py", f"# {MARKERS[0]}\n")
    git(s.public, "add", "-A", env=env)
    git(s.public, "commit", "-q", "-m", "later", env=env)
    second = run("git", "-C", s.public, "push", "origin", "main", env=env)
    assert second.returncode != 0 and "marker 1" in second.stdout + second.stderr, second.stdout + second.stderr


@needs_gitleaks
def test_a_private_path_inside_a_local_folder_stays_where_it_is_and_the_dry_run_says_so(tmp_path):
    s = do_split(tmp_path, dict(ANSWERS, sides=dict(SIDES, **{"app/cache/keys.txt": "private"})))
    dry = s.steps["dry"][1]
    assert "STAYS    app/cache/keys.txt" in dry, dry
    split_done(s)
    assert (s.root / "app" / "cache" / "keys.txt").read_text() == "the cache's keys\n"
    assert not (s.public / "app" / "cache" / "keys.txt").exists()
    assert (s.public / "app" / "cache" / "index.bin").is_file()


@pytest.mark.parametrize("root_file", [".gitignore", ".gitmodules", ".gitattributes"])
def test_the_private_sides_own_root_files_are_never_moved(tmp_path, root_file):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    rc, out = scaffold(root, dict(ANSWERS, sides=dict(SIDES, **{root_file: "public"})), "--dry-run", env=env)
    assert rc == 2 and root_file in out and f"as {root_file}" in out, out


def stopped_after_the_move(tmp_path, env, extra=None):
    """The project with a public README citing a private document, so the real run stops after it has written;
    `extra` changes the project first, committed with it."""
    root = history_project(tmp_path, env)
    write(root, "README.md", "# Larder\n\nSee [the notes](docs/notes.md).\n")
    if extra:
        extra(root)
    commit(root, "A link the public side cannot keep", env)
    return root


@needs_gitleaks
def test_a_stopped_run_ends_with_one_command_and_undo_gives_back_exactly_what_was_there(tmp_path):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env, lambda r: write(
        r, ".gitmodules", '[submodule "vendor"]\n\tpath = vendor\n\turl = ../vendor.git\n'))
    before = state(root, env)
    rc, out = scaffold(root, ANSWERS, env=env)
    assert rc == 1 and "STOPPED" in out and "README.md" in out, out
    last = out.strip().splitlines()[-1].strip()
    assert "--undo" in last and "scaffold.py" in last, last
    done = run("sh", "-c", last, env=env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert state(root, env) == before
    write(root, "README.md", "# Larder\n\nA recipe book.\n")
    commit(root, "The link dropped", env)
    rc, out = scaffold(root, ANSWERS, env=env)
    assert rc == 0, out


@needs_gitleaks
def test_undo_gives_back_ignored_instruction_files_the_run_replaced_or_removed_byte_for_byte(tmp_path):
    env = home_env(make_home(tmp_path))

    def ignored_instructions(r):
        with open(r / ".gitignore", "a", encoding="utf-8") as f:
            f.write("CLAUDE.md\n.claude/CLAUDE.md\n")
    root = stopped_after_the_move(tmp_path, env, ignored_instructions)
    write(root, "CLAUDE.md", "The owner's own rules, kept out of git.\n")
    write(root, ".claude/CLAUDE.md", "The owner's other rules.\n")
    before = state(root, env)
    rc, out = scaffold(root, ANSWERS, env=env)
    assert rc == 1 and "STOPPED" in out, out
    assert (root / "CLAUDE.md").read_text() != "The owner's own rules, kept out of git.\n"
    assert not (root / ".claude" / "CLAUDE.md").exists()
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 0, out
    assert state(root, env) == before


@needs_gitleaks
def test_undo_gives_back_a_renamed_file_the_run_moved_and_then_appended_to(tmp_path):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env, lambda r: write(r, "public-root.gitignore", "*.log\n"))
    before = state(root, env)
    answers = dict(ANSWERS, sides=dict(SIDES, **{"public-root.gitignore": "public as .gitignore"}))
    rc, out = scaffold(root, answers, env=env)
    assert rc == 1 and "STOPPED" in out, out
    rc, out = scaffold(root, answers, "--undo", env=env)
    assert rc == 0, out
    assert state(root, env) == before


@needs_gitleaks
def test_a_folder_whose_files_are_ignored_by_several_rules_stays_ignored_and_the_run_goes_on(tmp_path):
    env = home_env(make_home(tmp_path))

    def scattered(r):
        with open(r / ".gitignore", "a", encoding="utf-8") as f:
            f.write("*.log\n*.tmp\n")
    root = history_project(tmp_path, env)
    scattered(root)
    commit(root, "Two rules", env)
    write(root, "scratch/a.log", "a\n")
    write(root, "scratch/b.tmp", "b\n")
    assert "scratch/" in lines(root, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory",
                               env=env)
    rc, out = scaffold(root, ANSWERS, env=env)
    assert rc == 0, out
    assert not [f for f in lines(root, "diff", "--cached", "--name-only", env=env) if f.startswith("scratch/")]


@needs_gitleaks
def test_undo_refuses_when_a_path_the_run_wrote_changed_since_and_touches_nothing(tmp_path):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 1
    with open(root / "RATIONALE.md", "a", encoding="utf-8") as f:
        f.write("A line the owner added after the run.\n")
    after = state(root, env)
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 1 and "RATIONALE.md" in out, out
    assert state(root, env) == after


@needs_gitleaks
@pytest.mark.parametrize("change, named", [("a file added in a moved folder", "public/app/"),
                                           ("a moved file edited", "public/app/"),
                                           ("a file added at the public folder's top", "public/NOTES.txt")])
def test_undo_refuses_what_the_owner_did_in_the_public_folder_after_the_stop(tmp_path, change, named):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 1
    if change == "a file added in a moved folder":
        write(root / "public", "app/new-work.py", "work = 1\n")
    elif change == "a moved file edited":
        with open(root / "public" / "app" / "main.py", "a", encoding="utf-8") as f:
            f.write("# a fix written after the stop\n")
    else:
        write(root / "public", "NOTES.txt", "the owner's notes, written after the stop\n")
    after = state(root, env)
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 1 and named in out, out
    assert state(root, env) == after


@needs_gitleaks
def test_undo_lists_a_file_saved_at_a_moved_files_old_place_keeps_it_and_succeeds_once_it_is_gone(tmp_path):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    before = state(root, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 1
    write(root, "README.md", "EDITOR-SAVED NEW TEXT\n")
    after = state(root, env)
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    obstacles = [ln.strip() for ln in out.splitlines() if ln.startswith("    ")]
    assert rc == 1 and len(obstacles) == 1 and obstacles[0].startswith("README.md:"), out
    assert state(root, env) == after and (root / "README.md").read_text() == "EDITOR-SAVED NEW TEXT\n"
    (root / "README.md").unlink()
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 0, out
    assert state(root, env) == before


@needs_gitleaks
@pytest.mark.parametrize("foreign", ["plan/mine.md", "app/new.py"])
def test_undo_refuses_a_foreign_file_in_a_folder_the_run_made_or_at_a_moved_folders_old_place(tmp_path, foreign):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 1
    write(root, foreign, "the owner's own work\n")
    after = state(root, env)
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 1 and foreign.split("/")[0] in out and "Traceback" not in out, out
    assert state(root, env) == after


@needs_gitleaks
def test_undo_compares_the_index_by_its_entries_so_a_status_refresh_does_not_block_it(tmp_path):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    before = state(root, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 1
    os.utime(root / "docs" / "notes.md")
    git(root, "status", env=env)
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 0, out
    assert state(root, env) == before


@needs_gitleaks
def test_undo_says_what_it_compared_and_how(tmp_path):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 1
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 0, out
    last = out.strip().splitlines()[-1]
    assert "content hash" in last and "local" in last and "size" in last and "index" in last, last


def load_scaffold():
    spec = importlib.util.spec_from_file_location("scaffold_under_test", SCAFFOLD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Killed(BaseException):
    """What a kill looks like to the run: it stops between two lines, and nothing after runs."""


@needs_gitleaks
@pytest.mark.parametrize("act", ["move", "write", "git-init", "public-folder"])
def test_a_run_killed_between_an_act_and_its_record_is_undone_from_the_disk(tmp_path, monkeypatch, act):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    before = state(root, env)
    for name in [k for k in os.environ if k.startswith(("GIT_", "XDG_"))]:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    sc = load_scaffold()
    original = sc.Record.done

    def done(self, entry, **fields):
        if entry.get("act") == act:
            raise Killed(act)
        return original(self, entry, **fields)
    monkeypatch.setattr(sc.Record, "done", done)
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps(ANSWERS), encoding="utf-8")
    with pytest.raises(Killed):
        sc.main(["--answers", str(answers), "--target", str(root)])
    monkeypatch.undo()
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 0, out
    assert state(root, env) == before


def in_process(monkeypatch, env):
    """The scaffold loaded in this process, with the test's environment, for a test that stops it from inside."""
    for name in [k for k in os.environ if k.startswith(("GIT_", "XDG_"))]:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return load_scaffold()


def killed_run(tmp_path, monkeypatch, env, root, act, when):
    """The real run killed at the first `act`: `before` it happens (its record written, the act not done) or `after`
    it (done, its record not yet saying so)."""
    sc = in_process(monkeypatch, env)
    name = "act" if when == "before" else "done"
    original = getattr(sc.Record, name)

    def stop(self, entry, **fields):
        result = original(self, entry, **fields) if when == "before" else None
        if entry.get("act") == act:
            raise Killed(act)
        return result if when == "before" else original(self, entry, **fields)
    monkeypatch.setattr(sc.Record, name, stop)
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps(ANSWERS), encoding="utf-8")
    with pytest.raises(Killed):
        sc.main(["--answers", str(answers), "--target", str(root)])
    monkeypatch.undo()


@needs_gitleaks
@pytest.mark.parametrize("act", ["move", "write", "git-init", "mkdir"])
def test_a_run_killed_after_recording_an_act_and_before_doing_it_is_undone_from_the_disk(tmp_path, monkeypatch, act):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    before = state(root, env)
    killed_run(tmp_path, monkeypatch, env, root, act, "before")
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 0, out
    assert state(root, env) == before


@needs_gitleaks
def test_a_move_killed_before_its_record_and_changed_since_is_named_and_nothing_is_changed(tmp_path, monkeypatch):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    killed_run(tmp_path, monkeypatch, env, root, "move", "after")
    record = json.loads((root / ".git" / "airone-split.json").read_text(encoding="utf-8"))
    moved = next(a for a in record["acts"] if a["act"] == "move" and not a["done"])
    dest = root / moved["to"].rstrip("/")
    if dest.is_dir():
        write(dest, "added-after-the-kill.txt", "the owner's own work\n")
    else:
        with open(dest, "a", encoding="utf-8") as f:
            f.write("the owner's own line\n")
    after = state(root, env)
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 1 and "stopped while moving" in out and moved["from"] in out, out
    assert state(root, env) == after


@needs_gitleaks
def test_an_undo_stopped_midway_is_finished_by_running_it_again(tmp_path, monkeypatch):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    before = state(root, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 1
    sc = in_process(monkeypatch, env)

    def refuse(path, *a, **k):
        raise OSError(f"{path}: refused by the test")
    monkeypatch.setattr(sc.shutil, "rmtree", refuse)
    assert sc.main(["--target", str(root), "--undo"]) == 1
    monkeypatch.undo()
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 0, out
    assert state(root, env) == before


@needs_gitleaks
def test_undo_gives_back_a_file_the_run_wrote_twice(tmp_path):
    """The root .gitignore gets the setup's lines, then the private rule for an ignored file whose rule moved: two
    writes of one path, reversed newest first."""
    answers = dict(ANSWERS, sides={k: v for k, v in SIDES.items() if k != "server/.env"})
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    before = state(root, env)
    assert scaffold(root, answers, env=env)[0] == 1
    record = json.loads((root / ".git" / "airone-split.json").read_text(encoding="utf-8"))
    assert sum(1 for a in record["acts"] if a["act"] == "write" and a["path"] == ".gitignore") == 2
    rc, out = scaffold(root, answers, "--undo", env=env)
    assert rc == 0, out
    assert state(root, env) == before


@needs_gitleaks
def test_undo_refuses_an_empty_folder_of_the_owners_inside_a_folder_the_run_made(tmp_path):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 1
    (root / "plan" / "drafts").mkdir()
    after = state(root, env)
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 1 and "plan/drafts" in out and "Traceback" not in out, out
    assert state(root, env) == after


@needs_gitleaks
@pytest.mark.parametrize("folder, named", [("app", "app/: an empty folder is there again"),
                                           ("public/drafts", "public/drafts/"),
                                           ("public/app/empty-of-mine", "public/app/")])
def test_an_empty_folder_the_run_did_not_make_is_never_removed_and_is_an_obstacle(tmp_path, folder, named):
    """At a moved folder's old place, in the public folder, inside a moved folder: an empty folder of the owner's is
    listed, kept, and the undo goes through once the owner has taken it away."""
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    before = state(root, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 1
    (root / folder).mkdir()
    after = state(root, env)
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 1 and named in out and "Traceback" not in out, out
    assert state(root, env) == after and (root / folder).is_dir()
    (root / folder).rmdir()
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 0, out
    assert state(root, env) == before


@needs_gitleaks
def test_the_first_commit_reads_the_markers_file_as_the_push_gate_does(tmp_path):
    """A markers file saved with a byte-order mark and CRLF ends after the real run: its first marker still stops the
    first commit."""
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 0
    (root / "public-markers.txt").write_bytes(b"\xef\xbb\xbfLarder\r\nprivate.example\r\n")
    rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
    assert rc == 1 and "marker 1" in out, out
    assert git(root / "public", "rev-parse", "--verify", "-q", "HEAD", env=env).returncode != 0


@needs_gitleaks
def test_a_run_killed_while_staging_is_undone_and_says_so(tmp_path, monkeypatch):
    """Killed between the private repository's `git add` and the public one's: the index holds what the run staged,
    and its record does not say so yet."""
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    before = state(root, env)
    sc = in_process(monkeypatch, env)
    original = sc.git_ok

    def git_ok(where, *args, **kw):
        if args[:2] == ("add", "-A") and Path(where) == root / "public":
            raise Killed("staging")
        return original(where, *args, **kw)
    monkeypatch.setattr(sc, "git_ok", git_ok)
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps(ANSWERS), encoding="utf-8")
    with pytest.raises(Killed):
        sc.main(["--answers", str(answers), "--target", str(root)])
    monkeypatch.undo()
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 0, out
    assert state(root, env) == before


@needs_gitleaks
def test_an_index_changed_after_the_stop_is_refused_with_the_way_out_and_the_way_out_works(tmp_path):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    before = state(root, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 1
    git(root, "rm", "-q", "--cached", "docs/notes.md", env=env)
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 1 and f"git -C {root} reset -q" in out, out
    git(root, "reset", "-q", env=env)
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 0, out
    assert state(root, env) == before


@needs_gitleaks
@pytest.mark.parametrize("change", ["outside-path", "dotdot-from", "symlinked-parent", "saved-name", "truncated"])
def test_a_record_that_points_outside_the_project_is_refused_and_nothing_is_changed(tmp_path, change):
    env = home_env(make_home(tmp_path))
    root = stopped_after_the_move(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 1
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("not the project's\n")
    path = root / ".git" / "airone-split.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    digest = __import__("hashlib").sha256(b"not the project's\n").hexdigest()
    if change == "outside-path":
        record["acts"].append({"act": "write", "path": "../outside/keep.txt", "saved": None, "before": "absent",
                               "expect": digest, "after": digest, "done": True})
    elif change == "dotdot-from":
        move = next(a for a in record["acts"] if a["act"] == "move")
        move["from"] = "../outside/" + move["from"]
    elif change == "symlinked-parent":
        (root / "plan" / "escape").symlink_to(outside)
        record["acts"].append({"act": "write", "path": "plan/escape/keep.txt", "saved": None, "before": "absent",
                               "expect": digest, "after": digest, "done": True})
    elif change == "saved-name":
        write_act = next(a for a in record["acts"] if a["act"] == "write" and a["saved"])
        write_act["saved"] = "../../../outside/keep.txt"
    if change == "truncated":
        path.write_text(path.read_text(encoding="utf-8")[:200], encoding="utf-8")
    else:
        path.write_text(json.dumps(record), encoding="utf-8")
    after = state(root, env)
    rc, out = scaffold(root, ANSWERS, "--undo", env=env)
    assert rc == 1 and "not one the run wrote" in out and "Traceback" not in out, out
    assert (outside / "keep.txt").read_text() == "not the project's\n"
    assert state(root, env) == after


def test_the_undo_record_is_removed_once_the_first_commit_is_done(split):
    split_done(split)
    git_dir = split.root / ".git"
    assert not [p for p in git_dir.iterdir() if p.name.startswith("airone-")], list(git_dir.iterdir())


@needs_gitleaks
def test_an_ignored_file_whose_rule_moves_to_the_public_side_stays_ignored_on_the_private_side(tmp_path):
    sides = {k: v for k, v in SIDES.items() if k != "server/.env"}
    s = do_split(tmp_path, dict(ANSWERS, sides=sides))
    dry = s.steps["dry"][1]
    assert "IGNORE   .gitignore" in dry and "/server/.env" in dry, dry
    split_done(s)
    assert (s.root / "server" / ".env").is_file() and not (s.public / "server" / ".env").exists()
    assert "server/.env" not in lines(s.root, "ls-files", env=s.env)
    assert git(s.root, "check-ignore", "-q", "server/.env", env=s.env).returncode == 0


@needs_gitleaks
def test_the_private_commit_refuses_a_path_that_was_ignored_before_the_run(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 0
    git(root, "add", "-f", "server/tmp/session.txt", env=env)
    rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
    assert rc == 1 and "server/tmp/session.txt" in out and "ignored before" in out, out
    assert git(root / "public", "rev-parse", "--verify", "-q", "HEAD", env=env).returncode != 0


@needs_gitleaks
def test_a_public_commit_that_fails_has_its_hook_and_a_rerun_completes_it(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    assert scaffold(root, ANSWERS, env=env)[0] == 0
    public = root / "public"
    git(public, "config", "commit.gpgsign", "true", env=env)
    git(public, "config", "gpg.program", "false", env=env)
    rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
    assert rc == 1, out
    assert (public / ".git" / "hooks" / "pre-push").is_file()
    git(public, "config", "--unset", "commit.gpgsign", env=env)
    git(public, "config", "--unset", "gpg.program", env=env)
    rc, out = scaffold(root, ANSWERS, "--first-commit", env=env)
    assert rc == 0, out


@needs_gitleaks
def test_an_e_mail_that_only_a_replace_ref_hides_is_still_the_old_historys(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env, first_email="early@private.example")
    answers = dict(ANSWERS, public_author="Wren <early@private.example>", markers=[MARKERS[0]])
    rc, out = scaffold(root, answers, "--dry-run", env=env)
    assert rc == 1 and "signs the old history" in out, out


@needs_gitleaks
def test_a_public_path_can_take_another_name_and_the_private_one_stays(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    write(root, "README.public.md", "# Larder\n\nFor strangers.\n")
    write(root, "public-root.gitignore", "*.log\n")
    commit(root, "The public README and the public ignore rules, under names of their own", env)
    sides = dict(SIDES, **{"README.md": "private", "README.public.md": "public as README.md",
                           "public-root.gitignore": "public as .gitignore"})
    s_answers = dict(ANSWERS, sides=sides)
    for flags in ((), ("--first-commit",)):
        rc, out = scaffold(root, s_answers, *flags, env=env)
        assert rc == 0, out
    public = root / "public"
    assert (public / "README.md").read_text() == "# Larder\n\nFor strangers.\n"
    assert (root / "README.md").read_text() == "# Larder\n\nA recipe book.\n"
    ignore = (public / ".gitignore").read_text().splitlines()
    assert ignore[0] == "*.log", "the arriving file's own lines come first, untouched"
    tracked = set(lines(public, "ls-files", env=env))
    assert {"README.md", ".gitignore"} <= tracked and "README.public.md" not in tracked


@pytest.mark.parametrize("sides", [
    {"README.md": "public", "notes.md": "public as README.md"},
    {"app/": "public", "README.md": "public as app/README.md"},
])
def test_two_sources_for_one_public_path_are_refused(tmp_path, sides):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    rc, out = scaffold(root, dict(ANSWERS, sides=sides), "--dry-run", env=env)
    assert rc == 2 and "two sources" in out, out


def test_the_public_repository_ignores_the_agent_tools_files_whatever_their_case(split):
    split_done(split)
    for path in (".claude/settings.json", ".Claude/settings.json", ".mcp.json", ".MCP.json", "CLAUDE.md", "claude.md",
                 "app/Agents.md", "AGENTS.md"):
        assert git(split.public, "check-ignore", "-q", "--no-index", path, env=split.env).returncode == 0, path
    assert git(split.public, "check-ignore", "-q", "--no-index", "app/claudette.md", env=split.env).returncode == 1


def test_the_markers_file_holds_each_marker_as_a_line_and_nothing_else(split):
    split_done(split)
    assert (split.root / "public-markers.txt").read_text() == "".join(f"{m}\n" for m in MARKERS)


def test_the_setups_own_public_files_are_declared_one_by_one(split):
    split_done(split)
    text = (split.root / "public-paths.txt").read_text().splitlines()
    setup = {ln.split(" ", 1)[1] for ln in text if ln.startswith("setup ")}
    assert setup and all(not p.endswith("/") for p in setup), setup
    kit = {f for f in lines(split.public, "ls-files", env=split.env) if f.startswith(KIT_PUBLIC)}
    assert kit == setup, kit ^ setup


@needs_gitleaks
def test_a_symlink_to_a_folder_under_a_public_path_does_not_stop_the_dry_run(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    (root / "app" / "docs-link").symlink_to("../docs")
    commit(root, "A link to a folder", env)
    rc, out = scaffold(root, ANSWERS, "--dry-run", env=env)
    assert rc == 0, out


# ---------------------------------------------------------------- refusals

@pytest.mark.parametrize("change", [
    {"history": "maybe"},
    {"move_from": "/somewhere/larder"},
    {"cut": "all"},
    {"sides": None},
    {"markers": None},
    {"public_author": None},
    {"sides": {"app/": "private"}},
    {"markers": ["--"]},
    {"markers": ["two\nlines"]},
    {"markers": ["Wren Halloway", "ab"]},
    {"markers": ["a-b"]},
])
def test_invalid_answers_for_the_private_history_exit_two_and_write_nothing(tmp_path, change):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    answers = {k: v for k, v in dict(ANSWERS, **change).items() if v is not None}
    before = tree(root)
    rc, out = scaffold(root, answers, "--dry-run", env=env)
    assert rc == 2, out
    # Each is refused for its own reason, never as an answer the scaffold does not know.
    assert "unknown answer" not in out, out
    rc, out = scaffold(root, answers, env=env)
    assert rc == 2 and tree(root) == before, out


def refusal_case(base, env, case):
    """Change the project or the answers so that exactly one precondition fails; (answers, the message expected)."""
    root = base / "larder"
    answers = dict(ANSWERS)
    if case == "dirty":
        write(root, "app/main.py", "def main():\n    return 'changed'\n")
        return answers, "uncommitted changes"
    if case == "public-exists":
        (root / "public").mkdir()
        write(root, "public/x.txt", "here first\n")
        return answers, "exists"
    if case == "no-such-path":
        return dict(answers, sides=dict(SIDES, **{"web/": "public"})), "web/ is not in the repository"
    if case == "agent-dir-public":
        return dict(answers, sides=dict(SIDES, **{".claude/": "public"})), "never public"
    if case == "instructions-public":
        return dict(answers, sides=dict(SIDES, **{"AGENTS.md": "public"})), "never public"
    if case == "old-e-mail":
        return dict(answers, public_author=f"Wren <{OLD_AUTHOR[1]}>"), "signs the old history"
    raise ValueError(case)


@needs_gitleaks
@pytest.mark.parametrize("case", ["dirty", "public-exists", "no-such-path", "agent-dir-public",
                                  "instructions-public", "old-e-mail"])
def test_a_failed_precondition_refuses_the_run_before_anything_is_written(tmp_path, case):
    env = home_env(make_home(tmp_path))
    history_project(tmp_path, env)
    answers, expected = refusal_case(tmp_path, env, case)
    root = tmp_path / "larder"
    before = tree(root)
    rc, out = scaffold(root, answers, env=env)
    assert rc == 1 and "REFUSED" in out and expected in out, out
    assert tree(root) == before


@needs_gitleaks
def test_the_old_e_mail_is_allowed_when_the_owner_says_so(tmp_path):
    env = home_env(make_home(tmp_path))
    root = history_project(tmp_path, env)
    # The markers here leave the e-mail out: the owner's yes to an identity cannot overrule their own marker list.
    answers = dict(ANSWERS, public_author=f"Wren <{OLD_AUTHOR[1]}>", old_email_ok=True, markers=[MARKERS[0]])
    rc, out = scaffold(root, answers, "--dry-run", env=env)
    assert rc == 0, out
    rc, out = scaffold(root, dict(answers, markers=MARKERS), "--dry-run", env=env)
    assert rc == 1 and "in the identity" in out, out


def test_a_folder_without_commits_is_refused_for_the_private_history(tmp_path):
    env = home_env(make_home(tmp_path))
    root = tmp_path / "larder"
    root.mkdir()
    git(root, "init", "-q", env=env)
    write(root, "app/main.py", "x = 1\n")
    rc, out = scaffold(root, ANSWERS, env=env)
    assert rc == 1 and "REFUSED" in out and "no commits" in out, out
    assert not (root / "public").exists()
