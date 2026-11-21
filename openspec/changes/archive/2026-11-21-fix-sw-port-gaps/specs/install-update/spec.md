## MODIFIED Requirements

### Requirement: The sw download is bounded
Each download of a release asset or `SHA256SUMS` SHALL accept at most 64 MiB in all, redirects and error bodies included, under a 120-second deadline that stops HTTP(S) and refuses a late `file://` copy. A final HTTP 200 response SHALL be judged in order: expired deadline (`deadline_exceeded`), non-identity encoding (`download_failed`), size (`response_too_large`). The first bound passed SHALL be reported with the asset within 10 s of the stop, cleanup aside.

#### Scenario: Download completes in time
- **WHEN** the server answers an uncompressed 9 MiB asset, and its write and close settle before the deadline
- **THEN** the download completes and the checksum check runs on the whole file

#### Scenario: A partial file that is slow to open
- **WHEN** opening the partial file on the destination filesystem stalls
- **THEN** the 120-second deadline starts only once the file is open; the stalled open itself is not bounded

#### Scenario: A partial file that cannot be created
- **WHEN** the partial file cannot be created in the version directory, for a release whose asset would answer 404
- **THEN** no request is sent and the install stops with `download_failed` naming the partial file and the operating system's reason, not `assets_not_uploaded`

#### Scenario: Server stalls
- **WHEN** an HTTP(S) release download is still pending at the deadline with no outcome recorded
- **THEN** the download stops within 120 seconds plus 10 seconds, and once its cleanup returns the install reports `deadline_exceeded` and the asset; when the partial file can be deleted, no partial file is left

#### Scenario: A file mirror that finishes after the deadline
- **WHEN** the release URL is a `file://` mirror whose copy of an asset under 64 MiB finishes after the deadline
- **THEN** the install stops naming `deadline_exceeded` and the asset, and nothing is placed

#### Scenario: A file mirror
- **WHEN** the release URL is a `file://` mirror whose asset is over 64 MiB and the copy passes 64 MiB before the deadline
- **THEN** the install stops naming `response_too_large` and the asset, and nothing is placed

#### Scenario: Oversized answer
- **WHEN** before the deadline the server sends more than 64 MiB for an uncompressed asset
- **THEN** the install stops naming `response_too_large` and the asset, and, when the partial file can be deleted, no partial file is left

#### Scenario: An oversized error or redirect body
- **WHEN** before the deadline the server answers a redirect, a 404 or another error status with a body over 64 MiB
- **THEN** the install accepts no more than 64 MiB of it, stops reading, and stops naming `response_too_large` and the asset

#### Scenario: Bodies that fit alone but not together
- **WHEN** before the deadline a download follows a redirect whose body is 40 MiB to an uncompressed asset of 40 MiB
- **THEN** the install stops naming `response_too_large` and the asset, and nothing is placed

#### Scenario: The partial file cannot be closed after an oversized answer
- **WHEN** before the deadline an uncompressed download passes 64 MiB, and closing its partial file then fails or does not finish before the deadline
- **THEN** the download stops within 120 seconds plus 10 seconds, and once its cleanup returns the install reports `response_too_large` and the asset, and nothing is placed

#### Scenario: The deadline passes before an oversized chunk is read
- **WHEN** the deadline has passed by the time the download reads a chunk that would take it past 64 MiB
- **THEN** the install stops naming `deadline_exceeded` and the asset

#### Scenario: An oversized length with a stalled body
- **WHEN** before the deadline the server answers with an uncompressed HTTP 200, advertises a length over 64 MiB, and then sends no body
- **THEN** the downloader latches `response_too_large` when it reads the header, before the deadline, and returns it within ten seconds of that latch, not `deadline_exceeded`; once its cleanup returns, the install reports `response_too_large` naming the asset

#### Scenario: A write failure while the body stalls
- **WHEN** before the deadline the partial file's write fails while the server has stopped sending, and closing the file then runs past the deadline
- **THEN** the download stops reading at once, and after its bounded shutdown and cleanup the install reports `download_failed` and the asset, not `deadline_exceeded`

#### Scenario: A connection failure after the deadline
- **WHEN** the deadline has passed by the time the download's connection or file write fails
- **THEN** the install stops naming `deadline_exceeded` and the asset, not `download_failed`

#### Scenario: A compressed answer
- **WHEN** before the deadline the server answers the asset with HTTP 200 and a `Content-Encoding` other than `identity`, with or without a length header, an oversized one included
- **THEN** the install stops naming `download_failed`, the asset and the encoding, and nothing is placed

