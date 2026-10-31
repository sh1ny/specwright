"""Script tests for skills/specwright-pr/scripts/pr-pair.sh (PR-pair decisions for store-backed changes).

Every test runs the real script against real git repos in a temp dir (GitHub-form
remotes) and the fake gh from evals/fakes/gh.py. Tests that need a working push
reach a local bare repo through `url.<bare>.insteadOf`; none of those exercise
`identity` (git expands insteadOf when it reports a URL). Each pr-pair subcommand
prints one JSON line; exit 0 = answered, 1 = stop (error object), 2 = usage,
3 = GitHub state unknown.

Run: python -m unittest discover evals/pr-pair
"""
import datetime
import hashlib
import importlib.util
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import unittest.mock
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = ROOT / "skills" / "specwright-pr" / "scripts" / "pr-pair.sh"
sys.path.insert(0, str(ROOT / "evals" / "git-workflow"))
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
import fixtures  # noqa: E402
import jjenv  # noqa: E402

sys.path.append(str(ROOT / "evals"))
import fixturecache  # noqa: E402  per-process cache: the repo with its first commit is built once and copied
import bashexe  # noqa: E402

_spec = importlib.util.spec_from_file_location("fake_gh", ROOT / "evals" / "fakes" / "gh.py")
fake_gh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_gh)  # its state helpers (add_review_comment_reaction, add_node_reaction)

CODE, STORE = "acme/code", "acme/plans"
BRANCH, CHANGE = "feat/add-greeting", "add-greeting"
ARCHIVE = "openspec/changes/archive/2026-10-07-add-greeting"
SPEC_ARCHIVED = f"{ARCHIVE}/specs/greeting/spec.md"
SPEC_MAIN = "openspec/specs/greeting/spec.md"
MARKER = f"{ARCHIVE}/specwright-change.yaml"
OLD_TEXT, NEW_TEXT = "The system SHOULD greet", "The system SHALL greet"
T0 = "2026-10-08T10:00:00Z"
REV0 = f"11@{T0}"


def _build_repo(name, dest):
    """A repo on main with the one `chore: initial` commit and no remote: the stage make_repo caches (nothing in it names a path)."""
    env = {k: v for k, v in os.environ.items() if k.startswith(("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE",
                                                                         "GIT_CONFIG_"))}  # fixturecache: maintenance.auto=false
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    dest.mkdir(parents=True)
    for args in (("init", "-q", "-b", "main"), ("config", "user.name", "Eval Bot"), ("config", "user.email", "eval@example.invalid"),
                 ("config", "commit.gpgsign", "false")):
        subprocess.run(["git", *args], cwd=dest, check=True, capture_output=True, text=True, env=env)
    (dest / "README.md").write_text(f"# {name}\n", encoding="utf-8", newline="\n")
    for args in (("add", "-A"), ("commit", "-q", "-m", "chore: initial")):
        subprocess.run(["git", *args], cwd=dest, check=True, capture_output=True, text=True, env=env)


