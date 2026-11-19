"""`sw finish undo-archive-plan` entered directly (ADR 0028, design D7; the finish.sh shim is gone since 0.38.0).

The tests run the tree's sw through the test home (native-cli-finish D9): arguments reach it as given, a non-UTF-8
argument is refused before any command, and the plan finds the project from `--code`, then `--dir`.

Run: python -m unittest evals/finish/test_finish_shim.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.append(str(ROOT / "evals" / "vcs"))
import gitlog  # noqa: E402
import jjenv  # noqa: E402
from vcs_test_support import STAMP, sw_env, sw_run  # noqa: E402
import swcall  # noqa: E402

_spec = importlib.util.spec_from_file_location("finish_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

P = "openspec"
BRANCH = "bugfix/add-x"


class ShimCase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="swfs-"))
        self.addCleanup(fx.rmtree, self.tmp)
        self.shim = gitlog.install(self.tmp / "gitshim", real_git=jjenv.real_git(), log_path=self.tmp / "git.jsonl")
        self.work = fx.make_repo(self.tmp / "main")

    def archived(self, work, name="add-x", prefix=P, branch=BRANCH):
        """On <branch>: the change `name` planned (DEFERRED) and archived in one commit."""
        fx.git(work, "checkout", "-q", "-b", branch)
        fx.make_change(work, name, "DEFERRED", {"a": "New thing"}, prefix=prefix)
        return fx.archive(work, name, prefix=prefix, commit_it=True)

    def run_sw(self, *args, cwd=None, env=None):
        """`sw finish <args>` entered directly (evals/swcall.py)."""
        return sw_run(["finish", *args], cwd=cwd or self.work, env=env, shim=self.shim, stamp=False)

    def plan(self, change="add-x", *, prefix=P, dir_=None, code=None, archived=None, main="main"):
        args = (["--dir", str(dir_)] if dir_ else []) + ["undo-archive-plan", "--change", change, "--archived-name",
                                                           archived or f"{fx.DATE}-{change}", "--prefix", prefix,
                                                           "--main", main]
        return args + (["--code", str(code)] if code is not None else [])

    def document(self, result, code=0):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def mismatch_document(self, result):
        """The native refusal of a project without a matching VERSION: `sw_mismatch`, exit 1, no git command."""
        doc = self.document(result, 1)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_mismatch"), doc)
        self.assertEqual(self.shim.calls(), [], "a git command ran")
        return doc

    def no_git_calls(self):
        self.shim.log_path.unlink(missing_ok=True)


class TestPlanRunsSw(ShimCase):
    def test_plan_runs_sw(self):
        self.archived(self.work)
        doc = self.document(self.run_sw(*self.plan()))
        self.assertIs(doc["ok"], True, doc)
        self.assertEqual(doc["mode"], "committed")
        self.assertTrue(doc["steps"], doc)
        self.assertNotIn("script", doc)

    def test_prefix_with_space_and_non_ascii_change(self):
        prefix, name = "my plans/openspec", "add-éx"
        work = fx.make_repo(self.tmp / "space", prefix=prefix)
        self.archived(work, name, prefix=prefix)
        doc = self.document(self.run_sw(*self.plan(name, prefix=prefix), cwd=work))
        self.assertIs(doc["ok"], True, doc)
        self.assertEqual([m["name"] for m in doc["members"]], [name])
        steps = fx.flat(doc["steps"])
        self.assertIn(f"undo archive of {name}", steps)
        self.assertIn(f"{prefix}/changes/archive/{fx.DATE}-{name}", steps)

    def test_arguments_reach_sw_unchanged(self):
        """The helper starts sw with the list as given: spaces, non-ASCII text and an empty value arrive as they are."""
        prefix, name = "my plans/openspec", "add-éx"
        work = fx.make_repo(self.tmp / "space", prefix=prefix)
        self.archived(work, name, prefix=prefix)
        args = self.plan(name, prefix=prefix)
        self.assertEqual(swcall.argv(["finish", *args])[2:], args, "the helper adds nothing to the list")
        doc = self.document(self.run_sw(*args, cwd=work))
        steps = fx.flat(doc["steps"])
        self.assertIn(f"{prefix}/changes/archive/{fx.DATE}-{name}", steps)
        self.assertIn(f"undo archive of {name}", steps)

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: the runtime refuses a non-UTF-8 argument only on POSIX, and the name needs a Linux file system")
    def test_non_utf8_argument_is_refused(self):
        """A --change holding the byte 0xFF is refused before any command: non-zero exit, no output, no git; the valid call runs."""
        self.archived(self.work)
        self.no_git_calls()
        bad = [b"a\xffb" if arg == "add-x" else arg for arg in self.plan()]
        result = swcall.run(["finish", *bad], cwd=self.work, env=sw_env(shim=self.shim), text=False)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(self.shim.calls(), [], "a git command ran")
        control = self.document(self.run_sw(*self.plan()))  # the control: the valid change reaches git
        self.assertIs(control["ok"], True, control)
        self.assertTrue(self.shim.calls(), "the control never reached git")

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: a file name that is not UTF-8 needs a Linux file system")
    def test_non_utf8_committed_name_is_not_utf8(self):
        """A committed archive file whose name holds 0xFF stops the plan by name: no script, exit 1 (D4)."""
        fx.git(self.work, "checkout", "-q", "-b", BRANCH)
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing"})
        raw = os.fsencode(self.work) + b"/" + os.fsencode(P) + b"/changes/add-x/notes-\xff.md"
        with open(raw, "wb") as stream:
            stream.write(b"notes\n")
        fx.archive(self.work, "add-x", commit_it=True)

        result = self.run_sw(*self.plan())

        doc = self.document(result, 1)
        self.assertEqual((doc["ok"], doc["error"]), (False, "not_utf8"), doc)
        self.assertIn("notes-\\xFF.md", doc["message"])
        self.assertNotIn("script", doc)

    @unittest.skipUnless(os.name == "nt", "platform: Git Bash path forms are Windows-only")
    def test_unconverted_path_on_windows_is_refused(self):
        """change-finish "Path conversion fails on Windows": `--dir /etc/x` from a caller that is not Git Bash is taken as
        given, a root-relative Windows path. The plan stops with its error for a directory that is no repository: no
        bad_path, no script, no Git write."""
        self.archived(self.work)
        result = self.run_sw(*self.plan(dir_="/etc/x"), cwd=self.work)
        doc = self.document(result, 1)
        self.assertEqual((doc["ok"], doc["error"]), (False, "not_a_repo"), doc)
        self.assertNotIn("bad_path", result.stdout + result.stderr)
        self.assertNotIn("script", doc)
        self.assertEqual(self.shim.calls(), [], "a git command ran")


class TestProjectWalk(ShimCase):
    def store_and_code(self):
        """A planning store with the archive and no installed version, and a stamped code checkout."""
        store = fx.make_repo(self.tmp / "store")
        (store / STAMP).unlink()
        self.archived(store)
        code = fx.make_repo(self.tmp / "code")
        return store, code

    def test_code_picks_the_project(self):
        store, code = self.store_and_code()
        self.assertFalse((store / STAMP).exists())
        self.assertTrue((code / STAMP).is_file())
        doc = self.document(self.run_sw(*self.plan(dir_=store, code=code), cwd=store))
        self.assertIs(doc["ok"], True, doc)
        self.assertEqual(doc["head"], fx.git(store, "rev-parse", "HEAD"))

    def test_store_without_code_is_sw_mismatch(self):
        store, _ = self.store_and_code()
        self.no_git_calls()
        doc = self.mismatch_document(self.run_sw(*self.plan(dir_=store), cwd=store))
        self.assertIn("no installed version found", doc["message"])


if __name__ == "__main__":
    unittest.main()
