# Spec Delta

## MODIFIED Requirements

### Requirement: Frozen-oracle evals are migrated before the cutover
Every eval that runs a frozen script, a shim or the shipped scripts directory SHALL be moved, in the commits before the cutover, to one of: recorded CLI runs of the frozen side; recorded state in both directions; or outcome checks that run what `sw` prints. A CI check SHALL then fail on any eval naming a removed script. The one exception is the spec sweep guard, `evals/runner/test_spec_retired_names.py`: it names the retired scripts only to find them in spec text, and it runs none of them.

#### Scenario: Feedback records both ways after the cutover
- **WHEN** the feedback-record interoperability cases run on the script-free tree
- **THEN** the native reader resumes from the recorded bytes the frozen writer produced; a native-written record is UTF-8 with LF line ends, its generated owner id, write time, checkout and host are checked for form and for their relation to the run, and its other parsed fields equal the frozen-reader-accepted fixture once those are normalized; and no case starts a frozen script

#### Scenario: Finish parity becomes outcome checks
- **WHEN** the finish and GitButler undo parity cases run on the script-free tree
- **THEN** each runs the printed `steps` and checks the resulting refs, index and files, each refusal case checks its error and exit status, and none compares a document with the frozen planner's

#### Scenario: An eval left on a removed script
- **WHEN** after the cutover an eval still copies or runs `vcs.sh`, `as.sh`, `sw-path.sh`, `bounded.py` or a frozen script that needs them
- **THEN** the CI check fails, naming the eval file and the script

#### Scenario: The spec sweep guard names the retired scripts
- **WHEN** the CI check scans `evals/runner/test_spec_retired_names.py`, whose name list and allowlist hold the retired names as string literals
- **THEN** it reports nothing for that file, and any other eval file that names a removed script still fails the check
