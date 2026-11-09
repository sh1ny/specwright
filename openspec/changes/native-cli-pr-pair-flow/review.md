# Review

## Metadata

- **Round:** 4 (full review after the user-directed notice-sidecar amendment)
- **Prior round:** Round 3, APPROVE_WITH_CHANGES with all Required Changes applied in `5420791`. This amendment to the proposal, specs and design voids that verdict.
- **Reviewer:** fresh-context Claude agent (`claude-opus-5-5`)
- **Reviewed:**
  - **Rules and artifacts:** `AGENTS.md`, `schemas/specwright/schema.yaml`, `schemas/specwright/templates/review.md`, and the change's `proposal.md`, `design.md`, `tasks.md`, `review.md` and all three delta specs
  - **Baselines and ADRs:** `openspec/specs/native-cli/spec.md`, targeted lines of `openspec/specs/install-update/spec.md`, ADR 0027
  - **Packaging and install:** `.github/workflows/sw-build.yml`, `release.yml`, `cli/tool/attach_release.py`, `verify_artifact.py`, `scripts/install-sw.sh`, `scripts/update.sh:3011-3311`, `.gitattributes`, `mise.toml:23-31`, `README.md:224-247`
  - **Tests:** `evals/cli/test_attach_release.py`, `test_install_sw.py`, `test_workflows.py`, `evals/update/test_sw_install.py`, `evals/fakes/gh_release.py`, `cli/test/pr/closing_test.dart:30-54`, `evals/pr-pair/test_pr_pair.py:2881-2884, 2995-3029`
  - **D1-D6 citations:** every cited range in `pr-pair.sh`, `commands/pr.dart`, `pr/pair.dart`, `commands/vcs.dart`, `fence/fence.dart`, `process/limits.dart` and `closing_bodies.py`
- **Verification limits:**
  - Nothing was edited, installed, run or built, and no Git mutation occurred.
  - `git ls-files` was not available. Tracked status rests on the supplied Git status snapshot.
  - The old text of task 5.3 could not be diffed. Its intact move is judged from the current 8.5 text and the mapped rows.
  - The `html` package source and its licences were not opened; task 4.4 owns that check.
  - The "50-page" figure at `design.md:227` was not traced to the value of `bounded.MAX_PAGES`.
  - Windows runner line-ending conversion in M-2 comes from general platform behaviour, not from a file in this repository.

## Findings

### Critical (blocking)

None.

### Moderate

**M-1. A manual run for an older tag breaks once `sw-build.yml` packages the notice.**

- `release.yml:9-13` allows a manual run for a named tag, and `release.yml:27` calls the workflow's own copy of `sw-build.yml`.
- That copy then checks out the old tag (`sw-build.yml:46-48`). A pre-0.30.0 tag has no `cli/THIRD_PARTY_NOTICES.txt`, so an unconditional packaging step at `sw-build.yml:64-70` fails before `attach` starts.
- This regresses the baseline scenario "Sealed release run again" (`native-cli/spec.md:263-265`) and the user's requirement to retain old seals.
- This is the one place old tags really meet new code:
  - `release.yml:40-54` runs the tag's own `attach_release.py`.
  - `update.sh:3207-3209` with `README.md:243-244` runs the download's own script for its own tag.
- The attach and installer pre-0.30.0 branches therefore mainly protect the in-tree 0.29.0 state and the evals, while the real risk has no scenario or task.

**M-2. One manifest hash covers a notice built five times, with no byte-identity guarantee.**

- D7 puts the notice and its checksum in every build artifact (`design.md:82`). Every target runs its own checkout, and `.gitattributes:1-6` has no rule covering `.txt`, so the Windows checkout can convert line endings.
- `release.yml:46-50` merges all five artifacts with `merge-multiple: true`, so same-named files collide. The surviving notice and checksum can come from different builds.
- `attach_release.py:81-84` would then fail the seal, or the release would ship whichever copy won.
- `SHA256SUMS` can hold one notice line only, so the bytes must be the same on all targets.

