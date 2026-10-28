"""A fake `gh` for evals and script tests. Pure stdlib; no network.

State is JSON at $FAKE_GH_STATE:
  {"user": "login",                      # who `api user` reports without GH_TOKEN
   "tokens": {"login": "token"},         # `auth token --user`; GH_TOKEN picks the user
   "repos": {"owner/name": {"pulls": [REST pull objects], "comments": {"<pr>": [...]},
                            "default_branch": "main"}},
   "fail": ["regex" | {"match": "regex", "exit": 1, "stderr": "msg"}]}
Any call whose argv (joined by spaces) matches a `fail` pattern exits non-zero.
Every call appends one JSON line {argv, cwd, gh_repo, env, deadline_at} to $FAKE_GH_LOG; env holds GH_TOKEN, GITHUB_TOKEN,
GH_HOST, GH_ENTERPRISE_TOKEN and GITHUB_ENTERPRISE_TOKEN as the call saw them (null when unset, "" when set empty);
deadline_at is SPECWRIGHT_NET_DEADLINE_AT.
`api user` answers by GH_TOKEN when set, else by the state's active `user`; `auth switch [-u login]` (or switch_user(st, login))
changes that active user, so a test can switch accounts between calls like another process would.
Hostile-network injection (bound-pr-scripts), matched against the joined argv like `fail`, checked after it:
  "hang":  ["regex" | {"match": "regex", "pid_file": "path"}]  write the PID (to pid_file, else $FAKE_GH_PID_FILE) and sleep forever
  "delay": [{"match": "regex", "seconds": 2}]                   sleep, then answer normally
  "flood": [{"match": "regex", "bytes": 1000000}]               print that many bytes of JSON array pages, then exit 0
`api markdown --input <file>` (POST) serves a recorded GitHub rendering: the file holds {"text", "mode", "context"}; the answer is
  the raw HTML stored in the fixture file $FAKE_GH_MARKDOWN (default evals/pr-pair/fixtures/markdown.json), whose entries are
  {sha256-key: {"mode", "context", "html"}}. The key is markdown_key(mode, text) = sha256((mode + NEWLINE + text).encode("utf-8")).hexdigest(), NEWLINE = chr(10);
  `context` is ignored and mode defaults to "markdown". A missing key exits 1 with `no recorded rendering`. The recorder
  (evals/pr-pair/record_markdown.py) imports markdown_key from this module.
Issue lists: per repo "issue_list": [{"number", "state", "body", "pull_request": {...}}] backs `api repos/<o>/<n>/issues?state=all&per_page=100`
  (state filter default open, `all` for both; pages as for pulls; --jq as elsewhere), a pull_request key marking a PR.
A call (other than --help) whose host is not github.com (--hostname, else a non-empty GH_HOST) fails: the fake knows only github.com.

Merge and refs (add-agent-merge). Per repo: "branches": {"feat/x": "<sha>"} (branch heads), "protected_branches": [names]
(DELETE refused, 422), "allowed_methods": ["merge","squash","rebase"] (default all), "merge_queue": true (merge refused, 405).
  PUT repos/<o>/<n>/pulls/<pr>/merge (-f merge_method=, -f sha=): merges an open PR whose pull["head"]["sha"] equals sha:
    200 {sha, merged, message}, sets merged_at, merge_commit_sha, state closed. 409 head mismatch; 405 disallowed method,
    merge queue or an already merged/closed PR. Every call is in $FAKE_GH_LOG (argv has the method and sha).
  GET repos/<o>/<n>/git/ref/heads/<b> -> {ref, object:{sha}} or 404; DELETE repos/<o>/<n>/git/refs/heads/<b> -> 204 (no body)
    or 422 (missing, or protected). Branch names may contain "/".
  REST errors exit 1 with `gh: <message> (HTTP <code>)` on stderr and {"message","status"} on stdout. A "fail" entry with
  no HTTP code in its stderr (e.g. a connection error) models a failure without a status; "once": true fails only the next match.

Optional per-repo "readers": [logins] - only they may call `api repos/<o>/<n>/...` (a private repo); others get 404.
Optional per-repo "activity": [{"ref": "refs/heads/b", "after": "<sha>", "timestamp": "..."}]
backs `api repos/<o>/<n>/activity?ref=...` (the push-time lookup).
Covers: auth token (and its --help, which names --user), api (user, pulls list/get, activity,
issue comments list/create/patch), pr create/view/comment/edit, repo view,
release view <tag> [--json tagName,name,body,url [--jq]] / release create <tag> [--verify-tag] [-t title] [-F notes-file | -n notes]
(add-release-workflow). Anything else exits 2.
Releases: per repo "releases": {"<tag>": {"tag_name", "name", "body", "created_at"}}; "remote_tags": ["v0.5.0", ...] declares
the tags on the remote for --verify-tag; when the key is absent the fake asks `git ls-remote --tags origin refs/tags/<tag>`
in the cwd. view of a missing tag: exit 1, `release not found`. create: missing tag under --verify-tag, or an existing
release, exit 1; success prints https://github.com/<o>/<n>/releases/tag/<tag>. The repo comes from --repo/-R, GH_REPO or origin.
Like real gh, `api --paginate` prints each page's JSON one after another.

Reactions and closing references (state keys; add them with the helpers add_review_comment_reaction,
add_node_reaction, set_closing_refs, set_default_branch, which take and mutate the state dict):
  repos[slug]["review_comment_reactions"] = {"<comment id>": [{"user": {"login": l}, "content": "+1" | "-1"}]}
  st["nodes"] = {"<node id>": {"repo": "owner/name", "reactions": [{"login": l, "content": "THUMBS_UP" | "THUMBS_DOWN"}]}}
  pull["closing_refs"] = [{"number": n, "repo": "owner/name"}]; pull["closing_refs_has_next"] = bool
  repos[slug]["issues"] = {"<n>": {"state": "OPEN" | "CLOSED", "timeline": ["CLOSED", "REOPENED", ...]}}  (set_issue)
  st["graphql_page_size"] = N  (optional; caps the reactions page size below the query's `first`)

Accepted calls (any other query-only document under `api graphql` exits 2; mutations are listed below):
  REST  `api [--paginate] repos/<o>/<n>/pulls/comments/<id>/reactions[?content=%2B1|-1&per_page=N]`
        -> JSON array of {user:{login}, content}; pages of 30 (per_page up to 100), like the other REST lists.
  GQL a `api graphql -f query='...' -f id=<node id> [-f cursor=<endCursor>]` where the query text contains
        `node(id: $id)` and `reactions(` with `content: THUMBS_UP` or `content: THUMBS_DOWN` and `after: $cursor`:
        { node(id: $id) { ... on Reactable { reactions(first: 100, content: THUMBS_UP, after: $cursor)
          { nodes { user { login } } pageInfo { hasNextPage endCursor } } } } }
        -> {"data":{"node":{"reactions":{"nodes":[{"user":{"login":l}}],"pageInfo":{...}}}}}; node null if unknown; checks credentials, and the reader rule of the node's repository.
  GQL b `api graphql -f query='...' -f owner=<o> -f name=<n> -F number=<pr>`; the query text contains
        `repository(` and `pullRequest(number`:
        { repository(owner: $owner, name: $name) { defaultBranchRef { name }
          pullRequest(number: $number) { body baseRefName closingIssuesReferences(first: 100)
            { nodes { number repository { nameWithOwner } } pageInfo { hasNextPage } } } } }
        -> {"data":{"repository":{"defaultBranchRef":{"name":b},"pullRequest":{...}}}}
  GQL c `api graphql -f query='...' -f owner=<o> -f name=<n> -F number=<issue>`; the query text contains
        `repository(` and `issue(number`:
        { repository(owner: $owner, name: $name) { issue(number: $number) { state
          timelineItems(last: 1, itemTypes: [CLOSED_EVENT]) { nodes { ... on ClosedEvent { createdAt } } } } } }
        -> {"data":{"repository":{"issue":{"state":"OPEN"|"CLOSED","timelineItems":{"nodes":[{"createdAt":<last close>}]}}}}}
        (no nodes without a close);
        an unknown issue fails like GitHub ("Could not resolve to an Issue"). The pullRequest read also returns `state`
        (OPEN | CLOSED | MERGED), `url` and `mergedAt`.
Fields not named in the query are still returned; the failure-injection `fail` patterns match the whole argv,
so e.g. "graphql" or "/reactions" apply.

PR evidence (snapshot, reads and writes). State, all per PR (helpers below take and mutate the state dict):
  st["clock"] = "2026-10-10T10:00:00Z"   the fake's time (whole seconds); absent = the real time. Every write below stamps it.
      set_clock(st, iso), advance_clock(st, seconds).
  pull["threads"] = [{"id", "path", "line", "originalLine", "isResolved", "isOutdated",
                      "comments": [{"id", "databaseId", "author": login|None, "body", "createdAt", "lastEditedAt", "url"}]}]
      add_thread, add_thread_comment
  repos[slug]["comments"][pr] = [REST issue comments, plus optional "node_id" and "last_edited_at"]   add_pr_comment
  pull["reviews"] = [{"id", "databaseId", "author", "body", "state", "submittedAt", "lastEditedAt", "url"}]   add_review
  pull["checks"] = [raw statusCheckRollup context nodes]  set_checks;  pull["head_oid"], pull["committed_date"]  set_head
  pull["fields"] = {"mergeable": ..., ...} overrides of the scalar PR fields (isDraft, mergeable, mergeStateStatus, ...)
  edit_item(st, slug, pr, item id, body) changes a thread comment, PR comment or review and sets lastEditedAt to the clock.
  Reactions of every item live in st["nodes"][<item node id>] (add_node_reaction), so the snapshot's reactionGroups,
  `nodes(ids:)` reads and the addReaction mutation agree. A reaction may carry "createdAt".
The jq evaluator for non-trivial --jq filters is $FAKE_GH_JQ (a command name or path; default "jq"), e.g. gojq.

Forms added for PR evidence (the shipped --jq filters run unchanged; raw `data` is what the fake returns):
  GQL snapshot   a query containing `reviewThreads(`, variables owner, name, pr (or number):
        -> {"data":{"viewer":{"login"},"repository":{"pullRequest":{number url state isDraft mergeable mergeStateStatus
           reviewDecision headRefName headRefOid baseRefName author{login}
           commits{nodes:[{commit:{committedDate, statusCheckRollup:{state, contexts:{pageInfo, nodes}}|null}}]}
           reviewThreads{pageInfo{hasNextPage}, nodes:[{id isResolved isOutdated path line originalLine
              comments{totalCount, nodes:[{id databaseId author{login} body createdAt lastEditedAt url reactionGroups}]}}]}
           comments{pageInfo{hasPreviousPage}, nodes} reviews{pageInfo{hasPreviousPage}, nodes}}}}}
        `viewer` is GH_TOKEN's login. Pages: first 100 threads/thread comments/contexts, last 100 comments/reviews.
        reactionGroups lists only the contents that have a reaction; viewerHasReacted says whether the viewer made one.
  GQL head info  a query with `headRefOid` and no `reviewThreads(`: {headRefOid headRefName headRepository{nameWithOwner}
        commits{nodes:[{commit:{committedDate}}]}} (what prepare_cfg reads).
  GQL pending    a query with `reviews(states`: the viewer's PENDING reviews as pullRequest.reviews.nodes[].author, plus viewer.
  GQL rtimes     `nodes(ids:[...])` with `up:`/`down:` reactions(...){nodes{createdAt user{login}}} -> data.viewer, data.nodes.
  GQL node       `node(id: $id)` (no `reactions(`), `-f id=<node id>`: the item with every field, whatever the fragments name:
        thread (PullRequestReviewThread: id isResolved isOutdated path line originalLine comments{totalCount nodes pageInfo}),
        PullRequestReviewComment (id databaseId author body createdAt lastEditedAt url), IssueComment (same fields),
        PullRequestReview (same plus state submittedAt). Unknown id -> {"data":{"node":null}}. Same credential and reader checks.
  REST  `api -i rate_limit`   headers incl. `Date:` (RFC 1123, from the clock), a blank line, then a JSON body.
  REST  POST repos/<o>/<n>/pulls/<pr>/comments/<id>/replies  (-F body=@file | -f body=...): a reply in the thread of review
        comment <id>; returns the REST comment {id node_id html_url body user created_at in_reply_to_id}; 404 for an unknown id.
  REST  POST repos/<o>/<n>/pulls/comments/<id>/reactions (-f content=+1|-1): a reaction on a review comment.
  CLI   pr comment <pr> --body-file F|-   a PR comment stamped with the clock and the viewer (listed by the snapshot).
  GQL mutations  `resolveReviewThread(input:{threadId:$threadId})` -> {"data":{"resolveReviewThread":{"thread":{id,isResolved}}}};
        `addReaction(input:{subjectId:$subjectId,content:$content})` -> {"data":{"addReaction":{"reaction":{"content"}}}}.
        Applied only when a mutation operation selects the field at its top level (gqlops.operations, as the grader reads it);
        a comment or string that names one writes nothing. Only the operation GitHub executes counts: the one `-f operationName=`
        names, else the document's only one. An unparseable document, several operations without a name, an unknown operation
        name, a subscription or an unknown mutation field exits 1 with a GraphQL error and leaves the state unsaved.
  Each write records the clock's time and the viewer (reactions as "createdAt"/"login").
  A reaction is kept once per login and content: a repeat returns the existing one and keeps its time, as GitHub does.
  A review comment's reaction is one state: addReaction shows in the REST list, and the REST POST in the node's reactions.
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # the sibling modules, however gh.py is loaded
import gqlops  # noqa: E402  reads the operations of a GraphQL document

HOST = "https://github.com"
ENV_LOGGED = ("GH_TOKEN", "GITHUB_TOKEN", "GH_HOST", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")


class Fail(Exception):
    def __init__(self, msg, code=1, body=None):
        super().__init__(msg)
        self.code = code
        self.body = body


def http_fail(status, message):
    """A REST error as real gh reports it: exit 1, `gh: <message> (HTTP <status>)` on stderr, GitHub's JSON body on stdout."""
    return Fail(f"gh: {message} (HTTP {status})", 1, {"message": message, "status": str(status)})