#### Scenario: A partial answer
- **WHEN** before the deadline the server answers the asset with an identity-encoded HTTP 206 whose body ends within the remaining byte budget and before the deadline
- **THEN** the install stops with `download_failed` naming the status, as before this change, and nothing of the body is kept

#### Scenario: A compressed 404
- **WHEN** the server answers `SHA256SUMS` with a small gzip-encoded 404 whose response, redirects included, completes within the remaining byte and time budgets
- **THEN** the downloader latches the missing asset when the drain completes and returns it within ten seconds of that latch even while closing the partial file is still held, so a close that fails or stalls cannot replace it; once its cleanup returns, the install reports the missing asset as before this change, not `download_failed`; a 404 that passes a bound first reports that bound

#### Scenario: A compressed answer handled after the deadline
- **WHEN** the deadline has passed by the time a compressed answer's headers are handled
- **THEN** the install stops naming `deadline_exceeded` and the asset, not `download_failed`

#### Scenario: An answer of exactly 64 MiB
- **WHEN** with no redirect or error body counted, the server sends an uncompressed asset of exactly 64 MiB with no length header, and its write and close settle before the deadline
- **THEN** the download completes and the checksum check runs on the whole file

#### Scenario: A body that ends in time with a close that settles late
- **WHEN** over HTTP(S) an uncompressed asset of exactly 64 MiB ends before the deadline but its partial file's close settles after it, even after the grace period
- **THEN** the downloader latches `deadline_exceeded` at the deadline and returns it by the end of the grace period; once its cleanup returns, the install reports `deadline_exceeded` naming the asset, the partial file is closed exactly once, and no checksum check runs

#### Scenario: The partial file is held
- **WHEN** a download passes its deadline and its partial file cannot be deleted
- **THEN** the install stops naming `deadline_exceeded` and the asset, not a file-operation error, and the partial file remains

### Requirement: The macOS install clears quarantine only on the file it checked
On macOS the install SHALL remove the `com.apple.quarantine` attribute only from the downloaded file whose SHA-256 it has just checked, before it runs that file. A file whose checksum did not match SHALL never have the attribute removed and SHALL never run.

#### Scenario: Quarantined download on macOS arm64
- **WHEN** the downloaded `sw-macos-arm64` carries `com.apple.quarantine` and its SHA-256 matches its `SHA256SUMS` line
- **THEN** the attribute is removed, `sw version --json` exits 0, and the binary is placed

#### Scenario: Mismatched file is left quarantined
- **WHEN** the downloaded macOS binary's SHA-256 differs from its line
- **THEN** the install stops, the attribute is not removed, the file is not run, and the download is deleted when it can be; when it cannot, it is left in place and the install still stops with the checksum error

### Requirement: Placing sw is atomic and keeps other versions
The install SHALL write the binary into its version directory under a temporary name and rename it to `sw[.exe]` only after the checks pass, so the final path never holds a partial or unchecked file. It SHALL never change another version's directory. A file already at the final path SHALL be kept only when it has the release's SHA-256 and its `sw version --json` reports the release's version and interface. Any other file there SHALL be replaced by that rename.

#### Scenario: Rerun with the binary already placed
- **WHEN** the install of `v0.24.0` runs again and `<home>/.specwright/bin/0.24.0/sw` already matches the release's hash and passes the version and interface check
- **THEN** the file is kept unchanged and the report says it was already installed

#### Scenario: Interrupted before the rename
- **WHEN** the install is stopped after the download and before the rename
- **THEN** no file exists at `<home>/.specwright/bin/0.24.0/sw`, `<home>/.specwright/bin/0.23.0/sw` is unchanged, and the next run downloads and checks again

#### Scenario: A stale file at the final path
- **WHEN** `<home>/.specwright/bin/0.24.0/sw` exists but its SHA-256 differs from the release's
- **THEN** the checked download replaces it by rename, and the report says it was replaced

#### Scenario: Matching hash but not runnable
- **WHEN** `<home>/.specwright/bin/0.24.0/sw` has the release's SHA-256 but its executable bit was removed
- **THEN** the checked download replaces it, `sw version --json` at the final path exits 0, and the report says it was replaced

#### Scenario: Two installs of one version at once
- **WHEN** two projects on one machine install `v0.24.0` at the same time, each finishes within an hour so neither loses a live part to the other's age sweep, and no running process holds the final file
- **THEN** both succeed, one placing the binary and the other placing it or reporting it kept after checking the winner's file, the final file has the release's SHA-256, and neither run deletes the other's temporary file while it is younger than an hour

#### Scenario: Rename blocked by a running binary
- **WHEN** on Windows the rename to the final path fails because another process is running that file
- **THEN** the install checks the final file again: when it has the release's SHA-256 and its `sw version --json` reports the release's version and interface, the install succeeds and reports it kept; otherwise it stops with `sw_in_use` naming the path; the existing binary and other versions are unchanged, the checked notice may already be in place, and the part file may remain

