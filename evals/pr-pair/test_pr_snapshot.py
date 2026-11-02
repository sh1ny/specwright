"""Tests of pr-snapshot.sh and pr-reply.sh against the fake gh, through the shared fixture in snapfix.py.

Run: python -m unittest discover evals/pr-pair -p test_pr_snapshot.py
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import snapfix
from snapfix import SnapCase, T0, rev
import bashexe  # noqa: E402


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
        snap = self.snapshot(*self.cfg(rev("slowbot", timeout=60)))
        self.assertEqual(snap["reviewers"][0]["state"], "waiting")
        self.advance(40)
        snap = self.snapshot(*self.cfg(rev("slowbot", timeout=60)))
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
MARK = "markbot"  # a reviewer with a marker rule: one comment, edited in place
MARKER = "<!-- walkthrough -->"
WALK = f"{MARKER}\nWalkthrough: looks fine"
SHA_PATTERN = "Reviewed commit:\\*\\* `([0-9a-f]{7,40})`"
D = "2026-10-10T"


class HeadCutoff(SnapCase):
    """Without the head's push in the activity log, reports count from the time a snapshot first saw the head."""

    def head_b(self, committed="09:00:00"):
        self.set_head(B, f"{D}{committed}Z")

    def revs(self, snap):
        return {r["login"]: r["state"] for r in snap["reviewers"]}

    def both(self, timeout=3600):
        """A marker reviewer and a reviewer with no report rule."""
        return self.cfg(rev(MARK, timeout=timeout, marker=MARKER), rev("genrev", timeout=timeout))

    def test_snapshot_cutoff_uses_push_time(self):
        self.head_b()
        self.add_activity(B, f"{D}11:00:00Z")
        c = self.add_comment(MARK, WALK, at=f"{D}10:00:00Z")  # posted for the old head, edited in place after the push
        self.edit(c["node_id"], WALK + " (B)", at=f"{D}11:30:00Z")
        self.set_clock(f"{D}12:00:00Z")
        snap = self.snapshot(*self.cfg(rev(MARK, marker=MARKER)))
        self.assertEqual(self.revs(snap), {MARK: "reported"})
        self.assertEqual(snap["reviewers"][0]["by"], "marker")
        self.assertEqual(snap["head_cutoff"], {"source": "push", "at": f"{D}11:00:00Z"})

    def test_snapshot_rejects_previous_head_reports_without_push_activity(self):
        self.head_b()
        self.add_comment(MARK, WALK, at=f"{D}10:00:00Z")
        self.add_comment("genrev", "looks good", at=f"{D}10:00:00Z")
        self.set_clock(f"{D}12:00:00Z")
        snap = self.snapshot(*self.both())
        self.assertEqual(self.revs(snap), {MARK: "waiting", "genrev": "waiting"})
        self.assertEqual(snap["head_cutoff"], {"source": "first_seen", "at": f"{D}12:00:00Z"})

    def test_snapshot_counts_report_after_first_seen(self):
        self.head_b()
        self.set_clock(f"{D}12:00:00Z")
        self.assertEqual(self.revs(self.snapshot(*self.both())), {MARK: "waiting", "genrev": "waiting"})
        self.add_comment("genrev", "looks good", at=f"{D}12:10:00Z")
        self.set_clock(f"{D}12:10:00Z")
        snap = self.snapshot(*self.both())
        self.assertEqual(self.revs(snap), {MARK: "waiting", "genrev": "reported"})
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
        self.assertEqual(self.revs(snap), {MARK: "timed_out", "genrev": "reported"})
        rec = self.state_dir / "heads" / "o" / "n" / "7" / B
        self.assertTrue(rec.is_file(), "the record is <state>/heads/<owner>/<name>/<pr>/<oid>")
        self.assertEqual([p.name for p in rec.parent.iterdir()], [B], "no temp file is left behind")

    def test_ordinary_snapshot_records_the_first_sighting(self):
        self.head_b()
        self.set_clock(f"{D}12:00:00Z")
        self.snapshot()  # no --reviewer: it still saw B at 12:00
        self.add_comment("genrev", "looks good", at=f"{D}12:10:00Z")
        self.set_clock(f"{D}12:40:00Z")
        snap = self.snapshot(*self.both())
        self.assertEqual(snap["head_cutoff"], {"source": "first_seen", "at": f"{D}12:00:00Z"})
        self.assertEqual(self.revs(snap)["genrev"], "reported")

    def test_ordinary_snapshot_survives_an_unwritable_state_dir(self):
        self.head_b()
        self.state_dir.write_text("a file, not a directory")
        snap = self.snapshot()
        self.assertEqual((snap["head_cutoff"], snap["reviewers"]), (None, []))

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
                self.assertEqual(self.revs(snap), {MARK: "waiting", "genrev": "waiting"})
                self.assertEqual(snap["head_cutoff"], {"source": "first_seen_unsaved", "at": f"{D}12:00:00Z"})

    def test_snapshot_sha_pattern_counts_without_push_activity(self):
        self.head_b()
        self.add_comment("shabot[bot]", f"**Reviewed commit:** `{B[:10]}`\nNo findings", at=f"{D}10:30:00Z")
        self.set_clock(f"{D}12:00:00Z")
        snap = self.snapshot(*self.cfg(rev("shabot", sha_pattern=SHA_PATTERN)))
        self.assertEqual(self.revs(snap), {"shabot": "reported"})
        self.assertEqual(snap["reviewers"][0]["by"], "sha_pattern")
        self.assertEqual(snap["head_cutoff"]["source"], "first_seen")


