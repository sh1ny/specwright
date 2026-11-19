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
import fakeexe  # noqa: E402  (jjenv puts evals/ on sys.path)
import vcs_test_support  # noqa: E402
from vcs_test_support import STAMP, bash_run, sw_env, sw_home, sw_run, stamp_version, tree_version  # noqa: E402
import swcall  # noqa: E402

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
        """`sw finish <args>` entered directly (evals/swcall.py). A test of the shim's own resolver passes `script`, `home`
        or `shim_dir` and still goes through the shim, which task 7.6 deletes with it."""
        if script is None and home is None and shim_dir is None:
            return sw_run(["finish", *args], cwd=cwd or self.work, env=env, shim=self.shim, stamp=False)
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

    def mismatch_document(self, result):
        """The native refusal of a project without a matching VERSION: `sw_mismatch`, exit 1, no git command."""
        doc = self.document(result, 1)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_mismatch"), doc)
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
        self.assertTrue(doc["steps"], doc)
        self.assertNotIn("script", doc)

    def test_prefix_with_space_and_non_ascii_change(self):
        prefix, name = "my plans/openspec", "add-éx"
        work = fx.make_repo(self.tmp / "space", prefix=prefix)
        self.archived(work, name, prefix=prefix)
        doc = self.document(self.run_shim(*self.plan(name, prefix=prefix), cwd=work))
        self.assertIs(doc["ok"], True, doc)
        self.assertEqual([m["name"] for m in doc["members"]], [name])
        steps = fx.flat(doc["steps"])
        self.assertIn(f"undo archive of {name}", steps)
        self.assertIn(f"{prefix}/changes/archive/{fx.DATE}-{name}", steps)

    def test_arguments_reach_sw_unchanged(self):
        """The helper starts sw with the list as given: spaces, non-ASCII text and an empty value arrive as they are."""
        prefix, name = "my plans/openspec", "add-éx"
        work = fx.make_repo(self.tmp / "space", prefix=prefix)
        self.archived(work, name, prefix=prefix)
        args = self.plan(name, prefix=prefix)
        self.assertEqual(swcall.argv(["finish", *args])[2:], args, "the helper adds nothing to the list")
        doc = self.document(self.run_shim(*args, cwd=work))
        steps = fx.flat(doc["steps"])
        self.assertIn(f"{prefix}/changes/archive/{fx.DATE}-{name}", steps)
        self.assertIn(f"undo archive of {name}", steps)

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: the runtime refuses a non-UTF-8 argument only on POSIX, and the name needs a Linux file system")
    def test_non_utf8_argument_is_refused(self):
        """A --change holding the byte 0xFF is refused before any command: non-zero exit, no output, no git; the valid call runs."""
        self.archived(self.work)
        self.no_git_calls()
        bad = [b"a\xffb" if arg == "add-x" else arg for arg in self.plan()]
        result = swcall.run(["finish", *bad], cwd=self.work, env=sw_env(shim=self.shim), text=False)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(self.shim.calls(), [], "a git command ran")
        control = self.document(self.run_shim(*self.plan()))  # the control: the valid change reaches git
        self.assertIs(control["ok"], True, control)
        self.assertTrue(self.shim.calls(), "the control never reached git")

    @unittest.skipUnless(os.name == "nt", "platform: a Git Bash path form only exists on Windows")
    def test_unconverted_path_on_windows_is_refused(self):
        """sw reads --dir as given: a Git Bash form it cannot convert is refused, no git command runs."""
        self.archived(self.work)
        self.no_git_calls()
        result = self.run_shim(*self.plan(dir_="/etc/x"), cwd=self.tmp)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("etc", self.document(result, 1)["message"])  # read as C:\etc\x, which holds no project
        self.assertEqual(self.shim.calls(), [], "a git command ran")

    @unittest.skipUnless(sys.platform.startswith("linux"), "platform: a file name that is not UTF-8 needs a Linux file system")
    def test_non_utf8_committed_name_is_not_utf8(self):
        """A committed archive file whose name holds 0xFF stops the plan by name: no script, exit 1 (D4)."""
        fx.git(self.work, "checkout", "-q", "-b", BRANCH)
        fx.make_change(self.work, "add-x", "DEFERRED", {"a": "New thing"})
        raw = os.fsencode(self.work) + b"/" + os.fsencode(P) + b"/changes/add-x/notes-\xff.md"
        with open(raw, "wb") as stream:
            stream.write(b"notes\n")
        fx.archive(self.work, "add-x", commit_it=True)

        result = self.run_shim(*self.plan())

        doc = self.document(result, 1)
        self.assertEqual((doc["ok"], doc["error"]), (False, "not_utf8"), doc)
        self.assertIn("notes-\\xFF.md", doc["message"])
        self.assertNotIn("script", doc)

    @unittest.skipUnless(os.name == "nt", "platform: Git Bash path forms are Windows-only")
    def test_git_bash_dir_on_windows(self):
        self.archived(self.work)
        bash_form = subprocess.run(["cygpath", "-u", str(self.work)], capture_output=True, text=True).stdout.strip()
        self.assertTrue(bash_form.startswith("/"), bash_form)
        drive = self.run_shim(*self.plan(dir_=Path(self.work).as_posix()), cwd=self.tmp, shim_dir=self.shim.path)
        # a cygpath that logs its arguments and runs the real one: the shim's own conversions need it,
        # but sw converts the --dir path by its own rules and never runs it for that path
        stub = self.tmp / "stub"
        gitlog.install(stub, real_git=jjenv.real_git(), log_path=self.shim.log_path)
        log = self.tmp / "cygpath.log"
        fakeexe.write_fake(
            stub / "cygpath",
            '#!/bin/sh\nprintf \'%%s\\n\' "$*" >> "%s"\nexec "%s" "$@"\n'
            % (log.as_posix(), Path(shutil.which("cygpath")).as_posix()))
        bash = self.run_shim(*self.plan(dir_=bash_form), cwd=self.tmp, shim_dir=stub)
        self.assertEqual(bash.returncode, 0, bash.stdout + bash.stderr)
        self.assertNotIn("not_a_repo", bash.stdout)
        self.assertEqual(json.loads(bash.stdout), json.loads(drive.stdout))
        self.assertNotIn(bash_form, log.read_text(encoding="utf-8") if log.exists() else "", "cygpath ran for --dir")

    @unittest.skipUnless(os.name == "nt", "platform: Git Bash path forms are Windows-only")
    def test_failed_dir_conversion_is_bad_path(self):
        self.archived(self.work)
        # The shim hands over its own bash, whose install root is always found. So the handoff the shim
        # writes is made here with a bash path that holds no Git root: /etc/x has nowhere to go.
        bash_form = "/etc/x"
        records = [str(FINISH_SCRIPTS), r"C:\tools\bash.exe", *self.plan(dir_=bash_form)]
        result = subprocess.run([os.environ["SPECWRIGHT_SW"], "finish", "--args-stdin"],
                                input=b"".join(x.encode("utf-8") + b"\0" for x in records),
                                capture_output=True, cwd=self.tmp, env={**os.environ, **self.shim.env})
        result.stdout, result.stderr = result.stdout.decode("utf-8"), result.stderr.decode("utf-8")
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
        doc = self.mismatch_document(self.run_shim(*self.plan(dir_=store), cwd=store))
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
        # the shim resolves a relative --code from the planning repo; direct entry reads it from the caller's directory
        doc = self.document(self.run_shim(*self.plan(dir_=store, code="../code"), cwd=caller, home=sw_home()))
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
