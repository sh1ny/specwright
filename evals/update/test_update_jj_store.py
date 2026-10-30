"""A planning store whose backend is jj passes update.sh's branch check (store-check, the swap's store gate): the
branch is read through the download's skills/specwright-pr/scripts/vcs.sh, because a colocated jj store has a detached
Git HEAD. A Git store keeps the Git rule.

Run: python -m unittest test_update_jj_store   (from evals/update)
"""
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
import jjenv  # noqa: E402

_spec = importlib.util.spec_from_file_location("update_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)


class JjStoreBase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, self.tmp)

    def pair(self, vcs_script=True):
        """The store pair at 0.5.0, a 0.6.0 download that changes the schema, and (vcs_script) the real specwright-pr skill
        copied into the download before plan, so the download ships vcs.sh."""
        dl0 = fx.make_mini_download(self.tmp / "dl-0.5.0", "0.5.0", 1)
        self.p = fx.make_store_pair(self.tmp, "0.5.0", download=dl0)
        self.a, self.store = self.p.a, self.p.store
        fx.write_store_record(self.store, "0.5.0", fx.owner_id(self.a))
        self.p.env.update({"JJ_USER": jjenv.FIXTURE_NAME, "JJ_EMAIL": jjenv.FIXTURE_EMAIL})
        self.dl = fx.make_mini_download(self.tmp / "dl-0.6.0", "0.6.0", 1, schema_edit=fx.schema_edit_comment)
        if vcs_script:
            shutil.copytree(ROOT / "skills" / "specwright-pr", self.dl / "skills" / "specwright-pr",
                            ignore=shutil.ignore_patterns("__pycache__"))
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

    def test_jj_store_vcs_script_missing(self):
        self.pair(vcs_script=False)
        self.store_jj()
        self.assertFalse((self.dl / "skills" / "specwright-pr" / "scripts" / "vcs.sh").exists())
        self.plan_stage()
        before = self.installed()
        code, doc = self.run_sub("swap")
        self.assertEqual((code, doc["error"]), (1, "vcs_script_missing"), doc)
        self.assertIn("skills/specwright-pr/scripts/vcs.sh", doc["message"].replace("\\", "/"))
        self.assertTrue(doc["unchanged"], doc)
        self.assertEqual(self.installed(), before)
        self.assertFalse((self.store / ".git" / "specwright-gate.lock").exists())
        self.assertEqual(fx.store_record_path(self.store).read_text(encoding="utf-8"),
                         fx.record_text("0.5.0", fx.owner_id(self.a)))


if __name__ == "__main__":
    unittest.main()
