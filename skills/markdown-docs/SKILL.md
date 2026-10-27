---
name: markdown-docs
description: Write, search, move and edit the Markdown documents inside a project so they can be found again, trusted and corrected. Covers frontmatter with a created date and an updated timestamp, a document's lifecycle status, reading the index before the documents, the status markers, correcting a document instead of rewriting it, why a document must not report progress or hardcode counts, moving a document without leaving dead links, and optional commands for the iwe Markdown tool with its renaming hazard. Use whenever creating, drafting, searching, moving or editing a .md file in a project's documentation, and when asked to write a design note, decision record, plan, log, runbook or README.
---

# Markdown documents that stay useful

For **the `.md` files inside a project**: design notes, decision records, plans, logs, runbooks, READMEs. The goal
is documents that can be found again, trusted and corrected, rather than a pile of files nobody dares delete. It is
not a memory system and not a way of organising knowledge: a project keeps its documents as it prefers, and this is
how to write them well. Each rule carries its reason in italics. `DOCS` stands for the documentation folder the
project names in its instruction file.

---

## 1. Frontmatter: the minimum that earns its place

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

Five fields do real work:

- **`title:`** is what tools display and what a fuzzy search matches.
- **`description:`** is the most useful line in the file: it is what a reader reads to decide whether to open the
  document at all. **Write it last**, once you know what the document says.
- **`type:`** lets you ask for every decision record without reading anything. The project fixes the list of types.
- **`status:`** is the **document's** lifecycle, on the types that have one (a plan, and any other document that can
  be finished). It takes a small closed set of values; the default is `active`, `closed`, `superseded`. *It answers
  "which plans are still live" without opening a file, which works only if nobody invents a fourth value.* It is
  never an item's status: a project that tracks work item by item keeps that in one register, not in frontmatter.
- **`tags:`**: look at what exists, and prefer an existing tag to a new one. *Two tags for one subject split every
  query.*

**A project without frontmatter need not start**; match the project you are in. Where it has frontmatter, keep it
consistent. *Half-annotated documents are worse than none: a query over them returns a subset that looks complete.*

### Dates: `created:` and `updated:`

Both are **absolute, never relative**. *"Last week" means nothing six months later.*

| Field | Format | Rule |
|---|---|---|
| `created:` | `YYYY-MM-DD` | Written once, on the first save, and never changed: not on a rewrite, a move or a correction. *It is what makes "what did we think in spring?" answerable.* A date is enough: nobody asks at what hour a document was created |
| `updated:` | `YYYY-MM-DDTHH:MM:SS±HH:MM` | Set to now on every substantive edit, in the same edit. A typo fix is not substantive; a corrected claim, a new section or a changed conclusion is |

**`updated:` carries a time, not only a date.** *Six documents stamped with the same day cannot say which was
touched last, and that is the only question the field exists to answer.*

**One format and one offset across the whole corpus, and UTC is the safe offset.** *Tools sort this field as text,
not as a moment in time: `T01:00:00+00:00` sorts before `T01:00:00+01:00` although it is an hour later. One format
and one offset make the text sort and the time sort agree; a local offset changes with daylight saving and puts the
hours around each change in the wrong order.*

**Take the stamp from the clock inside the command that writes it:**

```sh
sed -i "s/^updated: .*/updated: $(date -u +%Y-%m-%dT%H:%M:%S+00:00)/" DOCS/the-document.md
```

*A stamp typed by hand or copied from earlier output drifts from the clock, and an agent has no clock of its own.*
Never touch `created:` while doing it. When backfilling, the file's modification time is close enough.

**A filter for an exact date stops matching once the value is a timestamp**: `updated: 2025-03-11` finds the
documents stamped with the bare date and skips every timestamped one from the same day. Filter on a range.

**`updated:` is the field that goes stale**, and is worth having only if it can be trusted: changing a document's
content and changing its `updated:` line are one action.

---

## 2. Read the index before the documents

Three steps, cheapest first. **Stop at the first one that answers the question.**

| Step | What you read | Roughly, for 40 documents |
|---|---|---|
| **1: the list** | `title`, `type`, `tags` | a few hundred tokens |
| **2: the summaries** | the above, plus `description` | under a thousand tokens |
| **3: the documents** | the bodies, of the few that steps 1 and 2 picked | tens of thousands of tokens |

*The last row is the whole argument: two orders of magnitude separate scanning the index from reading the folder,
and the gap grows with every document.* §1 exists to make steps 1 and 2 possible.

| Corpus | Verdict |
|---|---|
| fewer than about 15 documents | not worth it: list them and read them |
| about 30 to 100 | where it pays best: too many to read whole, few enough that a complete index is nearly free |
| several hundred or more | the steps are not enough alone; use a ranked full-text search to choose where to start |

