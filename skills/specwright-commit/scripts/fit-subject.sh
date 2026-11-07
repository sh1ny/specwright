#!/usr/bin/env bash
# Fit a task or group commit subject to 72 characters, in the message file itself. A shim (ADR 0028): it finds the
# project's `sw` through sw-path.sh and runs `sw commit --args-stdin fit-subject`, handing it this directory, this bash
# and the whole command line as NUL-terminated stdin records. All fitting logic lives in `sw commit fit-subject`.
#
# Usage: bash fit-subject.sh <msgfile>
# Line 1 must be `<type>(<scope>): task X.Y <task text>` or `<type>(<scope>): group N <group heading>`. When it is
# longer than 72 characters, line 1 is cut at the last whole word that fits and rewritten in place; every other line is
# kept byte for byte. Prints the final subject. The project is the current directory's.
# Exit 0: fitted, or already fits (file untouched).
# Exit 1: not even the first word fits after the prefix (file untouched), or no `sw` that sw-path.sh accepts (one
#         `sw_missing` JSON document on stdout: no fallback, file untouched; not a subject that does not fit).
# Exit 2: missing file, or line 1 has no task or group prefix.
set -euo pipefail

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
if [ -z "$py" ]; then
  # sw-path.sh needs Python too: say so with a fixed document (exit 2 would tell the skill to fix the message file)
  echo '{"ok":false,"error":"sw_missing","message":"sw missing or mismatched: rerun the install prompt (the resolver needs Python 3.8+)"}'
  echo "sw missing or mismatched: rerun the install prompt (the resolver needs Python 3.8+)" >&2
  exit 1
fi
SELF_DIR=$(cd "$(dirname "$0")" && pwd -P)
RESOLVER="$SELF_DIR/../../specwright-pr/scripts/sw-path.sh"
SELF_BASH=${BASH:-bash}
if command -v cygpath >/dev/null 2>&1; then SELF_DIR=$(cygpath -m "$SELF_DIR"); SELF_BASH=$(cygpath -w "$SELF_BASH"); fi

# The project: the current directory, then up to the first `.git` entry.
dir=$(pwd -P)
proj=$dir
while [ ! -e "$proj/.git" ] && [ "$proj" != / ]; do proj=$(dirname "$proj"); done
[ -e "$proj/.git" ] || proj=$dir

err=$(mktemp)
trap 'rm -f "$err"' EXIT
if ! sw=$("$BASH" "$RESOLVER" --code "$proj" 2>"$err"); then
  "$py" -I -X utf8 -c 'import json, sys; print(json.dumps({"ok": False, "error": "sw_missing", "message": sys.stdin.read().rstrip("\r\n")}, ensure_ascii=False))' <"$err"
  cat "$err" >&2
  rm -f "$err"
  exit 1
fi
rm -f "$err"
exec "$sw" commit --args-stdin < <(printf '%s\0' "$SELF_DIR" "$SELF_BASH" fit-subject "$@")
