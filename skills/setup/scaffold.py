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
import importlib.util
import json
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

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
}
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
    validate_sides(a)


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
    if form != "two":
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

    @classmethod
    def of(cls, a):
        return cls(a["cut"], form_of(a["cut"]), a["public_dir"], a["agent_layer"])

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
    if lay.form == "one-private":
        return "everything is private, and the ladder still orders the citations"
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
    return words


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
    if lay.form == "two":
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
                      if disk((f"{lay.public_dir}/" if lay.form == "two" else "") + n).is_file()],
        "claude_code_version": a["claude_code_version"] or SLOT.format("version"),
        "model": a["model"] or SLOT.format("model"),
        "four_hands": a["mode"] == "four-hands", "conductor": a["mode"] == "conductor",
        "sides": sides_in_words(a, lay), "layer_public": lay.agent_layer == "public",
        "commands": join([code(c) for c, on in (("specgraph", graph_file), ("check-status", a["status"]),
                                                    ("check-archive", True), ("check-links", True),
                                                    ("check-frontmatter", True)) if on]),
        "two_repos": lay.form == "two", "public_dir": lay.public_dir, "contributors": lay.agent_layer == "both",
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


def allowlist(a, lay):
    """The private workspace's .gitignore: everything ignored unless named, so nothing private is committed without
    being named first; the public folder is one entry, so only its gitlink is tracked."""
    names = {"docs": "docs/", "graph": "graph.yml", "plan": "plan/", "ai-docs": "ai-docs/"}
    private = [n for r, n in names.items() if not lay.public(r) and (r != "graph" or a["graph"] != "none")]
    private.append(f"{ARCHIVE}/")  # the workspace's own archive, always private
    lines = ["# Airone Giallo: the private workspace's allowlist. Everything is ignored unless re-included below,",
             "# so nothing private is committed without being named first; local-machine.md stays ignored.",
             "/*", "!/.gitignore", "!/.gitmodules", "!/.ignore", "!/AGENTS.md", "!/CLAUDE.md", "!/RATIONALE.md",
             "# the project's skills, and nothing else of the agent tool's folder",
             "!/.claude/", "/.claude/*", "!/.claude/skills/"]
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
    if lay.form == "two":
        text = allowlist(a, lay)
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
    repo = f"{lay.public_dir}/" if lay.form == "two" else ""
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
    moved = shown(target / lay.public_dir)
    source = Path(a["move_from"]).expanduser().resolve() if a["move_from"] else None
    here = f"{shown(source)} (public; moved last to {moved})" if source and not (target / lay.public_dir).exists() \
        else f"{moved} (public)"
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
        if a["carry"] and key == sections[0][0]:
            print("  Carried over after the run, as you confirmed", file=out)
            for line in a["carry"]:
                print(f"    {line}", file=out)


def run(a, target, dry_run, force, out=None):
    out = out or sys.stdout
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    lay = Layout.of(a)
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

    existing = [s for s in steps if not s.lines and not s.kept and not s.backup and disk(s.path).exists()]
    if existing and not force:
        print("REFUSED  these files exist; nothing was written. Read them, keep what the owner wants, then rerun "
              "with --force (records are kept even then):", file=out)
        for s in existing:
            print(f"  {s.path}", file=out)
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

    # The real run reports whether each step happened (DONE, KEPT, SKIPPED, FAILED); the dry run, which does nothing,
    # what each step would do (CREATE, REPLACE, APPEND, KEEP, and BACKUP and REMOVE for an old instruction file).
    kept = "KEEP" if dry_run else "KEPT"
    rows, problems = [], False

    def add(status, path, detail, had):
        rows.append((status, path, detail, had))

    for s in steps:
        dest = disk(s.path)
        had = dest.exists()
        if s.kept:
            add(kept, s.path, s.kept, True)
            continue
        if s.backup:
            to = ("the workspace's " if lay.form == "two" else "") + s.backup
            if dry_run:
                add("BACKUP", s.path, f"unchanged, to {to}", True)
                if s.remove:
                    add("REMOVE", s.path, s.what, True)
                    continue
            else:
                try:
                    ok = back_up(dest, target / s.backup, now)
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
                        dest.unlink()
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
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(prev + sep + "\n".join(ln for g in missing for ln in g) + "\n",
                                    encoding="utf-8")
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
            status, detail = s.action(disk)
        else:
            try:
                text = s.make()
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")
                # Read back what was written: the report states what is on disk, not what was meant.
                ok = dest.read_text(encoding="utf-8") == text
                status = "DONE" if ok else "FAILED"
                detail = ("replaced: " if had else "") + s.what if ok else "the file read back differs"
            except OSError as ex:
                status, detail = "FAILED", str(ex)
        add(status, s.path, detail, had)
        problems |= status not in ("DONE", "KEPT")

    if dry_run:
        print("DRY RUN: nothing has been written yet.", file=out)
        if source is not None or not target.exists():
            print("", file=out)
        if source is not None:
            print(f"{'MOVE':<8} {shown(source)} → {shown(target / lay.public_dir)}   your whole folder becomes the "
                  "public side, ignored files included; the session moves it last, after the real run and the "
                  "checks", file=out)
        if not target.exists():
            print(f"{'CREATE':<8} {shown(target)}   the new private workspace, a new repository; the session creates "
                  "it before the real run", file=out)
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
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    target = Path(args.target).expanduser().resolve()
    try:
        answers = load_answers(args)
    except AnswerError as ex:
        print(f"invalid answers: {ex}", file=sys.stderr)
        return 2
    # Before the move the workspace may not exist yet: only a dry run that shows the move may look at it.
    if not target.is_dir() and not (args.dry_run and answers["move_from"]):
        print(f"FAILED  the target {target} is not a folder", file=sys.stderr)
        return 2
    return run(answers, target, args.dry_run, args.force)


if __name__ == "__main__":
    sys.exit(main())
