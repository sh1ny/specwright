"""Execute the pinned-jj workflow setup step against a local archive and fake jj binary."""
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


def install_run_block():
    """Return the shell body of the named install step, rather than duplicating its commands in the test."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "- name: Install pinned jj":
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
    raise AssertionError("the eval workflow has no named pinned-jj install step")


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


if __name__ == "__main__":
    unittest.main()
