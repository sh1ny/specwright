"""finish.sh against its frozen oracle on a GitButler repo (real `but`), native-cli-finish D9.

The oracle (evals/finish/oracle/finish.sh) is the last finish.sh before the port to `sw`; both plan the same committed and
uncommitted archives and must print the same stdout bytes with the same exit code. The printed script still calls vcs.sh by its
absolute path and names no `sw` binary. This module runs in the `vcs` suite job, the only one that installs `but`.
"""
import importlib.util
import json
import subprocess
from pathlib import Path

import jjenv
from butenv import Scratch, require_but
from test_gitbutler_flows import BRANCH, CHANGE, GitButlerFlowCase
from vcs_test_support import stamp_version, sw_home

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("finish_fixtures", ROOT / "evals" / "finish" / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

P = "openspec"
ARCHIVED = "%s-%s" % (fx.DATE, CHANGE)
ARCHIVE_DIR = "%s/changes/archive/%s" % (P, ARCHIVED)
CHANGE_DIR = "%s/changes/%s" % (P, CHANGE)


def compact_guard(doc):
    """The oracle's document with its printed branch guard in sw's form: the one listed difference (C13).

    The guard reads the `vcs.sh state` document by text, and sw prints that document compact, so sw's guard matches
    `"branch":"<name>"` where the oracle's matched `"branch": "<name>"`."""
    if isinstance(doc.get("script"), str):
        doc = dict(doc, script=doc["script"].replace("'\"branch\": \"", "'\"branch\":\""))
    return doc


def without_undo(doc):
    """The document without the undo itself: the oracle prints a `script`, sw prints `steps`. test_gitbutler_undo_steps_commit_
    paths_to_branch checks the outcome; task 7.2 of native-cli-retire-scripts migrates this file. The warnings name the
    commit command the plan now prints, `sw vcs commit`, where the oracle named `vcs.sh commit`."""
    out = {k: v for k, v in doc.items() if k not in ("script", "steps") and not k.startswith("after_rerun")}
    if isinstance(out.get("warnings"), list):
        out["warnings"] = [w.replace("`vcs.sh commit`", "`sw vcs commit`") if isinstance(w, str) else w
                           for w in out["warnings"]]
    return out


class TestGitButlerParity(GitButlerFlowCase):
    def commit_paths(self, scratch, wrap, subject, *paths):
        result = self.commit(scratch, wrap, subject + "\n", *paths)
        self.assertTrue(result["ok"], result)
        return result["commit"]

    def planned(self, scratch, wrap, repo):
        """finish.sh and the oracle plan the same archive the same way; returns (new, old) as (exit code, stdout bytes, stderr bytes)."""
        args = fx.plan_args(CHANGE, archived=ARCHIVED, branch=BRANCH)
        results = []
        for script, extra in ((fx.SCRIPT, {}), (fx.ORACLE, {"ORACLE_FIN_DIR": str(fx.ORACLE_FIN_DIR)})):
            env = self.fenced_env(scratch, wrap)
            env.update({"SPECWRIGHT_STATE_DIR": str(self.root / "state"), "PYTHONIOENCODING": "utf-8",
                        "SPECWRIGHT_HOME": str(sw_home()), **extra})
            stamp_version(repo.path)
            env["VCS_TEST_SEARCH"] = env["PATH"]
            done = subprocess.run([jjenv.find_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"', "parity",
                                   script.as_posix(), *args], cwd=str(repo.path), env=env, capture_output=True)
            results.append((done.returncode, done.stdout, done.stderr))
        return results

    def assertParity(self, pair):
        new, old = pair
        self.assertEqual(old[0], 0, old[1] + old[2])
        # sw writes compact JSON, the oracle spaced: documents are equal by value, not by bytes (non-UTF-8 name bytes survive)
        self.assertEqual(without_undo(json.loads(new[1].decode("utf-8", "surrogateescape"))),
                         without_undo(json.loads(old[1].decode("utf-8", "surrogateescape"))),
                         "stdout documents differ between finish.sh and the oracle")
        self.assertEqual(new[0], old[0], "exit codes differ between finish.sh and the oracle")
        return json.loads(old[1].decode("utf-8"))

    def archived(self, scratch, committed):
        """feat/b beside the change branch; the change branch holds the planning commit and the archive, committed or not."""
        wrap, repo = self.start(scratch)
        self.other_agent(repo, wrap)
        repo.but("branch", "new", BRANCH)
        work = repo.path
        fx.write(work, "%s/specs/a/spec.md" % P, fx.base_spec("a"))
        fx.make_change(work, CHANGE, "DEFERRED", {"a": "New thing", "b": "B thing"}, commit_it=False)
        for rel in ("notes/z.md", "notes/deep/a/leaf.md", "notes/deep/b/leaf.md"):  # nested folders: walk order
            fx.write(work, "%s/%s" % (CHANGE_DIR, rel), rel + "\n")
        self.commit_paths(scratch, wrap, "docs(add-c): add planning artifacts", "%s/specs/a/spec.md" % P, CHANGE_DIR + "/")
        fx.archive(work, CHANGE, commit_it=False)
        if committed:
            self.commit_paths(scratch, wrap, "chore(add-c): archive change", ARCHIVE_DIR + "/", CHANGE_DIR + "/",
                              "%s/specs/a/spec.md" % P, "%s/specs/b/spec.md" % P)
        return wrap, repo

    def step_env(self, scratch, wrap, repo):
        env = self.fenced_env(scratch, wrap)
        env.update({"SPECWRIGHT_STATE_DIR": str(self.root / "state"), "PYTHONIOENCODING": "utf-8",
                    "SPECWRIGHT_HOME": str(sw_home())})
        stamp_version(repo.path)
        env["VCS_TEST_SEARCH"] = env["PATH"]
        return env

    def run_step(self, step, env):
        """One printed `{cwd, argv}` step in its own cwd, through bash so the fixture's PATH finds git and but."""
        return subprocess.run([jjenv.find_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$@"', "step", *step["argv"]],
                              cwd=step["cwd"], env=env, capture_output=True, text=True, encoding="utf-8")

    def test_gitbutler_undo_steps_commit_paths_to_branch(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.archived(scratch, True)
            env = self.step_env(scratch, wrap, repo)
            plan = subprocess.run([jjenv.find_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"', "plan",
                                   fx.SCRIPT.as_posix(), *fx.plan_args(CHANGE, archived=ARCHIVED, branch=BRANCH)],
                                  cwd=str(repo.path), env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(plan.returncode, 0, plan.stdout + plan.stderr)
            doc = json.loads(plan.stdout)
            self.assertNotIn("script", doc)
            other_tip = repo.git_run("rev-parse", "refs/heads/feat/b").stdout.strip()
            before = repo.git_run("rev-parse", "refs/heads/" + BRANCH).stdout.strip()
            for step in doc["steps"]:
                done = self.run_step(step, env)
                self.assertEqual(done.returncode, 0, "%s%s%s" % (step["argv"], done.stdout, done.stderr))
            tip = repo.git_run("rev-parse", "refs/heads/" + BRANCH).stdout.strip()
            self.assertNotEqual(tip, before, "no commit reached the change branch")
            self.assertEqual(repo.git_run("log", "-1", "--format=%s", tip).stdout.strip(), "feat(add-c): undo archive of add-c")
            touched = set(repo.git_run("diff-tree", "-r", "--no-commit-id", "--name-only", tip).stdout.split())
            self.assertIn("%s/review.md" % CHANGE_DIR, touched)
            self.assertTrue(any(t.startswith(ARCHIVE_DIR + "/") for t in touched), touched)
            for path in touched:
                self.assertTrue(path.startswith((CHANGE_DIR + "/", ARCHIVE_DIR + "/", P + "/specs/")), path)
            self.assertEqual(repo.git_run("rev-parse", "refs/heads/feat/b").stdout.strip(), other_tip, "feat/b moved")
            self.assertTrue((repo.path / CHANGE_DIR / "review.md").is_file())
            self.assertFalse((repo.path / ARCHIVE_DIR).exists())

    def test_committed_archive_output_equals_oracle(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.archived(scratch, True)
            doc = self.assertParity(self.planned(scratch, wrap, repo))
            self.assertEqual(doc["mode"], "committed")

    def test_uncommitted_archive_output_equals_oracle(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.archived(scratch, False)
            doc = self.assertParity(self.planned(scratch, wrap, repo))
            self.assertEqual(doc["mode"], "uncommitted")

    def test_script_calls_vcs_sh_by_path(self):
        # task 7.2 of native-cli-retire-scripts renames this: the plan calls `sw vcs`, not vcs.sh, and names no bash
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.archived(scratch, True)
            new, old = self.planned(scratch, wrap, repo)
            self.assertParity((new, old))
            doc = json.loads(new[1].decode("utf-8"))
            self.assertNotIn("script", doc)
            commits = [s["argv"] for s in doc["steps"] if s["argv"][3:5] == ["vcs", "commit"]]
            self.assertEqual(len(commits), 1, doc["steps"])
            self.assertEqual(Path(commits[0][2]).resolve(), repo.path.resolve())
            self.assertEqual(commits[0][1], "--project")
            self.assertIn("--", commits[0])
            self.assertTrue(any(s["argv"][3:6] == ["finish", "undo-step", "check"] and s["argv"][6] == "branch"
                                for s in doc["steps"]), "the branch guard is an undo-step check")
            for step in doc["steps"]:
                for word in step["argv"]:
                    self.assertNotIn("vcs.sh", word)
                    self.assertNotEqual(Path(word).stem, "bash")
