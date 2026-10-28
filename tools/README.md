# The tools

A project's documents rot in ways nobody sees at the moment of the edit. A file is moved and every link to it dies;
a public document cites a private one and the cut between the two sides leaks; a document is edited and its
`updated:` stamp still names last month.

This piece is commands of standard-library Python, each one file: two checks that run in a hook and in CI, and a
mover that keeps the references true. They read a project's own values from its files or their arguments, never from
constants: the ladder's cut, the archive's place.

It is a piece of Airone Giallo, the kit described in the [repository](https://github.com/Ev3nt1ne/airone-giallo), and
it is useful without the rest. The ladder and the archive it checks are the `doc-discipline` skill's §1; the
frontmatter is the `markdown-docs` skill's §1.

## Why

- **A check that is remembered is a check skipped.** Each rule a document keeps (a live link, a stamp that moves, a
  public text that cites nothing private) is checked by a command in the hook, so it holds at every commit.
- **The tracked tree is the tree.** A file present here but not tracked is missing in every other clone, so a link to
  it is dead; a file staged for the commit being made is in it.
- **The archive is frozen, and its rot is information.** A link inside it that a later move killed is counted and
  never repaired in passing; a change to an archived file goes with a row in its log, and the mover refuses one
  without it.
- **A move re-points what it can prove and reports what it cannot.** A link and a path written from the top name
  their target; a bare file name in prose may name another file, and a script's relative path may be read from the
  folder it runs in, so those are listed for a reader, never rewritten.

## Start

Python 3.10 or newer, standard library only, and git; the package is `airone-tools`, MIT, with no dependencies.
`pip install ./tools` from the kit gives the commands below. Each file in [src/](src/) also runs as a script
from the kit without installing (`python3 <kit>/tools/src/check_links.py`); none is ever copied into the project.
*A copied script is a second copy that the kit's next version does not reach.*

The setup skill installs no hook. A project that wants the checks at every commit copies these lines into its own
`.git/hooks/pre-commit` (or the hook manager it uses), each command exiting non-zero on a finding; `<cut>` is the
last public rung its instruction file names, `all` or `none` in one repository:

```sh
#!/bin/sh
# The documents' checks, zero errors before every commit.
check-links --cut <cut> || exit 1       # the two-repository form: check-links --public <dir> --cut <cut>
check-frontmatter || exit 1             # the documents being committed, against HEAD
```

In the two-repository form the workspace's hook runs `check-links --public <dir>` from the workspace root, which
walks the public folder too, and each repository's hook runs `check-frontmatter` on its own staged documents, since a
commit is made in one repository at a time. In CI, after `pip install <kit>/tools`, the same commands run on the
whole tree and on the range the change brings:

```sh
check-links --public <dir> --cut <cut>      # one repository: check-links --cut <cut>
check-frontmatter --all
check-frontmatter --range "$BASE..HEAD"     # BASE: the commit the change starts from
```

## The commands

Every command works on the repository holding the current folder (`--root DIR` names another) and exits 2 on a bad
argument or a repository that cannot be read. The two checks print `error:` lines and a count, and exit 1 on a
finding, 0 when clean.

### `check-links`

Resolves every relative link and image in the tracked Markdown files, nested repositories included, and checks each
anchor (`#section`) against the target's headings as a forge makes them, or an HTML id. A link from `/` is read from
the top of the repository holding the file. Links inside code and HTML comments are examples, not links.

- **The archive** (`archive/` at each repository's top): a dead link or anchor inside it is printed as `archived:`
  and counted, never an error. A live document citing a file inside it is a warning: the archive is cited as a
  category at most, its folder, its README or its log.
- **The ladder**, with `--cut RUNG` (`none`, `docs`, `graph`, `plan`, `ai-docs`, `archive`, `all`) in one repository,
  or `--public DIR` in the two-repository form, where everything in DIR is public and the rungs up to the cut (`plan`
  by default) sit inside it: a link, or a path written in backticks, from a public file to a private one is an error.
  A citation from a rung to a higher one is a warning. `--rung NAME=PATH[,PATH]` places a rung elsewhere, from the
  workspace root (`--rung docs=documentation/`). A file outside every rung has no side in one repository and is not
  held to the cut.

```text
$ check-links --public inkwell
error: inkwell/docs/spec.md:12: the ladder: a public file links to ../../ai-docs/status.md, on the private side: ai-docs/status.md (rung 4, ai-docs)
warning: ai-docs/design/save.md:3: links to ../../archive/old-save.md, inside the archive: a live document cites the archive as a category at most
archived: archive/old-save.md:7: dead link ../docs/journal.md
check-links: 41 Markdown file(s), 230 relative link(s), 18 external skipped; the ladder: public side inkwell/
1 dead link(s) inside the archive, information only: the archive is frozen, and a link in it is rebuilt only with a row in its log
1 error(s), 1 warning(s)
```

### `check-frontmatter`

Holds every tracked Markdown document to the frontmatter of `markdown-docs` §1: a block opening the file with
`title`, `description`, `type`, `created` (`YYYY-MM-DD`) and `updated` (`YYYY-MM-DDTHH:MM:SS+00:00`, not before
`created`); `status`, when present, one of `active`, `closed`, `superseded` (`--statuses` for the project's own);
`type` one of `--types` when given; `tags` a list without repeats; `archived:` only in the archive. In the body,
outside code, the change-of-plan marker keeps its one meaning: it stands beside the words CHANGE OF PLAN, on the
heading it marks or in a legend (`--no-markers` for a project with its own markers).

By default it reads the staged documents against HEAD: `created` is the same, and `updated` is later whenever
anything else in the file changed; a renamed document is compared with its old path. `--range A..B` does the same
between two revisions; `--all` reads every tracked document's block. Not checked: `AGENTS.md` and `CLAUDE.md`
anywhere, and at a repository's top `RATIONALE.md`, `.claude/`, `human-docs/` (the owner's notes, never held to the
rules), `sources/` and `.github/`; `--exempt PATH` adds a folder or a glob. In the archive a file carries its
`archived:` stamp in the time form and nothing else is checked; its README and log are documents like any other.

### `move-paths`

Moves tracked files with `git mv` and re-points every reference to them in the tracked text files: Markdown links
and HTML `href` and `src`, paths written relative to the file (`../plan/x.md`), and paths written from the top of the
repository holding the file, in prose, scripts, YAML, TOML and HTML (`--also .json` for more). A dry run by default,
every edit listed with its file and line; `--apply` does it.

```sh
move-paths docs/design.md docs/spec.md          # one file, or a folder and every file in it
move-paths --table moves.tsv --apply            # OLD<TAB>NEW a line; a third column `no` keeps a file's content
```

- A folder at the top is matched only with its slash (`plan/`), and a file at the top only in a link: their bare
  names are words in prose. Every other mention of a moved file's name is listed and left alone; read the list
  before applying.
- Nothing in the archive is edited, its log included; a link there that the move kills is listed as information. A
  file moved into the archive is not edited either: archiving changes nothing in it but the stamp, written by hand
  in the same commit.
- `--frozen-ok FILE` lets an archived file's link targets be re-pointed (its prose never), and only when the staged
  `archive/LOG.md` holds a new row in its Changes table naming that file; moving an archived file needs the same.
  The rows are read with the archive's own checker when `airone-archive` is installed, else by the same reading
  done here; the report says which.
- `--apply` refuses, before anything moves, a file not tracked, a target that exists, two files to one path, a move
  from one repository into another, an archived file without its row, and a file it would write that has changes not
  staged, since the undo is a checkout.

## What it is not

- **Not a linter of prose.** The checks hold the shape (links, dates, sides); whether a document says something true
  is the verify pass's work.
- **Not a fixer.** `check-links` and `check-frontmatter` change nothing; `move-paths` changes only what it listed.
- **Not installed by setup.** The hook lines above are the project's to copy, under its own commit rules.

## Tests

From this folder, with pytest and git installed:

```sh
pytest
```

## Licence

MIT; see [LICENSE](../LICENSE).
