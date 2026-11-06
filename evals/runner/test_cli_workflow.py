"""Text checks on .github/workflows/cli.yml and the sw-build.yml it calls (stdlib only, no YAML parser): the per-platform sw
build, artifact and download-and-run."""
import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "cli.yml"
BUILD = WORKFLOWS / "sw-build.yml"  # the jobs live here; cli.yml (pull requests) and release.yml call it
OSES = ["ubuntu-24.04", "ubuntu-24.04-arm", "windows-latest", "macos-latest", "macos-15-intel"]


def read(path=WORKFLOW):
    return path.read_text(encoding="utf-8")


def job_block(name):
    m = re.search(r"(?ms)^  %s:\n(.*?)(?=^  \S|\Z)" % re.escape(name), read(BUILD))
    if not m:
        raise AssertionError("no job %r in %s" % (name, BUILD))
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
        for path in ("cli/**", "mise.toml", "VERSION", ".github/workflows/cli.yml", ".github/workflows/sw-build.yml"):
            self.assertIn(path, t.split("\njobs:\n", 1)[0], "the trigger paths name %s" % path)
        self.assertRegex(t.split("\njobs:\n", 1)[1], r"(?m)^    uses: \./\.github/workflows/sw-build\.yml$")
        for name in ("build", "verify"):
            job = job_block(name)
            self.assertEqual(re.findall(r"(?m)^          - os: (\S+)$", job), OSES, "%s: one matrix row per platform" % name)
            self.assertIn("runs-on: ${{ matrix.os }}", job)
        self.assertRegex(job_block("verify"), r"(?m)^    needs: build$")

        build = job_block("build")
        mise = [s for s in steps(build) if "uses: jdx/mise-action@" in s]
        self.assertEqual(len(mise), 1)
        # The release binaries are built here: a third-party action runs pinned to a reviewed commit, its tag in a comment.
        self.assertRegex(mise[0], r"uses: jdx/mise-action@[0-9a-f]{40} # v\d+\.\d+\.\d+\s")
        for owner in re.findall(r"(?m)^\s+(?:- )?uses: ([\w.-]+)/\S+@(\S+)", read(BUILD)):
            if owner[0] not in ("actions",):
                self.assertRegex(owner[1], r"^[0-9a-f]{40}$", "%s actions run pinned to a commit SHA" % owner[0])
        self.assertRegex(mise[0], r"version: '?2026\.10\.12'?\s")
        for task in ("mise run deps", "mise run analyze", "mise run format", "mise run test", "mise run build"):
            self.assertIn(task, build)
        # A fresh checkout has no package config: analyze resolves no import until the dependencies are fetched.
        self.assertLess(build.index("mise run deps"), build.index("mise run analyze"))
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
