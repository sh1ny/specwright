"""Missing-jj policy for tests which exercise real colocated repositories."""
import os
import unittest
from unittest import mock

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "evals"))
from vcs import jjenv  # noqa: E402


class TestJjMissing(unittest.TestCase):
    def without_jj(self, required=None):
        env = {"PATH": ""}
        if required is not None:
            env["SPECWRIGHT_REQUIRE_JJ"] = required
        else:
            env.pop("SPECWRIGHT_REQUIRE_JJ", None)
        return mock.patch.dict(os.environ, env, clear=True)

    def test_jj_missing_skips_with_reason(self):
        with self.without_jj():
            with self.assertRaises(unittest.SkipTest) as caught:
                jjenv.require_jj()
        self.assertEqual(str(caught.exception), "jj not installed")

    def test_jj_missing_required_fails(self):
        with self.without_jj("1"):
            with self.assertRaises(AssertionError) as caught:
                jjenv.require_jj()
        self.assertIn("jj", str(caught.exception).lower())
        self.assertIn("not installed", str(caught.exception).lower())


if __name__ == "__main__":
    unittest.main()
