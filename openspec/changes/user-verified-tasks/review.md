# Review

## Metadata

- **Round:** 3
- **Prior round:** 2 — APPROVE_WITH_CHANGES; changes applied. Verdict voided by the approved evidence-source amendment.
- **Reviewer:** Codex, read-only re-check.
- **Reviewed:** Round 3 review; review template; evidence requirement and store-backed scenario; design D5; ADR 0024; commit skill section 3; `task-cover.sh` evidence implementation; evidence tests and test-map row.
- **Scope:** Re-check of Round 3’s two Required Changes only. Original Findings retained below. Tests inspected, not executed.

## Findings

### Critical (blocking)

None.

### Moderate

1. **The evidence repository is undefined for store-backed coverage calls.**

   D5 and the amended requirement specify git’s index without distinguishing the evidence repository from the repository whose commits are being checked. However, `skills/specwright-commit/SKILL.md:54` explicitly runs `task-cover.sh` against both the store and code repositories, passing the store’s `tasks.md` to both. Section 3 requires both checks to pass and stops on `evidence_missing`.

   Consider a completed evidence task whose non-empty regular blob and covering task commit are correctly recorded in the store. The code repository has no corresponding evidence entry. Looking in its index therefore reports `evidence_missing`; rejecting the external tasks path instead stops the entire coverage call. Either outcome prevents a valid store-backed change from reaching pre-ship review.

   The current filesystem check avoids this particular problem because it derives the evidence location from `tasks_path`, independently of `--repo`. Replacing it with an index lookup needs an explicit repository-selection rule.

### Suggestions

None.

## Verdict

Both Required Changes are applied.

The evidence requirement, design D5, ADR 0024 and the caller contract in section 3 consistently identify the repository holding `tasks.md` as the authoritative evidence source. Without `--rev`, `evidence_ok` derives the change folder from `tasks_path` and runs `git -C <change folder> ls-files -s -z -- ':(literal)<path>'`. It requires exactly one regular stage-zero entry with a non-empty blob, checks the blob size in that same repository, and has no filesystem fallback.

The “Store-backed evidence” scenario now establishes a group commit covering 2.2 in each repository and explicitly states that the end-of-apply check passes when both calls report no `uncovered`, `duplicates`, `cross_group` or `evidence_missing` entry. It also states that committed empty or removed store evidence makes both calls list 2.2 and stops the check.

The test-map row maps this scenario to `test_store_backed_evidence_read_from_tasks_repo`. That test creates covering group commits in both repositories, runs both coverage calls with the store’s `tasks.md`, asserts all four completion fields are empty, and checks that both calls report 2.2 after evidence is committed empty and after it is removed. `test_evidence_present_not_missing` separately covers staged evidence during Reconcile; `test_evidence_committed_not_missing` covers committed evidence.

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Define the planning repository as the authoritative evidence source in D5, the evidence requirement and ADR 0024. Update the caller contract so code-repository coverage checks either read evidence from an explicitly supplied planning repository or leave evidence validation exclusively to the planning-repository check. Preserve the prohibition on filesystem fallback.

   **Re-check: applied.** The planning artifacts, caller contract and implementation consistently select the repository holding `tasks.md`; index evidence has no filesystem fallback.

2. Add an assertable store-backed scenario and test-map row: tasks and evidence exist only in the store, both repositories have valid task coverage, and completion succeeds. Assert that missing or empty evidence in the store still blocks completion. Cover staged evidence during Reconcile as well as committed evidence at completion.

   **Re-check: applied.** The scenario states successful completion and both failure cases. Its mapped test establishes task coverage in both repositories, exercises both calls, asserts successful coverage and evidence results, and checks empty and removed store evidence. Separate tests cover staged and committed evidence.

CHANGES_APPLIED: yes

## Rebuttals

None.