"""The skills call release.sh in the right places and state the release rules.

The script's decisions (check, bump, status, untagged, publish) are tested in test_release.py; these checks
make sure the skill text uses them, by position and key terms and not by exact wording, in the style of
evals/pr-pair/test_skill_text.py.

Run: python -m unittest discover evals/release -p "test_skill_text.py"
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"


def read(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def sections(text):
    """{lowercased '## ' heading: section text}."""
    marks = [(m.start(), m.group(1).strip().lower()) for m in re.finditer(r"^## (.+)$", text, re.M)]
    return {title: text[start:(marks[i + 1][0] if i + 1 < len(marks) else len(text))]
            for i, (start, title) in enumerate(marks)}


def line_with(text, pattern, what):
    """The single line that matches pattern."""
    m = re.search(pattern + r".*$", text, re.M)
    assert m, f"{what} not found"
    return m.group(0)


def paragraph(text, start_pattern, what):
    """The block (up to the next blank line) that starts at the first line matching start_pattern."""
    m = re.search(start_pattern, text, re.M)
    assert m, f"{what} not found"
    end = text.find("\n\n", m.start())
    return text[m.start():end if end != -1 else len(text)]


class TestReleaseSkill(unittest.TestCase):
    def test_frontmatter_matches_version(self):
        text = read(SKILLS / "specwright-release" / "SKILL.md")
        self.assertTrue(text, "skills/specwright-release/SKILL.md is missing")
        self.assertRegex(text, r"(?m)^name: specwright-release$")
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(text, r"(?m)^metadata:\n  version: " + re.escape(version) + r"$")

    def test_states_the_rules(self):
        text = read(SKILLS / "specwright-release" / "SKILL.md")
        self.assertTrue(text, "skills/specwright-release/SKILL.md is missing")
        self.assertRegex(text, r"release\.enabled")
        for sub in ("check", "bump --to", "untagged", "publish --version"):
            self.assertIn(f"release.sh {sub}", text.replace("scripts/release.sh", "release.sh"), f"no `release.sh {sub}`")
        self.assertRegex(text, r"(?i)oldest first")
        self.assertRegex(text, r"(?i)first failure")
        for token in ("--force", "--tags"):
            self.assertIn(token, text, f"the Never list does not name {token}")
        self.assertRegex(text, r"(?i)never[^.\n]*(move|delete)[^.\n]*tag|tag[^.\n]*never[^.\n]*(move|delete)")
        self.assertRegex(text, r"(?i)store")
        self.assertRegex(text, r"(?i)backfill")

    def test_publish_is_fenced_and_fetches_main_only(self):
        # A user-started publish resolves its run login instead of running unfenced, and step 1 fetches main alone:
        # `--tags` would fail on a divergent local tag before release.sh can report tag_mismatch.
        text = read(SKILLS / "specwright-release" / "SKILL.md")
        publish = paragraph(text, r"\*\*Run login\.\*\*", "the publish run-login rule")
        self.assertIn("as.sh --resolve", publish)
        self.assertIn("github.login", publish)
        self.assertNotIn("with no run login, plain", text)
        self.assertNotRegex(text, r"git fetch[^`\n]*--tags")
        self.assertIn("`--no-tags`", text)  # tagOpt=--tags would otherwise fetch every tag


    def test_notes_check_names_proposal_in_planning_repo(self):
        text = read(SKILLS / "specwright-release" / "SKILL.md")
        self.assertTrue(text, "skills/specwright-release/SKILL.md is missing")
        notes = sections(text).get("release notes", "")
        self.assertTrue(notes, "no `## Release notes` section")
        self.assertIn("release.sh notes --proposal <proposal.md>", notes)
        self.assertNotIn("openspec/changes/<change>/proposal.md", notes)
        check = paragraph(notes, r"^.*release\.sh notes --proposal", "the notes check")
        self.assertRegex(check, r"(?i)planning repo", "the notes check does not say the proposal is in the planning repo")
        self.assertRegex(check, r"(?i)store", "the notes check does not name the store")

    def test_no_skill_passes_a_fixed_proposal_path(self):
        bad = [str(p.relative_to(ROOT)) for p in sorted(SKILLS.glob("*/SKILL.md"))
               if "--proposal openspec/" in read(p)]
        self.assertEqual(bad, [], f"skill text passes a fixed proposal path: {bad}")


class TestFinishText(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILLS / "specwright-finish" / "SKILL.md")
        self.assertTrue(self.text)
        self.step = paragraph(self.text, r"^\*\*Release", "finish: the **Release** paragraph")

    def test_release_step_before_roadmap_offer(self):
        roadmap = re.search(r"^If the roadmap \(", self.text, re.M)
        self.assertTrue(roadmap, "finish lost the roadmap offer")
        self.assertLess(self.text.index(self.step), roadmap.start(), "the release step comes after the roadmap offer")
        self.assertRegex(self.step, r"release\.enabled")
        self.assertRegex(self.step, r"(?i)once the change is on main")

    def test_offers_untagged_oldest_first(self):
        s = self.step
        self.assertRegex(s, r"release\.sh untagged")
        self.assertRegex(s, r"specwright-release[^.]*\*\*publish\*\*|\*\*publish\*\*[^.]*specwright-release")
        self.assertRegex(s, r"(?i)oldest first")
        self.assertRegex(s, r"`release\.auto`")
        self.assertRegex(s, r"(?i)first failure")

    def test_no_offer_when_untagged_empty(self):
        s = self.step
        self.assertRegex(s, r"(?is)(nothing|none|empty)[^.]*untagged[^.]*(no|not|say nothing)|untagged[^.]*(nothing|none|empty)[^.]*(say nothing|no release|not mention)|(nothing|none) listed[^.]*(say nothing|no release|not mention)",
                         "an empty `untagged` does not mean no release is mentioned")
        self.assertRegex(s, r"(?i)(say nothing|no release|mention no release|not mention)")

    def test_publish_failure_keeps_roadmap_offer(self):
        s = self.step
        self.assertRegex(s, r"(?is)publish failure[^.]*(error|report)")
        self.assertRegex(s, r"(?is)(undoes? neither|keeps?|does not undo)[^.]*merge[^.]*cleanup|merge[^.]*cleanup[^.]*(stay|kept|not undone)")
        self.assertRegex(s, r"(?is)roadmap offer[^.]*(still|follows)|(still|follows)[^.]*roadmap offer")

    def test_untagged_failure_skips_the_offer(self):
        self.assertRegex(self.step, r"(?is)`untagged`[^.]*fails?[^.]*skip")

    def test_local_mode_never_publishes(self):
        s = self.step
        self.assertRegex(s, r"(?is)`finish: local`[^.]*never publishes?")
        self.assertRegex(s, r"(?i)even with `release\.auto`")
        self.assertIn("after `main` is pushed", s)
        self.assertRegex(s, r"(?i)untagged")


    def test_local_mode_reads_local_tags_unfenced(self):
        s = self.step
        local = re.search(r"[^.]*untagged --local[^.]*\.", s)
        self.assertTrue(local, "the Release step has no `untagged --local` sentence for finish: local")
        self.assertNotIn("as.sh", local.group(0))
        self.assertNotIn("[as]", local.group(0))
        self.assertRegex(s, r"(?is)`finish: local`.{0,120}untagged --local")
        self.assertRegex(s, r"(?i)no login")
        self.assertRegex(s, r"(?i)from local tags")
        self.assertRegex(s, r"(?i)no network call")

    def test_local_merge_checks_version_before_merge(self):
        local = sections(self.text)["local"]
        check = line_with(local, r"^- \*\*Version check\*\*", "finish: the **Version check** bullet of ## local")
        self.assertIn("release.sh check --main <main>", check)
        self.assertRegex(check, r"release\.enabled")
        self.assertRegex(check, r"(?i)before the merge|before `git merge")
        self.assertRegex(check, r"(?is)refus[^.]*stops?[^.]*merge|stops?[^.]*before `git merge`")
        self.assertRegex(check, r"(?i)bump")
        self.assertLess(local.index(check), local.index("Write the merge message"), "the check comes after the merge")
        # store-backed, the store merges first: the code repo's check runs before either merge
        self.assertRegex(check, r"(?i)before either repo's merge")
        store = paragraph(local, r"^- \*\*Store-backed:\*\*", "finish: the **Store-backed:** bullet of ## local")
        self.assertLess(store.index("**Version check**"), store.index("merge and delete the store branch"),
                        "store-backed: the store merges before the version check")


class TestWatchText(unittest.TestCase):
    def setUp(self):
        text = read(SKILLS / "specwright-pr" / "SKILL.md")
        self.assertTrue(text)
        self.cleanup = sections(text)["cleanup after merge"]
        self.step = paragraph(self.cleanup, r"^- \*\*Release step\*\*", "pr: the **Release step** bullet")

    def test_watch_checks_version_before_ready_and_merge(self):
        watch = sections(read(SKILLS / "specwright-pr" / "SKILL.md"))["watch"]
        step = line_with(watch, r"^   - \*\*Version check\*\*", "watch: the **Version check** bullet in step 3")
        self.assertIn("release.sh check --main", step)
        self.assertRegex(step, r"release\.enabled")
        self.assertIn("--no-tags", step)
        self.assertRegex(step, r"(?i)before (it )?report")
        self.assertRegex(step, r"(?i)before (each|the) merge")
        self.assertRegex(step, r"(?is)refus[^.]*(neither|no)[^.]*ready")
        self.assertRegex(step, r"(?i)bump")
        self.assertLess(watch.index("3. Ready, per PR"), watch.index(step))
        self.assertLess(watch.index(step), watch.index("**Archive before merge:**"))
        merge = line_with(watch, r"^   - \*\*Merge:\*\*", "watch: the **Merge:** bullet")
        self.assertIn("**Version check**", merge)

    def test_release_only_after_cleanup(self):
        c, s = self.cleanup, self.step
        nxt = c.find("- **Next step**")
        self.assertNotEqual(nxt, -1, "Cleanup after merge lost its **Next step** bullet")
        self.assertLess(c.index(s), nxt, "the release step comes after **Next step**")
        self.assertLess(c.find("closed-check"), c.index(s), "the release step comes before the cleanup bullets")
        self.assertRegex(s, r"(?i)after an agent merge")
        self.assertRegex(s, r"(?is)cleanup (finished|is done|completed)")
        self.assertRegex(s, r"(?is)(stopped|stops)[^.]*\bpull\b|\bpull\b[^.]*(stopped|fail)")
        self.assertRegex(s, r"(?is)(no|neither|not)[^.]*(release|offer)")

    def test_offer_without_auto(self):
        s = self.step
        self.assertRegex(s, r"release\.enabled")
        self.assertRegex(s, r"release\.sh untagged")
        self.assertRegex(s, r"(?i)offer[^.]*specwright-release[^.]*publish|publish[^.]*offer")
        self.assertRegex(s, r"(?is)without `release\.auto`[^.]*no tag[^.]*until the user (accepts|says yes)|no tag[^.]*until the user (accepts|says yes)")

    def test_untagged_oldest_first(self):
        s = self.step
        self.assertRegex(s, r"(?i)oldest first")
        self.assertRegex(s, r"(?i)first failure")
        self.assertRegex(s, r"`release\.auto`")

    def test_publish_failure_reported(self):
        s = self.step
        self.assertRegex(s, r"(?is)publish failure[^.]*(merge|cleanup)[^.]*(undo|kept|stay|done)|(merge|cleanup)[^.]*(not undone|stay|stays|done)[^.]*publish")
        self.assertRegex(s, r"(?is)report[^.]*error")
        self.assertRegex(s, r"(?is)re-run[^.]*publish[^.]*resumes")


class TestShipText(unittest.TestCase):
    def setUp(self):
        text = read(SKILLS / "specwright-pr" / "SKILL.md")
        self.assertTrue(text)
        self.ship = sections(text)["ship"]

    def test_ship_checks_version_against_fetched_main_before_push(self):
        ship = self.ship
        step = line_with(ship, r"^   1\. .*release\.sh check --main", "ship: the version check item")
        self.assertRegex(step, r"release\.enabled")
        fetch = step.index("--no-tags")
        self.assertLess(fetch, step.index("check --main"), "the check comes before the fetch")
        self.assertRegex(step, r"(?is)refus[^.]*stop")
        self.assertRegex(step, r"(?i)bump")
        # the store is pushed first, so the code repo's check runs once, before either repo is validated or pushed
        self.assertRegex(step, r"(?i)once,? before either repo")
        validate = line_with(ship, r"^   2\. .*validate", "ship: the validate item")
        # every repo of the set runs its own validate, the store's included, before its push
        self.assertRegex(validate, r"(?i)each repo")
        self.assertIn("`planning_store.validate` in the store", validate)
        self.assertIn("`pr.validate` in the code repo", validate)
        self.assertLess(ship.index(step), ship.index(validate), "the check comes after validate")
        self.assertLess(ship.index(step), ship.index("Push each repo once its validate passed"), "the check comes after the push")


class TestVersionCheckOptIn(unittest.TestCase):
    def test_version_check_only_with_release_enabled(self):
        pr = read(SKILLS / "specwright-pr" / "SKILL.md")
        finish = read(SKILLS / "specwright-finish" / "SKILL.md")
        ship = sections(pr)["ship"]
        for name, line in (
            ("ship", next(l for l in ship.splitlines() if "check --main" in l)),
            ("watch", next(l for l in sections(pr)["watch"].splitlines() if "check --main" in l)),
            ("local merge", next(l for l in sections(finish)["local"].splitlines() if "check --main" in l)),
        ):
            self.assertRegex(line, r"(?i)(only )?with `release\.enabled` true", f"{name}: the check is not tied to release.enabled")
        # every mention of the check, in either skill, sits on a line that names release.enabled or points at the Version check
        for text in (pr, finish):
            for l in text.splitlines():
                if "check --main" in l:
                    self.assertTrue("release.enabled" in l, f"a check --main line without release.enabled: {l[:80]}")


class TestCloseText(unittest.TestCase):
    def setUp(self):
        text = read(SKILLS / "specwright-roadmap" / "SKILL.md")
        self.assertTrue(text)
        close = sections(text)["close"]
        m = re.search(r"^3b\. .*$", close, re.M)
        self.assertTrue(m, "roadmap close has no step 3b (releases)")
        self.step = m.group(0)
        self.close = close

    def test_offer_needs_yes_and_never_blocks(self):
        s = self.step
        self.assertRegex(s, r"release\.enabled")
        self.assertRegex(s, r"(?i)first-parent")
        self.assertRegex(s, r"(?i)no tag")
        self.assertRegex(s, r"(?i)oldest first")
        self.assertRegex(s, r"(?i)offer")
        self.assertRegex(s, r"(?is)(not|never) publish[^.]*without the user's yes|publish nothing without the user's yes")
        self.assertRegex(s, r"(?is)(refused|declined)[^.]*failed[^.]*(never|not)[^.]*block|(never|not)[^.]*block[^.]*close")
        # before the milestone is moved to Done, so a stop there cannot skip the close
        self.assertLess(self.close.index(s), self.close.index("\n4. Close on branch"))

    def test_disabled_no_offer(self):
        s = self.step
        self.assertRegex(s, r"(?i)only with `release\.enabled` true|`release\.enabled` (is )?(true|set)")
        self.assertRegex(s, r"(?is)(otherwise|disabled|false|off)[^.]*(no|not)[^.]*(version|release)|lists? no versions")


class TestSchemaText(unittest.TestCase):
    def test_tasks_instruction_requires_the_bump_task(self):
        text = read(ROOT / "schemas" / "specwright" / "schema.yaml")
        start = text.index("  - id: tasks")
        instruction = text[start:text.index("\n  - id:", start + 5) if "\n  - id:" in text[start + 5:] else len(text)]
        m = re.search(r"(?m)^\s*- [^\n]*release\.enabled[^\n]*(\n {8}[^ -][^\n]*)*", instruction)
        self.assertTrue(m, "the tasks instruction does not mention `release.enabled`")
        rule = m.group(0)
        rule = re.sub(r"\s+", " ", rule)
        self.assertIn("release.sh bump --to <version>", rule)
        self.assertRegex(rule, r"(?i)last task group")
        self.assertRegex(rule, r"release\.sh check")
        self.assertRegex(rule, r"(?is)(false|off|not enabled|disabled)[^.]*(no|not|without)[^.]*(bump )?task|no bump task")

    def _instruction(self, artifact):
        text = read(ROOT / "schemas" / "specwright" / "schema.yaml")
        start = text.index(f"  - id: {artifact}")
        nxt = text.find("\n  - id:", start + 5)
        return re.sub(r"\s+", " ", text[start:nxt if nxt != -1 else len(text)])

    def test_bump_task_rewrites_summary_and_checks_notes(self):
        rule = self._instruction("tasks")
        rule = rule[rule.index("release.enabled"):]
        self.assertRegex(rule, r"(?i)summary")
        self.assertRegex(rule, r"(?i)whole release")
        self.assertIn("release.sh notes --proposal", rule)
        apply = re.sub(r"\s+", " ", read(ROOT / "schemas" / "specwright" / "schema.yaml").split("\napply:")[1])
        self.assertIn("## Release Notes", apply)
        self.assertRegex(apply, r"(?i)own commit|same commit|task commit")
        self.assertIn("notes --proposal", apply)

    def test_proposal_instruction_asks_for_section_only_with_releases(self):
        ins = self._instruction("proposal")
        self.assertIn("## Release Notes", ins)
        self.assertRegex(ins, r"release\.enabled")
        self.assertRegex(ins, r"(?i)delete")
        self.assertIn("600", ins)
        self.assertIn("500", ins)
        for h in ("Added", "Changed", "Fixed", "Removed"):
            self.assertIn(f"### {h}", ins)
        self.assertRegex(ins, r"(?i)empty")
        self.assertIn("#123", ins)
        tpl = read(ROOT / "schemas" / "specwright" / "templates" / "proposal.md")
        self.assertIn("## Release Notes", tpl)
        self.assertRegex(tpl, r"release\.enabled: true")
        self.assertRegex(tpl, r"(?i)delete")

    def test_voiding_rule_exempts_release_notes_section(self):
        ins = self._instruction("review")
        voiding = re.search(r"A verdict covers only the contents reviewed:.{0,400}", ins).group(0)
        self.assertIn("Release Notes", voiding)
        tpl = read(ROOT / "schemas" / "specwright" / "templates" / "review.md")
        line = line_with(tpl, r"<!-- This verdict covers only", "review.md voiding comment")
        self.assertIn("Release Notes", line)

    def test_voiding_rule_still_voids_other_edits(self):
        ins = self._instruction("review")
        self.assertRegex(ins, r"editing proposal, specs or design for any other reason voids it")
        self.assertRegex(ins, r"(?i)outside (that|the) section")
        tpl = read(ROOT / "schemas" / "specwright" / "templates" / "review.md")
        line = line_with(tpl, r"<!-- This verdict covers only", "review.md voiding comment")
        self.assertRegex(line, r"Editing proposal, specs or design afterward")
        self.assertRegex(line, r"(?i)confined")


class TestBriefText(unittest.TestCase):
    def setUp(self):
        text = read(SKILLS / "specwright-review" / "references" / "brief.md")
        self.assertTrue(text)
        self.check = paragraph(text, r"^- \*\*Release Notes\*\*", "brief: the Release Notes check")

    def test_false_item_is_p1_docs(self):
        self.assertRegex(self.check, r"(?is)item[^.]*diff[^.]*not ship[^.]*P1[^.]*`docs`")

    def test_missing_item_is_p2_docs(self):
        self.assertRegex(self.check, r"(?is)user-visible[^.]*no item[^.]*P2[^.]*`docs`")

    def test_missing_section_is_p1_with_releases_on(self):
        self.assertRegex(self.check, r"release\.enabled")
        self.assertIn("openspec/specwright.yaml", self.check)
        self.assertRegex(self.check, r"(?is)missing[^.]*P1[^.]*`docs`")

    def test_format_break_is_p1_and_brief_states_the_rules(self):
        self.assertRegex(self.check, r"(?is)format[^.]*P1|P1[^.]*format")
        self.assertIn("600", self.check)
        self.assertIn("500", self.check)
        for h in ("Added", "Changed", "Fixed", "Removed"):
            self.assertIn(f"### {h}", self.check)

    def test_check_scoped_to_release_enabled(self):
        self.assertRegex(self.check, r"(?is)(releases? (are )?off|`release\.enabled` (is )?(false|not true)|otherwise)[^.]*(no finding|ignore)")


if __name__ == "__main__":
    unittest.main()
