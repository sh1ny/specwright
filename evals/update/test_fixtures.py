"""Self-test of the update eval fixtures: each layout is built and the real `openspec` CLI runs in it.

Run: python -m unittest discover evals/update
"""
import importlib.util
import io
import os
import tarfile
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

    def os_run(self, args, cwd, env=None):
        r = fx.openspec(args, cwd=cwd, env=env)
        return r.returncode, r.stdout + r.stderr


class TestDownload(Base):
    def test_download_rewrites_version_and_edits_schema(self):
        dl = fx.make_download(self.tmp / "dl", "0.6.0", schema_edit=fx.schema_edit_comment)
        self.assertEqual((dl / "VERSION").read_text(), "0.6.0\n")
        for d in ("skills", "agents", "schemas", "scripts"):
            self.assertTrue((dl / d).is_dir(), d)
        self.assertIn("<!-- v0.6.0 -->", (dl / "skills" / "specwright-branch" / "SKILL.md").read_text(encoding="utf-8"))
        edited = (dl / "schemas" / "specwright" / "schema.yaml").read_bytes()
        self.assertNotEqual(edited, (fx.ROOT / "schemas" / "specwright" / "schema.yaml").read_bytes())

    def test_two_versions_differ(self):
        a = fx.make_download(self.tmp / "a", "0.5.0")
        b = fx.make_download(self.tmp / "b", "0.6.0", drop_skills=("specwright-debug",),
                             add_skills={"specwright-new": "---\nname: specwright-new\n---\n"})
        self.assertNotEqual(fx.tree(a / "skills"), fx.tree(b / "skills"))
        self.assertFalse((b / "skills" / "specwright-debug").exists())
        self.assertTrue((b / "skills" / "specwright-new" / "SKILL.md").is_file())


class TestCheckout(Base):
    def test_checkout_layout_validates(self):
        co = fx.make_checkout(self.tmp, "0.5.0", skills_dirs=(".claude/skills", ".agents/skills"),
                              agents=(("claude", ".claude/agents"), ("omp", ".omp/agents")))
        self.assertEqual(co.version_file.read_text(), "0.5.0\n")
        for sd in co.skills:
            self.assertTrue((sd / "specwright-branch" / "SKILL.md").is_file())
        self.assertTrue((co.agents["claude"] / "specwright-implementer.md").is_file())
        self.assertTrue((co.agents["omp"] / "specwright-implementer.md").is_file())
        self.assertEqual(fx.git(co.code, "status", "--porcelain"), "")
        code, out = self.os_run(["schema", "validate", "specwright"], co.root)
        self.assertEqual(code, 0, out)

    def test_fresh_checkout_has_no_version(self):
        co = fx.make_checkout(self.tmp, None)
        self.assertFalse(co.version_file.exists())
        self.assertFalse(co.schema.exists())
        self.assertTrue((co.code / "openspec" / "config.yaml").is_file())
        self.assertEqual(fx.git(co.code, "branch", "--show-current"), "main")

    def test_args_describe_the_checkout(self):
        co = fx.make_checkout(self.tmp, "0.5.0")
        self.assertEqual(co.args()[:4], ["--code", fx.posix(co.code), "--root", fx.posix(co.root)])
        self.assertIn("claude=" + fx.posix(co.agents["claude"]), co.args())


class TestStorePair(Base):
    def test_store_pair_validates_a_change_in_the_store(self):
        sp = fx.make_store_pair(self.tmp)
        self.assertEqual(fx.git(sp.store, "status", "--porcelain"), "")
        for co in (sp.a, sp.b):
            self.assertEqual(fx.git(co.code, "status", "--porcelain"), "")
            self.assertEqual((co.code / "openspec" / "config.yaml").read_text(), f"store: {fx.STORE_ID}\n")
            self.assertEqual(co.root, sp.store)
            self.assertEqual(co.version_file.read_text(), "0.5.0\n")
        self.assertTrue((sp.store / "openspec" / "schemas" / "specwright" / "schema.yaml").is_file())
        code, out = self.os_run(["schema", "validate", "specwright"], sp.store, sp.env)
        self.assertEqual(code, 0, out)
        fx.add_change_worktree(sp.store, "add-greeting")
        code, out = self.os_run(["validate", "add-greeting"], sp.store, sp.env)
        self.assertEqual(code, 0, out)
        self.assertIn("valid", out)
        # the registry is the scratch one, not the user's
        self.assertTrue((self.tmp / "xdg-data").exists() or (self.tmp / "xdg-config").exists())


