"""Black-box tests for `sw run --bounded`, the compiled counterpart of skills/specwright-pr/scripts/bounded.py's CLI.

Needs the binary named by SPECWRIGHT_SW (skips as `sw not built` otherwise). Every test keeps its limits small by lowering
them through the environment, which can only lower them. Fixtures are small Python scripts run with sys.executable.

Run: SPECWRIGHT_SW=<path> python -m unittest evals/cli/test_sw_run.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import swharness  # noqa: E402
import bashexe  # noqa: E402

MIB = 1024 * 1024
HANG = "import os, sys, time\nopen(sys.argv[1], 'w').write(str(os.getpid()))\ntime.sleep(3600)\n"
SPEW_OUT = ("import os, sys\nopen(sys.argv[1], 'w').write(str(os.getpid()))\n"
            "while True:\n    sys.stdout.write('x' * 1000)\n    sys.stdout.flush()\n")
SPEW_ERR = SPEW_OUT.replace("sys.stdout", "sys.stderr")
MARK = "import sys\nopen(sys.argv[1], 'a').write('started\\n')\n"


def pid_alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
        return '"%d"' % pid in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_pid(pid):
    """Test cleanup only: stop a process this test started and recorded, by PID."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, 9)
    except OSError:
        pass


def wait_gone(pid, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if not pid_alive(pid):
            return True
        time.sleep(0.2)
    return not pid_alive(pid)


class Base(unittest.TestCase):
    def setUp(self):
        swharness.require_sw()
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-run-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.pidf = self.tmp / "pid"
        self.addCleanup(self.stop_recorded)

    def stop_recorded(self):
        for f in [self.pidf, *self.tmp.glob("*.pid")]:
            try:
                stop_pid(int(f.read_text().strip()))
            except (OSError, ValueError):
                pass

    def script(self, name, body):
        path = self.tmp / name
        path.write_text(body, encoding="utf-8")
        return str(path)

    def env(self, **extra):
        return swharness.fixture_env(**extra)

    def sw(self, *args, env=None, timeout=60):
        t0 = time.monotonic()
        proc = swharness.run_sw("run", "--bounded", *args, env=env if env is not None else self.env(), timeout=timeout)
        proc.elapsed = time.monotonic() - t0
        return proc

    def recorded_pid(self, path=None):
        path = path or self.pidf
        for _ in range(50):
            if path.exists() and path.read_text().strip():
                return int(path.read_text())
            time.sleep(0.1)
        self.fail("the command never wrote its PID")


class PassThrough(Base):
    def test_passes_output_and_status_through(self):
        script = self.script("c.py", "import sys\nsys.stdout.write('out\\n')\nsys.stderr.write('err\\n')\nsys.exit(3)\n")
        proc = self.sw("--", sys.executable, script)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (3, "out\n", "err\n"))


