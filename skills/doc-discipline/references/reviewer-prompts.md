# Running a review: the method, the prompts and the worksheet

For a review the owner has said yes to, on one of the occasions in the skill's §5. A design, a report or a
recommendation is often written, summarized and graded by the same agent, and a self-assessment is not evidence: two
or three reviewers attack the material from opposite sides, and their findings are merged, tempered and handed to
the owner to rule on. Each rule carries its reason in italics.

## Roles and cuts

Two or three reviewers, never one, except in the evidence cut. *One reviewer produces a critique; opposed reviewers
produce convergence, and convergence is what the owner can act on.*

| Role | Attacks |
|---|---|
| **R1, the mechanism** | the design: does the claimed defence defend, what does a hostile or careless participant do that was never modelled |
| **R1b, the other side** | the same design from the opposite seat: the clients against the server, the users against the operators |
| **R2, the feasibility sceptic** | the shape of the plan: the real team and timeline, adoption, whether a cheaper scope gets most of the value |
| **R3, the evidence auditor** | the provenance of every figure: re-run it, check its sensitivity, a model reported as a measurement |

| Cut | Roles | For occasion |
|---|---|---|
| **full** | R1, R2, R3 | a gate recommendation, a stage report (2) |
| **mechanism** | R1, R1b | a design recorded before it is built (1, 3) |
| **evidence** | R3 alone, with its own second pass | a figure about to become evidence (5) |
| **code** | R1 and R3 on the code, reading the tests as claims and planting the gaps they name | a security surface (4) |

Add R3 to any cut whose material carries numbers. Ask the owner for the cut only when the occasion does not decide
it.

## Running them

- **Name the target precisely**: a file and a range of sections, plus the notes it rests on. *"Review the design"
  gives each reviewer a different target, and nothing converges.*
- **Collect what the material declares it does not claim** (carried risks, stated limits, known residuals) and give
  every reviewer the list. *A reviewer who rediscovers a declared limit wastes a round and costs the review its
  credibility.*
- **A different model from the author's**, where you can. *A reviewer of the same lineage shares the author's blind
  spots.*
- Each reviewer gets the common brief and its role's prompt, below, filled in, and runs independently: none sees
  another's output. *Two reviewers who read each other agree by imitation, and the convergence means nothing.*

## The merge, where the value is

Never concatenate the reports; write one worksheet (the template is at the end).

1. **Group by theme**, not by reviewer.
2. **Merge duplicates and list the convergences first.** *Two reviewers reaching the same wall from opposite
   directions is the strongest signal the exercise produces.*
3. **Temper every finding yourself**, in a required column. *Reviewers overreach, and an untempered list is
   discounted wholesale.* **SOLID**: it stands. **PARTLY**: real, but overstated, mis-scoped, or with a cheaper
   answer. **OVERREACH**: weak, double-counted, or arguing against a decision taken on non-technical grounds.
   **CHALLENGES A DECISION**: flagged so the owner treats it deliberately.
4. **Give each SOLID finding a direction, not a fix.** *A fix written in advance pre-empts the ruling.*
5. **Say what survived.** *A review that reports only wounds is not a measurement.*

## Where the output goes

- A new file in the project's reviews folder, `<target>-<date>.md`, written by the `markdown-docs` rules, with
  `trigger:` and `cut:` in its frontmatter and, at triage, the count of findings that changed something. *After a
  few reviews, those fields say which occasions earn their cost.*
- Nothing is written into the specification, the plan or the registry before the owner rules; the owner's answers
  are transcribed into the worksheet as given, then applied.
- The worksheet is archived only when nothing in it is outstanding (`handoff` §6). A finding that outgrows triage
  becomes its own document, for a session of its own.

## What a review must not do

- **A reviewer that edits**: it removes the owner's triage and mixes finding with fix.
- **A quota** ("find ten issues"): it manufactures overreach and buries the solid findings.
- **A finding without a failure scenario**: it cannot be falsified, ruled on or acted on.
- **The document's own confidence taken as evidence**: the self-grade is what is under review.

## The prompts

Each reviewer's prompt is the common brief followed by its role's prompt. Replace each `<…>`; keep the rest as it is.

### The common brief

