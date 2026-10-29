# The archive's log

An archive holds the documents that stopped being true or needed and must stay readable. Its rule is that nothing in
it is edited, and still two things happen to it. A file in it is touched after all: a live document moves, a link
inside an archived file dies, and someone decides to rebuild it. And the vocabulary moves on while the archive does
not: a term is renamed, or worse, reused for something else, so a file frozen before the change says the old word
with no sign that it now means something different. A file frozen after the change never had the problem.

This piece is one file beside the frozen documents, `archive/LOG.md`, with two tables: every change made to an
archived file, and every change of a word's meaning left uncorrected in the archive, each dated. Each archived file
carries one stamp, `archived:`, the time it was frozen, so the conflicts that apply to a file are derived from the
dates rather than listed per file. A checker confirms the stamps against git, refuses a change to an archived file
without its row, and tells a session which conflicts apply to the file it is about to read.

It is a piece of Airone Giallo, the kit described in the [repository](https://github.com/Ev3nt1ne/airone-giallo), and
it is useful without the rest. In a project laid out by the kit each repository has its own archive, `archive/` at
its top, beside the ladder rather than on it (`skills/doc-discipline` §1): frozen, on its repository's side, outside
every search unless named, cited by nothing live beyond a category.

## Why

The model is the errata of frozen standards: a published standard is never changed, and what is wrong with it is
recorded beside it, dated, while metadata says what later document updates it. Both cases come from the projects the
kit was extracted from.

- **The document stays what it was; the record of what changed lives next to it.** A note edited into a frozen file
  is one more edit to it, and it ages as badly as the file.
- **An archived file is edited only with a row in the log, in the same commit.** An edit without its row is the
  failure the log exists to prevent: the file is no longer what it was, and nothing says so.
- **A rename is a dated event, and a frozen file has a freeze time.** The conflicts that apply to a file are those
  dated after its freeze, as a record is read by the schema in force when it was written; no list per file is kept,
  so nothing goes stale when a file is archived or a conflict is added.
- **The freeze time is a time, not a day.** A rename and an archiving on the same day must still say which came
  first.
- **The stamp is written in the file and checked against git.** A reader, or a tool without git, reads the time from
  the file itself; git holds the same fact, the commit that moved the file in, so a stamp that disagrees is caught.
- **Two kinds of conflict, because they carry different risk.** A word *renamed* is no longer used for anything, so
  an old file reads oddly but not wrongly; a word *reused* now means something else, so an old file reads wrongly and
  gives no sign.
- **The log is append-only, the newest row on top, in a fixed shape.** The changelog convention: a reader knows where
  to look and what each row holds.

## Start

Python 3.10 or newer, standard library only; the package is `airone-archive`, MIT, with no dependencies.

1. Copy [templates/LOG.md](templates/LOG.md) into the project's `archive/`, and install the checker from the kit:
   `pip install ./archive` gives the command `check-archive`. The checker,
   [tools/check_archive.py](tools/check_archive.py), also runs as a script from the kit without installing; it is
   never copied into the project. *A copied checker is a second copy that the kit's next version does not reach.*
2. **Archiving a document.** Rehouse first anything that lives only in it. Move it with `git mv` into `archive/`, add
   the stamp to its frontmatter, the time of the move in the kit's form, and change nothing else inside it; the live
   documents that cited it cite the archive as a category at most. One commit, and no row in the log: adding a file
   to the archive is not a change to it.

   ```markdown
   ---
   title: Crash-safe saving
   archived: 2026-09-14T10:32:05+00:00
   ...
   ---
   ```

3. **Renaming a term.** Rename it in the live documents, every occurrence read and changed one by one, never by a
   blind replacement. Then run `check-archive rename <old word>`: it lists every line of the archive that holds the
   word, file by file, with each file's freeze time. The owner rules file by file: a file changed gets a row in the
   Changes table in the same commit; every file left standing is covered by one row in the conflicts table, kind
   `renamed` or `reused`, dated the time of the rename. The glossary gets the new term, and keeps the old one as
   retired, with the date.

   ```markdown
   | Date | Kind | Old | Now | Where the current meaning is defined |
   |---|---|---|---|---|
   | 2026-11-10T14:05:00+00:00 | reused | "stage": a phase of the plan | "stage": a deployment environment | `docs/glossary.md` |
   ```

4. Run the check in the hook and in CI, and `read` before reading an archived file.

## The checker

`check-archive` takes the archive folder as `--archive DIR`, `archive` by default, and one of three verbs.

- **`check-archive`**, the check. Every Markdown file under the archive, its `LOG.md` and `README.md` aside, has an
  `archived:` stamp in its frontmatter of the form `YYYY-MM-DDTHH:MM:SS+00:00`. Where git is there and the file is
  tracked, the stamp agrees with the commit that moved the file into the archive (renames inside the archive are
  followed back to it): the same day in UTC, or less than a day before it, for a stamp written before midnight and
  committed after; a file being added in the commit being made is compared with the present time. Every staged
  change to an archived file (modified, deleted, renamed, changed type) has a new row in the staged log's Changes
  table naming it, a row the last commit's log did not hold, with `HEAD` or a hash in its Commit column. Every row of
  both tables parses: a Changes row has a date, the file, what, why and the commit; a conflicts row has its time, a
  kind `renamed` or `reused`, the old and the new meaning, and a place where the current meaning is defined that
  exists: a path from the folder holding the archive, a link from the log, or a URL. Exits 1 on any failure.
- **`check-archive read FILE`** prints the file's freeze time and every conflict dated after it, oldest first, the
  reused ones marked `REUSED`, or `no conflicts apply`. Without a stamp it takes the time from git and says so; with
  neither it lists every conflict and exits 1.
- **`check-archive rename WORD`** prints every line of the archive, the log aside, that holds the word whole, in any
  case: the file with its freeze time, each line with its number, and the two outcomes for that file. It changes
  nothing and exits 0 whether or not it finds the word. The archive is outside every default search; this is the
  explicit way in.

Every verb exits 2 on a bad argument or a file it cannot read. Without git, or outside a repository, the checks that
need it are printed as `NOT RUN`, never counted as passed, and the exit code is 1; the rest still run.

```text
$ check-archive read archive/2026-03-design.md
archive/2026-03-design.md: archived 2026-03-05T12:00:00+00:00
conflicts dated after it, oldest first; a REUSED word reads as a word, with the wrong meaning:
  2026-03-05T12:30:00+00:00  renamed  `registry.yml`  ->  `graph.yml`  (defined in `docs/glossary.md`)
  2026-04-01T10:00:00+00:00  REUSED   "stage": a phase of the plan  ->  "stage": a deployment environment  (defined in `docs/glossary.md`)
```

## What it is not

- **Not an annotation of the archived files.** Nothing is written into them but the stamp at archiving and the
  changes the log records.
- **Not a list of conflicts per file.** The dates derive it.
- **Not a decision.** `rename` lists and the log records; which archived occurrences change is the owner's ruling,
  file by file.
- **Not a way back into search.** The archive stays out of every default search; `rename` and `read` name it on
  purpose.

## Tests

From the repository's root, with pytest and git installed:

```sh
pytest archive/tools
```

## Licence

MIT; see [LICENSE](../LICENSE).
