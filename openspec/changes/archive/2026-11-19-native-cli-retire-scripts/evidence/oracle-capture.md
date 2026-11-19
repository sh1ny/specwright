# Parity oracle capture (task 6.5)

The frozen side of the pr-pair parity evals (`test_parity.py`, `test_workflow_parity.py`, `test_workflow_records.py`, `test_workflow_transport.py`) was run once per OS and its records were committed, so that from the cutover on, `sw pr` is compared with these records instead of the deleted scripts (D14).

## How

- Fixture commits carry a pinned author, committer and date (`PINNED_IDENTITY` in `evals/pr-pair/oracle_capture.py`), so commit ids repeat across runs and OSes and stay compared exactly.
- With `SPECWRIGHT_ORACLE_RECORDS` set, each frozen-side run writes one record: exit status, `gh` calls, stderr prefixes, parsed stdout, final fake-gh state and comment bodies. Machine paths, temp names and the `.exe` suffix are normalized. The feedback owner id is checked against the record the frozen writer left, then replaced by `<owner>`; other generated owner ids (32 hex digits), the owner host and write times are checked for form, then replaced. Frozen-writer feedback records are kept as bytes (`*.record`), and the frozen-reader-accepted fixture as `fixture.bin`.
- `evals.yml` takes the `workflow_dispatch` input `capture_oracle`: it narrows the matrix to pr-pair, runs `evals/pr-pair/oracle/capture.py` and uploads `oracle-records-<OS>`.
- The capture ran on the throwaway branch `tmp/retire-scripts-g6-capture` (since deleted); the artifacts were downloaded with `gh run download` and checked with `evals/pr-pair/oracle/check_records.py`.

## Runs

- Capture: https://github.com/sh1ny/specwright/actions/runs/44481746350, conclusion **success** on ubuntu-24.04, windows-latest and macos-latest.
- The same tree's normal run: https://github.com/sh1ny/specwright/actions/runs/44481750866, conclusion **success** on all three OSes.
- Earlier captures (44470278425, 44473425575, 44476562481, 44478557139) found the normalization gaps fixed above: a doubled temp-root replacement on Linux, ambient write times, hosts and owner ids, unpinned commit ids, `sw.exe`, and the runner's whole environment in an env dump (now only the `AS_SH_*`, `GH_*` and `GIT_*` lines).

## Agreement check

```
OK 100 cases, 336 records compared across 3 sets (Linux, Windows, macOS), 9 feedback records checked for form, 16 platform skips
OS-dependent, allowed: test_parity.AsParity.test_env_under_the_fence_with_the_token_masked $.stdout (1 comparisons): Git Credential Manager sets GCM_INTERACTIVE on the Windows runner, and the fence keeps it among the originals
OS-dependent, allowed: test_parity.AsParity.test_nested_fence_keeps_the_outer_originals $.stdout (1 comparisons): Git Credential Manager sets GCM_INTERACTIVE on the Windows runner, and the fence keeps it among the originals
OS-dependent, allowed: test_workflow_records.WorkflowRecords.test_directory_record_is_occupied_and_unreadable $.stdout.message (3 comparisons): Python's errno text for reading a directory is the OS's own: EISDIR on Linux and macOS, EACCES on Windows
```

Each set is complete: every case ran on each OS without failure, except the 16 platform skips the outcomes record. The three sets agree after normalization; the only differences are the three listed above, each the frozen scripts' own per-OS behaviour on that runner. Because of them the records are committed per OS, under `evals/pr-pair/oracle/records/{Linux,Windows,macOS}/`, and task 7.2 compares against the running OS's set. `.gitattributes` marks the records `-text`, so the recorded bytes are never converted.
