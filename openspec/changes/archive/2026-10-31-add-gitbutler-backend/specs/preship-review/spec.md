## MODIFIED Requirements

### Requirement: The pre-ship review runs when every task is committed
When every task of a change is committed and `review.preship` is not `false`, `specwright-commit` SHALL run the pre-ship review over `<main>...<head>`, where `<head>` is the change branch's tip (HEAD on the Git and jj backends), before it hands off to ship or suggests archive. Store-backed, the review SHALL cover the code range and the store range together. With `review.preship: false`, no pre-ship review SHALL run.

#### Scenario: Default settings
- **WHEN** the last task of a `finish: pr` change is committed and `review.preship` is not set
- **THEN** a pre-ship review of `<main>...<head>` runs, and ship starts only after it passes

#### Scenario: Opted out
- **WHEN** the last task is committed and `review.preship` is `false`
- **THEN** no review runs, and the hand-off to ship happens as before this change

#### Scenario: Store-backed change
- **WHEN** a store-backed change completes with commits in both the code repo and the store
- **THEN** the single review covers both ranges, and its record names the code head and the store head

#### Scenario: GitButler workspace
- **WHEN** the change branch `feat/add-c` is applied in a GitButler workspace beside `feat/b`
- **THEN** the review covers `<main>...<tip of feat/add-c>`, its record names that tip, and no commit of `feat/b` is in the reviewed diff
