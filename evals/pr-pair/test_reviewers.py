"""Tests for skills/specwright-pr/scripts/reviewers.py, the reviewer-detection evaluator behind pr-snapshot.sh.

Material and config fixtures go in (written to a tempdir per test); a compact snapshot comes out.

Run: python -m unittest evals/pr-pair/test_reviewers.py
"""
import base64
import calendar
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SCRIPT = ROOT / "skills" / "specwright-pr" / "scripts" / "reviewers.py"

HEAD = "1a2b3c4d" + "e" * 32
PREV = "a" * 40
CUT = "2026-01-01T00:10:00Z"
CUT_EPOCH = calendar.timegm(time.strptime(CUT, "%Y-%m-%dT%H:%M:%SZ"))


def iso(offset, base=CUT_EPOCH):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base + offset))


def reviewer(login, role="required", timeout=1200, report=None):
    r = {"login": login, "role": role, "timeout": timeout}
    if report is not None:
        r["report"] = report
    return r


def config(*reviewers):
    return {"format": 1, "reviewers": list(reviewers)}


def item(kind, body="", created=None, edited=None, state=None, commit=None, id="1"):
    return {"kind": kind, "id": id, "body": body, "created": created or iso(60), "edited": edited,
            "state": state, "commit": commit}


def review(commit, body="", created=None, state="COMMENTED", id="r1"):
    return item("review", body, created, None, state, commit, id)


def comment(body, created=None, edited=None, id="c1", kind="comment"):
    return item(kind, body, created, edited, None, None, id)


def material(items=None, since=CUT, now_offset=120, checks_all=None, head=HEAD, extra=None):
    m = {"viewer": "me", "number": 7, "head_oid": head,
         "checks": {"total": len(checks_all or []), "failing": []},
         "comments": [], "head_cutoff": since,
         "cfg": {"since": since, "now": CUT_EPOCH + now_offset},
         "checks_all": checks_all or [],
         "material": items or {},
         "sig_base": "SIG", "attn_base": "ATTN"}
    if extra:
        m.update(extra)
    return m


def check(name, state="pass", app="github-actions"):
    return {"name": name, "state": state, "app": app, "at": iso(30)}


class Base(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name)

    def write(self, name, obj):
        p = self.tmp / name
        if isinstance(obj, bytes):
            p.write_bytes(obj)
        elif isinstance(obj, str):
            p.write_text(obj, encoding="utf-8")
        else:
            p.write_text(json.dumps(obj, separators=(",", ":")), encoding="utf-8")
        return p

    def run_py(self, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                              encoding="utf-8", timeout=60)

    def snap(self, cfg, mat, head=None, raw=False):
        args = []
        if cfg is not None:
            args += ["--config", self.write("cfg.json", cfg)]
        args += ["--material", self.write("mat.json", mat), "--head", head or mat["head_oid"]]
        r = self.run_py(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout if raw else json.loads(r.stdout)

    def rv(self, cfg, mat, login="rev-bot"):
        out = self.snap(cfg, mat)
        return next(x for x in out["reviewers"] if x["login"] == login)

    def one(self, rev, items=None, **kw):
        """Run a single-reviewer config; items go under that reviewer's login."""
        items = {rev["login"]: items} if items is not None else {}
        return self.rv(config(rev), material(items, **kw), rev["login"])

    def bad_config(self, cfg, *needles):
        r = self.run_py("--check-config", self.write("bad.json", cfg))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout, "")
        for n in needles:
            self.assertIn(n, r.stderr)
        # the evaluate mode refuses the same config the same way
        r2 = self.run_py("--config", self.tmp / "bad.json", "--material", self.write("m.json", material()), "--head", HEAD)
        self.assertEqual(r2.returncode, 2, r2.stderr)
        self.assertEqual(r2.stdout, "")


