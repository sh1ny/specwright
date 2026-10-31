"""Execute the pinned-jj (each OS row) and pinned-but workflow setup steps against local archives / files and fake binaries."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "evals") not in sys.path:
    sys.path.append(str(ROOT / "evals"))
import bashexe  # noqa: E402
WORKFLOW = ROOT / ".github" / "workflows" / "evals.yml"


def install_run_block(step="Install pinned jj"):
    """Return the shell body of the named install step, rather than duplicating its commands in the test."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "- name: " + step:
            continue
        run_index = next(i for i in range(index + 1, len(lines)) if lines[i].lstrip().startswith("run:"))
        run_line = lines[run_index]
        if run_line.strip() == "run: |":
            body = []
            for item in lines[run_index + 1:]:
                if item.strip() and len(item) - len(item.lstrip()) <= len(run_line) - len(run_line.lstrip()):
                    break
                body.append(item[12:] if item.startswith("            ") else item.lstrip())
            return "\n".join(body) + "\n"
        return run_line.split("run:", 1)[1].strip()
    raise AssertionError("the eval workflow has no step named %r" % step)


JJ_VERSION = "0.46.0"
JJ_BASE = "https://github.com/jj-vcs/jj/releases/download/v%s/" % JJ_VERSION
# (RUNNER_OS, RUNNER_ARCH, release asset, pinned SHA-256, binary name in the archive)
JJ_ROWS = (
    ("Linux", "X64", "jj-v%s-x86_64-unknown-linux-musl.tar.gz" % JJ_VERSION,
     "fce0271158e665ceb82dc66c5eb95b1728649094e9133074f3b5baece345fc08", "jj"),
    ("macOS", "ARM64", "jj-v%s-aarch64-apple-darwin.tar.gz" % JJ_VERSION,
     "43daa37ce0f9716cdf6fb65a29cbcae74a3160aef048cf3cb3d166d41cb4ab58", "jj"),
    ("Windows", "X64", "jj-v%s-x86_64-pc-windows-msvc.zip" % JJ_VERSION,
     "c42316b10df04611bc65029a18bcb2d92636edddb6871d511f7bb4233e999b83", "jj.exe"),
)


class TestPinnedJjWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.marker = self.root / "jj-ran.json"
        self.curl_log = self.root / "curl.log"
        self.github_path = self.root / "github-path"
        self.github_env = self.root / "github-env"
        self._make_tools()

    def _make_tools(self):
        curl = self.bin / "curl"
        with curl.open("w", encoding="utf-8", newline="\n") as script:
            script.write(
                "#!/usr/bin/env python3\n"
                "import os, shutil, sys\n"
                "args = sys.argv[1:]\n"
                "open(os.environ['JJ_TEST_CURL_LOG'], 'a', newline='\\n').write(' '.join(args) + '\\n')\n"
                "if '--output' in args:\n"
                "    out = args[args.index('--output') + 1]\n"
                "elif '-o' in args:\n"
                "    out = args[args.index('-o') + 1]\n"
                "else:\n"
                "    raise SystemExit('fake curl requires an output path')\n"
                "if not any(arg.startswith('https://') for arg in args):\n"
                "    raise SystemExit('fake curl requires the workflow download URL')\n"
                "shutil.copyfile(os.environ['JJ_TEST_ARCHIVE'], out)\n"
            )
        curl.chmod(0o755)

    def make_archive(self, asset, name):
        """A local archive in the row's format (.tar.gz or .zip) holding a stand-in `jj`/`jj.exe`."""
        content = self.root / ("content-" + name)
        content.mkdir(exist_ok=True)
        binary = content / name
        with binary.open("w", encoding="utf-8", newline="\n") as script:
            script.write(
                "#!/usr/bin/env python3\n"
                "import json, os\n"
                "open(os.environ['JJ_TEST_MARKER'], 'w', newline='\\n').write(json.dumps({'required': os.environ.get('SPECWRIGHT_REQUIRE_JJ'), 'version': 'jj 0.46.0'}))\n"
                "print('jj 0.46.0')\n"
            )
        binary.chmod(0o755)
        archive = self.root / ("source-" + asset)
        if asset.endswith(".zip"):
            with zipfile.ZipFile(archive, "w") as z:
                z.write(binary, arcname=name)
        else:
            with tarfile.open(archive, "w:gz") as z:
                z.add(binary, arcname=name)
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    def run_install(self, checksum, row=JJ_ROWS[0], runner_arch=None, archive=None):
        env = {
            **os.environ,
            "PATH": os.environ.get("PATH", ""),
            "RUNNER_OS": row[0],
            "RUNNER_ARCH": runner_arch or row[1],
            "RUNNER_TEMP": str(self.root / "runner-temp"),
            "GITHUB_PATH": str(self.github_path),
            "GITHUB_ENV": str(self.github_env),
            "JJ_TEST_BIN": str(self.bin),
            "JJ_VERSION": JJ_VERSION,
            "JJ_SHA256": checksum,
            "JJ_TEST_ARCHIVE": str(archive or self.root / "unused"),
            "JJ_TEST_MARKER": str(self.marker),
            "JJ_TEST_CURL_LOG": str(self.curl_log),
        }
        env.pop("SPECWRIGHT_REQUIRE_JJ", None)
        (self.root / "runner-temp").mkdir(exist_ok=True)
        self.github_path.touch()
        self.github_env.touch()
        shell = (
            'if command -v cygpath >/dev/null 2>&1; then '
            'fake_bin="$(cygpath -u "$JJ_TEST_BIN")"; '
            'RUNNER_TEMP="$(cygpath -u "$RUNNER_TEMP")"; export RUNNER_TEMP; '
            'else fake_bin="$JJ_TEST_BIN"; fi\n'
            'PATH="$fake_bin:$PATH"\n'
            "export PATH\n"
            "hash -r\n"
            'curl() { "$fake_bin/curl" "$@"; }\n'
            + install_run_block()
            + '\nset -a; . "$GITHUB_ENV"; set +a\n'
            + 'export PATH="$(cat "$GITHUB_PATH"):$PATH"\n'
            # only a Windows host resolves `jj` to jj.exe; elsewhere the step above already ran it by path
            + ("jj --version\n" if row[4] == "jj" or os.name == "nt" else "")
        )
        bash = bashexe.bash()
        if not bash:
            self.skipTest("needs bash")
        return subprocess.run(
            [bash, "-euo", "pipefail", "-c", shell],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )

    def test_workflow_installs_pinned_jj_on_each_os(self):
        step = install_run_block()
        for row in JJ_ROWS:
            with self.subTest(runner="%s/%s" % row[:2]):
                self.assertIn(row[3], step, "the row's pinned digest is in the step")
                self.marker.unlink(missing_ok=True)
                self.curl_log.unlink(missing_ok=True)
                archive, digest = self.make_archive(row[2], row[4])
                result = self.run_install(digest, row, archive=archive)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(JJ_BASE + row[2], self.curl_log.read_text(encoding="utf-8").split())
                self.assertEqual(json.loads(self.marker.read_text(encoding="utf-8")),
                                 {"required": "1", "version": "jj 0.46.0"})
                self.assertIn("0.46.0", result.stdout)

    def test_workflow_checks_jj_sha256_before_use(self):
        for row in JJ_ROWS:
            with self.subTest(runner="%s/%s" % row[:2]):
                self.marker.unlink(missing_ok=True)
                archive, _ = self.make_archive(row[2], row[4])
                result = self.run_install("0" * 64, row, archive=archive)
                self.assertNotEqual(result.returncode, 0, "a mismatched jj archive must fail setup")
                self.assertFalse(self.marker.exists(), "the jj binary must not be used after a checksum mismatch")
                self.assertFalse((self.root / "runner-temp" / "jj-bin" / row[4]).exists(),
                                 "nothing is unpacked or installed after a mismatch")

    def test_unknown_runner_fails_before_download(self):
        archive, digest = self.make_archive(JJ_ROWS[0][2], "jj")
        result = self.run_install(digest, JJ_ROWS[0], runner_arch="ARM64", archive=archive)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no pinned jj for Linux/ARM64", result.stdout + result.stderr)
        self.assertFalse(self.curl_log.exists(), "no download for an unpinned runner")
        self.assertFalse(self.marker.exists())

    def test_version_pin_files_check_out_lf(self):
        files = ["OPENSPEC_VERSION", "JJ_VERSION", "BUT_VERSION", "VERSION"]
        result = subprocess.run(["git", "check-attr", "eol", "--"] + files, cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        found = dict(line.split(": eol: ") for line in result.stdout.strip().splitlines())
        for name in files:
            self.assertEqual(found.get(name), "lf", "%s must check out with LF (.gitattributes)" % name)

    def test_schema_files_check_out_lf(self):
        """Fixtures copy schemas/ byte for byte into repos that git commits with autocrlf and jj then compares: a CRLF
        checkout on Windows shows as a modified file there."""
        files = subprocess.run(["git", "ls-files", "--", "schemas"], cwd=ROOT, capture_output=True, text=True,
                               check=True).stdout.split()
        self.assertTrue(files)
        result = subprocess.run(["git", "check-attr", "eol", "--"] + files, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        found = dict(line.split(": eol: ") for line in result.stdout.strip().splitlines())
        self.assertEqual([f for f in files if found.get(f) != "lf"], [], "schema files must check out with LF")


BUT_BUILD = "0.23.1-3317"
BUT_URL = "https://releases.gitbutler.com/releases/release/%s/linux/x86_64/but" % BUT_BUILD
BUT_SHA256 = "57e442543839c912f164fb91a20ea934826fc0023ddf552a70f2ed63ba514a73"


def step_text(step):
    """The workflow lines of one named step (up to the next line at or left of its own indent)."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "- name: " + step), None)
    if start is None:
        raise AssertionError("the eval workflow has no step named %r" % step)
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) <= indent), len(lines))
    return "\n".join(lines[start:end])


def suite_job_header():
    """The suite job's lines before its steps (name, strategy, job-level env)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    job = text.split("\n  suite:\n", 1)[1]
    return job.split("\n    steps:\n", 1)[0]


class TestPinnedButWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.source = self.root / "source-but"
        self.curl_log = self.root / "curl.log"
        self.marker = self.root / "but-ran"
        self.github_path = self.root / "github-path"
        self.github_env = self.root / "github-env"
        self._make_tools()

    def _make_tools(self):
        curl = self.bin / "curl"
        with curl.open("w", encoding="utf-8", newline="\n") as script:
            script.write(
                "#!/usr/bin/env python3\n"
                "import os, shutil, sys\n"
                "args = sys.argv[1:]\n"
                "open(os.environ['BUT_TEST_CURL_LOG'], 'a', newline='\\n').write(' '.join(args) + '\\n')\n"
                "if '--output' in args:\n"
                "    out = args[args.index('--output') + 1]\n"
                "elif '-o' in args:\n"
                "    out = args[args.index('-o') + 1]\n"
                "else:\n"
                "    raise SystemExit('fake curl requires an output path')\n"
                "if not any(arg.startswith('https://') for arg in args):\n"
                "    raise SystemExit('fake curl requires the workflow download URL')\n"
                "shutil.copyfile(os.environ['BUT_TEST_SOURCE'], out)\n"
            )
        curl.chmod(0o755)
        # The downloaded file is a bare executable (an ELF upstream); a script stands in for it.
        with self.source.open("w", encoding="utf-8", newline="\n") as script:
            script.write('#!/bin/sh\necho ran > "$BUT_TEST_MARKER"\necho "but 0.23.1"\n')
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def run_install(self, checksum, overrides=None):
        env = {
            **os.environ,
            "RUNNER_TEMP": str(self.root / "runner-temp"),
            "GITHUB_PATH": str(self.github_path),
            "GITHUB_ENV": str(self.github_env),
            "BUT_TEST_BIN": str(self.bin),
            "BUT_VERSION": BUT_BUILD,
            "BUT_SHA256": checksum,
            "BUT_TEST_SOURCE": str(self.source),
            "BUT_TEST_CURL_LOG": str(self.curl_log),
            "BUT_TEST_MARKER": str(self.marker),
            **(overrides or {}),
        }
        env.pop("SPECWRIGHT_REQUIRE_BUT", None)
        (self.root / "runner-temp").mkdir(exist_ok=True)
        self.github_path.touch()
        self.github_env.touch()
        shell = (
            'if command -v cygpath >/dev/null 2>&1; then '
            'fake_bin="$(cygpath -u "$BUT_TEST_BIN")"; '
            'RUNNER_TEMP="$(cygpath -u "$RUNNER_TEMP")"; export RUNNER_TEMP; '
            'BUT_TEST_MARKER="$(cygpath -u "$BUT_TEST_MARKER")"; export BUT_TEST_MARKER; '
            'else fake_bin="$BUT_TEST_BIN"; fi\n'
            'PATH="$fake_bin:$PATH"\n'
            "export PATH\n"
            "hash -r\n"
            'curl() { "$fake_bin/curl" "$@"; }\n'
            + install_run_block("Install pinned but")
            + '\nexport PATH="$(cat "$GITHUB_PATH"):$PATH"\n'
            + "but --version\n"
        )
        bash = bashexe.bash()
        if not bash:
            self.skipTest("needs bash")
        return subprocess.run(
            [bash, "-euo", "pipefail", "-c", shell],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )

    def test_workflow_installs_pinned_but_for_vcs_on_linux_only(self):
        step = step_text("Install pinned but")
        self.assertRegex(step, r"if:\s*matrix\.suite == 'vcs' && runner\.os == 'Linux'\s*(\n|$)",
                         "only the Linux vcs job installs but")
        self.assertIn("#154", step, "the comment names the macOS/Windows gap issue")
        result = self.run_install(self.digest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.marker.exists(), "the installed but was run for its version")
        self.assertIn("0.23.1", result.stdout)
        # A build whose `but --version` names another version fails setup.
        result = self.run_install(self.digest, {"BUT_VERSION": "0.24.0-1"})
        self.assertNotEqual(result.returncode, 0, "setup must fail when but --version names another version")

    def test_but_requirement_is_set_on_linux_only(self):
        self.assertNotIn("SPECWRIGHT_REQUIRE_BUT", suite_job_header(), "no job-level SPECWRIGHT_REQUIRE_BUT")
        text = WORKFLOW.read_text(encoding="utf-8")
        steps = re.split(r"(?m)^(?=      - )", text.split("\n    steps:\n", 1)[1])
        setters = [s for s in steps if "SPECWRIGHT_REQUIRE_BUT=1" in s]
        self.assertEqual(len(setters), 1)
        self.assertRegex(setters[0], r"(?m)^\s+if: runner\.os == 'Linux'$")
        self.assertRegex(setters[0], r"SPECWRIGHT_REQUIRE_BUT=1\"? >> \"\$GITHUB_ENV\"")

    def test_install_steps_check_digests_without_sha256sum(self):
        # macOS has a BSD sha256sum without --check: both steps check the digest with Python, which runs the same on every OS
        for step in ("Install pinned jj", "Install pinned but"):
            with self.subTest(step=step):
                body = install_run_block(step)
                self.assertNotIn("sha256sum", body)
                self.assertIn("hashlib", body)

    def test_workflow_pins_but_build_url(self):
        self.assertEqual((ROOT / "BUT_VERSION").read_text(encoding="utf-8").strip(), BUT_BUILD)
        self.assertIn(BUT_SHA256, WORKFLOW.read_text(encoding="utf-8"))
        result = self.run_install(self.digest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = self.curl_log.read_text(encoding="utf-8").split()
        self.assertIn(BUT_URL, args)
        self.assertIn("--fail", args)

    def test_workflow_checks_but_sha256_before_use(self):
        result = self.run_install("0" * 64)
        self.assertNotEqual(result.returncode, 0, "a mismatched but download must fail setup")
        self.assertFalse(self.marker.exists(), "the but binary must not be run after a checksum mismatch")


if __name__ == "__main__":
    unittest.main()
