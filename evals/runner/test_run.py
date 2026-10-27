"""Tests for evals/run.py, the parallel runner: one process per test file, bounded by the shared process module.

Every test builds throwaway suites in a temp dir and runs the runner on them with --root.

Run: python -m unittest discover evals/runner
"""
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent / "run.py"

PASSING = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n    def test_b(self):\n        pass\n"
FAILING = "import unittest\nclass T(unittest.TestCase):\n    def test_bad(self):\n        self.fail('boom-marker')\n"
CRASHING = "import no_such_module_anywhere\n"


def pid_alive(pid):
    if sys.platform == "win32":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return re.search(rf"\b{pid}\b", r.stdout) is not None
    import os
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:  # a killed process an unreaping PID 1 has not collected still answers kill(pid, 0)
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="runner-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.kept = []

    def suite(self, name, files):
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        for fname, body in files.items():
            (d / fname).write_text(body, encoding="utf-8")

    def run_runner(self, *args, timeout=120):
        r = subprocess.run([sys.executable, str(RUN), "--root", str(self.root), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        for m in re.finditer(r"^full output: (.+)$", r.stdout, re.M):
            self.addCleanup(shutil.rmtree, Path(m.group(1)).parent, True)
        return r

    def test_all_files_pass(self):
        self.suite("alpha", {"test_one.py": PASSING, "test_two.py": PASSING})
        self.suite("beta", {"test_three.py": PASSING})
        self.suite("fakes", {"gh.py": "raise SystemExit(9)\n"})  # not a suite: holds no test_*.py
        r = self.run_runner("alpha", "beta")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"(?m)^alpha: 2 files, 4 tests, \d+(\.\d+)?s$")
        self.assertRegex(r.stdout, r"(?m)^beta: 1 files, 2 tests, \d+(\.\d+)?s$")
        r = self.run_runner()  # no suite named: every suite, and `fakes` is not one
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("fakes", r.stdout)

    def test_a_failing_file_is_reported_and_kept(self):
        self.suite("alpha", {"test_good.py": PASSING, "test_bad.py": FAILING})
        r = self.run_runner("alpha")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("alpha/test_bad.py", r.stdout)
        self.assertRegex(r.stdout, r"exit code 1")
        self.assertIn("boom-marker", r.stdout)
        m = re.search(r"(?m)^full output: (.+)$", r.stdout)
        self.assertIsNotNone(m, r.stdout)
        kept = Path(m.group(1))
        self.assertTrue(kept.is_file(), "the failed file's full output is kept after the run")
        self.assertIn("boom-marker", kept.read_text(encoding="utf-8", errors="replace"))
        self.assertNotIn("test_good.py", r.stdout.split("alpha/test_bad.py", 1)[1])  # the passing file prints no failure
        self.assertRegex(r.stdout, r"(?m)^alpha: 2 files, 3 tests, ")  # the other file still ran

    def test_unknown_suite_exits_2(self):
        self.suite("alpha", {"test_one.py": PASSING})
        self.suite("beta", {"test_two.py": FAILING})
        r = self.run_runner("no-such-suite")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("no-such-suite", r.stderr)
        self.assertIn("alpha", r.stderr)
        self.assertIn("beta", r.stderr)
        self.assertNotIn("Ran ", r.stdout + r.stderr)
        r = self.run_runner("beta", "no-such-suite")  # a bad name among good ones runs nothing
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("boom-marker", r.stdout + r.stderr)

    def test_a_crashing_file_is_reported(self):
        self.suite("alpha", {"test_crash.py": CRASHING + PASSING, "test_ok.py": PASSING})
        r = self.run_runner("alpha")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("alpha/test_crash.py", r.stdout)
        self.assertRegex(r.stdout, r"exit code [1-9]")
        self.assertIn("no_such_module_anywhere", r.stdout)  # the traceback, from the file's stderr
        m = re.search(r"(?m)^full output: (.+)$", r.stdout)
        self.assertIsNotNone(m, r.stdout)
        self.assertTrue(Path(m.group(1)).is_file())

    def test_a_timed_out_file_tree_is_stopped(self):
        pids = self.root / "pids.txt"
        hang = (
            "import os, subprocess, sys, time, unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_hang(self):\n"
            "        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])\n"
            f"        open({str(pids)!r}, 'w').write('%d %d' % (os.getpid(), child.pid))\n"
            "        time.sleep(600)\n")
        self.suite("alpha", {"test_hang.py": hang, "test_ok.py": PASSING})
        r = self.run_runner("alpha", "--timeout", "4")
        found = [int(x) for x in pids.read_text().split()] if pids.exists() else []
        self.assertEqual(len(found), 2, "the test file never recorded its PIDs: " + r.stdout + r.stderr)
        deadline = time.time() + 10
        while any(pid_alive(p) for p in found) and time.time() < deadline:
            time.sleep(0.2)
        alive = [p for p in found if pid_alive(p)]
        for p in alive:  # never leave a sleeper behind, whatever the assertion says
            subprocess.run(["taskkill", "/F", "/PID", str(p)] if sys.platform == "win32" else ["kill", "-9", str(p)],
                           capture_output=True)
        self.assertEqual(alive, [], "the timed-out file's process tree survived the runner")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("alpha/test_hang.py", r.stdout)
        self.assertRegex(r.stdout, r"timeout after 4 s")
        m = re.search(r"(?m)^full output: (.+)$", r.stdout)
        self.assertIsNotNone(m, r.stdout)
        self.assertTrue(Path(m.group(1)).is_file())
        self.assertRegex(r.stdout, r"(?m)^alpha: 2 files, 2 tests, ")  # the other file still ran

    def test_ids_lists_every_test_id_without_running(self):
        self.suite("alpha", {"test_one.py": PASSING})
        self.suite("beta", {"test_one.py": PASSING.replace("test_a", "test_c")})  # same module name in two suites
        r = self.run_runner("--ids", "alpha", "beta")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(sorted(lines), ["alpha:test_one.T.test_a", "alpha:test_one.T.test_b",
                                         "beta:test_one.T.test_b", "beta:test_one.T.test_c"])


if __name__ == "__main__":
    unittest.main()
