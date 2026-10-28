<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="brand/lockup-dark.svg">
    <img src="brand/lockup-light.svg" alt="Airone Giallo" width="420">
  </picture>
</p>

# Airone Giallo

A kit for running a long project with Claude Code agents: weeks or months of sessions on one codebase, where the
problems are continuity (a session that forgets what was decided), drift (a rule nobody enforces) and trust (a
number nobody measured). Each piece is adoptable alone; a plugin bundles them.

The kit gives a project a structure and a direction; it does not collect fixes. A rule is here because many projects
meet the case and an agent does not find the answer on its own. What one project learned from its own incidents
belongs in that project's memory, not here.

| Piece | What it is | Where |
|---|---|---|
| The specification graph | A project's decisions, requirements, assumptions and threats as a graph whose truth is computed, with a lint, a cascade and a batch tool | `graph/` |
| The status file | The one file that holds a project's work: what waits on the owner's decision, what is accepted, what is deferred until a trigger, and what closed with what was chosen; a checker allocates the IDs | `status/` |
| The archive's log | One log beside the frozen documents: every change made to an archived file, and every change of a word's meaning left uncorrected there, each dated; a checker holds every archived file to its freeze stamp and tells a reader which conflicts apply to it | `archive/` |
| The skills | How a session opens and closes, how a claim is verified, how documents are written and corrected, how changes are reviewed | `skills/` |
| The tools | Checks that run in a hook and in CI: links, frontmatter, the graph's lint | `tools/` |
| Setup | A skill that asks a few questions and installs the pieces you chose into an existing project | `skills/setup/` |
| The plugin | The pieces above, installable as one Claude Code plugin | `.claude-plugin/` |
| The brand | The mark, its lockups and the rules for using them | `brand/` |

The name is Italian for *yellow heron*: the slender, elegant evolution of the yellow rubber duck. Talking to the duck
bounces your ideas back; the heron does more with them.

## Start

Install the plugin, or copy the one folder you want. Each piece's folder has its own README with what it is, why,
and how to use it, in that order.

## Licence

MIT; see [LICENSE](LICENSE).
