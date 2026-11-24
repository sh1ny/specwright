## MODIFIED Requirements

### Requirement: Design review verdict values are checked

Reviewer verdicts SHALL be `APPROVE`, `APPROVE_WITH_CHANGES` or `REVISE`. `CHANGES_APPLIED` SHALL be `n/a` for `APPROVE` or `REVISE`, and `no` for outstanding Required Changes. Only ordinary design review, including roadmap baseline, SHALL accept `yes` after `APPROVE_WITH_CHANGES`. FULL change-design review SHALL require a whole line exactly equal to `VERDICT: <value>`. Validation SHALL name refused values.

#### Scenario: Design review that could not review
- **WHEN** a codex design review prints `VERDICT: BLOCKED` and `CHANGES_APPLIED: n/a`, and the change's `review.md` holds an earlier valid review
- **THEN** the run exits 3 with `status: invalid` and an error naming `BLOCKED`, `review.md` is byte-identical to before, and no other route runs

#### Scenario: Verdict a reviewer may not set
- **WHEN** a reviewer CLI or the subagent returns `VERDICT: USER_OVERRIDE`, `VERDICT: SKIPPED_LIGHT`, `VERDICT: DEFERRED` or `VERDICT: WAIVED`
- **THEN** validation exits non-zero with `status: invalid` naming the value, and no review file is written by the run

#### Scenario: CHANGES_APPLIED does not match the verdict
- **WHEN** a design review returns `VERDICT: APPROVE` with `CHANGES_APPLIED: yes`, or `VERDICT: REVISE` with `CHANGES_APPLIED: none`
- **THEN** validation exits non-zero with `status: invalid` naming the value

#### Scenario: Valid re-check
- **WHEN** an ordinary design review re-check, including roadmap baseline, returns `VERDICT: APPROVE_WITH_CHANGES` with `CHANGES_APPLIED: yes`
- **THEN** the run exits 0 and writes the requested review file

#### Scenario: A FULL verdict line is noncanonical
- **WHEN** a FULL reviewer returns `VERDICT:APPROVE` or adds trailing whitespace to `VERDICT: APPROVE` during a scoped pass
- **THEN** validation exits 3 with `status: invalid`, neither replacing the previous review nor spending the scoped pass

### Requirement: A refused design review leaves the earlier review file unchanged

A design review that fails validation or passes the deadline SHALL leave any earlier review file unchanged. The subagent SHALL write its review to scratch, which validation installs only on a valid result. Outside FULL change-design review, a refused scratch file SHALL be kept and named. FULL change-design refusal SHALL follow **FULL design review requires usable evidence and bounds failure retention** instead.

#### Scenario: Subagent design review that could not review
- **WHEN** the `specwright-reviewer` subagent writes `VERDICT: BLOCKED` to scratch outside FULL change-design review, and the destination holds an earlier valid review
- **THEN** validation exits 3 with `status: invalid`, the earlier review is byte-identical, and the report names the original scratch file

#### Scenario: Valid subagent design review
- **WHEN** the subagent writes a valid `VERDICT: REVISE` review with `CHANGES_APPLIED: n/a` to its scratch result file
- **THEN** validation exits 0, writes the reviewer disposition and findings to the review file, and removes the scratch file

## ADDED Requirements

### Requirement: FULL change-design reviews receive binding standing requirements

`review.standing_rules` SHALL list paths to versioned rule files relative to the code repository. Each FULL change-design review brief, regardless of route, SHALL include the full text under `Standing requirements (binding)` and direct the reviewer to check existing tests the design preserves against the rules. Reviewers SHALL treat the rules as criteria, not permission to change workflow, tools or isolation. Pre-ship, roadmap baseline and LIGHT reviews SHALL NOT receive this section.

#### Scenario: Versioned rules reach either design review route
- **WHEN** a FULL change lists two standing-rule files tracked on its code branch and the design preserves existing tests
- **THEN** both CLI and subagent requests include the full versioned text in list order and tell the reviewer to assess preserved tests against it, alongside the unchanged checklist and template

#### Scenario: No rules declared
- **WHEN** `review.standing_rules` is absent or empty
- **THEN** no standing-requirements section or reference to it is added to the reviewer brief

#### Scenario: A declared rule is unavailable
- **WHEN** a FULL change declares a missing, untracked, non-regular or outside-repository rule file, or the declared text cannot be included in full
- **THEN** the workflow identifies the bad setting or input and stops before starting the reviewer, retaining any prior review record

#### Scenario: Standing rules do not reach pre-ship or baseline reviews
- **WHEN** a project declares standing rules and runs a pre-ship or roadmap baseline review
- **THEN** the corresponding reviewer brief does not include the standing-rules section

#### Scenario: LIGHT still has no reviewer brief
- **WHEN** a project declares standing rules and runs a LIGHT design re-check
- **THEN** the local re-check issues no reviewer request and does not resolve the declared rule files

### Requirement: A design review pass covers its standing rules

