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


class ChangingCommands(unittest.TestCase):
    """The finish-resume graders' "nothing changed" checks must see every git branch change and every GitHub write."""

    def test_positional_checkout_and_switch_are_changes(self):
        for c in (["checkout", "main"], ["checkout", "HEAD~1"], ["checkout", "--", "a.txt"], ["switch", "main"],
                  ["checkout", "-q", "main"], ["checkout", "-b", "x"], ["switch", "-c", "x"], ["switch", "--detach", "HEAD"]):
            self.assertEqual(grade.changing_git([c]), [c], c)
        for c in (["status"], ["log", "--oneline"], ["branch", "--show-current"], ["checkout"], ["switch"]):
            self.assertEqual(grade.changing_git([c]), [], c)

    def test_graphql_mutation_is_a_change(self):
        q = lambda body: {"argv": ["api", "graphql", "-f", "threadId=T", "-f", "query=" + body]}
        for body in ("mutation($threadId:ID!){ resolveReviewThread(input:{threadId:$threadId}){ thread{ id } } }",
                     "\n    mutation { addReaction(input:{subjectId:\"X\",content:THUMBS_UP}){ reaction{ content } } }"):
            self.assertEqual(len(grade.changing_gh([q(body)])), 1, body)
        read = q("query($owner:String!){ repository(owner:$owner){ pullRequest(number:7){ mergedAt } } }")
        self.assertEqual(grade.changing_gh([read]), [], "a GraphQL read is not a change")
        self.assertEqual(grade.changing_gh([{"argv": ["api", "graphql", "-f", "query={ viewer { login } }"]}]), [])

    def test_unclassifiable_graphql_is_a_change(self):
        """A query read from a file or --input cannot be judged from argv, so it counts as a possible write; so does a
        mutation behind a `#` comment or passed in an attached -fquery=/--field=query= form."""
        m = "mutation { resolveReviewThread(input:{threadId:\"T\"}){ thread{ id } } }"
        for argv in (["api", "graphql", "-F", "query=@q.graphql"], ["api", "graphql", "--input", "q.json"],
                     ["api", "graphql", "--input=q.json"], ["api", "graphql", "-Fquery=@q.graphql"],
                     ["api", "graphql", "-fquery=" + m], ["api", "graphql", "--field=query=" + m],
                     ["api", "graphql", "--raw-field=query=" + m], ["api", "graphql", "-f", "query=# resolve\n" + m]):
            self.assertEqual(len(grade.changing_gh([{"argv": argv}])), 1, argv)
        self.assertEqual(grade.changing_gh([{"argv": ["api", "graphql", "-fquery={ viewer { login } }"]}]), [])

    def test_branch_format_is_a_read(self):
        for c in (["branch", "--format", "%(refname:short)"], ["branch", "--format=%(refname:short)"],
                  ["branch", "-a", "--format", "%(refname:short) %(upstream)"]):
            self.assertEqual(grade.changing_git([c]), [], c)
        for c in (["branch", "--format", "%(refname)", "new"], ["branch", "new"]):
            self.assertEqual(grade.changing_git([c]), [c], c)

    def test_git_pull_is_a_change(self):
        for c in (["pull"], ["pull", "--ff-only"], ["pull", "--rebase", "origin", "main"]):
            self.assertEqual(grade.changing_git([c]), [c], c)
        self.assertEqual(grade.changing_git([["fetch", "origin"]]), [], "a fetch changes no branch")

    def test_explicit_get_with_fields_is_a_read(self):
        for argv in (["api", "--method", "GET", "search/issues", "-f", "q=repo:o/n"], ["api", "-X", "GET", "search/issues", "-f", "q=x"],
                     ["api", "-XGET", "search/issues", "-f", "q=x"], ["api", "--method=get", "search/issues", "-F", "q=x"],
                     ["api", "repos/o/n/pulls/7"], ["api", "repos/acme/greeter-Xcode/pulls/7"],
                     ["api", "repos/o/n/pulls?head=o:fix-Xmethod"]):
            self.assertEqual(grade.changing_gh([{"argv": argv}]), [], argv)
        for argv in (["api", "repos/o/n/issues/7/comments", "-f", "body=x"], ["api", "-X", "PATCH", "repos/o/n/pulls/7"],
                     ["api", "--method", "POST", "repos/o/n/issues/7/reactions", "-f", "content=+1"],
                     ["api", "repos/o/n/issues/7/comments", "--input", "b.json"]):
            self.assertEqual(len(grade.changing_gh([{"argv": argv}])), 1, argv)


if __name__ == "__main__":
    unittest.main()
