# Review

## Metadata

- **Round:** 6
- **Prior round:** Round 5 REVISE: retained OMP tools accepted remote targets; inventories did not prove target denial.
- **Reviewer:** Codex CLI, fresh independent context.
- **Reviewed:** `openspec/changes/native-cli-review/` artifacts `proposal.md`, `specs/review-routes/spec.md`, `design.md`, `tasks.md`, prior `review.md`, and evidence `cli-tools.md`, `omp-native.json`, `codex-native.json`, `codex-observer.patch`, `toml-package.md`; ADRs 0007, 0014, 0022, 0025–0028, 0031, 0033–0035; cited source ranges in `skills/specwright-review/scripts/review-run.sh`, `cli/lib/src/settings/{rules.dart,yaml.dart}`, `cli/lib/src/pr/{policy.dart,settings_commands.dart}`, `cli/lib/src/process/{bounded_run.dart,launch.dart}`; `skills/specwright-pr/scripts/pr-snapshot.sh`; `cli/pubspec.yaml`; `openspec/architecture.md`; workflows `cli.yml`, `sw-build.yml`, `evals.yml`. Repository files were confirmed tracked before opening. Installed `codebase-design/SKILL.md` supplied review guidance. Active instructions and template came from `openspec instructions review --change native-cli-review --json`.
- **Scope:** Whole-plan design review. No files changed and no builds, tests, linters or formatters ran. External source links and scratch paths in the evidence were not followed.

## Findings

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

None.

## Verdict

VERDICT: APPROVE

The round-5 issue is addressed at design level. S5 and D12 preserve the user’s remote-target ban through native fetch-disable and one fixed first-party trusted module, retain `--no-extensions`, refuse user-supplied trusted modules, and explicitly permit provider transport without claiming an OS-wide sandbox.

The retained native events support the prototype’s stated scope: eight paired remote-target errors, successful local operations, zero fixture TCP connections, fatal malformed-module startup, and blocked calls when the hook throws. These observations do not establish production grammar acceptance. A5 and unticked tasks 3.5, 4.10 and 6.5 correctly retain emitted-module behavior tests, black-box integration and full-grammar native replay as completion requirements.

Optional LSP remains accepted with explicit operation and target restrictions. The approved Codex unsafe-alias correction remains consistent across D2, scenarios and tasks. Accepted ADR 0035 remains unchanged; task 1.6 assigns the newly approved boundary to ADR 0036.

Each carried constraint C1–C13 names exactly one durable destination and has a corresponding implementation task. The plan explicitly addresses held-pipe failure, output bounds, private per-run policy ownership, stale heads, concurrent runs, record compatibility and accepted orphan-process/snapshot limitations. No additional evidence-backed blocking consequence was identified.

This approval covers the reviewed plan, not completion of production implementation or acceptance.

## Required Changes

None.

CHANGES_APPLIED: n/a

## Rebuttals

None.