"""Tests for evals/timings.md: the before/after wall times of the six eval suites (design D8 of fix-eval-gaps).

The record is a markdown table, one row per suite plus a Total row:
  | Suite | Before (s) | Before tests | After (s) | After tests |
Every suite whose after time is not lower than its before time is named on a line starting `Not faster:`, and the
record states `Every base test ID is present.`

Run: python -m unittest discover evals/runner
"""
import re
import unittest
from pathlib import Path

RECORD = Path(__file__).resolve().parent.parent / "timings.md"
SUITES = ["pr-pair", "update", "review-routes", "git-workflow", "release", "finish"]
ROW = re.compile(r"^\|\s*([\w-]+)\s*\|\s*([\d.]+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*(\d+)\s*\|\s*$", re.M)


def read_record():
    text = RECORD.read_text(encoding="utf-8")
    rows = {m.group(1): (float(m.group(2)), int(m.group(3)), float(m.group(4)), int(m.group(5)))
            for m in ROW.finditer(text)}
    return text, rows


class TimingsRecord(unittest.TestCase):
    def test_every_suite_has_before_and_after_and_the_total_is_lower(self):
        _, rows = read_record()
        for suite in SUITES:
            self.assertIn(suite, rows, "no row for %s" % suite)
            before, before_tests, after, after_tests = rows[suite]
            self.assertGreater(before, 0, suite)
            self.assertGreater(after, 0, suite)
            self.assertGreater(before_tests, 0, suite)
            self.assertGreater(after_tests, 0, suite)
        before_total = sum(rows[s][0] for s in SUITES)
        after_total = sum(rows[s][2] for s in SUITES)
        self.assertLess(after_total, before_total)
        self.assertIn("Total", rows, "no Total row")
        self.assertAlmostEqual(rows["Total"][0], before_total, delta=1)
        self.assertAlmostEqual(rows["Total"][2], after_total, delta=1)
        self.assertNotIn("runner", rows, "the runner suite has no before figure and stays out of the totals")

    def test_a_suite_not_faster_is_named_in_a_note(self):
        text, rows = read_record()
        named = set()
        for line in re.findall(r"^Not faster:(.*)$", text, re.M):
            named.update(re.findall(r"[\w-]+", line))
        for suite in SUITES:
            if suite in rows and rows[suite][2] >= rows[suite][0]:
                self.assertIn(suite, named, "%s is not faster but no `Not faster:` note names it" % suite)

    def test_record_states_every_base_id_is_present(self):
        text, _ = read_record()
        self.assertIn("Every base test ID is present.", text)
        self.assertNotRegex(text, r"(?im)^missing test id")


if __name__ == "__main__":
    unittest.main()
