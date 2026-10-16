"""Script tests for scripts/update.sh (planning, staging, swapping and finishing an update).

Every test runs the real script, from a download tree, against a scratch checkout built by fixtures.py. One JSON
document on stdout per call; exit 0 = done, 1 = stop (the JSON has "ok": false, "error" and "message"), 2 = usage.

Run: python -m unittest discover evals/update
"""
import importlib.util
import os
import re
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("update_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

NEW_SKILL = {"specwright-extra": "---\nname: specwright-extra\ndescription: \"x\"\n---\n\n# extra\n"}


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, self.tmp)

    def checkout(self, version="0.5.0", **kw):
        kw.setdefault("skills_dirs", (".claude/skills", ".agents/skills"))
        self.co = fx.make_checkout(self.tmp, version, **kw)
        return self.co

    def download(self, version="0.6.0", name=None, **kw):
        self.dl = fx.make_download(self.tmp / (name or f"dl-new-{version}"), version, **kw)
        return self.dl

    def run_sub(self, sub, *extra, dl=None, co=None, **kw):
        """Run `update.sh <checkout options> <sub> <extra>`; returns (exit code, JSON, stderr)."""
        co, dl = co or self.co, dl or self.dl
        code, doc, out, err = fx.run_update(dl, [*co.args(), sub, *extra], **kw)
        self.assertIsNotNone(doc, f"{sub}: no JSON on stdout (exit {code}).\nstdout: {out}\nstderr: {err}")
        return code, doc, err

    def staging_dirs(self):
        return sorted(p.relative_to(self.co.code).as_posix() for p in self.co.code.rglob(".specwright-update-*"))


class TestPlan(Base):
    def test_plan_reports_interface(self):
        co = self.checkout("0.5.0")
        dl = self.download("0.6.0", schema_edit=fx.schema_edit_comment)
        code_before, dl_before = fx.snapshot(co.code), fx.snapshot(dl)
        code, doc, err = self.run_sub("plan")
        self.assertEqual(code, 0, err)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["interface"], 1)
        self.assertEqual((doc["from"], doc["to"], doc["kind"], doc["role"]), ("0.5.0", "0.6.0", "workflow", "none"))
        self.assertEqual(doc["refusals"], [])
        self.assertEqual(doc["journal"], None)
        # plan is read only: nothing in the checkout changed, and nothing in the download outside .update-scratch/
        self.assertEqual(fx.snapshot(co.code), code_before)
        after = {k: v for k, v in fx.snapshot(dl).items() if not k.startswith(".update-scratch")}
        self.assertEqual(after, {k: v for k, v in dl_before.items() if not k.startswith(".update-scratch")})
        self.assertEqual(self.staging_dirs(), [])

    def test_plan_kinds(self):
        for installed, target, kind in (("0.5.0", "0.5.1", "patch"), ("0.5.0", "0.6.0", "workflow"),
                                        ("0.5.0", "1.0.0", "workflow"), ("0.6.0", "0.6.0", "reinstall"),
                                        ("0.6.1", "0.6.0", "downgrade"), ("0.6.0", "0.5.9", "downgrade")):
            with self.subTest(f"{installed} -> {target}"):
                tmp = Path(tempfile.mkdtemp(dir=self.tmp))
                co = fx.make_checkout(tmp, installed, skills_dirs=(".claude/skills",))
                dl = fx.make_download(tmp / "dl", target)
                code, doc, out, err = fx.run_update(dl, [*co.args(), "plan"])
                self.assertEqual(code, 0, err)
                self.assertEqual((doc["from"], doc["to"], doc["kind"]), (installed, target, kind))

    def test_plan_without_installed_version_is_fresh(self):
        co = fx.make_checkout(self.tmp, None, skills_dirs=(".claude/skills",))
        dl = self.download("0.6.0")
        code, doc, err = self.run_sub("plan", co=co)
        self.assertEqual(code, 0, err)
        self.assertEqual((doc["from"], doc["to"], doc["kind"]), (None, "0.6.0", "fresh"))

    def test_plan_lists_orphans_and_targets(self):
        co = self.checkout("0.5.0")
        dl = self.download("0.6.0", drop_skills=("specwright-debug",), add_skills=NEW_SKILL)
        code, doc, err = self.run_sub("plan")
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(o["name"] for o in doc["orphans"]), ["specwright-debug", "specwright-debug"])
        names = {t["name"] for t in doc["targets"]}
        self.assertIn("specwright-extra", names)
        self.assertNotIn("specwright-debug", names)

    def test_refusal_reports_unchanged(self):
        co = self.checkout("0.5.0")
        dl = self.download("0.6.0")
        fx.write(dl, "VERSION", "not-a-version\n")  # a download the script cannot install
        before = fx.snapshot(co.code)
        for sub in ("plan", "stage"):
            with self.subTest(sub):
                code, doc, err = self.run_sub(sub)
                self.assertEqual(code, 1)
                self.assertFalse(doc["ok"])
                self.assertEqual(doc["error"], "refused")
                self.assertEqual(doc["installed"], "0.5.0")
                self.assertTrue(doc["unchanged"])
                self.assertNotIn("restart", doc)  # no restart notice: nothing was swapped
                self.assertTrue(doc["refusals"])
                self.assertEqual(fx.snapshot(co.code), before)
                self.assertEqual(self.staging_dirs(), [])
                self.assertEqual(co.version_file.read_text(), "0.5.0\n")


