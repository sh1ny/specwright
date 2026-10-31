"""Change ranges read the tip of the named change branch, never HEAD (GitButler: HEAD is the workspace commit).

Real `but` workspace with `feat/b` and `feat/add-c` applied. `review-run.sh` and `release.sh check` run in it with
`--branch feat/add-c`; a pre-ship step without `--branch` stops on a `vcs: gitbutler` project.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from butenv import Scratch, require_but
from gbnet import GitButlerNetworkCase

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "skills" / "specwright-review" / "scripts" / "review-run.sh"
RELEASE = ROOT / "skills" / "specwright-release" / "scripts" / "release.sh"
FAKE = ROOT / "evals" / "fakes" / "reviewcli.py"
CHANGE = "add-c"
BRANCH = "feat/add-c"
CLEAN = {"summary": "nothing to report", "findings": []}
NIT = {"summary": "one nit", "findings": [{"id": "F1", "priority": "P2", "category": "code", "file": "c.txt", "line": None,
                                           "title": "nit", "body": "minor", "spec_class": None}]}


class GitButlerRangeCase(GitButlerNetworkCase):
    def pair(self, scratch, settings="vcs: gitbutler\nfinish: pr\n"):
        """`feat/b` (b.txt) and `feat/add-c` (c.txt) applied; the settings sit in the repo's own openspec/specwright.yaml."""
        repo = self.managed(scratch)
        self.settings(repo.path, settings)
        self.repo_path = repo.path
        for branch in ("feat/b", BRANCH):
            repo.but("branch", "new", branch)
            self.commit_on(repo, branch, branch.split("/")[-1] + ".txt")
        return repo

    def env(self, scratch, **extra):
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        env = {**scratch.env, "SPECWRIGHT_STATE_DIR": str(self.root / "state"), "PYTHONIOENCODING": "utf-8",
               "FAKE_CLAUDE_ARGV_LOG": str(self.root / "claude.log"), **extra}
        env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
        return env

    def install_claude(self, scratch):
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / "claude.cmd").write_text('@"%s" "%s" claude %%*\r\n' % (sys.executable, FAKE), encoding="utf-8")
        shim = bin_dir / "claude"
        shim.write_text('#!/bin/sh\nexec "%s" "%s" claude "$@"\n' % (Path(sys.executable).as_posix(), FAKE.as_posix()),
                        encoding="utf-8", newline="\n")
        shim.chmod(0o755)

    def claude_runs(self):
        log = self.root / "claude.log"
        calls = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
        return [c for c in calls if c["argv"][:1] not in (["--version"], ["config"], ["models"])]

    def script(self, script, scratch, repo, *args, expected=0, env=None):
        done = subprocess.run(["bash", str(script), *map(str, args)], cwd=repo.path, env=env or self.env(scratch),
                              capture_output=True, text=True, encoding="utf-8")
        lines = done.stdout.strip().splitlines()
        self.assertEqual(done.returncode, expected, "%s\nstdout: %s\nstderr: %s" % (args, done.stdout, done.stderr))
        self.assertEqual(len(lines), 1, "want one JSON line from %s, got %r / %r" % (args, done.stdout, done.stderr))
        return json.loads(lines[0])

    def review(self, scratch, repo, command, *args, expected=0):
        return self.script(REVIEW, scratch, repo, command, *args, expected=expected)

    def preflight(self, scratch, repo, *extra, expected=0):
        out = self.review(scratch, repo, "preflight", "--kind", "preship", "--change", CHANGE, "--base", "main", *extra,
                          expected=expected)
        path = self.root / "preflight.json"
        path.write_text(json.dumps(out), encoding="utf-8")
        return out, path

    def record(self, scratch, repo, preflight, findings=CLEAN, expected=0):
        result = self.root / "findings.json"
        result.write_text(json.dumps(findings), encoding="utf-8")
        return self.review(scratch, repo, "record", "--kind", "preship", "--change", CHANGE, "--result", result,
                           "--route", "subagent", "--preflight", preflight, "--branch", BRANCH, expected=expected)

    def gate(self, scratch, repo, expected=0):
        return self.review(scratch, repo, "gate", "--change", CHANGE, "--branch", BRANCH, expected=expected)

    def commit_archive(self, repo):
        """The archive commit on the change branch: one new archive directory, the subject finish writes."""
        archive = repo.path / "openspec" / "changes" / "archive" / ("2026-10-30-" + CHANGE)
        archive.mkdir(parents=True)
        (archive / "proposal.md").write_text("# archived\n", encoding="utf-8")
        repo.but("commit", "-b", BRANCH, "-m", "docs(%s): archive change" % CHANGE, "--json",
                 "openspec/changes/archive/2026-10-30-%s/" % CHANGE)