**M-3. The install order that the delta requires is not specified, and concurrent placement is unsafe.**

- The delta forbids replacing an existing binary after a placement failure (`native-cli/spec.md:17`, `31-33`). The notice must therefore be placed before `os.replace` at `update.sh:3272`.
- D7 says only "before reporting success".
- The notice also cannot be placed earlier than the part-file checks. `assert_nothing_placed` requires an empty home after a failed binary check (`test_sw_install.py:220-221`, `329-333`).
- The early `kept` return at `update.sh:3258-3262` would skip a repair placed after it.
- Rerunning must not rewrite a correct notice, because `test_rerun_keeps_matching_binary` compares mtimes (`test_sw_install.py:465-471`).
- Concurrent installs must both succeed (`:505-518`). The binary path handles a blocked rename by re-checking the final file (`update.sh:3273-3279`). D7 has no equivalent for the notice, so a Windows sharing conflict would fail a run whose notice is already correct.
- The failure contract has gaps:
  - The retry advice at `update.sh:3241-3243` ("rerun once attached") is wrong for a sealed manifest with no notice line.
  - No error code is assigned to any notice failure.
  - The temporary name must match the `.sw-*.part` cleanup (`update.sh:3221`) and be deleted by the `finally` block (`:3282-3287`).

**M-4. The 0.30.0 bump inverts the installer fixtures, and no task handles it.**

- `test_sw_install.py:87-89` derives the tag from the built binary's version, and `:119-126` always writes a five-line manifest.
- At task 9.2, every test using those fixtures becomes a new-format release with no notice and fails. Task 9.2 has no fixture work.
- The `[EXE]`-only directory assertions at `:242`, `:518` and `:527` also change.
- Before the bump the opposite problem applies: `sw_check` requires the binary to report the tag's version (`update.sh:3254`), so the 0.29.0 build cannot pass as a v0.30.0 release.
- Task 4.5 must make the fixtures depend on the release format and let tests choose the tag independently of the built binary.

**M-5. The delta leaves conflicting baseline text and non-assertable outcomes.**

- The unmodified scenario "Sealed release run again" (`native-cli/spec.md:263-265`) reports any sealed release with five binaries as complete. The new "Sealed new release lacks its notice" requires failure for the same assets from 0.30.0. Both would survive archive.
- `spec.md:249` also gates the seal on five binaries only.
- The MODIFIED checksum requirement drops the baseline sentence "Renaming an asset, or changing this format, is a workflow change (minor version)" (`native-cli/spec.md:238`). The schema requires full updated content.
- "reports failure" (delta `:33`) is not assertable. `install-update/spec.md:422` requires a stop before staging, naming the cause, asset and release, but its list of causes does not mention the notice.
- The requirement covers builds (delta `:17`), but no scenario tests build packaging.

**M-6. The FULL-tier sections and ADR records were not updated for D7.**

- State & Ownership, Failure & Visibility, Resource Bounds, Mechanism Ledger and Flow & State Gaps have no notice entries (`design.md:192-263`).
- No T4 diagram shows the new release or install boundary (`design.md:181-190`).
- `design.md:274` and `proposal.md:33` still list only ADR 0031, although D7 and C14 record ADR 0032.
- `proposal.md:33` also omits the release workflows, the attach tool and both installers from Impact.

**M-7. The test map overclaims and leaves gaps.**

- "A malformed checksum line" is `green`, but the delta adds a duplicate name (`spec.md:11`) and `test_malformed_sums_line_is_rejected` has no duplicate case (`test_sw_install.py:351-356`).
- "Older release needs no retrospective notice" names both the installer and the attachment tool. The row covers only attach, and it sits under an ADDED requirement whose version gate is new code.
- There are no rows for notice read-back failure or the build scenario that Required Change 3 adds.
- `tasks.md:56` is a blank line that splits the table, so rows 57-66 lose their header.
- `tasks.md:5` still says "both deltas".

