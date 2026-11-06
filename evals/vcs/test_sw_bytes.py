"""sw vcs output bytes: separators stay escaped, a name's bytes round-trip, tool input reaches the tool.

Written for the harness switch (SPECWRIGHT_VCS_VIA_SW=1); the shim makes it permanent."""

import os
import subprocess
import sys
import unittest

import jjenv
from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase

LINUX = sys.platform.startswith("linux")
BRANCH = "feat/bytes"


class TestSwBytes(VcsTestCase):
    def write(self, name, text, repo=None):
        """Write a file whose name is `name` (str, or bytes for a name that is not UTF-8)."""
        root = os.fsencode(repo or self.repo)
        with open(os.path.join(root, os.fsencode(name)), "wb") as stream:
            stream.write(text.encode("utf-8"))

    def commit_names(self, rev="HEAD"):
        out = subprocess.run([jjenv.real_git(), "show", "--format=", "--name-only", "-z", rev], cwd=self.repo,
                             capture_output=True, check=True).stdout
        return [name for name in out.split(b"\0") if name]

    def message(self):
        path = self.root / "message.txt"
        path.write_text("feat(bytes): name\n", encoding="utf-8")
        return path

    def test_line_separators_stay_escaped(self):
        name = "a\u2028b\u2029caf\u00e9.txt"
        self.write(name, "x\n")
        state, result = self.invoke("state")
        self.assertIn(name, state["dirty_paths"])
        self.assertIn("a" + chr(92) + "u2028b" + chr(92) + "u2029caf" + chr(233) + ".txt", result.stdout)
        self.assertNotIn(chr(0x2028), result.stdout)
        self.assertNotIn(chr(0x2029), result.stdout)

    @unittest.skipUnless(LINUX, "platform: a file name that is not UTF-8 needs a Linux file system")
    def test_non_utf8_name_round_trips(self):
        name = b"a\xff.txt"
        self.write(name, "one\n")
        self.git(self.repo, "add", "--", os.fsdecode(name))
        self.git(self.repo, "commit", "-m", "add the file")
        self.git(self.repo, "checkout", "-b", BRANCH)
        self.write(name, "two\n")

        state, _ = self.invoke("state")
        self.assertEqual(state["dirty_paths"], [os.fsdecode(name)])

        result, _ = self.invoke("commit", "--branch", BRANCH, "--message-file", self.message(),
                                "--", state["dirty_paths"][0])
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.commit_names(), [name])

    @unittest.skipUnless(LINUX, "platform: a file name that is not UTF-8 needs a Linux file system")
    def test_valid_replacement_char_is_a_character(self):
        valid, other = "a\ufffd.txt", b"a\xff.txt"
        self.write(valid, "one\n")
        self.write(other, "one\n")
        self.git(self.repo, "add", "--", valid, os.fsdecode(other))
        self.git(self.repo, "commit", "-m", "add both files")
        self.git(self.repo, "checkout", "-b", BRANCH)
        self.write(valid, "two\n")
        self.write(other, "two\n")

        result, _ = self.invoke("commit", "--branch", BRANCH, "--message-file", self.message(), "--", valid)

        self.assertTrue(result["ok"], result)
        self.assertEqual(self.commit_names(), [valid.encode("utf-8")])
        state, _ = self.invoke("state")
        self.assertEqual(state["dirty_paths"], [os.fsdecode(other)])

    @unittest.skipUnless(os.name == "nt", "platform: the check-ignore input travels the Windows transport")
    def test_check_ignore_receives_oversized_name(self):
        """An ignored file over snapshot.max-new-file-size in a named directory must not stop the jj commit: that
        needs `git check-ignore -z --stdin` to be told its name."""
        jj = require_jj()
        scratch = Scratch()
        self.addCleanup(scratch.close)
        fixture = scratch.tracked_repo()
        repo = fixture.path
        self.set_settings(repo, "vcs: jj\nmain_branch: main\n")
        (repo / ".gitignore").write_text("*.bin\n", encoding="utf-8")
        fixture.run(jj, "commit", "-m", "fixture settings")
        fixture.run(jj, "bookmark", "set", "main", "-r", "@-")
        fixture.run(jj, "bookmark", "create", BRANCH, "-r", "@-")
        work = repo / "work"
        work.mkdir()
        (work / "small.txt").write_text("changed\n", encoding="utf-8")
        (work / "big.bin").write_bytes(b"x" * (2 * 1024 * 1024))

        result, _ = self.invoke("commit", "--branch", BRANCH, "--message-file", self.message(), "--", "work",
                                repo=repo)

        self.assertTrue(result["ok"], result)
        names = self.git(repo, "ls-tree", "-r", "--name-only", "refs/heads/" + BRANCH).stdout.split()
        self.assertIn("work/small.txt", names)
        self.assertNotIn("work/big.bin", names)


if __name__ == "__main__":
    unittest.main()