class TestGitButlerRanges(GitButlerRangeCase):
    def test_preship_range_uses_branch_tip(self):
        require_but()
        with Scratch() as scratch:
            repo = self.pair(scratch)
            self.install_claude(scratch)
            tips = {name: self.tip(repo, name) for name in ("feat/b", BRANCH)}
            head = self.git(repo.path, "rev-parse", "HEAD").stdout.strip()
            self.assertNotIn(head, tips.values(), "HEAD is the workspace commit")
            selection = self.root / "findings-out.json"
            stdout = self.root / "claude-stdout.json"
            stdout.write_text(json.dumps({"type": "result", "result": "done", "structured_output": CLEAN}), encoding="utf-8")
            env = self.env(scratch, FAKE_CLAUDE_STDOUT=str(stdout))

            result = self.script(REVIEW, scratch, repo, "run", "--kind", "preship", "--route", "claude", "--out", selection,
                                 "--change", CHANGE, "--base", "main", "--branch", BRANCH, env=env)

            self.assertEqual(result["status"], "ok", result)
            prompt = self.claude_runs()[0]["stdin"]
            begin = re.search(r"UNTRUSTED-BEGIN ([0-9a-f]+)", prompt).group(1)
            region = prompt[prompt.index("UNTRUSTED-BEGIN " + begin):prompt.index("UNTRUSTED-END " + begin)]
            self.assertIn("c.txt", region, "the change's own commit is reviewed")
            self.assertNotIn("b.txt", region, "no commit of feat/b is in the reviewed diff")
            self.assertEqual(Path(result["record"]).name, tips[BRANCH] + ".json", "the record names the branch tip")
            record = json.loads(Path(result["record"]).read_text(encoding="utf-8"))
            self.assertEqual(record["heads"], {"code": tips[BRANCH]})
            # the preflight reads the same tip
            out, _ = self.preflight(scratch, repo, "--branch", BRANCH)
            self.assertEqual(out["heads"], {"code": tips[BRANCH]})

    def test_preship_reviewer_reads_copy_of_branch_tip(self):
        # the working tree holds feat/b's files too: a CLI reviewer runs in a copy of the change branch's tip
        require_but()
        with Scratch() as scratch:
            repo = self.pair(scratch)
            self.install_claude(scratch)
            tip = self.tip(repo, BRANCH)
            self.assertTrue((repo.path / "b.txt").is_file(), "feat/b's file is in the working tree")
            stdout = self.root / "claude-stdout.json"
            stdout.write_text(json.dumps({"type": "result", "result": "done", "structured_output": CLEAN}), encoding="utf-8")
            env = self.env(scratch, FAKE_CLAUDE_STDOUT=str(stdout))

            result = self.script(REVIEW, scratch, repo, "run", "--kind", "preship", "--route", "claude", "--out",
                                 self.root / "out.json", "--change", CHANGE, "--base", "main", "--branch", BRANCH, env=env)

            self.assertEqual(result["status"], "ok", result)
            run = self.claude_runs()[0]
            self.assertIn("add-c.txt", run["cwd_files"], "the reviewer's directory lacks the change's file")
            self.assertNotIn("b.txt", run["cwd_files"], "the reviewer reads feat/b's file from the shared working tree")
            self.assertNotEqual(Path(run["cwd"]).resolve(), repo.path.resolve())
            self.assertIn("a copy of the files at %s" % tip, run["stdin"])
            self.assertIn("Code repository: %s" % Path(run["cwd"]).as_posix(), run["stdin"].replace("\\", "/"))

    def test_preship_copy_keeps_export_ignored_files(self):
        require_but()
        with Scratch() as scratch:
            repo = self.pair(scratch)
            self.install_claude(scratch)
            (repo.path / ".gitattributes").write_text("add-c.txt export-ignore\n", encoding="utf-8")
            repo.but("commit", "-b", BRANCH, "-m", "attrs", "--json", ".gitattributes")
            stdout = self.root / "claude-stdout.json"
            stdout.write_text(json.dumps({"type": "result", "result": "done", "structured_output": CLEAN}), encoding="utf-8")
            env = self.env(scratch, FAKE_CLAUDE_STDOUT=str(stdout))

            result = self.script(REVIEW, scratch, repo, "run", "--kind", "preship", "--route", "claude", "--out",
                                 self.root / "out.json", "--change", CHANGE, "--base", "main", "--branch", BRANCH, env=env)

            self.assertEqual(result["status"], "ok", result)
            files = self.claude_runs()[0]["cwd_files"]
            self.assertIn("add-c.txt", files, "an export-ignore file is missing from the reviewer's copy")
            self.assertIn(".gitattributes", files)

    def test_gate_after_archive_resolves_branch_tip(self):
        require_but()
        with Scratch() as scratch:
            repo = self.pair(scratch)
            _, preflight = self.preflight(scratch, repo, "--branch", BRANCH)
            reviewed = self.tip(repo, BRANCH)
            self.record(scratch, repo, preflight)
            self.commit_archive(repo)
            other = self.tip(repo, "feat/b")
            self.assertNotEqual(self.tip(repo, BRANCH), reviewed)
            self.assertEqual(self.git(repo.path, "rev-parse", self.tip(repo, BRANCH) + "^").stdout.strip(), reviewed)

            gate = self.gate(scratch, repo)

            self.assertEqual(gate["status"], "pass", gate)
            self.assertEqual(gate["heads"], {"code": self.tip(repo, BRANCH)})
            self.assertEqual(gate["reviewed_heads"], {"code": reviewed}, "the pass recorded for the archive commit's parent")
            self.assertEqual(self.tip(repo, "feat/b"), other)
            waived = self.review(scratch, repo, "waive", "--change", CHANGE, "--finding", "F9", "--reason", "x",
                                 "--branch", BRANCH, expected=1)
            self.assertEqual(waived["error"], "unknown_finding", "waive found the same record the gate used")

    def test_branch_moved_voids_record(self):
        require_but()
        with Scratch() as scratch:
            repo = self.pair(scratch)
            _, preflight = self.preflight(scratch, repo, "--branch", BRANCH)
            self.record(scratch, repo, preflight)
            self.assertEqual(self.gate(scratch, repo)["status"], "pass")
            self.commit_on(repo, BRANCH, "fix.txt")  # a fix commit lands on the branch after the review

            moved = self.record(scratch, repo, preflight, expected=3)
            gate = self.gate(scratch, repo)

            self.assertEqual(moved["error"], "heads_moved", moved)
            self.assertEqual(gate["status"], "missing", gate)
            self.assertEqual(gate["heads"], {"code": self.tip(repo, BRANCH)})
            self.assertIsNone(gate["reviewed_heads"])

    def test_without_branch_stops(self):
        require_but()
        with Scratch() as scratch:
            repo = self.pair(scratch, settings="vcs: gitbutler\nfinish: pr\nrelease:\n  enabled: true\n"
                                                    "  version_files:\n    VERSION: '^(\\d+\\.\\d+\\.\\d+)$'\n")
            self.install_claude(scratch)
            out = self.root / "out.json"
            for command in (("preflight", "--kind", "preship", "--change", CHANGE, "--base", "main"),
                            ("run", "--kind", "preship", "--route", "claude", "--out", out, "--change", CHANGE, "--base", "main"),
                            ("gate", "--change", CHANGE), ("rounds", "--change", CHANGE, "--base", "main"),
                            ("waive", "--change", CHANGE, "--finding", "F1", "--reason", "x")):
                result = self.review(scratch, repo, *command, expected=2)
                self.assertEqual(result["error"], "usage", command)
                self.assertIn("--branch", result["message"], command)
            self.assertEqual(self.claude_runs(), [], "no review ran")
            self.assertFalse(out.exists())
            check = self.script(RELEASE, scratch, repo, "check", "--main", "main", expected=2)
            self.assertEqual(check["error"], "usage")
            self.assertIn("--branch", check["message"])

    def test_release_check_reads_branch_tip(self):
        require_but()
        with Scratch() as scratch:
            repo = self.managed(scratch)
            self.settings(repo.path, "vcs: gitbutler\nfinish: pr\nrelease:\n  enabled: true\n  version_files:\n"
                                     "    VERSION: '^(\\d+\\.\\d+\\.\\d+)$'\n")
            self.repo_path = repo.path
            side = self.clone_of_origin(scratch)  # main already holds version 0.1.0
            (side / "VERSION").write_text("0.1.0\n", encoding="utf-8")
            self.side_git(side, "add", "VERSION")
            self.side_git(side, "commit", "-q", "-m", "chore: version")
            self.side_git(side, "push", "-q", "origin", "HEAD:refs/heads/main")
            repo.but("pull")
            self.assertEqual(self.git(repo.path, "show", "refs/heads/main:VERSION").stdout.strip(), "0.1.0")
            for branch in ("feat/b", BRANCH):
                repo.but("branch", "new", branch)
            (repo.path / "VERSION").write_text("0.2.0\n", encoding="utf-8")
            repo.but("commit", "-b", "feat/b", "-m", "chore: bump", "--json", "VERSION")  # feat/b bumps
            self.commit_on(repo, BRANCH, "c.txt")                                           # feat/add-c does not
            self.assertEqual((repo.path / "VERSION").read_text(encoding="utf-8").strip(), "0.2.0",
                             "the work tree carries feat/b's bump")

            result = self.script(RELEASE, scratch, repo, "check", "--main", "main", "--branch", BRANCH)

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["version"], "0.1.0", "the version files are read at the tip of feat/add-c")
            self.assertEqual(result["files"], ["VERSION"])
            missing = self.script(RELEASE, scratch, repo, "check", "--main", "main", "--branch", "feat/nope", expected=1)
            self.assertEqual(missing["error"], "branch_not_found", missing)

    def test_release_plain_check_reads_work_tree(self):
        # the bump task's verification: `check` without --main reads the working tree, also on GitButler
        require_but()
        with Scratch() as scratch:
            repo = self.pair(scratch, settings="vcs: gitbutler\nfinish: pr\nrelease:\n  enabled: true\n  version_files:\n"
                                                    "    VERSION: '^(\\d+\\.\\d+\\.\\d+)$'\n")
            (repo.path / "VERSION").write_text("0.3.0\n", encoding="utf-8")

            result = self.script(RELEASE, scratch, repo, "check")

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["version"], "0.3.0")


