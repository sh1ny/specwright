"""The delivered schema and templates carry the rules of carry-design-constraints.

These checks assert where a rule sits and its key terms, not exact wording, in the style of
evals/git-workflow/test_design_grounding.py. They prove the rule is in the instructions, not that a live
agent follows it.

Run: python -m unittest evals/git-workflow/test_design_constraints.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "specwright" / "schema.yaml"
DESIGN_TEMPLATE = ROOT / "schemas" / "specwright" / "templates" / "design.md"
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


class DesignCarriesConstraints(unittest.TestCase):
    def test_design_lists_carried_constraints_with_destination(self):
        d = artifact_instruction("design")
        self.assertIn("## Carried constraints", d, "the design instruction does not name the `## Carried constraints` section")
        self.assertRegex(d, r"`C1`", "the design instruction does not number constraints `C1`...")
        self.assertRegex(d, r"(?i)## Carried constraints[^.]{0,400}(invariant)[^.]{0,200}(deliberate gap)[^.]{0,200}(rejected alternative)",
                         "carried constraint entries do not name their kind")
        self.assertRegex(d, r"(?i)exactly one destination", "an entry does not take exactly one destination")
        self.assertRegex(d, r"doc comment: <path> <symbol>", "the doc comment destination form is missing")
        self.assertRegex(d, r"spec: specs/<capability>/spec\.md → Requirement: <name>", "the spec destination form is missing")
        self.assertRegex(d, r"ADR NNNN", "the ADR destination form is missing")

    def test_destination_rule_by_kind(self):
        d = artifact_instruction("design")
        self.assertRegex(d, r"(?i)fact about (specific )?code[^.]{0,200}doc comment",
                         "a fact about specific code does not go in that code's doc comment")
        self.assertRegex(d, r"(?i)(guarantee|relie\w+ on)[^.]{0,200}delta spec",
                         "a guarantee users or downstream systems rely on does not go in the delta spec")
        self.assertRegex(d, r"(?i)binds future changes[^.]{0,200}ADR",
                         "a decision that binds future changes beyond one module does not go in an ADR")
        self.assertRegex(d, r"(?i)cannot hold a comment[^.]{0,200}(nearest owning code|spec)",
                         "a file that cannot hold a comment has no fallback destination")

    def test_carried_constraints_none_when_empty(self):
        d = artifact_instruction("design")
        self.assertRegex(d, r"(?i)## Carried constraints[^.]{0,800}reads `None`|`None`[^.]{0,200}## Carried constraints",
                         "the design instruction does not say the section reads `None` when nothing outlives the change")

    def test_carried_constraints_above_light_boundary_and_in_light_list(self):
        t = read(DESIGN_TEMPLATE)
        self.assertIn("## Carried constraints", t, "the design template has no `## Carried constraints` section")
        self.assertIn(LIGHT_BOUNDARY, t, "the design template lost its LIGHT boundary")
        self.assertLess(t.index("## Assumptions"), t.index("## Carried constraints"),
                        "`## Carried constraints` should follow `## Assumptions`")
        self.assertLess(t.index("## Carried constraints"), t.index(LIGHT_BOUNDARY),
                        "`## Carried constraints` sits below the LIGHT boundary, so a LIGHT author deletes it")
        d = artifact_instruction("design")
        self.assertRegex(d, r"No trigger → LIGHT tier: write Triage, Context, Decisions, Assumptions and Carried constraints",
                         "the LIGHT section list does not name Carried constraints")

    def test_missing_section_reads_as_none(self):
        d = artifact_instruction("design")
        self.assertRegex(d, r"(?i)(planned before|no `## Carried constraints` section|has no section)[^.]{0,200}(counts as|reads as|is) `None`",
                         "a design planned before the rule is not read as `None`")


class ReviewChecksCompleteness(unittest.TestCase):
    def test_review_flags_unlisted_constraint_moderate(self):
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)Carried constraints:[^.]{0,300}(rejected alternative|invariant|deliberate gap)[^.]{0,300}(does not list|not listed|unlisted)[^.]{0,120}Moderate",
                         "a stated constraint the section does not list is not a Moderate finding")

    def test_review_flags_entry_without_single_destination(self):
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)Carried constraints:.{0,900}(zero or several|no destination or more than one|without exactly one)[^.]{0,80}destination",
                         "an entry with zero or several destinations is not a finding")

    def test_light_recheck_records_finding_and_withholds_verdict(self):
        r = artifact_instruction("review")
        m = re.search(r"LIGHT: re-check.*?(?=FULL: the review MUST NOT)", r, re.S)
        self.assertTrue(m, "the review instruction has no LIGHT paragraph")
        light = m.group(0)
        self.assertRegex(light, r"(?i)Carried constraints", "the LIGHT re-check does not apply the Carried constraints test")
        self.assertRegex(light, r"(?i)Moderate finding[^.]{0,120}## Findings", "a LIGHT failure is not recorded as a Moderate finding under `## Findings`")
        self.assertRegex(light, r"(?i)no `VERDICT:` line", "a LIGHT failure still writes a verdict line")
        self.assertRegex(light, r"(?i)re-run\w*[^.]{0,80}re-check|re-check[^.]{0,80}again", "the author does not re-run the re-check")
        self.assertRegex(light, r"(?i)marked fixed", "earlier findings are not marked fixed after a passing re-check")

    def test_review_missing_section_reads_as_none(self):
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)no `## Carried constraints` section[^.]{0,120}`None`",
                         "the review does not read a design with no section as `None`")


class TasksCarryEachEntry(unittest.TestCase):
    def test_tasks_write_each_entry_at_destination(self):
        t = artifact_instruction("tasks")
        self.assertRegex(t, r"(?i)## Carried constraints", "the tasks instruction does not read the Carried constraints section")
        self.assertRegex(t, r"(?i)CARRIED CONSTRAINTS\.[^.]{0,200}(task|tasks)[^.]{0,120}names its id[^.]{0,120}destination",
                         "each entry does not get a task naming its id and writing the fact at its destination")
        self.assertRegex(t, r"(?i)ADR destinations?[^.]{0,200}task that writes that ADR[^.]{0,120}(entry ids|ids)",
                         "ADR destinations do not ride the task that writes that ADR, naming the entry ids")
        self.assertNotRegex(t, r"(?i)ADR destinations?[^.]{0,80}first[- ]group",
                            "ADR destinations are pinned to the first task group, which an earlier verify task can occupy")
        self.assertRegex(t, r"(?i)ticked only when the text is at the destination",
                         "the task is not ticked only once the text is at the destination")
        self.assertRegex(t, r"(?i)(reads `None`|no section)[^.]{0,120}no task",
                         "a `None` or missing section adds a task")

    def test_moved_destination_is_drift(self):
        t = artifact_instruction("tasks")
        self.assertRegex(t, r"(?i)destination that is gone[^.]{0,120}design drift", "a gone destination is not design drift")
        self.assertRegex(t, r"(?i)design drift:[^.]{0,200}stops that task[^.]{0,200}amended[^.]{0,120}drift rule[^.]{0,120}new destination",
                         "drift does not stop the task, amend the entry and write at the new destination")


BRIEF = ROOT / "skills" / "specwright-review" / "references" / "brief.md"


def brief_report_section():
    """The flattened `## What to report` section of the pre-ship brief."""
    m = re.search(r"^## What to report$.*?(?=^## )", read(BRIEF), re.M | re.S)
    assert m, "brief.md has no `## What to report` section"
    return flat(m.group(0))


class PreshipBriefChecksConstraints(unittest.TestCase):
    def test_brief_missing_carried_constraint_is_p1(self):
        b = brief_report_section()
        self.assertRegex(b, r"\*\*Carried constraints\*\*", "the brief has no Carried constraints item")
        self.assertRegex(b, r"(?i)\*\*Carried constraints\*\*.{0,900}(missing|contradict\w*)[^.]{0,200}P1 `docs`[^.]{0,80}naming the entry",
                         "a missing or contradicted entry is not a P1 `docs` finding naming the entry")
        self.assertLess(b.index("**Release Notes**"), b.index("**Carried constraints**"),
                        "the Carried constraints item should follow the Release Notes item")

    def test_brief_checks_destination_in_range(self):
        b = brief_report_section()
        self.assertRegex(b, r"(?i)## Carried constraints[^.]{0,200}design", "the brief does not read the design's section")
        self.assertRegex(b, r"(?i)archived design", "the brief does not read the archived design after the archive commit")
        self.assertRegex(b, r"(?i)each entry[^.]{0,120}(present|text)[^.]{0,120}destination[^.]{0,120}reviewed range",
                         "the brief does not check each entry at its destination in the reviewed range")

    def test_brief_no_finding_for_none(self):
        b = brief_report_section()
        self.assertRegex(b, r"(?i)(reads `None`|no section)[^.]{0,200}no finding",
                         "a `None` or missing section still raises a finding")


if __name__ == "__main__":
    unittest.main()
