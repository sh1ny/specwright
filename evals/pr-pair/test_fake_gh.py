"""Tests for the fake gh in evals/fakes/gh.py.

Run: python -m unittest discover evals/pr-pair
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
GH = HERE.parent / "fakes" / "gh.py"
sys.path.insert(0, str(HERE.parent / "git-workflow"))
import fixtures  # noqa: E402

_spec = importlib.util.spec_from_file_location("fake_gh", GH)
fake_gh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_gh)
JQ = shutil.which("gojq") or shutil.which("jq")  # the evaluator for filters the fake does not evaluate itself


class FakeGhCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state = self.tmp / "state.json"
        self.logf = self.tmp / "log.jsonl"
        self.seed({"user": "KintsugiBot", "tokens": {"KintsugiBot": "tok-k", "sh1ny": "tok-s"}})

    def seed(self, st):
        self.state.write_text(json.dumps(st), encoding="utf-8")

    def st(self):
        return json.loads(self.state.read_text(encoding="utf-8"))

    def gh(self, *args, env=None, check=True):
        e = {**os.environ, "FAKE_GH_STATE": str(self.state), "FAKE_GH_LOG": str(self.logf)}
        e.pop("GH_TOKEN", None)
        e.pop("GITHUB_TOKEN", None)
        e.pop("GH_REPO", None)
        e.update(env or {})
        r = subprocess.run([sys.executable, str(GH), *args], capture_output=True, text=True, env=e, cwd=self.tmp)
        if check:
            self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def pull(self, n, ref, owner="o", state="open", merged=None):
        return {"number": n, "html_url": f"https://github.com/o/n/pull/{n}", "state": state, "merged_at": merged,
                "title": f"t{n}", "body": "", "head": {"ref": ref, "label": f"{owner}:{ref}", "repo": {"full_name": f"{owner}/n"}},
                "base": {"ref": "main"}}


class Pulls(FakeGhCase):
    def test_pagination_30_vs_paginate(self):
        st = self.st()
        st["repos"] = {"o/n": {"pulls": [self.pull(i, f"b{i}") for i in range(1, 36)]}}
        self.seed(st)
        first = json.loads(self.gh("api", "repos/o/n/pulls?state=open").stdout)
        self.assertEqual(len(first), 30)
        out = self.gh("api", "--paginate", "repos/o/n/pulls?state=open").stdout
        dec, i, pages = json.JSONDecoder(), 0, []
        while i < len(out):
            obj, j = dec.raw_decode(out, i)
            pages.append(obj)
            i = j
            while i < len(out) and out[i].isspace():
                i += 1
        self.assertEqual([len(p) for p in pages], [30, 5])
        small = json.loads(self.gh("api", "repos/o/n/pulls?per_page=10").stdout)
        self.assertEqual(len(small), 10)

    def test_head_filter_excludes_forks_and_state(self):
        st = self.st()
        st["repos"] = {"o/n": {"pulls": [self.pull(1, "feat/x"), self.pull(2, "feat/x", owner="forker"),
                                         self.pull(3, "feat/x", state="closed", merged="2026-01-01T00:00:00Z"),
                                         self.pull(4, "other")]}}
        self.seed(st)
        nums = lambda q: sorted(p["number"] for p in json.loads(self.gh("api", f"repos/o/n/pulls?{q}").stdout))
        self.assertEqual(nums("state=open&head=o:feat/x"), [1])
        self.assertEqual(nums("state=all&head=o:feat/x"), [1, 3])
        self.assertEqual(nums("state=closed&head=forker:feat/x"), [])
        self.assertEqual(nums("state=open&head=forker:feat/x"), [2])

    def test_jq_simple_path(self):
        st = self.st()
        st["repos"] = {"o/n": {"pulls": [self.pull(1, "a"), self.pull(2, "b")]}}
        self.seed(st)
        r = self.gh("api", "repos/o/n/pulls", "--jq", ".[].html_url")
        self.assertEqual(r.stdout.split(), ["https://github.com/o/n/pull/2", "https://github.com/o/n/pull/1"])


class RoundTrip(FakeGhCase):
    def test_create_view_comment_patch(self):
        url = self.gh("pr", "create", "--repo", "o/n", "--head", "feat/y", "--base", "main",
                      "--title", "T", "--body", "B").stdout.strip()
        self.assertEqual(url, "https://github.com/o/n/pull/1")
        v = json.loads(self.gh("pr", "view", url, "--repo", "o/n", "--json", "number,url,state,headRefName,baseRefName,body,title").stdout)
        self.assertEqual(v, {"number": 1, "url": url, "state": "OPEN", "headRefName": "feat/y", "baseRefName": "main", "body": "B", "title": "T"})
        listed = json.loads(self.gh("api", "repos/o/n/pulls?head=o:feat/y").stdout)
        self.assertEqual((listed[0]["head"]["label"], listed[0]["html_url"]), ("o:feat/y", url))
        cu = self.gh("pr", "comment", "1", "--repo", "o/n", "--body", "marker <!-- x -->").stdout.strip()
        cs = json.loads(self.gh("api", "repos/o/n/issues/1/comments").stdout)
        self.assertEqual((len(cs), cs[0]["body"], cs[0]["html_url"]), (1, "marker <!-- x -->", cu))
        p = json.loads(self.gh("api", "-X", "PATCH", f"repos/o/n/issues/comments/{cs[0]['id']}", "-f", "body=edited").stdout)
        self.assertEqual(p["body"], "edited")
        self.assertEqual(json.loads(self.gh("api", "repos/o/n/issues/1/comments").stdout)[0]["body"], "edited")
        self.gh("pr", "edit", "1", "--repo", "o/n", "--body", "B2")
        self.assertEqual(self.st()["repos"]["o/n"]["pulls"][0]["body"], "B2")

    def test_body_file_and_input(self):
        (self.tmp / "b.md").write_text("from file", encoding="utf-8")
        self.gh("pr", "create", "--repo", "o/n", "--head", "f", "--base", "main", "--title", "T", "--body-file", str(self.tmp / "b.md"))
        self.assertEqual(self.st()["repos"]["o/n"]["pulls"][0]["body"], "from file")
        self.gh("pr", "comment", "1", "--repo", "o/n", "--body", "c")
        (self.tmp / "in.json").write_text('{"body": "via input"}', encoding="utf-8")
        cid = self.st()["repos"]["o/n"]["comments"]["1"][0]["id"]
        self.gh("api", "-X", "PATCH", f"repos/o/n/issues/comments/{cid}", "--input", str(self.tmp / "in.json"))
        self.assertEqual(self.st()["repos"]["o/n"]["comments"]["1"][0]["body"], "via input")

    def test_merged_pull_views_as_merged(self):
        st = self.st()
        st["repos"] = {"o/n": {"pulls": [self.pull(7, "m", state="closed", merged="2026-01-01T00:00:00Z")]}}
        self.seed(st)
        v = json.loads(self.gh("pr", "view", "7", "--repo", "o/n", "--json", "state").stdout)
        self.assertEqual(v["state"], "MERGED")

    def test_duplicate_open_pr_is_rejected(self):
        args = ("pr", "create", "--repo", "o/n", "--head", "f", "--base", "main", "--title", "T", "--body", "B")
        self.gh(*args)
        self.assertNotEqual(self.gh(*args, check=False).returncode, 0)

    def test_gh_repo_env_and_repo_view(self):
        self.gh("pr", "create", "--head", "f", "--base", "main", "--title", "T", "--body", "B", env={"GH_REPO": "o/n"})
        self.assertEqual(len(self.st()["repos"]["o/n"]["pulls"]), 1)
        out = self.gh("repo", "view", "o/n", "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name").stdout.strip()
        self.assertEqual(out, "main")


class Auth(FakeGhCase):
    def test_token_and_user(self):
        self.assertEqual(self.gh("auth", "token", "--hostname", "github.com", "--user", "sh1ny").stdout.strip(), "tok-s")
        self.assertNotEqual(self.gh("auth", "token", "--user", "nobody", check=False).returncode, 0)
        self.assertEqual(self.gh("api", "user", "--jq", ".login").stdout.strip(), "KintsugiBot")
        self.assertEqual(self.gh("api", "--hostname", "github.com", "user", "--jq", ".login", env={"GH_TOKEN": "tok-s"}).stdout.strip(), "sh1ny")
        self.assertNotEqual(self.gh("api", "user", env={"GH_TOKEN": "bogus"}, check=False).returncode, 0)


class LogAndFailures(FakeGhCase):
    def test_log_lines(self):
        self.gh("auth", "token", "--user", "sh1ny")
        self.gh("api", "user", env={"GH_REPO": "o/n"})
        lines = [json.loads(l) for l in self.logf.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([l["argv"] for l in lines], [["auth", "token", "--user", "sh1ny"], ["api", "user"]])
        self.assertEqual([l["gh_repo"] for l in lines], [None, "o/n"])
        self.assertEqual(Path(lines[0]["cwd"]).resolve(), self.tmp.resolve())

    def test_failure_injection(self):
        st = self.st()
        st["fail"] = [{"match": r"api repos/o/n/pulls", "exit": 4, "stderr": "boom"}]
        self.seed(st)
        r = self.gh("api", "repos/o/n/pulls?head=o:x", check=False)
        self.assertEqual((r.returncode, r.stderr.strip()), (4, "boom"))
        self.assertEqual(self.gh("api", "user").returncode, 0)
        self.assertEqual(len(self.logf.read_text(encoding="utf-8").splitlines()), 2)  # failed calls are logged too

    def test_unknown_command_exits_2(self):
        r = self.gh("release", "list", check=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn("unsupported", r.stderr)


class ReactionsAndGraphql(FakeGhCase):
    GQL_REACTIONS = ("query($id: ID!, $cursor: String) { node(id: $id) { ... on Reactable { "
                     "reactions(first: 100, content: %s, after: $cursor) { nodes { user { login } } "
                     "pageInfo { hasNextPage endCursor } } } } }")
    GQL_PR = ("query($owner: String!, $name: String!, $number: Int!) { repository(owner: $owner, name: $name) { "
              "defaultBranchRef { name } pullRequest(number: $number) { body baseRefName "
              "closingIssuesReferences(first: 100) { nodes { number repository { nameWithOwner } } "
              "pageInfo { hasNextPage } } } } }")

    def seeded(self):
        st = self.st()
        st["repos"] = {"o/n": {"pulls": [self.pull(7, "b7")]}}
        return st

    def paginated(self, out):
        dec, i, pages = json.JSONDecoder(), 0, []
        while i < len(out):
            obj, j = dec.raw_decode(out, i)
            pages.append(obj)
            i = j
            while i < len(out) and out[i].isspace():
                i += 1
        return pages

    def test_rest_review_comment_reactions_filter_and_paginate(self):
        st = self.seeded()
        for i in range(35):
            fake_gh.add_review_comment_reaction(st, "o/n", 55, f"u{i}", "+1")
        fake_gh.add_review_comment_reaction(st, "o/n", 55, "down", "-1")
        fake_gh.add_review_comment_reaction(st, "o/n", 56, "other", "+1")
        self.seed(st)
        first = json.loads(self.gh("api", "repos/o/n/pulls/comments/55/reactions").stdout)
        self.assertEqual(len(first), 30)
        self.assertEqual(first[0], {"user": {"login": "u0"}, "content": "+1"})
        pages = self.paginated(self.gh("api", "--paginate", "repos/o/n/pulls/comments/55/reactions").stdout)
        self.assertEqual([len(p) for p in pages], [30, 6])
        down = json.loads(self.gh("api", "repos/o/n/pulls/comments/55/reactions?content=-1").stdout)
        self.assertEqual([r["user"]["login"] for r in down], ["down"])
        self.assertEqual(self.gh("api", "repos/o/n/pulls/comments/99/reactions").stdout.strip(), "[]")

    def test_graphql_node_reactions_paged(self):
        st = self.seeded()
        st["graphql_page_size"] = 2
        for login in ("a", "b", "c"):
            fake_gh.add_node_reaction(st, "o/n", "NODE1", login, "THUMBS_UP")
        fake_gh.add_node_reaction(st, "o/n", "NODE1", "d", "THUMBS_DOWN")
        self.seed(st)
        r1 = json.loads(self.gh("api", "graphql", "-f", "query=" + self.GQL_REACTIONS % "THUMBS_UP", "-f", "id=NODE1").stdout)
        rx = r1["data"]["node"]["reactions"]
        self.assertEqual([n["user"]["login"] for n in rx["nodes"]], ["a", "b"])
        self.assertTrue(rx["pageInfo"]["hasNextPage"])
        r2 = json.loads(self.gh("api", "graphql", "-f", "query=" + self.GQL_REACTIONS % "THUMBS_UP", "-f", "id=NODE1",
                                "-f", "cursor=" + rx["pageInfo"]["endCursor"]).stdout)
        rx2 = r2["data"]["node"]["reactions"]
        self.assertEqual([n["user"]["login"] for n in rx2["nodes"]], ["c"])
        self.assertEqual(rx2["pageInfo"], {"hasNextPage": False, "endCursor": None})
        down = json.loads(self.gh("api", "graphql", "-f", "query=" + self.GQL_REACTIONS % "THUMBS_DOWN", "-f", "id=NODE1").stdout)
        self.assertEqual([n["user"]["login"] for n in down["data"]["node"]["reactions"]["nodes"]], ["d"])
        none = json.loads(self.gh("api", "graphql", "-f", "query=" + self.GQL_REACTIONS % "THUMBS_UP", "-f", "id=NOPE").stdout)
        self.assertIsNone(none["data"]["node"])

    def node_query(self, node="NODE1", env=None, check=True):
        return self.gh("api", "graphql", "-f", "query=" + self.GQL_REACTIONS % "THUMBS_UP", "-f", "id=" + node, env=env, check=check)

    def test_graphql_node_reactions_check_credentials(self):
        st = self.seeded()
        st["tokens"] = {"KintsugiBot": "tok-k"}
        fake_gh.add_node_reaction(st, "o/n", "NODE1", "a", "THUMBS_UP")
        self.seed(st)
        other = self.gh("api", "user", env={"GH_TOKEN": "bogus"}, check=False)  # the failure every credentialed read gives
        self.assertEqual(other.returncode, 1)
        for node in ("NODE1", "NOPE"):  # credentials are checked before the node is looked up
            r = self.node_query(node, env={"GH_TOKEN": "bogus"}, check=False)
            self.assertEqual((r.returncode, r.stdout), (other.returncode, ""), f"a bad token read node {node}: {r.stdout}")
            self.assertEqual(r.stderr, other.stderr, "a bad token fails differently from the other reads")
        self.assertEqual(json.loads(self.node_query(env={"GH_TOKEN": "tok-k"}).stdout)["data"]["node"]["reactions"]["nodes"],
                         [{"user": {"login": "a"}}])

    def test_graphql_node_reactions_apply_the_reader_check(self):
        st = self.seeded()
        st["repos"]["o/n"]["readers"] = ["sh1ny"]  # the default user is KintsugiBot
        fake_gh.add_node_reaction(st, "o/n", "NODE1", "a", "THUMBS_UP")
        self.seed(st)
        r = self.node_query(check=False)
        self.assertEqual(r.returncode, 1, f"GraphQL answered a login that cannot read the node's repository: {r.stdout}")
        self.assertIn("Could not resolve", r.stderr)
        self.assertEqual(self.node_query("NOPE", check=False).stdout.strip().count("reactions"), 0)
        st["user"] = "sh1ny"
        self.seed(st)
        self.assertEqual(json.loads(self.node_query().stdout)["data"]["node"]["reactions"]["nodes"], [{"user": {"login": "a"}}])

    def test_graphql_pr_closing_refs_and_default_branch(self):
        st = self.seeded()
        st["repos"]["o/n"]["pulls"][0]["body"] = "Fixes #3"
        fake_gh.set_default_branch(st, "o/n", "trunk")
        fake_gh.set_closing_refs(st, "o/n", 7, [(3, "o/n"), (4, "x/y")], has_next=True)
        self.seed(st)
        args = ("api", "graphql", "-f", "query=" + self.GQL_PR, "-f", "owner=o", "-f", "name=n", "-F", "number=7")
        repo = json.loads(self.gh(*args).stdout)["data"]["repository"]
        self.assertEqual(repo["defaultBranchRef"], {"name": "trunk"})
        pr = repo["pullRequest"]
        self.assertEqual((pr["body"], pr["baseRefName"]), ("Fixes #3", "main"))
        self.assertEqual(pr["closingIssuesReferences"], {
            "nodes": [{"number": 3, "repository": {"nameWithOwner": "o/n"}},
                      {"number": 4, "repository": {"nameWithOwner": "x/y"}}],
            "pageInfo": {"hasNextPage": True}})
        fake_gh.set_closing_refs(st, "o/n", 7, [], has_next=False)
        self.seed(st)
        pr = json.loads(self.gh(*args).stdout)["data"]["repository"]["pullRequest"]
        self.assertEqual(pr["closingIssuesReferences"], {"nodes": [], "pageInfo": {"hasNextPage": False}})

    def test_graphql_repository_applies_the_reader_check(self):
        st = self.seeded()
        st["repos"]["o/n"]["readers"] = ["sh1ny"]  # the default user is KintsugiBot
        self.seed(st)
        args = ("api", "graphql", "-f", "query=" + self.GQL_PR, "-f", "owner=o", "-f", "name=n", "-F", "number=7")
        rest = self.gh("api", "repos/o/n/pulls", check=False)
        self.assertEqual(rest.returncode, 1, "the REST path rejects a login that cannot read the repository")
        r = self.gh(*args, check=False)
        self.assertEqual(r.returncode, 1, f"GraphQL answered a login that cannot read the repository: {r.stdout}")
        self.assertIn("Could not resolve to a Repository", r.stderr)
        st["user"] = "sh1ny"
        self.seed(st)
        self.assertEqual(self.gh(*args).returncode, 0)

    def test_graphql_reports_has_next_page_when_more_than_100_refs_are_seeded(self):
        st = self.seeded()
        fake_gh.set_closing_refs(st, "o/n", 7, [(n, "o/n") for n in range(1, 102)], has_next=False)  # no explicit flag
        self.seed(st)
        args = ("api", "graphql", "-f", "query=" + self.GQL_PR, "-f", "owner=o", "-f", "name=n", "-F", "number=7")
        refs = json.loads(self.gh(*args).stdout)["data"]["repository"]["pullRequest"]["closingIssuesReferences"]
        self.assertEqual(len(refs["nodes"]), 100)
        self.assertTrue(refs["pageInfo"]["hasNextPage"])
        fake_gh.set_closing_refs(st, "o/n", 7, [(n, "o/n") for n in range(1, 101)], has_next=False)
        self.seed(st)
        refs = json.loads(self.gh(*args).stdout)["data"]["repository"]["pullRequest"]["closingIssuesReferences"]
        self.assertEqual((len(refs["nodes"]), refs["pageInfo"]["hasNextPage"]), (100, False))

    GQL_CLOSED_PR = ("query($owner: String!, $name: String!, $number: Int!) { repository(owner: $owner, name: $name) { "
                     "defaultBranchRef { name } pullRequest(number: $number) { state url body baseRefName mergedAt } } }")
    GQL_ISSUE = ("query($owner: String!, $name: String!, $number: Int!) { repository(owner: $owner, name: $name) { "
                 "issue(number: $number) { state timelineItems(last: 1, itemTypes: [CLOSED_EVENT]) "
                 "{ nodes { ... on ClosedEvent { createdAt } } } } } }")

    def gql(self, query, owner, name, number, check=True):
        return self.gh("api", "graphql", "-f", "query=" + query, "-f", f"owner={owner}", "-f", f"name={name}",
                       "-F", f"number={number}", check=check)

    def test_graphql_pr_state_and_url(self):
        st = self.seeded()
        st["repos"]["o/n"]["pulls"] += [self.pull(8, "b8", state="closed"), self.pull(9, "b9", state="closed", merged="2026-10-08T10:00:00Z")]
        self.seed(st)
        got = {n: json.loads(self.gql(self.GQL_CLOSED_PR, "o", "n", n).stdout)["data"]["repository"]["pullRequest"] for n in (7, 8, 9)}
        self.assertEqual([got[n]["state"] for n in (7, 8, 9)], ["OPEN", "CLOSED", "MERGED"])
        self.assertEqual(got[9]["url"], "https://github.com/o/n/pull/9")
        self.assertEqual(got[9]["baseRefName"], "main")
        self.assertEqual((got[7]["mergedAt"], got[9]["mergedAt"]), (None, "2026-10-08T10:00:00Z"))

    def test_graphql_issue_state_and_close_history(self):
        st = self.seeded()
        fake_gh.set_issue(st, "o/n", 1, "OPEN")
        fake_gh.set_issue(st, "o/n", 2, "CLOSED", ["CLOSED"])
        fake_gh.set_issue(st, "o/n", 3, "OPEN", [("CLOSED", "2026-10-01T00:00:00Z"), "REOPENED", ("CLOSED", "2026-10-05T00:00:00Z"),
                                                 "REOPENED"])
        self.seed(st)
        got = {n: json.loads(self.gql(self.GQL_ISSUE, "o", "n", n).stdout)["data"]["repository"]["issue"] for n in (1, 2, 3)}
        self.assertEqual(got[1], {"state": "OPEN", "timelineItems": {"nodes": []}})
        self.assertEqual(got[2], {"state": "CLOSED", "timelineItems": {"nodes": [{"createdAt": fake_gh.CLOSE_AT}]}})
        self.assertEqual(got[3], {"state": "OPEN", "timelineItems": {"nodes": [{"createdAt": "2026-10-05T00:00:00Z"}]}},
                         "only the last ClosedEvent is returned")

    def test_graphql_unknown_issue_and_reader_check(self):
        st = self.seeded()
        fake_gh.set_issue(st, "o/n", 1, "OPEN")
        st["repos"]["o/n"]["readers"] = ["sh1ny"]
        self.seed(st)
        r = self.gql(self.GQL_ISSUE, "o", "n", 1, check=False)
        self.assertEqual(r.returncode, 1, "an issue read applies the same reader check")
        st["repos"]["o/n"].pop("readers")
        self.seed(st)
        r = self.gql(self.GQL_ISSUE, "o", "n", 99, check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Could not resolve to an Issue", r.stderr)

    def test_graphql_unknown_query_exits_2(self):
        r = self.gh("api", "graphql", "-f", "query={ viewer { login } }", check=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn("unsupported", r.stderr)

    def test_failure_injection_on_new_endpoints(self):
        st = self.seeded()
        fake_gh.add_review_comment_reaction(st, "o/n", 55, "u", "+1")
        st["fail"] = [{"match": r"reactions$|pulls/comments/55/reactions", "exit": 3, "stderr": "rest boom"},
                      {"match": r"graphql", "exit": 5, "stderr": "gql boom"}]
        self.seed(st)
        r = self.gh("api", "repos/o/n/pulls/comments/55/reactions", check=False)
        self.assertEqual((r.returncode, r.stderr.strip()), (3, "rest boom"))
        for q in (self.GQL_REACTIONS % "THUMBS_UP", self.GQL_PR):
            r = self.gh("api", "graphql", "-f", "query=" + q, "-f", "id=N", check=False)
            self.assertEqual((r.returncode, r.stderr.strip()), (5, "gql boom"))


class PrEvidence(FakeGhCase):
    """The PR snapshot query, the clock, node(id) reads and the writes the PR scripts use."""
    SNAP_Q = ("query($owner:String!, $name:String!, $pr:Int!) { viewer { login } repository(owner:$owner, name:$name) "
              "{ pullRequest(number:$pr) { number reviewThreads(first:100) { nodes { id } } } } }")
    NODE_Q = "query($id:ID!){ node(id:$id) { ... on IssueComment { id } ... on PullRequestReview { id } } }"
    RESOLVE = "mutation($threadId:ID!){ resolveReviewThread(input:{threadId:$threadId}){ thread{ id isResolved } } }"
    REACT = ("mutation($subjectId:ID!,$content:ReactionContent!){ addReaction(input:{subjectId:$subjectId,content:$content})"
             "{ reaction{ content } } }")
    T0 = "2026-10-10T10:00:00Z"

    def setUp(self):
        super().setUp()
        st = self.st()
        st["tokens"]["rev"] = "tok-rev"
        st["clock"] = self.T0
        st["repos"] = {"o/n": {"pulls": [self.pull(7, "b7")]}}
        self.t = fake_gh.add_thread(st, "o/n", 7, path="a.py", line=3)
        self.c1 = fake_gh.add_thread_comment(st, "o/n", 7, self.t["id"], "rev", "root")
        fake_gh.advance_clock(st, 30)
        self.c2 = fake_gh.add_thread_comment(st, "o/n", 7, self.t["id"], "KintsugiBot", "answer")
        fake_gh.advance_clock(st, 30)
        self.ic = fake_gh.add_pr_comment(st, "o/n", 7, "rev", "pr comment")
        self.rv = fake_gh.add_review(st, "o/n", 7, "rev", "review body", state="APPROVED")
        fake_gh.edit_item(st, "o/n", 7, self.c1["id"], "root edited")
        fake_gh.set_checks(st, "o/n", 7, [{"__typename": "CheckRun", "name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}])
        fake_gh.set_head(st, "o/n", 7, "b" * 40, "2026-10-10T09:00:00Z")
        fake_gh.add_node_reaction(st, "o/n", self.c1["id"], "KintsugiBot", "THUMBS_UP", at="2026-10-10T10:02:00Z")
        self.seed(st)

    def gql(self, query, *fields, env=None, check=True):
        args = ["api", "graphql", "-f", "query=" + query]
        for k, v in fields:
            args += ["-F" if k.startswith("+") else "-f", f"{k.lstrip('+')}={v}"]
        return self.gh(*args, env=env, check=check)

    def snap(self, env=None):
        r = self.gql(self.SNAP_Q, ("owner", "o"), ("name", "n"), ("+pr", 7), env=env)
        return json.loads(r.stdout)["data"]

    def node(self, nid, env=None):
        return json.loads(self.gql(self.NODE_Q, ("id", nid), env=env).stdout)["data"]["node"]

    def test_snapshot_shape(self):
        # the query names few fields on purpose: the fake returns every field it has
        d = self.snap()
        self.assertEqual(d["viewer"], {"login": "KintsugiBot"})
        pr = d["repository"]["pullRequest"]
        self.assertEqual((pr["number"], pr["state"], pr["headRefName"], pr["headRefOid"], pr["baseRefName"]), (7, "OPEN", "b7", "b" * 40, "main"))
        self.assertEqual(pr["commits"]["nodes"][0]["commit"]["committedDate"], "2026-10-10T09:00:00Z")
        ctx = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]
        self.assertEqual((ctx["pageInfo"], ctx["nodes"][0]["name"]), ({"hasNextPage": False}, "ci"))
        th = pr["reviewThreads"]["nodes"][0]
        self.assertEqual((th["id"], th["isResolved"], th["path"], th["line"], th["comments"]["totalCount"]), (self.t["id"], False, "a.py", 3, 2))
        c1, c2 = th["comments"]["nodes"]
        self.assertEqual((c1["databaseId"], c1["author"], c1["body"], c1["createdAt"], c1["lastEditedAt"]),
                         (self.c1["databaseId"], {"login": "rev"}, "root edited", self.T0, "2026-10-10T10:01:00Z"))
        self.assertIsNone(c2["lastEditedAt"])
        self.assertEqual(c1["reactionGroups"], [{"content": "THUMBS_UP", "viewerHasReacted": True}])
        self.assertEqual(c2["reactionGroups"], [])
        self.assertEqual(pr["comments"]["nodes"][0]["body"], "pr comment")
        self.assertEqual((pr["reviews"]["nodes"][0]["state"], pr["reviews"]["nodes"][0]["submittedAt"]), ("APPROVED", "2026-10-10T10:01:00Z"))

    @unittest.skipUnless(JQ, "needs gojq or jq on PATH")
    def test_snapshot_viewer_follows_gh_token_and_jq_runs_unchanged(self):
        self.assertEqual(self.snap(env={"GH_TOKEN": "tok-rev"})["viewer"], {"login": "rev"})
        self.assertEqual(self.snap(env={"GH_TOKEN": "tok-s"})["viewer"], {"login": "sh1ny"})
        out = self.gh("api", "graphql", "-f", "query=" + self.SNAP_Q, "-f", "owner=o", "-f", "name=n", "-F", "pr=7", "--jq",
                      '.data.viewer.login as $me | [.data.repository.pullRequest.reviewThreads.nodes[] | .id] | join(",") + "/" + $me',
                      env={"FAKE_GH_JQ": JQ}).stdout.strip()
        self.assertEqual(out, f"{self.t['id']}/KintsugiBot")

    @unittest.skipUnless(shutil.which("jq"), "needs jq")
    def test_jq_evaluator_is_selectable(self):
        args = ("api", "graphql", "-f", "query=" + self.SNAP_Q, "-f", "owner=o", "-f", "name=n", "-F", "pr=7", "--jq", ".data.viewer | .login")
        self.assertEqual(self.gh(*args, env={"FAKE_GH_JQ": shutil.which("jq")}).stdout.strip(), "KintsugiBot")
        r = self.gh(*args, env={"FAKE_GH_JQ": str(self.tmp / "no-such-evaluator")}, check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no-such-evaluator", r.stderr)

    def test_rate_limit_date_header_follows_the_clock(self):
        def date():
            out = self.gh("api", "-i", "rate_limit").stdout.replace("\r", "")
            head, _, body = out.partition("\n\n")
            self.assertIn("resources", json.loads(body))
            return next(l for l in head.splitlines() if l.startswith("Date: "))
        self.assertEqual(date(), "Date: Sat, 10 Oct 2026 10:01:00 GMT")
        st = self.st()
        fake_gh.advance_clock(st, 3661)
        self.seed(st)
        self.assertEqual(date(), "Date: Sat, 10 Oct 2026 11:02:01 GMT")

    def test_node_reads(self):
        th = self.node(self.t["id"])
        self.assertEqual([c["databaseId"] for c in th["comments"]["nodes"]], [self.c1["databaseId"], self.c2["databaseId"]])
        self.assertEqual(th["comments"]["nodes"][0]["lastEditedAt"], "2026-10-10T10:01:00Z")
        ic = self.node(self.ic["node_id"])
        self.assertEqual((ic["body"], ic["createdAt"], ic["lastEditedAt"], ic["author"], ic["url"]),
                         ("pr comment", "2026-10-10T10:01:00Z", None, {"login": "rev"}, self.ic["html_url"]))
        rv = self.node(self.rv["id"])
        self.assertEqual((rv["state"], rv["submittedAt"], rv["lastEditedAt"], rv["databaseId"]),
                         ("APPROVED", "2026-10-10T10:01:00Z", None, self.rv["databaseId"]))
        rc = self.node(self.c1["id"])
        self.assertEqual((rc["databaseId"], rc["body"], rc["createdAt"], rc["lastEditedAt"], rc["url"]),
                         (self.c1["databaseId"], "root edited", self.T0, "2026-10-10T10:01:00Z", self.c1["url"]))

    def test_node_ids_agree_with_the_snapshot_and_reactions(self):
        pr = self.snap()["repository"]["pullRequest"]
        ids = [pr["reviewThreads"]["nodes"][0]["id"], pr["reviewThreads"]["nodes"][0]["comments"]["nodes"][0]["id"],
               pr["comments"]["nodes"][0]["id"], pr["reviews"]["nodes"][0]["id"]]
        for nid in ids:
            self.assertEqual(self.node(nid)["id"], nid)
        r = self.gql(ReactionsAndGraphql.GQL_REACTIONS % "THUMBS_UP", ("id", ids[1]))
        self.assertEqual(json.loads(r.stdout)["data"]["node"]["reactions"]["nodes"], [{"user": {"login": "KintsugiBot"}}])

    def test_unknown_node_is_null(self):
        self.assertIsNone(self.node("PRRT_nope"))
        self.assertEqual(json.loads(self.gql(self.NODE_Q, ("id", "nope")).stdout), {"data": {"node": None}})

    def test_reply_post_appends_to_the_thread(self):
        (self.tmp / "b.md").write_text("reply text\n<!-- m -->", encoding="utf-8", newline="\n")
        st = self.st()
        fake_gh.advance_clock(st, 120)
        self.seed(st)
        url = self.gh("api", "--method", "POST", f"repos/o/n/pulls/7/comments/{self.c1['databaseId']}/replies",
                      "-F", f"body=@{self.tmp / 'b.md'}", "--jq", ".html_url", env={"GH_TOKEN": "tok-rev"}).stdout.strip()
        th = self.st()["repos"]["o/n"]["pulls"][0]["threads"][0]
        added = th["comments"][-1]
        self.assertEqual((len(th["comments"]), added["author"], added["body"], added["createdAt"], added["url"]),
                         (3, "rev", "reply text\n<!-- m -->", "2026-10-10T10:03:00Z", url))
        r = self.gh("api", "--method", "POST", "repos/o/n/pulls/7/comments/99999/replies", "-f", "body=x", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("404", r.stderr)

    def test_pr_comment_body_file_is_listed_with_clock_and_viewer(self):
        (self.tmp / "c.md").write_text("from file", encoding="utf-8", newline="\n")
        self.gh("pr", "comment", "7", "--repo", "o/n", "--body-file", str(self.tmp / "c.md"), env={"GH_TOKEN": "tok-s"})
        last = self.snap()["repository"]["pullRequest"]["comments"]["nodes"][-1]
        self.assertEqual((last["body"], last["author"], last["createdAt"]), ("from file", {"login": "sh1ny"}, "2026-10-10T10:01:00Z"))

    def test_resolve_and_react_mutations(self):
        r = self.gql(self.RESOLVE, ("threadId", self.t["id"]), env={"GH_TOKEN": "tok-rev"})
        self.assertEqual(json.loads(r.stdout)["data"]["resolveReviewThread"]["thread"], {"id": self.t["id"], "isResolved": True})
        th = self.st()["repos"]["o/n"]["pulls"][0]["threads"][0]
        self.assertEqual((th["isResolved"], th["resolvedBy"], th["resolvedAt"]), (True, "rev", "2026-10-10T10:01:00Z"))
        self.assertTrue(self.snap()["repository"]["pullRequest"]["reviewThreads"]["nodes"][0]["isResolved"])
        r = self.gql(self.REACT, ("subjectId", self.ic["node_id"]), ("content", "THUMBS_DOWN"), env={"GH_TOKEN": "tok-rev"})
        self.assertEqual(json.loads(r.stdout)["data"]["addReaction"]["reaction"], {"content": "THUMBS_DOWN"})
        self.assertEqual(self.st()["nodes"][self.ic["node_id"]]["reactions"],
                         [{"login": "rev", "content": "THUMBS_DOWN", "createdAt": "2026-10-10T10:01:00Z"}])
        groups = self.snap(env={"GH_TOKEN": "tok-rev"})["repository"]["pullRequest"]["comments"]["nodes"][0]["reactionGroups"]
        self.assertEqual(groups, [{"content": "THUMBS_DOWN", "viewerHasReacted": True}])
        self.assertEqual(self.gql(self.REACT, ("subjectId", "nope"), ("content", "THUMBS_UP"), check=False).returncode, 1)
        self.assertEqual(self.gql(self.RESOLVE, ("threadId", "nope"), check=False).returncode, 1)

    def test_repeated_reaction_keeps_the_first(self):
        rest = f"repos/o/n/pulls/comments/{self.c2['databaseId']}/reactions"
        self.gh("api", "--method", "POST", rest, "-f", "content=+1")
        self.gql(self.REACT, ("subjectId", self.ic["node_id"]), ("content", "THUMBS_UP"))
        st = self.st()
        fake_gh.advance_clock(st, 60)
        self.seed(st)
        self.gh("api", "--method", "POST", rest, "-f", "content=+1")
        self.gql(self.REACT, ("subjectId", self.ic["node_id"]), ("content", "THUMBS_UP"))
        self.assertEqual(json.loads(self.gh("api", rest).stdout), [{"user": {"login": "KintsugiBot"}, "content": "+1"}])
        for nid in (self.c2["id"], self.ic["node_id"]):
            self.assertEqual(self.st()["nodes"][nid]["reactions"],
                             [{"login": "KintsugiBot", "content": "THUMBS_UP", "createdAt": "2026-10-10T10:01:00Z"}], nid)

    def test_graphql_reaction_on_a_review_comment_is_visible_to_rest(self):
        self.gql(self.REACT, ("subjectId", self.c2["id"]), ("content", "THUMBS_DOWN"))
        rest = f"repos/o/n/pulls/comments/{self.c2['databaseId']}/reactions"
        self.assertEqual(json.loads(self.gh("api", rest).stdout), [{"user": {"login": "KintsugiBot"}, "content": "-1"}])
        self.gh("api", "--method", "POST", rest, "-f", "content=-1")  # the same reaction, through REST
        self.assertEqual(len(json.loads(self.gh("api", rest).stdout)), 1)

    def test_failure_injection_applies_to_the_new_calls(self):
        st = self.st()
        st["fail"] = [{"match": r"rate_limit", "exit": 7, "stderr": "rl"}, {"match": r"graphql", "exit": 8, "stderr": "gql"},
                      {"match": r"/replies", "exit": 9, "stderr": "rp"}]
        self.seed(st)
        for argv, code in ((("api", "-i", "rate_limit"), 7), (("api", "graphql", "-f", "query=" + self.SNAP_Q), 8),
                           (("api", "--method", "POST", "repos/o/n/pulls/7/comments/1/replies", "-f", "body=x"), 9)):
            self.assertEqual(self.gh(*argv, check=False).returncode, code)


@unittest.skipUnless(shutil.which("sh"), "needs sh")
class Shim(FakeGhCase):
    def test_install_fake_gh_shim(self):
        dest = self.tmp / "fx"
        (dest / "bin").mkdir(parents=True)
        fixtures.install_fake_gh(dest)
        env = (dest / "eval.env").read_text(encoding="utf-8")
        self.assertIn(f'export FAKE_GH_STATE="{fixtures.posix(dest / "gh-state.json")}"', env)
        self.assertIn(f'export FAKE_GH_LOG="{fixtures.posix(dest / "gh-log.jsonl")}"', env)
        (dest / "gh-state.json").write_text('{"user": "u"}', encoding="utf-8")
        r = subprocess.run(["sh", str(dest / "bin" / "gh"), "api", "user", "--jq", ".login"], capture_output=True, text=True,
                           env={**os.environ, "FAKE_GH_STATE": str(dest / "gh-state.json"), "FAKE_GH_LOG": str(dest / "gh-log.jsonl")})
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "u"), r.stderr)
        self.assertTrue((dest / "gh-log.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
