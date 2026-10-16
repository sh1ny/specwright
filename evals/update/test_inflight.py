"""Changes in flight (scripts/update.sh plan / stage / swap): collection from the working tree, local branches and
remote-tracking refs (design D4), and validation of each change against the new schema on a workflow update.

The failing change is `add-x`: the failing download's schema adds the artifact `research` and makes `specs` require
it, so `add-x` (which has specs but no research) passes `openspec validate` and fails the status dependency rule.

Run: python -m unittest discover evals/update
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("update_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, self.tmp)
        self.env = fx.openspec_env(self.tmp)  # openspec in the scratch roots never touches the user's registry

    def checkout(self, version="0.5.0"):
        self.co = fx.make_checkout(self.tmp, version, skills_dirs=(".claude/skills",),
                                   download=fx.make_mini_download(self.tmp / f"dl-{version}", version))
        return self.co

    def download(self, version="0.6.0", failing=False):
        edit = fx.schema_edit_dependency("research", "specs") if failing else fx.schema_edit_comment
        self.dl = fx.make_mini_download(self.tmp / f"dl-new-{version}{'-bad' if failing else ''}", version, schema_edit=edit)
        return self.dl

    def run_sub(self, sub, dl=None):
        code, doc, out, err = fx.run_update(dl or self.dl, [*self.co.args(), sub], env=self.env)
        self.assertIsNotNone(doc, f"{sub}: no JSON (exit {code}).\nstdout: {out}\nstderr: {err}")
        return code, doc, err

    def installed(self):
        return {"skills": fx.tree(self.co.skills[0]), "agents": fx.tree(self.co.agents["claude"]),
                "schema": fx.tree(self.co.schema), "version": self.co.version_file.read_text()}

    def names(self, doc):
        return {c["name"]: c for c in doc["inflight"]}


class TestCollect(Base):
    def test_change_on_branch_only_is_found(self):
        co = self.checkout()
        fx.add_change_branch(co.code, "add-x")
        self.assertFalse((co.code / "openspec" / "changes" / "add-x").exists())  # main and the working tree hold nothing
        code, doc, err = self.run_sub("plan", self.download())
        self.assertEqual(code, 0, err)
        self.assertEqual(self.names(doc)["add-x"]["source"], "feat/add-x")
        self.assertEqual(self.names(doc)["add-x"]["status"], "validated")
        # the branch's change is read from the branch: against the failing schema it stops the update, naming both
        before = self.installed()
        code, doc, err = self.run_sub("plan", self.download(failing=True))
        self.assertEqual(code, 1, err)
        self.assertEqual(doc["error"], "refused")
        self.assertIn("add-x", doc["message"])
        self.assertIn("feat/add-x", doc["message"])
        self.assertEqual(doc["refusals"][0]["change"], "add-x")
        self.assertEqual(self.installed(), before)

    def test_archived_change_not_in_flight(self):
        co = self.checkout()
        fx.add_change_branch(co.code, "add-z")
        fx.archive_change(co.code, "add-z")  # main holds openspec/changes/archive/2026-10-01-add-z/
        code, doc, err = self.run_sub("plan", self.download(failing=True))
        self.assertEqual(code, 0, err)  # not validated, so the failing schema does not matter
        self.assertNotIn("add-z", self.names(doc))
        self.assertEqual(doc["warnings"], [])

    def test_archive_name_matched_exactly(self):
        co = self.checkout()
        fx.add_change_branch(co.code, "add-z")
        fx.archive_change(co.code, "fix-add-z")  # a longer name: archive/2026-10-01-fix-add-z/ is not add-z's
        code, doc, err = self.run_sub("plan", self.download())
        self.assertEqual(code, 0, err)
        self.assertEqual(self.names(doc)["add-z"]["status"], "validated")

    def test_remote_only_change_is_warning(self):
        co = self.checkout()
        fx.add_change_remote(co.code, "add-v")
        code, doc, err = self.run_sub("plan", self.download(failing=True))
        self.assertEqual(code, 0, err)  # not refused, not validated
        self.assertNotIn("add-v", self.names(doc))
        self.assertEqual([(w["name"], w["ref"]) for w in doc["warnings"]], [("add-v", "origin/feat/add-v")])
        self.assertIn("in flight elsewhere, not validated", doc["warnings"][0]["message"])


class TestInflight(Base):
    def test_valid_change_allows_workflow_update(self):
        co = self.checkout()
        fx.add_change_worktree(co.code, "add-x")
        dl = self.download()
        code, doc, err = self.run_sub("plan")
        self.assertEqual(code, 0, err)
        self.assertTrue(doc["inflight_checked"])
        self.assertEqual(self.names(doc)["add-x"], {"name": "add-x", "source": "working tree", "status": "validated",
                                                    "validated_against": "0.6.0"})
        for sub in ("stage", "swap"):
            code, doc, err = self.run_sub(sub)
            self.assertEqual(code, 0, f"{sub}: {doc} {err}")
            self.assertEqual(self.names(doc)["add-x"]["validated_against"], "0.6.0")
        self.assertEqual(fx.tree(co.schema), fx.tree(dl / "schemas" / "specwright"))
        self.assertFalse((dl / ".update-scratch").exists())  # scratch roots are removed on exit

    def test_failing_change_refuses_workflow_update(self):
        co = self.checkout()
        fx.add_change_worktree(co.code, "add-x")
        self.download(failing=True)
        before = fx.snapshot(co.code)
        for sub in ("plan", "stage"):
            code, doc, err = self.run_sub(sub)
            self.assertEqual(code, 1, f"{sub}: {doc}")
            self.assertEqual(doc["error"], "refused")
            self.assertIn("add-x", doc["message"])
            self.assertIn("research", doc["message"])  # the first error: specs requires research
            self.assertTrue(doc["unchanged"])
            self.assertEqual(fx.snapshot(co.code), before)  # no file written: no staging, journal or lock
        self.assertEqual(co.version_file.read_text(), "0.5.0\n")

    def test_change_started_after_plan_stops_swap(self):
        co = self.checkout()
        self.download()
        code, doc, err = self.run_sub("plan")
        self.assertEqual((code, doc["inflight"]), (0, []), err)
        code, doc, err = self.run_sub("stage")
        self.assertEqual(code, 0, err)
        before = self.installed()
        # a session creates feat/add-w in another worktree after the plan
        wt = self.tmp / "wt-add-w"
        fx.git(co.code, "worktree", "add", "-q", "-b", "feat/add-w", fx.posix(wt), "main")
        for rel, text in fx.change_files("add-w").items():
            fx.write(wt, f"openspec/changes/add-w/{rel}", text)
        fx.commit_all(wt, "feat(add-w): scaffold")
        code, doc, err = self.run_sub("swap")
        self.assertEqual(code, 1, doc)
        self.assertEqual(doc["error"], "inflight_changed")
        self.assertIn("add-w", doc["message"])
        self.assertTrue(doc["unchanged"])
        self.assertEqual(self.installed(), before)  # stopped before any rename
        self.assertIn(b'"phase": "staged"', co.journal.read_bytes())

    def test_patch_update_skips_validation(self):
        co = self.checkout("0.6.0")
        fx.add_change_worktree(co.code, "add-x")
        self.download("0.6.1", failing=True)  # would fail add-x on a workflow update
        code, doc, err = self.run_sub("plan")
        self.assertEqual((code, doc["kind"]), (0, "patch"), err)
        self.assertFalse(doc["inflight_checked"])
        self.assertEqual(doc["inflight"], [])
        for sub in ("stage", "swap"):
            code, doc, err = self.run_sub(sub)
            self.assertEqual(code, 0, f"{sub}: {doc} {err}")
        self.assertFalse((self.dl / ".update-scratch").exists())


if __name__ == "__main__":
    unittest.main()