class CachedBuild(unittest.TestCase):
    def test_build_repo_passes_on_the_cache_git_config(self):
        """fixturecache turns off background maintenance through GIT_CONFIG_*; the whitelisted env must keep them."""
        calls = []
        real = subprocess.run

        def spy(argv, *a, **kw):
            calls.append((argv, kw.get("env")))
            return real(argv, *a, **kw)

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fixtures.rmtree, tmp)
        with fixturecache._no_auto_maintenance(), unittest.mock.patch.object(subprocess, "run", spy):
            _build_repo("demo", tmp / "repo")
        gits = [env for argv, env in calls if argv[0] == "git"]
        self.assertTrue(gits)
        for env in gits:
            n = int(env["GIT_CONFIG_COUNT"])
            pairs = {(env[f"GIT_CONFIG_KEY_{i}"], env[f"GIT_CONFIG_VALUE_{i}"]) for i in range(n)}
            self.assertIn(("maintenance.auto", "false"), pairs)


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fixtures.rmtree, self.tmp)
        (self.tmp / "bin").mkdir()
        fixtures.install_fake_gh(self.tmp)
        self.gh_state = self.tmp / "gh-state.json"
        self.gh_log = self.tmp / "gh-log.jsonl"
        self.gh_state.write_text(json.dumps({"user": "KintsugiBot", "tokens": {"KintsugiBot": "tok-k", "sh1ny": "tok-s"}}),
                                 encoding="utf-8")
        self.state_dir = self.tmp / "state"
        self.extra_env = {}

    # ---- environment -------------------------------------------------------------------------------------
    def env(self):
        e = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST")}
        e.update({"PATH": str(self.tmp / "bin") + os.pathsep + e.get("PATH", ""),
                  "FAKE_GH_STATE": str(self.gh_state), "FAKE_GH_LOG": str(self.gh_log),
                  "SPECWRIGHT_STATE_DIR": str(self.state_dir), "GIT_CONFIG_GLOBAL": os.devnull,
                  "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "PYTHONIOENCODING": "utf-8"})
        e.update(self.extra_env)
        return e

    def git(self, cwd, *args, check=True):
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=self.env())
        if check:
            self.assertEqual(r.returncode, 0, f"git {args}: {r.stderr}")
        return r.stdout.strip()

    def pp(self, *args, env=None, expect=0, cwd=None):
        """Run pr-pair.sh; return the parsed JSON line. The exit code must be `expect` (None = any)."""
        e = {**self.env(), **(env or {})}
        r = subprocess.run([bashexe.bash(), str(SCRIPT), *map(str, args)], capture_output=True, text=True, env=e, cwd=cwd or self.tmp)
        lines = r.stdout.strip().splitlines()
        if expect is not None:
            self.assertEqual(r.returncode, expect, f"{args}\nstdout: {r.stdout}\nstderr: {r.stderr}")
        self.assertEqual(len(lines), 1, f"want exactly one JSON line from {args}, got {r.stdout!r} / {r.stderr!r}")
        out = json.loads(lines[0])
        out["_rc"] = r.returncode
        return out

    # ---- git fixtures ------------------------------------------------------------------------------------
    def make_repo(self, name, remote):
        d = self.tmp / name
        fixturecache.copy(("pr-pair.make_repo", name), lambda dest: _build_repo(name, dest), d)
        if remote:
            self.git(d, "remote", "add", "origin", remote)
        return d

    def commit(self, repo, files, msg):
        for rel, text in files.items():
            p = Path(repo) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", msg)
        return self.git(repo, "rev-parse", "HEAD")

    def attach_bare(self, repo, slug):
        """Reach a local bare repo through insteadOf, so `origin` keeps its GitHub-form URL name."""
        bare = self.tmp / (Path(repo).name + ".bare.git")
        self.git(self.tmp, "init", "-q", "--bare", "-b", "main", str(bare))
        self.git(repo, "config", f"url.{fixtures.posix(bare)}.insteadOf", f"https://github.com/{slug}.git")
        self.git(repo, "push", "-q", "origin", "main")
        return bare

    def tip(self, repo, ref=BRANCH):
        return self.git(repo, "rev-parse", f"refs/heads/{ref}")

    # ---- fake gh state -----------------------------------------------------------------------------------
    def gh(self):
        return json.loads(self.gh_state.read_text(encoding="utf-8"))

    def save_gh(self, st):
        self.gh_state.write_text(json.dumps(st), encoding="utf-8")

    def seed_pulls(self, slug, pulls):
        st = self.gh()
        st.setdefault("repos", {}).setdefault(slug, {}).setdefault("pulls", []).extend(pulls)
        self.save_gh(st)

    def pull(self, slug, n, ref=BRANCH, state="open", merged=None, base="main", owner=None, head_repo=None, body="", sha=None):
        owner = owner or slug.split("/")[0]
        return {"number": n, "html_url": f"https://github.com/{slug}/pull/{n}", "state": state, "merged_at": merged,
                "title": f"t{n}", "body": body, "created_at": T0,
                "head": {"ref": ref, "label": f"{owner}:{ref}", "sha": sha or f"{n:040x}",
                         "repo": {"full_name": head_repo or f"{owner}/{slug.split('/')[1]}"}},
                "base": {"ref": base}}

    def add_pull(self, slug, n, **kw):
        self.seed_pulls(slug, [self.pull(slug, n, **kw)])

    def add_comment(self, slug, pr, body, user, cid, created_at=T0):
        st = self.gh()
        st["repos"].setdefault(slug, {}).setdefault("comments", {}).setdefault(str(pr), []).append(
            {"id": cid, "body": body, "user": {"login": user}, "created_at": created_at,
             "html_url": f"https://github.com/{slug}/pull/{pr}#issuecomment-{cid}"})
        self.save_gh(st)

    def comments(self, slug, pr):
        return self.gh().get("repos", {}).get(slug, {}).get("comments", {}).get(str(pr), [])

    def pulls(self, slug):
        return self.gh().get("repos", {}).get(slug, {}).get("pulls", [])

    def pushed_at(self, slug, branch, sha, ts):
        st = self.gh()
        st.setdefault("repos", {}).setdefault(slug, {}).setdefault("activity", []).append(
            {"ref": f"refs/heads/{branch}", "after": sha, "timestamp": ts})
        self.save_gh(st)

    def gh_calls(self):
        if not self.gh_log.exists():
            return []
        return [json.loads(l) for l in self.gh_log.read_text(encoding="utf-8").splitlines()]

    def write(self, rel, text):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        return p

    def write_json(self, rel, obj):
        return self.write(rel, json.dumps(obj))


def snap(threads=(), comments=(), reviews=(), viewer="KintsugiBot", pr=None, **over):
    """A pr-snapshot.sh result that passes the readiness test unless overridden.
    pr is a fake PR (Base.pull): the snapshot then takes its number, url and head_oid."""
    s = {"viewer": viewer, "number": 1, "url": "https://github.com/acme/x/pull/1", "state": "OPEN", "draft": False,
         "mergeable": "MERGEABLE", "merge_state": "CLEAN", "pending_review": False,
         "checks": {"total": 3, "pending": 0, "advisory_pending": 0, "failing": []},
         "threads": list(threads), "comments": list(comments), "reviews": list(reviews), "stale_verdicts": [],
         "reviewers": [{"login": "chatgpt-codex-connector", "role": "required", "timeout": 1200, "state": "reported"}],
         "complete": True, "truncated": []}
    if pr is not None:
        s.update(number=pr["number"], url=pr["html_url"], head_oid=pr["head"]["sha"])
    s.update(over)
    return s


def thread(tid="T1", rev=REV0, root_id=11, awaiting=False, resolved=False, resolve_pending=False, waiting_owner=False,
           comments=None):
    return {"id": tid, "root_id": root_id, "resolved": resolved, "rev": rev, "waiting_owner": waiting_owner,
            "awaiting_reviewer": awaiting, "resolve_pending": resolve_pending, "path": "x", "line": 1,
            "comments": comments or [{"id": "C11", "author": "chatgpt-codex-connector", "at": T0, "edited": None}]}


def _safe(t):
    return re.sub(r"[^A-Za-z0-9._-]", "_", t)


def record_key(repo, change):
    """The record's file name: readable owner.name.change (first 120 characters), then 32 hex of sha256(lower(owner), lower(name), change)."""
    owner, _, name = repo.partition("/")
    h = hashlib.sha256(f"{owner.lower()}\n{name.lower()}\n{change}".encode("utf-8")).hexdigest()[:32]
    return f"{_safe(owner)}.{_safe(name)}.{_safe(change)}"[:120].lower() + f"-{h}.json"


def legacy_key(repo, change):
    """The 0.1.9 file name."""
    owner, _, name = repo.partition("/")
    return f"{_safe(owner)}-{_safe(name)}-{_safe(change)}.json"


# =======================================================================================================
class Identity(Base):
    def test_identity_fetch_push_mismatch(self):
        d = self.make_repo("store", "https://github.com/team/plans.git")
        self.git(d, "remote", "set-url", "--push", "origin", "https://github.com/publishing/plans.git")
        r = self.pp("identity", d, expect=1)
        self.assertEqual(r["error"], "mismatch")
        self.assertEqual(r["fetch"], "team/plans")
        self.assertEqual(r["push"], ["publishing/plans"])
        self.assertIn("team/plans", r["message"])
        self.assertIn("publishing/plans", r["message"])
        self.assertEqual(self.gh_calls(), [], "a mismatch must stop before any GitHub lookup")

    def test_identity_every_push_url_must_match(self):
        d = self.make_repo("store", "https://github.com/team/plans.git")
        self.git(d, "remote", "set-url", "--push", "origin", "https://github.com/team/plans.git")
        self.git(d, "remote", "set-url", "--add", "--push", "origin", "git@github.com:other/plans.git")
        r = self.pp("identity", d, expect=1)
        self.assertEqual((r["error"], r["push"]), ("mismatch", ["team/plans", "other/plans"]))

    def test_identity_url_forms(self):
        for url in ("https://github.com/team/plans.git", "https://github.com/team/plans", "git@github.com:team/plans.git",
                    "ssh://git@github.com/team/plans.git", "https://x-access-token:tok@github.com/team/plans.git",
                    "ssh://git@ssh.github.com:443/team/plans.git", "git@ssh.github.com:team/plans.git"):
            d = self.make_repo("r" + str(abs(hash(url))), url)
            r = self.pp("identity", d)
            self.assertEqual((r["repo"], r["fetch"], r["push"]), ("team/plans", "team/plans", ["team/plans"]), url)

    def test_identity_not_github(self):
        d = self.make_repo("local", str(self.tmp / "elsewhere.git"))
        self.assertEqual(self.pp("identity", d, expect=1)["error"], "not-github")
        d2 = self.make_repo("gitlab", "https://gitlab.com/team/plans.git")
        self.assertEqual(self.pp("identity", d2, expect=1)["error"], "not-github")
        d3 = self.make_repo("noremote", None)
        self.assertEqual(self.pp("identity", d3, expect=1)["error"], "no-origin")


class Context(Base):
    def setUp(self):
        super().setUp()
        self.code = self.make_repo("code", f"https://github.com/{CODE}.git")
        self.store = self.make_repo("store", f"https://github.com/{STORE}.git")

    def settings(self, text):
        self.write("code/openspec/specwright.yaml", text)

    def test_context_login_per_repo(self):
        self.settings(
            "finish: pr\ngithub:\n  login: sh1ny\n"
            "planning_store:\n  login: KintsugiBot\n  main_branch: trunk\n  validate: \"openspec validate --all --strict\"\n"
            "  reviewers: {}\n"
            "pr:\n  validate: \"python -m unittest\"\n  max_fix_rounds: 3\n  react: true\n"
            "  reviewers:\n    chatgpt-codex-connector: { role: required, request: \"@codex review\" }\n"
            "    kody-ai: { role: advisory, timeout: 15m }\n")
        c = self.pp("context", "--code", self.code, "--store", self.store)
        self.assertEqual(c["code"]["login"], "sh1ny")
        self.assertEqual(c["store"]["login"], "KintsugiBot")
        self.assertEqual(c["code"]["main"], "main")
        self.assertEqual(c["store"]["main"], "trunk")
        self.assertEqual(c["code"]["validate"], "python -m unittest")
        self.assertEqual(c["store"]["validate"], "openspec validate --all --strict")
        self.assertEqual(c["store"]["reviewers"], {})
        self.assertEqual(c["code"]["reviewers"]["chatgpt-codex-connector"], {"role": "required", "timeout": 1200, "request": "@codex review"})
        self.assertEqual(c["code"]["reviewers"]["kody-ai"], {"role": "advisory", "timeout": 900, "request": ""})
        self.assertEqual((c["max_fix_rounds"], c["react"]), (3, True))

    def test_context_store_inherits_defaults(self):
        self.settings("github:\n  login: sh1ny\npr:\n  validate: \"python -m unittest\"\n"
                      "  reviewers:\n    kody-ai: { role: advisory }\n")
        self.git(self.store, "branch", "-m", "master")
        c = self.pp("context", "--code", self.code, "--store", self.store)
        self.assertEqual(c["store"]["login"], "sh1ny")
        self.assertEqual(c["store"]["validate"], "")  # the code validate command is meaningless in the store
        self.assertEqual(c["store"]["reviewers"], c["code"]["reviewers"])
        self.assertEqual((c["code"]["main"], c["store"]["main"]), ("main", "master"))
        self.assertEqual(c["code"]["reviewers"]["kody-ai"]["timeout"], 1200)

    def test_context_block_scalars(self):
        # `|` and `>` values are read whole, and the keys after them still count.
        self.settings("github:\n  login: sh1ny\n"
                      "planning_store:\n  validate: >-\n    openspec validate\n    --all --strict\n\n  login: KintsugiBot\n"
                      "pr:\n  validate: |\n    python -m unittest  # not a comment\n\n    openspec validate --all\n"
                      "  max_fix_rounds: 3\n  reviewers:\n    kody-ai: { role: advisory }\n")
        c = self.pp("context", "--code", self.code, "--store", self.store)
        self.assertEqual(c["code"]["validate"], "python -m unittest  # not a comment\n\nopenspec validate --all\n")
        self.assertEqual(c["store"]["validate"], "openspec validate --all --strict")
        self.assertEqual(c["store"]["login"], "KintsugiBot")
        self.assertEqual(c["max_fix_rounds"], 3)
        self.assertEqual(c["code"]["reviewers"]["kody-ai"]["role"], "advisory")

    def test_context_decodes_quoted_scalars(self):
        # quoted values are decoded as YAML does: escapes in double quotes, '' in single quotes
        self.settings("github:\n  login: 'sh1ny'\n"
                      "planning_store:\n  validate: 'echo ''ok'' # still the value'\n"
                      "pr:\n  validate: \"python -c \\\"print('ok')\\\" # not a comment\\tdone\\x21\\L\\P\"\n"
                      "  reviewers:\n    chatgpt-codex-connector: { role: required, request: \"@codex \\\"review, now\\\"\" }\n")
        c = self.pp("context", "--code", self.code, "--store", self.store)
        self.assertEqual(c["code"]["validate"], "python -c \"print('ok')\" # not a comment\tdone!\u2028\u2029")
        self.assertEqual(c["store"]["validate"], "echo 'ok' # still the value")
        self.assertEqual(c["code"]["reviewers"]["chatgpt-codex-connector"]["request"], "@codex \"review, now\"")

    def test_context_merge_defaults(self):
        self.settings("github:\n  login: sh1ny\npr:\n  reviewers:\n    kody-ai: { role: advisory }\n")
        c = self.pp("context", "--code", self.code, "--store", self.store)
        self.assertEqual((c["merge"], c["merge_method"], c["delete_branch"]), ("user", "merge", True))
        self.assertNotIn("merge_note", c)

    def test_context_merge_agent_settings_read(self):
        self.settings("pr:\n  merge: agent\n  merge_method: squash\n  delete_branch: false\n")
        c = self.pp("context", "--code", self.code)
        self.assertEqual((c["merge"], c["merge_method"], c["delete_branch"]), ("agent", "squash", False))
        self.assertNotIn("merge_note", c)

    def test_context_merge_unknown_value_reported_as_user(self):
        self.settings("pr:\n  merge: auto\n  reviewers:\n    chatgpt-codex-connector: { role: required }\n")
        c = self.pp("context", "--code", self.code)
        self.assertEqual(c["merge"], "user")
        self.assertEqual(c["merge_note"], "pr.merge: auto is not user or agent; treated as user")

    def test_context_merge_yes_reported_as_written(self):
        # YAML reads `yes` as true; the note names the value as the user wrote it
        for written in ("yes", "Yes", "true", "on"):
            self.settings(f"pr:\n  merge: {written}\n")
            c = self.pp("context", "--code", self.code)
            self.assertEqual(c["merge"], "user", written)
            self.assertEqual(c["merge_note"], f"pr.merge: {written} is not user or agent; treated as user")

    def test_context_merge_ready_with_required_reviewer(self):
        self.settings("pr:\n  merge: agent\n  reviewers:\n    chatgpt-codex-connector: { role: required }\n"
                      "    kody-ai: { role: advisory }\n")
        c = self.pp("context", "--code", self.code, "--store", self.store)
        for repo in ("code", "store"):  # the store falls back to pr.reviewers
            self.assertIs(c[repo]["merge_ready"], True, repo)
            self.assertIsNone(c[repo]["merge_reason"], repo)

    def test_context_merge_blocked_without_required_reviewer(self):
        self.settings("pr:\n  merge: agent\n  reviewers:\n    kody-ai: { role: advisory }\n")
        c = self.pp("context", "--code", self.code)
        self.assertIs(c["code"]["merge_ready"], False)
        self.assertEqual(c["code"]["merge_reason"], "no_required_reviewer")
        self.settings("pr:\n  merge: agent\n")
        c = self.pp("context", "--code", self.code)
        self.assertEqual((c["code"]["merge_ready"], c["code"]["merge_reason"]), (False, "no_required_reviewer"))

    def test_context_merge_blocked_store_reviewers_empty(self):
        self.settings("planning_store:\n  reviewers: {}\npr:\n  merge: agent\n"
                      "  reviewers:\n    chatgpt-codex-connector: { role: required }\n")
        c = self.pp("context", "--code", self.code, "--store", self.store)
        self.assertIs(c["code"]["merge_ready"], True)
        self.assertIs(c["store"]["merge_ready"], False)
        self.assertEqual(c["store"]["merge_reason"], "no_required_reviewer")

    def test_context_merge_method_bad_value(self):
        self.settings("pr:\n  merge: agent\n  merge_method: fast-forward\n")
        r = self.pp("context", "--code", self.code, expect=2)
        self.assertEqual((r["ok"], r["error"]), (False, "bad_setting"))
        self.assertEqual(r["message"], "pr.merge_method: fast-forward must be merge, squash or rebase")

    def test_context_delete_branch_non_boolean(self):
        self.settings("pr:\n  merge: agent\n  delete_branch: maybe\n")
        r = self.pp("context", "--code", self.code, expect=2)
        self.assertEqual((r["ok"], r["error"]), (False, "bad_setting"))
        self.assertIn("pr.delete_branch", r["message"])
        self.assertIn("maybe", r["message"])

    def test_context_merge_settings_ignored_in_user_mode(self):
        # only the agent merge reads them: a bad value must not stop ship, watch or cleanup in user mode
        for merge in ("", "  merge: user\n", "  merge: auto\n"):
            self.settings("pr:\n" + merge + "  merge_method: fast-forward\n  delete_branch: maybe\n")
            c = self.pp("context", "--code", self.code)
            self.assertEqual((c["merge"], c["merge_method"], c["delete_branch"]), ("user", "merge", True), merge)


# =======================================================================================================
class Discover(Base):
    def test_discover_paginates_past_fork_prs(self):
        # 130 newer PRs share the head label (a deleted/other-repo head) and 30 more come from a fork;
        # the change's own PR is the oldest and merged, so it sits on page 2 of the 100-per-page listing.
        noise = [self.pull(CODE, n, head_repo="acme/other-fork") for n in range(11, 141)]
        forks = [self.pull(CODE, n, owner="forker") for n in range(141, 171)]
        own = self.pull(CODE, 3, state="closed", merged="2026-10-01T00:00:00Z")
        self.seed_pulls(CODE, [own, *noise, *forks])
        r = self.pp("discover", "--repo", CODE, "--branch", BRANCH, "--base", "main")
        self.assertEqual([p["number"] for p in r["prs"]], [3])
        self.assertEqual(r["prs"][0]["state"], "MERGED")
        self.assertTrue(r["ok"])
        call = [c for c in self.gh_calls() if c["argv"][:1] == ["api"] and "pulls" in " ".join(c["argv"])][0]["argv"]
        self.assertIn("--paginate", call)
        endpoint = call[-1]
        self.assertTrue(endpoint.startswith(f"repos/{CODE}/pulls?"), endpoint)
        for part in ("state=all", f"head=acme:{BRANCH}", "per_page=100"):
            self.assertIn(part, endpoint)

    def test_discover_filters_base_and_state(self):
        self.seed_pulls(CODE, [self.pull(CODE, 1, state="closed"), self.pull(CODE, 2, base="integration"),
                               self.pull(CODE, 3, state="closed", merged="2026-10-01T00:00:00Z"), self.pull(CODE, 4)])
        nums = lambda *a: [p["number"] for p in self.pp("discover", "--repo", CODE, "--branch", BRANCH, *a)["prs"]]
        self.assertEqual(nums(), [4, 3, 2, 1])
        self.assertEqual(nums("--base", "main"), [4, 3, 1])
        self.assertEqual(nums("--base", "main", "--state", "merged"), [3])
        self.assertEqual(nums("--base", "main", "--state", "open,closed"), [4, 1])
        r = self.pp("discover", "--repo", CODE, "--branch", BRANCH, "--base", "main")
        self.assertEqual([p["number"] for p in r["other_base"]], [2])

    def test_discover_carries_merge_commit_sha(self):
        merged = self.pull(CODE, 3, state="closed", merged="2026-10-01T00:00:00Z")
        merged["merge_commit_sha"] = "a" * 40
        self.seed_pulls(CODE, [merged, self.pull(CODE, 4)])
        r = self.pp("discover", "--repo", CODE, "--branch", BRANCH, "--base", "main")
        by_number = {p["number"]: p for p in r["prs"]}
        self.assertEqual(by_number[3]["merge_commit_sha"], "a" * 40)
        self.assertIsNone(by_number[4]["merge_commit_sha"])
        newest_merged = self.pp("discover", "--repo", CODE, "--branch", BRANCH, "--base", "main", "--state", "merged")["newest"]
        self.assertEqual(newest_merged["merge_commit_sha"], "a" * 40)

    def test_discover_failure_is_unknown(self):
        st = self.gh()
        st["fail"] = [{"match": r"api .*repos/acme/code/pulls", "exit": 1, "stderr": "HTTP 502"}]
        self.save_gh(st)
        r = self.pp("discover", "--repo", CODE, "--branch", BRANCH, expect=3)
        self.assertFalse(r["ok"])
        self.assertTrue(r["unknown"])
        self.assertIn("502", r["message"])


# =======================================================================================================
class Expected(Base):
    """The expected PR set follows the change's work (code PR exists or code commits) and transport (store origin)."""

    def setUp(self):
        super().setUp()
        self.code = self.make_repo("code", f"https://github.com/{CODE}.git")
        self.store = self.make_repo("store", f"https://github.com/{STORE}.git")
        for d in (self.code, self.store):
            self.git(d, "checkout", "-q", "-b", BRANCH)

    def expected(self, **kw):
        return self.pp("expected", "--code", self.code, "--store", self.store, "--branch", BRANCH, **kw)

    def test_expected_planning_only_github_store(self):
        r = self.expected()
        self.assertEqual(r["set"], ["store"])
        self.assertFalse(r["code"]["expected"])
        self.assertEqual(r["code"]["commits"], 0)
        self.assertEqual(r["store"]["repo"], STORE)
        self.assertEqual(r["ship"]["report"], "store_only")
        self.assertIn("no code changes", r["ship"]["note"].lower())

    def test_expected_planning_only_local_store(self):
        self.git(self.store, "remote", "set-url", "origin", str(self.tmp / "plans.git"))
        r = self.expected()
        self.assertEqual(r["set"], [])
        self.assertFalse(r["store"]["expected"])
        self.assertEqual(r["ship"]["report"], "none")
        self.assertIn("by hand", r["ship"]["note"])

    def test_expected_code_only_when_store_has_no_github_origin(self):
        self.git(self.store, "remote", "remove", "origin")
        self.commit(self.code, {"greet.py": "x = 1\n"}, "feat(add-greeting): task 1.1")
        r = self.expected()
        self.assertEqual((r["set"], r["ship"]["report"]), (["code"], "code_only"))

    def test_expected_gains_code_pr_after_code_commit(self):
        self.assertEqual(self.expected()["set"], ["store"])
        self.commit(self.code, {"greet.py": "x = 1\n"}, "fix(add-greeting): address review feedback")
        r = self.expected()
        self.assertEqual(r["set"], ["store", "code"])
        self.assertEqual((r["code"]["commits"], r["code"]["reason"]), (1, "commits"))
        self.assertEqual(r["ship"]["report"], "both")

    def test_expected_mismatched_store_stops_the_set(self):
        self.git(self.store, "remote", "set-url", "--push", "origin", "https://github.com/publishing/plans.git")
        self.assertEqual(self.expected(expect=1)["error"], "mismatch")

    def test_expected_reads_the_store_with_the_store_login(self):
        # a private store only planning_store.login can read: pair-wide calls run as the code login (as.sh) yet still see it
        self.commit(self.code, {"openspec/specwright.yaml": "github:\n  login: KintsugiBot\nplanning_store:\n  login: sh1ny\n"},
                    "chore: settings")
        st = self.gh()
        st.setdefault("repos", {})[STORE] = {"readers": ["sh1ny"]}
        self.save_gh(st)
        self.add_pull(STORE, 3)
        r = self.expected(env={"GH_TOKEN": "tok-k"})
        self.assertEqual(r["store"]["pr"]["number"], 3)
        store_calls = [c for c in self.gh_calls() if any(STORE in a for a in c["argv"])]
        self.assertTrue(store_calls)
        # the code login still reads the code repo itself
        self.assertEqual(r["set"], ["store", "code"])

    def test_expected_stops_when_the_store_login_has_no_credential(self):
        self.commit(self.code, {"openspec/specwright.yaml": "github:\n  login: KintsugiBot\nplanning_store:\n  login: nobody\n"},
                    "chore: settings")
        r = self.expected(env={"GH_TOKEN": "tok-k"}, expect=3)
        self.assertEqual(r["error"], "no_credential")

    def test_expected_unknown_when_lookup_fails(self):
        st = self.gh()
        st["fail"] = [{"match": r"api .*repos/acme/code/pulls", "exit": 1, "stderr": "HTTP 500"}]
        self.save_gh(st)
        self.assertTrue(self.expected(expect=3)["unknown"])


# =======================================================================================================
class Ship(Base):
    """ship = ensure-pr store, ensure-pr code (store URL in its new description), link each PR to the other."""

    def setUp(self):
        super().setUp()
        self.login = "KintsugiBot"

    def ensure(self, slug, title, body, expect=0):
        f = self.write(f"{slug.replace('/', '-')}-body.md", body)
        return self.pp("ensure-pr", "--repo", slug, "--branch", BRANCH, "--base", "main", "--title", title, "--body-file", f,
                       expect=expect)

    def link(self, slug, pr, kind, peer, expect=0):
        return self.pp("link", "--repo", slug, "--pr", pr, "--kind", kind, "--peer-url", peer, "--login", self.login,
                       expect=expect)

    def ship(self, stop_after_store=False):
        s = self.ensure(STORE, f"docs({CHANGE}): plan", "Planning for add-greeting.\n")
        if stop_after_store:
            return s, None
        c = self.ensure(CODE, f"feat({CHANGE}): add greeting", f"Code for add-greeting.\n\nStore PR: {s['pr']['url']}\n")
        self.link(CODE, c["pr"]["number"], "store", s["pr"]["url"])
        self.link(STORE, s["pr"]["number"], "code", c["pr"]["url"])
        return s, c

    def markers(self, slug, pr):
        return [c for c in self.comments(slug, pr) if "<!-- specwright:link " in c["body"]]

    def test_ship_sequence_links_both(self):
        s, c = self.ship()
        self.assertEqual((s["action"], c["action"]), ("created", "created"))
        self.assertIn(s["pr"]["url"], self.pulls(CODE)[0]["body"])  # the code PR description carries the store link
        store_markers = self.markers(STORE, s["pr"]["number"])
        self.assertEqual(len(store_markers), 1)
        self.assertIn(f"<!-- specwright:link code {c['pr']['url']} -->", store_markers[0]["body"])
        self.assertEqual(self.markers(CODE, c["pr"]["number"]), [], "the description already links the store PR")

    def test_link_existing_code_pr_by_comment(self):
        self.add_pull(CODE, 7, body="Hand-written description, no link.")
        self.add_pull(STORE, 2)
        peer = f"https://github.com/{STORE}/pull/2"
        r = self.link(CODE, 7, "store", peer)
        self.assertEqual(r["action"], "created")
        ms = self.markers(CODE, 7)
        self.assertEqual(len(ms), 1)
        self.assertIn(f"<!-- specwright:link store {peer} -->", ms[0]["body"])
        self.assertEqual(self.pulls(CODE)[0]["body"], "Hand-written description, no link.")
        self.assertEqual(self.link(CODE, 7, "store", peer)["action"], "skipped")
        self.assertEqual(len(self.markers(CODE, 7)), 1)
        self.assertFalse([c for c in self.gh_calls() if c["argv"][:2] == ["pr", "edit"]])

    def test_ship_sequence_rerun_is_idempotent(self):
        s1, _ = self.ship(stop_after_store=True)  # an interrupted first run
        self.assertEqual(len(self.pulls(STORE)), 1)
        self.assertEqual(self.pulls(CODE), [])
        s2, c2 = self.ship()
        self.assertEqual((s2["action"], c2["action"]), ("found", "created"))
        self.assertEqual(s2["pr"]["number"], s1["pr"]["number"])
        s3, c3 = self.ship()  # and once more
        self.assertEqual((s3["action"], c3["action"]), ("found", "found"))
        self.assertEqual((len(self.pulls(STORE)), len(self.pulls(CODE))), (1, 1))
        self.assertEqual(len(self.markers(STORE, 1)), 1)
        self.assertEqual(len(self.markers(CODE, 1)), 0)
        self.assertIn(s1["pr"]["url"], self.pulls(CODE)[0]["body"])

    def test_link_updates_own_comment_for_new_peer(self):
        old, new = f"https://github.com/{CODE}/pull/5", f"https://github.com/{CODE}/pull/6"
        self.add_pull(CODE, 5, state="closed")
        self.add_pull(CODE, 6)
        self.add_pull(STORE, 2)
        self.add_comment(STORE, 2, f"Code PR: {old}\n\n<!-- specwright:link code {old} -->", self.login, 1500)
        r = self.link(STORE, 2, "code", new)
        self.assertEqual(r["action"], "updated")
        ms = self.markers(STORE, 2)
        self.assertEqual([m["id"] for m in ms], [1500])
        self.assertIn(f"<!-- specwright:link code {new} -->", ms[0]["body"])
        self.assertNotIn(old, ms[0]["body"])
        self.assertEqual(len(self.comments(STORE, 2)), 1)

    def test_link_leaves_other_users_comments_alone(self):
        old, new = f"https://github.com/{CODE}/pull/5", f"https://github.com/{CODE}/pull/6"
        self.add_pull(STORE, 2)
        theirs = f"quoted: <!-- specwright:link code {old} -->"
        self.add_comment(STORE, 2, theirs, "someone-else", 1500)
        r = self.link(STORE, 2, "code", new)
        self.assertEqual(r["action"], "created")
        by_id = {c["id"]: c for c in self.comments(STORE, 2)}
        self.assertEqual(by_id[1500]["body"], theirs)
        self.assertEqual(len(by_id), 2)

    def test_link_skipped_when_description_has_the_link(self):
        peer = f"https://github.com/{STORE}/pull/2"
        self.add_pull(CODE, 7, body=f"See {peer}")
        self.assertEqual(self.link(CODE, 7, "store", peer)["action"], "skipped")
        self.assertEqual(self.comments(CODE, 7), [])

    def test_ensure_pr_stops_on_wrong_base(self):
        self.add_pull(CODE, 9, base="integration")
        r = self.ensure(CODE, "t", "b", expect=1)
        self.assertEqual(r["error"], "wrong_base")
        self.assertEqual((r["pr"]["number"], r["base"]), (9, "integration"))
        self.assertIn("integration", r["message"])
        self.assertEqual(len(self.pulls(CODE)), 1)
        self.assertFalse([c for c in self.gh_calls() if c["argv"][:2] == ["pr", "create"]])

    def test_ensure_pr_replaces_a_closed_unmerged_pr_but_not_a_merged_one(self):
        self.add_pull(CODE, 5, state="closed")
        r = self.ensure(CODE, "t", "b")
        self.assertEqual((r["action"], r["pr"]["number"]), ("created", 6))
        self.add_pull(STORE, 1, state="closed", merged="2026-10-01T00:00:00Z")
        r = self.ensure(STORE, "t", "b", expect=1)
        self.assertEqual(r["error"], "already_merged")
        self.assertEqual(len(self.pulls(STORE)), 1)

    def test_gh_repo_env_ignored(self):
        # GH_REPO names the code repo; every store lookup must still hit the store's origin repository
        self.add_pull(STORE, 9, body="store pr")
        env = {"GH_REPO": CODE}
        d = self.pp("discover", "--repo", STORE, "--branch", BRANCH, "--base", "main", env=env)
        self.assertEqual([p["url"] for p in d["prs"]], [f"https://github.com/{STORE}/pull/9"])
        e = self.pp("ensure-pr", "--repo", STORE, "--branch", BRANCH, "--base", "main", "--title", "t",
                    "--body-file", self.write("b.md", "b"), env=env)
        self.assertEqual((e["action"], e["pr"]["number"]), ("found", 9))
        self.pp("link", "--repo", STORE, "--pr", 9, "--kind", "code", "--peer-url", f"https://github.com/{CODE}/pull/1",
                "--login", self.login, env=env)
        self.assertEqual(len(self.comments(STORE, 9)), 1)
        self.assertEqual(self.comments(CODE, 9), [])
        self.assertEqual(self.pulls(CODE), [])
        calls = self.gh_calls()
        self.assertTrue(calls)
        for c in calls:
            self.assertIsNone(c["gh_repo"], f"GH_REPO must be unset for {c['argv']}")
            a = c["argv"]
            if a[0] == "api":
                self.assertTrue(any(x.startswith("repos/") for x in a) or "user" in a, f"unscoped api call {a}")
            if a[0] == "pr":
                self.assertTrue("--repo" in a or "-R" in a, f"pr command without --repo: {a}")


# =======================================================================================================
class PairState(Base):
    def setUp(self):
        super().setUp()
        self.code = self.make_repo("code", f"https://github.com/{CODE}.git")
        self.store = self.make_repo("store", f"https://github.com/{STORE}.git")
        for d in (self.code, self.store):
            self.git(d, "checkout", "-q", "-b", BRANCH)

    def snap(self, slug, n=1, **kw):
        """A passing snapshot of the fake PR slug#n, as pr-snapshot.sh would report it."""
        pr = next(p for p in self.pulls(slug) if p["number"] == n)
        return snap(pr=pr, **kw)

    def state(self, code=None, store=None, dropped=(), expect=0):
        args = ["pair-state", "--code", self.code, "--store", self.store, "--branch", BRANCH]
        for name, s in (("code", code), ("store", store)):
            if s is not None:
                args += ["--snapshot", f"{name}={self.write_json(f'{name}-snap.json', s)}"]
        for d in dropped:
            args += ["--dropped", d]
        return self.pp(*args, expect=expect)

    def test_pair_state_waits_for_both(self):
        self.commit(self.code, {"greet.py": "x = 1\n"}, "feat(add-greeting): task 1.1")
        self.add_pull(CODE, 1)
        self.add_pull(STORE, 1)
        unresolved = thread(comments=[{"id": "C1", "author": "chatgpt-codex-connector", "at": T0, "edited": None}])
        r = self.state(code=self.snap(CODE), store=self.snap(STORE, threads=[unresolved]))
        self.assertEqual(r["set"], ["store", "code"])
        self.assertEqual(r["action"], "wait")
        self.assertEqual(r["ready"], {"code": True, "store": False})
        self.assertEqual(r["waiting_on"], ["store"])
        self.assertIn("threads", r["blocking"]["store"])
        self.assertEqual(sorted(r["waits"]), ["code", "store"])

    def test_pair_state_refreshes_an_old_head_snapshot(self):
        self.add_pull(STORE, 1, sha="b" * 40)
        old = snap(number=1, url=f"https://github.com/{STORE}/pull/1", head_oid="a" * 40)
        r = self.state(store=old)
        self.assertEqual(r["action"], "wait")
        self.assertEqual(r["ready"], {"store": False})
        self.assertEqual(r["refresh"], ["store"])
        self.assertIn("refresh:head:aaaaaaa!=bbbbbbb", r["blocking"]["store"])

    def test_pair_state_refreshes_an_old_head_code_snapshot(self):
        self.commit(self.code, {"greet.py": "x = 1\n"}, "feat(add-greeting): task 1.1")
        self.add_pull(CODE, 9, sha="b" * 40)
        self.add_pull(STORE, 1)
        old = snap(number=9, url=f"https://github.com/{CODE}/pull/9", head_oid="a" * 40)  # passes every readiness check
        r = self.state(code=old, store=self.snap(STORE))
        self.assertEqual(r["action"], "wait")
        self.assertEqual(r["ready"], {"code": False, "store": True})
        self.assertEqual(r["refresh"], ["code"])
        self.assertIn("refresh:head:aaaaaaa!=bbbbbbb", r["blocking"]["code"])

    def test_pair_state_refreshes_a_snapshot_of_another_pr(self):
        self.commit(self.code, {"greet.py": "x = 1\n"}, "feat(add-greeting): task 1.1")
        self.add_pull(CODE, 9)
        self.add_pull(STORE, 1)
        other = snap(number=7, url=f"https://github.com/{CODE}/pull/7", head_oid=f"{9:040x}")
        r = self.state(code=other, store=self.snap(STORE))
        self.assertEqual(r["action"], "wait")
        self.assertEqual(r["ready"], {"code": False, "store": True})
        self.assertEqual(r["refresh"], ["code"])
        self.assertIn("refresh:pr:7!=9", r["blocking"]["code"])

    def test_pair_state_refreshes_a_snapshot_without_a_head(self):
        self.add_pull(STORE, 1)
        for drop in ("head_oid", "number"):
            s = self.snap(STORE)
            del s[drop]
            r = self.state(store=s)
            self.assertEqual(r["action"], "wait", drop)
            self.assertEqual(r["refresh"], ["store"], drop)
            self.assertTrue([b for b in r["blocking"]["store"] if b.startswith("refresh:")], drop)

    def test_pair_state_ready_only_when_both_pass(self):
        self.commit(self.code, {"greet.py": "x = 1\n"}, "feat(add-greeting): task 1.1")
        self.add_pull(CODE, 1)
        self.add_pull(STORE, 1)
        r = self.state(code=self.snap(CODE), store=self.snap(STORE))
        self.assertEqual((r["action"], r["ready"]), ("ready", {"code": True, "store": True}))
        r = self.state(code=self.snap(CODE, checks={"total": 2, "pending": 1, "advisory_pending": 0, "failing": []}), store=self.snap(STORE))
        self.assertEqual((r["action"], r["waiting_on"]), ("wait", ["code"]))
        # a dropped item (id@rev) does not block
        t = thread()
        r = self.state(code=self.snap(CODE), store=self.snap(STORE, threads=[t]), dropped=[f"T1@{REV0}"])
        self.assertEqual(r["action"], "ready")

    def test_pair_state_single_store_pr_ready(self):
        self.add_pull(STORE, 1)
        r = self.state(store=self.snap(STORE))
        self.assertEqual(r["set"], ["store"])
        self.assertEqual((r["action"], r["ready"]), ("ready", {"store": True}))
        self.assertFalse(r.get("share_store_by_hand"))

    def test_pair_state_code_only_names_the_store_branch(self):
        self.git(self.store, "remote", "remove", "origin")
        self.commit(self.code, {"greet.py": "x = 1\n"}, "feat(add-greeting): task 1.1")
        self.add_pull(CODE, 1)
        r = self.state(code=self.snap(CODE))
        self.assertEqual((r["set"], r["action"], r["share_store_by_hand"]), (["code"], "ready", True))

    def test_pair_state_empty_set_does_not_watch(self):
        self.git(self.store, "remote", "remove", "origin")
        r = self.state()
        self.assertEqual((r["set"], r["action"]), ([], "no_watch"))

    def test_pair_state_split_hands_off(self):
        self.commit(self.code, {"greet.py": "x = 1\n"}, "feat(add-greeting): task 1.1")
        self.add_pull(CODE, 1)
        self.add_pull(STORE, 1, state="closed", merged="2026-10-08T09:00:00Z")
        r = self.state(code=self.snap(CODE), store=self.snap(STORE, state="MERGED"))
        self.assertEqual(r["action"], "split_hand_off")
        self.assertTrue(r["stop_waits"])
        self.assertEqual(r["states"], {"store": "MERGED", "code": "OPEN"})
        self.assertEqual((r["merged"], r["open"]), (["store"], ["code"]))
        self.assertFalse(r["archive"])
        self.assertFalse(r["rerequest"])

    def test_pair_state_merged_code_pr_stays_expected(self):
        # the code PR merged and main was pulled: the code branch has no commits after main any more
        self.add_pull(CODE, 5, state="closed", merged="2026-10-08T09:00:00Z")
        self.add_pull(STORE, 2)
        e = self.pp("expected", "--code", self.code, "--store", self.store, "--branch", BRANCH)
        self.assertEqual(e["set"], ["store", "code"])
        self.assertEqual((e["code"]["commits"], e["code"]["reason"]), (0, "pr_exists"))
        r = self.state(store=self.snap(STORE, 2))
        self.assertEqual(r["action"], "split_hand_off")
        self.assertEqual(r["states"], {"store": "OPEN", "code": "MERGED"})
        self.assertTrue(r["stop_waits"])
        self.assertFalse(r["archive"])

    def test_pair_state_every_pr_merged_goes_to_cleanup(self):
        self.add_pull(CODE, 5, state="closed", merged="2026-10-08T09:00:00Z")
        self.add_pull(STORE, 2, state="closed", merged="2026-10-08T09:30:00Z")
        self.assertEqual(self.state()["action"], "cleanup")

    def test_pair_state_missing_pr_needs_ship(self):
        self.commit(self.code, {"greet.py": "x = 1\n"}, "feat(add-greeting): task 1.1")
        self.add_pull(STORE, 1)
        r = self.state(store=self.snap(STORE))
        self.assertEqual((r["action"], r["missing"]), ("ship", ["code"]))


# =======================================================================================================
class Rounds(Base):
    def setUp(self):
        super().setUp()
        self.code = self.make_repo("code", f"https://github.com/{CODE}.git")
        self.store = self.make_repo("store", f"https://github.com/{STORE}.git")
        for d in (self.code, self.store):
            self.git(d, "checkout", "-q", "-b", BRANCH)
        self.write("code/openspec/specwright.yaml", "pr:\n  max_fix_rounds: 2\n")
        self.git(self.code, "add", "-A")
        self.git(self.code, "commit", "-q", "-m", "chore: settings")

    def rounds(self):
        return self.pp("rounds", "--code", self.code, "--store", self.store, "--branch", BRANCH)

    def test_remote_contains_jj_moves_no_ref(self):
        """On a jj repo the tip fetch of remote_contains writes FETCH_HEAD only: refs/remotes/origin/<branch> stays put."""
        jj = jjenv.require_jj()
        bares = {}
        for d, slug in ((self.code, CODE), (self.store, STORE)):
            bares[d] = self.attach_bare(d, slug)
            self.git(d, "push", "-q", "origin", BRANCH)
        fix = self.commit(self.store, {"a.md": "1\n"}, "fix(add-greeting): address review feedback\n\nFeedback-Round: 2")
        self.git(self.store, "push", "-q", "origin", BRANCH)
        other = self.tmp / "other-store"
        self.git(self.tmp, "clone", "-q", "-b", BRANCH, fixtures.posix(bares[self.store]), str(other))
        self.git(other, "config", "user.name", "Other")
        self.git(other, "config", "user.email", "other@example.com")
        self.commit(other, {"b.md": "2\n"}, "docs: someone else's commit")
        self.git(other, "push", "-q", "origin", BRANCH)
        theirs = self.tip(other)
        r = subprocess.run([jj, "git", "init", "--colocate"], cwd=self.store, capture_output=True, text=True, env=self.env())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        tracking = f"refs/remotes/origin/{BRANCH}"
        self.assertEqual(self.git(self.store, "rev-parse", tracking), fix)
        r = self.rounds()
        self.assertEqual((r["unpushed"], r["remote_unreadable"]), ({}, []))
        self.assertEqual(self.git(self.store, "rev-parse", tracking), fix)  # not advanced to the other checkout's tip
        self.assertEqual(self.git(self.store, "rev-parse", "FETCH_HEAD"), theirs)

    def test_rounds_highest_across_branches(self):
        self.commit(self.store, {"a.md": "1\n"}, "fix(add-greeting): address review feedback\n\nFeedback-Round: 1")
        self.commit(self.code, {"a.py": "2\n"}, "fix(add-greeting): address review feedback\n\nFeedback-Round: 2")
        r = self.rounds()
        self.assertEqual(r["rounds"], 2)
        self.assertEqual((r["code"]["max_trailer"], r["store"]["max_trailer"]), (2, 1))
        self.assertEqual(r["max_fix_rounds"], 2)
        self.assertTrue(r["limit_reached"])

    def test_rounds_below_limit(self):
        self.commit(self.store, {"a.md": "1\n"}, "fix(add-greeting): address review feedback\n\nFeedback-Round: 1")
        r = self.rounds()
        self.assertEqual((r["rounds"], r["limit_reached"]), (1, False))

    def test_rounds_legacy_subject_count_without_trailers(self):
        self.commit(self.code, {"a.py": "1\n"}, "fix(add-greeting): address review feedback")
        self.commit(self.code, {"a.py": "2\n"}, "fix(add-greeting): address review feedback")
        r = self.rounds()
        self.assertEqual((r["rounds"], r["code"]["subject_count"], r["limit_reached"]), (2, 2, True))

    def test_rounds_ignore_preship_fix_commits(self):
        # pre-ship review fixes have their own subject and trailer, so they never count as PR feedback rounds
        self.commit(self.code, {"a.py": "1\n"}, "feat(add-greeting): address pre-ship review\n\nPreship-Round: 1")
        self.commit(self.code, {"a.py": "2\n"}, "feat(add-greeting): address pre-ship review\n\nPreship-Round: 2")
        r = self.rounds()
        self.assertEqual((r["rounds"], r["code"]["subject_count"], r["limit_reached"]), (0, 0, False))

    def test_rounds_ignores_subject_count_when_trailers_exist(self):
        # a round-1 partial recovery: two commits carry the round-1 trailer, so the subject count of 2 is not the round
        self.commit(self.code, {"a.py": "1\n"}, "fix(add-greeting): address review feedback\n\nFeedback-Round: 1")
        self.commit(self.code, {"a.py": "2\n"}, "fix(add-greeting): address review feedback\n\nFeedback-Round: 1")
        r = self.rounds()
        self.assertEqual((r["rounds"], r["limit_reached"]), (1, False))

    def test_rounds_store_only_round_makes_the_next_pass_round_two(self):
        # max_fix_rounds is 2; only the store branch has a fix commit, so the code branch counts for nothing
        self.commit(self.store, {"a.md": "1\n"}, "fix(add-greeting): address review feedback\n\nFeedback-Round: 1")
        r = self.rounds()
        self.assertEqual((r["rounds"], r["code"]["max_trailer"], r["store"]["max_trailer"]), (1, 0, 1))
        self.assertEqual((r["max_fix_rounds"], r["limit_reached"]), (2, False))
        self.assertEqual(r["rounds"] + 1, 2)  # the next pass is round 2, within the limit

    def test_rounds_ignores_code_subjects_when_store_has_a_trailer(self):
        self.commit(self.store, {"a.md": "1\n"}, "fix(add-greeting): address review feedback\n\nFeedback-Round: 1")
        self.commit(self.code, {"a.py": "1\n"}, "fix(add-greeting): address review feedback")
        self.commit(self.code, {"a.py": "2\n"}, "fix(add-greeting): address review feedback")
        r = self.rounds()
        self.assertEqual((r["rounds"], r["limit_reached"]), (1, False))
        self.assertEqual(r["code"]["subject_count"], 2)  # seen, but not the round: a trailer exists on the store branch

    def test_rounds_unpushed_top_round_commits(self):
        for d, slug in ((self.code, CODE), (self.store, STORE)):
            self.attach_bare(d, slug)
            self.git(d, "push", "-q", "origin", BRANCH)
        sha = self.commit(self.store, {"a.md": "1\n"}, "fix(add-greeting): address review feedback\n\nFeedback-Round: 2")
        r = self.rounds()
        self.assertEqual(r["unpushed"], {"store": [sha]})
        self.git(self.store, "push", "-q", "origin", BRANCH)
        self.assertEqual(self.rounds()["unpushed"], {})

    def test_rounds_pushed_fix_under_a_remote_tip_this_checkout_lacks(self):
        # another checkout pushed on top of our fix: its tip is not in this repo, yet the fix is on the remote
        bares = {}
        for d, slug in ((self.code, CODE), (self.store, STORE)):
            bares[d] = self.attach_bare(d, slug)
            self.git(d, "push", "-q", "origin", BRANCH)
        self.commit(self.store, {"a.md": "1\n"}, "fix(add-greeting): address review feedback\n\nFeedback-Round: 2")
        self.git(self.store, "push", "-q", "origin", BRANCH)
        other = self.tmp / "other-store"
        self.git(self.tmp, "clone", "-q", "-b", BRANCH, fixtures.posix(bares[self.store]), str(other))
        self.git(other, "config", "user.name", "Other")
        self.git(other, "config", "user.email", "other@example.com")
        self.commit(other, {"b.md": "2\n"}, "docs: someone else's commit")
        self.git(other, "push", "-q", "origin", BRANCH)
        r = self.rounds()
        self.assertEqual((r["unpushed"], r["remote_unreadable"]), ({}, []))

    # ---- the store is read through as.sh from inside it, whatever the logins (default-identity-fencing D6) ----
    FIX = "fix(add-greeting): address review feedback\n\nFeedback-Round: 1"

    def dead_store_remote(self):
        """The store's GitHub origin is unreachable (a dead proxy): the read fails fast, but the calls before it are logged."""
        self.git(self.store, "config", "http.proxy", "http://127.0.0.1:9")
        return self.commit(self.store, {"a.md": "1\n"}, self.FIX)

    def test_context_empty_store_login_uses_code_run_login(self):
        # both logins empty: the store login stays empty, and the store is read as the code run login through as.sh,
        # started inside the store (so its URLs and headers are checked), not with plain git
        self.dead_store_remote()
        c = self.pp("context", "--code", self.code, "--store", self.store)
        self.assertEqual((c["code"]["login"], c["store"]["login"]), ("", ""))
        r = self.pp("rounds", "--code", self.code, "--store", self.store, "--branch", BRANCH, cwd=self.code)
        here = os.path.normcase(os.path.realpath(self.store))
        fenced = [c for c in self.gh_calls() if c["argv"][:2] == ["auth", "token"] and "--user" in c["argv"]
                  and os.path.normcase(os.path.realpath(c["cwd"])) == here]
        self.assertTrue(fenced, "the store read must run as.sh from inside the store")
        self.assertEqual({c["argv"][-1] for c in fenced}, {"KintsugiBot"}, "the run login is the ambient (fenced) login")

    def test_rounds_store_login_kept_with_non_github_push_url(self):
        # PR #82: the store fetches from github.com but pushes elsewhere; rounds still reads it as planning_store.login,
        # taken from the fetch URL, not as the code login or the ambient one (both KintsugiBot here)
        self.write("code/openspec/specwright.yaml", "github:\n  login: KintsugiBot\nplanning_store:\n  login: sh1ny\n")
        self.git(self.store, "remote", "set-url", "--push", "origin", "https://git.example.com/o/s.git")
        self.dead_store_remote()
        self.pp("rounds", "--code", self.code, "--store", self.store, "--branch", BRANCH, cwd=self.code, expect=None)
        here = os.path.normcase(os.path.realpath(self.store))
        users = {c["argv"][-1] for c in self.gh_calls() if c["argv"][:2] == ["auth", "token"] and "--user" in c["argv"]
                 and os.path.normcase(os.path.realpath(c["cwd"])) == here}
        self.assertEqual(users, {"sh1ny"}, "the store must be read as planning_store.login, not the code or ambient login")

    def test_rounds_under_as_sh_reads_non_github_store_with_user_git(self):
        # PR #82: pair-wide commands run under as.sh; a store on another host is read with the user's own git
        # (their GIT_SSH_COMMAND, prompts, helpers), not the outer fence's SSH block, and never sees the fence's token
        self.git(self.store, "remote", "set-url", "origin", "ssh://git@git.example.com/o/s.git")
        self.commit(self.store, {"a.md": "1\n"}, self.FIX)
        seen = self.tmp / "ssh-seen.txt"
        ssh = self.write("user-ssh.sh", f'#!/bin/sh\necho "token=${{GH_TOKEN:-unset}}" >> "{fixtures.posix(seen)}"\nexit 1\n')
        as_sh = ROOT / "skills" / "specwright-pr" / "scripts" / "as.sh"
        e = {**self.env(), "GIT_SSH_COMMAND": f"sh {fixtures.posix(ssh)}"}
        r = subprocess.run([bashexe.bash(), str(as_sh), "KintsugiBot", "bash", str(SCRIPT), "rounds", "--code", str(self.code),
                            "--store", str(self.store), "--branch", BRANCH], capture_output=True, text=True, env=e, cwd=self.code)
        self.assertIn('"ok": true', r.stdout, r.stdout + r.stderr)
        self.assertNotIn("SSH is disabled", r.stdout + r.stderr, "the store read ran inside the outer fence")
        self.assertTrue(seen.exists(), "the user's GIT_SSH_COMMAND did not run for the non-GitHub store")
        self.assertEqual(set(seen.read_text(encoding="utf-8").split()), {"token=unset"}, "the fence's token reached the non-GitHub remote")

    def rounds_enterprise_store(self, env):
        """rounds under as.sh with a non-GitHub store whose remote answers 401, so its `gh auth git-credential` helper is
        asked; the fake gh logs the helper call's environment. The remote is plain http through a proxy that is the 401
        server (an https remote would not reach the helper without a TLS server)."""
        class Rec(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="ghe"')
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", 0), Rec)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        self.addCleanup(t.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.git(self.store, "remote", "set-url", "origin", "http://ghe.example/o/s.git")
        self.git(self.store, "config", "http.proxy", f"http://127.0.0.1:{server.server_port}")
        self.git(self.store, "config", "credential.helper", "!gh auth git-credential")
        self.commit(self.store, {"a.md": "1\n"}, self.FIX)
        as_sh = ROOT / "skills" / "specwright-pr" / "scripts" / "as.sh"
        e = {**self.env(), "NO_PROXY": "", "no_proxy": "", **env}
        r = subprocess.run([bashexe.bash(), str(as_sh), "KintsugiBot", "bash", str(SCRIPT), "rounds", "--code", str(self.code),
                            "--store", str(self.store), "--branch", BRANCH], capture_output=True, text=True, env=e, cwd=self.code)
        helper = [c for c in self.gh_calls() if c["argv"][:2] == ["auth", "git-credential"]]
        self.assertTrue(helper, f"the store's credential helper never ran: {r.stdout}{r.stderr}")
        return helper

    def test_rounds_non_github_store_gets_enterprise_vars(self):
        # fix-m2-gaps D5: as.sh unsets the enterprise variables for its own fence, but the unfenced read of a non-GitHub
        # store gets the caller's back, so a helper such as `gh auth git-credential` finds its host and token
        helper = self.rounds_enterprise_store({"GH_HOST": "ghe.example", "GH_ENTERPRISE_TOKEN": "ent-1",
                                               "GITHUB_ENTERPRISE_TOKEN": "ent-2"})
        for c in helper:
            self.assertEqual((c["env"]["GH_HOST"], c["env"]["GH_ENTERPRISE_TOKEN"], c["env"]["GITHUB_ENTERPRISE_TOKEN"]),
                             ("ghe.example", "ent-1", "ent-2"))
            self.assertIsNone(c["env"]["GH_TOKEN"], "the fence's token must not reach a non-GitHub remote")

    def test_rounds_non_github_store_without_enterprise_vars(self):
        # variables the caller never set stay unset in the unfenced read, never an empty string
        helper = self.rounds_enterprise_store({})
        for c in helper:
            self.assertEqual((c["env"]["GH_HOST"], c["env"]["GH_ENTERPRISE_TOKEN"], c["env"]["GITHUB_ENTERPRISE_TOKEN"]),
                             (None, None, None))

    def test_trailing_dot_store_remote_is_fenced(self):
        # fix-m2-gaps D4: https://github.com./o/s.git is GitHub: read through as.sh from inside the store, never unfenced
        self.git(self.store, "remote", "set-url", "origin", f"https://github.com./{STORE}.git")
        self.git(self.store, "config", "http.proxy", "http://127.0.0.1:9")
        self.commit(self.store, {"a.md": "1\n"}, self.FIX)
        self.pp("rounds", "--code", self.code, "--store", self.store, "--branch", BRANCH, cwd=self.code, expect=None)
        here = os.path.normcase(os.path.realpath(self.store))
        fenced = [c for c in self.gh_calls() if c["argv"][:2] == ["auth", "token"] and "--user" in c["argv"]
                  and os.path.normcase(os.path.realpath(c["cwd"])) == here]
        self.assertTrue(fenced, "a trailing-dot GitHub store must be read through as.sh from inside it")

    def test_rounds_store_token_url_exits_3_no_request(self):
        # both logins empty and the store origin carries a token: as.sh refuses inside the store, before any request
        seen = []

        class Rec(BaseHTTPRequestHandler):
            def do_CONNECT(self):
                seen.append(self.path)
                self.send_response(502)
                self.end_headers()

            do_GET = do_CONNECT

            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", 0), Rec)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        self.addCleanup(t.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.git(self.store, "remote", "set-url", "origin", f"https://x-access-token:SECRETtok@github.com/{STORE}.git")
        self.git(self.store, "config", "http.proxy", f"http://127.0.0.1:{server.server_port}")
        self.commit(self.store, {"a.md": "1\n"}, self.FIX)
        r = self.pp("rounds", "--code", self.code, "--store", self.store, "--branch", BRANCH, cwd=self.code, expect=3)
        self.assertFalse(r["ok"])
        self.assertNotIn("remote_unreadable", r)
        self.assertNotIn("SECRETtok", json.dumps(r))
        self.assertEqual(seen, [], "no request may reach the server")

    def test_rounds_store_token_url_with_non_github_push_url_exits_3(self):
        # PR #82: the store fetches from github.com but pushes elsewhere; the fetch URL alone decides the fence, so the
        # token in it is still refused, never sent by a plain-git read
        seen = []

        class Rec(BaseHTTPRequestHandler):
            def do_CONNECT(self):
                seen.append(self.path)
                self.send_response(502)
                self.end_headers()

            do_GET = do_CONNECT

            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", 0), Rec)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        self.addCleanup(t.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.git(self.store, "remote", "set-url", "origin", f"https://x-access-token:SECRETtok@github.com/{STORE}.git")
        self.git(self.store, "remote", "set-url", "--push", "origin", "https://git.example.com/o/s.git")
        self.git(self.store, "config", "http.proxy", f"http://127.0.0.1:{server.server_port}")
        self.commit(self.store, {"a.md": "1\n"}, self.FIX)
        r = self.pp("rounds", "--code", self.code, "--store", self.store, "--branch", BRANCH, cwd=self.code, expect=3)
        self.assertFalse(r["ok"])
        self.assertNotIn("remote_unreadable", r)
        self.assertNotIn("SECRETtok", json.dumps(r))
        self.assertEqual(seen, [], "no request may reach the server")

    def test_token_for_unsets_host_variables(self):
        # a pinned store login: the gh calls that look up and verify its token never see GH_HOST or enterprise tokens
        self.write("code/openspec/specwright.yaml",
                   "github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\nplanning_store:\n  login: sh1ny\n")
        self.git(self.code, "add", "-A")
        self.git(self.code, "commit", "-q", "-m", "chore: logins")
        self.dead_store_remote()
        host ={"GH_HOST": "ghe.example.com", "GH_ENTERPRISE_TOKEN": "ent-1", "GITHUB_ENTERPRISE_TOKEN": "ent-2"}
        self.pp("rounds", "--code", self.code, "--store", self.store, "--branch", BRANCH, env=host, cwd=self.code)
        calls = self.gh_calls()
        self.assertTrue([c for c in calls if c["argv"][:2] == ["auth", "token"] and c["argv"][-1] == "sh1ny"])
        for c in calls:
            for k in host:
                self.assertIsNone(c["env"][k], f"{k} reached gh {c['argv']}")


# =======================================================================================================
class PassBase(Base):
    """Both repos on BRANCH with a pushed baseline: pushes go to local bare repos behind GitHub-form remotes."""

    def setUp(self):
        super().setUp()
        self.code = self.make_repo("code", f"https://github.com/{CODE}.git")
        self.store = self.make_repo("store", f"https://github.com/{STORE}.git")
        self.attach_bare(self.code, CODE)
        self.attach_bare(self.store, STORE)
        for d in (self.code, self.store):
            self.git(d, "checkout", "-q", "-b", BRANCH)
        self.commit(self.code, {"greet.py": "def greet(n):\n    return n\n"}, "feat(add-greeting): task 1.1")
        self.commit(self.store, {SPEC_ARCHIVED: f"{OLD_TEXT} by name.\n", SPEC_MAIN: f"{OLD_TEXT} by name.\n"},
                    "chore(add-greeting): archive change")
        self.settings("github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n  react: true\n"
                      "  reviewers:\n    chatgpt-codex-connector: { role: required, request: \"@codex review\" }\n")

    def settings(self, text):
        self.commit(self.code, {"openspec/specwright.yaml": text}, "chore: settings")
        for d in (self.code, self.store):
            self.git(d, "push", "-q", "origin", BRANCH)

    # ---- the record ----
    def finding(self, fid="F1", source="code", dest="store", kind="thread", item="T1", resolve=True, react="+1", edits=None,
                rev=REV0, at=T0):
        if edits is None:
            edits = [{"file": SPEC_ARCHIVED, "contains": [NEW_TEXT], "absent": [OLD_TEXT]},
                     {"file": SPEC_MAIN, "contains": [NEW_TEXT], "absent": [OLD_TEXT]}] if dest == "store" else [
                {"file": "greet.py", "contains": ["strip()"]}]
        return {"id": fid, "source": source, "destination": dest, "kind": kind, "item": item, "root_id": 11,
                "edits": edits, "disposition": {"reply": True, "resolve": resolve, "react": react},
                "revision": {"rev": rev, "last_reviewer_comment": {"id": "C11", "at": at}}}

    def intent(self, findings, rnd=2):
        return {"change": CHANGE, "branch": BRANCH, "round": rnd, "code_repo": CODE,
                "prs": {"code": {"repo": CODE, "number": 5}, "store": {"repo": STORE, "number": 3}},
                "findings": findings}

    def common(self):
        return ["--code", self.code, "--store", self.store, "--code-repo", CODE, "--change", CHANGE]

    def write_record(self, findings, rnd=2, intent=None, expect=0):
        f = self.write_json("intent.json", intent or self.intent(findings, rnd))
        out = self.pp("pass", "write", *self.common(), "--intent", f, expect=expect)
        if out.get("ok"):
            self.owner = out["owner"]  # the id `pass write` returns; plan and done carry it
        return out

    def record_path(self):
        return self.state_dir / "feedback" / record_key(CODE, CHANGE)

    def plan(self, code=None, store=None, sub="plan", expect=0):
        args = ["pass", sub, *self.common()]
        if getattr(self, "owner", None):
            args += ["--owner", self.owner]
        for name, s in (("code", code), ("store", store)):
            args += ["--snapshot", f"{name}={self.write_json(f'{name}-snap.json', s if s is not None else snap())}"]
        return self.pp(*args, expect=expect)

    @staticmethod
    def row(plan, step, repo=None, finding=None):
        rows = [r for r in plan["rows"] if r["step"] == step and (repo is None or r.get("repo") == repo)
                and (finding is None or r.get("finding") == finding)]
        assert len(rows) == 1, f"want one {step}/{repo}/{finding} row in {[(r['step'], r.get('repo'), r.get('finding')) for r in plan['rows']]}"
        return rows[0]

    # ---- progress ----
    def fix_store(self, rnd=2, message="fix(add-greeting): address review feedback"):
        return self.commit(self.store, {SPEC_ARCHIVED: f"{NEW_TEXT} by name.\n", SPEC_MAIN: f"{NEW_TEXT} by name.\n"},
                           f"{message}\n\nFeedback-Round: {rnd}")

    def fix_code(self, rnd=2):
        return self.commit(self.code, {"greet.py": "def greet(n):\n    return n.strip()\n"},
                           f"fix(add-greeting): address review feedback\n\nFeedback-Round: {rnd}")

    def push_all(self, *repos):
        for d in repos or (self.code, self.store):
            self.git(d, "push", "-q", "origin", BRANCH)


class PassPlan(PassBase):
    def test_pass_plan_routes_spec_fix_to_store(self):
        # a reviewer on the code PR asks for a spec change: the fix lands in the store, the reply goes to the code PR
        w = self.write_record([self.finding()])
        self.assertTrue(w["ok"])
        rec = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertEqual((rec["round"], rec["heads"]["store"], rec["heads"]["code"]),
                         (2, self.tip(self.store), self.tip(self.code)))
        p = self.plan(code=snap(threads=[thread()]))
        fix = self.row(p, "fix_commit", "store")
        self.assertEqual((fix["state"], fix["trailer"]), ("todo", "Feedback-Round: 2"))
        self.assertEqual(sorted(fix["files"]), sorted([SPEC_ARCHIVED, SPEC_MAIN]))
        self.assertEqual(len(fix["pending_edits"]), 2)
        self.assertNotIn("fix_commit", [(r["step"]) for r in p["rows"] if r.get("repo") == "code"])
        self.assertFalse(p["new_pass_allowed"])
        # once the store fix is committed, push + re-request go to the store PR and the reply to the code PR
        sha = self.fix_store()
        p = self.plan(code=snap(threads=[thread()]))
        self.assertEqual(self.row(p, "fix_commit", "store")["state"], "done")
        self.assertEqual(self.row(p, "push", "store")["state"], "todo")
        rr = self.row(p, "rerequest", "store")
        self.assertEqual(rr["pr"], {"repo": STORE, "number": 3})
        reply = self.row(p, "reply", finding="F1")
        self.assertEqual((reply["state"], reply["pr"]), ("todo", {"repo": CODE, "number": 5}))
        self.assertEqual(reply["link_commit"], {"repo": STORE, "sha": sha})
        self.assertTrue(reply["resolve"])
        self.assertTrue(all(r.get("repo") != "code" or r["step"] == "reply" for r in p["rows"] if r["step"] in ("fix_commit", "push")))

    def test_pass_plan_final_pass_push_pending(self):
        # max_fix_rounds is 2 and pass 2 committed in both repos, but the store push failed
        self.write_record([self.finding("F1", dest="store"), self.finding("F2", dest="code", item="T2", source="store")])
        self.fix_code()
        self.fix_store()
        self.push_all(self.code)
        r = self.pp("rounds", "--code", self.code, "--store", self.store, "--branch", BRANCH)
        self.assertTrue(r["limit_reached"])
        p = self.plan(code=snap(threads=[thread()]), store=snap(threads=[thread("T2")]))
        self.assertEqual(self.row(p, "fix_commit", "code")["state"], "done")
        self.assertEqual(self.row(p, "fix_commit", "store")["state"], "done")
        self.assertEqual(self.row(p, "push", "code")["state"], "done")
        self.assertEqual(self.row(p, "push", "store")["state"], "todo")
        self.assertEqual(self.row(p, "rerequest", "store")["state"], "todo")
        self.assertEqual(self.row(p, "reply", finding="F1")["state"], "todo")
        self.assertFalse(p["new_pass_allowed"])
        self.assertEqual(p["round"], 2)
        self.assertFalse(p["delete_record"])
        self.assertFalse([s for s in p["stops"]], "no after-limit stop: the pass is finished under its own round")

    def test_pass_plan_missing_store_commit(self):
        self.write_record([self.finding("F1", dest="store"), self.finding("F2", dest="code", item="T2", source="store")])
        self.fix_code()
        p = self.plan(code=snap(threads=[thread()]), store=snap(threads=[thread("T2")]))
        self.assertEqual(self.row(p, "fix_commit", "code")["state"], "done")
        store_fix = self.row(p, "fix_commit", "store")
        self.assertEqual((store_fix["state"], store_fix["trailer"]), ("todo", "Feedback-Round: 2"))
        self.assertEqual(p["round"], 2)
        self.assertFalse(p["new_pass_allowed"])
        self.assertFalse([r for r in p["rows"] if r["step"] == "fix_commit" and r["repo"] == "code" and r["state"] != "done"])

    def test_pass_plan_rerequest_and_replies_pending(self):
        self.write_record([self.finding("F1", dest="store"), self.finding("F2", dest="code", item="T2", source="store")])
        self.fix_code()
        self.fix_store()
        self.push_all()
        self.pushed_at(CODE, BRANCH, self.tip(self.code), "2026-10-08T12:00:00Z")
        self.pushed_at(STORE, BRANCH, self.tip(self.store), "2026-10-08T12:00:05Z")
        p = self.plan(code=snap(threads=[thread()]), store=snap(threads=[thread("T2")]))
        for repo in ("code", "store"):
            self.assertEqual(self.row(p, "fix_commit", repo)["state"], "done")
            self.assertEqual(self.row(p, "push", repo)["state"], "done")
            rr = self.row(p, "rerequest", repo)
            self.assertEqual(rr["state"], "todo")
            self.assertEqual(rr["requests"][0]["body"], "@codex review")
        self.assertEqual(self.row(p, "reply", finding="F1")["state"], "todo")
        self.assertEqual(self.row(p, "reply", finding="F2")["state"], "todo")
        self.assertFalse(p["delete_record"])
        # a request posted after the push is found by the timestamp rule and is not posted again
        self.add_comment(STORE, 3, "@codex review", "KintsugiBot", 2001, created_at="2026-10-08T12:00:06Z")
        self.add_comment(CODE, 5, "@codex review", "KintsugiBot", 2002, created_at="2026-10-08T11:59:59Z")  # before the push
        p = self.plan(code=snap(threads=[thread()]), store=snap(threads=[thread("T2")]))
        self.assertEqual(self.row(p, "rerequest", "store")["state"], "done")
        self.assertEqual(self.row(p, "rerequest", "code")["state"], "todo")

    def test_pass_plan_commit_found_by_trailer(self):
        self.write_record([self.finding("F1", dest="code", source="code", edits=[{"file": "greet.py", "contains": ["strip()"]}])])
        p = self.plan(code=snap(threads=[thread()]))
        self.assertEqual(self.row(p, "fix_commit", "code")["state"], "todo")
        # a commit after the recorded head without the trailer is not the pass's fix
        self.commit(self.code, {"other.py": "x = 1\n"}, "fix(add-greeting): unrelated")
        p = self.plan(code=snap(threads=[thread()]))
        self.assertEqual(self.row(p, "fix_commit", "code")["state"], "todo")
        sha = self.fix_code()
        p = self.plan(code=snap(threads=[thread()]))
        fix = self.row(p, "fix_commit", "code")
        self.assertEqual((fix["state"], fix["sha"]), ("done", sha))
        self.assertEqual(self.row(p, "push", "code")["state"], "todo")
        self.assertEqual(self.row(p, "reply", finding="F1")["state"], "todo")
        self.assertEqual(self.git(self.code, "rev-list", "--count", f"{json.loads(self.record_path().read_text(encoding='utf-8'))['heads']['code']}..HEAD"), "2")

    def test_pass_plan_reply_done_resolution_pending(self):
        self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}])])
        self.fix_code()
        self.push_all()
        self.pushed_at(CODE, BRANCH, self.tip(self.code), "2026-10-08T12:00:00Z")
        self.add_comment(CODE, 5, "@codex review", "KintsugiBot", 2002, created_at="2026-10-08T12:00:03Z")
        answered = thread(awaiting=True, resolve_pending=True,
                          comments=[{"id": "C11", "author": "chatgpt-codex-connector", "at": T0, "edited": None},
                                    {"id": "C12", "author": "KintsugiBot", "at": "2026-10-08T12:01:00Z", "edited": None}],
                          rev="12@2026-10-08T12:01:00Z")
        p = self.plan(code=snap(threads=[answered]))
        self.assertEqual(self.row(p, "reply", finding="F1")["state"], "done")
        res = self.row(p, "resolve", finding="F1")
        self.assertEqual(res["state"], "ask")
        self.assertEqual(res["thread"], "T1")
        self.assertTrue(p["needs_user"])
        self.assertFalse(p["delete_record"])
        self.assertEqual(p["status"], "resume")
        self.assertFalse([r for r in p["rows"] if r["step"] == "reply" and r["state"] == "todo"])
        self.assertTrue(self.record_path().exists())

    def test_pass_plan_stale_disposition_stops(self):
        self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}])])
        self.fix_code()
        self.push_all()
        follow_up = {"id": "C13", "author": "chatgpt-codex-connector", "at": "2026-10-08T12:30:00Z", "edited": None}
        t = thread(rev="13@2026-10-08T12:30:00Z", comments=[
            {"id": "C11", "author": "chatgpt-codex-connector", "at": T0, "edited": None}, follow_up])
        p = self.plan(code=snap(threads=[t]))
        self.assertEqual(p["status"], "stop")
        stop = [s for s in p["stops"] if s["reason"] == "stale_disposition"]
        self.assertEqual(len(stop), 1)
        self.assertEqual(stop[0]["finding"], "F1")
        self.assertEqual([a["id"] for a in stop[0]["new_activity"]], ["C13"])
        reply = self.row(p, "reply", finding="F1")
        self.assertEqual(reply["state"], "stopped")
        self.assertEqual(self.row(p, "resolve", finding="F1")["state"], "stopped")
        self.assertFalse(p["delete_record"])
        # an edit of the finding changes the revision even without a new comment
        edited = thread(rev=f"11@2026-10-08T12:40:00Z", comments=[
            {"id": "C11", "author": "chatgpt-codex-connector", "at": T0, "edited": "2026-10-08T12:40:00Z"}])
        p = self.plan(code=snap(threads=[edited]))
        self.assertEqual([s["reason"] for s in p["stops"]], ["stale_disposition"])

    def test_pass_plan_partial_edit_not_committable(self):
        self.write_record([self.finding()])
        self.write(f"store/{SPEC_ARCHIVED}", f"{NEW_TEXT} by name.\n")  # stopped after the archived delta only
        p = self.plan(code=snap(threads=[thread()]))
        fix = self.row(p, "fix_commit", "store")
        self.assertEqual(fix["state"], "todo")
        self.assertFalse(fix["committable"])
        self.assertEqual(fix["action"], "finish_edits")
        self.assertEqual([e["file"] for e in fix["pending_edits"]], [SPEC_MAIN])
        reply = self.row(p, "reply", finding="F1")
        self.assertEqual(reply["state"], "todo")
        self.assertIn("fix_commit:store", reply["after"])
        self.write(f"store/{SPEC_MAIN}", f"{NEW_TEXT} by name.\n")
        p = self.plan(code=snap(threads=[thread()]))
        fix = self.row(p, "fix_commit", "store")
        self.assertTrue(fix["committable"])
        self.assertEqual(fix["action"], "validate_and_commit")
        self.assertEqual(fix["pending_edits"], [])
        self.assertEqual(sorted(fix["files"]), sorted([SPEC_ARCHIVED, SPEC_MAIN]))

    def test_pass_plan_trailer_commit_with_part_of_the_edits_is_not_done(self):
        # an interrupted pass committed and pushed the archived delta only: the trailer commit is not the whole fix
        self.write_record([self.finding()])
        self.commit(self.store, {SPEC_ARCHIVED: f"{NEW_TEXT} by name.\n"},
                    "fix(add-greeting): address review feedback\n\nFeedback-Round: 2")
        self.push_all(self.store)
        partial = self.tip(self.store)
        p = self.plan(code=snap(threads=[thread()]))
        fix = self.row(p, "fix_commit", "store")
        self.assertEqual((fix["state"], fix["sha"], fix["partial_commit"]), ("todo", None, partial))
        self.assertEqual(fix["action"], "finish_edits")
        self.assertEqual([e["file"] for e in fix["pending_edits"]], [SPEC_MAIN])
        self.assertTrue(self.row(p, "push", "store")["blocked"])
        self.assertEqual(self.row(p, "reply", finding="F1")["state"], "todo")
        # the rest made but not committed: still todo, now committable
        self.write(f"store/{SPEC_MAIN}", f"{NEW_TEXT} by name.\n")
        fix = self.row(self.plan(code=snap(threads=[thread()])), "fix_commit", "store")
        self.assertEqual((fix["state"], fix["committable"], fix["action"]), ("todo", True, "validate_and_commit"))
        sha = self.commit(self.store, {SPEC_MAIN: f"{NEW_TEXT} by name.\n"},
                          "fix(add-greeting): address review feedback\n\nFeedback-Round: 2")
        fix = self.row(self.plan(code=snap(threads=[thread()])), "fix_commit", "store")
        self.assertEqual((fix["state"], fix["sha"]), ("done", sha))

    def test_pass_plan_recorded_head_dropped_from_the_branch_stops(self):
        self.write_record([self.finding("F1", dest="code", source="code", edits=[{"file": "greet.py", "contains": ["strip()"]}])])
        self.git(self.code, "reset", "-q", "--hard", "HEAD~1")  # the recorded head is gone from the branch
        self.fix_code()
        p = self.plan(code=snap(threads=[thread()]))
        self.assertIn("head_unreachable", [s["reason"] for s in p["stops"]])
        self.assertNotEqual(self.row(p, "fix_commit", "code")["state"], "done")

    def test_identical_legacy_copy_is_removed(self):
        self.settings("github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n")
        self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}], react=None)])
        legacy = self.state_dir / "feedback" / legacy_key(CODE, CHANGE)
        shutil.copyfile(self.record_path(), legacy)  # the leftover of an interrupted move
        self.fix_code()
        self.push_all()
        p = self.plan(code=snap(threads=[]))
        self.assertNotIn("legacy_record_ignored", p)
        self.assertFalse(legacy.exists(), "a legacy file identical to the record is a leftover and is removed")
        self.assertTrue(self.plan(code=snap(threads=[]), sub="done")["deleted"])
        later = self.plan(code=snap(threads=[]))
        self.assertFalse(later["record"])
        self.assertNotIn("legacy_record_ignored", later)

    def test_pass_plan_unrecorded_change_stops(self):
        self.write_record([self.finding()])
        self.write(f"store/{SPEC_ARCHIVED}", f"{NEW_TEXT} by name.\n")
        self.write("store/openspec/specs/other/spec.md", "unrelated edit\n")
        p = self.plan(code=snap(threads=[thread()]))
        self.assertEqual(p["status"], "stop")
        stop = [s for s in p["stops"] if s["reason"] == "unrecorded_change"][0]
        self.assertEqual(stop["repo"], "store")
        self.assertIn("openspec/specs/other/spec.md", stop["files"])
        self.assertFalse(self.row(p, "fix_commit", "store")["committable"])

    def test_pass_plan_unjudgeable_edit_stops(self):
        self.write_record([self.finding(edits=[{"file": SPEC_ARCHIVED}])])
        p = self.plan(code=snap(threads=[thread()]))
        self.assertEqual([s["reason"] for s in p["stops"]], ["edit_unjudgeable"])
        self.assertFalse(self.row(p, "fix_commit", "store")["committable"])

    def test_pass_plan_rerequest_not_applicable(self):
        self.settings("github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n")  # no review_request.body, no reviewers
        self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}], react=None)])
        self.fix_code()
        self.push_all()
        p = self.plan(code=snap(threads=[]))  # the thread is gone from the snapshot: replied and resolved
        self.assertEqual(self.row(p, "rerequest", "code")["state"], "not_applicable")
        self.assertEqual(self.row(p, "reply", finding="F1")["state"], "done")
        self.assertEqual(self.row(p, "resolve", finding="F1")["state"], "done")
        self.assertTrue(p["delete_record"])
        self.assertEqual(p["status"], "complete")
        self.assertFalse([r for r in p["rows"] if r["state"] in ("todo", "ask", "rerun", "stopped")])
        self.assertEqual([c for c in self.gh_calls() if "comment" in c["argv"] or "POST" in c["argv"]], [])
        d = self.plan(code=snap(threads=[]), sub="done")
        self.assertTrue(d["deleted"])
        self.assertFalse(self.record_path().exists())

    def finished_pass(self, push_store=True):
        """Pass 2 with a fix in each repo, both PRs re-requested after their pushes; the replies and resolutions are on
        GitHub (the threads are gone from the snapshots). With push_store=False the store's fix commit stays local."""
        self.write_record([self.finding("F1", dest="store", react=None),
                           self.finding("F2", dest="code", item="T2", source="store", react=None)])
        self.fix_code()
        self.fix_store()
        self.push_all(*((self.code, self.store) if push_store else (self.code,)))
        self.pushed_at(CODE, BRANCH, self.tip(self.code), "2026-10-08T12:00:00Z")
        self.add_comment(CODE, 5, "@codex review", "KintsugiBot", 2002, created_at="2026-10-08T12:00:03Z")
        if push_store:
            self.pushed_at(STORE, BRANCH, self.tip(self.store), "2026-10-08T12:00:05Z")
            self.add_comment(STORE, 3, "@codex review", "KintsugiBot", 2001, created_at="2026-10-08T12:00:06Z")

    def test_pass_done_removes_a_finished_record(self):
        self.finished_pass()
        p = self.plan(code=snap(threads=[]), store=snap(threads=[]))
        self.assertFalse([r for r in p["rows"] if r["state"] in ("todo", "ask", "rerun", "stopped")])
        for repo in ("code", "store"):
            self.assertEqual(self.row(p, "push", repo)["state"], "done")
            self.assertEqual(self.row(p, "rerequest", repo)["state"], "done")
        for fid in ("F1", "F2"):
            self.assertEqual(self.row(p, "reply", finding=fid)["state"], "done")
            self.assertEqual(self.row(p, "resolve", finding=fid)["state"], "done")
        self.assertEqual((p["status"], p["delete_record"]), ("complete", True))
        self.assertTrue(self.record_path().exists())  # planning alone never removes it
        d = self.plan(code=snap(threads=[]), store=snap(threads=[]), sub="done")
        self.assertEqual((d["ok"], d["deleted"]), (True, True))
        self.assertFalse(self.record_path().exists())

    def test_pass_done_keeps_record_while_store_push_pending(self):
        self.finished_pass(push_store=False)
        # the replies are posted and the threads are gone, but the store's fix commit is not on its remote
        p = self.plan(code=snap(threads=[]), store=snap(threads=[]))
        self.assertEqual(self.row(p, "fix_commit", "store")["state"], "done")
        self.assertEqual(self.row(p, "push", "store")["state"], "todo")
        self.assertEqual(self.row(p, "reply", finding="F1")["state"], "done")
        self.assertEqual(self.row(p, "reply", finding="F2")["state"], "done")
        self.assertEqual((p["status"], p["delete_record"]), ("resume", False))
        d = self.plan(code=snap(threads=[]), store=snap(threads=[]), sub="done", expect=1)
        self.assertEqual(d["error"], "not_complete")
        self.assertTrue(self.record_path().exists())
        # the next plan still lists the store push as to do
        p = self.plan(code=snap(threads=[]), store=snap(threads=[]))
        self.assertEqual(self.row(p, "push", "store")["state"], "todo")
        self.assertTrue(self.record_path().exists())

    def test_pass_plan_first_code_fix_on_store_only_change_needs_code_pr(self):
        # a store-only change (no code PR) gets a code fix: the pass is not complete until the code PR exists
        intent = {**self.intent([]), "prs": {"store": {"repo": STORE, "number": 3}},
                  "findings": [self.finding("F1", source="store", dest="code", react=None)]}
        self.write_record(None, intent=intent)
        self.fix_code()
        self.push_all()
        p = self.plan(store=snap(threads=[]))
        push = self.row(p, "push", "code")
        self.assertEqual((push["state"], push["action"]), ("todo", "ship"))
        self.assertNotIn("code", p["share_by_hand"])
        self.assertEqual(p["status"], "resume")
        self.assertFalse(p["delete_record"])
        self.plan(store=snap(threads=[]), sub="done", expect=1)
        self.assertTrue(self.record_path().exists())
        # once ship opened the code PR, the pass re-requests review on it and then completes
        self.add_pull(STORE, 3, body=f"Code PR: https://github.com/{CODE}/pull/7")  # ship linked the pair (step 5)
        self.add_pull(CODE, 7, body=f"Store PR: https://github.com/{STORE}/pull/3")
        p = self.plan(store=snap(threads=[]))
        self.assertEqual(self.row(p, "push", "code")["state"], "done")
        rr = self.row(p, "rerequest", "code")
        self.assertEqual((rr["pr"], rr["state"]), ({"repo": CODE, "number": 7}, "todo"))
        self.pushed_at(CODE, BRANCH, self.tip(self.code), "2026-10-08T12:00:00Z")
        self.add_comment(CODE, 7, "@codex review", "KintsugiBot", 2003, created_at="2026-10-08T12:00:03Z")
        p = self.plan(store=snap(threads=[]))
        self.assertEqual(p["status"], "complete")
        self.assertTrue(self.plan(store=snap(threads=[]), sub="done")["deleted"])

    def test_pass_plan_question_thread_done_when_replied(self):
        self.settings("github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n")
        self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}],
                                        resolve=False, react=None)])
        self.fix_code()
        self.push_all()
        answered = thread(awaiting=True, rev="12@2026-10-08T12:01:00Z", comments=[
            {"id": "C11", "author": "chatgpt-codex-connector", "at": T0, "edited": None},
            {"id": "C12", "author": "KintsugiBot", "at": "2026-10-08T12:01:00Z", "edited": None}])
        p = self.plan(code=snap(threads=[answered]))
        self.assertEqual(self.row(p, "reply", finding="F1")["state"], "done")
        self.assertEqual(self.row(p, "resolve", finding="F1")["state"], "not_applicable")
        self.assertTrue(p["delete_record"])
        self.assertFalse(p["needs_user"])

    # ---- reaction evidence (#25) ----
    def replied_code_fix(self, finding):
        """A code fix committed, pushed and re-requested; the reply is posted (so only the reaction can be missing)."""
        self.write_record([finding])
        self.fix_code()
        self.push_all()
        self.pushed_at(CODE, BRANCH, self.tip(self.code), "2026-10-08T12:00:00Z")
        self.add_comment(CODE, 5, "@codex review", "KintsugiBot", 2002, created_at="2026-10-08T12:00:03Z")

    ANSWERED = thread(awaiting=True, rev="12@2026-10-08T12:01:00Z", comments=[
        {"id": "C11", "author": "chatgpt-codex-connector", "at": T0, "edited": None},
        {"id": "C12", "author": "KintsugiBot", "at": "2026-10-08T12:01:00Z", "edited": None}])

    def thread_finding(self):
        return self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}], resolve=False)

    def react_rest(self, login, content, cid=11):
        st = self.gh()
        fake_gh.add_review_comment_reaction(st, CODE, cid, login, content)
        self.save_gh(st)

    def react_node(self, node, login, content):
        st = self.gh()
        fake_gh.add_node_reaction(st, CODE, node, login, content)
        self.save_gh(st)

    def test_pass_plan_reaction_todo_until_github_shows_it(self):
        self.replied_code_fix(self.thread_finding())
        p = self.plan(code=snap(threads=[self.ANSWERED]))
        react = self.row(p, "react", finding="F1")
        self.assertEqual((react["state"], react["react"], react["comment"]), ("todo", "+1", 11))
        self.assertNotIn("rerun", {r["state"] for r in p["rows"]})
        self.assertEqual((p["status"], p["delete_record"]), ("resume", False))
        done = self.plan(code=snap(threads=[self.ANSWERED]), sub="done", expect=1)
        self.assertEqual(done["error"], "not_complete")
        self.assertTrue(self.record_path().exists())
        # a reaction by someone else, or the opposite one by the viewer, is not this pass's reaction
        self.react_rest("chatgpt-codex-connector", "+1")
        self.react_rest("KintsugiBot", "-1")
        p = self.plan(code=snap(threads=[self.ANSWERED]))
        self.assertEqual(self.row(p, "react", finding="F1")["state"], "todo")
        self.react_rest("KintsugiBot", "+1")
        p = self.plan(code=snap(threads=[self.ANSWERED]))
        self.assertEqual((self.row(p, "react", finding="F1")["state"], p["status"]), ("done", "complete"))
        self.assertTrue(self.plan(code=snap(threads=[self.ANSWERED]), sub="done")["deleted"])
        self.assertFalse(self.record_path().exists())

    def test_pass_plan_reaction_done_when_present(self):
        self.replied_code_fix(self.thread_finding())
        self.react_rest("KintsugiBot", "+1")
        p = self.plan(code=snap(threads=[self.ANSWERED]))
        react = self.row(p, "react", finding="F1")
        self.assertEqual((react["state"], react["react"], react["comment"]), ("done", "+1", 11))
        self.assertEqual((p["status"], p["delete_record"]), ("complete", True))
        # the thread is gone from the snapshot (answered and resolved): the reaction is still read from GitHub
        self.assertEqual(self.row(self.plan(code=snap(threads=[])), "react", finding="F1")["state"], "done")

    def test_pass_plan_reaction_on_a_node_id_target(self):
        self.replied_code_fix(self.finding("F1", dest="code", kind="comment", item="IC_node1", resolve=False,
                                           edits=[{"file": "greet.py", "contains": ["strip()"]}]))
        self.react_node("IC_node1", "someone", "THUMBS_DOWN")  # the node exists on GitHub; nobody here has reacted yet
        p = self.plan(code=snap(comments=[]))  # the comment left the snapshot: answered
        react =self.row(p, "react", finding="F1")
        self.assertEqual((react["state"], react["comment"]), ("todo", "IC_node1"))
        self.react_node("IC_node1", "KintsugiBot", "THUMBS_DOWN")  # the opposite reaction does not count
        self.react_node("IC_node1", "someone", "THUMBS_UP")  # nor does someone else's
        self.assertEqual(self.row(self.plan(code=snap(comments=[])), "react", finding="F1")["state"], "todo")
        self.react_node("IC_node1", "KintsugiBot", "THUMBS_UP")
        p = self.plan(code=snap(comments=[]))
        self.assertEqual((self.row(p, "react", finding="F1")["state"], p["status"]), ("done", "complete"))

    def test_pass_plan_reaction_read_failure_is_unknown(self):
        self.replied_code_fix(self.thread_finding())
        st = self.gh()
        st["fail"] = ["/reactions"]
        self.save_gh(st)
        p = self.plan(code=snap(threads=[self.ANSWERED]), expect=3)
        self.assertEqual((p["ok"], p["error"]), (False, "lookup_failed"))
        self.assertTrue(self.record_path().exists())

    def test_pass_plan_node_reaction_read_failure_is_unknown(self):
        self.replied_code_fix(self.finding("F1", dest="code", kind="comment", item="IC_node1", resolve=False,
                                           edits=[{"file": "greet.py", "contains": ["strip()"]}]))
        st = self.gh()
        st["fail"] = ["graphql"]
        self.save_gh(st)
        p = self.plan(code=snap(comments=[]), expect=3)
        self.assertEqual((p["ok"], p["error"]), (False, "lookup_failed"))

    # ---- the link row (#30) ----
    def adopted_code_pr(self, store_url=None):
        """A store-only pass whose code fix was pushed, and whose code PR was opened without links; replies are done."""
        intent = {**self.intent([]), "prs": {"store": {"repo": STORE, "number": 3}},
                  "findings": [self.finding("F1", source="store", dest="code", react=None)]}
        self.write_record(None, intent=intent)
        self.fix_code()
        self.push_all()
        store_pull = self.pull(STORE, 3)
        if store_url:
            store_pull["html_url"] = store_url
        self.seed_pulls(STORE, [store_pull])
        self.add_pull(CODE, 7)
        self.pushed_at(CODE, BRANCH, self.tip(self.code), "2026-10-08T12:00:00Z")
        self.add_comment(CODE, 7, "@codex review", "KintsugiBot", 2003, created_at="2026-10-08T12:00:03Z")

    def link_args(self, repo, n, kind, peer):
        return ["link", "--repo", repo, "--pr", n, "--kind", kind, "--peer-url", peer, "--login", "KintsugiBot"]

    def markers(self, slug, n):
        return [c for c in self.comments(slug, n) if "specwright:link" in c["body"]]

    def test_pass_plan_adopted_code_pr_needs_the_link(self):
        canonical = "https://github.com/Acme/Plans/pull/3"  # GitHub's own spelling, not the record's slug
        self.adopted_code_pr(store_url=canonical)
        p = self.plan(store=snap(threads=[]))
        # #30: with no link row the pass reports complete although the pair was never linked
        self.assertNotEqual(p["status"], "complete", "the plan reports complete for an unlinked pair (#30)")
        link = self.row(p, "link")
        self.assertEqual((link["state"], link["code"], link["store"]),
                         ("todo", {"repo": CODE, "number": 7, "url": f"https://github.com/{CODE}/pull/7"},
                          {"repo": STORE, "number": 3, "url": canonical}))
        self.assertEqual(p["status"], "resume")
        self.plan(store=snap(threads=[]), sub="done", expect=1)
        self.assertTrue(self.record_path().exists())
        # ship step 5, with the row's URLs
        self.pp(*self.link_args(CODE, 7, "store", link["store"]["url"]))
        p = self.plan(store=snap(threads=[]))
        self.assertEqual((self.row(p, "link")["state"], p["status"]), ("todo", "resume"), "one side linked is not linked")
        self.pp(*self.link_args(STORE, 3, "code", link["code"]["url"]))
        p = self.plan(store=snap(threads=[]))
        self.assertEqual((self.row(p, "link")["state"], p["status"]), ("done", "complete"))
        self.assertEqual((len(self.markers(CODE, 7)), len(self.markers(STORE, 3))), (1, 1))
        self.assertTrue(self.plan(store=snap(threads=[]), sub="done")["deleted"])
        # running both links again changes nothing
        self.pp(*self.link_args(CODE, 7, "store", link["store"]["url"]))
        self.assertEqual((len(self.markers(CODE, 7)), len(self.markers(STORE, 3))), (1, 1))

    def test_pass_plan_link_done_when_descriptions_name_the_peer(self):
        self.adopted_code_pr()
        st = self.gh()
        for slug, n, peer in ((CODE, 7, f"https://github.com/{STORE}/pull/3"), (STORE, 3, f"https://github.com/{CODE}/pull/7")):
            next(p for p in st["repos"][slug]["pulls"] if p["number"] == n)["body"] = f"Peer: {peer}"
        self.save_gh(st)
        p = self.plan(store=snap(threads=[]))
        self.assertEqual((self.row(p, "link")["state"], p["status"]), ("done", "complete"))
        self.assertEqual([c for c in self.gh_calls() if "POST" in c["argv"] or "PATCH" in c["argv"]], [])

    def test_pass_plan_removes_marker_before_code_fix(self):
        # the archive carries the planning-only marker; a code fix must delete it in a store commit first
        self.commit(self.store, {MARKER: "code_changes: none\n"}, "chore(add-greeting): archive change marker")
        self.push_all(self.store)
        w = self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}])])
        self.assertEqual(w["marker"], MARKER)
        p = self.plan(code=snap(threads=[thread()]))
        store_fix = self.row(p, "fix_commit", "store")
        self.assertEqual(store_fix["state"], "todo")
        self.assertEqual(store_fix["files"], [MARKER])
        self.assertEqual(store_fix["trailer"], "Feedback-Round: 2")
        code_push = self.row(p, "push", "code")
        self.assertIn("fix_commit:store", code_push["after"])
        self.assertIn("fix_commit:code", code_push["after"])
        self.assertTrue(code_push["blocked"])
        # delete the marker in a store commit: the code push is then unblocked once the code fix is committed too
        (self.store / MARKER).unlink()
        self.git(self.store, "add", "-A")
        self.git(self.store, "commit", "-q", "-m", "fix(add-greeting): remove planning-only marker\n\nFeedback-Round: 2")
        self.fix_code()
        p = self.plan(code=snap(threads=[thread()]))
        self.assertEqual(self.row(p, "fix_commit", "store")["state"], "done")
        code_push = self.row(p, "push", "code")
        self.assertEqual((code_push["state"], code_push["blocked"]), ("todo", False))
        self.assertEqual(self.row(p, "push", "store")["state"], "todo")

    def test_pass_write_finds_the_marker_under_the_selected_root_only(self):
        # another OpenSpec root in the store archives a change of the same name; its marker sorts first and is not ours
        decoy = "aaa/openspec/changes/archive/2026-10-01-add-greeting/specwright-change.yaml"
        self.commit(self.store, {decoy: "code_changes: none\n", MARKER: "code_changes: none\n"}, "chore(add-greeting): archive change marker")
        w = self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}])])
        self.assertEqual(w["marker"], MARKER)

    def test_pass_write_ignores_another_roots_marker(self):
        decoy = "other/changes/archive/2026-10-01-add-greeting/specwright-change.yaml"
        self.commit(self.store, {decoy: "code_changes: none\n"}, "chore: other root archive")
        w = self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}])])
        self.assertIsNone(w["marker"], "a marker outside <store-prefix>/changes/archive/ belongs to another root")

    def reuse_change_name(self):
        """An earlier planning-only archive of the same change name, already merged into the store's main."""
        old = "openspec/changes/archive/2026-09-01-add-greeting/specwright-change.yaml"
        self.git(self.store, "checkout", "-q", "main")
        self.commit(self.store, {old: "code_changes: none\n"}, "merge: add-greeting (earlier)")
        self.git(self.store, "checkout", "-q", BRANCH)
        self.git(self.store, "merge", "-q", "--no-edit", "main")
        return old

    def test_pass_write_takes_this_archives_marker_not_an_earlier_one(self):
        self.reuse_change_name()
        self.commit(self.store, {MARKER: "code_changes: none\n"}, "chore(add-greeting): archive change marker")
        w = self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}])])
        self.assertEqual(w["marker"], MARKER)

    def test_pass_write_ignores_an_earlier_archives_marker(self):
        self.reuse_change_name()  # this archive (ARCHIVE) has code work, so no marker of its own
        w = self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}])])
        self.assertIsNone(w["marker"], "the earlier archive's marker is history on main, not this change's")

    def test_pass_write_stops_when_two_archives_are_new(self):
        other = "openspec/changes/archive/2026-09-01-add-greeting/specwright-change.yaml"
        self.commit(self.store, {other: "code_changes: none\n", MARKER: "code_changes: none\n"}, "chore: two archives")
        r = self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}])], expect=1)
        self.assertEqual(r["error"], "marker_ambiguous")
        self.assertFalse(self.record_path().exists())

    def test_pass_plan_no_marker_when_only_store_fixes(self):
        self.commit(self.store, {MARKER: "code_changes: none\n"}, "chore(add-greeting): archive change marker")
        w = self.write_record([self.finding()])
        self.assertIsNone(w["marker"])

    def test_pass_plan_without_record(self):
        p = self.plan()
        self.assertEqual((p["ok"], p["record"], p["new_pass_allowed"]), (True, False, True))

    def test_pass_plan_needs_the_snapshot_of_each_source_pr(self):
        self.write_record([self.finding()])
        args = ["pass", "plan", *self.common(), "--snapshot", f"store={self.write_json('s.json', snap())}"]
        r = self.pp(*args, expect=2)
        self.assertEqual(r["error"], "snapshot_required")

    def test_pass_plan_finding_spanning_both_repos(self):
        # one finding needs a spec edit in the store and a code edit: each edit goes to its own repo, one reply covers both
        both = self.finding("F1", dest="both", edits=[
            {"repo": "store", "file": SPEC_ARCHIVED, "contains": [NEW_TEXT], "absent": [OLD_TEXT]},
            {"repo": "store", "file": SPEC_MAIN, "contains": [NEW_TEXT], "absent": [OLD_TEXT]},
            {"repo": "code", "file": "greet.py", "contains": ["strip()"]}])
        self.write_record([both])
        p = self.plan(code=snap(threads=[thread()]))
        sfix, cfix = self.row(p, "fix_commit", "store"), self.row(p, "fix_commit", "code")
        self.assertEqual(sorted(sfix["files"]), sorted([SPEC_ARCHIVED, SPEC_MAIN]))
        self.assertEqual(cfix["files"], ["greet.py"])
        reply = self.row(p, "reply", finding="F1")
        self.assertTrue({"fix_commit:store", "fix_commit:code", "push:store", "push:code"} <= set(reply["after"]))
        s_sha, c_sha = self.fix_store(), self.fix_code()
        p = self.plan(code=snap(threads=[thread()]))
        self.assertEqual((self.row(p, "fix_commit", "store")["state"], self.row(p, "fix_commit", "code")["state"]), ("done", "done"))
        self.push_all()
        p = self.plan(code=snap(threads=[thread()]))
        reply = self.row(p, "reply", finding="F1")
        self.assertEqual(reply["after"], [])
        self.assertEqual(sorted((l["repo"], l["sha"]) for l in reply["link_commits"]), sorted([(CODE, c_sha), (STORE, s_sha)]))

    def test_pass_plan_reads_a_private_store_as_the_store_login(self):
        self.settings("github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n"
                      "  reviewers:\n    chatgpt-codex-connector: { role: required, request: \"@codex review\" }\n"
                      "planning_store:\n  login: sh1ny\n")
        st = self.gh()
        st.setdefault("repos", {}).setdefault(STORE, {})["readers"] = ["sh1ny"]
        self.save_gh(st)
        self.write_record([self.finding()])
        self.fix_store()
        self.push_all()
        p = self.pp("pass", "plan", *self.common(), "--snapshot", f"code={self.write_json('code-snap.json', snap(threads=[thread()]))}",
                    "--snapshot", f"store={self.write_json('store-snap.json', snap())}", env={"GH_TOKEN": "tok-k"})
        rr = self.row(p, "rerequest", "store")
        self.assertEqual(rr["state"], "todo")
        self.assertIn("push_time", rr)

    def test_pass_write_refuses_findings_pass_plan_cannot_read(self):
        # a record `pass plan` cannot read would block every later pass, so it is never written
        good = self.finding()
        for bad in ({k: v for k, v in good.items() if k != "item"}, {**good, "item": ""}, {**good, "kind": "issue"},
                    {**good, "disposition": "fixed"}, {**good, "revision": None}, {**good, "edits": [{"contains": ["x"]}]}):
            self.assertEqual(self.write_record([bad], expect=2)["error"], "invalid_intent", bad)
        self.assertFalse(self.record_path().exists())

    def refuses(self, intent, key):
        r = self.write_record(None, intent=intent, expect=2)
        self.assertEqual(r["error"], "invalid_intent", intent)
        self.assertIn(key, r["message"])
        self.assertFalse(self.record_path().exists())

    def test_pass_write_accepts_a_well_formed_intent(self):
        r = self.write_record([self.finding()], intent={**self.intent([self.finding()]), "prs": {"code": {"repo": CODE, "number": 5}}})
        self.assertTrue(r["ok"])
        self.assertTrue(self.record_path().exists())
        self.assertTrue(self.plan()["ok"])

    def test_pass_write_refuses_malformed_prs(self):
        base = self.intent([self.finding()])
        for prs in ("acme/app#5", {"code": "acme/app#5"}, {"code": {"repo": "acme", "number": 5}},
                    {"code": {"repo": CODE, "number": "5"}}, {"code": {"repo": CODE, "number": 0}},
                    {"code": {"repo": CODE, "number": True}}, {"other": None}):
            self.refuses({**base, "prs": prs}, "prs")

    def test_pass_write_refuses_a_bad_round(self):
        base = self.intent([self.finding()])
        for rnd in (0, "2", True, -1, 1.5):
            self.refuses({**base, "round": rnd}, "round")

    def test_pass_write_refuses_a_bad_root_id(self):
        good = self.finding()
        for bad in ({k: v for k, v in good.items() if k != "root_id"}, {**good, "root_id": "abc"}, {**good, "root_id": 0},
                    {**good, "root_id": True}):
            self.refuses(self.intent([bad]), "root_id")

    def test_pass_write_both_needs_a_repo_per_edit(self):
        bad = self.finding("F1", dest="both", edits=[{"file": "greet.py", "contains": ["x"]}])
        self.assertEqual(self.write_record([bad], expect=2)["error"], "invalid_intent")
        stray = self.finding("F1", dest="both", edits=[{"repo": "store", "file": "greet.py", "contains": ["x"]},
                                                       {"repo": "code", "file": "greet.py", "contains": ["y"]}])
        self.assertEqual(self.write_record([stray], expect=1)["error"], "misrouted")
        self.assertFalse(self.record_path().exists())

    def test_pass_write_refuses_an_existing_record_and_misrouted_edits(self):
        self.write_record([self.finding()])
        self.assertEqual(self.write_record([self.finding()], expect=1)["error"], "record_exists")
        self.record_path().unlink()
        bad = self.finding(edits=[{"file": "greet.py", "contains": ["x"]}])  # destination store, not under openspec/
        self.assertEqual(self.write_record([bad], expect=1)["error"], "misrouted")
        self.assertFalse(self.record_path().exists())


