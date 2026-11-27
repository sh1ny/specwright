"""The project version check at sw's entry (native-cli "Project commands check the project's version", "The version check
reads only a version", "Commands that check no project version", "The project is chosen by --project, then the command's own
argument"; ADR 0040).

Every case runs the built sw (SPECWRIGHT_SW) with ordinary arguments, in projects made here: a git repository whose
openspec/.specwright/VERSION holds sw's own version (the match), another version, or nothing.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swharness  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "git-workflow"))
import fixtures  # noqa: E402

EXE = ".exe" if os.name == "nt" else ""


class ProjectVersionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="swver-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sw = swharness.require_sw()
        self.version = json.loads(swharness.run_sw("version", "--json").stdout)["version"]
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = swharness.fixture_env(SPECWRIGHT_HOME=self.home, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                                         GIT_AUTHOR_NAME="Ver Test", GIT_AUTHOR_EMAIL="ver@example.invalid",
                                         GIT_COMMITTER_NAME="Ver Test", GIT_COMMITTER_EMAIL="ver@example.invalid")

    def git(self, repo, *args):
        done = subprocess.run(["git", *args], cwd=repo, env=self.env, capture_output=True, text=True, encoding="utf-8",
                              timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done.stdout

    def project(self, name, version="", raw=None):
        """A git repository with one commit on main; `version` (default sw's own) is its VERSION, None writes no file."""
        repo = self.root / name
        repo.mkdir()
        self.git(repo, "init", "-b", "main")
        (repo / "base.txt").write_text("base\n", encoding="utf-8")
        self.git(repo, "add", "base.txt")
        self.git(repo, "commit", "-m", "initial")
        value = self.version if version == "" else version
        if value is not None:
            stamp = repo / "openspec" / ".specwright" / "VERSION"
            stamp.parent.mkdir(parents=True)
            stamp.write_bytes(value.encode("utf-8") if raw is None else raw)
        return repo

    def sw_run(self, *args, cwd=None, env=None):
        done = subprocess.run([self.sw, *map(str, args)], cwd=cwd, env=env or self.env, capture_output=True, text=True,
                              encoding="utf-8", timeout=60)
        return done

    def vcs_state(self, repo, *prefix, cwd=None):
        return self.sw_run(*prefix, "vcs", "state", "--repo", repo, "--role", "code", cwd=cwd or repo)

    def assert_mismatch(self, done, *words):
        self.assertEqual(done.returncode, 1, (done.stdout, done.stderr))
        document = json.loads(done.stdout)
        self.assertEqual((document["ok"], document["error"]), (False, "sw_mismatch"), document)
        for word in words:
            self.assertIn(str(word), document["message"])
        return document


class ProjectCommandTests(ProjectVersionCase):
    def test_matching_version_runs(self):
        repo = self.project("code")
        done = self.vcs_state(repo)
        self.assertEqual(done.returncode, 0, (done.stdout, done.stderr))
        self.assertTrue(json.loads(done.stdout)["ok"], done.stdout)

    def test_another_version_is_sw_mismatch(self):
        """The mismatch document names the running version, the project's and the binary to run; nothing runs or changes."""
        repo = self.project("code", "99.0.0")
        (repo / "a.md").write_text("one\n", encoding="utf-8")
        (repo / "m.txt").write_text("feat(ver): a\n", encoding="utf-8")
        head = self.git(repo, "rev-parse", "HEAD")
        done = self.sw_run("vcs", "commit", "--repo", repo, "--role", "code", "--branch", "main", "--message-file", "m.txt",
                           "--", "a.md", cwd=repo)
        self.assert_mismatch(done, self.version, "99.0.0", self.home.as_posix() + "/.specwright/bin/99.0.0/sw" + EXE)
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), head, "no commit was made")
        self.assertEqual(self.git(repo, "status", "--porcelain", "--", "a.md"), "?? a.md\n", "nothing was staged")

    def test_no_version_is_sw_mismatch(self):
        repo = self.project("code", None)
        done = self.vcs_state(repo)
        document = self.assert_mismatch(done, "no installed version found", "rerun the install prompt")
        self.assertEqual(done.stderr, "")
        self.assertIn(repo.name, document["message"])

    def test_version_that_is_a_path_is_not_a_version(self):
        repo = self.project("code", "../../../planted/.specwright/bin/" + self.version)
        done = self.vcs_state(repo)
        self.assert_mismatch(done, "not a version")

    def test_version_with_crlf_matches(self):
        repo = self.project("code", raw=(self.version + "\r\n").encode("utf-8"))
        done = self.vcs_state(repo)
        self.assertEqual(done.returncode, 0, (done.stdout, done.stderr))

    def test_fenced_call_with_another_version_starts_nothing(self):
        """`sw as` stops before the credential lookup: only the document on stdout, and no gh ran."""
        repo = self.project("code", "99.0.0")
        marks = self.root / "gh-ran"
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text('#!/bin/sh\necho ran >> "%s"\nexit 0\n' % marks.as_posix(), encoding="utf-8", newline="\n")
        (bin_dir / "gh").chmod(0o755)
        (bin_dir / "gh.cmd").write_text('@echo ran >> "%s"\r\n' % marks, encoding="utf-8", newline="")
        env = dict(self.env, PATH=str(bin_dir) + os.pathsep + self.env["PATH"])
        body = repo / "b"
        body.write_text("hello\n", encoding="utf-8")
        done = self.sw_run("as", "sh1ny", "gh", "pr", "comment", "5", "--body-file", "b", cwd=repo, env=env)
        self.assert_mismatch(done, "99.0.0")
        self.assertEqual(done.stderr, "")
        self.assertFalse(marks.exists(), "no gh command ran")


