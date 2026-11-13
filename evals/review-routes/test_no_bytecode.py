"""Installed skills and binary resolution never create adjacent bytecode caches."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals"))
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
import bashexe  # noqa: E402
from vcs_test_support import bash_path_env, stamp_version, sw_home  # noqa: E402


class NoBytecode(unittest.TestCase):
    def test_review_run_select_writes_no_pycache(self):
        tmp = Path(tempfile.mkdtemp(prefix="sw157-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        skills = tmp / "skills"
        review = skills / "specwright-review" / "scripts"
        resolver = skills / "specwright-pr" / "scripts"
        review.mkdir(parents=True)
        resolver.mkdir(parents=True)
        shutil.copy2(ROOT / "skills" / "specwright-review" / "scripts" / "review-run.sh", review / "review-run.sh")
        for name in ("sw-path.sh", "bounded.py"):
            shutil.copy2(ROOT / "skills" / "specwright-pr" / "scripts" / name, resolver / name)
        repo = tmp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        stamp_version(repo)
        (repo / "openspec" / "specwright.yaml").write_text("review:\n  cross_model: false\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}
        env["SPECWRIGHT_HOME"] = str(sw_home())
        env = bash_path_env(environment=env)
        env["VCS_TEST_SEARCH"] = env["PATH"]
        result = subprocess.run([bashexe.bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"',
                                 "review-bytecode", str(review / "review-run.sh"), "select", "--runtime", "claude"],
                                cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["route"], "subagent")
        self.assertEqual(list(skills.rglob("__pycache__")), [])
        self.assertEqual(list(skills.rglob("*.pyc")), [])

    def test_release_remote_tag_read_writes_no_pycache(self):
        tmp = Path(tempfile.mkdtemp(prefix="release-bytecode-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        scripts = tmp / "skills" / "specwright-release" / "scripts"
        scripts.mkdir(parents=True)
        for name in ("release.sh", "bounded.py"):
            shutil.copy2(ROOT / "skills" / "specwright-release" / "scripts" / name, scripts / name)
        repo, origin = tmp / "repo", tmp / "origin.git"
        repo.mkdir()
        def git(*args):
            return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
        git("init", "-q", "-b", "main")
        git("init", "-q", "--bare", str(origin))
        git("config", "user.name", "Bytecode Fixture")
        git("config", "user.email", "fixture@example.invalid")
        git("config", "commit.gpgsign", "false")
        (repo / "VERSION").write_text("0.1.0\n", encoding="utf-8")
        (repo / "openspec").mkdir()
        (repo / "openspec" / "specwright.yaml").write_text(
            "release:\n  enabled: true\n  version_files:\n"
            "    VERSION: '^(\\d+\\.\\d+\\.\\d+)$'\n", encoding="utf-8")
        git("add", "VERSION", "openspec/specwright.yaml")
        git("commit", "-q", "-m", "feat: fixture (#1)")
        git("remote", "add", "origin", str(origin))
        git("push", "-q", "origin", "main")
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}
        env = bash_path_env(environment=env)
        env["VCS_TEST_SEARCH"] = env["PATH"]
        result = subprocess.run(
            [bashexe.bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"',
             "release-bytecode", str(scripts / "release.sh"), "untagged", "--main", "main"],
            cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual(document["tags"], "origin")
        self.assertEqual([entry["version"] for entry in document["untagged"]], ["0.1.0"])
        self.assertEqual(list(scripts.rglob("__pycache__")), [])
        self.assertEqual(list(scripts.rglob("*.pyc")), [])


if __name__ == "__main__":
    unittest.main()
