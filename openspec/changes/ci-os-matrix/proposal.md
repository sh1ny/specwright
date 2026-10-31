# Proposal

## Why

`.github/workflows/evals.yml` runs every eval suite on `ubuntu-24.04` only, but much of the shipped code is platform-specific: MSYS argv quoting in `vcs.sh`, `\` versus `/` paths and `cygpath`, CRLF handling and Git Bash PATH conversion. Linux CI never exercises any of it. Meanwhile local runs on Windows are slow and take over the machine: `pr-pair` takes about 57 minutes locally against 6 in Linux CI. Three `evals/vcs/test_git_backend.py` cases also crash real `git` (`0xC0000005`) on this machine, and nobody can tell yet whether that is the machine or a real problem. Issue #145 asks to run every suite on Linux, Windows and macOS in CI and to stop running suites locally during a change.

This change is M6 (Packs), change 1, version 0.12.1. It serves these exit criteria:
- `.github/workflows/evals.yml` runs every suite from `evals/run.py --list-suites` on `ubuntu-24.04`, `windows-latest` and `macos-latest`, with `fail-fast: false`. Every job passes on the PR that adds it and on each later M6 PR.
- Every issue in M6's changes is closed by a merged PR, and each code fix has a regression test in `evals/`.
- The change ships as its own release, 0.12.1.

## What Changes

- **OS matrix.** The `suite` job becomes a matrix of `ubuntu-24.04`, `windows-latest` and `macos-latest` × every suite from `python evals/run.py --list-suites`, with `fail-fast: false`. One check runs per suite and OS. Every step runs under `bash`, which is Git Bash on Windows. On Windows, Git's `usr/bin` (`cygpath`, `sed` and the rest of the POSIX userland the scripts need) comes before any other `bash` on PATH. Python 3.8 and 3.12, the pinned OpenSpec CLI and the Git identity step work on every OS.
- **Pinned, checksummed jj on every OS.** The jj in `JJ_VERSION` (0.46.0) is installed from the release archive for each runner: the Linux x86_64 musl archive (as today), the macOS arm64 archive and the Windows x86_64 zip. Each archive has its own pinned SHA-256, taken from the jj release, and is checked before the binary is unpacked or run. The check is portable and does not depend on `sha256sum --check`, which macOS's BSD `sha256sum` lacks.
- **`but` stays Linux-only.** GitButler publishes a standalone `but` CLI only for Linux. Its macOS download is the desktop app, with no `but` binary in it, and its Windows download is an MSI. The pinned `but` is therefore installed only in the Linux `vcs` job, and only Linux jobs set `SPECWRIGHT_REQUIRE_BUT=1`. On macOS and Windows the GitButler tests skip with `but not installed`. An issue names that gap, as #145 requires for any test that skips on one OS only.
- **Per-OS timeouts.** Each OS gets its own job timeout and `run.py --timeout`, set from the measured wall times of the first matrix runs (Windows is expected to be the slowest).
- **Pin files stay LF.** `.gitattributes` gains `*VERSION text eol=lf`, so `OPENSPEC_VERSION`, `JJ_VERSION`, `BUT_VERSION` and `VERSION` check out without `\r` on Windows and the workflow's version reads stay exact.
- **Skips are visible per OS.** `run.py` prints each suite's skipped count next to its test count, so a test skipped on one OS only shows as a difference between the jobs. A new runner test checks that every skip conditioned on the OS names an issue (`#<n>`) or says the tested mechanism is `platform:`-specific.
- **Platform failures fixed or filed.** Whatever the new jobs turn up is fixed, with a regression test, or filed as an issue that names it. That includes the `test_git_backend` crash, Windows `SERIAL` timing, and BSD `sed`/`find`/`stat`/`mktemp` differences on macOS. No test is skipped on one OS without an issue that names it: OS-conditioned skips are checked by the runner test, and any other one-OS-only skip shows in the skipped counts and is triaged like a failure. A suite or file that runs past its timeout on one OS is fixed in this change (a higher timeout, then a split), never deferred.
- **CI instead of local eval runs.** `AGENTS.md`, `CONTRIBUTING.md`, the README and the architecture's evals row stop telling contributors to run `python evals/run.py --changed main` or whole suites (`python -m unittest discover evals/<suite>`) during a change. During a change they rely on the CI matrix. Locally they run only the test module they are writing, red then green, and the `evals/runner` map test after adding files. A milestone close no longer runs every suite locally: it relies on a green matrix run on `main`, started by a manual dispatch. `run.py --changed` itself stays, unchanged. No shipped skill names `--changed main`, so no skill changes.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `eval-runner`:
  - CI runs every suite on all three OSes, not only Linux.
  - jj is pinned and checksummed per OS.
  - `but` is required only on Linux.
  - The runner prints each suite's skipped count.
  - OS-conditioned skips name an issue or are marked `platform:`.
  - The instructions name CI, the single-module and map-test local checks, and the milestone-close dispatch run instead of `--changed main` or whole-suite runs.

