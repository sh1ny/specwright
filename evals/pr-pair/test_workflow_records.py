"""Native feedback records and current-evidence planning against the frozen script."""
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
import test_parity as parity
import fakeexe  # parity puts evals/ on sys.path


def setUpModule():
    parity.setUpModule()


def tearDownModule():
    parity.tearDownModule()


class NativePass:
    def command(self, args, which="native", env=None, cwd=None):
        environment = {**self.env(), **(env or {})}
        args = list(map(str, args))
        if which == "native":
            binary = os.environ["SPECWRIGHT_SW"]
            payload = b"".join(str(x).encode("utf-8") + b"\0" for x in
                               [parity.SCRIPTS, parity.bashexe.bash(), *args[1:]])
            return subprocess.run([binary, "pr", args[0], "--args-stdin"], input=payload,
                                  cwd=cwd or self.tmp, env=environment, capture_output=True, timeout=120)
        environment["ORACLE_SW_DIR"] = parity.oracle_sw_dir()
        return subprocess.run([parity.bashexe.bash(), str(parity.ORACLE / "pr-pair.sh"), *args],
                              cwd=cwd or self.tmp, env=environment, capture_output=True, timeout=120)

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

    def test_native_runtime_has_no_embedded_workflow(self):
        text = original.SCRIPT.read_text(encoding='utf-8')
        self.assertNotIn("<<'PYSRC'", text)
        self.assertNotIn('def pass_write(', text)
        self.assertNotIn('class _Bounded:', text)
        for command in ('identity', 'context', 'vcs', 'tier', 'policy', 'discover',
                        'expected', 'ensure-pr', 'link', 'pair-state', 'rounds',
                        'closing-check', 'closed-check', 'merge', 'delete-remote',
                        'item-issues', 'pass', 'cleanup-plan', 'branch-check'):
            self.assertIn(command, text)

    def test_native_pass_write_uses_utf8_lf_without_python38(self):
        f = self.write_json('native-lf-intent.json', self.intent([]))
        result = self.pp('pass', 'write', *self.common(), '--intent', f)
        self.assertTrue(result['ok'])
        data = self.record_path().read_bytes()
        self.assertNotIn(b'\r', data)
        self.assertEqual(json.loads(data.decode('utf-8'))['change'], original.CHANGE)

    def python38(self):
        py = original.find_py38()
        if not py:
            self.skipTest('no Python 3.8 interpreter (set SPECWRIGHT_PY38, or `uv python install 3.8`)')
        return py

    def test_no_python_3_8_available_to_the_test(self):
        # Test the conditional check's reported outcome rather than returning
        # successfully when this machine has no minimum-version interpreter.
        case = unittest.FunctionTestCase(self.python38)
        result = unittest.TestResult()
        with mock.patch.object(original, 'find_py38', return_value=None):
            case.run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.skipped), 1)
        self.assertIn('no Python 3.8 interpreter', result.skipped[0][1])
        self.assertEqual(result.failures + result.errors, [])

    def test_pass_write_on_python_3_8(self):
        py = self.python38()
        shims = self.tmp / 'py38bin'
        shims.mkdir()
        for name in ('python3', 'python'):
            wrapper = shims / name
            wrapper.write_text(f'#!/bin/sh\nexec "{original.fixtures.posix(py)}" "$@"\n', encoding='utf-8', newline='\n')
            wrapper.chmod(0o755)
        environment = {**self.env(), 'PATH': str(shims) + os.pathsep + self.env()['PATH']}
        probe = subprocess.run([parity.bashexe.bash(), '-c', "python3 -c 'import sys; print(sys.version_info[:2])'"],
                               capture_output=True, text=True, env=environment, timeout=30)
        self.assertEqual(probe.stdout.strip(), '(3, 8)', probe.stdout + probe.stderr)
        intent = self.write_json('py38-intent.json', self.intent([]))
        result = subprocess.run([parity.bashexe.bash(), str(original.SCRIPT), 'pass', 'write',
                                 *map(str, self.common()), '--intent', str(intent)],
                                capture_output=True, text=True, env=environment, cwd=self.tmp, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])
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

    def raw_pp(self, args, environment, which='native', expect=0):
        args = list(map(str, args))
        environment = dict(environment)
        if which == 'native':
            payload = b''.join(str(value).encode('utf-8') + b'\0' for value in
                               [parity.SCRIPTS, parity.bashexe.bash(), *args[1:]])
            result = subprocess.run([os.environ['SPECWRIGHT_SW'], 'pr', args[0], '--args-stdin'],
                input=payload, env=environment, cwd=self.tmp, capture_output=True, timeout=120)
        else:
            environment[b'ORACLE_SW_DIR'] = os.fsencode(parity.oracle_sw_dir())
            result = subprocess.run([parity.bashexe.bash(), str(parity.ORACLE / 'pr-pair.sh'), *args],
                env=environment, cwd=self.tmp, capture_output=True, timeout=120)
        self.assertEqual(result.returncode, expect, (result.stdout, result.stderr))
        return json.loads(result.stdout.decode('utf-8', errors='surrogateescape'))

    @unittest.skipIf(os.name == 'nt', 'platform: raw POSIX process environment is unavailable on Windows')
    def test_raw_posix_state_directory_keeps_the_record_location(self):
        root = self.raw_root(b'raw-state')
        home = os.fsencode(self.tmp / 'unused-home')
        environment = self.raw_environment(state=root, home=home)
        intent = self.write_json('raw-intent.json', self.intent([]))
        written = self.raw_pp(['pass', 'write', *self.common(), '--intent', intent], environment)
        expected = root + b'/feedback/' + original.record_key(original.CODE, original.CHANGE).encode()
        self.assertTrue(os.path.isfile(expected))
        self.assertEqual(os.fsencode(written['path']), expected)
        for which in ('native', 'frozen'):
            plan = self.raw_pp(['pass', 'plan', *self.common(), '--owner', written['owner']], environment, which)
            self.assertTrue(plan['record'])
            self.assertEqual(os.fsencode(plan['path']), expected)
        self.assertFalse(os.path.exists(home + b'/.cache/specwright/feedback'))
        self.assertFalse(self.record_path().exists())

    @unittest.skipIf(os.name == 'nt', 'platform: raw POSIX process environment is unavailable on Windows')
    def test_raw_posix_home_keeps_the_record_location(self):
        home = self.raw_root(b'raw-home')
        for index, state in enumerate((None, b'')):
            change = f'raw-home-{index}'
            environment = self.raw_environment(state=state, home=home)
            args = [*self.common(), '--change', change]
            expected = home + b'/.cache/specwright/feedback/' + original.record_key(original.CODE, change).encode()
            os.makedirs(os.path.dirname(expected), exist_ok=True)
            record = {**self.intent([]), 'version': 2, 'change': change, 'code_repo': original.CODE,
                      'owner': {'id': 'old', 'at': original.T0, 'checkout': str(self.code), 'host': 'fixture'},
                      'written_at': original.T0, 'marker': None,
                      'heads': {'code': self.tip(self.code), 'store': self.tip(self.store)}}
            with open(expected, 'wb') as output:
                output.write(json.dumps(record).encode('utf-8'))
            adopted = self.raw_pp(['pass', 'adopt', *args, '--owner', 'native', '--from', 'old'], environment)
            self.assertEqual(os.fsencode(adopted['path']), expected)
            self.assertTrue(os.path.isfile(expected))
            adopted = self.raw_pp(['pass', 'adopt', *args, '--owner', 'frozen', '--from', 'native'], environment, 'frozen')
            self.assertEqual(os.fsencode(adopted['path']), expected)
            before = Path(os.fsdecode(expected)).read_bytes()
            for which in ('native', 'frozen'):
                refused = self.raw_pp(['pass', 'done', *args, '--owner', 'native'], environment, which, expect=1)
                self.assertEqual(refused['error'], 'not_owner')
                self.assertEqual(refused['owner']['id'], 'frozen')
                self.assertEqual(Path(os.fsdecode(expected)).read_bytes(), before)

    @unittest.skipIf(os.name == 'nt', 'platform: raw POSIX process environment is unavailable on Windows')
    def test_process_state_override_does_not_need_a_home(self):
        root = self.raw_root(b'no-home-state')
        environment = self.raw_environment(state=root)
        self.assertNotIn(b'HOME', environment)
        intent = self.write_json('raw-intent.json', self.intent([]))
        written = self.raw_pp(['pass', 'write', *self.common(), '--intent', intent], environment)
        expected = root + b'/feedback/' + original.record_key(original.CODE, original.CHANGE).encode()
        self.assertTrue(os.path.isfile(expected))
        self.assertEqual(os.fsencode(written['path']), expected)
        frozen = self.raw_pp(['pass', 'plan', *self.common()], environment, 'frozen')
        self.assertTrue(frozen['record'])
        self.assertEqual(os.fsencode(frozen['path']), expected)

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
    def test_first_seen_read_follows_the_raw_state_directory(self):
        root = self.raw_root(b'first-seen-state')
        environment = self.raw_environment(state=root, home=os.fsencode(self.tmp / 'unused-home'))
        intent = self.write_json('raw-intent.json', self.intent([self.finding()]))
        written = self.raw_pp(['pass', 'write', *self.common(), '--intent', intent], environment)
        self.fix_store()
        self.push_all()
        head = self.tip(self.store)
        path = root + b'/heads/' + original.STORE.lower().encode() + b'/3/' + head.encode()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as output:
            output.write(b'Thu, 08 Oct 2026 12:00:00 GMT\n')
        self.seed_pulls(original.STORE, [])
        self.add_comment(original.STORE, 3, '@codex review', 'KintsugiBot', 2001, created_at='2026-10-08T12:05:00Z')
        args = ['pass', 'plan', *self.common(), '--owner', written['owner'],
                *self.snapshots(original.snap(threads=[original.thread()]))]
        for which in ('native', 'frozen'):
            row = self.row(self.raw_pp(args, environment, which), 'rerequest', 'store')
            self.assertEqual((row['cutoff_source'], row['cutoff'], row['state']),
                             ('first_seen', '2026-10-08T12:00:00Z', 'done'))
    def snapshots(self, snapshot=None):
        return ["--snapshot", f"code={self.write_json('code-snap.json', snapshot or original.snap())}",
                "--snapshot", f"store={self.write_json('store-snap.json', original.snap())}"]

    def compare_plan(self, snapshot=None):
        args = ["pass", "plan", *self.common(), "--owner", self.owner, *self.snapshots(snapshot)]
        before = self.gh_state.read_bytes()
        native = self.pp(*args)
        native_calls = parity.calls_of(self.gh_log, lambda call: call["argv"])
        self.gh_state.write_bytes(before)
        frozen = self.pp(*args, which="frozen")
        frozen_calls = parity.calls_of(self.gh_log, lambda call: call["argv"])
        self.assertEqual(native, frozen)
        self.assertEqual(native_calls, frozen_calls)
        return native

    def test_native_plan_resumes_an_existing_record(self):
        intent = self.write_json("intent.json", self.intent([self.finding()]))
        written = self.pp("pass", "write", *self.common(), "--intent", intent, which="frozen")
        self.owner = written["owner"]
        result = self.compare_plan(original.snap(threads=[original.thread()]))
        self.assertEqual((result["status"], result["round"], result["new_pass_allowed"]), ("resume", 2, False))
        self.assertEqual(self.row(result, "fix_commit", "store")["action"], "finish_edits")

    def test_script_plan_reads_a_native_record(self):
        self.write_record([self.finding()])
        raw = self.record_path().read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertEqual(json.loads(raw)["version"], 2)
        self.compare_plan(original.snap(threads=[original.thread()]))
        self.assertEqual(self.record_path().read_bytes(), raw)

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
        barrier = threading.Barrier(6)
        results = []
        def adopt(index):
            barrier.wait()
            results.append(self.command(["pass", "adopt", *self.common(), "--owner", f"new-{index}", "--from", self.owner]))
        workers = [threading.Thread(target=adopt, args=(i,)) for i in range(6)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(timeout=120)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        docs = [json.loads(result.stdout) for result in results]
        self.assertEqual(sum(doc["ok"] for doc in docs), 1)
        self.assertTrue(all(doc.get("error") in ("record_busy", "not_owner") for doc in docs if not doc["ok"]))
        self.assertFalse(Path(str(self.record_path()) + ".lock").exists())

    def test_done_replans_under_its_lock_and_blocks_concurrent_adoption(self):
        self.settings("github:\n  login: KintsugiBot\npr:\n  react: false\n")
        self.write_record([self.finding(dest="code", react=None)])
        self.fix_code()
        self.push_all()
        held, release = self.tmp / "done-held", self.tmp / "done-release"
        lock = Path(str(self.record_path()) + ".lock")
        real_git = original.fixtures.posix(shutil.which("git"))
        tool = self.tmp / "bin" / "git"
        tool.write_text('#!/bin/bash\n'
            'if [ "$1" = show-ref ] && [ -f "$WF_RECORD_LOCK" ]; then\n'
            '  : > "$WF_DONE_HELD"\n'
            '  while [ ! -e "$WF_DONE_RELEASE" ]; do sleep 0.05; done\n'
            'fi\n'
            f'exec "{real_git}" "$@"\n', encoding="utf-8", newline="\n")
        tool.chmod(0o755)
        fakeexe.add_launcher(tool, exe=True)  # sw starts it by PATHEXT name on Windows (D9)
        self.extra_env.update(WF_RECORD_LOCK=lock.as_posix(), WF_DONE_HELD=held.as_posix(),
                              WF_DONE_RELEASE=release.as_posix())
        results = []
        args = ["pass", "done", *self.common(), "--owner", self.owner, *self.snapshots(original.snap(threads=[]))]
        worker = threading.Thread(target=lambda: results.append(self.command(args)))
        worker.start()
        try:
            end = time.monotonic() + 20
            while not held.exists() and time.monotonic() < end: time.sleep(0.05)
            self.assertTrue(held.exists(), "done did not replan while holding its native lock")
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

    def test_frozen_script_refuses_a_native_lock_file(self):
        self.write_record([self.finding()])
        raw = self.record_path().read_bytes()
        lock = Path(str(self.record_path()) + ".lock")
        lock.write_bytes(b"native holder")
        for operation, extra in [("adopt", ["--from", self.owner]), ("done", self.snapshots())]:
            doc = self.pp("pass", operation, *self.common(), "--owner", self.owner, *extra, which="frozen", expect=1)
            self.assertEqual(doc["error"], "record_busy")
            self.assertEqual(lock.read_bytes(), b"native holder")
            self.assertEqual(self.record_path().read_bytes(), raw)

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
                file = self.write_json("bad-snapshot.json", snapshot)
                args = ["pass", "plan", *self.common(), "--snapshot", f"code={file}"]
                frozen = self.pp(*args, which="frozen", expect=1)
                self.assertEqual(frozen["error"], "internal_error")
                native = self.pp(*args, expect=1)
                self.assertEqual(native["error"], "internal_error")
                self.assertEqual(self.record_path().read_bytes(), before)


# Exercise existing behavioural assertions through the native command boundary.
# The frozen script remains the independent read/write oracle above.
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
