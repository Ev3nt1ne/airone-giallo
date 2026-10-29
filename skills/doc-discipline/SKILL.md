---
name: doc-discipline
description: Keeping a project's design documents and graph consistent through a change, a milestone passed by the owner's ruling, and when a review is due. Load before editing a specification, plan or graph, minting an identifier, committing such a change, proposing a review, or running one the owner asked for.
---

# Changing a project's documents without breaking them

For a project whose design is written down: a specification, a plan, a graph of statements, often in several
documents that describe the same system at different altitudes. An edit that touches one and not the others leaves a
repository that passes every check and is still wrong. Each rule carries its reason in italics. How a single document
is written and corrected is the `markdown-docs` skill; this one is about keeping several of them true together.

**The invariant: at every commit the documents agree with each other and the project's checks report no errors.**
*It is a per-commit standard, not a release one: a mismatch left for later is found by the next reader as a
contradiction, with no way to tell which side is current.*

## 1. Levels, and what each owns

A pattern a project may use whole, in part, or not at all. A small project has one design document and the rules
below reduce to "the document, the graph and the code agree".

| Level | Typically | Owns | Never holds |
|---|---|---|---|
| Specification | `docs/` | requirements, architecture, threats, decisions, open problems | schedules, task lists |
| Plan | `plan/` | phases, milestones, the order between them, risks, each phase's status | mechanism design |
| Phase detail | one file per phase | work items, pitfalls, verification checklists, a milestone's exit criteria | decisions |

- A change at any level reaches the others in the same edit and the same commit. *A later "bring the docs up to
  date" commit makes the history lie about when a thing became true.*
- Each fact has one level that owns it; the others cite it. *A fact owned twice is edited once.*
- Working notes (research, measurements, drafts) are evidence, not a level: the levels cite them, they never stand
  in for them. A finding in a note has changed nothing until it is folded into the specification.

**The ladder: where a document sits, and what it may cite.** Airone Giallo's places form a ladder, read from the bottom:
1 the system documents (`docs/`: the specification, the glossary, the studies, the change notes); 2 the graph
(`graph.yml`); 3 the plan (`plan/`); 4 the AI documents (`ai-docs/`: the status file, the handoff, design, findings,
guides); 5 the agent layer (`AGENTS.md`, `CLAUDE.md`, `RATIONALE.md`, the skills). A document cites only rungs at or
below its own. The project's instruction file names **the cut**: every rung at or below it is public, every rung
above it private, so a public text never points into a private one; in a one-repository project the cut sits at the
top or the bottom and the rule still orders the citations. *A public text that cites a private one is a dead link to
its readers or a leak, and a rung that cited upward could never be made public on its own.* Outside the ladder, each
on the side the owner gives it: the owner's notes (`human-docs/`), downloaded sources (`sources/`, cited by URL
through their manifest, never by path), and the code.

**The archive is beside the ladder, not on it.** Each repository has its own, `archive/` at its top, on that
repository's side: a document that stops being true moves into the archive of the repository it was in, so archiving
never moves it across the cut. Nothing live is on a rung with it, so it has no rung: it is frozen, exempt from the
link check, out of every search unless named, and cited by nothing live beyond a category. Its log (`archive/LOG.md`)
records every change made to an archived file and every change of a word's meaning left uncorrected there;
`check-archive read <file>` says which apply to a file. *A frozen folder on a rung would be the one rung whose rule
is an exception, and one archive for two sides would have to choose one of them.*

## 2. Editing the specification

- **Refine in place.** A requirement is rewritten to its most precise current form; the old wording does not stay
  beside the new. *Two versions left standing are a contradiction, and each reader picks one.*
- **Decided and open are kept apart.** A decision is written in the decisions record and in the section it governs.
  An open problem that gets resolved has its content moved into the text and leaves a one-line tombstone where it
  was. *An identifier deleted breaks every reference to it; one reused makes old references lie.*
