"""Workflow entries against the immutable test-only Python oracle."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_parity as parity
import vcs_test_support


class WorkflowParity(parity.PairParity):
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
            result = super().side(which, args, cwd)
            result['calls'] = [self.command_binding(c) for c in result['calls']]
            return result
        args = args(which) if callable(args) else args
        e = self.env('me', SPECWRIGHT_HOME=str(self.home),
                     GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        binary = os.environ['SPECWRIGHT_SW']
        payload = b''.join(str(x).encode('utf-8') + b'\0' for x in
                           [parity.SCRIPTS, parity.bashexe.bash(), *args[1:]])
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