class ReviewerConfig(SnapCase):
    """--reviewer-config FILE: validated before any gh call; the evaluator (reviewers.py) decides, the script names no bot."""

    def refuse(self, *args, names=()):
        r = self.snapshot_run(*args)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "", "no snapshot printed")
        for n in names:
            self.assertIn(n, r.stderr)
        self.assertEqual(self.gh_calls(), [], "no gh call")

    def raw_config(self, reviewer, name="bad.json"):
        doc = {"format": 1, "reviewers": [reviewer]}
        path = self.tmp / name
        path.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")), encoding="utf-8", newline="\n")
        return snapfix.fixtures.posix(path)

    def test_bad_pattern_exits_2_without_gh(self):
        path = self.raw_config(rev("badbot", sha_pattern="([0-9a-f"))
        self.refuse("--reviewer-config", path, names=("badbot", "sha_pattern"))

    def test_unknown_report_key_exits_2_without_gh(self):
        path = self.raw_config(rev("keybot", checks="Bot Code Review"))
        self.refuse("--reviewer-config", path, names=("keybot", "checks"))

    def test_reviewer_flag_exits_2_naming_reviewer_config(self):
        self.refuse("--reviewer", "some-bot:required:1200", names=("--reviewer-config",))

    def test_missing_reviewer_config_exits_2_without_gh(self):
        self.refuse("--reviewer-config", snapfix.fixtures.posix(self.tmp / "nope.json"), names=("nope.json",))

    def test_snapshot_applies_config_check_rule(self):
        self.set_checks([run("tests"), run("Bot Code Review"), run("Other Review", state="IN_PROGRESS")])
        snap = self.snapshot(*self.cfg(rev("checkbot", check="Bot Code Review"), rev("quietbot", check="Other Review")))
        by = {r["login"]: r for r in snap["reviewers"]}
        self.assertEqual(sorted(by), ["checkbot", "quietbot"], "only config reviewers appear")
        self.assertEqual((by["checkbot"]["state"], by["checkbot"]["by"]), ("reported", "check"))
        self.assertEqual((by["quietbot"]["state"], by["quietbot"]["by"]), ("waiting", None))
        self.assertEqual(snap["checks"], {"total": 3, "pending": 1, "advisory_pending": 0, "ci_pending": 0, "failing": []})
        self.assertRegex(snap["reviewer_config"], "^[0-9a-f]{64}$")
        self.assertEqual(snap["now"], T0)
        self.assertEqual(by["checkbot"]["evidence"][0]["kind"], "check")

    def test_snapshot_without_a_config_has_no_reviewers(self):
        self.set_checks([run("tests", state="IN_PROGRESS")])
        snap = self.snapshot()
        self.assertEqual((snap["reviewers"], snap["reviewer_config"]), ([], None))
        self.assertEqual(snap["checks"]["ci_pending"], 1)

    def test_snapshot_with_fallback_config_reports_reviewers(self):
        # pr-pair.sh writes the config under the system temp dir when its state dir is unwritable; the snapshot reads it
        # from there while its own state dir is unwritable too
        self.head_b()
        d = Path(tempfile.mkdtemp())
        self.addCleanup(snapfix.fixtures.rmtree, d)
        path = self.write_config(rev("shabot", sha_pattern=SHA_PATTERN), rev("genrev"), where=d)
        self.state_dir.write_text("a file, not a directory")
        self.add_activity(B, f"{D}11:00:00Z")
        self.add_comment("shabot", f"**Reviewed commit:** `{B}`", at=f"{D}12:00:00Z")
        self.add_comment("genrev", "looks good", at=f"{D}12:05:00Z")
        self.set_clock(f"{D}12:10:00Z")
        snap = self.snapshot("--reviewer-config", path)
        self.assertEqual({r["login"]: r["state"] for r in snap["reviewers"]}, {"genrev": "reported", "shabot": "reported"})

    def test_material_temp_file_is_removed(self):
        scratch = self.tmp / "scratch"
        scratch.mkdir()
        self.snapshot(*self.cfg(rev("genrev")), env={"TMPDIR": snapfix.fixtures.posix(scratch)})
        self.assertEqual(list(scratch.iterdir()), [])

    def head_b(self):
        self.set_head(B, f"{D}09:00:00Z")


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
            "st = gh.read_state(p)\n"
            "gh.advance_clock(st, int(os.environ['FAKE_SLEEP_STEP']))\n"
            "for ev in json.loads(os.environ.get('FAKE_SLEEP_EVENTS', '[]')):\n"
            "    if st['clock'] >= ev['at'] and ev['key'] not in st.setdefault('fired', []):\n"
            "        st['fired'].append(ev['key'])\n"
            "        gh.add_pr_comment(st, 'o/n', 7, ev['author'], ev['body'], at=ev['at'])\n"
            "gh.write_state(p, st)\n", encoding="utf-8")
        sleep = self.tmp / "bin" / "sleep"
        sleep.write_text(f'#!/bin/sh\nexec "{snapfix.fixtures.posix(sys.executable)}" "{snapfix.fixtures.posix(helper)}"\n', encoding="utf-8", newline="\n")
        sleep.chmod(sleep.stat().st_mode | stat.S_IXUSR)
        self.state_dir.write_text("a file, not a directory")
        self.set_head(B, f"{D}09:00:00Z")
        self.add_comment("genrev", "old head: looks good", at=f"{D}10:00:00Z")  # before the first sighting: never counts
        self.set_clock(f"{D}12:00:00Z")

    def wait(self, events=()):
        env = {"FAKE_SLEEP_STEP": str(self.STEP), "FAKE_SLEEP_EVENTS": json.dumps(list(events))}
        r = self.snapshot_run("--wait", "--interval", "1", "--timeout", "7200",
                              *self.cfg(rev("genrev"), rev("silent", timeout=1200)), env=env)
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
    --timeout is elapsed time (bound-pr-scripts D5), so a run uses `--timeout 3 --interval 1` and takes seconds. No signals:
    every watcher ends by itself (timeout or exit 4)."""

    def setUp(self):
        super().setUp()
        sleep = self.tmp / "bin" / "sleep"
        sleep.write_text(f'#!/bin/sh\nexec "{snapfix.fixtures.posix(sys.executable)}" -c "import time; time.sleep(0.3)"\n',
                         encoding="utf-8", newline="\n")
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

    def start(self, slug, pr, timeout=3):
        env = self.env()
        p = subprocess.Popen([bashexe.bash(), str(snapfix.SNAPSHOT), str(pr), "--repo", slug, "--wait", "--interval", "1",
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
        b = self.start(self.SLUG, 7, timeout=3)
        rc_a, _, err_a = self.finish(a)
        self.assertEqual(rc_a, 4, err_a)
        self.assertIn("took over", err_a)
        rc_b, out_b, err_b = self.finish(b)
        self.assertEqual(rc_b, 0, err_b)
        self.assertEqual(json.loads(out_b.strip().splitlines()[-1])["wake"], "timeout")

    def test_watch_exit_leaves_a_newer_claim(self):
        a = self.start(self.SLUG, 7, timeout=3)
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
        b = self.start("acme/widget", 5, timeout=3)
        rc_a, _, err_a = self.finish(a)
        self.assertEqual(rc_a, 4, err_a)
        self.assertEqual(self.finish(b)[0], 0)

    def test_watch_without_a_state_dir_polls_unowned(self):
        self.state_dir.write_text("a file, not a directory")
        rc, out, err = self.finish(self.start(self.SLUG, 7, timeout=3))
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out.strip().splitlines()[-1])["wake"], "timeout")
        self.assertIn("ownership is off", err)


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


class WatchElapsed(SnapCase):
    """pr-watch: --timeout is elapsed time, and every poll, the first snapshot included, has one deadline.

    The per-poll deadline reads SPECWRIGHT_NET_DEADLINE (default 120 s); these tests set it to a few seconds and assert the
    spec's relations: the timeout is reported within the timeout plus one poll deadline plus 10 s. A `sleep` shim on PATH
    really sleeps, and on its first call merges FAKE_SLEEP_PATCH into the fake's state, so a poll can start hanging, or a
    failure can stop, after the first snapshot. Watchers write to files, so a hung fake gh that outlives a run cannot hold a
    pipe open; each run is stopped at 60 s."""

    # A poll is three gh calls, and each one starts bash, python and the fake gh: seconds on Windows, more under load. So
    # DEADLINE (and the timeouts below) must clear a normal poll by a wide margin; the relations asserted are the spec's.
    DEADLINE = 20
    CLAIMS = "watch/v2/o/n/7"

    def setUp(self):
        super().setUp()
        helper = self.tmp / "patchsleep.py"
        helper.write_text(
            "import json, os, sys, time\n"
            f"sys.path.insert(0, {str(snapfix.ROOT / 'evals' / 'fakes')!r})\n"
            "import gh\n"
            "p = os.environ['FAKE_GH_STATE']\n"
            "patch = json.loads(os.environ.get('FAKE_SLEEP_PATCH', '{}'))\n"
            "if patch and not os.path.exists(p + '.patched'):\n"
            "    st = gh.read_state(p)\n"
            "    st.update(patch)\n"
            "    gh.write_state(p, st)\n"
            "    open(p + '.patched', 'w').close()\n"
            "time.sleep(float(sys.argv[1]))\n", encoding="utf-8")
        sleep = self.tmp / "bin" / "sleep"
        sleep.write_text(f'#!/bin/sh\nexec "{snapfix.fixtures.posix(sys.executable)}" "{snapfix.fixtures.posix(helper)}" "$@"\n', encoding="utf-8", newline="\n")
        sleep.chmod(sleep.stat().st_mode | stat.S_IXUSR)
        self.pidf = self.tmp / "hang.pid"
        self.addCleanup(stop_pid_file, self.pidf)

    def hang_entry(self, match):
        return {"match": match, "pid_file": str(self.pidf)}

    def watch(self, *args, env=None, patch=None, then=None):
        """Run `pr-snapshot.sh PR --repo SLUG --wait args...`; (rc, stdout, stderr, seconds). `then(proc)` runs once the
        watcher has started, before waiting for it."""
        e = self.env(**{"SPECWRIGHT_NET_DEADLINE": str(self.DEADLINE), "FAKE_SLEEP_PATCH": json.dumps(patch or {}), **(env or {})})
        out, err = self.tmp / "w.out", self.tmp / "w.err"
        t = time.time()
        with open(out, "wb") as fo, open(err, "wb") as fe:
            p = subprocess.Popen([bashexe.bash(), str(snapfix.SNAPSHOT), str(self.PR), "--repo", self.SLUG, "--wait", *map(str, args)],
                                 stdout=fo, stderr=fe, env=e, cwd=self.tmp)
            try:
                if then:
                    then(p)
                rc = p.wait(timeout=60)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True) if os.name == "nt" else p.kill()
                p.wait()
                rc = -9
        took = time.time() - t
        return rc, out.read_text(encoding="utf-8", errors="replace"), err.read_text(encoding="utf-8", errors="replace"), took

    def graphql_calls(self):
        return len([c for c in self.gh_calls() if c[:2] == ["api", "graphql"]])

    def test_an_inherited_deadline_cannot_stretch_a_poll(self):
        # the deadline over one whole poll is capped at 120 s like each command's: SPECWRIGHT_NET_DEADLINE=999999 does not
        # move it (review round 9)
        start = time.time()
        rc, out, err, took = self.watch("--timeout", 1, "--interval", 1, env={"SPECWRIGHT_NET_DEADLINE": "999999"})
        self.assertEqual(rc, 0, err)
        ats = [json.loads(l)["deadline_at"] for l in self.gh_log.read_text(encoding="utf-8").splitlines()]
        ats = [float(a) for a in ats if a]
        self.assertTrue(ats, "a poll ran under a deadline")
        self.assertLessEqual(max(ats), int(start + took) + 120 + 1)

    def deadline_ats(self):
        """The SPECWRIGHT_NET_DEADLINE_AT every fake gh call of the run received."""
        ats = [json.loads(l)["deadline_at"] for l in self.gh_log.read_text(encoding="utf-8").splitlines()]
        return [float(a) for a in ats if a]

    def test_poll_fractional_net_deadline_lowers_poll(self):
        # spec "The deadline override is read one way": 1.5 lowers the poll's deadline, fractions included
        self.mutate(lambda st: st.update({"hang": [self.hang_entry("graphql")]}))
        start = time.time()
        rc, out, err, took = self.watch("--timeout", 1, "--interval", 1, env={"SPECWRIGHT_NET_DEADLINE": "1.5"})
        end = time.time()
        self.assertEqual(rc, 1, err)
        self.assertIn("deadline_exceeded", err)
        self.assertLess(took, 1.5 + 10)
        ats = self.deadline_ats()
        self.assertTrue(ats, "a poll ran under a deadline")
        self.assertLessEqual(max(ats), end + 1.5, "every command of the poll got a deadline at most 1.5 s from the poll's start")

    def _default_deadline(self, value):
        start = time.time()
        rc, out, err, took = self.watch("--timeout", 1, "--interval", 1, env={"SPECWRIGHT_NET_DEADLINE": value})
        end = time.time()
        self.assertEqual(rc, 0, err)
        ats = self.deadline_ats()
        self.assertTrue(ats, "a poll ran under a deadline")
        self.assertGreaterEqual(min(ats), start + 119, "the poll's deadline is 120 s")
        self.assertLessEqual(max(ats), end + 121)

    def test_poll_invalid_net_deadline_keeps_120(self):
        self._default_deadline("soon")

    def test_poll_net_deadline_above_120_capped(self):
        self._default_deadline("500")

    def test_slow_polls_count_toward_timeout(self):
        # spec: --timeout 60 --interval 20, polls of 15 s -> the timeout after at most 85 s, polled at most 4 times.
        # Scaled: --timeout 10 --interval 1, polls of 13 s or more (one call delayed 6 s). Counting polls would take 10 polls,
        # over 130 s; elapsed time is done after the first snapshot and one more poll at most.
        self.mutate(lambda st: st.update({"delay": [{"match": "rate_limit", "seconds": 6}]}))
        rc, out, err, took = self.watch("--timeout", 10, "--interval", 1, env={"SPECWRIGHT_NET_DEADLINE": "120"})
        self.assertEqual(rc, 0, err)
        doc = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(doc["wake"], "timeout")
        self.assertGreaterEqual(doc["waited"], 10)
        self.assertLess(took, 60, "elapsed time, not a count of polls")
        polls = len([c for c in self.gh_calls() if "rate_limit" in c])
        self.assertLessEqual(polls, 4, "polled no more than 4 times")

    def test_hung_polls_exit_1_within_bound(self):
        # spec: every gh call after the first snapshot never answers -> each poll stops at its deadline, exit 1
        rc, out, err, took = self.watch("--timeout", 20, "--interval", 1, patch={"hang": [self.hang_entry("graphql")]})
        self.assertEqual(rc, 1, err)
        self.assertIn("deadline_exceeded", err)
        self.assertIn("last poll failed", err)
        self.assertEqual(out, "")
        self.assertGreaterEqual(took, self.DEADLINE, "the poll hung until its deadline")
        self.assertLess(took, 20 + self.DEADLINE + 10)

    def test_takeover_during_hung_poll_exits_4(self):
        for timeout in (20, 600):  # 20: stops before reporting a timeout; 600: stops before the next poll
            with self.subTest(timeout=timeout):
                self.setUp()
                claims = self.state_dir / self.CLAIMS

                def claim_when_hung(p):
                    end = time.time() + 40
                    while not self.pidf.exists() and time.time() < end:
                        time.sleep(0.05)
                    claims.mkdir(parents=True, exist_ok=True)
                    (claims / "99999").write_text("", encoding="utf-8")  # a newer watcher's claim

                rc, out, err, took = self.watch("--timeout", timeout, "--interval", 1,
                                                patch={"hang": [self.hang_entry("graphql")]}, then=claim_when_hung)
                self.assertEqual(rc, 4, err)
                self.assertIn("took over", err)
                self.assertEqual(out, "")
                self.assertLess(took, 2 * self.DEADLINE + 15)
                self.assertLessEqual(self.graphql_calls(), 4, "no poll after the hung one")

    def test_first_snapshot_hung_exits_1(self):
        # spec: --timeout 30, the first snapshot's gh calls never answer -> deadline_exceeded, exit 1 within 30 + 120 + 10
        self.mutate(lambda st: st.update({"hang": [self.hang_entry("graphql")]}))
        rc, out, err, took = self.watch("--timeout", 2, "--interval", 1)
        self.assertEqual(rc, 1, err)
        self.assertIn("deadline_exceeded", err)
        self.assertIn("last poll failed", err)
        self.assertEqual(out, "")
        self.assertLess(took, 2 + self.DEADLINE + 10)

    def test_failed_first_snapshot_then_good_poll_becomes_the_base(self):
        # no base from a failed first snapshot; the first good poll is the base, so nothing counts as a change
        self.mutate(lambda st: st.update({"fail": [{"match": "graphql", "exit": 1, "stderr": "boom"}]}))
        rc, out, err, took = self.watch("--timeout", 15, "--interval", 1, patch={"fail": []},
                                        env={"SPECWRIGHT_NET_DEADLINE": "60"})
        self.assertEqual(rc, 0, err)
        doc = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(doc["wake"], "timeout")
        self.assertIn('"sig"', json.dumps(doc["snapshot"]), "a real snapshot, never an empty one")

    def test_failed_first_snapshot_then_incomplete_base_wakes_at_once(self):
        def many(st):
            for i in range(101):
                snapfix.fake_gh.add_thread(st, self.SLUG, self.PR, path="a.py", line=i + 1, thread_id=f"T{i}")
            st["fail"] = [{"match": "graphql", "exit": 1, "stderr": "boom"}]
        self.mutate(many)
        rc, out, err, took = self.watch("--timeout", 600, "--interval", 1, patch={"fail": []},
                                        env={"SPECWRIGHT_NET_DEADLINE": "60"})
        self.assertEqual(rc, 0, err)
        doc = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(doc["wake"], "incomplete")
        self.assertFalse(doc["snapshot"]["complete"])
        self.assertLess(took, 90, "woke at once, not at the timeout")


def run(name, state="COMPLETED", conclusion="SUCCESS"):
    """A raw CheckRun node for the fake's statusCheckRollup (state IN_PROGRESS has no conclusion)."""
    return {"__typename": "CheckRun", "name": name, "status": state,
            "conclusion": None if state != "COMPLETED" else conclusion}


