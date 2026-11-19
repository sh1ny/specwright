"""Black-box tests of `sw update` (native-cli-update).

Run: SPECWRIGHT_SW=<path> python -m unittest evals/update/test_sw_update.py
"""
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evals" / "cli"))
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
sys.path.insert(0, str(ROOT / "evals"))
import swharness  # noqa: E402
import bashexe  # noqa: E402
import fakeexe  # noqa: E402
import jjenv  # noqa: E402
import sentinels  # noqa: E402

_spec = importlib.util.spec_from_file_location("update_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)
_spec = importlib.util.spec_from_file_location("update_jj_store_tests", HERE / "test_update_jj_store.py")
jjstore = importlib.util.module_from_spec(_spec)  # only a base class is used: its tests are not collected from here
_spec.loader.exec_module(jjstore)
_spec = importlib.util.spec_from_file_location("pack_merge", ROOT / "evals" / "packs" / "merge.py")
merge = importlib.util.module_from_spec(_spec)  # the Step 5 config merge, as the prompt's agent does it
_spec.loader.exec_module(merge)
PACK_BASE, PACK_DOMAIN = "valid-ui-base", "valid-domain"

INTERPRETERS = ("bash", "sh", "python", "python3")  # bare-bash: not started


def snapshot(path):
    """{relative posix path: bytes (None for a directory)} of everything under path."""
    out = {}
    for p in sorted(Path(path).rglob("*")):
        out[p.relative_to(path).as_posix()] = None if p.is_dir() else p.read_bytes()
    return out


class TestInterface(unittest.TestCase):
    def test_interface_reports_3_and_writes_nothing(self):
        """D11: `sw update interface` reads and writes nothing else: no journal recovery, no lock, no settings."""
        with tempfile.TemporaryDirectory(prefix="sw-update-iface-") as tmp:
            tmp = Path(tmp)
            code = tmp / "code"
            home = tmp / "home"
            state = code / "openspec" / ".specwright"
            state.mkdir(parents=True)
            home.mkdir()
            (state / "update.json").write_text('{"format": 9}\n', encoding="utf-8", newline="\n")
            (state / "update.lock").mkdir()
            (code / "openspec" / "specwright.yaml").write_text("vcs: yes\n", encoding="utf-8", newline="\n")
            before = snapshot(tmp)
            env = swharness.fixture_env(SPECWRIGHT_HOME=str(home))
            proc = swharness.run_sw("update", "interface", cwd=code, env=env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(proc.stdout, '{"ok":true,"interface":3}\n')
            self.assertEqual(proc.stderr, "")
            self.assertEqual(snapshot(tmp), before)


class TestSettings(unittest.TestCase):
    def test_plain_yes_setting_refused_settings_invalid(self):
        """`sw update plan` reads `openspec/specwright.yaml` only through the shared reader: a plain `yes` stops it with
        `settings_invalid` naming the file, the line and the fix, before any write."""
        with tempfile.TemporaryDirectory(prefix="sw-update-yes-") as tmp:
            tmp = Path(tmp)
            code = tmp / "code"
            download = tmp / "dl"
            home = tmp / "home"
            (code / "openspec").mkdir(parents=True)
            download.mkdir()
            home.mkdir()
            (download / "VERSION").write_text("0.37.0\n", encoding="utf-8", newline="\n")
            (code / "openspec" / "specwright.yaml").write_text(
                "review:\n  preship: yes\n", encoding="utf-8", newline="\n")
            before = snapshot(tmp)
            env = swharness.fixture_env(SPECWRIGHT_HOME=str(home))
            proc = swharness.run_sw("update", "plan", "--code", code, "--download", download, cwd=code, env=env)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            doc = json.loads(proc.stdout)
            self.assertEqual(doc["error"], "settings_invalid", doc)
            self.assertFalse(doc["ok"], doc)
            self.assertIn("openspec/specwright.yaml", doc["message"])
            self.assertIn("line 2", doc["message"])
            self.assertIn("write true or false", doc["message"])
            self.assertIn("rerun the update", doc["message"])
            self.assertEqual(snapshot(tmp), before)


class Recorders:
    """Failing recording `bash`, `sh`, `python` and `python3` for the front of PATH: each appends its name to a log and exits 97
    (on Windows each has a `.cmd` wrapper, because sw finds a command through PATHEXT there). `probe` runs each one to show
    that it records, so that an absent log later means that nothing started them."""

    def __init__(self, root):
        self.bin = Path(root) / "interpreters"
        self.bin.mkdir(parents=True)
        self.log = Path(root) / "interpreters.log"
        for name in INTERPRETERS:
            fakeexe.write_fake(self.bin / name, '#!/bin/sh\nprintf "%s\\n" ' + name + ' >> "$SW_INTERPRETER_LOG"\nexit 97\n')

    def env(self, **extra):
        env = swharness.fixture_env(SW_INTERPRETER_LOG=self.log.as_posix(), OPENSPEC_TELEMETRY="0", **extra)
        env["PATH"] = str(self.bin) + os.pathsep + env.get("PATH", "")
        return env

    def probe(self, test):
        bash = bashexe.bash()
        test.assertTrue(bash, "the recorders need bash")
        done = []
        for name in INTERPRETERS:
            r = subprocess.run([bash, str(self.bin / name)], env=self.env(), capture_output=True, timeout=30)
            test.assertEqual(r.returncode, 97, name)
            done.append(name)
            test.assertEqual(self.recorded(), done, "the %s recorder did not record its run" % name)
        self.log.unlink()

    def recorded(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []


class SwUpdateCase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.sw = swharness.require_sw()
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-update-eval-")).resolve()
        self.addCleanup(fx.rmtree, self.tmp)
        self.home = self.tmp / "home"
        self.home.mkdir()

    def sw_update(self, env, co, dl, sub, *extra, kill_at=None, count=None):
        """`sw update <checkout options> --download <dl> <sub>`; returns (exit code, document or None, stdout, stderr)."""
        env = dict(env)
        if count:
            env["SPECWRIGHT_UPDATE_COUNT"] = fx.posix(count)
        if kill_at is not None:
            env["SPECWRIGHT_UPDATE_KILL_AT"] = str(kill_at)
        proc = subprocess.run([self.sw, "update", *map(str, co.args()), "--download", fx.posix(dl), sub, *extra], env=env,
                              cwd=co.code, capture_output=True, text=True, encoding="utf-8", timeout=300)
        doc = None
        if proc.stdout.strip():
            try:
                doc = json.loads(proc.stdout)
            except ValueError:
                pass
        return proc.returncode, doc, proc.stdout, proc.stderr

    def step(self, env, co, dl, sub, *extra, **kw):
        code, doc, out, err = self.sw_update(env, co, dl, sub, *extra, **kw)
        self.assertEqual(code, 0, f"{sub}: {out}{err}")
        self.assertTrue(doc and doc["ok"], f"{sub}: {out}")
        return doc

    def flow(self, env, co, dl):
        """The update: plan, stage, swap, the prompt's stamp, finish. Returns plan's document."""
        plan = self.step(env, co, dl, "plan")
        self.step(env, co, dl, "stage")
        self.step(env, co, dl, "swap")
        co.version_file.write_text((dl / "VERSION").read_text(encoding="utf-8"), encoding="utf-8", newline="")
        self.step(env, co, dl, "finish")
        return plan

    def interrupt_swap(self, env, co, dl):
        """Stage, then swap until exit 137 after the first target was renamed: a counting run (stage and swap) finds the first
        rename of the swap, the checkout goes back to its start and the run is repeated with the kill."""
        pristine = self.tmp / "pristine"
        shutil.copytree(co.code, pristine)
        count = self.tmp / "count"
        self.step(env, co, dl, "stage", count=count)
        self.step(env, co, dl, "swap", count=count)
        log = [line.split(" ", 2) for line in count.read_text(encoding="utf-8").splitlines()]
        first_rename = next(int(n) for n, op, args in log if op == "mv" and ".specwright-update-" in args)
        fx.rmtree(co.code)
        shutil.copytree(pristine, co.code)
        count.unlink()
        self.step(env, co, dl, "stage", count=count)
        code, _doc, out, err = self.sw_update(env, co, dl, "swap", count=count, kill_at=first_rename + 2)
        self.assertEqual(code, 137, out + err)
        self.assertTrue(co.journal.exists(), "the journal outlives the interrupted swap")

    def assert_installed_from(self, co, dl):
        self.assertEqual(co.version_file.read_text(encoding="utf-8"), (dl / "VERSION").read_text(encoding="utf-8"))
        for skill in sorted(p.name for p in (dl / "skills").glob("specwright-*")):
            self.assertEqual(fx.tree(co.skills[0] / skill), fx.tree(dl / "skills" / skill), skill)
        self.assertEqual(fx.tree(co.schema), fx.tree(dl / "schemas" / "specwright"))
        self.assertFalse(list(co.code.rglob(".specwright-update-*")), "staging left behind")
        self.assertFalse(co.journal.exists())
        self.assertFalse(co.lock.exists())


class TestNoInterpreters(SwUpdateCase):
    """sw update runs by itself: no bash, sh or Python is started, whatever is first on PATH (native-cli-update D1)."""

    def setUp(self):
        super().setUp()
        self.rec = Recorders(self.tmp)
        self.rec.probe(self)
        self.env = self.rec.env(SPECWRIGHT_HOME=self.home)

    def minis(self):
        old = fx.make_mini_download(self.tmp / "dl-0.5.0", "0.5.0", 2, provision=False)
        new = fx.make_mini_download(self.tmp / "dl-0.6.0", "0.6.0", 2, provision=False, schema_edit=fx.schema_edit_comment)
        return old, new

    def test_install_and_update_with_failing_interpreters(self):
        dl_old, dl_new = self.minis()
        # a fresh install of 0.5.0 ...
        fresh = fx.make_checkout(self.tmp, None, name="fresh")
        plan = self.flow(self.env, fresh, dl_old)
        self.assertEqual((plan["kind"], plan["from"], plan["to"]), ("fresh", None, "0.5.0"))
        self.assert_installed_from(fresh, dl_old)
        # ... and an update of another checkout from 0.5.0 to 0.6.0
        old = fx.make_checkout(self.tmp, "0.5.0", download=dl_old, name="old")
        plan = self.flow(self.env, old, dl_new)
        self.assertEqual((plan["kind"], plan["from"], plan["to"]), ("workflow", "0.5.0", "0.6.0"))
        self.assert_installed_from(old, dl_new)
        self.assertEqual(self.rec.recorded(), [], "an interpreter was started")

    def test_interrupted_swap_recovered_with_failing_interpreters(self):
        dl_old, dl_new = self.minis()
        co = fx.make_checkout(self.tmp, "0.5.0", download=dl_old)
        self.interrupt_swap(self.env, co, dl_new)
        plan = self.step(self.env, co, dl_new, "plan")
        self.assertEqual(plan["recovered"]["action"], "resumed", plan)
        self.assertEqual(plan["recovered"]["message"], "resumed update to 0.6.0")
        co.version_file.write_text("0.6.0\n", encoding="utf-8", newline="")
        self.step(self.env, co, dl_new, "finish")
        self.assert_installed_from(co, dl_new)
        self.assertEqual(self.rec.recorded(), [], "an interpreter was started")

    def test_pack_commands_with_failing_interpreters(self):
        """The commands the other two tests do not run: pack-check, note-config, pack-verify and pack-docs, with two
        enabled packs, one of them with a document (the README's Steps 4 to 7 for a repo-local project)."""
        packs = ROOT / "evals" / "packs" / "fixtures" / "packs"
        dl_old = fx.make_mini_download(self.tmp / "dl-0.5.0", "0.5.0", 1, provision=False)
        dl = fx.make_mini_download(self.tmp / "dl-0.6.0", "0.6.0", 1, provision=False)
        (dl / "packs").mkdir()
        for name in PACK_BASE, PACK_DOMAIN:
            shutil.copytree(packs / name, dl / "packs" / name)
        co = fx.make_checkout(self.tmp, "0.5.0", download=dl_old)
        enable = ["--pack", PACK_DOMAIN, "--pack", PACK_BASE]
        check = self.step(self.env, co, dl, "pack-check", *enable)
        self.assertEqual(check["subcommand"], "pack-check", check)
        plan = self.step(self.env, co, dl, "plan", *enable)
        self.assertEqual([p["name"] for p in plan["packs"]], [PACK_BASE, PACK_DOMAIN])
        self.step(self.env, co, dl, "stage", *enable)
        self.step(self.env, co, dl, "swap", *enable)
        manifests = [(p["name"], json.loads((dl / "packs" / p["name"] / "pack.json").read_text(encoding="utf-8")))
                     for p in plan["packs"]]
        config = co.root / "openspec" / "config.yaml"
        template = (dl / "templates" / "openspec" / "config.yaml").read_text(encoding="utf-8")
        text, unmanaged = merge.merge_config(config.read_text(encoding="utf-8"), template, manifests,
                                             plan["packs_previous"])
        self.assertEqual(unmanaged, [])
        config.write_text(text, encoding="utf-8", newline="\n")
        self.step(self.env, co, dl, "note-config")
        verify = self.step(self.env, co, dl, "pack-verify")
        self.assertEqual(verify["problems"], [], verify)
        co.version_file.write_text("0.6.0\n", encoding="utf-8", newline="")
        self.step(self.env, co, dl, "finish")
        docs = self.step(self.env, co, dl, "pack-docs")
        self.assertEqual([(d["pack"], d["id"], d["status"]) for d in docs["documents"]],
                         [(PACK_DOMAIN, "gdd", "created")])
        self.assertTrue((co.code / "docs" / "domain" / "gdd.md").is_file())
        self.assertEqual(self.rec.recorded(), [], "an interpreter was started")


def script_layout(journal):
    """The journal as update.sh 0.36.0 wrote it: each top-level key on its own line (two-space indent), a list of objects with
    one object per line, a nested object on one line, every value as Python's json.dumps writes it."""
    def one(value):
        return json.dumps(value, ensure_ascii=False)
    lines = []
    for key, value in journal.items():
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            inner = ",\n".join("    " + one(item) for item in value)
            lines.append("  %s: [\n%s\n  ]" % (one(key), inner))
        else:
            lines.append("  %s: %s" % (one(key), one(value)))
    return "{\n" + ",\n".join(lines) + "\n}\n"


class TestJournals(SwUpdateCase):
    def setUp(self):
        super().setUp()
        self.env = swharness.fixture_env(SPECWRIGHT_HOME=self.home, OPENSPEC_TELEMETRY="0")
        self.dl_old = fx.make_mini_download(self.tmp / "dl-0.5.0", "0.5.0", 2, provision=False)
        self.dl_new = fx.make_mini_download(self.tmp / "dl-0.6.0", "0.6.0", 2, provision=False,
                                            schema_edit=fx.schema_edit_comment)
        self.co = fx.make_checkout(self.tmp, "0.5.0", download=self.dl_old)

    def test_format_2_journal_from_update_sh_resumed(self):
        """A swap that 0.36.0's update.sh left half done (format 2, its layout) is resumed by `sw update plan`."""
        co = self.co
        self.interrupt_swap(self.env, co, self.dl_new)
        journal = json.loads(co.journal.read_text(encoding="utf-8"))
        self.assertEqual((journal["format"], journal["phase"]), (2, "swapping"))
        self.assertNotEqual({t["state"] for t in journal["targets"]}, {"staged"}, "the swap had started")
        text = script_layout(journal)
        self.assertEqual(json.loads(text), journal)
        co.journal.write_text(text, encoding="utf-8", newline="")
        plan = self.step(self.env, co, self.dl_new, "plan")
        self.assertEqual(plan["recovered"]["action"], "resumed", plan)
        self.assertEqual(plan["recovered"]["message"], "resumed update to 0.6.0")
        co.version_file.write_text("0.6.0\n", encoding="utf-8", newline="")
        self.step(self.env, co, self.dl_new, "finish")
        self.assert_installed_from(co, self.dl_new)

    def test_unknown_journal_format_refused(self):
        """`"format": 9` is unreadable: plan refuses and recover stops, naming the format, and the journal stays."""
        co = self.co
        co.journal.parent.mkdir(parents=True, exist_ok=True)
        co.journal.write_text('{"format": 9}\n', encoding="utf-8", newline="")
        before = fx.snapshot(co.code)
        code, doc, out, err = self.sw_update(self.env, co, self.dl_new, "plan")
        self.assertEqual((code, doc["error"]), (1, "refused"), out + err)
        self.assertIn("journal_unreadable", [r["code"] for r in doc["refusals"]])
        code, doc, out, err = self.sw_update(self.env, co, self.dl_new, "recover")
        self.assertEqual((code, doc["error"]), (1, "journal_unreadable"), out + err)
        self.assertIn("format 9", doc["message"])
        self.assertEqual(fx.snapshot(co.code), before)


def host_target():
    system = {"linux": "linux", "darwin": "macos", "windows": "windows"}.get(platform.system().lower())
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower())
    return "%s-%s" % (system, arch)


# The asset of the fixture release: a stand-in for the downloaded sw that logs its arguments and answers only `version --json`.
ASSET_SOURCE = """import json, os, sys
with open(os.environ["SW_ASSET_LOG"], "a", encoding="utf-8") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
if sys.argv[1:] == ["version", "--json"]:
    print(json.dumps({"version": os.environ["SW_ASSET_VERSION"], "interface": int(os.environ["SW_ASSET_INTERFACE"])}))
else:
    sys.exit(93)
"""


class TestNoScripts(SwUpdateCase):
    """sw-install and an owner's swap on a jj store start no script and no Python: failing recording python and python3 are
    first on PATH."""

    def plant(self):
        self.sent = sentinels.install(self.tmp / "pybin", self.tmp / "sentinels.log")
        self.sent.probe(self)

    def env(self, base=None, **extra):
        env = dict(base) if base is not None else swharness.fixture_env()
        env.update({"OPENSPEC_TELEMETRY": "0", **self.sent.env, **{k: str(v) for k, v in extra.items()}})
        env["PATH"] = str(self.sent.bin) + os.pathsep + env.get("PATH", "")
        return env

    def test_sw_install_and_jj_swap_start_no_script(self):
        target = host_target()
        report = json.loads(subprocess.run([self.sw, "version", "--json"], capture_output=True, text=True, timeout=60).stdout)
        tag = "v0.40.0"
        dl = fx.make_mini_download(self.tmp / "dl-install", "0.40.0", 1, provision=False)
        self.plant()
        release = self.tmp / "rel" / "releases" / "download" / tag
        release.mkdir(parents=True)
        asset = "sw-" + target + (".exe" if target.startswith("windows") else "")
        written = fakeexe.write_python_fake(release / asset.removesuffix(".exe"), ASSET_SOURCE)
        self.assertEqual(written.name, asset)
        notice = b"Fixture third-party notice\n"
        (release / "THIRD_PARTY_NOTICES.txt").write_bytes(notice)
        sums = [(hashlib.sha256(written.read_bytes() if name == asset else name.encode()).hexdigest(), name)
                for name in ("sw-linux-x64", "sw-linux-arm64", "sw-windows-x64.exe", "sw-macos-arm64", "sw-macos-x64")]
        sums.append((hashlib.sha256(notice).hexdigest(), "THIRD_PARTY_NOTICES.txt"))
        (release / "SHA256SUMS").write_text("".join("%s  %s\n" % pair for pair in sorted(sums, key=lambda pair: pair[1])),
                                            encoding="utf-8", newline="")
        asset_log = self.tmp / "asset.log"
        env = self.env(SPECWRIGHT_HOME=self.home, SW_ASSET_LOG=asset_log.as_posix(), SW_ASSET_VERSION="0.40.0",
                       SW_ASSET_INTERFACE=str(report["interface"]))
        proc = subprocess.run([self.sw, "update", "--code", fx.posix(self.tmp), "--download", fx.posix(dl), "--ref", tag,
                               "--release-url", (self.tmp / "rel").as_uri(), "sw-install"], env=env, capture_output=True,
                              text=True, encoding="utf-8", timeout=240)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual((doc["ok"], doc["action"]), (True, "installed"), doc)
        runs = asset_log.read_text(encoding="utf-8").splitlines()
        self.assertTrue(runs and set(runs) == {"version --json"}, runs)
        self.assertEqual(self.sent.recorded(), [], "an interpreter was started")

        # an owner's swap on a jj store, with the same sentinels first on PATH
        jjenv.require_jj()
        base = jjstore.JjStoreBase("run")
        base.tmp = self.tmp / "jj"
        base.tmp.mkdir()
        base.pair()
        base.store_jj()
        self.plant()
        env = self.env(base.p.env, SPECWRIGHT_HOME=self.home)
        for sub in ("plan", "stage", "swap"):
            code, swap, out, err = self.sw_update(env, base.a, base.dl, sub)
            self.assertEqual(code, 0, f"{sub}: {out}{err}")
        self.assertTrue(swap["store_written"], swap)
        self.assertEqual(self.sent.recorded(), [], "an interpreter was started")


if __name__ == "__main__":
    unittest.main()
