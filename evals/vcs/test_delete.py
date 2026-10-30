"""Deleting a jj branch forgets it locally, only once merged, and never publishes a deletion."""

from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase


class TestJjDelete(VcsTestCase):
    branch = "feat/add-x"

    def setUp(self):
        super().setUp()
        self.jj = require_jj()
        self.scratch = Scratch()
        self.addCleanup(self.scratch.close)
        self.fixture = self.scratch.tracked_repo()
        self.repo = self.fixture.path
        self.set_settings(self.repo, "vcs: jj\nmain_branch: main\n")
        self.fixture.run(self.jj, "commit", "-m", "fixture Specwright settings")
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", "@-")
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "feat(add-x): work")
        self.fixture.run(self.jj, "bookmark", "create", self.branch, "-r", "@-")
        self.fixture.run(self.jj, "git", "push", "--bookmark", 'exact:"%s"' % self.branch)

    def exists(self, ref, git_dir=None):
        args = ["--git-dir", str(git_dir)] if git_dir else []
        return self.git(self.repo, *args, "rev-parse", "--verify", "--quiet", ref).returncode == 0

    def test_delete_forgets_no_remote_deletion(self):
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", self.branch)
        self.assertTrue(self.exists("refs/heads/" + self.branch))

        result, _ = self.invoke("delete-branch", "--branch", self.branch, repo=self.repo)

        self.assertTrue(result["ok"], result)
        self.assertFalse(self.exists("refs/heads/" + self.branch))
        listed = self.fixture.run(self.jj, "bookmark", "list", "--all-remotes", "-T",
                                  'name ++ "@" ++ remote ++ "\\n"').stdout
        self.assertNotIn(self.branch + "@\n", listed)
        for flag in ("--deleted", "--tracked"):
            self.fixture.run(self.jj, "git", "push", flag, check=False)
        self.assertTrue(self.exists("refs/heads/" + self.branch, git_dir=self.scratch.origin),
                        "a later jj git push must not delete the remote branch")

    def test_delete_unmerged_stops(self):
        result, _ = self.invoke("delete-branch", "--branch", self.branch, repo=self.repo, expected=1)

        self.assertEqual(result["error"], "not_merged")
        self.assertTrue(self.exists("refs/heads/" + self.branch))
        listed = self.fixture.run(self.jj, "bookmark", "list", "-T", 'name ++ "\\n"').stdout.split()
        self.assertIn(self.branch, listed)

    def test_delete_force_skips_merged_check(self):
        result, _ = self.invoke("delete-branch", "--branch", self.branch, "--force", repo=self.repo)

        self.assertTrue(result["ok"], result)
        self.assertFalse(self.exists("refs/heads/" + self.branch))
