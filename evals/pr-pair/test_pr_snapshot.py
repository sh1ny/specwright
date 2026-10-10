"""Tests of pr-snapshot.sh and pr-reply.sh against the fake gh, through the shared fixture in snapfix.py.

Run: python -m unittest discover evals/pr-pair -p test_pr_snapshot.py
"""
import json
import stat
import subprocess
import time
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

    def test_snapshot_reaction_does_not_answer_a_raced_edit(self):
        ic = self.add_comment("rev", "ping")
        rv = self.add_review("rev", "looks off")
        snap = self.snapshot()
        judged = {x["id"]: x["rev"] for x in snap["comments"] + snap["reviews"]}
        self.advance(5)
        self.edit(ic["node_id"], "ping, edited")  # both edits land after the re-read ...
        self.edit(rv["id"], "looks off, edited")
        self.advance(1)
        for item in (ic["node_id"], rv["id"]):  # ... and before the reply and its reaction
            self.add_comment("me", self.mark(item, judged[item]))
            self.react(item, "me")
        after = self.snapshot()
        self.assertEqual([x["id"] for x in after["comments"]], [ic["node_id"]], "the reaction came with the stale reply")
        self.assertEqual([x["id"] for x in after["reviews"]], [rv["id"]])
        self.advance(5)
        self.edit(ic["node_id"], "ping, edited again")  # a follow-up edit after the reply ...
        self.add_comment("me", self.mark(ic["node_id"], self.snapshot()["comments"][0]["rev"]))
        self.advance(5)
        self.edit(ic["node_id"], "ping, one more")
        self.advance(1)
        self.react(ic["node_id"], "me")  # ... is answered by a reaction alone
        self.assertEqual(self.snapshot()["comments"], [])

    def test_snapshot_later_edit_does_not_fake_a_rebound(self):
        tid, c = self.add_thread("rev", "please fix")  # t0
        self.advance(5)
        self.edit(c["id"], "please fix, edited")  # t1, before the judgement
        judged = self.snapshot()["threads"][0]["rev"]
        self.advance(5)
        self.add_reply(tid, "me", self.mark(tid, judged, resolve=True))  # t2: answers the text as of t1
        self.resolve_thread(tid)
        self.advance(5)
        self.edit(c["id"], "please fix, edited twice")  # t3 overwrites lastEditedAt
        self.advance(1)
        self.react(c["id"], "me")  # the second edit is acknowledged
        self.assertEqual(self.snapshot()["threads"], [], "the reply matched the thread it answered")

    def test_snapshot_signature_follows_a_rebound_thread_resolution(self):
        tid, c = self.add_thread("rev", "please fix")
        judged = self.snapshot()["threads"][0]["rev"]
        self.advance(5)
        self.edit(c["id"], "please fix, and more")
        self.advance(1)
        self.add_reply(tid, "me", self.mark(tid, judged))
        before = self.snapshot()
        self.resolve_thread(tid)
        after = self.snapshot()
        self.assertEqual((before["threads"][0]["rebound"], after["threads"][0]["resolved"]), (True, True))
        self.assertNotEqual(before["sig"], after["sig"], "--wait wakes when the rebound thread is resolved")

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


