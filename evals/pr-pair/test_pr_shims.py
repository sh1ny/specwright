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
import sys
import time
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


@unittest.skipIf(os.name == "nt", "platform: POSIX signals")
class TestReplySignalCleanup(ShimCase):
    """The script's `trap ... EXIT` removed the reply body file when a signal ended it; `sw pr reply` does the same."""

    def test_sigterm_during_the_post_removes_the_body_file(self):
        import signal
        tid, c = self.add_thread("rev", "please fix")
        tmpdir = self.tmp / "tmpdir"
        tmpdir.mkdir()
        hang = self.tmp / "hang"
        hang.mkdir()
        seen = self.tmp / "posting"
        gh = hang / "gh"
        gh.write_text('#!/bin/sh\nfor a in "$@"; do case $a in body=@*) echo $$ > "%s"; exec sleep 60;; esac; done\n'
                      'exec "%s" "$@"\n' % (fixtures.posix(seen), fixtures.posix(self.tmp / "bin" / "gh")),
                      encoding="utf-8", newline="\n")
        gh.chmod(0o755)
        body = self.tmp / "body.md"
        body.write_text("done\n", encoding="utf-8", newline="\n")
        env = self.env(TMPDIR=str(tmpdir))
        env["PATH"] = str(hang) + os.pathsep + env["PATH"]
        p = subprocess.Popen([bashexe.bash(), str(REPLY), str(self.PR), "thread", tid, str(c["databaseId"]),
                              fixtures.posix(body), "--repo", self.SLUG], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding="utf-8", env=env, cwd=self.tmp)
        try:
            end = time.time() + 60
            while not (seen.exists() and seen.read_text().strip()) and time.time() < end:
                self.assertIsNone(p.poll(), p.stderr.read() if p.poll() is not None else "")
                time.sleep(0.05)
            self.assertTrue(seen.exists(), "the post was never reached")
            self.assertTrue(any(tmpdir.iterdir()), "the body file exists while the post runs")
            p.send_signal(signal.SIGTERM)
            _, err = p.communicate(timeout=30)
            self.assertEqual(p.returncode, 143, err)
            self.assertEqual(list(tmpdir.iterdir()), [], "the body file is removed")
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate()
            if seen.exists():
                try:
                    os.kill(int(seen.read_text().strip()), signal.SIGKILL)
                except (ValueError, ProcessLookupError):
                    pass


@unittest.skipUnless(os.name == "nt", "platform: checks the Git Bash form of HOME, which only Windows has (assumption A3)")
class TestHomeStateBaseOnWindows(ShimCase):
    """A3 (design D9): with no SPECWRIGHT_STATE_DIR and HOME in Git Bash `/c/...` form, the sw watcher claims under
    <HOME>/.cache/specwright/watch/v2/, the directory the old script used, so an old-script watcher sees its claim."""

    def setUp(self):
        super().setUp()
        sleep = self.tmp / "bin" / "sleep"  # short naps, so the old watcher's takeover check comes quickly
        sleep.write_text(f'#!/bin/sh\nexec "{fixtures.posix(sys.executable)}" -c "import time; time.sleep(0.3)"\n',
                         encoding="utf-8", newline="\n")
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.procs = []
        self.addCleanup(self._reap)

    def _reap(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.communicate()

    def start(self, script, **extra):
        env = self.env(HOME=fixtures.msys(self.home), **extra)
        env.pop("SPECWRIGHT_STATE_DIR")
        p = subprocess.Popen([bashexe.bash(), str(script), str(self.PR), "--repo", self.SLUG, "--wait", "--interval", "1",
                              "--timeout", "60"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             encoding="utf-8", env=env, cwd=self.tmp)
        self.procs.append(p)
        return p

    def claims(self):
        base = self.home / ".cache" / "specwright" / "watch" / "v2"
        return sorted(p.name for p in base.rglob("*") if p.is_file()) if base.is_dir() else []

    def wait_for(self, cond, what):
        end = time.time() + 60
        while time.time() < end:
            if cond():
                return
            time.sleep(0.05)
        self.fail(f"timed out waiting for {what}; claims: {self.claims()}")

    def test_home_default_state_base_is_shared_with_the_old_script(self):
        new = self.start(SNAPSHOT)
        self.wait_for(lambda: self.claims(), "the sw watcher's claim under <HOME>/.cache/specwright/watch/v2/")
        first = self.claims()
        self.assertEqual(len(first), 1, first)
        self.assertTrue(first[0].startswith("1-"), first)
        old = self.start(ORACLE / "pr-snapshot.sh", ORACLE_SW_DIR=fixtures.posix(snapfix.SCRIPTS))
        _, err_new = new.communicate(timeout=90)
        self.assertEqual(new.returncode, 4, err_new)  # the old watcher saw the claim and took a higher one
        self.assertIn("took over", err_new)
        self.assertTrue(any(c.startswith("2-") for c in self.claims()), self.claims())
        old.kill()
        old.communicate()


if __name__ == "__main__":
    unittest.main()
