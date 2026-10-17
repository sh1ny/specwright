"""The interruption criterion of the update (design: "Testing the interruption criterion"), for a repo-local project
(TestInterrupt) and for the owner of a store (TestStoreInterrupt: the store's gate lock is taken before the first rename
and must not outlive the update).

update.sh calls only the external mv, cp and rm, and the shims in evals/update/shims count every call and can SIGKILL the
script at call N (UPDATE_KILL_AT). A counting run (stage, then swap, one shared counter) gives the list of operations; the
tests then repeat the update once per operation, killing at it, with no sampling.

The layout is a minimal one (two skills, one skills directory, one agent file, the schema) so that the whole matrix runs
in a few minutes. The checkout is restored from a copy of its pristine state between runs.

Run: python -m unittest discover evals/update -p "test_interrupt.py"
"""
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("update_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)


class TestInterrupt(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.dl_old = fx.make_mini_download(cls.tmp / "dl-0.5.0", "0.5.0", 2)
        cls.dl_new = fx.make_mini_download(cls.tmp / "dl-0.6.0", "0.6.0", 2)
        cls.co = fx.make_checkout(cls.tmp, "0.5.0", skills_dirs=(".claude/skills",), download=cls.dl_old)
        cls.shims = fx.install_shims(cls.tmp / "shims")
        cls.pristine = cls.tmp / "pristine"
        shutil.copytree(cls.co.code, cls.pristine)
        cls.old = cls.installed()
        cls.counter = cls.tmp / "count"
        # the counting run: stage, swap, the prompt's stamp, finish
        cls.reset()
        cls.upd("stage", count=True)
        cls.upd("swap", count=True)
        log = Path(f"{cls.counter}.log").read_text(encoding="utf-8").splitlines()
        cls.log = [line.split(" ", 2) for line in log]
        cls.co.version_file.write_text("0.6.0\n")
        cls.upd("finish")
        cls.new = cls.installed()
        cls.total = len(cls.log)
        # the first swap rename is the first mv that touches a staging directory (journal writes move update.json.tmp)
        cls.first_rename = next(int(n) for n, tool, args in cls.log if tool == "mv" and ".specwright-update-" in args)

    @classmethod
    def tearDownClass(cls):
        fx.rmtree(cls.tmp)

    @classmethod
    def installed(cls):
        co = cls.co
        return {"skills": fx.tree(co.skills[0]), "agents": fx.tree(co.agents["claude"]), "schema": fx.tree(co.schema)}

    @classmethod
    def reset(cls):
        fx.rmtree(cls.co.code)
        shutil.copytree(cls.pristine, cls.co.code)
        for f in (cls.counter, Path(f"{cls.counter}.log")):
            f.unlink(missing_ok=True)

    @classmethod
    def upd(cls, sub, count=False, kill_at=None):
        return fx.run_update(cls.dl_new, [*cls.co.args(), sub], shim_dir=cls.shims if count else None,
                             count_file=cls.counter if count else None, kill_at=kill_at)

    def leftovers(self):
        co = self.co
        return sorted(p.relative_to(co.code).as_posix() for p in co.code.rglob(".specwright-update-*")) + \
            sorted(p.name for p in co.journal.parent.glob("update.*"))

    def test_counting_run_is_sane(self):
        self.assertNotEqual(self.old, self.new)
        self.assertGreater(self.first_rename, 3)
        self.assertGreater(self.total, self.first_rename + 8)

    def test_kill_before_swap_leaves_previous_runnable(self):
        for n in range(1, self.first_rename):
            with self.subTest(kill_at=n, op=" ".join(self.log[n - 1][1:])):
                self.reset()
                code, _, _, err = self.upd("stage", count=True, kill_at=n)
                if code == 0:  # the kill is past stage: it falls in the swap, before its first rename
                    code, _, _, err = self.upd("swap", count=True, kill_at=n)
                self.assertNotEqual(code, 0, "the run was meant to be killed")
                self.assertEqual(self.installed(), self.old)
                self.assertEqual(self.co.version_file.read_text(), "0.5.0\n")
                r = fx.openspec(["schema", "validate", "specwright"], cwd=self.co.root)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_kill_during_swap_resumes(self):
        for n in range(self.first_rename, self.total + 1):
            with self.subTest(kill_at=n, op=" ".join(self.log[n - 1][1:])):
                self.reset()
                code, _, _, err = self.upd("stage", count=True)
                self.assertEqual(code, 0, err)
                code, _, _, err = self.upd("swap", count=True, kill_at=n)
                self.assertNotEqual(code, 0, "the swap was meant to be killed")
                code, doc, out, err = self.upd("plan")  # the rerun recovers first
                self.assertEqual(code, 0, out + err)
                action = doc["recovered"]["action"]
                self.assertIn(action, ("resumed", "rolled-back"))
                if self.co.journal.exists():  # resumed: the prompt stamps VERSION, then finishes
                    self.co.version_file.write_text("0.6.0\n")
                    code, doc, out, err = self.upd("finish")
                    self.assertEqual(code, 0, out + err)
                if action == "resumed":
                    self.assertEqual(self.installed(), self.new)
                    self.assertEqual(self.co.version_file.read_text(), "0.6.0\n")
                else:
                    self.assertEqual(self.installed(), self.old)
                    self.assertEqual(self.co.version_file.read_text(), "0.5.0\n")
                self.assertEqual(self.leftovers(), [])

    def swap_killed_after_first_target(self):
        """Stage, then kill the swap at the first call after which the first target is swapped in. Returns the target."""
        import json
        for n in range(self.first_rename, self.total + 1):
            self.reset()
            code, _, _, err = self.upd("stage", count=True)
            self.assertEqual(code, 0, err)
            self.upd("swap", count=True, kill_at=n)
            if not self.co.journal.exists():
                continue
            t = json.loads(self.co.journal.read_text(encoding="utf-8"))["targets"][0]
            if t["state"] == "swapped" and not (Path(t["staging"]) / "new" / t["name"]).exists():
                return t
        self.fail("no kill point leaves the first target swapped")

    def test_refusal_after_resumed_swap_reports_not_unchanged(self):
        self.swap_killed_after_first_target()
        schema = self.dl_new / "schemas" / "specwright" / "schema.yaml"
        saved = schema.read_bytes()
        schema.unlink()  # the download is now incomplete: plan recovers first, then refuses
        try:
            code, doc, out, err = self.upd("plan")
        finally:
            schema.write_bytes(saved)
        self.assertEqual(code, 1, out + err)
        self.assertEqual(doc["error"], "refused")
        self.assertEqual(doc["recovered"]["action"], "resumed")
        self.assertEqual(doc["journal"]["phase"], "swapped")
        self.assertFalse(doc["unchanged"], "the new files are in place and VERSION is not stamped")

    def test_extra_file_in_swapped_target_rolls_back(self):
        t = self.swap_killed_after_first_target()
        extra = Path(t["dir"]) / t["name"] / "stray.txt"
        extra.write_text("not in the download\n", encoding="utf-8")
        code, doc, out, err = self.upd("plan")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(doc["recovered"]["action"], "rolled-back")
        self.assertTrue(doc["recovered"]["message"].startswith("rolled back to "), doc["recovered"]["message"])
        self.assertEqual(self.installed(), self.old)
        self.assertEqual(self.co.version_file.read_text(), "0.5.0\n")
        self.assertEqual(self.leftovers(), [])


class TestStoreInterrupt(unittest.TestCase):
    """The owner A of a store updates 0.5.0 -> 0.6.0 (the schema differs). The staged state is saved once; every run
    restores it, kills `swap` at its N-th mv/cp/rm call and reruns the update from the same checkout."""
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.dl_old = fx.make_mini_download(cls.tmp / "dl-0.5.0", "0.5.0", 1)
        cls.dl_new = fx.make_mini_download(cls.tmp / "dl-0.6.0", "0.6.0", 1, schema_edit=fx.schema_edit_comment)
        cls.pair = fx.make_store_pair(cls.tmp, "0.5.0", download=cls.dl_old)
        cls.a, cls.store = cls.pair.a, cls.pair.store
        fx.write_store_record(cls.store, "0.5.0", fx.owner_id(cls.a))
        cls.lock = cls.store / ".git" / "specwright-gate.lock"
        cls.shims = fx.install_shims(cls.tmp / "shims")
        cls.counter = cls.tmp / "count"
        cls.upd("stage")
        cls.saved = {"code": cls.tmp / "staged-code", "store": cls.tmp / "staged-store"}
        shutil.copytree(cls.a.code, cls.saved["code"])
        shutil.copytree(cls.store, cls.saved["store"])
        cls.old = cls.state()
        cls.upd("swap", count=True)  # the counting run: every mv/cp/rm of the swap, numbered from 1
        cls.log = [line.split(" ", 2) for line in Path(f"{cls.counter}.log").read_text(encoding="utf-8").splitlines()]
        cls.a.version_file.write_text("0.6.0\n")
        cls.upd("finish")
        cls.new = cls.state()
        cls.total = len(cls.log)
        cls.first_rename = next(int(n) for n, tool, args in cls.log if tool == "mv" and ".specwright-update-" in args)
        cls.gate_release = next((int(n) for n, tool, args in cls.log if tool == "rm" and "specwright-gate.lock" in args), 0)

    @classmethod
    def tearDownClass(cls):
        fx.rmtree(cls.tmp)

    @classmethod
    def state(cls):
        return {"skills": fx.tree(cls.a.skills[0]), "agents": fx.tree(cls.a.agents["claude"]), "schema": fx.tree(cls.a.schema),
                "record": fx.store_record_path(cls.store).read_bytes(), "config": (cls.store / "openspec" / "config.yaml").read_bytes()}

    @classmethod
    def restore(cls):
        fx.rmtree(cls.a.code)
        fx.rmtree(cls.store)
        shutil.copytree(cls.saved["code"], cls.a.code)
        shutil.copytree(cls.saved["store"], cls.store)
        for f in (cls.counter, Path(f"{cls.counter}.log")):
            f.unlink(missing_ok=True)

    @classmethod
    def upd(cls, sub, count=False, kill_at=None):
        return fx.run_update(cls.dl_new, [*cls.a.args(), sub], env=cls.pair.env, shim_dir=cls.shims if count else None,
                             count_file=cls.counter if count else None, kill_at=kill_at)

    def lock_owner(self):
        f = self.lock / "owner"
        return f.read_text(encoding="utf-8") if f.exists() else None

    def leftovers(self):
        found = [p.relative_to(r).as_posix() for r in (self.a.code, self.store) for p in r.rglob(".specwright-update-*")]
        return sorted(found) + sorted(p.name for p in self.a.journal.parent.glob("update.*"))

    def test_counting_run_is_sane(self):
        self.assertNotEqual(self.old, self.new)
        self.assertGreater(self.first_rename, 3)  # the token write, the saved config.yaml and STORE, the phase write
        self.assertGreater(self.total, self.first_rename + 8)
        self.assertGreater(self.gate_release, self.first_rename + 8)  # the gate lock is released after the last rename

    def test_kill_during_store_swap_rerun_recovers_and_releases_lock(self):
        for n in range(self.first_rename, self.total + 1):
            with self.subTest(kill_at=n, op=" ".join(self.log[n - 1][1:])):
                self.restore()
                code, _, _, err = self.upd("swap", count=True, kill_at=n)
                self.assertNotEqual(code, 0, "the swap was meant to be killed")
                owner = self.lock_owner()  # held from before the first rename until the schema and STORE are done
                if n <= self.gate_release:  # (the call after it only releases the project's own update lock)
                    self.assertIsNotNone(owner, "the gate lock must still be there")
                    self.assertIn("change: specwright-update 0.5.0 -> 0.6.0", owner)
                    self.assertIn(f"code: {fx.posix(self.a.code)}", owner)
                code, doc, out, err = self.upd("plan")  # the rerun, from the same checkout, recovers first
                self.assertEqual(code, 0, out + err)
                action = doc["recovered"]["action"]
                self.assertIn(action, ("resumed", "rolled-back"))
                self.assertFalse(self.lock.exists(), "the rerun releases the lock")
                if self.a.journal.exists():  # resumed: the prompt stamps VERSION, then finishes
                    self.a.version_file.write_text("0.6.0\n")
                    code, doc, out, err = self.upd("finish")
                    self.assertEqual(code, 0, out + err)
                self.assertEqual(self.state(), self.new if action == "resumed" else self.old)
                self.assertEqual(self.a.version_file.read_text(), "0.6.0\n" if action == "resumed" else "0.5.0\n")
                self.assertEqual(self.leftovers(), [])

    def test_kill_after_lock_before_rename_discards_and_releases(self):
        held_once = False
        for n in range(1, self.first_rename):
            with self.subTest(kill_at=n, op=" ".join(self.log[n - 1][1:])):
                self.restore()
                code, _, _, err = self.upd("swap", count=True, kill_at=n)
                self.assertNotEqual(code, 0, "the swap was meant to be killed")
                owner = self.lock_owner()
                if owner is not None:
                    held_once = True
                    self.assertIn("change: specwright-update 0.5.0 -> 0.6.0", owner)
                code, doc, out, err = self.upd("plan")
                self.assertEqual(code, 0, out + err)
                self.assertEqual(doc["recovered"]["action"], "discarded")
                self.assertEqual(doc["recovered"]["message"], "discarded unfinished update to 0.6.0")
                self.assertFalse(self.lock.exists(), "no lock is left")
                self.assertEqual(self.state(), self.old)
                self.assertEqual(self.a.version_file.read_text(), "0.5.0\n")
                self.assertEqual(self.leftovers(), [])
        self.assertTrue(held_once, "some kill point must fall after the lock was taken")

    def test_lock_without_owner_goes_to_the_user(self):
        self.restore()
        code, _, _, err = self.upd("swap", count=True, kill_at=self.first_rename - 1)
        self.assertNotEqual(code, 0)
        (self.lock / "owner").unlink()  # killed between the mkdir and the owner file
        code, doc, out, err = self.upd("plan")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(doc["error"], "gate_lock_unverified")
        self.assertIn(self.lock.as_posix(), doc["message"])
        self.assertTrue(self.lock.is_dir(), "the lock is not removed for the user")
        self.assertTrue(self.a.journal.exists())
        shutil.rmtree(self.lock)  # the user confirms and removes it
        code, doc, out, err = self.upd("plan")
        self.assertEqual((code, doc["recovered"]["action"]), (0, "discarded"), out + err)
        self.assertEqual(self.state(), self.old)


if __name__ == "__main__":
    unittest.main()
