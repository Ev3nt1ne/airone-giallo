---
name: verify
description: How to establish that a claim is true before recording it or building on it. Load before recording a number or a threshold, when a test fails, and for a second pass.
---

# Establishing that something is true

For every claim an agent records or acts on: a figure in a document, a threshold in a test, "the build is
reproducible", "everything was handled". A wrong measurement is usually a *stable* wrong measurement: it reproduces
perfectly, so reproducing it proves nothing. Each rule carries its reason in italics.

## 1. Measure the artifact, never the command that produces it

Run the built program, read the produced file, compare the actual bytes; keep build tools, test runners and package
managers out of the measurement path. *A timing taken through a test runner measures the runner's start-up, and a
comparison piped through a text filter can compare what the filter left, not the files.*

## 2. Always run a negative control

A green that has never been contrasted with a red is not evidence. Three kinds:

- **No work:** the same code path at size zero. *Whatever the empty run still costs is the harness.*
- **A planted failure:** seed the violation the check exists to refuse, and see it refused. *It proves the gate
  bites, not only that it passes.*
- **The clean arm:** run the variant that must not show the effect beside the one that must. *If both differ, the
  difference is not the cause you named.*

After writing any comparison pipeline, feed it two inputs known to differ before trusting its PASS. A control checks
its own precondition, or it passes without having run.

Example: to time a routine at *n* items, a small program, built as it ships, runs it at one *n* per process and
prints the time and peak memory; it runs at *n* = 0 too. A row that does not fall away at zero is measuring the
program around the routine.

## 3. Resolve a signifier to its contents

A name, a commit subject, a branch ref, a table of contents, a file's presence are signifiers: that one exists says
nothing about what it holds. Resolve it with a command that reads the contents. *A claim that "it is pushed" because
the remote branch exists, or "the commit added the tool" because its subject says so, has nothing under it but the
name, and each copy of it is taken from the last.*

| Signifier | What reads the contents |
|---|---|
| a remote branch exists | `git log origin/main..HEAD --oneline` |
| a commit subject names files | `git show --stat <sha>` |
| a hash you remember | `git cat-file -t <sha>` |
| a file is in the repository | `git ls-files <path>`, which sees what `.gitignore` hides from you |
| a document covers a point | open it and read the passage |
| a lint rule reaches every module | plant a violation in each module it should reach |
| a script edited every match | classify each edit (a constructor, or a pattern that only looks like one) |
| a web summary quotes a page | save the raw page and grep for the exact words |

Resolve the number too: a count copied from the previous record is a signifier of the count.

## 4. One variable per process, arms interleaved

- A high-water mark (peak memory, a maximum) never decreases in a process: one size per process.
- Arms run in blocks measure warm-up and drift: rotate the arms within each repetition, then take medians.
- A percentile names its rule (nearest rank, interpolated); *two rules give two medians at an even count.*

## 5. Report the spread, not a point

If the difference between arms is inside the spread within an arm, the measurement does not resolve it, and no
claim is made. Say so; *that is a result.* A number that moves between runs is not a measurement: quote what is
stable, or a range. Where absolutes drift and ratios hold, the ratios are the result.

## 6. Derive a test's numbers; never tune them

Every number in a test is derived, with its derivation written in the test. Derive the centre, measure the width,
and never write the check before the width is known. *A threshold adjusted until it passes encodes the current
behaviour, bugs included, and an invented band always looks principled.* State what the test cannot detect.

