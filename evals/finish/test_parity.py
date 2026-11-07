"""Differential eval (native-cli-finish D9): the frozen oracle copy of the old finish.sh and finish.sh plan the same fixture
repos and must print the same stdout bytes and exit with the same code.

The oracle (evals/finish/oracle/finish.sh) is test-only and ships nowhere; ORACLE_FIN_DIR makes it print the real vcs.sh path.
The GitButler cases are in evals/vcs/test_gitbutler_parity.py. M8 deletes the oracle together with the shim.

Run: python -m unittest evals/finish/test_parity.py
"""
import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.append(str(ROOT / "evals"))
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
import bashexe  # noqa: E402
import jjenv  # noqa: E402
import vcs_test_support  # noqa: E402


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fx = _load("finish_fixtures", "fixtures.py")
tp = _load("finish_test_undo_plan", "test_undo_plan.py")  # module attributes only: its test classes are not collected here
tj = _load("finish_test_undo_jj", "test_undo_jj.py")

P = "openspec"
BRANCH = tp.BRANCH
JJ_BRANCH = tj.BRANCH


def git_pair(work, args, cwd=None):
    """(finish.sh, oracle) as (exit code, stdout bytes, stderr bytes) on a Git repo, run the same way."""
    out = []
    for script, extra in ((fx.SCRIPT, {}), (fx.ORACLE, {"ORACLE_FIN_DIR": str(fx.ORACLE_FIN_DIR)})):
        r = subprocess.run([bashexe.bash(), str(script), *args], cwd=cwd or work, capture_output=True,
                           env=dict(os.environ, SPECWRIGHT_HOME=str(vcs_test_support.sw_home()), **extra))
        out.append((r.returncode, r.stdout, r.stderr))
    return out


def jj_pair(work, env, args):
    """The same on a jj repo, through the Git-Bash PATH the jj evals use."""
    out = []
    for script, extra in ((fx.SCRIPT, {}), (fx.ORACLE, {"ORACLE_FIN_DIR": str(fx.ORACLE_FIN_DIR)})):
        shell_env = vcs_test_support.bash_path_env(None)
        shell_env.update({k: v for k, v in env.items() if k != "PATH"})
        shell_env.update(extra)
        shell_env.setdefault("SPECWRIGHT_HOME", str(vcs_test_support.sw_home()))
        shell_env["VCS_TEST_SEARCH"] = shell_env["PATH"]
        r = subprocess.run([jjenv.find_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"', "parity",
                            script.as_posix(), *args], cwd=work, env=shell_env, capture_output=True)
        out.append((r.returncode, r.stdout, r.stderr))
    return out


class ParityAsserts:
    def assertParity(self, pair, code=None):
        new, old = pair
        self.assertEqual(new[1], old[1], "stdout bytes differ between finish.sh and the oracle")
        self.assertEqual(new[0], old[0], "exit codes differ between finish.sh and the oracle")
        if code is not None:  # the case really planned (or refused) what it names, not a broken fixture
            self.assertEqual(old[0], code, old[1] + old[2])
        self.assertTrue(old[1].strip(), "the oracle printed nothing: " + old[2].decode("utf-8", "replace"))