- **A number not derived from a measurement is marked illustrative**, and turning it into a derived one says what
  derived it (the `session` skill's [verify method](../session/references/verify-method.md)).
- **Every substantive edit to a level appends a dated line to that level's change note.** *Refining in place drops
  the old text; the change note is where its reason survives.*
- **Nothing is dropped silently**: refine it, move it, or archive it. Neither rule means "never modify": a stale
  table or a contradicted requirement left standing is the failure. What is forbidden is losing the *why*.
- **Renaming a term**: every occurrence is read and changed one by one, never by a blind replacement; the archive is
  entered only through `check-archive rename`, the owner ruling file by file; what is left standing there becomes one
  row in the archive's conflicts table, kind `renamed` or `reused`; the glossary keeps the retired term, with the
  date. *A blind replacement turns a word used in two senses into one wrong statement, and a retired word that is
  reused reads correctly and means the wrong thing.*

Where the reasoning of a superseded claim goes depends on the material:

| Material | The text | The reasoning survives in |
|---|---|---|
| the levels and the graph | refined in place | the change note, dated, append-only |
| working notes, studies | edited in place | correction entries and CHANGE OF PLAN headings (`markdown-docs` §4) |
| the status file | items edited in place; a closed item leaves | the closed file, with what was chosen |
| a frozen archive | never edited, but for a change the owner rules, with its row | the archive's log, `archive/LOG.md` |

## 3. Minting an identifier

One allocator per family; **an identifier in neither allocator does not exist.** The graph allocates statement IDs
(requirements, decisions, assumptions, threats): with the specification graph (`graph/` in Airone Giallo) it is
`graph.yml`, otherwise a table of identifier, one-sentence statement and the place that defines it. The status file
(`ai-docs/status.md` in a project laid out by Airone Giallo) allocates work-item IDs: what is left to do. Both are
append-only: never renumber, never reuse. *Two allocators for one family eventually give one number to two things, and
every citation of it becomes ambiguous.* An item may cite a node; a node never cites an item. *A node states what holds
and outlives the work; a citation of work inside it goes stale when the work closes.*

The steps below mint a statement; a work item takes the next free ID the status file's checker prints.

1. **Check it is not there.** Search the graph for the statement (with the graph, `specgraph near WORD…`), then
   take the next free number in the family: `grep -o 'REQ-[0-9]*' graph.yml | sort -uV | tail -1`.
2. **Write the entry as one sentence.** If it needs two, it is two entries. *A statement with two claims cannot be
   half false, and nothing can point at the half.*
3. **Link it.** Where the project uses the specification graph: its kind, its support and its edges, by the rules
   in `graph/docs/spec-graph.md`.
4. **Write the prose that uses it, in the same edit.** *A minted identifier with no text is a dangling allocation.*
5. **Run the checks**: with the graph, `specgraph lint --fix`, then `specgraph lint`, to zero errors.
6. **Commit the entry with the text that uses it** (§7).

**The budget test:** would anything downstream change if this statement flipped? If not, it is prose, not an entry.
*A graph of everything is read like a graph of nothing.* A decision cited by name that nothing rests on (a
licence, a project name) is a record: it keeps its identifier and carries no argument. When the owner states
something, ask whether anything technical rests on it before minting it.

**A change to an existing entry is the owner's decision.** State the change on its own, preview its cascade (§4),
have it confirmed, and report the actual effect before the commit. Where the project uses the graph,
`specgraph batch FILE` prints the batch's tier with the preview: an additive batch may be applied
(`--apply --additive`) and reported, neutral links are confirmed as one list, everything else is reviewed alone.
Never classify a batch yourself. *The agent proposing a change is the one most likely to miss what it moved.* A
proposal that conflicts with an existing entry is raised as a conflict first: the graph is enforced, not bent
to fit.

## 4. The cascade, before the edit

Before changing a statement other things rest on, find what rests on it. *After the edit, every dependent reads as
consistent with whatever you wrote.*

- With the graph: `specgraph lint --what-if REQ-04` prints what fails, what is warned and what is flagged, place
  by place. Without it: grep every citation of the identifier and read each site.
- Each dependent is re-read and re-argued or re-satisfied. One that cannot be is marked suspect until a recorded
  review clears it.
- **Loosening is not revoking.** Let requirements rest on conditions and let decisions satisfy the conditions; then
  swapping the decision moves nothing that rests on the condition. Prefer that shape when a decision changes.
- **Zero errors is the bar; warnings are read, not zeroed.** Where the graph lists what is not argued yet or
  undefended, that list is what the design argues today. *A claim invented to shorten it argues nothing.* Leave
  it, and report how it moves.

## 5. A milestone the project names

Where the plan names milestones (a release, a migration, the end of a phase), each has exit criteria written down
before the work toward it starts.

- **A milestone is passed by the owner's ruling, never by the agent that did the work concluding the criteria look
  met.** The agent lays out the evidence against each criterion and a recommendation, marked as such. *A milestone
  passed by the agent that did the work is a self-grade.*
- **The record answers each exit criterion and names what the work did not retire, in those words.** *A record that
  rounds a bounded but unchecked risk up to a retired one is the failure this discipline exists to prevent.*
- **The ruling is recorded as a decision** (§2, §7): in the specification with its reason, the plan's status changed
  in the same commit, the milestone's name in the subject. *The work is done at its last task; the milestone is
  passed at its ruling.*

Folding many findings into the specification at once is the same discipline at volume: work the list in order, read
the cascade of every statement about to be restated, and keep each mint in the commit of its text.

## 6. Reviews

A review is proposed, never launched unasked, in one line the owner can answer yes or no: the occasion, the target,
the cost, and what it cannot catch (`session` §2). *A review costs the owner a triage as well as the tokens.* It is
proposed on these occasions only; *an occasion that never pays teaches the owner to say no to all of them*:

1. A decision is recorded before anything satisfies it or gives evidence for it: before the build starts. *A flaw
   found in a design costs a paragraph; found in built code, it costs the code.*
2. A milestone recommendation is drafted.
3. Code with a security surface lands: a cache, a parser, an export format, anything a peer can feed.
4. A measurement is about to become evidence that a decision rests on.

**How one runs.** Two or three reviewers attack the same named target from opposed sides, read-only and without
seeing each other's output, on a different model from the author's where one is available, each told what the
material declares it does not claim; where the material carries numbers, one re-runs them. Every finding cites a file
and a line and gives a failure scenario; there is no quota. *Opposed reviewers who did not read each other converge
only where the flaw is real.* The merge is one findings document: by theme, convergences first, each finding tempered
(stands, overstated, overreach, challenges a decision) and given a direction, not a fix, and what survived said.
Nothing in it is applied before the owner rules; their answers are written in as given.

## 7. Committing the change

How a commit is made (staging, the message's form, branches, remotes) is the project's own commit skill's business;
these are the rules this discipline adds to it.

- **One logical task, with its bookkeeping**: the ticked items, the status file's rows, the change-note lines go in the
  commit of the work that caused them. *A later "update the docs" commit makes the history say a thing became true
  later than it did.*
- **A decision or a specification change gets its own commit**, its body saying whether the cascade (§4) was read
  and what it showed; so does a document that is itself the deliverable. *It is the most valuable history, and must
  be findable alone.*
- **Evidence a decision rests on lands on the main line**, even when the code that produced it is thrown away. *The
  code is disposable; the evidence is not.*
- **The graph is never committed alone and never left behind**: a new identifier with the text that uses it, a
  recomputed check value with the edit that changed its statement. Work on the graph's own machinery is the
  exception. *An entry without its text, or text without its entry, is an inconsistency the check may not see.*
- **The subject carries the identifiers the commit touches.** *`git log --grep` finds a subject that names one and
  misses one that describes it.*
- **The checks run before staging, never recalled**: zero errors, the documents agree, the status markers say what
  is true; a fix the checks require goes in this commit, not the next. *A check remembered as passing is a check
  skipped.*
- **Never a secret of any kind in the commit.** *A committed secret is in every clone and every copy of the
  history.*
