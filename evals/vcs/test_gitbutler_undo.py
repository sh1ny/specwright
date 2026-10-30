"""finish.sh undo-archive-plan on a GitButler repo (real `but`): the emitted script moves the archive back, writes the main
specs from `git cat-file --filters`, and commits exactly the touched paths with `but commit -b <branch>`; it runs no Git write.

`feat/b` stays applied beside the change branch, with a commit and an uncommitted edit of its own, throughout.
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import jjenv
from butenv import Scratch, require_but
from test_gitbutler_flows import BRANCH, CHANGE, GitButlerFlowCase

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("finish_fixtures", ROOT / "evals" / "finish" / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

P = "openspec"
ARCHIVED = "%s-%s" % (fx.DATE, CHANGE)
ARCHIVE_DIR = "%s/changes/archive/%s" % (P, ARCHIVED)
CHANGE_DIR = "%s/changes/%s" % (P, CHANGE)
SUBJECT = "feat(add-c): undo archive of add-c"
GIT_WRITES = ("git restore", "git checkout", "git add", "git commit", "git rm", "git read-tree", "git stash", "git reset")


class TestGitButlerUndoPlan(GitButlerFlowCase):
    def commit_paths(self, scratch, wrap, subject, *paths):
        result = self.commit(scratch, wrap, subject + "\n", *paths)
        self.assertTrue(result["ok"], result)
        return result["commit"]

    def names(self, repo, rev):
        out = self.git(repo.path, "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", rev).stdout
        return sorted(line for line in out.splitlines() if line)

    def plan(self, scratch, wrap, repo):
        return self.script(scratch, wrap, ROOT / "skills" / "specwright-finish" / "scripts" / "finish.sh", "undo-archive-plan",
                           "--change", CHANGE, "--archived-name", ARCHIVED, "--prefix", P, "--main", "main", "--branch", BRANCH,
                           cwd=repo.path)

    def run_script(self, scratch, wrap, repo, text, name="undo", expected=0):
        path = self.root / ("%s.sh" % name)
        path.write_text(text, encoding="utf-8", newline="\n")
        env = self.fenced_env(scratch, wrap)
        env["VCS_TEST_SEARCH"] = env["PATH"]
        done = subprocess.run([jjenv.find_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"', "undo",
                               path.as_posix()], cwd=str(repo.path), env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode != 0, expected != 0, done.stdout + done.stderr)
        return done

    def test_undo_plan_uses_but_commit(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            self.other_agent(repo, wrap)
            repo.but("branch", "new", BRANCH)
            work = repo.path
            fx.write(work, "%s/specs/a/spec.md" % P, fx.base_spec("a"))
            fx.make_change(work, CHANGE, "DEFERRED", {"a": "New thing", "b": "B thing"}, commit_it=False)
            planning = self.commit_paths(scratch, wrap, "docs(add-c): add planning artifacts", "%s/specs/a/spec.md" % P,
                                         CHANGE_DIR + "/")
            fx.archive(work, CHANGE, commit_it=False)
            archive = self.commit_paths(scratch, wrap, "chore(add-c): archive change", ARCHIVE_DIR + "/", CHANGE_DIR + "/",
                                        "%s/specs/a/spec.md" % P, "%s/specs/b/spec.md" % P)
            self.assertEqual(self.git(work, "rev-parse", archive + "^").stdout.strip(), planning)
            tips = {name: self.tip(repo, name) for name in ("feat/b", "main")}
            side_edit = (work / "src" / "b.py").read_text(encoding="utf-8")

            doc = self.plan(scratch, wrap, repo)

            self.assertTrue(doc["ok"], doc)
            self.assertEqual((doc["mode"], doc["archive_commit"], doc["branch"]), ("committed", archive, BRANCH))
            script = doc["script"]
            for forbidden in GIT_WRITES:
                self.assertNotIn(forbidden, script)
            self.assertNotIn("git branch --show-current", script, "HEAD is the workspace commit: the branch is not read from it")
            self.assertRegex(script, r"vcs\.sh' commit .*--branch feat/add-c|vcs\.sh commit .*--branch feat/add-c")
            self.assertIn("git cat-file --filters", script)
            for path in (ARCHIVE_DIR, CHANGE_DIR, "%s/specs/a/spec.md" % P, "%s/specs/b/spec.md" % P):
                self.assertIn(path, script)
            calls_before = len(wrap.calls())

            # a touched path with an uncommitted edit stops the script before anything moves
            spec_a = work / P / "specs" / "a" / "spec.md"
            clean_bytes = spec_a.read_bytes()  # bytes, so the restore leaves no line-ending change behind
            spec_a.write_bytes(clean_bytes + b"\nmy own edit\n")
            stopped = self.run_script(scratch, wrap, repo, script, "guard", expected=1)
            self.assertTrue((work / P / "changes" / "archive" / ARCHIVED).is_dir(), "the guard let the script move the archive")
            self.assertFalse((work / P / "changes" / CHANGE).exists())
            self.assertEqual(self.tip(repo, BRANCH), archive)
            self.assertEqual([c for c in wrap.calls()[calls_before:] if c[:1] == ["commit"]], [], "the guard let a but commit run")
            spec_a.write_bytes(clean_bytes)
            self.assertEqual(self.uncommitted(repo), ["src/b.py"], "only feat/b's edit is uncommitted")

            done = self.run_script(scratch, wrap, repo, script)

            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            new = self.tip(repo, BRANCH)
            self.assertNotEqual(new, archive)
            self.assertEqual(self.git(work, "rev-parse", new + "^").stdout.strip(), archive)
            self.assertEqual(self.git(work, "log", "-1", "--format=%s", new).stdout.strip(), SUBJECT)
            touched = self.names(repo, new)
            self.assertTrue(touched, "the undo commit is empty")
            for path in touched:
                self.assertTrue(path.startswith((ARCHIVE_DIR + "/", CHANGE_DIR + "/", P + "/specs/")), path)
            self.assertIn("%s/specs/a/spec.md" % P, touched)
            self.assertIn("%s/specs/b/spec.md" % P, touched)
            self.assertIn("%s/review.md" % CHANGE_DIR, touched)
            but_commits = [c for c in wrap.calls()[calls_before:] if c[:1] == ["commit"]]
            self.assertEqual(len(but_commits), 1, but_commits)
            self.assertEqual(but_commits[0][1:3], ["-b", BRANCH])
            # the files are back as the pre-archive commit had them
            self.assertTrue((work / P / "changes" / CHANGE / "review.md").is_file())
            self.assertFalse((work / P / "changes" / "archive" / ARCHIVED).exists())
            self.assertNotIn("New thing", spec_a.read_text(encoding="utf-8"))
            self.assertFalse((work / P / "specs" / "b" / "spec.md").exists())
            self.assertEqual(self.git(work, "show", planning + ":%s/specs/a/spec.md" % P).stdout, spec_a.read_text(encoding="utf-8"))
            # the other agent's branch and edit, and main, are untouched
            self.assertEqual(self.tip(repo, "feat/b"), tips["feat/b"])
            self.assertEqual(self.tip(repo, "main"), tips["main"])
            self.assertEqual((work / "src" / "b.py").read_text(encoding="utf-8"), side_edit)
            self.assertEqual(self.uncommitted(repo), ["src/b.py"])
            self.assertEqual(self.applied(repo), [BRANCH, "feat/b"])
            self.assert_only_allowed_git_writes([])
            self.assertEqual(self.git_writes(), [], "the undo ran a Git write")
