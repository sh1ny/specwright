"""Differential eval (native-cli-pr-io D12, native-cli-pr-pair D8, native-cli-retire-scripts D14): `sw pr snapshot`, `sw pr reply`,
`sw pr` (identity, vcs, tier, context, policy), `sw pr reviewers` and `sw as` run the same cases they ran against the frozen
scripts, on the same fake-gh state, and must give the same document, exit status, stderr prefixes, gh calls and fake-gh state.

The frozen side is no longer run. Task 6.5 ran it once on each OS and kept one record per run under evals/pr-pair/oracle/records/;
each case here makes its runs in the order the capture saw them and compares each with the record of the running OS, both
normalized by evals/pr-pair/oracle_capture.py (machine paths become placeholders, the free text of stderr is cut to its fixed
prefix, an OS-dependent value is compared as oracle/check_records.py allows).

Each run starts from a stamped directory with SPECWRIGHT_HOME set, so the CI-built `sw` runs.

Run: python -m unittest evals/pr-pair/test_parity.py
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
sys.path.insert(0, str(ROOT / "evals" / "git-workflow"))
sys.path.append(str(ROOT / "evals"))
import oracle_capture  # noqa: E402
import snapfix  # noqa: E402
from snapfix import SnapCase, T0, fake_gh, fixtures, rev  # noqa: E402
import swcall  # noqa: E402  every call of sw goes through the one helper
import test_as_sh as tas  # noqa: E402  module attributes only: its test classes are not collected here
import vcs_test_support  # noqa: E402
sys.path.insert(0, str(ROOT / "evals" / "cli"))
import swharness  # noqa: E402
import test_reviewers as tr  # noqa: E402  helpers only: its test classes are not collected here

SECRET = tas.SECRET
SNAPSHOT = ("pr", "snapshot")
REPLY = ("pr", "reply")


def setUpModule():
    snapfix.banner()


def run_sw(args, env, cwd, stdin=None):
    """(exit code, stdout bytes, stderr bytes) of `sw <args>`."""
    r = swcall.run([*map(str, args)], cwd=cwd, env=env, input=stdin, timeout=120, text=False)
    return r.returncode, r.stdout, r.stderr


def without_slurp(entry):
    """A listed difference from the frozen oracle (native-cli-library-foundations D4): sw reads a page list with
    `api --paginate --slurp`, the oracle with `api --paginate`. Drop a --slurp that directly follows --paginate so the
    two call logs compare equal; the Dart tests pin the flag itself."""
    argv = entry["argv"]
    if "--paginate" in argv:
        i = argv.index("--paginate") + 1
        if argv[i:i + 1] == ["--slurp"]:
            entry = {**entry, "argv": argv[:i] + argv[i + 1:]}
    return entry


def calls_of(log, keep):
    """The fake gh's call log as a list of keep(entry), then the log is removed."""
    out = []
    if log.exists():
        out = [keep(without_slurp(json.loads(l))) for l in log.read_text(encoding="utf-8").splitlines()]
        log.unlink()
    return out


def temp_names(argv):
    """argv with the random part of an mktemp name blanked: two runs never draw the same one."""
    return [re.sub(r"tmp\.[A-Za-z0-9]+", "tmp.X", a) for a in argv]


def parsed(stdout):
    """stdout as the JSON document it holds: `sw` writes compact JSON and the frozen scripts write spaced JSON, so two
    documents are compared by value and not by bytes (native-cli-library-foundations D3). Output that is not one JSON
    document (an environment dump, a command's own text) stays the bytes. NaN and Infinity read as their names."""
    try:
        return json.loads(stdout.decode("utf-8"), parse_constant=lambda name: name)
    except ValueError:
        return stdout


def masked(node, digest, mask="DIGEST"):
    """`node` with every string equal to `digest` (the config digest each side computes over its own bytes) replaced."""
    if isinstance(node, dict):
        return {k: masked(v, digest, mask) for k, v in node.items()}
    if isinstance(node, list):
        return [masked(v, digest, mask) for v in node]
    return mask if node == digest else node


PINNED_IDENTITY = oracle_capture.PINNED_IDENTITY  # fixture commits repeat their ids in every run and on every OS (D14)

said, fixed_prefix = oracle_capture.said, oracle_capture.fixed_prefix  # shared with the capture of the frozen side


class ParityAsserts:
    def assertMatches(self, new, old, **extra):
        """`new`, a run of sw, equals `old`, the recorded run of the frozen side, once both are normalized the way a record is:
        the exit status, the stdout document, the number of stderr lines and each line's fixed prefix, the gh calls and the
        fake-gh state. `extra` is what a record holds beyond that (the requests that reached a server)."""
        got = oracle_capture.document(self, new, **extra)
        problem = oracle_capture.compare(self, got, old)
        if problem:
            self.fail(f"the run differs from the frozen side's record at {problem}")

    def assertParity(self, pair, code=None, prefix=None):
        """(sw's run, the record of the frozen run) agree; `code` is the exit status the case names. With `prefix`, every stderr
        line of the record starts with it."""
        new, old = pair
        self.assertMatches(new, old, **{key: new[key] for key in ("requests",) if key in new})
        if prefix is not None:
            for fixed in old["stderr"]["prefixes"]:
                self.assertTrue(fixed.startswith(prefix), old["stderr"])
        if code is not None:  # the case really ran what it names, not a broken fixture
            self.assertEqual(old["exit"], code, old)


