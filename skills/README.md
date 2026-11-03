# Skills

Airone Giallo's skills for Claude Code. Each folder holds one skill: a `SKILL.md` with the frontmatter Claude Code reads
to decide when to load it, then the rules, each with its reason.

| Skill | What it is for |
|---|---|
| [markdown-docs](markdown-docs/SKILL.md) | Writing, searching, moving and correcting a project's Markdown documents so they stay findable and trustworthy |
| [handoff](handoff/SKILL.md) | The state file a cold session starts from and the log each close appends to, and the sections that earned their place |
| [session](session/SKILL.md) | The order of a working session: open from the handoff, classify a decision and explain it to the owner, say where the work stands, two passes, close with state consistent in three places; with the method for verifying a claim and the template for the project's map |
| [doc-discipline](doc-discipline/SKILL.md) | Keeping several design documents, the graph file and the status file true together: levels in sync, the ladder of places and the cut between public and private, a term renamed across the live documents and the archive, one allocator per identifier family, the cascade read before an edit, a milestone passed by the owner's ruling, when a review is due, and what a commit of the change holds |
| [setup](setup/SKILL.md) | Installing Airone Giallo into an existing project, once: the questions a template cannot answer, then a script that writes its tree on the sides the cut of the ladder sets (the short instruction file, the invariants file it loads into every session, its rationale file, the machine file, `ai-docs/`, `archive/` and the optional tools chosen: the status file, the handoff, the graph file), backing up an old instruction file before it replaces or removes it, refusing to overwrite anything else, and reporting every step it did not perform |

One more skill lives with its part: [graph](../graph/skills/graph/SKILL.md), reading, extending and checking the
specification graph, in `graph/skills/`, so that the graph's folder stays complete on its own; the plugin loads it
with these.

Airone Giallo deliberately ships no generic commit, test or review skill: the large public collections already have
them, and a project usually has its own. A second skill with the same name and the same trigger competes with the
project's, and the agent picks one of the two; the rules specific to Airone Giallo live instead in the skill that
defines what they govern.
