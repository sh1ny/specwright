#!/usr/bin/env bash
# A shim (ADR 0028): it finds the project's `sw` through sw-path.sh and runs `sw pr reply --args-stdin`, handing it this directory, this bash and
# the whole command line as NUL-terminated stdin records. Everything below the usage lives in `sw pr reply`, which keeps this script's
# arguments, messages, output and exit statuses. No `sw` that sw-path.sh accepts: one `sw_missing` JSON document on stdout, exit 1; no fallback.
# C14: no temp-file command runs before `sw` does (the evals fake it for the reply's body file), so a resolver that fails is run once more
# to capture its stderr, and the body file with its marker is made by `sw pr reply`.
# Reply to one piece of PR feedback, then (optionally) resolve its thread.
# Every reply carries a hidden `specwright:handled <source-id>` marker (plus
# `resolve` when the thread is to be resolved), so pr-snapshot.sh stops listing
# that item and can spot a resolution that failed - dedup state lives on GitHub.
#
# Usage:
#   bash pr-reply.sh <PR> thread  <thread-id> <root-comment-id> <body-file> [--resolve] [--react +1|-1] [--waiting] [--rev REV] [--repo o/n]
#   bash pr-reply.sh <PR> comment <source-id> <body-file> [--react +1|-1] [--waiting] [--rev REV] [--repo o/n]
#   bash pr-reply.sh <PR> react   <comment-id> +1|-1 [--repo o/n]
#   bash pr-reply.sh <PR> resolve <thread-id> [--rev REV] [--repo o/n]   (retry a failed resolution, or close a
#                                                              thread the reviewer only acknowledged)
# --react puts a thumbs up (+1: the finding was right) or down (-1: it was
# wrong) on the item answered: the thread's root comment, or the comment or
# review <source-id>. react alone answers a reviewer's follow-up without a
# reply; <comment-id> is a node id from the snapshot, or a review comment's
# numeric id. --waiting marks a "waiting on owner" reply (specwright:waiting):
# the snapshot keeps the item listed, with waiting_owner, until it is handled.
# --rev REV is the item's `rev` from the snapshot (or the pass record's
# revision.rev): the script re-reads the item first and posts, resolves and
# reacts to nothing when its revision now differs (exit 5, "judged A, now B" on
# stderr) or cannot be read, or is a thread of more than 100 comments (exit 3).
# The marker then carries `rev=REV`, which binds the reply to the text that
# was judged. Without --rev it behaves as in 0.1.10: no re-read, a marker
# without a revision.
# Thread replies use REST (GraphQL replies can attach to a pending review and
# stay invisible). Exit 2: a pending review of yours exists - submit or
# discard it on GitHub first. Exit 4: refused before any GitHub call (bad
# arguments, or a body file missing, unreadable, empty or not written in full
# with its marker); nothing was posted, and stderr names the cause.
# Wrap with as.sh to pin the GitHub identity.
# Needs bash, gh and Python 3.8+; every gh call has a deadline (sw's bounded runner), and a limit stops the script non-zero
# (`bounded: deadline_exceeded: gh api` on stderr) after its temp file is removed.
set -euo pipefail

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
[ -n "$py" ] || { echo 'pr-reply.sh: no_python: needs python 3.8+ for its bounded gh calls' >&2; exit 2; }
SW_DIR=$(cd "$(dirname "$0")" && pwd -P)
SW_BASH=${BASH:-bash}
if command -v cygpath >/dev/null 2>&1; then SW_DIR=$(cygpath -m "$SW_DIR"); SW_BASH=$(cygpath -w "$SW_BASH"); fi

# One optional leading `--project <dir>` names the code project whose `sw` runs; it is never passed on to `sw`.
# Without it the project is the current directory, then up to the first `.git` entry.
if [ "${1:-}" = --project ]; then
  if [ "$#" -lt 2 ] || [ -z "${2:-}" ]; then
    echo 'pr-reply.sh: usage: pr-reply.sh [--project <code-checkout>] <PR> <thread|comment|react|resolve> ...' >&2
    exit 4
  fi
  proj=$2
  shift 2
  if [ "${1:-}" = --project ]; then
    echo 'pr-reply.sh: usage: only one leading --project is allowed' >&2
    exit 4
  fi
else
  dir=$(pwd -P)
  proj=$dir
  while [ ! -e "$proj/.git" ] && [ "$proj" != / ]; do proj=$(dirname "$proj"); done
  [ -e "$proj/.git" ] || proj=$dir
fi

# No temp file before sw runs (the evals fake the command): a resolver that fails is run once more to capture its stderr.
if ! sw=$("$BASH" "$SW_DIR/sw-path.sh" --code "$proj" 2>/dev/null); then
  err=$("$BASH" "$SW_DIR/sw-path.sh" --code "$proj" 2>&1 >/dev/null || true)
  printf '%s' "$err" | "$py" -I -X utf8 -c 'import json, sys; print(json.dumps({"ok": False, "error": "sw_missing", "message": sys.stdin.read().rstrip("\r\n")}, ensure_ascii=False))'
  printf '%s\n' "$err" >&2
  exit 1
fi
exec "$sw" pr reply --args-stdin < <(printf '%s\0' "$SW_DIR" "$SW_BASH" "$@")
