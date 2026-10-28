#!/usr/bin/env python3
"""Install the pieces of Airone Giallo a project chose into that project's folder.

    python3 scaffold.py --answers ANSWERS.json [--target DIR] [--dry-run] [--force]
    python3 scaffold.py --name N --purpose P --mode conductor [more flags] [--target DIR] ...

The `setup` skill asks the questions and writes the answers; this script does the mechanics. Answers come from a
JSON file, from flags, or both; a flag overrides the file. `--help` lists every answer; DEFAULTS below holds the
defaults.

What it writes, in the target folder: AGENTS.md (with the opinionated layer appended when chosen), CLAUDE.md,
RATIONALE.md, local-machine.md (git-ignored), lines appended to .gitignore; with the status file, the status file and
its closed file in the docs folder and the checker in tools/; with the handoff, the state and the first log in
handoff/; with the graph, graph.yml through `python -m specgraph init`.

The rule it exists to obey: never report success for a step it did not perform. Every step is reported as done,
kept, skipped or failed, and the exit code follows the report: 0 when every step was done or kept, 1 when any was
refused, skipped or failed, 2 when the answers are invalid; a dry run exits 0 unless the real run would be
refused. Before writing anything it checks every target: an
existing file stops the whole run unless --force, so a refusal never leaves half an install. With --force the
instruction files are replaced, but a record (the status file, the closed file, the handoff, RATIONALE.md, the
graph file) is kept as it is, since replacing it with an empty one would delete the project's history.

Standard library only; the graph step runs specgraph in a child process when it is importable.
"""

import argparse
import datetime
import importlib.util
import json
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
KIT = HERE.parent.parent
REGISTER_TEMPLATES = KIT / "status" / "templates"
REGISTER_CHECKER = KIT / "status" / "tools" / "check_status.py"
HANDOFF_TEMPLATE = KIT / "skills" / "handoff" / "references" / "handoff-template.md"

MODES = ("conductor", "four-hands")
LAYOUTS = ("single", "umbrella")
GRAPHS = ("none", "lite", "full")
OUTWARD = ("gated", "free")
# The status checker's own grammar for a family code; a code it would reject is refused here, before writing.
FAMILY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,4}(?:-[A-Z][A-Z0-9]{1,4})?$")
# What the written file shows where the owner has not answered yet; `grep -n 'to fill'` lists what is left. Square
# brackets, not angle ones: `<to fill: x>` is a valid HTML tag to a Markdown renderer, which would hide it.
SLOT = "[to fill: {}]"

