---
title: The archive
description: Documents that stopped being true or needed, kept readable, frozen and outside every search unless named.
type: index
created: <YYYY-MM-DD>
updated: <YYYY-MM-DDTHH:MM:SS+00:00>
tags: [archive]
---

# The archive

Rung 5 of the kit's ladder (`doc-discipline` §1): where a document goes when it stops being true or needed and must
stay readable.

- **Frozen.** Nothing here is edited; a correction is a new live document that cites the archived one. *An archived
  document's value is that it is what it was.*
- **Out of every search unless named.** The workspace's `.ignore` holds `archive/`, which ripgrep, fd and Claude
  Code's search honour; plain `grep -r` does not, so a search over the archive names it on purpose. *An archived claim
  found by a search for current ones is read as current.*
- **Cited at most as a category**, once, by a live document; what a reader needs from an archived document is
  written fresh for them. Links inside the archive are exempt from the link check. *A live text that leans on a frozen
  one inherits everything that has since stopped being true.*