class GenericRules(Base):
    def test_review_on_head_reports_whatever_the_cutoff(self):
        rev = reviewer("rev-bot")
        r = self.one(rev, [review(HEAD, created=iso(-3600))])
        self.assertEqual((r["state"], r["by"]), ("reported", "review"))
        r = self.one(rev, [review(HEAD, created=iso(-3600))], since=None)
        self.assertEqual((r["state"], r["by"]), ("reported", "review"))

    def test_review_on_older_commit_is_waiting(self):
        r = self.one(reviewer("rev-bot"), [review(PREV, created=iso(-60))])
        self.assertEqual((r["state"], r["by"]), ("waiting", None))

    def test_pending_review_never_counts(self):
        r = self.one(reviewer("rev-bot"), [review(HEAD, state="PENDING")])
        self.assertEqual(r["state"], "waiting")

    def test_app_check_without_rule_does_not_report(self):
        out = self.snap(config(reviewer("github-actions")),
                        material({}, checks_all=[check("build", "pass", "github-actions")]))
        r = out["reviewers"][0]
        self.assertEqual((r["state"], r["by"]), ("waiting", None))

    def test_former_builtin_login_uses_output_rule(self):
        r = self.one(reviewer("kintsugimira"),
                     [comment("Review in progress, only a review is running.", created=iso(0))])
        self.assertEqual((r["state"], r["by"]), ("reported", "output"))

    def test_output_before_cutoff_does_not_report(self):
        r = self.one(reviewer("rev-bot"), [comment("hello", created=iso(-1))])
        self.assertEqual(r["state"], "waiting")

    def test_unknown_cutoff_output_does_not_report(self):
        r = self.one(reviewer("rev-bot"), [comment("hello", created=iso(5))], since=None)
        self.assertEqual((r["state"], r["by"]), ("waiting", None))

    def test_timed_out(self):
        rev = reviewer("rev-bot", timeout=900)
        self.assertEqual(self.one(rev, [], now_offset=899)["state"], "waiting")
        self.assertEqual(self.one(rev, [], now_offset=900)["state"], "timed_out")
        self.assertEqual(self.one(rev, [], now_offset=5000, since=None)["state"], "waiting")

    def test_ignore_excludes_output_and_head_review(self):
        rev = reviewer("rev-bot", report={"ignore": "in progress"})
        r = self.one(rev, [comment("Review in progress", created=iso(5)),
                           review(HEAD, body="in progress still", id="r2")])
        self.assertEqual(r["state"], "waiting")
        # ignored items still appear in evidence
        self.assertEqual(len(r["evidence"]), 2)

    def test_ignore_is_case_sensitive_search(self):
        rev = reviewer("rev-bot", report={"ignore": "in progress"})
        r = self.one(rev, [comment("Review In Progress", created=iso(5))])
        self.assertEqual(r["state"], "reported")


