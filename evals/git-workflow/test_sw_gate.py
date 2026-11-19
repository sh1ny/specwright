"""`sw gate lock|show|unlock`, the store gate lock (planning-stores "sw gate lock takes the store gate lock", "sw gate show
reports the lock and changes nothing", "sw gate unlock releases only the lock it is given", "A stale gate lock is removed
only on the user's word", "The gate lock keeps its on-disk form", "Store-started sw calls name the code checkout").

Every case runs the built sw (SPECWRIGHT_SW) against a store made here (a git repository) and a code checkout that holds
only the VERSION stamp the entry check reads. Calls name the code checkout with a leading `--project`, as a skill does
from the store.

Run: python -m unittest evals/git-workflow/test_sw_gate.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cli"))
import swharness  # noqa: E402


class GateCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="swgate-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.sw = swharness.require_sw()
        self.version = json.loads(swharness.run_sw("version", "--json").stdout)["version"]
        self.env = swharness.fixture_env(SPECWRIGHT_HOME=self.root / "home", GIT_CONFIG_NOSYSTEM="1",
                                         GIT_CONFIG_GLOBAL=os.devnull)
        self.code = self.root / "code"
        (self.code / "openspec" / ".specwright").mkdir(parents=True)
        (self.code / "openspec" / ".specwright" / "VERSION").write_text(self.version + "\n", encoding="utf-8")
        self.store = self.root / "store"  # no VERSION: a gate call from here needs --project
        self.store.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.store)], env=self.env, check=True, capture_output=True)
        self.lock = self.store / ".git" / "specwright-gate.lock"

    def run_gate(self, *args, store=None, project=True, cwd=None):
        """Run `[--project <code>] gate <args>` from the store; returns (exit code, parsed document or None, stderr)."""
        lead = ["--project", self.code] if project else []
        done = subprocess.run([self.sw, *map(str, lead), "gate", *map(str, args)], cwd=cwd or self.store, env=self.env,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        document = json.loads(done.stdout) if done.stdout.strip() else None
        return done.returncode, document, done.stderr

    def take(self, branch="add-x", code=None):
        status, doc, err = self.run_gate("lock", "--store", self.store, "--branch", branch, "--code", code or self.code)
        self.assertEqual((status, doc and doc["ok"]), (0, True), (doc, err))
        return doc

    def owner_text(self):
        return (self.lock / "owner").read_text(encoding="utf-8")

    def write_lock(self, text, owner=True):
        """A lock as an earlier version's inline `mkdir` and `printf` left it."""
        self.lock.mkdir()
        if owner:
            (self.lock / "owner").write_text(text, encoding="utf-8", newline="\n")


