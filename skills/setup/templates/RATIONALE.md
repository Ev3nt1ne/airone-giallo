# Why the rules in AGENTS.md exist

AGENTS.md states the rules and governs; this file says where each came from. A rule Airone Giallo wrote needs no entry
here: its reason is in AGENTS.md and in the Airone Giallo skill it points to. A rule the project adds gets one entry, in
the form below, under the rule's name as AGENTS.md words it. This file is on the top rung of the ladder
(`doc-discipline` §1): it is private unless the agent layer is public, and then it carries each reason without the
story.

````markdown
## <the rule's name, as AGENTS.md words it>

{{^layer_public}}
- **Failure**: what happened, in which session, what it cost; a link to the log entry or the commit.
- **The owner's words**: the ruling, verbatim, with the proposal it answered.
{{/layer_public}}
{{#layer_public}}
- **Failure**: the kind of failure, in general words; no names, no quotation, no private link.
{{/layer_public}}
- **The reason kept in AGENTS.md**: the one general sentence, so the two can be compared.
- **Last caught something**: the session; past the period AGENTS.md names without one, the rule is proposed for
  removal.
- ✏️ Corrections: dated, appended, never rewritten.
````

## Airone Giallo's own choices

Three choices the setup made for the project, recorded so that a session tempted to undo them finds the reason.

### `CLAUDE.md` is one line, `@AGENTS.md`

- **Choice**: the rules live in `AGENTS.md`; `CLAUDE.md` imports it and holds nothing else.
- **Reason**: Claude Code reads `CLAUDE.md` and other agent tools read `AGENTS.md`; with the import every tool reads
  one file, so the rules cannot drift between two copies.
- **Reopen if**: a tool the project adopts reads neither file, or the import stops being honoured.

### The project's map is in AGENTS.md

- **Choice**: which file answers which question, the identifier families and the opening and check commands sit in
  the instruction file, not in a document of their own.
- **Reason**: the map is needed at every opening, and the instruction file is the one file every session loads; a
  map elsewhere is one more file a cold session must know to open.
- **Reopen if**: the map grows past what every session should load.

### The invariants are in `{{invariants_file}}`, which AGENTS.md imports

- **Choice**: the invariants live in a file of their own on the first rung, and AGENTS.md loads it into every session
  with an `@` import, beside a link to it.
- **Reason**: an invariant describes the system, so it sits with the system documents and follows their side of the
  cut; and it protects the code only if the session about to change the code has read it, which a link alone does not
  make sure of.
- **Reopen if**: the agent tool stops honouring an import in AGENTS.md, or the file grows past what every session
  should load.