class NoCheckTests(ProjectVersionCase):
    def test_update_across_versions_has_no_check(self):
        """`sw update` reads no project version: in a project of another version it runs its own subcommand."""
        repo = self.project("code", "99.0.0")
        done = self.sw_run("update", "interface", cwd=repo)
        self.assertEqual(done.returncode, 0, (done.stdout, done.stderr))
        self.assertTrue(json.loads(done.stdout)["ok"], done.stdout)

    def test_version_outside_a_project(self):
        nowhere = self.root / "nowhere"
        nowhere.mkdir()
        done = self.sw_run("version", "--json", cwd=nowhere)
        self.assertEqual(done.returncode, 0, (done.stdout, done.stderr))
        self.assertEqual(json.loads(done.stdout)["version"], self.version)

    def test_run_bounded_and_reviewers_are_not_checked(self):
        repo = self.project("code", "99.0.0")
        done = self.sw_run("pr", "reviewers", cwd=repo)
        self.assertNotIn("sw_mismatch", done.stdout + done.stderr)
        done = self.sw_run("run", "--bounded", "--", sys.executable, "-c", "print('ok')", cwd=repo)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "ok"), done.stderr)


class ProjectChoiceTests(ProjectVersionCase):
    def test_store_started_call_with_project(self):
        """The store has no VERSION; the leading --project names the code checkout whose VERSION is checked."""
        code = self.project("code")
        store = self.project("store", None)
        done = self.sw_run("--project", code, "vcs", "state", "--repo", store, "--role", "store", "--code", store,
                           cwd=store)
        self.assertEqual(done.returncode, 0, (done.stdout, done.stderr))
        self.assertTrue(json.loads(done.stdout)["ok"], done.stdout)

    def test_store_started_call_without_project_is_sw_mismatch(self):
        store = self.project("store", None)
        done = self.sw_run("as", "sh1ny", "git", "status", cwd=store)
        document = self.assert_mismatch(done, "no installed version found")
        self.assertIn(store.name, document["message"])

    def enterprise_projects(self):
        code = self.project("code")
        store = self.project("store", None)
        (store / "openspec").mkdir()
        (code / "openspec" / "specwright.yaml").write_text(
            "github:\n  host: github.example.com\n", encoding="utf-8")
        (store / "openspec" / "specwright.yaml").write_text(
            "github:\n  host: stale.example.org\n", encoding="utf-8")
        fixtures.install_fake_gh(self.root)
        state, log = self.root / "gh-state.json", self.root / "gh-log.jsonl"
        state.write_text(json.dumps({
            "host": "github.example.com", "user": "active",
            "tokens": {"active": "other-account", "publisher": "expected-token"},
        }), encoding="utf-8")
        env = dict(self.env, PATH=str(self.root / "bin") + os.pathsep + self.env["PATH"],
                   FAKE_GH_STATE=str(state), FAKE_GH_LOG=str(log))
        return code, store, env

    def test_store_fence_uses_code_project_host(self):
        code, store, env = self.enterprise_projects()
        done = self.sw_run("--project", code, "as", "publisher", "gh", "api", "user", "--jq", ".login",
                           cwd=store, env=env)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "publisher"), done.stderr)

    def test_store_fence_checks_store_remote_from_store_cwd(self):
        code, store, env = self.enterprise_projects()
        self.git(store, "remote", "add", "origin", "https://marker:secret@github.example.com/team/plans.git")
        done = self.sw_run("--project", code, "as", "publisher", "git", "status", cwd=store, env=env)
        self.assertEqual((done.returncode, done.stdout), (3, ""), done.stderr)
        self.assertIn("origin", done.stderr)
        self.assertIn("github.example.com", done.stderr)
        self.assertNotIn("marker:secret", done.stderr)

    def test_resolve_refuses_project_with_another_version(self):
        caller = self.project("caller")
        other = self.project("other", "99.0.0")
        done = self.sw_run("--project", other, "as", "--resolve", cwd=caller)
        self.assert_mismatch(done, self.version, "99.0.0")

    def test_fence_has_no_fallback_when_selected_binary_is_missing(self):
        other = self.project("other", "99.0.0")
        self.assertFalse((self.home / ".specwright" / "bin" / "99.0.0" / ("sw" + EXE)).exists())
        done = self.sw_run("--project", other, "as", "--resolve", cwd=other)
        self.assert_mismatch(done, self.home.as_posix() + "/.specwright/bin/99.0.0/sw" + EXE)

    def test_fence_refuses_malformed_project_prefix(self):
        code = self.project("code")
        done = self.sw_run("--project", code, "--project", code, "as", "--resolve", cwd=code)
        self.assertEqual((done.returncode, done.stdout), (2, ""), done.stderr)
        self.assertIn("--project", done.stderr)

    def test_own_code_argument_chooses_the_project(self):
        code = self.project("code")
        store = self.project("store", None)
        done = self.sw_run("vcs", "state", "--repo", store, "--role", "store", "--code", code, cwd=store)
        self.assertEqual(done.returncode, 0, (done.stdout, done.stderr))

    @unittest.skipIf(os.name == "nt", "platform: `link/..` names the directory above the link's target only on POSIX")
    def test_project_through_link_and_dotdot_is_physical(self):
        """`--project /A/link/..` with `link` pointing into B/subdir: the check reads B's VERSION (the only match), not
        A's, and the command acts on the repository its own options name."""
        a = self.project("a", "99.0.0")
        b = self.project("b")
        (b / "subdir").mkdir()
        os.symlink(b / "subdir", a / "link")
        c = self.project("c", "99.0.0")
        done = self.sw_run("--project", f"{a}/link/..", "vcs", "state", "--repo", c, "--role", "code", cwd=c)
        self.assertEqual(done.returncode, 0, (done.stdout, done.stderr))
        document = json.loads(done.stdout)
        self.assertTrue(document["ok"], document)
        self.assertEqual(document["head"], self.git(c, "rev-parse", "HEAD").strip())

    def test_two_leading_project_options_is_usage(self):
        code = self.project("code")
        done = self.sw_run("--project", code, "--project", code, "vcs", "state", cwd=code)
        self.assertEqual((done.returncode, done.stdout), (2, ""), done.stderr)
        self.assertIn("--project", done.stderr)


if __name__ == "__main__":
    unittest.main()
