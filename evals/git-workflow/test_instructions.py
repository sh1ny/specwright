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

    def test_design_reviews_use_review_routes(self):
        review = schema_block("- id: review")
        self.assertNotRegex(review, r"(?i)author on\s+Claude\s*→\s*`codex`", "the review step still has the hardcoded pairing")
        self.assertNotRegex(review, r"(?i)read its current flags", "the agent still builds the reviewer command line")
        for name, block in (("design review", review), ("roadmap init step 5", mode_step("init", 5))):
            self.assertRegex(block, r"specwright-review", f"{name}: does not use the specwright-review routes")
            self.assertRegex(block, r"(?s)review-run\.sh\s+select|review-run\.sh select", f"{name}: no route selection")
            self.assertRegex(block, r"(?s)run\s+--kind\s+design", f"{name}: a CLI route is not run through review-run.sh")
            self.assertRegex(block, r"(?s)record\s+--kind\s+design", f"{name}: a subagent review is not validated")
        self.assertRegex(review, r"(?i)never try the next route", "an invalid review falls through to another route")
        self.assertRegex(review, r"review\.cross_model: false", "cross_model false no longer means the agent only")

    def test_reviewer_agents_have_preship_mode(self):
        for p in [*CLAUDE_AGENTS[1:], ROOT / "agents" / "omp" / "specwright-reviewer.md"]:
            text = read(p)
            self.assertRegex(text, r"(?m)^description:.*pre-ship", f"{p.name}: description has no pre-ship mode")
            self.assertRegex(text, r"(?i)for a pre-ship review", f"{p.name}: no pre-ship mode")
            self.assertRegex(text, r"(?is)pre-ship review.{0,900}findings file.{0,400}schema", f"{p.name}: no findings file output")

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


class BranchGateStoreVersion(unittest.TestCase):
    """The change gate compares the project's install version with the store's, and meets the update lock (D5, D6)."""

    def step2(self):
        return mode_block(branch_store_section(), 2)

    def test_gate_compares_major_minor(self):
        s = self.step2()
        self.assertRegex(s, r"openspec/\.specwright/VERSION", "store step 2 does not read the project's VERSION")
        self.assertRegex(s, r"openspec/\.specwright/STORE", "store step 2 does not read the store's STORE record")
        self.assertRegex(s, r"(?is)\bone (shell )?call\b.{0,200}\bVERSION|\bVERSION\b.{0,300}\bone (shell )?call\b",
                         "VERSION and STORE are not read in one shell call")
        self.assertRegex(s, r"major\.minor", "store step 2 does not compare major.minor")
        self.assertRegex(s, r"(?is)mismatch.{0,200}(both versions|name\w* both).{0,80}owner|(both versions).{0,80}owner",
                         "a mismatch does not name both versions and the owner")
        self.assertRegex(s, r"(?is)no `?STORE`?.{0,80}pass|`?STORE`? (is )?(absent|missing).{0,80}pass|pass\w*.{0,60}no `?STORE`?",
                         "a store with no STORE record does not pass")
        self.assertRegex(s, r"(?is)unreadable `?STORE`?|`?STORE`? (is )?unreadable", "an unreadable STORE does not stop")
        self.assertRegex(s, r"(?is)release.{0,40}lock", "a version stop does not release the lock")
        self.assertRegex(s, r"(?is)update this project to", "a project behind the store is not told to update itself")

    def test_gate_says_owner_updates_store_first(self):
        self.assertRegex(self.step2(), r"(?is)store.{0,30}behind.{0,300}owner.{0,60}updates? the store first",
                         "a store behind the project does not say its owner updates the store first")

    def test_gate_stops_without_version_file(self):
        s = self.step2()
        self.assertRegex(s, r"(?is)missing `?VERSION`?|no `?VERSION`?", "a missing VERSION does not stop")
        self.assertRegex(s, r"(?is)(missing|no) `?VERSION`?.{0,300}run the (install|update) in this project",
                         "a missing VERSION does not say to run the install or update in this project")

    def test_gate_names_update_lock_without_removal(self):
        for label, step in (("specwright-branch store step 1", mode_block(branch_store_section(), 1)),
                            ("specwright-roadmap store step 1", mode_block(store_part(committing_project_files()), 1))):
            with self.subTest(label):
                self.assertRegex(step, r"(?is)`change:` starts with `specwright-update`|change.{0,40}starts with `specwright-update`",
                                 f"{label}: the update lock is not recognised by its change")
                self.assertRegex(step, r"(?is)specwright-update.{0,400}rerun the update from",
                                 f"{label}: the update lock does not say to rerun the update")
                self.assertRegex(step, r"(?is)rerun the update from.{0,200}(no|not|never)[^.]{0,30}(offer|removal|remov)",
                                 f"{label}: the update lock still offers removal")


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

    def test_roadmap_next_skips_parked_change(self):
        s2 = re.sub(r"\s+", " ", mode_step("next", 2))
        self.assertRegex(s2, r"(?i)review\.md", "next step 2 does not read the active changes' review.md")
        self.assertIn("`VERDICT: DEFERRED`", s2, "next step 2 does not name VERDICT: DEFERRED")
        self.assertRegex(s2, r"(?i)DEFERRED.{0,200}parked", "next step 2 does not call a DEFERRED change parked")
        self.assertRegex(s2, r"(?i)never offer\w* (to resume )?(it|the parked)", "next step 2 may offer to resume a parked change")
        self.assertRegex(s2, r"(?i)continu\w* (to )?step 3 as if (it were|the change were) not active", "next does not go on to step 3 as if the parked change were not active")

    def test_roadmap_status_lists_parked_with_targets(self):
        sec = re.sub(r"\s+", " ", section(read(ROADMAP), r"status\b"))
        self.assertRegex(sec, r"(?i)`parked`", "status has no `parked` state")
        self.assertRegex(sec, r"(?i)`parked`.{0,120}`Deferred to:`", "status does not list the Deferred to: targets of a parked change")
        self.assertRegex(sec, r"(?i)never as active|not as active", "status may list a parked change as active")

    def test_roadmap_next_resumes_non_parked_change(self):
        s2 = re.sub(r"\s+", " ", mode_step("next", 2))
        self.assertRegex(s2, r"(?i)every other active change.{0,120}(offer|resume)", "next does not offer every other active change for resume")
        self.assertRegex(s2, r"(?i)(with no|without a|no) `review\.md`.{0,80}(offer|resume)|including one with no `review\.md`", "an active change with no review.md is not offered for resume")

    def test_roadmap_next_and_status_on_parking_branch(self):
        s2 = re.sub(r"\s+", " ", mode_step("next", 2))
        self.assertRegex(s2, r"(?i)parking change.{0,40}on its own branch", "next does not say the parking change is on its own branch")
        self.assertRegex(s2, r"(?i)starts? from main once it has merged", "next does not say it starts from main once the parking change has merged")
        self.assertRegex(s2, r"(?i)start\w* nothing.{0,60}no branch.{0,20}no change", "next may create a branch or change on the parking branch")
        sec = re.sub(r"\s+", " ", section(read(ROADMAP), r"status\b"))
        self.assertRegex(sec, r"(?i)parking change.{0,40}on its own branch.{0,120}starts? from main once it has merged", "status does not say the same on the parking branch")

    def test_baseline_gate_lists_own_verdicts_without_deferred_or_waived(self):
        s5 = re.sub(r"\s+", " ", mode_step("init", 5))
        self.assertNotRegex(s5, r"(?i)same precheck as tasks", "init step 5 still borrows the tasks precheck")
        self.assertIn("`VERDICT: APPROVE`", s5, "the baseline gate does not list VERDICT: APPROVE")
        self.assertRegex(s5, r"(?i)`VERDICT: APPROVE_WITH_CHANGES`.{0,60}`CHANGES_APPLIED: yes`", "the baseline gate does not tie APPROVE_WITH_CHANGES to CHANGES_APPLIED: yes")
        self.assertRegex(s5, r"(?i)`VERDICT: USER_OVERRIDE`.{0,40}after escalation", "the baseline gate does not list USER_OVERRIDE after escalation")
        self.assertRegex(s5, r"(?i)DEFERRED, WAIVED and SKIPPED_LIGHT never pass the baseline", "the baseline gate does not refuse DEFERRED, WAIVED and SKIPPED_LIGHT")
        self.assertRegex(s5, r"(?i)never pass the baseline.{0,300}no roadmap.{0,200}Status: proposed.{0,200}needs a review", "a refused verdict does not leave the ADRs proposed, write no roadmap and tell the user")


def prerequisites():
    """The README's **Prerequisites:** paragraph."""
    return find_block(read(README), r"\*\*Prerequisites:\*\*") or ""


def install_bullet(s1, *patterns):
    """The first top-level `- ` bullet of an install step matching every pattern, or None."""
    for b in re.split(r"\n(?=- )", s1 or ""):
        if all(re.search(p, b, re.I | re.S) for p in patterns):
            return b
    return None


