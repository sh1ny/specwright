"""jj commits only the requested, snapshotted paths with their complete message."""

import json
import os
import subprocess
from pathlib import Path
from unittest import mock

import jjenv
from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase, bash_path_env


TASK_COVER = Path(__file__).resolve().parents[2] / "skills" / "specwright-commit" / "scripts" / "task-cover.sh"


class TestJjCommit(VcsTestCase):
    def setUp(self):
        super().setUp()
        self.jj = require_jj()
        self.scratch = Scratch()
        self.addCleanup(self.scratch.close)
        self.fixture = self.scratch.tracked_repo()
        self.repo = self.fixture.path
        self.set_settings(self.repo, "vcs: jj\nmain_branch: main\n")
        self.fixture.run(self.jj, "commit", "-m", "fixture Specwright settings")
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", "@-")
        self.branch = "feat/add-jj-backend"
        self.fixture.run(self.jj, "bookmark", "create", self.branch, "-r", "@-")

    def commit(self, message, *paths, expected=0):
        message_file = self.root / "commit-message.txt"
        with message_file.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(message)
        return self.invoke("commit", "--branch", self.branch, "--message-file", message_file,
                           "--", *paths, repo=self.repo, expected=expected)

    def bookmark(self):
        return self.git(self.repo, "rev-parse", "refs/heads/" + self.branch).stdout.strip()

    def test_git_reads_see_bookmark_tip(self):
        named = self.repo / "group.txt"
        named.write_text("group work\n", encoding="utf-8")
        message = ("feat(add-jj-backend): group 3 jj writes\n\n"
                   "Specwright-Task: 3.1\n"
                   "Co-authored-by: Eval Bot <eval@example.invalid>\n")
        result, _ = self.commit(message, "group.txt")
        self.assertTrue(result["ok"])

        head = self.git(self.repo, "rev-parse", "HEAD")
        bookmark = self.git(self.repo, "rev-parse", "refs/heads/" + self.branch)
        self.assertEqual(head.returncode, 0, head.stderr)
        self.assertEqual(bookmark.returncode, 0, bookmark.stderr)
        self.assertEqual(head.stdout.strip(), bookmark.stdout.strip())
        body = self.git(self.repo, "cat-file", "commit", self.bookmark())
        self.assertEqual(body.returncode, 0, body.stderr)
        self.assertIn("\n\n", body.stdout)
        self.assertEqual(body.stdout.split("\n\n", 1)[1], message)

        tasks = self.root / "tasks.md"
        with tasks.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write("## 3. jj writes\n- [x] 3.1 Write the group tests\n")
        shell_env = bash_path_env()
        shell_env.update({key: value for key, value in self.scratch.env.items() if key != "PATH"})
        shell_env["VCS_TEST_SEARCH"] = shell_env["PATH"]
        cover = subprocess.run(
            [require_jjenv_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"',
             "task-cover", TASK_COVER.as_posix(), "--repo", self.repo.as_posix(), "--range", "main..HEAD",
             "--tasks", tasks.as_posix(), "--change", "add-jj-backend"],
            cwd=self.repo, env=shell_env, capture_output=True, text=True)
        self.assertEqual(cover.returncode, 0, cover.stdout + cover.stderr)
        coverage = json.loads(cover.stdout)
        self.assertEqual(coverage["uncovered"], [])
        covered = next(task for task in coverage["tasks"] if task["id"] == "3.1")
        self.assertEqual(len(covered["commits"]), 1)
        self.assertEqual(covered["commits"][0]["form"], "trailer")

    def test_vcs_sh_jj_reads_the_fixture_config(self):
        """A CI runner has no jj user config, so the jj that vcs.sh runs must read the fixture's, not the user's."""
        (self.repo / "group.txt").write_text("group work\n", encoding="utf-8")
        user = self.root / "user-jj.toml"
        user.write_text('user.name = "Someone Else"\nuser.email = "else@example.invalid"\n', encoding="utf-8")
        with mock.patch.dict(os.environ, {"JJ_CONFIG": str(user), "JJ_USER": "Someone Else"}):
            result, _ = self.commit("feat(add-jj-backend): work\n", "group.txt")
        self.assertTrue(result["ok"], result)
        author = self.git(self.repo, "log", "-1", "--format=%an|%ae|%cn|%ce", self.bookmark()).stdout.strip()
        self.assertEqual(author, "|".join([jjenv.FIXTURE_NAME, jjenv.FIXTURE_EMAIL] * 2))

    def test_unrelated_edit_stays_in_wc(self):
        named = self.repo / "named.txt"
        unrelated = self.repo / "notes.txt"
        named.write_text("committed path\n", encoding="utf-8")
        unrelated.write_text("keep this edit\n", encoding="utf-8")
        before = self.bookmark()

        result, _ = self.commit("feat(add-jj-backend): named path\n\nSpecwright-Task: 3.1\n", "named.txt")

        self.assertTrue(result["ok"])
        self.assertNotEqual(self.bookmark(), before)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep this edit\n")
        show = self.git(self.repo, "show", "--format=", "--name-only", self.bookmark())
        self.assertEqual(show.returncode, 0, show.stderr)
        self.assertEqual(show.stdout.replace("\\", "/").splitlines(), ["named.txt"])
        listed = self.fixture.run(self.jj, "file", "list", "-r", "@").stdout.replace("\\", "/")
        self.assertIn("notes.txt", listed)

    def test_commit_named_paths_only(self):
        ordinary = self.repo / "named.txt"
        metacharacter = self.repo / "group (one)&two.txt"
        unrelated = self.repo / "scratch.log"
        ordinary.write_text("ordinary named file\n", encoding="utf-8")
        metacharacter.write_text("fileset syntax must not reinterpret this name\n", encoding="utf-8")
        unrelated.write_text("leave in working copy\n", encoding="utf-8")
        before = self.bookmark()
        before_head = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        wrong_message = self.root / "wrong-branch-message.txt"
        wrong_message.write_text("feat(add-jj-backend): should not commit\n", encoding="utf-8")

        wrong, _ = self.invoke("commit", "--branch", "feat/not-current", "--message-file", wrong_message,
                               "--", "named.txt", repo=self.repo, expected=1)
        self.assertFalse(wrong["ok"])
        self.assertEqual(self.bookmark(), before)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), before_head)

        result, _ = self.commit("feat(add-jj-backend): selected files\n\nSpecwright-Task: 3.1\n",
                                "named.txt", "group (one)&two.txt")
        self.assertTrue(result["ok"])
        show = self.git(self.repo, "show", "--format=", "--name-only", self.bookmark())
        self.assertEqual(show.returncode, 0, show.stderr)
        self.assertEqual(set(line.replace("\\", "/") for line in show.stdout.splitlines()),
                         {"named.txt", "group (one)&two.txt"})
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "leave in working copy\n")
        listed = self.fixture.run(self.jj, "file", "list", "-r", "@").stdout.replace("\\", "/")
        self.assertIn("scratch.log", listed)

    def test_commit_nothing_no_empty_commit(self):
        before = self.bookmark()
        before_head = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        result, _ = self.commit("feat(add-jj-backend): nothing\n\nSpecwright-Task: 3.1\n", "README.md", expected=1)
        self.assertEqual(result["error"], "nothing_to_commit")
        self.assertEqual(self.bookmark(), before)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), before_head)

        ignored_rule = self.repo / ".gitignore"
        ignored_rule.write_text("*.ignored\n", encoding="utf-8")
        self.fixture.run(self.jj, "file", "track", ".gitignore")
        self.fixture.run(self.jj, "commit", "-m", "fixture ignore rule")
        self.fixture.run(self.jj, "bookmark", "set", self.branch, "-r", "@-")
        before_ignored = self.bookmark()
        ignored = self.repo / "untracked.ignored"
        ignored.write_text("not in jj snapshot\n", encoding="utf-8")
        missing, _ = self.commit("feat(add-jj-backend): ignored file\n\nSpecwright-Task: 3.1\n",
                                 "untracked.ignored", expected=1)
        self.assertEqual(missing["error"], "path_not_tracked")
        self.assertIn("untracked.ignored", missing["message"])
        self.assertEqual(self.bookmark(), before_ignored)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), before_ignored)
        self.assertEqual(ignored.read_text(encoding="utf-8"), "not in jj snapshot\n")

    def test_commit_oversize_file_path_not_tracked(self):
        large = self.repo / "oversize.bin"
        large.write_bytes(b"x" * (2 * 1024 * 1024))
        changed = self.repo / "otherwise-changed.txt"
        changed.write_text("this would be committable\n", encoding="utf-8")
        before = self.bookmark()
        before_head = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()

        result, _ = self.commit("feat(add-jj-backend): oversize named path\n\nSpecwright-Task: 3.1\n",
                                "oversize.bin", "otherwise-changed.txt", expected=1)

        self.assertEqual(result["error"], "path_not_tracked")
        self.assertIn("oversize.bin", result["message"])
        reason = result["message"].lower().replace("oversize.bin", "")
        self.assertRegex(reason, r"ignored|snapshot|size|limit|too large|maximum")
        self.assertEqual(self.bookmark(), before)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), before_head)

    def test_commit_equivalent_path_spellings(self):
        """`./work/a.txt` and `work/../work` name snapshotted paths: they commit instead of stopping as not tracked."""
        (self.repo / "work").mkdir()
        (self.repo / "work" / "a.txt").write_text("a\n", encoding="utf-8")
        (self.repo / "work" / "b.txt").write_text("b\n", encoding="utf-8")
        result, _ = self.commit("feat(add-jj-backend): spelled\n\nSpecwright-Task: 3.1\n", "./work/a.txt")
        self.assertTrue(result["ok"], result)
        result, _ = self.commit("feat(add-jj-backend): spelled dir\n\nSpecwright-Task: 3.1\n", "work/../work/")
        self.assertTrue(result["ok"], result)
        names = self.git(self.repo, "ls-tree", "-r", "--name-only", self.bookmark()).stdout.split()
        self.assertIn("work/a.txt", names)
        self.assertIn("work/b.txt", names)

    def test_commit_directory_with_oversize_file_path_not_tracked(self):
        """A named directory is not covered by one snapshotted file: an oversize new file in it stops the commit,
        while an ignored oversize file there does not."""
        work = self.repo / "work"
        (work / "deep").mkdir(parents=True)
        (work / "small.txt").write_text("snapshotted\n", encoding="utf-8")
        (work / "deep" / "oversize.bin").write_bytes(b"x" * (2 * 1024 * 1024))
        before = self.bookmark()

        result, _ = self.commit("feat(add-jj-backend): directory\n\nSpecwright-Task: 3.1\n", "work", expected=1)

        self.assertEqual(result["error"], "path_not_tracked")
        self.assertEqual(result["path"], "work/deep/oversize.bin")
        self.assertIn("snapshot.max-new-file-size", result["message"])
        self.assertEqual(self.bookmark(), before)

        (self.repo / ".gitignore").write_text("*.bin\n", encoding="utf-8")
        result, _ = self.commit("feat(add-jj-backend): directory\n\nSpecwright-Task: 3.1\n", "work", ".gitignore")
        self.assertTrue(result["ok"], result)
        names = self.git(self.repo, "ls-tree", "-r", "--name-only", self.bookmark()).stdout.split()
        self.assertIn("work/small.txt", names)
        self.assertNotIn("work/deep/oversize.bin", names)


def require_jjenv_bash():
    import jjenv

    bash = jjenv.find_bash()
    if not bash:
        raise AssertionError("Git Bash required for task-cover.sh")
    return bash