Example: a sampler draws *n* items with replacement from *n*. The covered share is derived as 1 − (1 − 1/*n*)^*n*,
about 0.632 at large *n*; 2,000 seeds measure σ; the band is the centre ± 4σ. Then the band is run against a sampler
broken to draw without replacement (share 1.0), and it fails.

## 7. A test counts once it has failed for the right reason

Every new test is re-run against the mutation it exists to catch: mutate the source, run, see it fail, restore
from a kept copy. *"It passes" says nothing; "it fails when the thing it guards breaks" is the evidence.*

- Distinguish the mutations from each other: *a failure should say which thing broke.*
- A mutation that ran no test, or never reached the branch it targets, tested nothing: check what each one ran
  before scoring it.
- A claim about the whole suite needs the caught-by table: each mutation against the tests that failed on it.
  *A round proves its mutations are caught, not that every test earns its place.*
- A mutation that reveals a missing observable (a counter the code never kept) is a finding.
- A mutation spec that anchors on source text checks that each anchor matches exactly once before it runs.

## 8. When a test fails, suspect the derivation before the code

Find why the expectation was wrong before touching the code or the assertion. Where the code is right and the
derivation missed a precondition, state the precondition. *A failing test "fixed" by moving the expectation
destroys the finding it handed you.* Before blaming a patch for a failure, run the unmodified code as many times.

## 9. Score every prediction

When a plan, a review or a handoff says what work will find, it is a hypothesis: score it **refuted**,
**confirmed** or **understated**. *Most of an audit's worth is in what it contradicts.* When every prediction is
refuted at once, suspect the measurement first.

## 10. The second pass

Two passes, always; nothing lands on the first. The second is claim by claim, never a re-read. *A re-read checks
that a text is coherent, not that it is true.*

1. List every claim the change makes: numbers, quotations, identifiers, hashes, citations, invariants stated in
   code comments, and every *all*, *every*, *none*, *only*.
2. Resolve each against its source, not against your draft. A fix made during the pass is a new claim.
3. Read the artifact, not a view of it: the changed text whole, never a truncated hunk; a grep anchored on the
   concept, with what it matched read (a case-insensitive grep matches inside other words; a search for the old
   wording misses a reworded passage).
4. Report what the pass found, including "nothing".

*False completeness is the expensive error: "everything was handled" is the sentence that stops the next reader
checking.* Correct such a claim in place.

## 11. Smaller rules

- Separate what a harness sent from what the system did: a throughput counts what landed.
- Check a scorer's verdict against the raw lines it summarizes.
- Label each benchmark arm with what it models, not what it resembles.
- A fix that looks behaviour-neutral gets a differential test against the unmodified code, with a control showing
  the test can tell two versions apart.
- An arm's assignment must not move in step with the system's own schedule; draw it from a mix and record the
  variable that could alias.
- Run an upstream project's checks with its own pinned toolchain before offering it a patch.
- A recorded figure's producer is committed in the repository, beside it or in a tools folder; a workload shared by
  a test and a benchmark lives in one file. *A figure whose producer lives in a transcript cannot be re-run, and a
  copied workload drifts from the assertion that guards it.*

## 12. Hidden nondeterminism in dependencies

A project's lint can ban clocks, unordered maps and entropy in its own code; it cannot see into a dependency. The
audit (what to enumerate, the hazard classes, a self-checking grep, reading the hits) is in
[references/dependency-audit.md](references/dependency-audit.md). Run it when determinism is claimed and again when
dependencies change.

## 13. Before recording a number

- [ ] The artifact was measured, not the command.
- [ ] A negative control ran and came out as it had to.
- [ ] One variable per process; arms interleaved.
- [ ] The spread is reported, or the claim withheld.
- [ ] Thresholds derived, the derivation in the test.
- [ ] Every new test seen failing on its mutation.
- [ ] Predictions scored.
- [ ] Every signifier resolved: hashes, refs, paths, cited passages.
- [ ] The producer is committed.

## Adapting this to your project

Fixed: the artifact and not the command; a negative control; signifiers resolved; derived, not tuned; a test seen
failing; predictions scored; two passes, the second claim by claim.

Slots the project fills in its instruction file: where measurements and their producers live; the mutation tool and
how a round is recorded; the percentile rule; the measuring machine and whether it may be in other use during a run;
the hazard classes its domain cares about (for a reproducible build, timestamps and paths; for a service,
perhaps locale and time zone); a claims-listing helper for the second pass, if it writes one.

Evolving: a rule is added from a named false verification, with its reason; a rule nobody has needed for a long
while is removed. *A checklist that grows without pruning is skimmed.*
