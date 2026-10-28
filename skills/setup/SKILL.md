---
name: setup
description: Install Airone Giallo into an existing project, once, from its root - ask the few questions a template cannot answer, then run the scaffold script. Load only when asked to set the kit up.
---

# Setting the kit up in a project

Run once, in the project's own session, from its root. The skill carries the judgement (what to ask, what to
recommend, what to check); `scaffold.py` beside it carries the mechanics and writes the files. Nothing of this skill
is copied into the project: what stays there is what the script writes. Each rule carries its reason in italics.

## 1. Before asking anything

- **Start on a clean tree.** `git status` must be empty, so that afterwards it shows exactly what the setup added and
  `git stash -u` or a checkout undoes it. *An install mixed into uncommitted work cannot be reviewed or reverted on
  its own.*
- **Read the repository first, and ask only what it cannot answer.** Look for an existing `AGENTS.md`, `CLAUDE.md`,
  `.gitignore`, a docs folder, a specification, a plan, a glossary, a findings folder, folders kept frozen,
  generated or vendored copies, the owner's own notes, and the test and lint commands. Take the Claude Code version
  from `claude --version` and the model from the session's own environment. Put what you found to the owner as one
  list to confirm, not as questions. *A question the repository answers costs the owner a turn and tells them the
  agent did not look.*
- **An existing `AGENTS.md` or `CLAUDE.md` is read before anything is written.** The script refuses to replace one
  without `--force`; with the owner, decide what of it moves into the new file or into RATIONALE.md first. *A
  project's instruction file holds rulings that exist nowhere else.*

## 2. The questions, in order

Ask in rounds of one to four, never as one long questionnaire, and explain each choice before asking it. Each answer
has a name in the answers file (§3).