class PrParity(SnapCase, ParityAsserts):
    """`sw pr snapshot` and `sw pr reply` against the records of the frozen scripts."""

    def setUp(self):
        super().setUp()
        self.home = vcs_test_support.sw_home()
        vcs_test_support.stamp_version(self.tmp)  # the project is the current directory

    def one(self, command, args, login, env, stdin=None):
        extra = {"SPECWRIGHT_HOME": str(self.home), "SPECWRIGHT_STATE_DIR": str(self.tmp / "state-new"), **(env or {})}
        code, out, err = run_sw([*command, *args], self.env(login, **extra), self.tmp, stdin)
        return {"code": code, "stdout": out, "stderr": err,
                "calls": calls_of(self.gh_log, lambda c: temp_names(c["argv"])), "state": self.gh_state.read_bytes()}

    def pair(self, command, *args, login="me", env=None):
        """(sw's run, the next recorded run of the frozen side): the fake-gh state is put back after the run."""
        before = self.gh_state.read_bytes()
        calls_of(self.gh_log, lambda c: c)
        new = self.one(command, args, login, env)
        self.gh_state.write_bytes(before)
        return new, oracle_capture.recorded(self)[0]

    def snapshot_pair(self, *args, **kw):
        return self.pair(SNAPSHOT, self.PR, "--repo", self.SLUG, *args, **kw)

    def config_pair(self, *reviewers, name="reviewers.json"):
        """The same reviewer rules as a format 2 file for sw and a format 1 file (the frozen evaluator's): returns (sw's path,
        the frozen side's path), same file name in two directories. The frozen file is not run: its bytes give the digest the
        record holds."""
        paths = []
        for fmt in (2, 1):
            d = self.tmp / f"cfg-format{fmt}"
            d.mkdir(exist_ok=True)
            paths.append(self.write_config(*reviewers, name=name, where=d, fmt=fmt))
        return tuple(paths)

    def reviewer_snapshot_pair(self, new_cfg, old_cfg):
        """A snapshot over sw's config and the record of the frozen side's over its own. Each side's `reviewer_config` is the
        SHA-256 of its own bytes; the digests differ by design (format 2 vs 1), so they are masked, and everything else is
        compared exactly."""
        new, old = self.pair(SNAPSHOT, self.PR, "--repo", self.SLUG, "--reviewer-config", new_cfg)
        if new["code"] == 0 and old["exit"] == 0:
            digest = hashlib.sha256(Path(new_cfg).read_bytes()).hexdigest()
            doc = json.loads(new["stdout"])
            self.assertEqual(doc["reviewer_config"], digest)
            new["stdout"] = json.dumps(masked(doc, digest)).encode()
            frozen = hashlib.sha256(Path(old_cfg).read_bytes()).hexdigest()
            self.assertEqual(old["stdout"]["reviewer_config"], frozen, "the record's digest is that of the frozen format-1 file")
            old["stdout"] = masked(old["stdout"], frozen)
            self.assertNotEqual(digest, frozen)
        return new, old

    def body(self, text="done"):
        f = self.tmp / "body.md"
        f.write_text(text, encoding="utf-8", newline="\n")
        return fixtures.posix(f)

    def reply_pair(self, *args, repo=True, **kw):
        return self.pair(REPLY, self.PR, *args, *(["--repo", self.SLUG] if repo else []), **kw)

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
        self.assertFalse(old["stdout"]["complete"], "the list must really be cut off")

    def test_snapshot_logs_and_a_pr_url(self):
        self.rich()
        url = f"https://github.com/{self.SLUG}/pull/{self.PR}"
        self.assertParity(self.pair(SNAPSHOT, url, "--logs"), 0)

    def test_snapshot_refusals_exit_2_alike(self):
        for args in (["--reviewer", "a:b:3"], ["--bogus"], ["--until", "quiet"], ["--interval", "0"]):
            with self.subTest(args=args):
                # sw's option rule words the parser's own refusals (an unknown option) its own way: the stop and the exit
                # status are compared, and every stderr line starts with the script's prefix
                self.assertParity(self.pair(SNAPSHOT, self.PR, "--repo", self.SLUG, *args), 2, prefix="pr-snapshot: ")

    def test_snapshot_full_without_a_node_id_is_a_usage_stop_in_sw(self):
        """An asserted difference (native-cli-library-foundations): the script died on `${2:?}` with exit 1; sw's one option rule
        stops an option with no value as a usage error, exit 2, before any gh call."""
        new, old = self.pair(SNAPSHOT, self.PR, "--repo", self.SLUG, "--full")
        self.assertEqual(old["exit"], 1, old)
        self.assertEqual(new["code"], 2, new)
        self.assertEqual(new["stdout"], b"")
        self.assertEqual(new["calls"], [])

    def test_snapshot_gh_failure(self):
        self.mutate(lambda st: st.update({"fail": [{"match": "graphql", "exit": 1, "stderr": "boom"}]}))
        new, old = self.snapshot_pair()
        self.assertParity((new, old))
        self.assertNotEqual(old["exit"], 0)

    def test_full_for_each_kind(self):
        tid, c = self.add_thread("rev", "thread body <!-- c --> and more")
        ic = self.add_comment("rev", "comment body " + "q" * 1500)
        rv = self.add_review("rev", "review body", state="COMMENTED")
        for kind, node in (("thread_comment", c["id"]), ("comment", ic["node_id"]), ("review", rv["id"])):
            with self.subTest(kind=kind):
                new, old = self.pair(SNAPSHOT, "--full", node, "--repo", self.SLUG)
                self.assertParity((new, old), 0)
                self.assertEqual(old["stdout"]["kind"], kind)

    def test_full_not_found(self):
        new, old = self.pair(SNAPSHOT, "--full", "MDNot_Found_1=", "--repo", self.SLUG)
        self.assertParity((new, old), 1)
        self.assertIn("not_found", json.dumps(old["stdout"]))

    def test_full_unreadable_exits_3(self):
        self.mutate(lambda st: st.update({"fail": [{"match": "node\\(id", "exit": 1, "stderr": "boom"}]}))
        self.assertParity(self.pair(SNAPSHOT, "--full", "MDNode1=", "--repo", self.SLUG), 3)

    def test_reviewer_config_snapshot(self):
        self.add_activity("a" * 40, T0)
        self.advance(30)
        self.add_comment("genrev", "looks good to me")
        self.add_comment("slowbot", "working on it")
        new_cfg, old_cfg = self.config_pair(rev("genrev"), rev("slowbot", timeout=60), rev("silent", role="advisory", timeout=20))
        new, old = self.reviewer_snapshot_pair(new_cfg, old_cfg)
        self.assertParity((new, old), 0)
        self.assertEqual(len(old["stdout"]["reviewers"]), 3, "the evaluator really ran")

    def test_bad_reviewer_config_exits_2_before_gh(self):
        bad = self.tmp / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        for path in (fixtures.posix(bad), fixtures.posix(self.tmp / "missing.json")):
            with self.subTest(path=path):
                new, old = self.snapshot_pair("--reviewer-config", path)
                self.assertParity((new, old), 2, prefix="reviewers.py: ")
                self.assertEqual(old["calls"], [], "no gh call before the config check")

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: a file name that is not UTF-8 needs Linux")
    def test_config_name_with_a_non_utf8_byte_is_refused(self):
        # Direct entry (task 6.4): the runtime refuses an argument that is not UTF-8 before `main` (exit non-zero, empty stdout)
        # and nothing is run, so no gh call is made.
        good, _ = self.config_pair(rev("genrev"), name=os.fsdecode(b"reviewers-\xff.json"))
        new = self.one(SNAPSHOT, (self.PR, "--repo", self.SLUG, "--reviewer-config", good), "me", None)
        self.assertNotEqual(new["code"], 0, new)
        self.assertEqual(new["stdout"], b"")
        self.assertEqual(new["calls"], [], "no gh call before the refusal")


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


