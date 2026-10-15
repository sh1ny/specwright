"""Script tests for skills/specwright-release/scripts/release.sh.

Every test runs the real script against a real git repo built by fixtures.py. One JSON
document on stdout per call; exit 0 = done, 1 = stop (the JSON has "error" and "message"),
2 = usage, 3 = a git or gh network call failed.

Run: python -m unittest discover evals/release
"""
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = Path(os.environ.get("RELEASE_SH") or ROOT / "skills" / "specwright-release" / "scripts" / "release.sh")

_spec = importlib.util.spec_from_file_location("release_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

VERSION_FILES = ["VERSION", "README.md", "skills/specwright-pr/SKILL.md", "skills/specwright-debug/SKILL.md"]


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, self.tmp)

    def repo(self, **kw):
        self.work = fx.make_repo(self.tmp, **kw)
        return self.work

    def release(self, *args, cwd=None):
        """Run release.sh; returns (exit code, parsed JSON, raw stdout)."""
        r = subprocess.run(["bash", str(SCRIPT), *args], cwd=cwd or self.work, capture_output=True, text=True,
                           encoding="utf-8")
        try:
            doc = json.loads(r.stdout)
        except ValueError:
            doc = None
        return r.returncode, doc, r.stdout + r.stderr

    def assertStops(self, out, *needles):
        code, doc, raw = out
        self.assertEqual(code, 1, raw)
        self.assertIs(doc["ok"], False, raw)
        self.assertIn("error", doc)
        for n in needles:
            self.assertIn(n, doc["message"], raw)


class TestOptIn(Base):
    def test_enabled_runs(self):
        # Publish is built in a later group; until then enabled=true means check, status and bump get
        # past the opt-in gate (group 4 extends this to publish).
        self.repo()
        code, doc, raw = self.release("check")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")
        fx.squash_merge(self.work, "add-x", "0.5.0", 7)
        self.assertEqual(self.release("status", "--version", "0.5.0")[0], 0)
        self.assertEqual(self.release("bump", "--to", "0.6.0")[0], 0)

    def test_missing_block_refuses(self):
        self.repo(with_release_block=False)
        before = fx.snapshot(self.work)
        for args in (("bump", "--to", "0.5.0"), ("publish", "--version", "0.4.2"), ("check",)):
            self.assertStops(self.release(*args), "release.enabled")
        self.assertEqual(fx.snapshot(self.work), before)
        self.assertEqual(fx.git(self.work, "tag"), "")

    def test_disabled_refuses(self):
        self.repo(enabled=False)
        before = fx.snapshot(self.work)
        self.assertStops(self.release("bump", "--to", "0.5.0"), "release.enabled")
        self.assertEqual(fx.snapshot(self.work), before)

    def test_rebase_method_refused(self):
        self.repo(merge_method="rebase")
        before = fx.snapshot(self.work)
        for args in (("bump", "--to", "0.5.0"), ("publish", "--version", "0.4.2")):
            self.assertStops(self.release(*args), "release.enabled", "pr.merge_method")
        self.assertEqual(fx.snapshot(self.work), before)
        self.assertEqual(fx.git(self.work, "tag"), "")

    def test_usage_errors_exit_2(self):
        self.repo()
        self.assertEqual(self.release("nonsense")[0], 2)
        self.assertEqual(self.release("bump")[0], 2)


class TestCheck(Base):
    def test_all_agree(self):
        self.repo()
        code, doc, raw = self.release("check")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")
        self.assertEqual(sorted(doc["files"]), sorted(VERSION_FILES))

    def test_one_disagrees(self):
        self.repo()
        fx.write(self.work, "skills/specwright-debug/SKILL.md", fx.skill_text("specwright-debug", "0.4.1"))
        before = fx.snapshot(self.work)
        out = self.release("check")
        self.assertStops(out, "skills/specwright-debug/SKILL.md", "0.4.1", "0.4.2")
        self.assertEqual(fx.snapshot(self.work), before)

    def test_zero_or_two_matches(self):
        self.repo()
        fx.write(self.work, "README.md", "# Demo\n\nno badge here\n")
        self.assertStops(self.release("check"), "README.md", fx.DEFAULT_VERSION_FILES["README.md"], "0")
        fx.write(self.work, "README.md", fx.readme_text("0.4.2") + fx.readme_text("0.4.2"))
        self.assertStops(self.release("check"), "README.md", fx.DEFAULT_VERSION_FILES["README.md"], "2")

    def test_status_reads_release_commit(self):
        # 0.4.1 was released when fewer SKILL.md files existed; HEAD is at 0.5.0 with one more.
        self.repo(version="0.4.0", skills=("specwright-pr",))
        fx.squash_merge(self.work, "add-a", "0.4.1", 11)
        fx.squash_merge(self.work, "add-b", "0.5.0", 12, extra_files={
            "skills/specwright-new/SKILL.md": fx.skill_text("specwright-new", "0.5.0")})
        code, doc, raw = self.release("status", "--version", "0.4.1")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.1")
        self.assertEqual(sorted(doc["files"]), ["README.md", "VERSION", "skills/specwright-pr/SKILL.md"])
        self.assertEqual(doc["release_commit"], fx.git(self.work, "rev-parse", "HEAD~1"))
        code, doc, raw = self.release("status", "--version", "0.5.0")
        self.assertEqual(code, 0, raw)
        self.assertEqual(len(doc["files"]), 4)
        # a version that no commit carries
        self.assertStops(self.release("status", "--version", "0.9.9"), "0.9.9")

    def test_status_stops_when_release_commit_disagrees(self):
        self.repo(version="0.4.0")
        fx.set_version(self.work, "0.4.1", skills=("specwright-pr",))  # specwright-debug stays 0.4.0
        fx.commit(self.work, "feat: half bump (#3)")
        self.assertStops(self.release("status", "--version", "0.4.1"), "skills/specwright-debug/SKILL.md", "0.4.0", "0.4.1")

    def test_empty_glob(self):
        self.repo(version_files={"VERSION": r"^(\d+\.\d+\.\d+)$", "pkg/*/VERSION": r"^(\d+\.\d+\.\d+)$"})
        self.assertStops(self.release("check"), "pkg/*/VERSION")


