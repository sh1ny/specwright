"""The schema and templates carry the rules of the decision-making change.

Wording checks in the style of test_instructions.py: they assert where a rule sits (the proposal
instruction of the schema, the proposal template) and its key terms, not exact wording. They prove
the rule is in the instructions, not that a live agent follows it.

Run: python -m unittest evals/git-workflow/test_decision_making.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "specwright" / "schema.yaml"
PROPOSAL_TEMPLATE = ROOT / "schemas" / "specwright" / "templates" / "proposal.md"

DESIGN_TEMPLATE = ROOT / "schemas" / "specwright" / "templates" / "design.md"

MODES = ("autonomous", "important", "all")


def read(p):
    return p.read_text(encoding="utf-8")


def schema_block(artifact_id):
    """The YAML block of one artifact (`- id: proposal`) up to the next artifact."""
    text = read(SCHEMA)
    m = re.search(r"^  - id: " + artifact_id + r"\s*$", text, re.M)
    assert m, f"schema.yaml has no artifact {artifact_id}"
    nxt = re.search(r"^  - id: ", text[m.end():], re.M)
    return text[m.start(): m.end() + nxt.start()] if nxt else text[m.start():]


def proposal_instruction():
    return schema_block("proposal")


def paragraphs(text):
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def find_block(text, *patterns):
    """First paragraph matching every pattern (case-insensitive), or None."""
    for p in paragraphs(text):
        if all(re.search(pat, p, re.I | re.S) for pat in patterns):
            return p
    return None


class ModeFromSetting(unittest.TestCase):
    """Requirement: The decision mode comes from the setting."""

    def test_setting_unset_means_autonomous(self):
        text = proposal_instruction()
        p = find_block(text, r"decision_making", r"specwright\.yaml", r"unset|no setting|absent|missing|default", r"autonomous")
        self.assertIsNotNone(p, "proposal instruction does not say decision_making is read from specwright.yaml and defaults to autonomous")
        for mode in MODES:
            self.assertIn(mode, p)

    def test_unknown_value_stops_naming_valid_values(self):
        text = proposal_instruction()
        p = find_block(text, r"decision_making", r"unknown|any other|not one of|invalid", r"stop", r"before")
        self.assertIsNotNone(p, "proposal instruction has no stop rule for an unknown decision_making value")
        self.assertRegex(p, r"(?i)decision.{0,40}written|before any decision")
        self.assertRegex(p, r"(?i)name|naming")
        for mode in MODES:
            self.assertIn(mode, p)


class OverrideForOneChange(unittest.TestCase):
    """Requirement: A user instruction overrides the mode for one change."""

    def test_override_recorded_in_proposal_with_words(self):
        text = proposal_instruction()
        self.assertIsNotNone(find_block(text, r"instruction", r"(this|that|one) change( only)?|for one change"),
                             "proposal instruction does not say a user instruction sets the mode for one change")
        p = find_block(text, r"Decision Making", r"proposal\.md", r"words")
        self.assertIsNotNone(p, "proposal instruction does not say the mode is recorded in proposal.md with the user's words")
        self.assertRegex(p, r"(?i)source")
        self.assertRegex(p, r"(?i)\bsetting\b")
        self.assertRegex(p, r"(?i)\buser\b")
        self.assertRegex(p, r"(?i)before .{0,40}proposal\.md.{0,20}(is )?written|first artifact")
        tpl = read(PROPOSAL_TEMPLATE)
        self.assertRegex(tpl, r"(?m)^## Decision Making\s*$")
        self.assertRegex(tpl, r"DECISION_MAKING:\s*<mode>")
        self.assertRegex(tpl, r"(?i)Source:")
        self.assertRegex(tpl, r"(?i)\buser\b.{0,60}(quot|words)")
        self.assertLess(tpl.index("## Decision Making"), tpl.index("## Release Notes"))

    def test_resumed_session_reads_mode_from_proposal(self):
        text = proposal_instruction()
        p = find_block(text, r"later|resum|new session|next session", r"DECISION_MAKING|recorded mode|mode (recorded|in force)", r"proposal\.md|Decision Making")
        self.assertIsNotNone(p, "proposal instruction does not say later steps read the mode from proposal.md")
        tpl = read(PROPOSAL_TEMPLATE)
        for field in ("S1", "Choice", "Rejected", "Reversal cost", "Important", "Chosen by"):
            self.assertIn(field, tpl)

    def test_override_is_for_one_change_only(self):
        text = proposal_instruction()
        p = find_block(text, r"instruction", r"(this|that|one) change( only)?|for one change", r"never|not|leave|unchanged|only")
        self.assertIsNotNone(p, "proposal instruction does not limit an override to one change")
        self.assertRegex(p, r"(?is)(does not|do not|never|not)\s+(change|write|edit|modify)\b.{0,60}(specwright\.yaml|setting)|setting (is )?(left )?unchanged|specwright\.yaml.{0,40}(unchanged|not)")

    def test_missing_mode_line_falls_back_to_setting(self):
        text = proposal_instruction()
        p = find_block(text, r"(no|without|missing|lacks?) .{0,40}(DECISION_MAKING|mode)", r"setting")
        self.assertIsNotNone(p, "proposal instruction does not say a proposal with no mode line uses the setting")
        self.assertRegex(p, r"(?i)(not|no|never) .{0,30}(rewrit|edit|add|written)|without (rewriting|editing)")


class DecisionFields(unittest.TestCase):
    """Requirement: Every decision records its importance and who chose it."""

    def test_importance_criteria_listed(self):
        text = schema_block("design")
        p = find_block(text, r"Important:\s*yes\|no|Important: yes", r"criteri")
        self.assertIsNotNone(p, "design instruction does not record Important: yes|no with the criterion met")
        self.assertRegex(p, r"(?i)reversal\s+cost")
        self.assertRegex(p, r"(?i)bind")
        self.assertRegex(p, r"(?i)config")
        self.assertRegex(p, r"(?i)users? (see|sees)|visible to users")
        self.assertRegex(p, r"(?i)weak\s+evidence")
        self.assertRegex(p, r"(?i)any one|one is enough|either")

    def test_design_template_has_important_and_chosen_by(self):
        tpl = read(DESIGN_TEMPLATE)
        self.assertRegex(tpl, r"\*\*Important:\*\*.{0,40}yes.{0,5}no")
        self.assertRegex(tpl, r"(?i)\*\*Important:\*\*.*criterion")
        self.assertRegex(tpl, r"\*\*Chosen by:\*\*.{0,40}agent.{0,5}user")
        p = find_block(schema_block("design"), r"Chosen by", r"user", r"any mode")
        self.assertIsNotNone(p, "design instruction does not say Chosen by is user when the user chose or stated it, in any mode")

    def test_wording_order_layout_not_decisions(self):
        p = find_block(schema_block("design"), r"wording", r"order of tasks|task order", r"layout", r"not (a )?decision|no Decisions entry")
        self.assertIsNotNone(p, "design instruction does not say wording, task order and test layout are not decisions")


class DecisionSummary(unittest.TestCase):
    """Requirement: Every change carries a decision summary."""

    def test_summary_shown_at_end_without_waiting(self):
        tpl = read(DESIGN_TEMPLATE)
        self.assertRegex(tpl, r"(?m)^### Decision summary\s*$")
        self.assertRegex(tpl, r"\|\s*#\s*\|\s*Decision\s*\|\s*Choice\s*\|\s*Rejected\s*\|\s*Reversal cost\s*\|\s*Important\s*\|\s*Chosen by\s*\|")
        self.assertLess(tpl.index("### D1"), tpl.index("### Decision summary"))
        p = find_block(schema_block("tasks"), r"Decision\s+summary", r"show", r"end\s+of\s+planning|before\s+apply", r"autonomous", r"(not|no|without)\s+(wait|an\s+answer|ask)")
        self.assertIsNotNone(p, "tasks instruction does not show the summary at the end of planning without waiting in autonomous mode")
        d = find_block(schema_block("design"), r"Decision\s+summary", r"one\s+row", r"\bS\b|S1|scope", r"\bD\b|D1")
        self.assertIsNotNone(d, "design instruction does not describe the summary table with one row per S and D entry")

    def test_stated_choice_is_user_without_asking(self):
        p = find_block(schema_block("design"), r"(stated|named|chose)", r"before planning|already", r"Chosen by:? `?user", r"(without|not) (ask|a question)|no question")
        self.assertIsNotNone(p, "design instruction does not record a choice the user already stated as user without asking")

    def test_summary_rows_match_entries(self):
        p = find_block(schema_block("design"), r"Decision\s+summary", r"same\s+edit", r"one\s+to\s+one|one-to-one|match")
        self.assertIsNotNone(p, "design instruction does not keep the summary in step with the entries in the same edit")


if __name__ == "__main__":
    unittest.main()
