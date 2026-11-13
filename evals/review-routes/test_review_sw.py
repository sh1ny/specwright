"""Native review operations: no interpreter fallback and pre-port record compatibility."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_review_run import Base, ROOT, VALID, bashexe, bash_path_env

sys.path.insert(0, str(ROOT / "evals" / "cli"))
from swharness import require_sw  # noqa: E402


class NativeReviewTests(Base):
    def native(self, *args, scripts=None, expect=0, env=None):
        scripts = scripts or ROOT / "skills" / "specwright-review" / "scripts"
        records = [str(scripts), "unused-bash", *map(str, args)]
        data = b"".join(value.encode("utf-8") + b"\0" for value in records)
        result = subprocess.run([require_sw(), "review", "--args-stdin"], input=data,
                                cwd=self.code, env=env or self.env(), capture_output=True)
        self.assertEqual(result.returncode, expect, result.stderr.decode("utf-8", "replace") + repr(result.stdout))
        lines = result.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1, result.stdout)
        return json.loads(lines[0])

    def msys_path(self, path, drive=False):
        if os.name != "nt":
            return str(path)
        if drive:
            return "/" + path.drive[0].lower() + path.as_posix()[2:]
        return subprocess.check_output(["cygpath", "-u", str(path)], env=self.env(), text=True).strip()

    def test_design_handoff_accepts_msys_paths(self):
        self.install("claude")
        review = "# Review\n\nVERDICT: APPROVE\nCHANGES_APPLIED: n/a\n"
        self.stdout_file("claude", json.dumps({"type": "result", "result": review}))
        self.set_settings("review:\n  routes:\n    claude:\n      tools: [Read]\n")
        folder = self.tmp / "review 文 files"
        folder.mkdir()
        prompt = folder / "request.md"
        prompt.write_text("Review this unique MSYS-path fixture.\n", encoding="utf-8")
        output = folder / "review.md"
        selection = folder / "selection.json"
        skipped = [{"route": "codex", "reason": "not installed"}]
        selection.write_text(json.dumps({"route": "claude", "skipped": skipped}), encoding="utf-8")
        result = self.script("run", "--kind", "design", "--route", "claude", "--change", "demo-change",
                             "--prompt-file", self.msys_path(prompt), "--out", self.msys_path(output),
                             "--settings", self.msys_path(self.settings, drive=True),
                             "--store", self.msys_path(self.store), "--selection", self.msys_path(selection))
        self.assertEqual(output.read_text(encoding="utf-8"), review)
        self.assertIn("unique MSYS-path fixture", self.runs("claude")[0]["stdin"])
        self.assertEqual(result["receipt"]["tools"], ["Read"])
        self.assertEqual(result["receipt"]["skipped"], skipped)

    def test_record_handoff_accepts_msys_paths(self):
        settings = self.msys_path(self.settings, drive=True)
        store = self.msys_path(self.store)
        preflight = self.script("preflight", "--kind", "preship", "--change", "demo-change",
                                "--base", "main", "--settings", settings, "--store", store)
        preflight_file = self.put("msys-preflight.json", json.dumps(preflight))
        findings = self.put("msys-findings.json", json.dumps(VALID))
        selection = self.put("msys-selection.json", json.dumps({"route": "subagent", "skipped": []}))
        before = self.status()
        result = self.script("record", "--kind", "preship", "--route", "subagent", "--change", "demo-change",
                             "--result", self.msys_path(findings), "--preflight", self.msys_path(preflight_file),
                             "--selection", self.msys_path(selection), "--settings", settings, "--store", store)
        record = json.loads(Path(result["record"]).read_text(encoding="utf-8"))
        self.assertEqual(record["heads"], preflight["heads"])
        self.assertEqual(record["findings"], VALID)
        gate = self.script("gate", "--change", "demo-change", "--settings", settings, "--store", store)
        self.assertEqual(gate["status"], "blocked")
        self.assertEqual([finding["id"] for finding in gate["open"]], ["F1"])
        archive = self.script("archive-only", "--base", "main", "--head", "HEAD", "--change", "demo-change",
                              "--dir", self.msys_path(self.code, drive=True))
        self.assertFalse(archive["archive_only"])
        self.assertEqual(self.status(), before)

    def test_preship_runs_without_python_or_bash(self):
        source = self.tmp / "fake-codex.dart"
        source.write_text("import 'dart:convert';\nimport 'dart:io';\n"
                          "Future<void> main(List<String> args) async {\n"
                          " if (args.contains('--version')) { print('codex-cli 0.166.0'); return; }\n"
                          " await stdin.drain<void>();\n"
                          " print(jsonEncode({'type':'item.completed','item':{'type':'agent_message','text':r'''"
                          + json.dumps(VALID) + "'''}}));\n}\n", encoding="utf-8")
        executable = self.bin / ("codex.exe" if os.name == "nt" else "codex")
        built = subprocess.run(["mise", "exec", "--", "dart", "compile", "exe", str(source), "-o", str(executable)],
                               cwd=ROOT / "cli", capture_output=True, text=True, timeout=180)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        marker = self.tmp / "interpreter-started"
        for name in ("python", "python3", "bash", "sh"):
            (self.bin / (name + ".cmd")).write_text(f'@echo started>>"{marker}"\r\n@exit /b 99\r\n', encoding="utf-8")
            script = self.bin / name
            script.write_text(f'#!/bin/sh\nprintf started >> "{marker.as_posix()}"\nexit 99\n', encoding="utf-8")
            script.chmod(0o755)
        skill = self.tmp / "skill"
        (skill / "scripts").mkdir(parents=True)
        shutil.copytree(ROOT / "skills" / "specwright-review" / "references", skill / "references")
        output = self.tmp / "findings.json"
        document = self.native("run", "--kind", "preship", "--route", "codex", "--change", "demo-change",
                               "--base", "main", "--settings", self.settings, "--out", output,
                               scripts=skill / "scripts")
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), VALID)
        self.assertTrue(Path(document["record"]).is_file())
        self.assertFalse(marker.exists())
        self.assertFalse((skill / "scripts" / "review-run.sh").exists())

    def test_gate_passes_preport_record(self):
        fixture = json.loads((ROOT / "evals" / "review-routes" / "fixtures" / "preport-record.json").read_text(encoding="utf-8"))
        data = fixture["repository"]
        repo = self.tmp / "preport"
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main", "--object-format=sha1")
        for key, value in (("user.name", data["author_name"]), ("user.email", data["author_email"]),
                           ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
            self.git(repo, "config", key, value)
        self.extra_env.update({"GIT_AUTHOR_DATE": data["timestamp"], "GIT_COMMITTER_DATE": data["timestamp"],
                               "GIT_AUTHOR_NAME": data["author_name"], "GIT_AUTHOR_EMAIL": data["author_email"],
                               "GIT_COMMITTER_NAME": data["author_name"], "GIT_COMMITTER_EMAIL": data["author_email"]})
        self.commit(repo, data["base"], data["base_subject"])
        self.git(repo, "checkout", "-q", "-b", data["branch"])
        self.commit(repo, data["change"], data["change_subject"])
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), data["code_head"])
        self.code = repo
        common = self.git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        key = hashlib.sha256(common.encode("utf-8")).hexdigest()[:16]
        record = self.state_dir / "reviews" / key / "preport-record" / (data["code_head"] + ".json")
        record.parent.mkdir(parents=True)
        record.write_text(json.dumps(fixture["record"]), encoding="utf-8")
        document = self.native("gate", "--change", "preport-record", "--settings", self.settings)
        self.assertEqual(document["status"], "pass")
        self.assertEqual(document["heads"], fixture["record"]["heads"])
        self.assertEqual(document["reviewed_heads"], fixture["record"]["heads"])

    def test_gitbutler_backend_read_without_pr_pair(self):
        settings = self.code / "openspec" / "specwright.yaml"
        settings.parent.mkdir(exist_ok=True)
        settings.write_text("vcs: gitbutler\nfinish: pr\n", encoding="utf-8")
        scripts = self.tmp / "empty-scripts"
        scripts.mkdir()
        document = self.native("preflight", "--kind", "preship", "--change", "demo-change", "--base", "main",
                               "--settings", self.settings, scripts=scripts, expect=2)
        self.assertEqual(document["error"], "usage")
        self.assertIn("--branch", document["message"])

    def test_gitbutler_view_reads_named_tip_without_changing_workspace(self):
        # Real Git refs model the workspace/tree boundary without requiring a
        # platform-specific but binary. Real-but coverage remains in CI.
        self.install("claude")
        self.claude_result()
        content = "branch-tip\n" + "x" * (70 * 1024) + "\n"
        self.commit(self.code, {"openspec/specwright.yaml": "vcs: gitbutler\nfinish: pr\n",
                                ".gitattributes": "only-tip.txt export-ignore\n",
                                "only-tip.txt": content}, "feat: named review tip")
        tip = self.git(self.code, "rev-parse", "HEAD")
        self.git(self.code, "checkout", "-q", "-b", "gitbutler/workspace")
        self.commit(self.code, {"other-branch.txt": "workspace only\n"}, "chore: workspace tree")
        (self.code / "only-tip.txt").write_text("uncommitted workspace value\n", encoding="utf-8")
        workspace = self.git(self.code, "rev-parse", "HEAD")
        before = self.status()
        self.extra_env["FAKE_CLAUDE_READ"] = "only-tip.txt"
        out = self.preship("claude", store=False, extra=("--branch", "feat/demo"))
        run = self.runs("claude")[0]
        self.assertIn("only-tip.txt", run["cwd_files"])
        self.assertNotIn("other-branch.txt", run["cwd_files"])
        self.assertNotEqual(Path(run["cwd"]).resolve(), self.code.resolve())
        self.assertEqual(hashlib.sha256(run["read"][1].encode()).hexdigest(),
                         hashlib.sha256(content.encode()).hexdigest())
        self.assertEqual(json.loads(Path(out["record"]).read_text(encoding="utf-8"))["heads"], {"code": tip})
        self.assertEqual(self.git(self.code, "rev-parse", "HEAD"), workspace)
        self.assertEqual(self.status(), before)

    def test_select_sw_missing_starts_no_probe(self):
        self.install("codex")
        version = self.code / "openspec" / ".specwright" / "VERSION"
        version.parent.mkdir(parents=True, exist_ok=True)
        version.write_text("999.0.0\n", encoding="utf-8")
        self.extra_env["SPECWRIGHT_SW"] = require_sw()
        document = self.script("select", "--runtime", "other", "--settings", self.settings, expect=1)
        self.assertEqual(document["error"], "sw_missing")
        self.assertEqual(self.calls("codex"), [])

    def test_missing_sw_encodes_resolver_error(self):
        skills = self.tmp / "error-skills"
        scripts = skills / "specwright-review" / "scripts"
        scripts.mkdir(parents=True)
        shim = scripts / "review-run.sh"
        shutil.copy2(ROOT / "skills/specwright-review/scripts/review-run.sh", shim)
        resolver = skills / "specwright-pr/scripts/sw-path.sh"
        resolver.parent.mkdir(parents=True)
        resolver.write_text('#!/usr/bin/env bash\nprintf "%s" "$CONTROLLED_RESOLVER_ERROR" >&2\nexit 1\n',
                            encoding="utf-8")
        message = 'quoted "path" and \\backslash ' + "".join(chr(i) for i in range(1, 32)) + " λ"
        env = bash_path_env(environment=self.env())
        env.update({"VCS_TEST_SEARCH": env["PATH"], "CONTROLLED_RESOLVER_ERROR": message})
        result = subprocess.run([bashexe.bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"',
                                 "review-error", str(shim), "select", "--runtime", "other"],
                                cwd=self.code, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1, result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual(document["error"], "sw_missing")
        self.assertEqual(document["message"], message)


if __name__ == "__main__":
    unittest.main()