class TestChanges(Base):
    def extract_and_validate(self, co, ref, name):
        """What `plan` does for a change on a branch: git archive it into a scratch root and validate there."""
        raw = fx.subprocess.run(["git", "archive", ref, f"openspec/changes/{name}"], cwd=co.code,
                                capture_output=True, check=True).stdout
        scratch = self.tmp / f"scratch-{name}"
        scratch.mkdir()
        with tarfile.open(fileobj=io.BytesIO(raw)) as t:
            t.extractall(scratch)
        fx.shutil.copytree(co.schema, scratch / "openspec" / "schemas" / "specwright")
        fx.write(scratch, "openspec/config.yaml", "schema: specwright\n")
        return self.os_run(["validate", name], scratch)

    def test_worktree_change_validates(self):
        co = fx.make_checkout(self.tmp)
        fx.add_change_worktree(co.code, "add-x")
        code, out = self.os_run(["validate", "add-x"], co.code)
        self.assertEqual(code, 0, out)
        self.assertEqual(fx.git(co.code, "branch", "--list", "feat/*"), "")

    def test_branch_change_is_only_on_its_branch(self):
        co = fx.make_checkout(self.tmp)
        ref = fx.add_change_branch(co.code, "add-x")
        self.assertEqual(ref, "feat/add-x")
        self.assertFalse((co.code / "openspec" / "changes" / "add-x").exists())
        self.assertEqual(fx.git(co.code, "branch", "--show-current"), "main")
        self.assertEqual(fx.git(co.code, "status", "--porcelain"), "")
        self.assertIn("openspec/changes/add-x/proposal.md", fx.git(co.code, "ls-tree", "-r", "--name-only", ref))
        code, out = self.extract_and_validate(co, ref, "add-x")
        self.assertEqual(code, 0, out)
        for prefix in ("bugfix", "refactor", "docs", "chore"):  # every specwright-branch prefix works
            fx.add_change_branch(co.code, f"y-{prefix}", prefix=prefix)
        self.assertEqual(sorted(fx.git(co.code, "for-each-ref", "--format=%(refname:short)", "refs/heads/").split()),
                         sorted(["main", "feat/add-x"] + [f"{p}/y-{p}" for p in ("bugfix", "refactor", "docs", "chore")]))

    def test_remote_change_has_no_local_branch(self):
        co = fx.make_checkout(self.tmp)
        ref = fx.add_change_remote(co.code, "add-v")
        self.assertEqual(ref, "refs/remotes/origin/feat/add-v")
        self.assertEqual(fx.git(co.code, "for-each-ref", "--format=%(refname)", "refs/heads/"), "refs/heads/main")
        self.assertEqual(fx.git(co.code, "for-each-ref", "--format=%(refname)", "refs/remotes/"), ref)
        self.assertEqual(fx.git(co.code, "status", "--porcelain"), "")
        code, out = self.extract_and_validate(co, ref, "add-v")
        self.assertEqual(code, 0, out)

    def test_archive_and_other_schema(self):
        co = fx.make_checkout(self.tmp)
        fx.archive_change(co.code, "add-z")
        self.assertTrue((co.code / "openspec" / "changes" / "archive" / "2026-10-01-add-z" / "proposal.md").is_file())
        fx.add_change_worktree(co.code, "other", schema="spec-driven")
        self.assertIn("schema: spec-driven", (co.code / "openspec" / "changes" / "other" / ".openspec.yaml").read_text())

    def test_failing_change_via_schema_edit(self):
        """schema_edit_dependency: with the edit, specs requires the new artifact `research`, and a change that has
        specs but no research shows specs `done` beside a dependency that is not done (status still exits 0)."""
        co = fx.make_checkout(self.tmp)
        fx.add_change_worktree(co.code, "add-x")
        dl = fx.make_download(self.tmp / "dl-new", "0.6.0", schema_edit=fx.schema_edit_dependency("research", "specs"))
        scratch = self.tmp / "scratch"
        fx.shutil.copytree(dl / "schemas" / "specwright", scratch / "openspec" / "schemas" / "specwright")
        fx.write(scratch, "openspec/config.yaml", "schema: specwright\n")
        fx.shutil.copytree(co.code / "openspec" / "changes" / "add-x", scratch / "openspec" / "changes" / "add-x")
        code, out = self.os_run(["schema", "validate", "specwright"], scratch)
        self.assertEqual(code, 0, out)
        r = fx.openspec(["status", "--change", "add-x", "--json"], cwd=scratch)
        self.assertEqual(r.returncode, 0, r.stderr)
        status = {a["id"]: a for a in fx.json.loads(r.stdout)["artifacts"]}
        self.assertEqual(status["specs"]["status"], "done")
        self.assertNotEqual(status["research"]["status"], "done")


