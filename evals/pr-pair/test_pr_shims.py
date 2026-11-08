"""pr-snapshot.sh and pr-reply.sh are shims (ADR 0028, native-cli-pr-io D10): each finds the project's sw with sw-path.sh and
runs `sw pr snapshot|reply --args-stdin`, handing it this directory, this bash and the whole command line as NUL-terminated
records. The PR logic is pinned by test_pr_snapshot.py, test_pr_reply.py and test_parity.py. These tests cover what the shims
add: how they find `sw`, what they do without one, and that the text of a query reaches gh whole.

They run the real shims against the tree's sw through the test home (snapfix.SnapCase sets SPECWRIGHT_HOME and stamps the
project).

Run: python -m unittest discover evals/pr-pair -p test_pr_shims.py
"""
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

import snapfix
from snapfix import REPLY, ROOT, SCRIPTS, SNAPSHOT, T0, SnapCase, fixtures, rev
import bashexe  # noqa: E402

STOP = "sw missing or mismatched: rerun the install prompt"
PAIR = SCRIPTS / "pr-pair.sh"
ORACLE = ROOT / "evals" / "pr-pair" / "oracle"


def setUpModule():
    snapfix.banner()


class ShimCase(SnapCase):
    def no_sw_env(self):
        """An environment whose test home holds no sw."""
        home = self.tmp / "empty-home"
        home.mkdir(exist_ok=True)
        return {"SPECWRIGHT_HOME": str(home)}

    def stop_document(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_missing"), doc)
        self.assertTrue(doc["message"].startswith(STOP), doc)
        self.assertIn(STOP, result.stderr)
        self.assertEqual(self.gh_calls(), [], "no gh call ran")
        return doc


class TestRunsSw(ShimCase):
    def test_snapshot_runs_sw(self):
        tid, c = self.add_thread("rev", "please fix the loop")
        snap = self.snapshot()
        self.assertEqual([t["id"] for t in snap["threads"]], [tid])
        thread = snap["threads"][0]
        self.assertEqual(thread["rev"], f"{c['databaseId']}@{c['createdAt']}")
        self.assertEqual(thread["comments"][0]["body"], "please fix the loop")

    def test_reply_runs_sw(self):
        tid, c = self.add_thread("rev", "please fix")
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--resolve", body="done\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        thread = self.st()["repos"]["o/n"]["pulls"][0]["threads"][0]
        self.assertTrue(thread["isResolved"])
        self.assertEqual(len(thread["comments"]), 2)
        self.assertEqual(thread["comments"][1]["body"], f"done\n\n\n<!-- specwright:handled {tid} resolve -->\n")

    def test_reply_refusal_keeps_its_exit_status(self):
        r = self.reply("comment", "IC_1", "missing.md")
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertIn("missing.md", r.stderr)
        self.assertEqual(self.gh_calls(), [], "no gh call ran")


class TestWithoutSw(ShimCase):
    def test_reply_without_sw_posts_nothing(self):
        tid, c = self.add_thread("rev", "please fix")
        r = self.reply("comment", "IC_1", "BODY", body="done", env=self.no_sw_env())
        self.stop_document(r)
        self.assertEqual(self.st()["repos"]["o/n"]["pulls"][0]["threads"][0]["comments"][0]["body"], "please fix")
        self.assertEqual(len(self.st()["repos"]["o/n"]["pulls"][0]["threads"][0]["comments"]), 1)

    def test_watch_without_sw_creates_no_claim(self):
        r = self.snapshot_run("--wait", env=self.no_sw_env())
        self.stop_document(r)
        self.assertFalse(self.state_dir.exists(), "no state directory, so no claim file")

    def test_snapshot_without_sw_runs_no_gh(self):
        self.stop_document(self.snapshot_run(env=self.no_sw_env()))

    def test_no_python(self):
        empty = self.tmp / "no-tools"
        empty.mkdir()
        for script, name in ((SNAPSHOT, "pr-snapshot.sh"), (REPLY, "pr-reply.sh")):
            with self.subTest(script=name):
                env = {**self.env(), "PATH": str(empty)}
                r = subprocess.run([bashexe.bash(), str(script), "7"], cwd=self.tmp, env=env, capture_output=True, text=True)
                self.assertEqual((r.returncode, r.stdout), (2, ""), r.stderr)
                self.assertEqual(r.stderr, f"{name}: no_python: needs python 3.8+ for its bounded gh calls\n")
        self.assertEqual(self.gh_calls(), [], "sw did not run")


class TestPairShim(ShimCase):
    """pr-pair.sh dispatches identity, vcs, tier, context and policy to `sw pr <sub> --args-stdin` after its Python probe (D2,
    C5); every other first argument, none included, runs the embedded program as before."""

    def pair_run(self, *args, cwd=None, env=None):
        return self.run_script(PAIR, *args, cwd=cwd, env=env)

    def make_repo(self, name, origin=None, settings=None, stamp=True):
        d = self.tmp / name
        d.mkdir()
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        for args in (("init", "-q", "-b", "main"), ("config", "user.name", "Eval Bot"), ("config", "user.email", "eval@example.invalid")):
            subprocess.run(["git", *args], cwd=d, check=True, capture_output=True, env=env)
        if origin:
            subprocess.run(["git", "remote", "add", "origin", origin], cwd=d, check=True, capture_output=True, env=env)
        if settings is not None:
            (d / "openspec").mkdir(exist_ok=True)
            (d / "openspec" / "specwright.yaml").write_text(settings, encoding="utf-8", newline="\n")
        if stamp:
            snapfix.vcs_test_support.stamp_version(d)
        return d

    def one_line(self, result):
        lines = result.stdout.strip().splitlines()
        self.assertEqual(len(lines), 1, f"want one JSON line: {result.stdout!r} / {result.stderr!r}")
        return json.loads(lines[0])

    def test_context_runs_sw(self):
        code = self.make_repo("code", origin="https://github.com/acme/code.git",
                              settings="github:\n  login: me\npr:\n  reviewers:\n    rev:\n      role: required\n")
        r = self.pair_run("context", "--code", fixtures.posix(code))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = self.one_line(r)
        self.assertTrue(doc["ok"])
        self.assertEqual((doc["code"]["login"], doc["code"]["main"], doc["code"]["repo"]), ("me", "main", "acme/code"))
        config = Path(doc["code"]["reviewer_config"])
        self.assertTrue(config.is_file(), "the reviewer config was written")
        self.assertIn('"format":2', config.read_text(encoding="utf-8"), "sw wrote it: the Python script wrote format 1")
        self.assertEqual(self.gh_calls(), [])

    def test_context_finds_sw_from_code_not_the_cwd(self):
        # D2: the project is the directory --code names when it is one, else the current directory
        code = self.make_repo("code", origin="https://github.com/acme/code.git", settings="github:\n  login: me\n")
        elsewhere = self.make_repo("elsewhere", stamp=False)
        self.assertFalse((elsewhere / "openspec" / ".specwright" / "VERSION").exists())
        r = self.pair_run("context", "--code", fixtures.posix(code), cwd=elsewhere)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = self.one_line(r)
        self.assertEqual((doc["ok"], doc["code"]["repo"]), (True, "acme/code"))

    def test_discover_keeps_the_script(self):
        self.mutate(lambda st: st["repos"].update({"o/r": {"pulls": []}}))
        args = ("discover", "--repo", "o/r", "--branch", "feat/a")
        with_sw = self.pair_run(*args)
        self.assertEqual(with_sw.returncode, 0, with_sw.stdout + with_sw.stderr)
        doc = self.one_line(with_sw)
        self.assertTrue(doc["ok"], doc)
        self.assertTrue(self.gh_calls(), "the embedded program asked GitHub")
        without_sw = self.pair_run(*args, env=self.no_sw_env())
        self.assertEqual((without_sw.returncode, without_sw.stdout), (0, with_sw.stdout))
        self.assertNotIn("sw_missing", without_sw.stdout)

    def test_identity_of_a_store_from_the_code_checkout(self):
        code = self.make_repo("code", origin="https://github.com/acme/code.git")
        store = self.make_repo("store", origin="git@github.com:acme/plans.git", stamp=False)
        self.assertFalse((store / "openspec" / ".specwright" / "VERSION").exists())
        r = self.pair_run("identity", fixtures.posix(store), cwd=code)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = self.one_line(r)
        self.assertEqual((doc["ok"], doc["repo"], doc["owner"], doc["name"]), (True, "acme/plans", "acme", "plans"))
        # from inside the store checkout there is no sw to find: the shim stops, as as.sh does
        r = self.pair_run("identity", fixtures.posix(store), cwd=store)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self.one_line(r)["error"], "sw_missing")

    def test_pr_pair_without_subcommand_lists_all_19(self):
        for env in (None, self.no_sw_env()):
            with self.subTest(sw=env is None):
                r = self.pair_run(env=env)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                doc = self.one_line(r)
                self.assertEqual((doc["ok"], doc["error"]), (False, "usage"))
                names = doc["message"].split(": ", 1)[1].split(" | ")
                self.assertEqual(len(names), 19, names)
                self.assertEqual(len(set(names)), 19)
                for sub in ("identity", "vcs", "tier", "context", "policy", "discover", "branch-check"):
                    self.assertIn(sub, names)
        unknown = self.pair_run("bogus")
        self.assertEqual(unknown.returncode, 2)
        self.assertEqual(self.one_line(unknown)["error"], "usage")

    def test_policy_without_sw_runs_no_gh(self):
        snap = self.tmp / "snap.json"
        snap.write_text("{}", encoding="utf-8")
        r = self.pair_run("policy", "--repo", "o/r", "--head", "a" * 40, "--snapshot", f"code={fixtures.posix(snap)}",
                          env=self.no_sw_env())
        doc = self.stop_document(r)
        self.assertEqual(doc["ok"], False)
        self.assertFalse(self.state_dir.exists(), "no reviewer config was written")

    def test_branch_check_without_sw_answers(self):
        code = self.make_repo("code", origin="https://github.com/acme/code.git")
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "c"], cwd=code, check=True, capture_output=True, env=env)
        subprocess.run(["git", "branch", "feat/a"], cwd=code, check=True, capture_output=True, env=env)
        r = self.pair_run("branch-check", "--dir", fixtures.posix(code), "--branch", "feat/a", "--main", "main",
                          env=self.no_sw_env())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = self.one_line(r)
        self.assertEqual((doc["ok"], doc["delete"], doc["reason"]), (True, True, "on_main"))

    def test_pr_pair_no_python_runs_no_sw(self):
        code = self.make_repo("code", origin="https://github.com/acme/code.git", settings="github:\n  login: me\n")
        empty = self.tmp / "no-tools"
        empty.mkdir()
        for sub in ("context", "policy", "identity", "vcs", "tier"):
            with self.subTest(sub=sub):
                args = {"identity": [fixtures.posix(code)], "policy": ["--repo", "o/r", "--head", "a" * 40]}.get(
                    sub, ["--code", fixtures.posix(code)])
                r = subprocess.run([bashexe.bash(), str(PAIR), sub, *args], cwd=self.tmp, env={**self.env(), "PATH": str(empty)},
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                doc = self.one_line(r)
                self.assertEqual((doc["ok"], doc["error"]), (False, "no_python"))
        self.assertFalse(self.state_dir.exists(), "sw did not run: it would have written a reviewer config")
        self.assertEqual(self.gh_calls(), [], "sw did not run")

    def test_header_holds_c5(self):
        header = PAIR.read_text(encoding="utf-8").split("set -euo pipefail", 1)[0]
        self.assertIn("no_python", header)
        self.assertIn("native-cli-retire-scripts", header)


def command_lines():
    """The command line of every running process, one per entry."""
    if os.name == "nt":
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-CimInstance Win32_Process | ForEach-Object { $_.CommandLine }"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    else:
        r = subprocess.run(["ps", "-A", "-o", "args="], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.splitlines()


class TestReviewerConfig(ShimCase):
    def python_log(self):
        """Put a python3 and python on PATH that log their arguments and run the real one; returns the log's path."""
        log = self.tmp / "python-log.txt"
        for name in ("python3", "python"):
            wrapper = self.tmp / "bin" / name
            wrapper.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{fixtures.posix(log)}"\nexec "{fixtures.posix(sys.executable)}" "$@"\n',
                               encoding="utf-8", newline="\n")
            wrapper.chmod(0o755)
        return log

    def test_bad_reviewer_config_exits_2_before_gh(self):
        cfg = self.tmp / "bad.json"
        cfg.write_text("{not json", encoding="utf-8", newline="\n")
        r = self.snapshot_run("--reviewer-config", fixtures.posix(cfg))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("reviewers.py: "), r.stderr)
        self.assertIn("bad.json", r.stderr)
        self.assertIn("not valid JSON", r.stderr)
        self.assertEqual(self.gh_calls(), [], "no gh call ran")

    def test_snapshot_evaluates_reviewers_in_sw(self):
        """The evaluator is `sw pr reviewers`: the states come out right and no python process ran reviewers.py."""
        log = self.python_log()
        self.add_activity("a" * 40, T0)
        self.advance(30)
        self.add_comment("genrev", "looks good to me")
        snap = self.snapshot(*self.cfg(rev("genrev"), rev("silent", role="advisory", timeout=3600)))
        self.assertEqual({x["login"]: x["state"] for x in snap["reviewers"]}, {"genrev": "reported", "silent": "waiting"})
        self.assertRegex(snap["reviewer_config"], "^[0-9a-f]{64}$")
        calls = log.read_text(encoding="utf-8") if log.exists() else ""
        self.assertIn("sys.version_info", calls, "the wrapper was on the path (the version check ran python)")
        self.assertNotIn("reviewers.py", calls, "no python process evaluated the reviewers")

    def test_backtracking_pattern_stops_at_the_deadline(self):
        """ADR 0022: a user pattern runs inside the poll's deadline. `(a+)+$` over a long run of a's and a b never ends in a
        backtracking engine; the limit line names reviewers.py, the poll fails, nothing is left running or on disk."""
        scratch = self.tmp / "scratch"
        scratch.mkdir()
        self.add_activity("a" * 40, T0)
        self.advance(30)
        self.add_comment("genrev", "a" * 64 + "b")
        args = self.cfg(rev("genrev", ignore="(a+)+$"))
        started = time.time()
        r = self.snapshot_run(*args, env={"SPECWRIGHT_NET_DEADLINE": "10", "TMPDIR": fixtures.posix(scratch)})
        took = time.time() - started
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout.strip(), "")
        self.assertIn("bounded: deadline_exceeded: reviewers.py", r.stderr)
        self.assertLess(took, 60, "the evaluation was cut at the deadline")
        self.assertEqual(list(scratch.iterdir()), [], "the material file is gone")
        end = time.time() + 10
        while True:  # the killed evaluator may take a moment to leave the process table
            left = [c for c in command_lines() if "reviewers" in c and str(self.tmp.name) in c]
            if not left or time.time() > end:
                break
            time.sleep(0.5)
        self.assertEqual(left, [], "no evaluator process is left")


