"""The CLI build workflows: contract and artifact checks (standard library, no YAML parser).

sw-build.yml is the one build-and-check workflow that pull requests (cli.yml) and releases (release.yml) both call.
"""
import shutil
import subprocess
import tempfile
import textwrap
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

TARGETS = {
    "linux-x64": "ubuntu-24.04",
    "linux-arm64": "ubuntu-24.04-arm",
    "windows-x64": "windows-latest",
    "macos-arm64": "macos-latest",
    "macos-x64": "macos-15-intel",
}


def read(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def block(text, header, indent):
    """The lines under `header:` at `indent` spaces, up to the next line indented no deeper than it."""
    lines = text.splitlines()
    start = None
    for number, line in enumerate(lines):
        if line == " " * indent + header + ":":
            start = number + 1
            break
    if start is None:
        return ""
    out = []
    for line in lines[start:]:
        if line.strip() and not line.startswith(" " * (indent + 1)):
            break
        out.append(line)
    return "\n".join(out)


def job(text, name):
    return block(text, name, 2)


class SwBuildTests(unittest.TestCase):
    def package(self, version, notice=True, target="linux-x64"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "cli/build").mkdir(parents=True)
        (root / "VERSION").write_text(version + "\n")
        ext = ".exe" if target.startswith("windows") else ""
        (root / ("cli/build/sw" + ext)).write_bytes(b"binary")
        source = ROOT / "cli/THIRD_PARTY_NOTICES.txt"
        if notice:
            (root / "cli/THIRD_PARTY_NOTICES.txt").write_bytes(source.read_bytes())
        text = read("sw-build.yml")
        step = text.split("      - name: Name the artifact and write its SHA-256\n", 1)[1].split("      - uses:", 1)[0]
        script = textwrap.dedent(step.split("run: |\n", 1)[1])
        script = script.replace("${{ matrix.target }}", target).replace("${{ matrix.ext }}", ext)
        bash = shutil.which("bash")
        self.assertIsNotNone(bash, "workflow fixture needs bash")
        result = subprocess.run([bash, "-e", "-c", script], cwd=root, capture_output=True, text=True, timeout=60)
        return root, result

    def test_build_packages_identical_notice(self):
        import hashlib
        expected = (ROOT / "cli/THIRD_PARTY_NOTICES.txt").read_bytes()
        self.assertNotIn(b"\r", expected)
        self.assertIn("cli/THIRD_PARTY_NOTICES.txt text eol=lf", (ROOT / ".gitattributes").read_text())
        for target in TARGETS:
            root, result = self.package("0.30.0", target=target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / "dist/THIRD_PARTY_NOTICES.txt").read_bytes(), expected)
            self.assertEqual((root / "dist/THIRD_PARTY_NOTICES.txt.sha256").read_text(),
                             hashlib.sha256(expected).hexdigest() + "  THIRD_PARTY_NOTICES.txt\n")
        root, result = self.package("0.30.0", notice=False)
        self.assertNotEqual(result.returncode, 0)

    def test_older_tag_build_requires_no_notice(self):
        # Numeric comparison also handles 0.9.0 correctly.
        for version in ("0.29.0", "0.9.0"):
            root, result = self.package(version, notice=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(sorted(p.name for p in (root / "dist").iterdir()),
                             ["sw-linux-x64", "sw-linux-x64.sha256"])

    def test_build_matrix_has_five_native_targets(self):
        text = read("sw-build.yml")
        for name in ("build", "verify"):
            body = job(text, name)
            self.assertTrue(body, "sw-build.yml has no %s job" % name)
            pairs = dict(
                (target, os_name)
                for os_name, target in re.findall(r"-\s+os:\s*(\S+)\s*\n\s+target:\s*(\S+)", body)
            )
            self.assertEqual(pairs, TARGETS, "%s job matrix" % name)

    def test_matrix_is_not_fail_fast(self):
        text = read("sw-build.yml")
        for name in ("build", "verify"):
            self.assertRegex(job(text, name), r"fail-fast:\s*false", "%s job" % name)

    def test_release_verify_checks_interface(self):
        body = job(read("sw-build.yml"), "verify")
        step = re.search(r"python cli/tool/verify_artifact\.py(?:(?!\n\s+- ).)*--interface-from skills/specwright-pr/scripts/sw-path\.sh",
                         body, re.S)
        self.assertTrue(step, "the verify job passes --interface-from sw-path.sh to verify_artifact.py")

    def test_workflow_call_takes_a_required_ref(self):
        text = read("sw-build.yml")
        self.assertIn("workflow_call:", text)
        ref = block(block(block(block(text, "on", 0), "workflow_call", 2), "inputs", 4), "ref", 6)
        self.assertRegex(ref, r"required:\s*true")
        self.assertRegex(ref, r"type:\s*string")
        self.assertIn("ref: ${{ inputs.ref }}", text)

    def test_cli_calls_the_shared_build(self):
        text = read("cli.yml")
        self.assertRegex(text, r"uses:\s*\./\.github/workflows/sw-build\.yml")


class ReleaseTests(unittest.TestCase):
    def test_release_concurrency_queues_per_tag(self):
        text = read("release.yml")
        concurrency = block(text, "concurrency", 0)
        group = re.search(r"group:\s*(.+)", concurrency)
        self.assertTrue(group, "release.yml has a concurrency group")
        self.assertIn("github.event.release.tag_name", group.group(1))
        self.assertIn("inputs.tag", group.group(1))
        self.assertRegex(concurrency, r"cancel-in-progress:\s*false")

    def test_attach_needs_every_verify_job(self):
        text = read("release.yml")
        jobs = block(text, "jobs", 0) + "\n"  # not the `on:` triggers, which also sit at two spaces (release:)
        build = re.search(r"^  (\w[\w-]*):\s*\n(?:\s+.*\n)*?\s+uses:\s*\./\.github/workflows/sw-build\.yml", jobs, re.M)
        self.assertTrue(build, "release.yml calls sw-build.yml")
        needs = re.search(r"needs:\s*(.+)", job(text, "attach"))
        self.assertTrue(needs, "the attach job has needs")
        self.assertIn(build.group(1), needs.group(1))

    def test_only_attach_can_write(self):
        text = read("release.yml")
        top = block(text, "permissions", 0)
        self.assertRegex(top, r"contents:\s*read")
        self.assertNotRegex(top, r"contents:\s*write")
        self.assertRegex(job(text, "attach"), r"contents:\s*write")
        writers = [m.start() for m in re.finditer(r"contents:\s*write", text)]
        attach_start = text.index("\n  attach:")
        attach_end = attach_start + 1 + len(job(text, "attach")) + len("  attach:")
        for position in writers:
            self.assertTrue(attach_start <= position <= attach_end + 1, "contents: write outside the attach job")


if __name__ == "__main__":
    unittest.main()
