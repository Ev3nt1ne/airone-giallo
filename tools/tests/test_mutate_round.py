"""Tests for mutate: a round on a small invented module and its unittest suite, every verdict it can give, the
restore, and the anchors verb."""

import io
from pathlib import Path
import json
import sys

import pytest

import mutate_round as mr
from conftest import run_tool

CODE = '''def add(a, b):
    return a + b


def sign(x):
    if x < 0:
        return -1
    return 1


def label(x):
    return "big" if x > 100 else "small"  # only ever called with x <= 100 in this module's tests
'''
TESTS = '''import unittest
from calc import add, sign


class T(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_sign(self):
        self.assertEqual(sign(-4), -1)
        self.assertEqual(sign(4), 1)


if __name__ == "__main__":
    unittest.main()
'''
UNITTEST = f'"{sys.executable}" -m unittest -v test_calc'


@pytest.fixture
def calc(repo):
    repo.write({"calc.py": CODE, "test_calc.py": TESTS}).commit()
    return repo


def spec(repo, mutations, name="spec.json", file="calc.py", **extra):
    target = {"file": file, "mutations": mutations}
    doc = dict(extra, targets=[target]) if extra else [target]
    path = repo.root / "specs" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(doc, indent=2))
    return path


def mutate(repo, *args):
    return run_tool("mutate_round", *[str(a) for a in args], cwd=repo.root)


def test_every_mutation_caught_and_the_control_clean(calc):
    s = spec(calc, [["M1 add subtracts", "return a + b", "return a - b"],
                    ["M2 negatives are positive", "        return -1", "        return 1"]])
    code, out, _ = mutate(calc, s, "--test", UNITTEST)
    assert code == 0, out
    assert "M1 add subtracts: caught; failed: test_add (test_calc.T.test_add)" in out
    assert "| calc.py | M2 negatives are positive | caught | test_sign (test_calc.T.test_sign) |" in out
    assert "control, unmutated: clean" in out
    assert calc.read("calc.py") == CODE


def test_a_survivor_fails_the_round(calc):
    s = spec(calc, [["M1 big is small", '"big" if', '"small" if']])
    code, out, _ = mutate(calc, s, "--test", UNITTEST)
    assert code == 1 and "M1 big is small: SURVIVED" in out and "1 not caught" in out


def test_an_equivalent_mutation_must_survive(calc):
    s = spec(calc, [["E1 big is small", '"big" if', '"small" if', "no test calls label above 100"]])
    code, out, _ = mutate(calc, s, "--test", UNITTEST)
    assert code == 0 and "survived, as declared equivalent" in out
    s = spec(calc, [["E2 add subtracts", "return a + b", "return a - b", "a claim that is false"]])
    code, out, _ = mutate(calc, s, "--test", UNITTEST)
    assert code == 1 and "CAUGHT, but declared equivalent" in out


def test_an_anchor_not_found_once_stops_the_round_before_anything_runs(calc):
    marker = calc.root / "ran"
    for anchor in ("return a * b", "return"):
        s = spec(calc, [["M1 fine", "return a + b", "return a - b"], ["M2 off", anchor, "x"]])
        code, out, _ = mutate(calc, s, "--test", f"touch {marker}")
        assert code == 1 and "M2 off: the anchor occurs" in out and "nothing was planted" in out
    assert not marker.exists() and calc.read("calc.py") == CODE


def test_a_missing_target_stops_the_round(calc):
    s = spec(calc, [["M1", "x", "y"]], file="nowhere.py")
    code, out, _ = mutate(calc, s, "--test", UNITTEST)
    assert code == 1 and "nowhere.py: no such file" in out


def test_a_failure_naming_no_test_is_void(calc):
    s = spec(calc, [["M1 a syntax error", "return a + b", "return a +"]])
    code, out, _ = mutate(calc, s, "--test", UNITTEST)
    assert code == 1 and "VOID: exit" in out


def test_a_broken_suite_fails_the_control(calc):
    calc.write({"test_calc.py": TESTS.replace("add(2, 3), 5", "add(2, 3), 6")}).commit()
    s = spec(calc, [["M1 add subtracts", "return a + b", "return a - b"]])
    code, out, _ = mutate(calc, s, "--test", UNITTEST)
    assert code == 1 and "control, unmutated: FAILED" in out


def test_the_rebuild_guard(calc):
    s = spec(calc, [["M1 add subtracts", "return a + b", "return a - b"]])
    code, out, _ = mutate(calc, s, "--test", f"echo Compiling calc && {UNITTEST}", "--expect-rebuild",
                          "^Compiling calc")
    assert code == 0, out
    code, out, _ = mutate(calc, s, "--test", UNITTEST, "--expect-rebuild", "^Compiling calc")
    assert code == 1 and "VOID: no rebuild in the output" in out


def test_a_timeout_without_a_named_test_is_void(calc):
    s = spec(calc, [["M1 slow", "return a + b", "return a + b"]])
    code, out, _ = mutate(calc, s, "--test", f'"{sys.executable}" -c "import time; time.sleep(5)"',
                          "--timeout", "0.5")
    assert code == 1 and "VOID: timed out" in out


def test_a_custom_failure_pattern(calc):
    s = spec(calc, [["M1 add subtracts", "return a + b", "return a - b"]])
    check = f'"{sys.executable}" -c "import calc, sys; ok = calc.add(2, 3) == 5; print(\'BAD add\' if not ok else \'\'); sys.exit(0 if ok else 1)"'
    code, out, _ = mutate(calc, s, "--test", check)
    assert code == 1 and "VOID" in out
    code, out, _ = mutate(calc, s, "--test", check, "--failed-pattern", r"^BAD (\w+)")
    assert code == 0 and "| calc.py | M1 add subtracts | caught | add |" in out


