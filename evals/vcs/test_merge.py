"""A jj local merge keeps the first-parent merge proof and moves nothing it should not."""

from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase


class TestJjMerge(VcsTestCase):
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
        self.message = self.root / "merge-message.txt"
        with self.message.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write("merge: add-x\n\nSpecwright-Change: add-x\n")

    def build(self, branch_file="feature.txt", main_file="main-only.txt"):
        """A branch commit and a main commit side by side, with @ left empty on main."""
        self.fixture.run(self.jj, "new", "main")
        (self.repo / branch_file).write_text("branch side\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "feat(add-x): work")
        self.fixture.run(self.jj, "bookmark", "create", self.branch, "-r", "@-")
        self.fixture.run(self.jj, "new", "main")
        (self.repo / main_file).write_text("main side\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "chore: main side")
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", "@-")
        self.fixture.run(self.jj, "new", "main")

    def ref(self, name):
        return self.git(self.repo, "rev-parse", "refs/heads/" + name).stdout.strip()

    def log(self, revset, template="commit_id"):
        return self.fixture.run(self.jj, "log", "--no-graph", "-r", revset, "-T", template).stdout.strip()

    def merge(self, expected=0):
        return self.invoke("merge", "--branch", self.branch, "--message-file", self.message,
                           repo=self.repo, expected=expected)

    def test_merge_first_parent_and_carry(self):
        self.build()
        old_main, branch_tip = self.ref("main"), self.ref(self.branch)
        (self.repo / "scratch.log").write_text("leftover\n", encoding="utf-8")

        result, _ = self.merge()

        self.assertTrue(result["ok"], result)
        subjects = self.git(self.repo, "log", "--first-parent", "--format=%s", "main").stdout.splitlines()
        self.assertEqual(subjects[0], "merge: add-x")
        head = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.ref("main"), head)
        self.assertEqual(result["commit"], head)
        parents = self.git(self.repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
        self.assertEqual(parents[1:], [old_main, branch_tip])
        self.assertEqual(self.ref(self.branch), branch_tip)
        self.assertEqual((self.repo / "scratch.log").read_text(encoding="utf-8"), "leftover\n")
        listed = self.fixture.run(self.jj, "file", "list", "-r", "@").stdout.replace("\\", "/")
        self.assertIn("scratch.log", listed)
        self.assertEqual(self.log("@-"), head)
        message = self.git(self.repo, "cat-file", "commit", head).stdout
        self.assertIn("Specwright-Change: add-x", message)

    def test_merge_conflict_abandons(self):
        self.build(branch_file="README.md", main_file="README.md")
        old_main, branch_tip = self.ref("main"), self.ref(self.branch)
        old_parent, old_change = self.log("@-"), self.log("@", "change_id")
        (self.repo / "scratch.log").write_text("leftover\n", encoding="utf-8")

        result, _ = self.merge(expected=1)

        self.assertEqual(result["error"], "conflicted")
        self.assertIn("README.md", result["message"].replace("\\", "/"))
        self.assertEqual(self.ref("main"), old_main)
        self.assertEqual(self.ref(self.branch), branch_tip)
        self.assertEqual(self.log("@-"), old_parent)
        self.assertEqual(self.log("@", "change_id"), old_change)
        self.assertEqual((self.repo / "scratch.log").read_text(encoding="utf-8"), "leftover\n")
        self.assertEqual(self.log('description(glob:"merge: add-x*")'), "")

    def test_merge_rerun_reuses_commit(self):
        self.build()
        old_main, branch_tip = self.ref("main"), self.ref(self.branch)
        self.fixture.run(self.jj, "new", "--no-edit", "-m", "merge: add-x\n\nSpecwright-Change: add-x\n",
                         "main", self.branch)
        existing = self.log('description(glob:"merge: add-x*")')
        self.assertEqual(len(existing.split()), 1)
        self.assertEqual(self.ref("main"), old_main)

        result, _ = self.merge()

        self.assertEqual(result["commit"], existing)
        self.assertEqual(self.ref("main"), existing)
        self.assertEqual(self.log('description(glob:"merge: add-x*")'), existing)
        parents = self.git(self.repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
        self.assertEqual(parents[1:], [old_main, branch_tip])
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), existing)

    def test_merge_rerun_after_carry_sets_main(self):
        self.build()
        self.fixture.run(self.jj, "new", "--no-edit", "-m", "merge: add-x\n\nSpecwright-Change: add-x\n",
                         "main", self.branch)
        existing = self.log('description(glob:"merge: add-x*")')
        self.fixture.run(self.jj, "new", existing)
        self.assertNotEqual(self.ref("main"), existing)

        result, _ = self.merge()

        self.assertEqual(result["commit"], existing)
        self.assertEqual(self.ref("main"), existing)
        self.assertEqual(self.log('description(glob:"merge: add-x*")'), existing)

        again, _ = self.merge()
        self.assertTrue(again["already_merged"])
        self.assertEqual(self.ref("main"), existing)
