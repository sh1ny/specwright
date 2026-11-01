"""The GitButler gate creates the change branch beside the other applied branches, or stops when the name is taken."""
import json
import tempfile
from pathlib import Path

from butenv import Scratch, require_but
from butwrap import ButWrap
from test_gitbutler_probe import GitButlerCase
from vcs_test_support import ROOT, bash_run

PR_PAIR = ROOT / "skills" / "specwright-pr" / "scripts" / "pr-pair.sh"


DEFAULT_SETTINGS = "vcs: gitbutler\nfinish: pr\n"


class GitButlerWorkspaceCase(GitButlerCase):
    def managed(self, scratch, settings=DEFAULT_SETTINGS):
        """A scratch GitButler repo whose `openspec/specwright.yaml` is committed on main (fix-m5-gaps D8): the file in the work
        tree then equals the one every change branch starts from, so the settings pin passes until a test edits it. The commit goes
        to origin's main through a side clone and `but pull` brings it into the workspace base before any branch exists."""
        repo = scratch.tracked_repo()
        # a fresh empty dir per call: a test can make several workspaces in one case, so a fixed name collides on the second
        side = Path(tempfile.mkdtemp(prefix="settings-side-", dir=self.root))
        for args in (("clone", "-q", str(scratch.origin), str(side)), ("-C", str(side), "config", "user.name", "Settings"),
                     ("-C", str(side), "config", "user.email", "settings@example.invalid"),
                     ("-C", str(side), "config", "core.autocrlf", "false")):
            done = self.git(self.root, *args, env=scratch.env)
            self.assertEqual(done.returncode, 0, done.stderr)
        self.set_settings(side, settings)
        for args in (("add", "openspec/specwright.yaml"), ("commit", "-q", "-m", "chore: settings"),
                     ("push", "-q", "origin", "HEAD:refs/heads/main")):
            done = self.git(side, *args, env=scratch.env)
            self.assertEqual(done.returncode, 0, done.stderr)
        repo.but("pull", "--json")
        self.set_settings(repo.path, settings)  # the same bytes: nothing to commit, whether or not the pull wrote the file
        return repo

    def pr_pair(self, repo_path, *args, env=None, shim=None, expected=0):
        """`pr-pair.sh <args>` run in the repo with the fixture environment; returns its one JSON line."""
        result = bash_run([PR_PAIR.as_posix(), *map(str, args)], cwd=repo_path, env=env, shim=shim)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

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
