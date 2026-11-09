"""Workflow entries against the immutable test-only Python oracle."""
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_parity as parity
import vcs_test_support


def setUpModule():
    parity.setUpModule()


def tearDownModule():
    parity.tearDownModule()


class WorkflowParity(parity.PairParity):
    # C13: cleanup producers add --project only to printed as.sh/pr-pair.sh
    # calls. test_cleanup_plan_preserves_commands_and_project_selection checks
    # the full old plan with precisely those prefixes added; its consumers run
    # from each printed cwd. HTML5 table interpretation is owner-approved and
    # is covered by closing_test.dart's raw-table HTML5 boundary check.
    # test_printed_cleanup_commands_preserve_consumer_effects executes each
    # printed cwd/target and consumes the exact project prefix. Script helper
    # roots are bound only after their exact producer paths are asserted.
    # WorkflowPassMatrix consumes each record_exists path and reads the same
    # record before binding OS path separators; generated owner/time values
    # remain linked to the persisted owner and validated creation interval.
    # All other workflow fields/calls/effects compare without normalization.
    def git(self, directory, *args):
        return subprocess.run(['git', *args], cwd=directory, env=self.git_env,
                              capture_output=True, check=True).stdout.decode().strip()

    @staticmethod
    def command_binding(argv):
        # The random input filename is a bound generated value. The fake's
        # persisted comment body is still compared byte-for-byte by run_pair.
        out = parity.temp_names(argv)
        if '--input' in out:
            i = out.index('--input') + 1
            out[i] = '<generated-json-input>'
        return out

    def side(self, which, args, cwd):
        if which == 'old':
            # The frozen workflow calls VCS through its script directory.
            # Supply the existing native VCS shim beside its frozen helpers.
            helper = Path(parity.oracle_sw_dir()) / 'vcs.sh'
            if not helper.exists():
                shutil.copy2(parity.SCRIPTS / 'vcs.sh', helper)
            result = super().side(which, args, cwd)
            result['calls'] = [self.command_binding(c) for c in result['calls']]
            return result
        args = args(which) if callable(args) else args
        e = self.env('me', SPECWRIGHT_HOME=str(self.home),
                     GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        binary = os.environ['SPECWRIGHT_SW']
        payload = b''.join(str(x).encode('utf-8') + b'\0' for x in
                           [parity.fixtures.posix(getattr(self, 'workflow_scripts', parity.SCRIPTS)), parity.bashexe.bash(), *args[1:]])
        r = subprocess.run([str(binary), 'pr', args[0], '--args-stdin'], input=payload,
                           cwd=cwd or self.tmp, env=e, capture_output=True, timeout=120)
        raw_calls = parity.calls_of(self.gh_log, lambda c: c)
        result = {'code': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr,
                'calls': [self.command_binding(c['argv']) for c in raw_calls],
                'raw_calls': raw_calls,
                'state': self.gh_state.read_bytes()}
        self.last_native_calls = result['calls']
        return result

    def test_discover_filters_forks_bases_and_states(self):
        def seed(st):
            base = self._pull()
            items = []
            for n, repo, branch, target, state in [
                (8, 'fork/n', 'feat/x', 'main', 'open'),
                (9, self.SLUG, 'feat/x', 'other', 'open'),
                (10, self.SLUG.upper(), 'feat/x', 'main', 'closed'),
                (11, self.SLUG, 'different', 'main', 'open')]:
                p = copy.deepcopy(base)
                p.update(number=n, state=state, html_url=f'https://github.com/{self.SLUG}/pull/{n}')
                p['head'].update(ref=branch, repo={'full_name': repo})
                p['base']['ref'] = target
                items.append(p)
            st['repos'][self.SLUG]['pulls'] += items
        self.mutate(seed)
        d = self.run_pair('discover', '--repo', self.SLUG, '--branch', 'feat/x',
                          '--base', 'main', '--state', 'open', code=0)
        self.assertEqual([p['number'] for p in d['prs']], [7])
        self.assertEqual([p['number'] for p in d['other_base']], [9])

    def test_workflow_error_keeps_structured_values(self):
        body = self.body('body')
        d = self.run_pair('ensure-pr', '--repo', self.SLUG, '--branch', 'feat/x',
                          '--base', 'other', '--title', 'title', '--body-file', body, code=1)
        self.assertEqual(d['error'], 'wrong_base')
        self.assertEqual(d['base'], 'main')

    def test_ensure_found_created_and_already_merged(self):
        body = self.body('body')
        for branch in ['feat/x', 'feat/new']:
            self.run_pair('ensure-pr', '--repo', self.SLUG, '--branch', branch,
                          '--base', 'main', '--title', 'title', '--body-file', body, code=0)
        self.mutate(lambda st: st['repos'][self.SLUG]['pulls'][0].update(
            state='closed', merged_at='2026-10-10T12:00:00Z'))
        self.run_pair('ensure-pr', '--repo', self.SLUG, '--branch', 'feat/x',
                      '--base', 'main', '--title', 'title', '--body-file', body, code=1)

    def test_link_create_update_and_idempotence(self):
        self.run_pair('link', '--repo', self.SLUG, '--pr', '7', '--kind', 'store',
                      '--peer-url', 'https://github.com/o/store/pull/2', code=0)
        self.add_comment('me', '<!-- specwright:link store https://github.com/o/store/pull/1 -->')
        self.run_pair('link', '--repo', self.SLUG, '--pr', '7', '--kind', 'store',
                      '--peer-url', 'https://github.com/o/store/pull/2', '--login', 'me', code=0)
        self.add_comment('me', '<!-- specwright:link store https://github.com/o/store/pull/2 -->')
        self.run_pair('link', '--repo', self.SLUG, '--pr', '7', '--kind', 'store',
                      '--peer-url', 'https://github.com/o/store/pull/2', code=0)

    def pair_repos(self):
        code = self.repo('code', settings='github:\n  login: me\nplanning_store:\n  login: other\n')
        store = self.repo('store', origin='https://github.com/o/plans.git')
        for d in [code, store]:
            self.git(d, 'commit', '--allow-empty', '-m', 'base')
            self.git(d, 'checkout', '-b', 'feat/x')
        self.mutate(lambda st: st['repos'].update({'o/plans': {'pulls': []}}))
        return code, store

    def test_expected_per_repo_login_and_pair_missing(self):
        code, store = self.pair_repos()
        args = ['--code', code, '--store', store, '--branch', 'feat/x']
        self.run_pair('expected', *args, code=0)
        self.run_pair('pair-state', *args, code=0)

    def merged_pair(self):
        code, store = self.pair_repos()
        def seed(st):
            p = st['repos'][self.SLUG]['pulls'][0]
            p.update(state='closed', merged_at='2026-10-08T10:00:00Z', merge_commit_sha='a'*40)
            p['head'].update(sha=self.git(code, 'rev-parse', 'HEAD'))
            other = copy.deepcopy(p)
            other['html_url'] = 'https://github.com/o/plans/pull/7'
            other['head'].update(sha=self.git(store, 'rev-parse', 'HEAD'), repo={'full_name': 'o/plans'})
            st['repos']['o/plans']['pulls'] = [other]
        self.mutate(seed)
        return code, store

    def cleanup_contract(self, code, store):
        args = ['cleanup-plan', '--code', code, '--store', store, '--branch', 'feat/x']
        before = self.gh_state.read_bytes()
        native = self.side('new', args, self.tmp)
        self.gh_state.write_bytes(before)
        oracle = self.side('old', args, self.tmp)
        self.gh_state.write_bytes(before)
        self.assertEqual(native['code'], 0, native)
        self.assertEqual(oracle['code'], 0, oracle)
        got, expected = self.normal(native)[0], self.normal(oracle)[0]
        # This is the explicit producer/consumer contract change in D4/C4,
        # not normalization of a workflow decision or mutation guard.
        for side in ['code', 'store']:
            for entry in expected[side]['commands']:
                command = entry['cmd']
                if command[0] == 'bash' and command[1].endswith(('/as.sh', '/vcs.sh')):
                    name = Path(command[1]).name
                    self.assertEqual(command[1], parity.fixtures.posix(Path(parity.oracle_sw_dir()) / name))
                    native_command = got[side]['commands'][expected[side]['commands'].index(entry)]['cmd']
                    self.assertEqual(native_command[1], parity.fixtures.posix(parity.SCRIPTS / name))
                    command[1] = native_command[1]
                if command[0] == 'pr-pair.sh':
                    command[1:1] = ['--project', code]
                elif command[0] == 'bash' and command[1].endswith('/as.sh'):
                    command[2:2] = ['--project', code]
                self.assertEqual(entry['cwd'], got[side]['dir'])
        for side in ['code', 'store']:
            delete = expected[side].get('delete', [])
            if delete[:1] == ['bash']:  # bare-bash: not started
                self.assertEqual(delete[1], parity.fixtures.posix(Path(parity.oracle_sw_dir()) / 'vcs.sh'))
                self.assertEqual(got[side]['delete'][1], parity.fixtures.posix(parity.SCRIPTS / 'vcs.sh'))
                delete[1] = got[side]['delete'][1]
        self.assertEqual(got, expected)
        self.assertEqual(native['calls'], oracle['calls'])
        return got

    def test_cleanup_plan_preserves_commands_and_project_selection(self):
        code, store = self.merged_pair()
        plan = self.cleanup_contract(code, store)
        for side, login in [('code', 'me'), ('store', 'other')]:
            pull = plan[side]['commands'][1]['cmd']
            self.assertEqual(pull[2:5], ['--project', code, login])
            self.assertEqual(plan[side]['commands'][2]['cmd'][1:3], ['--project', code])
            self.assertEqual(plan[side]['delete'], ['git', 'branch', '-D', 'feat/x'])
        self.mutate(lambda st: st['repos']['o/plans']['pulls'][0].update(state='open', merged_at=None))
        self.assertEqual(len(self.cleanup_contract(code, store)['keep']), 1)
        self.git(store, 'remote', 'remove', 'origin')
        self.assertEqual(self.cleanup_contract(code, store)['keep'][0]['state'], 'SHARE_BY_HAND')

    def test_branch_check_preserves_moved_commit_guard(self):
        code, _ = self.pair_repos()
        args = ['--dir', code, '--branch', 'feat/x', '--main', 'main']
        before = self.git(code, 'show-ref')
        self.assertEqual(self.run_pair('branch-check', *args, code=0)['reason'], 'on_main')
        self.git(code, 'commit', '--allow-empty', '-m', 'PR work')
        head = self.git(code, 'rev-parse', 'HEAD')
        self.assertEqual(self.run_pair('branch-check', *args, '--head', head, code=0)['reason'], 'pr_head')
        self.git(code, 'commit', '--allow-empty', '-m', 'new work after merge')
        moved = self.git(code, 'show-ref')
        doc = self.run_pair('branch-check', *args, '--head', head, code=0)
        self.assertEqual(doc['reason'], 'lacking')
        self.assertEqual(doc['lacking'][0]['subject'], 'new work after merge')
        self.assertEqual(self.git(code, 'show-ref'), moved)
        self.assertNotEqual(before, moved)
        self.assertEqual(self.run_pair('branch-check', *args, '--head', 'a'*40, code=0)['reason'], 'head_unknown')
        self.run_pair('branch-check', *args, '--head', 'invalid', code=2)
        self.run_pair('branch-check', '--dir', code, '--branch', 'absent', '--main', 'main', code=1)

    def select_backend(self, code, store, backend, role='code', logins=True):
        settings = ('github:\n  login: me\n' if logins else '')
        settings += ('vcs: '+backend+'\n' if role == 'code' else 'vcs: git\n')
        settings += 'finish: pr\nplanning_store:\n  vcs: '+(backend if role == 'store' else 'git')+'\n'
        if logins:
            settings += '  login: other\n'
        (Path(code) / self.SETTINGS).write_text(settings, encoding='utf-8')
        target = Path(code if role == 'code' else store)
        if backend == 'jj':
            (target / '.jj').mkdir(exist_ok=True)
            script = '#!/bin/sh\ncase "$1" in --version) echo "jj 0.46.0";; root) if command -v cygpath >/dev/null 2>&1; then cygpath -w "$PWD"; else pwd -P; fi;; *) exit 91;; esac\n'
            name = 'jj'
        else:
            (target / '.git' / 'gitbutler').mkdir(exist_ok=True)
            self.git(str(target), 'config', 'gitbutler.project.targetRef', 'refs/heads/main')
            script, name = '#!/bin/sh\necho "but 0.23.1"\n', 'but'
        tool = self.tmp / 'bin' / name
        tool.write_text(script, encoding='utf-8', newline='\n')
        tool.chmod(0o755)

    def test_cleanup_non_git_plans_preserve_backend_commands(self):
        code, store = self.merged_pair()
        for backend in ['jj', 'gitbutler']:
            with self.subTest(backend=backend):
                self.select_backend(code, store, backend)
                plan = self.cleanup_contract(code, store)
                self.assertEqual(plan['code']['commands'][0]['cmd'][2], 'switch')
                self.assertEqual(plan['code']['delete'][2], 'delete-branch')
                if backend == 'gitbutler':
                    self.assertIn('--merged-commit', plan['code']['delete'])

    def test_gitbutler_deleted_branch_is_already_deleted(self):
        code, store = self.merged_pair()
        self.select_backend(code, store, 'gitbutler')
        self.git(code, 'checkout', 'main')
        self.git(code, 'branch', '-D', 'feat/x')
        doc = self.run_pair('branch-check', '--dir', code, '--branch', 'feat/x', '--main', 'main', code=0)
        self.assertEqual(doc['reason'], 'already_deleted')

    def test_printed_cleanup_commands_preserve_consumer_effects(self):
        import shlex
        import shutil
        code, store = self.merged_pair()
        plan = self.cleanup_contract(code, store)
        real = shutil.which('git').replace('\\', '/')
        log = self.tmp / 'pull-consumer'
        tool = self.tmp / 'bin' / 'git'
        tool.write_text('#!/bin/sh\nif [ "$1" = pull ]; then target="$PWD"; if command -v cygpath >/dev/null 2>&1; then target=$(cygpath -m "$PWD"); fi; printf "%s|%s|%s\\n" "$target" "$GH_TOKEN" "$*" >> "$WF_PULL_LOG"; exit 0; fi\nexec '+shlex.quote(real)+' "$@"\n', encoding='utf-8', newline='\n')
        tool.chmod(0o755)
        self.extra_env['WF_PULL_LOG'] = log.as_posix()
        for role in ['code', 'store']:
            entry = plan[role]
            for printed in entry['commands'][:2]:
                self.assertIn(printed['cmd'][0], ['git', 'bash'])
                # Resolve the asserted interpreter through the same Git Bash
                # selector as every other eval. bin/bash.exe resets PATH and
                # hides the fake git that records this consumer's effects.
                command = ([parity.bashexe.bash(), *printed['cmd'][1:]]
                           if printed['cmd'][0] == 'bash' else printed['cmd'])
                result = subprocess.run(command, cwd=printed['cwd'], env=self.env('me', SPECWRIGHT_HOME=str(self.home)), capture_output=True)
                self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
            printed = entry['commands'][2]
            self.assertEqual(printed['cmd'][:3], ['pr-pair.sh', '--project', code])
            # Until group8 switches the shim, consume its exact selector and
            # send its unchanged remainder to the native entry from this cwd.
            result = self.side('new', printed['cmd'][3:], printed['cwd'])
            self.assertTrue(json.loads(result['stdout'])['delete'], result)
            if role == 'code':
                self.git(code, 'checkout', 'feat/x')
                self.git(code, 'commit', '--allow-empty', '-m', 'new work after merged PR')
                self.git(code, 'checkout', 'main')
                before = self.git(code, 'show-ref')
                result = self.side('new', printed['cmd'][3:], printed['cwd'])
                self.assertFalse(json.loads(result['stdout'])['delete'], result)
                self.assertEqual(self.git(code, 'show-ref'), before)
            else:
                self.git(store, *entry['delete'][1:])
                self.assertNotIn('refs/heads/feat/x', self.git(store, 'show-ref'))
        lines = log.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        for line, target, token in zip(lines, [code, store], ['tok-me', 'tok-other']):
            cwd, used, arguments = line.split('|')
            self.assertEqual(Path(cwd).resolve(), Path(target).resolve())
            self.assertEqual((used, arguments), (token, 'pull --ff-only'))

    def test_every_workflow_command_has_differential_coverage(self):
        code, store = self.merged_pair()
        base = self.gh_state.read_bytes()
        body = self.body('new PR body')
        cases = {
            'discover': ['--repo', self.SLUG, '--branch', 'feat/x'],
            'ensure-pr': ['--repo', self.SLUG, '--branch', 'feat/new', '--base', 'main', '--title', 'matrix', '--body-file', body],
            'link': ['--repo', self.SLUG, '--pr', '7', '--kind', 'store', '--peer-url', 'https://github.com/o/plans/pull/7'],
            'expected': ['--code', code, '--store', store, '--branch', 'feat/x'],
            'pair-state': ['--code', code, '--store', store, '--branch', 'feat/x'],
            'rounds': ['--code', code, '--store', store, '--branch', 'feat/x'],
            'closing-check': ['--repo', self.SLUG, '--pr', '7'],
            'closed-check': ['--repo', self.SLUG, '--pr', '7', '--repos', self.SLUG],
            'merge': ['--repo', self.SLUG, '--pr', '7', '--method', 'merge', '--head', self.HEAD],
            'delete-remote': ['--repo', self.SLUG, '--branch', 'feat/x', '--head', self.HEAD],
            'item-issues': ['--repo', self.SLUG, '--item', 'matrix'],
            'cleanup-plan': ['--code', code, '--store', store, '--branch', 'feat/x'],
            'branch-check': ['--dir', code, '--branch', 'feat/x', '--main', 'main'],
        }
        for command, args in cases.items():
            with self.subTest(command=command):
                self.gh_state.write_bytes(base)
                if command in ('closing-check', 'closed-check'):
                    self.closing_seed('Fixes #21\nFixes #24\n', merged='2026-10-08T10:00:00Z')
                    self.mutate(lambda st: [parity.fake_gh.set_issue(st, self.SLUG, n, 'CLOSED', ['CLOSED']) for n in [21, 24]])
                if command == 'item-issues':
                    self.mutate(lambda st: st['repos'][self.SLUG].update(issue_list=[{'number': 2, 'body': 'specwright:pr-item matrix'}]))
                if command == 'delete-remote':
                    self.mutate(lambda st: st['repos'][self.SLUG].update(branches={'feat/x': self.HEAD}))
                if command == 'cleanup-plan':
                    document = self.cleanup_contract(code, store)
                    self.assertTrue(document['code']['delete'])
                else:
                    document = self.run_pair(command, *args, code=0)
                if command == 'ensure-pr':
                    self.assertEqual(document['action'], 'created')
                    self.assertTrue(any(c[:2] == ['pr', 'create'] for c in self.last_native_calls))
                elif command == 'link':
                    self.assertEqual(document['action'], 'created')
                    self.assertTrue(any('POST' in c for c in self.last_native_calls))
                elif command == 'item-issues':
                    self.assertEqual(document['found'], {'matrix': 2})
                elif command == 'branch-check':
                    self.assertTrue(document['delete'])
                if command == 'branch-check':
                    refs = self.git(code, 'show-ref')
                    denied = self.run_pair(command, '--dir', code, '--branch', 'absent', '--main', 'main', code=1)
                    self.assertEqual(denied['error'], 'git_error')
                    self.assertEqual(self.git(code, 'show-ref'), refs)
                elif command == 'rounds':
                    # A domain-level unknown read is represented in the report,
                    # and preserves local refs rather than inventing success.
                    prior = self.git(code, 'rev-parse', 'HEAD')
                    self.git(code, 'remote', 'set-url', 'origin', str(self.tmp / 'missing.git'))
                    self.git(code, 'commit', '--allow-empty', '-m', 'fix\n\nFeedback-Round: 2')
                    denied = self.run_pair(command, *args, code=0)
                    self.assertEqual(denied['remote_unreadable'], ['code'])
                    self.assertEqual(denied['unpushed'], {})
                    self.git(code, 'reset', '--hard', prior)
                    self.git(code, 'remote', 'set-url', 'origin', 'https://github.com/'+self.SLUG+'.git')
                else:
                    self.mutate(lambda st: st.update(fail=[{'match': 'api', 'stderr': 'matrix read unavailable'}]))
                    before = self.gh_state.read_bytes()
                    self.run_pair(command, *args, code=3)
                    self.assertEqual(self.gh_state.read_bytes(), before)
                    self.assertFalse(any('POST' in c or 'PATCH' in c or 'DELETE' in c for c in self.last_native_calls))
        # The four pass operations have their record/call/ownership contracts
        # exercised by WorkflowPassMatrix below, in this same native module.
        self.assertEqual(set(cases) | {'pass'}, {'discover', 'ensure-pr', 'link', 'expected', 'pair-state', 'rounds', 'closing-check', 'closed-check', 'merge', 'delete-remote', 'item-issues', 'cleanup-plan', 'branch-check', 'pass'})

    def test_store_credential_lookup_limit_retains_error(self):
        code, store = self.pair_repos()
        self.extra_env['SPECWRIGHT_NET_DEADLINE'] = '1'
        self.mutate(lambda st: st.update(delay=[{'match': 'auth token --hostname', 'seconds': 2}]))
        self.run_pair('expected', '--code', code, '--store', store, '--branch', 'feat/x', code=3)

    def test_rounds_without_feedback_trailers(self):
        code, store = self.pair_repos()
        self.git(code, 'commit', '--allow-empty', '-m', 'address review feedback')
        self.run_pair('rounds', '--code', code, '--store', store, '--branch', 'feat/x', code=0)
        settings = Path(code) / 'openspec' / 'specwright.yaml'
        settings.write_text('pr:\n  max_fix_rounds: 99999999999999999999999999\n', encoding='utf-8')
        self.run_pair('rounds', '--code', code, '--store', store, '--branch', 'feat/x', code=0)

    def test_rounds_trailers_and_unreadable_remote(self):
        code, store = self.pair_repos()
        self.git(code, 'remote', 'set-url', 'origin', str(self.tmp / 'missing.git'))
        self.git(code, 'commit', '--allow-empty', '-m', 'fix\n\nFeedback-Round: 2')
        self.run_pair('rounds', '--code', code, '--store', store, '--branch', 'feat/x', code=0)

    def test_rounds_preserves_arbitrary_precision_feedback_trailers(self):
        code, store = self.pair_repos()
        self.git(code, 'remote', 'set-url', 'origin', str(self.tmp / 'missing.git'))
        number = 99999999999999999999999999
        self.git(code, 'commit', '--allow-empty', '-m', f'fix\n\nFeedback-Round: {number}')
        d = self.run_pair('rounds', '--code', code, '--store', store, '--branch', 'feat/x', code=0)
        self.assertEqual(d['rounds'], number)
        self.assertEqual(d['code']['max_trailer'], number)

    def test_unknown_read_permits_no_follow_on_mutation(self):
        self.mutate(lambda st: st.update(fail=['api --paginate repos/o/n/pulls']))
        body = self.body('body')
        d = self.run_pair('ensure-pr', '--repo', self.SLUG, '--branch', 'new',
                          '--base', 'main', '--title', 'title', '--body-file', body, code=3)
        self.assertEqual(d['error'], 'lookup_failed')

    def test_discover_reads_all_pages_and_deduplicates(self):
        def seed(st):
            first = self._pull()
            pulls = []
            for n in range(1, 105):
                p = copy.deepcopy(first)
                p.update(number=n, html_url=f'https://github.com/{self.SLUG}/pull/{n}')
                pulls.append(p)
            st['repos'][self.SLUG]['pulls'] = pulls + [pulls[0]]
        self.mutate(seed)
        d = self.run_pair('discover', '--repo', self.SLUG, '--branch', 'feat/x', code=0)
        self.assertEqual(len(d['prs']), 104)

    def test_pair_state_stale_snapshots_and_split_state(self):
        code, store = self.pair_repos()
        p = self._pull()
        p['html_url'] = 'https://github.com/o/plans/pull/7'
        p['head']['repo']['full_name'] = 'o/plans'
        self.mutate(lambda st: st['repos']['o/plans'].update(pulls=[p]))
        snap = self.tmp / 'stale.json'
        snap.write_text(json.dumps({'number': 7, 'url': 'https://github.com/o/n/pull/7',
            'head_oid': 'b'*40, 'mergeable': 'MERGEABLE', 'merge_state': 'CLEAN',
            'checks': {'pending': 0, 'ci_pending': 0}}), encoding='utf-8')
        args = ['--code', code, '--store', store, '--branch', 'feat/x']
        self.run_pair('pair-state', *args, '--snapshot', f'code={snap}',
                      '--snapshot', f'store={snap}', code=0)
        self.mutate(lambda st: st['repos']['o/plans']['pulls'][0].update(
            state='closed', merged_at='2026-10-10T12:00:00Z'))
        d = self.run_pair('pair-state', *args, code=0)
        self.assertEqual(d['action'], 'split_hand_off')

    def closing_seed(self, body, base='main', merged=None):
        def seed(st):
            p = st['repos'][self.SLUG]['pulls'][0]
            p.update(body=body, merged_at=merged, state='closed' if merged else 'open')
            p['base']['ref'] = base
            parity.fake_gh.set_closing_refs(st, self.SLUG, 7, [(21, self.SLUG)])
        self.mutate(seed)

    def test_rendered_closing_lines_preserve_code_boundaries(self):
        import closing_bodies
        bodies = closing_bodies.collect_bodies()
        selected = list(dict.fromkeys(bodies[:4] + [next(b for b in bodies if '`' in b),
                    next(b for b in bodies if '\n' in b)] + bodies[-2:]))
        for body in selected:
            with self.subTest(body=body):
                self.closing_seed(body)
                self.run_pair('closing-check', '--repo', self.SLUG, '--pr', '7', code=0)

    def test_closing_checks_base_and_render_refusal(self):
        self.closing_seed('Fixes #21\nFixes #24\n', base='release')
        doc = self.run_pair('closing-check', '--repo', self.SLUG, '--pr', '7', code=0)
        self.assertEqual(doc['status'], 'not_default_base')
        self.mutate(lambda st: st.update(fail=[{'match': 'POST markdown', 'stderr': 'render unavailable'}]))
        self.run_pair('closing-check', '--repo', self.SLUG, '--pr', '7', code=3)

    def test_closing_truncated_list_is_unknown_without_render(self):
        self.closing_seed('Fixes #21\nFixes #24\n')
        self.mutate(lambda st: parity.fake_gh.set_closing_refs(st, self.SLUG, 7, [], True))
        self.run_pair('closing-check', '--repo', self.SLUG, '--pr', '7', code=3)
        self.assertFalse(any('markdown' in c for c in self.last_native_calls))

    def test_closed_checks_merged_open_reopened_outside(self):
        self.closing_seed('Fixes #21\nFixes #24\n', merged='2026-10-08T10:00:00Z')
        def seed(st):
            parity.fake_gh.set_issue(st, self.SLUG, 21, 'CLOSED', ['CLOSED'])
            parity.fake_gh.set_issue(st, self.SLUG, 24, 'OPEN', ['CLOSED', 'REOPENED'])
        self.mutate(seed)
        doc = self.run_pair('closed-check', '--repo', self.SLUG, '--pr', '7', '--repos', self.SLUG, code=0)
        self.assertEqual(doc['closed'], [self.SLUG+'#21'])
        self.assertEqual(doc['reopened'], [self.SLUG+'#24'])
        self.run_pair('closed-check', '--repo', self.SLUG, '--pr', '7', '--repos', 'other/repo', code=0)
        self.mutate(lambda st: st['repos'][self.SLUG]['pulls'][0]['base'].update(ref='release'))
        self.run_pair('closed-check', '--repo', self.SLUG, '--pr', '7', '--repos', self.SLUG, code=0)
        self.mutate(lambda st: st.update(fail=[{'match': r'issue\(number', 'stderr': 'issue unavailable'}]))
        self.mutate(lambda st: st['repos'][self.SLUG]['pulls'][0]['base'].update(ref='main'))
        self.run_pair('closed-check', '--repo', self.SLUG, '--pr', '7', '--repos', self.SLUG, code=3)

    def test_merge_is_attempted_once_then_read_back(self):
        self.mutate(lambda st: st['repos'][self.SLUG]['pulls'][0]['head'].update(sha=self.HEAD))
        self.run_pair('merge', '--repo', self.SLUG, '--pr', '7', '--method', 'squash', '--head', self.HEAD, code=0)
        self.run_pair('merge', '--repo', self.SLUG, '--pr', '7', '--method', 'merge', '--head', 'a'*40, code=1)
        self.mutate(lambda st: st.update(fail=[{'match': '-X PUT', 'stderr': 'connection reset', 'once': True}]))
        self.run_pair('merge', '--repo', self.SLUG, '--pr', '7', '--method', 'merge', '--head', self.HEAD, code=3)
        self.assertEqual(sum('PUT' in c for c in self.last_native_calls), 1)
        self.assertEqual(self.last_native_calls[-1], ['api', f'repos/{self.SLUG}/pulls/7'])

    def test_merge_limited_put_reads_back_without_retry(self):
        self.extra_env['SPECWRIGHT_NET_MAX_BYTES'] = '2048'
        self.mutate(lambda st: st.update(flood=[{'match': '-X PUT', 'bytes': 20000}]))
        self.run_pair('merge', '--repo', self.SLUG, '--pr', '7', '--method', 'merge', '--head', self.HEAD, code=3)
        self.assertEqual(sum('PUT' in c for c in self.last_native_calls), 1)
        self.mutate(lambda st: st['repos'][self.SLUG]['pulls'][0].update(merged_at='2026-10-09T10:00:00Z', state='closed', merge_commit_sha='d'*40))
        doc = self.run_pair('merge', '--repo', self.SLUG, '--pr', '7', '--method', 'merge', '--head', self.HEAD, code=0)
        self.assertEqual(doc['status'], 'merged')
        self.assertEqual(sum('PUT' in c for c in self.last_native_calls), 1)
        self.mutate(lambda st: st.update(fail=[{'match': r'pulls/7$', 'stderr': 'read-back unavailable'}]))
        doc = self.run_pair('merge', '--repo', self.SLUG, '--pr', '7', '--method', 'merge', '--head', self.HEAD, code=3)
        self.assertEqual(doc['status'], 'unknown')
        self.assertEqual(sum('PUT' in c for c in self.last_native_calls), 1)

    def test_moved_remote_branch_is_retained(self):
        self.mutate(lambda st: st['repos'][self.SLUG].update(branches={'feat/x': 'a'*40}))
        self.run_pair('delete-remote', '--repo', self.SLUG, '--branch', 'feat/x', '--head', self.HEAD, code=0)
        self.mutate(lambda st: st['repos'][self.SLUG].update(branches={'feat/x': self.HEAD}))
        self.mutate(lambda st: st['repos'][self.SLUG]['pulls'][0]['base'].update(ref='feat/x'))
        based = self.run_pair('delete-remote', '--repo', self.SLUG, '--branch', 'feat/x', '--head', self.HEAD, code=0)
        self.assertEqual(based['status'], 'based_on')
        self.mutate(lambda st: st['repos'][self.SLUG]['pulls'][0]['base'].update(ref='main'))
        self.run_pair('delete-remote', '--repo', self.SLUG, '--branch', 'feat/x', '--head', self.HEAD, code=0)
        self.mutate(lambda st: st.update(fail=[{'match': 'git/ref/heads/', 'stderr': 'failed ref read'}]))
        self.run_pair('delete-remote', '--repo', self.SLUG, '--branch', 'feat/x', '--head', self.HEAD, code=3)

    def test_item_issues_lowest_marker_and_unknown_read(self):
        self.mutate(lambda st: st['repos'][self.SLUG].update(issue_list=[
            {'number': 9, 'body': 'specwright:pr-item a'}, {'number': 2, 'body': 'specwright:pr-item a'},
            {'number': 3, 'body': 'specwright:pr-item b extra'}]))
        doc = self.run_pair('item-issues', '--repo', self.SLUG, '--item', 'a', '--item', 'b', code=0)
        self.assertEqual(doc['found'], {'a': 2})
        self.mutate(lambda st: st.update(fail=[{'match': 'api .*issues', 'stderr': 'unreadable'}]))
        self.run_pair('item-issues', '--repo', self.SLUG, '--item', 'a', code=3)


# Reuse fixture/normalization helpers, without collecting their unrelated tests.
for _name in dir(parity.PairParity):
    if _name.startswith('test_') and _name not in WorkflowParity.__dict__:
        setattr(WorkflowParity, _name, None)


import test_workflow_records as records
import test_pr_pair as original


class WorkflowPassMatrix(records.NativePass, original.PassBase):
    """All four operations compare native/frozen calls and record effects.

    Generated owner ids and creation times are bound through each writer's
    returned owner and persisted record. Only these independently generated
    values differ: ownership checks and preserved written_at are asserted.
    """
    snapshots = records.WorkflowRecords.snapshots

    def calls(self):
        return parity.calls_of(self.gh_log, lambda call: call['argv'])

    def clean_doc(self, doc):
        result = {key: value for key, value in doc.items() if key != 'message'}
        if 'path' in result:
            # Native mixed/forward separators and Python OS separators must
            # name and open the same record; bind only after consuming it.
            path = Path(result['path'])
            self.assertEqual(path.resolve(), self.record_path().resolve())
            self.assertEqual(path.read_bytes(), self.record_path().read_bytes())
            result['path'] = str(path.resolve())
        return result

    def test_all_four_pass_operations_preserve_records_and_refusals(self):
        from datetime import datetime, timezone
        self.settings('github:\n  login: KintsugiBot\npr:\n  react: false\n')
        intent = self.write_json('matrix-intent.json', self.intent([]))
        outputs, persisted, calls = [], [], []
        for which in ['native', 'frozen']:
            self.record_path().unlink(missing_ok=True)
            started = datetime.now(timezone.utc).replace(microsecond=0)
            written = self.pp('pass', 'write', *self.common(), '--intent', intent, which=which)
            record = json.loads(self.record_path().read_bytes())
            self.assertRegex(written['owner'], r'^[0-9a-f]{32}$')
            self.assertEqual(record['owner']['id'], written['owner'])
            self.assertEqual(record['written_at'], record['owner']['at'])
            self.assertGreaterEqual(datetime.fromisoformat(record['written_at'].replace('Z', '+00:00')), started)
            self.assertLessEqual(datetime.fromisoformat(record['written_at'].replace('Z', '+00:00')), datetime.now(timezone.utc))
            self.assertEqual(record['heads'], written['heads'])
            self.assertEqual(record['version'], 2)
            self.assertEqual(record['owner']['checkout'], str(self.code).replace('\\', '/'))
            outputs.append({**written, 'owner': '<generated-owner>'})
            persisted.append(record)
            calls.append(self.calls())
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(calls[0], calls[1])
        for record in persisted:
            record['owner']['id'] = '<generated-owner>'
            record['owner']['at'] = record['written_at'] = '<creation-time>'
        self.assertEqual(persisted[0], persisted[1])
        # A concrete existing record is shared verbatim by both consumers.
        baseline = json.loads(self.record_path().read_bytes())
        baseline['owner']['id'] = 'matrix-owner'
        baseline_bytes = json.dumps(baseline).encode()
        for operation, extra in [
            ('plan', ['--owner', 'matrix-owner', *self.snapshots()]),
            ('adopt', ['--owner', 'adopted', '--from', 'matrix-owner']),
            ('done', ['--owner', 'matrix-owner', *self.snapshots()]),
        ]:
            responses, effects, observed = [], [], []
            for which in ['native', 'frozen']:
                self.record_path().write_bytes(baseline_bytes)
                result = self.pp('pass', operation, *self.common(), *extra, which=which)
                responses.append(self.clean_doc(result)); observed.append(self.calls())
                if operation == 'done':
                    self.assertTrue(result['deleted'])
                    self.assertFalse(self.record_path().exists())
                    effects.append(None)
                else:
                    raw = self.record_path().read_bytes()
                    if operation == 'plan':
                        self.assertEqual(raw, baseline_bytes)
                        self.assertTrue(result['owned'])
                        self.assertTrue(result['delete_record'])
                        effects.append(raw)
                    else:
                        record = json.loads(raw)
                        self.assertEqual(record['owner']['id'], 'adopted')
                        self.assertEqual(record['written_at'], baseline['written_at'])
                        self.assertEqual(record['heads'], baseline['heads'])
                        record['owner']['at'] = '<adoption-time>'
                        effects.append(record)
                self.assertFalse(Path(str(self.record_path())+'.lock').exists())
            self.assertEqual(responses[0], responses[1]); self.assertEqual(effects[0], effects[1]); self.assertEqual(observed[0], observed[1])
        for operation, extra, expected in [
            ('write', ['--intent', intent], 'record_exists'),
            ('plan', ['--owner', 'foreign', *self.snapshots()], 'record_unreadable'),
            ('adopt', ['--owner', 'new', '--from', 'foreign'], 'not_owner'),
            ('done', ['--owner', 'foreign', *self.snapshots()], 'not_owner'),
        ]:
            responses, observed = [], []
            protected = b'{partial-record' if operation == 'plan' else baseline_bytes
            for which in ['native', 'frozen']:
                self.record_path().write_bytes(protected)
                doc = self.pp('pass', operation, *self.common(), *extra, which=which, expect=1)
                self.assertEqual(doc['error'], expected)
                responses.append(self.clean_doc(doc)); observed.append(self.calls())
                self.assertEqual(self.record_path().read_bytes(), protected)
                self.assertFalse(Path(str(self.record_path())+'.lock').exists())
            self.assertEqual(responses[0], responses[1]); self.assertEqual(observed[0], observed[1])
