"""On GitButler a commit takes only its named paths into the change branch (real `but` in scratch repos)."""
import json
import shutil

from butenv import Scratch, require_but
from butwrap import ButWrap
from test_gitbutler_branch import GitButlerWorkspaceCase

ARCHIVE = "openspec/changes/archive/2026-10-30-add-c"
CHANGE = "openspec/changes/add-c"


class TestGitButlerCommit(GitButlerWorkspaceCase):
    def workspace(self, scratch, assign=None):
        """feat/a, feat/b and feat/add-c applied, each with one commit."""
        repo = self.managed(scratch)
        for branch in ("feat/a", "feat/b", "feat/add-c"):
            repo.but("branch", "new", branch)
        self.commit_on(repo, "feat/a", "a.txt")
        self.commit_on(repo, "feat/b", "b-committed.txt")
        self.commit_on(repo, "feat/add-c", "c.txt")
        return repo, ButWrap(scratch, assign)

    def write(self, repo, name, text):
        path = repo.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def tip(self, repo, branch):
        return self.git(repo.path, "rev-parse", "refs/heads/" + branch).stdout.strip()

    def tips(self, repo):
        return {name: self.tip(repo, name) for name in ("feat/a", "feat/b", "feat/add-c")}

    def commit(self, scratch, repo, wrap, message, *paths, expected=0, branch="feat/add-c"):
        message_file = self.root / "commit-message.txt"
        with message_file.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(message)
        result, _ = self.invoke("commit", "--branch", branch, "--message-file", message_file, "--", *paths,
                                repo=repo.path, env=wrap.env(scratch), expected=expected)
        return result

    def files(self, repo, rev):
        out = self.git(repo.path, "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", rev).stdout
        return sorted(line for line in out.splitlines() if line)

    def uncommitted(self, repo):
        status = json.loads(repo.but("status", "--json").stdout)
        return sorted(change["filePath"] for change in status["uncommittedChanges"])

    def test_commit_takes_only_named_paths(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)
            self.write(repo, "src/x.py", "print('x')\n")
            self.write(repo, "notes.txt", "notes\n")
            old, tips = self.tip(repo, "feat/add-c"), self.tips(repo)

            result = self.commit(scratch, repo, wrap, "feat(add-c): x\n", "src/x.py")

            self.assertTrue(result["ok"], result)
            new = self.tip(repo, "feat/add-c")
            self.assertEqual((result["backend"], result["branch"], result["commit"]), ("gitbutler", "feat/add-c", new))
            self.assertNotEqual(new, old)
            self.assertEqual(self.git(repo.path, "rev-parse", new + "^").stdout.strip(), old)
            self.assertEqual(self.files(repo, new), ["src/x.py"])
            self.assertEqual(self.uncommitted(repo), ["notes.txt"])
            self.assertEqual((repo.path / "notes.txt").read_text(encoding="utf-8"), "notes\n")
            for name in ("feat/a", "feat/b"):
                self.assertEqual(self.tip(repo, name), tips[name], name)
            # never a bare commit and never a CLI ID: every `but commit` call names -b and the path
            commits = [call for call in wrap.calls() if call[:1] == ["commit"]]
            self.assertEqual(len(commits), 1, commits)
            self.assertEqual(commits[0][1:3], ["-b", "feat/add-c"])
            self.assertEqual(commits[0][-1], "src/x.py")
            self.assertIn("--json", commits[0])

    def test_commit_path_owned_elsewhere_stops(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch, {"feat/b": ["src/b.py"]})
            self.write(repo, "src/b.py", "print('b')\n")
            self.write(repo, "src/x.py", "print('x')\n")
            before = (self.tips(repo), self.refs(repo), self.uncommitted(repo))

            result = self.commit(scratch, repo, wrap, "feat(add-c): b\n", "src/x.py", "src/b.py", expected=1)

            self.assertEqual(result["error"], "path_owned_elsewhere")
            self.assertIn("src/b.py", result["message"])
            self.assertIn("feat/b", result["message"])
            self.assertEqual(wrap.writes(), [], "a but write ran although a named path is owned elsewhere")
            self.assertEqual((self.tips(repo), self.refs(repo), self.uncommitted(repo)), before)

    def test_commit_short_path_not_cli_id(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)
            self.write(repo, "src/x.py", "print('x')\n")
            status = json.loads(repo.but("status", "--json").stdout)
            ident = next(c["cliId"] for c in status["uncommittedChanges"] if c["filePath"] == "src/x.py")
            self.assertTrue(2 <= len(ident) <= 4 and ident.isalpha(), ident)
            self.write(repo, ident, "named by an ID-looking name\n")  # a file called like src/x.py's short ID
            old, tips = self.tip(repo, "feat/add-c"), self.tips(repo)

            # `but commit` reads its arguments as CLI IDs: the commit holds exactly the named file (the pinned
            # `but` treats a path as a path), or vcs.sh stops with commit_mismatch naming the files it took
            result = self.commit(scratch, repo, wrap, "feat(add-c): id\n", ident)
            new = self.tip(repo, "feat/add-c")
            self.assertTrue(result["ok"], result)
            self.assertEqual(self.files(repo, new), [ident])  # exactly the named file, never src/x.py
            self.assertEqual(self.git(repo.path, "rev-parse", new + "^").stdout.strip(), old)
            self.assertEqual(self.uncommitted(repo), ["src/x.py"])
            for name in ("feat/a", "feat/b"):
                self.assertEqual(self.tip(repo, name), tips[name], name)

    def test_commit_keeps_trailers(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)
            self.write(repo, "src/x.py", "print('x')\n")
            message = ("feat(add-c): group 5 commit\n\nSome body text.\nSecond line.\n\n"
                       "Specwright-Task: 5.1\nSpecwright-Task: 5.2\n"
                       "Co-authored-by: Eval Bot <eval@example.invalid>\n")

            self.commit(scratch, repo, wrap, message, "src/x.py")

            body = self.git(repo.path, "log", "-1", "--format=%B", "refs/heads/feat/add-c").stdout
            self.assertEqual(body.rstrip("\n"), message.rstrip("\n"))

    def test_nothing_to_commit_and_bad_path(self):
        require_but()
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)
            self.write(repo, "src/x.py", "print('x')\n")
            before = self.tips(repo)
            result = self.commit(scratch, repo, wrap, "m\n", "c.txt", expected=1)  # committed already, unchanged
            self.assertEqual(result["error"], "nothing_to_commit")
            result = self.commit(scratch, repo, wrap, "m\n", "src/*.nomatch", expected=1)  # no file matches: Git Bash on Windows expands matching globs itself
            self.assertEqual(result["error"], "bad_path")
            self.assertEqual(wrap.writes(), [])
            self.assertEqual(self.tips(repo), before)
            # ./ spelling is normalized, and a directory is named with its slash
            result = self.commit(scratch, repo, wrap, "m\n", "./src", expected=0)
            self.assertEqual(self.files(repo, self.tip(repo, "feat/add-c")), ["src/x.py"])

    def archive(self, repo, change_only=False):
        """Commit the change directory on feat/add-c, then move it to the archive as `openspec archive` does."""
        self.write(repo, CHANGE + "/proposal.md", "proposal\n")
        self.write(repo, CHANGE + "/tasks.md", "- [ ] 1.1 x\n")
        repo.but("commit", "-b", "feat/add-c", "-m", "planning", "--json", CHANGE + "/")
        self.write(repo, "openspec/changes/other/proposal.md", "another change, uncommitted\n")
        (repo.path / "openspec" / "changes" / "archive").mkdir(parents=True)
        shutil.move(str(repo.path / CHANGE), str(repo.path / ARCHIVE))

    def test_archive_commit_names_exact_paths(self):
        require_but()
        # 1. every file renamed unchanged: naming the new directory and the old one commits both sides
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)
            self.archive(repo)
            old = self.tip(repo, "feat/add-c")
            result = self.commit(scratch, repo, wrap, "chore(add-c): archive\n", CHANGE + "/", ARCHIVE + "/")
            self.assertTrue(result["ok"], result)
            new = self.tip(repo, "feat/add-c")
            self.assertEqual(self.git(repo.path, "rev-parse", new + "^").stdout.strip(), old)
            self.assertEqual(self.files(repo, new), sorted([CHANGE + "/proposal.md", CHANGE + "/tasks.md",
                                                            ARCHIVE + "/proposal.md", ARCHIVE + "/tasks.md"]))
            self.assertEqual(self.uncommitted(repo), ["openspec/changes/other/proposal.md"])
            # the old directory path alone is never handed to but when only a rename's source covers it
            commits = [call for call in wrap.calls() if call[:1] == ["commit"]]
            self.assertEqual(len(commits), 1)
            self.assertNotIn(CHANGE + "/", commits[0])

        # 2. some files changed while moved (an added + a removed entry)
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)
            self.archive(repo)
            self.write(repo, ARCHIVE + "/tasks.md", "- [x] 1.1 x, done\n")
            result = self.commit(scratch, repo, wrap, "chore(add-c): archive\n", CHANGE + "/", ARCHIVE + "/")
            self.assertTrue(result["ok"], result)
            self.assertEqual(self.files(repo, self.tip(repo, "feat/add-c")),
                             sorted([CHANGE + "/proposal.md", CHANGE + "/tasks.md",
                                     ARCHIVE + "/proposal.md", ARCHIVE + "/tasks.md"]))
            self.assertEqual(self.uncommitted(repo), ["openspec/changes/other/proposal.md"])

        # 3. only the new directory named: the deletions were not named, so the commit is a mismatch
        with Scratch() as scratch:
            repo, wrap = self.workspace(scratch)
            self.archive(repo)
            old = self.tip(repo, "feat/add-c")
            result = self.commit(scratch, repo, wrap, "chore(add-c): archive\n", ARCHIVE + "/", expected=1)
            self.assertEqual(result["error"], "commit_mismatch", result)
            self.assertEqual(result["old_tip"], old)
            self.assertEqual(result["new_tip"], self.tip(repo, "feat/add-c"))
            self.assertIn(CHANGE + "/proposal.md", result["message"])  # names the file outside the named paths