class PrScriptRuntime(unittest.TestCase):
    def test_install_checks_core_and_pr_prerequisites(self):
        pre = prerequisites()
        self.assertRegex(pre, r"(?i)\bbash\b.{0,80}POSIX", "the prerequisites do not list bash with a POSIX userland")
        self.assertRegex(pre, r"`git`", "the prerequisites do not list git")
        self.assertRegex(pre, r"(?i)\bcore\b", "the prerequisites do not mark the core requirements")
        core_part, _, pr_part = pre.partition("PR skills")
        self.assertRegex(core_part, r"Python 3\.8", "the prerequisites do not list Python 3.8+ as a core requirement")
        self.assertRegex(pr_part, r"gh`? 2\.40", "the prerequisites do not list gh 2.40+ for the PR skills")
        self.assertNotRegex(pr_part, r"Python", "Python is still listed as a PR-only requirement")
        s1 = step(read(README), "Step 1")
        self.assertTrue(s1, "README has no install Step 1")
        core = install_bullet(s1, r"git --version", r"command -v awk sed grep")
        self.assertTrue(core, "Step 1 does not check git and the bash userland")
        self.assertRegex(core, r"STOP", "a missing core requirement does not stop the install")
        py = install_bullet(s1, r"version_info < \(3, 8\)")
        self.assertTrue(py, "Step 1 does not check for Python 3.8+")
        self.assertRegex(py, r"(?s)python3.{0,40}python\b", "Step 1 does not probe python3, then python")
        self.assertRegex(py, r"STOP", "a missing Python 3.8+ does not stop the install")
        self.assertRegex(s1, r"(?s)gh --version.{0,80}2\.40", "Step 1 does not check gh 2.40+")
        dep = find_block(read(PR_SKILL), r"Scripts live in")
        self.assertRegex(dep or "", r"(?i)\bbash\b.{0,60}\bgit\b.{0,60}gh`? 2\.40.{0,60}Python 3\.8",
                         "specwright-pr does not state bash, git, gh 2.40+ and Python 3.8+")

    def test_install_reports_pr_workflow_not_ready(self):
        s1 = step(read(README), "Step 1")
        pr = install_bullet(s1, r"gh --version")
        self.assertTrue(pr, "Step 1 has no PR prerequisite check")
        self.assertNotRegex(pr, r"(?i)python", "the PR prerequisite check still covers Python")
        self.assertRegex(pr, r"(?i)(not|never|does not) (block|stop)|without (blocking|stopping)|continue",
                         "a missing PR requirement blocks the install")
        self.assertRegex(pr, r"(?i)record|Step 8", "a missing PR requirement is not carried to the report")
        s8 = step(read(README), "Step 8")
        self.assertRegex(s8 or "", r"PR workflow not ready: <missing>", "Step 8 does not report `PR workflow not ready: <missing>`")
        self.assertRegex(s8 or "", r"PR workflow not ready: gh 2\.40\+", "Step 8's example still names Python")


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
        self.assertRegex(s, r"`newest`[^\n]*discover|discover[^\n]*`newest`", "the branch's PR is not the newest one discover lists")
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

    def test_finish_resume_merged_pr_rows_come_before_m_rows(self):
        """First match wins: a pr-mode merged PR must reach its rows even when main has `merge: <change-name>` (a merged
        PR that kept that subject, or cleanup interrupted after the branch was deleted), or the backstop is skipped."""
        s = resume_section()
        for m_row in ("| M and B |", "| M, not B |"):
            for pr_row in ("PR merged, B |", "PR merged, not B |"):
                self.assertLess(s.index(pr_row), s.index(m_row), f"{pr_row!r} is checked after {m_row!r}")

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

    def test_finish_resume_pulls_main_before_no_archive(self):
        """A cleanup can delete the branch before main is pulled: locally A, M and B are all false although the PR merged.
        pr mode looks for the merged PR and pulls main before it reports that no archive was found."""
        text = read(FINISH)
        at = text.index("None of A, M, B in any repo")
        rule = text[at:text.index("\n", at)]
        no_archive = rule.index("no archive of `<change-name>` was found")
        before = rule[:no_archive]
        self.assertRegex(before, r"`pr` mode", "the no-archive rule has no pr-mode check")
        self.assertRegex(before, r"discover", "the branch's PR is not looked up before reporting no archive")
        self.assertRegex(before, r"newest PR is merged", "main is pulled for an older merged PR, not the newest one")
        self.assertRegex(before, r"pull --ff-only", "main is not pulled before reporting no archive")
        self.assertRegex(before, r"read the three facts again", "the facts are not read again after the pull")

    def test_finish_resume_checks_dirty_tree_before_pulling_main(self):
        """The pr-mode pull must not check out main over uncommitted changes and skip the stop-and-ask guard."""
        text = read(FINISH)
        at = text.index("None of A, M, B in any repo")
        rule = text[at:text.index("\n", at)]
        self.assertIn("git status --porcelain", rule, "the no-archive rule has no dirty-tree check")
        self.assertLess(rule.index("git status --porcelain"), rule.index("git checkout <main>"), "main is checked out before the dirty-tree check")
        self.assertRegex(rule[:rule.index("git checkout <main>")], r"(?i)stop, list the files and ask", "a dirty tree does not stop and ask")

    def test_finish_resume_merged_pr_is_the_newest_of_any_state(self):
        """A reused branch name can leave an older generation's merged PR behind a newer open one: `--state merged` would
        hide the newer PR and finish the new change on the old archive. The branch's PR is the newest of any state."""
        s = resume_section()
        at = s.index("The branch's PR is")
        rule = s[at:s.index("\n", at)]
        self.assertRegex(rule, r"discover[^`]*--base <main>`", "the branch's PR is not found with discover")
        self.assertNotRegex(rule, r"discover[^`]*--state merged", "discover filters out a newer open or closed PR")
        self.assertRegex(rule, r"`newest`", "the branch's PR is not discover's newest")
        self.assertRegex(rule, r"(?i)reused", "a newer unmerged PR beside an older merged one is not treated as a reused name")
        self.assertRegex(rule, r"(?i)\bask", "a reused branch name does not ask the user")
        self.assertRegex(rule, r"(?i)never `closed-check` the older", "the older merged PR still gets the backstop")

    def test_finish_resume_reused_branch_rule_takes_precedence(self):
        """First match wins in the table, so the reused-name stop must say it comes first, except that a branch with an
        open newest PR is the current change in progress and still ships."""
        s = resume_section()
        at = s.index("The branch's PR is")
        rule = s[at:s.index("\n", at)]
        self.assertRegex(rule, r"checked before[^.]*any table row", "the reused-name rule does not take precedence over the table")
        self.assertRegex(rule, r"no-archive report", "a reused name can still reach the no-archive report")
        self.assertRegex(rule, r"B holds and the newest PR is open", "an in-progress branch with an open newest PR no longer ships")

    def test_finish_resume_merged_pr_without_branch_refreshes_main(self):
        """A stale local main has no archive although the merged PR brought it: the not-B row refreshes main (guarded) and
        reads A again in the planning repo only."""
        s = resume_section()
        row = resume_row(s, r"`pr`, the branch's PR merged, not B[^|]*")
        self.assertIn("git checkout <main>", row, "the not-B row does not check out main")
        self.assertIn("pull --ff-only", row, "the not-B row does not pull main")
        self.assertRegex(row, r"\[as\] git pull --ff-only", "the refresh pull is not fenced")
        self.assertRegex(row, r"(?i)already pulled", "the row pulls a repo twice in one run")
        self.assertRegex(row, r"(?i)read A again", "A is not read again on the refreshed main")
        self.assertRegex(row, r"(?i)planning repo", "the A re-read is not limited to the planning repo")
        self.assertRegex(row, r"A present[^;.]*closed-check", "A present does not lead to closed-check")

    def test_finish_resume_merged_pr_without_archive_after_refresh_not_done(self):
        row = resume_row(resume_section(), r"`pr`, the branch's PR merged, not B[^|]*")
        self.assertRegex(row, r"(?i)A absent", "the row has no A-absent outcome")
        self.assertRegex(row, r"(?i)did not bring the archive to `?<?main", "the report does not say the PR missed the archive")
        self.assertRegex(row, r"(?i)no backstop", "the A-absent outcome still runs the backstop")
        self.assertRegex(row, r"(?i)repo not done", "the A-absent outcome counts the repo as done")

    def test_finish_resume_store_code_repo_needs_no_archive(self):
        row = resume_row(resume_section(), r"`pr`, the branch's PR merged, not B[^|]*")
        self.assertRegex(row, r"(?i)store-backed code repo never has A", "the row does not exempt the store-backed code repo from A")
        self.assertRegex(row, r"(?i)code repo[^;]*closed-check`?, repo done", "the store-backed code repo is not done after closed-check")

    def test_finish_resume_merged_row_checks_dirty_tree_before_refresh(self):
        row = resume_row(resume_section(), r"`pr`, the branch's PR merged, not B[^|]*")
        self.assertIn("git status --porcelain", row, "the not-B row has no dirty-tree check")
        self.assertLess(row.index("git status --porcelain"), row.index("git checkout <main>"), "main is checked out before the dirty-tree check")
        self.assertRegex(row[:row.index("git checkout <main>")], r"(?i)stop and ask", "a dirty tree does not stop and ask")

    def test_finish_resume_reused_check_precedes_no_archive_report(self):
        s = resume_section()
        at = s.index("The branch's PR is")
        self.assertLess(at, s.index("None of A, M, B in any repo"), "the reused-name rule is not before the no-archive rule")
        self.assertLess(at, s.index("\n| Facts |"), "the reused-name rule is not before the table")
        rule = s[at:s.index("\n", at)]
        self.assertRegex(rule, r"(?i)once per repo", "discover is not run once per repo")
        self.assertRegex(rule, r"(?i)same result", "the reused-name check does not read the same discover result")
        self.assertRegex(rule, r"(?i)before the no-archive report, any pull, or any table row", "the reused-name stop does not precede the no-archive report, a pull and the table")
        self.assertRegex(rule, r"(?i)newer closed-unmerged PR", "a newer closed PR is not a reused name")
        self.assertRegex(rule, r"(?i)newer open PR with B false", "a newer open PR with no branch is not a reused name")

    def test_finish_resume_closed_pr_row_defers_to_reused_rule(self):
        m = re.search(r"^\|\s*(`pr`, store done; code branch with commits, the newest PR closed unmerged[^|]*)\|", resume_section(), re.M)
        self.assertTrue(m, "no Resume row for a code branch whose newest PR was closed")
        self.assertRegex(m.group(1), r"no older merged PR", "the closed-PR row does not exclude a reused name")
        self.assertRegex(m.group(1), r"reused-name rule above", "the closed-PR row does not defer to the reused-name rule")

    def test_finish_resume_closed_pr_row_reports_closed_pr(self):
        row = resume_row(resume_section(), r"`pr`, store done; code branch with commits, the newest PR closed unmerged[^|]*")
        self.assertTrue(row, "no Resume row for a code branch whose newest PR was closed")
        self.assertRegex(row, r"report the closed PR and ask", "the closed-PR row does not report the PR")
        self.assertRegex(row, r"Merge nothing, delete nothing", "the closed-PR row may merge or delete")

    def test_finish_resume_local_archive_directory_alone_asks(self):
        """A reused change name can match an older generation's archive directory, so the directory alone does not finish
        the repo: the row shows the directory and the commit that added it and asks."""
        row = resume_row(resume_section(), r"`local`, A on main through the archive directory, not M, not B[^|]*")
        self.assertRegex(row, r"(?i)\bask", "the row declares the repo done on the directory alone")
        self.assertRegex(row, r"the commit that added it", "the row does not show the commit that added the directory")
        self.assertRegex(row, r"git log -1[^`]*<main> -- ", "the row does not find that commit with git log on main")
        self.assertRegex(row, r"(?i)reused", "the row does not say why it asks (a reused change name)")
        self.assertRegex(row, r"(?i)\bno\b[^|]*touch nothing", "a no does not leave the repo untouched")

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

    def test_finish_resume_m_and_b_in_pr_mode_needs_no_pr(self):
        """A merged PR matches an earlier row, so pr mode reaches M and B only after a local merge, with no PR to give
        `--head`. M already puts the tip on main, so `branch-check` runs without `--head` and still decides the deletion."""
        row = resume_row(resume_section(), "M and B")
        self.assertRegex(row, r"`pr` mode", "the M and B row has no pr-mode path")
        self.assertNotRegex(row, r"After the PR is merged", "M and B in pr mode still needs a merged PR's head")
        check = re.search(r"branch-check[^;]*without `--head`", row)
        self.assertTrue(check, "M and B in pr mode does not run `branch-check` without `--head`")
        pull = row.find("pull --ff-only")
        self.assertTrue(0 <= pull < check.start(), "`branch-check` does not run after `pull --ff-only`")
        self.assertRegex(row[check.start():], r"delete: true[^;]*branch -D", "the row does not delete with -D on `delete: true`")
        self.assertRegex(row, r"`lacking`", "the row does not report the `lacking` commits")
        self.assertRegex(row, r"(?i)no `closed-check`", "the row runs the backstop for a PR that does not exist")

    def test_finish_resume_archive_directory_is_planning_repo_only(self):
        s = resume_section()
        a = self.fact_a()
        self.assertRegex(a, r"(?i)planning repo only", "the archive-directory source is not limited to the planning repo")
        self.assertRegex(a, r"(?i)never[^.;]*code repo", "fact A does not say the directory never gives the code repo an A")
        self.assertTrue(resume_row(s, r"code repo with no A, M or B; store done; no such marker"), "the code repo's existing no-A rows are gone")


