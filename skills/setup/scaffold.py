#!/usr/bin/env python3
"""Install Airone Giallo's tree, with the optional tools a project chose, into that project's workspace.

    python3 scaffold.py --answers ANSWERS.json [--target DIR] [--dry-run] [--force]
    python3 scaffold.py --name N --purpose P --mode conductor [more flags] [--target DIR] ...

The `setup` skill asks the questions and writes the answers; this script does the mechanics. Answers come from a
JSON file, from flags, or both; a flag overrides the file. `--help` lists every answer; DEFAULTS below holds the
defaults.

The documents form a ladder (`doc-discipline` §1): 1 `docs/`, 2 `graph.yml`, 3 `plan/`, 4 `ai-docs/`, 5 the agent
layer. The answer `cut` names the last public rung, and the form follows from it: `all` is one public repository,
`none` one private repository, anything else two, the private workspace (the target) holding the public repository
as a submodule folder. In the two-repository form the public rungs are written inside that folder, which the owner
adds with `git submodule add` before the run; the script checks that it is a git work tree of its own and never runs
`git submodule` itself. The archive is not a rung: each repository has its own, `archive/` at its top, on that
repository's side, so a document archived stays where it was public or private.

What it writes: at the workspace root the agent layer (AGENTS.md, CLAUDE.md, RATIONALE.md, local-machine.md, which is
git-ignored) and the `.gitignore` (an allowlist in the two-repository form, a few appended lines otherwise); at the
top of each repository `.ignore` with the line `archive/`, `archive/README.md` and the archive's log `archive/LOG.md`;
on each rung's side `ai-docs/` with its five places (the status file and the handoff when chosen), a README in `plan/`
and in `docs/` only when the folder is new, `docs/glossary.md` and `docs/invariants.md` when absent, and `graph.yml`
through `specgraph init`; outside the ladder `human-docs/README.md` and the `sources/README.md` manifest, each on its chosen
side; with `agent_layer: both`, a contributors' AGENTS.md and CLAUDE.md in the public folder. It copies no script into
the project: the checks are Airone Giallo's installed commands.

The rule it exists to obey: never report success for a step it did not perform. Every step is reported as done,
kept, skipped or failed, and the exit code follows the report: 0 when every step was done or kept, 1 when any was
refused, skipped or failed, 2 when the answers are invalid. A dry run says first that nothing has been written, then
gives each step the action the real run would take (create, replace, append or keep); it exits 0 unless the real run
would be refused.
Before writing anything it checks every target: an existing file stops the whole run unless --force, so a refusal
never leaves half an install. With --force the instruction files are replaced, but a record (the status file, the
closed file, the handoff, the archive's log, RATIONALE.md, the graph file, the folders' READMEs) is kept as it is,
since replacing it with an empty one would delete the project's history.

Standard library only; the graph step runs specgraph in a child process, its command on PATH or else its module.
"""

import argparse
import datetime
import errno
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
REPO = HERE.parent.parent
# The status file, the closed file and the archive's log are written as they are, their dates stamped, not rendered.
STATUS_TEMPLATES = TEMPLATES / "tree" / "ai-docs"
ARCHIVE_TEMPLATES = TEMPLATES / "tree" / "archive"
HANDOFF_TEMPLATE = REPO / "skills" / "handoff" / "references" / "handoff-template.md"

MODES = ("conductor", "four-hands")
# The ladder, bottom up: rung n is RUNGS[n - 1]. A cut names the last public rung; CUTS[i] makes rungs 1..i public.
# The archive is not a rung: each repository has its own at its top, on that repository's side.
RUNGS = ("docs", "graph", "plan", "ai-docs", "agent")
CUTS = ("none", "docs", "graph", "plan", "ai-docs", "all")
RUNG_NAMES = {"docs": "the system documents", "graph": "the graph", "plan": "the plan", "ai-docs": "the AI documents"}
ARCHIVE = "archive"
SIDES = ("private", "public")
LAYERS = ("private", "public", "both")
# Names the workspace root uses for itself, so the public folder cannot take one of them.
ROOT_NAMES = {"ai-docs", "archive", "human-docs", "sources", "docs", "plan", "graph.yml", ".claude", ".git",
              "AGENTS.md", "CLAUDE.md", "RATIONALE.md", "local-machine.md", ".ignore", ".gitignore", ".gitmodules"}
GRAPHS = ("none", "lite", "full")
# The files an agent tool loads as a folder's instructions (Claude Code: CLAUDE.md and .claude/CLAUDE.md; others:
# AGENTS.md). Those the owner's repository already holds are backed up into the workspace's archive under a name no
# tool loads, then replaced by the setup's own or removed.
OLD_INSTRUCTIONS = ("AGENTS.md", "CLAUDE.md", ".claude/CLAUDE.md")
# The agent tool's own files, part of the agent layer: in the two-repository form they move from the public folder to
# the workspace's root, where sessions open and Claude Code reads them. A `.claude/CLAUDE.md` is the old-file step's.
AGENT_FILES = (".claude", ".mcp.json")
OUTWARD = ("gated", "free")
# The status checker's own grammar for a family code; a code it would reject is refused here, before writing.
FAMILY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,4}(?:-[A-Z][A-Z0-9]{1,4})?$")
# What the written file shows where the owner has not answered yet; `grep -n 'to fill'` lists what is left. Square
# brackets, not angle ones: `<to fill: x>` is a valid HTML tag to a Markdown renderer, which would hide it.
SLOT = "[to fill: {}]"
SLOT_MARK = SLOT.split("{")[0]

DEFAULTS = {
    "invariants": [], "cut": "plan", "human_docs": "private", "sources": "private", "agent_layer": "",
    "public_dir": "", "graph": "none", "status": True, "families": {}, "handoff": True,
    "stage": "stage-1", "outward": "gated", "attribution": "", "reserved": [], "opinionated": False,
    "claude_code_version": "", "model": "", "spec": "", "plan": "", "glossary": "", "findings": "",
    "owner_notes": "", "frozen": [], "copies": [], "checks": "", "prune_after": "", "machine": {},
    "move_from": "", "carry": [],
    # The history's direction (B2), and with `private` the project's own paths' sides, the owner's markers and the
    # public commits' identity. `markers` is None until answered: an empty list is an answer, its absence is not.
    "history": "", "sides": {}, "markers": None, "public_author": "", "old_email_ok": False,
}
HISTORIES = ("private", "publish")
SIDE_WORDS = ("public", "private", "local")
AUTHOR_RE = re.compile(r"^[^<>]+ <[^<>@\s]+@[^<>\s]+>$")
# Where the tools sit in this checkout: the private direction's gate is the `check-public` command's own code.
TOOLS = REPO / "tools" / "src"
PRE_PUSH_TEMPLATE = TEMPLATES / "pre-push"
FIRST_MESSAGE = "First public state"
REQUIRED = ("name", "purpose", "mode")
MACHINE_KEYS = ("resources", "load", "limits", "timings")


class AnswerError(ValueError):
    """An answer that is missing, malformed or contradicts another."""


# ---------------------------------------------------------------- the template syntax

STANDALONE_RE = re.compile(r"^[ \t]*(\{\{[#^/]\w+\}\})[ \t]*\n", re.M)
SECTION_RE = re.compile(r"\{\{([#^])(\w+)\}\}(.*?)\{\{/\2\}\}", re.S)
VALUE_RE = re.compile(r"\{\{(\w+)\}\}")


def render(text, ctx):
    """Render the template subset: {{name}} is a value, {{#name}}…{{/name}} keeps its body when the value is
    true (a non-empty string or list, or True), {{^name}}…{{/name}} when it is false. A tag alone on its line takes
    the line with it. Sections of the same name do not nest. A name the context lacks is an error, never an empty
    string, so a template and its answers cannot drift apart unnoticed."""
    text = STANDALONE_RE.sub(r"\1", text)

    def section(m):
        kind, name, body = m.group(1), m.group(2), m.group(3)
        if name not in ctx:
            raise KeyError(f"template section '{name}' has no answer")
        keep = bool(ctx[name]) if kind == "#" else not ctx[name]
        return body if keep else ""

    while True:
        new = SECTION_RE.sub(section, text)
        if new == text:
            break
        text = new

    def value(m):
        name = m.group(1)
        if name not in ctx:
            raise KeyError(f"template slot '{name}' has no answer")
        v = ctx[name]
        return ", ".join(v) if isinstance(v, list) else str(v)

    text = VALUE_RE.sub(value, text)
    if "{{" in text:
        raise KeyError("an unmatched template tag is left: " + text[text.index("{{"):][:40])
    return text


WIDTH = 120  # Airone Giallo's own line length for Markdown


def rewrap(text, width=WIDTH):
    """Refill paragraphs and list items to the line length, after rendering: an answer's length must not decide how
    long a line is, or a line count of the written file would measure the answers instead of the rules. Headings,
    table rows and fenced blocks are left as they are."""
    out, block, fence = [], [], None

    def flush():
        if block:
            bullet = block[0].startswith("- ")
            joined = " ".join(ln.strip() for ln in block)
            out.extend(textwrap.wrap(joined, width, subsequent_indent="  " if bullet else "",
                                     break_long_words=False, break_on_hyphens=False))
            block.clear()

    for line in text.split("\n"):
        stripped = line.lstrip()
        if fence:
            out.append(line)
            if stripped.strip() == fence:
                fence = None
            continue
        if stripped.startswith("```"):
            flush()
            fence = stripped[:len(stripped) - len(stripped.lstrip("`"))]
            out.append(line)
        elif not stripped or stripped.startswith(("#", "|")):
            flush()
            out.append(line)
        elif line.startswith("- "):
            flush()
            block.append(line)
        else:
            block.append(line)
    flush()
    return "\n".join(out)


# ---------------------------------------------------------------- answers

