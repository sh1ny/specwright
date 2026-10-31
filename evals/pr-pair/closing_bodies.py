"""Every PR body the closing tests send to the renderer, collected from the test source.

The closing tests (`ClosingCheck`, `ClosedCheck`, `ClosingRendered` in test_pr_pair.py) seed a PR body through `self.seed(body, ...)`
or `self.intended(body, ...)`. The recorder (record_markdown.py) renders each of these through the real `POST /markdown`, and the
coverage test (`ClosingRecordings`) checks each has a recording, so a new test cannot silently lack one. A body must be a string
literal as the call's first argument: a computed body is refused rather than missed.
"""
import ast
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
FINISH_FIXTURES = HERE.parent / "git-workflow" / "fixtures.py"
TEST_FILE = HERE / "test_pr_pair.py"
CLASSES = ("ClosingCheck", "ClosedCheck", "ClosingRendered")
SEEDERS = ("seed", "intended")
MODE, CONTEXT = "gfm", "sh1ny/specwright"
FIXTURE = HERE / "fixtures" / "markdown.json"


def literal(node):
    """The str a Constant node holds, else None. Adjacent literals are one Constant; a `(...)` group adds no node."""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def collect_bodies(path=TEST_FILE):
    """The distinct bodies of the closing tests, in source order. A body is a string literal, or a local name last assigned a
    string literal before the call."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    bodies = []
    for cls in tree.body:
        if not (isinstance(cls, ast.ClassDef) and cls.name in CLASSES):
            continue
        for fn in (f for f in ast.walk(cls) if isinstance(f, ast.FunctionDef) and f.name not in SEEDERS):  # helpers pass `body` on
            assigned = sorted(((n.lineno, t.id, literal(n.value)) for n in ast.walk(fn) if isinstance(n, ast.Assign)
                               for t in n.targets if isinstance(t, ast.Name)), key=lambda x: x[0])
            calls = sorted((n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                            and n.func.attr in SEEDERS and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"
                            and n.args), key=lambda n: n.lineno)
            for call in calls:
                first = call.args[0]
                text = literal(first)
                if text is None and isinstance(first, ast.Name):
                    text = next((v for ln, name, v in reversed(assigned) if name == first.id and ln < call.lineno), None)
                if text is None:
                    raise ValueError(f"{cls.name}.{fn.name} line {call.lineno}: the PR body passed to self.{call.func.attr}() "
                                     "must be a string literal or a local name assigned one")
                if text not in bodies:
                    bodies.append(text)
    for text in finish_fixture_bodies():
        if text not in bodies:
            bodies.append(text)
    return bodies


def finish_fixture_bodies():
    """The merged-PR bodies the git-workflow finish fixtures seed (fixtures.MERGED_PR_BODIES), loaded by path."""
    spec = importlib.util.spec_from_file_location("gw_fixtures", FINISH_FIXTURES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.MERGED_PR_BODIES)