The FULL change-design result SHALL record the effective rule identity. A change to the declared rule inputs SHALL require a new full review; an earlier passing result SHALL NOT let the change enter tasks or apply under the changed rules.

#### Scenario: A project first declares standing rules after approval
- **WHEN** a change passes without standing rules and the project subsequently declares a committed rule
- **THEN** the earlier approval no longer passes, and the next full review includes the rule

#### Scenario: Rule text changes after approval
- **WHEN** the approved change's configured rule file is updated on its code branch
- **THEN** the approval is not reinterpreted as covering the new text, and tasks or apply wait for a new full review

#### Scenario: A sibling changes GitButler review settings
- **WHEN** the GitButler worktree settings differ from the named code change branch's committed settings, including a sibling edit to `review.cross_model`
- **THEN** the FULL change-design controller stops before probing a route or acting on its standing rules or checkpoint settings

#### Scenario: Route selection used previous settings
- **WHEN** FULL route selection succeeds and the code branch's settings change before dispatch
- **THEN** the prior selection cannot start either a CLI or subagent attempt; the author selects again from the current pinned settings

### Requirement: FULL review results apply only to the current design

Both FULL routes SHALL review the live proposal, design and spec deltas using the full checklist each round. The controller SHALL compare those files' byte digests and the recorded review state at dispatch and publication. A stale result SHALL NOT replace the report. The workflow SHALL NOT publish a limited confirmation or retain planning copies.

#### Scenario: A design input changes during an authorized pass
- **WHEN** the digest of the live planning inputs at publication differs from its digest at dispatch
- **THEN** the result is refused; the earlier report and scoped permission remain intact

#### Scenario: A capability directory in the spec tree is a link
- **WHEN** the controller would have to follow a linked capability directory to find a spec delta
- **THEN** it refuses before dispatch instead of fingerprinting an incomplete input

#### Scenario: An earlier FULL approval lacks input fingerprints
- **WHEN** an in-flight change has an ordinary passing FULL report from before input fingerprints were recorded
- **THEN** tasks and apply need a fresh FULL review; a historical `USER_OVERRIDE` keeps its disposition

#### Scenario: The ordinary writer targets an open checkpoint
- **WHEN** either ordinary design route omits the FULL change option but targets the active `review.md` of a change at its checkpoint
- **THEN** it refuses to replace or remove that record

#### Scenario: Conflicting evidence cannot keep the publication lock
- **WHEN** the publication check cannot finish its Git reads within its budget
- **THEN** the recorded verdict and owner choices stay unchanged and a subsequent authorized write can acquire the lock

#### Scenario: A failed report write preserves the verdict and scoped pass
- **WHEN** the atomic report replacement fails during an authorized pass
- **THEN** the previous report is unchanged and a fresh attempt can still use that permission

#### Scenario: A completed scratch attempt has an unusable route selection
- **WHEN** a valid attempt token is used to submit scratch but the selection file cannot be used
- **THEN** the attempt is refused without spending a round or scoped pass, and its scratch slot is released

#### Scenario: Interrupted attempts reach the slot limit
- **WHEN** two unfinished subagent attempts for the same review record still have scratch reservations
- **THEN** another scratch request names the occupied paths and refuses before allocating a third or spending a scoped pass

### Requirement: FULL design review requires usable evidence and bounds failure retention

A FULL change-design route without local file reads SHALL be refused before dispatch. Failed FULL attempts SHALL retain at most one diagnostic of up to 2 MiB per change across routes. A refusal SHALL name a diagnostic only when that attempt retained it. Oversized replies, malformed UTF-8 scratch replies and full session transcripts SHALL NOT be retained. Diagnostics SHALL NOT count as a review result or round.

#### Scenario: A selected route cannot read the packet
- **WHEN** an OMP or Claude route is selected for FULL change-design review with no effective `read` or `Read` tool respectively
- **THEN** dispatch identifies the missing tool without starting the reviewer, reserving scratch or mutating the prior report

#### Scenario: A bounded invalid FULL subagent reply
- **WHEN** the FULL subagent returns a bounded, well-formed UTF-8 reply with an invalid verdict during an authorized scoped pass
- **THEN** validation exits 3 with `status: invalid`, removes the original scratch, and reports a path to the retained bounded diagnostic; the earlier review is byte-identical and neither a round nor scoped permission is consumed

#### Scenario: A FULL scratch reply has malformed UTF-8
- **WHEN** a FULL subagent reply contains malformed UTF-8, even with a valid verdict and a raw size under 2 MiB
- **THEN** validation exits 3 with `status: invalid`, removes the scratch without retaining it, and leaves the earlier review and scoped permission unchanged

#### Scenario: Repeated failures and oversized scratch output
- **WHEN** multiple FULL attempts are refused with bounded invalid results, followed by an oversized scratch reply
- **THEN** at most one bounded diagnostic remains, the oversized reply and completed attempt directories are removed, and no refused result replaces the review or uses scoped permission