class LockTests(GateCase):
    def test_lock_free_store(self):
        doc = self.take("add-x")
        self.assertEqual(doc["token"], doc["owner"]["token"])
        self.assertTrue(doc["token"])
        lines = dict(line.split(": ", 1) for line in self.owner_text().splitlines())
        self.assertEqual(sorted(lines), ["change", "code", "time", "token"])
        self.assertEqual((lines["change"], lines["code"], lines["token"]), ("add-x", str(self.code), doc["token"]))
        self.assertRegex(lines["time"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(sorted(p.name for p in self.lock.iterdir()), ["owner"], "no temporary file is left")

    def test_lock_already_held_is_gate_locked(self):
        self.write_lock("time: 2026-01-01T00:00:00Z\nchange: add-y\ncode: /d\n")
        before = self.owner_text()
        status, doc, err = self.run_gate("lock", "--store", self.store, "--branch", "add-x", "--code", self.code)
        self.assertEqual((status, doc["ok"], doc["error"]), (1, False, "gate_locked"), (doc, err))
        self.assertEqual((doc["owner"]["change"], doc["owner"]["code"], doc["owner"]["time"]),
                         ("add-y", "/d", "2026-01-01T00:00:00Z"))
        self.assertEqual(self.owner_text(), before)
        self.assertEqual(sorted(p.name for p in self.lock.iterdir()), ["owner"])

    def test_two_locks_at_once_one_wins(self):
        procs = [subprocess.Popen([self.sw, "--project", str(self.code), "gate", "lock", "--store", str(self.store),
                                   "--branch", name, "--code", str(self.code)], cwd=self.store, env=self.env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
                 for name in ("add-a", "add-b")]
        outs = [p.communicate(timeout=60)[0] for p in procs]
        docs = [json.loads(o) for o in outs]
        winners = [d for d in docs if d["ok"]]
        losers = [d for d in docs if not d["ok"]]
        self.assertEqual((len(winners), len(losers)), (1, 1), docs)
        self.assertEqual(losers[0]["error"], "gate_locked")
        self.assertIn("change: " + winners[0]["owner"]["change"], self.owner_text())
        # the loser may read the lock before the winner's owner file lands; the owner file above names the winner

    def test_lock_outside_a_repository_is_refused(self):
        plain = self.root / "plain"
        plain.mkdir()
        status, doc, err = self.run_gate("lock", "--store", plain, "--branch", "add-x", "--code", self.code, cwd=plain)
        self.assertEqual((status, doc["ok"], doc["error"]), (1, False, "not_a_repo"), (doc, err))
        self.assertEqual(sorted(p.name for p in plain.iterdir()), [])


class ShowTests(GateCase):
    def test_show_lock_held(self):
        taken = self.take("add-x")
        before = self.owner_text()
        status, doc, err = self.run_gate("show", "--store", self.store)
        self.assertEqual((status, doc["ok"], doc["held"]), (0, True, True), (doc, err))
        self.assertEqual((doc["owner"]["change"], doc["owner"]["code"], doc["owner"]["token"]),
                         ("add-x", str(self.code), taken["token"]))
        self.assertTrue(doc["owner"]["time"])
        self.assertEqual(self.owner_text(), before)

    def test_show_ownerless_lock(self):
        self.write_lock("", owner=False)
        status, doc, err = self.run_gate("show", "--store", self.store)
        self.assertEqual((status, doc["held"]), (0, True), (doc, err))
        self.assertEqual(doc["owner"], {"time": "", "change": "", "code": "", "token": ""})
        self.assertEqual(list(self.lock.iterdir()), [], "nothing was written")

    def test_show_no_lock(self):
        status, doc, err = self.run_gate("show", "--store", self.store)
        self.assertEqual((status, doc["ok"], doc["held"]), (0, True, False), (doc, err))
        self.assertFalse(self.lock.exists())


class UnlockTests(GateCase):
    def test_unlock_own_lock(self):
        token = self.take()["token"]
        status, doc, err = self.run_gate("unlock", "--store", self.store, "--token", token)
        self.assertEqual((status, doc["ok"], doc["removed"]), (0, True, True), (doc, err))
        self.assertFalse(self.lock.exists())

    def test_unlock_wrong_token_is_gate_not_owner(self):
        first = self.take("add-x")["token"]
        self.run_gate("unlock", "--store", self.store, "--token", first)
        second = self.take("add-x")["token"]
        status, doc, err = self.run_gate("unlock", "--store", self.store, "--token", first)
        self.assertEqual((status, doc["error"], doc["owner"]["token"]), (1, "gate_not_owner", second), (doc, err))
        self.assertTrue(self.lock.is_dir())
        self.assertIn("token: " + second, self.owner_text())

    def test_unlock_without_lock_removes_nothing(self):
        status, doc, err = self.run_gate("unlock", "--store", self.store, "--token", "t1")
        self.assertEqual((status, doc["ok"], doc["removed"]), (0, True, False), (doc, err))

    def test_stale_unlock_with_shown_token(self):
        self.take("add-y")
        shown = self.run_gate("show", "--store", self.store)[1]["owner"]
        status, doc, err = self.run_gate("unlock", "--stale", "--store", self.store, "--token", shown["token"])
        self.assertEqual((status, doc["removed"]), (0, True), (doc, err))
        self.assertFalse(self.lock.exists())

    def test_stale_unlock_of_replaced_lock_is_refused(self):
        self.take("add-y")
        shown = self.run_gate("show", "--store", self.store)[1]["owner"]
        self.run_gate("unlock", "--store", self.store, "--token", shown["token"])
        replacement = self.take("add-y")["token"]
        status, doc, err = self.run_gate("unlock", "--stale", "--store", self.store, "--token", shown["token"])
        self.assertEqual((status, doc["error"], doc["owner"]["token"]), (1, "gate_not_owner", replacement), (doc, err))
        self.assertTrue(self.lock.is_dir())

    def test_stale_unlock_of_update_lock_is_gate_update_held(self):
        text = ("time: 2026-01-01T00:00:00Z\nchange: specwright-update 0.5.0 -> 0.6.0\ncode: /a\ntoken: upd1\n")
        self.write_lock(text)
        status, doc, err = self.run_gate("unlock", "--stale", "--store", self.store, "--token", "upd1")
        self.assertEqual((status, doc["error"], doc["code"]), (1, "gate_update_held", "/a"), (doc, err))
        self.assertEqual(self.owner_text(), text)

    def test_stale_unlock_ownerless(self):
        self.write_lock("time: 2026-01-01T00:00:00Z\nchange: add-y\ncode: /d\n")  # an older version's lock: no token
        status, doc, err = self.run_gate("unlock", "--stale", "--ownerless", "--store", self.store)
        self.assertEqual((status, doc["removed"]), (0, True), (doc, err))
        self.assertFalse(self.lock.exists())
        self.take("add-x")  # a lock with a token is not ownerless
        status, doc, err = self.run_gate("unlock", "--stale", "--ownerless", "--store", self.store)
        self.assertEqual((status, doc["error"]), (1, "gate_not_owner"), (doc, err))
        self.assertTrue(self.lock.is_dir())


class OnDiskFormTests(GateCase):
    def test_mkdir_lock_from_older_version_is_held(self):
        self.write_lock("time: 2026-01-01T00:00:00Z\nchange: add-y\ncode: /d\n")
        status, doc, err = self.run_gate("lock", "--store", self.store, "--branch", "add-x", "--code", self.code)
        self.assertEqual((status, doc["error"]), (1, "gate_locked"), (doc, err))
        self.assertEqual((doc["owner"]["time"], doc["owner"]["change"], doc["owner"]["code"]),
                         ("2026-01-01T00:00:00Z", "add-y", "/d"))

    def test_sw_gate_lock_blocks_older_mkdir(self):
        self.take("add-x")
        with self.assertRaises(FileExistsError):
            os.mkdir(self.lock)  # the inline `mkdir "$L"` of earlier versions
        text = self.owner_text()  # and their `cat "$L/owner"`
        for prefix in ("time: ", "change: add-x", "code: " + str(self.code)):
            self.assertIn(prefix, text)


class StoreStartedTests(GateCase):
    def test_gate_commands_from_store_with_project(self):
        """The store has no VERSION: --project names the code checkout whose VERSION is checked."""
        self.assertFalse((self.store / "openspec").exists())
        token = self.take("add-x")["token"]
        status, doc, err = self.run_gate("show", "--store", self.store)
        self.assertEqual((status, doc["owner"]["token"]), (0, token), (doc, err))
        status, doc, err = self.run_gate("unlock", "--store", self.store, "--token", token)
        self.assertEqual((status, doc["removed"]), (0, True), (doc, err))
        self.assertFalse(self.lock.exists())

    def test_store_call_without_project_is_sw_mismatch(self):
        status, doc, err = self.run_gate("lock", "--store", self.store, "--branch", "add-x", project=False)
        self.assertEqual((status, doc["ok"], doc["error"]), (1, False, "sw_mismatch"), (doc, err))
        self.assertIn("no installed version found", doc["message"])
        self.assertFalse(self.lock.exists(), "nothing was done in the store")


if __name__ == "__main__":
    unittest.main()
