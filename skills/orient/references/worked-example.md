# A filled map, and a walk through it

An invented project: a note-taking editor whose one hard promise is that a saved note survives a crash. It is the
same small design the specification graph's README uses (`REQ-01`, `DEC-journal`, `ATK-01`), grown into a
project with a plan. Everything here is invented; it shows the shape of a filled §6, not a recommended layout.

## The filled map

### Which document answers which question

| The question | The file | Note |
|---|---|---|
| What the editor is, why, and what breaks it | `docs/design.md` | §1 goals · §2 choices · §3 risks · §4 decisions record · §5 open questions · §6 change note |
| What gets built, in what order, gated by what | `docs/plan.md` | §2 holds each stage's status; gates `G1` to `G3` |
| How one stage is carried out | `docs/stages/stage-NN-<slug>.md` | work items, pitfalls, the gate's exit criteria at the bottom |
| What a stage's research found | `docs/stages/stage-NN/` | working notes; only some stages have one |
| Does this identifier exist, and where is it defined | `registry.yml` | the single allocator; `specgraph show ID` |
| What a term means | `docs/glossary.md` | |
| Where things stand, what is in flight | `handoff/current.md` | process, not normative |
| What a review found and how it was ruled | `docs/reviews/` | one worksheet per review |
| How to build and test | `docs/building.md` | |
| What we used to think | `docs/archive/` | frozen; uses the old `SR-1`-style requirement names, mapped at the top of each file |

### Identifier families

| Family | Form | Names | Defined in |
|---|---|---|---|
| `REQ` | `REQ-01` | a requirement | `registry.yml` |
| `ASM` | `ASM-01` | an assumption about the world, taken as given and re-checked | `registry.yml` |
| `ATK` | `ATK-01` | a threat: what could defeat a requirement | `registry.yml` |
| `DEC` | `DEC-journal` | a decision, by slug | `registry.yml` |
| `QST` | `QST-01` | an open question | `registry.yml` |
| `S` | `S2.3` | a work item: stage 2, item 3; **not a statement**, not in the registry | the stage file |
| `G` | `G2` | a gate | `docs/plan.md` and its stage file |

### Entry points

| To | Run or read |
|---|---|
| open a session | `handoff/current.md`, then `git log --oneline -10` |
| check the frontier | `specgraph lint`, `make test`, and the stage file's gate |
| resolve an identifier | `specgraph show ID`, or `grep -n 'ID' registry.yml` |

## A walk through it

**"Why does saving write a journal first?"** Step 1 of the ladder: `specgraph show DEC-journal` prints the one
sentence, *a save writes a journal entry, then replaces the file*, with `where: design.md §2` and the requirement it
satisfies. If the question was what was decided, that answers it. If it was why this and not a copy-on-write file,
step 3: `grep -n '^#' docs/design.md`, then the one subsection of §2. The rest of the document stays unread.

**"Is stage 2 done?"** `docs/plan.md` §2 shows stage 2 in progress. The stage file has every work item ticked, from
`S2.1` to `S2.6`, but `G2` at the bottom is not ticked, and its exit criteria ask for the crash test run a thousand
times on two file systems. The honest answer: the work items are done; the stage is not, because its gate has not
been ruled on.

**"What did the journal study recommend?"** `docs/stages/stage-02/journal-study.md` ends with a recommendation
written by the agent that ran the study. The handoff shows no ruling on it, and `docs/design.md` §4 has no entry for
it. It is a submission: the study recommended, the project has not decided.

**"Where is SR-3 defined?"** No `SR` family exists in the registry. The archive's mapping note says `SR-3` is the old
name of `REQ-03`; resolve that one instead, and write `REQ-03` in anything new.

**"What is next?"** `handoff/current.md` §4 names the first step. Before acting on it, check it against the
repository: the commits since the handoff was written, and the lint and the tests now. A handoff written two
sessions ago may name work that has since landed.