**M-8. The notice scope and its upkeep are under-specified.**

- D7 covers "the resolved runtime dependencies". Task 4.4 records only "each newly resolved runtime package", which excludes `args` and `ffi` (`cli/pubspec.yaml:16-17`).
- `dart compile exe` produces a single-file executable (ADR 0027:14), which embeds the Dart runtime. Neither D7 nor 4.4 says whether its notice is needed.
- C14 does not bind future dependency changes, and the hash check cannot detect a stale notice.

**M-9. Moving task 5.3 to 8.5 is coherent, but the checks must be written before the switch.**

- The dependency reasoning holds. The Python 3.8 shim checks need group 6's `pass` and task 8.2's dispatch. Primitive checks remain in 5.1/5.2.
- Two problems remain inside group 8:
  - "Verify red then green" in 8.5 cannot hold after 8.2, because the behaviour already exists by then.
  - 8.2 relies on always-run checks that 8.5 has not yet added. 8.2 also removes the `PYSRC` block that `embedded_python()` indexes (`test_pr_pair.py:2881-2884`), breaking those tests until 8.5 lands.

### Suggestions

- **S-1.** `closing_test.dart:46-48` still asserts `isEmpty` for `Fixes <table>#1</table>`, the opposite of the approved outcome. Replace it with the mapped test rather than adding one beside it.
- **S-2.** When `sw_sums` and `SHA256SUMS` change, reword the "for the five assets" message at `update.sh:3239-3240` and the five-asset docstring at `:3080`.

### Confirmed intact

- **Immutable seals and pre-seal read-back:** the existing structure supports D7 by extending the asset list used at `attach_release.py:68-73`, `:87` and `:89-99`. The seal stays last. `release.yml:19-21` still serialises runs per tag.
- **Pre-execution verification:** the marker pattern in `test_sw_install.py:296-310` can prove the notice is checked before the first run.
- **Download bounds:** the notice reuses `sw_download` (`update.sh:3123-3151`), and `install-update/spec.md:437` already bounds every release asset at 120 s and 64 MiB. No new cap is needed.
- **Retained checks:** D7 does not alter binary version or interface checks (`verify_artifact.py:52-68`, `update.sh:3254`), and nothing adds pruning or rollback changes. `update.sh:3197` and the rollback tests stay valid.
- **Source-build installer:** `install-sw.sh:21` checks before placing anything, which allows the same order as the download path. `test_install_sw.py:74` still holds when the notice is placed after that check.
- **ADR 0027 and C14:** D7 adds to ADR 0027 without editing it, and C14 has exactly one destination. ADR 0032 sits in task 4.5 rather than group 1, which is acceptable because group 1 is complete and 4.5 writes the ADR with the implementation.
- **Local test scope:** task 4.5 runs named modules and the suite-map check only. `cli/**` and `evals/cli/**` are already routed (`evals/suites.json:26`).
- **HTML5 outcome:** D6 (`design.md:78`), the delta (`spec.md:107-109`) and the map row (`tasks.md:58`) agree on the owner-approved result. Code exclusion, line boundaries, ownership and mutation safety remain binding.
- **D1-D6 citations:** every range re-read supports its claim. No S2 byte-replica requirement was added, and no earlier port is pulled into scope.
- **Group 5:** no completed task was unticked or renumbered. The Win32 last-error race remains open and is not claimed as resolved.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **`design.md` D7, build sentence.** Replace "Each build artifact includes it and its SHA-256 sidecar." with:

   > "Packaging is gated by a numeric MAJOR.MINOR.PATCH comparison of the VERSION at the ref being built or released, never by whether a notice is present. At 0.30.0 or later, each build artifact includes byte-identical `THIRD_PARTY_NOTICES.txt` and `THIRD_PARTY_NOTICES.txt.sha256`, and a missing source notice fails the build. Below 0.30.0, the build packages no notice, so a manual run for an older tag still reaches its sealed-release result. `.gitattributes` pins `cli/THIRD_PARTY_NOTICES.txt` to `text eol=lf`."