class TestQueryTextArrivesWhole(ShimCase):
    """Windows: a native command line cuts or expands what MSYS parses (constraint C16). The query and the jq program travel as
    records on stdin; this checks the fake gh received them byte for byte, the program's `…` and `{`, `*`, `$` included."""

    @staticmethod
    def heredoc(name, tag):
        text = (ORACLE / name).read_text(encoding="utf-8")
        body = text.split(f"<<'{tag}' || true\n", 1)[1].split(f"\n{tag}\n", 1)[0]
        return body.strip()

    def test_snapshot_query_and_jq_arrive_whole(self):
        self.add_thread("rev", "please fix")
        self.snapshot()
        calls = [c for c in self.gh_calls() if any(a.startswith("query=") and "statusCheckRollup" in a for a in c)]
        self.assertEqual(len(calls), 1)
        argv = calls[0]
        query = self.heredoc("pr-snapshot.sh", "GQL")
        shape = self.heredoc("pr-snapshot.sh", "JQ")
        self.assertIn(f"query={query}", argv)
        jq = argv[argv.index("--jq") + 1]
        self.assertTrue(jq.startswith("def cfg:"), jq[:40])
        self.assertTrue(jq.endswith("\n" + shape), "the jq program arrived whole")
        self.assertIn("…[truncated, see url]", jq)


