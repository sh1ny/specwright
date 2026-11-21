"""The undo plan prints steps (change native-cli-retire-scripts, group 4): `steps` and `after_rerun_steps` are lists of
`{cwd, argv}` objects. Each test runs them one by one, each in its own cwd, and compares the refs, index, files and backups
with the repository as it was before the archive: the change is back, its files and index entries are those it had, and
no archive of it remains (change native-cli-retire-scripts task 7.2; the frozen script is no longer run).

Run: python -m unittest evals/finish/test_undo_steps.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.append(str(ROOT / "evals"))
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
import vcs_test_support  # noqa: E402


GIT_SAFETY = ["--literal-pathspecs", "--no-replace-objects"]


def git_subcommand(argv):
    """The Git subcommand of an emitted step after its global options (the safety options come first), or None."""
    if argv[:1] != ["git"]:
        return None
    rest = argv[1:]
    while rest and rest[0].startswith("-"):
        rest = rest[1:]
    return rest[0] if rest else None


def undo_kind(step):
    """The kind of an emitted `sw finish undo-step <kind>` step, or None."""
    argv = step["argv"]
    return argv[5] if argv[3:5] == ["finish", "undo-step"] and len(argv) > 5 else None


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fx = _load("finish_fixtures", "fixtures.py")
tp = _load("finish_test_undo_plan", "test_undo_plan.py")  # module attributes only: its test classes are not collected here
tj = _load("finish_test_undo_jj", "test_undo_jj.py")

P = tp.P
SPEC_A, SPEC_B = tp.SPEC_A, tp.SPEC_B
BRANCH = tp.BRANCH
SHELL_WORDS = ("bash", "sh",  # bare-bash: not started
                "set -euo pipefail", "&&", "||", "|", ";", ">", "<", "2>&1")


def outcome(work):
    """What an undo leaves: every ref with its tree, the index, the status, the commit count and subject, the files
    outside .git and the backups under the git dir."""
    gitdir = Path(fx.git(work, "rev-parse", "--absolute-git-dir"))
    backups = gitdir / "specwright-undo"
    return {
        "refs": fx.git(work, "for-each-ref", "--format=%(refname) %(tree)"),
        "index": fx.git(work, "ls-files", "--stage"),
        "status": fx.git(work, "status", "--porcelain=v1", "--untracked-files=all"),
        "commits": fx.git(work, "rev-list", "--count", "HEAD"),
        "subject": fx.git(work, "log", "-1", "--format=%s"),
        "files": fx.snapshot(work),
        "backups": {p.relative_to(backups).as_posix(): p.read_bytes() for p in sorted(backups.rglob("*")) if p.is_file()}
        if backups.is_dir() else {},
    }


def build_single(work, committed=True, deltas=None):
    fx.git(work, "checkout", "-q", "-b", BRANCH)
    fx.make_change(work, "add-x", "DEFERRED", deltas or {"a": "New thing", "b": "B thing"})
    fx.archive(work, "add-x", commit_it=committed)


def build_pair(work):
    fx.git(work, "checkout", "-q", "-b", BRANCH)
    fx.make_change(work, "add-x", "DEFERRED", {"a": "X thing"})
    fx.make_change(work, "add-y", "APPROVE", {"a": "Y thing"})
    fx.archive(work, ["add-x", "add-y"], commit_it=True)


def restored_change(work, expected, name="add-x"):
    """What the undo of `name`'s archive leaves of the change itself in `work`, with the same facts in `expected`, a repo built
    the same way up to the archive: the change's files, its index entries, the archive folder's files and the tracked names."""
    archived = f"{P}/changes/archive/{fx.DATE}-{name}"

    def facts(repo):
        files = fx.snapshot(repo)
        return {"files": {k: v for k, v in files.items() if k.startswith(f"{P}/changes/{name}/")},
                "archived": sorted(k for k in files if k.startswith(archived + "/")),
                "index": fx.git(repo, "ls-files", "--stage", "--", f"{P}/changes/{name}"),
                "tracked_archive": fx.git(repo, "ls-files", "--", archived)}
    return facts(work), facts(expected)


class StepsCase(tp.Base):
    """self.work runs the printed steps; self.expected is the same fixture built without the archive."""

    def setUp(self):
        super().setUp()
        self.expected = fx.make_repo(self.tmp / "expected")

    def new_run(self, work, runner=None, **kw):
        """Plan with sw and run `steps`, then `after_rerun_steps`, each through [runner]; returns its document."""
        runner = runner or (lambda steps: fx.run_steps(self.scripts, steps))
        code, doc, raw = fx.run_plan(work, "add-x", **kw)
        self.assertEqual(code, 0, raw)
        r = runner(doc["steps"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        if doc["after_rerun_steps"]:
            r = runner(doc["after_rerun_steps"])
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return doc

    def restores(self, build, runner=None, **kw):
        """Build the archived fixture in self.work and the unarchived one in self.expected, plan, run the printed steps; the
        change is back as it was."""
        build(self.work)
        with mock.patch.object(fx, "archive", lambda *a, **k: None):
            build(self.expected)
        doc = self.new_run(self.work, runner, **kw)
        got, want = restored_change(self.work, self.expected)
        self.assertEqual(got["files"], want["files"], "the change's files")
        self.assertTrue(got["files"], "the change's files are back")
        self.assertEqual(got["index"], want["index"], "the change's index entries")
        self.assertEqual((got["archived"], got["tracked_archive"]), ([], ""), "no archive of the change remains")
        return doc


class TestUndoSteps(StepsCase):
    def test_every_emitted_git_step_carries_the_safety_options(self):
        doc = self.restores(build_single)
        git_steps = [s for s in doc["steps"] if s["argv"][0] == "git"]
        self.assertTrue(git_steps, doc)
        for step in git_steps:
            self.assertEqual(step["argv"][1:3], GIT_SAFETY, step)
        # the first guard is the preflight, whatever else follows
        self.assertEqual(doc["steps"][0]["argv"][3:7], ["finish", "undo-step", "check", "preflight"], doc["steps"][0])

    def test_check_index_sees_a_staged_gitlink_that_ignore_submodules_hides(self):
        """An update of a gitlink HEAD already has, staged after planning: `diff.ignoreSubmodules=all` hides it from
        `git diff --cached --quiet`."""
        fx.git(self.work, "update-index", "--add", "--cacheinfo", f"160000,{fx.git(self.work, 'rev-parse', 'HEAD')},sub")
        fx.git(self.work, "commit", "-q", "-m", "chore: add a gitlink")
        (self.work / "sub").mkdir()  # an uninitialized submodule: without its directory `git add -A` stages a deletion
        build_single(self.work)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        fx.git(self.work, "config", "diff.ignoreSubmodules", "all")
        head = fx.git(self.work, "rev-parse", "HEAD")
        fx.git(self.work, "update-index", "--cacheinfo", f"160000,{head},sub")
        self.assertEqual(fx.git(self.work, "diff", "--cached", "--name-only"), "", "the configuration does not hide the update")
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(git_subcommand(r.ran[-1]["argv"]), None, r.ran[-1])
        self.assertIn("index", r.stdout + r.stderr)
        self.assertTrue((self.work / tp.ad("add-x")).is_dir(), "a step ran after the index check")

    def test_resume_with_submodule_recurse_leaves_submodule(self):
        """`submodule.recurse=true`, a clean submodule on a local branch, and an archive branch that records another
        gitlink for it: the resume checkout leaves the submodule's HEAD, branch and files alone. No guard refuses the
        fixture: on main the submodule sits at the commit main records (a clean tree), and the gitlink difference is
        outside every member directory."""
        src = self.tmp / "subsrc"
        src.mkdir()
        sub_git = ["-c", "user.name=T", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
        fx.git(src, "init", "-q", "-b", "main")
        (src / "f.txt").write_text("one\n", encoding="utf-8")
        fx.git(src, "add", "-A")
        fx.git(src, *sub_git, "commit", "-q", "-m", "first")
        first = fx.git(src, "rev-parse", "HEAD")
        fx.git(self.work, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(src), "sub")
        fx.git(self.work, "commit", "-q", "-m", "chore: add a submodule")
        build_single(self.work)
        # the archive branch records a newer commit of the submodule, which the submodule already holds as an object
        (src / "f.txt").write_text("two\n", encoding="utf-8")
        fx.git(src, *sub_git, "commit", "-q", "-a", "-m", "second")
        second = fx.git(src, "rev-parse", "HEAD")
        sub = self.work / "sub"
        fx.git(sub, "-c", "protocol.file.allow=always", "fetch", "-q", "origin")
        fx.git(self.work, "update-index", "--cacheinfo", f"160000,{second},sub")
        fx.git(self.work, "commit", "-q", "-m", "chore: move the submodule")
        fx.git(self.work, "checkout", "-q", "main")
        fx.git(sub, "checkout", "-q", "-b", "local", first)
        fx.git(self.work, "config", "submodule.recurse", "true")
        before = (fx.git(sub, "rev-parse", "HEAD"), fx.git(sub, "branch", "--show-current"),
                  (sub / "f.txt").read_bytes())
        self.assertEqual(before[:2], (first, "local"))
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 0, raw)
        steps = doc["steps"]
        checkout = next(i for i, s in enumerate(steps) if git_subcommand(s["argv"]) == "checkout")
        self.assertIn("--no-recurse-submodules", steps[checkout]["argv"])
        r = fx.run_steps(self.scripts, steps[:checkout + 1])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(fx.git(self.work, "branch", "--show-current"), BRANCH)
        after = (fx.git(sub, "rev-parse", "HEAD"), fx.git(sub, "branch", "--show-current"),
                 (sub / "f.txt").read_bytes())
        self.assertEqual(after, before)

    def test_a_merge_in_progress_stops_the_steps_at_the_first_guard(self):
        build_single(self.work)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        gitdir = Path(fx.git(self.work, "rev-parse", "--absolute-git-dir"))
        (gitdir / "MERGE_HEAD").write_text(fx.git(self.work, "rev-parse", "HEAD") + "\n", encoding="utf-8")
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(r.ran), 1, "a step ran after the first guard")
        self.assertIn("operation_in_progress", r.stdout)
        self.assertTrue((self.work / tp.ad("add-x")).is_dir())

    def test_the_preflight_refuses_an_index_routed_elsewhere(self):
        build_single(self.work)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        other = self.work / ".git" / "other-index"
        shutil.copyfile(self.work / ".git" / "index", other)
        r = fx.run_steps(self.scripts, doc["steps"], env={"GIT_INDEX_FILE": str(other)})
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(r.ran), 1)
        self.assertIn("git_env", r.stdout)

    def test_committed_archive_plan_prints_steps(self):
        doc = self.restores(build_single)
        self.assertNotIn("script", doc)
        self.assertNotIn("after_rerun", doc)
        self.assertIsInstance(doc["steps"], list)
        self.assertIsInstance(doc["after_rerun_steps"], list)
        self.assertTrue(doc["steps"], doc)
        for step in doc["steps"]:
            self.assertEqual(set(step), {"cwd", "argv"}, step)
            self.assertTrue(os.path.isabs(step["cwd"]), step)
            self.assertEqual(Path(step["cwd"]).resolve(), self.work.resolve(), step)
            self.assertIsInstance(step["argv"], list)
            for word in step["argv"]:
                self.assertIsInstance(word, str)
                self.assertNotIn(word, SHELL_WORDS, step)
            self.assertIn(Path(step["argv"][0]).stem, ("sw", "git", "jj", "openspec"), step)
            if Path(step["argv"][0]).stem == "sw":
                at = step["argv"].index("--project")
                self.assertEqual(Path(step["argv"][at + 1]).resolve(), self.work.resolve(), step)

    def test_guard_step_stops_the_undo(self):
        build_single(self.work)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        fx.commit(self.work, "feat: later", {"src/app.py": "print('v2')\n"})
        before = fx.state(self.work)
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLess(len(r.ran), len(doc["steps"]), "a step ran after the failing guard")
        self.assertEqual(r.ran[-1]["argv"][3:6], ["finish", "undo-step", "check"], r.ran[-1])
        self.assertEqual(fx.state(self.work), before)
        self.assertFalse(Path(doc["backup_dir"]).exists())

    @unittest.skipUnless(sys.platform == "win32" and shutil.which("powershell"), "platform: PowerShell on Windows only")
    def test_steps_run_from_powershell(self):
        # no bash on PATH, a working directory outside the checkout, every step started by PowerShell in its own cwd
        keep = os.pathsep.join(d for d in os.environ["PATH"].split(os.pathsep) if d and not (Path(d) / "bash.exe").exists())
        env = dict(os.environ, PATH=keep, SPECWRIGHT_HOME=str(vcs_test_support.sw_home()))

        def quote(text):
            return "'" + text.replace("'", "''") + "'"

        def runner(steps):
            lines = ["$ErrorActionPreference = 'Stop'"]
            for step in steps:
                lines += [f"Set-Location -LiteralPath {quote(step['cwd'])}",
                          "& " + " ".join(quote(word) for word in step["argv"]),
                          "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"]
            path = self.scripts / "steps.ps1"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
            return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)],
                                  cwd=self.tmp, env=env, capture_output=True, text=True, encoding="utf-8")

        self.restores(build_single, runner)

    def test_store_backed_plan_runs_from_outside(self):
        # the store has no installed version; the code checkout does. Both are away from the directory the steps start in.
        def build(tag):
            store = fx.make_repo(self.tmp / tag / "store")
            (store / vcs_test_support.STAMP).unlink()
            build_single(store)
            return store, fx.make_repo(self.tmp / tag / "code")

        store, code = build("new")
        with mock.patch.object(fx, "archive", lambda *a, **k: None):
            expected_store, _ = build("expected")
        outside = self.tmp / "outside"
        outside.mkdir()
        args = fx.plan_args("add-x", dir_=store) + ["--code", str(code)]
        status, doc, raw = fx.run_finish(store, *args, cwd=outside)
        self.assertEqual(status, 0, raw)
        for step in doc["steps"]:
            self.assertEqual(Path(step["cwd"]).resolve(), store.resolve(), step)
            if Path(step["argv"][0]).stem == "sw":
                at = step["argv"].index("--project")
                self.assertEqual(Path(step["argv"][at + 1]).resolve(), code.resolve(), step)
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        got, want = restored_change(store, expected_store)
        self.assertEqual(got, want)
        self.assertTrue(got["files"], "the change's files are back")

    def test_write_blob_applies_filters(self):
        def build(work):
            fx.write(work, ".gitattributes", "*.md text eol=crlf\n")
            fx.commit(work, "chore: crlf checkout")
            build_single(work)
            fx.edit(work, SPEC_A, "Baseline purpose", "Amended purpose")
            fx.commit(work, "docs: amend the spec")

        doc = self.restores(build)
        base = Path(doc["backup_dir"]) / "base" / SPEC_A
        self.assertIn(b"\r\n", base.read_bytes())
        self.assertTrue(any(s["argv"][3:6] == ["finish", "undo-step", "write-blob"] for s in doc["steps"]), doc["steps"])

    def test_rmdir_if_empty_keeps_a_held_directory(self):
        def build(work):
            fx.git(work, "checkout", "-q", "-b", BRANCH)
            fx.write(work, f"{P}/specs/b/notes.md", "a neighbour of the new spec\n")
            fx.make_change(work, "add-x", "DEFERRED", {"a": "New thing", "b": "B thing"})
            fx.archive(work, "add-x", commit_it=True)

        self.restores(build)
        self.assertFalse((self.work / SPEC_B).exists())
        self.assertEqual(fx.read(self.work, f"{P}/specs/b/notes.md"), "a neighbour of the new spec\n")

    def test_failing_step_stops_later_steps(self):
        build_single(self.work)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        hook = self.work / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(git_subcommand(r.ran[-1]["argv"]), "commit", r.ran[-1])
        self.assertLess(len(r.ran), len(doc["steps"]), "a step ran after the failing one")
        self.assertTrue((self.work / tp.ad("add-x")).is_dir(), "the move ran after the failed commit")
        self.assertFalse((self.work / tp.cd("add-x")).exists())
        # the recovery text names the backup and what to do; the backup path is the one thing that varies
        text = " ".join(doc["warnings"])
        self.assertIn(doc["backup_dir"], text)


    def test_backup_steps_keep_the_amended_spec_before_restoring(self):
        def build(work):
            build_pair(work)
            fx.edit(work, SPEC_A, "Baseline purpose", "Amended purpose")
            fx.commit(work, "docs: amend the spec")

        doc = self.restores(build)
        backup = f"{doc['backup_dir']}/amended/{SPEC_A}"
        steps = doc["steps"]
        copy = next(i for i, s in enumerate(steps) if s["argv"][3:6] == ["finish", "undo-step", "copy"]
                    and s["argv"][6:] == [SPEC_A, backup])
        restore = next(i for i, s in enumerate(steps) if git_subcommand(s["argv"]) == "restore" and SPEC_A in s["argv"])
        self.assertLess(copy, restore)
        self.assertTrue((Path(doc["backup_dir"]) / "amended" / SPEC_A).is_file())

    def test_after_rerun_steps_refuse_as_before(self):
        # a main spec the user deleted and then recreated: the after-rerun steps stop at it, before any archive runs
        mine = tp.MINE

        def build(work):
            build_pair(work)
            fx.git(work, "rm", "-q", SPEC_A)
            fx.git(work, "commit", "-q", "-m", "docs: retire capability a")

        build(self.work)
        out = fx.run_scripts(self.work, self.scripts, "add-x", rerun=False)
        self.assertEqual(out.plan[0], 0, out.plan[2])
        self.assertEqual(out.script.returncode, 0, out.script.stdout + out.script.stderr)
        fx.write(self.work, SPEC_A, mine)
        r = fx.run_steps(self.scripts, out.plan[1]["after_rerun_steps"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(SPEC_A, r.stdout + r.stderr)
        last = r.ran[-1]["argv"]
        self.assertEqual(last[3:7], ["finish", "undo-step", "check", "absent"], last)
        self.assertEqual([x for x in r.ran if x["argv"][0] == "openspec"], [], "an archive ran before the guard")
        self.assertFalse((self.work / tp.ad("add-y")).exists(), "an archive ran before the guard")
        self.assertEqual(fx.read(self.work, SPEC_A), mine)


class TestBranchCheck(tj.JjBase):
    def test_branch_check_reads_structured_branch(self):
        # planned on feat/add-x, run on feat/other: the branch check reads the backend's branch, stops naming both, and no
        # later step runs
        self.archived_branch()
        code, doc, raw = self.plan()
        self.assertEqual(code, 0, raw)
        self.jjc("new", "main")
        self.jjc("bookmark", "create", "feat/other", "-r", "@-")
        before = self.snapshot()
        r = self.run_steps(doc["steps"])
        text = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0, text)
        self.assertEqual(r.ran[-1]["argv"][3:7], ["finish", "undo-step", "check", "branch"], r.ran[-1])
        self.assertLess(len(r.ran), len(doc["steps"]))
        self.assertIn(tj.BRANCH, text)
        self.assertIn("feat/other", text)
        self.assertEqual(self.snapshot(), before)



class TestResumeGuards(StepsCase):
    """The Git resume's guards around its one checkout (change fix-sw-port-gaps, D2)."""

    OTHER_BACKENDS = ("vcs: jj\n", "vcs: gitbutler\nfinish: pr\n")

    def planned_resume(self):
        """The archive is committed on BRANCH, HEAD is on main, and the resume is planned."""
        build_single(self.work)
        fx.git(self.work, "checkout", "-q", "main")
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 0, raw)
        return doc

    @staticmethod
    def checkouts(steps):
        return [n for n, s in enumerate(steps) if git_subcommand(s["argv"]) == "checkout"]

    @staticmethod
    def branch_guards(steps):
        """(position, expected branch) of each `check branch` step."""
        return [(n, s["argv"][7]) for n, s in enumerate(steps)
                if undo_kind(s) == "check" and s["argv"][6:7] == ["branch"]]

    def test_a_resume_from_main_passes_both_branch_guards(self):
        doc = self.planned_resume()
        steps = doc["steps"]
        (checkout,) = self.checkouts(steps)
        self.assertEqual([(n < checkout, name) for n, name in self.branch_guards(steps)], [(True, "main"), (False, BRANCH)])
        r = fx.run_steps(self.scripts, steps)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.checkouts(r.ran)), 1)
        self.assertEqual(fx.git(self.work, "branch", "--show-current"), BRANCH)

    def test_a_detached_head_moved_after_planning(self):
        build_single(self.work)
        fx.git(self.work, "checkout", "-q", "--detach", "main")
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 0, raw)
        moved = fx.commit(self.work, "feat: another detached commit", {"src/app.py": "print('v2')\n"})
        before = fx.state(self.work)
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.checkouts(r.ran), [], "the checkout ran")
        self.assertEqual(fx.git(self.work, "rev-parse", "HEAD"), moved)
        self.assertEqual(fx.git(self.work, "branch", "--show-current"), "")
        self.assertEqual(fx.state(self.work), before)

    def test_a_backend_selection_changed_before_the_resume_checkout(self):
        for text in self.OTHER_BACKENDS:
            with self.subTest(settings=text):
                self.setUp()
                doc = self.planned_resume()
                fx.write(self.work, f"{P}/specwright.yaml", text)  # the selection the plan was not made under
                before = fx.state(self.work)
                r = fx.run_steps(self.scripts, doc["steps"])
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("git_env", r.stdout)
                self.assertIn(text.split()[1], r.stdout + r.stderr)  # the backend it now selects is named
                self.assertEqual(self.checkouts(r.ran), [], "the checkout ran")
                self.assertEqual(fx.state(self.work), before)

    def test_a_resumed_branch_that_selects_another_backend(self):
        for text in self.OTHER_BACKENDS:
            with self.subTest(settings=text):
                self.setUp()
                build_single(self.work)
                fx.commit(self.work, "chore: select another backend", {f"{P}/specwright.yaml": text})
                tip = fx.git(self.work, "rev-parse", BRANCH)
                fx.git(self.work, "checkout", "-q", "main")
                code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
                self.assertEqual(code, 0, raw)
                r = fx.run_steps(self.scripts, doc["steps"])
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("git_env", r.stdout)
                self.assertTrue(text.split()[1] in r.stdout + r.stderr and "git" in r.stdout + r.stderr)
                self.assertEqual(len(self.checkouts(r.ran)), 1, "the stop comes after the checkout")
                self.assertEqual(r.ran[-1]["argv"][5:7], ["check", "branch"], r.ran[-1])
                self.assertFalse(Path(doc["backup_dir"]).exists(), "a backup was made")
                self.assertEqual(fx.git(self.work, "rev-parse", "HEAD"), tip, "an undo commit was made")
                self.assertEqual(fx.git(self.work, "diff", "--cached", "--name-only"), "")

    def test_configuration_that_reroutes_git_only_on_the_archive_branch(self):
        doc = self.planned_resume()
        # Git reads core.worktree only from the repository's own config file, never through an include, so a conditional
        # include cannot move the work tree; it can still switch on `attr.tree`, which only the archive branch sets
        routed = self.tmp / "on-branch.cfg"
        routed.write_text("[attr]\n\ttree = HEAD\n", encoding="utf-8")
        fx.git(self.work, "config", f"includeIf.onbranch:{BRANCH}.path", routed.as_posix())
        tip = fx.git(self.work, "rev-parse", f"refs/heads/{BRANCH}")
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("git_env", r.stdout)
        (checkout,) = self.checkouts(r.ran)
        self.assertEqual(checkout, len(r.ran) - 2, "the step right after the checkout did not stop")
        self.assertEqual(r.ran[-1]["argv"][5:7], ["check", "preflight"], r.ran[-1])
        self.assertFalse(Path(doc["backup_dir"]).exists(), "a backup was made")
        self.assertEqual(fx.git(self.work, "rev-parse", f"refs/heads/{BRANCH}"), tip, "an undo commit was made")

    def test_a_tag_named_like_the_archive_branch(self):
        build_single(self.work, deltas={"a": "Branch thing"})
        archive_commit = fx.git(self.work, "rev-parse", BRANCH)
        fx.git(self.work, "checkout", "-q", "main")
        fx.git(self.work, "checkout", "-q", "-b", "other")
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "Tag thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        fx.git(self.work, "tag", BRANCH, "HEAD")  # another archive of the same member, named like the branch
        fx.git(self.work, "checkout", "-q", "main")
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["archive_commit"], archive_commit)
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        parent = subprocess.run(["git", "cat-file", "blob", f"{archive_commit}^:{SPEC_A}"], cwd=self.work,
                                capture_output=True, check=True).stdout
        self.assertEqual((self.work / SPEC_A).read_bytes(), parent)

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: macOS and Windows file systems refuse a name with invalid UTF-8 bytes")
    def test_a_branch_name_that_is_not_utf8_at_the_guard(self):
        fx.git(self.work, "checkout", "-q", "-b", "bugfix/add-�")
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing"})
        fx.archive(self.work, "add-x", commit_it=True)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        bad = b"refs/heads/bugfix/add-\xff"  # a branch at the same commit whose name differs by one byte
        subprocess.run([b"git", b"update-ref", bad, b"HEAD"], cwd=self.work, check=True)
        subprocess.run([b"git", b"symbolic-ref", b"HEAD", bad], cwd=self.work, check=True)

        def facts():
            def git_bytes(*args):
                return subprocess.run(["git", *args], cwd=self.work, capture_output=True, check=True).stdout
            return (git_bytes("for-each-ref"), git_bytes("ls-files", "--stage"), (self.work / ".git" / "HEAD").read_bytes(),
                    fx.snapshot(self.work))

        before = facts()
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("not_utf8", r.stdout)
        self.assertEqual(r.ran[-1]["argv"][5:7], ["check", "branch"], r.ran[-1])
        self.assertEqual(facts(), before)


