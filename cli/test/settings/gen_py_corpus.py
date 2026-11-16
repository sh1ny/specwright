"""Dumps the settings texts of the Python evals as JSON, for cli/test/settings/reader_corpus_test.dart (task 2.6 of
`native-cli-yaml-settings`). Throwaway evidence tooling: deleted with the experiment. Its output is never committed.

usage: python -I gen_py_corpus.py <repo root> <output json>

Three sources, each entry carries `source` and `kind`:
  literal  a string expression under evals/ that evaluates to a YAML mapping whose first key is a settings key
  interp   the same, built with an f-string whose unresolved parts became `X`
  helper   the output of a settings-writing helper called over the argument combinations the tests use
Also writes `omitted`: every expression that holds a `key:` literal part but could not be evaluated, by file:line.
"""
import ast
import importlib.util
import itertools
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
out_path = Path(sys.argv[2])
YAMLISH = re.compile(r"""^(?:[ \t]*(?:#[^\n]*)?\n)*[ \t]*(?:[A-Za-z_][\w. \-]*|"[^"\n]*"|'[^'\n]*'):(?:[ \t]|\n|$)""")

TOP = set(re.findall(r"^#?\s?([a-z_]+):", (root / "templates/openspec/specwright.yaml").read_text(encoding="utf-8"), re.M)) | {
    "planning_store", "validate", "vcs", "finish", "main_branch", "github", "review", "pr", "release", "project", "cheap_tier"}


def looks(s):
    """A YAML mapping whose first key is a top-level settings key (so a skill front matter or a change file is not one)."""
    if len(s) <= 3 or not YAMLISH.match(s):
        return False
    for line in s.splitlines():
        t = line.strip()
        if t and not t.startswith("#"):
            m = re.match(r"""^["']?([A-Za-z_]+)["']?:""", t)
            return bool(m) and m.group(1) in TOP
    return False


class Unsupported(Exception):
    pass


SAFE_CALLS = {"chr": chr, "str": str, "range": range, "len": len, "repr": repr, "int": int, "list": list, "tuple": tuple, "sorted": sorted}
SAFE_METHODS = {"replace", "join", "strip", "lstrip", "rstrip", "format", "lower", "upper", "splitlines", "split", "encode", "decode", "rjust", "ljust", "zfill", "removesuffix", "removeprefix", "startswith", "endswith"}
MAX_ITEMS = 60


