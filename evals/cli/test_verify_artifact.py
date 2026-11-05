"""cli/tool/verify_artifact.py: checks a built sw against its SHA-256 file and the VERSION file (stdlib only)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "cli" / "tool" / "verify_artifact.py"


class VerifyArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.marker = self.dir / "ran"
        self.version_file = self.dir / "VERSION"
        self.version_file.write_text("1.2.3\n", encoding="utf-8", newline="\n")

    def make_binary(self, reported):
        """A stand-in sw that records that it ran and prints `version --json` for `reported`."""
        body = (
            "import json, os, sys\n"
            "open(os.environ['VA_MARKER'], 'w').write('ran')\n"
            "print(json.dumps({'version': %r, 'interface': 1}))\n" % reported
        )
        script = self.dir / "fake_sw.py"
        script.write_text(body, encoding="utf-8", newline="\n")
        if os.name == "nt":
            binary = self.dir / "sw.cmd"
            binary.write_text('@"%s" "%s" %%*\r\n' % (sys.executable, script), encoding="utf-8", newline="")
        else:
            binary = self.dir / "sw"
            binary.write_text("#!/bin/sh\nexec '%s' '%s' \"$@\"\n" % (sys.executable, script), encoding="utf-8",
                              newline="\n")
            binary.chmod(0o755)
        return binary

    def write_sha(self, binary, digest=None):
        digest = digest or hashlib.sha256(binary.read_bytes()).hexdigest()
        sha = self.dir / "sw.sha256"
        sha.write_text("%s  %s\n" % (digest, binary.name), encoding="utf-8", newline="\n")
        return sha

    def verify(self, binary, sha, *extra):
        env = {**os.environ, "VA_MARKER": str(self.marker)}
        return subprocess.run([sys.executable, "-I", str(TOOL), "--binary", str(binary), "--sha256", str(sha),
                               "--version-file", str(self.version_file), *extra],
                              capture_output=True, text=True, env=env, timeout=60)

    def test_matching_checksum_and_version_pass(self):
        binary = self.make_binary("1.2.3")
        result = self.verify(binary, self.write_sha(binary))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.marker.exists(), "the binary ran for its version")

    def test_checksum_mismatch_fails_without_running(self):
        binary = self.make_binary("1.2.3")
        result = self.verify(binary, self.write_sha(binary, "0" * 64))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sha256", (result.stdout + result.stderr).lower())
        self.assertFalse(self.marker.exists(), "a binary that fails its checksum must not be run")

    def test_version_drift_fails_naming_both(self):
        binary = self.make_binary("9.9.9")
        result = self.verify(binary, self.write_sha(binary))
        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("9.9.9", output)
        self.assertIn("1.2.3", output)

    def test_checksum_only_checks_without_running(self):
        binary = self.make_binary("9.9.9")
        result = self.verify(binary, self.write_sha(binary), "--checksum-only")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.marker.exists())


if __name__ == "__main__":
    unittest.main()
