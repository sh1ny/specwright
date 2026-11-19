"""evals/swcall.py, the helper every suite uses to run `sw` (eval-runner "Suites call sw through one eval helper").

Needs the binary named by SPECWRIGHT_SW (skips as `sw not built` otherwise).

Run: SPECWRIGHT_SW=<path> python -m unittest evals/runner/test_swcall.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import swcall  # noqa: E402


class SwCallTests(unittest.TestCase):
    def setUp(self):
        swcall.version()  # skips, or fails under SPECWRIGHT_REQUIRE_SW=1, without the binary
        self.root = Path(tempfile.mkdtemp(prefix="swcall-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_AUTHOR_NAME": "Call Test", "GIT_AUTHOR_EMAIL": "call@example.invalid",
                    "GIT_COMMITTER_NAME": "Call Test", "GIT_COMMITTER_EMAIL": "call@example.invalid"}
        self.elsewhere = self.root / "elsewhere"  # a directory with no VERSION: the command starts outside the project
        self.elsewhere.mkdir()

    def project(self, name, version=None):
        repo = self.root / name
        repo.mkdir()
        for args in (("init", "-b", "main"), ("commit", "--allow-empty", "-m", "initial")):
            done = subprocess.run(["git", *args], cwd=repo, env=self.env, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        swcall.stamp(repo, version)
        return repo

    def state(self, repo, project):
        return swcall.run(["vcs", "state", "--repo", repo, "--role", "code"], project=project, cwd=self.elsewhere, env=self.env)

    def test_helper_runs_project_command_with_matching_version(self):
        repo = self.project("code")
        reported = json.loads(swcall.run(["version", "--json"]).stdout)["version"]
        self.assertEqual((repo / swcall.STAMP).read_text(encoding="utf-8").strip(), reported, "the fixture's VERSION is the binary's")
        line = swcall.argv(["vcs", "state"], project=repo)
        self.assertEqual(line[1:], ["--project", str(repo), "vcs", "state"], "the helper starts SPECWRIGHT_SW with --project and the list")
        done = self.state(repo, repo)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(json.loads(done.stdout)["ok"], done.stdout)
        # control: the same call with a project of another version is the one the check reads, and stops
        other = self.project("other", "99.0.0")
        done = self.state(repo, other)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(json.loads(done.stdout)["error"], "sw_mismatch", done.stdout)


if __name__ == "__main__":
    unittest.main()
