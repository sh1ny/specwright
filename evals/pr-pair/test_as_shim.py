"""`sw as` entered directly (ADR 0028, ADR 0029; the as.sh shim is gone since 0.38.0).

The fence's own behaviour (the checks, the environment, the messages) is pinned by test_as_sh.py, test_as_jj.py, test_as_gitbutler.py and
test_parity.py. These tests cover what the entry adds: that the fenced command keeps the caller's stdin, its argument bytes, its
signals and its bounded caller, and that the project's version is checked.

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
from test_as_sh import ROOT, fixtures_kill, bashexe  # noqa: E402

sys.path.append(str(ROOT / "evals" / "cli"))
import swharness  # noqa: E402
import fakeexe  # noqa: E402  (evals/ is on sys.path through test_as_sh)
import swcall  # noqa: E402

USAGE = r"^as\.sh: line 47: 1: usage: as\.sh <login> <command> \[args\.\.\.\] \| as\.sh --resolve\n$"
NO_COMMAND = r"^as\.sh: no command given\n$"
HUNG_LOOKUP = r"as\.sh: deadline_exceeded: gh auth token --user KintsugiBot"


class ShimCase(tas.AsShCase):
    def bash_command(self, script, *args):
        """A fenced command that is bash itself (an absolute path, so the fence's exec finds it on every OS)."""
        return [Path(bashexe.bash()).as_posix(), "-c", script, "x", *args]

class TestShim(ShimCase):
    def test_fenced_gh_call_runs_sw(self):
        r = self.as_sh(self.code, "KintsugiBot", "gh", "api", "user", "--jq", ".login")  # the active account is sh1ny
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "KintsugiBot"), r.stderr)
        api = [c for c in self.gh_calls() if c["argv"][0] == "api"]
        self.assertEqual({c["env"]["GH_TOKEN"] for c in api}, {"tok-k"}, "sw as ran the fence: the run login's token")

    def test_resolve_runs_sw(self):
        r = self.as_sh(self.code, "--resolve")
        self.assertEqual((r.returncode, r.stdout), (0, "sh1ny\n"), r.stderr)

    def test_resolve_in_other_version_is_sw_mismatch(self):
        """native-cli A4: the project's VERSION is not the binary's, so `sw as --resolve` stops before any gh call."""
        swcall.stamp(self.code, "99.0.0")
        r = self.as_sh(self.code, "--resolve")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_mismatch"), doc)
        self.assertEqual(self.gh_calls(), [], "no gh call ran")
        swcall.stamp(self.code)
        control = self.as_sh(self.code, "--resolve")  # the control: the matching VERSION resolves
        self.assertEqual((control.returncode, control.stdout), (0, "sh1ny\n"), control.stderr)

    def test_old_handoff_flag_is_unknown_option(self):
        """github-identity "Old handoff flag": `sw as --args-file <path>` is an unknown option: exit 2, no gh call, nothing on
        stdout, and the file is neither read nor deleted."""
        handoff = self.tmp / "handoff"
        handoff.write_bytes(b"/scripts\0bash\0sh1ny\0gh\0api\0user\0")
        r = self.as_sh(self.code, "--args-file", str(handoff))
        self.assertEqual((r.returncode, r.stdout), (2, ""), r.stderr)
        self.assertIn("unknown option: --args-file", r.stderr)
        self.assertTrue(handoff.exists(), "the handoff file was read and deleted")
        self.assertEqual(self.gh_calls(), [], "no gh call ran")

    def failing_bash(self):
        """A recording `bash` that exits 1 (a `.cmd` on Windows, where only PATHEXT names start), first on PATH.

        Returns the environment that puts it there and the log it appends to. sw starts no shell for its own work, so the
        log stays empty; the fenced command in these tests names its bash by absolute path."""
        shells = self.tmp / "failing-shells"
        shells.mkdir()
        log = self.tmp / "shell.log"
        if os.name == "nt":
            (shells / "bash.cmd").write_bytes(b'@echo bash>>"%SW_SHELL_LOG%"\r\n@exit /b 1\r\n')
        else:
            fakeexe.write_script(shells / "bash", '#!/bin/sh\nprintf "%s\\n" bash >> "$SW_SHELL_LOG"\nexit 1\n')
        return {"PATH": str(shells) + os.pathsep + self.env()["PATH"], "SW_SHELL_LOG": str(log)}, log

    def test_argument_bytes_and_exit_status(self):
        out = self.tmp / "args.out"
        args = ["a b", "", "$x \"y\" *", "--sw-end--", "-n", "tab\there", "end"]
        if os.name != "nt":  # on Windows the MSYS bash that starts the shim brace-expands this one before the shim sees it
            args.insert(3, "{1,2}")
        env, log = self.failing_bash()
        r = self.as_sh(self.code, "sh1ny", *self.bash_command('printf "%s|" "${@:2}" > "$1"; exit 7', out.as_posix(), *args), env=env)
        self.assertEqual(r.returncode, 7, r.stderr)
        self.assertEqual(out.read_text(encoding="utf-8"), "".join(a + "|" for a in args))
        self.assertFalse(log.exists(), "a shell started")

    def test_fenced_shell_command_runs_as_asked(self):
        """A fenced command the caller names, even a shell, runs as given: `bash` is found on PATH and started once."""
        shells = self.tmp / "named-bash"
        shells.mkdir()
        log = self.tmp / "named-bash.log"
        real = Path(bashexe.bash()).as_posix()
        if os.name == "nt":
            (shells / "bash.cmd").write_bytes(('@echo bash>>"%%SW_SHELL_LOG%%"\r\n@"%s" %%*\r\n' % real).encode("utf-8"))
        else:
            fakeexe.write_script(shells / "bash", '#!/bin/sh\nprintf "%%s\\n" bash >> "$SW_SHELL_LOG"\nexec "%s" "$@"\n' % real)
        env = {"PATH": str(shells) + os.pathsep + self.env()["PATH"], "SW_SHELL_LOG": str(log)}
        r = self.as_sh(self.code, "sh1ny", "bash", "-c", "exit 7", env=env)
        self.assertEqual(r.returncode, 7, r.stderr)
        self.assertEqual(log.read_text().split(), ["bash"], "bash started once, as the fenced command")  # bare-bash: not started

    @unittest.skipUnless(os.name == "nt", "platform: Windows batch files")
    def test_fenced_batch_command_keeps_caller_stdio(self):
        bin_dir = self.tmp / "batch-bin"
        bin_dir.mkdir()
        (bin_dir / "fake.cmd").write_bytes(b"@echo off\r\nset /p L=\r\necho got:%L% token:%GH_TOKEN%\r\nexit /b 3\r\n")
        env = {"PATH": str(bin_dir) + os.pathsep + self.env()["PATH"]}
        r = self.as_sh(self.code, "sh1ny", "fake", env=env, stdin="from the caller\n")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("got:from the caller token:tok-s", r.stdout)
        self.assertEqual(r.stderr, "", "no helper frame on stderr")

    def argv_tool(self):
        """A fake `fake-tool` that writes its argument list as JSON to the file named by FAKE_ARGV_OUT; returns that file."""
        out = self.tmp / "argv.json"
        source = ('import json, os, sys\n'
                  'with open(os.environ["FAKE_ARGV_OUT"], "w", encoding="utf-8") as f:\n'
                  '    json.dump(sys.argv[1:], f)\n')
        fakeexe.write_python_fake(self.tmp / "bin" / "fake-tool", source)
        return out

    def test_fenced_tool_receives_unicode_values(self):
        out = self.argv_tool()
        args = ["a b", "", 'q "uo" te', "back\\slash", "trail\\", "h\u00e9llo \u20ac", "\u65e5\u672c\u8a9e", "tab\there"]
        if os.name != "nt":  # the MSYS bash that starts the shim on Windows splits an argument at a newline before the shim sees it
            args.insert(5, "two\nlines")
        r = self.as_sh(self.code, "sh1ny", "fake-tool", *args, env={"FAKE_ARGV_OUT": str(out)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8")), args)

    @unittest.skipUnless(os.name == "nt", "platform: Windows command lines")
    def test_long_argument_reaches_fenced_tool_on_windows(self):
        out = self.argv_tool()
        arg = "".join(chr(ord("a") + i % 26) for i in range(20000))
        r = self.as_sh(self.code, "sh1ny", "fake-tool", arg, env={"FAKE_ARGV_OUT": str(out)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8")), [arg])

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: Linux file names hold any byte")
    def test_non_utf8_argument_is_refused(self):
        ran = self.tmp / "git.ran"
        fakeexe.write_fake(self.tmp / "bin" / "git", '#!/bin/sh\necho ran >> "$FAKE_GIT_RAN"\nexit 0\n')
        name = os.fsdecode(b"a\xff.txt")  # the byte 0xFF, which no UTF-8 text holds
        r = self.as_sh(self.code, "sh1ny", "git", "add", "--", name, env={"FAKE_GIT_RAN": str(ran)})
        self.assertNotEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertEqual(self.gh_calls(), [], "no token was read")
        self.assertFalse(ran.exists(), "git ran")

    def test_missing_command_exits_127(self):
        r = self.as_sh(self.code, "sh1ny", "sw-no-such-command-xyz")
        self.assertEqual(r.returncode, 127, r.stderr)
        self.assertIn("sw-no-such-command-xyz", r.stderr)

    def test_stdin_reaches_the_command(self):
        r = self.as_sh(self.code, "sh1ny", "cat", stdin="from the caller\n")
        self.assertEqual((r.returncode, r.stdout), (0, "from the caller\n"), r.stderr)

    def test_exit_codes(self):
        self.assertEqual(self.as_sh(self.code).returncode, 1)
        self.assertRegex(self.as_sh(self.code).stderr, USAGE)
        r = self.as_sh(self.code, "sh1ny")
        self.assertEqual(r.returncode, 2)
        self.assertRegex(r.stderr, NO_COMMAND)
        self.assertEqual(self.as_sh(self.code, "--resolve", "extra").returncode, 2)
        refused = self.as_sh(self.code, "sh1ny", "git", "-C", str(self.store), "status")
        self.assertEqual(refused.returncode, 3, refused.stderr)
        self.assertEqual(self.as_sh(self.code, "sh1ny", *self.bash_command("exit 7")).returncode, 7)

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

class TestGhRepo(ShimCase):
    """`sw as` keeps an inherited GH_REPO out of the command it fences and out of its own lookups (github-identity)."""

    def seed_pull(self, slug="o/r", n=5):
        pull = {"number": n, "html_url": f"https://github.com/{slug}/pull/{n}", "state": "open", "merged_at": None,
                "title": f"t{n}", "body": "", "created_at": "2026-10-08T10:00:00Z",
                "head": {"ref": "feat/a", "label": "o:feat/a", "sha": f"{n:040x}", "repo": {"full_name": slug}},
                "base": {"ref": "main"}}
        self.state(user="sh1ny", tokens={"sh1ny": "tok-s", "KintsugiBot": "tok-k"}, repos={slug: {"pulls": [pull]}})

    def sw_as(self, cwd, *args):
        """`<sw> as <args>` with ordinary arguments and GH_REPO naming another repository."""
        return subprocess.run([swharness.require_sw(), "as", *args], cwd=cwd, env={**self.env(), "GH_REPO": "other/repo"},
                              capture_output=True, text=True, encoding="utf-8", timeout=60)

    def assert_no_gh_repo(self):
        calls = self.gh_calls()
        self.assertTrue(calls)
        for c in calls:
            self.assertIsNone(c["gh_repo"], f"GH_REPO reached gh {c['argv']}")

    def test_gh_repo_kept_out_of_fenced_command(self):
        self.seed_pull()
        r = self.sw_as(self.code, "sh1ny", "gh", "pr", "view", "5", "--repo", "o/r")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("https://github.com/o/r/pull/5", r.stdout)
        self.assertTrue([c for c in self.gh_calls() if c["argv"][0] == "pr"], "the fenced gh ran")
        self.assert_no_gh_repo()  # the fenced command and the fence's own lookups

    def test_fenced_call_without_repo_uses_cwd_remote(self):
        self.seed_pull()
        self.git(self.code, "remote", "set-url", "origin", "https://github.com/o/r.git")
        r = self.sw_as(self.code, "sh1ny", "gh", "pr", "view", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("https://github.com/o/r/pull/5", r.stdout)
        self.assert_no_gh_repo()


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
            p = subprocess.Popen(swcall.argv(["as", "KintsugiBot", *self.bash_command('touch "$1"', marker.as_posix())]),
                                 cwd=self.code, stdout=fo, stderr=fe, env=e)
            try:
                rc = p.wait(timeout=45)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True) if os.name == "nt" else p.kill()
                p.wait()
                rc = -9
        self.assertEqual(rc, 3, err.read_text(errors="replace"))
        self.assertRegex(err.read_text(errors="replace"), HUNG_LOOKUP)
        self.assertLess(time.time() - t, self.DEADLINE + 10)
        self.assertFalse(marker.exists(), "the fenced command must not run")

    def test_bounded_caller_stops_the_fenced_tree(self):
        late = self.tmp / "late"
        sw = swharness.require_sw()
        e = {**self.env(), "SPECWRIGHT_NET_DEADLINE": str(self.DEADLINE)}
        command = [sw, "run", "--bounded", "--", sw, "as", "sh1ny",
                   *self.bash_command('sleep 8; touch "$1"', late.as_posix())]
        t = time.time()
        r = subprocess.run(command, cwd=self.code, env=e, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 124, r.stdout + r.stderr)
        self.assertLess(time.time() - t, self.DEADLINE + 10)
        time.sleep(9)  # long enough for a command that was left running to finish
        self.assertFalse(late.exists(), "the fenced command outlived its bounded caller")

    @unittest.skipIf(os.name == "nt", "platform: POSIX signals")
    def test_sigterm_reaches_the_command(self):
        ready, term = self.tmp / "ready", self.tmp / "term"
        script = f'trap \'touch "{term.as_posix()}"; exit 0\' TERM; touch "{ready.as_posix()}"; while :; do sleep 0.2; done'
        p = subprocess.Popen(swcall.argv(["as", "sh1ny", *self.bash_command(script)]), cwd=self.code, env=self.env(),
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
