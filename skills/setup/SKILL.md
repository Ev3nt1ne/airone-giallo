---
name: setup
description: Install Airone Giallo into an existing project, once, from its root - ask the few questions a template cannot answer, then run the scaffold script. Load only when asked to set the kit up.
---

# Setting the kit up in a project

Run once, in the project's own session, from its workspace root. The skill carries the judgement (what to ask, what to
recommend, what to check); `scaffold.py` beside it carries the mechanics and writes the files. Nothing of this skill
is copied into the project: what stays there is what the script writes. Each rule carries its reason in italics.

## 1. Before asking anything

- **Start on a clean tree.** `git status` must be empty in every repository the setup writes into: the project in the
  one-repository form; the workspace and the public repository in the two-repository form, which they are once the
  submodule's addition below is committed. Afterwards it shows exactly what the setup added, and `git stash -u` or a
  checkout undoes it. *An install mixed into uncommitted work cannot be reviewed or reverted on its own.*
- **Read the repository first, and ask only what it cannot answer.** Look for an existing `AGENTS.md`, `CLAUDE.md`,
  `.gitignore`, a docs folder, a specification, a plan, a glossary, a findings folder, folders kept frozen,
  generated or vendored copies, the owner's own notes, and the test and lint commands. Take the Claude Code version
  from `claude --version` and the model from the session's own environment. Put what you found to the owner as one
  list to confirm, not as questions. *A question the repository answers costs the owner a turn and tells them the
  agent did not look.*
- **In the two-repository form, build the workspace before the setup, in this order, with the owner's go.**
  1. `git init <name>-nido`, beside the project or wherever the owner keeps it, then work inside it. *The workspace is
     the private repository; the project becomes one folder in it.*
  2. Add the project as a submodule named after it: `git submodule add <its remote URL> <name>`, or, when it has no
     remote yet, `git -c protocol.file.allow=always submodule add <its absolute path> <name>`. *Git refuses the file
     transport by default; the option lifts it for that one command only.*
  3. Commit the addition: `git commit -m "Add <name> as a submodule"`. *The setup then starts on a clean tree, and
     the gitlink it later moves names a commit that exists.*

  The submodule is a second clone of the project: from then on the work continues in `<name>-nido/<name>/`, and the
  original checkout is left or removed as the owner prefers. *Two working copies of one repository drift apart unless
  one is retired.* The script checks that the folder is a git work tree of its own declared in `.gitmodules`, and
  refuses otherwise. *The submodule records which public commit the private documents refer to; a plain copy would
  drift from them unseen.*
- **An existing `AGENTS.md` or `CLAUDE.md` is read before anything is written.** The script refuses to replace one
  without `--force`; with the owner, decide what of it moves into the new file or into RATIONALE.md first. *A
  project's instruction file holds rulings that exist nowhere else.*

## 2. The questions, in order

Ask in rounds of one to four, never as one long questionnaire, and explain each choice before asking it. Each answer
has a name in the answers file (§3).

