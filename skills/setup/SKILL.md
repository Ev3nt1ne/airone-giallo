---
name: setup
description: Install Airone Giallo into an existing project, once, from its root - ask the few questions a template cannot answer, then run the scaffold script. Load only when asked to set Airone Giallo up.
---

# Setting Airone Giallo up in a project

Run once, in the project's own session, from its workspace root. The skill carries the judgement (what to ask, what to
recommend, what to check); `scaffold.py` beside it carries the mechanics and writes the files. Nothing of this skill
is copied into the project: what stays there is what the script writes. Each rule carries its reason in italics.

## 1. Before asking anything

- **Start on a clean tree.** `git status` must be empty in the owner's repository before the dry run. Afterwards it
  shows exactly what the setup added, and `git stash -u` or a checkout undoes it. *An install mixed into uncommitted
  work cannot be reviewed or reverted on its own.*
- **Read the repository first, and ask only what it cannot answer.** Look for an existing `AGENTS.md`, `CLAUDE.md`,
  `.gitignore`, a docs folder, a specification, a plan, a glossary, a findings folder, folders kept frozen,
  generated or vendored copies, the owner's own notes, and the test and lint commands. Take the Claude Code version
  from `claude --version` and the model from the session's own environment. Put to the owner, as one list and not as
  questions, only what they must confirm or what changes an answer, one line each; details only when asked. *A question
  the repository answers costs the owner a turn and tells them the agent did not look, and a finding that changes
  nothing is one more line to read past.*
- **In the two-repository form the owner's folder moves, whole, into a new workspace, and the move is the setup's last
  act.** The workspace, `<folder>-nido` beside it, is a new private repository, and the folder becomes its public side,
  registered as a submodule where it is: one copy, with its ignored files (dependencies, `.env` files) kept. *A clone
  carries only committed files, and leaves a second copy beside the first that drifts from it unseen.* The whole setup
  runs in one session started in the owner's folder; the folder moves after the real run and the checks, with the
  owner's yes, by commands with absolute paths (§4). *A Claude Code session is bound to the folder it started in: moved
  in the middle of the setup, it has nowhere left to run.*
- **An existing `AGENTS.md`, `CLAUDE.md` or `.claude/CLAUDE.md` is read before anything is written**, and gets its own
  step before A1 (§2). *A project's instruction file holds rulings that exist nowhere else.*

## 2. The questions

Each question has a label: its group's letter, its place, and its name, as in `A1 · Name and purpose`. The groups are
A · The project, B · What is public, C · What the agent does alone, and what it asks, and D · Others, for what fits none
of them; they follow the order the answers rest on each other, and the skill names a question by its label's code. *The
cut can only place the files the tools add, and the rules on acting alone read what the cut made public.*

- **The first message holds only the opening findings** and, when the repository has an old instruction file, that
  file's step (below); no question of any group. *The findings and the old file are what the questions' proposals rest
  on; asked beside them, a question is answered before they are read.*
- **Each later message holds questions of one group only, never of two**, in the labels' order, and as many as the owner
  can read, understand and answer in one go. Weigh each question by how much there is to read, how hard it is to follow
  and how long it takes to answer: a demanding one comes alone, such as B1 with its ladder and its follow-ups, or C3
  with its candidates; light ones may come together, such as A3's machine to confirm and the handoff's stage name. There
  is no fixed number per message. Each question carries its label; no heading per group. *A message is answered at the
  pace of its hardest question, and one that mixes groups or stacks demanding questions comes back answered in part.*
- **Propose whenever the repository gives grounds, write only what the owner confirmed, and say plainly when there are
  no grounds.** A proposal says where it comes from (the README, the old instruction file, the folders, the repository's
  name); with no grounds, say so and ask. *A bare question costs the owner a draft the agent could have made, and a
  proposal written without the owner's yes is a decision nobody took.*
- **Say each question in three parts**: what it is, in one or two sentences; the options; the recommendation, with its
  reason in one line. An example only when the question cannot be understood without one. *A question the owner has to
  decode is answered a turn late or answered wrongly, and the answer is written into every file the script makes.*
- **A question left unanswered is reminded in one line at the end of the next message** (`Still open: A2 families`),
  never asked again in full. *A question restated every round buries the new ones under it.*

