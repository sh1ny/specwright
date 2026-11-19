"""`sw finish undo-archive-plan` on a GitButler repo (real `but`): outcome checks (native-cli-retire-scripts task 7.2).

The plan of a committed and of an uncommitted archive is run with its printed `steps` and the repository, branch and files
are checked afterwards; the frozen finish.sh is no longer run. The printed steps call `sw vcs`, not a shell script, and name no bash.
This module runs in the `vcs` suite job, the only one that installs `but`.
"""
import importlib.util
import json
import subprocess
from pathlib import Path

import jjenv
from butenv import Scratch, require_but
from test_gitbutler_flows import BRANCH, CHANGE, GitButlerFlowCase
from vcs_test_support import stamp_version, sw_home
import swcall  # noqa: E402  (vcs_test_support puts evals/ on sys.path)

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("finish_fixtures", ROOT / "evals" / "finish" / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

P = "openspec"
ARCHIVED = "%s-%s" % (fx.DATE, CHANGE)
ARCHIVE_DIR = "%s/changes/archive/%s" % (P, ARCHIVED)
CHANGE_DIR = "%s/changes/%s" % (P, CHANGE)


class TestGitButlerParity(GitButlerFlowCase):
    def commit_paths(self, scratch, wrap, subject, *paths):
        result = self.commit(scratch, wrap, subject + "\n", *paths)
        self.assertTrue(result["ok"], result)
        return result["commit"]

    def planned(self, scratch, wrap, repo):
        """sw's plan of the archive: (exit code, parsed document, raw output)."""
        args = fx.plan_args(CHANGE, archived=ARCHIVED, branch=BRANCH)
        env = self.step_env(scratch, wrap, repo)
        done = swcall.run(["finish", *args], cwd=str(repo.path), env=env)
        try:
            doc = json.loads(done.stdout)
        except ValueError:
            doc = None
        return done.returncode, doc, done.stdout + done.stderr

    def planned_doc(self, scratch, wrap, repo):
        code, doc, raw = self.planned(scratch, wrap, repo)
        self.assertEqual(code, 0, raw)
        self.assertNotIn("script", doc)
        return doc

    def archived(self, scratch, committed):
        """feat/b beside the change branch; the change branch holds the planning commit and the archive, committed or not."""
        wrap, repo = self.start(scratch)
        self.other_agent(repo, wrap)
        repo.but("branch", "new", BRANCH)
        work = repo.path
        fx.write(work, "%s/specs/a/spec.md" % P, fx.base_spec("a"))
        fx.make_change(work, CHANGE, "DEFERRED", {"a": "New thing", "b": "B thing"}, commit_it=False)
        for rel in ("notes/z.md", "notes/deep/a/leaf.md", "notes/deep/b/leaf.md"):  # nested folders: walk order
            fx.write(work, "%s/%s" % (CHANGE_DIR, rel), rel + "\n")
        self.commit_paths(scratch, wrap, "docs(add-c): add planning artifacts", "%s/specs/a/spec.md" % P, CHANGE_DIR + "/")
        fx.archive(work, CHANGE, commit_it=False)
        if committed:
            self.commit_paths(scratch, wrap, "chore(add-c): archive change", ARCHIVE_DIR + "/", CHANGE_DIR + "/",
                              "%s/specs/a/spec.md" % P, "%s/specs/b/spec.md" % P)
        return wrap, repo

    def step_env(self, scratch, wrap, repo):
        env = self.fenced_env(scratch, wrap)
        env.update({"SPECWRIGHT_STATE_DIR": str(self.root / "state"), "PYTHONIOENCODING": "utf-8",
                    "SPECWRIGHT_HOME": str(sw_home())})
        stamp_version(repo.path)
        env["VCS_TEST_SEARCH"] = env["PATH"]
        return env

    def run_step(self, step, env):
        """One printed `{cwd, argv}` step in its own cwd, through bash so the fixture's PATH finds git and but."""
        return subprocess.run([jjenv.find_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$@"', "step", *step["argv"]],
                              cwd=step["cwd"], env=env, capture_output=True, text=True, encoding="utf-8")

    def test_gitbutler_undo_steps_commit_paths_to_branch(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.archived(scratch, True)
            env = self.step_env(scratch, wrap, repo)
            doc = self.planned_doc(scratch, wrap, repo)
            other_tip = repo.git_run("rev-parse", "refs/heads/feat/b").stdout.strip()
            before = repo.git_run("rev-parse", "refs/heads/" + BRANCH).stdout.strip()
            for step in doc["steps"]:
                done = self.run_step(step, env)
                self.assertEqual(done.returncode, 0, "%s%s%s" % (step["argv"], done.stdout, done.stderr))
            tip = repo.git_run("rev-parse", "refs/heads/" + BRANCH).stdout.strip()
            self.assertNotEqual(tip, before, "no commit reached the change branch")
            self.assertEqual(repo.git_run("log", "-1", "--format=%s", tip).stdout.strip(), "feat(add-c): undo archive of add-c")
            touched = set(repo.git_run("diff-tree", "-r", "--no-commit-id", "--name-only", tip).stdout.split())
            self.assertIn("%s/review.md" % CHANGE_DIR, touched)
            self.assertTrue(any(t.startswith(ARCHIVE_DIR + "/") for t in touched), touched)
            for path in touched:
                self.assertTrue(path.startswith((CHANGE_DIR + "/", ARCHIVE_DIR + "/", P + "/specs/")), path)
            self.assertEqual(repo.git_run("rev-parse", "refs/heads/feat/b").stdout.strip(), other_tip, "feat/b moved")
            self.assertTrue((repo.path / CHANGE_DIR / "review.md").is_file())
            self.assertFalse((repo.path / ARCHIVE_DIR).exists())

    def run_all(self, doc, env):
        for key in ("steps", "after_rerun_steps"):
            for step in doc[key]:
                done = self.run_step(step, env)
                self.assertEqual(done.returncode, 0, "%s%s%s" % (step["argv"], done.stdout, done.stderr))

    def test_printed_steps_restore_a_committed_archive(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.archived(scratch, True)
            doc = self.planned_doc(scratch, wrap, repo)
            self.assertEqual(doc["mode"], "committed")
            self.run_all(doc, self.step_env(scratch, wrap, repo))
            self.assertTrue((repo.path / CHANGE_DIR / "review.md").is_file())
            self.assertFalse((repo.path / ARCHIVE_DIR).exists())

    def test_printed_steps_restore_an_uncommitted_archive(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.archived(scratch, False)
            doc = self.planned_doc(scratch, wrap, repo)
            self.assertEqual(doc["mode"], "uncommitted")
            self.run_all(doc, self.step_env(scratch, wrap, repo))
            self.assertTrue((repo.path / CHANGE_DIR / "review.md").is_file())
            self.assertFalse((repo.path / ARCHIVE_DIR).exists())

    def test_steps_call_sw_vcs_and_name_no_bash(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.archived(scratch, True)
            doc = self.planned_doc(scratch, wrap, repo)
            commits = [s["argv"] for s in doc["steps"] if s["argv"][3:5] == ["vcs", "commit"]]
            self.assertEqual(len(commits), 1, doc["steps"])
            self.assertEqual(Path(commits[0][2]).resolve(), repo.path.resolve())
            self.assertEqual(commits[0][1], "--project")
            self.assertIn("--", commits[0])
            self.assertTrue(any(s["argv"][3:6] == ["finish", "undo-step", "check"] and s["argv"][6] == "branch"
                                for s in doc["steps"]), "the branch guard is an undo-step check")
            for step in doc["steps"]:
                for word in step["argv"]:
                    self.assertFalse(word.endswith(".sh"), word)
                    self.assertNotEqual(Path(word).stem, "bash")
