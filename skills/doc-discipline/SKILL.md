---
name: doc-discipline
description: Keeping a project's design documents and registry consistent through a change, and the gate as a hard stop. Load before editing a specification, plan or registry, or minting an identifier.
---

# Changing a project's documents without breaking them

For a project whose design is written down: a specification, a plan, a registry of identifiers, often in several
documents that describe the same system at different altitudes. An edit that touches one and not the others leaves a
repository that passes every check and is still wrong. Each rule carries its reason in italics. How a single document
is written and corrected is the `markdown-docs` skill; this one is about keeping several of them true together.

**The invariant: at every commit the documents agree with each other and the project's checks report no errors.**
*It is a per-commit standard, not a release one: a mismatch left for later is found by the next reader as a
contradiction, with no way to tell which side is current.*

## 1. Levels, and what each owns

A pattern a project may use whole, in part, or not at all. A small project has one design document and the rules
below reduce to "the document, the registry and the code agree".

| Level | Typically | Owns | Never holds |
|---|---|---|---|
| Specification | `SPEC` | requirements, architecture, threats, decisions, open problems, gate records | schedules, task lists |
| Map | `PLAN` | stages, gates, the order between them, risks, each stage's status | mechanism design |
| Detail | one file per stage | work items, pitfalls, verification checklists, a gate's exit criteria | decisions |

- A change at any level reaches the others in the same edit and the same commit. *A later "bring the docs up to
  date" commit makes the history lie about when a thing became true.*
- Each fact has one level that owns it; the others cite it. *A fact owned twice is edited once.*
- Working notes (research, measurements, drafts) are evidence, not a level: the levels cite them, they never stand
  in for them. A finding in a note has changed nothing until it is folded into the specification.

## 2. Editing the specification

- **Refine in place.** A requirement is rewritten to its most precise current form; the old wording does not stay
  beside the new. *Two versions left standing are a contradiction, and each reader picks one.*
- **Decided and open are kept apart.** A decision is written in the decisions record and in the section it governs.
  An open problem that gets resolved has its content moved into the text and leaves a one-line tombstone where it
  was. *An identifier deleted breaks every reference to it; one reused makes old references lie.*
- **A number not derived from a measurement is marked illustrative**, and turning it into a derived one says what
  derived it (`verify`).
- **Every substantive edit to a level appends a dated line to that level's change note.** *Refining in place drops
  the old text; the change note is where its reason survives.*
- **Nothing is dropped silently**: refine it, move it, or archive it. Neither rule means "never modify": a stale
  table or a contradicted requirement left standing is the failure. What is forbidden is losing the *why*.

Where the reasoning of a superseded claim goes depends on the material:

| Material | The text | The reasoning survives in |
|---|---|---|
| the levels and the registry | refined in place | the change note, dated, append-only |
| working notes, studies, registers | edited in place, status tables kept current | correction entries and CHANGE OF PLAN headings (`markdown-docs` §4) |
| a frozen archive | never edited | — |

## 3. Minting an identifier

One registry allocates every identifier; **an identifier not in it does not exist.** It is append-only: never
renumber, never reuse. *Two allocators eventually give one number to two things, and every citation of it becomes
ambiguous.* Where the project uses the specification graph (`graph/` in this kit), the registry is its
`registry.yml`; otherwise it can be a table of identifier, one-sentence statement and the place that defines it.

1. **Check it is not there.** Search the registry for the statement (with the graph, `specgraph near WORD…`), then
   take the next free number in the family: `grep -o 'REQ-[0-9]*' registry.yml | sort -uV | tail -1`.
2. **Write the entry as one sentence.** If it needs two, it is two entries. *A statement with two claims cannot be
   half false, and nothing can point at the half.*
3. **Link it.** Where the project uses the specification graph: its kind, its support and its edges, by the rules
   in `graph/docs/spec-graph.md`.
4. **Write the prose that uses it, in the same edit.** *A minted identifier with no text is a dangling allocation.*
5. **Run the checks**: with the graph, `specgraph lint --fix`, then `specgraph lint`, to zero errors.
6. **Commit the entry with the text that uses it** (`commit`).

**The budget test:** would anything downstream change if this statement flipped? If not, it is prose, not an entry.
*A registry of everything is read like a registry of nothing.* A decision cited by name that nothing rests on (a
licence, a project name) is a record: it keeps its identifier and carries no argument. When the owner states
something, ask whether anything technical rests on it before minting it.

**A change to an existing entry is the owner's decision.** State the change on its own, preview its cascade (§4),
have it confirmed, and report the actual effect before the commit. Where the project uses the graph,
`specgraph batch FILE` prints the batch's tier with the preview: an additive batch may be applied
(`--apply --additive`) and reported, neutral links are confirmed as one list, everything else is reviewed alone.
Never classify a batch yourself. *The agent proposing a change is the one most likely to miss what it moved.* A
proposal that conflicts with an existing entry is raised as a conflict first: the registry is enforced, not bent
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

## 5. The gate: a hard stop

A gate is a point the project does not pass until named exit criteria are met and a decision is recorded. It is
the pattern for any hard stop: a release, a migration, a change of architecture.

- **A gate is passed by the owner's ruling, never by an agent concluding the criteria look met.** The agent lays
  out the evidence and a recommendation, marked as such. *A gate passed by the agent that did the work is a
  self-grade.*
- **Carried risks stay carried.** A risk the stage did not retire is named as not retired, in those words. *A gate
  that quietly turns a model that was bounded but never validated into a validated one is the failure this
  discipline exists to prevent.*

When the owner has ruled, the record:

1. Re-read the gate's exit criteria. The record answers each one; it does not paraphrase the gate.
2. Write the decision into the specification: the section it governs, the decisions record, the change note. The
   rationale, not only the choice.
3. Mint any identifier the ruling creates (§3).
4. Tick the gate in the detail, change the stage's status in the map, add the map's change-note line.
5. Run the checks to zero errors.
6. Commit it alone, with the gate's identifier in the subject, and tag it where the project tags gates (`commit`).

Folding a stage's findings into the specification after a gate is the same discipline at volume: work the list in
order, read the cascade of every statement about to be restated, and keep each mint in the commit of its text.

## Adapting this to your project

Fixed: the documents agree at every commit; one owner per fact; one allocator, append-only, one sentence per
entry; the cascade read before the edit; the reasoning of a superseded claim kept somewhere; a gate passed only by
the owner's ruling, recorded alone, carried risks named.

Slots the project fills in its instruction file: its levels and their files (one, two or three); the registry's
file and the identifier families with their grammar; whether it uses the specification graph; the check command;
where the change notes live; the frozen folder; its gates, where their exit criteria are written, and how a gate's
tag is named.

Evolving: a rule is added from a named inconsistency that reached a commit, with its reason beside it; a rule not
needed for a long while is removed. *A discipline nobody can recite is not practised.*