class TestParityGit(tp.Base, ParityAsserts):
    def plan(self, change="add-x", **kw):
        return git_pair(self.work, fx.plan_args(change, **kw))

    def test_uncommitted_single_archive_with_nested_folders(self):
        self.single({"a": "New thing", "b": "B thing"})
        for rel in ("notes/z.md", "notes/deep/b/leaf.md", "notes/deep/a/leaf.md", "notes/deep/a/aa.md", "assets/img/one.txt",
                    "assets/two.txt"):
            fx.write(self.work, f"{tp.cd('add-x')}/{rel}", f"{rel}\n")
        fx.commit(self.work, "docs(add-x): add notes")
        fx.archive(self.work, "add-x")
        self.assertParity(self.plan(), 0)

    def test_committed_single_archive(self):
        self.single({"a": "New thing", "b": "B thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        self.assertParity(self.plan(), 0)

    def test_committed_single_archive_with_amendment(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.edit(self.work, f"{tp.ad('add-x')}/design.md", "Original design.", "Amended design.")
        fx.edit(self.work, tp.SPEC_A, "Baseline purpose", "Amended purpose")
        fx.commit(self.work, "docs(add-x): amend")
        self.assertParity(self.plan(), 0)

    def test_bulk_archive_with_deferred_member_and_amendments(self):
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True, marker=True)
        fx.edit(self.work, tp.SPEC_A, "Baseline purpose", "Amended purpose")
        fx.commit(self.work, "docs: amend the spec")
        self.assertParity(self.plan(), 0)
        self.assertParity(self.plan("add-y"), 0)

    def test_uncommitted_bulk_archive_with_amendment(self):
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"])
        fx.edit(self.work, tp.SPEC_A, "Baseline purpose", "My own purpose")
        self.assertParity(self.plan(), 0)

    def test_member_waiting_on_a_user_task(self):
        for commit_it in (True, False):
            with self.subTest(committed=commit_it):
                self.setUp()
                self.on_branch()
                fx.make_change(self.work, "add-x", "APPROVE", {"a": "X thing"}, commit_it=False)
                fx.commit(self.work, "docs(add-x): add planning artifacts",
                          {f"{P}/changes/add-x/tasks.md": "# Tasks\n\n- [x] 1.1 do it\n- [ ] 1.2 [user] Play the level\n"})
                fx.make_change(self.work, "add-y", "APPROVE", {"a": "Y thing"}, commit_it=False)
                fx.commit(self.work, "docs(add-y): add planning artifacts",
                          {f"{P}/changes/add-y/tasks.md": "# Tasks\n\n- [x] 1.1 do it\n- [x] 1.2 [user] Play the level\n"})
                fx.archive(self.work, ["add-x", "add-y"], commit_it=commit_it)
                pair = self.plan()
                self.assertParity(pair, 0)
                self.assertIn(b'"waiting_on_user": ["1.2"]', pair[1][1])

    def test_resume_from_another_branch(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        self.git("checkout", "-q", "main")
        self.assertParity(self.plan(branch=BRANCH), 0)

    def test_refusal_target_exists(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.write(self.work, f"{tp.cd('add-x')}/notes.md", "recreated\n")
        pair = self.plan()
        self.assertParity(pair, 1)
        self.assertIn(b'"target_exists"', pair[1][1])

    def test_refusal_no_archive(self):
        self.single({"a": "New thing"})
        pair = self.plan()
        self.assertParity(pair, 1)
        self.assertIn(b'"no_archive"', pair[1][1])

    def test_refusal_dirty_tree(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        self.git("checkout", "-q", "main")
        fx.edit(self.work, "README.md", "demo", "demo edited")
        pair = self.plan(branch=BRANCH)
        self.assertParity(pair, 1)
        self.assertIn(b'"dirty_tree"', pair[1][1])

    @unittest.skipUnless(sys.platform.startswith("linux"), "macOS and Windows file systems refuse a name with invalid UTF-8 bytes")
    def test_uncommitted_archive_with_invalid_utf8_file_name(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x")
        bad = os.path.join(os.fsencode(str(self.work)), os.fsencode(tp.ad("add-x")), b"bad-\xff-name.md")
        with open(bad, "wb") as f:
            f.write(b"not utf-8 named\n")
        self.assertParity(self.plan())


class TestParityJj(tj.JjBase, ParityAsserts):
    def plan(self, change="add-x", **kw):
        return jj_pair(self.work, self.env, fx.plan_args(change, **kw))

    def two_changes(self, tasks=None):
        """add-x (DEFERRED) and add-y (APPROVE), each committed with jj."""
        for name, verdict, req in (("add-x", "DEFERRED", "X thing"), ("add-y", "APPROVE", "Y thing")):
            fx.make_change(self.work, name, verdict, {"a": req}, commit_it=False)
            if name in (tasks or {}):
                fx.write(self.work, f"{P}/changes/{name}/tasks.md", tasks[name])
            self.jjc("commit", "-m", f"docs({name}): add planning artifacts")

    def test_uncommitted_single_archive_with_nested_folders(self):
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing", "b": "B thing"}, commit_it=False)
        for rel in ("notes/z.md", "notes/deep/b/leaf.md", "notes/deep/a/leaf.md", "assets/img/one.txt", "assets/two.txt"):
            fx.write(self.work, f"{P}/changes/add-x/{rel}", f"{rel}\n")
        self.jjc("commit", "-m", "docs(add-x): add planning artifacts")
        fx.archive(self.work, "add-x", commit_it=False)
        self.jjc("bookmark", "create", JJ_BRANCH, "-r", "@-")
        self.assertParity(self.plan(branch=JJ_BRANCH), 0)

    def test_committed_single_archive(self):
        self.archived_branch()
        self.assertParity(self.plan(branch=JJ_BRANCH), 0)

    def test_bulk_archive_with_deferred_member_and_amendments(self):
        self.two_changes()
        fx.archive(self.work, ["add-x", "add-y"], commit_it=False)
        self.jjc("commit", "-m", "chore(add-x, add-y): archive change")
        self.jjc("bookmark", "create", JJ_BRANCH, "-r", "@-")
        fx.edit(self.work, tp.SPEC_A, "Baseline purpose", "Amended purpose")
        self.jjc("commit", "-m", "docs: amend the spec")
        self.jjc("bookmark", "set", JJ_BRANCH, "-r", "@-")
        self.assertParity(self.plan(branch=JJ_BRANCH), 0)

    def test_member_waiting_on_a_user_task(self):
        self.two_changes({"add-x": "# Tasks\n\n- [x] 1.1 do it\n- [ ] 1.2 [user] Play the level\n",
                            "add-y": "# Tasks\n\n- [x] 1.1 do it\n- [x] 1.2 [user] Play the level\n"})
        fx.archive(self.work, ["add-x", "add-y"], commit_it=False)
        self.jjc("commit", "-m", "chore(add-x, add-y): archive change")
        self.jjc("bookmark", "create", JJ_BRANCH, "-r", "@-")
        pair = self.plan(branch=JJ_BRANCH)
        self.assertParity(pair, 0)
        self.assertIn(b'"waiting_on_user": ["1.2"]', pair[1][1])

    def test_resume_from_another_branch(self):
        self.archived_branch()
        self.jjc("new", "main")
        self.jjc("bookmark", "create", "feat/other", "-r", "@-")
        self.assertParity(self.plan(branch=JJ_BRANCH), 0)

    def test_refusal_target_exists(self):
        self.archived_branch()
        fx.write(self.work, f"{P}/changes/add-x/notes.md", "recreated\n")
        pair = self.plan(branch=JJ_BRANCH)
        self.assertParity(pair, 1)
        self.assertIn(b'"target_exists"', pair[1][1])

    def test_refusal_no_archive(self):
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing"}, commit_it=False)
        self.jjc("commit", "-m", "docs(add-x): add planning artifacts")
        self.jjc("bookmark", "create", JJ_BRANCH, "-r", "@-")
        pair = self.plan(branch=JJ_BRANCH)
        self.assertParity(pair, 1)
        self.assertIn(b'"no_archive"', pair[1][1])

    def test_refusal_dirty_tree(self):
        self.archived_branch()
        self.jjc("new", "main")
        self.jjc("bookmark", "create", "feat/other", "-r", "@-")
        fx.write(self.work, "README.md", "dirty\n")
        pair = self.plan(branch=JJ_BRANCH)
        self.assertParity(pair, 1)
        self.assertIn(b'"dirty_tree"', pair[1][1])


if __name__ == "__main__":
    unittest.main()
