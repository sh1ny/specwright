"""The roadmap skill and the settings template carry the rules of the roadmap-init-autonomy change.

Wording checks in the style of test_decision_making.py: they assert where a rule sits and its key
terms, not exact wording. They prove the rule is in the instructions, not that a live agent follows it.

Run: python -m unittest evals/git-workflow/test_roadmap_autonomy.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "specwright-roadmap" / "SKILL.md"
TEMPLATE = ROOT / "templates" / "openspec" / "specwright.yaml"
README = ROOT / "README.md"
STRATEGY = ROOT / "skills" / "specwright-roadmap" / "references" / "strategy.md"
PR_SKILL = ROOT / "skills" / "specwright-pr" / "SKILL.md"
ARCH = ROOT / "openspec" / "architecture.md"

MODES = ("autonomous", "important", "all")


def read(p):
    return p.read_text(encoding="utf-8")


def paragraphs(text):
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def find_block(text, *patterns):
    """First paragraph matching every pattern (case-insensitive), or None."""
    for p in paragraphs(text):
        if all(re.search(pat, p, re.I | re.S) for pat in patterns):
            return p
    return None


class ModeFromSetting(unittest.TestCase):
    """Requirement: Roadmap runs read their decision mode from the project setting."""

    def test_unset_means_important_interview(self):
        p = find_block(read(SKILL), r"project\.decision_making", r"init", r"close", r"pack",
                       r"unset", r"important", r"before any")
        self.assertIsNotNone(p, "SKILL.md does not say init, close and pack read project.decision_making first, unset meaning important")
        self.assertRegex(p, r"(?i)unset.{0,40}important|important.{0,60}unset")

    def test_unknown_value_stops_before_write(self):
        p = find_block(read(SKILL), r"project\.decision_making", r"unknown|any other|not one of|invalid",
                       r"stop", r"before any", r"nam")
        self.assertIsNotNone(p, "SKILL.md has no stop rule for an unknown project.decision_making value")
        for mode in MODES:
            self.assertIn(mode, p)
        self.assertRegex(p, r"(?i)branch|write")

    def test_top_level_decision_making_not_read(self):
        p = find_block(read(SKILL), r"top-level", r"decision_making", r"never|not", r"roadmap")
        self.assertIsNotNone(p, "SKILL.md does not say the top-level decision_making never sets the roadmap mode")


class Override(unittest.TestCase):
    """Requirement: A user instruction overrides the roadmap mode for one run."""

    def test_override_recorded_with_words_setting_unchanged(self):
        p = find_block(read(SKILL), r"instruction|spoken|says", r"specwright\.yaml",
                       r"unchanged|never (write|change|edit)|not (write|change|edit)",
                       r"source", r"user", r"words", r"decision summary")
        self.assertIsNotNone(p, "SKILL.md does not say a user instruction is recorded with source user and the words, leaving specwright.yaml unchanged")
        self.assertRegex(p, r"(?i)\(source: setting\)|source: setting")
        self.assertRegex(p, r"(?i)close M<n>")
        self.assertRegex(p, r"(?i)pack <name>")

    def test_override_for_one_run_only(self):
        p = find_block(read(SKILL), r"instruction|spoken|says", r"(this|that|one) run only|only for (this|that|the) run|one run",
                       r"next run|later run|every run|each run|another run", r"setting")
        self.assertIsNotNone(p, "SKILL.md does not say the override holds for one run and the next run reads the setting again")


def section(text, heading):
    """The body of a `## heading` section of SKILL.md, up to the next `## `."""
    m = re.search(r"^## " + re.escape(heading) + r"\s*$", text, re.M)
    assert m, f"SKILL.md has no section {heading}"
    nxt = re.search(r"^## ", text[m.end():], re.M)
    return text[m.end(): m.end() + nxt.start()] if nxt else text[m.end():]


class Autonomous(unittest.TestCase):
    """Requirement: An autonomous roadmap run asks nothing and records every answer."""

    def test_init_asks_nothing_and_records_rows(self):
        p = find_block(read(SKILL), r"`autonomous`", r"ask(s)? nothing|no question", r"gap", r"ADR",
                       r"`agent` row", r"decision summary", r"reason", r"without (a )?wait")
        self.assertIsNotNone(p, "SKILL.md does not say an autonomous run asks nothing, records agent rows with reasons and shows them without a wait")

    def test_pack_mode_autonomous(self):
        s = section(read(SKILL), "pack")
        p = find_block(s, r"`autonomous`", r"ask(s)? nothing|no question", r"`agent` row", r"pack document")
        self.assertIsNotNone(p, "pack mode does not say an autonomous run answers the questions itself and records agent rows")

    def test_pack_offer_pending_not_enabled(self):
        p = find_block(read(SKILL), r"`autonomous`", r"pack offer", r"`pending` row", r"not enabled",
                       r"`packs:`.{0,40}unchanged", r"(goes|go) on")
        self.assertIsNotNone(p, "SKILL.md does not say an autonomous pack offer becomes a pending row, with the pack not enabled")

    def test_pack_questions_autonomous_init(self):
        s = section(read(SKILL), "init")
        p = find_block(s, r"`autonomous`", r"pack", r"`init` `questions`|pack questions", r"`agent` row", r"pack document")
        self.assertIsNotNone(p, "init step 2 does not say an autonomous init answers the pack questions itself into the pack documents")


class Rounds(unittest.TestCase):
    """Requirement: A question round may span several ask-tool calls."""

    def test_round_spans_calls_init(self):
        p = find_block(read(SKILL), r"round is", r"before any", r"several (ask-tool )?calls|more than one call|several calls",
                       r"Codex", r"no third round", r"dropped|drop")
        self.assertIsNotNone(p, "SKILL.md does not say a round may span several ask-tool calls, with init keeping two rounds")
        self.assertRegex(p, r"(?i)schema.{0,200}proposal|proposal.{0,200}schema")

    def test_round_spans_calls_pack(self):
        s = section(read(SKILL), "pack")
        p = find_block(s, r"one (batched )?round", r"several (ask-tool )?calls|more than one call", r"answered|answers")
        self.assertIsNotNone(p, "pack mode does not say its one round may span several calls, written only after all are answered")
        self.assertRegex(p, r"(?i)only after|not before|before any")


class AllMode(unittest.TestCase):
    """Requirement: In all mode every roadmap decision goes to the user."""

    def test_adr_and_replan_choices_in_further_batches(self):
        p = find_block(read(SKILL), r"`all`", r"ADR", r"re-plan", r"batch", r"at most 4",
                       r"Chosen by: user", r"before step 4")
        self.assertIsNotNone(p, "SKILL.md does not put ADR and re-plan choices to the user in further batches of at most 4 in all mode")
        self.assertRegex(p, r"(?i)lower limit|fewer")

    def test_asked_before_file_written(self):
        p = find_block(read(SKILL), r"`all`", r"before the file", r"session ends|ends before",
                       r"no ADR", r"next session asks again")
        self.assertIsNotNone(p, "SKILL.md does not say each batch is asked before its file is written, so an interrupted session leaves no ADR")


def init_step(n):
    s = section(read(SKILL), "init")
    m = re.search(r"^" + str(n) + r"\. .*$", s, re.M)
    assert m, f"init has no step {n}"
    return m.group(0)


class Summary(unittest.TestCase):
    """Requirement: The strategy carries the roadmap's decision summary."""

    def test_summary_edit_does_not_void_baseline(self):
        s5 = init_step(5)
        self.assertRegex(s5, r"(?is)edit to the strategy, architecture or ADRs voids it")
        self.assertRegex(s5, r"(?is)except.{0,300}(`## Decision summary`|decision summary).{0,200}(not void|never void|does not void)|"
                             r"(`## Decision summary`|decision summary).{0,200}(not void|never void|does not void)",
                         "init step 5 does not exempt edits confined to the decision summary from voiding the pass")
        self.assertRegex(s5, r"(?is)confined to")

    def test_pr_feedback_summary_only_no_rerun(self):
        text = read(PR_SKILL)
        p = find_block(text, r"docs/project-baseline", r"docs/close-", r"Decision summary", r"confined", r"architecture-review\.md")
        self.assertIsNotNone(p, "PR feedback does not exempt a fix confined to the decision summary from a new baseline round")
        self.assertRegex(p, r"(?is)(without|no) (a )?new baseline (review|round)|not re-?run")
        self.assertRegex(p, r"(?is)unchanged")

    def test_edit_outside_section_still_voids(self):
        s5 = init_step(5)
        self.assertRegex(s5, r"(?is)(any|an) (other )?edit (outside|elsewhere|beyond|not confined).{0,200}voids|"
                             r"(outside|beyond) (that|the) (section|summary).{0,200}voids",
                         "init step 5 does not say an edit outside the summary still voids the pass")

    def test_close_puts_pending_rows_to_owner(self):
        s = section(read(SKILL), "close")
        p = find_block(s, r"`pending` rows?", r"start", r"`important`|important", r"Chosen by: user", r"`autonomous`.{0,80}(leaves?|stay)")
        self.assertIsNotNone(p, "close does not list open pending rows at its start and put them to the owner")
        self.assertRegex(p, r"(?is)answer")

    def test_assumptions_list_kept(self):
        p = find_block(read(SKILL), r"`## Assumptions`", r"(left|kept|read) as (it is|is)", r"never rewritten|not rewritten",
                       r"`## Decision summary`", r"after it")
        self.assertIsNotNone(p, "SKILL.md does not leave an older Assumptions list as it is and add the summary after it")

    def test_rows_in_every_mode_and_step2_points_to_summary(self):
        self.assertIsNotNone(find_block(read(SKILL), r"rows? (are|is) written in every mode|every mode", r"Chosen by: user", r"`important`"))
        s2 = init_step(2)
        self.assertNotRegex(s2, r"stated assumption")
        self.assertRegex(s2, r"(?is)everything else.{0,200}`agent` rows?.{0,80}decision summary")

    def test_exemption_in_architecture_md(self):
        text = read(ARCH)
        row = next((l for l in text.splitlines() if l.startswith("| Design review")), "")
        self.assertRegex(row, r"(?i)decision summary", "architecture.md design-review row has no summary exemption")
        p = find_block(text, r"project\.decision_making", r"Decision summary", r"R\d|R ids?", r"pending", r"never deleted|not deleted")
        self.assertIsNotNone(p, "architecture.md has no contract bullet for project.decision_making and the decision summary")
        self.assertRegex(p, r"(?is)unset.{0,40}important")
        self.assertRegex(p, r"(?is)unknown.{0,40}stop")


