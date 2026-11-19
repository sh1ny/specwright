"""`mise run install-sw` places a tree-built sw where the skills look for it (native-cli-vcs D5, native-cli-update D7).

The task runs `dart run cli/tool/build.dart --install`: it builds a sw to a temporary path inside cli/build/, checks it
and places it with `sw update sw-install --build`. No shell syntax or bash reaches the task. The tests run the task
against a temporary SPECWRIGHT_HOME, so they do not touch the real one. A mismatched version or interface, or a
workflow interface other than the one the tree's skills require, must leave every existing file as it was.

Run: python -m unittest evals/cli/test_install_sw.py   (needs mise on PATH, which pins dart)
"""
import json
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
ROOT = Path(HERE).resolve().parent.parent
EXE = "sw.exe" if os.name == "nt" else "sw"
BUILD_DIR = ROOT / "cli" / "build"


def snapshot(folder):
    """Every file under folder as {relative path: (bytes, mtime_ns)}."""
    return {p.relative_to(folder).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in sorted(folder.rglob("*")) if p.is_file()}


class TestInstallSw(unittest.TestCase):
    def setUp(self):
        self.mise = shutil.which("mise")
        if not self.mise:
            self.skipTest("no mise installed")
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="install-sw-")))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {**os.environ, "SPECWRIGHT_HOME": self.home.as_posix()}
        self.version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.bin = self.home / ".specwright" / "bin" / self.version

    def task(self, *args, env=None):
        return subprocess.run([self.mise, "run", "install-sw", *(["--", *args] if args else [])], cwd=ROOT,
                              env=env or self.env, capture_output=True, text=True, encoding="utf-8", timeout=900)

    def test_task_wiring(self):
        task = (ROOT / "mise.toml").read_text(encoding="utf-8").split("[tasks.install-sw]", 1)[1].split("[tasks.", 1)[0]
        self.assertIn('run = "dart run cli/tool/build.dart --install"', task)
        self.assertNotIn("bash", task)
        self.assertFalse((ROOT / "scripts" / "install-sw.sh").exists())

    def test_build_placed_and_resolved(self):
        done = self.task()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        placed = self.bin / EXE
        self.assertTrue(placed.is_file(), done.stdout + done.stderr)
        self.assertEqual((self.bin / "THIRD_PARTY_NOTICES.txt").read_bytes(),
                         (ROOT / "cli/THIRD_PARTY_NOTICES.txt").read_bytes())
        printed = done.stdout.strip().splitlines()[-1]
        self.assertEqual(os.path.normcase(os.path.realpath(printed)), os.path.normcase(os.path.realpath(placed)))
        # The placed binary serves a project at the tree's VERSION: `sw vcs state` runs from it, nothing else resolves it.
        code = self.tmp / "code"
        (code / "openspec" / ".specwright").mkdir(parents=True)
        (code / "openspec" / ".specwright" / "VERSION").write_text(self.version + "\n", encoding="utf-8")
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run([*git, "init", "-q", "-b", "main", code.as_posix()], check=True, env=self.env, timeout=60)
        subprocess.run([*git, "-C", code.as_posix(), "add", "-A"], check=True, env=self.env, timeout=60)
        subprocess.run([*git, "-C", code.as_posix(), "commit", "-q", "-m", "init"], check=True, env=self.env, timeout=60)
        shown = subprocess.run([str(placed), "version", "--json"], env=self.env, capture_output=True, text=True,
                               encoding="utf-8", timeout=60)
        self.assertEqual(shown.returncode, 0, shown.stdout + shown.stderr)
        self.assertEqual(json.loads(shown.stdout)["version"], self.version)
        state = subprocess.run([str(placed), "vcs", "state", "--repo", code.as_posix(), "--role", "code"], env=self.env,
                               capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(state.returncode, 0, state.stdout + state.stderr)
        self.assertTrue(json.loads(state.stdout)["ok"], state.stdout)

    def test_workflow_interface_differs_from_skill_pin(self):
        # The skills in the tree require interface 1; the build reports its own: nothing is placed, both are named.
        pin = self.tmp / "pin.md"
        pin.write_text("# pr skill\n\ninterface 1\n", encoding="utf-8")
        self.bin.mkdir(parents=True)
        (self.bin / EXE).write_text("existing\n", encoding="utf-8")
        before_home = snapshot(self.home)
        before_build = sorted(p.name for p in BUILD_DIR.iterdir()) if BUILD_DIR.is_dir() else []
        done = self.task("--interface-from", pin.as_posix())
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("interface 2", done.stderr)
        self.assertIn("require interface 1", done.stderr)
        self.assertIn("nothing was placed", done.stderr)
        self.assertEqual(snapshot(self.home), before_home)
        after_build = sorted(p.name for p in BUILD_DIR.iterdir()) if BUILD_DIR.is_dir() else []
        self.assertEqual(after_build, before_build)

    def test_skill_pin_without_interface_line_places_nothing(self):
        pin = self.tmp / "pin.md"
        pin.write_text("# pr skill\n", encoding="utf-8")
        done = self.task("--interface-from", pin.as_posix())
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("interface <n>", done.stderr)
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), [])

    def test_expected_interface_build_placed(self):
        # The build's own interface (3) is the expected one: the task places it as it does without the check.
        done = self.task("--expect-update-interface", "3")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue((self.bin / EXE).is_file(), done.stdout + done.stderr)
        self.assertEqual((self.bin / "THIRD_PARTY_NOTICES.txt").read_bytes(),
                         (ROOT / "cli/THIRD_PARTY_NOTICES.txt").read_bytes())
        self.assertEqual(sorted(p.name for p in self.bin.iterdir()), ["THIRD_PARTY_NOTICES.txt", EXE])

    def test_interface_mismatch_places_nothing(self):
        # A main install's project is the downloaded tree the task runs in: here ROOT. A pending journal there must
        # survive the probe, which runs from ROOT; a staged one is what a recovery would discard.
        state = ROOT / "openspec" / ".specwright"
        journal = state / "update.json"
        if journal.exists():
            self.skipTest("this checkout has an update in flight")
        self.bin.mkdir(parents=True)
        (self.bin / EXE).write_text("existing\n", encoding="utf-8")
        (self.bin / "THIRD_PARTY_NOTICES.txt").write_text("old notice\n", encoding="utf-8")
        state.mkdir(parents=True, exist_ok=True)
        journal.write_text('{"format": 2, "phase": "staged", "from": "0.36.0", "to": "0.37.0", "targets": [], '
                           '"groups": []}\n', encoding="utf-8")
        self.addCleanup(journal.unlink, True)
        before_home, before_state = snapshot(self.home), snapshot(state)
        before_build = sorted(p.name for p in BUILD_DIR.iterdir()) if BUILD_DIR.is_dir() else []
        done = self.task("--expect-update-interface", "2")
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("update interface 3", done.stderr)
        self.assertIn("expected 2", done.stderr)
        self.assertEqual(snapshot(self.home), before_home)
        self.assertEqual(snapshot(state), before_state, "the probe touched the project's journal or state")
        # the build is deleted: nothing is left behind in cli/build
        after_build = sorted(p.name for p in BUILD_DIR.iterdir()) if BUILD_DIR.is_dir() else []
        self.assertEqual(after_build, before_build)

    def test_mismatched_build_leaves_existing_file(self):
        # --version makes the build report another version than the tree's VERSION: the check fails, nothing changes.
        self.bin.mkdir(parents=True)
        (self.bin / EXE).write_text("existing\n", encoding="utf-8")
        before = snapshot(self.home)
        done = self.task("--version", "9.9.9")
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("did not pass the version check", done.stderr)
        self.assertIn("reports version 9.9.9, not " + self.version, done.stderr)
        self.assertEqual(snapshot(self.home), before)

    def test_install_sw_task_without_bash(self):
        if os.name != "nt":
            self.skipTest("platform: the no-bash scenario is a Windows one")
        keep = []
        for tool in ("mise", "dart"):
            found = shutil.which(tool)
            self.assertTrue(found, tool + " not found")
            keep.append(str(Path(found).parent))
        path = os.pathsep.join(dict.fromkeys(keep))
        self.assertIsNone(shutil.which("bash", path=path))
        env = {**self.env, "PATH": path}
        done = self.task(env=env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue((self.bin / EXE).is_file(), done.stdout + done.stderr)
        self.assertTrue((self.bin / "THIRD_PARTY_NOTICES.txt").is_file())

    def test_output_and_version_options_write_where_named(self):
        # The eval fixtures (D8) build a named version to a named file without installing.
        out = self.tmp / ("fixture-" + EXE)
        dart = shutil.which("dart")
        self.assertTrue(dart)
        done = subprocess.run([dart, "run", (ROOT / "cli/tool/build.dart").as_posix(), "--version", "8.7.6",
                               "--output", out.as_posix()], cwd=ROOT, env=self.env, capture_output=True, text=True,
                              encoding="utf-8", timeout=900)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(out.is_file())
        shown = subprocess.run([str(out), "version", "--json"], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertIn("8.7.6", shown.stdout + shown.stderr)
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
