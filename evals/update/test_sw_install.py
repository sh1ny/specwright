"""Black-box tests for `update.sh sw-install` and the `sw` field of `plan` (native-cli-distribution, design D1, D3, D7, D8).

A fixture release lives in a directory served through `--release-url file://...` (laid out as
<base>/releases/download/<tag>/<asset>): the binary named by SPECWRIGHT_SW under the host's asset name plus a SHA256SUMS
file. Stalls, oversized answers and redirects come from a local http.server thread (127.0.0.1, port 0). The 120 s
deadline and the 64 MiB bound are made short with SPECWRIGHT_NET_DEADLINE and SPECWRIGHT_NET_MAX_BYTES, which bounded.py
already lets a test lower (the sw download reads the same variables, so no new option exists for them).
Test-only variables read by update.sh (never needed in production):
  SPECWRIGHT_TEST_HOST     `<system>/<machine>` in place of platform.system()/machine(), e.g. `Windows/ARM64`
  SPECWRIGHT_TEST_RENAME   `die` (exit between the checks and the rename), `fail` (the rename is blocked) or `race`
                           (another run places the final file, then the rename is blocked)

Run: SPECWRIGHT_SW=<path> python -m unittest evals/update/test_sw_install.py
"""
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evals" / "cli"))
sys.path.insert(0, str(ROOT / "evals"))
import swharness  # noqa: E402
import bashexe  # noqa: E402

_spec = importlib.util.spec_from_file_location("update_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

WINDOWS = os.name == "nt"
EXE = "sw.exe" if WINDOWS else "sw"
SWPATH_REL = Path("skills") / "specwright-pr" / "scripts" / "sw-path.sh"
TARGETS = ("linux-x64", "linux-arm64", "windows-x64", "macos-arm64", "macos-x64")
STOP = "sw missing or mismatched: rerun the install prompt"


def asset_of(target):
    return "sw-" + target + (".exe" if target.startswith("windows") else "")


def native_target():
    """The test's own idea of this host's target (not update.sh's code), or None."""
    import platform
    system = {"linux": "linux", "darwin": "macos", "windows": "windows"}.get(platform.system().lower())
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower())
    target = "%s-%s" % (system, arch)
    return target if target in TARGETS else None


def sha(data):
    return hashlib.sha256(data).hexdigest()


