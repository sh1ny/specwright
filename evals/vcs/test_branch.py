"""The jj gate creates its change bookmark at the parent of the working copy."""

import subprocess

from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase


class TestJjBranchCreate(VcsTestCase):
    def setUp(self):
        super().setUp()
        require_jj()
        self.scratch = Scratch()
        self.addCleanup(self.scratch.close)
        self.fixture = self.scratch.tracked_repo()
        self.repo = self.fixture.path
        self.set_settings(self.repo, "vcs: jj\nmain_branch: main\n")
        self.fixture.run(require_jj(), "commit", "-m", "fixture Specwright settings")
        self.fixture.run(require_jj(), "bookmark", "set", "main", "-r", "@-")

    def test_branch_create_at_parent(self):
        result, _ = self.invoke("branch-create", "--branch", "feat/add-jj-backend", repo=self.repo)
        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "jj")

        head = self.git(self.repo, "rev-parse", "HEAD")
        bookmark = self.git(self.repo, "rev-parse", "refs/heads/feat/add-jj-backend")
        parent = subprocess.run(
            [require_jj(), "log", "--no-graph", "-r", "@-", "-T", "commit_id", "--repository", str(self.repo)],
            env=self.scratch.env, capture_output=True, text=True)
        self.assertEqual(parent.returncode, 0, parent.stdout + parent.stderr)
        self.assertEqual(head.returncode, 0, head.stderr)
        self.assertEqual(bookmark.returncode, 0, bookmark.stderr)
        self.assertEqual(bookmark.stdout.strip(), parent.stdout.strip())
        self.assertEqual(head.stdout.strip(), bookmark.stdout.strip())

    def test_rollback_deletes_empty_bookmark_without_switch(self):
        """The gate's jj rollback: the new bookmark shares main's commit, so a switch to main changes nothing and `state`
        still reports the change branch; delete-branch alone puts the repo back on main."""
        branch = "feat/add-jj-backend"
        self.invoke("branch-create", "--branch", branch, repo=self.repo)
        self.invoke("switch", "--branch", "main", repo=self.repo)
        state, _ = self.invoke("state", repo=self.repo)
        self.assertEqual((state["branch"], state["on_main"]), (branch, False))

        result, _ = self.invoke("delete-branch", "--branch", branch, repo=self.repo)
        self.assertTrue(result["ok"], result)
        state, _ = self.invoke("state", repo=self.repo)
        self.assertTrue(state["on_main"], state)
        self.assertEqual(self.git(self.repo, "rev-parse", "--verify", "-q", "refs/heads/" + branch).returncode, 1)
