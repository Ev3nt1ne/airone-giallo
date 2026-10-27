---
name: adversary
description: Opposed reviewers against a deliverable, their findings tempered into a triage sheet for the owner. Load when asked to red-team something, or to propose a review on its listed occasions.
---

# Red-teaming a deliverable

On a project worked by agents, a design, a report or a recommendation is often written, summarized and graded by
the same agent. A self-assessment is not evidence. This skill sets two or three reviewers against the material from
opposite sides, merges what they find, and hands the owner a sheet to rule on. The reviewer prompts and the
worksheet are in [references/reviewer-prompts.md](references/reviewer-prompts.md). Each rule carries its reason in
italics.

**Never launch a review unasked.** A document that looks weak is a reason to ask the owner, not to spend their
budget. *A review costs the owner a triage as well as the tokens; it is theirs to order.*

## 1. When to propose one

Propose it in one line (§2) when one of these holds, and otherwise do not raise it:

1. **A decision is recorded before its design**: a direction with nothing yet satisfying it and no evidence for it.
   Propose it before the work that builds the decision starts. *A flaw found in a design costs a paragraph; found
   in built code, it costs the code.*
2. **A gate recommendation is drafted** (`doc-discipline` §5).
3. **Where the project uses the specification graph** (`graph/` in this kit): a batch makes a node newly hold on a
   place where a threat is undefended, or a new satisfier makes a condition hold. `specgraph batch` lists these as
   review occasions. *The engine shows the graph consistent; only a review says whether the support is enough.*
4. **Code with a security surface lands**: a cache, a parser, an export format, anything a peer can feed.
5. **A measurement is about to become evidence** that a decision rests on.

## 2. Before spawning anything

1. **Propose it in one line the owner can answer yes or no**: the occasion, the target by file and section, the cut
   (§3), the rough cost (reviewers, model, minutes), and what the review cannot catch. For example: *"Occasion 1:
   the session-cache decision has no design yet. Mechanism cut, two reviewers on `SPEC` §4.3 and the cache note
   §2, about forty minutes on a smaller model; it will not say what the time-out should be, which needs a
   measurement. Go?"*
2. **Name the target precisely**: a file, or a file and a range of sections, plus the notes it rests on. *"Review
   the design" gives each reviewer a different target, and nothing converges.*
3. **Pick the cut.** Ask the owner only when the occasion does not decide it, typically whether to attack the
   recommendations alone or the evidence under them too.
4. **Collect what the deliverable declares it does not claim**: carried risks, stated limits, known residuals. Each
   reviewer gets that list. *A reviewer who rediscovers a declared limit wastes a round and costs the review its
   credibility.*
5. **Use a different model for the reviewers from the one that produced the material**, where you can. *The point is
   an independent prior; a reviewer of the same lineage shares the author's blind spots.*

## 3. Roles and cuts

Two or three reviewers, never one, except in the evidence cut. *One reviewer produces a critique; opposed reviewers
produce convergence, and convergence is what the owner can act on.*

| Role | Attacks | Asks |
|---|---|---|
| **R1, the mechanism** | the design | Does the claimed defence defend? What does a hostile or careless participant do that the analysis never modelled? Where does a bound assume a polite adversary? Where the design declares places (environments, editions, scales), is a defence carried to a place where its premise fails? |
| **R1b, the mechanism from the other side** | the same design | R1's questions from the opposite seat: the clients against the server, the users against the operators. |
| **R2, the feasibility sceptic** | the shape of the plan | The real team and the real timeline, adoption, whether what is built serves the stated purpose, and whether a cheaper scope gets most of the value. |
| **R3, the evidence auditor** | the provenance of every figure | Does this number come out of the cited script, or was it asserted near a citation? Re-run it. Does the claimed sensitivity hold? Is a model reported as a measurement? Which system produced the figure, and is it used for a place that system stands for? |