**The old instruction file, before A1.** When the repository has one, its step comes right after the opening findings:
in the first message, show the file's sections, one line each, with where each would go, and say what happens to the
file itself; the owner confirms or changes any line, once, and it is not asked again. Said to the owner, the frame
filled at each run from the file:

> Your existing CLAUDE.md. The setup replaces it with a one-line `@AGENTS.md`, and each part of it is carried to where
> Airone Giallo keeps that kind of thing.
>
> Your CLAUDE.md is backed up, unchanged, as `archive/CLAUDE-before-setup.md`.
>
> Here is where each part would go: [one line per section: "<section>" → <place>]. Confirm, or change any line.

In the two-repository form the first sentence says instead that the setup removes the file from the public folder after
backing it up in the workspace's archive. The places a line chooses from:

- `AGENTS.md`: rules for how agents work here;
- `docs/invariants.md`: rules the code depends on, as the file states them;
- `docs/`: what the system is, its architecture, layout, data model;
- `ai-docs/guides/`: how a thing is done here, its commands, its deploy steps;
- the status file or `plan/`: open work;
- `RATIONALE.md`: where a rule came from;
- dropped: what no longer holds, with why;
- elsewhere: a place the agent names, with why, for a part that fits none of these.

The parts placed in `docs/invariants.md` go into `invariants`, word for word, one paragraph each, and the script writes
them; every confirmed line goes into `carry` as said, and the session carries the other parts from the backup after the
run (§4). *A part left in a file no session loads is a ruling nobody reads.* Never place as an invariant what the file
does not state as one, such as a convention or a rule inferred from the code. *Finding new invariants is later work,
proposed one by one under the rule AGENTS.md gives; at setup it opens a discussion nobody asked for.*

Each answer has a name in the answers file (§3).

