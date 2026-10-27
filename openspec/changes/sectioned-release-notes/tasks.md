# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| releases → Notes list the changes merged since the previous release | One change in the range | evals/release/test_release.py | TestNotes.test_one_change | green (existing; re-run) |
| releases → Notes list the changes merged since the previous release | Several changes in the range | evals/release/test_release.py | TestNotes.test_several_changes_in_order | green (existing; re-run) |
| releases → Notes list the changes merged since the previous release | No change in the range | evals/release/test_release.py | TestNotes.test_empty_range | green (existing; re-run) |
| releases → Notes list the changes merged since the previous release | Backfill in a clone without the tags | evals/release/test_release.py | TestNotes.test_backfill_boundary_counts_origin_only_tags | green (existing; re-run) |
| releases → Notes list the changes merged since the previous release | Backfill with no earlier tag | evals/release/test_release.py | TestNotes.test_backfill_no_tag | green (existing; re-run) |
| releases → Notes list the changes merged since the previous release | No change in the range has a section | evals/release/test_release.py | TestNotes.test_no_sections_gives_todays_notes_byte_for_byte | green (existing behaviour, pinned by a new test) |
| releases → A Release Notes section has one format | Valid section | evals/release/test_release.py | TestReleaseNotesParse.test_valid_section | red |
| releases → A Release Notes section has one format | Unknown heading | evals/release/test_release.py | TestReleaseNotesParse.test_unknown_heading_invalid | red |
| releases → A Release Notes section has one format | Prose under a heading | evals/release/test_release.py | TestReleaseNotesParse.test_prose_under_heading_invalid | red |
| releases → A Release Notes section has one format | No summary or no item | evals/release/test_release.py | TestReleaseNotesParse.test_missing_summary_or_items_invalid | red |
| releases → A Release Notes section has one format | Item over the limit | evals/release/test_release.py | TestReleaseNotesParse.test_item_over_500_invalid | red |
| releases → A Release Notes section tolerates comments, blank lines and wrapped items | Template guidance comment left in | evals/release/test_release.py | TestReleaseNotesParse.test_template_comments_ignored | red |
| releases → A Release Notes section tolerates comments, blank lines and wrapped items | Only a comment | evals/release/test_release.py | TestReleaseNotesParse.test_comment_only_section_has_no_summary | red |
| releases → A Release Notes section tolerates comments, blank lines and wrapped items | Wrapped item | evals/release/test_release.py | TestReleaseNotesParse.test_indented_continuation_joined | red |
| releases → A Release Notes section tolerates comments, blank lines and wrapped items | Unindented line after an item | evals/release/test_release.py | TestReleaseNotesParse.test_unindented_line_after_item_invalid | red |
| releases → A Release Notes section tolerates comments, blank lines and wrapped items | Two-paragraph summary | evals/release/test_release.py | TestReleaseNotesParse.test_two_paragraph_summary_joined | red |
| releases → One proposal's section can be checked before it merges | Valid section | evals/release/test_release.py | TestNotesCommand.test_valid_section_exit_0 | red |
| releases → One proposal's section can be checked before it merges | Two errors | evals/release/test_release.py | TestNotesCommand.test_two_errors_exit_1 | red |
| releases → One proposal's section can be checked before it merges | No section | evals/release/test_release.py | TestNotesCommand.test_no_section_exit_1 | red |
| releases → One proposal's section can be checked before it merges | Missing file | evals/release/test_release.py | TestNotesCommand.test_missing_file_exit_2 | red |
| releases → One proposal's section can be checked before it merges | File over the read bound | evals/release/test_release.py | TestNotesCommand.test_file_over_64kb_invalid | red |
| releases → Notes open with the release summary and group the items | One change with a section | evals/release/test_release.py | TestSectionedNotes.test_one_change_with_section | red |
| releases → Notes open with the release summary and group the items | Exact layout of several groups | evals/release/test_release.py | TestSectionedNotes.test_exact_layout_of_several_groups | red |
| releases → Notes open with the release summary and group the items | Two changes with sections | evals/release/test_release.py | TestSectionedNotes.test_two_changes_items_in_change_order | red |
| releases → Notes open with the release summary and group the items | A change with a section and an older one without | evals/release/test_release.py | TestSectionedNotes.test_mixed_section_and_why_line | red |
| releases → Notes open with the release summary and group the items | Many items | evals/release/test_release.py | TestSectionedNotes.test_over_150_items_count_line | red |
| releases → Notes open with the release summary and group the items | More than 100 changes in the range | evals/release/test_release.py | TestSectionedNotes.test_over_100_changes_keeps_bumping_summary | red |
| releases → The release summary comes from the bumping change | Bumping change archived with another in the same commit | evals/release/test_release.py | TestSectionedNotes.test_summary_from_bump_task_in_same_commit | red |
| releases → The release summary comes from the bumping change | No change has a bump task | evals/release/test_release.py | TestSectionedNotes.test_summary_from_last_section_without_bump_task | red |
| releases → The release summary comes from the bumping change | Bumping change without a valid section | evals/release/test_release.py | TestSectionedNotes.test_summary_from_earlier_when_bumper_has_none | red |
| releases → An item without a reference gets its change's PR | Item without a reference | evals/release/test_release.py | TestSectionedNotes.test_unreferenced_item_gets_pr | red |
| releases → An item without a reference gets its change's PR | Item with its own reference | evals/release/test_release.py | TestSectionedNotes.test_referenced_item_unchanged | red |
| releases → An item without a reference gets its change's PR | Reference only inside a code span | evals/release/test_release.py | TestSectionedNotes.test_code_span_reference_does_not_count | red |
| releases → An item without a reference gets its change's PR | Local merge with no PR | evals/release/test_release.py | TestSectionedNotes.test_no_pr_item_as_written | red |
| releases → An invalid section falls back to the Why line | Unknown heading in an archived proposal | evals/release/test_release.py | TestSectionedPublish.test_invalid_section_falls_back_with_warning | red |
| releases → An invalid section falls back to the Why line | Valid sections | evals/release/test_release.py | TestSectionedNotes.test_valid_sections_empty_warnings | red |
| releases → An invalid section falls back to the Why line | Proposal over the read bound | evals/release/test_release.py | TestSectionedNotes.test_proposal_over_64kb_falls_back_keeps_why | red |
| releases → An invalid section falls back to the Why line | Publish re-run after the tag exists | evals/release/test_release.py | TestSectionedPublish.test_rerun_after_tag_reports_no_warnings | red |
| releases → The bump task writes the release summary | Bump task in a project with releases | evals/release/test_skill_text.py | TestSchemaText.test_bump_task_rewrites_summary_and_checks_notes | red |
| releases → The bump task writes the release summary | Releases off | evals/release/test_skill_text.py | TestSchemaText.test_proposal_instruction_asks_for_section_only_with_releases | red |
| preship-review → The pre-ship review checks the Release Notes section against the diff | Item the diff does not ship | evals/release/test_skill_text.py | TestBriefText.test_false_item_is_p1_docs | red |
| preship-review → The pre-ship review checks the Release Notes section against the diff | Shipped change with no item | evals/release/test_skill_text.py | TestBriefText.test_missing_item_is_p2_docs | red |
| preship-review → The pre-ship review checks the Release Notes section against the diff | Section missing with releases on | evals/release/test_skill_text.py | TestBriefText.test_missing_section_is_p1_with_releases_on | red |
| preship-review → The pre-ship review checks the Release Notes section against the diff | Section breaks the format | evals/release/test_skill_text.py | TestBriefText.test_format_break_is_p1_and_brief_states_the_rules | red |
| preship-review → The pre-ship review checks the Release Notes section against the diff | Releases off | evals/release/test_skill_text.py | TestBriefText.test_check_scoped_to_release_enabled | red |
| design-review-gate → Release Notes edits keep the design review verdict | Release Notes item added during apply | evals/release/test_skill_text.py | TestSchemaText.test_voiding_rule_exempts_release_notes_section | red |
| design-review-gate → Release Notes edits keep the design review verdict | Edit outside the section | evals/release/test_skill_text.py | TestSchemaText.test_voiding_rule_still_voids_other_edits | red |

