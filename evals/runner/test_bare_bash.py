"""No eval starts bash by its bare name: on Windows, CreateProcess looks in System32 before PATH, so a bare `"bash"` runs
the WSL launcher instead of Git Bash. Evals start bash through `bashexe.bash()`.

The scan reads every `*.py` under evals/ with the ast module and flags each list or tuple display whose first element is
the string constant `"bash"`, wherever it appears, so an argv held in a variable or handed to a helper is caught too. A
display that is never started (an expected argv, a payload) is exempt only with `# bare-bash: not started` on its line.

Run: python -m unittest evals/runner/test_bare_bash.py
"""
import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EVALS))
import bashexe  # noqa: E402
MARKER = "# bare-bash: not started"


def check_source(source, filename="<source>"):
    """The line numbers of unmarked list/tuple displays that start with the constant "bash"."""
    lines = source.splitlines()
    bad = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
            first = node.elts[0]
            if isinstance(first, ast.Constant) and first.value == "bash" and MARKER not in lines[node.lineno - 1]:
                bad.append(node.lineno)
    return sorted(bad)


def scan(root):
    """`<path>:<line>` for every bare-bash display in a *.py under root, paths relative to root."""
    found = []
    for path in sorted(Path(root).rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        found.extend("%s:%d" % (rel, line) for line in check_source(path.read_text(encoding="utf-8"), str(path)))
    return found


class BareBash(unittest.TestCase):
    def scan_source(self, source):
        with tempfile.TemporaryDirectory(prefix="bare-bash-") as d:
            (Path(d) / "sample.py").write_text(source, encoding="utf-8")
            return scan(d)

    def test_bare_bash_call_is_named(self):
        cases = {
            "an inline call": ("import subprocess\nsubprocess.run(['bash', 'x.sh'])\n", ["sample.py:2"]),
            "an argv in a variable": ("import subprocess\nargs = [\"bash\", 'x.sh']\nsubprocess.run(args)\n",
                                      ["sample.py:2"]),
            "an argv handed to a helper": ("def go(cwd, argv):\n    pass\ngo('.', ('bash', '-c', 'true'))\n",
                                           ["sample.py:3"]),
            "an unmarked expected value": ("expected = ['bash', 'x.sh']\n", ["sample.py:1"]),
            "a marked expected value": ("expected = ['bash', 'x.sh']  %s\n" % MARKER, []),
            "a resolved bash": ("import subprocess, bashexe\nsubprocess.run([bashexe.bash(), 'x.sh'])\n", []),
            "bash later in the list": ("argv = ['env', 'bash']\n", []),
        }
        for name, (source, want) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.scan_source(source), want)

    def test_resolved_bash_keeps_the_callers_path_first(self):
        """Git for Windows' bin/bash.exe is a launcher that puts /mingw64/bin and /usr/bin before the caller's PATH, which
        hides every shim a test puts first; bashexe.bash() must be a bash that leaves PATH as it was given."""
        bash = bashexe.bash()
        if not bash:
            self.skipTest("needs bash")
        with tempfile.TemporaryDirectory(prefix="bare-bash-path-") as d:
            env = dict(os.environ, PATH=d + os.pathsep + os.environ.get("PATH", ""))
            first = subprocess.run([bash, "-c", 'printf %s "${PATH%%:*}"'], env=env, capture_output=True, text=True)
            want = subprocess.run([bash, "-c", 'cd "$1" && pwd', "x", d], capture_output=True, text=True)
        self.assertEqual(first.stdout, want.stdout.strip(), "the caller's first PATH entry must stay first")

    def test_repo_has_no_bare_bash(self):
        self.assertEqual(scan(EVALS), [], "start bash through bashexe.bash(), or mark a value that is never started "
                                          "with `%s`" % MARKER)


if __name__ == "__main__":
    unittest.main()
