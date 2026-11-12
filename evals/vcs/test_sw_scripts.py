"""sw vcs reads settings in-process (native-cli-pr-pair D6).

The tests run vcs.sh, the shim, against the tree's sw (SPECWRIGHT_SW=<built sw>, design D9). Each one copies the scripts directory and puts a recording wrapper in front of
`pr-pair.sh`, so it can see whether that script ran. The fence runs in process too: evals/vcs/test_sw_fence.py.

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

# Logs "$0" and the arguments of one call into $PR_PAIR_LOG (one line per call, NUL-free), then runs the real script.
PR_PAIR_WRAPPER = r"""#!/usr/bin/env bash
printf '%s\n' "$0" >> "$PR_PAIR_LOG"
printf 'args:' >> "$PR_PAIR_LOG"
for a in "$@"; do printf '%s|' "$a" >> "$PR_PAIR_LOG"; done
printf '\n' >> "$PR_PAIR_LOG"
exec bash "$(dirname "$0")/pr-pair.real.sh" "$@"
"""


def write_script(path, text):
    with Path(path).open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


class ScriptsCase(VcsTestCase):
    def copy_scripts(self, name="scripts", wrap_pr_pair=False):
        dest = self.root / name
        shutil.copytree(SCRIPTS, dest, ignore=shutil.ignore_patterns("__pycache__"))
        if wrap_pr_pair:
            os.replace(dest / "pr-pair.sh", dest / "pr-pair.real.sh")
            write_script(dest / "pr-pair.sh", PR_PAIR_WRAPPER)
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
    def test_scripts_under_non_utf8_directory_is_not_utf8(self):
        require_jj()
        scratch = Scratch()
        self.addCleanup(scratch.close)
        self.scratch = scratch
        self.shim = gitlog.install(self.root / "shim", real_git=jjenv.real_git(), log_path=self.root / "calls.jsonl")
        repo = scratch.tracked_repo().path
        self.set_settings(repo, "vcs: jj\n")
        name = os.fsdecode(b"scripts-\xff-dir")
        scripts = self.copy_scripts(name, wrap_pr_pair=True)
        log = self.root / "pr-pair.log"
        self.shim.log_path.unlink(missing_ok=True)

        state, result = self.invoke("state", repo=repo, scripts=scripts, env={"PR_PAIR_LOG": log.as_posix()},
                                    expected=1)

        self.assertEqual((state["ok"], state["error"]), (False, "not_utf8"), state)
        self.assertIn("scripts-\\xFF-dir", state["message"])
        self.assertIn("UTF-8 path", state["message"])
        self.assertEqual(self.shim.calls(), [], "no git, jj or but command ran")
        self.assertEqual(self.records(log), [], "no pr-pair.sh process was started")


if __name__ == "__main__":
    unittest.main()