class ReportKeys(Base):
    SHA = {"sha_pattern": "Reviewed commit: ([0-9a-f]{7,40})"}

    def test_sha_pattern_prefix_of_head_reports(self):
        r = self.one(reviewer("rev-bot", report=self.SHA), [comment("Reviewed commit: 1a2b3c4", created=iso(5))])
        self.assertEqual((r["state"], r["by"]), ("reported", "sha_pattern"))

    def test_sha_pattern_older_sha_waits(self):
        r = self.one(reviewer("rev-bot", report=self.SHA),
                     [comment("Reviewed commit: " + PREV[:12], created=iso(5))])
        self.assertEqual((r["state"], r["by"]), ("waiting", None))

    def test_sha_pattern_scans_all_matches_and_rejects_short(self):
        rb = reviewer("rev-bot", report=self.SHA)
        both = "Reviewed commit: " + PREV[:9] + "\nReviewed commit: 1a2b3c4d"
        self.assertEqual(self.one(rb, [comment(both, created=iso(5))])["by"], "sha_pattern")
        rb = reviewer("rev-bot", report={"sha_pattern": "at ([0-9a-f]+)"})
        self.assertEqual(self.one(rb, [comment("at 1a2b3c", created=iso(5))])["state"], "waiting")

    def test_sha_pattern_disables_output_rule(self):
        r = self.one(reviewer("rev-bot", report=self.SHA), [comment("anything", created=iso(5))])
        self.assertEqual(r["state"], "waiting")

    def test_named_check_reports_other_name_does_not(self):
        rev = reviewer("rev-bot", report={"check": "Bot Code Review"})
        checks = [check("Bot Code Review", "pass", "rev-bot")]
        r = self.rv(config(rev), material({}, checks_all=checks))
        self.assertEqual((r["state"], r["by"]), ("reported", "check"))
        other = [check("Other Check", "pass", "rev-bot")]
        r = self.rv(config(rev), material({}, checks_all=other))
        self.assertEqual((r["state"], r["by"]), ("waiting", None))
        r = self.rv(config(rev), material({}, checks_all=[check("Bot Code Review", "pending", "rev-bot")]))
        self.assertEqual(r["state"], "waiting")

    def test_named_check_counts_only_from_the_reviewers_own_app(self):
        """A same-named check from another app, or a commit status (no app), is not the reviewer's report."""
        rev = reviewer("rev-bot", report={"check": "Bot Code Review"})
        for app in ("github-actions", "other-bot", None):
            r = self.rv(config(rev), material({}, checks_all=[check("Bot Code Review", "pass", app)]))
            self.assertEqual((r["state"], r["by"], r["evidence"]), ("waiting", None, []), app)
        r = self.rv(config(rev), material({}, checks_all=[check("Bot Code Review", "pass", "Rev-Bot")]))
        self.assertEqual(r["by"], "check", "the app slug matches the login case-insensitively")

    def test_marker_ignored_until_edited_again(self):
        rev = reviewer("rev-bot", report={"marker": "<!-- walkthrough -->", "ignore": "in progress"})
        body1 = "<!-- walkthrough -->\nReview in progress"
        r = self.one(rev, [comment(body1, created=iso(-600), edited=iso(30))])
        self.assertEqual((r["state"], r["by"]), ("waiting", None))
        body2 = "<!-- walkthrough -->\nDone"
        r = self.one(rev, [comment(body2, created=iso(-600), edited=iso(90))])
        self.assertEqual((r["state"], r["by"]), ("reported", "marker"))

    def test_marker_needs_edit_or_creation_after_cutoff(self):
        rev = reviewer("rev-bot", report={"marker": "<!-- walkthrough -->"})
        r = self.one(rev, [comment("<!-- walkthrough -->", created=iso(-600))])
        self.assertEqual(r["state"], "waiting")
        r = self.one(rev, [comment("<!-- walkthrough -->", created=iso(10), kind="thread_comment")])
        self.assertEqual(r["by"], "marker")

    def test_review_on_head_counts_under_marker_rule(self):
        rev = reviewer("rev-bot", report={"marker": "<!-- walkthrough -->"})
        r = self.one(rev, [comment("<!-- walkthrough -->", created=iso(-600)), review(HEAD, created=iso(-30))])
        self.assertEqual((r["state"], r["by"]), ("reported", "review"))

    def test_marker_is_literal(self):
        rev = reviewer("rev-bot", report={"marker": "<!-- [bot] -->"})
        r = self.one(rev, [comment("<!-- b -->", created=iso(10))])
        self.assertEqual((r["state"], r["by"]), ("waiting", None))
        r = self.one(rev, [comment("x <!-- [bot] --> y", created=iso(10))])
        self.assertEqual(r["by"], "marker")


class Evidence(Base):
    def test_evidence_newest_first_with_excerpts(self):
        items = [comment("Review started", created=iso(30)),
                 review(HEAD, body="x" * 400, created=iso(90), state="APPROVED")]
        r = self.one(reviewer("rev-bot"), items)
        ev = r["evidence"]
        self.assertEqual([e["kind"] for e in ev], ["review", "comment"])
        self.assertEqual(ev[0]["state"], "APPROVED")
        self.assertEqual(ev[0]["at"], iso(90))
        self.assertEqual(len(ev[0]["excerpt"]), 300)
        self.assertEqual(ev[1]["excerpt"], "Review started")
        self.assertEqual(set(ev[1]), {"kind", "at", "state", "excerpt"})
        self.assertIsNone(ev[1]["state"])

    def test_evidence_capped_at_ten(self):
        items = [comment("c%d" % i, created=iso(10 + i), id="c%d" % i) for i in range(14)]
        ev = self.one(reviewer("rev-bot"), items)["evidence"]
        self.assertEqual(len(ev), 10)
        self.assertEqual(ev[0]["excerpt"], "c13")

    def test_evidence_empty_for_previous_head_only(self):
        items = [comment("old", created=iso(-100)), review(PREV, created=iso(-50))]
        r = self.one(reviewer("rev-bot"), items)
        self.assertEqual(r["evidence"], [])
        self.assertIn(r["state"], ("waiting", "timed_out"))

    def test_named_check_in_evidence(self):
        rev = reviewer("rev-bot", report={"check": "Bot Code Review"})
        r = self.rv(config(rev), material({}, checks_all=[check("Bot Code Review", "fail", "rev-bot"),
                                                         check("Other", "pass", "rev-bot")]))
        self.assertEqual(len(r["evidence"]), 1)
        e = r["evidence"][0]
        self.assertEqual((e["kind"], e["state"], e["excerpt"]), ("check", "fail", "Bot Code Review"))

    def test_state_does_not_depend_on_excerpt_length(self):
        rev = reviewer("rev-bot", report={"marker": "<!-- m -->"})
        r = self.one(rev, [comment("y" * 1000 + "<!-- m -->", created=iso(10))])
        self.assertEqual(r["by"], "marker")


