"""Black-box tests for how `sw run --bounded` finds a command and hands it its arguments (design D8).

Needs the binary named by SPECWRIGHT_SW (skips as `sw not built` otherwise). The recorder is a small Python script run with
sys.executable that writes the arguments it received to a JSON file. The batch-shim cases are Windows only (they skip with a
reason elsewhere): a `.cmd` or `.bat` file runs through cmd.exe there.

Run: SPECWRIGHT_SW=<path> python -m unittest evals/cli/test_sw_args.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import swharness  # noqa: E402
import bashexe  # noqa: E402

WINDOWS = os.name == "nt"
RECORDER = "import json, sys\nwith open(sys.argv[1], 'w', encoding='utf-8') as f:\n    json.dump(sys.argv[2:], f)\n"
UNSAFE_LINE = "bounded: unsafe batch argument: %s\n"


class Base(unittest.TestCase):
    def setUp(self):
        swharness.require_sw()
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-args-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = self.tmp / "recorded.json"
        self.recorder = self.tmp / "rec.py"
        self.recorder.write_text(RECORDER, encoding="utf-8")

    def env(self, *dirs, **extra):
        env = swharness.fixture_env(**extra)
        if dirs:
            env["PATH"] = os.pathsep.join([*map(str, dirs), env.get("PATH", "")])
        return env

    def sw(self, *args, env=None, input=b"", timeout=60):
        """`sw run --bounded -- args`, bytes in and out."""
        return subprocess.run([swharness.require_sw(), "run", "--bounded", "--", *map(str, args)],
                              env=env if env is not None else self.env(), input=input, capture_output=True, timeout=timeout)

    def recorded(self):
        return json.loads(self.out.read_text(encoding="utf-8"))

    def shim(self, directory, name, body):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(body, encoding="utf-8", newline="\r\n")
        return path

    def forwarding_shim(self, directory, name="fake.cmd", out=None):
        """A shim that forwards `%*` to the recorder, which writes what it got to `out`."""
        return self.shim(directory, name, '@"%s" "%s" "%s" %%*\n' % (sys.executable, self.recorder, out or self.out))


class Lookup(Base):
    @unittest.skipUnless(WINDOWS, "platform: .cmd and .bat shims run through cmd.exe on Windows only")
    def test_cmd_shim_resolves_through_pathext(self):
        bin_dir = self.tmp / "bin"
        self.shim(bin_dir, "gh.cmd", "@echo shim %~1 %~2\n@exit /b 4\n")
        self.assertFalse((bin_dir / "gh.exe").exists())
        proc = self.sw("gh", "api", "user", env=self.env(bin_dir))
        self.assertEqual((proc.returncode, proc.stdout.decode().strip()), (4, "shim api user"), proc.stderr)

    def test_unresolved_name_exits_127(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        proc = self.sw("sw-no-such-command-xyz", "arg", env=self.env(empty))
        self.assertEqual(proc.returncode, 127)
        self.assertIn(b"sw-no-such-command-xyz", proc.stderr)


@unittest.skipIf(WINDOWS, "platform: an empty PATH entry is the current directory on POSIX only (#202)")
class EmptyPathEntry(Base):
    """#202: an empty POSIX PATH entry is the current directory, searched in its position, as `bash -c tool` finds it."""

    def setUp(self):
        super().setUp()
        self.work = self.tmp / "work"
        self.bin = self.tmp / "bin"
        for d, who in ((self.work, "cwd"), (self.bin, "bin")):
            d.mkdir()
            tool = d / "tool"
            tool.write_text("#!/bin/sh\necho %s\n" % who, encoding="utf-8", newline="\n")
            tool.chmod(0o755)

    def run_tool(self, path):
        env = swharness.fixture_env()
        env["PATH"] = path
        return subprocess.run([swharness.require_sw(), "run", "--bounded", "--", "tool"], cwd=self.work, env=env,
                              capture_output=True, timeout=60)

    def test_empty_path_entry_is_cwd(self):
        proc = self.run_tool(":" + str(self.bin))
        self.assertEqual((proc.returncode, proc.stdout.decode().strip()), (0, "cwd"), proc.stderr)

    def test_empty_path_entry_keeps_position(self):
        proc = self.run_tool(str(self.bin) + ":")
        self.assertEqual((proc.returncode, proc.stdout.decode().strip()), (0, "bin"), proc.stderr)

    def test_no_empty_entry_no_cwd(self):
        (self.bin / "tool").unlink()
        proc = self.run_tool(str(self.bin))
        self.assertEqual(proc.returncode, 127, proc.stderr)
        self.assertIn(b"tool", proc.stderr)


