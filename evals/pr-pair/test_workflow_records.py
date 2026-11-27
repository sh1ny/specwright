"""Native feedback records and current-evidence planning, against the bytes and runs the frozen script left (change
native-cli-retire-scripts task 7.2): no case starts a frozen script."""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pr_pair as original
import oracle_capture
import test_parity as parity
import fakeexe  # parity puts evals/ on sys.path
import swcall  # parity puts evals/ on sys.path
from types import SimpleNamespace


def setUpModule():
    parity.setUpModule()


class NativePass:
    def command(self, args, which="native", env=None, cwd=None):
        environment = {**self.env(), **(env or {})}
        args = list(map(str, args))
        if which == "native":
            return swcall.run(["pr", *args], cwd=cwd or self.tmp, env=environment, timeout=120, text=False)  # direct entry
        return self.recorded_run()

    def recorded_run(self, case=None):
        """The next recorded run of the frozen side as a finished process. A `pass write` also leaves the record it wrote, as
        the recorded bytes with the checkout of the machine that wrote it replaced by this one's, and its stdout names that
        record's owner."""
        doc, kept = oracle_capture.recorded(self, case)
        out = doc["stdout"]
        if kept is not None:
            written = json.loads(kept.decode("utf-8"))["owner"]
            text = kept.decode("utf-8").replace(written["checkout"], str(self.code).replace("\\", "/"))
            self.record_path().parent.mkdir(parents=True, exist_ok=True)
            self.record_path().write_bytes(text.encode("utf-8"))
            if isinstance(out, dict):
                out = dict(out, owner=written["id"])
        stdout = (json.dumps(out) + "\n").encode("utf-8")
        return SimpleNamespace(returncode=doc["exit"], stdout=stdout, stderr=b"")

    def pp(self, *args, env=None, expect=0, cwd=None, which="native"):
        result = self.command(args, which, env, cwd)
        if expect is not None:
            self.assertEqual(result.returncode, expect, f"{args}\n{result.stdout!r}\n{result.stderr!r}")
        lines = result.stdout.decode("utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1, result)
        doc = json.loads(lines[0])
        doc["_rc"] = result.returncode
        return doc


class WorkflowRecords(NativePass, original.PassBase):
    thread_finding = original.PassPlan.thread_finding
    replied_code_fix = original.PassPlan.replied_code_fix
    react_rest = original.PassPlan.react_rest
    react_node = original.PassPlan.react_node
    ANSWERED = original.PassPlan.ANSWERED
    adopted_code_pr = original.PassPlan.adopted_code_pr
    link_args = original.PassPlan.link_args
    markers = original.PassPlan.markers

    def test_native_pass_write_uses_utf8_lf_without_python38(self):
        f = self.write_json('native-lf-intent.json', self.intent([]))
        result = self.pp('pass', 'write', *self.common(), '--intent', f)
        self.assertTrue(result['ok'])
        data = self.record_path().read_bytes()
        self.assertNotIn(b'\r', data)
        self.assertEqual(json.loads(data.decode('utf-8'))['change'], original.CHANGE)

    def raw_root(self, name):
        path = os.fsencode(self.tmp) + b'/' + name + b'-\xff'
        try:
            os.mkdir(path)
        except OSError as error:
            if sys.platform.startswith('linux'):
                self.fail(f'Linux raw-path probe must succeed: {error}')
            self.skipTest(f'platform: {sys.platform} filesystem refuses raw path bytes: {error}')
        return path

    def raw_environment(self, state=None, home=None):
        fixture = self.env()
        raw = {key: value for key, value in os.environb.items() if os.fsdecode(key) in fixture}
        raw.update({os.fsencode(key): os.fsencode(value) for key, value in fixture.items()})
        for key, value in ((b'SPECWRIGHT_STATE_DIR', state), (b'HOME', home)):
            raw.pop(key, None)
            if value is not None:
                raw[key] = value
        return raw

    def raw_pp(self, args, environment, expect=0):
        args = list(map(str, args))
        result = swcall.run(['pr', *args], env=dict(environment), cwd=self.tmp, timeout=120, text=False)  # direct entry
        self.assertEqual(result.returncode, expect, (result.stdout, result.stderr))
        return json.loads(result.stdout.decode('utf-8', errors='surrogateescape'))

    def assert_stops_naming(self, result, variable):
        self.assertEqual(result['error'], 'not_utf8', result)
        self.assertFalse(result['ok'])
        self.assertIn(f'{variable} is not valid UTF-8', result['message'])
        self.assertIn('\\xFF', result['message'])
        self.assertIn('UTF-8 path', result['message'])

    @unittest.skipIf(os.name == 'nt', 'platform: raw POSIX process environment is unavailable on Windows')
    def test_non_utf8_posix_state_directory_stops_by_name(self):
        root = self.raw_root(b'raw-state')
        home = os.fsencode(self.tmp / 'unused-home')
        environment = self.raw_environment(state=root, home=home)
        intent = self.write_json('raw-intent.json', self.intent([]))
        for args in (['pass', 'write', *self.common(), '--intent', intent],
                     ['pass', 'plan', *self.common()]):
            result = self.raw_pp(args, environment, expect=1)
            self.assert_stops_naming(result, 'SPECWRIGHT_STATE_DIR')
        self.assertEqual(os.listdir(root), [], 'no record or directory was created under the state directory')
        self.assertFalse(os.path.exists(home + b'/.cache/specwright/feedback'))
        self.assertFalse(self.record_path().exists())

    @unittest.skipIf(os.name == 'nt', 'platform: raw POSIX process environment is unavailable on Windows')
    def test_non_utf8_posix_home_stops_by_name(self):
        home = self.raw_root(b'raw-home')
        intent = self.write_json('raw-intent.json', self.intent([]))
        for state in (None, b''):
            environment = self.raw_environment(state=state, home=home)
            result = self.raw_pp(['pass', 'write', *self.common(), '--intent', intent], environment, expect=1)
            self.assert_stops_naming(result, 'HOME')
            self.assertEqual(os.listdir(home), [], 'no record or directory was created under the home')
            self.assertFalse(self.record_path().exists())

    @unittest.skipIf(os.name == 'nt', 'platform: raw POSIX process environment is unavailable on Windows')
    def test_process_state_override_does_not_need_a_home(self):
        root = os.fsencode(self.tmp) + b'/no-home-state'
        os.mkdir(root)
        environment = self.raw_environment(state=root)
        self.assertNotIn(b'HOME', environment)
        intent = self.write_json('raw-intent.json', self.intent([]))
        written = self.raw_pp(['pass', 'write', *self.common(), '--intent', intent], environment)
        expected = root + b'/feedback/' + original.record_key(original.CODE, original.CHANGE).encode()
        self.assertTrue(os.path.isfile(expected))
        self.assertEqual(os.fsencode(written['path']), expected)
        planned = self.raw_pp(['pass', 'plan', *self.common()], environment)
        self.assertTrue(planned['record'])
        self.assertEqual(os.fsencode(planned['path']), expected)

    @unittest.skipIf(os.name == 'nt', 'platform: raw POSIX process environment is unavailable on Windows')
    def test_missing_home_refuses_without_choosing_a_directory(self):
        intent = self.write_json('raw-intent.json', self.intent([]))
        for state in (None, b''):
            for home in (None, b''):
                environment = self.raw_environment(state=state, home=home)
                if home is None:
                    self.assertNotIn(b'HOME', environment)
                result = self.raw_pp(['pass', 'write', *self.common(), '--intent', intent], environment, expect=1)
                self.assertEqual(result['error'], 'internal_error')
                self.assertFalse(self.record_path().exists())
                for operation in ([], ['unknown'], ['plan']):
                    usage = self.raw_pp(['pass', *operation], environment, expect=2)
                    self.assertEqual(usage['error'], 'usage')

    @unittest.skipIf(os.name == 'nt', 'platform: raw POSIX process environment is unavailable on Windows')
    def test_non_utf8_state_directory_never_falls_back(self):
        raw = self.raw_root(b'no-fallback-state')
        home = os.fsencode(self.tmp / 'default-home')
        defaults = self.raw_environment(home=home)  # no state override: the default directory under home
        intent = self.write_json('raw-intent.json', self.intent([self.finding()]))
        written = self.raw_pp(['pass', 'write', *self.common(), '--intent', intent], defaults)
        self.fix_store()
        self.push_all()
        head = self.tip(self.store)
        path = home + b'/.cache/specwright/heads/' + original.STORE.lower().encode() + b'/3/' + head.encode()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as output:
            output.write(b'Thu, 08 Oct 2026 12:00:00 GMT\n')
        self.seed_pulls(original.STORE, [])
        self.add_comment(original.STORE, 3, '@codex review', 'KintsugiBot', 2001, created_at='2026-10-08T12:05:00Z')
        args = ['pass', 'plan', *self.common(), '--owner', written['owner'],
                *self.snapshots(original.snap(threads=[original.thread()]))]
        environment = self.raw_environment(state=raw, home=home)
        result = self.raw_pp(args, environment, expect=1)
        self.assert_stops_naming(result, 'SPECWRIGHT_STATE_DIR')
        self.assertNotIn('rows', result, 'the default directory record must not be read')
        self.assertEqual(os.listdir(raw), [])

    def snapshots(self, snapshot=None):
        code = self.with_pr_target(snapshot if snapshot is not None else original.snap(), original.CODE, 5)
        store = self.with_pr_target(original.snap(), original.STORE, 3)
        return ["--snapshot", f"code={self.write_json('code-snap.json', code)}",
                "--snapshot", f"store={self.write_json('store-snap.json', store)}"]

    def captured(self, method):
        """The directory name the capture gave this class's test `method`."""
        return f"{type(self).__module__.rsplit('.', 1)[-1]}.{type(self).__qualname__}.{method}"

    def compare_plan(self, snapshot=None, case=None):
        """Native `pass plan` equals the next recorded frozen run (`case` names its records, else this test's): the exit status,
        the document apart from the generated owner fields, the `gh` calls, the final fake-gh state and the comment bodies."""
        # The frozen planner did not verify saved PR targets. Seed the PRs
        # referenced by the old record, and require the new reads to be read-only.
        pulls = ((original.CODE, 5, self.code), (original.STORE, 3, self.store))
        for slug, number, repo in pulls:
            if not self.pulls(slug):
                self.add_pull(slug, number, sha=self.tip(repo))
        before = self.gh()
        args = ["pass", "plan", *self.common(), "--owner", self.owner, *self.snapshots(snapshot)]
        result = self.command(args)
        calls = parity.calls_of(self.gh_log, lambda call: call["argv"])
        got = oracle_capture.document(self, {"code": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
                                             "calls": calls, "state": self.gh_state.read_bytes()})
        want = oracle_capture.recorded(self, case)[0]
        self.assertEqual(self.gh(), before)
        endpoints = tuple(f"repos/{slug}/pulls?" for slug, _, _ in pulls)
        looks_up_pr = lambda argv: any(a.startswith(endpoints) for a in argv)
        self.assertEqual([argv[-1].split("?", 1)[0] for argv in calls if looks_up_pr(argv)],
                         [f"repos/{slug}/pulls" for slug, _, _ in pulls])
        got["calls"] = [argv for argv in got["calls"] if argv[:2] != ["auth", "token"]
                        and argv != ["api", "--hostname", "github.com", "user", "--jq", ".login"]
                        and not looks_up_pr(argv)]
        for slug, _, _ in pulls:
            got["state"]["repos"].pop(slug)
        if not got["state"]["repos"] and "repos" not in want["state"]:
            del got["state"]["repos"]
        self.assertIsNone(oracle_capture.compare(self, got, want))
        return json.loads(result.stdout)

    def resumes_a_recorded_frozen_record(self, case=None):
        written = json.loads(self.recorded_run(case).stdout)  # the frozen writer's run: it leaves its record as recorded bytes
        self.assertTrue(written["ok"], written)
        self.owner = written["owner"]
        before = self.record_path().read_bytes()
        result = self.compare_plan(original.snap(threads=[original.thread()]), case)
        self.assertEqual((result["status"], result["round"], result["new_pass_allowed"]), ("resume", 2, False))
        self.assertEqual(self.row(result, "fix_commit", "store")["action"], "finish_edits")
        self.assertEqual(self.record_path().read_bytes(), before, "a plan does not change the record")

    def test_native_plan_resumes_a_recorded_frozen_record(self):
        self.resumes_a_recorded_frozen_record()

    GENERATED = ("id", "at", "checkout", "host")

    def normalized_record(self, raw):
        """A record's parsed fields with the generated ones checked for form and for their relation to the run, then replaced."""
        from datetime import datetime, timezone
        record = json.loads(raw.decode("utf-8"))
        owner = record["owner"]
        self.assertRegex(owner["id"], r"^[0-9a-f]{32}$")
        stamp = datetime.fromisoformat(owner["at"].replace("Z", "+00:00"))
        self.assertLessEqual(stamp, datetime.now(timezone.utc))
        self.assertEqual(owner["checkout"], str(self.code).replace("\\", "/"))
        self.assertTrue(owner["host"].strip())
        if "written_at" in record:
            self.assertEqual(record["written_at"], owner["at"])
            record["written_at"] = "<time>"
        record["owner"] = {key: "<%s>" % key for key in self.GENERATED}
        return record

    def native_record_matches_the_fixture(self, case=None):
        self.write_record([self.finding()])
        raw = self.record_path().read_bytes()
        self.assertNotIn(b"\r", raw)
        raw.decode("utf-8")
        self.assertEqual(json.loads(raw)["version"], 2)
        self.compare_plan(original.snap(threads=[original.thread()]), case)  # the frozen reader's recorded plan of this record
        self.assertEqual(self.record_path().read_bytes(), raw)
        fixture = oracle_capture.recorded_fixture(self, case)  # the record the frozen reader accepted
        self.assertEqual(self.normalized_record(raw), self.normalized_fixture(fixture))

    def normalized_fixture(self, raw):
        """The recorded fixture's fields, as normalized_record leaves a native record (its generated fields were the capturing
        machine's: only their form is checked)."""
        record = json.loads(raw.decode("utf-8"))
        owner = record["owner"]
        self.assertRegex(owner["id"], r"^[0-9a-f]{32}$")
        self.assertTrue(owner["host"].strip())
        if "written_at" in record:
            self.assertEqual(record["written_at"], owner["at"])
            record["written_at"] = "<time>"
        record["owner"] = {key: "<%s>" % key for key in self.GENERATED}
        return record

    def test_native_record_matches_frozen_reader_fixture(self):
        self.native_record_matches_the_fixture()

    def test_records_both_ways_from_recorded_bytes(self):
        # the native reader resumes from the frozen writer's recorded bytes, and the native writer's record is the fixture the
        # frozen reader accepted: no frozen script starts
        self.resumes_a_recorded_frozen_record(self.captured("test_native_plan_resumes_an_existing_record"))
        self.setUp()
        self.native_record_matches_the_fixture(self.captured("test_script_plan_reads_a_native_record"))

    def test_concurrent_writers_publish_one_record(self):
        intent = self.write_json("intent.json", self.intent([self.finding()]))
        barrier = threading.Barrier(4)
        results = []
        def write():
            barrier.wait()
            results.append(self.command(["pass", "write", *self.common(), "--intent", intent]))
        workers = [threading.Thread(target=write) for _ in range(4)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(timeout=120)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(sorted(result.returncode for result in results), [0, 1, 1, 1])
        docs = [json.loads(result.stdout) for result in results]
        self.assertEqual(sum(doc.get("error") == "record_exists" for doc in docs), 3)
        record = json.loads(self.record_path().read_bytes())
        self.assertEqual(record["owner"]["id"], next(doc["owner"] for doc in docs if doc["ok"]))
        self.assertEqual(record["findings"], self.intent([self.finding()])["findings"])
        self.assertEqual(list(self.record_path().parent.glob(".tmp-*")), [])

    def test_legacy_migration_and_held_lock_remain_safe(self):
        self.write_record([self.finding()])
        raw = self.record_path().read_bytes()
        legacy = self.state_dir / "feedback" / original.legacy_key(original.CODE, original.CHANGE)
        self.record_path().rename(legacy)
        self.plan()
        self.assertEqual(self.record_path().read_bytes(), raw)
        self.assertFalse(legacy.exists())
        lock = Path(str(self.record_path()) + ".lock")
        lock.mkdir()
        refused = self.pp("pass", "adopt", *self.common(), "--owner", "new", "--from", self.owner, expect=1)
        self.assertEqual(refused["error"], "record_busy")
        self.assertTrue(lock.is_dir())
        self.assertEqual(self.record_path().read_bytes(), raw)

    def test_concurrent_mutations_acquire_one_lock(self):
        self.write_record([self.finding()])
        before = json.loads(self.record_path().read_bytes())
        barrier = threading.Barrier(6)
        raw = {}  # worker index -> (exit status, stdout, stderr) or the exception it raised
        def adopt(index):
            barrier.wait()
            try:
                result = self.command(["pass", "adopt", *self.common(), "--owner", f"new-{index}", "--from", self.owner])
                raw[index] = (result.returncode, result.stdout, result.stderr)
            except BaseException as error:
                raw[index] = error
        workers = [threading.Thread(target=adopt, args=(i,)) for i in range(6)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(timeout=120)
        shown = chr(10).join(f"worker {i}: {raw.get(i, 'no result')!r}" for i in range(6))
        self.assertTrue(all(not worker.is_alive() for worker in workers), shown)
        self.assertEqual(sorted(raw), list(range(6)), shown)
        self.assertTrue(all(isinstance(value, tuple) for value in raw.values()), shown)
        try:
            docs = {i: json.loads(value[1]) for i, value in raw.items()}
        except ValueError as error:
            self.fail(f"a worker's stdout is not JSON ({error}), raw results:{chr(10)}{shown}")
        winners = [i for i in range(6) if docs[i].get("ok") is True]
        self.assertEqual(len(winners), 1, shown)
        self.assertEqual(raw[winners[0]][0], 0, shown)
        for i in range(6):
            if i != winners[0]:
                self.assertEqual(raw[i][0], 1, shown)
                self.assertIn(docs[i].get("error"), ("record_busy", "not_owner"), shown)
        after = json.loads(self.record_path().read_bytes())
        expected = dict(before, owner=after["owner"])
        self.assertEqual(after, expected, shown)
        self.assertEqual(after["owner"]["id"], f"new-{winners[0]}", shown)
        self.assertFalse(Path(str(self.record_path()) + ".lock").exists(), shown)

    def test_done_replans_under_its_lock_and_blocks_concurrent_adoption(self):
        self.settings("github:\n  login: KintsugiBot\npr:\n  react: false\n")
        self.write_record([self.finding(dest="code", react=None)])
        self.fix_code()
        self.push_all()
        held, release = self.tmp / "done-held", self.tmp / "done-release"
        lock = Path(str(self.record_path()) + ".lock")
        tool = self.tmp / "bin" / "git"
        launcher = tool.with_suffix(".exe") if os.name == "nt" else tool
        delegate = launcher.with_name("git-with-fixture-origin" + launcher.suffix)
        launcher.rename(delegate)
        fakeexe.write_python_fake(tool, f'''
import os, subprocess, sys, time
from pathlib import Path
args = sys.argv[1:]
if args == ["rev-parse", "refs/heads/{original.BRANCH}"] and Path(os.environ["WF_RECORD_LOCK"]).is_file():
    Path(os.environ["WF_DONE_HELD"]).touch()
    release = Path(os.environ["WF_DONE_RELEASE"])
    while not release.exists():
        time.sleep(0.05)
sys.exit(subprocess.call([{str(delegate)!r}, *args]))
''')
        self.extra_env.update(WF_RECORD_LOCK=lock.as_posix(), WF_DONE_HELD=held.as_posix(),
                              WF_DONE_RELEASE=release.as_posix())
        results = []
        args = ["pass", "done", *self.common(), "--owner", self.owner, *self.snapshots(original.snap(threads=[]))]
        worker = threading.Thread(target=lambda: results.append(self.command(args)))
        worker.start()
        try:
            end = time.monotonic() + 75
            while worker.is_alive() and not held.exists() and time.monotonic() < end:
                time.sleep(0.05)
            self.assertTrue(held.exists(), f"done did not reach the locked replanning read: {results}")
            before = self.record_path().read_bytes()
            refused = self.pp("pass", "adopt", *self.common(), "--owner", "new", "--from", self.owner, expect=1)
            self.assertEqual(refused["error"], "record_busy")
            self.assertEqual(self.record_path().read_bytes(), before)
            self.assertTrue(lock.is_file())
        finally:
            release.touch()
            worker.join(timeout=120)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].returncode, 0, results[0].stdout)
        self.assertTrue(json.loads(results[0].stdout)["deleted"])
        self.assertFalse(self.record_path().exists())
        self.assertFalse(lock.exists())

    def test_owner_adoption_rechecks_and_retains_the_original_cutoff(self):
        self.write_record([self.finding()])
        before = json.loads(self.record_path().read_bytes())
        prior = self.owner
        adopted = self.pp("pass", "adopt", *self.common(), "--owner", "new-owner", "--from", prior)
        self.assertEqual(adopted["previous"], prior)
        record = json.loads(self.record_path().read_bytes())
        self.assertEqual(record["written_at"], before["written_at"])
        self.assertEqual(record["heads"], before["heads"])
        kept = self.record_path().read_bytes()
        stale = self.pp("pass", "adopt", *self.common(), "--owner", "third", "--from", prior, expect=1)
        self.assertEqual(stale["error"], "not_owner")
        foreign = self.pp("pass", "done", *self.common(), "--owner", prior, expect=1)
        self.assertEqual(foreign["error"], "not_owner")
        self.assertEqual(self.record_path().read_bytes(), kept)
        self.assertFalse(self.plan()["owned"])

    def test_gitbutler_uses_branch_evidence_and_ignores_preexisting_unassigned_paths(self):
        self.settings("vcs: gitbutler\nfinish: pr\ngithub:\n  login: KintsugiBot\npr:\n  react: false\n")
        (self.code / ".git" / "gitbutler").mkdir()
        self.git(self.code, "config", "gitbutler.project.targetRef", "refs/remotes/origin/main")
        target = self.tip(self.code, "main")
        status = self.tmp / "but-status.json"
        def state(uncommitted):
            status.write_text(json.dumps({"mergeBase": {"commitId": target}, "stacks": [
                {"branches": [{"name": original.BRANCH}], "assignedChanges": []},
                {"branches": [{"name": "feat/other"}], "assignedChanges": [{"filePath": "greet.py"}]},
            ], "uncommittedChanges": [{"filePath": f} for f in uncommitted]}), encoding="utf-8")
        state(["unrelated.txt", "greet.py"])
        tool = self.tmp / "bin" / "but"
        tool.write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo "but 0.23.1"; exit 0; fi\n'
                        'if [ "$1" = status ]; then cat "$WF_BUT_STATUS"; exit 0; fi\nexit 1\n',
                        encoding="utf-8", newline="\n")
        tool.chmod(0o755)
        fakeexe.add_launcher(tool)  # sw starts it by PATHEXT name on Windows (D9)
        self.extra_env["WF_BUT_STATUS"] = status.as_posix()
        (self.code / "unrelated.txt").write_text("already present", encoding="utf-8")
        # Another applied branch's work must not satisfy this pass's edit.
        (self.code / "greet.py").write_text("def greet(n):\n    return n.strip()\n", encoding="utf-8")
        self.write_record([self.finding(dest="code", react=None)])
        self.assertEqual(json.loads(self.record_path().read_bytes())["preexisting"], ["unrelated.txt"])
        result = self.plan()
        fix = self.row(result, "fix_commit", "code")
        self.assertEqual(fix["pending_edits"][0]["reason"], "not_made")
        self.assertFalse(any(stop["reason"] == "unrecorded_change" for stop in result["stops"]))
        state(["unrelated.txt", "greet.py", "new-outside.txt"])
        changed = self.plan()
        self.assertEqual(next(stop["files"] for stop in changed["stops"] if stop["reason"] == "unrecorded_change"), ["new-outside.txt"])

    def test_unreadable_record_blocks_a_new_pass(self):
        self.test_interrupted_record_is_refused_by_each_pass_operation()
        self.record_path().unlink()
        legacy = self.state_dir / "feedback" / original.legacy_key(original.CODE, original.CHANGE)
        legacy.write_bytes(b"{cut off")
        intent = self.write_json("intent.json", self.intent([self.finding()]))
        refused = self.pp("pass", "write", *self.common(), "--intent", intent, expect=1)
        self.assertEqual(refused["error"], "record_unreadable")
        self.assertEqual(legacy.read_bytes(), b"{cut off")

    def test_interrupted_record_is_refused_by_each_pass_operation(self):
        self.record_path().parent.mkdir(parents=True, exist_ok=True)
        intent = self.write_json("intent.json", self.intent([self.finding()]))
        for body in (b"", b'{"version":2,"owner":'):
            self.record_path().write_bytes(body)
            for operation, extra, error in [
                ("write", ["--intent", intent], "record_exists"),
                ("plan", [], "record_unreadable"),
                ("adopt", ["--owner", "new", "--from", "old"], "record_unreadable"),
                ("done", ["--owner", "old"], "record_unreadable"),
            ]:
                with self.subTest(body=body, operation=operation):
                    doc = self.pp("pass", operation, *self.common(), *extra, expect=1)
                    self.assertEqual(doc["error"], error)
                    self.assertEqual(self.record_path().read_bytes(), body)
                    self.assertFalse(Path(str(self.record_path()) + ".lock").exists())

    def test_structurally_corrupt_record_never_claims_completion(self):
        self.record_path().parent.mkdir(parents=True, exist_ok=True)
        for record in ({}, {"owner": {"id": "mine"}, "findings": None}, ["not", "an", "object"]):
            self.record_path().write_text(json.dumps(record), encoding="utf-8")
            before = self.record_path().read_bytes()
            frozen = self.pp("pass", "plan", *self.common(), which="frozen", expect=1)
            self.assertEqual(frozen["error"], "internal_error")
            result = self.pp("pass", "plan", *self.common(), expect=1)
            self.assertEqual(result["error"], "internal_error")
            self.assertEqual(self.record_path().read_bytes(), before)

    def test_corrupt_owner_cannot_be_adopted_as_unowned(self):
        self.record_path().parent.mkdir(parents=True, exist_ok=True)
        for record in ([], {"owner": "held"}, {"owner": ["held"]}, {"owner": 7}):
            self.record_path().write_text(json.dumps(record), encoding="utf-8")
            before = self.record_path().read_bytes()
            args = ["pass", "adopt", *self.common(), "--owner", "new", "--from", "none"]
            frozen = self.pp(*args, which="frozen", expect=1)
            self.assertEqual(frozen["error"], "internal_error")
            native = self.pp(*args, expect=1)
            self.assertEqual(native["error"], "internal_error")
            self.assertEqual(self.record_path().read_bytes(), before)

    def test_directory_record_is_occupied_and_unreadable(self):
        self.record_path().mkdir(parents=True)
        invalid_findings = self.write_json("intent.json", {**self.intent([]), "findings": None})
        for operation, extra, error in [
            ("write", ["--intent", invalid_findings], "record_exists"),
            ("plan", [], "record_unreadable"),
            ("done", ["--owner", "mine"], "record_unreadable"),
            ("adopt", ["--owner", "new", "--from", "none"], "record_unreadable"),
        ]:
            with self.subTest(operation=operation):
                frozen = self.pp("pass", operation, *self.common(), *extra, which="frozen", expect=1)
                self.assertEqual(frozen["error"], error)
                native = self.pp("pass", operation, *self.common(), *extra, expect=1)
                self.assertEqual(native["error"], error)
                self.assertTrue(self.record_path().is_dir())
                self.assertFalse(Path(str(self.record_path()) + ".lock").exists())

    def test_corrupt_snapshot_shape_is_never_evidence_of_an_answer(self):
        self.write_record([self.finding(react=None)])
        before = self.record_path().read_bytes()
        for snapshot in ([], {"threads": "invalid"}, {"threads": ["invalid"]}):
            with self.subTest(snapshot=snapshot):
                if isinstance(snapshot, dict):
                    snapshot = self.with_pr_target(snapshot, original.CODE, 5)
                file = self.write_json("bad-snapshot.json", snapshot)
                args = ["pass", "plan", *self.common(), "--snapshot", f"code={file}"]
                frozen = self.pp(*args, which="frozen", expect=1)
                self.assertEqual(frozen["error"], "internal_error")
                native = self.pp(*args, expect=1)
                self.assertEqual(native["error"], "internal_error")
                self.assertEqual(self.record_path().read_bytes(), before)


