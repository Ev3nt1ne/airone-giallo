---
title: Register
description: What work is open, what waits on the owner's decision, what is accepted but not built and what is deferred until when; each item named by an ID that never changes, with a link to its reason.
type: register
created: <YYYY-MM-DD>
updated: <YYYY-MM-DDTHH:MM:SS+00:00>
tags: [register]
---

# Register

This file answers one question: what work is left, and what of it needs the owner first?

- **This file owns status.** No other document keeps a table of item states or marks an item open, waiting or
  done; where one disagrees with this file, this file is right and the other has drifted. *Status kept in two places is
  updated in one, and the reader cannot tell which.*
- **It holds work, not design.** Facts, requirements and the decisions in force live in the design documents (or
  the specification graph); an item links to where its reason lives. *A register that explains goes stale at the
  speed of the design and is read at the speed of the work.*
- **It indexes items, never documents.** *An index of documents goes stale as they move, and misleads with
  confidence.*
- **An item leaves when it closes**, into [closed.md](closed.md), recording the choice made. *A register too long
  to read whole gets skimmed, and the skim misses the item that mattered.*
- **A suspected defect found while reading code becomes an item here**, and is not fixed on the spot: it goes to
  *Awaiting your decision* when fixing it takes a judgement, to *Accepted* when the fix is plain. *A fix made in
  passing is unreviewed, and it hides inside the change it interrupted.*
- **An item may cite a graph node by its ID; a node never cites an item.** *A node states what holds, which outlives
  the work; a citation of work in it goes stale when the work closes.*

## How an item is identified

```register-meta
families:
  <CODE>: <what the family covers: a repository, or an area of one>
```

An ID is `<FAMILY>-<nnn>`. The family is one declared above: a code of 2 to 5 capitals or digits starting with a
capital, or two such codes joined by a hyphen (a repository and an area inside it). The counter runs per family,
three digits from `001`, more once past `999`.

- **An ID records only what is fixed when the item is born**: its family and its counter. *Kind, owner, urgency and
  status all move, so they are columns that can change, never parts of the name.*
- **An ID is never renumbered and never given to another item**, even when the first was withdrawn within the
  hour. *A reused ID makes every old citation point at the wrong item.*
- **When an item splits, the original is closed as `superseded`, under its own ID, naming the items that replace
  it; an item found to belong to another family keeps its ID.** *The ID names the item, wherever it turns out to
  belong.*
- **A family code, once declared, keeps its meaning.** *Given a second meaning, it would change the target of every
  citation already written.*
- **This file is the allocator.** The next ID in a family is the highest one in this file or the closed one, plus
  one, derived by the checker and never read from a number written down: *nothing catches a written-down number
  going stale.*

  ```sh
  python3 <tools>/check_register.py <this file> <the closed file>
  ```

- **Every place that discusses an item names it by its ID**: a design document, a commit message, a code comment.
  *A search for the ID then finds all of them.*

| Column | Holds |
|---|---|
| ID | the item's ID, in backticks |
| Kind | `decision` (the owner chooses between options), `question` (a fact to find out before anything is chosen), `defect` (something that behaves wrongly), `enhancement` (something new or better to build), `chore` (upkeep that changes no behaviour) |
| Title | the item in one line |
| Reason | a link to where the reason lives: a design section, a graph node's document, a log entry, a line of code |
| Owner | who moves it next |
| Trigger or question | awaiting a decision: the question put to the owner; deferred: the event that brings it back; accepted: when it is to be built, or empty |
| Opened | the date it was registered, `YYYY-MM-DD` |

## Awaiting your decision

Each of these is blocked until the owner chooses.

| ID | Kind | Title | Reason | Owner | Trigger or question | Opened |
|---|---|---|---|---|---|---|

## Accepted, not yet built

Nothing here is left to decide; what remains is the work.

| ID | Kind | Title | Reason | Owner | Trigger or question | Opened |
|---|---|---|---|---|---|---|

## Deferred, with a trigger

Set aside on purpose, until the named event happens. *Without a trigger an item is not deferred: nobody will
ever come back for it.*

| ID | Kind | Title | Reason | Owner | Trigger or question | Opened |
|---|---|---|---|---|---|---|

## Closed

Closed items, each with its choice and what would reopen it, are in [closed.md](closed.md). Search it before
deciding anything that may have been decided already.
