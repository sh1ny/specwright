"""The README install prompt's Steps 4, 6, 7 and 8 say what the spec-wording-sweep scenarios say (issue #242).

The prompt is run by an agent, so these are mechanical checks of the load-bearing wording of Steps 4, 6 and 7 on
normalised whitespace, in the style of test_instructions.py: where a rule sits and its key terms, not whole sentences.

Run: python -m unittest evals/git-workflow/test_install_prompt_242.py
"""
import re
import unittest
from pathlib import Path

README = Path(__file__).resolve().parents[2] / "README.md"


def step(label):
    """`Step N - ...` paragraph of the README install prompt up to the next step, whitespace normalised."""
    text = README.read_text(encoding="utf-8")
    m = re.search(r"^" + label + r"\b.*?(?=^Step \d+ |^```)", text, re.M | re.S)
    assert m, f"README install prompt has no {label}"
    return " ".join(m.group(0).split())


class Step6Settings(unittest.TestCase):
    def setUp(self):
        self.s6 = step("Step 6")

    def test_step6_version_files_entries_are_user_data(self):
        self.assertRegex(self.s6, r"(?is)`release\.version_files\.`.{0,200}user data|user data.{0,200}`release\.version_files\.`",
                         "Step 6 does not treat the entries under release.version_files. as user data")
        self.assertRegex(self.s6, r"(?is)never compared, added.{0,100}listed as removed.{0,150}in order",
                         "Step 6 does not say entries are never compared, added or listed as removed, and kept in order")

    def test_step6_offers_version_files_mapping_whole(self):
        self.assertRegex(self.s6, r"(?is)`release\.version_files`.{0,200}compared.{0,300}whole mapping.{0,120}in order.{0,200}decline",
                         "Step 6 does not offer an absent release.version_files as the template's whole mapping, in order, to keep or decline")
        self.assertRegex(self.s6, r"(?is)When the user's file lacks it and the template sets it, offer the template's whole mapping, in order, as one default, and list it as added when the user keeps it",
                         "Step 6 does not add a kept release.version_files mapping and list it as added")

    def test_step6_keeps_comments_of_kept_keys(self):
        self.assertRegex(self.s6, r"(?is)keeps the user's values and the comments of every key it keeps",
                         "Step 6 does not say the merge keeps the user's values and the comments of kept keys")
        self.assertRegex(self.s6, r"(?is)never rewrites, adds or removes a comment on a key",
                         "Step 6 does not say the merge never rewrites, adds or removes a comment on a kept key")

    def test_step6_copies_comment_for_accepted_key(self):
        self.assertRegex(self.s6, r"(?is)copies the template's comment only with a key it adds.{0,80}accept",
                         "Step 6 does not say the template's comment is copied only with an added key the user accepts")

    def test_step6_obsolete_key_needs_consent(self):
        self.assertRegex(self.s6, r"(?is)no longer has.{0,120}ask before removing", "Step 6 no longer asks before removing a key")
        self.assertRegex(self.s6, r"(?is)consent.{0,80}take its comment",
                         "Step 6 does not say a key removed with consent may take its comment")
        self.assertRegex(self.s6, r"(?is)declines.{0,120}key and its comment stay.{0,120}neither as added nor as removed",
                         "Step 6 does not say a declined removal leaves the key and its comment, listed as neither added nor removed")


