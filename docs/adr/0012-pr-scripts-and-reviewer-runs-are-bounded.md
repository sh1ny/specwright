# 0012. PR scripts and reviewer runs are bounded

- Status: accepted
- Date: 2026-10-20

## Context
The PR scripts and the reviewer runner trusted GitHub and the reviewer CLIs to answer in reasonable time and size. No `gh` or `git` network call in `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh` or `as.sh` had a deadline, paged lists were buffered whole, and the watch timeout counted sleeps, so a hung poll blocked both the timeout report and the ownership check (#40). `review-run.sh` checked reviewer output only after the CLI exited or hit `review.timeout`, so runaway stdout was bounded only by free disk and stderr was never checked (#80). The cost tier (M4) needs bounded, predictable script runs before cheaper models lean on them. Only one process-tree deadline existed in the skills, `review-run.sh`'s `capture`/`kill_tree`, which writes output to files because a killed process tree cannot leave a pipe open.

## Decision
Every network command run by the PR scripts (`pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh`, and `as.sh`'s own lookups), and every reviewer run by `review-run.sh`, has a deadline and an output bound.

- **One shared runner for the PR scripts.** `skills/specwright-pr/scripts/bounded.py` (stdlib only) starts the command with its output in files, polls every 0.1 s, and kills the process tree by PID (taskkill `/T /F` on Windows, `killpg` on POSIX, never by name) when the deadline passes or stdout passes the byte bound. `pr-pair.sh` loads it by path; the bash scripts call its CLI through a `gh` shell function that wraps `bash -c 'exec gh "$@"'`, so shims and the eval fake still resolve on Windows.
- **Credentials never reach a file.** A `gh auth token` lookup runs in secret mode: pipes with `communicate(timeout)`, `kill_tree` at the deadline, then one more `communicate(timeout=5)`, so a lookup never waits past its deadline plus 5 s.
- **Fixed bounds.** 120 s per command, 300 s for a paginated read, 32 MiB of stdout per command, 50 pages in a cursor loop a script drives itself. Test-only environment overrides live in `bounded.py`'s header; no configuration key is added. The watch gives each poll, the first snapshot included, one 120 s deadline for all its commands and measures `--timeout` as elapsed time.
- **A limit is reported by name.** It is `deadline_exceeded` or `response_too_large`, never a generic failure. In `pr-pair.sh` it is GitHub state unknown (exit 3); `as.sh` exits 3 naming it; `pr-snapshot.sh` and `pr-reply.sh` name it on stderr and keep their failure exits.
- **A write cut off this way is GitHub state unknown**, decided by a read-back (the merge PUT) or by the next snapshot (replies), never retried inside a script.
- **Reviewer output is checked while it runs.** `review-run.sh` keeps its own `kill_tree` (the review skill is installed separately) and checks stdout, stderr and codex's answer file every 0.25 s: stdout 2 MiB on claude and 64 MiB on codex and OMP, stderr 8 MiB, the answer file 2 MiB, probes 1 MiB. Passing a bound stops the tree and fails the run `invalid` with `output too large`, naming the stream, and writes nothing (fail closed, ADR 0007).
- **New PR scripts follow it.**

**Known exceptions.** `release.sh` (`git ls-remote`, `gh api --paginate`, `gh release create`, `git push`), `finish.sh` and `update.sh` stay unbounded for now. They are tracked in https://github.com/sh1ny/specwright/issues/111.

**Rejected: coreutils `timeout` in the bash scripts**, because it is missing on stock macOS, has no output bound, and on Windows does not reliably stop a native `gh.exe` started through an MSYS shim. **Rejected: a bash background-and-kill loop, or bounding inside each script**, because each copies the tree-kill logic and none bounds bytes. **Rejected: `pr.command_timeout` and `pr.max_response` settings**, because nobody has asked to tune them and they add configuration surface every script must read before its first call. **Rejected: importing `bounded.py` from the review skill**, because it would tie two independently installed skill folders together.

## Consequences
- A hung or oversized `gh` response stops each PR script within its deadline or bound with a named error, and the watch always reports its timeout within 130 s of it passing.
- `pr-snapshot.sh`, `pr-reply.sh` and `as.sh` now need Python 3.8+, already a checked prerequisite of the PR scripts. Each bounded call adds a Python start (about 50-150 ms on Windows).
- A runner itself killed by SIGKILL can leave its temp dir (non-secret output only) and a hung child behind; this is accepted, since only a hung `gh` would leak and it holds no lock or claim.
- The exceptions above violate this decision until their issue is fixed.
- Reversal cost: low. The bounds sit behind one function, one CLI and `review-run.sh`'s `capture`.
