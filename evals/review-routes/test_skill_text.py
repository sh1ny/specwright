"""The skills call review-run.sh in the right places and state the pre-ship review rules.

The script's decisions (routes, validation, records, gate, rounds) are tested in test_review_run.py;
these checks make sure the skill text actually uses them, by position and key terms, not by exact
wording, in the style of evals/pr-pair/test_skill_text.py.

Run: python -m unittest discover evals/review-routes
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "skills" / "specwright-review" / "SKILL.md"


def read(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def sub(name):
    """Pattern for `review-run.sh <name>` however the path before it is written."""
    return re.compile(r"review-run\.sh[`\"']?\s+" + name + r"\b")


def sections(text):
    """{lowercased '## ' heading: section text}."""
    marks = [(m.start(), m.group(1).strip().lower()) for m in re.finditer(r"^## (.+)$", text, re.M)]
    return {title: text[start:(marks[i + 1][0] if i + 1 < len(marks) else len(text))]
            for i, (start, title) in enumerate(marks)}


def positions(pattern, text):
    return [m.start() for m in pattern.finditer(text)]


class ReviewSkill(unittest.TestCase):
    def setUp(self):
        self.text = read(REVIEW)
        self.assertTrue(self.text, f"{REVIEW} is missing")
        self.sections = sections(self.text)

    def section(self, key):
        found = [t for t in self.sections if key in t]
        self.assertTrue(found, f"SKILL.md has no '## ...{key}...' section; found {sorted(self.sections)}")
        return self.sections[found[0]]

    def test_frontmatter_version(self):
        self.assertRegex(self.text, r"(?m)^name: specwright-review$")
        self.assertRegex(self.text, r"(?m)^  version: 0\.2\.0$")

    def test_route_selection_via_select_before_run(self):
        sel, run = positions(sub("select"), self.text), positions(sub("run"), self.text)
        self.assertTrue(sel, "the skill never runs `review-run.sh select`")
        self.assertTrue(run, "the skill never runs `review-run.sh run`")
        self.assertLess(sel[0], run[0], "`run` appears before `select`")
        self.assertRegex(self.text, r"--runtime", "select is not given the current harness (--runtime)")
        self.assertRegex(self.text, r"(?is)subagent.{0,400}specwright-reviewer",
                         "the subagent route does not name the specwright-reviewer agent")
        self.assertTrue(positions(sub("record"), self.text), "the subagent route's output is not validated with `record`")

    def test_design_reviews_use_routes_and_record(self):
        design = self.section("design review")
        self.assertTrue(positions(sub("select"), design) or "select" in design)
        self.assertRegex(design, r"--kind design", "design reviews do not run with --kind design")
        self.assertRegex(design, r"(?s)record[`\"']?\s+--kind design|record --kind design",
                         "a subagent design review is not validated with `record --kind design`")

    def test_review_runs_in_background(self):
        self.assertRegex(self.text, r"(?i)background", "the review is not run in the background")
        self.assertRegex(self.text, r"run_in_background", "Claude Code's run_in_background is not named")

    def test_fail_closed_no_fallthrough(self):
        self.assertRegex(self.text, r"(?i)exit(s)? 3", "exit 3 (failed review) is not handled")
        self.assertRegex(self.text, r"(?i)never (try|run|fall (through|back) to) (the next|another) route",
                         "the skill does not forbid falling through to the next route")

    def test_failed_review_stops_ship_and_merge(self):
        m = re.search(r"(?is)exit(s)? 3.{0,600}", self.text)
        self.assertTrue(m, "no exit 3 handling")
        block = m.group(0)
        self.assertRegex(block, r"(?i)(ship|push).{0,80}(merge)|(merge).{0,80}(ship|push)",
                         "a failed review does not stop ship and the merge")
        self.assertRegex(block, r"(?i)route", "the failure report does not name the route")
        self.assertRegex(block, r"(?i)(retry|again)", "a retry is not offered")

    def test_waive_only_after_user_answer(self):
        w = positions(sub("waive"), self.text)
        self.assertTrue(w, "the skill never runs `review-run.sh waive`")
        around = self.text[max(0, w[0] - 600):w[0] + 600]
        self.assertRegex(around, r"(?i)only (after|when|on) the user", "waive is not limited to the user's answer")
        self.assertRegex(around, r"(?i)never waive", "the skill does not forbid waiving on its own")
        self.assertRegex(around, r"--reason", "the waiver does not record the user's reason")
        self.assertRegex(self.text, r"(?i)no answer.{0,200}(no pass|ship does not start|does not start)",
                         "an unanswered P0/P1 does not keep ship from starting")

    def test_fix_subject_and_preship_round_trailer(self):
        self.assertIn("address pre-ship review", self.text)
        self.assertRegex(self.text, r"Preship-Round: <n", "the fix commit's Preship-Round trailer is not given")
        self.assertRegex(self.text, r"(?i)never.{0,120}(address review feedback|Feedback-Round)",
                         "the skill does not forbid the PR feedback subject/trailer for pre-ship fixes")
        fix = self.text.find("address pre-ship review")
        rerun = re.search(r"(?i)(new|another|again).{0,40}pre-ship review|review again|run the review again",
                          self.text[fix:])
        self.assertTrue(rerun, "a fix round is not followed by a new pre-ship review")

    def test_escalate_after_round_2(self):
        r = positions(sub("rounds"), self.text)
        self.assertTrue(r, "the skill never runs `review-run.sh rounds`")
        fix = self.text.find("address pre-ship review")
        self.assertLess(r[0], fix, "rounds is read after the fix commit, not before it")
        self.assertRegex(self.text, r"(?is)rounds.{0,400}\b2\b.{0,300}(ask|stop)",
                         "escalation after round 2 is not stated")

    def test_clarification_amend_commit_and_rereview(self):
        self.assertRegex(self.text, r"(?i)clarification")
        self.assertIn("amend specs", self.text)
        self.assertIn("Amendment: clarification", self.text)
        self.assertRegex(self.text, r"(?is)every other scenario.{0,200}(code and (the )?tests|tests)",
                         "the clarification test (one reading fits every scenario; code and tests already match) is missing")
        amend = self.text.find("Amendment: clarification")
        self.assertRegex(self.text[amend:amend + 400], r"(?i)pre-ship review",
                         "a clarification amendment is not followed by a new pre-ship review")

    def test_behaviour_change_asks_user(self):
        m = re.search(r"(?is)behaviour[ _-]change.{0,500}", self.text)
        self.assertTrue(m)
        self.assertRegex(self.text, r"(?is)behaviour[ _-]change.{0,500}(ask|approv)",
                         "a behaviour change does not need the user's approval")
        self.assertRegex(self.text, r"(?i)(never|do not|don't) (edit|amend|change) the spec",
                         "the skill does not forbid editing the spec for a behaviour change before approval")
        self.assertRegex(self.text, r"(?i)never the other way",
                         "the agent may downgrade clarification to ask, never upgrade the other way")

    def test_behaviour_change_follows_drift_rule(self):
        self.assertIn("Amendment: behaviour-change", self.text)
        m = self.text.find("Amendment: behaviour-change")
        block = self.text[max(0, m - 500):m + 600]
        self.assertRegex(block, r"(?i)drift rule", "an approved behaviour change does not follow the drift rule")
        self.assertRegex(block, r"(?i)design (re-)?review|review step", "no design re-review for FULL")
        self.assertRegex(block, r"(?i)tests?", "tests are not updated")

    def test_preship_false_skips(self):
        self.assertRegex(self.text, r"review\.preship: false")

    def test_diff_too_large_asks(self):
        self.assertRegex(self.text, r"diff_too_large")
        self.assertRegex(self.text, r"review\.max_diff_kb")

    def test_credits(self):
        self.assertRegex(self.text, r"ce-code-review")
        self.assertRegex(self.text, r"reviewer\.md")


if __name__ == "__main__":
    unittest.main()
