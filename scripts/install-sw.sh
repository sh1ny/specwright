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
part=$(dirname "$dest")/.sw-$$.part
notice=$(dirname "$dest")/THIRD_PARTY_NOTICES.txt
notice_part=$(dirname "$dest")/.sw-$$.notice.part
source_notice=$root/cli/THIRD_PARTY_NOTICES.txt
trap 'rm -f "$part" "$notice_part"' EXIT
cp "$build" "$part"
chmod 0755 "$part"
# A matching notice keeps its mtime. Place the notice before replacing the binary.
if ! cmp -s "$source_notice" "$notice"; then
  cp "$source_notice" "$notice_part"
  if [ -d "$notice" ] || ! mv -f "$notice_part" "$notice"; then
    if ! cmp -s "$source_notice" "$notice"; then
      echo "notice_write_failed: THIRD_PARTY_NOTICES.txt for $version cannot be placed" >&2
      exit 1
    fi
  fi
fi
mv -f "$part" "$dest"
"$BASH" "$resolver" --file "$dest" --version "$version"
