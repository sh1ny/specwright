"""The GitButler probe uses Git reads, then `but --version` outside the repo; the Git backend refuses a workspace.

Fixtures are real: a managed repo is a scratch clone `but` has opened (butenv). A stub `but` on PATH records where it
ran, to prove no `but` command runs in the repo (any `but` command there would set the repo up).
"""
import json

from butenv import Scratch, require_but
from vcs_test_support import VcsTestCase, bash_path_env, sw_run


class GitButlerCase(VcsTestCase):
    def isolated(self, scratch):
        """The scratch environment minus PATH: invoke() builds the Git Bash PATH itself."""
        return {key: value for key, value in scratch.env.items() if key != "PATH"}

    def stub_but(self, version="but 0.23.1"):
        """A `but` that only reports a version and logs the directory it ran in. Returns (path env, log)."""
        stub = self.root / "stub-bin"
        stub.mkdir(exist_ok=True)
        log = self.root / "but-calls.log"
        script = stub / "but"
        with script.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("#!/bin/sh\nprintf '%%s\\n' \"$PWD\" >> '%s'\nprintf '%s\\n'\n" % (log.as_posix(), version))
        script.chmod(0o755)
        return {**bash_path_env(extra_path=(stub,))}, log

    def snapshot(self, repo):
        refs = self.git(repo, "for-each-ref").stdout
        return (repo / ".git" / "config").read_bytes(), refs, (repo / ".git" / "gitbutler").exists()

    def head(self, repo):
        return self.git(repo, "symbolic-ref", "HEAD").stdout.strip()

    def settings(self, repo, text="vcs: gitbutler\nfinish: pr\n"):
        self.set_settings(repo, text)

    def probe_from(self, scratch, repo, cwd, expected):
        """`sw vcs probe` started in `cwd`, with the stub `but` (stub_but() first) on PATH."""
        stub_env, _ = self.stub_but()
        result = sw_run(["vcs", "probe", "--repo", repo, "--role", "code"], cwd=cwd, env={**stub_env, **self.isolated(scratch)})
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)


