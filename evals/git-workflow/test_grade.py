"""Offline checks of grade.py: the store-resume code-merge graders must notice a recovery that merged without keeping the code."""
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixtures  # noqa: E402
import grade  # noqa: E402

TREE_CHECK = "The code repo's main tree equals the code branch's tip tree, so the merge kept the code"
EVALS = ("eval-store-finish-resume-code-merge", "eval-store-finish-resume-code-merge-from-main")


def run(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


class ResumeCodeMergeTree(unittest.TestCase):
    def recovered(self, name, merge_args):
        """The fixture of eval `name` after a recovery that merged feat/add-greeting into the code main with `merge_args`."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo"
        fixtures.build(name, repo)
        code = repo / "code"
        run(code, "checkout", "-q", "main")
        run(code, "-c", "user.name=t", "-c", "user.email=t@example.com", "merge", "--no-ff", *merge_args, "-m", "merge: add-greeting",
            "feat/add-greeting")
        run(code, "branch", "-D", "feat/add-greeting")
        return repo

    def results(self, name, repo):
        res = grade.check_store_finish(name, repo, repo / "code", repo / "store", "")
        return {text: (ok, ev) for text, ok, ev in res}

    def test_fixture_records_the_code_branch_tip_tree(self):
        for name in EVALS:
            with tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp) / "repo"
                fixtures.build(name, repo)
                tree = grade.git(repo / "code", "rev-parse", "feat/add-greeting^{tree}")
                self.assertEqual(grade.json.loads((repo / "fixture-state.json").read_text(encoding="utf-8")).get("code_tree"), tree, name)

    def test_a_merge_that_discards_the_code_fails(self):
        for name in EVALS:
            repo = self.recovered(name, ["-s", "ours"])
            res = self.results(name, repo)
            self.assertIn(TREE_CHECK, res, name)
            self.assertFalse(res[TREE_CHECK][0], f"{name}: a `-s ours` merge kept no code but passed: {res[TREE_CHECK][1]}")
            self.assertTrue(res["The code repo's main HEAD is a merge commit with two parents and subject merge: add-greeting"][0],
                            "the discarding merge must look right to the old checks, or the test proves nothing")

    def test_a_real_merge_passes(self):
        for name in EVALS:
            repo = self.recovered(name, [])
            res = self.results(name, repo)
            self.assertIn(TREE_CHECK, res, name)
            self.assertTrue(res[TREE_CHECK][0], f"{name}: {res[TREE_CHECK][1]}")


class Rmtree(unittest.TestCase):
    def test_rmtree_removes_read_only_files(self):
        # git marks its objects read-only; on Windows shutil.rmtree(ignore_errors=True) leaves them, and the test dir, in TEMP
        d = Path(tempfile.mkdtemp())
        f = d / "objects" / "ab" / "cdef"
        f.parent.mkdir(parents=True)
        f.write_text("blob", encoding="utf-8")
        os.chmod(f, stat.S_IREAD)  # the file only: its directory stays writable, as git leaves it
        fixtures.rmtree(d)
        self.assertFalse(d.exists())


if __name__ == "__main__":
    unittest.main()
