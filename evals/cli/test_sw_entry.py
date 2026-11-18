"""The direct argument entry of sw (native-cli "Arguments sw cannot represent are refused", ADR 0040).

Task 1.1's entry probes, kept as regression checks. On Windows sw reads the raw command line, tells a lone surrogate
apart from a valid U+FFFD, and prints the bad_argument document with exit 2. On Linux and macOS the Dart runtime refuses
non-UTF-8 argv before main: non-zero exit and empty stdout, its exit code and text unpinned (C6).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swharness  # noqa: E402

WINDOWS = os.name == "nt"


def _run(args):
    """Run sw with args (str or bytes items); return (exit code, stdout text, stderr text)."""
    proc = subprocess.run([swharness.require_sw(), *args], capture_output=True, timeout=60)
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


class BadArgumentTests(unittest.TestCase):
    def assert_bad_argument(self, args, position):
        code, out, err = _run(args)
        self.assertEqual(code, 2, (out, err))
        document = json.loads(out)
        self.assertEqual(document["ok"], False)
        self.assertEqual(document["error"], "bad_argument")
        self.assertIn("argument %d " % position, document["message"])

    @unittest.skipIf(WINDOWS, "platform: POSIX argv bytes")
    def test_non_utf8_bytes_on_posix_are_refused_before_sw_runs(self):
        # The Dart runtime refuses non-UTF-8 argv before main (ADR 0040, C6): non-zero exit, empty stdout. Its exit
        # code and stderr text are the runtime's own and are not pinned. No file is made: the control call, the same
        # command with a UTF-8 path, shows that a run reaching the command prints a document on stdout.
        with tempfile.TemporaryDirectory() as tmp:
            base = os.fsencode(tmp)
            control = _run([b"release", b"notes", b"--proposal", os.path.join(base, b"m-x.md")])
            code, out, err = _run([b"release", b"notes", b"--proposal", os.path.join(base, b"m\xffx.md")])
        self.assertNotEqual(control[1], "", control)
        json.loads(control[1])
        self.assertNotEqual(code, 0, err)
        self.assertEqual(out, "", err)

    @unittest.skipUnless(WINDOWS, "platform: Windows UTF-16 command line")
    def test_lone_surrogate_on_windows_is_bad_argument(self):
        self.assert_bad_argument(["release", "notes", "--proposal", "m\udc80x.md"], 4)

    def test_valid_replacement_character_is_a_character(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "m�x.md")
            code, out, err = _run(["release", "notes", "--proposal", missing])
        document = json.loads(out)
        self.assertNotEqual(document.get("error"), "bad_argument", out)
        self.assertIn("m�x.md", document["message"])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
