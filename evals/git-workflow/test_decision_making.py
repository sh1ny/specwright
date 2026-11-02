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


TOOL_NAMES = r"AskUserQuestion|request_user_input|ask_user_question|ask_user"


def asked_blocks():
    return {"proposal": proposal_instruction(), "design": schema_block("design")}


class PuttingDecisionsToTheUser(unittest.TestCase):
    """Requirement: Decisions go to the user per the mode."""

    def test_important_mode_asks_important_only(self):
        for name, text in asked_blocks().items():
            p = find_block(text, r"`?important`? mode", r"each important decision|important decisions?", r"before", r"written")
            self.assertIsNotNone(p, f"{name} instruction does not ask about each important decision in important mode before writing")
            self.assertRegex(p, r"(?i)Chosen by: `?agent")
            self.assertRegex(p, r"(?i)recommended")

    def test_all_mode_asks_every_decision(self):
        for name, text in asked_blocks().items():
            p = find_block(text, r"`?all`? mode", r"every decision", r"before", r"written")
            self.assertIsNotNone(p, f"{name} instruction does not ask about every decision in all mode before writing")

    def test_batches_of_at_most_four_through_ask_tool(self):
        for name, text in asked_blocks().items():
            p = find_block(text, r"batch", r"at\s+most\s+4", r"ask\s+tool", r"more\s+batches|further\s+batch")
            self.assertIsNotNone(p, f"{name} instruction has no batches of at most 4 through the ask tool")
            self.assertRegex(p, r"(?i)every\s+decision")

    def test_batch_shrinks_to_tool_question_limit(self):
        for name, text in asked_blocks().items():
            p = find_block(text, r"batch", r"at\s+most\s+4", r"fewer|lower|smaller", r"(tool|it)\s+takes|tool'?s? .{0,30}limit")
            self.assertIsNotNone(p, f"{name} instruction does not shrink a batch to the tool's question limit")
            self.assertNotRegex(p, r"(?i)(three|3)\s+questions")

    def test_options_fit_tool_limit_keeping_recommended_and_discuss(self):
        for name, text in asked_blocks().items():
            p = find_block(text, r"2\s+to\s+4\s+options", r"option\s+limit|options? (limit|cap)", r"recommended", r"discuss")
            self.assertIsNotNone(p, f"{name} instruction does not fit options to the tool's limit keeping recommended and discuss")
            self.assertRegex(p, r"(?i)weakest")
            self.assertRegex(p, r"(?i)free-text")
            self.assertRegex(p, r"(?i)discuss option")
        for text in asked_blocks().values():
            self.assertNotRegex(text, TOOL_NAMES)

    def test_unusable_tool_falls_back_to_plain_text(self):
        for name, text in asked_blocks().items():
            p = find_block(text, r"plain\s+text", r"lettered", r"(session|mode).{0,30}(not|no|does not).{0,20}(allow|usable)|not\s+usable|no\s+ask\s+tool\s+is\s+usable", r"wait")
            self.assertIsNotNone(p, f"{name} instruction has no plain-text fallback when the ask tool is unusable in the session or mode")
            self.assertRegex(p, r"(?i)recommended")
            self.assertRegex(p, r"(?i)discuss")

    def test_plain_text_only_as_fallback(self):
        for name, text in asked_blocks().items():
            p = find_block(text, r"harness'?s? own ask\s+tool", r"usable", r"user picks|picks (rather|instead)", r"plain\s+text")
            self.assertIsNotNone(p, f"{name} instruction does not make the harness's ask tool the first route")
            self.assertRegex(p, r"(?i)(only|fallback)")
            self.assertRegex(p, r"(?i)(has none|no ask tool|harness without)")

    def test_discuss_option_holds_the_decision(self):
        for name, text in asked_blocks().items():
            p = find_block(text, r"discussion|discuss", r"not\s+written", r"settles?", r"Chosen by: `?user")
            self.assertIsNotNone(p, f"{name} instruction does not hold a decision under discussion unwritten")

    def test_you_decide_records_agent(self):
        for name, text in asked_blocks().items():
            p = find_block(text, r"you decide", r"recommended", r"Chosen by: `?agent", r"note|noting")
            self.assertIsNotNone(p, f"{name} instruction does not record 'you decide' as Chosen by: agent with a note")
            self.assertRegex(p, r"(?i)handed")


def apply_instruction():
    """The `apply:` section of the schema (it is not an artifact)."""
    text = read(SCHEMA)
    m = re.search(r"^apply:\s*$", text, re.M)
    assert m, "schema.yaml has no apply section"
    return text[m.start():]


class ProtectingUserChoices(unittest.TestCase):
    """Requirements: A user-chosen decision changes only with the user; decisions changed after planning follow the mode."""

    def test_review_change_to_user_choice_asks_first(self):
        p = find_block(schema_block("review"), r"Required\s+Changes", r"revers\w+", r"Chosen by: `?user", r"user\s+first|to\s+the\s+user\s+before|before\s+(applying|editing)")
        self.assertIsNotNone(p, "review instruction does not send a required change reversing a user choice to the user first")
        self.assertRegex(p, r"(?i)options")
        self.assertRegex(p, r"(?i)recommended")
        self.assertRegex(p, r"(?i)until\s+(the\s+user|they)\s+answers?")

    def test_user_choice_protected_in_every_mode(self):
        p = find_block(schema_block("review"), r"Chosen by: `?user", r"any\s+mode|every\s+mode", r"autonomous", r"summary\s+row", r"unchanged")
        self.assertIsNotNone(p, "review instruction does not protect a user choice, entry and summary row, in every mode")
        d = find_block(apply_instruction(), r"SPEC OR DESIGN DRIFT", r"Chosen by: `?user", r"user")
        self.assertIsNotNone(d, "apply drift rule does not send a change to a user choice to the user")
        self.assertRegex(d, r"(?i)(any|every)\s+mode|always")

    def test_agent_choices_applied_without_asking_in_autonomous(self):
        p = find_block(schema_block("review"), r"Chosen by: `?agent", r"autonomous", r"without\s+asking", r"summary\s+table")
        self.assertIsNotNone(p, "review instruction does not apply agent-chosen required changes per the mode and update the summary table")
        self.assertRegex(p, r"(?i)mode")

    def test_apply_drift_follows_mode(self):
        d = find_block(apply_instruction(), r"SPEC OR DESIGN DRIFT", r"replacement\s+decision", r"DECISION_MAKING", r"setting", r"important")
        self.assertIsNotNone(d, "apply drift rule does not make a replacement decision follow the recorded mode")
        self.assertRegex(d, r"(?i)to\s+the\s+user")
        self.assertRegex(d, r"(?i)before\s+(amending|the\s+(design|artifact))")

    def test_autonomous_drift_amends_agent_choice_and_rereviews(self):
        d = find_block(apply_instruction(), r"SPEC OR DESIGN DRIFT", r"autonomous", r"Chosen by: `?agent", r"summary\s+table", r"re-run\s+the\s+review")
        self.assertIsNotNone(d, "apply drift rule does not amend an agent choice in autonomous mode, update the summary table and re-review")
        self.assertRegex(d, r"(?i)without\s+asking")


if __name__ == "__main__":
    unittest.main()
