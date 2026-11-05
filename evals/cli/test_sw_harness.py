import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

# A tiny inner suite with one test that needs sw, run in a subprocess so the skip or failure is observed as the
# runner reports it.
INNER = """
import sys, unittest
sys.path.insert(0, %r)
import swharness

class Inner(unittest.TestCase):
    def test_needs_sw(self):
        swharness.run_sw("version", "--json")

unittest.main(argv=["inner", "-v"], verbosity=2)
""" % HERE


def run_inner(**env_overrides):
    env = dict(os.environ)
    env.pop("SPECWRIGHT_SW", None)
    env.pop("SPECWRIGHT_REQUIRE_SW", None)
    env.update(env_overrides)
    return subprocess.run([sys.executable, "-c", INNER], env=env, capture_output=True, text=True, timeout=60)


class HarnessPolicyTests(unittest.TestCase):
    def test_skips_with_sw_not_built(self):
        proc = run_inner()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("skipped 'sw not built'", proc.stderr)
        self.assertIn("OK (skipped=1)", proc.stderr)

    def test_require_sw_fails_naming_the_binary(self):
        proc = run_inner(SPECWRIGHT_REQUIRE_SW="1")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("FAIL", proc.stderr)
        self.assertIn("SPECWRIGHT_SW unset", proc.stderr)
        missing = os.path.join("no", "such", "sw")
        proc = run_inner(SPECWRIGHT_REQUIRE_SW="1", SPECWRIGHT_SW=missing)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("FAIL", proc.stderr)
        self.assertIn(missing, proc.stderr)


if __name__ == "__main__":
    unittest.main()