class Limits(Base):
    def line(self, limit, script):
        return "bounded: %s: %s %s\n" % (limit, sys.executable, script)

    def test_deadline_exits_124_with_the_limit_line(self):
        script = self.script("hang.py", HANG)
        proc = self.sw("--", sys.executable, script, str(self.pidf), env=self.env(SPECWRIGHT_NET_DEADLINE=1))
        self.assertEqual(proc.returncode, 124)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, self.line("deadline_exceeded", script))
        self.assertTrue(wait_gone(self.recorded_pid(), 10), "the command survived the deadline")

    def test_too_large_exits_125_before_the_deadline(self):
        for name, body in (("stdout", SPEW_OUT), ("stderr", SPEW_ERR)):
            with self.subTest(stream=name):
                script = self.script("spew-%s.py" % name, body)
                pidf = self.tmp / ("%s.pid" % name)
                proc = self.sw("--", sys.executable, script, str(pidf), env=self.env(SPECWRIGHT_NET_MAX_BYTES=5000))
                self.assertEqual(proc.returncode, 125)
                self.assertEqual(proc.stdout, "")
                self.assertEqual(proc.stderr, self.line("response_too_large", script))
                self.assertLess(proc.elapsed, 15, "the flood was held until the deadline")
                self.assertTrue(wait_gone(self.recorded_pid(pidf), 10), "the command survived the bound")

    def test_limited_command_started_at_most_once(self):
        counter = self.tmp / "starts"
        for name, extra in (("deadline", {"SPECWRIGHT_NET_DEADLINE": 1}), ("bytes", {"SPECWRIGHT_NET_MAX_BYTES": 5000})):
            with self.subTest(limit=name):
                counter.write_text("")
                body = ("import sys, time\nopen(sys.argv[1], 'a').write('start\\n')\n"
                        "sys.stdout.write('x' * 100000)\nsys.stdout.flush()\ntime.sleep(3600)\n")
                script = self.script("once.py", body)
                proc = self.sw("--", sys.executable, script, str(counter), env=self.env(**extra))
                self.assertIn(proc.returncode, (124, 125))
                time.sleep(1)  # a retry would have started by now
                self.assertEqual(counter.read_text().count("start"), 1)

    def test_limit_line_names_the_command_inside_bash_c(self):
        bash = bashexe.bash()
        if not bash:
            self.skipTest("no bash installed")
        proc = self.sw("--", bash, "-c", "sleep 3600", "gh", "api", "user", env=self.env(SPECWRIGHT_NET_DEADLINE=1))
        self.assertEqual(proc.returncode, 124)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "bounded: deadline_exceeded: gh api\n")

    def test_exit_after_deadline_exits_124(self):
        script = self.script("late.py", "import time\ntime.sleep(2.5)\nprint('late')\n")
        proc = self.sw("--", sys.executable, script, env=self.env(SPECWRIGHT_NET_DEADLINE=1))
        self.assertEqual(proc.returncode, 124)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, self.line("deadline_exceeded", script))


class Invocation(Base):
    def test_invalid_invocation_exits_2_and_starts_nothing(self):
        marker = self.tmp / "started"
        script = self.script("mark.py", MARK)
        cases = {
            "no --": ["run", "--bounded", sys.executable, script, str(marker)],
            "nothing after --": ["run", "--bounded", "--"],
            "unknown flag": ["run", "--bounded", "--bogus", "--", sys.executable, script, str(marker)],
            "no --bounded": ["run", "--", sys.executable, script, str(marker)],
        }
        for name, args in cases.items():
            with self.subTest(case=name):
                proc = swharness.run_sw(*args, env=self.env())
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")
                self.assertIn("usage: sw run --bounded", proc.stderr)
                time.sleep(0.3)
                self.assertFalse(marker.exists(), "the command was started")

    def test_missing_command_exits_127(self):
        proc = self.sw("--", "sw-no-such-command-xyz", "arg")
        self.assertEqual(proc.returncode, 127)
        self.assertEqual(proc.stdout, "")
        self.assertIn("sw-no-such-command-xyz", proc.stderr)


