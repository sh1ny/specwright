"""Black-box tests for how `sw run --bounded` stops a command's whole process tree and holds the command until it is contained.

Needs the binary named by SPECWRIGHT_SW (skips as `sw not built` otherwise). The held-startup, helper-death and pre-hello
cases drive the test-only hooks of the helper: SPECWRIGHT_TEST_HOLD_START (prehello|before|after:<file>, which also writes
<file>.pid and <file>.exit), SPECWRIGHT_TEST_PRE_GO (<file>.reached marks that the parent consumed the ready frame and defers the
go while <file> exists), SPECWRIGHT_TEST_HELPER_EXIT=after-hello|after-ready, SPECWRIGHT_TEST_NO_JOB=1 and SPECWRIGHT_TEST_SPAWN_DIR.
Fixtures are small Python scripts run with sys.executable.

Run: SPECWRIGHT_SW=<path> python -m unittest evals/cli/test_sw_tree.py
"""
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import swharness  # noqa: E402
import test_sw_run as base  # noqa: E402  (the module, not its test classes: unittest must not collect them twice)

WINDOWS = os.name == "nt"

# The command: starts a child and waits for it; the child starts a grandchild, records its PID and exits. Only then does the
# command write `ready` and hang, so the grandchild is an orphan (its parent is gone) when the limit hits.
ORPHAN_COMMAND = (
    "import os, subprocess, sys, time\n"
    "d = sys.argv[1]\n"
    "open(d + '/cmd.pid', 'w').write(str(os.getpid()))\n"
    "subprocess.Popen([sys.executable, d + '/child.py', d]).wait()\n"
    "open(d + '/ready', 'w').write('1')\n"
    "time.sleep(3600)\n")
ORPHAN_CHILD = (
    "import os, subprocess, sys\n"
    "d = sys.argv[1]\n"
    "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(3600)'])\n"
    "open(d + '/grandchild.pid', 'w').write(str(g.pid))\n"
    "open(d + '/child.pid', 'w').write(str(os.getpid()))\n")
# The command keeps its child alive: a by-PID stop (taskkill /T) can reach the whole tree.
LIVE_TREE_COMMAND = (
    "import os, subprocess, sys, time\n"
    "d = sys.argv[1]\n"
    "open(d + '/cmd.pid', 'w').write(str(os.getpid()))\n"
    "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(3600)'])\n"
    "open(d + '/child.pid', 'w').write(str(c.pid))\n"
    "time.sleep(3600)\n")
QUICK = "print('ok')\n"
# Runs sw inside a job object it created itself, as a caller that wraps sw in a job does (Windows only).
IN_OUTER_JOB = (
    "import ctypes, subprocess, sys\n"
    "k = ctypes.WinDLL('kernel32', use_last_error=True)\n"
    "k.CreateJobObjectW.restype = ctypes.c_void_p\n"
    "k.GetCurrentProcess.restype = ctypes.c_void_p\n"
    "k.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]\n"
    "job = k.CreateJobObjectW(None, None)\n"
    "if not job or not k.AssignProcessToJobObject(job, k.GetCurrentProcess()):\n"
    "    sys.exit(90)\n"
    "sys.exit(subprocess.run(sys.argv[1:]).returncode)\n")


class TreeBase(base.Base):
    def setUp(self):
        super().setUp()
        self.mark = self.script("mark.py", base.MARK)
        self.marker = self.tmp / "started"

    def command_label(self, *cmd):
        return " ".join(cmd[:2])

    def limit_line(self, limit, *cmd):
        return "bounded: %s: %s\n" % (limit, self.command_label(*cmd))

    def recorded(self, *names):
        return [self.recorded_pid(self.tmp / n) for n in names]

    def assert_all_gone(self, pids, seconds=10):
        alive = [p for p in pids if not base.wait_gone(p, seconds)]
        self.assertEqual(alive, [], "processes of the command's tree survived the limit")

    def no_start_after_release(self, *holds):
        for hold in holds:
            hold.unlink(missing_ok=True)
        time.sleep(1.5)  # a helper that was not stopped would have started the command by now
        self.assertFalse(self.marker.exists(), "the command started after the hold was released")