FINISH_SH = ROOT / "skills" / "specwright-finish" / "scripts" / "finish.sh"


class TestGitButlerFinishGuards(GitButlerRangeCase):
    def plan(self, scratch, repo, *extra, expected=0):
        return self.script(FINISH_SH, scratch, repo, "undo-archive-plan", "--change", CHANGE, "--archived-name",
                           "2026-10-30-" + CHANGE, "--prefix", "openspec", "--main", "main", *extra, expected=expected)

    def test_finish_head_guards_resolve_the_branch(self):
        require_but()
        with Scratch() as scratch:
            repo = self.pair(scratch)
            change = repo.path / "openspec" / "changes" / CHANGE
            change.mkdir(parents=True)
            (change / "proposal.md").write_text("# proposal\n", encoding="utf-8")
            repo.but("commit", "-b", BRANCH, "-m", "docs(%s): plan" % CHANGE, "--json", "openspec/changes/%s/" % CHANGE)
            archive = repo.path / "openspec" / "changes" / "archive" / ("2026-10-30-" + CHANGE)
            archive.parent.mkdir(parents=True)
            change.rename(archive)
            (archive / "review.md").write_text("VERDICT: DEFERRED\n", encoding="utf-8")
            repo.but("commit", "-b", BRANCH, "-m", "docs(%s): archive change" % CHANGE, "--json",
                     "openspec/changes/archive/2026-10-30-%s/" % CHANGE)  # a rename is listed once, at its new path
            tip = self.tip(repo, BRANCH)

            missing = self.plan(scratch, repo, expected=2)
            plan = self.plan(scratch, repo, "--branch", BRANCH)

            self.assertEqual(missing["error"], "usage")
            self.assertIn("--branch", missing["message"])
            self.assertTrue(plan["ok"], plan)
            self.assertIn("git rev-parse refs/heads/%s)\" = %s" % (BRANCH, tip), plan["script"])
            self.assertNotIn("git rev-parse HEAD", plan["script"], "no guard reads the workspace commit")
