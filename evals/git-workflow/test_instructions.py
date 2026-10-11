"""The delivered agent, schema, skill and README text carries the rules of fix-agent-skills-and-subjects.

These checks assert where a rule sits and its key terms, not exact wording, in the style of
evals/pr-pair/test_skill_text.py. They prove the rule is in the instructions, not that a live agent
follows it; branch-state and stop paths are covered by the agent evals in evals.json.

Run: python -m unittest discover evals/git-workflow -p "test_instructions.py"
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_AGENTS = [ROOT / "agents" / "claude" / f"specwright-{n}.md" for n in ("implementer", "reviewer")]
OMP_AGENTS = [ROOT / "agents" / "omp" / f"specwright-{n}.md" for n in ("implementer", "reviewer")]
SCHEMA = ROOT / "schemas" / "specwright" / "schema.yaml"
ROADMAP = ROOT / "skills" / "specwright-roadmap" / "SKILL.md"
README = ROOT / "README.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
COMMIT = ROOT / "skills" / "specwright-commit" / "SKILL.md"


def read(p):
    return p.read_text(encoding="utf-8")


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return (m.group(1), text[m.end():]) if m else ("", text)


def paragraphs(text):
    """Blank-line separated blocks; list items stay with their block."""
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def find_block(text, *patterns):
    """First paragraph matching every pattern (case-insensitive), or None."""
    for p in paragraphs(text):
        if all(re.search(pat, p, re.I | re.S) for pat in patterns):
            return p
    return None


def section(text, heading_re):
    """Text from a markdown heading matching heading_re up to the next heading of the same or higher level."""
    m = re.search(r"^(#+) " + heading_re + r".*$", text, re.M | re.I)
    if not m:
        return None
    level = len(m.group(1))
    nxt = re.search(r"^#{1,%d} " % level, text[m.end():], re.M)
    return text[m.start(): m.end() + nxt.start()] if nxt else text[m.start():]


def schema_block(key):
    """The YAML block for a top-level-ish key (`apply:`, `- id: review`) up to the next block at its indent."""
    text = read(SCHEMA)
    m = re.search(r"^(\s*)" + key + r".*$", text, re.M)
    assert m, f"schema.yaml has no {key}"
    indent = len(m.group(1))
    nxt = re.search(r"^\s{0,%d}\S" % indent, text[m.end() + 1:], re.M)
    return text[m.start(): m.end() + 1 + nxt.start()] if nxt else text[m.start():]


def step(text, label):
    """`Step N - ...` paragraph of the README install prompt, up to the next step."""
    m = re.search(r"^" + label + r"\b.*?(?=^Step \d+ |^```)", text, re.M | re.S)
    return m.group(0) if m else None


# Loading a named skill: the agent loads/invokes each skill the packet or request names.
LOAD_NAMED = r"(load|invoke)\w*\b.{0,80}\bskill.{0,80}\b(packet|request)\b.{0,40}\bnames?\b|\bskill.{0,60}\b(packet|request)\b.{0,20}\bnames?\b.{0,120}\b(load|invoke)"
NEW_SESSION = r"\bnew (agent )?session\b|session (started|that starts) after"


class AgentDelegation(unittest.TestCase):
    def test_claude_agents_list_skill_and_load_named_skills(self):
        for p in CLAUDE_AGENTS:
            fm, body = frontmatter(read(p))
            tools = re.search(r"^tools:\s*(.*)$", fm, re.M)
            self.assertTrue(tools, f"{p.name}: no tools line")
            self.assertIn("Skill", [t.strip() for t in tools.group(1).split(",")], f"{p.name}: tools lack Skill")
            block = find_block(body, LOAD_NAMED, r"`Skill`")
            self.assertTrue(block, f"{p.name}: no rule to load each named skill with `Skill`")
            self.assertRegex(block, r"(?i)before\b", f"{p.name}: named skills are not loaded before working")

    def test_omp_agents_read_the_given_skill_path(self):
        for p in OMP_AGENTS:
            fm, body = frontmatter(read(p))
            self.assertRegex(fm, r"(?m)^tools:.*\bread\b", f"{p.name}: tools lack read")
            block = find_block(body, LOAD_NAMED, r"`read`", r"SKILL\.md", r"\bpath\b")
            self.assertTrue(block, f"{p.name}: no rule to `read` the SKILL.md path each named skill comes with")
            self.assertNotRegex(block, r"\.claude/skills/<", f"{p.name}: reads a fixed skills path, not the given one")

    def test_agents_never_invoke_specwright_skills(self):
        for p in CLAUDE_AGENTS + OMP_AGENTS:
            _, body = frontmatter(read(p))
            self.assertTrue(find_block(body, r"\bonly\b.{0,60}\bskills?\b.{0,80}\bnames?\b|\bonly the skills\b"),
                            f"{p.name}: does not limit loading to the named skills")
            self.assertTrue(find_block(body, r"\bnever\b.{0,60}`specwright-\*`"),
                            f"{p.name}: does not forbid invoking `specwright-*` workflow skills")

    def test_agents_report_unloaded_skills(self):
        for p in CLAUDE_AGENTS + OMP_AGENTS:
            _, body = frontmatter(read(p))
            self.assertTrue(find_block(body, r"\breport\w*\b.{0,120}\bskill.{0,80}\b(could not|couldn't|not) (be )?load",
                                       ) or find_block(body, r"\bskill.{0,80}\b(could not|couldn't|not) (be )?load.{0,120}\breport"),
                            f"{p.name}: no rule to report a named skill that could not be loaded")
        for p in (CLAUDE_AGENTS[0], OMP_AGENTS[0]):
            _, body = frontmatter(read(p))
            report = body[body.find("Report, in this shape"):]
            self.assertRegex(report, r"(?m)^- Skills:", f"{p.name}: the report shape has no Skills line")

    def test_schema_packets_and_review_requests_name_skills_or_none(self):
        apply = schema_block("apply:")
        deleg = apply[apply.find("DELEGATION"):]
        deleg = deleg[: deleg.find("\n\n")]
        for name, block in (("apply DELEGATION", deleg),
                            ("design review", schema_block("- id: review")),
                            ("roadmap init step 5", (section(read(ROADMAP), "init") or ""))):
            self.assertRegex(block, r"(?is)\bskills?\b.{0,160}`SKILL\.md`.{0,120}\bpath|\bskills?\b.{0,120}\bpath.{0,80}`SKILL\.md`",
                             f"{name}: does not name skills with their installed SKILL.md path")
            self.assertRegex(block, r"(?is)\bskills?\b.{0,300}`none`", f"{name}: no `none` when no skill applies")
        init5 = re.search(r"^5\. \*\*Review\*\*.*$", read(ROADMAP), re.M)
        self.assertTrue(init5, "roadmap init has no step 5 Review")
        self.assertRegex(init5.group(0), r"SKILL\.md", "roadmap init step 5's request does not name skills with paths")

    def test_install_report_requires_new_session_for_agents(self):
        s8 = step(read(README), "Step 8")
        self.assertTrue(s8, "README install prompt has no Step 8")
        self.assertRegex(s8, r"(?is)" + NEW_SESSION, "README Step 8 does not ask for a new session")
        self.assertRegex(s8, r"(?is)skills\b.{0,40}\bagent definitions|agent definitions\b.{0,40}\bskills",
                         "README Step 8 does not name both skills and agent definitions")
        setup = section(read(CONTRIBUTING), "Setup")
        item = re.search(r"^4\. .*$", setup or "", re.M)
        self.assertTrue(item, "CONTRIBUTING Setup has no step 4")
        self.assertRegex(item.group(0), r"(?i)" + NEW_SESSION, "CONTRIBUTING Setup step 4 does not ask for a new session")
        self.assertRegex(item.group(0), r"(?i)agent definitions", "CONTRIBUTING Setup step 4 does not mention agent definitions")

    def test_readme_probe_rejects_old_session(self):
        evals = section(read(README), r"\S* ?Evals")
        self.assertTrue(evals, "README has no Evals section")
        probe = find_block(evals, r"specwright-implementer", r"`Skill`")
        self.assertTrue(probe, "README Evals has no probe that dispatches specwright-implementer and looks for `Skill`")
        self.assertRegex(probe, r"(?is)" + NEW_SESSION, "the probe does not require a session started after install")
        self.assertRegex(probe, r"(?is)(already )?running (before|during)|started before|old session",
                         "the probe does not reject a session that was running before the install")


def commit_step2():
    text = read(COMMIT)
    s = section(text, r"2\. After each task")
    assert s, "specwright-commit SKILL.md has no '## 2. After each task' section"
    return text, s


FIT = r"fit-subject\.sh`?\s+<msgfile>"


class TaskCommits(unittest.TestCase):
    def test_commit_skill_reuses_fitted_message_for_store_pair(self):
        text, s2 = commit_step2()
        fit = re.search(FIT, s2)
        self.assertTrue(fit, "step 2 never runs `fit-subject.sh <msgfile>`")
        self.assertRegex(s2, r"(?is)full message.{0,80}\btemp file|temp file.{0,80}full message",
                         "step 2 does not write the full message to the temp file first")
        commit = re.search(r"git commit -F <msgfile>", s2[fit.end():])
        self.assertTrue(commit, "no `git commit -F <msgfile>` after the fit in step 2")
        self.assertTrue(find_block(s2, r"store", r"\bsame (message )?file\b|\bsame <msgfile>"),
                        "step 2 does not reuse the same message file for the store commit of a pair")
        self.assertRegex(text, r"(?m)^allowed-tools: Bash\(git \*\) Bash\(openspec \*\)$", "allowed-tools changed")

    def test_commit_skill_stops_on_unfittable_subject(self):
        _, s2 = commit_step2()
        block = find_block(s2, r"\bexit 1\b", r"fit-subject|the script|it exits")
        self.assertTrue(block, "step 2 does not say what to do when fit-subject.sh exits 1")
        self.assertRegex(block, r"(?is)\bno commit\b|\bnever commit|do not commit|make no commit", "exit 1 does not stop the commit")
        self.assertRegex(block, r"(?is)\breport\b.{0,80}\btask\b.{0,40}\bsubject\b.{0,40}\blimit\b|\b72\b",
                         "exit 1 does not report the task, the subject and the limit")


def committing_project_files():
    """The roadmap skill's "Committing project files" text, up to the first mode section."""
    text = read(ROADMAP)
    start = text.find("**Committing project files**")
    assert start >= 0, "roadmap SKILL.md has no **Committing project files**"
    return text[start:text.index("\n## init", start)]