def files(path):
    """{relative path: (bytes, mtime_ns, mode)} of the files under path (directories are not listed)."""
    out = {}
    for p in sorted(Path(path).rglob("*")):
        if p.is_file():
            st = p.stat()
            out[p.relative_to(path).as_posix()] = (p.read_bytes(), st.st_mtime_ns, stat.S_IMODE(st.st_mode))
    return out


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.sw = swharness.require_sw()
        if not bashexe.bash():
            self.skipTest("no bash installed")
        self.target = native_target()
        if self.target is None:
            self.skipTest("this host has no sw target")
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-install-")).resolve()
        self.addCleanup(fx.rmtree, self.tmp)
        report = json.loads(subprocess.run([self.sw, "version", "--json"], capture_output=True, text=True, timeout=60).stdout)
        self.version, self.interface = report["version"], report["interface"]
        self.tag = "v" + self.version
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.bin = self.home / ".specwright" / "bin" / self.version
        self.final = self.bin / EXE
        self.binary = Path(self.sw).read_bytes()
        self.code = self.tmp / "code"
        self.code.mkdir()
        self.rel = self.tmp / "rel"
        self.dl = self.make_download(self.tmp / "dl")
        self.base = self.rel.as_uri()
        self.servers = []

    def make_download(self, dest, version=None):
        """The part of a download sw-install reads: update.sh, the resolver and bounded.py, VERSION."""
        dest = Path(dest)
        shutil.copytree(ROOT / "scripts", dest / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "skills" / "specwright-pr" / "scripts", dest / SWPATH_REL.parent,
                        ignore=shutil.ignore_patterns("__pycache__"))
        (dest / "VERSION").write_text((version or self.version) + "\n", encoding="utf-8", newline="")
        return dest

    def edit_swpath(self, old, new, dl=None):
        p = (dl or self.dl) / SWPATH_REL
        data = p.read_bytes()
        assert old.encode() in data
        p.write_bytes(data.replace(old.encode(), new.encode(), 1))

    # --- the fixture release ---

    def sums(self, binary=None, target=None, hash_override=None):
        """SHA256SUMS text: five lines, the host's real (or overridden) and four made up."""
        target = target or self.target
        lines = []
        for t in TARGETS:
            h = (hash_override or sha(binary if binary is not None else self.binary)) if t == target else sha(t.encode())
            lines.append("%s  %s" % (h, asset_of(t)))
        return "\n".join(sorted(lines, key=lambda l: l.split("  ")[1])) + "\n"

    def release(self, binary=None, target=None, sums=True, asset=True, sums_text=None, tag=None):
        target = target or self.target
        d = self.rel / "releases" / "download" / (tag or self.tag)
        d.mkdir(parents=True, exist_ok=True)
        if asset:
            (d / asset_of(target)).write_bytes(self.binary if binary is None else binary)
        if sums:
            (d / "SHA256SUMS").write_text(sums_text if sums_text is not None else self.sums(binary, target), encoding="utf-8", newline="")
        return d

    def serve(self, **behaviour):
        """A local http.server over self.rel. behaviour: stall={names}, big={name: bytes}, redirect={name: url}."""
        rel, stop = self.rel, threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                name = self.path.rsplit("/", 1)[-1]
                if name in behaviour.get("stall", ()):
                    self.send_response(200)
                    self.send_header("Content-Length", "100")
                    self.end_headers()
                    self.wfile.flush()
                    stop.wait(120)
                    return
                if name in behaviour.get("redirect", {}):
                    self.send_response(302)
                    self.send_header("Location", behaviour["redirect"][name])
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if name in behaviour.get("big", {}):
                    body = b"\0" * behaviour["big"][name]
                else:
                    f = rel / self.path.lstrip("/")
                    if not f.is_file():
                        self.send_error(404)
                        return
                    body = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except OSError:
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        server.block_on_close = False
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def close():
            stop.set()
            server.shutdown()
            server.server_close()
            thread.join(10)
        self.addCleanup(close)
        return "http://127.0.0.1:%d" % server.server_address[1]

    # --- running ---

    def env(self, **extra):
        env = swharness.fixture_env(SPECWRIGHT_HOME=self.home.as_posix(), **extra)
        return env

    def sw_install(self, ref="tag", base=None, dl=None, env=None, **extra):
        args = ["--code", fx.posix(self.code), "--download", fx.posix(dl or self.dl), "--ref", self.tag if ref == "tag" else ref]
        if base is not False:
            args += ["--release-url", base or self.base]
        args.append("sw-install")
        return fx.run_update(dl or self.dl, args, env=env or self.env(**extra), timeout=240)

    def installed(self, **extra):
        code, doc, out, err = self.sw_install(**extra)
        self.assertEqual(code, 0, out + err)
        self.assertTrue(doc["ok"], doc)
        return doc

    def stopped(self, error, *mentions, **kw):
        code, doc, out, err = self.sw_install(**kw)
        self.assertEqual(code, 1, out + err)
        self.assertFalse(doc["ok"], doc)
        self.assertEqual(doc["error"], error, doc)
        for m in mentions:
            self.assertIn(m, doc["message"])
        return doc

    def assert_nothing_placed(self):
        self.assertEqual(files(self.home), {}, "no file may be placed or left under the home")

    def reported_version(self, path):
        r = subprocess.run([str(path), "version", "--json"], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["version"]


class TestInstall(Base):
    def test_tag_install_places_checked_binary(self):
        self.release()
        doc = self.installed()
        self.assertEqual(doc["action"], "installed")
        self.assertEqual(doc["asset"], asset_of(self.target))
        self.assertEqual(doc["version"], self.version)
        self.assertEqual(doc["interface"], 2)
        self.assertTrue(os.path.samefile(doc["path"], self.final), doc["path"])
        self.assertEqual(self.final.read_bytes(), self.binary)
        if not WINDOWS:
            self.assertTrue(os.access(self.final, os.X_OK))
        self.assertEqual(self.reported_version(self.final), self.version)
        self.assertEqual(sorted(p.name for p in self.bin.iterdir()), [EXE], "no part file may be left")

    def test_specwright_home_is_the_root(self):
        self.release()
        fake = self.tmp / "userhome"
        fake.mkdir()
        self.installed(HOME=fake.as_posix(), USERPROFILE=fake.as_posix())
        self.assertTrue(self.final.is_file())
        self.assertEqual(list(fake.iterdir()), [], "nothing is written under the user's home")

    def test_unsupported_platform_stops(self):
        self.release()
        doc = self.stopped("unsupported_platform", "Windows", "ARM64", *TARGETS, SPECWRIGHT_TEST_HOST="Windows/ARM64")
        self.assertFalse(doc["ok"])
        self.assert_nothing_placed()

    def test_quarantine_cleared_after_checksum(self):
        marker, shims = self.tmp / "marker", self.tmp / "shims"
        shims.mkdir()
        # the flag is present until -d removes it, so the probe after the removal finds it gone
        if WINDOWS:  # found through shutil.which, so a .cmd shim stands in for xattr
            (shims / "xattr.cmd").write_text('@echo off\r\necho XATTR %1 %2>>"%SW_MARKER%"\r\n'
                                             'if "%1"=="-d" type nul > "%SW_MARKER%.cleared"\r\n'
                                             'if "%1"=="-p" if exist "%SW_MARKER%.cleared" exit /b 1\r\nexit /b 0\r\n')
        else:
            (shims / "xattr").write_text('#!/bin/sh\necho "XATTR $1 $2" >> "$SW_MARKER"\ncase "$1" in\n'
                                         '  -p) [ -f "$SW_MARKER.cleared" ] && exit 1; echo 0081 ;;\n'
                                         '  -d) : > "$SW_MARKER.cleared" ;;\nesac\nexit 0\n')
            (shims / "xattr").chmod(0o755)
        self.edit_swpath("set -uo pipefail", 'set -uo pipefail\necho SWPATH >> "$SW_MARKER"')
        self.release(target="macos-arm64")
        self.installed(SPECWRIGHT_TEST_HOST="Darwin/arm64", SW_MARKER=marker.as_posix(),
                       PATH=str(shims) + os.pathsep + os.environ["PATH"])
        log = marker.read_text().splitlines()
        self.assertIn("XATTR -d com.apple.quarantine", log)
        self.assertLess(log.index("XATTR -d com.apple.quarantine"), log.index("SWPATH"), "removal comes before the first run")

    def test_failed_quarantine_removal_stops_before_running(self):
        marker, shims = self.tmp / "marker", self.tmp / "shims"
        shims.mkdir()
        if WINDOWS:  # found through shutil.which, so a .cmd shim stands in for xattr
            (shims / "xattr.cmd").write_text('@echo off\r\necho XATTR %1 %2>>"%SW_MARKER%"\r\nif "%1"=="-p" exit /b 0\r\nexit /b 1\r\n')
        else:
            (shims / "xattr").write_text('#!/bin/sh\necho "XATTR $1 $2" >> "$SW_MARKER"\ncase "$1" in -p) exit 0;; esac\nexit 1\n')
            (shims / "xattr").chmod(0o755)
        self.edit_swpath("set -uo pipefail", 'set -uo pipefail\necho SWPATH >> "$SW_MARKER"')
        self.release(target="macos-arm64")
        self.stopped("quarantine_not_cleared", asset_of("macos-arm64"), self.tag, SPECWRIGHT_TEST_HOST="Darwin/arm64",
                     SW_MARKER=marker.as_posix(), PATH=str(shims) + os.pathsep + os.environ["PATH"])
        log = marker.read_text().splitlines()
        self.assertIn("XATTR -d com.apple.quarantine", log)
        self.assertNotIn("SWPATH", log, "the file never ran")
        self.assert_nothing_placed()

    def test_mismatch_keeps_quarantine_and_never_runs(self):
        marker, shims = self.tmp / "marker", self.tmp / "shims"
        self.edit_swpath("set -uo pipefail", 'set -uo pipefail\necho SWPATH >> "$SW_MARKER"')
        extra = {"SW_MARKER": marker.as_posix()}
        target = self.target
        if not WINDOWS:
            shims.mkdir()
            (shims / "xattr").write_text('#!/bin/sh\necho "XATTR $1 $2" >> "$SW_MARKER"\nexit 0\n')
            (shims / "xattr").chmod(0o755)
            extra.update(SPECWRIGHT_TEST_HOST="Darwin/arm64", PATH=str(shims) + os.pathsep + os.environ["PATH"])
            target = "macos-arm64"
        self.release(target=target, sums_text=self.sums(target=target, hash_override="0" * 64))
        self.stopped("checksum_mismatch", asset_of(target), "0" * 64, sha(self.binary), **extra)
        self.assertFalse(marker.exists(), "the file was neither unquarantined nor run: %s" % (marker.read_text() if marker.exists() else ""))
        self.assert_nothing_placed()


class TestStops(Base):
    def test_unsealed_release_stops_assets_not_uploaded(self):
        self.release(sums=False)
        self.stopped("assets_not_uploaded", self.tag, "rerun")
        self.assert_nothing_placed()

    def test_missing_host_asset_stops(self):
        self.release(asset=False)
        self.stopped("asset_missing", asset_of(self.target), self.tag)
        self.assert_nothing_placed()

    def test_checksum_mismatch_stops_before_stage(self):
        self.release(sums_text=self.sums(hash_override="f" * 64))
        self.stopped("checksum_mismatch", asset_of(self.target), "f" * 64, sha(self.binary))
        self.assert_nothing_placed()

    def test_wrong_interface_stops_before_stage(self):
        self.edit_swpath("SW_INTERFACE=1", "SW_INTERFACE=7")
        self.release()
        self.stopped("sw_check_failed", "interface %d" % self.interface, "interface 7", asset_of(self.target))
        self.assert_nothing_placed()

    def test_wrong_version_stops(self):
        self.dl = self.make_download(self.tmp / "dl-other", version="9.9.9")
        self.release(tag="v9.9.9")
        self.stopped("sw_check_failed", "9.9.9", ref="v9.9.9")
        self.assert_nothing_placed()

    def test_tag_other_than_download_version_stops(self):
        # the download says self.version, the ref names another tag whose release holds a binary reporting self.version
        self.release(tag="v9.9.9")
        self.stopped("download_version_invalid", "v9.9.9", self.version, ref="v9.9.9")
        self.assert_nothing_placed()

    def test_malformed_sums_line_is_rejected(self):
        good = self.sums().splitlines()
        host = next(i for i, l in enumerate(good) if l.endswith(asset_of(self.target)))
        h = good[host].split("  ")[0]
        variants = {
            "uppercase hash": h.upper() + "  " + asset_of(self.target),
            "short hash": h[:63] + "  " + asset_of(self.target),
            "single space": h + " " + asset_of(self.target),
            "name outside the five": h + "  sw-freebsd-x64",
        }
        for label, line in variants.items():
            with self.subTest(label):
                lines = list(good)
                lines[host] = line
                self.release(sums_text="\n".join(lines) + "\n")
                self.stopped("sums_invalid", self.tag)
                self.assert_nothing_placed()

    def test_no_github_origin_stops(self):
        self.stopped("no_github_origin", base=False)
        self.assert_nothing_placed()


class TestBounds(Base):
    def test_stalled_download_hits_deadline(self):
        self.release()
        base = self.serve(stall={asset_of(self.target)})
        t0 = time.monotonic()
        self.stopped("deadline_exceeded", asset_of(self.target), base=base, SPECWRIGHT_NET_DEADLINE="3")
        self.assertLess(time.monotonic() - t0, 100)
        self.assertEqual(files(self.home), {}, "no partial file is left")

    def test_oversized_download_is_refused(self):
        self.release()
        base = self.serve(big={asset_of(self.target): 300000})
        self.stopped("response_too_large", asset_of(self.target), base=base, SPECWRIGHT_NET_MAX_BYTES="100000")
        self.assertEqual(files(self.home), {}, "no partial file is left")

    def test_download_over_http_completes(self):
        self.release()
        base = self.serve()
        doc = self.installed(base=base)
        self.assertEqual(doc["action"], "installed")
        self.assertEqual(self.final.read_bytes(), self.binary)

    def test_non_https_redirect_is_refused(self):
        self.release()
        base = self.serve(redirect={asset_of(self.target): "http://127.0.0.1:9/elsewhere"})
        self.stopped("download_failed", "redirect", base=base)
        self.assert_nothing_placed()


class TestPlan(Base):
    def setUp(self):
        super().setUp()
        self.dl_plan = fx.make_mini_download(self.tmp / "dl-plan", self.version, 1)
        self.co = fx.make_checkout(self.tmp, "0.0.1", download=fx.make_mini_download(self.tmp / "dl-old", "0.0.1", 1))

    def plan(self, ref):
        args = [*self.co.args(), "--download", fx.posix(self.dl_plan)]
        if ref:
            args += ["--ref", ref]
        code, doc, out, err = fx.run_update(self.dl_plan, [*args, "plan"], env=self.env(), timeout=240)
        self.assertEqual(code, 0, out + err)
        return doc

    def test_tag_plan_reports_the_host_asset(self):
        doc = self.plan(self.tag)
        self.assertEqual(doc["interface"], 2)
        self.assertEqual(doc["sw"], {"asset": asset_of(self.target), "target": self.target})

    def test_unsupported_host_plan_has_null_asset(self):
        self.env = lambda **extra: swharness.fixture_env(SPECWRIGHT_HOME=self.home.as_posix(), SPECWRIGHT_TEST_HOST="Windows/ARM64", **extra)
        doc = self.plan(self.tag)
        self.assertEqual(doc["sw"], {"asset": None, "reason": "unsupported_platform"})

    def test_main_install_reports_no_sw(self):
        self.assertNotIn("sw", self.plan("main"))
        code, doc, out, err = self.sw_install(ref="main", base=False)
        self.assertEqual(code, 0, out + err)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["action"], "skipped")
        self.assertEqual(doc["message"], "sw not installed: main has no release binaries")
        self.assert_nothing_placed()

    def test_plan_without_sw_field_means_no_sw(self):
        # an older tag's download runs its own update.sh, which has no sw field; the only plan of this script without the
        # field is one for a ref that is not a release tag. The step then installs nothing.
        doc = self.plan(None)
        self.assertNotIn("sw", doc)
        self.assertEqual(doc["interface"], 2)
        code, doc, out, err = self.sw_install(ref="", base=False)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(doc["action"], "skipped")
        self.assert_nothing_placed()

    def test_main_install_leaves_bin_untouched(self):
        other = self.home / ".specwright" / "bin" / "0.24.0"
        other.mkdir(parents=True)
        (other / EXE).write_bytes(b"an installed sw")
        os.utime(other / EXE, (1_600_000_000, 1_600_000_000))
        before = files(self.home)
        self.plan("main")
        self.sw_install(ref="main", base=False)
        self.assertEqual(files(self.home), before, "bytes, mode and timestamps stay")
        self.assertEqual(sorted(p.name for p in (self.home / ".specwright" / "bin").iterdir()), ["0.24.0"])


