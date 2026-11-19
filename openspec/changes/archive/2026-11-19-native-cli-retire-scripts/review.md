# Review

## Metadata

- **Round:** 13
- **Prior round:** 12 (REVISE)
- **Reviewer:** Codex
- **Change:** `native-cli-retire-scripts` (FULL)
- **Reviewed:** Working-tree proposal, design, spec deltas, task map, prior reviews, ADR 0040 and its architecture index entry, compiled-binary probe source, and review template.
- **Scope:** This review uses the recorded three-OS probe results. The probes were not rerun. The workspace is read-only, so the review is delivered here.

## Findings

### Critical (blocking)

None.

### Moderate

**M1. The architecture index still promises `bad_argument` and exit 2 on Linux and macOS.** The index entry for ADR 0040 gives an unconditional outcome for malformed arguments. The proposal, D3 decision table, Failure & Visibility, and the affected command specs now reflect C6. The ADR itself records the runtime refusal, but its opening contract and the two design diagrams can state the platform distinction more directly. [Architecture index](/F:/Dev/specwright/openspec/architecture.md:241) · [ADR 0040](/F:/Dev/specwright/docs/adr/0040-skills-call-the-projects-sw-directly.md:15) · [Design](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/design.md:200)

**M2. Task 6.4 omits the tool-invocation assertion required by the fenced-workflow scenario.** Round 12’s blocking contract conflict is resolved. The scenario now calls `sw pr rounds` with malformed direct argv, and its map row points to the migrated eval. The scenario requires both no credential lookup and no tool invocation. Task 6.4 names only the credential check, and the existing eval snapshots only the fake `gh` log. A valid control can establish that the fixture would reach the fenced tool and that both checks can detect activity. The scenario’s final clause about names encountered after entry also needs a separate input and assertion, since this invocation exits before entry. [Workflow scenario](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/specs/pr-script-runtime/spec.md:243) · [Task 6.4](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/tasks.md:339) · [Existing eval](/F:/Dev/specwright/evals/pr-pair/test_workflow_transport.py:307)

**M3. The test map and task 2.2 still treat the gate regressions as tests that start red.** Task 2.1 correctly keeps the three probe cases as regressions and identifies why the new tests should fail. The POSIX probe now supplies malformed bytes directly, creates no malformed filename, and checks that the valid control emits a document. The three mapped probe rows still say `red`, and task 2.2 says the Windows and POSIX refusal rows turn green during implementation. The test module’s opening docstring also still describes the original gate expectation as the current expectation on all platforms. [Test map](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/tasks.md:100) · [Tasks 2.1 and 2.2](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/tasks.md:310) · [Probe](/F:/Dev/specwright/evals/cli/test_sw_entry.py:1)

### Suggestions

None. The native CLI scenario and its map row now name Linux and macOS. The VCS scenario retains its existing title for the `MODIFIED` requirement, and its steps specify direct invocation.

## Prior-round findings

All three round 11 findings remain resolved. The source-build scenarios use the `0.38.0` slot and check the independent skill pin before placement. The older tagged install retains `0.37.0`. The final cutover group carries the absence evals, interface flip, consumer rewrites, native release instructions, and version bump in one commit. D14 and A4 retain the expanded citations for the fixture environment, commits and comparison, version stamp, and Git exclusion write. [Install delta](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/specs/install-update/spec.md:72) · [Cutover tasks](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/tasks.md:342) · [D14](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/design.md:124) · [A4](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/design.md:177)

## Required Changes

1. Update the ADR 0040 index entry and the D3 diagrams to reflect C6. State that Windows emits the `bad_argument` document and exits 2, while Linux and macOS refuse malformed argv before `main` with a non-zero exit, empty stdout, and no work. Leave the runtime exit code and diagnostic text unspecified. Use the same platform-first wording in the ADR’s opening contract and describe the raw check there as applying when execution reaches `sw`.
2. In task 6.4, require the migrated eval to check both the credential lookup and the fenced tool invocation, using a fixture with a valid-argv control that reaches the tool. Keep the malformed-argv scenario focused on the entry refusal and give values discovered after entry their own input and `not_utf8` assertion in the applicable existing coverage.
3. Mark the three entry probe rows as existing or updated regressions and align the test-map legend and task 2.2 with that status. Update the probe docstring to describe the current Windows and POSIX expectations.

## Verdict

The amended command requirements implement the accepted C6 contract. The remaining changes align the architecture summary and the verification plan with that contract.

VERDICT: APPROVE_WITH_CHANGES
CHANGES_APPLIED: yes