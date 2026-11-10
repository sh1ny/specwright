"""vcs.sh is a shim: it resolves the project's sw with sw-path.sh and runs `sw vcs` (design D1, D2, D6).

The tests run the real shim against the tree's sw through the test home (design D9). Where a test needs another resolver
outcome it runs a copy of the scripts directory.

Run: python -m unittest evals/vcs/test_shim.py
"""
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

import gitlog
import jjenv
from test_sw_scripts import write_script
from vcs_test_support import SCRIPTS, STAMP, VcsTestCase, bash_run, sw_home, tree_version

STOP = "sw missing or mismatched: rerun the install prompt"
RECORDER = r"""#!/usr/bin/env bash
printf 'args:' >> "$RESOLVER_LOG"
for a in "$@"; do printf ' %s' "$a" >> "$RESOLVER_LOG"; done
printf '\n' >> "$RESOLVER_LOG"
[ -f "$2/openspec/.specwright/VERSION" ] && echo version-found >> "$RESOLVER_LOG"
[ -e "$2/.git" ] && echo git-entry >> "$RESOLVER_LOG"
printf 'sw missing or mismatched: rerun the install prompt\nrecorder stop\n' >&2
exit 1
"""


class ShimCase(VcsTestCase):
    def setUp(self):
        super().setUp()
        self.shim = gitlog.install(self.root / "gitshim", real_git=jjenv.real_git(), log_path=self.root / "git.jsonl")
        self.env = self.shim.env

    def copy_scripts(self):
        dest = self.root / "scripts"
        shutil.copytree(SCRIPTS, dest, ignore=shutil.ignore_patterns("__pycache__"))
        return dest

    def run_shim(self, scripts, *args, cwd=None, env=None):
        """Run `bash <scripts>/vcs.sh args` with the test home and the logging git first on PATH."""
        shim_env = {"SPECWRIGHT_HOME": str(sw_home()), **self.shim.env, **(env or {})}
        return bash_run([(scripts / "vcs.sh").as_posix(), *map(str, args)], cwd=cwd or self.repo, env=shim_env,
                        shim=self.shim.path, stamp=False)

    def stop_document(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_missing"), doc)
        self.assertTrue(doc["message"].startswith(STOP), doc)
        self.assertIn(STOP, result.stderr)
        self.assertEqual(self.shim.calls(), [], "no git command ran")
        return doc


class TestShim(ShimCase):
    def test_matching_sw_runs_sw_vcs(self):
        done, _ = self.invoke("state")
        self.assertEqual((done["ok"], done["backend"], done["on_main"]), (True, "git", True), done)

    def test_project_found_from_subdirectory_without_git(self):
        scripts = self.copy_scripts()
        write_script(scripts / "sw-path.sh", RECORDER)
        sub = self.repo / "sub" / "dir"
        sub.mkdir(parents=True)
        log = self.root / "resolver.log"
        result = self.run_shim(scripts, "state", "--repo", sub.as_posix(), "--role", "code", env={"RESOLVER_LOG": log.as_posix()})
        self.stop_document(result)
        lines = log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0].split()[:2], ["args:", "--code"], lines)
        self.assertEqual(lines[1:], ["version-found", "git-entry"], "the resolver was handed the repo, not sub/dir")

    def test_arguments_reach_sw_unchanged(self):
        self.git(self.repo, "checkout", "-b", "feat/a")
        named = self.repo / "dir with space" / "a b.txt"
        named.parent.mkdir()
        named.write_text("named\n", encoding="utf-8")
        (self.repo / "other.txt").write_text("other\n", encoding="utf-8")
        message = self.root / "message.txt"
        message.write_text("feat(a): add the named file\n", encoding="utf-8", newline="\n")
        done, _ = self.invoke("commit", "--branch", "feat/a", "--message-file", message, "--", "dir with space/a b.txt")
        self.assertTrue(done["ok"], done)
        files = self.git(self.repo, "show", "--name-only", "--format=", "HEAD").stdout.splitlines()
        self.assertEqual(files, ["dir with space/a b.txt"])

    def test_fence_refusal_keeps_exit_3(self):
        # A remote URL that carries credentials is refused by the in-process fence before any gh call.
        self.git(self.repo, "remote", "add", "origin", "https://tok@github.com/o/r.git")
        self.git(self.repo, "checkout", "-b", "feat/a")
        refused, _ = self.invoke("push", "--branch", "feat/a", "--login", "KintsugiBot", expected=3)
        self.assertEqual((refused["ok"], refused["error"]), (False, "fence_failed"), refused)
        self.assertNotIn("tok@", refused["message"])

    def test_binary_missing_stops_sw_missing(self):
        home = self.root / "empty-home"
        home.mkdir()
        result = self.run_shim(SCRIPTS, "state", "--repo", self.repo, "--role", "code", env={"SPECWRIGHT_HOME": str(home)})
        doc = self.stop_document(result)
        self.assertIn(".specwright/bin/%s/sw" % tree_version(), doc["message"].replace("\\", "/"))

    def test_interface_mismatch_creates_no_branch(self):
        scripts = self.copy_scripts()
        path = scripts / "sw-path.sh"
        text = path.read_text(encoding="utf-8")
        self.assertIn("SW_INTERFACE=1\n", text)
        write_script(path, text.replace("SW_INTERFACE=1\n", "SW_INTERFACE=2\n", 1))
        result = self.run_shim(scripts, "branch-create", "--repo", self.repo, "--role", "code", "--branch", "feat/a")
        doc = self.stop_document(result)
        self.assertIn("interface", doc["message"])
        self.assertEqual(self.git(self.repo, "branch", "--list", "feat/a").stdout.strip(), "")

    def test_no_version_stops_sw_missing(self):
        (self.repo / STAMP).unlink()
        result = self.run_shim(SCRIPTS, "state", "--repo", self.repo, "--role", "code")
        doc = self.stop_document(result)
        self.assertIn("no installed version found", doc["message"])

    def test_no_python_keeps_no_python_document(self):
        empty = self.root / "no-tools"
        empty.mkdir()
        done = subprocess.run([jjenv.find_bash(), (SCRIPTS / "vcs.sh").as_posix(), "state", "--repo", str(self.repo),
                               "--role", "code"], env={**os.environ, "PATH": str(empty)}, cwd=self.repo,
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertEqual(done.stdout, '{"ok":false,"error":"no_python","message":"vcs.sh needs python 3.8+"}\n')

    def test_unknown_subcommand_is_usage(self):
        done, _ = self.invoke("frobnicate", expected=2)
        self.assertEqual((done["ok"], done["error"]), (False, "usage"), done)


if __name__ == "__main__":
    unittest.main()