class TestGitButlerProbe(GitButlerCase):
    def test_but_missing_stops_before_write(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo().path
            self.settings(repo)
            before = self.snapshot(repo)
            env = {**bash_path_env(exclude_tools=("but",)), **self.isolated(scratch)}
            result, _ = self.invoke("probe", repo=repo, env=env, expected=1)
            self.assertEqual(result["error"], "tool_missing")
            self.assertIn("but", result["message"])
            self.assertEqual(self.snapshot(repo), before)
            self.assertEqual(self.git(repo, "branch", "--list", "feat/*").stdout.strip(), "")

    def test_unmanaged_repo_not_set_up(self):
        self.settings(self.repo)
        stub_env, log = self.stub_but()
        before = self.snapshot(self.repo)
        result, _ = self.invoke("probe", repo=self.repo, env=stub_env, expected=1)
        self.assertEqual(result["error"], "not_managed")
        self.assertIn("GitButler", result["message"])
        self.assertFalse((self.repo / ".git" / "gitbutler").exists())
        self.assertEqual(self.snapshot(self.repo), before)
        self.assertFalse(log.exists(), "but ran although the repo is not managed")

    def test_target_mismatch_stops(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo().path
            self.settings(repo)
            self.git(repo, "config", "gitbutler.project.targetRef", "refs/remotes/origin/develop")
            stub_env, log = self.stub_but()
            result, _ = self.invoke("probe", repo=repo, env={**stub_env, **self.isolated(scratch)}, expected=1)
            self.assertEqual(result["error"], "target_mismatch")
            self.assertIn("develop", result["message"])
            self.assertIn("main", result["message"])
            self.assertFalse(log.exists(), "but ran although the target is wrong")

    def assert_target_refused(self, target):
        self.settings(self.repo, "vcs: gitbutler\nfinish: pr\nremote: publishing\n")
        (self.repo / ".git" / "gitbutler").mkdir()
        self.git(self.repo, "config", "gitbutler.project.targetRef", target)
        env, log = self.stub_but()
        before = self.snapshot(self.repo)
        result, _ = self.invoke("probe", repo=self.repo, env=env, expected=1)
        self.assertEqual(result["error"], "target_mismatch", result)
        self.assertIn("refs/remotes/publishing/main", result["message"])
        self.assertFalse(log.exists(), "but ran although the target is wrong")
        self.assertEqual(self.snapshot(self.repo), before)

    def test_explicit_remote_rejects_gitbutler_target_for_other_remote(self):
        self.assert_target_refused("refs/remotes/origin/main")

    def test_explicit_remote_rejects_gitbutler_local_only_target(self):
        self.assert_target_refused("refs/heads/main")

    def test_probe_passes_and_runs_but_outside_repo(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo().path
            self.settings(repo)
            stub_env, log = self.stub_but()
            for target in ("refs/heads/main", "refs/remotes/origin/main"):
                self.git(repo, "config", "gitbutler.project.targetRef", target)
                before = self.snapshot(repo)
                result, _ = self.invoke("probe", repo=repo, env={**stub_env, **self.isolated(scratch)})
                self.assertEqual((result["backend"], result["main"]), ("gitbutler", "main"))
                self.assertEqual(self.snapshot(repo), before)
            ran = log.read_text(encoding="utf-8").split()
            self.assertTrue(ran)
            for directory in ran:  # the scratch root's unique name is in every path inside the repo
                self.assertNotIn(scratch.root.name, directory)

    def test_old_or_unreadable_but_stops(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo().path
            self.settings(repo)
            for version, error in (("but 0.22.9", "tool_too_old"), ("nonsense", "tool_version_unknown")):
                stub_env, _ = self.stub_but(version)
                result, _ = self.invoke("probe", repo=repo, env={**stub_env, **self.isolated(scratch)}, expected=1)
                self.assertEqual(result["error"], error)


class TestInstallLocation(GitButlerCase):
    """gitbutler-in-repo-install: the probe passes wherever Specwright is installed, in the work tree or outside it."""

    def passes(self, scratch, repo, log, cwd):
        result = self.probe_from(scratch, repo, cwd, expected=0)
        self.assertIs(result["ok"], True)
        self.assertEqual((result["backend"], result["main"]), ("gitbutler", "main"))
        self.assertTrue(log.exists() and log.read_text(encoding="utf-8").split(), "the probe never reached but")

    def test_in_repo_scripts_probe_passes(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo().path
            self.settings(repo)
            _, log = self.stub_but()
            self.git(repo, "config", "gitbutler.project.targetRef", "refs/heads/main")
            installed = repo / ".claude" / "skills" / "specwright-pr"
            installed.mkdir(parents=True)
            self.passes(scratch, repo, log, installed)

    def test_user_level_scripts_with_in_repo_copy_probe_passes(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo().path
            self.settings(repo)
            _, log = self.stub_but()
            self.git(repo, "config", "gitbutler.project.targetRef", "refs/heads/main")
            (repo / ".claude" / "skills" / "specwright-pr").mkdir(parents=True)
            outside = self.root / "user-level" / "specwright-pr"
            outside.mkdir(parents=True)
            self.passes(scratch, repo, log, outside)

    def test_outside_repo_without_project_is_sw_mismatch(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo().path
            self.settings(repo)
            stub_env, log = self.stub_but()
            outside = self.root / "outside"
            outside.mkdir()
            done = sw_run(["vcs", "probe"], cwd=outside, env={**stub_env, **self.isolated(scratch)}, stamp=False)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            result = json.loads(done.stdout)
            self.assertEqual((result["ok"], result["error"]), (False, "sw_mismatch"), result)
            self.assertIn("no installed version found", result["message"])
            self.assertFalse(log.exists(), "a but command ran")


class TestGitBackendRefusesWorkspace(GitButlerCase):
    def refuses(self, scratch, repo, head):
        before = self.snapshot(repo)
        self.assertEqual(self.head(repo), head)
        result, _ = self.invoke("probe", repo=repo, env=self.isolated(scratch), expected=1)
        self.assertEqual(result["error"], "gitbutler_workspace")
        self.assertIn("vcs: gitbutler", result["message"])
        self.assertEqual(self.head(repo), head)
        self.assertEqual(self.snapshot(repo), before)
        return result

    def test_git_backend_refuses_workspace_head(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo()
            repo.but("branch", "new", "feat/a")
            repo.but("branch", "new", "feat/b")
            self.refuses(scratch, repo.path, "refs/heads/gitbutler/workspace")

    def test_git_backend_refuses_single_branch_mode(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo()
            repo.but("branch", "new", "feat/b")
            result = self.refuses(scratch, repo.path, "refs/heads/feat/b")
            self.assertNotIn("switch to main", result["message"].lower())

    def test_git_backend_refuses_head_on_main(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo()
            self.refuses(scratch, repo.path, "refs/heads/main")
