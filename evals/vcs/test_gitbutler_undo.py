"""sw finish undo-archive-plan on a GitButler repo (real `but`): the printed steps move the archive back, write the main
specs with `undo-step write-blob`, and commit exactly the touched paths through `sw vcs commit --branch <branch>`; they run no Git write.

`feat/b` stays applied beside the change branch, with a commit and an uncommitted edit of its own, throughout.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from butenv import Scratch, require_but
from test_gitbutler_flows import BRANCH, CHANGE, GitButlerFlowCase
from vcs_test_support import native_path, stamp_version, sw_home

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("finish_fixtures", ROOT / "evals" / "finish" / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

P = "openspec"
ARCHIVED = "%s-%s" % (fx.DATE, CHANGE)
ARCHIVE_DIR = "%s/changes/archive/%s" % (P, ARCHIVED)
CHANGE_DIR = "%s/changes/%s" % (P, CHANGE)
SUBJECT = "feat(add-c): undo archive of add-c"
GIT_WRITES = ("git restore", "git checkout", "git add", "git commit", "git rm", "git read-tree", "git stash", "git reset")


class TestGitButlerUndoPlan(GitButlerFlowCase):
    def commit_paths(self, scratch, wrap, subject, *paths):
        result = self.commit(scratch, wrap, subject + "\n", *paths)
        self.assertTrue(result["ok"], result)
        return result["commit"]

    def names(self, repo, rev):
        out = self.git(repo.path, "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", rev).stdout
        return sorted(line for line in out.splitlines() if line)

    def plan(self, scratch, wrap, repo):
        return self.script(scratch, wrap, "finish", "undo-archive-plan",
                           "--change", CHANGE, "--archived-name", ARCHIVED, "--prefix", P, "--main", "main", "--branch", BRANCH,
                           cwd=repo.path)

    def run_script(self, scratch, wrap, repo, steps, name="undo", expected=0):
        """The printed steps one by one in their own cwd, with the fixture's PATH so they find git and but; stops at the
        first failure. Returns the last step's result with `.ran` (the steps started) and the output of all of them."""
        env = self.fenced_env(scratch, wrap)
        env.update({"SPECWRIGHT_STATE_DIR": str(self.root / "state"), "PYTHONIOENCODING": "utf-8",
                    "SPECWRIGHT_HOME": str(sw_home())})
        stamp_version(repo.path)
        env["PATH"] = native_path(env["PATH"])
        done = SimpleNamespace(returncode=0, stdout="", stderr="", ran=[])
        for step in steps:
            r = subprocess.run(step["argv"], cwd=step["cwd"], env=env, capture_output=True, text=True, encoding="utf-8")
            done.returncode, done.stdout, done.stderr = r.returncode, done.stdout + r.stdout, done.stderr + r.stderr
            done.ran.append(step)
            if r.returncode != 0:
                break
        self.assertEqual(done.returncode != 0, expected != 0, done.stdout + done.stderr)
        return done

    def test_a_failed_carried_edits_read_stops_the_plan(self):
        """The planner's path-limited `git status` failing (C50): `vcs_error`, no steps, never an empty list of edits."""
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            repo.but("branch", "new", BRANCH)
            work = repo.path
            fx.write(work, "%s/specs/a/spec.md" % P, fx.base_spec("a"))
            fx.make_change(work, CHANGE, "DEFERRED", {"a": "New thing"}, commit_it=False)
            self.commit_paths(scratch, wrap, "docs(add-c): add planning artifacts", "%s/specs/a/spec.md" % P, CHANGE_DIR + "/")
            fx.archive(work, CHANGE, commit_it=False)
            self.commit_paths(scratch, wrap, "chore(add-c): archive change", ARCHIVE_DIR + "/", CHANGE_DIR + "/",
                              "%s/specs/a/spec.md" % P)
            Path(str(self.shim.log_path) + ".fail-scoped-status").write_text("fail\n", encoding="utf-8")  # see gitlog.install
            doc = self.script(scratch, wrap, "finish", "undo-archive-plan", "--change", CHANGE, "--archived-name", ARCHIVED,
                              "--prefix", P, "--main", "main", "--branch", BRANCH, cwd=repo.path, expected=1)
            self.assertFalse(doc["ok"], doc)
            self.assertEqual(doc["error"], "vcs_error", doc)
            self.assertNotIn("steps", doc)
            self.assertIn("git status", doc["message"])

    def test_undo_plan_uses_but_commit(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            self.other_agent(repo, wrap)
            repo.but("branch", "new", BRANCH)
            work = repo.path
            fx.write(work, "%s/specs/a/spec.md" % P, fx.base_spec("a"))
            fx.make_change(work, CHANGE, "DEFERRED", {"a": "New thing", "b": "B thing"}, commit_it=False)
            planning = self.commit_paths(scratch, wrap, "docs(add-c): add planning artifacts", "%s/specs/a/spec.md" % P,
                                         CHANGE_DIR + "/")
            fx.archive(work, CHANGE, commit_it=False)
            archive = self.commit_paths(scratch, wrap, "chore(add-c): archive change", ARCHIVE_DIR + "/", CHANGE_DIR + "/",
                                        "%s/specs/a/spec.md" % P, "%s/specs/b/spec.md" % P)
            self.assertEqual(self.git(work, "rev-parse", archive + "^").stdout.strip(), planning)
            tips = {name: self.tip(repo, name) for name in ("feat/b", "main")}
            side_edit = (work / "src" / "b.py").read_text(encoding="utf-8")

            doc = self.plan(scratch, wrap, repo)

            self.assertTrue(doc["ok"], doc)
            self.assertEqual((doc["mode"], doc["archive_commit"], doc["branch"]), ("committed", archive, BRANCH))
            self.assertNotIn("script", doc)
            steps = doc["steps"]
            script = fx.flat(steps)
            for forbidden in GIT_WRITES:
                self.assertNotIn(forbidden, script)
            self.assertNotIn("git branch --show-current", script, "HEAD is the workspace commit: the branch is not read from it")
            self.assertRegex(script, r"vcs commit .*--branch feat/add-c")
            self.assertIn("finish undo-step write-blob", script)
            for path in (ARCHIVE_DIR, CHANGE_DIR, "%s/specs/a/spec.md" % P, "%s/specs/b/spec.md" % P):
                self.assertIn(path, script)
            calls_before = len(wrap.calls())

            # a touched path with an uncommitted edit stops the script before anything moves
            spec_a = work / P / "specs" / "a" / "spec.md"
            clean_bytes = spec_a.read_bytes()  # bytes, so the restore leaves no line-ending change behind
            spec_a.write_bytes(clean_bytes + b"\nmy own edit\n")
            stopped = self.run_script(scratch, wrap, repo, steps, "guard", expected=1)
            self.assertTrue((work / P / "changes" / "archive" / ARCHIVED).is_dir(), "the guard let the script move the archive")
            self.assertFalse((work / P / "changes" / CHANGE).exists())
            self.assertEqual(self.tip(repo, BRANCH), archive)
            self.assertEqual([c for c in wrap.calls()[calls_before:] if c[:1] == ["commit"]], [], "the guard let a but commit run")
            spec_a.write_bytes(clean_bytes)
            self.assertEqual(self.uncommitted(repo), ["src/b.py"], "only feat/b's edit is uncommitted")

            done = self.run_script(scratch, wrap, repo, steps)

            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            new = self.tip(repo, BRANCH)
            self.assertNotEqual(new, archive)
            self.assertEqual(self.git(work, "rev-parse", new + "^").stdout.strip(), archive)
            self.assertEqual(self.git(work, "log", "-1", "--format=%s", new).stdout.strip(), SUBJECT)
            touched = self.names(repo, new)
            self.assertTrue(touched, "the undo commit is empty")
            for path in touched:
                self.assertTrue(path.startswith((ARCHIVE_DIR + "/", CHANGE_DIR + "/", P + "/specs/")), path)
            self.assertIn("%s/specs/a/spec.md" % P, touched)
            self.assertIn("%s/specs/b/spec.md" % P, touched)
            self.assertIn("%s/review.md" % CHANGE_DIR, touched)
            but_commits = [c for c in wrap.calls()[calls_before:] if c[:1] == ["commit"]]
            self.assertEqual(len(but_commits), 1, but_commits)
            self.assertEqual(but_commits[0][1:3], ["-b", BRANCH])
            # the files are back as the pre-archive commit had them
            self.assertTrue((work / P / "changes" / CHANGE / "review.md").is_file())
            self.assertFalse((work / P / "changes" / "archive" / ARCHIVED).exists())
            self.assertNotIn("New thing", spec_a.read_text(encoding="utf-8"))
            self.assertFalse((work / P / "specs" / "b" / "spec.md").exists())
            self.assertEqual(self.git(work, "show", planning + ":%s/specs/a/spec.md" % P).stdout, spec_a.read_text(encoding="utf-8"))
            # the other agent's branch and edit, and main, are untouched
            self.assertEqual(self.tip(repo, "feat/b"), tips["feat/b"])
            self.assertEqual(self.tip(repo, "main"), tips["main"])
            self.assertEqual((work / "src" / "b.py").read_text(encoding="utf-8"), side_edit)
            self.assertEqual(self.uncommitted(repo), ["src/b.py"])
            self.assertEqual(self.applied(repo), [BRANCH, "feat/b"])
            self.assert_only_allowed_git_writes([])
            self.assertEqual(self.git_writes(), [], "the undo ran a Git write")

    def test_undo_stops_when_another_branch_changed_a_spec(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            work = repo.path
            # spec a is on main, so another branch can commit its own edit of it
            side = self.clone_of_origin(scratch)
            fx.write(side, "%s/specs/a/spec.md" % P, fx.base_spec("a"))
            self.side_git(side, "add", "%s/specs/a/spec.md" % P)
            self.side_git(side, "commit", "-q", "-m", "docs: spec a")
            self.side_git(side, "push", "-q", "origin", "HEAD:refs/heads/main")
            repo.but("pull")
            repo.but("branch", "new", "feat/b")
            repo.but("branch", "new", BRANCH)
            fx.make_change(work, CHANGE, "DEFERRED", {"a": "New thing", "b": "B thing"}, commit_it=False)
            self.commit_paths(scratch, wrap, "docs(add-c): add planning artifacts", CHANGE_DIR + "/")
            fx.archive(work, CHANGE, commit_it=False)
            archive = self.commit_paths(scratch, wrap, "chore(add-c): archive change", ARCHIVE_DIR + "/", CHANGE_DIR + "/",
                                        "%s/specs/a/spec.md" % P, "%s/specs/b/spec.md" % P)
            # feat/b then commits its own edit of spec a's title line
            spec_a = work / P / "specs" / "a" / "spec.md"
            text = spec_a.read_text(encoding="utf-8")
            spec_a.write_text(text.replace("# a Specification", "# a Specification (feat/b)", 1), encoding="utf-8")
            repo.but("commit", "-b", "feat/b", "-m", "docs: retitle spec a", "--json", "%s/specs/a/spec.md" % P)
            self.assertIn("(feat/b)", self.git(work, "show", "refs/heads/feat/b:%s/specs/a/spec.md" % P).stdout)
            self.assertEqual(self.tip(repo, BRANCH), archive)
            before = spec_a.read_bytes()

            doc = self.plan(scratch, wrap, repo)

            self.assertTrue(doc["ok"], doc)
            calls_before = len(wrap.calls())
            stopped = self.run_script(scratch, wrap, repo, doc["steps"], "guard", expected=1)
            self.assertIn("another applied branch", stopped.stderr)
            self.assertEqual(spec_a.read_bytes(), before, "the undo restored feat/b's committed edit away")
            self.assertTrue((work / P / "changes" / "archive" / ARCHIVED).is_dir(), "the guard let the script move the archive")
            self.assertEqual(self.tip(repo, BRANCH), archive)
            self.assertEqual([c for c in wrap.calls()[calls_before:] if c[:1] == ["commit"]], [], "the guard let a but commit run")

    # ---- group 13: the planner and its steps on GitButler (D2, C30, C46) ----------------------------------------------
    SPEC_A = "%s/specs/a/spec.md" % P
    DESIGN = ARCHIVE_DIR + "/design.md"

    def archived(self, scratch, wrap, repo, caps=None, commit=True, base=("a",)):
        """feat/add-c holds the planning commit and, with `commit`, the archive commit (returned). Without it the archive
        is moved and its deltas synced in the work tree only. `caps` are the change's delta specs; `base` the main specs
        that exist before the change."""
        caps = caps or {"a": "New thing", "b": "B thing"}
        repo.but("branch", "new", BRANCH)
        work = repo.path
        for cap in base:
            fx.write(work, "%s/specs/%s/spec.md" % (P, cap), fx.base_spec(cap))
        fx.make_change(work, CHANGE, "DEFERRED", caps, commit_it=False)
        specs = ["%s/specs/%s/spec.md" % (P, cap) for cap in base]
        self.commit_paths(scratch, wrap, "docs(add-c): add planning artifacts", *specs, CHANGE_DIR + "/")
        fx.archive(work, CHANGE, commit_it=False)
        if not commit:
            return None
        return self.commit_paths(scratch, wrap, "chore(add-c): archive change", ARCHIVE_DIR + "/", CHANGE_DIR + "/",
                                 *["%s/specs/%s/spec.md" % (P, cap) for cap in caps])

    def archived_unnamed(self, repo, cap, commit=True, base=()):
        """Like `archived`, for a capability whose path `sw vcs commit` would not name: everything is committed by `but`
        itself, so the fixture reaches the state the undo then refuses."""
        repo.but("branch", "new", BRANCH)
        work = repo.path
        for name in base:
            fx.write(work, "%s/specs/%s/spec.md" % (P, name), fx.base_spec(name))
        fx.make_change(work, CHANGE, "DEFERRED", {cap: "New thing"}, commit_it=False)
        repo.but("commit", "-b", BRANCH, "-m", "docs(add-c): add planning artifacts", "--json")
        fx.archive(work, CHANGE, commit_it=False)
        if commit:
            repo.but("commit", "-b", BRANCH, "-m", "chore(add-c): archive change", "--json")
        return self.tip(repo, BRANCH)

    def refused(self, scratch, wrap, repo, error, tip=None):
        """The plan stops with `error`, prints no steps and leaves the backup directory unmade and the branch alone."""
        doc = self.script(scratch, wrap, "finish", "undo-archive-plan", "--change", CHANGE, "--archived-name", ARCHIVED,
                          "--prefix", P, "--main", "main", "--branch", BRANCH, cwd=repo.path, expected=1)
        self.assertFalse(doc["ok"], doc)
        self.assertEqual(doc["error"], error, doc)
        self.assertNotIn("steps", doc)
        self.assertFalse((repo.path / ".git" / "specwright-undo").exists(), "a refused plan made a backup directory")
        if tip is not None:
            self.assertEqual(self.tip(repo, BRANCH), tip)
        return doc

    def side_commit(self, scratch, rel, text, subject):
        """Commit `rel` on main in another clone of the origin and bring it into the workspace."""
        side = self.clone_of_origin(scratch)
        fx.write(side, rel, text)
        self.side_git(side, "add", rel)
        self.side_git(side, "commit", "-q", "-m", subject)
        self.side_git(side, "push", "-q", "origin", "HEAD:refs/heads/main")

    def test_a_bracket_in_a_committed_undos_path(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            archive = self.archived_unnamed(repo, "a[1]")
            doc = self.refused(scratch, wrap, repo, "bad_path", archive)
            self.assertIn("openspec/specs/a[1]/spec.md", doc["message"])
            self.assertEqual(doc["path"], "openspec/specs/a[1]/spec.md")
            self.assertTrue((repo.path / ARCHIVE_DIR).is_dir(), "a refused plan moved the archive")

    def test_the_same_path_in_an_uncommitted_undo(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            self.archived_unnamed(repo, "a[1]", commit=False)
            doc = self.plan(scratch, wrap, repo)
            self.assertTrue(doc["ok"], doc)
            self.assertEqual(doc["mode"], "uncommitted")
            self.assertNotIn("vcs commit", fx.flat(doc["steps"]), "an uncommitted undo makes no backend commit")

    def test_a_gitbutler_undo_of_a_path_with_glob_characters(self):
        require_but()
        names = ["a[1]"]
        if sys.platform != "win32":
            names.append("a\\b")  # a backslash is a name character on Linux and macOS, a separator `but` would respell
        for cap in names:
            with self.subTest(cap=cap), Scratch() as scratch:
                wrap, repo = self.start(scratch)
                archive = self.archived_unnamed(repo, cap)
                doc = self.refused(scratch, wrap, repo, "bad_path", archive)
                self.assertEqual(doc["path"], "openspec/specs/%s/spec.md" % cap)
                self.assertTrue((repo.path / ARCHIVE_DIR).is_dir(), "nothing may be moved or committed")

    def test_a_failed_target_read_during_a_gitbutler_undo(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            archive = self.archived(scratch, wrap, repo)
            # git exits 128 for `config --get gitbutler.project.targetRef`: an error, not the unset setting (exit 1)
            Path(str(self.shim.log_path) + ".fail-target-read").write_text("fail\n", encoding="utf-8")  # see gitlog.install
            doc = self.refused(scratch, wrap, repo, "vcs_error", archive)
            self.assertIn("gitbutler.project.targetRef", doc["message"])

    def test_a_failed_target_read_with_gitbutler_selected(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            archive = self.archived(scratch, wrap, repo)
            marker = Path(str(self.shim.log_path) + ".fail-target-read")
            marker.write_text("fail\n", encoding="utf-8")
            self.refused(scratch, wrap, repo, "vcs_error", archive)
            marker.unlink()
            # an unset target still stops with not_managed
            self.git(repo.path, "config", "--unset", "gitbutler.project.targetRef")
            self.refused(scratch, wrap, repo, "not_managed", archive)

    def test_an_unset_target_during_a_gitbutler_undo(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            archive = self.archived(scratch, wrap, repo)
            self.git(repo.path, "config", "--unset", "gitbutler.project.targetRef")
            self.refused(scratch, wrap, repo, "not_managed", archive)
            # a successful read of a blank value is unset too
            self.git(repo.path, "config", "gitbutler.project.targetRef", "")
            self.refused(scratch, wrap, repo, "not_managed", archive)

    def test_a_carriededits_read_fails_on_gitbutler(self):
        self.test_a_failed_carried_edits_read_stops_the_plan()

    def test_a_dirty_submodule_under_a_gitbutler_undo(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            work = repo.path
            src = self.root / "subsrc"
            src.mkdir()
            for args in (("init", "-q", "-b", "main"), ("config", "user.name", "T"), ("config", "user.email", "t@example.com"),
                         ("config", "commit.gpgsign", "false")):
                fx.git(src, *args)
            (src / "f.txt").write_text("one\n", encoding="utf-8")
            fx.git(src, "add", "-A")
            fx.git(src, "commit", "-q", "-m", "sub")
            repo.but("branch", "new", BRANCH)
            fx.write(work, self.SPEC_A, fx.base_spec("a"))
            fx.make_change(work, CHANGE, "DEFERRED", {"a": "New thing"}, commit_it=False)
            self.commit_paths(scratch, wrap, "docs(add-c): add planning artifacts", self.SPEC_A, CHANGE_DIR + "/")
            fx.archive(work, CHANGE, commit_it=False)
            archive = self.commit_paths(scratch, wrap, "chore(add-c): archive change", ARCHIVE_DIR + "/", CHANGE_DIR + "/",
                                        self.SPEC_A)
            doc = self.plan(scratch, wrap, repo)
            self.assertTrue(doc["ok"], doc)
            self.assertTrue(doc["steps"], doc)
            # A submodule that is already inside the archived member is refused at planning (`unsupported_entry`, a
            # nested repository), so the one that reaches `check clean` is added under the member after the plan, with
            # `ignore = all`, which hides it from a plain status; the step must still see it
            fx.git(work, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(src), ARCHIVE_DIR + "/sub")
            fx.git(work, "config", "submodule.%s/sub.ignore" % ARCHIVE_DIR, "all")
            (work / ARCHIVE_DIR / "sub" / "f.txt").write_text("changed" + chr(10), encoding="utf-8")
            staged = self.git(work, "ls-files", "-s", "--", ARCHIVE_DIR + "/sub").stdout
            self.assertTrue(staged.startswith("160000 "), "the gitlink is not in place: %r" % staged)
            stopped = self.run_script(scratch, wrap, repo, doc["steps"], "submodule", expected=1)
            self.assertTrue((work / ARCHIVE_DIR).is_dir(), "the check let the script move the archive")
            self.assertFalse((work / CHANGE_DIR).exists())
            self.assertEqual(self.tip(repo, BRANCH), archive)
            self.assertNotIn("undo-step move", fx.flat(stopped.ran))

    def test_another_applied_branchs_edit_with_a_diff_helper_that_exits_0(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            work = repo.path
            self.side_commit(scratch, self.SPEC_A, fx.base_spec("a"), "docs: spec a")
            spec = fx.base_spec("a").replace("# a Specification", "# a Specification (feat/b)", 1)
            archive = self.two_branches(scratch, wrap, repo, (self.SPEC_A, spec))
            # an external diff helper that always reports "no difference" must not decide the guard
            self.git(work, "config", "diff.external", "true")
            before = (work / self.SPEC_A).read_bytes()
            doc = self.plan(scratch, wrap, repo)
            stopped = self.run_script(scratch, wrap, repo, doc["steps"], "helper", expected=1)
            self.assertIn("another applied branch", stopped.stderr)
            self.assertEqual((work / self.SPEC_A).read_bytes(), before)
            self.assertTrue((work / ARCHIVE_DIR).is_dir(), "the guard let the script move the archive")
            self.assertFalse(Path(doc["backup_dir"]).exists(), "a backup was made before the guard refused")
            self.assertEqual(self.tip(repo, BRANCH), archive)

    def two_branches(self, scratch, wrap, repo, committed_edit):
        """`two_branches` for a repo whose main already holds spec a."""
        repo.but("pull")
        repo.but("branch", "new", "feat/b")
        repo.but("branch", "new", BRANCH)
        work = repo.path
        fx.make_change(work, CHANGE, "DEFERRED", {"a": "New thing", "b": "B thing"}, commit_it=False)
        self.commit_paths(scratch, wrap, "docs(add-c): add planning artifacts", CHANGE_DIR + "/")
        fx.archive(work, CHANGE, commit_it=False)
        archive = self.commit_paths(scratch, wrap, "chore(add-c): archive change", ARCHIVE_DIR + "/", CHANGE_DIR + "/",
                                    self.SPEC_A, "%s/specs/b/spec.md" % P)
        rel, text = committed_edit
        fx.write(work, rel, text)
        repo.but("commit", "-b", "feat/b", "-m", "docs: feat/b edit", "--json", rel)
        self.assertEqual(self.tip(repo, BRANCH), archive)
        return archive

    def test_another_applied_branch_edits_only_a_sibling_path(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            work = repo.path
            self.side_commit(scratch, self.SPEC_A, fx.base_spec("a"), "docs: spec a")
            archive = self.two_branches(scratch, wrap, repo, ("%s/specs/a/notes.md" % P, "feat/b notes\n"))
            doc = self.plan(scratch, wrap, repo)
            done = self.run_script(scratch, wrap, repo, doc["steps"], "sibling")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertNotEqual(self.tip(repo, BRANCH), archive, "the undo committed")
            self.assertEqual((work / P / "specs" / "a" / "notes.md").read_text(encoding="utf-8"), "feat/b notes\n")

    def test_a_gitbutler_undo_over_a_hidden_edit(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            work = repo.path
            archive = self.archived(scratch, wrap, repo)
            doc = self.plan(scratch, wrap, repo)
            self.git(work, "update-index", "--assume-unchanged", self.SPEC_A)
            spec = work / self.SPEC_A
            spec.write_bytes(spec.read_bytes() + b"\nhidden edit\n")
            hidden = spec.read_bytes()
            self.run_script(scratch, wrap, repo, doc["steps"], "hidden", expected=1)
            self.assertEqual(spec.read_bytes(), hidden)
            self.assertTrue((work / ARCHIVE_DIR).is_dir(), "the guard let the script move the archive")
            self.assertFalse(Path(doc["backup_dir"]).exists())
            self.assertEqual(self.tip(repo, BRANCH), archive)

    def test_an_untracked_case_alias_owned_by_another_gitbutler_branch(self):
        require_but()
        probe = self.root / "case-probe-A"
        probe.write_text("x", encoding="utf-8")
        if not (self.root / "case-probe-a").exists():
            self.skipTest("platform: this volume is case-sensitive")
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            self.other_agent(repo, wrap)
            work = repo.path
            alias = "%s/specs/foo/spec.md" % P
            repo.but("branch", "new", BRANCH)
            fx.write(work, alias, "# foo owned elsewhere\n")  # untracked, spelled `foo`; the delta names `Foo`
            wrap.set_assignments({"feat/b": ["src/b.py", alias]})
            fx.make_change(work, CHANGE, "DEFERRED", {"Foo": "New thing"}, commit_it=False)
            fx.archive(work, CHANGE, commit_it=False)
            before = (work / alias).read_bytes()
            doc = self.refused(scratch, wrap, repo, "path_owned_elsewhere")
            self.assertIn("foo", doc["message"])
            self.assertEqual((work / alias).read_bytes(), before)
            self.assertTrue((work / ARCHIVE_DIR).is_dir())

    def test_a_restore_destination_that_is_a_link(self):
        if sys.platform == "win32":
            self.skipTest("platform: a symlink needs a privilege on Windows")
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            work = repo.path
            archive = self.archived(scratch, wrap, repo)
            outside = self.root / "outside.md"
            outside.write_text("unrelated\n", encoding="utf-8")
            (work / self.SPEC_A).unlink()
            os.symlink(str(outside), str(work / self.SPEC_A))
            doc = self.refused(scratch, wrap, repo, "unsupported_entry", archive)
            self.assertIn(self.SPEC_A, doc["message"])
            self.assertEqual(outside.read_text(encoding="utf-8"), "unrelated\n")
            self.assertTrue((work / ARCHIVE_DIR).is_dir())

    def test_a_hard_linked_restore_destination(self):
        if sys.platform == "win32":
            self.skipTest("platform: modes and hard links need POSIX")
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            work = repo.path
            self.git(work, "config", "core.fileMode", "false")  # the executable bit alone is no edit
            planning = None
            archive = self.archived(scratch, wrap, repo)
            planning = self.git(work, "rev-parse", archive + "^").stdout.strip()
            spec = work / self.SPEC_A
            archived_bytes = spec.read_bytes()
            spec.chmod(0o755)  # executable on disk, not in the restore revision
            other = self.root / "second-link.md"
            os.link(str(spec), str(other))
            doc = self.plan(scratch, wrap, repo)
            done = self.run_script(scratch, wrap, repo, doc["steps"], "hardlink")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(spec.read_bytes(), self.git(work, "show", planning + ":" + self.SPEC_A).stdout.encode("utf-8"))
            self.assertEqual(spec.stat().st_mode & 0o111, 0, "the restore kept the executable bit")
            self.assertEqual(other.read_bytes(), archived_bytes, "the restore wrote through the second link")
            self.assertFalse((work / ARCHIVE_DIR).exists(), "the archive was not moved back")

    def test_a_rerun_spec_under_a_linked_directory(self):
        if sys.platform == "win32":
            self.skipTest("platform: a symlink needs a privilege on Windows")
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            work = repo.path
            archive = self.archived(scratch, wrap, repo, caps={"foo/bar": "New thing"}, base=("a",))
            outside = self.root / "outside-specs"
            (outside / "bar").mkdir(parents=True)
            shutil.rmtree(work / P / "specs" / "foo")
            os.symlink(str(outside), str(work / P / "specs" / "foo"))
            doc = self.refused(scratch, wrap, repo, "unsupported_entry", archive)
            self.assertIn("foo/bar/spec.md", doc["message"])
            self.assertEqual(sorted(p.name for p in (outside / "bar").iterdir()), [], "a file appeared outside the checkout")

    def test_another_gitbutler_branchs_edit_at_a_rerun_only_spec(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            self.other_agent(repo, wrap)
            work = repo.path
            repo.but("branch", "new", BRANCH)
            fx.write(work, self.SPEC_A, fx.base_spec("a"))
            fx.make_change(work, CHANGE, "DEFERRED", {"a": "New thing"}, commit_it=False)
            fx.make_change(work, "add-d", "APPROVE", {"foo": "Foo thing"}, commit_it=False)
            self.commit_paths(scratch, wrap, "docs: planning artifacts", self.SPEC_A, CHANGE_DIR + "/", "%s/changes/add-d/" % P)
            fx.archive(work, [CHANGE, "add-d"], commit_it=False)
            foo = "%s/specs/foo/spec.md" % P
            archive = self.commit_paths(scratch, wrap, "chore: archive changes", ARCHIVE_DIR + "/", CHANGE_DIR + "/",
                                        "%s/changes/archive/%s-add-d/" % (P, fx.DATE), "%s/changes/add-d/" % P, self.SPEC_A, foo)
            fx.write(work, foo, fx.read(work, foo) + "\nfeat/b is editing this\n")
            wrap.set_assignments({"feat/b": ["src/b.py", foo]})
            before = (work / foo).read_bytes()
            self.refused(scratch, wrap, repo, "path_owned_elsewhere", archive)
            self.assertEqual((work / foo).read_bytes(), before, "the other branch's edit changed")

    def test_another_gitbutler_branchs_assigned_edit_on_an_uncommitted_undo(self):
        require_but()
        for what in ("spec", "member"):
            with self.subTest(what=what), Scratch() as scratch:
                wrap, repo = self.start(scratch)
                self.other_agent(repo, wrap)
                self.archived(scratch, wrap, repo, commit=False)
                path = self.SPEC_A if what == "spec" else self.DESIGN
                if what == "member":
                    fx.write(repo.path, path, fx.read(repo.path, path) + "\nan edit\n")
                wrap.set_assignments({"feat/b": ["src/b.py", path]})
                before = (repo.path / path).read_bytes()
                doc = self.refused(scratch, wrap, repo, "path_owned_elsewhere")
                self.assertEqual(doc["path"], path)
                self.assertEqual(doc["branch"], "feat/b")
                self.assertEqual((repo.path / path).read_bytes(), before)
                self.assertTrue((repo.path / ARCHIVE_DIR).is_dir(), "a refused plan moved the archive")

    def test_another_gitbutler_branchs_assigned_edit_at_a_backslash_path(self):
        if sys.platform == "win32":
            self.skipTest("platform: a backslash is a separator on Windows")
        require_but()
        cap = "a\\b"
        path = "%s/specs/%s/spec.md" % (P, cap)
        for when in ("before", "after"):
            with self.subTest(when=when), Scratch() as scratch:
                wrap, repo = self.start(scratch)
                self.other_agent(repo, wrap)
                repo.but("branch", "new", BRANCH)
                work = repo.path
                fx.write(work, path, fx.base_spec("a"))
                fx.make_change(work, CHANGE, "DEFERRED", {cap: "New thing"}, commit_it=False)
                repo.but("commit", "-b", BRANCH, "-m", "docs(add-c): add planning artifacts", "--json", CHANGE_DIR + "/")
                fx.archive(work, CHANGE, commit_it=False)  # uncommitted: the undo restores the spec, makes no commit
                assigned = {"feat/b": ["src/b.py", path]}
                if when == "before":
                    wrap.set_assignments(assigned)
                    self.refused(scratch, wrap, repo, "path_owned_elsewhere")
                    continue
                doc = self.plan(scratch, wrap, repo)
                wrap.set_assignments(assigned)
                before = (work / path).read_bytes()
                stopped = self.run_script(scratch, wrap, repo, doc["steps"], "backslash", expected=1)
                self.assertIn(path, stopped.stdout + stopped.stderr)
                self.assertEqual((work / path).read_bytes(), before)
                self.assertTrue((work / ARCHIVE_DIR).is_dir(), "the check let the script move the archive")
                self.assertFalse(Path(doc["backup_dir"]).exists())

    def test_an_archived_member_edited_after_a_gitbutler_plan(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            archive = self.archived(scratch, wrap, repo)
            doc = self.plan(scratch, wrap, repo)
            design = repo.path / self.DESIGN
            design.write_text(design.read_text(encoding="utf-8") + "\nedited after the plan\n", encoding="utf-8")
            calls_before = len(wrap.calls())
            self.run_script(scratch, wrap, repo, doc["steps"], "member", expected=1)
            self.assertTrue(design.is_file(), "the script moved the archive")
            self.assertFalse(Path(doc["backup_dir"]).exists(), "a backup was made before the check refused")
            self.assertFalse((repo.path / CHANGE_DIR).exists())
            self.assertEqual(self.tip(repo, BRANCH), archive)
            self.assertEqual([c for c in wrap.calls()[calls_before:] if c[:1] == ["commit"]], [])

    def test_a_foreign_assignment_made_after_a_gitbutler_plan(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            self.other_agent(repo, wrap)
            self.archived(scratch, wrap, repo, commit=False)
            work = repo.path
            fx.write(work, self.DESIGN, fx.read(work, self.DESIGN) + "\nan edit made before planning\n")
            doc = self.plan(scratch, wrap, repo)  # assigned to no other branch, so the plan carries it
            self.assertIn(self.DESIGN, doc["carried_edits"])
            wrap.set_assignments({"feat/b": ["src/b.py", self.DESIGN]})  # reassigned before the steps run
            before = (work / self.DESIGN).read_bytes()
            stopped = self.run_script(scratch, wrap, repo, doc["steps"], "reassigned", expected=1)
            self.assertIn("path_owned_elsewhere", stopped.stdout)
            self.assertEqual((work / self.DESIGN).read_bytes(), before)
            self.assertTrue((work / ARCHIVE_DIR).is_dir(), "the check let the script move the archive")
            self.assertFalse(Path(doc["backup_dir"]).exists())

    def test_an_unassigned_member_edit_on_a_gitbutler_undo(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            self.other_agent(repo, wrap)
            self.archived(scratch, wrap, repo, commit=False)
            work = repo.path
            edited = fx.read(work, self.DESIGN) + "\nan unassigned edit\n"
            fx.write(work, self.DESIGN, edited)
            doc = self.plan(scratch, wrap, repo)
            done = self.run_script(scratch, wrap, repo, doc["steps"], "unassigned")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(fx.read(work, CHANGE_DIR + "/design.md"), edited, "the edit was not carried with the member")
            self.assertFalse((work / ARCHIVE_DIR).exists())
