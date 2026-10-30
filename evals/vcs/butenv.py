"""Real-but (GitButler) test fixtures and missing-binary policy for the VCS eval suite.

A fixture is a scratch clone of a local bare origin that `but status` has opened once. It is built once per
process (evals/fixturecache.py) and copied into each Scratch; the copy keeps working under `but` at its new path
(test_butenv_fixture.py checks this). GitButler's app data is isolated per Scratch (E2E_TEST_APP_DATA_DIR) with
metrics disabled, so no eval touches the developer's GitButler projects or sends metrics.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals"))
import fixturecache  # noqa: E402

FIXTURE_NAME = "Specwright Eval"
FIXTURE_EMAIL = "specwright-eval@example.invalid"
FAKE_GH = ROOT / "evals" / "fakes" / "gh.py"


def find_but():
    """Return but's executable path from PATH, or None when the executable is unavailable."""
    return shutil.which("but")


def require_but():
    """Require but for a test, honoring the local-skip / CI-required contract."""
    executable = find_but()
    if executable:
        return executable
    if os.environ.get("SPECWRIGHT_REQUIRE_BUT") == "1":
        raise AssertionError("but not installed (SPECWRIGHT_REQUIRE_BUT=1)")
    raise unittest.SkipTest("but not installed")


def real_git():
    """Resolve Git before a test prepends its call-logging shim to PATH."""
    git = shutil.which("git")
    if not git:
        raise AssertionError("git not installed")
    return str(Path(git).resolve())


def _run(argv, cwd=None, env=None):
    result = subprocess.run(list(map(str, argv)), cwd=str(cwd) if cwd else None, env=env, capture_output=True,
                            text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError("command failed (%s): %s\n%s\n%s" % (
            result.returncode, " ".join(map(str, argv)), result.stdout, result.stderr))
    return result


def _rmtree(path):
    fixturecache._rmtree(path)


def _isolated_env(app_data, extra_path=None):
    """The environment every fixture command gets: no user or system Git config, isolated GitButler app data."""
    env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": FIXTURE_NAME,
        "GIT_AUTHOR_EMAIL": FIXTURE_EMAIL,
        "GIT_COMMITTER_NAME": FIXTURE_NAME,
        "GIT_COMMITTER_EMAIL": FIXTURE_EMAIL,
        "E2E_TEST_APP_DATA_DIR": str(app_data),
    }
    if extra_path:
        env["PATH"] = str(extra_path) + os.pathsep + env.get("PATH", "")
    return env


def _posix(path):
    return Path(path).resolve().as_posix()


def _disable_metrics(but, env, cwd):
    """GitButler sends metrics unless told not to; once per app data directory."""
    _run([but, "config", "metrics", "disable"], cwd=cwd, env=env)


def _build_world(dest):
    """origin.git (main pushed) and repo (clone of it, opened by `but status`), built under `dest`.
    Only a path-independent shape is cached: the clone's remote URL is repointed after each copy."""
    but = require_but()
    git = real_git()
    dest.mkdir(parents=True)
    app_data = dest / "appdata"
    env = _isolated_env(app_data)
    origin = dest / "origin.git"
    seed = dest / "seed"
    _run([git, "init", "-q", "--bare", "-b", "main", _posix(origin)], env=env)
    _run([git, "init", "-q", "-b", "main", str(seed)], env=env)
    (seed / "README.md").write_text("specwright fixture\n", encoding="utf-8", newline="\n")
    _run([git, "add", "README.md"], cwd=seed, env=env)
    _run([git, "-c", "core.autocrlf=false", "commit", "-q", "-m", "initial"], cwd=seed, env=env)
    _run([git, "remote", "add", "origin", _posix(origin)], cwd=seed, env=env)
    _run([git, "push", "-q", "origin", "main"], cwd=seed, env=env)
    _run([git, "symbolic-ref", "HEAD", "refs/heads/main"], cwd=origin, env=env)
    repo = dest / "repo"
    _run([git, "clone", "-q", "-c", "core.autocrlf=false", _posix(origin), str(repo)], env=env)
    _run([git, "config", "user.name", FIXTURE_NAME], cwd=repo, env=env)
    _run([git, "config", "user.email", FIXTURE_EMAIL], cwd=repo, env=env)
    _disable_metrics(but, env, repo)
    _run([but, "status", "--json"], cwd=repo, env=env)  # there is no setup command: any `but` command opens the repo
    _rmtree(seed)


class Repo:
    """One scratch GitButler repository and its local bare origin."""
    def __init__(self, path, origin, env):
        self.path = Path(path)
        self.origin = Path(origin)
        self.env = dict(env)
        self.git = self.path / ".git"

    def run(self, *argv, check=True, env=None):
        """Run a command in this repository with the fixture environment."""
        result = subprocess.run(list(map(str, argv)), cwd=str(self.path), env={**self.env, **(env or {})},
                                capture_output=True, text=True, encoding="utf-8")
        if check and result.returncode:
            raise RuntimeError("command failed (%s): %s\n%s\n%s" % (
                result.returncode, " ".join(map(str, argv)), result.stdout, result.stderr))
        return result

    def but(self, *args, **kwargs):
        return self.run(require_but(), *args, **kwargs)

    def git_run(self, *args, **kwargs):
        return self.run(real_git(), *args, **kwargs)


class Scratch:
    """Own a short-lived root with a bare origin, isolated GitButler app data, a fake gh and a GitButler repo."""
    def __init__(self):
        require_but()
        self.root = Path(tempfile.mkdtemp(prefix="swb-"))
        self._open = True
        self.origin = self.root / "origin.git"
        self.app_data = self.root / "appdata"
        self.gh_state = self.root / "gh-state.json"
        self.gh_log = self.root / "gh-log.jsonl"
        self.bin = self.root / "bin"
        self._install_fake_gh()
        self.env = {
            **_isolated_env(self.app_data, self.bin),
            "FAKE_GH_STATE": _posix(self.gh_state),
            "FAKE_GH_LOG": _posix(self.gh_log),
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        if self._open:
            _rmtree(self.root)
            self._open = False

    def _install_fake_gh(self):
        self.bin.mkdir()
        shim = self.bin / "gh"
        shim.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (_posix(sys.executable), _posix(FAKE_GH)),
                        encoding="utf-8", newline="\n")
        shim.chmod(0o755)

    def tracked_repo(self, name="repo"):
        """A copy of the cached fixture world: the repo is a clone of this Scratch's origin and `but` has opened it."""
        world = self.root / "world"
        fixturecache.copy("butenv-world", _build_world, world)
        shutil.move(str(world / "origin.git"), str(self.origin))
        shutil.move(str(world / "appdata"), str(self.app_data))
        path = self.root / name
        shutil.move(str(world / "repo"), str(path))
        world.rmdir()
        _run([real_git(), "remote", "set-url", "origin", _posix(self.origin)], cwd=path, env=self.env)
        repo = Repo(path, self.origin, self.env)
        return repo

    def make_bare_remote(self):
        """Return the local bare origin of the scratch repository."""
        return self.origin
