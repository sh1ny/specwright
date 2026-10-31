"""Tests for evals/run.py, the parallel runner: one process per test file, bounded by the shared process module.

Every test builds throwaway suites in a temp dir and runs the runner on them with --root.

Run: python -m unittest discover evals/runner
"""
import _thread
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent / "run.py"

PASSING = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n    def test_b(self):\n        pass\n"
SKIPPING = ("import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n"
            "    @unittest.skip('one')\n    def test_s1(self):\n        pass\n"
            "    def test_s2(self):\n        self.skipTest('two')\n")
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


def hang_file(pids, seconds):
    """A test file that starts a sleeping child, records both PIDs in `pids`, and sleeps `seconds`."""
    return ("import os, subprocess, sys, time, unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_hang(self):\n"
            f"        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep({seconds})'])\n"
            f"        open({str(pids)!r}, 'w').write('%d %d' % (os.getpid(), child.pid))\n"
            f"        time.sleep({seconds})\n")


def load_runner():
    spec = importlib.util.spec_from_file_location("evals_run_under_test", str(RUN))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def wait_dead(pids, within=10):
    """The PIDs still alive after `within` seconds; kills those so no sleeper outlives the test."""
    deadline = time.time() + within
    while any(pid_alive(p) for p in pids) and time.time() < deadline:
        time.sleep(0.2)
    alive = [p for p in pids if pid_alive(p)]
    for p in alive:
        subprocess.run(["taskkill", "/F", "/PID", str(p)] if sys.platform == "win32" else ["kill", "-9", str(p)],
                       capture_output=True)
    return alive


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
        self.assertRegex(r.stdout, r"(?m)^alpha: 2 files, 4 tests, 0 skipped, \d+(\.\d+)?s$")
        self.assertRegex(r.stdout, r"(?m)^beta: 1 files, 2 tests, 0 skipped, \d+(\.\d+)?s$")
        r = self.run_runner()  # no suite named: every suite, and `fakes` is not one
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("fakes", r.stdout)

    def test_skips_are_counted_per_suite(self):
        self.suite("alpha", {"test_one.py": SKIPPING})
        self.suite("beta", {"test_two.py": PASSING})
        r = self.run_runner("alpha", "beta")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"(?m)^alpha: 1 files, 3 tests, 2 skipped, \d+(\.\d+)?s$")
        self.assertRegex(r.stdout, r"(?m)^beta: 1 files, 2 tests, 0 skipped, \d+(\.\d+)?s$")

    def test_list_suites_prints_every_suite_as_json(self):
        self.suite("beta", {"test_two.py": PASSING})
        self.suite("alpha", {"test_one.py": FAILING})  # --list-suites runs no test
        self.suite("fakes", {"gh.py": "raise SystemExit(9)\n"})
        r = self.run_runner("--list-suites")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout), ["alpha", "beta"])
        self.assertNotIn("Ran ", r.stdout + r.stderr)
        self.suite("gamma", {"test_three.py": PASSING})  # a new directory with a test file shows up
        self.assertEqual(json.loads(self.run_runner("--list-suites").stdout), ["alpha", "beta", "gamma"])
        for extra in (["alpha"], ["--ids"]):  # a usage error: nothing is listed
            r = self.run_runner("--list-suites", *extra)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertEqual(r.stdout, "")

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

    def interrupt_once(self, pids):
        """Interrupt the main thread, as Ctrl-C does, once `pids` exists; gives up after 60 s."""
        def fire():
            deadline = time.time() + 60
            while not pids.exists() and time.time() < deadline:
                time.sleep(0.1)
            time.sleep(0.5)
            _thread.interrupt_main()
        threading.Thread(target=fire, daemon=True).start()

    def run_in_process(self, mod, *args):
        """mod.main with --root; returns (whether KeyboardInterrupt came out, seconds taken)."""
        start = time.monotonic()
        try:
            mod.main(["--root", str(self.root), *args])
        except KeyboardInterrupt:
            return True, time.monotonic() - start
        return False, time.monotonic() - start

    def test_an_interrupt_stops_running_files_and_starts_no_queued_one(self):
        pids, marker = self.root / "pids.txt", self.root / "queued-started.txt"
        queued = ("import unittest\nclass T(unittest.TestCase):\n    def test_q(self):\n"
                  f"        open({str(marker)!r}, 'w').write('x')\n")
        self.suite("alpha", {"test_a_hang.py": hang_file(pids, 40), "test_b_queued.py": queued})
        self.interrupt_once(pids)
        interrupted, took = self.run_in_process(load_runner(), "--jobs", "1", "alpha")
        found = [int(x) for x in pids.read_text().split()] if pids.exists() else []
        alive = wait_dead(found)
        self.assertTrue(interrupted, "the interrupt did not reach the caller")
        self.assertEqual(len(found), 2, "the hanging file never recorded its PIDs")
        self.assertLess(took, 25, "the runner waited for the running file to end before stopping it")
        self.assertEqual(alive, [], "a running file's tree outlived the interrupt")
        time.sleep(1)
        self.assertFalse(marker.exists(), "a queued file started after the interrupt")

    def test_an_interrupt_in_the_serial_phase_stops_the_file(self):
        pids = self.root / "pids.txt"
        self.suite("alpha", {"test_hang.py": hang_file(pids, 40)})
        mod = load_runner()
        mod.SERIAL = {"alpha/test_hang.py"}
        self.interrupt_once(pids)
        interrupted, took = self.run_in_process(mod, "alpha")
        found = [int(x) for x in pids.read_text().split()] if pids.exists() else []
        alive = wait_dead(found)
        self.assertTrue(interrupted, "the interrupt did not reach the caller")
        self.assertEqual(len(found), 2, "the hanging file never recorded its PIDs")
        self.assertLess(took, 25, "the runner waited for the serial file to end before stopping it")
        self.assertEqual(alive, [], "the serial file's tree outlived the interrupt")

    def test_a_leftover_of_a_passing_file_is_stopped(self):
        pids = self.root / "pids.txt"
        leftover = ("import subprocess, sys, unittest\nclass T(unittest.TestCase):\n    def test_leave(self):\n"
                    "        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
                    f"        open({str(pids)!r}, 'w').write(str(child.pid))\n")
        self.suite("alpha", {"test_leave.py": leftover})
        r = self.run_runner("alpha")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        found = [int(x) for x in pids.read_text().split()] if pids.exists() else []
        self.assertEqual(len(found), 1, "the file never recorded its child's PID")
        self.assertEqual(wait_dead(found), [], "a process the passing file left behind outlived it")

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
