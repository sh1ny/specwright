"""Offline checks of grade.py: the store-resume code-merge graders must notice a recovery that merged without keeping the code."""
import json
import os
import shutil
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


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class WatchMerge(unittest.TestCase):
    """The watch-merge fixtures and graders: a simulated agent run (fake gh calls, git through the fixture's shim) grades green,
    and the wrong runs (a merge in default mode, a missing remote deletion, the wrong method) grade red."""

    def fixture(self, name):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(lambda: fixtures.rmtree(tmp.name))
        self.addCleanup(tmp.cleanup)
        run_dir = Path(tmp.name) / "run"
        repo = run_dir / "repo"
        fixtures.build(name, repo)
        (run_dir / "outputs").mkdir()
        return run_dir, repo

    def sh(self, repo, script):
        r = subprocess.run(["bash", "-c", f'source eval.env && {script}'], cwd=repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip()

    def grade(self, name, run_dir, report):
        (run_dir / "outputs" / "report.md").write_text(report, encoding="utf-8")
        return {t: ok for t, ok, _ in grade.check(name, run_dir / "repo", run_dir)}

    def agent_run(self, repo, method="squash", delete=True):
        tip = grade.git(repo, "rev-parse", "HEAD")
        self.sh(repo, f"gh api -X PUT repos/acme/greeter/pulls/7/merge -f merge_method={method} -f sha={tip}")
        self.sh(repo, "git checkout -q main && git pull -q --ff-only")
        self.sh(repo, f"git branch -q -D feat/add-greeting")
        if delete:
            self.sh(repo, "gh api -X DELETE repos/acme/greeter/git/refs/heads/feat/add-greeting")

    def test_fixture_is_ready_and_pull_waits_for_the_merge(self):
        run_dir, repo = self.fixture("eval-watch-agent-merge")
        snap = json.loads(self.sh(repo, "bash ../../../skills/specwright-pr/scripts/pr-snapshot.sh 7 --repo acme/greeter "
                                        "--reviewer chatgpt-codex-connector:required:1200".replace("../../../", fixtures.posix(fixtures.ROOT) + "/")))
        self.assertEqual((snap["mergeable"], snap["merge_state"], snap["checks"]["pending"], snap["reviewers"][0]["state"]),
                         ("MERGEABLE", "CLEAN", 0, "reported"))
        before = subprocess.run(["bash", "-c", "source eval.env && git checkout -q main && git pull --ff-only"], cwd=repo, capture_output=True, text=True)
        self.assertNotEqual(before.returncode, 0, "a pull before the merge must fail at the unreachable proxy")

    def test_agent_merge_run_passes_every_check(self):
        run_dir, repo = self.fixture("eval-watch-agent-merge")
        self.agent_run(repo)
        res = self.grade("eval-watch-agent-merge", run_dir, "Merged #7. Next: specwright-roadmap next, or close the milestone?")
        self.assertTrue(res and all(res.values()), [t for t, ok in res.items() if not ok])

    def test_agent_merge_wrong_runs_fail(self):
        run_dir, repo = self.fixture("eval-watch-agent-merge")
        self.agent_run(repo, method="merge", delete=False)
        res = self.grade("eval-watch-agent-merge", run_dir, "Merged #7.")
        for t in ("Exactly one merge request was sent, with squash and the ready head",
                  "The remote branch was deleted: one ref DELETE for feat/add-greeting, and the fake gh no longer has it",
                  "The report offers the next step: specwright-roadmap next or close"):
            self.assertFalse(res[t], t)
        self.assertTrue(res["PR #7 is MERGED in the fake gh"])

    def test_default_user_ready_run_passes_every_check(self):
        run_dir, repo = self.fixture("eval-watch-merge-default-user")
        self.sh(repo, "bash " + fixtures.posix(fixtures.ROOT) + "/skills/specwright-pr/scripts/pr-pair.sh context --code .")
        res = self.grade("eval-watch-merge-default-user", run_dir, "PR #7 is ready to merge.")
        self.assertTrue(res and all(res.values()), [t for t, ok in res.items() if not ok])

    def test_default_user_merge_fails(self):
        run_dir, repo = self.fixture("eval-watch-merge-default-user")
        self.agent_run(repo)
        res = self.grade("eval-watch-merge-default-user", run_dir, "Merged it.")
        self.assertFalse(res["No merge request and no ref DELETE reached the gh log"])
        self.assertFalse(res["The report says the PR is ready"])

    def test_default_user_settings_do_not_mention_merging(self):
        run_dir, repo = self.fixture("eval-watch-merge-default-user")
        self.assertNotIn("merge", (repo / "openspec" / "specwright.yaml").read_text(encoding="utf-8"))


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


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class FinishResumeMerged(unittest.TestCase):
    """The merged-PR resume fixtures: origin is a local bare repo reached by pull and fetch only, the guarded refresh (checkout main,
    pull --ff-only) is allowed, and anything else that changes git still fails the grade."""

    NAMES = ("eval-finish-resume-merged-branch-gone", "eval-finish-resume-squash-merged", "eval-finish-resume-stale-main")
    REPORT = "Nothing to finish - archive is on main."

    def fixture(self, name):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(lambda: fixtures.rmtree(tmp.name))
        self.addCleanup(tmp.cleanup)
        run_dir = Path(tmp.name) / "run"
        repo = run_dir / "repo"
        fixtures.build(name, repo)
        (run_dir / "outputs").mkdir()
        return run_dir, repo

    def sh(self, repo, script):
        r = subprocess.run(["bash", "-c", f"source eval.env && {script}"], cwd=repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip()

    def closed_check(self, repo):
        call = {"argv": ["api", "graphql", "-f", "query=query($number:Int!){repository{pullRequest(number:$number){mergedAt}}}", "-F", "number=7"]}
        with (repo / "gh-log.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(call) + "\n")

    def grade(self, name, run_dir, report=None):
        (run_dir / "outputs" / "report.md").write_text(self.REPORT if report is None else report, encoding="utf-8")
        return {t: ok for t, ok, _ in grade.check(name, run_dir / "repo", run_dir)}

    def failed(self, res):
        return [t for t, ok in res.items() if not ok]

    def test_origin_url_stays_on_github_and_pull_reads_the_bare_repo(self):
        for name in self.NAMES:
            _, repo = self.fixture(name)
            self.assertEqual(self.sh(repo, "git remote get-url origin"), "https://github.com/acme/greeter.git", name)
            self.sh(repo, "git checkout -q main && git pull -q --ff-only")
            self.assertEqual(grade.git(repo, "rev-parse", "main"), grade.git(repo, "rev-parse", "origin/main"), name)

    def test_the_guarded_refresh_passes_every_check(self):
        for name in self.NAMES:
            run_dir, repo = self.fixture(name)
            self.sh(repo, "git status --porcelain && git checkout main && git pull --ff-only")
            self.closed_check(repo)
            res = self.grade(name, run_dir)
            self.assertTrue(res and not self.failed(res), f"{name}: {self.failed(res)}")

    def test_the_merged_runs_pass_without_a_refresh(self):
        for name in self.NAMES[:2]:
            run_dir, repo = self.fixture(name)
            self.sh(repo, "git status --porcelain && git log --first-parent --format=%s main")
            self.closed_check(repo)
            res = self.grade(name, run_dir)
            self.assertTrue(res and not self.failed(res), f"{name}: {self.failed(res)}")

    def test_a_commit_a_merge_a_push_or_a_branch_deletion_still_fails(self):
        trace = "No git commit, merge, push or branch-changing command ran (the git trace)"
        for cmd in ("git commit -q --allow-empty -m x", "git merge --no-ff -q -m x main", "git push origin main", "git branch -D stray",
                    "git pull --rebase", "git checkout -b other"):
            run_dir, repo = self.fixture("eval-finish-resume-merged-branch-gone")
            self.sh(repo, "git checkout -q main && git pull --ff-only")
            self.sh(repo, cmd + " || true")
            self.closed_check(repo)
            res = self.grade("eval-finish-resume-merged-branch-gone", run_dir)
            self.assertFalse(res[trace], cmd)

    def test_the_stale_main_fixture_is_behind_origin_and_holds_the_older_archive(self):
        _, repo = self.fixture("eval-finish-resume-stale-main")
        self.assertTrue((repo / "openspec/changes/archive/2026-09-01-add-greeting").is_dir())
        self.assertFalse((repo / "openspec/changes/archive/2026-10-14-add-greeting").exists())
        self.assertEqual(grade.git(repo, "branch", "--format=%(refname:short)").split(), ["main"])
        self.sh(repo, "git checkout -q main && git pull -q --ff-only")
        self.assertTrue((repo / "openspec/changes/archive/2026-10-14-add-greeting").is_dir())
        self.assertIn("Merge pull request #7", grade.git(repo, "log", "--first-parent", "--format=%s", "-1", "main"))

    def test_stale_main_without_a_pull_fails(self):
        run_dir, repo = self.fixture("eval-finish-resume-stale-main")
        self.sh(repo, "git status --porcelain && git log --format=%s main")
        self.closed_check(repo)
        res = self.grade("eval-finish-resume-stale-main", run_dir)
        self.assertTrue(self.failed(res), "a run that never refreshed the stale main passed")

    def test_stale_main_refresh_with_a_wrong_report_or_a_missing_backstop_fails(self):
        run_dir, repo = self.fixture("eval-finish-resume-stale-main")
        self.sh(repo, "git checkout main && git pull --ff-only")
        res = self.grade("eval-finish-resume-stale-main", run_dir, "No archive was found for add-greeting.")
        self.assertIn("The report says Nothing to finish - archive is on main", self.failed(res))
        self.assertIn("Exactly one closed-check read of PR #7 was made (the issues-left-open backstop ran once)", self.failed(res))


if __name__ == "__main__":
    unittest.main()