class TestStage(Base):
    def agents_expected(self, dl, co, kind="claude"):
        out = {}
        for p in sorted((dl / "agents" / kind).glob("*.md")):
            out[p.name] = p.read_bytes()
        return out

    def test_update_completes(self):
        co = self.checkout("0.5.0")
        dl = self.download("0.6.0", schema_edit=fx.schema_edit_comment, add_skills=NEW_SKILL)
        # the user changed an agent's model: the update keeps it
        impl = co.agents["claude"] / "specwright-implementer.md"
        impl.write_bytes(impl.read_bytes().replace(b"model: sonnet", b"model: opus"))
        installed_before = {str(sd): fx.tree(sd) for sd in co.skills}
        installed_before["agents"] = fx.tree(co.agents["claude"])
        installed_before["schema"] = fx.tree(co.schema)

        code, doc, err = self.run_sub("stage")
        self.assertEqual(code, 0, err)
        self.assertTrue(doc["ok"])
        self.assertEqual((doc["from"], doc["to"], doc["state"]), ("0.5.0", "0.6.0", "staged"))
        # staged: the previous version is untouched and runnable, the staging sits beside each target
        self.assertEqual({str(sd): fx.tree(sd) for sd in co.skills} | {"agents": fx.tree(co.agents["claude"]),
                                                                       "schema": fx.tree(co.schema)}, installed_before)
        self.assertEqual(self.staging_dirs(), [".agents/.specwright-update-skills", ".claude/.specwright-update-agents",
                                               ".claude/.specwright-update-skills",
                                               "openspec/.specwright-update-schemas"])
        for sd in co.skills:
            self.assertFalse(list(sd.glob(".specwright-update*")), "staging must never sit inside a skills directory")
        journal = fx.json.loads(co.journal.read_text(encoding="utf-8"))
        self.assertEqual((journal["format"], journal["from"], journal["to"]), (1, "0.5.0", "0.6.0"))
        self.assertEqual(journal["role"], "none")
        self.assertTrue(journal["manifest"])
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", m["sha256"]) for m in journal["manifest"]))
        self.assertEqual(journal["phase"], "staged")
        self.assertTrue(journal["targets"])
        self.assertTrue(all(t["state"] == "staged" for t in journal["targets"]))
        self.assertEqual({g["id"] for g in journal["groups"]}, {t["gid"] for t in journal["targets"]})

        code, doc, err = self.run_sub("swap")
        self.assertEqual(code, 0, err)
        self.assertEqual(doc["state"], "swapped")
        self.assertIs(doc["store_written"], False)
        # the prompt's Step 7 stamps VERSION after its checks
        co.version_file.write_text("0.6.0\n")
        code, doc, err = self.run_sub("finish")
        self.assertEqual(code, 0, err)
        self.assertTrue(doc["ok"])

        for sd in co.skills:
            want = {p.name for p in (dl / "skills").glob("specwright-*")}
            self.assertEqual({p.name for p in sd.glob("specwright-*")}, want)
            for name in want:
                self.assertEqual(fx.tree(sd / name), fx.tree(dl / "skills" / name), f"{sd}/{name}")
        self.assertEqual(fx.tree(co.schema), fx.tree(dl / "schemas" / "specwright"))
        want_agents = self.agents_expected(dl, co)
        want_agents["specwright-implementer.md"] = want_agents["specwright-implementer.md"].replace(
            b"model: sonnet", b"model: opus")
        self.assertEqual({p.name: p.read_bytes() for p in co.agents["claude"].glob("*.md")}, want_agents)
        self.assertEqual(co.version_file.read_text(), "0.6.0\n")
        self.assertEqual(self.staging_dirs(), [])
        self.assertFalse(co.journal.exists())
        self.assertFalse(co.lock.exists())
        r = fx.openspec(["schema", "validate", "specwright"], cwd=co.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_staged_copy_fails_verification(self):
        co = self.checkout("0.5.0")
        self.download("0.6.0", schema_edit=fx.schema_edit_comment)
        # a cp that damages the staged copy of one skill after copying it
        wrap = self.tmp / "wrap"
        fx.write(wrap, "cp", '#!/bin/sh\nPATH="${PATH#*:}"\ncp "$@"\nrc=$?\nfor last; do :; done\n'
                             'case "$last" in *.specwright-update-*)\n'
                             '  find "$last" -path "*specwright-branch/SKILL.md" -exec sh -c \'echo tampered >> "$1"\' _ {} \\;\n'
                             'esac\nexit $rc\n')
        (wrap / "cp").chmod(0o755)
        before = fx.snapshot(co.code)
        code, doc, err = self.run_sub("stage", shim_dir=wrap)
        self.assertEqual(code, 1, doc)
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["error"], "verification_failed")
        self.assertTrue(any(m["path"].endswith("specwright-branch/SKILL.md") for m in doc["mismatches"]), doc)
        self.assertIn("specwright-branch/SKILL.md", doc["message"])
        self.assertTrue(doc["unchanged"])
        self.assertEqual(doc["installed"], "0.5.0")
        self.assertEqual(self.staging_dirs(), [])
        self.assertFalse(co.journal.exists())
        self.assertFalse(co.lock.exists())
        self.assertEqual(fx.snapshot(co.code), before)  # installed files, VERSION: byte for byte
        self.assertEqual(co.version_file.read_text(), "0.5.0\n")


if __name__ == "__main__":
    unittest.main()