class Checks(Base):
    CHK = {"check": "Bot Code Review"}

    def test_advisory_timed_out_check_moves_to_advisory_pending(self):
        rev = reviewer("check-bot", "advisory", 900, self.CHK)
        checks = [check("Bot Code Review", "pending", "check-bot"), check("build", "pending")]
        out = self.snap(config(rev), material({}, now_offset=16 * 60, checks_all=checks))
        self.assertEqual(out["reviewers"][0]["state"], "timed_out")
        c = out["checks"]
        self.assertEqual((c["pending"], c["advisory_pending"], c["ci_pending"]), (1, 1, 1))
        self.assertEqual(list(c), ["total", "pending", "advisory_pending", "ci_pending", "failing"])

    def test_advisory_waiting_check_stays_pending(self):
        rev = reviewer("check-bot", "advisory", 900, self.CHK)
        out = self.snap(config(rev), material({}, now_offset=60, checks_all=[check("Bot Code Review", "pending", "check-bot")]))
        c = out["checks"]
        self.assertEqual((c["pending"], c["advisory_pending"], c["ci_pending"]), (1, 0, 0))

    def test_required_reviewer_check_pending_not_ci(self):
        rev = reviewer("check-bot", "required", 900, self.CHK)
        out = self.snap(config(rev), material({}, now_offset=16 * 60, checks_all=[check("Bot Code Review", "pending", "check-bot")]))
        c = out["checks"]
        self.assertEqual((c["pending"], c["advisory_pending"], c["ci_pending"]), (1, 0, 0))

    def test_shared_app_checks_stay_ci(self):
        out = self.snap(config(reviewer("github-actions", "advisory")),
                        material({}, now_offset=9999, checks_all=[check("a", "pending"), check("b", "pending")]))
        c = out["checks"]
        self.assertEqual((c["pending"], c["advisory_pending"], c["ci_pending"]), (2, 0, 2))

    def test_same_named_check_from_another_app_is_ci(self):
        rev = reviewer("check-bot", "advisory", 900, self.CHK)
        checks = [check("Bot Code Review", "pending", "other-bot"), check("Bot Code Review", "pending", None)]
        out = self.snap(config(rev), material({}, now_offset=16 * 60, checks_all=checks))
        c = out["checks"]
        self.assertEqual((c["pending"], c["advisory_pending"], c["ci_pending"]), (2, 0, 2))

    def test_unconfigured_app_check_is_ci(self):
        out = self.snap(config(reviewer("rev-bot")), material({}, checks_all=[check("x", "pending", "other-bot")]))
        c = out["checks"]
        self.assertEqual((c["pending"], c["ci_pending"]), (1, 1))


class Output(Base):
    def test_compact_json_and_shape(self):
        rev = reviewer("rev-bot")
        cfg = config(rev)
        mat = material({"rev-bot": [review(HEAD)]}, now_offset=125, extra={"z_last": 1})
        raw = self.snap(cfg, mat, raw=True)
        self.assertEqual(raw.count("\n"), 1)
        self.assertTrue(raw.endswith("\n"))
        self.assertNotIn(", ", raw)
        self.assertNotIn('": ', raw)
        out = json.loads(raw)
        for gone in ("material", "checks_all", "cfg", "sig_base", "attn_base"):
            self.assertNotIn(gone, out)
        self.assertEqual(out["now"], iso(125))
        self.assertEqual(out["viewer"], "me")
        self.assertLess(list(out).index("viewer"), list(out).index("z_last"))
        self.assertEqual(list(out["reviewers"][0]), ["login", "role", "timeout", "state", "by", "evidence"])
        digest = hashlib.sha256((self.tmp / "cfg.json").read_bytes()).hexdigest()
        self.assertEqual(out["reviewer_config"], digest)
        r = "rev-bot:reported"
        self.assertEqual(base64.b64decode(out["sig"]).decode(), "SIG|" + r)
        self.assertEqual(base64.b64decode(out["attn"]).decode(), "ATTN|" + r)

    def test_no_config_means_no_reviewers(self):
        out = self.snap(None, material())
        self.assertEqual(out["reviewers"], [])
        self.assertIsNone(out["reviewer_config"])
        self.assertEqual(base64.b64decode(out["sig"]).decode(), "SIG|")

    def test_fractional_seconds_and_order_of_config(self):
        cfg = config(reviewer("b-bot"), reviewer("a-bot"))
        m = material({"a-bot": [comment("x", created=iso(5).replace("Z", ".250Z"))]})
        out = self.snap(cfg, m)
        self.assertEqual([x["login"] for x in out["reviewers"]], ["b-bot", "a-bot"])
        self.assertEqual(out["reviewers"][1]["state"], "reported")

    def test_head_mismatch_exit_1(self):
        r = self.run_py("--material", self.write("m.json", material()), "--head", "f" * 40)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")

    def test_bad_material_exit_1(self):
        r = self.run_py("--material", self.write("m.json", "{nope"), "--head", HEAD)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        r = self.run_py("--material", self.tmp / "missing.json", "--head", HEAD)
        self.assertEqual(r.returncode, 1)

    def test_check_config_prints_digest_and_logins(self):
        p = self.write("cfg.json", config(reviewer("a-bot"), reviewer("b-bot", report={})))
        r = self.run_py("--check-config", p)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, json.dumps({"ok": True, "digest": hashlib.sha256(p.read_bytes()).hexdigest(),
                                               "logins": ["a-bot", "b-bot"]}, separators=(",", ":")) + "\n")


