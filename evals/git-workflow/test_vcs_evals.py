"""Offline checks of the jj-backend live evals: their fixtures and graders.

The five evals (`eval-branch-git-jj-note`, `eval-branch-jj-dirty-no-stash`, `eval-branch-store-probe-fails`,
`eval-debug-jj-dirty-no-stash`, `eval-debug-jj-clean`) are live-agent evals: an agent runs the skill in the
fixture, then grade.py inspects the resulting repository, the Git trace, the stub-`jj` call log and the report. This
module proves the parts that run offline: each fixture builds the state its scenario names (checked by running the
real `vcs.sh` against it), and each grader passes the outcome the spec asks for and fails the outcomes it forbids.
It does not prove any live agent behaves that way; those runs stay red until they pass.

Fixtures that need the real jj skip as `jj not installed` unless SPECWRIGHT_REQUIRE_JJ=1 (evals/vcs/jjenv.py).

Run: python -m unittest discover evals/git-workflow -p "test_vcs_evals.py"
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "evals" / "vcs"))

import fixtures  # noqa: E402
import grade  # noqa: E402
import jjenv  # noqa: E402
from vcs_test_support import VCS, bash_run  # noqa: E402

NAMES = ("eval-branch-git-jj-note", "eval-branch-jj-dirty-no-stash", "eval-branch-store-probe-fails",
         "eval-debug-jj-dirty-no-stash", "eval-debug-jj-clean")
NEW = "feat/add-csv-export"
STASH = "No stash was made: no stash entry, no refs/stash and no git stash write in the trace"


def git(repo, *args, trace=None):
    env = {**os.environ, **({"GIT_TRACE": str(trace)} if trace else {})}
    r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, (args, r.stderr)
    return r.stdout.strip()


class Fx(unittest.TestCase):
    def build(self, name):
        if name != "eval-branch-git-jj-note" and name != "eval-branch-store-probe-fails":
            jjenv.require_jj()
        tmp = tempfile.mkdtemp(prefix="swe-")
        self.addCleanup(fixtures.rmtree, tmp)
        self.run_dir = Path(tmp) / "run"
        self.repo = self.run_dir / "repo"
        self.run_dir.mkdir()
        fixtures.build(name, self.repo)
        return self.repo

    def say(self, text):
        (self.run_dir / "outputs").mkdir(exist_ok=True)
        (self.run_dir / "outputs" / "report.md").write_text(text, encoding="utf-8")

    def trace(self, _repo, *cmds):
        """Append `trace: built-in: git ...` lines, as GIT_TRACE writes them."""
        with (self.repo / "git-trace.log").open("a", encoding="utf-8") as f:
            for c in cmds:
                f.write(f"10:00:00.000000 git.c:460 trace: built-in: git {' '.join(c)}\n")

    def vcs(self, repo, *args, role="code", code=None):
        r = bash_run([VCS, *args, "--repo", repo, "--role", role, *(["--code", code] if code else [])], self.repo, shim=self.repo / "bin")
        return r.returncode, json.loads(r.stdout or "{}")

    def jj(self, *args):
        """Run the real jj in the run's repo; any jj command first snapshots the working copy into a new undescribed @."""
        import shutil
        r = subprocess.run([shutil.which("jj"), *args], cwd=self.repo, capture_output=True, text=True)
        assert r.returncode == 0, (args, r.stderr)
        return r.stdout

    def results(self, name):
        return {t: (ok, ev) for t, ok, ev in grade.check_vcs(name, self.repo, self.run_dir)}

    def failed(self, name):
        res = self.results(name)
        return [t for t, (ok, _) in res.items() if not ok]


