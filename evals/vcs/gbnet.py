"""Shared fixtures for the GitButler network and delete tests: a fenced GitHub view of the local origin, a Git-call log,
a logging `but`, and helpers that act as the remote (merges, squash stand-ins).

The scratch origin is a local bare repository. Specwright fences a command only for a github.com origin, so
`github_view()` makes the logging `git` shim answer `git remote get-url origin` with a github.com URL (the way
test_flows.py does for jj); every real fetch and push still goes to the local bare repository.
"""
import json
import subprocess

import gitlog
from butenv import real_git
from butwrap import ButWrap
from test_gitbutler_branch import DEFAULT_SETTINGS, GitButlerWorkspaceCase
from vcs_test_support import bash_path_env

GITHUB = "https://github.com/o/r.git"
LOGIN = "code-bot"


class GitButlerNetworkCase(GitButlerWorkspaceCase):
    def prepare(self, scratch):
        """Fake gh tokens for two accounts and the Git-call log shim; returns the ButWrap for this scratch."""
        scratch.gh_state.write_text(json.dumps(
            {"user": "sh1ny", "tokens": {"sh1ny": "tok-sh1ny", LOGIN: "tok-code"}}), encoding="utf-8")
        self.shim = gitlog.install(self.root / "shim", real_git=real_git(), log_path=self.root / "git-calls.jsonl")
        return ButWrap(scratch)

    def github_view(self):
        script = self.shim.path / "git"
        text = script.read_text(encoding="utf-8").replace("\r\n", "\n")
        answer = 'if [ "$*" = "remote get-url origin" ]; then echo "%s"; exit 0; fi\n' % GITHUB
        text = text.replace('exec "$SPECWRIGHT_REAL_GIT" "$@"', answer + 'exec "$SPECWRIGHT_REAL_GIT" "$@"')
        with script.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)

    def fenced_env(self, scratch, wrap, extra_path=()):
        """Git shim first, then the logging `but`, then the fake gh; the fixture's isolated Git and GitButler state."""
        env = {**wrap.env(scratch), **{k: v for k, v in self.shim.env.items() if k != "PATH"}}
        env["PATH"] = bash_path_env(self.shim.path, extra_path=(*extra_path, wrap.dir, scratch.bin))["PATH"]
        return env

    def vcs(self, scratch, wrap, command, *options, expected=0, extra_path=()):
        result, _ = self.invoke(command, *options, repo=self.repo_path, env=self.fenced_env(scratch, wrap, extra_path),
                                expected=expected)
        return result

    def gh_tokens(self, scratch):
        path = scratch.gh_log
        calls = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
        return [call["env"]["GH_TOKEN"] for call in calls if call["argv"][0] == "api"]

    def workspace(self, scratch, branches, settings=DEFAULT_SETTINGS):
        """A managed repo with each branch applied and holding one commit (`<name>.txt`)."""
        repo = self.managed(scratch, settings)
        self.repo_path = repo.path
        for branch in branches:
            repo.but("branch", "new", branch)
            self.commit_on(repo, branch, branch.split("/")[-1] + ".txt")
        return repo

    def origin_refs(self, scratch):
        out = self.git(scratch.origin, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads").stdout
        return dict(line.split() for line in out.splitlines())

    def tip(self, repo, branch):
        return self.git(repo.path, "rev-parse", "refs/heads/" + branch).stdout.strip()

    def base(self, repo):
        """GitButler's stored workspace base."""
        return json.loads(repo.but("status", "--json").stdout)["mergeBase"]["commitId"]

    def clone_of_origin(self, scratch):
        side = self.root / "origin-side"
        done = subprocess.run([real_git(), "clone", "-q", str(scratch.origin), str(side)], env=scratch.env,
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        for key, value in (("user.name", "Remote"), ("user.email", "remote@example.invalid")):
            self.assertEqual(self.git(side, "config", key, value).returncode, 0)
        return side

    def side_git(self, side, *args):
        done = self.git(side, *args)
        self.assertEqual(done.returncode, 0, "git %s: %s" % (" ".join(map(str, args)), done.stderr))
        return done.stdout.strip()

    def merge_on_origin(self, scratch, branch):
        """The merge button with delete-branch: a merge commit on origin's main, then the head branch deleted."""
        side = self.clone_of_origin(scratch)
        self.side_git(side, "fetch", "-q", "origin", branch)
        self.side_git(side, "merge", "--no-ff", "-m", "Merge pull request #1 from o/" + branch, "FETCH_HEAD")
        self.side_git(side, "push", "-q", "origin", "HEAD:refs/heads/main")
        self.side_git(side, "push", "-q", "origin", ":refs/heads/" + branch)
        return self.side_git(side, "rev-parse", "HEAD")

    def real_squash(self, scratch, files):
        """A squash merge as GitHub makes it: one new commit on origin's main holding the branch's files (name -> text)."""
        side = self.clone_of_origin(scratch)
        for name, text in files.items():
            (side / name).write_text(text, encoding="utf-8")
            self.side_git(side, "add", name)
        self.side_git(side, "commit", "-q", "-m", "feat: add c (#1)")
        self.side_git(side, "push", "-q", "origin", "HEAD:refs/heads/main")
        return self.side_git(side, "rev-parse", "HEAD")

    def squash_stand_in(self, scratch):
        """A new commit on origin's main that leaves the branch's files alone: the PR's `merge_commit_sha`.

        A real squash carries the branch's own content, so `but pull` 0.23.1 reports the branch integrated and removes
        it, and the delete then finds it gone (`already_deleted`). The stand-in keeps the branch applied after the pull,
        so the `--merged-commit` rule is what decides the delete."""
        side = self.clone_of_origin(scratch)
        (side / "squashed.txt").write_text("squashed\n", encoding="utf-8")
        self.side_git(side, "add", "squashed.txt")
        self.side_git(side, "commit", "-q", "-m", "feat: add c (#1)")
        self.side_git(side, "push", "-q", "origin", "HEAD:refs/heads/main")
        return self.side_git(side, "rev-parse", "HEAD")
