"""`sw` starts no shell and no POSIX utility for its own work (native-cli-launcher: native-cli).

Each test runs the ported commands (`sw vcs` state, fetch-main, commit and push, `sw finish undo-archive-plan`, `sw commit`
task-cover and fit-subject, and a `sw pr` workflow command) twice from the same fixtures: once as they are, and once with
recording fakes first on PATH that exit 1. The recorded run must give the same result as the plain one, and no recorder may
have run. A probe first runs every recorder directly, so that an empty log means nothing started rather than that a recorder
cannot record.

Needs the binary named by SPECWRIGHT_SW (skips as `sw not built` otherwise; fails under SPECWRIGHT_REQUIRE_SW=1).
On Windows the recorders are `.cmd` files: only a PATHEXT name starts there (native-cli-launcher D9).

Run: SPECWRIGHT_SW=<path> python -m unittest evals/cli/test_no_shell.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS = HERE.parent
ROOT = EVALS.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EVALS))
import bashexe  # noqa: E402
import fakeexe  # noqa: E402
import swharness  # noqa: E402

_spec = importlib.util.spec_from_file_location("finish_fixtures", EVALS / "finish" / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

SHELLS = ("bash", "sh")  # bare-bash: not started (recorder names)
UTILITIES = ("mktemp", "ln", "sleep", "date", "getconf", "pwd", "cygpath")
LOG = "SW_NO_SHELL_LOG"
SCRIPTS = (ROOT / "skills" / "specwright-pr" / "scripts").resolve().as_posix()
SLUG = "o/code"
BRANCH = "feat/x"


def write_recorders(directory, names):
    """A recording fake for each of `names` in `directory`: it appends its name to $SW_NO_SHELL_LOG and exits 1."""
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        if os.name == "nt":
            text = '@echo %s>>"%%%s%%"\r\n@exit /b 1\r\n' % (name, LOG)
            (directory / (name + ".cmd")).write_bytes(text.encode("ascii"))
        else:
            path = directory / name
            path.write_bytes(('#!/bin/sh\nprintf "%%s\\n" %s >> "$%s"\nexit 1\n' % (name, LOG)).encode("ascii"))
            path.chmod(0o755)
    return directory


def recorder_command(directory, name):
    return str(directory / (name + ".cmd" if os.name == "nt" else name))


def git(repo, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
               GIT_AUTHOR_NAME="No Shell", GIT_AUTHOR_EMAIL="no-shell@example.invalid",
               GIT_COMMITTER_NAME="No Shell", GIT_COMMITTER_EMAIL="no-shell@example.invalid")
    done = subprocess.run([shutil.which("git"), *map(str, args)], cwd=repo, env=env, capture_output=True, text=True)
    if done.returncode != 0:
        raise AssertionError("git %s: %s%s" % (" ".join(map(str, args)), done.stdout, done.stderr))
    return done.stdout.strip()


# A fake gh for `sw pr discover`: a token for `auth token`, no pull requests for the pulls list, and no other call.
GH = '''import json, sys
args = sys.argv[1:]
if args[:2] == ["auth", "token"]:
    print("tok-me")
elif args[:1] == ["api"] and "/pulls" in " ".join(args):
    print("[]")
else:
    sys.stderr.write("fake gh: unexpected call %r\\n" % (args,))
    sys.exit(9)
'''


class NoShell(unittest.TestCase):
    def setUp(self):
        self.sw = swharness.require_sw()
        self.temp = tempfile.TemporaryDirectory(prefix="sw-no-shell-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "recorders.log"
        self.real_bash = bashexe.bash()
        self.assertTrue(self.real_bash, "the fixtures need bash")
        self.build_finish_repo()
        self.gh_dir = self.root / "gh-bin"
        self.gh_dir.mkdir()
        fakeexe.write_python_fake(self.gh_dir / "gh", GH)

    # ---- fixtures ---------------------------------------------------------------------------------------------
    def build_code_repo(self, tag):
        """A clone of a bare origin on `feat/x`, one commit ahead of `main`, with `tasks.md` in a `docs(...)` commit.
        Each pass gets its own, so the writing commands run on the same state in both."""
        base = self.root / tag
        base.mkdir()
        origin = base / "origin.git"
        subprocess.run([shutil.which("git"), "init", "-q", "--bare", "-b", "main", str(origin)], check=True,
                       env=dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1"))
        self.code = base / "code"
        self.code.mkdir()
        git(self.code, "init", "-q", "-b", "main")
        (self.code / "base.txt").write_text("base\n", encoding="utf-8")
        (self.code / "openspec").mkdir()
        (self.code / "openspec" / "specwright.yaml").write_text("vcs: git\nmain_branch: main\n", encoding="utf-8")
        git(self.code, "add", "-A")
        git(self.code, "commit", "-q", "-m", "initial")
        git(self.code, "remote", "add", "origin", str(origin))
        git(self.code, "push", "-q", "-u", "origin", "main")
        git(self.code, "checkout", "-q", "-b", BRANCH)
        (self.code / "tasks.md").write_text("# Tasks\n\n- [ ] 1.1 do it\n- [ ] 1.2 and that\n", encoding="utf-8")
        (self.code / "done.txt").write_text("done\n", encoding="utf-8")
        git(self.code, "add", "-A")
        git(self.code, "commit", "-q", "-m", "feat(x): task 1.1 do it\n\nSpecwright-Task: 1.1")
        self.origin = origin
        (self.code / "new.txt").write_text("new\n", encoding="utf-8")
        self.message = base / "message.txt"
        self.message.write_text("feat(x): named commit\n", encoding="utf-8")
        self.long_message = base / "long-message.txt"
        self.long_message.write_text("feat(x): task 1.2 " + "and so on " * 12 + "\n\nbody\n", encoding="utf-8")

    def build_finish_repo(self):
        self.finish_root = self.root / "finish"
        self.finish_root.mkdir()
        self.work = fx.make_repo(self.finish_root)
        fx.git(self.work, "checkout", "-q", "-b", "bugfix/add-x")
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True, marker=True)

    # ---- running ----------------------------------------------------------------------------------------------
    def env(self, front=None):
        """The fixture environment; `front` (a directory) first on PATH, then the fake gh, then the host's PATH."""
        env = swharness.fixture_env()
        env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
                    "GIT_AUTHOR_NAME": "No Shell", "GIT_AUTHOR_EMAIL": "no-shell@example.invalid",
                    "GIT_COMMITTER_NAME": "No Shell", "GIT_COMMITTER_EMAIL": "no-shell@example.invalid",
                    "SPECWRIGHT_HOME": str(self.root / "home"), "SPECWRIGHT_STATE_DIR": str(self.root / "state"),
                    LOG: self.log.resolve().as_posix(), "TMPDIR": str(self.root), "TEMP": str(self.root),
                    "TMP": str(self.root)})
        env["GH_TOKEN"] = "tok-me"
        parts = ([str(front)] if front else []) + [str(self.gh_dir), env.get("PATH", "")]
        env["PATH"] = os.pathsep.join(parts)
        return env

    def sw_handoff(self, command, bash, records, cwd, env):
        payload = b"".join(str(x).encode("utf-8") + b"\0" for x in [SCRIPTS, bash, *records])
        done = subprocess.run([self.sw, *command, "--args-stdin"], input=payload, cwd=str(cwd), env=env,
                              capture_output=True, timeout=180)
        return done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace")

    def ported_commands(self, front, bash, tag):
        """Run every ported command once on a fresh code repo; returns {name: (exit code, stdout, stderr)}. `front` is
        first on PATH and `bash` is the shell the handoff names."""
        self.build_code_repo(tag)
        env = self.env(front)
        code = self.code.resolve().as_posix()
        out = {}
        vcs = ["--repo", code, "--role", "code"]
        out["vcs state"] = self.sw_handoff(["vcs"], bash, ["state", *vcs], self.code, env)
        out["vcs fetch-main"] = self.sw_handoff(["vcs"], bash, ["fetch-main", *vcs, "--no-tags"], self.code, env)
        out["commit task-cover"] = self.sw_handoff(
            ["commit"], bash, ["task-cover", "--repo", code, "--range", "main..HEAD", "--tasks",
                               (self.code / "tasks.md").resolve().as_posix(), "--change", "x"], self.code, env)
        out["commit fit-subject"] = self.sw_handoff(
            ["commit"], bash, ["fit-subject", self.long_message.resolve().as_posix()], self.code, env)
        out["finish undo-archive-plan"] = self.sw_handoff(
            ["finish"], bash, fx.plan_args("add-x", dir_=self.work.resolve().as_posix()), self.work, env)
        out["pr discover"] = self.sw_handoff(
            ["pr", "discover"], bash, ["discover", "--repo", SLUG, "--branch", BRANCH], self.code, env)
        if os.name == "nt":
            # an MSYS path argument: sw converts it itself (no cygpath)
            drive = self.long_message.resolve().as_posix()
            msys = "/" + drive[0].lower() + drive[2:]
            out["commit fit-subject (MSYS path)"] = self.sw_handoff(
                ["commit"], bash, ["fit-subject", msys], self.code, env)
        # the two writing commands run last, on the same branch
        out["vcs commit"] = self.sw_handoff(
            ["vcs"], bash, ["commit", *vcs, "--branch", BRANCH, "--message-file", self.message.resolve().as_posix(),
                            "--", "new.txt"], self.code, env)
        out["vcs push"] = self.sw_handoff(["vcs"], bash, ["push", *vcs, "--branch", BRANCH], self.code, env)
        return out

    def probe(self, directory, names):
        """Run each recorder directly: it must record its name and exit 1, so a clean log later means nothing ran it."""
        self.log.unlink(missing_ok=True)
        env = dict(os.environ, **{LOG: self.log.resolve().as_posix()})
        for i, name in enumerate(names, 1):
            done = subprocess.run([recorder_command(directory, name)], env=env, capture_output=True, timeout=30)
            self.assertEqual(done.returncode, 1, "%s: %r" % (name, done.stderr))
            self.assertEqual(self.log.read_text(encoding="utf-8").split(), list(names[:i]),
                             "the %s recorder did not record its run" % name)
        self.log.unlink()

    def assert_same_as_plain(self, front, bash):
        """The ported commands with recorders first give what they give without them, and no recorder ran."""
        plain = self.ported_commands(None, self.real_bash, "plain")
        self.assertFalse(self.log.exists())
        got = self.ported_commands(front, bash, "recorded")
        recorded = self.log.read_text(encoding="utf-8").split() if self.log.exists() else []
        self.assertEqual(recorded, [], "recorders ran: %r" % recorded)
        self.assertEqual(set(got), set(plain))
        for name, (code, stdout, stderr) in got.items():
            with self.subTest(command=name):
                self.assertEqual(code, 0, (stdout, stderr))
                self.assertEqual(plain[name][0], 0, plain[name])
                if name in ("vcs commit", "vcs push", "vcs fetch-main", "vcs state"):
                    # these hold the fixture's own paths and commit ids, which differ between the two repos
                    self.assertTrue(json.loads(stdout)["ok"], stdout)
                    self.assertEqual(sorted(json.loads(stdout)), sorted(json.loads(plain[name][1])))
                elif name.startswith("commit task-cover"):
                    self.assertEqual(sorted(json.loads(stdout)), sorted(json.loads(plain[name][1])))
                else:
                    self.assertEqual(stdout, plain[name][1])
                self.assertEqual(stderr, plain[name][2])

    # ---- the tests --------------------------------------------------------------------------------------------
    def test_ported_commands_with_failing_shells_first(self):
        shells = write_recorders(self.root / "failing-shells", SHELLS)
        self.probe(shells, SHELLS)
        self.assert_same_as_plain(shells, recorder_command(shells, "bash"))

    def test_failing_utilities_first_on_path(self):
        utilities = write_recorders(self.root / "failing-utilities", UTILITIES)
        self.probe(utilities, UTILITIES)
        self.assert_same_as_plain(utilities, self.real_bash)


if __name__ == "__main__":
    unittest.main()