def load():
    p = os.environ.get("FAKE_GH_STATE")
    if p and os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save(st):
    p = os.environ.get("FAKE_GH_STATE")
    if p:
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(st, f, indent=2)


def log(argv):
    p = os.environ.get("FAKE_GH_LOG")
    if p:
        with open(p, "a", encoding="utf-8", newline="\n") as f:
            env = {k: os.environ.get(k) for k in ENV_LOGGED}
            f.write(json.dumps({"argv": argv, "cwd": os.getcwd(), "gh_repo": os.environ.get("GH_REPO"), "env": env,
                                "deadline_at": os.environ.get("SPECWRIGHT_NET_DEADLINE_AT")}) + "\n")


def inject_failure(st, argv):
    line = " ".join(argv)
    for f in list(st.get("fail", [])):
        f = {"match": f} if isinstance(f, str) else f
        if re.search(f["match"], line):
            if f.get("once"):  # fail only the next matching call
                st["fail"] = [x for x in st["fail"] if x != f]
                save(st)
            raise Fail(f.get("stderr", "fake gh: injected failure"), f.get("exit", 1))


def markdown_key(mode, text):
    """The fixture key of a rendering: SHA-256 of mode + "\n" + text (UTF-8). The context is not part of it."""
    return hashlib.sha256((mode + chr(10) + text).encode("utf-8")).hexdigest()


