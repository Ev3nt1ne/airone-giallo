"""Tests for the two-repository form when a project's history stays private (`history: private`).

The owner's folder stays where it is and becomes the private repository, its history kept; the public repository is
born inside it from one first commit, made only after a gate (the declared public paths, the owner's markers, a secret
scan, the agent tool's files, the ignore rules) has passed on what is staged for it. The project here is synthetic,
built by the tests: several commits, a private file present only in an early commit, an annotated tag, a replace ref,
an ignored secret file and an ignored private folder under public paths, the agent tool's settings, and a private
script importing public code.

Not built yet. Every test is marked `xfail(strict=True)`: the suite stays green while the direction is missing, and a
test that starts passing fails the suite until its mark is removed, so no test can pass unnoticed. `--runxfail` shows
each failure's own reason.

Run from the repository's root: pytest skills/setup/tests. The tests that run the gate need gitleaks; without it they
are skipped, and the test of the gate's refusal without gitleaks still runs.
"""

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

pytestmark = [
    pytest.mark.xfail(strict=True, reason="the private-history direction of the setup is not built yet"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed"),
]
needs_gitleaks = pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks is not installed")

OLD_AUTHOR = ("Wren Halloway", "wren@private.example")
PUBLIC_AUTHOR = "Wren <wren@users.noreply.example>"
MARKERS = ["Wren Halloway", "private.example"]
# The project's own paths and their sides; anything unnamed is private.
SIDES = {"app/": "public", "app/cache/": "public", "server/": "public", "server/.env": "public",
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


def commit(root, message, env):
    assert git(root, "add", "-A", env=env).returncode == 0
    done = git(root, "-c", f"user.name={OLD_AUTHOR[0]}", "-c", f"user.email={OLD_AUTHOR[1]}", "commit", "-q", "-m",
               message, env=env)
    assert done.returncode == 0, done.stderr


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def history_project(base, env, name="larder"):
    """The owner's project, with a history that must stay private."""
    root = base / name
    root.mkdir()
    assert git(root, "init", "-q", "-b", "main", env=env).returncode == 0
    write(root, "README.md", "# Larder\n\nA recipe book.\n")
    write(root, "app/main.py", "def main():\n    return 'larder'\n")
    write(root, "app/lib.mjs", "export const portions = 4\n")
    write(root, "docs/notes.md", "# Notes\n\nWhat the suppliers charge.\n")
    write(root, "early-private.txt", "the supplier's prices, never public\n")
    write(root, ".gitignore", "app/cache/\nserver/backups/\n.claude/settings.local.json\n")
    commit(root, "First state", env)
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
    assert split.before.refs <= refs, split.before.refs - refs
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


# ---------------------------------------------------------------- refusals

@pytest.mark.parametrize("change", [
    {"history": "maybe"},
    {"move_from": "/somewhere/larder"},
    {"cut": "none"},
    {"cut": "all"},
    {"sides": None},
    {"markers": None},
    {"public_author": None},
    {"sides": {"app/": "private"}},
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
    answers = dict(ANSWERS, public_author=f"Wren <{OLD_AUTHOR[1]}>", old_email_ok=True)
    rc, out = scaffold(root, answers, "--dry-run", env=env)
    assert rc == 0, out


def test_a_folder_without_commits_is_refused_for_the_private_history(tmp_path):
    env = home_env(make_home(tmp_path))
    root = tmp_path / "larder"
    root.mkdir()
    git(root, "init", "-q", env=env)
    write(root, "app/main.py", "x = 1\n")
    rc, out = scaffold(root, ANSWERS, env=env)
    assert rc == 1 and "REFUSED" in out and "no commits" in out, out
    assert not (root / "public").exists()
