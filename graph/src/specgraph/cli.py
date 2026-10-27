"""The command line. Its name is set in one place, pyproject.toml's [project.scripts]; the code reads it from argv."""
import argparse
import datetime
import os
import sys
from importlib import resources
from pathlib import Path

import yaml

from . import batch, view
from .lint import report_cascade, run_lint, summary_lines, what_if_lines, where_root
from .registry import fix_fingerprints, load, read_registry

PROFILES = ("lite", "full")


def prog_name():
    name = os.path.basename(sys.argv[0] or "")
    return "python -m specgraph" if name in ("", "__main__.py", "-c") else name


def _registry_arg(p):
    p.add_argument("--registry", metavar="PATH", default="registry.yml",
                   help="the registry file (default: registry.yml in the current folder)")


def parser():
    ap = argparse.ArgumentParser(prog=prog_name(), description="A specification graph whose truth is computed "
                                 "place by place: the lint, the read side, the batch tool.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="write an empty registry with its meta")
    p.add_argument("--profile", choices=PROFILES, default="lite")
    _registry_arg(p)

    p = sub.add_parser("lint", help="check the registry; with --what-if, simulate a change")
    _registry_arg(p)
    p.add_argument("--fix", action="store_true", help="write fingerprints back into the registry")
    p.add_argument("--what-if", metavar="ID|PLACE", help="simulate revising a node, or what we believe about a place")
    p.add_argument("--today", metavar="YYYY-MM-DD", help="the date L-9 measures staleness from (default: today)")
    p.add_argument("--root", metavar="DIR", help="the folder `where` resolves under (default: the registry's)")

    p = sub.add_parser("near", help="nodes whose id, statement or `where` holds every word")
    p.add_argument("words", nargs="+")
    p.add_argument("--at", metavar="PLACE", help="only nodes whose domain covers PLACE")
    _registry_arg(p)
    p = sub.add_parser("show", help="those nodes, with what the engine computes and their edges")
    p.add_argument("ids", nargs="+")
    _registry_arg(p)
    p = sub.add_parser("why", help="a node's justification, premises, checks, open problems, and why it holds or not")
    p.add_argument("id")
    _registry_arg(p)
    p = sub.add_parser("at", help="the nodes placed on a place, grouped by what holds there")
    p.add_argument("place")
    _registry_arg(p)
    p = sub.add_parser("draw", help="a node's neighbourhood as Mermaid, or Graphviz with --dot")
    p.add_argument("id")
    p.add_argument("--depth", type=int, default=2)
    p.add_argument("--dot", action="store_true")
    _registry_arg(p)

    p = sub.add_parser("batch", help="preview a batch of changes; --apply to apply it")
    p.add_argument("batch")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--additive", action="store_true", help="apply only if the preview reads the batch as tier A")
    p.add_argument("--root", metavar="DIR")
    p.add_argument("--today", metavar="YYYY-MM-DD")
    _registry_arg(p)
    p = sub.add_parser("actual", help="what changed since a git revision: outcomes on every place")
    p.add_argument("rev")
    _registry_arg(p)
    return ap


def profile_text(name):
    return resources.files("specgraph").joinpath("profiles", f"{name}.yml").read_text(encoding="utf-8")


def cmd_init(a):
    path = Path(a.registry)
    if path.exists():
        print(f"{path} exists; not overwritten", file=sys.stderr)
        return 1
    path.write_text(profile_text(a.profile), encoding="utf-8")
    print(f"wrote {path} ({a.profile} profile)")
    return 0


def cmd_lint(a):
    reg = Path(a.registry)
    try:
        meta, nodes, edges = load(reg)
    except yaml.YAMLError as ex:
        print(f"  ERROR L-1 {reg.name} cannot be read: {' '.join(str(ex).split())}")
        print(f"{prog_name()} lint: 1 error(s), 0 warning(s)")
        return 1
    today = datetime.date.fromisoformat(a.today) if a.today else None
    res = run_lint(meta, nodes, edges, root=where_root(reg, a.root), today=today, fixing=a.fix)
    if res.drifted:
        print(f"L-6 CHANGED since last review: {', '.join(res.drifted)}")
        print("\n".join(report_cascade(res.logic, res.drifted)))
    if a.what_if:
        lines, code = what_if_lines(res, a.what_if)
        print("\n".join(lines))
        if code is not None:
            return code
    if a.fix:
        missing = fix_fingerprints(reg, nodes)
        res.errors += [f"--fix could not locate node line for {m}" for m in missing]
        print(f"--fix: fingerprints written for {len(nodes)} nodes")
    print("\n".join(summary_lines(res, len(nodes), len(edges), prog=f"{prog_name()} lint")))
    return 1 if res.errors else 0


def main(argv=None):
    a = parser().parse_args(argv)
    if a.cmd == "init":
        return cmd_init(a)
    if a.cmd == "lint":
        return cmd_lint(a)
    if a.cmd == "batch":
        today = datetime.date.fromisoformat(a.today) if a.today else None
        try:
            return batch.run(a.batch, a.registry, a.root, a.apply, a.additive, today)
        except batch.BatchError as ex:
            print(ex, file=sys.stderr)
            return 1
    if a.cmd == "actual":
        return batch.actual(a.rev, a.registry)
    data = read_registry(a.registry)
    name = Path(a.registry).name
    if a.cmd == "near":
        return view.run("near", a.words, data, name, at=a.at)
    if a.cmd == "show":
        return view.run("show", a.ids, data, name)
    if a.cmd == "why":
        return view.run("why", [a.id], data, name)
    if a.cmd == "at":
        return view.run("at", [a.place], data, name)
    if a.cmd == "draw":
        return view.run("draw", [a.id], data, name, depth=a.depth, dot=a.dot)
    return 2


if __name__ == "__main__":
    sys.exit(main())