class Overrides(Base):
    def test_env_lowers_the_deadline(self):
        script = self.script("hang.py", HANG)
        proc = self.sw("--", sys.executable, script, str(self.pidf), env=self.env(SPECWRIGHT_NET_DEADLINE=1))
        self.assertEqual(proc.returncode, 124)
        self.assertLess(proc.elapsed, 20, "the default 120 s deadline applied")

    def test_env_cannot_raise_a_limit(self):
        # Bytes: 33 MiB written, then a quick exit. A raised bound would let it through with status 0.
        script = self.script("big.py", "import sys\nfor _ in range(33):\n    sys.stdout.write('x' * %d)\n    sys.stdout.flush()\n" % MIB)
        proc = self.sw("--", sys.executable, script, env=self.env(SPECWRIGHT_NET_MAX_BYTES=100 * MIB))
        self.assertEqual(proc.returncode, 125, "a bound above 32 MiB was honoured")
        # Deadline: the exact 120 s clamp is proven by cli/test/limits_test.dart (running it for 120 s is not cheap). Here a
        # raised value must leave the other limits in force: DEADLINE_AT still caps it, and the line is the usual one.
        hang = self.script("hang.py", HANG)
        proc = self.sw("--", sys.executable, hang, str(self.pidf),
                       env=self.env(SPECWRIGHT_NET_DEADLINE=100000, SPECWRIGHT_NET_PAGED_DEADLINE=100000,
                                    SPECWRIGHT_NET_DEADLINE_AT=time.time() + 2))
        self.assertEqual(proc.returncode, 124)
        self.assertLess(proc.elapsed, 30)

    def test_deadline_at_in_the_past_exits_124_unstarted(self):
        marker = self.tmp / "started"
        script = self.script("mark.py", MARK)
        proc = self.sw("--", sys.executable, script, str(marker), env=self.env(SPECWRIGHT_NET_DEADLINE_AT=time.time() - 100))
        self.assertEqual(proc.returncode, 124)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "bounded: deadline_exceeded: %s %s\n" % (sys.executable, script))
        time.sleep(1)
        self.assertFalse(marker.exists(), "the command started")

    def test_malformed_override_is_ignored(self):
        quick = self.script("quick.py", "print('ok')\n")
        hang = self.script("hang.py", HANG)
        for value in ("abc", "-5"):
            with self.subTest(value=value):
                proc = self.sw("--", sys.executable, quick, env=self.env(SPECWRIGHT_NET_DEADLINE=value, SPECWRIGHT_NET_MAX_BYTES=value))
                self.assertEqual((proc.returncode, proc.stdout), (0, "ok\n"), "a malformed value became a zero limit")
                self.pidf.unlink(missing_ok=True)
                proc = self.sw("--", sys.executable, hang, str(self.pidf),
                               env=self.env(SPECWRIGHT_NET_DEADLINE=value, SPECWRIGHT_NET_DEADLINE_AT=time.time() + 3))
                self.assertEqual(proc.returncode, 124)
                self.assertTrue(self.pidf.exists(), "the command never started: the value was read as 0")
                self.assertGreater(proc.elapsed, 1.5, "the deadline fired early")
                self.assertLess(proc.elapsed, 30, "the 120 s default applied instead of the cap")
                stop_pid(self.recorded_pid())


class ExitJudgement(Base):
    def test_exit_before_deadline_with_pipe_holder_keeps_status(self):
        # The command starts a child that inherits stdout and sleeps, prints, then exits 0 at ~2 s: shortly before the 3 s
        # deadline. Its status and output stand (never 124) and the child must be stopped.
        child = self.script("holder.py", "import os, sys, time\nopen(sys.argv[1], 'w').write(str(os.getpid()))\ntime.sleep(3600)\n")
        parent = self.script("parent.py",
                             "import subprocess, sys, time\n"
                             "subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2]])\n"
                             "print('parent-out', flush=True)\ntime.sleep(2)\nsys.exit(0)\n")
        holder_pid = self.tmp / "holder.pid"
        proc = self.sw("--", sys.executable, parent, child, str(holder_pid), env=self.env(SPECWRIGHT_NET_DEADLINE=3))
        self.assertEqual((proc.returncode, proc.stdout), (0, "parent-out\n"))
        self.assertTrue(wait_gone(self.recorded_pid(holder_pid), 5), "the pipe-holding child survived sw")


class Secret(Base):
    def setUp(self):
        super().setUp()
        self.scratch = self.tmp / "scratch"
        self.scratch.mkdir()

    def secret_env(self, **extra):
        return self.env(TMPDIR=self.scratch, TMP=self.scratch, TEMP=self.scratch, **extra)

    def test_secret_mode_writes_nothing_to_disk(self):
        script = self.script("tok.py", "import sys\nsys.stdout.write('tok-secret\\n')\nsys.exit(4)\n")
        proc = self.sw("--secret", "--", sys.executable, script, env=self.secret_env())
        self.assertEqual((proc.returncode, proc.stdout), (4, "tok-secret\n"))
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_secret_flood_never_echoes_output(self):
        for name, body in (("stdout", SPEW_OUT), ("stderr", SPEW_ERR)):
            with self.subTest(stream=name):
                script = self.script("spew-%s.py" % name, body.replace("'x' * 1000", "'tok-secret ' * 100"))
                proc = self.sw("--secret", "--", sys.executable, script, str(self.tmp / ("%s.pid" % name)),
                               env=self.secret_env(SPECWRIGHT_NET_MAX_BYTES=5000))
                self.assertEqual(proc.returncode, 125)
                self.assertEqual(proc.stdout, "")
                self.assertEqual(proc.stderr, "bounded: response_too_large: %s %s\n" % (sys.executable, script))
                self.assertNotIn("tok-secret ", proc.stdout + proc.stderr)
                self.assertEqual(list(self.scratch.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