MARKDOWN_FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pr-pair", "fixtures", "markdown.json")


def hostile(st, argv):
    """The hang, delay and flood injections: what a stuck or hostile network does to a call."""
    line = " ".join(argv)
    for h in st.get("hang", []):
        h = {"match": h} if isinstance(h, str) else h
        if re.search(h["match"], line):
            pid_file = h.get("pid_file") or os.environ.get("FAKE_GH_PID_FILE")
            if pid_file:
                with open(pid_file, "w", encoding="utf-8") as f:
                    f.write(str(os.getpid()))
            while True:
                time.sleep(3600)
    for d in st.get("delay", []):
        if re.search(d["match"], line):
            time.sleep(float(d["seconds"]))
    for fl in st.get("flood", []):
        if re.search(fl["match"], line):
            page = "[" + ",".join(['{"id":1,"body":"' + "x" * 80 + '"}'] * 10) + "]" + chr(10)
            left = int(fl["bytes"])
            try:
                while left > 0:
                    chunk = page if left >= len(page) else "x" * left
                    sys.stdout.write(chunk)
                    left -= len(chunk)
                sys.stdout.flush()
            except OSError:  # the reader stopped listening
                pass
            raise SystemExit(0)


def parse(args, valued, flags=()):
    """Split args into ({flag: [values]}, positionals). Short and long names share one key."""
    opts, pos, i = {}, [], 0
    while i < len(args):
        a = args[i]
        if a.startswith("-") and a != "-":
            k, eq, v = a.partition("=")
            if k in valued:
                if not eq:
                    i += 1
                    if i >= len(args):
                        raise Fail(f"flag needs an argument: {k}", 2)
                    v = args[i]
                opts.setdefault(valued[k], []).append(v)
            elif k in flags:
                opts[k.lstrip("-")] = [True]
            else:
                raise Fail(f"unknown flag: {k}", 2)
        else:
            pos.append(a)
        i += 1
    return opts, pos


def one(opts, key, default=None):
    return opts[key][-1] if key in opts else default


def read_file(f):
    """A path as the script passed it; an MSYS path (/tmp/x) is translated when Python is not an MSYS program."""
    if f == "-":
        return sys.stdin.read()
    if not os.path.exists(f) and f.startswith("/") and shutil.which("cygpath"):
        f = subprocess.run(["cygpath", "-w", f], capture_output=True, text=True).stdout.strip() or f
    with open(f, encoding="utf-8", newline="") as fh:
        return fh.read()


def body_of(opts):
    if "body-file" in opts:
        return read_file(one(opts, "body-file"))
    return one(opts, "body")


def jq(data, expr):
    """Simple paths (`.a.b`, `.[]`, `.[].a`, `.a[]`) here; anything else (select, pipes, functions) goes to the real
    `jq -r -c` ($FAKE_GH_JQ names another evaluator, e.g. gojq), as gh's own --jq would evaluate it. Strings print raw."""
    if not re.fullmatch(r"(\.(\[\]|[A-Za-z_][\w-]*))+|\.", expr.strip()):
        evaluator = os.environ.get("FAKE_GH_JQ") or "jq"
        try:
            r = subprocess.run([evaluator, "-r", "-c", expr], input=json.dumps(data), capture_output=True, text=True, encoding="utf-8")
        except OSError as e:
            raise Fail(f"fake gh: cannot run the jq evaluator {evaluator!r}: {e}", 1)
        if r.returncode:
            raise Fail(f"fake gh: jq failed: {r.stderr.strip()}", 1)
        return r.stdout.rstrip("\n")
    cur = [data]
    for part in re.findall(r"\.?([^.\[\]]+|\[\])", expr.strip()):
        nxt = []
        for c in cur:
            if part == "[]":
                nxt.extend(c if isinstance(c, list) else [])
            elif isinstance(c, dict):
                nxt.append(c.get(part))
        cur = nxt
    return "\n".join(c if isinstance(c, str) else json.dumps(c) for c in cur)


def emit(data, expr=None):
    print(jq(data, expr) if expr else json.dumps(data))


def repo_of(opts, st):
    r = one(opts, "repo") or os.environ.get("GH_REPO")
    if not r:
        out = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
        m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", out.stdout.strip())
        r = m.group(1) if m else None
    if not r:
        raise Fail("no repository: pass --repo or set GH_REPO")
    r = r.split("github.com/")[-1].strip("/")
    return r, st.setdefault("repos", {}).setdefault(r, {})


def pull_url(slug, n):
    return f"{HOST}/{slug}/pull/{n}"


def find_pull(slug, repo, ref):
    ref = str(ref)
    m = re.search(r"/pull/(\d+)", ref)
    n = int(m.group(1)) if m else int(ref) if ref.isdigit() else None
    for p in repo.get("pulls", []):
        if (n is not None and p["number"] == n) or (n is None and p["head"]["ref"] == ref):
            return p
    raise Fail(f"GraphQL: Could not resolve to a PullRequest with the number of {ref}. (repository.pullRequest)")


ISO = "%Y-%m-%dT%H:%M:%SZ"
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def now(st=None):
    """The fake clock when the state has one, else the real time."""
    if st and st.get("clock"):
        return st["clock"]
    return datetime.now(timezone.utc).strftime(ISO)


def set_clock(st, iso):
    st["clock"] = iso


def advance_clock(st, seconds):
    st["clock"] = (datetime.strptime(now(st), ISO) + timedelta(seconds=seconds)).strftime(ISO)
    return st["clock"]


def http_date(iso):
    """RFC 1123, as GitHub's Date header."""
    d = datetime.strptime(iso, ISO)
    return f"{DAYS[d.weekday()]}, {d.day:02d} {MONTHS[d.month - 1]} {d.year} {d:%H:%M:%S} GMT"


def new_comment(st, slug, num, text, user):
    st["next_id"] = st.get("next_id", 1000) + 1
    c = {"id": st["next_id"], "node_id": f"IC_{st['next_id']}", "body": text, "user": {"login": user}, "created_at": now(st),
         "html_url": f"{pull_url(slug, num)}#issuecomment-{st['next_id']}"}
    st["repos"][slug].setdefault("comments", {}).setdefault(str(num), []).append(c)
    return c


def whoami(st):
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok:
        for login, t in st.get("tokens", {}).items():
            if t == tok:
                return login
        raise Fail("gh: Bad credentials (HTTP 401)")
    if not st.get("user"):
        raise Fail("gh: To get started with GitHub CLI, please run:  gh auth login")
    return st["user"]


def graphql_view(p, slug):
    state = "MERGED" if p.get("merged_at") else p["state"].upper()
    return {"number": p["number"], "url": p["html_url"], "state": state, "title": p.get("title", ""),
            "body": p.get("body") or "", "headRefName": p["head"]["ref"], "baseRefName": p["base"]["ref"],
            "headRepositoryOwner": {"login": p["head"]["repo"]["full_name"].split("/")[0]},
            "isCrossRepository": p["head"]["repo"]["full_name"] != slug}


def switch_user(st, login):
    """What `gh auth switch` does to the shared state: another login becomes the active one."""
    st["user"] = login


