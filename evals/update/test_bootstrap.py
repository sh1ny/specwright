"""The README install prompt's bootstrap, run for real (native-cli-update, design D10, assumptions A4 and A5).

The first `sw` of a host comes from the agent, not from a script: Step 3 fetches the host's asset, `THIRD_PARTY_NOTICES.txt`
and `SHA256SUMS` with `curl`, checks both hashes, then makes the asset executable (POSIX), clears macOS quarantine and runs
`sw version --json`. This module runs those commands against the real `v0.36.0` release (the newest release with the asset
contract; its `sw` has no `update` command, so only `version --json` is run).

The commands are not copied here. They are read out of README.md, from the labelled lines of Step 3 (`- POSIX fetch: `...``,
`- PowerShell hash: `...`` and so on), so a README edit changes what this test runs and the two cannot drift. A command is
split on spaces (the lines carry no quotes or shell syntax, which the README text tests check) and started as an argument
list: no shell runs it, and the step's `PATH` holds one empty directory, so no `bash`, `sh` or Python is reachable. The
tools themselves (`curl`, `sha256sum`, `chmod`, `xattr`, PowerShell) are started by the absolute path found on the real
`PATH`. There is no wrapper that hands over to a real tool, so there is no PATH entry to drop and nothing that could run
inside itself.

The cases that touch the network run only where the network is meant to be used: in CI (`CI` set), or with
`SPECWRIGHT_BOOTSTRAP_NET=1`. Locally they skip.

Run (CI): python -m unittest evals/update/test_bootstrap.py
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
TAG = "v0.36.0"
VERSION = "0.36.0"
RELEASE = f"https://github.com/sh1ny/specwright/releases/download/{TAG}"
NOTICE = "THIRD_PARTY_NOTICES.txt"
SUMS = "SHA256SUMS"
NETWORK = bool(os.environ.get("CI")) or os.environ.get("SPECWRIGHT_BOOTSTRAP_NET") == "1"
NEEDS_NETWORK = "needs the network: runs in CI (CI set) or with SPECWRIGHT_BOOTSTRAP_NET=1"
WINDOWS = sys.platform == "win32"
FAMILY = "PowerShell" if WINDOWS else "POSIX"
# Interpreters that must not be reachable from the step's PATH. (bash is not first: see evals/runner/test_bare_bash.py.)
NO_INTERPRETER = ("python", "python3", "py", "bash", "sh")


def prompt():
    """The install prompt: the README's ```text block."""
    text = README.read_text(encoding="utf-8")
    start = text.index("```text\n") + len("```text\n")
    return text[start:text.index("\n```", start)]


def step3():
    text = prompt()
    start = text.index("\nStep 3 - ")
    return text[start:text.index("\nStep 4 - ", start)]


def bootstrap_commands():
    """label -> command template, from the labelled lines of Step 3. Each label appears once."""
    found = {}
    for m in re.finditer(r"^\s*- ((?:POSIX|PowerShell) [a-z ]+?): `([^`\n]+)`\s*$", step3(), re.M):
        assert m.group(1) not in found, f"README Step 3 labels {m.group(1)!r} twice"
        found[m.group(1)] = m.group(2)
    return found


def host_asset():
    """The release asset of this host, or None on a host with no target."""
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine().lower())
    system = "linux" if sys.platform.startswith("linux") else {"darwin": "macos", "win32": "windows"}.get(sys.platform)
    if not arch or not system:
        return None
    asset = f"sw-{system}-{arch}" + (".exe" if system == "windows" else "")
    return asset if asset in ("sw-linux-x64", "sw-linux-arm64", "sw-macos-arm64", "sw-macos-x64", "sw-windows-x64.exe") else None


def find_tool(name):
    """The absolute path of a tool on the real PATH. On Windows `curl.exe` is System32's (assumption A4)."""
    if WINDOWS and name.lower() in ("curl.exe", "curl"):
        system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "curl.exe"
        if system32.is_file():
            return str(system32)
    if WINDOWS and name == "powershell":
        ps = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if ps.is_file():
            return str(ps)
    return shutil.which(name)


class Bootstrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not NETWORK:
            raise unittest.SkipTest(NEEDS_NETWORK)
        cls.asset = host_asset()
        if cls.asset is None:
            raise unittest.SkipTest(f"platform: no release asset for {sys.platform} {platform.machine()}")
        if not find_tool("curl.exe" if WINDOWS else "curl"):
            raise AssertionError("curl is not installed: the prompt's bootstrap needs it (assumption A4)")
        cls.root = Path(tempfile.mkdtemp(prefix="bootstrap-eval-")).resolve()
        cls.addClassCleanup(shutil.rmtree, cls.root, True)
        cls.empty = cls.root / "empty-path"  # the step's PATH: one empty directory
        cls.empty.mkdir()
        cls.home = cls.root / "home"
        cls.home.mkdir()
        cls.commands = bootstrap_commands()
        cls.cache = cls.root / "cache"
        cls.cache.mkdir()
        cls.fetched = {}
        for name in (SUMS, cls.asset, NOTICE):
            cls.fetched[name] = cls.fetch(cls.cache, name)

    # The step's environment and the README's commands.

    @classmethod
    def env(cls):
        env = {k: v for k, v in os.environ.items() if k.upper() != "PATH"}
        env["PATH"] = str(cls.empty)
        env["SPECWRIGHT_HOME"] = str(cls.home)  # the placed-binary directory: nothing in the bootstrap may write there
        return env

    @classmethod
    def argv(cls, label, boot, file=None, release=RELEASE):
        """The README command `label` as an argument list: placeholders filled, the tool resolved to an absolute path."""
        values = {"boot": str(boot), "file": file or "", "asset": cls.asset, "release": release, "tag": TAG}
        out = []
        for token in cls.commands[label].split():
            for key, value in values.items():
                token = token.replace(f"<{key}>", value)
            out.append(token)
        first = out[0]
        if not (os.path.isabs(first) or "/" in first or "\\" in first):
            tool = find_tool(first)
            if not tool:
                raise AssertionError(f"README command {label!r} starts {first!r}, which is not installed")
            out[0] = tool
        return out

    @classmethod
    def run_command(cls, label, boot, file=None, release=RELEASE, extra=()):
        if label == "PowerShell hash":  # the one PowerShell cmdlet: run it as PowerShell would
            command = cls.commands[label].replace("<boot>", str(boot)).replace("<file>", file or "")
            argv = [find_tool("powershell"), "-NoProfile", "-NonInteractive", "-Command", command]
        else:
            argv = cls.argv(label, boot, file, release)
        return subprocess.run([*argv, *extra], env=cls.env(), capture_output=True, text=True, encoding="utf-8", timeout=180)

    @classmethod
    def fetch(cls, boot, name, release=RELEASE):
        r = cls.run_command(f"{FAMILY} fetch", boot, name, release)
        return r.returncode, r.stderr

    def first_hash(self, boot, name):
        """The README's hash command, tried as the Step 1 check orders them: the first word of the output, lowercase."""
        label = f"{FAMILY} hash"
        if not WINDOWS and not shutil.which("sha256sum"):
            label = "POSIX hash fallback"
        r = self.run_command(label, boot, name)
        self.assertEqual(r.returncode, 0, f"{label}: {r.stderr}")
        return r.stdout.split()[0].lower()

    @staticmethod
    def sums(boot):
        table = {}
        for line in (Path(boot) / SUMS).read_text(encoding="utf-8").splitlines():
            m = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line.strip())
            if m:
                table[m.group(2)] = m.group(1)
        return table

    # One boot directory per case, with the cached downloads copied in.

    def staged(self, notice=True):
        boot = Path(tempfile.mkdtemp(prefix="boot-", dir=self.root))
        for name in (SUMS, self.asset, *((NOTICE,) if notice else ())):
            shutil.copyfile(self.cache / name, boot / name)
        return boot

    def bootstrap(self, boot, notice_name=NOTICE):
        """Step 3 after the fetch, in the README's order. Returns the labels run; a stop deletes the file it names."""
        log = []
        table = self.sums(boot)
        asset = boot / self.asset
        self.assertIn(self.asset, table, "SHA256SUMS has no line for the host asset")
        notice = boot / notice_name
        if not notice.exists():  # the README's fetch: a release with no notice fails `curl -f` and nothing is run
            log.append(f"{FAMILY} fetch")
            r = self.run_command(f"{FAMILY} fetch", boot, notice_name)
            if r.returncode != 0:
                if notice.exists():
                    notice.unlink()
                log.append("stop: notice fetch")
                return log
        log.append(f"{FAMILY} hash {self.asset}")
        if self.first_hash(boot, self.asset) != table[self.asset]:
            asset.unlink()
            log.append("stop: asset hash")
            return log
        log.append(f"{FAMILY} hash {notice_name}")
        if self.first_hash(boot, notice_name) != table.get(notice_name):
            asset.unlink()  # the prompt deletes the temporary directory unrun
            log.append("stop: notice hash")
            return log
        if not WINDOWS:
            self.assertFalse(os.access(asset, os.X_OK), "a fresh download is not executable: the prompt must chmod it")
            r = self.run_command("POSIX chmod", boot, self.asset)
            self.assertEqual(r.returncode, 0, r.stderr)
            log.append("POSIX chmod")
            self.assertTrue(os.access(asset, os.X_OK))
            if sys.platform == "darwin":
                subprocess.run([find_tool("xattr"), "-w", "com.apple.quarantine", "0081;00000000;Eval;", str(asset)],
                               check=True, env=self.env())  # a browser download carries the flag; curl's does not
                r = self.run_command("POSIX quarantine check", boot, self.asset)
                self.assertIn("com.apple.quarantine", r.stdout)
                r = self.run_command("POSIX quarantine", boot, self.asset)
                self.assertEqual(r.returncode, 0, r.stderr)
                log.append("POSIX quarantine")
                r = self.run_command("POSIX quarantine check", boot, self.asset)
                self.assertNotIn("com.apple.quarantine", r.stdout)
        r = self.run_command(f"{FAMILY} run", boot, self.asset)
        self.assertEqual(r.returncode, 0, r.stderr)
        log.append(f"{FAMILY} run")
        self.version = json.loads(r.stdout)["version"]
        return log

    def assert_nothing_placed(self):
        self.assertEqual(list(self.home.iterdir()), [], "the bootstrap wrote under SPECWRIGHT_HOME")

    # The tests.

    def test_bootstrap_commands_without_bash_or_python(self):
        for name in NO_INTERPRETER:
            for candidate in (name, name + ".exe"):
                self.assertIsNone(shutil.which(candidate, path=str(self.empty)), f"{candidate} is on the step's PATH")
        self.assertEqual(self.env()["PATH"], str(self.empty))
        for label, command in self.commands.items():
            self.assertNotRegex(command, r"(?i)\b(bash|python3?|sh)\b", f"{label} names an interpreter")
            plain = re.sub(r"<[a-z]+>", "", command)
            if label != "PowerShell hash":  # the cmdlet's own parentheses are PowerShell, not a shell's grouping
                self.assertNotRegex(plain, r"[|&;<>$`()]", f"{label} holds shell syntax")
        wanted = {"POSIX fetch", "POSIX hash", "POSIX hash fallback", "POSIX chmod", "POSIX quarantine check",
                  "POSIX quarantine", "POSIX run", "PowerShell fetch", "PowerShell hash", "PowerShell run"}
        self.assertEqual(set(self.commands), wanted)
        boot = self.staged()
        log = self.bootstrap(boot)
        self.assertEqual(log[-1], f"{FAMILY} run")
        self.assertEqual(self.version, VERSION)
        self.assert_nothing_placed()

    def test_bootstrap_hashes_then_chmods_then_runs(self):
        s3 = step3()
        for labels in (("POSIX fetch", "POSIX hash", "POSIX chmod", "POSIX quarantine check", "POSIX quarantine", "POSIX run"),
                       ("PowerShell fetch", "PowerShell hash", "PowerShell run")):
            order = [s3.index(f"- {label}:") for label in labels]
            self.assertEqual(order, sorted(order), f"the README does not give {labels} in that order")
        self.assertIn(self.asset, s3, "the README does not name this host's asset")
        boot = self.staged()
        log = self.bootstrap(boot)
        hashes = [i for i, e in enumerate(log) if " hash " in e]
        self.assertEqual(len(hashes), 2, "both the asset and the notice are hashed")
        if not WINDOWS:
            self.assertLess(max(hashes), log.index("POSIX chmod"), "chmod ran before both hashes")
            self.assertLess(log.index("POSIX chmod"), log.index("POSIX run"))
        self.assertLess(max(hashes), log.index(f"{FAMILY} run"))
        self.assertEqual(self.version, VERSION)
        self.assert_nothing_placed()

    def test_bootstrap_hash_mismatch_never_runs(self):
        boot = self.staged()
        with open(boot / self.asset, "ab") as f:
            f.write(b"\0")  # one byte more than the release
        log = self.bootstrap(boot)
        self.assertEqual(log[-1], "stop: asset hash", log)
        self.assertFalse((boot / self.asset).exists(), "the mismatched file was not deleted")
        for ran in ("POSIX chmod", "POSIX quarantine", f"{FAMILY} run"):
            self.assertNotIn(ran, log)
        self.assert_nothing_placed()

    def test_bootstrap_bad_notice_never_runs(self):
        with self.subTest("notice with another hash"):
            boot = self.staged()
            with open(boot / NOTICE, "ab") as f:
                f.write(b"\n")
            log = self.bootstrap(boot)
            self.assertEqual(log[-1], "stop: notice hash", log)
            self.assertFalse((boot / self.asset).exists())
            for ran in ("POSIX chmod", "POSIX quarantine", f"{FAMILY} run"):
                self.assertNotIn(ran, log)
        with self.subTest("release with no notice"):
            boot = self.staged(notice=False)
            log = self.bootstrap(boot, notice_name="THIRD_PARTY_NOTICES-absent.txt")
            self.assertEqual(log[-1], "stop: notice fetch", log)
            self.assertFalse((boot / "THIRD_PARTY_NOTICES-absent.txt").exists(), "the partial file was not deleted")
            if not WINDOWS:
                self.assertFalse(os.access(boot / self.asset, os.X_OK), "the asset was made executable")
            for ran in ("POSIX chmod", "POSIX quarantine", f"{FAMILY} run"):
                self.assertNotIn(ran, log)
        self.assert_nothing_placed()

    def test_bootstrap_fetch_follows_https_redirect(self):
        for name, (code, err) in self.fetched.items():
            self.assertEqual(code, 0, f"the README fetch of {name} failed: {err}")
            self.assertGreater((self.cache / name).stat().st_size, 0, name)
        self.assertLess((self.cache / self.asset).stat().st_size, 64 * 1024 * 1024)
        self.assertIn(self.asset, self.sums(self.cache))
        # GitHub answers a release download with a redirect to its https asset host: count it on the small file.
        boot = Path(tempfile.mkdtemp(prefix="redirect-", dir=self.root))
        r = self.run_command(f"{FAMILY} fetch", boot, SUMS, extra=("-s", "-w", "%{num_redirects}"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertGreaterEqual(int(r.stdout.strip()), 1, "the release URL did not redirect: this case proves nothing")


class BootstrapRefusals(unittest.TestCase):
    """The README's curl line refuses a start URL that is not https, with no network use."""

    def test_bootstrap_fetch_refuses_http_start_url(self):
        self.assertTrue(find_tool("curl.exe" if WINDOWS else "curl"), "curl is not installed: the prompt's bootstrap needs it (assumption A4)")
        commands = bootstrap_commands()
        template = commands[f"{FAMILY} fetch"]
        self.assertIn("--proto =https", template)
        with tempfile.TemporaryDirectory(prefix="bootstrap-http-") as d:
            out = Path(d) / "x"
            argv = [t.replace("<boot>", d).replace("<file>", "x").replace("<release>", "http://127.0.0.1:9/never")
                    for t in template.split()]
            argv[0] = find_tool(argv[0])
            r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertNotEqual(r.returncode, 0, "curl followed an http start URL")
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