class TestRegularFileReads(StepsCase):
    """A FIFO a branch or a link puts where a step or the version check reads never blocks it (C38, ADR 0043). Each run
    is bounded to 60 seconds, so a read that blocks fails the test instead of hanging it."""

    def fifo(self, name="pipe"):
        """An ignored FIFO with no writer in the work tree."""
        path = self.work / name
        os.mkfifo(path)
        exclude = self.work / ".git" / "info" / "exclude"
        exclude.write_text(exclude.read_text(encoding="utf-8") + name + "\n", encoding="utf-8")
        return path

    def run_bounded(self, steps):
        """Run printed steps like fx.run_steps, each bounded to 60 seconds; stop at the first that fails."""
        env = dict(os.environ, FIXTURE_PREFIX=P, SPECWRIGHT_HOME=str(vcs_test_support.sw_home()))
        last = None
        for step in steps:
            argv = list(step["argv"])
            if argv[0] == "openspec":
                argv = [sys.executable, "-X", "utf8", str(HERE / "fixtures.py"), *argv[1:]]
            last = subprocess.run(argv, cwd=step["cwd"], capture_output=True, text=True, encoding="utf-8", env=env,
                                  timeout=60)
            if last.returncode != 0:
                break
        return last

    def resume_plan(self, tracked_stamp=False):
        """Build the archive on the branch, return to main, and plan the resume."""
        if tracked_stamp:
            self.git("add", "-f", vcs_test_support.STAMP)
            self.git("commit", "-q", "-m", "chore: track the stamp")
        build_single(self.work)

    def finish_resume(self):
        self.git("checkout", "-q", "main")
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 0, raw)
        return doc

    def backups(self):
        return Path(fx.git(self.work, "rev-parse", "--absolute-git-dir")) / "specwright-undo"

    @unittest.skipIf(sys.platform == "win32", "platform: a FIFO needs POSIX")
    def test_version_stamp_that_is_not_a_regular_file(self):
        """The archive branch makes VERSION a link to a FIFO with no writer: the first sw step after the checkout returns
        sw_mismatch saying so, and no backup or undo write runs."""
        self.resume_plan(tracked_stamp=True)
        self.git("checkout", "-q", BRANCH)
        pipe = self.fifo()
        stamp = self.work / vcs_test_support.STAMP
        stamp.unlink()
        os.symlink(pipe, stamp)
        self.git("add", "-f", vcs_test_support.STAMP)
        self.git("commit", "-q", "-m", "chore: link the stamp to a FIFO")
        doc = self.finish_resume()
        result = self.run_bounded(doc["steps"])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        stop = json.loads(result.stdout)
        self.assertEqual(stop["error"], "sw_mismatch", stop)
        self.assertIn("not a regular file", stop["message"])
        self.assertFalse(self.backups().exists(), "a backup directory was made")

    @unittest.skipIf(sys.platform == "win32", "platform: a FIFO needs POSIX")
    def test_settings_file_that_is_not_a_regular_file(self):
        """The archive branch adds openspec/specwright.yaml as a link to an ignored FIFO: the guard after the checkout stops
        with vcs_error naming the path, and no backup or undo write runs."""
        self.resume_plan(tracked_stamp=True)
        self.git("checkout", "-q", BRANCH)
        pipe = self.fifo()
        os.symlink(pipe, self.work / P / "specwright.yaml")
        self.git("add", "-f", f"{P}/specwright.yaml")
        self.git("commit", "-q", "-m", "chore: link the settings to a FIFO")
        doc = self.finish_resume()
        result = self.run_bounded(doc["steps"])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        stop = json.loads(result.stdout)
        self.assertEqual(stop["error"], "vcs_error", stop)
        self.assertIn(f"{P}/specwright.yaml", stop["message"].replace("\\", "/"))
        self.assertFalse(self.backups().exists(), "a backup directory was made")

    @unittest.skipIf(sys.platform == "win32", "platform: a FIFO needs POSIX")
    def test_a_change_marker_that_is_not_a_regular_file(self):
        """The marker the undo removes is replaced, after the plan, by a link to a FIFO with no writer: its copy into the
        backup stops with vcs_error naming it without blocking, and no index change, move or commit follows."""
        # the plan removes a marker only when the archive commit added it
        self.git("checkout", "-q", "-b", BRANCH)
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing", "b": "B thing"})
        fx.archive(self.work, "add-x", marker=True, commit_it=True)
        marker = f"{tp.ad('add-x')}/specwright-change.yaml"
        self.assertEqual(self.git("ls-files", "--", marker), marker, "the archive commit holds the marker")
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        pipe = self.fifo()
        (self.work / marker).unlink()
        os.symlink(pipe, self.work / marker)
        head, index = self.git("rev-parse", "HEAD"), self.git("ls-files", "--stage")
        result = self.run_bounded(doc["steps"])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        stop = json.loads(result.stdout)
        self.assertEqual(stop["error"], "vcs_error", stop)
        self.assertIn(marker, stop["message"].replace("\\", "/"))
        self.assertEqual(self.git("rev-parse", "HEAD"), head, "a commit was made")
        self.assertEqual(self.git("ls-files", "--stage"), index, "the index changed")
        self.assertTrue((self.work / tp.ad("add-x")).is_dir(), "the archive was moved")

    @unittest.skipIf(sys.platform == "win32", "platform: a FIFO needs POSIX")
    def test_destination_that_is_not_a_regular_file(self):
        """A main spec the undo would restore is replaced, after the plan, by a FIFO with no writer: the destination check
        stops the steps naming it without blocking, before any backup or move."""
        build_single(self.work)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        (self.work / SPEC_A).unlink()
        os.mkfifo(self.work / SPEC_A)
        result = self.run_bounded(doc["steps"])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        stop = json.loads(result.stdout)
        self.assertEqual(stop["error"], "unsupported_entry", stop)
        self.assertIn(SPEC_A, stop["message"].replace("\\", "/"))
        self.assertFalse(self.backups().exists(), "a backup directory was made")
        self.assertTrue((self.work / tp.ad("add-x")).is_dir(), "the archive was moved")


