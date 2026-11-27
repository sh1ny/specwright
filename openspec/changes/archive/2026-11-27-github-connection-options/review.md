# Review

## Metadata

- **Round:** 9, targeted recheck of Round 8.
- **Prior round:** Round 8 requested four design corrections.
- **Reviewer:** Codex.
- **Owner decision:** “Fix, recheck only those”
- **Reviewed:** Only the four Round 8 findings in `review.md`, the relevant passages in the revised design and VCS and release spec deltas, the current receipt source, and the cited ranges at baseline `1fe2c5d7046263db56a42896742b1e054dcca5bf`. The verdict closes the design review within that authorized scope. Full design review, implementation review, build approval, and merge approval were outside scope. No files were edited and no tests ran.

## Findings

### Critical (blocking)

1. **Resolved.** A supplied proof requires a successful fetch receipt in the same checkout. The design records it only after a successful fetch, exact commit read, confirmed private-ref removal, and destination recheck. A missing or unreadable receipt stops the operation and requires a fresh `prove-main` in that checkout. The receipt lasts for the checkout’s lifetime. Each distinct target, branch, and commit gets one empty file, identical retries reuse it, and validation uses one lookup without a scan. [Design](design.md#target-and-evidence-checks)

### Moderate

1. **Resolved.** C13 maps to `Fetches for reading move no jj bookmark`. The scenario requires a selected GitHub remote and a publish that needs a release-main fetch. That fetch removes its private ref immediately after reading it and preserves `FETCH_HEAD`, bookmarks, and remote-tracking refs. Ordinary jj reads retain the `FETCH_HEAD` path. [Design](design.md#carried-constraints) · [VCS delta](specs/vcs-backends/spec.md#requirement-fetches-for-reading-move-no-jj-bookmark)
2. **Resolved.** The release delta permits proof acquisition to write objects, its private ref, and the checkout-local receipt. Unconfirmed ref removal stops the operation before it records a successful receipt or issues proof. Missing version history, a missing or inconsistent receipt, a changed destination, or an older version due first blocks the applicable release-tag and GitHub-release writes. [Release delta](specs/releases/spec.md#requirement-the-release-commit-is-found-on-main)
3. **Resolved.** The cited ranges at the pinned baseline show the separate fetch and history-ref handoff, Git’s tracking-ref read, the jj and GitButler `FETCH_HEAD` reads, ship’s identity check before `expected`, and both deadline cases. The design marks the current receipt implementation citation separately. [Design](design.md#triage)

### Suggestions

None.

## Verdict

VERDICT: APPROVE

## Required Changes

CHANGES_APPLIED: n/a

## Rebuttals

None.

<!-- specwright-design-progress -->
<!-- eyJ2ZXJzaW9uIjoxLCJyb3VuZCI6OSwic2NvcGVfcm91bmQiOjUsImV4dGVuZGVkIjp0cnVlLCJsb2ciOlt7InJvdW5kIjoyLCJyZXBhaXJzIjoiQWN0dWFsIHB1bGwgdGFyZ2V0IGRyaXZlcyBmZW5jaW5nOyBwb3NpdGl2ZSByZW1vdGUgYW5kIGhpc3RvcnkgZXZpZGVuY2UgcHJlY2VkZXMgYXV0aGVudGljYXRpb247IGhvc3QgYW5kIFBSIGV2aWRlbmNlIGFyZSBjaGVja2VkIGJlZm9yZSBhdXRob3JpemF0aW9uIGFuZCBtdXRhdGlvbnM7IHJlbGVhc2UgdXNlcyBzdGFibGUgdGFyZ2V0IGFuZCBzZXBhcmF0ZSBiYXNlL3JlZjsgY2xhcmlmaWVkIEdpdEJ1dGxlciBhbmQgb3duZXItY29uZmlybWVkIGludmVyc2Ugc3RvcmUgc2NvcGU7IGluamVjdGVkIHRlc3Qgb3V0Y29tZXMuIn0seyJyb3VuZCI6MywicmVwYWlycyI6IkNsYXNzaWZ5IGFsbCBlZmZlY3RpdmUgcHVzaCBVUkxzIGFuZCByZWZ1c2UgbWl4ZWQvdW5rbm93biBkZXN0aW5hdGlvbnM7IHJlc29sdmUgb21pdHRlZCBzbmFwc2hvdC9yZXBseSByZXBvIGZyb20gdGhlIHNlbGVjdGVkIHJvbGU7IG1pZ3JhdGUgdG91Y2hlZCBkZWFkbGluZSBjb21wYXRpYmlsaXR5IHRlc3RzIHRvIGluamVjdGVkIG91dGNvbWVzOyBjYXJyeSBhbmQgdGVzdCB0aGUgZXhpc3Rpbmcgc3RvcmUtbWFpbiByZWxlYXNlIG5vdGVzIHJ1bGUuIn0seyJyb3VuZCI6MywiY2hvaWNlIjoic2NvcGVkLXBhc3MiLCJkZXRhaWwiOiJPd25lcjogT25lIG1vcmUgZml4IHBhc3MuIE9ubHkgcm91bmQgMyBsb2NhbC1zdG9yZSB3YXRjaCBnYXRlIGV2aWRlbmNlLCBwdXNoLWF1dGggc3BlYyBjb25zaXN0ZW5jeSwgbWFudWFsLXNoYXJlIGZlZWRiYWNrIHJlY292ZXJ5LCBhbmQgdGhlIHRocmVlIHdvcmRpbmcvY2FycmllZC1jb25zdHJhaW50IGNvcnJlY3Rpb25zLiBUaGVuIGZ1bGwgaW5kZXBlbmRlbnQgcmV2aWV3LiJ9LHsicm91bmQiOjQsInJlcGFpcnMiOiJDb2RlLW9ubHkgd2F0Y2ggcmVhZHMgYW5kIHJlY2hlY2tzIGNvbW1pdHRlZCBsb2NhbCB0YXNrcyBhbmQgYXJjaGl2ZSB0aXA7IG5vIHBsYW5uaW5nIHB1c2ggb3IgY2Fycnktb3Zlci4gTWFudWFsLXNoYXJlIGZlZWRiYWNrIGNvdW50cyBsb2NhbCByb3VuZHMgd2l0aG91dCByZW1vdGUgYWN0aW9ucy4gUHVzaCBzcGVjcyB1c2UgZWZmZWN0aXZlIHB1c2ggVVJMcy4gQ29ycmVjdCBtaXNzaW5nLWFjY291bnQgb3JkZXJpbmcsIGNvZGUtaWRlbnRpdHkgY29uc3RyYWludCBhbmQgcmVwbHkgbXV0YXRpb24gZ3JvdW5kaW5nLiJ9LHsicm91bmQiOjQsImNob2ljZSI6InNjb3BlLWNoYW5nZSIsImRldGFpbCI6Ik93bmVyOiBDdXQgIzI2MCB0byBzaGlwIG9ubHkuIFNoaXAgc3RpbGwgb3BlbnMgdGhlIGV4cGVjdGVkIGNvZGUgUFIgYW5kIHJlcG9ydHMgbWFudWFsIHNoYXJpbmcsIHdpdGggbm8gbG9jYWwgc3RvcmUgcHVzaCwgUFIgb3Igd2F0Y2guIEluIFBSIHdhdGNoLCBmZWVkYmFjayByb3VuZHMgYW5kIGZpbmlzaCwgaGFuZCB0aGUgbG9jYWwgcGxhbm5pbmcgYnJhbmNoIGJhY2sgZm9yIG1hbnVhbCBzaGFyaW5nIGFuZCBhcmNoaXZlOyBubyBsb2NhbCByb3VuZCBjb3VudGluZywgYXJjaGl2ZSBoYW5kb2ZmIG9yIHJlc3RhcnQgcmVjaGVja3MuICMxNjcgYW5kICMxNjggdW5jaGFuZ2VkLiBPbmUgZnVsbCBpbmRlcGVuZGVudCByZXZpZXcsIHRoZW4gaGFuZCBiYWNrIGFueSBpbi1zY29wZSBSRVZJU0UuIE5vdCBidWlsZCBhcHByb3ZhbC4ifSx7InJvdW5kIjo1LCJyZXBhaXJzIjoiT3duZXIgY3V0ICMyNjAgdG8gc2hpcCBvbmx5LiBLZWVwIGNvZGUgUFIgc2hpcCBhbmQgbWFudWFsIHNoYXJpbmc7IGFkZCBubyBzdG9yZSB3YXRjaC9hcmNoaXZlL3JvdW5kIGF1dG9tYXRpb24uIFN0b3AgdGhlIHN0b3JlIHBhcnQgaW4gbGF0ZXIgUFIgcGhhc2VzIHdpdGhvdXQgY2xhaW1pbmcgcmVhZGluZXNzLCBhbmQgdGVzdCBleHBsaWNpdCBWQ1MgZmV0Y2ggc2VwYXJhdGVseSBmcm9tIG5vIG5ldHdvcmsgZHVyaW5nIG1hbnVhbC1zaGFyZSByb3VuZHMuIFByZXNlcnZlICMxNjcgYW5kICMxNjguIn0seyJyb3VuZCI6NiwicmVwYWlycyI6Ik93bmVyIGFwcHJvdmVkIHNldmVuIHJvdW5kLTUgZml4ZXM6IG5hdGl2ZSBtYW51YWxfc3RvcmVfaGFuZG9mZjsgZmFpbCBjbG9zZWQgb24gYXN5bW1ldHJpYyBQUiB0cmFuc3BvcnRzOyBwcmUtYXJjaGl2ZSBmaW5pc2ggY2hlY2s7IGV4cGxpY2l0IGRlZmVycmVkL2JvdW5kIGxvZ2luIGhhbmRvZmZzOyByZWxlYXNlIG1haW4gcHJvb2YgYm91bmQgdG8gZGVzdGluYXRpb247IHJlZnVzZSByb2xlIGNvbGxpc2lvbnM7IG1pZ3JhdGUgY3JlZGVudGlhbCB0ZXN0cyBhbmQgcHJvdmUgbm8gc3RvcmUgcmVhZHMgaW4gcm91bmRzLiAjMjYwIHN0YXlzIHNoaXAgb25seS4ifSx7InJvdW5kIjo3LCJyZXBhaXJzIjoiT3duZXI6IEZpeCBib3RoLCByZWNoZWNrIG9ubHkgdGhvc2UuIEtlZXAgc2FmZSBpbmRleGVkIHJld3JpdGVzIGFuZCBjaGVjayBkZXN0aW5hdGlvbiBpbiB0aGUgYWN0dWFsIGZlbmNlZCBHaXQgZW52aXJvbm1lbnQgYWdhaW5zdCBQUi9yZWxlYXNlIHRhcmdldC4gQmluZCByZWxlYXNlIHByb29mIHRvIHRoZSBleGFjdCBpbnZvY2F0aW9uLXByaXZhdGUgbWFpbiBmZXRjaCBjb21taXQuIFRhcmdldGVkIHJlY2hlY2ssIG5vdCBmdWxsIHJldmlldyBvciBidWlsZCBhcHByb3ZhbC4ifSx7InJvdW5kIjo4LCJyZXBhaXJzIjoiT3duZXI6IEFsbG93IGl0IGZvciByZWxlYXNlcyBvbmx5LiBDbGFyaWZ5IHRoZSBhcHByb3ZlZCBqaiByZWxlYXNlLW9ubHkgcHJpdmF0ZS1yZWYgZXhjZXB0aW9uLCBpbW1lZGlhdGUgY2xlYW51cCBhbmQgdW5jaGFuZ2VkIG9yZGluYXJ5IGpqIHJlZnJlc2hlcy4ifSx7InJvdW5kIjo4LCJjaG9pY2UiOiJzY29wZWQtcGFzcyIsImRldGFpbCI6Ik93bmVyOiDigJxGaXgsIHJlY2hlY2sgb25seSB0aG9zZS7igJ0gTGltaXQgdGhpcyByZXBhaXIgYW5kIGl0cyBpbmRlcGVuZGVudCByZWNoZWNrIHRvIHRoZSBmb3VyIHJvdW5kIDggZmluZGluZ3MuIEV4cGxpY2l0IG93bmVyIGV4Y2VwdGlvbiB0byBmdWxsIHJlcmV2aWV3OyBubyBhcHByb3ZhbCBvZiBjaGFuZ2VkIGpqIGJlaGF2aW91ciwgIzI2MCBzY29wZSwgYnVpbGQgb3IgbWVyZ2UuIn0seyJyb3VuZCI6OSwicmVwYWlycyI6Ik93bmVyIGNsb3NlZCBkZXNpZ24gd2l0aCBhIHRhcmdldGVkIHJlY2hlY2sgb2YgZXhhY3RseSB0aGUgZm91ciByb3VuZCA4IGZpbmRpbmdzOyBhbGwgd2VyZSByZXNvbHZlZC4gTm8gY2hhbmdlIHRvIGpqIGJlaGF2aW91ciBvciAjMjYwIHNjb3BlLiJ9XX0= -->

## Review progress

- Validated round: 9 (scope round 5)
- Repairs before round 2: "Actual pull target drives fencing; positive remote and history evidence precedes authentication; host and PR evidence are checked before authorization and mutations; release uses stable target and separate base/ref; clarified GitButler and owner-confirmed inverse store scope; injected test outcomes."
- Repairs before round 3: "Classify all effective push URLs and refuse mixed/unknown destinations; resolve omitted snapshot/reply repo from the selected role; migrate touched deadline compatibility tests to injected outcomes; carry and test the existing store-main release notes rule."
- Owner round 3: `scoped-pass` — "Owner: One more fix pass. Only round 3 local-store watch gate evidence, push-auth spec consistency, manual-share feedback recovery, and the three wording/carried-constraint corrections. Then full independent review."
- Repairs before round 4: "Code-only watch reads and rechecks committed local tasks and archive tip; no planning push or carry-over. Manual-share feedback counts local rounds without remote actions. Push specs use effective push URLs. Correct missing-account ordering, code-identity constraint and reply mutation grounding."
- Owner round 4: `scope-change` — "Owner: Cut #260 to ship only. Ship still opens the expected code PR and reports manual sharing, with no local store push, PR or watch. In PR watch, feedback rounds and finish, hand the local planning branch back for manual sharing and archive; no local round counting, archive handoff or restart rechecks. #167 and #168 unchanged. One full independent review, then hand back any in-scope REVISE. Not build approval."
- Repairs before round 5: "Owner cut #260 to ship only. Keep code PR ship and manual sharing; add no store watch/archive/round automation. Stop the store part in later PR phases without claiming readiness, and test explicit VCS fetch separately from no network during manual-share rounds. Preserve #167 and #168."
- Repairs before round 6: "Owner approved seven round-5 fixes: native manual_store_handoff; fail closed on asymmetric PR transports; pre-archive finish check; explicit deferred/bound login handoffs; release main proof bound to destination; refuse role collisions; migrate credential tests and prove no store reads in rounds. #260 stays ship only."
- Repairs before round 7: "Owner: Fix both, recheck only those. Keep safe indexed rewrites and check destination in the actual fenced Git environment against PR/release target. Bind release proof to the exact invocation-private main fetch commit. Targeted recheck, not full review or build approval."
- Repairs before round 8: "Owner: Allow it for releases only. Clarify the approved jj release-only private-ref exception, immediate cleanup and unchanged ordinary jj refreshes."
- Owner round 8: `scoped-pass` — "Owner: “Fix, recheck only those.” Limit this repair and its independent recheck to the four round 8 findings. Explicit owner exception to full rereview; no approval of changed jj behaviour, #260 scope, build or merge."
- Repairs before round 9: "Owner closed design with a targeted recheck of exactly the four round 8 findings; all were resolved. No change to jj behaviour or #260 scope."

## Pre-ship owner decision

- Reviewed head: `cf473daa6e6d584fe28e53f75ef88b6725345497`, pre-ship round 4.
- Owner decision: “Fix four, file the race, ship.” Fix findings F2–F5 and verify them locally, then ship without another pre-ship round. This decision does not approve merge.
- F1 (P0), a fetch or pull can follow a remote URL changed during credential lookup: deferred by the owner to [#261](https://github.com/sh1ny/specwright/issues/261). The issue remains open; no fix, waiver, or passing pre-ship verdict is recorded for it.
