"""finish.sh is a shim (ADR 0028, design D7): it finds the project's sw with sw-path.sh and runs
`sw finish --args-stdin`, handing it this directory, this bash and the whole command line as NUL-terminated records.

The tests run the real shim against the tree's sw through the test home (native-cli-finish D9). Where a test needs
another resolver outcome it runs a copy of the two skills' scripts directories, laid out the way the shim expects them.

Run: python -m unittest evals/finish/test_finish_shim.py
"""
import importlib.util
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
sys.path.append(str(ROOT / "evals" / "vcs"))
import gitlog  # noqa: E402
import jjenv  # noqa: E402
import vcs_test_support  # noqa: E402
from vcs_test_support import STAMP, bash_run, sw_home, stamp_version, tree_version  # noqa: E402

_spec = importlib.util.spec_from_file_location("finish_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

P = "openspec"
BRANCH = "bugfix/add-x"
STOP = "sw missing or mismatched: rerun the install prompt"
NO_PYTHON = '{"ok":false,"error":"no_python","message":"finish.sh needs python 3.8+"}\n'
FINISH_SCRIPTS = ROOT / "skills" / "specwright-finish" / "scripts"
PR_SCRIPTS = ROOT / "skills" / "specwright-pr" / "scripts"


class ShimCase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="swfs-"))
        self.addCleanup(fx.rmtree, self.tmp)
        self.shim = gitlog.install(self.tmp / "gitshim", real_git=jjenv.real_git(), log_path=self.tmp / "git.jsonl")
        self.work = fx.make_repo(self.tmp / "main")

    def archived(self, work, name="add-x", prefix=P, branch=BRANCH):
        """On <branch>: the change `name` planned (DEFERRED) and archived in one commit."""
        fx.git(work, "checkout", "-q", "-b", branch)
        fx.make_change(work, name, "DEFERRED", {"a": "New thing"}, prefix=prefix)
        return fx.archive(work, name, prefix=prefix, commit_it=True)

    def copy_scripts(self):
        """Copies of both scripts directories under <tmp>/skills/<skill>/scripts; returns the finish.sh copy."""
        dest = self.tmp / "skills"
        for skill in ("specwright-finish", "specwright-pr"):
            shutil.copytree(ROOT / "skills" / skill / "scripts", dest / skill / "scripts",
                            ignore=shutil.ignore_patterns("__pycache__"))
        return dest / "specwright-finish" / "scripts" / "finish.sh"

    def run_shim(self, *args, cwd=None, env=None, script=None, home=None, shim_dir=None):
        shim_env = {"SPECWRIGHT_HOME": str(home or sw_home()), **self.shim.env, **(env or {})}
        return bash_run([(script or fx.SCRIPT).as_posix(), *map(str, args)], cwd=cwd or self.work, env=shim_env,
                        shim=shim_dir or self.shim.path, stamp=False)

    def plan(self, change="add-x", *, prefix=P, dir_=None, code=None, archived=None, main="main"):
        args = (["--dir", str(dir_)] if dir_ else []) + ["undo-archive-plan", "--change", change, "--archived-name",
                                                           archived or f"{fx.DATE}-{change}", "--prefix", prefix,
                                                           "--main", main]
        return args + (["--code", str(code)] if code is not None else [])

    def document(self, result, code=0):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def stop_document(self, result):
        doc = self.document(result, 1)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_missing"), doc)
        self.assertTrue(doc["message"].startswith(STOP), doc)
        self.assertIn(STOP, result.stderr)
        self.assertNotIn("script", doc)
        self.assertEqual(self.shim.calls(), [], "a git command ran")
        return doc

    def no_git_calls(self):
        self.shim.log_path.unlink(missing_ok=True)