```text
You are reviewing <target: file, sections, and the notes it rests on> in the repository at <path>.
You may read anything in the repository. Read <the project's rules files> first, so that you attack the
argument and not the house style.

READ-ONLY. Do not edit, create, commit or write to any file, the registry included. Report only;
a reviewer who fixes things removes the owner's triage step.

Provenance: this material was written, and in places graded, by an agent. Its marks of confidence
(ticks, "verified", "passes") are the author's own. Part of your job is to find the unearned ones.

What the material declares it does NOT claim (do not report these as findings):
<the carried risks, stated limits and known residuals, one per line>

Premises, out of scope: <the owner's non-technical decisions>. You may challenge how a premise is
implemented. You may flag a premise itself, marked PREMISE, but not argue it away.

Every finding:
- cites file and line;
- gives a concrete failure scenario: the inputs, the state, and the wrong outcome; a category of
  concern ("this may not scale") is not a finding;
- rates your confidence: high, medium or low, with one line on what would change it.

If a section survives your attack, say so and say why. Finding nothing in a section is a result.
Do not pad to a number.

Return: findings grouped by section, then the sections that survived, then anything you could not
check and why.
```

### R1, the mechanism

```text
Your role: the design and security architect. Attack the mechanism.
- For each defence the material claims, does it defend? Build the input or the sequence of events
  that gets through it.
- What does a hostile or careless participant do that the analysis never modelled? Consider who
  can send what, when, how often, and in what order.
- Where does a bound or a guarantee assume the adversary is polite: answers on time, honest
  timestamps, inputs of the expected size, no collusion?
- Where the design declares places it holds on (<the project's places: environments, editions,
  scales>), is any defence carried to a place where its premise fails?
```

### R1b, the mechanism from the other side

```text
Your role: a second mechanism reviewer, sitting on the other side from R1: <the two sides, for
example the clients against the server, or the users against the operators>. Ask R1's questions
from the side R1 does not take: what can this side do to the system, and what can the system do to
this side that the design does not admit?
```

### R2, the feasibility sceptic

```text
Your role: the feasibility and delivery sceptic. Attack the shape of the plan, not the mechanism.
- With the real team (<size>) and the real timeline, which stage does not fit, and what slips?
- Who has to adopt this, and what would stop them?
- Does what is being built serve the stated purpose (<purpose>), or a neighbouring one?
- Is there a cheaper scope that gets most of the value? Name it and what it gives up.
```

### R3, the evidence auditor

```text
Your role: the evidence auditor. Attack the provenance of every figure.
- For each number: does it come out of the cited script or measurement, or is it asserted near a
  citation? Re-run the script where you can, and report what it prints.
- Does a claimed sensitivity or margin hold when the inputs move within their stated range?
- Is a model or a simulation reported as a measurement?
- Which system produced the figure, and is it used for a place or a configuration that system
  stands for?
- Finish with your own second pass: list every figure you checked and its verdict (reproduced,
  differs, cannot be reproduced, not checked).
```

### The code cut, added to R1 and R3

```text
The target is code. Read the tests as claims: for each, what would have to break for it to fail?
Where a test claims to guard something it cannot see, plant the gap it names (a minimal change to
the code that the test should catch) in a scratch copy, run the tests, and report whether they
caught it. Never leave a planted change in the working tree.
```

## The triage worksheet

```markdown
---
title: Review of <target>
description: <cut> review of <target>; <n> findings, triage <pending | done>.
type: review
trigger: <occasion n, or the owner's request>
cut: <full | mechanism | evidence | code>
created: <YYYY-MM-DD>
updated: <YYYY-MM-DDTHH:MM:SS+00:00>
---

# Review of <target>

> Status: <untriaged | triaged | applied | archived>, <date>. Findings that changed something:
> <k> of <n>.

## Convergences

- **<theme>**: R1 <finding>, R3 <finding>. <why they are the same wall>.

## Findings by theme

| # | Theme | Finding, with file:line and failure scenario | From | Temper | Direction |
|---|---|---|---|---|---|
| 1 | <theme> | <finding> | R1 (high) | SOLID | <where the answer probably lies> |

## What survived

- <section>: <why it held>.

## Owner's answers

- **#1**: <the owner's answer, as given>.

## Disposition

| # | Applied in | What changed |
|---|---|---|
```
