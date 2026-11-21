"""The README install prompt's Step 8 warns about a `sw` that cannot serve the installed skills (native-cli-retire-scripts D13, native-cli-update D10).

The prompt is run by an agent, so these are mechanical checks of the conditional check and warning wording in Step 8, not
runs of an install, in the style of test_instructions.py. The check needs exit 0 within 10 seconds, the installed
version, and the interface the installed skills require: the `interface` line of the installed `specwright-pr/SKILL.md`,
or `SW_INTERFACE=` in `scripts/sw-path.sh` for a tag whose skills carry no such line.

Run: python -m unittest discover evals/git-workflow -p "test_install_sw_warning.py"
"""
import re
import unittest
from pathlib import Path

README = Path(__file__).resolve().parents[2] / "README.md"


def step8():
    text = README.read_text(encoding="utf-8")
    start = text.index("Step 8 - Report briefly")
    return " ".join(text[start:text.index("\n```", start)].split())


def check():
    """The sentences from the check through its warning rules, up to the OpenSpec line."""
    s8 = step8()
    return s8[s8.index("Then check whether the installed skills can run"):s8.index("Report the OpenSpec version")]


class TestInstallSwWarning(unittest.TestCase):
    def test_check_needs_exit_0_in_10_seconds_version_and_interface(self):
        c = check()
        self.assertRegex(c, r"(?i)<installed VERSION>/sw", "Step 8 does not check the placed binary of the installed version")
        self.assertRegex(c, r"(?i)`version --json`.{0,40}10-second timeout.{0,40}exit 0", "the check has no 10-second exit 0")
        self.assertRegex(c, r"(?i)one JSON object", "the check does not require one JSON object")
        self.assertRegex(c, r"(?i)report the installed `VERSION`", "the check does not compare the installed version")
        self.assertRegex(c, r"(?i)interface the installed skills require", "the check does not compare the interface")
        self.assertRegex(c, r"(?i)`interface <n>` line in the installed `specwright-pr/SKILL\.md`",
                         "the interface is not read from the installed specwright-pr skill")
        self.assertRegex(c, r"`SW_INTERFACE=`.{0,80}`scripts/sw-path\.sh`", "the older-tag interface source is missing")
        self.assertNotRegex(c, r"(?i)\bbash\b|by hand|resolver", "the check still runs a script or a resolver")

    def test_old_interface_binary_warns(self):
        c = check()
        self.assertRegex(c, r"(?i)interface differs", "a binary with another interface is not a warning")
        self.assertIn("sw_mismatch", c)
        self.assertRegex(c, r"(?i)not ready", "a failed check does not stop the install being reported ready")

    def test_main_without_binary_warns(self):
        c = check()
        self.assertRegex(c, r"(?i)file is missing", "a missing binary is not a warning")
        self.assertRegex(c, r"(?i)`main` install whose build was removed", "the main install case is not named")
        self.assertRegex(c, r"(?i)a tagged install", "Step 8 does not name a tagged install")
        self.assertRegex(c, r"CONTRIBUTING\.md", "Step 8 does not name the CONTRIBUTING.md bootstrap")
        self.assertIn("`sw built from main`", step8(), "the main line the warning follows is gone")

    def test_other_version_binary_warns(self):
        c = check()
        self.assertRegex(c, r"(?i)version or the interface differs", "another version's binary is not a warning")
        self.assertRegex(c, r"(?i)another version's `sw` never serves the project", "another version's binary may serve")

    def test_tagged_install_removed_binary_warns(self):
        # a tag install whose sw-install said installed/replaced/kept still warns when the check then fails
        self.assertRegex(check(), r"(?i)`sw-install` returned installed,\s*replaced or kept,\s*with the check passing,\s*gets no warning")

    def test_matching_binary_gets_no_warning(self):
        self.assertRegex(check(), r"(?i)matching (`sw`|binary) already placed.{0,160}no warning")

    def test_v0_37_0_tag_interface_1_gets_no_warning(self):
        # the v0.37.0 tag's skills require interface 1 through sw-path.sh and its binary reports 1: the comparison is
        # against what the installed skills require, never a fixed number
        c = check()
        self.assertNotRegex(c, r"(?i)interface 3\b", "the check hard-codes the current interface")
        self.assertRegex(c, r"(?i)differs", "the check does not compare against the installed skills' interface")

    def test_older_tag_gets_no_warning(self):
        # a ref below the minimum release is stopped in Step 3, before any write, so Step 8 never runs for it
        self.assertRegex(step8(), r"(?i)older than 0\.37\.0.{0,160}no warning")
        self.assertNotRegex(step8(), r"0\.25\.0", "Step 8 still conditions the warning on 0.25.0")

    def test_tagged_install_gets_no_warning(self):
        self.assertRegex(step8(), r"(?i)`sw-install` returned installed,\s*replaced or kept.{0,80}no warning")


if __name__ == "__main__":
    unittest.main()