class WatchOwnership(SnapCase):
    """pr-watch: the newest --wait owns a PR (a directory of numbered claims under <state>/watch/v2/<owner>/<name>/<pr>/).

    Watchers are real processes against the fake gh. A `sleep` shim on PATH sleeps 0.3 s whatever the interval, and
    --timeout counts polls, so a run takes seconds. No signals: every watcher ends by itself (timeout or exit 4)."""

    def setUp(self):
        super().setUp()
        sleep = self.tmp / "bin" / "sleep"
        sleep.write_text('#!/bin/sh\nexec python -c "import time; time.sleep(0.3)"\n', encoding="utf-8", newline="\n")
        sleep.chmod(sleep.stat().st_mode | stat.S_IXUSR)
        self.procs = []
        self.addCleanup(self._reap)

    def _reap(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.communicate()

    def add_repo(self, slug, pr):
        def f(st):
            p = self._pull()
            p.update({"number": pr, "html_url": f"https://github.com/{slug}/pull/{pr}"})
            st["repos"][slug] = {"pulls": [p]}
        self.mutate(f)

    def start(self, slug, pr, timeout=6):
        env = self.env()
        p = subprocess.Popen(["bash", str(snapfix.SNAPSHOT), str(pr), "--repo", slug, "--wait", "--interval", "1",
                              "--timeout", str(timeout)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             encoding="utf-8", env=env, cwd=self.tmp)
        self.procs.append(p)
        return p

    def finish(self, p):
        out, err = p.communicate(timeout=90)
        return p.returncode, out, err

    def calls(self):
        return len(self.gh_calls())

    def until(self, cond, what):
        end = time.time() + 60
        while time.time() < end:
            if cond():
                return
            time.sleep(0.05)
        self.fail(f"timed out waiting for {what}")

    def claims(self, owner="o", name="n", pr=7):
        d = self.state_dir / "watch" / "v2" / owner / name / str(pr)
        return sorted(x.name for x in d.iterdir()) if d.is_dir() else []

    def test_watch_newer_watcher_takes_over(self):
        a = self.start(self.SLUG, 7, timeout=60)
        self.until(lambda: self.calls() > 0, "A's first snapshot")
        b = self.start(self.SLUG, 7, timeout=5)
        rc_a, _, err_a = self.finish(a)
        self.assertEqual(rc_a, 4, err_a)
        self.assertIn("took over", err_a)
        rc_b, out_b, err_b = self.finish(b)
        self.assertEqual(rc_b, 0, err_b)
        self.assertEqual(json.loads(out_b.strip().splitlines()[-1])["wake"], "timeout")

    def test_watch_exit_leaves_a_newer_claim(self):
        a = self.start(self.SLUG, 7, timeout=4)
        self.until(lambda: self.calls() > 0, "A's first snapshot")
        d = self.state_dir / "watch" / "v2" / "o" / "n" / "7"
        d.mkdir(parents=True, exist_ok=True)
        (d / "99999").write_text("", encoding="utf-8")  # a newer watcher's claim
        rc, _, err = self.finish(a)
        self.assertEqual(rc, 4, err)
        self.assertEqual(self.claims(), ["99999"], "A gave up only its own claim")

    def test_watch_reused_claim_number_does_not_revive_an_old_owner(self):
        # A claims; B claims, removes A's claim and exits; C finds the directory empty and takes A's old number.
        a = self.start(self.SLUG, 7, timeout=60)
        self.until(lambda: self.calls() > 0, "A's first snapshot")
        d = self.state_dir / "watch" / "v2" / "o" / "n" / "7"
        (old,) = self.claims()
        for f in d.iterdir():
            f.unlink()
        (d / old.split("-")[0]).write_text("", encoding="utf-8")  # C's claim, under A's number
        rc, _, err = self.finish(a)
        self.assertEqual(rc, 4, err)
        self.assertEqual(self.claims(), [old.split("-")[0]], "A's exit left C's claim")

    def test_watch_simultaneous_claims_leave_one_owner(self):
        a, b = self.start(self.SLUG, 7), self.start(self.SLUG, 7)
        rcs = sorted([self.finish(a)[0], self.finish(b)[0]])
        self.assertEqual(rcs, [0, 4])

    def test_watch_claim_beats_a_crashed_owner(self):
        d = self.state_dir / "watch" / "v2" / "o" / "n" / "7"
        d.mkdir(parents=True)
        (d / "9").write_text("", encoding="utf-8")  # killed without cleanup; 9 < 10 only numerically
        rc, out, err = self.finish(self.start(self.SLUG, 7, timeout=3))
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out.strip().splitlines()[-1])["wake"], "timeout")
        self.assertEqual(self.claims(), [], "the crashed owner's claim was beaten and the new one released")

    def test_watch_keys_do_not_alias_hyphenated_identities(self):
        self.add_repo("acme-tools/widget", 5)
        self.add_repo("acme/tools-widget", 5)
        a = self.start("acme-tools/widget", 5)
        self.until(lambda: self.calls() > 0, "A's first snapshot")
        b = self.start("acme/tools-widget", 5)
        (rc_a, _, err_a), (rc_b, _, err_b) = self.finish(a), self.finish(b)
        self.assertEqual((rc_a, rc_b), (0, 0), f"{err_a} / {err_b}")

    def test_watch_key_ignores_case(self):
        self.add_repo("Acme/Widget", 5)
        self.add_repo("acme/widget", 5)
        a = self.start("Acme/Widget", 5, timeout=60)
        self.until(lambda: self.calls() > 0, "A's first snapshot")
        b = self.start("acme/widget", 5, timeout=4)
        rc_a, _, err_a = self.finish(a)
        self.assertEqual(rc_a, 4, err_a)
        self.assertEqual(self.finish(b)[0], 0)

    def test_watch_without_a_state_dir_polls_unowned(self):
        self.state_dir.write_text("a file, not a directory")
        rc, out, err = self.finish(self.start(self.SLUG, 7, timeout=3))
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out.strip().splitlines()[-1])["wake"], "timeout")
        self.assertIn("ownership is off", err)


