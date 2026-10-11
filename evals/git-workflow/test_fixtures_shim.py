"""The git shim fixtures.py writes for the store evals runs under /bin/bash, which is bash 3.2 on macOS.

Bash 4 case expansions (${x,,}, ${x^^}) are a syntax error there, so every store push in the evals that use the shim
would fail. The shim matches the store checkout case-insensitively (Windows paths), so the match is also run here.

Run: python -m unittest discover evals/git-workflow -p "test_fixtures_shim.py"
"""
import re
import shutil
import subprocess
import unittest

import fixtures


class ShimPortability(unittest.TestCase):
    def test_no_bash4_case_expansion(self):
        self.assertIsNone(re.search(r"\$\{[^}]*(,,?|\^\^?)\}", fixtures.SHIM), "bash 4 case expansion in the shim")

    @unittest.skipUnless(shutil.which("bash"), "needs bash")
    def test_store_match_ignores_case(self):
        lc = re.search(r"^\s*(lc\(\) \{.*\})", fixtures.SHIM, re.M).group(1)
        script = lc + '\n[ "$(lc "$1")" = "$(lc "$2")" ] && echo same || echo different\n'
        run = lambda a, b: subprocess.run(["bash", "-c", script, "shim", a, b], capture_output=True, text=True).stdout.strip()
        self.assertEqual(run("F:/Dev/Store", "f:/dev/store"), "same")
        self.assertEqual(run("F:/Dev/Store", "F:/Dev/Other"), "different")


if __name__ == "__main__":
    unittest.main()
