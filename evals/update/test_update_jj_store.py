"""A planning store whose backend is jj passes update.sh's branch check (store-check, the swap's store gate): sw reads the branch in
process through its VCS interfaces (no vcs.sh, no download sw call), because a colocated jj store has a detached Git HEAD. A Git
store keeps the Git rule. The update.sh shim hands over to the sw of the download's own VERSION.

Run: python -m unittest test_update_jj_store   (from evals/update)
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
sys.path.insert(0, str(ROOT / "evals" / "cli"))
import jjenv  # noqa: E402
import swharness  # noqa: E402
import vcs_test_support as support  # noqa: E402

_spec = importlib.util.spec_from_file_location("update_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)


class JjStoreBase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, self.tmp)

    def pair(self, home=True):
        """The store pair at 0.5.0 and a download at the tree's version that changes the schema. (home) The test home holding
        the tree's sw at the download's version, which the update.sh shim hands over to (design D8 of native-cli-update)."""
        dl0 = fx.make_mini_download(self.tmp / "dl-0.5.0", "0.5.0", 1, provision=False)
        self.p = fx.make_store_pair(self.tmp, "0.5.0", download=dl0)
        self.a, self.store = self.p.a, self.p.store
        fx.write_store_record(self.store, "0.5.0", fx.owner_id(self.a))
        self.p.env.update({"JJ_USER": jjenv.FIXTURE_NAME, "JJ_EMAIL": jjenv.FIXTURE_EMAIL})
        self.dl = fx.make_mini_download(self.tmp / "dl", support.tree_version(), 1, schema_edit=fx.schema_edit_comment,
                                        provision=False)
        self.p.env["SPECWRIGHT_HOME"] = str(support.sw_home() if home else self.tmp / "empty-home")
        return self.p

    def store_jj(self):
        """Make the store a colocated jj repo (Git HEAD detached at main) and declare it in the code repo's settings."""
        jj = jjenv.require_jj()
        r = subprocess.run([jj, "git", "init", "--colocate"], cwd=self.store, env=self.p.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for rev in ("root()", "main"):  # jj leaves HEAD on the branch until @- moves: go away and back, detaching it at main
            r = subprocess.run([jj, "new", rev], cwd=self.store, env=self.p.env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        fx.write(self.a.code, "openspec/specwright.yaml", "planning_store:\n  vcs: jj\n")

    def run_sub(self, sub):
        code, doc, out, err = fx.run_update(self.dl, [*self.a.args(), sub], env=self.p.env)
        self.assertIsNotNone(doc, f"{sub}: no JSON (exit {code}).\nstdout: {out}\nstderr: {err}")
        return code, doc

    def plan_stage(self):
        for sub in ("plan", "stage"):
            code, doc = self.run_sub(sub)
            self.assertEqual(code, 0, doc)

    def installed(self):
        return {"skills": fx.tree(self.a.skills[0]), "agents": fx.tree(self.a.agents["claude"]),
                "version": self.a.version_file.read_text(), "schema": fx.tree(self.a.schema)}


class TestJjStore(JjStoreBase):
    def test_jj_store_on_main_not_refused(self):
        self.pair()
        self.store_jj()
        self.assertEqual(fx.git(self.store, "branch", "--show-current"), "")  # detached, as jj leaves it
        self.plan_stage()
        code, doc = self.run_sub("swap")
        self.assertEqual(code, 0, doc)
        self.assertTrue(doc["store_written"], doc)
        self.assertEqual(fx.tree(self.a.schema), fx.tree(self.dl / "schemas" / "specwright"))
        self.assertFalse((self.store / ".git" / "specwright-gate.lock").exists())

    def test_jj_store_flow_map_setting_not_refused(self):
        """`planning_store: {vcs: jj}` selects jj as pr-pair.sh vcs reads it, so the jj store is not refused as detached."""
        self.pair()
        self.store_jj()
        fx.write(self.a.code, "openspec/specwright.yaml", "planning_store: {vcs: jj}\n")
        self.plan_stage()
        code, doc = self.run_sub("swap")
        self.assertEqual(code, 0, doc)
        self.assertTrue(doc["store_written"], doc)

    def test_branch_read_by_download_version_sw(self):
        """The project's version has no usable sw (a decoy that fails the resolver); the download's has the tree's: the
        branch is read by the download's, so the store is not refused."""
        self.pair()
        self.store_jj()
        decoy = Path(self.p.env["SPECWRIGHT_HOME"]) / ".specwright" / "bin" / "0.5.0"
        decoy.mkdir(parents=True)
        for name in ("sw", "sw.exe"):
            (decoy / name).write_text("not a binary\n", encoding="utf-8")
        self.plan_stage()
        code, doc = self.run_sub("swap")
        self.assertEqual(code, 0, doc)
        self.assertTrue(doc["store_written"], doc)

    def test_no_sw_for_download_version_refuses(self):
        """The shim hands over to the sw of the download's version only: with none placed it stops sw_missing, before any
        subcommand runs, so nothing is staged, taken or written."""
        self.pair(home=False)
        self.store_jj()
        before = self.installed()
        code, doc, out, err = fx.run_update(self.dl, [*self.a.args(), "plan"], env=self.p.env)
        self.assertEqual((code, doc["error"]), (1, "sw_missing"), out + err)
        self.assertIn(support.tree_version(), doc["message"])
        self.assertIn("rerun the install prompt", doc["message"])
        self.assertEqual(self.installed(), before)
        self.assertFalse(self.a.journal.exists())
        self.assertFalse((self.store / ".git" / "specwright-gate.lock").exists())

    def test_git_store_detached_still_refused(self):
        self.pair()
        fx.write(self.a.code, "openspec/specwright.yaml", "planning_store:\n  vcs: git\n")
        fx.git(self.store, "checkout", "-q", "--detach")
        self.plan_stage()
        before = self.installed()
        code, doc = self.run_sub("swap")
        self.assertEqual((code, doc["error"]), (1, "store_busy"), doc)
        self.assertIn("detached HEAD", doc["message"])
        self.assertEqual(self.installed(), before)
        self.assertFalse((self.store / ".git" / "specwright-gate.lock").exists())

    def test_jj_store_swap_needs_no_vcs_script(self):
        """The branch of a jj store is read in process: a download that ships no vcs.sh swaps as before."""
        self.pair()
        self.store_jj()
        (self.dl / "skills" / "specwright-pr" / "scripts" / "vcs.sh").unlink()
        self.assertFalse((self.dl / "skills" / "specwright-pr" / "scripts" / "vcs.sh").exists())
        self.plan_stage()
        code, doc = self.run_sub("swap")
        self.assertEqual(code, 0, doc)
        self.assertTrue(doc["store_written"], doc)
        self.assertEqual(fx.tree(self.a.schema), fx.tree(self.dl / "schemas" / "specwright"))
        self.assertFalse((self.store / ".git" / "specwright-gate.lock").exists())


class TestJjStoreInProcess(JjStoreBase):
    def sw_update(self, sub):
        proc = swharness.run_sw("update", *self.a.args(), "--download", fx.posix(self.dl), sub,
                                cwd=self.a.code, env=self.p.env)
        try:
            doc = json.loads(proc.stdout)
        except ValueError:
            self.fail(f"{sub}: no JSON (exit {proc.returncode}).\nstdout: {proc.stdout}\nstderr: {proc.stderr}")
        return proc.returncode, doc

    def test_busy_jj_store_read_in_process(self):
        """The branch of a jj store is read inside sw (its own VCS interfaces): the owner's swap on a busy jj store stops
        store_busy naming the change bookmark, and neither vcs.sh nor as.sh of the download ran (recording sentinels)."""
        self.pair()
        self.store_jj()
        scripts = self.dl / "skills" / "specwright-pr" / "scripts"
        for name in ("vcs.sh", "as.sh"):
            (scripts / name).write_text(f'#!/bin/sh\necho ran > "$(dirname "$0")/ran-{name}"\n', encoding="utf-8", newline="\n")
        jj = jjenv.require_jj()
        r = subprocess.run([jj, "bookmark", "create", "feat/busy", "-r", "@-"], cwd=self.store, env=self.p.env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for sub in ("plan", "stage"):
            code, doc = self.sw_update(sub)
            self.assertEqual(code, 0, doc)
        before = self.installed()
        code, doc = self.sw_update("swap")
        self.assertEqual((code, doc.get("error")), (1, "store_busy"), doc)
        self.assertIn("feat/busy", doc["message"])
        self.assertEqual(self.installed(), before)
        self.assertEqual(sorted(p.name for p in scripts.glob("ran-*")), [], "a download script ran")
        self.assertFalse((self.store / ".git" / "specwright-gate.lock").exists())


if __name__ == "__main__":
    unittest.main()
