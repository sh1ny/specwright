# Spec Delta

## ADDED Requirements

### Requirement: Stress-tier evals are marked by kind
A git-workflow eval in the stress tier SHALL carry `"stress"` in `evals.json` with one of the values `watch`, `light-apply` or `implementer`. Each kind SHALL have at least one marked eval. A test SHALL fail when a kind has none, or when a mark has another value.

#### Scenario: Every kind is covered
- **WHEN** the eval-list test reads `evals/git-workflow/evals.json`
- **THEN** it finds at least one eval marked `watch`, one marked `light-apply` and one marked `implementer`

#### Scenario: A kind loses its last mark
- **WHEN** the only eval marked `implementer` has its mark removed
- **THEN** the eval-list test fails and says that no stress eval covers `implementer`

#### Scenario: An unknown kind
- **WHEN** an eval is marked `"stress": true`
- **THEN** the eval-list test fails and names that eval and the value

### Requirement: The tier comparison names every difference
`evals/git-workflow/tiers.py <iteration-dir> --base <config> --cheap <config>` SHALL print one JSON document giving each stress eval's mean pass rate per configuration. It SHALL name each eval whose rates differ, with the assertions that pass in one configuration only, and each eval with no readable grading in a configuration. It SHALL exit 0 only when nothing differs or is missing, else 1. Unmarked evals SHALL be skipped.

#### Scenario: Same grades
- **WHEN** every stress eval passes all its assertions in both configurations
- **THEN** the report lists no differences and nothing missing, and the exit status is 0

#### Scenario: The cheap configuration fails an assertion
- **WHEN** `eval-watch-agent-merge` passes under the base configuration and fails one assertion under the cheap one
- **THEN** the report names `eval-watch-agent-merge`, both pass rates and the failed assertion's text, and the exit status is 1

#### Scenario: A grading is missing or unreadable
- **WHEN** a stress eval has a `grading.json` for the base configuration, and for the cheap one it has none or one that is not valid JSON
- **THEN** the report lists that eval as missing for the cheap configuration, never as the same grade, and the exit status is 1
