#!/usr/bin/env bash
# as.sh <login> <command> [args...] | as.sh --resolve
# The identity fence for a network command. A shim (ADR 0028, ADR 0029): it finds the project's `sw` through
# sw-path.sh and runs `sw as --args-file <file>`, handing it this directory, this bash and the whole command line as
# NUL-terminated records in a private file. `sw as` reads the file and deletes it first, so the fenced command keeps
# this script's stdin. All parsing, the checks and the command's own run happen in `sw as`, which keeps this script's
# messages and exit statuses (3 for a refusal or a limit, the command's own status otherwise).
# No `sw` that sw-path.sh accepts: one `sw_missing` JSON document on stdout, exit 1; no fallback.
set -euo pipefail

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
[ -n "$py" ] || { echo "as.sh: no_python: needs python 3.8+ for its bounded gh calls" >&2; exit 2; }
AS_DIR=$(cd "$(dirname "$0")" && pwd -P)
AS_BASH=${BASH:-bash}
if command -v cygpath >/dev/null 2>&1; then AS_DIR=$(cygpath -m "$AS_DIR"); AS_BASH=$(cygpath -w "$AS_BASH"); fi

# The project: the current directory, then up to the first `.git` entry.
dir=$(pwd -P)
proj=$dir
while [ ! -e "$proj/.git" ] && [ "$proj" != / ]; do proj=$(dirname "$proj"); done
[ -e "$proj/.git" ] || proj=$dir

# No mktemp before sw runs (the evals fake it): a resolver that fails is run once more to capture its stderr.
if ! sw=$("$BASH" "$AS_DIR/sw-path.sh" --code "$proj" 2>/dev/null); then
  err=$("$BASH" "$AS_DIR/sw-path.sh" --code "$proj" 2>&1 >/dev/null || true)
  printf '%s' "$err" | "$py" -I -X utf8 -c 'import json, sys; print(json.dumps({"ok": False, "error": "sw_missing", "message": sys.stdin.read().rstrip("\r\n")}, ensure_ascii=False))'
  printf '%s\n' "$err" >&2
  exit 1
fi

# The handoff: a private file (mktemp makes it mode 0600), not stdin: the fenced command reads the caller's stdin.
hand=$(mktemp)
trap 'rm -f "$hand"' EXIT
printf '%s\0' "$AS_DIR" "$AS_BASH" "$@" >"$hand"
if command -v cygpath >/dev/null 2>&1; then hand_arg=$(cygpath -m "$hand"); else hand_arg=$hand; fi
exec "$sw" as --args-file "$hand_arg"
