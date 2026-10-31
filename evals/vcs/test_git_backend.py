"""Git backend operations preserve the exact Git argv and consumer-visible results."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess

import gitlog
import jjenv
from vcs_test_support import VcsTestCase, bash_path_env

GRADE_PATH = Path(__file__).resolve().parents[1] / "git-workflow" / "grade.py"
_spec = importlib.util.spec_from_file_location("vcs_git_workflow_grade", GRADE_PATH)
grade = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(grade)


class TestGitBackend(VcsTestCase):
    def setUp(self):
        super().setUp()
        self.set_settings(self.repo, "main_branch: main\n")
        self.shim = gitlog.install(self.root / "shim", real_git=jjenv.real_git(), log_path=self.root / "git-calls.jsonl")
        self.env = {**self.shim.env, **bash_path_env(self.shim.path), "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "VCS Test",
                    "GIT_AUTHOR_EMAIL": "vcs-test@example.invalid", "GIT_COMMITTER_NAME": "VCS Test",
                    "GIT_COMMITTER_EMAIL": "vcs-test@example.invalid"}

    def native_env(self, trace):
        """self.env for a direct native git launch: on Windows its POSIX-form PATH crashes git.exe (0xC0000005)."""
        return {**self.env, "PATH": os.environ.get("PATH", ""), "GIT_TRACE": str(trace)}

    def trace_writes(self, trace):
        path = Path(trace)
        if path.is_file():
            directory = self.root / (path.stem + "-trace")
            directory.mkdir(exist_ok=True)
            shutil.copyfile(path, directory / "git-trace.log")
        else:
            directory = path
        commands = grade.git_trace(directory) or []
        return [cmd for cmd in commands if gitlog.classify(cmd)["write"]]

    def record_baseline(self, repo, args, tag):
        trace = self.root / (tag + "-raw-trace.log")
        trace.unlink(missing_ok=True)
        result = subprocess.run([jjenv.real_git(), *args], cwd=repo,
                                env=self.native_env(trace), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        copy = self.root / (tag + "-trace")
        copy.mkdir(exist_ok=True)
        shutil.copyfile(trace, copy / "git-trace.log")
        return self.trace_writes(copy)

    def prepare_origin(self):
        origin = self.root / "origin.git"
        self.git(self.root, "init", "--bare", str(origin))
        self.git(self.repo, "remote", "add", "origin", str(origin))
        self.git(self.repo, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
        self.git(self.repo, "push", "-u", "origin", "main")
        self.git(self.repo, "fetch", "origin", "refs/heads/main:refs/remotes/origin/main")
        self.git(self.root, "--git-dir", str(origin), "symbolic-ref", "HEAD", "refs/heads/main")
        return origin

    def test_git_commit_commands_exact(self):
        self.git(self.repo, "checkout", "-b", "feat/x")
        (self.repo / "a.sh").write_text("a\n", encoding="utf-8")
        (self.repo / "b.sh").write_text("b\n", encoding="utf-8")
        (self.repo / "unrelated.txt").write_text("stay dirty\n", encoding="utf-8")
        msg = self.root / "message.txt"
        msg.write_text("feat(x): named commit\n", encoding="utf-8")
        # Raw Git baseline and backend share the same named-path operation and trace grader.
        baseline = self.root / "baseline"
        self.git(self.repo, "worktree", "add", "--detach", str(baseline), "HEAD")
        (baseline / "a.sh").write_text("a\n", encoding="utf-8")
        (baseline / "b.sh").write_text("b\n", encoding="utf-8")
        (baseline / "unrelated.txt").write_text("stay dirty\n", encoding="utf-8")
        baseline_trace = self.root / "commit-baseline-trace.log"
        raw_env = self.native_env(baseline_trace)
        for args in (("add", "--", "a.sh", "b.sh"), ("commit", "-F", str(msg), "--", "a.sh", "b.sh")):
            result = subprocess.run([jjenv.real_git(), *args], cwd=baseline, env=raw_env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        backend_trace = self.root / "commit-backend-trace.log"
        backend_trace.unlink(missing_ok=True)
        env = {**self.env, "GIT_TRACE": str(backend_trace)}
        result, _ = self.invoke("commit", "--branch", "feat/x", "--message-file", msg, "--", "a.sh", "b.sh",
                               env=env, expected=0)
        self.assertEqual(result["ok"], True)
        self.assertEqual(self.trace_writes(backend_trace), self.trace_writes(baseline_trace))
        writes = [call["argv"] for call in self.shim.calls() if call["write"]]
        self.assertEqual(writes[-2:], [["add", "--", "a.sh", "b.sh"],
                                        ["commit", "-F", str(msg), "--", "a.sh", "b.sh"]])
        self.assertEqual(self.git(self.repo, "show", "--format=", "--name-only", "HEAD").stdout.strip().splitlines(),
                         ["a.sh", "b.sh"])
        self.assertTrue((self.repo / "unrelated.txt").exists())
        self.assertIn("unrelated.txt", self.git(self.repo, "status", "--porcelain").stdout)

    def test_git_push_command_exact_no_deadline(self):
        self.set_settings(self.repo, "main_branch: main\ngithub:\n  login: invalid-account\n")
        origin = self.root / "github.com" / "origin.git"
        origin.parent.mkdir(exist_ok=True)
        self.git(self.root, "init", "--bare", str(origin))
        self.git(self.root, "--git-dir", str(origin), "symbolic-ref", "HEAD", "refs/heads/main")
        self.git(self.repo, "remote", "add", "origin", str(origin))
        baseline = self.root / "push-baseline"
        self.git(self.root, "clone", str(self.repo), str(baseline))
        self.git(baseline, "remote", "set-url", "origin", str(origin))
        self.git(self.repo, "checkout", "-b", "feat/push")
        self.git(baseline, "checkout", "-b", "feat/push")
        baseline_writes = self.record_baseline(baseline, ["push", "-u", "origin", "HEAD"], "push")
        backend_trace = self.root / "push-backend-trace.log"
        backend_trace.unlink(missing_ok=True)
        self.shim.log_path.unlink(missing_ok=True)
        result, _ = self.invoke("push", "--branch", "feat/push",
                                env={"GIT_TRACE": str(backend_trace)})
        self.assertTrue(result["ok"])
        calls = [call["argv"] for call in self.shim.calls() if call["action"] == "push"]
        self.assertEqual(calls, [["push", "-u", "origin", "HEAD"]])
        self.assertEqual(self.trace_writes(backend_trace), baseline_writes)
        refs = self.git(self.root, "--git-dir", str(origin), "show-ref", "refs/heads/feat/push")
        self.assertEqual(refs.returncode, 0, refs.stderr)

    def test_git_commit_nothing_fails_like_git(self):
        self.git(self.repo, "checkout", "-b", "feat/noop")
        msg = self.root / "message.txt"
        msg.write_text("feat(noop): no changes\n", encoding="utf-8")
        baseline = self.root / "noop-baseline"
        self.git(self.repo, "worktree", "add", "--detach", str(baseline), "HEAD")
        trace = self.root / "noop-backend-trace.log"
        trace.unlink(missing_ok=True)
        baseline_head = self.git(baseline, "rev-parse", "HEAD").stdout.strip()
        baseline_trace = self.root / "noop-baseline-trace.log"
        baseline_calls = []
        for argv in (["add", "--", "base.txt"], ["commit", "-F", str(msg), "--", "base.txt"]):
            result = subprocess.run([jjenv.real_git(), *argv], cwd=baseline,
                                    env=self.native_env(baseline_trace),
                                    capture_output=True, text=True)
            baseline_calls.append(result)
        self.assertEqual(baseline_calls[0].returncode, 0, baseline_calls[0].stderr)
        self.assertNotEqual(baseline_calls[1].returncode, 0)
        self.assertEqual(self.git(baseline, "rev-parse", "HEAD").stdout.strip(), baseline_head)
        baseline_copy = self.root / "noop-trace"
        baseline_copy.mkdir()
        shutil.copyfile(baseline_trace, baseline_copy / "git-trace.log")
        baseline_writes = self.trace_writes(baseline_copy)
        trace.unlink(missing_ok=True)
        result, _ = self.invoke("commit", "--branch", "feat/noop", "--message-file", msg, "--", "base.txt",
                               env={"GIT_TRACE": str(trace)}, expected=1)
        self.assertEqual(result["error"], "git_commit_failed")
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), baseline_head)
        self.assertEqual(self.trace_writes(trace), baseline_writes)
        calls = [call["argv"] for call in self.shim.calls() if call["action"] in ("add", "commit")]
        self.assertEqual(calls[-2:], [["add", "--", "base.txt"],
                                      ["commit", "-F", str(msg), "--", "base.txt"]])

    def test_git_fetch_call_site_forms(self):
        self.prepare_origin()
        expected = [
            (("--quiet",), ["fetch", "-q", "origin", "main"]),
            (("--no-tags",), ["fetch", "--no-tags", "origin", "main"]),
            ((), ["fetch", "origin", "main"]),
        ]
        for index, (options, argv) in enumerate(expected):
            self.shim.log_path.unlink(missing_ok=True)
            baseline_writes = self.record_baseline(self.repo, argv, "fetch-%d" % index)
            backend_trace = self.root / ("fetch-backend-%d-trace.log" % index)
            backend_trace.unlink(missing_ok=True)
            self.shim.log_path.unlink(missing_ok=True)
            result, _ = self.invoke("fetch-main", *options, env={"GIT_TRACE": str(backend_trace)})
            self.assertTrue(result["ok"])
            self.assertEqual([c["argv"] for c in self.shim.calls() if c["action"] == "fetch"], [argv])
            self.assertEqual(self.trace_writes(backend_trace), baseline_writes)
            self.assertEqual(self.git(self.repo, "rev-parse", "refs/remotes/origin/main").returncode, 0)

    def test_git_pull_call_site_forms(self):
        origin = self.prepare_origin()
        pairs = []
        for index in range(2):
            raw = self.root / ("pull-raw-%d" % index)
            backend = self.root / ("pull-vcs-%d" % index)
            self.git(self.root, "clone", str(origin), str(raw))
            self.git(self.root, "clone", str(origin), str(backend))
            self.set_settings(backend, "main_branch: main\n")
            pairs.append((raw, backend))
        seed = self.root / "pull-seed"
        self.git(self.root, "clone", str(origin), str(seed))
        (seed / "pulled.txt").write_text("remote update\n", encoding="utf-8")
        self.git(seed, "add", "pulled.txt")
        self.git(seed, "commit", "-m", "remote update")
        self.git(seed, "push", "origin", "main")
        expected = (
            ((), ["pull", "--ff-only"]),
            (("--remote-branch",), ["pull", "--ff-only", "origin", "main"]),
        )
        for index, (options, argv) in enumerate(expected):
            raw, backend = pairs[index]
            baseline_writes = self.record_baseline(raw, argv, "pull-%d" % index)
            backend_trace = self.root / ("pull-backend-%d-trace.log" % index)
            backend_trace.unlink(missing_ok=True)
            self.shim.log_path.unlink(missing_ok=True)
            result, _ = self.invoke("pull", *options, repo=backend,
                                    env={"GIT_TRACE": str(backend_trace)})
            self.assertTrue(result["ok"])
            self.assertEqual([c["argv"] for c in self.shim.calls() if c["action"] == "pull"], [argv])
            self.assertEqual(self.trace_writes(backend_trace), baseline_writes)
            self.assertEqual(self.git(backend, "rev-parse", "HEAD").stdout.strip(),
                             self.git(backend, "rev-parse", "refs/remotes/origin/main").stdout.strip())
            self.assertEqual((backend / "pulled.txt").read_text(encoding="utf-8"), "remote update\n")

    def test_git_branch_merge_delete_forms(self):
        baseline = self.root / "branch-baseline"
        self.git(self.root, "clone", str(self.repo), str(baseline))
        message = self.root / "merge-message.txt"
        message.write_text("merge: feature\n", encoding="utf-8")
        for target in (self.repo, baseline):
            self.git(target, "checkout", "-b", "feat/merge")
            (target / "merge.txt").write_text("merge\n", encoding="utf-8")
            self.git(target, "add", "merge.txt")
            self.git(target, "commit", "-m", "feature")
            self.git(target, "checkout", "main")
        baseline_argv = [
            ["checkout", "-b", "feat/create"], ["checkout", "main"],
            ["merge", "--no-ff", "feat/merge", "-F", str(message)],
            ["branch", "-d", "feat/create"], ["branch", "-D", "feat/merge"]]
        baseline_writes = []
        for index, args in enumerate(baseline_argv):
            baseline_writes += self.record_baseline(baseline, args, "branch-%d" % index)
        backend_trace = self.root / "branch-backend-trace.log"
        backend_trace.unlink(missing_ok=True)
        self.shim.log_path.unlink(missing_ok=True)
        env = {"GIT_TRACE": str(backend_trace)}
        self.invoke("branch-create", "--branch", "feat/create", env=env)
        self.invoke("switch", "--branch", "main", env=env)
        self.invoke("merge", "--branch", "feat/merge", "--message-file", message, env=env)
        self.assertEqual(self.git(self.repo, "log", "-1", "--format=%s").stdout.strip(), "merge: feature")
        self.assertEqual(self.git(self.repo, "log", "-1", "--format=%P").stdout.strip().count(" "), 1)
        self.invoke("delete-branch", "--branch", "feat/create", env=env)
        self.invoke("delete-branch", "--branch", "feat/merge", "--force", env=env)
        self.assertEqual(self.trace_writes(backend_trace), baseline_writes)
        writes = [call["argv"] for call in self.shim.calls() if call["write"]]
        self.assertEqual(writes, baseline_argv)
