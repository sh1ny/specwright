"""Script tests for skills/specwright-finish/scripts/finish.sh (undo-archive-plan).

Every test builds a real git repo with fixtures.py, runs the real script, applies the printed `script`
(and `after_rerun`) with bash, and asserts on the resulting tree, index and refs. One JSON document on
stdout per call; exit 0 = done, 1 = stop (the JSON has "error" and "message"), 2 = usage.

Run: python -m unittest discover evals/finish
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("finish_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

P = "openspec"
SPEC_A = f"{P}/specs/a/spec.md"
SPEC_B = f"{P}/specs/b/spec.md"
BRANCH = "bugfix/add-x"


def ad(name):
    return f"{P}/changes/archive/{fx.DATE}-{name}"


def cd(name):
    return f"{P}/changes/{name}"


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, self.tmp)
        self.work = fx.make_repo(self.tmp)
        self.scripts = Path(tempfile.mkdtemp())  # printed scripts live outside the repo
        self.addCleanup(fx.rmtree, self.scripts)

    def git(self, *args, check=True):
        return fx.git(self.work, *args, check=check)

    def on_branch(self, name=BRANCH):
        self.git("checkout", "-q", "-b", name)

    def pair(self, x_deltas=None, y_deltas=None):
        """On bugfix/add-x: add-x (DEFERRED) and add-y (APPROVE), both committed."""
        self.on_branch()
        fx.make_change(self.work, "add-x", "DEFERRED", x_deltas or {"a": "X thing"})
        fx.make_change(self.work, "add-y", "APPROVE", y_deltas or {"a": "Y thing"})

    def single(self, deltas=None, verdict="DEFERRED"):
        self.on_branch()
        fx.make_change(self.work, "add-x", verdict, deltas or {"a": "New thing", "b": "B thing"})

    def run_all(self, change="add-x", **kw):
        return fx.run_scripts(self.work, self.scripts, change, **kw)

    def ok(self, out):
        code, doc, raw = out.plan
        self.assertEqual(code, 0, raw)
        self.assertIs(doc["ok"], True, raw)
        self.assertEqual(out.script.returncode, 0, out.script.stdout + out.script.stderr)
        return doc

    def assertStops(self, out, error, *needles):
        code, doc, raw = out
        self.assertEqual(code, 1, raw)
        self.assertIs(doc["ok"], False, raw)
        self.assertEqual(doc["error"], error, raw)
        self.assertNotIn("script", doc, raw)
        for n in needles:
            self.assertIn(n, doc["message"], raw)

    def count(self, rev="HEAD"):
        return int(self.git("rev-list", "--count", rev))

    def paths_of(self, rev):
        return set(self.git("diff-tree", "-r", "--no-commit-id", "--name-only", rev).splitlines())


class TestFixturesSmoke(Base):
    def test_fixtures_build_archive_and_fake_openspec(self):
        self.single({"a": "New thing", "b": "B thing"})
        fx.make_change(self.work, "add-y", "APPROVE", {"a": "Y thing"})
        before = fx.tree_files(self.work, cd("add-x"))
        self.assertIn("VERDICT: DEFERRED", before["review.md"])
        a = fx.archive(self.work, "add-x", commit_it=True, marker=True)
        self.assertEqual(self.git("rev-parse", "HEAD"), a)
        self.assertFalse((self.work / cd("add-x")).exists())
        self.assertEqual(set(fx.tree_files(self.work, ad("add-x"))) - {"specwright-change.yaml"}, set(before))
        self.assertIn("New thing", fx.read(self.work, SPEC_A))
        self.assertIn("B thing", fx.read(self.work, SPEC_B))
        r = fx.run_bash(self.work, self.scripts, "set -euo pipefail\nopenspec archive add-y --yes\n", "fake")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.work / ad("add-y") / "review.md").is_file())
        self.assertIn("Y thing", fx.read(self.work, SPEC_A))


class TestUndoPlan(Base):
    # ---- Resume takes the newest add of the archive ---------------------------------------------------------
    def test_archive_commit_is_the_add_not_a_later_edit(self):
        self.single({"a": "New thing"})
        a = fx.archive(self.work, "add-x", commit_it=True)
        fx.commit(self.work, "fix(add-x): review fix", {f"{ad('add-x')}/design.md": "# Design\n\nFixed.\n"})
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["mode"], "committed")
        self.assertEqual(doc["archive_commit"], a)

    def test_rearchived_targets_newest_add_only(self):
        self.single({"a": "New thing"})
        a1 = fx.archive(self.work, "add-x", commit_it=True)
        rv = fx.revert(self.work, a1)
        a2 = fx.archive(self.work, "add-x", commit_it=True)
        history = self.git("rev-list", "HEAD")
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(doc["archive_commit"], a2)
        self.assertEqual(self.count(), self.count("main") + 5)  # planning, A1, revert, A2, one undo commit
        self.assertEqual(self.git("rev-list", "HEAD~1"), history)
        self.assertIn(a1, history.split())
        self.assertIn(rv, history.split())
        self.assertTrue((self.work / cd("add-x") / "review.md").is_file())
        self.assertFalse((self.work / ad("add-x")).exists())
        self.assertEqual(fx.read(self.work, SPEC_A), self.git("show", f"{a2}^:{SPEC_A}") + "\n")

    def test_newest_add_reverted_is_no_archive(self):
        self.single({"a": "New thing"})
        a1 = fx.archive(self.work, "add-x", commit_it=True)
        fx.revert(self.work, a1)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertStops((code, doc, raw), "no_archive")
        self.assertEqual(doc["commits"], [a1])

    # ---- A deferred archive's undo is planned by a script that runs nothing ----------------------------------
    def test_plan_writes_nothing(self):
        self.single({"a": "New thing", "b": "B thing"})
        fx.archive(self.work, "add-x")  # uncommitted
        fx.edit(self.work, SPEC_A, "Baseline", "Edited baseline")
        before = fx.state(self.work)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["mode"], "uncommitted")
        self.assertEqual(fx.state(self.work), before)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "chore(add-x): archive change")
        self.git("checkout", "-q", "main")
        before = fx.state(self.work)
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 0, raw)
        self.assertEqual(fx.state(self.work), before)
        # also from a directory that is not the repo, through --dir
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH, cwd=self.tmp, dir_=self.work)
        self.assertEqual(code, 0, raw)
        self.assertEqual(fx.state(self.work), before)

    def test_resume_on_dirty_main_refused(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        self.git("checkout", "-q", "main")
        fx.edit(self.work, "README.md", "demo", "demo edited")
        before = fx.state(self.work)
        out = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertStops(out, "dirty_tree", "README.md")
        self.assertEqual(fx.state(self.work), before)

    def test_no_archive_refused(self):
        self.single({"a": "New thing"})
        before = fx.state(self.work)
        self.assertStops(fx.run_plan(self.work, "add-x"), "no_archive")
        self.assertStops(fx.run_plan(self.work, "add-z"), "no_archive")
        self.assertEqual(fx.state(self.work), before)

    def test_guard_fails_after_branch_moved(self):
        self.single({"a": "New thing", "b": "B thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        fx.commit(self.work, "feat: later", {"src/app.py": "print('v2')\n"})
        before = fx.state(self.work)
        r = fx.run_bash(self.work, self.scripts, doc["script"], "undo")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(fx.state(self.work), before)
        self.assertFalse(Path(doc["backup_dir"]).exists())
        self.assertIn("New thing", fx.read(self.work, SPEC_A))  # no main spec restored

    def test_guard_fails_before_checkout_on_a_resume(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        self.git("checkout", "-q", "main")
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 0, raw)
        self.git("checkout", "-q", BRANCH)
        fx.commit(self.work, "feat: later", {"src/app.py": "print('v2')\n"})
        self.git("checkout", "-q", "main")
        before = fx.state(self.work)
        r = fx.run_bash(self.work, self.scripts, doc["script"], "undo")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertEqual(fx.state(self.work), before)

    def test_staged_changes_refused(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.edit(self.work, "src/app.py", "v1", "v2")
        self.git("add", "src/app.py")
        self.assertStops(fx.run_plan(self.work, "add-x"), "staged_changes", "src/app.py")

    def test_target_exists_refused(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.write(self.work, f"{cd('add-x')}/notes.md", "recreated\n")
        self.assertStops(fx.run_plan(self.work, "add-x"), "target_exists", cd("add-x"))

    def test_backup_exists_refused_and_script_refuses_to_overwrite(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        Path(doc["backup_dir"]).mkdir(parents=True)
        self.assertStops(fx.run_plan(self.work, "add-x"), "backup_exists")
        before = fx.state(self.work)
        r = fx.run_bash(self.work, self.scripts, doc["script"], "undo")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(fx.state(self.work), before)

    # ---- The undo restores the pre-archive state without losing any edit -----------------------------------
    def test_uncommitted_single_archive(self):
        self.single({"a": "New thing", "b": "B thing"})
        before_change = fx.tree_files(self.work, cd("add-x"))
        head = self.git("rev-parse", "HEAD")
        fx.archive(self.work, "add-x")
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(doc["mode"], "uncommitted")
        self.assertIsNone(doc["archive_commit"])
        self.assertEqual([m["name"] for m in doc["members"]], ["add-x"])
        self.assertEqual(fx.tree_files(self.work, cd("add-x")), before_change)
        self.assertFalse((self.work / ad("add-x")).exists())
        self.assertEqual(fx.read(self.work, SPEC_A), fx.base_spec("a"))
        self.assertFalse((self.work / SPEC_B).exists())
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all"), "")

    def test_uncommitted_spec_edit_backed_up(self):
        self.single({"a": "New thing", "b": "B thing"})
        fx.archive(self.work, "add-x")
        fx.edit(self.work, SPEC_A, "Baseline purpose", "My own purpose")
        out = self.run_all()
        doc = self.ok(out)
        self.assertTrue(doc["warnings"])
        self.assertEqual(fx.read(self.work, SPEC_A), fx.base_spec("a"))
        saved = Path(doc["backup_dir"]) / "amended" / SPEC_A
        self.assertIn("My own purpose", saved.read_text(encoding="utf-8"))
        self.assertIn("New thing", saved.read_text(encoding="utf-8"))
        self.assertTrue((Path(doc["backup_dir"]) / "amended" / SPEC_B).is_file())

    def test_committed_with_later_amendment(self):
        self.single({"a": "New thing"})
        a = fx.archive(self.work, "add-x", commit_it=True)
        fx.edit(self.work, f"{ad('add-x')}/design.md", "Original design.", "Amended design.")
        fx.edit(self.work, SPEC_A, "Baseline purpose", "Amended purpose")
        fx.commit(self.work, "docs(add-x): amend")
        refs = {k: v for k, v in (ln.split(" ", 1)[::-1] for ln in self.git("for-each-ref", "--format=%(objectname) %(refname)").splitlines())}
        n = self.count()
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(self.count(), n + 1)
        self.assertIn("Amended design.", fx.read(self.work, f"{cd('add-x')}/design.md"))
        self.assertEqual(fx.read(self.work, SPEC_A), fx.base_spec("a"))
        self.assertEqual(self.git("show", f"{a}^:{SPEC_A}") + "\n", fx.read(self.work, SPEC_A))
        self.assertIn("Amended purpose", (Path(doc["backup_dir"]) / "amended" / SPEC_A).read_text(encoding="utf-8"))
        self.assertIn("New thing", (Path(doc["backup_dir"]) / "base" / SPEC_A).read_text(encoding="utf-8"))
        self.assertNotIn("Amended purpose", (Path(doc["backup_dir"]) / "base" / SPEC_A).read_text(encoding="utf-8"))
        self.assertEqual(doc["amended"], [SPEC_A])
        self.assertFalse((self.work / ad("add-x")).exists())
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all"), "")
        new_refs = {k: v for k, v in (ln.split(" ", 1)[::-1] for ln in self.git("for-each-ref", "--format=%(objectname) %(refname)").splitlines())}
        changed = {k for k in set(refs) | set(new_refs) if refs.get(k) != new_refs.get(k)}
        self.assertEqual(changed, {f"refs/heads/{BRANCH}"})

    def test_amendment_survives_bulk_rerun(self):
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        fx.edit(self.work, SPEC_A, "Baseline purpose", "Amended purpose")
        fx.commit(self.work, "docs: amend the spec")
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(doc["amended"], [SPEC_A])
        self.assertTrue(doc["script"].startswith("set -euo pipefail\n"))
        self.assertTrue(doc["after_rerun"].startswith("set -euo pipefail\n"))
        self.assertIsNotNone(out.after)
        self.assertEqual(out.after.returncode, 0, out.after.stdout + out.after.stderr)
        text = fx.read(self.work, SPEC_A)
        self.assertIn("Y thing", text)
        self.assertIn("Amended purpose", text)
        self.assertNotIn("X thing", text)
        self.assertNotIn("<<<<<<<", text)
        self.assertTrue((self.work / ad("add-y") / "review.md").is_file())  # rerun archive, uncommitted: no A yet
        self.assertTrue((self.work / cd("add-x") / "review.md").is_file())  # the deferred change stays unarchived

    def test_unrelated_paths_kept(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.edit(self.work, f"{ad('add-x')}/design.md", "Original design.", "Amended design.")
        fx.write(self.work, "src/app.py", "print('v2')\n")
        fx.commit(self.work, "feat: amend the archive copy and change the app")
        out = self.run_all()
        self.ok(out)
        self.assertEqual(fx.read(self.work, "src/app.py"), "print('v2')\n")
        for path in self.paths_of("HEAD"):
            self.assertTrue(path.startswith((f"{P}/changes/", f"{P}/specs/")), path)
        self.assertNotIn("src/app.py", self.paths_of("HEAD"))

    def test_uncommitted_edit_in_archive_copy_carried(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.edit(self.work, f"{ad('add-x')}/tasks.md", "do it", "do it with an edit")
        fx.write(self.work, f"{ad('add-x')}/scratch.md", "untracked note\n")
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(sorted(doc["carried_edits"]), [f"{ad('add-x')}/scratch.md", f"{ad('add-x')}/tasks.md"])
        self.assertIn("do it with an edit", fx.read(self.work, f"{cd('add-x')}/tasks.md"))
        self.assertEqual(fx.read(self.work, f"{cd('add-x')}/scratch.md"), "untracked note\n")
        self.assertNotIn("with an edit", self.git("show", f"HEAD:{cd('add-x')}/tasks.md"))  # the edit is not committed
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all").splitlines(),
                         [f"M {cd('add-x')}/tasks.md", f"?? {cd('add-x')}/scratch.md"])

    def test_committed_bulk_undone_whole(self):
        self.pair()
        a = fx.archive(self.work, ["add-x", "add-y"], commit_it=True, marker=True)
        n = self.count()
        out = self.run_all(typ=None)
        doc = self.ok(out)
        self.assertEqual({m["name"]: m["deferred"] for m in doc["members"]}, {"add-x": True, "add-y": False})
        self.assertTrue(doc["warnings"])
        self.assertEqual(self.count(), n + 1)
        subject = self.git("log", "-1", "--format=%s")
        self.assertTrue(subject.startswith("fix(add-x): undo archive of "), subject)
        self.assertIn("add-x", subject)
        self.assertIn("add-y", subject)
        for name in ("add-x", "add-y"):
            self.assertTrue((self.work / cd(name) / "review.md").is_file())
            self.assertFalse((self.work / ad(name)).exists())
            self.assertFalse((self.work / cd(name) / "specwright-change.yaml").exists())
        self.assertEqual(fx.read(self.work, SPEC_A), self.git("show", f"{a}^:{SPEC_A}") + "\n")
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all"), "")
        self.assertEqual(self.git("ls-tree", "-r", "--name-only", "HEAD", "--", f"{P}/changes/archive"), "")

    def test_uncommitted_bulk_members_found(self):
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"])
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual({m["name"] for m in doc["members"]}, {"add-x", "add-y"})
        self.assertTrue(doc["warnings"])
        for name in ("add-x", "add-y"):
            self.assertTrue((self.work / cd(name) / "review.md").is_file())
            self.assertFalse((self.work / ad(name)).exists())
        self.assertFalse((self.work / P / "changes" / "archive").exists() and any((self.work / P / "changes" / "archive").iterdir()))
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all"), "")

    def test_resume_on_main_checks_out_branch(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        tip = self.git("rev-parse", BRANCH)
        main = self.git("rev-parse", "main")
        self.git("checkout", "-q", "main")
        out = self.run_all(branch=BRANCH)
        self.ok(out)
        self.assertEqual(self.git("branch", "--show-current"), BRANCH)
        self.assertEqual(self.git("rev-parse", "main"), main)
        self.assertEqual(self.git("rev-parse", "HEAD~1"), tip)
        self.assertTrue((self.work / cd("add-x") / "review.md").is_file())

    def test_rerun_conflict_stops_and_keeps_copies(self):
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        fx.edit(self.work, SPEC_A, "SHALL do y thing.", "SHALL do y thing, amended.")
        fx.commit(self.work, "docs: amend the spec")

        def rework(res):  # the user reworks add-y's delta line the amendment also changed
            fx.edit(self.work, f"{cd('add-y')}/specs/a/spec.md", "SHALL do y thing.", "SHALL do y thing, reworked.")

        out = self.run_all(between=rework)
        doc = self.ok(out)
        self.assertNotEqual(out.after.returncode, 0)
        self.assertIn("<<<<<<<", fx.read(self.work, SPEC_A))
        self.assertTrue((Path(doc["backup_dir"]) / "base" / SPEC_A).is_file())
        self.assertTrue((Path(doc["backup_dir"]) / "amended" / SPEC_A).is_file())

    def test_spec_only_the_deferred_change_synced_is_never_merged(self):
        self.pair({"a": "X thing", "b": "B thing"}, {"a": "Y thing"})
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        fx.edit(self.work, SPEC_A, "Baseline purpose", "Amended purpose")
        fx.edit(self.work, SPEC_B, "SHALL do b thing.", "SHALL do b thing, amended.")
        fx.commit(self.work, "docs: amend both specs")
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(sorted(doc["amended"]), [SPEC_A, SPEC_B])
        self.assertIsNotNone(out.after)
        self.assertEqual(out.after.returncode, 0, out.after.stdout + out.after.stderr)
        self.assertIn("Amended purpose", fx.read(self.work, SPEC_A))
        self.assertFalse((self.work / SPEC_B).exists())  # not recreated, and never fed to merge-file
        saved = Path(doc["backup_dir"]) / "amended" / SPEC_B
        self.assertIn("amended", saved.read_text(encoding="utf-8"))

    def test_single_archive_keeps_amendment_without_after_rerun(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.edit(self.work, SPEC_A, "Baseline purpose", "Amended purpose")
        fx.commit(self.work, "docs: amend the spec")
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(doc["amended"], [SPEC_A])
        self.assertIsNone(doc["after_rerun"])
        self.assertIn("Amended purpose", (Path(doc["backup_dir"]) / "amended" / SPEC_A).read_text(encoding="utf-8"))

    def test_store_prefix_and_type_option(self):
        P2 = "planning"
        fx.git(self.work, "checkout", "-q", "-b", "feat/add-x")
        fx.write(self.work, f"{P2}/specs/a/spec.md", fx.base_spec("a"))
        fx.commit(self.work, "chore: planning root")
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing"}, prefix=P2)
        fx.archive(self.work, "add-x", prefix=P2, commit_it=True)
        out = self.run_all(prefix=P2, typ="docs")
        self.ok(out)
        self.assertTrue(self.git("log", "-1", "--format=%s").startswith("docs(add-x): undo archive of add-x"))
        self.assertTrue((self.work / P2 / "changes" / "add-x" / "review.md").is_file())

    def crlf_checkout(self):
        """Check every tracked file out again with core.autocrlf=true and no eol attribute, as Git for Windows does."""
        self.git("config", "core.autocrlf", "true")
        for f in self.git("ls-files").splitlines():
            (self.work / f).unlink()
        self.git("checkout", "--", ".")
        self.assertIn(b"\r\n", (self.work / SPEC_A).read_bytes())

    def test_crlf_checkout_is_not_an_amendment(self):
        # Pre-ship P2: the working tree under autocrlf holds CRLF, the stored blob LF; that alone is no edit.
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        self.crlf_checkout()
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(doc["amended"], [])
        self.assertEqual(doc["carried_edits"], [])
        self.assertIsNone(doc["after_rerun"])
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all"), "")

    def test_crlf_checkout_saves_base_in_checkout_form(self):
        # The base copy must match the amended copy's line endings, or merge-file sees every line as changed.
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        self.crlf_checkout()
        spec = (self.work / SPEC_A).read_bytes()
        (self.work / SPEC_A).write_bytes(spec.replace(b"Baseline purpose", b"Amended purpose", 1))
        fx.git(self.work, "commit", "-q", "-am", "docs: amend the spec")
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(doc["amended"], [SPEC_A])
        base = (Path(doc["backup_dir"]) / "base" / SPEC_A).read_bytes()
        amended = (Path(doc["backup_dir"]) / "amended" / SPEC_A).read_bytes()
        self.assertIn(b"\r\n", base)
        self.assertEqual(base.replace(b"Baseline purpose", b"Amended purpose", 1), amended)

    # ---- PR #108 review round 1 ------------------------------------------------------------------------------
    def test_uncommitted_nested_capability(self):
        # Codex P1: a nested capability (specs/<area>/<id>/spec.md) is a main spec the archive created too.
        nested = f"{P}/specs/id/auth/spec.md"
        self.single({"a": "New thing", "id/auth": "Auth thing"})
        fx.archive(self.work, "add-x")
        self.assertTrue((self.work / nested).is_file())
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(doc["main_specs"], {"modified": [SPEC_A], "created": [nested]})
        self.assertFalse((self.work / nested).exists())
        self.assertEqual(fx.read(self.work, SPEC_A), fx.base_spec("a"))
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all"), "")

    def dated_pair(self, commit_it):
        self.on_branch()
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "X thing"})
        fx.make_change(self.work, "2026-01-01-hotfix", "APPROVE", {"b": "Hot thing"})
        fx.archive(self.work, ["add-x", "2026-01-01-hotfix"], commit_it=commit_it)
        self.assertTrue((self.work / P / "changes" / "archive" / "2026-01-01-hotfix").is_dir())

    def assert_dated_restored(self, out):
        doc = self.ok(out)
        self.assertEqual({m["name"] for m in doc["members"]}, {"add-x", "2026-01-01-hotfix"})
        self.assertTrue((self.work / cd("2026-01-01-hotfix") / "review.md").is_file())
        self.assertFalse((self.work / cd("hotfix")).exists())
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all"), "")

    def test_bulk_member_with_dated_name_committed(self):
        # Codex P2: a change whose own name starts with a date keeps that name.
        self.dated_pair(commit_it=True)
        self.assert_dated_restored(self.run_all())

    def test_bulk_member_with_dated_name_uncommitted(self):
        self.dated_pair(commit_it=False)
        self.assert_dated_restored(self.run_all())

    def test_two_archives_of_one_member_refused(self):
        # Kody: two archive directories that restore to the same changes/<name>/ would nest one in the other.
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"])
        fx.write(self.work, f"{P}/changes/archive/2026-10-18-add-y/review.md", "# Review\n\nVERDICT: APPROVE\n")
        before = fx.state(self.work)
        self.assertStops(fx.run_plan(self.work, "add-x"), "duplicate_member", "2026-10-18-add-y", f"{fx.DATE}-add-y", cd("add-y"))
        self.assertEqual(fx.state(self.work), before)

    def test_deleted_synced_spec_refused(self):
        # Kody: a synced main spec deleted from the working tree would stop the script after it made the backup dir.
        for commit_it in (False, True):
            with self.subTest(committed=commit_it):
                if commit_it:
                    self.git("checkout", "-q", "-f", "main")
                    self.git("clean", "-fdq")
                    self.git("branch", "-D", BRANCH)
                self.single({"a": "New thing"})
                fx.archive(self.work, "add-x", commit_it=commit_it)
                (self.work / SPEC_A).unlink()
                before = fx.state(self.work)
                self.assertStops(fx.run_plan(self.work, "add-x"), "dirty_tree", SPEC_A)
                self.assertEqual(fx.state(self.work), before)

    def test_deleted_archive_dir_refused(self):
        # Kody: a committed archive directory deleted from the working tree would leave the undo commit made and the
        # working tree half fixed.
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.rmtree(self.work / ad("add-x"))
        before = fx.state(self.work)
        self.assertStops(fx.run_plan(self.work, "add-x"), "dirty_tree", ad("add-x"))
        self.assertEqual(fx.state(self.work), before)

    def test_later_deletion_of_synced_spec_kept(self):
        # PR #108 round 2, Codex P2: a later commit that deleted a main spec the archive modified is an amendment too;
        # the undo must not bring the spec back.
        self.single({"a": "New thing", "b": "B thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        self.git("rm", "-q", SPEC_A)
        fx.git(self.work, "commit", "-q", "-m", "docs: retire capability a")
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(doc["main_specs"]["modified"], [])
        self.assertFalse((self.work / SPEC_A).exists())
        self.assertNotIn(SPEC_A, self.git("ls-tree", "-r", "--name-only", "HEAD"))
        self.assertFalse((self.work / SPEC_B).exists())
        self.assertTrue(any(SPEC_A in w for w in doc["warnings"]), doc["warnings"])
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all"), "")

    def test_usage_errors_exit_2(self):
        for args in (["undo-archive-plan"], ["undo-archive-plan", "--change", "x"], ["nope"], ["undo-archive-plan", "--bogus", "1"]):
            code, doc, raw = fx.run_finish(self.work, *args)
            self.assertEqual(code, 2, raw)
            self.assertIs(doc["ok"], False, raw)


if __name__ == "__main__":
    unittest.main()
