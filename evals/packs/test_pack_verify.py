"""pack-verify (scripts/update.sh pack-verify): the merged config.yaml is checked through real `openspec instructions`.

Every test builds a download (the real schema plus fixture packs), a project whose config.yaml is the Step 5 merge
(evals/packs/merge.py), and runs the real script. The script's own scratch root must be gone afterwards.

Run: python -m unittest discover evals/packs -p "test_pack_verify.py"
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import packenv
import merge

WEB, BASE, DOMAIN = "valid-web", "valid-ui-base", "valid-domain"
ARTIFACTS = ("proposal", "specs", "design", "review", "tasks")


def delivered(proj_config_text, dl, tmp, *args):
    """`openspec instructions <args> --json` in a scratch root of our own with this config.yaml: the parsed output."""
    root = Path(tmp) / "delivered"
    shutil.rmtree(root, ignore_errors=True)
    (root / "openspec" / "changes" / "probe").mkdir(parents=True)
    (root / "openspec" / "specs").mkdir()
    shutil.copytree(Path(dl) / "schemas" / "specwright", root / "openspec" / "schemas" / "specwright")
    (root / "openspec" / "changes" / "probe" / ".openspec.yaml").write_text("schema: specwright\n", encoding="utf-8")
    (root / "openspec" / "config.yaml").write_text(proj_config_text, encoding="utf-8", newline="\n")
    r = subprocess.run([packenv.OPENSPEC, "instructions", *args, "--change", "probe", "--json"], cwd=root, capture_output=True,
                       text=True, encoding="utf-8", env={**__import__("os").environ, "OPENSPEC_TELEMETRY": "0"})
    return json.loads(r.stdout)


@unittest.skipUnless(packenv.OPENSPEC, "the openspec CLI is not on PATH")
class PackVerify(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pack-verify-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dl = packenv.make_download(self.tmp, (WEB, BASE, DOMAIN))

    def project(self, enabled, **kw):
        self.proj, self.unmanaged = packenv.make_project(self.tmp, self.dl, enabled, **kw)
        return self.proj

    def config_path(self):
        return self.proj / "openspec" / "config.yaml"

    def verify(self, *previous, expect=None):
        args = ["pack-verify"]
        for p in previous:
            args += ["--previous", p]
        code, doc, out, err = packenv.run_script(self.dl, self.proj, *args)
        self.assertIsNotNone(doc, f"no JSON (exit {code}).\nstdout: {out}\nstderr: {err}")
        if expect is not None:
            self.assertEqual(code, expect, out)
        self.assertEqual(code, 0 if doc["ok"] else 1)
        self.assertFalse((self.dl / ".update-scratch").exists(), "the scratch root is removed before return")
        return doc

    def problems(self, doc):
        return sorted((p["code"], p["pack"], p["line"], p["target"]) for p in doc["problems"])

    def edit_config(self, fn):
        text = self.config_path().read_text(encoding="utf-8")
        new = fn(text)
        self.assertNotEqual(text, new, "the edit changed nothing")
        self.config_path().write_text(new, encoding="utf-8", newline="\n")

    def test_lines_with_outer_spaces_are_found(self):
        # pack-check accepts a line with a leading or trailing space; OpenSpec's output is compared trimmed, so the
        # expected line must be trimmed the same way or it is reported missing on every install.
        path = self.dl / "packs" / WEB / "pack.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["rules"]["proposal"].append("A trailing space stays the pack's line. ")
        data["context"].append("A context line with a trailing space.  ")
        data["operations"]["apply"]["guidance"].append(" A leading space too.")
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
        code, check, out, err = packenv.run_script(self.dl, self.tmp, "pack-check")
        self.assertEqual(code, 0, out)
        self.project([WEB])
        doc = self.verify(expect=0)
        self.assertEqual(doc["problems"], [])

    def test_installed_line_prefixed(self):
        self.project([WEB])
        text = self.config_path().read_text(encoding="utf-8")
        line = manifest_line = packenv.manifest(self.dl, WEB)["rules"]["proposal"][0]
        self.assertIn(f'    - "[pack:{WEB}] {manifest_line}"', text.splitlines())
        self.assertIn(f"  [pack:{WEB}] Web changes name the browsers they were checked in.", text.splitlines())
        # OpenSpec hands the agent exactly the prefixed line
        self.assertEqual(delivered(text, self.dl, self.tmp, "proposal")["rules"], [f"[pack:{WEB}] {line}"])
        self.assertTrue(self.verify()["ok"])

    def test_lines_reach_artifacts_and_operations(self):
        self.project([BASE, DOMAIN, WEB])
        doc = self.verify(expect=0)
        self.assertEqual(doc["problems"], [])
        self.assertEqual(doc["checked"]["lines"], 10)
        self.assertEqual(doc["checked"]["runs"], 7)  # five artifacts, apply, archive
        text = self.config_path().read_text(encoding="utf-8")
        mans = {n: packenv.manifest(self.dl, n) for n in (BASE, DOMAIN, WEB)}
        for art in ARTIFACTS:
            want = [f"[pack:{n}] {t}" for n in (BASE, DOMAIN, WEB) for t in mans[n].get("rules", {}).get(art, [])]
            got = delivered(text, self.dl, self.tmp, art)
            self.assertEqual([r for r in got.get("rules", []) if r.startswith("[pack:")], want, art)
        apply_ = delivered(text, self.dl, self.tmp, "apply")
        self.assertEqual(apply_["operationGuidance"], [f"[pack:{WEB}] Run the linter before marking a web task done."])
        archive = delivered(text, self.dl, self.tmp, "archive")
        self.assertEqual(archive["operationGuidance"], [f"[pack:{DOMAIN}] Name the design document sections the change touched."])
        ctx = delivered(text, self.dl, self.tmp, "proposal")["context"].splitlines()
        for n in (DOMAIN, WEB):
            for t in mans[n]["context"]:
                self.assertEqual(ctx.count(f"[pack:{n}] {t}"), 1)

    def test_missing_duplicate_stale_lines(self):
        # web was enabled before and is removed now; the merge was skipped for it, so its lines are stale
        self.project([BASE, DOMAIN, WEB])
        (self.proj / "openspec" / ".specwright" / "packs.json").write_text(packenv.record_text([BASE, DOMAIN]), encoding="utf-8")

        def edit(text):
            lines = text.splitlines()
            lines = [ln for ln in lines if "Player-visible work ends with a playtest task." not in ln]  # missing (rules.tasks)
            i = next(k for k, ln in enumerate(lines) if "A new screen names its states" in ln)
            lines.insert(i, lines[i])  # duplicate (rules.design)
            return "\n".join(lines) + "\n"
        self.edit_config(edit)
        doc = self.verify(WEB, expect=1)
        got = self.problems(doc)
        self.assertIn(("missing", DOMAIN, "Player-visible work ends with a playtest task.", "rules.tasks"), got)
        self.assertIn(("duplicate", BASE, "A new screen names its states: empty, loading, error.", "rules.design"), got)
        stale = [g for g in got if g[0] == "not_enabled"]
        self.assertEqual(sorted(stale), sorted([
            ("not_enabled", WEB, "A change to a page states which routes it touches.", "rules.proposal"),
            ("not_enabled", WEB, "The review checks contrast ratios.", "rules.review"),
            ("not_enabled", WEB, "Browser-visible work ends with a manual check task.", "rules.tasks"),
            ("not_enabled", WEB, "Run the linter before marking a web task done.", "operations.apply"),
            ("not_enabled", WEB, "Web changes name the browsers they were checked in.", "context"),
        ]))
        self.assertEqual(len(got), 7)
        for p in doc["problems"]:
            self.assertTrue(p["message"])

    def test_previous_pack_line_not_enabled(self):
        self.project([BASE])
        self.edit_config(lambda t: t.replace(f'    - "[pack:{BASE}] A new screen', f'    - "[pack:{WEB}] Left behind."\n    - "[pack:{BASE}] A new screen'))
        doc = self.verify(WEB, expect=1)
        self.assertEqual(self.problems(doc), [("not_enabled", WEB, "Left behind.", "rules.design")])
        # without --previous the line belongs to nobody Specwright manages
        self.assertTrue(self.verify(expect=0)["ok"])

    def test_unmanaged_pack_lines_pass(self):
        core = (packenv.ROOT / "templates" / "openspec" / "config.yaml").read_text(encoding="utf-8")
        hand = (core.replace("context: |\n", "context: |\n  [pack:gamedev] Our game ships on consoles.\n", 1) +
                "rules:\n  proposal:\n    - \"[pack:gamedev] Name the target frame rate.\"\n"
                "operations:\n  apply:\n    guidance:\n      - \"[pack:gamedev] Playtest before done.\"\n")
        self.project([DOMAIN], existing=hand)
        self.assertEqual(len(self.unmanaged), 3)  # the merge keeps and reports them
        doc = self.verify(expect=0)
        self.assertEqual(doc["problems"], [])
        text = self.config_path().read_text(encoding="utf-8")
        self.assertEqual([r for r in delivered(text, self.dl, self.tmp, "proposal")["rules"]], ["[pack:gamedev] Name the target frame rate."])

    def test_core_context_lines_still_delivered(self):
        self.project([WEB])
        core = [ln.strip() for ln in (self.dl / "templates" / "openspec" / "config.yaml").read_text(encoding="utf-8").splitlines()
                if ln.startswith("  ")]
        self.assertGreater(len(core), 3)
        doc = self.verify(expect=0)
        self.assertEqual(doc["checked"]["core_lines"], len(core))
        # a context pushed over OpenSpec's 50 KB limit is dropped whole: the core lines go missing
        pad = "  " + "x" * 900 + "\n"
        self.edit_config(lambda t: t.replace("context: |\n", "context: |\n" + pad * 60, 1))
        doc = self.verify(expect=1)
        missing = sorted(p["line"] for p in doc["problems"] if p["code"] == "core_context_missing")
        self.assertEqual(missing, sorted(core))
        for p in doc["problems"]:
            if p["code"] == "core_context_missing":
                self.assertEqual(p["target"], "context")

    def test_one_core_line_dropped(self):
        self.project([WEB])
        self.edit_config(lambda t: "\n".join(ln for ln in t.splitlines() if not ln.strip().startswith("Project-level planning")) + "\n")
        doc = self.verify(expect=1)
        self.assertEqual([p["code"] for p in doc["problems"]], ["core_context_missing"])
        self.assertTrue(doc["problems"][0]["line"].startswith("Project-level planning"))

    def test_unquoted_flow_sequence_entry_is_found_missing(self):
        # the trap the prompt avoids by double-quoting: an unquoted entry starting with `[` drops the whole rules list
        self.project([WEB])
        self.edit_config(lambda t: t.replace(f'    - "[pack:{WEB}] A change to a page', f'    - [pack:{WEB}] A change to a page'))
        doc = self.verify(expect=1)
        self.assertIn(("missing", WEB, "A change to a page states which routes it touches.", "rules.proposal"), self.problems(doc))

    def test_scratch_removed_and_project_untouched(self):
        self.project([WEB, BASE])
        before = {p.relative_to(self.proj).as_posix(): p.read_bytes() for p in self.proj.rglob("*") if p.is_file()}
        self.verify()
        after = {p.relative_to(self.proj).as_posix(): p.read_bytes() for p in self.proj.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


class MergeHelper(unittest.TestCase):
    def test_second_merge_is_stable(self):
        tmp = Path(tempfile.mkdtemp(prefix="pack-merge-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        dl = packenv.make_download(tmp, (WEB, DOMAIN, BASE))
        proj, _ = packenv.make_project(tmp, dl, [BASE, DOMAIN, WEB])
        first = (proj / "openspec" / "config.yaml").read_text(encoding="utf-8")
        template = (dl / "templates" / "openspec" / "config.yaml").read_text(encoding="utf-8")
        again, _ = merge.merge_config(first, template, [(n, packenv.manifest(dl, n)) for n in (BASE, DOMAIN, WEB)], ())
        self.assertEqual(first, again)
        self.assertEqual(first.count(f"[pack:{WEB}] "), 5)


if __name__ == "__main__":
    unittest.main()
