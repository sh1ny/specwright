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
        # pre-ship F2: tasks.md is staged whole, so a long id list shortens the subject, never defers a trailer
        self.assertNotRegex(s, r"(?i)leave ids that do not fit", "the skill defers user ticks that do not fit the subject")
        self.assertRegex(s, r"(?i)record user checks.{0,400}?`and more`[^.]{0,80}trailers? name every (user )?tick",
                         "the record user checks commit does not keep a trailer for every tick")

    def test_reconcile_compares_agent_ticks_only(self):
        # pre-ship F2: a user tick in the tasks.md diff never trips the store recovery predicates
        r = flat(section(read(COMMIT), r"Reconcile \("))
        self.assertRegex(r, r"(?i)(only that task|exactly those)[^.]{0,200}agent and evidence (ticks|tasks)",
                         "Reconcile still compares user ticks in the tasks.md diff")
        self.assertRegex(r, r"(?i)user ticks in the diff[^.]{0,200}`Specwright-User-Task`",
                         "Reconcile does not add the user-task trailers when it completes the store commit")
        self.assertRegex(r, r"(?i)agent or evidence ticks in more than one group",
                         "Reconcile still stops on user ticks spread over groups")

CONFIG = ROOT / "templates" / "openspec" / "config.yaml"
FINISH = ROOT / "skills" / "specwright-finish" / "SKILL.md"
PR = ROOT / "skills" / "specwright-pr" / "SKILL.md"


def context_lines():
    """The flattened lines of the template config `context:` block, one per MANDATORY or rule line."""
    return [flat(l).strip() for l in read(CONFIG).splitlines() if l.startswith("  ")]


def pr_bullet(lead):
    """One flattened bullet of specwright-pr watch that starts with `- **lead`."""
    m = re.search(r"^   - \*\*" + lead + r".*?(?=^   - \*\*|^## )", read(PR), re.M | re.S)
    assert m, f"specwright-pr has no watch bullet {lead}"
    return flat(m.group(0))


class ArchiveAndMergeWaitForUser(unittest.TestCase):
    def test_archive_context_line_stops_on_user_task(self):
        lines = [l for l in context_lines() if re.search(r"`\[user\]`", l)]
        self.assertEqual(len(lines), 1, "the config context has not exactly one line about a `[user]` task")
        l = lines[0]
        self.assertTrue(l.startswith("MANDATORY: Before archiving a change"), "the `[user]` rule is not on the archive line")
        for name in ("/opsx:archive", "/opsx:bulk-archive", "openspec-archive-change", "'openspec archive'"):
            self.assertIn(name, l, f"the archive line does not name {name}")
        self.assertRegex(l, r"(?i)unticked `\[user\]` task[^.]{0,40}stops the archive", "the line does not say an unticked `[user]` task stops the archive")
        self.assertRegex(l, r"`tasks\.md`", "the line does not read `tasks.md`")
        self.assertRegex(l, r"(?i)move nothing, sync no spec, name the waiting tasks", "the line does not say move nothing, sync no spec, name the waiting tasks")
        self.assertRegex(l, r"(?i)bulk archive skips that change and archives the rest", "the line does not skip the change in a bulk archive")
        self.assertRegex(l, r"(?i)ticked one does not stop", "the line does not say a ticked task does not stop the archive")
        self.assertRegex(l, r"(?i)/opsx:verify, openspec-verify-change\)[^.]*unticked `\[user\]` task as waiting on the user", "verify does not report an unticked `[user]` task as waiting on the user")
        self.assertRegex(l, r"(?i)never reports the change verified", "verify may report the change verified")

    def test_archive_gate_only_on_unticked(self):
        c = read(CONFIG)
        self.assertRegex(flat(c), r"(?i)an unticked `\[user\]` task stops the archive.{0,200}; a ticked one does not stop it", "the gate is not limited to an unticked task")
        # the gate sits on the DEFERRED archive line, before the finish line
        i, j, k = c.find("VERDICT: DEFERRED"), c.find("unticked `[user]`"), c.find("Invoke the 'specwright-finish'")
        self.assertTrue(0 < i < j < k, "the `[user]` rule is not on the DEFERRED archive line, before the finish line")

    def test_finish_checks_archived_user_tasks(self):
        s0 = flat(section(read(FINISH), r"Steps").split(" 1. **Branch:**")[0])
        self.assertRegex(s0, r"task-cover\.sh", "finish step 0 does not run task-cover.sh")
        self.assertRegex(s0, r"<specwright-commit>/scripts/task-cover\.sh", "finish step 0 does not give the specwright-commit script path")
        self.assertRegex(s0, r"changes/archive/<archived-name>/tasks\.md", "finish step 0 does not read the archived tasks.md")
        self.assertRegex(s0, r"(?i)non-empty `waiting_on_user`[^.]{0,120}stop|stop[^.]{0,200}non-empty `waiting_on_user`", "finish step 0 does not stop on a non-empty `waiting_on_user`")
        self.assertRegex(s0, r"(?i)exit 1[-– ]*(to )?3", "finish step 0 does not stop on a script failure (exit 1-3)")
        self.assertRegex(s0, r"(?i)same undo plan", "finish step 0 does not show the same undo plan as the DEFERRED stop")

    def test_watch_waits_on_user_before_archive_and_merge(self):
        a = pr_bullet("Archive before merge")
        m = pr_bullet("Merge:")
        u = pr_bullet("User tasks")
        self.assertRegex(u, r"task-cover\.sh --rev <ready head>", "watch does not run task-cover.sh at the ready head")
        self.assertRegex(u, r"(?i)never the working tree", "watch may read the working tree")
        self.assertRegex(u, r"changes/archive/<archived-name>/tasks\.md", "watch does not fall back to the archived tasks.md")
        self.assertRegex(u, r"ready, waiting on the user: <ids>", "watch does not report `ready, waiting on the user: <ids>`")
        self.assertRegex(u, r"(?i)no archive commit", "watch may still push an archive commit")
        self.assertRegex(u, r"(?i)no merge request", "watch may still send a merge request")
        self.assertRegex(u, r"(?i)before it archives and again before every merge request", "watch does not check before archive and before each merge request")
        self.assertRegex(a, r"(?i)\*\*User tasks\*\*|user-task check", "the archive bullet does not point at the user-task check")
        self.assertRegex(m, r"(?i)\*\*User tasks\*\*|user-task check", "the merge bullet does not point at the user-task check")
        # pre-ship F1: roadmap branches have no change tasks.md and are not blocked by the check
        self.assertRegex(u, r"docs/project-baseline", "the user-task check does not exempt roadmap branches")
        self.assertRegex(u, r"docs/close-\*", "the user-task check does not exempt docs/close-* branches")

    def test_watch_rejudges_after_tick(self):
        u = pr_bullet("User tasks")
        self.assertRegex(u, r"(?i)tick commit", "watch does not mention the tick commit")
        self.assertRegex(u, r"(?i)judges the new head like any pushed commit", "watch does not judge the tick head like any pushed commit")
        self.assertRegex(u, r"(?i)only once it is ready again", "watch does not archive/merge only once ready again")

    def test_watch_unknown_user_check_blocks_merge(self):
        u = pr_bullet("User tasks")
        self.assertRegex(u, r"(?i)exit 2 or 3", "watch does not handle exit 2 or 3")
        self.assertRegex(u, r"(?i)user-task check as unknown", "watch does not report the user-task check as unknown")
        self.assertRegex(u, r"(?i)unknown[^.]{0,120}send no merge request|send no merge request[^.]{0,60}unknown", "an unknown check does not block the merge request")


if __name__ == "__main__":
    unittest.main()
