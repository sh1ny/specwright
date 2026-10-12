## MODIFIED Requirements

### Requirement: Prerequisites are stated and checked at install
The README prerequisites and install Step 1 SHALL list `bash` with a POSIX userland, `git` and Python 3.8+ as core requirements (the review scripts run every design and pre-ship review), and `gh` 2.40+ as a requirement of the PR skills. Install SHALL check each one. A missing core requirement SHALL stop the install. A missing PR requirement SHALL be reported as `PR workflow not ready: <missing>` without blocking the install. `specwright-pr` SHALL state the same script dependencies.

#### Scenario: All prerequisites present
- **WHEN** install runs where bash, git, gh 2.45 and Python 3.11 are available
- **THEN** Step 1 passes and the final report shows no `PR workflow not ready` line

#### Scenario: Python missing
- **WHEN** install runs where neither `python3` nor `python` reports version 3.8 or later
- **THEN** the install stops at Step 1 and tells the user to install Python 3.8 or later

#### Scenario: gh missing
- **WHEN** install runs where `gh` is missing or older than 2.40, and every core requirement is present
- **THEN** the install completes and its report includes `PR workflow not ready: gh 2.40+`
