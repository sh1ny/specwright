"""Outcome evals for `sw finish undo-archive-plan` (change native-cli-retire-scripts, task 7.2). They once compared the plan with
the frozen finish.sh (native-cli-finish D9); the frozen script is no longer run. Each case plans on a fixture repo, checks the
printed document, and where the plan carries `steps` runs them with `sw` and checks that refs, index and files are the ones
the repository had before the archive (`TestOutcomeGit.test_printed_steps_restore_refs_index_files`).

The one difference the old oracle showed is kept as an assertion of sw's side: a task id in other Unicode digits is not a task
(`test_user_task_ids_are_ascii_digits`). The GitButler cases are in evals/vcs/test_gitbutler_parity.py.

Run: python -m unittest evals/finish/test_parity.py
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.append(str(ROOT / "evals"))
sys.path.insert(0, str(ROOT / "evals" / "vcs"))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fx = _load("finish_fixtures", "fixtures.py")
tp = _load("finish_test_undo_plan", "test_undo_plan.py")  # module attributes only: its test classes are not collected here
tj = _load("finish_test_undo_jj", "test_undo_jj.py")
ts = _load("finish_test_undo_steps", "test_undo_steps.py")
fx = ts.fx  # the module the fixtures of ts.build_* call, so a patch of `archive` reaches them

P = "openspec"
BRANCH = tp.BRANCH
JJ_BRANCH = tj.BRANCH


def plan(work, change="add-x", **kw):
    """(exit code, document, raw output) of `sw finish undo-archive-plan` on `work`."""
    return fx.run_plan(work, change, **kw)


class PlanAsserts:
    def assertPlans(self, result, code=0):
        status, doc, raw = result
        self.assertEqual(status, code, raw)
        self.assertIsInstance(doc, dict, raw)
        return doc


class TestOutcomeGit(tp.Base, PlanAsserts):
    def refs(self, repo):
        return sorted(fx.git(repo, "for-each-ref", "--format=%(refname)").split())

    def restores(self, build):
        """Build the archived fixture in self.work and the same fixture without the archive in a second repo, plan, run the
        printed steps and the after-rerun steps with sw: refs, index and the change's files are the unarchived repo's."""
        expected = fx.make_repo(self.tmp / "expected")
        build(self.work)
        with mock.patch.object(fx, "archive", lambda *a, **k: None):
            build(expected)
        doc = self.assertPlans(plan(self.work))
        self.assertTrue(doc["steps"], doc)
        for steps in (doc["steps"], doc["after_rerun_steps"]):
            if steps:
                r = fx.run_steps(self.scripts, steps)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        got, want = ts.restored_change(self.work, expected)
        self.assertEqual(got["files"], want["files"], "the change's files")
        self.assertTrue(got["files"], "the change's files are back")
        self.assertEqual(got["index"], want["index"], "the change's index entries")
        self.assertEqual((got["archived"], got["tracked_archive"]), ([], ""), "no archive of the change remains")
        self.assertEqual(self.refs(self.work), self.refs(expected), "the refs")
        return doc

    def test_printed_steps_restore_refs_index_files(self):
        def uncommitted(work):
            fx.git(work, "checkout", "-q", "-b", BRANCH)
            fx.make_change(work, "add-x", "DEFERRED", {"a": "New thing", "b": "B thing"})
            for rel in ("notes/z.md", "notes/deep/b/leaf.md", "assets/img/one.txt"):
                fx.write(work, f"{tp.cd('add-x')}/{rel}", f"{rel}\n")
            fx.commit(work, "docs(add-x): add notes")
            fx.archive(work, "add-x")

        def committed(work):
            ts.build_single(work)

        def amended(work):
            ts.build_single(work, deltas={"a": "New thing"})
            # the unarchived fixture (archive patched out) holds the design where the change was
            held = tp.ad("add-x") if (Path(work) / tp.ad("add-x")).is_dir() else tp.cd("add-x")
            fx.edit(work, f"{held}/design.md", "Original design.", "Amended design.")
            fx.edit(work, tp.SPEC_A, "Baseline purpose", "Amended purpose")
            fx.commit(work, "docs(add-x): amend")

        for name, build in (("uncommitted archive", uncommitted), ("committed archive", committed), ("amended archive", amended),
                            ("bulk archive", ts.build_pair)):
            with self.subTest(name):
                self.setUp()
                self.restores(build)


class TestPlanGit(tp.Base, PlanAsserts):
    def plan(self, change="add-x", **kw):
        return plan(self.work, change, **kw)

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
                doc = self.assertPlans(self.plan())
                self.assertEqual([m["waiting_on_user"] for m in doc["members"]], [["1.2"], []])

    def test_user_task_ids_are_ascii_digits(self):
        """sw reads ASCII digits only: a task id written in other Unicode digits is not a task."""
        self.on_branch()
        fx.make_change(self.work, "add-x", "APPROVE", {"a": "X thing"}, commit_it=False)
        fx.commit(self.work, "docs(add-x): add planning artifacts",
                  {f"{P}/changes/add-x/tasks.md": "# Tasks\n\n- [x] 1.1 do it\n- [ ] ١.١ [user] Play the level\n"
                                                   "- [ ] 1.2 [user] Play the level\n"})
        fx.archive(self.work, "add-x", commit_it=True)
        doc = self.assertPlans(self.plan())
        self.assertEqual([m["waiting_on_user"] for m in doc["members"]], [["1.2"]])

    def test_resume_from_another_branch(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        self.git("checkout", "-q", "main")
        self.assertPlans(self.plan(branch=BRANCH))

    def test_refusal_target_exists(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.write(self.work, f"{tp.cd('add-x')}/notes.md", "recreated\n")
        self.assertEqual(self.assertPlans(self.plan(), 1)["error"], "target_exists")

    def test_refusal_no_archive(self):
        self.single({"a": "New thing"})
        self.assertEqual(self.assertPlans(self.plan(), 1)["error"], "no_archive")

    def test_refusal_dirty_tree(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        self.git("checkout", "-q", "main")
        fx.edit(self.work, "README.md", "demo", "demo edited")
        doc = self.assertPlans(self.plan(branch=BRANCH), 1)
        self.assertEqual(doc["error"], "dirty_tree")
        self.assertEqual(doc["files"], ["README.md"])
        self.assertEqual(doc["message"], tp.DIRTY_PREFIX + "M README.md")

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: macOS and Windows file systems refuse a name with invalid UTF-8 bytes")
    def test_uncommitted_archive_with_invalid_utf8_file_name(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x")
        bad = os.path.join(os.fsencode(str(self.work)), os.fsencode(tp.ad("add-x")), b"bad-\xff-name.md")
        with open(bad, "wb") as f:
            f.write(b"not utf-8 named\n")
        # sw stops with `not_utf8` naming the file with its bytes as \xHH and prints no undo
        doc = self.assertPlans(self.plan(), 1)
        self.assertEqual(doc["error"], "not_utf8", doc)
        self.assertIn("bad-\\xFF-name.md", doc["message"])
        self.assertNotIn("steps", doc)


class TestPlanJj(tj.JjBase, PlanAsserts):
    def plan(self, change="add-x", **kw):
        return plan(self.work, change, **kw)

    def two_changes(self, tasks=None):
        """add-x (DEFERRED) and add-y (APPROVE), each committed with jj."""
        for name, verdict, req in (("add-x", "DEFERRED", "X thing"), ("add-y", "APPROVE", "Y thing")):
            fx.make_change(self.work, name, verdict, {"a": req}, commit_it=False)
            if name in (tasks or {}):
                fx.write(self.work, f"{P}/changes/{name}/tasks.md", tasks[name])
            self.jjc("commit", "-m", f"docs({name}): add planning artifacts")

    def test_member_waiting_on_a_user_task(self):
        self.two_changes({"add-x": "# Tasks\n\n- [x] 1.1 do it\n- [ ] 1.2 [user] Play the level\n",
                          "add-y": "# Tasks\n\n- [x] 1.1 do it\n- [x] 1.2 [user] Play the level\n"})
        fx.archive(self.work, ["add-x", "add-y"], commit_it=False)
        self.jjc("commit", "-m", "chore(add-x, add-y): archive change")
        self.jjc("bookmark", "create", JJ_BRANCH, "-r", "@-")
        doc = self.assertPlans(self.plan(branch=JJ_BRANCH))
        self.assertEqual([m["waiting_on_user"] for m in doc["members"]], [["1.2"], []])

    def test_refusal_target_exists(self):
        self.archived_branch()
        fx.write(self.work, f"{P}/changes/add-x/notes.md", "recreated\n")
        self.assertEqual(self.assertPlans(self.plan(branch=JJ_BRANCH), 1)["error"], "target_exists")

    def test_refusal_no_archive(self):
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing"}, commit_it=False)
        self.jjc("commit", "-m", "docs(add-x): add planning artifacts")
        self.jjc("bookmark", "create", JJ_BRANCH, "-r", "@-")
        self.assertEqual(self.assertPlans(self.plan(branch=JJ_BRANCH), 1)["error"], "no_archive")

    def test_refusal_dirty_tree(self):
        self.archived_branch()
        self.jjc("new", "main")
        self.jjc("bookmark", "create", "feat/other", "-r", "@-")
        fx.write(self.work, "README.md", "dirty\n")
        self.assertEqual(self.assertPlans(self.plan(branch=JJ_BRANCH), 1)["error"], "dirty_tree")


if __name__ == "__main__":
    unittest.main()
