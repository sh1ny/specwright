"""Exercise the FULL change-design rules and owner checkpoint through sw."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_review_run import Base, CHANGE, VERDICT_OK

BRANCH = 'feat/demo'
REVISE = '# Review\n\n## Findings\n- The lock outlives the host.\n\nVERDICT: REVISE\nCHANGES_APPLIED: n/a\n'
CONDITIONAL = '# Review\n\nVERDICT: APPROVE_WITH_CHANGES\nCHANGES_APPLIED: no\n\n## Required Changes\nWait for exit.\n'


class TestDesignReview(Base):
    def setUp(self):
        super().setUp()
        root = self.code / 'openspec' / 'changes' / CHANGE
        root.mkdir(parents=True)
        self.review = root / 'review.md'
        self.config = self.code / 'openspec' / 'specwright.yaml'
        self.prompt = self.put('brief.md', 'Read the unchanged checklist and template.\n')

    def settings_for(self, *, rules='', limit=''):
        self.install('claude')
        self.config.write_text(f'review:\n  order: [claude]\n{rules}{limit}', encoding='utf-8')

    def full_args(self):
        return ['--kind', 'design', '--change-review', '--change', CHANGE, '--out', self.review, '--branch', BRANCH]

    def scratch(self, expect=0):
        return self.script('record', '--scratch', *self.full_args(), expect=expect)

    def complete(self, started, text, repairs=None, expect=0):
        path = Path(started['scratch'])
        path.write_bytes(text.encode('utf-8'))
        return self.script('record', *self.full_args(), '--result', path, '--route', 'subagent',
                           *([] if repairs is None else ['--repairs', repairs]), expect=expect)

    def step(self, *args, expect=0):
        return self.script('design-step', '--out', self.review, *args, expect=expect)

    def choose(self, round_, choice, detail=None, expect=0):
        return self.step('--round', round_, '--choice', choice,
                         *([] if detail is None else ['--detail', detail]), expect=expect)

    def run_full(self, answer, expect=0):
        self.stdout_file('claude', json.dumps({'type': 'result', 'result': answer}))
        return self.script('run', *self.full_args(), '--route', 'claude', '--prompt-file', self.prompt, expect=expect)

    def test_full_rules_use_branch_blobs_on_both_routes(self):
        self.settings_for(rules='  standing_rules: [rules/windows.md, rules/order.md]\n')
        rule = 'Wait for the exit event.\nFull café text.\n'
        self.commit(self.code, {'rules/windows.md': rule, 'rules/order.md': 'Order before timing.\n'}, 'rules')
        self.git(self.code, 'checkout', '-q', '-b', 'other-branch')
        self.commit(self.code, {'rules/windows.md': 'Rule committed on the checked-out branch.\n'}, 'other rules')
        (self.code / 'rules/windows.md').write_text('uncommitted replacement', encoding='utf-8')
        self.run_full(REVISE)
        packet = self.runs('claude')[-1]['stdin']
        subagent = self.scratch()['standing_requirements']
        self.assertIn('## Standing requirements (binding)', subagent)
        self.assertIn('existing tests the design preserves', subagent)
        self.assertIn(subagent, packet)
        self.assertIn(rule, subagent)
        self.assertLess(subagent.index(rule), subagent.index('Order before timing.'))
        self.assertNotIn('Rule committed on the checked-out branch.', packet)
        self.assertNotIn('uncommitted replacement', packet)

    @unittest.skipIf(sys.platform == 'win32', 'Win32 normalizes trailing spaces in paths')
    def test_reads_rules_in_repository_with_trailing_space(self):
        self.settings_for(rules='  standing_rules: [rules/windows.md]\n')
        self.commit(self.code, {'rules/windows.md': 'Wait for the exit event.\n'}, 'rules')
        renamed = self.code.with_name('code ')
        self.code.rename(renamed)
        self.review = renamed / self.review.relative_to(self.code)
        self.code = renamed
        self.assertIn('Wait for the exit event.', self.scratch()['standing_requirements'])

    def test_no_rules_leaves_both_briefs_unchanged(self):
        for setting in ('', '  standing_rules: []\n'):
            with self.subTest(setting=setting):
                self.settings_for(rules=setting)
                self.run_full(VERDICT_OK)
                self.assertEqual(self.runs('claude')[-1]['stdin'], self.prompt.read_text(encoding='utf-8'))
                self.assertNotIn('standing_requirements', self.scratch())

    def test_bad_rule_fails_before_reviewer(self):
        self.settings_for(rules='  standing_rules: [not-tracked.md]\n')
        (self.code / 'not-tracked.md').write_text('not versioned', encoding='utf-8')
        self.assertEqual(self.run_full(REVISE, expect=1)['error'], 'bad_design_rule')
        self.assertEqual(self.scratch(expect=1)['error'], 'bad_design_rule')
        self.assertFalse(self.calls('claude'))
        self.assertFalse(self.review.exists())

    def test_default_checkpoint_keeps_revise(self):
        for n in (1, 2, 3):
            self.complete(self.scratch(), REVISE, f'Repaired item {n}.')
            state = self.step()
            self.assertEqual(state['round'], n)
            self.assertEqual(state['status'], 'owner_checkpoint' if n == 3 else 'review')
        before = self.review.read_bytes()
        self.assertEqual(self.scratch(expect=1)['error'], 'owner_checkpoint')
        self.assertEqual(self.review.read_bytes(), before)
        self.assertIn(b'VERDICT: REVISE', before)
        self.assertIn(b'Repaired item 1.', before)
        self.assertIn(b'Repaired item 3.', before)

    def test_explicit_null_round_limit_stops_before_dispatch(self):
        self.settings_for(limit='  design_max_rounds: null\n')
        for result in (self.step(expect=1), self.scratch(expect=1), self.run_full(REVISE, expect=1)):
            self.assertEqual(result['error'], 'bad_design_setting')
            self.assertIn('review.design_max_rounds must be a positive integer', result['message'])
        self.assertFalse(self.calls('claude'))
        self.assertFalse(self.review.exists())

    def test_prior_pass_does_not_reset_the_round_budget(self):
        design = self.review.with_name('design.md')
        design.write_text('TIER: FULL\n\nOriginal design.\n', encoding='utf-8')
        self.complete(self.scratch(), REVISE)
        self.complete(self.scratch(), VERDICT_OK, 'Wait on the child exit event.')
        self.assertEqual(self.step()['verdict'], 'APPROVE')
        design.write_text('TIER: FULL\n\nChanged lock lifecycle in the same scope.\n', encoding='utf-8')
        self.complete(self.scratch(), REVISE)
        state = self.step()
        self.assertEqual((state['round'], state['scope_round'], state['status'], state['verdict']),
                         (3, 3, 'owner_checkpoint', 'REVISE'))
        self.assertEqual(self.scratch(expect=1)['error'], 'owner_checkpoint')

    def test_scoped_pass_survives_replacement_and_hands_back(self):
        self.settings_for(limit='  design_max_rounds: 1\n')
        self.complete(self.scratch(), REVISE)
        before = self.review.read_bytes().split(b'<!-- specwright-design-progress -->')[0]
        self.choose(1, 'scoped-pass', 'Check only the lock lifetime.')
        self.assertEqual(self.step()['choice'], 'scoped-pass')
        self.assertTrue(self.review.read_bytes().startswith(before))
        self.complete(self.scratch(), 'Not a verdict.', expect=3)
        self.assertEqual(self.step()['choice'], 'scoped-pass')
        self.complete(self.scratch(), REVISE, 'Wait on the child exit event.')
        state = self.step()
        self.assertEqual((state['round'], state['status'], state['verdict']), (2, 'owner_checkpoint', 'REVISE'))
        self.assertIn(b'Check only the lock lifetime.', self.review.read_bytes())

    def test_scoped_repairs_require_reviewing_the_other_findings(self):
        self.settings_for(limit='  design_max_rounds: 1\n')
        both = CONDITIONAL + 'Keep the recovered files.\n'
        self.complete(self.scratch(), both)
        self.choose(1, 'scoped-pass', 'Repair only the lock lifetime.')
        before = self.review.read_bytes()
        scratch = self.scratch()
        partial = CONDITIONAL.replace('CHANGES_APPLIED: no', 'CHANGES_APPLIED: yes')
        self.assertEqual(self.complete(scratch, partial, expect=3)['error'], 'invalid_output')
        self.assertEqual(self.review.read_bytes(), before)
        self.assertEqual(self.step()['choice'], 'scoped-pass')
        self.assertIn('entire current design', scratch['review_instruction'])
        self.assertIn('all still-applicable open findings', scratch['review_instruction'])

        self.run_full(REVISE.replace('The lock outlives the host.', 'The recovered files are lost.'))
        self.assertIn(scratch['review_instruction'], self.runs('claude')[-1]['stdin'])
        self.assertEqual(self.step()['status'], 'owner_checkpoint')
        self.assertIn(b'The recovered files are lost.', self.review.read_bytes())

    def test_scope_change_records_reason_and_restarts_round_budget(self):
        self.settings_for(limit='  design_max_rounds: 2\n')
        self.run_full(REVISE)
        self.run_full(CONDITIONAL)
        self.assertEqual(self.step()['status'], 'owner_checkpoint')
        self.choose(2, 'scope-change', expect=2)
        self.choose(2, 'scope-change', 'Do not change child execution.')
        self.assertEqual(self.step()['verdict'], 'APPROVE_WITH_CHANGES')
        before = self.review.read_bytes()
        confirmed_old_scope = CONDITIONAL.replace('CHANGES_APPLIED: no', 'CHANGES_APPLIED: yes')
        self.assertEqual(self.run_full(confirmed_old_scope, expect=3)['error'], 'invalid_output')
        self.assertEqual(self.review.read_bytes(), before)
        self.assertEqual(self.step()['choice'], 'scope-change')
        self.assertIn('entire current design', self.runs('claude')[-1]['stdin'])
        self.run_full(REVISE)
        state = self.step()
        self.assertEqual((state['round'], state['scope_round'], state['status']), (3, 1, 'review'))
        self.assertIn(b'Do not change child execution.', self.review.read_bytes())

    def test_stop_keeps_checkpoint_unresolved(self):
        self.settings_for(limit='  design_max_rounds: 1\n')
        self.complete(self.scratch(), REVISE)
        self.choose(1, 'stop')
        state = self.step()
        self.assertEqual((state['status'], state['verdict']), ('stopped', 'REVISE'))
        self.assertEqual(self.scratch(expect=1)['error'], 'stopped')
        self.assertIn(b'`stop`', self.review.read_bytes())

    def test_stop_survives_a_missing_blank_line_before_the_progress_marker(self):
        self.settings_for(limit='  design_max_rounds: 3\n')
        legacy_round_one = REVISE.replace('# Review\n', '# Review\n\n- **Round:** 1\n')
        for _ in range(3):
            self.complete(self.scratch(), legacy_round_one)
        self.choose(3, 'stop')
        self.assertEqual(self.step()['status'], 'stopped')
        stopped_record = self.review.read_bytes()
        padded = stopped_record.replace(
            b'<!-- specwright-design-progress -->\n',
            b'<!-- specwright-design-progress --> \t\n',
        )
        self.review.write_bytes(padded)
        state = self.step()
        self.assertEqual((state['status'], state['verdict']), ('stopped', 'REVISE'))
        self.assertEqual(self.scratch(expect=1)['error'], 'stopped')
        self.assertEqual(self.review.read_bytes(), padded)

        marker = b'<!-- specwright-design-progress -->'
        body, footer = stopped_record.split(marker)
        damaged = body.rstrip(b'\n') + b'\n' + marker + footer
        self.review.write_bytes(damaged)

        self.assertEqual(self.step(expect=1)['error'], 'bad_design_progress')
        self.assertEqual(self.scratch(expect=1)['error'], 'bad_design_progress')
        self.assertEqual(self.review.read_bytes(), damaged)


if __name__ == '__main__':
    unittest.main()
