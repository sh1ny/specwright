"""Store ownership (scripts/update.sh, design D5): the `STORE` record, the four roles, the free-store rule, attribution of
changes in flight, and the rollback after a failed Step 7.

Every test runs the real script, from a download tree, against the store pair of fixtures.py (a store repo with its own
root plus code repos A and B that declare it). A has no `origin`, so its owner id is `path:<A's toplevel>`
(fx.owner_id). "VERSION is stamped" means the test writes the stamp the prompt's Step 7 would write, then runs finish;
"Step 5" is a test edit of the store's config.yaml followed by `note-config`.

Run: python -m unittest discover evals/update -p "test_store.py"
"""
import hashlib
import importlib.util
import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("update_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

RECORD = "openspec/.specwright/STORE"


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, self.tmp)

    def pair(self, version="0.5.0", record="a"):
        """The store pair with `version` installed in both projects. record "a": the store records `version`, owner A
        (committed); None: the store has no STORE."""
        dl = fx.make_mini_download(self.tmp / f"dl-{version}", version, 1)
        self.p = fx.make_store_pair(self.tmp, version, download=dl)
        self.a, self.b, self.store = self.p.a, self.p.b, self.p.store
        self.owner_a, self.owner_b = fx.owner_id(self.a), fx.owner_id(self.b)
        if record == "a":
            fx.write_store_record(self.store, version, self.owner_a)
        return self.p

    def download(self, version, edit=None, name=None):
        self.dl = fx.make_mini_download(self.tmp / (name or f"new-{version}"), version, 1, schema_edit=edit)
        return self.dl

    def run_sub(self, co, dl, sub, *extra):
        code, doc, out, err = fx.run_update(dl, [*co.args(), sub, *extra], env=self.p.env)
        self.assertIsNotNone(doc, f"{sub}: no JSON (exit {code}).\nstdout: {out}\nstderr: {err}")
        return code, doc, err

    def ok(self, co, dl, sub, *extra):
        code, doc, err = self.run_sub(co, dl, sub, *extra)
        self.assertEqual(code, 0, f"{sub}: {doc} {err}")
        return doc

    def update(self, co, dl):
        """plan, stage, swap; returns the three documents."""
        return [self.ok(co, dl, sub) for sub in ("plan", "stage", "swap")]

    def stamp_finish(self, co, dl, to):
        co.version_file.write_text(f"{to}\n")
        doc = self.ok(co, dl, "finish")
        self.assertTrue(doc["finished"])
        return doc

    # --- state readers

    @property
    def lock(self):
        return self.store / ".git" / "specwright-gate.lock"

    def record(self):
        p = fx.store_record_path(self.store)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def config(self):
        return (self.store / "openspec" / "config.yaml").read_bytes()

    def installed(self, co):
        return {"skills": fx.tree(co.skills[0]), "agents": fx.tree(co.agents["claude"]), "version": co.version_file.read_text()}

    def store_state(self):
        return {"schema": fx.tree(self.a.schema), "record": self.record(), "config": self.config()}

    def staging_left(self):
        return sorted(p.relative_to(r).as_posix() for r in (self.a.code, self.b.code, self.store)
                      for p in r.rglob(".specwright-update-*"))

    def porcelain(self):
        return fx.git(self.store, "status", "--porcelain", "--untracked-files=all").splitlines()