class FinishAgentMerge(unittest.TestCase):
    """add-agent-merge: with `pr.merge: agent` finish hands the PR to watch and deletes the remote branch at the merged head."""

    def pr_bullets(self):
        pr = section(read(FINISH), r"pr\b")
        self.assertTrue(pr, "specwright-finish has no `## pr` section")
        return pr

    def handback_bullet(self):
        b = find_block(self.pr_bullets(), r"hand back")
        self.assertTrue(b, "the pr path has no hand-back bullet")
        return b

    def test_finish_pr_agent_mode_starts_watch(self):
        b = self.handback_bullet()
        self.assertRegex(b, r"pr\.merge: agent", "the pr path does not branch on `pr.merge: agent`")
        agent = re.search(r"pr\.merge: agent[^.]*\bwatch\b", b, re.S)
        self.assertTrue(agent, "agent mode does not start watch")
        self.assertRegex(b, r"(?i)start\w* .{0,40}\*\*watch\*\*.{0,60}run login|run login.{0,60}\*\*watch\*\*",
                         "watch is not started with the run login")
        ready = b.index("Ready to merge on GitHub")
        self.assertGreater(ready, b.index("pr.merge: agent"), "`Ready to merge on GitHub` is not placed after the agent-mode branch")
        self.assertRegex(b[b.index("pr.merge: agent"):ready], r"(?i)\bnot\b|never|instead|only",
                         "agent mode is not kept apart from `Ready to merge on GitHub`")
        self.assertRegex(b, r"pr\.merge: user", "the user-mode report is not tied to `pr.merge: user`")
        self.assertRegex(b, r"(?i)do(es)? not (print|report)[^.]*Ready to merge on GitHub|no `Ready to merge on GitHub`|without `Ready to merge on GitHub`",
                         "agent mode does not say it prints no `Ready to merge on GitHub`")

    def test_finish_pr_agent_mode_hands_back_to_watch_that_started_it(self):
        b = self.handback_bullet()
        self.assertRegex(b, r"\*\*watch\*\* started this archive", "the hand-back to the watch that started the archive is gone")
        self.assertIn("pr.merge: agent", b, "the hand-back bullet has no agent-mode branch")
        self.assertLess(b.index("started this archive"), b.index("pr.merge: agent"),
                        "the hand-back to a watch that started the archive does not come first")

    def test_finish_pr_agent_mode_ship_failure_no_watch(self):
        pr = self.pr_bullets()
        ship = pr.index("**ship**")
        b = self.handback_bullet()
        self.assertRegex(b, r"(?i)failed \*\*ship\*\*[^.]*starts? no \*\*watch\*\*",
                         "a failed ship does not start no watch")
        self.assertLess(ship, pr.index("pr.merge: agent"), "the ship bullet does not come before the agent-mode watch")

    def test_finish_never_merge_is_scoped_to_user_mode(self):
        pr = self.pr_bullets()
        never = re.search(r"Never merge the PR", pr)
        self.assertTrue(never, "the pr path lost its `Never merge the PR` rule")
        around = pr[max(0, never.start() - 160):never.end() + 80]
        self.assertRegex(around, r"pr\.merge: user", "`Never merge the PR` is not scoped to `pr.merge: user`")
        self.assertRegex(pr, r"(?i)agent.{0,80}\bwatch\b.{0,80}merg|\bwatch\b.{0,80}merges", "finish does not say that in agent mode watch merges")

    def test_finish_resume_delete_remote_agent_mode_only(self):
        b = ChangeFinishResume.merged_bullet(self)
        self.assertRegex(b, r"delete-remote", "After the PR is merged never runs `delete-remote`")
        d = b.index("delete-remote")
        self.assertLess(b.index("pull --ff-only"), d, "`delete-remote` does not run after the pull")
        self.assertLess(b.index("branch-check"), d, "`delete-remote` does not run after `branch-check`")
        tail = b[d - 300:d + 700]
        self.assertRegex(tail, r"pr\.merge: agent", "`delete-remote` is not limited to `pr.merge: agent`")
        self.assertRegex(tail, r"delete_branch", "`delete-remote` ignores `delete_branch`")
        self.assertRegex(b, r"delete-remote[^`]*--head <head_sha>|--head <head_sha>[^`]*delete-remote",
                         "`delete-remote` is not given the merged head")
        self.assertRegex(b[d - 100:], r"\[as\] bash scripts/pr-pair\.sh delete-remote", "`delete-remote` is not run fenced")
        for status in ("deleted", "gone", "moved", "based_on", "kept"):
            self.assertRegex(b[d:], r"`%s`" % status, "`delete-remote` status `%s` is not handled" % status)
        self.assertRegex(b[d:], r"(?i)exit 3", "`delete-remote` exit 3 is not handled")
        self.assertRegex(b, r"pr\.merge: user", "user mode is not said to keep the remote branch")

    def test_finish_local_merge_ignores_pr_merge(self):
        local = section(read(FINISH), r"local\b")
        self.assertTrue(local, "specwright-finish has no `## local` section")
        self.assertNotRegex(local, r"pr\.merge|delete-remote|merge_method", "the local path reads `pr.merge`")
        self.assertRegex(read(FINISH), r"(?i)`local`[^.]*(ignores|never reads)[^.]*`pr\.merge`|`pr\.merge`[^.]*(ignored|not read)[^.]*`local`|local[^.]*never[^.]*`pr\.merge`",
                         "finish does not say that `local` ignores `pr.merge`")


class FencedGitHubCalls(unittest.TestCase):
    """default-identity-fencing: main refreshes and pulls from GitHub run fenced, decided by the fetch URL."""

    def gate_fetch(self):
        b = find_block(read(BRANCH), r"Used once", r"git fetch")
        self.assertTrue(b, "specwright-branch step 3 has no main refresh")
        return b

    def roadmap_status_bullet(self):
        b = find_block(read(ROADMAP), r"\*\*Main branches\.\*\*")
        self.assertTrue(b, "roadmap has no Main branches rule")
        return b

    def pull_bullet(self):
        text = read(FINISH)
        at = text.index("- **After the PR is merged**")
        return text[at:text.index("\n\n", at)]

    def test_branch_gate_fetch_fenced_local_refs_on_refusal(self):
        b = self.gate_fetch()
        self.assertRegex(b, r"\[as\] git fetch -q origin <main>", "the gate's main refresh is not fenced")
        self.assertRegex(b, r"github\.com", "the gate does not say the fence applies to github.com remotes")
        self.assertRegex(b, r"(?is)refus[^.]*local refs only|local refs only[^.]*refus", "a refusal does not report local refs only")
        self.assertRegex(b, r"(?i)continue", "a refused refresh does not continue on local refs")

    def test_fetch_fenced_by_fetch_url_not_identity(self):
        for name, b in (("branch gate", self.gate_fetch()), ("roadmap status", self.roadmap_status_bullet())):
            self.assertRegex(b, r"git remote get-url", f"{name}: the host is not read from the fetch URL")
            self.assertRegex(b, r"(?i)fetch URL", f"{name}: does not decide by the fetch URL")
            self.assertRegex(b, r"(?is)not (decided )?by `?pr-pair\.sh identity`?", f"{name}: may still be decided by `identity`")

    def test_trailing_dot_host_counts_as_github(self):
        """fix-m2-gaps (#83, review S3): the fetch-URL rule treats `github.com.` as github.com, so that remote is fenced too."""
        for p in (FINISH, ROOT / "skills" / "specwright-pr" / "SKILL.md", BRANCH, ROADMAP):
            lines = [l for l in read(p).splitlines() if re.search(r"(?i)fetch URL|github\.com remote", l) and "github.com" in l]
            self.assertTrue(lines, f"{p.parent.name}: no fetch-URL rule for github.com")
            self.assertTrue(any("`github.com.`" in l for l in lines),
                            f"{p.parent.name}: the fetch-URL rule does not say that `github.com.` counts as github.com")

    def test_non_github_fetch_runs_plain(self):
        for name, b in (("branch gate", self.gate_fetch()), ("roadmap status", self.roadmap_status_bullet())):
            self.assertRegex(b, r"(?is)(other|any other|another) host[^.]*plain|plain[^.]*(other|another) host|not on github\.com[^.]*plain",
                             f"{name}: a non-GitHub remote does not run plain git")

    def test_gate_and_roadmap_status_local_refs_when_resolve_fails(self):
        for name, b in (("branch gate", self.gate_fetch()), ("roadmap status", self.roadmap_status_bullet())):
            self.assertRegex(b, r"--resolve", f"{name}: does not resolve the run login")
            self.assertRegex(b, r"(?is)--resolve[^.]*(fail|exit)[^.]*local refs only|local refs only \(no gh account\)",
                             f"{name}: a failed --resolve does not report local refs only")
            self.assertRegex(b, r"no gh account", f"{name}: the note does not say there is no gh account")
        status = section(read(ROADMAP), r"status\b")
        self.assertRegex(status, r"(?i)local refs only|refused", "roadmap status does not report the refused refresh")

    def test_local_finish_never_resolves(self):
        # PR #82: finish: local makes no GitHub call, so with no gh account it hands `run login: none` instead of stopping
        finish = read(FINISH)
        run_login = finish[finish.index("**Run login.**"):].split("\n", 1)[0]
        self.assertRegex(run_login, r"(?is)--resolve[^.]*only when a GitHub call[^.]*first needs it",
                         "finish resolves the run login before any GitHub call needs it")
        self.assertRegex(run_login, r"(?is)`local` merge[^.]*never resolves", "the local merge may resolve the run login")
        self.assertRegex(run_login, r"(?is)failed `--resolve` on that path is not a stop", "a failed resolve stops a local finish")
        offer = find_block(finish, r"project\.roadmap", r"(?i)\boffer")
        self.assertRegex(offer, r"`run login: none`", "finish -> roadmap cannot hand a run with no login")
        roadmap = read(ROADMAP)
        self.assertRegex(self.roadmap_status_bullet(), r"(?is)handed `run login: none` means local refs only",
                         "roadmap has no meaning for a handed `run login: none`")
        step4 = next((l for l in roadmap.splitlines() if l.startswith("4. Start `/opsx:propose")), "")
        self.assertRegex(step4, r"(?is)`run login: none` as this step was handed it",
                         "roadmap next does not pass a handed `run login: none` on to the gate")

    def test_roadmap_init_close_pulls_fenced(self):
        c = committing_project_files()
        self.assertRegex(c, r"\[as\] git pull --ff-only origin <main>", "the init/close pull is not fenced")
        self.assertRegex(c, r"(?is)github\.com[^.]*\[as\] git pull|\[as\] git pull[^.]*github\.com|fetch URL", "the pull is not tied to a github.com fetch URL")
        self.assertRegex(c, r"(?is)(refus|non-zero|fail)[^.]*\bstop", "a refused or failed pull does not stop")
        self.assertRegex(c, r"(?i)nothing (is )?branched|branch nothing|before (any )?branch", "a failed pull may still branch")

    def test_finish_post_merge_check_fenced_with_repo(self):
        b = self.pull_bullet()
        self.assertNotRegex(b, r"(?<!\] )gh pr view <branch>", "finish still runs plain `gh pr view <branch>`")
        view = re.search(r"\[as\] gh pr view <branch>[^`]*", b)
        disc = re.search(r"\[as\] bash scripts/pr-pair\.sh[^`]*discover[^`]*", b)
        self.assertTrue(view or disc, "the post-merge check is neither a fenced `gh pr view` nor `[as] ... discover`")
        if view:
            self.assertIn("--repo <owner>/<name>", view.group(0), "the fenced `gh pr view` does not name the repository")

    def test_finish_post_merge_check_exit3_stops(self):
        b = self.pull_bullet()
        m = re.search(r"(?i)exit 3[^.;]*", b)
        self.assertTrue(m, "the post-merge check never handles exit 3")
        self.assertRegex(m.group(0), r"(?i)stop", "exit 3 does not stop")
        self.assertRegex(b, r"(?is)exit 3.{0,200}(neither|not)[^.]*merged", "exit 3 may be read as merged or unmerged")

    def test_finish_pull_fenced_stops_on_failure(self):
        text = read(FINISH)
        b = self.pull_bullet()
        self.assertRegex(b, r"\[as\] git pull --ff-only", "the post-merge pull is not fenced")
        self.assertRegex(b, r"(?is)non-zero[^.;]*stop|stop[^.;]*non-zero", "a failed post-merge pull does not stop")
        self.assertRegex(b, r"(?i)delete no branch", "a failed pull may still delete a branch")
        self.assertRegex(b, r"(?i)show the error|report the error", "a failed pull does not show the error")
        # every other pull in finish is fenced too
        for m in re.finditer(r"git pull --ff-only", text):
            self.assertEqual(text[max(0, m.start() - 5):m.start()], "[as] ", f"unfenced pull in finish: {text[m.start() - 60:m.end()]!r}")

    def test_finish_non_github_pull_runs_plain(self):
        self.assertRegex(self.pull_bullet(), r"(?is)(other|another) host[^.]*plain|not on github\.com[^.]*plain|plain[^.]*(other|another) host",
                         "finish does not run a non-GitHub pull plain")

    def test_commit_and_finish_handoffs_pass_run_login(self):
        commit = read(COMMIT)
        pr = next((l for l in commit.splitlines() if l.startswith("- `pr` →")), "")
        self.assertTrue(pr, "commit has no `pr` hand-off")
        self.assertRegex(pr, r"(?i)run login", "commit -> ship does not pass the run login")
        self.assertRegex(pr, r"--resolve", "commit, a user-started step, does not resolve the run login")
        finish = read(FINISH)
        ship = next((l for l in finish.splitlines() if l.startswith("- Run `specwright-pr` **ship**")), "")
        self.assertRegex(ship, r"(?i)run login", "finish -> ship does not pass the run login")
        offer = find_block(finish, r"project\.roadmap", r"(?i)\boffer")
        self.assertRegex(offer, r"(?i)run login", "finish -> the roadmap offer does not pass the run login")
        self.assertRegex(finish, r"(?s)\*\*Run login\.\*\*.{0,1200}(cannot|can't) find[^.]*stop", "finish does not stop when a handed-off step has no run login")

    def test_branch_gate_takes_handed_run_login(self):
        # PR #82: roadmap next starts the gate in the same run; the gate uses the login it is handed, never resolves again
        g = self.gate_fetch()
        self.assertRegex(g, r"run login: <login>", "the gate does not take a handed run login")
        self.assertRegex(g, r"(?is)handed[^.]*run login: <login>[^.]*(otherwise|else)[^.]*`github\.login`",
                         "a handed run login does not come before github.login and --resolve")
        step4 = next((l for l in read(ROADMAP).splitlines() if l.startswith("4. Start `/opsx:propose")), "")
        self.assertRegex(step4, r"run login: <login>", "roadmap next does not hand its run login to the branch gate")
        # PR #82: only a user-started step resolves (github-identity spec). Roadmap next, with no run login yet
        # (local mode), resolves it itself and hands it, or hands `run login: none`; the handed-off gate never resolves.
        self.assertRegex(step4, r"(?is)no run login yet.{0,80}user-started.{0,120}--resolve.{0,120}`run login: none`",
                         "roadmap next with no run login (local mode) does not resolve it before handing off")
        self.assertNotRegex(step4, r"(?i)gate resolves", "roadmap next leaves the resolve to the handed-off gate")
        self.assertRegex(g, r"(?is)--resolve[^.]*only when it is user-started",
                         "the gate resolves even when another step started it")
        self.assertNotRegex(g, r"started by `specwright-roadmap` \*\*next\*\* without a login",
                            "the gate still resolves when roadmap next hands it no login")
        self.assertRegex(g, r"(?is)`run login: none`[^.]*local refs only", "the gate has no meaning for a handed `run login: none`")

    def test_store_login_chosen_per_repo(self):
        # PR #82: a handed run login is the code repo's; the store keeps planning_store.login.
        finish = read(FINISH)
        run_login = finish[finish.index("**Run login.**"):].split("\n", 1)[0]
        for name, b in (("branch gate", self.gate_fetch()), ("finish", run_login), ("roadmap status", self.roadmap_status_bullet())):
            self.assertNotIn("(the store's: `planning_store.login`)", b, f"{name}: the store login is still an alternative to the handed login")
            self.assertRegex(b, r"(?is)store[^.]*`planning_store\.login`[^.]*else[^.]*run login",
                             f"{name}: the store does not use planning_store.login, else the code repo's run login")
        pr = read(PR_SKILL)
        settings = next((l for l in pr.splitlines() if "**Settings per repo:**" in l), "")
        self.assertTrue(settings, "specwright-pr has no Settings per repo block")
        self.assertRegex(settings, r"(?i)empty store login means the run login", "specwright-pr: an empty store login has no fallback")
        self.assertRegex(settings, r"(?i)handed run login never replaces a set `planning_store\.login`",
                         "specwright-pr: a handed run login may replace planning_store.login")


