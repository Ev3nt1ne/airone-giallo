# The project's map: a template and a worked example

A long project's documents run to thousands of lines and cite each other by identifier; read whole, they would fill
most of a context window. The map is the index in between, and it lives in the project's instruction file. Copy the
template below there and fill it from the repository as it is, not as it was planned: every path resolved, every
family checked against its allocator.

How the map is used, cheapest first, stopping at the step that answers:

1. **Address by identifier, not by file name.** Grep the identifier in its allocator (with the specification graph,
   `specgraph show REQ-04`); a one-sentence registry statement often answers the question alone.
2. Every site that cites it: `grep -rn 'REQ-04' DOCS`.
3. One file's section map, `grep -n '^#' DOCS/design.md`, then one section.
4. The whole document, last.

*Finding a definition by reading the document that holds it spends ten thousand tokens on one sentence.* Two
families that look alike can name different things, statements and work items; the map says which is which, so
never guess from the prefix.

## The template

### Which document answers which question

| The question | The file | Note |
|---|---|---|
| What the system is, why, and what breaks it | `<spec>` | <its main sections> |
| What gets built, in what order, gated by what | `<map>` | <where the stage status lives> |
| How one stage is carried out | `<detail files>` | <exit criteria> |
| Does this statement exist, and where is it defined | `<graph registry>` | the allocator of statement IDs |
| What is left to do, and what waits on the owner | `<register>` | the allocator of work-item IDs |
| What a term means, in plain words | `<glossary>` | |
| Where things stand, and what is in flight | `<handoff state>` | process, not normative |
| What was decided by the owner, in their words | `<decisions record or log>` | |
| What a review found and how it was ruled | `<reviews folder>` | |
| How to build and test | `<build guide>` | |
| What we used to think | `<archive>` | frozen |

### Identifier families

| Family | Form | Names | Allocated by |
|---|---|---|---|
| `<PREFIX>` | `<PREFIX>-NN` or `<PREFIX>-slug` | <what kind of thing> | `<graph registry or register>` |

### Entry points

| To | Run or read |
|---|---|
| open a session | <the opening command, or the handoff's path> |
| check the frontier | <the log command, the checks, the test command> |
| resolve an identifier | <step 1 above, in this project's form> |

### Where the rules live

| Rules | Source |
|---|---|
| keeping the documents in sync, minting identifiers, committing a change, reviews | `doc-discipline`, and `<file and section>` |
| how a commit is made | `<the project's own commit skill or guide>` |
| writing a document | `markdown-docs`, and `<house style, if any>` |

## A worked example

An invented project: a note-taking editor whose one hard promise is that a saved note survives a crash, the same
small design the specification graph's README uses (`REQ-01`, `DEC-journal`, `ATK-01`) grown into a project with a
plan. It shows the shape of a filled map, not a recommended layout.

| The question | The file | Note |
|---|---|---|
| What the editor is, why, and what breaks it | `docs/design.md` | §1 goals · §2 choices · §3 risks · §4 decisions record · §5 open questions · §6 change note |
| What gets built, in what order, gated by what | `docs/plan.md` | §2 holds each stage's status; gates `G1` to `G3` |
| How one stage is carried out | `docs/stages/stage-NN-<slug>.md` | pitfalls, the gate's exit criteria at the bottom |
| Does this statement exist | `registry.yml` | `specgraph show ID` |
| What is left to do | `docs/register.md` | the checker prints the next free ID |
| Where things stand, what is in flight | `handoff/current.md` | process, not normative |
| What we used to think | `docs/archive/` | frozen; uses the old `SR-1`-style names, mapped at the top of each file |

| Family | Form | Names | Allocated by |
|---|---|---|---|
| `REQ`, `ASM`, `ATK`, `QST` | `REQ-01` | a requirement, an assumption, a threat, an open question | `registry.yml` |
| `DEC` | `DEC-journal` | a decision, by slug | `registry.yml` |
| `ED` | `ED-001` | a work item; **not a statement**, never cited by one | `docs/register.md` |
| `G` | `G2` | a gate | `docs/plan.md` and its stage file |

**"Why does saving write a journal first?"** `specgraph show DEC-journal` prints the one sentence, *a save writes a
journal entry, then replaces the file*, with `where: design.md §2`. If the question was what was decided, that
answers it; if it was why this and not a copy-on-write file, read the one subsection of §2 and nothing else.

**"Is stage 2 done?"** The register holds no open item for stage 2, but `G2` at the bottom of the stage file is not
ticked, and its exit criteria ask for the crash test run a thousand times on two file systems. The work is done; the
stage is not. *Stages close at their gates, not at their last task.*

**"What did the journal study recommend?"** The study ends with a recommendation written by the agent that ran it,
and `docs/design.md` §4 has no entry for it. It is a submission, not a record: the study recommended, the project
has not decided. *A self-graded report read as a record turns an agent's opinion into the project's position.*

**"Where is SR-3 defined?"** No `SR` family exists. The archive's mapping note says `SR-3` is the old name of
`REQ-03`; resolve that one, and write `REQ-03` in anything new. *A retired name stays retired.*

**"What is next?"** `handoff/current.md` names the first step. Check it against the repository first: the commits
since the handoff was written, the lint and the tests now. *A frontier recalled from an earlier session is the one
most confidently wrong.*
