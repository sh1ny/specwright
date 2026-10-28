"""Tests for the suite map model of evals/run.py (`evals/suites.json`): the coverage check over a file list.

Every test builds a scratch root with suites and calls run.check_map(map, root, prefix, paths), which returns problem messages.

Run: python -m unittest discover evals/runner
"""
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RUN = Path(__file__).resolve().parent.parent / "run.py"
PREFIX = "evals"


def load_runner():
    spec = importlib.util.spec_from_file_location("evals_run_for_map", str(RUN))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SuiteMapTests(unittest.TestCase):
    def setUp(self):
        self.run = load_runner()
        self.root = Path(tempfile.mkdtemp(prefix="suite-map-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        for suite in ("alpha", "beta"):
            (self.root / suite).mkdir()
            (self.root / suite / "test_one.py").write_text("", encoding="utf-8")
        self.map = {"rules": [{"paths": ["skills/alpha/**"], "suites": ["alpha"]},
                              {"paths": ["docs/*.md"], "suites": ["beta/test_one.py"]}],
                    "no_eval": ["docs/adr/**", "LICENSE"]}

    def check(self, paths, map_=None):
        return self.run.check_map(map_ or self.map, self.root, PREFIX, paths)

    def test_a_covered_file_list_has_no_problem(self):
        paths = ["skills/alpha/SKILL.md", "docs/guide.md", "docs/adr/0001.md", "LICENSE", "evals/alpha/test_one.py",
                 "evals/run.py", "evals/fakes/gh.py"]
        self.assertEqual(self.check(paths), [])

    def test_an_uncovered_file_is_named(self):
        problems = self.check(["skills/alpha/SKILL.md", "src/new-file.txt", "evals/gone/test_x.py"])
        self.assertEqual(len(problems), 2, problems)
        self.assertIn("src/new-file.txt", problems[0])
        self.assertIn("evals/gone/test_x.py", problems[1])  # under a directory that is no longer a suite

    def test_a_missing_target_is_named(self):
        m = {"rules": [{"paths": ["a/**"], "suites": ["nosuch"]}, {"paths": ["b/**"], "suites": ["alpha/test_nope.py"]},
                       {"paths": ["c/**"], "suites": ["nodir/test_one.py"]}, {"paths": ["d/**"], "suites": ["alpha"]}],
             "no_eval": []}
        problems = self.check([], m)
        self.assertEqual(len(problems), 3, problems)
        for target, problem in zip(("nosuch", "alpha/test_nope.py", "nodir/test_one.py"), problems):
            self.assertIn(target, problem)

    def test_a_no_eval_overlap_is_named(self):
        m = dict(self.map, no_eval=["docs/**"])
        problems = self.check(["docs/guide.md"], m)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("docs/guide.md", problems[0])
        self.assertIn("docs/**", problems[0])
        sel, uncovered, no_eval = self.run.classify(m, self.root, PREFIX, ["docs/guide.md"])
        self.assertEqual((sel, uncovered, no_eval), ({"beta/test_one.py": ["docs/guide.md"]}, [], []))  # the rule still selects

    def test_matching_is_the_union_of_every_rule(self):
        m = {"rules": [{"paths": ["skills/**"], "suites": ["alpha"]}, {"paths": ["skills/x/*.md"], "suites": ["beta"]}],
             "no_eval": []}
        sel, uncovered, no_eval = self.run.classify(m, self.root, PREFIX, ["skills/x/a.md", "skills/x/y/a.md", "evals/beta/test_one.py"])
        self.assertEqual(sel, {"alpha": ["skills/x/a.md", "skills/x/y/a.md"], "beta": ["skills/x/a.md", "evals/beta/test_one.py"]})
        self.assertEqual((uncovered, no_eval), ([], []))  # `*` stays inside one segment: y/a.md is not beta's

    def test_shared_harness_selects_every_suite(self):
        sel, uncovered, _ = self.run.classify({"rules": [], "no_eval": []}, self.root, PREFIX, ["evals/fakes/gh.py"])
        self.assertEqual((sel, uncovered), ({"alpha": ["evals/fakes/gh.py"], "beta": ["evals/fakes/gh.py"]}, []))

    def test_the_prefix_is_the_roots_place_in_the_repo(self):
        sel, uncovered, _ = self.run.classify({"rules": [], "no_eval": []}, self.root, "", ["alpha/test_one.py", "evals/x"])
        self.assertEqual((sel, uncovered), ({"alpha": ["alpha/test_one.py"]}, ["evals/x"]))

    def test_a_file_target_runs_once_inside_its_suite(self):
        self.assertEqual(self.run.dedupe_targets(["alpha", "alpha/test_one.py", "beta/test_one.py"]),
                         ["alpha", "beta/test_one.py"])

    def test_a_bad_map_file_exits_2_naming_the_file(self):
        (self.root / "suites.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self.run.load_map(self.root)
        self.assertEqual(cm.exception.code, 2)


class LiveRepoMapTests(unittest.TestCase):
    def test_every_tracked_file_is_covered_once(self):
        # The real evals/suites.json against the real file list: tracked files plus untracked-but-not-ignored ones, so a file
        # a change adds is checked before it is committed (git ls-files --others --exclude-standard skips ignored files).
        run = load_runner()
        evals = RUN.parent
        repo = evals.parent
        paths = set()
        for extra in ([], ["--others", "--exclude-standard"]):
            out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", *extra], capture_output=True, check=True).stdout
            paths.update(p.decode("utf-8") for p in out.split(b"\0") if p)
        problems = run.check_map(run.load_map(evals), evals, PREFIX, sorted(paths))
        self.assertEqual(problems, [], "the suite map has %d problem(s):\n%s" % (len(problems), "\n".join(problems)))


if __name__ == "__main__":
    unittest.main()
