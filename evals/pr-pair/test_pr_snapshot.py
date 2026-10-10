"""Tests of pr-snapshot.sh and pr-reply.sh against the fake gh, through the shared fixture in snapfix.py.

Run: python -m unittest discover evals/pr-pair -p test_pr_snapshot.py
"""
import json
import unittest

import snapfix
from snapfix import SnapCase, T0


def setUpModule():
    snapfix.banner()


class Smoke(SnapCase):
    def test_empty_pr_snapshot_parses(self):
        snap = self.snapshot()
        self.assertEqual((snap["viewer"], snap["number"], snap["state"], snap["head"], snap["head_oid"], snap["base"]),
                         ("me", 7, "OPEN", "feat/x", "a" * 40, "main"))
        self.assertEqual((snap["threads"], snap["comments"], snap["reviews"], snap["complete"]), ([], [], [], True))
        self.assertEqual(snap["checks"]["total"], 0)

    def test_evaluator_is_named(self):
        self.assertIn(snapfix.JQ_NAME, ("gojq", "jq"))

    def test_viewer_follows_gh_token(self):
        self.assertEqual(self.snapshot(login="rev")["viewer"], "rev")

    def test_items_added_by_helpers_are_listed_with_their_clock_times(self):
        tid, c = self.add_thread("rev", "fix this", resolved=False)
        self.advance(60)
        ic = self.add_comment("rev", "general remark")
        self.advance(60)
        rv = self.add_review("rev", "overall", state="CHANGES_REQUESTED")
        self.advance(60)
        self.edit(c["id"], "fix this, edited")
        snap = self.snapshot()
        t = snap["threads"][0]
        self.assertEqual((t["id"], t["root_id"], t["comments"][0]["body"], t["comments"][0]["at"], t["comments"][0]["edited"]),
                         (tid, c["databaseId"], "fix this, edited", T0, "2026-10-10T10:03:00Z"))
        self.assertEqual(t["rev"], f"{c['databaseId']}@2026-10-10T10:03:00Z")
        self.assertEqual([(x["id"], x["at"]) for x in snap["comments"]], [(ic["node_id"], "2026-10-10T10:01:00Z")])
        self.assertEqual([(x["id"], x["state"], x["at"]) for x in snap["reviews"]], [(rv["id"], "CHANGES_REQUESTED", "2026-10-10T10:02:00Z")])

    def test_reviewer_state_uses_the_fake_date_header(self):
        self.add_activity("a" * 40, T0)
        self.advance(30)
        snap = self.snapshot("--reviewer", "slowbot:required:60")
        self.assertEqual(snap["reviewers"][0]["state"], "waiting")
        self.advance(40)
        snap = self.snapshot("--reviewer", "slowbot:required:60")
        self.assertEqual((snap["reviewers"][0]["state"], snap["head_pushed_at"]), ("timed_out", T0))

    def test_reply_posts_a_marked_reply_and_resolves(self):
        tid, c = self.add_thread("rev", "please fix")
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--resolve", body="done")
        self.assertEqual(r.returncode, 0, r.stderr)
        t = self.st()["repos"]["o/n"]["pulls"][0]["threads"][0]
        self.assertEqual((t["isResolved"], len(t["comments"]), t["comments"][1]["author"]), (True, 2, "me"))
        self.assertIn(f"<!-- specwright:handled {tid} resolve -->", t["comments"][1]["body"])
        self.assertEqual(self.snapshot()["threads"], [], "a handled, resolved thread is not listed")

    def test_pr_comment_reply_is_listed_by_the_snapshot_as_mine(self):
        ic = self.add_comment("rev", "ping")
        r = self.reply("comment", ic["node_id"], "BODY", body="pong")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.snapshot()["comments"], [], "the marked reply handles the comment")
        mine = json.loads(self.gh_state.read_text(encoding="utf-8"))["repos"]["o/n"]["comments"]["7"][-1]
        self.assertEqual((mine["user"]["login"], mine["created_at"]), ("me", T0))


if __name__ == "__main__":
    unittest.main()
