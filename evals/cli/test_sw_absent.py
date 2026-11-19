"""Every command runs with no shipped script and no interpreter or shell it could start (native-cli-retire-scripts, task 7.7).

The tree has no `skills/*/scripts` directory and no `scripts` directory since 0.38.0. Each test runs `sw vcs`, `commit`,
`finish`, `pr`, `as`, `review`, `release`, `update` and `gate` twice from the same fixtures: once as they are, and once with
recording `python`, `python3`, `bash` and `sh` first on PATH that exit 1. The recorded run must give the result of the plain
one, and no recorder may have run. A probe first runs every recorder directly, so that an empty log means nothing started
rather than that a recorder cannot record.

A shell the caller asks for is the one exception: `sw as <login> bash -c 'exit 7'` starts the recording `bash` as the fenced
command, and `sw as` exits with its status 1. On Windows the recorders are `.cmd` files: only a PATHEXT name starts there.
The recording `bash` is never started by this eval, so it is not a bash the bare-bash check has to resolve.

It reuses the fixtures and the harness of evals/cli/test_no_shell.py.

Needs the binary named by SPECWRIGHT_SW (skips as `sw not built` otherwise; fails under SPECWRIGHT_REQUIRE_SW=1).

Run: SPECWRIGHT_SW=<path> python -m unittest evals/cli/test_sw_absent.py
"""
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS = HERE.parent
ROOT = EVALS.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EVALS))
sys.path.insert(0, str(EVALS / "runner"))
import fakeexe  # noqa: E402
import test_bare_bash  # noqa: E402
import test_no_shell as ns  # noqa: E402

INTERPRETERS = ("python", "python3", "bash", "sh")  # bare-bash: not started (recorder names)
LOGIN = "me"

# A fake gh for `sw pr discover` and the fence of `sw as`: `auth token` answers a token (and, with --help, a text that names
# --user), `api user` answers the login, the pulls list is empty, and no other call is answered.
GH = '''import sys
args = sys.argv[1:]


def say(text):  # ends the line with a line feed alone, as gh does on every OS (print adds a carriage return on Windows)
    sys.stdout.buffer.write(text.encode() + bytes([10]))


if args[:2] == ["auth", "token"]:
    say("usage: gh auth token [--user <login>]" if "--help" in args else "tok-me")
elif args[:1] == ["api"] and "/pulls" in " ".join(args):
    say("[]")
elif args[:1] == ["api"] and "user" in args:
    say("me")
else:
    sys.stderr.write("fake gh: unexpected call %r\\n" % (args,))
    sys.exit(9)
'''


def shape(stdout, *keys):
    """The named keys of a JSON document, as text: what two runs of a command must share."""
    document = json.loads(stdout)
    return json.dumps({key: document.get(key) for key in keys}, sort_keys=True)


class SwAbsent(ns.NoShell):
    # the two tests of test_no_shell.py are not this file's
    test_ported_commands_with_failing_shells_first = None
    test_failing_utilities_first_on_path = None

    def setUp(self):
        super().setUp()
        fakeexe.write_python_fake(self.gh_dir / "gh", GH)
        self.review_settings = self.root / "review-settings.yaml"
        self.review_settings.write_text("review:\n  cross_model: false\n", encoding="utf-8", newline="\n")
        self.proposal = self.root / "proposal.md"
        self.proposal.write_text("## Why\n\nx\n\n## Release Notes\n\nS.\n\n### Added\n\n- New flag (#1)\n", encoding="utf-8",
                                 newline="\n")
        self.download = self.root / "download"  # a tree for `sw update pack-check`: the packs' fixture schema and packs
        (self.download / "schemas" / "specwright").mkdir(parents=True)
        packs = ROOT / "evals" / "packs" / "fixtures"
        shutil.copy(packs / "schema.yaml", self.download / "schemas" / "specwright" / "schema.yaml")
        (self.download / "packs").mkdir()
        for name in ("valid-web", "valid-ui-base", "valid-domain", "strict-wording"):
            shutil.copytree(packs / "packs" / name, self.download / "packs" / name)

    def ported_commands(self, front, tag):
        """The commands of test_no_shell.py and the others the requirement names: `as`, `review`, `release`, `update`, `gate`."""
        out = super().ported_commands(front, tag)
        env = self.env(front)
        code, stdout, stderr = self.sw_call(["as"], [LOGIN, "git", "--version"], self.code, env)
        out["as git"] = (code, stdout, stderr)
        code, stdout, stderr = self.sw_call(
            ["review"], ["select", "--runtime", "other", "--settings", self.review_settings.resolve().as_posix()], self.code,
            env)
        out["review select"] = (code, shape(stdout, "route") if code == 0 else stdout, stderr)
        code, stdout, stderr = self.sw_call(["release"], ["notes", "--proposal", self.proposal.resolve().as_posix()],
                                            self.root, env)
        out["release notes"] = (code, shape(stdout, "summary") if code == 0 else stdout, stderr)
        code, stdout, stderr = self.sw_call(
            ["update"], ["--download", self.download.resolve().as_posix(), "pack-check"], self.root, env)
        out["update pack-check"] = (code, shape(stdout, "ok", "refusals") if code == 0 else stdout, stderr)
        code, stdout, stderr = self.sw_call(["gate"], ["show", "--store", self.work.resolve().as_posix()], self.work, env)
        out["gate show"] = (code, shape(stdout, "ok", "held") if code == 0 else stdout, stderr)
        return out

    def test_no_script_is_on_disk(self):
        self.assertEqual([d.name for d in ROOT.glob("skills/*") if (d / "scripts").exists()], [])
        self.assertFalse((ROOT / "scripts").exists())

    def test_commands_without_scripts_or_interpreters(self):
        recorders = ns.write_recorders(self.root / "failing-interpreters", INTERPRETERS)
        self.probe(recorders, INTERPRETERS)
        self.assert_same_as_plain(recorders)

    def fenced_shell(self):
        """`sw as me bash -c 'exit 7'` with the recorders first: (exit code, names the recorders logged)."""
        recorders = ns.write_recorders(self.root / "failing-interpreters", INTERPRETERS)
        self.probe(recorders, INTERPRETERS)
        self.build_code_repo("fenced")
        code, stdout, stderr = self.sw_call(["as"], [LOGIN, "bash", "-c", "exit 7"], self.code, self.env(recorders))
        logged = self.log.read_text(encoding="utf-8").split() if self.log.exists() else []
        return code, stdout + stderr, logged

    def test_fenced_shell_the_caller_asked_for(self):
        code, output, logged = self.fenced_shell()
        self.assertEqual(logged, ["bash"], "the recording bash started once, as the fenced command: " + output)  # bare-bash: not started
        self.assertEqual(code, 1, output)

    @unittest.skipUnless(os.name == "nt", "platform: the .cmd wrapper is how a recorder starts on Windows")
    def test_fenced_shell_control_on_windows(self):
        code, output, logged = self.fenced_shell()
        self.assertTrue((self.root / "failing-interpreters" / "bash.cmd").is_file())
        self.assertEqual(logged, ["bash"], output)  # bare-bash: not started
        self.assertEqual(code, 1, output)
        # the bash-resolution check reports no violation for this eval: it never starts the recorder itself
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertEqual(test_bare_bash.check_source(source, __file__), [])


if __name__ == "__main__":
    unittest.main()
