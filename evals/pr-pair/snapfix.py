"""Shared fixture for tests of pr-snapshot.sh and pr-reply.sh against the fake gh (evals/fakes/gh.py).

SnapCase gives each test a temp dir with the fake gh on PATH, a state file, an empty SPECWRIGHT_STATE_DIR, and helpers that
add threads, comments, reviews and edits at a fake-clock time and advance the clock. The scripts run through `bash`.

The fake hands the shipped --jq filters to an external evaluator: gojq when it is on PATH (what gh itself embeds), else jq.
JQ_NAME says which one; `banner()` prints it, so a test run shows what evaluated the filters. A test needing neither is skipped.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "skills" / "specwright-pr" / "scripts"
SNAPSHOT, REPLY = SCRIPTS / "pr-snapshot.sh", SCRIPTS / "pr-reply.sh"
sys.path.insert(0, str(ROOT / "evals" / "git-workflow"))
import fixtures  # noqa: E402

sys.path.insert(0, str(ROOT / "evals" / "fakes"))
import gh as fake_gh  # noqa: E402

JQ = shutil.which("gojq") or shutil.which("jq")
JQ_NAME = Path(JQ).stem if JQ else None
T0 = "2026-10-10T10:00:00Z"


def banner():
    """Name the filter evaluator in the test output (call from setUpModule)."""
    print(f"\n[snapfix] --jq evaluator: {JQ_NAME or 'none (tests skipped)'}{' = ' + JQ if JQ else ''}", file=sys.stderr)


@unittest.skipUnless(JQ, "needs gojq or jq on PATH")
class SnapCase(unittest.TestCase):
    maxDiff = None
    SLUG, PR = "o/n", 7

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        fixtures.install_fake_gh(self.tmp)
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
        return json.loads(self.gh_state.read_text(encoding="utf-8"))

    def mutate(self, fn):
        """Load the fake's state, apply fn(state), save it. Returns fn's result."""
        st = json.loads(self.gh_state.read_text(encoding="utf-8")) if self.gh_state.exists() else {}
        out = fn(st)
        self.gh_state.write_text(json.dumps(st, indent=2), encoding="utf-8", newline="\n")
        return out

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

    def gh_calls(self):
        if not self.gh_log.exists():
            return []
        return [json.loads(l)["argv"] for l in self.gh_log.read_text(encoding="utf-8").splitlines()]

    # ---- running the scripts -----------------------------------------------------------------------------
    def env(self, login="me", **extra):
        """Environment with the fake gh first on PATH; GH_TOKEN picks the viewer (login None = the state's default user)."""
        e = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST")}
        e.update({"PATH": str(self.tmp / "bin") + os.pathsep + e.get("PATH", ""),
                  "FAKE_GH_STATE": str(self.gh_state), "FAKE_GH_LOG": str(self.gh_log), "FAKE_GH_JQ": JQ,
                  "SPECWRIGHT_STATE_DIR": str(self.state_dir), "PYTHONIOENCODING": "utf-8", "GIT_TERMINAL_PROMPT": "0"})
        if login:
            e["GH_TOKEN"] = self.st()["tokens"][login]
        e.update(self.extra_env)
        e.update(extra)
        return e

    def run_script(self, script, *args, login="me", env=None, cwd=None, stdin=None):
        return subprocess.run(["bash", str(script), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                              env=self.env(login, **(env or {})), cwd=cwd or self.tmp, input=stdin)

    def snapshot_run(self, *args, login="me", env=None):
        """pr-snapshot.sh for the fixture PR; the CompletedProcess."""
        return self.run_script(SNAPSHOT, self.PR, "--repo", self.SLUG, *args, login=login, env=env)

    def snapshot(self, *args, login="me", env=None):
        """pr-snapshot.sh for the fixture PR, one JSON line parsed; the exit code must be 0."""
        r = self.snapshot_run(*args, login=login, env=env)
        self.assertEqual(r.returncode, 0, f"pr-snapshot {args}: {r.stderr}")
        lines = r.stdout.strip().splitlines()
        self.assertEqual(len(lines), 1, f"want one JSON line, got {r.stdout!r} / {r.stderr!r}")
        return json.loads(lines[0])

    def reply(self, *args, login="me", env=None, body=None):
        """pr-reply.sh <PR> <args...> --repo SLUG. With `body`, it is written to a file and its path is appended to args
        wherever the literal "BODY" appears. Returns the CompletedProcess (the caller checks the exit code)."""
        args = list(args)
        if body is not None:
            f = self.tmp / "body.md"
            f.write_text(body, encoding="utf-8", newline="\n")
            args = [fixtures.posix(f) if a == "BODY" else a for a in args]
        return self.run_script(REPLY, self.PR, *args, "--repo", self.SLUG, login=login, env=env)
