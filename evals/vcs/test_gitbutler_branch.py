"""The GitButler gate creates the change branch beside the other applied branches, or stops when the name is taken."""
import json

from butenv import Scratch, require_but
from butwrap import ButWrap
from test_gitbutler_probe import GitButlerCase


class GitButlerWorkspaceCase(GitButlerCase):
    def managed(self, scratch):
        """A scratch GitButler repo with the Specwright settings kept out of the workspace's uncommitted changes."""
        repo = scratch.tracked_repo()
        self.settings(repo.path)
        exclude = repo.path / ".git" / "info" / "exclude"
        exclude.parent.mkdir(exist_ok=True)
        exclude.write_text("openspec/specwright.yaml\n", encoding="utf-8")
        return repo

    def commit_on(self, repo, branch, name):
        (repo.path / name).write_text(name + "\n", encoding="utf-8")
        repo.but("commit", "-b", branch, "-m", "work on " + name, "--json", name)

    def refs(self, repo):
        return self.git(repo.path, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/feat").stdout

    def applied(self, repo):
        stacks = json.loads(repo.but("status", "--json").stdout)["stacks"]
        return sorted(branch["name"] for stack in stacks for branch in stack["branches"])


class TestGitButlerBranchCreate(GitButlerWorkspaceCase):
    def test_branch_create_beside_applied(self):
        require_but()
        with Scratch() as scratch:
            repo = self.managed(scratch)
            repo.but("branch", "new", "feat/a")
            repo.but("branch", "new", "feat/b")
            self.commit_on(repo, "feat/a", "a.txt")
            self.commit_on(repo, "feat/b", "b-committed.txt")
            (repo.path / "src").mkdir()
            (repo.path / "src" / "b.py").write_text("print('b')\n", encoding="utf-8")
            tips = {name: self.git(repo.path, "rev-parse", "refs/heads/" + name).stdout.strip() for name in ("feat/a", "feat/b")}
            target = self.git(repo.path, "rev-parse", "refs/heads/main").stdout.strip()

            result, _ = self.invoke("branch-create", "--branch", "feat/add-c", repo=repo.path, env=self.isolated(scratch))

            self.assertTrue(result["ok"], result)
            self.assertEqual((result["backend"], result["branch"]), ("gitbutler", "feat/add-c"))
            self.assertEqual(self.applied(repo), ["feat/a", "feat/add-c", "feat/b"])
            self.assertEqual(self.git(repo.path, "rev-parse", "refs/heads/feat/add-c").stdout.strip(), target)
            for name, tip in tips.items():
                self.assertEqual(self.git(repo.path, "rev-parse", "refs/heads/" + name).stdout.strip(), tip, name)
            self.assertEqual((repo.path / "src" / "b.py").read_text(encoding="utf-8"), "print('b')\n")
            uncommitted = [c["filePath"] for c in json.loads(repo.but("status", "--json").stdout)["uncommittedChanges"]]
            self.assertEqual(uncommitted, ["src/b.py"])

            # the gate names the other branch's edit as not part of this change
            state, _ = self.invoke("state", "--branch", "feat/add-c", repo=repo.path, env=self.isolated(scratch))
            self.assertEqual(state["change_paths"], [])
            self.assertEqual(state["unassigned_paths"], ["src/b.py"])
            self.assertTrue(state["applied"])

    def test_branch_create_name_taken(self):
        require_but()
        with Scratch() as scratch:
            repo = self.managed(scratch)
            repo.but("branch", "new", "feat/a")
            repo.but("branch", "new", "feat/add-c")
            self.commit_on(repo, "feat/add-c", "c.txt")
            repo.but("unapply", "feat/add-c", "--json")  # exists, not applied
            before = (self.refs(repo), self.head(repo.path), self.snapshot(repo.path))
            wrap = ButWrap(scratch)

            result, _ = self.invoke("branch-create", "--branch", "feat/add-c", repo=repo.path, env=wrap.env(scratch), expected=1)

            self.assertEqual(result["error"], "branch_exists")
            self.assertIn("feat/add-c", result["message"])
            self.assertEqual(wrap.writes(), [], "a but write ran although the name is taken")
            self.assertEqual((self.refs(repo), self.head(repo.path), self.snapshot(repo.path)), before)
            self.assertEqual(self.applied(repo), ["feat/a"])
            # an applied branch of that name stops the same way
            result, _ = self.invoke("branch-create", "--branch", "feat/a", repo=repo.path, env=wrap.env(scratch), expected=1)
            self.assertEqual(result["error"], "branch_exists")
            self.assertEqual(wrap.writes(), [])