class TestRestoredCopy(StepsCase):
    """The undo's attribute guards and its check of the restored decision files (change fix-sw-port-gaps, group 11, D2)."""

    def resume_plan(self):
        """The archive on the branch, a clean main, and the resume plan."""
        build_single(self.work)
        self.git("checkout", "-q", "main")
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 0, raw)
        return doc

    def backups(self):
        return Path(fx.git(self.work, "rev-parse", "--absolute-git-dir")) / "specwright-undo"

    def test_a_checkout_filter_configured_only_when_the_steps_run(self):
        """The plan sees no filter; the steps run with `core.attributesFile` naming one for `tasks.md`: the attribute guard
        before the checkout stops them with unsupported_filter, the smudge command never runs and main stays checked out."""
        doc = self.resume_plan()
        rules = self.tmp / "attributes"
        rules.write_text("tasks.md filter=sentinel\n", encoding="utf-8", newline="")
        ran = self.tmp / "ran.txt"
        self.git("config", "filter.sentinel.smudge", f'echo ran >> "{ran.as_posix()}"; cat')
        self.git("config", "filter.sentinel.clean", "cat")
        env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.attributesFile", "GIT_CONFIG_VALUE_0": rules.as_posix()}
        r = fx.run_steps(self.scripts, doc["steps"], env=env)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("unsupported_filter", r.stdout)
        self.assertIn(f"{tp.ad('add-x')}/tasks.md", r.stdout)
        self.assertFalse(ran.exists(), "the smudge command ran")
        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertFalse(self.backups().exists(), "a backup directory was made")

    def test_an_inherited_attribute_source_stops_the_steps_at_the_first_guard(self):
        doc = self.resume_plan()
        r = fx.run_steps(self.scripts, doc["steps"], env={"GIT_ATTR_SOURCE": "HEAD"})
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(r.ran), 1, "a step ran after the first guard")
        self.assertIn("git_env", r.stdout)
        self.assertIn("GIT_ATTR_SOURCE", r.stdout)
        self.git("config", "attr.tree", "HEAD")
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(r.ran), 1, "a step ran after the first guard")
        self.assertIn("attr.tree", r.stdout)


    def test_restored_decision_bytes_that_differ_from_the_tip_stop_the_steps_after_the_checkout(self):
        """`ident` is no filter, so the attribute guard lets it through; the checkout then expands `$Id$` in `tasks.md`, and
        the restored bytes differ from the tip's blob. Expected red until group 12 adds the check of the restored inputs."""
        build_single(self.work)
        tasks = f"{tp.ad('add-x')}/tasks.md"
        fx.commit(self.work, "chore: an expanded keyword", {f"{P}/.gitattributes": "tasks.md ident\n",
                                                            tasks: "# Tasks\n\n- [ ] 1.1 $Id$\n"})
        self.git("checkout", "-q", "main")
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 0, raw)
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(tasks, r.stdout.replace("\\", "/"))
        self.assertEqual(self.git("branch", "--show-current"), BRANCH, "the checkout ran before the check")
        self.assertFalse(self.backups().exists(), "a backup directory was made")
        self.assertTrue((self.work / tp.ad("add-x")).is_dir(), "the archive was undone")


