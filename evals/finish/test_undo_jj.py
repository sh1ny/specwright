"""finish.sh undo-archive-plan on a colocated jj repo (real jj): the emitted script works the working copy and commits
named paths with `jj commit`; it never runs a Git write.

Run: python -m unittest test_undo_jj   (from evals/finish)
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
import jjenv  # noqa: E402
import bashexe  # noqa: E402
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
        r = vcs_test_support.bash_run([fx.SCRIPT.as_posix(), *args], self.work, self.env)
        try:
            doc = json.loads(r.stdout)
        except ValueError:
            doc = None
        return r.returncode, doc, r.stdout + r.stderr

    def plan(self, **kw):
        args = ["undo-archive-plan", "--change", "add-x", "--archived-name", f"{fx.DATE}-add-x", "--prefix", P,
                "--main", "main", "--branch", BRANCH]
        return self.finish(*args)

    def run_script(self, text, name="undo"):
        path = self.tmp / f"{name}.sh"
        path.write_text(text, encoding="utf-8", newline="\n")
        return vcs_test_support.bash_run([path.as_posix()], self.work, self.env)

    def snapshot(self):
        files = {k: v for k, v in fx.snapshot(self.work).items() if not k.startswith(".jj/")}
        return {"files": files, "log": self.jjc("log", "--no-graph", "-r", "all()", "-T",
                                                                  'commit_id ++ " " ++ bookmarks ++ "\\n"')}


class TestUndoPlanJj(JjBase):
    def test_undo_plan_jj_commands_and_result(self):
        a = self.archived_branch()
        code, doc, raw = self.plan()
        self.assertEqual(code, 0, raw)
        self.assertTrue(doc["ok"], raw)
        self.assertEqual((doc["mode"], doc["archive_commit"], doc["branch"]), ("committed", a, BRANCH))
        script = doc["script"]
        for forbidden in GIT_WRITES:
            self.assertNotIn(forbidden, script)
        self.assertIn("jj restore --from", script)
        self.assertIn("jj commit", script)
        self.assertNotIn("jj new", script)  # the archive is on the current branch
        self.assertTrue(any("jj restore" in w and "working tree" in w for w in doc["warnings"]), doc["warnings"])
        r = self.run_script(script)
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
        script = doc["script"]
        for forbidden in GIT_WRITES:
            self.assertNotIn(forbidden, script)
        self.assertIn(f"jj new {BRANCH}", script)
        self.assertLess(script.index("jj new"), script.index("jj restore --from"))
        r = self.run_script(script)
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
        r = self.run_script(doc["script"])
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
        self.assertNotIn("script", doc)
        self.assertEqual(self.snapshot(), before)


class TestVcsScriptMissing(unittest.TestCase):
    def test_undo_plan_vcs_script_missing(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, tmp)
        work = fx.make_repo(tmp)
        lone = tmp / "skills" / "specwright-finish" / "scripts"
        lone.mkdir(parents=True)
        (lone / "finish.sh").write_bytes(fx.SCRIPT.read_bytes())
        r = subprocess.run([bashexe.bash(), str(lone / "finish.sh"), "undo-archive-plan", "--change", "add-x", "--archived-name",
                            f"{fx.DATE}-add-x", "--prefix", P, "--main", "main", "--branch", BRANCH],
                           cwd=work, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual(doc["error"], "vcs_script_missing")
        self.assertIn("specwright-pr/scripts/vcs.sh", doc["message"].replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
