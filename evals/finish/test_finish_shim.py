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



class TestVersionAndCodeDirectory(ShimCase):
    """The planner runs the one version check, on the checkout its `--code` (else `--dir`) names (ADR 0043)."""

    def store_and_code(self):
        """A planning store with the archive and no installed version, and a stamped code checkout."""
        store = fx.make_repo(self.tmp / "store")
        (store / STAMP).unlink()
        self.archived(store)
        return store, fx.make_repo(self.tmp / "code")

    def stamp_as(self, checkout, version):
        (checkout / STAMP).write_text(version + "\n", encoding="utf-8")

    def test_relative_code_is_anchored_at_the_planning_root(self):
        """`../../code/work` from the store is checkout B (matching); from the cwd it is checkout A, of another version."""
        store, code = self.store_and_code()
        relative = os.path.relpath(code, store)
        cwd = self.tmp / "e" / "f" / "g"
        cwd.mkdir(parents=True)
        other = fx.make_repo(self.tmp / "e" / "code")
        self.stamp_as(other, "99.0.0")
        self.assertEqual((cwd / relative).resolve(), other.resolve())
        doc = self.document(self.run_sw(*self.plan(dir_=store, code=relative), cwd=cwd))
        self.assertIs(doc["ok"], True, doc)

    def test_a_relative_code_of_another_version_is_the_one_that_stops_the_plan(self):
        store, code = self.store_and_code()
        self.stamp_as(code, "99.0.0")
        relative = os.path.relpath(code, store)
        self.no_git_calls()
        doc = self.mismatch_document(self.run_sw(*self.plan(dir_=store, code=relative), cwd=self.tmp))
        self.assertIn("99.0.0", doc["message"])

    def test_missing_change_is_usage_in_another_version(self):
        self.stamp_as(self.work, "99.0.0")
        self.no_git_calls()
        result = self.run_sw("--dir", str(self.work), "undo-archive-plan")
        doc = self.document(result, 2)
        self.assertEqual((doc["ok"], doc["error"]), (False, "usage"), doc)
        self.assertEqual(self.shim.calls(), [], "a git command ran")

    def test_missing_dir_is_not_a_repo_before_any_version_check(self):
        """A `--dir` that is no directory is `not_a_repo` naming it, although the checkout the call runs in is of another version."""
        self.stamp_as(self.work, "99.0.0")
        missing = self.tmp / "no-such-dir"
        self.no_git_calls()
        doc = self.document(self.run_sw(*self.plan(dir_=missing), cwd=self.work), 1)
        self.assertEqual((doc["ok"], doc["error"]), (False, "not_a_repo"), doc)
        self.assertIn(str(missing), doc["message"])
        self.assertEqual(self.shim.calls(), [], "a git command ran")

    def test_missing_code_is_not_repository(self):
        """A `--code` that names no directory is `not_repository`, in a matching checkout and in one of another version."""
        self.archived(self.work)
        for version in (None, "99.0.0"):
            if version:
                self.stamp_as(self.work, version)
            self.no_git_calls()
            doc = self.document(self.run_sw(*self.plan(code=self.work / "missing")), 1)
            self.assertEqual((doc["ok"], doc["error"]), (False, "not_repository"), doc)
            self.assertNotIn("steps", doc)
            self.assertEqual(self.shim.calls(), [], "a git command ran")

    def test_empty_code_is_not_repository(self):
        """An empty `--code` is refused by the planner, whatever the `--dir` checkout's version, and is never an omission."""
        store, _ = self.store_and_code()
        self.no_git_calls()
        doc = self.document(self.run_sw(*self.plan(dir_=store, code=""), cwd=store), 1)
        self.assertEqual((doc["ok"], doc["error"]), (False, "not_repository"), doc)
        self.assertNotIn("steps", doc)
        self.assertEqual(self.shim.calls(), [], "a git command ran")

    def test_emitted_steps_check_the_version_the_planner_checked(self):
        """`--project A` (matching) with `--code B` (another version): every sw step carries `--project A`, and the steps
        run as printed pass their own version check."""
        code = fx.make_repo(self.tmp / "code")
        self.stamp_as(code, "99.0.0")
        self.archived(self.work)
        result = sw_run(["finish", *self.plan(code=code)], cwd=self.work, shim=self.shim, stamp=False, project=self.work)
        doc = self.document(result)
        steps = doc["steps"] + doc["after_rerun_steps"]
        carried = [step["argv"] for step in steps if "--project" in step["argv"]]
        self.assertTrue(carried, doc)
        for argv in carried:
            self.assertTrue(os.path.samefile(argv[argv.index("--project") + 1], self.work), argv)
        ran = fx.run_steps(self.tmp, doc["steps"])
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    @unittest.skipIf(sys.platform == "win32", "platform: `link/..` names the directory above the link's target only on POSIX")
    def test_code_directory_reached_through_a_symlink_and_dotdot(self):
        """`--code <A>/link/..`, with `link` pointing into checkout B: the plan uses B's settings (here a malformed file)."""
        a = fx.make_repo(self.tmp / "a")
        b = fx.make_repo(self.tmp / "b")
        (b / "sub").mkdir()
        os.symlink(b / "sub", a / "link")
        fx.write(b, f"{P}/specwright.yaml", "vcs: [unclosed\n")
        self.archived(self.work)
        doc = self.document(self.run_sw(*self.plan(code=f"{a}/link/..")), 1)
        self.assertEqual(doc["error"], "bad_setting", doc)

    @unittest.skipIf(sys.platform == "win32", "platform: `link/..` names the directory above the link's target only on POSIX")
    def test_the_version_check_names_the_same_checkout(self):
        """`--code <A>/link/..` with `link` pointing into B: only A's VERSION matches, and B's version is what stops the plan."""
        a = fx.make_repo(self.tmp / "a")
        b = fx.make_repo(self.tmp / "b")
        (b / "sub").mkdir()
        os.symlink(b / "sub", a / "link")
        self.stamp_as(b, "99.0.0")
        self.archived(self.work)
        self.no_git_calls()
        doc = self.mismatch_document(self.run_sw(*self.plan(code=f"{a}/link/..")))
        self.assertIn("99.0.0", doc["message"])


if __name__ == "__main__":
    unittest.main()