class InstallSettingsKeys(unittest.TestCase):
    """README install Steps 6-7 compare settings by dotted path; commented-out template keys are optional (#78)."""

    def s6(self):
        s = step(read(README), "Step 6")
        self.assertTrue(s, "README install prompt has no Step 6")
        return s

    def test_install_compares_dotted_paths(self):
        s6 = self.s6()
        self.assertRegex(s6, r"(?i)dotted path", "Step 6 does not compare keys by dotted path")
        self.assertRegex(s6, r"(?i)never by (the )?bare (key )?name", "Step 6 does not forbid comparing bare names")
        self.assertRegex(s6, r"planning_store\.login", "Step 6 gives no example of the same name at two paths")

    def test_install_step6_commented_paths_optional(self):
        s6 = self.s6()
        self.assertRegex(s6, r"(?is)comment(ed)?[- ]out.{0,300}optional", "commented-out template paths are not optional")
        self.assertRegex(s6, r"(?is)comment(ed)?[- ]out.{0,600}never (list|listed).{0,40}remov",
                         "a commented-out path the project sets may still be listed as removed")
        self.assertRegex(s6, r"(?is)indentation.{0,80}#|#.{0,80}indentation", "the path of a commented-out line is not read from its indentation after #")

    def test_install_step6_never_adds_commented(self):
        s6 = self.s6()
        self.assertRegex(s6, r"(?is)comment(ed)?[- ]out.{0,600}never add", "Step 6 may add a commented-out key")

    def test_install_reviewer_entries_user_data(self):
        s6 = self.s6()
        self.assertRegex(s6, r"pr\.reviewers\.", "pr.reviewers entries are not named")
        self.assertRegex(s6, r"planning_store\.reviewers\.", "planning_store.reviewers entries are not named")
        self.assertRegex(s6, r"(?is)user data.{0,200}never (compared|compare)", "reviewer entries are still compared")

    def test_install_step7_uncommented_only(self):
        s7 = step(read(README), "Step 7")
        self.assertTrue(s7, "README install prompt has no Step 7")
        self.assertRegex(s7, r"(?is)every uncommented (dotted )?path", "Step 7 requires keys the template only has commented out")

    def test_install_step6_asks_before_removing(self):
        s6 = self.s6()
        self.assertRegex(s6, r"(?is)no longer has.{0,120}(list|ask).{0,80}before removing",
                         "the removed-key question is gone")


OPENSPEC_PIN_FILE = ROOT / "OPENSPEC_VERSION"


def openspec_pin():
    """The pinned OpenSpec version from OPENSPEC_VERSION."""
    assert OPENSPEC_PIN_FILE.is_file(), "OPENSPEC_VERSION is missing at the repo root"
    pin = read(OPENSPEC_PIN_FILE).strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", pin), f"OPENSPEC_VERSION does not hold a version: {pin!r}"
    return pin


def pin_drift(readme, contributing, pin, extra=(), badge=True):
    """The README and CONTRIBUTING lines (and `extra` (name, text) pairs) that disagree with the OpenSpec pin, as `file:line: text`."""
    out = []

    def name(fname, text, pos):
        n = text.count("\n", 0, pos) + 1
        out.append(f"{fname}:{n}: {text.splitlines()[n - 1].strip()}")

    for fname, text in (("README.md", readme), ("CONTRIBUTING.md", contributing), *extra):
        for m in re.finditer(r'npm i -g @fission-ai/openspec(@\S+?)?(?=[`\s)"\\,]|\.(?:\s|$)|$)', text):
            if m.group(1) not in ("@" + pin, "@<pin>"):
                name(fname, text, m.start())
        for m in re.finditer(r"`spec-driven`\s*\((\d[^)\s]*)\)", text):
            if m.group(1) != pin:
                name(fname, text, m.start())
        # Prose that spells the pin out: Step 1's comparison, the override note and report, examples, Stores note.
        for m in re.finditer(r"(?:\bnot\s+|`OPENSPEC_VERSION`,\s+|\(pinned\s+|\ba\s+pin\s+of\s+|pinned\s+OpenSpec,\s+)"
                             r"(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)(?=[\s,)])", text):
            if m.group(1) != pin:
                name(fname, text, m.start(1))
        # Python 3.8 and gh 2.40 are two-part; an OpenSpec version is three-part.
        for m in re.finditer(r"\d+\.\d+\.\d+\s+or\s+later", text):
            name(fname, text, m.start())
    if badge:
        b = re.search(r"badge/OpenSpec-([^-]+)-", readme)
        if not b or b.group(1) != pin:
            name("README.md", readme, b.start() if b else 0)
    return out


