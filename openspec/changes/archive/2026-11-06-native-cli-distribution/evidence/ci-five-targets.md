# A2 and A3: five targets built and verified in CI

Settles assumptions A2 (the `ubuntu-24.04-arm` and `macos-15-intel` runner labels are available to this repository) and A3 (mise installs Dart 3.13.7 on linux-arm64 and macOS x64, and `dart compile exe` works there with no change to `cli/`).

- Run: https://github.com/sh1ny/specwright/actions/runs/42125939400
- Workflow: `cli.yml` (calls `sw-build.yml`), event `workflow_dispatch` on `feat/native-cli-distribution`
- Head: `5347277164efc2f95f80249c35f9e75c594c374f` (group 2 commit)
- Started 2026-11-05T22:58:39Z, finished 2026-11-05T23:00:09Z; run conclusion `success`

| Job | Result | Started (UTC) | Completed (UTC) |
|---|---|---|---|
| build (linux-x64) | success | 22:58:43 | 22:59:15 |
| build (linux-arm64) | success | 22:58:45 | 22:59:16 |
| build (windows-x64) | success | 22:58:44 | 22:59:50 |
| build (macos-arm64) | success | 22:58:44 | 22:59:27 |
| build (macos-x64) | success | 22:58:44 | 22:59:43 |
| verify (linux-x64) | success | 22:59:53 | 23:00:01 |
| verify (linux-arm64) | success | 22:59:55 | 23:00:03 |
| verify (windows-x64) | success | 22:59:53 | 23:00:08 |
| verify (macos-arm64) | success | 22:59:53 | 23:00:05 |
| verify (macos-x64) | success | 22:59:53 | 23:00:04 |

Each verify job ran `verify_artifact.py` with `--interface-from skills/specwright-pr/scripts/sw-path.sh` on its own runner. That run checked the SHA-256 against the build's `.sha256`, the reported version against `VERSION` (0.23.0 at that head) and the interface against `SW_INTERFACE=1`.

Artifact sizes, as the Actions artifacts API reports them (`size_in_bytes`). These are the uploaded artifact archives, each holding one binary and its `.sha256` file:

| Artifact | Bytes |
|---|---|
| sw-linux-x64 | 2898889 |
| sw-linux-arm64 | 2827228 |
| sw-windows-x64 | 2907836 |
| sw-macos-arm64 | 2650683 |
| sw-macos-x64 | 2841259 |

Every artifact is under 3 MB, well inside the 64 MiB download cap of D3.

Result: A2 and A3 hold. Both new runner labels started and finished their jobs, and Dart under mise compiled and ran `sw` on linux-arm64 and macOS x64 with no change to `cli/`. There is no design drift.