class OrphanedTree(TreeBase):
    def setUp(self):
        super().setUp()
        self.script("child.py", ORPHAN_CHILD)
        self.command = self.script("orphan.py", ORPHAN_COMMAND)

    def assert_orphans_stopped(self, proc):
        self.assertTrue((self.tmp / "ready").exists(), "the fixture was not ready before the limit hit: " + proc.stderr)
        self.assertEqual(proc.returncode, 124, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.endswith(self.limit_line("deadline_exceeded", sys.executable, self.command, str(self.tmp))),
                        proc.stderr)
        self.assert_all_gone(self.recorded("cmd.pid", "child.pid", "grandchild.pid"))

    def test_orphaned_grandchild_is_stopped(self):
        proc = self.sw("--", sys.executable, self.command, str(self.tmp), env=self.env(SPECWRIGHT_NET_DEADLINE=6))
        self.assert_orphans_stopped(proc)

    @unittest.skipUnless(WINDOWS, "platform: job objects are Windows only")
    def test_nested_job_holds_the_tree(self):
        wrapper = self.script("outer_job.py", IN_OUTER_JOB)
        proc = subprocess.run(
            [sys.executable, wrapper, swharness.require_sw(), "run", "--bounded", "--", sys.executable, self.command,
             str(self.tmp)], env=self.env(SPECWRIGHT_NET_DEADLINE=6), capture_output=True, text=True, timeout=60)
        self.assertNotEqual(proc.returncode, 90, "the wrapper could not put itself into a job: " + proc.stderr)
        self.assert_orphans_stopped(proc)


@unittest.skipUnless(WINDOWS, "platform: SPECWRIGHT_TEST_NO_JOB is a Windows hook")
class NoJob(TreeBase):
    def test_no_job_announces_and_stops_by_pid(self):
        command = self.script("live.py", LIVE_TREE_COMMAND)
        proc = self.sw("--", sys.executable, command, str(self.tmp),
                       env=self.env(SPECWRIGHT_TEST_NO_JOB=1, SPECWRIGHT_NET_DEADLINE=3))
        self.assertEqual(proc.returncode, 124, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr,
                         "bounded: no job object: SPECWRIGHT_TEST_NO_JOB is set\n"
                         + self.limit_line("deadline_exceeded", sys.executable, command))
        self.assert_all_gone(self.recorded("cmd.pid", "child.pid"))


class HeldStartup(TreeBase):
    def variants(self):
        return [("job", {}), ("no job", {"SPECWRIGHT_TEST_NO_JOB": 1})] if WINDOWS else [("session", {})]

    def check_limited(self, name, extra, hold_point):
        hold = self.tmp / ("hold-%s-%s" % (hold_point, name.replace(" ", "-")))
        hold.write_text("")
        holds = [hold]
        env = dict(extra, SPECWRIGHT_TEST_HOLD_START="%s:%s" % (hold_point, hold), SPECWRIGHT_NET_DEADLINE=2)
        pre = None
        if hold_point == "after":
            pre = self.tmp / ("pre-go-" + name.replace(" ", "-"))
            pre.write_text("")
            holds.append(pre)
            env["SPECWRIGHT_TEST_PRE_GO"] = str(pre)
        proc = self.sw("--", sys.executable, self.mark, str(self.marker), env=self.env(**env))
        self.assertEqual(proc.returncode, 124, proc.stderr)
        self.assertEqual(proc.stdout, "")
        announced = "bounded: no job object: SPECWRIGHT_TEST_NO_JOB is set\n" if hold_point == "after" and extra else ""
        self.assertEqual(proc.stderr, announced + self.limit_line("deadline_exceeded", sys.executable, self.mark))
        if pre is not None:
            self.assertTrue(Path(str(pre) + ".reached").exists(), "the parent never consumed the ready frame")
        helper = self.recorded_pid(Path(str(hold) + ".pid"))
        self.assertTrue(base.wait_gone(helper, 10), "the held helper survived the limit")
        self.no_start_after_release(*holds)

    def test_held_startup_before_containment(self):
        for name, extra in self.variants():
            with self.subTest(variant=name):
                self.check_limited(name, extra, "before")

    def test_held_startup_after_ready_before_go(self):
        for name, extra in self.variants():
            with self.subTest(variant=name):
                self.check_limited(name, extra, "after")

    def test_prehello_limit_leaves_helper_that_never_starts(self):
        hold = self.tmp / "hold-prehello"
        hold.write_text("")
        proc = self.sw("--", sys.executable, self.mark, str(self.marker),
                       env=self.env(SPECWRIGHT_TEST_HOLD_START="prehello:%s" % hold, SPECWRIGHT_NET_DEADLINE=1))
        self.assertEqual(proc.returncode, 124, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "bounded: helper not stopped: %s\n" % self.command_label(sys.executable, self.mark)
                         + self.limit_line("deadline_exceeded", sys.executable, self.mark))
        self.assertGreaterEqual(proc.elapsed, 5, "sw did not wait the stop wait for the helper to announce itself")
        helper = self.recorded_pid(Path(str(hold) + ".pid"))
        self.assertTrue(base.pid_alive(helper), "the helper was stopped though it had not announced itself")
        self.assertFalse(self.marker.exists())
        hold.unlink()  # this test owns the cleanup: the helper runs on and must exit without starting the command
        exit_file = Path(str(hold) + ".exit")
        end = time.time() + 5
        while not exit_file.exists() and time.time() < end:
            time.sleep(0.1)
        self.assertTrue(exit_file.exists(), "the released helper did not end within the stop wait")
        self.assertEqual(exit_file.read_text().strip(), "125")
        self.assertTrue(base.wait_gone(helper, 5))
        self.no_start_after_release()