class TestOpenSpecPin(unittest.TestCase):
    def test_install_commands_and_badge_match_pin(self):
        pin = openspec_pin()
        readme, contributing = read(README), read(CONTRIBUTING)
        self.assertEqual(pin_drift(readme, contributing, pin), [], "lines disagree with OPENSPEC_VERSION")
        self.assertIn(f"npm i -g @fission-ai/openspec@{pin}", prerequisites(), "the prerequisites do not install the pin")
        s1 = step(readme, "Step 1")
        self.assertIn(f"npm i -g @fission-ai/openspec@{pin}", s1 or "", "Step 1 does not install the pin")
        self.assertIn(f"npm i -g @fission-ai/openspec@{pin}", contributing, "CONTRIBUTING does not install the pin")
        self.assertRegex(contributing, r"(?s)upgrade.{0,200}OPENSPEC_VERSION", "the upgrade rule does not name OPENSPEC_VERSION")

    def test_pin_drift_names_disagreeing_line(self):
        pin = openspec_pin()
        readme = read(README)
        drift = pin_drift(readme, read(CONTRIBUTING), "1.15.0")
        line = next(i for i, l in enumerate(readme.splitlines(), 1) if "**Prerequisites:**" in l)
        self.assertIn(f"npm i -g @fission-ai/openspec@{pin}", readme.splitlines()[line - 1])
        self.assertTrue(any(d.startswith(f"README.md:{line}:") for d in drift),
                        f"a pin bumped only in OPENSPEC_VERSION does not name README line {line}: {drift}")

    def test_pin_drift_names_every_literal_pin_mention(self):
        # Prose that spells the pin out (not only install commands) goes stale on an upgrade too.
        pin, readme = openspec_pin(), read(README)
        drift = pin_drift(readme, read(CONTRIBUTING), "0.0.0")
        lines, v = readme.splitlines(), re.escape(pin)
        for label, pat in (("Step 1 comparison", rf"not\s+{v}\s+\(the\s+pin"), ("override note", rf"OPENSPEC_VERSION`,\s+{v}\)"),
                           ("override report", rf"\(pinned\s+{v},\s+override\)"), ("Step 3 example", rf"a\s+pin\s+of\s+{v}"),
                           ("Stores note", rf"pinned\s+OpenSpec,\s+{v}\)")):
            n = next((i for i, l in enumerate(lines, 1) if re.search(pat, l)), None)
            self.assertTrue(n, f"the README has no {label} naming {pin}; update this test")
            self.assertTrue(any(d.startswith(f"README.md:{n}:") for d in drift),
                            f"a stale {label} (README line {n}) is not named: {drift}")

    def test_upgrade_rule_names_pin_prose(self):
        contributing = read(CONTRIBUTING)
        rule = next(l for l in contributing.splitlines() if "OpenSpec upgrade" in l)
        self.assertRegex(rule, r"(?i)every\s+.{0,40}mention|spells?\s+out", "the upgrade rule does not cover pin prose")

    # Install prompt: the version check (Step 1 records, Step 3 compares before Step 4 writes).

    def s3_check(self):
        s3 = step(read(README), "Step 3")
        self.assertTrue(s3, "README install prompt has no Step 3")
        check = install_bullet(s3, r"openspec --version", r"OPENSPEC_VERSION|<pin>")
        self.assertTrue(check, "Step 3 has no OpenSpec version check bullet")
        return s3, check

    def stop_branch(self, check, *patterns):
        """The nested `  - ` bullet of the check matching every pattern."""
        for b in re.split(r"\n(?=\s+- )", check):
            if all(re.search(p, b, re.I | re.S) for p in patterns):
                return b
        self.fail(f"the Step 3 check has no branch matching {patterns}")

    def assert_stops(self, b):
        self.assertRegex(b, r"STOP", "the branch does not STOP")
        self.assertRegex(b, r"(?i)before\s+Step\s+4", "the branch does not stop before Step 4")
        self.assertRegex(b, r"<found>", "the branch does not name the version found")
        self.assertRegex(b, r"<pin>", "the branch does not name the pin")
        self.assertIn("npm i -g @fission-ai/openspec@<pin>", b, "the branch does not name the pinned install command")
        self.assertRegex(b, r"(?i)delete\s+the\s+temporary\s+(directory|clone)", "the branch does not delete the temporary clone")
        self.assertRegex(b, r"(?i)write\s+no\s+file|no\s+file\s+is\s+written|writes?\s+nothing", "the branch does not rule out writes")

    def test_step3_compares_with_downloaded_pin_before_step4(self):
        readme = read(README)
        s3, check = self.s3_check()
        self.assertRegex(s3, r"(?s)downloaded `VERSION`.{0,80}`OPENSPEC_VERSION`", "Step 3 does not read the downloaded OPENSPEC_VERSION")
        self.assertRegex(check, r"(?i)before\s+Step\s+4", "the check does not sit before Step 4")
        self.assertIn(r"\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?", check, "the check does not name the version token")
        self.assertRegex(check, r"(?i)exact", "the check does not require an exact match")
        self.assertLess(readme.index(check), readme.index("Step 4 - "), "the check is not before Step 4")
        s8 = step(readme, "Step 8")
        self.assertIn("OpenSpec <found> (pinned)", s8 or "", "Step 8 does not report `OpenSpec <found> (pinned)`")

    def test_mismatch_stops_before_any_write(self):
        _, check = self.s3_check()
        self.assert_stops(self.stop_branch(check, r"(?i)mismatch", r"STOP"))

    def test_exact_match_counts_prerelease_as_mismatch(self):
        _, check = self.s3_check()
        self.assertRegex(check, r"(?is)whole token.{0,80}pre-release|pre-release.{0,80}whole token",
                         "the check does not compare the whole token, pre-release included")
        self.assertRegex(check, r"(?s)1\.14\.1-beta\.1.{0,80}mismatch|mismatch.{0,80}1\.14\.1-beta\.1",
                         "a pre-release of the pin is not named as a mismatch")
        self.assertRegex(check, r"1\.14\.2", "a newer patch release is not named as a mismatch")

    def test_exact_match_counts_build_metadata_as_mismatch(self):
        # A token cut before `+build` would turn 1.14.1+vendor.1 into 1.14.1 and pass.
        token = r"`\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?`"
        _, check = self.s3_check()
        self.assertIn(token, check, "the Step 3 token drops build metadata")
        self.assertRegex(check, r"(?is)whole token.{0,80}build metadata", "the check does not keep build metadata in the token")
        self.assertRegex(check, r"(?s)1\.14\.1\+vendor\.1.{0,80}mismatch|mismatch.{0,80}1\.14\.1\+vendor\.1",
                         "a build of the pin is not named as a mismatch")
        root = install_bullet(step(read(README), "Step 1"), r"openspec list --json")
        self.assertIn(token, root or "", "the Step 1 token drops build metadata")

    def test_unreadable_version_stops(self):
        _, check = self.s3_check()
        b = self.stop_branch(check, r"(?i)no version (number|token)")
        self.assertRegex(b, r"(?i)raw output", "the unreadable output is not shown")
        self.assert_stops(b)

    def test_missing_pin_file_stops(self):
        _, check = self.s3_check()
        b = self.stop_branch(check, r"(?i)no `OPENSPEC_VERSION`", r"(?i)empty")
        self.assertRegex(b, r"(?i)names\s+no\s+pinned\s+OpenSpec\s+version", "the stop does not say the copy names no pin")
        self.assert_stops(b)

    def test_step1_root_failure_on_unpinned_cli_names_pin_not_init(self):
        pin = openspec_pin()
        s1 = step(read(README), "Step 1")
        root = install_bullet(s1, r"openspec list --json")
        self.assertTrue(root, "Step 1 has no root check")
        unpinned = re.search(rf"(?is)version.{{0,40}}recorded.{{0,200}}?(not|differs).{{0,400}}?STOP", root)
        self.assertTrue(unpinned, "the root-check failure has no branch for an unpinned OpenSpec")
        b = unpinned.group(0)
        self.assertRegex(b, r"(?i)(name|naming)\s+the\s+version\s+found", "the unpinned branch does not name the version found")
        self.assertIn(f"npm i -g @fission-ai/openspec@{pin}", b, "the unpinned branch does not name the pinned install command")
        self.assertNotRegex(b, r"run\s+`openspec init`", "the unpinned branch tells the user to run openspec init")
        self.assertRegex(root, r"(?is)(do not|never) suggest\s+`openspec init`", "the unpinned branch does not rule out openspec init")
        self.assertRegex(root, r"(?is)pinned version.{0,120}`openspec init`", "openspec init advice is not limited to the pinned version")

    def test_step1_root_failure_compares_version_token(self):
        # Step 1 compares the same token Step 3 takes, not the whole `--version` output.
        root = install_bullet(step(read(README), "Step 1"), r"openspec list --json")
        unpinned = re.search(r"(?is)version.{0,40}recorded.{0,200}?\bnot\s+\d", root or "")
        self.assertTrue(unpinned, "the root-check failure has no comparison with the pin")
        self.assertIn(r"\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?", unpinned.group(0), "Step 1 does not take the version token")
        self.assertRegex(unpinned.group(0), r"(?is)as\s+Step\s+3\s+takes\s+it", "Step 1 does not take the token as Step 3 does")

    def test_step3_run_on_token_is_unreadable(self):
        _, check = self.s3_check()
        self.assertRegex(check, r"(?is)directly\s+followed\s+by\s+a\s+digit,\s+(a\s+)?letter,\s+`\.`,\s+`\+`\s+or\s+`-`.{0,120}unreadable",
                         "Step 3 does not call a run-on token unreadable output")
        self.assertIn("1.14.1.0", check, "Step 3 does not give 1.14.1.0 as an example")
        self.assertIn("1.14.1vendor", check, "Step 3 does not give 1.14.1vendor as an example")
        self.assertNotIn("(?!", check, "Step 3 uses a negative lookahead")

    def test_step1_run_on_token_is_unreadable(self):
        root = install_bullet(step(read(README), "Step 1"), r"openspec list --json")
        unpinned = re.search(r"(?is)version.{0,40}recorded.{0,200}?\bnot\s+\d.{0,400}?STOP", root or "")
        self.assertTrue(unpinned, "the root-check failure has no comparison with the pin")
        self.assertRegex(unpinned.group(0), r"(?is)as\s+Step\s+3\s+takes\s+it", "Step 1 does not refer to Step 3's rule")
        self.assertRegex(unpinned.group(0), r"(?is)unreadable", "Step 1 does not treat a run-on token as unreadable")
        self.assertNotIn("(?!", root, "Step 1 uses a negative lookahead")

    def test_readme_token_rule_on_sample_outputs(self):
        # Run the rule as the README states it: first match of its own token pattern, then the boundary character.
        _, check = self.s3_check()
        m = re.search(r"`(\\d\+\\\.\\d\+\\\.\\d\+[^`]*)`", check)
        self.assertTrue(m, "Step 3 states no token pattern")
        token = re.compile(m.group(1))
        rule = re.search(r"directly\s+followed\s+by\s+a\s+digit,\s+(?:a\s+)?letter,\s+`(.)`,\s+`(.)`\s+or\s+`(.)`", check)
        self.assertTrue(rule, "Step 3 states no boundary rule")
        bound = "0-9A-Za-z" + "".join(re.escape(c) for c in rule.groups())

        def read_version(out):
            t = token.search(out)
            if not t:
                return "unreadable"
            if re.match(rf"[{bound}]", out[t.end():t.end() + 1]):
                return "unreadable"
            return t.group(0)

        for out, want in (("1.14.1", "1.14.1"), ("openspec 1.14.1\n", "1.14.1"), ("1.14.1+vendor.1", "1.14.1+vendor.1"),
                          ("1.14.1.0", "unreadable"), ("1.14.1vendor", "unreadable")):
            self.assertEqual(read_version(out), want, f"the README rule reads {out!r} wrongly")

    def test_eval_scaffolding_matches_pin(self):
        # The pin evals spell the pin out too; the fake must report another version, or the refusal tests nothing.
        pin, here = openspec_pin(), Path(__file__).resolve().parent
        files = [(f"evals/git-workflow/{n}", read(here / n)) for n in ("grade.py", "test_grade.py", "evals.json")]
        self.assertEqual(pin_drift("", "", pin, files, badge=False), [], "eval scaffolding disagrees with OPENSPEC_VERSION")
        stale = pin_drift("", "", "0.0.0", files, badge=False)
        for n in ("grade.py", "test_grade.py", "evals.json"):
            self.assertTrue(any(d.startswith(f"evals/git-workflow/{n}:") for d in stale), f"pin_drift does not read {n}")
        fake = re.search(r'install_fake_openspec\(repo,\s*"([^"]+)"\)', read(here / "fixtures.py"))
        self.assertTrue(fake, "fixtures.py does not install the fake openspec")
        self.assertNotEqual(fake.group(1), pin, "the fake openspec reports the pin, so the refusal eval tests nothing")
        self.assertRegex(read(CONTRIBUTING), r"(?s)OpenSpec upgrade.{0,900}the two OpenSpec-pin evals",
                         "the upgrade rule does not name the pin evals")

    def test_step1_missing_openspec_names_pinned_install(self):
        pin = openspec_pin()
        s1 = step(read(README), "Step 1")
        b = install_bullet(s1, r"openspec --version")
        self.assertTrue(b, "Step 1 does not run openspec --version")
        self.assertRegex(b, r"(?i)record", "Step 1 does not record the openspec --version output")
        self.assertIn(f"npm i -g @fission-ai/openspec@{pin}", b, "a missing OpenSpec does not name the pinned install command")
        self.assertRegex(b, r"STOP", "a missing OpenSpec does not stop the install")

    # The explicit override: the user's own words, naming the found version.

    def override(self):
        s3 = step(read(README), "Step 3")
        b = install_bullet(s3 or "", r"^- Override\b")
        self.assertTrue(b, "Step 3 has no override bullet")
        return b

    def test_override_requires_found_version_and_is_reported(self):
        readme, b = read(README), self.override()
        self.assertIn("continue with OpenSpec <found>", b, "the override does not require `continue with OpenSpec <found>`")
        self.assertRegex(b, r"(?i)own\s+words", "the override does not require the user's own words")
        self.assertRegex(b, r"(?is)(request|reply)", "the override does not say where the user may state it")
        self.assertRegex(b, r"(?is)never\s+(offer|recommend).{0,60}default|not\s+.{0,20}default", "the override may be offered as a default")
        self.assertRegex(b, r"(?is)(this|one)\s+run\s+only|nothing\s+is\s+(stored|saved)", "the override is not limited to one run")
        _, check = self.s3_check()
        mismatch = self.stop_branch(check, r"(?i)mismatch", r"STOP")
        self.assertRegex(mismatch, r"(?i)unless\s+the\s+(user\s+states\s+the\s+)?override", "the mismatch stop does not yield to a stated override")
        s8 = step(readme, "Step 8")
        self.assertIn("OpenSpec <found> (pinned <pin>, override)", s8 or "", "Step 8 does not report the override")
        docs = readme[readme.index("**Prerequisites:**"): readme.index("```text")]
        self.assertRegex(docs, r"continue with OpenSpec <(found|version)>|continue with OpenSpec \d",
                         "the README does not document the override next to the prerequisites")

    def test_general_confirmation_is_not_override(self):
        b = self.override()
        self.assertRegex(b, r"(?is)(plain|general)\s+.{0,40}(yes|confirmation).{0,120}\bnot\b.{0,20}override",
                         "a general confirmation is not ruled out as an override")
        self.assertRegex(b, r"(?is)install\s+<pin>.{0,120}state\s+the\s+override|state\s+the\s+override.{0,120}install\s+<pin>",
                         "a general confirmation does not ask to install the pin or state the override")

    def test_override_for_other_version_stops(self):
        b = self.override()
        self.assertRegex(b, r"(?is)(different|another|other)\s+version.{0,120}\bnot\b.{0,20}override",
                         "an override naming another version is not ruled out")
        self.assertRegex(b, r"(?is)as\s+on\s+a\s+mismatch", "an override for another version does not stop as on a mismatch")

    def test_override_in_reply_downloads_again(self):
        # The mismatch stop deletes the temporary directory, so a later override must fetch it again.
        b = self.override()
        self.assertRegex(b, r"(?is)reply.{0,200}(clone|download).{0,40}again|(clone|download).{0,40}again.{0,200}reply",
                         "an override given in a reply does not download the copy again")


