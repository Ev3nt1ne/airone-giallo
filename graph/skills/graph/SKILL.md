---
name: graph
description: Reading, extending and checking a project's specification graph (graph.yml) with the specgraph command - what holds and why, minting a node, the cascade before a change, a batch previewed by its tier, lint to zero errors. Load when the project has a graph.yml, when a design statement is added or changed, or when asked what depends on what.
---

# Working with the specification graph

For a project that keeps its design as a graph: one YAML file, `graph.yml`, where each statement is a node with a
kind and each dependency a typed edge, and an engine computes, for every node, whether it holds, is not argued yet,
or fails. The rules of the graph, each with its reason, are in the package's `docs/spec-graph.md`; this skill is
what an agent does with it. Each rule carries its reason in italics.

**The invariant: whether a node holds is computed from the graph, never declared.** *A status can say "done" while
the decision under it was withdrawn; a computed truth cannot disagree with the graph.* Never write a status as a
truth, never report a node as holding without `specgraph why`, and never bend the graph to fit a document: a
contradiction is raised, not edited away.

## 1. The command

- `specgraph` is a Python package. Installed with
  `pip install 'git+https://github.com/Ev3nt1ne/airone-giallo.git#subdirectory=graph'`, or run without installing
  with `uvx --from 'git+https://github.com/Ev3nt1ne/airone-giallo.git#subdirectory=graph' specgraph …`. If neither
  works, ask the owner to install it; do not reimplement a check. *The tools follow `docs/spec-graph.md`; a check
  written in the session follows memory.*
- Every command takes `--graph PATH`; the default is `graph.yml` in the current folder. Each has `--help`.
- A project without a graph gets one only at the owner's word: `specgraph init --profile lite` writes an empty
  `graph.yml` whose `meta` block is the schema every command reads. *Lite (requirement, assumption, decision,
  threat; `requires`, `satisfies`, `mitigates`, `obstructs`) is valid under the full profile unchanged, so starting
  small costs nothing later.*

## 2. Read before writing

- `specgraph near WORD…` finds nodes by words in their statements; `show ID…` prints nodes whole; `why ID` prints
  whether a node holds, where, and on what; `at PLACE` lists what holds on one place; `draw ID` prints the
  neighbourhood as Mermaid (`--dot` for Graphviz). *A node that already says it is found by its words, not by its
  number.*
- `specgraph lint` prints the engine's line (what fails somewhere, what is not argued yet, which threats are
  undefended) and the lint's errors and warnings. **Zero errors is the bar; warnings are read, not zeroed.** *An
  error is a contradiction in the file; a warning is a judgement the lint cannot make.*
- "Not argued yet" and "fails" are different work: the first is a hole someone has to fill (a satisfier, a defender,
  an answer), the second a contradiction in what is written. Report them apart.

## 3. Adding a statement

1. **Check it is not there**: `specgraph near` with the statement's words. *A second node for one claim splits its
   support and its threats between two addresses.*
2. **One proposition, one sentence.** Split what would be read apart: parts that hold in different places, that
   need their own support, or that a threat bears on alone. A proposition enters only if something downstream would
   change were it to flip. *A node nothing could rest on is bookkeeping, and bookkeeping goes stale.*
3. **Kind, then support.** Kind says what the statement is (a requirement is wanted of the software; a decision is
   a choice; an assumption is how the world is taken to be; a threat is what may go against it). Support says how an
   assertion is argued: `given`, `chosen`, `premises`, or `satisfier`. A technical means toward a target is a
   decision, never a requirement. *The engine reads the support; the kind is for the reader.*
4. **The next free ID in the family**, never a reused or renumbered one: `grep -o 'REQ-[0-9]*' graph.yml | sort
   -uV | tail -1`. *A reference written anywhere else must keep meaning the same thing.*
5. **`where` names the document and section that defines the node**, in a form the resolver reads (`design.md
   §2`). *An attribute nobody can follow is no attribute.*
6. **Edges by the relation table**: a requirement names the condition it needs with `requires`, and a decision
   `satisfies` it; a decision says what it satisfies or mitigates, or the lint refuses it (W4). A decision that only
   restates the requirement it would satisfy justifies nothing. *Replacing a decision then withdraws one
   satisfaction and leaves the requirement standing, instead of retracting everything above it.*
7. **Anything taken as given carries `reviewed` and `watch`** (days). *Assumptions about the world decay silently;
   a date makes the decay visible.*
8. **`specgraph lint --fix`, then `specgraph lint`**, to zero errors. The first writes each new statement's
   fingerprint. *A statement edited later without review is then caught, and its cascade printed.*

## 4. Changing what is there

- **Run the cascade first**: `specgraph lint --what-if ID` (or a place, `--what-if PROD.SERVER`) prints what
  fails, what still holds on fewer legs, and what should be re-read, before anything is edited. Put the result to
  the owner with the change. *The tool shows what could move; a person decides whether a remaining satisfier is in
  fact enough.*
- **Write the change as a batch**, a YAML file of operations on the graph's lines, and preview it:
  `specgraph batch FILE`. The preview prints the lint's verdict, every node whose outcome moves, the cascade of each
  touched node, and the batch's **tier**, read from the operations, never declared:

  ```yaml
  ops:
    - {op: add_node, after: DEC-journal, line: '{id: ATK-01, kind: threat, statement: "…", where: "design.md §3"}'}
    - {op: add_edge, after_edge: [DEC-journal, satisfies, REQ-01], line: "{from: ATK-01, type: obstructs, to: REQ-01}"}
    - {op: set_statement, id: REQ-01, statement: "…"}
    - {op: set_status, id: DEC-journal, status: suspect}
    - {op: remove_edge, from: A, type: requires, to: B}
  ```

  Tier A (additive: new nodes, none a decision, and edges that each touch a new node, no outcome moving) may be
  applied directly, `specgraph batch FILE --apply --additive`, and reported. Tier B (new neutral links between
  existing nodes) is confirmed as a group. Everything else (a changed statement, domain, kind, support or status, a
  removed edge, a retired node, a new decision, any outcome that moves) is put to the owner one change at a time.
  *Nothing already argued moves in tier A; everything else can change what was decided.*
- **After applying**, `specgraph actual REV` prints the outcomes that changed against a git revision, in the
  preview's form. Compare the two; a difference is a finding.
- **A node that failed in a cascade is marked `suspect`** until it is re-argued and the owner clears it. A node
  withdrawn keeps its line, `retired` or `superseded`, never deleted. *A withdrawn statement can no longer be relied
  on, and withdrawing it is not a proof of the opposite.*
- **The statement changes with the document, in the same commit.** A `where` that no longer resolves is an error
  (W11); a statement that no longer matches its document is a lie the fingerprint cannot see. *The graph and the
  documents are read as one argument.*

## 5. What goes in the graph

- A decision is recorded once it is made, at the strength it was made with, and its source is checked first. A
  question, a leaning or an example is not a decision. *A graph that records more than was decided gives false
  authority to what was only said.*
- A choice that nothing technical rests on (a name, a licence, how the work is organized) is a `record`: it keeps
  its ID, and nothing may rest on it, until something does.
- Tags and groupings that do not change what holds where are not axes. Declare axes (`meta.axes`) only when a
  statement holds in one environment, edition or side and not another; then every node says where it holds (W1).

## 6. In the commit hook and in CI

`specgraph lint` exits non-zero on any error; run it where the project runs its checks. *A graph without its
checker is stale bookkeeping.* Where the project also keeps a status file or several design documents, the
`doc-discipline` skill of Airone Giallo says how the graph, the documents and the work items stay true together;
this skill is the graph alone.
