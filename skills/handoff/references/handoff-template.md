# Handoff template

Two files to copy into the project's `ai-docs/handoff/` folder. Fill each `[to fill: …]` slot; delete the guidance in italics. The
frontmatter follows the `markdown-docs` skill; drop it if the project does not use frontmatter. The handoff sits on
rung 4 of the ladder (`doc-discipline` §1): it may cite anything at or below that rung, and nothing cites it as a
source.

## `current.md`, the state

```markdown
---
title: Handoff, the current state
description: Where the project stands at the last close, and nothing else.
type: log
status: active
created: [to fill: YYYY-MM-DD]
updated: [to fill: YYYY-MM-DDTHH:MM:SS+00:00]
---

# Handoff, the current state

> Written at the close of session [to fill: session], [to fill: date]: [to fill: the state in one sentence]. The log: [to fill: the log file, as a link],
> newest entry.

## 1. What is true now

- **[to fill: item]**: [to fill: status]. [to fill: what is done, what is left].
- **Checks**: [to fill: test result, lint result], from `[to fill: command]` at `[to fill: commit]`.
- **Progress**: [to fill: n of m items]; by weight, [to fill: estimate and how it was weighed].

## 2. What was decided, and why

- **[to fill: decision]**: [to fill: what it settles, and the question it answered]. *Why:* [to fill: reason]. Recorded in full in [to fill: place].

## 3. What is open

1. **For the owner**: [to fill: question, with the facts that decide it].
2. **Unexplained**: [to fill: finding whose cause is not established, and what would establish it].
3. **Deferred**: [to fill: item], until [to fill: trigger].

## 4. What the next session does first

[to fill: one concrete step].

Prompt to paste:

    [to fill: the prompt]

## 5. What must not be touched

- [to fill: invariant the next change could break, and the test that guards it, or "none guards it"].
- [to fill: run in flight: what it writes, where, until when].

## 6. Where the numbers come from

| Figure | Value | Produced by | Kind |
|---|---|---|---|
| [to fill: name] | [to fill: value] | `[to fill: command]` at `[to fill: commit]`, on [to fill: system] | measurement / model / estimate |
```

*Mark anything that exists only in this file with "only here".*

## `log-[stage].md`, the log

```markdown
---
title: Handoff log, [to fill: stage]
description: One entry per session close in [to fill: stage], newest first; appended, never edited.
type: log
status: active
created: [to fill: YYYY-MM-DD]
updated: [to fill: YYYY-MM-DDTHH:MM:SS+00:00]
---

# Handoff log, [to fill: stage]

One entry per close, newest first. Appended, never edited; a correction is a new entry that names the one it
corrects. The current state is in [current.md](current.md).

## [to fill: YYYY-MM-DD] ([to fill: session]) — [to fill: title]

*Opened with:* [to fill: prompt or command].

### Rulings

- **[to fill: subject]**: *"[to fill: the owner's exact words]"*, answering [to fill: the proposal, or where it is recorded].

### What landed

| Commit | What |
|---|---|
| `[to fill: sha]` | [to fill: what it did] |

### Checked

- [to fill: what was run or measured]: [to fill: result].

### What the second pass found

- [to fill: claim]: [to fill: what was wrong, how it was found, how it was fixed]. Or: nothing.

### Standing lessons

- [to fill: lesson, one line].
```
