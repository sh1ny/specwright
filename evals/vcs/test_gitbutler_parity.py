"""finish.sh against its frozen oracle on a GitButler repo (real `but`), native-cli-finish D9.

The oracle (evals/finish/oracle/finish.sh) is the last finish.sh before the port to `sw`; both plan the same committed and
uncommitted archives and must print the same stdout bytes with the same exit code. The printed script still calls vcs.sh by its
absolute path and names no `sw` binary. This module runs in the `vcs` suite job, the only one that installs `but`.
"""
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

import jjenv
from butenv import Scratch, require_but
from test_gitbutler_flows import BRANCH, CHANGE, GitButlerFlowCase
from vcs_test_support import stamp_version, sw_home

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("finish_fixtures", ROOT / "evals" / "finish" / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

P = "openspec"
ARCHIVED = "%s-%s" % (fx.DATE, CHANGE)
ARCHIVE_DIR = "%s/changes/archive/%s" % (P, ARCHIVED)
CHANGE_DIR = "%s/changes/%s" % (P, CHANGE)
VCS_SH = (ROOT / "skills" / "specwright-pr" / "scripts" / "vcs.sh").resolve().as_posix()


class TestGitButlerParity(GitButlerFlowCase):
    def commit_paths(self, scratch, wrap, subject, *paths):
        result = self.commit(scratch, wrap, subject + "\n", *paths)
        self.assertTrue(result["ok"], result)
        return result["commit"]

    def planned(self, scratch, wrap, repo):
        """finish.sh and the oracle plan the same archive the same way; returns (new, old) as (exit code, stdout bytes, stderr bytes)."""
        args = fx.plan_args(CHANGE, archived=ARCHIVED, branch=BRANCH)
        results = []
        for script, extra in ((fx.SCRIPT, {}), (fx.ORACLE, {"ORACLE_FIN_DIR": str(fx.ORACLE_FIN_DIR)})):
            env = self.fenced_env(scratch, wrap)
            env.update({"SPECWRIGHT_STATE_DIR": str(self.root / "state"), "PYTHONIOENCODING": "utf-8",
                        "SPECWRIGHT_HOME": str(sw_home()), **extra})
            stamp_version(repo.path)
            env["VCS_TEST_SEARCH"] = env["PATH"]
            done = subprocess.run([jjenv.find_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"', "parity",
                                   script.as_posix(), *args], cwd=str(repo.path), env=env, capture_output=True)
            results.append((done.returncode, done.stdout, done.stderr))
        return results

    def assertParity(self, pair):
        new, old = pair
        self.assertEqual(old[0], 0, old[1] + old[2])
        self.assertEqual(new[1], old[1], "stdout bytes differ between finish.sh and the oracle")
        self.assertEqual(new[0], old[0], "exit codes differ between finish.sh and the oracle")
        return json.loads(old[1].decode("utf-8"))

    def archived(self, scratch, committed):
        """feat/b beside the change branch; the change branch holds the planning commit and the archive, committed or not."""
        wrap, repo = self.start(scratch)
        self.other_agent(repo, wrap)
        repo.but("branch", "new", BRANCH)
        work = repo.path
        fx.write(work, "%s/specs/a/spec.md" % P, fx.base_spec("a"))
        fx.make_change(work, CHANGE, "DEFERRED", {"a": "New thing", "b": "B thing"}, commit_it=False)
        for rel in ("notes/z.md", "notes/deep/a/leaf.md", "notes/deep/b/leaf.md"):  # nested folders: walk order
            fx.write(work, "%s/%s" % (CHANGE_DIR, rel), rel + "\n")
        self.commit_paths(scratch, wrap, "docs(add-c): add planning artifacts", "%s/specs/a/spec.md" % P, CHANGE_DIR + "/")
        fx.archive(work, CHANGE, commit_it=False)
        if committed:
            self.commit_paths(scratch, wrap, "chore(add-c): archive change", ARCHIVE_DIR + "/", CHANGE_DIR + "/",
                              "%s/specs/a/spec.md" % P, "%s/specs/b/spec.md" % P)
        return wrap, repo

    def test_committed_archive_output_equals_oracle(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.archived(scratch, True)
            doc = self.assertParity(self.planned(scratch, wrap, repo))
            self.assertEqual(doc["mode"], "committed")

    def test_uncommitted_archive_output_equals_oracle(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.archived(scratch, False)
            doc = self.assertParity(self.planned(scratch, wrap, repo))
            self.assertEqual(doc["mode"], "uncommitted")

    def test_script_calls_vcs_sh_by_path(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.archived(scratch, True)
            pair = self.planned(scratch, wrap, repo)
            script = self.assertParity(pair)["script"]
            for verb in ("state", "commit"):
                self.assertRegex(script, r"bash '?%s'? %s\b" % (re.escape(VCS_SH), verb), script)
            self.assertNotIn("vcs.sh", script.replace(VCS_SH, ""), "vcs.sh is named by another path")
            self.assertIsNone(re.search(r"(^|[\s;&|'\"/\\])sw(\.exe)?['\"]?\s", script), "the script runs an sw binary")
            self.assertNotIn(os.sep + "sw ", script)
