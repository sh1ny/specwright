"""`sw pr snapshot` runs no script, no interpreter and no child `sw` for what it can do itself (native-cli-internal-calls D3, D4, D5).

Every test runs the built `sw` (SPECWRIGHT_SW) as `sw pr snapshot <args>` through evals/swcall.py, against the fake `gh`.

- A bad reviewer config is refused in the process itself: no child is started for the check, so the config's own error
  reaches stderr.
- With failing `python` and `python3` first on PATH (`evals/vcs/sentinels.py`), a snapshot with a reviewer config is printed
  whole and nothing recorded a run.
- `--full` reads the `not_found` document by parsing it, so a gh `--jq` that prints a space after `:` or `,` reads the same.

Run: python -m unittest discover -s evals/pr-pair -t evals/pr-pair -p test_snapshot_native.py
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import snapfix
from snapfix import REPLY, SNAPSHOT, T0, SnapCase, fixtures, rev
import bashexe  # noqa: E402
import fakeexe  # noqa: E402
import swcall  # noqa: E402  (snapfix puts evals/ on sys.path through vcs_test_support)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vcs"))
import sentinels  # noqa: E402


def setUpModule():
    snapfix.banner()


class NativeSnapshotCase(SnapCase):
    def setUp(self):
        super().setUp()
        self.sw = snapfix.vcs_test_support.swharness.require_sw()
        snapfix.vcs_test_support.sw_home()  # the SPECWRIGHT_HOME that SnapCase.env names

    def sentinels(self):
        """Failing recording interpreters in a directory for PATH."""
        sent = sentinels.install(self.tmp / "sentinel-bin", self.tmp / "sentinel-log")
        self.addCleanup(sent.clear)
        sent.probe(self, env=self.env())
        return sent

    def handoff_run(self, *args, path_first=None, env=None):
        """`sw pr snapshot` for the fixture PR, entered directly (evals/swcall.py); the CompletedProcess of bytes."""
        run_env = self.env(**(env or {}))
        if path_first:
            run_env["PATH"] = str(path_first) + os.pathsep + run_env["PATH"]
        return swcall.run(["pr", "snapshot", *args], cwd=self.tmp, env=run_env, text=False)

    def text(self, data):
        return data.decode("utf-8")


class TestReviewerConfigWithoutChild(NativeSnapshotCase):
    def test_bad_config_checked_without_child(self):
        """The config is checked in the process itself, before any gh call: one `reviewers.py:` line about the JSON and exit 2."""
        cfg = self.tmp / "cfg.json"
        cfg.write_text("{not json", encoding="utf-8", newline="\n")
        r = self.handoff_run(self.PR, "--repo", self.SLUG, "--reviewer-config", fixtures.posix(cfg))
        err = self.text(r.stderr)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(r.stdout, b"")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertTrue(err.startswith("reviewers.py: "), err)
        self.assertIn("cfg.json", err)
        self.assertIn("not valid JSON", err)
        self.assertEqual(self.gh_calls(), [], "no gh call ran")


class TestNoInterpreter(NativeSnapshotCase):
    def reported_snapshot(self, **kwargs):
        self.add_activity("a" * 40, T0)
        self.advance(30)
        self.add_comment("genrev", "looks good to me")
        args = [self.PR, "--repo", self.SLUG, *self.cfg(rev("genrev"), rev("silent", role="advisory", timeout=3600))]
        return self.handoff_run(*args, **kwargs)

    def assert_printed(self, r):
        err = self.text(r.stderr)
        self.assertNotIn("no_python", err)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        snap = json.loads(self.text(r.stdout))
        self.assertEqual({x["login"]: x["state"] for x in snap["reviewers"]}, {"genrev": "reported", "silent": "waiting"})
        self.assertRegex(snap["reviewer_config"], "^[0-9a-f]{64}$")

    def test_snapshot_without_python(self):
        """The snapshot and its reviewer states are printed, exit 0, neither interpreter ran, and stderr has no `no_python`."""
        sent = self.sentinels()
        r = self.reported_snapshot(path_first=sent.bin, env=sent.env)
        self.assert_printed(r)
        self.assertEqual(sent.recorded(), [], "neither interpreter ran")


class TestStoreEvaluator(NativeSnapshotCase):
    """A store-started snapshot runs from the planning store, which holds no VERSION; the evaluator child it starts runs
    in that directory too and checks no project version (native-cli "Commands that check no project version")."""

    def direct_run(self, *args, env=None):
        """`<sw> --project <code> pr snapshot ...` with ordinary arguments, the store as the working directory."""
        code, store = self.tmp / "code", self.tmp / "store"
        for d in (code, store):
            d.mkdir(exist_ok=True)
        snapfix.vcs_test_support.stamp_version(code)
        return subprocess.run([self.sw, "--project", fixtures.posix(code), "pr", "snapshot", str(self.PR), "--repo", self.SLUG,
                               *map(str, args)], capture_output=True, env=self.env(**(env or {})), cwd=store, timeout=120)

    def test_store_snapshot_evaluator_has_no_version_check(self):
        self.add_activity("a" * 40, T0)
        self.advance(30)
        self.add_comment("genrev", "looks good to me")
        r = self.direct_run(*self.cfg(rev("genrev"), rev("silent", role="advisory", timeout=3600)))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(b"sw_mismatch", r.stdout + r.stderr)
        snap = json.loads(self.text(r.stdout))
        self.assertEqual({x["login"]: x["state"] for x in snap["reviewers"]}, {"genrev": "reported", "silent": "waiting"})

    def test_store_snapshot_still_kills_a_backtracking_evaluator(self):
        self.add_activity("a" * 40, T0)
        self.advance(30)
        self.add_comment("genrev", "a" * 64 + "b")
        r = self.direct_run(*self.cfg(rev("genrev", ignore="(a+)+$")), env={"SPECWRIGHT_NET_DEADLINE": "10"})
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout.strip(), b"")
        self.assertIn("bounded: deadline_exceeded: reviewers.py python3", self.text(r.stderr).splitlines())
        self.assertNotIn(b"sw_mismatch", r.stderr)


class TestFullNotFound(NativeSnapshotCase):
    """`--full` returns 1 for a `not_found` document however the jq program spaced it or ordered its members."""

    def stub_gh(self, document):
        stub = self.tmp / "full-bin"
        stub.mkdir(exist_ok=True)
        # the document has quotes, which a `.cmd` launcher refuses, so sw (PATHEXT only on Windows, D9) gets an `.exe`
        fakeexe.write_fake(stub / "gh", '#!/bin/sh\nprintf "%s\\n" "$SW_FULL_DOCUMENT"\n', exe=True)
        return stub

    def read_full(self, document):
        stub = self.stub_gh(document)
        r = self.handoff_run("--full", "PRRC_1=", path_first=stub, env={"SW_FULL_DOCUMENT": document})
        return r.returncode, self.text(r.stdout), self.text(r.stderr)

    def test_full_not_found_exits_1_in_compact_and_spaced_form(self):
        for name, document in (("compact", '{"ok":false,"error":"not_found"}'),
                               ("spaced", '{"ok": false, "error": "not_found"}'),
                               ("reordered, spaced", '{"error": "not_found", "ok": false}')):
            with self.subTest(form=name):
                code, out, err = self.read_full(document)
                self.assertEqual((code, out), (1, document + "\n"), err)

    def test_full_found_exits_0_and_prints_the_document_unchanged(self):
        for name, document in (("compact", '{"ok":true,"id":"PRRC_1=","body":"error: not_found"}'),
                               ("spaced", '{"ok": true, "id": "PRRC_1=", "body": "\\"error\\": \\"not_found\\""}')):
            with self.subTest(form=name):
                code, out, err = self.read_full(document)
                self.assertEqual((code, out), (0, document + "\n"), err)


class TestProjectSelector(SnapCase):
    """native-cli-internal-calls D6: one leading `--project <dir>` picks the project whose version `sw` checks.

    `self.tmp` holds the stamped version; `code` is another stamped project, `store` has none."""

    def setUp(self):
        super().setUp()
        snapfix.vcs_test_support.sw_home()
        self.code = self.tmp / "code"
        self.store = self.tmp / "store"
        for d in (self.code, self.store):
            d.mkdir()
        snapfix.vcs_test_support.stamp_version(self.code)

    def test_store_snapshot_selects_code_project(self):
        tid, _ = self.add_thread("rev", "please fix the loop")
        r = self.run_script(SNAPSHOT, self.PR, "--repo", self.SLUG, cwd=self.store, project=fixtures.posix(self.code))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        snap = json.loads(r.stdout)
        self.assertEqual([t["id"] for t in snap["threads"]], [tid])
        self.assertTrue(self.gh_calls(), "the snapshot asked GitHub")
        for argv in self.gh_calls():
            self.assertNotIn("--project", argv)

    def test_store_reply_selects_code_project(self):
        item = self.add_comment("rev", "a note")
        body = self.tmp / "body.md"
        body.write_text("done" + chr(10), encoding="utf-8", newline=chr(10))
        r = self.run_script(REPLY, self.PR, "comment", item["node_id"], fixtures.posix(body), "--repo", self.SLUG,
                            cwd=self.store, project=fixtures.posix(self.code))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        comments = self.st()["repos"][self.SLUG]["comments"][str(self.PR)]
        self.assertEqual(len(comments), 2, "one reply was posted")
        self.assertIn("specwright:handled", comments[1]["body"])
        self.assertTrue(self.gh_calls(), "the reply reached GitHub")
        for argv in self.gh_calls():
            self.assertNotIn("--project", argv)

    def test_missing_selected_binary_has_no_fallback(self):
        """A project at a version no binary serves is a `sw_mismatch`: the other binary is not used and no gh call runs."""
        other = self.tmp / "other"
        other.mkdir()
        (other / "openspec" / ".specwright").mkdir(parents=True)
        (other / "openspec" / ".specwright" / "VERSION").write_text("999.0.0" + chr(10), encoding="utf-8")
        r = self.run_script(SNAPSHOT, self.PR, "--repo", self.SLUG, project=fixtures.posix(other))  # cwd's project has one
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_mismatch"), doc)
        self.assertEqual(self.gh_calls(), [], "no gh call ran, the other binary was not used")

    def test_malformed_project_prefix_is_usage(self):
        for command in ("snapshot", "reply"):
            for prefix in (["--project"], ["--project", ""], ["--project", fixtures.posix(self.code), "--project", "x"]):
                with self.subTest(command=command, prefix=prefix):
                    r = swcall.run([*prefix, "pr", command], cwd=self.store, env=self.env())
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertIn("usage", r.stderr.lower())
        self.assertEqual(self.gh_calls(), [])


if __name__ == "__main__":
    unittest.main()
