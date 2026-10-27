# Skills

The kit's skills for Claude Code. Each folder holds one skill: a `SKILL.md` with the frontmatter Claude Code reads to
decide when to load it, then the rules, each with its reason, and a closing section on adapting it to a project.

| Skill | What it is for |
|---|---|
| [markdown-docs](markdown-docs/SKILL.md) | Writing, searching, moving and correcting a project's Markdown documents so they stay findable and trustworthy |
| [verify](verify/SKILL.md) | Establishing that a claim is true before it is recorded or built on: the artifact measured, a negative control, derived thresholds, a test seen failing, a second pass claim by claim |
| [handoff](handoff/SKILL.md) | The state file a cold session starts from and the log each close appends to, the sections that earned their place, and the rule for evolving the form |
| [session](session/SKILL.md) | The order of a working session: open from the handoff, classify a decision and explain it to the owner, say where the work stands, two passes, close with state consistent in three places |
| [doc-discipline](doc-discipline/SKILL.md) | Keeping several design documents and their registry true together: levels in sync, identifiers minted through one allocator, the cascade read before an edit, a gate recorded as a hard stop |
| [commit](commit/SKILL.md) | What one commit holds, the changes that get a commit of their own, the checks run before staging, the message, and what never goes in |
