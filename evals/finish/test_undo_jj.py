"""`sw finish undo-archive-plan` on a colocated jj repo (real jj): the printed steps work the working copy and commit
named paths with `jj commit`; they never run a Git write.

Run: python -m unittest test_undo_jj   (from evals/finish)
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
sys.path.insert(0, str(ROOT / "evals"))
import fakeexe  # noqa: E402
import jjenv  # noqa: E402
import vcs_test_support  # noqa: E402

_spec = importlib.util.spec_from_file_location("finish_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

P = "openspec"
BRANCH = "feat/add-x"
SUBJECT = "feat(add-x): undo archive of add-x"
GIT_WRITES = ("git checkout", "git rm", "git read-tree", "git restore", "git commit")


class JjBase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.jj = jjenv.require_jj()
        self.scratch = jjenv.Scratch()
        self.addCleanup(self.scratch.close)
        self.repo = self.scratch.tracked_repo()
        self.work = self.repo.path
        vcs_test_support.stamp_version(self.work)  # `sw` checks the project's VERSION (native-cli-vcs D9)
        self.env = {**self.scratch.env, "JJ_USER": jjenv.FIXTURE_NAME, "JJ_EMAIL": jjenv.FIXTURE_EMAIL}
        self.tmp = Path(tempfile.mkdtemp(prefix="swf-"))
        self.addCleanup(fx.rmtree, self.tmp)
        fx.write(self.work, f"{P}/specwright.yaml", "vcs: jj\n")
        fx.write(self.work, f"{P}/specs/a/spec.md", fx.base_spec("a"))
        self.jjc("commit", "-m", "baseline")
        self.jjc("bookmark", "set", "main", "-r", "@-")

    def jjc(self, *args):
        r = self.repo.run(self.jj, *args)
        return r.stdout.strip()

    def names(self, revset):
        out = self.jjc("diff", "-r", revset, "--name-only")
        return {line.replace("\\", "/") for line in out.splitlines() if line}

    def archived_branch(self):
        """feat/add-x holds the planning commit and the archive commit A; @ is empty on top. Returns A."""
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing", "b": "B thing"}, commit_it=False)
        self.jjc("commit", "-m", "docs(add-x): add planning artifacts")
        fx.archive(self.work, "add-x", commit_it=False)
        self.jjc("commit", "-m", "chore(add-x): archive change")
        self.jjc("bookmark", "create", BRANCH, "-r", "@-")
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.work, env=self.env, capture_output=True,
                              text=True).stdout.strip()

    def finish(self, *args):
        r = vcs_test_support.sw_run(["finish", *args], self.work, self.env, stamp=False)
        try:
            doc = json.loads(r.stdout)
        except ValueError:
            doc = None
        return r.returncode, doc, r.stdout + r.stderr

    def plan(self, **kw):
        args = ["undo-archive-plan", "--change", "add-x", "--archived-name", f"{fx.DATE}-add-x", "--prefix", P,
                "--main", "main", "--branch", BRANCH]
        return self.finish(*args)

    def run_steps(self, steps):
        return fx.run_steps(self.tmp, steps, env=self.env, tools={"jj": self.jj})

    def snapshot(self):
        files = {k: v for k, v in fx.snapshot(self.work).items() if not k.startswith(".jj/")}
        return {"files": files, "log": self.jjc("log", "--no-graph", "-r", "all()", "-T",
                                                                  'commit_id ++ " " ++ bookmarks ++ "\\n"')}

    def files(self):
        """Every file outside .git and .jj, read without running jj."""
        return {k: v for k, v in fx.snapshot(self.work).items() if not k.startswith(".jj/")}

    def ops(self):
        """The operation log's descriptions, newest first, read with --ignore-working-copy so reading adds none."""
        out = self.jjc("op", "log", "--ignore-working-copy", "--no-graph", "-T", 'description.first_line() ++ "\\n"')
        return [line for line in out.splitlines() if line]

    def only_sync_ops(self, before):
        """The operations added since `before` are all jj's own snapshot or Git import; returns them."""
        after = self.ops()
        new = after[:len(after) - len(before)]
        self.assertEqual(after[len(after) - len(before):], before, "an earlier operation changed")
        for op in new:
            self.assertTrue(op.startswith(("snapshot working copy", "import git refs")), new)
        return new

    def git_c(self, *args, cwd=None):
        r = subprocess.run([jjenv.real_git(), *args], cwd=str(cwd or self.work), env=self.env, capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, "git %s: %s%s" % (" ".join(args), r.stdout, r.stderr))
        return r.stdout.strip()