# ---- task 3.1: the re-request cutoff (design D2) ----
class RerequestCutoff(PassBase):
    """A fix on the store branch, pushed; `pass plan` judges the store re-request against the cutoff it can establish."""

    def setUp(self):
        super().setUp()
        self.write_record([self.finding()])
        self.fix_store()
        self.push_all()
        self.head = self.tip(self.store)

    def first_seen(self, iso, oid=None):
        """A pr-snapshot.sh first-sighting record: <state>/heads/<owner/name/pr, lowercased>/<oid>, one HTTP-date line."""
        t = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
        p = self.state_dir / "heads" / STORE.lower() / "3" / (oid or self.head)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(t.strftime("%a, %d %b %Y %H:%M:%S GMT") + "\n", encoding="utf-8", newline="\n")

    def request(self, at, cid=2001):
        self.save_gh({**self.gh(), "repos": self.gh().get("repos", {})})
        self.add_comment(STORE, 3, "@codex review", "KintsugiBot", cid, created_at=at)

    def rr(self):
        return self.row(self.plan(code=snap(threads=[thread()])), "rerequest", "store")

    def check(self, row, state, cutoff, source):
        self.assertEqual((row["state"], row["cutoff"], row["cutoff_source"]), (state, cutoff, source))

    def test_rerequest_cutoff_push_time(self):
        self.pushed_at(STORE, BRANCH, self.head, "2026-10-08T12:00:00Z")
        self.first_seen("2026-10-08T11:00:00Z")  # a record exists, but the push wins
        self.request("2026-10-08T12:05:00Z")
        row = self.rr()
        self.check(row, "done", "2026-10-08T12:00:00Z", "push")
        self.assertEqual(row["push_time"], "2026-10-08T12:00:00Z")

    def test_rerequest_cutoff_first_seen_done_once(self):
        self.first_seen("2026-10-08T12:00:00Z")
        self.request("2026-10-08T12:05:00Z")
        for _ in range(2):  # repeated plans keep the row done: no further request is scheduled
            row = self.rr()
            self.check(row, "done", "2026-10-08T12:00:00Z", "first_seen")
            self.assertIsNone(row["push_time"])

    def test_rerequest_cutoff_pass_written(self):
        written = json.loads(self.record_path().read_text(encoding="utf-8"))["written_at"]
        self.assertRegex(written, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.request(written)  # at the cutoff counts
        self.check(self.rr(), "done", written, "pass_written")

    def test_rerequest_earlier_head_request_is_todo(self):
        self.first_seen("2026-10-08T12:00:00Z")
        self.request("2026-10-08T10:00:00Z")  # for the previous head
        self.check(self.rr(), "todo", "2026-10-08T12:00:00Z", "first_seen")

    def test_rerequest_before_first_sighting_bounded_to_one_more(self):
        self.request("2026-10-08T12:05:00Z")
        self.first_seen("2026-10-08T12:10:00Z")  # the snapshot saw the head after that request
        self.check(self.rr(), "todo", "2026-10-08T12:10:00Z", "first_seen")
        self.request("2026-10-08T12:11:00Z", cid=2002)
        for _ in range(2):
            self.check(self.rr(), "done", "2026-10-08T12:10:00Z", "first_seen")

    def test_rerequest_second_head_in_pass_is_todo(self):
        self.request("2026-10-08T12:05:00Z")  # for the first head
        self.first_seen("2026-10-08T12:20:00Z")  # the second head, first seen later
        self.check(self.rr(), "todo", "2026-10-08T12:20:00Z", "first_seen")

    def test_rerequest_old_record_falls_back_to_owner_at(self):
        rec = json.loads(self.record_path().read_text(encoding="utf-8"))
        rec.pop("written_at", None)  # a 0.1.12 record
        rec["owner"]["at"] = "2026-10-08T11:50:00Z"
        self.record_path().write_text(json.dumps(rec), encoding="utf-8")
        self.request("2026-10-08T12:05:00Z")
        self.check(self.rr(), "done", "2026-10-08T11:50:00Z", "pass_written")

    def test_rerequest_old_record_keeps_its_cutoff_after_adopt(self):
        """Adopting a 0.1.12 record replaces the owner (and its `at`): the pass start moves into written_at first, so a
        request posted between the pass start and the adoption still counts."""
        rec = json.loads(self.record_path().read_text(encoding="utf-8"))
        rec.pop("written_at", None)
        rec["owner"]["at"] = "2026-10-08T11:50:00Z"
        self.record_path().write_text(json.dumps(rec), encoding="utf-8")
        self.request("2026-10-08T12:05:00Z")
        out = self.pp("pass", "adopt", *self.common(), "--owner", "b" * 32, "--from", rec["owner"]["id"])
        self.assertTrue(out["ok"], out)
        self.owner = "b" * 32
        self.assertEqual(json.loads(self.record_path().read_text(encoding="utf-8"))["written_at"], "2026-10-08T11:50:00Z")
        self.check(self.rr(), "done", "2026-10-08T11:50:00Z", "pass_written")


class PassOwnership(PassBase):
    """One owner per feedback pass, and a record key that never aliases two repositories."""

    def fresh_pass(self):
        """A pass whose every step is done, so `pass done` may remove it."""
        self.settings("github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n")
        self.write_record([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}], react=None)])
        self.fix_code()
        self.push_all()
        return snap(threads=[])

    def raw(self):
        return self.record_path().read_bytes()

    def adopt(self, new, frm, expect=0):
        return self.pp("pass", "adopt", *self.common(), "--owner", new, "--from", frm, expect=expect)

    def cmd_for(self, sub, repo, *extra, expect=0):
        args = ["pass", sub, "--code", self.code, "--store", self.store, "--code-repo", repo, "--change", "fix-login", *extra]
        return self.pp(*args, expect=expect)

    def test_record_keys_do_not_alias_hyphenated_identities(self):
        s = self.write_json("s.json", snap())
        for repo, rnd in (("acme-tools/widget", 2), ("acme/tools-widget", 3)):
            f = self.write_json("intent.json", self.intent([self.finding()], rnd))
            self.cmd_for("write", repo, "--intent", f)
        names = sorted(p.name for p in (self.state_dir / "feedback").iterdir())
        self.assertEqual(names, sorted([record_key("acme-tools/widget", "fix-login"), record_key("acme/tools-widget", "fix-login")]))
        for repo, rnd in (("acme-tools/widget", 2), ("acme/tools-widget", 3)):
            p = self.cmd_for("plan", repo, "--snapshot", f"code={s}", "--snapshot", f"store={s}")
            self.assertEqual((p["record"], p["round"]), (True, rnd), repo)

    def test_legacy_record_is_moved_to_the_new_key(self):
        self.write_record([self.finding()])
        self.owner = None
        rec = json.loads(self.raw().decode("utf-8"))
        rec.pop("owner")
        rec["version"] = 1
        legacy = self.state_dir / "feedback" / legacy_key(CODE, CHANGE)
        legacy.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        before = legacy.read_bytes()
        self.record_path().unlink()
        p = self.plan()
        self.assertTrue(p["record"])
        self.assertIsNone(p["owned"])
        self.assertFalse(legacy.exists())
        self.assertEqual(self.raw(), before)

    def test_record_key_is_bounded_for_the_longest_names(self):
        # GitHub allows a 39-character owner and a 100-character repository; the record and its `.lock` must stay under 255 characters
        self.settings("github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n")
        repo = "o" * 39 + "/" + "r" * 100
        base = ["--code", self.code, "--store", self.store, "--code-repo", repo]
        s = self.write_json("s.json", snap(threads=[]))
        snaps = ["--snapshot", f"code={s}", "--snapshot", f"store={s}"]
        for change in ("c" * 80, "d" * 120):  # the second: its 0.1.9 file name is itself too long for the file system
            intent = self.intent([self.finding("F1", dest="code", edits=[{"file": "greet.py", "contains": ["strip()"]}], react=None)])
            intent.update(change=change, code_repo=repo)
            w = self.pp("pass", "write", *base, "--change", change, "--intent", self.write_json("intent.json", intent))
            path = self.state_dir / "feedback" / record_key(repo, change)
            self.assertTrue(path.exists(), "the record is created")
            self.assertLessEqual(len(path.name) + len(".lock"), 255)
            self.assertEqual([p.name for p in path.parent.iterdir()], [path.name])
            p = self.pp("pass", "plan", *base, "--change", change, "--owner", w["owner"], *snaps)
            self.assertTrue(p["record"])
            self.pp("pass", "adopt", *base, "--change", change, "--owner", "new-owner", "--from", w["owner"])  # takes the `.lock`
            self.assertFalse(Path(str(path) + ".lock").exists())
            if change[0] == "d":  # the fix is already pushed; adopt and done are covered by the first change
                continue
            self.fix_code()
            self.push_all()
            d = self.pp("pass", "done", *base, "--change", change, "--owner", "new-owner", *snaps)
            self.assertTrue(d["deleted"])
            self.assertFalse(path.exists())

        # where the OS answers ENAMETOOLONG (POSIX) instead of "no such file" (Windows), the old path counts as absent
        import errno
        from unittest import mock
        ns = PublishFallback.namespace()
        real_exists = Path.exists

        def exists(p):
            if p.name == legacy_key(repo, "d" * 120):
                raise OSError(errno.ENAMETOOLONG, "File name too long", str(p))
            return real_exists(p)

        with mock.patch.dict(os.environ, {"SPECWRIGHT_STATE_DIR": str(self.state_dir)}), mock.patch.object(Path, "exists", exists):
            path, ignored = ns["locate_record"](repo, "d" * 120)
        self.assertEqual((Path(path).name, ignored), (record_key(repo, "d" * 120), None))

    def test_legacy_move_finished_by_another_caller(self):
        # another call sees our published copy identical to the old file and removes the old file before our unlink
        from unittest import mock
        ns = PublishFallback.namespace()
        rec = {"version": 1, "code_repo": CODE, "change": CHANGE, "round": 2, "findings": []}
        legacy = self.state_dir / "feedback" / legacy_key(CODE, CHANGE)
        legacy.parent.mkdir(parents=True)
        legacy.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        real_publish = ns["publish"]

        def publish_then_other_caller_removes_old(src, dst):
            real_publish(src, dst)
            os.unlink(src)

        with mock.patch.dict(os.environ, {"SPECWRIGHT_STATE_DIR": str(self.state_dir)}):
            ns["publish"] = publish_then_other_caller_removes_old
            path, ignored = ns["locate_record"](CODE, CHANGE)
        self.assertEqual((Path(path).name, ignored), (record_key(CODE, CHANGE), None))
        self.assertTrue(Path(path).exists())
        self.assertFalse(legacy.exists())

    def test_legacy_record_of_another_identity_is_left_alone(self):
        self.write_record([self.finding()])
        self.owner = None
        rec = json.loads(self.raw().decode("utf-8"))
        rec.update(code_repo="acme-code/add", change="greeting")  # 0.1.9 gave both identities `acme-code-add-greeting.json`
        self.record_path().unlink()
        legacy = self.state_dir / "feedback" / legacy_key("acme-code/add", "greeting")
        self.assertEqual(legacy.name, legacy_key(CODE, CHANGE))
        legacy.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        before = legacy.read_bytes()
        p = self.plan()
        self.assertFalse(p["record"])
        self.assertEqual(legacy.read_bytes(), before)
        self.assertFalse(self.record_path().exists())

    def legacy_file(self, content):
        legacy = self.state_dir / "feedback" / legacy_key(CODE, CHANGE)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_bytes(content)
        return legacy

    def test_unreadable_legacy_record_stops(self):
        cut = b'{"code_repo": "acme/code", "chan'  # a 0.1.9 file cut off mid-write
        legacy = self.legacy_file(cut)
        self.assertFalse(self.record_path().exists())
        intent = self.write_json("intent.json", self.intent([self.finding()]))
        for out in (self.plan(expect=1), self.pp("pass", "write", *self.common(), "--intent", intent, expect=1)):
            self.assertEqual((out["ok"], out["error"]), (False, "record_unreadable"))
            self.assertIn(legacy.name, out["message"])
        self.assertFalse(self.record_path().exists(), "no new-key record may be started beside an unreadable legacy file")
        self.assertEqual(legacy.read_bytes(), cut)

    def test_unreadable_legacy_beside_valid_record_is_ignored(self):
        self.write_record([self.finding()])
        legacy = self.legacy_file(b"not json")
        p = self.plan()
        self.assertTrue(p["record"])
        self.assertEqual(p["legacy_record_ignored"].replace(chr(92), "/").rsplit("/", 1)[-1], legacy.name)
        self.assertEqual(legacy.read_bytes(), b"not json")
        d = self.plan(sub="done", expect=1)  # the pass is not complete, but the legacy file does not stop it
        self.assertEqual(d["error"], "not_complete")

    def test_denied_legacy_record_is_unreadable(self):
        # the old file cannot be read at all (a permission error): its identity is unknown, like a cut-off file
        import errno
        from unittest import mock
        ns = PublishFallback.namespace()
        legacy = self.legacy_file(b"{}")
        real_text, real_bytes = Path.read_text, Path.read_bytes

        def denied(real):
            def read(p, *a, **k):
                if p.name == legacy.name:
                    raise PermissionError(errno.EACCES, "Permission denied", str(p))
                return real(p, *a, **k)
            return read

        env = {"SPECWRIGHT_STATE_DIR": str(self.state_dir)}
        reads = (mock.patch.dict(os.environ, env), mock.patch.object(Path, "read_text", denied(real_text)),
                 mock.patch.object(Path, "read_bytes", denied(real_bytes)))
        with reads[0], reads[1], reads[2]:
            with self.assertRaises(ns["Stop"]) as cm:
                ns["locate_record"](CODE, CHANGE)
        self.assertEqual(cm.exception.error, "record_unreadable")
        self.assertIn(legacy.name, cm.exception.message)
        self.assertFalse(self.record_path().exists())
        self.write_record([self.finding()])
        with reads[0], reads[1], reads[2]:
            path, ignored = ns["locate_record"](CODE, CHANGE)  # beside a valid record it is ignored, not fatal
        self.assertEqual((Path(path).name, Path(ignored).name), (record_key(CODE, CHANGE), legacy.name))

    def test_pass_write_is_exclusive_under_concurrency(self):
        f = self.write_json("intent.json", self.intent([self.finding()]))
        cmd = [bashexe.bash(), str(SCRIPT), "pass", "write", *map(str, self.common()), "--intent", str(f)]
        res = []
        gate = threading.Barrier(2)

        def go():
            gate.wait()
            r = subprocess.run(cmd, capture_output=True, text=True, env=self.env(), cwd=self.tmp)
            res.append((r.returncode, json.loads(r.stdout.strip().splitlines()[0])))

        ts = [threading.Thread(target=go) for _ in range(2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(sorted(rc for rc, _ in res), [0, 1], res)
        win = next(o for rc, o in res if rc == 0)
        lose = next(o for rc, o in res if rc == 1)
        self.assertEqual(lose["error"], "record_exists")
        self.assertEqual(json.loads(self.raw().decode("utf-8"))["owner"]["id"], win["owner"])
        self.assertEqual([p.name for p in (self.state_dir / "feedback").iterdir()], [record_key(CODE, CHANGE)])

    def test_pass_owner_plans_and_completes(self):
        w = self.write_record([self.finding()])
        self.assertRegex(w["owner"], r"^[0-9a-f]{32}$")
        rec = json.loads(self.raw().decode("utf-8"))
        self.assertEqual(rec["version"], 2)
        self.assertEqual(rec["owner"]["id"], w["owner"])
        self.assertEqual(set(rec["owner"]), {"id", "at", "checkout", "host"})
        p = self.plan()
        self.assertIs(p["owned"], True)
        self.assertEqual(p["owner"]["id"], w["owner"])
        self.record_path().unlink()
        s = self.fresh_pass()
        self.assertIs(self.plan(code=s)["owned"], True)
        self.assertTrue(self.plan(code=s, sub="done")["deleted"])
        self.assertFalse(self.record_path().exists())

    def test_pass_plan_reports_foreign_owner(self):
        w = self.write_record([self.finding()])
        self.assertIs(self.plan()["owned"], True)
        self.owner = "f" * 32
        p = self.plan()
        self.assertIs(p["owned"], False)
        self.assertEqual(p["owner"]["id"], w["owner"])
        self.assertTrue(p["owner"]["at"] and p["owner"]["checkout"] and p["owner"]["host"])
        self.assertTrue(p["record"])  # reported, never refused

    def test_pass_adopt_hands_over_the_record(self):
        w = self.write_record([self.finding()])
        before = json.loads(self.raw().decode("utf-8"))
        self.assertTrue(self.adopt("b" * 32, w["owner"])["ok"])
        after = json.loads(self.raw().decode("utf-8"))
        self.assertEqual(after["owner"]["id"], "b" * 32)
        before.pop("owner")
        after.pop("owner")
        self.assertEqual(after, before)
        self.owner = "b" * 32
        self.assertIs(self.plan()["owned"], True)
        self.assertEqual([p.name for p in (self.state_dir / "feedback").iterdir()], [record_key(CODE, CHANGE)])

    def test_pass_adopt_refuses_a_stale_from(self):
        self.write_record([self.finding()])
        before = self.raw()
        self.assertEqual(self.adopt("b" * 32, "0" * 32, expect=1)["error"], "not_owner")
        self.assertEqual(self.raw(), before)

    def test_pass_adopt_and_done_refuse_a_held_lock(self):
        w = self.write_record([self.finding()])
        before = self.raw()
        lock = Path(str(self.record_path()) + ".lock")
        lock.mkdir()
        r = self.adopt("b" * 32, w["owner"], expect=1)
        self.assertEqual(r["error"], "record_busy")
        self.assertIn(lock.name, r["message"])
        d = self.plan(sub="done", expect=1)
        self.assertEqual(d["error"], "record_busy")
        self.assertIn(lock.name, d["message"])
        self.assertEqual(self.raw(), before)
        self.assertTrue(lock.is_dir())

    def test_pass_done_refuses_a_non_owner(self):
        s = self.fresh_pass()
        self.owner = "e" * 32
        self.assertEqual(self.plan(code=s, sub="done", expect=1)["error"], "not_owner")
        self.assertTrue(self.record_path().exists())


# =======================================================================================================
class StoreTransport(PassBase):
    """The store's git network reads authenticate as planning_store.login.

    A `git` shim first on PATH guards the store's GitHub URL: ls-remote/fetch ask `git credential fill` for
    github.com over HTTPS and fail unless the password is the store login's token, else they run against a local
    bare repository. The store's own config has no insteadOf, and an unreachable http.proxy, so a git that does not
    go through the shim (which is how pr-pair.sh reaches the store today) cannot read it."""

    SHIM = """#!/bin/sh
real="$SHIM_REAL_GIT"
case "$1" in ls-remote|fetch) ;; *) exec "$real" "$@" ;; esac
url=$("$real" remote get-url origin 2>/dev/null) || exec "$real" "$@"
case $url in *github.com/acme/plans*) ;; *) exec "$real" "$@" ;; esac
cred=$(printf 'protocol=https\\nhost=github.com\\n\\n' | "$real" credential fill 2>/dev/null) || cred=
pw=$(printf '%s\\n' "$cred" | sed -n 's/^password=//p' | tr -d '\\r')
echo "$1 ${pw:+with-credential}" >> "$SHIM_LOG"
if [ "$pw" != "$SHIM_STORE_TOKEN" ]; then
  echo "fatal: Authentication failed for '$url'" >&2
  exit 128
fi
exec "$real" -c "url.$SHIM_BARE.insteadOf=$url" "$@"
"""

    def private_store(self, login, fix="store"):
        """The store reads only as `login`'s token; `login` is planning_store.login, the code login is KintsugiBot."""
        self.settings("github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n"
                      "  reviewers:\n    chatgpt-codex-connector: { role: required, request: \"@codex review\" }\n"
                      f"planning_store:\n  login: {login}\n")
        self.write_record([self.finding()])
        self.sha = self.fix_store() if fix == "store" else self.fix_code()
        self.push_all()
        bare = self.tmp / "store.bare.git"
        self.git(self.store, "config", "--unset", f"url.{fixtures.posix(bare)}.insteadOf")
        self.git(self.store, "config", "http.proxy", "http://127.0.0.1:9")
        self.shim_log = self.tmp / "git-shim.log"
        self.write("bin/git", self.SHIM)
        os.chmod(self.tmp / "bin" / "git", 0o755)
        self.extra_env.update({"SHIM_REAL_GIT": fixtures.posix(shutil.which("git")), "SHIM_LOG": fixtures.posix(self.shim_log),
                               "SHIM_STORE_TOKEN": "tok-s", "SHIM_BARE": fixtures.posix(bare)})

    def rounds(self, expect=0):
        return self.pp("rounds", "--code", self.code, "--store", self.store, "--branch", BRANCH, expect=expect)

    def plan_store(self, expect=0):
        return self.pp("pass", "plan", *self.common(),
                       "--snapshot", f"code={self.write_json('code-snap.json', snap(threads=[thread()]))}",
                       "--snapshot", f"store={self.write_json('store-snap.json', snap())}", env={"GH_TOKEN": "tok-k"}, expect=expect)

    def shim_calls(self):
        return self.shim_log.read_text(encoding="utf-8").splitlines() if self.shim_log.exists() else []

    def test_rounds_and_pass_plan_read_a_private_store_remote_as_the_store_login(self):
        self.private_store("sh1ny")
        r = self.rounds()
        self.assertEqual((r["unpushed"], r["remote_unreadable"]), ({}, []))
        p = self.plan_store()
        self.assertEqual(self.row(p, "push", "store")["state"], "done")
        self.assertNotIn("remote_unreadable", json.dumps(p))
        self.assertTrue(self.shim_calls())
        self.assertTrue(all(c.endswith("with-credential") for c in self.shim_calls()), self.shim_calls())

    def test_store_git_reads_stop_without_a_store_credential(self):
        self.private_store("nobody")  # no gh credential for this login
        r = self.rounds(expect=3)
        self.assertEqual(r["error"], "no_credential")
        p = self.plan_store(expect=3)
        self.assertEqual(p["error"], "no_credential")
        self.assertEqual(self.shim_calls(), [])  # no store network call, with the code login or without a credential


    # Both remotes guarded; every network read is logged "<repo> <token>" in one file. The store is guarded as in
    # private_store, by a git shim that runs ahead of the store's (as.sh) reads. The code repo is read as the caller, with
    # plain `git` that a shim cannot intercept on Windows, so its origin is an ext:: remote (insteadOf in the repo's
    # config) whose command accepts only the code login's token from GH_TOKEN. The script runs with GH_TOKEN set to that
    # token, as the skill runs it under as.sh.
    SHIM_LOGGED = SHIM.replace('echo "$1 ${pw:+with-credential}" >> "$SHIM_LOG"', 'echo "store $pw" >> "$SHIM_LOG"')
    EXT = """#!/bin/sh
echo "code ${GH_TOKEN:-none}" >> "$SHIM_LOG"
if [ "$GH_TOKEN" != "$1" ]; then
  echo "fatal: Authentication failed for the code repository" >&2
  exit 128
fi
exec git "${3#git-}" "$2"
"""

    def two_private_remotes(self, push_code):
        """planning_store.login is sh1ny (tok-s), github.login KintsugiBot (tok-k). The store accepts only tok-s and the
        code repo only tok-k. Both repos hold a pass-2 fix; the code fix is pushed only when push_code."""
        self.private_store("sh1ny")  # record, store fix pushed, store guarded by the shim
        self.sha = self.fix_code()
        if push_code:
            self.push_all(self.code)
        self.write("bin/git", self.SHIM_LOGGED)
        os.chmod(self.tmp / "bin" / "git", 0o755)
        bare = self.tmp / "code.bare.git"
        self.git(self.code, "config", "--unset", f"url.{fixtures.posix(bare)}.insteadOf")
        self.git(self.code, "config", "protocol.ext.allow", "always")
        ext = fixtures.posix(self.write("ext-remote.sh", self.EXT))
        self.git(self.code, "config", f"url.ext::sh {ext} tok-k {fixtures.posix(bare)} %S.insteadOf", f"https://github.com/{CODE}.git")
        self.extra_env["GH_TOKEN"] = "tok-k"

    def reads(self):
        """repo -> the set of tokens its git network reads carried."""
        out = {}
        for line in self.shim_calls():
            repo, tok = line.split(" ", 1)
            out.setdefault(repo, set()).add(tok)
        return out

    def test_rounds_reads_each_remote_as_its_login(self):
        self.two_private_remotes(push_code=True)
        r = self.rounds()
        self.assertEqual((r["rounds"], r["unpushed"], r["remote_unreadable"]), (2, {}, []))
        self.assertEqual(self.reads(), {"store": {"tok-s"}, "code": {"tok-k"}})

    def test_code_remote_reads_keep_the_code_login(self):
        # the code remote accepts only the code login: its unpushed fix is reported as such, not as an unreadable remote
        self.two_private_remotes(push_code=False)
        r = self.rounds()
        self.assertEqual((r["unpushed"], r["remote_unreadable"]), ({"code": [self.sha]}, []))
        self.assertEqual(self.reads()["code"], {"tok-k"})  # never the store login's token
        self.assertEqual(self.reads()["store"], {"tok-s"})

    def test_code_only_rounds_need_no_store_credential(self):
        self.private_store("nobody", fix="code")  # the round's fix is in the code repo; the store has nothing to check
        r = self.rounds()
        self.assertEqual((r["rounds"], r["unpushed"], r["remote_unreadable"]), (2, {}, []))
        self.assertEqual(self.shim_calls(), [])


# =======================================================================================================
class PassRepoLocal(Base):
    """A repo-local change (no store): the same pass record, plan and rounds, with `--store` left out."""

    def setUp(self):
        super().setUp()
        self.code = self.make_repo("code", f"https://github.com/{CODE}.git")
        self.attach_bare(self.code, CODE)
        self.git(self.code, "checkout", "-q", "-b", BRANCH)
        self.commit(self.code, {"greet.py": "def greet(n):\n    return n\n", "openspec/specwright.yaml":
                                "github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n"}, "feat(add-greeting): task 1.1")
        self.git(self.code, "push", "-q", "origin", BRANCH)
        self.owner = None

    def common(self):
        return ["--code", self.code, "--code-repo", CODE, "--change", CHANGE]

    def finding(self, fid="F1", source="code", dest="code", item="T1"):
        return {"id": fid, "source": source, "destination": dest, "kind": "thread", "item": item, "root_id": 11,
                "edits": [{"file": "greet.py", "contains": ["strip()"]}],
                "disposition": {"reply": True, "resolve": True, "react": None},
                "revision": {"rev": REV0, "last_reviewer_comment": {"id": "C11", "at": T0}}}

    def intent(self, findings, prs=None, rnd=2):
        return {"change": CHANGE, "branch": BRANCH, "round": rnd, "code_repo": CODE,
                "prs": {"code": {"repo": CODE, "number": 5}, "store": None} if prs is None else prs, "findings": findings}

    def write_record(self, findings, prs=None, expect=0):
        f = self.write_json("intent.json", self.intent(findings, prs))
        out = self.pp("pass", "write", *self.common(), "--intent", f, expect=expect)
        if out.get("ok"):
            self.owner = out["owner"]
        return out

    def plan(self, code=None, sub="plan", expect=0):
        args = ["pass", sub, *self.common()]
        if self.owner:
            args += ["--owner", self.owner]
        args += ["--snapshot", f"code={self.write_json('code-snap.json', code if code is not None else snap())}"]
        return self.pp(*args, expect=expect)

    def fix_code(self, rnd=2):
        return self.commit(self.code, {"greet.py": "def greet(n):\n    return n.strip()\n"},
                           f"fix(add-greeting): address review feedback\n\nFeedback-Round: {rnd}")

    def record_path(self):
        return self.state_dir / "feedback" / record_key(CODE, CHANGE)

    def test_repo_local_final_pass_resumes_without_a_new_round(self):
        # max_fix_rounds is 2 and pass 2 committed and pushed its fix, then the session died before replying
        self.write_record([self.finding()])
        self.fix_code()
        self.git(self.code, "push", "-q", "origin", BRANCH)
        r = self.pp("rounds", "--code", self.code, "--branch", BRANCH)
        self.assertEqual((r["rounds"], r["limit_reached"], r["unpushed"], r["remote_unreadable"]), (2, True, {}, []))
        p = self.plan(code=snap(threads=[thread()]))
        self.assertEqual(self.row(p, "fix_commit", "code")["state"], "done")
        self.assertEqual(self.row(p, "push", "code")["state"], "done")
        self.assertEqual(self.row(p, "reply", finding="F1")["state"], "todo")
        self.assertEqual((p["status"], p["round"], p["new_pass_allowed"], p["delete_record"], p["stops"]), ("resume", 2, False, False, []))
        self.assertEqual({r["repo"] for r in p["rows"] if "repo" in r}, {"code"})  # code rows only

    def test_repo_local_pass_completes_and_is_removed(self):
        w = self.write_record([self.finding()])
        self.assertEqual(self.plan(code=snap(threads=[thread()]))["status"], "resume")
        self.fix_code()
        self.git(self.code, "push", "-q", "origin", BRANCH)
        p = self.plan(code=snap(threads=[]))  # the reply and the resolution are on GitHub: the thread is answered and gone
        self.assertEqual((p["status"], p["delete_record"], p["owned"]), ("complete", True, True))
        d = self.plan(code=snap(threads=[]), sub="done")
        self.assertEqual((d["ok"], d["deleted"]), (True, True))
        self.assertFalse(self.record_path().exists())
        self.assertEqual(self.plan()["status"], "none")
        self.assertTrue(w["owner"])

    def test_repo_local_pass_write_refuses_store_destination(self):
        for dest in ("store", "both"):
            f = self.finding(dest=dest)
            if dest == "both":
                f["edits"][0]["repo"] = "code"
            out = self.write_record([f], expect=1)
            self.assertEqual(out["error"], "misrouted", dest)
            self.assertFalse(self.record_path().exists())
        out = self.write_record([self.finding(source="store")], expect=1)
        self.assertEqual(out["error"], "misrouted")
        self.assertFalse(self.record_path().exists())

    def test_repo_local_pass_write_refuses_a_store_pr(self):
        out = self.write_record([self.finding()], prs={"code": {"repo": CODE, "number": 5}, "store": {"repo": STORE, "number": 3}}, expect=2)
        self.assertEqual(out["error"], "invalid_intent")
        self.assertIn("prs.store", out["message"])
        self.assertFalse(self.record_path().exists())

    @staticmethod
    def row(plan, step, repo=None, finding=None):
        rows = [r for r in plan["rows"] if r["step"] == step and (repo is None or r.get("repo") == repo)
                and (finding is None or r.get("finding") == finding)]
        assert len(rows) == 1, f"want one {step}/{repo}/{finding} row in {[(r['step'], r.get('repo'), r.get('finding')) for r in plan['rows']]}"
        return rows[0]


def embedded_python():
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index("<<'PYSRC'\n") + len("<<'PYSRC'\n")
    return text[start:text.index("\nPYSRC", start)]


def calls(src, name):
    """The full argument text of every `.name(...)` call, matching nested parentheses."""
    out = []
    for m in re.finditer(r"\." + name + r"\(", src):
        depth, i = 1, m.end()
        while depth and i < len(src):
            depth += {"(": 1, ")": -1}.get(src[i], 0)
            i += 1
        out.append(src[m.end():i - 1])
    return out


def find_py38():
    """A Python 3.8 interpreter: SPECWRIGHT_PY38, then `uv python find 3.8`, then `py -3.8`; None if none."""
    cands = [os.environ.get("SPECWRIGHT_PY38")]
    for cmd in (["uv", "python", "find", "3.8"], ["py", "-3.8", "-c", "import sys; print(sys.executable)"]):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            cands.append(r.stdout.strip() if r.returncode == 0 else None)
        except (OSError, subprocess.TimeoutExpired):
            pass
    for c in cands:
        if c and Path(c).exists():
            r = subprocess.run([c, "-c", "import sys; print(sys.version_info[:2] == (3, 8))"], capture_output=True, text=True)
            if r.stdout.strip() == "True":
                return c
    return None


class RecordLock(unittest.TestCase):
    """record_lock: a lock directory that cannot be removed never replaces the outcome of the work done under it."""

    def setUp(self):
        self.ns = PublishFallback.namespace()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fixtures.rmtree, self.tmp)
        self.path = self.tmp / "rec.json"

    def held(self, body, path):
        from unittest import mock
        with mock.patch.object(self.ns["os"], "rmdir", side_effect=PermissionError(13, "denied")):
            with self.ns["record_lock"](path):
                body()

    def test_failed_lock_removal_keeps_the_outcome(self):
        self.held(lambda: None, self.path)  # the work succeeded: no exception, the lock is reported as left behind
        self.assertEqual(self.ns["LEFT_LOCKS"], [self.ns["norm"](Path(str(self.path) + ".lock"))])
        with self.assertRaises(self.ns["Stop"]) as busy:  # the lock that was left stops the next call, as for any held lock
            self.held(lambda: None, self.path)
        self.assertEqual(busy.exception.obj()["error"], "record_busy")
        Stop = self.ns["Stop"]

        def fail():
            raise Stop("not_owner", "someone else")

        with self.assertRaises(Stop) as cm:  # the body's own stop is what the caller sees
            self.held(fail, self.tmp / "other.json")
        self.assertEqual(cm.exception.obj()["error"], "not_owner")


class PublishFallback(unittest.TestCase):
    """publish() without hard links creates the destination with O_EXCL and writes it; a failed write leaves no record behind."""

    @staticmethod
    def namespace():
        text = SCRIPT.read_text(encoding="utf-8")
        src = text.split("<<'PYSRC'\n", 1)[1].rsplit("\nPYSRC", 1)[0]
        src = src.split("\nargs = sys.argv[1:]", 1)[0]  # the definitions, not the dispatch
        ns = {"__name__": "pr_pair_under_test"}
        exec(compile(src, str(SCRIPT), "exec"), ns)
        return ns

    def test_failed_fallback_publish_leaves_no_record(self):
        import errno
        from unittest import mock
        publish = self.namespace()["publish"]
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fixtures.rmtree, tmp)
        src, dst = tmp / "src.json", tmp / "dst.json"
        src.write_bytes(b'{"a": 1}')
        real_fdopen = os.fdopen

        class Failing:
            def __init__(self, f):
                self.f = f

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.f.close()

            def write(self, data):
                raise OSError(errno.ENOSPC, "No space left on device")

        def failing_fdopen(fd, mode="r", *a, **k):
            return Failing(real_fdopen(fd, mode, *a, **k))

        with mock.patch.object(os, "link", side_effect=OSError(errno.EPERM, "links unsupported")), \
                mock.patch.object(os, "fdopen", side_effect=failing_fdopen):
            with self.assertRaises(OSError):
                publish(str(src), str(dst))
        self.assertFalse(dst.exists(), "the fallback left a partly written destination that would read as record_unreadable")
        publish(str(src), str(dst))  # and the next attempt can create it
        self.assertEqual(dst.read_bytes(), b'{"a": 1}')


