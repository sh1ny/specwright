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
import swcall  # noqa: E402
import swharness  # noqa: E402


class TestDocuments(unittest.TestCase):
    def test_document_is_compact_with_one_lf(self):
        with tempfile.TemporaryDirectory(prefix="sw-doc-") as repo:
            subprocess.run(["git", "init", "-q", repo], check=True, capture_output=True, timeout=60)
            swcall.stamp(repo)
            done = swcall.run(["vcs", "probe", "--repo", repo, "--role", "code"], project=repo, env=swharness.fixture_env(),
                              timeout=60, text=False)
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