class ConfigValidation(Base):
    def test_config_wrong_format(self):
        self.bad_config({"format": 2, "reviewers": []}, "format")

    def test_config_unknown_top_key(self):
        self.bad_config({"format": 1, "reviewers": [], "extra": 1}, "extra")

    def test_config_unknown_reviewer_key(self):
        self.bad_config(config({"login": "rev-bot", "role": "required", "timeout": 1, "checks": "x"}), "rev-bot", "checks")

    def test_config_unknown_report_key(self):
        self.bad_config(config(reviewer("rev-bot", report={"checks": "x"})), "rev-bot", "checks")

    def test_config_bad_sha_pattern_regex(self):
        self.bad_config(config(reviewer("rev-bot", report={"sha_pattern": "([0-9a-f"})), "rev-bot", "sha_pattern")

    def test_config_sha_pattern_without_group(self):
        self.bad_config(config(reviewer("rev-bot", report={"sha_pattern": "abc"})), "rev-bot", "sha_pattern")

    def test_config_bad_ignore_regex(self):
        self.bad_config(config(reviewer("rev-bot", report={"ignore": "("})), "rev-bot", "ignore")

    def test_config_pattern_over_500_chars(self):
        self.bad_config(config(reviewer("rev-bot", report={"sha_pattern": "(" + "a" * 500 + ")"})), "rev-bot", "sha_pattern")
        self.bad_config(config(reviewer("rev-bot", report={"marker": "m" * 501})), "rev-bot", "marker")
        self.bad_config(config(reviewer("rev-bot", report={"check": "c" * 501})), "rev-bot", "check")

    def test_config_500_chars_is_fine(self):
        p = self.write("ok.json", config(reviewer("rev-bot", report={"marker": "m" * 500})))
        self.assertEqual(self.run_py("--check-config", p).returncode, 0)

    def test_config_empty_report_value(self):
        self.bad_config(config(reviewer("rev-bot", report={"marker": ""})), "rev-bot", "marker")

    def test_config_21_reviewers(self):
        self.bad_config(config(*[reviewer("bot-%d" % i) for i in range(21)]), "reviewers")
        ok = self.write("ok.json", config(*[reviewer("bot-%d" % i) for i in range(20)]))
        self.assertEqual(self.run_py("--check-config", ok).returncode, 0)

    def test_config_bad_login_role_timeout(self):
        self.bad_config(config(reviewer("bad login")), "bad login", "login")
        self.bad_config(config(reviewer("rev-bot", role="boss")), "rev-bot", "role")
        self.bad_config(config(reviewer("rev-bot", timeout=-1)), "rev-bot", "timeout")
        self.bad_config(config(reviewer("rev-bot", timeout=True)), "rev-bot", "timeout")

    def test_config_missing_file(self):
        r = self.run_py("--check-config", self.tmp / "nope.json")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("nope.json", r.stderr)

    def test_config_not_json(self):
        r = self.run_py("--check-config", self.write("x.json", "not json"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("x.json", r.stderr)

    def test_usage_error_exit_2(self):
        r = self.run_py("--bogus")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")


if __name__ == "__main__":
    unittest.main()
