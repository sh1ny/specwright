"""Offline checks of tiers.py: the stress marks in evals.json and the base/cheap grade comparison.

Run: python -m unittest discover evals/git-workflow -p "test_tiers.py"
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import tiers  # noqa: E402

EVALS = HERE / "evals.json"
KINDS = ("watch", "light-apply", "implementer")


def real():
    return json.loads(EVALS.read_text(encoding="utf-8"))


class TestStressMarks(unittest.TestCase):
    def test_every_kind_marked(self):
        doc = real()
        self.assertEqual(tiers.check_marks(doc), [])
        marks = {e.get("stress") for e in doc["evals"]}
        for kind in KINDS:
            self.assertIn(kind, marks)

    def test_missing_kind_named(self):
        doc = real()
        for e in doc["evals"]:
            if e.get("stress") == "implementer":
                del e["stress"]
        problems = tiers.check_marks(doc)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("no stress eval covers implementer", problems[0])

    def test_unknown_kind_named(self):
        doc = real()
        victim = next(e for e in doc["evals"] if e.get("stress") == "watch")
        victim["stress"] = True
        problems = tiers.check_marks(doc)
        self.assertTrue(any(victim["name"] in p and "True" in p for p in problems), problems)


class TestCompare(unittest.TestCase):
    EVAL = "eval-watch-agent-merge"
    A1, A2 = "Exactly one merge request was sent", "PR #7 is MERGED in the fake gh"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.it = Path(tmp.name) / "iteration-1"
        self.it.mkdir()
        self.evals = Path(tmp.name) / "evals.json"
        self.evals.write_text(json.dumps({"skill_name": "x", "evals": [
            {"id": 55, "name": self.EVAL, "stress": "watch"},
            {"id": 9, "name": "eval-unmarked"},
        ]}), encoding="utf-8")

    def grade(self, name, config, passes, run="run-1", raw=None):
        d = self.it / name / config / run
        d.mkdir(parents=True)
        exp = [{"text": t, "passed": p, "evidence": ""} for t, p in passes.items()]
        n = sum(passes.values())
        doc = {"expectations": exp, "summary": {"passed": n, "failed": len(exp) - n, "total": len(exp),
                                                "pass_rate": round(n / len(exp), 2)}}
        (d / "grading.json").write_text(raw if raw is not None else json.dumps(doc), encoding="utf-8")

    def tiers(self):
        r = subprocess.run([sys.executable, str(HERE / "tiers.py"), str(self.it), "--base", "base", "--cheap", "cheap",
                            "--evals", str(self.evals)], capture_output=True, text=True, encoding="utf-8")
        return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else None), r.stderr

    def test_same_grades_exit_0(self):
        both = {self.A1: True, self.A2: True}
        self.grade(self.EVAL, "base", both)
        self.grade(self.EVAL, "cheap", both)
        code, out, err = self.tiers()
        self.assertEqual(code, 0, err)
        self.assertEqual((out["differences"], out["missing"]), ([], []))
        self.assertEqual(out["evals"][self.EVAL], {"base": 1.0, "cheap": 1.0})

    def test_difference_named_with_assertion(self):
        self.grade(self.EVAL, "base", {self.A1: True, self.A2: True})
        self.grade(self.EVAL, "cheap", {self.A1: False, self.A2: True})
        code, out, _ = self.tiers()
        self.assertEqual(code, 1)
        (d,) = out["differences"]
        self.assertEqual((d["eval"], d["base"], d["cheap"]), (self.EVAL, 1.0, 0.5))
        self.assertEqual((d["pass_only_base"], d["pass_only_cheap"]), ([self.A1], []))
        self.assertEqual(out["missing"], [])

    def test_missing_or_unreadable_is_missing(self):
        both = {self.A1: True, self.A2: True}
        self.grade(self.EVAL, "base", both)
        self.grade(self.EVAL, "cheap", both, raw="{not json")
        code, out, _ = self.tiers()
        self.assertEqual(code, 1)
        self.assertEqual(out["missing"], [{"eval": self.EVAL, "config": "cheap"}])
        self.assertEqual(out["differences"], [])

    def test_no_run_at_all_is_missing(self):
        self.grade(self.EVAL, "base", {self.A1: True})
        code, out, _ = self.tiers()
        self.assertEqual((code, out["missing"]), (1, [{"eval": self.EVAL, "config": "cheap"}]))

    def test_a_grading_without_a_summary_is_missing(self):
        self.grade(self.EVAL, "base", {self.A1: True})
        self.grade(self.EVAL, "cheap", {self.A1: True}, raw=json.dumps({"expectations": []}))
        code, out, _ = self.tiers()
        self.assertEqual((code, out["missing"]), (1, [{"eval": self.EVAL, "config": "cheap"}]))

    def test_unmarked_evals_are_skipped(self):
        both = {self.A1: True}
        self.grade(self.EVAL, "base", both)
        self.grade(self.EVAL, "cheap", both)
        self.grade("eval-unmarked", "base", {self.A1: True})
        self.grade("eval-unmarked", "cheap", {self.A1: False})
        code, out, _ = self.tiers()
        self.assertEqual(code, 0)
        self.assertNotIn("eval-unmarked", out["evals"])

    def test_usage_error_exits_2(self):
        r = subprocess.run([sys.executable, str(HERE / "tiers.py"), str(self.it)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
