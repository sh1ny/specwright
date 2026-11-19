"""scripts/update.sh is a shim (ADR 0028, design D8 of native-cli-update): it reads <download>/VERSION, finds the sw of
that version at <home>/.specwright/bin/<version>/ with the sw-path.sh beside it in the download, and runs
`sw update <its arguments> --download <its tree>`. With no matching sw it prints `sw_missing` and exits 1.

Run: python -m unittest evals/update/test_shim.py   (needs dart on PATH: the fixtures build a sw per version)
"""
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("update_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)


class TestShim(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(fx.rmtree, self.tmp)
        self.home = self.tmp / "home"

    def env(self):
        return {**os.environ, "OPENSPEC_TELEMETRY": "0", "SPECWRIGHT_HOME": str(self.home)}

    def direct(self, sw, args):
        """`sw update <args>`, as the shim must hand it over."""
        r = subprocess.run([str(sw), "update", *map(str, args)], env=self.env(), capture_output=True, text=True,
                           encoding="utf-8", timeout=300)
        return r.returncode, r.stdout, r.stderr

    def test_shim_hands_over_to_download_sw(self):
        old = fx.make_download(self.tmp / "dl-0.5.0", "0.5.0", home=self.home)
        new = fx.make_download(self.tmp / "dl-0.6.0", "0.6.0", home=self.home)
        co = fx.make_checkout(self.tmp, "0.5.0", download=old)
        sw = self.home / ".specwright" / "bin" / "0.6.0" / ("sw.exe" if os.name == "nt" else "sw")
        self.assertTrue(sw.is_file())
        args = [*co.args(), "plan"]
        expected = self.direct(sw, [*args, "--download", fx.posix(new)])
        code, doc, out, err = fx.run_update(new, args, env=self.env(), shim=True)
        self.assertEqual((code, out, err), expected)
        self.assertEqual(doc["ok"], True, out)
        self.assertEqual(doc["interface"], 3, out)  # sw's plan, not the script's
        # an explicit --download is handed over as given and not added twice
        code, _doc, out, err = fx.run_update(new, [*args, "--download", fx.posix(new)], env=self.env(), shim=True)
        self.assertEqual((code, out, err), expected)

    def test_shim_without_matching_sw_reports_sw_missing(self):
        # no sw at all, then a sw of another version only: both stop before any write
        for label, other in (("no sw", None), ("wrong-version sw", "0.5.0")):
            with self.subTest(label):
                tmp = self.tmp / label.replace(" ", "-")
                tmp.mkdir()
                home = tmp / "home"
                new = fx.make_download(tmp / "dl-0.6.0", "0.6.0", provision=False)
                co = fx.make_checkout(tmp, "0.5.0", download=fx.make_download(tmp / "dl-0.5.0", "0.5.0", provision=False))
                if other:
                    fx.provision_sw(home, other)
                before = fx.snapshot(co.code)
                env = {**self.env(), "SPECWRIGHT_HOME": str(home)}
                code, doc, out, err = fx.run_update(new, [*co.args(), "plan"], env=env, shim=True)
                self.assertEqual(code, 1, out + err)
                self.assertEqual(doc["ok"], False, out)
                self.assertEqual(doc["error"], "sw_missing", out)
                self.assertIn("sw missing or mismatched", doc["message"])
                self.assertEqual(fx.snapshot(co.code), before)
                self.assertEqual(json.loads(out), doc)


if __name__ == "__main__":
    unittest.main()
