"""Tests of `sw finish undo-archive-plan`.

Every test builds a real git repo with fixtures.py, runs the real `sw`, runs the printed `steps`
(and `after_rerun_steps`), and asserts on the resulting tree, index and refs. One JSON document on
stdout per call; exit 0 = done, 1 = stop (the JSON has "error" and "message"), 2 = usage.

Run: python -m unittest discover evals/finish
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("finish_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)
import bashexe  # noqa: E402
import gitlog  # noqa: E402  (fixtures.py puts evals/vcs on sys.path)
import jjenv  # noqa: E402
from vcs_test_support import STAMP, sw_home, sw_run  # noqa: E402

P = "openspec"
SPEC_A = f"{P}/specs/a/spec.md"
SPEC_B = f"{P}/specs/b/spec.md"
BRANCH = "bugfix/add-x"
DIRTY_PREFIX = "The working tree is dirty, so the branch cannot be checked out: "


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
        self.assertNotIn("steps", doc, raw)
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

NL = "\n"
MINE = "# mine" + NL * 2 + "A new spec of my own." + NL

NETWORK_RX = re.compile(r"(?<![\w-])(fetch|pull|push|ls-remote)(?![\w-])|(?<![\w./-])gh(?![\w-])")


DART_FINISH = fx.ROOT / "cli" / "lib" / "src" / "finish"


def dart_network_lines(root):
    """(file name, line number, text) of every non-`//` line of the Dart files under root that names a network command."""
    found = []
    for path in sorted(Path(root).rglob("*.dart")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.lstrip().startswith("//") and NETWORK_RX.search(line):
                found.append((path.name, n, line.strip()))
    return found


class TestNoNetwork(Base):
    def test_plan_runs_no_network_command(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        self.git("remote", "add", "origin", "https://unreachable.invalid/nowhere.git")
        bindir = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, bindir)
        log = bindir / "gh.log"
        fake = bindir / "gh"
        fake.write_text("#!/usr/bin/env bash" + NL + f'echo "$@" >> "{log.as_posix()}"' + NL + "sleep 600" + NL, encoding="utf-8", newline=NL)
        fake.chmod(0o755)
        env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ.get("PATH", ""),
                   SPECWRIGHT_HOME=str(fx.vcs_test_support.sw_home()))
        args = ["finish", "undo-archive-plan", "--change", "add-x", "--archived-name", f"{fx.DATE}-add-x",
                "--prefix", P, "--main", "main"]
        t0 = time.monotonic()
        r = fx.swcall.run(args, cwd=self.work, env=env, timeout=30)
        self.assertLess(time.monotonic() - t0, 30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIs(__import__("json").loads(r.stdout)["ok"], True)
        self.assertFalse(log.exists(), "gh was called: " + (log.read_text() if log.exists() else ""))

    def test_sw_finish_source_has_no_network_command(self):
        self.assertTrue(list(DART_FINISH.rglob("*.dart")), "no Dart source under cli/lib/src/finish")
        hits = dart_network_lines(DART_FINISH)
        self.assertEqual(hits, [], "sw finish runs a network command: " + "; ".join(f"{f} line {n}: {t}" for f, n, t in hits))

    def test_dart_scan_names_an_injected_line(self):
        copy = self.scripts / "finish"
        shutil.copytree(DART_FINISH, copy)
        target = copy / "undo_plan.dart"
        lines = target.read_text(encoding="utf-8").splitlines()
        lines.insert(40, "  await git(top, ['fetch', 'origin']);")
        lines.insert(41, "  // git push origin is only a comment")
        target.write_text(NL.join(lines) + NL, encoding="utf-8", newline=NL)
        self.assertEqual(dart_network_lines(copy), [("undo_plan.dart", 41, "await git(top, ['fetch', 'origin']);")])


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
        # D9: the report holds the path whole, and the message reads as it always did
        self.assertEqual(out[1]["files"], ["README.md"], out[2])
        self.assertEqual(out[1]["message"], DIRTY_PREFIX + "M README.md", out[2])
        self.assertEqual(fx.state(self.work), before)

    # ---- The undo planner reports paths whole (change-finish, D2) ----------------------------------------------
    def resume_on_main(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        self.git("checkout", "-q", "main")

    def dirty_doc(self):
        """The `dirty_tree` document of a resume on `main`, the repository unchanged."""
        before = fx.state(self.work)
        out = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertStops(out, "dirty_tree")
        self.assertEqual(fx.state(self.work), before)
        return out[1]

    def test_first_dirty_path_keeps_its_first_character(self):
        self.resume_on_main()
        fx.edit(self.work, "README.md", "demo", "demo edited")
        doc = self.dirty_doc()
        self.assertEqual(doc["files"], ["README.md"])
        self.assertNotIn("EADME.md", doc["files"])

    def test_a_name_that_porcelain_quotes_is_reported_unquoted(self):
        self.resume_on_main()
        fx.write(self.work, "café.md", "x\n")
        self.assertEqual(self.git("-c", "core.quotePath=true", "status", "--porcelain"), '?? "caf\\303\\251.md"', "the fixture's name is not quoted")
        doc = self.dirty_doc()
        self.assertEqual(doc["files"], ["café.md"])
        self.assertTrue(doc["message"].endswith("?? café.md"), doc["message"])

    def test_a_staged_rename_reports_both_paths(self):
        fx.commit(self.work, "docs: notes", {"notes.md": "notes\n"})
        self.resume_on_main()
        self.git("mv", "notes.md", "old-notes.md")
        doc = self.dirty_doc()
        self.assertEqual(sorted(doc["files"]), ["notes.md", "old-notes.md"])
        self.assertTrue(doc["message"].endswith("R notes.md -> old-notes.md"), doc["message"])

    def test_planner_leaves_a_stale_index_alone(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        index, readme = self.work / ".git" / "index", self.work / "README.md"
        stat = readme.stat()
        os.utime(readme, (stat.st_atime, stat.st_mtime + 100))  # the same bytes, another mtime: a stale stat entry
        before = index.read_bytes()
        self.git("status", "--porcelain")
        self.assertNotEqual(index.read_bytes(), before, "the stat entry is not stale: a plain git status leaves the index alone")
        index.write_bytes(before)
        shim = gitlog.install(self.tmp / "gitshim", real_git=jjenv.real_git(), log_path=self.tmp / "git.jsonl")
        r = sw_run(["finish", *fx.plan_args("add-x")], cwd=self.work, env={"GIT_OPTIONAL_LOCKS": "1"}, shim=shim, stamp=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(index.read_bytes(), before, "the plan rewrote the index")
        calls = shim.calls()
        # the planner's read-only reads: its status reads and its index-flag scan (`ls-files -v`, C45)
        quiet = lambda c: c["action"] == "status" or (c["action"] == "ls-files" and "-v" in c["argv"])
        status = [c for c in calls if quiet(c)]
        others = [c for c in calls if not quiet(c)]
        # the settings reader's `show-ref` (detect_main) runs on every plan, `main_branch` set or not
        for action in ("rev-parse", "show-ref"):
            self.assertTrue(status and any(c["action"] == action for c in others), f"the shim saw no {action} call of the plan")
        # every read-only read runs with the optional locks off; every other call keeps the caller's environment
        self.assertEqual({c["optional_locks"] for c in status}, {"0"}, status)
        self.assertEqual({c["optional_locks"] for c in others}, {"1"}, others)

    @unittest.skipIf(sys.platform == "win32", "platform: Windows refuses a backslash in a file name")
    def test_a_name_with_a_backslash_keeps_it(self):
        self.resume_on_main()
        fx.write(self.work, "a\\b.md", "x\n")
        doc = self.dirty_doc()
        self.assertEqual(doc["files"], ["a\\b.md"])
        self.assertTrue(doc["message"].endswith("?? a\\b.md"), doc["message"])

    def committed_with_older_archive(self):
        """On the change branch: add-x archived and committed, beside an older committed archive `add-y`."""
        self.single({"a": "New thing"})
        old = f"{P}/changes/archive/2026-10-18-add-y"
        fx.commit(self.work, "docs(add-y): older archive", {f"{old}/review.md": "# Review\n\nVERDICT: APPROVE\n"})
        fx.archive(self.work, "add-x", commit_it=True)
        return self.work / old

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: macOS and Windows file systems refuse a name with invalid UTF-8 bytes")
    def test_a_non_utf8_name_in_an_unrelated_archive_is_no_obstacle(self):
        older = self.committed_with_older_archive()
        bad = os.path.join(os.fsencode(str(older)), b"bad-\xff-name.md")
        with open(bad, "wb") as f:
            f.write(b"untracked\n")
        listed = subprocess.run(["git", "status", "--porcelain", "-z"], cwd=self.work, capture_output=True).stdout
        self.assertIn(b"\xff", listed, "the plain status read does not list the name")
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        self.assertNotIn("bad-", raw)
        self.assertEqual(doc["carried_edits"], [])

    @unittest.skipIf(sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0), "platform: needs POSIX modes and a non-root user")
    def test_an_unreadable_directory_in_an_unrelated_archive_stops_the_plan(self):
        older = self.committed_with_older_archive()
        scratch = older / "scratch"
        scratch.mkdir()
        (scratch / "x.txt").write_text("x\n", encoding="utf-8")
        scratch.chmod(0)
        self.addCleanup(scratch.chmod, 0o700)
        out = fx.run_plan(self.work, "add-x")
        self.assertStops(out, "vcs_error", "git status")
        self.assertIn("scratch", out[1]["message"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: macOS and Windows file systems refuse a name with invalid UTF-8 bytes")
    def test_a_dirty_path_that_is_not_utf8_on_resume_stops_with_not_utf8(self):
        self.resume_on_main()
        bad = os.path.join(os.fsencode(str(self.work)), b"bad-\xff-name.md")
        with open(bad, "wb") as f:
            f.write(b"untracked\n")
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 1, raw)
        self.assertEqual(doc["error"], "not_utf8", raw)
        self.assertNotIn("steps", doc, raw)

    def test_untracked_files_hidden_by_configuration_are_listed(self):
        self.resume_on_main()
        self.git("config", "status.showUntrackedFiles", "no")
        fx.write(self.work, "new/notes.md", "x\n")
        self.assertEqual(self.git("status", "--porcelain"), "", "the fixture's configuration does not hide the file")
        doc = self.dirty_doc()
        self.assertEqual(doc["files"], ["new/notes.md"])

    # ---- The dirty_tree message names each record plainly -----------------------------------------------------
    def test_dirty_stops_keep_their_messages(self):
        # a committed archive's file missing from the working tree
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.rmtree(self.work / ad("add-x"))
        out = fx.run_plan(self.work, "add-x")
        self.assertStops(out, "dirty_tree")
        self.assertEqual(out[1]["message"], f"Deleted in the working tree: {ad('add-x')}. Restore them with "
                                            f"`git restore -- {ad('add-x')}` (or commit the deletion), then plan again.")
        self.assertEqual(out[1]["files"], [ad("add-x")])

    def test_ordinary_names_read_as_before(self):
        self.resume_on_main()
        fx.edit(self.work, "README.md", "demo", "demo edited")
        fx.write(self.work, "new.txt", "x\n")
        doc = self.dirty_doc()
        self.assertEqual(doc["message"], DIRTY_PREFIX + "M README.md; ?? new.txt")
        self.assertEqual(doc["files"], ["README.md", "new.txt"])

    @unittest.skipIf(sys.platform == "win32", "platform: Windows refuses a tab in a file name")
    def test_a_rename_and_a_name_with_a_tab(self):
        fx.commit(self.work, "docs: a", {"a.md": "a\n"})
        self.resume_on_main()
        self.git("mv", "a.md", "b.md")
        fx.write(self.work, "x\ty.md", "x\n")
        doc = self.dirty_doc()
        self.assertIn("R a.md -> b.md", doc["message"])
        self.assertIn("?? x\\ty.md", doc["message"])
        self.assertNotIn("\t", doc["message"])
        self.assertEqual(sorted(doc["files"]), ["a.md", "b.md", "x\ty.md"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: only Linux file systems take a carriage return and a trailing space in a name")
    def test_a_carriage_return_and_a_trailing_space_in_a_name(self):
        self.resume_on_main()
        name = "x\ry.md "
        with open(os.path.join(os.fsencode(str(self.work)), os.fsencode(name)), "wb") as f:
            f.write(b"x\n")
        doc = self.dirty_doc()
        self.assertTrue(doc["message"].endswith("?? x\\ry.md "), repr(doc["message"]))
        self.assertEqual(doc["files"], [name])

    # ---- A usage error from the planner's state read exits 2; any other stop exits 1 --------------------------
    def test_malformed_settings_state_read_exits_1(self):
        """The state read rejects a malformed settings file with `bad_setting` (loadSettings, exit 2 in the settings
        module); the planner prints its own stop document and exits 1, as every stop but `usage` does."""
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.write(self.work, f"{P}/specwright.yaml", "vcs: [unclosed\n")
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 1, raw)
        self.assertIs(doc["ok"], False, raw)
        self.assertEqual(doc["error"], "bad_setting", raw)
        self.assertIn("specwright.yaml", doc["message"], raw)
        self.assertNotIn("steps", doc, raw)

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
        r = fx.run_steps(self.scripts, doc["steps"])
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
        r = fx.run_steps(self.scripts, doc["steps"])
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
        r = fx.run_steps(self.scripts, doc["steps"])
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
        self.assertTrue(doc["steps"] and doc["after_rerun_steps"])
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
        out = self.run_all(typ=None, rerun=False)
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
        out = self.run_all(rerun=False)
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
        self.assertEqual(doc["after_rerun_steps"], [])
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
        out = self.run_all(rerun=False)
        doc = self.ok(out)
        self.assertEqual(doc["amended"], [])
        self.assertEqual(doc["carried_edits"], [])
        self.assertNotIn("merge-back", fx.flat(doc["after_rerun_steps"]))
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

    def dated_pair(self, commit_it, marker=False):
        self.on_branch()
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "X thing"})
        fx.make_change(self.work, "2026-01-01-hotfix", "APPROVE", {"b": "Hot thing"})
        fx.archive(self.work, ["add-x", "2026-01-01-hotfix"], commit_it=commit_it, marker=marker)
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
        self.assert_dated_restored(self.run_all(rerun=False))

    def test_bulk_member_with_dated_name_uncommitted(self):
        self.dated_pair(commit_it=False)
        self.assert_dated_restored(self.run_all(rerun=False))

    def test_bulk_member_with_dated_name_and_marker(self):
        # PR #108 round 3, Kody: the fixture writes the marker into the dated member's own archive directory.
        self.dated_pair(commit_it=False, marker=True)
        self.assertEqual(sorted(p.name for p in (self.work / P / "changes" / "archive").iterdir()),
                         ["2026-01-01-hotfix", f"{fx.DATE}-add-x"])
        self.assert_dated_restored(self.run_all(rerun=False))

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

    # ---- PR #108 review round 3 ------------------------------------------------------------------------------
    def test_stray_file_in_archive_root_is_no_member(self):
        # Kody: a plain file the archive commit added directly under changes/archive/ is not an archive directory.
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x")
        fx.write(self.work, f"{P}/changes/archive/.DS_Store", "junk\n")
        self.git("add", "-A", "--", P)
        self.git("commit", "-q", "-m", "chore(add-x): archive change")
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual([m["name"] for m in doc["members"]], ["add-x"])
        self.assertTrue((self.work / cd("add-x") / "review.md").is_file())
        self.assertTrue((self.work / P / "changes" / "archive" / ".DS_Store").is_file())

    def test_bulk_member_deleted_later_refused(self):
        # Codex P2: undoing the rest would restore every synced spec and drop the deleted member's requirements.
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        self.git("rm", "-r", "-q", ad("add-y"))
        fx.git(self.work, "commit", "-q", "-m", "chore: drop add-y's archive")
        before = fx.state(self.work)
        self.assertStops(fx.run_plan(self.work, "add-x"), "member_missing", ad("add-y"))
        self.assertEqual(fx.state(self.work), before)

    # ---- PR #108 review round 4 ------------------------------------------------------------------------------
    def assert_rerun_archive_only(self, out):
        doc = self.ok(out)
        self.assertTrue(doc["after_rerun_steps"], doc["warnings"])
        self.assertNotIn("merge-back", fx.flat(doc["after_rerun_steps"]))
        self.assertIn("openspec archive add-y --yes", fx.flat(doc["after_rerun_steps"]))
        self.assertNotIn("add-x", fx.flat(doc["after_rerun_steps"]))
        self.assertEqual(out.after.returncode, 0, out.after.stdout + out.after.stderr)
        self.assertTrue((self.work / cd("add-x") / "review.md").is_file())
        self.assertTrue((self.work / ad("add-y") / "review.md").is_file())
        self.assertIn("Y thing", fx.read(self.work, SPEC_A))
        self.assertNotIn("X thing", fx.read(self.work, SPEC_A))

    def test_bulk_undo_without_amendments_reruns_archive(self):
        # Codex P2: with no later amendment, a bulk undo still needs the script that archives the other members again.
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        self.assert_rerun_archive_only(self.run_all())

    def test_uncommitted_bulk_undo_reruns_archive(self):
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"])
        self.assert_rerun_archive_only(self.run_all())

    # ---- PR #108 review round 5 ------------------------------------------------------------------------------
    def test_bulk_undo_named_member_rerun(self):
        # Codex P2: finish run for add-y (not deferred) undoes the bulk archive for add-x; add-y must be archived again.
        for commit_it in (True, False):
            with self.subTest(committed=commit_it):
                self.setUp()
                self.pair()
                fx.archive(self.work, ["add-x", "add-y"], commit_it=commit_it)
                self.assert_rerun_archive_only(self.run_all("add-y", archived=f"{fx.DATE}-add-y"))

    # ---- user-verified-tasks pre-ship F1: a member waiting on the user is never archived again ---------------
    def test_bulk_rerun_skips_member_waiting_on_user(self):
        for commit_it in (True, False):
            with self.subTest(committed=commit_it):
                self.setUp()
                self.on_branch()
                fx.make_change(self.work, "add-x", "APPROVE", {"a": "X thing"}, commit_it=False)
                fx.commit(self.work, "docs(add-x): add planning artifacts",
                          {f"{P}/changes/add-x/tasks.md": "# Tasks\n\n- [x] 1.1 do it\n- [ ] 1.2 [user] Play the level\n"})
                fx.make_change(self.work, "add-y", "APPROVE", {"a": "Y thing"}, commit_it=False)
                fx.commit(self.work, "docs(add-y): add planning artifacts",
                          {f"{P}/changes/add-y/tasks.md": "# Tasks\n\n- [x] 1.1 do it\n- [x] 1.2 [user] Play the level\n"})
                fx.archive(self.work, ["add-x", "add-y"], commit_it=commit_it)
                code, doc, raw = fx.run_plan(self.work, "add-x")
                self.assertEqual(code, 0, raw)
                self.assertEqual({m["name"]: m["waiting_on_user"] for m in doc["members"]},
                                 {"add-x": ["1.2"], "add-y": []}, raw)
                self.assertIn("openspec archive add-y --yes", fx.flat(doc["after_rerun_steps"]))
                self.assertNotIn("openspec archive add-x", fx.flat(doc["after_rerun_steps"]))

    def test_committed_bulk_rerun_reads_working_tree_untick(self):
        # PR #187: the undo carries the working-tree tasks.md back, so an uncommitted untick decides the rerun
        self.on_branch()
        for name in ("add-x", "add-y"):
            fx.make_change(self.work, name, "APPROVE", {"a": name}, commit_it=False)
            fx.commit(self.work, f"docs({name}): add planning artifacts",
                      {f"{P}/changes/{name}/tasks.md": "# Tasks\n\n- [x] 1.1 do it\n- [x] 1.2 [user] Play the level\n"})
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        fx.write(self.work, f"{ad('add-x')}/tasks.md", "# Tasks\n\n- [x] 1.1 do it\n- [ ] 1.2 [user] Play the level\n")
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        self.assertEqual({m["name"]: m["waiting_on_user"] for m in doc["members"]},
                         {"add-x": ["1.2"], "add-y": []}, raw)
        self.assertIn("openspec archive add-y --yes", fx.flat(doc["after_rerun_steps"]))
        self.assertNotIn("openspec archive add-x", fx.flat(doc["after_rerun_steps"]))

    # ---- fix-m4-gaps D8: the after-rerun script deletes again what the user deleted -------------------------
    def retire_a(self):
        self.git("rm", "-q", SPEC_A)
        fx.git(self.work, "commit", "-q", "-m", "docs: retire capability a")

    def test_bulk_rerun_deletes_later_deleted_spec_again(self):
        self.pair()  # both members sync specs/a/spec.md
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        self.retire_a()
        out = self.run_all()
        doc = self.ok(out)
        self.assertEqual(out.after.returncode, 0, out.after.stdout + out.after.stderr)
        self.assertFalse((self.work / SPEC_A).exists())
        self.assertTrue((self.work / ad("add-y") / "review.md").is_file())
        self.assertTrue(any(SPEC_A in w and "after_rerun" in w and "again" in w for w in doc["warnings"]), doc["warnings"])
        self.assertTrue(all("deletes it again" in w for w in doc["warnings"] if SPEC_A in w), doc["warnings"])

    def test_after_rerun_stops_when_deleted_spec_recreated(self):
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        self.retire_a()
        out = self.run_all(rerun=False)
        self.ok(out)
        fx.write(self.work, SPEC_A, MINE)
        r = fx.run_steps(self.scripts, out.plan[1]["after_rerun_steps"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(SPEC_A, r.stderr)
        self.assertFalse((self.work / ad("add-y")).exists(), "an archive ran before the guard")
        self.assertEqual(fx.read(self.work, SPEC_A), MINE)

    def test_deleted_spec_only_in_deferred_member_left_deleted(self):
        self.pair({"a": "X thing", "b": "B thing"}, {"a": "Y thing"})
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        self.git("rm", "-q", SPEC_B)
        fx.git(self.work, "commit", "-q", "-m", "docs: retire capability b")
        out = self.run_all()
        doc = self.ok(out)
        self.assertNotIn(SPEC_B, fx.flat(doc["after_rerun_steps"]))
        self.assertTrue(any(SPEC_B in w and "leaves it deleted" in w for w in doc["warnings"]), doc["warnings"])
        self.assertEqual(out.after.returncode, 0, out.after.stdout + out.after.stderr)
        self.assertFalse((self.work / SPEC_B).exists())

    def test_usage_errors_exit_2(self):
        for args in (["undo-archive-plan"], ["undo-archive-plan", "--change", "x"], ["nope"], ["undo-archive-plan", "--bogus", "1"]):
            code, doc, raw = fx.run_finish(self.work, *args)
            self.assertEqual(code, 2, raw)
            self.assertIs(doc["ok"], False, raw)


    # ---- The version stamp and a work-tree file that is not a regular file (ADR 0043, C36, C38) -------------------
    def track_stamp(self, version=None):
        """Track the (excluded) VERSION on main with `version`, default the tree's own."""
        stamp = self.work / STAMP
        if version is not None:
            stamp.write_text(version + "\n", encoding="utf-8")
        self.git("add", "-f", STAMP)
        self.git("commit", "-q", "-m", "chore: track the stamp")

    def test_archive_branch_with_another_committed_version_is_sw_mismatch(self):
        """A resume from main whose committed VERSION matches, with the archive branch committing another: sw_mismatch
        naming the branch's value, no steps, and HEAD, index and work tree as they were."""
        self.track_stamp()
        self.single({"a": "New thing"})
        fx.write(self.work, STAMP, "0.0.1\n")
        fx.archive(self.work, "add-x", commit_it=True)
        self.git("checkout", "-q", "main")
        before = fx.state(self.work)
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 1, raw)
        self.assertEqual(doc["error"], "sw_mismatch", raw)
        self.assertIn("0.0.1", doc["message"])
        self.assertNotIn("steps", doc)
        self.assertEqual(fx.state(self.work), before)

    @unittest.skipIf(sys.platform == "win32", "platform: a FIFO needs POSIX")
    def test_decision_file_that_is_a_fifo_is_vcs_error_without_blocking(self):
        """On the checked-out archive branch a committed tasks.md that links to an ignored FIFO with no writer: exit 1,
        vcs_error naming tasks.md, no steps, within the bound."""
        self.on_branch()
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing"}, commit_it=False)
        fifo = self.work / "pipe"
        os.mkfifo(fifo)
        exclude = self.work / ".git" / "info" / "exclude"
        exclude.write_text(exclude.read_text(encoding="utf-8") + "pipe\n", encoding="utf-8")
        tasks = self.work / cd("add-x") / "tasks.md"
        tasks.unlink()
        os.symlink(fifo, tasks)
        fx.commit(self.work, "docs(add-x): planning with a linked task list")
        fx.archive(self.work, "add-x", commit_it=True)
        import json
        import swcall
        done = swcall.run(["finish", *fx.plan_args("add-x")], cwd=self.work, timeout=60,
                          env=dict(os.environ, SPECWRIGHT_HOME=str(sw_home())))
        code, doc, raw = done.returncode, json.loads(done.stdout), done.stdout + done.stderr
        self.assertEqual(code, 1, raw)
        self.assertEqual(doc["error"], "vcs_error", raw)
        self.assertIn("tasks.md", doc["message"])
        self.assertNotIn("steps", doc)


