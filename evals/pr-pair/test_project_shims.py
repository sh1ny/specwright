"""Explicit binary selection preserves the caller's repository and stdin."""
import json
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_as_shim import ShimCase
from test_as_sh import AS_SH, bashexe


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