class FixtureStates(Fx):
    def test_git_jj_note_is_a_git_repo_with_jj_metadata_and_a_jj_that_must_not_run(self):
        repo = self.build("eval-branch-git-jj-note")
        self.assertTrue((repo / ".jj").is_dir())
        self.assertEqual(git(repo, "status", "--porcelain"), "", "the metadata and the run's helper files must not dirty the tree")
        self.assertNotIn("vcs:", (repo / "openspec/specwright.yaml").read_text(encoding="utf-8"))
        code, out = self.vcs(repo, "state")
        self.assertEqual((code, out["backend"], out["branch"], out["on_main"], out["clean"], out.get("jj_present")),
                         (0, "git", "main", True, True, True), out)
        self.assertFalse((repo / "jj-calls.log").exists(), "the Git backend ran jj")

    def test_jj_dirty_gate_fixture(self):
        repo = self.build("eval-branch-jj-dirty-no-stash")
        code, out = self.vcs(repo, "state")
        self.assertEqual((code, out["backend"], out["on_main"], out["clean"], out["dirty_paths"]),
                         (0, "jj", True, False, ["README.md"]), out)

    def test_debug_dirty_fixture_fails_only_because_of_the_uncommitted_edit(self):
        repo = self.build("eval-debug-jj-dirty-no-stash")
        code, out = self.vcs(repo, "state")
        self.assertEqual((code, out["backend"], out["clean"], out["dirty_paths"]), (0, "jj", False, ["greet.py"]), out)
        tests = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=repo, capture_output=True, text=True)
        self.assertNotEqual(tests.returncode, 0, "test_greet_named must fail with the edit")
        committed = git(repo, "show", "main:greet.py")
        self.assertIn('Hello, {name}!', committed, "the committed greet.py is correct")

    def test_debug_clean_fixture_has_a_committed_bug_and_an_empty_working_copy(self):
        repo = self.build("eval-debug-jj-clean")
        code, out = self.vcs(repo, "state")
        self.assertEqual((code, out["backend"], out["clean"], out["dirty_paths"]), (0, "jj", True, []), out)
        tests = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=repo, capture_output=True, text=True)
        self.assertNotEqual(tests.returncode, 0, "the committed bug must fail the test")

    def test_store_probe_fixture_asks_jj_for_a_git_store(self):
        repo = self.build("eval-branch-store-probe-fails")
        code, store = repo / "code", repo / "store"
        self.assertFalse((store / ".jj").exists())
        self.assertIn("vcs: jj", (code / "openspec/specwright.yaml").read_text(encoding="utf-8"))
        self.assertIn("planning_store:", (code / "openspec/specwright.yaml").read_text(encoding="utf-8"))
        rc, out = self.vcs(store, "state", role="store", code=code)
        self.assertEqual((rc, out.get("error")), (1, "not_managed"), out)
        calls = (repo / "jj-calls.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(calls, ["free jj --version"], "the stub reports whether the gate lock was held at each probe")

    def test_stub_jj_reports_a_held_gate_lock(self):
        repo = self.build("eval-branch-store-probe-fails")
        lock = repo / "store" / ".git" / "specwright-gate.lock"
        lock.mkdir()
        self.vcs(repo / "store", "state", role="store", code=repo / "code")
        self.assertEqual((repo / "jj-calls.log").read_text(encoding="utf-8").splitlines(), ["held jj --version"])


class GitJjNote(Fx):
    NAME = "eval-branch-git-jj-note"

    def done(self, report="Note: this repo has jj metadata (.jj/); `vcs: jj` would route writes through jj. Continuing on Git. "
                          "On branch feat/add-csv-export (from main)."):
        repo = self.build(self.NAME)
        git(repo, "checkout", "-b", NEW, trace=repo / "git-trace.log")
        fixtures.write(repo, "openspec/changes/add-csv-export/.openspec.yaml", "schema: specwright\n")
        self.say(report)
        return repo

    def test_the_outcome_the_spec_asks_for_passes_every_check(self):
        self.done()
        self.assertEqual(self.failed(self.NAME), [])

    def test_a_jj_command_fails(self):
        repo = self.done()
        (repo / "jj-calls.log").write_text("jj bookmark create feat/add-csv-export\n", encoding="utf-8")
        self.assertEqual(self.failed(self.NAME), ["No jj command ran"])

    def test_no_note_fails(self):
        self.done(report="On branch feat/add-csv-export (from main).")
        self.assertEqual(self.failed(self.NAME), ["The report says the repo has jj metadata and that vcs: jj routes writes through jj"])

    def test_a_second_git_write_fails(self):
        repo = self.done()
        self.trace(repo, ["stash", "push", "-u"])
        self.assertEqual(self.failed(self.NAME), ["The only Git write was git checkout -b feat/add-csv-export", STASH])

    def test_branch_on_the_wrong_commit_fails(self):
        repo = self.build(self.NAME)
        self.say("Note: jj metadata, `vcs: jj`.")
        self.assertIn("Branch feat/add-csv-export exists, is checked out and starts at main's tip", self.failed(self.NAME))


class JjDirtyGate(Fx):
    NAME = "eval-branch-jj-dirty-no-stash"
    GOOD = ("The working copy is not clean: README.md changed. Commit it first, or abort. "
            "jj has no stash, so I will not stash. No branch was created.")

    def test_stopping_and_offering_commit_or_abort_passes(self):
        self.build(self.NAME)
        self.trace(self.repo, ["rev-parse", "--show-toplevel"], ["status", "--porcelain"])
        self.say(self.GOOD)
        self.assertEqual(self.failed(self.NAME), [])

    def test_a_branch_a_stash_or_a_lost_edit_fails(self):
        repo = self.build(self.NAME)
        git(repo, "branch", NEW)
        self.trace(repo, ["stash", "push", "-u"])
        self.say(self.GOOD)
        failed = self.failed(self.NAME)
        self.assertIn("Still on main with no new branch", failed)
        self.assertIn("No stash was made: no stash entry, no refs/stash and no git stash write in the trace", failed)
        self.assertIn("The only Git commands were reads", failed)

    def test_offering_a_stash_fails(self):
        self.build(self.NAME)
        self.trace(self.repo, ["status", "--porcelain"])
        self.say("README.md changed. Options: commit it, stash it, or abort.")
        self.assertEqual(self.failed(self.NAME), ["The report does not offer a stash"])

    def test_the_edit_being_reverted_fails(self):
        repo = self.build(self.NAME)
        self.trace(repo, ["status", "--porcelain"])
        git(repo, "checkout", "--", "README.md")
        self.say(self.GOOD)
        self.assertIn("The uncommitted README.md edit is still in the working tree", self.failed(self.NAME))


class StoreProbeFails(Fx):
    NAME = "eval-branch-store-probe-fails"
    GOOD = "Stopped: the store has no .jj (not_managed), so planning_store.vcs: jj cannot be used. No branch was created in either repo."

    def stopped(self, calls="held jj --version\n"):
        repo = self.build(self.NAME)
        (repo / "jj-calls.log").write_text(calls, encoding="utf-8")
        self.trace(repo, ["rev-parse", "--is-inside-work-tree"], ["branch", "--show-current"], ["status", "--porcelain"])
        self.say(self.GOOD)
        return repo

    def test_stop_with_the_lock_released_passes(self):
        self.stopped()
        self.assertEqual(self.failed(self.NAME), [])

    def test_a_probe_without_the_lock_fails(self):
        self.stopped(calls="free jj --version\n")
        self.assertEqual(self.failed(self.NAME), ["Every jj probe of the store ran with the gate lock held, and at least one ran"])

    def test_lock_left_behind_fails(self):
        repo = self.stopped()
        (repo / "store" / ".git" / "specwright-gate.lock").mkdir()
        self.assertEqual(self.failed(self.NAME), ["No gate lock is left in the store"])

    def test_a_branch_in_either_repo_fails(self):
        repo = self.stopped()
        git(repo / "code", "branch", NEW)
        self.assertIn("Both repos are on main with only the main branch and no new commit", self.failed(self.NAME))

    def test_missing_report_of_the_failure_fails(self):
        self.stopped()
        self.say("Something went wrong with the store.")
        self.assertEqual(self.failed(self.NAME), ["The report names the store and its missing .jj"])


class DebugDirty(Fx):
    NAME = "eval-debug-jj-dirty-no-stash"
    GOOD = ("Your uncommitted change to greet.py is the suspect: `git stash list` is empty and jj has no stash, so I did not stash. "
            "Please set your edits aside (or commit them) so I can run the test on a clean tree, or abort. Which do you prefer?")

    def test_asking_the_user_passes(self):
        self.build(self.NAME)
        self.trace(self.repo, ["stash", "list"], ["status", "--porcelain"])
        self.say(self.GOOD)
        self.assertEqual(self.failed(self.NAME), [])

    def test_stashing_fails(self):
        repo = self.build(self.NAME)
        self.trace(repo, ["stash", "list"], ["stash", "push", "-u", "-m", "specwright-debug: greet"])
        self.say(self.GOOD)
        failed = self.failed(self.NAME)
        self.assertIn("No stash was made: no stash entry, no refs/stash and no git stash write in the trace", failed)
        self.assertIn("The only Git commands were reads", failed)

    def test_a_jj_snapshot_and_jjs_config_listing_pass(self):
        # every jj read snapshots the edited working copy into a new @ (kept under refs/jj/keep/), and jj's Git library lists the
        # config to find its files; neither commits or writes anything
        self.build(self.NAME)
        self.jj("status")
        self.trace(self.repo, ["config", "-lz", "--show-origin", "--no-includes", "--show-scope", "--name-only"], ["status", "--porcelain"])
        self.say(self.GOOD)
        self.assertEqual(self.failed(self.NAME), [])

    def test_describing_the_working_copy_or_a_config_write_fails(self):
        self.build(self.NAME)
        self.jj("describe", "-m", "wip: greet experiment")
        self.trace(self.repo, ["config", "user.name", "x"])
        self.say(self.GOOD)
        self.assertEqual(sorted(self.failed(self.NAME)), ["The only Git commands were reads",
                                                         "The uncommitted edit to greet.py is untouched and nothing was committed"])

    def test_a_jj_commit_fails(self):
        self.build(self.NAME)
        self.jj("commit", "-m", "wip: greet experiment")
        fixtures.write(self.repo, "greet.py", json.loads((self.repo / ".git" / "fixture-state.json").read_text(encoding="utf-8"))["edited"])
        self.trace(self.repo, ["status", "--porcelain"])
        self.say(self.GOOD)
        self.assertIn("The uncommitted edit to greet.py is untouched and nothing was committed", self.failed(self.NAME))

    def test_a_silent_run_that_asks_nothing_fails(self):
        self.build(self.NAME)
        self.trace(self.repo, ["status", "--porcelain"])
        self.say("The cause is the missing comma in greet.py.")
        self.assertIn("The report shows the changed path greet.py and asks the user to set the edits aside or abort", self.failed(self.NAME))

    def test_a_fix_over_the_edit_fails(self):
        repo = self.build(self.NAME)
        self.trace(repo, ["status", "--porcelain"])
        (repo / "greet.py").write_text("def greet(name):\n    return 'x'\n", encoding="utf-8")
        self.say(self.GOOD)
        self.assertIn("The uncommitted edit to greet.py is untouched and nothing was committed", self.failed(self.NAME))


class DebugClean(Fx):
    NAME = "eval-debug-jj-clean"

    def fixed(self, report="Root cause: greet.py formatted the greeting without the comma and the exclamation mark. "
                           "Fixed test-first: test_greet_named now passes. Nothing committed."):
        repo = self.build(self.NAME)
        fixtures.write(repo, "greet.py", fixtures.GREET_OK)
        self.trace(repo, ["stash", "list"], ["status", "--porcelain"])
        self.say(report)
        return repo

    def test_diagnose_and_fix_without_asking_passes(self):
        self.fixed()
        self.assertEqual(self.failed(self.NAME), [])

    def test_a_jj_snapshot_of_the_fix_passes(self):
        self.fixed()
        self.jj("status")
        self.assertEqual(self.failed(self.NAME), [])

    def test_an_unnecessary_question_fails(self):
        self.fixed("greet.py misses the comma. Should I set your edits aside or abort before I continue? Fixed it anyway.")
        self.assertEqual(self.failed(self.NAME), ["The report does not ask the user to set edits aside, stash or abort"])

    def test_a_stash_fails(self):
        repo = self.fixed()
        self.trace(repo, ["stash", "push", "-u"])
        failed = self.failed(self.NAME)
        self.assertIn("No stash was made: no stash entry, no refs/stash and no git stash write in the trace", failed)
        self.assertIn("The only Git commands were reads", failed)

    def test_no_fix_fails(self):
        self.build(self.NAME)
        self.trace(self.repo, ["status", "--porcelain"])
        self.say("Root cause: greet.py misses the comma.")
        self.assertIn("The test suite passes", self.failed(self.NAME))

    def test_committing_fails(self):
        repo = self.fixed()
        git(repo, "commit", "-am", "fix: greet")
        self.assertIn("The fix is left uncommitted in greet.py, with no other file changed", self.failed(self.NAME))


class EvalsJson(unittest.TestCase):
    def test_every_new_eval_is_listed_with_the_graders_assertions(self):
        evals = {e["name"]: e for e in json.loads((HERE / "evals.json").read_text(encoding="utf-8"))["evals"]}
        ids = [e["id"] for e in evals.values()]
        self.assertEqual(sorted(ids), list(range(1, len(ids) + 1)), "ids are consecutive")
        for name in NAMES:
            self.assertIn(name, evals)
            self.assertTrue(evals[name]["prompt"] and evals[name]["expected_output"])
            self.assertTrue(evals[name]["skills"])

    def test_assertion_lists_match_the_grader_output(self):
        evals = {e["name"]: e for e in json.loads((HERE / "evals.json").read_text(encoding="utf-8"))["evals"]}
        for name in NAMES:
            if name not in ("eval-branch-git-jj-note", "eval-branch-store-probe-fails"):
                jjenv.require_jj()
            tmp = tempfile.mkdtemp(prefix="swe-")
            self.addCleanup(fixtures.rmtree, tmp)
            repo = Path(tmp) / "run" / "repo"
            repo.parent.mkdir()
            fixtures.build(name, repo)
            got = [t for t, _, _ in grade.check_vcs(name, repo, repo.parent)]
            self.assertEqual(sorted(got), sorted(evals[name]["assertions"]), name)

    def test_the_live_rows_are_unrun(self):
        # an eval that has not run is never green: no grading.json ships with the repo
        self.assertEqual(list(HERE.glob("**/grading.json")), [])


if __name__ == "__main__":
    unittest.main()
