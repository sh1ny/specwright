"""The backend reports jj bookmarks and Git state from observable repository data."""
from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase


class TestJjState(VcsTestCase):
    def setUp(self):
        super().setUp()
        require_jj()
        self.scratch = Scratch()
        self.addCleanup(self.scratch.close)
        self.repo = self.scratch.tracked_repo().path
        (self.repo / "openspec").mkdir(exist_ok=True)
        (self.repo / "openspec" / "specwright.yaml").write_text("vcs: jj\n", encoding="utf-8")

    def test_state_one_bookmark_beside_main(self):
        jj = require_jj()
        import subprocess
        result = subprocess.run([jj, "bookmark", "create", "feat/x", "-r", "@-", "--repository", str(self.repo)],
                                env=self.scratch.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state, _ = self.invoke("state", repo=self.repo)
        self.assertEqual(state["branch"], "feat/x")
        self.assertFalse(state["on_main"])

    def test_state_two_bookmarks_ambiguous(self):
        jj = require_jj()
        import subprocess
        for branch in ("feat/x", "docs/y"):
            result = subprocess.run([jj, "bookmark", "create", branch, "-r", "@-", "--repository", str(self.repo)],
                                    env=self.scratch.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state, _ = self.invoke("state", repo=self.repo, expected=1)
        self.assertEqual(state["error"], "ambiguous_branch")
        self.assertIn("feat/x", state["message"])
        self.assertIn("docs/y", state["message"])

    def test_state_off_main_no_branch(self):
        jj = require_jj()
        import subprocess
        result = subprocess.run([jj, "new", "--repository", str(self.repo)], env=self.scratch.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state, _ = self.invoke("state", repo=self.repo)
        self.assertEqual(state["branch"], "")
        self.assertFalse(state["on_main"])

    def test_state_two_parent_working_copy_ambiguous(self):
        jj = require_jj()
        import subprocess
        for args in (("commit", "-m", "settings"), ("bookmark", "set", "main", "-r", "@-"),
                     ("new", "main", "-m", "left"), ("new", "main", "-m", "right")):
            subprocess.run([jj, *args, "--repository", str(self.repo)], env=self.scratch.env,
                           capture_output=True, text=True, check=True)
        result = subprocess.run([jj, "new", 'description(exact:"left\\n")', 'description(exact:"right\\n")',
                                 "--repository", str(self.repo)], env=self.scratch.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state, _ = self.invoke("state", repo=self.repo, expected=1)
        self.assertEqual(state["error"], "ambiguous_branch")

    def test_state_conflicted_bookmark_ambiguous(self):
        jj = require_jj()
        import subprocess

        def run(*args):
            result = subprocess.run([jj, *args, "--repository", str(self.repo)], env=self.scratch.env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout.strip()

        run("commit", "-m", "settings")
        run("bookmark", "set", "main", "-r", "@-")
        run("new", "main", "-m", "left")
        run("new", "main", "-m", "right")
        left = run("log", "--no-graph", "-r", 'description(exact:"left\\n")', "-T", "commit_id")
        right = run("log", "--no-graph", "-r", 'description(exact:"right\\n")', "-T", "commit_id")
        run("bookmark", "create", "feat/x", "-r", left)
        run("--at-op", "@-", "bookmark", "create", "feat/x", "-r", right)
        run("new", left)
        state, _ = self.invoke("state", repo=self.repo, expected=1)
        self.assertEqual(state["error"], "ambiguous_branch", state)

    def test_state_dirty_lists_paths(self):
        (self.repo / "dirty file.txt").write_text("dirty\n", encoding="utf-8")
        state, _ = self.invoke("state", repo=self.repo)
        self.assertFalse(state["clean"])
        self.assertIn("dirty file.txt", state["dirty_paths"])
        self.assertTrue(all("\\" not in path for path in state["dirty_paths"]))


class TestGitState(VcsTestCase):
    def test_git_state_reports_jj_present(self):
        (self.repo / ".jj").mkdir()
        state, _ = self.invoke("state")
        self.assertTrue(state["jj_present"])
        self.assertEqual(state["backend"], "git")

    def test_git_state_no_jj_note_runs_no_jj(self):
        state, _ = self.invoke("state")
        self.assertNotIn("jj_present", state)
        self.assertEqual(state["backend"], "git")

    def test_git_writes_ignore_bad_merge_settings(self):
        """Only the agent merge reads pr.merge_method and pr.delete_branch: a typo there stops no branch write."""
        self.set_settings(self.repo, "pr:\n  merge: agent\n  merge_method: typo\n  delete_branch: maybe\n")
        self.git(self.repo, "add", "openspec")
        self.git(self.repo, "commit", "-m", "settings")
        for command, options in (("probe", ()), ("state", ()), ("branch-create", ("--branch", "feat/add-x"))):
            with self.subTest(command):
                result, _ = self.invoke(command, *options)
                self.assertTrue(result["ok"], result)
        self.assertEqual(self.git(self.repo, "branch", "--show-current").stdout.strip(), "feat/add-x")

    def test_git_dirty_paths_are_real_paths(self):
        """Porcelain quotes names with spaces or non-ASCII characters; the state lists the names themselves."""
        notes = self.repo / "openspec" / "changes" / "add-x" / "notes draft.md"
        notes.parent.mkdir(parents=True)
        notes.write_text("draft\n", encoding="utf-8")
        (self.repo / "naïve.txt").write_text("x\n", encoding="utf-8")
        self.git(self.repo, "mv", "base.txt", "moved base.txt")
        state, _ = self.invoke("state")
        self.assertEqual(sorted(state["dirty_paths"]), sorted([
            "base.txt", "moved base.txt", "naïve.txt", "openspec/"]))
        for path in state["dirty_paths"]:
            self.assertTrue(path == "base.txt" or (self.repo / path).exists(), path)
        renamed = next(entry for entry in state["dirty"] if entry["path"] == "moved base.txt")
        self.assertEqual((renamed["status"], renamed["from"]), ("R ", "base.txt"))
