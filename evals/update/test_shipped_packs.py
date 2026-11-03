"""The shipped packs through the real installer (change gamedev-pack, design D6 (e) and (f)).

The harness is evals/update/test_packs.py (`Base`, `TestPackInstall`): its download is given the repository's own
`packs/` instead of the fixture packs. ShippedInstall drives plan, stage, swap and finish; Signals matches the signals
of the catalogue the install writes in packs.json against file lists, under both readings of `**/`.

Run: python -m unittest evals/update/test_shipped_packs.py
"""
import importlib.util
import shutil
import unittest
from fnmatch import fnmatchcase
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("update_test_packs", HERE / "test_packs.py")
tp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tp)
fx = tp.fx

REPO_PACKS = HERE.parents[1] / "packs"
THREE = ("ui-prototyping", "gamedev", "godot")
SIX = {
    "ui-prototyping": ["ui-prototyping-html"],
    "gamedev": ["gamedev-design", "gamedev-narrative", "gamedev-ux", "gamedev-playtest"],
    "godot": ["godot-engine"],
}
GDD = "docs/game/gdd.md"


class Shipped(tp.Base):
    """tp.Base plus the helpers of tp.TestPackInstall that do not depend on its fixture constants."""

    # borrowed as they are: plain functions of self
    upd = tp.TestPackInstall.upd
    packs = staticmethod(tp.TestPackInstall.packs)
    swapped = tp.TestPackInstall.swapped
    finished = tp.TestPackInstall.finished
    record_file = tp.TestPackInstall.record_file
    record_of = tp.TestPackInstall.record_of
    core_skill = tp.TestPackInstall.core_skill
    leftovers = tp.TestPackInstall.leftovers
    config_of = tp.TestPackInstall.config_of
    pack_lines = tp.TestPackInstall.pack_lines
    one_run = tp.TestPackInstall.one_run

    def checkout(self, *a, **kw):
        co = super().checkout(*a, **kw)
        self.dl0 = co.download  # version 0.5.0, no pack
        return co

    def download(self, packs=THREE, version="0.6.0", name="dl-shipped"):
        for p in THREE:
            self.assertTrue((REPO_PACKS / p / "pack.json").is_file(), f"packs/{p}/pack.json does not exist")
        self.dl = fx.make_mini_download(self.tmp / name, version, 1)
        (self.dl / "packs").mkdir()
        for p in packs:
            shutil.copytree(REPO_PACKS / p, self.dl / "packs" / p, ignore=shutil.ignore_patterns("__pycache__"))
        return self.dl

    def pack_skill_names(self, skills_dir):
        return sorted(p.name for p in Path(skills_dir).iterdir() if p.is_dir() and not p.name.startswith("specwright-"))


