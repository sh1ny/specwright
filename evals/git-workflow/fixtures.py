"""Build scratch git repos for the git-workflow evals.

Usage: python fixtures.py <eval-name> <dest-dir>
Each fixture is a small Python project with OpenSpec + Specwright settings
(finish: local) and a deterministic git state for one scenario.
Store fixtures (eval-store-*) make <dest>/code and <dest>/store instead, plus
<dest>/eval.env. Source it before running anything, with <dest>/code as the
working directory: it points the OpenSpec registry and config and the
Specwright state at <dest>, so the user's real ones are never touched.
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def rmtree(path):
    """shutil.rmtree that also removes read-only entries (git marks its objects read-only). On Windows a plain
    rmtree fails on them, and with ignore_errors=True every test that built a repository left its directory in TEMP."""
    def again(func, p, _exc):
        try:
            if os.path.islink(p):  # never change the mode of what a link points at
                raise OSError
            os.chmod(p, 0o700)  # only the entry that failed, which is being removed
            func(p)
        except OSError:
            pass  # still held (a process that has not exited): leave it rather than fail the test
    shutil.rmtree(path, **({"onexc": again} if sys.version_info >= (3, 12) else {"onerror": again}))

ROOT = Path(__file__).resolve().parents[2]  # specwright repo
sys.path.insert(0, str(ROOT / "evals" / "fakes"))
import gh as fake_gh  # noqa: E402  the fake gh's state helpers
if str(ROOT / "evals") not in sys.path:
    sys.path.append(str(ROOT / "evals"))
import fixturecache  # noqa: E402  per-process cache: path-independent repo stages are built once and copied
import bashexe  # noqa: E402


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def write(repo, rel, text):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def _init(repo):
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Eval Bot")
    git(repo, "config", "user.email", "eval@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")


def init(repo):
    """An empty configured repo on main at `repo` (a copy of one built once per process; the config holds no path)."""
    fixturecache.copy(("git-workflow.init",), _init, repo)


def base(repo, settings="finish: local\n"):
    """The schema-bearing project repo on main; a copy of one built once per process (nothing in it names a path).
    `settings` is the text of openspec/specwright.yaml, committed in the first commit."""
    fixturecache.copy(("git-workflow.base", settings), lambda d: _base(d, settings), repo)


def _base(repo, settings="finish: local\n"):
    _init(repo)
    shutil.copytree(ROOT / "schemas" / "specwright", repo / "openspec" / "schemas" / "specwright")
    shutil.copy(ROOT / "templates" / "openspec" / "config.yaml", repo / "openspec" / "config.yaml")
    write(repo, "openspec/specwright.yaml", settings)
    write(repo, "openspec/specs/.gitkeep", "")
    project(repo)


def project(repo):
    """The tiny Python project and its first commit; every fixture shares it."""
    write(repo, "greet.py", '"""Greeting helpers."""\n')
    write(repo, "test_greet.py", "import unittest\n\nimport greet  # noqa: F401\n\n\nclass GreetTests(unittest.TestCase):\n    pass\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
    write(repo, "README.md", "# greeter\n\nA tiny greeting library.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "chore: initial project")


def posix(p):
    return Path(p).resolve().as_posix()


def msys(p):
    """posix(p) as an MSYS path (/c/x): a drive colon would split a PATH entry in Git Bash."""
    s = posix(p)
    return f"/{s[0].lower()}{s[2:]}" if s[1:2] == ":" else s


def openspec(dest, *args, cwd=None):
    """Run the openspec CLI against the fixture's isolated registry and config (from `cwd`, default dest)."""
    env = {**os.environ, "XDG_DATA_HOME": posix(dest / "xdg-data"), "XDG_CONFIG_HOME": posix(dest / "xdg-config"),
           "OPENSPEC_TELEMETRY": "0"}
    subprocess.run([shutil.which("openspec") or "openspec", *args], cwd=cwd or dest, env=env, check=True, capture_output=True, text=True)


def env_file(dest, **extra):
    """Write <dest>/eval.env; once it exists, later calls append (install_fake_gh adds its variables)."""
    p = dest / "eval.env"
    if not p.exists():
        extra = {"XDG_DATA_HOME": posix(dest / "xdg-data"), "XDG_CONFIG_HOME": posix(dest / "xdg-config"),
                 "SPECWRIGHT_STATE_DIR": posix(dest / "state"), "PATH": f"{msys(dest / 'bin')}:$PATH", **extra}
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.writelines(f'export {k}="{v}"\n' for k, v in extra.items())


def install_fake_gh(dest):
    """Put the fake gh on the fixture's PATH; its state and call log live in <dest>."""
    write(dest, "bin/gh", f'#!/bin/sh\nexec "{posix(sys.executable)}" "{posix(ROOT / "evals" / "fakes" / "gh.py")}" "$@"\n')
    (dest / "bin" / "gh").chmod(0o755)
    env_file(dest, FAKE_GH_STATE=posix(dest / "gh-state.json"), FAKE_GH_LOG=posix(dest / "gh-log.jsonl"))


def install_fake_openspec(dest, version):
    """Put an openspec on the fixture's PATH that reports `version` for --version and otherwise runs the real CLI.
    The real CLI's absolute path is resolved now, before <dest>/bin is on PATH; on Windows the npm shim's
    extensionless sh twin is used, since sh cannot exec openspec.cmd."""
    real = shutil.which("openspec")
    if not real:
        raise SystemExit("install_fake_openspec: the openspec CLI is not on PATH")
    real = Path(real)
    if real.suffix.lower() in (".cmd", ".bat", ".ps1") and real.with_suffix("").is_file():
        real = real.with_suffix("")
    write(dest, "bin/openspec", f'#!/bin/sh\nif [ "$1" = "--version" ]; then echo "{version}"; exit 0; fi\n'
                                f'exec "{posix(real)}" "$@"\n')
    (dest / "bin" / "openspec").chmod(0o755)


def code_repo(code, store_id="team-plans", pointer=True, settings="finish: local\n"):
    """The project repo: Specwright settings, an optional config.yaml pointing at the store
    (otherwise the store is the global defaultStore) and the tiny project. No openspec specs/changes.
    A copy of one built once per process per argument set (nothing in it names a path)."""
    fixturecache.copy(("git-workflow.code_repo", store_id, pointer, settings),
                      lambda dest: _code_repo(dest, store_id, pointer, settings), code)


def _code_repo(code, store_id, pointer, settings):
    _init(code)
    if settings is not None:
        write(code, "openspec/specwright.yaml", settings)
    if pointer:
        write(code, "openspec/config.yaml", f"store: {store_id}\n")
    project(code)


def store_content(root):
    """What a planning root holds: the schema, trigger config and specs (not yet committed)."""
    shutil.copytree(ROOT / "schemas" / "specwright", root / "openspec" / "schemas" / "specwright")
    shutil.copy(ROOT / "templates" / "openspec" / "config.yaml", root / "openspec" / "config.yaml")
    write(root, "openspec/specs/.gitkeep", "")


def register(dest, root, store_id, pointer=True):
    openspec(dest, "store", "register", posix(root), "--id", store_id, "--yes")
    if not pointer:
        openspec(dest, "config", "set", "defaultStore", store_id)


def _initial_store(store):
    _init(store)
    store_content(store)
    git(store, "add", "-A")
    git(store, "commit", "-q", "-m", "chore: initial store")


def store_base(dest, store_id="team-plans", pointer=True, registered=True, store_git=True, store_worktree=False,
               settings="finish: local\n"):
    """<dest>/code (the project; its openspec/config.yaml points at the store when `pointer`,
    otherwise the store is the global defaultStore) and <dest>/store (a registered store
    holding the schema, trigger config and specs). Both are clean on main.
    registered=False: no store at all, the pointer dangles (the registry is empty).
    store_git=False: <dest>/store is a plain directory, not a git repo.
    store_worktree: <dest>/store is a worktree of the code repo on branch `plans`."""
    code, store = dest / "code", dest / "store"
    code_repo(code, store_id, pointer, settings)
    (dest / "bin").mkdir()
    if not registered:
        return env_file(dest)
    if store_worktree:
        git(code, "worktree", "add", "-q", "--orphan", "-b", "plans", posix(store))
        git(store, "config", "commit.gpgsign", "false")
    elif store_git:  # init, content and first commit: a copy of one built once (before register, so nothing names a path)
        fixturecache.copy(("git-workflow.initial_store",), _initial_store, store)
    else:
        store.mkdir()
    if store_worktree or not store_git:
        store_content(store)
        if store_git:
            git(store, "add", "-A")
            git(store, "commit", "-q", "-m", "chore: initial store")
    register(dest, store, store_id, pointer)
    if store_git:
        git(store, "add", "-A")  # registration wrote .openspec-store/store.yaml
        git(store, "commit", "-q", "-m", "chore: register store")
    env_file(dest)


def nested_base(dest, store_id="team-plans"):
    """<dest>/code only: the planning root is <dest>/code/planning, registered as a store and
    committed inside the code repo. The top-level openspec/ holds only the pointer config."""
    code = dest / "code"
    code_repo(code, store_id)
    (dest / "bin").mkdir()
    store_content(code / "planning")
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "chore: add planning root")
    register(dest, code / "planning", store_id)
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "chore: register store")
    env_file(dest)


CHANGE = "openspec/changes/add-greeting"


def change_artifacts(repo, name="add-greeting"):
    CHANGE = f"openspec/changes/{name}"  # shadows the module constant for other names
    write(repo, f"{CHANGE}/.openspec.yaml", "schema: specwright\ncreated: 2026-10-07\n")
    write(repo, f"{CHANGE}/proposal.md", "## Why\n\nUsers need friendly greetings.\n\n## What Changes\n\n- Add `greet` and `farewell`.\n\n## Capabilities\n\n### New Capabilities\n- `greeting`: greeting and farewell messages\n\n## Impact\n\n`greet.py`, `README.md`.\n")
    write(repo, f"{CHANGE}/specs/greeting/spec.md", "# Spec Delta\n\n## Purpose\n\nProduces greeting and farewell messages for a named person.\n\n## ADDED Requirements\n\n### Requirement: Greeting\nThe system SHALL return `Hello, <name>!` for a non-empty name.\n\n#### Scenario: Named greeting\n- **WHEN** greet is called with `Ada`\n- **THEN** it returns `Hello, Ada!`\n\n#### Scenario: Empty name\n- **WHEN** greet is called with an empty string\n- **THEN** it raises ValueError\n\n### Requirement: Farewell\nThe system SHALL return `Goodbye, <name>!` for a non-empty name.\n\n#### Scenario: Named farewell\n- **WHEN** farewell is called with `Ada`\n- **THEN** it returns `Goodbye, Ada!`\n\n#### Scenario: Empty farewell name\n- **WHEN** farewell is called with an empty string\n- **THEN** it raises ValueError\n")
    write(repo, f"{CHANGE}/design.md", "# Design\n\n## Triage\n\nNo trigger applies: two pure functions in an existing module.\n\nTIER: LIGHT\n\n## Context\n\n`greet.py` is an empty module.\n\n## Decisions\n\n### D1: Validate names with ValueError\n\n- **Choice:** raise ValueError on empty names.\n- **Rejected:** returning a default greeting, because it hides caller bugs.\n- **Reversal cost:** low\n")
    write(repo, f"{CHANGE}/review.md", "# Review\n\n## Metadata\n\n- **Round:** 1\n- **Reviewer:** n/a for SKIPPED_LIGHT\n\nTriage re-checked: no trigger applies.\n\n## Verdict\n\nVERDICT: SKIPPED_LIGHT\n\nCHANGES_APPLIED: n/a\n")
    write(repo, f"{CHANGE}/tasks.md", "# Tasks\n\n## Test map\n\n| Requirement | Scenario | Test file | Test name | State |\n|---|---|---|---|---|\n| greeting → Greeting | Named greeting | test_greet.py | test_greet_named | red |\n| greeting → Greeting | Empty name | test_greet.py | test_greet_empty | red |\n| greeting → Farewell | Named farewell | test_greet.py | test_farewell_named | red |\n| greeting → Farewell | Empty farewell name | test_greet.py | test_farewell_empty | red |\n\n## 1. Greeting functions\n\n- [ ] 1.1 Add `greet(name)` with tests test_greet_named and test_greet_empty; verify `python -m unittest -q` passes\n- [ ] 1.2 Add `farewell(name)` with tests test_farewell_named and test_farewell_empty; verify `python -m unittest -q` passes\n\n## 2. Documentation\n\n- [ ] 2.1 Document greet and farewell in README.md; verify README names both functions\n")