DEFAULTS = {
    "invariants": [], "layout": "single", "graph": "none", "status": True, "families": {}, "handoff": True,
    "stage": "stage-1", "outward": "gated", "attribution": "", "reserved": [], "opinionated": False,
    "claude_code_version": "", "model": "", "spec": "", "plan": "", "glossary": "", "findings": "",
    "owner_notes": "", "frozen": [], "copies": [], "checks": "", "prune_after": "", "docs_dir": "docs",
    "machine": {},
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
    """Render the kit's template subset: {{name}} is a value, {{#name}}…{{/name}} keeps its body when the value is
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


WIDTH = 120  # the kit's own line length for Markdown


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
    for key, allowed in (("mode", MODES), ("layout", LAYOUTS), ("graph", GRAPHS), ("outward", OUTWARD)):
        if a[key] not in allowed:
            raise AnswerError(f"'{key}' is {a[key]!r}; it must be one of {', '.join(allowed)}")
    if a["attribution"] and a["outward"] != "free":
        raise AnswerError("an attribution trailer is written only when outward acts are free")
    for key in ("status", "handoff", "opinionated"):
        if not isinstance(a[key], bool):
            raise AnswerError(f"'{key}' must be true or false")
    for key in ("invariants", "reserved", "frozen", "copies"):
        if not isinstance(a[key], list) or not all(isinstance(x, str) for x in a[key]):
            raise AnswerError(f"'{key}' must be a list of strings")
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
    if not re.match(r"^[A-Za-z0-9._-]+$", a["stage"]):
        raise AnswerError("'stage' names a file: letters, digits, dot, dash or underscore")
    docs = Path(a["docs_dir"])
    if docs.is_absolute() or ".." in docs.parts:
        raise AnswerError("'docs_dir' is a folder inside the project")


def code(path):
    return f"`{path}`"


def context(a):
    """The values the templates read, derived from the answers. What is not answered shows as a visible slot."""
    docs = a["docs_dir"].rstrip("/")
    register_file, closed_file = f"{docs}/status.md", f"{docs}/closed.md"
    handoff_state = "handoff/current.md"

    families = []
    if a["graph"] != "none":
        families.append("the statement families declared in `graph.yml`'s meta, allocated by `graph.yml`")
    if a["status"]:
        codes = ", ".join(code(c) for c in a["families"])
        families.append(f"{codes} for work items, allocated by `{register_file}` (its checker prints the next free ID)")

    checks = []
    if a["graph"] != "none":
        checks.append("`specgraph lint`")
    if a["status"]:
        graph_flag = " --graph graph.yml" if a["graph"] != "none" else ""
        checks.append(f"`python3 tools/check_status.py {register_file} {closed_file}{graph_flag}`")
    if a["checks"]:
        checks.append(a["checks"])
    if not checks:
        checks.append(SLOT.format("the project's test and lint commands"))

    if a["handoff"]:
        opening = code(handoff_state)
    elif a["status"]:
        opening = f"`git log` since the last session and `{register_file}`"
    else:
        opening = "`git log` since the last session"

    m = a["machine"]
    return {
        "name": a["name"].strip(),
        "purpose": a["purpose"].strip().rstrip("."),
        "invariants": "; ".join(a["invariants"]) if a["invariants"]
        else SLOT.format("each invariant, and what breaks"),
        "claude_code_version": a["claude_code_version"] or SLOT.format("version"),
        "model": a["model"] or SLOT.format("model"),
        "four_hands": a["mode"] == "four-hands", "conductor": a["mode"] == "conductor",
        "umbrella": a["layout"] == "umbrella",
        "status": a["status"], "handoff": a["handoff"],
        "status_file": register_file, "closed_file": closed_file, "handoff_state": handoff_state,
        "spec": a["spec"], "plan": a["plan"], "glossary": a["glossary"], "findings": a["findings"],
        "families": "; ".join(families), "open": opening, "checks": "; ".join(checks),
        "reserved": a["reserved"], "owner_notes": a["owner_notes"],
        "gated": a["outward"] == "gated", "free": a["outward"] == "free", "attribution": a["attribution"],
        "frozen": [code(f) for f in a["frozen"]], "copies": [code(c) for c in a["copies"]],
        "prune_after": a["prune_after"] or SLOT.format("a period"),
        "machine_resources": m.get("resources") or SLOT.format("cores, memory, disk, accelerators"),
        "machine_load": m.get("load") or SLOT.format("other sessions, agents, services, scheduled jobs"),
        "machine_limits": m.get("limits") or SLOT.format("the longest run and the most parallel jobs allowed"),
        "machine_timings": m.get("timings") or SLOT.format("yes, or no and why"),
    }


# ---------------------------------------------------------------- the steps

@dataclass
class Step:
    path: str           # relative to the target
    what: str           # one line for the report
    make: object        # a function returning the file's text, or None for an action step
    record: bool = False  # a record is never replaced, even with --force
    action: object = None  # for a step that is not a plain write (the graph)


def stamp_frontmatter(text, now):
    """Fill the date slots of the leading frontmatter only; the same slots further down are examples of an entry."""
    if not text.startswith("---\n"):
        return text
    end = text.index("\n---\n", 4)
    head = (text[:end].replace("<YYYY-MM-DDTHH:MM:SS+00:00>", now.strftime("%Y-%m-%dT%H:%M:%S+00:00"))
            .replace("<YYYY-MM-DD>", now.strftime("%Y-%m-%d")))
    return head + text[end:]


def replace_once(text, old, new, source):
    """Replace a passage the template is known to hold; a template that changed under the script is a failure."""
    if text.count(old) != 1:
        raise RuntimeError(f"{source}: expected the passage {old[:50]!r} once, found it {text.count(old)} times")
    return text.replace(old, new)


def handoff_files(stage, now):
    text = HANDOFF_TEMPLATE.read_text(encoding="utf-8")
    blocks = re.findall(r"^```markdown\n(.*?)^```$", text, re.M | re.S)
    if len(blocks) != 2:
        raise RuntimeError(f"{HANDOFF_TEMPLATE}: expected two ```markdown blocks, the state and the log; "
                           f"found {len(blocks)}")
    log_name = f"log-{stage}.md"
    state = replace_once(blocks[0], "[<log file>](<log file>)", f"[{log_name}]({log_name})", HANDOFF_TEMPLATE)
    log = blocks[1].replace("<stage>", stage)
    return stamp_frontmatter(state, now), stamp_frontmatter(log, now), log_name


def register_files(a, ctx, now):
    reg = REGISTER_TEMPLATES.joinpath("status.md").read_text(encoding="utf-8")
    fams = "\n".join(f"  {c}: {w}" for c, w in a["families"].items())
    reg = replace_once(reg, "  <CODE>: <what the family covers: a repository, or an area of one>", fams,
                       "status.md template")
    reg = replace_once(reg, "python3 <tools>/check_status.py <this file> <the closed file>",
                       f"python3 tools/check_status.py {ctx['status_file']} {ctx['closed_file']}",
                       "status.md template")
    closed = REGISTER_TEMPLATES.joinpath("closed.md").read_text(encoding="utf-8")
    return stamp_frontmatter(reg, now), stamp_frontmatter(closed, now)


def specgraph_available():
    return importlib.util.find_spec("specgraph") is not None


def graph_action(profile):
    def run(target):
        if not specgraph_available():
            return ("SKIPPED", f"specgraph is not importable from {sys.executable}; install the kit's graph "
                    f"(pip install -e <kit>/graph), then run: specgraph init --profile {profile}")
        proc = subprocess.run([sys.executable, "-m", "specgraph", "init", "--profile", profile,
                               "--registry", "graph.yml"], cwd=target, capture_output=True, text=True)
        out = (proc.stdout + proc.stderr).strip()
        # Measure the artifact, not the command: the file must exist and carry its meta.
        reg = target / "graph.yml"
        if proc.returncode != 0 or not reg.is_file() or "meta:" not in reg.read_text(encoding="utf-8"):
            return ("FAILED", f"specgraph init exited {proc.returncode}: {out}")
        return ("DONE", f"{profile} profile, by specgraph init")
    return run


def plan(a, ctx, now):
    agents = render(TEMPLATES.joinpath("AGENTS.md").read_text(encoding="utf-8"), ctx)
    if a["opinionated"]:
        agents += render(TEMPLATES.joinpath("opinionated.md").read_text(encoding="utf-8"), ctx)
    agents = rewrap(agents)
    rationale = rewrap(render(TEMPLATES.joinpath("RATIONALE.md").read_text(encoding="utf-8"), ctx))
    steps = [
        Step("AGENTS.md", "the instruction file", lambda: agents),
        Step("CLAUDE.md", "one line, importing AGENTS.md", lambda: TEMPLATES.joinpath("CLAUDE.md").read_text(encoding="utf-8")),
        Step("RATIONALE.md", "where each rule came from",
             lambda: rationale, record=True),
        Step("local-machine.md", "this device's resources and limits (git-ignored)",
             lambda: render(TEMPLATES.joinpath("local-machine.md").read_text(encoding="utf-8"), ctx)),
    ]
    if a["status"]:
        reg, closed = register_files(a, ctx, now)
        steps += [
            Step(ctx["status_file"], "the status file", lambda: reg, record=True),
            Step(ctx["closed_file"], "the closed file", lambda: closed, record=True),
            Step("tools/check_status.py", "the status file's checker",
                 lambda: REGISTER_CHECKER.read_text(encoding="utf-8")),
        ]
    if a["handoff"]:
        state, log, log_name = handoff_files(a["stage"], now)
        steps += [
            Step("handoff/current.md", "the handoff's state", lambda: state, record=True),
            Step(f"handoff/{log_name}", "the handoff's first log", lambda: log, record=True),
        ]
    if a["graph"] != "none":
        steps.append(Step("graph.yml", f"the graph file ({a['graph']} profile)", None, record=True,
                          action=graph_action(a["graph"])))
    return steps


def gitignore_addition(target):
    """The lines of gitignore-lines that .gitignore lacks, with the comment, or '' when none is missing."""
    lines = TEMPLATES.joinpath("gitignore-lines").read_text(encoding="utf-8").splitlines()
    gi = target / ".gitignore"
    have = set(gi.read_text(encoding="utf-8").splitlines()) if gi.exists() else set()
    missing = [ln for ln in lines if ln and not ln.startswith("#") and ln not in have]
    if not missing:
        return ""
    return "\n".join([ln for ln in lines if ln.startswith("#")] + missing) + "\n"


# ---------------------------------------------------------------- running

def run(a, target, dry_run, force, out=None):
    out = out or sys.stdout
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    ctx = context(a)
    try:
        steps = plan(a, ctx, now)
    except (OSError, RuntimeError, KeyError) as ex:
        print(f"FAILED  cannot prepare the install: {ex}", file=out)
        return 1

    existing = [s for s in steps if (target / s.path).exists()]
    if existing and not force:
        print("REFUSED  these files exist; nothing was written. Read them, keep what the owner wants, then rerun "
              "with --force (records are kept even then):", file=out)
        for s in existing:
            print(f"  {s.path}", file=out)
        return 1

    report, problems = [], False
    for s in steps:
        dest = target / s.path
        if dest.exists() and s.record:
            report.append(("KEPT", s.path, "a record, never replaced"))
            continue
        if dry_run:
            verb = "replace" if dest.exists() else "create"
            report.append(("WOULD", s.path, f"{verb}: {s.what}"))
            continue
        if s.action:
            status, detail = s.action(target)
        else:
            try:
                text = s.make()
                dest.parent.mkdir(parents=True, exist_ok=True)
                was = dest.exists()
                dest.write_text(text, encoding="utf-8")
                # Read back what was written: the report states what is on disk, not what was meant.
                ok = dest.read_text(encoding="utf-8") == text
                status = "DONE" if ok else "FAILED"
                detail = ("replaced: " if was else "") + s.what if ok else "the file read back differs"
            except OSError as ex:
                status, detail = "FAILED", str(ex)
        report.append((status, s.path, detail))
        problems |= status not in ("DONE", "KEPT")

    addition = gitignore_addition(target)
    if not addition:
        report.append(("KEPT", ".gitignore", "already ignores the machine file"))
    elif dry_run:
        report.append(("WOULD", ".gitignore", "append: " + addition.strip().replace("\n", " | ")))
    else:
        gi = target / ".gitignore"
        try:
            prev = gi.read_text(encoding="utf-8") if gi.exists() else ""
            sep = "" if not prev or prev.endswith("\n") else "\n"
            gi.write_text(prev + sep + addition, encoding="utf-8")
            ok = not gitignore_addition(target)
            report.append(("DONE" if ok else "FAILED", ".gitignore", "appended the machine file's line" if ok
                           else "the line is still missing after the write"))
            problems |= not ok
        except OSError as ex:
            report.append(("FAILED", ".gitignore", str(ex)))
            problems = True

    for status, path, detail in report:
        print(f"{status:<8} {path:<28} {detail}", file=out)
    if dry_run:
        print("dry run: nothing was written", file=out)
        return 0
    if problems:
        print("SETUP INCOMPLETE: a step above is SKIPPED or FAILED, and has not passed.", file=out)
        return 1
    print("every step done or kept", file=out)
    return 0


def parser():
    p = argparse.ArgumentParser(description="Install the chosen pieces of Airone Giallo into a project.",
                                epilog="Every answer can also come from --answers FILE, a JSON object with the "
                                "same names (underscores for dashes); a flag overrides the file.")
    p.add_argument("--answers", metavar="FILE", help="a JSON object of answers")
    p.add_argument("--target", default=".", help="the project's root (default: the current folder)")
    p.add_argument("--dry-run", action="store_true", help="print what would be done, write nothing")
    p.add_argument("--force", action="store_true", help="replace existing instruction files; records are kept")
    p.add_argument("--name")
    p.add_argument("--purpose", help="one line: what the project is, for whom")
    p.add_argument("--invariants", action="append", metavar="TEXT", help="repeatable: an invariant and what breaks")
    p.add_argument("--mode", choices=MODES)
    p.add_argument("--layout", choices=LAYOUTS, help="default: single")
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
    for key in ("spec", "plan", "glossary", "findings", "owner-notes", "checks", "prune-after", "docs-dir"):
        p.add_argument(f"--{key}")
    p.add_argument("--frozen", action="append", metavar="PATH", help="repeatable: a folder never edited")
    p.add_argument("--copies", action="append", metavar="PATH", help="repeatable: a generated or synced copy")
    for k in MACHINE_KEYS:
        p.add_argument(f"--machine-{k}")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"FAILED  the target {target} is not a folder", file=sys.stderr)
        return 2
    try:
        answers = load_answers(args)
    except AnswerError as ex:
        print(f"invalid answers: {ex}", file=sys.stderr)
        return 2
    return run(answers, target, args.dry_run, args.force)


if __name__ == "__main__":
    sys.exit(main())
