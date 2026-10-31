"""A GitButler branch is deleted only once the workspace base holds the merge; a failed `but` write names autocrlf."""
from butenv import Scratch, find_but, require_but
from gbnet import LOGIN, GitButlerNetworkCase

HINT = "hint: core.autocrlf is true; GitButler checkouts can conflict on line endings"


class TestGitButlerDelete(GitButlerNetworkCase):
    def merged_workspace(self, scratch, branches):
        """`branches` applied with a commit each; the PR merged on origin as a commit that leaves their files alone;
        `but pull` run by the user, so the workspace base holds it and the branches are rebased on top of it."""
        wrap = self.prepare(scratch)
        repo = self.workspace(scratch, branches)
        merged = self.squash_stand_in(scratch)
        repo.but("pull", "--json")
        self.assertEqual(self.base(repo), merged)
        self.assertEqual(self.applied(repo), sorted(branches))
        for branch in branches:  # the rebased tip is not an ancestor of the base: only the merge commit is
            self.assertNotEqual(self.git(repo.path, "merge-base", "--is-ancestor", self.tip(repo, branch), merged).returncode, 0)
        return repo, wrap, merged

    def delete(self, scratch, wrap, *options, expected=0):
        return self.vcs(scratch, wrap, "delete-branch", "--branch", "feat/add-c", *options, expected=expected)

    def test_delete_after_squash_merge(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap, merged = self.merged_workspace(scratch, ["feat/b", "feat/add-c"])
            tip_b = self.tip(repo, "feat/b")
            refs = self.git(repo.path, "for-each-ref", "refs/remotes").stdout
            self.github_view()

            result = self.delete(scratch, wrap, "--force", "--merged-commit", merged, "--login", LOGIN)

            self.assertTrue(result["ok"], result)
            self.assertIs(result["deleted"], True)
            self.assertEqual(self.applied(repo), ["feat/b"], "only the merged branch is removed")
            self.assertEqual(self.tip(repo, "feat/b"), tip_b)
            self.assertEqual(self.git(repo.path, "rev-parse", "--verify", "-q", "refs/heads/feat/add-c").returncode, 1)
            self.assertEqual(wrap.writes(), [["branch", "delete", "feat/add-c", "--json"]])
            self.assertEqual([c for c in self.shim.calls() if c["write"]], [], "never a Git branch -D")
            self.assertEqual(self.git(repo.path, "for-each-ref", "refs/remotes").stdout, refs)

    def test_delete_left_applied_when_base_lacks_merge(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/b", "feat/add-c"])
            merged = self.squash_stand_in(scratch)
            self.git(repo.path, "fetch", "-q", "origin", "main")  # cleanup's fetch moved origin/main, `but` did not pull
            repo.but("unapply", "feat/b", "--json")  # the other branch left before the delete runs
            self.github_view()
            tip, base = self.tip(repo, "feat/add-c"), self.base(repo)
            self.assertNotEqual(base, merged)

            result = self.delete(scratch, wrap, "--force", "--merged-commit", merged, "--login", LOGIN)

            self.assertTrue(result["ok"], result)
            self.assertIs(result["deleted"], False)
            self.assertEqual(result["reason"], "left_applied")
            self.assertEqual(result["branch"], "feat/add-c")
            self.assertEqual(wrap.writes(), [], "no but write ran")
            self.assertEqual(self.applied(repo), ["feat/add-c"])
            self.assertEqual(self.tip(repo, "feat/add-c"), tip)
            self.assertEqual(self.base(repo), base)
            self.assertEqual((repo.path / "add-c.txt").read_text(encoding="utf-8"), "add-c.txt\n")

    def test_state_of_deleted_branch_has_no_pin_stop(self):
        # fix-m5-gaps D8 (#151): after the merge and the delete, state reports the branch gone with no settings_not_pinned
        # stop, and cleanup's settings are pinned against GitButler's target ref instead (context --after-merge)
        require_but()
        with Scratch() as scratch:
            repo, wrap, merged = self.merged_workspace(scratch, ["feat/add-c"])
            self.github_view()
            deleted = self.delete(scratch, wrap, "--force", "--merged-commit", merged, "--login", LOGIN)
            self.assertIs(deleted["deleted"], True, deleted)
            settings = repo.path / "openspec" / "specwright.yaml"
            settings.write_text(settings.read_text(encoding="utf-8") + "pr:\n  merge: agent\n  delete_branch: true\n",
                                encoding="utf-8")
            env = self.fenced_env(scratch, wrap)

            state = self.vcs(scratch, wrap, "state", "--branch", "feat/add-c")
            self.assertTrue(state["ok"], state)
            self.assertEqual((state["applied"], state["branch"]), (False, ""))
            after = ("context", "--code", repo.path, "--after-merge", "--branch", "feat/add-c")
            stopped = self.pr_pair(repo.path, *after, env=env, shim=self.shim.path, expected=1)
            self.assertEqual(stopped["error"], "settings_not_pinned", stopped)
            self.assertIn("but pull", stopped["message"])

            self.set_settings(repo.path, "vcs: gitbutler\nfinish: pr\n")
            passed = self.pr_pair(repo.path, *after, env=env, shim=self.shim.path)
            self.assertEqual((passed["ok"], passed["merge"], passed["delete_branch"]), (True, "user", True), passed)

    def test_delete_unmerged_left_applied(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/add-c"])
            self.github_view()
            tip, base = self.tip(repo, "feat/add-c"), self.base(repo)

            # the caller proved a merged PR but gave no merge commit, and the tip is not in the base
            result = self.delete(scratch, wrap, "--force", "--login", LOGIN)
            self.assertTrue(result["ok"], result)
            self.assertEqual((result["deleted"], result["reason"], result["branch"]), (False, "left_applied", "feat/add-c"))

            # no proof at all: the tip is not in the fetched main either
            result = self.delete(scratch, wrap, "--login", LOGIN, expected=1)
            self.assertEqual(result["error"], "not_merged")
            self.assertIn("feat/add-c", result["message"])

            self.assertEqual(wrap.writes(), [], "no but write ran")
            self.assertEqual(self.applied(repo), ["feat/add-c"])
            self.assertEqual((self.tip(repo, "feat/add-c"), self.base(repo)), (tip, base))

    def test_delete_gone_and_unapplied(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/a", "feat/add-c"])
            self.github_view()
            repo.but("unapply", "feat/a", "--json")  # exists, not applied: never deleted with Git
            result = self.vcs(scratch, wrap, "delete-branch", "--branch", "feat/a", "--force", "--login", LOGIN, expected=1)
            self.assertEqual(result["error"], "branch_not_applied")
            self.assertEqual(self.git(repo.path, "rev-parse", "--verify", "-q", "refs/heads/feat/a").returncode, 0)
            self.assertEqual(wrap.writes(), [])
            repo.but("branch", "delete", "feat/add-c", "--json")
            before = len(wrap.calls())
            result = self.delete(scratch, wrap, "--force", "--login", LOGIN)
            self.assertTrue(result["ok"], result)
            self.assertEqual((result["deleted"], result["reason"]), (False, "already_deleted"))
            self.assertEqual([c for c in wrap.calls()[before:] if c[:1] != ["status"] and c[:1] != ["--version"]], [])

    def test_but_error_names_autocrlf(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap, merged = self.merged_workspace(scratch, ["feat/add-c"])
            stub = self.root / "failing-but"
            stub.mkdir()
            with (stub / "but").open("w", encoding="utf-8", newline="\n") as handle:
                handle.write('#!/bin/sh\ncase "$1" in\n  --version|status) exec "%s" "$@" ;;\nesac\n'
                             'echo "Error: 1 conflict prevents checkout" >&2\nexit 1\n' % find_but().replace("\\", "/"))
            (stub / "but").chmod(0o755)
            tip = self.tip(repo, "feat/add-c")
            args = ("--force", "--merged-commit", merged, "--login", LOGIN)

            self.assertEqual(self.git(repo.path, "config", "core.autocrlf", "true").returncode, 0)
            result = self.vcs(scratch, wrap, "delete-branch", "--branch", "feat/add-c", *args, expected=1,
                              extra_path=(stub,))
            self.assertEqual(result["error"], "but_error")
            self.assertIn("1 conflict prevents checkout", result["message"])
            self.assertIn(HINT, result["message"])

            # with autocrlf off the same failure carries no hint
            self.assertEqual(self.git(repo.path, "config", "core.autocrlf", "false").returncode, 0)
            result = self.vcs(scratch, wrap, "delete-branch", "--branch", "feat/add-c", *args, expected=1,
                              extra_path=(stub,))
            self.assertEqual(result["error"], "but_error")
            self.assertIn("1 conflict prevents checkout", result["message"])
            self.assertNotIn("autocrlf", result["message"])
            self.assertEqual(self.tip(repo, "feat/add-c"), tip)
