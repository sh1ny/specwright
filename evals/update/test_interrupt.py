"""The interruption criterion of the update (design: "Testing the interruption criterion").

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


if __name__ == "__main__":
    unittest.main()