**An index helps only if it is true.** *A stale `description:` misleads with confidence: the right document is
skipped, not merely missed.* This is a way of reading, not a feature of a tool; the standard shell tools do it:

```sh
# Step 1, the list: frontmatter fields only, bodies unread
find DOCS -name '*.md' -exec awk 'FNR == 1 && !/^---$/ { nextfile }
  FNR > 1 && /^---$/ { nextfile }
  /^(title|type|tags):/ { print FILENAME ": " $0 }' {} +
# Step 2, the summaries: the same command with  /^(title|type|tags|description):/
# Step 3: read only the files steps 1 and 2 picked
```

A project with an index tool uses it instead (§7 gives the commands for one).

---

## 3. Drafting a new document

1. **Search first** (§2). *A second document on a subject splits the answer in two, and neither half is trusted.*
2. **State the question the document answers in its first three lines.** If you cannot, it is not ready to be
   written.
3. **Label the evidence.** Anything measured says so, with the date and how. Anything inferred is marked as an
   inference. **Never let the two share a sentence unmarked.** *That is how a guess becomes a fact nobody checks
   again.*
4. **A document whose job is tracking work** (a plan, a register) opens with its status table. *It is what the next
   reader reads first.* A document whose job is reasoning has no status table (§4).
5. **Write `description:` last.**

---

## 4. Editing: correct in place, never silently

**Correct by appending, not by overwriting.** *A document's history is part of its value: someone will work out a
bad conclusion again unless they can see it was tried, and why it failed.*

- A claim that turned out false gets a **correction entry** (✏️), not a silent edit: what was claimed, what is true,
  and how that was found.
- An approach that changed gets an explicit **CHANGE OF PLAN** heading (🔻). *A change of direction buried in a
  paragraph is missed, and people keep following the old plan.*
- A rejected option keeps its reasoning (❌). *"Considered and rejected" with no reason is worse than nothing: the
  option comes back and nobody remembers why it was dropped.*
- **Keep a status table current in the same edit.** *It is read first, so a stale one misleads first.*
- **Never write a count into a document**: "the suite has 212 tests", "nine items are open", "the three services".
  *A number like that is wrong by the next commit, and nobody edits a design document to correct an integer.*
  Counts are the output of whatever counts them: cite the command, not its answer.
- **A document that reasons does not also report progress**: "done", "landed", "not yet implemented", "the code
  currently does". *Such words are true for one commit and the prose around them for months, so they go stale on a
  different schedule.* Progress lives only in the project's register, and other documents link to it. A plan or a
  log may record what it delivered, in the past tense and dated: that is history, and history does not go stale.
- **An out-of-date operational document is worse than none**, because it is trusted. Runbooks, recovery notes and
  setup guides are updated in the same session as the change they describe.

**Do not restructure a document you were asked to add one line to.** *A rewrite hides the one change in a diff
nobody can review.*

---

## 5. The status markers

They let a reader scan a long document without reading it, so each has one meaning and no other.

| Marker | Means |
|---|---|
| ✅ | Done and verified |
| ⬜ | Not started |
| 🟡 | Partial, or done but not verified |
| 🔴 | A problem, a risk, or something that will cause trouble |
| 🟢 | Good news, or a constraint resolved |
| 🔻 | **CHANGE OF PLAN**: the approach changed |
| ✏️ | **CORRECTION**: an earlier claim was wrong |
| 🚨 | Alert: this has already caused damage once |
| 🔑 | The key point of a section |
| 🧭 | A direction, or a decision pending |
| ⚖️ | A trade-off with no free answer |
| ❌ | Considered and rejected |
| ⭐ | The recommended option |
| 🧠 | A lesson learned the hard way |
| ⚠️ | A caveat that changes how the text should be read |
| 📋 | To do |

Put them where a reader scans (tables, the start of a bullet, a heading). *A marker on every line is a marker on
none.*

---

## 6. Paths, links, and moving a document

- **A path named in prose is written from the project root**, whatever folder the document sits in (`DOCS/design.md`,
  `src/save.py`). *The reader then finds it without knowing where the sentence lives.* A link's target follows what
  the project's renderer resolves, which on most forges is relative to the linking file.
- **Move a document with `git mv`, then fix the links that point in.** Find them by the old file name
  (`grep -rn 'old-name.md' --include='*.md' .`) and edit each. *A bare move leaves every link to the old place dead,
  and nothing warns.*
- **Run any command that rewrites files on a clean tree**, so `git checkout -- .` undoes it if it goes too far.
- **A frozen folder** (an archive the project keeps unchanged) has its dead links reported, not repaired, unless the
  project's owner allows that one repair. *A frozen document's value is that it is what it was.*

**Finish every move by proving no local link is dead:**

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

No output is the bar. Targets resolve from the linking file's folder, or from the root when they start with `/`;
external links, anchors and code blocks are skipped. A project's own link checker, if it has one, is the authority.