| Question | What it is | The options | Recommend, and why | What the answer changes |
|---|---|---|---|---|
| A1 · Name and purpose | The project's name, and what it is and for whom in one line, each asked on its own line with its label, so that a one-word answer fills exactly one | the **name** (`name`); the **purpose** (`purpose`) | drafts of both, taken from the README, the old instruction file or the repository's name and said with their source, for the owner to confirm or replace; where none gives grounds, say so and ask | the opening paragraph of AGENTS.md |
| A2 · Tools to add | Which tools to add to the project, each optional and chosen on its own | the specification graph (`graph`: `none`, `lite`, `full`); the status file (`status`, with its `families`, asked whenever the status file is chosen, as the paragraph on families below says); the handoff (`handoff`, with the first log's `stage`) | the status file and the handoff for any project worked over many sessions; the graph's `lite` profile once decisions and requirements rest on each other, `full` when evidence, checks and open questions need nodes too | the files written, the map's rows, the identifier families and the checks |
| A3 · This machine | This device: its resources, what else runs on it, the run limits, whether timings measured here count as results | one line each (`machine`: `resources`, `load`, `limits`, `timings`) | what the session can see (`nproc`, `free -h`, `df -h .`), for the owner to confirm: it is measured, not guessed | `local-machine.md`, git-ignored, one per device |
| B1 · What is public | Which rungs of the ladder are public, asked after the ladder's table below is shown and the cut explained; then where the owner's notes and the downloaded sources go, and in the two-repository form whether contributors get a short public instruction file | the highest public rung (`cut`: `none`, `docs`, `graph`, `plan`, `ai-docs`, `all`); each `private` or `public`, the owner's notes (`human_docs`) and the downloaded sources (`sources`); the agent layer (`agent_layer`: `private`, `both`) | `plan`: the system public, the work private; `private` for both elements; say what the repository already shows, such as a public remote or a licence | the form: `all` is one public repository, `none` one private repository, any other cut two, the public rungs in the submodule folder; where each file is written; the ladder rule and the map of AGENTS.md |
| C1 · How you work | How the owner works with the agent | **Conductor (directing)**: the owner directs, wants explanations and recommendations, seldom the technical detail; or **Four-Hands (pairing)**: the owner works beside the agent, judges every line, gives prototypes and directions (`mode`: `conductor`, `four-hands`) | no default: the repository cannot show how the owner works, so say so and ask, after describing both | Four-Hands adds the choices list after building, the scope rule, the tool-clash rule and the structure rule; Conductor adds the sentence on directions as leads to explore |
| C2 · What the agent sends out on your behalf | Pushes, tags, releases, issues, pull requests, comments, posts: whether the owner sees each before it goes out | **gated**, prepared as a branch or a draft for the owner to send, or **free**, done and reported, with an attribution trailer if they want one (`outward`, `attribution`) | `gated`: an act outside the repository cannot be taken back | the outward rule |
| C3 · Actions asked first | Actions the agent always stops and asks about before doing them. Say that the answer becomes one sentence in AGENTS.md | Propose candidates: actions found in the repository that can do damage, one line each with why. Do not propose an action that `session` §2 already leaves to the owner in every project (scope, priorities, cost, anything irreversible or public, a change to a recorded ruling); when a candidate is already covered by B1 or C2, say which, as the text below does. The owner keeps some by number, adds their own, or answers none (`reserved`) | the candidates the repository suggests; none is an answer too, and more are added as they surface | one sentence in the first rule on deciding |
| D1 · Opinionated rules | Whether the project takes the more opinionated, less general rules of Airone Giallo's author, as one block, asked as the paragraph on D1 below says | yes or no (`opinionated`) | no, unless the owner wants them: never assumed | the author's rules, appended to AGENTS.md under their own heading |

A family of the status file is a code of 2 to 5 capitals or digits starting with a capital, or two joined by a hyphen,
and a line saying what it covers. Declare one per area of the work (the application, the documentation), never one per
repository. *An item's family says what the work is about, and the work on one area often crosses both repositories.* A
family, once declared, keeps its meaning. *A code chosen in haste is cited for the life of the project.* When the status
file is chosen, even by an answer such as "all" to A2, ask for the families in their own question, after saying what a
family is: propose families from the areas of work found in the repository, one line each with its code, and write only
those the owner confirms; never take them from memory or from another project. *A family written without the owner's yes
reads as answered, so nobody checks it, and the script refuses a status file with none.*

Before asking B1, show the owner the ladder of `doc-discipline` §1 as this table, copied rather than paraphrased. *The
cut is a choice among these rungs, and the owner can only choose among what is in front of them.*

| Rung | Folder | What it holds |
|---|---|---|
| 1 | `docs/` | the specification, the glossary, studies, change notes: what the system is |
| 2 | `graph.yml` | the specification graph: requirements, decisions, assumptions, threats and their relations, checked by `specgraph` |
| 3 | `plan/` | phases, milestones, their order and status: what gets done when |
| 4 | `ai-docs/` | what agents write: the status file, the handoff, design notes, findings, guides |
| 5 | the workspace root | the agent layer, `AGENTS.md`, `CLAUDE.md`, `RATIONALE.md` and the project's skills: how sessions are run |

Then explain the cut in two sentences: the cut names the highest rung that is public, so it and every rung below it
are public and every rung above it is private. `none` keeps everything private, `plan` makes the specification, the
graph and the plan public and keeps the agents' documents and the instruction files private, and `all` makes
everything public. A rung cites only rungs at or below it, so one cut is enough. *One cut instead of a side per
document keeps every public text free of links into the private side.* A doubtful rung starts private: *a file moved
from public to private keeps its public history.* The archive is beside the ladder and has no side to answer: each
repository gets its own, `archive/` at its top, so an archived document stays on the side it was on. With `cut: all`
the agent layer is public and RATIONALE.md drops the owner's words from its form; `agent_layer: both` keeps the full
layer private and adds a contributors' `AGENTS.md` that cites only public rungs.

C3 is said to the owner as written here, the bracket filled at each run with the candidates found in the repository:
"Actions I always ask you about first. You already decided which parts of the repository are public (B1), and what I may
send out under your name (C2). Here you can name actions in this repository that I must never take on my own; your list
becomes one line in AGENTS.md. From the repository, these look worth naming: [the candidates, one line each with why;
when one is already covered by an earlier answer, say which]. Keep any by number, add your own, or answer none." *An
owner who is not told what reserving does, and what earlier answers already cover, cannot tell a new candidate from one
already decided.*

**D1 is a closed box.** Ask it as one yes or no, in words such as "Do you want Airone Giallo's author's more
opinionated, less general rules for this project?", without describing what the rules say or how many there are. *The
layer is the author's and may change; a question that summarised it would drift from it, and the owner would answer the
summary.*

**The answers no question asks.** The facts of §1 go in as `spec`, `plan`, `glossary`, `findings` (each a path or a
short phrase, written into the map as given; a path is written from the workspace root and in backticks, as the defaults
are, `` `<name>/docs/spec.md` ``), `owner_notes`, `frozen`, `copies`, `checks` (the project's own test and lint
commands) and `prune_after` (how long a rule may go unneeded); `spec`, `plan`, `glossary` and `findings` default to the
tree's own paths, and `public_dir` to the name in lower case. Anything not answered is written as a visible
`[to fill: …]` slot, never guessed. The invariants leave no slot: without any, `docs/invariants.md` says none is
recorded yet, and AGENTS.md has the agent propose one when the work shows it. *An invariant is found by the work that
depends on it; one demanded on the first day is a guess, written into the file every session reads.*

## 3. Running the script

Write the answers as one JSON object to a file in the session's scratch folder, not in the project:

```json
{"name": "Larder", "purpose": "a recipe book for people who cook for others, with what each dish contains",
 "mode": "conductor", "cut": "plan", "graph": "lite",
 "families": {"APP": "the application", "DOC": "the documentation"}, "outward": "gated",
 "claude_code_version": "<from claude --version>", "model": "<the session's model>",
 "machine": {"resources": "8 cores, 16 GB", "load": "nothing else", "limits": "one run at a time", "timings": "yes"}}
```

In the two-repository form add `move_from`, the owner's folder. Then run the script, in four steps, with `--target` the
workspace root: the project in the one-repository form; in the two-repository form `<folder>-nido`, beside the folder.
Both runs find the folder where it is: the real run writes the public side into it there, and the workspace's files into
`<folder>-nido`, as they must be once the folder has moved in:

1. The dry run, which writes nothing. Its first line says so; in the two-repository form the move, done last, and the
   new workspace follow, each a short line with its explanation below it. Then each repository has its own section, the
   owner's first: the files it already has, each line starting with what the real run does to it (`BACKUP`, `REPLACE`,
   `APPEND`, `REMOVE`, `KEEP`), and the new files, `CREATE`, grouped by folder. Last, in a section of its own, the lines
   of `carry`, which the session carries over after the run:

   ```sh
   python3 <airone-giallo>/skills/setup/scaffold.py --answers ANSWERS.json --target <root> --dry-run
   ```

