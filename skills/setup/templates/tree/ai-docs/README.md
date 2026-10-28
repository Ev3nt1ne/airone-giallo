---
title: The AI documents
description: What the agent writes about the work, in five places, each answering one question.
type: index
created: <YYYY-MM-DD>
updated: <YYYY-MM-DDTHH:MM:SS+00:00>
tags: [index]
---

# The AI documents

Rung 4 of the kit's ladder (`doc-discipline` §1): documents about the work, not about the system. They may cite
anything at or below this rung. Each place answers one question, so a document has one place and a session knows
where to look without a map; a new folder is added only for a document that fits none of them.

| Place | The question | What it holds |
|---|---|---|
{{#status}}
| [status.md](status.md), [closed.md](closed.md) | What work is open, and what needs the owner first? | the one file that owns status, and the file of what left it |
{{/status}}
{{#handoff}}
| [handoff/](handoff/current.md) | Where are we? | `current.md`, the state, and one log per stage, appended |
{{/handoff}}
| [design/](design/README.md) | What did we decide, and why? | studies and decisions in their argued form |
| [findings/](findings/README.md) | What did we observe? | measurements, reviews, audits: each dated, with its method |
| [guides/](guides/README.md) | How do we do X here? | how-tos, reusable prompts, reference lists |

The status file and the handoff's state are the only two files edited in place; everything else is appended or
superseded, and a document with a date in its name is a finding or a log, never a guide. *A document edited in
place loses what it said before, and only the two current-state files are meant to.*