---

## 7. Optional: the `iwe` tool

`iwe` is an open-source tool that indexes Markdown files by frontmatter and links. Nothing above needs it. Where the
documents are an `iwe` workspace (`.iwe/` is present), these commands do the steps of §2; check the flags against
`iwe --help`.

```sh
# Step 1, the list: names only
iwe find --filter 'type: decision' -f keys
iwe tree -d 3 -f keys                                  # the shape of the folder
# Step 2, the summaries: add the one-liner, still no bodies
iwe find --filter 'tags: saving' --project 'title,description'
iwe find --lexical "journal replay" --limit 10 --project 'title,description'
# Step 3, the documents: only once 1 and 2 have narrowed it
iwe retrieve -k DOCS/design --expand-references 1
# Housekeeping
iwe find --sort 'updated:1' --project 'title,updated'  # stalest first
iwe schema                                             # is the frontmatter consistent?
```

- **`--project` is what keeps step 2 cheap.** *Without it `find` returns the documents' content, and you pay for
  step 3 while believing you are scanning an index.*
- **Limit what you pull** with `--limit`, `--max-documents` or `--max-tokens`. *Unlimited expansion
  (`--expand-includes 0`) can return the whole store.*

🚨 **`iwe rename` and `iwe normalize` rewrite every file they touch, not only the link you meant.** They write each
file back in canonical form, applying `refs_path` and `refs_extension` from `.iwe/config.toml` to every link. Where
that does not match how the links are written, they rewrite paths, append `.md` to links that point at a folder or a
script (breaking them), and strip formatting from link text. Before the first rename, **measure whether the
configuration fits**: count how the links are actually written (relative to the file or the root; with `.md` or
without).

| What you measured | Do this |
|---|---|
| `refs_path` and `refs_extension` match every link | `iwe rename`, which rewrites the links that point in |
| they do not match, which is usual when documents link to code, scripts or folders | never `rename` or `normalize`; `git mv` and fix the links yourself (§6) |

Write the verdict at the top of `.iwe/config.toml` so the next session need not measure again.

- **`iwe` reports a link to a folder or a non-Markdown file as unresolved.** *Its graph holds documents only*; the
  check of §6 is the authority on whether a link works.
- **A link alone on its own line means inclusion** ("this document includes that one"); a link inside a sentence is
  a cross-reference. **Never leave a "see also" alone on a line.** *It silently becomes a structural link.*

---

## 8. Writing the prose

- **Lead with the finding, then the evidence**, not the story of how you got there.
- **Tables for anything with more than two dimensions**, prose for reasoning.
- **Record what was got wrong** (§4). A growing corrections section is normal, not a failure.
- **Write a defined term as one.** Where the project keeps a glossary of words it gives one precise meaning, write
  such a word capitalised and in italics when the precise meaning is meant (*Journal*), as code when the name in the
  code is meant (`Journal`), and in plain lower case only for the everyday sense. *A reader, human or agent, then
  never has to guess which of the three is meant.* Only glossary words take this form; a document that coins one
  says so where it defines it.

---

## 9. Never write into a document

Encryption keys, access and secret keys, tokens, API keys, passwords, credentials, password hashes.

If a command's output would contain one, write the form of the command that hides it, and say why. This applies to
documents, notes, pasted logs and commit messages alike. *A secret in a Markdown file is in every clone and every
copy of the history.*

---

## Adapting this to your project

**Fixed (the core).** The index is read before the documents; `created:` never changes and `updated:` changes with
every substantive edit, in one format and one offset; a document is corrected by appending, never silently; measured
and inferred are never mixed unmarked; no counts, and no progress in a document that reasons; each status marker has
one meaning; a move ends with no dead link; no secrets.

**Slots**, which the project fills in its instruction file or beside this skill:

| Slot | Default here | What the project decides |
|---|---|---|
| the documentation folder (`DOCS`) | none | where its documents live, and any folder kept frozen |
| frontmatter fields | `title`, `description`, `type`, `status`, `created`, `updated`, `tags` | whether it uses frontmatter at all; any field it adds |
| the list of `type:` values | `design`, `plan`, `decision`, `log`, `reference`, `howto` | its own closed list |
| the document lifecycle values | `active`, `closed`, `superseded` | its own closed set, still for documents only |
| where progress lives | one register | which file that is |
| the status markers | the table in §5 | added markers, each with one meaning |
| tools | standard shell tools; `iwe` optional | an index tool, a link checker, a frontmatter check |

**Evolving it.** A rule is added only from a named failure (a document trusted while stale, a link broken by a
move) and is written with its reason beside it, as every rule here is. A rule that has not been needed for a long
while is a candidate for removal: a list of rules nobody applies teaches readers to skip the list.
