#!/usr/bin/env bash
# Place the sw built from this tree where the resolver looks for it (the body of `mise run install-sw`).
# Usage: bash scripts/install-sw.sh [<built sw> <version>]   (default: cli/build/sw[.exe] and the tree's VERSION)
# The build must pass `sw-path.sh --file <built sw> --version <version>`; only then is it copied to
# <home>/.specwright/bin/<version>/sw[.exe] and renamed over any file there. <home> is SPECWRIGHT_HOME, else the user's home
# (%USERPROFILE% on Windows), as the resolver finds it. Prints the placed path; a failed check exits 1 with the resolver's
# message on stderr and leaves the destination untouched.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd -P)
resolver=$root/skills/specwright-pr/scripts/sw-path.sh
home=${SPECWRIGHT_HOME:-}
ext=
case $(uname -s) in
  MINGW*|MSYS*|CYGWIN*) ext=.exe; [ -n "$home" ] || home=${USERPROFILE:-$HOME} ;;
  *) [ -n "$home" ] || home=$HOME ;;
esac
build=${1:-$root/cli/build/sw$ext}
version=${2:-$(tr -d '\r\n' < "$root/VERSION")}

"$BASH" "$resolver" --file "$build" --version "$version" >/dev/null

dest=$home/.specwright/bin/$version/sw$ext
mkdir -p "$(dirname "$dest")"
part=$dest.$$.part
trap 'rm -f "$part"' EXIT
cp "$build" "$part"
chmod 0755 "$part"
mv -f "$part" "$dest"
"$BASH" "$resolver" --file "$dest" --version "$version"
