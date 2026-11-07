# Review

## Metadata

- **Round:** 2
- **Prior round:** REVISE: relative `--code` resolution, incorrect fixture citation, GitButler platform coverage, and missing byte-parity evidence.
- **Reviewer:** Codex, read-only design review; re-check limited to round 2's Required Changes.
- **Reviewed:** Existing round 2 review; review template; proposal Impact; design D4, D9, A1, C4, C8 and Decision summary; cli/lib/src/vcs/walk.dart; skills/specwright-finish/scripts/finish.sh lines 290–330; .github/workflows/evals.yml installation, requirement and suite execution steps; evals/vcs/butenv.py requirement behavior.

## Findings

### Critical (blocking)

None.

### Moderate

The round 2 findings are retained below. Their required design changes are now verified under Rebuttals.

**M1 — D9 does not arrange for GitButler differential tests to run in CI.**

Round 2 found that D9 placed differential tests in `evals/finish/test_parity.py` while CI installed `but` only in the Linux `vcs` job. Requiring `but` in the Linux `finish` job would fail; skipping unavailable GitButler tests would omit the promised differential coverage. Existing effect tests did not supply the missing byte comparison.

**M2 — The proposed directory walk does not preserve filename bytes.**

Round 2 found that A1 proposed `Directory.listSync` despite D4's raw-byte filesystem promise. The VCS walker explicitly avoids Dart directory enumeration because its exposed path is lossy.

For an uncommitted archive containing a POSIX filename with invalid UTF-8 bytes, replacement decoding followed by `encodeEscaped` cannot recover the original filename. This could change reads, failures or `carried_edits` output, outside the permitted parity exceptions.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Update D9 and the implementation scope to provide an explicit CI route for GitButler differential cases: either install pinned `but` in the Linux `finish` job or run those cases from a test module in the Linux `vcs` job. Require their execution there while retaining the documented macOS/Windows gap.
2. Replace the `Directory.listSync` walk assumption with a mechanism that preserves filename bytes through enumeration, reads and output construction. Preserve finish’s existing traversal and symlink behavior; the VCS walker’s pruning and regular-file restrictions cannot be adopted wholesale. Add a POSIX differential case containing an invalid-UTF-8 filename in an uncommitted archive, and carry this invariant into C4’s destination.

CHANGES_APPLIED: yes

## Rebuttals

- **Round 1 C1:** Accepted as fixed. D2 joins relative `--code` to the planning toplevel; D7 uses that base for project discovery. The new scenario and C7 carry the rule.
- **Round 1 M1:** Accepted as fixed. The revised helper-chain citations show the inherited `script` → `run_argv` path, test home and version stamp.
- **Round 1 M2:** Accepted as fixed. Proposal, delta scenario, dedicated risk and C8 identify Linux-only GitButler evidence.
- **Round 1 M3:** The differential-oracle approach addresses the original effect-versus-bytes concern. The remaining GitButler CI wiring concern is resolved by round 2 Required Change 1 below.
- **Round 2 Required Change 1 / M1 — Verified; accepted by reviewer.** D9 explicitly places GitButler differential cases in `evals/vcs/test_gitbutler_parity.py`, sharing the oracle runner from `evals/finish/fixtures.py`. Proposal Impact names both parity modules and the Linux `vcs` route. This matches the existing workflow: pinned `but` is installed in the Linux `vcs` job, Linux sets `SPECWRIGHT_REQUIRE_BUT=1`, and the job runs the `vcs` suite. D9 requires the module to call `require_but()`, whose existing implementation raises when that environment variable is set and `but` is missing. Thus the planned cases cannot silently skip for a missing Linux CI binary. D9 and C8 retain the macOS/Windows gap and issue #154; the D9 summary row agrees.
- **Round 2 Required Change 2 / M2 — Verified; accepted by reviewer.** D4 replaces lossy directory enumeration with transport-backed `find ROOT/ -mindepth 1 -print0`, NUL-delimited byte records decoded with `decodeEscaped`, and `encodeEscaped` for subsequent raw-path reads and output names. It explicitly rejects wholesale reuse of `walkFiles`: nothing is pruned, entries are classified with link-following checks, non-directory entries remain files, linked directories are classified as directories but not descended into, and records are regrouped into `os.walk`'s top-down files-before-subdirectories order. These distinctions preserve the relevant finish walk behavior at lines 296 and 313–320 instead of adopting the VCS walker's `.git`/`.jj` pruning and regular non-link file restriction. A1 now records the remaining platform listing-order assumption and its differential check. D9 adds a Linux POSIX invalid-UTF-8 filename case in an uncommitted archive with stdout-byte and exit-code comparison. C4 carries byte preservation from listing through reads to output, top-down ordering and link-following filesystem checks into the `undoArchivePlan` doc-comment destination. The D4 summary row agrees.

Both verifications concern the revised design commitments. They do not certify implementation or CI execution.
