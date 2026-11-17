#!/usr/bin/env bash
# ADR 0028 shim: hand every argument to the DOWNLOAD's own sw, `sw update <arguments> --download <this tree>`. The update
# itself (plan, stage, swap, note-config, finish, recover, pack-check, pack-verify, pack-docs, sw-install) runs in sw, which
# the install prompt calls directly; this file stays for an older prompt or a person who still runs
# `bash <download>/scripts/update.sh [options] <subcommand>` from the downloaded copy.
#
# It reads <download>/VERSION (the download is the tree this script sits in), finds sw of exactly that version with the
# sw-path.sh beside it (skills/specwright-pr/scripts/sw-path.sh: <home>/.specwright/bin/<version>/sw, checked with
# `version --json`), and runs it. It adds `--download <its tree>` unless the arguments name one. No fallback: with no matching
# sw it prints {"ok":false,"error":"sw_missing","message":...} and exits 1, before anything is written.
#
# The update.sh shim stays only until native-cli-retire-scripts, which removes it with the other shims.
set -uo pipefail

SW_DIR=$(cd "$(dirname "$0")" && pwd -P)
DOWNLOAD=$(cd "$SW_DIR/.." && pwd -P)
if command -v cygpath >/dev/null 2>&1; then
  DOWNLOAD=$(cygpath -m "$DOWNLOAD")
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
        # Bash 3 can report UTF-8 bytes as negative signed ordinals.
        if ((ordinal >= 0 && ordinal < 32)); then
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

missing() {
  printf '{"ok":false,"error":"sw_missing","message":%s}\n' "$(json_string "$1")"
  exit 1
}

version=
if [ -f "$SW_DIR/../VERSION" ]; then IFS= read -r version < "$SW_DIR/../VERSION" || [ -n "$version" ] || true; fi
version=$(printf '%s' "$version" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
[ -n "$version" ] || missing "sw missing or mismatched: rerun the install prompt
no download version found: $DOWNLOAD/VERSION is missing or empty"

resolver="$SW_DIR/../skills/specwright-pr/scripts/sw-path.sh"
[ -f "$resolver" ] || missing "sw missing or mismatched: rerun the install prompt
$resolver does not exist"
if ! sw=$("${BASH:-bash}" "$resolver" --version "$version" --code "$DOWNLOAD" 2>/dev/null); then
  error=$("${BASH:-bash}" "$resolver" --version "$version" --code "$DOWNLOAD" 2>&1 >/dev/null || true)
  [ -n "$error" ] || error='sw missing or mismatched: rerun the install prompt'
  missing "$error"
fi

for arg in "$@"; do
  case $arg in --download|--download=*) exec "$sw" update "$@" ;; esac
done
exec "$sw" update "$@" --download "$DOWNLOAD"
