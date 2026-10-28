# Using `iwe` with a project's documents

`iwe` is an open-source command-line tool that indexes Markdown files by frontmatter and links and answers
queries over them. Nothing in the `markdown-docs` skill needs it; where a project has it, it does the index steps
faster than shell tools. Check every flag against `iwe <command> --help`; `iwe docs` prints the query language
and the configuration reference.

## Setup, once per project

```sh
cd DOCS                      # or the repository root, if documents live in several folders
iwe init --dry-run           # shows the detected settings and how many files `normalize` would rewrite
iwe init --auto              # writes .iwe/config.toml from what it detected; touches nothing else
```

Read the written config: each value is labelled detected, assumed or overridden, with its evidence. Two values
decide whether the rewriting commands are safe (§3): `refs_path` (links relative to the file, or to the root) and
`refs_extension` (links written with `.md` or without). Commit `.iwe/config.toml`.

## The index steps, with iwe

| Step | Command |
|---|---|
| the list: names only | `iwe find --filter 'type: decision' -f keys` |
| the summaries, no bodies | `iwe find --filter 'tags: saving' --project 'title,description'` |
| one document, one level of context | `iwe retrieve -k DOCS/design --expand-references 1` |

- `--project` is what keeps the summaries step cheap: *without it `find` returns the documents' content, and you
  pay for the bodies while believing you are scanning an index.*
- Limit what you pull with `--limit`, `--max-documents` or `--max-tokens`. *Unlimited expansion
  (`--expand-includes 0`) can return the whole store.*

## `rename` and `normalize` rewrite every file they touch

Both re-emit each file in the project's canonical form, applying `refs_path` and `refs_extension` to every link in
it, not only the link you meant. Before the first `rename` or `normalize`, measure how the links are written and set
those two values to match; where they cannot match (documents that link to code, scripts or folders), never `rename`
or `normalize`: move with `git mv`, fix the links by hand, then run the dead-link check of the skill's §6. Write the
verdict at the top of `.iwe/config.toml`, as a comment, so the next session need not measure again.

## Two things to know

- `iwe` reports a link to a folder or a non-Markdown file as unresolved: *its graph holds documents only.* The
  skill's dead-link check is the authority on whether a link works.
- A link alone on its own line is an **inclusion** to `iwe` ("this document includes that one"); a link inside a
  sentence is a cross-reference. Never leave a "see also" alone on a line: *it silently becomes structure.*
