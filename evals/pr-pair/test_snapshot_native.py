"""`sw pr snapshot` runs no script, no interpreter and no child `sw` for what it can do itself (native-cli-internal-calls D3, D4, D5).

Every test hands the built `sw` (SPECWRIGHT_SW) the scripts-directory handoff of `pr-snapshot.sh` directly (`sw pr snapshot
--args-stdin`: the scripts directory, the bash and the script's own arguments as NUL-terminated records), against the fake `gh`.
The shim `pr-snapshot.sh` itself still checks for Python until `native-cli-retire-scripts`, so none of these goes through it.

- A bad reviewer config is refused in the process itself: the handoff names a bash that does not exist, so a child started
  for the check (a tool run goes through bash) could not even start and its error would reach stderr instead of the config's.
- With failing `python` and `python3` first on PATH, and recording `as.sh`, `vcs.sh`, `pr-pair.sh`, `sw-path.sh` in the handoff's
  scripts directory (`evals/vcs/sentinels.py`), a snapshot with a reviewer config is printed whole and nothing recorded a run.
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
from snapfix import SCRIPTS, T0, SnapCase, fixtures, rev
import bashexe  # noqa: E402

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
        """Recording script sentinels in a handoff scripts directory and failing interpreters in a directory for PATH."""
        sent = sentinels.install(self.tmp / "sentinel-scripts", self.tmp / "sentinel-bin", self.tmp / "sentinel-log")
        self.addCleanup(sent.clear)
        sent.probe(self, env=self.env())
        return sent

    def handoff_run(self, *args, scripts=SCRIPTS, bash=None, path_first=None, env=None):
        """`sw pr snapshot --args-stdin` for the fixture PR, through the handoff `pr-snapshot.sh` writes; the CompletedProcess."""
        records = [str(scripts), str(bash or bashexe.bash()), *map(str, args)]
        payload = b"".join(r.encode("utf-8") + b"\0" for r in records)
        run_env = self.env(**(env or {}))
        if path_first:
            run_env["PATH"] = str(path_first) + os.pathsep + run_env["PATH"]
        return subprocess.run([self.sw, "pr", "snapshot", "--args-stdin"], input=payload, capture_output=True,
                              env=run_env, cwd=self.tmp, timeout=120)

    def text(self, data):
        return data.decode("utf-8")


class TestReviewerConfigWithoutChild(NativeSnapshotCase):
    def test_bad_config_checked_without_child(self):
        """The config is checked in the process itself, before any gh call: one `reviewers.py:` line about the JSON and exit 2,
        with a bash that cannot start (a child `sw` for the check runs through bash, so it would have failed to start)."""
        cfg = self.tmp / "cfg.json"
        cfg.write_text("{not json", encoding="utf-8", newline="\n")
        r = self.handoff_run(self.PR, "--repo", self.SLUG, "--reviewer-config", fixtures.posix(cfg),
                             bash=self.tmp / "no-such-bash")
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

    def test_retrofitted_snapshot_runs_no_script_or_python(self):
        """With recording sentinels for the shipped scripts in the handoff's scripts directory as well, none recorded a run."""
        sent = self.sentinels()
        r = self.reported_snapshot(scripts=sent.scripts, path_first=sent.bin, env=sent.env)
        self.assert_printed(r)
        self.assertEqual(sent.recorded(), [], "no sentinel recorded a run")


class TestFullNotFound(NativeSnapshotCase):
    """`--full` returns 1 for a `not_found` document however the jq program spaced it or ordered its members."""

    def stub_gh(self, document):
        stub = self.tmp / "full-bin"
        stub.mkdir(exist_ok=True)
        with (stub / "gh").open("w", encoding="utf-8", newline="\n") as stream:
            stream.write('#!/bin/sh\nprintf "%s\\n" "$SW_FULL_DOCUMENT"\n')
        (stub / "gh").chmod(0o755)
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


if __name__ == "__main__":
    unittest.main()