class TestPlacement(Base):
    def test_rerun_keeps_matching_binary(self):
        self.release()
        self.installed()
        before = files(self.bin)
        doc = self.installed()
        self.assertEqual(doc["action"], "kept")
        self.assertEqual(files(self.bin), before)

    def test_interrupt_before_rename_leaves_no_final_file(self):
        self.release()
        previous = self.home / ".specwright" / "bin" / "0.0.1"
        previous.mkdir(parents=True)
        (previous / EXE).write_bytes(b"previous")
        before = files(previous)
        code, doc, out, err = self.sw_install(SPECWRIGHT_TEST_RENAME="die")
        self.assertNotEqual(code, 0)
        self.assertFalse(self.final.exists())
        self.assertEqual(files(previous), before)
        doc = self.installed()  # the next run downloads and checks again
        self.assertEqual(doc["action"], "installed")

    def test_stale_final_file_is_replaced(self):
        self.release()
        self.bin.mkdir(parents=True)
        self.final.write_bytes(b"stale")
        doc = self.installed()
        self.assertEqual(doc["action"], "replaced")
        self.assertEqual(self.final.read_bytes(), self.binary)

    def test_unrunnable_matching_file_is_replaced(self):
        if WINDOWS:
            self.skipTest("platform: a Windows file has no executable bit to remove")
        self.release()
        self.bin.mkdir(parents=True)
        self.final.write_bytes(self.binary)
        self.final.chmod(0o644)
        doc = self.installed()
        self.assertEqual(doc["action"], "replaced")
        self.assertEqual(self.reported_version(self.final), self.version)

    def test_concurrent_installs_both_succeed(self):
        self.release()
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.sw_install())) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(300)
        self.assertEqual(len(results), 2)
        for code, doc, out, err in results:
            self.assertEqual(code, 0, out + err)
            self.assertIn(doc["action"], ("installed", "replaced", "kept"))
        self.assertEqual(sha(self.final.read_bytes()), sha(self.binary))
        self.assertEqual(sorted(p.name for p in self.bin.iterdir()), [EXE])

    def test_blocked_rename_with_matching_file_is_kept(self):
        self.release()
        self.bin.mkdir(parents=True)
        self.final.write_bytes(b"stale")
        doc = self.installed(SPECWRIGHT_TEST_RENAME="race")  # another run placed the file while this rename failed
        self.assertEqual(doc["action"], "kept")
        self.assertEqual(self.final.read_bytes(), self.binary)
        self.assertEqual(sorted(p.name for p in self.bin.iterdir()), [EXE], "this run's part file is deleted")

    def test_blocked_rename_with_other_file_stops_sw_in_use(self):
        self.release()
        self.bin.mkdir(parents=True)
        self.final.write_bytes(b"stale")
        self.stopped("sw_in_use", EXE, SPECWRIGHT_TEST_RENAME="fail")
        self.assertEqual(self.final.read_bytes(), b"stale")
        self.assertEqual(sorted(p.name for p in self.bin.iterdir()), [EXE])

    def test_only_old_part_files_are_cleaned(self):
        self.release()
        self.bin.mkdir(parents=True)
        old, fresh, other = self.bin / ".sw-aaaa.part", self.bin / ".sw-bbbb.part", self.bin / "notes.txt"
        for p in (old, fresh, other):
            p.write_bytes(b"x")
        two_hours = time.time() - 7200
        os.utime(old, (two_hours, two_hours))
        os.utime(other, (two_hours, two_hours))
        self.installed()
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists(), "a part modified within the hour belongs to another run")
        self.assertTrue(other.exists())


