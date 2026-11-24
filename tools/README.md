# The tools

Command-line checks and helpers that keep a project's documents, links, identifiers and tests honest at every commit,
in a hook or in CI.

A project's documents and tests rot in ways nobody sees at the moment of the edit. The work left to do is written
into a design document, which says "not yet implemented" months after it was; a work item is cited by an ID that was
renumbered; a file is moved and every link to it dies; a public document cites a private one and the cut between the
two sides leaks; a document is edited and its `updated:` stamp still names last month; an archived document is edited
and nothing says it is no longer what it was; a term is renamed and a frozen file keeps the old word with no sign it
now means something else; a test passes, and nobody has seen it fail when the thing it guards breaks; a commit
message claims a hash, an identifier and "every case" that nobody resolved.

This folder is Airone Giallo's commands, eight of them, each one file of standard-library Python beside the module
they share (`airone_tree.py`): four checks that run in a hook and in CI (the status file, the archive, the links with
the ladder, the frontmatter), a mover that keeps the references true, a mutation round, a lister of the claims a
change makes, and the gate a public repository's commits and pushes go through when the project's history stays
private. They read a project's own values from its files or their arguments, never from constants: the ladder's
cut, the graph file's `meta`, the status file's `status-meta` block, the archive's place.

It is part of Airone Giallo, described in the [repository](https://github.com/Ev3nt1ne/airone-giallo); the graph,
the other code, is a package of its own in `graph/`. The status file and the archive's log are written
into a project by the `setup` skill from its templates, their rules in their own headers; the ladder and the archive's
rules are the `doc-discipline` skill's §1; the frontmatter is the `markdown-docs` skill's §1; the mutation round is
the method of the `session` skill's verify reference, §6.

Some words recur below. A project's documents sit on a *ladder* of places, read from the bottom, each place a *rung*:
1 the system documents (`docs/`), 2 the graph (`graph.yml`), 3 the plan (`plan/`), 4 the AI documents
(`ai-docs/`), 5 the agent layer (`AGENTS.md`, `CLAUDE.md`, `RATIONALE.md`, the skills); a document cites only rungs at
or below its own. The *cut*, named in the project's instruction file, is the highest public rung: it and every rung
below it are public, every rung above it private. In the *two-repository form*, which any cut but `none` and `all`
makes, the public rungs are a repository of their own, held as a submodule inside a private *workspace* repository that
holds the rest. A *family* is the code that opens a work item's ID (`APP` in `APP-001`). The *owner* is the person who
leads the project and rules on what is theirs to decide. The *verify pass* is the second, claim-by-claim pass over a
change (§6 of the `session` skill itself, Two passes), which `claims` starts.

## Why

- **One file owns the work, and it is not a design document.** What the system *is* changes slowly and lives in the
  specification and the graph; what is *left to do* changes every session and lives in the status file, because the
  two go stale on different schedules. Where another document disagrees with the status file, the status file is
  right.
- **An ID names the item and nothing that can change.** A family and a counter, never renumbered or reused: a reused
  ID makes every old citation, in commit messages and code comments nobody will edit, point at the wrong item. The
  status file is the allocator and the next ID is derived, counting the closed file too, since a number that left is
  still taken.
- **Closed items leave, with what was chosen.** A status file too long to read whole gets skimmed, and "done" without
  the choice sends the next session to work it out again.
- **An archived document stays what it was; the record of what changed lives next to it.** The model is the errata of
  a frozen standard. An edit to an archived file goes with a row in the archive's log in the same commit; a rename is
  a dated event and a frozen file has a freeze time, so the conflicts that apply to a file are derived from the dates,
  never listed per file. A word *renamed* reads oddly in an old file; a word *reused* reads wrongly and gives no sign.
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
- **A test counts once it has failed for the right reason.** The round plants each bug, sees which tests fail, and
  restores the file; a failure that names no test is void, since a syntax error fails every suite and proves none.
- **Listing claims is the hard half of checking them.** Re-reading one's own text finds coherence, not truth; the
  lister enumerates, settles what a lookup can settle, and leaves the rest marked for the pass.

## Start

Python 3.10 or newer, standard library only, and git; the package is `airone-tools`, MIT, with no dependencies.
`check-public` also needs the `gitleaks` command, which it runs and never replaces. This gives the eight commands
below:

```sh
uv tool install 'git+https://github.com/Ev3nt1ne/airone-giallo.git#subdirectory=tools'
```

or, from a clone of the repository, `uv tool install ./tools`; `pipx install` takes the same arguments, and
`pip install` works inside a project's own venv. Each file in [src/](src/) also runs as a script from the clone without
installing (`python3 <airone-giallo>/tools/src/check_links.py`); none is ever copied into the
project. *A copied script is a second copy that the next version of Airone Giallo does not reach.*

The setup skill installs no hook of these checks; the one hook it writes is the public repository's `pre-push` gate
when the history stays private (`check-public`, below). A project that wants the checks at every commit copies these
lines into its own
`.git/hooks/pre-commit` (or the hook manager it uses), each command exiting non-zero on a finding; `<cut>` is the
last public rung its instruction file names, `all` or `none` in one repository:

```sh
#!/bin/sh
# The documents' checks, zero errors before every commit.
check-status ai-docs/status.md ai-docs/closed.md || exit 1   # with the graph: --graph graph.yml
check-archive || exit 1                 # this repository's archive and its log
check-links --cut <cut> || exit 1       # the two-repository form: check-links --public <dir> --cut <cut>
check-frontmatter || exit 1             # the documents being committed, against HEAD
```

In the two-repository form the workspace's hook runs `check-links --public <dir>` from the workspace root, which walks
the public folder too, and `check-archive --archive <dir>/archive` for the public repository's own archive; each
repository's hook runs `check-frontmatter` on its own staged documents, since a commit is made in one repository at a
time. In CI, after `pip install <airone-giallo>/tools`, the same commands run on the whole tree and on the range the
change brings:

```sh
check-status ai-docs/status.md ai-docs/closed.md
check-archive
check-links --public <dir> --cut <cut>      # one repository: check-links --cut <cut>
check-frontmatter --all
check-frontmatter --range "$BASE..HEAD"     # BASE: the commit the change starts from
```

## The commands

Every command but `check-status` and `check-archive` works on the repository holding the current folder (`--root DIR`
names another, `mutate anchors` aside); those two read the paths they are given, from the current folder. Each exits 2
on a bad argument or on a file, folder or repository it cannot read. The four checks print `error:` lines and a count,
and exit 1 on a finding, 0 when clean.

### `check-status`

Reads the status file and the closed file, reports what breaks their rules and prints the next free ID in each
family. The two files come from the setup's templates, `status.md` and `closed.md` under
`skills/setup/templates/tree/ai-docs/`, whose headers carry the rules; the status file declares its families in a
`status-meta` block, one line each, a code and what it covers:

````markdown
```status-meta
families:
  APP: the application
  DOC: the documentation
```
````

A code is 2 to 5 capitals or digits starting with a capital, or two codes joined by a hyphen when the project wants a
repository and an area (`WEB-API`); an ID is the family and a three-digit counter, `APP-001`. An item is registered
under its section with the ID the checker printed; when it closes, its row leaves the status file and a row goes into
the closed file saying what was chosen:

```markdown
| ID | Kind | Title | Outcome | Chosen | Reopen if | Reason | Closed |
|---|---|---|---|---|---|---|---|
| `APP-001` | decision | Export format for reports | done | JSON lines; ❌ CSV, which cannot hold nested fields | a consumer needs a spreadsheet | [design.md §4](design.md) | 2026-01-12 |
```

What it checks: IDs unique across both files, of a declared family and of the form `FAMILY-nnn` (a gap is not an
error, a reuse is); a closed item only in the closed file; kinds, sections and outcomes from their closed sets; an
owner on every open item, a trigger on every deferred one, a question on every one awaiting a decision; a link in
every reason; real dates; a superseded item naming what superseded it; every item ID cited in either file existing in
one of them. With `--graph GRAPH`, an item may cite a graph node by its ID and every cited node must exist, no node
may mention an item's ID (a node states what holds, which outlives the work), and no family of the status file may
share a code with a graph family. The graph file is read as `specgraph` writes it, without PyYAML.

```text
$ check-status ai-docs/status.md ai-docs/closed.md --graph graph.yml
ai-docs/status.md: 3 open item(s); ai-docs/closed.md: 1 closed item(s)
next free ID per family:
  APP-004
  DOC-002
0 error(s)
```

### `check-archive`

Holds an archive to its rules: every Markdown file under it, its `LOG.md` and `README.md` aside, carries an
`archived:` stamp in the time form, and where git is there the stamp agrees with the commit that moved the file in
(the same day in UTC, or less than a day before it, for a stamp written before midnight and committed after); every
staged change to an archived file (modified, deleted, renamed) has a new row in the staged log's Changes table naming
it; every row of both tables parses, and a conflicts row names a place where the current meaning is defined that
exists. `--archive DIR` names the folder, `archive` by default; the log's template is `LOG.md` under
`skills/setup/templates/tree/archive/`. Without git the checks that need it print `NOT RUN` and the exit code is 1: a
check that did not run is not a check that passed.

The archive is used in three moves, and the checker has a verb for two of them:

- **Archiving a document.** Rehouse first anything that lives only in it, `git mv` it into `archive/`, add the
  `archived:` stamp with the time of the move, change nothing else inside it. One commit, and no row in the log:
  adding a file to the archive is not a change to it.
- **Reading an archived file.** `check-archive read FILE` first: it prints the file's freeze time and every conflict
  dated after it, oldest first, the reused ones marked `REUSED`, or `no conflicts apply`. Without `--archive` it takes
  the archive the file is in, the nearest folder above it holding a log.
- **Renaming a term.** Rename it in the live documents one occurrence at a time, then `check-archive rename WORD`: it
  prints every line of the archive, the log aside, that holds the word whole, file by file with each file's freeze
  time, and changes nothing. The owner rules file by file: a file changed gets a row in the Changes table in the same
  commit; the files left standing are covered by one row in the conflicts table, kind `renamed` or `reused`, dated
  the time of the rename. The archive is outside every default search; `rename` and `read` are the explicit ways in.

```text
$ check-archive read archive/2026-03-design.md
archive/2026-03-design.md: archived 2026-03-05T12:00:00+00:00
conflicts dated after it, oldest first; a REUSED word reads as a word, with the wrong meaning:
  2026-03-05T12:30:00+00:00  renamed  `registry.yml`  ->  `graph.yml`  (defined in `docs/glossary.md`)
  2026-04-01T10:00:00+00:00  REUSED   "stage": a phase of the plan  ->  "stage": a deployment environment  (defined in `docs/glossary.md`)
```

### `check-links`

Resolves every relative link and image in the tracked Markdown files, nested repositories included, and checks each
anchor (`#section`) against the target's headings as a forge makes them, or an HTML id. A link from `/` is read from
the top of the repository holding the file. Links inside code and HTML comments are examples, not links.

- **The archive** (`archive/` at each repository's top, or `--archive DIR`, repeatable): a dead link or anchor inside
  it is printed as `archived:` and counted, never an error. A live document citing a file inside it is a warning: the
  archive is cited as a category at most, its folder, its README or its log. The archive is not a rung, so it has no
  side of its own: in the two-repository form it is on its repository's side like any file there.
- **The ladder**, with `--cut RUNG` (`none`, `docs`, `graph`, `plan`, `ai-docs`, `all`) in one repository,
  or `--public DIR` in the two-repository form, where everything in DIR is public and the rungs up to the cut (`plan`
  by default) sit inside it: a link, or a path written in backticks, from a public file to a private one is an error.
  A citation from a rung to a higher one is a warning. `--rung NAME=PATH[,PATH]` places a rung elsewhere, from the
  workspace root (`--rung docs=documentation/`). A file outside every rung has no side in one repository and is not
  held to the cut.
- `--exempt PATH` (repeatable) keeps a folder or a glob out of the scan as a source: a template whose links resolve only
  once it is written into a project. Airone Giallo checks itself with `check-links --exempt skills/setup/templates/`.

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
  The rows are read as `check-archive` reads them, by its own code.
- `--apply` refuses, before anything moves, a file not tracked, a target that exists, two files to one path, a move
  from one repository into another, an archived file without its row, and a file it would write that has changes not
  staged, since the undo is a checkout.

### `mutate`

Runs a mutation round (`session`'s verify reference, §6) from a JSON spec:

```json
[{"file": "src/parser.py",
  "mutations": [["M1 an empty name is accepted", "    if not name:", "    if False:"],
                ["M2 the fallback", "return DEFAULT", "return None", "equivalent: no caller reaches it"]]}]
```

```sh
mutate parser-mutations.json --test "python -m pytest -q tests/test_parser.py" --timeout 300
```

Every anchor must occur exactly once before anything is planted. Each target is copied to a backup folder, named at
the start; each mutation is planted, the tests run, the failing tests recorded, and the file restored in a `finally`;
the round ends with an unmutated control run that must be clean, and prints a caught-by table. A mutation counts as
caught only through a failing test named in the output (pytest, unittest, cargo and go test are read;
`--failed-pattern` for another runner); a failure naming no test, a timeout naming none, or a run whose output misses
`--expect-rebuild PATTERN` is void. A fourth element declares a mutation equivalent: it must survive, and its being
caught is the failure. Every write is stamped later than the one before and ahead of the clock, since a build tool,
and Python's own bytecode cache, can take a source as unchanged by its time. A killed round runs no `finally`:
restore from the backup folder it named.

`mutate anchors SPEC...` reads specs (files, or folders of them) and counts each anchor in its file, at the working
tree or at `--rev REV`; a spec or target with `ran_at` is the record of a round run at that commit, listed but never
failing. Run it before a round when code has moved, and on the commit as made.

### `claims`

Lists the claims a change makes, so each can be checked: the staged lines by default, `--range A..B`, or
`--message FILE` for a commit message read as prose. It settles commit hashes with `git cat-file`; graph identifiers
against the graph file (`--graph`, `graph.yml` by default), the families from its `meta` and the nodes by their ids;
status identifiers against the status file and the closed file (`--status`, `ai-docs/status.md` by default), the
families from its `status-meta` block; and section references (`§4.2`) against the headings of the document the line
names, the line's own file, or a `--doc`. It lists numbers, quotations and the completeness words (all, every, each,
none, only, never, always) with their lines. In code and configuration only comment lines are read.

A helper, not a gate: it exits 1 only when a hash or an identifier is unknown, and an empty list means nothing
matched, not that the change is true. Known false positive: a run of 7 to 40 hexadecimal digits with a letter and a
digit in it is read as a commit hash, so a checksum reports as an unknown hash; read each failure before believing
it.

### `check-public`

The gate a public repository's commits and pushes go through when a project's history stays private: the setup's
private-history direction, where the owner's folder is the private repository and the public one is born inside it.
The setup runs it before the first public commit; the public repository's `pre-push` hook runs it before every push.

```sh
check-public --staged [--root DIR] [--message TEXT]      # what the next commit would hold
check-public --pre-push REMOTE URL [--root DIR]          # what a push sends: git gives the refs on standard input
```

It reads two lists the private side keeps and the public side never holds, at the private repository's root (the
superproject, or `--private-root`, or `--sides` and `--markers`):

- **`public-paths.txt`**, one rule a line, a side and a path from the project's root, a folder ending in `/`:
  `public` goes into the public repository, `private` stays, and `local` is an ignored entry under a public path that
  travels with it and stays ignored there (an environment file, installed dependencies). `public SRC -> DEST`
  publishes SRC under another name (the setup's answer writes it `"SRC": "public as DEST"`); two sources for one
  public name are refused, and so is a path holding a `.git` folder or the arrow. `setup FILE` is a file the setup
  wrote on the public side, one line per file, never a folder, and an explicit `private` rule wins over it. The
  longest matching path wins, and a path no rule covers is private. `old-email-ok yes` is the owner's yes to an
  identity the old history used.
- **`public-markers.txt`**, the owner's words that must never be published, one a line. It is read as UTF-8, a
  byte-order mark at its start dropped and lines ending in LF or CRLF alike; each line is stripped of the whitespace
  around it, and every line left non-empty is a marker. The file has no comment syntax and no header, so a line
  starting with `#` is a marker too. The setup and the gate read it through one function. With none, the output says
  that no markers were given. A marker matches as plain text with case ignored and every whitespace character (line
  breaks, tabs and no-break spaces included), hyphen, underscore and dot removed on both sides, across the whole text,
  and is placed on the line where it starts; so `Wren Halloway` also hits `wren-halloway`, `WrenHalloway` and a name
  wrapped across two lines, a short marker hits inside longer words, and letters that only look alike, or accented
  ones, are not folded and do not hit. A marker that folds to fewer than 3 characters would match nothing or nearly
  everything, and is refused with a message, by the setup and by the gate (exit 2).

What fails the gate:

- a path not declared public;
- an agent tool's file (`.claude/`, `.mcp.json`, `AGENTS.md`, `CLAUDE.md`, at any depth, whatever the case of their
  letters, since a file system that ignores case reads `claude.md` as `CLAUDE.md`);
- a marker in a path, a file, a ref's name, an identity or a message, named by its number and place, never by its
  words;
- a finding of gitleaks, which is required: when it is missing, or ran without writing its report, the gate fails;
- a gitleaks configuration (`.gitleaks.toml`, `.gitleaksignore`) in the public folder that is not tracked; a tracked
  `.gitleaks.toml` is in effect, and the output says so, while a `.gitleaksignore` is never honoured;
- inside the public folder, an ignored entry that is not `local` or holds a `private` path, a `local` one not ignored
  by the public repository's own tracked rules, or an untracked file;
- the old history's e-mail as an identity.

Images and binary files are listed for a person, not read; a text file over 1 MiB is read like any other and listed
too. With `--pre-push` the gate judges the objects the push adds to the remote, not the diffs. They are every object
reachable from the pushed ids and not from the ids the remote says, on the hook's standard input, that it holds.
Remote-tracking refs are not believed, so a new branch, or a remote emptied and created again, is judged whole. Of
those objects it judges the content of every new file, every path of every new commit's tree and of any tree a pushed
ref or tag names, and the raw text of every new commit and annotated tag. That text is parsed as git writes it: the
headers run to the first blank line, and the message is the rest, searched whole, whatever it holds (a signed tag's
signature, and lines that look like headers, included). In the headers, only the `tree`, `parent` and `object` ids
and a commit's `gpgsig` (or `gpgsig-sha256`) signature are left out, since nobody wrote them; a merge's `mergetag`
holds a tag, parsed the same way, its tagger and its whole message read. Each pushed ref's name is judged too. So a marker added in one commit and removed in the
next, a file added and removed, content only a merge brings, a rename onto a marker, a tag's message, and a signed
tag merged into a commit are all stops. The secret scan reads exactly the new files, copied into a private temporary
folder; a path with an empty, `.`, `..` or `.git` part is refused and never written there. Git runs with replace refs
off in every mode, so a replace ref cannot hide what is sent, and a git command that fails stops the gate (exit 2),
never reads as an empty answer. When a path a rule made private after it was pushed blocks a push, the output says
in one line that the commits already on the remote publish it and that only a new history without them can be pushed.
The hook lives where git looks by default, the public repository's `.git/hooks`, and runs on a push from the
repository or from any worktree of it. The setup refuses to run, and to make the first commit, while a
`core.hooksPath` is in effect for the public repository, and names the command that unsets it; it cannot see one set
afterwards, or one behind a conditional include that matches only later (once a remote exists, say), and either
turns the gate off without a word. A hook manager that sets `core.hooksPath` when it installs (husky, and tools like
it, often on the first `npm install`) turns the gate off the same way; with one, add the gate's call,
`check-public --pre-push "$@"`, to that manager's own pre-push hook. After `git submodule absorbgitdirs` the hook
stops every push, and says how to put the git folder back. A clone has no hook until one is installed. The push gate reads every new object
of a push in one pass and holds their paths and texts in memory, so a long first push of a large history is slow
and needs memory in proportion; it has not been measured beyond a few hundred files. Exit 0 when
clean, 1 on a finding or a scan that could not run, 2 on a bad argument or a list it cannot read.

```text
$ check-public --staged
check-public: the staged tree of /work/larder/public
declared public: 41 of 41 file(s)
the agent tool's files: none
markers: 3 given, none found
gitleaks: ran on the 41 staged file(s), 0 finding(s)
ignore: 2 ignored entries inside, 2 local rule(s)
identity: not an e-mail of the old history
images, binary files and files over 1 MiB, listed, not read: app/logo.png (18342 B)
0 error(s)
```

## What it is not

- **Not a linter of prose.** The checks hold the shape (links, dates, sides); whether a document says something true
  is the verify pass's work, which `claims` only starts.
- **Not a fixer.** The four checks change nothing; `move-paths` changes only what it listed.
- **Not a changelog, and not a decision.** A closed item records what was chosen, not every step taken; `check-archive
  rename` lists and the log records, and which archived occurrences change is the owner's ruling, file by file.
- **Not installed by setup.** The hook lines above are the project's to copy, under its own commit rules. The one
  hook the setup writes is the public repository's `pre-push`, running `check-public`, when the history stays private.

## Tests

From this folder, with pytest and git installed:

```sh
pytest
```

The mutation rounds the tests were held to are in [tests/mutations/](tests/mutations/), one spec per command that
has had a round and one for the module they share, each anchor a line of `src/`. From the repository's root:

```sh
mutate anchors tools/tests/mutations
mutate tools/tests/mutations/check-links.json --test "cd tools && python -m pytest -q tests/test_check_links.py"
```

A round on `mutate` itself runs from a copy of `src/` outside the repository, so the round's own code is not the code
being mutated.

## Licence

MIT; see [LICENSE](../LICENSE).