def implemented(repo):
    """Code, tests and README as they would be after apply."""
    write(repo, "greet.py", '"""Greeting helpers."""\n\n\ndef greet(name):\n    if not name:\n        raise ValueError("name is required")\n    return f"Hello, {name}!"\n\n\ndef farewell(name):\n    if not name:\n        raise ValueError("name is required")\n    return f"Goodbye, {name}!"\n')
    write(repo, "test_greet.py", "import unittest\n\nfrom greet import farewell, greet\n\n\nclass GreetTests(unittest.TestCase):\n    def test_greet_named(self):\n        self.assertEqual(greet('Ada'), 'Hello, Ada!')\n\n    def test_greet_empty(self):\n        with self.assertRaises(ValueError):\n            greet('')\n\n    def test_farewell_named(self):\n        self.assertEqual(farewell('Ada'), 'Goodbye, Ada!')\n\n    def test_farewell_empty(self):\n        with self.assertRaises(ValueError):\n            farewell('')\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
    write(repo, "README.md", "# greeter\n\nA tiny greeting library.\n\n- `greet(name)` returns `Hello, <name>!`.\n- `farewell(name)` returns `Goodbye, <name>!`.\n")


def finished(code, root):
    """On feat/add-greeting: planning commit, implementation commit with ticked tasks, then a
    simulated completed vanilla archive (change moved, spec synced) left uncommitted.
    `root` is the planning root: the code repo itself, or a folder inside it."""
    change = root / CHANGE
    git(code, "checkout", "-q", "-b", "feat/add-greeting")
    change_artifacts(root)
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "feat(add-greeting): add planning artifacts")
    implemented(code)
    tasks = (change / "tasks.md").read_text(encoding="utf-8")
    write(root, f"{CHANGE}/tasks.md", tasks.replace("- [ ]", "- [x]").replace("| red |", "| green |"))
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "feat(add-greeting): implement tasks 1.1-2.1")
    archive = root / "openspec/changes/archive/2026-10-07-add-greeting"
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(change), str(archive))
    spec = (archive / "specs/greeting/spec.md").read_text(encoding="utf-8")
    write(root, "openspec/specs/greeting/spec.md", spec.replace("# Spec Delta", "# greeting Specification").replace("## ADDED Requirements", "## Requirements"))


TASK_SUBJECT = {
    "1.1": "feat(add-greeting): task 1.1 Add greet(name)",
    "1.2": "feat(add-greeting): task 1.2 Add farewell(name)",
    "2.1": "feat(add-greeting): task 2.1 Document greet and farewell",
}
VERIFY_TASK = "- [ ] 2.1 Verify the full suite: run `python -m unittest -q` and confirm it passes (verification only, no files change)"


def task_code(code, t):
    """The code files task `t` changes (cumulative: 1.2 builds on 1.1), left uncommitted."""
    if t == "1.1":
        write(code, "greet.py", '"""Greeting helpers."""\n\n\ndef greet(name):\n    if not name:\n        raise ValueError("name is required")\n    return f"Hello, {name}!"\n')
        write(code, "test_greet.py", "import unittest\n\nfrom greet import greet\n\n\nclass GreetTests(unittest.TestCase):\n    def test_greet_named(self):\n        self.assertEqual(greet('Ada'), 'Hello, Ada!')\n\n    def test_greet_empty(self):\n        with self.assertRaises(ValueError):\n            greet('')\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
    elif t == "1.2":
        implemented(code)  # greet.py and test_greet.py are final; README is task 2.1's
        write(code, "README.md", "# greeter\n\nA tiny greeting library.\n")
    elif t == "2.1":
        implemented(code)


def commit_code(code, t):
    task_code(code, t)
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", TASK_SUBJECT[t])


def tick(store, *tasks):
    """Tick tasks in the store's tasks.md, uncommitted."""
    text = (store / CHANGE / "tasks.md").read_text(encoding="utf-8")
    for t in tasks:
        text = text.replace(f"- [ ] {t} ", f"- [x] {t} ")
    write(store, f"{CHANGE}/tasks.md", text)


def commit_tick(store, t):
    git(store, "add", f"{CHANGE}/tasks.md")
    git(store, "commit", "-q", "-m", TASK_SUBJECT[t])


def apply_base(dest, verify_last=False, kind=None):
    """store_base, both repos on feat/add-greeting, the planning artifacts committed in the store.
    verify_last: task 2.1 is a verification-only task instead of the README one.
    kind: a GROUP_TASKS key; group mode is on and tasks.md holds those groups."""
    code, store = dest / "code", dest / "store"
    store_base(dest, settings=GROUP_SETTINGS if kind else "finish: local\n")
    for r in (code, store):
        git(r, "checkout", "-q", "-b", "feat/add-greeting")
    if kind:
        group_artifacts(store, kind)
    else:
        change_artifacts(store)
    if verify_last:
        text = (store / CHANGE / "tasks.md").read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if l.startswith("- [ ] 2.1 "))
        write(store, f"{CHANGE}/tasks.md", text.replace(line, VERIFY_TASK).replace("## 2. Documentation", "## 2. Verification"))
    git(store, "add", "-A")
    git(store, "commit", "-q", "-m", "feat(add-greeting): add planning artifacts")


# ---- group mode (commit_granularity: group) ----
GROUP_SETTINGS = "finish: local\ncommit_granularity: group\n"
CO_AUTHOR = "Co-authored-by: KintsugiBot <296966193+KintsugiBot@users.noreply.github.com>"
_V = "verify `python -m unittest -q` passes"
_ONLY = "(verification only, no files change)"
_T11 = f"Add `greet(name)` with tests test_greet_named and test_greet_empty; {_V}"
_T12 = f"Add `farewell(name)` with tests test_farewell_named and test_farewell_empty; {_V}"
GROUP_TASKS = {  # kind -> [(group number, heading, [(task id, text)])]
    "groups": [(1, "Greeting functions", [("1.1", _T11), ("1.2", _T12), ("1.3", f"Export both names in `__all__` of greet.py; {_V}")]),
               (2, "Documentation", [("2.1", "Document greet in README.md; verify README names greet"),
                                     ("2.2", "Document farewell in README.md; verify README names farewell")])],
    "ten": [(1, "Greeting functions", [("1.1", _T11), ("1.2", _T12)]),
            (10, "Documentation", [("10.1", "Document greet and farewell in README.md; verify README names both functions")])],
    "resume": [(1, "Greeting functions", [("1.1", "Write test_greet_named in test_greet.py and confirm it fails (red step)"),
                                          ("1.2", f"Implement `greet(name)` in greet.py so test_greet_named passes; {_V}"),
                                          ("1.3", f"Make `greet('')` raise ValueError with test_greet_empty, and add `farewell(name)` "
                                                  f"with tests test_farewell_named and test_farewell_empty; {_V}")])],
    "noop": [(1, "Greeting functions", [("1.1", _T11), ("1.2", _T12)]),
             (2, "Documentation", [("2.1", "Document greet and farewell in README.md; verify README names both functions")]),
             (3, "Verification", [("3.1", f"Verify the full suite: run `python -m unittest -q` and confirm it passes {_ONLY}"),
                                  ("3.2", f"Verify test_greet.py names test_greet_named: run `python -m unittest -v` {_ONLY}")])],
}
TASKS_HEAD = ("# Tasks\n\n## Test map\n\n| Requirement | Scenario | Test file | Test name | State |\n|---|---|---|---|---|\n"
              "| greeting → Greeting | Named greeting | test_greet.py | test_greet_named | red |\n"
              "| greeting → Greeting | Empty name | test_greet.py | test_greet_empty | red |\n"
              "| greeting → Farewell | Named farewell | test_greet.py | test_farewell_named | red |\n"
              "| greeting → Farewell | Empty farewell name | test_greet.py | test_farewell_empty | red |\n")


def group_artifacts(root, kind, name="add-greeting"):
    """The change's planning artifacts (uncommitted), with the tasks.md of GROUP_TASKS[kind]."""
    change_artifacts(root, name)
    text = TASKS_HEAD + "".join(f"\n## {n}. {h}\n\n" + "".join(f"- [ ] {t} {x}\n" for t, x in ts) for n, h, ts in GROUP_TASKS[kind])
    write(root, f"openspec/changes/{name}/tasks.md", text)


def group_spec(kind, n):
    """(heading, [task ids]) of group n."""
    return next((h, [t for t, _ in ts]) for g, h, ts in GROUP_TASKS[kind] if g == n)


def group_msg(kind, n, tasks=None, body=None, no_code=False):
    """A group commit message: subject, optional body, then the final trailer block (Code-Changes: none first when
    there is no code, the Specwright-Task trailers in task order, Co-authored-by last)."""
    heading, ids = group_spec(kind, n)
    lines = [f"feat(add-greeting): group {n} {heading}", ""] + ([body, ""] if body else [])
    lines += (["Code-Changes: none"] if no_code else []) + [f"Specwright-Task: {t}" for t in (ids if tasks is None else tasks)] + [CO_AUTHOR]
    return "\n".join(lines) + "\n"


def group_code(code, n):
    """Write group n's code files, uncommitted, and return their paths."""
    if n == 1:
        task_code(code, "1.2")
        write(code, "greet.py", (code / "greet.py").read_text(encoding="utf-8") + '\n__all__ = ["greet", "farewell"]\n')
        return ["greet.py", "test_greet.py"]
    if n in (2, 10):
        write(code, "README.md", "# greeter\n\nA tiny greeting library.\n\n- `greet(name)` returns `Hello, <name>!`.\n- `farewell(name)` returns `Goodbye, <name>!`.\n")
        return ["README.md"]
    return []


def commit_group(code, root, kind, n, tasks=None, body=None, no_code=False, msg=None):
    """Finish group n: write its code (unless no_code), tick its tasks in root's tasks.md, commit.
    root == code: one commit. Store-backed: the code repo first, then tasks.md in root, with the same message."""
    ids = group_spec(kind, n)[1] if tasks is None else tasks
    msg = msg or group_msg(kind, n, ids, body, no_code)
    paths = [] if no_code else group_code(code, n)
    tick(root, *ids)
    tasks_md = f"{CHANGE}/tasks.md"
    if code == root:
        git(code, "add", "--", *paths, tasks_md)
        git(code, "commit", "-q", "-m", msg, "--", *paths, tasks_md)
        return
    if paths:
        git(code, "add", "--", *paths)
        git(code, "commit", "-q", "-m", msg, "--", *paths)
    git(root, "add", "--", tasks_md)
    git(root, "commit", "-q", "-m", msg, "--", tasks_md)


def plan_commit(root):
    git(root, "add", "--", CHANGE)
    git(root, "commit", "-q", "-m", "feat(add-greeting): add planning artifacts")


GROUP_EVALS = {"eval-apply-groups": "groups", "eval-apply-groups-ten": "ten", "eval-apply-groups-resume": "resume",
               "eval-apply-groups-switch": "groups"}


