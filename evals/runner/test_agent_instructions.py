"""The agent instructions and CONTRIBUTING.md say CI runs the suites, not the contributor (ci-os-matrix).

AGENTS.md and CONTRIBUTING.md each name the CI workflow, the single-module run, the map test and the
milestone close; CLAUDE.md imports AGENTS.md. A missing rule names the file. AGENTS.md, CONTRIBUTING.md
and README.md never tell the reader to run a whole suite locally.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SINGLE_MODULE = "python -m unittest evals/<suite>/test_"
MAP_TEST = "evals/runner/test_suite_map.py"
WORKFLOW = ".github/workflows/evals.yml"
MILESTONE = "milestone close"
IMPORT_LINE = "@AGENTS.md"
RULE_FILES = ("AGENTS.md", "CONTRIBUTING.md")
RULES = (
    (WORKFLOW, "the CI workflow"),
    (SINGLE_MODULE, "the single-module run"),
    (MAP_TEST, "the map test"),
    (MILESTONE, "the milestone close"),
)
LOCAL_RUN_FILES = ("AGENTS.md", "CONTRIBUTING.md", "README.md")
LOCAL_RUNS = ("python evals/run.py --changed main", "python -m unittest discover evals/")


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


def local_runs(root):
    """Each whole-suite local run a file under `root` tells the reader to make, naming file and command."""
    out = []
    for name in LOCAL_RUN_FILES:
        path = Path(root) / name
        if not path.is_file():
            out.append(f"{name} does not exist")
            continue
        text = path.read_text(encoding="utf-8")
        for command in LOCAL_RUNS:
            if command in text:
                out.append(f"{name} tells the reader to run `{command}`")
    return out


class TestAgentInstructions(unittest.TestCase):
    def test_agents_and_contributing_carry_the_rule(self):
        self.assertEqual(problems(ROOT), [])

    def test_a_file_without_the_rule_is_named(self):
        for name in (*RULE_FILES, "CLAUDE.md"):
            self.assertTrue((ROOT / name).is_file(), f"{name} does not exist")
        cases = (
            ("CONTRIBUTING.md", MAP_TEST, "the map test"),
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

    def test_a_local_suite_run_is_named(self):
        self.assertEqual(local_runs(ROOT), [])
        for name in LOCAL_RUN_FILES:
            for command in LOCAL_RUNS:
                with self.subTest(file=name, command=command), tempfile.TemporaryDirectory() as tmp:
                    for f in LOCAL_RUN_FILES:
                        shutil.copy(ROOT / f, Path(tmp) / f)
                    path = Path(tmp) / name
                    path.write_text(path.read_text(encoding="utf-8") + f"\nRun `{command}pr-pair`.\n", encoding="utf-8")
                    found = local_runs(tmp)
                    self.assertEqual(len(found), 1, found)
                    self.assertTrue(found[0].startswith(name) and command in found[0], found)


if __name__ == "__main__":
    unittest.main()
