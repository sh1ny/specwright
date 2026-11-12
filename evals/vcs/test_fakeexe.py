"""The `.exe` launchers of evals/fakeexe.py hand a fake its arguments unchanged (native-cli-launcher D9).

Git Bash (MSYS) rewrites glob characters in the arguments it is started with: it halves backslashes before `[` and drops
braces. A fake `gh` that gets a jq program with `\\[bot\\]` would then see `\\[bot\\]` halved. The bash launcher therefore passes
arguments in the environment; these cases pin that, directly and through `sw run --bounded`.

Run: python -m unittest evals/vcs/test_fakeexe.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bashexe  # noqa: E402
import fakeexe  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cli"))
import swharness  # noqa: E402

BS = "\\"
VALUES = [
    'def norm: sub("' + BS * 2 + "[bot" + BS * 2 + ']$"; "");',  # the jq text a gh fake receives
    "a" + BS * 2 + "[b",
    "plain" + BS + "[",
    "x" + BS * 3 + "[y" + BS * 2,
    "say " + BS + '"hi' + BS * 2 + '"',
    "tail" + BS * 2,
    "two words" + BS * 2,
    "HEAD^{commit}",
    "--format=%H",
    "!x!",
    "",
]
PRINTER = '#!/bin/sh\nfor a in "$@"; do printf "[%s]\\n" "$a"; done\n'
RECORDER = "import json, sys\nsys.stdout.write(json.dumps(sys.argv[1:]))\n"


@unittest.skipUnless(bashexe.bash(), "needs bash")
class TestFakeExe(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="swfx-")
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def bash_fake(self):
        fakeexe.write_fake(self.dir / "printer", PRINTER, exe=True)
        return str(self.dir / ("printer.exe" if os.name == "nt" else "printer"))

    def python_fake(self):
        fakeexe.write_python_fake(self.dir / "recorder", RECORDER)
        return str(self.dir / ("recorder.exe" if os.name == "nt" else "recorder"))

    def lines(self, values):
        return "".join("[%s]\n" % value for value in values)

    def test_bash_launcher_passes_arguments_unchanged(self):
        done = subprocess.run([self.bash_fake(), *VALUES], capture_output=True)
        self.assertEqual(done.stdout.decode("utf-8").replace("\r\n", "\n"), self.lines(VALUES), done.stderr)

    def test_python_launcher_passes_arguments_unchanged(self):
        done = subprocess.run([self.python_fake(), *VALUES], capture_output=True)
        self.assertEqual(json.loads(done.stdout), VALUES, done.stderr)

    def test_bash_launcher_arguments_survive_sw(self):
        sw = swharness.require_sw()
        values = [v for v in VALUES if v]
        done = subprocess.run([sw, "run", "--bounded", "--", self.bash_fake(), *values], capture_output=True)
        self.assertEqual(done.stdout.decode("utf-8").replace("\r\n", "\n"), self.lines(values), done.stderr)


if __name__ == "__main__":
    unittest.main()
