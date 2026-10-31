"""Tests of pr-reply.sh --rev against the fake gh, through the shared fixture in snapfix.py.

A reply is posted only for the revision that was judged: with --rev the script re-reads the item through node(id) and
refuses (exit 5) when the revision changed, or exits 3 when it cannot be read. Without --rev it behaves as in 0.1.10.

Run: python -m unittest discover evals/pr-pair -p test_pr_reply.py
"""
import os
import stat
import subprocess
import sys
import time
import unittest

import snapfix
from snapfix import SnapCase, fake_gh, fixtures
import bashexe  # noqa: E402


def setUpModule():
    snapfix.banner()


class ReplyCase(SnapCase):
    def thread_state(self):
        return self.st()["repos"]["o/n"]["pulls"][0]["threads"][0]

    def node_reads(self):
        return [c for c in self.gh_calls() if any("node(id" in a for a in c)]

    def rev_of(self, c):
        return f"{c['databaseId']}@{c['lastEditedAt'] or c['createdAt']}"

    def assert_untouched(self, tid, n=1):
        t = self.thread_state()
        self.assertEqual((t["isResolved"], len(t["comments"])), (False, n), "nothing posted, nothing resolved")
        self.assertEqual(self.st().get("nodes", {}), {}, "nothing reacted")
        self.assertFalse([c for c in self.gh_calls() if any("replies" in a or "resolveReviewThread" in a or "addReaction" in a
                                                            for a in c)], "no write call was made")