DEBUG = ROOT / "skills" / "specwright-debug" / "SKILL.md"


class DebugStash(unittest.TestCase):
    """specwright-debug names, reports and finds its stash (debugging spec)."""

    def text(self):
        return read(DEBUG)

    def test_stash_is_named_and_ref_reported(self):
        t = self.text()
        self.assertIn('git stash push -u -m "specwright-debug: <topic>"', t, "the test stash is not named")
        self.assertRegex(t, r"(?is)report\w*\s+(the\s+)?(stash\s+)?ref", "the stash ref is not reported")
        self.assertRegex(t, r"(?is)git stash apply.{0,300}git stash drop", "restore is not apply then drop")
        self.assertRegex(t, r"(?is)drop.{0,120}(only\s+)?(after|once).{0,80}(files|verif)", "the drop does not wait for the files to be verified")

    def test_ref_resolved_by_message_before_apply_and_drop(self):
        t = self.text()
        self.assertRegex(t, r"(?is)(look\w*\s+up|find|resolve)\w*.{0,60}(ref\s+)?again.{0,80}message|(ref|stash).{0,60}by\s+(its\s+)?(exact\s+)?message",
                         "the ref is not looked up again by its message")
        self.assertRegex(t, r"(?is)before\s+each\s+`?apply`?\s+and\s+(each\s+)?`?drop", "the lookup does not precede each apply and drop")
        self.assertRegex(t, r"(?is)not\s+found,\s+or\s+found\s+twice,\s+stops", "a missing or doubled message does not stop")

    def test_start_of_run_lists_leftover_stash_and_offers_restore(self):
        t = self.text()
        self.assertIn("git stash list", t)
        self.assertIn("specwright-debug: ", t)
        self.assertRegex(t, r"(?is)offer.{0,80}restore", "no restore offer for a leftover stash")
        self.assertRegex(t, r"(?is)(not|no)\s+(stash\w*\s+)?(again|new\s+stash).{0,80}(user\s+decides|decides)|until\s+the\s+user\s+decides",
                         "the run may stash again before the user decides")

    def test_conflicting_restore_keeps_stash_and_stops(self):
        t = self.text()
        self.assertRegex(t, r"(?is)conflict.{0,160}keep.{0,40}stash.{0,80}stop|conflict.{0,160}stop.{0,80}keep.{0,40}stash",
                         "a conflicting restore does not keep the stash and stop")

    def test_marker_is_matched_after_git_prefix(self):
        # `git stash list` prints `stash@{n}: On <branch>: <message>`, so the marker is never at the start of a line
        t = self.text()
        self.assertIn("On <branch>: ", t, "the list format with Git's branch prefix is not named")
        self.assertRegex(t, r"(?is)after\s+(Git's\s+)?`On <branch>: `", "the marker is not matched after Git's prefix")
        self.assertNotRegex(t, r"(?i)messages that start with `specwright-debug: `", "the marker is still matched at the start of the line")

    def test_no_leftover_reported_and_continues(self):
        self.assertRegex(self.text(), r"(?is)no\s+leftover\s+stash\s+and\s+continue", "no leftover stash is not reported")

    def test_only_specwright_debug_stashes_are_offered(self):
        self.assertRegex(self.text(), r"(?is)other\s+stashes.{0,80}(alone|untouched|never)|(never|not).{0,60}other\s+stash",
                         "other stashes are not left alone")


