"""The pr-pair settings interface chooses code and planning-store VCS independently."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "specwright-pr" / "scripts" / "pr-pair.sh"


class TestVcsSettings(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.code = Path(self.temp.name) / "code"
        (self.code / "openspec").mkdir(parents=True)

    def set_settings(self, text):
        (self.code / "openspec" / "specwright.yaml").write_text(text, encoding="utf-8")

    def bash(self):
        if os.name != "nt":
            return shutil.which("bash")
        candidates = [
            os.environ.get("GIT_BASH"),
            str(Path(os.environ["SCOOP"]) / "apps" / "git" / "current" / "bin" / "bash.exe")
            if os.environ.get("SCOOP") else None,
            str(Path(os.environ["USERPROFILE"]) / "scoop" / "apps" / "git" / "current" / "bin" / "bash.exe")
            if os.environ.get("USERPROFILE") else None,
        ]
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(variable)
            if root:
                candidates.append(str(Path(root) / "Git" / "bin" / "bash.exe"))
        return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)

    def vcs(self, expected=0):
        bash = self.bash()
        self.assertIsNotNone(bash, "Git Bash is required to run pr-pair.sh on Windows")
        result = subprocess.run(
            [bash, SCRIPT.as_posix(), "vcs", "--code", self.code.as_posix()],
            capture_output=True, text=True, env=os.environ.copy(), cwd=self.code,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_unset_vcs_is_git(self):
        self.set_settings("finish: local\n")
        self.assertEqual(self.vcs(), {"ok": True, "code": "git", "store": "git"})

    def test_store_vcs_not_inherited(self):
        self.set_settings("vcs: jj\nplanning_store: {}\n")
        self.assertEqual(self.vcs(), {"ok": True, "code": "jj", "store": "git"})

    def test_unknown_vcs_stops(self):
        self.set_settings("vcs: hg\n")
        result = self.vcs(expected=1)
        self.assertEqual(result.get("error"), "unknown_vcs")
        self.assertIn("hg", result.get("message", ""))
        self.assertIn("git", result.get("message", ""))
        self.assertIn("jj", result.get("message", ""))
        self.assertIn("gitbutler", result.get("message", ""))

    def test_gitbutler_code_with_git_store(self):
        self.set_settings("vcs: gitbutler\nfinish: pr\n")
        self.assertEqual(self.vcs(), {"ok": True, "code": "gitbutler", "store": "git"})

    def test_gitbutler_store_unsupported_vcs(self):
        self.set_settings("finish: pr\nplanning_store:\n  vcs: gitbutler\n")
        result = self.vcs(expected=1)
        self.assertEqual(result.get("error"), "unsupported_vcs")
        self.assertIn("git", result.get("message", ""))
        self.assertIn("jj", result.get("message", ""))

    def test_gitbutler_local_finish_unsupported(self):
        self.set_settings("vcs: gitbutler\nfinish: local\n")
        result = self.vcs(expected=1)
        self.assertEqual(result.get("error"), "unsupported_combination")
        self.assertIn("finish: pr", result.get("message", ""))

    def test_gitbutler_absent_finish_unsupported(self):
        self.set_settings("vcs: gitbutler\n")
        result = self.vcs(expected=1)
        self.assertEqual(result.get("error"), "unsupported_combination")
        self.assertIn("finish: pr", result.get("message", ""))


if __name__ == "__main__":
    unittest.main()
