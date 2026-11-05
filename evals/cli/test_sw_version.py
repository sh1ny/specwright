import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swharness  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


class SwVersionTests(unittest.TestCase):
    def test_version_json_reports_version_and_interface(self):
        proc = swharness.run_sw("version", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertTrue(proc.stdout.endswith("\n"))
        report = json.loads(proc.stdout)
        self.assertEqual(report, {"version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(), "interface": 1})

    def test_unknown_command_or_flag_prints_usage_and_exits_2(self):
        for args in ([], ["frobnicate"], ["version", "--bogus"]):
            with self.subTest(args=args):
                proc = swharness.run_sw(*args)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")
                self.assertIn("usage: sw", proc.stderr)
                self.assertIn("version", proc.stderr)
                self.assertIn("run", proc.stderr)


if __name__ == "__main__":
    unittest.main()