class ShippedInstall(Shipped):
    def test_all_three_install_six_skills(self):
        co = self.checkout()
        self.download()
        self.finished(co, *self.packs(*THREE))
        every = sorted(s for names in SIX.values() for s in names)
        self.assertEqual(len(every), 6)
        for d in co.skills:
            self.assertEqual(self.pack_skill_names(d), every, d)
            for pack, names in SIX.items():
                for skill in names:
                    self.assertEqual(fx.tree(d / skill), fx.tree(self.dl / "packs" / pack / "skills" / skill), (d, skill))
        recorded = self.record_of(co)["packs"]
        self.assertEqual(sorted(recorded), sorted(THREE))
        for pack, names in SIX.items():
            self.assertEqual(sorted(recorded[pack]["skills"]), sorted(names), pack)
        self.assertEqual(self.leftovers(co), [])

    def test_gamedev_without_ui_prototyping_refused(self):
        co = self.checkout()
        self.download()
        before = fx.snapshot(co.code)
        code, doc = self.plan("--pack", "gamedev")
        self.assertEqual(code, 1, doc)
        self.assertEqual(doc["error"], "refused")
        found = self.refusals(doc, "pack_requires")
        self.assertEqual(len(found), 1, doc["refusals"])
        r = found[0]
        self.assertEqual((r["pack"], r["requires"]), ("gamedev", "ui-prototyping"))
        self.assertIn("gamedev", r["message"])
        self.assertIn("ui-prototyping", r["message"])
        self.assertEqual(fx.snapshot(co.code), before)

    def test_godot_alone(self):
        co = self.checkout()
        self.download()
        code, doc = self.plan("--pack", "godot")
        self.assertEqual(code, 0, doc)
        self.assertEqual(self.refusals(doc, "pack_requires"), [])
        self.assertEqual([(p["name"], p["skills"]) for p in doc["packs"]], [("godot", ["godot-engine"])])
        self.assertEqual(sorted({t["name"] for t in doc["targets"] if "pack" in t}), ["godot-engine"])
        self.finished(co, *self.packs("godot"))
        for d in co.skills:
            self.assertEqual(self.pack_skill_names(d), ["godot-engine"], d)

    def test_removal_keeps_gdd_drops_lines(self):
        # Step 5 (the config.yaml merge) is an agent prompt step, not part of the scripted install: one_run applies it
        # with evals/packs/merge.py, exactly as test_packs.py's end-to-end test does.
        co = self.checkout()
        self.download()
        gdd = co.code / GDD
        self.one_run(co, "gamedev", "ui-prototyping")
        self.assertTrue(gdd.is_file(), "the GDD was not created")
        text = self.config_of(co)
        self.assertTrue(self.pack_lines(text, "gamedev"))
        self.assertTrue(self.pack_lines(text, "ui-prototyping"))
        with open(gdd, "a", encoding="utf-8", newline="") as f:  # the project's own work
            f.write("\nMy own design notes.\n")
        mine = gdd.read_bytes()
        plan, docs = self.one_run(co)  # both removed from packs:
        self.assertEqual(plan["packs"], [])
        self.assertNotIn("[pack:", self.config_of(co))
        self.assertEqual(gdd.read_bytes(), mine)
        self.assertEqual(self.record_of(co)["packs"], {})
        for d in co.skills:
            self.assertEqual(self.pack_skill_names(d), [], d)


# --- signal matching over the installed catalogue ----------------------------------------------------------------------

def _match(pat, path, strict):
    if not pat:
        return not path
    if pat[0] == "**":
        # zero or more leading directories (gitignore reading), or at least one (strict reading)
        return any(_match(pat[1:], path[k:], strict) for k in range(1 if strict else 0, len(path) + 1))
    return bool(path) and fnmatchcase(path[0], pat[0]) and _match(pat[1:], path[1:], strict)


def matches(pattern, path, strict):
    return _match(pattern.split("/"), path.split("/"), strict)


def offered(catalogue, files, strict):
    return sorted(e["name"] for e in catalogue if any(matches(s, f, strict) for s in e["signals"] for f in files))


class Signals(Shipped):
    def catalogue(self):
        co = self.checkout()
        self.download()
        self.finished(co, *self.packs(*THREE))
        self.cat = {e["name"]: e for e in self.record_of(co)["catalogue"]}
        return list(self.cat.values())

    def test_nested_project_godot_offers_gamedev_and_godot(self):
        cat = self.catalogue()
        files = ["Source/Game/project.godot", "README.md"]
        for strict in (False, True):
            got = offered(cat, files, strict)
            self.assertIn("gamedev", got, strict)
            self.assertIn("godot", got, strict)
            self.assertNotIn("ui-prototyping", got, strict)  # offered only as what gamedev requires
        requires = self.cat["gamedev"].get("requires")
        if requires is None:  # a catalogue without `requires`: take it from the download manifest
            requires = tp.json.loads((self.dl / "packs" / "gamedev" / "pack.json").read_text(encoding="utf-8")).get("requires", [])
        self.assertIn("ui-prototyping", requires)

    def test_no_engine_file_no_offer(self):
        cat = self.catalogue()
        for strict in (False, True):
            self.assertEqual(offered(cat, ["README.md", "src/main.py"], strict), [])

    def test_root_file_both_readings(self):
        cat = self.catalogue()
        for strict in (True, False):
            got = offered(cat, ["project.godot"], strict)
            self.assertIn("gamedev", got, strict)
            self.assertIn("godot", got, strict)


if __name__ == "__main__":
    unittest.main()
