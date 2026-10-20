# Spec Delta

## ADDED Requirements

### Requirement: Network commands have a deadline
Every `gh` or `git` network command run by `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh` or `as.sh` SHALL run under a deadline: 120 seconds, or 300 seconds for a paginated read. When the deadline passes, the command and every process it started SHALL be stopped, and the script SHALL report `deadline_exceeded`, naming the command. It SHALL NOT wait for the command.

#### Scenario: GitHub answers in time
- **WHEN** `pr-pair.sh closing-check` runs and every `gh` call answers within its deadline
- **THEN** the check reports its result as before this change, and no `deadline_exceeded` appears

#### Scenario: Hung gh call in pr-pair.sh
- **WHEN** `pr-pair.sh discover` runs and its `gh api` call never answers
- **THEN** the script exits 3 within the deadline plus 10 seconds, with one JSON line holding `"error": "deadline_exceeded"` and a message naming `gh api`, and no `gh` process it started is still running

#### Scenario: Hung gh call in a bash PR script
- **WHEN** `pr-reply.sh` posts a reply and its `gh api` call never answers
- **THEN** the script exits non-zero within the deadline plus 10 seconds, stderr names `deadline_exceeded` and the command, and no temp file it created remains

#### Scenario: Hung credential lookup in as.sh
- **WHEN** `as.sh <login> gh ...` runs and its `gh auth token` lookup never answers
- **THEN** as.sh exits 3 within the deadline plus 10 seconds, names `deadline_exceeded` on stderr, and does not run the fenced command

### Requirement: GitHub responses are bounded
The PR scripts SHALL read at most 32 MiB from any one `gh` or `git` network command, paginated reads included, and at most 50 pages in any cursor loop they drive themselves. Passing either bound SHALL stop the command and be reported as `response_too_large`, naming the command. It SHALL NOT yield a partial result.

#### Scenario: Large but bounded list
- **WHEN** `pr-pair.sh discover` reads a paginated list whose pages total 2 MiB
- **THEN** the script reads all of it and answers as before this change

#### Scenario: Oversized paginated read
- **WHEN** a paginated `gh api` read in `pr-pair.sh` prints more than 32 MiB
- **THEN** the script exits 3 with `"error": "response_too_large"` naming the command, and reports no partial list as the answer

#### Scenario: Reaction loop past its page cap
- **WHEN** `pass plan` looks for a reaction, and the reactions it pages through never contain it and have more than 50 pages
- **THEN** the script exits 3 with `"error": "response_too_large"`, and does not report the reaction as absent