def test_the_file_is_restored_when_a_run_raises(calc, monkeypatch, capsys):
    def boom(cmd, root, timeout):
        raise KeyboardInterrupt
    monkeypatch.setattr(mr, "run_tests", boom)
    targets = mr.load_spec(json.dumps([{"file": "calc.py", "mutations": [["M1", "return a + b", "return 0"]]}]), "s")
    with pytest.raises(KeyboardInterrupt):
        mr.round_(targets, calc.root, "true", None, None, mr.FAILED_PATTERNS)
    assert calc.read("calc.py") == CODE


def test_every_write_is_stamped_later(calc, monkeypatch):
    import time
    start = time.time()
    stamps = []
    monkeypatch.setattr(mr, "run_tests", lambda cmd, root, timeout: (stamps.append(
        (calc.root / "calc.py").stat().st_mtime) or 1, "FAILED tests/t.py::test_x"))
    targets = mr.load_spec(json.dumps([{"file": "calc.py", "mutations": [["M1", "a + b", "a - b"],
                                                                          ["M2", "a, b", "b, a"]]}]), "s")
    mr.round_(targets, calc.root, "true", None, None, mr.FAILED_PATTERNS, out=io.StringIO())
    # two mutations, then the control, which runs on the restored file: the restore is stamped later too
    assert len(stamps) == 3 and stamps[0] > start + 0.5                       # ahead of the clock
    assert stamps[1] - stamps[0] >= 2 and stamps[2] - stamps[1] >= 2          # each strictly later than the last
    assert (calc.root / "calc.py").stat().st_mtime == stamps[2]


def test_the_failure_patterns_name_each_runner():
    output = ("FAILED tests/test_a.py::test_one - AssertionError\nERROR tests/test_a.py::test_two - KeyError\n"
              "ERROR tests/test_b.py - SyntaxError\nFAIL: test_three (m.T.test_three)\n"
              "test parser::tests::empty ... FAILED\n    --- FAIL: TestFour (0.00s)\n")
    assert mr.failed_tests(output, mr.FAILED_PATTERNS) == [
        "tests/test_a.py::test_one", "tests/test_a.py::test_two", "test_three (m.T.test_three)",
        "parser::tests::empty", "TestFour"]


def test_bad_specs_and_arguments_exit_two(calc):
    bad = calc.root / "bad.json"
    for text in ("not json", '{"targets": 3}', '[{"file": "calc.py"}]', '[{"file": "calc.py", "mutations": [["M1"]]}]',
                 '[{"file": "calc.py", "mutations": [["M1", "", "x"]]}]'):
        bad.write_text(text)
        assert mutate(calc, bad, "--test", "true")[0] == 2, text
    assert mutate(calc, "nowhere.json", "--test", "true")[0] == 2
    assert mutate(calc, bad)[0] == 2                                              # no --test
    good = spec(calc, [["M1", "return a + b", "return a - b"]])
    assert mutate(calc, good, "--test", "true", "--failed-pattern", "(")[0] == 2


# --- anchors ---------------------------------------------------------------------------------------------------------

def test_anchors_counts_every_anchor_and_fails_on_a_live_one_off(calc):
    spec(calc, [["M1 once", "return a + b", "x"], ["M2 nowhere", "return a * b", "x"], ["M3 twice", "return", "x"]])
    code, out, _ = mutate(calc, "anchors", "specs")
    assert code == 1, out
    assert "1 spec(s), 3 anchor(s), 1 matching once" in out
    assert "M2 nowhere: the anchor occurs 0 time(s) in calc.py" in out and "M3 twice: the anchor occurs" in out


def test_anchors_lists_a_record_without_failing(calc):
    spec(calc, [["M1 nowhere", "return a * b", "x"]], ran_at="0123abc")
    code, out, _ = mutate(calc, "anchors", "specs/spec.json")
    assert code == 0 and "off in records" in out and "(ran_at 0123abc)" in out
    path = calc.root / "specs" / "target.json"
    path.write_text(json.dumps([{"file": "calc.py", "ran_at": "0123abc", "mutations": [["M2", "gone", "x"]]},
                                {"file": "missing.py", "mutations": [["M3", "x", "y"]]}]))
    code, out, _ = mutate(calc, "anchors", path)
    assert code == 1 and "M3: missing.py does not exist" in out and "M2" in out


def test_anchors_at_a_revision(calc):
    spec(calc, [["M1", "return a + b", "x"]])
    calc.commit("the spec")
    calc.write({"calc.py": CODE.replace("return a + b", "return b + a")})
    assert mutate(calc, "anchors", "specs")[0] == 1
    code, out, _ = mutate(calc, "anchors", "specs", "--rev", "HEAD")
    assert code == 0 and "anchors at HEAD" in out


def test_anchors_bad_arguments_exit_two(calc, tmp_path):
    assert mutate(calc, "anchors")[0] == 2
    outside = tmp_path / "elsewhere.json"
    outside.write_text("[]")
    assert mutate(calc, "anchors", outside)[0] == 2
    bad = calc.root / "bad.json"
    bad.write_text("{")
    assert mutate(calc, "anchors", bad)[0] == 2


def test_the_repositorys_own_mutation_specs_still_anchor(monkeypatch):
    """The specs committed under tests/mutations are live records of the rounds the tools were held to: an anchor that
    stops matching once the code moves is drift the next round would refuse, so the suite refuses it first."""
    repo = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo)
    assert mr.main(["anchors", "tools/tests/mutations"]) == 0
