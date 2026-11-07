"""Differential eval (native-cli-pr-io D12): the frozen oracle copies of as.sh, pr-snapshot.sh and pr-reply.sh
(evals/pr-pair/oracle/) and the tree's three scripts run the same cases against the same fake-gh state, and must print the same
stdout bytes and stderr bytes, exit with the same code, leave the same fake-gh state and make the same gh calls.

Before the port the tree's scripts are the oracle's twins, so this passes; after it, it proves the `sw` behind the shims.
The oracle is test-only and ships nowhere; ORACLE_SW_DIR points its helpers (bounded.py, reviewers.py) at the tree's scripts
directory. native-cli-retire-scripts deletes it together with the shims.

Each script runs from a stamped directory with SPECWRIGHT_HOME set, so the shims find the CI-built `sw`.

Run: python -m unittest evals/pr-pair/test_parity.py
"""
import json
import os
import re
import stat
import subprocess
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "skills" / "specwright-pr" / "scripts"
ORACLE = HERE / "oracle"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
sys.path.insert(0, str(ROOT / "evals" / "git-workflow"))
sys.path.append(str(ROOT / "evals"))
import snapfix  # noqa: E402
from snapfix import SnapCase, T0, fake_gh, fixtures, rev  # noqa: E402
import bashexe  # noqa: E402
import test_as_sh as tas  # noqa: E402  module attributes only: its test classes are not collected here
import vcs_test_support  # noqa: E402

SECRET = tas.SECRET


def setUpModule():
    snapfix.banner()