def build_group(name, repo):
    """Repo-local group-mode fixtures, on feat/add-greeting with commit_granularity: group.
    groups: planning artifacts uncommitted, plus scratch-notes.txt. ten: the same without the scratch file, groups 1 and 10.
    resume: planning committed; 1.1 (red step) and 1.2 ticked with their work uncommitted, 1.3 open, and an uncommitted design.md edit.
    switch: planning committed and task 1.1 committed per task before the mode changed; .git/fixture-state.json records its SHA."""
    base(repo, GROUP_SETTINGS)
    git(repo, "checkout", "-q", "-b", "feat/add-greeting")
    group_artifacts(repo, GROUP_EVALS[name])
    if name == "eval-apply-groups":
        write(repo, "scratch-notes.txt", "personal notes - not part of the change\n")
    elif name == "eval-apply-groups-resume":
        plan_commit(repo)
        tick(repo, "1.1", "1.2")
        write(repo, "test_greet.py", "import unittest\n\nfrom greet import greet\n\n\nclass GreetTests(unittest.TestCase):\n    def test_greet_named(self):\n        self.assertEqual(greet('Ada'), 'Hello, Ada!')\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
        write(repo, "greet.py", '"""Greeting helpers."""\n\n\ndef greet(name):\n    return f"Hello, {name}!"\n')
        with (repo / CHANGE / "design.md").open("a", encoding="utf-8", newline="\n") as f:
            f.write("\n## Notes\n\n- Both functions live in `greet.py`, so the tasks of group 1 share that file. This note changes no decision.\n")
    elif name == "eval-apply-groups-switch":
        plan_commit(repo)
        task_code(repo, "1.1")
        tick(repo, "1.1")
        git(repo, "add", "--", "greet.py", "test_greet.py", f"{CHANGE}/tasks.md")
        git(repo, "commit", "-q", "-m", TASK_SUBJECT["1.1"])
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
        write(repo, ".git/fixture-state.json", json.dumps({"task_1_1": sha}, indent=2))


def done_pair(dest, t):
    """Task t finished normally: code commit, then the store tick with the same subject."""
    commit_code(dest / "code", t)
    tick(dest / "store", t)
    commit_tick(dest / "store", t)


def gate_lock(store, when, change="other-change", checkout="C:/elsewhere/code", owner=None):
    """Another session's gate lock in the store's git common dir, taken at `when` (a datetime).
    `owner`: the owner file's text, when it is not the gate's own three lines."""
    r = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=store,
                       check=True, capture_output=True, text=True)
    lock = Path(r.stdout.strip()) / "specwright-gate.lock"
    lock.mkdir()
    (lock / "owner").write_text(owner if owner is not None else
                                f"time: {when.isoformat(timespec='seconds')}\nchange: {change}\ncheckout: {checkout}\n",
                                encoding="utf-8", newline="\n")


def archive_change(dest, name):
    """Run the real `openspec archive` in the store, as the vanilla archive workflow does: the change
    directory moves into openspec/changes/archive/ and the delta syncs into openspec/specs/, uncommitted.
    A name without a date prefix is archived as <today>-<name>, so graders match the date by pattern."""
    openspec(dest, "archive", name, "--yes", cwd=dest / "store")


def finish_ready(dest, name="add-greeting", code_work=True, settings="finish: local\n"):
    """store_base, both repos on feat/<name>, the planning artifacts committed in the store and
    every task done. code_work: each task is a code commit plus a store tick commit (done_pair);
    otherwise the change is planning-only: the code branch has no commit and the store ticks every task
    in one commit. Both trees are clean; the archive has not run."""
    code, store = dest / "code", dest / "store"
    store_base(dest, settings=settings)
    for r in (code, store):
        git(r, "checkout", "-q", "-b", f"feat/{name}")
    change_artifacts(store, name)
    git(store, "add", "-A")
    git(store, "commit", "-q", "-m", f"feat({name}): add planning artifacts")
    if code_work:
        for t in ("1.1", "1.2", "2.1"):
            done_pair(dest, t)
    else:
        tasks = store / f"openspec/changes/{name}/tasks.md"
        write(store, f"openspec/changes/{name}/tasks.md", tasks.read_text(encoding="utf-8").replace("- [ ]", "- [x]").replace("| red |", "| green |"))
        git(store, "add", "-A")
        git(store, "commit", "-q", "-m", f"feat({name}): complete planning tasks")


def diverge_main(repo, rel, text, subject, branch="feat/add-greeting"):
    """A commit on main that conflicts with the change branch, which has not touched `rel` the same way;
    the repo ends up back on `branch` with a clean tree."""
    git(repo, "checkout", "-q", "main")
    write(repo, rel, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", subject)
    git(repo, "checkout", "-q", branch)


CONFLICT_SPEC = "# greeting Specification\n\n## Purpose\n\nGreetings, as another team wrote them first.\n\n## Requirements\n\n### Requirement: Salutation\nThe system SHALL open every message with `Dear <name>,`.\n\n#### Scenario: Salutation\n- **WHEN** a message is written for `Ada`\n- **THEN** it starts with `Dear Ada,`\n"
CONFLICT_STORE = "docs(greeting): add greeting spec on main"
CONFLICT_CODE = "feat: add formal greeting"
PR_SLUG = "acme/greeter"
ARCHIVED_CSV = "## Why\n\nAn earlier CSV export, shipped and archived.\n"


def merge_into_main(repo, branch="feat/add-greeting", name="add-greeting"):
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", branch, "-m", f"merge: {name}")
    git(repo, "branch", "-q", "-d", branch)


def open_code_pr(dest, code):
    """The code PR for feat/add-greeting is open on GitHub (fake gh): origin names the repo, the state holds the PR."""
    git(code, "remote", "add", "origin", f"https://github.com/{PR_SLUG}.git")
    install_fake_gh(dest)
    pr = {"number": 7, "html_url": f"https://github.com/{PR_SLUG}/pull/7", "state": "open", "merged_at": None,
          "title": "feat(add-greeting): add greet and farewell", "body": "Adds greet and farewell.",
          "head": {"ref": "feat/add-greeting", "label": "acme:feat/add-greeting", "repo": {"full_name": PR_SLUG}},
          "base": {"ref": "main"}}
    st = {"user": "eval-bot", "tokens": {"eval-bot": "eval-token"}, "repos": {PR_SLUG: {"default_branch": "main", "pulls": [pr]}}}
    write(dest, "gh-state.json", json.dumps(st, indent=2))


STORE_SLUG = "acme/greeter-plans"
PR_SETTINGS = "finish: pr\ngithub:\n  login: eval-bot\n"
STORE_PR_BODY = "Plans for add-greeting."


def unreachable_proxy(dest):
    """Every git network operation in the run fails fast: the fixture's global git config (GIT_CONFIG_GLOBAL in
    eval.env) sends HTTP(S) through a proxy nobody listens on. as.sh clears only extraHeader and credential
    helpers, so the proxy survives it; GIT_CONFIG_COUNT variables would not (as.sh replaces them)."""
    write(dest, "gitconfig", "[http]\n\tproxy = http://127.0.0.1:9\n")
    env_file(dest, GIT_CONFIG_GLOBAL=posix(dest / "gitconfig"))


SHIM = r'''#!/bin/bash
# git shim for the eval: real git for everything, except `push` in the store checkout, which goes to a local
# bare repo and then updates refs/remotes/origin/<branch> (and the upstream with -u) as a push to origin would.
REAL="@REAL@"
STORE="@STORE@"
BARE="@BARE@"
dir=.
a=("$@")
while [ ${#a[@]} -gt 0 ]; do
  case "${a[0]}" in
    -C) dir="${a[1]}"; a=("${a[@]:2}") ;;
    -c) a=("${a[@]:2}") ;;
    -*) a=("${a[@]:1}") ;;
    *) break ;;
  esac
done
if [ "${a[0]:-}" = push ]; then
  top=$("$REAL" -C "$dir" rev-parse --show-toplevel 2>/dev/null)
  branch=$("$REAL" -C "$dir" symbolic-ref --short -q HEAD 2>/dev/null)
  lc() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }  # no bash 4 case expansion: macOS /bin/bash is 3.2
  if [ "$(lc "$top")" = "$(lc "$STORE")" ] && [ -n "$branch" ]; then
    "$REAL" -C "$dir" push -q "$BARE" "HEAD:refs/heads/$branch" || exit $?
    "$REAL" -C "$dir" update-ref "refs/remotes/origin/$branch" HEAD || exit $?
    url=$("$REAL" -C "$dir" remote get-url origin)
    echo "To $url" >&2
    echo " * [new branch]      HEAD -> $branch" >&2
    for x in "${a[@]}"; do
      if [ "$x" = -u ] || [ "$x" = --set-upstream ]; then
        "$REAL" -C "$dir" config "branch.$branch.remote" origin
        "$REAL" -C "$dir" config "branch.$branch.merge" "refs/heads/$branch"
        echo "branch '$branch' set up to track 'origin/$branch'."
        break
      fi
    done
    exit 0
  fi
fi
exec "$REAL" "$@"
'''


def git_shim(dest):
    """A `git` first on the eval's PATH (<dest>/bin, which eval.env already puts there): a push in the store checkout
    succeeds into the bare repo <dest>/so.git, and sets the remote-tracking branch and upstream. The store's origin stays
    on GitHub, so `pr-pair.sh identity` passes. A push in the code repo still dies at the unreachable proxy."""
    bare = dest / "so.git"  # short: Windows paths under the eval run dir near MAX_PATH
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", posix(bare)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", posix(bare), "config", "core.longpaths", "true"], check=True, capture_output=True, text=True)
    real =msys(shutil.which("git") or "git")
    write(dest, "bin/git", SHIM.replace("@REAL@", real).replace("@STORE@", posix(dest / "store")).replace("@BARE@", posix(bare)))
    (dest / "bin" / "git").chmod(0o755)


def pr_pair_base(dest, store_origin=True, code_pr=False, store_pr=False, store_push_ok=False):
    """Both repos finished on feat/add-greeting (task pairs committed, archive not run), finish: pr as
    eval-bot, fake gh, an unreachable git proxy. The code repo's origin is acme/greeter; the store's is
    acme/greeter-plans when `store_origin`, otherwise it has no remote. code_pr: code PR #7 is open.
    store_pr: store PR #3 is open. store_push_ok: the git shim lets the store push succeed (the code push fails)."""
    finish_ready(dest, settings=PR_SETTINGS)
    code, store = dest / "code", dest / "store"
    git(code, "remote", "add", "origin", f"https://github.com/{PR_SLUG}.git")
    if store_origin:
        git(store, "remote", "add", "origin", f"https://github.com/{STORE_SLUG}.git")
    install_fake_gh(dest)
    unreachable_proxy(dest)
    if store_push_ok:
        git_shim(dest)
    repos = {PR_SLUG: {"default_branch": "main", "pulls": []}}
    if code_pr:
        repos[PR_SLUG]["pulls"].append(
            {"number": 7, "html_url": f"https://github.com/{PR_SLUG}/pull/7", "state": "open", "merged_at": None,
             "title": "feat(add-greeting): add greet and farewell", "body": "Adds greet and farewell.",
             "head": {"ref": "feat/add-greeting", "label": "acme:feat/add-greeting", "repo": {"full_name": PR_SLUG}},
             "base": {"ref": "main"}})
    if store_origin:
        repos[STORE_SLUG] = {"default_branch": "main", "pulls": []}
        if store_pr:
            repos[STORE_SLUG]["pulls"].append(
                {"number": 3, "html_url": f"https://github.com/{STORE_SLUG}/pull/3", "state": "open", "merged_at": None,
                 "title": "feat(add-greeting): add greeting plans", "body": STORE_PR_BODY,
                 "head": {"ref": "feat/add-greeting", "label": "acme:feat/add-greeting", "repo": {"full_name": STORE_SLUG}},
                 "base": {"ref": "main"}})
    write(dest, "gh-state.json", json.dumps({"user": "eval-bot", "tokens": {"eval-bot": "eval-token"}, "repos": repos}, indent=2))


ROADMAP_SETTINGS = "project:\n  roadmap: openspec/roadmap.md\n"


def archive_in_store(store, archived, subject, marker=False):
    """An archived change on the store's main, as a merge left it: one commit adding the archive directory."""
    d = f"openspec/changes/archive/{archived}"
    write(store, f"{d}/.openspec.yaml", "schema: specwright\ncreated: 2026-10-07\n")
    write(store, f"{d}/proposal.md", f"## Why\n\n{archived} was planned, built and archived.\n")
    write(store, f"{d}/tasks.md", "# Tasks\n\n## 1. Work\n\n- [x] 1.1 Do the work\n")
    if marker:
        write(store, f"{d}/specwright-change.yaml", "code_changes: none\n")
    git(store, "add", "-A")
    git(store, "commit", "-q", "-m", subject)


def code_branch(code, name, files=("1.1", "2.1")):
    """feat/<name> off main with one commit per task (each adds its own file, so branches never conflict); back on main.
    Returns the commit hashes, oldest first."""
    git(code, "checkout", "-q", "-b", f"feat/{name}", "main")
    hashes = []
    for t in files:
        write(code, f"{name}-{t}.txt", f"task {t} of {name}\n")
        git(code, "add", "-A")
        git(code, "commit", "-q", "-m", f"feat({name}): task {t} Work for {name}")
        hashes.append(subprocess.run(["git", "rev-parse", "HEAD"], cwd=code, check=True, capture_output=True, text=True).stdout.strip())
    git(code, "checkout", "-q", "main")
    return hashes


