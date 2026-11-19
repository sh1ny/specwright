"""No eval names a removed script, the shipped scripts directory or a frozen oracle checkout (native-cli-retire-scripts D14, task 7.1;
eval-runner "Frozen-oracle evals are migrated before the cutover").

The check reads the code files under evals/ (`.py`, `.sh`, `.mjs`, `.js`, `.ps1`) and starts nothing. Fixture data (`.json`, `.md`) and
the suite map are not code an eval runs. It fails, listing every file and what it names, when an eval:

  - names one of the twelve removed scripts or a `bounded.py`, as a string literal (`"vcs.sh"`, `"scripts/as.sh"`), in a `.py` file;
    in a shell, JavaScript or PowerShell file, as a word;
  - names the shipped scripts directory: a string literal such as `skills/specwright-pr/scripts`, or a file that builds the path
    from the literals `"skills"` and `"scripts"`;
  - names a frozen oracle checkout: the variables `ORACLE_SW_DIR` and `ORACLE_FIN_DIR` the frozen scripts read, or a script or
    `reviewers.py` file kept under an `oracle/` directory (the records under `oracle/records/` and the helpers that read them are fine).

Comments and docstrings are prose and are not read: a sentence may say what the script used to do. After the cutover nothing under
evals/ may run a removed script, so an eval that still does is migrated, or deleted when it only tested the script (task 7.6).

Run: python -m unittest evals/runner/test_oracle_migration.py
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "evals"
SELF = Path(__file__).resolve()

REMOVED = ["vcs.sh", "as.sh", "pr-pair.sh", "pr-snapshot.sh", "pr-reply.sh", "sw-path.sh", "task-cover.sh", "fit-subject.sh",
           "finish.sh", "review-run.sh", "release.sh", "update.sh", "bounded.py"]
NAME = re.compile(r"(?<![\w.-])(" + "|".join(re.escape(n) for n in REMOVED) + r")(?![\w-])")
SCRIPTS_DIR = re.compile(r"(?:^|[\\/])skills[\\/][^\s\"']*[\\/]scripts(?:$|[\\/\s\"'])")
ORACLE_VARIABLE = re.compile(r"\bORACLE_(?:SW|FIN)_DIR\b")
CODE = {".py", ".sh", ".mjs", ".js", ".ps1"}
SKIPPED_DIRS = {"__pycache__", "records"}
FROZEN_FILE = re.compile(r"\.sh$|^reviewers\.py$")
MAX_BYTES = 2_000_000


def docstrings(tree):
    """The ids of the string nodes that are docstrings."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def python_findings(text):
    """What a Python file names in its string literals (docstrings and comments are not read)."""
    tree = ast.parse(text)
    prose = docstrings(tree)
    literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in prose]
    found = set()
    for value in literals:
        found.update(f"script {m}" for m in NAME.findall(value))
        if SCRIPTS_DIR.search(value):
            found.add("the scripts directory")
        if ORACLE_VARIABLE.search(value):
            found.add("a frozen oracle checkout")
    if "skills" in literals and "scripts" in literals:
        found.add("the scripts directory")
    return found


def text_findings(text):
    found = {f"script {m}" for m in NAME.findall(text)}
    if SCRIPTS_DIR.search(text):
        found.add("the scripts directory")
    if ORACLE_VARIABLE.search(text):
        found.add("a frozen oracle checkout")
    return found


def scan(root=EVALS):
    """{path relative to the repo: sorted names} of every eval file that names something removed."""
    out = {}
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or path.resolve() == SELF or SKIPPED_DIRS & set(relative.parts[:-1]):
            continue
        if path.suffix not in CODE:
            continue
        found = set()
        if "oracle" in relative.parts[:-1] and FROZEN_FILE.search(path.name):
            found.add("a frozen oracle checkout")
        if path.stat().st_size <= MAX_BYTES:
            try:
                text = path.read_bytes().decode("utf-8")
                found |= python_findings(text) if path.suffix == ".py" else text_findings(text)
            except (UnicodeDecodeError, SyntaxError):
                pass
        if found:
            out[(Path(root) / relative).relative_to(ROOT).as_posix()] = sorted(found)
    return out


class OracleMigration(unittest.TestCase):
    def test_eval_naming_a_removed_script_fails(self):
        found = scan()
        listing = "\n".join(f"  {path}: {', '.join(names)}" for path, names in found.items())
        self.assertEqual(found, {}, f"{len(found)} eval files name a removed script, the scripts directory or a frozen oracle:\n{listing}")

    def test_the_check_names_each_kind(self):
        """The scan reads literals, not prose, and names each kind it looks for."""
        self.assertEqual(python_findings('x = ROOT / "skills" / "specwright-pr" / "scripts" / "pr-pair.sh"'),
                         {"the scripts directory", "script pr-pair.sh"})
        self.assertEqual(python_findings('x = "skills/*/scripts/bounded.py"'), {"the scripts directory", "script bounded.py"})
        self.assertEqual(python_findings('e["ORACLE_SW_DIR"] = d'), {"a frozen oracle checkout"})
        self.assertEqual(python_findings('"""vcs.sh used to run here."""\n# as.sh\nx = "bias.sh"'), set())
        self.assertEqual(python_findings('x = "sw vcs"'), set())
        self.assertEqual(text_findings("run vcs.sh now"), {"script vcs.sh"})


if __name__ == "__main__":
    unittest.main()
