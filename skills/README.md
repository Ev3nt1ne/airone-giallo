# Skills

The kit's skills for Claude Code. Each folder holds one skill: a `SKILL.md` with the frontmatter Claude Code reads to
decide when to load it, then the rules, each with its reason, and a closing section on adapting it to a project.

| Skill | What it is for |
|---|---|
| [markdown-docs](markdown-docs/SKILL.md) | Writing, searching, moving and correcting a project's Markdown documents so they stay findable and trustworthy |
| [handoff](handoff/SKILL.md) | The state file a cold session starts from and the log each close appends to, the sections that earned their place, and the rule for evolving the form |
| [session](session/SKILL.md) | The order of a working session: open from the handoff, classify a decision and explain it to the owner, say where the work stands, two passes, close with state consistent in three places; with the method for verifying a claim and the template for the project's map |
| [doc-discipline](doc-discipline/SKILL.md) | Keeping several design documents, the graph's registry and the register true together: levels in sync, one allocator per identifier family, the cascade read before an edit, a gate recorded as a hard stop, the occasions for a review and how one is run, and what a commit of the change holds |
| [setup](setup/SKILL.md) | Installing the kit into an existing project, once: the questions a template cannot answer, then a script that writes the short instruction file, its rationale file, the machine file and the pieces chosen (the register, the handoff, the graph's registry), refusing to overwrite and reporting every step it did not perform |

The kit deliberately ships no generic commit, test or review skill: the large public collections already have them,
and a project usually has its own. A second skill with the same name and the same trigger competes with the
project's, and the agent picks one of the two; the rules specific to this kit live instead in the skill that defines
what they govern.