class NativeArguments(Base):
    def test_long_argument_to_native_exe_is_unchanged(self):
        long_arg = ("word \"quoted\" back\\slash \\\\ trailing\\ new\nline \u00e9\u4e2d\U0001f600 " * 400)[:20000]
        self.assertEqual(len(long_arg), 20000)
        args = [long_arg, "", "next arg", 'say "hi"', "C:\\two words\\"]
        proc = self.sw(sys.executable, self.recorder, self.out, *args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.recorded(), args)

    def test_long_argument_through_bash_c_transport(self):
        bash = bashexe.bash()
        if not bash:
            self.skipTest("no bash installed")
        long_arg = ("word \"quoted\" back\\slash \u00e9\u4e2d " * 1000)[:20000]
        proc = self.sw(bash, "-c", 'printf %s "$1"', "name", long_arg)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, long_arg.encode("utf-8"))

    @unittest.skipUnless(WINDOWS, "platform: the bash -c stdin transport is used on Windows only")
    def test_missing_transport_marker_exits_126(self):
        bash = bashexe.bash()
        if not bash:
            self.skipTest("no bash installed")
        # The prelude the binary puts in front of the script is read back from bash itself.
        script = 'printf %s "$BASH_EXECUTION_STRING"'
        shown = self.sw(bash, "-c", script, "name", "x").stdout.decode("utf-8")
        self.assertTrue(shown.endswith("; " + script), shown)
        prelude = shown[:-len("; " + script)]
        ran = self.tmp / "ran"
        for data in (b"a\0b\0", b""):
            with self.subTest(data=data):
                helper = subprocess.run([swharness.require_sw(), "__exec", "--", bash, "-c", prelude + "; echo ran > " + ran.as_posix(), "name"],
                                        input=b"g" + data, capture_output=True, timeout=60)
                self.assertEqual(helper.returncode, 126, helper.stderr)
                self.assertIn(b"bounded: argument transport failed", helper.stderr)
                self.assertFalse(ran.exists())


@unittest.skipUnless(WINDOWS, "platform: .cmd and .bat shims run through cmd.exe on Windows only")
class BatchShims(Base):
    def test_batch_metacharacters_reach_recorder(self):
        self.forwarding_shim(self.tmp / "bin")
        args = ["a&b", "c|d", "<e>", "(f)", "g^h", "", "x & echo pwned"]
        proc = self.sw("fake.cmd", *args, env=self.env(self.tmp / "bin"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.recorded(), args)
        self.assertNotIn(b"pwned", proc.stdout + proc.stderr)

    def test_batch_trailing_backslashes_survive(self):
        self.forwarding_shim(self.tmp / "bin")
        args = ["C:\\two words\\", "D:\\x\\\\", "next", ""]
        proc = self.sw("fake.cmd", *args, env=self.env(self.tmp / "bin"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.recorded(), args)

    def test_batch_path_with_percent_is_refused(self):
        expanded = self.tmp / "decoy"
        decoy_out = self.tmp / "decoy.json"
        percent_out = self.tmp / "percent.json"
        self.forwarding_shim(expanded, out=decoy_out)
        percent_dir = self.tmp / "%SW_SLOT%"
        self.forwarding_shim(percent_dir, out=percent_out)
        proc = self.sw("fake.cmd", "x", env=self.env(percent_dir, SW_SLOT=expanded))
        self.assertEqual((proc.returncode, proc.stdout), (2, b""))
        self.assertEqual(proc.stderr.decode(), UNSAFE_LINE % "fake.cmd")
        self.assertFalse(decoy_out.exists() or percent_out.exists(), "a shim ran")

    def test_batch_unsafe_argument_is_refused(self):
        self.forwarding_shim(self.tmp / "bin")
        for arg in ("%PATH%", "!x!", 'a"b', "a\rb", "a\nb"):
            with self.subTest(arg=arg):
                proc = self.sw("fake.cmd", "ok", arg, env=self.env(self.tmp / "bin"))
                self.assertEqual((proc.returncode, proc.stdout), (2, b""))
                self.assertEqual(proc.stderr.decode(), UNSAFE_LINE % "fake.cmd")
                self.assertFalse(self.out.exists(), "the shim ran")

    def test_batch_line_over_limit_is_refused(self):
        self.forwarding_shim(self.tmp / "bin", name="fake.bat")
        proc = self.sw("fake.bat", "a" * 8200, env=self.env(self.tmp / "bin"))
        self.assertEqual((proc.returncode, proc.stdout), (2, b""))
        self.assertEqual(proc.stderr.decode(), UNSAFE_LINE % "fake.bat")
        self.assertFalse(self.out.exists(), "the shim ran")


if __name__ == "__main__":
    unittest.main()
