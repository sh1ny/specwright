"""Text checks on .github/workflows/evals.yml (stdlib only, no YAML parser): the CI that runs every eval suite on Linux, Windows and macOS.

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

    def test_workflow_runs_each_listed_suite_on_three_oses(self):
        suite = job_block(read(), "suite")
        m = re.search(r"(?m)^        os: \[([^\]]*)\]$", suite)
        self.assertIsNotNone(m, "matrix.os must be an inline list")
        self.assertEqual([o.strip() for o in m.group(1).split(",")], ["ubuntu-24.04", "windows-latest", "macos-latest"])
        self.assertRegex(suite, r"(?m)^    runs-on: \$\{\{ matrix\.os \}\}$")
        self.assertNotRegex(suite, r"runs-on: ubuntu-")
        self.assertRegex(job_block(read(), "list"), r"runs-on: ubuntu-24\.04")

    def test_job_name_and_fail_fast_cover_each_os(self):
        suite = job_block(read(), "suite")
        self.assertRegex(suite, r"(?m)^    name: \$\{\{ matrix\.suite \}\} \(\$\{\{ matrix\.os \}\}\)$")
        self.assertIn("fail-fast: false", suite)

    def test_steps_run_under_bash_with_git_usr_bin_first_on_windows(self):
        suite = job_block(read(), "suite")
        self.assertRegex(suite, r"(?m)^    defaults:\n      run:\n        shell: bash$")
        steps = [s for s in re.split(r"(?m)^(?=      - )", suite.split("\n    steps:\n", 1)[1]) if s.strip()]
        windows = [s for s in steps if "if: runner.os == 'Windows'" in s]
        self.assertTrue(windows, "a step must run only on Windows")
        path_step = windows[0]
        usr, plain = "C:\\Program Files\\Git\\usr\\bin", "C:\\Program Files\\Git\\bin"
        self.assertIn("GITHUB_PATH", path_step)
        self.assertIn(usr, path_step)
        self.assertIn(plain, path_step)
        self.assertLess(path_step.index(usr), path_step.index(plain), "usr\\bin goes first")
        install = next(i for i, s in enumerate(steps) if "Install pinned jj" in s.splitlines()[0])
        self.assertLess(steps.index(path_step), install)
        logged = "\n".join(windows)
        self.assertIn("command -v bash cygpath sed", logged)
        self.assertIn("shutil.which('bash')", logged)

    def test_job_and_run_timeouts_are_per_os(self):
        suite = job_block(read(), "suite")
        # measured in evals/timings.md (CI matrix): run_timeout 1.5 x the slowest suite, timeout run_timeout + 5 min
        for os_name, timeout, run_timeout in (("ubuntu-24.04", 15, 600), ("macos-latest", 25, 1200),
                                              ("windows-latest", 35, 1800)):
            self.assertRegex(suite, r"- os: %s\n\s+timeout: %d\n\s+run_timeout: %d\b"
                             % (re.escape(os_name), timeout, run_timeout))
        self.assertRegex(suite, r"(?m)^    timeout-minutes: \$\{\{ matrix\.timeout \}\}$")
        self.assertIn("python evals/run.py --timeout ${{ matrix.run_timeout }} ${{ matrix.suite }}", suite)

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