class PassRuntime(PassBase):
    """pass write on the minimum Python the script accepts, and its JSON error contract for unexpected failures."""

    def test_embedded_python_passes_no_newline_kwarg(self):
        src = embedded_python()
        found = [f"{n}({a})" for n in ("write_text", "read_text") for a in calls(src, n) if re.search(r"\bnewline\s*=", a)]
        self.assertTrue(calls(src, "read_text"), "no read_text call found; the scan would be vacuous")
        self.assertEqual(found, [], "Path.write_text/read_text take newline= only on Python 3.10+")

    def test_unexpected_error_is_internal_error_json(self):
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "feedback").write_text("not a directory\n", encoding="utf-8")  # the record's parent is a file
        f = self.write_json("intent.json", self.intent([self.finding()]))
        r = subprocess.run([bashexe.bash(), str(SCRIPT), "pass", "write", *map(str, self.common()), "--intent", str(f)],
                           capture_output=True, text=True, env=self.env(), cwd=self.tmp)
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(len(lines), 1, f"want one JSON line, got {r.stdout!r} / {r.stderr!r}")
        out = json.loads(lines[0])
        self.assertEqual((r.returncode, out["ok"], out["error"]), (1, False, "internal_error"), out)
        self.assertTrue(out.get("message"), out)

    def test_pass_write_on_python38(self):
        py = find_py38()
        if not py:
            self.skipTest("no Python 3.8 interpreter (set SPECWRIGHT_PY38, or `uv python install 3.8`)")
        shims = self.tmp / "py38bin"
        shims.mkdir()
        for name in ("python3", "python"):
            (shims / name).write_text(f'#!/bin/sh\nexec "{fixtures.posix(py)}" "$@"\n', encoding="utf-8", newline="\n")
            os.chmod(shims / name, 0o755)
        e = self.env()
        e["PATH"] = str(shims) + os.pathsep + e["PATH"]
        v = subprocess.run([bashexe.bash(), "-c", "python3 -c 'import sys; print(sys.version_info[:2])'"], capture_output=True, text=True, env=e)
        self.assertEqual(v.stdout.strip(), "(3, 8)", f"the shim does not reach 3.8: {v.stdout!r} {v.stderr!r}")
        f = self.write_json("intent.json", self.intent([self.finding()]))
        r = subprocess.run([bashexe.bash(), str(SCRIPT), "pass", "write", *map(str, self.common()), "--intent", str(f)],
                           capture_output=True, text=True, env=e, cwd=self.tmp)
        self.assertEqual(r.returncode, 0, f"stdout: {r.stdout}\nstderr: {r.stderr}")
        self.assertTrue(json.loads(r.stdout.strip().splitlines()[0])["ok"], r.stdout)
        data = self.record_path().read_bytes()
        self.assertNotIn(b"\r", data)
        self.assertEqual(json.loads(data.decode("utf-8"))["change"], CHANGE)