class InstallUpdateLifecycle(unittest.TestCase):
    """README install Steps 3-8 pick a release tag and drive scripts/update.sh (safe-update-lifecycle)."""

    def s(self, n):
        text = step(read(README), f"Step {n}")
        self.assertTrue(text, f"README install prompt has no Step {n}")
        return text

    def branch(self, s, *patterns):
        """The first bullet (top-level or nested) of a step matching every pattern."""
        for b in re.split(r"\n(?=\s*- )", s):
            if all(re.search(p, b, re.I | re.S) for p in patterns):
                return b
        self.fail(f"no bullet matches {patterns}")

    def assert_stops_before_staging(self, b):
        self.assertRegex(b, r"STOP", "the bullet does not STOP")
        self.assertRegex(b, r"(?i)before\s+Step\s+4", "the bullet does not stop before Step 4")
        self.assertRegex(b, r"(?i)write\s+no\s+file", "the bullet does not rule out writes")

    # Step 3: which ref is installed.

    def test_step3_installs_latest_tag(self):
        s3 = self.s(3)
        self.assertRegex(s3, r"git ls-remote --tags --refs \S+ 'v\*'", "Step 3 does not list the release tags")
        self.assertRegex(s3, r"(?is)highest.{0,60}(semver|semantic)", "Step 3 does not take the highest semver tag")
        self.assertRegex(s3, r"git clone --depth 1 --branch <tag>", "Step 3 does not clone the chosen tag")
        self.assertRegex(s3, r"(?is)latest.{0,40}tag|tag.{0,60}default", "the latest tag is not the default")
        self.assertRegex(self.s(8), r"(?is)\bref\b.{0,20}installed", "Step 8 does not report the ref installed")

    def test_step3_named_version_without_tag_stops(self):
        b = self.branch(self.s(3), r"named", r"does not exist")
        self.assert_stops_before_staging(b)
        self.assertRegex(b, r"(?is)list.{0,40}tags.{0,40}exist|tags that (do )?exist", "the stop does not list the tags that exist")

    def test_step3_refuses_below_minimum_release(self):
        b = self.branch(self.s(3), r"minimum release", r"0\.6\.0")
        self.assert_stops_before_staging(b)
        self.assertRegex(b, r"(?i)named|highest|latest", "the minimum applies to the default tag too")
        self.assertRegex(b, r"(?i)cannot be installed", "the stop does not say versions before 0.6.0 cannot be installed")
        self.assertRegex(b, r"(?i)offer.{0,60}`main`", "the stop does not offer main")

    def test_step3_checks_script_interface(self):
        b = self.branch(self.s(3), r"scripts/update\.sh", r"interface")
        self.assert_stops_before_staging(b)
        self.assertRegex(b, r"\bplan\b", "the interface is not read from `plan`")
        self.assertRegex(b, r"(?i)interface\s+1\b", "the prompt does not name the interface it drives")
        self.assertRegex(b, r"(?is)name the ref.{0,80}interface", "the stop does not name the ref and the interfaces")
        self.assertRegex(b, r"(?i)has no `scripts/update\.sh", "a download without the script is not stopped")

    def test_step3_falls_back_to_main_without_tags(self):
        s3 = self.s(3)
        self.assertIn("main (no release tag)", s3, "Step 3 does not name the no-tag report")
        self.assertRegex(s3, r"(?is)`main`.{0,120}(asks|request)", "Step 3 does not limit main to a request")
        self.assertRegex(s3, r"(?is)no release tag.{0,200}`main`|`main`.{0,200}no release tag", "Step 3 does not fall back to main without tags")
        self.assertIn("main (no release tag)", self.s(8), "Step 8 does not report `main (no release tag)`")

    # Step 4: the script does the file work.

    def test_step4_runs_update_script_and_acts_on_refusals(self):
        s4 = self.s(4)
        for sub in ("plan", "stage", "swap"):
            self.assertRegex(s4, rf"update\.sh.{{0,300}}`{sub}`|`{sub}`.{{0,300}}update\.sh", f"Step 4 does not run update.sh {sub}")
        self.assertRegex(s4, r"(?i)from the download|download.{0,40}never an installed", "Step 4 may run an installed copy of the script")
        self.assertRegex(s4, r"(?is)refus.{0,300}STOP", "Step 4 does not stop on a refusal")
        self.assertRegex(s4, r"(?is)refus.{0,300}(unchanged|nothing (was )?changed)", "a refusal does not say the installation is unchanged")
        self.assertRegex(s4, r"`swapped`", "Step 4 does not record the swapped flag")
        self.assertRegex(s4, r"`store_written`", "Step 4 does not read store_written")
        self.assertRegex(s4, r"(?is)`recover`.{0,400}resumed update to", "Step 4 does not run recover and say what it did")
        self.assertRegex(s4, r"(?is)orphans.{0,200}ask", "Step 4 does not ask about installed skills with no downloaded counterpart")
        self.assertRegex(s4, r"(?is)do not write.{0,80}VERSION", "Step 4 may write the stamp")

    # Step 5: only the project that writes the store's config merges it.

    def test_step5_runs_only_for_role_none_or_store_written_then_note_config(self):
        s5 = self.s(5)
        self.assertRegex(s5, r"(?is)only.{0,200}role\s+`none`.{0,200}`store_written: true`", "Step 5 is not gated on role none or store_written")
        self.assertRegex(s5, r"(?is)otherwise.{0,40}skip|skip.{0,80}otherwise|any other role.{0,80}skip", "Step 5 does not skip for other roles")
        self.assertRegex(s5, r"(?is)leave.{0,60}config\.yaml", "a skipped Step 5 may touch the store's config.yaml")
        self.assertIn("note-config", s5, "Step 5 does not run note-config")
        self.assertGreater(s5.rindex("note-config"), s5.index("`context:`"), "note-config does not come after the merge")

    def test_step5_failed_note_config_stops(self):
        s5 = self.s(5)
        self.assertNotRegex(s5, r"(?is)note-config.{0,300}go on to Step 7", "a failed note-config still goes on to Step 7")
        self.assertRegex(s5, r"(?is)`\"ok\": false`.{0,120}stop", "a failed note-config does not stop")
        self.assertRegex(s5, r"(?is)stop.{0,120}`note-config` again.{0,120}`\"ok\": true`", "Step 5 does not rerun note-config until it succeeds")

    def test_step4_resumed_swap_takes_store_written_from_recovered(self):
        s4, s5 = self.s(4), self.s(5)
        self.assertRegex(s4, r"(?is)skip `stage` and `swap`.{0,300}recovered\.store_written", "Step 4 does not take store_written from recovered after a resumed swap")
        self.assertRegex(s5, r"(?is)recovered\.store_written", "Step 5 does not name recovered.store_written as the other source")
        self.assertRegex(s5, r"(?is)`swap`.{0,200}`store_written: true`.{0,300}recovered\.store_written", "Step 5 does not name both sources")

    def test_step4_refusal_with_unchanged_false_is_not_reported_unchanged(self):
        b = self.branch(self.s(4), r'"unchanged": false')
        self.assertRegex(b, r"(?is)not (report|say).{0,60}unchanged", "an unchanged:false refusal may be reported as unchanged")
        self.assertRegex(b, r"(?is)installed but not stamped", "the refusal does not say the files are installed but not stamped")
        self.assertRegex(b, r"(?is)restart notice", "the refusal does not give the restart notice")
        self.assertRegex(b, r"(?is)rerunning this prompt.{0,120}completes the update", "the refusal does not say a rerun completes the update")

    # Step 7: the stamp, the store config line, finish.

    def test_step7_reports_store_config_managed_and_runs_finish(self):
        s7 = self.s(7)
        self.assertIn("store config managed by owner <id>", s7, "Step 7 does not report the skipped config.yaml check")
        self.assertRegex(s7, r"(?is)store config managed by owner <id>.{0,200}(not|never).{0,40}fail|(not|never).{0,40}fail.{0,200}store config managed",
                         "the skipped config.yaml check may count as a failure")
        self.assertRegex(s7, r"(?is)still.{0,40}stamp|stamp.{0,200}still|VERSION.{0,80}still", "a managed store config blocks the stamp")
        self.assertRegex(s7, r"update\.sh.{0,80}`finish`|`finish`", "Step 7 does not run finish")
        self.assertGreater(s7.index("`finish`"), s7.index("openspec/.specwright/VERSION"), "finish does not run after the stamp")
        self.assertRegex(s7, r"recover --rollback", "Step 7 does not offer the rollback after a failed check")

    # Step 8: the restart notice follows a swap only.

    def test_step8_restart_notice_after_swap(self):
        s8 = self.s(8)
        self.assertRegex(s8, r"(?is)only.{0,40}(after|when).{0,60}swap|swapped", "Step 8 does not tie the notice to a swap")
        notice = re.search(r"(?is)(started before|still run).{0,300}restart.{0,300}", s8)
        self.assertTrue(notice, "Step 8 has no restart notice for running sessions")
        self.assertRegex(notice.group(0), r"(?s)<old>.{0,200}<new>", "the notice does not name the previous and the new version")
        self.assertRegex(s8, r"(?is)" + NEW_SESSION, "Step 8 does not keep the new-session instruction")
        self.assertRegex(s8, r"(?is)store role.{0,80}owner", "Step 8 does not report the store role and owner")
        self.assertRegex(s8, r"(?is)remote.{0,120}(not validated|warning)", "Step 8 does not report remote-only changes as warnings")

    def test_step8_no_restart_notice_when_unchanged(self):
        s8 = self.s(8)
        self.assertRegex(s8, r"(?is)no restart notice", "Step 8 does not rule out the notice without a swap")
        self.assertRegex(s8, r"(?is)(refus|stop|fail).{0,300}installed version is unchanged", "a refused update does not say the installed version is unchanged")

    # Docs around the prompt.

    def test_docs_name_staging_ignore_and_update_evals(self):
        readme = read(README)
        self.assertIn(".specwright-update-*/", readme, "the README does not name the staging directories")
        self.assertIn(".specwright-update-*/", read(ROOT / ".gitignore"), ".gitignore does not ignore the staging directories")
        self.assertRegex(section(readme, r"\S* ?Stores") or "", r"(?s)STORE.{0,1500}manual commit|manual commit.{0,1500}STORE", "Stores does not explain the transfer")
        self.assertIn("python -m unittest discover evals/update", readme, "the README Evals section does not name evals/update")
        testing = section(read(CONTRIBUTING), "Testing")
        self.assertIn("python -m unittest discover evals/update", testing or "", "CONTRIBUTING Testing does not name evals/update")


REVIEW_TEMPLATE = ROOT / "schemas" / "specwright" / "templates" / "review.md"