class TestDestinations(StepsCase):
    """The destination list, its checks and the line sizing of the steps (change fix-sw-port-gaps, group 12, D2)."""

    def backups(self):
        return Path(fx.git(self.work, "rev-parse", "--absolute-git-dir")) / "specwright-undo"

    def test_the_first_undo_in_a_fresh_checkout_proves_its_backup_absent(self):
        """Nothing under `.git/specwright-undo` exists yet: the absence check passes from the nearest existing ancestor and
        the steps run to the end."""
        build_single(self.work)
        self.assertFalse(self.backups().exists())
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        absent = [s for s in doc["steps"] if s["argv"][3:7] == ["finish", "undo-step", "check", "absent"]]
        self.assertTrue(absent, "the plan checks the backup directory is absent")
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.work / tp.cd("add-x")).is_dir(), "the change is back")

    def test_a_git_bulk_undo_whose_synced_spec_paths_force_batching(self):
        """600 new specs: no single `rm --cached` or `remove` line holds their paths under 32,766 units. Each is split into
        runs, and the steps run to one undo commit that leaves no new spec."""
        caps = {f"c{i:04d}-{'y' * 30}": f"Thing {i}" for i in range(600)}
        build_single(self.work, deltas=caps)
        count = int(self.git("rev-list", "--count", "HEAD"))
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        for step in doc["steps"]:
            self.assertLessEqual(len(" ".join(step["argv"])), 32766, step["argv"][:8])
        removes = [s for s in doc["steps"] if s["argv"][3:6] == ["finish", "undo-step", "remove"]]
        self.assertGreater(len(removes), 1, "the removals are one line")
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(int(self.git("rev-list", "--count", "HEAD")), count + 1, "one undo commit")
        left = [k for k in fx.snapshot(self.work) if k.startswith(f"{P}/specs/c0")]
        self.assertEqual(left, [], "a new spec is left")

    @unittest.skipIf(sys.platform == "win32", "platform: a link needs POSIX")
    def test_a_removed_spec_under_a_linked_directory(self):
        """A new spec's capability directory becomes a link to an outside directory with its own `spec.md` after the plan:
        the destination check stops the steps naming it before any backup or move, and the outside file is unchanged."""
        build_single(self.work)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "spec.md").write_text("mine\n", encoding="utf-8", newline="")
        shutil.rmtree(self.work / f"{P}/specs/b")
        os.symlink(outside, self.work / f"{P}/specs/b")
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"{P}/specs/b", (r.stdout + r.stderr).replace("\\", "/"))
        self.assertEqual((outside / "spec.md").read_text(encoding="utf-8"), "mine\n")
        self.assertTrue((self.work / tp.ad("add-x")).is_dir(), "the archive was moved")
        self.assertFalse(self.backups().exists(), "a backup directory was made")

    @unittest.skipIf(sys.platform == "win32", "platform: a link needs POSIX")
    def test_a_rerun_destination_linked_after_the_undo(self):
        """The undo's steps ran; a rerun spec's capability directory then becomes a link to an outside directory: the
        after-rerun destination check stops naming it before any `openspec archive` starts."""
        self.git("checkout", "-q", "-b", BRANCH)
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "X thing"})
        fx.make_change(self.work, "add-y", "APPROVE", {"c": "Y thing"})
        fx.archive(self.work, ["add-x", "add-y"], commit_it=True)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        outside = self.tmp / "outside"
        outside.mkdir()
        spec = self.work / f"{P}/specs/c"
        if spec.is_dir() and not spec.is_symlink():
            shutil.rmtree(spec)
        os.symlink(outside, spec)
        r = fx.run_steps(self.scripts, doc["after_rerun_steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"{P}/specs/c", (r.stdout + r.stderr).replace("\\", "/"))
        self.assertTrue(all(s["argv"][0] != "openspec" for s in r.ran), "an archive started")
        self.assertEqual(list(outside.iterdir()), [], "a file was written outside the checkout")

    @unittest.skipIf(sys.platform == "win32", "platform: a link needs POSIX")
    def test_a_linked_archive_directory(self):
        """`changes/archive` becomes a link to an outside directory holding the archived member, which has no spec deltas:
        the destination check stops the steps naming the member before any backup or move."""
        self.git("checkout", "-q", "-b", BRANCH)
        fx.make_change(self.work, "add-x", "DEFERRED", {})
        fx.archive(self.work, "add-x", commit_it=True)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        archive = self.work / P / "changes" / "archive"
        outside = self.tmp / "outside"
        shutil.move(str(archive), str(outside))
        os.symlink(outside, archive)
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(tp.ad("add-x"), (r.stdout + r.stderr).replace("\\", "/"))
        self.assertTrue((outside / f"{fx.DATE}-add-x").is_dir(), "the member left the outside directory")
        self.assertFalse(self.backups().exists(), "a backup directory was made")

    def exclude(self, pattern):
        """Ignore `pattern` through .git/info/exclude."""
        path = self.work / ".git" / "info" / "exclude"
        path.write_text(path.read_text(encoding="utf-8") + pattern + "\n", encoding="utf-8")

    def marker_archive(self):
        """The archive of add-x on the branch with its change marker, committed. Returns the marker's path."""
        fx.git(self.work, "checkout", "-q", "-b", BRANCH)
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing", "b": "B thing"})
        fx.archive(self.work, "add-x", marker=True, commit_it=True)
        return f"{tp.ad('add-x')}/specwright-change.yaml"

    def resume_plan(self):
        """From a clean main, plan the resume of the archive branch."""
        self.git("checkout", "-q", "main")
        code, doc, raw = fx.run_plan(self.work, "add-x", branch=BRANCH)
        self.assertEqual(code, 0, raw)
        return doc

    def saved_marker(self, doc):
        return Path(doc["backup_dir"]) / "markers" / "add-x" / "specwright-change.yaml"

    def step_index(self, steps, test, what):
        found = [i for i, s in enumerate(steps) if test(s)]
        self.assertTrue(found, f"no {what} in the steps")
        return found[0]

    def test_an_ignored_directory_at_a_restore_destination(self):
        """The resume plan is made; an ignored, untracked, non-empty directory then appears where the change comes back:
        the steps stop at the destination check after the checkout, before any backup or index write."""
        build_single(self.work)
        tip = self.git("rev-parse", BRANCH)
        doc = self.resume_plan()
        keep = self.work / tp.cd("add-x") / "keep" / "notes.txt"
        keep.parent.mkdir(parents=True)
        keep.write_text("mine\n", encoding="utf-8", newline="")
        self.exclude(f"/{tp.cd('add-x')}/")
        self.git("check-ignore", "-q", "--", f"{tp.cd('add-x')}/keep/notes.txt")
        self.assertEqual(self.git("status", "--porcelain"), "", "the directory is hidden from Git")
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(tp.cd("add-x"), (r.stdout + r.stderr).replace("\\", "/"))
        self.assertEqual(self.git("branch", "--show-current"), BRANCH, "the checkout ran before the stop")
        self.assertEqual(keep.read_text(encoding="utf-8"), "mine\n", "the ignored file was lost")
        self.assertTrue((self.work / tp.ad("add-x")).is_dir(), "the archive was moved")
        self.assertEqual(self.git("rev-parse", "HEAD"), tip, "an undo commit was made")
        self.assertEqual(self.git("status", "--porcelain"), "", "an index write ran")
        self.assertFalse(self.backups().exists(), "a backup directory was made")

    def test_an_untracked_file_in_a_resumed_archive(self):
        """An ignored file lies in the archive directory on main, where the tip tracks no such path: after the checkout the
        steps stop naming it, before any backup or index write."""
        build_single(self.work)
        tip = self.git("rev-parse", BRANCH)
        doc = self.resume_plan()
        extra = self.work / tp.ad("add-x") / "extra" / "draft.md"
        extra.parent.mkdir(parents=True)
        extra.write_text("mine\n", encoding="utf-8", newline="")
        self.exclude("draft.md")
        rel = f"{tp.ad('add-x')}/extra/draft.md"
        self.git("check-ignore", "-q", "--", rel)
        self.assertNotIn(rel, self.git("ls-tree", "-r", "--name-only", BRANCH).splitlines(), "the tip tracks it")
        self.assertEqual(self.git("status", "--porcelain"), "", "the file is hidden from Git")
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(rel, (r.stdout + r.stderr).replace("\\", "/"))
        self.assertEqual(self.git("branch", "--show-current"), BRANCH, "the checkout ran before the stop")
        self.assertEqual(extra.read_text(encoding="utf-8"), "mine\n")
        self.assertEqual(self.git("rev-parse", "HEAD"), tip, "an undo commit was made")
        self.assertFalse(self.backups().exists(), "a backup directory was made")
        self.assertTrue((self.work / tp.ad("add-x")).is_dir(), "the archive was moved")

    def test_an_edited_change_marker_in_the_archive(self):
        """The marker the undo removes is edited after the plan was printed, and the guards pass: the backup holds its
        bytes as they were when the backup step ran, copied before the undo's first index change."""
        marker = self.marker_archive()
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        edited = b"code_changes: none\nedited_after_the_plan: true\n"
        (self.work / marker).write_bytes(edited)
        self.assertNotEqual(self.git("show", f"HEAD:{marker}").encode("utf-8"), edited, "the edit is the committed marker")
        steps = doc["steps"]
        copy = self.step_index(steps, lambda s: undo_kind(s) == "copy" and "--if-present" in s["argv"], "marker copy")
        first_index_change = self.step_index(
            steps, lambda s: git_subcommand(s["argv"]) in ("rm", "read-tree", "restore"), "index change")
        self.assertLess(copy, first_index_change)
        r = fx.run_steps(self.scripts, steps)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.saved_marker(doc).read_bytes(), edited)
        self.assertFalse((self.work / tp.cd("add-x") / "specwright-change.yaml").exists(), "the marker was kept in place")

    def test_a_guard_refuses_before_the_backup(self):
        """A staged change made after the plan stops `check index`, and on a resume a dirty tree stops `check clean`: each
        stops the steps at the guard, the marker is untouched and no backup directory exists."""
        marker = self.marker_archive()
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        before = (self.work / marker).read_bytes()
        (self.work / "README.md").write_text("changed\n", encoding="utf-8", newline="")
        self.git("add", "README.md")
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(undo_kind(r.ran[-1]), "check", r.ran[-1])
        self.assertEqual((self.work / marker).read_bytes(), before, "the marker changed")
        self.assertFalse(self.backups().exists(), "a backup directory was made")
        self.git("restore", "--staged", "--worktree", "--", "README.md")
        tip = self.git("rev-parse", BRANCH)
        doc = self.resume_plan()
        (self.work / "README.md").write_text("dirty\n", encoding="utf-8", newline="")
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.ran[-1]["argv"][5:7], ["check", "clean"], r.ran[-1])
        self.assertEqual(self.git("branch", "--show-current"), "main", "the checkout ran")
        self.assertEqual(self.git("rev-parse", BRANCH), tip)
        self.assertEqual((self.work / "README.md").read_text(encoding="utf-8"), "dirty\n")
        self.assertFalse(self.backups().exists(), "a backup directory was made")

    def test_a_resumed_undos_marker(self):
        """On a resume the marker is copied after the checkout and every guard that follows it, before the first
        `git rm --cached`, and the copy holds the marker's bytes."""
        self.marker_archive()
        doc = self.resume_plan()
        steps = doc["steps"]
        checkout = self.step_index(steps, lambda s: git_subcommand(s["argv"]) == "checkout", "checkout")
        copy = self.step_index(steps, lambda s: undo_kind(s) == "copy" and "--if-present" in s["argv"], "marker copy")
        rm = self.step_index(steps, lambda s: git_subcommand(s["argv"]) == "rm" and "--cached" in s["argv"], "git rm --cached")
        guards = [i for i, s in enumerate(steps) if i > checkout and undo_kind(s) == "check"]
        self.assertTrue(guards, "no guard follows the checkout")
        self.assertTrue(all(i < copy for i in guards), f"a guard follows the copy: {guards} {copy}")
        self.assertLess(copy, rm)
        r = fx.run_steps(self.scripts, steps)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.saved_marker(doc).read_bytes(), b"code_changes: none\n")

    def test_a_marker_deleted_after_planning(self):
        """The marker of a committed archive is deleted after the plan: its backup step does nothing and the undo
        completes with one commit, the change back and no marker in the backup."""
        marker = self.marker_archive()
        count = int(self.git("rev-list", "--count", "HEAD"))
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        (self.work / marker).unlink()
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.saved_marker(doc).exists(), "a marker was backed up")
        self.assertEqual(int(self.git("rev-list", "--count", "HEAD")), count + 1, "one undo commit")
        self.assertTrue((self.work / tp.cd("add-x") / "review.md").is_file(), "the change is back")
        self.assertEqual(self.git("ls-files", "--", f"{tp.cd('add-x')}/specwright-change.yaml"), "")

    @unittest.skipIf(sys.platform == "win32", "platform: a link needs POSIX")
    def test_a_plain_git_removal_under_a_linked_directory(self):
        """An uncommitted archive made a new spec; its capability directory then links to an outside directory holding a
        regular `spec.md`: the plan stops naming the path, nothing is backed up or moved, and the outside file is unchanged."""
        build_single(self.work, committed=False)
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "spec.md").write_text("mine\n", encoding="utf-8", newline="")
        shutil.rmtree(self.work / f"{P}/specs/b")
        os.symlink(outside, self.work / f"{P}/specs/b")
        self.assertTrue((self.work / SPEC_B).is_file(), "the link resolves to a regular spec.md")
        before = fx.state(self.work)
        self.assertStops(fx.run_plan(self.work, "add-x"), "unsupported_entry", f"{P}/specs/b")
        self.assertEqual(fx.state(self.work), before)
        self.assertEqual((outside / "spec.md").read_text(encoding="utf-8"), "mine\n")
        self.assertTrue((self.work / tp.ad("add-x")).is_dir(), "the archive was moved")
        self.assertFalse(self.backups().exists(), "a backup directory was made")


