"""The undo plan prints steps (change native-cli-retire-scripts, group 4): `steps` and `after_rerun_steps` are lists of
`{cwd, argv}` objects. Each test runs them one by one, each in its own cwd, and compares the refs, index, files and backups
with what the old script left on the same fixture (the frozen oracle prints that script; evals/finish/oracle/finish.sh).

Run: python -m unittest evals/finish/test_undo_steps.py
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.append(str(ROOT / "evals"))
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
import vcs_test_support  # noqa: E402


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


class StepsCase(tp.Base):
    """self.work runs the printed steps; self.old runs the old script on the same fixture."""

    def setUp(self):
        super().setUp()
        self.old = fx.make_repo(self.tmp / "old")

    def old_run(self, work, **kw):
        """Plan with the oracle and run its script (and its after-rerun script); returns its document."""
        code, doc, raw = fx.run_oracle(work, *fx.plan_args("add-x", **kw))
        self.assertEqual(code, 0, raw)
        r = fx.run_bash(work, self.scripts, doc["script"], "undo")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        if doc.get("after_rerun"):
            r = fx.run_bash(work, self.scripts, doc["after_rerun"], "after")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return doc

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

    def same_as_old(self, build, runner=None, **kw):
        build(self.work)
        build(self.old)
        doc = self.new_run(self.work, runner, **kw)
        old = self.old_run(self.old, **kw)
        self.assertEqual(outcome(self.work), outcome(self.old))
        return doc, old


class TestUndoSteps(StepsCase):
    def test_committed_archive_plan_prints_steps(self):
        doc, _ = self.same_as_old(build_single)
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

        self.same_as_old(build_single, runner)

    def test_store_backed_plan_runs_from_outside(self):
        # the store has no installed version; the code checkout does. Both are away from the directory the steps start in.
        def build(tag):
            store = fx.make_repo(self.tmp / tag / "store")
            (store / vcs_test_support.STAMP).unlink()
            build_single(store)
            return store, fx.make_repo(self.tmp / tag / "code")

        store, code = build("new")
        old_store, old_code = build("old")
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
        ostatus, odoc, oraw = fx.run_oracle(old_store, *(fx.plan_args("add-x", dir_=old_store) + ["--code", str(old_code)]),
                                            cwd=outside)
        self.assertEqual(ostatus, 0, oraw)
        r = fx.run_bash(old_store, self.scripts, odoc["script"], "undo")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(outcome(store), outcome(old_store))

    def test_write_blob_applies_filters(self):
        def build(work):
            fx.write(work, ".gitattributes", "*.md text eol=crlf\n")
            fx.commit(work, "chore: crlf checkout")
            build_single(work)
            fx.edit(work, SPEC_A, "Baseline purpose", "Amended purpose")
            fx.commit(work, "docs: amend the spec")

        doc, _ = self.same_as_old(build)
        base = Path(doc["backup_dir"]) / "base" / SPEC_A
        self.assertIn(b"\r\n", base.read_bytes())
        self.assertTrue(any(s["argv"][3:6] == ["finish", "undo-step", "write-blob"] for s in doc["steps"]), doc["steps"])

    def test_rmdir_if_empty_keeps_a_held_directory(self):
        def build(work):
            fx.git(work, "checkout", "-q", "-b", BRANCH)
            fx.write(work, f"{P}/specs/b/notes.md", "a neighbour of the new spec\n")
            fx.make_change(work, "add-x", "DEFERRED", {"a": "New thing", "b": "B thing"})
            fx.archive(work, "add-x", commit_it=True)

        self.same_as_old(build)
        self.assertFalse((self.work / SPEC_B).exists())
        self.assertEqual(fx.read(self.work, f"{P}/specs/b/notes.md"), "a neighbour of the new spec\n")

    def test_failing_step_stops_later_steps(self):
        def build(work):
            build_single(work)

        build(self.work)
        code, doc, raw = fx.run_plan(self.work, "add-x")
        self.assertEqual(code, 0, raw)
        hook = self.work / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        r = fx.run_steps(self.scripts, doc["steps"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.ran[-1]["argv"][:2], ["git", "commit"], r.ran[-1])
        self.assertLess(len(r.ran), len(doc["steps"]), "a step ran after the failing one")
        self.assertTrue((self.work / tp.ad("add-x")).is_dir(), "the move ran after the failed commit")
        self.assertFalse((self.work / tp.cd("add-x")).exists())
        # the recovery text is the old plan's, up to the backup path
        build(self.old)
        ocode, odoc, oraw = fx.run_oracle(self.old, *fx.plan_args("add-x"))
        self.assertEqual(ocode, 0, oraw)

        def plain(d):
            return [w.replace(d["backup_dir"], "<backup>") for w in d["warnings"]]

        self.assertEqual(plain(doc), plain(odoc))

    def test_backup_steps_match_old_script_backups(self):
        def build(work):
            build_pair(work)
            fx.edit(work, SPEC_A, "Baseline purpose", "Amended purpose")
            fx.commit(work, "docs: amend the spec")

        doc, _ = self.same_as_old(build)
        backup = f"{doc['backup_dir']}/amended/{SPEC_A}"
        steps = doc["steps"]
        copy = next(i for i, s in enumerate(steps) if s["argv"][3:6] == ["finish", "undo-step", "copy"]
                    and s["argv"][6:] == [SPEC_A, backup])
        restore = next(i for i, s in enumerate(steps) if s["argv"][:2] == ["git", "restore"] and SPEC_A in s["argv"])
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
        build(self.old)
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
        # the old script refuses at the same file and leaves the same tree
        code, odoc, raw = fx.run_oracle(self.old, *fx.plan_args("add-x"))
        self.assertEqual(code, 0, raw)
        self.assertEqual(fx.run_bash(self.old, self.scripts, odoc["script"], "undo").returncode, 0)
        fx.write(self.old, SPEC_A, mine)
        o = fx.run_bash(self.old, self.scripts, odoc["after_rerun"], "after")
        self.assertNotEqual(o.returncode, 0)
        self.assertEqual(outcome(self.work), outcome(self.old))


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


if __name__ == "__main__":
    unittest.main()
