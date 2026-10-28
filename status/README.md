# The status file

A long project has two kinds of record, and they age differently. What the system *is* (its requirements,
decisions, assumptions) changes slowly and is argued in design documents or in the specification graph. What is
*left to do* (a question waiting on the owner, a defect found while reading code, a feature accepted and not yet
built) changes every session. When the second kind is written into the first, a design document ends up saying
"not yet implemented" months after it was, and nobody can tell which of two documents is current.

The status file is the one file that holds the work: what waits on the owner's decision, what is accepted but not
built, what is deferred until a named trigger. Each item has an ID that never changes and a link to where its reason
lives. A second file, the closed file, keeps every item that left, with what was chosen. A checker reads both,
reports what breaks the rules and prints the next free ID in each family.

It is a piece of Airone Giallo, the kit described in the [repository](https://github.com/Ev3nt1ne/airone-giallo), and
it is useful without the rest. In a project laid out by the kit it sits in `ai-docs/`, on rung 4 of the ladder
(`skills/doc-discipline` §1): an item may cite a graph node or any document at or below that rung, and a handoff or a
finding may cite an item.

## Why

- **One file owns status.** Status kept in two places is updated in one, so where another document disagrees with
  the status file, the status file is right and the other has drifted.
- **Work and design are kept apart.** The graph and the design documents state what holds; the status file states
  what is left to do, because the two go stale on different schedules.
- **An ID names the item and nothing that can change.** It holds only what is fixed at birth, a family and a
  counter, so a change of kind, owner or area never breaks a citation.
- **IDs are never renumbered or reused.** A reused ID makes every old citation point at the wrong item, in commit
  messages and code comments nobody will edit.
- **The status file is the allocator, and the next ID is derived.** A number written down goes stale without anything
  noticing; the checker counts the closed file too, since a number that left the status file is still taken.
- **Closed items leave, with what was chosen.** A status file too long to read whole gets skimmed, and "done" without
  the choice sends the next session to work it out again.
- **It indexes items, never documents.** An index of documents goes stale as they move, and misleads with
  confidence.
- **A suspected defect is registered, and not fixed in passing.** A fix made in passing is unreviewed and hides
  inside the change it interrupted.

## Start

Python 3.10 or newer, standard library only; the package is `airone-status`, MIT, with no dependencies.

1. Copy [templates/status.md](templates/status.md) and [templates/closed.md](templates/closed.md) into the
   project's documentation folder, and install the checker from the kit: `pip install ./status` gives the command
   `check-status`. The rules are the templates' headers; edit them only to fit the project's words. The checker,
   [tools/check_status.py](tools/check_status.py), also runs as a script from the kit without installing; it is
   never copied into the project. *A copied checker is a second copy that the kit's next version does not reach.*
2. Declare the families in the status file's `status-meta` block, one line each, a code and what it covers:

   ````markdown
   ```status-meta
   families:
     APP: the application
     DOC: the documentation
   ```
   ````

   A code is 2 to 5 capitals or digits starting with a capital, or two codes joined by a hyphen when the project
   wants a repository and an area (`WEB-API`). An ID is the family and a three-digit counter: `APP-001`.
3. Run the checker:

   ```sh
   check-status docs/status.md docs/closed.md
   ```

   ```text
   docs/status.md: 0 open item(s); docs/closed.md: 0 closed item(s)
   next free ID per family:
     APP-001
     DOC-001
   0 error(s)
   ```

4. Register an item under its section, taking the ID the checker printed:

   ```markdown
   ## Awaiting your decision

   | ID | Kind | Title | Reason | Owner | Trigger or question | Opened |
   |---|---|---|---|---|---|---|
   | `APP-001` | decision | Export format for reports | [design.md §4](design.md) | owner | CSV, or JSON lines? | 2026-01-05 |
   ```

   When it closes, its row leaves the status file and a row goes into the closed file, saying what was chosen:

   ```markdown
   | ID | Kind | Title | Outcome | Chosen | Reopen if | Reason | Closed |
   |---|---|---|---|---|---|---|---|
   | `APP-001` | decision | Export format for reports | done | JSON lines; ❌ CSV, which cannot hold nested fields | a consumer needs a spreadsheet | [design.md §4](design.md) | 2026-01-12 |
   ```

The checker exits non-zero on any error, so it can run in a hook or in CI. What it checks: IDs unique across both
files, of a declared family and of the form `FAMILY-nnn` (a gap is not an error, a reuse is); a closed item only in
the closed file; kinds, sections and outcomes from their closed sets; an owner on every open item, a trigger on every
deferred one, a question on every one awaiting a decision; a link in every reason; real dates; a superseded item
naming what superseded it; every item ID cited in either file existing in one of them. Each rule and its reason is in
the templates.

## With the specification graph

An item may cite a graph node by its ID, in backticks: *"`APP-004` builds what `REQ-02` requires"*. A node never
cites an item: a node states what holds, which outlives the work, and a citation of work inside it goes stale when the
work closes. Give the graph file to check both directions:

```sh
check-status docs/status.md docs/closed.md --graph graph.yml
```

Every cited node must then exist in the graph, no node may mention an item's ID, and no family of the status file
may share a code with a graph family, since a citation of either would be ambiguous. Without `--graph`, a citation of
a node is allowed and not checked. The checker reads the graph file's text as `specgraph` writes it, without PyYAML.

## What it is not

- **Not a graph node.** It holds no statement that something is true; the decision it waits on becomes a node, or a
  section of a design document, when it is taken.
- **Not a changelog.** A closed item records what was chosen, not every step taken; the history of the work is in
  the commits and the session log.
- **Not a document index.** Its links are each item's reason; a document no item needs is not linked from it.

## Tests

From the repository's root, with pytest installed:

```sh
pytest status/tools
```

## Licence

MIT; see [LICENSE](../LICENSE).