def cherry_pick(code, commit):
    """Land one task commit of an unmerged branch on main, as a new commit after unrelated work (so it is not a fast-forward twin)."""
    write(code, "CHANGELOG.md", "# Changelog\n")
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "docs: add changelog")
    git(code, "cherry-pick", commit)


def roadmap_file(code, changes):
    """The roadmap (project.roadmap) committed on the code repo's main. `changes` are (name, description) lines."""
    lines = "".join(f"{i}. `{n}` - {d}\n" for i, (n, d) in enumerate(changes, 1))
    write(code, "openspec/roadmap.md",
          "# Greeter Roadmap\n\nStrategy: openspec/strategy.md · Architecture: openspec/architecture.md\n\n"
          "<!-- Status is derived: a change is done when archived; a milestone is done when its changes are done and its exit criteria pass. Do not add status checkboxes for changes. -->\n\n"
          "## Now: M2 - Friendly greetings\n\n**Outcome:** Users get greetings, farewells and the first reports.\n\n"
          "**Exit criteria:**\n- The suite passes on main (agent)\n\n"
          f"**Changes** (in order; each about one PR):\n{lines}\n"
          "## Next: M3 - Sharing\n\nSharing greetings between teams; retires the risk of unreadable exports.\n\n"
          "## Later\n\n- M4 - Localisation: translated greetings\n")
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "docs: add project roadmap")


def gh_pull(n, name, merged=False, state=None, base="main", owner="acme"):
    """A REST pull object for the fake gh: head feat/<name> from `owner`'s greeter repo, into `base`."""
    return {"number": n, "html_url": f"https://github.com/{PR_SLUG}/pull/{n}", "state": state or ("closed" if merged else "open"),
            "merged_at": "2026-10-09T10:00:00Z" if merged else None, "title": f"feat({name}): work for {name}", "body": "Work.",
            "head": {"ref": f"feat/{name}", "label": f"{owner}:feat/{name}", "repo": {"full_name": f"{owner}/greeter"}},
            "base": {"ref": base}}


def build_roadmap(name, dest):
    """Several archived changes on the store's main, one per roadmap status row; the roadmap lists them all, plus planned
    changes behind them. Both repos are clean on main."""
    code, store = dest / "code", dest / "store"
    pr = name.endswith("pr")
    store_base(dest, settings=(PR_SETTINGS if pr else "finish: local\n") + ROADMAP_SETTINGS)
    if pr:
        git(code, "remote", "add", "origin", f"https://github.com/{PR_SLUG}.git")
        git(store, "remote", "add", "origin", f"https://github.com/{STORE_SLUG}.git")
        install_fake_gh(dest)
        unreachable_proxy(dest)  # every git fetch fails; gh (the fake) works
        archive_in_store(store, "2026-10-07-add-greeting", "feat(add-greeting): archive change (#1)")
        archive_in_store(store, "2026-10-08-add-farewell", "feat(add-farewell): archive change (#2)")
        archive_in_store(store, "2026-10-08-add-shout", "feat(add-shout): archive change (#3)")
        archive_in_store(store, "2026-10-09-add-metrics", "feat(add-metrics): archive change (#4)")
        archive_in_store(store, "2026-10-09-plan-release", "feat(plan-release): archive change (#5)", marker=True)  # squash-merged, branch deleted
        write(code, "add-greeting-1.1.txt", "task 1.1 of add-greeting\n")  # the squash-merged code PR #1
        git(code, "add", "-A")
        git(code, "commit", "-q", "-m", "feat(add-greeting): add greet (#1)")
        farewell = code_branch(code, "add-farewell")  # task 1.1 cherry-picked onto main, PR #2 still open
        cherry_pick(code, farewell[0])
        pulls = [gh_pull(1, "add-greeting", merged=True),
                 gh_pull(2, "add-farewell"),
                 gh_pull(3, "add-shout"),  # the change's own PR: open
                 gh_pull(4, "add-shout", merged=True, owner="forkuser"),  # a fork's same-named branch, merged into main
                 gh_pull(5, "add-metrics", merged=True, base="integration")]  # merged, but not into main
        repos = {PR_SLUG: {"default_branch": "main", "pulls": pulls}, STORE_SLUG: {"default_branch": "main", "pulls": []}}
        write(dest, "gh-state.json", json.dumps({"user": "eval-bot", "tokens": {"eval-bot": "eval-token"}, "repos": repos}, indent=2))
        roadmap_file(code, [("add-greeting", "greet function"), ("add-farewell", "farewell function (after `add-greeting`)"),
                            ("add-shout", "shout function (after `add-greeting`)"), ("add-metrics", "usage metrics (after `add-greeting`)"),
                            ("plan-release", "release plan, documents only (after `add-greeting`)"),
                            ("add-share", "share greetings (after `add-shout`)"), ("add-report", "usage report (after `add-metrics`)"),
                            ("add-export", "export greetings (after `plan-release`)")])
    else:
        archive_in_store(store, "2026-10-07-add-greeting", "feat(add-greeting): archive change")
        archive_in_store(store, "2026-10-08-add-logging", "feat(2026-10-08-add-logging): archive change")  # the change name carries the date
        archive_in_store(store, "2026-10-09-add-farewell", "feat(add-farewell): archive change")
        for n in ("add-greeting", "2026-10-08-add-logging"):
            code_branch(code, n)
            merge_into_main(code, f"feat/{n}", n)
        farewell = code_branch(code, "add-farewell")  # task 1.1 cherry-picked onto main; the branch is never merged
        cherry_pick(code, farewell[0])
        roadmap_file(code, [("add-greeting", "greet function"), ("2026-10-08-add-logging", "logging (after `add-greeting`)"),
                            ("add-farewell", "farewell function (after `add-greeting`)"), ("add-shout", "shout function (after `add-farewell`)"),
                            ("add-metrics", "usage metrics (after `2026-10-08-add-logging`)")])


HOOK_MESSAGE = "post-checkout: hook failed (eval)"


def failing_post_checkout(repo):
    """A post-checkout hook that fails after git has created and switched to the branch. Write it last: the fixture's own
    checkouts would trigger it. Git for Windows runs it through its bundled sh."""
    write(repo, ".git/hooks/post-checkout", f'#!/bin/sh\necho "{HOOK_MESSAGE}" >&2\nexit 1\n')
    (repo / ".git" / "hooks" / "post-checkout").chmod(0o755)


def build_roadmap_close_locked(dest, hook=False):
    """Local mode, planning in a store. M1's only change (add-greeting) is done: its archive is on the store's main and
    code main has merge: add-greeting. Its exit criterion is agent-verified and passes. Another session holds the
    store's gate lock right now. Both repos are clean on main. fixture-state.json records the tips and the owner file.
    hook: no lock is held; instead the code repo's post-checkout hook fails (the store has none)."""
    code, store = dest / "code", dest / "store"
    store_base(dest, settings="finish: local\n" + ROADMAP_SETTINGS)
    archive_in_store(store, "2026-10-07-add-greeting", "feat(add-greeting): archive change")
    code_branch(code, "add-greeting")
    git(code, "checkout", "-q", "feat/add-greeting")
    task_code(code, "1.1")  # real greet() and tests, so the exit criterion passes on main
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "feat(add-greeting): task 1.1 Add greet(name) with tests")
    merge_into_main(code, "feat/add-greeting", "add-greeting")
    write(code, "openspec/roadmap.md",
          "# Greeter Roadmap\n\nStrategy: openspec/strategy.md · Architecture: openspec/architecture.md\n\n"
          "<!-- Status is derived: a change is done when archived; a milestone is done when its changes are done and its exit criteria pass. Do not add status checkboxes for changes. -->\n\n"
          "## Now: M1 - Greetings\n\n**Outcome:** Users get a greeting by name.\n\n"
          "**Exit criteria:**\n- `python -m unittest -q` passes on main (agent)\n\n"
          "**Changes** (in order; each about one PR):\n1. `add-greeting` - greet function\n\n"
          "## Next: M2 - Farewells\n\nFarewells and shouting greetings.\n\n"
          "## Later\n\n- M3 - Sharing: greetings shared between teams\n\n## Done\n")
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "docs: add project roadmap")
    tip = lambda r: subprocess.run(["git", "rev-parse", "main"], cwd=r, check=True, capture_output=True, text=True).stdout.strip()
    if hook:
        write(dest, "fixture-state.json", json.dumps({"code_main": tip(code), "store_main": tip(store)}, indent=2))
        failing_post_checkout(code)
        return
    gate_lock(store, datetime.now(timezone.utc), change="add-csv-export")  # another session is in its gate right now
    lock = Path(subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=store,
                               check=True, capture_output=True, text=True).stdout.strip()) / "specwright-gate.lock"
    write(dest, "fixture-state.json", json.dumps({"code_main": tip(code), "store_main": tip(store),
                                                  "owner": (lock / "owner").read_text(encoding="utf-8")}, indent=2))


MILESTONE_END_ROADMAP = (
    "# Greeter Roadmap\n\nStrategy: openspec/strategy.md · Architecture: openspec/architecture.md\n\n"
    "<!-- Status is derived: a change is done when archived; a milestone is done when its changes are done and its exit criteria pass. Do not add status checkboxes for changes. -->\n\n"
    "## Now: M1 - Greetings\n\n**Outcome:** Users get a greeting by name.\n\n"
    "**Exit criteria:**\n- {criterion}\n\n"
    "**Changes** (in order; each about one PR):\n1. `add-greeting` - greet function\n\n"
    "## Next: M2 - Farewells\n\nFarewells and shouting greetings.\n\n"
    "**Split agreed:** 2026-10-01\n\n"
    "**Changes** (in order; each about one PR):\n1. `add-farewell` - farewell function\n2. `add-shout` - shout function (after `add-farewell`)\n\n"
    "## Later\n\n- M3 - Sharing: greetings shared between teams\n\n## Done\n")


