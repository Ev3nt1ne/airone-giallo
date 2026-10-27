---
name: orient
description: Which document answers which question, how an identifier resolves, where the frontier is. Load when opening a repository cold, or asked where something is or what is next.
---

# Finding your way around a project

A long project's documents run to thousands of lines, cite each other by identifier, and would fill most of a
context window if read whole. This skill is the index in between. It is a **template**: §1 to §5 hold for any
project; §6 is the project's map, filled in the project's own copy of this skill. Until §6 is filled, the skill
knows the method and nothing about the repository. A filled map for an invented project, with a walk through it, is
in [references/worked-example.md](references/worked-example.md). Each rule carries its reason in italics.

## 1. Address by identifier, not by file name

Where the project names its statements and work items with identifiers, each one resolves to exactly one defining
place. **Grep the identifier; do not read the file.** *Finding a definition by reading the document that holds it
spends ten thousand tokens on one sentence.*

- The registry's `where:` (or the project's equivalent) says where a statement lives now. It is an attribute, not
  an authority, and it can lag a renumbered section.
- Two families that look alike can name different things, typically statements and work items. §6 says which is
  which; never guess from the prefix.

## 2. The reading ladder

Cheapest first; **stop at the step that answers the question.**

| Step | Do this | Cost |
|---|---|---|
| 1 | the registry line: `grep -n 'REQ-04' registry.yml`, or with the specification graph (`graph/` in this kit) `specgraph show REQ-04` | almost nothing |
| 2 | every site that cites it: `grep -rn 'REQ-04' DOCS` | a few hundred tokens |
| 3 | one file's section map, `grep -n '^#' DOCS/design.md`, then one section, `sed -n '120,168p' DOCS/design.md` | about a thousand |
| 4 | the whole document | tens of thousands |

Step 1 is the one skipped. *A registry statement is a deliberately one-sentence form of the proposition; if it
answers the question, the long document has nothing to add.* For a subject rather than an identifier, the index
steps of `markdown-docs` §2 come first.

## 3. The frontier: read it, never assume it

Where the project stands is in the handoff's state (`handoff`), checked against the repository: the latest
commits, the checks, the tests. *A frontier recalled from an earlier session is the one most confidently wrong.*

- Each stage's status is in the map; each work item's marker is in the detail.
- **A stage with every work item done can still be open.** Stages close at their gates, not at their last task.
  Check the gate before calling anything finished.

## 4. Records, submissions and the normative text

- The specification is normative. Handoffs, logs and review worksheets are process records: when one disagrees with
  the specification, the specification wins, and the disagreement is a finding to report.
- **An agent's recommendation that the owner has not ratified is a submission, not a record.** Asked what such a
  report decided, the honest answer is that it decided nothing: it recommended. *A self-graded report read as a
  record turns an agent's opinion into the project's position.* The `adversary` skill exists to attack this
  material.

## 5. Things that trip a cold session

- **A frozen folder is never edited.** It may use older identifier forms; a mapping note at its top translates them.
- **A retired name stays retired.** Do not reintroduce an identifier form or a name that was changed to end a
  collision.
- **A derived copy is never edited.** Where installed copies are generated from a tracked source (skills mirrored
  into a tool's folder, a built site), edit the source and regenerate.
- **A working-notes folder may be absent.** Where each stage may have one, it is created with its first note, and a
  stage without one is normal.
- **Research scripts are not project code.** Models and spikes kept as evidence live with the notes they support.

## 6. The project's map (filled by the project)

### Which document answers which question

| The question | The file | Note |
|---|---|---|
| What the system is, why, and what breaks it | `<spec>` | <its main sections> |
| What gets built, in what order, gated by what | `<map>` | <where the stage status lives> |
| How one stage is carried out | `<detail files>` | <work items, exit criteria> |
| Does this identifier exist, and where is it defined | `<registry>` | the single allocator |
| What a term means, in plain words | `<glossary>` | |
| Where things stand, and what is in flight | `<handoff state>` | process, not normative |
| What was decided by the owner, in their words | `<decisions record or log>` | |
| What a review found and how it was ruled | `<reviews folder>` | |
| What a result is whose cause is unknown | `<register>` | a living list |
| How to build and test | `<build guide>` | |
| How commits are made | `<commit rules>` | the `commit` skill |
| What we used to think | `<archive>` | frozen |

### Identifier families

| Family | Form | Names | Defined in |
|---|---|---|---|
| `<PREFIX>` | `<PREFIX>-NN` or `<PREFIX>-slug` | <what kind of thing> | `<registry or file>` |

### Entry points

| To | Run or read |
|---|---|
| open a session | <the opening command, or the handoff's path> |
| check the frontier | <the log command, the checks, the test command> |
| resolve an identifier | <step 1 of §2, in this project's form> |

### Where the rules live

| Rules | Source | Skill |
|---|---|---|
| keeping the documents in sync, minting identifiers | `<file and section>` | `doc-discipline` |
| commits, gates, tags | `<file>` | `commit` |
| reviewing a deliverable | `<reviews folder>` | `adversary` |
| writing a document | `<house style, if any>` | `markdown-docs` |

## Adapting this to your project

Fixed: address by identifier; the reading ladder, stopping at the first step that answers; the frontier read and
checked, never recalled; a stage closes at its gate; the specification over process records; a submission is not a
record; frozen folders and derived copies never edited.

Slots: all of §6. Fill it from the repository as it is, not as it was planned: every path in it resolved, every
family checked against the registry.

Evolving: a row is added when a session looked for something and could not find it, and a trap in §5 when a cold
session fell into it; a row whose file is gone is removed in the same commit that removed the file. *An index that
points at a missing file is believed until someone follows it.*
