# CI run: task 7.2

PR #203, head `457c034ce92d3ae6c5639a3cf708ba6403fda055`. Recorded 2026-11-05.

## cli.yml (build, artifact, download-and-run)

Run: https://github.com/sh1ny/specwright/actions/runs/42073150467 (success)

| Job | Result |
|---|---|
| build (ubuntu-24.04) | success |
| build (windows-latest) | success |
| build (macos-latest) | success |
| verify (ubuntu-24.04) | success |
| verify (windows-latest) | success |
| verify (macos-latest) | success |

Each build job ran `mise run deps`, `analyze`, `format`, `test` and `build`. Each verify job then downloaded the artifact in a fresh job, checked its checksum and ran it (`version ok: 0.23.0` on all three).

| Artifact | SHA-256 (of the binary, from the build job; matched by verify) |
|---|---|
| sw-linux-x64 | `59bb157f9da25ed858d7e2b1c771e34603c48e270442cd681b5905ccaa8f0396` |
| sw-macos-arm64 | `7d200f7970c8270c2933b2854e6cfa14a8b87c0e92fd99005378bf5d53490e0e` |
| sw-windows-x64.exe | `537ca17f88568abb9b6f1efb3791cc48c56c47cc1904926c95a425d416144ced` |

## macOS quarantine (A2)

The verify (macos-latest) log line:

```
A2: the quarantined binary ran before the step
```

On this runner, the downloaded binary with the quarantine attribute ran even before the explicit quarantine step. Gatekeeper did not block an unsigned binary executed from a CI shell. That is no evidence for a download through a browser on a user's Mac, which `native-cli-distribution` still has to check.

## evals.yml (process-tree and sweep rows)

Run: https://github.com/sh1ny/specwright/actions/runs/42073150474 (success)

The `cli` and `runner` suites ran on Linux, Windows and macOS against a `sw` built from the tree (`SPECWRIGHT_REQUIRE_SW=1`, so a missing binary fails rather than skips). This run proves the rows flipped green in this commit: `test_sw_tree.py` (orphaned grandchild, held startup, nested job, no job, helper death after ready and between hello and ready, pre-hello limit, spawn record) and `test_run.py`'s `test_sweep_stops_sw_sessions_after_timeout`. The Windows-only rows skip on Linux and macOS with a `platform:` reason, and the POSIX-only rows skip on Windows.

## Windows antivirus check (task 9.1, by the owner)

The owner downloaded the `sw-windows-x64` artifact from the cli.yml run above in a browser and extracted it on their own machine, with Malwarebytes real-time protection on.
- SHA-256 `537ca17f88568abb9b6f1efb3791cc48c56c47cc1904926c95a425d416144ced`, which matches the build job.
- `sw-windows-x64.exe version --json` printed `{"version":"0.23.0","interface":1}`.
- A Malwarebytes custom scan of the zip and the folder checked 2 items: 0 threats, 0 PUPs, 0 PUMs, nothing quarantined.
- Nothing blocked the download, the extraction or the run, and neither Malwarebytes nor SmartScreen showed a prompt.

Under ADR 0027 the unsigned build stands. Signing stays the response to a future block.
