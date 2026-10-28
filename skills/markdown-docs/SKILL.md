---
name: markdown-docs
description: How to write, find, move and correct a project's Markdown documents. Load when creating or editing any .md file in a project's docs.
---

# Markdown documents that stay useful

For the `.md` files inside a project: design notes, decision records, plans, logs, runbooks, READMEs. The aim is
documents that can be found again, trusted and corrected. Each rule carries its reason in italics. `DOCS` stands
for the documentation folder the project names in its instruction file.

## 1. Frontmatter

```markdown
---
title: Crash-safe saving
description: How the editor keeps a saved document through a crash, and the two designs that were rejected.
type: design
status: active                       # only on types with a lifecycle
created: 2025-03-04
updated: 2025-03-11T09:42:17+00:00
tags: [saving, journal]
---
```

- `title:` is what tools display and a fuzzy search matches.
- `description:` is the line a reader uses to decide whether to open the file. Write it last.
- `type:` answers "every decision record" without reading anything. The project fixes the list.
- `status:` is the document's lifecycle (`active`, `closed`, `superseded` by default), only on types that can be
  finished. *It answers "which plans are live" without opening a file, if nobody invents a fourth value.* It is never
  a work item's status: that lives in the project's one status file.
- `tags:` prefer an existing tag to a new one. *Two tags for one subject split every query.*
- `created:` `YYYY-MM-DD`, written once, never changed, not on a move or a rewrite. *It is what makes "what did we
  think in spring?" answerable.*
- `updated:` `YYYY-MM-DDTHH:MM:SS+00:00`, set on every substantive edit, in the same edit. *A date alone cannot say
  which of six documents touched today was touched last.* One format and one offset across the corpus, UTC: *tools
  sort the field as text, and a local offset breaks the order around daylight saving.* Take the stamp from the clock
  inside the command that writes it, since an agent has no clock of its own:

  ```sh
  sed -i "s/^updated: .*/updated: $(date -u +%Y-%m-%dT%H:%M:%S+00:00)/" DOCS/the-document.md
  ```

- `archived:` `YYYY-MM-DDTHH:MM:SS+00:00`, the time a file was moved into `archive/`, present only on files there,
  written once, in the commit that moves it, and never changed. *The renames that apply to an archived file are those
  dated after it, and a rename and an archiving on the same day still order.*

A project without frontmatter need not start; where it has it, keep it complete. *A half-annotated corpus returns a
subset that looks complete.*

## 2. Read the index before the documents

Three steps, cheapest first; stop at the first that answers the question: the list (`title`, `type`, `tags`),
then the summaries (add `description`), then the bodies of the few documents the first two picked. *Two orders of
magnitude separate scanning the index from reading the folder.* Standard tools do it:

```sh
# the list; add description to the pattern for the summaries
find DOCS -name '*.md' -exec awk 'FNR == 1 && !/^---$/ { nextfile }
  FNR > 1 && /^---$/ { nextfile }
  /^(title|type|tags):/ { print FILENAME ": " $0 }' {} +
```

An index helps only if it is true: *a stale `description:` makes the right document skipped with confidence.*
Below about fifteen documents, list and read them; above a few hundred, add a ranked full-text search.

## 3. Drafting

1. Search first (§2). *A second document on a subject splits the answer, and neither half is trusted.*
2. State the question the document answers in its first three lines; if you cannot, it is not ready.
3. Mark what is measured (with date and method) and what is inferred, never both in one unmarked sentence. *That
   is how a guess becomes a fact nobody checks again.*
4. No document carries a table of item states: work and its state live in the status file, and a document that
   reports on items cites them by ID (`doc-discipline` §1).
5. Write `description:` last.

## 4. Editing: correct in place, never silently

- A claim that turned out false gets a correction entry (✏️): what was claimed, what is true, how it was found.
  *The history is part of the value: without it the bad conclusion is worked out again.*
- A changed approach gets a CHANGE OF PLAN heading (🔻). *Buried in a paragraph, it is missed.*
- A rejected option keeps its reason (❌). *Without it the option comes back.*
- A state written anywhere but the status file is a copy: cite the item instead. *A table of states in two places is
  updated in one, and the reader cannot tell which.*
- Never write a count: "the suite has 212 tests", "nine items are open", "the three services". *It is wrong by the
  next commit and nobody edits a design document to fix an integer.* Cite the command that counts, not its answer.
- A document that reasons does not report progress: "done", "landed", "not yet implemented", "the code currently
  does". *Such words are true for one commit and the prose around them for months, so they go stale on a different
  schedule.* Progress lives in the status file (`status/` in this kit); a plan or log
  may record what it delivered, dated and in the past tense.
- Operational documents (runbooks, setup, recovery) change in the same session as the change they describe. *An
  out-of-date one is trusted.*
- Do not restructure a document you were asked to add one line to. *A rewrite hides the change in a diff nobody
  can review.*

## 5. Status markers

One meaning each, placed where a reader scans. *A marker on every line is a marker on none.*

The kit's default, for state: ✅ done and verified · ⬜ not started · 🟡 partial, or done but unverified · 🔴 a problem
or risk; for corrections (§4): ✏️ CORRECTION of an earlier claim · 🔻 CHANGE OF PLAN · ❌ considered and rejected. The
project fixes its own markers, one meaning each, in its instruction file.

## 6. Paths, links, moving

- A path in prose is written from the project root (`DOCS/design.md`). A link's target follows the renderer, on
  most forges relative to the linking file.
- Move with `git mv`, then fix the links that point in: `grep -rn 'old-name.md' --include='*.md' .`. *A bare move
  leaves every inbound link dead, and nothing warns.*
- Run anything that rewrites files on a clean tree, so `git checkout -- .` undoes it.
- A frozen folder (an archive kept unchanged) gets its dead links reported, not repaired.
- Finish every move by proving no local link is dead; no output is the bar:

```sh
find . -name '*.md' -not -path './.git/*' | while read -r f; do
  awk '/^ *```/ { c = !c; next } !c' "$f" | grep -oE '\]\([^)]+\)' |
  sed 's/^](//; s/)$//; s/[ #].*//' | grep -vE '^([a-z]+:|$)' |
  while read -r t; do
    case $t in /*) p=".$t" ;; *) p="$(dirname "$f")/$t" ;; esac
    [ -e "$p" ] || echo "DEAD: $f -> $t"
  done
done
```

## 7. Optional: the `iwe` tool

Where the documents are an `iwe` workspace (`.iwe/` is present), `iwe` does §2 faster; setup, the commands and
the one hazard (`rename` and `normalize` rewrite every file they touch) are in [references/iwe.md](references/iwe.md).
Read it before the first `iwe` call in a project.

## 8. Prose and secrets

- Lead with the finding, then the evidence, not the story of finding it.
- Tables for more than two dimensions; prose for reasoning.
- A term with a precise sense is written one way throughout, as the project's glossary says. *The reader never
  guesses which is meant.*
- Never write a key, token, password, credential or hash into a document, note, pasted log or commit message.
  *A secret in a Markdown file is in every clone and every copy of the history.* Write the form of the command
  that hides it.