class StrategyTemplate(unittest.TestCase):
    def test_decision_summary_replaces_assumptions(self):
        t = read(STRATEGY)
        self.assertIn("## Decision summary", t)
        self.assertNotIn("## Assumptions", t)

    def test_run_line_and_table(self):
        t = read(STRATEGY)
        self.assertIn("- <run> <YYYY-MM-DD>: <mode> (source: setting)", t)
        self.assertIn('(source: user, "<words>")', t)
        for run in ("init", "close M<n>", "pack <name>"):
            self.assertIn(run, t)
        header = "| # | Run | Decision | Choice | Rejected | Reason | Important | Chosen by |"
        self.assertIn(header, t)
        self.assertRegex(t, r"R1")
        for v in ("agent", "user", "pending"):
            self.assertIn(v, t)
        self.assertRegex(t, r"(?i)in place")
        self.assertRegex(t, r"(?i)never deleted|not deleted|never removed")


def close_text():
    return section(read(SKILL), "close")


class OwnerGates(unittest.TestCase):
    """Requirement: Autonomy never passes a gate meant for the owner."""

    def test_agreed_split_amendment_pending(self):
        p = find_block(close_text(), r"Split agreed", r"`autonomous`", r"amendment", r"`pending` row", r"not applied",
                       r"unchanged", r"in order")
        self.assertIsNotNone(p, "close does not record an autonomous amendment to an agreed split as a pending row, promoting the split unchanged")
        self.assertRegex(p, r"(?is)never add the line|no `Split agreed|never (writes?|adds?) a `?\*{0,2}Split agreed|never gets a `?\*{0,2}Split agreed")

    def test_amendment_asked_in_interactive_modes(self):
        p = find_block(close_text(), r"Split agreed", r"`important` and `all`", r"amendment", r"ask")
        self.assertIsNotNone(p, "close does not ask an amendment to an agreed split in important and all mode")

    def test_unagreed_listing_promoted_no_split_line(self):
        p = find_block(close_text(), r"without that line", r"`autonomous`", r"as it stands", r"in order", r"`agent` row")
        self.assertIsNotNone(p, "close does not promote an unmarked listing as it stands, in order, with an agent row, in autonomous mode")
        self.assertRegex(p, r"(?is)(never|no).{0,60}Split agreed")
        self.assertRegex(p, r"(?is)no changes.{0,200}`agent` row")

    def test_unmarked_split_asked_in_interactive_modes(self):
        p = find_block(close_text(), r"without that line", r"`important` and `all`", r"ask the user whether")
        self.assertIsNotNone(p, "close does not ask about an unmarked split in important and all mode")

    def test_user_criterion_never_passed(self):
        p = find_block(close_text(), r"user-verified", r"unverified", r"any mode|every mode|whatever the mode",
                       r"stays? in Now", r"never")
        self.assertIsNotNone(p, "close does not keep an unverified user-verified criterion unverified in every mode")
        self.assertRegex(p, r"(?is)`autonomous`.{0,200}stops? at step 3 before its branch exists.{0,200}writes? nothing.{0,80}no branch, no row"
                            r".{0,200}(lists?|report).{0,120}(run's report|report)",
                         "autonomous close does not stop before its branch, write nothing and list the criterion in the report")
        self.assertRegex(p, r"(?is)next close.{0,40}(finds?|walks?).{0,40}again")
        self.assertNotRegex(p, r"(?is)record it as a `pending` row", "an unverified user criterion must not become a pending row")

    def test_close_writes_summary_only_after_its_branch(self):
        # Pre-ship review round 1, F1: owner answers to pending rows (close start) and autonomous
        # release rows (step 3b) come before step 4 creates the branch; they are held until then.
        p = find_block(close_text(), r"step 4", r"branch", r"(hold|keep)s?\b.{0,160}(memory|until)",
                       r"pending", r"stops? before step 4", r"report", r"writes? nothing|nothing is written")
        self.assertIsNotNone(p, "close does not hold summary answers and rows until step 4 creates its branch, "
                                "and report them when it stops before that")
        self.assertRegex(p, r"(?is)answer", "the hold rule does not cover the owner's answers to pending rows")
        self.assertRegex(p, r"(?is)release|untagged|3b", "the hold rule does not cover the release rows of step 3b")

    def test_owner_agreement_still_acts(self):
        p = find_block(read(SKILL), r"owner gate", r"explicit agreement", r"never supplies?|agent never", r"interactive",
                       r"pack", r"`Split agreed`", r"amendment")
        self.assertIsNotNone(p, "SKILL.md does not say the owner gates forbid an action only without the owner's explicit agreement, and an interactive run acts on it")
        self.assertRegex(p, r"(?is)`packs:`")

    def test_release_not_published(self):
        p = find_block(close_text(), r"release\.enabled", r"`autonomous`", r"`pending` row", r"nothing (is )?published|publish(es)? nothing",
                       r"(goes|go) on")
        self.assertIsNotNone(p, "close does not record untagged versions as a pending row without publishing in autonomous mode")