class ClippedBodies(SnapCase):
    """A body the snapshot shortened says so (`clipped`), and --full reads it whole."""

    def full(self, item_id, *args):
        return self.run_script(snapfix.SNAPSHOT, "--full", item_id, "--repo", self.SLUG, *args)

    def test_snapshot_marks_a_clipped_review(self):
        self.add_review("rev", "r" * 5000)
        review = self.snapshot()["reviews"][0]
        self.assertTrue(review["clipped"])
        self.assertLess(len(review["body"]), 5000)
        self.assertTrue(review["body"].startswith("r" * 1200))

    def test_snapshot_marks_clipped_thread_comments_and_comments(self):
        self.add_thread("rev", "t" * 3000)
        self.add_comment("rev", "c" * 1500)
        snap = self.snapshot()
        self.assertIs(snap["threads"][0]["comments"][0]["clipped"], True)
        self.assertIs(snap["comments"][0]["clipped"], True)

    def test_snapshot_body_at_the_limit_is_not_clipped(self):
        self.add_comment("rev", "c" * 1200)
        comment = self.snapshot()["comments"][0]
        self.assertEqual((comment["body"], comment["clipped"]), ("c" * 1200, False))

    def test_snapshot_stripping_html_comments_is_not_clipping(self):
        self.add_thread("rev", "short <!-- " + "h" * 4000 + " --> text")
        self.add_review("rev", "<!-- " + "h" * 4000 + " -->ok")
        snap = self.snapshot()
        self.assertEqual(snap["threads"][0]["comments"][0]["clipped"], False)
        self.assertEqual((snap["reviews"][0]["body"], snap["reviews"][0]["clipped"]), ("ok", False))

    def test_snapshot_sig_does_not_depend_on_clipped(self):
        self.add_comment("rev", "c" * 1200)
        self.assertNotIn("clipped", self.snapshot()["sig"])

    def test_full_prints_the_unclipped_body(self):
        raw = "x" * 5000
        tid, tc = self.add_thread("rev", raw)
        ic = self.add_comment("rev", raw)
        rv = self.add_review("rev", raw)
        self.advance(60)
        self.edit(ic["node_id"], raw + "!")
        for item, kind, body, rev in (
                (tc, "thread_comment", raw, T0),
                (ic, "comment", raw + "!", "2026-10-10T10:01:00Z"),
                (rv, "review", raw, T0)):
            nid = item.get("node_id") or item["id"]
            r = self.full(nid)
            self.assertEqual(r.returncode, 0, r.stderr)
            lines = r.stdout.strip().splitlines()
            self.assertEqual(len(lines), 1, r.stdout)
            out = json.loads(lines[0])
            self.assertEqual(out, {"ok": True, "id": nid, "kind": kind, "body": body, "rev": rev, "url": out["url"]})
            self.assertTrue(out["url"].startswith("https://github.com/o/n/pull/7#"), out["url"])

    def test_full_rev_prefers_the_edit_time(self):
        tid, tc = self.add_thread("rev", "first")
        rv = self.add_review("rev", "first")
        self.advance(60)
        self.edit(tc["id"], "second")
        self.edit(rv["id"], "second")
        for nid in (tc["id"], rv["id"]):
            self.assertEqual(json.loads(self.full(nid).stdout)["rev"], "2026-10-10T10:01:00Z")

    def test_full_unknown_id_is_not_found(self):
        r = self.full("PRR_nope")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(json.loads(r.stdout), {"ok": False, "error": "not_found"})

    def test_full_a_read_failure_exits_3(self):
        rv = self.add_review("rev", "r" * 5000)
        self.mutate(lambda st: st.update({"fail": ["graphql"]}))
        r = self.full(rv["id"])
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(r.stdout.strip(), "")

    def test_full_needs_no_reviewer_and_no_watch_claim(self):
        rv = self.add_review("rev", "r" * 5000)
        r = self.full(rv["id"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.state_dir / "watch").exists())
        self.assertFalse(any("reviewThreads" in " ".join(c) for c in self.gh_calls()), "ran the snapshot query")


if __name__ == "__main__":
    unittest.main()
