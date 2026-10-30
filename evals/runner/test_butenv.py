"""Missing-but policy for tests which exercise real GitButler repositories."""
import os
import unittest
from unittest import mock

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "evals"))
from vcs import butenv  # noqa: E402


class TestButMissing(unittest.TestCase):
    def without_but(self, required=None):
        env = {"PATH": ""}
        if required is not None:
            env["SPECWRIGHT_REQUIRE_BUT"] = required
        return mock.patch.dict(os.environ, env, clear=True)

    def test_but_missing_skips_with_reason(self):
        with self.without_but():
            with self.assertRaises(unittest.SkipTest) as caught:
                butenv.require_but()
        self.assertEqual(str(caught.exception), "but not installed")

    def test_but_missing_required_fails(self):
        with self.without_but("1"):
            with self.assertRaises(AssertionError) as caught:
                butenv.require_but()
        self.assertIn("but", str(caught.exception).lower())
        self.assertIn("not installed", str(caught.exception).lower())


if __name__ == "__main__":
    unittest.main()
