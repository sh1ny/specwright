"""Black-box test of the shape of a `sw` document: compact JSON that ends in one line feed on every platform.

Needs the binary named by SPECWRIGHT_SW (skips as `sw not built` otherwise). The bytes are read as bytes: text mode would
turn a CR LF into an LF and hide the Windows line end this test exists to refuse.

Run: SPECWRIGHT_SW=<path> python -m unittest evals/cli/test_documents.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import bashexe  # noqa: E402
import swharness  # noqa: E402

SCRIPTS = os.path.join(HERE, "..", "..", "skills", "specwright-pr", "scripts")


class TestDocuments(unittest.TestCase):
    def test_document_is_compact_with_one_lf(self):
        sw = swharness.require_sw()
        with tempfile.TemporaryDirectory(prefix="sw-doc-") as repo:
            subprocess.run(["git", "init", "-q", repo], check=True, capture_output=True, timeout=60)
            # the shim's records: its directory, its bash, then the command line, each ended by a NUL
            records = [SCRIPTS, bashexe.bash(), "probe", "--repo", repo, "--role", "code"]
            done = subprocess.run([sw, "vcs", "--args-stdin"], env=swharness.fixture_env(), capture_output=True, timeout=60,
                                  input="".join(r + chr(0) for r in records).encode("utf-8"))
        self.assertEqual(done.returncode, 0, done.stderr)
        out = done.stdout
        self.assertTrue(out.endswith(b"}\n"))
        self.assertNotIn(b"\r", out)
        self.assertEqual(out.count(b"\n"), 1)
        # compact: no space after a separator outside the strings of this document
        self.assertNotIn(b'": ', out)
        self.assertNotIn(b", ", out)
        # consumers parse documents, they never match their text
        self.assertIs(json.loads(out)["ok"], True)


if __name__ == "__main__":
    unittest.main()
