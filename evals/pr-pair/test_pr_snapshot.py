"""Tests of pr-snapshot.sh and pr-reply.sh against the fake gh, through the shared fixture in snapfix.py.

Run: python -m unittest discover evals/pr-pair -p test_pr_snapshot.py
"""
import json
import stat
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


class MarkerBinding(SnapCase):
    """A handled marker with `rev=` answers an item only while the item still has that revision."""

    def mark(self, item, rev=None, resolve=False, kind="handled"):
        tail = f"{' resolve' if resolve else ''}{f' rev={rev}' if rev else ''}"
        return "done" + chr(10) * 2 + f"<!-- specwright:{kind} {item}{tail} -->"

    def resolve_thread(self, tid):
        self.mutate(lambda st: next(t for t in st["repos"]["o/n"]["pulls"][0]["threads"] if t["id"] == tid).update(isResolved=True))

    def test_snapshot_relists_comment_edited_before_bound_reply(self):
        ic = self.add_comment("rev", "ping")
        judged = self.snapshot()["comments"][0]["rev"]
        self.advance(5)
        self.edit(ic["node_id"], "ping, edited")  # lands after the re-read ...
        self.advance(1)
        self.add_comment("me", self.mark(ic["node_id"], judged))  # ... and before the reply
        listed = self.snapshot()["comments"]
        self.assertEqual([(x["id"], x["rev"]) for x in listed], [(ic["node_id"], "2026-10-10T10:00:05Z")])

    def test_snapshot_relists_resolved_thread_as_rebound(self):
        tid, c = self.add_thread("rev", "please fix")
        judged = self.snapshot()["threads"][0]["rev"]
        self.advance(5)
        self.edit(c["id"], "please fix, and more")
        self.advance(1)
        self.add_reply(tid, "me", self.mark(tid, judged, resolve=True))
        self.resolve_thread(tid)
        t = self.snapshot()["threads"]
        self.assertEqual(len(t), 1, "the resolved thread is listed again")
        self.assertEqual((t[0]["id"], t[0]["resolved"], t[0]["rebound"], t[0]["awaiting_reviewer"]), (tid, True, True, False))

    def test_snapshot_bound_reply_keeps_items_answered(self):
        ic = self.add_comment("rev", "ping")
        tid, c = self.add_thread("rev", "please fix")
        snap = self.snapshot()
        self.advance(5)
        self.add_comment("me", self.mark(ic["node_id"], snap["comments"][0]["rev"]))
        self.add_reply(tid, "me", self.mark(tid, snap["threads"][0]["rev"]))
        after = self.snapshot()
        self.assertEqual(after["comments"], [], "a bound reply to the current revision answers the comment")
        self.assertEqual([(t["id"], t["rebound"], t["awaiting_reviewer"]) for t in after["threads"]], [(tid, False, True)])

    def test_snapshot_legacy_marker_uses_the_time_rule(self):
        ic = self.add_comment("rev", "ping")
        self.advance(5)
        self.edit(ic["node_id"], "ping, edited")
        self.advance(5)
        self.add_comment("me", self.mark(ic["node_id"]))  # a 0.1.10 marker: no rev=
        self.assertEqual(self.snapshot()["comments"], [], "edited before the reply: handled")
        self.advance(5)
        self.edit(ic["node_id"], "ping, edited again")
        self.assertEqual([x["id"] for x in self.snapshot()["comments"]], [ic["node_id"]], "edited after the reply: listed")

    def test_snapshot_waiting_marker_follows_the_same_binding(self):
        ic = self.add_comment("rev", "ping")
        judged = self.snapshot()["comments"][0]["rev"]
        self.advance(5)
        self.add_comment("me", self.mark(ic["node_id"], judged, kind="waiting"))
        self.assertTrue(self.snapshot()["comments"][0]["waiting_owner"], "bound to the current revision: still waiting")
        ic2 = self.add_comment("rev", "pong")
        judged2 = self.snapshot()["comments"][-1]["rev"]
        self.advance(5)
        self.edit(ic2["node_id"], "pong, edited")  # edited before the reply, which is bound to the older text
        self.advance(5)
        self.add_comment("me", self.mark(ic2["node_id"], judged2, kind="waiting"))
        later = {x["id"]: x for x in self.snapshot()["comments"]}
        self.assertFalse(later[ic2["node_id"]]["waiting_owner"], "a waiting reply bound to an older revision does not hold the item")


