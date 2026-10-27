# Handoff template

Two files to copy into the project's `HANDOFF` folder. Replace each `<…>`; delete the guidance in italics. The
frontmatter follows the `markdown-docs` skill; drop it if the project does not use frontmatter.

## `current.md`, the state

```markdown
---
title: Handoff, the current state
description: Where the project stands at the last close, and nothing else.
type: log
status: active
created: <YYYY-MM-DD>
updated: <YYYY-MM-DDTHH:MM:SS+00:00>
---

# Handoff, the current state

> Written at the close of session <session>, <date>: <the state in one sentence>. The log: [<log file>](<log file>),
> newest entry.

## 1. What is true now

- **<item>**: <status>. <what is done, what is left>.
- **Checks**: <test result, lint result>, from `<command>` at `<commit>`.
- **Progress**: <n of m items>; by weight, <estimate and how it was weighed>.

## 2. What was decided, and why

- **<decision>**: <what it settles, and the question it answered>. *Why:* <reason>. Recorded in full in <place>.

## 3. What is open

1. **For the owner**: <question, with the facts that decide it>.
2. **Unexplained**: <finding whose cause is not established, and what would establish it>.
3. **Deferred**: <item>, until <trigger>.

## 4. What the next session does first

<one concrete step>.

Prompt to paste:

    <the prompt>

## 5. What must not be touched

- <invariant the next change could break, and the test that guards it, or "none guards it">.
- <run in flight: what it writes, where, until when>.

## 6. Where the numbers come from

| Figure | Value | Produced by | Kind |
|---|---|---|---|
| <name> | <value> | `<command>` at `<commit>`, on <system> | measurement / model / estimate |
```

*Mark anything that exists only in this file with ⚠️ only here.*

## `log-<stage>.md`, the log

```markdown
---
title: Handoff log, <stage>
description: One entry per session close in <stage>, newest first; appended, never edited.
type: log
status: active
created: <YYYY-MM-DD>
updated: <YYYY-MM-DDTHH:MM:SS+00:00>
---

# Handoff log, <stage>

One entry per close, newest first. Appended, never edited; a correction is a new entry that names the one it
corrects. The current state is in [current.md](current.md).

## <YYYY-MM-DD> (<session>) — <title>

*Opened with:* <prompt or command>.

### Rulings

- **<subject>**: *"<the owner's exact words>"*, answering <the proposal, or where it is recorded>.

### What landed

| Commit | What |
|---|---|
| `<sha>` | <what it did> |

### Checked

- <what was run or measured>: <result>.

### What the second pass found

- <claim>: <what was wrong, how it was found, how it was fixed>. Or: nothing.

### Standing lessons

- <lesson, one line>.
```
