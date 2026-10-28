---
title: The archive's log
description: Every change made to a file after it was archived, and every change of a word's meaning left uncorrected in the archive, each dated.
type: log
created: <YYYY-MM-DD>
updated: <YYYY-MM-DDTHH:MM:SS+00:00>
tags: [archive]
---

# The archive's log

This file answers two questions: what was changed in an archived file after it was frozen, and which words in an
archived file no longer mean what they say?

- **Append-only; the newest row goes on top of its table.** A row is never rewritten: a wrong one is corrected by a
  newer row that names it. *The log is the record of what happened to frozen files; a rewritten row is one more
  silent edit.*
- **Before reading an archived file, run `check-archive read <file>`**: it prints the file's freeze time and the
  conflicts below dated after it. *The conflicts that apply to a file are derived from the dates, so no list per file
  can go stale.*
- **Check it with `check-archive`**, in the hook and in CI: every archived file has its `archived:` stamp, every
  staged change to one has its row here, every conflict's row parses.

## Changes made to archived files

A file in this folder is edited only with a row here, in the same commit as the edit. *An edit to a frozen file
without its row is the failure this log exists to prevent: the file is no longer what it was, and nothing says so.*
Archiving a file is not a change to it: its one edit, the `archived:` stamp, is made in the commit that moves it
here, and it gets no row.

- **Date** is the day of the change, `YYYY-MM-DD`; **File** the file's path inside this folder; **What** the change in
  one line; **Why, and who decided** the reason and whose ruling it was.
- **Commit** is `HEAD` in the row written with the change, since that commit has no hash yet: it reads as "the
  commit that added this row", which `git log -S` finds; a hash when the row records a change already committed.

<!-- An example row, newest first under the header:
| 2026-11-03 | `2026-09-review-answers.md` | the link to `docs/design.md` §4 rebuilt after its move to `docs/spec.md` §4 | the owner, when the move was made | `HEAD` |
-->

| Date | File | What | Why, and who decided | Commit |
|---|---|---|---|---|

## Vocabulary conflicts left uncorrected

Each row is a dated change of a word's meaning that the archived files were not corrected for. It applies to every
archived file frozen before its time and to none frozen after it. Where the owner chose to correct a file, that file
has its row in the Changes table above.

- **Date** is the time of the rename, `YYYY-MM-DDTHH:MM:SS+00:00`. *A time, not a day: a rename and an archiving on
  the same day must still say which came first.*
- **Kind** is `renamed` (the old word is no longer used for anything: an old file reads oddly, not wrongly) or
  `reused` (the old word now means something else: an old file reads wrongly, with no sign). *The second is the
  dangerous one, and the kind makes it stand out.*
- **Old** and **Now** are the word and its meaning before and after; **Where the current meaning is defined** is a
  path from the project's root (the folder holding this one), usually the glossary, a link, or a URL. The glossary
  keeps the retired word too, with the date.

<!-- An example row, newest first under the header:
| 2026-11-10T14:05:00+00:00 | reused | "stage": a phase of the plan | "stage": a deployment environment | `docs/glossary.md` |
-->

| Date | Kind | Old | Now | Where the current meaning is defined |
|---|---|---|---|---|