PASS, PEND, FAIL = {}, {"state": "IN_PROGRESS"}, {"conclusion": "FAILURE"}


def checks(**by_name):
    """checks(a=PASS, b=PEND, c=FAIL) -> raw CheckRun nodes."""
    return [run(n, **kw) for n, kw in by_name.items()]


class TestUntilAttention(SnapCase):
    """pr-watch: `--wait --until attention` skips wakes that are only check progress (design D3).

    A `sleep` shim on PATH really sleeps 0.2 s, and on each call applies the next step of FAKE_STEPS to the fake's state
    ({"checks": [...]} | {"fields": {...}} | {"comment": [author, body]}), so the state changes between polls. Once the steps
    are spent the state stays as it is."""

    def setUp(self):
        super().setUp()
        helper = self.tmp / "steps.py"
        helper.write_text(
            "import json, os, sys, time\n"
            f"sys.path.insert(0, {str(snapfix.ROOT / 'evals' / 'fakes')!r})\n"
            "import gh\n"
            "p = os.environ['FAKE_GH_STATE']\n"
            "c = p + '.step'\n"
            "n = int(open(c).read()) if os.path.exists(c) else 0\n"
            "steps = json.loads(os.environ.get('FAKE_STEPS', '[]'))\n"
            "if n < len(steps):\n"
            "    st = gh.read_state(p)\n"
            "    s = steps[n]\n"
            "    pull = st['repos']['o/n']['pulls'][0]\n"
            "    if 'checks' in s:\n"
            "        pull['checks'] = s['checks']\n"
            "    if 'fields' in s:\n"
            "        pull.setdefault('fields', {}).update(s['fields'])\n"
            "    if 'comment' in s:\n"
            "        gh.add_pr_comment(st, 'o/n', 7, s['comment'][0], s['comment'][1])\n"
            "    gh.write_state(p, st)\n"
            "open(c, 'w').write(str(n + 1))\n"
            "time.sleep(0.2)\n", encoding="utf-8")
        sleep = self.tmp / "bin" / "sleep"
        sleep.write_text(f'#!/bin/sh\nexec "{snapfix.fixtures.posix(sys.executable)}" "{snapfix.fixtures.posix(helper)}" "$@"\n', encoding="utf-8", newline="\n")
        sleep.chmod(sleep.stat().st_mode | stat.S_IXUSR)

    def wait(self, baseline, steps, *args, timeout=120):
        """Run the watch with `--until attention`; the parsed wake line."""
        self.set_checks(baseline)
        r = self.snapshot_run("--wait", "--until", "attention", "--interval", "1", "--timeout", timeout, *args,
                              env={"FAKE_STEPS": json.dumps(steps)})
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_check_progress_is_filtered(self):
        # one of three pending passes; two still pending: keep waiting, and the timeout wake counts the skipped poll
        doc = self.wait(checks(a=PEND, b=PEND, c=PEND), [{"checks": checks(a=PASS, b=PEND, c=PEND)}], timeout=12)
        self.assertEqual(doc["wake"], "timeout")
        self.assertGreaterEqual(doc["filtered"], 1)

    def test_last_check_done_wakes(self):
        doc = self.wait(checks(a=PASS, b=PEND), [{"checks": checks(a=PASS, b=PASS)}])
        self.assertEqual(doc["wake"], "changed")
        self.assertEqual(doc["filtered"], 0)

    def test_new_failure_wakes(self):
        # a baseline-pending check fails while another is still pending
        doc = self.wait(checks(a=PEND, b=PEND), [{"checks": checks(a=FAIL, b=PEND)}])
        self.assertEqual(doc["wake"], "changed")

    def test_feedback_during_checks_wakes(self):
        doc = self.wait(checks(a=PEND, b=PEND), [{"comment": ["rev", "please change this"]}])
        self.assertEqual(doc["wake"], "changed")
        self.assertEqual(len(doc["snapshot"]["comments"]), 1)

    def test_dirty_wakes(self):
        doc = self.wait(checks(a=PEND, b=PEND), [{"fields": {"mergeStateStatus": "DIRTY"}}])
        self.assertEqual(doc["wake"], "changed")
        self.assertEqual(doc["snapshot"]["merge_state"], "DIRTY")

    def test_rerun_back_to_baseline_times_out(self):
        # every check passed; one is re-run (pending, filtered) and passes again: the snapshot equals the baseline
        doc = self.wait(checks(a=PASS, b=PASS), [{"checks": checks(a=PEND, b=PASS)}, {"checks": checks(a=PASS, b=PASS)}],
                        timeout=12)
        self.assertEqual(doc["wake"], "timeout")
        self.assertGreaterEqual(doc["filtered"], 1)

    def test_ci_done_wakes_while_reviewer_check_pending(self):
        # the last CI check passes while a reviewer's own check still runs: nothing but that check is pending, so wake
        doc = self.wait(checks(a=PEND, bot=PEND), [{"checks": checks(a=PASS, bot=PEND)}],
                        *self.cfg(rev("checkbot", check="bot")))
        self.assertEqual((doc["wake"], doc["filtered"]), ("changed", 0))
        self.assertEqual(doc["snapshot"]["checks"]["ci_pending"], 0)
        self.assertEqual(doc["snapshot"]["checks"]["pending"], 1)

    def test_reviewer_check_progress_alone_wakes(self):
        # no CI check pending; the reviewer's check is the only difference from the baseline
        doc = self.wait(checks(a=PASS, bot=PEND), [{"checks": checks(a=PASS, bot=PASS)}],
                        *self.cfg(rev("checkbot", check="bot")))
        self.assertEqual((doc["wake"], doc["filtered"]), ("changed", 0))
        self.assertEqual([r["state"] for r in doc["snapshot"]["reviewers"]], ["reported"])

    def test_ci_progress_with_a_reviewer_config_is_filtered(self):
        doc = self.wait(checks(a=PEND, b=PEND, bot=PEND), [{"checks": checks(a=PASS, b=PEND, bot=PEND)}],
                        *self.cfg(rev("checkbot", check="bot")), timeout=12)
        self.assertEqual(doc["wake"], "timeout")
        self.assertGreaterEqual(doc["filtered"], 1)

    def test_wake_works_on_compact_evaluator_output(self):
        r_args = self.cfg(rev("checkbot", check="bot"))
        self.set_checks(checks(a=PEND, bot=PEND))
        r = self.snapshot_run("--wait", "--until", "attention", "--interval", "1", "--timeout", 120, *r_args,
                              env={"FAKE_STEPS": json.dumps([{"comment": ["rev", "please change this"]}])})
        self.assertEqual(r.returncode, 0, r.stderr)
        line = r.stdout.strip().splitlines()[-1]
        self.assertNotIn('": ', line, "compact JSON, no spaces after the colons")
        doc = json.loads(line)
        self.assertEqual(doc["wake"], "changed")
        snap = doc["snapshot"]
        self.assertEqual(len(snap["comments"]), 1)
        self.assertRegex(snap["reviewer_config"], "^[0-9a-f]{64}$")
        self.assertEqual(set(snap["checks"]), {"total", "pending", "advisory_pending", "ci_pending", "failing"})
        self.assertTrue({"reviewers", "now", "reviewer_config", "sig", "attn"} <= set(snap))
        self.assertEqual(line.count('"sig":"'), 1)

    def test_without_until_a_check_passing_wakes(self):
        self.set_checks(checks(a=PEND, b=PEND))
        r = self.snapshot_run("--wait", "--interval", "1", "--timeout", 120,
                              env={"FAKE_STEPS": json.dumps([{"checks": checks(a=PASS, b=PEND)}])})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1])["wake"], "changed")

    def test_bad_until_exits_2_without_gh(self):
        for args in (("--wait", "--until", "quiet"), ("--until", "attention")):
            with self.subTest(args=args):
                r = self.snapshot_run(*args)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("--until", r.stderr)
                self.assertNotIn("unknown argument", r.stderr)
                self.assertEqual(self.gh_calls(), [], "no gh call")


