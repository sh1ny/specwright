"""Interrupted jj commits move only when their complete history is in scope."""

from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase


class TestJjAdvance(VcsTestCase):
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
        self.branch = "feat/add-jj-backend"
        self.scope = "add-jj-backend"
        self.fixture.run(self.jj, "bookmark", "create", self.branch, "-r", "@-")

    def bookmark(self):
        return self.git(self.repo, "rev-parse", "refs/heads/" + self.branch).stdout.strip()

    def make_commit(self, index, subject):
        path = self.repo / ("interrupted-%02d.txt" % index)
        path.write_text("commit %d\n" % index, encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", subject)
        return self.git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def test_advance_own_scope_moves(self):
        old_bookmark = self.bookmark()
        candidate = self.make_commit(1, "feat(add-jj-backend): group 3 interrupted commit")
        self.assertNotEqual(candidate, old_bookmark)
        self.assertEqual(self.bookmark(), old_bookmark)

        result, _ = self.invoke("advance", "--scope", self.scope, "--branch", self.branch, repo=self.repo)

        self.assertTrue(result["ok"])
        self.assertEqual(self.bookmark(), candidate)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), candidate)
        count = self.git(self.repo, "rev-list", "--count", old_bookmark + ".." + self.bookmark())
        self.assertEqual(count.returncode, 0, count.stderr)
        self.assertEqual(count.stdout.strip(), "1")

    def test_advance_foreign_commit_stops(self):
        old_bookmark = self.bookmark()
        foreign = self.make_commit(1, "wip")
        before_parent = self.fixture.run(self.jj, "log", "--no-graph", "-r", "@-", "-T", "commit_id").stdout.strip()

        result, _ = self.invoke("advance", "--scope", self.scope, "--branch", self.branch,
                                repo=self.repo, expected=1)

        self.assertEqual(result["error"], "bookmark_behind")
        self.assertIn(foreign, result["message"])
        self.assertEqual(self.bookmark(), old_bookmark)
        self.assertEqual(self.fixture.run(self.jj, "log", "--no-graph", "-r", "@-", "-T", "commit_id").stdout.strip(),
                         before_parent)

    def test_advance_over_cap_stops(self):
        old_bookmark = self.bookmark()
        candidates = [self.make_commit(i, "feat(add-jj-backend): recovery commit %02d" % i)
                      for i in range(1, 52)]

        state, _ = self.invoke("state", "--scope", self.scope, repo=self.repo)
        self.assertEqual(len(state["behind"]), 50)
        self.assertTrue(state["behind_truncated"])
        result, _ = self.invoke("advance", "--scope", self.scope, "--branch", self.branch,
                                repo=self.repo, expected=1)

        self.assertEqual(result["error"], "bookmark_behind")
        self.assertEqual(self.bookmark(), old_bookmark)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), candidates[-1])
        capped_ids = [entry["commit"] for entry in state["behind"]]
        self.assertEqual(len(set(capped_ids)), 50)
        self.assertTrue(set(capped_ids).issubset(set(candidates)))
        self.assertTrue(all(commit in result["message"] for commit in capped_ids))
