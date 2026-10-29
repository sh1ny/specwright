"""Switching jj branches carries edits and rolls conflicts back without loss."""

from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase


class TestJjSwitch(VcsTestCase):
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

    def test_switch_carries_added_files(self):
        self.fixture.run(self.jj, "bookmark", "create", "feat/old", "-r", "@-")
        initial_old = self.git(self.repo, "rev-parse", "refs/heads/feat/old").stdout.strip()
        self.fixture.run(self.jj, "new", "main")
        (self.repo / "target-only.txt").write_text("target side\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "target-only change")
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", "@-")
        initial_main = self.git(self.repo, "rev-parse", "refs/heads/main").stdout.strip()
        self.fixture.run(self.jj, "new", "feat/old")
        old_parent = self.fixture.run(self.jj, "log", "--no-graph", "-r", "@-", "-T", "commit_id").stdout.strip()
        self.assertEqual(old_parent, initial_old)
        self.assertNotEqual(initial_main, initial_old)

        added = self.repo / "openspec" / "changes" / "add-x" / "proposal.md"
        added.parent.mkdir(parents=True)
        added.write_text("uncommitted proposal\n", encoding="utf-8")
        result, _ = self.invoke("switch", "--branch", "main", repo=self.repo)

        self.assertTrue(result["ok"])
        self.assertEqual(added.read_text(encoding="utf-8"), "uncommitted proposal\n")
        listed = self.fixture.run(self.jj, "file", "list", "-r", "@").stdout.replace("\\", "/")
        self.assertIn("openspec/changes/add-x/proposal.md", listed)
        self.assertEqual(self.git(self.repo, "rev-parse", "refs/heads/main").stdout.strip(), initial_main)
        self.assertEqual(self.git(self.repo, "rev-parse", "refs/heads/feat/old").stdout.strip(), initial_old)
        parent = self.fixture.run(self.jj, "log", "--no-graph", "-r", "@-", "-T", "commit_id").stdout.strip()
        self.assertEqual(parent, initial_main)

    def test_switch_carry_conflict_rolls_back(self):
        self.fixture.run(self.jj, "bookmark", "create", "feat/old", "-r", "@-")
        old_tip = self.git(self.repo, "rev-parse", "refs/heads/feat/old").stdout.strip()

        self.fixture.run(self.jj, "new", "main")
        target_file = self.repo / "README.md"
        target_file.write_text("target side\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "target change")
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", "@-")
        target_tip = self.git(self.repo, "rev-parse", "refs/heads/main").stdout.strip()

        self.fixture.run(self.jj, "new", "feat/old")
        target_file.write_text("local carried side\n", encoding="utf-8")
        result, _ = self.invoke("switch", "--branch", "main", repo=self.repo, expected=1)

        self.assertEqual(result["error"], "carry_conflict")
        self.assertIn("README.md", result["message"].replace("\\", "/"))
        self.assertEqual(target_file.read_text(encoding="utf-8"), "local carried side\n")
        self.assertEqual(self.git(self.repo, "rev-parse", "refs/heads/feat/old").stdout.strip(), old_tip)
        self.assertEqual(self.git(self.repo, "rev-parse", "refs/heads/main").stdout.strip(), target_tip)
        parent = self.fixture.run(self.jj, "log", "--no-graph", "-r", "@-", "-T", "commit_id").stdout.strip()
        self.assertEqual(parent, old_tip)
        listed = self.fixture.run(self.jj, "file", "list", "-r", "@").stdout.replace("\\", "/")
        self.assertIn("README.md", listed)
