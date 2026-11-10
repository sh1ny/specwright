"""The shared sentinels (evals/vcs/sentinels.py) record when run directly, so a log that stays absent means nothing ran.

Run: python -m unittest evals/vcs/test_sentinels.py
"""
import tempfile
import unittest
from pathlib import Path

import sentinels


class TestSentinels(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="swv-sentinels-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.sent = sentinels.install(root / "scripts", root / "bin", root / "ran.log")

    def test_each_sentinel_records_when_run_directly(self):
        self.sent.probe(self)
        self.assertEqual(self.sent.recorded(), [], "the probe clears the log")

    def test_the_four_scripts_and_both_interpreters_exist(self):
        self.assertEqual(sorted(p.name for p in self.sent.scripts.iterdir()),
                         sorted(["as.sh", "pr-pair.sh", "sw-path.sh", "vcs.sh"]))
        self.assertEqual(sorted(p.name for p in self.sent.bin.iterdir()), ["python", "python3"])


if __name__ == "__main__":
    unittest.main()