class ReplyRev(ReplyCase):
    def test_reply_with_matching_rev_posts_and_resolves(self):
        tid, c = self.add_thread("rev", "please fix")
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--resolve", "--rev", self.rev_of(c), body="done")
        self.assertEqual(r.returncode, 0, r.stderr)
        t = self.thread_state()
        self.assertEqual((t["isResolved"], len(t["comments"])), (True, 2))
        self.assertIn(f"<!-- specwright:handled {tid} resolve rev={self.rev_of(c)} -->", t["comments"][1]["body"])
        self.assertEqual(len(self.node_reads()), 1, "one node read per reply")

    def test_reply_refuses_a_changed_rev(self):
        tid, c = self.add_thread("rev", "please fix")
        judged = self.rev_of(c)
        self.advance(30)
        self.edit(c["id"], "please fix, actually this")
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--resolve", "--react", "+1", "--rev", judged, body="done")
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertIn(f"judged {judged}, now {c['databaseId']}@{self.clock()}", r.stderr)
        self.assert_untouched(tid)

    def test_reply_exits_3_when_the_item_is_unreadable(self):
        tid, c = self.add_thread("rev", "please fix")
        self.mutate(lambda st: st.update({"fail": [{"match": r"node\(id", "exit": 1, "stderr": "boom"}]}))
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--resolve", "--rev", self.rev_of(c), body="done")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assert_untouched(tid)

    def test_reply_refuses_a_thread_too_long_to_reread(self):
        tid, c = self.add_thread("rev", "please fix")
        last = self.mutate(lambda st: [fake_gh.add_thread_comment(st, self.SLUG, self.PR, tid, "rev", f"note {i}")
                                       for i in range(99)][-1])
        judged = self.rev_of(last)  # the thread as judged: 100 comments
        self.add_reply(tid, "rev", "one more thing")  # the 101st is past the re-read's first page
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--resolve", "--rev", judged, body="done")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("101 comments", r.stderr)
        self.assert_untouched(tid, n=101)

    def test_resolve_retry_after_a_posted_reply_takes_a_fresh_rev(self):
        tid, c = self.add_thread("rev", "please fix")
        judged = self.rev_of(c)
        self.mutate(lambda st: st.update({"fail": [{"match": "resolveReviewThread", "exit": 1, "stderr": "boom"}]}))
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--resolve", "--rev", judged, body="done")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("fresh snapshot", r.stderr, "the retry hint must not suggest the judged rev")
        self.mutate(lambda st: st.update({"fail": []}))
        self.assertEqual(self.reply("resolve", tid, "--rev", judged).returncode, 5, "your own reply changed the thread's rev")
        t = self.snapshot()["threads"][0]
        self.assertTrue(t["resolve_pending"])
        r = self.reply("resolve", tid, "--rev", t["rev"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.thread_state()["isResolved"])

    def test_reply_without_rev_posts_as_before(self):
        tid, c = self.add_thread("rev", "please fix")
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--resolve", body="done")
        self.assertEqual(r.returncode, 0, r.stderr)
        t = self.thread_state()
        self.assertEqual((t["isResolved"], len(t["comments"])), (True, 2))
        self.assertIn(f"<!-- specwright:handled {tid} resolve -->", t["comments"][1]["body"])
        self.assertEqual(self.node_reads(), [], "no re-read without --rev")


class ReplyRevKinds(ReplyCase):
    """The revision from a real snapshot is accepted unchanged, for every kind; an edit after it is refused."""

    def test_snapshot_rev_of_a_thread_is_accepted_then_refused_after_an_edit(self):
        tid, c = self.add_thread("rev", "please fix")
        rev = self.snapshot()["threads"][0]["rev"]
        self.advance(10)
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--rev", rev, body="first")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.advance(10)
        self.edit(c["id"], "changed")
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--rev", rev, body="second")
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertEqual(len(self.thread_state()["comments"]), 2, "the second reply was not posted")

    def test_snapshot_rev_of_a_comment_and_a_review_is_accepted_then_refused_after_an_edit(self):
        ic = self.add_comment("rev", "ping")
        rv = self.add_review("rev", "overall")
        snap = self.snapshot()
        self.assertEqual(len(snap["comments"]), 1)
        self.assertEqual(len(snap["reviews"]), 1)
        self.advance(10)
        for kind, item in (("comment", snap["comments"][0]), ("comment", snap["reviews"][0])):
            r = self.reply(kind, item["id"], "BODY", "--rev", item["rev"], body="ok")
            self.assertEqual(r.returncode, 0, r.stderr)
        self.advance(10)
        self.edit(ic["node_id"], "ping, edited")
        self.edit(rv["id"], "overall, edited")
        for item in (snap["comments"][0], snap["reviews"][0]):
            r = self.reply("comment", item["id"], "BODY", "--rev", item["rev"], body="late")
            self.assertEqual(r.returncode, 5, r.stderr)
            self.assertIn(f"judged {item['rev']}, now ", r.stderr)
        self.assertEqual(len(self.st()["repos"]["o/n"]["comments"]["7"]), 3, "two replies posted, none after the edits")

    def test_resolve_with_rev_checks_the_thread(self):
        tid, c = self.add_thread("rev", "ok thanks")
        rev = self.snapshot()["threads"][0]["rev"]
        self.advance(10)
        self.edit(c["id"], "wait, no")
        r = self.reply("resolve", tid, "--rev", rev)
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertFalse(self.thread_state()["isResolved"])
        fresh = self.snapshot()["threads"][0]["rev"]
        r = self.reply("resolve", tid, "--rev", fresh)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.thread_state()["isResolved"])

    def test_waiting_marker_carries_the_rev(self):
        tid, c = self.add_thread("rev", "please fix")
        rev = self.rev_of(c)
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--waiting", "--rev", rev, body="later")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"<!-- specwright:waiting {tid} rev={rev} -->", self.thread_state()["comments"][1]["body"])