class TestNestedPlanningRoot(StepsCase):
    """The rerun runs in the selected OpenSpec root, with the pinned OpenSpec CLI (change fix-sw-port-gaps, group 12, D2).
    CI installs it before the evals run (`.github/workflows/evals.yml`); a rerun of OPENSPEC_VERSION selects this module."""

    PROPOSAL = ("## Why\n\nThe undo evals need an active change that the real OpenSpec CLI can archive again, with enough "
                "text to pass its validation.\n\n## What Changes\n\n- Adds a requirement to the a capability.\n")

    def openspec(self):
        found = shutil.which("openspec")
        if not found:
            if os.environ.get("CI"):
                self.fail("the pinned openspec CLI is not on PATH in CI")
            self.skipTest("platform: the openspec CLI is not on PATH")
        return found

    def test_a_rerun_under_a_nested_planning_root(self):
        """`planning/openspec` is the selected root and the checkout's top-level `openspec/` holds an active change of the
        same name: the printed steps, run with the real `openspec archive`, change only the `planning/` root."""
        real = self.openspec()
        nested = f"planning/{P}"
        (self.tmp / "nested").mkdir()
        work = fx.make_repo(self.tmp / "nested", prefix=nested)
        fx.make_change(work, "add-y", "APPROVE", {"a": "Top level thing"})
        fx.write(work, f"{P}/changes/add-y/proposal.md", self.PROPOSAL)
        fx.write(work, f"{P}/specs/a/spec.md", fx.base_spec("a"))
        fx.commit(work, "chore: a top-level OpenSpec root")
        fx.git(work, "checkout", "-q", "-b", BRANCH)
        fx.make_change(work, "add-x", "DEFERRED", {"a": "X thing"}, prefix=nested)
        fx.make_change(work, "add-y", "APPROVE", {"a": "Y thing"}, prefix=nested)
        fx.commit(work, "docs(add-y): a proposal that validates", {f"{nested}/changes/add-y/proposal.md": self.PROPOSAL})
        fx.archive(work, ["add-x", "add-y"], prefix=nested, commit_it=True)

        def top_level():
            return {k: v for k, v in fx.snapshot(work).items() if k.startswith(f"{P}/")}
        top = top_level()
        self.assertTrue((work / P / "changes" / "add-y" / "proposal.md").is_file(), "the top-level change is active")
        env = {"XDG_DATA_HOME": str(self.tmp / "xdg-data"), "XDG_CONFIG_HOME": str(self.tmp / "xdg-config"),
               "OPENSPEC_TELEMETRY": "0"}
        self.new_run(work, lambda steps: fx.run_steps(self.scripts, steps, env=env, tools={"openspec": real}),
                     prefix=nested)
        self.assertEqual(top_level(), top, "the top-level root changed")
        archived = sorted(p.name for p in (work / nested / "changes" / "archive").glob("*-add-y"))
        self.assertEqual(len(archived), 1, f"the planning root's add-y was not archived again: {archived}")
        self.assertTrue((work / nested / "changes" / "add-x" / "review.md").is_file(), "add-x is not back")
        self.assertFalse((work / nested / "changes" / "add-y").exists(), "add-y stays active")

if __name__ == "__main__":
    unittest.main()
