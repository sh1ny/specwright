"""as.sh fences `jj git push` and `jj git fetch` like git, and refuses every other jj command.

The push test runs real jj in a colocated repository whose origin is a github.com URL rewritten
(`url.<path>.insteadOf`) to a local bare repository. jj pushes with `--no-verify`, so the Git child
process's reference-transaction hook (it fires when the push updates the remote-tracking ref) asks
`git credential fill` for github.com and for another host: the hook sees the fenced helper's answer
exactly as the transport would. The fake gh holds two accounts, and only the run login's token may
ever be used.

Run: python -m unittest evals/pr-pair/test_as_jj.py
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
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
import fixtures  # noqa: E402
import jjenv  # noqa: E402
import bashexe  # noqa: E402

GITHUB = "https://github.com/o/r.git"
HOOK = (
    "#!/bin/sh\n"
    "cat >/dev/null\n"
    '[ "$1" = prepared ] && [ -n "${CRED_LOG:-}" ] || exit 0\n'
    "printf 'protocol=https\\nhost=github.com\\n\\n' | git credential fill > \"$CRED_LOG\" 2>/dev/null || true\n"
    "printf 'protocol=https\\nhost=evil.example\\n\\n' | git credential fill > \"$CRED_LOG.other\" 2>/dev/null || true\n"
    "exit 0\n"
)


@unittest.skipUnless(bashexe.bash(), "needs bash")
class AsJjCase(unittest.TestCase):
    def setUp(self):
        self.jj = jjenv.require_jj()
        self.scratch = jjenv.Scratch()
        self.addCleanup(self.scratch.close)
        self.tmp = Path(tempfile.mkdtemp(prefix="swj-"))
        self.addCleanup(fixtures.rmtree, self.tmp)
        (self.tmp / "bin").mkdir()
        fixtures.install_fake_gh(self.tmp)
        (self.tmp / "gh-state.json").write_text(json.dumps(
            {"user": "sh1ny", "tokens": {"sh1ny": "tok-sh1ny", "code-bot": "tok-code"}}), encoding="utf-8")
        self.fixture = self.scratch.tracked_repo()
        self.repo = self.fixture.path
        self.marker = self.tmp / "ran"
        # a jj stand-in that only records that it ran; refusal tests put it first on PATH
        self.stub = self.tmp / "stub"
        self.stub.mkdir()
        (self.stub / "jj").write_text("#!/bin/sh\ntouch '%s'\n" % self.marker.as_posix(), encoding="utf-8", newline="\n")
        (self.stub / "jj").chmod(0o755)

    def env(self, **extra):
        env = {k: v for k, v in self.scratch.env.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO")}
        env.update({"PATH": str(self.tmp / "bin") + os.pathsep + env.get("PATH", ""),
                    "FAKE_GH_STATE": str(self.tmp / "gh-state.json"), "FAKE_GH_LOG": str(self.tmp / "gh-log.jsonl")})
        env.update(extra)
        return env

    def as_sh(self, *args, env=None):
        return subprocess.run([bashexe.bash(), str(AS_SH), "code-bot", *args], cwd=self.repo, env=env or self.env(),
                              capture_output=True, text=True, timeout=120)

    def gh_calls(self):
        path = self.tmp / "gh-log.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def refused(self, *args, needle):
        env = self.env(PATH=str(self.stub) + os.pathsep + str(self.tmp / "bin") + os.pathsep + os.environ.get("PATH", ""))
        result = self.as_sh("jj", *args, env=env)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn(needle, result.stderr)
        self.assertFalse(self.marker.exists(), "the jj command must not run")


class TestAsJj(AsJjCase):
    def test_jj_push_uses_fenced_token(self):
        origin = self.scratch.origin
        git = jjenv.real_git()
        self.fixture.run(git, "remote", "set-url", "origin", GITHUB)
        self.fixture.run(git, "config", "url.%s.insteadOf" % origin.as_posix(), GITHUB)
        log = self.tmp / "credential.txt"
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "feat: fenced push")
        self.fixture.run(self.jj, "bookmark", "create", "feat/x", "-r", "@-")
        hook = self.repo / ".git" / "hooks" / "reference-transaction"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(HOOK, encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        tip = self.fixture.run(git, "rev-parse", "refs/heads/feat/x").stdout.strip()

        result = self.as_sh("jj", "git", "push", "--remote", "origin", "--bookmark", "feat/x",
                            env=self.env(CRED_LOG=log.as_posix()))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        pushed = subprocess.run([git, "--git-dir", str(origin), "rev-parse", "refs/heads/feat/x"],
                                capture_output=True, text=True, env=self.scratch.env).stdout.strip()
        self.assertEqual(pushed, tip)
        answer = dict(line.split("=", 1) for line in log.read_text(encoding="utf-8").splitlines() if "=" in line)
        self.assertEqual(answer.get("username"), "x-access-token")
        self.assertEqual(answer.get("password"), "tok-code")
        other = Path(str(log) + ".other").read_text(encoding="utf-8")
        self.assertNotIn("password", other, "the fenced helper answers github.com only")
        self.assertNotIn("tok-sh1ny", log.read_text(encoding="utf-8"))
        api = [call for call in self.gh_calls() if call["argv"][0] == "api"]
        self.assertTrue(api)
        self.assertEqual({call["env"]["GH_TOKEN"] for call in api}, {"tok-code"}, "no call uses the active account's token")

    def test_jj_repository_option_refused(self):
        for args in (("-R", "../other", "git", "push"), ("--repository=../other", "git", "push"),
                     ("git", "push", "-R", "../other"), ("-R../other", "git", "fetch")):
            with self.subTest(args=args):
                self.refused(*args, needle="selects another repository")

    def test_jj_config_option_refused(self):
        for args in (("--config", "git.executable-path=/tmp/x", "git", "fetch"),
                     ("--config-file", "/tmp/x.toml", "git", "fetch"),
                     ("--config=git.executable-path=/tmp/x", "git", "push"),
                     ("git", "fetch", "--config", "x=y")):
            with self.subTest(args=args):
                self.refused(*args, needle="selects another config")

    def test_jj_other_subcommand_refused(self):
        for args in (("bookmark", "set", "feat/x", "-r", "@-"), ("git", "clone", "x"), ("git",), ("log",)):
            with self.subTest(args=args):
                self.refused(*args, needle="only 'jj git push' and 'jj git fetch' are fenced")


if __name__ == "__main__":
    unittest.main()
