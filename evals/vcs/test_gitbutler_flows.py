"""Whole GitButler flows make no Git write beyond the change branch's push, and the PR pair routes the code repo through vcs.sh.

Real `but` workspaces with `feat/b` applied beside the change branch `feat/add-c` throughout. A logging `git` shim sits first on
the PATH of every bash script Specwright runs here (vcs.sh, review-run.sh, pr-pair.sh and the commands cleanup-plan emits), so the
log holds every `git` call those scripts make through bash. pr-pair.sh's own Python calls Git by name, so the shim sees them where
the platform lets a script named `git` run (Linux, not Windows); the assertions hold either way.
"""
import json
import subprocess
import sys
from pathlib import Path

import jjenv
from butenv import Scratch, require_but
from gbnet import LOGIN, GitButlerNetworkCase

ROOT = Path(__file__).resolve().parents[2]
PR_PAIR = ROOT / "skills" / "specwright-pr" / "scripts" / "pr-pair.sh"
REVIEW = ROOT / "skills" / "specwright-review" / "scripts" / "review-run.sh"
CHANGE = "add-c"
BRANCH = "feat/add-c"
CODE, STORE = "o/r", "o/plans"
SETTINGS = "vcs: gitbutler\nfinish: pr\ngithub:\n  login: %s\n" % LOGIN
CLEAN = {"summary": "nothing to report", "findings": []}
PUSH = ["push", "--no-follow-tags", "origin", "refs/heads/%s:refs/heads/%s" % (BRANCH, BRANCH)]
# spec: "No other Git write runs under GitButler" - the verbs the code repo's log must not hold
FORBIDDEN = {"checkout", "switch", "add", "rm", "restore", "read-tree", "commit", "merge", "stash", "reset", "rebase", "pull",
             "update-ref", "tag", "clean", "cherry-pick", "am", "apply", "mv"}
T0 = "2026-10-08T10:00:00Z"
REV0 = "11@" + T0


class GitButlerFlowCase(GitButlerNetworkCase):
    def start(self, scratch, settings=SETTINGS):
        """A managed repo with the Specwright settings, the fake gh tokens and the Git-call log shim."""
        wrap = self.prepare(scratch)
        repo = self.managed(scratch)
        self.repo_path = repo.path
        self.settings(repo.path, settings)
        return wrap, repo

    def other_agent(self, repo, wrap):
        """feat/b: one commit and an uncommitted edit that GitButler assigns to it."""
        repo.but("branch", "new", "feat/b")
        self.commit_on(repo, "feat/b", "b-committed.txt")
        (repo.path / "src").mkdir(exist_ok=True)
        (repo.path / "src" / "b.py").write_text("print('b')\n", encoding="utf-8")
        wrap.set_assignments({"feat/b": ["src/b.py"]})

    def run_argv(self, scratch, wrap, argv, cwd, expected=0):
        """Run `bash <script> <args>` (argv[0] is "bash") with the Git shim, the logging `but` and the fake gh on PATH; one JSON line out."""
        self.assertEqual(argv[0], "bash", argv)
        env = self.fenced_env(scratch, wrap)
        env.update({"SPECWRIGHT_STATE_DIR": str(self.root / "state"), "PYTHONIOENCODING": "utf-8"})
        env["VCS_TEST_SEARCH"] = env["PATH"]
        done = subprocess.run([jjenv.find_bash(), "-c", 'export PATH="$VCS_TEST_SEARCH"; exec "$BASH" "$@"', "flow",
                               *map(str, argv[1:])], cwd=str(cwd), env=env, capture_output=True, text=True, encoding="utf-8")
        lines = done.stdout.strip().splitlines()
        self.assertEqual(done.returncode, expected, "%s\nstdout: %s\nstderr: %s" % (argv, done.stdout, done.stderr))
        self.assertEqual(len(lines), 1, "want one JSON line from %s, got %r / %r" % (argv, done.stdout, done.stderr))
        return json.loads(lines[0])

    def script(self, scratch, wrap, script, *args, cwd=None, expected=0):
        return self.run_argv(scratch, wrap, ["bash", Path(script).as_posix(), *args], cwd or self.repo_path, expected)  # bare-bash: not started

    def message(self, text):
        path = self.root / "message.txt"
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        return path

    def commit(self, scratch, wrap, text, *paths):
        return self.vcs(scratch, wrap, "commit", "--branch", BRANCH, "--message-file", self.message(text), "--", *paths)

    def seed_gh(self, scratch, repos):
        state = json.loads(scratch.gh_state.read_text(encoding="utf-8"))
        state.setdefault("repos", {}).update(repos)
        scratch.gh_state.write_text(json.dumps(state), encoding="utf-8")

    def gh_state(self, scratch):
        return json.loads(scratch.gh_state.read_text(encoding="utf-8"))

    def gh_calls(self, scratch, *argv):
        path = scratch.gh_log
        calls = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
        return [call for call in calls if call["argv"][:len(argv)] == list(argv)]

    def git_writes(self):
        """Every logged Git write. `worktree list` only reads, though the shim files every `worktree` call under writes."""
        return [call["argv"] for call in self.shim.calls()
                if call["write"] and not (call["action"] == "worktree" and "list" in call["argv"])]

    def assert_only_allowed_git_writes(self, allowed):
        writes = self.git_writes()
        self.assertTrue(self.shim.calls(), "the git shim logged nothing: the test does not see Specwright's calls")
        self.assertEqual([w for w in writes if w not in allowed], [], "a Git write other than the allowed ones")
        for call in self.shim.calls():
            self.assertNotIn(call["action"], FORBIDDEN, call["argv"])
            if call["action"] == "branch":
                self.assertFalse({"-d", "-D", "--delete", "-m", "-M", "-c", "-C", "-f"} & set(call["argv"]), call["argv"])
            if call["action"] == "fetch":
                self.assertIn("--refmap=", call["argv"], "a fetch without an empty refmap writes remote-tracking refs")

    def uncommitted(self, repo):
        return sorted(c["filePath"] for c in json.loads(repo.but("status", "--json").stdout)["uncommittedChanges"])


