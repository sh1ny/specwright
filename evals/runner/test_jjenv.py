"""Missing-jj policy for tests which exercise real colocated repositories."""
import os
import unittest
from unittest import mock

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "evals"))
from vcs import jjenv  # noqa: E402


class TestJjMissing(unittest.TestCase):
    def without_jj(self, required=None):
        env = {"PATH": ""}
        if required is not None:
            env["SPECWRIGHT_REQUIRE_JJ"] = required
        else:
            env.pop("SPECWRIGHT_REQUIRE_JJ", None)
        return mock.patch.dict(os.environ, env, clear=True)

    def test_jj_missing_skips_with_reason(self):
        with self.without_jj():
            with self.assertRaises(unittest.SkipTest) as caught:
                jjenv.require_jj()
        self.assertEqual(str(caught.exception), "jj not installed")

    def test_jj_missing_required_fails(self):
        with self.without_jj("1"):
            with self.assertRaises(AssertionError) as caught:
                jjenv.require_jj()
        self.assertIn("jj", str(caught.exception).lower())
        self.assertIn("not installed", str(caught.exception).lower())


class TestJjIdentity(unittest.TestCase):
    def test_fixture_ignores_the_users_jj_config(self):
        """A CI runner has no jj user config: the fixture sets its own, so a jj commit has an author there too, and jj's
        own Git calls go to the real git, past a test's logging shim (jj 0.46 never reads .jj/repo/config.toml)."""
        with mock.patch.dict(os.environ, {"JJ_CONFIG": "/elsewhere/config.toml", "JJ_USER": "Someone"}):
            with jjenv.Scratch() as scratch:
                self.assertEqual(Path(scratch.env["JJ_CONFIG"]).parent, scratch.root)
                self.assertEqual(scratch.env["JJ_USER"], jjenv.FIXTURE_NAME)
                self.assertEqual(scratch.env["JJ_EMAIL"], jjenv.FIXTURE_EMAIL)
                repo = scratch.tracked_repo()
                jj = jjenv.require_jj()
                executable = repo.run(jj, "config", "get", "git.executable-path").stdout.strip()
                self.assertEqual(Path(executable), Path(jjenv.real_git()))
                (repo.path / "work.txt").write_text("work\n", encoding="utf-8")
                repo.run(jj, "commit", "-m", "work")
                author = repo.run(jj, "log", "--no-graph", "-r", "@-", "-T", 'author.name() ++ "|" ++ author.email()').stdout
        self.assertEqual(author, "%s|%s" % (jjenv.FIXTURE_NAME, jjenv.FIXTURE_EMAIL))


if __name__ == "__main__":
    unittest.main()
