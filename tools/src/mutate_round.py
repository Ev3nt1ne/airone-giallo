#!/usr/bin/env python3
"""Run a mutation round: plant each bug, run the tests, restore; and check that a round's anchors still hold.

    mutate SPEC --test CMD [--expect-rebuild PATTERN] [--timeout S]   the round
    mutate anchors SPEC... [--rev REV]                                every anchor of the specs, read only
    python3 mutate_round.py ...                                       from the kit, without installing

A test counts once it has failed for the right reason (the `session` skill's verify method, §6). The round plants
each mutation in its file, runs the test command, records which tests failed, and restores the file, then ends with
an unmutated control run that must be clean.

SPEC is JSON: a list of targets, or an object with `targets` and an optional `ran_at`:

    [{"file": "src/parser.py",
      "mutations": [["M1 an empty name is accepted", "if not name:", "if False:"],
                    ["M2 the fallback, unreachable", "return DEFAULT", "return None", "equivalent: no caller
                     reaches it"]]}]

Each mutation is a name, the exact text to replace (its anchor) and the text to put in its place. A fourth element
declares it equivalent, with the reason: it cannot change behaviour, so it is expected to survive, and its being
caught is the failure, since the stated reason is false. A file's path is from the repository's top.

Its guards:
  * every anchor occurs exactly once in its file, checked for every target before anything is planted;
  * each target is copied to a backup folder, named when the round starts, and restored in a `finally`; a killed
    process runs no `finally`, so after a round stopped from outside restore from that folder, then run
    `mutate anchors`;
  * each write is stamped later than the one before and a second ahead of the clock, for a build tool that takes a
    source as unchanged when its time is older than its last build;
  * a mutation is caught only through a failing test named in the output (pytest, unittest, cargo, go test, or
    --failed-pattern): a command that fails without naming a test (a syntax error, a collection error) is VOID, a
    mutation that did not exercise anything;
  * with --expect-rebuild PATTERN, a run whose output does not match it is VOID: the code under test was not rebuilt.

`mutate anchors` reads each spec (files, or folders of .json specs) and counts every anchor in its file, at the
working tree or at --rev; a target or spec carrying `ran_at` is the record of a round run at that commit, listed but
never failing.

Exit 0 when every mutation was caught (or survived as declared equivalent) and the control was clean, or every live
anchor matches once; 1 when a mutation survived, an equivalent one was caught, a run was void or timed out without a
name, the control failed, or an anchor is off; 2 on a bad argument or spec. Standard library only.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import airone_tree as at

# A failing test as the common runners name it; group 1 is the name.
FAILED_PATTERNS = (
    r"^FAILED (\S+::\S+)",                    # pytest's short summary
    r"^ERROR (\S+::\S+)",                     # pytest: an error in a test's own setup
    r"^(?:FAIL|ERROR): (\S+ \([^)]*\))",      # unittest
    r"^test (\S+) \.\.\. FAILED",             # cargo test
    r"^\s*--- FAIL: (\S+)",                   # go test
)


class SpecError(Exception):
    """A spec that cannot be read or does not have the shape: exit 2."""


def load_spec(text, name):
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as e:
        raise SpecError(f"{name}: not JSON: {e}") from e
    record = doc.get("ran_at") if isinstance(doc, dict) else None
    targets = doc.get("targets") if isinstance(doc, dict) else doc
    if not isinstance(targets, list):
        raise SpecError(f"{name}: a list of targets, or an object with `targets`")
    out = []
    for i, t in enumerate(targets):
        if not isinstance(t, dict) or not isinstance(t.get("file"), str) or not isinstance(t.get("mutations"), list):
            raise SpecError(f"{name}: target {i}: an object with `file` and `mutations`")
        muts = []
        for j, m in enumerate(t["mutations"]):
            if not (isinstance(m, list) and len(m) in (3, 4) and all(isinstance(x, str) for x in m)):
                raise SpecError(f"{name}: {t['file']}: mutation {j}: [name, old text, new text] and optionally the "
                                f"reason it is equivalent")
            if not m[1]:
                raise SpecError(f"{name}: {t['file']}: {m[0]}: an empty anchor")
            muts.append((m[0], m[1], m[2], m[3] if len(m) == 4 else None))
        out.append({"file": t["file"], "mutations": muts, "ran_at": t.get("ran_at") or record})
    return out


# ---------------------------------------------------------------- the round

class Stamper:
    """Every write stamped strictly later than the one before, and ahead of the clock."""

    def __init__(self):
        self.last = time.time()

    def touch(self, path):
        self.last = max(self.last + 2, time.time() + 1)
        os.utime(path, (self.last, self.last))


def run_tests(cmd, root, timeout):
    """(exit code or None on a timeout, the output)."""
    try:
        p = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"") + (e.stderr or b"")
        return None, out.decode(errors="replace") if isinstance(out, bytes) else out


def failed_tests(output, patterns):
    names = []
    for rx in patterns:
        for m in re.finditer(rx, output, re.M):
            if m.group(1) not in names:
                names.append(m.group(1))
    return names


def verdict(code, output, failed, equivalent, rebuild):
    """(verdict, whether it is a pass for the round)."""
    if rebuild is not None and not re.search(rebuild, output, re.M):
        return "VOID: no rebuild in the output", False
    if code is None:
        return ("caught (timed out)", True) if failed else ("VOID: timed out, no failing test named", False)
    if code != 0 and not failed:
        return f"VOID: exit {code}, no failing test named", False
    caught = code != 0
    if equivalent:
        return ("CAUGHT, but declared equivalent", False) if caught else ("survived, as declared equivalent", True)
    return ("caught", True) if caught else ("SURVIVED", False)


def round_(targets, root, cmd, timeout, rebuild, patterns, out=None, keep=None):
    """Run the round; return the exit code."""
    out = out or sys.stdout
    off = []
    for t in targets:
        path = root / t["file"]
        if not path.is_file():
            off.append(f"{t['file']}: no such file")
            continue
        text = path.read_text(encoding="utf-8")
        for name, old, _, _ in t["mutations"]:
            n = text.count(old)
            if n != 1:
                off.append(f"{t['file']}: {name}: the anchor occurs {n} time(s), not once")
    if off:
        for line in off:
            print(f"anchor: {line}", file=out)
        print("the round did not start: nothing was planted", file=out)
        return 1
    backup = Path(tempfile.mkdtemp(prefix="mutate-backup-"))
    print(f"backups of the targets: {backup}", file=out)
    stamper, rows, bad = Stamper(), [], 0
    for i, t in enumerate(targets):
        path = root / t["file"]
        saved = backup / f"{i}-{path.name}"
        shutil.copy2(path, saved)
        pristine = saved.read_text(encoding="utf-8")
        print(f"== {t['file']}", file=out)
        try:
            for name, old, new, equivalent in t["mutations"]:
                path.write_text(pristine.replace(old, new, 1), encoding="utf-8")
                stamper.touch(path)
                code, output = run_tests(cmd, root, timeout)
                failed = failed_tests(output, patterns)
                what, ok = verdict(code, output, failed, equivalent, rebuild)
                bad += not ok
                rows.append((t["file"], name, what, failed))
                print(f"  {name}: {what}" + (f"; failed: {', '.join(failed)}" if failed else ""), file=out)
                if equivalent:
                    print(f"      equivalent: {equivalent}", file=out)
                if keep is not None:
                    (keep / f"{len(rows):03d}.txt").write_text(f"{t['file']}: {name}\n{output}", encoding="utf-8")
        finally:
            shutil.copyfile(saved, path)
            stamper.touch(path)
    code, output = run_tests(cmd, root, timeout)
    failed = failed_tests(output, patterns)
    clean = code == 0 and not failed and (rebuild is None or re.search(rebuild, output, re.M))
    if keep is not None:
        (keep / "control.txt").write_text(output, encoding="utf-8")
    print(f"control, unmutated: {'clean' if clean else 'FAILED'}" +
          (f"; failed: {', '.join(failed)}" if failed else "") + ("" if clean or code is not None else "; timed out"),
          file=out)
    shutil.rmtree(backup, ignore_errors=True)
    print("\n| File | Mutation | Verdict | Caught by |\n|---|---|---|---|", file=out)
    for file, name, what, failed in rows:
        print(f"| {file} | {name} | {what} | {', '.join(failed) or '-'} |", file=out)
    print(f"\nround: {len(rows)} mutation(s), {bad} not caught, void or wrongly caught; control "
          f"{'clean' if clean else 'FAILED'}", file=out)
    return 0 if bad == 0 and clean else 1


# ---------------------------------------------------------------- anchors

def spec_files(paths):
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            out += sorted(q for q in p.rglob("*.json") if q.is_file())
        else:
            out.append(p)
    return out


def anchors(paths, rev=None, out=None):
    out = out or sys.stdout
    root = at.top(".")
    cache = {}

    def text(rel):
        if rel not in cache:
            if rev:
                p = at.git(root, "show", f"{rev}:{rel}")
                cache[rel] = p.stdout if p.returncode == 0 else None
            else:
                try:
                    cache[rel] = (root / rel).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    cache[rel] = None
        return cache[rel]

    live, records = [], []
    counts = {"specs": 0, "anchors": 0, "once": 0}
    for spec in spec_files(paths):
        try:
            rel = spec.resolve().relative_to(root).as_posix()
        except ValueError:
            raise at.Usage(f"{spec} is not inside the repository {root}") from None
        raw = text(rel)
        if raw is None:
            raise at.Usage(f"{spec}: cannot be read" + (f" at {rev}" if rev else ""))
        counts["specs"] += 1
        for t in load_spec(raw, rel):
            src = text(t["file"])
            for name, old, _, _ in t["mutations"]:
                counts["anchors"] += 1
                if src is None:
                    what = f"{rel}: {name}: {t['file']} does not exist"
                else:
                    n = src.count(old)
                    if n == 1:
                        counts["once"] += 1
                        continue
                    what = f"{rel}: {name}: the anchor occurs {n} time(s) in {t['file']}"
                (records if t["ran_at"] else live).append(what + (f" (ran_at {t['ran_at']})" if t["ran_at"] else ""))
    print(f"anchors at {rev or 'the working tree'}: {counts['specs']} spec(s), {counts['anchors']} anchor(s), "
          f"{counts['once']} matching once", file=out)
    if live:
        print(f"{len(live)} off in live specs, which cannot run until each is re-pointed:", file=out)
        for line in live:
            print(f"  {line}", file=out)
    if records:
        print(f"{len(records)} off in records (ran_at: the round's record, not kept live):", file=out)
        for line in records:
            print(f"  {line}", file=out)
    return 1 if live else 0


# ---------------------------------------------------------------- the command

def round_parser():
    p = argparse.ArgumentParser(prog="mutate", description="Run a mutation round; `mutate anchors SPEC...` checks "
                                                           "the specs' anchors.")
    p.add_argument("spec", metavar="SPEC")
    p.add_argument("--test", metavar="CMD", required=True, help="the test command, run at the repository's top")
    p.add_argument("--expect-rebuild", metavar="PATTERN",
                   help="a regular expression every run's output must match, or the run is void")
    p.add_argument("--failed-pattern", metavar="REGEX", action="append",
                   help="how the command names a failing test, group 1 the name; repeatable (default: pytest, "
                        "unittest, cargo, go)")
    p.add_argument("--timeout", metavar="S", type=float, default=None, help="seconds a run may take")
    p.add_argument("--keep-output", metavar="DIR", help="write each run's full output into DIR")
    p.add_argument("--root", metavar="DIR", help="the repository (default: the one holding the current folder)")
    return p


def anchors_parser():
    p = argparse.ArgumentParser(prog="mutate anchors", description="Count every anchor of the specs in its file.")
    p.add_argument("specs", nargs="+", metavar="SPEC", help="a spec file, or a folder of them")
    p.add_argument("--rev", metavar="REV", help="read the specs and their files at this git revision")
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    try:
        if argv and argv[0] == "anchors":
            args = anchors_parser().parse_args(argv[1:])
            return anchors(args.specs, args.rev)
        args = round_parser().parse_args(argv)
        root = at.top(args.root or ".")
        spec = Path(args.spec)
        try:
            raw = spec.read_text(encoding="utf-8")
        except OSError as e:
            raise at.Usage(f"cannot read {spec}: {e.strerror}") from e
        targets = load_spec(raw, str(spec))
        keep = None
        if args.keep_output:
            keep = Path(args.keep_output)
            keep.mkdir(parents=True, exist_ok=True)
        patterns = tuple(args.failed_pattern) if args.failed_pattern else FAILED_PATTERNS
        for rx in patterns + ((args.expect_rebuild,) if args.expect_rebuild else ()):
            try:
                re.compile(rx)
            except re.error as e:
                raise at.Usage(f"not a regular expression: {rx}: {e}") from e
        return round_(targets, root, args.test, args.timeout, args.expect_rebuild, patterns, keep=keep)
    except (at.Usage, SpecError) as e:
        print(e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
