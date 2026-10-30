"""On GitButler the change branch is resolved by name: state, switch and the commit's branch check never read HEAD."""
from butenv import Scratch, require_but
from butwrap import ButWrap
from test_gitbutler_branch import GitButlerWorkspaceCase


class TestGitButlerState(GitButlerWorkspaceCase):
    def workspace(self, scratch, assign=None):
        """feat/a, feat/b and feat/add-c applied, each with a commit; src/b.py edited and uncommitted."""
        repo = self.managed(scratch)
        for branch in ("feat/a", "feat/b", "feat/add-c"):
            repo.but("branch", "new", branch)
        self.commit_on(repo, "feat/a", "a.txt")
        self.commit_on(repo, "feat/b", "b-committed.txt")
        self.commit_on(repo, "feat/add-c", "c.txt")
        (repo.path / "src").mkdir()
        (repo.path / "src" / "b.py").write_text("print('b')\n", encoding="utf-8")
        return repo, ButWrap(scratch, assign)

    def tip(self, repo, branch):
        return self.git(repo.path, "rev-parse", "refs/heads/" + branch).stdout.strip()

    def state(self, scratch, repo, wrap, *options, expected=0):
        result, _ = self.invoke("state", *options, repo=repo.path, env=wrap.env(scratch), expected=expected)
        return result

    def test_state_reads_branch_not_head(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)
            self.assertEqual(self.head(repo.path), "refs/heads/gitbutler/workspace")
            state = self.state(scratch, repo, wrap, "--branch", "feat/add-c")
            self.assertEqual((state["backend"], state["branch"], state["applied"]), ("gitbutler", "feat/add-c", True))
            self.assertEqual(state["head"], self.tip(repo, "feat/add-c"))
            self.assertNotEqual(state["head"], self.git(repo.path, "rev-parse", "HEAD").stdout.strip())
            self.assertFalse(state["on_main"])
            self.assertEqual(state["target"], self.tip(repo, "main"))
            self.assertEqual(sorted(state["applied_branches"]), ["feat/a", "feat/add-c", "feat/b"])

    def test_clean_ignores_other_branch_paths(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch, {"feat/b": ["src/b.py"]})
            state = self.state(scratch, repo, wrap, "--branch", "feat/add-c")
            self.assertTrue(state["clean"], state)
            self.assertEqual(state["other_branch_paths"], [{"path": "src/b.py", "branch": "feat/b"}])
            self.assertEqual((state["change_paths"], state["unassigned_paths"]), ([], []))
            self.assertIn("src/b.py", state["dirty_paths"])  # the union stays for callers that read it
            self.assertEqual(state["branch"], "feat/add-c")
            # the same edit seen from feat/b is its own
            own = self.state(scratch, repo, wrap, "--branch", "feat/b")
            self.assertEqual((own["change_paths"], own["other_branch_paths"]), (["src/b.py"], []))
            self.assertFalse(own["clean"])

    def test_own_unassigned_edit_not_clean(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch, {"feat/b": ["src/b.py"]})
            (repo.path / "src" / "y.py").write_text("print('y')\n", encoding="utf-8")
            state = self.state(scratch, repo, wrap, "--branch", "feat/add-c")
            # D4: `clean` covers the change's own paths only; an unnamed edit is unassigned, and the
            # completion check asks about unassigned paths as Git callers ask about dirty paths
            self.assertTrue(state["clean"], state)
            self.assertEqual(state["unassigned_paths"], ["src/y.py"])
            self.assertEqual(state["other_branch_paths"], [{"path": "src/b.py", "branch": "feat/b"}])
            leftovers = state["change_paths"] + state["unassigned_paths"]  # what the completion check lists
            self.assertIn("src/y.py", leftovers)
            self.assertNotIn("src/b.py", leftovers)

    def test_change_paths_are_the_changes_own(self):
        """Unassigned paths under <P>/changes/<change-name>/ and paths the branch already touched are the change's."""
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)
            artifact = repo.path / "openspec" / "changes" / "add-c" / "tasks.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("- [ ] 1.1 x\n", encoding="utf-8")
            (repo.path / "c.txt").write_text("c again\n", encoding="utf-8")  # c.txt is in feat/add-c's commit
            (repo.path / "src" / "y.py").write_text("print('y')\n", encoding="utf-8")
            state = self.state(scratch, repo, wrap, "--branch", "feat/add-c", "--prefix", "openspec")
            self.assertEqual(sorted(state["change_paths"]), ["c.txt", "openspec/changes/add-c/tasks.md"])
            self.assertEqual(sorted(state["unassigned_paths"]), ["src/b.py", "src/y.py"])

    def test_unapplied_branch_is_reported_not_stopped(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)
            tip = self.tip(repo, "feat/add-c")
            repo.but("unapply", "feat/add-c", "--json")
            state = self.state(scratch, repo, wrap, "--branch", "feat/add-c")
            self.assertEqual((state["applied"], state["branch"], state["on_main"]), (False, "", True))
            self.assertEqual(state["head"], tip)
            state = self.state(scratch, repo, wrap)  # no --branch: the applied branches only, nothing applied implicitly
            self.assertEqual(sorted(state["applied_branches"]), ["feat/a", "feat/b"])
            self.assertEqual(state["branch"], "")
            self.assertEqual(wrap.writes(), [])

    def test_switch_to_main_is_noop(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)

            def observe():
                return (self.head(repo.path), self.refs(repo), self.git(repo.path, "status", "--porcelain").stdout,
                        (repo.path / "src" / "b.py").read_bytes())

            before = observe()
            for branch in ("main", "feat/add-c"):  # main, then an applied branch (resume)
                result, _ = self.invoke("switch", "--branch", branch, repo=repo.path, env=wrap.env(scratch))
                self.assertEqual((result["ok"], result["switched"], result["branch"]), (True, False, branch))
            self.assertEqual(observe(), before)
            self.assertEqual(wrap.writes(), [])

    def test_branch_not_applied_stops(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)
            repo.but("unapply", "feat/add-c", "--json")
            before = (self.head(repo.path), self.refs(repo), self.snapshot(repo.path), self.applied(repo))

            result, _ = self.invoke("switch", "--branch", "feat/add-c", repo=repo.path, env=wrap.env(scratch), expected=1)
            self.assertEqual(result["error"], "branch_not_applied")
            self.assertIn("feat/add-c", result["message"])

            message = scratch.root / "message.txt"
            message.write_text("feat(add-c): work\n", encoding="utf-8")
            result, _ = self.invoke("commit", "--branch", "feat/add-c", "--message-file", message, "--", "src/b.py",
                                    repo=repo.path, env=wrap.env(scratch), expected=1)
            self.assertEqual(result["error"], "branch_not_applied")
            self.assertEqual(wrap.writes(), [], "a but write ran for an unapplied branch")
            self.assertEqual((self.head(repo.path), self.refs(repo), self.snapshot(repo.path), self.applied(repo)), before)

    def test_status_output_over_the_cap_stops(self):
        require_but()
        with Scratch() as scratch:
            repo = self.managed(scratch)
            stub_env, _ = self.stub_but()
            stub = self.root / "stub-bin" / "but"
            stub.write_text("#!/bin/sh\nif [ \"$1\" = status ]; then head -c 17000000 /dev/zero | tr '\\0' ' '; exit 0; fi\n"
                            "echo 'but 0.23.1'\n", encoding="utf-8", newline="\n")
            result, _ = self.invoke("state", "--branch", "feat/add-c", repo=repo.path,
                                    env={**stub_env, **self.isolated(scratch)}, expected=1)
            self.assertEqual(result["error"], "but_output_too_large")
