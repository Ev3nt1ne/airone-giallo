# The specification graph: rules

This document states the rules of the graph: what a node is, what the relations mean, how the engine decides what
holds and where, what a change does, and what the lint checks. Each rule carries one sentence of reason. The
tools follow this document; where they disagree, one of them is wrong.

## 1. The graph file

The graph lives in one YAML file, `graph.yml` by default, with three parts:

- `meta`: the schema. Every project-specific value the tools need is here: the ID families, the kinds, the
  supports, the relation table, the axes, how `where` is resolved. *The tools carry no project's vocabulary, so the
  same code serves any project.*
- `nodes`: one line per node, in YAML flow style. *One line per entry keeps diffs readable and lets the batch tool
  edit an entry without rewriting the file.*
- `edges`: one line per edge.

The graph file is the only place an ID is allocated: an ID not in it does not exist. IDs are never renumbered and
never reused; a node that is withdrawn keeps its line with status `retired` or `superseded`. *A reference written
anywhere else must keep meaning the same thing.*

Two profiles are shipped (§10). The rules below use the full profile's vocabulary.

## 2. A node

A node is **one proposition, written as one sentence**. *Two claims in one node cannot be supported, threatened or
withdrawn separately.* Split a node when its parts would be read apart: they hold in different places, each needs
its own support, or a threat or an open question bears on one part only. A proposition enters the graph only if
something downstream would change were it to flip. *A node nothing could rest on is bookkeeping, and bookkeeping
goes stale.*

Each node carries four things that answer different questions.

### 2.1 Family: the address

The ID's prefix (`REQ-04`, `DEC-journal`) names the family. Numbered families take two or three digits
(`meta.id_digits`); the families in `meta.slug_prefixes` take a lowercase slug (or a number). No rule but the ID
grammar reads a family. *A family is how a node is cited; what the node is belongs to its kind, which can be
corrected without renaming anything.*

### 2.2 Kind: what the statement is

| Kind | What it is |
| :--- | :--- |
| objective | why the project exists |
| goal | something wanted that several agents bring about together, or that is not yet assigned to one |
| requirement | something wanted that the software brings about, given the assumptions it states |
| expectation | something the software relies on an outside agent to do and cannot force |
| assumption | how the world is, as the project takes it: a fact about networks, users, mathematics, an adversary's means, held until a measurement settles it |
| decision | a choice the project made in answer to its forces |
| threat | what an adversary or the world may do against something the project wants |
| evidence | a reference to a measurement, a model or a paper: it lends confidence, not truth |
| check | a test whose failure would refute what it checks |
| question | an open problem: a part of an argument not developed yet |
| justification | a reason given for a decision, kept beside it |
| record | a fact kept for reference that nothing in the argument rests on |

The first six are **assertions** (`meta.assertion_kinds`): each holds or not on each place. A threat is defended
or not; evidence stands or not; a check, a question, a justification and a record carry no truth value. *The kinds
come from requirements engineering and assurance cases, where the difference between what is wanted, what is
assumed and what is chosen is what makes an argument checkable.* A technical means toward a target is a decision,
not a requirement: *it is wanted only for what it achieves, and it should be replaceable without touching the
target.*

### 2.3 Support: how an assertion comes to hold

| Support | The assertion holds when … | What it owes |
| :--- | :--- | :--- |
| `given` | what it requires holds: it is taken as given | the date it was last confirmed and how long it may go unchecked (L-9) |
| `chosen` | what it requires holds: the project chose it | for a decision, what it is for (W4) |
| `premises` | what it requires holds: its premises are jointly enough | its premises (L-3); a check once declared validated (W5) |
| `satisfier` | what it requires holds **and** one of its satisfiers holds | a satisfier, or it is not argued yet |

A kind does not fix the support: a requirement may be argued from its premises, a goal may need a satisfier. *Kind
says what a statement is; support says how it is argued; the engine reads only the second.*

### 2.4 Status: declared, never truth

`active` (the default), `candidate` (asserted, not yet validated), `suspect` (failed in a cascade, until a review
clears it), `open` (a condition waiting on a work item, named in its `homed_by`), `retired`, `superseded`. Whether a
node holds is computed (§4), never read from its status; a status only leaves retired and superseded nodes out of
the logic and holds a few declarations to account (L-1, W5). *A declared truth can disagree with the graph; a
computed one cannot.* A milestone's exit criteria may be written as conditions with status `open`, each homed by the
work item that closes it; the milestone is ready to put to the owner when none of its conditions is open and each
holds.