| Cut | Roles | For |
|---|---|---|
| **full** | R1, R2, R3 | a gate recommendation, a stage report |
| **mechanism** | R1, R1b | a design recorded before it is built (occasions 1 and 3) |
| **evidence** | R3 alone, with its own second pass | a figure about to become evidence (occasion 5) |
| **code** | R1 and R3 on the code only, reading the tests as claims and planting the gaps they name | code with a security surface (occasion 4) |

Add R3 to any cut whose material carries numbers.

## 4. Running them

Each reviewer gets the common brief and its role's prompt, from the reference file, with the target and the
declared limits filled in. The brief makes every reviewer read-only, has every finding cite a file and line with a
concrete failure scenario, asks for an honest negative where a section survives, asks for a confidence on each
finding, and puts the owner's non-technical decisions out of scope as premises.

Run them independently: none sees another's output. *Two reviewers who read each other agree by imitation, and the
convergence means nothing.*

## 5. Merging: the part that carries the value

Never concatenate the reports. Write one triage worksheet:

1. **Group by theme**, not by reviewer; the themes come from the material.
2. **Merge duplicates and say they converged; list the convergences first.** *Two reviewers reaching the same wall
   from opposite directions is the strongest signal the exercise produces.*
3. **Temper every finding yourself**, in a required column. *Reviewers overreach, and an untempered list is
   discounted wholesale.*
   - **SOLID**: the finding stands.
   - **PARTLY**: real, but overstated, mis-scoped, or with a cheaper answer than it implies.
   - **OVERREACH**: weak, double-counted, or arguing against a decision taken on non-technical grounds.
   - **CHALLENGES A DECISION**: flagged so the owner treats it deliberately, not by reflex.
4. **Give each SOLID finding a direction, not a fix**: one line on where the answer probably lies. *The owner rules;
   a fix written in advance pre-empts the ruling.*
5. **Say what survived.** *A review that reports only wounds is not a measurement.*

## 6. Where the output goes

- A new file in the project's reviews folder, `<target>-<date>.md`, written by the `markdown-docs` rules. Its
  frontmatter carries `trigger:` (the occasion, or the owner's request) and `cut:`. At triage, a line in its status
  header counts the findings that changed something (a statement, a text, a test) against all of them. *After a few
  reviews, those two fields say which occasions earn their cost.*
- **Nothing is applied before the owner rules.** No finding is written into the specification, the plan or the
  registry until then. The owner's answers are transcribed into the worksheet as given, beside the findings they
  answer, then applied.
- The worksheet is a session record, archived only when nothing in it is outstanding and nothing lives only there
  (`handoff` §6).
- A finding that outgrows triage becomes its own document, for a session of its own.

## 7. What a review must not do

| Never | Why |
|---|---|
| one reviewer | a critique, not convergence: the merge has nothing to merge |
| a reviewer that edits | it removes the owner's triage and mixes finding with fix |
| a quota ("find ten issues") | it manufactures overreach and buries the solid findings |
| a finding without a failure scenario | it cannot be falsified, ruled on or acted on |
| a review blind to what the material declares it does not claim | it rediscovers carried risks and loses credibility |
| the document's own confidence taken as evidence | the self-grade is what is under review |
| findings applied before the owner rules | decisions and specification changes are the owner's |

## Adapting this to your project

Fixed: never launched unasked; proposed in one line with its cost; two or three opposed reviewers, read-only and
independent; findings cited with a failure scenario; every finding tempered; convergences first; what survived
stated; nothing applied before the owner rules.

Slots the project fills in its instruction file: the occasions, with the graph occasion only if it uses the graph;
the reviews folder and its file name; the rules files a reviewer reads first; the owner's premises a reviewer may
flag but not overturn; the places a design is judged on; the models available for review; the second mechanism
role's two sides.

Evolving: an occasion is added when a flaw a review would have caught reached the code, and dropped when the
`trigger:` counts show it rarely changes anything. *An occasion that never pays teaches the owner to say no to all
of them.*
