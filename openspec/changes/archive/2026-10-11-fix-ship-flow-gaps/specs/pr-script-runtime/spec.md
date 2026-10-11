# Spec Delta

## ADDED Requirements

### Requirement: PR scripts remove their temp files on every exit
Every temp file a PR script creates SHALL be removed when the script exits, whether it succeeds, fails or stops on a structured error. A skill step that tells the agent to write a body or message to a temp file SHALL also tell it to remove that file once the command that reads it has run, whatever that command's outcome.

#### Scenario: Reply posted
- **WHEN** `pr-reply.sh` posts a reply and exits 0
- **THEN** no temp file it created remains

#### Scenario: Post fails
- **WHEN** `pr-reply.sh` has written its reply temp file and the GitHub call that posts it fails
- **THEN** the script exits non-zero and no temp file it created remains

#### Scenario: Pending review stop after the reply
- **WHEN** a thread reply was posted and the following pending-review check exits 2
- **THEN** no temp file it created remains

#### Scenario: Skill steps that write body files
- **WHEN** the `specwright-pr` text tells the agent to write a PR description, review request, reply or issue body to a temp file
- **THEN** the same step tells the agent to remove that file after the command that reads it
