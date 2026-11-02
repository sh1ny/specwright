"""pack-check (scripts/update.sh pack-check): the structural checks and the crude gate-wording check on a pack.

Every test builds a scratch "download" (the fixture packs it needs under packs/, plus the fixture schema under
schemas/specwright/) and runs the real script against it with --download. The fixtures live in evals/packs/fixtures/:
the packs/<name>/ directories and a schema.yaml with the five artifact ids.

Run: python -m unittest discover evals/packs -p "test_pack_check.py"
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evals"))
import bashexe  # noqa: E402

SCRIPT = ROOT / "scripts" / "update.sh"
FIXTURES = HERE / "fixtures"
VALID = ("valid-web", "valid-ui-base", "valid-domain", "strict-wording")
OPENSPEC_CONTEXT_LIMIT = 50 * 1024


def posix(p):
    return Path(p).resolve().as_posix()


def tree(path):
    return {p.relative_to(path).as_posix(): (p.read_bytes() if p.is_file() else None) for p in sorted(Path(path).rglob("*"))}


def script_constants():
    """The term lists of update.sh, read from its embedded Python without running it."""
    text = SCRIPT.read_text(encoding="utf-8")
    src = text.split("\n#---PYSRC---\n", 1)[1].split("\nPYSRC_EOF\n", 1)[0]
    found = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("GATE_TERMS", "GATE_TERMS_CAPITALS", "RELAXING_TERMS", "NEGATED_ONLY_TERMS", "NEGATORS"):
                found[node.targets[0].id] = list(ast.literal_eval(node.value))
    return found


class PackCheck(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pack-check-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def download(self, *packs):
        dl = self.tmp / f"dl{len(list(self.tmp.glob('dl*')))}"
        (dl / "schemas" / "specwright").mkdir(parents=True)
        shutil.copy(FIXTURES / "schema.yaml", dl / "schemas" / "specwright" / "schema.yaml")
        (dl / "packs").mkdir()
        for name in packs:
            shutil.copytree(FIXTURES / "packs" / name, dl / "packs" / name)
        return dl

    def check(self, dl, *args):
        argv = [bashexe.bash(), posix(SCRIPT), "--download", posix(dl), "pack-check", *args]
        r = subprocess.run(argv, cwd=self.tmp, capture_output=True, text=True, encoding="utf-8", timeout=120)
        try:
            doc = json.loads(r.stdout)
        except ValueError:
            self.fail(f"not one JSON document (exit {r.returncode}):\nstdout: {r.stdout}\nstderr: {r.stderr}")
        return r.returncode, doc

    def refusals(self, doc, pack=None):
        return [r for r in doc["refusals"] if pack is None or r["pack"] == pack]

    def refused(self, packs, pack, *args):
        """Run over a download of `packs`; return the refusals naming `pack` (the run must exit 1 and fail only that pack)."""
        code, doc = self.check(self.download(*packs), *args)
        self.assertEqual(code, 1, doc)
        self.assertFalse(doc["ok"])
        self.assertEqual({p["name"]: p["ok"] for p in doc["packs"]}[pack], False, doc)
        return self.refusals(doc, pack)

    def one(self, packs, pack, code):
        found = self.refused(packs, pack)
        self.assertEqual([r["code"] for r in found], [code], found)
        self.assertIn("message", found[0])
        return found[0]

    # --- A pack is a directory with a JSON manifest -------------------------------------------------------------

    def test_valid_manifest_accepted(self):
        code, doc = self.check(self.download("valid-web"))
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc["packs"], [{"name": "valid-web", "ok": True}])
        self.assertEqual((doc["ok"], doc["refusals"]), (True, []))

    def test_malformed_manifests_refused(self):
        self.one(["bad-not-json"], "bad-not-json", "manifest_invalid")
        self.one(["bad-unknown-field"], "bad-unknown-field", "manifest_invalid")
        self.one(["bad-missing-description"], "bad-missing-description", "manifest_invalid")
        self.one(["openspec-extra"], "openspec-extra", "manifest_invalid")  # a reserved prefix
        self.one(["bad-format-unsupported"], "bad-format-unsupported", "format_unsupported")
        self.one(["bad-name-mismatch"], "bad-name-mismatch", "name_mismatch")
        self.one(["bad-source"], "bad-source", "external_pack_unsupported")

    # --- Documents, questions and signals ------------------------------------------------------------------------

    def test_complete_document_entry(self):
        code, doc = self.check(self.download("valid-domain", "valid-ui-base"))
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc["refusals"], [])

    def test_broken_documents_questions_signals(self):
        r = self.one(["bad-document-template"], "bad-document-template", "document_invalid")
        self.assertEqual(r["field"], "documents.gdd")
        found = self.refused(["bad-document-path"], "bad-document-path")
        self.assertEqual(sorted((r["code"], r["field"]) for r in found),
                         [("document_invalid", "documents.abs"), ("document_invalid", "documents.up")])
        r = self.one(["bad-init"], "bad-init", "init_invalid")
        self.assertEqual(r["field"], "init.questions")
        self.assertEqual(r["index"], 1)
        r = self.one(["bad-signals"], "bad-signals", "signals_invalid")
        self.assertEqual((r["field"], r["index"]), ("signals", 1))

    # --- Pack and skill names ------------------------------------------------------------------------------------

    def test_prefixed_skills_accepted(self):
        code, doc = self.check(self.download("valid-ui-base", "valid-domain"))
        self.assertEqual(code, 0, doc)

    def test_core_or_foreign_skill_refused(self):
        found = self.refused(["valid-web", "bad-skill-name"], "bad-skill-name")
        self.assertEqual([(r["code"], r["skill"]) for r in found],
                         [("skill_name", "specwright-commit"), ("skill_name", "valid-web-ux")])
        self.assertEqual(found[1]["owner"], "valid-web")
        r = self.one(["bad-skill-missing"], "bad-skill-missing", "skill_missing")
        self.assertEqual(r["skill"], "bad-skill-missing-a")
        r = self.one(["bad-skill-unlisted"], "bad-skill-unlisted", "skill_unlisted")
        self.assertEqual(r["skill"], "bad-skill-unlisted-b")

    def test_longest_prefix_owns_skill(self):
        code, doc = self.check(self.download("react", "react-native"))
        self.assertEqual(code, 1, doc)
        self.assertEqual({p["name"]: p["ok"] for p in doc["packs"]}, {"react": False, "react-native": True})
        (r,) = doc["refusals"]
        self.assertEqual((r["code"], r["pack"], r["skill"], r["owner"]), ("skill_name", "react", "react-native-nav", "react-native"))
        self.assertIn("react-native", r["message"])

    # --- Rules and guidance attach only to known artifacts -------------------------------------------------------

    def test_known_artifacts_accepted(self):
        code, doc = self.check(self.download("valid-web"))  # rules.proposal, review, tasks; operations.apply
        self.assertEqual((code, doc["refusals"]), (0, []))

    def test_unknown_artifact_or_operation(self):
        r = self.one(["bad-unknown-artifact"], "bad-unknown-artifact", "unknown_artifact")
        self.assertEqual(r["field"], "rules.playtest")
        r = self.one(["bad-unknown-operation"], "bad-unknown-operation", "unknown_operation")
        self.assertEqual(r["field"], "operations.verify")

    # --- Every pack line is one owned, bounded line -------------------------------------------------------------

    def test_plain_line_accepted(self):
        code, doc = self.check(self.download("valid-domain", "valid-ui-base"))
        self.assertEqual((code, doc["refusals"]), (0, []))

    def test_invalid_lines_refused(self):
        found = self.refused(["bad-line-invalid"], "bad-line-invalid")
        self.assertEqual({r["code"] for r in found}, {"line_invalid"})
        self.assertEqual(sorted((r["field"], r["index"]) for r in found),
                         [("context", 1), ("operations.apply", 0), ("rules.design", 1), ("rules.proposal", 0)])

    def test_too_many_lines_or_context_bytes(self):
        r = self.one(["bad-too-many-lines"], "bad-too-many-lines", "too_many_lines")
        self.assertEqual(r["count"], 41)
        self.assertIn("41", r["message"])
        r = self.one(["bad-context-too-large"], "bad-context-too-large", "context_too_large")
        self.assertEqual(r["count"], 2049)
        self.assertIn("2049", r["message"])

    # --- Gate-relaxing wording -----------------------------------------------------------------------------------

    def test_relaxing_line_refused(self):
        r = self.one(["bad-relaxes-gate"], "bad-relaxes-gate", "relaxes_gate")
        self.assertEqual((r["field"], r["index"]), ("rules.design", 0))
        self.assertEqual(r["line"], "Actor-local state machines do not trip T2 on their own.")

    def test_contracted_negator_trip_refused(self):
        # `n't` attaches to the word before it ("don't", "doesn't"), unlike `not` and `never`
        for line in ("Actor-local state machines don't trip T2 on their own.",
                     "A cosmetic tweak doesn’t trip the T4 trigger.",
                     "Actor-local state machines never trip T2."):
            dl = self.download("bad-relaxes-gate")
            path = dl / "packs" / "bad-relaxes-gate" / "pack.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["rules"]["design"] = [line]
            path.write_text(json.dumps(data), encoding="utf-8")
            code, doc = self.check(dl)
            self.assertEqual(code, 1, line)
            self.assertEqual([r["code"] for r in doc["refusals"]], ["relaxes_gate"], line)
            shutil.rmtree(dl)

    def test_strict_wording_passes(self):
        code, doc = self.check(self.download("strict-wording"))
        self.assertEqual((code, doc["refusals"]), (0, []))

    # --- Composition ---------------------------------------------------------------------------------------------

    def test_requires_missing_or_cyclic_refused(self):
        r = self.one(["bad-requires"], "bad-requires", "pack_requires")
        self.assertEqual(r["requires"], "no-such-pack")
        code, doc = self.check(self.download("cycle-a", "cycle-b"))
        self.assertEqual(code, 1, doc)
        self.assertEqual({p["name"]: p["ok"] for p in doc["packs"]}, {"cycle-a": False, "cycle-b": False})
        self.assertEqual({(r["code"], r["pack"]) for r in doc["refusals"]}, {("pack_cycle", "cycle-a"), ("pack_cycle", "cycle-b")})
        for r in doc["refusals"]:
            self.assertIn("cycle-a", r["message"])
            self.assertIn("cycle-b", r["message"])

    # --- The report ---------------------------------------------------------------------------------------------

    def test_all_packs_pass_and_shipped_packs_pass(self):
        dl = self.download(*VALID)
        before = tree(dl)
        code, doc = self.check(dl)
        self.assertEqual(code, 0, doc)
        self.assertEqual((doc["ok"], doc["refusals"]), (True, []))
        self.assertEqual([p["name"] for p in doc["packs"]], sorted(VALID))
        self.assertTrue(all(p["ok"] for p in doc["packs"]))
        self.assertEqual(tree(dl), before)  # writes nothing
        # The real tree: every shipped pack, against the real schema (this is the per-PR check of first-party packs).
        code, doc = self.check(ROOT)
        self.assertEqual((code, doc["refusals"]), (0, []), doc)
        self.assertTrue(doc["ok"])

    def test_shipped_context_fits_openspec_limit(self):
        """Design, Resource Bounds: the core managed context lines plus every shipped pack's context stay under
        OpenSpec's 50 KB, or OpenSpec would ignore the whole `context:`."""
        core = 0
        in_block = False
        for line in (ROOT / "templates" / "openspec" / "config.yaml").read_text(encoding="utf-8").splitlines():
            if line.startswith("context:"):
                in_block = True
            elif in_block and line.startswith("  "):
                core += len(line[2:].encode("utf-8")) + 1
            elif in_block and line.strip():
                in_block = False
        self.assertGreater(core, 0)
        packs = 0
        for manifest in sorted((ROOT / "packs").glob("*/pack.json")):
            data = json.loads(manifest.read_text(encoding="utf-8"))
            prefix = f"[pack:{data['name']}] "
            packs += sum(len((prefix + line).encode("utf-8")) + 1 for line in data.get("context", []))
        self.assertLess(core + packs, OPENSPEC_CONTEXT_LIMIT, f"core {core} + packs {packs} bytes")

    def test_named_pack_missing(self):
        dl = self.download("valid-web", "valid-ui-base")
        code, doc = self.check(dl, "--pack", "mobile")
        self.assertEqual(code, 1, doc)
        (r,) = doc["refusals"]
        self.assertEqual((r["code"], r["pack"]), ("pack_unknown", "mobile"))
        self.assertEqual(r["available"], ["valid-ui-base", "valid-web"])
        self.assertIn("valid-web", r["message"])
        # --pack limits the check to the named packs
        code, doc = self.check(self.download("valid-web", "bad-relaxes-gate"), "--pack", "valid-web")
        self.assertEqual((code, doc["packs"], doc["refusals"]), (0, [{"name": "valid-web", "ok": True}], []))

    # --- The README's term lists -------------------------------------------------------------------------------

    def test_readme_term_lists_match_script(self):
        consts = script_constants()
        self.assertEqual(set(consts), {"GATE_TERMS", "GATE_TERMS_CAPITALS", "RELAXING_TERMS", "NEGATED_ONLY_TERMS", "NEGATORS"})
        text = (ROOT / "packs" / "README.md").read_text(encoding="utf-8")

        def listed(label):
            lines = [ln for ln in text.splitlines() if ln.startswith(label)]
            self.assertEqual(len(lines), 1, f"packs/README.md needs exactly one line starting {label!r}")
            return re.findall(r"`([^`]+)`", lines[0])

        self.assertEqual(listed("- Gate terms (any case):"), consts["GATE_TERMS"])
        self.assertEqual(listed("- Gate terms (capitals only):"), consts["GATE_TERMS_CAPITALS"])
        self.assertEqual(listed("- Relaxing terms:"), consts["RELAXING_TERMS"])
        self.assertEqual(listed("- Relaxing only when negated:"), consts["NEGATED_ONLY_TERMS"])
        self.assertEqual(listed("- Negators:"), consts["NEGATORS"])


if __name__ == "__main__":
    unittest.main()
