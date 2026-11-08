"""sw vcs reads settings in-process (native-cli-pr-pair D6) and fences identity through the scripts of the vcs.sh that started it (design D2, S2).

The tests run vcs.sh, the shim, against the tree's sw (SPECWRIGHT_SW=<built sw>, design D9). Each one copies the scripts directory and puts a recording wrapper in front of
`pr-pair.sh` or `as.sh`, so it can see which script ran, from where and with which arguments.

Run: python -m unittest evals/vcs/test_sw_scripts.py
"""
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

import gitlog
import jjenv
from jjenv import Scratch, require_jj
from vcs_test_support import SCRIPTS, VcsTestCase, bash_path_env, bash_run

GITHUB = "https://github.com/o/r.git"
LOGIN = "KintsugiBot"

# Logs "$0" and the arguments of one call into $PR_PAIR_LOG (one line per call, NUL-free), then runs the real script.
PR_PAIR_WRAPPER = r"""#!/usr/bin/env bash
printf '%s\n' "$0" >> "$PR_PAIR_LOG"
printf 'args:' >> "$PR_PAIR_LOG"
for a in "$@"; do printf '%s|' "$a" >> "$PR_PAIR_LOG"; done
printf '\n' >> "$PR_PAIR_LOG"
exec bash "$(dirname "$0")/pr-pair.real.sh" "$@"
"""

# A stand-in for the fence: it records its arguments, answers --resolve, can refuse, and otherwise runs the command.
AS_WRAPPER = r"""#!/usr/bin/env bash
for a in "$@"; do printf '%s|' "$a" >> "$AS_LOG"; done
printf '\n' >> "$AS_LOG"
if [ "${1:-}" = --resolve ]; then
  if [ -n "${AS_REFUSE_RESOLVE:-}" ]; then echo "as.sh: no active github.com account" >&2; exit 3; fi
  echo "${AS_RESOLVED:-resolved-bot}"
  exit 0
fi
if [ -n "${AS_REFUSE:-}" ]; then echo "as.sh: no credential for $1" >&2; exit 3; fi
shift
exec "$@"
"""


def write_script(path, text):
    with Path(path).open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


class ScriptsCase(VcsTestCase):
    def copy_scripts(self, name="scripts", wrap_pr_pair=False, wrap_as=False):
        dest = self.root / name
        shutil.copytree(SCRIPTS, dest, ignore=shutil.ignore_patterns("__pycache__"))
        if wrap_pr_pair:
            os.replace(dest / "pr-pair.sh", dest / "pr-pair.real.sh")
            write_script(dest / "pr-pair.sh", PR_PAIR_WRAPPER)
        if wrap_as:
            write_script(dest / "as.sh", AS_WRAPPER)
        return dest

    @staticmethod
    def records(log_path):
        path = Path(log_path)
        return path.read_bytes().decode("utf-8", "surrogateescape").splitlines() if path.exists() else []


class TestSettingsThroughPrPair(ScriptsCase):
    def jj_repo(self, settings="vcs: jj\n"):
        require_jj()
        scratch = Scratch()
        self.addCleanup(scratch.close)
        self.scratch = scratch
        repo = scratch.tracked_repo().path
        self.set_settings(repo, settings)
        return repo

    def test_settings_read_through_pr_pair(self):
        repo = self.jj_repo()
        scripts = self.copy_scripts(wrap_pr_pair=True)
        log = self.root / "pr-pair.log"
        state, _ = self.invoke("state", repo=repo, scripts=scripts, env={"PR_PAIR_LOG": log.as_posix()})
        # the same rules run in sw: the backend is the one `pr-pair.sh vcs` reports, and no pr-pair.sh process started
        self.assertEqual(state["backend"], "jj", state)
        self.assertEqual(self.records(log), [], "no pr-pair.sh process was started")


class TestUnknownBackend(ScriptsCase):
    def setUp(self):
        super().setUp()
        self.shim = gitlog.install(self.root / "shim", real_git=jjenv.real_git(), log_path=self.root / "git-calls.jsonl")
        self.env = {**self.shim.env, **bash_path_env(self.shim.path)}

    def test_unknown_backend_stops_as_before(self):
        self.set_settings(self.repo, "vcs: svn\n")
        direct = bash_run([(SCRIPTS / "pr-pair.sh").as_posix(), "vcs", "--code", str(self.repo)], cwd=self.repo)
        self.assertEqual(direct.returncode, 1, direct.stdout + direct.stderr)
        expected = json.loads(direct.stdout)
        self.assertEqual(expected["error"], "unknown_vcs")
        head = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()

        state, _ = self.invoke("state", expected=1)

        # D11: the error code and the prefix are the script's; the words after it are sw's own
        prefix = "unknown code VCS "
        self.assertTrue(expected["message"].startswith(prefix), expected)
        self.assertEqual(set(state), {"ok", "error", "message"})
        self.assertEqual((state["ok"], state["error"]), (False, "unknown_vcs"))
        self.assertTrue(state["message"].startswith(prefix), state)
        self.assertIn("svn", state["message"])
        self.shim.assert_no_writes()
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), head)


