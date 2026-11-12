"""Shared subprocess and repository helpers for the VCS backend contract tests."""
import atexit
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
sys.path.append(str(ROOT / "evals" / "cli"))
import swharness  # noqa: E402

SCRIPTS = ROOT / "skills" / "specwright-pr" / "scripts"
VCS = SCRIPTS / "vcs.sh"
STAMP = "openspec/.specwright/VERSION"

_SW_HOMES = {}  # SPECWRIGHT_SW path -> (tempdir, home): one home per sw binary per test process


def tree_version():
    """The tree's version: the repo root VERSION file."""
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def make_sw_home(sw):
    """Copy the `sw` file to <new home>/.specwright/bin/<tree VERSION>/sw[.exe]; return the home. The caller owns the cleanup."""
    home = Path(tempfile.mkdtemp(prefix="swv-home-"))
    target = home / ".specwright" / "bin" / tree_version() / ("sw.exe" if os.name == "nt" else "sw")
    target.parent.mkdir(parents=True)
    shutil.copy2(sw, target)
    target.chmod(0o755)
    return home


def forget_sw_homes():
    """Delete every cached test home (the process exit does the same)."""
    while _SW_HOMES:
        _, home = _SW_HOMES.popitem()
        shutil.rmtree(home, ignore_errors=True)


atexit.register(forget_sw_homes)


def sw_home():
    """The SPECWRIGHT_HOME holding SPECWRIGHT_SW, made once per process. Skips as `sw not built` without the binary,
    or fails when SPECWRIGHT_REQUIRE_SW=1 (swharness.require_sw)."""
    sw = swharness.require_sw()
    key = str(Path(sw).resolve())
    if key not in _SW_HOMES:
        _SW_HOMES[key] = make_sw_home(sw)
    return _SW_HOMES[key]


def stamp_version(repo):
    """Write the tree's version to <repo>/openspec/.specwright/VERSION and list it in <repo>/.git/info/exclude, so no
    status read of Git, jj or GitButler sees it (A1) and no fixture tree content changes."""
    repo = Path(repo)
    vfile = repo / STAMP
    vfile.parent.mkdir(parents=True, exist_ok=True)
    nl = chr(10)
    vfile.write_bytes((tree_version() + nl).encode("utf-8"))
    dotgit = repo / ".git"
    if not dotgit.exists():
        return
    if dotgit.is_dir():
        exclude = dotgit / "info" / "exclude"
    else:
        # a linked worktree: `.git` is a file, and Git reads the common dir's exclude file
        out = subprocess.run([jjenv.real_git(), "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"],
                             cwd=repo, capture_output=True, check=True).stdout
        exclude = Path(os.fsdecode(out.rstrip(b"\n")))
    exclude.parent.mkdir(parents=True, exist_ok=True)
    text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if STAMP not in text.splitlines():
        prefix = "" if not text or text.endswith(nl) else nl
        exclude.write_bytes((text + prefix + STAMP + nl).encode("utf-8"))


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
        bash_dir = Path(bash).resolve().parent
        # bashexe.bash() is <git>/usr/bin/bash.exe; a GIT_BASH override may name the <git>/bin launcher instead
        git_root = bash_dir.parent.parent if bash_dir.parent.name.lower() == "usr" else bash_dir.parent
        roots.extend((git_root / "usr" / "bin", git_root / "mingw64" / "bin"))
        excluded = {str(Path(shutil.which(name)).parent.resolve()).casefold()
                    for name in exclude_tools if shutil.which(name)}
        excluded.add(str(git_root / "bin").casefold())
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


def bash_run(args, cwd, env=None, shim=None, stamp=True):
    """Run `bash <args>` with a Git-Bash-native PATH (the way VcsTestCase.invoke does); returns the CompletedProcess.
    `env` adds variables (its PATH is ignored); `shim` is a directory put first on PATH; `stamp` writes the
    excluded VERSION into the directories named by --code and --repo."""
    shell_env = bash_path_env(shim)
    shell_env.update({key: value for key, value in (env or {}).items() if key != "PATH"})
    shell_env.setdefault("SPECWRIGHT_HOME", str(sw_home()))
    for flag, value in zip(map(str, args), map(str, args[1:])) if stamp else ():  # the shim resolves sw from --code or --repo
        if flag in ("--code", "--repo") and Path(value).is_dir() and not (Path(value) / STAMP).exists():
            stamp_version(value)
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
        self._stamp(self.repo)

    def _stamp(self, *repos):
        """The shim resolves sw from the code repo's installed VERSION (design D9)."""
        for repo in repos:
            if repo is not None and Path(repo).is_dir() and not (Path(repo) / STAMP).exists():
                stamp_version(repo)

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

    def invoke(self, command, *options, repo=None, role="code", code=None, env=None, expected=0, scripts=None, cwd=None):
        """Run one subcommand; `scripts` names another directory holding vcs.sh and its siblings (default: the tree's); `cwd` is the directory it runs in (default: `repo`)."""
        target = Path(repo or self.repo)
        scripts = Path(scripts) if scripts is not None else SCRIPTS
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
        shell_env.setdefault("SPECWRIGHT_HOME", str(sw_home()))
        self._stamp(target, code)
        result = subprocess.run(
            [jjenv.find_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"', "vcs-test",
             (scripts / "vcs.sh").as_posix(), command, *args, *map(str, options)],
            cwd=cwd or target, env=shell_env, capture_output=True, text=True, encoding="utf-8", errors="surrogateescape")
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