2. Show the owner the dry run's list as it printed, and end the turn there: the real run waits for the owner's
   word and never runs in the same turn as the dry run. *The preview is where a wrong answer costs nothing, and only
   if the owner reads it before anything is written.* An answer the owner changes goes into ANSWERS.json, and the
   dry run is shown again.
3. In the two-repository form, with the owner's yes, the workspace: `git init <folder>-nido`, beside the folder. *The
   real run writes into it; the folder itself moves only at the end (§4).*
4. With the owner's word, the real run, which lists every file by the same sections, with what happened to it first:
   `DONE`, `KEPT`, `SKIPPED` or `FAILED`. *Before the run the question is what will be done, after it whether it was.*

   ```sh
   python3 <airone-giallo>/skills/setup/scaffold.py --answers ANSWERS.json --target <root>
   ```

What it writes, the dry run lists file by file: at the workspace root the agent layer (`AGENTS.md`, `CLAUDE.md`,
`RATIONALE.md`, the git-ignored `local-machine.md`) and the `.gitignore`, an allowlist in the two-repository form; at
the top of each repository `.ignore` with `archive/`, `archive/README.md` and the archive's log `archive/LOG.md`; on
each rung's side `ai-docs/` with the status file, the handoff (a first state written from the answers, a first log
with no entry yet) and a README for each of its places, a README in `docs/` and in `plan/` when the folder is new,
`docs/glossary.md` when absent and no other glossary is answered, `docs/invariants.md` when absent, and `graph.yml`;
`human-docs/README.md` and the `sources/README.md` manifest on their chosen sides; and for each old instruction file of
the owner's repository its backup in the workspace's archive, then the file replaced by the setup's own or removed.

`--help` lists every answer as a flag; a flag overrides the file.

