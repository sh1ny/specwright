"""Offline checks of grade.py: the store-resume code-merge graders must notice a recovery that merged without keeping the code."""
import json
import os
import re
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
        res = self.grade("eval-watch-agent-merge", run_dir, "Merged #7. Run specwright-roadmap close for M2?")
        self.assertTrue(res and all(res.values()), [t for t, ok in res.items() if not ok])

    def test_agent_merge_wrong_runs_fail(self):
        run_dir, repo = self.fixture("eval-watch-agent-merge")
        self.agent_run(repo, method="merge", delete=False)
        res = self.grade("eval-watch-agent-merge", run_dir, "Merged #7.")
        for t in ("Exactly one merge request was sent, with squash and the ready head",
                  "The remote branch was deleted: one ref DELETE for feat/add-greeting, and the fake gh no longer has it",
                  "The report offers the prescribed next step: specwright-roadmap close"):
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


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class RoadmapOffer(unittest.TestCase):
    """roadmap_offer and the agent-merge next-step check: the mode offered is the word bound to specwright-roadmap, and the check
    passes only when that set is exactly the mode the fixture's milestone state prescribes."""

    CLOSE, NEXT = "eval-watch-agent-merge", "eval-agent-merge-release-auto"
    PREFIX = "The report offers the prescribed next step: specwright-roadmap "

    def graded(self, name, report):
        """(ok, evidence) of the next-step assertion for `report` on the fixture of eval `name` (no agent run needed)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(lambda: fixtures.rmtree(tmp.name))
        self.addCleanup(tmp.cleanup)
        run_dir = Path(tmp.name) / "run"
        fixtures.build(name, run_dir / "repo")
        (run_dir / "outputs").mkdir()
        (run_dir / "outputs" / "report.md").write_text(report, encoding="utf-8")
        res = [(ok, ev) for t, ok, ev in grade.check(name, run_dir / "repo", run_dir) if t.startswith(self.PREFIX)]
        self.assertEqual(len(res), 1, res)
        return res[0]

    def test_fixture_records_the_expected_mode(self):
        for name, mode in ((self.CLOSE, "close"), (self.NEXT, "next")):
            with tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp) / "repo"
                fixtures.build(name, repo)
                fx = json.loads((repo / ".git" / "fixture-state.json").read_text(encoding="utf-8"))
                self.assertEqual(fx.get("expected_mode"), mode, name)
                self.assertIn("project:\n  roadmap: openspec/roadmap.md\n", (repo / "openspec" / "specwright.yaml").read_text(encoding="utf-8"))
                rm = (repo / "openspec" / "roadmap.md").read_text(encoding="utf-8")
                self.assertEqual("add-shout" in rm, mode == "next", name)
            fixtures.rmtree(tmp)

    def test_default_user_variant_has_no_roadmap(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            fixtures.build("eval-watch-merge-default-user", repo)
            self.assertFalse((repo / "openspec" / "roadmap.md").exists())
            self.assertNotIn("expected_mode", json.loads((repo / ".git" / "fixture-state.json").read_text(encoding="utf-8")))
        fixtures.rmtree(tmp)

    def test_prescribed_mode_passes(self):
        ok, ev = self.graded(self.CLOSE, "Merged #7. Run specwright-roadmap close for M2?")
        self.assertTrue(ok, ev)
        ok, ev = self.graded(self.NEXT, "Merged #7.\n\nRun `specwright-roadmap next` for M2?")
        self.assertTrue(ok, ev)

    def test_mode_bound_to_command(self):
        self.assertEqual(grade.roadmap_offer("Next step: run specwright-roadmap close for M2?"), {"close"})
        ok, ev = self.graded(self.CLOSE, "Next step: run specwright-roadmap close for M2?")
        self.assertTrue(ok, ev)

    def test_bulleted_offer_with_the_question_above(self):
        rep = "Merged. What next?\n- run specwright-roadmap close for M2"
        self.assertEqual(grade.roadmap_offer(rep), {"close"})
        self.assertEqual(grade.roadmap_offer("Shall I go on?\n\n- specwright-roadmap close"), set())  # the question is in another block
        self.assertEqual(grade.roadmap_offer("- **specwright-roadmap**: `close`?"), {"close"})

    def test_explaining_sentence_offers_nothing(self):
        rep = "Merged #7. M2 has no planned change left, so specwright-roadmap next does not apply. Run specwright-roadmap close for M2?"
        self.assertEqual(grade.roadmap_offer(rep), {"close"})
        rep = "Merged #7; specwright-roadmap next does not apply. What now?\n- run specwright-roadmap close for M2"
        self.assertEqual(grade.roadmap_offer(rep), {"close"})

    def test_negated_question_offers_nothing(self):
        self.assertEqual(grade.roadmap_offer("I will not run specwright-roadmap next; should I stop?"), set())
        self.assertEqual(grade.roadmap_offer("specwright-roadmap next doesn't apply. Run specwright-roadmap close for M2?"), {"close"})

    def test_incidental_negation_keeps_the_offer(self):
        # a negation in another clause of the sentence does not rule the mode out
        self.assertEqual(grade.roadmap_offer("I didn't create anything; should I run specwright-roadmap close?"), {"close"})
        self.assertEqual(grade.roadmap_offer("Nothing was not merged: run specwright-roadmap next for M3?"), {"next"})
        self.assertEqual(grade.roadmap_offer("I didn't tag anything, so shall I run specwright-roadmap close?"), {"close"})
        # the clause that names the mode rules it out
        self.assertEqual(grade.roadmap_offer("Should I stop? I will not run specwright-roadmap next; the milestone is done?"), set())

    def test_stated_mode_with_question_after_it_is_offered(self):
        rep = "Next step: `specwright-roadmap close` for M2 (run login: eval-bot). Shall I run it?"
        self.assertEqual(grade.roadmap_offer(rep), {"close"})
        rep = "Merged #7.\n\nNext: specwright-roadmap next for M3. Want me to run it?"
        self.assertEqual(grade.roadmap_offer(rep), {"next"})
        rep = "Next: specwright-roadmap close.\n\nAnything else?"  # the question is in another block
        self.assertEqual(grade.roadmap_offer(rep), set())

    def test_named_but_not_offered_fails(self):
        rep = "There is no roadmap step to run next; close the PR tab when done"
        self.assertEqual(grade.roadmap_offer(rep), set())
        ok, ev = self.graded(self.CLOSE, rep)
        self.assertFalse(ok)

    def test_both_modes_fail(self):
        ok, ev = self.graded(self.NEXT, "Run specwright-roadmap next or close?")
        self.assertFalse(ok)
        self.assertIn("expected next", ev)
        self.assertIn("offered ['close', 'next']", ev)
        for rep in ("Run specwright-roadmap next or close?", "Run specwright-roadmap: next/close?",
                    "Run specwright-roadmap next, or close?", "Run specwright-roadmap **next** and **close**?", "roadmap `next` or `close`?"):
            self.assertEqual(grade.roadmap_offer(rep), {"next", "close"}, rep)

    def test_wrong_mode_fails(self):
        ok, ev = self.graded(self.CLOSE, "Run specwright-roadmap next?")
        self.assertFalse(ok)
        self.assertIn("expected close", ev)
        ok, ev = self.graded(self.NEXT, "Run specwright-roadmap close?")
        self.assertFalse(ok)
        self.assertIn("expected next", ev)

    def test_offers_close_only_when_a_connector_is_followed_by_prose(self):
        rep = "Run specwright-roadmap close, and I'll pick up the next change after M3 is planned?"
        self.assertEqual(grade.roadmap_offer(rep), {"close"})

    def test_offers_nothing(self):
        self.assertEqual(grade.roadmap_offer("the Next milestone (M3)"), set())
        self.assertEqual(grade.roadmap_offer("Is the Next milestone (M3) ready for the roadmap?"), set())

    def test_mode_in_emphasis_after_the_backticked_command_is_bound(self):
        rep = "Next step: M2 is done. Shall I run `specwright-roadmap` **close** for M2 (run login: eval-bot)?"
        self.assertEqual(grade.roadmap_offer(rep), {"close"})
        self.assertEqual(grade.roadmap_offer("Shall I run __specwright-roadmap__ _next_ for M3?"), {"next"})

    def test_mode_after_a_sentence_end_is_not_bound(self):
        self.assertEqual(grade.roadmap_offer("Merged per the roadmap. Next, run specwright-roadmap close for M2?"), {"close"})


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
        self.assertEqual(grade.changing_git([["fetch", "origin"]]), [["fetch", "origin"]], "a default-refspec fetch follows tags into refs/tags/")
        self.assertEqual(grade.changing_git([["fetch", "--no-tags", "origin"]]), [], "a fetch that stores no ref changes nothing")

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


class GhAllowlist(unittest.TestCase):
    """gh_writes counts every gh call as a write unless it is on the read-only allowlist (design D2)."""

    def writes(self, *lines):
        for line in lines:
            argv = line.split()
            self.assertEqual(grade.gh_writes([{"argv": argv}]), [line], line)
            self.assertEqual(grade.changing_gh([{"argv": argv}]), [line], line)

    def reads(self, *argvs):
        for argv in argvs:
            argv = argv.split() if isinstance(argv, str) else argv
            self.assertEqual(grade.gh_writes([{"argv": argv}]), [], argv)

    def test_listed_issue_and_pr_writes(self):
        self.writes("issue lock 3", "issue delete 3", "issue unlock 3", "issue pin 3", "issue unpin 3", "issue transfer 3 o/other",
                    "pr lock 7", "pr unlock 7", "pr revert 7", "pr update-branch 7")

    def test_graphql_without_a_readable_query_is_a_write(self):
        mut = "mutation { addReaction(input:{subjectId:\"X\",content:THUMBS_UP}){ reaction{ content } } }"
        for argv in (["api", "graphql", "-f=query=" + mut], ["api", "graphql", "-F=query=" + mut],  # the equals-attached spellings
                     ["api", "graphql"], ["api", "graphql", "-f", "q=" + mut]):  # no query gh would send as one: never a read
            self.assertEqual(grade.gh_writes([{"argv": argv}]), [" ".join(argv)], argv)
        self.reads(["api", "graphql", "-f=query={ viewer { login } }"], ["api", "graphql", "-F=query=query { viewer { login } }"])

    def test_graphql_mutation_without_method_in_pr_mutations(self):
        mut = "mutation { addReaction(input:{subjectId:\"X\",content:THUMBS_UP}){ reaction{ content } } }"
        read = "query { viewer { login } }"
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            log = [{"argv": ["api", "graphql", "-f", "query=" + mut]}, {"argv": ["api", "graphql", "-f", "query=" + read]},
                   {"argv": ["pr", "view", "7"]}]
            (repo / "gh-log.jsonl").write_text("".join(json.dumps(c) + "\n" for c in log), encoding="utf-8")
            self.assertEqual(grade.pr_mutations(repo), ["api graphql -f query=" + mut])
            self.assertEqual(grade.pr_mutations(repo), grade.gh_writes(grade.gh_calls(repo)))

    def test_graphql_mutation_sent_as_get_is_a_write(self):
        mut = "mutation($threadId:ID!){ resolveReviewThread(input:{threadId:$threadId}){ thread{ id } } }"
        for argv in (["api", "-X", "GET", "graphql", "-f", "query=" + mut, "-f", "threadId=T"],
                     ["api", "--method=GET", "/graphql", "-f", "query=" + mut, "-f", "threadId=T"]):
            self.assertEqual(grade.gh_writes([{"argv": argv}]), [" ".join(argv)], argv)
            self.assertEqual(grade.changing_gh([{"argv": argv}]), [" ".join(argv)], argv)
            with tempfile.TemporaryDirectory() as tmp:  # the pr_mutations check reads the same log
                repo = Path(tmp)
                (repo / "gh-log.jsonl").write_text(json.dumps({"argv": argv}) + "\n", encoding="utf-8")
                self.assertEqual(grade.pr_mutations(repo), [" ".join(argv)], argv)

    def test_graphql_read_with_options_before_the_endpoint(self):
        self.reads(["api", "--paginate", "graphql", "-f", "query={ viewer { login } }"],
                   ["api", "--hostname", "github.com", "/graphql", "-f", "query=query { viewer { login } }"])

    def test_graphql_input_after_get_is_a_write(self):
        self.writes("api -X GET graphql --input q.json")

    def test_unknown_subcommand_is_a_write(self):
        self.writes("label create x", "auth switch", "release create v1", "release delete v1", "repo delete o/n", "gist create f", "frobnicate")
        self.assertEqual(grade.gh_writes([{"argv": []}]), [""], "an empty call is not known to be a read")

    def test_reads_stay_reads(self):
        self.reads("pr view 7 --json state", "pr checks 7", "pr list", "pr diff 7", "pr status", "issue view 3", "issue list", "issue status",
                   "repo view", "release view v1", "release list", "auth status", "auth token", "search issues x",
                   "api repos/o/n/pulls/7", "pr view 7 -R o/n", "pr view 7 --repo=o/n",
                   ["api", "--method", "GET", "search/issues", "-f", "q=x"],
                   ["api", "-X", "POST", "markdown", "--input", "req.json"], ["api", "-X", "POST", "markdown/raw", "--input", "req.md"],
                   ["api", "graphql", "-f", "query={ viewer { login } }"])
        self.writes("api -X PATCH markdown", "api -X POST repos/o/n/issues/7/comments", "api graphql --input q.json",
                    "api -X POST repos/o/n/issues --input markdown", "api -X POST repos/o/n/labels -f name=x markdown/raw")


class ExpectedWrites(unittest.TestCase):
    """An eval whose correct run writes subtracts exactly the writes it expects: the release-auto evals expect one release create."""

    def fixture(self, name, log):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(lambda: fixtures.rmtree(tmp.name))
        self.addCleanup(tmp.cleanup)
        run_dir = Path(tmp.name) / "run"
        repo = run_dir / "repo"
        fixtures.build(name, repo)
        (run_dir / "outputs").mkdir()
        (run_dir / "outputs" / "report.md").write_text("", encoding="utf-8")
        with (repo / "gh-log.jsonl").open("a", encoding="utf-8") as f:
            for argv in log:
                f.write(json.dumps({"argv": argv}) + "\n")
        return {t: ok for t, ok, _ in grade.check(name, repo, run_dir)}

    MERGE = ["api", "-X", "PUT", "repos/acme/greeter/pulls/7/merge", "-f", "merge_method=squash", "-f", "sha=abc"]
    DELETE = ["api", "-X", "DELETE", "repos/acme/greeter/git/refs/heads/feat/add-greeting"]
    CREATE = ["release", "create", "v0.5.0", "--repo", "acme/greeter", "--verify-tag", "--title", "v0.5.0", "-n", "notes"]
    WATCH = "No other gh call created or changed anything (no gh pr merge, auto-merge or comment)"
    FINISH = "No gh call created or changed a pull request, issue or comment"

    @unittest.skipUnless(shutil.which("bash"), "needs bash")
    def test_release_auto_gh_log(self):
        cases = (("eval-agent-merge-release-auto", self.WATCH, [self.MERGE, self.DELETE]),
                 ("eval-finish-release-auto", self.FINISH, []))
        for name, check, base in cases:
            self.assertTrue(self.fixture(name, base + [self.CREATE])[check], f"{name}: the one expected release create must pass")
            self.assertFalse(self.fixture(name, base + [self.CREATE, self.CREATE])[check], f"{name}: a second release create must fail")
            self.assertFalse(self.fixture(name, base + [self.CREATE, ["release", "delete", "v0.5.0", "--yes"]])[check],
                             f"{name}: a release delete must fail")
            self.assertFalse(self.fixture(name, base + [self.CREATE, ["issue", "lock", "3"]])[check], f"{name}: an issue lock must fail")


class GitAllowlist(unittest.TestCase):
    """changing_git counts every traced git command as a change unless it is on the read-only allowlist (design D2)."""

    def writes(self, *cmds):
        for line in cmds:
            c = line.split()
            self.assertEqual(grade.changing_git([c]), [c], line)

    def reads(self, *cmds):
        for line in cmds:
            c = line.split()
            self.assertEqual(grade.changing_git([c]), [], line)

    def test_plumbing_and_dash_targets_are_writes(self):
        self.writes("update-ref refs/heads/main abc123", "symbolic-ref HEAD refs/heads/x", "symbolic-ref -d HEAD",
                    "symbolic-ref --delete HEAD", "checkout -", "switch -",
                    "branch --set-upstream-to=origin/main", "branch --track=direct x")

    def test_unknown_subcommand_is_a_write(self):
        self.writes("replace", "notes add", "reflog expire --all", "reflog delete HEAD@{0}", "reflog write refs/heads/x 0 1 msg", "reflog drop --all",
                    "reflog frobnicate", "frobnicate", "gc", "maintenance run",
                    "gc --prune=now", "config user.name x", "remote add o url", "remote -v add o url", "remote --verbose set-url o url",
                    "remote -v remove o", "remote -v prune o", "remote -v update", "stash push", "worktree add ../w", "")

    def test_fetch_into_local_branch_is_a_write(self):
        self.writes("fetch origin main:main", "fetch origin +refs/heads/x:refs/remotes/origin/x", "fetch origin feat/x:refs/heads/main",
                    "fetch origin tag v1",
                    "fetch --tags origin", "fetch -q origin main --tags",
                    "fetch --force origin main:refs/remotes/origin/main", "fetch -f origin main:refs/remotes/origin/main", "fetch -qf origin",
                    "fetch --set-upstream origin main", "fetch --set-up origin main",  # writes branch.<current>.remote and .merge
                    "fetch --forc origin main:refs/remotes/origin/main", "fetch --tag origin", "fetch --prune-t origin",  # git takes prefixes
                    "fetch -t origin", "fetch --prune-tags origin", "fetch -P origin",
                    "fetch --refmap=refs/heads/*:refs/heads/copied-* origin refs/heads/main",  # the refmap maps into refs/heads/
                    "fetch --refmap refs/heads/*:refs/heads/copied-* origin refs/heads/main", "fetch --frobnicate origin",
                    "fetch -qx origin", "fetch --depth 1 origin",  # an option off the read-only list is a write
                    "fetch +refs/heads/main:refs/heads/main", "fetch -q +refs/heads/x:refs/remotes/origin/x")  # + in any slot

    def test_branch_option_off_the_list_is_a_write(self):
        self.writes("branch -uother", "branch -vuother", "branch -fx main", "branch --frobnicate", "branch --sort=x -u other",
                    "branch -a --unset-upstream")
        self.reads("branch -vv", "branch -a", "branch -avv", "branch -r", "branch --sort=-committerdate", "branch --sort -committerdate",
                   "branch --no-color --list feat/*", "branch --contains HEAD", "branch --merged main -a", "branch --no-merged main",
                   "branch --points-at HEAD", "branch --column=never", "branch --abbrev=7 -v", "branch -i --list X")

    def test_reads_stay_reads(self):
        self.reads("status --porcelain", "log --oneline", "branch --show-current", "rev-parse HEAD", "fetch origin main", "fetch --no-tags origin", "diff-tree",
                   "reflog", "reflog -n 5", "reflog --oneline", "reflog show main", "reflog show", "reflog list",
                   "reflog exists refs/heads/main", "reflog HEAD", "reflog refs/heads/main", "reflog main@{1}",
                   "config --name-only --get-regexp x", "config get x", "config list", "config --list", "grep", "blame",
                   "symbolic-ref HEAD", "gc --auto --no-quiet --detach", "maintenance run --auto --no-quiet",
                   "upload-pack", "pack-objects", "remote -v", "remote", "remote -v show o", "remote -v get-url o", "stash list",
                   "worktree list", "tag", "ls-remote origin", "fetch --dry-run origin", "fetch -v --progress origin main")

    def test_fetch_that_stores_refs_is_a_write(self):
        self.writes("fetch origin", "fetch", "fetch --all", "fetch --multiple origin upstream", "fetch --prune origin",
                    "fetch --update-head-ok", "fetch -q origin", "fetch --all --prune", "fetch -j 4 --all", "fetch --jobs=4 --all",
                    "fetch origin refs/heads/x:refs/remotes/origin/x", "fetch --all origin main", "fetch --multiple origin main",
                    "fetch origin main refs/heads/x:refs/remotes/origin/x")

    def test_update_head_ok_without_a_pull_is_a_write(self):
        self.writes("fetch --update-head-ok origin", "fetch -u origin")
        c = [["status"], ["fetch", "--update-head-ok", "origin"]]
        self.assertEqual(grade.changing_git(c), [c[1]])

    def test_pull_child_fetch_is_judged_with_the_pull(self):
        pull, fetch, merge = ["pull", "--ff-only"], ["fetch", "--update-head-ok"], ["merge", "--ff-only", "FETCH_HEAD"]
        cmds = [pull, fetch, merge]
        self.assertEqual(grade.changing_git(cmds), [pull, merge])
        self.assertEqual(grade.refresh_exceptions(cmds), [])
        self.assertEqual(grade.changing_git([pull, ["rev-list", "x"], ["upload-pack", "."], fetch, merge]), [pull, merge])
        self.assertEqual(grade.changing_git([["pull"], ["commit", "-m", "x"], fetch]), [["pull"], ["commit", "-m", "x"], fetch])

    def test_fetch_with_no_tags_or_no_destination_is_a_read(self):
        self.reads("fetch --no-tags origin", "fetch -n --all", "fetch origin main", "fetch origin refs/tags/v1", "fetch --dry-run origin",
                   "fetch -qn origin", "fetch -nq --multiple origin upstream", "fetch --dry-run --all", "fetch -q --no-tags origin main",
                   "fetch --no-tags origin refs/heads/x:refs/remotes/origin/x")

    def test_no_tags_does_not_excuse_a_branch_or_tag_write(self):
        self.writes("fetch --no-tags origin main:main", "fetch -n origin tag v1", "fetch -n origin +refs/heads/x:refs/remotes/origin/x",
                    "fetch --dry-run origin main:main")

    def test_quiet_branch_listing_is_a_read(self):
        self.reads("branch -q --list", "branch --quiet --list feat/*")

    def test_quiet_flag_does_not_hide_a_branch_write(self):
        self.writes("branch -q feat/x", "branch -q -D feat/x", "branch --quiet feat/x")

    def test_tag_verification_is_a_read(self):
        self.reads("tag -v v1.0.0", "tag --verify v1.0.0")

    def test_verify_flag_does_not_hide_a_tag_write(self):
        self.writes("tag -v -d v1.0.0", "tag -f -v v1.0.0", "tag -vd v1.0.0")

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_real_traces_of_reads_are_reads(self):
        """Run real git against a local bare repo with GIT_TRACE and check what it traces. Built-ins git 2.55.0 traced as
        children (fetch, pull, push, commit): fetch --update-head-ok, upload-pack, receive-pack, pack-objects, unpack-objects,
        rev-list, for-each-ref, merge --ff-only FETCH_HEAD (pull's own), maintenance run --auto (--quiet or --no-quiet) --detach.
        No gc --auto, index-pack or fetch-pack appeared (the allowlist still covers them). The global options -C and -c are
        consumed before the built-in line, so the first traced command is the subcommand itself."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: fixtures.rmtree(tmp))
        root = Path(tmp)
        log = root / "git-trace.log"
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com",
                   GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")

        def git(cwd, *args, trace=False):
            e = dict(env, GIT_TRACE=str(log)) if trace else env
            if trace and log.exists():
                log.unlink()
            subprocess.run(["git", *args], cwd=str(cwd), env=e, check=True, capture_output=True, text=True)
            return (grade.git_trace(root) or []) if trace else None

        bare, work, other = root / "origin.git", root / "work", root / "other"
        git(root, "init", "-q", "--bare", "-b", "main", str(bare))
        git(root, "clone", "-q", str(bare), str(work))
        git(work, "checkout", "-q", "-b", "main")
        git(work, "commit", "-q", "--allow-empty", "-m", "one")
        git(work, "push", "-q", "origin", "main")
        git(root, "clone", "-q", str(bare), str(other))
        git(other, "commit", "-q", "--allow-empty", "-m", "two")
        git(other, "push", "-q", "origin", "main")

        seen = {}
        def traced(label, cwd, *args):
            cmds = git(cwd, *args, trace=True)
            self.assertTrue(cmds, label)
            seen[label] = cmds
            return cmds

        guarded = [traced("status", work, "status", "--porcelain")[0]]
        # a -C or -c option is consumed before the built-in line, so the first traced command is the subcommand itself
        self.assertEqual(traced("-C status", root, "-C", str(work), "status")[0], ["status"])
        self.assertEqual(traced("-c status", work, "-c", "core.quotepath=false", "status")[0], ["status"])
        for label, cmds in seen.items():
            self.assertFalse([a for c in cmds for a in c[:1] if a in ("-C", "-c")], label)
        traced("ls-remote", work, "ls-remote", "origin")
        traced("fetch", work, "fetch", "origin")
        guarded += traced("checkout main", work, "checkout", "main")[:1]
        guarded += traced("pull", work, "-c", "pull.rebase=false", "-c", "advice.detachedHead=false", "pull", "--ff-only")
        self.assertIn(["merge", "--ff-only", "FETCH_HEAD"], guarded, "pull runs its merge as a traced child: " + repr(seen["pull"]))
        self.assertEqual(grade.refresh_exceptions(guarded), [])
        git(work, "commit", "-q", "--allow-empty", "-m", "three")
        for label, args in (("commit", ("commit", "-q", "--allow-empty", "-m", "four")), ("push branch", ("push", "-q", "origin", "main:feat")),
                            ("tag", ("tag", "-a", "v1", "-m", "release")), ("push tag", ("push", "-q", "origin", "v1"))):
            cmds = traced(label, work, *args)
            self.assertEqual(grade.changing_git(cmds[1:]), [], f"{label}: children of {cmds[0]} must be reads: {cmds[1:]}")
        self.assertEqual(grade.other_changes(guarded + seen["tag"] + seen["push tag"]), [])
        # every child git started on its own, across all the commands, is a read
        # (pull's own children, its fetch --update-head-ok and merge, are judged with the pull)
        children = [c for label, cmds in seen.items() if label != "pull" for c in cmds[1:]]
        self.assertEqual(grade.changing_git(children), [], children)
        self.assertEqual([c[0] for c in grade.changing_git(seen["pull"])], ["pull", "merge"], seen["pull"])
        self.assertEqual(grade.changing_git(seen["fetch"][:1]), [seen["fetch"][0]], "a plain fetch origin follows tags: a write")


class GraphqlOperations(unittest.TestCase):
    """`gh api graphql` calls are classified by the operations in the document, not by its first token."""

    def setUp(self):
        import gqlops  # the fakes dir is on sys.path through fixtures
        self.ops, self.named = gqlops.operations, gqlops.named_operations

    def changing(self, *argv):
        return grade.changing_gh([{"argv": ["api", "graphql", *argv]}])

    def test_named_operations_carry_the_name(self):
        q = "query Q($n:Int) @d { a } mutation { b } fragment F on X { c } subscription query { d }"
        self.assertEqual(self.named(q), [("query", "Q", ["a"]), ("mutation", None, ["b"]), ("subscription", "query", ["d"])])
        self.assertEqual(self.named("query @d { a } mutation M @e { b }"), [("query", None, ["a"]), ("mutation", "M", ["b"])])
        self.assertEqual(self.ops(q), [("query", ["a"]), ("mutation", ["b"]), ("subscription", ["d"])])

    OP_DOC = ('query Q { viewer { login } } mutation M { addReaction(input:{subjectId:"X",content:THUMBS_UP}) '
              '{ reaction { content } } }')

    def test_operation_name_selects_a_query(self):
        self.assertEqual(self.changing("-f", "query=" + self.OP_DOC, "-f", "operationName=Q"), [])
        for spelling in (["-fquery=" + self.OP_DOC, "-foperationName=Q"], ["-F", "query=" + self.OP_DOC, "-F", "operationName=Q"],
                         ["--field", "query=" + self.OP_DOC, "--raw-field=operationName=Q"],
                         ["-f=query=" + self.OP_DOC, "-f=operationName=Q"]):
            self.assertEqual(self.changing(*spelling), [], spelling)

    def test_operation_name_selects_a_mutation(self):
        self.assertEqual(len(self.changing("-f", "query=" + self.OP_DOC, "-f", "operationName=M")), 1)
        self.assertEqual(len(self.changing("-f", "query=" + self.OP_DOC)), 1, "no operationName: every operation is classified")

    def test_unknown_operation_name_is_a_write(self):
        self.assertEqual(len(self.changing("-f", "query=" + self.OP_DOC, "-f", "operationName=Missing")), 1)

    def test_mutation_after_fragment_is_a_write(self):
        q = 'fragment R on Reaction { content } mutation { addReaction(input:{subjectId:"X",content:THUMBS_UP}) { reaction { ...R } } }'
        self.assertEqual(len(self.changing("-f", "query=" + q)), 1)
        self.assertEqual(self.ops(q), [("mutation", ["addReaction"])])

    def test_comment_or_string_mention_is_a_read(self):
        for q in ("query { viewer { login } } # resolveReviewThread",
                  'query { search(query: "mutation { addReaction") { issueCount } }',
                  'query { search(query: "say \\"mutation { addReaction\\" ") { issueCount } }',
                  'query { search(query: """mutation { addReaction""") { issueCount } }',
                  "query { viewer { login } } # mutation { addReaction"):
            self.assertEqual(self.changing("-f", "query=" + q), [], q)
            self.assertEqual([k for k, _ in self.ops(q)], ["query"], q)

    def test_unparseable_or_opaque_is_a_write(self):
        for argv in (["-f", "query=query { viewer { login }"], ["-f", "query=query { viewer { login } } }"],
                     ["-f", 'query=query { search(query: "x) { issueCount } }'], ["-F", "query=@q.graphql"],
                     ["--input", "q.json"], ["-f", "query=bogus { a }"], ["-f", "query=fragment F on User { login }"]):
            self.assertEqual(len(self.changing(*argv)), 1, argv)
        self.assertIsNone(self.ops("query { a "))
        self.assertIsNone(self.named("query { a "))
        self.assertIsNone(self.ops('query { a(x: "u) }'))
        self.assertIsNone(self.ops('query { a(x: """u) }'))
        self.assertIsNone(self.ops("query { a } }"))
        self.assertIsNone(self.ops("bogus { a }"))

    def test_operations_shapes(self):
        self.assertEqual(self.ops("{ viewer { login } }"), [("query", ["viewer"])])
        self.assertEqual(self.ops("query Q($n: Int = 3, $o: String!) @dir(a: {b: 1}) { repository(owner: $o) { id } rateLimit { cost } }"),
                         [("query", ["repository", "rateLimit"])])
        self.assertEqual(self.ops('mutation M { a: addReaction(input: {subjectId: "X"}) { reaction { content } } b: resolveReviewThread(input: {threadId: "T"}) { thread { id } } }'),
                         [("mutation", ["addReaction", "resolveReviewThread"])])
        self.assertEqual(self.ops("query A { x } mutation B { y } subscription C { z }"),
                         [("query", ["x"]), ("mutation", ["y"]), ("subscription", ["z"])])
        self.assertEqual(self.ops("query { viewer { ...F } ...G ... on Query { rateLimit { cost } } }"), [("query", ["viewer"])])
        self.assertEqual(self.ops("fragment F on User { login }"), [])
        self.assertEqual(self.ops("# only a comment\n"), [])


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

    REFRESH = "The guarded refresh ran: git status --porcelain, then git checkout main, then git pull --ff-only (the git trace)"

    def test_the_merged_runs_fail_without_a_refresh(self):
        # main is already current in these two fixtures, so only the trace shows a skipped refresh
        for name in self.NAMES:
            run_dir, repo = self.fixture(name)
            self.sh(repo, "git status --porcelain && git log --first-parent --format=%s main")
            self.closed_check(repo)
            res = self.grade(name, run_dir)
            self.assertIn(self.REFRESH, self.failed(res), name)

    def test_a_pull_before_the_checkout_fails(self):
        # off main, a pull before `checkout main` updates the current branch and leaves main stale; the fixtures start on main, so only
        # the trace order shows it
        for script in ("git status --porcelain && git pull --ff-only && git checkout main", "git status --porcelain && git pull --ff-only"):
            for name in self.NAMES:
                run_dir, repo = self.fixture(name)
                self.sh(repo, script)
                self.closed_check(repo)
                res = self.grade(name, run_dir)
                self.assertEqual(self.failed(res), [self.REFRESH], f"{name}: {script}")

    def test_a_pull_without_the_guard_before_it_fails(self):
        for script in ("git checkout -q main && git pull --ff-only", "git pull --ff-only && git status --porcelain"):
            for name in self.NAMES:
                run_dir, repo = self.fixture(name)
                self.sh(repo, script)
                self.closed_check(repo)
                res = self.grade(name, run_dir)
                self.assertEqual(self.failed(res), [self.REFRESH], f"{name}: {script}")

    def test_a_commit_a_merge_a_push_or_a_branch_deletion_still_fails(self):
        trace = "No git commit, merge, push or branch-changing command ran (the git trace)"
        for cmd in ("git commit -q --allow-empty -m x", "git merge --no-ff -q -m x main", "git push origin main", "git branch -D stray",
                    "git pull --rebase", "git checkout -b other"):
            run_dir, repo = self.fixture("eval-finish-resume-merged-branch-gone")
            self.sh(repo, "git status --porcelain && git checkout -q main && git pull --ff-only")
            self.closed_check(repo)
            # the refresh alone passes, so a failure below comes from the injected command
            self.assertTrue(self.grade("eval-finish-resume-merged-branch-gone", run_dir)[trace], cmd)
            self.sh(repo, cmd + " || true")
            res = self.grade("eval-finish-resume-merged-branch-gone", run_dir)
            self.assertFalse(res[trace], cmd)

    def test_a_quiet_guarded_refresh_passes_every_check(self):
        for name in self.NAMES:
            run_dir, repo = self.fixture(name)
            self.sh(repo, "git status --porcelain && git checkout -q main && git pull -q --ff-only")
            self.closed_check(repo)
            res = self.grade(name, run_dir)
            self.assertTrue(res and not self.failed(res), f"{name}: {self.failed(res)}")

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


class InstallOpenSpecPin(unittest.TestCase):
    """eval-install-openspec-mismatch / -override: the refusal grades a run that wrote nothing, the override its report line."""

    def fixture(self, name):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo"
        fixtures.build(name, repo)
        return repo

    def results(self, name, repo, report):
        return {t: ok for t, ok, _ in grade.check_install(name, repo, repo / "code", repo / "store", report.lower())}

    def assertions(self, name):
        evals = json.loads((Path(__file__).resolve().parent / "evals.json").read_text(encoding="utf-8"))["evals"]
        return next(e["assertions"] for e in evals if e["name"] == name)

    def test_refusal_that_writes_nothing_passes_every_check(self):
        repo = self.fixture("eval-install-openspec-mismatch")
        res = self.results("eval-install-openspec-mismatch", repo,
                           "Stopped before Step 4: OpenSpec 1.15.0 is installed, but this release is pinned to 1.14.1. "
                           "Run npm i -g @fission-ai/openspec@1.14.1 and rerun the prompt. No file was written.")
        self.assertEqual(sorted(res), sorted(self.assertions("eval-install-openspec-mismatch")))
        self.assertTrue(all(res.values()), [t for t, ok in res.items() if not ok])

    def test_refusal_that_installs_anyway_fails(self):
        repo = self.fixture("eval-install-openspec-mismatch")
        fixtures.write(repo / "code", ".claude/skills/specwright-commit/SKILL.md", "x\n")
        fixtures.write(repo / "code", "openspec/.specwright/VERSION", "0.4.2\n")
        res = self.results("eval-install-openspec-mismatch", repo, "Installation complete. Specwright 0.4.2 installed.")
        for t in ("No skill, agent, schema or specwright.yaml was written in either repo, and both trees are unchanged",
                  "openspec/.specwright/VERSION is absent", "The report names 1.15.0, 1.14.1 and npm i -g @fission-ai/openspec@1.14.1",
                  "The report does not say the install completed"):
            self.assertFalse(res[t], t)

    def test_override_report_line_is_checked(self):
        repo = self.fixture("eval-install-openspec-override")
        name, line = "eval-install-openspec-override", "The report shows OpenSpec 1.15.0 (pinned 1.14.1, override)"
        # the install-store checks plus the override line (evals.json words the inherited ones as eval-install-store does)
        self.assertEqual(sorted(self.results(name, repo, "")), sorted([*self.results("eval-install-store", repo, ""), line]))
        self.assertEqual(self.assertions(name), [*self.assertions("eval-install-store"), line])
        self.assertFalse(self.results(name, repo, "OpenSpec 1.15.0 (pinned)")[line])
        self.assertTrue(self.results(name, repo, "OpenSpec 1.15.0 (pinned 1.14.1, override)")[line])


RELEASE_SH = fixtures.posix(fixtures.ROOT) + "/skills/specwright-release/scripts/release.sh"
AS_SH = fixtures.posix(fixtures.ROOT) + "/skills/specwright-pr/scripts/as.sh"
RELEASE_NAMES = ("eval-finish-release-offer", "eval-finish-release-auto", "eval-finish-release-disabled",
                 "eval-finish-local-release-reported", "eval-agent-merge-release-auto")
OFFER_REPORT = "Cleanup done: main is current.\n\nVersion 0.5.0 has no tag yet. Shall I publish v0.5.0 (tag and GitHub release)?\n\nNext: specwright-roadmap next, or close?"
PUBLISHED_REPORT = "Cleanup done.\n\nrelease v0.5.0: tag pushed at abc1234, GitHub release created.\n\nNext: specwright-roadmap next, or close?"
AGENT_PUBLISHED_REPORT = PUBLISHED_REPORT.replace("next, or close?", "next for M2?")  # the Now milestone still lists add-shout: next only


class ReleaseHelpers(unittest.TestCase):
    """The pure helpers of the release graders."""

    def test_tag_writes_only_flags_what_changes_tags(self):
        for c in (["tag", "-a", "v1", "-m", "x"], ["tag", "v1"], ["tag", "-d", "v1"], ["tag", "-f", "v1"], ["tag", "-am", "x", "v1"],
                  ["tag", "--annotate", "--cleanup=verbatim", "-F", "f", "v1", "abc"], ["tag", "-s", "v1"]):
            self.assertEqual(grade.tag_writes([c]), [c], c)
        for c in (["tag"], ["tag", "-l"], ["tag", "-l", "v*"], ["tag", "-l", "--format=%(contents)", "v1"], ["tag", "--list", "v*"],
                  ["tag", "--contains", "abc"], ["tag", "--points-at", "HEAD"], ["status"]):
            self.assertEqual(grade.tag_writes([c]), [], c)

    def test_force_like_finds_every_forcing_form(self):
        for argv in (["--force"], ["-f"], ["--force-with-lease"], ["--force-with-lease=main"], ["--tags"], ["--mirror"], ["--all"], ["--delete"],
                     ["-d"], ["-fq"], ["+refs/tags/v1:refs/tags/v1"], ["--prune"]):
            self.assertTrue(grade.force_like(argv), argv)
        self.assertEqual(grade.force_like(["origin", "refs/tags/v0.5.0:refs/tags/v0.5.0", "-q", "--verify-tag"]), [])

    def test_push_refspecs_skip_the_remote_and_options(self):
        self.assertEqual(grade.push_refspecs(["push", "origin", "refs/tags/v1:refs/tags/v1"]), ["refs/tags/v1:refs/tags/v1"])
        self.assertEqual(grade.push_refspecs(["push", "-q", "origin", "main", "v1"]), ["main", "v1"])
        self.assertEqual(grade.push_refspecs(["push"]), [])

    def test_report_order_and_offer(self):
        low = OFFER_REPORT.lower()
        self.assertTrue(grade.release_offered(low))
        self.assertLess(grade.release_pos(low), grade.roadmap_pos(low))
        late = "next: specwright-roadmap next, or close?\n\nshall i publish v0.5.0?"
        self.assertGreater(grade.release_pos(late), grade.roadmap_pos(late))
        self.assertFalse(grade.release_offered("version 0.5.0 is released and tagged."))
        self.assertFalse(grade.release_offered("nothing to finish - archive is on main."))
        self.assertIsNone(grade.release_pos("the 0.5.0 milestone is unrelated"))
        self.assertTrue(grade.near("v0.5.0 is untagged.\nit can be published once main is pushed.", r"0\.5\.0", r"push", grade.RELEASE_WORDS))
        self.assertFalse(grade.near("v0.5.0 is untagged. push main.\n\n\nunrelated. tag it later.", r"0\.5\.0", r"push", r"publish"))


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class ReleaseEvals(unittest.TestCase):
    """The five release fixtures and graders: simulated runs (git and the fake gh through the fixture's shims, and the real
    release.sh publish) grade green, and the wrong runs grade red."""

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

    def grade(self, name, run_dir, report):
        (run_dir / "outputs" / "report.md").write_text(report, encoding="utf-8")
        return {t: ok for t, ok, _ in grade.check(name, run_dir / "repo", run_dir)}

    def failed(self, res):
        return [t for t, ok in res.items() if not ok]

    def cleanup(self, repo):
        self.sh(repo, "git status --porcelain && git checkout -q main && git pull -q --ff-only && git fetch -q --no-tags origin main")

    def publish(self, repo):
        return json.loads(self.sh(repo, f"bash {AS_SH} eval-bot bash {RELEASE_SH} --dir . publish --version 0.5.0 --main origin/main"))

    def test_evals_json_lists_the_graders_assertions(self):
        evals = {e["name"]: e for e in json.loads((Path(__file__).resolve().parent / "evals.json").read_text(encoding="utf-8"))["evals"]}
        ids = [e["id"] for e in evals.values()]
        self.assertEqual(len(ids), len(set(ids)), "duplicate eval ids")
        for name in RELEASE_NAMES:
            run_dir, repo = self.fixture(name)
            self.assertEqual(list(self.grade(name, run_dir, "")), evals[name]["assertions"], name)
            self.assertTrue(evals[name]["prompt"] and evals[name]["expected_output"], name)

    def test_pr_fixtures_untagged_lists_0_5_0_on_origins_main(self):
        for name in RELEASE_NAMES[:2]:
            _, repo = self.fixture(name)
            doc = json.loads(self.sh(repo, f"bash {RELEASE_SH} --dir . untagged --main origin/main"))
            self.assertEqual([u["version"] for u in doc["untagged"]], ["0.5.0"], name)
            self.assertEqual(grade.git(repo, "log", "-1", "--format=%s", "origin/main"), "Add greeting (#7)")
            self.assertEqual(self.sh(repo, "git remote get-url origin"), "https://github.com/acme/greeter.git", name)
            self.assertEqual(grade.git(repo, "tag"), "")
            self.assertEqual(grade.git(repo / "ob.git", "tag"), "")

    def test_settings_blocks(self):
        for name, auto in (("eval-finish-release-offer", "false"), ("eval-finish-release-auto", "true")):
            _, repo = self.fixture(name)
            text = (repo / "openspec" / "specwright.yaml").read_text(encoding="utf-8")
            self.assertIn(f"release:\n  enabled: true\n  auto: {auto}\n", text, name)
            self.assertIn("VERSION: '^(\\d+\\.\\d+\\.\\d+)$'", text)
        _, repo = self.fixture("eval-finish-release-disabled")
        self.assertIn("release:\n  enabled: false\n", (repo / "openspec" / "specwright.yaml").read_text(encoding="utf-8"))

    # eval-finish-release-offer
    def test_offer_run_passes_every_check(self):
        run_dir, repo = self.fixture("eval-finish-release-offer")
        self.cleanup(repo)
        self.sh(repo, f"bash {RELEASE_SH} --dir . untagged --main origin/main")  # reading the list is allowed
        res = self.grade("eval-finish-release-offer", run_dir, OFFER_REPORT)
        self.assertTrue(res and not self.failed(res), self.failed(res))

    def test_offer_run_that_publishes_unasked_fails(self):
        run_dir, repo = self.fixture("eval-finish-release-offer")
        self.cleanup(repo)
        self.publish(repo)
        res = self.grade("eval-finish-release-offer", run_dir, OFFER_REPORT)
        for t in ("No tag exists locally or on origin, and no git tag write or git push ran", "No gh release call was made (no create, no view)"):
            self.assertIn(t, self.failed(res))

    def test_offer_report_without_offer_or_in_the_wrong_order_fails(self):
        run_dir, repo = self.fixture("eval-finish-release-offer")
        self.cleanup(repo)
        res = self.grade("eval-finish-release-offer", run_dir, "Nothing to finish - archive is on main.\n\nNext: specwright-roadmap next, or close?")
        self.assertEqual(self.failed(res), ["The report offers to publish 0.5.0 (asks, naming the version and publish, release or tag)",
                                            "The release offer comes before the roadmap offer (specwright-roadmap next or close)"])
        res = self.grade("eval-finish-release-offer", run_dir, "Next: specwright-roadmap next, or close?\n\nShall I publish v0.5.0?")
        self.assertEqual(self.failed(res), ["The release offer comes before the roadmap offer (specwright-roadmap next or close)"])

    def test_offer_run_without_a_refresh_fails(self):
        run_dir, repo = self.fixture("eval-finish-release-offer")
        self.sh(repo, "git fetch -q --no-tags origin main")
        res = self.grade("eval-finish-release-offer", run_dir, OFFER_REPORT)
        self.assertEqual(self.failed(res), ["The guarded refresh ran: git status --porcelain, then git checkout main, then git pull --ff-only (the git trace)"])

    # eval-finish-release-auto
    def test_auto_run_passes_every_check(self):
        run_dir, repo = self.fixture("eval-finish-release-auto")
        self.cleanup(repo)
        doc = self.publish(repo)
        self.assertEqual((doc["tag_local"], doc["tag_remote"], doc["github_release"]), ("created", "pushed", "created"))
        res = self.grade("eval-finish-release-auto", run_dir, PUBLISHED_REPORT)
        self.assertTrue(res and not self.failed(res), self.failed(res))

    def test_auto_run_without_a_release_fails(self):
        run_dir, repo = self.fixture("eval-finish-release-auto")
        self.cleanup(repo)
        res = self.grade("eval-finish-release-auto", run_dir, OFFER_REPORT)
        failed = self.failed(res)
        for t in ("An annotated tag v0.5.0 on the squash merge commit exists locally and on origin, and it is the only tag in either",
                  "Exactly one gh release create v0.5.0 was made, with --verify-tag", "The fake gh holds the release, and its body equals the tag's message",
                  "The release step pushed only the tag: every git push names only refs/tags/v0.5.0, and origin holds no other new ref"):
            self.assertIn(t, failed)

    def test_auto_run_with_a_tag_only_on_origin_or_a_lightweight_tag_fails(self):
        key = "An annotated tag v0.5.0 on the squash merge commit exists locally and on origin, and it is the only tag in either"
        run_dir, repo = self.fixture("eval-finish-release-auto")
        self.cleanup(repo)
        self.sh(repo, "git tag v0.5.0 && git push -q origin refs/tags/v0.5.0:refs/tags/v0.5.0")
        self.assertIn(key, self.failed(self.grade("eval-finish-release-auto", run_dir, PUBLISHED_REPORT)))
        run_dir, repo = self.fixture("eval-finish-release-auto")
        self.cleanup(repo)
        self.sh(repo, "git tag -a v0.5.0 -m notes")  # never pushed
        self.assertIn(key, self.failed(self.grade("eval-finish-release-auto", run_dir, PUBLISHED_REPORT)))

    def test_auto_run_that_pushes_a_branch_or_forces_fails(self):
        push = "The release step pushed only the tag: every git push names only refs/tags/v0.5.0, and origin holds no other new ref"
        force = "No git push or gh release call used --force, -f, --force-with-lease, --tags, --mirror, --all or --delete, or a + refspec"
        for extra in ("git push -q origin main", "git push -q origin main:refs/heads/side"):
            run_dir, repo = self.fixture("eval-finish-release-auto")
            self.cleanup(repo)
            self.publish(repo)
            self.sh(repo, extra)
            self.assertIn(push, self.failed(self.grade("eval-finish-release-auto", run_dir, PUBLISHED_REPORT)), extra)
        run_dir, repo = self.fixture("eval-finish-release-auto")
        self.cleanup(repo)
        self.publish(repo)
        self.sh(repo, "git push -q --force origin refs/tags/v0.5.0:refs/tags/v0.5.0")
        self.assertIn(force, self.failed(self.grade("eval-finish-release-auto", run_dir, PUBLISHED_REPORT)))

    def test_auto_run_whose_release_body_differs_from_the_tag_message_fails(self):
        run_dir, repo = self.fixture("eval-finish-release-auto")
        self.cleanup(repo)
        self.sh(repo, "git tag -a v0.5.0 -m 'the tag message' && git push -q origin refs/tags/v0.5.0:refs/tags/v0.5.0 "
                      "&& GIT_CONFIG_GLOBAL=\"$PWD/state/gitconfig-release\" gh release create v0.5.0 --repo acme/greeter --verify-tag "
                      "--title v0.5.0 -n 'other notes'")
        res = self.grade("eval-finish-release-auto", run_dir, PUBLISHED_REPORT)
        self.assertEqual(self.failed(res), ["The fake gh holds the release, and its body equals the tag's message"])

    def test_auto_report_without_a_roadmap_offer_fails(self):
        run_dir, repo = self.fixture("eval-finish-release-auto")
        self.cleanup(repo)
        self.publish(repo)
        res = self.grade("eval-finish-release-auto", run_dir, "release v0.5.0: tag pushed, GitHub release created.")
        self.assertEqual(self.failed(res), ["The report names the release of 0.5.0, then offers the roadmap mode (next or close), the release first"])

    # eval-finish-release-disabled
    def test_disabled_run_passes_every_check(self):
        run_dir, repo = self.fixture("eval-finish-release-disabled")
        self.cleanup(repo)
        res = self.grade("eval-finish-release-disabled", run_dir, "Nothing to finish - archive is on main.\n\nNext: specwright-roadmap next, or close?")
        self.assertTrue(res and not self.failed(res), self.failed(res))
        res = self.grade("eval-finish-release-disabled", run_dir, "Pull request #7 was released to main and cleaned up. Next: specwright-roadmap next?")
        self.assertTrue(res and not self.failed(res), "the word 'released' must not count as a release step: " + str(self.failed(res)))

    def test_disabled_run_that_mentions_or_makes_a_release_fails(self):
        key = "The report has no release step: no publish, untagged, release, tag or 0.5.0"
        run_dir, repo = self.fixture("eval-finish-release-disabled")
        self.cleanup(repo)
        for text in ("Version 0.5.0 is untagged. Next: specwright-roadmap next?", "Shall I publish it? Next: specwright-roadmap next?",
                     "The release is not enabled. Next: specwright-roadmap next?", "Nothing to tag. Next: specwright-roadmap next?"):
            self.assertIn(key, self.failed(self.grade("eval-finish-release-disabled", run_dir, text)), text)
        self.sh(repo, "git tag -a v0.5.0 -m notes && gh release create v0.5.0 --repo acme/greeter -n notes")
        res = self.grade("eval-finish-release-disabled", run_dir, "Next: specwright-roadmap next?")
        for t in ("No tag exists locally or on origin, and no git tag write or git push ran", "No gh release call was made (no create, no view)",
                  "No git tag or ls-remote command ran (the git trace)"):
            self.assertIn(t, self.failed(res))

    def test_disabled_report_without_roadmap_offer_fails(self):
        run_dir, repo = self.fixture("eval-finish-release-disabled")
        self.cleanup(repo)
        res = self.grade("eval-finish-release-disabled", run_dir, "Nothing to finish - archive is on main.")
        self.assertEqual(self.failed(res), ["The report offers the roadmap mode (next or close): finish went on as usual"])

    # eval-finish-local-release-reported
    LOCAL_REPORT = "Merged add-greeting into main. Local only - push main when ready.\n\nv0.5.0 is untagged: publish it once main is pushed."

    def local_run(self, repo):
        self.sh(repo, "git add -A && git commit -q -m 'feat(add-greeting): archive change' && git checkout -q main "
                      "&& git merge -q --no-ff feat/add-greeting -m 'merge: add-greeting' && git branch -q -d feat/add-greeting")

    def test_local_fixture_is_ready_and_bumps_the_version_on_the_branch(self):
        _, repo = self.fixture("eval-finish-local-release-reported")
        self.assertEqual(grade.git(repo, "branch", "--show-current"), "feat/add-greeting")
        self.assertEqual(grade.git(repo, "show", "main:VERSION"), "0.4.0")
        self.assertEqual(grade.git(repo, "show", "HEAD:VERSION"), "0.5.0")
        text = (repo / "openspec" / "specwright.yaml").read_text(encoding="utf-8")
        self.assertIn("finish: local\n", text)
        self.assertIn("release:\n  enabled: true\n  auto: true\n", text)
        self.assertEqual(grade.git(repo, "rev-parse", "main"), grade.git(repo / "ob.git", "rev-parse", "main"))

    def test_local_run_passes_every_check(self):
        run_dir, repo = self.fixture("eval-finish-local-release-reported")
        self.local_run(repo)
        self.sh(repo, f"bash {RELEASE_SH} --dir . untagged --main main")
        res = self.grade("eval-finish-local-release-reported", run_dir, self.LOCAL_REPORT)
        self.assertTrue(res and not self.failed(res), self.failed(res))
        doc = json.loads(self.sh(repo, f"bash {RELEASE_SH} --dir . untagged --main main"))
        self.assertEqual([u["version"] for u in doc["untagged"]], ["0.5.0"], "main's merge commit carries the release")

    def test_local_run_that_publishes_fails(self):
        run_dir, repo = self.fixture("eval-finish-local-release-reported")
        self.local_run(repo)
        self.sh(repo, f"bash {AS_SH} eval-bot bash {RELEASE_SH} --dir . publish --version 0.5.0 --main main")
        res = self.grade("eval-finish-local-release-reported", run_dir, "Published v0.5.0.")
        for t in ("No tag was created", "Nothing was pushed: origin keeps its main and has no tag, no git push ran, and no gh release call was made",
                  "The report says v0.5.0 can be published after main is pushed"):
            self.assertIn(t, self.failed(res))

    def test_local_run_that_pushes_main_fails_and_one_that_stays_silent_fails(self):
        run_dir, repo = self.fixture("eval-finish-local-release-reported")
        self.local_run(repo)
        self.sh(repo, "git push -q origin main")
        res = self.grade("eval-finish-local-release-reported", run_dir, self.LOCAL_REPORT)
        self.assertEqual(self.failed(res), ["Nothing was pushed: origin keeps its main and has no tag, no git push ran, and no gh release call was made"])
        run_dir, repo = self.fixture("eval-finish-local-release-reported")
        self.local_run(repo)
        res = self.grade("eval-finish-local-release-reported", run_dir, "Merged add-greeting into main. Local only - push main when ready.")
        self.assertEqual(self.failed(res), ["The report says v0.5.0 can be published after main is pushed"])

    def test_local_run_that_does_not_merge_fails(self):
        run_dir, repo = self.fixture("eval-finish-local-release-reported")
        res = self.grade("eval-finish-local-release-reported", run_dir, self.LOCAL_REPORT)
        self.assertIn("Now on main, and main HEAD is a merge commit with two parents and subject merge: add-greeting", self.failed(res))

    # eval-agent-merge-release-auto
    def agent_run(self, repo, publish=True):
        tip = grade.git(repo, "rev-parse", "HEAD")
        self.sh(repo, f"gh api -X PUT repos/acme/greeter/pulls/7/merge -f merge_method=squash -f sha={tip}")
        self.sh(repo, "git checkout -q main && git pull -q --ff-only && git fetch -q --no-tags origin main")
        self.sh(repo, "git branch -q -D feat/add-greeting")
        self.sh(repo, "gh api -X DELETE repos/acme/greeter/git/refs/heads/feat/add-greeting")
        if publish:
            self.publish(repo)

    def test_agent_fixture_bumps_the_version_in_the_squash_commit_and_waits_for_the_merge(self):
        _, repo = self.fixture("eval-agent-merge-release-auto")
        self.assertEqual(grade.git(repo / "ob.git", "show", "main:VERSION"), "0.5.0")
        self.assertEqual(grade.git(repo, "show", "main:VERSION"), "0.4.0")
        self.assertEqual(grade.git(repo, "log", "-1", "--format=%s", "feat/add-greeting~1"), "feat(add-greeting): bump version to 0.5.0")
        text = (repo / "openspec" / "specwright.yaml").read_text(encoding="utf-8")
        self.assertIn("merge: agent", text)
        self.assertIn("release:\n  enabled: true\n  auto: true\n", text)
        before = subprocess.run(["bash", "-c", "source eval.env && git checkout -q main && git pull --ff-only"], cwd=repo, capture_output=True, text=True)
        self.assertNotEqual(before.returncode, 0, "a pull before the merge must fail at the unreachable proxy")

    def test_agent_fixture_serves_the_pre_merge_main_to_the_version_checks_fetch(self):
        _, repo = self.fixture("eval-agent-merge-release-auto")
        main = grade.git(repo, "rev-parse", "main")
        r = subprocess.run(["bash", "-c", "source eval.env && git fetch -q --no-tags origin main"], cwd=repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(grade.git(repo, "rev-parse", "origin/main"), main, "a fetch before the merge must see main without the squash")
        check = subprocess.run(["bash", str(Path(__file__).resolve().parents[2] / "skills" / "specwright-release" / "scripts" / "release.sh"), "check", "--main", "origin/main"],
                               cwd=repo, capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.agent_run(repo, publish=False)
        self.assertEqual(grade.git(repo, "rev-parse", "origin/main"), grade.git(repo / "ob.git", "rev-parse", "main"),
                         "a fetch after the merge must see the squash")

    def test_agent_run_passes_every_check(self):
        run_dir, repo = self.fixture("eval-agent-merge-release-auto")
        self.agent_run(repo)
        res = self.grade("eval-agent-merge-release-auto", run_dir, AGENT_PUBLISHED_REPORT)
        self.assertTrue(res and not self.failed(res), self.failed(res))

    def test_agent_run_that_releases_before_the_cleanup_fails(self):
        run_dir, repo = self.fixture("eval-agent-merge-release-auto")
        tip = grade.git(repo, "rev-parse", "HEAD")
        self.sh(repo, f"gh api -X PUT repos/acme/greeter/pulls/7/merge -f merge_method=squash -f sha={tip}")
        self.sh(repo, "git checkout -q main && git pull -q --ff-only && git fetch -q --no-tags origin main")
        self.publish(repo)
        self.sh(repo, "git branch -q -D feat/add-greeting")
        self.sh(repo, "gh api -X DELETE repos/acme/greeter/git/refs/heads/feat/add-greeting")
        res = self.grade("eval-agent-merge-release-auto", run_dir, AGENT_PUBLISHED_REPORT)
        self.assertEqual(self.failed(res), [
            "The release came after the cleanup: the gh log has the merge, the remote branch DELETE, then the release create, and the tag push "
            "follows the pull and the local branch deletion (the git trace)"])

    def test_agent_run_without_a_release_or_a_report_line_fails(self):
        run_dir, repo = self.fixture("eval-agent-merge-release-auto")
        self.agent_run(repo, publish=False)
        res = self.grade("eval-agent-merge-release-auto", run_dir, "Merged #7. Run specwright-roadmap next for M2?")
        failed = self.failed(res)
        self.assertIn("Exactly one gh release create v0.5.0 was made, with --verify-tag", failed)
        self.assertIn("An annotated tag v0.5.0 on the squash merge commit exists locally and on origin, and it is the only tag in either", failed)
        self.assertIn("The report names the release of 0.5.0, then offers the roadmap mode (next or close), the release first", failed)
        self.assertNotIn("Exactly one merge request was sent, with squash and the ready head", failed)


class BranchStoreEvals(unittest.TestCase):
    """eval-branch-store-*: the store-version gate and the update lock. Simulated runs (a gate that stops leaves the fixture as it
    was; a gate that continues creates both branches) grade green, and the wrong runs grade red."""

    NAMES = ("eval-branch-store-version-match", "eval-branch-store-version-behind", "eval-branch-store-update-lock")
    BEHIND = ("Stopped: this project is at 0.5.0 but the store is at 0.6.0, owned by alice-laptop. "
              "Update this project to 0.6, then rerun the gate. No branch was created.")
    LOCKED = ("Stopped before touching either repo: an update from C:\\elsewhere\\code holds the store. "
              "Rerun the update there. I am not offering to remove the lock.")

    def fixture(self, name):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(lambda: fixtures.rmtree(tmp.name))
        self.addCleanup(tmp.cleanup)
        run_dir = Path(tmp.name) / "run"
        repo = run_dir / "repo"
        fixtures.build(name, repo)
        (run_dir / "outputs").mkdir()
        return run_dir, repo

    def grade(self, name, run_dir, report):
        (run_dir / "outputs" / "report.md").write_text(report, encoding="utf-8")
        return {t: ok for t, ok, _ in grade.check_store(name, run_dir / "repo", run_dir)}

    def failed(self, res):
        return [t for t, ok in res.items() if not ok]

    def branch_both(self, repo):
        for r in ("code", "store"):
            grade.git(repo / r, "checkout", "-q", "-b", "feat/add-csv-export")

    def lock_dir(self, repo):
        cd = grade.git(repo / "store", "rev-parse", "--path-format=absolute", "--git-common-dir")
        return Path(cd) / "specwright-gate.lock"

    def test_evals_json_lists_the_graders_assertions(self):
        evals = {e["name"]: e for e in json.loads((Path(__file__).resolve().parent / "evals.json").read_text(encoding="utf-8"))["evals"]}
        for name in self.NAMES:
            run_dir, _ = self.fixture(name)
            self.assertEqual(list(self.grade(name, run_dir, "")), evals[name]["assertions"], name)
            self.assertTrue(evals[name]["prompt"] and evals[name]["expected_output"], name)
            self.assertEqual(evals[name]["skills"], ["specwright-branch"], name)

    def test_fixtures_record_the_versions_and_the_update_lock(self):
        _, repo = self.fixture("eval-branch-store-version-match")
        self.assertEqual((repo / "code/openspec/.specwright/VERSION").read_text(encoding="utf-8").strip(), "0.6.1")
        self.assertEqual((repo / "store/openspec/.specwright/STORE").read_text(encoding="utf-8"), "version: 0.6.0\nowner: alice-laptop\n")
        _, repo = self.fixture("eval-branch-store-version-behind")
        self.assertEqual((repo / "code/openspec/.specwright/VERSION").read_text(encoding="utf-8").strip(), "0.5.0")
        self.assertEqual(grade.git(repo / "code", "status", "--porcelain"), "")
        self.assertEqual(grade.git(repo / "store", "status", "--porcelain"), "")
        _, repo = self.fixture("eval-branch-store-update-lock")
        owner = (self.lock_dir(repo) / "owner").read_text(encoding="utf-8")
        self.assertIn("change: specwright-update 0.5.0 -> 0.6.0\n", owner)
        self.assertIn("code: C:/elsewhere/code\n", owner)
        self.assertIn("token: ", owner)

    def test_match_with_both_branches_created_passes(self):
        run_dir, repo = self.fixture("eval-branch-store-version-match")
        self.branch_both(repo)
        res = self.grade("eval-branch-store-version-match", run_dir, "On branch feat/add-csv-export in the code repo and the store.")
        self.assertEqual(self.failed(res), [])

    def test_match_that_stops_on_a_mismatch_fails(self):
        run_dir, _ = self.fixture("eval-branch-store-version-match")
        res = self.grade("eval-branch-store-version-match", run_dir, "Version mismatch: update this project.")
        self.assertIn("Both repos are on feat/add-csv-export, each branch at its repo's main with no new commits", self.failed(res))
        self.assertIn("The report does not stop on a version mismatch", self.failed(res))

    def test_match_that_leaves_the_lock_fails(self):
        run_dir, repo = self.fixture("eval-branch-store-version-match")
        self.branch_both(repo)
        self.lock_dir(repo).mkdir()
        self.assertEqual(self.failed(self.grade("eval-branch-store-version-match", run_dir, "ok")),
                         ["No gate lock is left in the store"])

    def test_behind_stop_with_versions_owner_and_advice_passes(self):
        run_dir, _ = self.fixture("eval-branch-store-version-behind")
        self.assertEqual(self.failed(self.grade("eval-branch-store-version-behind", run_dir, self.BEHIND)), [])

    def test_behind_advice_worded_as_needs_updating_passes(self):
        run_dir, _ = self.fixture("eval-branch-store-version-behind")
        rep = ("Stopped: VERSION 0.5.0, STORE 0.6.0, owner alice-laptop. This project needs updating to "
               "Specwright 0.6 to match the store.")
        self.assertEqual(self.failed(self.grade("eval-branch-store-version-behind", run_dir, rep)), [])

    def test_behind_that_created_a_branch_fails(self):
        run_dir, repo = self.fixture("eval-branch-store-version-behind")
        self.branch_both(repo)
        res = self.grade("eval-branch-store-version-behind", run_dir, self.BEHIND)
        self.assertEqual(self.failed(res), ["Both repos are still on main with only the main branch and no new commit"])

    def test_behind_report_without_the_owner_or_the_advice_fails(self):
        run_dir, _ = self.fixture("eval-branch-store-version-behind")
        res = self.grade("eval-branch-store-version-behind", run_dir, "Stopped: project 0.5.0, store 0.6.0.")
        self.assertEqual(self.failed(res), ["The report names this project's version 0.5.0, the store's version 0.6.0 and the store's owner alice-laptop",
                                           "The report says to update this project to 0.6"])
        res = self.grade("eval-branch-store-version-behind", run_dir, "Stopped: 0.5.0 vs 0.6.0 (alice-laptop). The store owner updates it first.")
        self.assertEqual(self.failed(res), ["The report says to update this project to 0.6"])

    def test_update_lock_stop_passes(self):
        run_dir, _ = self.fixture("eval-branch-store-update-lock")
        self.assertEqual(self.failed(self.grade("eval-branch-store-update-lock", run_dir, self.LOCKED)), [])

    def test_update_lock_with_a_removal_offer_fails(self):
        run_dir, _ = self.fixture("eval-branch-store-update-lock")
        res = self.grade("eval-branch-store-update-lock", run_dir,
                         "An update from C:/elsewhere/code holds the store. Rerun the update there, or confirm and I will remove the lock.")
        self.assertEqual(self.failed(res), ["The report does not offer to remove the lock"])

    def test_update_lock_report_without_the_rerun_or_the_checkout_fails(self):
        run_dir, _ = self.fixture("eval-branch-store-update-lock")
        res = self.grade("eval-branch-store-update-lock", run_dir, "The store is locked by another session.")
        self.assertEqual(self.failed(res), ["The report names the update and its checkout C:/elsewhere/code",
                                           "The report says to rerun the update from that checkout"])

    def test_update_lock_removed_or_branch_created_fails(self):
        run_dir, repo = self.fixture("eval-branch-store-update-lock")
        fixtures.rmtree(self.lock_dir(repo))
        self.branch_both(repo)
        failed = self.failed(self.grade("eval-branch-store-update-lock", run_dir, self.LOCKED))
        self.assertIn("The update's gate lock and its owner file are still there, unchanged", failed)
        self.assertIn("Both repos are still on main with only the main branch and no new commit", failed)


class InstallLatestTagPredatesScript(unittest.TestCase):
    """eval-install-latest-tag-predates-script: the highest tag is v0.5.0, so the update stops before staging and offers main."""

    NAME = "eval-install-latest-tag-predates-script"
    GOOD = ("Stopped before staging: the latest release tag is v0.5.0, and this update needs the minimum release 0.6.0 "
            "(v0.5.0 has no update script). Shall I install main instead? No file was written.")

    def fixture(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo"
        fixtures.build(self.NAME, repo)
        return repo

    def results(self, repo, report):
        return {t: ok for t, ok, _ in grade.check_install(self.NAME, repo, repo / "code", repo / "store", report.lower())}

    def assertions(self):
        evals = json.loads((Path(__file__).resolve().parent / "evals.json").read_text(encoding="utf-8"))["evals"]
        return next(e["assertions"] for e in evals if e["name"] == self.NAME)

    def failed(self, res):
        return sorted(t for t, ok in res.items() if not ok)

    def test_fixture_source_has_only_the_old_tag(self):
        repo = self.fixture()
        src = repo / "specwright-src"
        self.assertEqual(grade.git(src, "tag", "--list").split(), ["v0.5.0"])
        self.assertIsNone(grade.git(src, "cat-file", "-e", "v0.5.0:scripts/update.sh"))
        self.assertIsNotNone(grade.git(src, "cat-file", "-e", "main:scripts/update.sh"))
        self.assertEqual(grade.git(src, "show", "v0.5.0:VERSION").strip(), "0.5.0")

    def test_stop_that_writes_nothing_passes_every_check(self):
        res = self.results(self.fixture(), self.GOOD)
        self.assertEqual(sorted(res), sorted(self.assertions()))
        self.assertEqual(self.failed(res), [])

    def test_install_of_the_old_tag_fails(self):
        repo = self.fixture()
        fixtures.write(repo / "code", ".claude/skills/specwright-commit/SKILL.md", "x\n")
        fixtures.write(repo / "code", "openspec/.specwright/VERSION", "0.5.0\n")
        res = self.results(repo, "Installation complete. Specwright v0.5.0 installed.")
        for t in ("No skill, agent, schema or specwright.yaml was written in either repo, and both trees are unchanged",
                  "openspec/.specwright/VERSION is absent", "The report does not say the install completed"):
            self.assertIn(t, self.failed(res))

    def test_staging_left_behind_fails(self):
        repo = self.fixture()
        fixtures.write(repo / "code", ".claude/.specwright-update-skills/new/x.md", "x\n")
        res = self.results(repo, self.GOOD)
        self.assertIn("No staging directory (.specwright-update-*) exists in either repo", self.failed(res))

    def test_report_without_the_tag_the_minimum_or_the_main_offer_fails(self):
        repo = self.fixture()
        res = self.results(repo, "Cannot install: the update script is missing. Nothing was written.")
        self.assertEqual(self.failed(res), ["The report names the latest tag v0.5.0 and the minimum release 0.6.0",
                                           "The report offers to install main"])
        res = self.results(repo, "Latest tag v0.5.0 is below the minimum release 0.6.0. I will install main now.")
        self.assertEqual(self.failed(res), ["The report offers to install main"])

    def test_source_repo_changed_fails(self):
        repo = self.fixture()
        fixtures.git(repo / "specwright-src", "tag", "v0.6.0", "main")
        self.assertEqual(self.failed(self.results(repo, self.GOOD)),
                         ["The Specwright source repo is unchanged: its only tag is still v0.5.0 and its tree is clean"])


class ImplementerLightPacket(unittest.TestCase):
    """eval-implementer-light-packet: a scripted good run grades green, and a run that committed, ticked, strayed or reported no evidence grades red."""
    NAME = "eval-implementer-light-packet"
    GOOD = ("- STATUS: DONE\n- Files changed: greet.py, test_greet.py\n"
            "- Tests: test_greet_named, test_greet_empty, test_farewell_named, test_farewell_empty -> red-confirmed, then passing\n"
            "  - red: `python -m unittest -q` failed with ImportError: cannot import name 'greet' before the implementation\n"
            "  - green: `python -m unittest -q` Ran 4 tests, OK, after it\n- Skills: none named\n- Processes: none started\n- Notes: none\n")

    def fixture(self, report=GOOD, implement=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(lambda: fixtures.rmtree(tmp.name))
        self.addCleanup(tmp.cleanup)
        self.run_dir = Path(tmp.name) / "run"
        repo = self.run_dir / "repo"
        fixtures.build(self.NAME, repo)
        (self.run_dir / "outputs").mkdir()
        (self.run_dir / "outputs" / "report.md").write_text(report, encoding="utf-8")
        if implement:
            fixtures.task_code(repo, "1.2")  # greet.py and test_greet.py final; README.md back to its committed text
        return repo

    def failed(self, repo):
        res = grade.check(self.NAME, repo, self.run_dir)
        return [t for t, ok, _ in res if not ok]

    def test_evals_json_lists_the_graders_assertions(self):
        repo = self.fixture()
        res = grade.check(self.NAME, repo, self.run_dir)
        evals = {e["name"]: e for e in json.loads((Path(__file__).resolve().parent / "evals.json").read_text(encoding="utf-8"))["evals"]}
        self.assertEqual([t for t, _, _ in res], evals[self.NAME]["assertions"])
        self.assertEqual(evals[self.NAME]["stress"], "implementer")

    def test_fixture_starts_planned_with_nothing_implemented(self):
        repo = self.fixture(implement=False)
        self.assertEqual(grade.subjects(repo, "main..HEAD"), [grade.PLAN_SUBJECT])
        self.assertEqual(grade.status_of(repo), [])
        self.assertNotIn("test_greet_named", (repo / "test_greet.py").read_text(encoding="utf-8"))
        self.assertIn("TIER: LIGHT", (repo / grade.CHANGE / "design.md").read_text(encoding="utf-8"))

    def test_scripted_good_run_passes_every_check(self):
        self.assertEqual(self.failed(self.fixture()), [])

    def test_a_run_that_implemented_nothing_fails(self):
        failed = self.failed(self.fixture(implement=False))
        self.assertIn("test_greet.py defines all four test-map tests and the test suite passes", failed)

    def test_a_run_that_committed_fails(self):
        repo = self.fixture()
        fixtures.git(repo, "add", "-A")
        fixtures.git(repo, "commit", "-q", "-m", "feat(add-greeting): task 1.1 Add greet(name)")
        failed = self.failed(repo)
        for t in ("Still on feat/add-greeting, main is unchanged and the branch holds only the planning commit",
                  "No commit was made and none amended"):
            self.assertIn(t, failed)

    def test_a_run_that_staged_fails(self):
        repo = self.fixture()
        fixtures.git(repo, "add", "-A")
        self.assertEqual(self.failed(repo), ["Only greet.py and test_greet.py changed, and nothing is staged"])

    def test_a_run_that_ticked_a_task_fails(self):
        repo = self.fixture()
        fixtures.write(repo, f"{grade.CHANGE}/tasks.md", (repo / grade.CHANGE / "tasks.md").read_text(encoding="utf-8").replace("- [ ] 1.1 ", "- [x] 1.1 "))
        self.assertEqual(self.failed(repo), ["tasks.md has no ticked task and the test map states are unchanged",
                                             "Only greet.py and test_greet.py changed, and nothing is staged"])

    def test_a_run_that_changed_the_test_map_state_fails(self):
        repo = self.fixture()
        p = repo / grade.CHANGE / "tasks.md"
        fixtures.write(repo, f"{grade.CHANGE}/tasks.md", p.read_text(encoding="utf-8").replace("| red |", "| green |", 1))
        self.assertIn("tasks.md has no ticked task and the test map states are unchanged", self.failed(repo))

    def test_a_run_that_touched_a_file_outside_the_group_fails(self):
        repo = self.fixture()
        fixtures.write(repo, "README.md", "# greeter\n\nrewritten\n")
        self.assertEqual(self.failed(repo), ["Only greet.py and test_greet.py changed, and nothing is staged"])

    def test_report_without_red_or_green_evidence_fails(self):
        no_red = "- STATUS: DONE\n- Tests: test_greet_named -> passing\n  - `python -m unittest -q` Ran 4 tests, OK\n"
        self.assertEqual(self.failed(self.fixture(no_red)), ["The report gives red evidence: a failing run before the implementation"])
        no_green = "- STATUS: DONE\n- Tests: test_greet_named -> red-confirmed\n  - `python -m unittest -q` failed before the implementation\n"
        self.assertEqual(self.failed(self.fixture(no_green)), ["The report gives green evidence: a passing run of the group's tests"])

    def test_negation_inside_quoted_error_text_still_counts_as_red(self):
        rep = ("- STATUS: DONE\n- Tests: test_greet_named -> red-confirmed, then passing\n"
               "  1. `python -m unittest -q` -> FAILED (errors=2): `AttributeError: module 'greet' has no attribute 'greet'`\n"
               "  2. `python -m unittest -q` -> Ran 4 tests, OK\n")
        self.assertEqual(self.failed(self.fixture(rep)), [])
        negated = "- STATUS: DONE\n  - `python -m unittest -q` did not fail\n  - `python -m unittest -q` Ran 4 tests, OK\n"
        self.assertIn("The report gives red evidence: a failing run before the implementation", self.failed(self.fixture(negated)))

    def test_a_blocked_or_missing_status_fails(self):
        rest = self.GOOD.split("\n", 1)[1]
        for rep in ("- STATUS: BLOCKED\n" + rest, "no status line\n" + rest):
            self.assertEqual(self.failed(self.fixture(rep)), ["The report states STATUS: DONE"], rep)


# ---- group-mode apply and recovery (change commit-per-task-group, task 5.1) ----
# These tests fix the contract of the grader checks added in task 5.2: each check's text is a constant below.
# They simulate what an agent run leaves behind (commits, a report) on the fixtures of fixtures.py and grade it
# with grade.check / grade.check_store. The grader must read evidence with its own parsing of `git log` subjects and
# `git interpret-trailers --parse` (review S3), never by calling task-cover.sh, so the graded result does not depend on
# the script under evaluation.
CHANGE_TASKS = f"{grade.CHANGE}/tasks.md"
DESIGN = f"{grade.CHANGE}/design.md"

# eval-apply-groups
G_TWO = "Exactly two task-work commits: group 1 with trailers 1.1, 1.2 and 1.3 in order, then group 2 with trailers 2.1 and 2.2"
G_SHARED = "greet.py appears in the group 1 commit only, and no commit holds part of group 1's work"
G_SCRATCH = "scratch-notes.txt was never committed and is still untracked"
G_COVER = "Every task is covered by exactly one commit and no trailer names a task outside its commit's group"
G_REPORT = "The report gives 5 tasks, 2 task-work commits, tree clean"
# eval-apply-groups-ten
T_ONE = "The group 1 commit carries trailers 1.1 and 1.2 only, and its tasks.md diff ticks only 1.1 and 1.2"
T_TEN = "The group 10 commit carries trailer 10.1 only and ticks only 10.1"
# eval-apply-groups-resume
R_ONE = "Exactly one group 1 commit carries trailers 1.1, 1.2 and 1.3, and its tasks.md diff ticks exactly 1.1, 1.2 and 1.3"
R_BODY = "The group 1 commit body says task 1.1's original red output is unavailable"
R_PLAN = "The planning commit holds design.md and no tick: the ticks reach Git only in the group 1 commit"
# eval-apply-groups-switch
S_KEEP = "The task 1.1 commit keeps its SHA on the branch"
S_G1 = "The group 1 commit carries trailers 1.2 and 1.3 only, and no task is covered twice"
S_G2 = "The group 2 commit carries trailers 2.1 and 2.2"
S_MIX = "The report says group 1 mixes per-task and group commits"
# eval-store-apply-groups
SP_PAIR = "Each group has one code commit and one store commit with the identical message: subject and trailers"
SP_TICKS = "Each store group commit touches only tasks.md and its diff ticks exactly its group's tasks"
SP_REPORT = "The report's completion check gives the task-work commits and a clean tree separately for the code repo and the store"
# eval-store-group-code-half, -store-half, -noop
CH_PAIR = "The code repo gets one group 1 commit, then the store one with the same message, and the store's tasks.md diff ticks exactly 1.1, 1.2 and 1.3"
CH_KEPT = "No tick is lost: 1.1, 1.2 and 1.3 are ticked in the store, and both trees are clean"
SH_STORE = "The store gets one commit with the code commit's subject and trailers, and its tasks.md diff ticks exactly 1.1, 1.2 and 1.3"
SH_NODUP = "The code repo has exactly one group 1 commit"
NG_CODE = "The code repo has no group 3 commit and its tree is clean"
NG_ASK = "The report names group 3 and asks whether it changed code"
NG_STORE = "A group 3 commit in the store has Code-Changes: none before the trailers 3.1 and 3.2 and ticks exactly 3.1 and 3.2; without one, both ticks are still uncommitted"
# eval-apply-three-tasks (task mode)
NO_TRAILER = "No commit carries a Specwright-Task trailer"

GROUPS_REPORT = "Applied 5 tasks in 2 groups.\n\n5 tasks, 2 task-work commits, tree clean (scratch-notes.txt was already there).\n"
STORE_REPORT = ("Applied 5 tasks in 2 groups, each committed in the code repo and then in the store.\n\n"
                "- code: 5 tasks, 2 task-work commits, tree clean\n- store: 5 tasks, 2 task-work commits, tree clean\n")
RED_BODY = "Task 1.1 was ticked before an interruption; its original red output is unavailable. test_greet_named now passes."


class GroupGraderCase(unittest.TestCase):
    def fixture(self, name, report=""):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(lambda: fixtures.rmtree(tmp.name))
        self.addCleanup(tmp.cleanup)
        self.name = name
        self.run_dir = Path(tmp.name) / "run"
        self.repo = self.run_dir / "repo"
        fixtures.build(name, self.repo)
        (self.run_dir / "outputs").mkdir()
        self.report(report)
        return self.repo

    def report(self, text):
        (self.run_dir / "outputs" / "report.md").write_text(text, encoding="utf-8")

    def results(self):
        fn = grade.check_store if grade.is_store_run(self.repo) else grade.check
        return {t: (ok, ev) for t, ok, ev in fn(self.name, self.repo, self.run_dir)}

    def failed(self):
        return [t for t, (ok, _) in self.results().items() if not ok]

    def assert_passes(self):
        res = self.results()
        self.assertTrue(res, f"grade.check returned no checks for {self.name}")
        self.assertEqual([(t, ev) for t, (ok, ev) in res.items() if not ok], [])

    def assert_fails(self, text):
        res = self.results()
        self.assertIn(text, res, f"{self.name} has no check {text!r}: {sorted(res)}")
        self.assertFalse(res[text][0], f"{self.name}: {text!r} passed on a run that should fail it: {res[text][1]}")


def commit_paths(root, msg, *paths):
    """Commit exactly `paths` (staged by name) in `root` with `msg`."""
    fixtures.git(root, "add", "--", *paths)
    fixtures.git(root, "commit", "-q", "-m", msg, "--", *paths)


def two_groups(repo, kind="groups"):
    fixtures.plan_commit(repo)
    fixtures.commit_group(repo, repo, kind, 1)
    fixtures.commit_group(repo, repo, kind, 2)


class GroupApply(GroupGraderCase):
    """eval-apply-groups: group mode on a 5-task change (1.1-1.3 share greet.py, 2.1-2.2), scratch-notes.txt untracked."""
    NAME = "eval-apply-groups"

    def test_group_apply_two_commits_pass(self):
        repo = self.fixture(self.NAME, GROUPS_REPORT)
        two_groups(repo)
        self.assert_passes()
        res = self.results()
        for t in (G_TWO, G_SHARED, G_SCRATCH, G_COVER, G_REPORT):
            self.assertIn(t, res)

    def test_group_apply_per_task_commits_fail(self):
        repo = self.fixture(self.NAME, GROUPS_REPORT.replace("2 task-work", "5 task-work"))
        fixtures.plan_commit(repo)
        for n in (1, 2):
            paths = fixtures.group_code(repo, n)
            for i, t in enumerate(fixtures.group_spec("groups", n)[1]):
                fixtures.tick(repo, t)
                commit_paths(repo, f"feat(add-greeting): task {t} Do it", CHANGE_TASKS, *(paths if i == 0 else []))
        self.assert_fails(G_TWO)

    def test_group_apply_split_group_fails(self):
        repo = self.fixture(self.NAME, GROUPS_REPORT)
        fixtures.plan_commit(repo)
        fixtures.task_code(repo, "1.2")
        fixtures.tick(repo, "1.1", "1.2")
        commit_paths(repo, fixtures.group_msg("groups", 1, ["1.1", "1.2"]), "greet.py", "test_greet.py", CHANGE_TASKS)
        fixtures.group_code(repo, 1)  # task 1.3 changes greet.py again, in a second group 1 commit
        fixtures.tick(repo, "1.3")
        commit_paths(repo, fixtures.group_msg("groups", 1, ["1.3"]), "greet.py", CHANGE_TASKS)
        fixtures.commit_group(repo, repo, "groups", 2)
        self.assert_fails(G_SHARED)

    def test_group_apply_swept_scratch_fails(self):
        repo = self.fixture(self.NAME, GROUPS_REPORT)
        fixtures.plan_commit(repo)
        paths = fixtures.group_code(repo, 1)
        fixtures.tick(repo, "1.1", "1.2", "1.3")
        commit_paths(repo, fixtures.group_msg("groups", 1), CHANGE_TASKS, "scratch-notes.txt", *paths)
        fixtures.commit_group(repo, repo, "groups", 2)
        self.assert_fails(G_SCRATCH)

    def test_grader_matches_evidence_without_task_cover(self):
        """Review S3: the grader parses `git log` and `git interpret-trailers` itself. This guard is green by design."""
        src = (Path(__file__).resolve().parent / "grade.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"""["'][^"'\s]*task-cover""", src))


class GroupApplyTen(GroupGraderCase):
    """eval-apply-groups-ten: groups 1 (1.1, 1.2) and 10 (10.1); `10.1` is not a task of group 1."""
    NAME = "eval-apply-groups-ten"

    def test_group_ten_pass(self):
        repo = self.fixture(self.NAME)
        fixtures.plan_commit(repo)
        fixtures.commit_group(repo, repo, "ten", 1)
        fixtures.commit_group(repo, repo, "ten", 10)
        self.assert_passes()
        res = self.results()
        for t in (T_ONE, T_TEN):
            self.assertIn(t, res)

    def test_group_ten_tick_in_group_one_fails(self):
        repo = self.fixture(self.NAME)
        fixtures.plan_commit(repo)
        fixtures.tick(repo, "10.1")  # task 10.1's tick rides along in the group 1 commit, whose trailers are right
        fixtures.commit_group(repo, repo, "ten", 1)
        fixtures.commit_group(repo, repo, "ten", 10)
        self.assert_fails(T_ONE)


class GroupApplyResume(GroupGraderCase):
    """eval-apply-groups-resume: 1.1 (red step) and 1.2 ticked with work uncommitted, 1.3 open, design.md edited."""
    NAME = "eval-apply-groups-resume"

    def finish(self, body=RED_BODY, design_with_ticks=False):
        repo = self.repo
        fixtures.git(repo, "add", "--", *([DESIGN, CHANGE_TASKS] if design_with_ticks else [DESIGN]))
        fixtures.git(repo, "commit", "-q", "-m", "docs(add-greeting): amend design")
        fixtures.commit_group(repo, repo, "resume", 1, body=body)

    def test_group_resume_one_commit_pass(self):
        self.fixture(self.NAME, "Resumed group 1: re-ran test_greet_named (passes), finished 1.3, one group 1 commit.\n")
        self.finish()
        self.assert_passes()
        res = self.results()
        for t in (R_ONE, R_BODY, R_PLAN):
            self.assertIn(t, res)

    def test_group_resume_body_names_red_step(self):
        self.fixture(self.NAME, "Resumed group 1.\n")
        self.finish(body="Finished the group after an interruption.")
        self.assert_fails(R_BODY)

    def test_group_resume_planning_commit_without_ticks(self):
        self.fixture(self.NAME, "Resumed group 1.\n")
        self.finish(design_with_ticks=True)  # the planning commit staged tasks.md with the pending 1.1 and 1.2 ticks
        self.assert_fails(R_PLAN)


class GroupApplySwitch(GroupGraderCase):
    """eval-apply-groups-switch: task 1.1 committed per task before commit_granularity became group."""
    NAME = "eval-apply-groups-switch"
    REPORT = "Group 1 mixes per-task and group commits: task 1.1 keeps its earlier commit, 1.2 and 1.3 are in the group 1 commit.\n"

    def test_group_switch_mixed_pass(self):
        repo = self.fixture(self.NAME, self.REPORT)
        fixtures.commit_group(repo, repo, "groups", 1, tasks=["1.2", "1.3"])
        fixtures.commit_group(repo, repo, "groups", 2)
        self.assert_passes()
        res = self.results()
        for t in (S_KEEP, S_G1, S_G2, S_MIX):
            self.assertIn(t, res)

    def test_group_switch_rewritten_task_commit_fails(self):
        repo = self.fixture(self.NAME, self.REPORT)
        fixtures.git(repo, "reset", "-q", "--soft", "HEAD~1")  # drops the task 1.1 commit: regrouped into one group 1 commit
        fixtures.commit_group(repo, repo, "groups", 1)
        fixtures.commit_group(repo, repo, "groups", 2)
        self.assert_fails(S_KEEP)


class StoreGroupApply(GroupGraderCase):
    """eval-store-apply-groups: group mode with the planning in a store; each group is a code commit and a store commit."""
    NAME = "eval-store-apply-groups"

    def test_store_group_pair_pass(self):
        self.fixture(self.NAME, STORE_REPORT)
        code, store = self.repo / "code", self.repo / "store"
        fixtures.plan_commit(store)
        fixtures.commit_group(code, store, "groups", 1)
        fixtures.commit_group(code, store, "groups", 2)
        self.assert_passes()
        res = self.results()
        for t in (SP_PAIR, SP_TICKS, SP_REPORT):
            self.assertIn(t, res)

    def test_store_group_message_mismatch_fails(self):
        self.fixture(self.NAME, STORE_REPORT)
        code, store = self.repo / "code", self.repo / "store"
        fixtures.plan_commit(store)
        paths = fixtures.group_code(code, 1)
        commit_paths(code, fixtures.group_msg("groups", 1), *paths)
        fixtures.tick(store, "1.1", "1.2", "1.3")
        commit_paths(store, fixtures.group_msg("groups", 1, ["1.1", "1.2"]), CHANGE_TASKS)  # the store message lost trailer 1.3
        fixtures.commit_group(code, store, "groups", 2)
        self.assert_fails(SP_PAIR)


class StoreGroupRecovery(GroupGraderCase):
    def test_store_group_code_half_pass(self):
        self.fixture("eval-store-group-code-half", "Verified 1.1 to 1.3 again, committed group 1 in the code repo, then in the store.\n")
        code, store = self.repo / "code", self.repo / "store"
        fixtures.commit_group(code, store, "groups", 1)
        self.assert_passes()
        res = self.results()
        for t in (CH_PAIR, CH_KEPT):
            self.assertIn(t, res)

    def test_store_group_code_half_lost_tick_fails(self):
        self.fixture("eval-store-group-code-half", "Committed group 1.\n")
        code, store = self.repo / "code", self.repo / "store"
        paths = fixtures.group_code(code, 1)
        commit_paths(code, fixtures.group_msg("groups", 1), *paths)
        text = (store / CHANGE_TASKS).read_text(encoding="utf-8").replace("- [x] 1.2 ", "- [ ] 1.2 ")  # a tick was removed
        fixtures.write(store, CHANGE_TASKS, text)
        commit_paths(store, fixtures.group_msg("groups", 1), CHANGE_TASKS)
        self.assert_fails(CH_KEPT)

    def test_store_group_store_half_pass(self):
        self.fixture("eval-store-group-store-half", "Group 1's code commit existed; committed its ticks in the store with the same message.\n")
        store = self.repo / "store"
        commit_paths(store, fixtures.group_msg("groups", 1), CHANGE_TASKS)
        self.assert_passes()
        res = self.results()
        for t in (SH_STORE, SH_NODUP):
            self.assertIn(t, res)

    def test_store_group_store_half_duplicate_code_fails(self):
        self.fixture("eval-store-group-store-half", "Committed group 1.\n")
        code, store = self.repo / "code", self.repo / "store"
        fixtures.git(code, "commit", "-q", "--allow-empty", "-m", fixtures.group_msg("groups", 1))  # a second group 1 code commit
        commit_paths(store, fixtures.group_msg("groups", 1), CHANGE_TASKS)
        self.assert_fails(SH_NODUP)

    ASK = "Group 3 is ticked in the store but neither repo has a group 3 commit and the code tree is clean. Did group 3 change any code?\n"

    def test_store_group_noop_asks_first(self):
        self.fixture("eval-store-group-noop", self.ASK)  # stops at the question: nothing committed
        self.assert_passes()
        res = self.results()
        for t in (NG_CODE, NG_ASK, NG_STORE):
            self.assertIn(t, res)
        self.report("Recorded group 3 in the store with Code-Changes: none.\n")  # it assumed a no-op instead of asking
        self.assert_fails(NG_ASK)

    def test_store_group_nocode_store_only_pass(self):
        self.fixture("eval-store-group-noop", self.ASK + "You said group 3 changed no code, so the store got the group 3 commit with Code-Changes: none.\n")
        code, store = self.repo / "code", self.repo / "store"
        fixtures.commit_group(code, store, "noop", 3, no_code=True)
        self.assert_passes()
        self.assertIn(NG_STORE, self.results())
        fixtures.git(code, "commit", "-q", "--allow-empty", "-m", fixtures.group_msg("noop", 3))  # a code commit for group 3
        self.assert_fails(NG_CODE)


class TaskModeNoTrailers(GroupGraderCase):
    """eval-apply-three-tasks (commit_granularity unset): the task commits carry no Specwright-Task trailer."""
    NAME = "eval-apply-three-tasks"

    def run_tasks(self, trailer=False):
        repo = self.fixture(self.NAME, "3 tasks, 3 task commits, tree clean (scratch-notes.txt was already there).\n")
        fixtures.plan_commit(repo)
        for t in grade.TASKS:
            fixtures.task_code(repo, t)
            fixtures.tick(repo, t)
            msg = fixtures.TASK_SUBJECT[t] + (f"\n\nSpecwright-Task: {t}\n" if trailer and t == "1.2" else "")
            commit_paths(repo, msg, "greet.py", "test_greet.py", "README.md", CHANGE_TASKS)

    def test_task_mode_run_has_no_trailers(self):
        self.run_tasks()
        res = self.results()
        self.assertIn(NO_TRAILER, res, sorted(res))
        self.assertTrue(res[NO_TRAILER][0], res[NO_TRAILER][1])
        self.assertEqual(self.failed(), [])
        self.run_tasks(trailer=True)
        self.assert_fails(NO_TRAILER)


class CompletionWording(unittest.TestCase):
    BOTH = {"commits", "clean"}

    def test_completion_accepts_task_work_wording(self):
        rep = "code: 5 tasks, 2 task-work commits, tree clean\nstore: 5 tasks, 2 task-work commits, tree clean\n"
        self.assertEqual(grade.completion_by_repo(rep), {"code": self.BOTH, "store": self.BOTH})
        old = "code: 3 task commits, tree clean\nstore: 3 task commits, tree clean\n"
        self.assertEqual(grade.completion_by_repo(old), {"code": self.BOTH, "store": self.BOTH})


if __name__ == "__main__":
    unittest.main()
