"""Text checks on .github/workflows/evals.yml (stdlib only, no YAML parser): the CI that runs every eval suite on Linux.

Run: python -m unittest discover evals/runner -p test_workflow.py
"""
import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "evals.yml"


def read():
    return WORKFLOW.read_text(encoding="utf-8")


def job_block(text, name):
    """The text of one top-level job (lines under `  <name>:` until the next 2-space key)."""
    m = re.search(r"^  %s:\n((?:(?:    .*|\s*)\n?)*)" % re.escape(name), text, re.M)
    if not m:
        raise AssertionError("no job %r in %s" % (name, WORKFLOW))
    return m.group(1)


class TestWorkflow(unittest.TestCase):
    def test_triggers_and_read_only_permissions(self):
        t = read()
        self.assertRegex(t, r"(?m)^on:\n(?:  .*\n)*?  pull_request:")
        self.assertRegex(t, r"(?m)^on:\n(?:  .*\n)*?  workflow_dispatch:")
        self.assertRegex(t, r"(?m)^permissions:\n  contents: read$")

    def test_concurrency_cancels_superseded_runs_per_pr(self):
        t = read()
        self.assertRegex(t, r"(?m)^concurrency:\n  group: .*github\.event\.pull_request\.number")
        self.assertIn("cancel-in-progress: true", t)

    def test_matrix_comes_from_list_suites(self):
        t = read()
        lst = job_block(t, "list")
        self.assertIn("python evals/run.py --list-suites", lst)
        self.assertRegex(lst, r"(?m)^    outputs:\n      suites: \$\{\{ steps\.\w+\.outputs\.suites \}\}")
        suite = job_block(t, "suite")
        self.assertRegex(suite, r"suite: \$\{\{ fromJSON\(needs\.list\.outputs\.suites\) \}\}")

    def test_suite_jobs_need_the_list_job(self):
        self.assertRegex(job_block(read(), "suite"), r"(?m)^    needs: list$")
        # The listing runs as its own assignment: inside `echo "...$(...)"` its exit status is lost and the list job passes.
        lst = job_block(read(), "list")
        self.assertRegex(lst, r"(?m)^\s+suites=\$\(python evals/run\.py --list-suites\)$")
        self.assertNotRegex(lst, r"echo \"[^\"]*\$\(python evals/run\.py --list-suites\)")

    def test_workflow_runs_each_listed_suite_on_linux(self):
        suite = job_block(read(), "suite")
        self.assertRegex(suite, r"runs-on: ubuntu-")
        self.assertIn("python evals/run.py --timeout 2400 ${{ matrix.suite }}", suite)
        self.assertIn("timeout-minutes: 120", suite)

    def test_one_failing_suite_does_not_cancel_the_others(self):
        t = read()
        suite = job_block(t, "suite")
        self.assertIn("fail-fast: false", suite)
        # The run step's exit code must be the job's: nothing masks a failure.
        self.assertNotIn("continue-on-error", t)
        self.assertNotIn("|| true", t)
        run_step = [l for l in suite.splitlines() if "evals/run.py --timeout" in l]
        self.assertEqual(len(run_step), 1)
        self.assertNotRegex(run_step[0], r"\|\||;|\|")

    def test_checkout_is_full_depth_and_local_main_exists(self):
        suite = job_block(read(), "suite")
        self.assertIn("fetch-depth: 0", suite)
        self.assertIn("git show-ref --verify --quiet refs/heads/main || git branch main origin/main", suite)

    def test_openspec_cli_comes_from_the_pinned_version(self):
        self.assertIn("npm i -g @fission-ai/openspec@$(cat OPENSPEC_VERSION)", job_block(read(), "suite"))

    def test_python38_interpreter_is_exposed_to_the_evals(self):
        suite = job_block(read(), "suite")
        self.assertRegex(suite, r"python-version: ['\"]?3\.8['\"]?")
        self.assertRegex(suite, r"SPECWRIGHT_PY38: \$\{\{ steps\.\w+\.outputs\.python-path \}\}")
        self.assertRegex(suite, r"python-version: ['\"]?3\.12['\"]?")

    def test_git_identity_and_default_branch_are_set(self):
        suite = job_block(read(), "suite")
        for needle in ("git config --global user.name", "git config --global user.email",
                       "git config --global init.defaultBranch main"):
            self.assertIn(needle, suite)


if __name__ == "__main__":
    unittest.main()
