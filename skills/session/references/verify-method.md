# Establishing that a claim is true

The method behind every claim a session records or acts on: a number in a document or a test, "the build is
reproducible", "everything was handled". A wrong measurement is usually a *stable* wrong measurement: it reproduces
perfectly, so reproducing it proves nothing. The second pass over a change is in the skill's §6; this file is what
that pass and every measurement rest on. Each rule carries its reason in italics.

## 1. Measure the artifact, never the command that produces it

Run the built program, read the produced file, compare the actual bytes; keep build tools, test runners and package
managers out of the measurement path. A throughput counts what landed, not what the harness sent. *A timing taken
through a test runner measures the runner's start-up, and a comparison piped through a text filter can compare what
the filter left, not the files.*

## 2. The negative control

A green that has never been contrasted with a red is not evidence. Three kinds:

- **No work:** the same code path at size zero. *Whatever the empty run still costs is the harness.*
- **A planted failure:** seed the violation the check exists to refuse, and see it refused. *It proves the gate
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
| a script edited every match | classify each edit (a constructor, or a pattern that only looks like one) |
| a web summary quotes a page | save the raw page and grep for the exact words |
| a scorer's verdict | the raw lines it summarizes |
| a count in the previous record | the command that counts, run again |

## 4. One variable per process; the spread, not a point

- A high-water mark (peak memory, a maximum) never decreases in a process: one size per process.
- Arms run in blocks measure warm-up and drift: rotate the arms within each repetition, then take medians. An arm's
  assignment must not move in step with the system's own schedule: draw it from a mix and record the variable that
  could alias.
- A percentile names its rule (nearest rank, interpolated); *two rules give two medians at an even count.*
- If the difference between arms is inside the spread within an arm, the measurement does not resolve it and no
  claim is made: say so; *that is a result.* A number that moves between runs is quoted as a range; where absolutes
  drift and ratios hold, the ratios are the result.

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

- Distinguish the mutations from each other: *a failure should say which thing broke.*
- A mutation that ran no test, or never reached its branch, tested nothing: check what each one ran before scoring it.
- A claim about the whole suite needs the caught-by table: each mutation against the tests that failed on it.
- A mutation that reveals a missing observable (a counter the code never kept) is a finding.
- A mutation spec anchored on source text checks that each anchor matches exactly once before it runs.
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

## 9. Hidden nondeterminism in dependencies

A project's lint can ban clocks, unordered maps and entropy in its own code; it cannot see into a dependency, and
one clock read in a logging library breaks a reproducibility claim. Run the audit when determinism is claimed and
again whenever a dependency is added or upgraded.

1. **Enumerate** every dependency on a runtime edge, with the package manager's graph command and its runtime
   filter, not the manifest, which omits what is pulled in transitively. *Development-only dependencies cannot
   reach a run and bury the real candidates.*
2. **Grep the hazard classes**, with the patterns kept in the script, not in a document:

   | Class | What to look for |
   |---|---|
   | time | clock reads, sleeps, timers, timestamps added by loggers |
   | iteration order | hash maps and sets whose order depends on a seed or on insertion history |
   | entropy | randomness seeded from the operating system, random hash keys, UUID generation |
   | per-thread state | thread-local caches, thread ids, work stealing that changes order |
   | address dependence | pointer values used as keys or hashes, sorting by address, allocation order |

   The script greps a known positive and a known negative first, and stops if either comes out wrong. *An empty
   result is otherwise indistinguishable from a broken grep.*

   ```sh
   for f in audit-fixtures/positive.*; do grep -qE "$PATTERNS" "$f" || { echo "pattern missed $f"; exit 2; }; done
   for f in audit-fixtures/negative.*; do grep -qE "$PATTERNS" "$f" && { echo "pattern hit $f"; exit 2; }; done
   ```

3. **Read every hit**; the grep prints candidates, not defects. Record a verdict with its reason: *reachable*,
   *unreachable* (with what makes it so) or *deterministic* (a hash keyed by a constant seed). A reachable hit is a
   finding before any run has shown it. Score the hazards predicted before the audit (§8).
4. **Keep the output beside the lock file's commit.** *The audit holds for one lock file, not for the project:
   where features are unified across the graph, a later dependency can switch on entropy in an audited one.*

## 10. Before recording a number

- [ ] The artifact was measured, not the command.
- [ ] A negative control ran and came out as it had to.
- [ ] One variable per process; arms interleaved.
- [ ] The spread is reported, or the claim withheld.
- [ ] Thresholds derived, the derivation in the test.
- [ ] Every new test seen failing on its mutation.
- [ ] Predictions scored.
- [ ] Every signifier resolved: hashes, refs, paths, cited passages, counts.
- [ ] The producer is committed, beside the figure or in a tools folder; a workload shared by a test and a
  benchmark lives in one file. *A figure whose producer lives in a transcript cannot be re-run.*