2. **`design.md` D7, downloader sentence.** Replace "The downloader verifies both ... notice verification/write failure." with:

   > "For a release at 0.30.0 or later, the downloader verifies the notice and binary hashes before quarantine removal or the first run. After the part binary passes every check, and before the kept-binary decision or binary rename, it places the notice once. A notice already matching the manifest is left untouched. Otherwise a `.sw-<token>.notice.part` file replaces it. If that replacement fails and the final notice now matches, the run continues; otherwise it stops with `notice_write_failed` and the binary is not replaced. A new-format `SHA256SUMS` without a notice line is `sums_invalid`, a 404 for the notice is `asset_missing`, and a wrong notice hash is `checksum_mismatch`. The source-build installer uses the same order: check the build, place the notice, rename the binary, then run the final resolver check."

3. **`specs/native-cli/spec.md`:**
   - Restore "Renaming an asset, or changing this format, is a workflow change (minor version)." to the MODIFIED checksum requirement.
   - Add the whole block from baseline lines 248-273 under `## MODIFIED Requirements`, with two changes:
     - The first sentence becomes "only after every asset required for that release (the five binaries and, from 0.30.0, the notice) is attached and each, read back from the release, has the hash it lists".
     - The "Sealed release run again" WHEN becomes "for a release that already has `SHA256SUMS` and every asset required for its version".
   - In "Notice failure preserves the existing binary", replace the THEN with:

     > "**THEN** `sw-install` returns `ok: false` with `sums_invalid`, `asset_missing`, `checksum_mismatch` or `notice_write_failed`, its message names the notice and the release, the install stops before staging, the downloaded binary did not run before notice verification, and any existing binary is byte-identical"

   - Add these scenarios to the notice requirement:

     > "#### Scenario: Build artifacts carry identical notices
     > - **WHEN** a ref at 0.30.0 or later is built for the five targets
     > - **THEN** each artifact holds the same notice bytes and a matching checksum file, and a missing source notice fails the build
     >
     > #### Scenario: Older tag builds without a notice
     > - **WHEN** the current build workflow runs for a tag below 0.30.0
     > - **THEN** it requires no notice and a sealed release reports complete without any asset change
     >
     > #### Scenario: Notice read-back differs before the seal
     > - **WHEN** the notice read back from an unsealed 0.30.0 release differs from the built notice
     > - **THEN** attachment fails naming the notice and both hashes, and uploads no `SHA256SUMS`"

4. **`design.md`, FULL sections:**
   - **State & Ownership**, add:

     > "| Installed notice | `sw-install` or the source-build installer | Beside its version's binary | Replaced only when absent or not matching the release hash; source installs use the tree notice | Release `SHA256SUMS` for release installs; `cli/THIRD_PARTY_NOTICES.txt` for source builds |"

   - **Failure & Visibility**, add:

     > "| Notice delivery | Missing, corrupt, unplaceable or concurrently replaced notice | Rerun the install; a sealed release lacking its notice needs its owner | Yes; placement is idempotent | User sees `ok: false` with the code and release; a concurrent identical result continues |"

   - **Resource Bounds**, add:

     > "| Notice download | Existing per-download 120 s and 64 MiB bounds | Stop, delete the part, report the limit | One small file per install; unchanged at 10x or 100x installs |"

   - **Mechanism Ledger**, add:

     > "| Automated notice-completeness check | no | Task 4.4's evidence and C14 cover this change; it would need a runtime-graph-to-licence mapping | A dependency change ships with a stale notice |"

   - **T4 diagram**, add edges for build artifacts, attach and read-back, `SHA256SUMS` seal, and install beside the binary.
   - **Flow & State Gaps**, add a line for death between notice placement and binary rename: the correct notice remains and the next run repeats the binary placement.

