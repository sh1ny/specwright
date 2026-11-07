"""as.sh is a shim: it resolves the project's sw with sw-path.sh and runs `sw as --args-file` (ADR 0028, ADR 0029).

The fence's own behaviour (the checks, the environment, the messages) is pinned by test_as_sh.py, test_as_jj.py, test_as_gitbutler.py and
test_parity.py. These tests cover what the shim adds: how it finds `sw`, what it hands over, and that the fenced command keeps
the caller's stdin, its argument bytes, its signals and its bounded caller.

Run: python -m unittest evals/pr-pair/test_as_shim.py
"""
import json
import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_as_sh as tas  # noqa: E402
from test_as_sh import AS_SH, ROOT, fixtures_kill, bashexe, vcs_test_support  # noqa: E402

sys.path.append(str(ROOT / "evals" / "cli"))
import swharness  # noqa: E402

STOP = "sw missing or mismatched: rerun the install prompt"
USAGE = "as.sh: line 47: 1: usage: as.sh <login> <command> [args...] | as.sh --resolve"


class ShimCase(tas.AsShCase):
    def bash_command(self, script, *args):
        """A fenced command that is bash itself (an absolute path, so the fence's exec finds it on every OS)."""
        return [Path(bashexe.bash()).as_posix(), "-c", script, "x", *args]

    def stop_document(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_missing"), doc)
        self.assertTrue(doc["message"].startswith(STOP), doc)
        self.assertIn(STOP, result.stderr)
        return doc


class TestShim(ShimCase):
    def test_fenced_gh_call_runs_sw(self):
        r = self.as_sh(self.code, "KintsugiBot", "gh", "api", "user", "--jq", ".login")  # the active account is sh1ny
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "KintsugiBot"), r.stderr)
        api = [c for c in self.gh_calls() if c["argv"][0] == "api"]
        self.assertEqual({c["env"]["GH_TOKEN"] for c in api}, {"tok-k"}, "sw as ran the fence: the run login's token")

    def test_resolve_runs_sw(self):
        r = self.as_sh(self.code, "--resolve")
        self.assertEqual((r.returncode, r.stdout), (0, "sh1ny\n"), r.stderr)

    def test_binary_missing_is_sw_missing(self):
        home = self.tmp / "empty-home"
        home.mkdir()
        r = self.as_sh(self.code, "sh1ny", "gh", "api", "user", env={"SPECWRIGHT_HOME": str(home)})
        doc = self.stop_document(r)
        self.assertIn(".specwright/bin/%s/sw" % vcs_test_support.tree_version(), doc["message"].replace("\\", "/"))
        self.assertEqual(self.gh_calls(), [], "no gh call ran")

    def test_resolve_without_sw_exits_1(self):
        home = self.tmp / "empty-home"
        home.mkdir()
        r = self.as_sh(self.code, "--resolve", env={"SPECWRIGHT_HOME": str(home)})
        self.stop_document(r)
        self.assertEqual(self.gh_calls(), [], "no gh call ran")

    def test_no_python(self):
        empty = self.tmp / "no-tools"
        empty.mkdir()
        e = {**self.env(), "PATH": str(empty)}
        r = subprocess.run([bashexe.bash(), str(AS_SH), "--resolve"], cwd=self.code, env=e, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (2, ""), r.stderr)
        self.assertEqual(r.stderr, "as.sh: no_python: needs python 3.8+ for its bounded gh calls\n")

    def test_argument_bytes_and_exit_status(self):
        out = self.tmp / "args.out"
        args = ["a b", "", "$x \"y\" *", "--sw-end--", "-n", "tab\there", "end"]
        if os.name != "nt":  # on Windows the MSYS bash that starts the shim brace-expands this one before the shim sees it
            args.insert(3, "{1,2}")
        r = self.as_sh(self.code, "sh1ny", *self.bash_command('printf "%s|" "${@:2}" > "$1"; exit 7', out.as_posix(), *args))
        self.assertEqual(r.returncode, 7, r.stderr)
        self.assertEqual(out.read_text(encoding="utf-8"), "".join(a + "|" for a in args))

    def test_missing_command_exits_127(self):
        r = self.as_sh(self.code, "sh1ny", "sw-no-such-command-xyz")
        self.assertEqual(r.returncode, 127, r.stderr)
        self.assertIn("sw-no-such-command-xyz", r.stderr)

    def test_stdin_reaches_the_command(self):
        r = self.as_sh(self.code, "sh1ny", "cat", stdin="from the caller\n")
        self.assertEqual((r.returncode, r.stdout), (0, "from the caller\n"), r.stderr)

    def test_exit_codes(self):
        self.assertEqual(self.as_sh(self.code).returncode, 1)
        self.assertEqual(self.as_sh(self.code).stderr, USAGE + "\n")
        r = self.as_sh(self.code, "sh1ny")
        self.assertEqual((r.returncode, r.stderr), (2, "as.sh: no command given\n"))
        self.assertEqual(self.as_sh(self.code, "--resolve", "extra").returncode, 2)
        refused = self.as_sh(self.code, "sh1ny", "git", "-C", str(self.store), "status")
        self.assertEqual(refused.returncode, 3, refused.stderr)
        self.assertEqual(self.as_sh(self.code, "sh1ny", *self.bash_command("exit 7")).returncode, 7)

    def test_handoff_file_gone_before_the_command(self):
        temp = self.tmp / "fresh-temp"
        temp.mkdir()
        listing = self.tmp / "temp-listing"
        env = {"TEMP": str(temp), "TMP": str(temp), "TMPDIR": temp.as_posix() if os.name == "nt" else str(temp)}
        r = self.as_sh(self.code, "sh1ny", *self.bash_command('ls -A "$1" > "$2"', temp.as_posix(), listing.as_posix()), env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(listing.read_text(), "", "the handoff file or the fence's own directory was still there when the command ran")
        self.assertEqual(list(temp.iterdir()), [])

    def test_configured_account_not_active_passes(self):
        r = self.as_sh(self.code, "KintsugiBot", "gh", "api", "user", "--jq", ".login")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "KintsugiBot"), r.stderr)

    def test_token_of_another_login_is_refused(self):
        self.state(user="sh1ny", tokens={"sh1ny": "tok-s", "KintsugiBot": "tok-s"})
        marker = self.tmp / "ran"
        r = self.as_sh(self.code, "KintsugiBot", *self.bash_command('touch "$1"', marker.as_posix()))
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("token resolves to 'sh1ny', expected 'KintsugiBot'", r.stderr)
        self.assertFalse(marker.exists())

    @unittest.skipUnless(sys.platform == "darwin" and os.path.exists("/bin/bash"), "macOS /bin/bash 3.2 only")
    def test_macos_bin_bash_empty_argument_and_argument_bytes(self):
        out = self.tmp / "mac.out"
        e = self.env()
        r = subprocess.run(["/bin/bash", str(AS_SH), "sh1ny", *self.bash_command('printf "%s|" "${@:2}" > "$1"', out.as_posix(), "", "a b", "é")],
                           cwd=self.code, env=e, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(out.read_text(encoding="utf-8"), "|a b|é|")


class TestShimProcess(ShimCase):
    DEADLINE = 2

    def hang(self, match):
        pidf = self.tmp / "hang.pid"
        self.addCleanup(fixtures_kill, pidf)
        st = json.loads((self.tmp / "gh-state.json").read_text(encoding="utf-8"))
        st["hang"] = [{"match": match, "pid_file": str(pidf)}]
        self.state(**st)

    def test_hung_token_lookup_exits_3(self):
        self.hang(r"auth token --hostname")
        out, err = self.tmp / "as.out", self.tmp / "as.err"
        marker = self.tmp / "ran"
        e = {**self.env(), "SPECWRIGHT_NET_DEADLINE": str(self.DEADLINE)}
        t = time.time()
        with open(out, "wb") as fo, open(err, "wb") as fe:
            p = subprocess.Popen([bashexe.bash(), str(AS_SH), "KintsugiBot", *self.bash_command('touch "$1"', marker.as_posix())],
                                 cwd=self.code, stdout=fo, stderr=fe, env=e)
            try:
                rc = p.wait(timeout=45)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True) if os.name == "nt" else p.kill()
                p.wait()
                rc = -9
        self.assertEqual(rc, 3, err.read_text(errors="replace"))
        self.assertIn("as.sh: deadline_exceeded: gh auth token --user KintsugiBot", err.read_text(errors="replace"))
        self.assertLess(time.time() - t, self.DEADLINE + 10)
        self.assertFalse(marker.exists(), "the fenced command must not run")

    def test_bounded_caller_stops_the_fenced_tree(self):
        late = self.tmp / "late"
        sw = swharness.require_sw()
        e = {**self.env(), "SPECWRIGHT_NET_DEADLINE": str(self.DEADLINE)}
        command = [sw, "run", "--bounded", "--", bashexe.bash(), str(AS_SH), "sh1ny",
                   *self.bash_command('sleep 8; touch "$1"', late.as_posix())]
        t = time.time()
        r = subprocess.run(command, cwd=self.code, env=e, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 124, r.stdout + r.stderr)
        self.assertLess(time.time() - t, self.DEADLINE + 10)
        time.sleep(9)  # long enough for a command that was left running to finish
        self.assertFalse(late.exists(), "the fenced command outlived its bounded caller")

    @unittest.skipIf(os.name == "nt", "POSIX signals")
    def test_sigterm_reaches_the_command(self):
        ready, term = self.tmp / "ready", self.tmp / "term"
        script = f'trap \'touch "{term.as_posix()}"; exit 0\' TERM; touch "{ready.as_posix()}"; while :; do sleep 0.2; done'
        p = subprocess.Popen([bashexe.bash(), str(AS_SH), "sh1ny", *self.bash_command(script)], cwd=self.code, env=self.env(),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(p.kill)
        deadline = time.time() + 30
        while not ready.exists() and time.time() < deadline:
            time.sleep(0.1)
        self.assertTrue(ready.exists(), "the command never started")
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=30), 0)
        self.assertTrue(term.exists(), "SIGTERM did not reach the fenced command")


if __name__ == "__main__":
    unittest.main()
