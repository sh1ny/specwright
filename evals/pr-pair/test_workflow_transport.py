"""Command-boundary transport checks; no GitHub network is used."""
import json
import os
import shutil
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_workflow_parity as wp
from test_bounded import pid_alive


class WorkflowTransport(wp.WorkflowParity):
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
        written = self.side('new', ['pass', 'write', *common, '--intent', intent], self.tmp)
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
        self.extra_env.update(WF_FENCE_START=started.as_posix(), WF_CHILD_PID=child_pid.as_posix(),
                              WF_FENCE_DIR=code, SPECWRIGHT_NET_DEADLINE='8')
        try:
            result = self.side('new', ['pass', 'plan', *common, '--owner', json.loads(written['stdout'])['owner'],
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
        self.extra_env.update(WF_SHA=sha)
        return code, store

    def native_rounds(self, code, store=None):
        args = ['rounds', '--code', code, '--branch', 'feat/x']
        if store:
            args += ['--store', store]
        result = self.side('new', args, self.tmp)
        return result, json.loads(result['stdout'])

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
        native = self.side('new', args, self.tmp)
        self.assertTrue(fetch_args.exists(), native)
        native_fetch = fetch_args.read_bytes()
        oracle = self.side('old', args, self.tmp)
        oracle_fetch = fetch_args.read_bytes()
        self.assertEqual(self.normal(native)[0], self.normal(oracle)[0])
        self.assertEqual(native_fetch, oracle_fetch)
        self.assertEqual(oracle_fetch.split(b'\0')[:-1],
                         [b'fetch', b'-q', b'--refmap=', b'origin', b'refs/heads/feat/x'])


for _name in dir(wp.WorkflowParity):
    if _name.startswith('test_') and _name not in WorkflowTransport.__dict__:
        setattr(WorkflowTransport, _name, None)
