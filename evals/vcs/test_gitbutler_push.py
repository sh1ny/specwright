"""A GitButler push publishes only the change branch, through the fence, without force."""
from butenv import Scratch, require_but
from gbnet import LOGIN, GitButlerNetworkCase

FORCE_FLAGS = {"-f", "--force", "--force-with-lease", "--mirror", "--all", "-u", "--set-upstream", "--delete"}


class TestGitButlerPush(GitButlerNetworkCase):
    def pushes(self):
        return [call for call in self.shim.calls() if call["action"] == "push"]

    def test_push_only_change_branch(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/a", "feat/b", "feat/add-c"])
            (repo.path / "notes.txt").write_text("uncommitted\n", encoding="utf-8")
            self.github_view()
            initial = self.origin_refs(scratch)
            tips = {name: self.tip(repo, name) for name in ("feat/a", "feat/b", "feat/add-c")}
            config = (repo.path / ".git" / "config").read_bytes()
            head = self.head(repo.path)

            result = self.vcs(scratch, wrap, "push", "--branch", "feat/add-c", "--login", LOGIN)

            self.assertTrue(result["ok"], result)
            self.assertEqual((result["backend"], result["branch"]), ("gitbutler", "feat/add-c"))
            refs = self.origin_refs(scratch)
            self.assertEqual(set(refs) - set(initial), {"refs/heads/feat/add-c"})
            self.assertEqual(refs["refs/heads/feat/add-c"], tips["feat/add-c"])
            self.assertEqual(refs["refs/heads/main"], initial["refs/heads/main"])
            self.assertEqual(set(self.gh_tokens(scratch)), {"tok-code"}, "the push went through as.sh")
            # one fenced Git push of the branch's own ref, never `but push` or `but pr`
            self.assertEqual([call["argv"] for call in self.pushes()],
                             [["push", "--no-follow-tags", "origin", "refs/heads/feat/add-c:refs/heads/feat/add-c"]])
            self.assertEqual(wrap.writes(), [], "a but write ran")
            self.assertEqual([call for call in self.shim.calls() if call["write"] and call["action"] != "push"], [])
            # HEAD, config and the local branches are untouched
            self.assertEqual(self.head(repo.path), head)
            self.assertEqual((repo.path / ".git" / "config").read_bytes(), config)
            for name, tip in tips.items():
                self.assertEqual(self.tip(repo, name), tip, name)
            self.assertEqual((repo.path / "notes.txt").read_text(encoding="utf-8"), "uncommitted\n")

    def test_push_sends_no_tags(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/b", "feat/add-c"])
            self.github_view()
            # the user's push.followTags would publish an annotated tag that points into the pushed branch
            self.assertEqual(self.git(repo.path, "config", "push.followTags", "true").returncode, 0)
            tag = self.git(repo.path, "tag", "-a", "v9.9.9", "-m", "local only", "refs/heads/feat/add-c")
            self.assertEqual(tag.returncode, 0, tag.stderr)

            result = self.vcs(scratch, wrap, "push", "--branch", "feat/add-c", "--login", LOGIN)

            self.assertTrue(result["ok"], result)
            self.assertEqual(self.origin_refs(scratch)["refs/heads/feat/add-c"], self.tip(repo, "feat/add-c"))
            tags = self.git(scratch.origin, "tag", "--list").stdout.split()
            self.assertEqual(tags, [], "the push published a tag")

    def test_sibling_settings_change_stops(self):
        # every step reads openspec/specwright.yaml from the shared work tree: feat/b's own copy would set validate and preship
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/b", "feat/add-c"])
            self.github_view()
            (repo.path / ".git" / "info" / "exclude").write_text("", encoding="utf-8")  # the fixture hides the settings
            settings = repo.path / "openspec" / "specwright.yaml"
            settings.write_text(settings.read_text(encoding="utf-8") + "pr:\n  validate: \"echo pwned\"\n", encoding="utf-8")
            repo.but("commit", "-b", "feat/b", "-m", "settings", "--json", "openspec/specwright.yaml")
            initial = self.origin_refs(scratch)

            state = self.vcs(scratch, wrap, "state", "--branch", "feat/add-c", expected=1)
            push = self.vcs(scratch, wrap, "push", "--branch", "feat/add-c", "--login", LOGIN, expected=1)

            self.assertEqual(state["error"], "settings_not_pinned", state)
            self.assertEqual(push["error"], "settings_not_pinned", push)
            self.assertEqual(self.origin_refs(scratch), initial)
            self.assertEqual(self.pushes(), [])
            # feat/b itself is not stopped: the settings are its own
            self.assertTrue(self.vcs(scratch, wrap, "state", "--branch", "feat/b")["ok"])

    def test_push_unapplied_stops(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/a", "feat/add-c"])
            repo.but("unapply", "feat/a", "--json")
            self.github_view()
            initial = self.origin_refs(scratch)

            result = self.vcs(scratch, wrap, "push", "--branch", "feat/a", "--login", LOGIN, expected=1)

            self.assertEqual(result["error"], "branch_not_applied")
            self.assertEqual(self.origin_refs(scratch), initial)
            self.assertEqual(self.pushes(), [])

    def test_push_rejected_never_forced(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            self.workspace(scratch, ["feat/b", "feat/add-c"])
            self.github_view()
            # the branch was rebased outside Specwright after its last push: origin's copy has another history
            main = self.git(scratch.origin, "rev-parse", "refs/heads/main").stdout.strip()
            tree = self.git(scratch.origin, "rev-parse", "refs/heads/main^{tree}").stdout.strip()
            other = self.git(scratch.origin, "commit-tree", tree, "-p", main, "-m", "published elsewhere").stdout.strip()
            self.assertEqual(self.git(scratch.origin, "update-ref", "refs/heads/feat/add-c", other).returncode, 0)
            initial = self.origin_refs(scratch)

            result = self.vcs(scratch, wrap, "push", "--branch", "feat/add-c", "--login", LOGIN, expected=1)

            self.assertEqual(result["error"], "push_rejected", result)
            self.assertIn("feat/add-c", result["message"])
            self.assertEqual(self.origin_refs(scratch), initial)
            self.assertEqual(self.origin_refs(scratch)["refs/heads/feat/add-c"], other)
            pushes = self.pushes()
            self.assertEqual(len(pushes), 1, "no retry")
            argv = pushes[0]["argv"]
            self.assertFalse(FORCE_FLAGS & set(argv), argv)
            self.assertFalse([arg for arg in argv if arg.startswith(("+", "--force"))], argv)
            self.assertEqual(wrap.writes(), [])

    def test_merge_and_advance_stop(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, ["feat/add-c"])
            message = self.root / "message.txt"
            message.write_text("merge\n", encoding="utf-8")
            before = (self.tip(repo, "feat/add-c"), self.head(repo.path), self.refs(repo))

            for command, options in (("merge", ("--branch", "feat/add-c", "--message-file", message)),
                                     ("advance", ("--scope", "x"))):
                result = self.vcs(scratch, wrap, command, *options, expected=1)
                self.assertEqual(result["error"], "unsupported_combination", command)

            self.assertEqual(wrap.writes(), [])
            self.assertEqual([call for call in self.shim.calls() if call["write"]], [])
            self.assertEqual((self.tip(repo, "feat/add-c"), self.head(repo.path), self.refs(repo)), before)
