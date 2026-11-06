# Review

## Metadata

- **Round:** 4
- **Re-check:** Required Change 1 applied: `design.md:40,84` moves the scripts directory, bash path and operation into NUL-terminated stdin records, leaving only `--args-stdin` on argv; C1, the decision table and shim flowchart agree (`design.md:131,152,170`). The Linux 0xFF installation-path scenario asserts the settings script’s location, backend and exit status (`specs/vcs-backends/spec.md:84-86`), covering the directory-derived script paths in `vcs.sh:10-13,27-30`. Required Change 2 applied: D5 (`design.md:68`) supplies explicit skills/agents targets, requires Step 7 verification before stamping, then `finish`, and requires a scratch-clone proof starting with an older stamp and resolving the tree-version binary. This matches `scripts/update.sh:15-20,266-267,969-971,1859-1860` and `README.md:400-426`. Suggestion applied in `proposal.md:14`.
- **Prior round:** Round 3 REVISE was escalated; user chose all fixes plus a consistency sweep: C1 now stamps before finish, M1 uses count framing, M2 conditions both warning statements, and M3 gives D7 the stdin handoff.
- **Reviewer:** OMP CLI (OpenAI Codex)
- **Reviewed:** Proposal, both delta specs, design, round-3 review and Rebuttals; schema review instruction; architecture; ADRs 0004, 0008, 0011, 0014, 0017, 0018, 0021, 0026 and 0027; main vcs-backends, native-cli and install-update specs; cited sections of vcs.sh, sw-path.sh, pr-pair.sh, finish.sh, update.sh, README.md, evals.yml and both harnesses; cli/lib and pubspec.yaml; CONTRIBUTING.md and evals/suites.json.
- **Verification:** Static inspection only. Runtime execution and `git ls-files`/symlink checks were unavailable. The installed-VERSION citation was not opened or independently verified.

## Findings

### Critical (blocking)

None.

### Moderate

**M1 — The byte-preserving handoff still passes the scripts directory through Dart argv.**

D2 and D7 (`design.md:40,84`) put `--scripts <dir>` and `--bash <path>` on argv. Only operation arguments use stdin. D4 and C6 instead promise that names never pass through Dart’s lossy argv decoding.

The current implementation obtains `VCS_DIR` from Python’s environment and derives `pr-pair.sh` and `as.sh` from it (`vcs.sh:10-13,27-30`). Their locations therefore need preservation too.

[INFERENCE] On POSIX, an in-repository installation beneath a directory containing byte 0xFF loses that byte in `<dir>` before the proposed codec runs. Subsequent settings and fence calls target another, nonexistent path—even when every operation argument arrived intact.

Specify a byte-preserving route for the scripts-directory path and other path-valued handoff metadata. Include a POSIX scenario with installed scripts beneath a non-UTF-8 directory.

**M2 — D5’s prescribed bootstrap omits required installation targets.**

`design.md:68` specifies `--code .`, `--download .` and `--ref <branch>` through `plan`, `stage` and `swap`, but supplies no skills or agents target.

The updater initializes both target lists empty (`scripts/update.sh:266-267`). `build_groups` explicitly refuses empty lists with `no_targets` (`scripts/update.sh:1859-1860`).

[INFERENCE] Following the stated invocation stops at `plan`; the corrected stamp-before-finish ordering is never reached.

Name the target arguments in the bootstrap and scratch-clone proof. Also retain the verification-before-stamping boundary from `README.md:400-426`; D5 currently moves directly from swap to copying VERSION.

### Suggestions

Remove `update.sh` from the proposal’s “keep calling vcs.sh unchanged” list (`proposal.md:14`). D7 intentionally changes that caller to invoke the download’s binary directly.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Revise D2/D7 and the corresponding handoff contract to preserve path-valued metadata without Dart argv decoding. Add an assertable POSIX scenario covering a non-UTF-8 scripts-directory path.
2. Complete D5’s bootstrap with explicit installation targets and verification before stamping. Require its scratch-clone proof to use those arguments, start with an older stamp, complete `finish`, and resolve the tree-version binary.

CHANGES_APPLIED: yes

## Rebuttals
Round 4 Required Changes, as applied by the author (the reviewer's re-check sets `CHANGES_APPLIED`):

1. **Required Change 1 (applied; the user chose a stdin header for D2):** `sw vcs` takes only `--args-stdin` on argv. The shim writes the scripts directory, the bash path, the subcommand and every argument on stdin as NUL-terminated records, and fewer than three records is a usage error. D7's `update.sh` call writes the download's scripts directory and bash the same way. C1, the decision table and the flowchart now say the same. A new scenario under "sw vcs reads settings and fences identity through the existing scripts" covers scripts installed under a directory whose name holds 0xFF on Linux.
2. **Required Change 2 (applied):** D5's bootstrap names its targets (`--skills <dir>`, repeated, and `--agents <kind>=<dir>`; this repo uses `--skills .claude/skills --agents claude=.claude/agents`). It runs the install prompt's Step 7 checks before the stamp. The scratch-clone proof uses those arguments, starts from an older stamp, completes `finish`, and resolves the tree-version binary.
- **Suggestion (applied):** `proposal.md` no longer lists `update.sh` among the callers that are unchanged. It now says `update.sh` changes only its jj-store read.