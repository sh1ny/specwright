#!/usr/bin/env bash
# A shim (ADR 0028): it finds the project's `sw` through sw-path.sh and runs `sw pr snapshot --args-stdin`, handing it this directory, this bash and
# the whole command line as NUL-terminated stdin records. Everything below the usage lives in `sw pr snapshot`, which keeps this script's
# arguments, messages, output and exit statuses. No `sw` that sw-path.sh accepts: one `sw_missing` JSON document on stdout, exit 1; no fallback.
# One-call PR snapshot: state, checks, unresolved threads, unhandled comments
# and reviews, as one JSON line. Needs gh (uses gh's built-in --jq) and Python 3.8+:
# sw's bounded runner gives every gh call a deadline and a size bound, so a hung call ends as
# `deadline_exceeded` on stderr (exit 1 in a watch); without Python, exit 2 `no_python`.
# The same bound runs the reviewer evaluator (`sw pr reviewers`, see below).
#
# Usage: bash pr-snapshot.sh [PR-number|PR-url] [--repo owner/name] [--logs]
#                            [--reviewer-config FILE]
#                            [--wait [--timeout SECONDS] [--interval SECONDS] [--until attention]]
#        bash pr-snapshot.sh --full NODE_ID [--repo owner/name]
#   (no PR)   the PR for the current branch
#   --reviewer-config  the reviewer config file pr-pair.sh writes (context / policy):
#             which logins to watch, their role and timeout, and how each one's report
#             is recognised. The file is checked by `sw pr reviewers --check-config` before
#             any gh call: a missing file, bad JSON, a bad key or pattern exits 2 with one
#             line naming the file or `<login>: report.<key>`. This script knows no
#             reviewer by name: it gathers what the configured logins wrote, in full, into
#             a system-temp file (removed on exit, also when the evaluator is stopped at its
#             deadline) and `sw pr reviewers` decides, then adds "reviewers" (login, role,
#             timeout, state, by, evidence), "reviewer_config" (the file's digest) and "now".
#             Without the flag there are no reviewers ("reviewers": [], "reviewer_config":
#             null). The removed flag '--reviewer' (LOGIN:ROLE:SECONDS) exits 2 naming the new flag.
#   --logs    append the last 80 lines of each failing run's failed-step log
#   --full    read one item whole: the NODE_ID of a thread comment, PR comment or review
#             (the snapshot's "id"). Prints {"ok":true,"id","kind","body","rev","url"}
#             with the raw body; kind is thread_comment | comment | review; rev is the
#             item's own revision (lastEditedAt, else createdAt/submittedAt), never what
#             pr-reply.sh --rev takes. An unknown id prints {"ok":false,"error":"not_found"}
#             and exits 1; exits 3 when GitHub cannot be read. One call; no snapshot, no
#             --reviewer, no watch claim. Read every item with "clipped":true this way.
#   --wait    poll inside this process; print {"wake":..., "snapshot":...}
#             once anything changes (checks, threads, comments, reviews, head,
#             state, edits, a list getting cut off) or the timeout passes
#             (default 1800s, interval 300s) - elapsed time from the start, polls
#             included, and never slept past; "waited" is the elapsed seconds. Each
#             poll, the first snapshot included, has one 120 s deadline for all its gh
#             calls (SPECWRIGHT_NET_DEADLINE, a non-negative number of seconds, lowers it), so the timeout is reported
#             within ~130 s of passing. "incomplete" at once if the first good
#             snapshot is already cut off; exits 1 if the last poll failed (a failed
#             first snapshot has no base: the first good poll becomes it).
#             One watcher per PR on this machine: a newer --wait on the same
#             PR (from any agent; owner/name compared case-insensitively) takes
#             over, and the older one exits 4 before its next poll, so a lost
#             or forgotten watcher stops spending the account's API budget. A
#             watcher's exit never ends a newer watcher's ownership. If the
#             state directory cannot be created, it polls unowned and says so
#             on stderr.
#   --until attention  (with --wait only; "quiet" or any other mode exits 2 before any gh
#             call) keep waiting while a poll differs from the first good snapshot only
#             in checks or merge state, a CI check ("checks":{"ci_pending"} above 0: a
#             check that is not a reviewer's own) is still pending, no check fails that
#             was not failing in that snapshot, and the merge state is not DIRTY. Any
#             other difference wakes "changed", a reviewer's state change included. Skipped
#             polls add no polls and no gh
#             calls; the wake JSON counts them as "filtered" (always present with
#             --wait, 0 without --until). A "timeout" wake still means nothing else
#             changed, filtered polls included. The snapshot's "attn" is "sig" without
#             the checks and merge state; "fail_names" are the failing checks' names,
#             base64 each.
# "head_cutoff": {source, at} says where reports start to count and each
# reviewer's timeout starts: source push | first_seen | first_seen_unsaved (the
# push is not in the activity log; see prepare_cfg).
# "clipped": true on a thread comment, PR comment or review means its body was cut
# at 2500 (thread comments) or 1200 (the others) characters; stripping HTML comments
# alone does not count.
# "complete": false means a list was cut off at its page size - do not treat
# missing items as absent.
# Wrap with as.sh to pin the GitHub identity.
set -euo pipefail

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
[ -n "$py" ] || { echo 'pr-snapshot.sh: no_python: needs python 3.8+ for its bounded gh calls' >&2; exit 2; }
SW_DIR=$(cd "$(dirname "$0")" && pwd -P)
SW_BASH=${BASH:-bash}
if command -v cygpath >/dev/null 2>&1; then SW_DIR=$(cygpath -m "$SW_DIR"); SW_BASH=$(cygpath -w "$SW_BASH"); fi

# The project: the current directory, then up to the first `.git` entry.
dir=$(pwd -P)
proj=$dir
while [ ! -e "$proj/.git" ] && [ "$proj" != / ]; do proj=$(dirname "$proj"); done
[ -e "$proj/.git" ] || proj=$dir

# No temp file before sw runs (the evals fake the command): a resolver that fails is run once more to capture its stderr.
if ! sw=$("$BASH" "$SW_DIR/sw-path.sh" --code "$proj" 2>/dev/null); then
  err=$("$BASH" "$SW_DIR/sw-path.sh" --code "$proj" 2>&1 >/dev/null || true)
  printf '%s' "$err" | "$py" -I -X utf8 -c 'import json, sys; print(json.dumps({"ok": False, "error": "sw_missing", "message": sys.stdin.read().rstrip("\r\n")}, ensure_ascii=False))'
  printf '%s\n' "$err" >&2
  exit 1
fi
exec "$sw" pr snapshot --args-stdin < <(printf '%s\0' "$SW_DIR" "$SW_BASH" "$@")