def build_roadmap_milestone_end(repo, user_verified):
    """Repo-local, local mode. M1's only change (add-greeting) is archived and merged on main (greet() and its tests are real).
    Its exit criterion is user-verified with no recorded result (user_verified) or agent-verified and passing. Next (M2) lists
    two changes under a `Split agreed:` line. .git/fixture-state.json records main's tip and the roadmap text."""
    base(repo)
    write(repo, "openspec/specwright.yaml", "finish: local\n" + ROADMAP_SETTINGS)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "chore: roadmap settings")
    code_branch(repo, "add-greeting")
    git(repo, "checkout", "-q", "feat/add-greeting")
    task_code(repo, "1.1")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat(add-greeting): task 1.1 Add greet(name) with tests")
    archive_in_store(repo, "2026-10-07-add-greeting", "feat(add-greeting): archive change")
    merge_into_main(repo, "feat/add-greeting", "add-greeting")
    criterion = ("Users find the greetings friendly after trying them (user)" if user_verified
                 else "`python -c \"from greet import greet; assert greet('Ada') == 'Hello, Ada!'\"` exits 0 on main (agent)")
    write(repo, "openspec/roadmap.md", MILESTONE_END_ROADMAP.format(criterion=criterion))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "docs: add project roadmap")
    rev = lambda r: subprocess.run(["git", "rev-parse", r], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    write(repo, ".git/fixture-state.json", json.dumps({"main": rev("main"), "roadmap_commit": rev("HEAD"),
                                                       "roadmap": (repo / "openspec/roadmap.md").read_text(encoding="utf-8")}, indent=2))


def build_roadmap_next_gap(repo, dirty):
    """Repo-local, local mode. M1's only change (add-greeting) is archived and merged on main, but its agent-verified exit
    criterion (farewell) fails, so **next** proposes a gap-closing change. `dirty`: README has an uncommitted edit, so the
    branch gate stops. .git/fixture-state.json (outside the work tree) records main's tip, the roadmap and its commit."""
    base(repo)
    write(repo, "openspec/specwright.yaml", "finish: local\n" + ROADMAP_SETTINGS)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "chore: roadmap settings")
    code_branch(repo, "add-greeting")
    git(repo, "checkout", "-q", "feat/add-greeting")
    archive_in_store(repo, "2026-10-07-add-greeting", "feat(add-greeting): archive change")
    merge_into_main(repo, "feat/add-greeting", "add-greeting")
    write(repo, "openspec/roadmap.md",
          "# Greeter Roadmap\n\nStrategy: openspec/strategy.md · Architecture: openspec/architecture.md\n\n"
          "<!-- Status is derived: a change is done when archived; a milestone is done when its changes are done and its exit criteria pass. Do not add status checkboxes for changes. -->\n\n"
          "## Now: M1 - Greetings\n\n**Outcome:** Users get a greeting and a farewell by name.\n\n"
          "**Exit criteria:**\n- `python -c \"from greet import farewell; assert farewell('Ada') == 'Goodbye, Ada!'\"` exits 0 on main (agent)\n\n"
          "**Changes** (in order; each about one PR):\n1. `add-greeting` - greet function\n\n"
          "## Next: M2 - Sharing\n\nGreetings shared between teams.\n\n## Later\n\n- M3 - Localisation: translated greetings\n\n## Done\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "docs: add project roadmap")
    rev = lambda r: subprocess.run(["git", "rev-parse", r], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    state = {"main": rev("main"), "roadmap_commit": rev("HEAD"),
             "roadmap": (repo / "openspec/roadmap.md").read_text(encoding="utf-8")}
    write(repo, ".git/fixture-state.json", json.dumps(state, indent=2))
    if dirty:
        write(repo, "README.md", "# greeter\n\nA tiny greeting library. WIP edit.\n")


def build_branch_store(name, dest):
    """Store-version gate fixtures (specwright-branch, store step 2) and the update lock (store step 1).
    The project's install version (openspec/.specwright/VERSION) is committed in the code repo and the store's record
    (openspec/.specwright/STORE: version and owner) in the store, both clean on main."""
    code, store = dest / "code", dest / "store"
    store_base(dest)
    if name == "eval-branch-store-update-lock":
        # another project's update holds the store: its owner file is the update's, not a change gate's
        when = datetime.now(timezone.utc)
        gate_lock(store, when, owner=(f"time: {when.isoformat(timespec='seconds')}\n"
                                      "change: specwright-update 0.5.0 -> 0.6.0\ncode: C:/elsewhere/code\ntoken: 0123456789abcdef\n"))
        return
    project_version, store_version = {"eval-branch-store-version-match": ("0.6.1", "0.6.0"),
                                      "eval-branch-store-version-behind": ("0.5.0", "0.6.0")}[name]
    write(code, "openspec/.specwright/VERSION", project_version + "\n")
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "chore: record install version")
    write(store, "openspec/.specwright/STORE", f"version: {store_version}\nowner: alice-laptop\n")
    git(store, "add", "-A")
    git(store, "commit", "-q", "-m", "chore: record store version")


def build_store(name, dest):
    """Fixtures whose planning lives outside the code repo (or in a folder inside it)."""
    code, store = dest / "code", dest / "store"
    if name == "eval-store-branch-clean":
        store_base(dest)  # both repos clean on main, store registered, code points at it
    elif name == "eval-store-branch-dirty":
        store_base(dest)
        with (store / "openspec/config.yaml").open("a", encoding="utf-8", newline="\n") as f:
            f.write("# local edit, not committed\n")  # tracked store file outside the change dir
    elif name == "eval-store-branch-busy":
        store_base(dest)
        git(store, "checkout", "-q", "-b", "feat/other-change")
        write(store, "openspec/changes/other-change/proposal.md", "## Why\n\nAnother change in progress.\n")
        git(store, "add", "-A")
        git(store, "commit", "-q", "-m", "feat(other-change): add planning artifacts")
    elif name == "eval-store-branch-reused-name":
        store_base(dest)
        write(store, "openspec/changes/archive/2026-09-01-add-csv-export/proposal.md", ARCHIVED_CSV)
        git(store, "add", "-A")
        git(store, "commit", "-q", "-m", "merge: add-csv-export")  # an earlier change of the same name, archived on main
    elif name == "eval-store-branch-reused-name-origin":
        # an earlier change of the same name was archived and merged from another checkout: it is on the store's
        # origin main only, and this checkout's local main has not been pulled
        store_base(dest)
        bare = dest / "so.git"  # short: Windows paths under the eval run dir near MAX_PATH
        git(dest, "init", "-q", "--bare", "-b", "main", posix(bare))
        git(store, "remote", "add", "origin", posix(bare))
        git(store, "push", "-q", "origin", "main")
        other = dest / "oc"
        git(dest, "clone", "-q", posix(bare), posix(other))
        for k, v in (("user.name", "Other Bot"), ("user.email", "other@example.invalid"), ("commit.gpgsign", "false")):
            git(other, "config", k, v)
        write(other, "openspec/changes/archive/2026-09-01-add-csv-export/proposal.md", ARCHIVED_CSV)
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "merge: add-csv-export")
        git(other, "push", "-q", "origin", "main")
        rmtree(other)
    elif name == "eval-store-branch-hook-fail":
        store_base(dest)  # as eval-store-branch-clean, then the store's post-checkout hook fails
        failing_post_checkout(store)
    elif name == "eval-store-branch-locked":
        store_base(dest)
        gate_lock(store, datetime.now(timezone.utc))  # another session is in its gate right now
    elif name == "eval-store-branch-stale-lock":
        store_base(dest)
        gate_lock(store, datetime.now(timezone.utc) - timedelta(days=2))  # left by an interrupted session
    elif name == "eval-store-apply":
        store_base(dest)
        for r in (code, store):
            git(r, "checkout", "-q", "-b", "feat/add-greeting")
        change_artifacts(store)  # planning lives in the store, uncommitted
        write(code, "scratch-notes.txt", "personal notes - not part of the change\n")
    elif name == "eval-store-apply-groups":
        store_base(dest, settings=GROUP_SETTINGS)
        for r in (code, store):
            git(r, "checkout", "-q", "-b", "feat/add-greeting")
        group_artifacts(store, "groups")  # planning lives in the store, uncommitted
        write(code, "scratch-notes.txt", "personal notes - not part of the change\n")
    elif name == "eval-store-group-code-half":
        apply_base(dest, kind="groups")  # 1.1-1.3 ticked in the store, group 1's code uncommitted, no group 1 commit anywhere
        tick(store, "1.1", "1.2", "1.3")
        group_code(code, 1)
    elif name == "eval-store-group-store-half":
        apply_base(dest, kind="groups")  # group 1's code commit exists; its store commit failed (ticks uncommitted)
        paths = group_code(code, 1)
        git(code, "add", "--", *paths)
        git(code, "commit", "-q", "-m", group_msg("groups", 1), "--", *paths)
        tick(store, "1.1", "1.2", "1.3")
    elif name == "eval-store-group-noop":
        apply_base(dest, kind="noop")  # groups 1 and 2 done as pairs; group 3 ticked in the store, no code, code tree clean
        commit_group(code, store, "noop", 1)
        commit_group(code, store, "noop", 2)
        tick(store, "3.1", "3.2")
    elif name == "eval-store-apply-wrong-branch":
        store_base(dest)
        git(code, "checkout", "-q", "-b", "feat/add-greeting")  # the store stays on main
        change_artifacts(store)  # planning artifacts uncommitted on the store's main
    elif name == "eval-store-apply-reconcile":
        apply_base(dest)  # 1.1: code commit made, the store commit failed (tick uncommitted)
        commit_code(code, "1.1")
        tick(store, "1.1")
    elif name == "eval-store-apply-multi-gap":
        apply_base(dest)  # 1.1 and 1.2 have code commits; both ticks sit in one uncommitted tasks.md diff
        commit_code(code, "1.1")
        commit_code(code, "1.2")
        tick(store, "1.1", "1.2")
    elif name == "eval-store-apply-orphan-tick":
        apply_base(dest)  # 1.1 done; 1.2 ticked, its code changes uncommitted: the session stopped before the code commit
        done_pair(dest, "1.1")
        tick(store, "1.2")
        task_code(code, "1.2")
    elif name == "eval-store-apply-noop-gap":
        apply_base(dest, verify_last=True)  # 2.1 is verification-only: ticked, no code commit, store commit failed
        done_pair(dest, "1.1")
        done_pair(dest, "1.2")
        tick(store, "2.1")
    elif name == "eval-store-complete-gap":
        apply_base(dest)  # every task ticked and committed in code; the last store commit failed
        done_pair(dest, "1.1")
        done_pair(dest, "1.2")
        commit_code(code, "2.1")
        tick(store, "2.1")
    elif name == "eval-store-unregistered":
        store_base(dest, registered=False)  # config.yaml says `store: team-plans`; nothing is registered
    elif name == "eval-store-other-worktree":
        store_base(dest, store_worktree=True)  # the store is the `plans` worktree of the code repo
        git(code, "checkout", "-q", "-b", "feat/add-greeting")
        change_artifacts(store)
    elif name == "eval-store-finish-local":
        finish_ready(dest)
        write(store, "store-notes.txt", "personal notes - not part of the change\n")
        archive_change(dest, "add-greeting")
    elif name == "eval-store-finish-dated":
        finish_ready(dest, "2026-10-07-add-greeting", code_work=False)  # planning-only and date-prefixed
        archive_change(dest, "2026-10-07-add-greeting")
    elif name == "eval-store-finish-planning-only":
        finish_ready(dest, code_work=False)
        archive_change(dest, "add-greeting")
    elif name == "eval-store-finish-store-conflict":
        finish_ready(dest)
        diverge_main(store, "openspec/specs/greeting/spec.md", CONFLICT_SPEC, CONFLICT_STORE)
        archive_change(dest, "add-greeting")
    elif name == "eval-store-finish-code-conflict":
        finish_ready(dest)
        diverge_main(code, "greet.py", '"""Greeting helpers."""\n\n\ndef greet(name):\n    return "Dear " + name + ","\n', CONFLICT_CODE)
        archive_change(dest, "add-greeting")
    elif name in ("eval-store-finish-resume-code-merge", "eval-store-finish-resume-code-merge-from-main"):
        finish_ready(dest)  # the interrupted finish merged and deleted the store branch; the code merge never ran
        archive_change(dest, "add-greeting")
        git(store, "add", "-A")
        git(store, "commit", "-q", "-m", "feat(add-greeting): archive change")
        merge_into_main(store)
        out = lambda *a: subprocess.run(["git", *a], cwd=store, check=True, capture_output=True, text=True).stdout.strip()
        code_tree = subprocess.run(["git", "rev-parse", "feat/add-greeting^{tree}"], cwd=code, check=True, capture_output=True, text=True).stdout.strip()
        write(dest, "fixture-state.json", json.dumps({"store_main": out("rev-parse", "main"), "store_commits": int(out("rev-list", "--count", "--all")),
                                                      "code_tree": code_tree}, indent=2))  # code_tree: what a recovered code main must hold
        if name.endswith("-from-main"):
            git(code, "checkout", "-q", "main")  # the code repo was left on main; its branch still has the commits
    elif name == "eval-store-archive-on-main":
        finish_ready(dest)  # both branches merged into main, then the archive ran with the store on main
        for r in (code, store):
            merge_into_main(r)
        archive_change(dest, "add-greeting")
    elif name == "eval-store-archive-on-main-pr-open":
        finish_ready(dest)  # the store's change is merged; the code PR is still open on feat/add-greeting
        merge_into_main(store)
        open_code_pr(dest, code)
        archive_change(dest, "add-greeting")
    elif name == "eval-store-ship-push-rejected":
        pr_pair_base(dest)  # both repos have a GitHub origin; any push dies at the unreachable proxy
    elif name == "eval-store-ship-code-push-rejected":
        pr_pair_base(dest, store_push_ok=True)  # the shim lets the store push through; the code push dies at the proxy
    elif name == "eval-store-ship-code-push-rejected-store-pr-open":
        pr_pair_base(dest, store_push_ok=True, store_pr=True)  # the same, with store PR #3 already open
    elif name == "eval-store-archive-before-merge-local-store":
        pr_pair_base(dest, store_origin=False, code_pr=True)  # code PR #7 is open and ready; the store has no GitHub origin
    elif name == "eval-store-roadmap-close-locked":
        build_roadmap_close_locked(dest)
    elif name == "eval-store-roadmap-close-hook-fail":
        build_roadmap_close_locked(dest, hook=True)
    elif name in ("eval-store-roadmap-local", "eval-store-roadmap-pr"):
        build_roadmap(name, dest)
    elif name == "eval-nested-root-finish":
        nested_base(dest)
        finished(code, code / "planning")
    elif name == "eval-root-outside-git":
        store_base(dest, store_git=False)  # the store is a plain directory
        git(code, "checkout", "-q", "-b", "feat/add-greeting")
        change_artifacts(store)
    else:
        raise SystemExit(f"unknown eval {name}")


