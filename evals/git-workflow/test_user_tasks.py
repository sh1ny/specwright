"""The delivered schema, templates, skills and agent definitions carry the rules of user-verified-tasks.

These checks assert where a rule sits and its key terms, not exact wording, in the style of
evals/git-workflow/test_instructions.py. They prove the rule is in the instructions, not that a live
agent follows it; `task-cover.sh` behaviour is tested in evals/git-workflow/test_task_cover.py.

Run: python -m unittest evals/git-workflow/test_user_tasks.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "specwright" / "schema.yaml"
TASKS_TEMPLATE = ROOT / "schemas" / "specwright" / "templates" / "tasks.md"
IMPLEMENTERS = [ROOT / "agents" / h / f"specwright-implementer{s}.md" for h in ("claude", "omp") for s in ("", "-light")]


def read(p):
    return p.read_text(encoding="utf-8")


def flat(text):
    return re.sub(r"\s+", " ", text)


def artifact_instruction(artifact_id):
    """The flattened instruction of one schema artifact (`proposal`, `review`, `tasks`)."""
    text = read(SCHEMA)
    m = re.search(r"^  - id: " + artifact_id + r"$.*?(?=^  - id: |^apply:)", text, re.M | re.S)
    assert m, f"schema.yaml has no artifact {artifact_id}"
    return flat(m.group(0))


def apply_instruction():
    """The flattened `apply:` block of the schema."""
    text = read(SCHEMA)
    m = re.search(r"^apply:.*", text, re.M | re.S)
    assert m, "schema.yaml has no apply block"
    return flat(m.group(0))


def frontmatter_body(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return text[m.end():] if m else text


class ApplyNeverTouchesUserTasks(unittest.TestCase):
    def test_apply_skips_and_never_dispatches_user_tasks(self):
        a = apply_instruction()
        self.assertRegex(a, r"`\[user\]`", "apply does not name the `[user]` marker")
        self.assertRegex(a, r"(?i)never tick\w*,? implement\w* or dispatch\w*[^.]{0,80}`\[user\]` task",
                         "apply does not forbid ticking, implementing and dispatching a `[user]` task")
        self.assertRegex(a, r"(?i)`\[user\]` task[^.]{0,120}(implementer|worker)|(implementer|worker)[^.]{0,120}`\[user\]` task",
                         "apply does not name the implementer or worker a `[user]` task must never go to")
        self.assertRegex(a, r"(?i)skip\w*[^.]{0,60}`\[user\]`|`\[user\]`[^.]{0,80}skip", "apply does not skip a `[user]` task")
        self.assertRegex(a, r"(?i)waiting on the user", "apply does not list a `[user]` task as waiting on the user")

    def test_implementers_refuse_user_tasks(self):
        for p in IMPLEMENTERS:
            with self.subTest(p.parent.name + "/" + p.name):
                body = flat(frontmatter_body(read(p)))
                self.assertRegex(body, r"`\[user\]` task", f"{p.name}: does not name a `[user]` task")
                self.assertRegex(body, r"(?i)`\[user\]` task[^.]{0,200}\brefus\w*|\brefus\w*[^.]{0,120}`\[user\]` task",
                                 f"{p.name}: does not refuse a `[user]` task")
                self.assertRegex(body, r"(?i)no work for it", f"{p.name}: does not say it does no work for the task")
                self.assertRegex(body, r"(?i)BLOCKED[^.]{0,40}user task|user task[^.]{0,40}BLOCKED",
                                 f"{p.name}: does not report the refused task BLOCKED as a user task")

    def test_chat_report_asks_user_to_tick(self):
        a = apply_instruction()
        self.assertRegex(a, r"(?i)(user|they) (reports?|says?|tells?)[^.]{0,80}\bin chat",
                         "apply does not cover the user reporting a result in chat")
        self.assertRegex(a, r"(?i)\bin chat[^.]{0,200}\bask\w* (them|the user) to tick[^.]{0,60}`tasks\.md`",
                         "apply does not ask the user to tick the task in `tasks.md` after a chat report")
        self.assertRegex(a, r"(?i)tick\w* it themselves|never writes the `?x`?|agent never writes the `?x`?",
                         "apply does not say the agent never writes the x")


class TestMapUserState(unittest.TestCase):
    def test_test_map_user_state(self):
        t = artifact_instruction("tasks")
        self.assertRegex(t, r"`user`", "the tasks instruction does not name the test map state `user`")
        self.assertRegex(t, r"(?i)only a person can judge[^.]{0,200}`user`|`user`[^.]{0,200}only a person can judge",
                         "state `user` is not tied to a scenario only a person can judge")
        self.assertRegex(t, r"(?i)names? the user task id", "the row does not name the user task id")
        self.assertRegex(t, r"(?i)turns `green` when its user task is ticked",
                         "the row does not turn green when its user task is ticked")
        self.assertRegex(t, r"(?i)testable scenario never maps to a user task",
                         "a testable scenario may map to a user task")
        self.assertRegex(t, r"`- \[ \] 4\.3 \[user\] ", "no `[user]` marker example")
        self.assertRegex(t, r"`- \[ \] 4\.2 \[evidence\] [^`]*evidence/<file>`", "no `[evidence]` marker example")
        self.assertRegex(t, r"(?i)evidence/[^.]{0,200}non-empty[^.]{0,120}committed",
                         "the evidence rule lacks present, non-empty and committed")
        tpl = read(TASKS_TEMPLATE)
        self.assertRegex(tpl, r"\[user\]", "the tasks template has no `[user]` example")
        self.assertRegex(tpl, r"\[evidence\]", "the tasks template has no `[evidence]` example")

    def test_review_flags_testable_scenario_on_user_task(self):
        r = artifact_instruction("review")
        self.assertRegex(r, r"(?i)testable scenario[^.]{0,100}(mapped|maps?) to a (`\[user\]`|user) task[^.]{0,60}finding|"
                            r"finding[^.]{0,100}testable scenario[^.]{0,100}user task",
                         "the review does not list a testable scenario mapped to a user task as a finding")


class ExitCriterionReachesTasks(unittest.TestCase):
    def test_user_criterion_becomes_user_task(self):
        t = artifact_instruction("tasks")
        self.assertRegex(t, r"(?i)user-verified[^.]{0,80}exit criteri\w+[^.]{0,200}`\[user\]` task|"
                            r"`\[user\]` task[^.]{0,200}user-verified[^.]{0,80}exit criteri",
                         "the tasks instruction does not carry a user-verified exit criterion into a `[user]` task")
        self.assertRegex(t, r"(?i)proposal names", "the carry-through is not limited to criteria the proposal names")

    def test_criterion_at_close_explained_in_proposal(self):
        p = artifact_instruction("proposal")
        self.assertRegex(p, r"(?i)user-verified[^.]{0,80}exit criteri\w+", "the proposal instruction does not mention user-verified exit criteria")
        self.assertRegex(p, r"(?i)judged at the milestone close[^.]{0,60}\bwhy\b|\bwhy\b[^.]{0,80}judged at the milestone close",
                         "the proposal is not asked to say a criterion is judged at the milestone close and why")
        t = artifact_instruction("tasks")
        self.assertRegex(t, r"(?i)judged at (the )?milestone close[^.]{0,60}\bwhy\b",
                         "the tasks instruction does not accept the proposal saying it is judged at close and why")


COMMIT = ROOT / "skills" / "specwright-commit" / "SKILL.md"


def section(text, heading_re):
    """Text from a markdown heading matching heading_re up to the next heading of the same or higher level."""
    m = re.search(r"^(#+) " + heading_re + r".*$", text, re.M | re.I)
    assert m, f"specwright-commit SKILL.md has no section {heading_re}"
    nxt = re.search(r"^#{1,%d} " % len(m.group(1)), text[m.end():], re.M)
    return flat(text[m.start(): m.end() + nxt.start()] if nxt else text[m.start():])


class CommitSkillUserTasks(unittest.TestCase):
    def test_group_commit_skips_user_tasks(self):
        g = section(read(COMMIT), r"Group mode")
        self.assertRegex(g, r"(?i)never ticks? a user task|never tick\w* a `\[user\]` task",
                         "group mode does not say a user task is never ticked")
        self.assertRegex(g, r"(?i)`\[user\]`[^.]{0,200}(never|not)[^.]{0,60}(hold|block)\w* (back )?the group|"
                            r"user tasks? (never|do not|does not)[^.]{0,40}hold\w* (back )?the group",
                         "group mode does not say a user task never holds the group commit back")
        self.assertRegex(g, r"(?i)`Specwright-Task`[^.]{0,120}agent and evidence tasks? only|"
                            r"agent and evidence tasks? only[^.]{0,120}`Specwright-Task`|only[^.]{0,40}agent and evidence tasks",
                         "group mode does not limit Specwright-Task trailers to agent and evidence tasks")
        s = flat(read(COMMIT))
        self.assertRegex(section(read(COMMIT), r"Reconcile"), r"(?i)`user_uncommitted`[^.]{0,200}(apart|separate)\w*[^.]{0,80}pending|"
                                                            r"(apart|separate)\w*[^.]{0,80}pending[^.]{0,200}`user_uncommitted`",
                         "Reconcile does not list `user_uncommitted` apart from pending groups")
        self.assertRegex(section(read(COMMIT), r"Reconcile"), r"(?i)user tick[^.]{0,120}(never|not)[^.]{0,60}(makes?|pending)",
                         "Reconcile does not say a user tick never makes a group pending")

    def test_completion_reports_waiting_on_user(self):
        c = section(read(COMMIT), r"3\. When every task")
        self.assertRegex(c, r"(?i)every (agent and evidence|agent or evidence) task|agent and evidence tasks",
                         "the completion check does not count agent and evidence tasks only")
        self.assertRegex(c, r"waiting on the user: <ids>", "the completion check does not report `waiting on the user: <ids>`")
        self.assertRegex(c, r"`waiting_on_user`", "the completion check does not take the ids from `waiting_on_user`")
        self.assertRegex(c, r"(?i)user tasks? (still )?open[^.]{0,120}hand\w*|hand\w*[^.]{0,120}user tasks? (still )?open|"
                            r"open user tasks?[^.]{0,120}hand",
                         "the completion check does not hand off with user tasks still open")

    def test_commit_stops_on_evidence_missing(self):
        c = section(read(COMMIT), r"3\. When every task")
        self.assertRegex(c, r"(?i)`evidence_missing`[^.]{0,200}stop|stop\w*[^.]{0,120}`evidence_missing`",
                         "the completion check does not stop on `evidence_missing`")
        s = flat(read(COMMIT))
        self.assertRegex(s, r"(?i)evidence task[^.]{0,200}`evidence/`[^.]{0,120}non-empty[^.]{0,120}committed|"
                            r"evidence task[^.]{0,200}non-empty[^.]{0,120}committed",
                         "the skill does not tick an evidence task only with a present, non-empty, committed evidence file")

    def test_record_user_checks_commit(self):
        s = flat(read(COMMIT))
        self.assertRegex(s, r"`Specwright-User-Task: X\.Y`", "the skill does not name the `Specwright-User-Task: X.Y` trailer")
        self.assertRegex(s, r"(?i)every commit that stages `tasks\.md`[^.]{0,200}`Specwright-User-Task",
                         "the skill does not put the user-task trailer on every commit that stages tasks.md")
        self.assertRegex(s, r"`user_uncommitted`", "the skill does not name `user_uncommitted`")
        self.assertRegex(s, r"<type>\(<change-name>\): record user checks <ids>",
                         "the skill does not give the `record user checks <ids>` subject")
        block = section(read(COMMIT), r"Group mode")
        self.assertRegex(block, r"(?i)no agent work pending[^.]{0,120}`tasks\.md` alone|`tasks\.md` alone[^.]{0,120}no agent work pending",
                         "the skill does not commit `tasks.md` alone when no agent work is pending")
        self.assertRegex(s, r"(?i)before (the user's )?`?Co-authored-by", "the trailer is not placed before Co-authored-by")


if __name__ == "__main__":
    unittest.main()
