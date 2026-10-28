---
name: session
description: How a working session on a long project runs, from opening on the handoff to the close. Load when starting, resuming or closing work, putting a decision to the owner, before recording a number or a threshold, or when a test fails.
---

# A working session, end to end

A long project is worked in sessions by agents that start cold. Most of what goes wrong is a continuity failure:
a claim carried forward without being checked, a decision re-derived because nobody recorded why, a fact left in
one file that was then archived. This skill is the order of a session; `handoff` and the references beside this skill
hold the methods it calls on. Each rule carries its reason in italics.

## 1. Opening

Read the instruction file, then the handoff's state, then check what you will build on against the repository;
report where things stand in a few lines, and stop unless the owner's message already says what to do. Only then
the long documents, and only the parts the task needs. *A re-survey spends the session on what is already known
and reopens questions that were settled.*

- **The handoff exists so you do not re-derive.** A recorded ruling holds; build on it. A ruling on one question
  is not a ruling on its neighbours.
- **A handoff is a record, not a source.** It says what was true when written. Resolve anything you build on
  against the code or the specification; where a record disagrees with the specification, the specification wins and
  the disagreement is a finding to report. *A record repeats its errors as faithfully as its facts.*
- **A recommendation the owner has not ratified is a submission, not a record.** A report or a discussion file
  carries submissions; a plan, a specification or a decision record carries what was ruled. Asked what a report
  decided, the honest answer is that it decided nothing. *A quoted recommendation starts to read as a ruling.*
- **The project's map** (which document answers which question, the identifier families, the entry points) lives in
  its instruction file; until the setup skill writes it there, the template is
  [references/project-map-template.md](references/project-map-template.md).

## 2. Whose decision it is

Classify every decision before acting on it.

- **Technical, the agent's**: how to implement what is agreed, inside the rules already recorded, reversible by a
  commit. Decide, record the reason where the work is, report it.
- **Project, the owner's**: scope, priorities, cost, anything irreversible or public, anything that changes a
  recorded ruling, and whatever the owner has reserved. Put it to them and wait.

When unsure, it is the owner's. *A project decision taken as a technical one is discovered after it is built on.*
A review of a deliverable is never launched unasked: it is proposed in one line the owner can answer yes or no (the
occasion, the target, the cut, the cost, and what the review cannot catch), and nothing a reviewer finds is applied
before the owner rules. *A review costs the owner a triage as well as the tokens, and what it finds changes decisions
that are theirs.* When blocked on a privilege, print the command and wait instead of working around it.

## 3. Putting a decision to the owner

The owner rules after an explanation, never after a menu. *A list of options with a recommendation gets ruled on
the recommendation, and the condition it missed surfaces later.*

1. **From basics**: what the thing mechanically is, with file and line.
2. **What it does now**, and why the gap matters in practice.
3. **Each option's costs and gains**, with real numbers, not adjectives. *"Two gigabytes of index on a machine with
   eight" decides what "expensive" cannot.*
4. **A recommendation**, naming the two or three facts that decide it.

Expect the explanation to change the answer: the owner may add a condition or take a fuller option.

- **Context with every term.** The first use of a project term gets one plain line saying what it is, from the
  glossary. Every figure says which system produced it and whether it is a measurement, a model or an estimate.
  *The owner rules on what they understood, not on what you meant.*
- **Verify the explanation before sending it.** List its factual claims and resolve each against its source; a
  claim you cannot cite is cut or marked as a guess. A subagent's or reviewer's line is a pointer: open what it
  points at. *A false claim in an explanation goes straight into a ruling, with no review to catch it.*

## 4. Where the work stands, in every reply

1. **Where we are**, first: the session's piece of work and the step in it.
2. **What just changed**: what is now true, and whether it is committed. Earlier work is named by what it is,
   never by a label from an earlier message.
3. **What is next**, last, and what the owner is asked, answerable in one line.

Before sending, read only the first and the last line: together they must say where we are and what is asked.
*An owner who has to ask what happened has lost the thread, and every later message costs more.*

## 5. Doing the work

- One logical task per commit, its bookkeeping in the same commit (`doc-discipline` §6).
- Before recording a number or a threshold, in a document or a test, and when a test fails, read and apply
  [references/verify-method.md](references/verify-method.md); the method is there, not in this file.
- A gate is a hard stop: not passed until its exit criteria are met and the decision recorded.
- A frozen folder is never edited.
- Speed is not a goal. *A wrong claim in a recorded decision reads as verified to everyone downstream.*
- A task bigger than its item: do the part that is owed and record the rest as a finding. Smaller, because a
  premise was wrong: say the premise was wrong.
- A recommendation against a run is not withdrawn by the go that follows it; restate it as what limits how the
  result may be read. A conditional yes does not cover a version the checks then corrected: put the new one again.
- Delete temporary files by exact name, never by glob. *A glob reaches what another session kept.*

## 6. Two passes

Two passes, always; nothing lands on the first. The second is claim by claim, never a re-read. *A re-read checks
that a text is coherent, not that it is true.*

1. List every claim the change makes, its commit message included ("all tests pass", "no behaviour change"):
   numbers, quotations, identifiers, hashes, citations, invariants stated in code comments, and every *all*, *every*,
   *none*, *only*.
2. Resolve each against its source, never against the draft. A fix made during the pass is a new claim.
3. Read the artifact, not a view of it: the changed text whole, never a truncated hunk; a grep anchored on the
   concept, with what it matched read (a case-insensitive grep matches inside other words; a search for the old
   wording misses a reworded passage).
4. Report what the pass found, including "nothing".

*False completeness is the expensive error: "everything was handled" is the sentence that stops the next reader
checking.* Correct such a claim in place.

## 7. Where state lives

Three places, not interchangeable, kept consistent at every close.

- **The repository**: anything that matters after this session. A decision in the decision record, a measurement
  beside the producer that made it. A ruling is recorded with the owner's exact words and the proposal they
  answered, in the place it governs.
- **Memory**: what a cold session needs to start (owner preferences, standing constraints, where the handoff is).
  Not code structure, not history. *Memory that keeps a claim the repository has corrected misleads every session
  that loads it*: delete what has become false.
- **The handoff**: what is in flight, and nothing that lives only there (`handoff`).

## 8. The close

- [ ] Work committed, one logical task per commit.
- [ ] The project's checks clean (tests, lint, format, link check).
- [ ] The second pass run and its findings reported, including "nothing".
- [ ] Every prediction tested this session scored refuted, confirmed or understated.
- [ ] Every quotation attributed to the owner checked against what they said.
- [ ] Memory updated; what it said that is now false, deleted.
- [ ] The handoff written, its pointer updated.
- [ ] Nothing uncommitted. Mid-task, commit an honest checkpoint marked as such. *A half-done task is no reason
  for an inconsistent tree.*