| # | Question | Recommend | What the answer changes |
|---|---|---|---|
| 1 | The project's name, what it is and for whom in one line, and its invariants: what breaks silently if each is violated, each written as one clause, the invariant then what breaks (`X, else Y`), since the list is read as one sentence (`name`, `purpose`, `invariants`) | the invariants now, even one; they may be left as a slot | the opening paragraph of AGENTS.md |
| 2 | How the owner works: **Conductor (directing)**: the owner directs, wants explanations and recommendations, seldom the technical detail; or **Four-Hands (pairing)**: the owner works beside the agent, judges every line, gives prototypes and directions (`mode`: `conductor`, `four-hands`) | no default: ask, after describing both | Four-Hands adds the choices list after building, the scope rule, the tool-clash rule and the structure rule; Conductor adds the sentence on directions as leads to explore |
| 3 | The cut: the last rung of the ladder that is public (`cut`: `none`, `docs`, `graph`, `plan`, `ai-docs`, `archive`, `all`); then, each `private` or `public`, the owner's notes (`human_docs`) and the downloaded sources (`sources`), and in the two-repository form whether contributors get a short public instruction file (`agent_layer`: `private`, `both`) | `plan`: the system public, the work private; `private` for both elements | the form: `all` is one public repository, `none` one private repository, any other cut two, the public rungs in the submodule folder; where each file is written; the ladder rule and the map of AGENTS.md |
| 4 | Which pieces: the specification graph (`graph`: `none`, `lite`, `full`), the status file (`status`, with its `families`), the handoff (`handoff`, with the first log's `stage`) | the status file and the handoff for any project worked over many sessions; the graph's `lite` profile once decisions and requirements rest on each other, `full` when evidence, checks and open questions need nodes too | the files written, the map's rows, the identifier families and the checks |
| 5 | Outward acts (pushes, tags, releases, issues, pull requests, comments, posts): **gated**, prepared as a branch or a draft for the owner to send, or **free**, done and reported, with an attribution trailer if they want one (`outward`, `attribution`) | `gated` | the outward rule |
| 6 | Decisions the owner reserves beyond the project decisions of `session` §2 (`reserved`) | none to start; add as they surface | one sentence in the first rule on deciding |
| 7 | This machine: its resources, what else runs on it, the run limits, whether timings measured here count as results (`machine`) | fill what the session can see (`nproc`, `free -h`, `df -h .`) and have the owner confirm | `local-machine.md`, git-ignored, one per device |
| 8 | The kit author's opinionated layer: comments state invariants (Four-Hands only), every fix has a test, irreversible acts offered as such (`opinionated`) | off; offer it, never assume it | the rules appended under their own heading: three for Four-Hands, two for Conductor |

The ladder is `doc-discipline` §1: 1 `docs/`, 2 `graph.yml`, 3 `plan/`, 4 `ai-docs/`, 5 `archive/`, 6 the agent
layer; each rung cites only rungs at or below it, so every rung at or below the cut is public and every rung above it
private. *One cut instead of a side per document keeps every public text free of links into the private side.* A
doubtful rung starts private: *a file moved from public to private keeps its public history.* With `cut: all` the
agent layer is public and RATIONALE.md drops the owner's words from its form; `agent_layer: both` keeps the full
layer private and adds a contributors' `AGENTS.md` that cites only public rungs.

A family of the status file is a code of 2 to 5 capitals or digits starting with a capital, or two joined by a hyphen,
and a line saying what it covers. Declare one per area of the work (the application, the documentation), never one per
repository. *An item's family says what the work is about, and the work on one area often crosses both repositories.* A
family, once declared, keeps its meaning. *A code chosen in haste is cited for the life of the project.* The facts of §1
go in as `spec`, `plan`, `glossary`, `findings` (each a path or a short phrase, written into the map as given; a path is
written from the workspace root and in backticks, as the defaults are, `` `<name>/docs/spec.md` ``), `owner_notes`,
`frozen`, `copies`, `checks` (the project's own test and lint commands) and `prune_after` (how long a rule may go
unneeded); `spec`, `plan`, `glossary` and `findings` default to the tree's own paths, and `public_dir` to the name in
lower case. Anything not answered is written as a visible `[to fill: …]` slot, never guessed.

## 3. Running the script

Write the answers as one JSON object to a file in the session's scratch folder, not in the project:

```json
{"name": "Inkwell", "purpose": "a note editor whose saved notes survive a crash, for people who write offline",
 "invariants": ["a saved note survives a crash, else notes are lost silently"], "mode": "conductor",
 "cut": "plan", "graph": "lite", "families": {"APP": "the application", "DOC": "the documentation"},
 "outward": "gated", "claude_code_version": "<from claude --version>", "model": "<the session's model>",
 "machine": {"resources": "8 cores, 16 GB", "load": "nothing else", "limits": "one run at a time", "timings": "yes"}}
```

Then, from the workspace root (the private repository in the two-repository form), preview and run:

```sh
python3 <kit>/skills/setup/scaffold.py --answers ANSWERS.json --dry-run
python3 <kit>/skills/setup/scaffold.py --answers ANSWERS.json
```

What it writes, the dry run lists file by file: at the workspace root the agent layer (`AGENTS.md`, `CLAUDE.md`,
`RATIONALE.md`, the git-ignored `local-machine.md`), `.ignore` with `archive/` and the `.gitignore`, an allowlist
in the two-repository form; on each rung's side `ai-docs/` with the status file, the handoff and a README for each
of its places, `archive/README.md` and the archive's log `archive/LOG.md`, a README in `docs/` and in `plan/` when the
folder is new, `docs/glossary.md` when absent and no other glossary is answered, and `graph.yml`;
`human-docs/README.md` and the `sources/README.md` manifest on their chosen sides.

`--help` lists every answer as a flag; a flag overrides the file. Show the owner the dry run before the real
one. *The preview is where a wrong answer costs nothing.*

- **Run the graph step with the Python that has `specgraph`.** The script calls `python -m specgraph init` with its
  own interpreter, and only when `specgraph` is importable there; otherwise it reports the step SKIPPED with the
  install command, and exits 1. Ask the owner to install it; do not work around it.
- **The exit code is the report.** 0: every step done or kept. 1: a step was refused, skipped or failed, each named
  in the report. 2: the answers are invalid. *A setup that says "done" over a step it skipped is the failure this
  script exists to prevent.*
- **An existing file stops the whole run before anything is written.** `--force` replaces the instruction files
  (AGENTS.md, CLAUDE.md, the machine file, the contributors' files, the workspace's allowlist `.gitignore`); a record
  (RATIONALE.md, the status file, the closed file, the handoff, the archive's log, the graph file, the folders'
  READMEs) is never replaced, even then, and is reported KEPT. An existing `docs/` or `plan/` gets no index and only
  the files it lacks (the glossary), which changes none of its own; `.ignore` and a one-repository `.gitignore` only
  get the lines they lack. *An empty status file written over a full one deletes the project's history.*

The templates in `templates/` use the syntax the script implements: `{{name}}` is a value, `{{#name}}…{{/name}}`
keeps its body when the answer is true or non-empty, `{{^name}}…{{/name}}` when it is false or empty; a tag alone on a
line takes the line with it. A slot with no answer stops the script, so a template and its answers cannot drift apart
unnoticed. `templates/tree/` mirrors the folders the script writes. To change what a project gets, edit the template
and the answer it reads, with a test.

## 4. After the script

The checks are the kit's installed commands, never copies in the project: `pip install ./graph ./status ./archive`
from the kit, or from the plugin's copy of it, gives `specgraph`, `check-status` and `check-archive`. Ask the owner to
install them. *A copied script is a second copy that the kit's next version does not reach.* Run each check and read
its output; the script's report is a claim, these measure the files.

1. With the graph: `specgraph lint` reports 0 errors (`--graph <name>/graph.yml` when the graph is public in the
   two-repository form).
2. With the status file: `check-status ai-docs/status.md ai-docs/closed.md`, adding `--graph` and the graph's path
   with the graph, reports 0 errors and prints the first free ID of each family.
3. `check-archive` (`--archive <name>/archive` when the archive is public in the two-repository form) reports 0
   errors.
4. The dead-link check of `markdown-docs` §6, run from the workspace root so that it walks the public folder too,
   prints nothing.
5. `git check-ignore local-machine.md` prints the file's name; in the two-repository form `git status` at the root
   lists only the files the allowlist names and the public folder.
6. `grep -n 'to fill' AGENTS.md local-machine.md` lists the slots left; give them to the owner as one list.
7. Read the written AGENTS.md whole with the owner. *They will be bound by it; the first reading is theirs.*

Then propose a local commit of what was installed, by the project's own commit rules: in the two-repository form one
in the public repository first, then one in the private workspace with the updated gitlink, *so the gitlink names a
commit that exists.* Anything outward follows the answer to question 5.

## 5. What the script does not do

It runs no `git submodule` and no other git command that changes anything, commits nothing, deletes nothing and
copies no script into the project; it writes no hook and no CI workflow (that is the job of the kit's tools piece),
and it moves no existing document into the tree: that is a session's work with the owner, file by file. Not done
yet: injecting the agent layer into the public checkout, several public folders under one workspace, and
`.git/info/exclude` in place of a visible ignore block.