#### Scenario: The final file cannot be read after a blocked rename
- **WHEN** the rename to the final path fails and the final file disappears or cannot be opened while it is being checked
- **THEN** the install stops with `sw_in_use` naming the path, not a file-operation error, and makes no further placement attempt

#### Scenario: A temporary file left by a killed run
- **WHEN** the version directory holds a temporary file last modified more than one hour ago
- **THEN** the next install of that version deletes it when it can, and leaves it without an error when it cannot; a temporary file modified within the last hour is left alone

### Requirement: A missing or incompatible sw stops a tagged install before any change
For a release tag whose downloaded copy offers the `sw` install step, any failure to get a matching `sw` (asset or `SHA256SUMS` missing or invalid, download failed or bounded, checksum differs, version report fails or mismatches) SHALL stop the install/update before staging. Installed files, `VERSION` and every binary under `<home>/.specwright/bin/` SHALL stay unchanged, and the report SHALL name the cause, the asset and the release.

#### Scenario: Release assets not uploaded yet
- **WHEN** `v0.24.0` was just published, the release workflow has not attached its assets, and the request for them is sent and answered 404 with a response that completes within the remaining byte and time budgets (a 404 that passes a bound reports that bound instead)
- **THEN** the install stops before staging, says the release's binaries are not uploaded yet and to rerun the install once they are, and no file changes

#### Scenario: Checksum mismatch
- **WHEN** the downloaded binary's SHA-256 differs from its `SHA256SUMS` line
- **THEN** the install stops before staging, naming the asset and both hashes, the file is not run, and nothing is placed

#### Scenario: Wrong interface
- **WHEN** the checked binary reports `"version": "0.24.0"` and an interface other than the skills' interface
- **THEN** the install stops before staging, naming both interfaces, and nothing is placed

#### Scenario: Unattached assets and an unwritable version directory
- **WHEN** the release has no assets yet and the partial file cannot be created in the version directory
- **THEN** no request is sent and the install stops with `download_failed` naming the partial file, since a failed open comes before any HTTP outcome

## ADDED Requirements

### Requirement: Part-file cleanup never replaces the install's result
Every deletion of a temporary part file or `.stage` directory during `sw update sw-install` SHALL be best effort. A part file it cannot delete SHALL be left in place and SHALL NOT change the install's exit status, document or error; where another requirement says no file changes, a leftover temporary part and an old part removed by the existing age-based sweep are the only exceptions; installed files, binaries and `VERSION` never are.

#### Scenario: A locked binary part after a notice write failure
- **WHEN** on Windows the install stops with `notice_write_failed` and its `.part.exe` cannot be deleted because it is still locked
- **THEN** the document's error is `notice_write_failed`, not `file_operation_failed`, the existing binary is unchanged, and the part file remains

#### Scenario: A locked part after a rename lost to a concurrent install
- **WHEN** a concurrent install places the release's binary at the final path after this install's first check, this install's rename then fails, and deleting its part fails
- **THEN** the install reports `kept`, as when the delete succeeds, and the part file remains

#### Scenario: A locked part after a rename that fails otherwise
- **WHEN** this install's rename fails, the final path does not hold the release's binary, and deleting its part fails
- **THEN** the install stops with `sw_in_use`, not a file-operation error, and the part file remains

#### Scenario: A part left when the release has no SHA256SUMS
- **WHEN** a tagged install stops because `SHA256SUMS` is missing and deleting the partial download fails
- **THEN** installed files, `VERSION` and every binary under `<home>/.specwright/bin/` are unchanged and the stop is reported as before; the temporary part file remains, and the existing age-based sweep may already have removed old parts from the version directory; these two are the only exceptions to that stop's "no file changes"

#### Scenario: A version directory that cannot be listed
- **WHEN** the version directory can be written but not listed when the install sweeps old parts
- **THEN** the sweep is skipped and the install goes on as if no old part were there

#### Scenario: A source build whose stage cannot be deleted
- **WHEN** an install from source ends and its `.stage` directory cannot be deleted
- **THEN** the install's result and document are those of the build, and the `.stage` directory remains

#### Scenario: Cleanup succeeds
- **WHEN** the install succeeds and every part file it created can be deleted
- **THEN** none of this run's part files or its source-build `.stage` directory remain, another run's part file younger than an hour is left untouched, and the document reports the install as before

#### Scenario: A later run meets the leftover
- **WHEN** a later install in the same version directory finds a part file older than an hour
- **THEN** it tries to delete it, and leaves it without an error when it is still held
