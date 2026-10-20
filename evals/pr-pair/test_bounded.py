"""Tests for skills/specwright-pr/scripts/bounded.py, the deadline and byte bound every pr script's network call runs under.

Run: python -m unittest discover evals/pr-pair -p test_bounded.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BOUNDED = ROOT / "skills" / "specwright-pr" / "scripts" / "bounded.py"
FAKE_GH = ROOT / "evals" / "fakes" / "gh.py"
sys.path.insert(0, str(ROOT / "evals" / "git-workflow"))
import fixtures  # noqa: E402


def load_bounded():
    spec = importlib.util.spec_from_file_location("bounded", BOUNDED)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pid_alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
        return f'"{pid}"' in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def wait_gone(pid, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if not pid_alive(pid):
            return True
        time.sleep(0.2)
    return not pid_alive(pid)


def py(code, *args):
    return [sys.executable, "-c", code, *args]


# writes its PID to argv[1], then runs `body` (a forever loop or a quick print)
HANG = "import os,sys,time\nopen(sys.argv[1],'w').write(str(os.getpid()))\ntime.sleep(3600)\n"
SPEW = ("import os,sys\nopen(sys.argv[1],'w').write(str(os.getpid()))\n"
        "while True:\n    sys.stdout.write('x'*1000); sys.stdout.flush()\n")
SPEW_ERR = SPEW.replace("sys.stdout", "sys.stderr")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fixtures.rmtree, self.tmp)
        self.pidf = self.tmp / "pid"
        env = {k: v for k, v in os.environ.items() if not k.startswith("SPECWRIGHT_NET_")}
        self.env = env

    def pid(self):
        for _ in range(50):
            if self.pidf.exists() and self.pidf.read_text().strip():
                return int(self.pidf.read_text())
            time.sleep(0.1)
        self.fail("the child never wrote its PID")


class RunBounded(Base):
    def setUp(self):
        super().setUp()
        self.b = load_bounded()

    def test_deadline_stops_the_child_and_reports_deadline_exceeded(self):
        t0 = time.time()
        r = self.b.run_bounded(py(HANG, str(self.pidf)), 1, 1 << 20, self.env, None)
        self.assertEqual(r.limit, "deadline_exceeded")
        self.assertLess(time.time() - t0, 1 + 10)
        self.assertTrue(wait_gone(self.pid(), 10), "the child outlived deadline + 10 s")

    def test_output_over_the_bound_reports_response_too_large_and_stops_the_child(self):
        r = self.b.run_bounded(py(SPEW, str(self.pidf)), 30, 5000, self.env, None)
        self.assertEqual(r.limit, "response_too_large")
        self.assertTrue(wait_gone(self.pid(), 10))

    def test_stderr_over_the_bound_reports_response_too_large_and_stops_the_child(self):
        t0 = time.time()
        r = self.b.run_bounded(py(SPEW_ERR, str(self.pidf)), 30, 5000, self.env, None)
        self.assertEqual(r.limit, "response_too_large")
        self.assertLess(time.time() - t0, 15, "stderr ran on to the deadline")
        self.assertTrue(wait_gone(self.pid(), 10))

    def test_stderr_over_the_bound_after_a_quick_exit_is_response_too_large(self):
        r = self.b.run_bounded(py("import sys\nsys.stderr.write('x'*5000)"), 30, 100, self.env, None)
        self.assertEqual(r.limit, "response_too_large")

    def test_normal_exit_passes_rc_stdout_and_stderr_through(self):
        r = self.b.run_bounded(py("import sys\nprint('out')\nprint('err', file=sys.stderr)\nsys.exit(3)"), 30, 1 << 20, self.env, None)
        self.assertEqual((r.rc, r.limit), (3, None))
        self.assertEqual(r.stdout.strip(), "out")
        self.assertEqual(r.stderr.strip(), "err")

    def test_a_finished_command_is_never_reported_as_a_limit(self):
        r = self.b.run_bounded(py("print('x'*100)"), 30, 100000, self.env, None)
        self.assertEqual((r.rc, r.limit), (0, None))

    def test_deadline_at_caps_the_deadline(self):
        env = {**self.env, "SPECWRIGHT_NET_DEADLINE_AT": str(time.time() + 1)}
        t0 = time.time()
        r = self.b.run_bounded(py(HANG, str(self.pidf)), 60, 1 << 20, env, None)
        self.assertEqual(r.limit, "deadline_exceeded")
        self.assertLess(time.time() - t0, 15)
        self.assertTrue(wait_gone(self.pid(), 10))

    def test_deadline_at_in_the_past_stops_at_once(self):
        env = {**self.env, "SPECWRIGHT_NET_DEADLINE_AT": str(time.time() - 5)}
        r = self.b.run_bounded(py("import time\ntime.sleep(60)"), 60, 1 << 20, env, None)
        self.assertEqual(r.limit, "deadline_exceeded")

    def test_defaults_come_from_the_environment(self):
        env = {**self.env, "SPECWRIGHT_NET_DEADLINE": "1", "SPECWRIGHT_NET_MAX_BYTES": "5000"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(self.b.run_bounded(py(HANG, str(self.pidf))).limit, "deadline_exceeded")
            self.assertEqual(self.b.run_bounded(py(SPEW, str(self.pidf))).limit, "response_too_large")

    def test_paged_uses_the_paged_deadline(self):
        env = {**self.env, "SPECWRIGHT_NET_DEADLINE": "60", "SPECWRIGHT_NET_PAGED_DEADLINE": "1"}
        with mock.patch.dict(os.environ, env, clear=True):
            t0 = time.time()
            r = self.b.run_bounded(py(HANG, str(self.pidf)), paged=True)
            self.assertEqual(r.limit, "deadline_exceeded")
            self.assertLess(time.time() - t0, 15)

    def test_constants(self):
        self.assertEqual(self.b.MAX_PAGES, 50)

    def test_spawn_failure_is_rc_127(self):
        r = self.b.run_bounded([str(self.tmp / "no-such-binary")], 5, 1000, self.env, None)
        self.assertEqual((r.rc, r.limit), (127, None))


class SecretMode(Base):
    def setUp(self):
        super().setUp()
        self.b = load_bounded()
        self.scratch = self.tmp / "scratch"
        self.scratch.mkdir()
        for k in ("TMPDIR", "TEMP", "TMP"):
            self.env[k] = str(self.scratch)

    def test_writes_no_file_and_returns_the_token(self):
        r = self.b.run_bounded(py("print('tok-secret')"), 30, 1 << 20, self.env, None, secret=True)
        self.assertEqual((r.rc, r.limit, r.stdout.strip()), (0, None, "tok-secret"))
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_cli_secret_writes_no_file_under_a_fresh_tmpdir(self):
        r = subprocess.run([sys.executable, "-I", str(BOUNDED), "--secret", "--", *py("print('tok-secret')")],
                           capture_output=True, text=True, env=self.env)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "tok-secret"))
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_hung_lookup_stops_within_deadline_plus_5(self):
        t0 = time.time()
        r = self.b.run_bounded(py(HANG, str(self.pidf)), 2, 1 << 20, self.env, None, secret=True)
        self.assertEqual(r.limit, "deadline_exceeded")
        self.assertLess(time.time() - t0, 2 + 5)
        self.assertEqual(list(self.scratch.iterdir()), [])
        self.assertTrue(wait_gone(self.pid(), 10))

    def test_secret_flood_stops_at_the_bound_before_the_deadline(self):
        t0 = time.time()
        r = self.b.run_bounded(py(SPEW, str(self.pidf)), 30, 5000, self.env, None, secret=True)
        self.assertEqual(r.limit, "response_too_large")
        self.assertLess(time.time() - t0, 15, "the flood was buffered until the deadline")
        self.assertTrue(wait_gone(self.pid(), 10))
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_secret_stderr_flood_stops_at_the_bound(self):
        t0 = time.time()
        r = self.b.run_bounded(py(SPEW_ERR, str(self.pidf)), 30, 5000, self.env, None, secret=True)
        self.assertEqual(r.limit, "response_too_large")
        self.assertLess(time.time() - t0, 15)
        self.assertTrue(wait_gone(self.pid(), 10))

    def test_oversized_secret_output_is_response_too_large(self):
        r = self.b.run_bounded(py("print('x'*5000)"), 30, 100, self.env, None, secret=True)
        self.assertEqual(r.limit, "response_too_large")


class Cli(Base):
    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, "-I", str(BOUNDED), *args], capture_output=True, text=True, env={**self.env, **(env or {})})

    def test_normal_exit_passes_rc_stdout_stderr(self):
        r = self.run_cli("--", *py("import sys\nprint('out')\nprint('err', file=sys.stderr)\nsys.exit(3)"))
        self.assertEqual(r.returncode, 3)
        self.assertEqual(r.stdout.strip(), "out")
        self.assertEqual(r.stderr.strip(), "err")

    def test_deadline_exits_124_with_the_limit_line(self):
        cmd = py(HANG, str(self.pidf))
        r = self.run_cli("--", *cmd, env={"SPECWRIGHT_NET_DEADLINE": "1"})
        self.assertEqual(r.returncode, 124)
        self.assertIn(f"bounded: deadline_exceeded: {cmd[0]} {cmd[1]}", r.stderr)
        self.assertTrue(wait_gone(self.pid(), 10))

    def test_limit_line_names_the_command_inside_bash_c(self):
        # the pr scripts run `bash -c 'exec gh "$@"' gh api ...`: the line names gh api, not bash -c
        sh = shutil.which("bash") or shutil.which("sh")
        cmd = [sh, "-c", "sleep 3600", "gh", "api"]
        r = self.run_cli("--", *cmd, env={"SPECWRIGHT_NET_DEADLINE": "1"})
        self.assertEqual(r.returncode, 124)
        self.assertIn("bounded: deadline_exceeded: gh api" + chr(10), r.stderr)

    def test_too_large_exits_125_with_the_limit_line(self):
        cmd = py(SPEW, str(self.pidf))
        r = self.run_cli("--", *cmd, env={"SPECWRIGHT_NET_MAX_BYTES": "5000"})
        self.assertEqual(r.returncode, 125)
        self.assertIn(f"bounded: response_too_large: {cmd[0]} {cmd[1]}", r.stderr)
        self.assertTrue(wait_gone(self.pid(), 10))

    def test_paged_flag_uses_the_paged_deadline(self):
        cmd = py(HANG, str(self.pidf))
        r = self.run_cli("--paged", "--", *cmd, env={"SPECWRIGHT_NET_DEADLINE": "60", "SPECWRIGHT_NET_PAGED_DEADLINE": "1"})
        self.assertEqual(r.returncode, 124)

    def test_secret_deadline_exits_124(self):
        r = self.run_cli("--secret", "--", *py(HANG, str(self.pidf)), env={"SPECWRIGHT_NET_DEADLINE": "1"})
        self.assertEqual(r.returncode, 124)
        self.assertIn("bounded: deadline_exceeded:", r.stderr)


class ShimOnWindows(Base):
    """A `#!/bin/sh` gh is started through "$BASH" -c 'exec gh "$@"', as the scripts do."""

    def test_sh_shim_runs_through_bash(self):
        bash = os.environ.get("BASH") or shutil.which("bash")
        if not bash:
            self.skipTest("no bash")
        if shutil.which("cygpath"):
            bash = subprocess.run(["cygpath", "-w", bash], capture_output=True, text=True).stdout.strip() or bash
        bindir = self.tmp / "bin"
        bindir.mkdir()
        shim = bindir / "gh"
        shim.write_text('#!/bin/sh\necho "shim: $*"\n', encoding="utf-8", newline="\n")
        shim.chmod(0o755)
        env = {**self.env, "PATH": f"{bindir}{os.pathsep}{self.env.get('PATH', '')}"}
        r = subprocess.run([sys.executable, "-I", str(BOUNDED), "--", bash, "-c", 'exec gh "$@"', "gh", "api", "user"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "shim: api user")

    def test_the_fake_gh_hangs_and_is_stopped_through_bash(self):
        bash = os.environ.get("BASH") or shutil.which("bash")
        if not bash:
            self.skipTest("no bash")
        if shutil.which("cygpath"):
            bash = subprocess.run(["cygpath", "-w", bash], capture_output=True, text=True).stdout.strip() or bash
        bindir = self.tmp / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        fake = FAKE_GH.as_posix()
        gh.write_text(f'#!/bin/sh\nexec python "{fake}" "$@"\n', encoding="utf-8", newline="\n")
        gh.chmod(0o755)
        state = self.tmp / "state.json"
        state.write_text(json.dumps({"user": "u", "hang": [{"match": "api user", "pid_file": str(self.pidf)}]}), encoding="utf-8")
        env = {**self.env, "PATH": f"{bindir}{os.pathsep}{self.env.get('PATH', '')}", "FAKE_GH_STATE": str(state),
               "SPECWRIGHT_NET_DEADLINE": "2"}
        t0 = time.time()
        r = subprocess.run([sys.executable, "-I", str(BOUNDED), "--", bash, "-c", 'exec gh "$@"', "gh", "api", "user"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 124, r.stderr)
        self.assertLess(time.time() - t0, 2 + 10)
        self.assertTrue(wait_gone(self.pid(), 10), "the fake gh outlived the deadline")


def windows_bash():
    bash = os.environ.get("BASH") or shutil.which("bash")
    if not bash:
        return None
    if shutil.which("cygpath"):
        bash = subprocess.run(["cygpath", "-w", bash], capture_output=True, text=True).stdout.strip() or bash
    return bash


@unittest.skipUnless(os.name == "nt", "the argument transport is Windows only")
class ArgumentTransport(Base):
    """D1: on Windows the arguments after $0 travel on the child's stdin, not on the command line."""

    def setUp(self):
        super().setUp()
        self.bash = windows_bash()
        if not self.bash:
            self.skipTest("no bash")
        self.mod = load_bounded()

    def test_round_trip_through_bash_c(self):
        args = ["a " * 4500, "line one\nline two", "say \"hi\" and 'there'", "back\\\\slash \\\\ end",
                "ellipsis … thumbs \U0001F44D", ""]
        self.assertGreaterEqual(len(args[0]), 9000)
        script = 'printf "%s\\0" "$#" "$0" "$@"; [ -z "$(cat)" ] || printf STDIN-NOT-EMPTY'
        for secret in (False, True):
            with self.subTest(secret=secret):
                r = self.mod.run_bounded([self.bash, "-c", script, "zero", *args], env=self.env, secret=secret)
                self.assertEqual(r.rc, 0, r.stderr)
                self.assertEqual(r.limit, None)
                self.assertEqual(r.stdout.split("\0")[:-1], [str(len(args)), "zero", *args])

    def test_no_arguments_after_zero(self):
        r = self.mod.run_bounded([self.bash, "-c", 'printf "%s|%s" "$#" "$0"', "zero"], env=self.env)
        self.assertEqual((r.rc, r.stdout), (0, "0|zero"))

    def test_a_missing_end_marker_exits_126_and_does_not_run_the_command(self):
        ran = self.tmp / "ran"
        script = self.mod.ARGV_PRELUDE + "; echo ran > " + ran.as_posix()
        for data in (b"a\0b\0", b""):
            with self.subTest(data=data):
                r = subprocess.run([self.bash, "-c", script, "zero"], input=data, capture_output=True)
                self.assertEqual(r.returncode, 126, r.stderr)
                self.assertIn(b"bounded: argument transport failed", r.stderr)
                self.assertFalse(ran.exists())

    def test_a_child_that_never_reads_prints_no_traceback(self):
        code = ("import sys; sys.path.insert(0, %r); import bounded\n"
                "r = bounded.run_bounded([%r, '-c', 'exit 0', 'zero', 'x' * 20000000], deadline=1, secret=%%s)\n"
                "print(r.limit)\n") % (str(BOUNDED.parent), self.bash)
        for secret in (False, True):
            with self.subTest(secret=secret):
                r = subprocess.run([sys.executable, "-c", code % secret], capture_output=True, text=True, env=self.env, timeout=60)
                self.assertNotIn("Traceback", r.stderr)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_cli_limit_line_names_the_original_command(self):
        bindir = self.tmp / "bin"
        bindir.mkdir()
        (bindir / "gh").write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8", newline="\n")
        env = {**self.env, "PATH": f"{bindir}{os.pathsep}{self.env.get('PATH', '')}", "SPECWRIGHT_NET_DEADLINE": "1"}
        r = subprocess.run([sys.executable, "-I", str(BOUNDED), "--", self.bash, "-c", 'exec gh "$@"', "gh", "api", "user"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 124, r.stderr)
        self.assertIn("bounded: deadline_exceeded: gh api", r.stderr)


if __name__ == "__main__":
    unittest.main()
