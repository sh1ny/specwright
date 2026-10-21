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
        self.writes("replace", "notes add", "reflog expire --all", "reflog delete HEAD@{0}", "frobnicate", "gc", "maintenance run",
                    "gc --prune=now", "config user.name x", "remote add o url", "stash push", "worktree add ../w", "")

    def test_fetch_into_local_branch_is_a_write(self):
        self.writes("fetch origin main:main", "fetch origin +refs/heads/x:refs/remotes/origin/x", "fetch origin feat/x:refs/heads/main",
                    "fetch origin tag v1")

    def test_reads_stay_reads(self):
        self.reads("status --porcelain", "log --oneline", "branch --show-current", "rev-parse HEAD", "fetch origin", "diff-tree",
                   "reflog", "reflog -n 5", "reflog --oneline", "reflog main", "reflog show", "reflog list",
                   "config --name-only --get-regexp x", "config get x", "config list", "config --list", "grep", "blame",
                   "symbolic-ref HEAD", "gc --auto --no-quiet --detach", "maintenance run --auto --no-quiet",
                   "fetch origin refs/heads/x:refs/remotes/origin/x", "upload-pack", "pack-objects", "remote -v", "stash list",
                   "worktree list", "tag", "ls-remote origin")

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
        children = [c for label, cmds in seen.items() for c in cmds[1:]]
        self.assertEqual(grade.changing_git([c for c in children if c[:1] != ["merge"]]), [], children)


class GraphqlOperations(unittest.TestCase):
    """`gh api graphql` calls are classified by the operations in the document, not by its first token."""

    def setUp(self):
        import gqlops  # the fakes dir is on sys.path through fixtures
        self.ops = gqlops.operations

    def changing(self, *argv):
        return grade.changing_gh([{"argv": ["api", "graphql", *argv]}])

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
        self.sh(repo, "git status --porcelain && git checkout -q main && git pull -q --ff-only && git fetch -q origin main --tags")

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
        self.sh(repo, "git fetch -q origin main --tags")
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
        self.sh(repo, "git checkout -q main && git pull -q --ff-only && git fetch -q origin main --tags")
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

    def test_agent_run_passes_every_check(self):
        run_dir, repo = self.fixture("eval-agent-merge-release-auto")
        self.agent_run(repo)
        res = self.grade("eval-agent-merge-release-auto", run_dir, PUBLISHED_REPORT)
        self.assertTrue(res and not self.failed(res), self.failed(res))

    def test_agent_run_that_releases_before_the_cleanup_fails(self):
        run_dir, repo = self.fixture("eval-agent-merge-release-auto")
        tip = grade.git(repo, "rev-parse", "HEAD")
        self.sh(repo, f"gh api -X PUT repos/acme/greeter/pulls/7/merge -f merge_method=squash -f sha={tip}")
        self.sh(repo, "git checkout -q main && git pull -q --ff-only && git fetch -q origin main --tags")
        self.publish(repo)
        self.sh(repo, "git branch -q -D feat/add-greeting")
        self.sh(repo, "gh api -X DELETE repos/acme/greeter/git/refs/heads/feat/add-greeting")
        res = self.grade("eval-agent-merge-release-auto", run_dir, PUBLISHED_REPORT)
        self.assertEqual(self.failed(res), [
            "The release came after the cleanup: the gh log has the merge, the remote branch DELETE, then the release create, and the tag push "
            "follows the pull and the local branch deletion (the git trace)"])

    def test_agent_run_without_a_release_or_a_report_line_fails(self):
        run_dir, repo = self.fixture("eval-agent-merge-release-auto")
        self.agent_run(repo, publish=False)
        res = self.grade("eval-agent-merge-release-auto", run_dir, "Merged #7. Next: specwright-roadmap next, or close the milestone?")
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


if __name__ == "__main__":
    unittest.main()