class ReplyBody(ReplyCase):
    """A reply is never posted without its body: the body file is checked before any GitHub call."""

    def test_reply_body_then_marker(self):
        tid, c = self.add_thread("rev", "please fix")
        r = self.reply("thread", tid, c["databaseId"], "BODY", body="done, thanks")
        self.assertEqual(r.returncode, 0, r.stderr)
        body = self.thread_state()["comments"][1]["body"]
        self.assertTrue(body.startswith("done, thanks"), body)
        self.assertEqual(body.rstrip("\n").splitlines()[-1], f"<!-- specwright:handled {tid} -->")

    def refused(self, r, path):
        self.assertEqual(r.returncode, 4, "a reply without its body exits 4, not 2 (a pending review)")
        self.assertIn(str(path), r.stderr, "stderr names the body file")
        self.assertEqual(self.gh_calls(), [], "no GitHub request at all")

    def test_reply_refuses_missing_body_file(self):
        tid, c = self.add_thread("rev", "please fix")
        path = fixtures.posix(self.tmp / "nope.md")
        self.refused(self.reply("thread", tid, c["databaseId"], path), path)
        self.refused(self.reply("comment", "IC_x", path), path)

    def test_reply_refuses_missing_body_file_without_repo(self):
        """Without --repo the script resolves the repository through gh: that must wait until the body is checked."""
        tid, c = self.add_thread("rev", "please fix")
        path = fixtures.posix(self.tmp / "nope.md")
        self.refused(self.reply("thread", tid, c["databaseId"], path, repo=False), path)
        self.refused(self.reply("comment", "IC_x", path, repo=False), path)

    def test_bad_arguments_are_refused_before_any_github_call(self):
        for args in (("thread", "T", "1"), ("comment", "IC_x"), ("react", "IC_x"), ("react", "IC_x", "+2"),
                     ("resolve",), ("nope",)):
            for repo in (True, False):
                r = self.reply(*args, repo=repo)
                self.assertEqual(r.returncode, 4, (args, repo, r.stderr))
                self.assertEqual(self.gh_calls(), [], (args, repo, "no GitHub request at all"))

    def test_reply_refuses_empty_body_file(self):
        tid, c = self.add_thread("rev", "please fix")
        path = fixtures.posix(self.tmp / "empty.md")
        (self.tmp / "empty.md").write_bytes(b"")
        self.refused(self.reply("thread", tid, c["databaseId"], path), path)
        self.refused(self.reply("comment", "IC_x", path), path)

    def test_reply_refuses_unreadable_body_file(self):
        tid, c = self.add_thread("rev", "please fix")
        f = self.tmp / "locked.md"
        f.write_text("secret", encoding="utf-8")
        f.chmod(0)
        self.addCleanup(f.chmod, stat.S_IRUSR | stat.S_IWUSR)
        if os.access(f, os.R_OK) or os.name == "nt":
            self.skipTest("platform: chmod cannot make a file unreadable here (Windows, or running as a user that bypasses permissions)")
        path = fixtures.posix(f)
        self.refused(self.reply("thread", tid, c["databaseId"], path), path)
        self.refused(self.reply("comment", "IC_x", path), path)


class ReplyMarkerWrite(ReplyCase):
    """The reply with its marker is written in full before any GitHub call, and a failed write says so."""

    def fake_mktemp(self, path):
        f = self.tmp / "bin" / "mktemp"
        f.write_text(f'#!/bin/sh\necho "{path}"\n', encoding="utf-8", newline="\n")
        f.chmod(0o755)

    def test_failed_marker_write_makes_no_github_call(self):
        tid, c = self.add_thread("rev", "please fix")
        self.fake_mktemp(fixtures.posix(self.tmp / "no-such-dir" / "reply.md"))  # cat > it fails
        f = self.tmp / "body.md"
        f.write_text("done", encoding="utf-8")
        path = fixtures.posix(f)
        for args in (("thread", tid, c["databaseId"], path, "--resolve", "--rev", self.rev_of(c)),
                     ("comment", "IC_x", path, "--rev", "x")):
            r = self.reply(*args)
            self.assertEqual(r.returncode, 4, (args, r.stderr))
            self.assertIn(path, r.stderr, "stderr names the body file")
            self.assertIn("nothing was posted", r.stderr)
            self.assertEqual(self.gh_calls(), [], (args, "no GitHub request at all"))
        self.assert_untouched(tid)


