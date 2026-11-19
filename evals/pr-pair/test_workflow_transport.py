"""Command-boundary transport checks; no GitHub network is used."""
import json
import os
import shutil
import shlex
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vcs'))
import sentinels
import fakeexe  # sentinels puts evals/ on sys.path
import oracle_capture
import test_workflow_parity as wp


def pid_alive(pid):
    """Whether a process still runs (a zombie an unreaping parent has not collected is stopped all the same)."""
    if os.name == 'nt':
        out = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout
        return f'"{pid}"' in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z'
    except (OSError, IndexError):
        return not subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip().startswith('Z')


class WorkflowTransport(wp.WorkflowParity):
    def native_document(self, args, cwd=None):
        result = self.side(args, cwd or self.tmp)
        self.assertTrue(result['stdout'], result)
        return result, json.loads(result['stdout'])

    def test_internal_scripts_are_not_launched(self):
        code, store = self.merged_pair()
        # The shared sentinels: failing python/python3 first on PATH (the fake gh and Git shims follow).
        shared = sentinels.install(self.tmp / 'failing-python', self.tmp / 'launched-python')
        sentinel_log = shared.log
        self.extra_env.update(shared.env)
        self.extra_env['PATH'] = os.pathsep.join([str(shared.bin), str(self.tmp / 'bin'), os.environ.get('PATH', '')])
        shared.probe(self, self.env('me'))
        self.mutate(lambda st: st['repos'][self.SLUG].update(pulls=[]))
        result, doc = self.native_document(['cleanup-plan', '--code', code, '--store', store, '--branch', 'feat/x'])
        self.assertEqual(result['code'], 0, doc)
        self.assertEqual(doc['code']['commands'][-1]['cmd'], ['git', 'branch', '-d', 'feat/x'])
        self.assertNotIn(b'unexpected-interpreter', result['stderr'])
        self.assertFalse(sentinel_log.exists())

        def restore_code_pr(st):
            pull = wp.copy.deepcopy(st['repos']['o/plans']['pulls'][0])
            pull['head']['repo']['full_name'] = self.SLUG
            st['repos'][self.SLUG]['pulls'] = [pull]
        self.mutate(restore_code_pr)
        self.select_backend(code, store, 'jj')
        result, doc = self.native_document(['cleanup-plan', '--code', code, '--store', store, '--branch', 'feat/x'])
        self.assertEqual(result['code'], 0, doc)
        self.assertEqual(doc['code']['commands'][0]['cmd'][3:5], ['vcs', 'switch'])
        self.assertFalse(sentinel_log.exists())

        self.git(code, 'commit', '--allow-empty', '-m', 'fix\n\nFeedback-Round: 1')
        self.extra_env['WF_SHA'] = self.git(code, 'rev-parse', 'HEAD')
        reads = self.tmp / 'fenced-git-reads'
        self.extra_env['WF_READ_LOG'] = reads.as_posix()
        real = shutil.which('git').replace('\\', '/')
        tool = self.tmp / 'bin' / 'git'
        tool.write_text('#!/bin/sh\nif [ "$1" = ls-remote ]; then\n'
                        'here=$PWD; if command -v cygpath >/dev/null 2>&1; then here=$(cygpath -m "$PWD"); fi\n'
                        'printf "%s\\n" "$here" >> "$WF_READ_LOG"\n'
                        'printf "%s\\n" "$WF_SHA"; exit 0\nfi\nexec '+shlex.quote(real)+' "$@"\n',
                        encoding='utf-8', newline='\n')
        tool.chmod(0o755)
        fakeexe.add_launcher(tool, exe=True)  # sw starts it by PATHEXT name on Windows (D9)
        result, doc = self.native_rounds(code)
        self.assertEqual(result['code'], 0, doc)
        self.assertEqual(doc['rounds'], 1)
        self.assertEqual(doc['remote_unreadable'], [])
        self.assertEqual(Path(reads.read_text().strip()).resolve(), Path(code).resolve())
        self.assertTrue(any(call['argv'][:2] == ['auth', 'token'] and
                            '--hostname' in call['argv'] and
                            Path(call['cwd']).resolve() == Path(code).resolve()
                            for call in result['raw_calls']))
        self.assertFalse(sentinel_log.exists())

    def printed_plan(self, code, store):
        result, doc = self.native_document(['cleanup-plan', '--code', code, '--store', store, '--branch', 'feat/x'])
        self.assertEqual(result['code'], 0, doc)
        return doc

    def assert_names_running_sw(self, argv, code):
        """The command starts with the running sw's absolute path and `--project <code>`."""
        self.assertTrue(Path(argv[0]).is_absolute(), argv)
        self.assertEqual(Path(argv[0]).resolve(), Path(os.environ['SPECWRIGHT_SW']).resolve(), argv)
        self.assertEqual(argv[1], '--project', argv)
        self.assertEqual(Path(argv[2]).resolve(), Path(code).resolve(), argv)

    def test_cleanup_plan_names_running_sw(self):
        code, store = self.merged_pair()
        plan = self.printed_plan(code, store)
        for side, login in [('code', 'me'), ('store', 'other')]:
            commands = plan[side]['commands']
            self.assertEqual(commands[0]['cmd'], ['git', 'checkout', 'main'])
            pull, check = commands[1]['cmd'], commands[2]['cmd']
            self.assert_names_running_sw(pull, code)
            self.assertEqual(pull[3:], ['as', login, 'git', 'pull', '--ff-only'])
            self.assert_names_running_sw(check, code)
            self.assertEqual(check[3:5], ['pr', 'branch-check'])
            for entry in commands:
                self.assertFalse([x for x in entry['cmd'] if x == 'bash' or x.endswith(('.sh', '.py'))], entry)
        self.select_backend(code, store, 'jj')  # the vcs plans name the running sw as well
        plan = self.printed_plan(code, store)
        for argv in (plan['code']['commands'][0]['cmd'], plan['code']['commands'][1]['cmd'], plan['code']['delete']):
            self.assert_names_running_sw(argv, code)
            self.assertEqual(argv[3], 'vcs', argv)
            self.assertFalse([x for x in argv if x == 'bash' or x.endswith('.sh')], argv)

    def test_store_cleanup_names_code_project(self):
        code, store = self.merged_pair()
        plan = self.printed_plan(code, store)
        self.assertEqual(Path(plan['store']['dir']).resolve(), Path(store).resolve())
        for entry in plan['store']['commands'][1:]:
            self.assert_names_running_sw(entry['cmd'], code)
            self.assertNotEqual(Path(entry['cmd'][2]).resolve(), Path(store).resolve(), 'the project is the code checkout')
            self.assertEqual(Path(entry['cwd']).resolve(), Path(store).resolve(), 'the command runs in the store')
        self.assertEqual(plan['store']['commands'][1]['cmd'][3:], ['as', 'other', 'git', 'pull', '--ff-only'])

    def test_printed_cleanup_runs_from_store(self):
        code, store = self.merged_pair()
        plan = self.printed_plan(code, store)
        (Path(store) / 'openspec' / '.specwright' / 'VERSION').unlink()
        checkout, _, check = plan['store']['commands']
        env = self.env('me', SPECWRIGHT_HOME=str(self.home), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        done = subprocess.run(checkout['cmd'], cwd=checkout['cwd'], env=env, capture_output=True, timeout=120)
        self.assertEqual(done.returncode, 0, (done.stdout, done.stderr))
        done = subprocess.run(check['cmd'], cwd=check['cwd'], env=env, capture_output=True, timeout=120)
        self.assertEqual(done.returncode, 0, (done.stdout, done.stderr))
        doc = json.loads(done.stdout)
        self.assertNotEqual(doc.get('error'), 'sw_mismatch', doc)
        self.assertTrue(doc['delete'], doc)

    def unfenced_pass_limits(self, github):
        code, _ = self.setup_remote(github=github)
        self.git(code, 'add', 'openspec/specwright.yaml')
        self.git(code, 'commit', '-m', 'settings before the pass')
        intent = self.tmp / 'unfenced-intent.json'
        intent.write_text(json.dumps({'branch': 'feat/x', 'round': 1,
            'prs': {'code': {'repo': self.SLUG, 'number': 7}}, 'findings': [{
                'id': 'F1', 'item': 'T1', 'source': 'code', 'destination': 'code', 'root_id': 11,
                'edits': [{'file': 'fix.txt', 'contains': ['done']}],
                'disposition': {'react': None, 'resolve': False}, 'revision': {'rev': 'old'}}]}), encoding='utf-8')
        common = ['--code', code, '--code-repo', self.SLUG, '--change', 'unfenced-limits']
        result, written = self.native_document(['pass', 'write', *common, '--intent', intent])
        self.assertEqual(result['code'], 0, written)
        record = Path(written['path'])
        before = record.read_bytes()
        (Path(code) / 'fix.txt').write_text('done\n', encoding='utf-8')
        self.git(code, 'add', 'fix.txt')
        self.git(code, 'commit', '-m', 'fix\n\nFeedback-Round: 1')
        head = self.git(code, 'rev-parse', 'HEAD')
        snapshot = self.tmp / 'unfenced-snapshot.json'
        snapshot.write_text(json.dumps({'viewer': 'me', 'threads': []}), encoding='utf-8')
        reached = self.tmp / 'unfenced-read'
        real = shutil.which('git').replace('\\', '/')
        python = wp.parity.fixtures.posix(sys.executable)
        tool = self.tmp / 'bin' / 'git'
        tool.write_text('#!/bin/sh\n'
            'if [ "$1" = "$WF_LIMIT_PHASE" ]; then\n'
            '  here=$PWD; if command -v cygpath >/dev/null 2>&1; then here=$(cygpath -m "$PWD"); fi\n'
            '  printf "%s|%s\\n" "$1" "$here" >> "$WF_REACHED"\n'
            '  if [ "$WF_LIMIT_KIND" = deadline ]; then sleep 3; else\n'
            '    '+shlex.quote(python)+' -c "print(\'x\' * 8192)"\n'
            '  fi\n  exit 0\nfi\n'
            'if [ "$1" = ls-remote ]; then printf "%s\\n" "$WF_REMOTE_SHA"; exit 0; fi\n'
            'exec '+shlex.quote(real)+' "$@"\n', encoding='utf-8', newline='\n')
        tool.chmod(0o755)
        fakeexe.add_launcher(tool, exe=True)  # sw starts it by PATHEXT name on Windows (D9)
        cwd = code if github else self.tmp
        for phase in ['ls-remote', 'fetch']:
            for kind, error in [('deadline', 'deadline_exceeded'), ('bytes', 'response_too_large')]:
                with self.subTest(phase=phase, kind=kind):
                    reached.unlink(missing_ok=True)
                    self.extra_env.update(WF_LIMIT_PHASE=phase, WF_LIMIT_KIND=kind,
                        WF_REACHED=reached.as_posix(), WF_REMOTE_SHA='b'*40 if phase == 'fetch' else head,
                        SPECWRIGHT_NET_DEADLINE='2', SPECWRIGHT_NET_MAX_BYTES='1024')
                    result, doc = self.native_document(['pass', 'plan', *common, '--owner', written['owner'],
                                                       '--snapshot', f'code={snapshot}'], cwd=cwd)
                    self.assertTrue(reached.exists(), result)
                    operation, directory = reached.read_text().strip().split('|')
                    self.assertEqual(operation, phase)
                    self.assertEqual(Path(directory).resolve(), Path(code).resolve())
                    self.assertEqual((result['code'], doc.get('error'), doc.get('unknown')), (3, error, True), doc)
                    self.assertEqual(record.read_bytes(), before)
                    self.assertEqual(self.git(code, 'rev-parse', 'HEAD'), head)
        self.extra_env.update(WF_LIMIT_PHASE='ls-remote', WF_LIMIT_KIND='deadline')
        result, doc = self.native_document(['rounds', '--code', code, '--branch', 'feat/x'], cwd=cwd)
        self.assertEqual(result['code'], 0, doc)
        self.assertEqual(doc['remote_unreadable'], ['code'])

    def test_started_repository_preserves_git_network_limits(self):
        self.unfenced_pass_limits(github=True)

    def test_non_github_repository_preserves_git_network_limits(self):
        self.unfenced_pass_limits(github=False)

    def test_direct_vcs_failures_retain_wrapper_mapping(self):
        code, store = self.merged_pair()
        self.select_backend(code, store, 'gitbutler')
        self.mutate(lambda st: st['repos'][self.SLUG]['pulls'][0].update(merge_commit_sha='bad-proof'))
        result, doc = self.native_document(['cleanup-plan', '--code', code, '--store', store, '--branch', 'feat/x'])
        self.assertEqual(result['code'], 1, result)
        self.assertEqual(doc['error'], 'usage')
        self.assertIn('--merged-commit', doc['message'])

    def test_unbounded_vcs_calls_remain_unbounded(self):
        code, store = self.merged_pair()
        self.extra_env['SPECWRIGHT_NET_DEADLINE'] = '2'
        delayed = self.tmp / 'delayed-vcs-calls'
        self.extra_env['WF_VCS_DELAY_LOG'] = delayed.as_posix()
        real = shutil.which('git').replace('\\', '/')
        script = self.tmp / 'bin' / 'git'
        script.write_text('#!/bin/sh\nif [ "$1" = status ]; then echo git-state >> "$WF_VCS_DELAY_LOG"; sleep 3; fi\nexec '+shlex.quote(real)+' "$@"\n', encoding='utf-8')
        script.chmod(0o755)
        fakeexe.add_launcher(script, exe=True)  # sw starts it by PATHEXT name on Windows (D9)
        self.mutate(lambda st: st['repos'][self.SLUG].update(pulls=[]))
        result, doc = self.native_document(['cleanup-plan', '--code', code, '--store', store, '--branch', 'feat/x'])
        self.assertEqual(result['code'], 0, doc)
        self.assertIn('git-state', delayed.read_text().splitlines())
        delayed.unlink()
        self.select_backend(code, store, 'jj')
        jj = self.tmp / 'bin' / 'jj'
        jj.write_text(jj.read_text().replace('case ', 'echo jj-plan >> "$WF_VCS_DELAY_LOG"\nsleep 3\ncase ', 1), encoding='utf-8')
        def restore_code_pr(st):
            pull = wp.copy.deepcopy(st['repos']['o/plans']['pulls'][0])
            pull['head']['repo']['full_name'] = self.SLUG
            st['repos'][self.SLUG]['pulls'] = [pull]
        self.mutate(restore_code_pr)
        result, doc = self.native_document(['cleanup-plan', '--code', code, '--store', store, '--branch', 'feat/x'])
        self.assertEqual(result['code'], 0, doc)
        self.assertIn('jj-plan', delayed.read_text().splitlines())

    def test_nested_vcs_fetch_runs_the_fence_in_process(self):
        code, store = self.pair_repos()
        self.select_backend(code, store, 'jj', role='store', logins=False)
        (Path(store) / 'openspec' / '.specwright' / 'VERSION').unlink()
        real = shutil.which('git').replace('\\', '/')
        fetch = self.tmp / 'fetch-calls'
        shim = self.tmp / 'bin' / 'git'
        shim.write_text('#!/bin/sh\nif [ "$1" = fetch ]; then\n'
            ' target="$PWD"; if command -v cygpath >/dev/null 2>&1; then target=$(cygpath -m "$PWD"); fi\n'
            ' printf "%s|%s\\n" "$target" "${GH_TOKEN-unset}" >> "$WF_FETCH_LOG"\n'
            ' printf "%s\\n" "$WF_SHA" > "$WF_FETCH_HEAD"; exit 0\nfi\nexec '+shlex.quote(real)+' "$@"\n', encoding='utf-8')
        shim.chmod(0o755)
        fakeexe.add_launcher(shim, exe=True)  # sw starts it by PATHEXT name on Windows (D9)
        sentinel = sentinels.install(self.tmp / 'fetch-bin', self.tmp / 'fetch-sentinel-log')
        self.extra_env.update(sentinel.env, WF_FETCH_LOG=fetch.as_posix(),
            WF_SHA=self.git(store, 'rev-parse', 'HEAD'), WF_FETCH_HEAD=str(Path(store) / '.git' / 'FETCH_HEAD'))
        sentinel.probe(self, self.env('me'))
        for login in [None, 'other']:
            with self.subTest(login=login):
                fetch.unlink(missing_ok=True)
                args = ['branch-check', '--dir', store, '--branch', 'feat/x', '--main', 'main',
                        '--code', 'code', '--role', 'store']
                if login:
                    args += ['--login', login]
                result, doc = self.native_document(args, cwd=self.tmp)
                self.assertEqual(result['code'], 0, doc)
                self.assertNotEqual(doc.get('error'), 'sw_missing', doc)
                self.assertTrue(doc['delete'], doc)
                self.assertEqual(sentinel.recorded(), [])
                target, token = fetch.read_text().strip().split('|')
                self.assertEqual(Path(target).resolve(), Path(store).resolve())
                self.assertEqual(token, 'tok-other' if login else 'tok-me')

    def test_fenced_read_uses_one_deadline(self):
        code, store = self.setup_remote(github=True)
        self.git(code, 'add', 'openspec/specwright.yaml')
        self.git(code, 'commit', '-m', 'settings before the pass')
        intent = self.tmp / "intent.json"
        intent.write_text(json.dumps({"branch": "feat/x", "round": 1,
            "prs": {"code": {"repo": self.SLUG, "number": 7}}, "findings": [{
                "id": "F1", "item": "T1", "source": "code", "destination": "code", "root_id": 11,
                "edits": [{"file": "fix.txt", "contains": ["done"]}],
                "disposition": {"react": None, "resolve": False}, "revision": {"rev": "old"}}]}), encoding="utf-8")
        common = ['--code', code, '--store', store, '--code-repo', self.SLUG, '--change', 'deadline']
        written = self.side(['pass', 'write', *common, '--intent', intent], self.tmp)
        self.assertEqual(written['code'], 0, written)
        (Path(code) / 'fix.txt').write_text('done\n', encoding='utf-8')
        self.git(code, 'add', 'fix.txt')
        self.git(code, 'commit', '-m', 'fix\n\nFeedback-Round: 1')
        snapshot = self.tmp / 'snapshot.json'
        snapshot.write_text(json.dumps({'viewer': 'me', 'threads': []}), encoding='utf-8')
        started, child_pid = self.tmp / 'fence-start', self.tmp / 'child-pid'
        hanging = self.tmp / 'hung-git.py'
        hanging.write_text('import os, pathlib, subprocess, sys, time\n'
            'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])\n'
            'pathlib.Path(os.environ["WF_CHILD_PID"]).write_text(str(child.pid))\n'
            'time.sleep(60)\n', encoding='utf-8')
        python = wp.parity.fixtures.posix(sys.executable)
        tool = self.tmp / 'bin' / 'git'
        tool.write_text(tool.read_text(encoding='utf-8').replace('if [ "$1" = ls-remote ]; then',
            f'if [ "$1" = ls-remote ]; then exec "{python}" "{hanging.as_posix()}"; fi\n'
            'if [ "$1" = ls-remote ]; then'), encoding='utf-8', newline='\n')
        gh = self.tmp / 'bin' / 'gh'
        real = gh.with_name('gh-real')
        gh.rename(real)
        gh.write_text('#!/bin/bash\n'
            'if [ "$1" = auth ] && [ "${2:-}" = token ] && [ "${3:-}" = --hostname ]; then\n'
            f'  "{python}" -c \'import os,pathlib,time; target=pathlib.Path(os.environ["WF_FENCE_DIR"]); inside=pathlib.Path.cwd()==target; pathlib.Path(os.environ["WF_FENCE_START"]).write_text(str(time.monotonic())) if inside else None; time.sleep(1.5) if inside else None\'\n'
            'fi\n'
            f'exec "{real.as_posix()}" "$@"\n', encoding='utf-8', newline='\n')
        gh.chmod(0o755)
        fakeexe.add_launcher(gh, exe=True)  # sw starts it by PATHEXT name on Windows (D9)
        self.extra_env.update(WF_FENCE_START=started.as_posix(), WF_CHILD_PID=child_pid.as_posix(),
                              WF_FENCE_DIR=code, SPECWRIGHT_NET_DEADLINE='8')
        try:
            result = self.side(['pass', 'plan', *common, '--owner', json.loads(written['stdout'])['owner'],
                                      '--snapshot', f'code={snapshot}'], self.tmp)
            doc = json.loads(result['stdout'])
            self.assertEqual(result['code'], 3, result)
            self.assertEqual((doc['error'], doc['unknown']), ('deadline_exceeded', True), result)
            # Historical token_for preflight runs from the caller before net.
            # Only the later target-cwd fence lookup shares the launch budget.
            credentials = [call for call in result['raw_calls'] if
                           call['argv'][:2] == ['auth', 'token'] and '--hostname' in call['argv']]
            self.assertTrue(any(Path(call['cwd']).resolve() == self.tmp.resolve() for call in credentials))
            self.assertTrue(any(Path(call['cwd']).resolve() == Path(code).resolve() for call in credentials))
            self.assertTrue(started.exists(), 'the delayed credential check was not reached')
            self.assertLess(time.monotonic() - float(started.read_text()), 8.8,
                            'the launched command received a fresh deadline after credential checks')
            self.assertTrue(child_pid.exists(), 'the bounded Git command did not start its descendant')
            pid = int(child_pid.read_text())
            end = time.monotonic() + 3
            while pid_alive(pid) and time.monotonic() < end: time.sleep(0.05)
            self.assertFalse(pid_alive(pid), 'the hung descendant survived the caller deadline')
        finally:
            if child_pid.exists():
                pid = int(child_pid.read_text())
                if pid_alive(pid): os.kill(pid, signal.SIGTERM)

    def setup_remote(self, github=False):
        code, store = self.pair_repos()
        if not github:
            self.git(code, 'remote', 'set-url', 'origin', str(self.tmp / 'local.git'))
        sha = self.git(code, 'commit', '--allow-empty', '-m', 'fix\n\nFeedback-Round: 1')
        sha = self.git(code, 'rev-parse', 'HEAD')
        real = shutil.which('git').replace('\\', '/')
        tool = self.tmp / 'bin' / 'git'
        tool.write_text('#!/bin/bash\n'
            'if [ "$1" = ls-remote ]; then\n'
            '  if [ -n "${WF_ENV_FILE:-}" ]; then printf "%s|%s|%s" "${GH_TOKEN-unset}" "${GIT_SSH_COMMAND-unset}" "${GH_HOST-unset}" > "$WF_ENV_FILE"; fi\n'
            '  [ "${WF_DELAY:-}" = yes ] && sleep 3\n'
            '  printf "%s\\n" "${WF_SHA}"; exit 0\n'
            'fi\n'
            f'exec "{real}" "$@"\n', encoding='utf-8', newline='\n')
        tool.chmod(0o755)
        fakeexe.add_launcher(tool, exe=True)  # sw starts it by PATHEXT name on Windows (D9)
        self.extra_env.update(WF_SHA=sha)
        return code, store

    def native_rounds(self, code, store=None):
        args = ['rounds', '--code', code, '--branch', 'feat/x']
        if store:
            args += ['--store', store]
        result = self.side(args, self.tmp)
        return result, json.loads(result['stdout'])

    @unittest.skipUnless(sys.platform.startswith('linux'), 'platform: a file name that is not UTF-8 needs a Linux file system')
    def test_non_utf8_path_argument_is_refused(self):
        code, _ = self.setup_remote(github=True)
        raw = os.fsencode(code) + b'-\xff'
        os.mkdir(raw)
        e = self.env('me', SPECWRIGHT_HOME=str(self.home), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        before = len(wp.parity.calls_of(self.gh_log, lambda c: c))
        r = wp.swcall.run(['pr', 'rounds', '--code', raw, '--branch', 'feat/x'], cwd=self.tmp, env=e, timeout=120, text=False)
        self.assertNotEqual(r.returncode, 0, (r.stdout, r.stderr))
        self.assertEqual(r.stdout, b'')
        self.assertEqual(len(wp.parity.calls_of(self.gh_log, lambda c: c)), before, 'a credential lookup or a fenced tool ran')
        # the control: the same fixture with a valid argument does reach the tool
        control = wp.swcall.run(['pr', 'rounds', '--code', code, '--branch', 'feat/x'], cwd=self.tmp, env=e, timeout=120, text=False)
        self.assertEqual(control.returncode, 0, (control.stdout, control.stderr))
        self.assertGreater(len(wp.parity.calls_of(self.gh_log, lambda c: c)), before, 'the valid call never reached gh')

    def test_rounds_reports_an_outer_read_deadline_as_unreadable(self):
        code, _ = self.setup_remote()
        self.extra_env.update(WF_DELAY='yes', SPECWRIGHT_NET_DEADLINE='0.3')
        result, doc = self.native_rounds(code)
        self.assertEqual(result['code'], 0, result)
        self.assertEqual(doc['remote_unreadable'], ['code'])
        self.assertEqual(doc['rounds'], 1)

    def test_nested_fence_lookup_limit_retains_refusal_mapping(self):
        code, _ = self.setup_remote(github=True)
        self.extra_env['SPECWRIGHT_NET_MAX_BYTES'] = '1024'
        self.mutate(lambda st: st.update(flood=[{'match': 'auth token --help', 'bytes': 4096}]))
        self.run_pair('rounds', '--code', code, '--branch', 'feat/x', code=3)
        result, doc = self.native_rounds(code)
        self.assertEqual(result['code'], 3, result)
        self.assertEqual(doc['error'], 'fence_refused')
        self.assertNotIn('tok-me', json.dumps(doc))

    def test_another_repository_is_checked_under_its_own_identity(self):
        code, store = self.setup_remote()
        self.git(store, 'commit', '--allow-empty', '-m', 'fix\n\nFeedback-Round: 1')
        result, doc = self.native_rounds(code, store)
        self.assertEqual(result['code'], 0, result)
        calls = result['raw_calls']
        inside = [c for c in calls if c['argv'][:2] == ['auth', 'token'] and
                  Path(c['cwd']).resolve() == Path(store).resolve()]
        self.assertTrue(inside)
        self.assertEqual({c['argv'][-1] for c in inside if '--user' in c['argv']}, {'other'})

    def test_non_github_transport_restores_the_original_environment(self):
        code, _ = self.setup_remote()
        out = self.tmp / 'original-env'
        self.extra_env.update(WF_ENV_FILE=out.as_posix(),
            AS_SH_ORIG_SET=' GIT_SSH_COMMAND GH_HOST',
            AS_SH_ORIG_GIT_SSH_COMMAND='user ssh', AS_SH_ORIG_GH_HOST='enterprise.example',
            GIT_SSH_COMMAND='blocked by fence')
        result, doc = self.native_rounds(code)
        self.assertEqual(result['code'], 0, result)
        self.assertEqual(out.read_text(), 'unset|user ssh|enterprise.example')

    def test_command_arguments_remain_exact(self):
        branch = 'feat/$x;é[quoted]'
        d = self.run_pair('discover', '--repo', self.SLUG, '--branch', branch, code=0)
        self.assertEqual(d['branch'], branch)
        # The same call again with a failing recording `bash` first on PATH: the native side starts no shell, so the recorder
        # never runs and the arguments reach gh unchanged.
        recorder_dir = self.tmp / 'failing-bash'
        recorder_dir.mkdir()
        log = self.tmp / 'failing-bash-log'
        for name in ('bash', 'sh'):  # bare-bash: not started (recorder names)
            fakeexe.write_fake(recorder_dir / name,
                               '#!/bin/sh\nprintf "%s\\n" ' + name + ' >> "$SW_SHELL_LOG"\nexit 1\n')
        self.extra_env.update(SW_SHELL_LOG=log.as_posix(),
                              PATH=os.pathsep.join([str(recorder_dir), str(self.tmp / 'bin'), os.environ.get('PATH', '')]))
        # the recorder must record, or the empty log below would hold for the wrong reason
        probe = subprocess.run([str(recorder_dir / ('bash.cmd' if os.name == 'nt' else 'bash'))],
                               env=self.env('me'), capture_output=True, timeout=30)
        self.assertEqual(probe.returncode, 1, probe)
        self.assertEqual(log.read_text(encoding='utf-8').splitlines(), ['bash'])  # bare-bash: not started (the recorder log)
        log.unlink()
        before = self.gh_state.read_bytes()
        native =self.side(['discover', '--repo', self.SLUG, '--branch', branch], None)
        self.gh_state.write_bytes(before)
        self.assertEqual(native['code'], 0, native)
        self.assertEqual(json.loads(native['stdout'])['branch'], branch)
        self.assertFalse(log.exists(), 'a shell ran: ' + log.read_text(encoding='utf-8') if log.exists() else '')

    def test_absolute_gitbutler_metadata_path_keeps_fetch_refmap_empty(self):
        code, _ = self.setup_remote()
        metadata = self.tmp / 'outside-code' / 'gitbutler'
        metadata.mkdir(parents=True)
        fetch_args = self.tmp / 'fetch-args'
        tool = self.tmp / 'bin' / 'git'
        text = tool.read_text(encoding='utf-8')
        text = text.replace('if [ "$1" = ls-remote ]; then',
            'if [ "$1" = rev-parse ] && [ "${2:-}" = --git-path ] && [ "${3:-}" = gitbutler ]; then\n'
            '  printf "%s\\n" "$WF_GITBUTLER"; exit 0\n'
            'fi\n'
            'if [ "$1" = fetch ]; then\n'
            '  printf "%s\\0" "$@" > "$WF_FETCH_ARGS"; exit 1\n'
            'fi\n'
            'if [ "$1" = ls-remote ]; then')
        tool.write_text(text, encoding='utf-8', newline='\n')
        self.extra_env.update(WF_GITBUTLER=metadata.as_posix(),
                              WF_FETCH_ARGS=fetch_args.as_posix(), WF_SHA='b'*40)
        args = ['rounds', '--code', code, '--branch', 'feat/x']
        native = self.side(args, self.tmp)
        self.assertTrue(fetch_args.exists(), native)
        native_fetch = fetch_args.read_bytes()
        # the record of the frozen run: the same document and the same fetch (the arguments it received were not recorded)
        oracle = oracle_capture.recorded(self)[0]
        paths, canon = oracle_capture.Paths(self), oracle_capture.canon
        self.assertEqual(native['code'], oracle['exit'])
        self.assertEqual(canon(paths.node(self.normal(native)[0])), canon(self.shape(oracle['stdout'], False)))
        self.assertEqual(native_fetch.split(b'\0')[:-1],
                         [b'fetch', b'-q', b'--refmap=', b'origin', b'refs/heads/feat/x'])


for _name in dir(wp.WorkflowParity):
    if _name.startswith('test_') and _name not in WorkflowTransport.__dict__:
        setattr(WorkflowTransport, _name, None)
