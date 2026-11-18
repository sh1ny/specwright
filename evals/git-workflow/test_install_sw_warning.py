"""The README install prompt's Step 8 warns about a missing `sw` only when the install needs one (native-cli-vcs D5, native-cli-update D10).

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
        self.assertRegex(s8, r"(?i)<installed VERSION>/sw", "Step 8 does not check the placed binary of the installed version")
        self.assertRegex(s8, r"(?i)by hand \(no script\)", "Step 8 runs the resolver script, which needs bash")
        self.assertNotRegex(s8, r"(?i)\bbash\b|sw-path", "Step 8 still names bash or the resolver script")
        self.assertIn("sw_missing", s8)
        self.assertRegex(s8, r"(?i)a tagged install", "Step 8 does not name a tagged install")
        self.assertRegex(s8, r"CONTRIBUTING\.md", "Step 8 does not name the CONTRIBUTING.md bootstrap")
        self.assertIn("`sw built from main`", step8(), "the main line the warning follows is gone")

    def test_matching_binary_gets_no_warning(self):
        self.assertRegex(step8(), r"(?i)matching (`sw`|binary) already placed.{0,160}no warning")

    def test_older_tag_gets_no_warning(self):
        # a ref below the minimum release is stopped in Step 3, before any write, so Step 8 never runs for it
        self.assertRegex(step8(), r"(?i)older than 0\.37\.0.{0,160}no warning")
        self.assertNotRegex(step8(), r"0\.25\.0", "Step 8 still conditions the warning on 0.25.0")

    def test_tagged_install_gets_no_warning(self):
        self.assertRegex(step8(), r"(?i)`sw-install` (returned|reports) installed, replaced or kept.{0,80}no warning")


if __name__ == "__main__":
    unittest.main()
