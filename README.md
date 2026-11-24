<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="brand/lockup-dark.svg">
    <img src="brand/lockup-light.svg" alt="Airone Giallo" width="420">
  </picture>
</p>

# Airone Giallo

Airone Giallo runs a long project with Claude Code agents: weeks or months of sessions on one codebase, where the
problems are four: continuity (each new session loses the context of the last and works out again what was already
decided), truth maintenance (every decision depends on others, and when one changes the rest must be rechecked by rule,
not by memory), drift (a rule in CLAUDE.md that nobody enforces stops being followed, and documents that should agree
stop agreeing) and trust (a session reports a number nobody measured, or a commit that never ran). It installs whole:
a setup that lays out the project's documents, including the status file and the handoff a new session starts from;
skills that open and close each session on that layout; and commands that check it. The project chooses which parts
it uses when it runs the setup. Some parts also stand on their own: the specification graph, which keeps a project's
decisions, requirements and assumptions as a graph and computes which of them still hold, is a package of its own,
used by Airone Giallo and usable without it.

Airone Giallo gives a project a structure and a direction; it does not collect fixes. A rule is here because many
projects meet the case and an agent does not find the answer on its own. What one project learned from its own incidents
belongs in that project's memory, not here.

| What | Where |
|---|---|
| The skills: how a session opens and closes, how a claim is verified, how documents are written, corrected and kept true together, and the setup, which asks a project a few questions and lays out its documents: the system documents, the plan, the AI documents with the status file and the handoff, an archive with its log in each repository, the agent layer | `skills/`, the setup in `skills/setup/` with the templates of every file it writes |
| The commands: four checks for a hook and CI (the status file with its IDs, the archive and its log, the links, with no public document linking to a private one, the frontmatter with its dates), a mover that re-points every reference to a moved file, a mutation round, a lister of the claims a change makes, and a gate on what a public repository commits and pushes when the project's history stays private | `tools/` |
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
`check-status`, `check-archive`, `check-links`, `check-frontmatter`, `move-paths`, `mutate`, `claims` and
`check-public`. Each
folder's README says what it holds, why, and how it is used, in that order.

To lay Airone Giallo out in a project, open a session at the project's root, on a clean git tree, and run
`/airone-giallo:setup`. It reads the repository, asks only what the repository cannot answer, and shows a dry run that
writes nothing; the real run waits for your word. When only part of the project is to be public, the project becomes
two repositories, and the setup asks whether its history may be public. If it may not, the folder stays where it is as
the private repository, its history with it, and the public repository is born inside it: the paths you declare public
move in, a gate checks them (your markers, a secret scan by `gitleaks`, the agent's own files, the ignore rules), and
the first public commit waits for your yes after the gate's report. If the whole history may be public, a new private
repository, `<folder>-nido`, is created beside the folder, which moves into it, whole, as its public side, as the
setup's last step and with your yes.

### Where it runs and what it runs

Airone Giallo is made for Claude Code. Its skills also load in claude.ai chat and in Cowork, but the commands they call
need a terminal and a git repository. The plugin has no hooks and no MCP servers: it carries skills, text that tells
Claude what to run. Claude then runs the commands installed above; the setup's script, `skills/setup/scaffold.py`, which
comes with the plugin and runs with `python3`; and the git commands a skill names, such as `git mv`, and, each with your
yes, the setup's `git init`, `git submodule add` and commits. The commands read and write the project's files and run
local git commands (such as `ls-files`, `log`, `show`, `diff`, `mv`); `mutate` also runs the test command it is given,
and `check-public`, with the setup when the history stays private, runs `gitleaks` on a local copy.
None of them opens a network connection: `check-links` counts external links and skips them without fetching them. The
network is used to install the commands from GitHub, and by `uvx`, which the graph skill offers when `specgraph` is not
installed and which downloads the graph package from GitHub at a fixed commit. No skill tells Claude to push, open an
issue or post; the setup asks whether the project's agents may, and writes the answer into the project's instructions.

### What it costs in context

The figures below are a dated measurement, not a property of the plugin: Claude Code's own estimate, printed by
`claude plugin details airone-giallo@airone-giallo`, taken on 2026-11-03 for version 0.1.0 of the plugin. About 473
tokens are added to every session; a skill's full text is loaded only when the skill is used:

| Skill | Tokens when used |
|---|---|
| setup (once per project) | about 10.4k |
| doc-discipline | about 4.8k |
| graph | about 2.8k |
| session | about 2.7k |
| markdown-docs | about 2.7k |
| handoff | about 1.8k |

They change with each version of the skills; run the command after installing for the figures of the version you have.

### The graph alone

The graph is also a plugin of its own in the same marketplace, for a project that wants the graph and nothing else:

```
/plugin marketplace add Ev3nt1ne/airone-giallo
/plugin install specgraph@airone-giallo
uv tool install 'git+https://github.com/Ev3nt1ne/airone-giallo.git#subdirectory=graph'
```

The skill is then `/specgraph:graph`, and the command `specgraph`; `pipx install` takes the same argument as
`uv tool install`, and
`uvx --from 'git+https://github.com/Ev3nt1ne/airone-giallo.git@261602f957613ffe2131e716db10efa9bfa8f930#subdirectory=graph' specgraph`
runs it with nothing installed, at a fixed commit. See [graph/README.md](graph/README.md).

## Other projects

- [Embers](https://github.com/Ev3nt1ne/embers): keeps Claude Code subagents' prompt caches from going cold.
- [cache-watch](https://github.com/Ev3nt1ne/cache-watch): warns you before a Claude Code session's prompt cache goes
  cold.
- [grammar-guard](https://github.com/Ev3nt1ne/grammar-guard): grammar and spell check for the prompts you type or
  dictate into Claude Code.

## Licence

MIT; see [LICENSE](LICENSE).
