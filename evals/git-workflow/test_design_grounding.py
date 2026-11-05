"""The delivered schema, templates and reviewer agents carry the rules of verify-design-claims (#197).

These checks assert where a rule sits and its key terms, not exact wording, in the style of
evals/git-workflow/test_user_tasks.py. They prove the rule is in the instructions, not that a live
agent follows it.

Run: python -m unittest evals/git-workflow/test_design_grounding.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "specwright" / "schema.yaml"
DESIGN_TEMPLATE = ROOT / "schemas" / "specwright" / "templates" / "design.md"
TASKS_TEMPLATE = ROOT / "schemas" / "specwright" / "templates" / "tasks.md"
REVIEWERS = [ROOT / "agents" / h / "specwright-reviewer.md" for h in ("claude", "omp")]
LIGHT_BOUNDARY = "LIGHT tier ends here"


def read(p):
    return p.read_text(encoding="utf-8")


def flat(text):
    return re.sub(r"\s+", " ", text)


def artifact_instruction(artifact_id):
    """The flattened instruction of one schema artifact (`design`, `review`, `tasks`)."""
    text = read(SCHEMA)
    m = re.search(r"^  - id: " + artifact_id + r"$.*?(?=^  - id: |^apply:)", text, re.M | re.S)
    assert m, f"schema.yaml has no artifact {artifact_id}"
    return flat(m.group(0))


class DesignCitesTheCode(unittest.TestCase):
    def test_design_claims_cite_path_line(self):
        d = artifact_instruction("design")
        self.assertRegex(d, r"(?i)claim[^.]{0,120}existing (code|behaviou?r)[^.]{0,200}`path:line`",
                         "the design instruction does not require a `path:line` citation for claims about existing behaviour")
        self.assertRegex(d, r"(?i)narrow\w*[^.]{0,80}(range|lines)|(range|lines)[^.]{0,80}narrow",
                         "the design instruction does not ask for the narrowest range that shows the claim")
        self.assertRegex(flat(read(DESIGN_TEMPLATE)), r"(?i)`path:line`",
                         "the design template's Context comment does not ask for `path:line`")

    def test_unchecked_claim_is_numbered_assumption(self):
        d = artifact_instruction("design")
        self.assertIn("## Assumptions", d, "the design instruction does not name the `## Assumptions` section")
        self.assertRegex(d, r"`A1`", "the design instruction does not number assumptions `A1`...")
        self.assertRegex(d, r"(?i)(not (been )?checked|unchecked)[^.]{0,200}## Assumptions|## Assumptions[^.]{0,300}(not (been )?checked|unchecked)",
                         "the design instruction does not send unchecked claims to `## Assumptions`")
        self.assertRegex(d, r"(?i)depend\w*", "assumption entries do not name what depends on them")

    def test_assumptions_none_when_all_cited(self):
        d = artifact_instruction("design")
        self.assertRegex(d, r"(?i)## Assumptions[^.]{0,400}`None`|`None`[^.]{0,200}## Assumptions",
                         "the design instruction does not say the section reads `None` when every claim is cited")

    def test_template_assumptions_above_light_boundary(self):
        t = read(DESIGN_TEMPLATE)
        self.assertIn("## Assumptions", t, "the design template has no `## Assumptions` section")
        self.assertIn(LIGHT_BOUNDARY, t, "the design template lost its LIGHT boundary")
        self.assertLess(t.index("## Assumptions"), t.index(LIGHT_BOUNDARY),
                        "`## Assumptions` sits below the LIGHT boundary, so a LIGHT author deletes it")
        self.assertLess(t.index("### Decision summary"), t.index("## Assumptions"),
                        "`## Assumptions` should follow the Decision summary")

    def test_light_section_list_names_assumptions(self):
        d = artifact_instruction("design")
        self.assertRegex(d, r"No trigger → LIGHT tier: write Triage, Context, Decisions and Assumptions only",
                         "the LIGHT section list does not name Assumptions")


class ReviewChecksClaims(unittest.TestCase):
    def test_review_rereads_citations_contradiction_critical(self):
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)\*\*?Claims\*?\*?|- Claims:", "the review checklist has no Claims item")
        self.assertRegex(r, r"(?i)re-read\w*[^.]{0,80}(cited range|citation)",
                         "the review does not re-read every cited range")
        self.assertRegex(r, r"(?i)contradict\w*[^.]{0,200}(decision or task|task or decision)[^.]{0,120}Critical",
                         "a contradicted load-bearing claim is not Critical")

    def test_review_flags_uncited_claim(self):
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)(neither a citation nor an? (Assumptions )?entry|no citation and no (Assumptions )?entry)",
                         "a claim with neither a citation nor an Assumptions entry is not a finding")
        self.assertRegex(r, r"(?i)at least Moderate", "other claim findings are not at least Moderate")

    def test_review_flags_settleable_assumption(self):
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)assumption[^.]{0,80}(the code settles|settle\w* by reading)",
                         "an assumption the code settles is not a finding")

    def test_review_flags_citation_not_showing_claim(self):
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)citation[^.]{0,80}(does not|doesn't) show[^.]{0,120}(broad|moved|missing)",
                         "a citation that does not show its claim (too broad, moved, missing) is not a finding")

    def test_light_recheck_rereads_citations(self):
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)LIGHT:[^.]{0,400}re-read\w*[^.]{0,80}citation",
                         "the LIGHT re-check does not re-read citations")

    def test_light_contradiction_fixed_before_verdict(self):
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)contradict\w*[^.]{0,120}fix\w*[^.]{0,80}design\.md[^.]{0,80}before[^.]{0,40}verdict",
                         "a LIGHT contradiction is not fixed in design.md before any verdict")

    def test_old_design_without_section_counts_as_none(self):
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)no `## Assumptions` section[^.]{0,120}`None`",
                         "a design planned before the rule is not read as `None`")

    def test_cited_files_limited_to_tracked_files(self):
        # A design can come from PR content: a citation such as `.env:1-20` must not make a reviewer
        # read an ignored local secret and send it to the review provider.
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)only files? tracked[^.]{0,200}(ignored|untracked)[^.]{0,200}symlink[^.]{0,120}not opened[^.]{0,80}finding",
                         "the Claims item does not limit re-reads to tracked repository files")
        self.assertRegex(r, r"(?i)LIGHT:[^.]{0,400}re-read\w*[^.]{0,200}tracked",
                         "the LIGHT re-check does not limit re-reads to tracked repository files")
        for p in REVIEWERS:
            self.assertRegex(flat(read(p)), r"(?i)re-read\w*[^.]{0,200}only files? tracked",
                             f"{p.relative_to(ROOT)} does not limit the claim check to tracked files")

    def test_reviewer_agents_name_the_claim_check(self):
        for p in REVIEWERS:
            text = flat(read(p))
            self.assertRegex(text, r"(?i)design review[^.]{0,400}(re-read\w*[^.]{0,60}cit\w*|cit\w*[^.]{0,60}re-read)",
                             f"{p.relative_to(ROOT)} does not name the claim check for design reviews")


class TasksVerifyAssumptions(unittest.TestCase):
    def test_tasks_verify_assumption_before_dependents(self):
        t = artifact_instruction("tasks")
        self.assertRegex(t, r"(?i)## Assumptions", "the tasks instruction does not read the Assumptions section")
        self.assertRegex(t, r"(?i)task[^.]{0,120}(names|naming) its id", "the verify task does not name the assumption id")
        self.assertRegex(t, r"(?i)before the first task that relies on it",
                         "the verify task is not ordered before the first task that relies on it")

    def test_disproved_assumption_is_drift(self):
        t = artifact_instruction("tasks")
        self.assertRegex(t, r"(?i)disproved assumption[^.]{0,80}drift", "a disproved assumption is not design drift")

    def test_no_verify_task_without_dependents(self):
        t = artifact_instruction("tasks")
        self.assertRegex(t, r"(?i)(no dependents|nothing depends on|names no dependent)[^.]{0,60}no (verify )?task",
                         "an assumption with no dependents still gets a task")
        self.assertRegex(flat(read(TASKS_TEMPLATE)), r"(?i)Verify A1",
                         "the tasks template has no verify-first example line")


if __name__ == "__main__":
    unittest.main()