A, B = "a" * 40, "b" * 40
MIRA = "kintsugimira"
WALK = "<!-- mira-walkthrough -->\nWalkthrough: looks fine"
D = "2026-10-10T"


class HeadCutoff(SnapCase):
    """Without the head's push in the activity log, reports count from the time a snapshot first saw the head."""

    def head_b(self, committed="09:00:00"):
        self.set_head(B, f"{D}{committed}Z")

    def revs(self, snap):
        return {r["login"]: r["state"] for r in snap["reviewers"]}

    def both(self, timeout=3600):
        return ["--reviewer", f"{MIRA}:required:{timeout}", "--reviewer", f"genrev:required:{timeout}"]

    def test_snapshot_cutoff_uses_push_time(self):
        self.head_b()
        self.add_activity(B, f"{D}11:00:00Z")
        self.add_comment(MIRA, WALK, at=f"{D}11:30:00Z")
        self.set_clock(f"{D}12:00:00Z")
        snap = self.snapshot("--reviewer", f"{MIRA}:required:3600")
        self.assertEqual(self.revs(snap), {MIRA: "reported"})
        self.assertEqual(snap["head_cutoff"], {"source": "push", "at": f"{D}11:00:00Z"})

    def test_snapshot_rejects_previous_head_reports_without_push_activity(self):
        self.head_b()
        self.add_comment(MIRA, WALK, at=f"{D}10:00:00Z")
        self.add_comment("genrev", "looks good", at=f"{D}10:00:00Z")
        self.set_clock(f"{D}12:00:00Z")
        snap = self.snapshot(*self.both())
        self.assertEqual(self.revs(snap), {MIRA: "waiting", "genrev": "waiting"})
        self.assertEqual(snap["head_cutoff"], {"source": "first_seen", "at": f"{D}12:00:00Z"})

    def test_snapshot_counts_report_after_first_seen(self):
        self.head_b()
        self.set_clock(f"{D}12:00:00Z")
        self.assertEqual(self.revs(self.snapshot(*self.both())), {MIRA: "waiting", "genrev": "waiting"})
        self.add_comment("genrev", "looks good", at=f"{D}12:10:00Z")
        self.set_clock(f"{D}12:10:00Z")
        snap = self.snapshot(*self.both())
        self.assertEqual(self.revs(snap), {MIRA: "waiting", "genrev": "reported"})
        self.assertEqual(snap["head_cutoff"], {"source": "first_seen", "at": f"{D}12:00:00Z"})

    def test_snapshot_first_seen_persists_across_processes(self):
        self.head_b()
        self.set_clock(f"{D}12:00:00Z")
        self.snapshot(*self.both(1800))  # process 1 saw B at 12:00 and exited
        self.add_comment("genrev", "looks good", at=f"{D}12:20:00Z")
        self.set_clock(f"{D}12:40:00Z")
        snap = self.snapshot(*self.both(1800))  # a new process, 40 minutes later
        self.assertEqual(snap["head_cutoff"], {"source": "first_seen", "at": f"{D}12:00:00Z"})
        # 12:00 is the cutoff (the 12:20 comment counts) and the timeout start (30 minutes are over)
        self.assertEqual(self.revs(snap), {MIRA: "timed_out", "genrev": "reported"})
        rec = self.state_dir / "heads" / "o" / "n" / "7" / B
        self.assertTrue(rec.is_file(), "the record is <state>/heads/<owner>/<name>/<pr>/<oid>")
        self.assertEqual([p.name for p in rec.parent.iterdir()], [B], "no temp file is left behind")

    def test_snapshot_removes_sibling_heads_once_the_record_is_published(self):
        d = self.state_dir / "heads" / "o" / "n" / "7"
        d.mkdir(parents=True)
        (d / A).write_text("Fri, 10 Oct 2026 08:00:00 GMT\n")
        self.head_b()
        self.set_clock(f"{D}12:00:00Z")
        self.snapshot(*self.both())
        self.assertEqual(sorted(p.name for p in d.iterdir()), [B])

    def test_snapshot_first_seen_unsaved_keeps_process_time(self):
        for how in ("unwritable", "unparseable"):
            with self.subTest(how):
                self.setUp()
                self.head_b()
                self.add_comment("genrev", "looks good", at=f"{D}10:00:00Z")
                self.set_clock(f"{D}12:00:00Z")
                if how == "unwritable":
                    self.state_dir.write_text("a file, not a directory")
                else:
                    d = self.state_dir / "heads" / "o" / "n" / "7"
                    d.mkdir(parents=True)
                    (d / B).write_text("not a date\n")
                snap = self.snapshot(*self.both())
                self.assertEqual(self.revs(snap), {MIRA: "waiting", "genrev": "waiting"})
                self.assertEqual(snap["head_cutoff"], {"source": "first_seen_unsaved", "at": f"{D}12:00:00Z"})

    def test_snapshot_codex_sha_counts_without_push_activity(self):
        self.head_b()
        self.add_comment("chatgpt-codex-connector[bot]", f"**Reviewed commit:** `{B[:10]}`\nNo findings", at=f"{D}10:30:00Z")
        self.set_clock(f"{D}12:00:00Z")
        snap = self.snapshot("--reviewer", "chatgpt-codex-connector:required:3600")
        self.assertEqual(self.revs(snap), {"chatgpt-codex-connector": "reported"})
        self.assertEqual(snap["head_cutoff"]["source"], "first_seen")