class TestNonUtf8ScriptsDirectory(ScriptsCase):
    @unittest.skipUnless(sys.platform.startswith("linux"),
                         "platform: a directory name holding the byte 0xFF needs a Linux filesystem (macOS and Windows reject it)")
    def test_scripts_under_non_utf8_directory(self):
        require_jj()
        scratch = Scratch()
        self.addCleanup(scratch.close)
        repo = scratch.tracked_repo().path
        self.set_settings(repo, "vcs: jj\n")
        name = os.fsdecode(b"scripts-\xff-dir")
        scripts = self.copy_scripts(name, wrap_pr_pair=True)
        log = self.root / "pr-pair.log"

        state, result = self.invoke("state", repo=repo, scripts=scripts, env={"PR_PAIR_LOG": log.as_posix()})

        self.assertEqual(result.returncode, 0)
        self.assertEqual(state["backend"], "jj", state)


class TestFencedPush(ScriptsCase):
    def setUp(self):
        super().setUp()
        self.set_settings(self.repo, "main_branch: main\n")
        self.shim = gitlog.install(self.root / "shim", real_git=jjenv.real_git(), log_path=self.root / "git-calls.jsonl")
        self.env = {**self.shim.env, **bash_path_env(self.shim.path)}
        self.origin = self.root / "origin.git"
        self.git(self.root, "init", "--bare", str(self.origin))
        self.git(self.root, "--git-dir", str(self.origin), "symbolic-ref", "HEAD", "refs/heads/main")
        # origin is github.com to Specwright (so it fences through as.sh) and the local bare repo to Git: insteadOf
        # rewrites every push, and the logging shim answers `git remote get-url origin` (which would expand the rewrite).
        self.git(self.repo, "remote", "add", "origin", GITHUB)
        self.git(self.repo, "config", "url.%s.insteadOf" % self.origin.as_posix(), GITHUB)
        script = self.shim.path / "git"
        text = script.read_text(encoding="utf-8").replace("\r\n", "\n")
        answer = 'if [ "$*" = "remote get-url origin" ]; then echo "%s"; exit 0; fi\n' % GITHUB
        write_script(script, text.replace('exec "$SPECWRIGHT_REAL_GIT" "$@"', answer + 'exec "$SPECWRIGHT_REAL_GIT" "$@"'))
        self.git(self.repo, "checkout", "-b", "feat/a")
        self.scripts = self.copy_scripts(wrap_as=True)
        self.as_log = self.root / "as.log"

    def origin_branches(self):
        out = self.git(self.origin, "for-each-ref", "--format=%(refname)", "refs/heads").stdout
        return out.split()

    def push(self, *options, env=None, expected=0):
        return self.invoke("push", "--branch", "feat/a", *options, scripts=self.scripts,
                           env={"AS_LOG": self.as_log.as_posix(), **(env or {})}, expected=expected)

    def test_fenced_push_runs_through_as_sh(self):
        with self.subTest("the push runs as the login"):
            done, _ = self.push("--login", LOGIN)
            self.assertEqual(done, {"ok": True, "backend": "git", "branch": "feat/a"})
            self.assertEqual(self.records(self.as_log), ["|".join([LOGIN, "git", "push", "-u", "origin", "HEAD"]) + "|"])
            self.assertEqual(self.origin_branches(), ["refs/heads/feat/a"])
        self.git(self.origin, "update-ref", "-d", "refs/heads/feat/a")
        self.as_log.unlink(missing_ok=True)
        with self.subTest("a refused fence exits 3 and pushes nothing"):
            refused, _ = self.push("--login", LOGIN, env={"AS_REFUSE": "1"}, expected=3)
            self.assertEqual(refused["error"], "fence_failed")
            self.assertEqual(refused["message"], "as.sh: no credential for " + LOGIN)
            self.assertEqual(self.origin_branches(), [])
        self.as_log.unlink(missing_ok=True)
        with self.subTest("no login resolves one first"):
            done, _ = self.push(env={"AS_RESOLVED": "pinned-bot"})
            self.assertTrue(done["ok"], done)
            self.assertEqual(self.records(self.as_log), ["--resolve|", "|".join(["pinned-bot", "git", "push", "-u", "origin", "HEAD"]) + "|"])
        self.git(self.origin, "update-ref", "-d", "refs/heads/feat/a")
        self.as_log.unlink(missing_ok=True)
        with self.subTest("a refused resolve exits 3 and pushes nothing"):
            refused, _ = self.push(env={"AS_REFUSE_RESOLVE": "1"}, expected=3)
            self.assertEqual(refused["error"], "fence_failed")
            self.assertEqual(refused["message"], "as.sh: no active github.com account")
            self.assertEqual(self.records(self.as_log), ["--resolve|"])
            self.assertEqual(self.origin_branches(), [])


if __name__ == "__main__":
    unittest.main()