## Impact

- **CI:** `.github/workflows/evals.yml` (matrix, shell, PATH, jj and `but` steps, per-OS timeouts). Check names change from `<suite>` to one per suite and OS. No branch protection or ruleset on `main` names them today.
- **Evals:**
  - `evals/runner/test_ci_workflow.py` asserts the OS matrix, `fail-fast: false`, each OS's jj asset and checksum, the check before use, and `but` on Linux only.
  - `evals/runner/test_agent_instructions.py` checks the new instruction text and fails on `--changed main` or `unittest discover evals/` in `AGENTS.md`, `CONTRIBUTING.md` or `README.md`.
  - `evals/run.py` prints the skipped count; `evals/runner/test_run.py` covers it.
  - A new `evals/runner/test_platform_skips.py` scans OS-conditioned skips; six existing reasons gain `platform:`.
  - `evals/bashexe.py` resolves Git Bash for every eval that starts bash; `evals/runner/test_bare_bash.py` forbids a bare `"bash"` argv; `evals/runner/test_bash3.py` keeps shipped scripts on bash 3.2 (macOS).
  - Fixes from triage land with regression tests in their suites.
- **Docs:** `AGENTS.md`, `CONTRIBUTING.md` (the testing section, including the per-area `unittest discover` bullets), `README.md`, `openspec/architecture.md` (evals row, which today says "on Linux"), `openspec/roadmap.md` (this change's line said `but` per OS).
- **Repo config:** `.gitattributes` (`*VERSION text eol=lf`).
- **Release:** version files bumped to 0.12.1.
- **Dependencies:** none new. jj and `but` stay at their pinned versions.

## Release Notes

Every eval suite now runs in CI on Linux, Windows and macOS for each pull request, so the platform-specific parts of Specwright (Git Bash argv quoting, `cygpath`, CRLF, BSD tools) are tested on all three. jj is pinned and checksum-verified on each OS. Contributors no longer run eval suites locally during a change.

### Changed
- `.github/workflows/evals.yml` runs every suite on `ubuntu-24.04`, `windows-latest` and `macos-latest` with `fail-fast: false`, with a pinned, checksum-verified jj on each OS; `but` stays Linux-only because GitButler ships no standalone CLI for macOS or Windows (#145, #154).
- `AGENTS.md`, `CONTRIBUTING.md` and the README rely on the CI matrix during a change and at a milestone close instead of local `run.py --changed main` runs (#145).

### Fixed
- `scripts/update.sh` reads its journal without `mapfile`, so `update` runs under macOS's `/bin/bash`, which is bash 3.2 (#145).
- On macOS, `scripts/update.sh` again puts back a lock that another update run took while this one was replacing a stale lock. It used GNU `mv -T`, which BSD `mv` lacks, so the other run's lock was left renamed aside (#145).
