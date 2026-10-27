"""Reading and writing the registry file: one YAML file with `meta` (the schema), `nodes` and `edges`."""
import hashlib
import re
from pathlib import Path

import yaml

GONE = {"retired", "superseded"}     # statuses kept for the ID only: never read as logic


def fingerprint(statement: str) -> str:
    """The first eight hex digits of sha256 over the statement, whitespace collapsed and lower-cased."""
    norm = " ".join(str(statement).split()).lower()
    return hashlib.sha256(norm.encode()).hexdigest()[:8]


class StrictLoader(yaml.SafeLoader):
    """A YAML loader that refuses a mapping with the same key twice (the default keeps the last one silently)."""


def _no_duplicate_keys(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
        seen.add(key)
    return loader.construct_mapping(node, deep)


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)


def read_registry(path):
    data = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=StrictLoader) or {}
    data.setdefault("meta", {})
    data["meta"] = data["meta"] or {}
    data["nodes"] = data.get("nodes") or []
    data["edges"] = data.get("edges") or []
    return data


def load(path):
    data = read_registry(path)
    return data["meta"], data["nodes"], data["edges"]


def live(nodes):
    return [n for n in nodes if n.get("status", "active") not in GONE]


def fix_fingerprints(path, nodes):
    """Write each node's fingerprint at the end of its one-line entry, quoted (all-digit hex would otherwise read
    as a number); any other fingerprint on the line is dropped. Text surgery, so comments and layout survive.
    Returns the ids whose line could not be found."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    missing = []
    for n in nodes:
        fp = fingerprint(n["statement"])
        pat = re.compile(r"^(  - \{id: " + re.escape(n["id"]) + r",[^\n]*)\}[ \t]*$", re.M)
        m = pat.search(text)
        if not m:
            missing.append(n["id"])
            continue
        body = re.sub(r', fingerprint: "?[0-9a-f]{8}"?', "", m.group(1))
        line = body + f', fingerprint: "{fp}"}}'
        if line != m.group(0):
            text = text[:m.start()] + line + text[m.end():]
    path.write_text(text, encoding="utf-8")
    return missing
