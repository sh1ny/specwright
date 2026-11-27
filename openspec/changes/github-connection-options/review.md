# Review

## Metadata

- **Reviewer:** Codex, independent design reviewer
- **Owner decision after round 6:** “Fix both, recheck only those.”
- **Coverage:** Round 6 Critical 1 and Moderate 1 only, including the repaired design passages, C8 and C12, their spec scenarios, the cited tracked code, and the four proposed test-first cases. Round 6 provides the independent assessment of the rest of the design. This verdict closes the two findings at the design gate. Build approval remains separate.
- **Verification:** Read-only review. No files changed and no tests ran. The proposed `red` states are test-first labels, with `tasks.md` held for the gate.

## Findings

### Critical (blocking)

1. **Round 6 Critical 1 is closed.** C8 preserves safe indexed `insteadOf` and `pushInsteadOf` rules in order, excludes indexed auth overrides, and retains helper and header scrubbing. Dispatch resolves and checks destinations in the environment it will launch. A changed or unconfirmed destination stops publication before the push or PR creation. The proposed cases exercise both rewrite kinds and use distinguishable refs and recorded `gh` targets to verify where publication lands and that a refusal produces no writes. [Design](openspec/changes/github-connection-options/design.md#target-and-evidence-checks) · [GitHub identity spec](openspec/changes/github-connection-options/specs/github-identity/spec.md#requirement-push-authentication-follows-the-actual-destinations) · [Fence check and launch](cli/lib/src/fence/fence.dart#L573)

### Moderate

1. **Round 6 Moderate 1 is closed.** C12 reads the exact commit from the release fetch’s invocation-unique ref. The explicit refspec and fetch flags isolate it from normal tracking refs, tags, and `FETCH_HEAD`. The proof binds that commit to the validated release destination, and publish checks the binding before writes. The proposed cases cover a stale conventional tracking ref with a real custom refspec and a second fetch that completes before the proof read. Exact commit and tag assertions and checks on user refs make both outcomes observable without sleeps. [Design](openspec/changes/github-connection-options/design.md#target-and-evidence-checks) · [Release spec](openspec/changes/github-connection-options/specs/releases/spec.md#requirement-the-release-commit-is-found-on-main) · [Git fetch and lookup](cli/lib/src/vcs/git_backend.dart#L506)

### Suggestions

None.

## Verdict

VERDICT: APPROVE

## Required Changes

CHANGES_APPLIED: n/a

## Rebuttals

None.

<!-- specwright-design-progress -->
<!-- eyJ2ZXJzaW9uIjoxLCJyb3VuZCI6Nywic2NvcGVfcm91bmQiOjMsImV4dGVuZGVkIjpmYWxzZSwibG9nIjpbeyJyb3VuZCI6MiwicmVwYWlycyI6IkFjdHVhbCBwdWxsIHRhcmdldCBkcml2ZXMgZmVuY2luZzsgcG9zaXRpdmUgcmVtb3RlIGFuZCBoaXN0b3J5IGV2aWRlbmNlIHByZWNlZGVzIGF1dGhlbnRpY2F0aW9uOyBob3N0IGFuZCBQUiBldmlkZW5jZSBhcmUgY2hlY2tlZCBiZWZvcmUgYXV0aG9yaXphdGlvbiBhbmQgbXV0YXRpb25zOyByZWxlYXNlIHVzZXMgc3RhYmxlIHRhcmdldCBhbmQgc2VwYXJhdGUgYmFzZS9yZWY7IGNsYXJpZmllZCBHaXRCdXRsZXIgYW5kIG93bmVyLWNvbmZpcm1lZCBpbnZlcnNlIHN0b3JlIHNjb3BlOyBpbmplY3RlZCB0ZXN0IG91dGNvbWVzLiJ9LHsicm91bmQiOjMsInJlcGFpcnMiOiJDbGFzc2lmeSBhbGwgZWZmZWN0aXZlIHB1c2ggVVJMcyBhbmQgcmVmdXNlIG1peGVkL3Vua25vd24gZGVzdGluYXRpb25zOyByZXNvbHZlIG9taXR0ZWQgc25hcHNob3QvcmVwbHkgcmVwbyBmcm9tIHRoZSBzZWxlY3RlZCByb2xlOyBtaWdyYXRlIHRvdWNoZWQgZGVhZGxpbmUgY29tcGF0aWJpbGl0eSB0ZXN0cyB0byBpbmplY3RlZCBvdXRjb21lczsgY2FycnkgYW5kIHRlc3QgdGhlIGV4aXN0aW5nIHN0b3JlLW1haW4gcmVsZWFzZSBub3RlcyBydWxlLiJ9LHsicm91bmQiOjMsImNob2ljZSI6InNjb3BlZC1wYXNzIiwiZGV0YWlsIjoiT3duZXI6IE9uZSBtb3JlIGZpeCBwYXNzLiBPbmx5IHJvdW5kIDMgbG9jYWwtc3RvcmUgd2F0Y2ggZ2F0ZSBldmlkZW5jZSwgcHVzaC1hdXRoIHNwZWMgY29uc2lzdGVuY3ksIG1hbnVhbC1zaGFyZSBmZWVkYmFjayByZWNvdmVyeSwgYW5kIHRoZSB0aHJlZSB3b3JkaW5nL2NhcnJpZWQtY29uc3RyYWludCBjb3JyZWN0aW9ucy4gVGhlbiBmdWxsIGluZGVwZW5kZW50IHJldmlldy4ifSx7InJvdW5kIjo0LCJyZXBhaXJzIjoiQ29kZS1vbmx5IHdhdGNoIHJlYWRzIGFuZCByZWNoZWNrcyBjb21taXR0ZWQgbG9jYWwgdGFza3MgYW5kIGFyY2hpdmUgdGlwOyBubyBwbGFubmluZyBwdXNoIG9yIGNhcnJ5LW92ZXIuIE1hbnVhbC1zaGFyZSBmZWVkYmFjayBjb3VudHMgbG9jYWwgcm91bmRzIHdpdGhvdXQgcmVtb3RlIGFjdGlvbnMuIFB1c2ggc3BlY3MgdXNlIGVmZmVjdGl2ZSBwdXNoIFVSTHMuIENvcnJlY3QgbWlzc2luZy1hY2NvdW50IG9yZGVyaW5nLCBjb2RlLWlkZW50aXR5IGNvbnN0cmFpbnQgYW5kIHJlcGx5IG11dGF0aW9uIGdyb3VuZGluZy4ifSx7InJvdW5kIjo0LCJjaG9pY2UiOiJzY29wZS1jaGFuZ2UiLCJkZXRhaWwiOiJPd25lcjogQ3V0ICMyNjAgdG8gc2hpcCBvbmx5LiBTaGlwIHN0aWxsIG9wZW5zIHRoZSBleHBlY3RlZCBjb2RlIFBSIGFuZCByZXBvcnRzIG1hbnVhbCBzaGFyaW5nLCB3aXRoIG5vIGxvY2FsIHN0b3JlIHB1c2gsIFBSIG9yIHdhdGNoLiBJbiBQUiB3YXRjaCwgZmVlZGJhY2sgcm91bmRzIGFuZCBmaW5pc2gsIGhhbmQgdGhlIGxvY2FsIHBsYW5uaW5nIGJyYW5jaCBiYWNrIGZvciBtYW51YWwgc2hhcmluZyBhbmQgYXJjaGl2ZTsgbm8gbG9jYWwgcm91bmQgY291bnRpbmcsIGFyY2hpdmUgaGFuZG9mZiBvciByZXN0YXJ0IHJlY2hlY2tzLiAjMTY3IGFuZCAjMTY4IHVuY2hhbmdlZC4gT25lIGZ1bGwgaW5kZXBlbmRlbnQgcmV2aWV3LCB0aGVuIGhhbmQgYmFjayBhbnkgaW4tc2NvcGUgUkVWSVNFLiBOb3QgYnVpbGQgYXBwcm92YWwuIn0seyJyb3VuZCI6NSwicmVwYWlycyI6Ik93bmVyIGN1dCAjMjYwIHRvIHNoaXAgb25seS4gS2VlcCBjb2RlIFBSIHNoaXAgYW5kIG1hbnVhbCBzaGFyaW5nOyBhZGQgbm8gc3RvcmUgd2F0Y2gvYXJjaGl2ZS9yb3VuZCBhdXRvbWF0aW9uLiBTdG9wIHRoZSBzdG9yZSBwYXJ0IGluIGxhdGVyIFBSIHBoYXNlcyB3aXRob3V0IGNsYWltaW5nIHJlYWRpbmVzcywgYW5kIHRlc3QgZXhwbGljaXQgVkNTIGZldGNoIHNlcGFyYXRlbHkgZnJvbSBubyBuZXR3b3JrIGR1cmluZyBtYW51YWwtc2hhcmUgcm91bmRzLiBQcmVzZXJ2ZSAjMTY3IGFuZCAjMTY4LiJ9LHsicm91bmQiOjYsInJlcGFpcnMiOiJPd25lciBhcHByb3ZlZCBzZXZlbiByb3VuZC01IGZpeGVzOiBuYXRpdmUgbWFudWFsX3N0b3JlX2hhbmRvZmY7IGZhaWwgY2xvc2VkIG9uIGFzeW1tZXRyaWMgUFIgdHJhbnNwb3J0czsgcHJlLWFyY2hpdmUgZmluaXNoIGNoZWNrOyBleHBsaWNpdCBkZWZlcnJlZC9ib3VuZCBsb2dpbiBoYW5kb2ZmczsgcmVsZWFzZSBtYWluIHByb29mIGJvdW5kIHRvIGRlc3RpbmF0aW9uOyByZWZ1c2Ugcm9sZSBjb2xsaXNpb25zOyBtaWdyYXRlIGNyZWRlbnRpYWwgdGVzdHMgYW5kIHByb3ZlIG5vIHN0b3JlIHJlYWRzIGluIHJvdW5kcy4gIzI2MCBzdGF5cyBzaGlwIG9ubHkuIn0seyJyb3VuZCI6NywicmVwYWlycyI6Ik93bmVyOiBGaXggYm90aCwgcmVjaGVjayBvbmx5IHRob3NlLiBLZWVwIHNhZmUgaW5kZXhlZCByZXdyaXRlcyBhbmQgY2hlY2sgZGVzdGluYXRpb24gaW4gdGhlIGFjdHVhbCBmZW5jZWQgR2l0IGVudmlyb25tZW50IGFnYWluc3QgUFIvcmVsZWFzZSB0YXJnZXQuIEJpbmQgcmVsZWFzZSBwcm9vZiB0byB0aGUgZXhhY3QgaW52b2NhdGlvbi1wcml2YXRlIG1haW4gZmV0Y2ggY29tbWl0LiBUYXJnZXRlZCByZWNoZWNrLCBub3QgZnVsbCByZXZpZXcgb3IgYnVpbGQgYXBwcm92YWwuIn1dfQ== -->

## Review progress

- Validated round: 7 (scope round 3)
- Repairs before round 2: "Actual pull target drives fencing; positive remote and history evidence precedes authentication; host and PR evidence are checked before authorization and mutations; release uses stable target and separate base/ref; clarified GitButler and owner-confirmed inverse store scope; injected test outcomes."
- Repairs before round 3: "Classify all effective push URLs and refuse mixed/unknown destinations; resolve omitted snapshot/reply repo from the selected role; migrate touched deadline compatibility tests to injected outcomes; carry and test the existing store-main release notes rule."
- Owner round 3: `scoped-pass` — "Owner: One more fix pass. Only round 3 local-store watch gate evidence, push-auth spec consistency, manual-share feedback recovery, and the three wording/carried-constraint corrections. Then full independent review."
- Repairs before round 4: "Code-only watch reads and rechecks committed local tasks and archive tip; no planning push or carry-over. Manual-share feedback counts local rounds without remote actions. Push specs use effective push URLs. Correct missing-account ordering, code-identity constraint and reply mutation grounding."
- Owner round 4: `scope-change` — "Owner: Cut #260 to ship only. Ship still opens the expected code PR and reports manual sharing, with no local store push, PR or watch. In PR watch, feedback rounds and finish, hand the local planning branch back for manual sharing and archive; no local round counting, archive handoff or restart rechecks. #167 and #168 unchanged. One full independent review, then hand back any in-scope REVISE. Not build approval."
- Repairs before round 5: "Owner cut #260 to ship only. Keep code PR ship and manual sharing; add no store watch/archive/round automation. Stop the store part in later PR phases without claiming readiness, and test explicit VCS fetch separately from no network during manual-share rounds. Preserve #167 and #168."
- Repairs before round 6: "Owner approved seven round-5 fixes: native manual_store_handoff; fail closed on asymmetric PR transports; pre-archive finish check; explicit deferred/bound login handoffs; release main proof bound to destination; refuse role collisions; migrate credential tests and prove no store reads in rounds. #260 stays ship only."
- Repairs before round 7: "Owner: Fix both, recheck only those. Keep safe indexed rewrites and check destination in the actual fenced Git environment against PR/release target. Bind release proof to the exact invocation-private main fetch commit. Targeted recheck, not full review or build approval."
