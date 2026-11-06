"""The README install prompt's Step 8 warns about a missing `sw` only when the install needs one (native-cli-vcs D5).

The prompt is run by an agent, so these are mechanical checks of the conditional warning wording in Step 8, not runs of an
install, in the style of test_instructions.py.

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


class TestInstallSwWarning(unittest.TestCase):
    def test_main_without_binary_warns(self):
        s8 = step8()
        self.assertRegex(s8, r"(?i)resolver finds no matching `?sw`? binary", "Step 8 does not condition the warning on the resolver")
        self.assertRegex(s8, r"(?i)0\.25\.0 or newer", "Step 8 does not condition the warning on the installed version")
        self.assertIn("sw_missing", s8)
        self.assertRegex(s8, r"(?i)a tagged install", "Step 8 does not name a tagged install")
        self.assertRegex(s8, r"CONTRIBUTING\.md", "Step 8 does not name the CONTRIBUTING.md bootstrap")
        self.assertIn("sw not installed: main has no release binaries", step8(), "the main line the warning follows is gone")

    def test_matching_binary_gets_no_warning(self):
        self.assertRegex(step8(), r"(?i)matching (`sw`|binary) already placed.{0,160}no warning")

    def test_older_tag_gets_no_warning(self):
        self.assertRegex(step8(), r"(?i)older than 0\.25\.0.{0,160}no warning")

    def test_tagged_install_gets_no_warning(self):
        self.assertRegex(step8(), r"(?i)`sw-install` (returned|reports) installed, replaced or kept.{0,80}no warning")


if __name__ == "__main__":
    unittest.main()
