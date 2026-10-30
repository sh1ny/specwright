"""jj read fetches move no bookmark; the jj pull fetches only main and only fast-forwards."""
import os
import subprocess
from pathlib import Path

import gitlog
import jjenv
from jjenv import Repo, Scratch, require_jj
from vcs_test_support import VcsTestCase, bash_path_env

READ_FETCH = "FETCH_HEAD-only read fetch"


class FetchPullCase(VcsTestCase):
    def setUp(self):
        super().setUp()
        self.jj = require_jj()
        self.scratch = Scratch()
        self.addCleanup(self.scratch.close)
        self.other = self.root / "other"
        self.must(self.root, "clone", str(self.scratch.origin), "other")
        settings = self.other / "openspec" / "specwright.yaml"
        settings.parent.mkdir(parents=True)
        settings.write_text("vcs: jj\nmain_branch: main\n", encoding="utf-8")
        self.origin_commit("chore: settings")
        self.shim = gitlog.install(self.root / "shim", real_git=jjenv.real_git(),
                                   log_path=self.root / "git-calls.jsonl")
        self.env = {**self.shim.env, **bash_path_env(self.shim.path)}

    def must(self, cwd, *args):
        result = self.git(cwd, *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def origin_commit(self, subject, name=None):
        """Commit one file in the other clone and push it to origin; return the new commit."""
        path = self.other / (name or "from-origin.txt")
        path.write_text(subject + "\n", encoding="utf-8")
        self.must(self.other, "add", "-A")
        self.must(self.other, "commit", "-m", subject)
        self.must(self.other, "push", "origin", "HEAD:refs/heads/main")
        return self.must(self.other, "rev-parse", "HEAD")

    def tracked(self):
        self.fixture = self.scratch.tracked_repo()
        self.repo = self.fixture.path
        return self.fixture

    def untracked(self):
        path = self.scratch.root / "untracked"
        subprocess.run([self.jj, "git", "init", "--colocate", str(path)], env=self.scratch.env,
                       capture_output=True, text=True, check=True)
        self.fixture = Repo(path, self.scratch.origin, self.scratch.env, self.scratch._git)
        self.fixture.git_configure_jj()
        self.repo = path
        self.fixture.run(jjenv.real_git(), "remote", "add", "origin", self.scratch.origin)
        self.fixture.run(self.jj, "git", "fetch", "--remote", "origin")
        self.fixture.run(self.jj, "bookmark", "create", "main", "-r", "main@origin")
        self.fixture.run(self.jj, "new", "main")
        return self.fixture

    def ref(self, name):
        return self.git(self.repo, "rev-parse", name).stdout.strip()

    def jj_log(self, revset, template="commit_id"):
        return self.fixture.run(self.jj, "log", "--no-graph", "-r", revset, "-T", template).stdout.strip()

    def conflicted(self):
        return self.fixture.run(self.jj, "bookmark", "list", "--conflicted", "-T", 'name ++ "\\n"').stdout.split()

    def remote_main(self):
        return self.git(self.scratch.origin, "rev-parse", "refs/heads/main").stdout.strip()

    def calls(self, action):
        return [call for call in self.shim.calls() if call["action"] == action]


class TestJjFetchMain(FetchPullCase):
    def test_fetch_main_tracked_moves_nothing(self):
        self.tracked()
        new = self.origin_commit("feat: origin moved")
        main, tracking = self.ref("refs/heads/main"), self.ref("refs/remotes/origin/main")
        self.assertNotEqual(main, new)

        result, _ = self.invoke("fetch-main", "--no-tags", repo=self.repo)

        self.assertEqual(result["ref"], new)
        self.assertEqual(self.ref("refs/heads/main"), main)
        self.assertEqual(self.ref("refs/remotes/origin/main"), tracking)
        self.assertEqual(self.jj_log("@-"), main)
        self.assertEqual(self.jj_log("main"), main)
        state, _ = self.invoke("state", repo=self.repo)
        self.assertTrue(state["on_main"])
        self.assertEqual(self.conflicted(), [])
        fetches = self.calls("fetch")
        self.assertEqual([call["argv"] for call in fetches],
                         [["fetch", "--no-tags", "--refmap=", "origin", "refs/heads/main"]])
        self.shim.assert_no_writes(allowed=(READ_FETCH,))
        # the archive check can read the fetched commit
        self.assertEqual(self.ref(new + "^{commit}"), new)

    def test_fetch_main_diverged_no_conflict(self):
        self.tracked()
        (self.repo / "local-merge.txt").write_text("local\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "merge: local")
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", "@-")
        local = self.ref("refs/heads/main")
        tracking = self.ref("refs/remotes/origin/main")
        new = self.origin_commit("feat: origin moved")

        result, _ = self.invoke("fetch-main", "--quiet", repo=self.repo)

        self.assertEqual(result["ref"], new)
        self.assertEqual(self.conflicted(), [])
        self.assertEqual(self.ref("refs/heads/main"), local)
        self.assertEqual(self.ref("refs/remotes/origin/main"), tracking)
        self.assertEqual(self.jj_log("main"), local)
        self.assertEqual([call["argv"] for call in self.calls("fetch")],
                         [["fetch", "-q", "--refmap=", "origin", "refs/heads/main"]])
        self.shim.assert_no_writes(allowed=(READ_FETCH,))


class TestJjPull(FetchPullCase):
    def pull(self, expected=0):
        return self.invoke("pull", repo=self.repo, expected=expected)

    def test_pull_fast_forward_tracked_and_untracked(self):
        for build in (self.tracked, self.untracked):
            with self.subTest(build.__name__):
                self.shim.log_path.unlink(missing_ok=True)
                build()
                new = self.origin_commit("feat: origin moved " + build.__name__, name=build.__name__ + ".txt")

                result, _ = self.pull()

                self.assertTrue(result["ok"], result)
                self.assertEqual(self.ref("refs/heads/main"), new)
                self.assertEqual(self.jj_log("main"), new)
                self.assertEqual(self.jj_log('"main"@"origin"'), new)
                self.assertEqual(self.jj_log("@-"), new)
                self.assertEqual(self.ref("HEAD"), new)
                self.assertEqual(self.jj_log("@", 'if(empty, "empty", "dirty")'), "empty")
                self.assertEqual(self.conflicted(), [])
                self.shim.assert_no_writes(allowed=(READ_FETCH,))

    def test_pull_keeps_bookmark_of_deleted_remote(self):
        self.tracked()
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "feat(add-x): work")
        self.fixture.run(self.jj, "bookmark", "create", "feat/add-x", "-r", "@-")
        self.fixture.run(self.jj, "git", "push", "--bookmark", 'exact:"feat/add-x"')
        branch = self.ref("refs/heads/feat/add-x")
        self.fixture.run(self.jj, "new", "main")
        self.must(self.scratch.origin, "update-ref", "-d", "refs/heads/feat/add-x")
        new = self.origin_commit("feat: origin moved")

        result, _ = self.pull()

        self.assertTrue(result["ok"], result)
        self.assertEqual(self.ref("refs/heads/main"), new)
        self.assertEqual(self.ref("refs/heads/feat/add-x"), branch)
        self.assertEqual(self.jj_log('"feat/add-x"'), branch)

    def test_pull_diverged_stops_before_jj_fetch(self):
        self.tracked()
        (self.repo / "local-only.txt").write_text("local\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "merge: local")
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", "@-")
        local = self.ref("refs/heads/main")
        tracking = self.ref("refs/remotes/origin/main")
        remote = self.origin_commit("feat: origin moved")

        result, _ = self.pull(expected=1)

        self.assertEqual(result["error"], "not_fast_forward", result)
        self.assertIn(local, result["message"])
        self.assertIn(remote, result["message"])
        self.assertEqual(self.conflicted(), [])
        self.assertEqual(self.ref("refs/heads/main"), local)
        self.assertEqual(self.ref("refs/remotes/origin/main"), tracking, "no jj fetch ran")

    def test_pull_local_ahead_succeeds_unmoved(self):
        self.tracked()
        (self.repo / "local-only.txt").write_text("local\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "merge: local")
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", "@-")
        local = self.ref("refs/heads/main")
        tracking = self.ref("refs/remotes/origin/main")

        result, _ = self.pull()

        self.assertTrue(result["ok"], result)
        self.assertEqual(self.ref("refs/heads/main"), local)
        self.assertEqual(self.ref("refs/remotes/origin/main"), tracking)
        self.assertEqual(self.jj_log("@-"), local)
        self.assertEqual(self.conflicted(), [])

    def test_pull_conflicted_main_set_back(self):
        self.tracked()
        base = self.ref("refs/heads/main")
        # local main holds X'; origin will hold Y1 (a child of X') but jj only knows the older tracking base
        (self.repo / "x-prime.txt").write_text("x\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "x-prime")
        x_prime = self.jj_log("@-")
        (self.repo / "y1.txt").write_text("y1\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "y1")
        y1 = self.jj_log("@-")
        self.fixture.run(self.jj, "new", base)
        (self.repo / "y2.txt").write_text("y2\n", encoding="utf-8")
        self.fixture.run(self.jj, "commit", "-m", "y2")
        y2 = self.jj_log("@-")
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", x_prime)
        self.fixture.run(self.jj, "new", "main")
        # push by a file:// URL, not origin's configured spelling, so no remote-tracking ref moves: origin gets Y1 now,
        # and Y2 once the read fetch is done
        origin = self.scratch.origin.resolve().as_uri()
        tracking = self.ref("refs/remotes/origin/main")
        self.must(self.repo, "push", origin, "%s:refs/heads/main" % y1, "--force")
        self.assertEqual(self.ref("refs/remotes/origin/main"), tracking, "the setup push moved origin/main")
        self.assertEqual(self.jj_log("main"), x_prime, "jj moved main after the setup push")
        hook = self.root / "hook.sh"
        real = jjenv.real_git().replace("\\", "/")
        with hook.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write('#!/bin/sh\n"%s" --git-dir="%s" push --force "%s" %s:refs/heads/main >/dev/null 2>&1\n' % (
                real, (self.repo / ".git").as_posix(), origin, y2))
        # a git wrapper which runs the hook once, right after the read fetch, as the shim does for logging
        shim_git = self.root / "shim" / "git"
        text = shim_git.read_text(encoding="utf-8")
        text = text.replace('exec "$SPECWRIGHT_REAL_GIT" "$@"',
                            '"$SPECWRIGHT_REAL_GIT" "$@"\nrc=$?\n'
                            'case " $* " in *" --refmap= "*) sh "%s" ;; esac\nexit $rc' % hook.as_posix())
        with shim_git.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        self.assertEqual(self.remote_main(), y1)

        result, _ = self.pull(expected=1)

        self.assertEqual(result["error"], "not_fast_forward", result)
        self.assertEqual(self.remote_main(), y2, "the hook moved origin between read and fetch")
        self.assertEqual(self.conflicted(), [])
        self.assertEqual(self.ref("refs/heads/main"), x_prime)
        self.assertEqual(self.jj_log("main"), x_prime)
