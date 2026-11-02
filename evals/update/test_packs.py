"""Packs in `update.sh plan` (pack-mechanism group 3): which packs are enabled, the requires closure and install order,
the store and user-level refusals, the ownership of pack skills (record, adoption, `unmanaged_skill`), `remove` items,
the document paths, `packs_previous` and update-script interface 2.

Every test runs the real script, from a download tree that holds the fixture packs of evals/packs/fixtures/packs/, against
a scratch checkout built by fixtures.py. Plan is read only: each refusal test also proves the checkout did not change.
TestPackInstall (group 4) runs the install itself: stage, swap, the record packs.json, the removal of a pack's skills
and the recovery of a swap killed at a chosen mv (the mechanism of evals/update/test_interrupt.py).

Run: python -m unittest evals/update/test_packs.py
"""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("update_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

_mspec = importlib.util.spec_from_file_location("pack_merge", HERE.parent / "packs" / "merge.py")
merge = importlib.util.module_from_spec(_mspec)
_mspec.loader.exec_module(merge)

PACKS = HERE.parents[0] / "packs" / "fixtures" / "packs"
BASE, DOMAIN, WEB = "valid-ui-base", "valid-domain", "valid-web"
BASE_SKILL, DOMAIN_SKILL = "valid-ui-base-kit", "valid-domain-design"


def record(**packs):
    """A packs.json (format 1) text: {pack: [skill names]} are the enabled packs it lists."""
    return json.dumps({"format": 1,
                       "packs": {n: {"version": "0.5.0", "skills": s, "documents": {}, "init": {"questions": []}}
                                 for n, s in packs.items()},
                       "catalogue": []}, indent=2) + "\n"


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(fx.rmtree, self.tmp)

    def checkout(self, version="0.5.0", **kw):
        kw.setdefault("skills_dirs", (".claude/skills", ".agents/skills"))
        kw.setdefault("download", fx.make_mini_download(self.tmp / f"dl-{version}", version, 1))
        self.co = fx.make_checkout(self.tmp, version, **kw)
        return self.co

    def download(self, packs=(BASE, DOMAIN, WEB), version="0.6.0", name="dl-packs"):
        self.dl = fx.make_mini_download(self.tmp / name, version, 1)
        (self.dl / "packs").mkdir()
        for p in packs:
            shutil.copytree(PACKS / p, self.dl / "packs" / p)
        return self.dl

    def plan(self, *extra, co=None, dl=None, env=None):
        co, dl = co or self.co, dl or self.dl
        code, doc, out, err = fx.run_update(dl, [*co.args(), "plan", *extra], env=env)
        self.assertIsNotNone(doc, f"plan: no JSON (exit {code}).\nstdout: {out}\nstderr: {err}")
        return code, doc

    def put_record(self, text, co=None):
        fx.write((co or self.co).code, "openspec/.specwright/packs.json", text)

    def install_pack_skill(self, pack, skill, skills_dir=0, same=True, co=None):
        """A directory `skill` in the checkout's skills_dir-th skills directory: a copy of the download's, or a hand-edited one."""
        co = co or self.co
        dst = co.skills[skills_dir] / skill
        shutil.copytree(self.dl / "packs" / pack / "skills" / skill, dst)
        if not same:
            (dst / "SKILL.md").write_text("# hand copy\n", encoding="utf-8", newline="")
        return dst

    def refusals(self, doc, code):
        return [r for r in doc["refusals"] if r["code"] == code]

    def target_names(self, doc, group=None):
        return sorted(t["name"] for t in doc["targets"] if group in (None, t["group"]))


class TestPackPlan(Base):
    def test_requires_both_enabled_installs_both(self):
        self.checkout()
        self.download()
        before = fx.snapshot(self.co.code)
        code, doc = self.plan("--pack", DOMAIN, "--pack", BASE)
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc["refusals"], [])
        self.assertEqual([p["name"] for p in doc["packs"]], [BASE, DOMAIN])  # dependencies first
        self.assertEqual([p["skills"] for p in doc["packs"]], [[BASE_SKILL], [DOMAIN_SKILL]])
        for g in ("skills-1", "skills-2"):
            names = self.target_names(doc, g)
            self.assertIn(BASE_SKILL, names)
            self.assertIn(DOMAIN_SKILL, names)
            items = [t for t in doc["targets"] if t["group"] == g and t["name"] in (BASE_SKILL, DOMAIN_SKILL)]
            self.assertEqual([(t["name"], t["pack"], t["installed"]) for t in items],
                             [(BASE_SKILL, BASE, False), (DOMAIN_SKILL, DOMAIN, False)])
        self.assertEqual(fx.snapshot(self.co.code), before)  # plan is read only

    def test_missing_requirement_and_cycle_refused(self):
        self.checkout()
        self.download()
        before = fx.snapshot(self.co.code)
        code, doc = self.plan("--pack", DOMAIN)
        self.assertEqual(code, 1)
        self.assertEqual(doc["error"], "refused")
        (r,) = self.refusals(doc, "pack_requires")
        self.assertEqual((r["pack"], r["requires"]), (DOMAIN, BASE))
        self.assertIn(DOMAIN, r["message"])
        self.assertIn(BASE, r["message"])
        self.assertEqual(fx.snapshot(self.co.code), before)
        self.download(("cycle-a", "cycle-b"), name="dl-cycle")
        code, doc = self.plan("--pack", "cycle-a", "--pack", "cycle-b")
        self.assertEqual(code, 1)
        found = self.refusals(doc, "pack_cycle")
        self.assertTrue(found, doc["refusals"])
        for r in found:
            self.assertIn("cycle-a", r["message"])
            self.assertIn("cycle-b", r["message"])
        self.assertEqual(fx.snapshot(self.co.code), before)

    def test_no_packs_installs_nothing_extra(self):
        self.checkout()
        self.download()
        code, doc = self.plan()
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc["packs"], [])
        self.assertEqual(doc["packs_previous"], [])
        self.assertFalse([t for t in doc["targets"] if "pack" in t])
        self.assertFalse([n for n in self.target_names(doc) if n.startswith("valid-")])
        self.assertEqual(doc["orphans"], [])

    def test_unknown_pack_refused(self):
        self.checkout()
        self.download()
        before = fx.snapshot(self.co.code)
        code, doc = self.plan("--pack", "mobile")
        self.assertEqual(code, 1)
        (r,) = self.refusals(doc, "pack_unknown")
        self.assertEqual(r["pack"], "mobile")
        self.assertEqual(r["available"], sorted([BASE, DOMAIN, WEB]))
        self.assertIn("mobile", r["message"])
        for n in (BASE, DOMAIN, WEB):
            self.assertIn(n, r["message"])
        self.assertEqual(fx.snapshot(self.co.code), before)

    def test_pack_doc_path_refused(self):
        self.checkout()
        self.download()
        (self.co.code / "docs" / "adir").mkdir(parents=True)
        outside = self.tmp / "outside"
        outside.mkdir()
        link = self.co.code / "linked"
        try:
            link.symlink_to(outside, target_is_directory=True)
            leaves = "linked/gdd.md"
        except (OSError, NotImplementedError):
            leaves = None  # no symlinks here: the other three cases still run
        fx.commit_all(self.co.code, "chore: dirs")
        before = fx.snapshot(self.co.code)
        cases = ["../shared/gdd.md", "/tmp/gdd.md", "docs/adir", "docs/../../gdd.md"] + ([leaves] if leaves else [])
        for path in cases:
            with self.subTest(path):
                code, doc = self.plan("--pack", DOMAIN, "--pack", BASE, "--pack-doc", f"{DOMAIN}.gdd={path}")
                self.assertEqual(code, 1, doc)
                (r,) = self.refusals(doc, "pack_doc_path")
                self.assertEqual((r["pack"], r["document"], r["path"]), (DOMAIN, "gdd", path))
                for part in (DOMAIN, "gdd", path):
                    self.assertIn(part, r["message"])
                self.assertEqual(fx.snapshot(self.co.code), before)
                self.assertFalse(list((self.tmp).glob("shared")))
        self.assertTrue(link.is_symlink() or leaves is None)

    def test_pack_doc_reports_existence_and_rejects_unknown_documents(self):
        self.checkout()
        self.download()
        fx.write(self.co.code, "docs/mine.md", "# mine\n")
        code, doc = self.plan("--pack", DOMAIN, "--pack", BASE)
        self.assertEqual(code, 0, doc)
        (d,) = [p for p in doc["packs"] if p["name"] == DOMAIN][0]["documents"]
        self.assertEqual((d["id"], d["path"], d["exists"]), ("gdd", "docs/domain/gdd.md", False))
        code, doc = self.plan("--pack", DOMAIN, "--pack", BASE, "--pack-doc", f"{DOMAIN}.gdd=docs/mine.md")
        self.assertEqual(code, 0, doc)
        (d,) = [p for p in doc["packs"] if p["name"] == DOMAIN][0]["documents"]
        self.assertEqual((d["path"], d["exists"]), ("docs/mine.md", True))
        for spec in (f"{DOMAIN}.nope=docs/x.md", f"{WEB}.gdd=docs/x.md"):  # an id the pack lacks; a pack not enabled
            with self.subTest(spec):
                code, doc = self.plan("--pack", DOMAIN, "--pack", BASE, "--pack-doc", spec)
                self.assertEqual(code, 1, doc)
                self.assertEqual(len(self.refusals(doc, "pack_doc_unknown")), 1, doc["refusals"])
        code, doc = self.plan("--pack", DOMAIN, "--pack", BASE, "--pack-doc", "no-equals-sign")
        self.assertEqual(code, 1, doc)
        self.assertEqual(len(self.refusals(doc, "pack_doc_invalid")), 1, doc["refusals"])

    def test_repo_local_packs_allowed(self):
        self.checkout()
        self.download()
        code, doc = self.plan("--pack", WEB)
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc["role"], "none")
        self.assertEqual(self.refusals(doc, "packs_on_store"), [])

    def test_store_packs_refused(self):
        dl0 = fx.make_mini_download(self.tmp / "dl-0.5.0", "0.5.0", 1)
        pair = fx.make_store_pair(self.tmp, "0.5.0", download=dl0)
        self.download(version="0.5.1")
        fx.write_store_record(pair.store, "0.5.0", fx.owner_id(pair.a))
        for role, co in (("owner", pair.a), ("other", pair.b)):
            with self.subTest(role):
                before = {"code": fx.snapshot(co.code), "store": fx.snapshot(pair.store)}
                code, doc = self.plan("--pack", WEB, co=co, env=pair.env)
                self.assertEqual(doc["role"], role)
                self.assertEqual(code, 1, doc)
                self.assertEqual(len(self.refusals(doc, "packs_on_store")), 1, doc["refusals"])
                self.assertEqual({"code": fx.snapshot(co.code), "store": fx.snapshot(pair.store)}, before)
                code, doc = self.plan(co=co, env=pair.env)  # no pack, no refusal
                self.assertEqual(self.refusals(doc, "packs_on_store"), [])
        fx.git(pair.store, "rm", "-q", "-f", "openspec/.specwright/STORE")
        fx.commit_all(pair.store, "chore: no record")
        code, doc = self.plan("--pack", WEB, co=pair.a, env=pair.env)
        self.assertEqual(doc["role"], "claim")
        self.assertEqual(len(self.refusals(doc, "packs_on_store")), 1, doc["refusals"])

    def test_project_level_skills_allowed(self):
        self.checkout()
        self.download()
        code, doc = self.plan("--pack", WEB)
        self.assertEqual(code, 0, doc)
        self.assertEqual(self.refusals(doc, "packs_user_level"), [])

    def test_user_level_skills_refused(self):
        self.checkout()
        self.download()
        home = self.tmp / "home" / ".claude" / "skills"
        self.co.skills.append(home)
        before = fx.snapshot(self.co.code)
        code, doc = self.plan("--pack", WEB)
        self.assertEqual(code, 1, doc)
        (r,) = self.refusals(doc, "packs_user_level")
        self.assertEqual(r["dir"], fx.posix(home))
        self.assertIn(fx.posix(home), r["message"])
        self.assertEqual(fx.snapshot(self.co.code), before)
        self.assertFalse(home.exists())
        code, doc = self.plan()  # the same directory without a pack is Specwright's own business
        self.assertEqual(code, 0, doc)
        self.assertEqual(self.refusals(doc, "packs_user_level"), [])

    def test_failing_pack_installs_nothing(self):
        self.checkout()
        self.download(("bad-source", WEB))
        before = fx.snapshot(self.co.code)
        for sub in ("plan", "stage"):
            with self.subTest(sub):
                code, doc, out, err = fx.run_update(self.dl, [*self.co.args(), sub, "--pack", "bad-source", "--pack", WEB])
                self.assertEqual(code, 1, out)
                self.assertEqual(doc["error"], "refused")
                (r,) = [r for r in doc["refusals"] if r["pack"] == "bad-source"]
                self.assertEqual(r["code"], "external_pack_unsupported")
                self.assertEqual(fx.snapshot(self.co.code), before)
        _, check, _, _ = fx.run_update(self.dl, ["pack-check", "--pack", "bad-source"])
        self.assertEqual(check["refusals"], [r for r in doc["refusals"] if r["pack"] == "bad-source"])

    def test_removal_breaking_requirement_refused(self):
        self.checkout()
        self.download()
        self.put_record(record(**{BASE: [BASE_SKILL], DOMAIN: [DOMAIN_SKILL]}))
        self.install_pack_skill(BASE, BASE_SKILL)
        self.install_pack_skill(DOMAIN, DOMAIN_SKILL)
        before = fx.snapshot(self.co.code)
        code, doc = self.plan("--pack", DOMAIN)  # the user removed valid-ui-base from packs:, valid-domain stays
        self.assertEqual(code, 1)
        (r,) = self.refusals(doc, "pack_requires")
        self.assertEqual((r["pack"], r["requires"]), (DOMAIN, BASE))
        self.assertIn(DOMAIN, r["message"])
        self.assertIn(BASE, r["message"])
        self.assertEqual(fx.snapshot(self.co.code), before)

    def test_unmanaged_skill_refused(self):
        self.checkout()
        self.download()
        dst = self.install_pack_skill(BASE, BASE_SKILL, same=False)
        for rec in (None, record(**{WEB: []})):  # no record; a record that does not list the skill for this pack
            with self.subTest(record=rec is not None):
                if rec:
                    self.put_record(rec)
                before = fx.snapshot(self.co.code)
                code, doc = self.plan("--pack", BASE)
                self.assertEqual(code, 1, doc)
                (r,) = self.refusals(doc, "unmanaged_skill")
                self.assertEqual((r["pack"], r["skill"], r["path"]), (BASE, BASE_SKILL, fx.posix(dst)))
                self.assertIn(fx.posix(dst), r["message"])
                self.assertEqual(fx.snapshot(self.co.code), before)

    def test_identical_unrecorded_skill_adopted(self):
        self.checkout()
        self.download()
        dst = self.install_pack_skill(BASE, BASE_SKILL)
        before = fx.snapshot(self.co.code)
        code, doc = self.plan("--pack", BASE)
        self.assertEqual(code, 0, doc)
        self.assertEqual(self.refusals(doc, "unmanaged_skill"), [])
        (p,) = doc["packs"]
        self.assertEqual([(a["group"], a["name"], a["path"]) for a in p["adopted"]], [("skills-1", BASE_SKILL, fx.posix(dst))])
        self.assertEqual(fx.snapshot(self.co.code), before)
        self.put_record(record(**{BASE: [BASE_SKILL]}))  # once recorded it is the install's own, not adopted
        code, doc = self.plan("--pack", BASE)
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc["packs"][0]["adopted"], [])

    def test_hand_copy_of_disabled_pack_untouched(self):
        self.checkout()
        self.download()
        dst = self.install_pack_skill(DOMAIN, DOMAIN_SKILL, same=False)
        for rec in (None, record(**{WEB: []})):
            with self.subTest(record=rec is not None):
                if rec:
                    self.put_record(rec)
                before = fx.snapshot(self.co.code)
                code, doc = self.plan("--pack", WEB)  # valid-domain is in the download but not enabled
                self.assertEqual(code, 0, doc)
                self.assertNotIn(DOMAIN_SKILL, [o["name"] for o in doc["orphans"]])
                self.assertNotIn(DOMAIN_SKILL, self.target_names(doc))
                self.assertEqual(doc["refusals"], [])
                self.assertEqual(fx.snapshot(self.co.code), before)
        self.assertEqual((dst / "SKILL.md").read_text(encoding="utf-8"), "# hand copy\n")

    def test_unrelated_skill_untouched(self):
        self.checkout()
        self.download()
        fx.write(self.co.skills[0], "my-tool/SKILL.md", "# mine\n")
        self.put_record(record(**{BASE: [BASE_SKILL]}))
        before = fx.snapshot(self.co.code)
        for packs in ((), ("--pack", BASE)):
            code, doc = self.plan(*packs)
            self.assertEqual(code, 0, doc)
            self.assertNotIn("my-tool", [o["name"] for o in doc["orphans"]])
            self.assertNotIn("my-tool", self.target_names(doc))
            self.assertEqual(fx.snapshot(self.co.code), before)

    def test_plan_reports_interface_2(self):
        self.checkout()
        self.download()
        for packs in ((), ("--pack", WEB)):
            code, doc = self.plan(*packs)
            self.assertEqual(code, 0, doc)
            self.assertEqual(doc["interface"], 2)

    def test_recover_and_finish_report_interface_2(self):
        # with no journal, recover and finish answer from the shell; they must report the same interface as plan
        self.checkout()
        self.download()
        for sub in ("recover", "finish"):
            code, doc, out, err = fx.run_update(self.dl, [*self.co.args(), sub])
            self.assertIsNotNone(doc, f"{sub}: no JSON (exit {code}).\nstdout: {out}\nstderr: {err}")
            self.assertEqual(code, 0, doc)
            self.assertEqual(doc["interface"], 2, sub)

    def test_packs_previous_from_record(self):
        self.checkout()
        self.download()
        self.put_record(record(**{WEB: [], BASE: [BASE_SKILL]}))
        code, doc = self.plan("--pack", WEB)  # one of the two stays enabled; the record still says what was before
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc["packs_previous"], sorted([BASE, WEB]))

    def test_packs_previous_empty_without_record(self):
        self.checkout()
        self.download()
        code, doc = self.plan("--pack", WEB)
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc["packs_previous"], [])

    # --- beyond the test map: the plan data group 4 builds on ----------------------------------------------------

    def test_removed_pack_gets_remove_items_where_held(self):
        self.checkout()
        self.download()
        self.put_record(record(**{BASE: [BASE_SKILL]}))
        dst = self.install_pack_skill(BASE, BASE_SKILL, skills_dir=0)  # held in the first skills directory only
        before = fx.snapshot(self.co.code)
        code, doc = self.plan("--pack", WEB)
        self.assertEqual(code, 0, doc)
        removes = [t for t in doc["targets"] if t.get("type") == "remove"]
        self.assertEqual([(t["group"], t["name"], t["pack"], t["installed"]) for t in removes], [("skills-1", BASE_SKILL, BASE, True)])
        self.assertTrue(dst.is_dir())
        self.assertEqual(fx.snapshot(self.co.code), before)

    def test_recorded_skill_no_longer_shipped_is_orphan(self):
        self.checkout()
        self.download()
        self.put_record(record(**{BASE: [BASE_SKILL, "valid-ui-base-gone"]}))
        fx.write(self.co.skills[1], "valid-ui-base-gone/SKILL.md", "# gone\n")
        code, doc = self.plan("--pack", BASE)
        self.assertEqual(code, 0, doc)
        self.assertEqual([(o["group"], o["name"]) for o in doc["orphans"]], [("skills-2", "valid-ui-base-gone")])
        self.assertNotIn("valid-ui-base-gone", self.target_names(doc))


