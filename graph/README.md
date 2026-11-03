# The specification graph

A project's design is a web of conditional statements: *this requirement holds because that decision satisfies it,
provided this assumption about the world is true, and as long as that threat is defended*. Usually the web lives in
prose, and when one strand moves (a decision is loosened, an assumption turns out false) the statements that lose
their footing are found by re-reading everything, or not found at all.

This package keeps that web as data and computes it. Each statement is a **node** with a kind (a requirement, a
decision, an assumption, a threat, …); each dependency is a typed **edge** (`requires`, `satisfies`, `mitigates`,
`obstructs`, …). An engine reads the graph as logic and says, for every node, whether it **holds**, is **not argued
yet**, or **fails**, and why. A lint keeps the file honest. A cascade shows what a change would break before it is
made.

It is the graph of Airone Giallo, described in the [repository](https://github.com/Ev3nt1ne/airone-giallo), and the
one part of it that stands alone: nothing here needs the rest.

## Why

- **Truth is computed, never declared.** A status field can say "done" while the decision under it was withdrawn
  last week. Here whether a node holds is derived from the graph every time, so it cannot drift from the graph.
- **A change has a known blast radius.** `lint --what-if NODE` lists what fails, what still holds on fewer legs, and
  what should be re-read, before anyone edits the design.
- **Requirements name what they need, not who provides it.** A requirement rests on a condition; a decision
  satisfies the condition. Swap the decision and the requirement is untouched, which keeps the cascade precise.
- **Where a statement holds is part of the statement.** A project may declare axes (environments, editions,
  platforms); the engine then evaluates each place, including the boundary between two places and the move from one
  to the next. A project with no axes has one place, and the rule is the plain one.

The rules, each with its reason, are in [docs/spec-graph.md](docs/spec-graph.md).

## Install

Python 3.10 or newer; the only dependency is PyYAML.

```sh
uv tool install 'git+https://github.com/Ev3nt1ne/airone-giallo.git#subdirectory=graph'
```

or, from a clone of the repository, `uv tool install ./graph`; `pipx install` takes the same arguments, and
`pip install` works inside a project's own venv. This puts the command `specgraph` on the PATH; installed with `pip`,
the package is importable too, and `python -m specgraph` is the same command. For developing the graph,
`pip install -e graph` from the clone, in a venv, installs it editable, as under Tests. The examples below use the
command. With `uv`, the command runs with nothing installed:
`uvx --from 'git+https://github.com/Ev3nt1ne/airone-giallo.git#subdirectory=graph' specgraph …`.

In Claude Code, the skill that teaches an agent the graph ([skills/graph/SKILL.md](skills/graph/SKILL.md)) comes as
the plugin `specgraph`, from the repository's marketplace: `/plugin marketplace add Ev3nt1ne/airone-giallo`, then
`/plugin install specgraph@airone-giallo`. The plugin carries the skill only; the command is installed as above.

## Start

Create an empty graph in the lite profile (four kinds, four relations, no axes):

```sh
specgraph init --profile lite
```

This writes `graph.yml`: a `meta` block, which is the schema every tool reads, and empty `nodes` and `edges`.
The `full` profile adds objectives, goals, expectations, evidence, checks, open questions, records and
justifications, with the relations `evidenced-by`, `verified-by` and `awaits`; a lite graph is valid under the
full meta unchanged.

A small example: a Mars rover must never drive off a cliff. Write a short design document beside the graph file,
`design.md`:

```markdown
# Design

## 1. Goals

## 2. Choices

## 3. Risks
```

Then replace the empty `nodes: []` and `edges: []` in `graph.yml` with five nodes and four edges:

```yaml
nodes:
  - {id: REQ-01, kind: requirement, support: satisfier, statement: "The rover never drives off a cliff.", where: "design.md §1"}
  - {id: ASM-01, kind: assumption, support: given, statement: "In daylight the camera sees every cliff edge ahead.", where: "design.md §1", reviewed: 2026-10-01, watch: 365}
  - {id: DEC-daylight, kind: decision, support: chosen, statement: "The rover drives only in daylight.", where: "design.md §2"}
  - {id: DEC-blind-stop, kind: decision, support: chosen, statement: "When the camera's image degrades, the rover stops, and moves again only once the image is clear.", where: "design.md §2"}
  - {id: ATK-01, kind: threat, statement: "A dust storm blinds the camera.", where: "design.md §3"}
edges:
  - {from: DEC-daylight, type: satisfies, to: REQ-01}
  - {from: DEC-daylight, type: requires, to: ASM-01}
  - {from: ATK-01, type: obstructs, to: REQ-01}
  - {from: DEC-blind-stop, type: mitigates, to: ATK-01}
```

Read it: the requirement needs a satisfier (`support: satisfier`), and driving only in daylight is one; that decision
rests on an assumption about the camera, taken as given and re-checked every 365 days; a dust storm obstructs the
requirement until a defender holds, and stopping as soon as the image degrades is one: it reacts to what the camera
sees, so it needs no warning that a storm has begun.

Check it. The first run writes each statement's fingerprint, so a later edit to a statement is noticed:

```sh
specgraph lint --fix
specgraph lint
```

```text
5 nodes, 4 edges
  backfill (schema, not warnings): W5 claim without check 0
  engine (computed, not warnings): 0 assertion(s) fail somewhere, 0 more not argued yet somewhere; 0 threat(s) undefended somewhere
specgraph lint: 0 error(s), 0 warning(s)
```

Ask what happens if the assumption about the camera is wrong:

```sh
specgraph lint --what-if ASM-01
```

The daylight decision fails, and the requirement loses its only satisfier, so it fails too. Remove `DEC-blind-stop` and
the dust storm is undefended: the requirement is then *not argued yet*, which is not a failure but a hole someone has to
fill.

To look nodes up: `near WORD…`, `show ID…`, `why ID`, `at PLACE`, `draw ID` (Mermaid, or Graphviz with `--dot`).
To change the graph in reviewable steps: `batch FILE` previews a batch of edits and reads its tier (additive,
neutral links, or needs review); `batch FILE --apply` applies it; `actual REV` compares the outcomes with a git
revision. Each command has `--help`.

## Tests

From the repository's root:

```sh
pip install -e 'graph[test]'
pytest graph/tests
```

## Licence

MIT; see [LICENSE](../LICENSE).
