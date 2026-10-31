"""A test skipped on some OSes only must say why: its reason names an issue (`#<number>`) or starts with `platform:`.

The scan reads every `test_*.py` under evals/ with the ast module. A skip counts as OS-dependent when its condition reads
`os.name`, `sys.platform` or `platform.system()`, directly or through a module-level name assigned from one of them:
`unittest.skipIf/skipUnless` (decorator or call), `self.skipTest(...)` and `raise unittest.SkipTest(...)` inside an `if`
whose condition reads one. Skips that depend on a tool or interpreter on PATH are outside the check.

Run: python -m unittest evals/runner/test_platform_skips.py
"""
import ast
import re
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent.parent
REASON = re.compile(r"#\d+|\Aplatform:")


def reads_platform(node, names):
    """Whether the expression reads os.name, sys.platform or platform.system, or a name known to."""
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            if (n.value.id, n.attr) in {("os", "name"), ("sys", "platform"), ("platform", "system")}:
                return True
        if isinstance(n, ast.Name) and n.id in names:
            return True
    return False


def platform_names(tree):
    """Module-level names assigned from an expression that reads the platform."""
    names = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and reads_platform(stmt.value, names):
            names.update(t.id for t in stmt.targets if isinstance(t, ast.Name))
    return names


def callee(call):
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""


def reason_ok(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and REASON.search(node.value) is not None


def check_tree(tree):
    """The line numbers of OS-dependent skips whose reason names no issue and has no `platform:` prefix."""
    names, bad = platform_names(tree), []

    def visit(node, conds):
        if isinstance(node, ast.Call):
            name, args = callee(node), node.args
            if name in ("skipIf", "skipUnless") and len(args) >= 2 and reads_platform(args[0], names):
                if not reason_ok(args[1]):
                    bad.append(node.lineno)
            elif name in ("skipTest", "SkipTest") and any(conds):
                if not (args and reason_ok(args[0])):
                    bad.append(node.lineno)
        if isinstance(node, ast.If):
            visit(node.test, conds)
            inner = conds + [reads_platform(node.test, names)]
            for child in node.body + node.orelse:
                visit(child, inner)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, conds)

    visit(tree, [])
    return sorted(bad)


def scan(root):
    """`<path>:<line>` for every offending skip in a test_*.py under root, paths relative to root."""
    found = []
    for path in sorted(Path(root).rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(root).as_posix()
        found.extend("%s:%d" % (rel, line) for line in check_tree(tree))
    return found


class PlatformSkips(unittest.TestCase):
    def scan_source(self, source):
        with tempfile.TemporaryDirectory(prefix="platform-skips-") as d:
            (Path(d) / "test_sample.py").write_text(source, encoding="utf-8")
            return scan(d)

    def test_os_skip_naming_an_issue_passes(self):
        src = ("import os, unittest\n"
               "class T(unittest.TestCase):\n"
               "    @unittest.skipIf(os.name == 'nt', 'fails on Windows, see #123')\n"
               "    def test_a(self):\n"
               "        pass\n")
        self.assertEqual(self.scan_source(src), [])

    def test_platform_prefixed_skip_passes(self):
        src = ("import os, unittest\n"
               "class T(unittest.TestCase):\n"
               "    @unittest.skipUnless(os.name == 'nt', 'platform: job objects are Windows only')\n"
               "    def test_a(self):\n"
               "        pass\n")
        self.assertEqual(self.scan_source(src), [])

    def test_os_skip_with_neither_is_named(self):
        src = ("import os, unittest\n"
               "class T(unittest.TestCase):\n"
               "    @unittest.skipIf(\n"
               "        os.name == 'nt',\n"
               "        'does not work here')\n"
               "    def test_a(self):\n"
               "        pass\n")
        self.assertEqual(self.scan_source(src), ["test_sample.py:3"])

    def test_skiptest_inside_os_branch_is_named(self):
        src = ("import sys, unittest\n"
               "class T(unittest.TestCase):\n"
               "    def test_a(self):\n"
               "        if sys.platform == 'win32':\n"
               "            self.skipTest('does not work here')\n"
               "        if sys.platform == 'win32':\n"
               "            self.skipTest('platform: fine')\n")
        self.assertEqual(self.scan_source(src), ["test_sample.py:5"])

    def test_tool_skips_are_outside_the_check(self):
        src = ("import shutil, unittest\n"
               "class T(unittest.TestCase):\n"
               "    @unittest.skipUnless(shutil.which('bash'), 'needs bash')\n"
               "    def test_a(self):\n"
               "        pass\n"
               "    def test_b(self):\n"
               "        if not shutil.which('jq'):\n"
               "            self.skipTest('no jq')\n")
        self.assertEqual(self.scan_source(src), [])

    def test_repo_skips_pass(self):
        self.assertEqual(scan(EVALS), [], "OS-dependent skips need `#<issue>` or a `platform:` prefix in the reason")


if __name__ == "__main__":
    unittest.main()