def cmd_auth(st, args):
    if args[:1] == ["switch"]:
        o, _ = parse(args[1:], {"--hostname": "hostname", "-h": "hostname", "--user": "user", "-u": "user"})
        login = one(o, "user")
        if login not in st.get("tokens", {}):
            raise Fail(f"no logged-in account {login}")
        return switch_user(st, login)
    if args[:1] != ["token"]:
        raise Fail(f"fake gh: unsupported auth command {args[:1]}", 2)
    if "--help" in args or "-h" in args[1:]:
        print("Print the authentication token gh uses for a hostname and account.\n\nFLAGS\n"
              "  -h, --hostname string   The hostname of the GitHub instance\n"
              "  -u, --user string       The account to log out of")
        return
    o, _ = parse(args[1:], {"--hostname": "hostname", "-h": "hostname", "--user": "user", "-u": "user"})
    login = one(o, "user") or st.get("user")
    tok = st.get("tokens", {}).get(login)
    if not tok:
        raise Fail(f"no oauth token found for {login}")
    print(tok)


def paged(items, query):
    n = max(1, min(int(query.get("per_page", 30)), 100))
    page = int(query.get("page", 1))
    return items[(page - 1) * n: page * n], len(items) > page * n


def emit_pages(items, query, o, expr):
    """First page only, or every page with --paginate."""
    query["page"] = int(query.get("page", 1))
    while True:
        page, more = paged(items, query)
        emit(page, expr)
        if not more or "paginate" not in o:
            return
        query["page"] += 1


def add_review_comment_reaction(st, slug, comment_id, login, content):
    """content is the REST form: "+1" or "-1"."""
    rx = st.setdefault("repos", {}).setdefault(slug, {}).setdefault("review_comment_reactions", {})
    rx.setdefault(str(comment_id), []).append({"user": {"login": login}, "content": content})


def add_node_reaction(st, slug, node_id, login, content, at=None):
    """content is the GraphQL form: "THUMBS_UP" or "THUMBS_DOWN". `slug` is the repository the node lives in: reading the
    node needs a login that can read that repository."""
    node = st.setdefault("nodes", {}).setdefault(str(node_id), {"repo": slug})
    node["repo"] = slug
    node.setdefault("reactions", []).append({"login": login, "content": content, **({"createdAt": at} if at else {})})


def react_once(st, slug, node_id, login, content):
    """A viewer's reaction as GitHub records it: one per login and content. A repeat returns the existing reaction and
    keeps its time, so a retried --react never looks like fresh evidence."""
    if not any(r["login"] == login and r["content"] == content
               for r in st.get("nodes", {}).get(node_id, {}).get("reactions", [])):
        add_node_reaction(st, slug, node_id, login, content, at=now(st))


REST_CONTENT = {"THUMBS_UP": "+1", "THUMBS_DOWN": "-1", "LAUGH": "laugh", "HOORAY": "hooray", "CONFUSED": "confused",
                "HEART": "heart", "ROCKET": "rocket", "EYES": "eyes"}


def rest_react_once(st, slug, comment_id, login, content):
    """react_once for the REST list of a review comment (content in the REST form)."""
    if not any(r["user"]["login"] == login and r["content"] == content
               for r in st.get("repos", {}).get(slug, {}).get("review_comment_reactions", {}).get(str(comment_id), [])):
        add_review_comment_reaction(st, slug, comment_id, login, content)


def set_closing_refs(st, slug, number, refs, has_next=False):
    """refs: [(number, "owner/name"), ...] for PR `number` of `slug`."""
    for p in st["repos"][slug]["pulls"]:
        if p["number"] == number:
            p["closing_refs"] = [{"number": n, "repo": r} for n, r in refs]
            p["closing_refs_has_next"] = has_next
            return
    raise KeyError(number)


def set_default_branch(st, slug, name):
    st.setdefault("repos", {}).setdefault(slug, {})["default_branch"] = name


def set_issue(st, slug, number, state="OPEN", timeline=()):
    """state: "OPEN" or "CLOSED"; timeline: the close/reopen events in order, e.g. ["CLOSED", "REOPENED"]. An event is a name, or
    (name, createdAt); a bare "CLOSED" happened at CLOSE_AT."""
    st.setdefault("repos", {}).setdefault(slug, {}).setdefault("issues", {})[str(number)] = {
        "state": state, "timeline": list(timeline)}


CLOSE_AT = "2026-10-09T00:00:00Z"  # a bare "CLOSED" event's time: after the test PRs merge


# ---- PR evidence state (see the module docstring) ---------------------------------------------------------------
def _pull(st, slug, number):
    for p in st.setdefault("repos", {}).setdefault(slug, {}).setdefault("pulls", []):
        if p["number"] == int(number):
            return p
    raise KeyError(number)


def _new_id(st):
    st["next_id"] = st.get("next_id", 1000) + 1
    return st["next_id"]


def add_thread(st, slug, number, path="a.py", line=1, thread_id=None, resolved=False, outdated=False):
    """An empty review thread on PR `number`; fill it with add_thread_comment."""
    t = {"id": thread_id or f"PRRT_{_new_id(st)}", "path": path, "line": line, "originalLine": line,
         "isResolved": resolved, "isOutdated": outdated, "comments": []}
    _pull(st, slug, number).setdefault("threads", []).append(t)
    return t


def add_thread_comment(st, slug, number, thread_id, author, body, at=None):
    """A comment in a thread, created at `at` (default the clock). author None = a deleted user (GraphQL null)."""
    t = next(t for t in _pull(st, slug, number)["threads"] if t["id"] == thread_id)
    dbid = _new_id(st)
    c = {"id": f"PRRC_{dbid}", "databaseId": dbid, "author": author, "body": body, "createdAt": at or now(st),
         "lastEditedAt": None, "url": f"{pull_url(slug, number)}#discussion_r{dbid}"}
    t["comments"].append(c)
    return c


def add_pr_comment(st, slug, number, author, body, at=None):
    """A PR (issue) comment; the REST list `issues/<pr>/comments` shows it too."""
    c = new_comment(st, slug, number, body, author)
    if at:
        c["created_at"] = at
    return c


def add_review(st, slug, number, author, body, state="COMMENTED", at=None):
    dbid = _new_id(st)
    r = {"id": f"PRR_{dbid}", "databaseId": dbid, "author": author, "body": body, "state": state,
         "submittedAt": at or now(st), "lastEditedAt": None, "url": f"{pull_url(slug, number)}#pullrequestreview-{dbid}"}
    _pull(st, slug, number).setdefault("reviews", []).append(r)
    return r


def edit_item(st, slug, number, item_id, body, at=None):
    """Edit a thread comment, PR comment or review: new body, lastEditedAt = `at` (default the clock)."""
    found = find_item(st, item_id)
    if not found or found[0] != slug:
        raise KeyError(item_id)
    item = found[3]
    item["body"] = body
    item["last_edited_at" if "created_at" in item else "lastEditedAt"] = at or now(st)
    return item


def set_checks(st, slug, number, contexts):
    """contexts: raw statusCheckRollup nodes, e.g. {"__typename": "CheckRun", "name": ..., "status": "COMPLETED", "conclusion": "SUCCESS"}."""
    _pull(st, slug, number)["checks"] = list(contexts)


def set_head(st, slug, number, oid, committed_date=None):
    p = _pull(st, slug, number)
    p["head_oid"] = oid
    p["head"]["sha"] = oid
    p["committed_date"] = committed_date


def head_oid(p):
    return p.get("head_oid") or p["head"].get("sha") or f"{p['number']:040x}"


def find_item(st, nid):
    """(slug, pull|None, kind, item, thread|None) for a snapshot node id: a thread, thread comment, PR comment or review."""
    for slug, repo in st.get("repos", {}).items():
        for p in repo.get("pulls", []):
            for t in p.get("threads", []):
                if t["id"] == nid:
                    return slug, p, "thread", t, t
                for c in t["comments"]:
                    if c["id"] == nid:
                        return slug, p, "review_comment", c, t
            for r in p.get("reviews", []):
                if r["id"] == nid:
                    return slug, p, "review", r, None
        for num, lst in repo.get("comments", {}).items():
            for c in lst:
                if c.get("node_id", f"IC_{c['id']}") == nid:
                    return slug, next((p for p in repo.get("pulls", []) if str(p["number"]) == str(num)), None), "issue_comment", c, None
    return None


