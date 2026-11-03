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
