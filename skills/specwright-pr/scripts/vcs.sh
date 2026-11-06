#!/usr/bin/env bash
# Single branch-read and write boundary for Git, jj and GitButler repositories. A shim (ADR 0028): it finds the project's `sw`
# through sw-path.sh and runs `sw vcs --args-stdin`, handing it this directory, this bash and the whole command line as
# NUL-terminated stdin records. All parsing and validation, usage errors included, happens in `sw vcs`.
# No `sw` that sw-path.sh accepts: one `sw_missing` JSON document on stdout, exit 1; no fallback.
set -euo pipefail

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
[ -n "$py" ] || { echo '{"ok":false,"error":"no_python","message":"vcs.sh needs python 3.8+"}'; exit 2; }
VCS_DIR=$(cd "$(dirname "$0")" && pwd -P)
VCS_BASH=${BASH:-bash}
if command -v cygpath >/dev/null 2>&1; then VCS_DIR=$(cygpath -m "$VCS_DIR"); VCS_BASH=$(cygpath -w "$VCS_BASH"); fi

# The project: the first existing directory among --code, --repo and the current one, then up to the first `.git` entry.
code= repo=
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  case ${args[i]} in
    --) break ;;
    --code) code=${args[i + 1]:-}; i=$((i + 1)) ;;
    --repo) repo=${args[i + 1]:-}; i=$((i + 1)) ;;
  esac
done
dir=.
if [ -n "$code" ] && [ -d "$code" ]; then dir=$code; elif [ -n "$repo" ] && [ -d "$repo" ]; then dir=$repo; fi
dir=$(cd "$dir" && pwd -P)
proj=$dir
while [ ! -e "$proj/.git" ] && [ "$proj" != / ]; do proj=$(dirname "$proj"); done
[ -e "$proj/.git" ] || proj=$dir

err=$(mktemp)
trap 'rm -f "$err"' EXIT
if ! sw=$("$BASH" "$VCS_DIR/sw-path.sh" --code "$proj" 2>"$err"); then
  "$py" -I -X utf8 -c 'import json, sys; print(json.dumps({"ok": False, "error": "sw_missing", "message": sys.stdin.read().rstrip("\r\n")}, ensure_ascii=False))' <"$err"
  cat "$err" >&2
  rm -f "$err"
  exit 1
fi
rm -f "$err"
exec "$sw" vcs --args-stdin < <(printf '%s\0' "$VCS_DIR" "$VCS_BASH" "$@")