def _groups(st, nid, viewer):
    rx = st.get("nodes", {}).get(nid, {}).get("reactions", [])
    return [{"content": c, "viewerHasReacted": any(r["login"] == viewer and r["content"] == c for r in rx)}
            for c in dict.fromkeys(r["content"] for r in rx)]


def _author(login):
    return {"login": login} if login else None


def _render_tc(st, c, viewer):
    return {"__typename": "PullRequestReviewComment", "id": c["id"], "databaseId": c["databaseId"], "author": _author(c["author"]),
            "body": c["body"], "createdAt": c["createdAt"], "lastEditedAt": c.get("lastEditedAt"), "url": c["url"],
            "reactionGroups": _groups(st, c["id"], viewer)}


def _render_ic(st, c, viewer):
    nid = c.get("node_id", f"IC_{c['id']}")
    return {"__typename": "IssueComment", "id": nid, "databaseId": c["id"], "author": _author(c["user"]["login"]), "body": c["body"],
            "createdAt": c["created_at"], "lastEditedAt": c.get("last_edited_at"), "url": c["html_url"],
            "reactionGroups": _groups(st, nid, viewer)}


def _render_review(st, r, viewer):
    return {"__typename": "PullRequestReview", "id": r["id"], "databaseId": r["databaseId"], "author": _author(r["author"]),
            "body": r["body"], "state": r["state"], "submittedAt": r["submittedAt"], "lastEditedAt": r.get("lastEditedAt"),
            "url": r["url"], "reactionGroups": _groups(st, r["id"], viewer)}


def _render_thread(st, t, viewer):
    cs = t["comments"]
    return {"__typename": "PullRequestReviewThread", "id": t["id"], "isResolved": t["isResolved"], "isOutdated": t["isOutdated"],
            "path": t["path"], "line": t["line"], "originalLine": t["originalLine"],
            "comments": {"totalCount": len(cs), "nodes": [_render_tc(st, c, viewer) for c in cs[:100]],
                         "pageInfo": {"hasNextPage": len(cs) > 100}}}


def _render_item(st, kind, item, viewer):
    return {"thread": _render_thread, "review_comment": _render_tc, "review": _render_review,
            "issue_comment": _render_ic}[kind](st, item, viewer)


def _readable(st, slug, viewer):
    repo = st.get("repos", {}).get(slug, {})
    return not repo.get("readers") or viewer in repo["readers"]


def read_pull(st, fields):
    """(slug, repo, pull, viewer) for owner/name/pr(or number) variables, with the credential and reader checks."""
    slug = f"{fields.get('owner')}/{fields.get('name')}"
    repo = st.get("repos", {}).get(slug)
    viewer = whoami(st)
    if repo is None or not _readable(st, slug, viewer):
        raise Fail(f"GraphQL: Could not resolve to a Repository with the name '{slug}'. (repository)")
    return slug, repo, find_pull(slug, repo, fields.get("pr") or fields.get("number", "")), viewer


def _commits(p):
    checks = p.get("checks", [])
    rollup = None
    if checks:
        busy = any(c.get("status", "COMPLETED") != "COMPLETED" or c.get("state") in ("PENDING", "EXPECTED") for c in checks)
        bad = any(c.get("conclusion") in ("FAILURE", "CANCELLED", "TIMED_OUT") or c.get("state") in ("FAILURE", "ERROR") for c in checks)
        rollup = {"state": "PENDING" if busy else "FAILURE" if bad else "SUCCESS",
                  "contexts": {"pageInfo": {"hasNextPage": len(checks) > 100}, "nodes": checks[:100]}}
    return {"nodes": [{"commit": {"committedDate": p.get("committed_date"), "statusCheckRollup": rollup}}]}


def snapshot_data(st, slug, repo, p, viewer):
    threads = p.get("threads", [])
    ics = repo.get("comments", {}).get(str(p["number"]), [])
    revs = p.get("reviews", [])
    pr = {"number": p["number"], "url": p["html_url"], "state": graphql_view(p, slug)["state"], "isDraft": False,
          "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "reviewDecision": None,
          "headRefName": p["head"]["ref"], "headRefOid": head_oid(p), "baseRefName": p["base"]["ref"],
          "author": {"login": p.get("author", "author")}, "commits": _commits(p),
          "reviewThreads": {"pageInfo": {"hasNextPage": len(threads) > 100},
                            "nodes": [_render_thread(st, t, viewer) for t in threads[:100]]},
          "comments": {"pageInfo": {"hasPreviousPage": len(ics) > 100}, "nodes": [_render_ic(st, c, viewer) for c in ics[-100:]]},
          "reviews": {"pageInfo": {"hasPreviousPage": len(revs) > 100}, "nodes": [_render_review(st, r, viewer) for r in revs[-100:]]}}
    pr.update(p.get("fields", {}))
    return {"data": {"viewer": {"login": viewer}, "repository": {"pullRequest": pr}}}


def _resolve_thread(st, fields):
    viewer = whoami(st)
    found = find_item(st, fields.get("threadId", ""))
    if not found or found[2] != "thread" or not _readable(st, found[0], viewer):
        raise Fail(f"GraphQL: Could not resolve to a node with the global id of '{fields.get('threadId', '')}'. (resolveReviewThread)")
    found[3]["isResolved"] = True
    found[3]["resolvedBy"], found[3]["resolvedAt"] = viewer, now(st)
    return {"resolveReviewThread": {"thread": {"id": found[3]["id"], "isResolved": True}}}


def _add_reaction(st, fields):
    viewer = whoami(st)
    sid, content = fields.get("subjectId", ""), fields.get("content", "")
    found = find_item(st, sid)
    if not found or not _readable(st, found[0], viewer):
        raise Fail(f"GraphQL: Could not resolve to a node with the global id of '{sid}'. (addReaction)")
    if content not in ("THUMBS_UP", "THUMBS_DOWN", "LAUGH", "HOORAY", "CONFUSED", "HEART", "ROCKET", "EYES"):
        raise Fail(f"GraphQL: Variable $content of type ReactionContent! was provided invalid value ({content})")
    react_once(st, found[0], sid, viewer, content)
    if found[2] == "review_comment":  # REST reads the same reaction
        rest_react_once(st, found[0], found[3]["databaseId"], viewer, REST_CONTENT[content])
    return {"addReaction": {"reaction": {"content": content}}}


MUTATIONS = {"resolveReviewThread": _resolve_thread, "addReaction": _add_reaction}