class TestGitButlerFullFlow(GitButlerFlowCase):
    def test_full_pr_flow_git_write_boundary(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            self.other_agent(repo, wrap)
            self.github_view()
            self.seed_gh(scratch, {CODE: {"pulls": [], "default_branch": "main"}})
            tip_b = self.tip(repo, "feat/b")
            login = ("--login", LOGIN)

            # branch gate: the change branch joins the workspace beside feat/b
            state = self.vcs(scratch, wrap, "state", "--branch", BRANCH)
            self.assertEqual((state["applied"], state["on_main"]), (False, True), state)
            self.vcs(scratch, wrap, "fetch-main", "--quiet", *login)
            created = self.vcs(scratch, wrap, "branch-create", "--branch", BRANCH)
            self.assertTrue(created["applied"], created)

            # apply: two task groups, one commit each, naming their paths
            change = repo.path / "openspec" / "changes" / CHANGE
            change.mkdir(parents=True)
            (change / "proposal.md").write_text("proposal\n", encoding="utf-8")
            (repo.path / "src" / "one.txt").write_text("group one\n", encoding="utf-8")
            self.commit(scratch, wrap, "feat(add-c): group 1\n\nSpecwright-Task: 1.1\n", "src/one.txt",
                        "openspec/changes/%s/" % CHANGE)
            (repo.path / "src" / "two.txt").write_text("group two\n", encoding="utf-8")
            self.commit(scratch, wrap, "feat(add-c): group 2\n\nSpecwright-Task: 2.1\n", "src/two.txt")
            state = self.vcs(scratch, wrap, "state", "--branch", BRANCH)
            self.assertTrue(state["clean"], state)
            self.assertEqual([item["path"] for item in state["other_branch_paths"]], ["src/b.py"])

            # pre-ship review of the branch tip, then the gate
            preflight = self.script(scratch, wrap, REVIEW, "preflight", "--kind", "preship", "--change", CHANGE, "--base", "main",
                                    "--branch", BRANCH)
            (self.root / "preflight.json").write_text(json.dumps(preflight), encoding="utf-8")
            (self.root / "findings.json").write_text(json.dumps(CLEAN), encoding="utf-8")
            recorded = self.script(scratch, wrap, REVIEW, "record", "--kind", "preship", "--change", CHANGE, "--result",
                                   self.root / "findings.json", "--route", "subagent", "--preflight", self.root / "preflight.json",
                                   "--branch", BRANCH)
            self.assertEqual(recorded["status"], "ok", recorded)
            gate = self.script(scratch, wrap, REVIEW, "gate", "--change", CHANGE, "--branch", BRANCH)
            self.assertEqual(gate["status"], "pass", gate)

            # ship: the fenced push of the branch alone, then one PR for that head
            self.vcs(scratch, wrap, "push", "--branch", BRANCH, *login)
            body = self.root / "body.md"
            body.write_text("body\n", encoding="utf-8")
            ensure = ("ensure-pr", "--repo", CODE, "--branch", BRANCH, "--base", "main", "--title", "add c", "--body-file", body)
            self.assertEqual(self.script(scratch, wrap, PR_PAIR, *ensure)["action"], "created")
            self.assertEqual(self.script(scratch, wrap, PR_PAIR, *ensure)["action"], "found")

            # archive on the change branch, pushed again
            archived = "openspec/changes/archive/2026-10-30-" + CHANGE
            (repo.path / archived).parent.mkdir(parents=True, exist_ok=True)
            change.rename(repo.path / archived)
            self.commit(scratch, wrap, "chore(add-c): archive add-c\n\nSpecwright-Change: add-c\n", "openspec/changes/%s/" % CHANGE,
                        archived + "/")  # a deleted directory is named with its trailing slash
            tip = self.tip(repo, BRANCH)
            self.vcs(scratch, wrap, "push", "--branch", BRANCH, *login)
            self.assertEqual(self.origin_refs(scratch), {"refs/heads/main": self.origin_refs(scratch)["refs/heads/main"],
                                                         "refs/heads/" + BRANCH: tip}, "only the change branch is published")

            # the PR merges on GitHub; cleanup: refresh, switch, pull (skipped: feat/b), the proof, the delete
            merged = self.merge_on_origin(scratch, BRANCH)
            fetched = self.vcs(scratch, wrap, "fetch-main", "--quiet", *login)
            self.assertEqual(fetched["commit"], merged)
            self.assertFalse(self.vcs(scratch, wrap, "switch", "--branch", "main")["switched"])
            pulled = self.vcs(scratch, wrap, "pull", "--branch", BRANCH, *login)
            self.assertEqual((pulled["pulled"], pulled["reason"], pulled["applied_branches"]), (False, "pull_skipped", ["feat/b"]))
            check = self.script(scratch, wrap, PR_PAIR, "branch-check", "--dir", repo.path, "--branch", BRANCH, "--main",
                                fetched["commit"], "--head", tip)
            self.assertEqual((check["ok"], check["delete"]), (True, True), check)
            deleted = self.vcs(scratch, wrap, "delete-branch", "--branch", BRANCH, "--force", "--merged-commit", merged, *login)
            self.assertEqual((deleted["deleted"], deleted["reason"]), (False, "left_applied"), deleted)

            # the other agent's work is untouched; one PR; no Git write but the push
            self.assertEqual(self.tip(repo, "feat/b"), tip_b)
            self.assertEqual(self.applied(repo), ["feat/add-c", "feat/b"])
            self.assertEqual((repo.path / "src" / "b.py").read_text(encoding="utf-8"), "print('b')\n")
            self.assertEqual(self.uncommitted(repo), ["src/b.py"])
            pulls = self.gh_state(scratch)["repos"][CODE]["pulls"]
            self.assertEqual([p["head"]["ref"] for p in pulls], [BRANCH])
            self.assertEqual(len(self.gh_calls(scratch, "pr", "create")), 1, "exactly one PR was opened")
            self.assert_only_allowed_git_writes([PUSH])
            self.assertEqual(self.git_writes(), [PUSH, PUSH])


class TestGitButlerCleanupPlan(GitButlerFlowCase):
    def test_cleanup_plan_routes_code_repo_through_vcs(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.start(scratch)
            repo.but("branch", "new", "feat/b")
            self.commit_on(repo, "feat/b", "b-committed.txt")
            repo.but("branch", "new", BRANCH)
            self.commit_on(repo, BRANCH, "c.txt")
            self.git(repo.path, "push", "-q", "origin", "refs/heads/%s:refs/heads/%s" % (BRANCH, BRANCH))
            merged = self.merge_on_origin(scratch, BRANCH)
            tip, tip_b = self.tip(repo, BRANCH), self.tip(repo, "feat/b")
            # a Git store beside it, on the same branch
            store = self.root / "store"
            self._init_git(store)
            self.git(store, "checkout", "-q", "-b", BRANCH)
            (store / "plan.md").write_text("plan\n", encoding="utf-8")
            self.git(store, "add", "plan.md")
            self.git(store, "commit", "-q", "-m", "docs(add-c): plan")
            self.git(store, "remote", "add", "origin", "https://github.com/%s.git" % STORE)
            # cleanup-plan reads each origin as a GitHub URL; the commands it prints run against the local bare origin
            self.git(repo.path, "remote", "set-url", "origin", "https://github.com/%s.git" % CODE)
            pull = lambda slug, n, sha: {"number": n, "html_url": "https://github.com/%s/pull/%d" % (slug, n), "state": "closed",
                                         "merged_at": "2026-10-30T10:00:00Z", "title": "t", "body": "", "created_at": T0,
                                         "merge_commit_sha": sha, "head": {"ref": BRANCH, "label": "o:" + BRANCH, "sha": tip,
                                         "repo": {"full_name": slug}}, "base": {"ref": "main"}}
            self.seed_gh(scratch, {CODE: {"pulls": [pull(CODE, 5, merged)]}, STORE: {"pulls": [pull(STORE, 2, "c" * 40)]}})

            plan = self.script(scratch, wrap, PR_PAIR, "cleanup-plan", "--code", repo.path, "--store", store, "--branch", BRANCH,
                               cwd=self.root)

            code, kept = plan["code"], plan["store"]
            self.assertEqual(plan["keep"], [])
            self.assertTrue(code["merged"] and code["branch_exists"], code)
            argvs = [c["cmd"] for c in code["commands"]] + [code["delete"]]
            self.assertFalse([argv for argv in argvs if "git" in argv or argv[0] == "git" or "as.sh" in argv[1].lower()],
                             "a Git command in the GitButler code repo's plan: %s" % argvs)
            subs = [argv[2] if argv[0] == "bash" and argv[1].lower().endswith("vcs.sh") else argv[1] for argv in argvs]
            self.assertEqual(subs, ["switch", "pull", "branch-check", "delete-branch"], argvs)

            def option(argv, name):
                return argv[argv.index(name) + 1]
            pull_argv = argvs[1]
            self.assertEqual((option(pull_argv, "--role"), option(pull_argv, "--branch"), option(pull_argv, "--login")),
                             ("code", BRANCH, LOGIN), "the pull names the branch being cleaned up")
            self.assertEqual(option(argvs[3], "--branch"), BRANCH)
            self.assertIn("--force", argvs[3])
            self.assertEqual(option(argvs[3], "--merged-commit"), merged, "the PR's merge_commit_sha is the squash proof")
            # the store keeps its Git commands
            self.assertEqual([c["cmd"][:2] for c in kept["commands"]][0], ["git", "checkout"])
            self.assertEqual(kept["delete"], ["git", "branch", "-D", BRANCH])

            # run the code repo's commands for real: nothing in the log but reads
            self.git(repo.path, "remote", "set-url", "origin", str(scratch.origin))
            self.github_view()
            self.shim.log_path.unlink(missing_ok=True)
            results = []
            for argv in argvs:
                run = ["bash", PR_PAIR.as_posix(), *argv[1:]] if argv[0] == "pr-pair.sh" else argv  # bare-bash: not started
                results.append(self.run_argv(scratch, wrap, run, repo.path))
            switched, pulled, checked, deleted = results
            self.assertFalse(switched["switched"])
            self.assertEqual((pulled["pulled"], pulled["reason"], pulled["applied_branches"]), (False, "pull_skipped", ["feat/b"]))
            self.assertEqual((checked["delete"], checked["reason"]), (True, "on_main"), checked)
            self.assertEqual((deleted["deleted"], deleted["reason"]), (False, "left_applied"), deleted)
            self.assertEqual(self.applied(repo), ["feat/add-c", "feat/b"])
            self.assertEqual((self.tip(repo, BRANCH), self.tip(repo, "feat/b")), (tip, tip_b))
            self.assert_only_allowed_git_writes([])
            self.assertEqual(self.git_writes(), [])
            self.assertEqual(wrap.writes(), [], "no but write ran: the pull was skipped and the delete left the branch applied")


class TestGitButlerCleanupLoneBranch(GitButlerFlowCase):
    def test_cleanup_after_pull_removes_lone_branch(self):
        require_but()
        with Scratch() as scratch:
            wrap = self.prepare(scratch)
            repo = self.workspace(scratch, [BRANCH])
            self.settings(repo.path, SETTINGS)
            self.github_view()
            origin_before = self.origin_refs(scratch)
            merged = self.real_squash(scratch, {"add-c.txt": "add-c.txt\n"})  # the branch's own content
            login = ("--login", LOGIN)
            fetched = self.vcs(scratch, wrap, "fetch-main", "--quiet", *login)
            self.assertEqual(fetched["commit"], merged)
            head_sha = self.tip(repo, BRANCH)  # the merged PR's head
            self.shim.log_path.unlink(missing_ok=True)

            self.assertFalse(self.vcs(scratch, wrap, "switch", "--branch", "main")["switched"])
            pulled = self.vcs(scratch, wrap, "pull", "--branch", BRANCH, *login)
            self.assertTrue(pulled["pulled"], pulled)
            self.assertEqual(self.applied(repo), [], "the integrated branch left the workspace")
            # `but pull` fetches with the system git (D7); the shim sees that child on Linux, not on Windows
            self.assertEqual([w for w in self.git_writes() if "fetch" not in w], [], "the pull wrote more than a fetch")
            self.shim.log_path.unlink(missing_ok=True)
            # the repo-local call the pr and finish skills document, then the store-backed cleanup-plan form
            for extra in (("--head", head_sha), ("--code", repo.path, "--role", "code", *login)):
                check = self.script(scratch, wrap, PR_PAIR, "branch-check", "--dir", repo.path, "--branch", BRANCH,
                                    "--main", fetched["commit"], *extra)
                self.assertEqual((check["ok"], check["delete"], check["reason"], check["lacking"]),
                                 (True, True, "already_deleted", []), check)
            deleted = self.vcs(scratch, wrap, "delete-branch", "--branch", BRANCH, "--force", "--merged-commit", merged, *login)
            self.assertEqual((deleted["ok"], deleted["deleted"], deleted["reason"]), (True, False, "already_deleted"), deleted)

            self.assertEqual(self.git_writes(), [])
            self.assertEqual({k: v for k, v in self.origin_refs(scratch).items() if k != "refs/heads/main"},
                             {k: v for k, v in origin_before.items() if k != "refs/heads/main"})
            self.assertEqual(self.origin_refs(scratch)["refs/heads/main"], merged)


class TestGitButlerFeedbackPass(GitButlerFlowCase):
    def snapshot(self):
        snap = {"viewer": "KintsugiBot", "number": 5, "url": "https://github.com/%s/pull/5" % CODE, "state": "OPEN", "draft": False,
                "mergeable": "MERGEABLE", "merge_state": "CLEAN", "pending_review": False,
                "checks": {"total": 3, "pending": 0, "advisory_pending": 0, "failing": []},
                "threads": [{"id": "T1", "root_id": 11, "resolved": False, "rev": REV0, "waiting_owner": False,
                             "awaiting_reviewer": False, "resolve_pending": False, "path": "x", "line": 1,
                             "comments": [{"id": "C11", "author": "chatgpt-codex-connector", "at": T0, "edited": None}]}],
                "comments": [], "reviews": [], "stale_verdicts": [], "reviewers": [], "complete": True, "truncated": []}
        path = self.root / "snapshot.json"
        path.write_text(json.dumps(snap), encoding="utf-8")
        return path

    def intent(self):
        finding = {"id": "F1", "source": "code", "destination": "code", "kind": "thread", "item": "T1", "root_id": 11,
                   "edits": [{"file": "src/fix.py", "contains": ["strip()"]}],
                   "disposition": {"reply": True, "resolve": True, "react": None},
                   "revision": {"rev": REV0, "last_reviewer_comment": {"id": "C11", "at": T0}}}
        path = self.root / "intent.json"
        path.write_text(json.dumps({"change": CHANGE, "branch": BRANCH, "round": 2, "code_repo": CODE,
                                    "prs": {"code": {"repo": CODE, "number": 5}, "store": None}, "findings": [finding]}),
                        encoding="utf-8")
        return path

    def pass_args(self, repo):
        return ["--code", repo.path, "--code-repo", CODE, "--change", CHANGE]

    def pass_plan(self, scratch, wrap, repo, owner):
        return self.script(scratch, wrap, PR_PAIR, "pass", "plan", *self.pass_args(repo), "--owner", owner, "--snapshot",
                           "code=%s" % self.snapshot(), cwd=self.root)

    def begin(self, scratch):
        """feat/b and the change branch applied; src/b.py assigned to feat/b; notes.txt unassigned and modified before the pass."""
        wrap, repo = self.start(scratch)
        self.other_agent(repo, wrap)
        repo.but("branch", "new", BRANCH)
        self.commit_on(repo, BRANCH, "c.txt")
        (repo.path / "notes.txt").write_text("my notes\n", encoding="utf-8")
        self.git(repo.path, "push", "-q", "origin", "refs/heads/%s:refs/heads/%s" % (BRANCH, BRANCH))
        return wrap, repo

    def record(self):
        found = sorted((self.root / "state" / "feedback").glob("*.json"))
        self.assertEqual(len(found), 1, found)
        return json.loads(found[0].read_text(encoding="utf-8"))

    def test_feedback_pass_ignores_other_and_preexisting_paths(self):
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.begin(scratch)
            written = self.script(scratch, wrap, PR_PAIR, "pass", "write", *self.pass_args(repo), "--intent", self.intent(),
                                  cwd=self.root)
            owner = written["owner"]
            self.assertEqual(self.record()["preexisting"], ["notes.txt"], "the unassigned path present at the start is recorded")

            # the pass makes its recorded edit, uncommitted
            (repo.path / "src" / "fix.py").write_text("def f(x):\n    return x.strip()\n", encoding="utf-8")
            plan = self.pass_plan(scratch, wrap, repo, owner)
            self.assertEqual(plan["stops"], [], "neither feat/b's src/b.py nor the old notes.txt is an unrecorded change")
            fix = [r for r in plan["rows"] if r["step"] == "fix_commit"][0]
            self.assertEqual((fix["files"], fix["state"], fix["action"], fix["committable"]),
                             (["src/fix.py"], "todo", "validate_and_commit", True), fix)

            # the pass commits only its recorded file
            done = self.commit(scratch, wrap, "fix(add-c): address review feedback\n\nFeedback-Round: 2\n", "src/fix.py")
            self.assertEqual(self.git(repo.path, "show", "--name-only", "--format=", done["commit"]).stdout.split(), ["src/fix.py"])
            plan = self.pass_plan(scratch, wrap, repo, owner)
            self.assertEqual(plan["stops"], [])
            fix = [r for r in plan["rows"] if r["step"] == "fix_commit"][0]
            self.assertEqual((fix["state"], fix["sha"]), ("done", done["commit"]), fix)
            self.assertEqual(self.uncommitted(repo), ["notes.txt", "src/b.py"], "the others' edits are still uncommitted")

            # an unassigned path that appears during the pass is asked about, and only that one
            (repo.path / "extra.txt").write_text("new\n", encoding="utf-8")
            plan = self.pass_plan(scratch, wrap, repo, owner)
            self.assertEqual([(s["reason"], s["files"]) for s in plan["stops"]], [("unrecorded_change", ["extra.txt"])])

    def test_other_branch_edit_is_no_fix_evidence(self):
        """The recorded file holds the fix only in feat/b's assigned edit: the change branch still has the bug, so a partial
        round commit does not make the fix row done."""
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.begin(scratch)
            (repo.path / "src" / "fix.py").write_text("def f(x):\n    return x  # broken\n", encoding="utf-8")
            self.commit(scratch, wrap, "feat(add-c): f\n", "src/fix.py")
            owner = self.script(scratch, wrap, PR_PAIR, "pass", "write", *self.pass_args(repo), "--intent", self.intent(),
                                cwd=self.root)["owner"]
            (repo.path / "src" / "fix.py").write_text("def f(x):\n    return x.strip()\n", encoding="utf-8")
            wrap.set_assignments({"feat/b": ["src/b.py", "src/fix.py"]})
            (repo.path / "c2.txt").write_text("part\n", encoding="utf-8")
            partial = self.commit(scratch, wrap, "fix(add-c): address review feedback\n\nFeedback-Round: 2\n", "c2.txt")["commit"]

            plan = self.pass_plan(scratch, wrap, repo, owner)

            fix = [r for r in plan["rows"] if r["step"] == "fix_commit"][0]
            self.assertEqual((fix["state"], fix.get("partial_commit")), ("todo", partial), fix)
            self.assertEqual(fix["pending_edits"], [{"file": "src/fix.py", "finding": "F1", "reason": "not_made"}], fix)
            replies = [r for r in plan["rows"] if r["step"] == "reply"]
            self.assertTrue(replies and all(r["state"] != "todo" or r.get("blocked") for r in replies), replies)

    def test_pass_plan_remote_contains_fetch_writes_no_tracking_ref(self):
        """The pass plan's push check fetches an unknown remote tip into FETCH_HEAD only: a Git ref write is outside the workspace."""
        require_but()
        with Scratch() as scratch:
            wrap, repo = self.begin(scratch)
            owner = self.script(scratch, wrap, PR_PAIR, "pass", "write", *self.pass_args(repo), "--intent", self.intent(),
                                cwd=self.root)["owner"]
            (repo.path / "src" / "fix.py").write_text("def f(x):\n    return x.strip()\n", encoding="utf-8")
            fix = self.commit(scratch, wrap, "fix(add-c): address review feedback\n\nFeedback-Round: 2\n", "src/fix.py")["commit"]
            self.git(repo.path, "push", "-q", "origin", "refs/heads/%s:refs/heads/%s" % (BRANCH, BRANCH))
            side = self.clone_of_origin(scratch)  # another checkout pushes a commit on top of the fix
            self.side_git(side, "fetch", "-q", "origin", BRANCH)
            self.side_git(side, "checkout", "-q", "-B", BRANCH, "FETCH_HEAD")
            (side / "other.txt").write_text("other\n", encoding="utf-8")
            self.side_git(side, "add", "other.txt")
            self.side_git(side, "commit", "-q", "-m", "other")
            self.side_git(side, "push", "-q", "origin", "HEAD:refs/heads/" + BRANCH)
            remote_tip = self.side_git(side, "rev-parse", "HEAD")
            tracking = "refs/remotes/origin/" + BRANCH
            self.assertEqual(self.git(repo.path, "rev-parse", tracking).stdout.strip(), fix)

            plan = self.pass_plan(scratch, wrap, repo, owner)

            push = [r for r in plan["rows"] if r["step"] == "push"][0]
            self.assertEqual(push["state"], "done", push)
            self.assertEqual(self.git(repo.path, "rev-parse", tracking).stdout.strip(), fix, "no remote-tracking ref moved")
            head = (repo.path / ".git" / "FETCH_HEAD").read_text(encoding="utf-8")
            self.assertIn(remote_tip, head, "the unknown tip was fetched into FETCH_HEAD")
            self.assertEqual(self.git(repo.path, "cat-file", "-t", remote_tip).stdout.strip(), "commit")


if __name__ == "__main__":
    sys.exit(__import__("unittest").main())
