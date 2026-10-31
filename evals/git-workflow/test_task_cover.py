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

    def git(self, *args):
        r = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True)
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

    def run_script(self, tasks=None, env=None, change=CHANGE):
        tasks = tasks or self.tasks_file()
        e = dict(os.environ, **(env or {}))
        return subprocess.run(
            [bashexe.bash(), str(SCRIPT), "--repo", str(self.repo), "--range", self.base + "..HEAD",
             "--tasks", str(tasks), "--change", change],
            capture_output=True, env=e)

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

    def test_missing_tasks_file_exits_2(self):
        r = self.run_script(tasks=self.tmp / "nope.md")
        self.assertEqual(r.returncode, 2)

    def test_bad_range_exits_3(self):
        r = subprocess.run([bashexe.bash(), str(SCRIPT), "--repo", str(self.repo), "--range", "nope..HEAD",
                            "--tasks", str(self.tasks_file()), "--change", CHANGE], capture_output=True)
        self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