def load_answers(args):
    answers = dict(DEFAULTS)
    if args.answers:
        try:
            given = json.loads(Path(args.answers).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as ex:
            raise AnswerError(f"cannot read the answers file {args.answers}: {ex}") from ex
        if not isinstance(given, dict):
            raise AnswerError("the answers file must hold one JSON object")
        unknown = set(given) - set(DEFAULTS) - set(REQUIRED)
        if unknown:
            raise AnswerError("unknown answer(s): " + ", ".join(sorted(unknown)))
        answers.update(given)
    for key in list(DEFAULTS) + list(REQUIRED):
        flag = getattr(args, key, None)
        if flag is not None and key != "machine":
            answers[key] = flag
    if args.side:
        sides = {}
        for item in args.side:
            path, _, word = item.rpartition("=")
            sides[path.strip()] = word.strip()
        answers["sides"] = sides
    if args.marker:
        answers["markers"] = list(args.marker)
    if args.family:
        fams = {}
        for item in args.family:
            code, _, what = item.partition("=")
            fams[code.strip()] = what.strip()
        answers["families"] = fams
    if not isinstance(answers.get("machine") or {}, dict):
        raise AnswerError("'machine' must map resources, load, limits and timings to text")
    machine = dict(answers.get("machine") or {})
    for k in MACHINE_KEYS:
        v = getattr(args, f"machine_{k}", None)
        if v is not None:
            machine[k] = v
    answers["machine"] = machine
    validate(answers)
    return answers


def validate(a):
    for key in REQUIRED:
        if not isinstance(a.get(key), str) or not a[key].strip():
            raise AnswerError(f"'{key}' is required, as text")
    for key, allowed in (("mode", MODES), ("cut", CUTS), ("human_docs", SIDES), ("sources", SIDES),
                         ("agent_layer", ("",) + LAYERS), ("graph", GRAPHS), ("outward", OUTWARD)):
        if a[key] not in allowed:
            raise AnswerError(f"'{key}' is {a[key]!r}; it must be one of {', '.join(allowed)}")
    if a["attribution"] and a["outward"] != "free":
        raise AnswerError("an attribution trailer is written only when outward acts are free")
    for key in ("status", "handoff", "opinionated"):
        if not isinstance(a[key], bool):
            raise AnswerError(f"'{key}' must be true or false")
    for key in ("invariants", "reserved", "frozen", "copies", "carry"):
        if not isinstance(a[key], list) or not all(isinstance(x, str) for x in a[key]):
            raise AnswerError(f"'{key}' must be a list of strings")
    if not all(x.strip() for x in a["invariants"]):
        raise AnswerError("each invariant is a paragraph of text; a blank one would hide that none is recorded")
    if not isinstance(a["families"], dict):
        raise AnswerError("'families' must map a code to what it covers")
    if a["status"]:
        if not a["families"]:
            raise AnswerError("the status file needs at least one family (a code and what it covers)")
        for code, what in a["families"].items():
            if not FAMILY_RE.match(code):
                raise AnswerError(f"family code {code!r}: 2 to 5 capitals or digits starting with a capital, "
                                  "or two such codes joined by a hyphen")
            if not str(what).strip():
                raise AnswerError(f"family {code} needs a line saying what it covers")
    unknown = set(a["machine"]) - set(MACHINE_KEYS)
    if unknown:
        raise AnswerError("unknown machine answer(s): " + ", ".join(sorted(unknown)))
    if not isinstance(a["move_from"], str):
        raise AnswerError("'move_from' is the path of the owner's folder before it moves into the workspace")
    if not re.match(r"^[A-Za-z0-9._-]+$", a["stage"]):
        raise AnswerError("'stage' names a file: letters, digits, dot, dash or underscore")
    validate_history(a)
    validate_sides(a)


def validate_history(a):
    """The history's direction and, with `private`, what it needs; an answer of the private history given without it
    is refused, never silently dropped."""
    if a["history"] not in ("",) + HISTORIES:
        raise AnswerError(f"'history' is {a['history']!r}; it must be one of {', '.join(HISTORIES)}")
    if a["history"] != "private":
        for key, empty in (("sides", {}), ("markers", None), ("public_author", ""), ("old_email_ok", False)):
            if a[key] != empty:
                raise AnswerError(f"'{key}' belongs to a history that stays private (history: private)")
        return
    if a["move_from"]:
        raise AnswerError("'move_from' moves the folder into a new workspace, which is the publish direction; with "
                          "history private the folder stays where it is and the public repository is born inside it")
    if a["cut"] == "all":
        raise AnswerError("history private needs two repositories: with cut 'all' everything is public, and there is "
                          "no private side to keep the history")
    sides = a["sides"]
    if not isinstance(sides, dict) or not sides:
        raise AnswerError("'sides' is required when the history stays private: each of the project's own paths and "
                          "its side, public, private or local")
    for path, word in sides.items():
        if not isinstance(word, str) or (word not in SIDE_WORDS and not re.match(r"^public as \S", word)):
            raise AnswerError(f"'sides': {path} is {word!r}; a side is one of {', '.join(SIDE_WORDS)}, or `public as "
                              "<the public name>`")
        parts = Path(path).parts
        if not isinstance(path, str) or not path or path.startswith("/") or ".." in parts:
            raise AnswerError(f"'sides': {path!r} is not a path from the project's root")
        if path in ROOT_OWN and word.startswith("public"):
            raise AnswerError(f"'sides': {path} is the private repository's own and never moves; to give the public "
                              f"repository one, publish a file of the project's under that name, such as "
                              f"\"public-root{path}\": \"public as {path}\"")
    if not any(w.startswith("public") for w in sides.values()):
        raise AnswerError("'sides': no path is public, so the public repository would be empty")
    try:
        sides_of(a)
    except check_public().Usage as ex:
        raise AnswerError(f"'sides': {ex}") from None
    if a["agent_layer"] == "both":
        raise AnswerError("'agent_layer: both' writes a contributors' instruction file into the public folder, and the "
                          "gate refuses every instruction file there when the history stays private")
    markers = a["markers"]
    if markers is None:
        raise AnswerError("'markers' is required when the history stays private: the owner's words that must never be "
                          "published; [] gives none, and the gate says so")
    if not isinstance(markers, list) or not all(isinstance(m, str) and m.strip() for m in markers):
        raise AnswerError("'markers' must be a list of words, each not blank")
    broken = [m for m in markers if "\n" in m or "\r" in m]
    if broken:
        raise AnswerError("'markers': a marker is one line of the markers file, so it holds no line break: "
                          + ", ".join(repr(m) for m in broken))
    try:
        check_public().markers_from(markers, "'markers'")  # the one reader the gates use, its refusals included
    except check_public().Usage as ex:
        raise AnswerError(str(ex)) from None
    if not isinstance(a["public_author"], str) or not AUTHOR_RE.match(a["public_author"]):
        raise AnswerError("'public_author' is required when the history stays private, as `Name <email>`: the identity "
                          "of the public commits")
    if not isinstance(a["old_email_ok"], bool):
        raise AnswerError("'old_email_ok' must be true or false")


def form_of(cut):
    return "one-public" if cut == "all" else "one-private" if cut == "none" else "two"


def slug(name):
    return re.sub(r"[^a-z0-9._-]+", "-", name.strip().lower()).strip("-.")


def validate_sides(a):
    """The side choices against the form the cut gives; an answer the form makes meaningless is refused, never
    silently dropped. Fills the derived values: the agent layer's side and the public folder's name."""
    form = form_of(a["cut"])
    if form == "one-private":
        for key in ("human_docs", "sources"):
            if a[key] == "public":
                raise AnswerError(f"cut 'none' keeps everything private; '{key}' cannot be public in it")
    layer = a["agent_layer"]
    if layer == "both" and form != "two":
        raise AnswerError("'agent_layer: both' writes a contributors' file into the public folder of the "
                          f"two-repository form; cut '{a['cut']}' gives one repository")
    if layer == "public" and form != "one-public":
        raise AnswerError("the agent layer cites every rung, the private ones too, so it is public only with cut "
                          "'all'; for a public contributors' file beside it, answer 'both'")
    if layer == "private" and form == "one-public":
        raise AnswerError("with cut 'all' the one repository is public, and the agent layer in it too")
    a["agent_layer"] = layer or ("public" if form == "one-public" else "private")
    # With a private history the two repositories come from the direction, not the cut: even with cut 'none' the
    # public repository is born inside the owner's folder, holding only the project's own public paths.
    if form != "two" and a["history"] != "private":
        for key in ("public_dir", "move_from"):
            if a[key]:
                raise AnswerError(f"'{key}' belongs to the two-repository form; cut '{a['cut']}' gives one repository")
        return
    # The owner's folder moves into the workspace whole and keeps its name, unless the owner names the folder.
    public = a["public_dir"] or (Path(a["move_from"]).name if a["move_from"] else slug(a["name"]))
    if not public:
        raise AnswerError("the name gives no folder name; answer 'public_dir', the public repository's folder")
    if not re.match(r"^[A-Za-z0-9._-]+$", public) or public in (".", "..") or public in ROOT_NAMES:
        raise AnswerError(f"'public_dir' {public!r}: one folder name, not one the workspace root uses itself")
    a["public_dir"] = public


@dataclass
class Layout:
    """Where each rung and each element outside the ladder goes, from the workspace root."""
    cut: str
    form: str
    public_dir: str
    agent_layer: str
    nest: bool = False       # the history stays private: the public repository is born inside the owner's folder

    @classmethod
    def of(cls, a):
        return cls(a["cut"], form_of(a["cut"]), a["public_dir"], a["agent_layer"], a["history"] == "private")

    @property
    def two(self):
        """Whether there are two repositories: by the cut, or by a private history even with cut 'none'."""
        return self.form == "two" or self.nest

    @property
    def owner_repo(self):
        """Where the owner's repository is, from the workspace root: the public folder in today's direction, the root
        itself when the history stays private."""
        return f"{self.public_dir}/" if self.form == "two" and not self.nest else ""

    def public(self, rung):
        return RUNGS.index(rung) + 1 <= CUTS.index(self.cut)

    def _in(self, public, rel):
        return f"{self.public_dir}/{rel}" if self.form == "two" and public else rel

    def at(self, rung, rel):
        """The path of a file or folder of a rung; the agent layer is always at the workspace root."""
        return self._in(rung != "agent" and self.public(rung), rel)

    def outside(self, side, rel):
        return self._in(side == "public", rel)

    @property
    def archives(self):
        """Each repository's archive, from the workspace root: the workspace's own first, then the public one."""
        return [ARCHIVE] + ([f"{self.public_dir}/{ARCHIVE}"] if self.form == "two" else [])

    def local_only(self, side):
        """A private element in the one public repository stays on this device, git-ignored."""
        return self.form == "one-public" and side == "private"


def code(path):
    return f"`{path}`"


def sides_in_words(a, lay):
    """The cut in words, for the ladder rule of AGENTS.md: which places are public, which private."""
    outside = (("human_docs", "human-docs"), ("sources", "sources"))
    own = (f"; the project's own paths are on the side `{PUBLIC_PATHS_FILE}` gives each, the public ones in the "
           f"public repository `{lay.public_dir}/`, which the history never reached") if lay.nest else ""
    if lay.form == "one-private":
        return "everything the setup writes is private, and the ladder still orders the citations" + own \
            if lay.nest else "everything is private, and the ladder still orders the citations"
    if lay.form == "one-public":
        local = ["`local-machine.md`"] + [f"`{rel}/`" for key, rel in outside if lay.local_only(a[key])]
        return ("everything is public, and the ladder still orders the citations; "
                f"{join(local)} {'stays' if len(local) == 1 else 'stay'} on this device, git-ignored")
    names = {"docs": "docs/", "graph": "graph.yml", "plan": "plan/", "ai-docs": "ai-docs/"}
    rungs = [r for r in names if r != "graph" or a["graph"] != "none"]
    public = [f"`{lay.at(r, names[r])}`" for r in rungs if lay.public(r)]
    private = [f"`{names[r]}`" for r in rungs if not lay.public(r)] + ["the agent layer"]
    elements = join([f"`{lay.outside(a[key], rel)}/` is {a[key]}" for key, rel in outside])
    words = (f"the public side ends at {RUNG_NAMES[lay.cut]}: {join(public)} {'is' if len(public) == 1 else 'are'} "
             f"public, in the public repository `{lay.public_dir}/`; {join(private)} "
             f"{'is' if len(private) == 1 else 'are'} private, at the workspace "
             f"root; outside the ladder, {elements}, and each repository's `{ARCHIVE}/` is on its repository's side")
    if lay.agent_layer == "both":
        words += f"; the contributors' `{lay.public_dir}/AGENTS.md` cites only the public rungs"
    return words + own


def join(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def context(a, lay, disk):
    """The values the templates read, derived from the answers and the layout. What is not answered shows as a
    visible slot."""
    ai = lay.at("ai-docs", "ai-docs")
    status_file, closed_file = f"{ai}/status.md", f"{ai}/closed.md"
    handoff_state = f"{ai}/handoff/current.md"
    graph_file = lay.at("graph", "graph.yml") if a["graph"] != "none" else ""
    docs, plan_dir = lay.at("docs", "docs"), lay.at("plan", "plan")
    glossary_file = f"{docs}/glossary.md"
    invariants_file = f"{docs}/invariants.md"
    # Without an answer the glossary is the tree's own, written when absent; an answered one lives elsewhere.
    has_glossary = not a["glossary"] or disk(glossary_file).is_file()

    families = []
    if graph_file:
        families.append(f"the statement families declared in `{graph_file}`'s meta, allocated by `{graph_file}`")
    if a["status"]:
        codes = ", ".join(code(c) for c in a["families"])
        families.append(f"{codes} for work items, allocated by `{status_file}` (its checker prints the next free ID)")

    # Each repository's archive is checked from the workspace root: the checker reads `archive` from where it runs,
    # so the workspace's own needs no flag and the public repository's is named.
    archive_checks = ["check-archive"] + [f"check-archive --archive {d}" for d in lay.archives[1:]]
    lint = ""
    if graph_file:
        lint = "`specgraph lint`" if graph_file == "graph.yml" else f"`specgraph lint --graph {graph_file}`"
    checks = [lint] if lint else []
    if a["status"]:
        graph_flag = f" --graph {graph_file}" if graph_file else ""
        checks.append(f"`check-status {status_file} {closed_file}{graph_flag}`")
    checks += [code(c) for c in archive_checks]
    # The documents' checks: the links walk the public folder from the workspace root and hold both sides to the cut;
    # the frontmatter is read in the repository whose commit is being made.
    if lay.two:
        checks.append(f"`check-links --public {lay.public_dir} --cut {lay.cut}`")
        checks.append("`check-frontmatter`, in the repository being committed")
    else:
        checks.append(f"`check-links --cut {lay.cut}`")
        checks.append("`check-frontmatter`")
    # The project's own checks beside Airone Giallo's, or a visible slot until they are known.
    own_checks = a["checks"] or SLOT.format("the project's own test and lint commands")
    checks.append(own_checks)

    if a["handoff"]:
        opening = code(handoff_state)
    elif a["status"]:
        opening = f"`git log` since the last session and `{status_file}`"
    else:
        opening = "`git log` since the last session"

    # The contributors' file sits in the public folder and names paths from there, public rungs only.
    def local(path):
        return path[len(lay.public_dir) + 1:] if lay.form == "two" else path
    c_checks = []
    if graph_file and lay.public("graph"):
        c_checks.append("`specgraph lint`")
    if a["status"] and lay.public("ai-docs"):
        graph_flag = f" --graph {local(graph_file)}" if graph_file else ""
        c_checks.append(f"`check-status {local(status_file)} {local(closed_file)}{graph_flag}`")
    # The public repository has an archive of its own, read from its root; and alone, everything in it is public, so
    # a link out of it is dead and no cut is needed.
    c_checks += ["`check-archive`", "`check-links`", "`check-frontmatter`"]
    c_checks.append(own_checks)

    human_docs = lay.outside(a["human_docs"], "human-docs") + "/"
    m = a["machine"]
    return {
        "name": a["name"].strip(),
        "purpose": a["purpose"].strip().rstrip("."),
        # Paragraphs carried over as written from the project's existing instruction file on the owner's yes; without
        # any, the invariants file says that none is recorded yet, which is a fact and not a slot left unanswered.
        "invariants": "\n\n".join(x.strip() for x in a["invariants"]),
        "invariants_file": invariants_file,
        # A project's own invariants file is kept as it is, and then states what it states.
        "has_invariants": bool(a["invariants"]) or disk(invariants_file).is_file(),
        # The old instruction files the owner's repository holds now, each backed up by the run.
        "old_files": [n for n in OLD_INSTRUCTIONS
                      if disk(lay.owner_repo + n).is_file()],
        "claude_code_version": a["claude_code_version"] or SLOT.format("version"),
        "model": a["model"] or SLOT.format("model"),
        "four_hands": a["mode"] == "four-hands", "conductor": a["mode"] == "conductor",
        "sides": sides_in_words(a, lay), "layer_public": lay.agent_layer == "public",
        "commands": join([code(c) for c, on in (("specgraph", graph_file), ("check-status", a["status"]),
                                                    ("check-archive", True), ("check-links", True),
                                                    ("check-frontmatter", True)) if on]),
        "two_repos": lay.two, "public_dir": lay.public_dir, "contributors": lay.agent_layer == "both",
        "status": a["status"], "handoff": a["handoff"], "graph_on": bool(graph_file), "graph_file": graph_file,
        "status_file": status_file, "closed_file": closed_file, "handoff_state": handoff_state,
        "spec": a["spec"] or code(f"{docs}/"), "plan": a["plan"] or code(f"{plan_dir}/"),
        "glossary": a["glossary"] or code(glossary_file),
        "findings": a["findings"] or code(f"{ai}/findings/"),
        "design_dir": f"{ai}/design/", "guides_dir": f"{ai}/guides/",
        "archive_dirs": join([code(f"{d}/") for d in lay.archives]),
        "human_docs_dir": human_docs,
        "sources_manifest": lay.outside(a["sources"], "sources") + "/README.md",
        "families": "; ".join(families), "open": opening, "checks": "; ".join(checks),
        "reserved": a["reserved"], "owner_notes": a["owner_notes"] or code(human_docs),
        "gated": a["outward"] == "gated", "free": a["outward"] == "free", "attribution": a["attribution"],
        "frozen": [code(f"{d}/") for d in lay.archives] + [code(f) for f in a["frozen"]],
        "copies": [code(c) for c in a["copies"]],
        "prune_after": a["prune_after"] or SLOT.format("a period"),
        "machine_resources": m.get("resources") or SLOT.format("cores, memory, disk, accelerators"),
        "machine_load": m.get("load") or SLOT.format("other sessions, agents, services, scheduled jobs"),
        "machine_limits": m.get("limits") or SLOT.format("the longest run and the most parallel jobs allowed"),
        "machine_timings": m.get("timings") or SLOT.format("yes, or no and why"),
        "c_docs": local(docs) + "/", "c_glossary": local(glossary_file) if has_glossary else "",
        "c_graph": local(graph_file) if graph_file and lay.public("graph") else "",
        "c_plan": local(plan_dir) + "/" if lay.public("plan") else "",
        "c_checks": "; ".join(c_checks),
    }


# ---------------------------------------------------------------- the steps

@dataclass
class Step:
    path: str                # relative to the target, the workspace root
    what: str                # one line for the report
    make: object = None      # a function returning the file's text
    record: bool = False     # a record is never replaced, even with --force
    action: object = None    # for a step that is not a plain write (the graph)
    lines: tuple = ()        # for an append step: groups of lines, each appended whole when any line is missing
    kept: str = ""           # for a step decided at planning: why it is not done
    backup: str = ""         # for an old instruction file: its backup's path, written and checked before the step
    remove: bool = False     # for an old instruction file the setup does not replace: removed once backed up
    move_to: str = ""        # for the agent tool's files of the public folder: their place at the workspace's root


def stamp_frontmatter(text, now):
    """Fill the date slots of the leading frontmatter only; the same slots further down are examples of an entry."""
    if not text.startswith("---\n"):
        return text
    end = text.index("\n---\n", 4)
    head = text[:end]
    for slot in ("<YYYY-MM-DDTHH:MM:SS+00:00>", "[to fill: YYYY-MM-DDTHH:MM:SS+00:00]"):
        head = head.replace(slot, now.strftime("%Y-%m-%dT%H:%M:%S+00:00"))
    for slot in ("<YYYY-MM-DD>", "[to fill: YYYY-MM-DD]"):
        head = head.replace(slot, now.strftime("%Y-%m-%d"))
    return head + text[end:]


def replace_once(text, old, new, source):
    """Replace a passage the template is known to hold; a template that changed under the script is a failure."""
    if text.count(old) != 1:
        raise RuntimeError(f"{source}: expected the passage {old[:50]!r} once, found it {text.count(old)} times")
    return text.replace(old, new)


def items(*lines):
    """List items, or a paragraph, each filled to the line length, a continuation indented under its text."""
    return "\n".join("\n".join(textwrap.wrap(ln, WIDTH, subsequent_indent=" " * len(re.match(r"(- |\d+\. )?", ln)[0]),
                                             break_long_words=False, break_on_hyphens=False)) for ln in lines)


def fill_sections(block, bodies, source):
    """Give each `## ` section of a template block the body written for its heading. The template keeps the shape
    (frontmatter, banner, headings, their order); a heading with no body, or a body whose heading is gone, is a
    template that changed under the script."""
    parts = re.split(r"^## (.+)\n", block, flags=re.M)
    headings = parts[1::2]
    if headings != list(bodies):
        raise RuntimeError(f"{source}: expected the sections {list(bodies)}, found {headings}")
    return parts[0] + "".join(f"## {h}\n\n{bodies[h].strip()}\n\n" for h in headings).rstrip("\n") + "\n"


def first_state(block, a, lay, ctx, now, log_name, slotted):
    """The handoff's state as the setup leaves it: what the setup knows, and "none" where it knows there is nothing.
    It names no file of the agent layer: that layer is the rung above the handoff, and private when the cut makes
    the handoff public. The checks run after the script, so the state says they have not run, and the setup's agent
    writes their results in."""
    date = now.strftime("%Y-%m-%d")
    for old, new in (("[to fill: session]", "setup"), ("[to fill: date]", date),
                     ("[to fill: the state in one sentence]", "Airone Giallo's layout is installed, and no document "
                      "of the project's own has been moved into it yet"),
                     # The template points to the log's newest entry, right after every close; the setup's log has
                     # none yet.
                     ("[to fill: the log file, as a link],\n> newest entry.",
                      f"[{log_name}]({log_name}), no entry yet:\n> the first close writes the first.")):
        block = replace_once(block, old, new, HANDOFF_TEMPLATE)
    pieces = []
    if a["status"]:
        pieces.append(f"the status file `{ctx['status_file']}`, its families in its `status-meta` block")
    pieces.append(f"the handoff, this state and one log per stage, the first for the stage `{a['stage']}`")
    pieces.append(f"the specification graph `{ctx['graph_file']}`, {a['graph']} profile" if ctx["graph_file"]
                  else "no specification graph")
    if slotted:
        open_for_owner = f"the slots the setup left unanswered in {join(slotted)}"
        step = "Fill with the owner the slots the setup left unanswered, as §3 lists them."
        prompt = f"Fill with me the slots the setup left unanswered in {join(slotted)}."
    else:
        open_for_owner = "none"
        step = "Agree the first piece of work with the owner" + (
            f", and record it in `{ctx['status_file']}`." if a["status"] else ".")
        prompt = "Propose the first piece of work, from what the repository holds."
    if a["carry"]:
        # The archive is named as a category, never by a file in it, as a live document must; and the old file by its
        # name as text, since in backticks its name is the agent layer's own file, the rung above the handoff.
        old = join(ctx["old_files"]) or "it"
        step = (f"Finish carrying over the old instruction file from the backup of the old {old} in the archive, "
                f"each part to the place confirmed at setup, and delete each line here once its part is carried: "
                f"{'; '.join(a['carry'])}.")
        prompt = "Finish carrying over the old instruction file, as the handoff lists it."
    bodies = {
        "1. What is true now": items(
            f"- **The layout**: Airone Giallo's tree, written by its setup on {date}; no document of the project's "
            "own has been moved into it yet, which is a session's work with the owner, file by file.",
            "- **Checks**: not run when the setup wrote this file; the setup runs them next and writes their "
            "results here, each with its command.",
            "- **Progress**: none recorded yet."),
        "2. What was decided, and why": items(
            f"- **The cut**: `{lay.cut}`, so {describe(a, lay)}. *Why:* the owner's answer at setup.",
            f"- **The optional tools**: {'; '.join(pieces)}. *Why:* the owner's answers at setup."),
        "3. What is open": items(
            f"1. **For the owner**: {open_for_owner}.", "2. **Unexplained**: none.", "3. **Deferred**: none."),
        "4. What the next session does first": f"{items(step)}\n\nPrompt to paste:\n\n    {prompt}",
        "5. What must not be touched": items(
            f"- **Invariants**: as `{ctx['invariants_file']}` states them; no test is recorded yet as guarding one."
            if ctx["has_invariants"] else f"- **Invariants**: none recorded yet in `{ctx['invariants_file']}`.",
            "- **Frozen**: each repository's archive, and anything else the instruction file names frozen.",
            "- **Runs in flight**: none."),
        "6. Where the numbers come from": "None: this state quotes no figure.",
    }
    return fill_sections(block, bodies, HANDOFF_TEMPLATE)


def handoff_files(a, lay, ctx, now, slotted):
    """The handoff's first state, and its first log without the template's blank entry: each entry is written at a
    close, from the handoff skill's template. `slotted` names the files written with a slot left."""
    text = HANDOFF_TEMPLATE.read_text(encoding="utf-8")
    blocks = re.findall(r"^```markdown\n(.*?)^```$", text, re.M | re.S)
    if len(blocks) != 2:
        raise RuntimeError(f"{HANDOFF_TEMPLATE}: expected two ```markdown blocks, the state and the log; "
                           f"found {len(blocks)}")
    log_name = f"log-{a['stage']}.md"
    state = first_state(blocks[0], a, lay, ctx, now, log_name, slotted)
    log, entry, _ = blocks[1].replace("[to fill: stage]", a["stage"]).partition("\n## ")
    if not entry:
        raise RuntimeError(f"{HANDOFF_TEMPLATE}: expected the log's entry under a `## ` heading")
    return stamp_frontmatter(state, now), stamp_frontmatter(log, now), log_name


def status_files(a, ctx, now):
    status = STATUS_TEMPLATES.joinpath("status.md").read_text(encoding="utf-8")
    fams = "\n".join(f"  {c}: {w}" for c, w in a["families"].items())
    status = replace_once(status, "  <CODE>: <what the family covers: a repository, or an area of one>", fams,
                          "status.md template")
    status = replace_once(status, "check-status <this file> <the closed file>",
                          f"check-status {ctx['status_file']} {ctx['closed_file']}", "status.md template")
    closed = STATUS_TEMPLATES.joinpath("closed.md").read_text(encoding="utf-8")
    return stamp_frontmatter(status, now), stamp_frontmatter(closed, now)


def archive_log(now):
    return stamp_frontmatter(ARCHIVE_TEMPLATES.joinpath("LOG.md").read_text(encoding="utf-8"), now)


def specgraph_command():
    """How to run specgraph: its command on PATH first, else this interpreter's module, else None. A tool installer
    (uv tool, pipx) puts the command on PATH and keeps the module out of every other Python."""
    found = shutil.which("specgraph")
    if found:
        return [found]
    if importlib.util.find_spec("specgraph") is not None:
        return [sys.executable, "-m", "specgraph"]
    return None


def graph_action(profile, folder):
    def run(disk):
        command = specgraph_command()
        if not command:
            install = shlex.quote(str(REPO / "graph"))
            return ("SKIPPED", f"specgraph is neither a command on PATH nor importable from {sys.executable}; "
                    f"install the command with uv tool install {install} (pipx install takes the same argument), "
                    f"then run in {folder}: specgraph init --profile {profile}")
        where = disk(folder)
        proc = subprocess.run([*command, "init", "--profile", profile, "--graph", "graph.yml"],
                              cwd=where, capture_output=True, text=True)
        out = (proc.stdout + proc.stderr).strip()
        # Measure the artifact, not the command: the file must exist and carry its meta.
        graph = where / "graph.yml"
        if proc.returncode != 0 or not graph.is_file() or "meta:" not in graph.read_text(encoding="utf-8"):
            return ("FAILED", f"specgraph init exited {proc.returncode}: {out}")
        return ("DONE", f"{profile} profile, by specgraph init")
    return run


def template(rel, ctx, now):
    """A template rendered, its frontmatter dates stamped."""
    return stamp_frontmatter(render(TEMPLATES.joinpath(rel).read_text(encoding="utf-8"), ctx), now)


def body_rewrapped(text):
    """Refill a document's body to the line length and leave its frontmatter as it is: the body may hold paragraphs
    carried over from the project, whose line breaks were made for another width."""
    if not text.startswith("---\n"):
        return rewrap(text)
    end = text.index("\n---\n", 4) + len("\n---\n")
    return text[:end] + rewrap(text[end:])


def agent_files(lay, disk):
    """The agent tool's files the public folder holds, to move to the workspace's root: `.claude/` when it holds more
    than a `CLAUDE.md` (which the old-file step backs up and removes first), and `.mcp.json`."""
    if lay.form != "two" or lay.nest:
        return []
    found = []
    for name in AGENT_FILES:
        path = disk(f"{lay.public_dir}/{name}")
        if name == ".claude":
            if path.is_dir() and any(c.name != "CLAUDE.md" for c in path.iterdir()):
                found.append(name)
        elif path.is_file():
            found.append(name)
    return found


def allowlist(a, lay, moved=()):
    """The private workspace's .gitignore: everything ignored unless named, so nothing private is committed without
    being named first; the public folder is one entry, so only its gitlink is tracked."""
    names = {"docs": "docs/", "graph": "graph.yml", "plan": "plan/", "ai-docs": "ai-docs/"}
    private = [n for r, n in names.items() if not lay.public(r) and (r != "graph" or a["graph"] != "none")]
    private.append(f"{ARCHIVE}/")  # the workspace's own archive, always private
    lines = ["# Airone Giallo: the private workspace's allowlist. Everything is ignored unless re-included below,",
             "# so nothing private is committed without being named first; local-machine.md stays ignored.",
             "/*", "!/.gitignore", "!/.gitmodules", "!/.ignore", "!/AGENTS.md", "!/CLAUDE.md", "!/RATIONALE.md",
             *(("# the agent tool's folder, moved in from the public folder; settings.local.json stays personal",
                "!/.claude/", "/.claude/settings.local.json") if ".claude" in moved else
               ("# the project's skills, and nothing else of the agent tool's folder",
                "!/.claude/", "/.claude/*", "!/.claude/skills/")),
             *(("!/.mcp.json",) if ".mcp.json" in moved else ())]
    lines += [f"!/{n}" for n in private]
    if a["human_docs"] == "private":
        lines.append("!/human-docs/")
    if a["sources"] == "private":
        lines += ["# downloaded sources: the manifest is committed, the files are not",
                  "!/sources/", "/sources/*", "!/sources/README.md"]
    lines += ["# the public repository, a submodule: only its gitlink, the commit the private documents refer to",
              f"!/{lay.public_dir}"]
    return "\n".join(lines) + "\n"


def plan(a, lay, ctx, now, disk):
    agents = template("AGENTS.md", ctx, now)
    if a["opinionated"]:
        agents += render(TEMPLATES.joinpath("opinionated.md").read_text(encoding="utf-8"), ctx)
    agents = rewrap(agents)
    rationale = rewrap(template("RATIONALE.md", ctx, now))
    claude = TEMPLATES.joinpath("CLAUDE.md").read_text(encoding="utf-8")
    machine = template("local-machine.md", ctx, now)

    def tree(rel):
        text = template(f"tree/{rel}", ctx, now)
        return lambda: text

    steps = [
        Step("AGENTS.md", "the instruction file", lambda: agents),
        Step("CLAUDE.md", "one line, importing AGENTS.md", lambda: claude),
        Step("RATIONALE.md", "where each rule came from", lambda: rationale, record=True),
        Step("local-machine.md", "this device's resources and limits (git-ignored)", lambda: machine),
    ]
    # The .ignore of each repository sits at its top, beside its archive.
    steps += [Step(f"{d[:-len(ARCHIVE)]}.ignore", "the archive out of every search unless named",
                   lines=((f"{ARCHIVE}/",),)) for d in lay.archives]
    if lay.form == "two" and not lay.nest:
        text = allowlist(a, lay, agent_files(lay, disk))
        steps.append(Step(".gitignore", f"the allowlist; {lay.public_dir}/ tracked as its gitlink only",
                          lambda: text))
    else:
        groups = [("# Airone Giallo: the per-device machine file, never committed", "/local-machine.md")]
        for key, rel in (("sources", "sources"), ("human_docs", "human-docs")):
            if lay.local_only(a[key]):
                groups.append((f"# Airone Giallo: {rel}/ is private in a public repository, so it stays on this device",
                               f"/{rel}/"))
            elif key == "sources":
                groups.append(("# Airone Giallo: downloaded sources; the manifest is committed, the files are not",
                               "/sources/*", "!/sources/README.md"))
        steps.append(Step(".gitignore", "the machine file and the sources ignored", lines=tuple(groups)))
    contributors = rewrap(template("AGENTS.contributors.md", ctx, now)) if lay.agent_layer == "both" else ""
    if contributors:
        steps += [Step(f"{lay.public_dir}/AGENTS.md", "the contributors' instruction file, public rungs only",
                       lambda: contributors),
                  Step(f"{lay.public_dir}/CLAUDE.md", "one line, importing the contributors' AGENTS.md",
                       lambda: claude)]

    ai = lay.at("ai-docs", "ai-docs")
    steps.append(Step(f"{ai}/README.md", "the five places of the AI documents (rung 4)", tree("ai-docs/README.md"),
                      record=True))
    if a["status"]:
        status, closed = status_files(a, ctx, now)
        steps += [Step(ctx["status_file"], "the status file", lambda: status, record=True),
                  Step(ctx["closed_file"], "the closed file", lambda: closed, record=True)]
    if a["handoff"]:
        # The files written with a slot left, by what they are: the handoff names no path of the agent layer.
        slotted = [what for what, body in (("the instruction file", agents), ("the machine file", machine),
                                           ("the contributors' instruction file", contributors))
                   if SLOT_MARK in body]
        state, first_log, log_name = handoff_files(a, lay, ctx, now, slotted)
        steps += [Step(f"{ai}/handoff/current.md", "the handoff's state", lambda: state, record=True),
                  Step(f"{ai}/handoff/{log_name}", "the handoff's first log", lambda: first_log, record=True)]
    for place, what in (("design", "what was decided, and why"), ("findings", "what was observed"),
                        ("guides", "how a thing is done here")):
        steps.append(Step(f"{ai}/{place}/README.md", what, tree(f"ai-docs/{place}/README.md"), record=True))
    archive_log_text = archive_log(now)
    for d in lay.archives:
        steps += [Step(f"{d}/README.md", "this repository's archive: what it is", tree("archive/README.md"),
                       record=True),
                  Step(f"{d}/LOG.md", "the archive's log: changes to archived files, vocabulary conflicts",
                       lambda: archive_log_text, record=True)]

    for rung in ("docs", "graph", "plan"):
        if rung == "graph":
            if a["graph"] != "none":
                graph = ctx["graph_file"]
                steps.append(Step(graph, f"the graph file ({a['graph']} profile, rung 2)", record=True,
                                  action=graph_action(a["graph"], str(Path(graph).parent))))
            continue
        # An existing folder gets no index: its own layout is the project's. A new file beside its files changes
        # none of them, so the glossary is written into it when absent.
        folder = lay.at(rung, rung)
        if disk(folder).exists():
            steps.append(Step(f"{folder}/", "", kept="the folder exists; no index written into it"))
        else:
            steps.append(Step(f"{folder}/README.md", f"the index of {folder}/ (rung {RUNGS.index(rung) + 1})",
                              tree(f"{rung}/README.md"), record=True))
        if rung == "docs" and not a["glossary"]:
            glossary = f"{folder}/glossary.md"
            if disk(glossary).exists():
                steps.append(Step(glossary, "", kept="the glossary exists"))
            else:
                steps.append(Step(glossary, "the glossary", tree("docs/glossary.md"), record=True))
        if rung == "docs":
            invariants = ctx["invariants_file"]
            if disk(invariants).exists():
                steps.append(Step(invariants, "", kept="the project's own invariants file exists, loaded as it is"))
            else:
                # Its own name: the steps run after plan() returns, so a lambda reading a rebound `text` would
                # write this file's text into the allowlist.
                invariants_text = body_rewrapped(template("tree/docs/invariants.md", ctx, now))
                steps.append(Step(invariants, "the invariants, loaded into every session through AGENTS.md",
                                  lambda: invariants_text, record=True))

    for key, rel, what in (("human_docs", "human-docs", "the owner's notes, as written"),
                           ("sources", "sources", "the sources' manifest; the files are git-ignored")):
        side = "kept on this device" if lay.local_only(a[key]) else a[key]
        steps.append(Step(f"{lay.outside(a[key], rel)}/README.md", f"{what} ({side})", tree(f"{rel}/README.md"),
                          record=True))
    if lay.form == "two" and a["sources"] == "public":
        steps.append(Step(f"{lay.public_dir}/.gitignore", "the public sources' files ignored, the manifest kept",
                          lines=(("# Airone Giallo: downloaded sources; the manifest is committed, the files are not",
                                  "/sources/*", "!/sources/README.md"),)))
    # The owner's repository may hold its old instruction files: each is backed up, then replaced by the setup's own
    # file of that name or removed. The backup goes to the workspace's archive: an instruction file is the top rung.
    repo = lay.owner_repo
    written = {s.path: s for s in steps}
    for name in OLD_INSTRUCTIONS:
        old = repo + name
        if disk(old).is_file():
            backup = f"{ARCHIVE}/{backup_name(name)}"
            if old in written:
                written[old].backup = backup
            else:
                steps.append(Step(old, "once backed up; its parts are carried over after the run, as confirmed",
                                  remove=True, backup=backup))
    # The agent tool's files follow the agent layer to the workspace's root, after the old-file step has taken
    # `.claude/CLAUDE.md` out of the folder they leave.
    for name in agent_files(lay, disk):
        steps.append(Step(f"{lay.public_dir}/{name}" + ("/" if name == ".claude" else ""), "", move_to=name))
    # The workspace root first, then the public folder: the order the dry run is read in.
    return sorted(steps, key=lambda s: lay.form == "two" and s.path.startswith(lay.public_dir + "/"))


def backup_name(name):
    """The backup's file name: never the name a tool loads, so the archived copy instructs nobody."""
    stem = Path(name).stem
    return (f"dot-claude-{stem}" if name.startswith(".claude/") else stem) + "-before-setup.md"


def stamped(original, now):
    """The backup's bytes: the original's, with only what the archive requires added, an `archived:` stamp in a
    frontmatter block (inserted into the original's own block when it has one). Returns (bytes, where, what added)."""
    stamp = f"archived: {now.strftime('%Y-%m-%dT%H:%M:%S+00:00')}\n".encode()
    if original.startswith(b"---\n") and b"\n---\n" in original[3:]:
        added, at = stamp, 4
    else:
        added, at = b"---\n" + stamp + b"---\n", 0
    return original[:at] + added + original[at:], at, added


def write_backup(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def back_up(source, backup, now):
    """Write the backup and read it back: it must be the original's bytes plus the stamp, and nothing else."""
    original = source.read_bytes()
    data, at, added = stamped(original, now)
    write_backup(backup, data)
    back = backup.read_bytes()
    return back == data and back[:at] + back[at + len(added):] == original


def move_agent_file(source, dest):
    """Move one of the agent tool's files to the workspace's root: a rename, or across file systems a copy that is
    compared file by file before the original goes. (ok, why not)."""
    if (source / "CLAUDE.md").exists():
        return False, "its CLAUDE.md is still there, so the old-file step did not finish; not moved"
    try:
        os.rename(source, dest)
    except OSError as ex:
        if ex.errno != errno.EXDEV:
            return False, str(ex)
        if source.is_dir():
            shutil.copytree(source, dest, symlinks=True)
            pairs = [(f, dest / f.relative_to(source)) for f in source.rglob("*") if f.is_file()]
        else:
            shutil.copy2(source, dest)
            pairs = [(source, dest)]
        if not all(b.is_file() and a.read_bytes() == b.read_bytes() for a, b in pairs):
            return False, "the copy did not read back as the original; the original is left where it was"
        shutil.rmtree(source) if source.is_dir() else source.unlink()
    return dest.exists() and not source.exists(), "not moved"


def missing_groups(path, groups):
    """The groups of lines the file lacks; a group is appended whole, since a re-inclusion before its ignore line
    would be undone by it."""
    have = set(path.read_text(encoding="utf-8").splitlines()) if path.exists() else set()
    return [g for g in groups if any(ln not in have for ln in g if not ln.startswith("#"))]


def public_folder_problem(target, folder):
    """Why the public folder cannot take the public rungs, or None: it must be a git work tree of its own, declared as
    a submodule of the workspace."""
    add = (f"move the owner's folder in whole and register it in place first: mv <the folder> {folder}, then "
           f"git submodule add <its URL, or ./{folder} without one> {folder}")
    where = target / folder
    if not where.is_dir():
        return f"the public folder {folder}/ is not there; {add}"
    if shutil.which("git") is None:
        return f"git is not installed, so {folder}/ cannot be checked to be a repository of its own"
    proc = subprocess.run(["git", "-C", str(where), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    top = proc.stdout.strip()
    if proc.returncode != 0 or Path(top).resolve() != where.resolve():
        return (f"{folder}/ is not a git work tree of its own (its top level is {top or 'none'}); {add}")
    modules = target / ".gitmodules"
    declared = modules.exists() and any(
        ln.strip().startswith("path") and ln.split("=", 1)[1].strip() == folder
        for ln in modules.read_text(encoding="utf-8").splitlines() if "=" in ln)
    if not declared:
        return (f"{folder}/ is a repository of its own but not a submodule of this workspace (no `path = {folder}` in "
                f".gitmodules), so the workspace would not record which public commit its documents refer to; {add}")
    return None


# ---------------------------------------------------------------- running

def describe(a, lay):
    if lay.nest:
        kit = ("every file the setup writes private" if lay.form == "one-private" else
               f"the setup's own public side ending at {RUNG_NAMES[lay.cut]} (cut {lay.cut})")
        return (f"two repositories: this private repository, its history kept, and the public repository born inside "
                f"it in {lay.public_dir}/ from one gated commit, holding the paths {PUBLIC_PATHS_FILE} declares "
                f"public; {kit}, the agent layer {lay.agent_layer}")
    if lay.form == "one-public":
        return "one public repository: every rung public, the ladder still orders the citations"
    if lay.form == "one-private":
        return "one private repository: every rung private, the ladder still orders the citations"
    return (f"two repositories: this private workspace, and the public repository in {lay.public_dir}/; the public "
            f"side ends at {RUNG_NAMES[lay.cut]} (cut {lay.cut}), the agent layer {lay.agent_layer}")


def invariants_problem(a, ctx, disk):
    """Why the carried invariants cannot be written, or None: an existing invariants file is the project's own and is
    never replaced, so the paragraphs carried over would be lost without a word."""
    path = ctx["invariants_file"]
    if a["invariants"] and disk(path).exists():
        return (f"{path} exists and is never replaced, so the invariants carried over have no file to go into; add "
                "them to it with the owner and leave the answer 'invariants' empty")
    return None


def resolver(a, lay, target):
    """(disk, source). disk(path) is where a path of the plan is on disk now: before the move, the public folder is
    still the owner's folder at `move_from`, which is then `source`; once moved, or without a move, source is None."""
    source = None
    if lay.form == "two" and a["move_from"] and not (target / lay.public_dir).exists():
        source = Path(a["move_from"]).expanduser().resolve()
    prefix = lay.public_dir + "/"

    def disk(rel):
        if source is not None and (rel == lay.public_dir or rel.startswith(prefix)):
            return source if rel == lay.public_dir else source / rel[len(prefix):]
        return target / rel
    return disk, source


def move_problem(source):
    """Why the owner's folder cannot be moved in as the public side, or None: it must be a git work tree of its own."""
    if not source.is_dir():
        return f"the folder to move, {source}, is not there"
    if shutil.which("git") is None:
        return f"git is not installed, so {source} cannot be checked to be a repository of its own"
    proc = subprocess.run(["git", "-C", str(source), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if proc.returncode != 0 or Path(proc.stdout.strip()).resolve() != source:
        return f"{source} is not a git work tree of its own, so it cannot become the public repository"
    return None


def shown(path):
    """A path as the owner reads it: from the home folder when it is under it, absolute otherwise."""
    try:
        return "~/" + str(Path(path).relative_to(Path.home()))
    except ValueError:
        return str(path)


def grouped(paths):
    """New files by folder: the files at the repository's top, then each folder with the files in it."""
    top, folders = [], {}
    for rel in paths:
        head, _, rest = rel.partition("/")
        if rest:
            folders.setdefault(head, []).append(rest[:-3] if rest.endswith(".md") else rest)
        else:
            top.append(rel)
    lines = [top] if top else []
    if folders:
        lines.append([f"{f}/ ({', '.join(rs)})" for f, rs in folders.items()])
    return lines


def wrap_items(items, width):
    """Items joined by commas, a line broken only between two items, never inside one."""
    lines, line = [], ""
    for item in items:
        piece = item if not line else f"{line}, {item}"
        if line and len(piece) > width:
            lines.append(line + ",")
            line = item
        else:
            line = piece
    return lines + [line]


def print_report(rows, a, lay, target, dry_run, out):
    """The rows by repository, the owner's own first, each split into the files it already had and the new ones; the
    dry run groups the new files by folder, the real run lists every file."""
    public = lay.form == "two"
    prefix = lay.public_dir + "/"
    # The owner's repository is named where it is now; the move has its own line at the top.
    source = Path(a["move_from"]).expanduser().resolve() if a["move_from"] else None
    here = shown(source if source and not (target / lay.public_dir).exists() else target / lay.public_dir)
    here = f"{here} (public)"
    sections = [("public", f"Your repository: {here}"),
                ("root", f"The workspace: {shown(target)} (private{', new' if not target.exists() else ''})")] \
        if public else [("root", f"Your repository: {shown(target)}")]
    for key, title in sections:
        mine = [(st, path[len(prefix):] if key == "public" else path, detail, had)
                for st, path, detail, had in rows if (public and path.startswith(prefix)) == (key == "public")]
        print(f"\n{title}", file=out)
        have, new = [r for r in mine if r[3]], [r for r in mine if not r[3]]
        for label, part in (("Files you have", have), ("New files", new)):
            if not part:
                continue
            print(f"  {label}", file=out)
            if dry_run and label == "New files":
                for items in grouped([path for _, path, _, _ in part]):
                    print(f"    {'CREATE':<8} " + f"\n{' ' * 13}".join(wrap_items(items, WIDTH - 13)), file=out)
                continue
            width = max(len(path) for _, path, _, _ in part) + 1
            for st, path, detail, _ in part:
                print(f"    {st:<8} {path:<{width}} {detail}".rstrip(), file=out)
    # What the session carries over after the run is no file of either repository: a section of its own, last.
    if a["carry"]:
        print("\nCarried over after the run, as you confirmed", file=out)
        for line in a["carry"]:
            print(f"    {line}", file=out)


def run(a, target, dry_run, force, out=None):
    out = out or sys.stdout
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    lay = Layout.of(a)
    if lay.nest:
        return run_private(a, lay, target, dry_run, force, out)
    disk, source = resolver(a, lay, target)
    try:
        ctx = context(a, lay, disk)
        steps = plan(a, lay, ctx, now, disk)
    except (OSError, RuntimeError, KeyError) as ex:
        print(f"FAILED  cannot prepare the install: {ex}", file=out)
        return 1

    # The real run needs the public folder in place; the dry run may come before the move, which it then shows.
    problem = None
    if lay.form == "two":
        problem = move_problem(source) if source is not None else public_folder_problem(target, lay.public_dir)
    problem = problem or invariants_problem(a, ctx, disk)
    if problem and not dry_run:
        print(f"REFUSED  {problem}. Nothing was written.", file=out)
        return 1

    existing = [s for s in steps if not s.lines and not s.kept and not s.backup and not s.move_to
                and disk(s.path).exists()]
    if existing and not force:
        print("REFUSED  these files exist; nothing was written. Read them, keep what the owner wants, then rerun "
              "with --force (records are kept even then):", file=out)
        for s in existing:
            print(f"  {s.path}", file=out)
        return 1
    # The agent tool's files are never moved over the workspace's own: the two would have to be merged by hand.
    clash = [s for s in steps if s.move_to and (target / s.move_to).exists()]
    if clash:
        print("REFUSED  the workspace already has these, so the public folder's cannot be moved over them; nothing was "
              "written. Merge each pair by hand with the owner, then run again:", file=out)
        for s in clash:
            print(f"  {s.path} → {target / s.move_to}", file=out)
        return 1
    # A backup is never written over another: the earlier one may be the only copy of an original.
    taken = [s for s in steps if s.backup and disk(s.backup).exists()]
    if taken:
        print("REFUSED  a backup of that name exists, and a backup is never replaced; nothing was written:", file=out)
        for s in taken:
            print(f"  {s.backup}, the backup {s.path} would get", file=out)
        print("A second run of the setup on the same project is not handled. To run it again, undo the first with the "
              "owner (git stash -u or a checkout in each repository it wrote into), or change this install by hand.",
              file=out)
        return 1

    rows, problems = execute(steps, disk, target, lay, dry_run, now)
    return finish(a, lay, target, dry_run, source, problem, rows, problems, out)


def execute(steps, disk, target, lay, dry_run, now, track=None):
    """Run or, in a dry run, describe each step: (rows of status, path, detail, whether it existed; any problem).
    `track`, when given, is told of each write before it happens (the bytes it will leave, or None for a removal, or
    `unknown` when a command writes) and after it: the private direction records them so that `--undo` can reverse
    them, even when the run is stopped between a write and its record."""
    # The real run reports whether each step happened (DONE, KEPT, SKIPPED, FAILED); the dry run, which does nothing,
    # what each step would do (CREATE, REPLACE, APPEND, KEEP, and BACKUP and REMOVE for an old instruction file).
    kept = "KEEP" if dry_run else "KEPT"
    rows, problems = [], False

    def add(status, path, detail, had):
        rows.append((status, path, detail, had))

    def intend(path, data=None, unknown=False):
        if track:
            track.intend(str(path.relative_to(target)), data, unknown=unknown)

    def did(path):
        if track:
            track.did(str(path.relative_to(target)))

    for s in steps:
        dest = disk(s.path)
        had = dest.exists()
        if s.kept:
            add(kept, s.path, s.kept, True)
            continue
        if s.move_to:
            where = f"the workspace's root, {s.move_to}{'/' if dest.is_dir() else ''}"
            if dry_run:
                add("MOVE", s.path, f"to {where}", True)
                continue
            ok, why = move_agent_file(dest, target / s.move_to)
            add("DONE" if ok else "FAILED", s.path, f"moved to {where}" if ok else why, True)
            problems |= not ok
            continue
        if s.backup:
            to = ("the workspace's " if lay.owner_repo else "") + s.backup
            if dry_run:
                add("BACKUP", s.path, f"unchanged, to {to}", True)
                if s.remove:
                    add("REMOVE", s.path, s.what, True)
                    continue
            else:
                try:
                    intend(target / s.backup, stamped(dest.read_bytes(), now)[0])
                    ok = back_up(dest, target / s.backup, now)
                    did(target / s.backup)
                except OSError:
                    ok = False
                if not ok:
                    add("FAILED", s.path, f"its backup {to} did not read back as the original plus its stamp; the "
                        "file is left as it was", True)
                    problems = True
                    continue
                add("DONE", s.path, f"backed up to {to}, its bytes read back and compared", True)
                if s.remove:
                    try:
                        intend(dest, None)
                        dest.unlink()
                        did(dest)
                        ok = not dest.exists()
                    except OSError:
                        ok = False
                    add("DONE" if ok else "FAILED", s.path, "removed " + s.what if ok else "not removed", True)
                    problems |= not ok
                    continue
        if s.lines:
            missing = missing_groups(dest, s.lines)
            lines = [ln for g in missing for ln in g if not ln.startswith("#")]
            shown_lines = " | ".join(lines)
            if not missing:
                add(kept, s.path, "already holds the lines: " + s.what, had)
            elif dry_run:
                add("APPEND" if had else "CREATE", s.path,
                    f"{len(lines)} line{'s' if len(lines) != 1 else ''}: {shown_lines}" if had else shown_lines, had)
            else:
                try:
                    prev = dest.read_text(encoding="utf-8") if had else ""
                    sep = "" if not prev or prev.endswith("\n") else "\n"
                    new = prev + sep + "\n".join(ln for g in missing for ln in g) + "\n"
                    intend(dest, new.encode("utf-8"))
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(new, encoding="utf-8")
                    did(dest)
                    ok = not missing_groups(dest, s.lines)
                    verb = "appended" if prev else "written"
                    add("DONE" if ok else "FAILED", s.path, f"{verb}: {shown_lines}" if ok
                        else "the lines are still missing after the write", had)
                    problems |= not ok
                except OSError as ex:
                    add("FAILED", s.path, str(ex), had)
                    problems = True
            continue
        if had and s.record:
            add(kept, s.path, "a record, never replaced", True)
            continue
        if dry_run:
            add("REPLACE" if had else "CREATE", s.path, s.what, had)
            continue
        if s.action:
            intend(dest, unknown=True)
            status, detail = s.action(disk)
            did(dest)
        else:
            try:
                text = s.make()
                intend(dest, text.encode("utf-8"))
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")
                did(dest)
                # Read back what was written: the report states what is on disk, not what was meant.
                ok = dest.read_text(encoding="utf-8") == text
                status = "DONE" if ok else "FAILED"
                detail = ("replaced: " if had else "") + s.what if ok else "the file read back differs"
            except OSError as ex:
                status, detail = "FAILED", str(ex)
        add(status, s.path, detail, had)
        problems |= status not in ("DONE", "KEPT")
    return rows, problems


def finish(a, lay, target, dry_run, source, problem, rows, problems, out):
    """Today's direction's report, and the exit code that follows it."""
    if dry_run:
        print("DRY RUN: nothing has been written yet.", file=out)
        if source is not None or not target.exists():
            print("", file=out)
        # Each line short, its explanation indented below it, so the paths read at a glance.
        if source is not None:
            print(f"{'MOVE':<8} {shown(source)} → {shown(target / lay.public_dir)}   (the last step)", file=out)
            print(f"{'':<9}your whole folder becomes the public side, ignored files included; the session moves it "
                  "after the real run and the checks", file=out)
        if not target.exists():
            print(f"{'CREATE':<8} {shown(target)}   (before the real run)", file=out)
            print(f"{'':<9}the new private workspace, a new repository; the session creates it", file=out)
    else:
        print(f"{'FORM':<8} {describe(a, lay)}", file=out)
    print_report(rows, a, lay, target, dry_run, out)
    print("", file=out)
    if dry_run:
        if problem:
            print(f"REFUSED  the real run would stop here: {problem}", file=out)
            return 1
        return 0
    if problems:
        print("SETUP INCOMPLETE: a step above is SKIPPED or FAILED, and has not passed.", file=out)
        return 1
    print("every step done or kept", file=out)
    return 0


# ---------------------------------------------------------------- the private history

PUBLIC_PATHS_FILE = "public-paths.txt"
MARKERS_FILE = "public-markers.txt"
# In the private repository's git folder, never tracked: the record of every act of the real run, and the bytes of
# every file it changed or removed, so that `--undo` gives back exactly what was there and nothing else.
SPLIT_STATE = "airone-split.json"
SAVED = "airone-undo"
# The private repository's own root files: git reads them there, so they never move; a public repository gets one of
# these as another file of the project's, published under that name.
ROOT_OWN = (".gitignore", ".gitmodules", ".gitattributes")
CODE_EXT = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".mts")
IMPORT_RE = re.compile(r"""(?:\bfrom\s+|\bimport\s*\(\s*|\brequire\s*\(\s*|^\s*import\s+)['"](\.{1,2}/[^'"]+)['"]""",
                       re.M)
JOIN_RE = re.compile(r"\b(?:join|resolve)\s*\(((?:[^()]|\((?:[^()]|\([^()]*\))*\))*)\)")
HERE_RE = re.compile(r"__dirname|import\.meta\.(?:url|dirname)")
STRING_RE = re.compile(r"""['"]([^'"\n]*)['"]""")


class GitFailed(RuntimeError):
    """A git command whose failure is not an answer: the step it serves stops, never reads it as empty."""


def check_public():
    """The gate's code is the `check-public` command's, from this checkout's tools: one gate, the setup's and the
    hook's."""
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    return importlib.import_module("check_public")


def git_run(root, *args, stdin=None):
    """Git with replace refs off, as the gate runs it, so the old history read here is the one that exists."""
    return subprocess.run(["git", "-c", "core.quotepath=off", "-C", str(root), *args], capture_output=True,
                          text=True, input=stdin, encoding="utf-8", errors="surrogateescape",
                          env={**os.environ, "GIT_NO_REPLACE_OBJECTS": "1"})


def git_ok(root, *args, allowed=(0,), stdin=None):
    """A git command's output; an exit outside `allowed` raises GitFailed with git's own words."""
    p = git_run(root, *args, stdin=stdin)
    if p.returncode not in allowed:
        raise GitFailed(f"git {' '.join(args)} in {shown(root)} failed (exit {p.returncode}): "
                        f"{(p.stderr.strip() or p.stdout.strip())[:300]}")
    return p.stdout


def zsplit(text):
    return [x for x in text.split("\0") if x]


def has_commits(folder):
    """Whether the folder is the top of a git repository of its own with at least one commit. Both git calls answer
    yes or no; a failure is a no, which only asks the history question where it may not be needed."""
    folder = Path(folder).expanduser()
    if not folder.is_dir() or shutil.which("git") is None:
        return False
    top = git_run(folder, "rev-parse", "--show-toplevel")
    return (top.returncode == 0 and Path(top.stdout.strip()).resolve() == folder.resolve()
            and git_run(folder, "rev-parse", "--verify", "-q", "HEAD").returncode == 0)


def author(a):
    """(name, email) of the public commits."""
    name, _, rest = a["public_author"].partition("<")
    return name.strip(), rest.rstrip(">").strip()


def sides_of(a):
    return check_public().Sides.from_answers(a["sides"])


def hooks_path(where=None):
    """(the value, the file that sets it) of a core.hooksPath in effect, includes followed, or None: for a new
    repository (where=None) the global and the system configuration it would inherit; for an existing one, what git
    reads there. `git config` exits 1 when the key is unset, an answer; any other exit stops the step, since an
    unreadable configuration might hide one."""
    scopes = [["--global"], ["--system"]] if where is None else [[]]
    for scope in scopes:
        args = ["git"] + (["-C", str(where)] if where else []) + ["config", *scope, "--includes", "--show-origin",
                                                                   "--get", "core.hooksPath"]
        p = subprocess.run(args, capture_output=True, text=True)
        if p.returncode not in (0, 1):
            raise GitFailed(f"git config --get core.hooksPath failed (exit {p.returncode}): {p.stderr.strip()}")
        if p.returncode == 0 and p.stdout.strip():
            origin, _, value = p.stdout.strip().partition("\t")
            return value, origin.split(":", 1)[1] if origin.startswith("file:") else origin
    return None


def hooks_path_problem(found, where):
    """The refusal when a core.hooksPath is in effect: git would run the hooks from there, never the public
    repository's own pre-push gate. The setup leaves every configuration alone; the command is the owner's."""
    value, origin = found
    said = (f"core.hooksPath is set to {value} (in {origin}), so git would run the hooks from there and never the "
            "public repository's own pre-push gate")
    if origin.startswith("command line"):
        return (f"{said}. It comes from the environment (GIT_CONFIG_COUNT with GIT_CONFIG_KEY_n and GIT_CONFIG_VALUE_n, "
                "or GIT_CONFIG_PARAMETERS) or from a `git -c` option: unset that variable, or drop the option, in the "
                "shell or the tool that runs the setup, then run again")
    if not Path(origin).is_absolute() and where is not None and Path(origin).name == "config.worktree":
        command = f"git -C {shlex.quote(str(where))} config --worktree --unset core.hooksPath"
    elif not Path(origin).is_absolute() and where is not None and Path(origin).name == "config":
        command = f"git -C {shlex.quote(str(where))} config --local --unset core.hooksPath"
    elif Path(origin).is_absolute():
        command = f"git config --file {shlex.quote(origin)} --unset core.hooksPath"
    else:
        return f"{said}. Take it out of {origin}, then run again"
    return f"{said}; unset it ({command}), then run again"


def old_emails_of(target):
    return set(zsplit(git_ok(target, "log", "--all", "--format=%ae%x00%ce").replace("\n", "\0")))


@dataclass
class Survey:
    """What the private direction finds in the owner's repository before anything is written."""
    problems: list
    sides: object = None
    tracked: list = None
    moving: list = None      # tracked files whose side is public: they move into the public folder
    local: list = None       # ignored entries that travel with them and stay ignored there
    stays: list = None       # (path, why): what sits under a public path and stays private, where it is
    units: list = None       # what is moved, each a file or a whole folder holding only what moves
    rehome: list = None      # (local entry, the file whose rule ignores it now and stays behind)
    keep_ignored: list = None  # (private entry, the moving file whose rule ignores it now): the private side's rule
    imports: list = None     # (private file, its import, where the target goes)
    olds: set = None         # the e-mails of the old history
    ignored_before: list = None  # every ignored, untracked entry of the owner's folder before the run


def code_imports(text):
    """The relative paths a code file reaches: static imports and requires, and join/resolve paths built from the
    file's own folder. A heuristic: a path built any other way is not seen."""
    found = IMPORT_RE.findall(text)
    for m in JOIN_RE.finditer(text):
        if HERE_RE.search(m.group(1)):
            parts = STRING_RE.findall(m.group(1))
            if parts and (parts[0] in ("..", ".") or parts[0].startswith(("../", "./"))):
                found.append("/".join(parts))
    return found


def survey(a, lay, target):
    try:
        return survey_or_fail(a, lay, target)
    except GitFailed as ex:
        return Survey([str(ex)])


def survey_or_fail(a, lay, target):
    cp = check_public()
    sides = sides_of(a)
    public = target / lay.public_dir
    top = git_run(target, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != target.resolve():
        return Survey([f"{shown(target)} is not the top folder of a git repository: a private history is that "
                       "repository's"])
    problems = []
    if (git_dir(target) / SPLIT_STATE).exists():
        problems.append(f"a split is already staged or stopped in {shown(target)}: finish it with --first-commit, "
                        "or undo it with --undo")
    # rev-parse --verify exits 1 when there is no commit, an answer.
    if git_ok(target, "rev-parse", "--verify", "-q", "HEAD", allowed=(0, 1)).strip() == "":
        problems.append(f"{shown(target)} has no commits: there is no history to keep private; with none, the "
                        "project takes today's two-repository form or one repository")
    if public.exists() or public.is_symlink():
        problems.append(f"{shown(public)} exists: the public repository is born there, from nothing")
    dirty = zsplit(git_ok(target, "status", "--porcelain", "-z", "--untracked-files=all"))
    if dirty:
        shown_dirty = ", ".join(d[3:] for d in dirty[:3]) + (" …" if len(dirty) > 3 else "")
        problems.append(f"{shown(target)} has uncommitted changes ({shown_dirty}): commit, ignore or move them "
                        "first; the split moves files, and its undo restores what was there")
    found = hooks_path()
    if found:
        problems.append(hooks_path_problem(found, None))
    entries = [e.split("\t", 1) for e in zsplit(git_ok(target, "ls-files", "-s", "-z"))]
    tracked = [path for _, path in entries]
    gitlinks = [path for head, path in entries if head.startswith("160000 ")]
    ignored_before = zsplit(git_ok(target, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory",
                                   "-z"))
    ignored = []
    for e in ignored_before:
        # A local folder holding a private path moves piece by piece, so the private path stays where it is.
        if e.endswith("/") and sides.ignored_side(e) == "local" and any(
                w == "private" and cp.covers(e, r) and r != e for r, w in sides.words.items()):
            ignored += cp.expand(target, e)
        else:
            ignored.append(e)
    public_rules = {r: w for r, w in sides.words.items() if w == "public"}
    for rule, word in sorted(sides.words.items()):
        in_tracked = any(cp.covers(rule, f) for f in tracked)
        in_ignored = any(cp.covers(rule, e) or (e.endswith("/") and rule.startswith(e)) for e in ignored)
        if not in_tracked and not in_ignored:
            problems.append(f"sides: {rule} is not in the repository")
        if word == "local" and in_tracked:
            problems.append(f"sides: {rule} is local, which is for an ignored entry, but it covers tracked files")
        if word == "local" and sides.side_of(rule, ("public",)) is None:
            problems.append(f"sides: {rule} is local, but no public path holds it, so it would not travel")
    moving = [f for f in tracked if sides.side_of(f) == "public"]
    for f in moving:
        if cp.is_agent_file(f) or cp.is_agent_file(sides.dest(f)):
            rule = max((r for r in public_rules if cp.covers(r, f)), key=len)
            problems.append(f"sides: {rule} makes {f} public; it is the agent tool's, and never public")
    for g in gitlinks:
        if g in moving:
            problems.append(f"{g} holds a repository of its own, which cannot be moved into another one")
    local = [e for e in ignored if sides.ignored_side(e) == "local"]
    stays = [(r, "private") for r, w in sorted(sides.words.items()) if w == "private" and sides.side_of(r, ("public",))]
    stays += [(e, "ignored, no rule: private") for e in ignored
              if e not in local and sides.ignored_side(e) is None and sides.side_of(e, ("public",))]
    moving_set = set(moving) | set(local)
    items = tracked + ignored
    units = []
    for m in sorted(moving_set):
        parts = m.rstrip("/").split("/")
        unit = m
        for i in range(1, len(parts)):
            folder = "/".join(parts[:i]) + "/"
            whole = all(x in moving_set for x in items if x.startswith(folder))
            # A folder renamed inside is moved piece by piece, so each piece lands under its own public name.
            if whole and not any(r.startswith(folder) and r != folder for r in sides.dests):
                unit = folder
                break
        if unit not in units:
            units.append(unit)
    destinations = {}
    for m in sorted(moving_set):
        destinations.setdefault(sides.dest(m).rstrip("/"), []).append(m)
    for dest, sources in sorted(destinations.items()):
        if len(sources) > 1:
            problems.append(f"sides: two sources for one public path, {dest}: {', '.join(sources)}")

    def source_of(entry):
        probe = entry + ".probe" if entry.endswith("/") else entry
        # check-ignore exits 1 when nothing ignores the path, an answer.
        return git_ok(target, "check-ignore", "-v", "--no-index", "--", probe, allowed=(0, 1)).split(":", 1)[0]
    rehome = [(e, source_of(e) or "nothing") for e in local if source_of(e) not in moving]
    # What stays private and ignored must stay ignored: when the rule that ignores it lives in a file that moves to
    # the public side, the private side gets that rule of its own.
    keep_ignored = []
    for e in ignored:
        if e in moving_set:
            continue
        src = source_of(e)
        if src in moving:
            keep_ignored.append((e, src))
    imports = []
    for f in tracked:
        if f in moving_set or not f.endswith(CODE_EXT) or (target / f).is_symlink():
            continue
        try:
            text = (target / f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for spec in code_imports(text):
            reached = os.path.normpath(str(Path(f).parent / spec)).replace(os.sep, "/")
            if sides.side_of(reached) == "public" or sides.side_of(reached + "/") == "public":
                imports.append((f, spec, f"{lay.public_dir}/{sides.dest(reached)}"))
    olds = old_emails_of(target)
    if author(a)[1] in olds and not a["old_email_ok"]:
        problems.append("public_author: that e-mail signs the old history; answer another, such as a no-reply "
                        "address, or old_email_ok with the owner's yes")
    if shutil.which("gitleaks") is None:
        problems.append("gitleaks is not installed, so the gate cannot run; install it (https://github.com/gitleaks/"
                        "gitleaks: a release binary, `brew install gitleaks`, or `go install "
                        "github.com/zricethezav/gitleaks/v8@latest`) and run again")
    return Survey(problems, sides, tracked, moving, local, stays, units, rehome, keep_ignored, imports, olds,
                  ignored_before)


def file_bytes(path):
    """A file's bytes as git stores them: a symbolic link is its target's text, never what it points at."""
    return os.readlink(path).encode() if path.is_symlink() else path.read_bytes()


def preview_gate(a, lay, target, sv):
    """The gate on the files that would be public, read where they are, under their public names: the dry run's,
    and the real run's before it moves anything. The secret scan reads a temporary copy, mode 700, removed on every
    way out."""
    cp = check_public()
    report = cp.Report()
    files = [(sv.sides.dest(f), file_bytes(target / f)) for f in sv.moving]
    markers = cp.markers_from(a["markers"])
    cp.judge_files(report, files, sv.sides.public_view(), markers)
    cp.judge_words(report, "the identity", a["public_author"], markers)
    cp.judge_words(report, "the commit message", FIRST_MESSAGE, markers)
    cp.markers_part(report, markers)
    config = next((data for path, data in files if path == ".gitleaks.toml"), None)
    folder = tempfile.mkdtemp(prefix="airone-gate-")
    try:
        os.chmod(folder, 0o700)
        export = (Path(folder) / "files").resolve()
        export.mkdir()
        for path, data in files:
            dest = export / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        config_file = None
        if config is not None:
            config_file = Path(folder) / "gitleaks.toml"
            config_file.write_bytes(config)
            report.parts.append("gitleaks: the repository's own .gitleaks.toml is in effect, as tracked")
        ran, hits, note = cp.gitleaks(["dir", str(export)], export, config_file)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    cp.judge_secrets(report, ran, hits, note, f"the {len(files)} file(s) that would be public")
    report.parts.append(f"ignore: {len(sv.local)} local entr{'y' if len(sv.local) == 1 else 'ies'}, "
                        f"{len(sv.rehome)} of them ignored by a rule that stays private, re-homed into "
                        f"{lay.public_dir}/.gitignore; {len(sv.keep_ignored)} private entr"
                        f"{'y' if len(sv.keep_ignored) == 1 else 'ies'} whose rule moves, given one on the private side")
    cp.judge_identity(report, [author(a)], sv.olds, a["old_email_ok"])
    return report


def markers_text(a):
    """The markers file: each marker a line, verbatim, and nothing else; what the file is for is said in
    public-paths.txt's header and in the tools' README, since any line here is a marker."""
    return "".join(f"{m}\n" for m in a["markers"])


def nest_disk(a, lay, target):
    """Where a path of the plan is on disk now: before the move, a path of the public folder that moves there is
    still at its own place, under its own name, in the owner's folder."""
    cp = check_public()
    sides = sides_of(a)
    public = target / lay.public_dir
    prefix = lay.public_dir + "/"

    def disk(rel):
        if not public.exists() and rel.startswith(prefix):
            rest = rel[len(prefix):]
            for src, dst in sides.dests.items():
                if cp.covers(dst, rest):
                    return target / (src if not dst.endswith("/") else src + rest[len(dst):])
            if sides.side_of(rest) == "public" and sides.dest(rest) == rest:
                return target / rest
        return target / rel
    return disk


def public_ignore_lines(sv):
    """The lines the public repository's root .gitignore must hold: the local entries a private rule ignores now,
    and the agent tool's files."""
    cp = check_public()
    rehome = [f"/{sv.sides.dest(e)}" for e, _ in sv.rehome]
    return [("# Airone Giallo: ignored before the split by a rule that stays private", rehome),
            ("# Airone Giallo: the agent tool's files, created by a session opened here, never public, whatever "
             "their case", [cp.case_blind(p) for p in cp.AGENT_IGNORE])]


def private_ignore_lines(sv):
    """The lines the private side's root .gitignore must gain: what stays private and was ignored by a rule that
    moves to the public side."""
    return ("# Airone Giallo: ignored before the split by a rule that moved to the public side",
            [f"/{e}" for e, _ in sv.keep_ignored])


def project_rows(a, lay, sv, dry_run):
    cp = check_public()
    pub = lay.public_dir
    done = (lambda verb: verb) if dry_run else (lambda verb: "DONE")
    public_rules = {r: w for r, w in sv.sides.words.items() if w == "public"}
    rows = [(done("MOVE"), r, f"to {pub}/{sv.sides.dest(r)}") for r in sorted(public_rules)
            if r in sv.sides.dests or not any(cp.covers(o, r) for o in public_rules if o != r)]
    rows += [(done("MOVE"), e, f"local: ignored, travels to {pub}/{sv.sides.dest(e)} and stays ignored there")
             for e in sv.local]
    rows += [("STAYS", p, why) for p, why in sv.stays]
    for _, lines in public_ignore_lines(sv):
        if lines:
            rows.append((done("IGNORE"), f"{pub}/.gitignore", " ".join(lines)))
    for e, src in sv.keep_ignored:
        rows.append((done("IGNORE"), ".gitignore", f"/{e}   (ignored now by {src}, which moves to the public side; "
                     "the private side keeps its own rule)"))
    rows += [("LISTED", f, f"imports {spec}, which moves to {to}; private code reaching public code") for f, spec, to
             in sv.imports]
    rows += [(done("CREATE"), PUBLIC_PATHS_FILE, "the sides, read by the gate and the pre-push hook"),
             (done("CREATE"), MARKERS_FILE, "the markers, read by the gate and the pre-push hook")]
    return rows


def print_rows(rows, out):
    if not rows:
        return
    width = max(len(path) for _, path, _ in rows) + 1
    for st, path, detail in rows:
        print(f"    {st:<8} {path:<{width}} {detail}".rstrip(), file=out)


def print_private(a, lay, target, dry_run, prows, rows, out):
    public = target / lay.public_dir
    prefix = lay.public_dir + "/"
    if dry_run:
        print("DRY RUN: nothing has been written yet.\n", file=out)
    print(f"{'KEEP':<8} {shown(target)}   (the private repository, its history kept)", file=out)
    print(f"{'CREATE':<8} {shown(public)}   (a new repository, empty history; its first commit waits for the gate "
          "and the owner's yes)", file=out)
    print(f"{'':<9}{describe(a, lay)}", file=out)
    print(f"\nYour repository: {shown(target)} (private)", file=out)
    print("  The project's own paths", file=out)
    print_rows(prows, out)
    for title, mine in ((None, [r for r in rows if not r[1].startswith(prefix)]),
                        (f"The public repository: {shown(public)} (public, new)",
                         [(s, p[len(prefix):], d, h) for s, p, d, h in rows if p.startswith(prefix)])):
        if title and mine:
            print(f"\n{title}", file=out)
        for label, part in (("Files you have", [r for r in mine if r[3]]), ("New files", [r for r in mine if not r[3]])):
            if part:
                print(f"  {label}", file=out)
                print_rows([(s, p, d) for s, p, d, _ in part], out)
    if a["carry"]:
        print("\nCarried over after the run, as you confirmed", file=out)
        for line in a["carry"]:
            print(f"    {line}", file=out)


def print_gate(report, title, out):
    print(f"\n{title}", file=out)
    report.print(out)


def private_refusal(lines, out, dry_run, what="Nothing was written."):
    lead = "REFUSED  the real run would stop here:" if dry_run else "REFUSED"
    for line in lines:
        print(f"{lead} {line}.", file=out)
    if not dry_run:
        print(what, file=out)
    return 1


def git_dir(root):
    return Path(git_ok(root, "rev-parse", "--absolute-git-dir").strip())


def run_private(a, lay, target, dry_run, force, out):
    """The private history: the owner's folder stays where it is, the public repository is born inside it, and the
    first public commit waits for the gate and the owner's yes (--first-commit)."""
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    sv = survey(a, lay, target)
    if sv.tracked is None:
        return private_refusal(sv.problems, out, dry_run)
    disk = nest_disk(a, lay, target)
    try:
        ctx = context(a, lay, disk)
        steps = plan(a, lay, ctx, now, disk)
    except (OSError, RuntimeError, KeyError) as ex:
        print(f"FAILED  cannot prepare the install: {ex}", file=out)
        return 1
    problems = list(sv.problems)
    problem = invariants_problem(a, ctx, disk)
    if problem:
        problems.append(problem)
    for name in (PUBLIC_PATHS_FILE, MARKERS_FILE):
        if (target / name).exists():
            problems.append(f"{name} exists, and the setup writes its own; merge it by hand with the owner")
    existing = [s.path for s in steps if not s.lines and not s.kept and not s.backup and disk(s.path).exists()]
    if existing and not force:
        problems.append("these files exist; read them, keep what the owner wants, then rerun with --force (records "
                        "are kept even then): " + ", ".join(existing))
    taken = [s.backup for s in steps if s.backup and disk(s.backup).exists()]
    if taken:
        problems.append("a backup of that name exists, and a backup is never replaced: " + ", ".join(taken))
    if problems:
        return private_refusal(problems, out, dry_run)
    prows = project_rows(a, lay, sv, dry_run)
    gate = preview_gate(a, lay, target, sv)
    scrub = (f"the gate found {len(gate.errors)} problem(s) on the files that would be public; scrub them as commits "
             "in this repository, then run the dry run again")
    if dry_run:
        rows, _ = execute(steps, disk, target, lay, True, now)
        print_private(a, lay, target, True, prows, rows, out)
        print_gate(gate, f"The gate, on the {len(sv.moving)} file(s) that would be public", out)
        print("", file=out)
        return private_refusal([scrub], out, True) if gate.errors else 0
    if gate.errors:
        print_gate(gate, f"The gate, on the {len(sv.moving)} file(s) that would be public", out)
        return private_refusal([scrub], out, False)
    try:
        return split_now(a, lay, target, sv, steps, prows, now, out)
    except GitFailed as ex:
        print(f"FAILED  {ex}", file=out)
        print("STOPPED  before any commit. Every act so far is recorded; to give back what was there, run:", file=out)
        print(f"    {undo_command(target)}", file=out)
        return 1


# ---------------------------------------------------------------- the record and the undo

def content_hash(path):
    """What a path holds, as the record compares it: a file's bytes' hash, a link's target, a folder, or absent."""
    if path.is_symlink():
        return "link:" + os.readlink(path)
    if path.is_dir():
        return "folder"
    if not path.exists():
        return "absent"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(path):
    """A file's state for the whole-tree comparison: its content hash and its mode; None if absent."""
    if path.is_symlink():
        return "link:" + os.readlink(path)
    if not path.is_file():
        return None
    return f"{content_hash(path)}:{stat.S_IMODE(path.stat().st_mode):o}"


def index_entries(root):
    """What the index holds, by its entries (mode, object, stage, path): never its file's bytes, which git rewrites
    whenever it refreshes the stat data it caches."""
    return git_ok(root, "ls-files", "-s", "-z")


def tree_state(root, listed=()):
    """Every file and folder of the owner's folder, its git folder aside, with the index's entries and `git status
    --ignored`: what an undo must give back. A file under a `listed` entry (the local entries, installed dependencies
    among them) is compared by its size and time, not its bytes, which would cost too much to hash."""
    cp = check_public()
    files, dirs = {}, []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            dirnames[:] = [d for d in dirnames if d != ".git"]
        else:
            dirs.append(rel_dir.replace(os.sep, "/"))
        for name in filenames + [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]:
            p = Path(dirpath) / name
            rel = str(p.relative_to(root)).replace(os.sep, "/")
            if any(cp.covers(e, rel) for e in listed):
                st = p.lstat()
                files[rel] = f"listed:{st.st_size}:{st.st_mtime_ns}"
            else:
                files[rel] = digest(p)
    return {"files": files, "dirs": sorted(dirs), "index": index_entries(root),
            "status": git_ok(root, "status", "--porcelain", "--ignored", "-z", "--untracked-files=all")}


def listing(path):
    """What a moved folder or file holds, by name, size and time: cheap enough for installed dependencies. A folder
    inside it is listed by its name, ending in '/', so an empty one added later is seen."""
    if not path.is_dir() or path.is_symlink():
        st = path.lstat()
        return [["", st.st_size, st.st_mtime_ns]]
    out = []
    for p in sorted(path.rglob("*")):
        rel = str(p.relative_to(path)).replace(os.sep, "/")
        if p.is_file() or p.is_symlink():
            st = p.lstat()
            out.append([rel, st.st_size, st.st_mtime_ns])
        elif p.is_dir():
            out.append([rel + "/", 0, 0])
    return out


class Record:
    """The real run's acts, saved in the private repository's git folder. Each act is written down before it is done,
    with what it will leave, and marked done after: a run stopped between the two is settled by `--undo` from the
    disk."""

    def __init__(self, target, data):
        self.target, self.data = target, data
        self.folder = git_dir(target) / SAVED
        self.pending = {}

    @classmethod
    def begin(cls, target, pub, ignored_before, listed):
        record = cls(target, {"version": 2, "public": pub, "listed": list(listed),
                              "before": tree_state(target, listed), "ignored_before": ignored_before, "acts": []})
        record.folder.mkdir(exist_ok=True)
        index = git_dir(target) / "index"
        record.act({"act": "index", "saved": record.keep(index) if index.exists() else None,
                    "entries_before": record.data["before"]["index"], "entries_after": None, "done": True})
        return record

    @classmethod
    def load(cls, target):
        path = git_dir(target) / SPLIT_STATE
        return cls(target, json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else None

    def save(self):
        path = git_dir(self.target) / SPLIT_STATE
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def keep(self, path):
        """Keep a file's bytes and mode in the record's folder; the name under which they are kept."""
        name = f"{len(os.listdir(self.folder)):05d}"
        shutil.copy2(path, self.folder / name, follow_symlinks=False)
        return name

    def act(self, entry):
        self.data["acts"].append(entry)
        self.save()
        return entry

    def done(self, entry, **fields):
        entry.update(fields, done=True)
        self.save()

    def remove(self):
        shutil.rmtree(self.folder, ignore_errors=True)
        (git_dir(self.target) / SPLIT_STATE).unlink(missing_ok=True)

    def intend(self, rel, data=None, unknown=False):
        """Before a write: the folders it will make, the bytes the path holds now (kept), and the hash of what it will
        hold after ('absent' for a removal, None when a command writes and the run cannot know)."""
        p = self.target / rel
        parent, new_dirs = Path(rel).parent, []
        while str(parent) not in ("", ".") and not (self.target / parent).exists():
            new_dirs.append(parent.as_posix())
            parent = parent.parent
        dirs = [self.act({"act": "mkdir", "path": d, "done": False}) for d in reversed(new_dirs)]
        saved = self.keep(p) if (p.is_file() or p.is_symlink()) else None
        expect = None if unknown else ("absent" if data is None else hashlib.sha256(data).hexdigest())
        self.pending[rel] = (self.act({"act": "write", "path": rel, "saved": saved, "before": content_hash(p),
                                       "expect": expect, "done": False}), dirs)

    def did(self, rel):
        entry, dirs = self.pending.pop(rel)
        for d in dirs:
            if (self.target / d["path"]).is_dir():
                self.done(d)
        self.done(entry, after=content_hash(self.target / rel))

    def write(self, rel, data):
        """A write of the run's own, recorded around it."""
        self.intend(rel, data)
        path = self.target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.did(rel)


def undo_command(target):
    return f"python3 {shlex.quote(str(Path(__file__).resolve()))} --target {shlex.quote(str(target))} --undo"


SAVED_NAME = re.compile(r"\d{5}")
ACT_PATHS = {"write": ("path",), "mkdir": ("path",), "move": ("from", "to"), "git-init": ("path",),
             "public-folder": ("path",), "index": ()}


class NotTheRunsRecord(Exception):
    """The record cannot be the one the run wrote: a path outside the project, a kept name that is not one, a field
    missing, or text that is not the record's JSON."""


def check_record(record, target):
    """Refuse a record the run cannot have written, before anything is read from the disk through it: every path is
    relative, holds no '..', and has a parent that resolves inside the project's folder, symlinks resolved; every
    kept name is one the record's folder gives."""
    root = target.resolve()

    def inside(rel, what):
        if not isinstance(rel, str) or not rel.strip("/"):
            raise NotTheRunsRecord(f"{what}: {rel!r} is no path")
        p = PurePosixPath(rel.rstrip("/"))
        if p.is_absolute() or ".." in p.parts or "." in p.parts:
            raise NotTheRunsRecord(f"{what}: {rel} is not a path inside the project")
        parent = (target / p).parent.resolve()
        if parent != root and root not in parent.parents:
            raise NotTheRunsRecord(f"{what}: {rel} resolves outside {shown(target)}")

    data = record.data
    if not isinstance(data, dict) or not isinstance(data.get("acts"), list):
        raise NotTheRunsRecord("it holds no list of acts")
    inside(data.get("public"), "the public folder")
    for n, a in enumerate(data["acts"], 1):
        if not isinstance(a, dict) or a.get("act") not in ACT_PATHS:
            raise NotTheRunsRecord(f"act {n} is of no kind the run records")
        for key in ACT_PATHS[a["act"]]:
            inside(a.get(key), f"act {n} ({a['act']}, {key})")
        if a["act"] in ("write", "index") and a.get("saved") is not None and \
                not (isinstance(a["saved"], str) and SAVED_NAME.fullmatch(a["saved"])):
            raise NotTheRunsRecord(f"act {n} ({a['act']}): {a['saved']!r} is not a name the record keeps bytes under")


def runs_folder(rel, made_dirs, moved_to, written, git_dirs):
    """Whether a folder is the run's: one it made, one leading to what it made, moved or wrote, or one inside what it
    moved or inside the public repository's git folder."""
    return rel in made_dirs or any(m == rel or m.startswith(rel + "/") for m in [*made_dirs, *moved_to, *written]) \
        or any(rel == m or rel.startswith(m + "/") for m in [*moved_to, *git_dirs])


def resolve(record, target):
    """Every act of the record not yet undone, settled against the disk: (the steps to take, the obstacles). Nothing
    is changed here. An act the run started and did not mark done is read from the disk: whole at its old place
    (nothing to undo), whole at its new one (undone like a finished act), or an obstacle named as such."""
    acts = [a for a in record.data["acts"] if not a.get("undone")]
    pub = record.data["public"]
    steps, obstacles = [], []
    # What the run left that the undo will take away: files it created, folders it made, its moves' destinations, the
    # public repository's git folder.
    removed_files, made_dirs, moved_to, git_dirs = set(), set(), [], []
    writes = {}
    # A path the run wrote, or a folder it made, after moving its folder there is judged by its own act, not by the
    # move's listing: the record holds the moves first, so these are gathered first.
    written = {a["path"] for a in acts if a["act"] == "write"}
    made = {a["path"] for a in acts if a["act"] == "mkdir"}
    # A path the run wrote more than once is judged newest write first, as the reversal goes: the disk must hold what
    # the newest write left, and each write undone gives back what the one before it left.
    verdict, now, blocked = {}, {}, set()
    for i in reversed(range(len(acts))):
        a = acts[i]
        if a["act"] != "write" or a["path"] in blocked:
            continue
        cur = now[a["path"]] if a["path"] in now else content_hash(target / a["path"])
        if a["done"]:
            run_state = a["after"]
        elif cur == a["before"]:
            verdict[i] = None  # stopped before writing it: nothing to undo
            continue
        elif a["expect"] is not None and cur == a["expect"]:
            run_state = cur  # stopped after writing it, before the record said so
        else:
            kept = record.folder / a["saved"] if a["saved"] else None
            verdict[i] = ("obstacle", f"{a['path']}: the run was stopped while writing it, and it holds neither its "
                          f"earlier state nor the run's; its earlier bytes are kept at {kept}" if kept else
                          f"{a['path']}: the run was stopped while writing it, and it holds neither its earlier state "
                          "(absent) nor the run's")
            blocked.add(a["path"])
            continue
        if cur != run_state:
            verdict[i] = ("obstacle", f"{a['path']}: changed since the run wrote it")
            blocked.add(a["path"])
            continue
        verdict[i] = ("undo", run_state)
        now[a["path"]] = a["before"]
    for i, a in enumerate(acts):
        kind = a["act"]
        if kind == "write":
            if verdict.get(i) is None:
                continue  # never written, or not reached behind an obstacle on a newer write of the same path
            how, run_state = verdict[i]
            if how == "obstacle":
                obstacles.append(run_state)
                continue
            writes[a["path"]] = a
            if not a["saved"] and run_state != "absent":
                removed_files.add(a["path"])
            steps.append(("write", a))
        elif kind == "mkdir":
            if (target / a["path"]).is_dir():
                made_dirs.add(a["path"])
                steps.append(("mkdir", a))
        elif kind == "move":
            src, dest = target / a["from"].rstrip("/"), target / a["to"].rstrip("/")
            to_rel = a["to"].rstrip("/")
            own_inside = {w[len(to_rel) + 1:] for w in written if w.startswith(to_rel + "/")} | \
                {d[len(to_rel) + 1:] + "/" for d in made if d.startswith(to_rel + "/")}
            whole_at_new = os.path.lexists(dest) and (to_rel in written or [
                x for x in listing(dest) if x[0] not in own_inside] == [
                x for x in a["listing"] if x[0] not in own_inside])
            if not a["done"]:
                if os.path.lexists(src) and not os.path.lexists(dest):
                    continue  # stopped before the move
                if not (whole_at_new and not os.path.lexists(src)):
                    obstacles.append(f"{a['from']}: the run was stopped while moving it to {a['to']}, and it is whole "
                                     "at neither place")
                    continue
            elif not whole_at_new:
                obstacles.append(f"{a['to']}: changed since the run moved it there from {a['from']}")
                continue
            moved_to.append(to_rel)  # whole where the run left it: the run's, whatever its return place holds
            if os.path.lexists(src):
                what = "an empty folder" if src.is_dir() and not src.is_symlink() and not any(src.iterdir()) else \
                    "something"
                obstacles.append(f"{a['from']}: {what} is there again, where the undo puts back what the run moved "
                                 f"to {a['to']}; move it away first")
                continue
            for parent in Path(a["from"].rstrip("/")).parents:
                if str(parent) != "." and os.path.lexists(target / parent) and not (target / parent).is_dir():
                    obstacles.append(f"{parent}: a file where the undo needs the folder that held {a['from']}")
            steps.append(("move", a))
        elif kind == "git-init":
            if (target / a["path"]).exists():
                git_dirs.append(a["path"])
                steps.append(("git-init", a))
        elif kind == "public-folder":
            if (target / a["path"]).is_dir():
                steps.append(("public-folder", a))
        elif kind == "index":
            entries = index_entries(target)
            allowed = [x for x in (a.get("entries_after"), a["entries_before"]) if x is not None]
            # Stopped while staging: the index holds what the run staged, and the record does not say so yet. The
            # undo puts back the index kept before the run, whatever it holds now.
            if a.get("entries_after") is None and a.get("staging"):
                allowed = [entries]
            if entries not in allowed:
                obstacles.append(f"the private repository's index holds other entries than the run left: something "
                                 f"was staged or unstaged since. The run started from a clean tree, so `git -C "
                                 f"{target} reset -q` gives back the index it started from, and changes no file; "
                                 "then run --undo again")
                continue
            steps.append(("index", a))

    def accounted(rel):
        return (rel in removed_files or any(rel == m or rel.startswith(m + "/") for m in moved_to)
                or any(rel.startswith(g + "/") for g in git_dirs))

    def own_folder(rel):
        return runs_folder(rel, made_dirs, moved_to, written, git_dirs)
    # A folder the run made goes only when nothing of anyone else's is in it, an empty folder included.
    for d in sorted(made_dirs):
        for p in (target / d).rglob("*"):
            rel = str(p.relative_to(target)).replace(os.sep, "/")
            if p.is_dir() and not p.is_symlink():
                if not own_folder(rel):
                    obstacles.append(f"{rel}/: a folder inside {d}/, which the run made, and not the run's")
            elif not accounted(rel):
                obstacles.append(f"{rel}: inside {d}/, which the run made, and not the run's")
    public = target / pub
    if public.is_dir():
        for p in public.rglob("*"):
            rel = str(p.relative_to(target)).replace(os.sep, "/")
            if p.is_dir() and not p.is_symlink():
                if not own_folder(rel) and not any(rel == d or rel.startswith(d + "/") for d in made_dirs):
                    obstacles.append(f"{rel}/: a folder in the public folder, and not the run's")
            elif not accounted(rel):
                obstacles.append(f"{rel}: in the public folder, and not put there by the run")
    return steps, obstacles


def undo(target, out):
    """Reverse the real run's record. The record is checked first, every path in it inside the project; then every
    act, where the run left each thing and where it goes back; any obstacle is listed and nothing is changed. The
    reversal marks each act undone as it goes, so a second --undo continues where a first one was stopped. Then the
    tree, the index's entries and the status are compared with the state recorded before the run, and the last line
    says how."""
    state_file = git_dir(target) / SPLIT_STATE if (target / ".git").exists() else None
    try:
        record = Record.load(target)
        if record is None:
            print(f"REFUSED  no split is recorded in {shown(target)}: there is nothing to undo.", file=out)
            return 1
        check_record(record, target)
        steps, obstacles = resolve(record, target)
    except (NotTheRunsRecord, ValueError, KeyError, TypeError, AttributeError) as ex:
        # json's decoding error is a ValueError.
        print(f"REFUSED  {shown(state_file) if state_file else 'the record'} is not one the run wrote ({ex}); nothing "
              "was changed. Restore it from where it was copied, or put the project back by hand: the moves show in "
              "`git status`", file=out)
        return 1
    except (GitFailed, OSError) as ex:
        print(f"REFUSED  {ex}; nothing was changed", file=out)
        return 1
    if obstacles:
        print("REFUSED  the undo changed nothing. Deal with each of these, then run --undo again:", file=out)
        for o in obstacles:
            print(f"    {o}", file=out)
        return 1
    try:
        for kind, a in reversed(steps):
            if kind == "write":
                path = target / a["path"]
                if os.path.lexists(path):
                    path.unlink()
                if a["saved"]:
                    shutil.copy2(record.folder / a["saved"], path, follow_symlinks=False)
            elif kind == "mkdir":
                (target / a["path"]).rmdir()
            elif kind == "move":
                src, dest = target / a["from"].rstrip("/"), target / a["to"].rstrip("/")
                src.parent.mkdir(parents=True, exist_ok=True)
                os.rename(dest, src)
            elif kind == "git-init":
                shutil.rmtree(target / a["path"])
            elif kind == "public-folder":
                # Only the run's folders are left in it, the ones the moves made above what they moved: removed
                # deepest first.
                for dirpath, _, _ in sorted(os.walk(target / a["path"]), key=lambda w: -len(w[0])):
                    os.rmdir(dirpath)
            elif kind == "index":
                index = git_dir(target) / "index"
                index.unlink(missing_ok=True)
                if a["saved"]:
                    shutil.copy2(record.folder / a["saved"], index)
            a["undone"] = True
            record.save()
    except OSError as ex:
        print(f"FAILED  the undo stopped at {ex}; every act already reversed is marked so: deal with this, then run "
              "--undo again to finish", file=out)
        return 1
    before = record.data["before"]
    after = tree_state(target, record.data.get("listed", ()))
    differs = [k for k in ("files", "dirs", "index", "status") if after[k] != before[k]]
    if differs:
        print(f"FAILED  the undo ran, but the {', '.join(differs)} differ from before the run; the record is kept",
              file=out)
        return 1
    record.remove()
    listed = record.data.get("listed", [])
    print(f"UNDONE  {shown(target)} is as before the run: every file compared by its content hash and mode"
          + (f", except under the {len(listed)} local entr{'y' if len(listed) == 1 else 'ies'} "
             f"({', '.join(listed[:3])}{' …' if len(listed) > 3 else ''}), compared by name, size and time" if listed
             else "") + "; every folder; the index by its entries; and the status", file=out)
    return 0


def split_now(a, lay, target, sv, steps, prows, now, out):
    """The real run, once every refusal and the preview gate have passed: each act recorded as it goes, then the gate
    on what is staged and the link check across both repositories."""
    cp = check_public()
    public = target / lay.public_dir
    pub = lay.public_dir
    sides = sv.sides
    record = Record.begin(target, pub, sv.ignored_before, sv.local)
    folder_act = record.act({"act": "public-folder", "path": pub, "done": False})
    public.mkdir()
    record.done(folder_act)
    for unit in sv.units:
        dest = sides.dest(unit)
        src, to = target / unit.rstrip("/"), public / dest.rstrip("/")
        move = record.act({"act": "move", "from": unit, "to": f"{pub}/{dest}", "listing": listing(src),
                           "done": False})
        to.parent.mkdir(parents=True, exist_ok=True)
        os.rename(src, to)
        record.done(move)
    init = record.act({"act": "git-init", "path": f"{pub}/.git", "done": False})
    git_ok(public, "init", "-q", "-b", "main")
    record.done(init)
    name, email = author(a)
    for key, value in (("user.name", name), ("user.email", email)):
        git_ok(public, "config", key, value)
    rows, problems = execute(steps, lambda rel: target / rel, target, lay, False, now, track=record)
    setup_inside = [p[len(pub) + 1:] for s, p, d, had in rows if p.startswith(pub + "/") and not had]
    ignore = public / ".gitignore"
    had_ignore = ignore.exists() and ".gitignore" not in setup_inside
    record.write(f"{pub}/.gitignore", with_lines(ignore, public_ignore_lines(sv)).encode("utf-8"))
    if not had_ignore:
        setup_inside.append(".gitignore")
    comment, lines = private_ignore_lines(sv)
    if lines:
        record.write(".gitignore", with_lines(target / ".gitignore", [(comment, lines)]).encode("utf-8"))
    sides.setup |= set(setup_inside)
    record.write(PUBLIC_PATHS_FILE, sides.text().encode("utf-8"))
    record.write(MARKERS_FILE, markers_text(a).encode("utf-8"))
    record.write(".gitmodules", gitmodules_with(target, pub))
    failed = []
    # What stayed private and was ignored before the run must still be ignored, or staging would start tracking it:
    # nothing untracked and not ignored may sit under what was ignored before (a folder listed as ignored may hold
    # files each ignored by its own rule, so the files are what is asked about).
    loose = zsplit(git_ok(target, "ls-files", "--others", "--exclude-standard", "-z", "--", ".", f":(exclude){pub}"))
    unignored = sorted(f for f in loose if any(cp.covers(e, f) for e in sv.ignored_before))
    for f in unignored:
        failed.append(f"{f}: ignored before the run and no longer ignored on the private side")
    if not unignored:
        # Staging the private side records the moved files as removed from it and adds the setup's files; the public
        # folder is excluded, since it gets its gitlink only after its first commit.
        index_act = next(x for x in record.data["acts"] if x["act"] == "index")
        index_act["staging"] = True  # recorded before the first `git add`, so a run stopped while staging is undone
        record.save()
        git_ok(target, "add", "-A", "--", ".", f":(exclude){pub}")
        git_ok(public, "add", "-A")
        record.done(index_act, entries_after=index_entries(target))
    record.data["tree"] = git_ok(public, "write-tree").strip()
    record.save()
    gate = cp.staged(public, sides, cp.markers_from(a["markers"]), sv.olds, FIRST_MESSAGE)
    links = subprocess.run([sys.executable, str(TOOLS / "check_links.py"), "--root", str(target), "--public", pub,
                            "--cut", lay.cut], capture_output=True, text=True,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    errors = [ln[len("error: "):] for ln in links.stdout.splitlines() if ln.startswith("error: ")]
    stop = [e for e in errors if e.startswith(pub + "/")]
    listed = [e for e in errors if not e.startswith(pub + "/")]
    if links.returncode not in (0, 1):
        stop.append(f"check-links could not run (exit {links.returncode}): {links.stderr.strip()}")
    print_private(a, lay, target, False, prows, rows, out)
    for f in failed:
        print(f"FAILED  {f}", file=out)
    print_gate(gate, f"The gate, on what is staged in {shown(public)}", out)
    print(f"\nThe links across both repositories: check-links --public {pub} --cut {lay.cut}", file=out)
    for e in stop:
        print(f"error: {e}", file=out)
    if listed:
        print(f"  on the private side, listed for the session and never a stop ({len(listed)}): the move changes "
              f"where a private document's link to the public code points; write it as {pub}/<path>", file=out)
        for e in listed:
            print(f"    {e}", file=out)
    print(f"  {len(stop)} error(s) on the public side", file=out)
    print("", file=out)
    if gate.errors or stop or problems or failed:
        print("STOPPED  before any commit. Undo the split first; then fix what is listed above, as commits in this "
              "repository, and run the setup again. The undo:", file=out)
        print(f"    {undo_command(target)}", file=out)
        return 1
    print(f"READY  the gate passed on what is staged. With the owner's yes, the first public commit: "
          f"scaffold.py --answers <the same answers> --target {shown(target)} --first-commit", file=out)
    return 0


def with_lines(path, groups):
    """An ignore file's text with the lines of each (comment, lines) group it lacks added, never a line of it
    changed."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    have = set(text.splitlines())
    for comment, lines in groups:
        missing = [ln for ln in lines if ln not in have]
        if missing:
            text += ("" if not text or text.endswith("\n") else "\n") + "\n".join([comment] + missing) + "\n"
    return text


def gitmodules_with(target, pub):
    """The .gitmodules the public repository's entry needs, written by git on a copy, so the run knows the bytes it
    will write before it writes them."""
    folder = tempfile.mkdtemp(prefix="airone-modules-")
    try:
        copy = Path(folder) / "gitmodules"
        if (target / ".gitmodules").exists():
            shutil.copy2(target / ".gitmodules", copy)
        for key, value in (("path", pub), ("url", f"./{pub}")):
            git_ok(target, "config", "-f", str(copy), f"submodule.{pub}.{key}", value)
        return copy.read_bytes()
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def first_commit(a, lay, target, out):
    """After the gate and the owner's yes: the pre-push hook, the public repository's first commit, the submodule and
    the private commit. The hook comes first, so a public commit never exists without it; a run that failed midway is
    completed by running it again, each step done already being checked and skipped."""
    try:
        return first_commit_or_fail(a, lay, target, out)
    except GitFailed as ex:
        print(f"FAILED  {ex}", file=out)
        print("Run --first-commit again once this is fixed: the steps already done are checked and kept.", file=out)
        return 1


def first_commit_or_fail(a, lay, target, out):
    cp = check_public()
    public = target / lay.public_dir
    pub = lay.public_dir
    record = Record.load(target) if (target / ".git").exists() else None
    if record is None or "tree" not in record.data:
        return private_refusal([f"no split is staged in {shown(target)}: run the setup's real run first, and its gate"],
                               out, False, "Nothing was committed.")
    state = record.data
    hook = public / ".git" / "hooks" / "pre-push"
    template = PRE_PUSH_TEMPLATE.read_text(encoding="utf-8")
    problems = []
    if not (public / ".git").is_dir():
        problems.append(f"{shown(public)} is not a repository with its own git folder")
    found = hooks_path(public) if (public / ".git").is_dir() else None
    if found:
        problems.append(hooks_path_problem(found, public))
    if hook.exists() and hook.read_text(encoding="utf-8") != template:
        problems.append(f"{shown(hook)} exists and is not the setup's; merge the gate into it by hand")
    # rev-parse --verify exits 1 when there is no commit yet, an answer.
    committed = git_ok(public, "rev-parse", "--verify", "-q", "HEAD", allowed=(0, 1)).strip() != ""
    if committed and git_ok(public, "rev-parse", "HEAD^{tree}").strip() != state["tree"]:
        problems.append(f"{shown(public)} has a commit that is not the tree the gate passed")
    if not committed and git_ok(public, "write-tree").strip() != state["tree"]:
        problems.append("what is staged in the public repository is not what the gate passed; restore it, or undo the "
                        "split and run the setup again")
    added = zsplit(git_ok(target, "diff", "--cached", "--name-only", "-z", "--diff-filter=A"))
    was_ignored = sorted(p for p in added if any(cp.covers(e, p) for e in state.get("ignored_before", [])))
    if was_ignored:
        problems.append("the private commit would add what was ignored before the run: " + ", ".join(was_ignored)
                        + "; unstage it (git rm --cached)")
    if problems:
        return private_refusal(problems, out, False, "Nothing was committed.")
    rows = []

    def step(what, done, where, *args):
        if done:
            rows.append(("KEPT", what, "already done, checked"))
            return True
        p = git_run(where, *args)
        rows.append(("DONE" if p.returncode == 0 else "FAILED", what, "" if p.returncode == 0 else
                     (p.stderr.strip() or p.stdout.strip())))
        return p.returncode == 0

    if hook.exists():
        rows.append(("KEPT", "the pre-push hook", f"{shown(hook)}, already the setup's"))
    else:
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(template, encoding="utf-8")
        hook.chmod(0o755)
        ok = hook.read_text(encoding="utf-8") == template and os.access(hook, os.X_OK)
        rows.append(("DONE" if ok else "FAILED", "the pre-push hook", f"{shown(hook)}, running check-public on every "
                     "push, from this folder and from any worktree of it" if ok else "not written as the template"))
        if not ok:
            print_rows(rows, out)
            return 1
    if not committed:
        olds = old_emails_of(target)
        # The sides as the real run wrote them, the setup's own files declared one by one.
        written = cp.Sides.parse((target / PUBLIC_PATHS_FILE).read_text(encoding="utf-8"))
        gate = cp.staged(public, written, cp.read_markers_file(target / MARKERS_FILE), olds,
                         FIRST_MESSAGE)
        if gate.errors:
            print_rows(rows, out)
            print_gate(gate, f"The gate, on what is staged in {shown(public)}", out)
            return private_refusal([f"the gate found {len(gate.errors)} problem(s)"], out, False,
                                   "Nothing was committed.")
    if not step("the public repository's first commit", committed, public, "commit", "-q", "-m", FIRST_MESSAGE):
        print_rows(rows, out)
        print("Run --first-commit again once this is fixed: the steps already done are checked and kept, and the "
              "public repository's pre-push gate is already in place.", file=out)
        return 1
    head = git_ok(public, "rev-parse", "HEAD").strip()
    linked = any(e.startswith("160000 ") and e.split()[1] == head and e.split("\t", 1)[1] == pub
                 for e in git_ok(target, "ls-files", "-s", "--", pub).splitlines())
    if not step("the public repository registered as a submodule", linked, target, "submodule", "add", f"./{pub}",
                pub):
        print_rows(rows, out)
        return 1
    who = []
    # `git config` exits 1 when the key is unset, an answer.
    if not git_ok(target, "config", "user.email", allowed=(0, 1)).strip() and "GIT_AUTHOR_EMAIL" not in os.environ:
        last = git_ok(target, "log", "-1", "--format=%an%x00%ae").strip().split("\0")
        who = ["-c", f"user.name={last[0]}", "-c", f"user.email={last[1]}"]
    in_head = git_ok(target, "ls-tree", "HEAD", "--", pub).split()
    # diff --cached --quiet exits 1 when something is staged, an answer; any other exit is an error.
    staged_now = git_run(target, "diff", "--cached", "--quiet")
    if staged_now.returncode not in (0, 1):
        raise GitFailed(f"git diff --cached in {shown(target)} failed (exit {staged_now.returncode}): "
                        f"{staged_now.stderr.strip()}")
    private_done = len(in_head) >= 3 and in_head[2] == head and staged_now.returncode == 0
    if not step("the private repository's commit", private_done, target, *who, "commit", "-q", "-m",
                f"Airone Giallo: {pub}/ is born as the public repository, from one gated commit; the history stays "
                "here"):
        print_rows(rows, out)
        print("Run --first-commit again once this is fixed: the steps already done are checked and kept, and the "
              "public repository's pre-push gate is already in place.", file=out)
        return 1
    record.remove()
    clean = [git_ok(r, "status", "--porcelain").strip() for r in (target, public)]
    rows.append(("DONE" if not any(clean) else "FAILED", "both repositories clean",
                 "" if not any(clean) else "; ".join(c for c in clean if c)))
    print_rows(rows, out)
    return 0 if not any(clean) else 1


def parser():
    p = argparse.ArgumentParser(description="Install Airone Giallo into a project, with the optional tools it chose.",
                                epilog="Every answer can also come from --answers FILE, a JSON object with the "
                                "same names (underscores for dashes); a flag overrides the file.")
    p.add_argument("--answers", metavar="FILE", help="a JSON object of answers")
    p.add_argument("--target", default=".", help="the workspace root (default: the current folder)")
    p.add_argument("--dry-run", action="store_true", help="print what would be done, write nothing")
    p.add_argument("--force", action="store_true", help="replace existing instruction files; records are kept")
    p.add_argument("--name")
    p.add_argument("--purpose", help="one line: what the project is, for whom")
    p.add_argument("--invariants", action="append", metavar="TEXT",
                   help="repeatable: one paragraph, an invariant the project's existing instruction file states, "
                   "carried over as written on the owner's yes")
    p.add_argument("--mode", choices=MODES)
    p.add_argument("--cut", choices=CUTS, help="the last public rung of the ladder (default: plan)")
    p.add_argument("--human-docs", choices=SIDES, help="the side of human-docs/ (default: private)")
    p.add_argument("--sources", choices=SIDES, help="the side of sources/ (default: private)")
    p.add_argument("--agent-layer", choices=LAYERS, help="default: public with cut all, private otherwise; "
                   "both adds a contributors' AGENTS.md in the public folder")
    p.add_argument("--public-dir", help="the public repository's folder in the two-repository form "
                   "(default: the name, lower-cased)")
    p.add_argument("--graph", choices=GRAPHS, help="default: none")
    p.add_argument("--status", action=argparse.BooleanOptionalAction, default=None, help="default: on")
    p.add_argument("--family", action="append", metavar="CODE=WHAT", help="repeatable: a family of the status file")
    p.add_argument("--handoff", action=argparse.BooleanOptionalAction, default=None, help="default: on")
    p.add_argument("--stage", help="the name of the first log's stage (default: stage-1)")
    p.add_argument("--outward", choices=OUTWARD, help="default: gated")
    p.add_argument("--attribution", help="the trailer on outward acts, with --outward free")
    p.add_argument("--reserved", action="append", metavar="TEXT", help="repeatable: a decision the owner reserves")
    p.add_argument("--opinionated", action=argparse.BooleanOptionalAction, default=None, help="default: off")
    p.add_argument("--claude-code-version")
    p.add_argument("--model")
    for key in ("spec", "plan", "glossary", "findings", "owner-notes", "checks", "prune-after"):
        p.add_argument(f"--{key}")
    p.add_argument("--frozen", action="append", metavar="PATH", help="repeatable: a folder never edited")
    p.add_argument("--copies", action="append", metavar="PATH", help="repeatable: a generated or synced copy")
    for k in MACHINE_KEYS:
        p.add_argument(f"--machine-{k}")
    p.add_argument("--move-from", metavar="DIR", help="two repositories: the owner's folder, which the session moves "
                   "whole into the workspace as the public side; a dry run before the move shows it")
    p.add_argument("--carry", action="append", metavar="LINE", help="repeatable: one confirmed line of where a part "
                   "of the old instruction file goes, carried over by the session after the run")
    p.add_argument("--history", choices=HISTORIES, help="two repositories, a folder with commits: private keeps the "
                   "folder and its history private and gives birth to the public repository inside it; publish makes "
                   "the folder, history and all, the public side (required when the folder has commits)")
    p.add_argument("--side", action="append", metavar="PATH=SIDE", help="history private, repeatable: one of the "
                   "project's paths and its side, public, private or local")
    p.add_argument("--marker", action="append", metavar="WORD", help="history private, repeatable: a word of the "
                   "owner's that must never be published")
    p.add_argument("--public-author", metavar="'NAME <EMAIL>'", help="history private: the public commits' identity")
    p.add_argument("--old-email-ok", action=argparse.BooleanOptionalAction, default=None,
                   help="history private: the owner's yes to a public identity the old history used")
    p.add_argument("--first-commit", action="store_true", help="history private, after the gate and the owner's yes: "
                   "the pre-push hook, the public repository's first commit, the submodule and the private commit")
    p.add_argument("--undo", action="store_true", help="history private, after a real run that stopped: reverse it "
                   "from its record, touching only what the run wrote; needs only --target")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    target = Path(args.target).expanduser().resolve()
    if args.undo:
        # The undo reads its record, not the answers: it reverses what was done, whatever is answered now.
        if not target.is_dir():
            print(f"FAILED  the target {target} is not a folder", file=sys.stderr)
            return 2
        return undo(target, sys.stdout)
    try:
        answers = load_answers(args)
        # The folder handed over for two repositories: with commits, the direction of its history is an answer the
        # setup never takes by default, since a history once published cannot be called back.
        handed = answers["move_from"] or str(target)
        if not answers["history"] and form_of(answers["cut"]) == "two" and has_commits(handed):
            raise AnswerError(f"'history' is required: {handed} has commits. Answer private (the folder and its "
                              "history stay private, and the public repository is born inside it) or publish (the "
                              "folder, its whole history with it, becomes the public side)")
        if args.first_commit and answers["history"] != "private":
            raise AnswerError("--first-commit belongs to a history that stays private (history: private)")
    except AnswerError as ex:
        print(f"invalid answers: {ex}", file=sys.stderr)
        return 2
    if args.first_commit:
        if not target.is_dir():
            print(f"FAILED  the target {target} is not a folder", file=sys.stderr)
            return 2
        return first_commit(answers, Layout.of(answers), target, sys.stdout)
    # Before the move the workspace may not exist yet: only a dry run that shows the move may look at it.
    if not target.is_dir() and not (args.dry_run and answers["move_from"]):
        print(f"FAILED  the target {target} is not a folder", file=sys.stderr)
        return 2
    return run(answers, target, args.dry_run, args.force)


if __name__ == "__main__":
    sys.exit(main())
