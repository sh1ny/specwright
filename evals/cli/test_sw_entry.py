"""The direct argument entry of sw (native-cli "Arguments sw cannot represent are refused", ADR 0040).

Task 1.1's entry probes, kept as regression checks. On Windows sw reads the raw command line, tells a lone surrogate
apart from a valid U+FFFD, and prints the bad_argument document with exit 2. On Linux and macOS the Dart runtime refuses
non-UTF-8 argv before main: non-zero exit and empty stdout, its exit code and text unpinned (C6).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swharness  # noqa: E402

WINDOWS = os.name == "nt"


def _run(args, cwd=None):
    """Run sw with args (str or bytes items); return (exit code, stdout text, stderr text)."""
    proc = subprocess.run([swharness.require_sw(), *args], capture_output=True, timeout=60, cwd=cwd)
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


class BadArgumentTests(unittest.TestCase):
    def assert_bad_argument(self, args, position):
        code, out, err = _run(args)
        self.assertEqual(code, 2, (out, err))
        document = json.loads(out)
        self.assertEqual(document["ok"], False)
        self.assertEqual(document["error"], "bad_argument")
        self.assertIn("argument %d " % position, document["message"])

    @unittest.skipIf(WINDOWS, "platform: POSIX argv bytes")
    def test_non_utf8_bytes_on_posix_are_refused_before_sw_runs(self):
        # The Dart runtime refuses non-UTF-8 argv before main (ADR 0040, C6): non-zero exit, empty stdout. Its exit
        # code and stderr text are the runtime's own and are not pinned. No file is made: the control call, the same
        # command with a UTF-8 path, shows that a run reaching the command prints a document on stdout.
        with tempfile.TemporaryDirectory() as tmp:
            base = os.fsencode(tmp)
            control = _run([b"release", b"notes", b"--proposal", os.path.join(base, b"m-x.md")])
            code, out, err = _run([b"release", b"notes", b"--proposal", os.path.join(base, b"m\xffx.md")])
        self.assertNotEqual(control[1], "", control)
        json.loads(control[1])
        self.assertNotEqual(code, 0, err)
        self.assertEqual(out, "", err)

    @unittest.skipUnless(WINDOWS, "platform: Windows UTF-16 command line")
    def test_lone_surrogate_on_windows_is_bad_argument(self):
        self.assert_bad_argument(["release", "notes", "--proposal", "m\udc80x.md"], 4)

    def test_valid_replacement_character_is_a_character(self):
        # a project command checks the project's version first, so it runs in a project of sw's own version
        with tempfile.TemporaryDirectory() as tmp:
            stamp_project(tmp)
            missing = os.path.join(tmp, "m�x.md")
            code, out, err = _run(["release", "notes", "--proposal", missing], cwd=tmp)
        document = json.loads(out)
        self.assertNotEqual(document.get("error"), "bad_argument", out)
        self.assertIn("m�x.md", document["message"])
        self.assertNotEqual(code, 0)


def stamp_project(root, version=None):
    """Make `root` a project of sw's own version: its openspec/.specwright/VERSION (the version check)."""
    if version is None:
        version = json.loads(swharness.run_sw("version", "--json").stdout)["version"]
    stamp = Path(root) / "openspec" / ".specwright" / "VERSION"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(version + "\n", encoding="utf-8")


class DirectArgumentTests(unittest.TestCase):
    def test_arguments_with_spaces_and_non_ascii(self):
        """sw vcs takes its arguments from the process argument list: a repo directory with a space, a message file and a
        path each arrive as one whole value (it fails while `sw vcs` reads only the stdin handoff)."""
        git_env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                   "GIT_AUTHOR_NAME": "Entry Test", "GIT_AUTHOR_EMAIL": "entry@example.invalid",
                   "GIT_COMMITTER_NAME": "Entry Test", "GIT_COMMITTER_EMAIL": "entry@example.invalid"}

        def git(repo, *args):
            done = subprocess.run(["git", *args], cwd=repo, env=git_env, capture_output=True, text=True,
                                  encoding="utf-8", timeout=60)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            return done.stdout

        with tempfile.TemporaryDirectory(prefix="swentry-") as tmp:
            repo = Path(tmp) / "a dir é"
            repo.mkdir()
            git(repo, "init", "-b", "main")
            (repo / "base.txt").write_text("base\n", encoding="utf-8")
            git(repo, "add", "base.txt")
            git(repo, "commit", "-m", "initial")
            git(repo, "checkout", "-b", "feat/x")
            stamp_project(repo)
            (repo / "a b.md").write_text("one\n", encoding="utf-8")
            (repo / "m é.txt").write_text("feat(entry): spaces and é\n", encoding="utf-8")
            proc = subprocess.run(
                [swharness.require_sw(), "vcs", "commit", "--repo", str(repo), "--role", "code", "--branch", "feat/x",
                 "--message-file", "m é.txt", "--", "a b.md"],
                cwd=repo, env=git_env, capture_output=True, timeout=60)
            document = json.loads(proc.stdout.decode("utf-8"))
            self.assertEqual(proc.returncode, 0, (proc.stdout, proc.stderr))
            self.assertTrue(document["ok"], document)
            self.assertEqual(git(repo, "show", "--format=%s", "--name-only", "HEAD").splitlines(),
                             ["feat(entry): spaces and é", "", "a b.md"])


if __name__ == "__main__":
    unittest.main()
