"""sw vcs output bytes: line separators parse back, a name's bytes round-trip, tool input reaches the tool.

Run through the vcs.sh shim against the tree's sw (design D9)."""

import json
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

    def test_line_separators_parse_back(self):
        name = "a b café.txt"
        self.write(name, "x\n")
        state, result = self.invoke("state")
        self.assertIn(name, state["dirty_paths"])
        # the encoder leaves U+2028 and U+2029 raw: consumers parse documents, they never match their text
        self.assertIn(name, json.loads(result.stdout)["dirty_paths"])

    @unittest.skipUnless(LINUX, "platform: a file name that is not UTF-8 needs a Linux file system")
    def test_non_utf8_name_is_not_utf8(self):
        """A name from `git status -z` that is not UTF-8 stops the document by name (D4), never a U+FFFD look-alike."""
        name = b"a\xff.txt"
        self.write(name, "one\n")
        self.git(self.repo, "add", "--", os.fsdecode(name))
        self.git(self.repo, "commit", "-m", "add the file")
        self.git(self.repo, "checkout", "-b", BRANCH)
        self.write(name, "two\n")
        self.write(b"other.txt", "other\n")

        state, _ = self.invoke("state", expected=1)

        self.assertEqual((state["ok"], state["error"]), (False, "not_utf8"), state)
        self.assertIn("a\\xFF.txt", state["message"])
        self.assertNotIn("\ufffd", state["message"])
        self.assertIn("rename", state["message"])

        # Git commits only the named paths, so naming other files still commits them.
        result, _ = self.invoke("commit", "--branch", BRANCH, "--message-file", self.message(), "--", "other.txt")
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.commit_names(), [b"other.txt"])

    @unittest.skipUnless(LINUX, "platform: a file name that is not UTF-8 needs a Linux file system")
    def test_valid_replacement_char_is_a_character(self):
        """No name in the repo is invalid UTF-8, so a valid U+FFFD in a name is just a character."""
        valid = "a\ufffd.txt"
        self.write(valid, "one\n")
        self.git(self.repo, "add", "--", valid)
        self.git(self.repo, "commit", "-m", "add the file")
        self.git(self.repo, "checkout", "-b", BRANCH)
        self.write(valid, "two\n")

        result, _ = self.invoke("commit", "--branch", BRANCH, "--message-file", self.message(), "--", valid)

        self.assertTrue(result["ok"], result)
        self.assertEqual(self.commit_names(), [valid.encode("utf-8")])
        state, _ = self.invoke("state")
        self.assertEqual(state["dirty_paths"], [])

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

    def jj_walk_fixture(self):
        """A colocated jj repo with a changed `work/small.txt`; returns (repo, head of BRANCH before the commit)."""
        jj = require_jj()
        scratch = Scratch()
        self.addCleanup(scratch.close)
        fixture = scratch.tracked_repo()
        repo = fixture.path
        self.set_settings(repo, "vcs: jj\nmain_branch: main\n")
        fixture.run(jj, "commit", "-m", "fixture settings")
        fixture.run(jj, "bookmark", "set", "main", "-r", "@-")
        fixture.run(jj, "bookmark", "create", BRANCH, "-r", "@-")
        (repo / "work").mkdir()
        (repo / "work" / "small.txt").write_text("changed\n", encoding="utf-8")
        before = self.git(repo, "rev-parse", "refs/heads/" + BRANCH).stdout.strip()
        return repo, before

    @unittest.skipUnless(LINUX, "platform: a file name that is not UTF-8 needs a Linux file system")
    def test_non_utf8_name_in_walk_stops_commit(self):
        """The directory walk lists names itself: a name that is not UTF-8 stops it, shown with U+FFFD."""
        repo, before = self.jj_walk_fixture()
        self.write(b"work/a\xff.txt", "one\n", repo=repo)

        result, _ = self.invoke("commit", "--branch", BRANCH, "--message-file", self.message(), "--", "work",
                                repo=repo, expected=1)

        self.assertEqual(result["error"], "not_utf8", result)
        self.assertIn("work/a\ufffd.txt", result["message"])
        self.assertEqual(self.git(repo, "rev-parse", "refs/heads/" + BRANCH).stdout.strip(), before)

    @unittest.skipUnless(LINUX, "platform: a file name that is not UTF-8 needs a Linux file system")
    def test_non_utf8_lookalike_in_walk_stops_commit(self):
        """A raw `a\\xff.txt` over the snapshot size limit beside a valid `a\ufffd.txt` must not pass as the small file."""
        repo, before = self.jj_walk_fixture()
        self.write(b"work/a\xff.txt", "x" * (2 * 1024 * 1024), repo=repo)
        self.write("work/a\ufffd.txt", "small\n", repo=repo)

        result, _ = self.invoke("commit", "--branch", BRANCH, "--message-file", self.message(), "--", "work",
                                repo=repo, expected=1)

        self.assertEqual(result["error"], "not_utf8", result)
        self.assertIn("work/a\ufffd.txt", result["message"])
        self.assertEqual(self.git(repo, "rev-parse", "refs/heads/" + BRANCH).stdout.strip(), before)


if __name__ == "__main__":
    unittest.main()
