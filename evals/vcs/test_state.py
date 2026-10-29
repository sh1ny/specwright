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