class LookupLimits(SnapCase):
    """A named limit on the clock or push-time lookup fails the snapshot; it never takes that lookup's fallback (review
    round 3: an activity timeout must not turn the push cutoff into first_seen)."""

    def setUp(self):
        super().setUp()
        self.pidf = self.tmp / "hang.pid"
        self.addCleanup(stop_pid_file, self.pidf)
        self.set_head(B, f"{D}09:00:00Z")
        self.add_activity(B, f"{D}11:00:00Z")
        self.set_clock(f"{D}12:00:00Z")

    def hung(self, match, *args):
        self.mutate(lambda st: st.update({"hang": [{"match": match, "pid_file": str(self.pidf)}]}))
        return self.snapshot_run(*args, env={"SPECWRIGHT_NET_DEADLINE": "4"})

    def assert_failed(self, r, command):
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn(f"deadline_exceeded: {command}", r.stderr)
        self.assertEqual(r.stdout.strip(), "")
        heads = self.state_dir / "heads"
        self.assertEqual([p for p in heads.rglob("*") if p.is_file()] if heads.exists() else [], [], "no first_seen record")

    def test_activity_lookup_limit_fails_the_snapshot(self):
        self.assert_failed(self.hung("activity", *self.cfg(rev(MARK, marker=MARKER))), "gh api")

    def test_clock_lookup_limit_fails_the_snapshot(self):
        self.assert_failed(self.hung("rate_limit", *self.cfg(rev(MARK, marker=MARKER))), "gh api")

    def test_clock_lookup_limit_fails_a_snapshot_without_reviewers(self):
        self.assert_failed(self.hung("rate_limit"), "gh api")


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
