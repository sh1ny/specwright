"""review-run.sh select / run against fake codex, claude and omp CLIs (add-preship-review, group 3).

Run: python -m unittest discover evals/review-routes
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "specwright-review" / "scripts" / "review-run.sh"
FAKE = ROOT / "evals" / "fakes" / "reviewcli.py"
CHANGE = "demo-change"

FINDING = {"id": "F1", "priority": "P1", "category": "code", "file": "mathutil.py", "line": 3,
           "title": "clamp is wrong", "body": "returns the upper bound", "spec_class": None}
MINOR = {**FINDING, "id": "F2", "priority": "P2", "title": "nit", "line": None}
VALID = {"summary": "one real defect", "findings": [FINDING, MINOR]}
VERDICT_OK = "# Review\n\nLooks fine.\n\nVERDICT: approve\nCHANGES_APPLIED: none\n"


def rmtree(p):
    def onerr(func, path, _exc):
        os.chmod(path, 0o700)
        func(path)
    shutil.rmtree(p, onerror=onerr)


def clean_path():
    """PATH without any directory that holds a real codex, claude or omp, so `not installed` is real."""
    keep = []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d and not any(shutil.which(n, path=d) for n in ("codex", "claude", "omp")):
            keep.append(d)
    return os.pathsep.join(keep)


def pid_alive(pid):
    if sys.platform == "win32":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return re.search(rf"\b{pid}\b", r.stdout) is not None
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(rmtree, self.tmp)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.state_dir = self.tmp / "state"
        self.settings = self.tmp / "specwright.yaml"
        self.settings.write_text("", encoding="utf-8")
        self.extra_env = {}
        self.code = self.make_repo("code", "mathutil.py", "def clamp(v, lo, hi):\n    return v\n", "code",
                                   {"mathutil.py": "def clamp(v, lo, hi):\n    # CODE_MARKER_LINE\n    return max(lo, min(v, hi))\n"})
        self.store = self.make_repo("store", "plan.md", "# plan\n", "store",
                                    {"openspec/changes/demo-change/proposal.md": "STORE_MARKER_LINE needs clamp\n"})

    # ---- fixtures ----------------------------------------------------------------------------------------
    def env(self):
        e = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
        e.update({"PATH": str(self.bin) + os.pathsep + clean_path(), "SPECWRIGHT_STATE_DIR": str(self.state_dir),
                  "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "PYTHONIOENCODING": "utf-8"})
        e.update(self.extra_env)
        return e

    def git(self, cwd, *args):
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=self.env())
        self.assertEqual(r.returncode, 0, f"git {args}: {r.stderr}")
        return r.stdout.strip()

    def make_repo(self, name, first_file, first_text, tag, change):
        d = self.tmp / name
        d.mkdir()
        self.git(d, "init", "-q", "-b", "main")
        for k, v in (("user.name", "Eval Bot"), ("user.email", "eval@example.invalid"), ("commit.gpgsign", "false")):
            self.git(d, "config", k, v)
        self.commit(d, {first_file: first_text}, "chore: initial")
        self.git(d, "checkout", "-q", "-b", "feat/demo")
        self.commit(d, change, f"feat({CHANGE}): {tag} change")
        return d

    def commit(self, d, files, msg):
        for rel, text in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")
        self.git(d, "add", "-A")
        self.git(d, "commit", "-q", "-m", msg)

    def install(self, *names):
        for n in names:
            (self.bin / f"{n}.cmd").write_text(f'@"{sys.executable}" "{FAKE}" {n} %*\r\n', encoding="utf-8")
            sh = self.bin / n
            sh.write_text(f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "{FAKE.as_posix()}" {n} "$@"\n',
                          encoding="utf-8", newline="\n")
            sh.chmod(0o755)
            self.extra_env[f"FAKE_{n.upper()}_ARGV_LOG"] = str(self.tmp / f"{n}.log")

    def put(self, name, text):
        p = self.tmp / name
        p.write_text(text, encoding="utf-8", newline="\n")
        return p

    def set_settings(self, text):
        self.settings.write_text(text, encoding="utf-8", newline="\n")

    def calls(self, cli):
        p = self.tmp / f"{cli}.log"
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []

    def runs(self, cli):
        """The review calls of a fake: not the --version / config / models probes."""
        return [c for c in self.calls(cli) if c["argv"][:1] not in (["--version"], ["config"], ["models"])]

    def script(self, *args, cwd=None, expect=0):
        r = subprocess.run(["bash", str(SCRIPT), *map(str, args)], capture_output=True, text=True, env=self.env(),
                           cwd=cwd or self.code, encoding="utf-8")
        lines = r.stdout.strip().splitlines()
        if expect is not None:
            self.assertEqual(r.returncode, expect, f"{args}\nstdout: {r.stdout}\nstderr: {r.stderr}")
        self.assertEqual(len(lines), 1, f"want exactly one JSON line from {args}, got {r.stdout!r} / {r.stderr!r}")
        out = json.loads(lines[0])
        out["_rc"] = r.returncode
        return out

    def select(self, runtime="claude", expect=0):
        return self.script("select", "--runtime", runtime, "--settings", self.settings, expect=expect)

    def preship(self, route, expect=0, out="findings.json", store=True, extra=()):
        args = ["run", "--kind", "preship", "--route", route, "--out", self.tmp / out, "--change", CHANGE,
                "--base", "main", "--settings", self.settings, *extra]
        if store:
            args += ["--store", self.store, "--store-base", "main"]
        return self.script(*args, expect=expect)

    def design(self, route, expect=0, out="review.md"):
        prompt = self.put("design-prompt.md", "Review the design.\n")
        return self.script("run", "--kind", "design", "--route", route, "--out", self.tmp / out, "--change", CHANGE,
                           "--prompt-file", prompt, "--settings", self.settings, expect=expect)

    def stdout_file(self, cli, text):
        self.extra_env[f"FAKE_{cli.upper()}_STDOUT"] = str(self.put(f"{cli}-stdout.txt", text))

    def claude_result(self, findings=VALID, **extra):
        self.stdout_file("claude", json.dumps({"type": "result", "result": "done", "structured_output": findings, **extra}))

    def omp_events(self, findings=VALID, fenced=False):
        text = json.dumps(findings)
        if fenced:
            text = f"Here you go:\n```json\n{text}\n```\n"
        events = [{"type": "agent_start"},
                  {"type": "agent_end", "messages": [{"role": "user", "content": [{"type": "text", "text": "review"}]},
                                                      {"role": "assistant", "content": [{"type": "text", "text": text}]}]}]
        self.stdout_file("omp", "\n".join(json.dumps(e) for e in events) + "\n")

    def omp_session(self, model="openai-codex/gpt-6.1-sol", level="high"):
        lines = [{"type": "session", "id": "s1"}, {"type": "model_change", "model": model},
                 {"type": "thinking_level_change", "thinkingLevel": level},
                 {"type": "message", "message": {"role": "user", "content": "FIRST_RUN_MESSAGE"}}]
        self.extra_env["FAKE_OMP_SESSION"] = str(self.put("omp-session.jsonl", "\n".join(json.dumps(l) for l in lines) + "\n"))

    def repo_key(self):
        common = self.git(self.code, "rev-parse", "--path-format=absolute", "--git-common-dir")
        return hashlib.sha256(common.encode("utf-8")).hexdigest()[:16]

    def status(self):
        return (self.git(self.code, "status", "--porcelain"), self.git(self.store, "status", "--porcelain"),
                self.git(self.code, "ls-files", "-s"))


class SelectTests(Base):
    def by_route(self, out):
        return {s["route"]: s["reason"] for s in out["skipped"]}

    def test_select_skips_runtime_takes_codex(self):
        self.install("codex", "claude", "omp")
        out = self.select("claude")
        self.assertEqual(out["route"], "codex")
        self.assertEqual(self.by_route(out), {"claude": "current runtime"})

    def test_select_missing_first_route_takes_omp(self):
        self.install("claude", "omp")
        out = self.select("claude")
        self.assertEqual(out["route"], "omp")
        self.assertEqual(self.by_route(out), {"codex": "not installed", "claude": "current runtime"})

    def test_select_none_available_is_subagent(self):
        out = self.select("claude")
        self.assertEqual(out["route"], "subagent")
        self.assertEqual(self.by_route(out), {"codex": "not installed", "claude": "current runtime", "omp": "not installed"})

    def test_select_cross_model_false_no_probe(self):
        self.install("codex")
        self.set_settings("review:\n  cross_model: false\n")
        out = self.select("claude")
        self.assertEqual(out["route"], "subagent")
        self.assertEqual(self.calls("codex"), [])

    def test_select_unknown_route_exits_1(self):
        self.install("codex")
        self.set_settings("review:\n  order: [codex, gemini]\n")
        out = self.select("claude", expect=1)
        self.assertFalse(out["ok"])
        self.assertNotIn("route", out)
        for word in ("gemini", "codex", "claude", "omp"):
            self.assertIn(word, out["message"])
        self.assertEqual(self.calls("codex"), [])

    def test_select_failed_probe_moves_on(self):
        self.install("codex", "omp")
        self.extra_env["FAKE_CODEX_VERSION_EXIT"] = "3"
        out = self.select("claude")
        self.assertEqual(out["route"], "omp")
        self.assertTrue(self.by_route(out)["codex"].startswith("probe failed"))

    def test_omp_role_passed_as_model(self):
        self.install("omp")
        self.set_settings("review:\n  order: [omp]\n  models:\n    omp: \"@slow\"\n")
        self.omp_events()
        self.omp_session()
        sel = self.select("claude")
        self.assertEqual((sel["route"], sel["model"]), ("omp", "@slow"))
        self.preship("omp")
        argv = self.runs("omp")[0]["argv"]
        self.assertEqual(argv[argv.index("--model") + 1], "@slow")

    def test_omp_unknown_role_falls_to_next(self):
        self.install("omp", "claude")
        self.set_settings("review:\n  order: [omp, claude]\n  models:\n    omp: \"@nosuchrole\"\n")
        out = self.select("codex")
        self.assertEqual(out["route"], "claude")
        self.assertIn('Model "@nosuchrole" not found', self.by_route(out)["omp"])
        self.assertEqual(self.runs("omp"), [])

    def test_omp_provider_selector_probe(self):
        self.install("omp")
        self.set_settings("review:\n  order: [omp]\n  models:\n    omp: \"openai-codex/gpt-6.1-sol:high\"\n")
        self.extra_env["FAKE_OMP_MODELS"] = str(self.put("models.json", json.dumps(
            {"models": [{"id": "gpt-6.1-sol", "selector": "openai-codex/gpt-6.1-sol"}]})))
        self.assertEqual(self.select("claude")["route"], "omp")
        self.set_settings("review:\n  order: [omp]\n  models:\n    omp: \"nosuchprov/nosuch\"\n")
        out = self.select("claude")
        self.assertEqual(out["route"], "subagent")
        self.assertIn('Model "nosuchprov/nosuch" not found', self.by_route(out)["omp"])


class RunTests(Base):
    def test_omp_fresh_session_dir_per_run(self):
        self.install("omp")
        self.omp_events()
        self.omp_session()
        self.preship("omp", out="a.json")
        self.preship("omp", out="b.json")
        first, second = self.runs("omp")
        dirs = [c["argv"][c["argv"].index("--session-dir") + 1] for c in (first, second)]
        self.assertNotEqual(dirs[0], dirs[1])
        self.assertEqual(second["session_dir_before"], [])
        self.assertEqual(first["session_dir_before"], [])

    def test_command_lines_read_only_allowlists(self):
        self.install("codex", "claude", "omp")
        self.stdout_file("codex", json.dumps(VALID))
        self.claude_result()
        self.omp_events()
        before = self.status()
        for route in ("codex", "claude", "omp"):
            self.preship(route, out=f"{route}.json")
        self.assertEqual(self.status(), before)
        a = self.runs("codex")[0]["argv"]
        self.assertEqual(a[:8], ["exec", "-s", "read-only", "--ephemeral", "--ignore-rules", "--ignore-user-config",
                                 "--skip-git-repo-check", "--output-schema"])
        self.assertTrue(a[8].endswith(".json"))
        self.assertEqual((a[9], a[11], a[12:]), ("-o", "--json", ["-"]))
        self.assertEqual(len(a), 13)
        a = self.runs("claude")[0]["argv"]
        self.assertEqual(a[:7], ["-p", "--safe-mode", "--disable-slash-commands", "--tools", "Read,Grep,Glob", "--restricted",
                                 "--json-schema"])
        schema = json.loads(a[7])
        self.assertNotIn("$schema", schema)
        self.assertEqual(schema["required"], ["summary", "findings"])
        self.assertEqual(a[8:], ["--output-format", "json"])
        a = self.runs("omp")[0]["argv"]
        self.assertEqual(a[:7], ["-p", "--no-skills", "--no-extensions", "--no-rules", "--tools", "read,grep,find,glob",
                                 "--session-dir"])
        self.assertEqual(a[8:12], ["--mode", "json", "--model", "@default"])
        self.assertEqual(len(a), 13)
        self.assertTrue(a[12].startswith("@"))

    def test_model_and_thinking_flags(self):
        self.install("codex", "claude", "omp")
        self.set_settings("review:\n  models:\n    codex: gpt-x\n    claude: opus-y\n    omp: openai-codex/gpt-6.1-sol\n"
                          "  thinking:\n    codex: high\n    claude: max\n    omp: xhigh\n")
        self.stdout_file("codex", json.dumps(VALID))
        self.claude_result()
        self.omp_events()
        for route in ("codex", "claude", "omp"):
            self.preship(route, out=f"{route}.json")
        a = self.runs("codex")[0]["argv"]
        self.assertEqual(a[a.index("-m") + 1], "gpt-x")
        self.assertEqual(a[a.index("-c") + 1], "model_reasoning_effort=high")
        a = self.runs("claude")[0]["argv"]
        self.assertEqual((a[a.index("--model") + 1], a[a.index("--effort") + 1]), ("opus-y", "max"))
        a = self.runs("omp")[0]["argv"]
        self.assertEqual((a[a.index("--model") + 1], a[a.index("--thinking") + 1]), ("openai-codex/gpt-6.1-sol", "xhigh"))
        self.set_settings("review:\n  thinking:\n    omp: xhigh\n")
        self.preship("omp", out="role.json")
        self.assertNotIn("--thinking", self.runs("omp")[-1]["argv"])

    def test_prompt_embeds_code_and_store_diff(self):
        self.install("claude")
        self.claude_result()
        self.preship("claude", out="a.json")
        self.preship("claude", out="b.json")
        prompts = [c["stdin"] for c in self.runs("claude")]
        nonces = []
        for p in prompts:
            m = re.search(r"UNTRUSTED-BEGIN ([0-9a-f]{16,})", p)
            self.assertIsNotNone(m, p)
            nonce = m.group(1)
            nonces.append(nonce)
            region = p[p.index(f"UNTRUSTED-BEGIN {nonce}"):p.index(f"UNTRUSTED-END {nonce}")]
            self.assertIn("CODE_MARKER_LINE", region)
            self.assertIn("STORE_MARKER_LINE", region)
            self.assertIn("mathutil.py", p)
            self.assertIn(CHANGE, p)
            self.assertNotIn("CODE_MARKER_LINE", p[:p.index(f"UNTRUSTED-BEGIN {nonce}")])
        self.assertNotEqual(*nonces)

    def test_diff_over_bound_stops_before_reviewer(self):
        self.install("claude")
        self.claude_result()
        self.commit(self.code, {"big.txt": ("x" * 99 + "\n") * 15500}, "feat: big file")  # ~1.5 MB
        out = self.preship("claude", expect=1)
        self.assertEqual(out["error"], "diff_too_large")
        self.assertRegex(out["message"], r"\d")
        self.assertEqual(self.calls("claude"), [])
        self.assertFalse((self.tmp / "findings.json").exists())
        self.assertFalse(self.state_dir.exists() and list(self.state_dir.rglob("*.json")))

    def test_valid_findings_recorded(self):
        self.install("codex")
        self.stdout_file("codex", json.dumps(VALID))
        code_head, store_head = self.git(self.code, "rev-parse", "HEAD"), self.git(self.store, "rev-parse", "HEAD")
        out = self.preship("codex")
        self.assertEqual((out["ok"], out["status"], out["route"]), (True, "ok", "codex"))
        self.assertEqual(json.loads((self.tmp / "findings.json").read_text(encoding="utf-8")), VALID)
        self.assertEqual(out["blocking"], ["F1"])
        self.assertEqual(out["counts"], {"P0": 0, "P1": 1, "P2": 1, "P3": 0})
        rec_path = self.state_dir / "reviews" / self.repo_key() / CHANGE / f"{code_head}+{store_head}.json"
        self.assertTrue(rec_path.is_file(), out)
        self.assertEqual(Path(out["record"]).resolve(), rec_path.resolve())
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        self.assertEqual((rec["kind"], rec["change"], rec["route"], rec["waivers"]), ("preship", CHANGE, "codex", []))
        self.assertEqual(rec["heads"], {"code": code_head, "store": store_head})
        self.assertEqual(rec["findings"], VALID)
        self.assertEqual(rec["receipt"]["route"], "codex")
        self.assertNotIn("outcome", rec)

    def test_record_without_store_is_keyed_by_code_head(self):
        self.install("codex")
        self.stdout_file("codex", json.dumps(VALID))
        head = self.git(self.code, "rev-parse", "HEAD")
        out = self.preship("codex", store=False)
        self.assertEqual(Path(out["record"]).name, f"{head}.json")
        self.assertNotIn("STORE_MARKER_LINE", self.runs("codex")[0]["stdin"])

    def test_prose_output_invalid_no_fallthrough(self):
        self.install("codex", "claude", "omp")
        self.stdout_file("codex", "I reviewed it and found no issues.\n")
        out = self.preship("codex", expect=3)
        self.assertEqual((out["status"], out["route"]), ("invalid", "codex"))
        self.assertTrue(out["error"])
        self.assertEqual(self.runs("claude"), [])
        self.assertEqual(self.runs("omp"), [])
        self.assertFalse((self.tmp / "findings.json").exists())
        self.assertFalse(self.state_dir.exists() and list(self.state_dir.rglob("*.json")))

    def test_schema_violations_are_invalid(self):
        self.install("claude")
        spec_without_class = {**FINDING, "category": "spec", "spec_class": None}
        for bad in ({"summary": "x"}, {"summary": "x", "findings": [{**FINDING, "priority": "P9"}]},
                    {"summary": "x", "findings": [spec_without_class]},
                    {"summary": "x", "findings": [{**FINDING, "id": "F%d" % i} for i in range(101)]}):
            self.claude_result(bad)
            out = self.preship("claude", expect=3)
            self.assertEqual(out["status"], "invalid", bad)

    def test_spec_finding_with_class_is_valid(self):
        self.install("claude")
        self.claude_result({"summary": "x", "findings": [{**FINDING, "category": "spec", "spec_class": "clarification"}]})
        self.assertEqual(self.preship("claude")["status"], "ok")

    def test_record_design_without_verdict_invalid(self):
        # needs the `record` subcommand (group 4); stays red until then
        review = self.put("review.md", "# Review\n\nNo verdict here.\nCHANGES_APPLIED: none\n")
        out = self.script("record", "--kind", "design", "--change", CHANGE, "--result", review, "--route", "subagent",
                          "--settings", self.settings, expect=3)
        self.assertEqual(out["status"], "invalid")

    def test_design_two_verdicts_invalid_no_file(self):
        self.install("codex")
        self.stdout_file("codex", "VERDICT: approve\nmore\nVERDICT: reject\nCHANGES_APPLIED: none\n")
        out = self.design("codex", expect=3)
        self.assertEqual(out["status"], "invalid")
        self.assertFalse((self.tmp / "review.md").exists())
        argv = self.runs("codex")[0]["argv"]
        self.assertNotIn("--output-schema", argv)

    def test_design_valid_written_with_receipt_file(self):
        self.install("codex")
        self.stdout_file("codex", VERDICT_OK)
        out = self.design("codex")
        self.assertEqual((self.tmp / "review.md").read_text(encoding="utf-8"), VERDICT_OK)
        self.assertEqual(json.loads(Path(out["receipt_file"]).read_text(encoding="utf-8"))["route"], "codex")
        self.assertEqual(self.runs("codex")[0]["stdin"], "Review the design.\n")
        self.assertFalse(self.state_dir.exists() and list(self.state_dir.rglob("*.json")))

    def test_timeout_kills_reviewer_exit_3(self):
        self.install("codex", "claude")
        self.set_settings("review:\n  timeout: 2s\n")
        pid_file = self.tmp / "codex.pid"
        self.extra_env.update({"FAKE_CODEX_DELAY": "60", "FAKE_CODEX_PID_FILE": str(pid_file)})
        self.stdout_file("codex", json.dumps(VALID))
        started = time.time()
        out = self.preship("codex", expect=3)
        self.assertLess(time.time() - started, 30)
        self.assertEqual((out["status"], out["route"]), ("timeout", "codex"))
        pid = int(pid_file.read_text(encoding="utf-8"))
        deadline = time.time() + 10
        while pid_alive(pid) and time.time() < deadline:
            time.sleep(0.2)
        self.assertFalse(pid_alive(pid), "the reviewer process survived the deadline")
        self.assertEqual(self.runs("claude"), [])
        self.assertFalse((self.tmp / "findings.json").exists())

    def test_reviewer_crash_exit_3(self):
        self.install("codex")
        self.extra_env["FAKE_CODEX_EXIT"] = "7"
        out = self.preship("codex", expect=3)
        self.assertNotEqual(out["status"], "ok")

    def test_receipt_omp_actual_model_from_session(self):
        self.install("omp")
        self.omp_events(fenced=True)
        self.omp_session("openai-codex/gpt-6.1-sol", "high")
        out = self.preship("omp")
        r = out["receipt"]
        self.assertEqual((r["route"], r["requested_model"], r["actual_model"], r["actual_thinking"]),
                         ("omp", "@default", "gpt-6.1-sol", "high"))
        self.assertEqual(r["requested_thinking"], "default")
        for k in ("skipped", "cli_version", "started_at", "finished_at"):
            self.assertIn(k, r)
        rec = json.loads(Path(out["record"]).read_text(encoding="utf-8"))
        self.assertEqual(rec["receipt"]["actual_model"], "gpt-6.1-sol")

    def test_receipt_unknown_actual_model(self):
        self.install("claude")
        self.set_settings("review:\n  models:\n    claude: default\n")
        self.claude_result()
        r = self.preship("claude")["receipt"]
        self.assertEqual((r["route"], r["requested_model"], r["actual_model"], r["actual_thinking"]),
                         ("claude", "default", "unknown", "unknown"))
        self.assertNotIn("--model", self.runs("claude")[0]["argv"])

    def test_receipt_claude_model_from_model_usage(self):
        self.install("claude")
        self.claude_result(modelUsage={"claude-opus-5-5": {"inputTokens": 1}})
        self.assertEqual(self.preship("claude")["receipt"]["actual_model"], "claude-opus-5-5")

    def test_receipt_codex_model_unknown(self):
        self.install("codex")
        self.stdout_file("codex", json.dumps(VALID))
        r = self.preship("codex")["receipt"]
        self.assertEqual((r["actual_model"], r["actual_thinking"], r["requested_model"]), ("unknown", "unknown", "default"))

    def test_selection_skipped_in_receipt(self):
        self.install("codex", "claude")
        self.stdout_file("codex", json.dumps(VALID))
        sel = self.select("claude")
        selection = self.put("selection.json", json.dumps(sel))
        r = self.preship("codex", extra=("--selection", selection))["receipt"]
        self.assertEqual(r["skipped"], sel["skipped"])
        self.preship("claude", expect=2, extra=("--selection", selection))

    def test_run_subagent_route_is_usage_error(self):
        self.preship("subagent", expect=2)


SPEC_TEXT = "### Requirement: X\n\nThe system SHALL do X.\n"
ARCHIVE_SUBJECT = f"chore({CHANGE}): archive change"


class RecordGateTests(Base):
    """record, waive, gate, archive-only and rounds (add-preship-review, group 4)."""

    def setUp(self):
        super().setUp()
        for d in (self.code, self.store):
            self.plan(d)

    def plan(self, d):
        self.commit(d, {f"openspec/changes/{CHANGE}/proposal.md": "# proposal\n",
                        f"openspec/changes/{CHANGE}/specs/foo/spec.md": SPEC_TEXT}, f"docs({CHANGE}): plan")

    def archive(self, d, dated=True, extra=None, subject=ARCHIVE_SUBJECT):
        name = f"2026-10-12-{CHANGE}" if dated else CHANGE
        (d / "openspec" / "changes" / "archive").mkdir(parents=True, exist_ok=True)
        self.git(d, "mv", f"openspec/changes/{CHANGE}", f"openspec/changes/archive/{name}")
        files = {"openspec/specs/foo/spec.md": SPEC_TEXT, **(extra or {})}
        self.commit(d, files, subject)

    def head(self, d, rev="HEAD"):
        return self.git(d, "rev-parse", rev)

    def findings_file(self, findings=VALID, name="subagent-findings.json"):
        return self.put(name, json.dumps(findings))

    def record(self, findings=VALID, store=False, expect=0, kind="preship", route="subagent"):
        args = ["record", "--kind", kind, "--change", CHANGE, "--result", self.findings_file(findings), "--route", route,
                "--settings", self.settings]
        if store:
            args += ["--store", self.store]
        return self.script(*args, expect=expect)

    def gate(self, store=False, expect=0):
        args = ["gate", "--change", CHANGE, "--settings", self.settings]
        if store:
            args += ["--store", self.store]
        return self.script(*args, expect=expect)

    def waive(self, finding="F1", reason="accepted risk", store=False, expect=0):
        args = ["waive", "--change", CHANGE, "--finding", finding, "--reason", reason, "--settings", self.settings]
        if store:
            args += ["--store", self.store]
        return self.script(*args, expect=expect)

    def archive_only(self, base, head, d=None, expect=0, **kw):
        args = ["archive-only", "--base", base, "--head", head, "--change", CHANGE]
        if d is not None:
            args += ["--dir", d]
        for k, v in kw.items():
            args += [f"--{k}", v]
        return self.script(*args, expect=expect)

    def record_files(self):
        return sorted(self.state_dir.rglob("*.json")) if self.state_dir.exists() else []

    # ---- record ----------------------------------------------------------------------------------------
    def test_store_backed_record_names_both_heads(self):
        code_head, store_head = self.head(self.code), self.head(self.store)
        out = self.record(store=True)
        rec_path = self.state_dir / "reviews" / self.repo_key() / CHANGE / f"{code_head}+{store_head}.json"
        self.assertTrue(rec_path.is_file(), out)
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        self.assertEqual(rec["heads"], {"code": code_head, "store": store_head})
        self.assertEqual((rec["kind"], rec["change"], rec["route"], rec["waivers"], rec["findings"]),
                         ("preship", CHANGE, "subagent", [], VALID))
        for k in ("base", "receipt", "at"):
            self.assertIn(k, rec)
        self.assertNotIn("outcome", rec)

    def test_record_preship_repo_local_keyed_by_code_head(self):
        out = self.record()
        self.assertEqual(Path(out["record"]).name, f"{self.head(self.code)}.json")

    def test_record_preship_invalid_exit_3_no_record(self):
        out = self.record({"summary": "x"}, expect=3)
        self.assertEqual(out["status"], "invalid")
        self.assertEqual(self.record_files(), [])

    def test_record_preship_prose_exit_3_no_record(self):
        p = self.put("prose.json", "no issues found\n")
        out = self.script("record", "--kind", "preship", "--change", CHANGE, "--result", p, "--route", "subagent",
                          "--settings", self.settings, expect=3)
        self.assertEqual(out["status"], "invalid")
        self.assertEqual(self.record_files(), [])

    def test_record_design_valid_writes_no_record(self):
        review = self.put("review.md", VERDICT_OK)
        out = self.script("record", "--kind", "design", "--change", CHANGE, "--result", review, "--route", "subagent",
                          "--settings", self.settings)
        self.assertTrue(out["ok"])
        self.assertEqual(self.record_files(), [])

    def test_record_design_two_verdicts_invalid(self):
        review = self.put("review.md", "VERDICT: a\nVERDICT: b\nCHANGES_APPLIED: none\n")
        out = self.script("record", "--kind", "design", "--change", CHANGE, "--result", review, "--route", "subagent",
                          "--settings", self.settings, expect=3)
        self.assertEqual(out["status"], "invalid")

    # ---- gate ------------------------------------------------------------------------------------------
    def test_gate_missing_without_record(self):
        out = self.gate()
        self.assertEqual((out["status"], out["reviewed_heads"]), ("missing", None))
        self.assertEqual(out["heads"], {"code": self.head(self.code)})

    def test_gate_pass_with_only_p2_p3(self):
        self.record({"summary": "ok", "findings": [MINOR, {**MINOR, "id": "F3", "priority": "P3"}]})
        out = self.gate()
        self.assertEqual((out["status"], out["open"]), ("pass", []))
        self.assertEqual(out["reviewed_heads"], out["heads"])

    def test_gate_blocked_with_p1(self):
        self.record()
        out = self.gate()
        self.assertEqual(out["status"], "blocked")
        self.assertEqual([f["id"] for f in out["open"]], ["F1"])

    def test_gate_missing_after_new_commit(self):
        self.record()
        self.commit(self.code, {"mathutil.py": "def clamp(v, lo, hi):\n    return v\n"}, f"fix({CHANGE}): clamp")
        self.assertEqual(self.gate()["status"], "missing")

    def test_waive_turns_blocked_into_pass(self):
        self.record()
        out = self.waive("F1", "accepted: clamp is a stub")
        self.assertTrue(out["ok"])
        gate = self.gate()
        self.assertEqual((gate["status"], gate["open"]), ("pass", []))
        rec = json.loads(Path(self.record_files()[0]).read_text(encoding="utf-8"))
        self.assertEqual(len(rec["waivers"]), 1)
        self.assertEqual((rec["waivers"][0]["id"], rec["waivers"][0]["reason"]), ("F1", "accepted: clamp is a stub"))
        self.assertIn("at", rec["waivers"][0])
        self.assertEqual(list(Path(self.record_files()[0]).parent.glob("*.tmp")), [])

    def test_waive_unknown_finding_exit_1(self):
        self.record()
        out = self.waive("F99", expect=1)
        self.assertIn("F99", out["message"])
        self.assertEqual(self.gate()["status"], "blocked")

    def test_waive_without_record_exit_1(self):
        out = self.waive(expect=1)
        self.assertEqual(out["error"], "no_record")

    def test_waive_store_backed_targets_both_heads_record(self):
        self.record(store=True)
        self.waive(store=True)
        self.assertEqual(self.gate(store=True)["status"], "pass")

    def test_gate_store_backed_missing_when_store_moves(self):
        self.record(store=True)
        self.commit(self.store, {"plan.md": "# plan 2\n"}, f"docs({CHANGE}): more")
        self.assertEqual(self.gate(store=True)["status"], "missing")

    def test_gate_missing_after_non_archive_commit(self):
        self.record({"summary": "ok", "findings": []})
        self.commit(self.code, {"extra.py": "x = 1\n"}, f"feat({CHANGE}): extra")
        self.assertEqual(self.gate()["status"], "missing")

    def test_gate_accepts_archive_commit_repo_local(self):
        reviewed = self.head(self.code)
        self.record({"summary": "ok", "findings": []})
        self.archive(self.code)
        out = self.gate()
        self.assertEqual(out["status"], "pass")
        self.assertEqual(out["reviewed_heads"], {"code": reviewed})
        self.assertEqual(out["heads"], {"code": self.head(self.code)})

    def test_gate_archive_commit_still_blocked_when_record_blocked(self):
        self.record()
        self.archive(self.code)
        self.assertEqual(self.gate()["status"], "blocked")

    def test_gate_archive_plus_other_commit_is_missing(self):
        self.record({"summary": "ok", "findings": []})
        self.archive(self.code)
        self.commit(self.code, {"extra.py": "x = 1\n"}, f"feat({CHANGE}): extra")
        self.assertEqual(self.gate()["status"], "missing")

    def test_gate_archive_commit_touching_other_files_is_missing(self):
        self.record({"summary": "ok", "findings": []})
        self.archive(self.code, extra={"src.py": "x = 1\n"})
        self.assertEqual(self.gate()["status"], "missing")

    def test_gate_accepts_store_archive_commit(self):
        code_head, reviewed_store = self.head(self.code), self.head(self.store)
        self.record({"summary": "ok", "findings": []}, store=True)
        self.archive(self.store)
        out = self.gate(store=True)
        self.assertEqual(out["status"], "pass")
        self.assertEqual(out["reviewed_heads"], {"code": code_head, "store": reviewed_store})
        self.assertEqual(out["heads"], {"code": code_head, "store": self.head(self.store)})

    def test_gate_store_archive_does_not_cover_code_moving(self):
        self.record({"summary": "ok", "findings": []}, store=True)
        self.archive(self.store)
        self.commit(self.code, {"extra.py": "x = 1\n"}, f"feat({CHANGE}): extra")
        self.assertEqual(self.gate(store=True)["status"], "missing")

    # ---- archive-only ----------------------------------------------------------------------------------
    def test_archive_only_true_for_archive_commit(self):
        base = self.head(self.code)
        self.archive(self.code)
        out = self.archive_only(base, self.head(self.code))
        self.assertEqual(out["archive_only"], True)
        self.assertIn("reason", out)

    def test_archive_only_true_undated_archive_name(self):
        base = self.head(self.code)
        self.archive(self.code, dated=False)
        self.assertTrue(self.archive_only(base, self.head(self.code))["archive_only"])

    def test_archive_only_false_outside_paths(self):
        base = self.head(self.code)
        self.archive(self.code, extra={"README.md": "edit\n"})
        out = self.archive_only(base, self.head(self.code))
        self.assertEqual(out["archive_only"], False)
        self.assertIn("README.md", out["reason"])

    def test_archive_only_false_spec_of_other_capability(self):
        base = self.head(self.code)
        self.archive(self.code, extra={"openspec/specs/other/spec.md": SPEC_TEXT})
        self.assertFalse(self.archive_only(base, self.head(self.code))["archive_only"])

    def test_archive_only_false_two_commits(self):
        base = self.head(self.code)
        self.commit(self.code, {"extra.py": "x = 1\n"}, f"feat({CHANGE}): extra")
        self.archive(self.code)
        out = self.archive_only(base, self.head(self.code))
        self.assertEqual(out["archive_only"], False)
        self.assertRegex(out["reason"], "commit")

    def test_archive_only_false_wrong_subject(self):
        base = self.head(self.code)
        self.archive(self.code, subject=f"chore({CHANGE}): tidy up")
        self.assertFalse(self.archive_only(base, self.head(self.code))["archive_only"])

    def test_archive_only_false_other_change_name_in_subject(self):
        base = self.head(self.code)
        self.archive(self.code, subject="chore(other-change): archive change")
        self.assertFalse(self.archive_only(base, self.head(self.code))["archive_only"])

    def test_archive_only_custom_prefix(self):
        self.git(self.code, "mv", "openspec", "plans")
        self.git(self.code, "commit", "-q", "-m", "chore: move planning root")
        base = self.head(self.code)
        (self.code / "plans" / "changes" / "archive").mkdir(parents=True, exist_ok=True)
        self.git(self.code, "mv", f"plans/changes/{CHANGE}", f"plans/changes/archive/{CHANGE}")
        self.commit(self.code, {"plans/specs/foo/spec.md": SPEC_TEXT}, ARCHIVE_SUBJECT)
        self.assertFalse(self.archive_only(base, self.head(self.code))["archive_only"])
        self.assertTrue(self.archive_only(base, self.head(self.code), prefix="plans")["archive_only"])

    def test_archive_only_in_store_dir(self):
        base = self.head(self.store)
        self.archive(self.store)
        out = self.archive_only(base, self.head(self.store), d=self.store)
        self.assertEqual(out["archive_only"], True)
        # the same shas mean nothing in the code repo: a git error stops (exit 1), never a false positive
        out = self.script("archive-only", "--base", base, "--head", self.head(self.store), "--change", CHANGE, expect=1)
        self.assertEqual(out["ok"], False)

    # ---- rounds ----------------------------------------------------------------------------------------
    def round_commit(self, d, n, name):
        self.commit(d, {name: f"{n}\n"}, f"fix({CHANGE}): address pre-ship review\n\nPreship-Round: {n}")

    def rounds(self, store=False):
        args = ["rounds", "--change", CHANGE, "--settings", self.settings]
        if store:
            args += ["--store", self.store]
        return self.script(*args)

    def test_rounds_zero_without_trailers(self):
        self.assertEqual(self.rounds()["rounds"], 0)

    def test_rounds_reads_preship_round_trailers(self):
        self.round_commit(self.code, 1, "a.txt")
        self.round_commit(self.code, 2, "b.txt")
        self.assertEqual(self.rounds()["rounds"], 2)

    def test_rounds_takes_highest_across_both_repos(self):
        self.round_commit(self.code, 1, "a.txt")
        self.round_commit(self.store, 2, "b.txt")
        self.assertEqual(self.rounds(store=True)["rounds"], 2)
        self.assertEqual(self.rounds()["rounds"], 1)

    def test_rounds_without_records_from_git(self):
        self.round_commit(self.code, 1, "a.txt")
        self.round_commit(self.code, 2, "b.txt")
        self.record()
        shutil.rmtree(self.state_dir)  # a new session or machine: no records
        self.assertEqual(self.rounds()["rounds"], 2)

    def test_rounds_ignores_commits_on_main(self):
        self.git(self.code, "checkout", "-q", "main")
        self.round_commit(self.code, 5, "m.txt")
        self.git(self.code, "checkout", "-q", "feat/demo")
        self.git(self.code, "merge", "-q", "--no-edit", "main")
        self.assertEqual(self.rounds()["rounds"], 0)

    def test_rounds_ignores_feedback_trailer(self):
        self.commit(self.code, {"f.txt": "1\n"}, f"fix({CHANGE}): address review feedback\n\nFeedback-Round: 3")
        self.assertEqual(self.rounds()["rounds"], 0)


if __name__ == "__main__":
    unittest.main()
