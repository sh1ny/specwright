"""`mise run install-sw` places a tree-built sw where the resolver looks for it (native-cli-vcs D5, task 8.6).

The tests check task wiring and run its body against a temporary SPECWRIGHT_HOME,
using SPECWRIGHT_SW so they do not overwrite another worker's build. A mismatched version must preserve the old file.

Run: SPECWRIGHT_SW=<path> python -m unittest evals/cli/test_install_sw.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import swharness  # noqa: E402
import bashexe  # noqa: E402

ROOT = Path(HERE).resolve().parent.parent
RESOLVER = ROOT / "skills" / "specwright-pr" / "scripts" / "sw-path.sh"
INSTALL = ROOT / "scripts" / "install-sw.sh"
EXE = "sw.exe" if os.name == "nt" else "sw"
STOP = "sw missing or mismatched: rerun the install prompt"


class TestInstallSw(unittest.TestCase):
    def setUp(self):
        self.bash = bashexe.bash()
        if not self.bash:
            self.skipTest("no bash installed")
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="install-sw-")))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {**os.environ, "SPECWRIGHT_HOME": self.home.as_posix()}
        self.version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    def test_build_placed_and_resolved(self):
        # The task builds, then runs scripts/install-sw.sh. Rebuilding here would overwrite cli/build/sw while other
        # tests run it, so this checks the task's wiring and runs its body on the build CI already made.
        task = (ROOT / "mise.toml").read_text(encoding="utf-8").split("[tasks.install-sw]", 1)[1].split("[tasks.", 1)[0]
        self.assertIn('depends = ["build"]', task)
        self.assertIn('run = "bash scripts/install-sw.sh"', task)
        done = subprocess.run([self.bash, INSTALL.as_posix(), Path(swharness.require_sw()).as_posix(), self.version], cwd=ROOT, env=self.env,
                              capture_output=True, text=True, encoding="utf-8", timeout=600)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        placed = self.home / ".specwright" / "bin" / self.version / EXE
        self.assertTrue(placed.is_file(), done.stdout + done.stderr)
        code = self.tmp / "code"
        (code / "openspec" / ".specwright").mkdir(parents=True)
        (code / "openspec" / ".specwright" / "VERSION").write_text(self.version + "\n", encoding="utf-8")
        found = subprocess.run([self.bash, RESOLVER.as_posix(), "--code", code.as_posix()], env=self.env,
                               capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(found.returncode, 0, found.stdout + found.stderr)
        self.assertEqual(os.path.normcase(os.path.realpath(found.stdout.strip())), os.path.normcase(os.path.realpath(placed)))
        printed = done.stdout.strip().splitlines()[-1]
        self.assertEqual(os.path.normcase(os.path.realpath(printed)), os.path.normcase(os.path.realpath(placed)))

    def test_source_build_places_notice_beside_binary(self):
        built = swharness.require_sw()
        done = subprocess.run([self.bash, INSTALL.as_posix(), Path(built).as_posix(), self.version], env=self.env,
                              capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        notice = self.home / ".specwright/bin" / self.version / "THIRD_PARTY_NOTICES.txt"
        self.assertEqual(notice.read_bytes(), (ROOT / "cli/THIRD_PARTY_NOTICES.txt").read_bytes())
        before = notice.stat().st_mtime_ns
        done = subprocess.run([self.bash, INSTALL.as_posix(), Path(built).as_posix(), self.version], env=self.env,
                              capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(notice.stat().st_mtime_ns, before)
        self.assertEqual(sorted(p.name for p in notice.parent.iterdir()), ["THIRD_PARTY_NOTICES.txt", EXE])

    def test_mismatched_build_leaves_existing_file(self):
        built = swharness.require_sw()
        target = self.home / ".specwright" / "bin" / "9.9.9" / EXE
        target.parent.mkdir(parents=True)
        target.write_text("existing\n", encoding="utf-8")
        done = subprocess.run([self.bash, INSTALL.as_posix(), Path(built).as_posix(), "9.9.9"], env=self.env,
                              capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(STOP, done.stderr)
        self.assertIn("expected 9.9.9", done.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "existing\n")
        self.assertEqual(sorted(p.name for p in target.parent.iterdir()), [EXE])


if __name__ == "__main__":
    unittest.main()
