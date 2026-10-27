# Spec Delta

## ADDED Requirements

### Requirement: The release-tag lookup is bounded
The `git ls-remote --tags` that `update.sh` runs to name the highest release tag SHALL run under a 60-second deadline and read at most 32 MiB. When it passes a bound, its process tree SHALL be stopped and the tag SHALL be reported as not named, with the limit (`deadline_exceeded` or `response_too_large`) and the command in the reason. The refusal it belongs to SHALL still be made, and nothing SHALL be written.

#### Scenario: Tags listed in time
- **WHEN** another project's update would leave the store's 0.6 version, and the download's origin lists `v0.6.0` and `v0.6.2` within the deadline
- **THEN** the `store_version` refusal names `v0.6.2`

#### Scenario: Hung tag lookup
- **WHEN** another project's update would leave the store's 0.6 version, and the download's origin never answers `git ls-remote`
- **THEN** `update.sh plan` exits 1 within 60 seconds plus 10 seconds with the `store_version` refusal, whose message says the highest 0.6 release could not be named and names `deadline_exceeded` and `git ls-remote`, no file is written, and no process it started is still running

#### Scenario: Oversized tag list
- **WHEN** the download's origin answers `git ls-remote` with more than 32 MiB
- **THEN** the `store_version` refusal names `response_too_large` and `git ls-remote` as the reason, and no tag is named from a partial list
