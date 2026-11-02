# Spec Delta

## ADDED Requirements

### Requirement: An archive-only push skips the code validate
Watch SHALL hand finish, and finish ship, the ready head of each repo (`ready head: <repo>=<sha>`). Before the push, ship SHALL run `review-run.sh archive-only` in the planning repo against its ready head. When it reports `archive_only: true`, ship SHALL skip `pr.validate` for the planning repo, and for a code repo still at its ready head; `planning_store.validate` SHALL still run. Any other result, an error, or no ready head SHALL run `pr.validate`.

#### Scenario: Archive of a reviewed head
- **WHEN** watch reported head `h1` ready and handed `ready head: h1`, the change is archived as commit `h2` whose only change is the archive move and the synced main specs, and `pr.validate` is `make test`
- **THEN** ship pushes `h2` without running `make test`, and reports that validate was skipped for an archive-only push

#### Scenario: Store-backed archive
- **WHEN** the change is store-backed, the archive commit is on the store branch, `archive-only` in the store reports `true`, and `planning_store.validate` is `openspec validate --all --strict`
- **THEN** that command runs in the store before the push, a failure stops the push, and the code repo's `pr.validate` is skipped because its head is still the code ready head it was handed

#### Scenario: Archive commit with other files
- **WHEN** the archive commit also changes `src/app.dart`
- **THEN** `archive-only` reports `archive_only: false`, and `pr.validate` runs before the push

#### Scenario: No ready head
- **WHEN** the archive was started by hand, outside watch, so no ready head was handed over
- **THEN** `pr.validate` runs before the push

#### Scenario: Check fails to run
- **WHEN** `archive-only` exits 3 because git cannot read the commits
- **THEN** `pr.validate` runs before the push, and the report names the `archive-only` error