def run_script(script, args, env, cwd, stdin=None):
    """(exit code, stdout bytes, stderr bytes) of `bash <script> <args>`."""
    r = subprocess.run([bashexe.bash(), str(script), *map(str, args)], cwd=cwd, env=env, input=stdin,
                       capture_output=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


def calls_of(log, keep):
    """The fake gh's call log as a list of keep(entry), then the log is removed."""
    out = []
    if log.exists():
        out = [keep(json.loads(l)) for l in log.read_text(encoding="utf-8").splitlines()]
        log.unlink()
    return out


def temp_names(argv):
    """argv with the random part of an mktemp name blanked: two runs never draw the same one."""
    return [re.sub(r"tmp\.[A-Za-z0-9]+", "tmp.X", a) for a in argv]


def said(stderr):
    """stderr with bash's `<script path>: line N:` prefix cut to the script's name: the path and the line differ by design."""
    return re.sub(rb"(?m)^.*?([a-z-]+\.sh): line \d+: ", rb"\1: line N: ", stderr)


class ParityAsserts:
    def assertParity(self, pair, code=None):
        new, old = pair
        self.assertEqual(new["stdout"], old["stdout"], "stdout bytes differ between the script and the oracle")
        self.assertEqual(said(new["stderr"]), said(old["stderr"]), "stderr bytes differ between the script and the oracle")
        self.assertEqual(new["code"], old["code"], "exit codes differ between the script and the oracle")
        self.assertEqual(new["calls"], old["calls"], "the gh calls differ between the script and the oracle")
        self.assertEqual(new["state"], old["state"], "the fake gh state differs after the run")
        if code is not None:  # the case really ran what it names, not a broken fixture
            self.assertEqual(old["code"], code, old["stdout"] + old["stderr"])


class PrParity(SnapCase, ParityAsserts):
    """pr-snapshot.sh and pr-reply.sh against their oracle copies."""

    def setUp(self):
        super().setUp()
        self.home = vcs_test_support.sw_home()
        vcs_test_support.stamp_version(self.tmp)  # the shim's project is its current directory

    def one(self, script, args, which, login, env, stdin=None):
        extra = {"SPECWRIGHT_HOME": str(self.home), "SPECWRIGHT_STATE_DIR": str(self.tmp / f"state-{which}"), **(env or {})}
        if which == "old":
            extra["ORACLE_SW_DIR"] = fixtures.posix(SCRIPTS)
        e = self.env(login, **extra)
        code, out, err = run_script((ORACLE if which == "old" else SCRIPTS) / script, args, e, self.tmp, stdin)
        return {"code": code, "stdout": out, "stderr": err,
                "calls": calls_of(self.gh_log, lambda c: temp_names(c["argv"])), "state": self.gh_state.read_bytes()}

    def pair(self, script, *args, login="me", env=None):
        """(the tree's script, the oracle) on the same fake-gh state: the state is put back before the second run."""
        before = self.gh_state.read_bytes()
        calls_of(self.gh_log, lambda c: c)
        new = self.one(script, args, "new", login, env)
        self.gh_state.write_bytes(before)
        old = self.one(script, args, "old", login, env)
        self.gh_state.write_bytes(before)
        return new, old

    def snapshot_pair(self, *args, **kw):
        return self.pair("pr-snapshot.sh", self.PR, "--repo", self.SLUG, *args, **kw)

    def body(self, text="done"):
        f = self.tmp / "body.md"
        f.write_text(text, encoding="utf-8", newline="\n")
        return fixtures.posix(f)

    def reply_pair(self, *args, repo=True, **kw):
        return self.pair("pr-reply.sh", self.PR, *args, *(["--repo", self.SLUG] if repo else []), **kw)

    def rev_of(self, c):
        return f"{c['databaseId']}@{c['lastEditedAt'] or c['createdAt']}"


class SnapshotParity(PrParity):
    def rich(self):
        """Threads (open, handled and resolved, rev-bound), comments, reviews, reactions and clipped bodies."""
        tid, c = self.add_thread("rev", "please fix this")
        self.advance(5)
        self.add_reply(tid, "me", f"ack\n\n<!-- specwright:handled {tid} rev={self.rev_of(c)} -->")
        tid2, c2 = self.add_thread("rev", "second finding", path="b.py", line=4)
        self.advance(5)
        self.add_reply(tid2, "me", f"done\n\n<!-- specwright:handled {tid2} resolve -->")
        self.mutate(lambda st: next(t for t in st["repos"]["o/n"]["pulls"][0]["threads"] if t["id"] == tid2).update(isResolved=True))
        self.add_thread("rev", "x" * 3000 + " <!-- hidden --> tail", path="c.py", line=9)  # clipped at 2500
        ic = self.add_comment("rev", "ping")
        self.add_comment("rev", "y" * 1500)  # clipped at 1200
        ic3 = self.add_comment("rev", "handled one")
        self.add_comment("me", f"ok\n\n<!-- specwright:handled {ic3['node_id']} -->")
        self.add_comment("rev", "waiting one")
        self.advance(5)
        self.edit(ic["node_id"], "ping, edited")
        self.react(ic["node_id"], "me")
        self.add_review("rev", "overall: " + "z" * 1300, state="CHANGES_REQUESTED")
        self.add_review("other", "fine", state="APPROVED")
        self.set_checks([{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"},
                         {"name": "lint", "status": "IN_PROGRESS", "conclusion": None}])

    def test_snapshot_with_threads_comments_reviews_markers_and_reactions(self):
        self.rich()
        self.assertParity(self.snapshot_pair(), 0)

    def test_snapshot_of_an_empty_pr(self):
        self.assertParity(self.snapshot_pair(), 0)

    def test_snapshot_with_a_cut_off_list(self):
        def many(st):
            for i in range(101):
                fake_gh.add_pr_comment(st, self.SLUG, self.PR, "rev", f"comment {i}")
        self.mutate(many)
        new, old = self.snapshot_pair()
        self.assertParity((new, old), 0)
        self.assertFalse(json.loads(old["stdout"])["complete"], "the list must really be cut off")

    def test_snapshot_logs_and_a_pr_url(self):
        self.rich()
        url = f"https://github.com/{self.SLUG}/pull/{self.PR}"
        self.assertParity(self.pair("pr-snapshot.sh", url, "--logs"), 0)

    def test_snapshot_refusals_exit_2_alike(self):
        for args in (["--reviewer", "a:b:3"], ["--bogus"], ["--until", "quiet"], ["--interval", "0"]):
            with self.subTest(args=args):
                self.assertParity(self.pair("pr-snapshot.sh", self.PR, "--repo", self.SLUG, *args), 2)

    def test_snapshot_full_without_a_node_id_exits_1_alike(self):
        self.assertParity(self.pair("pr-snapshot.sh", self.PR, "--repo", self.SLUG, "--full"), 1)

    def test_snapshot_gh_failure(self):
        self.mutate(lambda st: st.update({"fail": [{"match": "graphql", "exit": 1, "stderr": "boom"}]}))
        new, old = self.snapshot_pair()
        self.assertParity((new, old))
        self.assertNotEqual(old["code"], 0)

    def test_full_for_each_kind(self):
        tid, c = self.add_thread("rev", "thread body <!-- c --> and more")
        ic = self.add_comment("rev", "comment body " + "q" * 1500)
        rv = self.add_review("rev", "review body", state="COMMENTED")
        for kind, node in (("thread_comment", c["id"]), ("comment", ic["node_id"]), ("review", rv["id"])):
            with self.subTest(kind=kind):
                new, old = self.pair("pr-snapshot.sh", "--full", node, "--repo", self.SLUG)
                self.assertParity((new, old), 0)
                self.assertEqual(json.loads(old["stdout"])["kind"], kind)

    def test_full_not_found(self):
        new, old = self.pair("pr-snapshot.sh", "--full", "MDNot_Found_1=", "--repo", self.SLUG)
        self.assertParity((new, old), 1)
        self.assertIn("not_found", old["stdout"].decode("utf-8"))

    def test_full_unreadable_exits_3(self):
        self.mutate(lambda st: st.update({"fail": [{"match": "node\\(id", "exit": 1, "stderr": "boom"}]}))
        self.assertParity(self.pair("pr-snapshot.sh", "--full", "MDNode1=", "--repo", self.SLUG), 3)

    def test_reviewer_config_snapshot(self):
        self.add_activity("a" * 40, T0)
        self.advance(30)
        self.add_comment("genrev", "looks good to me")
        self.add_comment("slowbot", "working on it")
        cfg = self.cfg(rev("genrev"), rev("slowbot", timeout=60), rev("silent", role="advisory", timeout=20))
        new, old = self.snapshot_pair(*cfg)
        self.assertParity((new, old), 0)
        self.assertEqual(len(json.loads(old["stdout"])["reviewers"]), 3, "the evaluator really ran")

    def test_bad_reviewer_config_exits_2_before_gh(self):
        bad = self.tmp / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        for path in (fixtures.posix(bad), fixtures.posix(self.tmp / "missing.json")):
            with self.subTest(path=path):
                new, old = self.snapshot_pair("--reviewer-config", path)
                self.assertParity((new, old), 2)
                self.assertEqual(old["calls"], [], "no gh call before the config check")

    @unittest.skipUnless(sys.platform.startswith("linux"), "a file name that is not UTF-8 needs Linux")
    def test_config_name_with_a_non_utf8_byte_for_the_check_and_the_evaluation(self):
        name = os.fsdecode(b"reviewers-\xff.json")
        good = self.write_config(rev("genrev"), name=name)
        self.add_activity("a" * 40, T0)
        self.add_comment("genrev", "looks good")
        new, old = self.snapshot_pair("--reviewer-config", good)  # the evaluation
        self.assertParity((new, old), 0)
        self.assertEqual(json.loads(old["stdout"])["reviewers"][0]["login"], "genrev")
        bad = self.tmp / os.fsdecode(b"bad-\xff.json")
        bad.write_text("{not json", encoding="utf-8")
        new, old = self.snapshot_pair("--reviewer-config", fixtures.posix(bad))  # the check
        self.assertParity((new, old), 2)
        self.assertIn(b"\xff", old["stderr"], "the check names the file by its bytes")


class ReplyParity(PrParity):
    def thread_case(self):
        tid, c = self.add_thread("rev", "please fix")
        return tid, c

    def test_thread_reply_resolves_and_reacts(self):
        tid, c = self.thread_case()
        self.assertParity(self.reply_pair("thread", tid, c["databaseId"], self.body(), "--resolve", "--react", "+1"), 0)

    def test_thread_reply_with_a_matching_rev(self):
        tid, c = self.thread_case()
        self.assertParity(self.reply_pair("thread", tid, c["databaseId"], self.body(), "--resolve", "--rev", self.rev_of(c)), 0)

    def test_thread_reply_with_a_stale_rev(self):
        tid, c = self.thread_case()
        judged = self.rev_of(c)
        self.advance(30)
        self.edit(c["id"], "please fix, actually this")
        self.assertParity(self.reply_pair("thread", tid, c["databaseId"], self.body(), "--resolve", "--rev", judged), 5)

    def test_comment_reply_with_matching_and_stale_rev(self):
        ic = self.add_comment("rev", "ping")
        judged = self.snapshot()["comments"][0]["rev"]
        self.assertParity(self.reply_pair("comment", ic["node_id"], self.body(), "--rev", judged, "--react", "-1"), 0)
        self.advance(10)
        self.edit(ic["node_id"], "ping, edited")
        self.assertParity(self.reply_pair("comment", ic["node_id"], self.body(), "--rev", judged), 5)

    def test_review_reply_waiting(self):
        rv = self.add_review("rev", "looks off", state="CHANGES_REQUESTED")
        self.assertParity(self.reply_pair("comment", rv["id"], self.body(), "--waiting"), 0)

    def test_react_alone(self):
        tid, c = self.thread_case()
        self.assertParity(self.reply_pair("react", c["id"], "+1"), 0)

    def test_resolve_with_matching_and_stale_rev(self):
        tid, c = self.thread_case()
        self.assertParity(self.reply_pair("resolve", tid, "--rev", self.rev_of(c)), 0)
        self.advance(10)
        self.edit(c["id"], "changed")
        self.assertParity(self.reply_pair("resolve", tid, "--rev", "1@2020-01-01T00:00:00Z"), 5)

    def test_pending_review_exits_2(self):
        tid, c = self.thread_case()
        self.add_review("me", "draft", state="PENDING")
        self.assertParity(self.reply_pair("thread", tid, c["databaseId"], self.body()), 2)

    def test_refused_before_any_gh_call_exits_4(self):
        tid, c = self.thread_case()
        for args in (("thread", tid, c["databaseId"], fixtures.posix(self.tmp / "missing.md")),
                     ("thread", tid, c["databaseId"], self.body(), "--react", "x"),
                     ("thread", tid, c["databaseId"], self.body(), "--waiting", "--resolve")):
            with self.subTest(args=args[3:]):
                new, old = self.reply_pair(*args)
                self.assertParity((new, old), 4)
                self.assertEqual(old["calls"], [])

    def test_failed_resolution_prints_the_retry_line(self):
        tid, c = self.thread_case()
        self.mutate(lambda st: st.update({"fail": [{"match": "resolveReviewThread", "exit": 1, "stderr": "boom"}]}))
        self.assertParity(self.reply_pair("thread", tid, c["databaseId"], self.body(), "--resolve"), 1)


class WatcherTakeover(PrParity):
    """C6: the claim directory is shared, so a newer watcher of one implementation ends an older one of the other."""

    def setUp(self):
        super().setUp()
        sleep = self.tmp / "bin" / "sleep"
        sleep.write_text(f'#!/bin/sh\nexec "{fixtures.posix(sys.executable)}" -c "import time; time.sleep(0.3)"\n',
                         encoding="utf-8", newline="\n")
        sleep.chmod(sleep.stat().st_mode | stat.S_IXUSR)
        self.procs = []
        self.addCleanup(self._reap)

    def _reap(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.communicate()

    def start(self, which, timeout):
        script = (ORACLE if which == "old" else SCRIPTS) / "pr-snapshot.sh"
        env = self.env(SPECWRIGHT_HOME=str(self.home), SPECWRIGHT_STATE_DIR=str(self.state_dir),
                       **({"ORACLE_SW_DIR": fixtures.posix(SCRIPTS)} if which == "old" else {}))
        p = subprocess.Popen([bashexe.bash(), str(script), str(self.PR), "--repo", self.SLUG, "--wait", "--interval", "1",
                              "--timeout", str(timeout)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             encoding="utf-8", env=env, cwd=self.tmp)
        self.procs.append(p)
        return p

    def until(self, cond, what):
        end = time.time() + 60
        while time.time() < end:
            if cond():
                return
            time.sleep(0.05)
        self.fail(f"timed out waiting for {what}")

    def test_shim_watcher_takes_over_oracle_watcher(self):
        a = self.start("old", 60)
        self.until(lambda: self.gh_log.exists() and self.gh_log.stat().st_size > 0, "the oracle watcher's first snapshot")
        b = self.start("new", 3)
        out_a, err_a = a.communicate(timeout=90)
        self.assertEqual(a.returncode, 4, err_a)
        self.assertIn("took over", err_a)
        out_b, err_b = b.communicate(timeout=90)
        self.assertEqual(b.returncode, 0, err_b)
        self.assertEqual(json.loads(out_b.strip().splitlines()[-1])["wake"], "timeout")


class AsParity(tas.AsShCase, ParityAsserts):
    """as.sh against its oracle copy, in a repo whose origin is github.com."""

    def setUp(self):
        super().setUp()
        self.home = vcs_test_support.sw_home()
        self.work = self.repo("work")
        self.git(self.work, "remote", "set-url", "origin", "https://github.com/o/r.git")
        self.git(self.work, "config", "http.proxy", self.base.rstrip("/"))
        vcs_test_support.stamp_version(self.work)

    def pair(self, *args, cwd=None, env=None, stdin=None, mask=None):
        """(as.sh, oracle) in `cwd` (the work repo): a dict per run. `mask` is a text replaced by *** in stdout and stderr."""
        out = []
        before = (self.tmp / "gh-state.json").read_bytes()
        for which in ("new", "old"):
            e = self.env()
            e.update({"SPECWRIGHT_HOME": str(self.home), **(env or {})})
            if which == "old":
                e["ORACLE_SW_DIR"] = fixtures.posix(SCRIPTS)
            Recorder = tas.Recorder
            Recorder.seen = []
            calls_of(self.tmp / "gh-log.jsonl", lambda c: c)
            code, so, se = run_script((ORACLE if which == "old" else SCRIPTS) / "as.sh", args, e, cwd or self.work, stdin)
            if mask:
                so, se = so.replace(mask.encode(), b"***"), se.replace(mask.encode(), b"***")
            out.append({"code": code, "stdout": so, "stderr": se, "state": (self.tmp / "gh-state.json").read_bytes(),
                        "calls": calls_of(self.tmp / "gh-log.jsonl", lambda c: (temp_names(c["argv"]), c["env"])),
                        "requests": list(Recorder.seen)})
        self.assertEqual(out[0]["requests"], out[1]["requests"], "the requests that reached the server differ")
        self.assertEqual(before, out[0]["state"])
        return out[0], out[1]

    def test_resolve(self):
        self.assertParity(self.pair("--resolve"), 0)
        self.state(tokens={})
        self.assertParity(self.pair("--resolve"), 3)
        self.state(user="sh1ny", tokens={"sh1ny": "tok-s"})
        self.assertParity(self.pair("--resolve", "extra"), 2)

    def test_identity_mismatch_and_missing_credential(self):
        self.state(user="sh1ny", tokens={"sh1ny": "tok-s", "KintsugiBot": "tok-s"})
        self.assertParity(self.pair("KintsugiBot", "gh", "api", "user", "--jq", ".login"), 3)
        self.state(user="KintsugiBot", tokens={"KintsugiBot": "tok-k"})
        self.assertParity(self.pair("sh1ny", "gh", "api", "user"), 3)

    def test_usage_exits(self):
        self.assertParity(self.pair("sh1ny"), 2)

    def test_a_configured_login_that_is_not_the_active_one(self):
        self.assertParity(self.pair("KintsugiBot", "gh", "api", "user", "--jq", ".login"), 0)

    def test_userinfo_refusals(self):
        other = self.repo("other")
        self.git(other, "remote", "set-url", "origin", f"https://x-access-token:{SECRET}@github.com/o/r.git")
        cases = {
            "fetch url": ([("remote", "set-url", "origin", f"https://x-access-token:{SECRET}@github.com/o/r.git")],
                          ("git", "fetch", "origin", "main")),
            "second push url": ([("config", "--add", "remote.origin.pushurl", "https://github.com/o/r.git"),
                                 ("config", "--add", "remote.origin.pushurl", f"https://u:{SECRET}@github.com/o/r.git")],
                                ("git", "push", "origin", "HEAD")),
            "insteadof rule": ([("config", f"url.https://u:{SECRET}@github.com/.insteadOf", "https://github.com/")],
                               ("git", "fetch", "origin", "main")),
            "rule without a matching remote": ([("remote", "set-url", "origin", "https://git.example.com/o/r.git"),
                                                ("config", f"url.https://u:{SECRET}@github.com/.pushInsteadOf", "https://github.com/")],
                                               ("git", "status")),
            "username slot": ([("remote", "set-url", "origin", f"https://{SECRET}@github.com/o/r.git")], ("git", "fetch", "origin")),
            "bare username": ([("remote", "set-url", "origin", "https://someone@github.com/o/r.git")], ("git", "fetch", "origin")),
            "trailing dot": ([("remote", "set-url", "origin", f"https://u:{SECRET}@GitHub.COM./o/r.git")], ("git", "fetch", "origin")),
            "another command": ([("remote", "set-url", "origin", f"https://{SECRET}@github.com/o/r.git")], ("gh", "api", "repos/o/r/pulls")),
            "git -C": ([], ("git", "-C", str(other), "fetch", "origin")),
            "git --git-dir=": ([], ("git", f"--git-dir={other / '.git'}", "fetch", "origin")),
            "git -c rule": ([], ("git", "-c", f"url.https://u:{SECRET}@github.com/.insteadOf=https://github.com/", "status")),
            "git -c url": ([], ("git", "-c", f"remote.origin.url=https://u:{SECRET}@github.com/o/r.git", "fetch", "origin")),
            "url argument": ([], ("git", "ls-remote", f"https://u:{SECRET}@github.com/o/r.git")),
            "url in a value": ([], ("git", "ls-remote", f"--upload-pack=x", f"https://u:{SECRET}@GITHUB.com:443/o/r.git")),
            "but -C": ([], ("but", "-C", str(other), "pull")),
            "but other subcommand": ([], ("but", "status")),
            "jj -R": ([], ("jj", "-R", str(other), "git", "push")),
            "jj other subcommand": ([], ("jj", "log")),
            "jj --config": ([], ("jj", "git", "push", "--config", "x=y")),
        }
        for name, (git_steps, command) in cases.items():
            with self.subTest(name):
                work = self.repo(f"w-{len(name)}-{abs(hash(name)) % 1000}")
                self.git(work, "remote", "set-url", "origin", "https://github.com/o/r.git")
                self.git(work, "config", "http.proxy", self.base.rstrip("/"))
                vcs_test_support.stamp_version(work)
                for step in git_steps:
                    self.git(work, *step)
                new, old = self.pair("sh1ny", *command, cwd=work, mask=SECRET)
                self.assertParity((new, old), 3)
                self.assertIn(b"refusing", old["stderr"])

    def test_a_lookalike_host_and_the_credential_helper(self):
        self.git(self.work, "remote", "set-url", "origin", f"https://u:{SECRET}@github.com.example.org/o/r.git")
        self.assertParity(self.pair("sh1ny", "gh", "api", "user", "--jq", ".login"), 0)
        for host in ("github.com", "github.com.:443", "GitHub.COM.", "github.com.example.org"):
            with self.subTest(host=host):
                self.assertParity(self.pair("sh1ny", "git", "credential", "fill", stdin=f"protocol=https\nhost={host}\n\n".encode()))

    def test_env_under_the_fence_with_the_token_masked(self):
        env = {"GH_HOST": "corp.example", "GH_ENTERPRISE_TOKEN": "ent-tok", "GITHUB_ENTERPRISE_TOKEN": "ent-tok2",
               "GH_TOKEN": "amb", "GITHUB_TOKEN": "amb", "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.x",
               "GIT_CONFIG_VALUE_0": "y"}
        self.git(self.work, "config", f"http.{self.base}.extraheader", "X-A: 1")
        self.git(self.work, "config", f"http.https://example.com/.extraheader", "X-B: 2")
        new, old = self.pair("sh1ny", "env", env=env, mask="tok-s")
        # the oracle alone is told where its helpers are, through this variable
        old = dict(old, stdout=b"".join(l for l in old["stdout"].splitlines(True) if not l.startswith(b"ORACLE_SW_DIR=")))
        # the order of an environment dump follows how each program built the block, not what it holds: compare the sets
        # (a Windows environment has one variable for NO_PROXY and no_proxy, which the fixture sets both: the two programs keep a different spelling)
        dump = lambda out: sorted(l for l in out.splitlines() if l.split(b"=", 1)[0].lower() != b"no_proxy")
        self.maxDiff = None
        self.assertEqual(set(dump(new["stdout"])) ^ set(dump(old["stdout"])), set())
        self.assertParity((dict(new, stdout=b""), dict(old, stdout=b"")), 0)
        self.assertNotIn(b"tok-s", new["stdout"] + new["stderr"])
        names = {l.split(b"=", 1)[0] for l in old["stdout"].splitlines()}
        for v in (b"GIT_CONFIG_COUNT", b"AS_SH_ORIG_SET", b"AS_SH_ORIG_GH_HOST", b"GIT_SSH_COMMAND"):
            self.assertIn(v, names)
        self.assertNotIn(b"GH_HOST", names)

    def test_nested_fence_keeps_the_outer_originals(self):
        env = {"GH_HOST": "corp.example"}
        new, old = self.pair("sh1ny", "bash", str(SCRIPTS / "as.sh"), "sh1ny", "bash", "-c",
                             'printf "%s|%s|%s" "$AS_SH_ORIG_GH_HOST" "${GH_HOST-unset}" "$AS_SH_ORIG_SET"', env=env)
        self.assertEqual(new["stdout"], old["stdout"])
        self.assertEqual(new["code"], old["code"])

    def test_the_command_exit_status_and_stdout_pass_through(self):
        self.assertParity(self.pair("sh1ny", "bash", "-c", 'printf %s "$1"; exit 7', "x", 'a "b" $c'), 7)
        self.assertParity(self.pair("sh1ny", "no-such-tool"), 127)


if __name__ == "__main__":
    unittest.main()
