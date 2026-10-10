"""Tests of pr-reply.sh --rev against the fake gh, through the shared fixture in snapfix.py.

A reply is posted only for the revision that was judged: with --rev the script re-reads the item through node(id) and
refuses (exit 5) when the revision changed, or exits 3 when it cannot be read. Without --rev it behaves as in 0.1.10.

Run: python -m unittest discover evals/pr-pair -p test_pr_reply.py
"""
import unittest

import snapfix
from snapfix import SnapCase, fake_gh


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


if __name__ == "__main__":
    unittest.main()
