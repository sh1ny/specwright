# Spec Delta

## ADDED Requirements

### Requirement: A reply is never posted without its body
`pr-reply.sh` SHALL check that the body file of a `thread` or `comment` reply exists, is readable and is not empty, and that the reply with its marker was written in full, before any GitHub call. When a check fails, it SHALL exit non-zero, name the body file on stderr, and post, resolve and react to nothing.

#### Scenario: Body file present
- **WHEN** feedback answers a thread with a non-empty, readable body file
- **THEN** the reply holds that body followed by the handled marker, and the exit status is 0

#### Scenario: Body file missing
- **WHEN** `pr-reply.sh` is called with a body file path that does not exist
- **THEN** the exit status is non-zero, stderr names the path, and no GitHub request is made

#### Scenario: Body file empty
- **WHEN** the body file exists and is empty
- **THEN** the exit status is non-zero, stderr names the path, and no GitHub request is made

#### Scenario: Body file unreadable
- **WHEN** the body file exists but cannot be read
- **THEN** the exit status is non-zero, stderr names the path, and no GitHub request is made