class Step7SkillsAndKeys(unittest.TestCase):
    def setUp(self):
        self.s7 = step("Step 7")

    def test_step7_key_check_skips_version_files_entries(self):
        self.assertRegex(self.s7, r"(?is)(skip|do not check|never check).{0,200}`release\.version_files\.`",
                         "Step 7's key check does not skip the entries under release.version_files.")
        self.assertRegex(self.s7, r"(?is)`release\.version_files`.{0,40}like any (other |compared )?key",
                         "Step 7's key check does not check release.version_files itself like any key")

    def test_step7_passes_declined_version_files(self):
        self.assertRegex(self.s7, r"(?is)chose otherwise in Step 6.{0,200}declined.{0,100}passes",
                         "Step 7 does not pass a template default the user declined in Step 6")
        self.assertRegex(step("Step 6"), r"(?is)The user may keep or decline it; a declined mapping is not written\.",
                         "Step 6 may write a release.version_files mapping the user declined")

    def test_step7_skills_check_ignores_other_directories(self):
        self.assertRegex(self.s7, r"(?is)other directories.{0,160}`openspec-\*`.{0,160}do not count",
                         "Step 7's skills check counts directories that are not Specwright's")

    def test_step7_skills_check_fails_on_extra_file(self):
        self.assertRegex(self.s7, r"(?is)with a downloaded counterpart.{0,80}no extra file.{0,120}fails.{0,40}naming",
                         "Step 7's skills check does not fail, naming it, on an extra file in a Specwright directory")

    def test_step7_kept_orphan_passes(self):
        self.assertRegex(self.s7, r"(?is)orphan.{0,80}passes.{0,60}kept it in Step 4.{0,100}Step 8.{0,40}(reports|lists)",
                         "Step 7 does not pass an orphan the user kept, reported by Step 8")

    def test_step7_approved_orphan_still_present_blocks_stamp(self):
        self.assertRegex(self.s7, r"(?is)agreed.{0,40}to remove.{0,100}still (there|present).{0,60}fails.{0,60}naming.{0,100}no stamp",
                         "Step 7 does not fail, naming it, on an approved orphan that is still there, with no stamp")

    def test_update_completes_allows_kept_orphans(self):
        self.assertRegex(self.s7, r"(?is)no other `specwright-\*` directory than the downloaded ones and the orphans the user kept",
                         "Step 7 does not allow exactly the downloaded directories plus the orphans the user kept")


class Step4Orphans(unittest.TestCase):
    def test_step4_resume_removes_orphan_before_step5(self):
        s4 = step("Step 4")
        self.assertRegex(s4, r"(?is)orphan skills.{0,400}after a new `swap`.{0,200}completed swap.{0,200}confirmed",
                         "Step 4 does not ask about orphans after a new swap and after a confirmed completed swap")
        self.assertRegex(s4, r"(?is)orphan skills.{0,100}before Step 5", "Step 4 does not settle orphans before Step 5")
        self.assertRegex(s4, r"(?is)after a new `swap` and on a rerun whose plan shows a completed swap \(once that swap is confirmed, as above\)\. Remove only those the user agrees to remove\.",
                         "Step 4 does not remove the orphans the user agrees to remove on both swap paths, and only those")
        self.assertRegex(s4, r"(?is)other `orphans` entries \(agent files, pack skills\).{0,60}ask before removing them.{0,60}remove only those the user agrees to",
                         "Step 4 drops the consent path for agent-file and pack-skill orphans")
        self.assertRegex(s4, r"(?is)skip `stage` and `swap`.{0,120}orphan question.{0,80}Steps 5-7",
                         "Step 4's resume of a finished swap does not go through the orphan question first")
        self.assertRegex(step("Step 7"), r"(?is)rerun this prompt.{0,60}orphan question.{0,40}Steps 5-7",
                         "Step 7's rerun does not go through Step 4's orphan question first")

    def test_step4_resume_kept_orphan_reported(self):
        self.assertRegex(step("Step 4"), r"(?is)declined orphan stays.{0,100}Step 7.{0,100}Step 8 lists it as an orphan kept",
                         "Step 4 does not keep a declined orphan, passing Step 7 and listed by Step 8")


class Step8Interface(unittest.TestCase):
    def test_step8_interface_is_the_standalone_line(self):
        s8 = step("Step 8")
        self.assertRegex(s8, r"(?is)`interface <n>` line in the installed `specwright-pr/SKILL\.md`: the line that holds only `interface <n>` and nothing else",
                         "Step 8 does not say the interface is the line holding only `interface <n>`")
        self.assertRegex(s8, r"(?is)a sentence that mentions an interface inside a paragraph is not that line",
                         "Step 8 does not say a paragraph naming an interface is not the interface line")


if __name__ == "__main__":
    unittest.main()
