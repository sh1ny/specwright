"""The agent instructions and CONTRIBUTING.md say which suites to run when (targeted-eval-runs).

AGENTS.md and CONTRIBUTING.md each name the targeted command, the CI workflow and the milestone close;
CLAUDE.md imports AGENTS.md. A missing rule names the file.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

COMMAND = "python evals/run.py --changed main"
WORKFLOW = ".github/workflows/evals.yml"
MILESTONE = "milestone close"
IMPORT_LINE = "@AGENTS.md"
RULE_FILES = ("AGENTS.md", "CONTRIBUTING.md")
RULES = ((COMMAND, "the targeted command"), (WORKFLOW, "the CI workflow"), (MILESTONE, "the milestone close"))


def problems(root):
    """Each rule a file under `root` lacks, as a message that names the file."""
    out = []
    for name in RULE_FILES:
        path = Path(root) / name
        if not path.is_file():
            out.append(f"{name} does not exist")
            continue
        text = path.read_text(encoding="utf-8")
        for needle, what in RULES:
            if needle not in text:
                out.append(f"{name} does not name {what} (`{needle}`)")
    path = Path(root) / "CLAUDE.md"
    if not path.is_file():
        out.append("CLAUDE.md does not exist")
    elif IMPORT_LINE not in path.read_text(encoding="utf-8").splitlines():
        out.append(f"CLAUDE.md does not hold the line `{IMPORT_LINE}`")
    return out


class TestAgentInstructions(unittest.TestCase):
    def test_agents_and_contributing_carry_the_rule(self):
        self.assertEqual(problems(ROOT), [])

    def test_a_file_without_the_rule_is_named(self):
        for name in (*RULE_FILES, "CLAUDE.md"):
            self.assertTrue((ROOT / name).is_file(), f"{name} does not exist")
        cases = (
            ("CONTRIBUTING.md", COMMAND, "--changed"),
            ("CONTRIBUTING.md", WORKFLOW, "the workflow"),
            ("AGENTS.md", MILESTONE, "the close"),
            ("CLAUDE.md", IMPORT_LINE, "# nothing"),
        )
        for name, needle, repl in cases:
            with self.subTest(file=name, dropped=needle), tempfile.TemporaryDirectory() as tmp:
                for f in (*RULE_FILES, "CLAUDE.md"):
                    shutil.copy(ROOT / f, Path(tmp) / f)
                path = Path(tmp) / name
                text = path.read_text(encoding="utf-8")
                self.assertIn(needle, text)
                path.write_text(text.replace(needle, repl), encoding="utf-8")
                found = problems(tmp)
                self.assertTrue(found, f"dropping {needle!r} from {name} was not caught")
                self.assertTrue(all(p.startswith(name) for p in found), found)


if __name__ == "__main__":
    unittest.main()
