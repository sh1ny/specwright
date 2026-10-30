"""The GitButler pull runs `but pull` fenced only when nothing else is applied and no linked worktree exists."""
import os
import re
from pathlib import Path

from butenv import Scratch, require_but
from gbnet import LOGIN, GitButlerNetworkCase

FINISH = Path(__file__).resolve().parents[2] / "skills" / "specwright-finish" / "SKILL.md"


class TestGitButlerPull(GitButlerNetworkCase):
    def norm(self, path):
        return os.path.normcase(os.path.realpath(path))

    def test_pull_alone_runs_fenced(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/add-c"])
            self.git(repo.path, "push", "-q", "origin", "refs/heads/feat/add-c:refs/heads/feat/add-c")
            merged = self.merge_on_origin(scratch, "feat/add-c")
            self.github_view()
            self.assertNotEqual(self.base(repo), merged)

            result = self.vcs(scratch, wrap, "pull", "--branch", "feat/add-c", "--login", LOGIN)

            self.assertTrue(result["ok"], result)
            self.assertTrue(result["pulled"], result)
            self.assertEqual(wrap.writes(), [["pull", "--json"]])
            self.assertEqual(set(self.gh_tokens(scratch)), {"tok-code"}, "but pull ran through as.sh")
            self.assertEqual(self.base(repo), merged, "the local target moved to the remote's main")
            self.assertEqual(self.applied(repo), [], "the merged branch is no longer applied")

    def test_pull_skipped_other_branch(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/b", "feat/add-c"])
            self.git(repo.path, "push", "-q", "origin", "refs/heads/feat/add-c:refs/heads/feat/add-c")
            self.merge_on_origin(scratch, "feat/add-c")
            self.github_view()
            tips = {name: self.tip(repo, name) for name in ("feat/b", "feat/add-c")}
            base = self.base(repo)

            result = self.vcs(scratch, wrap, "pull", "--branch", "feat/add-c", "--login", LOGIN)

            self.assertTrue(result["ok"], result)
            self.assertIs(result["pulled"], False)
            self.assertEqual(result["reason"], "pull_skipped")
            self.assertEqual(result["applied_branches"], ["feat/b"])
            self.assertEqual(result["worktrees"], [])
            self.assertEqual(wrap.writes(), [], "no but write ran")
            self.assertEqual([c for c in self.shim.calls() if c["action"] in ("fetch", "pull", "push")], [])
            self.assertEqual({name: self.tip(repo, name) for name in tips}, tips)
            self.assertEqual(self.base(repo), base)
            self.assertEqual(self.gh_tokens(scratch), [])

    def test_pull_skipped_linked_worktree(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/add-c"])
            self.git(repo.path, "push", "-q", "origin", "refs/heads/feat/add-c:refs/heads/feat/add-c")
            self.merge_on_origin(scratch, "feat/add-c")
            linked = scratch.root / "linked"
            repo.git_run("worktree", "add", "--detach", linked)
            self.github_view()
            tip, base = self.tip(repo, "feat/add-c"), self.base(repo)

            result = self.vcs(scratch, wrap, "pull", "--branch", "feat/add-c", "--login", LOGIN)

            self.assertTrue(result["ok"], result)
            self.assertIs(result["pulled"], False)
            self.assertEqual(result["reason"], "pull_skipped")
            self.assertEqual(result["applied_branches"], [])
            self.assertEqual([self.norm(path) for path in result["worktrees"]], [self.norm(linked)])
            self.assertEqual(wrap.writes(), [], "no but write ran")
            self.assertEqual(self.tip(repo, "feat/add-c"), tip)
            self.assertEqual(self.base(repo), base)
            self.assertEqual(self.applied(repo), ["feat/add-c"])

    def test_finish_reads_fetched_main(self):
        """The merge landed on origin, the pull was skipped (feat/b applied): local main lacks the archive, the fetched
        commit holds it, and finish's A and M reads on GitButler name that commit."""
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/b", "feat/add-c"])
            archived = "openspec/changes/archive/2026-10-30-add-c"
            (repo.path / archived).mkdir(parents=True)
            (repo.path / archived / "review.md").write_text("VERDICT: APPROVE" + chr(10), encoding="utf-8")
            repo.but("commit", "-b", "feat/add-c", "-m", "docs(add-c): archive change", "--json", archived + "/")
            self.git(repo.path, "push", "-q", "origin", "refs/heads/feat/add-c:refs/heads/feat/add-c")
            merged = self.merge_on_origin(scratch, "feat/add-c")
            self.github_view()

            pulled = self.vcs(scratch, wrap, "pull", "--branch", "feat/add-c", "--login", LOGIN)
            self.assertIs(pulled["pulled"], False, pulled)
            fetched = self.vcs(scratch, wrap, "fetch-main", "--login", LOGIN)

            self.assertEqual(fetched["commit"], merged)
            listing = ("ls-tree", "-d", "--name-only")
            self.assertEqual(self.git(repo.path, *listing, "refs/heads/main", "--", "openspec/changes/archive/").stdout.strip(), "",
                             "local main is stale after the skipped pull")
            self.assertEqual(self.git(repo.path, *listing, fetched["commit"], "--", "openspec/changes/archive/").stdout.strip(),
                             archived, "the archive is on the fetched main")
            tip = self.tip(repo, "feat/add-c")
            self.assertEqual(self.git(repo.path, "merge-base", "--is-ancestor", tip, fetched["commit"]).returncode, 0,
                             "M holds on the fetched main")
            self.assertNotEqual(self.git(repo.path, "merge-base", "--is-ancestor", tip, "refs/heads/main").returncode, 0)
            # finish's text reads A and M there on GitButler, and does not report the repo as not done
            text = FINISH.read_text(encoding="utf-8")
            self.assertRegex(text, r"On GitButler, read A and M [^\n]{0,160}`fetch-main`[^\n]{0,160}never (the )?local `<main>`",
                             "finish does not read A and M on the fetched main under GitButler")
