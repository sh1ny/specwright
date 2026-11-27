"""Workflow entries of `sw pr` against the recorded runs of the frozen workflow (change native-cli-retire-scripts task 7.2):
no frozen script is started."""
import copy
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_parity as parity
import vcs_test_support
import swcall  # vcs_test_support puts evals/ on sys.path
import fakeexe
import oracle_capture


def setUpModule():
    parity.setUpModule()


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
        return subprocess.run(['git', *args], cwd=directory, env={**self.git_env, **parity.PINNED_IDENTITY},
                              capture_output=True, check=True).stdout.decode().strip()

    @staticmethod
    def command_binding(argv):
        # The random input filename stays as it is: the record holds it as `<temp>/<name>`. The fake's persisted comment body
        # is still compared byte-for-byte by run_pair.
        return parity.temp_names(argv)

    def comparable_calls(self, calls):
        # Account binding now precedes discovery, including the store check.
        # Keep transport authorization in the dedicated tests with raw calls.
        return [argv for argv in calls if argv[:2] != ["auth", "token"] and
                argv != ["api", "--hostname", "github.com", "user", "--jq", ".login"]]

    MATRIX_API_FAILURE = r'^api (?!.*\buser --jq \.login$)'

    def comparable_state(self, state):
        # Only the matrix's injected fault changed: identity verification now
        # succeeds before the same simulated API failure. Compare all repo data.
        if state is not None and state.get('fail') == [
            {'match': self.MATRIX_API_FAILURE, 'stderr': 'matrix read unavailable'}
        ]:
            return {**state, 'fail': [{'match': 'api', 'stderr': 'matrix read unavailable'}]}
        return state

    def side(self, args, cwd):
        """sw's run of `pr <args>`, direct entry (evals/swcall.py), with the calls bound by command_binding."""
        args = args('new') if callable(args) else args
        e = self.env('me', SPECWRIGHT_HOME=str(self.home),
                     GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        r = swcall.run(['pr', *args], cwd=cwd or self.tmp, env=e, timeout=120, text=False)
        raw_calls = parity.calls_of(self.gh_log, lambda c: c)
        result = {'code': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr,
                'calls': [self.command_binding(c['argv']) for c in raw_calls],
                'raw_calls': raw_calls,
                'state': self.gh_state.read_bytes()}
        self.last_native_calls = result['calls']
        return result

    def assert_native_refuses(self, *args, code, error, old_code=0):
        """An asserted difference (native-cli-library-foundations D8): the frozen workflow held an integer of any size and
        went on (recorded exit `old_code`), the native one cannot hold it and refuses with `error` (exit `code`) after the same
        gh reads. Returns the native document; the fake gh state is put back afterwards."""
        before = self.gh_state.read_bytes()
        parity.calls_of(self.gh_log, lambda c: c)
        new = self.side(args, None)
        self.gh_state.write_bytes(before)
        old = oracle_capture.recorded(self)[0]
        self.assertEqual(old['exit'], old_code, old['stdout'])
        self.assertEqual(new['code'], code, (new['stdout'], new['stderr']))
        document = json.loads(new['stdout'])
        self.assertEqual(document['error'], error, document)
        return document

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

    @staticmethod
    def printed_form(command, code):
        """A frozen printed command as the native plan prints it: `<sw> --project <code> ...` (the sw bound by bind_sw)."""
        # a frozen printed command ran a helper by its file name (`<name>` + the shell suffix), alone or under `bash`
        verb = {'pr-pair': 'pr', 'as': 'as', 'vcs': 'vcs'}
        shell = 1 if command[0] == 'bash' else 0
        stem, suffix = Path(command[shell]).name.rpartition('.')[0::2]
        if suffix == 'sh' and stem in verb:
            return ['<sw>', '--project', code, verb[stem], *command[shell + 1:]]
        if command[1:2] == ['--project']:  # the frozen shim hands `vcs plan` to sw: already the native form
            return ['<sw>', *command[1:]]
        return command

    def bind_sw(self, command, code):
        """Check that a printed command starts with the running sw and the code project, and replace both by their
        stand-ins (the project may print in a resolved form of the same directory)."""
        if command[0] in ('git', 'jj'):
            return command
        # the running sw: SPECWRIGHT_SW itself, or under the shim its version-matched copy `<home>/.specwright/bin/<v>/sw`
        running = Path(command[0]).resolve()
        self.assertTrue(running == Path(os.environ['SPECWRIGHT_SW']).resolve() or running.parts[-4:-2] == ('.specwright', 'bin'), command)
        self.assertEqual(command[1], '--project', command)
        self.assertEqual(Path(command[2]).resolve(), Path(code).resolve(), command)
        command[0], command[2] = '<sw>', code
        return command

    def run_printed(self, printed):
        """Run a printed `{cmd, cwd}` as printed, with the test home; the CompletedProcess."""
        return subprocess.run(printed['cmd'], cwd=printed['cwd'], capture_output=True, timeout=120,
                              env=self.env('me', SPECWRIGHT_HOME=str(self.home), GIT_CONFIG_GLOBAL=os.devnull,
                                           GIT_CONFIG_NOSYSTEM='1'))

    def cleanup_contract(self, code, store):
        args = ['cleanup-plan', '--code', code, '--store', store, '--branch', 'feat/x']
        before = self.gh_state.read_bytes()
        native = self.side(args, self.tmp)
        self.gh_state.write_bytes(before)
        oracle = oracle_capture.recorded(self)[0]
        self.assertEqual(native['code'], 0, native)
        self.assertEqual(oracle['exit'], 0, oracle)
        paths, canon = oracle_capture.Paths(self), oracle_capture.canon
        plan, expected = self.normal(native)[0], self.shape(oracle['stdout'], False)
        got, here = paths.node(plan), paths.text(str(code))
        # This is the explicit producer/consumer contract change in D4: the frozen plan printed scripts, the native one
        # prints the running sw and `--project <code>`. Each recorded frozen command is translated to that form, not normalized
        # away: the sw path is checked on its own, then the decisions, arguments and cwd must match exactly.
        bound = copy.deepcopy(plan)
        for side in ['code', 'store']:
            for entry in expected[side]['commands']:
                self.assertEqual(entry['cwd'], got[side]['dir'])
            commands = []
            for entry in expected[side]['commands']:
                argv = self.printed_form(entry['cmd'], here)
                if argv[3:4] == ['as'] and argv[5:] == ['git', 'pull', '--ff-only']:
                    argv = [*argv[:3], 'vcs', 'pull', '--repo', entry['cwd'], '--role', side,
                            '--code', here, '--branch', 'main', '--login', argv[4]]
                commands.append(dict(entry, cmd=argv))
            expected[side]['commands'] = commands
            if 'delete' in expected[side]:
                expected[side]['delete'] = self.printed_form(expected[side]['delete'], here)
            for c in bound[side]['commands']:
                self.bind_sw(c['cmd'], code)
            if 'delete' in bound[side]:
                self.bind_sw(bound[side]['delete'], code)
        self.assertEqual(canon(paths.node(bound)), canon(expected))
        self.assertEqual(canon(paths.node(self.comparable_calls(native['calls']))),
                         canon(self.comparable_calls(oracle['calls'])))
        return plan

    def test_cleanup_plan_preserves_commands_and_project_selection(self):
        code, store = self.merged_pair()
        plan = self.cleanup_contract(code, store)
        for side, login in [('code', 'me'), ('store', 'other')]:
            pull = plan[side]['commands'][1]['cmd']
            self.assertEqual(pull[1:], ['--project', code, 'vcs', 'pull', '--repo', plan[side]['dir'],
                                      '--role', side, '--code', code, '--branch', 'main', '--login', login])
            self.assertEqual(plan[side]['commands'][2]['cmd'][1:4], ['--project', code, 'pr'])
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
        fakeexe.add_launcher(tool)  # sw starts jj and but by PATHEXT name on Windows (D9)

    def test_cleanup_non_git_plans_preserve_backend_commands(self):
        code, store = self.merged_pair()
        for backend in ['jj', 'gitbutler']:
            with self.subTest(backend=backend):
                self.select_backend(code, store, backend)
                plan = self.cleanup_contract(code, store)
                self.assertEqual(plan['code']['commands'][0]['cmd'][3:5], ['vcs', 'switch'])
                self.assertEqual(plan['code']['delete'][3:5], ['vcs', 'delete-branch'])
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
        code, store = self.merged_pair()
        plan = self.cleanup_contract(code, store)
        real = shutil.which('git').replace('\\', '/')
        log = self.tmp / 'pull-consumer'
        fakeexe.write_python_fake(self.tmp / 'bin' / 'git', f'''
import json, os, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
if args[:1] == ['pull']:
    with Path(os.environ['WF_PULL_LOG']).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps([str(Path.cwd()), os.environ.get('GH_TOKEN'), args]) + '\\n')
    sys.exit(0)
sys.exit(subprocess.call([{real!r}, *args]))
''')
        self.extra_env['WF_PULL_LOG'] = log.as_posix()
        for role in ['code', 'store']:
            entry = plan[role]
            for printed in entry['commands'][:2]:
                # Run the printed checkout and role-bound pull from the printed directory.
                result = subprocess.run(printed['cmd'], cwd=printed['cwd'], env=self.env('me', SPECWRIGHT_HOME=str(self.home)), capture_output=True)
                self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
            printed = entry['commands'][2]
            self.assertEqual(printed['cmd'][1:4], ['--project', code, 'pr'])
            result = self.run_printed(printed)
            self.assertTrue(json.loads(result.stdout)['delete'], result)
            if role == 'code':
                self.git(code, 'checkout', 'feat/x')
                self.git(code, 'commit', '--allow-empty', '-m', 'new work after merged PR')
                self.git(code, 'checkout', 'main')
                before = self.git(code, 'show-ref')
                result = self.run_printed(printed)
                self.assertFalse(json.loads(result.stdout)['delete'], result)
                self.assertEqual(self.git(code, 'show-ref'), before)
            else:
                self.git(store, *entry['delete'][1:])
                self.assertNotIn('refs/heads/feat/x', self.git(store, 'show-ref'))
        lines = log.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        for line, target, token in zip(lines, [code, store], ['tok-me', 'tok-other']):
            cwd, used, arguments = json.loads(line)
            self.assertEqual(Path(cwd).resolve(), Path(target).resolve())
            self.assertEqual((used, arguments), (token, ['pull', '--ff-only']))

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
                    self.mutate(lambda st: st.update(fail=[{'match': self.MATRIX_API_FAILURE,
                                                            'stderr': 'matrix read unavailable'}]))
                    self.run_pair(command, *args, code=3)
                    self.assertFalse(any('POST' in c or 'PATCH' in c or 'DELETE' in c for c in self.last_native_calls))
        # The four pass operations have their record/call/ownership contracts
        # exercised by WorkflowPassMatrix below, in this same native module.
        self.assertEqual(set(cases) | {'pass'}, {'discover', 'ensure-pr', 'link', 'expected', 'pair-state', 'rounds', 'closing-check', 'closed-check', 'merge', 'delete-remote', 'item-issues', 'cleanup-plan', 'branch-check', 'pass'})

    def test_store_credential_lookup_limit_precedes_pr_discovery(self):
        code, store = self.pair_repos()
        self.extra_env['SPECWRIGHT_NET_MAX_BYTES'] = '4096'
        self.mutate(lambda st: st.update(flood=[{'match': r'auth token --hostname github\.com --user other$', 'bytes': 8192}]))
        result = self.side(['expected', '--code', code, '--store', store, '--branch', 'feat/x'], self.tmp)
        self.assertEqual(result['code'], 3, result)
        self.assertEqual(json.loads(result['stdout'])['error'], 'response_too_large')
        self.assertIn(['auth', 'token', '--hostname', 'github.com', '--user', 'other'], result['calls'])
        self.assertFalse(any('/pulls' in arg for argv in result['calls'] for arg in argv), result['calls'])

    def test_rounds_without_feedback_trailers(self):
        code, store = self.pair_repos()
        self.git(code, 'commit', '--allow-empty', '-m', 'address review feedback')
        self.run_pair('rounds', '--code', code, '--store', store, '--branch', 'feat/x', code=0)
        settings = Path(code) / 'openspec' / 'specwright.yaml'
        # An asserted difference: an oversized setting cannot be held, so sw stops with bad_setting (exit 2)
        settings.write_text('pr:\n  max_fix_rounds: 99999999999999999999999999\n', encoding='utf-8')
        d = self.assert_native_refuses('rounds', '--code', code, '--store', store, '--branch', 'feat/x',
                                       code=2, error='bad_setting')
        self.assertIn('pr.max_fix_rounds', d['message'])

    def test_rounds_trailers_and_unreadable_remote(self):
        code, store = self.pair_repos()
        self.git(code, 'remote', 'set-url', 'origin', str(self.tmp / 'missing.git'))
        self.git(code, 'commit', '--allow-empty', '-m', 'fix\n\nFeedback-Round: 2')
        self.run_pair('rounds', '--code', code, '--store', store, '--branch', 'feat/x', code=0)

    def test_rounds_refuses_oversized_feedback_trailers(self):
        # An asserted difference: the frozen workflow keeps an arbitrary-precision trailer, sw cannot hold one past 64 bits
        # and stops as an unknown read (exit 3, lookup_failed) rather than invent a round count
        code, store = self.pair_repos()
        self.git(code, 'remote', 'set-url', 'origin', str(self.tmp / 'missing.git'))
        number = 99999999999999999999999999
        self.git(code, 'commit', '--allow-empty', '-m', f'fix\n\nFeedback-Round: {number}')
        d = self.assert_native_refuses('rounds', '--code', code, '--store', store, '--branch', 'feat/x',
                                       code=3, error='lookup_failed')
        self.assertTrue(d.get('unknown'), d)
        self.assertIn(str(number), d['message'])
        # the largest 64-bit round is still a number both sides count
        self.git(code, 'reset', '--hard', 'HEAD~1')
        top = 9223372036854775807
        self.git(code, 'commit', '--allow-empty', '-m', f'fix\n\nFeedback-Round: {top}')
        d = self.run_pair('rounds', '--code', code, '--store', store, '--branch', 'feat/x', code=0)
        self.assertEqual(d['rounds'], top)

    def test_unknown_read_permits_no_follow_on_mutation(self):
        self.mutate(lambda st: st.update(fail=['api --paginate (--slurp )?repos/o/n/pulls']))
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
    """All four operations: native calls and record effects, and the recorded frozen run of the same case.

    The native run is checked on its own for what a record holds (owner id, write time, checkout, heads, version, the lock
    file left alone, the record kept or deleted); stdout, the `gh` calls, the final fake-gh state and the comment bodies are
    compared with the frozen run's record. Generated owner ids and creation times are bound through each writer's returned
    owner and persisted record.
    """
    snapshots = records.WorkflowRecords.snapshots

    def calls(self):
        return parity.calls_of(self.gh_log, lambda call: call['argv'])

    def clean_doc(self, doc):
        result = {key: value for key, value in doc.items() if key != 'message'}
        if 'path' in result:
            # Native mixed/forward separators must name and open the same record
            path = Path(result['path'])
            self.assertEqual(path.resolve(), self.record_path().resolve())
            self.assertEqual(path.read_bytes(), self.record_path().read_bytes())
            result['path'] = str(path.resolve())
        return result

    def run_native(self, *args, expect=0):
        """sw's run: its parsed one-line document, and the side `oracle_capture.document` reads."""
        result = self.command(args)
        self.assertEqual(result.returncode, expect, f"{args}\n{result.stdout!r}\n{result.stderr!r}")
        side = {'code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr, 'calls': self.calls(),
                'state': self.gh_state.read_bytes()}
        lines = result.stdout.decode('utf-8').strip().splitlines()
        self.assertEqual(len(lines), 1, result)
        return json.loads(lines[0]), side

    def agrees_with_record(self, side, owner_record=None):
        """The native run equals the next recorded frozen run: exit status, `gh` calls, stderr lines, stdout (its free text
        `message` apart), the final fake-gh state and the comment bodies."""
        got = oracle_capture.document(self, side, owner_record)
        want = oracle_capture.recorded(self)[0]
        for doc in (got, want):
            if isinstance(doc['stdout'], dict):
                doc['stdout'].pop('message', None)
        self.assertIsNone(oracle_capture.compare(self, got, want))

    def test_all_four_pass_operations_preserve_records_and_refusals(self):
        from datetime import datetime, timezone
        self.settings('github:\n  login: KintsugiBot\npr:\n  react: false\n')
        intent = self.write_json('matrix-intent.json', self.intent([]))
        self.record_path().unlink(missing_ok=True)
        started = datetime.now(timezone.utc).replace(microsecond=0)
        written, side = self.run_native('pass', 'write', *self.common(), '--intent', intent)
        record = json.loads(self.record_path().read_bytes())
        self.assertRegex(written['owner'], r'^[0-9a-f]{32}$')
        self.assertEqual(record['owner']['id'], written['owner'])
        self.assertEqual(record['written_at'], record['owner']['at'])
        self.assertGreaterEqual(datetime.fromisoformat(record['written_at'].replace('Z', '+00:00')), started)
        self.assertLessEqual(datetime.fromisoformat(record['written_at'].replace('Z', '+00:00')), datetime.now(timezone.utc))
        self.assertEqual(record['heads'], written['heads'])
        self.assertEqual(record['version'], 2)
        self.assertEqual(record['owner']['checkout'], str(self.code).replace('\\', '/'))
        self.agrees_with_record(side, self.record_path().read_bytes())  # the owner printed is the one in the record it wrote
        # A concrete existing record is shared verbatim by the consumers.
        baseline = json.loads(self.record_path().read_bytes())
        baseline['owner']['id'] = 'matrix-owner'
        baseline_bytes = json.dumps(baseline).encode()
        for operation, extra in [
            ('plan', ['--owner', 'matrix-owner', *self.snapshots()]),
            ('adopt', ['--owner', 'adopted', '--from', 'matrix-owner']),
            ('done', ['--owner', 'matrix-owner', *self.snapshots()]),
        ]:
            self.record_path().write_bytes(baseline_bytes)
            result, side = self.run_native('pass', operation, *self.common(), *extra)
            self.clean_doc(result)
            if operation == 'done':
                self.assertTrue(result['deleted'])
                self.assertFalse(self.record_path().exists())
            else:
                raw = self.record_path().read_bytes()
                if operation == 'plan':
                    self.assertEqual(raw, baseline_bytes)
                    self.assertTrue(result['owned'])
                    self.assertTrue(result['delete_record'])
                else:
                    adopted = json.loads(raw)
                    self.assertEqual(adopted['owner']['id'], 'adopted')
                    self.assertEqual(adopted['written_at'], baseline['written_at'])
                    self.assertEqual(adopted['heads'], baseline['heads'])
            self.assertFalse(Path(str(self.record_path())+'.lock').exists())
            self.agrees_with_record(side)
        for operation, extra, expected in [
            ('write', ['--intent', intent], 'record_exists'),
            ('plan', ['--owner', 'foreign', *self.snapshots()], 'record_unreadable'),
            ('adopt', ['--owner', 'new', '--from', 'foreign'], 'not_owner'),
            ('done', ['--owner', 'foreign', *self.snapshots()], 'not_owner'),
        ]:
            protected = b'{partial-record' if operation == 'plan' else baseline_bytes
            self.record_path().write_bytes(protected)
            doc, side = self.run_native('pass', operation, *self.common(), *extra, expect=1)
            self.assertEqual(doc['error'], expected)
            self.clean_doc(doc)
            self.assertEqual(self.record_path().read_bytes(), protected)
            self.assertFalse(Path(str(self.record_path())+'.lock').exists())
            self.agrees_with_record(side)


RETIRED = {
    'test_parity.PairParity.test_git_bash_paths_read_the_same_repo':
        'sw no longer converts a Git Bash path (task 7.3); the absence is checked by evals/cli/test_no_shell.py (task 7.7)',
    'test_parity.WatcherTakeover.test_shim_watcher_takes_over_oracle_watcher':
        'a watcher of one frozen script taking over from another: no frozen script is started',
    'test_workflow_records.WorkflowRecords.test_frozen_script_refuses_a_native_lock_file':
        'a frozen script reading a native lock: no frozen script is started',
    'test_workflow_records.WorkflowRecords.test_native_runtime_has_no_embedded_workflow':
        'it read the script text, which this change deletes',
    'test_workflow_records.WorkflowRecords.test_no_python_3_8_available_to_the_test':
        'the script ran under Python 3.8; sw runs no Python',
    'test_workflow_records.WorkflowRecords.test_pass_write_on_python_3_8':
        'the script ran under Python 3.8; sw runs no Python',
}


class RecordedRuns(unittest.TestCase):
    def test_sw_pr_matches_recorded_oracle_runs(self):
        """Every case the capture of task 6.5 ran is read back by a migrated test of the same name (or the new name
        oracle_capture.CAPTURED_AS gives it), or is retired here with its reason; the cases themselves compare `sw pr`, `sw as`
        and `sw pr reviewers` with the records of the running OS (test_parity.py, test_workflow_parity.py,
        test_workflow_records.py, test_workflow_transport.py)."""
        import importlib
        outcomes = json.loads((oracle_capture.records_dir() / 'outcomes.json').read_text(encoding='utf-8'))
        self.assertTrue(outcomes)
        for case, outcome in sorted(outcomes.items()):
            with self.subTest(case):
                self.assertIn(outcome['status'], ('ok', 'skipped'))
                module, klass, method = case.split('.', 2)
                if case in RETIRED:
                    self.assertTrue(RETIRED[case])
                    continue
                holder = getattr(importlib.import_module(module), klass, None)
                renamed = [new for new, old in oracle_capture.CAPTURED_AS.items() if old == method]
                self.assertTrue(any(holder is not None and getattr(holder, name, None) is not None for name in [method, *renamed]),
                                f'{case} was captured and no test reads it')
