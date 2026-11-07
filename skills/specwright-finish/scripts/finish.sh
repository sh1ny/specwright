#!/usr/bin/env bash
# Decisions for finishing a change that were prose before: how to undo an archive of a DEFERRED change (or of one waiting on the user). A shim
# (ADR 0028): it finds the project's `sw` through sw-path.sh and runs `sw finish --args-stdin`, handing it this directory, this bash and the
# whole command line as NUL-terminated stdin records. The plan, its usage errors and its output live in `sw finish undo-archive-plan`. The
# command only READS the repo (rev-parse, status, log, show, diff-tree, ls-tree, ls-files, cat-file). It never checks out, moves, restores or
# commits; the user runs the scripts it prints. Every run prints ONE JSON document.
#
# Usage: bash finish.sh [--dir <planning toplevel>] undo-archive-plan --change <name> --archived-name <archived>
#                       --prefix <P> --main <main> [--branch <branch>] [--type <commit type>] [--code <code toplevel>]
#   undo-archive-plan   the plan to undo the archive of <name> (its directory <P>/changes/archive/<archived>/) and of every
#                       change archived with it. <P> is the openspec root inside the planning repo ("openspec"). --dir is the
#                       planning repo (default: the current directory; store-backed: the store's toplevel). --branch is the
#                       branch that holds a committed archive (default: the current branch). --type is the commit type of the
#                       undo commit's subject `<type>(<name>): undo archive of <member names>`; default: the branch prefix
#                       (`bugfix` -> `fix`, any other prefix as it is, no prefix -> `chore`).
#                       Uncommitted archive (the archive directory is in the working tree and not in HEAD): the members are
#                       every untracked directory under <P>/changes/archive/ whose <P>/changes/<name>/ is tracked at HEAD and
#                       missing from the working tree. Committed archive: A is the NEWEST commit in <main>..<branch> that added
#                       the archive directory's review.md; the members are the archive directories A added. A member's name
#                       is its directory name without the date, unless the change was itself named with a date (that
#                       <P>/changes/<dated name>/ is the one the archive moved). Main specs include nested capabilities
#                       (<P>/specs/<area>/<id>/spec.md).
#                       JSON: ok, mode (uncommitted|committed), archive_commit (A, null when uncommitted), branch, head,
#                       members [{name, archived_name, deferred, waiting_on_user}] (waiting_on_user: the ids of the member's unticked
#                       `[user]` tasks in its archived tasks.md), main_specs {modified[], created[]} (a spec deleted on the
#                       branch after the archive is left deleted, with a warning), amended[] (main specs whose working copy
#                       differs from A's synced content), carried_edits[] (archive-copy files with edits
#                       that are not committed or differ from the change directory), backup_dir
#                       (<git-dir>/specwright-undo/<archived>/), script, after_rerun (for a bulk archive, a script that
#                       archives the members that are neither deferred nor waiting on the user again and merges back amendments to the main specs they sync;
#                       null otherwise), warnings[].
#                       `script` and `after_rerun` are bash texts that begin with `set -euo pipefail`: save each to a file and
#                       run it with `bash <file>`. `script` guards the branch, HEAD and index first (a resume from another
#                       branch checks the tree is clean and the branch tip is the planned head BEFORE the checkout, then
#                       guards again), saves backups, builds ONE undo commit in the index (committed mode only), and fixes
#                       the working tree. Nothing here ever resets, force-pushes or reverts a later commit.
#                       Refusals (exit 1, ok false, error, message): no_archive (nothing to undo; `commits` lists the add
#                       commits when the newest add was reverted), dirty_tree (a resume on another branch with a dirty tree,
#                       or a synced main spec or member archive directory deleted from the working tree; `files` names
#                       them), staged_changes, target_exists (<P>/changes/<name>/ already exists), duplicate_member (two
#                       archive directories restore to one <P>/changes/<name>/), member_missing (a later commit deleted a
#                       member's archive directory; `paths` names them), backup_exists (the backup directory exists),
#                       bad_ref, not_a_repo.
#                       On GitButler (the code repo's backend) --branch is required (exit 2, usage) and the head every guard
#                       checks is the tip of refs/heads/<branch>, resolved now: HEAD is the workspace commit there. On Git and jj
#                       the head is HEAD. The current branch is read through ../../specwright-pr/scripts/vcs.sh `state` (exit 2,
#                       error vcs_script_missing, naming the path when that script is absent). On a jj repo `script` works the
#                       working copy and commits only the touched paths with `jj commit`, then sets the branch's bookmark; it runs no Git write.
#   --code <dir>        the code repo's toplevel; give it with `--dir <store>` so the store's own backend is probed, and so that its
#                       openspec/.specwright/VERSION names the sw to run (a store holds none). A relative --code is read from the planning
#                       repo. Without --code the project is the planning repo's.
# Exit: 0 done, 1 stop (the JSON has "ok": false, "error" and "message"; sw_missing when no sw that sw-path.sh accepts is installed:
#       no fallback), 2 usage or bad input (no_python: the shim needs Python 3.8+; bad_path: a --dir or --code that cannot be converted).
# Needs bash and Python 3.8+ (sw-path.sh), the installed sw, git, and jj for a jj repo.
set -euo pipefail

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
[ -n "$py" ] || { echo '{"ok":false,"error":"no_python","message":"finish.sh needs python 3.8+"}'; exit 2; }
SELF_DIR=$(cd "$(dirname "$0")" && pwd -P)
RESOLVER="$SELF_DIR/../../specwright-pr/scripts/sw-path.sh"
SELF_BASH=${BASH:-bash}
if command -v cygpath >/dev/null 2>&1; then SELF_DIR=$(cygpath -m "$SELF_DIR"); SELF_BASH=$(cygpath -w "$SELF_BASH"); fi