5. **ADR and Impact records:**
   - In `design.md` ADRs, add: "ADR 0032, third-party notice distribution, carrying C14 and adding to 0027."
   - In `proposal.md:33`, replace "Apply will add ADR 0031" with "Apply will add ADRs 0031 and 0032", and add `.github/workflows/sw-build.yml`, `cli/tool/attach_release.py`, `scripts/update.sh`, `scripts/install-sw.sh` and `cli/THIRD_PARTY_NOTICES.txt` to the affected code.

6. **`tasks.md` task 4.5.** Append:

   > "Make the attach and installer fixtures choose their manifest format from the fixture tag, independently of the built binary's reported version, so old- and new-format cases pass both before and after task 9.2. Update directory-content assertions accordingly. Add `.gitattributes` coverage and tests for byte-identical packaging, the older-tag build path, the placement order, an untouched correct notice, concurrent placement and every stop code in D7."

7. **`tasks.md` test map:**
   - Remove the blank line at `tasks.md:56`.
   - Change "both deltas" to "all three deltas" at `tasks.md:5`.
   - Set "A malformed checksum line" to `red`, and add duplicate-name and pre-0.30.0-notice-line variants to `test_malformed_sums_line_is_rejected`.
   - Set the attach row for "Older release needs no retrospective notice" to `red`.
   - Add these rows:

     | Requirement | Scenario | Test file | Test name | State |
     |---|---|---|---|---|
     | native-cli - Third-party notices accompany new sw distributions | Older release needs no retrospective notice | evals/update/test_sw_install.py | TestNotices.test_pre_030_release_installs_without_notice | red |
     | native-cli - Third-party notices accompany new sw distributions | Build artifacts carry identical notices | evals/cli/test_workflows.py | SwBuildTests.test_build_packages_identical_notice | red |
     | native-cli - Third-party notices accompany new sw distributions | Older tag builds without a notice | evals/cli/test_workflows.py | SwBuildTests.test_older_tag_build_requires_no_notice | red |
     | native-cli - Third-party notices accompany new sw distributions | Notice read-back differs before the seal | evals/cli/test_attach_release.py | AttachReleaseTests.test_notice_readback_mismatch_writes_no_seal | red |

8. **Notice scope:**
   - In D7, replace "covering the resolved runtime dependencies" with "covering every direct and transitive package compiled into `sw`, plus the Dart runtime embedded by `dart compile exe` when its licence requires a notice".
   - In task 4.4, replace "each newly resolved runtime package's" with "each direct and transitive package compiled into `sw`, and the embedded Dart runtime's".
   - Append to C14: "A change to the compiled dependency set updates the notice."

9. **`tasks.md` group 8:**
   - Append to 8.1: "Also add the failing always-run native checks and conditional Python 3.8 shim checks named in 8.5, and verify them red before the final switch."
   - In 8.5, replace "Verify red then green using the changed module and native test file individually" with "Verify the checks added in 8.1 turn green after 8.2, and that each moved extraction check keeps its failure assertion, using the changed module and native test file individually".
   - State in 8.2 and 8.5 that 8.2 and the extraction-check move land together, so `embedded_python()` users are never left broken by a commit.

CHANGES_APPLIED: yes

## Rebuttals

None yet.

## Required change application

The coordinator applied Required Changes 1-9: version-gated identical notice artifacts and LF source; verified notice/binary placement order, idempotence, concurrency and named stops; complete checksum/seal delta scenarios; notice ownership/failure/resource/flow/diagram entries; ADR0032 and packaging Impact records; fixture work; complete scenario-map rows and states; compiled runtime plus embedded Dart licence scope and upkeep; and group8 red checks before the atomic shim/extraction switch. Strict change validation, release-notes validation and the diff whitespace check passed. These are coordinator checks, not extra reviewer execution. Group4/5 implementation remains incomplete and unticked.