class TestRecovery(Base):
    """bin/ is outside the update journal: a rollback leaves every file under it (spec: Recovery leaves placed binaries in place)."""

    def setUp(self):
        super().setUp()
        self.dl_old = fx.make_mini_download(self.tmp / "dl-old", "0.0.1", 1)
        self.dl_new = fx.make_mini_download(self.tmp / "dl-new", self.version, 1)
        shutil.copytree(self.dl / SWPATH_REL.parent, self.dl_new / SWPATH_REL.parent)
        self.co = fx.make_checkout(self.tmp, "0.0.1", download=self.dl_old)
        self.old_bin = self.home / ".specwright" / "bin" / "0.0.1"

    def update_then_roll_back(self):
        def run(sub, *more):
            code, doc, out, err = fx.run_update(self.dl_new, [*self.co.args(), *more, sub], env=self.env(), timeout=300)
            self.assertEqual(code, 0, out + err)
            return doc
        run("stage")
        run("swap")
        doc = run("recover", "--rollback")
        self.assertEqual(doc["action"], "rolled-back", doc)
        self.assertEqual(self.co.version_file.read_text().strip(), "0.0.1")
        return doc

    def test_rollback_keeps_placed_binaries(self):
        self.old_bin.mkdir(parents=True)
        (self.old_bin / EXE).write_bytes(b"the previous sw")
        self.release()
        code, doc, out, err = self.sw_install(dl=self.dl_new)
        self.assertEqual(code, 0, out + err)
        before = files(self.home)
        self.update_then_roll_back()
        self.assertEqual(files(self.home), before)
        self.assertTrue(self.final.is_file())
        self.assertEqual((self.old_bin / EXE).read_bytes(), b"the previous sw")

    def test_rollback_to_version_without_sw(self):
        self.release()
        doc = self.update_then_roll_back()
        self.assertEqual(doc["sw_note"], "no sw serves 0.0.1, which no 0.0.1 skill needs", doc)
        self.assertEqual(doc["message"], "rolled back to 0.0.1", doc)
        self.assertFalse(self.old_bin.exists(), "the rollback creates nothing under bin/")
        r = subprocess.run([bashexe.bash(), str(self.dl / SWPATH_REL), "--code", str(self.co.code)], env=self.env(),
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.splitlines()[0], STOP, "no sw serves the rolled-back version")


if __name__ == "__main__":
    unittest.main()
