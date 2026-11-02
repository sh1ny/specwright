"""pack-docs (scripts/update.sh pack-docs): create each missing pack document from its template, never overwrite one.

The documents come from the record openspec/.specwright/packs.json (the resolved paths the swap wrote) and the templates
from the download's packs/. The step needs no journal and no lock, so a rerun completes an interrupted run.

Run: python -m unittest discover evals/packs -p "test_pack_docs.py"
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import packenv

DOMAIN, BASE = "valid-domain", "valid-ui-base"
GDD = "docs/domain/gdd.md"


def tree(path):
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(Path(path).rglob("*")) if p.is_file()}


class PackDocs(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pack-docs-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dl = packenv.make_download(self.tmp, (BASE, DOMAIN))
        self.template = (self.dl / "packs" / DOMAIN / "documents" / "gdd.md").read_bytes()

    def project(self, enabled=(BASE, DOMAIN), documents=None):
        documents = {DOMAIN: {"gdd": GDD}} if documents is None else documents
        self.proj = self.tmp / "proj"
        shutil.rmtree(self.proj, ignore_errors=True)
        (self.proj / "openspec" / ".specwright").mkdir(parents=True)
        (self.proj / "openspec" / ".specwright" / "packs.json").write_text(packenv.record_text(enabled, documents), encoding="utf-8")
        return self.proj

    def docs(self, expect=0):
        code, doc, out, err = packenv.run_script(self.dl, self.proj, "pack-docs")
        self.assertIsNotNone(doc, f"no JSON (exit {code}).\nstdout: {out}\nstderr: {err}")
        self.assertEqual(code, expect, out)
        return doc

    def test_missing_document_created(self):
        self.project()
        doc = self.docs()
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["documents"], [{"pack": DOMAIN, "id": "gdd", "path": GDD, "status": "created"}])
        self.assertEqual((self.proj / GDD).read_bytes(), self.template)  # parent directories made, template bytes

    def test_existing_document_kept(self):
        self.project()
        (self.proj / "docs" / "domain").mkdir(parents=True)
        (self.proj / GDD).write_text("# Our GDD\n\nWritten by hand.\n", encoding="utf-8", newline="\n")
        before = tree(self.proj)
        doc = self.docs()
        self.assertEqual(doc["documents"], [{"pack": DOMAIN, "id": "gdd", "path": GDD, "status": "kept"}])
        self.assertEqual(tree(self.proj), before)
        # the pack is removed later: the record no longer lists it, and the document stays as it is
        self.project(enabled=(BASE,), documents={})
        (self.proj / "docs" / "domain").mkdir(parents=True)
        (self.proj / GDD).write_text("# Our GDD\n\nWritten by hand.\n", encoding="utf-8", newline="\n")
        before = tree(self.proj)
        doc = self.docs()
        self.assertEqual(doc["documents"], [])
        self.assertEqual(tree(self.proj), before)

    def test_pack_docs_creates_after_stamp(self):
        proj = self.project()
        (proj / "openspec" / ".specwright" / "VERSION").write_text("0.6.0\n", encoding="utf-8")  # the stamp; finish removed the journal
        before = tree(proj)
        doc = self.docs()
        self.assertEqual([d["status"] for d in doc["documents"]], ["created"])
        self.assertEqual(set(tree(proj)) - set(before), {GDD})  # no journal, no lock, nothing else written
        self.assertFalse((proj / "openspec" / ".specwright" / "update.json").exists())
        self.assertFalse((proj / "openspec" / ".specwright" / "update.lock").exists())
        self.assertEqual({k: v for k, v in tree(proj).items() if k != GDD}, before)

    def test_pack_docs_rerun_completes(self):
        # a pack with two documents; the first run stopped after the first (only it exists), the user edited it
        second = json.loads((self.dl / "packs" / DOMAIN / "pack.json").read_text(encoding="utf-8"))
        second["documents"]["levels"] = {"path": "docs/domain/levels.md", "template": "documents/levels.md"}
        (self.dl / "packs" / DOMAIN / "pack.json").write_text(json.dumps(second), encoding="utf-8")
        (self.dl / "packs" / DOMAIN / "documents" / "levels.md").write_text("# Levels\n\nFill in.\n", encoding="utf-8", newline="\n")
        self.project(documents={DOMAIN: {"gdd": GDD}})
        first = self.docs()
        self.assertEqual([d["status"] for d in first["documents"]], ["created"])
        (self.proj / GDD).write_text("# Edited after the first run\n", encoding="utf-8", newline="\n")
        self.project_record_both()
        again = self.docs()
        self.assertEqual([(d["id"], d["status"]) for d in again["documents"]], [("gdd", "kept"), ("levels", "created")])
        self.assertEqual((self.proj / GDD).read_text(encoding="utf-8"), "# Edited after the first run\n")
        self.assertEqual((self.proj / "docs" / "domain" / "levels.md").read_text(encoding="utf-8"), "# Levels\n\nFill in.\n")
        third = self.docs()
        self.assertEqual([d["status"] for d in third["documents"]], ["kept", "kept"])

    def project_record_both(self):
        (self.proj / "openspec" / ".specwright" / "packs.json").write_text(
            packenv.record_text((BASE, DOMAIN), {DOMAIN: {"gdd": GDD, "levels": "docs/domain/levels.md"}}), encoding="utf-8")

    def test_unsafe_path_refused_before_any_write(self):
        for bad in ("/etc/gdd.md", "../outside/gdd.md", "docs/../../x.md", "docs/"):
            with self.subTest(path=bad):
                self.project(documents={DOMAIN: {"gdd": bad}})
                before = tree(self.proj)
                doc = self.docs(expect=1)
                self.assertFalse(doc["ok"])
                self.assertEqual([r["code"] for r in doc["refusals"]], ["pack_doc_path"])
                self.assertEqual(tree(self.proj), before)
                self.assertFalse((self.tmp / "outside").exists())


if __name__ == "__main__":
    unittest.main()