class TestStoreRecord(Base):
    def test_first_update_claims_store(self):
        self.pair("0.5.0", record=None)
        dl = self.download("0.6.0", fx.schema_edit_comment)
        plan, _, swap = self.update(self.a, dl)
        self.assertEqual((plan["role"], plan["store"]["owner"], plan["store"]["id"]), ("claim", None, self.owner_a))
        self.assertTrue(swap["store_written"])
        store = swap["store"]
        self.assertEqual((store["role"], store["claimed"], store["owner"], store["version"]), ("claim", True, self.owner_a, "0.6.0"))
        self.assertIn(RECORD, store["uncommitted"])  # left uncommitted, and listed
        self.assertIn(self.owner_a, store["message"])
        self.assertIn("owns the store's schema", store["message"])
        self.assertFalse(self.lock.exists())
        self.stamp_finish(self.a, dl, "0.6.0")
        self.assertEqual(self.record(), fx.record_text("0.6.0", self.owner_a))
        self.assertIn(RECORD, [x[3:] for x in self.porcelain() if x.startswith("??")])  # uncommitted in the store
        self.assertEqual(fx.tree(self.a.schema), fx.tree(dl / "schemas" / "specwright"))

    def test_second_claimer_names_owner(self):
        self.pair("0.5.0", record=None)
        dl = self.download("0.6.0", fx.schema_edit_comment)
        for co in (self.a, self.b):
            self.assertEqual(self.ok(co, dl, "plan")["role"], "claim")
        # B stages as a claimer, then A's claim lands in the store (A's own update would be refused for B's staging,
        # design D7, so its record is written directly): B's swap reads STORE again under the lock
        self.ok(self.b, dl, "stage")
        fx.write_store_record(self.store, "0.6.0", self.owner_a)
        store_before = self.store_state()
        b_before = self.installed(self.b)
        code, doc, err = self.run_sub(self.b, dl, "swap")
        self.assertEqual(code, 1, doc)
        self.assertEqual(doc["error"], "store_claimed")
        self.assertIn(self.owner_a, doc["message"])  # A, not the first claimer's uncommitted files
        self.assertNotIn("uncommitted", doc["message"])
        self.assertEqual(self.record(), fx.record_text("0.6.0", self.owner_a))
        self.assertEqual(self.store_state(), store_before)
        self.assertEqual(self.staging_left(), [], "B's refused swap took its staging with it")
        self.assertFalse(self.b.journal.exists())
        self.assertEqual(self.installed(self.b), b_before)  # B's skills, agents and VERSION: nothing written
        self.assertFalse(self.lock.exists(), "the lock B took is released")

    def test_unreadable_record_stops(self):
        self.pair("0.5.0", record=None)
        dl = self.download("0.6.0", fx.schema_edit_comment)
        for text, missing in (("version: 0.5.0\n", "owner"), (f"owner: {self.owner_a}\n", "version"), ("", "version")):
            with self.subTest(missing=missing, text=text):
                fx.write_store_record(self.store, None, None, text=text)
                a_before, store_before = fx.snapshot(self.a.code), fx.snapshot(self.store)
                for sub in ("plan", "stage"):
                    code, doc, err = self.run_sub(self.a, dl, sub)
                    self.assertEqual(code, 1, doc)
                    self.assertEqual(doc["error"], "refused")
                    self.assertIn("STORE", doc["message"])
                    self.assertIn(missing, doc["message"])
                    self.assertEqual(doc["refusals"][0]["code"], "store_record_unreadable")
                    self.assertEqual(fx.snapshot(self.a.code), a_before)  # nothing written, not even staging or a lock
                    self.assertEqual(fx.snapshot(self.store), store_before)

    def test_owner_id_from_origin(self):
        self.pair("0.5.0", record=None)
        dl = self.download("0.6.0")
        for url, want in (("https://user:tok@github.com./Acme/Widgets.git", "github.com/Acme/Widgets"),
                          ("git@github.com:Acme/Widgets.git", "github.com/Acme/Widgets"),
                          ("ssh://git@example.com:2222/team/repo", "example.com/team/repo")):
            with self.subTest(url=url):
                fx.git(self.a.code, "remote", "remove", "origin", check=False)
                fx.git(self.a.code, "remote", "add", "origin", url)
                self.assertEqual(self.ok(self.a, dl, "plan")["store"]["id"], want)
        fx.git(self.a.code, "remote", "remove", "origin")
        self.assertEqual(self.ok(self.a, dl, "plan")["store"]["id"], self.owner_a)


