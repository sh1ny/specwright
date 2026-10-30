"""Whole flows on jj make no Git write: the Git-write log holds every `git` call Specwright makes.

jj itself runs the real Git named in its repo config, so the logging shim on PATH sees only the calls Specwright
makes (vcs.sh and as.sh), never jj's own.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import gitlog
import jjenv
from jjenv import Scratch, require_jj
from vcs_test_support import ROOT, VcsTestCase, bash_path_env, bash_run

sys.path.insert(0, str(ROOT / "evals" / "git-workflow"))
import fixtures  # noqa: E402

BRANCH = "feat/add-x"
READ_FETCH = "FETCH_HEAD-only read fetch"
GITHUB = "https://github.com/o/r.git"
# spec: "No other Git write runs under jj"
FORBIDDEN = {"checkout", "switch", "add", "rm", "restore", "read-tree", "commit", "merge", "stash", "reset",
             "rebase", "pull", "push", "update-ref", "tag", "clean", "cherry-pick"}


class FlowCase(VcsTestCase):
    def setUp(self):
        super().setUp()
        self.jj = require_jj()
        self.scratch = Scratch()
        self.addCleanup(self.scratch.close)
        self.shim = gitlog.install(self.root / "shim", real_git=jjenv.real_git(),
                                   log_path=self.root / "git-calls.jsonl")
        self.env = {**self.shim.env, **bash_path_env(self.shim.path)}
        self.extra_env = {}

    def start(self, fixture):
        """A repo with `vcs: jj`, the settings committed, and main at the settings commit."""
        self.fixture, self.repo = fixture, fixture.path
        self.set_settings(self.repo, "vcs: jj\nmain_branch: main\nfinish: local\n")
        fixture.run(self.jj, "commit", "-m", "fixture Specwright settings")
        fixture.run(self.jj, "bookmark", "set", "main", "-r", "@-")

    def vcs(self, command, *options, expected=0, **kwargs):
        result, _ = self.invoke(command, *options, repo=self.repo, expected=expected, env=self.extra_env, **kwargs)
        if expected == 0:
            self.assertTrue(result["ok"], result)
        return result

    def message(self, text):
        path = self.root / "message.txt"
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        return path

    def commit_paths(self, text, *paths):
        return self.vcs("commit", "--branch", BRANCH, "--message-file", self.message(text), "--", *paths)

    def write(self, name, text="work\n"):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def ref(self, name, repo=None):
        done = self.git(repo or self.repo, "rev-parse", "--verify", "--quiet", name)
        return done.stdout.strip() if done.returncode == 0 else None

    def apply_and_archive(self):
        """Two task groups, each one commit with a Specwright-Task trailer, then the archive commit."""
        self.write("openspec/changes/add-x/proposal.md", "proposal\n")
        self.write("src/one.txt", "group one\n")
        self.commit_paths("feat(add-x): group 1 first\n\nSpecwright-Task: 1.1\n", "src/one.txt", "openspec/changes/add-x")
        self.write("src/two.txt", "group two\n")
        self.commit_paths("feat(add-x): group 2 second\n\nSpecwright-Task: 2.1\n", "src/two.txt")
        archived = "openspec/changes/archive/2026-10-30-add-x"
        (self.repo / archived).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.repo / "openspec/changes/add-x"), str(self.repo / archived))
        self.commit_paths("chore(add-x): archive add-x\n\nSpecwright-Change: add-x\n", "openspec/changes/add-x", archived)
        subjects = self.git(self.repo, "log", "--format=%s", "-3", "refs/heads/" + BRANCH).stdout.splitlines()
        self.assertEqual(subjects, ["chore(add-x): archive add-x", "feat(add-x): group 2 second",
                                    "feat(add-x): group 1 first"])
        body = self.git(self.repo, "log", "--format=%B", "-3", "refs/heads/" + BRANCH).stdout
        self.assertIn("Specwright-Task: 1.1", body)
        self.assertIn("Specwright-Task: 2.1", body)
        listed = self.git(self.repo, "ls-tree", "-r", "--name-only", "refs/heads/" + BRANCH).stdout.replace("\\", "/")
        self.assertIn(archived + "/proposal.md", listed)
        self.assertNotIn("openspec/changes/add-x/", listed)

    def assert_no_git_writes(self, expect_reads=True):
        """Every logged call is a read (a FETCH_HEAD-only fetch counts as one), and none is a forbidden verb."""
        calls = self.shim.calls()
        if expect_reads:
            self.assertTrue(calls, "the git shim logged nothing: the test does not see Specwright's calls")
        self.shim.assert_no_writes(allowed=(READ_FETCH,))
        for call in calls:
            argv = call["argv"]
            action = call["action"]
            self.assertNotIn(action, FORBIDDEN, argv)
            if action == "branch":
                self.assertFalse({"-d", "-D", "--delete", "-m", "-M", "-c", "-C", "-f"} & set(argv), argv)
            if action == "fetch":
                self.assertIn("--refmap=", argv, "a fetch without an empty refmap writes remote-tracking refs")
                self.assertFalse(call["write"], argv)
                self.assertEqual(call["exception"], READ_FETCH)
        return calls


class TestLocalFlow(FlowCase):
    def local_flow(self, build):
        self.start(build())
        main_before = self.ref("refs/heads/main")

        # branch gate
        state = self.vcs("state")
        self.assertTrue(state["on_main"] and state["clean"], state)
        self.vcs("fetch-main", "--quiet")
        self.vcs("branch-create", "--branch", BRANCH)
        # apply (two groups) and archive
        self.apply_and_archive()
        tip = self.ref("refs/heads/" + BRANCH)
        # local finish: back to main, merge, delete the branch
        self.vcs("switch", "--branch", "main")
        merged = self.vcs("merge", "--branch", BRANCH,
                          "--message-file", self.message("merge: add-x\n\nSpecwright-Change: add-x\n"))
        self.vcs("delete-branch", "--branch", BRANCH)

        self.assertEqual(self.ref("refs/heads/main"), merged["commit"])
        parents = self.git(self.repo, "rev-list", "--parents", "-n", "1", "main").stdout.split()
        self.assertEqual(parents[1:], [main_before, tip])
        self.assertIsNone(self.ref("refs/heads/" + BRANCH))
        self.assertEqual(self.git(self.repo, "log", "--first-parent", "--format=%s", "-1", "main").stdout.strip(),
                         "merge: add-x")
        final = self.vcs("state")
        self.assertTrue(final["on_main"] and final["clean"], final)
        return self.assert_no_git_writes()

    def test_local_flow_no_git_writes(self):
        for name, build in (("tracked main", self.scratch.tracked_repo),
                            ("untracked main", self.scratch.untracked_repo)):
            with self.subTest(name):
                self.shim.log_path.unlink(missing_ok=True)
                calls = self.local_flow(lambda: build(name.split()[0]))
                self.assertTrue(any(call["action"] == "fetch" for call in calls), "the read fetch is in the log")


class TestPrFlow(FlowCase):
    login = "code-bot"

    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="swf-"))
        self.addCleanup(fixtures.rmtree, self.tmp)
        (self.tmp / "bin").mkdir()
        fixtures.install_fake_gh(self.tmp)
        (self.tmp / "gh-state.json").write_text(json.dumps(
            {"user": "sh1ny", "tokens": {"sh1ny": "tok-sh1ny", self.login: "tok-code"}}), encoding="utf-8")
        gh_bin = self.tmp / "bin"
        self.extra_env = {**bash_path_env(self.shim.path, extra_path=[gh_bin]),
                          "FAKE_GH_STATE": str(self.tmp / "gh-state.json"),
                          "FAKE_GH_LOG": str(self.tmp / "gh-log.jsonl")}

    def origin_ref(self, name):
        return self.ref(name, self.scratch.origin)

    def github_view(self):
        """origin is github.com to Specwright (so it fences through as.sh) and the local bare repo to Git and jj.

        `url.<bare>.insteadOf` rewrites every fetch and push; the logging shim answers `git remote get-url origin`
        (which would expand the rewrite) with the github.com URL, as the release evals' shim does."""
        git = jjenv.real_git()
        self.fixture.run(git, "remote", "set-url", "origin", GITHUB)
        self.fixture.run(git, "config", "url.%s.insteadOf" % self.scratch.origin.as_posix(), GITHUB)
        script = self.shim.path / "git"
        text = script.read_text(encoding="utf-8").replace("\r\n", "\n")
        answer = 'if [ "$*" = "remote get-url origin" ]; then echo "%s"; exit 0; fi\n' % GITHUB
        text = text.replace('exec "$SPECWRIGHT_REAL_GIT" "$@"', answer + 'exec "$SPECWRIGHT_REAL_GIT" "$@"')
        with script.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        self.assertEqual(self.vcs_remote_url(), GITHUB)

    def vcs_remote_url(self):
        done = bash_run(["-c", "git remote get-url origin"], cwd=self.repo, env=self.shim.env, shim=self.shim.path)
        return done.stdout.strip()

    def gh_api_tokens(self):
        path = self.tmp / "gh-log.jsonl"
        calls = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
        return [call["env"]["GH_TOKEN"] for call in calls if call["argv"][0] == "api"]

    def merge_on_github(self):
        """The merge button with delete-branch: a merge commit on origin's main, then the head branch deleted."""
        side = self.root / "github-side"
        self.assertEqual(self.git(self.root, "clone", "-q", str(self.scratch.origin), "github-side").returncode, 0)
        done = self.git(side, "merge", "--no-ff", "-m", "Merge pull request #1 from o/" + BRANCH,
                        "origin/" + BRANCH)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.git(side, "push", "-q", "origin", "HEAD:refs/heads/main").returncode, 0)
        self.assertEqual(self.git(self.scratch.origin, "update-ref", "-d", "refs/heads/" + BRANCH).returncode, 0)
        return self.git(side, "rev-parse", "HEAD").stdout.strip()

    def test_pr_flow_no_git_writes(self):
        self.start(self.scratch.tracked_repo())
        self.fixture.run(self.jj, "git", "push", "--bookmark", "main")  # fixture: origin holds the settings commit
        base = self.origin_ref("refs/heads/main")
        self.assertEqual(self.ref("refs/remotes/origin/main"), base)
        self.github_view()
        login = ("--login", self.login)

        # branch gate, apply, archive
        state = self.vcs("state")
        self.assertTrue(state["on_main"] and state["clean"], state)
        self.vcs("fetch-main", "--quiet", *login)
        self.vcs("branch-create", "--branch", BRANCH)
        self.apply_and_archive()
        tip = self.ref("refs/heads/" + BRANCH)

        # ship: push through as.sh, as the pinned login
        self.vcs("push", "--branch", BRANCH, *login)
        self.assertEqual(self.origin_ref("refs/heads/" + BRANCH), tip)
        self.assertEqual(self.origin_ref("refs/heads/main"), base)
        self.assertTrue(self.gh_api_tokens(), "the push went through as.sh")
        self.assertEqual(set(self.gh_api_tokens()), {"tok-code"})

        # the PR is merged on GitHub and its head branch deleted
        merged = self.merge_on_github()
        self.assertIsNone(self.origin_ref("refs/heads/" + BRANCH))
        self.assertEqual(self.ref("refs/remotes/origin/main"), base, "nothing fetched yet")

        # cleanup: refresh, back to main, pull, delete the local branch
        fetched = self.vcs("fetch-main", "--quiet", *login)
        self.assertEqual(fetched["ref"], merged)
        self.assertEqual(self.ref("refs/remotes/origin/main"), base, "the read fetch moves no remote-tracking ref")
        self.assertEqual(self.ref("refs/heads/main"), base)
        self.vcs("switch", "--branch", "main")
        pulled = self.vcs("pull", *login)
        self.assertEqual(pulled["commit"], merged)
        self.assertEqual(self.ref("refs/heads/main"), merged)
        self.assertEqual(self.ref("refs/remotes/origin/main"), merged, "jj's fetch moved it")
        self.assertEqual(self.ref("refs/heads/" + BRANCH), tip, "the change bookmark survives the pull")
        self.vcs("delete-branch", "--branch", BRANCH)
        self.assertIsNone(self.ref("refs/heads/" + BRANCH))
        self.assertEqual(self.ref("HEAD"), merged)
        final = self.vcs("state")
        self.assertTrue(final["on_main"] and final["clean"], final)

        calls = self.assert_no_git_writes()
        self.assertFalse([call for call in calls if call["action"] in ("push", "pull")],
                         "every push and pull ran through jj git")
        self.assertEqual(set(self.gh_api_tokens()), {"tok-code"})
