"""Text checks on .github/workflows/cli.yml (stdlib only, no YAML parser): the per-OS sw build, artifact and download-and-run."""
import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "cli.yml"
OSES = ["ubuntu-24.04", "windows-latest", "macos-latest"]


def read():
    return WORKFLOW.read_text(encoding="utf-8")


def job_block(name):
    m = re.search(r"(?ms)^  %s:\n(.*?)(?=^  \S|\Z)" % re.escape(name), read())
    if not m:
        raise AssertionError("no job %r in %s" % (name, WORKFLOW))
    return m.group(1)


def steps(job):
    """The job's steps as text blocks, in order."""
    return re.split(r"(?m)^(?=      - )", job.split("\n    steps:\n", 1)[1])


def step(job, name):
    for s in steps(job):
        if re.match(r"\s+- (name: %s|.*\n\s+name: %s)\n" % (re.escape(name), re.escape(name)), s):
            return s
    raise AssertionError("no step named %r" % name)


class TestCliWorkflow(unittest.TestCase):
    def test_cli_workflow_builds_tests_and_verifies_each_os(self):
        t = read()
        self.assertRegex(t, r"(?m)^on:\n(?:  .*\n)*?  pull_request:")
        self.assertRegex(t, r"(?m)^on:\n(?:  .*\n)*?  workflow_dispatch:")
        for path in ("cli/**", "mise.toml", "VERSION", ".github/workflows/cli.yml"):
            self.assertIn(path, t.split("\njobs:\n", 1)[0], "the trigger paths name %s" % path)
        for name in ("build", "verify"):
            job = job_block(name)
            matrix_os = re.search(r"(?m)^\s+os: \[([^\]]*)\]$", job)
            self.assertIsNotNone(matrix_os, "%s: matrix.os must be an inline list" % name)
            self.assertEqual([o.strip() for o in matrix_os.group(1).split(",")], OSES)
            self.assertIn("runs-on: ${{ matrix.os }}", job)
        self.assertRegex(job_block("verify"), r"(?m)^    needs: build$")

        build = job_block("build")
        mise = [s for s in steps(build) if "uses: jdx/mise-action@" in s]
        self.assertEqual(len(mise), 1)
        self.assertRegex(mise[0], r"uses: jdx/mise-action@v\d+\s")
        self.assertRegex(mise[0], r"version: '?2026\.10\.12'?\s")
        for task in ("mise run analyze", "mise run format", "mise run test", "mise run build"):
            self.assertIn(task, build)
        self.assertLess(build.index("mise run analyze"), build.index("mise run build"))
        self.assertIn("sha256", build)
        self.assertRegex(build, r"actions/upload-artifact@v\d+")

        verify = job_block("verify")
        self.assertRegex(verify, r"actions/download-artifact@v\d+")
        self.assertIn("cli/tool/verify_artifact.py", verify)
        self.assertNotIn("continue-on-error", verify)
        self.assertNotIn("continue-on-error", build)

    def test_macos_verify_sets_quarantine_and_applies_step(self):
        verify = job_block("verify")
        parts = steps(verify)

        def index(fragment):
            hits = [i for i, s in enumerate(parts) if fragment in s]
            self.assertTrue(hits, "no verify step contains %r" % fragment)
            return hits[0]

        quarantine, remove, final = (index("xattr -w com.apple.quarantine"), index("xattr -d com.apple.quarantine"),
                                     len(parts) - 1)
        self.assertLess(quarantine, remove)
        self.assertLess(remove, final)
        self.assertIn("--checksum-only", verify)
        self.assertLess(index("--checksum-only"), quarantine, "the checksum is checked before the file is run")
        for i in (quarantine, remove):
            self.assertRegex(parts[i], r"(?m)^\s+if: runner\.os == 'macOS'$")
        # A2: whether the quarantined binary ran before the step is logged, not asserted.
        self.assertRegex(parts[quarantine], r"ran before the step")
        self.assertRegex(parts[quarantine], r"did not run before the step")
        self.assertIn("cli/tool/verify_artifact.py", parts[final])

    def test_macos_verify_fails_when_step_does_not_unblock(self):
        verify = job_block("verify")
        parts = steps(verify)
        remove = next(s for s in parts if "xattr -d com.apple.quarantine" in s)
        # the removal must not be tolerated, and the attribute must be gone afterwards
        self.assertNotRegex(remove, r"xattr -d com\.apple\.quarantine[^\n]*(\|\||;\s*true)")
        self.assertRegex(remove, r"(?s)xattr -p com\.apple\.quarantine.*exit 1")
        # the final run is the plain, required verification of the unquarantined file
        final = parts[-1]
        self.assertNotRegex(final, r"\|\||;\s*true|continue-on-error")
        self.assertNotIn("--checksum-only", final)
        self.assertNotIn("quarantine", final)


if __name__ == "__main__":
    unittest.main()
