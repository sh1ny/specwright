# Proposal

## Why

`sw` still starts external tools through bash, and much of its code exists to carry file names that are not valid UTF-8 through Dart's string APIs. This change serves M8, Complete the native CLI migration (#148), and the exit criterion that `sw` starts no bash or sh for its own work. It must land before the remaining ports add more shell launches.

This proposal amends the scope already listed for this change in `openspec/roadmap.md` (change 6). The design is written when this change starts, because `native-cli-pr-pair-flow`, `native-cli-library-foundations` and `native-cli-internal-calls` will change the code it would cite.

## What Changes

The scope already on the roadmap stands: a native launcher with command lookup, exit 127, stdin, signal and deadline behaviour preserved, no deadline added to unbounded calls, native replacements for `mktemp`, `ln`, `sleep`, `date`, `getconf`, `pwd -P` and `cygpath`, and an ADR adding to 0027. This amendment adds or rewords the following.

- **BREAKING:** a file name that is not valid UTF-8 is refused with a named stop wherever a safety check would otherwise skip it. Specwright no longer promises to carry such names through.
- **BREAKING:** the launcher passes UTF-8 arguments, with a named refusal for input it cannot represent, replacing the earlier promise of exact argument bytes.
- The surrogate escaping in `cli/lib/src/vcs/codec.dart` shrinks to what the named stop needs. About two dozen files under `cli/lib/src` import it today, and each is reviewed.
- The `find`-based walks in `cli/lib/src/vcs/walk.dart` and `cli/lib/src/finish/walk.dart` become a native listing in stable sorted order.

### Tests that retire

- `cli/test/vcs/codec_test.dart`: the cases that follow CPython's `surrogateescape` decoder (overlong forms, encoded surrogates, truncated sequences).
- `cli/test/vcs/raw_path_test.dart`: cases that exist only to keep non-UTF-8 bytes through a listing.
- `cli/test/vcs/document_test.dart`: the case that writes lone U+DC80..U+DCFF back as bytes (kept alive by `native-cli-library-foundations` until this change).

### Tests that change from exact bytes to outcomes

- `evals/vcs/test_sw_bytes.py`: round-trip cases assert the named stop and that nothing was committed.
- `evals/vcs/test_sw_scripts.py` `test_scripts_under_non_utf8_directory`: asserts the named stop, or the supported install location.
- `evals/pr-pair/test_parity.py`: its non-UTF-8 cases assert the named stop on the `sw` side, as a listed difference from the oracle.
- Walk tests compare the sorted list of names, on every OS, in place of `os.walk` order.
- `evals/cli` launcher cases record the argument values each tool receives, on the three CI platforms.

### Skills and scripts that change

- Shim handoff in `vcs.sh`, `as.sh`, `finish.sh`, `task-cover.sh` and `fit-subject.sh`: a record that is not valid UTF-8 reaches the same named stop. The NUL-record handoff itself stays until `native-cli-retire-scripts`.
- `specwright-pr`, `specwright-commit`, `specwright-finish` and `specwright-branch` state the named stop in their failure text, so the agent tells the user to rename the file rather than work around it.
- `scripts/install-sw.sh` is unaffected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `native-cli`: "Arguments reach native executables unchanged", reworded to UTF-8 arguments with a named refusal, and the new launcher.
- `vcs-backends`: name handling in "sw vcs documents keep their values and name bytes" (as renamed by `native-cli-library-foundations`) and the walk's order.
- `change-finish` and `task-commits`: the non-UTF-8 scenarios become the named stop.
- `github-identity`: the fenced command starts without a shell and receives UTF-8 argument values, with the named refusal.
- `pr-script-runtime`: direct fenced reads pass argument values without a shell, and a non-UTF-8 `SPECWRIGHT_STATE_DIR` or `HOME` stops feedback with the named error instead of keeping raw bytes (S4).

## Impact

Touches `cli/lib/src/process/`, `cli/lib/src/vcs/` (walks, codec and its callers), `cli/lib/src/finish/walk.dart`, shim records, and the skill failure text listed above. Records a new ADR adding to 0027 that defines argument encoding on each OS, MSYS-form path input and extensionless Windows scripts. `shellQuote`, `quoteBatchLine`, process-tree, job-object and FFI code stay custom and are not replaced. A project with a tracked non-UTF-8 name stops with the named error until the file is renamed.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Refuse non-UTF-8 names instead of carrying them

- **Choice:** A named stop wherever a safety check would otherwise skip such a name.
- **Rejected:** Keep byte-preserving names through `sw`, which keeps the escaping across two dozen files for a case that does not occur in practice.
- **Reversal cost:** medium
- **Important:** yes, changes what users see.
- **Chosen by:** user, "refuse non-UTF-8 file names with a named stop wherever a safety check would otherwise skip them".

### S2: A native listing in stable sorted order

- **Choice:** Replace the `find` walks with a native listing in sorted order.
- **Rejected:** Keep `find -print0`, which needs a shell-free way to launch it and exposes OS order.
- **Reversal cost:** low
- **Important:** no.
- **Chosen by:** user, "replace the find-based walks with a native listing in stable sorted order".

### S3: Write the design at this change's turn

- **Choice:** This proposal only; design, specs and tasks are written when the change starts.
- **Rejected:** Full artifacts now, which the intervening ports would make stale.
- **Reversal cost:** low
- **Important:** yes, binds future changes.
- **Chosen by:** user, "Their designs are written at their turn, because the intervening ports would make them stale."

### S4: Non-UTF-8 state and home paths get the same named stop

- **Choice:** A non-UTF-8 `SPECWRIGHT_STATE_DIR` or `HOME` stops feedback with the named error, so the `getenv` FFI reader and the rest of the escaping codec can go.
- **Rejected:** Keep raw POSIX bytes for the feedback state paths, which keeps the FFI reader and part of the codec for this case alone.
- **Reversal cost:** low
- **Important:** yes, changes what users see.
- **Chosen by:** user, "Same named stop".

## Release Notes

`sw` starts external tools without bash, and refuses file names that are not valid UTF-8 with a named error instead of carrying their bytes through.

### Changed

- `sw` launches external tools natively, passing UTF-8 arguments and refusing input it cannot represent by name (#148).
- File listings use a native, stable sorted order (#148).

### Removed

- Support for carrying non-UTF-8 file names through `sw`: such a name now stops the command with a named error asking for a rename (#148).
