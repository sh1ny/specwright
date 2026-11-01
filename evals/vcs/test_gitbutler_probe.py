"""The GitButler probe uses Git reads, then `but --version` outside the repo; the Git backend refuses a workspace.

Fixtures are real: a managed repo is a scratch clone `but` has opened (butenv). A stub `but` on PATH records where it
ran, to prove no `but` command runs in the repo (any `but` command there would set the repo up).
"""
import json
import shutil

from butenv import Scratch, require_but
from vcs_test_support import ROOT, VcsTestCase, bash_path_env, bash_run


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

    def copy_scripts(self, destination):
        """A copy of the shipped specwright-pr scripts at `destination`; returns its vcs.sh."""
        shutil.copytree(ROOT / "skills" / "specwright-pr" / "scripts", destination,
                        ignore=shutil.ignore_patterns("__pycache__"))
        return destination / "vcs.sh"

    def run_copy(self, script, scratch, repo, expected):
        """`probe` through the vcs.sh at `script`, with the stub `but` (stub_but() first) on PATH."""
        result = bash_run([script.as_posix(), "probe", "--repo", str(repo), "--role", "code"], cwd=repo,
                          env=self.isolated(scratch), shim=self.root / "stub-bin")
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


class TestScriptsOutsideWorkspace(GitButlerCase):
    """fix-m5-gaps D7 (#150): the probe stops before any `but` command when Specwright is in the work tree."""

    def test_scripts_in_work_tree_stop_before_but(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo().path
            self.settings(repo)
            _, log = self.stub_but()
            script = self.copy_scripts(repo / "tools" / "flow" / "scripts")
            before = self.snapshot(repo)
            result = self.run_copy(script, scratch, repo, expected=1)
            self.assertEqual(result["error"], "scripts_in_workspace")
            self.assertIn("tools/flow/scripts", result["message"])
            self.assertIn("user level", result["message"])
            self.assertIn("by hand", result["message"])
            self.assertIn("GitButler", result["message"])
            self.assertFalse(log.exists(), "but ran although the scripts are in the work tree")
            self.assertEqual(self.snapshot(repo), before)

    def test_scripts_outside_work_tree_probe_continues(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo().path
            self.settings(repo)
            _, log = self.stub_but()
            self.git(repo, "config", "gitbutler.project.targetRef", "refs/heads/main")
            script = self.copy_scripts(self.root / "user-level" / "specwright-pr" / "scripts")
            result = self.run_copy(script, scratch, repo, expected=0)
            self.assertEqual((result["backend"], result["main"]), ("gitbutler", "main"))
            self.assertTrue(log.exists() and log.read_text(encoding="utf-8").split(), "the probe never reached but")

    def test_specwright_copy_in_work_tree_stops(self):
        require_but()
        with Scratch() as scratch:
            repo = scratch.tracked_repo().path
            self.settings(repo)
            _, log = self.stub_but()
            script = self.copy_scripts(self.root / "user-level" / "specwright-pr" / "scripts")
            for rel, is_dir in ((".claude/skills/specwright-pr", True), (".agents/skills/specwright-branch", True),
                                (".claude/agents/specwright-reviewer.md", False),
                                (".omp/agents/specwright-implementer.md", False)):
                with self.subTest(rel):
                    copy = repo / rel
                    copy.parent.mkdir(parents=True, exist_ok=True)
                    if is_dir:
                        copy.mkdir()
                    else:
                        copy.write_text("copy\n", encoding="utf-8")
                    try:
                        result = self.run_copy(script, scratch, repo, expected=1)
                    finally:
                        if is_dir:
                            shutil.rmtree(copy)
                        else:
                            copy.unlink()
                    self.assertEqual(result["error"], "scripts_in_workspace")
                    self.assertIn(rel, result["message"])
                    self.assertIn("user level", result["message"])
                    self.assertIn("by hand", result["message"])
                    self.assertFalse(log.exists(), "but ran although a Specwright copy is in the work tree")


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