@unittest.skipIf(os.name == "nt", "platform: POSIX signals")
class TestReplySignalCleanup(ShimCase):
    """The script's `trap ... EXIT` removed the reply body file when a signal ended it; `sw pr reply` does the same."""

    def test_sigterm_during_the_post_removes_the_body_file(self):
        import signal
        tid, c = self.add_thread("rev", "please fix")
        hang = self.tmp / "hang"
        hang.mkdir()
        seen = self.tmp / "posting"  # the hung gh's pid, then the body file it was given
        gh = hang / "gh"
        gh.write_text('#!/bin/sh\nfor a in "$@"; do case $a in body=@*)\n'
                      '  printf "%%s\\n%%s\\n" "$$" "${a#body=@}" > "%s.part" && mv "%s.part" "%s"; exec sleep 60;;\n'
                      'esac; done\nexec "%s" "$@"\n'
                      % (fixtures.posix(seen), fixtures.posix(seen), fixtures.posix(seen),
                         fixtures.posix(self.tmp / "bin" / "gh")),
                      encoding="utf-8", newline="\n")
        gh.chmod(0o755)
        body = self.tmp / "body.md"
        body.write_text("done\n", encoding="utf-8", newline="\n")
        env = self.env()
        env["PATH"] = str(hang) + os.pathsep + env["PATH"]
        p = subprocess.Popen([bashexe.bash(), str(REPLY), str(self.PR), "thread", tid, str(c["databaseId"]),
                              fixtures.posix(body), "--repo", self.SLUG], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding="utf-8", env=env, cwd=self.tmp)
        pid = None
        try:
            end = time.time() + 60
            while not seen.exists() and time.time() < end:
                self.assertIsNone(p.poll(), p.stderr.read() if p.poll() is not None else "")
                time.sleep(0.05)
            self.assertTrue(seen.exists(), "the post was never reached")
            pid, posted = seen.read_text(encoding="utf-8").splitlines()
            self.assertTrue(os.path.isfile(posted), f"the body file {posted} exists while the post runs")
            p.send_signal(signal.SIGTERM)
            _, err = p.communicate(timeout=30)
            self.assertEqual(p.returncode, 143, err)
            self.assertFalse(os.path.exists(posted), f"the body file {posted} is removed")
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate()
            if pid:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except (ValueError, ProcessLookupError):
                    pass


