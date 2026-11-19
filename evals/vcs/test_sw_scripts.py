"""sw vcs reads settings in-process (native-cli-pr-pair D6).

The tests run `sw vcs` directly (evals/swcall.py); no scripts directory is involved. The fence runs in process too:
evals/vcs/test_sw_fence.py.

Run: python -m unittest evals/vcs/test_sw_scripts.py
"""
import json
import os
import sys
import unittest
from pathlib import Path

import gitlog
import jjenv
from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase, sw_run

def write_script(path, text):
    """A script file with LF line endings (test_shim.py writes its fake resolver with it)."""
    with Path(path).open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


class TestSettingsThroughPrPair(VcsTestCase):
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
        state, _ = self.invoke("state", repo=repo)
        # the settings are read in sw, with no pr-pair process
        self.assertEqual(state["backend"], "jj", state)


class TestUnknownBackend(VcsTestCase):
    def setUp(self):
        super().setUp()
        self.shim = gitlog.install(self.root / "shim", real_git=jjenv.real_git(), log_path=self.root / "git-calls.jsonl")

    def test_unknown_backend_stops_as_before(self):
        self.set_settings(self.repo, "vcs: svn\n")
        direct = sw_run(["pr", "vcs", "--code", str(self.repo)], cwd=self.repo, shim=self.shim)
        self.assertEqual(direct.returncode, 1, direct.stdout + direct.stderr)
        expected = json.loads(direct.stdout)
        self.assertEqual(expected["error"], "unknown_vcs")
        head = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()

        state, _ = self.invoke("state", expected=1)

        # D11: `sw pr vcs` and `sw vcs` stop with the same code and prefix
        prefix = "unknown code VCS "
        self.assertTrue(expected["message"].startswith(prefix), expected)
        self.assertEqual(set(state), {"ok", "error", "message"})
        self.assertEqual((state["ok"], state["error"]), (False, "unknown_vcs"))
        self.assertTrue(state["message"].startswith(prefix), state)
        self.assertIn("svn", state["message"])
        self.shim.assert_no_writes()
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), head)


class TestNonUtf8ScriptsDirectory(VcsTestCase):
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
        moved = Path(os.fsdecode(os.path.join(os.fsencode(self.root), b"repo-\xff-dir")))
        os.rename(repo, moved)
        self.shim.log_path.unlink(missing_ok=True)

        # the runtime refuses an argument or directory that is not UTF-8 before sw's code runs (native-cli A1)
        done = sw_run(["vcs", "state", "--repo", moved, "--role", "code"], cwd=moved, shim=self.shim, scratch=scratch, stamp=False)

        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(done.stdout, "")
        self.assertEqual(self.shim.calls(), [], "no git, jj or but command ran")


if __name__ == "__main__":
    unittest.main()
