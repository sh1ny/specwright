"""skills/specwright-commit/scripts/task-cover.sh reports which tasks of tasks.md commits cover.

Each test builds a scratch git repo with a tasks.md and commits whose subjects and `Specwright-Task`
trailers are the evidence; the script reads them read-only and prints one JSON document. Exit 0
answered, 1 range_too_large, 2 usage or tasks_too_large, 3 git failure.

Run: python -m unittest discover evals/git-workflow -p "test_task_cover.py"
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "evals") not in sys.path:
    sys.path.append(str(ROOT / "evals"))
import bashexe  # noqa: E402
SCRIPT = ROOT / "skills" / "specwright-commit" / "scripts" / "task-cover.sh"
CHANGE = "add-greeting"

TASKS = """# Tasks

## 1. Greeting

- [x] 1.1 Write greet
- [x] 1.2 Test greet
- [ ] 1.10 Tenth thing

## 2. Farewell

- [x] 2.1 Write bye
- [x] 2.2 Test bye
"""


class TaskCover(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "T")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "commit.gpgsign", "false")
        self.n = 0
        self.commit("chore: base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args, input=None):
        r = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, input=input)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.decode("utf-8")

    def commit(self, subject, *trailers):
        self.n += 1
        (self.repo / ("f%d.txt" % self.n)).write_text(str(self.n))
        self.git("add", "-A")
        msg = subject + "\n\nBody.\n"
        if trailers:
            msg += "\n" + "\n".join("Specwright-Task: " + t for t in trailers) + "\n"
        msgfile = self.tmp / "msg.txt"
        msgfile.write_bytes(msg.encode("utf-8"))
        self.git("commit", "-q", "-F", str(msgfile))
        return self.git("rev-parse", "HEAD").strip()

    def tasks_file(self, text=TASKS):
        p = self.tmp / "tasks.md"
        p.write_bytes(text.encode("utf-8"))
        return p

    def run_script(self, tasks=None, env=None, change=CHANGE, rev=None, repo=None, base=None):
        tasks = tasks or self.tasks_file()
        e = dict(os.environ, **(env or {}))
        extra = ["--rev", rev] if rev else []
        return subprocess.run(
            [bashexe.bash(), str(SCRIPT), "--repo", str(repo or self.repo), "--range", (base or self.base) + "..HEAD",
             "--tasks", str(tasks), "--change", change, *extra],
            capture_output=True, env=e)

    def user_commit(self, subject, task_trailers=(), user_trailers=()):
        """Like commit(), with Specwright-Task and Specwright-User-Task trailers in one block."""
        self.n += 1
        (self.repo / ("f%d.txt" % self.n)).write_text(str(self.n))
        self.git("add", "-A")
        lines = ["Specwright-Task: " + t for t in task_trailers] + \
                ["Specwright-User-Task: " + t for t in user_trailers]
        msg = subject + "\n\nBody.\n" + ("\n" + "\n".join(lines) + "\n" if lines else "")
        msgfile = self.tmp / "msg.txt"
        msgfile.write_bytes(msg.encode("utf-8"))
        self.git("commit", "-q", "-F", str(msgfile))
        return self.git("rev-parse", "HEAD").strip()

    def repo_tasks(self, text, archived=False):
        """Write tasks.md inside the repo, in the active or archived change folder; returns its path."""
        folder = Path("openspec") / "changes" / ("archive/2026-01-01-" + CHANGE if archived else CHANGE)
        p = self.repo / folder / "tasks.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
        return p

    def write_evidence(self, name="run.log", text="output\n", base=None):
        p = (base or self.tmp) / "evidence" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def cover(self, **kw):
        r = self.run_script(**kw)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return json.loads(r.stdout.decode("utf-8"))

    @staticmethod
    def task(doc, tid):
        return next(t for t in doc["tasks"] if t["id"] == tid)

    def test_group_ten_is_not_group_one(self):
        text = "## 1. One\n\n- [x] 1.1 a\n- [x] 1.2 b\n\n## 10. Ten\n\n- [x] 10.1 c\n"
        sha = self.commit("feat(%s): group 1 One" % CHANGE, "1.1", "1.2")
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual([self.task(doc, i)["group"] for i in ("1.1", "1.2", "10.1")], [1, 1, 10])
        self.assertEqual(self.task(doc, "10.1")["commits"], [])
        self.assertEqual(doc["cross_group"], [])
        self.assertEqual(doc["pending_groups"], [{"group": 10, "tasks": ["10.1"]}])
        self.assertEqual(self.task(doc, "1.1")["commits"], [{"sha": sha, "form": "trailer"}])

    def test_group_without_heading_is_reported(self):
        text = "## 1. One\n\n- [x] 1.1 a\n\n## Cleanup\n\n- [ ] 3.1 x\n- [ ] 3.2 y\n"
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual(doc["missing_headings"], [3])
        self.assertEqual({g["group"]: g["heading"] for g in doc["groups"]}, {1: "One", 3: None})

    def test_trailer_match_is_exact(self):
        sha = self.commit("feat(%s): group 1 Greeting" % CHANGE, "1.10")
        text = "## 1. G\n\n- [x] 1.1 a\n- [x] 1.10 b\n"
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual(self.task(doc, "1.10")["commits"], [{"sha": sha, "form": "trailer"}])
        self.assertEqual(self.task(doc, "1.1")["commits"], [])
        self.assertEqual(doc["uncovered"], ["1.1"])

    def test_task_id_inside_text_is_not_evidence(self):
        self.commit("fix(%s): group 2 Fix task 1.1 regressions" % CHANGE)
        self.commit("fix(%s): task 2.1 Revert task 1.1 output" % CHANGE)
        doc = self.cover()
        self.assertEqual(self.task(doc, "1.1")["commits"], [])
        self.assertEqual(len(self.task(doc, "2.1")["commits"]), 1)
        self.assertEqual(self.task(doc, "2.1")["commits"][0]["form"], "subject")
        self.assertIn("1.1", doc["uncovered"])

    def test_task_covered_twice_names_both(self):
        a = self.commit("feat(%s): task 1.2 Test greet" % CHANGE)
        b = self.commit("feat(%s): group 1 Greeting" % CHANGE, "1.2", "1.10")
        doc = self.cover()
        self.assertEqual(len(doc["duplicates"]), 1)
        self.assertEqual(doc["duplicates"][0]["task"], "1.2")
        self.assertEqual(sorted(doc["duplicates"][0]["commits"]), sorted([a, b]))

    def test_cross_group_trailer_reported(self):
        sha = self.commit("feat(%s): group 1 Greeting" % CHANGE, "1.1", "2.1")
        doc = self.cover()
        self.assertEqual(doc["cross_group"], [{"sha": sha, "task": "2.1", "group": 1}])

    def test_pending_excludes_covered_tasks(self):
        text = "## 1. G\n\n- [x] 1.1 a\n- [x] 1.2 b\n- [x] 1.3 c\n"
        self.commit("feat(%s): task 1.1 a" % CHANGE)
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual(doc["pending_groups"], [{"group": 1, "tasks": ["1.2", "1.3"]}])
        self.assertEqual(doc["uncovered"], ["1.2", "1.3"])

    def test_two_pending_groups_reported(self):
        doc = self.cover()
        self.assertEqual(doc["pending_groups"],
                         [{"group": 1, "tasks": ["1.1", "1.2"]}, {"group": 2, "tasks": ["2.1", "2.2"]}])

    def test_uncovered_ticked_task_reported(self):
        self.commit("feat(%s): group 1 Greeting" % CHANGE, "1.1", "1.2")
        self.commit("feat(%s): task 2.1 Write bye" % CHANGE)
        doc = self.cover()
        self.assertEqual(doc["uncovered"], ["2.2"])
        self.assertFalse(self.task(doc, "1.10")["ticked"])

    def test_crlf_tasks_and_utf8_subject(self):
        text = "## 1. Grüße\r\n\r\n- [x] 1.1 café\r\n"
        self.commit("feat(%s): task 1.1 café ✓" % CHANGE)
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual(doc["groups"], [{"group": 1, "heading": "Grüße"}])
        self.assertEqual(doc["uncovered"], [])

    def test_spaced_checkbox_counts_as_ticked(self):
        # the apply schema: a box holding only x, with any spacing, is done; any other marker is not
        text = "## 1. G\n\n- [ x] 1.1 a\n- [X ] 1.2 b\n- [ ] 1.3 c\n- [~] 1.4 d\n- [] 1.5 e\n"
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual([(t["id"], t["ticked"]) for t in doc["tasks"]],
                         [("1.1", True), ("1.2", True), ("1.3", False), ("1.4", False), ("1.5", False)])
        self.assertEqual(doc["pending_groups"], [{"group": 1, "tasks": ["1.1", "1.2"]}])

    @unittest.skipUnless(shutil.which("ssh-keygen"), "needs ssh-keygen")
    def test_signed_commit_with_show_signature(self):
        key = self.tmp / "key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True,
                       capture_output=True)
        self.git("config", "gpg.format", "ssh")
        self.git("config", "user.signingkey", str(key))
        self.git("config", "commit.gpgsign", "true")
        sha = self.commit("feat(%s): group 1 Greeting" % CHANGE, "1.1", "1.2")
        self.git("config", "log.showSignature", "true")
        doc = self.cover()
        self.assertEqual(self.task(doc, "1.1")["commits"], [{"sha": sha, "form": "trailer"}])

    def test_tasks_too_large_exits_2(self):
        big = self.tasks_file("## 1. G\n\n- [x] 1.1 " + "x" * (1024 * 1024) + "\n")
        r = self.run_script(tasks=big)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(json.loads(r.stdout)["error"], "tasks_too_large")

    def test_range_too_large_exits_1(self):
        for i in range(3):
            self.commit("chore: filler %d" % i)
        r = self.run_script(env={"TASK_COVER_MAX_COMMITS": "2"})
        self.assertEqual(r.returncode, 1, r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual(doc["error"], "range_too_large")
        self.assertNotIn("tasks", doc)

    def test_repeated_task_id_exits_2(self):
        self.commit("feat(%s): task 1.1 add greet" % CHANGE)
        text = "## 1. G\n\n- [x] 1.1 add greet\n- [x] 1.2 b\n- [~] 1.1 draft\n"
        r = self.run_script(tasks=self.tasks_file(text))
        self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
        doc = json.loads(r.stdout)
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["error"], "duplicate_task_ids")
        self.assertIn("1.1", doc["message"])
        self.assertNotIn("uncovered", doc)
        self.assertNotIn("tasks", doc)

    def test_repeated_id_in_plain_bullet_is_not_a_task(self):
        sha = self.commit("feat(%s): task 1.1 add greet" % CHANGE)
        text = "## 1. G\n\n- [x] 1.1 add greet\n- 1.1 note: see above\n"
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual([t["id"] for t in doc["tasks"]], ["1.1"])
        self.assertEqual(self.task(doc, "1.1")["commits"], [{"sha": sha, "form": "subject"}])
        self.assertEqual(doc["uncovered"], [])

    KINDS = ("## 2. Mixed\n\n- [ ] 2.1 Add the parser\n- [ ] 2.2 [evidence] Save the run log → evidence/run.log\n"
             "- [ ] 2.3 [user] Play the first level\n")

    def test_task_kinds_reported(self):
        doc = self.cover(tasks=self.tasks_file(self.KINDS))
        self.assertEqual([(t["id"], t["kind"]) for t in doc["tasks"]],
                         [("2.1", "agent"), ("2.2", "evidence"), ("2.3", "user")])
        self.assertEqual(doc["waiting_on_user"], ["2.3"])

    def test_marker_elsewhere_or_other_case_is_agent(self):
        text = ("## 2. M\n\n- [ ] 2.4 Document the [user] marker\n- [ ] 2.5 [User] Check the menu\n"
                "- [ ] 2.6 [EVIDENCE] Capture\n- [ ] 2.7 [user]Check glued\n")
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual([t["kind"] for t in doc["tasks"]], ["agent"] * 4)
        self.assertEqual(doc["waiting_on_user"], [])

    def test_ticked_user_task_not_waiting(self):
        doc = self.cover(tasks=self.tasks_file("## 2. M\n\n- [x] 2.3 [user] Play the first level\n"))
        self.assertEqual(self.task(doc, "2.3")["kind"], "user")
        self.assertEqual(doc["waiting_on_user"], [])

    # Evidence is read from git's index (with --rev, the revision's tree), never through the working tree.
    def change_with_evidence(self, text, files=(), stage=True):
        """tasks.md in the fixture repo's change folder, with evidence files {name: text}; staged when `stage`."""
        p = self.repo_tasks(text)
        for name, body in dict(files).items():
            self.write_evidence(name, body, base=p.parent)
        self.git("add", "--", str(p))
        if stage and files:
            self.git("add", "--", str(p.parent / "evidence"))
        return p

    def stage_symlink(self, p, name, target):
        # a symlink index entry through plumbing: Git for Windows would stage a real link as a plain file
        blob = self.git("hash-object", "-w", "--stdin", input=target.encode()).strip()
        path = p.parent.relative_to(self.repo).as_posix() + "/evidence/" + name
        self.git("update-index", "--add", "--cacheinfo", "120000,%s,%s" % (blob, path))

    def symlink_or_skip(self, target, link):
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not available")

    def test_evidence_present_not_missing(self):
        # staged is enough: Reconcile reads coverage before the group commit records the file
        p = self.change_with_evidence("## 2. M\n\n- [x] 2.2 [evidence] Save the log → evidence/run.log\n",
                                      {"run.log": "output\n"})
        self.assertEqual(self.cover(tasks=p)["evidence_missing"], [])

    def test_evidence_committed_not_missing(self):
        p = self.change_with_evidence("## 2. M\n\n- [x] 2.2 [evidence] Save the log → evidence/run.log\n",
                                      {"run.log": "output\n"})
        self.git("commit", "-q", "-m", "chore: evidence")
        self.assertEqual(self.cover(tasks=p)["evidence_missing"], [])

    def test_evidence_untracked_is_missing(self):
        p = self.change_with_evidence("## 2. M\n\n- [x] 2.2 [evidence] Save the log → evidence/run.log\n",
                                      {"run.log": "output\n"}, stage=False)
        self.assertEqual(self.cover(tasks=p)["evidence_missing"], ["2.2"])

    def test_evidence_file_missing_reported(self):
        text = "## 2. M\n\n- [x] 2.2 [evidence] Save the log → evidence/run.log\n- [x] 2.3 [evidence] Save b → evidence/b.log\n"
        p = self.change_with_evidence(text, {"b.log": ""})  # staged but empty counts as missing
        self.assertEqual(self.cover(tasks=p)["evidence_missing"], ["2.2", "2.3"])

    def test_evidence_without_path_reported(self):
        text = "## 2. M\n\n- [x] 2.6 [evidence] Capture the frame times\n- [ ] 2.7 [evidence] Unticked, no path\n"
        self.assertEqual(self.cover(tasks=self.change_with_evidence(text))["evidence_missing"], ["2.6"])

    def test_evidence_path_trailing_punctuation_ignored(self):
        text = ("## 2. M\n\n- [x] 2.2 [evidence] Save → evidence/run.log.\n"
                "- [x] 2.3 [evidence] Save **evidence/run.log**\n- [x] 2.4 [evidence] Save to evidence/run.log: done\n")
        p = self.change_with_evidence(text, {"run.log": "output\n"})
        self.assertEqual(self.cover(tasks=p)["evidence_missing"], [])

    def test_store_backed_evidence_read_from_tasks_repo(self):
        # tasks.md and its evidence live in the store; the code-repo call reads them from the store, as the store does
        store = self.tmp / "store"
        store.mkdir()

        def sgit(*args):
            r = subprocess.run(["git", "-C", str(store), *args], capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout.decode("utf-8").strip()
        sgit("init", "-q", "-b", "main")
        sgit("config", "user.name", "T")
        sgit("config", "user.email", "t@example.com")
        sgit("config", "commit.gpgsign", "false")
        tasks = store / "openspec" / "changes" / CHANGE / "tasks.md"
        tasks.parent.mkdir(parents=True)
        tasks.write_bytes("## 2. M\n\n- [ ] 2.2 [evidence] Save → evidence/run.log\n".encode("utf-8"))
        sgit("add", "-A")
        sgit("commit", "-q", "-m", "chore: planning")
        store_base = sgit("rev-parse", "HEAD")
        # the group commit in each repo: the code half here, the store half with the tick and the evidence
        self.user_commit("feat(x): group 2 M", task_trailers=["2.2"])
        tasks.write_bytes("## 2. M\n\n- [x] 2.2 [evidence] Save → evidence/run.log\n".encode("utf-8"))
        self.write_evidence("run.log", "output\n", base=tasks.parent)
        sgit("add", "-A")
        sgit("commit", "-q", "-m", "feat(x): group 2 M\n\nSpecwright-Task: 2.2")

        def both():
            store_doc = self.json_ok(self.run_script(tasks=tasks, repo=store, base=store_base))
            code_doc = self.json_ok(self.run_script(tasks=tasks))  # --repo is the code repo
            return store_doc, code_doc

        for doc in both():  # completion holds in both repos: covered once, nothing missing
            self.assertEqual((doc["uncovered"], doc["duplicates"], doc["cross_group"], doc["evidence_missing"]),
                             ([], [], [], []))
        self.write_evidence("run.log", "", base=tasks.parent)
        sgit("add", "-A")
        sgit("commit", "-q", "-m", "chore: empty evidence")
        self.assertEqual([d["evidence_missing"] for d in both()], [["2.2"], ["2.2"]])
        sgit("rm", "-q", "-r", "openspec/changes/%s/evidence" % CHANGE)
        sgit("commit", "-q", "-m", "chore: evidence gone")
        self.assertEqual([d["evidence_missing"] for d in both()], [["2.2"], ["2.2"]])

    def test_evidence_path_with_backslash_rejected(self):
        # Windows reads `\` as a separator: the path is refused as written, whatever the index holds
        p = self.change_with_evidence("## 2. M\n\n- [x] 2.2 [evidence] Save → evidence/sub\\x.log\n",
                                      {"sub/x.log": "output\n"})
        self.assertEqual(self.cover(tasks=p)["evidence_missing"], ["2.2"])

    def test_evidence_path_with_drive_colon_rejected(self):
        p = self.change_with_evidence("## 2. M\n\n- [x] 2.2 [evidence] Save → evidence/C:x.log\n")
        self.assertEqual(self.cover(tasks=p)["evidence_missing"], ["2.2"])

    def test_evidence_staged_symlink_is_missing(self):
        p = self.change_with_evidence("## 2. M\n\n- [x] 2.2 [evidence] Save → evidence/x.log\n")
        self.stage_symlink(p, "x.log", "../../../../outside.log")
        self.assertEqual(self.cover(tasks=p)["evidence_missing"], ["2.2"])

    def test_evidence_worktree_symlink_is_missing(self):
        # a link in the working tree, unstaged, to a real file outside: never followed, never counted
        outside = Path(tempfile.mkdtemp(prefix="specwright-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (outside / "x.log").write_text("output\n")
        p = self.change_with_evidence("## 2. M\n\n- [x] 2.2 [evidence] Save → evidence/x.log\n")
        (p.parent / "evidence").mkdir()
        self.symlink_or_skip(outside / "x.log", p.parent / "evidence" / "x.log")
        self.assertEqual(self.cover(tasks=p)["evidence_missing"], ["2.2"])

    def test_evidence_symlinked_directory_is_missing(self):
        outside = Path(tempfile.mkdtemp(prefix="specwright-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (outside / "x.log").write_text("output\n")
        p = self.change_with_evidence("## 2. M\n\n- [x] 2.2 [evidence] Save → evidence/x.log\n")
        self.symlink_or_skip(outside, p.parent / "evidence")
        self.assertEqual(self.cover(tasks=p)["evidence_missing"], ["2.2"])

    def test_rev_evidence_directory_is_missing(self):
        p = self.repo_tasks("## 4. M\n\n- [x] 4.4 [evidence] Log → evidence/run.log\n")
        self.write_evidence("run.log/other", base=p.parent)
        self.commit("chore: evidence as a directory")
        doc = self.json_ok(self.run_script(tasks=p, rev="HEAD"))
        self.assertEqual(doc["evidence_missing"], ["4.4"])

    def test_rev_evidence_committed_symlink_is_missing(self):
        p = self.repo_tasks("## 4. M\n\n- [x] 4.4 [evidence] Log → evidence/run.log\n")
        self.commit("chore: planning")
        # stage a symlink entry through plumbing, so the test needs no symlink support from the OS
        blob = self.git("hash-object", "-w", "--stdin", input=b"../../../outside.log").strip()
        path = p.parent.relative_to(self.repo).as_posix() + "/evidence/run.log"
        self.git("update-index", "--add", "--cacheinfo", "120000,%s,%s" % (blob, path))
        self.git("commit", "-q", "-m", "chore: evidence as a symlink")
        doc = self.json_ok(self.run_script(tasks=p, rev="HEAD"))
        self.assertEqual(doc["evidence_missing"], ["4.4"])

    def test_rev_evidence_regular_file_present(self):
        p = self.repo_tasks("## 4. M\n\n- [x] 4.4 [evidence] Log → evidence/run.log\n")
        self.write_evidence(base=p.parent)
        self.commit("chore: evidence")
        doc = self.json_ok(self.run_script(tasks=p, rev="HEAD"))
        self.assertEqual(doc["evidence_missing"], [])

    def test_rev_ignores_worktree_symlink_on_tasks_path(self):
        # --rev reads the named path at the revision; a working-tree symlink must not redirect it to another file
        p = self.repo_tasks("## 1. M\n\n- [ ] 1.1 [user] Play\n")
        other = p.parent.parent / "other" / "tasks.md"
        other.parent.mkdir(parents=True)
        other.write_bytes(b"## 1. M\n\n- [x] 1.1 [user] Play\n")
        self.commit("chore: two changes")
        p.unlink()
        self.symlink_or_skip(other, p)
        doc = self.json_ok(self.run_script(tasks=p, rev="HEAD"))
        self.assertEqual(doc["waiting_on_user"], ["1.1"])

    def assert_rev_no_tasks(self, p):
        r = self.run_script(tasks=p, rev="HEAD")
        self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
        self.assertEqual(json.loads(r.stdout)["error"], "no_tasks")

    def test_rev_rejects_committed_symlink_tasks(self):
        # PR #187: git show would print the link target, read as a task list with no tasks: an unknown check, not ok
        p = self.repo_tasks("## 1. M\n\n- [ ] 1.1 [user] Play\n")
        other = p.parent.parent / "other" / "tasks.md"
        other.parent.mkdir(parents=True)
        other.write_bytes(b"## 1. M\n\n- [ ] 1.1 [user] Play\n")
        self.git("add", "-A")
        rel = p.relative_to(self.repo).as_posix()
        self.git("rm", "-q", "--cached", "--", rel)
        blob = self.git("hash-object", "-w", "--stdin", input=b"../other/tasks.md").strip()
        self.git("update-index", "--add", "--cacheinfo", "120000,%s,%s" % (blob, rel))
        self.git("commit", "-q", "-m", "chore: link")
        self.assert_rev_no_tasks(p)

    def test_rev_rejects_committed_directory_tasks(self):
        d = self.repo / "openspec" / "changes" / CHANGE / "tasks.md"
        d.mkdir(parents=True)
        (d / "x.md").write_bytes(b"- [ ] 1.1 [user] Play\n")
        self.commit("chore: directory")
        self.assert_rev_no_tasks(d)

    def test_rev_ignores_replace_refs(self):
        # PR #187 security: a local refs/replace/<sha> must not change what the ready head holds
        p = self.repo_tasks("## 1. M\n\n- [ ] 1.1 [user] Play\n")
        head = self.commit("chore: planning")
        p.write_bytes(b"## 1. M\n\n- [x] 1.1 [user] Play\n")
        fake = self.commit("chore: tick")
        self.git("replace", head, fake)
        doc = self.json_ok(self.run_script(tasks=p, rev=head))
        self.assertEqual(doc["waiting_on_user"], ["1.1"])

    def test_rev_reads_archived_tasks_at_commit(self):
        p = self.repo_tasks("## 4. M\n\n- [x] 4.3 [user] Play\n", archived=True)
        ticked = self.commit("chore: tick")
        p.write_bytes(b"## 4. M\n\n- [ ] 4.3 [user] Play\n")
        self.commit("chore: untick")
        doc = self.json_ok(self.run_script(tasks=p, rev="HEAD"))
        self.assertEqual(doc["waiting_on_user"], ["4.3"])
        doc = self.json_ok(self.run_script(tasks=p, rev=ticked))
        self.assertEqual(doc["waiting_on_user"], [])

    def test_rev_ignores_working_tree(self):
        text = "## 4. M\n\n- [ ] 4.3 [user] Play\n- [x] 4.4 [evidence] Log → evidence/run.log\n"
        p = self.repo_tasks(text)
        self.commit("chore: planning")
        p.write_bytes(text.replace("[ ] 4.3", "[x] 4.3").encode("utf-8"))
        self.write_evidence(base=p.parent)
        doc = self.json_ok(self.run_script(tasks=p, rev="HEAD"))
        self.assertEqual(doc["waiting_on_user"], ["4.3"])
        self.assertEqual(doc["evidence_missing"], ["4.4"])
        self.assertEqual(self.json_ok(self.run_script(tasks=p))["waiting_on_user"], [])

    def test_rev_missing_file_exits_2(self):
        p = self.repo_tasks("## 4. M\n\n- [ ] 4.3 [user] Play\n")  # in the working tree only
        r = self.run_script(tasks=p, rev="HEAD")
        self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
        doc = json.loads(r.stdout)
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["error"], "no_tasks")

    def json_ok(self, r):
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return json.loads(r.stdout.decode("utf-8"))

    def test_user_tick_never_makes_group_pending(self):
        text = "## 1. A\n\n- [x] 1.1 a\n\n## 2. B\n\n- [x] 2.1 [user] play\n"
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual(doc["pending_groups"], [{"group": 1, "tasks": ["1.1"]}])
        self.assertEqual(doc["uncovered"], ["1.1"])
        self.assertEqual(doc["user_uncommitted"], ["2.1"])

    def test_all_user_group_never_pending(self):
        text = "## 5. U\n\n- [x] 5.1 [user] play\n- [ ] 5.2 [user] watch\n"
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual(doc["pending_groups"], [])
        self.assertEqual(doc["uncovered"], [])
        self.assertEqual(doc["user_uncommitted"], ["5.1"])
        self.assertEqual(doc["waiting_on_user"], ["5.2"])

    def test_user_task_trailer_covers(self):
        text = "## 3. U\n\n- [x] 3.1 [user] play\n"
        sha = self.user_commit("docs(%s): record user checks 3.1" % CHANGE, user_trailers=["3.1"])
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual(doc["user_uncommitted"], [])
        self.assertEqual([c["sha"] for c in self.task(doc, "3.1")["commits"]], [sha])

    def test_two_user_trailers_cover_both(self):
        text = "## 3. U\n\n- [x] 3.2 [user] a\n\n## 4. V\n\n- [x] 4.3 [user] b\n"
        self.user_commit("docs(%s): record user checks 3.2, 4.3" % CHANGE, user_trailers=["3.2", "4.3"])
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual(doc["user_uncommitted"], [])
        self.assertEqual(doc["cross_group"], [])

    def test_user_trailer_on_group_commit_not_cross_group(self):
        text = "## 1. A\n\n- [x] 1.1 a\n- [x] 1.2 b\n\n## 2. B\n\n- [x] 2.1 [user] play\n"
        sha = self.user_commit("feat(%s): group 1 A" % CHANGE, task_trailers=["1.1", "1.2"], user_trailers=["2.1"])
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual(doc["cross_group"], [])
        self.assertEqual(doc["user_uncommitted"], [])
        self.assertEqual(doc["pending_groups"], [])
        self.assertEqual([c["sha"] for c in self.task(doc, "2.1")["commits"]], [sha])

    def test_user_trailer_does_not_cover_agent_task(self):
        text = "## 1. A\n\n- [x] 1.1 a\n- [x] 1.2 [evidence] log → evidence/x.log\n"
        self.user_commit("docs(%s): record user checks 1.1" % CHANGE, user_trailers=["1.1", "1.2"])
        doc = self.cover(tasks=self.tasks_file(text))
        self.assertEqual([self.task(doc, i)["kind"] for i in ("1.1", "1.2")], ["agent", "evidence"])
        self.assertEqual(self.task(doc, "1.1")["commits"], [])
        self.assertEqual(doc["uncovered"], ["1.1", "1.2"])
        self.assertEqual(doc["pending_groups"], [{"group": 1, "tasks": ["1.1", "1.2"]}])

    def test_missing_tasks_file_exits_2(self):
        r = self.run_script(tasks=self.tmp / "nope.md")
        self.assertEqual(r.returncode, 2)

    def test_bad_range_exits_3(self):
        r = subprocess.run([bashexe.bash(), str(SCRIPT), "--repo", str(self.repo), "--range", "nope..HEAD",
                            "--tasks", str(self.tasks_file()), "--change", CHANGE], capture_output=True)
        self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