class ReplyTempFiles(ReplyCase):
    """Every temp file the script makes is gone when it exits, on every path."""

    def setUp(self):
        super().setUp()
        self.tmpdir = self.tmp / "tmpdir"
        self.tmpdir.mkdir()
        self.extra_env["TMPDIR"] = fixtures.posix(self.tmpdir)

    def leftovers(self):
        return sorted(p.name for p in self.tmpdir.iterdir())

    def test_reply_leaves_no_temp_file_on_success(self):
        tid, c = self.add_thread("rev", "please fix")
        self.assertEqual(self.reply("thread", tid, c["databaseId"], "BODY", body="done").returncode, 0)
        self.assertEqual(self.reply("comment", "IC_x", "BODY", body="ok").returncode, 0)
        self.assertEqual(self.leftovers(), [])

    def test_reply_leaves_no_temp_file_when_post_fails(self):
        tid, c = self.add_thread("rev", "please fix")
        self.mutate(lambda st: st.update({"fail": [{"match": "replies", "exit": 1, "stderr": "boom"}]}))
        r = self.reply("thread", tid, c["databaseId"], "BODY", body="done")
        self.assertNotEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.thread_state()["comments"]), 1, "nothing was posted")
        self.assertEqual(self.leftovers(), [])

    def test_reply_leaves_no_temp_file_on_pending_review_stop(self):
        tid, c = self.add_thread("rev", "please fix")
        gh = self.tmp / "bin" / "gh"
        (self.tmp / "bin" / "gh-real").write_text(gh.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        (self.tmp / "bin" / "gh-real").chmod(0o755)
        helper = self.tmp / "pend.py"  # after a posted reply, the viewer gains a pending review
        helper.write_text(
            "import json, sys\n"
            f"sys.path.insert(0, {fixtures.posix(snapfix.ROOT / 'evals' / 'fakes')!r})\n"
            "import gh\n"
            "p = sys.argv[1]\n"
            "st = json.load(open(p, encoding='utf-8'))\n"
            f"gh.add_review(st, {self.SLUG!r}, {self.PR}, 'me', 'draft', state='PENDING')\n"
            "json.dump(st, open(p, 'w', encoding='utf-8'))\n", encoding="utf-8")
        gh.write_text('#!/bin/sh\n"$(dirname "$0")/gh-real" "$@" || exit $?\n'
                      f'case "$*" in *replies*) "{fixtures.posix(sys.executable)}" "{fixtures.posix(helper)}" "$FAKE_GH_STATE";; esac\n',
                      encoding="utf-8", newline="\n")
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--resolve", body="done")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("pending", r.stderr)
        self.assertEqual(len(self.thread_state()["comments"]), 2, "the reply was posted before the stop")
        self.assertEqual(self.leftovers(), [])



def stop_pid_file(pid_file):
    """Stop a hung fake gh by the PID it wrote (never by name); a no-op when it is gone."""
    try:
        with open(pid_file, encoding="utf-8") as f:
            pid = int(f.read())
    except (OSError, ValueError):
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


class Bounded(ReplyCase):
    """bound-pr-scripts D1: every gh call of pr-reply.sh runs under a deadline, and the script still cleans up."""

    DEADLINE = 2

    def test_reply_hung_gh_deadline_exceeded_no_temp_file(self):
        tid, c = self.add_thread("rev", "please fix")
        pidf = self.tmp / "hang.pid"
        self.addCleanup(stop_pid_file, pidf)
        self.mutate(lambda st: st.update({"hang": [{"match": "replies", "pid_file": str(pidf)}]}))  # the reply POST
        temp = self.tmp / "fresh-temp"
        temp.mkdir()
        body = self.tmp / "body.md"
        body.write_text("done", encoding="utf-8", newline=chr(10))
        env = self.env(SPECWRIGHT_NET_DEADLINE=str(self.DEADLINE), TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
        out, err = self.tmp / "r.out", self.tmp / "r.err"
        t = time.time()
        with open(out, "wb") as fo, open(err, "wb") as fe:  # files, so an unbounded hung gh cannot hold a pipe open
            p = subprocess.Popen([bashexe.bash(), str(snapfix.REPLY), str(self.PR), "thread", tid, str(c["databaseId"]),
                                  fixtures.posix(body), "--repo", self.SLUG], stdout=fo, stderr=fe, env=env, cwd=self.tmp)
            try:
                rc = p.wait(timeout=45)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True) if os.name == "nt" else p.kill()
                p.wait()
                rc = -9
        took = time.time() - t
        stderr = err.read_text(errors="replace")
        self.assertNotIn(rc, (0, -9), stderr)
        self.assertIn("deadline_exceeded", stderr)
        self.assertIn("gh api", stderr, "the limit line names the command")
        self.assertLess(took, self.DEADLINE + 10)
        self.assertEqual(self.thread_state()["comments"][1:], [], "nothing was posted")
        self.assertEqual(list(temp.iterdir()), [], "the body temp file is removed")


if __name__ == "__main__":
    unittest.main()
