#!/usr/bin/env bash
# Which tasks of tasks.md are covered by commits on a change branch. Read-only. A shim (ADR 0028): it finds the project's
# `sw` through sw-path.sh and runs `sw commit --args-stdin task-cover`, handing it this directory, this bash and the whole
# command line as NUL-terminated stdin records. All coverage logic, usage errors included, lives in `sw commit task-cover`.
# Prints ONE JSON document.
#
# Usage: bash task-cover.sh --repo <dir> --range <a>..<b> --tasks <tasks.md> --change <name> [--rev <sha>] [--code <dir>]
#   --code <dir>  the code checkout whose openspec/.specwright/VERSION names the sw to run (a store-backed project's code
#                 checkout); default: the current directory's project. sw accepts it and does nothing else with it.
# Exit: 0 answered (even with uncovered tasks or gaps: the caller decides), 1 stop (JSON "error": range_too_large, or
#       sw_missing when no sw that sw-path.sh accepts is installed: no fallback), 2 usage or bad input (no_python: the shim
#       needs Python 3.8+), 3 git failed.
set -euo pipefail

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
[ -n "$py" ] || { echo '{"ok":false,"error":"no_python","message":"task-cover.sh needs python 3.8+"}'; exit 2; }
SELF_DIR=$(cd "$(dirname "$0")" && pwd -P)
RESOLVER="$SELF_DIR/../../specwright-pr/scripts/sw-path.sh"
SELF_BASH=${BASH:-bash}
if command -v cygpath >/dev/null 2>&1; then SELF_DIR=$(cygpath -m "$SELF_DIR"); SELF_BASH=$(cygpath -w "$SELF_BASH"); fi

# The project: --code when it is a directory, else the current one, then up to the first `.git` entry.
code=
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  case ${args[i]} in
    --) break ;;
    --code) code=${args[i + 1]:-}; i=$((i + 1)) ;;
  esac
done
dir=.
if [ -n "$code" ] && [ -d "$code" ]; then dir=$code; fi
dir=$(cd "$dir" && pwd -P)
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
exec "$sw" commit --args-stdin < <(printf '%s\0' "$SELF_DIR" "$SELF_BASH" task-cover "$@")
