"""Packs in `update.sh plan` (pack-mechanism group 3): which packs are enabled, the requires closure and install order,
the store and user-level refusals, the ownership of pack skills (record, adoption, `unmanaged_skill`), `remove` items,
the document paths, `packs_previous` and update-script interface 2.

Every test runs the real script, from a download tree that holds the fixture packs of evals/packs/fixtures/packs/, against
a scratch checkout built by fixtures.py. Plan is read only: each refusal test also proves the checkout did not change.
The install itself (stage, swap, the record, recovery) is group 4 and is not tested here.

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


if __name__ == "__main__":
    unittest.main()
