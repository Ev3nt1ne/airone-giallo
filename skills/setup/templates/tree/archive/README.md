---
title: The archive
description: Documents that stopped being true or needed, kept readable, frozen and outside every search unless named.
type: index
created: <YYYY-MM-DD>
updated: <YYYY-MM-DDTHH:MM:SS+00:00>
tags: [archive]
---

# The archive

This repository's archive, beside the ladder rather than on it (`doc-discipline` §1): where a document of this
repository goes when it stops being true or needed and must stay readable. It stays on this repository's side, so
archiving never moves a document between public and private.

- **Frozen.** A correction is a new live document that cites the archived one, never an edit here. An archived file
  is edited only with a row in [LOG.md](LOG.md), the archive's log, in the same commit. *An archived document's value
  is that it is what it was, and an edit without its row hides that it no longer is.*
- **Read with its conflicts.** Before reading an archived file, run `check-archive read <file>`: it prints the
  words whose meaning changed after the file was frozen, from the log. *A word renamed or reused since reads as
  current, with the wrong meaning.*
- **Out of every search unless named.** Search with ripgrep, fd or Claude Code's own search: they honour the
  `.ignore` at this repository's top, which lists `archive/`. A plain `grep -r`, `find` or `sed` does not read
  `.ignore`, so one that must stay out of the archive excludes it by name (`--exclude-dir=archive`), and one that
  reaches into the archive names it on purpose. *An archived claim found by a search for current ones is read as
  current.*
- **Cited at most as a category**, once, by a live document; what a reader needs from an archived document is
  written fresh for them. Links inside the archive are exempt from the link check. *A live text that leans on a frozen
  one inherits everything that has since stopped being true.*