def store_part(text):
    """From the first mention of a store-backed project on."""
    m = re.search(r"(?i)store-backed", text)
    return text[m.start():] if m else ""


BRANCH_TEST_STORE = r'test "\$\(git -C "<store toplevel>" branch --show-current\)" = <branch>'
BRANCH_TEST_CD = r'cd "<store toplevel>" && test "\$\(git branch --show-current\)" = <branch> &&'


BRANCH = ROOT / "skills" / "specwright-branch" / "SKILL.md"


def branch_store_section():
    """specwright-branch's "Store-backed changes" section."""
    s = section(read(BRANCH), r"Store-backed changes")
    assert s, "specwright-branch SKILL.md has no ## Store-backed changes"
    return s


def mode_block(text, n):
    """Numbered item `n` of a list in `text`, up to the next numbered item or blank line."""
    m = re.search(r"^%d\. .*?(?=^\d+\. |\n\n|\Z)" % n, text, re.M | re.S)
    return m.group(0) if m else ""


class PlanningStores(unittest.TestCase):
    def test_roadmap_store_branch_under_gate_lock(self):
        s = store_part(committing_project_files())
        self.assertTrue(s, "Committing project files has no store-backed part")
        lock = re.search(r"specwright-gate\.lock", s)
        take = re.search(r'mkdir "\$L"', s)
        owner = re.search(r'> "\$L/owner"', s)
        clean = re.search(r"(?i)clean\b.{0,40}\bmain|on (its|the store's) main.{0,60}clean", s)
        busy = re.search(r"(?i)\bbusy\b", s)
        branch = re.search(r"git checkout -b <branch>", s)
        release = re.search(r'rm -r "\$L"', s)
        for name, m in (("the lock path", lock), ("mkdir of the lock", take), ("the owner file", owner),
                        ("the clean-on-main check", clean), ("the busy check", busy), ("git checkout -b", branch),
                        ("the release", release)):
            self.assertTrue(m, f"store-backed Committing project files lacks {name}")
        self.assertLess(take.start(), clean.start(), "the store is checked before the lock is taken")
        self.assertLess(clean.start(), branch.start(), "the branch is created before the store checks")
        self.assertLess(branch.start(), release.start(), "the lock is released before the branch exists")
        held = find_block(s, r"(?i)mkdir.{0,40}fails|lock (exists|is held)", r"(?i)\bstop", r"(?i)owner")
        self.assertTrue(held, "a held lock does not stop and show its owner")
        self.assertRegex(held, r"(?i)only the lock (you|it) took|never remove.{0,60}(another|other)|not yours",
                         "the release is not limited to the lock this run took")
        self.assertNotRegex(s, r"specwright-branch`?\s+(store\S*\s+)?steps?\s+\d", "the gate cites specwright-branch step numbers")

    def test_roadmap_store_checks_code_repo_before_any_branch(self):
        s = store_part(committing_project_files())
        check = mode_block(s, 2)
        self.assertRegex(check, r"(?i)code repo", "step 2 does not check the code repo")
        self.assertRegex(check, r"(?s)(?i)code repo.{0,200}(clean|on its main).{0,200}<branch>.{0,40}exist",
                         "step 2 does not check that the code repo is clean, on main and without <branch>")

    def assert_one_rollback_rule(self, step, branch, label):
        """A store gate's branch step rolls back after any `git checkout -b` error, by what exists (D3)."""
        self.assertRegex(step, r"(?s)(?i)\bany\b.{0,20}`git checkout -b[^`]*`.{0,20}errors",
                         f"{label}: the rollback does not cover any `git checkout -b` error")
        self.assertRegex(step, r"(?s)(?i)each repo where.{0,60}ran `git checkout -b`.{0,40}`" + re.escape(branch) + r"` exists",
                         f"{label}: the rollback is not scoped to each repo the gate branched where the branch exists")
        self.assertRegex(step, r"`git checkout <main>`", f"{label}: the rollback does not switch back to main")
        self.assertRegex(step, r"`git branch -d " + re.escape(branch) + r"`",
                         f"{label}: the rollback does not delete the branch with `git branch -d`")
        self.assertRegex(step, r"(?s)(?i)\brelease.{0,40}lock.{0,80}\bstop.{0,60}(original )?error",
                         f"{label}: the rollback does not release the lock, then stop showing the error")
        self.assertNotRegex(step, r"(?i)nothing was branched", f"{label}: an error still assumes nothing was branched")

    def test_roadmap_store_branch_error_rolls_back_every_branched_repo(self):
        step = mode_block(store_part(committing_project_files()), 3)
        self.assert_one_rollback_rule(step, "<branch>", "roadmap step 3")
        self.assertRegex(step, r"(?i)post-checkout", "roadmap step 3 does not name the hook case")

    def test_branch_store_error_rolls_back_every_branched_repo(self):
        step = mode_block(branch_store_section(), 3)
        self.assert_one_rollback_rule(step, "<prefix>/<change-name>", "specwright-branch store step 3")
        self.assertRegex(step, r"(?i)code repo", "specwright-branch store step 3 does not cover the code repo")
        self.assertNotRegex(step, r"(?i)if the store creation fails",
                            "specwright-branch store step 3 still rolls back only a store-side failure")

    def test_gate_rollback_judges_switch_by_current_branch(self):
        for label, step, branch in (("roadmap step 3", mode_block(store_part(committing_project_files()), 3), "<branch>"),
                                    ("specwright-branch store step 3", mode_block(branch_store_section(), 3),
                                     "<prefix>/<change-name>")):
            with self.subTest(label):
                self.assertRegex(step, r"`git branch --show-current`", f"{label}: the switch is not checked by the current branch")
                self.assertRegex(step, r"(?i)ignore its exit status|never by (its|the) exit status|not by (its|the) exit status",
                                 f"{label}: the switch is judged by its exit status")
                self.assertRegex(step, r"(?s)(?i)still on `" + re.escape(branch) + r"`.{0,80}(keeps it|delete nothing)",
                                 f"{label}: a repo that could not switch back has its branch deleted")
                self.assertRegex(step, r"(?s)(?i)still roll back the other repo",
                                 f"{label}: one stuck repo stops the other repo's rollback")
                self.assertRegex(step, r"(?s)(?i)name.{0,20}that repo.{0,40}`" + re.escape(branch) + r"`.{0,20}(its )?main",
                                 f"{label}: the stop does not name the stuck repo and both branches")

    def test_roadmap_store_commits_check_branch_in_same_call(self):
        s = store_part(committing_project_files())
        m = re.search(BRANCH_TEST_CD + r"\s*git add -- <files> && git commit", s)
        self.assertTrue(m, "a store commit does not run the branch check in the same call as `git add` and `git commit`")

    def test_roadmap_store_writes_check_branch_and_stop_on_mismatch(self):
        s = store_part(committing_project_files())
        block = find_block(s, BRANCH_TEST_STORE)
        self.assertTrue(block, "store write steps do not start with the store branch check")
        self.assertRegex(block, r"(?i)before (each|every)\b.{0,60}\bwrit", "the check does not run before each store write step")
        stop = find_block(s, r"(?i)mismatch|fails|does not match|another branch", r"(?i)\bstop")
        self.assertTrue(stop, "a branch mismatch does not stop")
        self.assertRegex(stop, r"(?i)\bboth branch|expected.{0,60}found|name.{0,30}(expected|both)",
                         "the stop does not name both the expected and the found branch")


