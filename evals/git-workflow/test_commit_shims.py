"""task-cover.sh and fit-subject.sh are shims: they resolve the project's sw with sw-path.sh and run
`sw commit --args-stdin <sub>` (design D6, D7).

The tests run the real shims against the tree's sw through the test home (design D9). Where a test needs another
resolver outcome it runs a copy of the two skills' scripts directories, laid out the way the shims expect them.

Run: python -m unittest evals/git-workflow/test_commit_shims.py
"""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "evals" / "vcs"))
import gitlog  # noqa: E402
import jjenv  # noqa: E402
from vcs_test_support import STAMP, VcsTestCase, bash_run, sw_home, stamp_version, tree_version  # noqa: E402

COMMIT_SCRIPTS = ROOT / "skills" / "specwright-commit" / "scripts"
PR_SCRIPTS = ROOT / "skills" / "specwright-pr" / "scripts"
STOP = "sw missing or mismatched: rerun the install prompt"
CHANGE = "a"
TASKS = "# Tasks\n\n## 1. Group\n\n- [x] 1.1 Add it\n"
LONG = "feat(a): task 1.1 " + "Add the thing and then more words to pass the limit of subject " + "x" * 9  # 90 characters
NO_PYTHON_COVER = '{"ok":false,"error":"no_python","message":"task-cover.sh needs python 3.8+"}\n'


class ShimCase(VcsTestCase):
    def setUp(self):
        super().setUp()
        self.shim = gitlog.install(self.root / "gitshim", real_git=jjenv.real_git(), log_path=self.root / "git.jsonl")
        self.skills = None

    def copy_scripts(self):
        """Copies of both scripts directories under <root>/skills/<skill>/scripts; returns the skills directory."""
        dest = self.root / "skills"
        for skill in ("specwright-commit", "specwright-pr"):
            shutil.copytree(ROOT / "skills" / skill / "scripts", dest / skill / "scripts",
                            ignore=shutil.ignore_patterns("__pycache__"))
        return dest

    def script(self, name, skills=None):
        return ((Path(skills) / "specwright-commit" / "scripts") if skills else COMMIT_SCRIPTS) / name

    def run_shim(self, name, *args, cwd=None, env=None, skills=None, home=None):
        shim_env = {"SPECWRIGHT_HOME": str(home or sw_home()), **self.shim.env, **(env or {})}
        return bash_run([self.script(name, skills).as_posix(), *map(str, args)], cwd=cwd or self.repo, env=shim_env,
                        shim=self.shim.path, stamp=False)

    def branch_commit(self, subject, repo=None):
        repo = repo or self.repo
        self.git(repo, "checkout", "-b", "feat/a")
        (repo / "f.txt").write_text("f\n", encoding="utf-8")
        self.git(repo, "add", "f.txt")
        self.assertEqual(self.git(repo, "commit", "-m", subject).returncode, 0)

    def tasks_file(self, where=None):
        p = Path(where or self.root) / "tasks.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(TASKS.encode("utf-8"))
        return p

    def cover_args(self, repo=None, tasks=None, code=None):
        args = []
        if code is not None:
            args += ["--code", code]
        return args + ["--repo", repo or self.repo, "--range", "main..feat/a", "--tasks", tasks or self.tasks_file(),
                       "--change", CHANGE]

    def message(self, text, name="msg.txt"):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
        return p

    def stop_document(self, result, code=1):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_missing"), doc)
        self.assertTrue(doc["message"].startswith(STOP), doc)
        self.assertIn(STOP, result.stderr)
        self.assertEqual(self.shim.calls(), [], "no git command ran")
        return doc

    def no_python(self, name, *args):
        empty = self.root / "no-tools"
        empty.mkdir(exist_ok=True)
        return subprocess.run([jjenv.find_bash(), (COMMIT_SCRIPTS / name).as_posix(), *map(str, args)],
                              env={**os.environ, "PATH": str(empty)}, cwd=self.repo, capture_output=True, text=True,
                              encoding="utf-8")


