# Spec Delta

## ADDED Requirements

### Requirement: Store-group pair evidence names the trailers it checks
The grader's `eval-store-group-code-half` and `eval-store-group-store-half` checks SHALL list in their evidence each commit's subject together with its parsed `Specwright-Task` trailers, for both the code and the store commits, as `eval-store-apply-groups` does.

#### Scenario: Only the trailers fail
- **WHEN** the code and store group 1 commits have the right subjects and ticks but no `Specwright-Task` trailers
- **THEN** `eval-store-group-code-half` fails and its evidence shows each commit's subject with an empty task list

#### Scenario: Trailers present
- **WHEN** both group 1 commits carry trailers for 1.1, 1.2 and 1.3
- **THEN** the check passes and its evidence shows `['1.1', '1.2', '1.3']` for each commit

### Requirement: The fake gh state file is replaced whole
Every write of the fake `gh` state file (by the fake `gh`, `snapfix`, or a test helper script) SHALL go to a temporary file in the same directory and then be renamed over the state file. A rename that the OS refuses because a reader holds the file SHALL be retried for up to 5 s, then fail with an error naming the file. A reader SHALL never see an empty or partial file.

#### Scenario: Reader during a write
- **WHEN** one thread reads the state file in a loop while another writes it 200 times
- **THEN** every read parses as JSON and equals one of the written states

#### Scenario: Rename held off
- **WHEN** the rename is refused for longer than 5 s
- **THEN** the write fails with an error naming the state file, and the previous state file is unchanged

### Requirement: A fake gh read never rewrites the state
The fake `gh` SHALL write the state file only when a call changed the state (a mutation, or a `once` failure being used up). A call that only reads SHALL leave the file untouched, so a background watcher's polls cannot overwrite a concurrent test's change.

#### Scenario: Watcher polls while the test mutates
- **WHEN** a test changes the state through `snapfix.mutate` while a watcher's `gh api graphql` read is in flight
- **THEN** the read writes nothing, and the test's change is still in the state file afterwards

#### Scenario: A mutation still saves
- **WHEN** a fake `gh` call adds a PR comment
- **THEN** the state file holds the comment after the call

### Requirement: Every seeded PR body for an issue check has a recorded rendering
Every merged PR body that a git-workflow fixture seeds for the closed-check SHALL be among the bodies the markdown recorder renders and the recordings coverage test checks. The coverage test SHALL fail for a seeded body with no recording.

#### Scenario: Finish fixtures' body
- **WHEN** the finish fixtures seed PR #7 with `Adds greet and farewell.\n\nCloses #12`
- **THEN** `markdown.json` has a recording for it, and `pr-pair.sh closed-check` against that fixture exits with the issue's state instead of `GitHub state unknown: no recorded rendering`

#### Scenario: A new fixture body without a recording
- **WHEN** a fixture seeds a merged PR body that has no recording
- **THEN** the recordings coverage test fails and names that body
