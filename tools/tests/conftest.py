"""The tools' tests, each on a throwaway git repository made by pytest, with invented files and known answers.

Run from the tools' folder: pytest
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

if shutil.which("git") is None:  # every tool reads the tracked tree through git
    pytest.skip("git is not installed", allow_module_level=True)

ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="A",
           GIT_AUTHOR_EMAIL="a@example.com", GIT_COMMITTER_NAME="A", GIT_COMMITTER_EMAIL="a@example.com")


class Repo:
    """A git repository in a temporary folder; `write` takes a mapping of paths to text."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q")

    def write(self, files):
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return self

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def git(self, *args, when="2026-03-01T10:00:00+00:00"):
        env = dict(ENV, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
        p = subprocess.run(["git", *args], cwd=self.root, env=env, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        return p.stdout

    def stage(self):
        self.git("add", "-A")
        return self

    def commit(self, message="a commit"):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def nest(self, folder, files):
        """A repository nested in this one at `folder`, declared in .gitmodules as `git submodule add` leaves it,
        with its files committed; returns it."""
        inner = Repo(self.root / folder)
        inner.write(files).commit("the public side")
        (self.root / ".gitmodules").write_text(f'[submodule "{folder}"]\n\tpath = {folder}\n\turl = ../{folder}.git\n')
        return inner


@pytest.fixture
def repo(tmp_path):
    return Repo(tmp_path / "project")


def run_tool(module, *args, cwd):
    """The tool as a script from the kit, the way a hook calls it: (exit code, stdout, stderr)."""
    p = subprocess.run([sys.executable, str(SRC / f"{module}.py"), *args], cwd=cwd, capture_output=True, text=True,
                       env=ENV)
    return p.returncode, p.stdout, p.stderr