class TestGitGuards(Base):
    """The Git-side guards of the plan (change fix-sw-port-gaps, group 10)."""

    def refused(self, error, *needles, **kw):
        self.assertStops(fx.run_plan(self.work, "add-x", **kw), error, *needles)

    def committed(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)

    def test_a_true_pathspec_mode_variable_is_refused(self):
        self.committed()
        for name in ("GIT_GLOB_PATHSPECS", "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS"):
            self.assertStops(fx.run_plan(self.work, "add-x", env={name: "1"}), "git_env", name)

    def test_a_namespace_or_alternate_objects_is_refused(self):
        self.committed()
        for name in ("GIT_NAMESPACE", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
            self.assertStops(fx.run_plan(self.work, "add-x", env={name: "x"}), "git_env", name)

    def test_an_index_routed_elsewhere_is_refused(self):
        self.committed()
        other = self.work / ".git" / "other-index"
        shutil.copyfile(self.work / ".git" / "index", other)
        self.assertStops(fx.run_plan(self.work, "add-x", env={"GIT_INDEX_FILE": str(other)}), "git_env", "index")

    def test_grafts_partial_clone_and_sparse_checkout_are_refused(self):
        self.committed()
        (self.work / ".git" / "info").mkdir(exist_ok=True)
        grafts = self.work / ".git" / "info" / "grafts"
        grafts.write_text("\n", encoding="utf-8")
        self.refused("git_env", "grafts")
        grafts.unlink()
        self.git("config", "remote.origin.promisor", "true")
        self.refused("git_env", "partial clone")
        self.git("config", "--unset", "remote.origin.promisor")
        self.git("config", "core.sparseCheckout", "true")
        self.refused("git_env", "sparse checkout")

    def test_a_gitbutler_directory_is_refused(self):
        self.committed()
        (self.work / ".git" / "gitbutler").mkdir()
        self.refused("gitbutler_workspace")

    def test_an_operation_in_progress_is_refused(self):
        self.committed()
        (self.work / ".git" / "MERGE_HEAD").write_text(self.git("rev-parse", "HEAD") + "\n", encoding="utf-8")
        self.refused("operation_in_progress")

    def test_a_staged_gitlink_hidden_by_configuration_is_staged_changes(self):
        """An update of a gitlink HEAD already has: `diff.ignoreSubmodules=all` hides it from `git diff --cached`, so the
        old staged read saw a clean index. A newly added gitlink would show anyway and prove nothing."""
        self.git("update-index", "--add", "--cacheinfo", f"160000,{self.git('rev-parse', 'HEAD')},sub")
        self.git("commit", "-q", "-m", "chore: add a gitlink")
        (self.work / "sub").mkdir()  # an uninitialized submodule: without its directory `git add -A` stages a deletion
        self.committed()
        self.git("config", "diff.ignoreSubmodules", "all")
        self.git("update-index", "--cacheinfo", f"160000,{self.git('rev-parse', 'HEAD')},sub")
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "", "the configuration does not hide the update")
        self.refused("staged_changes")

    def test_a_resume_refuses_an_assume_unchanged_file_anywhere(self):
        self.committed()
        self.git("checkout", "-q", "main")
        self.git("update-index", "--assume-unchanged", "src/app.py")
        fx.edit(self.work, "src/app.py", "v1", "hidden edit")
        self.refused("git_env", "src/app.py", branch=BRANCH)

    def test_the_tip_lookup_is_exact(self):
        self.committed()
        self.git("checkout", "-q", "main")
        self.git("tag", f"refs/heads/{BRANCH}", BRANCH)
        self.git("tag", BRANCH, BRANCH)
        self.git("branch", "-D", BRANCH)
        self.refused("no_archive", branch=BRANCH)

    def test_a_member_replaced_by_a_file_is_a_vcs_error(self):
        self.pair()
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        member = ad("add-y")
        self.git("rm", "-r", "-q", member)
        (self.work / member).write_text("now a file\n", encoding="utf-8")
        fx.commit(self.work, "chore: replace a member with a file")
        self.refused("vcs_error", member)

    def test_ignored_content_under_the_archive_root_is_refused(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x")
        exclude = self.work / ".git" / "info" / "exclude"
        exclude.write_text(exclude.read_text(encoding="utf-8") + "*-add-y/\n", encoding="utf-8")
        fx.write(self.work, f"{ad('add-y')}/proposal.md", "never committed\n")
        self.refused("git_env", ad("add-y"))

    @unittest.skipIf(os.name == "nt", "platform: no POSIX permission bits")
    def test_an_unlistable_delta_directory_is_a_vcs_error(self):
        self.single({"a": "New thing"})
        fx.archive(self.work, "add-x")
        specs = self.work / ad("add-x") / "specs"
        specs.chmod(0)
        self.addCleanup(specs.chmod, 0o755)
        if os.geteuid() == 0:
            self.skipTest("platform: root reads every directory")
        self.refused("vcs_error")

    def test_the_plan_warns_about_the_index_and_prints_no_recovery_command(self):
        self.committed()
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        warnings = doc["warnings"]
        self.assertIn("Do not edit files or start a merge, cherry-pick, revert or rebase while the steps run.", warnings)
        self.assertIn("The index must not be changed by other commands or hooks while the steps run.", warnings)
        recovery = next(w for w in warnings if w.startswith("If a step fails after the steps began"))
        self.assertIn(doc["backup_dir"], recovery)
        self.assertNotIn("git restore", recovery)
        self.assertNotIn("`", recovery)


if __name__ == "__main__":
    unittest.main()