PR_SKILL = ROOT / "skills" / "specwright-pr" / "SKILL.md"


def mode_step(mode, n):
    """Numbered step `n` of a roadmap mode section (`init`, `close`), up to the next numbered step."""
    sec = section(read(ROADMAP), mode + r"\b")
    assert sec, f"roadmap SKILL.md has no ## {mode}"
    m = re.search(r"^%d\. .*?(?=^\d+\. |\Z)" % n, sec, re.M | re.S)
    return m.group(0) if m else ""


class ProjectPlanning(unittest.TestCase):
    def test_roadmap_writes_adrs_proposed(self):
        s4 = mode_step("init", 4)
        self.assertRegex(s4, r"Status: proposed", "init step 4 does not write ADRs as `Status: proposed`")
        self.assertNotRegex(s4, r"Status: accepted", "init step 4 writes ADRs already accepted")
        s45 = s4 + mode_step("init", 5)
        self.assertRegex(s45, r"(?i)(proposed|REVISE).{0,160}\bedit\w*\b.{0,40}\bin place|in place.{0,120}proposed",
                         "a proposed ADR is not edited in place when the review asks to change it")

    def test_roadmap_accepts_adrs_only_after_gate(self):
        sec = section(read(ROADMAP), r"init\b")
        gate = re.search(r"Gate:", sec)
        accept = re.search(r"Status: accepted", sec)
        roadmap = re.search(r"^\d+\. \*\*Roadmap\*\*", sec, re.M)
        self.assertTrue(gate and accept and roadmap, "init lacks the gate, the acceptance or the roadmap step")
        self.assertLess(gate.start(), accept.start(), "ADRs are accepted before the review gate")
        self.assertLess(accept.start(), roadmap.start(), "the roadmap is written before the ADRs are accepted")
        block = find_block(sec, r"Status: accepted")
        self.assertRegex(block, r"(?i)\bdate\b", "acceptance does not record the date")
        self.assertRegex(block, r"(?i)\bindex\b", "acceptance does not add the in-force index rows")
        self.assertRegex(block, r"(?i)(does not|never) void|not void", "the acceptance edit is not exempt from voiding the verdict")

    def test_roadmap_close_reviews_superseding_adr(self):
        s5 = mode_step("close", 5)
        self.assertRegex(s5, r"Status: proposed", "close does not write the superseding ADR as proposed")
        self.assertRegex(s5, r"Supersedes", "close's new ADR does not name what it supersedes")
        self.assertRegex(s5, r"(?i)review\w*.{0,80}(init step 5|like the baseline|as the baseline|architecture-review\.md)",
                         "close does not review the superseding ADR like the baseline")
        self.assertRegex(s5, r"(?i)accept\w*.{0,60}only after|only after.{0,80}accept",
                         "close accepts the superseding ADR before the gate passes")
        self.assertRegex(s5, r"(?i)never edit an accepted ADR|superseded (ADR|file).{0,40}(unchanged|untouched|not touched)",
                         "close may edit the superseded ADR")

    def test_roadmap_next_offers_close_at_milestone_end(self):
        s3 = mode_step("next", 3)
        end = find_block(s3, r"(?i)every change of the Now milestone is done", r"(?i)milestone end")
        self.assertTrue(end, "next step 3 has no milestone end for when every Now change is done")
        self.assertRegex(end, r"(?i)offer\w* \*\*close\*\*", "the milestone end does not offer close")
        for what in ("change", "branch", "file"):
            self.assertRegex(end, r"(?i)\b(start|create|edit)\w* no %s\b|no %s (is )?(started|created|edited)" % (what, what),
                             f"the milestone end does not rule out a new {what}")

    def test_roadmap_next_starts_only_now_changes(self):
        s3 = mode_step("next", 3)
        self.assertRegex(s3, r"(?i)starts only changes of the Now milestone", "next may start a change outside Now")
        self.assertRegex(s3, r"(?s)(?i)Next.{0,120}(agreed split|lists).{0,120}\*\*close\*\* promotes",
                         "next does not leave an already split Next to close")

    def test_roadmap_status_names_milestone_end(self):
        sec = section(read(ROADMAP), r"status\b")
        self.assertRegex(sec, r"`milestone end: run close`", "status does not name the milestone end as what next would do")
        self.assertRegex(sec, r"(?s)`milestone end: run close`.{0,160}unless an exit criterion was shown failing by \*\*close\*\* or reported failing by the user",
                         "status names the milestone end even after close found a criterion failing")
        self.assertRegex(sec, r"(?i)what it waits for when no change is ready to start",
                         "status does not name what next waits for when no change is ready")

    def test_roadmap_next_reports_what_it_waits_for(self):
        s3 = mode_step("next", 3)
        self.assertRegex(s3, r"(?s)When no planned change is ready to start.{0,200}report what it waits for.{0,80}start nothing",
                         "next does not say what to report when every planned change waits on a prerequisite")

    def test_roadmap_milestone_end_names_both_gap_triggers(self):
        end = find_block(mode_step("next", 3), r"(?i)milestone end")
        self.assertRegex(end, r"unless an exit criterion was shown failing by \*\*close\*\* or reported failing by the user",
                         "the milestone end does not name who shows a criterion failing")

    def test_roadmap_milestone_end_needs_every_change_done(self):
        end = find_block(mode_step("next", 3), r"(?i)milestone end")
        self.assertTrue(end, "next step 3 has no milestone end")
        self.assertRegex(end, r"(?s)(?i)planning merged, code pending.{0,80}not done",
                         "a planning-merged, code-pending change may count toward a milestone end")

    def test_finish_offers_close_after_last_change(self):
        offer = find_block(read(FINISH), r"project\.roadmap", r"(?i)\boffer")
        self.assertTrue(offer, "finish has no roadmap offer")
        self.assertRegex(offer, r"(?s)(?i)\*\*close\*\*.{0,40}when every change of the Now milestone is (then )?done",
                         "finish does not offer close when the milestone's changes are all done")
        self.assertRegex(offer, r"(?i)otherwise \*\*next\*\*", "finish does not offer next otherwise")
        self.assertRegex(offer, r"(?i)never (offer )?both", "finish may offer next and close together")
        self.assertNotRegex(offer, r"\*\*next\*\* \(or \*\*close\*\*", "finish still offers next or close as alternatives")

    def test_roadmap_init_records_agreed_next_split(self):
        s6 = mode_step("init", 6)
        self.assertRegex(s6, r"(?i)only the current milestone is split", "init splits more than the current milestone")
        self.assertRegex(s6, r"(?s)(?i)explicitly agree\w*.{0,80}split.{0,40}Next.{0,200}`\*\*Split agreed:\*\* <YYYY-MM-DD>`",
                         "init does not record an explicitly agreed Next split with a `Split agreed:` line")
        self.assertRegex(s6, r"(?i)never add the line", "init may mark a split the author did not agree")
        tpl = read(ROOT / "skills" / "specwright-roadmap" / "references" / "roadmap.md")
        nxt = section(tpl, r"Next:")
        self.assertRegex(nxt or "", r"\*\*Split agreed:\*\* <YYYY-MM-DD>", "the roadmap template does not document the line")

    def test_roadmap_close_records_agreed_split_for_new_next(self):
        s5 = mode_step("close", 5)
        self.assertRegex(s5, r"(?s)(?i)new Next.{0,200}explicitly agree\w*.{0,200}`\*\*Split agreed:\*\* <today>`",
                         "close does not record a split agreed for the new Next")

    def test_roadmap_close_keeps_agreed_split(self):
        s5 = mode_step("close", 5)
        marked = find_block(s5, r"Split agreed:", r"(?i)\bkeep")
        self.assertTrue(marked, "close does not keep a marked Next split")
        self.assertRegex(marked, r"(?i)names.{0,30}order|order.{0,30}names", "close may rename or reorder an agreed split")
        self.assertRegex(marked, r"(?i)drop\w* the line", "close does not drop the line on promotion")
        self.assertRegex(s5, r"(?s)(?i)no changes.{0,60}split it into changes", "a Next without changes is no longer split")
        self.assertNotRegex(s5, r"(?i)promote Next to Now and split it into changes",
                            "close still re-splits every Next unconditionally")

    def test_roadmap_close_proposes_split_amendments(self):
        s5 = mode_step("close", 5)
        self.assertRegex(s5, r"(?s)(?i)amendment.{0,160}propose it to the user.{0,80}only if they agree",
                         "close may amend an agreed split without the user")
        self.assertRegex(s5, r"(?i)never re-plan an agreed split silently", "close may re-plan an agreed split silently")

    def test_roadmap_close_asks_about_unmarked_split(self):
        s5 = mode_step("close", 5)
        unmarked = find_block(s5, r"(?i)without that line")
        self.assertTrue(unmarked, "close has no rule for a Next that lists changes without the line")
        self.assertRegex(unmarked, r"(?i)ask the user whether", "close does not ask about an unmarked split")
        self.assertRegex(unmarked, r"(?s)(?i)yes.{0,40}keep.{0,80}no.{0,40}split", "the yes and no answers are not both covered")

    def test_roadmap_gap_change_needs_a_shown_failure(self):
        s3 = mode_step("next", 3)
        self.assertRegex(s3, r"(?s)(?i)shown failing.{0,40}by \*\*close\*\*.{0,40}reported failing by the user",
                         "the gap path is not limited to a criterion close or the user showed failing")
        self.assertRegex(s3, r"(?i)never propose a gap-closing change for criteria nobody has shown failing",
                         "next may invent a gap-closing change at an unwalked milestone end")
        self.assertNotRegex(s3, r"(?i)if none is left but exit criteria still fail", "the old gap trigger is still there")

    def test_roadmap_review_escalates_after_two_consecutive_revise(self):
        s5 = mode_step("init", 5)
        self.assertNotRegex(s5, r"(?i)at most two rounds", "init step 5 still caps the review at two rounds")
        self.assertRegex(s5, r"(?i)\b(2|two) consecutive\b.{0,20}REVISE", "init step 5 does not escalate after two consecutive REVISE")
        self.assertRegex(s5, r"(?i)escalat|ask the user", "init step 5 does not escalate to the user")
        self.assertRegex(s5, r"USER_OVERRIDE", "init step 5 does not record the user's decision as USER_OVERRIDE")
        self.assertRegex(s5, r"(?i)\bvoids?\b|new round", "a later edit does not void a passing verdict")

    def test_baseline_edit_after_pass_reruns_review(self):
        fb = section(read(PR_SKILL), r"feedback\b")
        block = find_block(fb, r"docs/project-baseline", r"docs/close-")
        self.assertTrue(block, "PR feedback has no rule for the baseline and close branches")
        self.assertRegex(block, r"(?i)strategy.{0,40}architecture.{0,40}ADR", "the rule does not name strategy, architecture and ADRs")
        self.assertRegex(block, r"(?i)(re-?run|run again).{0,60}baseline review|baseline review.{0,60}(again|re-?run)",
                         "the rule does not re-run the baseline review")
        self.assertRegex(block, r"(?i)before.{0,60}(reply|report|done)", "the review is not re-run before the fix is reported done")