- **The graph step needs the `specgraph` command.** The script runs `specgraph init` from the PATH, and only when no
  command is there `python -m specgraph init` with its own interpreter, if the module is importable there; with
  neither it reports the step SKIPPED with the install command, and exits 1. Ask the owner to install it; do not work
  around it. *A tool installer puts the command on the PATH and keeps the module out of every other Python, so the
  command is the one looked for first.*
- **The exit code is the report.** 0: every step done or kept. 1: a step was refused, skipped or failed, each named
  in the report. 2: the answers are invalid. *A setup that says "done" over a step it skipped is the failure this
  script exists to prevent.*
- **An old instruction file of the owner's repository is backed up, then replaced or removed.** Each `AGENTS.md`,
  `CLAUDE.md` and `.claude/CLAUDE.md` there is copied into the workspace's archive as `archive/<NAME>-before-setup.md`,
  a name no tool loads, with only the `archived:` stamp the archive requires added; the copy is read back and compared
  with the original before the file is replaced by the setup's own or removed, and a copy that differs leaves the file
  as it was and fails the step. A backup of that name already there stops the run, even with `--force`. *Once the file
  is replaced the backup is the only copy of the original, and a copy nobody compared is the one that is lost.*
- **Any other existing file stops the whole run before anything is written.** `--force` replaces the other instruction
  files (the machine file, the workspace's own AGENTS.md and CLAUDE.md, the workspace's allowlist `.gitignore`); a
  record (RATIONALE.md, the status file, the closed file, the handoff, the archive's log, the graph file, the folders'
  READMEs, the invariants file) is never replaced, even then, and is reported KEPT. An existing `docs/` or `plan/` gets
  no index and only the files it lacks (the glossary, the invariants file), which changes none of its own; `.ignore` and
  a one-repository `.gitignore` only get the lines they lack. *An empty status file written over a full one deletes the
  project's history.* A project's own `docs/invariants.md` is loaded as it is, so invariants carried over from its old
  instruction file stop the run: add them to that file with the owner, and leave `invariants` empty. *The script never
  writes into a file of the project's, and paragraphs it dropped would be lost unseen.*

The templates in `templates/` use the syntax the script implements: `{{name}}` is a value, `{{#name}}…{{/name}}`
keeps its body when the answer is true or non-empty, `{{^name}}…{{/name}}` when it is false or empty; a tag alone on a
line takes the line with it. A slot with no answer stops the script, so a template and its answers cannot drift apart
unnoticed. `templates/tree/` mirrors the folders the script writes. To change what a project gets, edit the template
and the answer it reads, with a test.

## 4. After the script

First, with an old instruction file, carry each part from its backup to the place its line in `carry` names, in that
document's own form (the frontmatter of `markdown-docs`, the status file's identifiers), and leave out what was
confirmed dropped; the parts placed in `docs/invariants.md` are already there. The setup is not done before every line
is carried; each line's part carried, delete that line from the handoff's next step, where the script wrote them all.
*The backup keeps the content, but a part nobody carries is a ruling no session reads, and the handoff tells a session
that opens before the end what is left.*

The checks are Airone Giallo's installed commands, never copies in the project: `uv tool install ./graph` and
`uv tool install ./tools`, from the clone or from the plugin's copy of it, give `specgraph`, `check-status`,
`check-archive`, `check-links` and `check-frontmatter`, with the tools' other commands; `pipx install` takes the same
arguments, and `pip install` works inside a project's own venv. Ask the owner to install them. *A copied script
is a second copy that the next version does not reach.* The two document checks read the tracked tree, so first
stage what the script wrote, `git add` in each repository it wrote into; staging is undone by `git reset`. Run each
check and read its output; the script's report is a claim, these measure the files. In the two-repository form the
folder is still at its own path while they run: a public path written `<name>/…` below is in the folder, which is the
session's own, and a workspace command runs from `<folder>-nido` (`cd <folder>-nido && …`, or the check's `--root`). The
one check that needs the folder inside the workspace, the links across both repositories, runs with the move (below).

1. With the graph: `specgraph lint` reports 0 errors; in the two-repository form, with the graph public, it runs in the
   folder, where `graph.yml` is.
2. With the status file: `check-status ai-docs/status.md ai-docs/closed.md`, adding `--graph` and the graph's path
   with the graph, reports 0 errors and prints the first free ID of each family.
