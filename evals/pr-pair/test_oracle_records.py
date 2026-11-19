"""The oracle record capture and its checker (native-cli-retire-scripts D14, task 6.5): machine paths are normalized, and the
checker names an incomplete set and a record that differs between OSes.

Run: python -m unittest evals/pr-pair/test_oracle_records.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "oracle"))
import check_records  # noqa: E402
import oracle_capture  # noqa: E402

CASE = "test_parity.PairParity.test_x"
RECORD = {"case": CASE, "exit": 0, "stdout": {"ok": True}}
BLOB = b'{"version": 2, "owner": {"id": "a"}}\n'


class Carrier:
    def __init__(self, tmp):
        self.tmp = tmp


class Normalizing(unittest.TestCase):
    def test_machine_paths_become_placeholders(self):
        with tempfile.TemporaryDirectory() as td:
            paths = oracle_capture.Paths(Carrier(Path(td)))
            posix = Path(td).resolve().as_posix()
            self.assertEqual(paths.text(f"{td}\\sub\\f.json and {posix}/g"), "<tmp>/sub/f.json and <tmp>/g")
            self.assertEqual(paths.node({"a": [f"{td}/x"]}), {"a": ["<tmp>/x"]})
            self.assertEqual(paths.text("mktemp tmp.AbC123xyz"), "mktemp tmp.X")
            self.assertEqual(paths.text(tempfile.gettempdir().replace(chr(92), "/") + "/tmpv6l3ll8i.json"), "<temp>/<name>")  # not "<temp><temp>"
            self.assertEqual(paths.text(f"{td}/.specwright/bin/0.37.0/sw.exe"), "<tmp>/.specwright/bin/0.37.0/sw")
            self.assertEqual(paths.text(repr(td + chr(92) + "state")), "'<tmp>/state'")  # a path inside a Python repr

    def test_stderr_prefix_and_comment_bodies(self):
        self.assertEqual(oracle_capture.fixed_prefix("line 7: boom"), "line 7:")
        self.assertEqual(oracle_capture.fixed_prefix("sw: bad"), "sw: ")
        state = {"repos": {"o/n": {"comments": {"7": [{"body": "hi"}]}, "pulls": [{"body": "not a comment"}]}}}
        self.assertEqual(oracle_capture.comment_bodies(state), {"/repos/o/n/comments/7/0": "hi"})


class Checking(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)

    def capture(self, name, record=RECORD, blob=BLOB, outcome="ok", case=CASE):
        directory = self.root / name
        (directory / case).mkdir(parents=True)
        (directory / case / "01-old.json").write_text(json.dumps(record), encoding="utf-8")
        if blob is not None:
            (directory / case / "01-old.record").write_bytes(blob)
        (directory / "outcomes.json").write_text(json.dumps({case: {"status": outcome, "reason": ""}}), encoding="utf-8")
        return str(directory)

    def test_three_agreeing_complete_sets_pass(self):
        problems, summary = check_records.check([self.capture(n) for n in ("Linux", "Windows", "macOS")])
        self.assertEqual(problems, [])
        self.assertIn("1 cases", summary)

    def test_a_difference_between_oses_is_named(self):
        sets = [self.capture("Linux"), self.capture("Windows", {**RECORD, "exit": 1}), self.capture("macOS")]
        problems, _ = check_records.check(sets)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("$.exit", problems[0])

    def test_a_missing_case_and_a_bad_feedback_record_are_named(self):
        sets = [self.capture("Linux"), self.capture("Windows", blob=b'{"version": 2, "owner": {}}\r\n'), self.root / "macOS"]
        (self.root / "macOS").mkdir()
        (self.root / "macOS" / "outcomes.json").write_text(json.dumps({CASE: {"status": "ok", "reason": ""}}), encoding="utf-8")
        (self.root / "macOS" / "other").mkdir()
        problems, _ = check_records.check([str(s) for s in sets])
        text = "\n".join(problems)
        self.assertIn("macOS: no records for " + CASE, text)
        self.assertIn("CR line ends", text)

    def test_a_listed_os_difference_passes_and_is_reported_and_an_unlisted_one_fails(self):
        case = "test_parity.AsParity.test_nested_fence_keeps_the_outer_originals"
        nested = lambda text: {**RECORD, "stdout": text}
        sets = [self.capture("Linux", nested("a|b| GH_HOST"), case=case), self.capture("macOS", nested("a|b| GH_HOST"), case=case),
                self.capture("Windows", nested("a|b| GH_HOST GCM_INTERACTIVE"), case=case)]
        problems, summary = check_records.check(sets)
        self.assertEqual(problems, [])
        self.assertIn("OS-dependent, allowed: " + case + " $.stdout", summary)
        sets[2] = self.capture("Other", nested("a|b| GH_HOST GCM_INTERACTIVE and more"), case=case)
        self.assertEqual(len(check_records.check(sets)[0]), 1)

    def test_a_failed_test_is_a_problem(self):
        problems, _ = check_records.check([self.capture("Linux", outcome="failed"), self.capture("Windows"), self.capture("macOS")])
        self.assertEqual(problems, [f"Linux: {CASE} failed"])


if __name__ == "__main__":
    unittest.main()
