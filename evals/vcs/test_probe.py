"""The backend probe validates selected jj repositories without initializing them."""

import json
import os
import shutil
import subprocess
import sys

import jjenv
from jjenv import Scratch, require_jj, real_git
from fakeexe import write_fake  # after jjenv, which puts evals/ on sys.path
from vcs_test_support import ROOT, SCRIPTS, VcsTestCase, bash_path_env, bash_run

sys.path.append(str(ROOT / "evals" / "cli"))
import swharness  # noqa: E402

SHELL_LOG = "SWP_SHELL_LOG"


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

    def failing_shells(self):
        """A directory with a recording `bash` and `sh` that exit 1 (`.cmd` files on Windows, where only PATHEXT names start)."""
        shells = self.root / "failing-shells"
        shells.mkdir()
        for name in ("bash", "sh"):  # bare-bash: not started (the names of the fake shells)
            if os.name == "nt":
                text = '@echo %s>>"%%%s%%"\r\n@exit /b 1\r\n' % (name, SHELL_LOG)
                (shells / (name + ".cmd")).write_bytes(text.encode("ascii"))
            else:
                path = shells / name
                text = '#!/bin/sh\nprintf "%%s\\n" %s >> "$%s"\nexit 1\n' % (name, SHELL_LOG)
                path.write_bytes(text.encode("ascii"))
                path.chmod(0o755)
        return shells

    def test_missing_jj_is_tool_missing_without_shell(self):
        """native-cli-launcher D1: a missing `jj` is the same `tool_missing` stop, and no shell looks for it.

        `sw vcs` gets the handoff directly. Recording `bash` and `sh` that fail are first on PATH, and the handoff names the
        recording `bash` as its shell, so a call that still starts a shell leaves a record and a different stop."""
        sw = swharness.require_sw()
        self.set_settings(self.repo, "vcs: jj\n")
        shells = self.failing_shells()
        log = self.root / "shell.log"
        shell = shells / ("bash.cmd" if os.name == "nt" else "bash")
        env = swharness.fixture_env()
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, SHELL_LOG: log.resolve().as_posix()})
        env["PATH"] = bash_path_env(shells, exclude_tools=("jj",))["PATH"]
        env["SWP_SEARCH"], env["SWP_SW"] = env["PATH"], sw
        handoff = [SCRIPTS.resolve().as_posix(), str(shell), "probe", "--repo", str(self.repo), "--role", "code"]
        done = subprocess.run([jjenv.find_bash(), "-c", 'export PATH="$SWP_SEARCH"; exec "$SWP_SW" vcs --args-stdin'],
                              input=b"".join(arg.encode("utf-8") + b"\0" for arg in handoff), cwd=str(self.repo),
                              env=env, capture_output=True, timeout=180)
        out, err = done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace")
        shell_runs = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        self.assertEqual(shell_runs, [], "a shell started: %s %s" % (out, err))
        self.assertEqual(done.returncode, 1, out + err)
        result = json.loads(out)
        self.assertEqual((result["ok"], result["error"]), (False, "tool_missing"), result)
        self.assertIn("jj", result["message"])

    def test_probe_tool_too_old(self):
        self.set_settings(self.repo, "vcs: jj\n")
        stub = self.root / "old-jj"
        stub.mkdir()
        write_fake(stub / "jj", "#!/bin/sh\nprintf 'jj 0.45.1\\n'\n")
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