# =======================================================================================================
class Cleanup(Base):
    def setUp(self):
        super().setUp()
        self.code = self.make_repo("code", f"https://github.com/{CODE}.git")
        self.store = self.make_repo("store", f"https://github.com/{STORE}.git")
        for d in (self.code, self.store):
            self.git(d, "checkout", "-q", "-b", BRANCH)
        self.commit(self.code, {"greet.py": "x = 1\n"}, "feat(add-greeting): task 1.1")
        self.commit(self.store, {"openspec/a.md": "a\n"}, "docs(add-greeting): plan")
        self.merged = "2026-10-08T09:00:00Z"

    def plan(self):
        return self.pp("cleanup-plan", "--code", self.code, "--store", self.store, "--branch", BRANCH)

    @staticmethod
    def cmds(entry):
        return [c["cmd"] for c in entry["commands"]]

    @staticmethod
    def fenced_pull(login):
        """The fenced pull cleanup-plan emits: as.sh runs git pull as the login that reads the repo."""
        return ["bash", str(SCRIPT.parent / "as.sh").replace("\\", "/"), login, "git", "pull", "--ff-only"]  # bare-bash: not started

    def same_cmds(self, got, want):
        fold = lambda cs: [[x.lower() if i == 1 and c[:1] == ["bash"] else x for i, x in enumerate(c)] for c in cs]  # bare-bash: not started
        self.assertEqual(fold(got), fold(want))

    @staticmethod
    def check_cmd(entry, head, main="main"):
        """The branch-check command a merged side runs after the pull: --head is the merged PR's head commit."""
        return ["pr-pair.sh", "branch-check", "--dir", entry["dir"], "--branch", BRANCH, "--main", main, "--head", head]

    def test_cleanup_plan_both_merged(self):
        self.add_pull(CODE, 5, state="closed", merged=self.merged, sha="a" * 40)  # squash: not the local tip
        self.add_pull(STORE, 2, state="closed", merged=self.merged, sha=self.tip(self.store))
        p = self.plan()
        for repo in ("code", "store"):
            e = p[repo]
            self.assertTrue(e["merged"])
            self.same_cmds(self.cmds(e)[:2], [["git", "checkout", "main"], self.fenced_pull("KintsugiBot")])
            self.assertEqual(self.cmds(e)[2], self.check_cmd(e, "a" * 40 if repo == "code" else self.tip(self.store)))
            self.assertEqual(len(e["commands"]), 3)
            self.assertEqual(e["delete"], ["git", "branch", "-D", BRANCH])
            self.assertNotIn("force_delete", e)
            self.assertNotIn("force_delete_allowed", e)
            self.assertEqual(e["commands"][0]["cwd"], str(self.code if repo == "code" else self.store).replace("\\", "/"))
        self.assertEqual(p["keep"], [])

    def test_cleanup_plan_jj_commands(self):
        """A jj repo's switch, pull and delete come from vcs.sh plan; the paired Git store keeps its Git commands."""
        jj = jjenv.require_jj()
        r = subprocess.run([jj, "git", "init", "--colocate"], cwd=self.code, capture_output=True, text=True, env=self.env())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.write("code/openspec/specwright.yaml", "vcs: jj\n")
        self.add_pull(CODE, 5, state="closed", merged=self.merged, sha="a" * 40)
        self.add_pull(STORE, 2, state="closed", merged=self.merged, sha=self.tip(self.store))
        p = self.plan()
        vcs_sh = str(SCRIPT.parent / "vcs.sh").replace("\\", "/").lower()

        def opt(cmd, flag):
            return cmd[cmd.index(flag) + 1]

        e = p["code"]
        switch, pull, check = self.cmds(e)
        for cmd, op in ((switch, "switch"), (pull, "pull")):
            self.assertEqual((cmd[0], cmd[1].lower(), cmd[2]), ("bash", vcs_sh, op), cmd)  # bare-bash: not started
            self.assertEqual((opt(cmd, "--role"), opt(cmd, "--branch")), ("code", "main"), cmd)
            self.assertEqual(Path(opt(cmd, "--repo")).resolve(), Path(self.code).resolve(), cmd)
        self.assertEqual(opt(pull, "--login"), "KintsugiBot")
        self.assertEqual(check, self.check_cmd(e, "a" * 40))
        delete = e["delete"]
        self.assertEqual((delete[0], delete[1].lower(), delete[2]), ("bash", vcs_sh, "delete-branch"), delete)  # bare-bash: not started
        self.assertEqual(opt(delete, "--branch"), BRANCH)
        self.assertIn("--force", delete)
        self.assertEqual(e["commands"][0]["cwd"], str(self.code).replace("\\", "/"))
        s = p["store"]
        self.same_cmds(self.cmds(s)[:2], [["git", "checkout", "main"], self.fenced_pull("KintsugiBot")])
        self.assertEqual(s["delete"], ["git", "branch", "-D", BRANCH])

    def test_cleanup_plan_pull_runs_through_as_sh(self):
        self.add_pull(CODE, 5, state="closed", merged=self.merged, sha="a" * 40)
        self.add_pull(STORE, 2, state="closed", merged=self.merged, sha=self.tip(self.store))
        # each repo's login from context: the store's planning_store.login, else the code login
        self.write("code/openspec/specwright.yaml", "github:\n  login: sh1ny\nplanning_store:\n  login: KintsugiBot\n")
        p = self.plan()
        self.same_cmds(self.cmds(p["code"])[1:2], [self.fenced_pull("sh1ny")])
        self.same_cmds(self.cmds(p["store"])[1:2], [self.fenced_pull("KintsugiBot")])
        self.write("code/openspec/specwright.yaml", "github:\n  login: sh1ny\n")  # the store inherits the code login
        p = self.plan()
        self.same_cmds(self.cmds(p["store"])[1:2], [self.fenced_pull("sh1ny")])
        # no login at all: the ambient (fenced) login, never a plain pull
        self.write("code/openspec/specwright.yaml", "pr:\n  max_fix_rounds: 2\n")
        p = self.plan()
        for repo in ("code", "store"):
            self.same_cmds(self.cmds(p[repo])[1:2], [self.fenced_pull("KintsugiBot")])
            self.assertTrue(all(c["cwd"] == p[repo]["dir"] for c in p[repo]["commands"]))

    def test_ambient_login_read_once_per_run(self):
        # PR #82: with no login set, one pr-pair run resolves the ambient login once, never per repo or per read
        self.add_pull(CODE, 5, state="closed", merged=self.merged, sha="a" * 40)
        self.add_pull(STORE, 2, state="closed", merged=self.merged, sha=self.tip(self.store))
        self.write("code/openspec/specwright.yaml", "pr:\n  max_fix_rounds: 2\n")
        if self.gh_log.exists():
            self.gh_log.unlink()
        self.plan()
        ambient = [c for c in self.gh_calls() if c["argv"][:2] == ["api", "user"] and not (c.get("env") or {}).get("GH_TOKEN")]
        self.assertEqual(len(ambient), 1, f"the ambient login was read {len(ambient)} times")

    def test_cleanup_plan_split(self):
        self.add_pull(CODE, 5, state="closed", merged=self.merged)
        self.add_pull(STORE, 2)  # open
        p = self.plan()
        self.assertTrue(p["code"]["merged"])
        self.assertEqual(self.cmds(p["code"])[-1][:2], ["pr-pair.sh", "branch-check"])
        self.assertEqual(p["code"]["delete"], ["git", "branch", "-D", BRANCH])
        self.assertFalse(p["store"]["merged"])
        self.assertEqual(p["store"]["commands"], [])
        self.assertEqual(len(p["keep"]), 1)
        keep = p["keep"][0]
        self.assertEqual((keep["repo"], keep["state"], keep["branch"]), ("store", "OPEN", BRANCH))
        self.assertEqual(keep["url"], f"https://github.com/{STORE}/pull/2")

    def test_cleanup_plan_rerun_code_branch_gone(self):
        # the code side was cleaned up on an earlier run; now the store PR merged too
        self.git(self.code, "checkout", "-q", "main")
        self.git(self.code, "branch", "-D", BRANCH)
        self.add_pull(CODE, 5, state="closed", merged=self.merged)
        self.add_pull(STORE, 2, state="closed", merged=self.merged, sha=self.tip(self.store))
        p = self.plan()
        self.assertTrue(p["code"]["merged"], "the merged code PR still counts; it is not missing")
        self.assertFalse(p["code"]["branch_exists"])
        self.assertEqual(p["code"]["commands"], [])
        self.same_cmds(self.cmds(p["store"])[:2], [["git", "checkout", "main"], self.fenced_pull("KintsugiBot")])
        self.assertEqual(self.cmds(p["store"])[2], self.check_cmd(p["store"], self.tip(self.store)))
        self.assertEqual(p["store"]["delete"], ["git", "branch", "-D", BRANCH])
        self.assertEqual(p["keep"], [])

    def test_cleanup_plan_deletes_an_empty_code_branch_with_d(self):
        self.git(self.code, "checkout", "-q", "main")
        self.git(self.code, "branch", "-D", BRANCH)
        self.git(self.code, "branch", BRANCH)  # no commits after main
        self.add_pull(STORE, 2, state="closed", merged=self.merged)
        p = self.plan()
        self.assertFalse(p["code"]["expected"])
        self.assertEqual(self.cmds(p["code"]), [["git", "branch", "-d", BRANCH]])
        self.assertNotIn("delete", p["code"])
        self.assertNotIn("force_delete", p["code"])
        self.assertNotIn("force_delete_allowed", p["code"])

    def test_cleanup_plan_runs_branch_check_after_pull(self):
        self.add_pull(CODE, 5, state="closed", merged=self.merged, sha="b" * 40)
        self.add_pull(STORE, 2, state="closed", merged=self.merged, sha="c" * 40)
        p = self.plan()
        for repo, head in (("code", "b" * 40), ("store", "c" * 40)):
            e = p[repo]
            self.same_cmds(self.cmds(e), [["git", "checkout", "main"], self.fenced_pull("KintsugiBot"), self.check_cmd(e, head)])
            self.assertEqual(e["delete"], ["git", "branch", "-D", BRANCH])  # run only when branch-check says delete: true
            self.assertNotIn("force_delete", e)
            self.assertNotIn("force_delete_allowed", e)
            self.assertTrue(all(c["cwd"] == e["dir"] for c in e["commands"]))

    def test_cleanup_plan_keeps_a_store_branch_shared_by_hand(self):
        # no GitHub origin on the store: no PR merges its branch, so cleanup must not finish silently
        self.git(self.store, "remote", "remove", "origin")
        self.add_pull(CODE, 5, state="closed", merged=self.merged)
        p = self.plan()
        self.assertEqual(self.cmds(p["code"])[-1][:2], ["pr-pair.sh", "branch-check"])
        self.assertEqual(p["store"]["commands"], [])
        self.assertEqual([(k["repo"], k["state"], k["branch"]) for k in p["keep"]], [("store", "SHARE_BY_HAND", BRANCH)])

    def test_cleanup_plan_open_pr_keeps_everything(self):
        self.add_pull(STORE, 2)
        p = self.plan()
        self.assertEqual(p["store"]["commands"], [])
        self.assertEqual(p["code"]["commands"], [])  # code has commits but no PR yet: nothing merged
        self.assertTrue(p["keep"])


