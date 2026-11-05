import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swharness  # noqa: E402


class HarnessPolicyTests(unittest.TestCase):
    def test_unset_skips_as_sw_not_built(self):
        with mock.patch.dict(os.environ, clear=False) as env:
            env.pop("SPECWRIGHT_SW", None)
            env.pop("SPECWRIGHT_REQUIRE_SW", None)
            with self.assertRaises(unittest.SkipTest) as cm:
                swharness.require_sw()
        self.assertEqual(str(cm.exception), "sw not built")

    def test_required_and_missing_fails_naming_the_binary(self):
        with mock.patch.dict(os.environ, {"SPECWRIGHT_REQUIRE_SW": "1", "SPECWRIGHT_SW": "no/such/sw"}):
            with self.assertRaises(AssertionError) as cm:
                swharness.require_sw()
        self.assertIn("no/such/sw", str(cm.exception))
        with mock.patch.dict(os.environ, {"SPECWRIGHT_REQUIRE_SW": "1"}) as env:
            env.pop("SPECWRIGHT_SW", None)
            with self.assertRaises(AssertionError) as cm:
                swharness.require_sw()
        self.assertIn("SPECWRIGHT_SW unset", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
