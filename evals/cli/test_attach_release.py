"""cli/tool/attach_release.py: attaches the five checked binaries and SHA256SUMS to a release, driven with a fake gh."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "cli" / "tool" / "attach_release.py"
FAKE = ROOT / "evals" / "fakes" / "gh_release.py"
NAMES = ["sw-linux-arm64", "sw-linux-x64", "sw-macos-arm64", "sw-macos-x64", "sw-windows-x64.exe"]
TAG = "v0.24.0"


def sha(data):
    return hashlib.sha256(data).hexdigest()


class AttachReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.releases = base / "releases"
        self.releases.mkdir()
        self.log = base / "log.jsonl"
        self.dist = base / "dist"
        self.dist.mkdir()
        self.version_file = base / "VERSION"
        self.version_file.write_text("0.24.0\n", encoding="utf-8", newline="\n")
        bin_dir = base / "bin"
        bin_dir.mkdir()
        py = Path(sys.executable).resolve().as_posix()
        if os.name == "nt":
            (bin_dir / "gh.cmd").write_text('@"%s" "%s" %%*\r\n' % (py, FAKE), encoding="utf-8", newline="")
        else:
            shim = bin_dir / "gh"
            shim.write_text("#!/bin/sh\nexec '%s' '%s' \"$@\"\n" % (py, FAKE.as_posix()), encoding="utf-8", newline="\n")
            shim.chmod(0o755)
        self.env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                    "FAKE_REL_DIR": str(self.releases), "FAKE_REL_LOG": str(self.log)}
        self.env.pop("FAKE_REL_CORRUPT", None)
        self.contents = {}
        for name in NAMES:
            data = ("binary " + name).encode()
            self.contents[name] = data
            (self.dist / name).write_bytes(data)
            (self.dist / (name + ".sha256")).write_text("%s  %s\n" % (sha(data), name), encoding="utf-8", newline="\n")

    def release(self, tag=TAG, assets=None):
        folder = self.releases / tag
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in (assets or {}).items():
            (folder / name).write_bytes(data)
        return folder

    def run_tool(self, tag=TAG, **env):
        return subprocess.run([sys.executable, "-I", str(TOOL), "--tag", tag, "--version-file", str(self.version_file),
                               "--dist", str(self.dist), "--repo", "o/n"],
                              capture_output=True, text=True, env={**self.env, **env}, timeout=120)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line)["argv"] for line in self.log.read_text(encoding="utf-8").splitlines()]

    def uploads(self):
        return [call for call in self.calls() if call[:2] == ["release", "upload"]]

    def new_release(self):
        self.version_file.write_text("0.30.0\n", encoding="utf-8")
        name = "THIRD_PARTY_NOTICES.txt"
        data = b"Third-party notices\n"
        (self.dist / name).write_bytes(data)
        (self.dist / (name + ".sha256")).write_text("%s  %s\n" % (sha(data), name), encoding="utf-8")
        return self.release(tag="v0.30.0")

    def test_new_release_notice_is_verified_before_seal(self):
        folder = self.new_release()
        result = self.run_tool(tag="v0.30.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        notice = "THIRD_PARTY_NOTICES.txt"
        self.assertEqual((folder / notice).read_bytes(), (self.dist / notice).read_bytes())
        lines = (folder / "SHA256SUMS").read_text().splitlines()
        self.assertEqual(len(lines), 6)
        self.assertEqual([line.split("  ")[1] for line in lines], sorted(NAMES + [notice]))
        calls = self.calls()
        readback = next(i for i, c in enumerate(calls) if c[:2] == ["release", "download"] and notice in c)
        seal = next(i for i, c in enumerate(calls) if c[:2] == ["release", "upload"] and any(Path(a).name == "SHA256SUMS" for a in c))
        self.assertLess(readback, seal)

    def test_sealed_new_release_missing_notice_is_unchanged(self):
        folder = self.new_release()
        for name in NAMES + ["SHA256SUMS"]:
            (folder / name).write_bytes(b"published")
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        result = self.run_tool(tag="v0.30.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("THIRD_PARTY_NOTICES.txt", result.stderr)
        self.assertEqual(self.uploads(), [])
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)

    def test_notice_readback_mismatch_writes_no_seal(self):
        folder = self.new_release()
        result = self.run_tool(tag="v0.30.0", FAKE_REL_CORRUPT="THIRD_PARTY_NOTICES.txt")
        self.assertNotEqual(result.returncode, 0)
        data = (self.dist / "THIRD_PARTY_NOTICES.txt").read_bytes()
        for mention in ("THIRD_PARTY_NOTICES.txt", sha(data), sha(data + b"tampered")):
            self.assertIn(mention, result.stderr)
        self.assertFalse((folder / "SHA256SUMS").exists())

    def test_unsealed_release_gets_five_binaries_then_sums(self):
        folder = self.release()
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted(NAMES + ["SHA256SUMS"]))
        for name in NAMES:
            self.assertEqual(sha((folder / name).read_bytes()), sha(self.contents[name]), name)
        uploads = self.uploads()
        self.assertTrue(any(Path(arg).name == "SHA256SUMS" for arg in uploads[-1]), uploads)
        for call in uploads[:-1]:
            self.assertFalse(any(Path(arg).name == "SHA256SUMS" for arg in call), uploads)

    def test_partial_unsealed_release_is_replaced_then_sealed(self):
        folder = self.release(assets={"sw-linux-x64": b"older", "sw-macos-x64": b"older"})
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--clobber", self.uploads()[0])
        self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted(NAMES + ["SHA256SUMS"]))
        self.assertEqual((folder / "sw-linux-x64").read_bytes(), self.contents["sw-linux-x64"])
        self.assertEqual((folder / "sw-macos-x64").read_bytes(), self.contents["sw-macos-x64"])
        self.assertTrue(any(Path(arg).name == "SHA256SUMS" for arg in self.uploads()[-1]))

    def test_sealed_complete_release_changes_nothing(self):
        assets = {name: b"published" for name in NAMES}
        assets["SHA256SUMS"] = b"sums"
        folder = self.release(assets=assets)
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("complete", result.stdout)
        self.assertEqual(self.uploads(), [])
        self.assertEqual((folder / "sw-linux-x64").read_bytes(), b"published")

    def test_sealed_release_missing_binary_fails(self):
        assets = {name: b"published" for name in NAMES if name != "sw-macos-x64"}
        assets["SHA256SUMS"] = b"sums"
        self.release(assets=assets)
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sw-macos-x64", result.stderr)
        self.assertEqual(self.uploads(), [])

    def test_tag_without_release_fails(self):
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.uploads(), [])

    def test_readback_mismatch_writes_no_seal(self):
        folder = self.release()
        result = self.run_tool(FAKE_REL_CORRUPT="sw-linux-arm64")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sw-linux-arm64", result.stderr)
        self.assertIn(sha(self.contents["sw-linux-arm64"]), result.stderr)
        self.assertIn(sha(self.contents["sw-linux-arm64"] + b"tampered"), result.stderr)
        self.assertFalse((folder / "SHA256SUMS").exists())
        self.assertFalse(any(Path(arg).name == "SHA256SUMS" for call in self.uploads() for arg in call))

    def test_tag_version_mismatch_attaches_nothing(self):
        folder = self.release()
        self.version_file.write_text("0.23.0\n", encoding="utf-8", newline="\n")
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("0.24.0", result.stderr)
        self.assertIn("0.23.0", result.stderr)
        self.assertEqual(self.uploads(), [])
        self.assertEqual(list(folder.iterdir()), [])

    def test_sums_has_five_sorted_lines_matching_binaries(self):
        folder = self.release()
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = (folder / "SHA256SUMS").read_bytes().decode("utf-8")
        self.assertNotIn("\r", text)
        self.assertTrue(text.endswith("\n"))
        lines = text.splitlines()
        self.assertEqual(len(lines), 5)
        for line in lines:
            self.assertRegex(line, r"^[0-9a-f]{64}  \S+$")
        names = [line.split("  ")[1] for line in lines]
        self.assertEqual(names, sorted(names))
        self.assertEqual(names, NAMES)
        for line in lines:
            digest, name = line.split("  ")
            self.assertEqual(digest, sha((folder / name).read_bytes()))


if __name__ == "__main__":
    unittest.main()
