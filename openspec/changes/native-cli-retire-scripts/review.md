# Review

## Metadata

- **Round:** 11
- **Prior round:** 10
- **Tier:** FULL
- **Reviewer:** Codex
- **Change:** `native-cli-retire-scripts`
- **Installed project skills applicable to the reviewed work:** None.
- **Scope:** Read the explicitly requested working-tree artifacts and installed schema. Used Git-tracked files for supporting citations. Scenario-to-task assignments remain unverified because `tasks.md` has yet to be written.

## Round 10 findings

| Finding | Status | Round 11 assessment |
|---|---|---|
| C1. The interface cutover can replace the binary that existing 0.37.0 projects still need | Resolved in the cutover design | D5 puts interface 2 and the `0.38.0` bump in the same commit and calls for a shared-home test with both binaries. The install delta still contains a conflicting source-build example. See M1 below. [D5](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/design.md:68) |
| M1. The `v0.37.0` success case still permits a false-ready report | Resolved | The older-tag scenario now requires the final probe to exit successfully and report `0.37.0` with interface 1. The enclosing requirement applies the 10-second deadline. [Older-tag scenario](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/specs/install-update/spec.md:35) |
| M2. The remaining citation gaps obscure what the oracle and fixture tests must preserve | Partially resolved | D14 now includes owner normalization and cites the Git helper. The citations still omit the fixture commit calls and environment assignment. A4 still misses the stamp call and exclusion write. See M3 below. [D14](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/design.md:124) · [A4](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/design.md:177) |
| M3. The merged specs would require incompatible undo guard implementations | Resolved | Both deltas now require the guard to read the backend’s structured branch in process. The native CLI delta preserves the assertions that the planned branch passes and another branch refuses. [Native CLI delta](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/specs/native-cli/spec.md:244) · [Finish delta](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/specs/change-finish/spec.md:39) |

C7 was assessed against the current inline store gate and per-backend undo recovery. C8 was assessed with the 10-second deadline and the approved removal of the 1 MiB output cap. [Store gate](/F:/Dev/specwright/skills/specwright-branch/SKILL.md:35) · [Undo recovery](/F:/Dev/specwright/cli/lib/src/finish/undo_plan.dart:1063) · [Owner decisions](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/design.md:186)

## Findings and Required Changes

### Moderate

**M1. The source-build scenarios still exercise the old version slot, and the placement check has no independent skill pin.** The install delta puts a direct-entry source build in `bin/0.37.0`, the slot D5 reserves for interface 1. Its failure scenario also depends on detecting a mismatch with the skills before placement. Today `build.dart` probes the separate update interface and then invokes the built binary to install itself. The installer defaults its workflow interface check to the running binary’s own constant. A binary and its copied build can therefore agree while the skill pin differs. **Required change:** Move the source-build success and refusal scenarios to `0.38.0`, retain the older tagged-install scenario at `0.37.0`, and specify that source placement checks the workflow interface against the tree’s skill pin before replacing the binary or notice. Add a scenario where the update interface passes and the workflow interface differs from the skill pin, with both existing files unchanged. [Install delta](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/specs/install-update/spec.md:71) · [Build probe](/F:/Dev/specwright/cli/tool/build.dart:89) · [Build placement](/F:/Dev/specwright/cli/lib/src/update/sw_install.dart:294) · [Interface default](/F:/Dev/specwright/cli/lib/src/update/place.dart:67)

**M2. The cutover order conflicts with the retained last-group release requirement.** D5 puts the bump in the cutover group, and the task order puts absence evals after that group. The release spec and current task instructions require the bump in the last group. Following the latter as written can move the bump past the interface flip or schedule a second bump. **Required change:** Put the absence evals in the final cutover group and make its single commit carry the `0.38.0` bump, interface flip, consumer rewrites and verification. Align D5 and the task-order paragraph with that schedule, and update the shipped release instructions to use the native bump, check and notes commands. [Cutover order](/F:/Dev/specwright/openspec/changes/native-cli-retire-scripts/design.md:312) · [Release scenario](/F:/Dev/specwright/openspec/specs/releases/spec.md:548) · [Task instructions](/F:/Dev/specwright/schemas/specwright/schema.yaml:696)

**M3. Two grounding gaps remain in the oracle and fixture citations.** D14 points to the `setUp` and branch-case declarations plus the generic Git helper. Those lines do not show which environment the Git calls inherit or which commits supply the SHA under comparison. A4 labels line 189 as the stamp call, but that line sets the remote URL, and its helper range ends before the exclusion is written. These are the steps the migration must preserve to keep oracle IDs repeatable and the version stamp out of status results. **Required change:** Extend the D14 citations to cover the assignment of `git_env`, the fixture’s base commit, and the branch case’s commits and comparison. In A4, include the stamp call at line 191 and the helper’s exclusion write at line 83. [Fixture environment](/F:/Dev/specwright/evals/pr-pair/test_parity.py:602) · [Base commit](/F:/Dev/specwright/evals/pr-pair/test_workflow_parity.py:142) · [Branch case](/F:/Dev/specwright/evals/pr-pair/test_workflow_parity.py:219) · [Stamp call](/F:/Dev/specwright/evals/vcs/butenv.py:191) · [Exclusion write](/F:/Dev/specwright/evals/vcs/vcs_test_support.py:83)

## Verdict

VERDICT: APPROVE_WITH_CHANGES

CHANGES_APPLIED: yes