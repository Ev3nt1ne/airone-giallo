---
name: handoff
description: The state file a cold session starts from and the log each close appends to. Load when closing a session with work outstanding, or when changing the handoff's form.
---

# The handoff: state and log

A long project is worked by sessions that start cold. What a session knows and does not write down is gone, and
the usual loss is not a fact but its reason: a settled question gets argued again because nobody recorded why it
was settled. The handoff is two files; a template for both is in
[references/handoff-template.md](references/handoff-template.md). Each rule carries its reason in italics.

## 1. Two files

- **The state** (`HANDOFF/current.md`): where the project stands at the last close, and nothing else. Rewritten
  whole at every close, never a new file per session; version control keeps its history.
- **The log** (`HANDOFF/log-<stage>.md`): one entry per close, newest first, appended and never edited. A new log
  starts with each stage of the project.

*A state that is also a history grows until nobody reads it cold; a history that is also a state gets edited, and
the record of what was decided goes with the edit.*

Write both for someone who knows nothing of this session: every item named by what it is, never by a label
from the conversation.

## 2. The state's core sections

Each earned its place by a fact that had no home and was lost or re-derived. The order is the reading order.

1. **What is true now.** The items in flight with their status; the checks' results with the command that
   produced them; progress said honestly, by weight as well as by count. *Half the items done can be a fifth of the
   work, and the reader plans against the flattering number.*
2. **What was decided, and why.** The rulings and constraints the next work inherits, each with its reason and
   where it is recorded in full. *This is the section that saves a day: without it, the next session re-derives a
   settled question and may settle it differently.* A ruling on one question is not a ruling on its neighbours;
   say which question it answered.
3. **What is open.** Questions put to the owner, in the order they should be answered; findings whose cause is not
   established; items deferred, with their trigger.
4. **What the next session does first.** One concrete first step, and a prompt the owner can paste to start it.
5. **What must not be touched.** Properties the next change could silently break, runs in flight and what they
   write, frozen files. *A cold session cannot see an invariant that lives only in the last session's head.*
6. **Where the numbers come from.** For each figure the state quotes: the commit, the command, the system that
   produced it, and whether it is a measurement, a model or an estimate. *A number without its producer cannot be
   re-checked and gets copied as a fact.*

A one-line banner opens the file: which close wrote it, the state in one sentence, a link to the log's newest
entry.

An item that lives only in the handoff is marked as such (*only here*). *A record cannot be archived while it
holds the only copy of a fact, and an unmarked one gets archived anyway.* Move it to its home in the repository
when you can.

## 3. The log entry

Headed `## <date> (<session>) — <title>`, with:

- **How it opened**: the prompt or command, one line.
- **Rulings**: the owner's exact words and the proposal they answered. *A paraphrase in the record becomes a
  position the owner never took.*
- **What landed**: a table of commit → what, so any claim can be traced to a diff.
- **Checked**: what was measured or run, with its result.
- **What the second pass found**, including "nothing". *The hit rate is the argument for running it.*
- **Standing lessons**: a lesson that will bind later sessions, in one line each, until it is moved to a rule.

## 4. Extension slot

A project adds sections the core lacks, in the state or in the log: changes applied under a standing permission
that the owner may reverse, the state of a long-running job, a machine's availability. Each added section names,
in the project's rationale file (or beside the section, if it has none), the continuity failure that made it.

## 5. The close

At every close with work outstanding, after the work is committed:

1. Rewrite the state whole, from this close; do not edit the last one. *An edited state keeps stale lines no
   one re-read.*
2. Diff it against the previous version: everything the new one drops is dropped on purpose. *The rewrite is where
   a live item disappears without a trace.*
3. Append the log entry.
4. Run the second pass over both files, claim by claim: every hash, path, count and quotation resolved against its
   source.
5. Update the one pointer line in the project's index that says where the handoff is and what the state is.
6. Commit the handoff with the session's last bookkeeping.

A run that will outlive the session gets its handoff written before it starts. *If the session ends with the run
still going, the next one must know what it writes and how to read it.*

## 6. Archiving

A log, or any session record, moves to the archive only when nothing in it is outstanding and nothing in it lives
only there. *An archive is never re-read, so archiving a record whose facts exist nowhere else deletes them.*
Rehouse first, archive second.
