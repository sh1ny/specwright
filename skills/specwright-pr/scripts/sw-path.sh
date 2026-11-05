#!/usr/bin/env bash
# Find the project's `sw` binary and check it before any skill uses it.
#
# Usage: bash sw-path.sh --code <toplevel> [--version <x>] [--file <path>]
#        bash sw-path.sh --file <path> --version <x>
#   --code <toplevel>  the project's code checkout; its openspec/.specwright/VERSION names the version to find
#   --version <x>      the version to find instead of reading VERSION
#   --file <path>      check this file instead of the derived path
#   --code is required unless --file and --version are both given.
# The derived path is <home>/.specwright/bin/<version>/sw (sw.exe on Windows); <home> is SPECWRIGHT_HOME when set, else the
# user's home (%USERPROFILE% on Windows).
#
# Contract: run `<sw> version --json`; when stdout is exactly one JSON object whose `version` equals the expected version and
# whose `interface` equals SW_INTERFACE, print the absolute path of the binary on stdout and exit 0. Every other outcome (no
# VERSION, no file, a non-zero exit, a limit hit, not one JSON object, a missing field, another version or interface) prints
# `sw missing or mismatched: rerun the install prompt` and one detail line (the path and what was found) on stderr, nothing on
# stdout, and exits 1. Usage errors exit 2.
#
# Bounds (C10): the version report runs through the bounded.py beside this script with a 10 s deadline and 1 MiB per stream
# (SPECWRIGHT_NET_DEADLINE and SPECWRIGHT_NET_MAX_BYTES only lower the bounds bounded.py already has).
# No fallback (C6): it never looks in another version's directory and never uses an `sw` found on PATH.
#
# SW_INTERFACE must change together with `interfaceVersion` in cli/lib/src/commands/version.dart (evals/cli/test_sw_interface_pin.py).
set -uo pipefail

SW_INTERFACE=1
STOP="sw missing or mismatched: rerun the install prompt"

usage() { echo "sw-path.sh: $1" >&2; echo "usage: sw-path.sh --code <toplevel> [--version <x>] [--file <path>] | --file <path> --version <x>" >&2; exit 2; }
stop() { printf '%s\n%s\n' "$STOP" "$1" >&2; exit 1; }

code= version= file=
while [ $# -gt 0 ]; do
  case $1 in
    --code|--version|--file)
      [ $# -ge 2 ] || usage "$1 needs a value"
      case $1 in --code) code=$2 ;; --version) version=$2 ;; --file) file=$2 ;; esac
      shift 2 ;;
    *) usage "unknown argument: $1" ;;
  esac
done
[ -n "$code" ] || { [ -n "$file" ] && [ -n "$version" ]; } || usage "--code is required unless --file and --version are given"

win=
case $(uname -s 2>/dev/null) in MINGW*|MSYS*|CYGWIN*) win=1 ;; esac

if [ -z "$version" ]; then
  vfile=$code/openspec/.specwright/VERSION
  [ -f "$vfile" ] || stop "no installed version found: $vfile does not exist"
  IFS= read -r version < "$vfile" || [ -n "$version" ]
  version=$(printf '%s' "$version" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
  [ -n "$version" ] || stop "no installed version found: $vfile is empty"
fi

if [ -z "$file" ]; then
  home=${SPECWRIGHT_HOME:-}
  if [ -z "$home" ]; then
    if [ -n "$win" ]; then home=${USERPROFILE:-$HOME}; else home=$HOME; fi
  fi
  [ -n "$home" ] || stop "no home directory to look in for sw $version"
  file=$home/.specwright/bin/$version/sw
  [ -z "$win" ] || file=$file.exe
fi

[ -f "$file" ] || stop "$file does not exist (expected sw $version)"
# absolute path: the one we print, and the one native Windows python is handed (-m: forward slashes bash accepts)
dir=$(cd "$(dirname "$file")" && pwd -P) || stop "$file cannot be reached"
abs=$dir/$(basename "$file")
SW_DIR=$(cd "$(dirname "$0")" && pwd -P)
if command -v cygpath >/dev/null 2>&1; then abs=$(cygpath -m "$abs"); SW_DIR=$(cygpath -m "$SW_DIR"); fi

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
[ -n "$py" ] || { echo "sw-path.sh: no_python: needs python 3.8+ for its bounded check" >&2; exit 2; }

# The caps, kept lower when the caller set a lower SPECWRIGHT_NET_DEADLINE or SPECWRIGHT_NET_MAX_BYTES (a bad value is ignored).
limits=$("$py" -I -c '
import os
def low(name, cap, cast):
    try:
        v = cast(os.environ.get(name, ""))
    except ValueError:
        return cap
    return v if 0 <= v < cap else cap
print(low("SPECWRIGHT_NET_DEADLINE", 10, float), low("SPECWRIGHT_NET_MAX_BYTES", 1048576, int))')
read -r deadline max_bytes <<< "$limits"
out=$(SPECWRIGHT_NET_DEADLINE=${deadline:-10} SPECWRIGHT_NET_MAX_BYTES=${max_bytes:-1048576} "$py" -I "$SW_DIR/bounded.py" -- "$abs" version --json 2>/dev/null)
status=$?
case $status in
  0) ;;
  124) stop "$abs: sw version --json hit the 10 s deadline" ;;
  125) stop "$abs: sw version --json printed more than 1 MiB" ;;
  *) stop "$abs: sw version --json could not run or exited $status" ;;
esac

# the checker reads the report on stdin; it prints a found-description and exits 1 unless the report matches
found=$(printf '%s' "$out" | "$py" -I -c '
import json, sys
want_v, want_i = sys.argv[1], int(sys.argv[2])
try:
    obj = json.loads(sys.stdin.read())
except ValueError:
    print("the report is not one JSON object"); sys.exit(1)
if not isinstance(obj, dict):
    print("the report is not one JSON object"); sys.exit(1)
v, i = obj.get("version"), obj.get("interface")
if not isinstance(v, str) or not isinstance(i, int) or isinstance(i, bool):
    print("the report lacks a string version or an integer interface"); sys.exit(1)
bad = []
if v != want_v:
    bad.append("version %s, expected %s" % (v, want_v))
if i != want_i:
    bad.append("interface %d, expected interface %d" % (i, want_i))
if bad:
    print("; ".join(bad)); sys.exit(1)
' "$version" "$SW_INTERFACE") || stop "$abs reports: $found"

printf '%s\n' "$abs"