class TestTaskCoverShim(ShimCase):
    def test_task_cover_runs_sw(self):
        self.branch_commit("feat(a): task 1.1 Add it")
        result = self.run_shim("task-cover.sh", *self.cover_args())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertTrue(doc["ok"], doc)
        self.assertEqual([(c["form"]) for c in doc["tasks"][0]["commits"]], ["subject"], doc)
        self.assertEqual(doc["tasks"][0]["id"], "1.1")

    @unittest.skipUnless(os.name == "nt", "platform: Git Bash path forms are Windows-only")
    def test_task_cover_git_bash_paths_on_windows(self):
        self.branch_commit("feat(a): task 1.1 Add it")
        tasks = self.tasks_file(self.repo / "openspec" / "changes" / CHANGE)

        def run(*paths):
            repo, tasks_arg = paths
            return self.run_shim("task-cover.sh", *self.cover_args(repo=repo, tasks=tasks_arg))

        def bash_form(p):
            out = subprocess.run(["cygpath", "-u", str(p)], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            return out.stdout.strip()

        drive = run(self.repo, tasks)
        self.assertEqual(drive.returncode, 0, drive.stdout + drive.stderr)
        bash = run(bash_form(self.repo), bash_form(tasks))
        self.assertEqual(bash.returncode, 0, bash.stdout + bash.stderr)
        self.assertEqual(json.loads(bash.stdout)["tasks"][0]["id"], "1.1")
        self.assertNotIn("no_tasks", bash.stdout)
        # the documents differ only in the spelling of the paths they echo, if at all
        self.assertEqual(bash.stdout, drive.stdout)

    def test_code_picks_the_project(self):
        store = self.root / "store"
        self._init_git(store)
        self.branch_commit("feat(a): task 1.1 Add it", repo=store)
        tasks = self.tasks_file(store / "openspec" / "changes" / CHANGE)
        self.assertFalse((store / STAMP).exists())
        result = self.run_shim("task-cover.sh", *self.cover_args(repo=store, tasks=tasks, code=self.repo), cwd=store)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual([c["form"] for c in doc["tasks"][0]["commits"]], ["subject"], doc)
        # --code changes nothing in the document: the same call from a stamped store, without --code
        stamp_version(store)
        plain = self.run_shim("task-cover.sh", *self.cover_args(repo=store, tasks=tasks), cwd=store)
        self.assertEqual(plain.stdout, result.stdout)

    def test_store_without_code_is_sw_missing(self):
        store = self.root / "store"
        self._init_git(store)
        self.branch_commit("feat(a): task 1.1 Add it", repo=store)
        tasks = self.tasks_file(store / "openspec" / "changes" / CHANGE)
        self.shim.log_path.unlink(missing_ok=True)
        result = self.run_shim("task-cover.sh", *self.cover_args(repo=store, tasks=tasks), cwd=store)
        doc = self.stop_document(result)
        self.assertIn("no installed version found", doc["message"])

    def test_task_cover_binary_missing(self):
        self.branch_commit("feat(a): task 1.1 Add it")
        self.shim.log_path.unlink(missing_ok=True)
        home = self.root / "empty-home"
        home.mkdir()
        result = self.run_shim("task-cover.sh", *self.cover_args(), home=home)
        doc = self.stop_document(result)
        self.assertIn(".specwright/bin/%s/sw" % tree_version(), doc["message"].replace("\\", "/"))

    def test_task_cover_no_python(self):
        done = self.no_python("task-cover.sh", *self.cover_args())
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertEqual(done.stdout, NO_PYTHON_COVER)


class TestFitSubjectShim(ShimCase):
    def test_fit_subject_runs_sw(self):
        self.assertEqual(len(LONG), 90)
        data = LONG + "\n\nBody.\n"
        msg = self.message(data)
        result = self.run_shim("fit-subject.sh", msg)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        fitted = result.stdout.rstrip("\n")
        self.assertLessEqual(len(fitted), 72)
        self.assertTrue(LONG.startswith(fitted) and LONG[len(fitted)] == " ", fitted)
        self.assertEqual(msg.read_bytes().decode("utf-8"), fitted + "\n\nBody.\n")

    def test_fit_subject_path_with_space_and_dollar(self):
        msg = self.message(LONG + "\n\nBody.\n", name="dir with space/msg $1.txt")
        result = self.run_shim("fit-subject.sh", msg)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        fitted = result.stdout.rstrip("\n")
        self.assertLessEqual(len(fitted), 72)
        self.assertEqual(msg.read_bytes().decode("utf-8"), fitted + "\n\nBody.\n")

    def test_fit_subject_interface_mismatch(self):
        skills = self.copy_scripts()
        path = skills / "specwright-pr" / "scripts" / "sw-path.sh"
        text = path.read_text(encoding="utf-8")
        self.assertIn("SW_INTERFACE=1\n", text)
        path.write_bytes(text.replace("SW_INTERFACE=1\n", "SW_INTERFACE=2\n", 1).encode("utf-8"))
        data = (LONG + "\n\nBody.\n").encode("utf-8")
        msg = self.message(LONG + "\n\nBody.\n")
        result = self.run_shim("fit-subject.sh", msg, skills=skills)
        doc = self.stop_document(result)
        self.assertIn("interface", doc["message"])
        self.assertEqual(msg.read_bytes(), data, "the message file changed")

    def test_fit_subject_no_python(self):
        msg = self.message(LONG + "\n\nBody.\n")
        before = msg.read_bytes()
        done = self.no_python("fit-subject.sh", msg)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        doc = json.loads(done.stdout)
        self.assertEqual((doc["ok"], doc["error"]), (False, "sw_missing"), doc)
        self.assertTrue(doc["message"].startswith(STOP), doc)
        self.assertIn("Python 3.8+", doc["message"])
        self.assertTrue(done.stdout.isascii(), done.stdout)
        self.assertEqual(msg.read_bytes(), before, "the message file changed")


if __name__ == "__main__":
    unittest.main()
