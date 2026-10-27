"""Tests for evals/fixturecache.py: build a fixture repo once per process, hand out independent copies.

Run: python -m unittest discover evals/runner
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import fixturecache  # noqa: E402

ENV = {
    "GIT_AUTHOR_NAME": "Eval Bot", "GIT_AUTHOR_EMAIL": "eval@example.invalid",
    "GIT_COMMITTER_NAME": "Eval Bot", "GIT_COMMITTER_EMAIL": "eval@example.invalid",
    "GIT_AUTHOR_DATE": "2026-10-19T12:00:00+00:00", "GIT_COMMITTER_DATE": "2026-10-19T12:00:00+00:00",
}


def git(repo, *args):
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, **ENV})
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr}")
    return r.stdout.strip()


def build_repo(dest):
    """A small two-commit repo with a tag and a side branch; same SHAs on every run (pinned env)."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    git(dest, "init", "-q", "-b", "main")
    (dest / "a.txt").write_text("one\n", encoding="utf-8")
    (dest / "sub").mkdir()
    (dest / "sub" / "b.txt").write_text("two\n", encoding="utf-8")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "first")
    git(dest, "branch", "side")
    git(dest, "tag", "v1")
    (dest / "a.txt").write_text("one\nmore\n", encoding="utf-8")
    git(dest, "commit", "-q", "-am", "second")


def snapshot(repo):
    return {
        "refs": git(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
        "head": git(repo, "rev-parse", "HEAD"),
        "log": git(repo, "log", "--all", "--format=%H %T"),
    }


def tree(repo):
    repo = Path(repo)
    return sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*") if ".git" not in p.relative_to(repo).parts)


class FixtureCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-fixturecache-test-"))
        self.addCleanup(fixturecache._rmtree, self.tmp)

    def test_copies_are_independent(self):
        key = ("independent", 1)
        one = fixturecache.copy(key, build_repo, self.tmp / "one")
        two = fixturecache.copy(key, build_repo, self.tmp / "two")
        cached = fixturecache.cached(key, build_repo)
        before = snapshot(cached)
        self.assertEqual(snapshot(one), before)
        self.assertEqual(snapshot(two), before)

        (one / "c.txt").write_text("new\n", encoding="utf-8")
        git(one, "add", "-A")
        git(one, "commit", "-q", "-m", "third")
        git(one, "tag", "v2")
        git(one, "branch", "-D", "side")

        self.assertNotEqual(snapshot(one), before)
        self.assertEqual(snapshot(two), before)
        self.assertEqual(snapshot(cached), before)
        self.assertFalse((two / "c.txt").exists())
        self.assertFalse((cached / "c.txt").exists())
        self.assertIn("side", git(two, "branch", "--list"))

    def test_failed_build_leaves_key_missing_and_rebuilds(self):
        key = ("failing", 1)
        seen = []

        def bad(dest):
            seen.append(Path(dest))
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest) / "partial.txt").write_text("half", encoding="utf-8")
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            fixturecache.cached(key, bad)
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].exists())

        with self.assertRaises(ValueError):  # key is missing, so the builder runs again
            fixturecache.cached(key, bad)
        self.assertEqual(len(seen), 2)

        path = fixturecache.cached(key, build_repo)
        self.assertTrue((path / "a.txt").is_file())

    def test_cache_equals_direct_build(self):
        direct = self.tmp / "direct"
        build_repo(direct)
        via = fixturecache.copy(("equiv", 1), build_repo, self.tmp / "via")
        self.assertEqual(git(via, "log", "--all", "--format=%H %T"), git(direct, "log", "--all", "--format=%H %T"))
        self.assertEqual(tree(via), tree(direct))
        self.assertEqual(git(via, "status", "--porcelain"), "")
        self.assertEqual(git(direct, "status", "--porcelain"), "")

    def test_builds_once_per_key(self):
        calls = []

        def build(dest):
            calls.append(1)
            build_repo(dest)

        a = fixturecache.cached(("once", 1), build)
        b = fixturecache.cached(("once", 1), build)
        self.assertEqual(a, b)
        self.assertEqual(len(calls), 1)
        fixturecache.cached(("once", 2), build)
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
