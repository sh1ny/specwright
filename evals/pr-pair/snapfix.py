"""Shared fixture for tests of `sw pr snapshot` and `sw pr reply` against the fake gh (evals/fakes/gh.py).

SnapCase gives each test a temp dir with the fake gh on PATH, a state file, an empty SPECWRIGHT_STATE_DIR, and helpers that
add threads, comments, reviews and edits at a fake-clock time and advance the clock. They run through `sw` (evals/swcall.py).

The fake hands the shipped --jq filters to an external evaluator: gojq when it is on PATH (what gh itself embeds), else jq.
JQ_NAME says which one; `banner()` prints it, so a test run shows what evaluated the filters. A test needing neither is skipped.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SNAPSHOT, REPLY = "snapshot", "reply"  # `run_script` starts `sw pr <name>`
sys.path.insert(0, str(ROOT / "evals" / "git-workflow"))
import fixtures  # noqa: E402

sys.path.insert(0, str(ROOT / "evals" / "vcs"))
import vcs_test_support  # noqa: E402
import swcall  # noqa: E402  (vcs_test_support puts evals/ on sys.path)

sys.path.insert(0, str(ROOT / "evals" / "fakes"))
import gh as fake_gh  # noqa: E402

JQ = shutil.which("gojq") or shutil.which("jq")
JQ_NAME = Path(JQ).stem if JQ else None
T0 = "2026-10-10T10:00:00Z"


def rev(login, role="required", timeout=3600, **report):
    """One reviewer entry of a --reviewer-config file; `report` holds its rules (sha_pattern, check, marker, ignore)."""
    out = {"login": login, "role": role, "timeout": timeout}
    if report:
        out["report"] = report
    return out


def banner():
    """Name the filter evaluator in the test output (call from setUpModule)."""
    print(f"\n[snapfix] --jq evaluator: {JQ_NAME or 'none (tests skipped)'}{' = ' + JQ if JQ else ''}", file=sys.stderr)


@unittest.skipUnless(JQ, "needs gojq or jq on PATH")
class SnapCase(unittest.TestCase):
    maxDiff = None
    SLUG, PR = "o/n", 7

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fixtures.rmtree, self.tmp)
        (self.tmp / "bin").mkdir()
        fixtures.install_fake_gh(self.tmp)
        vcs_test_support.stamp_version(self.tmp)  # `sw` checks the version stamp of the project it runs in
        self.gh_state, self.gh_log = self.tmp / "gh-state.json", self.tmp / "gh-log.jsonl"
        self.state_dir = self.tmp / "state"
        self.extra_env = {}
        self.mutate(lambda st: st.update(
            {"user": "me", "tokens": {"me": "tok-me", "rev": "tok-rev", "other": "tok-other"}, "clock": T0,
             "repos": {self.SLUG: {"pulls": [self._pull()]}}}))

    def _pull(self):
        n = self.PR
        return {"number": n, "html_url": f"https://github.com/{self.SLUG}/pull/{n}", "state": "open", "merged_at": None,
                "title": f"t{n}", "body": "", "author": "me",
                "head": {"ref": "feat/x", "label": "o:feat/x", "sha": "a" * 40, "repo": {"full_name": self.SLUG}},
                "base": {"ref": "main"}}

    # ---- state -------------------------------------------------------------------------------------------
    def st(self):
        return fake_gh.read_state(self.gh_state)

    def mutate(self, fn):
        """Load the fake's state, apply fn(state), save it whole. Returns fn's result."""
        st = fake_gh.read_state(self.gh_state) if self.gh_state.exists() else {}
        out = fn(st)
        fake_gh.write_state(self.gh_state, st)
        return out

    def set_tick(self, **spec):
        """State that moves between the polls of a --wait loop (fake gh `tick`). sw sleeps in its own process, so the fake
        gh does it instead, on the call each poll starts with (the head-info query, the only one naming headRepository):
        every poll after the first applies one tick (see evals/fakes/gh.py)."""
        self.mutate(lambda st: st.update({"tick": {"match": "headRepository", **spec}}))

    def advance(self, seconds):
        return self.mutate(lambda st: fake_gh.advance_clock(st, seconds))

    def set_clock(self, iso):
        self.mutate(lambda st: fake_gh.set_clock(st, iso))

    def clock(self):
        return self.st()["clock"]

    def add_thread(self, author, body, at=None, resolved=False, path="a.py", line=1, thread_id=None):
        """A thread with its first comment; returns (thread id, comment dict)."""
        def f(st):
            t = fake_gh.add_thread(st, self.SLUG, self.PR, path=path, line=line, thread_id=thread_id, resolved=resolved)
            return t["id"], fake_gh.add_thread_comment(st, self.SLUG, self.PR, t["id"], author, body, at=at)
        return self.mutate(f)

    def add_reply(self, thread_id, author, body, at=None):
        return self.mutate(lambda st: fake_gh.add_thread_comment(st, self.SLUG, self.PR, thread_id, author, body, at=at))

    def add_comment(self, author, body, at=None):
        return self.mutate(lambda st: fake_gh.add_pr_comment(st, self.SLUG, self.PR, author, body, at=at))

    def add_review(self, author, body, state="COMMENTED", at=None):
        return self.mutate(lambda st: fake_gh.add_review(st, self.SLUG, self.PR, author, body, state=state, at=at))

    def edit(self, item_id, body, at=None):
        return self.mutate(lambda st: fake_gh.edit_item(st, self.SLUG, self.PR, item_id, body, at=at))

    def react(self, item_id, login, content="THUMBS_UP", at=None):
        self.mutate(lambda st: fake_gh.add_node_reaction(st, self.SLUG, item_id, login, content, at=at or fake_gh.now(st)))

    def set_head(self, oid, committed_date=None):
        self.mutate(lambda st: fake_gh.set_head(st, self.SLUG, self.PR, oid, committed_date))

    def set_checks(self, contexts):
        self.mutate(lambda st: fake_gh.set_checks(st, self.SLUG, self.PR, contexts))

    def add_activity(self, oid, timestamp, ref="refs/heads/feat/x"):
        self.mutate(lambda st: st["repos"][self.SLUG].setdefault("activity", []).append(
            {"ref": ref, "after": oid, "timestamp": timestamp}))

    def write_config(self, *reviewers, name="reviewers.json", where=None, fmt=2):
        """Write a reviewer config as `sw pr` does (format 2, canonical JSON, logins sorted) and return its path."""
        doc = {"format": fmt, "reviewers": sorted(reviewers, key=lambda r: r["login"])}
        path = Path(where or self.tmp) / name
        path.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False), encoding="utf-8", newline="\n")
        return fixtures.posix(path)

    def cfg(self, *reviewers):
        """The arguments that hand `reviewers` to `sw pr snapshot`."""
        return ["--reviewer-config", self.write_config(*reviewers)]

    def gh_calls(self):
        if not self.gh_log.exists():
            return []
        return [json.loads(l)["argv"] for l in self.gh_log.read_text(encoding="utf-8").splitlines()]

    # ---- running sw -----------------------------------------------------------------------------
    def env(self, login="me", **extra):
        """Environment with the fake gh first on PATH; GH_TOKEN picks the viewer (login None = the state's default user)."""
        e = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST")}
        e.update({"PATH": str(self.tmp / "bin") + os.pathsep + e.get("PATH", ""),
                  "FAKE_GH_STATE": str(self.gh_state), "FAKE_GH_LOG": str(self.gh_log), "FAKE_GH_JQ": JQ,
                  "SPECWRIGHT_STATE_DIR": str(self.state_dir), "SPECWRIGHT_HOME": str(vcs_test_support.sw_home()), "PYTHONIOENCODING": "utf-8", "GIT_TERMINAL_PROMPT": "0"})
        if login:
            e["GH_TOKEN"] = self.st()["tokens"][login]
        e.update(self.extra_env)
        e.update(extra)
        return e

    def run_script(self, script, *args, login="me", env=None, cwd=None, stdin=None, project=None):
        """`sw pr <script> <args>` (script is SNAPSHOT or REPLY); `project` is the leading `--project` of a call started outside
        the checkout that carries the VERSION."""
        return swcall.run(["pr", script, *args], project=project, cwd=cwd or self.tmp, env=self.env(login, **(env or {})), input=stdin)

    def snapshot_run(self, *args, login="me", env=None):
        """`sw pr snapshot` for the fixture PR; the CompletedProcess."""
        return self.run_script(SNAPSHOT, self.PR, "--repo", self.SLUG, *args, login=login, env=env)

    def snapshot(self, *args, login="me", env=None):
        """`sw pr snapshot` for the fixture PR, one JSON line parsed; the exit code must be 0."""
        r = self.snapshot_run(*args, login=login, env=env)
        self.assertEqual(r.returncode, 0, f"pr-snapshot {args}: {r.stderr}")
        lines = r.stdout.strip().split("\n")
        self.assertEqual(len(lines), 1, f"want one JSON line, got {r.stdout!r} / {r.stderr!r}")
        return json.loads(lines[0])

    def reply(self, *args, login="me", env=None, body=None, repo=True):
        """`sw pr reply` <PR> <args...> --repo SLUG (no --repo when `repo` is false). With `body`, it is written to a file and
        its path is appended to args wherever the literal "BODY" appears. Returns the CompletedProcess (the caller checks
        the exit code)."""
        args = list(args)
        if body is not None:
            f = self.tmp / "body.md"
            f.write_text(body, encoding="utf-8", newline="\n")
            args = [fixtures.posix(f) if a == "BODY" else a for a in args]
        return self.run_script(REPLY, self.PR, *args, *(["--repo", self.SLUG] if repo else []), login=login, env=env)
