"""`sw commit task-cover` and `sw commit fit-subject` entered directly (design D6, D7; the task-cover.sh and fit-subject.sh
shims are gone since 0.38.0).

The tests run the tree's sw through the test home (design D9): arguments reach it as given, the project's VERSION is
checked, and the project is chosen by `--code`, then `--repo`.

Run: python -m unittest evals/git-workflow/test_commit_shims.py
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "evals" / "vcs"))
import gitlog  # noqa: E402
import jjenv  # noqa: E402
import swcall  # noqa: E402  (vcs_test_support puts evals/ on sys.path)
from vcs_test_support import STAMP, VcsTestCase, sw_run, stamp_version  # noqa: E402

CHANGE = "a"
TASKS = "# Tasks\n\n## 1. Group\n\n- [x] 1.1 Add it\n"
LONG = "feat(a): task 1.1 " + "Add the thing and then more words to pass the limit of subject " + "x" * 9  # 90 characters


class ShimCase(VcsTestCase):
    def setUp(self):
        super().setUp()
        self.shim = gitlog.install(self.root / "gitshim", real_git=jjenv.real_git(), log_path=self.root / "git.jsonl")

    def run_sw(self, name, *args, cwd=None, env=None):
        """`sw commit <name> <args>` entered directly (evals/swcall.py), name being `task-cover` or `fit-subject`."""
        return sw_run(["commit", name, *args], cwd=cwd or self.repo, env=env, shim=self.shim, stamp=False)

    def branch_commit(self, subject, repo=None):
        repo = repo or self.repo
        self.git(repo, "checkout", "-b", "feat/a")
        (repo / "f.txt").write_text("f\n", encoding="utf-8")
        self.git(repo, "add", "f.txt")
        self.assertEqual(self.git(repo, "commit", "-m", subject).returncode, 0)

    def tasks_file(self, where=None):
        p = Path(where or self.root) / "tasks.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(TASKS.encode("utf-8"))
        return p

    def cover_args(self, repo=None, tasks=None, code=None):
        args = []
        if code is not None:
            args += ["--code", code]
        return args + ["--repo", repo or self.repo, "--range", "main..feat/a", "--tasks", tasks or self.tasks_file(),
                       "--change", CHANGE]

    def message(self, text, name="msg.txt"):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
        return p

    def mismatch_document(self, result):
        """The native refusal when the project's VERSION is missing or another version: `sw_mismatch`, exit 1, no git."""
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_mismatch"), doc)
        self.assertEqual(self.shim.calls(), [], "no git command ran")
        return doc

class TestTaskCoverShim(ShimCase):
    def test_task_cover_runs_sw(self):
        self.branch_commit("feat(a): task 1.1 Add it")
        result = self.run_sw("task-cover", *self.cover_args())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertTrue(doc["ok"], doc)
        self.assertEqual([(c["form"]) for c in doc["tasks"][0]["commits"]], ["subject"], doc)
        self.assertEqual(doc["tasks"][0]["id"], "1.1")

    def test_code_picks_the_project(self):
        store = self.root / "store"
        self._init_git(store)
        self.branch_commit("feat(a): task 1.1 Add it", repo=store)
        tasks = self.tasks_file(store / "openspec" / "changes" / CHANGE)
        self.assertFalse((store / STAMP).exists())
        result = self.run_sw("task-cover", *self.cover_args(repo=store, tasks=tasks, code=self.repo), cwd=store)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual([c["form"] for c in doc["tasks"][0]["commits"]], ["subject"], doc)
        # --code changes nothing in the document: the same call from a stamped store, without --code
        stamp_version(store)
        plain = self.run_sw("task-cover", *self.cover_args(repo=store, tasks=tasks), cwd=store)
        self.assertEqual(plain.stdout, result.stdout)

    def test_another_version_is_sw_mismatch(self):
        self.branch_commit("feat(a): task 1.1 Add it")
        self.shim.log_path.unlink(missing_ok=True)
        swcall.stamp(self.repo, "99.0.0")
        doc = self.mismatch_document(self.run_sw("task-cover", *self.cover_args()))
        self.assertIn("99.0.0", doc["message"])
        swcall.stamp(self.repo)
        again = self.run_sw("task-cover", *self.cover_args())  # the control: the matching VERSION runs
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)

    def test_store_without_code_is_sw_mismatch(self):
        store = self.root / "store"
        self._init_git(store)
        self.branch_commit("feat(a): task 1.1 Add it", repo=store)
        tasks = self.tasks_file(store / "openspec" / "changes" / CHANGE)
        self.shim.log_path.unlink(missing_ok=True)
        result = self.run_sw("task-cover", *self.cover_args(repo=store, tasks=tasks), cwd=store)
        doc = self.mismatch_document(result)
        self.assertIn("no installed version found", doc["message"])

class TestFitSubjectShim(ShimCase):
    def test_fit_subject_runs_sw(self):
        self.assertEqual(len(LONG), 90)
        data = LONG + "\n\nBody.\n"
        msg = self.message(data)
        result = self.run_sw("fit-subject", msg)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        fitted = result.stdout.rstrip("\n")
        self.assertLessEqual(len(fitted), 72)
        self.assertTrue(LONG.startswith(fitted) and LONG[len(fitted)] == " ", fitted)
        self.assertEqual(msg.read_bytes().decode("utf-8"), fitted + "\n\nBody.\n")

    def test_fit_subject_path_with_space_and_dollar(self):
        msg = self.message(LONG + "\n\nBody.\n", name="dir with space/msg $1.txt")
        result = self.run_sw("fit-subject", msg)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        fitted = result.stdout.rstrip("\n")
        self.assertLessEqual(len(fitted), 72)
        self.assertEqual(msg.read_bytes().decode("utf-8"), fitted + "\n\nBody.\n")

if __name__ == "__main__":
    unittest.main()
