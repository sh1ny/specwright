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
from test_review_run import Base, ROOT, VALID, bashexe, bash_path_env, stamp_version, sw_home, swcall

sys.path.insert(0, str(ROOT / "evals" / "cli"))
from swharness import require_sw  # noqa: E402


class NativeReviewTests(Base):
    def native(self, *args, expect=0, env=None):
        run_env = env or self.env()
        run_env.setdefault("SPECWRIGHT_HOME", str(sw_home()))
        result = swcall.run(["review", *map(str, args)], cwd=self.code, env=run_env, text=False)  # direct entry
        self.assertEqual(result.returncode, expect, result.stderr.decode("utf-8", "replace") + repr(result.stdout))
        lines = result.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1, result.stdout)
        return json.loads(lines[0])

    def fake_codex(self):
        """A compiled `codex` in the test's bin directory that reports a valid findings document."""
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

    def test_preship_runs_without_python_or_bash(self):
        self.fake_codex()
        marker = self.tmp / "interpreter-started"
        for name in ("python", "python3", "bash", "sh"):
            (self.bin / (name + ".cmd")).write_text(f'@echo started>>"{marker}"\r\n@exit /b 99\r\n', encoding="utf-8")
            script = self.bin / name
            script.write_text(f'#!/bin/sh\nprintf started >> "{marker.as_posix()}"\nexit 99\n', encoding="utf-8")
            script.chmod(0o755)
        output = self.tmp / "findings.json"
        document = self.native("run", "--kind", "preship", "--route", "codex", "--change", "demo-change",
                               "--base", "main", "--settings", self.settings, "--out", output)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), VALID)
        self.assertTrue(Path(document["record"]).is_file())
        self.assertFalse(marker.exists())

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
        stamp_version(repo)  # untracked and excluded: the head above is unchanged
        common = self.git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        key = hashlib.sha256(common.encode("utf-8")).hexdigest()[:16]
        record = self.state_dir / "reviews" / key / "preport-record" / (data["code_head"] + ".json")
        record.parent.mkdir(parents=True)
        record.write_text(json.dumps(fixture["record"]), encoding="utf-8")
        document = self.native("gate", "--change", "preport-record", "--settings", self.settings)
        self.assertEqual(document["status"], "pass")
        self.assertEqual(document["heads"], fixture["record"]["heads"])
        self.assertEqual(document["reviewed_heads"], fixture["record"]["heads"])
        if os.name == "nt":
            profile = self.tmp / "Windows profile"
            bash_home = self.tmp / "custom Bash home"
            default_record = profile / ".cache" / "specwright" / record.relative_to(self.state_dir)
            default_record.parent.mkdir(parents=True)
            shutil.copyfile(record, default_record)
            for name, home_env in (
                ("profile", {"USERPROFILE": str(profile)}),
                ("drive-and-path", {"HOMEDRIVE": profile.drive,
                                    "HOMEPATH": str(profile)[len(profile.drive):]}),
            ):
                with self.subTest(default_home=name):
                    env = self.env()
                    for variable in ("SPECWRIGHT_STATE_DIR", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"):
                        env.pop(variable, None)
                    env.update({"HOME": str(bash_home), **home_env})
                    document = self.native("gate", "--change", "preport-record",
                                           "--settings", self.settings, env=env)
                    self.assertEqual(document["status"], "pass")
                    self.assertEqual(Path(document["record"]), default_record)
            env = self.env()
            for variable in ("SPECWRIGHT_STATE_DIR", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"):
                env.pop(variable, None)
            env["HOME"] = str(bash_home)
            document = self.native("gate", "--change", "preport-record",
                                   "--settings", self.settings, env=env, expect=1)
            self.assertEqual(document["error"], "internal_error")
            self.assertFalse((bash_home / ".cache").exists())

    def test_gitbutler_backend_read_without_pr_pair(self):
        settings = self.code / "openspec" / "specwright.yaml"
        settings.parent.mkdir(exist_ok=True)
        settings.write_text("vcs: gitbutler\nfinish: pr\n", encoding="utf-8")
        document = self.native("preflight", "--kind", "preship", "--change", "demo-change", "--base", "main",
                               "--settings", self.settings, expect=2)
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
        self.assertEqual(document["error"], "sw_mismatch")
        self.assertEqual(self.calls("codex"), [])

    def test_no_matching_sw_is_sw_mismatch(self):
        """A project whose VERSION is not the binary's stops at entry (native-cli A4) before any reviewer CLI starts."""
        self.install("codex")
        swcall.stamp(self.code, "999.0.0")
        document = self.script("select", "--runtime", "other", "--settings", self.settings, expect=1)
        self.assertEqual(document["error"], "sw_mismatch")
        self.assertEqual(self.calls("codex"), [], "a reviewer CLI started")
        swcall.stamp(self.code)
        self.script("select", "--runtime", "other", "--settings", self.settings)  # the control: the matching VERSION selects


if __name__ == "__main__":
    unittest.main()
