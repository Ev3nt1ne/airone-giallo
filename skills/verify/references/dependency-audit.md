# Auditing dependencies for hidden nondeterminism

For a project that claims a run is reproducible: the same seed and inputs give the same output, byte for byte.
Its own code can be held to that by a lint; its dependencies cannot, and one clock read in a logging library is
enough to break the claim. The audit has three parts: enumerate, grep, read.

## 1. Enumerate what can reach a run

List every dependency on a runtime edge of the dependency graph. Development-only and build-only dependencies
cannot reach a run's output and are left out; *including them buries the real candidates in noise.* Use the
package manager's own graph command with its runtime filter, not the manifest, which omits what is pulled in
transitively.

## 2. Grep the hazard classes

| Class | What to look for |
|---|---|
| time | wall-clock and monotonic clock reads, sleeps, timers, timestamps added by loggers |
| iteration order | hash maps and sets whose order depends on a seed or on insertion history |
| entropy | randomness seeded from the operating system, random hash keys, UUID generation |
| per-thread state | thread-local caches, thread ids, work stealing that changes order |
| address dependence | pointer values used as keys or hashes, sorting by address, allocation order |

Each language spells these differently; write the patterns for yours, and keep them in the script, not in a
document.

The script checks its own patterns before it reports: it greps a known positive (a small file that contains each
hazard) and a known negative (one that contains none), and stops if either comes out wrong. *An empty result is
otherwise indistinguishable from a broken grep.*

```sh
# the self-check, before the real run
for f in audit-fixtures/positive.*; do grep -qE "$PATTERNS" "$f" || { echo "pattern missed $f"; exit 2; }; done
for f in audit-fixtures/negative.*; do grep -qE "$PATTERNS" "$f" && { echo "pattern hit $f"; exit 2; }; done
```

## 3. The audit is the reading, not the grep

The grep prints candidates, not defects. Most hits are comments, test bodies, or code for types the project never
constructs. Read each hit and record a verdict with its reason: *reachable* (the project's runs call it),
*unreachable* (with what makes it so), or *deterministic* (for example, a hash keyed by a constant seed fixed at
compile time). A reachable hit is a finding even if no run has shown it yet: *the default logger that stamps every
line with the time makes the trace differ between runs before any threading is involved.*

Score each hazard predicted before the audit as refuted, confirmed or understated (the skill's §9).

## 4. Re-run on change

Re-run the audit whenever a dependency is added or upgraded, and keep its output beside the lock file's commit.
Where the package manager unifies optional features across the graph, a dependency added later can switch on an
entropy feature in one audited earlier; *the audit holds for one lock file, not for the project.*