| # | Question | Recommend | What the answer changes |
|---|---|---|---|
| 1 | The project's name, what it is and for whom in one line, and its invariants: what breaks silently if each is violated (`name`, `purpose`, `invariants`) | the invariants now, even one; they may be left as a slot | the opening paragraph of AGENTS.md |
| 2 | How the owner works: **hands-off** (directs, wants explanations and recommendations, seldom the technical detail) or **hands-on** (codes, judges every line, gives prototypes) (`mode`) | no default: ask, after describing both | hands-on adds the choices list after building, the scope rule, the tool-clash rule and the structure rule; hands-off adds the sentence on directions as leads to explore |
| 3 | One repository, or an umbrella with public parts (`layout`: `single`, `umbrella`) | `single` unless public parts already exist | `umbrella` adds the rule that each document gets its side, public or private, before it is written, and marks RATIONALE.md as private |
| 4 | Which pieces: the specification graph (`graph`: `none`, `lite`, `full`), the register (`register`, with its `families`), the handoff (`handoff`, with the first log's `stage`) | the register and the handoff for any project worked over many sessions; the graph's `lite` profile once decisions and requirements rest on each other, `full` when evidence, checks and open questions need nodes too | the files written, the map's rows, the identifier families and the checks |
| 5 | Outward acts (pushes, tags, releases, issues, pull requests, comments, posts): **gated**, prepared as a branch or a draft for the owner to send, or **free**, done and reported, with an attribution trailer if they want one (`outward`, `attribution`) | `gated` | the outward rule |
| 6 | Decisions the owner reserves beyond the project decisions of `session` §2 (`reserved`) | none to start; add as they surface | one sentence in the first rule on deciding |
| 7 | This machine: its resources, what else runs on it, the run limits, whether timings measured here count as results (`machine`) | fill what the session can see (`nproc`, `free -h`, `df -h .`) and have the owner confirm | `local-machine.md`, git-ignored, one per device |
| 8 | The kit author's opinionated layer: comments state invariants (hands-on only), every fix has a test, irreversible acts offered as such (`opinionated`) | off; offer it, never assume it | the rules appended under their own heading: three for hands-on, two for hands-off |

A register family is a code of 2 to 5 capitals or digits starting with a capital, or two joined by a hyphen, and a
line saying what it covers; start with one per repository or area, since a family, once declared, keeps its meaning.
*A code chosen in haste is cited for the life of the project.* The facts of §1 go in as `spec`, `plan`, `glossary`,
`findings` (each a path or a short phrase, written into the map as given), `owner_notes`, `frozen`, `copies`,
`checks` (the project's own test and lint commands) and `prune_after` (how long a rule may go unneeded). Anything not
answered is written as a visible `[to fill: …]` slot, never guessed.

## 3. Running the script

Write the answers as one JSON object to a file in the session's scratch folder, not in the project:

```json
{"name": "Inkwell", "purpose": "a note editor whose saved notes survive a crash, for people who write offline",
 "invariants": ["a saved note survives a crash: otherwise silent data loss"], "mode": "hands-off",
 "graph": "lite", "families": {"APP": "the application", "DOC": "the documentation"},
 "outward": "gated", "claude_code_version": "<from claude --version>", "model": "<the session's model>",
 "machine": {"resources": "8 cores, 16 GB", "load": "nothing else", "limits": "one run at a time", "timings": "yes"}}
```

Then, from the project's root, preview and run:

```sh
python3 <kit>/skills/setup/scaffold.py --answers ANSWERS.json --dry-run
python3 <kit>/skills/setup/scaffold.py --answers ANSWERS.json
```

`--help` lists every answer as a flag; a flag overrides the file. Show the owner the dry run before the real
one. *The preview is where a wrong answer costs nothing.*

- **Run the graph step with the Python that has `specgraph`.** The script calls `python -m specgraph init` with its
  own interpreter, and only when `specgraph` is importable there; otherwise it reports the step SKIPPED with the
  install command, and exits 1. Ask the owner to install it; do not work around it.
- **The exit code is the report.** 0: every step done or kept. 1: a step was refused, skipped or failed, each named
  in the report. 2: the answers are invalid. *A setup that says "done" over a step it skipped is the failure this
  script exists to prevent.*
- **An existing file stops the whole run before anything is written.** `--force` replaces the instruction files
  (AGENTS.md, CLAUDE.md, the machine file, the checker); a record (RATIONALE.md, the register, the closed file, the
  handoff, the registry) is never replaced, even then, and is reported KEPT. *An empty register written over a full
  one deletes the project's history.*

## 4. After the script

Run each check and read its output; the script's report is a claim, these measure the files.

1. With the graph: `specgraph lint` reports 0 errors.
2. With the register: `python3 tools/check_register.py <docs>/register.md <docs>/closed.md`, adding
   `--graph registry.yml` with the graph, reports 0 errors and prints the first free ID of each family.
3. The dead-link check of `markdown-docs` §6 prints nothing.
4. `git check-ignore local-machine.md` prints the file's name.
5. `grep -n 'to fill' AGENTS.md local-machine.md` lists the slots left; give them to the owner as one list.
6. Read the written AGENTS.md whole with the owner. *They will be bound by it; the first reading is theirs.*

Then propose one local commit of what was installed, by the project's own commit rules; anything outward follows the
answer to question 5.

## 5. What the script does not do

It writes no hook and no CI workflow (that is the job of the kit's tools piece), and none of the umbrella's machinery: the private
repository's allowlist `.gitignore`, the propagation of shared files into the public parts and its refusals. For an
umbrella, the setup writes the rule on sides and leaves the repositories as they are. It never commits, and never
deletes a file.

## Adapting this to your project

Fixed: the questions are asked, never answered by the agent alone; the repository is read before the owner is asked;
the dry run before the run; nothing replaced without `--force`, and no record replaced at all; the exit code follows
the report; the checks of §4 run after.

Slots: the templates in `templates/`, in the syntax the script implements: `{{name}}` is a value, `{{#name}}…{{/name}}`
keeps its body when the answer is true or non-empty, `{{^name}}…{{/name}}` when it is false or empty; a tag alone on a
line takes the line with it. A slot with no answer stops the script, so a template and its answers cannot drift apart
unnoticed. To change what a project gets, edit the template and the answer it reads, with a test.

Evolving: a question is added when a project needed something the template could not guess, with the failure written
in the kit's history; a rule enters the AGENTS template only when no skill can carry it. *The file every session
loads is the most expensive place for a rule.*
