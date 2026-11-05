"""Black-box tests for the shared sw resolver, skills/specwright-pr/scripts/sw-path.sh (design D2, D6).

Each test drives `bash sw-path.sh` against a temp code checkout (openspec/.specwright/VERSION) and a temp SPECWRIGHT_HOME.
A matching binary is a copy of the binary named by SPECWRIGHT_SW (skips as `sw not built` without it); the mismatched or
broken ones are small stubs (a shell script on POSIX, a .cmd on Windows) passed with --file.

Run: SPECWRIGHT_SW=<path> python -m unittest evals/cli/test_sw_path.py
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
SCRIPT = Path(HERE).resolve().parent.parent / "skills" / "specwright-pr" / "scripts" / "sw-path.sh"
STOP = "sw missing or mismatched: rerun the install prompt"
EXE = "sw.exe" if WINDOWS else "sw"


class Base(unittest.TestCase):
    def setUp(self):
        self.sw = swharness.require_sw()
        self.bash = bashexe.bash()
        if not self.bash:
            self.skipTest("no bash installed")
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="sw-path-")))  # long form: a runner's TEMP may be 8.3 (RUNNER~1)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.code = self.tmp / "code"
        self.home = self.tmp / "home"
        self.home.mkdir()
        report = subprocess.run([self.sw, "version", "--json"], capture_output=True, text=True, timeout=60)
        self.report = json.loads(report.stdout)

    def version_file(self, version):
        path = self.code / "openspec" / ".specwright" / "VERSION"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(version + "\n", encoding="utf-8")

    def binary_dir(self, version, home=None):
        return Path(home or self.home) / ".specwright" / "bin" / version

    def install(self, version, home=None):
        """Copy the real binary to <home>/.specwright/bin/<version>/sw[.exe]; return that path."""
        target = self.binary_dir(version, home) / EXE
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.sw, target)
        return target

    def stub(self, stdout, status=0, name="stub"):
        """A stub that prints `stdout` and exits `status`."""
        if WINDOWS:
            path = self.tmp / (name + ".cmd")
            lines = ["@echo off"] + ["echo %s" % line for line in stdout.splitlines()] + ["exit /b %d" % status]
            path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="")
        else:
            path = self.tmp / name
            path.write_text("#!/bin/sh\ncat <<'EOF_STUB'\n%s\nEOF_STUB\nexit %d\n" % (stdout, status), encoding="utf-8")
            path.chmod(0o755)
        return path

    def resolve(self, *args, home=True, **extra):
        env = swharness.fixture_env(**extra)
        env.pop("SPECWRIGHT_HOME", None)
        if home is True:
            env["SPECWRIGHT_HOME"] = str(self.home)
        elif home:
            env["SPECWRIGHT_HOME"] = str(home)
        return subprocess.run([self.bash, str(SCRIPT), *map(str, args)], env=env, capture_output=True, text=True, timeout=120)

    def assert_stop(self, proc, *details):
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        lines = proc.stderr.strip().splitlines()
        self.assertEqual(lines[0], STOP, proc.stderr)
        self.assertEqual(len(lines), 2, proc.stderr)
        for detail in details:
            self.assertIn(str(detail).replace("\\", "/").lower(), lines[1].replace("\\", "/").lower())


class Resolver(Base):
    def test_matching_binary_prints_path(self):
        self.version_file(self.report["version"])
        target = self.install(self.report["version"])
        proc = self.resolve("--code", self.code)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(proc.stdout.strip().splitlines()), 1, proc.stdout)
        self.assertEqual(os.path.normcase(os.path.realpath(proc.stdout.strip())), os.path.normcase(os.path.realpath(target)))

    def test_specwright_home_is_used(self):
        self.version_file(self.report["version"])
        other = self.tmp / "other-home"
        target = self.install(self.report["version"], home=other)
        proc = self.resolve("--code", self.code, home=other)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(os.path.normcase(os.path.realpath(proc.stdout.strip())), os.path.normcase(os.path.realpath(target)))
        self.assertNotIn(str(self.home), proc.stdout)

    def test_override_without_binary_does_not_fall_back(self):
        self.version_file(self.report["version"])
        user_home = self.tmp / "user-home"
        self.install(self.report["version"], home=user_home)
        env = {"HOME": str(user_home), "USERPROFILE": str(user_home)}
        proc = self.resolve("--code", self.code, **env)
        self.assert_stop(proc, self.binary_dir(self.report["version"]))

    def test_no_version_file_stops(self):
        (self.code / "openspec").mkdir(parents=True)
        self.install(self.report["version"])
        proc = self.resolve("--code", self.code)
        self.assert_stop(proc, "no installed version")

    def test_missing_binary_ignores_other_versions(self):
        self.version_file("0.24.0")
        self.install("0.23.0")
        proc = self.resolve("--code", self.code)
        self.assert_stop(proc, self.binary_dir("0.24.0") / EXE)

    def test_interface_mismatch_stops(self):
        stub = self.stub('{"version":"0.24.0","interface":99}')
        proc = self.resolve("--file", stub, "--version", "0.24.0")
        self.assert_stop(proc, stub, "99", "interface 1")

    def test_non_json_report_stops(self):
        for name, body, status in (("text", "hello there", 0), ("two", '{"version":"0.24.0","interface":1}\n{"x":1}', 0),
                                   ("fail", '{"version":"0.24.0","interface":1}', 3), ("partial", '{"version":"0.24.0"}', 0)):
            with self.subTest(case=name):
                stub = self.stub(body, status, name=name)
                proc = self.resolve("--file", stub, "--version", "0.24.0")
                self.assert_stop(proc, stub)


if __name__ == "__main__":
    unittest.main()
