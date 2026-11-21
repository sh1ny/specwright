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
        self.assertEqual(len(r.ran), 1, "a step ran after the refusal")
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


if __name__ == "__main__":
    unittest.main()