### 2.5 Other fields

- `statement`: the sentence. `fingerprint`: the first eight hex digits of a hash of the statement, written by
  `lint --fix`. *A statement that changes without review is caught by the fingerprint, and its cascade is printed.*
- `where`: the document that defines the node, with the sections and IDs it cites (§8). *An attribute nobody can
  follow is no attribute.*
- `domain`: where the node is asserted to hold (§5).
- `reviewed` and `watch` (days), on anything taken as given; optionally `settled_by`, what would turn it into
  evidence. *Assumptions about the world decay silently; a date makes the decay visible.*
- `system`, on evidence: what produced it (§7, W6).

An edge may carry `domain` (§5) and `why`, one line on the reason the dependency holds, which the read side prints
with the edge. *A reason stored as a comment cannot be read back by any tool.*

## 3. Relations

The relation set is closed, and each relation joins only the kinds listed in `meta.relations` (W0). In that table
`assertion` stands for every assertion kind.

| Relation | Reading | From | To |
| :--- | :--- | :--- | :--- |
| `requires` | y is a **necessary** condition of x | an assertion, evidence, a record | a goal, requirement, expectation, assumption or decision |
| `satisfies` | x, together with everything y requires, is **sufficient** for y | a decision, goal, requirement or expectation | an objective, goal, requirement or expectation whose support is `satisfier` |
| `mitigates` | x **defeats** threat t | a decision, goal or requirement | a threat |
| `obstructs` | threat t defeats g unless one of t's defenders holds | a threat | an objective, goal, requirement or expectation |
| `evidenced-by` | e **supports** x: confidence, not proof | an assertion | evidence |
| `verified-by` | t is a check whose failure would refute x | an assertion | a check |
| `awaits` | x's argument has a hole that question q names | an assertion, threat, evidence, check or record | a question |

A decision's justification is what it satisfies or mitigates; its premises, what it requires; its checks, what it
is evidenced-by or verified-by. **A requirement names the condition it needs, not the decision that currently
provides it.** *Then replacing the decision withdraws one satisfaction and leaves the requirement standing, waiting
for a new satisfier, instead of retracting everything above it.* A decision that only restates the requirement it
would satisfy justifies nothing: the argument is circular, and the link goes.

## 4. The holding rule

On each place (§5), with the nodes present there and the edges that count there:

- An **assertion holds** when everything it `requires` holds; if its support is `satisfier`, one of its
  satisfiers holds; every threat that `obstructs` it is defended; and it `awaits` no open question there.
- A **threat is defended** where it awaits no open question and one of its defenders (`mitigates`) holds.
- **Evidence stands** where everything it requires holds.

`requires` is AND; `satisfies` is OR: each satisfier, with what its target requires, is claimed to be enough on its
own, as each defender is against its threat. *When only a combination is enough, the combination is a node of its
own that requires its parts and satisfies the target; written flat, the graph would claim more than is meant.*

An assertion that does not hold is **not argued yet** when it would hold if every open question were answered,
every assertion without a satisfier were satisfied, every threat without a defender were defended, and every
required node absent from the place held. Otherwise it **fails**. Both sets are least fixpoints, so **an assertion
supported only through itself fails.** *"Not argued yet" is a hole someone has to fill; "fails" is a contradiction
in what is written. The two call for different work, so they are kept apart.*

A node that requires a retired or superseded node is not argued yet there, and the reason says so. *A withdrawn
statement can no longer be relied on, but withdrawing it is not a proof of the opposite.*

## 5. Places

A node holds *somewhere*. The places come from the axes in `meta.axes`:

```yaml
axes:
  - {name: env, values: [DEV, STAGING, PROD], ordered: true}
  - {name: side, values: [CLIENT, SERVER], interfaces: true}
```

- A **cell** is one value per axis, joined by dots in axis order: `PROD.SERVER`.
- An **interface** is the boundary between two values of an axis marked `interfaces`, on the same values of the
  other axes: `PROD.CLIENT~PROD.SERVER`. *What crosses a boundary often needs an argument of its own.*
- A **transition** is the move from one value to the next on an axis marked `ordered` (values listed bottom to
  top), on the same values of the others: `STAGING.SERVER>PROD`. *What holds before and after a move can fail
  during it.*

With **no axes** there is exactly one place, `all`, and the holding rule is the plain one. *Places are opt-in: a
project that does not need them pays nothing.* A value names one axis only, so a transition's target is never
ambiguous.