class WaitUnwritable(SnapCase):
    """--wait with a state directory that cannot be created: the watcher's own first sighting is kept across polls.

    A fake `sleep` on PATH moves the fake clock by FAKE_SLEEP_STEP seconds per poll instead of sleeping, and adds the
    scheduled comments once the clock reaches them, so the run is deterministic and needs no signals."""

    STEP = 300

    def setUp(self):
        super().setUp()
        helper = self.tmp / "fakesleep.py"
        helper.write_text(
            "import json, os, sys\n"
            f"sys.path.insert(0, {str(snapfix.ROOT / 'evals' / 'fakes')!r})\n"
            "import gh\n"
            "p = os.environ['FAKE_GH_STATE']\n"
            "st = json.load(open(p, encoding='utf-8'))\n"
            "gh.advance_clock(st, int(os.environ['FAKE_SLEEP_STEP']))\n"
            "for ev in json.loads(os.environ.get('FAKE_SLEEP_EVENTS', '[]')):\n"
            "    if st['clock'] >= ev['at'] and ev['key'] not in st.setdefault('fired', []):\n"
            "        st['fired'].append(ev['key'])\n"
            "        gh.add_pr_comment(st, 'o/n', 7, ev['author'], ev['body'], at=ev['at'])\n"
            "json.dump(st, open(p, 'w', encoding='utf-8', newline='\\n'), indent=2)\n", encoding="utf-8")
        sleep = self.tmp / "bin" / "sleep"
        sleep.write_text(f'#!/bin/sh\nexec python "{snapfix.fixtures.posix(helper)}"\n', encoding="utf-8", newline="\n")
        sleep.chmod(sleep.stat().st_mode | stat.S_IXUSR)
        self.state_dir.write_text("a file, not a directory")
        self.set_head(B, f"{D}09:00:00Z")
        self.add_comment("genrev", "old head: looks good", at=f"{D}10:00:00Z")  # before the first sighting: never counts
        self.set_clock(f"{D}12:00:00Z")

    def wait(self, events=()):
        env = {"FAKE_SLEEP_STEP": str(self.STEP), "FAKE_SLEEP_EVENTS": json.dumps(list(events))}
        r = self.snapshot_run("--wait", "--interval", "1", "--timeout", "7200", "--reviewer", "genrev:required:3600",
                              "--reviewer", "silent:required:1200", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout.strip().splitlines()[-1])
        return out, {x["login"]: x["state"] for x in out["snapshot"]["reviewers"]}

    def test_wait_unwritable_state_reports_and_times_out(self):
        # the report at 12:10: the poll right after it sees it
        out, states = self.wait([{"at": f"{D}12:10:00Z", "author": "genrev", "body": "looks good", "key": "g"}])
        self.assertEqual((out["wake"], states), ("changed", {"genrev": "reported", "silent": "waiting"}))
        self.assertEqual(out["snapshot"]["head_cutoff"], {"source": "first_seen_unsaved", "at": f"{D}12:00:00Z"})
        self.assertEqual(self.clock(), f"{D}12:10:00Z")
        # the same watcher without a report: the timeout runs from the first sighting, not from each poll
        self.setUp()
        out, states = self.wait()
        self.assertEqual((out["wake"], states), ("changed", {"genrev": "waiting", "silent": "timed_out"}))
        self.assertEqual(self.clock(), f"{D}12:20:00Z", "the first poll at or after 12:20 timed it out")
        self.assertEqual(out["snapshot"]["head_cutoff"], {"source": "first_seen_unsaved", "at": f"{D}12:00:00Z"})


if __name__ == "__main__":
    unittest.main()
