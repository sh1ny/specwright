"""Shared subprocess and repository helpers for the VCS backend contract tests."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import gitlog
import jjenv

ROOT = Path(__file__).resolve().parents[2]
VCS = ROOT / "skills" / "specwright-pr" / "scripts" / "vcs.sh"


def bash_path_env(git_shim=None, extra_path=(), exclude_tools=()):
    """Build a Git-Bash-native PATH while retaining host tools and exposing extensionless shims."""
    env = os.environ.copy()
    bash = jjenv.find_bash()
    if os.name == "nt" and bash:
        cygpath = shutil.which("cygpath")
        if not cygpath:
            raise AssertionError("cygpath is required to construct Git Bash PATH")
        roots = []
        if git_shim:
            roots.append(Path(git_shim))
        roots.extend(Path(p) for p in extra_path)
        bash_root = Path(bash).resolve().parent
        roots.extend((bash_root.parent / "usr" / "bin", bash_root.parent / "mingw64" / "bin"))
        excluded = {str(Path(shutil.which(name)).parent.resolve()).casefold()
                    for name in exclude_tools if shutil.which(name)}
        excluded.add(str(bash_root).casefold())
        roots.extend(Path(p) for p in env.get("PATH", "").split(os.pathsep)
                     if p and str(Path(p).resolve()).casefold() not in excluded)
        converted = []
        seen = set()
        for root in roots:
            result = subprocess.run([cygpath, "-u", str(root)], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip() not in seen:
                converted.append(result.stdout.strip())
                seen.add(result.stdout.strip())
        env["PATH"] = ":".join(converted)
    else:
        excluded = {str(Path(shutil.which(name)).parent).casefold() for name in exclude_tools if shutil.which(name)}
        prefixes = [str(Path(p)) for p in ((git_shim,) if git_shim else ()) + tuple(extra_path)]
        inherited = [p for p in env.get("PATH", "").split(os.pathsep)
                     if p and str(Path(p)).casefold() not in excluded]
        env["PATH"] = os.pathsep.join(prefixes + inherited)
    return env


def bash_run(args, cwd, env=None, shim=None):
    """Run `bash <args>` with a Git-Bash-native PATH (the way VcsTestCase.invoke does); returns the CompletedProcess.
    `env` adds variables (its PATH is ignored); `shim` is a directory put first on PATH."""
    shell_env = bash_path_env(shim)
    shell_env.update({key: value for key, value in (env or {}).items() if key != "PATH"})
    shell_env["VCS_TEST_SEARCH"] = shell_env["PATH"]
    return subprocess.run([jjenv.find_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"',
                           "bash-run", *map(str, args)], cwd=cwd, env=shell_env, capture_output=True, text=True,
                          encoding="utf-8")


class VcsTestCase(unittest.TestCase):
    def setUp(self):
        if not VCS.is_file():
            self.fail("missing component: skills/specwright-pr/scripts/vcs.sh")
        self.temp = tempfile.TemporaryDirectory(prefix="swv-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self._init_git(self.repo)

    def _init_git(self, path):
        path.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_AUTHOR_NAME": "VCS Test", "GIT_AUTHOR_EMAIL": "vcs-test@example.invalid",
               "GIT_COMMITTER_NAME": "VCS Test", "GIT_COMMITTER_EMAIL": "vcs-test@example.invalid"}
        for args in (("init", "-b", "main"), ("config", "user.name", "VCS Test"),
                     ("config", "user.email", "vcs-test@example.invalid")):
            result = subprocess.run([jjenv.real_git(), *args], cwd=path, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (path / "base.txt").write_text("base\n", encoding="utf-8")
        self.git(path, "add", "base.txt", env=env)
        self.git(path, "commit", "-m", "initial", env=env)

    def git(self, repo, *args, env=None):
        result = subprocess.run([jjenv.real_git(), *map(str, args)], cwd=repo,
                                env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                                     "GIT_AUTHOR_NAME": "VCS Test", "GIT_AUTHOR_EMAIL": "vcs-test@example.invalid",
                                     "GIT_COMMITTER_NAME": "VCS Test", "GIT_COMMITTER_EMAIL": "vcs-test@example.invalid",
                                     **(env or {})}, capture_output=True, text=True)
        return result

    def invoke(self, command, *options, repo=None, role="code", code=None, env=None, expected=0):
        target = Path(repo or self.repo)
        args = ["--repo", str(target), "--role", role]
        if code is not None:
            args += ["--code", str(code)]
        shim = getattr(self, "shim", None)
        shell_env = bash_path_env(shim.path if shim else None)
        scratch = getattr(self, "scratch", None)
        shell_env.update(scratch.jj_env if scratch is not None else {})  # the jj that vcs.sh runs reads the fixture's config
        shell_env.update({key: value for key, value in getattr(self, "env", {}).items() if key != "PATH"})
        shell_env.update(env or {})
        shell_env["VCS_TEST_SEARCH"] = shell_env["PATH"]
        result = subprocess.run(
            [jjenv.find_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"',
             "vcs-test", VCS.as_posix(), command, *args, *map(str, options)],
            cwd=target, env=shell_env, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        try:
            obj = json.loads(result.stdout)
        except ValueError as e:
            self.fail("vcs.sh did not emit one JSON document: %r (%s)" % (result.stdout, e))
        return obj, result

    def set_settings(self, repo, text):
        path = Path(repo) / "openspec" / "specwright.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
