"""A paired change drives each repo with its own backend, and the gate lock is released on every stop.

The test plays the gate in `skills/specwright-branch/SKILL.md` (Store-backed changes): take the store lock, run
`[vcs] state` in both repos, `fetch-main` in the code repo, then `branch-create` in each, and release the lock.
"""
import json
import os
import shutil

import gitlog
import jjenv
from jjenv import Scratch, require_jj
from vcs_test_support import VCS, VcsTestCase, bash_path_env, bash_run

BRANCH = "feat/add-x"
READ_FETCH = "FETCH_HEAD-only read fetch"


class GateStop(Exception):
    """The gate stopped on a vcs.sh error; `result` is the JSON document it printed."""
    def __init__(self, step, result):
        super().__init__("%s: %s" % (step, result))
        self.step, self.result = step, result


class PairCase(VcsTestCase):
    store_vcs = "git"

    def setUp(self):
        super().setUp()
        self.jj = require_jj()
        self.scratch = Scratch()
        self.addCleanup(self.scratch.close)
        self.fixture = self.scratch.tracked_repo()
        self.code = self.fixture.path
        self.set_settings(self.code, "vcs: jj\nmain_branch: main\nplanning_store:\n  vcs: %s\n  main_branch: main\n"
                          % self.store_vcs)
        self.fixture.run(self.jj, "commit", "-m", "fixture Specwright settings")
        self.fixture.run(self.jj, "bookmark", "set", "main", "-r", "@-")
        self.store = self.root / "store"
        self._init_git(self.store)
        self.shim = gitlog.install(self.root / "shim", real_git=jjenv.real_git(),
                                   log_path=self.root / "git-calls.jsonl")
        self.env = {**self.shim.env, **bash_path_env(self.shim.path)}

    # the lock, as the skill's shell takes and releases it
    def lock_path(self):
        common = self.git(self.store, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
        return os.path.join(common, "specwright-gate.lock")

    def take_lock(self):
        lock = self.lock_path()
        os.mkdir(lock)  # atomic; fails when another session holds the lock
        with open(os.path.join(lock, "owner"), "w", encoding="utf-8", newline="\n") as stream:
            stream.write("time: now\nchange: add-x\ncode: %s\n" % self.code.as_posix())

    def release_lock(self):
        shutil.rmtree(self.lock_path())

    def vcs(self, command, *options, role="code"):
        """Run vcs.sh as the gate does; returns (exit status, the JSON document it printed)."""
        repo = self.code if role == "code" else self.store
        args = [VCS.as_posix(), command, "--repo", str(repo), "--role", role]
        if role == "store":
            args += ["--code", str(self.code)]
        done = bash_run(args + list(map(str, options)), cwd=repo, env=self.env, shim=self.shim.path)
        try:
            return done.returncode, json.loads(done.stdout)
        except ValueError:
            self.fail("vcs.sh did not emit one JSON document: %r (%s)" % (done.stdout, done.stderr))

    def step(self, name, command, *options, role="code"):
        """One gate call; a vcs.sh stop ends the gate."""
        status, result = self.vcs(command, *options, role=role)
        if status or not result.get("ok"):
            raise GateStop(name, result)
        return result

    def gate(self):
        """The store-backed gate, in the skill's order; every stop releases the lock first."""
        self.take_lock()
        try:
            code = self.step("code state", "state")
            self.assertTrue(code["on_main"] and code["clean"], code)
            self.step("code fetch-main", "fetch-main", "--quiet")
            store = self.step("store state", "state", role="store")
            self.assertTrue(store["on_main"] and store["clean"], store)
            created = {"code": self.step("code branch-create", "branch-create", "--branch", BRANCH),
                       "store": self.step("store branch-create", "branch-create", "--branch", BRANCH, role="store")}
        finally:
            self.release_lock()
        return created

    def branch_exists(self, repo):
        return self.git(repo, "rev-parse", "--verify", "--quiet", "refs/heads/" + BRANCH).returncode == 0

    def calls(self, action):
        return [call for call in self.shim.calls() if call["action"] == action]


class TestPairBackends(PairCase):
    def test_pair_jj_code_git_store_branch(self):
        self.assertFalse(os.path.exists(self.lock_path()))
        self.take_lock()
        self.assertTrue(os.path.isdir(self.lock_path()), "the gate holds the lock")
        with self.assertRaises(FileExistsError):
            os.mkdir(self.lock_path())  # a second session cannot take it
        self.release_lock()

        created = self.gate()

        self.assertEqual(created["code"]["backend"], "jj", created)
        self.assertEqual(created["store"]["backend"], "git", created)
        # the code repo has a bookmark made by jj: Git has the ref, HEAD stays detached, jj lists the bookmark
        self.assertTrue(self.branch_exists(self.code))
        listed = self.fixture.run(self.jj, "bookmark", "list", "exact:" + BRANCH, "-T", 'name ++ "\\n"').stdout.split()
        self.assertEqual(listed, [BRANCH])
        self.assertEqual(self.git(self.code, "branch", "--show-current").stdout.strip(), "")
        main = self.git(self.code, "rev-parse", "refs/heads/main").stdout.strip()
        self.assertEqual(self.git(self.code, "rev-parse", "refs/heads/" + BRANCH).stdout.strip(), main)
        # the store has a Git branch, checked out
        self.assertTrue(self.branch_exists(self.store))
        self.assertEqual(self.git(self.store, "branch", "--show-current").stdout.strip(), BRANCH)
        self.assertFalse((self.store / ".jj").exists())
        # Git writes in the whole gate: only the store's `checkout -b`; the code repo's writes were jj's
        writes = [call["argv"] for call in self.shim.calls() if call["write"]]
        self.assertEqual(writes, [["checkout", "-b", BRANCH]])
        self.assertEqual(self.calls("checkout")[0]["write"], True)
        self.assertFalse(os.path.exists(self.lock_path()), "the lock is released")


class TestPairStoreProbeFails(PairCase):
    store_vcs = "jj"

    def test_pair_store_probe_fails(self):
        self.assertFalse((self.store / ".jj").exists())

        with self.assertRaises(GateStop) as stop:
            self.gate()

        self.assertEqual(stop.exception.step, "store state")
        self.assertEqual(stop.exception.result["error"], "not_managed", stop.exception.result)
        # it stopped before either branch was made, and the lock is released
        self.assertFalse(self.branch_exists(self.code))
        self.assertFalse(self.branch_exists(self.store))
        self.assertEqual(self.git(self.store, "branch", "--show-current").stdout.strip(), "main")
        self.assertEqual(self.fixture.run(self.jj, "bookmark", "list", "exact:" + BRANCH).stdout.strip(), "")
        self.assertFalse(os.path.exists(self.lock_path()), "the lock is released on the stop")
        self.assertEqual([call["argv"] for call in self.shim.calls() if call["write"]], [])
        # the lock is free again for the next gate
        self.take_lock()
        self.release_lock()
