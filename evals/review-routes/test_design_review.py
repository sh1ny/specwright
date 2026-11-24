"""Exercise the FULL design workflow through sw and executable reviewer routes."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_review_run import Base, CHANGE, VERDICT_OK

BRANCH = "feat/demo"
REVISE = "# Review\n\n## Findings\n- The lock outlives the host.\n\nVERDICT: REVISE\nCHANGES_APPLIED: n/a\n"
CONDITIONAL = "# Review\n\nVERDICT: APPROVE_WITH_CHANGES\nCHANGES_APPLIED: no\n\n## Required Changes\nWait for exit.\n"
CONFIRMED = CONDITIONAL.replace("CHANGES_APPLIED: no", "CHANGES_APPLIED: yes")


class TestDesignReview(Base):
    def setUp(self):
        super().setUp()
        self.root = self.code / "openspec" / "changes" / CHANGE
        self.root.mkdir(parents=True)
        self.proposal = self.root / "proposal.md"
        self.proposal.write_text("# Proposal\n\n## Why\nLock lifecycle.\n\n## Release Notes\nOriginal notes.\n", encoding="utf-8")
        self.plan = self.root / "design.md"
        self.plan.write_text("TIER: FULL\nDesign A\n", encoding="utf-8")
        self.review = self.root / "review.md"
        self.config = self.code / "openspec" / "specwright.yaml"
        self.prompt = self.put("brief.md", "Follow the review checklist and template.\n")

    def project_settings(self, text):
        self.config.write_text(text, encoding="utf-8")

    def select_full(self):
        return self.script("select", "--change-review", "--branch", BRANCH, "--runtime", "other")

    def args(self, selection, repair="none", recheck=False):
        path = self.put("selection.json", json.dumps(selection))
        return ["--kind", "design", "--change-review", "--change", CHANGE, "--branch", BRANCH,
                "--out", self.review, "--selection", path, "--repairs", repair,
                *(["--recheck"] if recheck else [])]

    def step(self, *extra, expect=0):
        return self.script("design-step", "--branch", BRANCH, "--out", self.review, *extra, expect=expect)

    def choice(self, round_, choice, detail=None):
        return self.step("--round", round_, "--choice", choice, *([] if detail is None else ["--detail", detail]))

    def scratch(self, repair="none", recheck=False, expect=0):
        args = self.args(self.select_full(), repair, recheck)
        return self.script("record", "--scratch", *args, expect=expect)

    def complete(self, started, answer, expect=0):
        from pathlib import Path
        path = Path(started["scratch"])
        path.write_bytes(answer.encode("utf-8") if isinstance(answer, str) else answer)
        return self.script("record", *self.args(self.select_full()), "--result", path,
                           "--attempt", started["attempt"], "--route", "subagent", expect=expect)

    def run_cli(self, answer, repair="none", recheck=False, expect=0, selection=None):
        self.stdout_file("claude", json.dumps({"type": "result", "result": answer}))
        selection = selection or self.select_full()
        return self.script("run", *self.args(selection, repair, recheck), "--route", selection["route"],
                           "--prompt-file", self.prompt, expect=expect)

    def subagent(self, limit=None):
        self.project_settings("review:\n  cross_model: false\n" + ("" if limit is None else f"  design_max_rounds: {limit}\n"))

    def cli(self, limit=None):
        self.install("claude")
        self.project_settings("review:\n  order: [claude]\n" + ("" if limit is None else f"  design_max_rounds: {limit}\n"))

    def test_default_checkpoint_keeps_revise(self):
        self.cli()
        for index in range(1, 4):
            self.run_cli(REVISE, f"Repair {index}")
            state = self.step()
            self.assertEqual(state["round"], index)
            self.assertEqual(state["status"], "owner_checkpoint" if index == 3 else "review")
        old = self.review.read_bytes()
        self.assertIn(b"The lock outlives the host", old)
        self.assertIn(b"Repair 2", old)
        self.assertEqual(self.run_cli(VERDICT_OK, expect=1)["error"], "owner_checkpoint")
        self.assertEqual(len(self.runs("claude")), 3)
        self.assertEqual(self.review.read_bytes(), old)
        self.assertEqual([l for l in old.splitlines() if l.startswith(b"VERDICT:")], [b"VERDICT: REVISE"])

    def test_scoped_pass_survives_replacement(self):
        self.subagent(1)
        self.complete(self.scratch(), REVISE)
        self.choice(1, "scoped-pass", "Check only lock exit\nVERDICT: APPROVE")
        self.complete(self.scratch("Wait for exact host exit"), REVISE)
        self.assertEqual(self.step()["status"], "owner_checkpoint")
        record = self.review.read_text(encoding="utf-8")
        self.assertIn("scoped-pass", record)
        self.assertIn("Wait for exact host exit", record)
        self.assertEqual([l for l in record.splitlines() if l.startswith("VERDICT:")], ["VERDICT: REVISE"])

    def test_scope_change_requires_changed_artifacts(self):
        self.subagent(1)
        self.complete(self.scratch(), REVISE)
        self.choice(1, "scope-change", "Remove cross-process feature")
        self.proposal.write_text(self.proposal.read_text(encoding="utf-8").replace("Original notes.", "New notes."), encoding="utf-8")
        self.assertEqual(self.scratch(expect=1)["error"], "scope_unchanged")
        self.plan.write_text("TIER: FULL\nSmaller design\n", encoding="utf-8")
        self.complete(self.scratch(), VERDICT_OK)
        self.assertEqual(self.step()["status"], "pass")
        self.assertIn(b"Remove cross-process feature", self.review.read_bytes())

    def test_stop_stays_stopped(self):
        self.subagent(1)
        self.complete(self.scratch(), REVISE)
        self.assertEqual(self.scratch(expect=1)["error"], "owner_checkpoint")
        self.assertNotIn(b"Owner round 1", self.review.read_bytes())
        self.choice(1, "stop")
        self.assertEqual(self.step()["status"], "stopped")
        self.assertEqual(self.scratch(expect=1)["error"], "stopped")
        self.assertIn(b"stop", self.review.read_bytes())

    def test_custom_cap_blocks_conditional(self):
        self.cli(1)
        self.run_cli(CONDITIONAL)
        self.assertEqual(self.step()["status"], "owner_checkpoint")
        self.assertEqual(self.run_cli(CONFIRMED, recheck=True, expect=1)["error"], "owner_checkpoint")

    def test_approval_at_cap(self):
        self.cli(2)
        self.run_cli(CONDITIONAL)
        self.plan.write_text("TIER: FULL\nWait for exit.\n", encoding="utf-8")
        self.run_cli(CONFIRMED, recheck=True)
        self.assertEqual(self.step()["status"], "pass")
        self.assertEqual(self.step()["round"], 2)

    def test_legacy_override_still_passes(self):
        self.review.write_text("VERDICT: USER_OVERRIDE\nCHANGES_APPLIED: n/a\n", encoding="utf-8")
        self.assertEqual(self.step()["status"], "pass")

    def test_legacy_unpinned_approval_requires_full_review(self):
        self.subagent()
        for old in (VERDICT_OK, CONFIRMED):
            with self.subTest(verdict=old):
                self.review.write_bytes(old.encode("utf-8"))
                self.assertEqual(self.step()["status"], "review")
                self.assertEqual(self.scratch(recheck=True, expect=1)["error"], "full_review_required")
                self.assertEqual(self.review.read_bytes(), old.encode("utf-8"))

    def test_full_rules_use_branch_blobs_on_both_routes(self):
        self.cli()
        files = {"rules/windows.md": "Wait for exit.\nFull café text.\n", "rules/order.md": "Order before timing.\n"}
        self.commit(self.code, files, "rules")
        (self.code / "rules/windows.md").write_text("uncommitted replacement", encoding="utf-8")
        declaration = "  standing_rules: [rules/windows.md, rules/order.md]\n"
        self.project_settings("review:\n  order: [claude]\n" + declaration)
        self.run_cli(REVISE)
        prompt = self.runs("claude")[-1]["stdin"]
        self.project_settings("review:\n  cross_model: false\n" + declaration)
        sub = self.scratch()["standing_requirements"]
        self.assertIn("## Standing requirements (binding)", sub)
        self.assertIn("existing tests the design preserves", sub)
        self.assertIn(sub, prompt)
        self.assertLess(sub.index(files["rules/windows.md"]), sub.index(files["rules/order.md"]))
        self.assertNotIn("uncommitted replacement", prompt)

    def test_no_rules_does_not_add_section(self):
        self.cli()
        self.run_cli(REVISE)
        self.assertNotIn("Standing requirements (binding)", self.runs("claude")[-1]["stdin"])
        self.project_settings("review:\n  cross_model: false\n  standing_rules: []\n")
        self.assertNotIn("standing_requirements", self.scratch())

    def test_linked_spec_tree_refuses_full_review(self):
        self.subagent()
        outside = self.tmp / "outside-specs"
        outside.mkdir()
        (outside / "spec.md").write_text("Uncaptured requirement.\n", encoding="utf-8")
        link = self.root / "specs" / "capability"
        link.parent.mkdir()
        if os.name == "nt":
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            link.symlink_to(outside, target_is_directory=True)
        try:
            self.assertEqual(self.scratch(expect=1)["error"], "bad_design_artifact")
            self.assertFalse(self.review.exists())
        finally:
            if os.name == "nt":
                link.rmdir()
            else:
                link.unlink()

    def test_fenced_release_heading_does_not_hide_proposal_edits(self):
        self.subagent()
        for fence, info in (("````", "markdown"), ("~~~", "markdown"), ("<!--", "")):
            with self.subTest(fence=fence):
                close = "-->" if fence == "<!--" else fence
                before = f"# Proposal\n\n{fence}{info}\n## Release Notes\n{close}\n\nRequire draining.\n"
                self.proposal.write_bytes(before.encode("utf-8"))
                attempt = self.scratch()
                self.proposal.write_bytes(before.replace("draining", "aborting").encode("utf-8"))
                self.assertEqual(self.complete(attempt, VERDICT_OK, expect=1)["error"], "stale_review")
                self.assertFalse(self.review.exists())

        before = "# Proposal\n\n## Release Notes\nExample:\n```\n## Sample\n```\nNotes here.\n\n## Rollback\nKeep the backup.\n"
        self.proposal.write_bytes(before.encode("utf-8"))
        attempt = self.scratch()
        self.proposal.write_bytes(before.replace("Notes here.", "Updated notes.").encode("utf-8"))
        self.complete(attempt, VERDICT_OK)
        self.proposal.write_bytes(before.replace("Keep the backup.", "Delete the backup.").encode("utf-8"))
        self.assertEqual(self.step()["status"], "review")

    def test_raw_html_cannot_hide_proposal_edits(self):
        self.subagent()
        for opening, closing in (
            ("<div class=\"example\">", "</div>"),
            ("<pre>\n", "</pre>"),
            ("<example-panel>", "</example-panel>"),
            ("<?example", "?>"),
        ):
            with self.subTest(opening=opening):
                before = f"# Proposal\n\n{opening}\n## Release Notes\n{closing}\n\nRequire draining.\n"
                self.proposal.write_bytes(before.encode("utf-8"))
                self.complete(self.scratch(), VERDICT_OK)
                self.proposal.write_bytes(before.replace("draining", "aborting").encode("utf-8"))
                self.assertEqual(self.step()["status"], "review")

        before = "# Proposal\n\n<div>\n## A raw heading\n</div>\n\n## Release Notes\nOld notes.\n"
        self.proposal.write_bytes(before.encode("utf-8"))
        attempt = self.scratch()
        self.proposal.write_bytes(before.replace("Old notes.", "New notes.").encode("utf-8"))
        self.complete(attempt, VERDICT_OK)
        self.assertEqual(self.step()["status"], "pass")

    def test_setext_heading_after_release_notes_stays_reviewed(self):
        self.subagent()
        for underline in ("--------", "========"):
            with self.subTest(underline=underline):
                before = f"# Proposal\n\n## Release Notes\nOriginal notes.\n\nRollback\n{underline}\nKeep the backup.\n"
                self.proposal.write_bytes(before.encode("utf-8"))
                self.complete(self.scratch(), VERDICT_OK)
                self.proposal.write_bytes(before.replace("Keep the backup.", "Delete the backup.").encode("utf-8"))
                self.assertEqual(self.step()["status"], "review")

    def test_ambiguous_notes_fence_does_not_hide_dedented_heading(self):
        self.subagent()
        before = (
            "# Proposal\n\n## Release Notes\n- Example:\n\n"
            "  ```text\n  sample\n\n## Rollback\nKeep the backup.\n"
        )
        self.proposal.write_bytes(before.encode("utf-8"))
        self.complete(self.scratch(), VERDICT_OK)
        self.proposal.write_bytes(before.replace("Keep the backup.", "Delete the backup.").encode("utf-8"))
        self.assertEqual(self.step()["status"], "review")
        self.proposal.write_bytes(before.replace("sample", "new sample").encode("utf-8"))
        self.assertEqual(self.step()["status"], "review")

    def test_release_heading_matches_release_validation(self):
        self.subagent()
        before = "# Proposal\n\n## \tReLeAsE nOtEs\nOriginal notes.\n\n## Rollback\nKeep the backup.\n"
        self.proposal.write_bytes(before.encode("utf-8"))
        self.complete(self.scratch(), VERDICT_OK)
        self.proposal.write_bytes(before.replace("Original notes.", "Updated notes.").encode("utf-8"))
        self.assertEqual(self.step()["status"], "pass")

    def test_bad_rule_fails_before_reviewer(self):
        self.cli()
        (self.code / "not-tracked.md").write_text("not versioned", encoding="utf-8")
        for path in ("../outside.md", "not-tracked.md", "missing.md"):
            with self.subTest(path=path):
                self.project_settings(f"review:\n  order: [claude]\n  standing_rules: [{path}]\n")
                self.assertIn(path, self.run_cli(REVISE, expect=1)["message"])
        self.assertEqual(self.runs("claude"), [])
        self.assertFalse(self.review.exists())

    def test_other_review_modes_do_not_resolve_rules(self):
        self.cli()
        settings = "review:\n  standing_rules: [missing.md]\n"
        self.project_settings(settings)
        self.plan.write_text("TIER: LIGHT\nNo architecture triggers.\n", encoding="utf-8")
        self.assertEqual(self.step("--light")["status"], "light")
        verdict = self.put("light.md", "VERDICT: SKIPPED_LIGHT\nCHANGES_APPLIED: n/a\n")
        self.script("record", "--kind", "light", "--out", self.review, "--result", verdict)
        self.assertIn(b"VERDICT: SKIPPED_LIGHT", self.review.read_bytes())
        self.set_settings(settings)
        self.stdout_file("claude", json.dumps({"type": "result", "result": VERDICT_OK}))
        self.design("claude")
        self.claude_result()
        self.preship("claude")
        self.assertTrue(all("Standing requirements (binding)" not in r["stdin"] for r in self.runs("claude")))

    def test_rules_change_requires_full_review(self):
        self.cli()
        self.run_cli(CONDITIONAL)
        self.commit(self.code, {"rules.md": "Wait for exit.\n"}, "rules")
        self.project_settings("review:\n  order: [claude]\n  standing_rules: [rules.md]\n")
        self.assertEqual(self.run_cli(CONFIRMED, recheck=True, expect=1)["error"], "full_review_required")
        self.run_cli(VERDICT_OK)
        self.assertEqual(self.step()["status"], "pass")
        self.commit(self.code, {"rules.md": "Wait for the exact process.\n"}, "update rules")
        self.assertEqual(self.step()["status"], "review")

    def test_settings_pin_and_stale_selection(self):
        self.cli()
        self.commit(self.code, {"openspec/specwright.yaml": "vcs: gitbutler\nreview:\n  order: [claude]\n"}, "settings")
        selection = self.select_full()
        self.commit(self.code, {"openspec/specwright.yaml": "vcs: gitbutler\nreview:\n  order: [claude]\n  design_max_rounds: 4\n"}, "new settings")
        self.assertEqual(self.run_cli(REVISE, selection=selection, expect=1)["error"], "stale_selection")
        self.project_settings("vcs: gitbutler\nreview:\n  cross_model: false\n")
        self.assertEqual(self.script("select", "--change-review", "--branch", BRANCH, "--runtime", "other", expect=1)["error"], "settings_not_pinned")
        self.assertFalse(self.runs("claude"))

    def test_subagent_capture_and_stale_publication(self):
        from pathlib import Path
        self.subagent(1)
        self.complete(self.scratch(), REVISE)
        self.choice(1, "scoped-pass", "Lock only")
        first = self.scratch()
        copy = Path(first["artifacts"]["design"])
        self.plan.write_text("TIER: FULL\nDesign B\n", encoding="utf-8")
        self.assertIn("Design A", copy.read_text(encoding="utf-8"))
        self.plan.write_text("TIER: FULL\nDesign A\n", encoding="utf-8")
        self.complete(first, REVISE)
        self.choice(2, "scoped-pass", "Lock only again")
        second = self.scratch()
        old = self.review.read_bytes()
        self.plan.write_text("TIER: FULL\nDesign C\n", encoding="utf-8")
        self.assertEqual(self.complete(second, VERDICT_OK, expect=1)["error"], "stale_review")
        self.assertEqual(self.review.read_bytes(), old)
        self.complete(self.scratch(), VERDICT_OK)
        self.assertEqual(self.step()["round"], 3)

    def test_conditional_baseline_preserves_exact_dispatch_bytes(self):
        self.subagent()
        original = self.proposal.read_bytes()
        live = original.replace(b"Original notes.", b"Notes changed after dispatch.")
        first = self.scratch()
        self.assertEqual(Path(first["artifacts"]["proposal"]).read_bytes(), original)
        self.proposal.write_bytes(live)
        self.complete(first, CONDITIONAL)
        recheck = self.scratch(recheck=True)
        self.assertEqual(Path(recheck["prior_artifacts"]["proposal"]).read_bytes(), original)
        self.assertEqual(Path(recheck["artifacts"]["proposal"]).read_bytes(), live)
        self.complete(recheck, CONFIRMED)
        self.assertEqual(self.step()["status"], "pass")

    def test_changed_dispatch_capture_cannot_create_conditional_baseline(self):
        self.subagent(1)
        self.complete(self.scratch(), REVISE)
        self.choice(1, "scoped-pass", "Verify graceful exit")
        previous = self.review.read_bytes()
        first = self.scratch()
        capture = Path(first["artifacts"]["proposal"])
        capture.write_bytes(capture.read_bytes().replace(b"Original notes.", b"Modified private copy."))
        self.assertEqual(self.complete(first, CONDITIONAL, expect=1)["error"], "stale_review")
        self.assertEqual(self.review.read_bytes(), previous)
        self.complete(self.scratch(), VERDICT_OK)
        self.assertEqual(self.step()["status"], "pass")

    def test_changed_attempt_evidence_rejects_full_and_recheck_verdicts(self):
        self.subagent(1)
        self.complete(self.scratch(), REVISE)
        self.choice(1, "scoped-pass", "Verify graceful exit")
        previous = self.review.read_bytes()
        first = self.scratch()
        Path(first["artifacts"]["design"]).unlink()
        self.assertEqual(self.complete(first, VERDICT_OK, expect=1)["error"], "stale_review")
        self.assertEqual(self.review.read_bytes(), previous)
        self.complete(self.scratch(), CONDITIONAL)
        self.choice(2, "scoped-pass", "Check the Required Changes")
        previous = self.review.read_bytes()

        for artifact in ("artifacts", "prior_artifacts", "prior_review"):
            with self.subTest(artifact=artifact):
                attempt = self.scratch(recheck=True)
                path = Path(attempt[artifact] if artifact == "prior_review" else attempt[artifact]["proposal"])
                original = b"Wait for exit." if artifact == "prior_review" else b"Original notes."
                path.write_bytes(path.read_bytes().replace(original, b"Modified captured evidence."))
                self.assertEqual(self.complete(attempt, CONFIRMED, expect=1)["error"], "stale_review")
                self.assertEqual(self.review.read_bytes(), previous)
        self.complete(self.scratch(recheck=True), CONFIRMED)
        self.assertEqual(self.step()["status"], "pass")

    def test_reopened_recheck_refuses_changed_cached_baseline(self):
        self.subagent()
        first = self.scratch()
        self.complete(first, CONDITIONAL)
        previous = self.review.read_bytes()
        # Corrupt only Release Notes in the persisted cache: the normalized
        # review fingerprint is unchanged, but these are not the reviewed bytes.
        cached, = self.state_dir.glob("change-review/*/baselines/*/proposal.md")
        cached.write_bytes(cached.read_bytes().replace(b"Original notes.", b"Incorrect baseline notes."))
        self.assertEqual(self.scratch(recheck=True, expect=1)["error"], "full_review_required")
        self.assertEqual(self.review.read_bytes(), previous)
        self.complete(self.scratch(), CONDITIONAL)
        self.complete(self.scratch(recheck=True), CONFIRMED)
        self.assertEqual(self.step()["status"], "pass")

    def test_recheck_cannot_renew_baseline(self):
        from pathlib import Path
        self.subagent()
        first = self.scratch()
        self.complete(first, CONFIRMED, expect=3)
        self.assertFalse(self.review.exists())
        self.complete(self.scratch(), CONDITIONAL)
        self.plan.write_text("TIER: FULL\nWait for exit, plus unrelated policy.\n", encoding="utf-8")
        recheck = self.scratch(recheck=True)
        self.assertIn("Design A", Path(recheck["prior_artifacts"]["design"]).read_text(encoding="utf-8"))
        self.assertIn("unrelated policy", Path(recheck["artifacts"]["design"]).read_text(encoding="utf-8"))
        self.assertEqual(recheck["mode"], "recheck")
        self.assertIn("## Required Changes\nWait for exit.", Path(recheck["prior_review"]).read_text(encoding="utf-8"))
        old = self.review.read_bytes()
        self.complete(recheck, CONDITIONAL, expect=3)
        self.assertEqual(self.review.read_bytes(), old)
        self.complete(self.scratch(recheck=True), REVISE)
        self.assertEqual(self.scratch(recheck=True, expect=1)["error"], "full_review_required")
        self.cli(4)
        self.run_cli(CONDITIONAL)
        old = self.review.read_bytes()
        self.run_cli(CONDITIONAL, recheck=True, expect=3)
        prompt = self.runs("claude")[-1]["stdin"]
        self.assertIn("Prior full-review artifacts:", prompt)
        self.assertIn("Prior review:", prompt)
        self.assertRegex(prompt, r"(?i)if .*outside the Required Changes, return REVISE\b")
        self.assertEqual(self.review.read_bytes(), old)

    def test_other_writers_cannot_erase_checkpoint(self):
        self.cli(1)
        self.run_cli(REVISE)
        old = self.review.read_bytes()
        self.plan.write_text("TIER: LIGHT\nNo architecture triggers.\n", encoding="utf-8")
        self.assertEqual(self.step("--light")["status"], "full_required")
        result = self.put("light.md", "VERDICT: SKIPPED_LIGHT\nCHANGES_APPLIED: n/a\n")
        self.script("record", "--kind", "light", "--out", self.review, "--result", result, expect=1)
        self.script("record", "--kind", "design", "--route", "subagent", "--change", CHANGE,
                    "--out", self.review, "--result", result, expect=1)
        self.script("run", "--kind", "design", "--route", "claude", "--change", CHANGE,
                    "--out", self.review, "--prompt-file", self.prompt, expect=1)
        self.assertEqual(self.review.read_bytes(), old)
        self.assertEqual(len(self.runs("claude")), 1)

    def test_failed_revalidation_releases_publication_lock(self):
        self.subagent(1)
        self.complete(self.scratch(), REVISE)
        self.choice(1, "scoped-pass", "Lock only")
        attempt = self.scratch()
        old = self.review.read_bytes()
        # Pass the actual selection of the attempt, but make the named ref unavailable.
        from pathlib import Path
        selected = self.args(self.select_full())
        result = Path(attempt["scratch"])
        result.write_text(REVISE, encoding="utf-8")
        self.git(self.code, "branch", "-m", "feat/temporarily-moved")
        self.script("record", *selected, "--result", result, "--route", "subagent", "--attempt", attempt["attempt"], expect=1)
        self.assertEqual(self.review.read_bytes(), old)
        self.git(self.code, "branch", "-m", BRANCH)
        self.complete(self.scratch(), VERDICT_OK)
        self.assertEqual(self.step()["status"], "pass")

    def test_interrupted_slots_and_bounded_failure(self):
        from pathlib import Path
        self.subagent(1)
        self.complete(self.scratch(), REVISE)
        self.choice(1, "scoped-pass", "Check the lock")
        old = self.review.read_bytes()
        a, b = self.scratch(), self.scratch()
        self.assertEqual(self.scratch(expect=1)["error"], "design_attempt_limit")
        failure = self.complete(a, "invalid one", expect=3)
        diagnostic = Path(failure["diagnostic"])
        self.assertFalse(Path(a["scratch"]).exists())
        self.assertEqual(diagnostic.read_bytes(), b"invalid one")
        failure = self.complete(b, "invalid two", expect=3)
        self.assertEqual(Path(failure["diagnostic"]), diagnostic)
        self.assertEqual(diagnostic.read_bytes(), b"invalid two")
        large = self.scratch()
        failure = self.complete(large, "a" * (2 * 1024 * 1024 + 1), expect=3)
        self.assertNotIn("diagnostic", failure)
        self.assertFalse(Path(large["scratch"]).exists())
        self.assertEqual(self.review.read_bytes(), old)
        self.assertEqual(self.step()["round"], 1)
        self.complete(self.scratch(), VERDICT_OK)

    def test_malformed_utf8_keeps_scoped_pass_and_record(self):
        self.subagent(1)
        self.complete(self.scratch(), REVISE)
        self.choice(1, "scoped-pass", "Verify graceful exit")
        previous = self.review.read_bytes()
        for count in (1, 1536 * 1024):
            with self.subTest(count=count):
                attempt = self.scratch()
                malformed = b"\xff" * count + b"\n" + VERDICT_OK.encode("utf-8")
                rejected = self.complete(attempt, malformed, expect=3)
                self.assertEqual(rejected["error"], "invalid_output")
                self.assertIn("UTF-8", rejected["message"])
                self.assertNotIn("diagnostic", rejected)
                self.assertFalse(Path(attempt["scratch"]).exists())
                self.assertEqual(self.review.read_bytes(), previous)
                self.assertEqual(self.step()["round"], 1)
        self.complete(self.scratch(), VERDICT_OK)
        self.assertEqual(self.step()["status"], "pass")

    def test_unreadable_route_refuses_before_capture(self):
        self.install("claude", "omp")
        for route in ("omp", "claude"):
            with self.subTest(route=route):
                self.project_settings(f"review:\n  order: [{route}]\n  routes:\n    {route}:\n      tools: []\n")
                outcome = self.run_cli(REVISE, expect=1)
                self.assertEqual(outcome["error"], "design_route_cannot_read")
                self.assertFalse(self.runs(route))
                self.assertFalse(self.review.exists())


if __name__ == "__main__":
    unittest.main()