def cmd_graphql_evidence(st, q, fields):
    """The PR-evidence queries and mutations; None when `q` is not one of them. Only the operation GitHub would execute is
    dispatched: the one `operationName` names, or the document's only operation (several without a name, or an unknown name, fail).
    A write is a mutation operation's top-level field, dispatched by exact name, as the grader classifies it; text in a comment
    or string never writes. A failing field leaves the state unsaved (main saves only when no Fail is raised)."""
    ops = gqlops.named_operations(q)
    if ops is None:
        raise Fail("GraphQL: Parse error: the query document cannot be read")
    # only the operation to execute counts, as on GitHub: the one operationName names, else the document's only operation
    name = fields.get("operationName")
    if name is not None:
        ops = [op for op in ops if op[1] == name]
        if not ops:
            raise Fail(f"GraphQL: Unknown operation named '{name}'.")
        if len(ops) > 1:  # GitHub rejects the document before executing any of them
            raise Fail(f"GraphQL: There are multiple operations named '{name}'.")
    elif len(ops) > 1:
        raise Fail("GraphQL: Must provide operation name if query contains multiple operations.")
    ops = [(kind, top) for kind, _, top in ops]
    if any(kind != "query" for kind, _ in ops):
        data = {}
        for kind, top in ops:
            if kind != "mutation":
                raise Fail(f"GraphQL: {kind} operations are not supported")
            if not top:  # fields only through a fragment spread, which the fake does not expand: an error, not an empty success
                raise Fail("GraphQL: the mutation selects no field the fake supports (fragment spreads on Mutation are not expanded)")
            for name in top:
                if name not in MUTATIONS:
                    raise Fail(f"GraphQL: Field '{name}' doesn't exist on type 'Mutation'")
                data.update(MUTATIONS[name](st, fields))
        return {"data": data}
    if "reviewThreads(" in q:
        slug, repo, p, viewer = read_pull(st, fields)
        return snapshot_data(st, slug, repo, p, viewer)
    if "reviews(states" in q:
        slug, repo, p, viewer = read_pull(st, fields)
        pending = [{"author": _author(r["author"])} for r in p.get("reviews", []) if r["state"] == "PENDING" and r["author"] == viewer]
        return {"data": {"viewer": {"login": viewer}, "repository": {"pullRequest": {"reviews": {"nodes": pending}}}}}
    if "headRefOid" in q:
        slug, repo, p, viewer = read_pull(st, fields)
        return {"data": {"repository": {"pullRequest": {
            "headRefOid": head_oid(p), "headRefName": p["head"]["ref"],
            "headRepository": {"nameWithOwner": p["head"]["repo"]["full_name"]}, "commits": _commits(p)}}}}
    m = re.search(r"nodes\(ids:\s*\[([^\]]*)\]", q)
    if m:
        viewer = whoami(st)
        out = []
        for nid in re.findall(r"[A-Za-z0-9_=-]+", m.group(1)):
            found = find_item(st, nid)
            if not found or not _readable(st, found[0], viewer):
                out.append(None)
                continue
            rx = st.get("nodes", {}).get(nid, {}).get("reactions", [])
            pick = lambda c: {"nodes": [{"createdAt": r.get("createdAt"), "user": {"login": r["login"]}} for r in rx if r["content"] == c]}
            out.append({"id": nid, "up": pick("THUMBS_UP"), "down": pick("THUMBS_DOWN")})
        return {"data": {"viewer": {"login": viewer}, "nodes": out}}
    if "node(id" in q and "reactions(" not in q:
        viewer = whoami(st)
        found = find_item(st, fields.get("id", ""))
        if not found or not _readable(st, found[0], viewer):
            return {"data": {"node": None}}
        return {"data": {"node": _render_item(st, found[2], found[3], viewer)}}
    return None


def cmd_graphql(st, fields):
    q = fields.get("query", "")
    evidence = cmd_graphql_evidence(st, q, fields)
    if evidence is not None:
        return evidence
    if "node(id" in q and "reactions(" in q:
        m = re.search(r"content:\s*(THUMBS_UP|THUMBS_DOWN)", q)
        content = m.group(1) if m else fields.get("content")
        first = re.search(r"first:\s*(\d+)", q)
        size = max(1, min(int(first.group(1)) if first else 30, 100, int(st.get("graphql_page_size", 100))))
        reader = whoami(st)  # a bad token or no login fails like every credentialed read
        node = st.get("nodes", {}).get(fields.get("id", ""))
        if node is None:
            return {"data": {"node": None}}
        repo = st.get("repos", {}).get(node.get("repo", ""), {})
        if repo.get("readers") and reader not in repo["readers"]:  # the node's repository is private to others
            raise Fail(f"GraphQL: Could not resolve to a node with the global id of '{fields.get('id', '')}'. (node)")
        items = [r for r in node.get("reactions", []) if not content or r["content"] == content]
        start = int(fields.get("cursor") or 0)
        end = start + size
        return {"data": {"node": {"reactions": {
            "nodes": [{"user": {"login": r["login"]}} for r in items[start:end]],
            "pageInfo": {"hasNextPage": end < len(items), "endCursor": str(end) if end < len(items) else None}}}}}
    if "repository(" in q and "issue(number" in q:
        slug = f"{fields.get('owner')}/{fields.get('name')}"
        repo = st.get("repos", {}).get(slug)
        if repo is None or (repo.get("readers") and whoami(st) not in repo["readers"]):
            raise Fail(f"GraphQL: Could not resolve to a Repository with the name '{slug}'. (repository)")
        issue = repo.get("issues", {}).get(str(fields.get("number", "")))
        if issue is None:
            raise Fail(f"GraphQL: Could not resolve to an Issue with the number of {fields.get('number')}. (repository.issue)")
        events = [(e, CLOSE_AT) if isinstance(e, str) else tuple(e) for e in issue.get("timeline", [])]
        closes = [{"createdAt": at} for name, at in events if name == "CLOSED"]
        return {"data": {"repository": {"issue": {"state": issue["state"], "timelineItems": {"nodes": closes[-1:]}}}}}
    if "repository(" in q and "pullRequest(number" in q:
        slug = f"{fields.get('owner')}/{fields.get('name')}"
        repo = st.get("repos", {}).get(slug)
        if repo is None:
            raise Fail(f"GraphQL: Could not resolve to a Repository with the name '{slug}'. (repository)")
        if repo.get("readers") and whoami(st) not in repo["readers"]:  # the same access check as the REST path
            raise Fail(f"GraphQL: Could not resolve to a Repository with the name '{slug}'. (repository)")
        p = find_pull(slug, repo, fields.get("number", ""))
        refs = p.get("closing_refs", [])
        return {"data": {"repository": {"defaultBranchRef": {"name": repo.get("default_branch", "main")},
                "pullRequest": {"body": p.get("body") or "", "baseRefName": p["base"]["ref"],
                                "state": graphql_view(p, slug)["state"], "url": p["html_url"], "mergedAt": p.get("merged_at"),
                                "closingIssuesReferences": {
                                    "nodes": [{"number": r["number"], "repository": {"nameWithOwner": r.get("repo", slug)}}
                                              for r in refs[:100]],
                                    "pageInfo": {"hasNextPage": bool(p.get("closing_refs_has_next")) or len(refs) > 100}}}}}}
    raise Fail("fake gh: unsupported graphql query", 2)