class TestPlanRunsSw(ShimCase):
    def test_plan_runs_sw(self):
        self.archived(self.work)
        doc = self.document(self.run_shim(*self.plan()))
        self.assertIs(doc["ok"], True, doc)
        self.assertEqual(doc["mode"], "committed")
        self.assertTrue(doc["script"].startswith("set -euo pipefail"), doc["script"][:60])

    def test_prefix_with_space_and_non_ascii_change(self):
        prefix, name = "my plans/openspec", "add-éx"
        work = fx.make_repo(self.tmp / "space", prefix=prefix)
        self.archived(work, name, prefix=prefix)
        doc = self.document(self.run_shim(*self.plan(name, prefix=prefix), cwd=work))
        self.assertIs(doc["ok"], True, doc)
        self.assertEqual([m["name"] for m in doc["members"]], [name])
        self.assertIn(f"undo archive of {name}", doc["script"])
        self.assertIn(f"{prefix}/changes/archive/{fx.DATE}-{name}", doc["script"])

    @unittest.skipUnless(os.name == "nt", "platform: Git Bash path forms are Windows-only")
    def test_git_bash_dir_on_windows(self):
        self.archived(self.work)
        bash_form = subprocess.run(["cygpath", "-u", str(self.work)], capture_output=True, text=True).stdout.strip()
        self.assertTrue(bash_form.startswith("/"), bash_form)
        drive = self.run_shim(*self.plan(dir_=Path(self.work).as_posix()), cwd=self.tmp)
        bash = self.run_shim(*self.plan(dir_=bash_form), cwd=self.tmp)
        self.assertEqual(bash.returncode, 0, bash.stdout + bash.stderr)
        self.assertNotIn("not_a_repo", bash.stdout)
        self.assertEqual(json.loads(bash.stdout), json.loads(drive.stdout))

    @unittest.skipUnless(os.name == "nt", "platform: Git Bash path forms are Windows-only")
    def test_failed_dir_conversion_is_bad_path(self):
        self.archived(self.work)
        bash_form = subprocess.run(["cygpath", "-u", str(self.work)], capture_output=True, text=True).stdout.strip()
        stub = self.tmp / "stub"
        gitlog.install(stub, real_git=jjenv.real_git(), log_path=self.shim.log_path)
        # fails for the --dir path only: the resolver and the shim convert their own paths with cygpath too
        (stub / "cygpath").write_text(
            '#!/bin/sh\nfor a in "$@"; do [ "$a" = "%s" ] && exit 1; done\nexec "%s" "$@"\n'
            % (bash_form, Path(shutil.which("cygpath")).as_posix()), encoding="utf-8", newline="\n")
        result = self.run_shim(*self.plan(dir_=bash_form), cwd=self.tmp, shim_dir=stub)
        doc = self.document(result, 2)
        self.assertEqual((doc["ok"], doc["error"]), (False, "bad_path"), doc)
        self.assertIn(bash_form, doc["message"])
        self.assertNotIn("script", doc)
        self.assertEqual(self.shim.calls(), [], "a git command ran")


class TestProjectWalk(ShimCase):
    def store_and_code(self):
        """A planning store with the archive and no installed version, and a stamped code checkout."""
        store = fx.make_repo(self.tmp / "store")
        (store / STAMP).unlink()
        self.archived(store)
        code = fx.make_repo(self.tmp / "code")
        return store, code

    def test_code_picks_the_project(self):
        store, code = self.store_and_code()
        self.assertFalse((store / STAMP).exists())
        self.assertTrue((code / STAMP).is_file())
        doc = self.document(self.run_shim(*self.plan(dir_=store, code=code), cwd=store))
        self.assertIs(doc["ok"], True, doc)
        self.assertEqual(doc["head"], fx.git(store, "rev-parse", "HEAD"))

    def test_store_without_code_is_sw_missing(self):
        store, _ = self.store_and_code()
        self.no_git_calls()
        doc = self.stop_document(self.run_shim(*self.plan(dir_=store), cwd=store))
        self.assertIn("no installed version found", doc["message"])

    def test_relative_code_from_planning_repo(self):
        # <base>/p/work is the planning repo, <base>/p/code the right checkout, <base>/elsewhere/code the wrong one
        base = self.tmp / "layout"
        store = fx.make_repo(base / "p")
        (store / STAMP).unlink()
        self.archived(store)
        code = base / "p" / "code"
        shutil.copytree(fx.make_repo(base / "q"), code)
        wrong = base / "elsewhere" / "code"
        shutil.copytree(code, wrong)
        (wrong / STAMP).write_text("0.0.1\n", encoding="utf-8")  # no sw installed for it
        fx.write(wrong, f"{P}/specwright.yaml", "vcs: jj\n")  # settings the probe would fail on
        caller = base / "elsewhere" / "sub"
        caller.mkdir(parents=True)
        self.assertEqual((caller / ".." / "code").resolve(), wrong.resolve())
        doc = self.document(self.run_shim(*self.plan(dir_=store, code="../code"), cwd=caller))
        self.assertIs(doc["ok"], True, doc)
        self.assertEqual(doc["head"], fx.git(store, "rev-parse", "HEAD"))


class TestResolverStops(ShimCase):
    def test_binary_missing_is_sw_missing(self):
        self.archived(self.work)
        home = self.tmp / "empty-home"
        home.mkdir()
        self.no_git_calls()
        doc = self.stop_document(self.run_shim(*self.plan(), home=home))
        self.assertIn(".specwright/bin/%s/sw" % tree_version(), doc["message"].replace("\\", "/"))

    def test_stub_resolver_failure_is_sw_missing(self):
        self.archived(self.work)
        script = self.copy_scripts()
        (script.parent.parent.parent / "specwright-pr" / "scripts" / "sw-path.sh").write_text(
            '#!/usr/bin/env bash\necho "sw missing or mismatched: rerun the install prompt" >&2\necho "stub detail" >&2\nexit 1\n',
            encoding="utf-8", newline="\n")
        self.no_git_calls()
        result = self.run_shim(*self.plan(), script=script)
        doc = self.stop_document(result)
        self.assertIn("stub detail", doc["message"])
        self.assertIn("stub detail", result.stderr)

    def test_no_python(self):
        empty = self.tmp / "no-tools"
        empty.mkdir()
        done = subprocess.run([jjenv.find_bash(), fx.SCRIPT.as_posix(), *self.plan()], env={**os.environ, "PATH": str(empty)},
                              cwd=self.work, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertEqual(done.stdout, NO_PYTHON)


if __name__ == "__main__":
    unittest.main()
