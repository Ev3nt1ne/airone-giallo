---
name: commit
description: What goes in one commit, which changes get their own, the checks before staging, the message. Load before any commit, tag or branch.
---

# Committing on a long project

**Every commit is a consistent state the project could publish**: the documents agree (`doc-discipline`), the
checks report no errors, the code builds and its tests pass. *A bisect must never land on a broken tree, and a
reader of the history must be able to trust when a thing became true.* Each rule carries its reason in italics.

A half-done task is no excuse for an inconsistent tree. In-progress markers and a DRAFT header make "in progress" a
consistent state: commit an honest checkpoint, marked as such. Never end a session with finished work uncommitted.
*Work that exists only in a working tree is lost to the next session, which cannot see it.*

## 1. The unit: one logical task, with its bookkeeping

- A deliverable travels with the bookkeeping it caused: the ticked items, the tracker rows, the change-note lines.
  They are one change.
- Never a separate "update the docs" commit for work done in the same session. *It makes the history say the
  thing became true later than it did, and the commit that did the work looks incomplete.*
- Never two unrelated tasks in one commit. *Reverting one then takes the other with it.*
- A document that reports or tracks a code change ships with the code. A document that is itself the deliverable
  gets its own commit.

## 2. Changes that get a commit of their own

| Change | Rule | Why |
|---|---|---|
| A decision, or a change to the specification | its own commit; the body says whether the cascade was read and what it showed | *the most valuable history: it must be findable alone and never share a commit with routine work* |
| A gate | its own commit with nothing else in it, plus an annotated tag (`git tag -a <name> -m "…"`) | *gates are where the project re-baselines; a tag makes each one addressable* |
| The registry | never alone and never left behind: a new identifier commits with the text that uses it, a recomputed check value with the edit that changed the statement | *a registry entry without its text, or text without its entry, is an inconsistency the check may not see* |
| Evidence a gate will rest on | lands on the main line even when the code that produced it is thrown away | *the code is disposable, the evidence is not* |

The registry rule has one exception: work on the registry's own machinery.

## 3. Before staging: run the checks, never recall them

```sh
<the project's check>     # zero errors
git status                # no strays, no forgotten bookkeeping, nothing unrelated staged
git diff --cached --stat  # does this match one logical task?
```

1. **The project's checks report zero errors.** A fix they require (with the specification graph,
   `specgraph lint --fix` after a statement changed) goes in this commit, never the next.
2. **The documents agree** for everything the commit touches, and their change notes have their line.
3. **Status markers say what is true**: done, in progress, not started.
4. **The full suite runs locally before any commit that changes code**, where the continuous integration does not
   run everything on every push. *A check that runs nowhere before the commit runs first on the main line.*
5. **A changed dependency manifest runs the project's dependency checks.** *One new dependency can change how
   everything else builds.*
6. **While anything writes into the tree, stage files by name, never `git add -A`.** *A running job's temporary file
   rides into a commit that never named it.*
7. **A new script has its executable bit** (`git update-index --chmod=+x <file>`).
8. **The message is written** (§4).

## 4. The message

- **Subject**: imperative, about 72 characters at most, carrying the identifiers the commit touches. *Identifiers
  are the project's addresses; `git log --grep` finds a subject that names one and misses one that describes it.*
- **Body**: the *why*, never a restatement of the diff; which documents were kept in sync; what verification ran.
  Every claim in it ("all tests pass", "no behaviour change") gets the second pass like any other (`verify` §10).

```text
REQ-04, DEC-cache-ttl: bound a cached entry's life to one session

A cached entry outlived a permission change and served a revoked user.
Specification and plan updated together; registry entry minted here.
Cascade read before the edit: two requirements warned, none failed.
Checked: full test suite, the lint, a planted stale entry now refused.
```

## 5. Branches and history

- **Shared history is append-only.** Never rebase, amend or force-push anything another person or machine has seen;
  fix a mistake with a new commit. *Rewritten history breaks every clone and every citation of a hash.*
- Routine linear work commits directly to the main line. Branch for exploratory, risky or discardable work: short
  lived, merged when its checks pass, deleted after.
- **Two sessions in one checkout share one working tree.** Do not stash, pull with rebase or reset while the other
  session has uncommitted files: fetch, compare with the remote, check that nothing is staged, then
  `git commit --only -- <your files>`. *Stashing another session's files disturbs work you cannot see.*

## 6. What never goes in a commit

- **A secret of any kind**: a key, a token, a password, in code, a document, a pasted log or a message. *Once
  committed, it is in every clone and every copy of the history, and removing it means rewriting both.*
- **Temporary and scratch files.** Keep `.gitignore` current rather than cleaning up after the fact.
- **Another session's work.** Stage only the files you changed, by name. *A commit that carries someone else's
  half-done edit publishes it under your message.*
- **Generated output that can be reproduced.** A script's table lives in the document that interprets it, and the
  script beside it, not as a separate dump.

## Adapting this to your project

Fixed: every commit a consistent state; one logical task with its bookkeeping; decisions and gates in commits of
their own; the registry never alone; the checks run before staging, not recalled; identifiers in the subject and
the why in the body; shared history append-only; no secrets, no scratch, no one else's work.

Slots the project fills in its instruction file: the check commands and the local suite; its identifier families;
the continuous integration's tiers, what a push runs, and when a full run is owed and where its id is recorded;
its remotes and who pushes to them; the attribution trailer, if any; how gate tags are named; its status markers.

Evolving: a rule is added from a named commit that broke something, with its reason beside it; a rule not needed
for a long while is removed. *A checklist recited from memory is a checklist skipped.*
