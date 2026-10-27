"""W11: a node's `where` names the document that defines it, and every section and ID it cites is found there.

Everything project-specific is read from the registry's `meta`: `where_aliases` maps a short name to a path, and
`where_forms` says how sections and IDs are written (the defaults below are plain Markdown conventions).
"""
import re
from pathlib import Path

DEFAULT_WHERE_FORMS = {
    "section_mark": "§",                                       # a section token starts with it: §4.2
    "id": r"^[A-Z]{2,5}-(?:[0-9]{2,3}|[a-z0-9][a-z0-9-]*)$",  # what an ID token looks like (others are prose)
    "heading": r"^#{1,6}\s+§?(\S+)",                           # a heading; its first word is a section number
    "lead": r"^\*\*§?([0-9][0-9A-Za-z.]*)\b",                  # a sub-section written as a bold lead
    "item": r"^([0-9]+)\.\s",                                  # a numbered item: under heading 3, "1." is 3.1
    "folder_files": ["README.md"],                             # what a folder token reads, as globs inside it
}


class Forms:
    def __init__(self, meta):
        f = dict(DEFAULT_WHERE_FORMS)
        f.update((meta or {}).get("where_forms") or {})
        self.mark = f["section_mark"]
        self.id = re.compile(f["id"])
        self.heading = re.compile(f["heading"]) if f.get("heading") else None
        self.lead = re.compile(f["lead"]) if f.get("lead") else None
        self.item = re.compile(f["item"]) if f.get("item") else None
        self.folder_files = list(f.get("folder_files") or [])
        self.aliases = (meta or {}).get("where_aliases") or {}


def where_files(token, root, forms):
    """The documents a file token names, under root: the path itself; the path with .md; a folder's files
    (`where_forms.folder_files`); and the one file a prefix names (`notes/part-1` reads `notes/part-1-*.md`).
    Empty when nothing resolves."""
    token = forms.aliases.get(token, token)
    base = Path(root) / token
    out = []
    if base.is_file():
        out.append(base)
    if (base.parent / (base.name + ".md")).is_file():
        out.append(base.parent / (base.name + ".md"))
    if base.is_dir():
        for g in forms.folder_files:
            out += sorted(f for f in base.glob(g) if f.is_file())
    if base.parent.is_dir():
        out += sorted(f for f in base.parent.glob(base.name + "-*.md") if f.is_file())
    seen, uniq = set(), []
    for f in out:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq


def where_headings(text, forms):
    """The sections a document has, as their numbers are written: the first word of every heading; a bold lead;
    a numbered item under a numbered heading."""
    out, current = set(), None
    for line in text.splitlines():
        m = forms.heading.match(line) if forms.heading else None
        if m:
            current = m.group(1).rstrip(".:,;—-")
            out.add(current)
            continue
        m = forms.lead.match(line) if forms.lead else None
        if m:
            out.add(m.group(1).rstrip("."))
            continue
        m = forms.item.match(line) if forms.item else None
        if m and current and current[0].isdigit():
            out.add(f"{current}.{m.group(1)}")
    return out


def check_where(where, root, forms):
    """What a `where` value fails to resolve, as (kind, token) with kind 'file', 'section' or 'id', and whether
    the value names a document at all. A `where` is one or more references separated by ';'. In each, a file token
    has a slash, ends in .md or is an alias; a section token starts with the section mark, and several may share one
    token joined by '/'; an ID token matches `where_forms.id`; every other word is prose and is not read."""
    problems, named = [], False
    mark = forms.mark
    for ref in str(where).split(";"):
        tokens = []
        for t in ref.split():
            t = t.strip(",()")
            if t.startswith(mark):
                for x in t.split("/"):
                    x = x[len(mark):] if x.startswith(mark) else x
                    if x:
                        tokens.append(x if forms.id.match(x) else mark + x)
            else:
                tokens.append(t)
        files = [t for t in tokens
                 if ("/" in t or t.endswith(".md") or t in forms.aliases) and not t.startswith(mark)]
        if not files:
            continue
        named = True
        docs = []
        for f in files:
            found = where_files(f, root, forms)
            if not found:
                problems.append(("file", f))
            docs += found
        if not docs:
            continue
        text = "".join(d.read_text(encoding="utf-8", errors="replace") for d in docs)
        heads = where_headings(text, forms)
        for t in tokens:
            if t.startswith(mark):
                sec = t[len(mark):].rstrip(".")
                if sec not in heads:
                    problems.append(("section", t))
            elif forms.id.match(t) and t not in text:
                problems.append(("id", t))
    return problems, named