class HelperDeath(TreeBase):
    def test_helper_exit_after_ready_is_a_start_failure(self):
        # The pre-go hook keeps the parent between the ready frame and the go until the helper is gone, so the order is fixed.
        pre = self.tmp / "pre-go"
        pre.write_text("")
        env = self.env(SPECWRIGHT_TEST_HELPER_EXIT="after-ready", SPECWRIGHT_TEST_PRE_GO=str(pre), SPECWRIGHT_NET_DEADLINE=30)
        proc = subprocess.Popen([swharness.require_sw(), "run", "--bounded", "--", sys.executable, self.mark, str(self.marker)],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(proc.kill)
        reached = Path(str(pre) + ".reached")
        end = time.time() + 30
        while not reached.exists() and time.time() < end:
            time.sleep(0.1)
        self.assertTrue(reached.exists(), "the parent never consumed the ready frame")
        time.sleep(1.5)  # the helper exits right after its ready frame
        pre.unlink()
        out, err = proc.communicate(timeout=30)
        self.assertEqual(proc.returncode, 127, err)
        self.assertEqual(out, "")
        self.assertEqual(err, "bounded: helper exited during startup: %s\n" % self.command_label(sys.executable, self.mark))
        self.no_start_after_release()

    def test_helper_exit_between_hello_and_ready_is_a_start_failure(self):
        # The helper announces itself, waits a second (so the parent identifies it), then exits before its ready frame.
        env = self.env(SPECWRIGHT_TEST_HELPER_EXIT="after-hello", SPECWRIGHT_NET_DEADLINE=30)
        proc = swharness.run_sw("run", "--bounded", "--", sys.executable, self.mark, str(self.marker), env=env, timeout=60)
        self.assertEqual(proc.returncode, 127, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr,
                         "bounded: helper exited during startup: %s\n" % self.command_label(sys.executable, self.mark))
        self.no_start_after_release()


class SpawnRecord(TreeBase):
    def setUp(self):
        super().setUp()
        self.quick = self.script("quick.py", QUICK)

    def listing(self):
        return sorted(str(p.relative_to(self.tmp)) for p in self.tmp.rglob("*"))

    def run_quick(self, **extra):
        scratch = self.tmp / "scratch"
        scratch.mkdir(exist_ok=True)
        env = self.env(TMP=scratch, TEMP=scratch, TMPDIR=scratch, **extra)
        if swharness.SPAWN_DIR not in extra:
            env.pop(swharness.SPAWN_DIR, None)  # these cases own the record; the runner's must not leak in
        return swharness.run_sw("run", "--bounded", "--", sys.executable, self.quick, env=env, cwd=scratch, timeout=60)

    def test_no_spawn_record_without_variable(self):
        before = self.listing()
        proc = self.run_quick()
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "ok\n", ""))
        self.assertEqual(self.listing(), sorted(before + ["scratch"]), "a file was created")

    def test_unwritable_spawn_dir_leaves_result_unchanged(self):
        plain = self.run_quick()
        not_a_dir = self.tmp / "a-file"
        not_a_dir.write_text("")
        for name, target in (("missing", self.tmp / "nope" / "deeper"), ("a file", not_a_dir)):
            with self.subTest(target=name):
                proc = self.run_quick(SPECWRIGHT_TEST_SPAWN_DIR=target)
                self.assertEqual((proc.returncode, proc.stdout, proc.stderr),
                                 (plain.returncode, plain.stdout, plain.stderr))
        self.assertFalse((self.tmp / "nope").exists(), "sw created the spawn directory")

    @unittest.skipIf(WINDOWS, "platform: the record names a POSIX process group")
    def test_spawn_record_names_the_group(self):
        spawns = self.tmp / "spawns"
        spawns.mkdir()
        proc = self.run_quick(SPECWRIGHT_TEST_SPAWN_DIR=spawns)
        self.assertEqual((proc.returncode, proc.stdout), (0, "ok\n"))
        names = [p.name for p in spawns.iterdir()]
        self.assertEqual(len(names), 1, names)
        self.assertTrue(names[0].isdigit(), names)
        self.assertEqual((spawns / names[0]).stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
