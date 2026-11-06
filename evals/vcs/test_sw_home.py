"""The eval helper that lets the vcs suite run the shim against the tree's `sw` (design D9).

One SPECWRIGHT_HOME per test process holds a copy of SPECWRIGHT_SW at .specwright/bin/<tree VERSION>/sw[.exe]. A fixture's
openspec/.specwright/VERSION is written and hidden through .git/info/exclude, so no status read sees it.

Run: python -m unittest evals/vcs/test_sw_home.py
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import butenv
import jjenv
import vcs_test_support as support
from vcs_test_support import ROOT, VcsTestCase

TREE_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
STAMP = "openspec/.specwright/VERSION"


class TestExcludedVersionIsInvisible(VcsTestCase):
    """Assumption A1: Git, jj and GitButler ignore a file that .git/info/exclude lists."""

    def stamp(self, path):
        vfile = Path(path) / "openspec" / ".specwright" / "VERSION"
        vfile.parent.mkdir(parents=True, exist_ok=True)
        vfile.write_text("0.22.0\n", encoding="utf-8")
        exclude = Path(path) / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(STAMP + "\n")

    def test_excluded_version_invisible_to_backends(self):
        with self.subTest("git"):
            self.stamp(self.repo)
            (self.repo / "visible.txt").write_text("x\n", encoding="utf-8")  # control: status does report this
            out = self.git(self.repo, "status", "--porcelain").stdout
            self.assertIn("visible.txt", out)
            self.assertNotIn("VERSION", out)
            self.assertNotIn(".specwright", out)
        with self.subTest("jj"):
            jjenv.require_jj()
            with jjenv.Scratch() as scratch:
                repo = scratch.tracked_repo()
                self.stamp(repo.path)
                (repo.path / "visible.txt").write_text("x\n", encoding="utf-8")
                out = repo.run(jjenv.require_jj(), "status").stdout
                self.assertIn("visible.txt", out)
                self.assertNotIn("VERSION", out)
                self.assertNotIn(".specwright", out)
        with self.subTest("but"):
            butenv.require_but()
            with butenv.Scratch() as scratch:
                repo = scratch.tracked_repo()
                self.stamp(repo.path)
                (repo.path / "visible.txt").write_text("x\n", encoding="utf-8")
                out = repo.but("status", "--json").stdout
                json.loads(out)
                self.assertIn("visible.txt", out)
                self.assertNotIn("VERSION", out)
                self.assertNotIn(".specwright", out)


class TestSwHome(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="swv-home-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fake = self.root / "fake-sw"
        self.fake.write_bytes(b"not a real sw\n")
        self.addCleanup(support.forget_sw_homes)

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items() if k not in ("SPECWRIGHT_SW", "SPECWRIGHT_REQUIRE_SW")}
        env.update(extra)
        return env

    def test_home_holds_a_copy_of_sw_at_the_tree_version(self):
        home = support.make_sw_home(self.fake)
        placed = home / ".specwright" / "bin" / TREE_VERSION / ("sw.exe" if os.name == "nt" else "sw")
        self.assertEqual(placed.read_bytes(), b"not a real sw\n")
        self.assertNotEqual(placed.resolve(), self.fake.resolve())

    def test_one_home_per_process(self):
        with mock.patch.dict(os.environ, self.env(SPECWRIGHT_SW=str(self.fake)), clear=True):
            first = support.sw_home()
            second = support.sw_home()
        self.assertEqual(first, second)
        self.assertTrue(first.is_dir())

    def test_stamp_is_written_and_excluded(self):
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run([jjenv.real_git(), "init", "-q", str(repo)], check=True)
        support.stamp_version(repo)
        support.stamp_version(repo)  # twice: one exclude line
        self.assertEqual((repo / STAMP).read_text(encoding="utf-8").strip(), TREE_VERSION)
        exclude = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
        self.assertEqual(exclude.count(STAMP), 1)
        status = subprocess.run([jjenv.real_git(), "status", "--porcelain", "--untracked-files=all"], cwd=repo,
                                capture_output=True, text=True)
        self.assertEqual(status.stdout, "")

    def test_skips_as_sw_not_built_without_sw(self):
        with mock.patch.dict(os.environ, self.env(), clear=True):
            with self.assertRaises(unittest.SkipTest) as caught:
                support.sw_home()
        self.assertEqual(str(caught.exception), "sw not built")

    def test_fails_without_sw_when_required(self):
        with mock.patch.dict(os.environ, self.env(SPECWRIGHT_REQUIRE_SW="1"), clear=True):
            with self.assertRaises(AssertionError) as caught:
                support.sw_home()
        self.assertIn("SPECWRIGHT_SW", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