# up_to_git <dir>: the first directory at or above <dir> holding a `.git` entry, else <dir>. No Git command runs.
up_to_git() {
  local d=$1
  while [ ! -e "$d/.git" ] && [ "$d" != / ]; do d=$(dirname "$d"); done
  if [ -e "$d/.git" ]; then printf '%s\n' "$d"; else printf '%s\n' "$1"; fi
}

# The planning repo: a leading --dir, else the current directory, then up to the first `.git` entry.
start=.
if [ "${1:-}" = --dir ] && [ -n "${2:-}" ] && [ -d "$2" ]; then start=$2; fi
start=$(cd "$start" && pwd -P)
plan=$(up_to_git "$start")

# --code: a relative one is read from the planning repo. Each option takes the next argument as its value.
code=
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  case ${args[i]} in
    --code) code=${args[i + 1]:-}; i=$((i + 1)) ;;
    --dir|--change|--archived-name|--prefix|--main|--branch|--type) i=$((i + 1)) ;;
  esac
done
case $code in
  ''|/*|\\*|[A-Za-z]:*) ;;
  *) code=$plan/$code ;;
esac

# The project: --code when it is a directory, else the planning repo, then up to the first `.git` entry.
dir=$plan
if [ -n "$code" ] && [ -d "$code" ]; then dir=$(cd "$code" && pwd -P); fi
proj=$(up_to_git "$dir")

err=$(mktemp)
trap 'rm -f "$err"' EXIT
if ! sw=$("$BASH" "$RESOLVER" --code "$proj" 2>"$err"); then
  "$py" -I -X utf8 -c 'import json, sys; print(json.dumps({"ok": False, "error": "sw_missing", "message": sys.stdin.read().rstrip("\r\n")}, ensure_ascii=False))' <"$err"
  cat "$err" >&2
  rm -f "$err"
  exit 1
fi
rm -f "$err"
exec "$sw" finish --args-stdin < <(printf '%s\0' "$SELF_DIR" "$SELF_BASH" "$@")