class DesignReviewDispositions(unittest.TestCase):
    """DEFERRED and WAIVED are user-owned design-review verdicts (record-review-dispositions)."""

    @classmethod
    def setUpClass(cls):
        text = read(SCHEMA)

        def flat(chunk):
            return re.sub(r"\s+", " ", chunk)  # instruction lines wrap; phrases must not depend on where

        cls.review = flat(text[text.index("  - id: review"):text.index("  - id: tasks")])
        cls.precheck = flat(text[text.index("PRECHECK:"):text.index("Before writing tasks")])
        cls.gate = flat(text[text.index("GATE:"):text.index("Work through pending tasks")])

    def test_tasks_precheck_accepts_deferred_with_target(self):
        p = self.precheck
        self.assertIn("`VERDICT: DEFERRED`", p, "tasks PRECHECK does not name VERDICT: DEFERRED")
        self.assertRegex(p, r"(?is)DEFERRED.{0,400}Deferred to:.{0,200}(at least one|a) target", "DEFERRED does not require a Deferred to: line naming a target")
        self.assertRegex(p, r"(?is)DEFERRED.{0,400}CHANGES_APPLIED: n/a", "DEFERRED is not tied to CHANGES_APPLIED: n/a")

    def test_tasks_precheck_accepts_waived_with_user_words(self):
        p = self.precheck
        self.assertIn("`VERDICT: WAIVED`", p, "tasks PRECHECK does not name VERDICT: WAIVED")
        self.assertRegex(p, r"(?is)WAIVED.{0,500}User decision:.{0,200}quoted", "WAIVED does not require a quoted User decision: line")
        self.assertIn("No design review ran.", p, "WAIVED does not require the 'No design review ran.' line")
        self.assertRegex(p, r"(?is)WAIVED.{0,600}CHANGES_APPLIED: n/a", "WAIVED is not tied to CHANGES_APPLIED: n/a")

    def test_tasks_precheck_ignores_commented_and_placeholder_records(self):
        # The template carries the three DEFERRED/WAIVED record lines inside comments, so an unedited one must not pass (PR #104 review).
        p = self.precheck
        self.assertIn("`Deferred to:`, `User decision:` and `No design review ran.` lines count only outside", p,
                      "PRECHECK does not name which record lines must sit outside a comment")
        self.assertRegex(p, r"(?is)outside an HTML comment", "PRECHECK counts a record line inside an HTML comment")
        self.assertIn("<changes or milestones>", p, "PRECHECK accepts the Deferred to: placeholder")
        self.assertIn("<the user's words>", p, "PRECHECK accepts the User decision: placeholder")
        self.assertRegex(p, r"(?is)placeholder.{0,200}missing|missing.{0,200}placeholder", "PRECHECK does not treat a placeholder as missing")

    def test_tasks_precheck_matches_whole_lines_for_new_verdicts(self):
        p = self.precheck
        self.assertRegex(p, r"(?is)whole lines", "PRECHECK lost whole-line matching")
        self.assertIn("DEFERRED_LATER", p, "PRECHECK does not name DEFERRED_LATER as a non-match")
        self.assertIn("WAIVED?", p, "PRECHECK does not name WAIVED? as a non-match")

    def test_apply_gate_refuses_deferred_and_says_review_needed(self):
        g = self.gate
        self.assertRegex(g, r"(?is)tasks precheck", "apply GATE does not reuse the tasks precheck")
        self.assertRegex(g, r"(?is)`VERDICT: DEFERRED`.{0,300}STOP", "apply GATE does not stop on VERDICT: DEFERRED")
        self.assertRegex(g, r"(?is)before any task is implemented.{0,40}ticked.{0,40}committed", "apply does not stop before implementing, ticking or committing")
        self.assertRegex(g, r"(?is)deferred", "apply does not say the change is deferred")
        self.assertIn("Deferred to:", g, "apply does not name the Deferred to: targets")
        self.assertRegex(g, r"(?is)design review.{0,60}first|first.{0,60}design review", "apply does not say a design review is needed first")
        self.assertRegex(g, r"(?is)(not|never) rewrites? the verdict", "apply does not forbid rewriting the verdict")

    def test_tasks_precheck_stops_on_deferred_without_target(self):
        p = self.precheck
        self.assertRegex(p, r"(?is)DEFERRED.{0,600}STOP", "no stop for DEFERRED without a target")
        self.assertRegex(p, r"(?is)where each part.{0,40}review will happen", "precheck does not ask where each part's review will happen")

    def test_waiver_records_user_words_and_no_review_ran(self):
        r = self.review
        self.assertRegex(r, r'(?is)WAIVED.{0,900}\*\*User decision:\*\* "<the user\'s words>"', "WAIVED does not record the quoted User decision line")
        self.assertIn("No design review ran.", r, "WAIVED does not record 'No design review ran.'")
        self.assertRegex(r, r"(?is)WAIVED.{0,1200}CHANGES_APPLIED: n/a", "WAIVED does not carry CHANGES_APPLIED: n/a")
        self.assertRegex(r, r"(?is)DEFERRED.{0,900}\*\*Deferred to:\*\*", "DEFERRED does not record the Deferred to: line")
        self.assertRegex(r, r"(?is)DEFERRED.{0,600}(parking|never applied)", "DEFERRED is not limited to a parking change")

    def test_waiver_without_user_words_refused_at_tasks_and_apply(self):
        p, g = self.precheck, self.gate
        self.assertRegex(p, r"(?is)WAIVED.{0,900}STOP", "tasks precheck does not stop on a WAIVED without its record")
        self.assertRegex(g, r"(?is)WAIVED.{0,300}(without|missing|lacks?).{0,200}(STOP|stops?)|WAIVED.{0,300}fails? the tasks precheck", "apply does not stop on a WAIVED without its record")

    def test_agent_never_offers_waiver_or_deferral(self):
        r = self.review
        self.assertRegex(r, r"(?is)never (offer|suggest)s?.{0,300}(DEFERRED|WAIVED|deferral|waiver)", "review instruction does not forbid offering the new verdicts")
        self.assertRegex(r, r"(?is)never (offer|suggest).{0,400}(route fails|failed route)", "offering after a failed route is not ruled out")
        self.assertRegex(r, r"(?is)never (offer|suggest).{0,400}REVISE", "offering after REVISE rounds is not ruled out")
        self.assertRegex(r, r"(?is)never (offer|suggest).{0,500}(way past|missing review)", "offering as a way past a missing review is not ruled out")
        self.assertIn("If no route works, STOP and tell the user", r, "the no-route STOP rule was lost")

    def test_waiver_does_not_waive_preship(self):
        r = self.review
        self.assertRegex(r, r"(?is)WAIVED.{0,1500}pre-ship.{0,120}(not waived|still runs|does not waive|never waive)", "WAIVED does not keep the pre-ship review")

    def test_user_override_only_after_escalation(self):
        r = self.review
        self.assertRegex(r, r"(?is)USER_OVERRIDE.{0,300}(after 2 consecutive REVISE|escalat)", "USER_OVERRIDE is not limited to escalation")
        self.assertRegex(r, r"(?is)USER_OVERRIDE.{0,500}user's words.{0,80}open findings", "USER_OVERRIDE does not record the user's words and open findings")
        self.assertRegex(r, r"(?is)(deferral|DEFERRED).{0,200}(waiver|WAIVED).{0,100}never.{0,80}USER_OVERRIDE", "a deferral or waiver is not barred from USER_OVERRIDE")

    def test_review_template_and_readme_list_new_verdicts(self):
        t = read(REVIEW_TEMPLATE)
        self.assertRegex(t, r"DEFERRED \| WAIVED", "template verdict comment does not list DEFERRED | WAIVED")
        self.assertIn("none (DEFERRED by the user)", t)
        self.assertIn("none (WAIVED by the user)", t)
        self.assertIn("**Deferred to:**", t)
        self.assertIn("**User decision:**", t)
        readme = read(README)
        table = readme[readme.index("Review verdicts"):]
        table = table[:table.index("</details>")]
        self.assertRegex(table, r"\| `DEFERRED` \|", "README has no DEFERRED row")
        self.assertRegex(table, r"\| `WAIVED` \|", "README has no WAIVED row")
        self.assertRegex(table, r"(?is)USER_OVERRIDE.{0,400}rewrit.{0,100}DEFERRED|rewrit.{0,200}DEFERRED.{0,200}USER_OVERRIDE", "README lacks the note on rewriting a deferral recorded as USER_OVERRIDE")

    # Archive refusal (task group 2).

    @staticmethod
    def _context_lines(path):
        text = read(path)
        block = text[text.index("context: |"):]
        lines = []
        for ln in block.splitlines()[1:]:
            if not ln.startswith("  "):
                break
            lines.append(ln.strip())
        return lines

    def test_config_context_refuses_archive_of_deferred(self):
        own = ROOT / "openspec" / "config.yaml"  # git-ignored: absent in a fresh clone
        for path in (ROOT / "templates" / "openspec" / "config.yaml", *([own] if own.exists() else [])):
            lines = [ln for ln in self._context_lines(path) if ln.startswith("MANDATORY: Before archiving a change")]
            where = str(path.relative_to(ROOT))
            self.assertEqual(len(lines), 1, f"{where} does not carry exactly one archive-refusal context line")
            ln = lines[0]
            for name in ("/opsx:archive", "/opsx:bulk-archive", "openspec-archive-change", "'openspec archive'"):
                self.assertIn(name, ln, f"{where} refusal line does not name {name}")
            self.assertIn("review.md", ln, f"{where} refusal line does not read review.md")
            self.assertIn("`VERDICT: DEFERRED`", ln, f"{where} refusal line does not name VERDICT: DEFERRED")
            self.assertRegex(ln, r"(?is)do not archive", f"{where} does not say do not archive")
            self.assertRegex(ln, r"(?is)move nothing", f"{where} does not say move nothing")
            self.assertRegex(ln, r"(?is)sync no spec", f"{where} does not say sync no spec")
            self.assertIn("`Deferred to:`", ln, f"{where} does not name the Deferred to: targets")
            self.assertRegex(ln, r"(?is)bulk archive.{0,80}skip.{0,80}archive the rest", f"{where} does not skip the change in a bulk archive")

    def test_finish_resume_runs_deferred_check_on_committed_archive(self):
        # A committed but unmerged deferred archive must not reach the merge/ship rows unchecked (PR #104 review).
        flat = re.sub(r"\s+", " ", read(FINISH))
        resume = flat[flat.index("## Resume"):flat.index("| Facts | Next |")]
        self.assertRegex(resume, r"(?is)before any (table )?row.{0,200}step 0", "resume does not run step 0 before the table rows")
        self.assertIn("a committed archive gets the same check", resume, "resume skips step 0 for a committed archive")
        s0 = flat[flat.index("0. **"):flat.index("1. **Branch")]
        self.assertIn("git revert --no-edit <A>", s0, "step 0 does not give the revert of a committed archive")
        self.assertRegex(s0, r"(?is)never (a )?reset", "step 0 does not forbid a reset of the committed archive")

    def test_finish_step0_undoes_bulk_archive_as_a_whole(self):
        # Restoring a shared main spec also drops another change's sync, so a bulk archive is undone whole (PR #104 review).
        flat = re.sub(r"\s+", " ", read(FINISH))
        s0 = flat[flat.index("0. **"):flat.index("1. **Branch")]
        self.assertIn("undo the whole bulk archive", s0, "step 0 does not undo a bulk archive as a whole")
        self.assertRegex(s0, r"(?is)again without the deferred change", "step 0 does not rerun the bulk archive without the deferred change")
        self.assertRegex(s0, r"(?is)never restore only the deferred change", "step 0 allows restoring only the deferred change's files")

    def test_finish_step0_stops_on_deferred_and_lists_restore_groups(self):
        text = read(FINISH)
        flat = re.sub(r"\s+", " ", text)
        self.assertTrue("0. **" in text, "finish has no step 0")
        s0 = flat[flat.index("0. **"):flat.index("1. **Branch")]
        self.assertIn("VERDICT: DEFERRED", s0, "step 0 does not check VERDICT: DEFERRED")
        self.assertRegex(s0, r"(?is)archive.{0,40}(director|name)", "step 0 does not read the archived review.md")
        self.assertRegex(s0, r"(?is)every (archived )?change|each archived change", "step 0 does not check every archived change")
        self.assertRegex(s0, r"(?is)no commit.{0,60}merge.{0,40}push|before any commit, merge or push", "step 0 does not stop before commit, merge and push")
        self.assertRegex(s0, r"(?is)no restore|restore nothing|never restores?|runs? no restore", "step 0 does not forbid restoring itself")
        self.assertIn("git restore -- <file>", s0, "step 0 does not give the main-spec restore")
        self.assertRegex(s0, r"(?is)uncommitted edits", "step 0 does not warn about the user's uncommitted edits")
        self.assertRegex(s0, r"(?is)(created|untracked).{0,200}delete", "step 0 does not list created main specs to delete")
        self.assertIn("git restore -- <P>/changes/<name>/", s0, "step 0 does not give the change directory restore")
        self.assertRegex(s0, r"(?is)otherwise.{0,60}move.{0,60}back", "step 0 does not give the move-back fallback")
        self.assertRegex(s0, r"(?is)git restore -- <P>/changes/<name>/.{0,200}delete.{0,40}<P>/changes/archive/<archived-name>/", "after git restore, step 0 does not say to delete the archive copy")
        row = next((r for r in text.splitlines() if r.startswith("| archive paths uncommitted, no A")), "")
        self.assertRegex(row, r"(?i)steps 0-3|starts? at step 0", "the Resume table's first row does not reach step 0")

    def test_template_context_lines_use_managed_prefixes(self):
        readme = re.sub(r"\s+", " ", read(README))
        start = readme.index("is Specwright-managed when it starts with")
        end = readme.index("Remove every managed line", start)
        prefixes = re.findall(r"`([^`]+)`", readme[start:end])
        self.assertIn("MANDATORY: Before archiving a change", prefixes, "README Step 5 does not list the archive-refusal prefix")
        for ln in self._context_lines(ROOT / "templates" / "openspec" / "config.yaml"):
            self.assertTrue(any(ln.startswith(p) for p in prefixes), f"context line is not covered by a managed prefix: {ln[:60]}")

    # Watch and parked changes (task group 3).

    @staticmethod
    def _archive_before_merge():
        watch = section(read(PR_SKILL), r"watch\b")
        m = re.search(r"^   - \*\*Archive before merge:\*\*.*?(?=^   - \*\*Merge:\*\*)", watch or "", re.M | re.S)
        assert m, "watch has no Archive before merge bullet"
        return re.sub(r"\s+", " ", m.group(0))

    def test_watch_skips_archive_for_deferred_and_reports_parked(self):
        b = self._archive_before_merge()
        self.assertIn("`VERDICT: DEFERRED`", b, "Archive before merge does not name VERDICT: DEFERRED")
        self.assertRegex(b, r"(?i)review\.md.{0,80}whole line.{0,40}`VERDICT: DEFERRED`", "Archive before merge does not read review.md for a whole DEFERRED line")
        self.assertRegex(b, r"(?i)DEFERRED.{0,300}archive nothing", "watch archives a DEFERRED change")
        self.assertRegex(b, r"(?i)DEFERRED.{0,400}ready as a parked change.{0,80}user (merges|to merge)", "watch does not report the PR ready as a parked change for the user to merge")
        self.assertRegex(b, r"(?i)DEFERRED.{0,500}(sends?|send) no merge request", "watch may send a merge request for a parked change")

    def test_watch_archive_before_merge_kept_for_other_verdicts(self):
        b = self._archive_before_merge()
        self.assertIn("ask `Ready. Archive <change-name> on this branch now?`", b, "the user-mode archive question was lost")
        self.assertIn("when `merge` is `agent`, archive without asking", b, "the agent-mode archive was lost")
        self.assertRegex(b, r"(?i)every other change \(any other verdict, or no `review\.md`\) archives", "the DEFERRED skip is not scoped to DEFERRED only")
        self.assertNotRegex(b, r"(?i)APPROVE.{0,40}(skip|parked)", "the skip names a verdict other than DEFERRED")


if __name__ == "__main__":
    unittest.main()