class TestUndoPlanJj(JjBase):
    def test_undo_plan_jj_commands_and_result(self):
        a = self.archived_branch()
        code, doc, raw = self.plan()
        self.assertEqual(code, 0, raw)
        self.assertTrue(doc["ok"], raw)
        self.assertEqual((doc["mode"], doc["archive_commit"], doc["branch"]), ("committed", a, BRANCH))
        script = fx.flat(doc["steps"])
        for forbidden in GIT_WRITES:
            self.assertNotIn(forbidden, script)
        self.assertIn("jj restore --from", script)
        self.assertIn("jj commit", script)
        self.assertNotIn("jj new", script)  # the archive is on the current branch
        self.assertTrue(any("jj restore" in w and "working tree" in w for w in doc["warnings"]), doc["warnings"])
        r = self.run_steps(doc["steps"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.jjc("log", "--no-graph", "-r", "@-", "-T", "description.first_line()"), SUBJECT)
        self.assertEqual(self.jjc("log", "--no-graph", "-r", BRANCH, "-T", "commit_id"),
                         self.jjc("log", "--no-graph", "-r", "@-", "-T", "commit_id"))
        arch, chg = f"{P}/changes/archive/{fx.DATE}-add-x/", f"{P}/changes/add-x/"
        touched = self.names("@-")
        self.assertTrue(touched, "the undo commit is empty")
        for path in touched:
            self.assertTrue(path.startswith((arch, chg, f"{P}/specs/")), path)
        self.assertIn(f"{P}/specs/a/spec.md", touched)
        self.assertIn(f"{P}/specs/b/spec.md", touched)
        self.assertEqual(self.names("@"), set())
        self.assertTrue((self.work / P / "changes" / "add-x" / "review.md").is_file())
        self.assertFalse((self.work / P / "changes" / "archive" / f"{fx.DATE}-add-x").exists())
        self.assertNotIn("New thing", fx.read(self.work, f"{P}/specs/a/spec.md"))
        self.assertFalse((self.work / P / "specs" / "b" / "spec.md").exists())
        self.assertTrue(Path(doc["backup_dir"]).is_dir())

    def test_undo_plan_jj_other_branch_moves_wc(self):
        a = self.archived_branch()
        self.jjc("new", "main")
        self.jjc("bookmark", "create", "feat/other", "-r", "@-")
        code, doc, raw = self.plan()
        self.assertEqual(code, 0, raw)
        self.assertEqual((doc["mode"], doc["archive_commit"]), ("committed", a))
        script = fx.flat(doc["steps"])
        for forbidden in GIT_WRITES:
            self.assertNotIn(forbidden, script)
        self.assertIn(f"jj new {BRANCH}", script)
        self.assertLess(script.index("jj new"), script.index("jj restore --from"))
        r = self.run_steps(doc["steps"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.jjc("log", "--no-graph", "-r", "@-", "-T", "description.first_line()"), SUBJECT)
        self.assertEqual(self.jjc("log", "--no-graph", "-r", BRANCH, "-T", "commit_id"),
                         self.jjc("log", "--no-graph", "-r", "@-", "-T", "commit_id"))
        self.assertEqual(self.jjc("log", "--no-graph", "-r", f"{BRANCH}-", "-T", "commit_id"), a)
        self.assertEqual(self.jjc("log", "--no-graph", "-r", "feat/other", "-T", "commit_id"),
                         self.jjc("log", "--no-graph", "-r", "main", "-T", "commit_id"))
        self.assertTrue((self.work / P / "changes" / "add-x" / "review.md").is_file())

    def test_undo_plan_jj_guard_fails_first(self):
        self.archived_branch()
        fx.write(self.work, f"{P}/changes/archive/{fx.DATE}-add-x/notes.md", "mine\n")
        code, doc, raw = self.plan()
        self.assertEqual(code, 0, raw)
        before = self.snapshot()
        r = self.run_steps(doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(Path(doc["backup_dir"]).exists())

    def test_undo_plan_jj_wrong_branch(self):
        self.archived_branch()
        self.jjc("new", "main")
        self.jjc("bookmark", "create", "feat/other", "-r", "@-")
        fx.write(self.work, "README.md", "edited\n")
        before = self.snapshot()
        code, doc, raw = self.plan()
        self.assertEqual(code, 1, raw)
        self.assertFalse(doc["ok"], raw)
        self.assertEqual(doc["error"], "dirty_tree", raw)
        self.assertIn("README.md", doc["message"])
        self.assertIn("working copy", doc["message"])
        # the jj resume stop keeps its message and its files (change-finish: other dirty stops keep their messages)
        self.assertEqual(doc["message"], f"The working copy @ is not empty, so it cannot move onto {BRANCH} with jj new: README.md")
        self.assertEqual(doc["files"], ["README.md"])
        self.assertNotIn("steps", doc)
        self.assertEqual(self.snapshot(), before)

    def test_jj_plan_prints_jj_steps(self):
        # the steps work with jj and sw only, each in the repository's top; a git write would break a colocated repo
        self.archived_branch()
        code, doc, raw = self.plan()
        self.assertEqual(code, 0, raw)
        steps = doc["steps"]
        for step in steps:
            self.assertEqual(set(step), {"cwd", "argv"}, step)
            self.assertEqual(Path(step["cwd"]).resolve(), self.work.resolve(), step)
            self.assertIn(Path(step["argv"][0]).stem, ("jj", "sw"), step)
        self.assertTrue(any(s["argv"][:2] == ["jj", "commit"] for s in steps), steps)
        self.assertTrue(any(s["argv"][:2] == ["jj", "restore"] for s in steps), steps)
        r = self.run_steps(steps)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.jjc("log", "--no-graph", "-r", "@-", "-T", "description.first_line()"), SUBJECT)

    # ---- group 13: the planner reads what jj itself records (C42) and checks the settings first ------------------------
    def test_jj_plan_changes_no_file(self):
        self.archived_branch()
        before_ops, before_files, refs = self.ops(), self.files(), self.git_c("for-each-ref")
        code, doc, raw = self.plan()
        self.assertEqual(code, 0, raw)
        self.assertEqual(self.files(), before_files)
        self.only_sync_ops(before_ops)
        self.assertEqual(self.git_c("for-each-ref"), refs)

    def test_a_jj_plan_with_an_unsnapshotted_edit(self):
        self.archived_branch()
        self.jjc("status")  # jj records the baseline; the edit below comes after it
        fx.write(self.work, "README.md", "edited after the last snapshot\n")
        before_ops, before_files = self.ops(), self.files()
        code, doc, raw = self.plan()
        self.assertEqual(code, 0, raw)
        self.assertEqual(self.files(), before_files)
        new = self.only_sync_ops(before_ops)
        self.assertTrue(any(op.startswith("snapshot working copy") for op in new), new)

    def push_branch(self):
        """feat/add-x on the origin, and the local bookmark tracking it."""
        self.git_c("push", "-q", "origin", "refs/heads/%s:refs/heads/%s" % (BRANCH, BRANCH))
        self.jjc("bookmark", "track", BRANCH, "--remote", "origin")

    def remote_commit(self, text):
        """Another clone commits `text` on feat/add-x and pushes it; returns the new remote tip."""
        other = self.tmp / "other"
        if not other.exists():
            self.git_c("clone", "-q", str(self.scratch.origin), str(other), cwd=self.tmp)
            for key, value in (("user.name", "T"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
                self.git_c("config", key, value, cwd=other)
            self.git_c("checkout", "-q", BRANCH, cwd=other)
        (other / "remote.txt").write_text(text, encoding="utf-8")
        self.git_c("add", "remote.txt", cwd=other)
        self.git_c("commit", "-q", "-m", "remote work", cwd=other)
        self.git_c("push", "-q", "origin", "HEAD:refs/heads/" + BRANCH, cwd=other)
        return self.git_c("rev-parse", "HEAD", cwd=other)

    def test_a_jj_plan_with_a_pending_git_ref_import(self):
        a = self.archived_branch()
        self.push_branch()
        self.jjc("new", "main")  # the resume starts from main
        moved = self.remote_commit("remote one\n")
        self.git_c("fetch", "-q", "origin")  # a plain `git fetch`, which jj has not imported
        self.assertEqual(self.git_c("rev-parse", "refs/remotes/origin/" + BRANCH), moved)
        self.assertEqual(self.git_c("rev-parse", "refs/heads/" + BRANCH), a, "jj imported before the plan")
        before_ops, before_files = self.ops(), self.files()
        code, doc, raw = self.plan()
        self.assertEqual(code, 0, raw)
        self.assertEqual(self.files(), before_files)
        new = self.only_sync_ops(before_ops)
        self.assertTrue(any(op.startswith("import git refs") for op in new), new)
        self.assertEqual(self.git_c("rev-parse", "refs/heads/" + BRANCH), moved, "the tracked bookmark did not follow")

    def test_a_conflicted_resume_bookmark_is_ambiguous_branch(self):
        a = self.archived_branch()
        self.push_branch()
        remote = self.remote_commit("remote one\n")
        # the local bookmark moves on its own, so the import finds both sides changed
        self.jjc("new", BRANCH)
        fx.write(self.work, "local.txt", "local\n")
        self.jjc("commit", "-m", "local work")
        self.jjc("bookmark", "set", BRANCH, "-r", "@-")
        self.jjc("new", "main")
        local = self.git_c("rev-parse", "refs/heads/" + BRANCH)
        self.git_c("fetch", "-q", "origin")
        self.assertEqual(len({a, local, remote}), 3, "the fixture needs a local and a remote move from the same tip")
        before_ops, before_files = self.ops(), self.files()
        code, doc, raw = self.plan()
        self.assertEqual(code, 1, raw)
        self.assertEqual(doc["error"], "ambiguous_branch", raw)
        self.assertNotIn("steps", doc)
        self.assertEqual(self.files(), before_files)
        self.only_sync_ops(before_ops)

    def test_an_unbookmarked_child_of_the_archive_tip(self):
        a = self.archived_branch()
        self.jjc("new", BRANCH)
        fx.write(self.work, "child.txt", "child\n")
        self.jjc("commit", "-m", "work after the archive")  # @- is a child of the archive tip with no bookmark; @ is empty
        self.assertEqual(self.jjc("log", "--no-graph", "-r", "@-", "-T", "bookmarks"), "")
        code, doc, raw = self.plan()
        self.assertEqual(code, 0, raw)
        argvs = [s["argv"] for s in doc["steps"]]
        guard = [n for n, argv in enumerate(argvs) if argv[-3:] == ["", "--backend", "jj"]]
        self.assertTrue(guard, "no pre-move check expects an empty source branch: %s" % argvs)
        clean = next(n for n, argv in enumerate(argvs) if "clean" in argv and "--jj" in argv)
        move = argvs.index(["jj", "new", BRANCH])
        self.assertLess(guard[0], clean)
        self.assertLess(clean, move)
        r = self.run_steps(doc["steps"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.jjc("log", "--no-graph", "-r", BRANCH, "-T", "description.first_line()"), SUBJECT)
        self.assertEqual(self.jjc("log", "--no-graph", "-r", BRANCH + "-", "-T", "commit_id"), a)

    def test_a_jj_store_resume_whose_backend_changed_after_planning(self):
        self.archived_branch()
        self.jjc("new", "main")
        self.jjc("bookmark", "create", "feat/other", "-r", "@-")
        code, doc, raw = self.plan()
        self.assertEqual(code, 0, raw)
        shim_dir, log = self.tmp / "jjshim", self.tmp / "jj-calls.txt"
        shim_dir.mkdir()
        shim = fakeexe.write_fake(shim_dir / "jj", '#!/bin/sh\necho "$@" >> "$SW_JJ_LOG"\nexec "$SW_REAL_JJ" "$@"\n', exe=True)
        env = {**self.env, "PATH": str(shim_dir) + os.pathsep + self.env.get("PATH", os.environ.get("PATH", "")),
               "SW_JJ_LOG": str(log), "SW_REAL_JJ": str(self.jj)}
        fx.write(self.work, f"{P}/specwright.yaml", "vcs: git\n")  # the settings change is itself an unsnapshotted edit
        before = self.files()
        r = fx.run_steps(self.tmp, doc["steps"], env=env)  # PATH finds the shim: jj.exe on Windows, the script elsewhere
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("git_env", r.stdout + r.stderr)
        self.assertEqual(len(r.ran), 1, "a step after the branch check ran")
        self.assertEqual(log.read_text(encoding="utf-8") if log.exists() else "", "", "a jj command ran")
        self.assertEqual(self.files(), before)

    def test_a_jj_bulk_undo_whose_commit_fileset_is_too_long(self):
        names = ["c%03d-%s" % (i, "x" * 70) for i in range(300)]
        for name in names:
            fx.make_change(self.work, name, "DEFERRED", None, commit_it=False)
        self.jjc("commit", "-m", "docs: planning artifacts")
        fx.archive(self.work, names, commit_it=False)
        self.jjc("commit", "-m", "chore: archive changes")
        self.jjc("bookmark", "create", BRANCH, "-r", "@-")
        tip = self.git_c("rev-parse", "refs/heads/" + BRANCH)
        before_ops, before_files = self.ops(), self.files()
        code, doc, raw = self.finish("undo-archive-plan", "--change", names[0], "--archived-name", f"{fx.DATE}-{names[0]}",
                                     "--prefix", P, "--main", "main", "--branch", BRANCH)
        self.assertEqual(code, 1, raw[:600])
        self.assertEqual(doc["error"], "plan_too_large", raw[:600])
        # the line that overflows is the commit's fileset, not the `check clean --jj` line a chunked plan no longer builds
        self.assertIn("jj commit", doc["message"], raw[:600])
        self.assertNotIn("steps", doc)
        self.assertEqual(self.files(), before_files)
        self.assertEqual(self.git_c("rev-parse", "refs/heads/" + BRANCH), tip)
        self.only_sync_ops(before_ops)


if __name__ == "__main__":
    unittest.main()
