"""A jj push publishes only the change bookmark, and only a bookmark at @- with sound commits."""

from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase


class TestJjPush(VcsTestCase):
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

    def commit_on_branch(self, name="feature.txt", message="feat(add-x): work"):
        (self.repo / name).write_text("feature\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", message)
        self.fixture.run(self.jj, "bookmark", "set", self.branch, "-r", "@-")

    def origin_refs(self):
        out = self.git(self.scratch.origin, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads").stdout
        return dict(line.split() for line in out.splitlines())

    def push(self, expected=0):
        return self.invoke("push", "--branch", self.branch, repo=self.repo, expected=expected)

    def test_push_only_change_bookmark(self):
        initial = self.origin_refs()
        self.fixture.run(self.jj, "bookmark", "create", self.branch, "-r", "@-")
        self.commit_on_branch()
        self.fixture.run(self.jj, "bookmark", "create", "side/other", "-r", "main")
        (self.repo / "leftover.txt").write_text("uncommitted\n", encoding="utf-8")

        result, _ = self.push()

        self.assertTrue(result["ok"], result)
        head = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        refs = self.origin_refs()
        self.assertEqual(refs["refs/heads/" + self.branch], head)
        self.assertEqual(set(refs) - set(initial), {"refs/heads/" + self.branch})
        self.assertEqual(refs["refs/heads/main"], initial["refs/heads/main"])

    def test_push_conflicted_stops(self):
        self.fixture.run(self.jj, "bookmark", "create", self.branch, "-r", "@-")
        (self.repo / "README.md").write_text("branch side\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "feat(add-x): readme")
        self.fixture.run(self.jj, "bookmark", "set", self.branch, "-r", "@-")
        self.fixture.run(self.jj, "new", "main")
        (self.repo / "README.md").write_text("main side\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "chore: main readme")
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", "@-")
        self.fixture.run(self.jj, "rebase", "-b", self.branch, "-o", "main")
        self.fixture.run(self.jj, "new", self.branch)
        conflicted = self.fixture.run(self.jj, "log", "--no-graph", "-r", 'conflicts() & (main.."feat/add-x")', "-T", "commit_id").stdout.strip()
        self.assertTrue(conflicted)
        initial = self.origin_refs()

        result, _ = self.push(expected=1)

        self.assertEqual(result["error"], "conflicted")
        self.assertIn(conflicted, result["message"])
        self.assertEqual(self.origin_refs(), initial)

    def test_push_bookmark_not_parent_stops(self):
        self.fixture.run(self.jj, "bookmark", "create", self.branch, "-r", "@-")
        self.commit_on_branch()
        (self.repo / "later.txt").write_text("later\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "feat(add-x): not yet on the bookmark")
        initial = self.origin_refs()

        result, _ = self.push(expected=1)

        self.assertEqual(result["error"], "wrong_branch")
        self.assertEqual(self.origin_refs(), initial)

    def test_push_undescribed_stops(self):
        self.fixture.run(self.jj, "bookmark", "create", self.branch, "-r", "@-")
        self.commit_on_branch(message="")
        initial = self.origin_refs()

        result, _ = self.push(expected=1)

        self.assertEqual(result["error"], "undescribed")
        self.assertEqual(self.origin_refs(), initial)
