"""Differential eval (native-cli-pr-io D12, native-cli-pr-pair D8): the frozen oracle copies of as.sh, pr-snapshot.sh, pr-reply.sh and
pr-pair.sh (identity, vcs, tier, context, policy)
(evals/pr-pair/oracle/) and the tree's three scripts run the same cases against the same fake-gh state, and must print the same
stdout bytes and stderr bytes, exit with the same code, leave the same fake-gh state and make the same gh calls.

Before the port the tree's scripts are the oracle's twins, so this passes; after it, it proves the `sw` behind the shims.
The oracle is test-only and ships nowhere; ORACLE_SW_DIR points its helpers at a temp directory that holds
the tree's bounded.py, as.sh and sw-path.sh and the oracle's own reviewers.py, so the frozen pr-snapshot.sh keeps the old
evaluator after reviewers.py leaves the tree (native-cli-pr-pair D8). native-cli-retire-scripts deletes it with the shims.

Each script runs from a stamped directory with SPECWRIGHT_HOME set, so the shims find the CI-built `sw`.

Run: python -m unittest evals/pr-pair/test_parity.py
"""
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
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
sys.path.insert(0, str(ROOT / "evals" / "cli"))
import swharness  # noqa: E402
import test_reviewers as tr  # noqa: E402  helpers only: its test classes are not collected here

SECRET = tas.SECRET


oracle_sw_dir = snapfix.oracle_sw_dir  # shared with test_pr_shims.py


def setUpModule():
    snapfix.banner()


def tearDownModule():
    snapfix.forget_oracle_sw_dir()


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


def fixed_prefix(text):
    """The stable leading part of a free-text line: `line N:`, `merge policy unknown:`, else the text up to and including its
    first `: `, else None (nothing to compare)."""
    for pat in (r"line \d+:", r"merge policy unknown:"):
        m = re.match(pat, text)
        if m:
            return m.group()
    i = text.find(": ")
    return text[:i + 2] if i >= 0 else None


class ParityAsserts:
    def assertParity(self, pair, code=None, prefix=None):
        """With `prefix`, stderr is free text after that fixed prefix (design D11): each side prints the same number of lines,
        all starting with it; line endings are Python's text-mode ones on one side and are not compared."""
        new, old = pair
        self.assertEqual(new["stdout"], old["stdout"], "stdout bytes differ between the script and the oracle")
        if prefix is None:
            self.assertEqual(said(new["stderr"]), said(old["stderr"]), "stderr bytes differ between the script and the oracle")
        else:
            lines = [side["stderr"].decode("utf-8", "replace").splitlines() for side in (new, old)]
            self.assertEqual(len(lines[0]), len(lines[1]), lines)
            for line in lines[0] + lines[1]:
                self.assertTrue(line.startswith(prefix), line)
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
            extra["ORACLE_SW_DIR"] = oracle_sw_dir()
        e = self.env(login, **extra)
        code, out, err = run_script((ORACLE if which == "old" else SCRIPTS) / script, args, e, self.tmp, stdin)
        return {"code": code, "stdout": out, "stderr": err,
                "calls": calls_of(self.gh_log, lambda c: temp_names(c["argv"])), "state": self.gh_state.read_bytes()}

    def pair(self, script, *args, login="me", env=None, old_args=None):
        """(the tree's script, the oracle) on the same fake-gh state: the state is put back before the second run.
        `old_args` are the oracle's arguments when they differ from the script's (a format 1 reviewer config)."""
        before = self.gh_state.read_bytes()
        calls_of(self.gh_log, lambda c: c)
        new = self.one(script, args, "new", login, env)
        self.gh_state.write_bytes(before)
        old = self.one(script, args if old_args is None else old_args, "old", login, env)
        self.gh_state.write_bytes(before)
        return new, old

    def snapshot_pair(self, *args, **kw):
        return self.pair("pr-snapshot.sh", self.PR, "--repo", self.SLUG, *args, **kw)

    def config_pair(self, *reviewers, name="reviewers.json"):
        """The same reviewer rules as a format 2 file for the script and a format 1 file for the oracle (design D8): returns
        (script's path, oracle's path), same file name in two directories."""
        paths = []
        for fmt in (2, 1):
            d = self.tmp / f"cfg-format{fmt}"
            d.mkdir(exist_ok=True)
            paths.append(self.write_config(*reviewers, name=name, where=d, fmt=fmt))
        return tuple(paths)

    def reviewer_snapshot_pair(self, new_cfg, old_cfg):
        """A snapshot of both sides over their own config. Each side's `reviewer_config` must be the SHA-256 of its own bytes;
        the digests differ by design (format 2 vs 1), so they are masked, and everything else is compared exactly."""
        new, old = self.pair("pr-snapshot.sh", self.PR, "--repo", self.SLUG, "--reviewer-config", new_cfg,
                             old_args=(self.PR, "--repo", self.SLUG, "--reviewer-config", old_cfg))
        if new["code"] == 0 and old["code"] == 0:
            for side, path in ((new, new_cfg), (old, old_cfg)):
                digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
                doc = json.loads(side["stdout"])
                self.assertEqual(doc["reviewer_config"], digest)
                side["stdout"] = side["stdout"].replace(digest.encode(), b"DIGEST")
            self.assertNotEqual(hashlib.sha256(Path(new_cfg).read_bytes()).digest(), hashlib.sha256(Path(old_cfg).read_bytes()).digest())
        return new, old

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
        new_cfg, old_cfg = self.config_pair(rev("genrev"), rev("slowbot", timeout=60), rev("silent", role="advisory", timeout=20))
        new, old = self.reviewer_snapshot_pair(new_cfg, old_cfg)
        self.assertParity((new, old), 0)
        self.assertEqual(len(json.loads(old["stdout"])["reviewers"]), 3, "the evaluator really ran")

    def test_bad_reviewer_config_exits_2_before_gh(self):
        bad = self.tmp / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        for path in (fixtures.posix(bad), fixtures.posix(self.tmp / "missing.json")):
            with self.subTest(path=path):
                new, old = self.snapshot_pair("--reviewer-config", path)
                self.assertParity((new, old), 2, prefix="reviewers.py: ")
                self.assertEqual(old["calls"], [], "no gh call before the config check")

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: a file name that is not UTF-8 needs Linux")
    def test_config_name_with_a_non_utf8_byte_for_the_check_and_the_evaluation(self):
        name = os.fsdecode(b"reviewers-\xff.json")
        good, good_old = self.config_pair(rev("genrev"), name=name)
        self.add_activity("a" * 40, T0)
        self.add_comment("genrev", "looks good")
        new, old = self.reviewer_snapshot_pair(good, good_old)  # the evaluation
        self.assertParity((new, old), 0)
        self.assertEqual(json.loads(old["stdout"])["reviewers"][0]["login"], "genrev")
        bad = self.tmp / os.fsdecode(b"bad-\xff.json")
        bad.write_text("{not json", encoding="utf-8")
        new, old = self.snapshot_pair("--reviewer-config", fixtures.posix(bad))  # the check
        self.assertParity((new, old), 2, prefix="reviewers.py: ")
        # reviewers.py opened the file by its bytes (a lost byte would be "No such file"); Python's stderr writes the name
        # with backslashreplace, so the byte shows as \udcff in both
        self.assertIn(b"not valid JSON", new["stderr"], "the check opened the file by its bytes")


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
                       **({"ORACLE_SW_DIR": oracle_sw_dir()} if which == "old" else {}))
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
                e["ORACLE_SW_DIR"] = oracle_sw_dir()
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