3. `check-archive` reports 0 errors; in the two-repository form `check-archive` in the folder for the public
   repository's own archive, and `check-archive --archive <folder>-nido/archive` for the workspace's, which holds the
   backup.
4. `check-links --cut <cut>` reports 0 errors; in the two-repository form `check-links` in the folder, which holds the
   public repository on its own, and after the move `check-links --root <folder>-nido --public <name> --cut <cut>`,
   which walks both and holds each side to the cut.
5. `check-frontmatter --all` reports 0 errors; in the two-repository form in each repository, `--root <folder>-nido` for
   the workspace.
6. `git check-ignore local-machine.md` prints the file's name (`git -C <folder>-nido` in the two-repository form, whose
   `git status` after the move's commit is clean).
7. With the handoff, replace the **Checks** line of its state with what steps 1 to 6 reported, each result beside its
   command. *The script writes the state before any check runs, so it says they have not run; only the agent that ran
   them can record what they measured.*
8. `grep -n 'to fill' AGENTS.md local-machine.md`, adding the handoff's state at its path in the map and, with
   `agent_layer: both`, the contributors' `<name>/AGENTS.md`, lists the slots left; give them to the owner as one
   list. *Name the files: an agent's shell may wrap `grep` in a search that skips what git ignores, and
   `local-machine.md` is ignored.*
9. Read the written AGENTS.md and `docs/invariants.md` whole with the owner. *They will be bound by them; the first
   reading is theirs.*

Then, in either mode, list for the owner the choices the setup made that they did not: how something was numbered or
named, where a document's content was placed, a wording carried over or changed, what of an old file was dropped; each
with its why where it is not obvious, and each a choice until the owner confirms it. *The owner confirmed the answers,
not what the agent made of them, and a choice nobody lists is a decision nobody took.*

Then propose a local commit of what was installed, by the project's own commit rules: in the two-repository form one in
the public repository first, in the folder, and the workspace's after the move, with the updated gitlink, *so the
gitlink names a commit that exists.* The public commit removes the old instruction file; its earlier versions stay in
that repository's history, which the owner should know before anything is pushed. Anything outward follows the answer to
C2.

**In the two-repository form the move comes last**, with the owner's yes, once the checks, the choices and the public
commit are done. Before the yes, say plainly that the folder's path changes from `<folder>` to `<folder>-nido/<folder>`,
that the editor, scripts and Claude Code's per-path memory do not follow, and that moving the folder back undoes it.
Then, with absolute paths only (`<dir>` the folder's parent), since the session's own folder is the one that moves:

```sh
mv <dir>/<folder> <dir>/<folder>-nido/<folder>
git -C <dir>/<folder>-nido submodule add <its remote URL, or ./<folder> without one> <folder>
check-links --root <dir>/<folder>-nido --public <folder> --cut <cut>
git -C <dir>/<folder>-nido add -A
git -C <dir>/<folder>-nido commit -m "Install Airone Giallo; add <folder> as a submodule"
git -C <dir>/<folder>-nido status --short
```

`git submodule add` on a path that already holds a repository adopts it where it is ("Adding existing repo"); never
`git submodule absorbgitdirs`, which moves the folder's `.git` into the workspace. *With its `.git` inside, the folder
is still a repository of its own, so moving it back undoes the move.* A link check that reports errors stops there,
before the commit, and the errors go to the owner. Nothing after these commands needs the session: close by giving the
owner the new path, `<folder>-nido/<folder>`, and telling them to open the next session at `<folder>-nido`. *The editor,
scripts and Claude Code's per-path memory still point at the old path, where nothing is left.*

## 5. What the script does not do

It runs no `git submodule` and no other git command that changes anything, commits nothing, moves no folder (the
two-repository move is the session's, with the owner's yes), deletes nothing but an old instruction file of the owner's
repository once its backup has been read back equal to it, and copies no script into the project; it writes no hook and
no CI workflow (the lines a project copies into its own are in Airone Giallo's `tools/README.md`), and it carries no
document's content into the tree: that is a session's work with the owner, file by file. Not done yet: injecting the
agent layer into the public checkout, several public folders under one workspace, and `.git/info/exclude` in place of a
visible ignore block.