class TestShims(Base):
    def fake_download(self, body):
        dl = self.tmp / "fake-dl"
        fx.write(dl, "scripts/update.sh", "#!/bin/bash\n" + body)
        return dl

    def test_shims_count_every_call(self):
        dl = self.fake_download('d="$1"\ncp "$d/a" "$d/b"\nmv "$d/b" "$d/c"\nrm "$d/c"\necho done > "$d/marker"\n')
        work = self.tmp / "work"
        fx.write(work, "a", "x")
        shims = fx.install_shims(self.tmp / "shimbin")
        count = self.tmp / "count"
        code, _doc, out, err = fx.run_update(dl, [fx.posix(work)], shim_dir=shims, count_file=count)
        self.assertEqual(code, 0, err)
        self.assertEqual(count.read_text().strip(), "3")
        log = Path(str(count) + ".log").read_text().splitlines()
        self.assertEqual([line.split()[1] for line in log], ["cp", "mv", "rm"])
        self.assertEqual((work / "marker").read_text().strip(), "done")
        self.assertFalse((work / "b").exists() or (work / "c").exists())
        self.assertEqual((work / "a").read_text(), "x")

    def test_kill_at_n_stops_the_script_before_the_nth_call(self):
        dl = self.fake_download('d="$1"\ncp "$d/a" "$d/b"\nmv "$d/b" "$d/c"\nrm "$d/c"\necho done > "$d/marker"\n')
        shims = fx.install_shims(self.tmp / "shimbin")
        for n, expect in ((1, set()), (2, {"b"}), (3, {"c"})):
            work = self.tmp / f"work{n}"
            fx.write(work, "a", "x")
            count = self.tmp / f"count{n}"
            code, _doc, _out, err = fx.run_update(dl, [fx.posix(work)], shim_dir=shims, count_file=count, kill_at=n)
            self.assertNotEqual(code, 0, f"kill_at={n} exit")
            self.assertEqual(count.read_text().strip(), str(n))
            self.assertFalse((work / "marker").exists(), f"kill_at={n}: the script went on")
            present = {p.name for p in work.iterdir()} - {"a"}
            self.assertEqual(present, expect, f"kill_at={n}")

    def test_without_count_file_the_shim_passes_through(self):
        dl = self.fake_download('cp "$1/a" "$1/b"\n')
        work = self.tmp / "work"
        fx.write(work, "a", "x")
        shims = fx.install_shims(self.tmp / "shimbin")
        code, _doc, _out, err = fx.run_update(dl, [fx.posix(work)], shim_dir=shims)
        self.assertEqual(code, 0, err)
        self.assertEqual((work / "b").read_text(), "x")


if __name__ == "__main__":
    unittest.main()