CONFIG_PATH = re.compile(r"[/\\]reviewers[/\\]([0-9a-f]{64})\.json$")


class PairParity(PrParity):
    """pr-pair.sh identity, vcs, tier, context and policy (the shim and the `sw` behind it) against the frozen oracle script
    (native-cli-pr-pair S5, D8, D11): the same JSON fields and values, error codes, exit codes, gh calls and fake-gh state.
    `message` is free text after a fixed prefix and is not compared; a reviewer-config path is replaced by the file's rules
    (the name is the SHA-256 of the file's bytes on both sides; `format` differs by design, D10)."""

    HEAD = f"{9:040x}"
    SETTINGS = "openspec/specwright.yaml"
    AGENT = "pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    rev: { role: required }\n"
    USER = "pr:\n  merge: user\n  reviewers:\n    rev: { role: required }\n"

    def setUp(self):
        super().setUp()
        self.git_env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

    # ---- fixtures ----------------------------------------------------------------------------------------
    def repo(self, name, origin="https://github.com/o/n.git", settings=None, push=()):
        d = self.tmp / name
        d.mkdir()
        for args in (("init", "-q", "-b", "main"), ("config", "user.name", "Eval Bot"), ("config", "user.email", "eval@example.invalid")):
            subprocess.run(["git", *args], cwd=d, check=True, capture_output=True, env=self.git_env)
        if origin:
            subprocess.run(["git", "remote", "add", "origin", origin], cwd=d, check=True, capture_output=True, env=self.git_env)
        for url in push:
            subprocess.run(["git", "remote", "set-url", "--push", "origin", url], cwd=d, check=True, capture_output=True, env=self.git_env)
        if settings is not None:
            (d / "openspec").mkdir()
            (d / self.SETTINGS).write_text(settings, encoding="utf-8", newline="\n")
        vcs_test_support.stamp_version(d)  # the shim finds sw from the repo --code names (D2)
        return fixtures.posix(d)

    def contents(self, ref, text):
        def seed(st):
            if text is None:
                fake_gh.set_file(st, self.SLUG, ref, "README.md", "x")
            else:
                fake_gh.set_file(st, self.SLUG, ref, self.SETTINGS, text)
        self.mutate(seed)

    def digest(self, fmt, *logins):
        entries = [{"login": l, "role": "required", "timeout": 1200, "report": {}} for l in sorted(logins)]
        raw = json.dumps({"format": fmt, "reviewers": entries}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def reviewed(self, which, *logins, head=None):
        """A snapshot file as pr-snapshot.sh writes it, carrying the digest of this side's own config format."""
        fmt = 2 if which == "new" else 1
        doc = {"head_oid": head or self.HEAD, "number": 1, "url": f"https://github.com/{self.SLUG}/pull/1",
               "reviewers": [{"login": l, "role": "required", "timeout": 1200, "state": "reported"} for l in logins],
               "reviewer_config": self.digest(fmt, "rev")}
        f = self.tmp / f"snap-{which}.json"
        f.write_text(json.dumps(doc), encoding="utf-8")
        return fixtures.posix(f)

    # ---- running ----------------------------------------------------------------------------------------
    def side(self, which, args, cwd):
        extra = {"SPECWRIGHT_HOME": str(self.home), "SPECWRIGHT_STATE_DIR": str(self.tmp / f"state-{which}"),
                 "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        if which == "old":
            extra["ORACLE_SW_DIR"] = oracle_sw_dir()
        e = self.env("me", **extra)
        code, out, err = run_script((ORACLE if which == "old" else SCRIPTS) / "pr-pair.sh", args(which) if callable(args) else args,
                                    e, cwd or self.tmp)
        return {"code": code, "stdout": out, "stderr": err, "calls": calls_of(self.gh_log, lambda c: temp_names(c["argv"])),
                "state": self.gh_state.read_bytes()}

    def normal(self, side):
        """(the side's JSON document, its `message` or None). In the document a reviewer-config path is replaced by the file's
        rules and a `settings_problem` by its fixed prefix (`line N:`, else the text up to its first `: `)."""
        lines = side["stdout"].decode("utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1, side)
        doc = json.loads(lines[0])

        def walk(node):
            if isinstance(node, dict):
                return {k: (fixed_prefix(v) or v if k == "settings_problem" and isinstance(v, str) else walk(v))
                        for k, v in node.items() if k != "message"}
            if isinstance(node, list):
                return [walk(v) for v in node]
            if isinstance(node, str):
                m = CONFIG_PATH.search(node)
                if m:
                    raw = Path(node).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), m.group(1), "the name is the digest of the bytes")
                    rules = json.loads(raw.decode("utf-8"))
                    rules.pop("format")
                    return {"config": rules}
            return node
        return walk(doc), doc.get("message")

    def run_pair(self, *args, cwd=None, code=None):
        """(the tree's script, the oracle) in `cwd`; asserts they agree and returns the new side's normalized document.
        `args` may be a function of the side ("new" | "old") when a snapshot file differs between them. Free text is compared
        by its fixed prefix (spec: pr-script-runtime): `message`, every stderr line, and `settings_problem` (see normal)."""
        before = self.gh_state.read_bytes()
        calls_of(self.gh_log, lambda c: c)
        sides = []
        for which in ("new", "old"):
            sides.append(self.side(which, args[0] if len(args) == 1 and callable(args[0]) else args, cwd))
            self.gh_state.write_bytes(before)
        new, old = sides
        self.assertEqual(new["code"], old["code"], f"exit codes differ\n{new}\n{old}")
        (new_doc, new_msg), (old_doc, old_msg) = self.normal(new), self.normal(old)
        self.last_message = new_msg
        self.assertEqual(new_doc, old_doc, "JSON differs between the script and the oracle")
        self.assertEqual(new_msg is None, old_msg is None, f"`message` is on one side only\n{new_msg!r}\n{old_msg!r}")
        if old_msg is not None and fixed_prefix(old_msg):
            self.assertTrue(new_msg.startswith(fixed_prefix(old_msg)), f"message prefix differs: {new_msg!r} vs {old_msg!r}")
        self.assertEqual(new["calls"], old["calls"], "the gh calls differ")
        self.assertEqual(new["state"], old["state"], "the fake gh state differs")
        err_new, err_old = (side["stderr"].decode("utf-8", "replace").splitlines() for side in (new, old))
        self.assertEqual(len(err_new), len(err_old), f"stderr lines differ\n{err_new}\n{err_old}")
        for n, o in zip(err_new, err_old):
            self.assertTrue(n.startswith(fixed_prefix(o) or ""), f"stderr prefix differs: {n!r} vs {o!r}")
        if code is not None:
            self.assertEqual(old["code"], code, old["stdout"] + old["stderr"])
        return new_doc

    # ---- identity ----------------------------------------------------------------------------------------
    def test_identity_answers_and_stops(self):
        cases = [
            (self.repo("a", "https://github.com/o/n.git"), 0),
            (self.repo("b", "git@github.com:Acme/Widgets.git", push=["https://github.com/acme/widgets"]), 0),
            (self.repo("c", "https://gitlab.com/o/n"), 1),
            (self.repo("d", "https://github.com/o/n", push=["git@github.com:fork/n.git"]), 1),
            (self.repo("e", None), 1),
            (fixtures.posix(self.tmp / "missing"), 1),
        ]
        for d, code in cases:
            with self.subTest(d=d):
                self.run_pair("identity", d, code=code)

    @unittest.skipUnless(sys.platform == "win32", "platform: a Git Bash path form exists only on Windows")
    def test_git_bash_paths_read_the_same_repo(self):
        """A shim hands its arguments over stdin, so no MSYS conversion happens on the way: sw converts them itself."""
        def msys(path):
            return subprocess.run([bashexe.bash(), "-c", 'cygpath -u "$1"', "_", path], capture_output=True, text=True, check=True).stdout.strip()
        code = self.repo("code", settings="vcs: jj\nfinish: pr\ngithub:\n  login: me\n")
        store = self.repo("store", "https://github.com/o/plans.git", settings="planning_store:\n  login: bob\n")
        m_code, m_store = msys(code), msys(store)
        self.assertTrue(m_code.startswith("/"), m_code)
        self.run_pair("identity", m_code, code=0)
        self.assertEqual(self.run_pair("vcs", "--code", m_code, code=0)["code"], "jj")
        self.run_pair("tier", "--code", m_code, code=0)
        self.run_pair("context", "--code", m_code, "--store", m_store, code=0)
        self.contents("main", self.AGENT)
        self.contents(self.HEAD, self.AGENT)
        self.run_pair(lambda which: ["policy", "--repo", self.SLUG, "--head", self.HEAD,
                                     "--snapshot", "code=" + msys(self.reviewed(which, "rev"))], code=0)

    def test_identity_usage_exits_2(self):
        self.run_pair("identity", code=2)
        self.run_pair("identity", "a", "b", code=2)
        self.run_pair("identity", "--x", code=2)

    # ---- vcs and tier -----------------------------------------------------------------------------------
    def test_vcs_for_each_backend_and_stop(self):
        for i, (settings, code) in enumerate([
            (None, 0), ("vcs: jj\nfinish: pr\n", 0), ("vcs: git\n", 0), ("vcs: svn\n", 1), ("vcs: gitbutler\nfinish: local\n", 1),
            ("vcs: gitbutler\nfinish: pr\n", 0), ("planning_store:\n  vcs: jj\n", 0),
        ]):
            with self.subTest(settings=settings):
                self.run_pair("vcs", "--code", self.repo(f"v{i}", settings=settings), code=code)

    def test_tier_reads_only_cheap_tier(self):
        for i, settings in enumerate([None, "cheap_tier:\n  enabled: true\n", "cheap_tier:\n  enabled: false\n",
                                      "cheap_tier:\n  enabled: maybe\n", "cheap_tier: yes\n", "pr:\n  merge_method: bogus\n",
                                      "cheap_tier:\n\tenabled: true\n"]):
            with self.subTest(settings=settings):
                self.run_pair("tier", "--code", self.repo(f"t{i}", settings=settings), code=0)

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: a directory name that is not UTF-8 needs Linux")
    def test_checkout_under_a_non_utf8_directory_reads_its_settings(self):
        code = self.repo(os.fsdecode(b"co-\xff"), settings="vcs: jj\nfinish: pr\ngithub:\n  login: me\n")
        self.assertEqual(self.run_pair("vcs", "--code", code, code=0)["code"], "jj")
        self.run_pair("tier", "--code", code, code=0)

    def test_vcs_and_tier_usage_exit_2(self):
        for sub in ("vcs", "tier"):
            self.run_pair(sub, code=2)

    # ---- context ----------------------------------------------------------------------------------------
    def test_context_per_repo_settings(self):
        text = ("github:\n  login: me\nvalidate: make check\npr:\n  settle: 2m\n  merge: agent\n  merge_method: squash\n"
                "  delete_branch: true\n  reviewers:\n    codex: { role: required, timeout: 30m, report: { marker: done } }\n"
                "    Other[bot]: { role: advisory }\n")
        code = self.repo("code", settings=text)
        store = self.repo("store", "https://github.com/o/plans.git", settings="planning_store:\n  login: bob\n  reviewers:\n    s: {}\n")
        self.run_pair("context", "--code", code, code=0)
        self.run_pair("context", "--code", code, "--store", store, code=0)
        self.run_pair("context", "--code", code, "--store", store, "--only", "repos", code=0)

    def test_context_stops_on_a_section_that_is_not_a_mapping(self):
        for i, text in enumerate(("pr: oops\n", "pr: 5\n", "pr: true\n", "pr: [a]\n", "github: oops\n", "github:\n  review_request: oops\n")):
            code = self.repo(f"bad{i}", settings=text)
            self.run_pair("context", "--code", code, code=1)
        for i, text in enumerate(("pr: 0\n", "github: false\n", "planning_store: oops\n")):
            code = self.repo(f"empty{i}", settings=text)
            self.run_pair("context", "--code", code, code=0)
        code, store = self.repo("code", settings="planning_store: oops\n"), self.repo("store", "https://github.com/o/plans.git")
        self.run_pair("context", "--code", code, "--store", store, code=1)

    def test_context_stops_and_problems(self):
        cases = [
            ("pr:\n  merge: agent\n  merge_method: bogus\n", 2), ("pr:\n  merge: agent\n  delete_branch: maybe\n", 2),
            ("pr:\n  settle: 30s\n", 0), ("pr:\n  settle: forever\n", 0), ("pr:\n\treviewers: x\n", 0),
            ("pr:\n  reviewers:\n    r: { report: 3 }\n", 0), ("pr:\n  merge: yes\n", 0), ("a: [\n", 0),
        ]
        for i, (settings, code) in enumerate(cases):
            with self.subTest(settings=settings):
                self.run_pair("context", "--code", self.repo(f"x{i}", settings=settings), code=code)
        self.run_pair("context", code=2)

    def test_context_on_gitbutler_pins_the_settings(self):
        d = self.repo("gb", settings="vcs: gitbutler\nfinish: pr\npr:\n  merge: agent\n")
        self.run_pair("context", "--code", d, code=2)
        self.run_pair("context", "--code", d, "--only", "repos", code=0)
        self.run_pair("context", "--code", d, "--branch", "feat/a", code=1)

    # ---- policy -----------------------------------------------------------------------------------------
    def policy_args(self, *extra, snapshot=True, logins=("rev",)):
        def build(which):
            args = ["policy", "--repo", self.SLUG, "--head", self.HEAD, *extra]
            if snapshot:
                args += ["--snapshot", "code=" + self.reviewed(which, *logins)]
            return args
        return build

    def test_policy_drift_and_main_values(self):
        for i, (main, head) in enumerate([
            (self.AGENT, self.AGENT), (self.AGENT, self.USER), (self.USER, self.AGENT), (None, self.AGENT),
            (self.AGENT, "pr:\n  merge: agent\n  merge_method: rebase\n  delete_branch: true\n"),
            ("pr:\n  reviewers: [a, b]\n", self.AGENT), (self.AGENT, "pr:\n  reviewers: nope\n"),
        ]):
            with self.subTest(i=i):
                self.contents("main", main)
                self.contents(self.HEAD, head)
                self.run_pair(self.policy_args(), code=0)

    def test_policy_stops(self):
        self.contents("main", self.AGENT)
        self.contents(self.HEAD, None)
        self.run_pair(self.policy_args(), code=3)
        self.contents(self.HEAD, "pr:\n  merge: agent\n  items:\n    - a\n")
        self.run_pair(self.policy_args(), code=3)
        self.contents("main", "pr:\n  merge: agent\n  merge_method: bogus\n")
        self.contents(self.HEAD, self.AGENT)
        self.run_pair(self.policy_args(), code=2)
        self.contents("main", "pr:\n  merge: agent\n  settle: forever\n")
        self.run_pair(self.policy_args(), code=2)

    def test_policy_reported_and_rules_mismatch(self):
        self.contents("main", self.AGENT)
        self.contents(self.HEAD, self.AGENT)
        self.run_pair(self.policy_args(logins=()), code=0)
        self.run_pair(self.policy_args(logins=("other",)), code=0)
        self.run_pair(self.policy_args("--reviewed-head", "code=" + self.HEAD[:12]), code=0)
        self.run_pair(self.policy_args(snapshot=False), code=2)

    def test_policy_with_a_store(self):
        self.contents("main", self.AGENT + "planning_store:\n  reviewers:\n    rev: {}\n")
        self.contents(self.HEAD, self.AGENT)

        def build(which):
            return ["policy", "--repo", self.SLUG, "--head", self.HEAD, "--store", "--snapshot", "code=" + self.reviewed(which, "rev"),
                    "--snapshot", "store=" + self.reviewed(which, "rev"), "--reviewed-head", "store=" + self.HEAD]
        self.run_pair(build, code=0)
        self.run_pair(self.policy_args("--store"), code=2)

    def test_policy_usage_exits_2(self):
        self.run_pair("policy", code=2)
        self.run_pair("policy", "--repo", self.SLUG, code=2)


    # ---- named cases of the test map ---------------------------------------------------------------------
    def find(self, node, key):
        """Every value of `key` anywhere in a document."""
        if isinstance(node, dict):
            for k, v in node.items():
                if k == key:
                    yield v
                yield from self.find(v, key)
        elif isinstance(node, list):
            for v in node:
                yield from self.find(v, key)

    def test_context_tab_in_indentation_names_line_7(self):
        text = "github:\n  login: me\nvalidate: make check\npr:\n  merge: user\n  reviewers:\n\trev: { role: required }\n"
        self.assertEqual(text.splitlines()[6][0], "\t")
        code = self.repo("tab", settings=text)
        problems = [p for p in self.find(self.run_pair("context", "--code", code, code=0), "settings_problem")]
        self.assertTrue(problems and all(p.startswith("line 7:") for p in problems), problems)
        for side in ("new", "old"):  # the raw text on each side, not only the compared prefix
            raw = self.side(side, ["context", "--code", code], None)["stdout"].decode("utf-8")
            self.assertRegex(raw, r'"settings_problem": ?"line 7:')

    def test_policy_bad_base64_keeps_lookup_failed(self):
        self.contents(self.HEAD, self.AGENT)
        self.mutate(lambda st: fake_gh.set_file(st, self.SLUG, "main", self.SETTINGS, {"content": "!!! not base64 !!!\n"}))
        doc = self.run_pair(self.policy_args(), code=3)
        self.assertEqual(doc["error"], "lookup_failed")
        self.assertTrue(self.last_message.startswith(f"merge policy unknown: unreadable {self.SETTINGS} at main:"), self.last_message)
        # the head side too
        self.contents("main", self.AGENT)
        self.mutate(lambda st: fake_gh.set_file(st, self.SLUG, self.HEAD, self.SETTINGS, {"content": "QUJD\n=\n"}))
        self.run_pair(self.policy_args(), code=3)

    # ---- unicode and shape cases ------------------------------------------------------------------------
    def test_context_unicode_digits_and_spaces_in_settings(self):
        nbsp, ideo, arab = chr(0xA0), chr(0x3000), "".join(chr(0x660 + int(d)) for d in "30")
        cases = [
            f"pr:\n  settle: {arab}0s\n",
            f"pr:\n  reviewers:\n    rev: {{ timeout: {arab}m }}\n",
            f"pr:\n  reviewers:\n    rev: {{ timeout: {chr(0xFF12)}{chr(0xFF10)}m }}\n",
            f"pr:\n{nbsp}{nbsp}merge: agent\n",
            f"pr:\n{ideo}merge: agent\n",
            f"pr:\n  merge:{nbsp}agent\n",
            f"pr:\n  merge: agent{ideo}\n",
            f"pr:\n  settle:{ideo}2m{nbsp}\n",
            f"pr:\n  reviewers:\n    rev:{ideo}{{ role: advisory }}\n",
            f"github:\n  login:{nbsp}me\n",
        ]
        for i, text in enumerate(cases):
            with self.subTest(i=i):
                self.run_pair("context", "--code", self.repo(f"u{i}", settings=text), code=None)

    def test_policy_unicode_digits_and_spaces_in_settings(self):
        nbsp, ideo, arab = chr(0xA0), chr(0x3000), "".join(chr(0x660 + int(d)) for d in "30")
        for i, text in enumerate([f"pr:\n  merge: agent\n  settle: {arab}0s\n", f"pr:\n{nbsp}merge: agent\n",
                                  f"pr:\n  merge: agent{ideo}\n  reviewers:\n    rev: {{ timeout: {arab}m }}\n"]):
            with self.subTest(i=i):
                self.contents("main", text)
                self.contents(self.HEAD, self.AGENT)
                self.run_pair(self.policy_args(), code=None)

    def test_bot_login_with_a_final_newline(self):
        """Python's `$` in the [bot]-stripping regex also matches before a final newline: a snapshot login `rev[bot]<LF>`
        reads as `rev<LF>`; both sides must decide alike for it."""
        bs = chr(92)
        self.contents("main", "pr:" + chr(10) + "  merge: agent" + chr(10) + "  reviewers:" + chr(10) + "    rev[bot]: { role: required }" + chr(10))
        self.contents(self.HEAD, self.AGENT)
        for login in ("rev[bot]" + chr(10), "rev[bot]", "REV[bot]" + chr(10), "rev" + chr(10), "rev[bot][bot]", "rev[bot]" + chr(10) + chr(10)):
            with self.subTest(login=login):
                self.run_pair(self.policy_args(logins=(login,)), code=0)
        # a flow-mapping reviewer set whose key carries the escape: both sides read it alike, whatever they make of it
        for i, text in enumerate(['pr:' + chr(10) + '  reviewers: { "rev[bot]' + bs + 'n": { role: required } }' + chr(10),
                                  'pr:' + chr(10) + '  reviewers:' + chr(10) + '    rev[bot]: { role: required }' + chr(10)]):
            self.run_pair("context", "--code", self.repo(f"b{i}", settings=text), code=0)

    def test_policy_21_reviewers_is_too_many_reviewers(self):
        many = "pr:\n  merge: agent\n  reviewers:\n" + "".join(f"    bot-{i}: {{ role: advisory }}\n" for i in range(21))
        self.contents("main", many)
        self.contents(self.HEAD, self.AGENT)
        self.run_pair(self.policy_args(), code=2)
        self.contents("main", self.AGENT)
        self.contents(self.HEAD, many)
        self.run_pair(self.policy_args(), code=0)
        self.run_pair("context", "--code", self.repo("many", settings=many), code=0)


class ReviewersParity(unittest.TestCase):
    """`sw pr reviewers` (format 2 config) against the frozen evaluator oracle/reviewers.py (format 1 config, the same rules) on
    the same material (native-cli-pr-pair D5, D8). stdout is compared exactly but for the config digest, which each side checks
    against its own bytes; exit codes are exact; stderr is compared by the `reviewers.py: ` prefix, line for line."""

    PREFIX = "reviewers.py: "

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name)
        self.sw = swharness.require_sw()

    def write(self, name, obj, where=None):
        d = self.tmp if where is None else where
        d.mkdir(exist_ok=True)
        p = d / name
        if isinstance(obj, str):
            p.write_text(obj, encoding="utf-8", newline="")
        else:
            p.write_text(json.dumps(obj, separators=(",", ":")), encoding="utf-8", newline="")
        return p

    def config_for(self, fmt, *reviewers):
        return {"format": fmt, "reviewers": list(reviewers)}

    def run_side(self, which, args):
        cmd = [self.sw, "pr", "reviewers", *args] if which == "new" else [sys.executable, "-I", "-X", "utf8", str(ORACLE / "reviewers.py"), *args]
        r = subprocess.run(cmd, capture_output=True, cwd=self.tmp, timeout=60, env=swharness.fixture_env())
        return {"code": r.returncode, "stdout": r.stdout, "stderr": r.stderr}

    def pair(self, cfg=None, material=None, head=None, code=None, extra=(), raw_config=None, check=False, crash=False):
        """Run both sides. `cfg` is a function of the format (1 for the oracle, 2 for sw) giving the config document, or
        `raw_config` a text both read as is. `check` runs --check-config instead of an evaluation."""
        out = []
        digests = []
        for which, fmt in (("new", 2), ("old", 1)):
            d = self.tmp / which
            args = []
            cfg_path = None
            if raw_config is not None:
                cfg_path = self.write("cfg.json", raw_config, d)
            elif cfg is not None:
                cfg_path = self.write("cfg.json", cfg(fmt), d)
            if check:
                args = ["--check-config", str(cfg_path if cfg_path else d / "missing.json")]
            else:
                if cfg_path:
                    args += ["--config", str(cfg_path)]
                if material is not None:
                    args += ["--material", str(self.write("mat.json", material, d) if not isinstance(material, Path) else material)]
                args += ["--head", head or tr.HEAD]
            args += list(extra)
            res = self.run_side(which, args)
            if cfg_path is not None and cfg_path.exists():
                digest = hashlib.sha256(cfg_path.read_bytes()).hexdigest().encode()
                if digest in res["stdout"]:
                    res["stdout"] = res["stdout"].replace(digest, b"DIGEST")
                digests.append(digest)
            out.append(res)
        new, old = out
        self.assertEqual(new["code"], old["code"], f"exit codes differ\n{new}\n{old}")
        self.assertEqual(new["stdout"], old["stdout"], "stdout differs between sw and the oracle")
        lines = [s["stderr"].decode("utf-8", "replace").splitlines() for s in out]
        if crash:  # the oracle dies on an uncaught exception (a Python defect, exit 1 all the same); sw states it in one line
            self.assertIn("Traceback", old["stderr"].decode("utf-8", "replace"))
            self.assertEqual(len(lines[0]), 1, lines[0])
            self.assertTrue(lines[0][0].startswith(self.PREFIX), lines[0])
        else:
            self.assertEqual(len(lines[0]), len(lines[1]), lines)
            for line in lines[0] + lines[1]:
                self.assertTrue(line.startswith(self.PREFIX), line)
        if code is not None:
            self.assertEqual(old["code"], code, old["stdout"] + old["stderr"])
        if code == 0 and not check and cfg is not None:
            self.assertIn(b"DIGEST", new["stdout"], "the digest was masked")
        return new

    def rev(self, login="rev-bot", **kw):
        return tr.reviewer(login, **kw)

    def test_evaluations_agree(self):
        rev = self.rev()
        sha = self.rev("sha-bot", report={"sha_pattern": "Reviewed commit: ([0-9a-f]{7,40})"})
        mark = self.rev("mark-bot", role="advisory", timeout=60, report={"marker": "LGTM", "ignore": "^skip"})
        chk = self.rev("chk-bot", report={"check": "review"})
        items = {
            "rev-bot": [tr.review(tr.HEAD, "ok", id="r1"), tr.comment("later", created=tr.iso(90), id="c2")],
            "sha-bot": [tr.comment("Reviewed commit: " + tr.HEAD[:12], created=tr.iso(5), id="c3"),
                        tr.comment("Reviewed commit: " + tr.PREV[:12], created=tr.iso(6), id="c4")],
            "mark-bot": [tr.comment("LGTM", created=tr.iso(7), edited=tr.iso(8), id="c5"), tr.comment("skip LGTM", id="c6")],
            "chk-bot": [],
        }
        mat = tr.material(items, checks_all=[tr.check("review", app="chk-bot"), tr.check("build")])
        cfg = lambda fmt: self.config_for(fmt, rev, sha, mark, chk)
        self.pair(cfg, mat, code=0)

    def test_states_waiting_timed_out_and_pending(self):
        rev, adv = self.rev(timeout=30), self.rev("adv-bot", role="advisory")
        mat = tr.material({"rev-bot": [tr.review(tr.PREV, "old head"), tr.review(tr.HEAD, "x", state="PENDING", id="r2")]}, now_offset=500)
        self.pair(lambda fmt: self.config_for(fmt, rev, adv), mat, code=0)

    def test_unicode_and_odd_bodies(self):
        rev = self.rev(report={"marker": "é中"})
        mat = tr.material({"rev-bot": [tr.comment("café 中文 \U0001F600 " + "x" * 3000, created=tr.iso(9))]})
        self.pair(lambda fmt: self.config_for(fmt, rev), mat, code=0)

    def test_no_config_means_no_reviewers(self):
        self.pair(None, tr.material(), code=0)

    def test_nan_and_infinity_material(self):
        rev = self.rev()
        cfg = lambda fmt: self.config_for(fmt, rev)
        base = tr.material({"rev-bot": [tr.review(tr.HEAD)]})
        # NaN in a field nothing reads, in one the clock reads, and as a bare token in the document
        self.pair(cfg, dict(base, z_unused=float("nan")))
        self.pair(cfg, dict(base, cfg={"since": tr.CUT, "now": float("nan")}))
        # the oracle crashes with an OverflowError traceback here; sw says so in one `reviewers.py:` line (same exit 1, empty stdout)
        self.pair(cfg, dict(base, cfg={"since": tr.CUT, "now": float("inf")}), code=1, crash=True)
        self.pair(cfg, dict(base, number=float("-inf")))
        self.pair(cfg, tr.material({"rev-bot": [tr.comment("x", created=float("nan"))]}))
        self.pair(cfg, json.dumps(dict(base, z_unused=0)).replace('"z_unused":0', '"z_unused":NaN'))
        self.pair(cfg, '{"head_oid":"%s","z":NaN' % tr.HEAD)

    def test_material_and_head_refusals(self):
        rev = self.rev()
        cfg = lambda fmt: self.config_for(fmt, rev)
        self.pair(cfg, tr.material(), head="f" * 40, code=1)
        self.pair(cfg, "{nope", code=1)
        self.pair(cfg, "[]", code=1)
        self.pair(cfg, "null", code=1)
        self.pair(cfg, tr.material(), code=2, extra=["--bogus"])
        self.pair(cfg, self.tmp / "no-such-material.json", code=1)
        self.pair(cfg, None, code=2)

    def test_non_json_and_unreadable_config(self):
        mat = tr.material()
        self.pair(None, mat, raw_config="not json", code=2)
        self.pair(None, mat, raw_config="", code=2)
        self.pair(None, mat, raw_config="[]", code=2)
        self.pair(None, mat, raw_config='{"format": NaN, "reviewers": []}', code=2)
        self.pair(None, mat, raw_config="﻿{}", code=2)
        self.pair(None, tr.material(), raw_config=None, check=True, code=2)
        self.pair(None, mat, raw_config="not json", check=True, code=2)

    def test_config_refusals_exit_2(self):
        mat = tr.material()
        bad = {
            "unknown top key": lambda fmt: {"format": fmt, "reviewers": [], "extra": 1},
            "unknown reviewer key": lambda fmt: self.config_for(fmt, {"login": "rev-bot", "role": "required", "timeout": 1, "x": 1}),
            "bad login": lambda fmt: self.config_for(fmt, self.rev("bad login")),
            "bad role": lambda fmt: self.config_for(fmt, self.rev(role="boss")),
            "negative timeout": lambda fmt: self.config_for(fmt, self.rev(timeout=-1)),
            "bool timeout": lambda fmt: self.config_for(fmt, self.rev(timeout=True)),
            "empty marker": lambda fmt: self.config_for(fmt, self.rev(report={"marker": ""})),
            "unknown report key": lambda fmt: self.config_for(fmt, self.rev(report={"checks": "x"})),
            "21 reviewers": lambda fmt: self.config_for(fmt, *[self.rev("bot-%d" % i) for i in range(21)]),
            "duplicate login": lambda fmt: self.config_for(fmt, self.rev(), self.rev()),
            "bad sha_pattern": lambda fmt: self.config_for(fmt, self.rev(report={"sha_pattern": "([0-9a-f"})),
            "sha_pattern without a group": lambda fmt: self.config_for(fmt, self.rev(report={"sha_pattern": "abc"})),
            "long marker": lambda fmt: self.config_for(fmt, self.rev(report={"marker": "m" * 501})),
        }
        for name, cfg in bad.items():
            with self.subTest(name):
                self.pair(cfg, mat, code=2)
                self.pair(cfg, None, check=True, code=2)

    def test_check_config_prints_digest_and_logins(self):
        cfg = lambda fmt: self.config_for(fmt, self.rev("b-bot"), self.rev("a-bot", report={}))
        new = self.pair(cfg, check=True, code=0)
        self.assertIn(b'"logins":["b-bot","a-bot"]', new["stdout"])
        self.pair(lambda fmt: self.config_for(fmt, *[self.rev("bot-%d" % i) for i in range(20)]), check=True, code=0)

    def test_usage_stops_exit_2(self):
        for extra in ([], ["--head", tr.HEAD], ["--material", "m.json"]):
            with self.subTest(extra=extra):
                new, old = (self.run_side(w, extra) for w in ("new", "old"))
                self.assertEqual((new["code"], new["stdout"]), (old["code"], old["stdout"]))
                self.assertEqual(new["code"], 2)
                for s in (new, old):
                    self.assertTrue(s["stderr"].decode().startswith(self.PREFIX), s)
        new, old = (self.run_side(w, ["--check-config", "x.json", "--head", tr.HEAD]) for w in ("new", "old"))
        self.assertEqual((new["code"], old["code"]), (2, 2))


if __name__ == "__main__":
    unittest.main()
