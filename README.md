<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="brand/lockup-dark.svg">
    <img src="brand/lockup-light.svg" alt="Airone Giallo" width="420">
  </picture>
</p>

# Airone Giallo

Airone Giallo runs a long project with Claude Code agents: weeks or months of sessions on one codebase, where the
problems are continuity (a session that forgets what was decided), drift (a rule nobody enforces) and trust (a
number nobody measured). It installs whole: a setup that lays out the project's documents, skills that run the
sessions on that layout, and commands that check it. Which parts the project uses, it says at setup. Some parts also
stand on their own: the specification graph is a package of its own, used by Airone Giallo and usable without it.

Airone Giallo gives a project a structure and a direction; it does not collect fixes. A rule is here because many
projects meet the case and an agent does not find the answer on its own. What one project learned from its own incidents
belongs in that project's memory, not here.

| What | Where |
|---|---|
| The skills: how a session opens and closes, how a claim is verified, how documents are written, corrected and kept true together, and the setup, which asks a project a few questions and lays out its documents: the system documents, the plan, the AI documents with the status file and the handoff, an archive with its log in each repository, the agent layer | `skills/`, the setup in `skills/setup/` with the templates of every file it writes |
| The commands: four checks for a hook and CI (the status file with its IDs, the archive and its log, the links with the ladder's cut, the frontmatter with its dates), a mover that re-points every reference to a moved file, a mutation round, and a lister of the claims a change makes | `tools/` |
| The specification graph: a project's decisions, requirements, assumptions and threats as a graph whose truth is computed, with a lint, a cascade and a batch tool; a package of its own, with its own skill and plugin entry (`specgraph`) for a project that takes the graph alone | `graph/` |
| The plugin, which carries the skills into Claude Code | `.claude-plugin/` |
| The brand: the mark, its lockups and the rules for using them | `brand/` |

The name is Italian for *yellow heron*: the slender, elegant evolution of the yellow rubber duck. Talking to the duck
bounces your ideas back; the heron does more with them.

## Start

The skills come as one Claude Code plugin; the commands come as two Python packages, since a plugin cannot put a
command on the PATH. In Claude Code:

```
/plugin marketplace add Ev3nt1ne/airone-giallo
/plugin install airone-giallo@airone-giallo
```

Then the commands the project will use, one line per package:

```
uv tool install 'git+https://github.com/Ev3nt1ne/airone-giallo.git#subdirectory=graph'
uv tool install 'git+https://github.com/Ev3nt1ne/airone-giallo.git#subdirectory=tools'
```

From a clone of this repository, `uv tool install ./graph` and `uv tool install ./tools`; `pipx install` takes the
same arguments, and `pip install` works inside a project's own venv. The tool installer comes first because the
system Python on most machines refuses `pip install` outside a venv, and a tool installer keeps the commands'
environment apart from the project's.

The skills are then `/airone-giallo:session`, `/airone-giallo:handoff`, `/airone-giallo:markdown-docs`,
`/airone-giallo:doc-discipline`, `/airone-giallo:setup` and `/airone-giallo:graph`; the commands are `specgraph`,
`check-status`, `check-archive`, `check-links`, `check-frontmatter`, `move-paths`, `mutate` and `claims`. To lay Airone
Giallo out in a project, open a session at the project's root and run `/airone-giallo:setup`. Each folder's README
says what it holds, why, and how it is used, in that order.

### The graph alone

The graph is also a plugin of its own in the same marketplace, for a project that wants the graph and nothing else:

```
/plugin marketplace add Ev3nt1ne/airone-giallo
/plugin install specgraph@airone-giallo
uv tool install 'git+https://github.com/Ev3nt1ne/airone-giallo.git#subdirectory=graph'
```

The skill is then `/specgraph:graph`, and the command `specgraph`; `pipx install` takes the same argument as
`uv tool install`, and `uvx --from 'git+https://github.com/Ev3nt1ne/airone-giallo.git#subdirectory=graph' specgraph`
runs it with nothing installed. See [graph/README.md](graph/README.md).

## Licence

MIT; see [LICENSE](LICENSE).
