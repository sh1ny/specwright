"""Real-jj test fixtures and missing-binary policy for the VCS eval suite."""
import os
import shutil
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "evals") not in sys.path:
    sys.path.append(str(ROOT / "evals"))
import bashexe  # noqa: E402


FIXTURE_NAME = "Specwright Eval"
FIXTURE_EMAIL = "specwright-eval@example.invalid"


def find_jj():
    """Return jj's executable path from PATH, or None when the executable is unavailable."""
    return shutil.which("jj")


def require_jj():
    """Require jj for a test, honoring the local-skip / CI-required contract."""
    executable = find_jj()
    if executable:
        return executable
    if os.environ.get("SPECWRIGHT_REQUIRE_JJ") == "1":
        raise AssertionError("jj not installed (SPECWRIGHT_REQUIRE_JJ=1)")
    raise unittest.SkipTest("jj not installed")


find_bash = bashexe.bash  # moved to evals/bashexe.py; the name stays for the vcs suite


def real_git():
    """Resolve Git before a test prepends its call-logging shim to PATH."""
    git = shutil.which("git")
    if not git:
        raise AssertionError("git not installed")
    return str(Path(git).resolve())


def _run(argv, cwd=None, env=None):
    result = subprocess.run(argv, cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("command failed (%s): %s\n%s\n%s" % (
            result.returncode, " ".join(map(str, argv)), result.stdout, result.stderr))
    return result


class Repo:
    """One scratch repository and its local bare origin."""
    def __init__(self, path, origin, env, git_executable):
        self.path = Path(path)
        self.origin = Path(origin)
        self.env = dict(env)
        self.git = self.path / ".git"
        self.jj = self.path / ".jj"
        self._git_executable = git_executable

    def run(self, *argv, check=True, env=None):
        """Run a command in this repository with the fixture environment."""
        result = subprocess.run(list(map(str, argv)), cwd=str(self.path), env={**self.env, **(env or {})},
                                capture_output=True, text=True)
        if check and result.returncode:
            raise RuntimeError("command failed (%s): %s\n%s\n%s" % (
                result.returncode, " ".join(map(str, argv)), result.stdout, result.stderr))
        return result

    def git_configure_jj(self):
        config = self.jj / "repo" / "config.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text('git.executable-path = %s\n' % _toml_string(self._git_executable), encoding="utf-8")


def _toml_string(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


class Scratch:
    """Own a short-lived root, bare origin, and real colocated jj repository fixtures."""
    def __init__(self):
        self._temp = tempfile.TemporaryDirectory(prefix="swv-")
        self.root = Path(self._temp.name)
        self.origin = self.root / "origin.git"
        self._git = real_git()
        # The user's jj config is not read (a CI runner has none): jj commits get the fixture identity everywhere.
        # jj 0.46 keeps repo config outside .jj/, so jj's own Git calls are pointed past a test's logging shim here.
        self.jj_env = {
            "JJ_CONFIG": str(self.root / "jj-config.toml"),
            "JJ_USER": FIXTURE_NAME,
            "JJ_EMAIL": FIXTURE_EMAIL,
        }
        (self.root / "jj-config.toml").write_text(
            "git.executable-path = %s\n" % _toml_string(self._git), encoding="utf-8")
        self.env = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": FIXTURE_NAME,
            "GIT_AUTHOR_EMAIL": FIXTURE_EMAIL,
            "GIT_COMMITTER_NAME": FIXTURE_NAME,
            "GIT_COMMITTER_EMAIL": FIXTURE_EMAIL,
            **self.jj_env,
        }
        self._make_bare_remote()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        if self._temp is not None:
            self._temp.cleanup()
            self._temp = None

    def _git_run(self, *args, cwd=None):
        return _run([self._git, *map(str, args)], cwd=cwd, env=self.env)

    def _make_bare_remote(self):
        self._git_run("init", "--bare", str(self.origin))
        seed = self.root / "seed"
        seed.mkdir()
        self._git_run("init", "-b", "main", str(seed))
        (seed / "README.md").write_text("specwright fixture\n", encoding="utf-8")
        self._git_run("add", "README.md", cwd=seed)
        self._git_run("commit", "-m", "initial", cwd=seed)
        self._git_run("remote", "add", "origin", str(self.origin), cwd=seed)
        self._git_run("push", "-u", "origin", "main", cwd=seed)
        self._git_run("symbolic-ref", "HEAD", "refs/heads/main", cwd=self.origin)

    def tracked_repo(self, name="tracked"):
        """Clone the fixture origin with jj git clone --colocate (main tracks origin/main)."""
        jj = require_jj()
        path = self.root / name
        _run([jj, "--config", 'user.name="%s"' % FIXTURE_NAME,
              "--config", 'user.email="%s"' % FIXTURE_EMAIL,
              "git", "clone", "--colocate", str(self.origin), str(path)], env=self.env)
        repo = Repo(path, self.origin, self.env, self._git)
        repo.git_configure_jj()
        return repo

    def untracked_repo(self, name="untracked"):
        """Initialize a colocated repository whose local main has no remote tracking bookmark."""
        jj = require_jj()
        path = self.root / name
        _run([jj, "--config", 'user.name="%s"' % FIXTURE_NAME,
              "--config", 'user.email="%s"' % FIXTURE_EMAIL,
              "git", "init", "--colocate", str(path)], env=self.env)
        repo = Repo(path, self.origin, self.env, self._git)
        repo.git_configure_jj()
        (path / "README.md").write_text("specwright fixture\n", encoding="utf-8")
        _run([jj, "--config", 'user.name="%s"' % FIXTURE_NAME,
              "--config", 'user.email="%s"' % FIXTURE_EMAIL,
              "commit", "-m", "initial", "--repository", str(path)], env=self.env)
        _run([jj, "--config", 'user.name="%s"' % FIXTURE_NAME,
              "--config", 'user.email="%s"' % FIXTURE_EMAIL,
              "bookmark", "create", "main", "-r", "@-", "--repository", str(path)], env=self.env)
        self._git_run("remote", "add", "origin", str(self.origin), cwd=path)
        return repo

    def make_bare_remote(self):
        """Return the local bare origin shared by the scratch repositories."""
        return self.origin
