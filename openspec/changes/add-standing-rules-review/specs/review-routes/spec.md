## MODIFIED Requirements

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

The FULL change-design result SHALL record the effective rule identity. A change to the declared rule inputs SHALL require a full review, not a Required Changes recheck, and an earlier passing result SHALL NOT let the change enter tasks or apply under the changed rules.

#### Scenario: Rules added between conditional approval and its recheck
- **WHEN** a change with no standing rules gets `APPROVE_WITH_CHANGES` with `CHANGES_APPLIED: no`, then its project declares a committed rule
- **THEN** a Required Changes-only recheck is refused; a full review includes the new rule

#### Scenario: Rule text changes after approval
- **WHEN** the approved change's configured rule file is updated on its code branch
- **THEN** the approval is not reinterpreted as covering the new text, and tasks or apply wait for a new full review

#### Scenario: A sibling changes GitButler review settings
- **WHEN** the GitButler worktree settings differ from the named code change branch's committed settings, including a sibling edit to `review.cross_model`
- **THEN** the FULL change-design controller stops before probing a route or acting on its standing rules or checkpoint settings

#### Scenario: Route selection used previous settings
- **WHEN** FULL route selection succeeds and the code branch's settings change before dispatch
- **THEN** the prior selection cannot start either a CLI or subagent attempt; the author selects again from the current pinned settings

### Requirement: Review results apply only to captured design inputs

Both FULL routes SHALL review a private capture. A stale result SHALL NOT replace the report. Only a full attempt SHALL establish a conditional baseline. A recheck SHALL compare the captured current artifacts with that baseline and SHALL NOT confirm if changes exceed the Required Changes. A recheck SHALL NOT create or extend a baseline; a valid confirmation or `REVISE` retires it. Incomplete or unpinned input SHALL NOT produce a passing result.

#### Scenario: Live artifacts change and change back during dispatch
- **WHEN** the live design is edited and restored while the reviewer is running
- **THEN** the reviewer receives the captured design, not the intervening edit; a persistent edit instead makes the result stale at publication

#### Scenario: A conditional recheck receives unrelated changes
- **WHEN** the artifacts contain a Required Change plus an unrelated change to a requirement
- **THEN** the recheck gets the prior and current captures and must not confirm unless all changes are within the Required Changes, excluding Release Notes-only changes

#### Scenario: A full pass cannot confirm a recheck
- **WHEN** either FULL route returns `APPROVE_WITH_CHANGES` with `CHANGES_APPLIED: yes` on an initial review or after an unavailable prior capture or changed rule identity forced full review
- **THEN** validation refuses the result and does not replace any prior review record or consume permission for a scoped pass

#### Scenario: A limited recheck cannot establish another baseline
- **WHEN** either FULL route, during a limited recheck, returns `APPROVE_WITH_CHANGES` with `CHANGES_APPLIED: no` after an unrelated artifact change
- **THEN** the result is rejected without replacing the previous report or promoting the recheck's capture; a valid `REVISE` instead closes the prior baseline and the next attempt must be a full review

#### Scenario: The ordinary writer targets an open checkpoint
- **WHEN** either ordinary design route omits the FULL change option but targets the active `review.md` of a change at its checkpoint
- **THEN** it refuses to replace or remove that record

#### Scenario: Conflicting evidence cannot keep the publication lock
- **WHEN** the publication check cannot finish its Git reads within its budget
- **THEN** the recorded verdict and owner choices stay unchanged and a subsequent authorized write can acquire the lock

#### Scenario: Interrupted attempts reach the slot limit
- **WHEN** two unfinished subagent attempts for the same review record still have captures
- **THEN** another scratch request names those attempts and refuses before allocating a third; it deletes neither existing capture and does not consume a scoped pass

### Requirement: FULL design review requires usable evidence and bounds failure retention

A FULL change-design route without local file reads SHALL be refused before dispatch. Completed failed FULL attempts SHALL retain at most one diagnostic of up to 2 MiB per change, across CLI and subagent routes. A refusal SHALL report a diagnostic path only if that attempt successfully retained a bounded result. Oversized replies SHALL NOT be retained. Diagnostics SHALL NOT count as a review result or round.

#### Scenario: A selected route cannot read the packet
- **WHEN** an OMP or Claude route is selected for FULL change-design review with no effective `read` or `Read` tool respectively
- **THEN** dispatch identifies the missing tool without starting the reviewer, creating a capture or mutating the prior report

#### Scenario: A bounded invalid FULL subagent reply
- **WHEN** the FULL subagent returns a bounded invalid reply during an authorized scoped pass
- **THEN** validation exits 3 with `status: invalid`, removes the original scratch, and reports a path to the retained bounded diagnostic; the earlier review is byte-identical and neither a round nor scoped permission is consumed

#### Scenario: Repeated failures and oversized scratch output
- **WHEN** multiple FULL attempts are refused with bounded invalid results, followed by an oversized scratch reply
- **THEN** at most one bounded diagnostic remains, the oversized reply and completed attempt captures are removed, and no refused result replaces the review or uses scoped permission
