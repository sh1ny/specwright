"""as.sh fences `but pull` like git, and refuses every other `but` command and the -C option.

`but pull` fetches by running the system `git fetch`, which honours the GIT_CONFIG_* environment. The fake
`but` here records its argv and asks `git credential fill` for github.com and for another host, exactly as
that fetch would: it sees the fenced helper's answer. The fake gh holds two accounts, and only the run
login's token may ever be used. No real `but` is needed.

Run: python -m unittest evals/pr-pair/test_as_gitbutler.py
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
ROOT = HERE.parents[1]
AS_SH = ROOT / "skills" / "specwright-pr" / "scripts" / "as.sh"
sys.path.insert(0, str(ROOT / "evals" / "git-workflow"))
import fixtures  # noqa: E402

FAKE_BUT = (
    "#!/bin/sh\n"
    'printf \'%s\n\' "$@" > "$BUT_LOG"\n'
    "printf 'protocol=https\nhost=github.com\n\n' | git credential fill > \"$BUT_LOG.cred\" 2>/dev/null || true\n"
    "printf 'protocol=https\nhost=evil.example\n\n' | git credential fill > \"$BUT_LOG.other\" 2>/dev/null || true\n"
    "exit 0\n"
)


@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "needs bash and git")
class TestAsGitButler(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="swb-"))
        self.addCleanup(fixtures.rmtree, self.tmp)
        (self.tmp / "bin").mkdir()
        fixtures.install_fake_gh(self.tmp)
        (self.tmp / "gh-state.json").write_text(json.dumps(
            {"user": "sh1ny", "tokens": {"sh1ny": "tok-sh1ny", "code-bot": "tok-code"}}), encoding="utf-8")
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.log = self.tmp / "but-argv.txt"
        # a `but` stand-in first on PATH: it records argv, and what the fenced helper answers
        self.stub = self.tmp / "stub"
        self.stub.mkdir()
        (self.stub / "but").write_text(FAKE_BUT, encoding="utf-8", newline="\n")
        (self.stub / "but").chmod(0o755)

    def env(self):
        env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO")}
        env.update({"PATH": os.pathsep.join([str(self.stub), str(self.tmp / "bin"), env.get("PATH", "")]),
                    "FAKE_GH_STATE": str(self.tmp / "gh-state.json"), "FAKE_GH_LOG": str(self.tmp / "gh-log.jsonl"),
                    "BUT_LOG": self.log.as_posix()})
        return env

    def as_sh(self, *args):
        return subprocess.run(["bash", str(AS_SH), "code-bot", "but", *args], cwd=self.work, env=self.env(),
                              capture_output=True, text=True, timeout=120)

    def gh_calls(self):
        path = self.tmp / "gh-log.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def refused(self, *args, needle):
        result = self.as_sh(*args)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn(needle, result.stderr)
        self.assertFalse(self.log.exists(), "the but command must not run")

    def test_but_pull_uses_fenced_token(self):
        result = self.as_sh("pull")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8").split(), ["pull"])
        answer = dict(line.split("=", 1) for line in Path(str(self.log) + ".cred").read_text(encoding="utf-8").splitlines() if "=" in line)
        self.assertEqual(answer.get("username"), "x-access-token")
        self.assertEqual(answer.get("password"), "tok-code")
        other = Path(str(self.log) + ".other").read_text(encoding="utf-8")
        self.assertNotIn("password", other, "the fenced helper answers github.com only")
        api = [call for call in self.gh_calls() if call["argv"][0] == "api"]
        self.assertTrue(api)
        self.assertEqual({call["env"]["GH_TOKEN"] for call in api}, {"tok-code"}, "no call uses the active account's token")
        self.assertNotIn("tok-sh1ny", json.dumps(self.gh_calls()))

    def test_but_other_subcommand_refused(self):
        for args in (("commit", "-m", "x"), ("push",), ("branch", "new", "x"), ("status",), ("--json", "status"), ()):
            with self.subTest(args=args):
                self.refused(*args, needle="only 'but pull' is fenced")

    def test_but_directory_option_refused(self):
        for args in (("-C", "../other", "pull"), ("-C../other", "pull"), ("--current-dir", "../other", "pull"),
                     ("--current-dir=../other", "pull"), ("pull", "-C", "../other"), ("pull", "--current-dir=../o")):
            with self.subTest(args=args):
                self.refused(*args, needle="selects another repository")


if __name__ == "__main__":
    unittest.main()
