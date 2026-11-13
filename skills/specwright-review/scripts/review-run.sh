#!/usr/bin/env bash
# ADR 0028: resolve the project's matching sw, then hand off NUL-terminated
# script-directory, bash and original argument records. No fallback.
# Usage: review-run.sh <select|preflight|run|record|gate|waive|rounds|archive-only> [options]
set -euo pipefail

SW_DIR=$(cd "$(dirname "$0")" && pwd -P)
SW_BASH=${BASH:-bash}
project=$(pwd -P)
original=$project
while [ ! -e "$project/.git" ] && [ "$project" != / ]; do project=$(dirname "$project"); done
[ -e "$project/.git" ] || project=$original
if command -v cygpath >/dev/null 2>&1; then
  SW_DIR=$(cygpath -m "$SW_DIR")
  SW_BASH=$(cygpath -w "$SW_BASH")
fi

# Escape every JSON control byte without starting another interpreter.
json_string() {
  local LC_ALL=C value=$1 result= char ordinal escaped i
  for ((i=0; i<${#value}; i++)); do
    char=${value:i:1}
    case $char in
      '\') result+='\\' ;;
      '"') result+='\"' ;;
      *)
        printf -v ordinal '%d' "'$char"
        if ((ordinal < 32)); then
          printf -v escaped '\\u%04x' "$ordinal"
          result+=$escaped
        else
          result+=$char
        fi
        ;;
    esac
  done
  printf '"%s"' "$result"
}

resolver="$SW_DIR/../../specwright-pr/scripts/sw-path.sh"
if ! sw=$("$BASH" "$resolver" --code "$project" 2>/dev/null); then
  error=$("$BASH" "$resolver" --code "$project" 2>&1 >/dev/null || true)
  [ -n "$error" ] || error='sw missing or mismatched: rerun the install prompt'
  printf '{"ok":false,"error":"sw_missing","message":%s}\n' "$(json_string "$error")"
  exit 1
fi
exec "$sw" review --args-stdin < <(printf '%s\0' "$SW_DIR" "$SW_BASH" "$@")