class BranchCheck(Base):
    """branch-check (task 4.1): may a change branch be deleted after the merge? Read-only, local refs only."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("code", None)
        self.git(self.repo, "checkout", "-q", "-b", BRANCH)
        self.a = self.commit(self.repo, {"a.txt": "a\n"}, "feat: A")

    def refs(self):
        return self.git(self.repo, "for-each-ref", "--format=%(refname) %(objectname)") + "|" + self.git(self.repo, "symbolic-ref", "HEAD")

    def check(self, head=None):
        before = self.refs()
        args = ["branch-check", "--dir", self.repo, "--branch", BRANCH, "--main", "main"] + (["--head", head] if head else [])
        out = self.pp(*args)
        self.assertEqual(self.refs(), before, "branch-check changes no ref")
        self.assertTrue(out["ok"])
        return out

    def squash_to_main(self):
        """main gets the branch's work as one new commit, so the tip is not on main."""
        self.git(self.repo, "checkout", "-q", "main")
        self.commit(self.repo, {"a.txt": "a\n"}, "feat: A (squash)")
        self.git(self.repo, "checkout", "-q", BRANCH)

    def test_branch_check_on_main(self):
        self.git(self.repo, "checkout", "-q", "main")
        self.git(self.repo, "merge", "-q", "--no-ff", "-m", "merge", BRANCH)
        out = self.check("e" * 40)  # a head that is not here does not matter
        self.assertEqual((out["delete"], out["reason"], out["lacking"]), (True, "on_main", []))

    def test_branch_check_pr_head(self):
        self.squash_to_main()
        out = self.check(self.a)
        self.assertEqual((out["delete"], out["reason"], out["lacking"]), (True, "pr_head", []))

    def test_branch_check_ancestor_of_pr_head(self):
        c = self.commit(self.repo, {"c.txt": "c\n"}, "feat: C")
        self.git(self.repo, "update-ref", f"refs/remotes/origin/{BRANCH}", c)  # head C is here through origin/<branch>
        self.git(self.repo, "reset", "-q", "--hard", self.a)  # the local branch is behind the merged head
        self.squash_to_main()
        out = self.check(c)
        self.assertEqual((out["delete"], out["reason"], out["lacking"]), (True, "pr_head", []))

    def test_branch_check_keeps_commit_pushed_after_merge(self):
        self.squash_to_main()
        b = self.commit(self.repo, {"b.txt": "b\n"}, "feat: B after the merge")
        out = self.check(self.a)
        self.assertEqual((out["delete"], out["reason"]), (False, "lacking"))
        self.assertEqual(out["lacking"], [{"sha": b, "subject": "feat: B after the merge"}])

    def test_branch_check_head_unknown_keeps_branch(self):
        self.squash_to_main()
        out = self.check("d" * 40)  # the merged head is not in this checkout
        self.assertEqual((out["delete"], out["reason"]), (False, "head_unknown"))
        self.assertEqual(out["lacking"], [{"sha": self.a, "subject": "feat: A"}])
        out = self.check()  # no head at all
        self.assertEqual((out["delete"], out["reason"]), (False, "head_unknown"))

    def test_branch_check_git_error_stops(self):
        out = self.pp("branch-check", "--dir", self.repo, "--branch", "no-such-branch", "--main", "main", expect=1)
        self.assertFalse(out["ok"])