class Escalation(unittest.TestCase):
    """Requirement: Baseline review rounds follow the schema's escalation rule (autonomous part)."""

    def test_findings_copied_before_next_round(self):
        s5 = init_step(5)
        self.assertRegex(s5, r"(?is)`autonomous`.{0,400}before a (new|next) (baseline )?round.{0,200}(replaces?|overwrit).{0,200}"
                             r"copy.{0,120}findings.{0,120}severity.{0,80}one line.{0,200}(decision summary|summary)",
                         "init step 5 does not copy the earlier round's findings into the summary before a new round replaces the review file")

    def test_autonomous_escalation_stops(self):
        s5 = init_step(5)
        self.assertRegex(s5, r"(?is)`autonomous`.{0,400}(2|two) consecutive.{0,40}REVISE.{0,200}stop without asking")
        self.assertRegex(s5, r"(?is)stop without asking.{0,400}no roadmap.{0,200}`Status: proposed`.{0,200}no `VERDICT: USER_OVERRIDE`")
        self.assertRegex(s5, r"(?is)`pending` escalation row.{0,200}round 1.{0,120}severity.{0,80}one line")
        self.assertRegex(s5, r"(?is)never write.{0,80}architecture-review\.md")
        self.assertRegex(s5, r"(?i)stop and ask the user", "the non-autonomous path must still stop and ask")


