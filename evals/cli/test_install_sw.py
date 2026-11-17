"""`mise run install-sw` places a tree-built sw where the resolver looks for it (native-cli-vcs D5, native-cli-update D7).

The task runs `dart run cli/tool/build.dart --install`: it builds a sw to a temporary path inside cli/build/, checks it
and places it with `sw update sw-install --build`. No shell syntax or bash reaches the task. The tests run the task
against a temporary SPECWRIGHT_HOME, so they do not touch the real one. A mismatched version or interface must leave
every existing file as it was.

Run: python -m unittest evals/cli/test_install_sw.py   (needs mise on PATH, which pins dart)
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
import bashexe  # noqa: E402

ROOT = Path(HERE).resolve().parent.parent
RESOLVER = ROOT / "skills" / "specwright-pr" / "scripts" / "sw-path.sh"
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
        bash = bashexe.bash()
        if bash:
            code = self.tmp / "code"
            (code / "openspec" / ".specwright").mkdir(parents=True)
            (code / "openspec" / ".specwright" / "VERSION").write_text(self.version + "\n", encoding="utf-8")
            found = subprocess.run([bash, RESOLVER.as_posix(), "--code", code.as_posix()], env=self.env,
                                   capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(found.returncode, 0, found.stdout + found.stderr)
            self.assertEqual(os.path.normcase(os.path.realpath(found.stdout.strip())),
                             os.path.normcase(os.path.realpath(placed)))

    def test_expected_interface_build_placed(self):
        # The build's own interface (3) is the expected one: the task places it as it does without the check.
        done = self.task("--expect-update-interface", "3")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue((self.bin / EXE).is_file(), done.stdout + done.stderr)
        self.assertEqual((self.bin / "THIRD_PARTY_NOTICES.txt").read_bytes(),
                         (ROOT / "cli/THIRD_PARTY_NOTICES.txt").read_bytes())
        self.assertEqual(sorted(p.name for p in self.bin.iterdir()), ["THIRD_PARTY_NOTICES.txt", EXE])

    def test_interface_mismatch_places_nothing(self):
        self.bin.mkdir(parents=True)
        (self.bin / EXE).write_text("existing\n", encoding="utf-8")
        (self.bin / "THIRD_PARTY_NOTICES.txt").write_text("old notice\n", encoding="utf-8")
        project = self.tmp / "project"
        (project / "openspec" / ".specwright").mkdir(parents=True)
        (project / "openspec" / ".specwright" / "update-journal.json").write_text('{"state":"pending"}\n', encoding="utf-8")
        (project / "openspec" / ".specwright" / "VERSION").write_text("0.1.0\n", encoding="utf-8")
        before_home, before_project = snapshot(self.home), snapshot(project)
        before_build = sorted(p.name for p in BUILD_DIR.iterdir()) if BUILD_DIR.is_dir() else []
        done = self.task("--expect-update-interface", "2")
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("update interface 3", done.stderr)
        self.assertIn("expected 2", done.stderr)
        self.assertEqual(snapshot(self.home), before_home)
        self.assertEqual(snapshot(project), before_project)
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
