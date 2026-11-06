# Review

## Metadata

- **Round:** 4 — re-check run.
- **Prior round:** round 3 REVISE only because the untracked change artifacts were not opened.
- **Reviewer:** Codex, fresh review context.
- **Reviewed:** Only round 4’s two Required Changes: the Context interface claim and carried constraints C16–C17 in `design.md`, checked against `README.md:209-224` and the two named requirements in `specs/install-update/spec.md`. Untracked artifacts were read.
- **Installed project skills:** none.

## Findings

### Critical (blocking)

None.

### Moderate

**M9 — Resolved: the installation-interface claim includes the supported compatibility path.**  
`design.md:23` now says the prompt accepts interface 2, plus interface 1 only when settings enable no pack and installed pack state lists no enabled pack. It retains the `README.md:209-224` citation and matches that passage.

**M10 — Resolved: carried constraints preserve verification and placement ordering.**  
`design.md:135` adds C16, requiring SHA-256 verification before macOS quarantine removal and the downloaded file’s first execution. Its single destination is “The macOS install clears quarantine only on the file it checked” in `specs/install-update/spec.md`.

`design.md:136` adds C17, requiring checksum and resolver checks to complete before placement by rename within the version directory, and prohibiting writing the final executable in place. Its single destination is “Placing sw is atomic and keeps other versions” in `specs/install-update/spec.md`. Both destination requirements exist and express the corresponding obligations.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Correct Context’s interface claim to state that the prompt accepts interface 2, plus interface 1 only when no pack is enabled in settings or installed pack state. Retain the existing README citation.
2. Add carried-constraint entries, each with exactly one destination:
   - Check SHA-256 before removing quarantine or executing the downloaded file. Destination: `specs/install-update/spec.md` → “The macOS install clears quarantine only on the file it checked”.
   - Complete checksum and resolver checks before placing the temporary file by same-directory rename; never write the final executable in place. Destination: `specs/install-update/spec.md` → “Placing sw is atomic and keeps other versions”.

CHANGES_APPLIED: yes

Both required changes are correctly applied. Nothing remains missing within this re-check’s scope.

## Rebuttals

- **C3:** Resolved by per-tag serialization, uploaded-binary read-back before sealing, and both corresponding scenarios.
- **M5:** Resolved by the failed-rename re-check and the Windows scenario.
- **M6:** Resolved by C13–C15.
- **M7:** Resolved in both CI and release requirements, with interface-mismatch scenarios.
- **M8:** Resolved for the prior review: all four untracked review subjects were opened.
- **M9:** Resolved in this re-check: Context preserves the interface 1 exception only when neither settings nor installed pack state enables packs, and retains the README citation.
- **M10:** Resolved in this re-check: C16 and C17 explicitly carry both ordering invariants, each with exactly one destination at the required install-update requirement.