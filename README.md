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

| Piece | What it is | Where |
|---|---|---|
| The specification graph | A project's decisions, requirements, assumptions and threats as a graph whose truth is computed, with a lint, a cascade and a batch tool | `graph/` |
| The status file | The one file that holds a project's work: what waits on the owner's decision, what is accepted, what is deferred until a trigger, and what closed with what was chosen; a checker allocates the IDs | `status/` |
| The skills | How a session opens and closes, how a claim is verified, how documents are written and corrected, how changes are reviewed | `skills/` |
| The tools | Checks that run in a hook and in CI: links, frontmatter, the graph's lint | `tools/` |
| Setup | A skill that asks a few questions and installs the pieces you chose into an existing project | `skills/setup/` |
| The plugin | The pieces above, installable as one Claude Code plugin | `.claude-plugin/` |
| The brand | The mark, its lockups and the rules for using them | `brand/` |

The name is Italian for *yellow heron*: an elegant cousin of the yellow rubber duck. Like the bird, the
kit is slow on purpose where it matters: a claim is checked before it is recorded, and a change is previewed before
it is made.

## Start

Install the plugin, or copy the one folder you want. Each piece's folder has its own README with what it is, why,
and how to use it, in that order.

## Licence

MIT; see [LICENSE](LICENSE).