class TestOwner(Base):
    def test_owner_update_leaves_other_project_unchanged(self):
        self.pair("0.5.0")
        dl = self.download("0.6.0", fx.schema_edit_comment)
        b_before = fx.snapshot(self.b.code)
        plan, _, swap = self.update(self.a, dl)
        self.assertEqual((plan["role"], plan["store"]["owner"]), ("owner", self.owner_a))
        self.assertTrue(swap["store_written"])
        self.assertFalse(swap["store"]["claimed"])
        self.stamp_finish(self.a, dl, "0.6.0")
        self.assertEqual(fx.tree(self.a.schema), fx.tree(dl / "schemas" / "specwright"))
        self.assertEqual(self.record(), fx.record_text("0.6.0", self.owner_a))
        self.assertEqual(fx.snapshot(self.b.code), b_before)
        self.assertFalse(self.lock.exists())
        self.assertEqual(self.staging_left(), [])

    def test_other_project_patch_leaves_store_unchanged(self):
        self.pair("0.6.0")
        dl = self.download("0.6.1", fx.schema_edit_comment)  # even a changed schema is never written by another project
        store_before = fx.snapshot(self.store)
        plan, stage, swap = self.update(self.b, dl)
        self.assertEqual((plan["role"], plan["store"]["owner"]), ("other", self.owner_a))
        self.assertFalse(any(t["group"] == "schema" for t in plan["targets"]))  # code-side files only
        self.assertFalse(swap["store_written"])
        self.assertIn(self.owner_a, swap["store"]["message"])
        self.assertIn("store config managed by owner", swap["store"]["message"])
        self.stamp_finish(self.b, dl, "0.6.1")
        self.assertIn(b"<!-- v0.6.1 -->", next(v for k, v in fx.tree(self.b.skills[0]).items() if k.endswith("SKILL.md")))
        self.assertEqual(fx.snapshot(self.store), store_before)  # schema, config.yaml and STORE byte-identical, no staging
        self.assertEqual(fx.git(self.store, "status", "--porcelain"), "")

    def test_other_project_minor_refused_names_matching_tag(self):
        self.pair("0.5.0")
        dl = self.download("0.6.0", fx.schema_edit_comment)
        self.with_bounded(dl)
        fx.give_origin(dl, fx.make_tag_origin(self.tmp / "releases", ["v0.5.0", "v0.5.3", "v0.6.0"]))
        b_before, store_before = fx.snapshot(self.b.code), fx.snapshot(self.store)
        for sub in ("plan", "stage"):
            with self.subTest(sub):
                code, doc, err = self.run_sub(self.b, dl, sub)
                self.assertEqual(code, 1, doc)
                self.assertEqual(doc["error"], "refused")
                self.assertEqual(doc["refusals"][0]["code"], "store_version")
                for want in ("0.5.0", self.owner_a, "v0.5.3", "update the store first"):
                    self.assertIn(want, doc["message"])
                self.assertNotIn("v0.6.0", doc["message"])
                self.assertEqual(fx.snapshot(self.b.code), b_before)
                self.assertEqual(fx.snapshot(self.store), store_before)

    @staticmethod
    def with_bounded(dl):
        """The tag lookup loads <download>/skills/specwright-pr/scripts/bounded.py; the mini download has no specwright-pr."""
        bounded = dl / "skills" / "specwright-pr" / "scripts" / "bounded.py"
        bounded.parent.mkdir(parents=True, exist_ok=True)
        bounded.write_bytes((fx.ROOT / "skills" / "specwright-pr" / "scripts" / "bounded.py").read_bytes())

    def tag_lookup(self, url, env_extra):
        """plan as B (the other project) against a download whose origin is `url`; returns (exit code, doc, seconds).
        The mini download carries no specwright-pr, so bounded.py is copied in, as the full download has it."""
        self.pair("0.5.0")
        dl = self.download("0.6.0", fx.schema_edit_comment)
        self.with_bounded(dl)
        fx.give_origin(dl, url)
        self.b_before, self.store_before = fx.snapshot(self.b.code), fx.snapshot(self.store)
        t0 = time.monotonic()
        code, doc, out, err = fx.run_update(dl, [*self.b.args(), "plan"], env={**self.p.env, **env_extra})
        self.assertIsNotNone(doc, f"no JSON (exit {code}).\nstdout: {out}\nstderr: {err}")
        return code, doc, time.monotonic() - t0

    def test_hung_tag_lookup_names_deadline_exceeded(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(8)
        held = []
        stop = threading.Event()

        def accept():  # accepts and never answers: git ls-remote waits for the daemon's reply
            srv.settimeout(0.2)
            while not stop.is_set():
                try:
                    held.append(srv.accept()[0])
                except OSError:
                    pass

        t = threading.Thread(target=accept, daemon=True)
        t.start()
        self.addCleanup(lambda: (stop.set(), t.join(5), [c.close() for c in held], srv.close()))
        code, doc, secs = self.tag_lookup(f"git://127.0.0.1:{srv.getsockname()[1]}/releases", {"SPECWRIGHT_NET_DEADLINE": "2"})
        self.assertEqual(code, 1, doc)
        self.assertEqual(doc["refusals"][0]["code"], "store_version")
        for want in ("could not be named", "deadline_exceeded", "git ls-remote"):
            self.assertIn(want, doc["message"])
        self.assertLess(secs, 60 + 10)
        self.assertEqual(fx.snapshot(self.b.code), self.b_before)
        self.assertEqual(fx.snapshot(self.store), self.store_before)

    def test_oversized_tag_list_names_response_too_large(self):
        url = fx.make_tag_origin(self.tmp / "releases", ["v0.5.0", "v0.5.3", "v0.6.0", "v0.6.2", "v0.6.3"])
        code, doc, secs = self.tag_lookup(url, {"SPECWRIGHT_NET_MAX_BYTES": "100"})
        self.assertEqual(code, 1, doc)
        self.assertEqual(doc["refusals"][0]["code"], "store_version")
        for want in ("could not be named", "response_too_large", "git ls-remote"):
            self.assertIn(want, doc["message"])
        self.assertNotIn("release is v", doc["message"])  # no tag named from a partial list
        self.assertEqual(fx.snapshot(self.b.code), self.b_before)
        self.assertEqual(fx.snapshot(self.store), self.store_before)

    def test_other_project_swap_refused_when_store_moved_after_stage(self):
        self.pair("0.6.0")
        dl = self.download("0.6.1")
        b_before = fx.snapshot(self.b.code)
        self.ok(self.b, dl, "plan")
        self.ok(self.b, dl, "stage")
        fx.write_store_record(self.store, "0.7.0", self.owner_a)  # the owner moved the store after B staged
        store_before = fx.snapshot(self.store)
        code, doc, err = self.run_sub(self.b, dl, "swap")
        self.assertEqual(code, 1, doc)
        self.assertEqual(doc["error"], "other_store_version")
        for want in ("0.7.0", self.owner_a, "Nothing was written"):
            self.assertIn(want, doc["message"])
        self.assertEqual(fx.snapshot(self.b.code), b_before)  # installed files untouched; the refused swap removed its staging and journal
        self.assertEqual(fx.snapshot(self.store), store_before)
        self.assertEqual(self.staging_left(), [])


    def test_owner_swap_stops_when_store_version_advanced_after_stage(self):
        self.pair("0.6.0")
        dl = self.download("0.6.1")
        self.ok(self.a, dl, "plan")
        self.ok(self.a, dl, "stage")
        fx.write_store_record(self.store, "0.7.0", self.owner_a)  # another checkout of A advanced the store and committed it
        a_before, store_before = self.installed(self.a), self.store_state()
        code, doc, err = self.run_sub(self.a, dl, "swap")
        self.assertEqual(code, 1, doc)
        self.assertEqual(doc["error"], "store_version_changed")
        for want in ("0.7.0", self.owner_a, "0.6.0", "nothing was written", "rerun the update"):
            self.assertIn(want, doc["message"].replace("Rerun", "rerun"))
        self.assertEqual(self.store_state(), store_before)  # the schema and STORE are as the other checkout left them
        self.assertEqual(self.staging_left(), [])  # the refused swap removed its staging
        self.assertEqual(self.installed(self.a), a_before)  # nothing installed was touched
        self.assertFalse(self.lock.exists(), "the gate lock is released")


    def test_claim_swap_stops_when_same_repo_checkout_recorded_newer_version(self):
        self.pair("0.5.0", record=None)
        dl = self.download("0.6.0", fx.schema_edit_comment)
        self.assertEqual(self.ok(self.a, dl, "plan")["role"], "claim")
        self.ok(self.a, dl, "stage")
        fx.write_store_record(self.store, "0.7.0", self.owner_a)  # another checkout of A claimed it first, at a newer version
        a_before, store_before = self.installed(self.a), self.store_state()
        code, doc, err = self.run_sub(self.a, dl, "swap")
        self.assertEqual(code, 1, doc)
        self.assertEqual(doc["error"], "store_claimed")
        for want in ("0.7.0", self.owner_a, "0.6.0", "nothing was written"):
            self.assertIn(want, doc["message"])
        self.assertEqual(self.store_state(), store_before)  # the schema and STORE are as the other checkout left them
        self.assertEqual(self.staging_left(), [])  # the refused swap removed its staging
        self.assertEqual(self.installed(self.a), a_before)
        self.assertFalse(self.lock.exists(), "the gate lock is released")


class TestFreeStore(Base):
    def test_busy_store_patch_same_schema_code_side_only(self):
        self.pair("0.6.0")
        fx.git(self.store, "checkout", "-q", "-b", "feat/add-x")
        dl = self.download("0.6.1")  # the schema is byte-identical to 0.6.0's
        store_before = fx.snapshot(self.store)
        plan, _, swap = self.update(self.a, dl)
        self.assertEqual(plan["role"], "owner")
        self.assertFalse(swap["store_written"])
        self.assertIn("store schema already current", swap["store"]["message"])
        self.assertFalse(self.lock.exists())
        self.stamp_finish(self.a, dl, "0.6.1")
        self.assertIn(b"<!-- v0.6.1 -->", next(v for k, v in fx.tree(self.a.skills[0]).items() if k.endswith("SKILL.md")))
        self.assertEqual(fx.snapshot(self.store), store_before)  # files, config.yaml and STORE unchanged; staging gone
        self.assertEqual(fx.git(self.store, "branch", "--show-current"), "feat/add-x")
        self.assertEqual(self.staging_left(), [])

    def test_busy_store_schema_change_refused(self):
        self.pair("0.6.0")
        fx.git(self.store, "checkout", "-q", "-b", "feat/add-x")
        dl = self.download("0.7.0", fx.schema_edit_comment)
        self.ok(self.a, dl, "plan")
        self.ok(self.a, dl, "stage")
        a_before, store_before = self.installed(self.a), self.store_state()
        code, doc, err = self.run_sub(self.a, dl, "swap")
        self.assertEqual(code, 1, doc)
        self.assertEqual(doc["error"], "store_busy")
        self.assertIn("feat/add-x", doc["message"])
        self.assertIn("finish that change first", doc["message"])
        self.assertTrue(doc["unchanged"])
        self.assertEqual(self.installed(self.a), a_before)
        self.assertEqual(self.store_state(), store_before)
        self.assertFalse(self.lock.exists(), "the gate lock it took is released")

    def test_failed_git_status_makes_store_busy_and_nothing_is_swapped(self):
        self.pair("0.5.0")
        dl = self.download("0.6.0", fx.schema_edit_comment)
        self.ok(self.a, dl, "plan")
        self.ok(self.a, dl, "stage")
        a_before, store_before = self.installed(self.a), self.store_state()
        (self.store / ".git" / "index").write_bytes(b"garbage, not an index\n")
        code, doc, err = self.run_sub(self.a, dl, "swap")
        self.assertEqual((code, doc["error"]), (1, "store_busy"), doc)
        self.assertIn("git status failed", doc["message"])
        self.assertTrue(doc["unchanged"])
        self.assertEqual(self.installed(self.a), a_before)
        self.assertEqual(self.store_state(), store_before)
        self.assertFalse(self.lock.exists(), "the gate lock it took is released")

    def test_dirty_store_refused_then_clean_store_swaps(self):
        self.pair("0.5.0")
        dl = self.download("0.6.0", fx.schema_edit_comment)
        self.ok(self.a, dl, "plan")
        self.ok(self.a, dl, "stage")
        stray = self.store / "notes.txt"
        stray.write_text("x")
        code, doc, err = self.run_sub(self.a, dl, "swap")
        self.assertEqual((code, doc["error"]), (1, "store_busy"), doc)
        self.assertIn("notes.txt", doc["message"])
        self.assertFalse(self.lock.exists())
        self.assertEqual(self.record(), fx.record_text("0.5.0", self.owner_a))
        self.assertEqual(self.staging_left(), [])  # the refused swap removed its staging and journal
        stray.unlink()
        self.ok(self.a, dl, "plan")  # the rerun stages again and swaps once the store is clean
        self.ok(self.a, dl, "stage")
        self.assertTrue(self.ok(self.a, dl, "swap")["store_written"])

    def test_rename_into_own_staging_makes_store_busy(self):
        """A rename lists both paths: the source outside this update's staging makes the store busy."""
        self.pair("0.5.0")
        dl = self.download("0.6.0", fx.schema_edit_comment)
        self.ok(self.a, dl, "plan")
        self.ok(self.a, dl, "stage")
        staging = next((self.store / "openspec").glob(".specwright-update-schemas*")).relative_to(self.store).as_posix()
        fx.git(self.store, "mv", "openspec/config.yaml", f"{staging}/moved.yaml")
        self.assertTrue(any(x.startswith("R  ") for x in self.porcelain()), self.porcelain())
        a_before = self.installed(self.a)
        code, doc, err = self.run_sub(self.a, dl, "swap")
        self.assertEqual((code, doc["error"]), (1, "store_busy"), doc)
        self.assertIn("openspec/config.yaml", doc["message"])
        self.assertEqual(self.installed(self.a), a_before)
        self.assertEqual(self.record(), fx.record_text("0.5.0", self.owner_a))
        self.assertFalse(self.lock.exists())

    def test_own_staging_does_not_make_store_busy(self):
        self.pair("0.5.0")
        dl = self.download("0.6.0", fx.schema_edit_comment)
        self.ok(self.a, dl, "plan")
        self.ok(self.a, dl, "stage")
        lines = self.porcelain()
        self.assertTrue(lines)
        self.assertTrue(all(x.startswith("?? openspec/.specwright-update-schemas-") for x in lines), lines)  # only the staging
        swap = self.ok(self.a, dl, "swap")
        self.assertTrue(swap["store_written"])
        self.assertEqual(fx.tree(self.a.schema), fx.tree(dl / "schemas" / "specwright"))

    def test_store_main_from_planning_store_setting(self):
        self.pair("0.5.0")
        fx.git(self.store, "branch", "-m", "main", "trunk")  # neither main nor master exists
        dl = self.download("0.6.0", fx.schema_edit_comment)
        self.ok(self.a, dl, "plan")
        self.ok(self.a, dl, "stage")
        code, doc, err = self.run_sub(self.a, dl, "swap")
        self.assertEqual((code, doc["error"]), (1, "store_busy"), doc)  # no known main: the store is not on it
        self.assertIn("trunk", doc["message"])
        fx.write(self.a.code, "openspec/specwright.yaml", "planning_store:\n  login: bot\n  main_branch: trunk # the store's main\n")
        self.ok(self.a, dl, "plan")  # the refused swap removed its staging: plan and stage again
        self.ok(self.a, dl, "stage")
        self.assertTrue(self.ok(self.a, dl, "swap")["store_written"])


class TestStagingPerCheckout(Base):
    """Design D7 (#97): the store schema staging directory is keyed by the code checkout, so two checkouts that stage
    against one store never share (or delete) each other's `new/` and `old/`."""

    def journal(self, co):
        return json.loads(co.journal.read_text(encoding="utf-8"))

    def store_staging(self, co):
        return Path(self.journal(co)["store_staging"])

    def staged_pair(self, ignored=False):
        """Both checkouts claim the store and stage; neither has swapped. ignored: the store's .gitignore hides the
        staging directories, as Specwright's own does."""
        self.pair("0.5.0", record=None)
        if ignored:
            (self.store / ".gitignore").write_text(".specwright-update-*/\n", encoding="utf-8", newline="\n")
            fx.git(self.store, "add", ".gitignore")
            fx.git(self.store, "commit", "-q", "-m", "ignore update staging")
        dl = self.download("0.6.0", fx.schema_edit_comment)
        for co in (self.a, self.b):
            self.assertEqual(self.ok(co, dl, "plan")["role"], "claim")
        self.ok(self.a, dl, "stage")
        self.ok(self.b, dl, "stage")
        return dl

    def test_two_checkouts_stage_separately(self):
        self.staged_pair()
        sa, sb = self.store_staging(self.a), self.store_staging(self.b)
        self.assertNotEqual(sa, sb)
        for s in (sa, sb):
            self.assertEqual(s.parent, self.store / "openspec")
            self.assertTrue(s.name.startswith(".specwright-update-schemas-"), s.name)
            self.assertTrue((s / "new" / "specwright").is_dir(), s)
        found = sorted(p.name for p in (self.store / "openspec").glob(".specwright-update-schemas*"))
        self.assertEqual(found, sorted([sa.name, sb.name]))
        for co in (self.a, self.b):  # each journal names its own, for the group and for the store
            j = self.journal(co)
            self.assertEqual(next(g["staging"] for g in j["groups"] if g["kind"] == "schema"), j["store_staging"])
        # the code-side staging keeps its name
        self.assertTrue((self.a.code / ".claude" / ".specwright-update-skills" / "new").is_dir())

    def test_refused_swap_recover_keeps_other_rollback_copy(self):
        # two clones of one repository share an owner id (the same origin)
        self.pair("0.5.0", record=None)
        for co in (self.a, self.b):
            fx.git(co.code, "remote", "add", "origin", "https://example.com/team/app.git")
        fx.write_store_record(self.store, "0.5.0", "example.com/team/app")
        dl = self.download("0.6.0", fx.schema_edit_comment)
        a_before, store_before = self.installed(self.a), self.store_state()
        self.ok(self.a, dl, "plan")
        self.ok(self.a, dl, "stage")
        self.ok(self.a, dl, "swap")
        sa = self.store_staging(self.a)
        self.assertTrue((sa / "old" / "specwright").is_dir(), "A's rollback copy of the old schema")
        self.assertEqual(self.ok(self.b, dl, "plan")["role"], "owner")
        self.ok(self.b, dl, "stage")
        sb = self.store_staging(self.b)
        self.assertNotEqual(sa, sb)
        code, doc, err = self.run_sub(self.b, dl, "swap")
        self.assertEqual((code, doc["error"]), (1, "store_busy"), doc)
        self.assertFalse(sb.exists(), "B's refused swap removes its own staging directory")
        self.assertFalse(self.b.journal.exists(), "and its own journal")
        self.assertTrue((sa / "old" / "specwright").is_dir(), "B's recovery must leave A's old/ alone")
        rec = self.ok(self.a, dl, "recover", "--rollback")
        self.assertEqual(rec["message"], "rolled back to 0.5.0")
        self.assertEqual(self.store_state()["schema"], store_before["schema"])
        self.assertEqual(self.installed(self.a), a_before)
        self.assertEqual(self.staging_left(), [])

    def test_other_checkout_staging_makes_store_busy(self):
        dl = self.staged_pair()
        sa = self.store_staging(self.a)
        b_before = self.installed(self.b)
        code, doc, err = self.run_sub(self.b, dl, "swap")
        self.assertEqual((code, doc["error"]), (1, "store_busy"), doc)
        self.assertIn("another checkout's update is staged in the store", doc["message"])
        self.assertIn(sa.name, doc["message"])
        self.assertIn("finish or recover it by rerunning the update in that checkout", doc["message"])
        self.assertNotIn("uncommitted changes", doc["message"])  # ahead of the generic dirty-tree reason
        self.assertEqual(self.installed(self.b), b_before)
        self.assertFalse(self.lock.exists())
        self.assertFalse(self.b.journal.exists(), "B's staging and journal are gone")
        self.assertTrue((sa / "new" / "specwright").is_dir(), "A's staging is untouched")
        self.assertEqual([p.name for p in (self.store / "openspec").glob(".specwright-update-schemas*")], [sa.name])

    def test_other_checkout_staging_ignored_by_git_makes_store_busy(self):
        # `git status` omits ignored paths, so the staging directory is looked for on disk too
        dl = self.staged_pair(ignored=True)
        sa = self.store_staging(self.a)
        self.assertEqual(fx.git(self.store, "status", "--porcelain").strip(), "", "the staging is not ignored")
        b_before = self.installed(self.b)
        code, doc, err = self.run_sub(self.b, dl, "swap")
        self.assertEqual((code, doc["error"]), (1, "store_busy"), doc)
        self.assertIn("another checkout's update is staged in the store", doc["message"])
        self.assertIn(sa.name, doc["message"])
        self.assertEqual(self.installed(self.b), b_before)
        self.assertTrue((sa / "new" / "specwright").is_dir(), "A's staging is untouched")

    def test_both_staged_first_refused_swap_discards_and_other_swaps(self):
        dl = self.staged_pair()
        sa, sb = self.store_staging(self.a), self.store_staging(self.b)
        a_before = self.installed(self.a)
        code, doc, err = self.run_sub(self.a, dl, "swap")
        self.assertEqual((code, doc["error"]), (1, "store_busy"), doc)
        self.assertIn(sb.name, doc["message"])
        self.assertFalse(sa.exists(), "A's refused swap removes its own staging")
        self.assertFalse(self.a.journal.exists(), "and its own journal")
        self.assertEqual(self.installed(self.a), a_before)
        self.assertTrue((sb / "new" / "specwright").is_dir(), "B's staging is untouched")
        self.assertTrue(self.ok(self.b, dl, "swap")["store_written"])
        self.stamp_finish(self.b, dl, "0.6.0")
        self.assertEqual(self.staging_left(), [])
        # A reruns after B finished: plan and stage, and the swap is not refused for staging
        self.ok(self.a, dl, "plan")
        self.ok(self.a, dl, "stage")
        code, doc, err = self.run_sub(self.a, dl, "swap")
        self.assertNotIn("staged in the store", json.dumps(doc), doc)
        self.assertEqual(code, 0, doc)

    def test_recover_uses_legacy_shared_staging_from_journal(self):
        self.pair("0.5.0", record=None)
        dl = self.download("0.6.0", fx.schema_edit_comment)
        self.ok(self.a, dl, "plan")
        self.ok(self.a, dl, "stage")
        new = self.store_staging(self.a)
        legacy = new.parent / ".specwright-update-schemas"
        new.rename(legacy)
        text = self.a.journal.read_text(encoding="utf-8").replace(new.as_posix(), legacy.as_posix())
        self.a.journal.write_text(text, encoding="utf-8", newline="\n")
        self.assertEqual(self.journal(self.a)["format"], 1)
        self.assertEqual(self.store_staging(self.a), legacy)
        rec = self.ok(self.a, dl, "recover")
        self.assertEqual(rec["action"], "discarded")
        self.assertFalse(legacy.exists())
        self.assertFalse(self.a.journal.exists())
        self.assertEqual(self.staging_left(), [])


class TestAttribution(Base):
    def test_other_projects_change_refuses_owner_update(self):
        self.pair("0.5.0")
        fx.add_change_branch(self.store, "add-y")  # B's change: A has no feat/add-y
        dl = self.download("0.6.0", fx.schema_edit_comment)
        a_before, store_before = fx.snapshot(self.a.code), fx.snapshot(self.store)
        for sub in ("plan", "stage"):
            with self.subTest(sub):
                code, doc, err = self.run_sub(self.a, dl, sub)
                self.assertEqual(code, 1, doc)
                self.assertEqual(doc["error"], "refused")
                self.assertEqual(doc["refusals"][0]["code"], "other_project_change")
                self.assertEqual(doc["refusals"][0]["change"], "add-y")
                self.assertIn("add-y", doc["message"])
                self.assertEqual(fx.snapshot(self.a.code), a_before)
                self.assertEqual(fx.snapshot(self.store), store_before)  # the store schema stays 0.5.0
        self.assertEqual(fx.tree(self.a.schema), fx.tree(self.p.store / "openspec" / "schemas" / "specwright"))

    def test_owner_change_validated_and_update_completes(self):
        self.pair("0.5.0")
        fx.add_change_branch(self.store, "add-x")
        fx.git(self.a.code, "branch", "feat/add-x")  # A's own branch for the change
        dl = self.download("0.6.0", fx.schema_edit_comment)
        plan = self.ok(self.a, dl, "plan")
        self.assertEqual([(c["name"], c["status"], c["validated_against"]) for c in plan["inflight"]],
                         [("add-x", "validated", "0.6.0")])
        self.ok(self.a, dl, "stage")
        swap = self.ok(self.a, dl, "swap")
        self.assertEqual([(c["name"], c["validated_against"]) for c in swap["inflight"]], [("add-x", "0.6.0")])
        self.assertTrue(swap["store_written"])
        self.stamp_finish(self.a, dl, "0.6.0")
        self.assertEqual(fx.tree(self.a.schema), fx.tree(dl / "schemas" / "specwright"))


class TestStoreRollback(Base):
    def swapped(self, record="a"):
        """The owner's (or claimer's) swap done, Step 5 merged into the store's config.yaml and noted, Step 7 failed
        (no stamp). Returns (download, state before the update)."""
        self.pair("0.5.0", record=record)
        dl = self.download("0.6.0", fx.schema_edit_comment)
        self.before = {"store": self.store_state(), "a": self.installed(self.a), "b": fx.snapshot(self.b.code)}
        self.update(self.a, dl)
        merged = self.config() + b"# merged by Step 5\n"
        fx.write(self.store, "openspec/config.yaml", merged.decode())
        note = self.ok(self.a, dl, "note-config")
        self.assertEqual((note["subcommand"], note["sha256"]), ("note-config", hashlib.sha256(merged).hexdigest()))
        return dl

    def test_rollback_after_step7_restores_schema_config_and_record(self):
        dl = self.swapped()
        self.assertNotEqual(self.store_state(), self.before["store"])
        rec = self.ok(self.a, dl, "recover", "--rollback")
        self.assertEqual((rec["action"], rec["message"]), ("rolled-back", "rolled back to 0.5.0"))
        self.assertFalse(rec["store_written"])
        self.assertEqual(self.store_state(), self.before["store"])  # schema, config.yaml and STORE as before the update
        self.assertEqual(self.installed(self.a), self.before["a"])
        self.assertEqual(fx.snapshot(self.b.code), self.before["b"])
        self.assertFalse(self.lock.exists())
        self.assertFalse(self.a.journal.exists())
        self.assertEqual(self.staging_left(), [])
        self.assertEqual(fx.git(self.store, "status", "--porcelain"), "")

    def test_rollback_after_claim_removes_store_record(self):
        dl = self.swapped(record=None)
        self.assertIsNotNone(self.record())
        rec = self.ok(self.a, dl, "recover", "--rollback")
        self.assertEqual(rec["message"], "rolled back to 0.5.0")
        self.assertIsNone(self.record())  # a claim leaves no STORE behind
        self.assertEqual(self.store_state(), self.before["store"])
        self.assertFalse(self.lock.exists())
        self.assertEqual(fx.git(self.store, "status", "--porcelain"), "")

    def test_rollback_refused_when_store_busy_keeps_swapped_state(self):
        dl = self.swapped()
        swapped_store = self.store_state()
        fx.git(self.store, "checkout", "-q", "-b", "feat/add-u")  # B's new branch
        code, doc, err = self.run_sub(self.a, dl, "recover", "--rollback")
        self.assertEqual(code, 1, doc)
        self.assertEqual(doc["error"], "store_busy")
        self.assertIn("feat/add-u", doc["message"])
        self.assertEqual(self.store_state(), swapped_store)  # stopped before any rename
        self.assertTrue(self.a.journal.exists())
        self.assertIn(b"<!-- v0.6.0 -->", next(v for k, v in fx.tree(self.a.skills[0]).items() if k.endswith("SKILL.md")))
        self.assertFalse(self.lock.exists(), "the lock it took is released")
        # back on main the store is free again, and the rollback goes through
        fx.git(self.store, "checkout", "-q", "main")
        rec = self.ok(self.a, dl, "recover", "--rollback")
        self.assertEqual(rec["message"], "rolled back to 0.5.0")
        self.assertEqual(self.store_state(), self.before["store"])
    def test_rollback_stops_when_git_status_fails(self):
        dl = self.swapped()
        swapped_store = self.store_state()
        (self.store / ".git" / "index").write_bytes(b"garbage, not an index\n")
        code, doc, err = self.run_sub(self.a, dl, "recover", "--rollback")
        self.assertEqual((code, doc["error"]), (1, "store_busy"), doc)
        self.assertIn("git status failed", doc["message"])
        self.assertEqual(self.store_state(), swapped_store)
        self.assertTrue(self.a.journal.exists())
        self.assertFalse(self.lock.exists())


if __name__ == "__main__":
    unittest.main()
