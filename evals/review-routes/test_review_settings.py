"""Route controls through the real review entrypoint and executable reviewer fixtures."""
import hashlib
import http.server
import json
import shutil
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_review_run import Base, VERDICT_OK, c_values


class SettingsTests(Base):
    def design_ok(self, route, **kwargs):
        self.install(route)
        if route == "omp":
            events = [{"type": "agent_end", "messages": [{"role": "assistant", "content": [{"type": "text", "text": VERDICT_OK}]}]}]
            self.stdout_file(route, "\n".join(map(json.dumps, events)) + "\n")
        elif route == "claude":
            self.stdout_file(route, json.dumps({"type": "result", "result": VERDICT_OK}))
        else:
            self.stdout_file(route, VERDICT_OK)
        return self.design(route, **kwargs)

    def test_omp_tools_from_settings(self):
        self.set_settings("review:\n  routes:\n    omp:\n      tools: [read, grep, glob, lsp]\n")
        self.design_ok("omp")
        args = self.runs("omp")[0]["argv"]
        self.assertEqual(args[args.index("--tools") + 1], "read,grep,glob,lsp")
        self.assertTrue(all(flag in args for flag in ("--no-skills", "--no-extensions", "--no-rules", "--trusted-extension")))

    def test_codex_extra_disable_keeps_defaults(self):
        self.set_settings("review:\n  routes:\n    codex:\n      disable: [apps, new_feature]\n")
        self.design_ok("codex")
        args = self.runs("codex")[0]["argv"]
        disabled = {args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--disable"}
        self.assertTrue({"apps", "new_feature", "image_generation", "memories", "hooks", "goals", "sleep_tool"} <= disabled)
        self.assertIn("web_search=\"disabled\"", c_values(args))
        self.assertEqual(args[args.index("-s") + 1], "read-only")

    def test_claude_extra_arg_after_fixed_flags(self):
        self.set_settings('review:\n  routes:\n    claude:\n      args: ["--no-session-persistence"]\n')
        self.design_ok("claude")
        args = self.runs("claude")[0]["argv"]
        self.assertGreater(args.index("--no-session-persistence"), args.index("--restricted"))

    def refused(self, text, key, error="route_setting_unsafe"):
        self.set_settings(text)
        self.install("codex", "omp", "claude")
        for operation in ("select", "run"):
            args = ("select", "--runtime", "other") if operation == "select" else (
                "run", "--kind", "design", "--route", "codex", "--change", "demo-change",
                "--prompt-file", self.put("prompt.md", "Review."), "--out", self.tmp / "denied.md")
            out = self.script(*args, "--settings", self.settings, expect=1)
            self.assertEqual(out.get("error"), error)
            self.assertIn(key, out["message"])
        for name in ("codex", "omp", "claude"):
            self.assertEqual(self.calls(name), [], f"{name} must not even be probed")
        self.assertFalse((self.tmp / "denied.md").exists())
        self.assertEqual(list(self.state_dir.rglob("*.json")), [])

    def test_wrong_route_key_bad_route_setting(self):
        self.refused("review:\n  routes:\n    codex:\n      tools: [read]\n", "review.routes.codex.tools", "bad_route_setting")

    def test_tools_string_bad_route_setting(self):
        self.refused('review:\n  routes:\n    omp:\n      tools: "read,grep"\n', "review.routes.omp.tools", "bad_route_setting")

    def test_claude_bash_tool_refused(self):
        self.refused("review:\n  routes:\n    claude:\n      tools: [Read, Bash]\n", "review.routes.claude.tools")

    def test_omp_refused_tools(self):
        for tool in ("write", "learn", "find", "eval", "ast_edit", "debug", "github", "checkpoint", "retain"):
            with self.subTest(tool=tool):
                self.refused(f"review:\n  routes:\n    omp:\n      tools: [read, {tool}]\n", "review.routes.omp.tools")

    def test_codex_sandbox_flags_refused(self):
        for flag in ("--sandbox=danger-full-access", "--yolo", "--not-so-yolo", "-sdanger-full-access", "--enable=apps"):
            with self.subTest(flag=flag):
                self.refused(f"review:\n  routes:\n    codex:\n      args: [{json.dumps(flag)}]\n", "review.routes.codex.args")

    def test_codex_protected_key_forms_refused(self):
        for value in ('features={apps=true}', '"features"."apps"=true', 'windows={sandbox="none"}', ' sandbox_mode = "danger-full-access"'):
            with self.subTest(value=value):
                self.refused(f"review:\n  routes:\n    codex:\n      args: [-c, {json.dumps(value)}]\n", "review.routes.codex.args")

    def test_omp_owned_flags_refused(self):
        self.refused('review:\n  routes:\n    omp:\n      args: ["--session-dir=old"]\n', "review.routes.omp.args")

    def test_omp_user_trusted_module_refused_before_probe(self):
        self.refused('review:\n  routes:\n    omp:\n      args: ["--trusted-extension=untrusted.mjs"]\n', "review.routes.omp.args")

    def test_default_omp_command_line(self):
        result = self.design_ok("omp")
        args = self.runs("omp")[0]["argv"]
        self.assertEqual(args[args.index("--tools") + 1], "read,grep,glob")
        self.assertEqual(args.count("--trusted-extension"), 1)
        self.assertEqual(result["receipt"].get("overlay"), {f"{key}.enabled": False for key in ("autolearn", "memories", "find", "fetch")})

    def test_default_codex_command_line(self):
        result = self.design_ok("codex")
        self.assertTrue({"apps", "image_generation", "memories", "hooks", "goals", "sleep_tool"} <= set(result["receipt"].get("disabled", [])))
        args = self.runs("codex")[0]["argv"]
        self.assertTrue(all(flag in args for flag in ("--ephemeral", "--ignore-rules", "--ignore-user-config", "--json")))
        self.assertNotIn("--output-last-message", args)

    def test_omp_below_floor_skipped_and_refused(self):
        self.install("omp", "claude")
        self.extra_env["FAKE_OMP_VERSION"] = "omp 18.18.9"
        self.set_settings("review:\n  order: [omp, claude]\n")
        selected = self.select(runtime="other")
        self.assertEqual(selected["route"], "claude")
        self.assertIn("18.19.0", selected["skipped"][0]["reason"])
        result = self.design("omp", expect=1)
        self.assertEqual(result["error"], "omp_too_old")
        self.assertEqual(self.runs("omp"), [])

    def test_codex_unknown_feature_fails_closed(self):
        self.install("codex", "claude")
        self.extra_env["FAKE_CODEX_EXIT"] = "1"
        self.stdout_file("codex", "unknown feature")
        result = self.design("codex", expect=3)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.calls("claude"), [])
        self.assertFalse((self.tmp / "review.md").exists())

    def test_receipt_effective_tools(self):
        self.set_settings("review:\n  routes:\n    omp:\n      tools: [read, grep, glob, lsp]\n")
        result = self.design_ok("omp")
        self.assertEqual(result["receipt"].get("tools"), ["read", "grep", "glob", "lsp"])
        self.assertEqual(result["receipt"].get("extra_args"), [])

    def test_refused_setting_writes_nothing(self):
        self.refused('review:\n  routes:\n    codex:\n      args: ["--yolo"]\n', "review.routes.codex.args")

    def policy_trial(self, cases, mode="normal", expect=0):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.requests += 1
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"remote fixture")
            def log_message(self, *_args):
                pass
        class Server(http.server.ThreadingHTTPServer):
            daemon_threads = True
            connections = 0
            requests = 0
            def get_request(self):
                client = super().get_request()
                self.connections += 1
                return client
        server = Server(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            records = cases(host, port) if callable(cases) else cases
            spec = {"cases": records, "cwd": str(self.code), "host": host, "port": port, "mode": mode}
            self.extra_env["FAKE_OMP_POLICY_CASES"] = str(self.put("policy-cases.json", json.dumps(spec)))
            self.extra_env["FAKE_OMP_POLICY_REPORT"] = str(self.tmp / "policy-report.json")
            self.extra_env["FAKE_OMP_NODE"] = shutil.which("node") or "node"
            self.put("review.md", "keep old review\n")
            result = self.design_ok("omp", expect=expect)
            path = self.tmp / "policy-report.json"
            self.assertTrue(path.is_file(), "reviewer fixture must execute the actual emitted module")
            report = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(server.connections, 0, report)
            self.assertEqual(server.requests, 0, report)
            return result, report
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_omp_remote_targets_blocked_without_requests(self):
        def cases(host, port):
            targets = [f"http://{host}:{port}/x", f"ssh://{host}:{port}/x", "fixture-mcp:resource",
                       f"local;http://{host}:{port}/x", json.dumps(["local", f"ssh://{host}:{port}/x"]),
                       f"local;!http://{host}:{port}/x", f"/http://{host}:{port}/x"]
            return [{"tool": tool, "input": {"path": target, **({"pattern": "needle"} if tool == "grep" else {})}, "remote": True}
                    for tool in ("read", "grep", "glob") for target in targets]
        _, report = self.policy_trial(cases)
        self.assertTrue(report["loaded"])
        self.assertTrue(all(item["blocked"] for item in report["results"]))

    def test_omp_local_target_compatibility(self):
        fixture = self.put("local spaces λ.txt", "local fixture needle\n")
        cases = [{"tool": "read", "input": {"path": str(fixture)}, "remote": False}]
        _, report = self.policy_trial(cases)
        self.assertEqual(report["results"][0]["output"], "local fixture needle\n")
        self.assertFalse(report["results"][0]["blocked"])

    def test_omp_optional_lsp_readonly_actions(self):
        self.set_settings("review:\n  routes:\n    omp:\n      tools: [read, grep, glob, lsp]\n")
        cases = [{"tool": "lsp", "input": {"action": action, "file": "mathutil.py"}, "remote": False}
                 for action in ("definition", "rename", "request", "reload")]
        _, report = self.policy_trial(cases)
        self.assertEqual([item["blocked"] for item in report["results"]], [False, True, True, True])

    def test_omp_policy_load_failure_writes_no_review(self):
        result, _ = self.policy_trial([], mode="load-failure", expect=3)
        self.assertEqual(result["status"], "failed")
        self.assertEqual((self.tmp / "review.md").read_text(encoding="utf-8"), "keep old review\n")
        self.assertEqual(list(self.state_dir.rglob("*.json")), [])
        self.assertEqual(len(self.runs("omp")), 1)

    def test_omp_policy_callback_failure_blocks_dispatch(self):
        result, report = self.policy_trial(lambda h, p: [{"tool": "read", "input": {"path": f"ssh://{h}:{p}/x"}, "remote": True}],
                                           mode="callback-failure", expect=3)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(report["results"][0]["blocked"])
        self.assertEqual(len(self.runs("omp")), 1)
        self.assertEqual((self.tmp / "review.md").read_text(encoding="utf-8"), "keep old review\n")

    def test_omp_receipt_identifies_executed_policy(self):
        result, report = self.policy_trial([])
        receipt = result["receipt"]
        self.assertEqual(receipt.get("policy_id"), "local-only-v1")
        self.assertEqual(receipt["policy_sha256"], report["sha256"])
        self.assertEqual(hashlib.sha256(report["module_source"].encode("utf-8")).hexdigest(), receipt["policy_sha256"])
        self.assertEqual(receipt.get("extra_args"), [])


if __name__ == "__main__":
    unittest.main()
