"""The cached GitButler fixture: a copy still works under `but` at its new path, in isolated app data."""
import json
import unittest

import butenv


class TestButFixture(unittest.TestCase):
    def setUp(self):
        butenv.require_but()

    def test_copied_repo_works_under_but_at_its_new_path(self):
        with butenv.Scratch() as one, butenv.Scratch() as two:
            first = one.tracked_repo()
            second = two.tracked_repo()
            self.assertNotEqual(first.path, second.path)
            for repo in (first, second):
                status = json.loads(repo.but("status", "--json").stdout)
                self.assertEqual(status["stacks"], [])
                repo.but("branch", "new", "feat/x")
                (repo.path / "a.txt").write_text("a\n", encoding="utf-8", newline="\n")
                repo.but("commit", "-b", "feat/x", "-m", "work", "--json", "a.txt")
                repo.but("branch", "delete", "feat/x", "--json")
            self.assertEqual(first.git_run("remote", "get-url", "origin").stdout.strip(), one.origin.as_posix())
            self.assertEqual(second.git_run("config", "--get", "core.autocrlf").stdout.strip(), "false")

    def test_app_data_is_isolated_with_metrics_disabled(self):
        with butenv.Scratch() as scratch:
            repo = scratch.tracked_repo()
            self.assertTrue(str(scratch.app_data).startswith(str(scratch.root)))
            self.assertEqual(repo.env["E2E_TEST_APP_DATA_DIR"], str(scratch.app_data))
            self.assertEqual(repo.env["GIT_CONFIG_NOSYSTEM"], "1")
            self.assertIn("Metrics: disabled", repo.but("config", "metrics").stdout)


if __name__ == "__main__":
    unittest.main()
