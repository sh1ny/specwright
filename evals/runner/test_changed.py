"""Tests for `evals/run.py --changed <base>`: the changed paths since a merge base select the suites to run.

Every test builds a scratch git repository holding an `evals/` root of fake suites (each test file writes its own name to a
file of its own in a marker directory, since concurrent appends to one file lose writes on Windows) and an
`evals/suites.json`, then runs `run.py --root <scratch>/evals --changed main`. The live checkout is never read.

Run: python -m unittest discover evals/runner
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUN = Path(__file__).resolve().parent.parent / "run.py"

TEST_BODY = (
    "import os, unittest\n"
    "class T(unittest.TestCase):\n"
    "    def test_marker(self):\n"
    "        with open(os.path.join(os.environ['MARKER_DIR'], str(os.getpid())), 'w') as f:\n"
    "            f.write(%r + '\\n')\n")

SUITES = {"alpha": ["test_one.py", "test_two.py"], "beta": ["test_one.py"], "gamma": ["test_one.py"], "delta": ["test_one.py"]}
EVERY_FILE = ["alpha/test_one.py", "alpha/test_two.py", "beta/test_one.py", "delta/test_one.py", "gamma/test_one.py"]

MAP = {"rules": [{"paths": ["skills/x/**"], "suites": ["alpha"]},
                 {"paths": ["skills/y/**"], "suites": ["beta"]},
                 {"paths": ["skills/z/**"], "suites": ["gamma"]},
                 {"paths": ["skills/w/**"], "suites": ["delta"]},
                 {"paths": ["openspec/**"], "suites": ["alpha/test_two.py"]}],
       "no_eval": ["docs/adr/**", "evals/suites.json"]}


class ChangedTests(unittest.TestCase):
    def setUp(self):
        base = Path(tempfile.mkdtemp(prefix="changed-test-"))
        self.addCleanup(shutil.rmtree, str(base), True)
        self.repo = base / "repo"
        self.root = self.repo / "evals"
        self.marker = base / "markers"
        self.marker.mkdir()
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("checkout", "-q", "-b", "main")
        for suite, files in SUITES.items():
            for f in files:
                self.write("evals/%s/%s" % (suite, f), TEST_BODY % ("%s/%s" % (suite, f)))
        self.set_map(MAP)
        for p in ("skills/x/a.sh", "skills/y/old.sh", "skills/w/gone.sh", "docs/adr/0001.md", "openspec/changes/c/tasks.md"):
            self.write(p, "base\n")
        self.git("add", "-A")
        self.commit("base")
        self.git("checkout", "-q", "-b", "feature")

    def git(self, *args):
        cmd = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false",
               "-C", str(self.repo)] + list(args)
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        return r.stdout.decode("utf-8", "replace")

    def commit(self, msg):
        self.git("commit", "-q", "-m", msg)

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))

    def set_map(self, m):
        self.write("evals/suites.json", json.dumps(m))

    def run_changed(self, *args):
        """Run the runner over the scratch root; returns (exit code, stdout, stderr, the sorted marker lines)."""
        env = dict(os.environ, MARKER_DIR=str(self.marker))
        cmd = [sys.executable, str(RUN), "--root", str(self.root)] + list(args)
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=str(self.repo.parent))
        marks = sorted(m for f in self.marker.iterdir() for m in f.read_text().split())
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace"), marks

    def changed(self, base="main"):
        return self.run_changed("--changed", base)

    def test_one_mapped_path_runs_only_its_suite(self):
        self.write("skills/x/a.sh", "changed\n")
        self.git("add", "-A")
        self.commit("edit")
        rc, out, err, marks = self.changed()
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(marks, ["alpha/test_one.py", "alpha/test_two.py"])
        self.assertIn("alpha: skills/x/a.sh", out)
        self.assertIn("alpha: 2 files, 2 tests", out)
        self.assertNotIn("beta:", out)

    def test_a_file_target_runs_only_that_file(self):
        self.write("openspec/changes/c/tasks.md", "changed\n")
        rc, out, err, marks = self.changed()
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(marks, ["alpha/test_two.py"])
        self.assertIn("alpha/test_two.py: openspec/changes/c/tasks.md", out)
        self.assertIn("alpha: 1 files, 1 tests", out)

    def test_a_file_target_inside_a_selected_suite_runs_once(self):
        self.write("skills/x/a.sh", "changed\n")
        self.write("openspec/changes/c/tasks.md", "changed\n")
        rc, out, err, marks = self.changed()
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(marks, ["alpha/test_one.py", "alpha/test_two.py"])  # test_two.py once, not twice
        self.assertIn("alpha: 2 files, 2 tests", out)

    def test_an_unstaged_change_counts(self):
        self.write("skills/y/old.sh", "modified, not staged\n")
        rc, out, err, marks = self.changed()
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(marks, ["beta/test_one.py"])
        self.assertIn("beta: skills/y/old.sh", out)

    def test_renamed_deleted_and_untracked_paths_count(self):
        (self.repo / "skills" / "z").mkdir(parents=True)
        self.git("mv", "skills/y/old.sh", "skills/z/new.sh")  # both sides of a rename: beta (old), gamma (new)
        self.git("rm", "-q", "skills/w/gone.sh")  # deleted: delta
        self.commit("move and delete")
        self.write("skills/x/fresh.sh", "new\n")  # untracked, not ignored: alpha
        rc, out, err, marks = self.changed()
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(marks, EVERY_FILE)
        for line in ("beta: skills/y/old.sh", "gamma: skills/z/new.sh", "delta: skills/w/gone.sh", "alpha: skills/x/fresh.sh"):
            self.assertIn(line, out)

    def test_an_uncovered_path_runs_every_suite(self):
        self.write("src/new.txt", "x\n")
        rc, out, err, marks = self.changed()
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(marks, EVERY_FILE)
        self.assertIn("uncovered: src/new.txt (running every suite)", out)

    def test_a_path_under_a_removed_suite_runs_every_suite(self):
        self.write("evals/gone/test_x.py", "")
        self.git("add", "-A")
        self.commit("add a suite")
        self.git("checkout", "-q", "-b", "later")
        self.git("rm", "-q", "evals/gone/test_x.py")
        self.commit("remove it")
        rc, out, err, marks = self.changed("feature")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(marks, EVERY_FILE)
        self.assertIn("uncovered: evals/gone/test_x.py", out)

    def test_only_no_eval_paths_run_nothing_and_exit_0(self):
        self.write("docs/adr/0001.md", "edited\n")
        rc, out, err, marks = self.changed()
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(marks, [])
        self.assertIn("no eval suite covers these changes", out)

    def test_a_rule_wins_over_an_overlapping_no_eval(self):
        self.set_map(dict(MAP, no_eval=["docs/adr/**", "evals/suites.json", "skills/x/**"]))
        self.git("add", "-A")
        self.commit("overlap")
        self.write("skills/x/a.sh", "changed\n")
        rc, out, err, marks = self.changed()
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(marks, ["alpha/test_one.py", "alpha/test_two.py"])
        self.assertIn("alpha: skills/x/a.sh", out)

    def test_an_unknown_base_exits_2(self):
        rc, out, err, marks = self.changed("no-such-ref")
        self.assertEqual(rc, 2, out + err)
        self.assertIn("no-such-ref", err)
        self.assertEqual(marks, [])

    def test_a_base_with_no_merge_base_exits_2(self):
        self.git("checkout", "-q", "--orphan", "island")
        self.git("rm", "-rfq", "--cached", ".")
        self.write("lonely.txt", "x\n")
        self.git("add", "lonely.txt")
        self.commit("unrelated history")
        self.git("checkout", "-q", "-f", "feature")
        rc, out, err, marks = self.changed("island")
        self.assertEqual(rc, 2, out + err)
        self.assertIn("island", err)
        self.assertEqual(marks, [])

    def test_changed_with_suite_names_exits_2(self):
        self.write("skills/x/a.sh", "changed\n")
        rc, out, err, marks = self.run_changed("--changed", "main", "beta")
        self.assertEqual(rc, 2, out + err)
        self.assertIn("--changed", err)
        self.assertIn("cannot be combined", err)
        self.assertEqual(marks, [])

    def test_changed_exits_2_on_a_missing_target(self):
        self.set_map(dict(MAP, rules=MAP["rules"] + [{"paths": ["skills/q/**"], "suites": ["nosuch"]}]))
        self.write("skills/x/a.sh", "changed\n")
        rc, out, err, marks = self.changed()
        self.assertEqual(rc, 2, out + err)
        self.assertIn("nosuch", err)
        self.assertEqual(marks, [])


if __name__ == "__main__":
    unittest.main()