INSTALL_CONFIG = "schema: spec-driven\n\n# Project context (optional)\n# Add only constraints that should guide OpenSpec artifacts and workflows.\n"  # what `openspec store setup` writes, shortened
INSTALL_OTHER_CONFIG = "schema: team-flow\n\ncontext: |\n  Team convention: write every spec in British English.\n"


def _install_store(store, kind, dest):
    _init(store)
    root = store / "planning" if kind == "nested" else store
    write(root, "openspec/config.yaml", INSTALL_CONFIG)
    write(root, "openspec/specs/.gitkeep", "")
    write(root, "openspec/changes/archive/.gitkeep", "")
    if kind == "other-schema":
        openspec(dest, "schema", "init", "team-flow", "--description", "The team's own flow", "--artifacts", "proposal,tasks",
                 "--no-default", cwd=root)
        write(root, "openspec/config.yaml", INSTALL_OTHER_CONFIG)
    if kind == "nested":
        write(store, "README.md", "# team plans\n")
    git(store, "add", "-A")
    git(store, "commit", "-q", "-m", "chore: initial store")


def install_base(dest, kind):
    """Install evals: the code repo is a fresh project (no specwright.yaml, no skills) whose openspec/ holds only the
    `store: team-plans` pointer; its planning root is a healthy, registered, empty OpenSpec root, as `openspec store setup`
    leaves one (config.yaml naming spec-driven, specs/ and changes/archive/ with .gitkeep files).
    "store": the root is <dest>/store.
    "other-schema": the same, but the store's config.yaml names the project-local schema team-flow (in the store) and
    a context line of the team's own.
    "nested": the root is <dest>/store/planning, inside the store repo, whose top level has no openspec/.
    Everything is committed and clean; the install must leave the store's files uncommitted."""
    code, store = dest / "code", dest / "store"
    code_repo(code, settings=None)
    (dest / "bin").mkdir()
    root = store / "planning" if kind == "nested" else store
    if kind == "other-schema":  # runs the openspec CLI against this fixture's registry: built here, not cached
        _install_store(store, kind, dest)
    else:  # a copy of one built once per process (before register, so nothing in it names a path)
        fixturecache.copy(("git-workflow.install_store", kind), lambda d: _install_store(d, kind, dest), store)
    register(dest, root, "team-plans")
    git(store, "add", "-A")  # registration wrote .openspec-store/store.yaml
    git(store, "commit", "-q", "-m", "chore: register store")
    env_file(dest)


def specwright_source(dest):
    """<dest>/specwright-src stands in for the Specwright repository: its only release tag is v0.5.0, whose tree has no
    scripts/update.sh, and main is one commit ahead (VERSION 0.6.0, with the update script). An install prompt that picks the
    latest release tag therefore finds one below its minimum release (0.6.0)."""
    src = dest / "specwright-src"
    init(src)
    write(src, "VERSION", "0.5.0\n")
    write(src, "OPENSPEC_VERSION", "1.14.1\n")
    write(src, "skills/specwright-commit/SKILL.md", "---\nname: specwright-commit\n---\nCommit each task.\n")
    shutil.copytree(ROOT / "schemas" / "specwright", src / "schemas" / "specwright")
    shutil.copytree(ROOT / "templates" / "openspec", src / "templates" / "openspec")
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "chore: release 0.5.0")
    git(src, "tag", "-a", "v0.5.0", "-m", "v0.5.0")
    write(src, "VERSION", "0.6.0\n")
    write(src, "scripts/update.sh", "#!/usr/bin/env bash\necho '{\"ok\": true, \"interface\": 1}'\n")
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "feat: update script")


def references_base(dest, registered=True, ref_id="team-plans"):
    """<dest>/code keeps its own openspec/ root (schema, specs, config.yaml with `references: [team-plans]`),
    so planning is repo-local; <dest>/team-plans is the referenced store: a git repo holding a shared spec,
    clean on main, registered (with the isolated registry) when `registered`. Either way the code repo is on
    feat/add-greeting with the change's planning artifacts uncommitted, and carries a scratch-notes.txt.
    Unregistered: the referenced folder stays on disk (it holds the same files) but the registry is empty,
    so OpenSpec reports the reference as unresolved."""
    code, ref = dest / "code", dest / ref_id
    base(code)
    with (code / "openspec/config.yaml").open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"\nreferences:\n  - {ref_id}\n")
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "chore: declare references")
    (dest / "bin").mkdir()
    init(ref)
    store_content(ref)
    write(ref, "openspec/specs/audit/spec.md", "# audit Specification\n\n## Purpose\n\nShared audit rules from the platform team.\n\n## Requirements\n\n### Requirement: Audit trail\nThe system SHALL log every user-facing message.\n\n#### Scenario: Message logged\n- **WHEN** a message is sent\n- **THEN** an audit entry is written\n")
    git(ref, "add", "-A")
    git(ref, "commit", "-q", "-m", "chore: initial store")
    if registered:
        openspec(dest, "store", "register", posix(ref), "--id", ref_id, "--yes")
        git(ref, "add", "-A")  # registration wrote .openspec-store/store.yaml
        git(ref, "commit", "-q", "-m", "chore: register store")
    env_file(dest)
    git(code, "checkout", "-q", "-b", "feat/add-greeting")
    change_artifacts(code)  # planning lives in the code repo, uncommitted
    write(code, "scratch-notes.txt", "personal notes - not part of the change\n")


MERGED_CLOSES = 12  # the issue the merged PR's description closes, already closed in the fake gh


def origin_with_main(repo, ref):
    """A local bare origin <repo>/ob.git holding `ref` as main, and the github.com origin remote with main tracking it. The remote's
    URL stays on github.com (the finish skill fences GitHub fetches and pulls by it); origin_shim reaches the bare repo for pull and fetch."""
    write(repo, ".git/info/exclude", "/ob.git/\n")  # before any `add -A`: the bare repo lives inside the work tree
    bare = repo / "ob.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", posix(bare)], check=True, capture_output=True, text=True)
    git(repo, "push", "-q", posix(bare), f"{ref}:refs/heads/main")
    git(repo, "remote", "add", "origin", f"https://github.com/{PR_SLUG}.git")
    git(repo, "update-ref", "refs/remotes/origin/main", ref)
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    git(repo, "config", "branch.main.remote", "origin")
    git(repo, "config", "branch.main.merge", "refs/heads/main")


def origin_shim(repo):
    """bin/git: the watch-merge shim without its merge condition, so `pull` and `fetch` in the repo always read <repo>/ob.git through a
    command-scoped url.<bare>.insteadOf; `git remote get-url origin` still prints the github.com URL."""
    shim = MERGED_SHIM.replace("@REAL@", msys(shutil.which("git") or "git")).replace("@CODE@", posix(repo)) \
        .replace("@BARE@", posix(repo / "ob.git")).replace("@LOG@", posix(repo / "gh-log.jsonl")).replace("@URL@", f"https://github.com/{PR_SLUG}.git")
    write(repo, "bin/git", shim)
    (repo / "bin" / "git").chmod(0o755)


RELEASE_VERSION = "0.5.0"


def release_settings(enabled=True, auto=False):
    """The `release:` block of openspec/specwright.yaml the release evals use: VERSION is the only (primary) version file."""
    return (f"release:\n  enabled: {'true' if enabled else 'false'}\n  auto: {'true' if auto else 'false'}\n  github_release: true\n"
            "  tag: \"v{version}\"\n  version_files:\n    VERSION: '^(\\d+\\.\\d+\\.\\d+)$'\n")


RELEASE_SHIM = r'''#!/bin/bash
# git shim for the release evals: real git for everything, except `pull`, `fetch`, `push` and `ls-remote` in the code repo, which read or
# write the local bare repo (@BARE@) through a command-scoped url.<bare>.insteadOf, so origin's URL stays on github.com. With GATED=1
# `pull` and `fetch` do so only once the fake gh logged a merge of PR #7. Before it, `fetch` reads @PRE@ (origin as it was before the
# merge, which watch's version check fetches) and `pull` hits the unreachable proxy; `push` and `ls-remote` are never gated. Every other
# network command hits the unreachable proxy.
REAL="@REAL@"
CODE="@CODE@"
BARE="@BARE@"
PRE="@PRE@"
LOG="@LOG@"
URL="@URL@"
GATED=@GATED@
dir=.
a=("$@")
while [ ${#a[@]} -gt 0 ]; do
  case "${a[0]}" in
    -C) dir="${a[1]}"; a=("${a[@]:2}") ;;
    -c) a=("${a[@]:2}") ;;
    -*) a=("${a[@]:1}") ;;
    *) break ;;
  esac
done
sub="${a[0]:-}"
case "$sub" in pull|fetch|push|ls-remote) ;; *) exec "$REAL" "$@" ;; esac
top=$("$REAL" -C "$dir" rev-parse --show-toplevel 2>/dev/null)
lc() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
if [ "$(lc "$top")" = "$(lc "$CODE")" ]; then
  if [ "$sub" = push ] || [ "$sub" = ls-remote ] || [ "$GATED" = 0 ] || grep -q 'pulls/7/merge' "$LOG" 2>/dev/null; then
    exec "$REAL" -c "url.$BARE.insteadOf=$URL" "$@"
  fi
  if [ "$sub" = fetch ]; then
    exec "$REAL" -c "url.$PRE.insteadOf=$URL" "$@"
  fi
fi
exec "$REAL" "$@"
'''


BASH_SHIM = r'''#!/bin/sh
# bash shim for the release evals: a `bash .../release.sh` run (and everything it starts) reads GIT_CONFIG_GLOBAL=@REWRITE@, which
# reaches the local bare origin through a global url.<bare>.insteadOf. release.sh's own git calls (ls-remote, tag, push) and the fake
# gh's `git ls-remote` are spawned by Python, which on Windows never finds the extensionless bin/git shim; the rewrite stays out of
# every other command, so `git remote get-url origin` (read by pr-pair.sh and the agent) keeps printing the github.com URL.
for a in "$@"; do
  case "$a" in
    release.sh|*/release.sh) GIT_CONFIG_GLOBAL="@REWRITE@"; export GIT_CONFIG_GLOBAL; break ;;
  esac
done
exec "@BASH@" "$@"
'''


def release_shim(repo, gated):
    """bin/git and bin/bash for the release evals (RELEASE_SHIM, BASH_SHIM): <repo>/ob.git is the reachable origin. `gated` holds
    git pull and fetch back until the fake gh logged the merge of PR #7; before it, fetch reads <repo>/ob-pre.git (origin before the
    merge; only a gated fixture creates it). state/gitconfig-release is the rewrite config bin/bash hands
    to release.sh: the fixture's proxy config plus url.<bare>.insteadOf."""
    url, bare = f"https://github.com/{PR_SLUG}.git", posix(repo / "ob.git")
    rewrite = repo / "state" / "gitconfig-release"
    write(repo, "state/gitconfig-release", (repo / "gitconfig").read_text(encoding="utf-8") + f'[url "{bare}"]\n\tinsteadOf = {url}\n')
    shim = RELEASE_SHIM.replace("@REAL@", msys(shutil.which("git") or "git")).replace("@CODE@", posix(repo)) \
        .replace("@BARE@", bare).replace("@PRE@", posix(repo / "ob-pre.git")).replace("@LOG@", posix(repo / "gh-log.jsonl")) \
        .replace("@URL@", url).replace("@GATED@", "1" if gated else "0")
    write(repo, "bin/git", shim)
    write(repo, "bin/bash", BASH_SHIM.replace("@REWRITE@", posix(rewrite)).replace("@BASH@", msys(bashexe.bash() or "bash")))
    for n in ("git", "bash"):
        (repo / "bin" / n).chmod(0o755)


RELEASE_EXCLUDE = "/bin/\n/eval.env\n/gh-state.json\n/gh-log.jsonl\n/git-trace.log\n/gitconfig\n/state/\n/xdg-data/\n/xdg-config/\n/ob.git/\n"