class AsParity(tas.AsShCase, ParityAsserts):
    """`sw as` against the records of the frozen script, in a repo whose origin is github.com."""

    def setUp(self):
        super().setUp()
        self.home = vcs_test_support.sw_home()
        self.work = self.repo("work")
        self.git(self.work, "remote", "set-url", "origin", "https://github.com/o/r.git")
        self.git(self.work, "config", "http.proxy", self.base.rstrip("/"))
        vcs_test_support.stamp_version(self.work)

    def pair(self, *args, cwd=None, env=None, stdin=None, mask=None, dump_env=False):
        """(sw's run in `cwd`, the next recorded run of the frozen side). `mask` is a text replaced by *** in stdout and stderr.
        `dump_env`: stdout is an environment dump; a record keeps the fence's own variables only (oracle_capture.env_lines)."""
        e = self.env()
        e.update({"SPECWRIGHT_HOME": str(self.home), **(env or {})})
        tas.Recorder.seen = []
        calls_of(self.tmp / "gh-log.jsonl", lambda c: c)
        before = (self.tmp / "gh-state.json").read_bytes()
        code, so, se = run_sw(["as", *args], e, cwd or self.work, stdin)
        if mask:
            so, se = so.replace(mask.encode(), b"***"), se.replace(mask.encode(), b"***")
        new = {"code": code, "stdout": so, "stderr": se, "state": (self.tmp / "gh-state.json").read_bytes(),
               "calls": calls_of(self.tmp / "gh-log.jsonl", lambda c: (temp_names(c["argv"]), c["env"])),
               "requests": list(tas.Recorder.seen)}
        if dump_env:
            new["dump"] = so
            new["stdout"] = oracle_capture.env_lines(so)
        old = oracle_capture.recorded(self)[0]
        self.assertEqual(before, new["state"])
        return new, old

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
                self.assertIn(b"refusing", new["stderr"])

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
        new, old = self.pair("sh1ny", "env", env=env, mask="tok-s", dump_env=True)
        # the record keeps only the variables the fence sets or keeps (`AS_SH_*`, `GH_*`, `GIT_*`), sorted: the order of a dump
        # follows how each program built the block, and the machine's own variables are not the fence's
        self.maxDiff = None
        self.assertParity((new, old), 0)
        self.assertNotIn(b"tok-s", new["dump"] + new["stderr"])
        names = {l.split("=", 1)[0] for l in old["stdout"].splitlines()}
        for v in ("GIT_CONFIG_COUNT", "AS_SH_ORIG_SET", "AS_SH_ORIG_GH_HOST", "GIT_SSH_COMMAND"):
            self.assertIn(v, names)
        self.assertNotIn("GH_HOST", names)

    def test_nested_fence_keeps_the_outer_originals(self):
        env = {"GH_HOST": "corp.example"}
        # the inner fence is a second `sw as` the outer one runs
        new, old = self.pair("sh1ny", swharness.require_sw(), "as", "sh1ny", "bash", "-c",
                             'printf "%s|%s|%s" "$AS_SH_ORIG_GH_HOST" "${GH_HOST-unset}" "$AS_SH_ORIG_SET"', env=env)
        got = oracle_capture.document(self, new)
        self.assertEqual(got["stdout"], old["stdout"])
        self.assertEqual(new["code"], old["exit"])

    def test_the_command_exit_status_and_stdout_pass_through(self):
        self.assertParity(self.pair("sh1ny", "bash", "-c", 'printf %s "$1"; exit 7', "x", 'a "b" $c'), 7)
        # native-cli-launcher D3: the fence finds the command itself, so the name is bash's `exec` text no more
        new, old = self.pair("sh1ny", "no-such-tool")
        self.assertEqual((new["code"], old["exit"]), (127, 127))
        got = oracle_capture.document(self, new)
        self.assertEqual((got["stdout"], got["calls"]), (old["stdout"], old["calls"]))
        self.assertEqual(got["stderr"], old["stderr"])
        self.assertTrue(new["stderr"].decode("utf-8").strip().endswith("no-such-tool: command not found"), new["stderr"])


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
        self.git_env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", **PINNED_IDENTITY}

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
    def side(self, args, cwd):
        """sw's run of `pr <args>` (`args` may be a function of the side, "new", when a snapshot file belongs to it)."""
        e = self.env("me", SPECWRIGHT_HOME=str(self.home), SPECWRIGHT_STATE_DIR=str(self.tmp / "state-new"),
                     GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        code, out, err = run_sw(["pr", *(args("new") if callable(args) else args)], e, cwd or self.tmp)
        return {"code": code, "stdout": out, "stderr": err, "calls": calls_of(self.gh_log, lambda c: temp_names(c["argv"])),
                "state": self.gh_state.read_bytes()}

    def shape(self, doc, files):
        """`doc` with `message` left out, a `settings_problem` cut to its fixed prefix (`line N:`, else the text up to its first
        `: `) and a reviewer-config path replaced by a stand-in for the file's rules. With `files`, the path is sw's own and is read:
        its name is the SHA-256 of its bytes and it holds a `format` and the rules; a record has the path alone."""
        def walk(node):
            if isinstance(node, dict):
                return {k: (fixed_prefix(v) or v if k == "settings_problem" and isinstance(v, str) else walk(v))
                        for k, v in node.items() if k != "message"}
            if isinstance(node, list):
                return [walk(v) for v in node]
            if isinstance(node, str):
                m = CONFIG_PATH.search(node)
                if m:
                    if files:
                        raw = Path(node).read_bytes()
                        self.assertEqual(hashlib.sha256(raw).hexdigest(), m.group(1), "the name is the digest of the bytes")
                        rules = json.loads(raw.decode("utf-8"))
                        self.assertEqual(rules.pop("format"), 2)
                        self.assertIsInstance(rules["reviewers"], list)
                    return {"config": "<rules>"}
            return node
        return walk(doc)

    def normal(self, side):
        """(sw's JSON document, normalized the way `shape` says, its `message` or None)."""
        lines = side["stdout"].decode("utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1, side)
        doc = json.loads(lines[0])
        return self.shape(doc, True), doc.get("message")

    def run_pair(self, *args, cwd=None, code=None):
        """sw's run in `cwd` equals the next recorded run of the frozen side; returns sw's normalized document. `args` may be a
        function of the side when a snapshot file belongs to it. Free text is compared by its fixed prefix (spec:
        pr-script-runtime): `message`, every stderr line, and `settings_problem` (see shape)."""
        before = self.gh_state.read_bytes()
        calls_of(self.gh_log, lambda c: c)
        new = self.side(args[0] if len(args) == 1 and callable(args[0]) else args, cwd)
        self.gh_state.write_bytes(before)
        old = oracle_capture.recorded(self)[0]
        self.assertEqual(new["code"], old["exit"], f"exit codes differ\n{new}\n{old}")
        paths, canon = oracle_capture.Paths(self), oracle_capture.canon
        new_doc, new_msg = self.normal(new)
        old_doc, old_msg = self.shape(old["stdout"], False), old["stdout"].get("message")
        self.last_message = new_msg
        self.assertEqual(canon(paths.node(new_doc)), canon(old_doc), "JSON differs between sw and the record")
        self.assertEqual(new_msg is None, old_msg is None, f"`message` is on one side only\n{new_msg!r}\n{old_msg!r}")
        if old_msg is not None and fixed_prefix(old_msg):
            self.assertTrue(canon(paths.text(new_msg)).startswith(canon(fixed_prefix(old_msg))), f"message prefix differs: {new_msg!r} vs {old_msg!r}")
        got = oracle_capture.document(self, new)
        for key in ("calls", "state"):
            self.assertEqual(canon(got[key]), canon(old[key]), f"the {key} differ")
        self.assertEqual(got["stderr"]["lines"], old["stderr"]["lines"], f"stderr lines differ\n{new['stderr']}\n{old['stderr']}")
        for line, fixed in zip(said(new["stderr"]).decode("utf-8", "replace").splitlines(), old["stderr"]["prefixes"]):
            self.assertTrue(canon(paths.text(line)).startswith(canon(fixed)), f"stderr prefix differs: {line!r} vs {fixed!r}")
        if code is not None:
            self.assertEqual(old["exit"], code, old)
        return new_doc

    def new_side(self, args, cwd=None):
        """sw's answer alone, for a case whose outcome differs from the frozen side's by design: (exit code, its document, the
        raw side)."""
        side = self.side(args, cwd)
        lines = side["stdout"].decode("utf-8").strip().splitlines()
        return side["code"], (json.loads(lines[0]) if len(lines) == 1 else None), side

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
                                      "cheap_tier:\n  enabled: maybe\n", "cheap_tier: true\n", "pr:\n  merge_method: bogus\n"]):
            with self.subTest(settings=settings):
                self.run_pair("tier", "--code", self.repo(f"t{i}", settings=settings), code=0)

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: a directory name that is not UTF-8 needs Linux")
    def test_checkout_under_a_non_utf8_directory_is_not_utf8(self):
        # Direct entry (task 6.4): the runtime refuses an argument that is not UTF-8 before `main` (exit non-zero, empty stdout)
        # and nothing is run, so no gh call is made.
        code = self.repo(os.fsdecode(b"co-\xff"), settings="vcs: jj\nfinish: pr\ngithub:\n  login: me\n")
        for sub in ("vcs", "tier"):
            with self.subTest(sub=sub):
                new = self.side((sub, "--code", code), None)
                self.assertNotEqual(new["code"], 0, new)
                self.assertEqual(new["stdout"], b"")
                self.assertEqual(new["calls"], [], "no gh call before the refusal")

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
        """Both sides stop on a truthy section that is no mapping, with their own error (`internal_error`, exit 1 in the oracle;
        D5's `bad_setting`, exit 2 in the shim: test_refused_settings_are_a_listed_difference); an absent section is no stop."""
        for i, text in enumerate(("pr: oops\n", "pr: 5\n", "pr: true\n", "pr: [a]\n", "github: oops\n", "github:\n  review_request: oops\n")):
            code = self.repo(f"bad{i}", settings=text)
            self.assertEqual(oracle_capture.recorded(self)[0]["exit"], 1, text)
            new = self.side(["context", "--code", code], None)
            self.assertEqual(new["code"], 2, text)
            self.assertEqual(json.loads(new["stdout"])["error"], "bad_setting", text)
        for i, text in enumerate(("planning_store: oops\n", "pr:\ngithub:\n")):
            code = self.repo(f"empty{i}", settings=text)
            self.run_pair("context", "--code", code, code=0)

    def test_context_stops_and_problems(self):
        cases = [
            ("pr:\n  merge: agent\n  merge_method: bogus\n", 2), ("pr:\n  merge: agent\n  delete_branch: maybe\n", 2),
            ("pr:\n  settle: 30s\n", 0), ("pr:\n  settle: forever\n", 0),
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
        ]):
            with self.subTest(i=i):
                self.contents("main", main)
                self.contents(self.HEAD, head)
                self.run_pair(self.policy_args(), code=0)

    def test_policy_stops(self):
        self.contents("main", self.AGENT)
        self.contents(self.HEAD, None)
        self.run_pair(self.policy_args(), code=3)
        # a duplicate key and refused syntax: both sides refuse (the oracle's strict check, the shim's reader)
        for text in ("pr:\n  merge: user\n  merge: agent\n", "pr:\n  merge: [unterminated\n", "pr:\n\tmerge: agent\n"):
            self.contents(self.HEAD, text)
            self.run_pair(self.policy_args(), code=3)
        self.contents(self.HEAD, self.AGENT)
        self.contents("main", "pr:\n  merge: agent\n  merge_method: bogus\n")
        self.run_pair(self.policy_args(), code=2)
        self.contents("main", "pr:\n  merge: agent\n  settle: forever\n")
        self.run_pair(self.policy_args(), code=2)
        # a wrong shape is `lookup_failed` in the shim, where the oracle read it as empty (a listed difference)
        for text in ("pr: [a]\n", "pr: oops\n", "pr:\n  reviewers: [a, b]\n", "pr:\n  reviewers:\n    rev: [x]\n"):
            for main, head in ((text, self.AGENT), (self.AGENT, text)):
                with self.subTest(main=main, head=head):
                    self.contents("main", main)
                    self.contents(self.HEAD, head)
                    code, doc, raw = self.new_side(self.policy_args()("new"))
                    self.assertEqual((code, doc["error"]), (3, "lookup_failed"), raw)

    def test_policy_deep_nesting_is_lookup_failed(self):
        self.contents("main", self.AGENT)
        self.contents(self.HEAD, "a: " + "{a: " * 100000 + "1" + "}" * 100000 + "\n")
        code, doc, raw = self.new_side(self.policy_args()("new"))
        self.assertEqual((code, doc["error"]), (3, "lookup_failed"), raw)
        self.assertNotRegex(raw["stderr"].decode("utf-8", "replace") + raw["stdout"].decode("utf-8", "replace"),
                            r"(?i)stack ?overflow|traceback|\.dart:\d+")

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
        """The shim stops with `bad_setting`, exit 2, naming line 7 (the one reader, D4); the frozen oracle still reports the
        line as a soft `settings_problem` and exits 0."""
        text = "github:\n  login: me\nvalidate: make check\npr:\n  merge: user\n  reviewers:\n\trev: { role: required }\n"
        self.assertEqual(text.splitlines()[6][0], "\t")
        code = self.repo("tab", settings=text)
        status, doc, raw = self.new_side(["context", "--code", code])
        self.assertEqual((status, doc["ok"], doc["error"]), (2, False, "bad_setting"), raw)
        self.assertIn("line 7", doc["message"])
        old = oracle_capture.recorded(self)[0]
        self.assertEqual(old["exit"], 0)
        self.assertTrue(old["stdout"]["settings_problem"].startswith("line 7:"), old["stdout"])

    def test_refused_settings_are_a_listed_difference(self):
        """Settings the one reader refuses, or reads as YAML where the oracle skipped or misread them, are listed differences
        (spec: pr-script-runtime): each case gives the oracle's exit code and the shim's."""
        listed = [  # (args, settings text, oracle exit, shim exit, shim error)
            ("context", "pr:\n  merge: yes\n", 0, 2, "bad_setting"),
            ("context", "pr:\n  settle: 5m\n  react: No\n", 0, 2, "bad_setting"),
            ("context", "a: [\n", 0, 2, "bad_setting"),
            ("context", "pr:\n  merge: user\n  merge: agent\n", 0, 2, "bad_setting"),
            ("context", "pr:\n  reviewers:\n    r: { report: 3 }\n", 0, 2, "bad_setting"),
            ("context", "pr:\n  reviewers:\n    guard:\n      - role: required\n", 0, 2, "bad_setting"),
            ("context", "pr:\n  reviewers:\n    r: [x]\n", 0, 2, "bad_setting"),
            ("context", "pr: 0\n", 0, 2, "bad_setting"),
            ("vcs", "vcs: jj\npr:\n\tx: 1\n", 0, 2, "bad_setting"),
            ("tier", "cheap_tier:\n  enabled: yes\n", 0, 0, None),
        ]
        for i, (sub, text, old_code, new_code, error) in enumerate(listed):
            with self.subTest(sub=sub, settings=text):
                code = self.repo(f"listed{i}", settings=text)
                old = oracle_capture.recorded(self)[0]
                status, doc, raw = self.new_side([sub, "--code", code])
                self.assertEqual((old["exit"], status), (old_code, new_code), (old["stdout"], raw))
                if error:
                    self.assertEqual(doc["error"], error, raw)
        status, doc, raw = self.new_side(["tier", "--code", self.repo("listed-tier", settings="cheap_tier:\n  enabled: yes\n")])
        self.assertEqual((doc["cheap_tier"], "line 2" in doc["note"]), (False, True), raw)
        for i, (main, head, old_code, new_code) in enumerate([
            ("pr:\n  reviewers: [a, b]\n", self.AGENT, 0, 3), (self.AGENT, "pr:\n  reviewers: nope\n", 0, 3),
            (self.AGENT, "pr:\n  merge: agent\n  items:\n    - a\n", 3, 0),
            (self.AGENT, self.AGENT.replace("{ role: required }", "{ role: required, }"), 3, 0),
        ]):
            with self.subTest(i=i, main=main, head=head):
                self.contents("main", main)
                self.contents(self.HEAD, head)
                old = oracle_capture.recorded(self)[0]
                status, doc, raw = self.new_side(self.policy_args()("new"))
                self.assertEqual((old["exit"], status), (old_code, new_code), (old["stdout"], raw))

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
        """D3 and the one reader (the oracle refused a non-ASCII space; YAML reads it as text): a non-ASCII digit or space is
        part of a string, never a refusal on its own. Only the new side answers; a section that becomes a string stops."""
        nbsp, ideo, arab = chr(0xA0), chr(0x3000), "".join(chr(0x660 + int(d)) for d in "30")
        stops = "bad_setting"
        cases = [
            (f"pr:\n  settle: {arab}0s\n", 0, f"{arab}0s"),  # a string, not a duration: the default and a value problem
            (f"pr:\n  reviewers:\n    rev: {{ timeout: {arab}m }}\n", 0, None),
            (f"pr:\n  reviewers:\n    rev: {{ timeout: {chr(0xFF12)}{chr(0xFF10)}m }}\n", 0, None),
            (f"pr:\n{nbsp}{nbsp}merge: agent\n", 0, None),  # a key named with the space, not merge
            (f"pr:\n{ideo}merge: agent\n", 0, None),
            (f"pr:\n  merge:{nbsp}agent\n", stops, f"pr: merge:{chr(0xA0)}agent"),  # pr is the string the space joins
            (f"pr:\n  merge: agent{ideo}\n", 0, None),  # the value is a string that is not agent
            (f"pr:\n  settle:{ideo}2m{nbsp}\n", stops, "pr: settle:"),
            (f"pr:\n  reviewers:\n    rev:{ideo}{{ role: advisory }}\n", stops, "pr.reviewers.rev:"),
            (f"github:\n  login:{nbsp}me\n", stops, "github: login:"),
        ]
        for i, (text, want, shown) in enumerate(cases):
            with self.subTest(i=i):
                code, doc, _ = self.new_side(["context", "--code", self.repo(f"u{i}", settings=text)])
                if want == stops:
                    self.assertEqual((code, doc["error"]), (2, stops))
                    self.assertIn(shown, doc["message"])
                    continue
                self.assertEqual(code, 0, doc)
                self.assertEqual(doc["merge"], "user", "a space that is not YAML's never turns the policy on")
                if shown:
                    self.assertIn(shown, doc["settings_problem"])

    def test_policy_unicode_digits_and_spaces_in_settings(self):
        """The same string outcome on the remote read: a space that is not YAML's no longer leaves the policy unknown."""
        nbsp, ideo, arab = chr(0xA0), chr(0x3000), "".join(chr(0x660 + int(d)) for d in "30")
        for i, (text, want) in enumerate([(f"pr:\n  merge: agent\n  settle: {arab}0s\n", 2), (f"pr:\n{nbsp}merge: agent\n", 0),
                                          (f"pr:\n  merge: agent{ideo}\n  reviewers:\n    rev: {{ timeout: {arab}m }}\n", 0)]):
            with self.subTest(i=i):
                self.contents("main", text)
                self.contents(self.HEAD, self.AGENT)
                code, doc, _ = self.new_side(self.policy_args())
                self.assertEqual(code, want, doc)
                if want == 0:
                    self.assertEqual(doc["merge"], "user", "main's text never turns the policy on")
                else:
                    self.assertEqual(doc["error"], "bad_setting")

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
    the same material (native-cli-pr-pair D5, D8). stdout is compared as parsed JSON (sw writes compact JSON, the oracle spaced)
    but for the config digest, which each side checks against its own bytes and is masked in its field; exit codes are exact;
    stderr is compared by the `reviewers.py: ` prefix, line for line.

    Asserted differences from the oracle (native-cli-library-foundations, listed here and in the tests that assert them):
    - NaN, Infinity and -Infinity in the material, where the oracle still answers: Python's json.loads reads them, sw
      refuses the file (exit 1, empty stdout, one `reviewers.py: <material>: ` line); `refused=` below asserts it. A NaN
      clock (`cfg.now`) is refused by both, so it is no difference.
    - An abbreviated long option: argparse (the oracle) accepts a unique prefix, sw's one option rule will not
      (a usage stop, exit 2, nothing read; asserted by test_abbreviated_option_is_a_usage_stop_in_sw)."""

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

    def run_side(self, args):
        r = subprocess.run([self.sw, "pr", "reviewers", *args], capture_output=True, cwd=self.tmp, timeout=60, env=swharness.fixture_env())
        doc = parsed(r.stdout)
        return {"code": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "doc": doc.decode("utf-8", "replace") if isinstance(doc, bytes) else doc}

    def pair(self, cfg=None, material=None, head=None, code=None, extra=(), raw_config=None, check=False, crash=False,
             refused=False):
        """Run sw and read the record of the frozen run. `cfg` is a function of the format (1 for the frozen evaluator's file,
        2 for sw's) giving the config document, or `raw_config` a text both files hold as is; the frozen file is written but not
        run, its digest is the one the record holds. `check` runs --check-config instead of an evaluation. `refused` is the NaN
        difference: sw refuses the material (exit 1, no stdout, one `reviewers.py: <material>: ` line) where the frozen
        json.loads reads it (exit 0, or 1 when it then crashes: `crash`)."""
        digests = {}
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
            if cfg_path is not None and cfg_path.exists():
                digests[which] = hashlib.sha256(cfg_path.read_bytes()).hexdigest()
            if which == "new":
                new = self.run_side(args)
        if "new" in digests:
            new["doc"] = masked(new["doc"], digests["new"])
        old = oracle_capture.recorded(self)[0]
        if "old" in digests:
            old["stdout"] = masked(old["stdout"], digests["old"])
        if refused:
            self.assertEqual(old["exit"], 1 if crash else 0, old)
            self.assertEqual(new["code"], 1, new)
            self.assertEqual(new["stdout"], b"")
            lines = new["stderr"].decode("utf-8", "replace").splitlines()
            self.assertEqual(len(lines), 1, lines)
            self.assertTrue(lines[0].startswith(self.PREFIX + str(self.tmp / "new" / "mat.json") + ": "), lines)
            return new
        self.assertEqual(new["code"], old["exit"], f"exit codes differ\n{new}\n{old}")
        self.assertEqual(oracle_capture.canon(oracle_capture.Paths(self).node(new["doc"])), oracle_capture.canon(old["stdout"]),
                         "stdout documents differ between sw and the record")
        lines = new["stderr"].decode("utf-8", "replace").splitlines()
        if crash:  # the frozen evaluator dies on an uncaught exception (a Python defect, exit 1 all the same); sw states it in one line
            self.assertGreater(old["stderr"]["lines"], 1, old["stderr"])
            self.assertEqual(len(lines), 1, lines)
            self.assertTrue(lines[0].startswith(self.PREFIX), lines[0])
        else:
            self.assertEqual(len(lines), old["stderr"]["lines"], lines)
            for line in lines + old["stderr"]["prefixes"]:
                self.assertTrue(line.startswith(self.PREFIX), line)
        if code is not None:
            self.assertEqual(old["exit"], code, old)
        if code == 0 and not check and cfg is not None:
            self.assertIn("DIGEST", json.dumps(new["doc"]), "the digest was masked")
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

    def test_abbreviated_option_is_a_usage_stop_in_sw(self):
        """The oracle reads `--mat` as `--material`; sw has no abbreviations: exit 2, one usage line, no document (the
        material is readable, so reading it would have exited 0)."""
        mat = self.write("mat.json", tr.material({}), self.tmp / "new")
        new, old = self.run_side(["--mat", str(mat), "--head", tr.HEAD]), oracle_capture.recorded(self)[0]
        self.assertEqual(old["exit"], 0, old)
        self.assertEqual(new["code"], 2, new)
        self.assertEqual(new["stdout"], b"")
        lines = new["stderr"].decode("utf-8", "replace").splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(self.PREFIX + "usage"), lines)

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
        # The asserted difference: the oracle's json.loads reads NaN and Infinity, sw refuses the file naming it (exit 1)
        self.pair(cfg, dict(base, z_unused=float("nan")), refused=True)
        # a NaN clock is refused by both (exit 1, empty stdout, one `reviewers.py: <material>: ` line): no difference
        self.pair(cfg, dict(base, cfg={"since": tr.CUT, "now": float("nan")}), code=1)
        # the oracle crashes with an OverflowError traceback on an infinite clock (exit 1); sw refuses the file (exit 1)
        self.pair(cfg, dict(base, cfg={"since": tr.CUT, "now": float("inf")}), crash=True, refused=True)
        self.pair(cfg, dict(base, number=float("-inf")), refused=True)
        self.pair(cfg, tr.material({"rev-bot": [tr.comment("x", created=float("nan"))]}), refused=True)
        self.pair(cfg, json.dumps(dict(base, z_unused=0)).replace('"z_unused": 0', '"z_unused": NaN'), refused=True)
        # a truncated document is refused by both
        self.pair(cfg, '{"head_oid":"%s","z":NaN' % tr.HEAD, code=1)

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
        self.assertEqual(new["doc"]["logins"], ["b-bot", "a-bot"])
        self.pair(lambda fmt: self.config_for(fmt, *[self.rev("bot-%d" % i) for i in range(20)]), check=True, code=0)

    def test_usage_stops_exit_2(self):
        for extra in ([], ["--head", tr.HEAD], ["--material", "m.json"]):
            with self.subTest(extra=extra):
                new, old = self.run_side(extra), oracle_capture.recorded(self)[0]
                self.assertEqual((new["code"], old["exit"]), (2, 2))
                self.assertEqual(oracle_capture.canon(new["doc"]), oracle_capture.canon(old["stdout"]))
                self.assertTrue(new["stderr"].decode().startswith(self.PREFIX), new)
        new, old = self.run_side(["--check-config", "x.json", "--head", tr.HEAD]), oracle_capture.recorded(self)[0]
        self.assertEqual((new["code"], old["exit"]), (2, 2))


if __name__ == "__main__":
    unittest.main()