def prerequisites():
    """The README's **Prerequisites:** paragraph."""
    return find_block(read(README), r"\*\*Prerequisites:\*\*") or ""


class PrScriptRuntime(unittest.TestCase):
    def test_install_checks_core_and_pr_prerequisites(self):
        pre = prerequisites()
        self.assertRegex(pre, r"(?i)\bbash\b.{0,80}POSIX", "the prerequisites do not list bash with a POSIX userland")
        self.assertRegex(pre, r"`git`", "the prerequisites do not list git")
        self.assertRegex(pre, r"(?i)\bcore\b", "the prerequisites do not mark the core requirements")
        self.assertRegex(pre, r"(?i)gh`? 2\.40.{0,120}Python 3\.8|Python 3\.8.{0,120}gh`? 2\.40",
                         "the prerequisites do not list gh 2.40+ and Python 3.8+ together for the PR skills")
        s1 = step(read(README), "Step 1")
        self.assertTrue(s1, "README has no install Step 1")
        core = find_block(s1, r"git --version", r"command -v awk sed grep")
        self.assertTrue(core, "Step 1 does not check git and the bash userland")
        self.assertRegex(core, r"STOP", "a missing core requirement does not stop the install")
        self.assertRegex(s1, r"(?s)gh --version.{0,80}2\.40", "Step 1 does not check gh 2.40+")
        self.assertRegex(s1, r"(?s)python3.{0,40}python\b", "Step 1 does not probe python3, then python")
        self.assertRegex(s1, r"version_info < \(3, 8\)|3\.8", "Step 1 does not check for Python 3.8+")
        dep = find_block(read(PR_SKILL), r"Scripts live in")
        self.assertRegex(dep or "", r"(?i)\bbash\b.{0,60}\bgit\b.{0,60}gh`? 2\.40.{0,60}Python 3\.8",
                         "specwright-pr does not state bash, git, gh 2.40+ and Python 3.8+")

    def test_install_reports_pr_workflow_not_ready(self):
        s1 = step(read(README), "Step 1")
        pr = find_block(s1 or "", r"gh --version")
        self.assertTrue(pr, "Step 1 has no PR prerequisite check")
        self.assertRegex(pr, r"(?i)(not|never|does not) (block|stop)|without (blocking|stopping)|continue",
                         "a missing PR requirement blocks the install")
        self.assertRegex(pr, r"(?i)record|Step 8", "a missing PR requirement is not carried to the report")
        s8 = step(read(README), "Step 8")
        self.assertRegex(s8 or "", r"PR workflow not ready: <missing>", "Step 8 does not report `PR workflow not ready: <missing>`")