class ClosingCheck(Base):
    """closing-check: the issues a description's closing lines name against what GitHub will close (#61)."""

    def seed(self, body, refs=(), base="main", has_next=False, default=None):
        self.add_pull(CODE, 7, body=body, base=base)
        st = self.gh()
        fake_gh.set_closing_refs(st, CODE, 7, [(n, r) for n, r in refs], has_next)
        if default:
            fake_gh.set_default_branch(st, CODE, default)
        self.save_gh(st)

    def check(self, expect=0):
        return self.pp("closing-check", "--repo", CODE, "--pr", 7, expect=expect)

    def intended(self, body, refs=()):
        self.seed(body, refs)
        return self.check()["intended"]

    def test_closing_check_match(self):
        self.seed("Fixes #21\nFixes #24\n", refs=[(21, CODE), (24, CODE)])
        r = self.check()
        self.assertEqual((r["ok"], r["status"]), (True, "match"))
        self.assertEqual(r["intended"], [f"{CODE}#21", f"{CODE}#24"])
        self.assertEqual((r["missing"], r["extra"]), ([], []))
        self.assertEqual((r["base"], r["default_branch"]), ("main", "main"))
        self.assertEqual(sorted(r["linked"]), [f"{CODE}#21", f"{CODE}#24"])
        graphql = [c for c in self.gh_calls() if "graphql" in " ".join(c["argv"])]
        self.assertEqual(len(graphql), 1, "one GraphQL read")

    def test_closing_check_reports_refs_after_one_keyword_as_missing(self):
        self.seed("Fixes #24, #21, #43\n", refs=[(24, CODE)])
        r = self.check()
        self.assertEqual(r["status"], "mismatch")
        self.assertEqual(sorted(r["intended"]), [f"{CODE}#21", f"{CODE}#24", f"{CODE}#43"])
        self.assertEqual(sorted(r["missing"]), [f"{CODE}#21", f"{CODE}#43"])

    def test_closing_check_extra_is_not_a_mismatch(self):
        self.seed("Fixes #21\n", refs=[(21, CODE), (30, CODE)])
        r = self.check()
        self.assertEqual((r["status"], r["missing"], r["extra"]), ("match", [], [f"{CODE}#30"]))

    def test_closing_check_not_default_base(self):
        self.seed("Fixes #21\n", base="develop")
        r = self.check()
        self.assertEqual((r["ok"], r["status"]), (True, "not_default_base"))
        self.assertEqual((r["base"], r["default_branch"], r["intended"]), ("develop", "main", [f"{CODE}#21"]))

    def test_closing_check_default_branch_is_read_from_the_repository(self):
        self.seed("Fixes #21\n", refs=[(21, CODE)], base="trunk", default="trunk")
        self.assertEqual(self.check()["status"], "match")

    def test_closing_check_lookup_failure_is_unknown(self):
        self.seed("Fixes #21\n", refs=[(21, CODE)])
        st = self.gh()
        st["fail"] = ["graphql"]  # the one read carries the closing list and the default branch
        self.save_gh(st)
        r = self.check(expect=3)
        self.assertEqual((r["ok"], r["error"], r["unknown"]), (False, "lookup_failed", True))

    def test_closing_check_unreadable_pr_is_unknown(self):
        r = self.pp("closing-check", "--repo", CODE, "--pr", 99, expect=3)  # no such repo or PR in the fake
        self.assertEqual((r["ok"], r["error"]), (False, "lookup_failed"))

    def test_closing_check_next_page_is_unknown(self):
        self.seed("Fixes #21\n", refs=[(21, CODE)], has_next=True)
        r = self.check(expect=3)
        self.assertEqual((r["ok"], r["error"]), (False, "lookup_failed"))

    def test_closing_check_requires_repo_and_pr(self):
        self.pp("closing-check", "--repo", CODE, expect=2)
        self.pp("closing-check", "--pr", 7, expect=2)

    # ---- the parser ----
    def test_closing_check_keywords_and_forms(self):
        body = ("Close #1\nCLOSES: #2\nclosed #3\nfix #4\nFixed #5\nresolve #6\nResolves #7\nresolved: #8\n"
                "Prefix #9\nunfixed #10\n")
        self.assertEqual(self.intended(body), [f"{CODE}#{n}" for n in range(1, 9)])

    def test_closing_check_ignores_refs_in_code(self):
        body = ("Fixes #1\n```\nFixes #2\n```\n~~~\nFixes #3\n~~~\nand `Fixes #4` inline\n"
                "Fixes #6 and `#5`\n")
        self.assertEqual(self.intended(body), [f"{CODE}#1", f"{CODE}#6"])

    def test_closing_check_ignores_multi_backtick_code_spans(self):
        # a span closes at the next run of the same length: the single backtick inside does not end it
        body = "Fixes #1\nsee ``Fixes #2 ` Fixes #4`` and Fixes #3\n"
        self.assertEqual(self.intended(body), [f"{CODE}#1", f"{CODE}#3"])

    def test_closing_check_unmatched_backtick_is_literal(self):
        # no closing run of three or of two: both runs are text, so the keyword between them counts
        self.assertEqual(self.intended("Fixes #1\nsee ```Fixes #3 `` here\n"), [f"{CODE}#1", f"{CODE}#3"])

    def test_closing_check_reads_numbered_closing_lines(self):
        self.seed("1. Fixes #24, #21, #43\n2) Closes #7\n", refs=[(24, CODE), (7, CODE)])
        r = self.check()
        self.assertEqual(r["status"], "mismatch")
        self.assertEqual(sorted(r["intended"]), sorted(f"{CODE}#{n}" for n in (7, 21, 24, 43)))
        self.assertEqual(sorted(r["missing"]), [f"{CODE}#21", f"{CODE}#43"])

    def test_closing_check_normalises_cross_repo_and_urls(self):
        body = ("Fixes other/repo#5\nFixes https://github.com/acme/code/issues/8\n"
                "Resolves https://github.com/other/repo/issues/9\nFixes #1\n")
        self.assertEqual(self.intended(body), ["other/repo#5", f"{CODE}#8", "other/repo#9", f"{CODE}#1"])

    def test_closing_check_normalises_linked_issues_of_other_repos(self):
        self.seed("Fixes other/repo#5\n", refs=[(5, "other/repo"), (6, CODE)])
        r = self.check()
        self.assertEqual((r["status"], r["extra"]), ("match", [f"{CODE}#6"]))

    def test_closing_check_related_is_not_intended(self):
        self.assertEqual(self.intended("Fixes #21\nRelated: #52\nSee #53 and other/repo#54\n"), [f"{CODE}#21"])

    def test_closing_check_keyword_mid_line_names_only_the_next_ref(self):
        self.assertEqual(self.intended("This also fixes #5 but see #6\n"), [f"{CODE}#5"])

    def test_closing_check_keyword_line_names_every_ref(self):
        self.assertEqual(self.intended("- Fixes #5 and #6, other/repo#7\n"), [f"{CODE}#5", f"{CODE}#6", "other/repo#7"])

    def test_closing_check_lists_each_issue_once(self):
        self.assertEqual(self.intended("Fixes #5\nFixes #5\n"), [f"{CODE}#5"])


class ClosedCheck(Base):
    """closed-check: at cleanup, which issues a merged PR's closing lines name are still open (#61 part 3)."""

    MERGED = "2026-10-08T10:00:00Z"

    def seed(self, body, merged=MERGED, base="main", issues=None):
        """PR #7 of CODE; `issues` maps (slug, n) to (state, timeline)."""
        self.add_pull(CODE, 7, body=body, base=base, state="closed", merged=merged)
        st = self.gh()
        for (slug, n), (state, timeline) in (issues or {}).items():
            fake_gh.set_issue(st, slug, n, state, timeline)
        self.save_gh(st)

    def check(self, repos=CODE, expect=0, pr=7):
        return self.pp("closed-check", "--repo", CODE, "--pr", pr, "--repos", repos, expect=expect)

    def reads(self, needle):
        return [c for c in self.gh_calls() if "graphql" in " ".join(c["argv"]) and needle in " ".join(c["argv"])]

    def test_closed_check_lists_open_intended_issues(self):
        self.seed("Fixes #21\nFixes #24\n", issues={(CODE, 21): ("CLOSED", ["CLOSED"]), (CODE, 24): ("OPEN", [])})
        r = self.check()
        self.assertEqual((r["ok"], r["status"]), (True, "merged"))
        self.assertEqual(r["pr_url"], f"https://github.com/{CODE}/pull/7")
        self.assertEqual((r["base"], r["default_branch"]), ("main", "main"))
        self.assertEqual(r["intended"], [f"{CODE}#21", f"{CODE}#24"])
        self.assertEqual((r["open"], r["closed"], r["reopened"], r["outside"]), ([f"{CODE}#24"], [f"{CODE}#21"], [], []))
        self.assertEqual(len(self.reads("pullRequest(number")), 1, "one GraphQL read of the PR")
        self.assertEqual(len(self.reads("issue(number")), 2, "one read per intended issue")
        writes = [c for c in self.gh_calls() if c["argv"][:2] in (["issue", "close"], ["issue", "comment"])
                  or ("-X" in c["argv"] and "markdown" not in c["argv"])]  # the markdown POST renders; it writes nothing
        self.assertEqual(writes, [], "the check never writes")

    def test_closed_check_all_closed(self):
        self.seed("Fixes #21\nFixes #24\n", issues={(CODE, 21): ("CLOSED", ["CLOSED"]), (CODE, 24): ("CLOSED", ["CLOSED"])})
        r = self.check()
        self.assertEqual((r["status"], r["open"], r["reopened"], r["outside"]), ("merged", [], [], []))
        self.assertEqual(r["closed"], [f"{CODE}#21", f"{CODE}#24"])

    def test_closed_check_ignores_related(self):
        self.seed("Fixes #21\n\nRelated: #52\n", issues={(CODE, 21): ("CLOSED", ["CLOSED"]), (CODE, 52): ("OPEN", [])})
        r = self.check()
        self.assertEqual(r["intended"], [f"{CODE}#21"])
        self.assertEqual((r["open"], r["reopened"], r["outside"]), ([], [], []))
        self.assertEqual(self.reads("number=52"), [], "a Related issue is never read")

    def test_closed_check_not_merged(self):
        self.seed("Fixes #21\n", merged=None, issues={(CODE, 21): ("OPEN", [])})
        r = self.check()
        self.assertEqual((r["ok"], r["status"]), (True, "not_merged"))
        self.assertEqual((r["open"], r["reopened"], r["closed"], r["outside"]), ([], [], [], []))
        self.assertEqual(self.reads("issue(number"), [], "no issue is read for an unmerged PR")

    def test_closed_check_not_default_base(self):
        self.seed("Fixes #21\n", base="develop", issues={(CODE, 21): ("OPEN", [])})
        r = self.check()
        self.assertEqual((r["ok"], r["status"]), (True, "not_default_base"))
        self.assertEqual((r["base"], r["default_branch"], r["intended"]), ("develop", "main", [f"{CODE}#21"]))
        self.assertEqual((r["open"], r["reopened"], r["closed"], r["outside"]), ([], [], [], []))
        self.assertEqual(self.reads("issue(number"), [], "nothing is closed, so nothing is read")

    def test_closed_check_reports_reopened(self):
        self.seed("Fixes #24\nFixes #25\n", issues={(CODE, 24): ("OPEN", ["CLOSED", "REOPENED"]), (CODE, 25): ("OPEN", [])})
        r = self.check()
        self.assertEqual((r["reopened"], r["open"]), ([f"{CODE}#24"], [f"{CODE}#25"]))

    def test_closed_check_does_not_read_outside_issues(self):
        self.seed("Fixes #21\nFixes other/tool#5\n", issues={(CODE, 21): ("OPEN", [])})
        st = self.gh()
        st["fail"] = [{"match": "name=tool", "exit": 1, "stderr": "boom"}]  # any read of the outside repo would fail
        self.save_gh(st)
        r = self.check()
        self.assertEqual(r["status"], "merged")
        self.assertEqual((r["open"], r["outside"]), ([f"{CODE}#21"], ["other/tool#5"]))
        self.assertEqual(r["intended"], [f"{CODE}#21", "other/tool#5"])
        self.assertEqual(self.reads("name=tool"), [], "an outside issue is never read")

    def test_closed_check_reads_issues_of_every_listed_repo_case_insensitively(self):
        self.seed("Fixes #21\nFixes acme/plans#3\nFixes Other/Tool#5\n",
                  issues={(CODE, 21): ("OPEN", []), (STORE, 3): ("OPEN", ["CLOSED", "REOPENED"])})
        r = self.check(repos=f"{CODE.upper()},{STORE}")
        self.assertEqual((r["open"], r["reopened"], r["outside"]), ([f"{CODE}#21"], [f"{STORE}#3"], ["Other/Tool#5"]))
        self.assertEqual(len(self.reads("name=plans")), 1)

    def test_closed_check_reads_each_repo_through_its_login(self):
        # a private store only sh1ny can read: its issue is read as sh1ny while the call runs as KintsugiBot
        self.seed("Fixes #21\nFixes acme/plans#3\n", issues={(CODE, 21): ("OPEN", []), (STORE, 3): ("OPEN", [])})
        st = self.gh()
        st.setdefault("repos", {}).setdefault(STORE, {})["readers"] = ["sh1ny"]
        self.save_gh(st)
        args = ("closed-check", "--repo", CODE, "--pr", 7, "--repos", f"{CODE},{STORE}")
        self.assertEqual(self.pp(*args, env={"GH_TOKEN": "tok-k"}, expect=3)["error"], "lookup_failed")
        r = self.pp(*args, "--login", f"{STORE}=sh1ny", env={"GH_TOKEN": "tok-k"})
        self.assertEqual(r["open"], [f"{CODE}#21", f"{STORE}#3"])
        self.pp(*args, "--login", "sh1ny", expect=2)

    def test_closed_check_lookup_failure_is_unknown(self):
        self.seed("Fixes #21\n", issues={(CODE, 21): ("OPEN", [])})
        st = self.gh()
        st["fail"] = [{"match": r"pullRequest\(number", "exit": 1, "stderr": "boom"}]  # the PR read
        self.save_gh(st)
        r = self.check(expect=3)
        self.assertEqual((r["ok"], r["error"], r["unknown"]), (False, "lookup_failed", True))
        st["fail"] = [{"match": r"issue\(number", "exit": 1, "stderr": "boom"}]  # an in-scope issue read
        self.save_gh(st)
        r = self.check(expect=3)
        self.assertEqual((r["ok"], r["error"], r["unknown"]), (False, "lookup_failed", True))

    def test_closed_check_unreadable_pr_or_issue_is_unknown(self):
        self.seed("Fixes #21\n")  # issue 21 does not exist in the fake
        self.assertEqual(self.check(expect=3)["error"], "lookup_failed")
        self.assertEqual(self.check(expect=3, pr=99)["error"], "lookup_failed")

    def test_closed_check_ignores_hidden_references(self):
        body = ("Fixes #21\n\n    Fixes #30\n\n## Notes\n    Fixes #31\n\nsee `code\nFixes #32` here\n\n"
                "<!-- hidden\nFixes #33\n-->\n")
        self.seed(body, issues={(CODE, 21): ("OPEN", [])})
        r = self.check()
        self.assertEqual((r["intended"], r["open"]), ([f"{CODE}#21"], [f"{CODE}#21"]))
        for n in (30, 31, 32, 33):
            self.assertEqual(self.reads(f"number={n}"), [], f"hidden #{n} is never read")

    def test_closed_check_ignores_related_on_a_closing_line(self):
        self.seed("Fixes #21; Related: #52\n", issues={(CODE, 21): ("OPEN", []), (CODE, 52): ("OPEN", [])})
        r = self.check()
        self.assertEqual((r["intended"], r["open"]), ([f"{CODE}#21"], [f"{CODE}#21"]))
        self.assertEqual(self.reads("number=52"), [], "a Related issue is never read")

    def test_closed_check_ignores_a_line_without_a_closing_list(self):
        self.seed("Fixes the crash; Related: #52\n", issues={(CODE, 52): ("OPEN", [])})
        r = self.check()
        self.assertEqual((r["intended"], r["open"]), ([], []))
        self.assertEqual(self.reads("number=52"), [], "a Related issue is never read")

    def test_closed_check_fence_closes_only_on_a_bare_fence(self):
        # a fence line closes only with the same character, at least as long, and nothing but white space after it
        body = ("Fixes #21\n```\nFixes #30\n``` not a closer\nFixes #31\n```\nFixes #22\n"
                "~~~~\nFixes #32\n~~~ short\nFixes #33\n~~~~   \nFixes #34\n")
        self.seed(body, issues={(CODE, n): ("OPEN", []) for n in (21, 22, 34)})
        r = self.check()
        self.assertEqual(r["intended"], [f"{CODE}#21", f"{CODE}#22", f"{CODE}#34"])
        for n in (30, 31, 32, 33):
            self.assertEqual(self.reads(f"number={n}"), [], f"fenced #{n} is never read")

    def test_closed_check_removed_span_leaves_a_space(self):
        # the text around a removed code span never joins into a new word: Fi`x`xes is not Fixes
        self.seed("Fi`x`xes #30\nFixes #21\n", issues={(CODE, 21): ("OPEN", [])})
        r = self.check()
        self.assertEqual((r["intended"], r["open"]), ([f"{CODE}#21"], [f"{CODE}#21"]))
        self.assertEqual(self.reads("number=30"), [], "a joined word is no keyword")

    def test_closed_check_comment_opener_in_a_span_is_code(self):
        # code spans are found before HTML comments in a paragraph; a real comment still hides its text
        body = ("see `<!--` here\nFixes #21\n\nText `<!--\nstill code` and <!-- hidden\nFixes #30\n-->\nFixes #22\n")
        self.seed(body, issues={(CODE, 21): ("OPEN", []), (CODE, 22): ("OPEN", [])})
        r = self.check()
        self.assertEqual(r["intended"], [f"{CODE}#21", f"{CODE}#22"])
        self.assertEqual(self.reads("number=30"), [], "text in a real comment is never read")

    def test_closed_check_list_needs_a_ref_right_after_the_keyword(self):
        # only white space and an optional colon may sit between the leading keyword and the first reference
        body = "Fixes, #30\nFixes `x`; #31\nFixes `#21` and #32\nFixes: #22, #23\n"
        self.seed(body, issues={(CODE, n): ("OPEN", []) for n in (22, 23)})
        r = self.check()
        self.assertEqual(r["intended"], [f"{CODE}#22", f"{CODE}#23"])
        for n in (30, 31, 32):
            self.assertEqual(self.reads(f"number={n}"), [], f"#{n} is in no closing list")

    def test_closed_check_ignores_code_inside_containers(self):
        # block rules apply after the blockquote markers: `>     Fixes` is indented code in a quote, and a quoted fence hides its
        # lines; a list marker followed by five spaces starts indented code too
        body = (">     Fixes #30\n\n> ```\n> Fixes #31\n> ```\n\n-     Fixes #32\n\n> Fixes #21\n\n- Fixes #22\n")
        self.seed(body, issues={(CODE, n): ("OPEN", []) for n in (21, 22)})
        r = self.check()
        self.assertEqual(r["intended"], [f"{CODE}#21", f"{CODE}#22"])
        for n in (30, 31, 32):
            self.assertEqual(self.reads(f"number={n}"), [], f"#{n} is code in a container")

    def test_closed_check_ignores_fences_in_list_items(self):
        # a fence opened after a list marker hides its lines like any other fence
        body = "- ~~~\n  Fixes #52\n  ~~~\n\n1. ```\n   Fixes #53\n   ```\n\n- Fixes #21\n"
        self.seed(body, issues={(CODE, 21): ("OPEN", [])})
        r = self.check()
        self.assertEqual(r["intended"], [f"{CODE}#21"])
        for n in (52, 53):
            self.assertEqual(self.reads(f"number={n}"), [], f"#{n} is fenced code in a list item")

    def test_closed_check_list_marker_in_a_fence_is_code(self):
        # inside an open fence a list-marked fence line is content, never the closer; a tab after a marker counts like a space
        body = "```\n- ```\nFixes #30\n```\nFixes #21\n\n-\t~~~\n    Fixes #31\n    ~~~\n\nFixes #22\n"
        self.seed(body, issues={(CODE, n): ("OPEN", []) for n in (21, 22)})
        r = self.check()
        self.assertEqual(r["intended"], [f"{CODE}#21", f"{CODE}#22"])
        for n in (30, 31):
            self.assertEqual(self.reads(f"number={n}"), [], f"#{n} is fenced code")

    def test_closed_check_close_before_the_merge_is_open(self):
        # only a close at or after the merge, then a reopen, makes `reopened`; an older close/reopen leaves the issue `open`
        early = ("CLOSED", "2026-10-01T00:00:00Z")
        self.seed("Fixes #24\nFixes #25\n", issues={(CODE, 24): ("OPEN", [early, "REOPENED"]),
                                                    (CODE, 25): ("OPEN", [early, "REOPENED", ("CLOSED", self.MERGED), "REOPENED"])})
        r = self.check()
        self.assertEqual((r["open"], r["reopened"]), ([f"{CODE}#24"], [f"{CODE}#25"]))

    def test_closed_check_reads_text_after_an_inline_comment(self):
        # a comment ends at `-->` and the text after it is rendered: GitHub shows ` Fixes #31` after an HTML block comment too
        # (recorded rendering), while the comment's own text is dropped
        body = "Intro <!-- hidden\nFixes #30 --> Fixes #21\n\n<!-- block\n--> Fixes #31\n\nFixes #22\n"
        self.seed(body, issues={(CODE, n): ("OPEN", []) for n in (21, 22, 31)})
        r = self.check()
        self.assertEqual(r["intended"], [f"{CODE}#21", f"{CODE}#31", f"{CODE}#22"])
        self.assertEqual(self.reads("number=30"), [], "#30 is in a comment")

    def test_closed_check_requires_repo_pr_and_repos(self):
        self.pp("closed-check", "--repo", CODE, "--pr", 7, expect=2)
        self.pp("closed-check", "--repo", CODE, "--repos", CODE, expect=2)
        self.pp("closed-check", "--pr", 7, "--repos", CODE, expect=2)


class ClosingRendered(Base):
    """The closing lines are read from GitHub's own rendering of the description, never from a hand parse of its source (D7)."""

    WIDGET = "acme/widget"

    def seed(self, body, repo=CODE, merged=None):
        self.add_pull(repo, 7, body=body, state="closed" if merged else "open", merged=merged)

    def intended(self, body, repo=CODE):
        self.seed(body, repo)
        return self.pp("closing-check", "--repo", repo, "--pr", 7)["intended"]

    def test_continued_list_paragraph_counts(self):
        # four columns after a blank line continue the list item as a paragraph, not as indented code
        self.assertEqual(self.intended("- Notes\n\n    Fixes #21\n"), [f"{CODE}#21"])

    def test_quote_marked_fence_line_stays_code(self):
        # a quote-marked fence line inside a fence opened outside a quote is content, so `Fixes #12` is still code
        self.assertEqual(self.intended("```\n> ```\nFixes #12\n```\n"), [])

    def test_code_span_inside_word_no_join(self):
        self.assertEqual(self.intended("Fi`x`xes #52\n"), [])

    def test_soft_break_ends_closing_list(self):
        self.assertEqual(self.intended("Fixes #21\n#22 is unrelated\n"), [f"{CODE}#21"])

    def test_code_span_after_keyword_ends_list(self):
        # a code span between the keyword and the reference ends the list: #31 is not intended
        self.assertEqual(self.intended("Fixes `later` #31\n"), [])

    def test_code_span_after_midline_keyword_ends_list(self):
        self.assertEqual(self.intended("Notes, then fixes `x` #33\n"), [])

    def test_code_span_after_list_ends_it(self):
        self.assertEqual(self.intended("Fixes #34 `see log` #35\n"), [f"{CODE}#34"])

    def test_plain_closing_line(self):
        self.assertEqual(self.intended("Fixes #36\n"), [f"{CODE}#36"])

    def test_issue_url_counts(self):
        self.assertEqual(self.intended("Fixes https://github.com/acme/widget/issues/21\n", self.WIDGET), [f"{self.WIDGET}#21"])

    def test_other_repo_reported_outside(self):
        self.seed("Fixes other/tool#5\n", self.WIDGET, merged="2026-10-08T10:00:00Z")
        st = self.gh()
        st["fail"] = [{"match": "name=tool", "exit": 1, "stderr": "boom"}]  # any read of the outside repo would fail
        self.save_gh(st)
        r = self.pp("closed-check", "--repo", self.WIDGET, "--pr", 7, "--repos", self.WIDGET)
        self.assertEqual((r["intended"], r["outside"]), (["other/tool#5"], ["other/tool#5"]))

    def test_render_failure_unknown_both_checks(self):
        self.seed("Fixes #21\n", merged="2026-10-08T10:00:00Z")
        st = self.gh()
        st["fail"] = [{"match": "markdown", "exit": 1, "stderr": "boom"}]
        self.save_gh(st)
        for args in (("closing-check", "--repo", CODE, "--pr", 7), ("closed-check", "--repo", CODE, "--pr", 7, "--repos", CODE)):
            r = self.pp(*args, expect=3)
            self.assertEqual((r["ok"], r["error"], r["unknown"]), (False, "lookup_failed", True), args[0])


class ClosingRecordings(Base):
    """Every body the closing tests send has a recorded GitHub rendering (evals/pr-pair/record_markdown.py)."""

    def test_every_closing_body_has_a_recording(self):
        sys.path.insert(0, str(HERE))
        import closing_bodies
        recorded = json.loads(closing_bodies.FIXTURE.read_text(encoding="utf-8"))
        bodies = closing_bodies.collect_bodies()
        self.assertTrue(bodies)
        missing = [b for b in bodies if fake_gh.markdown_key(closing_bodies.MODE, b) not in recorded]
        self.assertEqual(missing, [], "run `python evals/pr-pair/record_markdown.py` to record these bodies")
        self.assertEqual(len(recorded), len(bodies), "one entry per body: rerun the recorder to drop stale entries")

    def test_finish_fixture_body_closed_check_reads_issue_state(self):
        """The body the finish fixtures seed (#146) has a recording: closed-check reads the issue, not `no recorded rendering`."""
        slug, issue = fixtures.PR_SLUG, fixtures.MERGED_CLOSES
        for state, key in (("CLOSED", "closed"), ("OPEN", "open")):
            with self.subTest(state=state):
                st = self.gh()
                st.setdefault("repos", {}).setdefault(slug, {})["pulls"] = [
                    self.pull(slug, 7, body=fixtures.MERGED_PR_BODIES[0], state="closed", merged="2026-10-08T10:00:00Z")]
                fake_gh.set_issue(st, slug, issue, state, ["CLOSED"] if state == "CLOSED" else [])
                self.save_gh(st)
                r = self.pp("closed-check", "--repo", slug, "--pr", 7, "--repos", slug, expect=None)
                self.assertNotIn("no recorded rendering", json.dumps(r))
                self.assertEqual(r["_rc"], 0, r)
                self.assertEqual((r["status"], r["intended"], r[key]), ("merged", [f"{slug}#{issue}"], [f"{slug}#{issue}"]))


