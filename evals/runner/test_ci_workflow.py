"""Execute the pinned-jj and pinned-but workflow setup steps against a local archive / file and fake binaries."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "evals.yml"


def git_bash():
    if os.name != "nt":
        return shutil.which("bash")
    candidates = [os.environ.get("GIT_BASH")]
    scoop = os.environ.get("SCOOP")
    if scoop:
        candidates.append(str(Path(scoop) / "apps" / "git" / "current" / "bin" / "bash.exe"))
    profile = os.environ.get("USERPROFILE")
    if profile:
        candidates.append(str(Path(profile) / "scoop" / "apps" / "git" / "current" / "bin" / "bash.exe"))
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(variable)
        if root:
            candidates.append(str(Path(root) / "Git" / "bin" / "bash.exe"))
    return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)


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


class TestPinnedJjWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.source_archive = self.root / "source.tar.gz"
        self.marker = self.root / "jj-ran.json"
        self.github_path = self.root / "github-path"
        self.github_env = self.root / "github-env"
        self._make_tools()
        self._make_archive()

    def _make_tools(self):
        curl = self.bin / "curl"
        with curl.open("w", encoding="utf-8", newline="\n") as script:
            script.write(
                "#!/usr/bin/env python3\n"
                "import os, shutil, sys\n"
                "args = sys.argv[1:]\n"
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

    def _make_archive(self):
        binary_dir = self.root / "archive-content"
        binary_dir.mkdir()
        binary = binary_dir / "jj"
        with binary.open("w", encoding="utf-8", newline="\n") as script:
            script.write(
                "#!/usr/bin/env python3\n"
                "import json, os\n"
                "open(os.environ['JJ_TEST_MARKER'], 'w', newline='\\n').write(json.dumps({'required': os.environ.get('SPECWRIGHT_REQUIRE_JJ'), 'version': 'jj 0.46.0'}))\n"
                "print('jj 0.46.0')\n"
            )
        binary.chmod(0o755)
        with tarfile.open(self.source_archive, "w:gz") as archive:
            archive.add(binary, arcname="jj")
        self.digest = hashlib.sha256(self.source_archive.read_bytes()).hexdigest()

    def run_install(self, checksum):
        env = {
            **os.environ,
            "PATH": os.environ.get("PATH", ""),
            "RUNNER_TEMP": str(self.root / "runner-temp"),
            "GITHUB_PATH": str(self.github_path),
            "GITHUB_ENV": str(self.github_env),
            "JJ_TEST_BIN": str(self.bin),
            "JJ_VERSION": "0.46.0",
            "JJ_SHA256": checksum,
            "JJ_TEST_ARCHIVE": str(self.source_archive),
            "JJ_TEST_MARKER": str(self.marker),
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
            + "jj --version\n"
        )
        return subprocess.run(
            [git_bash() or "bash", "-euo", "pipefail", "-c", shell],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )

    def test_workflow_installs_pinned_jj_and_requires_it(self):
        result = self.run_install(self.digest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.marker.read_text(encoding="utf-8")), {"required": "1", "version": "jj 0.46.0"})
        self.assertIn("0.46.0", result.stdout)

    def test_workflow_checks_jj_sha256_before_use(self):
        result = self.run_install("0" * 64)
        self.assertNotEqual(result.returncode, 0, "a mismatched jj archive must fail setup")
        self.assertFalse(self.marker.exists(), "the jj binary must not be used after a checksum mismatch")


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
        return subprocess.run(
            [git_bash() or "bash", "-euo", "pipefail", "-c", shell],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )

    def test_workflow_installs_pinned_but_for_vcs_only(self):
        step = step_text("Install pinned but")
        self.assertRegex(step, r"if:\s*matrix\.suite == 'vcs'", "only the vcs job installs but")
        self.assertRegex(suite_job_header(), r"SPECWRIGHT_REQUIRE_BUT:\s*['\"]?1['\"]?\s*(\n|$)",
                         "every suite job requires but (job-level env)")
        result = self.run_install(self.digest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.marker.exists(), "the installed but was run for its version")
        self.assertIn("0.23.1", result.stdout)
        # A build whose `but --version` names another version fails setup.
        result = self.run_install(self.digest, {"BUT_VERSION": "0.24.0-1"})
        self.assertNotEqual(result.returncode, 0, "setup must fail when but --version names another version")

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
