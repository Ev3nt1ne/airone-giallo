"""Fixtures shared by the tests: a full-profile meta read with two neutral axes, and small registries written to a
temporary folder and run through the command line in-process."""
import contextlib
import io
import tempfile
from pathlib import Path

import yaml

from specgraph import cli

AXES = [{"name": "zone", "values": ["Z1", "Z2", "Z3"], "interfaces": True},
        {"name": "stage", "values": ["DEV", "BETA", "PROD", "SCALE"], "ordered": True}]
FULL = yaml.safe_load(cli.profile_text("full"))["meta"]
LITE = yaml.safe_load(cli.profile_text("lite"))["meta"]
META = dict(FULL, axes=AXES, orphan_exempt=["check", "question"])

# The fixtures' default kind and support by family: a convenience of these tests only. The lint never reads a
# family; tests that say so give the kind explicitly.
DEFAULT_KIND = {
    "OBJ": ("objective", "satisfier"), "REQ": ("requirement", "satisfier"), "GOAL": ("goal", "premises"),
    "EXP": ("expectation", "satisfier"), "ASM": ("assumption", "given"),
    "DEC": ("decision", "chosen"), "ATK": ("threat", None), "EVD": ("evidence", None), "CHK": ("check", None),
    "QST": ("question", None), "REC": ("record", None), "JUS": ("justification", None),
}

SPEC = ("# Spec\n\n## 1. One\n\nATK-01 and #7 are named here.\n\n### 1.2 Two\n\n## 7. Choices\n\n"
        "1. **First problem.** text\n2. **Second.** text\n\n## 8. Runs\n\n**8.3 On one machine.** text\n")


def write(meta, nodes, edges, d):
    """The registry, and beside it the one document the fixtures' `where` values point at."""
    p = Path(d) / "registry.yml"
    p.write_text(yaml.safe_dump({"meta": meta, "nodes": nodes, "edges": edges}, sort_keys=False))
    (Path(d) / "spec.md").write_text(SPEC)
    return p


def call(argv):
    """Run the command line in-process: (exit code, stdout + stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(argv)
        except SystemExit as ex:
            code = ex.code
    return code, out.getvalue() + err.getvalue()


def run(nodes, edges, *extra, base=None, **meta_over):
    """The lint on a throwaway registry."""
    meta = dict(base or META, orphan_ok={})
    meta.update(meta_over)
    with tempfile.TemporaryDirectory() as d:
        p = write(meta, nodes, edges, d)
        return call(["lint", "--registry", str(p), *extra])


def graph(nodes, edges, *args, base=None, **meta_over):
    """A read-side command on a throwaway registry."""
    meta = dict(base or META, orphan_ok={})
    meta.update(meta_over)
    with tempfile.TemporaryDirectory() as d:
        p = write(meta, nodes, edges, d)
        return call([*args, "--registry", str(p)])[1]


def node(nid, domain=None, **kw):
    fam = nid.split("-")[0]
    n = {"id": nid, "statement": f"statement of {nid}", "where": "spec.md §1"}
    kind, support = DEFAULT_KIND[fam]
    n["kind"] = kw.pop("kind", kind)
    if "support" in kw:                    # given explicitly: kept, even where the lint must refuse it
        n["support"] = kw.pop("support")
    elif support is not None and n["kind"] in META["assertion_kinds"]:
        n["support"] = support
    if domain is not None:
        n["domain"] = domain
    if n.get("support") == "given":
        n.update(reviewed="2024-01-10", watch=365)
    n.update(kw)
    return {k: v for k, v in n.items() if v is not None}


def edge(a, t, b, **kw):
    e = {"from": a, "type": t, "to": b}
    e.update(kw)
    return e


def report(out):
    """A cascade report alone, without the lint's own lines after it."""
    return out.split("cascade:")[1].split("\n\n")[0]


def section(out, title):
    """The lines of one part of a cascade report: "fail", "still hold", "flagged" or "did not hold"."""
    lines = report(out).splitlines()
    heads = [i for i, line in enumerate(lines) if "node(s)" in line] + [len(lines)]
    for a, b in zip(heads, heads[1:]):
        if title in lines[a]:
            return "\n".join(lines[a + 1:b])
    return ""