class TestBump(Base):
    def read(self, rel):
        return (self.work / rel).read_bytes()

    def test_minor_bump_rewrites_only_versions(self):
        self.repo()
        # CRLF in one file must survive: only the captured version changes
        fx.write(self.work, "README.md", fx.readme_text("0.4.2").replace("\n", "\r\n"))
        fx.git(self.work, "add", "-A")
        fx.git(self.work, "commit", "-q", "-m", "crlf")
        before = fx.snapshot(self.work)
        code, doc, raw = self.release("bump", "--to", "0.5.0")
        self.assertEqual(code, 0, raw)
        self.assertEqual((doc["from"], doc["to"]), ("0.4.2", "0.5.0"))
        after = fx.snapshot(self.work)
        self.assertEqual(sorted(after), sorted(before))  # no stray temp files
        for rel in VERSION_FILES:
            self.assertEqual(after[rel], before[rel].replace(b"0.4.2", b"0.5.0"), rel)
        self.assertEqual(after["README.md"], fx.readme_text("0.5.0").replace("\n", "\r\n").encode())
        self.assertEqual({k for k in after if after[k] != before[k]}, set(VERSION_FILES))
        self.assertEqual(self.release("check")[1]["version"], "0.5.0")
        self.assertEqual(len(fx.git(self.work, "log", "--oneline").splitlines()), 2)  # bump never commits

    def test_target_not_greater(self):
        self.repo()
        before = fx.snapshot(self.work)
        for target in ("0.4.2", "0.4.1"):
            self.assertStops(self.release("bump", "--to", target), "0.4.2", target)
        self.assertEqual(fx.snapshot(self.work), before)

    def test_interrupted_bump_completes(self):
        self.repo()
        fx.write(self.work, "VERSION", "0.5.0\n")  # the first rename happened, the rest did not
        out = self.release("bump", "--to", "0.6.0")
        self.assertStops(out, "0.5.0", "0.4.2", "VERSION")
        self.assertEqual(self.read("VERSION"), b"0.5.0\n")
        self.assertEqual(self.read("README.md"), fx.readme_text("0.4.2").encode())
        code, doc, raw = self.release("bump", "--to", "0.5.0")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["changed"], ["README.md", "skills/specwright-debug/SKILL.md", "skills/specwright-pr/SKILL.md"])
        self.assertEqual(self.release("check")[1]["version"], "0.5.0")
        self.assertEqual(self.read("VERSION"), b"0.5.0\n")

    def test_interrupted_bump_to_lower_target_refused(self):
        self.repo()
        fx.write(self.work, "VERSION", "0.4.9\n")  # split {0.4.9, 0.4.2}: the lower one is no completion target
        before = fx.snapshot(self.work)
        self.assertStops(self.release("bump", "--to", "0.4.2"), "0.4.9", "0.4.2")
        self.assertEqual(fx.snapshot(self.work), before)

    def test_malformed_target(self):
        self.repo()
        before = fx.snapshot(self.work)
        for target in ("v0.5", "0.5.0-beta", "0.5", "0.5.0.1", " 0.5.0"):
            self.assertStops(self.release("bump", "--to", target), "MAJOR.MINOR.PATCH")
        self.assertEqual(fx.snapshot(self.work), before)

    def test_bump_refuses_when_a_file_does_not_match(self):
        self.repo()
        fx.write(self.work, "README.md", "# Demo\n")
        before = fx.snapshot(self.work)
        self.assertStops(self.release("bump", "--to", "0.5.0"), "README.md")
        self.assertEqual(fx.snapshot(self.work), before)


if __name__ == "__main__":
    unittest.main()