def evaluate(node, env, dyn):
    """Evaluates a pure expression over `env` (a dict). Raises Unsupported when it cannot. `dyn` is a list a lenient f-string appends to."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise Unsupported(node.id)
    if isinstance(node, ast.Attribute):
        if node.attr in env.get("__attrs__", {}):
            return env["__attrs__"][node.attr]
        raise Unsupported("." + node.attr)
    if isinstance(node, ast.BinOp):
        a, b = evaluate(node.left, env, dyn), evaluate(node.right, env, dyn)
        try:
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Mod) and isinstance(a, str):
                return a % b
        except Exception as e:  # noqa: BLE001
            raise Unsupported(str(e))
        raise Unsupported("binop")
    if isinstance(node, ast.JoinedStr):
        buf = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                buf.append(v.value)
                continue
            try:
                val = evaluate(v.value, env, dyn)
                if v.conversion not in (-1, None):
                    raise Unsupported("conversion")
                spec = evaluate(v.format_spec, env, None) if v.format_spec is not None else ""
                buf.append(format(val, spec))
            except Unsupported:
                if dyn is None:
                    raise
                dyn.append(1)
                buf.append("X")
        return "".join(buf)
    if isinstance(node, (ast.Tuple, ast.List)):
        return [evaluate(e, env, dyn) for e in node.elts]
    if isinstance(node, ast.Subscript):
        base = evaluate(node.value, env, dyn)
        sl = node.slice
        if isinstance(sl, ast.Slice):
            lo = evaluate(sl.lower, env, dyn) if sl.lower else None
            hi = evaluate(sl.upper, env, dyn) if sl.upper else None
            return base[lo:hi]
        return base[evaluate(sl, env, dyn)]
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in SAFE_CALLS and not node.keywords:
            args = [evaluate(a, env, dyn) for a in node.args]
            try:
                return SAFE_CALLS[node.func.id](*args)
            except Exception as e:  # noqa: BLE001
                raise Unsupported(str(e))
        if isinstance(node.func, ast.Attribute) and node.func.attr in SAFE_METHODS and not node.keywords:
            recv = evaluate(node.func.value, env, dyn)
            if isinstance(recv, str):
                args = [evaluate(a, env, dyn) for a in node.args]
                try:
                    return getattr(recv, node.func.attr)(*args)
                except Exception as e:  # noqa: BLE001
                    raise Unsupported(str(e))
        raise Unsupported("call")
    if isinstance(node, (ast.GeneratorExp, ast.ListComp)):
        if len(node.generators) != 1 or node.generators[0].ifs or not isinstance(node.generators[0].target, ast.Name):
            raise Unsupported("comprehension")
        g = node.generators[0]
        items = list(evaluate(g.iter, env, dyn))
        if len(items) > 5000:
            raise Unsupported("big")
        out = []
        for item in items:
            out.append(evaluate(node.elt, {**env, g.target.id: item}, dyn))
        return out
    if isinstance(node, ast.IfExp):
        return evaluate(node.body if evaluate(node.test, env, dyn) else node.orelse, env, dyn)
    if isinstance(node, ast.BoolOp):
        val = None
        for v in node.values:
            val = evaluate(v, env, dyn)
            if isinstance(node.op, ast.Or) and val:
                return val
            if isinstance(node.op, ast.And) and not val:
                return val
        return val
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not evaluate(node.operand, env, dyn)
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        a, b = evaluate(node.left, env, dyn), evaluate(node.comparators[0], env, dyn)
        op = node.ops[0]
        for kind, fn in ((ast.Eq, lambda: a == b), (ast.NotEq, lambda: a != b), (ast.Is, lambda: a is b), (ast.IsNot, lambda: a is not b), (ast.In, lambda: a in b)):
            if isinstance(op, kind):
                return fn()
    raise Unsupported(type(node).__name__)


def module_env(tree):
    env = {}
    for _ in range(3):
        for st in tree.body:
            if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                try:
                    env[st.targets[0].id] = evaluate(st.value, env, None)
                except Unsupported:
                    pass
    return env


def class_attrs(tree, env):
    """Every class-level `NAME = <expr>` over the module env, by name (the tests read them as self.NAME)."""
    attrs = {}
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        for _ in range(3):
            for st in cls.body:
                if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                    try:
                        attrs[st.targets[0].id] = evaluate(st.value, {**env, "__attrs__": attrs}, None)
                    except Unsupported:
                        pass
    return attrs


entries, omitted, seen = [], [], set()


def add(source, kind, text):
    if text in seen:
        return
    seen.add(text)
    entries.append({"source": source, "kind": kind, "text": text})


STRINGY = re.compile(r"\w: |\w:$|\w:\\n", re.M)


def scan_expr(node, env, rel):
    """Finds the settings-looking strings an expression builds. Returns after the first evaluable string on each branch."""
    if isinstance(node, (ast.Constant, ast.BinOp, ast.JoinedStr, ast.Call)):
        for lenient in (False, True):
            dyn = [] if lenient else None
            try:
                value = evaluate(node, env, dyn)
            except Unsupported:
                continue
            except Exception:  # noqa: BLE001
                continue
            if isinstance(value, str):
                if looks(value):
                    add(f"{rel}:{node.lineno}", "interp" if dyn else "literal", value)
                return
            break
        if isinstance(node, (ast.BinOp, ast.JoinedStr)) and any(
            isinstance(c, ast.Constant) and isinstance(c.value, str) and STRINGY.search(c.value) for c in ast.walk(node)
        ):
            omitted.append(f"{rel}:{node.lineno}: expression not evaluated")
            return
    for child in ast.iter_child_nodes(node):
        scan_expr(child, env, rel)


def run_block(stmts, env, rel):
    env = dict(env)
    for st in stmts:
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
            scan_expr(st.value, env, rel)
            try:
                env[st.targets[0].id] = evaluate(st.value, env, None)
            except Exception:  # noqa: BLE001
                env.pop(st.targets[0].id, None)
        elif isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Tuple):
            scan_expr(st.value, env, rel)
            try:
                vals = evaluate(st.value, env, None)
                for t, v in zip(st.targets[0].elts, vals):
                    env[t.id] = v
            except Exception:  # noqa: BLE001
                for t in st.targets[0].elts:
                    if isinstance(t, ast.Name):
                        env.pop(t.id, None)
        elif isinstance(st, ast.For) and isinstance(st.target, (ast.Name, ast.Tuple)):
            try:
                items = list(evaluate(st.iter, env, None))
            except Exception:  # noqa: BLE001
                items = None
            if items is not None and len(items) <= MAX_ITEMS:
                for item in items:
                    local = dict(env)
                    try:
                        if isinstance(st.target, ast.Name):
                            local[st.target.id] = item
                        else:
                            for t, v in zip(st.target.elts, item):
                                local[t.id] = v
                    except Exception:  # noqa: BLE001
                        pass
                    run_block(st.body, local, rel)
            else:
                run_block(st.body, {k: v for k, v in env.items()}, rel)
        elif isinstance(st, ast.AugAssign) and isinstance(st.target, ast.Name) and isinstance(st.op, ast.Add):
            scan_expr(st.value, env, rel)
            try:
                env[st.target.id] = evaluate(st.target, env, None) + evaluate(st.value, env, None)
            except Exception:  # noqa: BLE001
                env.pop(st.target.id, None)
        elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # parameters with a constant default are bound to it; a bool default is tried both ways (at most three of them)
            a = st.args
            pos = a.posonlyargs + a.args
            defaults = dict(zip([x.arg for x in pos[len(pos) - len(a.defaults):]], a.defaults))
            defaults.update({x.arg: d for x, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None})
            choices = []
            for name, d in list(defaults.items())[:8]:
                if isinstance(d, ast.Constant):
                    vals = [d.value] + ([not d.value] if isinstance(d.value, bool) else [])
                    choices.append((name, vals))
            bools = [c for c in choices if len(c[1]) == 2][:3]
            fixed = {n: v[0] for n, v in choices if (n, v) not in bools}
            for combo in itertools.product(*[v for _, v in bools]):
                run_block(st.body, {**env, **fixed, **{n: c for (n, _), c in zip(bools, combo)}}, rel)
        elif isinstance(st, ast.ClassDef):
            run_block(st.body, env, rel)
        elif isinstance(st, (ast.With, ast.If, ast.Try, ast.While)):
            for field in ("test", "items"):
                for x in (getattr(st, field, None) if isinstance(getattr(st, field, None), list) else [getattr(st, field, None)]):
                    if x is not None:
                        scan_expr(x.context_expr if isinstance(x, ast.withitem) else x, env, rel)
            for body in ("body", "orelse", "finalbody"):
                run_block(getattr(st, body, []), env, rel)
            for h in getattr(st, "handlers", []):
                run_block(h.body, env, rel)
        else:
            scan_expr(st, env, rel)
    return env


files = sorted(p for p in (root / "evals").rglob("*.py") if "specwright.yaml" in p.read_text(encoding="utf-8", errors="replace"))
for path in files:
    rel = path.relative_to(root).as_posix()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        omitted.append(f"{rel}: not parsed")
        continue
    env = module_env(tree)
    env["__attrs__"] = class_attrs(tree, env)
    run_block(tree.body, env, rel)


# ---- helpers, called for real ----------------------------------------------------------------------------------------
def load(rel, name):
    p = root / rel
    sys.path.insert(0, str(p.parent))
    sys.path.insert(0, str(root / "evals"))
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


helpers_note = []
try:
    fx = load("evals/release/fixtures.py", "release_fixtures")
    vfs = [fx.DEFAULT_VERSION_FILES, None, {}, {"VERSION": r"^(\d+\.\d+\.\d+)$"}]
    for tree_path in (root / "evals" / "release").glob("*.py"):
        for node in ast.walk(ast.parse(tree_path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.keyword) and node.arg == "version_files":
                try:
                    v = ast.literal_eval(node.value)
                    if isinstance(v, dict) and v not in vfs:
                        vfs.append(v)
                except Exception:
                    pass
    n = 0
    for vf, en, mm, er, ex, fin in itertools.product(
        vfs, (True, False), (None, "squash", "merge", "rebase", "fast"),
        ("", "  github_release: false\n", '  tag: "release"\n', "  auto: true\n", "\tnote: x\n"),
        ("", "vcs: gitbutler\n", "release:\n  enabled: true\n"), ("pr", "local"),
    ):
        add("evals/release/fixtures.py settings_text", "helper", fx.settings_text(vf, en, mm, er, ex, fin))
        n += 1
    helpers_note.append(f"release settings_text: {n} combinations over {len(vfs)} version_files maps")
except Exception as e:  # noqa: BLE001
    helpers_note.append(f"release fixtures not imported: {type(e).__name__}: {e}")
try:
    gw = load("evals/git-workflow/fixtures.py", "gw_fixtures")
    for en, au in itertools.product((True, False), (True, False)):
        add("evals/git-workflow/fixtures.py release_settings", "helper", gw.release_settings(en, au))
    helpers_note.append("git-workflow release_settings: 4 combinations")
    # texts the git-workflow fixtures and the pr-pair parity test build from their parameters, rebuilt here with the same parts
    rels = [None] + [gw.release_settings(en, au) for en, au in itertools.product((True, False), (True, False))]
    n = 0
    for agent, rel in itertools.product((True, False), rels):
        merging = "  merge: agent\n  merge_method: squash\n" if agent else ""
        add("evals/git-workflow/fixtures.py build_watch_merge", "helper",
            f"finish: pr\ngithub:\n  login: eval-bot\npr:\n  poll_interval: 5s\n{merging}  reviewers:\n    {gw.WATCH_REVIEWER}: {{ role: required }}\n"
            + ((rel or "") + gw.ROADMAP_SETTINGS if agent else ""))
        n += 1
    for pr in (True, False):
        add("evals/git-workflow/fixtures.py line 689", "helper", (gw.PR_SETTINGS if pr else "finish: local\n") + gw.ROADMAP_SETTINGS)
        n += 1
    for en, au in itertools.product((True, False), (True, False)):
        add("evals/git-workflow/fixtures.py line 1457", "helper", "finish: local\n" + gw.release_settings(en, au))
        n += 1
    for backend, role, logins in itertools.product(("git", "jj", "gitbutler"), ("code", "store"), (True, False)):
        t = ("github:\n  login: me\n" if logins else "")
        t += ("vcs: " + backend + "\n" if role == "code" else "vcs: git\n")
        t += "finish: pr\nplanning_store:\n  vcs: " + (backend if role == "store" else "git") + "\n"
        add("evals/pr-pair/test_workflow_parity.py select_backend", "helper", t)
        n += 1
    helpers_note.append(f"git-workflow and pr-pair parameterised texts: {n} combinations")
except Exception as e:  # noqa: BLE001
    helpers_note.append(f"git-workflow fixtures not imported: {type(e).__name__}: {e}")

out_path.write_text(json.dumps({"entries": entries, "omitted": omitted, "helpers": helpers_note}, ensure_ascii=False), encoding="utf-8")
print(len(entries), "entries;", len(omitted), "omitted;", helpers_note)
