"""pr-snapshot.sh and pr-reply.sh are shims (ADR 0028, native-cli-pr-io D10): each finds the project's sw with sw-path.sh and
runs `sw pr snapshot|reply --args-stdin`, handing it this directory, this bash and the whole command line as NUL-terminated
records. The PR logic is pinned by test_pr_snapshot.py, test_pr_reply.py and test_parity.py. These tests cover what the shims
add: how they find `sw`, what they do without one, and that the text of a query reaches gh whole.

They run the real shims against the tree's sw through the test home (snapfix.SnapCase sets SPECWRIGHT_HOME and stamps the
project).

Run: python -m unittest discover evals/pr-pair -p test_pr_shims.py
"""
import json
import os
import subprocess
import unittest

import snapfix
from snapfix import REPLY, ROOT, SNAPSHOT, SnapCase, fixtures
import bashexe  # noqa: E402

STOP = "sw missing or mismatched: rerun the install prompt"
ORACLE = ROOT / "evals" / "pr-pair" / "oracle"


def setUpModule():
    snapfix.banner()


class ShimCase(SnapCase):
    def no_sw_env(self):
        """An environment whose test home holds no sw."""
        home = self.tmp / "empty-home"
        home.mkdir(exist_ok=True)
        return {"SPECWRIGHT_HOME": str(home)}

    def stop_document(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_missing"), doc)
        self.assertTrue(doc["message"].startswith(STOP), doc)
        self.assertIn(STOP, result.stderr)
        self.assertEqual(self.gh_calls(), [], "no gh call ran")
        return doc


class TestRunsSw(ShimCase):
    def test_snapshot_runs_sw(self):
        tid, c = self.add_thread("rev", "please fix the loop")
        snap = self.snapshot()
        self.assertEqual([t["id"] for t in snap["threads"]], [tid])
        thread = snap["threads"][0]
        self.assertEqual(thread["rev"], f"{c['databaseId']}@{c['createdAt']}")
        self.assertEqual(thread["comments"][0]["body"], "please fix the loop")

    def test_reply_runs_sw(self):
        tid, c = self.add_thread("rev", "please fix")
        r = self.reply("thread", tid, c["databaseId"], "BODY", "--resolve", body="done\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        thread = self.st()["repos"]["o/n"]["pulls"][0]["threads"][0]
        self.assertTrue(thread["isResolved"])
        self.assertEqual(len(thread["comments"]), 2)
        self.assertEqual(thread["comments"][1]["body"], f"done\n\n\n<!-- specwright:handled {tid} resolve -->\n")

    def test_reply_refusal_keeps_its_exit_status(self):
        r = self.reply("comment", "IC_1", "missing.md")
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertIn("missing.md", r.stderr)
        self.assertEqual(self.gh_calls(), [], "no gh call ran")


class TestWithoutSw(ShimCase):
    def test_reply_without_sw_posts_nothing(self):
        tid, c = self.add_thread("rev", "please fix")
        r = self.reply("comment", "IC_1", "BODY", body="done", env=self.no_sw_env())
        self.stop_document(r)
        self.assertEqual(self.st()["repos"]["o/n"]["pulls"][0]["threads"][0]["comments"][0]["body"], "please fix")
        self.assertEqual(len(self.st()["repos"]["o/n"]["pulls"][0]["threads"][0]["comments"]), 1)

    def test_watch_without_sw_creates_no_claim(self):
        r = self.snapshot_run("--wait", env=self.no_sw_env())
        self.stop_document(r)
        self.assertFalse(self.state_dir.exists(), "no state directory, so no claim file")

    def test_snapshot_without_sw_runs_no_gh(self):
        self.stop_document(self.snapshot_run(env=self.no_sw_env()))

    def test_no_python(self):
        empty = self.tmp / "no-tools"
        empty.mkdir()
        for script, name in ((SNAPSHOT, "pr-snapshot.sh"), (REPLY, "pr-reply.sh")):
            with self.subTest(script=name):
                env = {**self.env(), "PATH": str(empty)}
                r = subprocess.run([bashexe.bash(), str(script), "7"], cwd=self.tmp, env=env, capture_output=True, text=True)
                self.assertEqual((r.returncode, r.stdout), (2, ""), r.stderr)
                self.assertEqual(r.stderr, f"{name}: no_python: needs python 3.8+ for its bounded gh calls\n")
        self.assertEqual(self.gh_calls(), [], "sw did not run")


class TestReviewerConfig(ShimCase):
    def test_bad_reviewer_config_exits_2_before_gh(self):
        cfg = self.tmp / "bad.json"
        cfg.write_text("{not json", encoding="utf-8", newline="\n")
        r = self.snapshot_run("--reviewer-config", fixtures.posix(cfg))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertIn("bad.json", r.stderr)
        self.assertEqual(self.gh_calls(), [], "no gh call ran")


class TestQueryTextArrivesWhole(ShimCase):
    """Windows: a native command line cuts or expands what MSYS parses (constraint C16). The query and the jq program travel as
    records on stdin; this checks the fake gh received them byte for byte, the program's `…` and `{`, `*`, `$` included."""

    @staticmethod
    def heredoc(name, tag):
        text = (ORACLE / name).read_text(encoding="utf-8")
        body = text.split(f"<<'{tag}' || true\n", 1)[1].split(f"\n{tag}\n", 1)[0]
        return body.strip()

    def test_snapshot_query_and_jq_arrive_whole(self):
        self.add_thread("rev", "please fix")
        self.snapshot()
        calls = [c for c in self.gh_calls() if any(a.startswith("query=") and "statusCheckRollup" in a for a in c)]
        self.assertEqual(len(calls), 1)
        argv = calls[0]
        query = self.heredoc("pr-snapshot.sh", "GQL")
        shape = self.heredoc("pr-snapshot.sh", "JQ")
        self.assertIn(f"query={query}", argv)
        jq = argv[argv.index("--jq") + 1]
        self.assertTrue(jq.startswith("def cfg:"), jq[:40])
        self.assertTrue(jq.endswith("\n" + shape), "the jq program arrived whole")
        self.assertIn("…[truncated, see url]", jq)


if __name__ == "__main__":
    unittest.main()
