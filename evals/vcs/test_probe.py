"""The backend probe validates selected jj repositories without initializing them."""

import json
import shutil

from jjenv import Scratch, require_jj, real_git
from vcs_test_support import ROOT, VcsTestCase, bash_path_env, bash_run


class TestProbe(VcsTestCase):
    def test_probe_colocated_passes(self):
        require_jj()
        with Scratch() as scratch:
            repo = scratch.tracked_repo()
            (repo.path / "openspec").mkdir(exist_ok=True)
            (repo.path / "openspec" / "specwright.yaml").write_text("vcs: jj\n", encoding="utf-8")
            result, _ = self.invoke("probe", repo=repo.path)
            self.assertEqual(result["backend"], "jj")
            self.assertEqual(result["main"], "main")

    def test_probe_tool_missing(self):
        self.set_settings(self.repo, "vcs: jj\n")
        result, _ = self.invoke("probe", repo=self.repo, env=bash_path_env(exclude_tools=("jj",)), expected=1)
        self.assertEqual(result["error"], "tool_missing")
        self.assertIn("jj", result["message"])

    def test_probe_tool_too_old(self):
        self.set_settings(self.repo, "vcs: jj\n")
        stub = self.root / "old-jj"
        stub.mkdir()
        executable = stub / "jj"
        with executable.open("w", encoding="utf-8", newline="\n") as script:
            script.write("#!/bin/sh\nprintf 'jj 0.45.1\\n'\n")
        executable.chmod(0o755)
        env = bash_path_env(extra_path=(stub,))
        result, _ = self.invoke("probe", repo=self.repo, env=env, expected=1)
        self.assertEqual(result["error"], "tool_too_old")
        self.assertIn("0.45.1", result["message"])
        self.assertIn("0.46", result["message"])

    def test_probe_not_managed_runs_no_init(self):
        require_jj()
        self.set_settings(self.repo, "vcs: jj\n")
        result, _ = self.invoke("probe", repo=self.repo, expected=1)
        self.assertEqual(result["error"], "not_managed")
        self.assertFalse((self.repo / ".jj").exists())

    def test_probe_secondary_workspace_not_colocated(self):
        require_jj()
        with Scratch() as scratch:
            root = scratch.tracked_repo().path
            workspace = scratch.root / "secondary"
            # A secondary jj workspace has its own working directory and no Git work tree.
            import subprocess
            made = subprocess.run([require_jj(), "workspace", "add", "--no-colocate", str(workspace),
                                   "--repository", str(root)],
                                  env=scratch.env, capture_output=True, text=True)
            self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
            git_root = subprocess.run([real_git(), "rev-parse", "--show-toplevel"], cwd=workspace,
                                      env=scratch.env, capture_output=True, text=True)
            self.assertNotEqual(git_root.returncode, 0, git_root.stdout + git_root.stderr)
            (workspace / "openspec").mkdir(exist_ok=True)
            (workspace / "openspec" / "specwright.yaml").write_text("vcs: jj\n", encoding="utf-8")
            result, _ = self.invoke("probe", repo=workspace, expected=1)
            self.assertEqual(result["error"], "not_colocated")

    def test_git_backend_ignores_in_repo_scripts(self):
        """fix-m5-gaps D7 (#150): the workspace check belongs to the GitButler backend; Git keeps in-repo installs."""
        self.set_settings(self.repo, "vcs: git\n")
        scripts = self.repo / ".claude" / "skills" / "specwright-pr" / "scripts"
        shutil.copytree(ROOT / "skills" / "specwright-pr" / "scripts", scripts,
                        ignore=shutil.ignore_patterns("__pycache__"))
        for extra in (".agents/skills/specwright-branch", ".claude/agents/specwright-reviewer.md",
                      ".omp/agents/specwright-implementer.md"):
            path = self.repo / extra
            path.parent.mkdir(parents=True, exist_ok=True)
            if extra.endswith(".md"):
                path.write_text("copy\n", encoding="utf-8")
            else:
                path.mkdir()
        result = bash_run([(scripts / "vcs.sh").as_posix(), "probe", "--repo", str(self.repo), "--role", "code"],
                          cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        obj = json.loads(result.stdout)
        self.assertEqual((obj["ok"], obj["backend"], obj["main"]), (True, "git", "main"))