FINISH = ROOT / "skills" / "specwright-finish" / "SKILL.md"


def resume_section():
    s = section(read(FINISH), r"Resume\b")
    assert s, "specwright-finish SKILL.md has no ## Resume section"
    return s


def resume_row(s, facts):
    """The next-step table row whose first cell is `facts`, as its second cell; '' when there is none."""
    m = re.search(r"^\|\s*" + facts + r"\s*\|(.*)\|\s*$", s, re.M)
    return m.group(1) if m else ""


class ChangeFinishResume(unittest.TestCase):
    def test_finish_resume_deletes_a_merged_branch_without_merging(self):
        text, s = read(FINISH), resume_section()
        self.assertLess(text.index("## Resume"), text.index("1. **Branch:**"), "Resume does not sit before the normal steps")
        for fact in ("A", "M", "B"):
            self.assertRegex(s, r"\*\*%s\*\*" % fact, f"Resume does not define fact {fact}")
        self.assertRegex(s, r"git log --first-parent --format=%s <main>", "M is not read from main's first-parent history")
        self.assertRegex(s, r"merge: <change-name>", "M does not name the exact merge subject")
        row = resume_row(s, "M and B")
        self.assertRegex(row, r"git branch -d", "M and B does not delete the branch with -d")
        self.assertRegex(row, r"(?i)no (new )?merge", "M and B may merge again")
        self.assertTrue(resume_row(s, "M, not B"), "no row for a repo that is done (M, not B)")

    def test_resume_checks_out_main_before_deleting(self):
        s = resume_section()
        rows = (("M and B", resume_row(s, "M and B")),
                ("store done; code branch without commits", resume_row(s, r"store done[^|]*code branch without commits[^|]*")))
        for name, row in rows:
            self.assertTrue(row, f"no Resume row for {name}")
            self.assertRegex(row, r"git checkout <main> && git branch -d <branch>",
                             f"the {name} row deletes the branch without checking out <main> first (it may be the checked-out branch)")

    def test_resume_merge_requires_branch_tip_on_main(self):
        s = resume_section()
        m = re.search(r"\*\*M\*\*[^\n]*", s)
        self.assertTrue(m, "Resume does not define fact M")
        fact = m.group(0)
        self.assertIn("git merge-base --is-ancestor <branch> <main>", fact,
                      "M does not require the branch tip to be on main, so an archive-recovery branch made after the merge counts as merged")
        self.assertRegex(fact, r"(?i)\bB\b|exists", "the tip check is not limited to a branch that exists")

    def test_finish_resume_pr_mode_ships_without_a_second_archive_commit(self):
        s = resume_section()
        self.assertRegex(s, r"(?i)never repeat|not repeat", "Resume does not forbid repeating a done step")
        row = resume_row(s, r"`pr`, A on branch[^|]*")
        self.assertRegex(row, r"(?i)\bship\b", "pr mode with A on the branch does not go to ship")
        self.assertRegex(row, r"(?i)idempotent", "the ship row does not say push and PR are idempotent")
        self.assertNotRegex(row, r"(?i)archive commit", "the pr row repeats the archive commit")
        merged = resume_row(s, r"`pr`, [^|]*PR merged[^|]*")
        self.assertRegex(merged, r"After the PR is merged", "a merged PR does not go to the cleanup")
        self.assertRegex(merged, r"(?i)not ship", "a merged PR may be shipped again")

    def test_resume_pr_mode_keeps_an_open_code_pr(self):
        s = resume_section()
        local = resume_row(s, r"store done[^|]*code branch with commits[^|]*")
        self.assertRegex(s, r"(?m)^\|\s*store done[^|]*code branch with commits[^|]*`local`", "the code-merge row is not restricted to local mode")
        self.assertRegex(local, r"(?i)code merge", "the local row no longer merges the code branch")
        open_pr = resume_row(s, r"`pr`, store done[^|]*code branch with commits[^|]*(?:no PR|open PR)[^|]*")
        self.assertTrue(open_pr, "no pr-mode row for a store done, code branch with commits, no PR or an open PR")
        self.assertRegex(open_pr, r"## pr", "the open-PR row does not go to `## pr` ship")
        self.assertRegex(open_pr, r"(?i)\bship\b", "the open-PR row does not ship")
        self.assertRegex(open_pr, r"(?i)merge nothing|no merge|not merge", "the open-PR row may merge the code branch")
        self.assertRegex(open_pr, r"(?i)delete nothing|no delet|not delete", "the open-PR row may delete the code branch")
        closed = resume_row(s, r"`pr`, store done[^|]*code branch with commits[^|]*closed[^|]*")
        self.assertTrue(closed, "no pr-mode row for a code PR closed unmerged")
        self.assertRegex(closed, r"(?i)\breport\b.*\bask\b", "the closed-PR row does not report and ask")
        self.assertRegex(closed, r"(?i)merge nothing|no merge|not merge", "the closed-PR row may merge")
        self.assertRegex(closed, r"(?i)delete nothing|no delet|not delete", "the closed-PR row may delete the branch")

    def test_finish_resume_stops_on_dirty_archive_paths(self):
        s = resume_section()
        block = find_block(s, r"git status --porcelain", r"<P>/changes/<change-name>/", r"archive directory", r"\bstop\b")
        self.assertTrue(block, "Resume does not stop on uncommitted changes under the change or archive directory")
        self.assertRegex(block, r"(?i)\blist", "the stop does not list the files")
        self.assertRegex(block, r"(?i)\bask\b", "the stop does not ask the user")
        self.assertNotRegex(s, r"(?i)planning-only marker.{0,80}(write|add)s? ", "Resume writes the planning-only marker")

    def test_finish_resume_reports_nothing_to_finish_only_when_all_done(self):
        text, s = read(FINISH), resume_section()
        block = find_block(s, r"Nothing to finish")
        self.assertTrue(block, "Resume never reports Nothing to finish")
        self.assertRegex(block, r"(?i)only when every repo", "Nothing to finish is not limited to every repo being done")
        rest = text.replace(s, "")
        line = next((l for l in rest.splitlines() if "Nothing to finish" in l), "")
        self.assertRegex(line, r"(?i)resume|every repo", "step 1 still reports Nothing to finish without checking every repo")
        self.assertTrue(resume_row(s, r"store done[^|]*code branch with commits[^|]*"), "no row for a store done and the code merge pending")

    def test_resume_runs_the_planning_only_test_before_the_archive_commit(self):
        text, s = read(FINISH), resume_section()
        self.assertRegex(s, r"(?i)top to bottom", "Resume does not say the rows are checked top to bottom")
        self.assertRegex(s, r"(?i)first match wins", "Resume does not say the first matching row wins")
        row = resume_row(s, r"archive paths uncommitted, no A")
        self.assertTrue(row, "no Resume row for archive paths uncommitted and no A")
        self.assertRegex(row, r"steps 1-3 in order", "the no-A row does not run steps 1-3 in order")
        self.assertRegex(row, r"(?is)planning-only test.*archive commit", "the no-A row does not run the planning-only test before the archive commit")
        self.assertLess(s.index("archive paths uncommitted, no A"), s.index("| A on branch, not M"), "the no-A row is not the first row")
        self.assertNotIn("step 3, as today", s, "the no-A row still skips the planning-only test")
        self.assertNotRegex(text, r"A resume writes no planning-only marker", "the old no-marker sentence contradicts the no-A row")
        self.assertRegex(s, r"(?i)once A exists, a resume never writes the marker", "a resume that finds A may write the marker")

    def test_resume_planning_only_finished_is_done(self):
        s = resume_section()
        done = resume_row(s, r"code repo with no A, M or B[^|]*`code_changes: none`[^|]*")
        self.assertTrue(done, "no Resume row for a code repo with no A, M or B beside a finished store whose archive is marked planning-only")
        self.assertRegex(done, r"(?i)\bdone\b", "the planning-only row does not finish the code repo")
        ask = resume_row(s, r"code repo with no A, M or B[^|]*no such marker[^|]*")
        self.assertTrue(ask, "no Resume row for a code repo with no A, M or B and no planning-only marker")
        self.assertRegex(ask, r"(?i)\breport\b.*\bask\b", "without the marker the row does not report and ask")
        self.assertLess(s.index("`code_changes: none`"), s.index("no such marker"), "the marker row is not checked before the ask row")
        self.assertIn("git show --name-only --format= <A>", s, "the marker path is not read from the store's A")
        self.assertRegex(s, r"git show <main>:<", "the marker is not read from <main>")
        self.assertIn(r"^code_changes:\s*none\s*$", s, "the marker test is not the one find_marker uses")

    def test_resume_store_only_recovery_leaves_the_code_repo(self):
        text, s = read(FINISH), resume_section()
        row = resume_row(s, r"code repo, [^|]*`Archive-Scope: store-only`[^|]*")
        self.assertTrue(row, "no Resume row for a store archive marked Archive-Scope: store-only")
        self.assertRegex(row, r"(?i)\breport\b", "the store-only row does not report the code branch's state")
        self.assertRegex(row, r"(?i)touch nothing", "the store-only row may touch the code repo")
        self.assertRegex(row, r"(?i)\bdone\b", "the store-only row does not count as done")
        bullet = find_block(s, r"Archive-Scope: store-only", r"Nothing to finish", r"touches? nothing|no code merge")
        self.assertTrue(bullet, "Resume never says a store-only archive counts as done for Nothing to finish")
        self.assertLess(s.index("`Archive-Scope: store-only`"), s.index("| M and B"), "the store-only row is not above M and B")
        self.assertIn("git log -1 --format=%B <A>", s, "Resume does not read the marker from the newest store A's body")
        steps = text[text.index("1. **Branch:**"):text.index("\n## local\n")]
        step1 = steps[:steps.index("2. **Planning-only test**")]
        step3 = steps[steps.index("3. **Archive commit**"):steps.index("4. **Finish**")]
        self.assertIn("Archive-Scope: store-only", step1, "step 1's store-backed recovery does not mention the marker line")
        self.assertRegex(step3, r"Archive-Scope: store-only", "step 3 never writes the marker line")
        self.assertRegex(step3, r"(?is)store-backed.*chore/archive-<change-name>.*Archive-Scope: store-only|"
                                r"Archive-Scope: store-only.*store-backed.*chore/archive-<change-name>",
                         "step 3 does not tie the marker line to a store-backed change on the recovery branch")

    def test_finish_resume_reports_no_archive_found(self):
        s = resume_section()
        block = find_block(s, r"no archive of", r"(?i)do nothing|no commit")
        self.assertTrue(block, "Resume does not report that no archive of the change was found")
        self.assertRegex(block, r"(?i)none of|no fact|not found", "the no-archive report is not tied to finding no fact")
        self.assertRegex(s, r"\^\[a-z\]\+\\\(<change-name>\\\): archive change\$", "the archive subject regex is missing")
        self.assertRegex(s, r"chore/archive-<change-name>.{0,120}\*/<change-name>", "the branch lookup lacks the recovery and glob fallbacks")

    def fact_a(self):
        m = re.search(r"\*\*A\*\*[^\n]*", resume_section())
        self.assertTrue(m, "Resume does not define fact A")
        return m.group(0)

    def test_finish_resume_finds_archive_directory_on_main(self):
        a = self.fact_a()
        self.assertIn("git ls-tree -d --name-only <main> -- <P>/changes/archive/", a, "fact A does not look for the archive directory on main with ls-tree")
        self.assertRegex(a, r"(?i)last path component", "fact A does not match the ls-tree output on its last path component")
        self.assertRegex(a, r"<archived-name>", "fact A does not match the archived name")
        self.assertIn(r"^[a-z]+\(<change-name>\): archive change$", a, "fact A lost the archive subject match")

    def test_finish_resume_archive_match_is_exact(self):
        a = self.fact_a()
        self.assertIn(r"^\d{4}-\d{2}-\d{2}-<change-name>$", a, "the dated-name match is not anchored on both ends")
        self.assertRegex(a, r"(?i)never a substring", "fact A does not forbid a substring match")
        self.assertRegex(a, r"(?i)dated name itself|as is", "a change name that already has a date is not matched as is")

    def test_finish_resume_merged_pr_without_branch_is_done(self):
        s = resume_section()
        row = resume_row(s, r"`pr`, the branch's PR merged, not B[^|]*")
        self.assertTrue(row, "no Resume row for a merged PR with no branch")
        self.assertRegex(row, r"closed-check", "the row does not run the issues-left-open backstop")
        self.assertIn("discover", row + s, "the merged PR is not found with discover")
        self.assertRegex(s, r"discover[^\n]*--state merged", "the merged PR is not found with discover --state merged")
        self.assertNotRegex(row, r"git branch -[dD]", "the row deletes a branch that is already gone")
        self.assertRegex(row, r"(?i)no branch delet", "the row does not forbid a branch deletion")
        self.assertRegex(row, r"(?i)repo done|\bdone\b", "the row does not count the repo as done")

    def test_finish_resume_merged_pr_with_branch_runs_cleanup(self):
        s = resume_section()
        row = resume_row(s, r"`pr`, the branch's PR merged, B[^|]*")
        self.assertTrue(row, "no Resume row for a merged PR whose branch exists")
        self.assertRegex(row, r"After the PR is merged", "the B row does not keep the cleanup")
        self.assertRegex(row, r"(?i)not ship", "the B row may ship again")
        self.assertLess(s.index("PR merged, B |"), s.index("PR merged, not B |"), "the B row is not checked before the not-B row")

    def test_finish_resume_backstop_exit_3_is_not_done(self):
        s = resume_section()
        row = resume_row(s, r"`pr`, the branch's PR merged, not B[^|]*")
        self.assertRegex(row, r"exits? 3", "the not-B row does not handle closed-check exit 3")
        self.assertRegex(row, r"(?i)not done", "closed-check exit 3 does not leave the repo not done")
        self.assertRegex(row, r"(?i)backstop did not run", "the report does not say the backstop did not run")
        block = find_block(s, r"Nothing to finish", r"exit 3")
        self.assertTrue(block, "the Nothing to finish rule does not count a backstop exit 3 as not done")

    def test_finish_resume_local_bulk_archive_on_main_is_done(self):
        s = resume_section()
        row = resume_row(s, r"`local`, A on main through the archive directory, not M, not B[^|]*")
        self.assertTrue(row, "no Resume row for a local archive that reached main through another change's merge")
        self.assertRegex(row, r"(?i)repo done", "the local bulk-archive row does not finish the repo")
        self.assertLess(s.index("| M, not B"), s.index("`local`, A on main through the archive directory"), "the local row is not after M, not B")

    def merged_bullet(self):
        text = read(FINISH)
        at = text.index("- **After the PR is merged**")
        return text[at:text.index("\n\n", at)]

    def test_finish_cleanup_runs_branch_check_before_deleting(self):
        b = self.merged_bullet()
        check = re.search(r"branch-check", b)
        self.assertTrue(check, "After the PR is merged never runs `branch-check`")
        pull = b.find("pull --ff-only")
        self.assertTrue(0 <= pull < check.start(), "`branch-check` does not run after `pull --ff-only`")
        for m in re.finditer(r"branch -[dD]", b):
            self.assertLess(check.start(), m.start(), "After the PR is merged deletes the branch before `branch-check`")
        self.assertRegex(b, r"branch -D", "the cleanup never deletes with -D on `delete: true`")
        self.assertRegex(b, r"delete: true", "the cleanup does not delete only on `delete: true`")
        self.assertRegex(b, r"`lacking`", "the cleanup does not report the `lacking` commits")
        self.assertRegex(b, r"`head_unknown`", "the cleanup does not report `head_unknown`")
        self.assertRegex(b, r"--head <head_sha>", "`branch-check` is not given `--head`")
        self.assertRegex(b, r"discover[^`]*--state merged", "`--head` does not come from `discover --state merged`")
        self.assertRegex(b, r"`head_sha`", "`--head` is not `discover`'s `head_sha`")
        self.assertNotRegex(b, r"-D` only when the PR is MERGED and its `headRefOid` equals the local branch tip",
                            "the cleanup still deletes with -D when headRefOid equals the local tip")
        self.assertNotIn("force_delete_allowed", read(FINISH), "finish still mentions `force_delete_allowed`")
        row = resume_row(resume_section(), "M and B")
        self.assertRegex(row, r"(?is)`pr`.*After the PR is merged|After the PR is merged.*`pr`",
                         "the M and B row does not send pr mode to After the PR is merged, so `branch-check` decides the deletion")

    def test_finish_resume_archive_directory_is_planning_repo_only(self):
        s = resume_section()
        a = self.fact_a()
        self.assertRegex(a, r"(?i)planning repo only", "the archive-directory source is not limited to the planning repo")
        self.assertRegex(a, r"(?i)never[^.;]*code repo", "fact A does not say the directory never gives the code repo an A")
        self.assertTrue(resume_row(s, r"code repo with no A, M or B; store done; no such marker"), "the code repo's existing no-A rows are gone")


if __name__ == "__main__":
    unittest.main()