def cmd_api(st, args):
    o, pos = parse(args, {"-X": "method", "--method": "method", "-f": "field", "--raw-field": "field",
                          "-F": "typed", "--field": "typed", "--input": "input", "--jq": "jq", "-q": "jq",
                          "--hostname": "hostname", "-H": "header", "--header": "header", "-t": "tmpl",
                          "--template": "tmpl", "--cache": "cache"}, ("--paginate", "--silent", "--include", "-i", "--slurp"))
    if len(pos) != 1:
        raise Fail("fake gh: api needs exactly one endpoint", 2)
    u = urlsplit(pos[0].lstrip("/"))
    query = dict(parse_qsl(u.query))
    path, method = u.path, (one(o, "method") or "GET").upper()
    fields = dict(f.partition("=")[::2] for f in o.get("field", []))
    for f in o.get("typed", []):  # -F: a value starting with @ is read from that file (- = stdin)
        k, _, v = f.partition("=")
        fields[k] = read_file(v[1:]) if v.startswith("@") else v
    if "input" in o:
        i = one(o, "input")
        fields.update(json.loads(sys.stdin.read() if i == "-" else open(i, encoding="utf-8").read()))
    if method == "GET":
        query.update(fields)
    expr = one(o, "jq")
    if path == "user":
        return emit({"login": whoami(st)}, expr)
    if path == "graphql":
        return emit(cmd_graphql(st, fields), expr)
    if path == "markdown" and method == "POST":
        text, mode = fields.get("text", ""), fields.get("mode") or "markdown"
        fx = os.environ.get("FAKE_GH_MARKDOWN") or MARKDOWN_FIXTURE
        try:
            with open(fx, encoding="utf-8") as f:
                rec = json.load(f).get(markdown_key(mode, text))
        except (OSError, ValueError):
            rec = None
        if rec is None:
            raise Fail("no recorded rendering", 1)
        sys.stdout.write(rec if isinstance(rec, str) else rec["html"])
        return
    if path == "rate_limit":
        body = {"resources": {"core": {"limit": 5000, "remaining": 4999}, "graphql": {"limit": 5000, "remaining": 4999}}}
        if "include" in o or "i" in o:
            sys.stdout.write(f"HTTP/2.0 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nDate: {http_date(now(st))}\r\n\r\n")
        return emit(body, expr)
    m = re.fullmatch(r"repos/([^/]+/[^/]+)/(.*)", path)
    if not m:
        raise Fail(f"fake gh: unsupported api endpoint {path}", 2)
    slug, rest = m.groups()
    repo = st.setdefault("repos", {}).setdefault(slug, {})
    if repo.get("readers") and whoami(st) not in repo["readers"]:
        raise Fail("gh: Not Found (HTTP 404)")
    if rest == "pulls" and method == "GET":
        state = query.get("state", "open")
        head = query.get("head")
        items = [p for p in sorted(repo.get("pulls", []), key=lambda p: -p["number"])
                 if (state == "all" or p["state"] == state)
                 and (not head or p["head"]["label"] == head)
                 and (not query.get("base") or p["base"]["ref"] == query["base"])]
        return emit_pages(items, query, o, expr)
    if rest == "issues" and method == "GET":
        state = query.get("state", "open")
        items = [i for i in repo.get("issue_list", []) if state == "all" or i.get("state", "open") == state]
        return emit_pages(items, query, o, expr)
    if rest == "activity" and method == "GET":
        items = [a for a in repo.get("activity", []) if not query.get("ref") or a.get("ref") == query["ref"]]
        return emit_pages(items, query, o, expr)
    m = re.fullmatch(r"pulls/(\d+)", rest)
    if m and method == "GET":
        return emit(find_pull(slug, repo, m.group(1)), expr)
    m = re.fullmatch(r"pulls/(\d+)/merge", rest)
    if m and method == "PUT":
        pull = next((p for p in repo.get("pulls", []) if p["number"] == int(m.group(1))), None)
        if pull is None:
            raise http_fail(404, "Not Found")
        meth = fields.get("merge_method", "merge")
        if pull.get("merged_at") or pull["state"] != "open":
            raise http_fail(405, "Pull Request is not mergeable")
        if repo.get("merge_queue"):
            raise http_fail(405, "Changes must be made through the merge queue")
        if meth not in repo.get("allowed_methods", ["merge", "squash", "rebase"]):
            raise http_fail(405, f"{meth.capitalize()} merges are not allowed on this repository.")
        if fields.get("sha") and fields["sha"] != pull.get("head", {}).get("sha"):
            raise http_fail(409, "Head branch was modified. Review and try the merge again.")
        st["next_id"] = st.get("next_id", 1000) + 1
        sha = f"{st['next_id']:040x}"
        pull.update({"state": "closed", "merged_at": now(st), "merge_commit_sha": sha})
        return emit({"sha": sha, "merged": True, "message": "Pull Request successfully merged"}, expr)
    m = re.fullmatch(r"git/ref/heads/(.+)", rest)
    if m and method == "GET":
        b = m.group(1)
        if b not in repo.get("branches", {}):
            raise http_fail(404, "Not Found")
        return emit({"ref": f"refs/heads/{b}", "object": {"type": "commit", "sha": repo["branches"][b]}}, expr)
    m = re.fullmatch(r"git/refs/heads/(.+)", rest)
    if m and method == "DELETE":
        b = m.group(1)
        if b not in repo.get("branches", {}):
            raise http_fail(422, "Reference does not exist")
        if b in repo.get("protected_branches", []):
            raise http_fail(422, f"Cannot delete {b}: branch is protected")
        del repo["branches"][b]
        return
    m = re.fullmatch(r"pulls/(\d+)/comments/(\d+)/replies", rest)
    if m and method == "POST":
        viewer = whoami(st)
        pull = find_pull(slug, repo, m.group(1))
        thread = next((t for t in pull.get("threads", []) if any(c["databaseId"] == int(m.group(2)) for c in t["comments"])), None)
        if thread is None:
            raise Fail("gh: Not Found (HTTP 404)")
        c = add_thread_comment(st, slug, pull["number"], thread["id"], viewer, fields.get("body", ""))
        return emit({"id": c["databaseId"], "node_id": c["id"], "html_url": c["url"], "body": c["body"], "user": {"login": viewer},
                     "created_at": c["createdAt"], "in_reply_to_id": thread["comments"][0]["databaseId"]}, expr)
    m = re.fullmatch(r"pulls/comments/(\d+)/reactions", rest)
    if m and method == "POST":
        viewer = whoami(st)
        hit = next((c for p in repo.get("pulls", []) for t in p.get("threads", []) for c in t["comments"]
                    if c["databaseId"] == int(m.group(1))), None)
        content = fields.get("content", "")
        if hit is None or content not in ("+1", "-1"):
            raise Fail("gh: Not Found (HTTP 404)" if hit is None else "gh: Validation Failed (HTTP 422)")
        rest_react_once(st, slug, m.group(1), viewer, content)
        react_once(st, slug, hit["id"], viewer, "THUMBS_UP" if content == "+1" else "THUMBS_DOWN")
        return emit({"content": content, "user": {"login": viewer}}, expr)
    m = re.fullmatch(r"pulls/comments/(\d+)/reactions", rest)
    if m and method == "GET":
        items = [r for r in repo.get("review_comment_reactions", {}).get(m.group(1), [])
                 if not query.get("content") or r["content"] == query["content"].replace(" ", "+")]
        return emit_pages(items, query, o, expr)
    m = re.fullmatch(r"issues/(\d+)/comments", rest)
    if m:
        num = m.group(1)
        if method == "POST":
            return emit(new_comment(st, slug, num, fields.get("body", ""), whoami(st)), expr)
        if method == "GET":
            return emit_pages(repo.get("comments", {}).get(num, []), query, o, expr)
    m = re.fullmatch(r"issues/comments/(\d+)", rest)
    if m and method == "PATCH":
        for lst in repo.get("comments", {}).values():
            for c in lst:
                if c["id"] == int(m.group(1)):
                    c["body"] = fields.get("body", c["body"])
                    c["last_edited_at"] = now(st)
                    return emit(c, expr)
        raise Fail("gh: Not Found (HTTP 404)")
    raise Fail(f"fake gh: unsupported api call {method} {path}", 2)


