"""Retired script names map to sw commands (native-cli "Retired script names map to sw commands").

A requirement that names `vcs.sh` means `sw vcs`; `bounded.py` and `reviewers.py` mean `sw run --bounded` and
`sw pr reviewers`; a shim's own `sw_missing` and `no_python` stops are never printed. Every call goes through evals/swcall.py.

Needs the binary named by SPECWRIGHT_SW (skips as `sw not built` otherwise).

Run: SPECWRIGHT_SW=<path> python -m unittest evals/cli/test_name_map.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import swcall  # noqa: E402

GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_AUTHOR_NAME": "Name Map", "GIT_AUTHOR_EMAIL": "map@example.invalid",
           "GIT_COMMITTER_NAME": "Name Map", "GIT_COMMITTER_EMAIL": "map@example.invalid"}


class NameMapCase(unittest.TestCase):
    def setUp(self):
        swcall.version()  # skips, or fails under SPECWRIGHT_REQUIRE_SW=1, without the binary
        self.root = Path(tempfile.mkdtemp(prefix="swmap-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.env = {**os.environ, **GIT_ENV}

    def git(self, cwd, *args):
        done = subprocess.run(["git", *args], cwd=cwd, env=self.env, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done.stdout.strip()

    def repo_with_origin(self):
        """A stamped repository on main with a local bare origin that has moved one commit ahead."""
        origin = self.root / "origin.git"
        self.git(self.root, "init", "-q", "--bare", "-b", "main", str(origin))
        repo = self.root / "repo"
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main")
        self.git(repo, "commit", "-q", "--allow-empty", "-m", "initial")
        self.git(repo, "remote", "add", "origin", origin.as_posix())
        self.git(repo, "push", "-q", "-u", "origin", "main")
        side = self.root / "side"
        self.git(self.root, "clone", "-q", origin.as_posix(), str(side))
        self.git(side, "commit", "-q", "--allow-empty", "-m", "ahead")
        self.git(side, "push", "-q", "origin", "HEAD:refs/heads/main")
        swcall.stamp(repo)
        # the stamp is not part of the fixture's content
        exclude = repo / ".git" / "info" / "exclude"
        exclude.write_text(exclude.read_text(encoding="utf-8") + swcall.STAMP + "\n", encoding="utf-8")
        return repo, self.git(side, "rev-parse", "HEAD")


class TestNameMap(NameMapCase):
    def test_fetch_main_prints_ref_through_sw_vcs(self):
        """`vcs.sh fetch-main` prints a `ref` and `commit`: `sw vcs fetch-main` prints the same, under the same rules."""
        repo, head = self.repo_with_origin()
        done = swcall.run(["vcs", "fetch-main", "--repo", repo, "--role", "code"], cwd=repo, env=self.env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        doc = json.loads(done.stdout)
        self.assertEqual((doc["ok"], doc["ref"], doc["commit"]), (True, "origin/main", head), doc)

    def test_python_helpers_map_to_sw_commands(self):
        """`bounded.py` is `sw run --bounded` (runs the command, passes its exit status); `reviewers.py` is `sw pr reviewers`."""
        done = swcall.run(["run", "--bounded", "--", sys.executable, "-c", "import sys; print('ran'); sys.exit(7)"], env=self.env)
        self.assertEqual((done.returncode, done.stdout.strip()), (7, "ran"), done.stdout + done.stderr)
        material = self.root / "material.json"
        material.write_text(json.dumps({
            "viewer": "me", "number": 7, "head_oid": "a" * 40, "checks": {"total": 0, "failing": []}, "comments": [],
            "head_cutoff": "2026-01-01T00:00:00Z", "cfg": {"since": "2026-01-01T00:00:00Z", "now": 1767225720},
            "checks_all": [], "material": {}, "sig_base": "SIG", "attn_base": "ATTN"}), encoding="utf-8")
        done = swcall.run(["pr", "reviewers", "--material", material, "--head", "a" * 40], env=self.env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(json.loads(done.stdout)["reviewers"], [], "no config means no reviewers")

    def test_removed_shim_errors_are_never_printed(self):
        """The shims' `sw_missing` and `no_python` stops do not exist: each refusal below is a native one."""
        repo, _ = self.repo_with_origin()
        empty = self.root / "no-tools"
        empty.mkdir()
        cases = {
            "another version": lambda: (swcall.stamp(repo, "99.0.0"), swcall.run(["vcs", "state", "--repo", repo, "--role", "code"], cwd=repo, env=self.env))[1],
            "no version": lambda: swcall.run(["vcs", "state", "--repo", self.root / "bare", "--role", "code"], cwd=self.root, env=self.env),
            "no python or shell": lambda: swcall.run(["version", "--json"], env={**self.env, "PATH": str(empty)}),
        }
        (self.root / "bare").mkdir()
        for name, call in cases.items():
            with self.subTest(name):
                done = call()
                text = done.stdout + done.stderr
                self.assertNotIn("sw_missing", text)
                self.assertNotIn("no_python", text)
        stopped = cases["another version"]()
        self.assertEqual(json.loads(stopped.stdout)["error"], "sw_mismatch", stopped.stdout)


if __name__ == "__main__":
    unittest.main()
