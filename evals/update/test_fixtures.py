"""Self-test of the update eval fixtures: each layout is built and the real `openspec` CLI runs in it.

Run: python -m unittest discover evals/update
"""
import importlib.util
import io
import json
import os
import subprocess
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


class TestProvisionedSw(Base):
    def test_provision_places_a_sw_that_reports_the_version_with_its_notice(self):
        home = self.tmp / "home"
        placed = fx.provision_sw(home, "0.5.0")
        self.assertEqual(placed, home / ".specwright" / "bin" / "0.5.0" / ("sw.exe" if os.name == "nt" else "sw"))
        self.assertTrue((placed.parent / "THIRD_PARTY_NOTICES.txt").is_file())
        done = subprocess.run([str(placed), "version", "--json"], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["version"], "0.5.0")
        other = fx.provision_sw(self.tmp / "home2", "0.5.0")  # the cached build is copied, not rebuilt
        self.assertEqual(other.read_bytes(), placed.read_bytes())

    def test_make_download_provisions_beside_it_and_can_skip(self):
        dl = fx.make_download(self.tmp / "dl-0.6.1", "0.6.1")
        self.assertTrue((fx.sw_home_for(dl) / ".specwright" / "bin" / "0.6.1").is_dir())
        skipped = fx.make_download(self.tmp / "sub" / "dl-0.6.2", "0.6.2", provision=False)
        self.assertFalse(fx.sw_home_for(skipped).exists())


class TestKillSeam(Base):
    """run_update counts sw's file operations and can end it before operation n (SPECWRIGHT_UPDATE_COUNT/KILL_AT)."""

    def setUp(self):
        super().setUp()
        self.dl = fx.make_mini_download(self.tmp / "dl-0.6.0", "0.6.0")
        self.co = fx.make_checkout(self.tmp, "0.5.0", download=fx.make_mini_download(self.tmp / "dl-0.5.0", "0.5.0"))

    def stage(self, **kwargs):
        return fx.run_update(self.dl, [*self.co.args(), "stage"], **kwargs)

    def test_count_file_lists_every_file_operation_in_order(self):
        count = self.tmp / "count"
        code, doc, out, err = self.stage(count_file=count)
        self.assertEqual(code, 0, out + err)
        log = [line.split(" ", 2) for line in count.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([n for n, _op, _args in log], [str(i) for i in range(1, len(log) + 1)])
        self.assertTrue({"mkdir", "cp", "mv"} <= {op for _n, op, _args in log}, log)

    def test_kill_at_n_ends_sw_before_the_nth_operation(self):
        count = self.tmp / "count"
        code, _doc, out, _err = self.stage(count_file=count)
        total = len(count.read_text(encoding="utf-8").splitlines())
        for n in (1, total):
            fx.rmtree(self.co.code / "openspec" / ".specwright")
            killed = self.tmp / f"count-{n}"
            code, _doc, out, err = self.stage(count_file=killed, kill_at=n)
            self.assertEqual(code, 137, f"kill_at={n}: {out}{err}")
            self.assertEqual(out, "")
            self.assertEqual(len(killed.read_text(encoding="utf-8").splitlines()), n)

    def test_without_count_file_nothing_is_logged_and_nothing_is_killed(self):
        code, _doc, out, err = self.stage(kill_at=1)
        self.assertEqual(code, 0, out + err)
        self.assertFalse((self.tmp / "count").exists())


if __name__ == "__main__":
    unittest.main()
