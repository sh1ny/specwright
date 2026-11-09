"""Explicit binary selection preserves the caller's repository and stdin."""
import json
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_as_shim import ShimCase
from test_as_sh import AS_SH, bashexe
from test_pr_shims import PAIR
import test_pr_pair as original


class ProjectShims(ShimCase):
    def as_sh(self, cwd, *args, env=None, stdin=None):
        # Native output is UTF-8; Windows' default ANSI decoder is unsuitable
        # for this exact argument/stdio test.
        e = self.env()
        e.update(env or {})
        return subprocess.run([bashexe.bash(), str(AS_SH), *args], cwd=cwd,
                              capture_output=True, text=True, encoding='utf-8',
                              env=e, input=stdin, timeout=60)

    def setUp(self):
        super().setUp()
        (self.store / 'openspec' / '.specwright' / 'VERSION').unlink()

    def test_fenced_store_call_selects_the_code_project(self):
        out = self.tmp / 'where'
        args = ['a b', '', '$x *', 'é']
        r = self.as_sh(self.store, '--project', str(self.code), 'KintsugiBot',
                       *self.bash_command('pwd -P > "$1"; printf "%s|" "$GH_TOKEN" "${@:2}"; cat',
                                          out.as_posix(), *args), stdin='input\n')
        self.assertEqual((r.returncode, r.stdout), (0, 'tok-k|a b||$x *|é|input\n'), r.stderr)
        self.assertTrue(out.read_text().strip().replace('\\', '/').endswith('/store'))
        self.assertEqual({c['env']['GH_TOKEN'] for c in self.gh_calls()
                          if c['argv'][0] == 'api'}, {'tok-k'})

    def test_selected_project_does_not_change_target_validation(self):
        self.git(self.store, 'remote', 'set-url', 'origin', 'https://secret@github.com/o/store.git')
        r = self.as_sh(self.store, '--project', str(self.code), 'KintsugiBot', 'echo', 'ran')
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn('https://***@github.com/o/store.git', r.stderr)
        self.assertNotIn('secret', r.stderr)
        self.assertNotIn('ran', r.stdout)

    def test_missing_selected_binary_refuses_without_fallback(self):
        r = self.as_sh(self.code, '--project', str(self.store), 'KintsugiBot', 'echo', 'ran')
        self.stop_document(r)
        self.assertEqual(self.gh_calls(), [])

    def test_malformed_fence_project_prefix_is_refused(self):
        for prefix in [('--project',), ('--project', ''),
                       ('--project', str(self.code), '--project', str(self.code))]:
            with self.subTest(prefix=prefix):
                r = self.as_sh(self.store, *prefix)
                self.assertEqual((r.returncode, r.stdout), (2, ''), r.stderr)
                self.assertIn('usage:', r.stderr)
        self.assertEqual(self.gh_calls(), [])

    def test_relative_project_and_default_discovery(self):
        selected = self.as_sh(self.store, '--project', '../code', '--resolve')
        default = self.as_sh(self.code, '--resolve')
        self.assertEqual((selected.returncode, selected.stdout), (0, 'sh1ny\n'), selected.stderr)
        self.assertEqual((default.returncode, default.stdout), (0, 'sh1ny\n'), default.stderr)

    def pair_run(self, *args, cwd=None, env=None):
        environment = {**self.env(), **(env or {})}
        return subprocess.run([bashexe.bash(), str(PAIR), *map(str, args)],
                              cwd=cwd or self.store, capture_output=True, text=True,
                              encoding='utf-8', env=environment, timeout=60)

    def test_workflow_command_starts_in_a_store(self):
        # The outer fence checks the store; the nested pair shim independently
        # selects the code binary. Neither selector changes the target or login.
        self.git(self.store, 'remote', 'set-url', 'origin', 'https://github.com/o/store.git')
        self.state(user='sh1ny', tokens={'sh1ny': 'tok-s', 'KintsugiBot': 'tok-k'},
                   repos={'o/store': {'pulls': []}})
        r = self.as_sh(self.store, '--project', str(self.code), 'KintsugiBot',
                       bashexe.bash(), str(PAIR), '--project', '../code',
                       'discover', '--repo', 'o/store', '--branch', 'feat/a')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)['prs'], [])
        calls = self.gh_calls()
        self.assertTrue(calls)
        self.assertEqual({c['env']['GH_TOKEN'] for c in calls if c['argv'][0] == 'api'}, {'tok-k'})
        self.assertEqual({Path(c['cwd']).resolve() for c in calls}, {self.store.resolve()})
        # Identity's positional directory remains the store's, rather than the
        # explicitly selected code checkout.
        identity = self.pair_run('--project', '../code', 'identity', str(self.store))
        self.assertEqual((identity.returncode, json.loads(identity.stdout)['repo']), (0, 'o/store'), identity.stderr)

    def test_selected_project_cannot_resolve_a_binary(self):
        # The --code argument names a usable fallback candidate, but an explicit
        # selector without VERSION must fail instead of consulting it.
        r = self.pair_run('--project', str(self.store), 'context', '--code', str(self.code), cwd=self.code)
        self.stop_document(r)
        self.assertEqual(self.gh_calls(), [])

    def test_malformed_project_prefix_is_refused(self):
        for prefix in [('--project',), ('--project', ''),
                       ('--project', str(self.code), '--project', str(self.code))]:
            with self.subTest(prefix=prefix):
                r = self.pair_run(*prefix)
                self.assertEqual((r.returncode, json.loads(r.stdout)['error']), (2, 'usage'), r.stderr)
        self.assertEqual(self.gh_calls(), [])

    def test_cleanup_commands_carry_the_explicit_project(self):
        # Use the existing real-repository cleanup fixture, but execute each
        # printed branch-check through the completed production shim. The pull
        # is checked as an argv contract; it must never contact GitHub here.
        fixture = original.Cleanup('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.add_pull(original.CODE, 5, state='closed', merged=fixture.merged, sha=fixture.tip(fixture.code))
        fixture.add_pull(original.STORE, 2, state='closed', merged=fixture.merged, sha=fixture.tip(fixture.store))
        (fixture.store / 'openspec/.specwright/VERSION').unlink()
        plan = fixture.plan()
        code = str(fixture.code).replace('\\', '/')
        for side in ('code', 'store'):
            entry = plan[side]
            pull, check = (row['cmd'] for row in entry['commands'][1:])
            self.assertEqual(pull[2:5], ['--project', code, 'KintsugiBot'])
            self.assertEqual(pull[5:], ['git', 'pull', '--ff-only'])
            self.assertEqual(check[:4], ['pr-pair.sh', '--project', code, 'branch-check'])
            self.assertEqual(check[4:], ['--dir', entry['dir'], '--branch', original.BRANCH,
                                        '--main', 'main', '--head', fixture.tip(getattr(fixture, side))])
            self.assertTrue(all(row['cwd'] == entry['dir'] for row in entry['commands']))
            result = subprocess.run([bashexe.bash(), str(PAIR), *check[1:]], cwd=entry['dir'],
                                    capture_output=True, text=True, env=fixture.env(), timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)['delete'])