class Merge(Base):
    """merge: one PUT of the configured method at the ready head, then a read-back that decides (add-agent-merge D2)."""

    HEAD = f"{7:040x}"
    TOKEN = {"GH_TOKEN": "tok-k"}

    def setUp(self):
        super().setUp()
        self.add_pull(CODE, 7)

    def merge(self, method="merge", head=None, expect=0, **kw):
        return self.pp("merge", "--repo", CODE, "--pr", 7, "--method", method, "--head", head or self.HEAD,
                       env=kw.pop("env", self.TOKEN), expect=expect, **kw)

    def repo_state(self, **over):
        st = self.gh()
        st.setdefault("repos", {}).setdefault(CODE, {}).update(over)
        self.save_gh(st)

    def inject(self, *entries):
        st = self.gh()
        st["fail"] = list(entries)
        self.save_gh(st)

    def puts(self):
        return [c for c in self.gh_calls() if "PUT" in c["argv"]]

    def writes(self):
        return [c for c in self.gh_calls() if any(x in ("PUT", "POST", "PATCH", "DELETE") for x in c["argv"])]

    def test_merge_sends_method_and_head_sha_fenced(self):
        r = self.merge("squash")
        self.assertEqual((r["ok"], r["status"]), (True, "merged"))
        puts = self.puts()
        self.assertEqual(len(puts), 1)
        argv = puts[0]["argv"]
        self.assertIn(f"repos/{CODE}/pulls/7/merge", argv)
        self.assertIn("merge_method=squash", argv)
        self.assertIn(f"sha={self.HEAD}", argv)
        calls = [c for c in self.gh_calls() if f"repos/{CODE}/pulls/7" in " ".join(c["argv"])]
        self.assertGreaterEqual(len(calls), 2, "the PUT and the read-back")
        for c in calls:
            self.assertEqual((c.get("env") or {}).get("GH_TOKEN"), "tok-k", "every call runs as the repo's login")
            self.assertIsNone(c.get("gh_repo"))

    def test_merge_reads_back_merged(self):
        r = self.merge()
        self.assertEqual((r["ok"], r["status"], r["repo"], r["pr"]), (True, "merged", CODE, 7))
        self.assertEqual(r["head_sha"], self.HEAD)
        self.assertEqual(r["merge_commit_sha"], self.pulls(CODE)[0]["merge_commit_sha"])
        self.assertTrue(self.pulls(CODE)[0]["merged_at"])
        last = self.gh_calls()[-1]["argv"]
        self.assertNotIn("PUT", last, "the read-back comes after the PUT")
        self.assertEqual(last[-1], f"repos/{CODE}/pulls/7")

    def test_merge_human_merged_first_is_merged(self):
        st = self.gh()
        p = st["repos"][CODE]["pulls"][0]
        p.update(state="closed", merged_at=T0, merge_commit_sha="c" * 40)
        self.save_gh(st)
        r = self.merge()
        self.assertEqual((r["ok"], r["status"]), (True, "merged"))
        self.assertEqual((r["head_sha"], r["merge_commit_sha"]), (self.HEAD, "c" * 40))
        self.assertEqual(len(self.puts()), 1, "the PUT was refused (405) and not retried")

    def test_merge_head_changed_409_reports_head_changed(self):
        r = self.merge(head="a" * 40, expect=1)
        self.assertEqual((r["ok"], r["error"], r["status"], r["reason"]), (False, "refused", "refused", "head_changed"))
        self.assertEqual((r["http_status"], r["repo"], r["pr"]), (409, CODE, 7))
        self.assertIn("Head branch was modified", r["message"])
        self.assertEqual(len(self.puts()), 1)
        self.assertIsNone(self.pulls(CODE)[0]["merged_at"])

    def test_merge_405_refused_single_request(self):
        self.repo_state(allowed_methods=["squash"])
        r = self.merge("rebase", expect=1)
        self.assertEqual((r["ok"], r["error"], r["status"], r["reason"], r["http_status"]), (False, "refused", "refused", "refused", 405))
        self.assertIn("Rebase merges are not allowed on this repository.", r["message"])
        self.assertEqual(len(self.puts()), 1, "no second method is tried")
        self.assertIn("merge_method=rebase", self.puts()[0]["argv"])

    def test_merge_queue_refusal_no_auto_merge(self):
        self.repo_state(merge_queue=True)
        r = self.merge(expect=1)
        self.assertEqual((r["status"], r["reason"], r["http_status"]), ("refused", "refused", 405))
        self.assertIn("merge queue", r["message"])
        self.assertEqual(len(self.puts()), 1)
        self.assertEqual(len(self.writes()), 1, "only the one PUT writes")
        text = " ".join(" ".join(c["argv"]) for c in self.gh_calls()).lower()
        for needle in ("graphql", "automerge", "auto_merge", "auto-merge", "queue"):
            self.assertNotIn(needle, text)
        self.assertFalse([c for c in self.gh_calls() if c["argv"][:2] == ["pr", "merge"]])

    def test_merge_readback_failure_exit3_unknown(self):
        self.inject({"match": r"pulls/7$", "exit": 1, "stderr": "boom"})
        r = self.merge(expect=3)
        self.assertEqual((r["ok"], r["error"], r["status"], r["unknown"]), (False, "lookup_failed", "unknown", True))
        self.assertEqual(len(self.puts()), 1, "the merge may have happened: never a second PUT")

    def test_merge_put_without_status_and_unreadable_readback_is_unknown(self):
        self.inject({"match": "-X PUT", "stderr": "connection reset", "once": True}, {"match": r"pulls/7$", "exit": 1, "stderr": "boom"})
        r = self.merge(expect=3)
        self.assertEqual((r["error"], r["status"], r["unknown"]), ("lookup_failed", "unknown", True))
        self.assertEqual(len(self.puts()), 1)

    def test_merge_put_without_status_and_open_readback_is_unknown(self):
        self.inject({"match": "-X PUT", "stderr": "connection reset", "once": True})
        r = self.merge(expect=3)
        self.assertEqual((r["error"], r["status"], r["unknown"]), ("lookup_failed", "unknown", True))
        self.assertEqual(len(self.puts()), 1)
        self.assertIsNone(self.pulls(CODE)[0]["merged_at"])

    def test_merge_put_5xx_and_open_readback_is_unknown(self):
        # GitHub may still complete a merge it answered with a server error: never report it refused
        for i, code in enumerate((500, 502, 503)):
            self.inject({"match": "-X PUT", "exit": 1, "stderr": f"gh: Server Error (HTTP {code})", "once": True})
            r = self.merge(expect=3)
            self.assertEqual((r["error"], r["status"], r["unknown"]), ("lookup_failed", "unknown", True), code)
            self.assertEqual(len(self.puts()), i + 1, f"one PUT per run, never a retry ({code})")
            self.assertIsNone(self.pulls(CODE)[0]["merged_at"])

    def test_merge_put_without_status_but_readback_merged(self):
        st = self.gh()
        st["repos"][CODE]["pulls"][0].update(state="closed", merged_at=T0, merge_commit_sha="d" * 40)
        self.save_gh(st)
        self.inject({"match": "-X PUT", "stderr": "connection reset", "once": True})
        r = self.merge()
        self.assertEqual((r["status"], r["merge_commit_sha"]), ("merged", "d" * 40))
        self.assertEqual(len(self.puts()), 1)

    def test_merge_invalid_method_usage_no_request(self):
        for method in ("fast-forward", "Squash", "", "admin"):
            r = self.merge(method, expect=2)
            self.assertEqual((r["ok"], r["error"]), (False, "usage"))
            self.assertIn("--method", r["message"])
        self.assertEqual(self.gh_calls(), [])

    def test_merge_invalid_head_usage_no_request(self):
        for head in ("xyz", "abc", "g" * 40, "a" * 41, "", "main"):
            r = self.pp("merge", "--repo", CODE, "--pr", 7, "--method", "merge", "--head", head, env=self.TOKEN, expect=2)
            self.assertEqual((r["ok"], r["error"]), (False, "usage"))
            self.assertIn("--head", r["message"])
        self.assertIn("--head", self.pp("merge", "--repo", CODE, "--pr", 7, "--method", "merge", expect=2)["message"])
        self.assertIn("--method", self.pp("merge", "--repo", CODE, "--pr", 7, "--head", self.HEAD, expect=2)["message"])
        self.assertEqual(self.gh_calls(), [])


class DeleteRemote(Base):
    """delete-remote: delete the remote branch only at the merged head, with no open PR based on it (add-agent-merge D3)."""

    HEAD = f"{7:040x}"
    OTHER = "b" * 40
    TOKEN = {"GH_TOKEN": "tok-k"}

    def setUp(self):
        super().setUp()
        self.set_branches({BRANCH: self.HEAD})

    def set_branches(self, branches, **over):
        st = self.gh()
        st.setdefault("repos", {}).setdefault(CODE, {}).update(branches=branches, **over)
        self.save_gh(st)

    def branches(self):
        return self.gh()["repos"][CODE].get("branches", {})

    def inject(self, *entries):
        st = self.gh()
        st["fail"] = list(entries)
        self.save_gh(st)

    def delete(self, branch=BRANCH, head=None, expect=0, **kw):
        return self.pp("delete-remote", "--repo", CODE, "--branch", branch, "--head", head or self.HEAD,
                       env=kw.pop("env", self.TOKEN), expect=expect, **kw)

    def deletes(self):
        return [c for c in self.gh_calls() if "DELETE" in c["argv"]]

    def test_delete_remote_at_head_deletes(self):
        r = self.delete()
        self.assertEqual((r["ok"], r["status"], r["repo"], r["branch"]), (True, "deleted", CODE, BRANCH))
        self.assertNotIn(BRANCH, self.branches())
        self.assertEqual(len(self.deletes()), 1)
        self.assertIn(f"repos/{CODE}/git/refs/heads/{BRANCH}", self.deletes()[0]["argv"])
        self.assertEqual(self.deletes()[0]["env"]["GH_TOKEN"], "tok-k", "runs as the repo's login")

    def test_delete_remote_head_compare_ignores_case(self):
        self.set_branches({BRANCH: "ab" * 20})
        self.assertEqual(self.delete(head="AB" * 20)["status"], "deleted")

    def test_delete_remote_moved_keeps_branch(self):
        self.set_branches({BRANCH: self.OTHER})
        r = self.delete()
        self.assertEqual((r["ok"], r["status"], r["sha"]), (True, "moved", self.OTHER))
        self.assertEqual(self.branches(), {BRANCH: self.OTHER})
        self.assertEqual(self.deletes(), [])

    def test_delete_remote_based_on_keeps_branch(self):
        self.add_pull(CODE, 11, ref="feat/child", base=BRANCH)
        self.add_pull(CODE, 12, ref="feat/other", base="main")
        self.add_pull(CODE, 13, ref="feat/closed", base=BRANCH, state="closed")
        r = self.delete()
        self.assertEqual((r["ok"], r["status"], r["prs"]), (True, "based_on", [11]))
        self.assertIn(BRANCH, self.branches())
        self.assertEqual(self.deletes(), [])
        lists = [c["argv"] for c in self.gh_calls() if any("pulls?" in x for x in c["argv"])]
        self.assertEqual(len(lists), 1)
        self.assertIn("--paginate", lists[0])
        self.assertTrue(any(x.startswith(f"repos/{CODE}/pulls?state=open&base=") and "per_page=100" in x for x in lists[0]))

    def test_delete_remote_missing_ref_gone(self):
        self.set_branches({})
        r = self.delete()
        self.assertEqual((r["ok"], r["status"]), (True, "gone"))
        self.assertEqual(self.deletes(), [])

    def test_delete_remote_ref_read_failure_exit3(self):
        self.inject({"match": r"git/ref/heads", "exit": 1, "stderr": "gh: Server Error (HTTP 500)"})
        r = self.delete(expect=3)
        self.assertEqual((r["ok"], r["unknown"]), (False, True))
        self.assertIn(BRANCH, self.branches())
        self.assertEqual(self.deletes(), [])

    def test_delete_remote_ref_read_without_status_exit3(self):
        self.inject({"match": r"git/ref/heads", "exit": 1, "stderr": "connection reset"})
        r = self.delete(expect=3)
        self.assertTrue(r["unknown"])
        self.assertEqual(self.deletes(), [])

    def test_delete_remote_pr_list_failure_exit3(self):
        self.inject({"match": r"pulls\?", "exit": 1, "stderr": "boom"})
        r = self.delete(expect=3)
        self.assertEqual((r["ok"], r["unknown"]), (False, True))
        self.assertIn(BRANCH, self.branches())
        self.assertEqual(self.deletes(), [])

    def test_delete_remote_refused_is_kept_with_message(self):
        self.set_branches({BRANCH: self.HEAD}, protected_branches=[BRANCH])
        r = self.delete(expect=1)
        self.assertEqual((r["ok"], r["error"], r["status"]), (False, "kept", "kept"))
        self.assertIn("protected", r["message"])
        self.assertIn(BRANCH, self.branches())
        self.assertEqual(len(self.deletes()), 1)

    def test_delete_remote_vanished_between_read_and_delete_is_gone(self):
        self.inject({"match": "-X DELETE", "exit": 1, "stderr": "gh: Reference does not exist (HTTP 422)", "once": True})
        r = self.delete()
        self.assertEqual((r["ok"], r["status"]), (True, "gone"))
        self.assertEqual(len(self.deletes()), 1)

    def test_delete_remote_delete_without_status_exit3(self):
        self.inject({"match": "-X DELETE", "exit": 1, "stderr": "connection reset", "once": True})
        r = self.delete(expect=3)
        self.assertTrue(r["unknown"])
        self.assertEqual(len(self.deletes()), 1)

    def test_delete_remote_branch_with_slash(self):
        self.set_branches({"feat/a/b": self.HEAD, "feat": self.OTHER})
        self.add_pull(CODE, 11, ref="x", base="feat/a/c")
        r = self.delete("feat/a/b")
        self.assertEqual((r["status"], r["branch"]), ("deleted", "feat/a/b"))
        self.assertEqual(self.branches(), {"feat": self.OTHER})

    def test_delete_remote_usage_no_request(self):
        for head in ("xyz", "abc1234", "g" * 40, "a" * 41, "", "main"):
            r = self.pp("delete-remote", "--repo", CODE, "--branch", BRANCH, "--head", head, env=self.TOKEN, expect=2)
            self.assertEqual((r["ok"], r["error"]), (False, "usage"))
            self.assertIn("--head", r["message"])
        for args, word in ((("--branch", BRANCH, "--head", self.HEAD), "--repo"), (("--repo", CODE, "--head", self.HEAD), "--branch"),
                           (("--repo", CODE, "--branch", BRANCH), "--head")):
            r = self.pp("delete-remote", *args, env=self.TOKEN, expect=2)
            self.assertEqual(r["error"], "usage")
            self.assertIn(word, r["message"])
        self.assertEqual(self.gh_calls(), [])
        self.assertIn(BRANCH, self.branches())


class ItemIssues(Base):
    """item-issues: the existing PR-item issues of one repository in one paged read (bound-pr-scripts D4)."""

    TOKEN = {"GH_TOKEN": "tok-k"}

    def seed(self, slug, issues):
        st = self.gh()
        st.setdefault("repos", {}).setdefault(slug, {})["issue_list"] = issues
        self.save_gh(st)

    def item_issues(self, repo, *items, expect=0, env=None):
        args = ["item-issues", "--repo", repo]
        for i in items:
            args += ["--item", i]
        return self.pp(*args, env={**self.TOKEN, **(env or {})}, expect=expect)

    def issue_reads(self, slug):
        return [c for c in self.gh_calls() if any(f"repos/{slug}/issues" in x for x in c["argv"])]

    def test_one_read_finds_tracked_item(self):
        self.seed(CODE, [{"number": 9, "state": "closed", "body": "text\n\nspecwright:pr-item PRRT_2"},
                         {"number": 4, "state": "open", "body": "unrelated"},
                         {"number": 12, "state": "open", "body": "dup\nspecwright:pr-item PRRT_2"},
                         {"number": 13, "state": "open", "body": "specwright:pr-item PRRT_20"}])
        r = self.item_issues(CODE, "PRRT_1", "PRRT_2", "PRRT_3")
        self.assertEqual((r["ok"], r["found"], r["missing"]), (True, {"PRRT_2": 9}, ["PRRT_1", "PRRT_3"]))
        reads = self.issue_reads(CODE)
        self.assertEqual(len(reads), 1, "one read whatever the number of items")
        self.assertIn("--paginate", reads[0]["argv"])
        self.assertTrue(any("state=all" in x and "per_page=100" in x for x in reads[0]["argv"]))
        self.assertIn("--jq", reads[0]["argv"])

    def test_reads_only_its_repo_as_its_login(self):
        self.seed(CODE, [{"number": 3, "state": "open", "body": "specwright:pr-item A"}])
        self.seed(STORE, [{"number": 5, "state": "open", "body": "specwright:pr-item B"}])
        r = self.item_issues(CODE, "A", "B")
        self.assertEqual((r["found"], r["missing"]), ({"A": 3}, ["B"]), "an item is matched only in its own repository")
        self.assertEqual(self.issue_reads(STORE), [])
        r = self.item_issues(STORE, "B", env={"GH_TOKEN": "tok-s"})
        self.assertEqual(r["found"], {"B": 5})
        reads = self.issue_reads(STORE)
        self.assertEqual(len(reads), 1)
        self.assertEqual(reads[0]["env"]["GH_TOKEN"], "tok-s")
        self.assertEqual(len(self.issue_reads(CODE)), 1)

    def test_pull_request_with_marker_ignored(self):
        self.seed(CODE, [{"number": 7, "state": "open", "body": "specwright:pr-item A", "pull_request": {"url": "u"}}])
        r = self.item_issues(CODE, "A")
        self.assertEqual((r["found"], r["missing"]), ({}, ["A"]))

    def test_marker_must_be_a_whole_line(self):
        self.seed(CODE, [{"number": 7, "state": "open", "body": "see specwright:pr-item A in text"},
                         {"number": 8, "state": "open", "body": "x\r\nspecwright:pr-item A\r\n"}])
        self.assertEqual(self.item_issues(CODE, "A")["found"], {"A": 8})

    def test_read_failure_exits_3_named(self):
        st = self.gh()
        st["fail"] = [{"match": r"issues\?", "exit": 1, "stderr": "boom"}]
        self.save_gh(st)
        r = self.item_issues(CODE, "A", expect=3)
        self.assertEqual((r["ok"], r["error"], r["unknown"]), (False, "lookup_failed", True))
        self.assertNotIn("found", r)

    def test_read_past_size_bound_exits_3_named(self):
        self.seed(CODE, [{"number": 1, "state": "open", "body": "specwright:pr-item A"}])
        st = self.gh()
        st["flood"] = [{"match": r"api .*issues", "bytes": 20000}]
        self.save_gh(st)
        r = self.item_issues(CODE, "A", expect=3, env={"SPECWRIGHT_NET_MAX_BYTES": "5000"})
        self.assertEqual((r["ok"], r["error"]), (False, "response_too_large"))

    def test_usage_makes_no_request(self):
        self.item_issues(CODE, expect=2)
        self.pp("item-issues", "--item", "A", env=self.TOKEN, expect=2)
        self.assertEqual(self.gh_calls(), [])


class Bounded(PassBase):
    """Network commands run under a deadline and a byte bound (bound-pr-scripts D3); a limit is a named stop."""

    def pid_alive(self, pid):
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
            return f'"{pid}"' in out
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def wait_gone(self, pid, seconds=10):
        import time
        end = time.time() + seconds
        while time.time() < end and self.pid_alive(pid):
            time.sleep(0.2)
        return not self.pid_alive(pid)

    def replied_code_fix(self, finding):
        """A code fix committed, pushed and re-requested; the reply is posted (so only the reaction can be missing)."""
        self.write_record([finding])
        self.fix_code()
        self.push_all()
        self.pushed_at(CODE, BRANCH, self.tip(self.code), "2026-10-08T12:00:00Z")
        self.add_comment(CODE, 5, "@codex review", "KintsugiBot", 2002, created_at="2026-10-08T12:00:03Z")

    def inject(self, **over):
        st = self.gh()
        st.update(over)
        self.save_gh(st)

    def test_discover_hung_gh_deadline_exceeded(self):
        import time
        pid_file = self.tmp / "hung.pid"
        self.inject(hang=[{"match": r"api .*pulls", "pid_file": str(pid_file)}])
        t0 = time.time()
        r = self.pp("discover", "--repo", CODE, "--branch", BRANCH, expect=3,
                    env={"SPECWRIGHT_NET_PAGED_DEADLINE": "2", "SPECWRIGHT_NET_DEADLINE": "2"})
        self.assertLess(time.time() - t0, 2 + 10)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "deadline_exceeded")
        self.assertTrue(r["unknown"])
        self.assertIn("gh api", r["message"])
        self.assertTrue(pid_file.exists(), "the hung gh call was reached")
        self.assertTrue(self.wait_gone(int(pid_file.read_text())), "no gh process the script started is still running")

    def test_discover_large_list_read_whole(self):
        pulls = [self.pull(CODE, n, body="x" * 14000) for n in range(1, 151)]  # ~2 MiB over two pages
        self.seed_pulls(CODE, pulls)
        r = self.pp("discover", "--repo", CODE, "--branch", BRANCH)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["prs"]), 150)
        self.assertNotIn("error", r)

    def test_paginated_read_too_large(self):
        self.inject(flood=[{"match": r"api .*pulls", "bytes": 20000}])
        r = self.pp("discover", "--repo", CODE, "--branch", BRANCH, expect=3, env={"SPECWRIGHT_NET_MAX_BYTES": "5000"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "response_too_large")
        self.assertTrue(r["unknown"])
        self.assertIn("gh api", r["message"])
        self.assertNotIn("prs", r)

    def test_reaction_loop_page_cap(self):
        self.replied_code_fix(self.finding("F1", dest="code", kind="comment", item="IC_node1", resolve=False,
                                           edits=[{"file": "greet.py", "contains": ["strip()"]}]))
        st = self.gh()
        for i in range(60):  # one reaction per page: past the 50-page cap, and never the viewer's
            fake_gh.add_node_reaction(st, CODE, "IC_node1", f"someone{i}", "THUMBS_UP")
        st["graphql_page_size"] = 1
        self.save_gh(st)
        p = self.plan(code=snap(comments=[]), expect=3)
        self.assertEqual((p["ok"], p["error"]), (False, "response_too_large"))
        self.assertTrue(p["unknown"])
        self.assertTrue(self.record_path().exists())

    def merge_hung(self, merged):
        self.add_pull(CODE, 7, state="closed" if merged else "open", merged="2026-10-08T11:00:00Z" if merged else None)
        self.inject(hang=[{"match": r"-X PUT", "pid_file": str(self.tmp / "put.pid")}])
        return self.pp("merge", "--repo", CODE, "--pr", 7, "--method", "merge", "--head", f"{7:040x}",
                       env={"GH_TOKEN": "tok-k", "SPECWRIGHT_NET_DEADLINE": "2"}, expect=0 if merged else 3)

    def test_merge_hung_put_with_merged_readback_is_merged(self):
        r = self.merge_hung(True)
        self.assertEqual((r["ok"], r["status"]), (True, "merged"))
        self.assertTrue(self.wait_gone(int((self.tmp / "put.pid").read_text())))

    def test_merge_hung_put_with_open_readback_is_unknown(self):
        r = self.merge_hung(False)
        self.assertEqual((r["ok"], r["status"], r["unknown"]), (False, "unknown", True))
        self.assertTrue(self.wait_gone(int((self.tmp / "put.pid").read_text())))


class TestTier(Base):
    """tier: the cheap-tier switch is true only for a parsed boolean true; nothing else in the settings matters (add-cheap-tier D2)."""

    def setUp(self):
        super().setUp()
        self.code = self.make_repo("code", f"https://github.com/{CODE}.git")

    def tier(self, text=None):
        if text is not None:
            self.write("code/openspec/specwright.yaml", text)
        return self.pp("tier", "--code", self.code)

    def test_unset_is_off(self):
        for text in (None, "finish: pr\n", "cheap_tier:\n  other: 1\n", "cheap_tier:\n  enabled:\n"):
            r = self.tier(text)
            self.assertEqual((r["ok"], r["cheap_tier"]), (True, False), text)
            self.assertNotIn("note", r, text)

    def test_false_and_no_are_off(self):
        for v in ("false", "no", "False", "NO"):
            r = self.tier(f"cheap_tier:\n  enabled: {v}\n")
            self.assertEqual((r["ok"], r["cheap_tier"]), (True, False), v)
            self.assertNotIn("note", r, v)

    def test_true_and_yes_are_on(self):
        for v in ("true", "yes", "True"):
            r = self.tier(f"cheap_tier:\n  enabled: {v}\n")
            self.assertEqual((r["ok"], r["cheap_tier"]), (True, True), v)
            self.assertNotIn("note", r, v)

    def test_unrecognised_value_is_off_with_note(self):
        r = self.tier("cheap_tier:\n  enabled: on\n")
        self.assertEqual((r["ok"], r["cheap_tier"]), (True, False))
        self.assertIn("cheap_tier.enabled: on is not true or false; treated as false", r["note"])
        for v in ('"true"', "1"):
            r = self.tier(f"cheap_tier:\n  enabled: {v}\n")
            self.assertEqual(r["cheap_tier"], False, v)
            self.assertIn(v, r["note"])

    def test_non_map_section_is_off_with_note(self):
        r = self.tier("cheap_tier: true\n")
        self.assertEqual((r["ok"], r["cheap_tier"]), (True, False))
        self.assertIn("cheap_tier must hold enabled: true|false; treated as false", r["note"])

    def test_inline_form_unrecognised_value_is_off_with_note(self):
        r = self.tier("cheap_tier: { enabled: on }\n")
        self.assertEqual((r["ok"], r["cheap_tier"]), (True, False))
        self.assertIn("on", r["note"])
        self.assertIn("cheap_tier.enabled", r["note"])
        self.assertEqual(self.tier("cheap_tier: { enabled: true }\n")["cheap_tier"], True)

    def test_bad_merge_settings_do_not_affect_tier(self):
        r = self.tier("pr:\n  merge: agent\n  merge_method: fast\ncheap_tier:\n  enabled: true\n")
        self.assertEqual((r["ok"], r["cheap_tier"], r["_rc"]), (True, True, 0))
        self.assertEqual(self.pp("context", "--code", self.code, expect=2)["error"], "bad_setting")


if __name__ == "__main__":
    unittest.main()
