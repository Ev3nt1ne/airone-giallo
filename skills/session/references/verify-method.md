# Establishing that a claim is true

The method behind every claim a session records or acts on: a number in a document or a test, "the build is
reproducible", "everything was handled". A wrong measurement is usually a *stable* wrong measurement: it reproduces
perfectly, so reproducing it proves nothing. The second pass over a change is in the skill's §6; this file is what
that pass and every measurement rest on. Each rule carries its reason in italics.

## 1. Measure the artifact, never the command that produces it

Run the built program, read the produced file, compare the actual bytes; keep build tools, test runners and package
managers out of the measurement path. *A timing taken through a test runner measures the runner's start-up, and a
comparison piped through a text filter can compare what the filter left, not the files.*

## 2. The negative control

A green that has never been contrasted with a red is not evidence. Two kinds:

- **A planted failure:** seed the violation the check exists to refuse, and see it refused. *It proves the check
  bites, not only that it passes.*
- **The clean arm:** run the variant that must not show the effect beside the one that must. *If both differ, the
  difference is not the cause you named.*

Feed any new comparison pipeline two inputs known to differ before trusting its PASS. A control checks its own
precondition, or it passes without having run.

## 3. Resolve a signifier to its contents

A name, a commit subject, a branch ref, a table of contents, a file's presence are signifiers: that one exists says
nothing about what it holds; resolve it with a command that reads the contents. *A claim with nothing under it but
a name gets copied from record to record.*

| Signifier | What reads the contents |
|---|---|
| a remote branch exists | `git log origin/main..HEAD --oneline` |
| a commit subject names files | `git show --stat <sha>` |
| a hash you remember | `git cat-file -t <sha>` |
| a file is in the repository | `git ls-files <path>`, which sees what `.gitignore` hides from you |
| a document covers a point | open it and read the passage |
| a lint rule reaches every module | plant a violation in each module it should reach |
| a web summary quotes a page | save the raw page and grep for the exact words |
| a tool's summary or verdict | the raw output it summarizes |
| a count in the previous record | the command that counts, run again |

## 4. The spread, not a point

- Variants compared are interleaved, not run one block after the other, and the spread is reported. *Blocks measure
  warm-up and drift as if they were the difference.*
- If the difference between arms is inside the spread within an arm, the measurement does not resolve it and no
  claim is made: say so; *that is a result.* A number that moves between runs is quoted as a range.

## 5. Derive a test's numbers; never tune them

Every number in a test is derived, with its derivation written in the test. Derive the centre, measure the width,
and never write the check before the width is known. State what the test cannot detect. *A threshold adjusted until
it passes encodes the current behaviour, bugs included, and an invented band always looks principled.*

Example: a sampler draws *n* items with replacement from *n*. The covered share is 1 − (1 − 1/*n*)^*n*, about
0.632 at large *n*; 2,000 seeds measure σ; the band is the centre ± 4σ. Run against a sampler broken to draw without
replacement (share 1.0), the band fails.

## 6. A test counts once it has failed for the right reason: the mutation round

Every new test is re-run against the mutation it exists to catch: mutate the source, run, see it fail, restore from
a kept copy. *"It passes" says nothing; "it fails when the thing it guards breaks" is the evidence.*

- A mutation that ran no test, or never reached its branch, tested nothing: check what each one ran before scoring it.
- A claim about the whole suite rests on each mutation's result, not on a sample.
- A fix that looks behaviour-neutral gets a differential test against the unmodified code, with a control showing
  the test can tell two versions apart.

## 7. When a test fails, suspect the derivation before the code

Find why the expectation was wrong before touching the code or the assertion; where the code is right and the
derivation missed a precondition, state the precondition. Before blaming a patch, run the unmodified code as many
times. *A failing test "fixed" by moving the expectation destroys the finding it handed you.*

## 8. Score every prediction

What a plan, a review or a handoff says the work will find is a hypothesis: score it **refuted**, **confirmed** or
**understated**. When every prediction is refuted at once, suspect the measurement first. *Most of an audit's worth
is in what it contradicts.*

## 9. A property claimed of the whole program

A property claimed of the whole program (deterministic, offline, no telemetry) holds only if the dependencies on its
runtime path hold it too: check them, not only your own code. *A lint over your own code cannot see into a
dependency, and one clock read in a logging library breaks a reproducibility claim.*

## 10. Before recording a number

- [ ] The artifact was measured, not the command.
- [ ] A negative control ran and came out as it had to.
- [ ] Variants interleaved.
- [ ] The spread is reported, or the claim withheld.
- [ ] Thresholds derived, the derivation in the test.
- [ ] Every new test seen failing on its mutation.
- [ ] Predictions scored.
- [ ] Every signifier resolved: hashes, refs, paths, cited passages, counts.
- [ ] The producer is committed, beside the figure or in a tools folder. *A figure whose producer lives in a
  transcript cannot be re-run.*