A **domain** is a list of tokens: a place; a wildcard, where `*` stands for every value of one axis (`PROD.*`,
`*.SERVER`, `*.CLIENT~*.SERVER` for that interface on every environment, `STAGING.*>PROD` for that move on every
side; the axis an interface or a transition is on takes a value, never `*`); or `all` for every cell.
Kinds that carry a domain are listed in `meta.domain_kinds`; once a graph declares axes, each live node of those
kinds has one (W1). An objective, a justification and a record carry none.

The **sides** of an interface or a transition are the two cells it joins. A domain **covers** a place when the place
is in it; when the place is a boundary and the domain holds on one of its sides; or when the place is a cell and the
domain holds on a boundary of it. *A statement about a cell is read on that cell's boundaries, and a rule about a
boundary may rest on statements about either side.*

A node is **present** on a place its domain covers; a node without a domain is present everywhere. An edge
**counts** on a place when its source is present, its domain (its own, else its source's) covers the place and,
except for `requires`, its target is present. An edge may carry a domain within its source's (W0) when the
dependency holds on part of the source's domain only. Every place is evaluated, whichever domains exist. *A boundary
that no domain names is still a place where something may fail.*

Tags or groupings that do not change what holds where are not axes.

## 6. The cascade

`lint --what-if NODE` simulates a change: the node is made to fail (a threat: its defence is set aside) and the
graph is read again, place by place. Compared with before:

| Link to what changed | What happens to the node | Spreads? |
| :--- | :--- | :--- |
| `requires` | **fails** | yes |
| `satisfies`, and every satisfier that held is lost | **fails** (unsatisfied) | yes |
| `satisfies`, and a satisfier that holds remains | **warning**: still holds, on fewer legs | no |
| `mitigates` | **warning** if a defender that holds remains; else the threat is **flagged** undefended, and what it obstructs **fails** | the flag no; what it obstructs, yes |
| `evidenced-by`, `verified-by` | **flag**: lost backing | no |
| `requires`, from evidence or a record | **flag** | no |
| `awaits` | **flag**: re-review | no |
| the changed node is a threat | what it obstructs **fails** where it held through that defence | yes |

"Every satisfier is lost" is judged when nothing more fails, *since two satisfiers can fail a step apart.* The
report also lists what rests on the change but did not hold there before, and says where the changed node itself did
not hold. A cascade can start from a place (`--what-if PROD.SERVER`): every node whose domain covers it fails
there, and the cascade is evaluated at that place.

The cascade computes the *potential* impact; a person's review decides the actual one, and marks a failed node
`suspect` until it is re-argued. *A tool can show that the graph is consistent; only a reader can say whether a
satisfier is in fact enough.*

## 7. The lint

The lint checks the graph file's form. Whether a node holds is the engine's, printed on a line of its own, never a
check. Each check reads a node's kind or support, never its family.

| Rule | Check | Level | Why |
| :--- | :--- | :--- | :--- |
| L-1 | the file reads as YAML with no key given twice; every ID matches the grammar; IDs unique; statuses and edge types known; every edge's ends exist; `open` names its work item (`homed_by`) | error | a duplicated key is silently dropped by YAML, and a dangling edge argues nothing |
| L-2 | no family prefix is a prefix of another | error | an ID must be readable without knowing the list |
| L-3 | an assertion argued from its premises names at least one (`requires`) | error | a claim with no stated premise is trivial or hides one |
| L-6 | every statement matches its fingerprint; a mismatch prints its cascade | error until `--fix` | a statement edited without review changes the meaning of everything resting on it |
| L-7 | on each place, the edges that count there form no cycle, read in the direction of dependence (a node depends on what it requires, on its satisfiers, and on the defenders of the threats obstructing it) | error | a circular argument proves nothing |
| L-8 | every live node in the argument has an edge, unless listed in `meta.orphan_ok` with a reason or of a kind in `meta.orphan_exempt`; records and justifications are never asked | warning | an unlinked node is either noise or a dependency nobody recorded |
| L-9 | anything taken as given carries `reviewed` and `watch`; past the date, a warning | error / warning | the world changes under an assumption without notice |
| W0 | every edge joins kinds its relation allows; `satisfies` ends at a node whose support is `satisfier`; an edge's domain lies within its source's | error | a link the engine would not read is a false reassurance |
| W1 | once axes are declared, every live node of a kind in `meta.domain_kinds` has a domain; the other kinds carry none | error | a node with no place is read everywhere, which is rarely what was meant |
| W2 | if x requires y, y's domain covers every place of the edge's domain | error | a premise must hold wherever the claim relies on it |
| W4 | every decision says what it satisfies or mitigates | error | a choice with no purpose cannot be weighed when it is challenged |
| W5 | an assertion argued from its premises and declared validated (not `candidate`) has evidence or a check | count | validation without a check is an assertion twice |
| W6 | evidence that something rests on names its `system` and requires an assumption, taken as given, that this system stands for its places | error | a figure measured on one system supports a claim about another only through an assumption that says so |
| W7 | `meta.orphan_exempt` names kinds in the argument only, and a kind leaves once its nodes are linked | error / warning | a temporary exemption that never shrinks becomes permanent |
| W10 | every live node has a known kind; an assertion a known support, any other kind none | error | the engine reads kind and support; an unknown one is silently ignored |
| W11 | every live node's `where` resolves (§8); a `where` naming no document is a warning | error / warning | a cross-reference to a section that does not exist is easy to write and cheap to catch |

The rule numbers are an index and are not consecutive. The lint exits non-zero on any error. *Run it in
the commit hook and in CI: a graph without its checker is stale bookkeeping.*

## 8. Resolving `where`

A `where` is one or more references separated by `;`. In each reference:

- a **file token** has a slash, ends in `.md`, or is a short name in `meta.where_aliases`. It resolves under the
  graph file's folder (or `--root`) to the file itself, the file with `.md` added, a folder's files
  (`where_forms.folder_files`, globs inside the folder), and the one file a prefix names (`notes/part-3` reads
  `notes/part-3-*.md`);
- a **section token** starts with the section mark (`§4.2`; several may share one token: `§4.1/§7`), and must start
  a heading in those files, or be a bold lead, or a numbered item under a numbered heading (`1.` under `## 3.` is
  `3.1`);
- an **ID token** matches `where_forms.id`, and must occur in those files;
- every other word is prose and is not read.

All of these forms are data in `meta.where_forms` (`section_mark`, `id`, `heading`, `lead`, `item`,
`folder_files`), with plain Markdown conventions as the default. *Projects cite their documents in their own ways;
the resolver should follow the project, not the other way round.*

## 9. Changing the graph in batches

A batch is a YAML file of operations on the graph file's lines (add a node or an edge, change a statement, a domain, a
status, remove an edge, replace a text). `batch FILE` previews it on a copy: the lint's verdict, every node whose
outcome changes on some place, the cascade of each node it touches, and the batch's **tier**, which is read from the
operations and the outcomes, never declared:

- **A, additive**: only new nodes, none a decision, and edges that each touch a new node; no existing node changes
  outcome on any place. *Nothing already argued can move, so it may be applied directly (`--apply --additive`
  refuses anything else) and reported.*
- **B, neutral links**: only new `verified-by`, `evidenced-by` or `awaits` edges between existing nodes, and no
  outcome moves. *Harmless to the argument, but each says something about content, so they are confirmed together.*
- **Everything else**: a changed statement, domain, kind, support or status; a removed edge; a retired node; a new
  decision; any outcome that moves. *These can change what was decided, so each is reviewed on its own.*

The preview also lists **review occasions**: nodes that newly hold on a place where some threat is undefended. *The
engine shows the graph consistent there; only a review says whether the new support is enough.* After applying,
`actual REV` prints the outcomes that changed against a git revision, in the preview's form, so the two can be
compared.

## 10. Profiles

- **lite**: kinds requirement, assumption, decision, threat; relations `requires`, `satisfies`, `mitigates`,
  `obstructs`; no axes; families DEC, REQ, ASM, ATK. *Enough to record what is needed, what is assumed, what was
  chosen, and what could go wrong.*
- **full**: every kind and relation above, with evidence, checks, open questions, records and justifications.

Every kind, relation and family of lite is in full, with the same reading, so **a lite graph is valid under the
full meta unchanged**; growing is a matter of replacing the `meta` block. Declaring axes later is a modelling step,
not a migration: the nodes then say where they hold (W1).

## 11. What the graph holds, and what it does not

The graph holds the design's dependencies: propositions whose change would make another proposition need
re-arguing. A choice that nothing technical rests on (a name, a licence, how the work is organized) is a **record**:
it keeps its ID, carries no domain, and nothing may rest on it (W0, W1). A record becomes an argued node when
something comes to rest on it, and the reverse; either move is a change like any other.

The graph is not a log of discussion. A question, a leaning or an example is not a decision; a decision is recorded
once it is made, at the strength it was made with, and its source is checked first. *A graph that records more than
was decided gives false authority to what was only said.*