@unittest.skipUnless(os.name == "nt", "platform: checks the Git Bash form of HOME, which only Windows has (assumption A3)")
class TestHomeStateBaseOnWindows(ShimCase):
    """A3 (design D9): with no SPECWRIGHT_STATE_DIR and HOME in Git Bash `/c/...` form, the sw watcher claims under
    <HOME>/.cache/specwright/watch/v2/, the directory the old script used, so an old-script watcher sees its claim."""

    def setUp(self):
        super().setUp()
        sleep = self.tmp / "bin" / "sleep"  # short naps, so the old watcher's takeover check comes quickly
        sleep.write_text(f'#!/bin/sh\nexec "{fixtures.posix(sys.executable)}" -c "import time; time.sleep(0.3)"\n',
                         encoding="utf-8", newline="\n")
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.procs = []
        self.addCleanup(self._reap)

    def _reap(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.communicate()

    def start(self, script, **extra):
        env = self.env(HOME=fixtures.msys(self.home), **extra)
        env.pop("SPECWRIGHT_STATE_DIR")
        p = subprocess.Popen([bashexe.bash(), str(script), str(self.PR), "--repo", self.SLUG, "--wait", "--interval", "1",
                              "--timeout", "60"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             encoding="utf-8", env=env, cwd=self.tmp)
        self.procs.append(p)
        return p

    def claims(self):
        base = self.home / ".cache" / "specwright" / "watch" / "v2"
        return sorted(p.name for p in base.rglob("*") if p.is_file()) if base.is_dir() else []

    def wait_for(self, cond, what):
        end = time.time() + 60
        while time.time() < end:
            if cond():
                return
            time.sleep(0.05)
        self.fail(f"timed out waiting for {what}; claims: {self.claims()}")

    def test_home_default_state_base_is_shared_with_the_old_script(self):
        new = self.start(SNAPSHOT)
        self.wait_for(lambda: self.claims(), "the sw watcher's claim under <HOME>/.cache/specwright/watch/v2/")
        first = self.claims()
        self.assertEqual(len(first), 1, first)
        self.assertTrue(first[0].startswith("1-"), first)
        old = self.start(ORACLE / "pr-snapshot.sh", ORACLE_SW_DIR=snapfix.oracle_sw_dir())
        _, err_new = new.communicate(timeout=90)
        self.assertEqual(new.returncode, 4, err_new)  # the old watcher saw the claim and took a higher one
        self.assertIn("took over", err_new)
        self.assertTrue(any(c.startswith("2-") for c in self.claims()), self.claims())
        old.kill()
        old.communicate()


if __name__ == "__main__":
    unittest.main()