class Docs(unittest.TestCase):
    """The template and the README name the nested key."""

    def test_template_line_commented_inside_project(self):
        text = read(TEMPLATE)
        m = re.search(r"^project:\s*$", text, re.M)
        self.assertIsNotNone(m, "template has no project: block")
        nxt = re.search(r"^\S", text[m.end():], re.M)
        block = text[m.end(): m.end() + nxt.start()] if nxt else text[m.end():]
        self.assertRegex(block, r"(?m)^  # decision_making: important\b",
                         "template has no commented `  # decision_making: important` line inside project:")
        self.assertNotRegex(block, r"(?m)^  decision_making:", "the nested key must stay commented")
        for mode in MODES:
            self.assertIn(mode, block)
        self.assertRegex(block, r"(?i)unset")

    def test_readme_names_nested_key(self):
        text = read(README)
        m = re.search(r"^project:\s+#.*$", text, re.M)
        self.assertIsNotNone(m, "README settings block has no project: block")
        block = text[m.end(): m.end() + 800]
        self.assertRegex(block.split("\n\n")[0], r"(?m)^\s+#?\s*decision_making:",
                         "README settings block does not list decision_making under project:")
        self.assertIn("project.decision_making", text)
        p = find_block(text, r"project\.decision_making", r"roadmap", r"init", r"top-level|decision_making")
        self.assertIsNotNone(p, "README has no paragraph on the roadmap decision mode")


if __name__ == "__main__":
    unittest.main()