The pre-ship and design-review-gate rows are agent behaviour driven by instruction text; their tests check that the brief, the schema and the review template state each rule (by key terms, in the style of `evals/release/test_skill_text.py`), the mechanical check the schema allows for behaviour that cannot run in code.

Every test run below uses `python -m unittest` from the repo root: `discover evals/<suite>` for a whole suite, or `-k <name>` for one test.

## 1. ADR 0015 and the architecture file

- [x] 1.1 Write `docs/adr/0015-release-notes-come-from-each-proposal.md` (MADR-short: Status: accepted with today's date, no Supersedes) with the decision under design.md "ADRs → To record during apply": the `## Release Notes` section is the source of release notes, read from the archive at the release commit; the summary is the bumping change's (ticked `release.sh bump --to <V>` task in its archived `tasks.md`, else the last change with a valid section) and is written by the bump task; an invalid, oversized or missing section falls back to the Why line with a warning; section-only edits do not void the design review. Context, a rejected alternative (D1's) and Consequences. Verify: the file exists, and `git diff --stat docs/adr/` shows only the new file.
- [ ] 1.2 Update `openspec/architecture.md`: the `specwright-release` component row (the `notes --proposal` subcommand, `warnings` in `status`/`publish`), the "Release publish" Resource Bounds row (150 items, the 1 000-change parse bound with its size pass, 64 KB per proposal), the "Releases" data-format bullet (the `## Release Notes` section format is parsed by later runs, so changing it is a workflow change), and the in-force index row for 0015. Verify: `grep -n "0015\|notes --proposal\|Release Notes" openspec/architecture.md` shows each, and `discover evals/git-workflow` passes.

## 2. Section parser and `notes --proposal`

- [x] 2.1 Write the failing tests `TestReleaseNotesParse` (the ten format and tolerance rows) in `evals/release/test_release.py`, calling the parser through `release.sh notes --proposal` on temp files so the tests cross the script boundary. Verify: all ten fail (unknown subcommand, exit 2).
- [x] 2.2 Write the failing tests `TestNotesCommand` (the five `notes --proposal` rows). Verify: all five fail for the same reason.
- [x] 2.3 Implement `parse_release_notes(text)` in `release.sh` per the two format requirements: section from `## Release Notes` to the next `##` heading or the end; HTML comments stripped first; summary = text before the first `###`, whitespace collapsed, at most 600 characters; headings `Added`/`Changed`/`Fixed`/`Removed` (case-insensitive) at most once each; items starting `-`, `*` or `+` and a space, indented continuations joined, at most 500 characters; every error collected with its line. Verify: the ten `TestReleaseNotesParse` rows turn green; flip them.
- [ ] 2.4 Add the `notes` subcommand: handled in `main` before `git rev-parse` and `st.gate()` (design D5); size checked before the read (over `MAX_PROPOSAL` → `release_notes_invalid` naming 64 KB); a missing file → exit 2 naming the path; prints `summary`, `items` by heading and each item's `line` (` (#<pr>)` appended literally when it names no reference); exit 1 `release_notes_invalid` with `errors`, or `no_release_notes`. Update the usage line and the header comment. Verify: the five `TestNotesCommand` rows turn green; flip them.
- [ ] 2.5 Document `notes --proposal` and the section format in `skills/specwright-release/SKILL.md` (a `## Release notes` section: format, where the summary comes from, the bump task's rewrite and check, the fallback and `warnings`). Verify: `discover evals/release -p "test_skill_text.py"` passes.
- [ ] 2.6 Check GitHub's release body limit (design.md Resource Bounds, the "Notes text" row) in GitHub's REST docs for `POST /repos/{owner}/{repo}/releases`. If the limit is lower than the ~117 000-character worst case, lower the item cap so it fits and update the design's row and the "Many items" scenario through the drift rule. Verify: the source and limit are named in the task's commit message.

## 3. Sectioned notes in `status` and `publish`

- [ ] 3.1 Write the failing tests in `TestSectionedNotes` and `TestSectionedPublish` (the notes, summary, reference and fallback rows) with fixture repos whose archived proposals carry sections and whose archived `tasks.md` carry ticked bump tasks, plus `TestNotes.test_no_sections_gives_todays_notes_byte_for_byte` (asserting the full notes string for a two-change range without sections). Verify: the new red rows fail on the old notes shape or a missing `warnings` key, and the byte-for-byte test passes.
- [ ] 3.2 Read sections for the last 1 000 changes of the range: one `git cat-file --batch-check` for the sizes of their `proposal.md` and `tasks.md`, then one `cat_batch` of the blobs within `MAX_PROPOSAL`; Why lines are read for the listed no-section changes as today (design D1, D4 and the Resource Bounds row). Find the bumping change by a ticked `release.sh bump --to <V>` task (`- [x]`, any case and spacing, as the apply phase counts done). Verify: `discover evals/release` still passes apart from the rows 3.3 turns green.
- [ ] 3.3 Rewrite `build_notes` for the sectioned shape: summary, then `Added:`/`Changed:`/`Fixed:`/`Removed:` groups and `Changes:` with one blank line between groups and none at the end; ` (#<pr>)` appended to an item with no `#<n>` or `<owner>/<repo>#<n>` outside a code span; 150 items at most with `…and <n> more items` right after the last listed one; today's text unchanged when no change has a valid section. Add `warnings` to `status` and to `publish` (only when publish creates the tag; `[]` otherwise). Update the header comment's notes and JSON lines. Verify: every `TestSectionedNotes`, `TestSectionedPublish` and `TestNotes` row is green, and `discover evals/release` passes; flip them.
- [ ] 3.4 Report `warnings` in `skills/specwright-release/SKILL.md`'s publish report (each change and its error next to the release line). Verify: `discover evals/release -p "test_skill_text.py"` passes.

## 4. Workflow text: proposal, review gate, tasks, apply, pre-ship

- [ ] 4.1 Write the failing text tests `TestSchemaText.test_bump_task_rewrites_summary_and_checks_notes`, `test_proposal_instruction_asks_for_section_only_with_releases`, `test_voiding_rule_exempts_release_notes_section`, `test_voiding_rule_still_voids_other_edits` and `TestBriefText` (five tests) in `evals/release/test_skill_text.py`. Verify: all nine fail.
- [ ] 4.2 In `schemas/specwright/schema.yaml`: the proposal instruction asks for a `## Release Notes` section (format, references, summary) when `release.enabled` is true and says to delete it otherwise; the review instruction's voiding rule exempts an edit confined to that section; the tasks rule's bump task also rewrites the bumping change's summary for the whole release and verifies it with `release.sh notes --proposal`; the apply instruction says a task that changes what ships updates the section in its own commit, and every commit editing the section runs `notes --proposal`. In `schemas/specwright/templates/proposal.md` add the section with its guidance comment; in `schemas/specwright/templates/review.md` add the same exemption to the voiding comment. Verify: the four `TestSchemaText` rows turn green, and `openspec schema validate specwright` (run from the repo root) passes; flip them.
- [ ] 4.3 In `skills/specwright-review/references/brief.md`, add the Release Notes check per design D6 (with `release.enabled` true: missing section, broken format with the format rules stated, item the diff does not ship → P1 `docs`; user-visible change with no item → P2 `docs`; releases off → no finding). In `skills/specwright-commit/SKILL.md`, add the keep-current rule and the `notes --proposal` verification for commits that edit the section, pre-ship and PR fix commits included. Verify: the five `TestBriefText` rows turn green, `discover evals/review-routes` and `discover evals/git-workflow` pass; flip them.

## 5. Integration and release

- [ ] 5.1 Run every suite the M5 exit criterion names: `discover evals/pr-pair`, `evals/git-workflow`, `evals/review-routes`, `evals/update`, `evals/release` and `evals/finish`. Verify: all pass on Windows, and the Test map has no `red` row left.
- [ ] 5.2 Check this repo's real history: `release.sh status --version 0.8.1 --main origin/main` still gives v0.8.1's notes in today's shape (no archived change in its range has a section). Verify: the notes match the published v0.8.1 tag's message (`git tag -l --format='%(contents)' v0.8.1`).
- [ ] 5.3 `release.sh bump --to 0.9.0`, and rewrite this proposal's `## Release Notes` summary to describe the 0.9.0 release as a whole. Verify: `release.sh check` reports 0.9.0, with `VERSION`, the README badge and every `skills/*/SKILL.md` version agreeing, and `release.sh notes --proposal openspec/changes/sectioned-release-notes/proposal.md` exits 0.
- [ ] 5.4 `openspec validate sectioned-release-notes --strict` and `openspec schema validate specwright`. Verify: both pass.

## Workflow follow-up

- Pre-ship review, ship (PR closing #130 with a `Fixes #130` line), watch, archive, finish; then publish 0.9.0, whose notes are the first in the sectioned shape.