def cmd_pr(st, args):
    sub, args = (args[:1] or [""])[0], args[1:]
    V = {"--repo": "repo", "-R": "repo", "--body": "body", "-b": "body", "--body-file": "body-file", "-F": "body-file",
         "--title": "title", "-t": "title", "--base": "base", "-B": "base", "--head": "head", "-H": "head",
         "--json": "json", "--jq": "jq", "-q": "jq"}
    o, pos = parse(args, V, ("--draft", "-d", "--web", "--edit-last"))
    slug, repo = repo_of(o, st)
    if sub == "create":
        head = one(o, "head")
        if not head:
            raise Fail("fake gh: pr create needs --head", 2)
        owner, _, ref = head.rpartition(":")
        owner = owner or slug.split("/")[0]
        pulls = repo.setdefault("pulls", [])
        if any(p["state"] == "open" and p["head"]["ref"] == ref and p["head"]["repo"]["full_name"].split("/")[0] == owner
               for p in pulls):
            raise Fail(f'a pull request for branch "{ref}" into branch "{one(o, "base", "main")}" already exists')
        n = max([p["number"] for p in pulls] + [0]) + 1
        pulls.append({"number": n, "html_url": pull_url(slug, n), "state": "open", "merged_at": None,
                      "title": one(o, "title", ""), "body": body_of(o) or "",
                      "head": {"ref": ref, "label": f"{owner}:{ref}", "sha": f"{n:040x}",
                               "repo": {"full_name": f"{owner}/{slug.split('/')[1]}"}},
                      "base": {"ref": one(o, "base") or repo.get("default_branch", "main")}})
        return print(pull_url(slug, n))
    if sub == "view":
        p = find_pull(slug, repo, pos[0] if pos else "")
        if "json" in o:
            v = graphql_view(p, slug)
            return emit({k: v[k] for k in one(o, "json").split(",") if k in v}, one(o, "jq"))
        return print(f"title:\t{p['title']}\nstate:\t{graphql_view(p, slug)['state']}\nurl:\t{p['html_url']}\n--\n{p['body']}")
    if sub == "comment":
        p = find_pull(slug, repo, pos[0] if pos else "")
        return print(new_comment(st, slug, p["number"], body_of(o) or "", whoami(st))["html_url"])
    if sub == "edit":
        p = find_pull(slug, repo, pos[0] if pos else "")
        if body_of(o) is not None:
            p["body"] = body_of(o)
        if "title" in o:
            p["title"] = one(o, "title")
        if "base" in o:
            p["base"]["ref"] = one(o, "base")
        return print(p["html_url"])
    raise Fail(f"fake gh: unsupported pr command {sub!r}", 2)


def cmd_repo(st, args):
    if args[:1] != ["view"]:
        raise Fail(f"fake gh: unsupported repo command {args[:1]}", 2)
    o, pos = parse(args[1:], {"--json": "json", "--jq": "jq", "-q": "jq"})
    slug = (pos[0] if pos else None) or os.environ.get("GH_REPO") or repo_of({}, st)[0]
    repo = st.setdefault("repos", {}).setdefault(slug, {})
    full = {"nameWithOwner": slug, "name": slug.split("/")[1], "owner": {"login": slug.split("/")[0]},
            "url": f"{HOST}/{slug}", "defaultBranchRef": {"name": repo.get("default_branch", "main")}}
    if "json" in o:
        return emit({k: full[k] for k in one(o, "json").split(",") if k in full}, one(o, "jq"))
    print(f"name:\t{slug}\nurl:\t{full['url']}")


def remote_has_tag(repo, tag):
    """Whether the tag exists on the remote: the state list repos[slug]["remote_tags"] when present (deterministic),
    else `git ls-remote --tags origin refs/tags/<tag>` in the cwd (test repos use a local bare origin)."""
    if "remote_tags" in repo:
        return tag in repo["remote_tags"]
    r = subprocess.run(["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"], capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def cmd_release(st, args):
    sub, args = (args[:1] or [""])[0], args[1:]
    V = {"--repo": "repo", "-R": "repo", "--title": "title", "-t": "title", "--notes": "notes", "-n": "notes",
         "--notes-file": "notes-file", "-F": "notes-file", "--json": "json", "--jq": "jq", "-q": "jq"}
    if sub not in ("view", "create"):
        raise Fail(f"fake gh: unsupported release command {sub!r}", 2)
    o, pos = parse(args, V, ("--verify-tag",))
    slug, repo = repo_of(o, st)
    if not pos:
        raise Fail(f"fake gh: release {sub} needs a tag", 2)
    tag = pos[0]
    releases = repo.setdefault("releases", {})
    if sub == "view":
        rel = releases.get(tag)
        if rel is None:
            raise Fail("release not found")
        full = {"tagName": rel["tag_name"], "name": rel.get("name", ""), "body": rel.get("body", ""),
                "url": f"{HOST}/{slug}/releases/tag/{tag}"}
        if "json" in o:
            return emit({k: full[k] for k in one(o, "json").split(",") if k in full}, one(o, "jq"))
        return print(f"title:\t{full['name']}\ntag:\t{tag}\nurl:\t{full['url']}\n--\n{full['body']}")
    if "verify-tag" in o and not remote_has_tag(repo, tag):
        raise Fail(f"tag {tag} doesn't exist in the repo {slug}, aborting due to --verify-tag flag")
    if tag in releases:
        raise Fail(f"a release with the same tag name already exists: {tag}")
    notes = read_file(one(o, "notes-file")) if "notes-file" in o else one(o, "notes", "")
    releases[tag] = {"tag_name": tag, "name": one(o, "title", tag), "body": notes, "created_at": now(st)}
    print(f"{HOST}/{slug}/releases/tag/{tag}")


def host_of(argv):
    """The host a call targets: --hostname, else a non-empty GH_HOST, else github.com."""
    for i, a in enumerate(argv):
        if a == "--hostname" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--hostname="):
            return a.partition("=")[2]
    return os.environ.get("GH_HOST") or "github.com"


def main(argv):
    for stream in (sys.stdout, sys.stdin):  # bodies and filter output carry non-ASCII text; no CRLF translation
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", **({"newline": "\n"} if stream is sys.stdout else {}))
    log(argv)
    st = load()
    try:
        inject_failure(st, argv)
        hostile(st, argv)
        if host_of(argv) != "github.com" and "--help" not in argv:
            raise Fail(f"fake gh: host {host_of(argv)} is not supported (only github.com)", 1)
        cmds = {"auth": cmd_auth, "api": cmd_api, "pr": cmd_pr, "repo": cmd_repo, "release": cmd_release}
        if not argv or argv[0] not in cmds:
            raise Fail(f"fake gh: unsupported command: {' '.join(argv)}", 2)
        cmds[argv[0]](st, argv[1:])
    except Fail as e:
        if e.body is not None:
            print(json.dumps(e.body))
        print(str(e), file=sys.stderr)
        return e.code
    save(st)
    return 0


def run(argv, env, stdin="", cwd=None):
    """Answer one call in this process, as `python gh.py <argv>` would: returns (code, stdout, stderr) as text.

    `env` replaces os.environ (in place, so jq and git children inherit it), `cwd` is the working directory when given, and
    stdin/stdout/stderr are in-memory streams. A SystemExit from main is the exit code. The cwd, the environment and the
    streams are restored afterwards, however main ended; an unexpected exception propagates. Not for the `hang` injection
    (it sleeps forever) or a PID file (the PID is this process's): use the process for those."""
    old_cwd, old_env = os.getcwd(), dict(os.environ)
    old_streams = sys.stdout, sys.stderr, sys.stdin
    out, err = io.StringIO(), io.StringIO()
    try:
        if cwd is not None:
            os.chdir(cwd)
        os.environ.clear()
        os.environ.update(env)
        sys.stdout, sys.stderr, sys.stdin = out, err, io.StringIO(stdin)
        try:
            code = main(list(argv))
        except SystemExit as e:
            code = e.code
        if code is None:
            code = 0
        elif not isinstance(code, int):  # sys.exit("msg") prints the message and exits 1
            err.write(f"{code}\n")
            code = 1
    finally:
        sys.stdout, sys.stderr, sys.stdin = old_streams
        os.chdir(old_cwd)
        os.environ.clear()
        os.environ.update(old_env)
    return code, out.getvalue(), err.getvalue()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
