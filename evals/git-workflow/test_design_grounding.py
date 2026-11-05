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


if __name__ == "__main__":
    unittest.main()