def build_finish_resume_merged(repo, squash, release=None):
    """Repo-local, `finish: pr` as eval-bot, origin on GitHub, fake gh. The change's PR #7 was merged and the local branch is gone:
    main holds the archive directory (and the code) under the squash subject `Add greeting (#7)`, or, when not `squash`, under a merge
    commit `Merge pull request #7 ...` of the deleted feat/add-greeting. No change directory, a clean tree on main. The fake gh has
    PR #7 merged into main, its description closing issue #12, which is closed. The run's helper files live in the repo directory,
    hidden through .git/info/exclude: eval.env (source it, with the repo as the working directory), bin/gh, gh-state.json,
    gh-log.jsonl (the fake gh's call log) and git-trace.log (GIT_TRACE: every git command the run made).
    .git/fixture-state.json records main's tip and the commit count.
    `release` (the eval-finish-release-* fixtures; squash only): the `release:` settings block, the roadmap setting and file, and a VERSION
    file that reads 0.4.0 before the PR and 0.5.0 in the squash commit `Add greeting (#7)`. No tag exists anywhere. The shim then also
    reads the bare origin for `ls-remote` and `push` (release_shim), so a tag push is observable in ob.git."""
    base(repo)
    write(repo, "openspec/specwright.yaml", PR_SETTINGS + (release + ROADMAP_SETTINGS if release is not None else ""))
    if release is not None:
        write(repo, "VERSION", "0.4.0\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "chore: pr settings")
    if release is not None:
        roadmap_file(repo, [("add-greeting", "greet and farewell"), ("add-shout", "shout")])
    if squash:
        if release is not None:
            write(repo, "VERSION", f"{RELEASE_VERSION}\n")
        implemented(repo)
        archive_in_store(repo, "2026-10-07-add-greeting", "Add greeting (#7)")
        title = "Add greeting"
    else:
        git(repo, "checkout", "-q", "-b", "feat/add-greeting")
        implemented(repo)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "feat(add-greeting): implement tasks 1.1-2.1")
        archive_in_store(repo, "2026-10-07-add-greeting", "feat(add-greeting): archive change")
        git(repo, "checkout", "-q", "main")
        git(repo, "merge", "-q", "--no-ff", "feat/add-greeting", "-m", "Merge pull request #7 from acme/feat/add-greeting")
        git(repo, "branch", "-q", "-d", "feat/add-greeting")
        title = "feat(add-greeting): add greet and farewell"
    origin_with_main(repo, "main")
    dest = repo
    install_fake_gh(dest)
    unreachable_proxy(dest)
    env_file(dest, GIT_TRACE=posix(dest / "git-trace.log"))
    if release is not None:
        release_shim(repo, gated=False)
    else:
        origin_shim(repo)
    pr = gh_pull(7, "add-greeting", merged=True)
    pr.update({"title": title, "body": f"Adds greet and farewell.\n\nCloses #{MERGED_CLOSES}",
               "closing_refs": [{"number": MERGED_CLOSES, "repo": PR_SLUG}]})
    st = {"user": "eval-bot", "tokens": {"eval-bot": "eval-token"},
          "repos": {PR_SLUG: {"default_branch": "main", "pulls": [pr],
                              "issues": {str(MERGED_CLOSES): {"state": "CLOSED", "timeline": [["CLOSED", "2026-10-09T10:00:05Z"]]}}}}}
    write(dest, "gh-state.json", json.dumps(st, indent=2))
    write(repo, ".git/info/exclude", "/bin/\n/eval.env\n/gh-state.json\n/gh-log.jsonl\n/git-trace.log\n/gitconfig\n/state/\n/xdg-data/\n/xdg-config/\n/ob.git/\n")
    rev = subprocess.run(["git", "rev-parse", "main"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    count = subprocess.run(["git", "rev-list", "--count", "--all"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    write(repo, ".git/fixture-state.json", json.dumps({"main": rev, "commits": int(count)}, indent=2))


def build_finish_resume_stale_main(repo):
    """Like build_finish_resume_merged, but local main is behind origin: it holds only an older change's archive
    (2026-09-01-add-greeting, the same change name), while origin's main (the local bare repo) additionally holds the merge commit of
    PR #7, which brings 2026-10-14-add-greeting. PR #7 is merged in the fake gh and feat/add-greeting is gone locally. A pull
    through the fixture's git shim fast-forwards main. .git/fixture-state.json records origin's tip as `main` and the stale tip."""
    base(repo)
    write(repo, "openspec/specwright.yaml", PR_SETTINGS)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "chore: pr settings")
    archive_in_store(repo, "2026-09-01-add-greeting", "chore: archive an earlier add-greeting change")
    out = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    stale = out("rev-parse", "main")
    origin_with_main(repo, "main")  # origin/main stays at the stale tip until the pull
    git(repo, "checkout", "-q", "-b", "feat/add-greeting")
    implemented(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat(add-greeting): implement tasks 1.1-2.1")
    archive_in_store(repo, "2026-10-14-add-greeting", "feat(add-greeting): archive change")
    git(repo, "checkout", "-q", "-b", "origin-tmp", "main")
    git(repo, "merge", "-q", "--no-ff", "feat/add-greeting", "-m", "Merge pull request #7 from acme/feat/add-greeting")
    new = out("rev-parse", "HEAD")
    git(repo, "push", "-q", posix(repo / "ob.git"), "origin-tmp:refs/heads/main")
    git(repo, "checkout", "-q", "main")
    git(repo, "branch", "-q", "-D", "origin-tmp")
    git(repo, "branch", "-q", "-D", "feat/add-greeting")
    install_fake_gh(repo)
    unreachable_proxy(repo)
    env_file(repo, GIT_TRACE=posix(repo / "git-trace.log"))
    origin_shim(repo)
    pr = gh_pull(7, "add-greeting", merged=True)
    pr.update({"title": "feat(add-greeting): add greet and farewell", "body": f"Adds greet and farewell.\n\nCloses #{MERGED_CLOSES}",
               "closing_refs": [{"number": MERGED_CLOSES, "repo": PR_SLUG}]})
    st = {"user": "eval-bot", "tokens": {"eval-bot": "eval-token"},
          "repos": {PR_SLUG: {"default_branch": "main", "pulls": [pr],
                              "issues": {str(MERGED_CLOSES): {"state": "CLOSED", "timeline": [["CLOSED", "2026-10-09T10:00:05Z"]]}}}}}
    write(repo, "gh-state.json", json.dumps(st, indent=2))
    write(repo, ".git/info/exclude", "/bin/\n/eval.env\n/gh-state.json\n/gh-log.jsonl\n/git-trace.log\n/gitconfig\n/state/\n/xdg-data/\n/xdg-config/\n/ob.git/\n")
    write(repo, ".git/fixture-state.json", json.dumps({"main": new, "stale": stale}, indent=2))


WATCH_REVIEWER = "chatgpt-codex-connector"
WATCH_SHIM = r'''#!/bin/bash
# git shim for the watch-merge evals: real git for everything, except `pull` and `fetch` in the code repo once the fake gh
# logged a merge of PR #7: those read the local bare repo (@BARE@) where origin's main already holds the squash commit, as
# GitHub's would after the merge. Before the merge they hit the unreachable proxy like any other network command.
REAL="@REAL@"
CODE="@CODE@"
BARE="@BARE@"
LOG="@LOG@"
URL="@URL@"
dir=.
a=("$@")
while [ ${#a[@]} -gt 0 ]; do
  case "${a[0]}" in
    -C) dir="${a[1]}"; a=("${a[@]:2}") ;;
    -c) a=("${a[@]:2}") ;;
    -*) a=("${a[@]:1}") ;;
    *) break ;;
  esac
done
if [ "${a[0]:-}" = pull ] || [ "${a[0]:-}" = fetch ]; then
  top=$("$REAL" -C "$dir" rev-parse --show-toplevel 2>/dev/null)
  lc() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
  if [ "$(lc "$top")" = "$(lc "$CODE")" ] && grep -q 'pulls/7/merge' "$LOG" 2>/dev/null; then
    exec "$REAL" -c "url.$BARE.insteadOf=$URL" "$@"
  fi
fi
exec "$REAL" "$@"
'''


MERGED_SHIM = WATCH_SHIM.replace(""" && grep -q 'pulls/7/merge' "$LOG" 2>/dev/null""", "")
assert MERGED_SHIM != WATCH_SHIM


def build_watch_merge(repo, agent, release=None):
    """Repo-local, `finish: pr` as eval-bot, origin on GitHub, fake gh. On feat/add-greeting with the change archived and committed
    (feat(add-greeting): archive change); PR #7 is open and ready in the fake gh (head = the branch tip, a green check, the required
    reviewer WATCH_REVIEWER reported with an approval on that head). `agent`: pr.merge agent with merge_method squash, otherwise the
    settings do not mention merging. A bare repo <repo>/ob.git holds origin's main as it stands after the squash merge (main plus one
    squash commit `Add greeting (#7)` with the branch's tree); the git shim lets `git pull --ff-only` read it only once the fake gh
    logged the merge of PR #7. The fake gh knows the branch feat/add-greeting at the tip, so the remote ref can be read and deleted.
    The run's helper files live in the repo directory, hidden through .git/info/exclude (eval.env, bin/, gh-state.json, gh-log.jsonl,
    git-trace.log, ob.git). .git/fixture-state.json records main's tip, the branch tip and its tree.
    `agent` variants also get the roadmap setting and file: the Now milestone lists add-greeting alone (expected_mode close in
    fixture-state.json), or with release also add-shout (expected_mode next).
    `release` (eval-agent-merge-release-auto): the `release:` settings block is added, main holds a
    VERSION file reading 0.4.0, and the branch bumps it to 0.5.0 (commit `feat(add-greeting): bump version to 0.5.0`), so the squash
    commit on origin's main reads 0.5.0. The shim (release_shim, gated on the merge) also reads and writes the bare origin for
    `ls-remote` and `push`, so a tag push is observable in ob.git."""
    base(repo)
    merging = "  merge: agent\n  merge_method: squash\n" if agent else ""
    write(repo, "openspec/specwright.yaml",
          f"finish: pr\ngithub:\n  login: eval-bot\npr:\n  poll_interval: 5s\n{merging}  reviewers:\n    {WATCH_REVIEWER}: {{ role: required }}\n"
          + ((release or "") + ROADMAP_SETTINGS if agent else ""))
    if release is not None:
        write(repo, "VERSION", "0.4.0\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "chore: pr settings")
    changes = [("add-greeting", "greet and farewell")] + ([("add-shout", "shout")] if release is not None else [])
    if agent:
        roadmap_file(repo, changes)
    finished(repo, repo)
    if release is not None:
        write(repo, "VERSION", f"{RELEASE_VERSION}\n")
        git(repo, "add", "VERSION")
        git(repo, "commit", "-q", "-m", f"feat(add-greeting): bump version to {RELEASE_VERSION}", "--", "VERSION")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat(add-greeting): archive change")
    out = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    tip, tree, main = out("rev-parse", "HEAD"), out("rev-parse", "HEAD^{tree}"), out("rev-parse", "main")
    write(repo, ".git/info/exclude", "/ob.git/\n")  # before any `add -A`: the bare repo lives inside the work tree
    bare = repo / "ob.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", posix(bare)], check=True, capture_output=True, text=True)
    git(repo, "checkout", "-q", "-b", "squash-tmp", "main")
    git(repo, "merge", "-q", "--squash", "feat/add-greeting")
    git(repo, "commit", "-q", "-m", "Add greeting (#7)")
    squash = out("rev-parse", "HEAD")
    git(repo, "push", "-q", posix(bare), "squash-tmp:refs/heads/main")
    git(repo, "checkout", "-q", "feat/add-greeting")
    git(repo, "branch", "-q", "-D", "squash-tmp")
    git(repo, "remote", "add", "origin", f"https://github.com/{PR_SLUG}.git")
    git(repo, "update-ref", "refs/remotes/origin/main", "main")  # origin/main is where main is until the pull
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    git(repo, "config", "branch.main.remote", "origin")
    git(repo, "config", "branch.main.merge", "refs/heads/main")
    dest = repo
    install_fake_gh(dest)
    unreachable_proxy(dest)
    env_file(dest, GIT_TRACE=posix(dest / "git-trace.log"))
    if release is not None:
        pre = repo / "ob-pre.git"  # origin before the merge: what watch's version check fetches
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", posix(pre)], check=True, capture_output=True, text=True)
        git(repo, "push", "-q", posix(pre), "main:refs/heads/main")
        release_shim(repo, gated=True)
    else:
        write(dest, "bin/git", WATCH_SHIM.replace("@REAL@", msys(shutil.which("git") or "git")).replace("@CODE@", posix(repo))
              .replace("@BARE@", posix(bare)).replace("@LOG@", posix(dest / "gh-log.jsonl")).replace("@URL@", f"https://github.com/{PR_SLUG}.git"))
        (dest / "bin" / "git").chmod(0o755)
    pr = gh_pull(7, "add-greeting")
    pr.update({"title": "feat(add-greeting): add greet and farewell", "body": "Adds greet and farewell.", "author": "eval-bot"})
    pr["head"]["sha"] = tip
    st = {"user": "eval-bot", "tokens": {"eval-bot": "eval-token"}, "clock": "2026-10-10T10:00:00Z",
          "repos": {PR_SLUG: {"default_branch": "main", "pulls": [pr], "branches": {"feat/add-greeting": tip, "main": main}}}}
    fake_gh.set_head(st, PR_SLUG, 7, tip, "2026-10-10T09:00:00Z")
    fake_gh.set_checks(st, PR_SLUG, 7, [{"__typename": "CheckRun", "name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"}])
    fake_gh.add_review(st, PR_SLUG, 7, WATCH_REVIEWER, f"**Reviewed commit:** `{tip}`\n\nNo issues found.", state="APPROVED", at="2026-10-10T09:30:00Z")
    write(dest, "gh-state.json", json.dumps(st, indent=2))
    write(repo, ".git/info/exclude", "/bin/\n/eval.env\n/gh-state.json\n/gh-log.jsonl\n/git-trace.log\n/gitconfig\n/state/\n/xdg-data/\n/xdg-config/\n/ob.git/\n/ob-pre.git/\n")
    write(repo, ".git/fixture-state.json", json.dumps({"main": main, "tip": tip, "tree": tree, "squash": squash,
                                                       **({"expected_mode": "next" if len(changes) > 1 else "close"} if agent else {})}, indent=2))


def build_finish_local_release(repo):
    """eval-finish-local's fixture (finish: local, change archived and uncommitted on feat/add-greeting) with `release.auto` true:
    main holds a VERSION file reading 0.4.0 and the branch bumped it to 0.5.0 in its own commit, so the merge into main brings
    0.5.0. A bare repo <repo>/ob.git is origin (the remote URL stays on github.com) and holds main as it stands; the shim lets
    `fetch`, `ls-remote` and `push` reach it, so a publish would be observable there (and in the fake gh). Nothing is tagged.
    .git/fixture-state.json records main's tip."""
    base(repo)
    write(repo, "openspec/specwright.yaml", "finish: local\n" + release_settings(True, True))
    write(repo, "VERSION", "0.4.0\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "chore: release settings")
    main = subprocess.run(["git", "rev-parse", "main"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    finished(repo, repo)
    write(repo, "VERSION", f"{RELEASE_VERSION}\n")
    git(repo, "add", "VERSION")
    git(repo, "commit", "-q", "-m", f"feat(add-greeting): bump version to {RELEASE_VERSION}", "--", "VERSION")
    origin_with_main(repo, "main")
    install_fake_gh(repo)
    unreachable_proxy(repo)
    env_file(repo, GIT_TRACE=posix(repo / "git-trace.log"))
    release_shim(repo, gated=False)
    st = {"user": "eval-bot", "tokens": {"eval-bot": "eval-token"}, "repos": {PR_SLUG: {"default_branch": "main", "pulls": []}}}
    write(repo, "gh-state.json", json.dumps(st, indent=2))
    write(repo, ".git/info/exclude", RELEASE_EXCLUDE)
    write(repo, ".git/fixture-state.json", json.dumps({"main": main}, indent=2))


RELEASE_EVALS = {"eval-finish-release-offer": release_settings(True, False), "eval-finish-release-auto": release_settings(True, True),
                 "eval-finish-release-disabled": release_settings(False, True)}


# --- jj-backend evals (add-jj-backend task 6.1) ---------------------------------------------------------------
VCS_EVALS = ("eval-branch-git-jj-note", "eval-branch-jj-dirty-no-stash", "eval-branch-store-probe-fails",
             "eval-debug-jj-dirty-no-stash", "eval-debug-jj-clean")
VCS_HIDDEN = "/bin/\n/eval.env\n/git-trace.log\n/jj-calls.log\n/state/\n/xdg-data/\n/xdg-config/\n"
JJ_SETTINGS = "finish: local\nvcs: jj\n"
GREET_OK = '"""Greeting helpers."""\n\n\ndef greet(name):\n    return f"Hello, {name}!"\n'
GREET_BAD = '"""Greeting helpers."""\n\n\ndef greet(name):\n    return f"Hello {name}"\n'
GREET_EDITED = '"""Greeting helpers."""\n\n\ndef greet(name):\n    return "Hello " + name  # local experiment\n'
GREET_TEST = ("import unittest\n\nimport greet\n\n\nclass GreetTests(unittest.TestCase):\n"
              "    def test_greet_named(self):\n        self.assertEqual(greet.greet(\"Ada\"), \"Hello, Ada!\")\n\n\n"
              "if __name__ == '__main__':\n    unittest.main()\n")
# A `jj` first on the run's PATH. It answers `--version` like jj 0.46.0, fails every other call, and logs each call
# with whether the store's gate lock existed at that moment ("held" or "free"). In the Git-backend fixture any log
# line means Specwright ran jj on a Git backend.
JJ_STUB = """#!/bin/sh
d="$(cd "$(dirname "$0")/.." && pwd)"
if [ -d "$d/store/.git/specwright-gate.lock" ]; then held=held; else held=free; fi
echo "$held jj $*" >> "$d/jj-calls.log"
case "$1" in
  --version) echo "jj 0.46.0"; exit 0;;
esac
echo "jj must not run in this fixture" >&2
exit 1
"""


def _rev(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def jj_colocate(repo):
    """Make the Git repo at `repo` a colocated jj repo with the real jj (`jj git init --colocate`, which imports main as
    a bookmark and starts an empty @ on top of it). The identity is set for this repo only."""
    jj = shutil.which("jj")
    if not jj:
        raise SystemExit("jj is not on PATH: this fixture needs the real jj 0.46 or newer")
    for argv in (["git", "init", "--colocate"], ["config", "set", "--repo", "user.name", "Eval Bot"],
                 ["config", "set", "--repo", "user.email", "eval@example.invalid"]):
        subprocess.run([jj, *argv], cwd=repo, check=True, capture_output=True, text=True)


def vcs_helpers(dest):
    """bin/jj (the stub), and eval.env with GIT_TRACE; the first call to env_file also puts bin/ on PATH."""
    (dest / "bin").mkdir(exist_ok=True)
    write(dest, "bin/jj", JJ_STUB)
    (dest / "bin" / "jj").chmod(0o755)
    env_file(dest, GIT_TRACE=posix(dest / "git-trace.log"))


def build_vcs(name, repo):
    """The jj-backend live evals. The run's helper files sit in the repo directory (hidden through .git/info/exclude),
    and .git/fixture-state.json (fixture-state.json for the store pair) records what the graders compare with."""
    if name == "eval-branch-store-probe-fails":
        # the code repo's settings ask for a jj store; the store is a plain Git repo, so the gate's store probe must stop
        store_base(repo, settings="finish: local\nplanning_store:\n  vcs: jj\n")
        vcs_helpers(repo)
        write(repo, "fixture-state.json", json.dumps({"code_main": _rev(repo / "code", "rev-parse", "main"),
                                                      "store_main": _rev(repo / "store", "rev-parse", "main")}, indent=2))
        return
    jj_backend = name != "eval-branch-git-jj-note"
    base(repo, JJ_SETTINGS if jj_backend else "finish: local\n")
    if name.startswith("eval-debug-"):
        write(repo, "greet.py", GREET_OK if name.endswith("dirty-no-stash") else GREET_BAD)
        write(repo, "test_greet.py", GREET_TEST)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "feat: add greet")
    write(repo, ".git/info/exclude", VCS_HIDDEN)
    extra = {}
    if jj_backend:
        jj_colocate(repo)  # before the helpers: the Git-backend fixture has the stub, the jj ones the real jj
        if name == "eval-branch-jj-dirty-no-stash":
            extra["edited"] = "# greeter\n\nA tiny greeting library. WIP edit.\n"
            write(repo, "README.md", extra["edited"])
        elif name == "eval-debug-jj-dirty-no-stash":
            extra["edited"] = GREET_EDITED
            write(repo, "greet.py", GREET_EDITED)
        (repo / "bin").mkdir(exist_ok=True)
        env_file(repo, GIT_TRACE=posix(repo / "git-trace.log"))
    else:  # leftover jj metadata on a Git-backend repo; jj writes this same .gitignore into its own .jj
        write(repo, ".jj/.gitignore", "/*\n")
        vcs_helpers(repo)
    write(repo, ".git/fixture-state.json", json.dumps(
        {"main": _rev(repo, "rev-parse", "main"), "commits": int(_rev(repo, "rev-list", "--count", "--all")), **extra}, indent=2))


def build(name, repo):
    if name in VCS_EVALS:
        return build_vcs(name, repo)
    if name in RELEASE_EVALS:
        return build_finish_resume_merged(repo, squash=True, release=RELEASE_EVALS[name])
    if name == "eval-finish-local-release-reported":
        return build_finish_local_release(repo)
    if name == "eval-agent-merge-release-auto":
        return build_watch_merge(repo, agent=True, release=release_settings(True, True))
    if name in ("eval-watch-agent-merge", "eval-watch-merge-default-user"):
        return build_watch_merge(repo, agent=name.endswith("agent-merge"))
    if name in ("eval-finish-resume-squash-merged", "eval-finish-resume-merged-branch-gone"):
        return build_finish_resume_merged(repo, squash=name.endswith("squash-merged"))
    if name == "eval-finish-resume-stale-main":
        return build_finish_resume_stale_main(repo)
    if name in ("eval-install-openspec-mismatch", "eval-install-openspec-override"):
        install_base(repo, "store")
        return install_fake_openspec(repo, "1.15.0")
    if name == "eval-install-latest-tag-predates-script":
        install_base(repo, "store")
        return specwright_source(repo)
    if name.startswith("eval-install-"):
        return install_base(repo, {"eval-install-store": "store", "eval-install-store-other-schema": "other-schema",
                                   "eval-install-nested-store": "nested"}[name])
    if name in ("eval-references-apply", "eval-references-unregistered"):
        return references_base(repo, registered=name == "eval-references-apply")
    if name.startswith("eval-branch-store-"):
        return build_branch_store(name, repo)
    if name.startswith(("eval-store-", "eval-nested-", "eval-root-")):
        return build_store(name, repo)
    if name in ("eval-roadmap-next-gap", "eval-roadmap-next-gap-dirty-main"):
        return build_roadmap_next_gap(repo, dirty=name.endswith("dirty-main"))
    if name in ("eval-roadmap-next-milestone-end", "eval-roadmap-close-agreed-split"):
        return build_roadmap_milestone_end(repo, user_verified=name.endswith("milestone-end"))
    if name in GROUP_EVALS:
        return build_group(name, repo)
    base(repo)
    if name == "eval-branch-dirty-main":
        write(repo, "README.md", "# greeter\n\nA tiny greeting library. WIP edit.\n")
    elif name == "eval-branch-clean-main":
        pass
    elif name in ("eval-apply-three-tasks", "eval-apply-on-main"):
        if name == "eval-apply-three-tasks":
            git(repo, "checkout", "-q", "-b", "feat/add-greeting")
        change_artifacts(repo)  # left uncommitted: the planning commit is under test
        write(repo, "scratch-notes.txt", "personal notes - not part of the change\n")
    elif name == "eval-implementer-light-packet":  # planned and committed on the branch; the implementer starts from the empty greet.py
        git(repo, "checkout", "-q", "-b", "feat/add-greeting")
        change_artifacts(repo)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "feat(add-greeting): add planning artifacts")
    elif name == "eval-finish-local":
        finished(repo, repo)
    elif name in ("eval-finish-resume-after-archive-commit", "eval-finish-resume-from-main"):
        finished(repo, repo)  # the interrupted finish committed the archive on the branch; the merge never ran
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "feat(add-greeting): archive change")
        if name.endswith("from-main"):
            git(repo, "checkout", "-q", "main")  # HEAD on main, the branch unmerged
    else:
        raise SystemExit(f"unknown eval {name}")


if __name__ == "__main__":
    build(sys.argv[1], Path(sys.argv[2]))