# Exercise existing behavioural assertions through the native command boundary.
for _name in [
    "test_pass_plan_trailer_commit_with_part_of_the_edits_is_not_done",
    "test_pass_plan_recorded_head_dropped_from_the_branch_stops",
    "test_pass_plan_unrecorded_change_stops", "test_pass_plan_unjudgeable_edit_stops",
    "test_pass_plan_stale_disposition_stops", "test_pass_plan_reply_done_resolution_pending",
    "test_pass_plan_reaction_done_when_present", "test_pass_plan_reaction_on_a_node_id_target",
    "test_pass_plan_reaction_read_failure_is_unknown", "test_pass_plan_node_reaction_read_failure_is_unknown",
    "test_pass_write_finds_the_marker_under_the_selected_root_only",
    "test_pass_write_stops_when_two_archives_are_new", "test_pass_plan_finding_spanning_both_repos",
    "test_pass_plan_reads_a_private_store_as_the_store_login",
    "test_pass_plan_adopted_code_pr_needs_the_link",
    "test_pass_plan_link_done_when_descriptions_name_the_peer",
]:
    setattr(WorkflowRecords, _name, getattr(original.PassPlan, _name))


class RepoLocalRecords(NativePass, original.PassRepoLocal):
    pass


class CutoffRecords(NativePass, original.RerequestCutoff):
    pass


for _name in dir(original.RerequestCutoff):
    if _name.startswith('test_') and _name not in {
        'test_rerequest_cutoff_push_time', 'test_rerequest_cutoff_first_seen_done_once',
        'test_rerequest_old_record_keeps_its_cutoff_after_adopt',
    }:
        setattr(CutoffRecords, _name, None)