class TestPackInstall(Base):
    """Stage, swap and recover with packs. The fixture packs valid-ui-base and valid-domain each ship one skill."""

    def setUp(self):
        super().setUp()
        self.shims = fx.install_shims(self.tmp / "shims")
        self.counter = self.tmp / "count"

    def checkout(self, *a, **kw):
        co = super().checkout(*a, **kw)
        self.dl0 = co.download  # the download the checkout was installed from (version 0.5.0, no pack)
        return co

    def upd(self, co, sub, *extra, count=False, kill_at=None):
        return fx.run_update(self.dl, [*co.args(), sub, *extra], shim_dir=self.shims if count else None,
                             count_file=self.counter if count else None, kill_at=kill_at)

    @staticmethod
    def packs(*names):
        return [x for n in names for x in ("--pack", n)]

    def swapped(self, co, *extra):
        """Stage and swap (not stamped, not finished)."""
        for sub in ("stage", "swap"):
            code, doc, out, err = self.upd(co, sub, *extra)
            self.assertEqual(code, 0, f"{sub}: {out}{err}")

    def finished(self, co, *extra):
        self.swapped(co, *extra)
        co.version_file.write_text((self.dl / "VERSION").read_text(encoding="utf-8"), encoding="utf-8")
        code, doc, out, err = self.upd(co, "finish")
        self.assertEqual(code, 0, out + err)

    def record_file(self, co):
        return co.code / "openspec" / ".specwright" / "packs.json"

    def record_of(self, co):
        return json.loads(self.record_file(co).read_text(encoding="utf-8"))

    def download_skill(self, pack, skill):
        return fx.tree(self.dl / "packs" / pack / "skills" / skill)

    def core_skill(self):
        return sorted(p.name for p in (self.dl / "skills").glob("specwright-*"))[0]

    def leftovers(self, co):
        return sorted(p.relative_to(co.code).as_posix() for p in co.code.rglob(".specwright-update-*")) + \
            sorted(p.name for p in co.journal.parent.glob("update.*"))

    def tree_of(self, co):
        return {"skills": [fx.tree(d) for d in co.skills], "agents": fx.tree(co.agents["claude"]), "schema": fx.tree(co.schema),
                "record": self.record_file(co).read_bytes() if self.record_file(co).exists() else None}

    def assert_installed(self, co, *pairs):
        """Every skills directory holds the core skill and each (pack, skill) with the download's content."""
        core = self.core_skill()
        for d in co.skills:
            self.assertEqual(fx.tree(d / core), fx.tree(self.dl / "skills" / core), d)
            for pack, skill in pairs:
                self.assertEqual(fx.tree(d / skill), self.download_skill(pack, skill), d)

    def preinstall(self, co, *pairs):
        """The checkout as an earlier install of these (pack, skill) pairs left it: the skills in every directory and the record."""
        recorded = {}
        for pack, skill in pairs:
            recorded.setdefault(pack, []).append(skill)
            for i in range(len(co.skills)):
                self.install_pack_skill(pack, skill, skills_dir=i, co=co)
        text = record(**recorded)
        self.put_record(text, co=co)
        return text

    # --- interruption: a counting run lists the swap's mv/cp/rm calls; the killed run stops at the call after a chosen one

    def prepare_kill(self, co, *extra):
        """Save the checkout, run stage and a counted swap to list the calls, then restore the checkout."""
        self.pristine = self.tmp / "pristine"
        shutil.copytree(co.code, self.pristine)
        code, _, out, err = self.upd(co, "stage", *extra)
        self.assertEqual(code, 0, out + err)
        code, _, out, err = self.upd(co, "swap", count=True)
        self.assertEqual(code, 0, out + err)
        self.log = [line.split(" ", 2) for line in Path(f"{self.counter}.log").read_text(encoding="utf-8").splitlines()]
        self.reset(co)

    def reset(self, co):
        fx.rmtree(co.code)
        shutil.copytree(self.pristine, co.code)
        for f in (self.counter, Path(f"{self.counter}.log")):
            f.unlink(missing_ok=True)

    def mv_call(self, src_end, dst_part):
        """The number of the first logged mv whose source ends with `src_end` and whose destination contains `dst_part`."""
        for n, t, args in self.log:
            a = args.split(" ")
            if t == "mv" and len(a) == 2 and a[0].endswith(src_end) and dst_part in a[1]:
                return int(n)
        self.fail(f"no mv of ...{src_end} to ...{dst_part} in {self.log}")

    def killed_swap(self, co, after_call, *extra):
        """Restore, stage, and swap with the kill at the call after `after_call` (the journal write that follows it)."""
        self.reset(co)
        code, _, out, err = self.upd(co, "stage", *extra)
        self.assertEqual(code, 0, out + err)
        code, _, out, err = self.upd(co, "swap", count=True, kill_at=after_call + 1)
        self.assertNotEqual(code, 0, "the swap was meant to be killed")

    def recover(self, co, how):
        code, doc, out, err = self.upd(co, "recover", *(["--rollback"] if how == "rollback" else []))
        self.assertEqual(code, 0, out + err)
        self.assertEqual(doc["action"], "resumed" if how == "resume" else "rolled-back", doc)

    def stamp_and_finish(self, co):
        co.version_file.write_text("0.6.0\n")
        code, _, out, err = self.upd(co, "finish")
        self.assertEqual(code, 0, out + err)

    # --- the tests ---------------------------------------------------------------------------------------------------

    def test_pack_skills_installed_in_every_dir(self):
        co = self.checkout()
        self.download()
        self.finished(co, *self.packs(BASE, DOMAIN))
        self.assert_installed(co, (BASE, BASE_SKILL), (DOMAIN, DOMAIN_SKILL))
        self.assertEqual(self.leftovers(co), [])

    def test_interrupted_pack_install_recovered(self):
        co = self.checkout()
        self.download()
        args = self.packs(BASE, DOMAIN)
        before = self.tree_of(co)
        self.prepare_kill(co, *args)
        first = self.mv_call(f"/new/{BASE_SKILL}", fx.posix(co.skills[0] / BASE_SKILL))
        for how in ("resume", "rollback"):
            with self.subTest(how):
                self.killed_swap(co, first, *args)
                self.assertTrue((co.skills[0] / BASE_SKILL).is_dir())  # the first pack skill is in place ...
                self.assertFalse((co.skills[0] / DOMAIN_SKILL).exists())  # ... the next one is not
                self.recover(co, how)
                if how == "resume":
                    self.assert_installed(co, (BASE, BASE_SKILL), (DOMAIN, DOMAIN_SKILL))
                    self.stamp_and_finish(co)
                    self.assertEqual(sorted(self.record_of(co)["packs"]), sorted([BASE, DOMAIN]))
                else:
                    self.assertEqual(self.tree_of(co), before)
                    self.assertEqual(co.version_file.read_text(), "0.5.0\n")
                self.assertEqual(self.leftovers(co), [])

    def test_interrupted_pack_removal_recovered(self):
        co = self.checkout()
        self.download()
        old = self.preinstall(co, (BASE, BASE_SKILL))
        args = self.packs(WEB)  # valid-ui-base was recorded and is no longer enabled
        before = self.tree_of(co)
        self.prepare_kill(co, *args)
        moved = self.mv_call(fx.posix(co.skills[0] / BASE_SKILL), "/old/")
        for how in ("resume", "rollback"):
            with self.subTest(how):
                self.killed_swap(co, moved, *args)
                self.assertFalse((co.skills[0] / BASE_SKILL).exists())  # the removal is under way in the first directory ...
                self.assertTrue((co.skills[1] / BASE_SKILL).is_dir())  # ... and not yet in the second
                self.recover(co, how)
                if how == "resume":
                    for d in co.skills:
                        self.assertFalse((d / BASE_SKILL).exists(), d)
                    self.assert_installed(co)
                    self.stamp_and_finish(co)
                    self.assertEqual(self.record_of(co)["packs"].keys(), {WEB})
                else:
                    self.assertEqual(self.tree_of(co), before)
                    self.assertEqual(self.record_file(co).read_text(encoding="utf-8"), old)
                    self.assertEqual(co.version_file.read_text(), "0.5.0\n")
                self.assertEqual(self.leftovers(co), [])

    def test_record_matches_installed_packs(self):
        co = self.checkout()
        self.download()
        manifests = {n: json.loads((self.dl / "packs" / n / "pack.json").read_text(encoding="utf-8")) for n in (BASE, DOMAIN, WEB)}
        catalogue = [{"name": n, "description": manifests[n]["description"], "requires": manifests[n].get("requires", []),
                      "signals": manifests[n].get("signals", [])} for n in sorted(manifests)]
        self.finished(co, *self.packs(DOMAIN, BASE), "--pack-doc", f"{DOMAIN}.gdd=docs/mine.md")
        self.assertEqual(self.record_of(co), {
            "format": 1,
            "packs": {
                BASE: {"version": "0.6.0", "skills": [BASE_SKILL], "documents": {}, "init": {"questions": []}},
                DOMAIN: {"version": "0.6.0", "skills": [DOMAIN_SKILL], "documents": {"gdd": "docs/mine.md"},
                         "init": {"questions": manifests[DOMAIN]["init"]["questions"]}},
            },
            "catalogue": catalogue})
        co2 = fx.make_checkout(self.tmp, "0.5.0", skills_dirs=(".claude/skills",), name="code2", download=self.dl0)
        self.finished(co2)  # no pack: the record still exists, with no pack enabled and the whole catalogue
        self.assertEqual(self.record_of(co2), {"format": 1, "packs": {}, "catalogue": catalogue})

    def test_rollback_restores_record(self):
        co = self.checkout()
        self.download()
        old = self.preinstall(co, (BASE, BASE_SKILL))
        self.swapped(co, *self.packs(WEB))
        self.assertEqual(self.record_of(co)["packs"].keys(), {WEB})
        self.recover(co, "rollback")
        self.assertEqual(self.record_file(co).read_text(encoding="utf-8"), old)
        self.assertTrue(all((d / BASE_SKILL).is_dir() for d in co.skills))
        co2 = fx.make_checkout(self.tmp, "0.5.0", skills_dirs=(".claude/skills",), name="code2", download=self.dl0)
        self.swapped(co2, *self.packs(WEB))
        self.assertTrue(self.record_file(co2).is_file())
        self.recover(co2, "rollback")
        self.assertFalse(self.record_file(co2).exists())  # absent before, absent after
        self.assertEqual(self.leftovers(co2), [])

    def test_removing_pack_removes_skills(self):
        co = self.checkout()
        self.download()
        self.preinstall(co, (BASE, BASE_SKILL), (DOMAIN, DOMAIN_SKILL))
        fx.write(co.code, "docs/domain/gdd.md", "# my game design\n")
        mine = fx.snapshot(co.code / "docs")
        self.finished(co, *self.packs(WEB))
        for d in co.skills:
            self.assertFalse((d / BASE_SKILL).exists(), d)
            self.assertFalse((d / DOMAIN_SKILL).exists(), d)
        self.assertEqual(self.record_of(co)["packs"].keys(), {WEB})
        self.assertEqual(fx.snapshot(co.code / "docs"), mine)  # a pack's documents are the project's
        self.assertEqual(self.leftovers(co), [])

    def test_packs_previous_from_journal_after_swap(self):
        co = self.checkout()
        self.download()
        self.preinstall(co, (BASE, BASE_SKILL))
        self.swapped(co, *self.packs(WEB))  # the run stops here: no Step 5, no stamp, no finish
        self.assertEqual(self.record_of(co)["packs"].keys(), {WEB})
        self.assertEqual(json.loads(co.journal.read_text(encoding="utf-8"))["prev_packs"], [BASE])
        code, doc = self.plan(*self.packs(WEB))
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc["journal"]["phase"], "swapped")
        self.assertEqual(doc["packs_previous"], [BASE])  # the journal's, not the new packs.json's

    def test_format_1_journal_still_recovered(self):
        co = self.checkout()
        self.download()
        code, _, out, err = self.upd(co, "stage")
        self.assertEqual(code, 0, out + err)
        text = co.journal.read_text(encoding="utf-8")
        self.assertIn('"format": 2', text)
        co.journal.write_text(text.replace('"format": 2', '"format": 1'), encoding="utf-8", newline="")  # what a 0.x download wrote
        self.recover_discards(co)
        code, _, out, err = self.upd(co, "stage")
        co.journal.write_text(co.journal.read_text(encoding="utf-8").replace('"format": 2', '"format": 3'), encoding="utf-8", newline="")
        code, doc, out, err = self.upd(co, "recover")
        self.assertEqual((code, doc["error"]), (1, "journal_unreadable"), out)
        self.assertIn("format 3", doc["message"])

    def recover_discards(self, co):
        code, doc, out, err = self.upd(co, "recover")
        self.assertEqual((code, doc["action"]), (0, "discarded"), out + err)
        self.assertEqual(self.leftovers(co), [])

    # --- group 8: the whole life of two packs ------------------------------------------------------------------------

    def config_of(self, co):
        return (co.root / "openspec" / "config.yaml").read_text(encoding="utf-8")

    def pack_lines(self, text, pack):
        return [ln for ln in text.splitlines() if f"[pack:{pack}] " in ln]

    def one_run(self, co, *packs):
        """The README sequence of Steps 4-7 for a repo-local project: plan, stage, swap, the Step 5 merge (test helper),
        note-config, pack-verify, stamp, finish, pack-docs. Returns (plan document, pack-docs document)."""
        code, plan = self.plan(*self.packs(*packs), co=co)
        self.assertEqual(code, 0, plan)
        for sub in ("stage", "swap"):
            code, doc, out, err = self.upd(co, sub, *self.packs(*packs))
            self.assertEqual(code, 0, f"{sub}: {out}{err}")
        manifests = [(p["name"], json.loads((self.dl / "packs" / p["name"] / "pack.json").read_text(encoding="utf-8")))
                     for p in plan["packs"]]
        template = (self.dl / "templates" / "openspec" / "config.yaml").read_text(encoding="utf-8")
        text, unmanaged = merge.merge_config(self.config_of(co), template, manifests, plan["packs_previous"])
        self.assertEqual(unmanaged, [])
        (co.root / "openspec" / "config.yaml").write_text(text, encoding="utf-8", newline="\n")
        code, doc, out, err = self.upd(co, "note-config")
        self.assertEqual((code, doc["ok"]), (0, True), out + err)
        verify = ["pack-verify"] + [x for n in plan["packs_previous"] for x in ("--previous", n)]
        code, doc, out, err = self.upd(co, *verify)
        self.assertEqual((code, doc["ok"], doc["problems"]), (0, True, []), out + err)
        co.version_file.write_text((self.dl / "VERSION").read_text(encoding="utf-8"), encoding="utf-8")
        code, doc, out, err = self.upd(co, "finish")
        self.assertEqual(code, 0, out + err)
        code, docs, out, err = self.upd(co, "pack-docs")
        self.assertEqual((code, docs["ok"]), (0, True), out + err)
        return plan, docs

    def test_end_to_end_install_and_remove_packs(self):
        co = self.checkout()
        self.download()
        gdd = co.code / "docs" / "domain" / "gdd.md"

        # install both packs
        plan, docs = self.one_run(co, DOMAIN, BASE)
        self.assertEqual([p["name"] for p in plan["packs"]], [BASE, DOMAIN])
        self.assertEqual(plan["packs_previous"], [])
        self.assertEqual([(d["pack"], d["id"], d["path"], d["status"]) for d in docs["documents"]],
                         [(DOMAIN, "gdd", "docs/domain/gdd.md", "created")])
        self.assert_installed(co, (BASE, BASE_SKILL), (DOMAIN, DOMAIN_SKILL))
        text = self.config_of(co)
        self.assertTrue(self.pack_lines(text, BASE))
        self.assertTrue(self.pack_lines(text, DOMAIN))
        self.assertEqual(sorted(self.record_of(co)["packs"]), sorted([BASE, DOMAIN]))
        self.assertEqual(co.version_file.read_text(encoding="utf-8").strip(), "0.6.0")
        self.assertEqual(self.leftovers(co), [])
        self.assertTrue(gdd.is_file())
        template = (self.dl / "packs" / DOMAIN / "documents" / "gdd.md").read_bytes()
        self.assertEqual(gdd.read_bytes(), template)
        with open(gdd, "a", encoding="utf-8", newline="") as f:  # the project's own work in the document
            f.write("\nMy own design notes.\n")
        mine = gdd.read_bytes()

        # remove both: no --pack at all
        plan, docs = self.one_run(co)
        self.assertEqual(plan["packs"], [])
        self.assertEqual(plan["packs_previous"], sorted([BASE, DOMAIN]))
        removes = {(t["group"], t["name"]) for t in plan["targets"] if t.get("type") == "remove"}
        self.assertEqual(removes, {(g, n) for g in ("skills-1", "skills-2") for n in (BASE_SKILL, DOMAIN_SKILL)})
        self.assertEqual(docs["documents"], [])
        for d in co.skills:
            self.assertFalse((d / BASE_SKILL).exists(), d)
            self.assertFalse((d / DOMAIN_SKILL).exists(), d)
        self.assert_installed(co)
        self.assertNotIn("[pack:", self.config_of(co))
        self.assertEqual(self.record_of(co)["packs"], {})
        self.assertEqual(gdd.read_bytes(), mine)  # the document is the project's: kept, unchanged
        self.assertEqual(self.leftovers(co), [])


if __name__ == "__main__":
    unittest.main()
