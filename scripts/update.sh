#!/usr/bin/env bash
# Stage, swap and finish a Specwright update. Run it from the DOWNLOADED copy of the new version, never from the
# project: `bash <download>/scripts/update.sh [options] <subcommand>`. Every subcommand prints ONE JSON document, like
# skills/specwright-release/scripts/release.sh. The README install prompt asks the questions (targets, settings,
# schema choice), merges config.yaml and specwright.yaml (Steps 5-6), runs the Step 7 checks and writes the stamp
# `openspec/.specwright/VERSION`; this script does the file work of Step 4 so that an interrupted update can be
# recovered (design D1-D3 of the safe-update-lifecycle change).
#
# Usage: bash <download>/scripts/update.sh [options] <subcommand>
# Options (all before or after the subcommand; paths may be absolute or relative to the current directory):
#   --code DIR        the code checkout (default: the current directory). Holds openspec/.specwright/ (VERSION, the
#                     journal update.json and the lock update.lock)
#   --root DIR        the planning root whose openspec/schemas/specwright/ is replaced (default: --code; a store's
#                     root for a project that uses a store)
#   --skills DIR      a chosen skills directory (e.g. <code>/.claude/skills); repeat for each one. Only the
#                     specwright-* directories in it are touched
#   --agents KIND=DIR a chosen agents directory and the agent kind of the files it gets: claude (agents/claude/*.md
#                     from the download) or omp (agents/omp/*.md); repeat for each one. Only specwright-*.md files
#   --download DIR    the download tree (default: the directory above this script). Its VERSION is the target version
#   --ref REF         the ref the download came from (e.g. v0.6.0 or main); recorded in the journal and the reports
# The installed version is read from <code>/openspec/.specwright/VERSION (missing = a fresh install).
#
# Subcommands:
#   plan     read only. Prints interface (1), from, to, ref, kind (fresh | patch | workflow | reinstall | downgrade),
#            role (none: no store handling yet), inflight_checked, inflight, targets (every directory or file that stage will replace), orphans
#            (installed specwright-* names with no downloaded counterpart; never touched), journal (a pending
#            update.json: {from, to, phase, format} or null), refusals and warnings. Writes nothing outside
#            <download>/.update-scratch/ (removed before plan returns), with one exception: when a journal is pending, plan
#            first runs recover (below) and adds recovered: {action, message, from, to} to its document; journal then
#            shows what is left. A journal that is not format 1 is not recovered (plan refuses it as unreadable).
#            A refusal is exit 1, error "refused".
#            Changes in flight (design D4), on a workflow update only (no installed VERSION, or a different major
#            or minor; a patch update, a reinstall and a same-minor downgrade skip it: inflight_checked false):
#              - collected: every change directory in <root>/openspec/changes/ other than archive/, and every local
#                branch feat|bugfix|refactor|docs|chore/<name> of the planning repo (the git repo of --root) whose
#                tree holds <P>/changes/<name>/ while the planning main (origin/main when present, else main; then
#                master) has no archive named <name> or YYYY-MM-DD-<name> exactly. A branch's change is read with
#                git archive, so it validates with that branch's specs. The working tree wins over a branch.
#              - a remote-tracking origin/<prefix>/<name> that holds an unarchived change and has no local branch is
#                a warning {code in_flight_elsewhere, name, ref, message}: not validated, never a refusal, no fetch.
#              - each change on the specwright schema gets a scratch root in <download>/.update-scratch/ (the new
#                schema, `schema: specwright`, the main specs, the change) and three checks run there with cwd = the
#                scratch root: `openspec schema validate specwright`, `openspec validate <name>` and
#                `openspec status --change <name> --json` (no status[] error; every artifact whose files exist has
#                each required artifact done or skipped). A change whose .openspec.yaml does not name specwright is
#                listed with status "not on specwright" and not checked.
#              - inflight lists {name, source (working tree | the branch), status, validated_against}; a failing
#                change is a refusal {code change_invalid, change, ref, message} naming the change and the first error.
#   stage    copies every new skill directory, agent file and the schema into a staging directory beside its target
#            (D2): <parent>/.specwright-update-<basename>/new/. Agent files carry the user's `model:` line over.
#            Writes the journal (format 1) first, verifies the staged copy against a SHA-256 manifest and stops with
#            error verification_failed (naming each file, staging and journal removed) when a file differs. Installed
#            files are untouched. Refuses while a journal is pending (run recover first). Runs plan first (so a
#            failing change refuses it) and records the collected set and results in the journal (inflight).
#   swap     re-verifies the staged copy and, on a workflow update, collects and validates the changes in flight
#            again against the staged schema; any difference from the journal's record (a new, removed or now
#            failing change) stops it before the first rename with error inflight_changed, naming the changes
#            (differences[]), and changes no installed file. Then replaces each target with two renames: target -> old/<name>, then
#            new/<name> -> target. The journal records each step before it runs. Prints store_written (false:
#            this script never writes a store) and a restart notice. Rerunning after an interruption goes on from
#            the journal and the disk.
#   finish   once VERSION reads the target version (the prompt's Step 7 stamp): removes old/, the staging directories
#            and the journal. Rerunning it is safe.
#   recover  decides from the journal and the disk (design D3), and prints action, message, from, to:
#              - swap not started (no target old-moved or swapped)  -> discarded: staging and journal removed;
#                message `discarded unfinished update to <to>`
#              - phase swapped and VERSION already reads <to>        -> finished: staging and journal removed
#              - every staged file (in new/ or already swapped in) matches the manifest -> resumed: the rest of the
#                swap runs; message `resumed update to <to>`. The journal stays (phase swapped) for the prompt's
#                Step 7 stamp and finish, unless the update is not the download's own version (the download's VERSION
#                differs from <to>) or VERSION already reads <to>: then VERSION is written as <to> and the update is
#                finished, so that the download's own update can start from it
#              - otherwise -> rolled back: each old/ is moved back, each swapped-in new copy is removed, staging and
#                journal removed, VERSION untouched; message `rolled back to <from>`
#            Also removes a leftover update.json.tmp. With no journal it reports action none. plan calls it first.
# Journal (openspec/.specwright/update.json, written to update.json.tmp and renamed): format 1, from, to, ref, kind,
# role, code, root, phase (staging | staged | swapping | swapped), groups, targets (state pending | staged |
# old-moved | swapped), manifest ({group, path, sha256} for every staged file).
# Lock: openspec/.specwright/update.lock (a directory made with mkdir) holds `pid:` and `host:`. A lock held by a dead pid
# on this host is replaced and reported as lock_replaced; any other holder stops the run (error locked).
# File operations use the external mv, cp and rm only (never builtins or Python), so the evals can put counting shims
# first on PATH and see every step (design: Testing the interruption criterion).
# Exit: 0 done, 1 stop (the JSON has "ok": false, "error" and "message"), 2 usage.
# Needs bash, mkdir and Python 3.8+ (hostname when $HOSTNAME is unset).
set -euo pipefail

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
[ -n "$py" ] || { echo '{"ok":false,"error":"no_python","message":"update.sh needs python 3.8+"}'; exit 2; }


# --- paths ------------------------------------------------------------------------------------------------------

native() {  # native VAR PATH: VAR = PATH as an absolute path both bash and a native Python read (C:/x on Windows)
  local p=$2
  case "$p" in
    [A-Za-z]:*) p=${p//\\//} ;;  # already a drive path: no process needed
    *)
      case "$p" in /*) ;; *) p="$PWD/$p" ;; esac
      if command -v cygpath >/dev/null 2>&1; then p=$(cygpath -ma -- "$p"); fi ;;
  esac
  while [ "${#p}" -gt 1 ] && [ "${p%/}" != "$p" ]; do p=${p%/}; done
  printf -v "$1" '%s' "$p"
}

# The Python helper is the text between the "#---PYSRC---" and PYSRC_EOF lines at the end of this file. A short -c loader reads it from the
# script itself: passing 13 KB of source as an argument costs about a second per call under Git Bash on Windows.
PYLOAD='import sys;f=sys.argv[1];s=open(f,encoding="utf-8").read().split("\n#---PYSRC---\n",1)[1].split("\nPYSRC_EOF\n",1)[0];sys.argv=sys.argv[1:];exec(compile(s,f,"exec"),{"__name__":"__main__"})'
native SELF "${BASH_SOURCE[0]}"
pyx() { "$py" -I -X utf8 -c "$PYLOAD" "$SELF" "$@"; }

code="" root="" download="" ref="" sub=""
skills=() agents=()
usage() { echo "{\"ok\":false,\"error\":\"usage\",\"message\":\"$1\"}"; exit 2; }
while [ $# -gt 0 ]; do
  case "$1" in
    --code|--root|--download|--ref|--skills|--agents)
      [ $# -ge 2 ] || usage "$1 needs a value"
      case "$1" in
        --code) native code "$2" ;;
        --root) native root "$2" ;;
        --download) native download "$2" ;;
        --ref) ref=$2 ;;
        --skills) native tmp "$2"; skills+=("$tmp") ;;
        --agents)
          case "$2" in *=*) ;; *) usage "--agents needs KIND=DIR" ;; esac
          native tmp "${2#*=}"; agents+=("${2%%=*}=$tmp") ;;
      esac
      shift 2 ;;
    -*) usage "unknown option $1" ;;
    *) [ -z "$sub" ] || usage "one subcommand only"; sub=$1; shift ;;
  esac
done
[ -n "$sub" ] || usage "a subcommand is required: plan, stage, swap, finish or recover"
[ -n "$code" ] || native code "$PWD"
[ -n "$root" ] || root=$code
if [ -z "$download" ]; then
  self=${BASH_SOURCE[0]}
  case "$self" in */*) self=${self%/*} ;; *) self=. ;; esac
  case "$self" in
    */scripts) native download "${self%/scripts}" ;;
    *) native download "$self/.." ;;
  esac
fi

PYARGS=(--code "$code" --root "$root" --download "$download")
[ -z "$ref" ] || PYARGS+=(--ref "$ref")
for s in ${skills[@]+"${skills[@]}"}; do PYARGS+=(--skills "$s"); done
for a in ${agents[@]+"${agents[@]}"}; do PYARGS+=(--agents "$a"); done

state_dir="$code/openspec/.specwright"
journal="$state_dir/update.json"
jtmp="$state_dir/update.json.tmp"
lock="$state_dir/update.lock"

die() {  # die CODE MESSAGE [EXTRA_JSON]: one JSON error document, exit 1
  local extra=${3:-}
  pyx err "${PYARGS[@]}" --error "$1" --message "$2" ${extra:+--extra "$extra"}
  exit 1
}

# --- lock -------------------------------------------------------------------------------------------------------

LOCK_HELD=0
LOCK_EXTRA='{}'
release_lock() { if [ "$LOCK_HELD" = 1 ]; then LOCK_HELD=0; rm -rf "$lock"; fi; }

acquire_lock() {
  local host=${HOSTNAME:-$(hostname)} owner_pid owner_host l tries=0
  mkdir -p "$state_dir"
  while ! mkdir "$lock" 2>/dev/null; do
    owner_pid="" owner_host=""
    if [ -f "$lock/owner" ]; then
      while IFS= read -r l || [ -n "$l" ]; do
        case "$l" in
          "pid: "*) owner_pid=${l#pid: } ;;
          "host: "*) owner_host=${l#host: } ;;
        esac
      done < "$lock/owner"
    fi
    tries=$((tries + 1))
    if [ "$tries" -le 3 ] && [ "$owner_host" = "$host" ] && [[ "$owner_pid" =~ ^[0-9]+$ ]] && ! kill -0 "$owner_pid" 2>/dev/null; then
      LOCK_EXTRA="{\"lock_replaced\": {\"pid\": $owner_pid, \"host\": \"$owner_host\"}}"
      rm -rf "$lock"
      continue
    fi
    die locked "another update holds $lock (pid ${owner_pid:-unknown} on ${owner_host:-unknown host}); wait for it to finish"
  done
  LOCK_HELD=1
  printf 'pid: %s\nhost: %s\n' "$$" "$host" > "$lock/owner"
}
trap release_lock EXIT

# --- journal helpers ----------------------------------------------------------------------------------------------
# The journal is one JSON document with one group, target and manifest entry per line (written by `journal-new`). The
# shell keeps its lines in JL, changes a state in memory and rewrites the file atomically: temp file, then the external
# mv. No process but mv runs per journal write, which keeps a swap fast on Windows.

JL=()
jload() { mapfile -t JL < "$journal"; }
jflush() { printf '%s\n' "${JL[@]}" > "$jtmp"; mv -f "$jtmp" "$journal"; }

jfield() {  # jfield KEY: the top-level string or number value of KEY ("" when missing)
  local l
  for l in "${JL[@]}"; do
    if [[ "$l" =~ ^\ \ \"$1\":\ \"?([^\",]*)\"?,?$ ]]; then printf '%s' "${BASH_REMATCH[1]}"; return 0; fi
  done
}

jwrite_phase() {  # jwrite_phase PHASE: record the phase, atomically
  local i
  for i in "${!JL[@]}"; do
    if [[ "${JL[i]}" == '  "phase": "'*'",' ]]; then JL[i]="  \"phase\": \"$1\","; fi
  done
  jflush
}

jwrite_target() {  # jwrite_target GID NAME STATE
  local i head="    {\"gid\": \"$1\", \"name\": \"$2\", "
  for i in "${!JL[@]}"; do
    if [[ "${JL[i]}" == "$head"* && "${JL[i]}" =~ ^(.*\"state\":\ \")[a-z-]+(\"\}.*)$ ]]; then
      JL[i]="${BASH_REMATCH[1]}$3${BASH_REMATCH[2]}"
    fi
  done
  jflush
}

jwrite_all_targets() {  # jwrite_all_targets FROM TO
  local i
  for i in "${!JL[@]}"; do
    if [[ "${JL[i]}" == '    {"gid": '* && "${JL[i]}" =~ ^(.*\"state\":\ \")$1(\"\}.*)$ ]]; then
      JL[i]="${BASH_REMATCH[1]}$2${BASH_REMATCH[2]}"
    fi
  done
  jflush
}

remove_staging() {  # remove every staging directory of the journal (or of the plan when there is no journal)
  local d
  while IFS= read -r d; do
    [ -z "$d" ] || [ ! -e "$d" ] || rm -rf "$d"
  done < <(pyx staging "${PYARGS[@]}")
}

# --- recover ----------------------------------------------------------------------------------------------------
# Needs the lock. Every step checks the disk before it acts, and the journal is removed last, so a rerun after a kill
# during recover decides again from what is left.

REC_ACTION="" REC_MSG="" REC_FROM="" REC_TO=""

recover_cleanup() {  # staging first, journal last
  remove_staging
  rm -f "$jtmp"
  rm -f "$journal"
}

recover_after() {  # runs after every outcome; a store target and its gate lock are released here (group 5)
  :
}

recover_rollback() {
  local l gid name type dir staging state inst new old tgt
  load_targets
  for l in "${TARGETS[@]}"; do
    IFS='|' read -r gid name type dir staging state inst <<< "$l"
    new="$staging/new/$name" old="$staging/old/$name" tgt="$dir/$name"
    if [ -e "$old" ]; then  # the old copy was moved aside: put it back, dropping a new copy that was swapped in
      if [ -e "$tgt" ]; then rm -rf "$tgt" || die rename_failed "could not remove $tgt"; fi
      mkdir -p "$dir"
      mv "$old" "$tgt" || die rename_failed "could not move $old back to $tgt (a directory held open by another program?)"
    elif [ "$inst" = false ] && [ ! -e "$new" ] && [ -e "$tgt" ]; then  # first install: the swapped-in copy goes
      rm -rf "$tgt" || die rename_failed "could not remove $tgt"
    fi
  done
  recover_cleanup
}

recover_core() {
  REC_ACTION=none REC_MSG="no unfinished update" REC_FROM="" REC_TO=""
  if [ ! -f "$journal" ]; then rm -f "$jtmp"; return 0; fi
  jload
  [ "$(jfield format)" = 1 ] || die journal_unreadable "update.json has format '$(jfield format)', not 1"
  local phase to from now="" dlv="" l started=0 vrc=0
  phase=$(jfield phase)
  case "$phase" in staging|staged|swapping|swapped) ;; *) die journal_unreadable "update.json has phase '$phase'" ;; esac
  to=$(jfield to) from=$(jfield from)
  [ "$from" != null ] || from=""
  [ -n "$to" ] || die journal_unreadable "update.json has no target version"
  REC_FROM=$from REC_TO=$to
  [ ! -f "$state_dir/VERSION" ] || read -r now < "$state_dir/VERSION" || true
  now=${now//$'\r'/}
  for l in "${JL[@]}"; do
    case "$l" in '    {"gid": '*'"state": "old-moved"}'*|'    {"gid": '*'"state": "swapped"}'*) started=1; break ;; esac
  done
  if [ "$phase" = swapped ] && [ "$now" = "$to" ]; then
    recover_cleanup
    REC_ACTION=finished REC_MSG="finished update to $to"
  elif [ "$started" = 0 ]; then
    recover_cleanup
    REC_ACTION=discarded REC_MSG="discarded unfinished update to $to"
  else
    pyx verify-swap "${PYARGS[@]}" >/dev/null || vrc=$?
    if [ "$vrc" = 0 ]; then
      swap_loop
      [ ! -f "$download/VERSION" ] || read -r dlv < "$download/VERSION" || true
      dlv=${dlv//$'\r'/}
      if [ "$now" = "$to" ] || [ "$dlv" != "$to" ]; then  # nobody will stamp this update: do it here, then finish
        [ "$now" = "$to" ] || printf '%s\n' "$to" > "$state_dir/VERSION"
        recover_cleanup
      fi
      REC_ACTION=resumed REC_MSG="resumed update to $to"
    else
      recover_rollback
      REC_ACTION=rolled-back REC_MSG="rolled back to ${from:-the state before the first install}"
    fi
  fi
  recover_after
}

q() { if [ -n "$1" ]; then printf '"%s"' "$1"; else printf null; fi; }  # a JSON string or null

rec_json() {  # the recovered object: action, message, from, to
  printf '{"action": "%s", "message": "%s", "from": %s, "to": %s}' "$REC_ACTION" "$REC_MSG" "$(q "$REC_FROM")" "$(q "$REC_TO")"
}

lock_extra_members() {  # the members of LOCK_EXTRA, for splicing into another object ("" when none)
  local x=${LOCK_EXTRA#\{}
  printf '%s' "${x%\}}"
}

do_recover() {
  acquire_lock
  recover_core
  local now="" lx
  [ ! -f "$state_dir/VERSION" ] || read -r now < "$state_dir/VERSION" || true
  now=${now//$'\r'/}
  lx=$(lock_extra_members)
  printf '{"ok": true, "interface": 1, "subcommand": "recover", "installed": %s, "action": "%s", "message": "%s", "from": %s, "to": %s%s}\n' \
    "$(q "$now")" "$REC_ACTION" "$REC_MSG" "$(q "$REC_FROM")" "$(q "$REC_TO")" "${lx:+, $lx}"
}

# --- subcommands ------------------------------------------------------------------------------------------------

do_plan() {
  if [ -f "$journal" ]; then
    jload
    local ph lx
    ph=$(jfield phase)
    if [ "$(jfield format)" = 1 ]; then
      case "$ph" in
        staging|staged|swapping|swapped)
          acquire_lock
          recover_core
          release_lock
          lx=$(lock_extra_members)
          pyx plan "${PYARGS[@]}" --extra "{\"recovered\": $(rec_json)${lx:+, $lx}}"
          return 0 ;;
      esac
    fi
  fi
  pyx plan "${PYARGS[@]}"
}

do_stage() {
  local out rc=0
  out=$(pyx plan "${PYARGS[@]}") || rc=$?
  if [ "$rc" != 0 ]; then printf '%s\n' "$out"; exit "$rc"; fi  # a refusal writes nothing, not even the lock
  acquire_lock
  if [ -f "$journal" ]; then
    jload
    die journal_pending "an unfinished update${JL:+ to $(jfield to)} is recorded in $journal; run recover first"
  fi
  [ ! -e "$jtmp" ] || rm -f "$jtmp"
  [ ! -e "$download/.update-scratch" ] || rm -rf "$download/.update-scratch"
  remove_staging
  pyx journal-new "${PYARGS[@]}" --plan "$out" "$jtmp"
  mv -f "$jtmp" "$journal"
  local op a b c
  while IFS=$'\t' read -r op a b c; do
    case "$op" in
      mkdir) mkdir -p "$a" ;;
      cp) if [ "$a" = "-R" ]; then cp -R "$b" "$c/"; else cp "$b" "$c/"; fi ;;
    esac
  done < <(pyx ops "${PYARGS[@]}")
  pyx carry "${PYARGS[@]}"
  local vout vrc=0
  vout=$(pyx verify "${PYARGS[@]}") || vrc=$?
  if [ "$vrc" != 0 ]; then
    # the verdict was composed while the journal still said "staging": installed files were never touched
    remove_staging
    rm -f "$journal"
    printf '%s\n' "$vout"
    exit 1
  fi
  jload
  jwrite_all_targets pending staged
  jwrite_phase staged
  pyx report "${PYARGS[@]}" stage --extra "$LOCK_EXTRA"
}

TARGETS=()
load_targets() {  # fill TARGETS with "gid|name|type|dir|staging|state|installed" from the journal lines in JL
  local l
  local re='^    \{"gid": "([^"]*)", "name": "([^"]*)", "type": "([^"]*)", "dir": "([^"]*)", "staging": "([^"]*)", "installed": (true|false), "state": "([a-z-]+)"\}'
  TARGETS=()
  for l in "${JL[@]}"; do
    if [[ "$l" == '    {"gid": '* ]]; then
      [[ "$l" =~ $re ]] || die journal_unreadable "update.json has a target line this script cannot read"
      TARGETS+=("${BASH_REMATCH[1]}|${BASH_REMATCH[2]}|${BASH_REMATCH[3]}|${BASH_REMATCH[4]}|${BASH_REMATCH[5]}|${BASH_REMATCH[7]}|${BASH_REMATCH[6]}")
    fi
  done
}

swap_loop() {  # the renames of every target, from the journal in JL and the disk; ends with phase swapped
  local l gid name type dir staging state inst new old tgt
  local made=" "  # directories already created in this run
  load_targets
  for l in "${TARGETS[@]}"; do
    IFS='|' read -r gid name type dir staging state inst <<< "$l"
    new="$staging/new/$name" old="$staging/old/$name" tgt="$dir/$name"
    if [ ! -e "$new" ]; then  # already swapped (a rerun after an interruption)
      [ -e "$tgt" ] || die inconsistent "$name: neither $new nor $tgt exists"
      [ "$state" = swapped ] || jwrite_target "$gid" "$name" swapped
      continue
    fi
    if [ -e "$tgt" ]; then
      [ ! -e "$old" ] || die inconsistent "$name: $tgt, $new and $old all exist"
      jwrite_target "$gid" "$name" old-moved
      case "$made" in *" $staging/old "*) ;; *) mkdir -p "$staging/old"; made="$made$staging/old " ;; esac
      mv "$tgt" "$old" || die rename_failed "could not move $tgt to $old (a directory held open by another program?)"
    fi
    jwrite_target "$gid" "$name" swapped
    case "$made" in *" $dir "*) ;; *) mkdir -p "$dir"; made="$made$dir " ;; esac
    mv "$new" "$tgt" || die rename_failed "could not move $new to $tgt (a directory held open by another program?)"
    { [ -e "$tgt" ] && [ ! -e "$new" ]; } || die inconsistent "$name: the rename to $tgt did not take effect"
  done
  jwrite_phase swapped
}

do_swap() {
  acquire_lock
  [ -f "$journal" ] || die no_journal "no staged update is recorded in $journal; run stage first"
  jload
  [ "$(jfield format)" = 1 ] || die journal_unreadable "update.json has format '$(jfield format)', not 1"
  local phase
  phase=$(jfield phase)
  case "$phase" in
    staged|swapping|swapped) ;;
    *) die not_staged "the recorded update is in phase '$phase', not staged; run recover first" ;;
  esac
  if [ "$phase" = staged ]; then
    local vout vrc=0
    vout=$(pyx verify "${PYARGS[@]}") || vrc=$?
    if [ "$vrc" != 0 ]; then printf '%s\n' "$vout"; exit 1; fi
    vrc=0  # a workflow update: the changes in flight must still be the ones the plan validated (before any rename)
    vout=$(pyx swap-check "${PYARGS[@]}") || vrc=$?
    if [ "$vrc" != 0 ]; then printf '%s\n' "$vout"; exit 1; fi
  fi
  [ "$phase" = swapped ] || jwrite_phase swapping
  swap_loop
  pyx report "${PYARGS[@]}" swap --extra "$LOCK_EXTRA"
}

do_finish() {
  acquire_lock
  if [ ! -f "$journal" ]; then
    printf '{"ok": true, "interface": 1, "subcommand": "finish", "state": "done", "finished": false, "message": "no update is in progress"}\n'
    return 0
  fi
  jload
  local to now="" phase rep
  to=$(jfield to)
  phase=$(jfield phase)
  [ ! -f "$state_dir/VERSION" ] || read -r now < "$state_dir/VERSION" || true
  now=${now//$'\r'/}
  [ "$now" = "$to" ] || die not_stamped "VERSION reads '${now:-missing}', not $to; finish runs after the stamp"
  [ "$phase" = swapped ] || die not_swapped "the recorded update is in phase '$phase', not swapped; run recover first"
  rep=$(pyx report "${PYARGS[@]}" finish --extra '{"state": "done", "finished": true}')
  remove_staging
  rm -f "$jtmp"
  rm -f "$journal"
  printf '%s\n' "$rep"
}

case "$sub" in
  plan) do_plan ;;
  stage) do_stage ;;
  swap) do_swap ;;
  finish) do_finish ;;
  recover) do_recover ;;
  *) usage "unknown subcommand $sub (plan, stage, swap, finish, recover)" ;;
esac
exit "$?"

: <<'PYSRC_EOF'
#---PYSRC---
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

sys.stdout.reconfigure(newline="\n")  # no CRLF on Windows: the shell reads these lines
INTERFACE = 1
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
STATE_REL = "openspec/.specwright"
VALUE_OPTS = ("code", "root", "download", "ref", "error", "message", "extra", "plan")
PREFIXES = ("feat", "bugfix", "refactor", "docs", "chore")
SCRATCH = ".update-scratch"


def parse(argv):
    o, pos, i = {"skills": [], "agents": []}, [], 0
    while i < len(argv):
        a = argv[i]
        if a in ("--skills", "--agents"):
            o[a[2:]].append(argv[i + 1])
            i += 2
        elif a.startswith("--") and a[2:] in VALUE_OPTS:
            o[a[2:]] = argv[i + 1]
            i += 2
        else:
            pos.append(a)
            i += 1
    o["code"] = (o.get("code") or os.getcwd()).replace("\\", "/")
    o["root"] = (o.get("root") or o["code"]).replace("\\", "/")
    return o, pos


def emit(doc, status=0):
    print(json.dumps(doc, indent=2))
    sys.exit(status)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def state_dir(o):
    return Path(o["code"]) / STATE_REL


def journal_path(o):
    return state_dir(o) / "update.json"


def read_version(p):
    """(text or None, exists)."""
    try:
        return Path(p).read_text(encoding="utf-8").strip(), True
    except OSError:
        return None, False


def vtuple(v):
    return tuple(int(x) for x in SEMVER.match(v).groups())


def kind_of(frm, to):
    if frm is None:
        return "fresh"
    a, b = vtuple(frm), vtuple(to)
    if a == b:
        return "reinstall"
    if b < a:
        return "downgrade"
    return "workflow" if a[:2] != b[:2] else "patch"


def workflow_update(frm, to):
    """A workflow update: no installed VERSION, or a different major or minor (a downgrade across a minor too)."""
    return frm is None or vtuple(frm)[:2] != vtuple(to)[:2]


def load_journal(o):
    """The parsed journal, None when absent; ValueError when unreadable or of another format."""
    p = journal_path(o)
    if not p.exists():
        return None
    try:
        j = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ValueError(f"update.json is not readable JSON ({e})")
    if not isinstance(j, dict) or j.get("format") != 1:
        raise ValueError(f"update.json has format {j.get('format') if isinstance(j, dict) else None!r}, not 1")
    return j


# --- changes in flight (design D4) --------------------------------------------------------------------------------

def git(top, *args):
    r = subprocess.run(["git", "-C", str(top), "-c", "core.quotepath=off", *args], capture_output=True)
    return r.returncode, r.stdout


def git_lines(top, *args):
    rc, out = git(top, *args)
    return [x for x in out.decode("utf-8", "replace").split("\n") if x.strip()] if rc == 0 else []


def planning_repo(o):
    """(toplevel, P): the planning repo's toplevel and <root>/openspec relative to it; (None, None) outside a repo."""
    rc, out = git(o["root"], "rev-parse", "--show-toplevel")
    if rc != 0:
        return None, None
    top = Path(out.decode("utf-8", "replace").strip()).resolve()
    try:
        return top, (Path(o["root"]) / "openspec").resolve().relative_to(top).as_posix()
    except ValueError:
        return None, None


def planning_main(top):
    """The planning main: origin/<main> when present, else the local main (main, else master)."""
    for c in ("main", "master"):
        for ref in (f"refs/remotes/origin/{c}", f"refs/heads/{c}"):
            if git(top, "rev-parse", "--verify", "-q", ref + "^{commit}")[0] == 0:
                return ref
    return None


def branch_parts(short):
    """(prefix, change name) of a branch `<prefix>/<name>`, else None."""
    prefix, _, name = short.partition("/")
    return (prefix, name) if prefix in PREFIXES and name and "/" not in name else None


def collect(o):
    """(items, warnings): every change in flight, as {name, source, ref}. source is `working tree` or the local branch;
    ref is the git ref to read from (None for the working tree). Remote-only changes are warnings."""
    items, warnings, seen = [], [], set()
    changes = Path(o["root"]) / "openspec" / "changes"
    if changes.is_dir():
        for d in sorted(changes.iterdir()):
            if d.is_dir() and d.name != "archive":
                items.append({"name": d.name, "source": "working tree", "ref": None})
                seen.add(d.name)
    top, planning = planning_repo(o)
    if top is None:
        return items, warnings
    main = planning_main(top)
    archived = git_lines(top, "ls-tree", "--name-only", f"{main}:{planning}/changes/archive") if main else []

    def is_archived(name):
        return any(a == name or re.fullmatch(r"\d{4}-\d{2}-\d{2}-" + re.escape(name), a) for a in archived)

    def holds(ref, name):
        rc, out = git(top, "cat-file", "-t", f"{ref}:{planning}/changes/{name}")
        return rc == 0 and out.strip() == b"tree"

    local = set()
    for short in sorted(git_lines(top, "for-each-ref", "--format=%(refname:short)", "refs/heads/")):
        local.add(short)
        parts = branch_parts(short)
        if parts and parts[1] not in seen and holds("refs/heads/" + short, parts[1]) and not is_archived(parts[1]):
            items.append({"name": parts[1], "source": short, "ref": "refs/heads/" + short})
            seen.add(parts[1])
    for full in sorted(git_lines(top, "for-each-ref", "--format=%(refname)", "refs/remotes/origin/")):
        short = full[len("refs/remotes/origin/"):]
        parts = branch_parts(short)
        if parts and short not in local and parts[1] not in seen and holds(full, parts[1]) and not is_archived(parts[1]):
            warnings.append({"code": "in_flight_elsewhere", "name": parts[1], "ref": f"origin/{short}",
                             "message": f"{parts[1]} on origin/{short}: in flight elsewhere, not validated"})
    return items, warnings


def extract_branch(o, item, scratch):
    """git archive of the branch's change and specs into scratch/openspec/ (the branch's own specs, as validated)."""
    top, planning = planning_repo(o)
    paths = git_lines(top, "ls-tree", "--name-only", item["ref"], "--", f"{planning}/changes/{item['name']}", f"{planning}/specs")
    rc, data = git(top, "archive", "--format=tar", item["ref"], "--", *paths)
    if rc != 0:
        raise OSError(f"git archive {item['ref']} failed")
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for m in tar:
            if not m.name.startswith(planning + "/") or ".." in m.name.split("/") or not (m.isfile() or m.isdir()):
                continue
            dest = scratch / "openspec" / m.name[len(planning) + 1:]
            if m.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(tar.extractfile(m).read())


def run_openspec(args, cwd):
    exe = shutil.which("openspec")
    if not exe:
        return 127, "", "the openspec CLI is not on PATH"
    r = subprocess.run([exe, *args], cwd=str(cwd), env={**os.environ, "OPENSPEC_TELEMETRY": "0"}, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def first_error(text):
    lines = [x.strip() for x in text.splitlines() if x.strip() and not x.strip().startswith("Note:")]
    for x in lines:
        if x.lower().startswith("error"):
            return x
    return lines[0] if lines else "no output"


def check_change(scratch, name):
    """The three checks of design D4; the first error as text, None when the change passes."""
    rc, out, err = run_openspec(["schema", "validate", "specwright"], scratch)
    if rc != 0:
        return "openspec schema validate specwright: " + first_error(out + "\n" + err)
    rc, out, err = run_openspec(["validate", name, "--json"], scratch)
    try:
        item = json.loads(out)["items"][0]
        if not item.get("valid", rc == 0):
            iss = (item.get("issues") or [{}])[0]
            return f"openspec validate {name}: " + (f"{iss['path']}: " if iss.get("path") else "") + str(iss.get("message", "invalid"))
    except (ValueError, KeyError, IndexError, TypeError):
        if rc != 0:
            return f"openspec validate {name}: " + first_error(out + "\n" + err)
    rc, out, err = run_openspec(["status", "--change", name, "--json"], scratch)
    try:
        st = json.loads(out)
    except ValueError:
        return f"openspec status {name}: " + first_error(err + "\n" + out)
    bad = [x for x in st.get("status", []) if x.get("severity") == "error"] if isinstance(st.get("status"), list) else []
    if bad:
        return f"openspec status {name}: " + str(bad[0].get("message", bad[0].get("code", "error")))
    arts = {a["id"]: a for a in st.get("artifacts", [])}
    paths = st.get("artifactPaths", {})
    for a in arts.values():
        if a.get("status") == "done" or paths.get(a["id"], {}).get("existingOutputPaths"):
            for r in a.get("requires", []):
                if arts.get(r, {}).get("status") not in ("done", "skipped"):
                    return f"openspec status {name}: artifact {a['id']} exists but its dependency {r} is {arts.get(r, {}).get('status', 'missing')}"
    return None


def inflight_entries(o, to, schema_dir):
    """(entries, warnings) for a workflow update: every change in flight, validated against schema_dir in its own
    scratch root under <download>/.update-scratch/ (removed on the way out). An entry has name, source, status
    (validated | not on specwright | invalid), validated_against and, when invalid, error."""
    items, warnings = collect(o)
    base = Path(o["download"]) / SCRATCH
    entries = []
    try:
        for i, it in enumerate(items, 1):
            scratch = base / f"{i}-{it['name']}"
            e = {"name": it["name"], "source": it["source"], "status": "validated", "validated_against": to}
            try:
                (scratch / "openspec").mkdir(parents=True)
                if it["ref"] is None:
                    root = Path(o["root"]) / "openspec"
                    shutil.copytree(root / "changes" / it["name"], scratch / "openspec" / "changes" / it["name"])
                    if (root / "specs").is_dir():
                        shutil.copytree(root / "specs", scratch / "openspec" / "specs")
                else:
                    extract_branch(o, it, scratch)
                meta = scratch / "openspec" / "changes" / it["name"] / ".openspec.yaml"
                m = re.search(r"^schema:\s*['\"]?([^\s'\"#]+)", meta.read_text(encoding="utf-8", errors="replace"), re.M) if meta.is_file() else None
                if not m or m.group(1) != "specwright":
                    e.update({"status": "not on specwright", "validated_against": None})
                else:
                    shutil.copytree(schema_dir, scratch / "openspec" / "schemas" / "specwright")
                    (scratch / "openspec" / "config.yaml").write_text("schema: specwright\n", encoding="utf-8", newline="\n")
                    (scratch / "openspec" / "specs").mkdir(exist_ok=True)
                    err = check_change(scratch, it["name"])
                    if err:
                        e.update({"status": "invalid", "error": err})
            except OSError as ex:
                e.update({"status": "invalid", "error": f"could not read the change: {ex}"})
            entries.append(e)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return entries, warnings


def entry_key(e):
    return (e["name"], e["source"], e["status"])


def installed_unchanged(o):
    """True while no installed file has been replaced: no journal, or one that has not started the swap."""
    try:
        j = load_journal(o)
    except ValueError:
        return False
    return j is None or j.get("phase") in ("staging", "staged")


def base_doc(o, ok):
    inst, _ = read_version(state_dir(o) / "VERSION")
    return {"ok": ok, "interface": INTERFACE, "installed": inst, "unchanged": installed_unchanged(o)}


def model_line(data):
    """The `model:` line (bytes) in the frontmatter of an agent file, or None."""
    if not data.startswith(b"---"):
        return None
    end = data.find(b"\n---", 3)
    m = re.search(rb"^model:[^\r\n]*", data[:end] if end > 0 else data, re.M)
    return m.group(0) if m else None


def carry_model(data, installed):
    """The downloaded agent file with the installed file's `model:` line (the user's choice, kept)."""
    if installed is None or not Path(installed).is_file():
        return data
    new, old = model_line(data), model_line(Path(installed).read_bytes())
    if new is None or old is None or new == old:
        return data
    i = data.find(new)
    return data[:i] + old + data[i + len(new):]


def mk_group(gid, kind, d, items):
    d = d.replace("\\", "/").rstrip("/")
    parent, _, base = d.rpartition("/")
    g = {"id": gid, "kind": kind, "dir": d, "staging": f"{parent}/.specwright-update-{base}", "items": []}
    for name, typ, src in items:
        g["items"].append({"name": name, "type": typ, "src": src, "installed": (Path(d) / name).exists()})
    return g


def build_groups(o, refusals):
    dl = Path(o["download"])
    groups, orphans = [], []
    names = sorted(p.name for p in (dl / "skills").glob("specwright-*") if p.is_dir())
    if not names:
        refusals.append({"code": "download_incomplete", "message": "the download has no skills/specwright-* directory"})
    if not (dl / "schemas" / "specwright" / "schema.yaml").is_file():
        refusals.append({"code": "download_incomplete", "message": "the download has no schemas/specwright/schema.yaml"})
    if not o["skills"] and not o["agents"]:
        refusals.append({"code": "no_targets", "message": "no --skills or --agents directory was given"})
    for i, sd in enumerate(o["skills"], 1):
        g = mk_group(f"skills-{i}", "skills", sd, [(n, "dir", dl / "skills" / n) for n in names])
        groups.append(g)
        for p in sorted(Path(g["dir"]).glob("specwright-*")):
            if p.is_dir() and p.name not in names:
                orphans.append({"group": g["id"], "dir": g["dir"], "name": p.name})
    for spec in o["agents"]:
        kind, _, d = spec.partition("=")
        adir = dl / "agents" / kind
        if not d or not adir.is_dir():
            refusals.append({"code": "agent_kind", "message": f"--agents {spec}: the download has no agents/{kind}"})
            continue
        files = sorted(p.name for p in adir.glob("*.md"))
        g = mk_group(f"agents-{kind}", "agents", d, [(n, "file", adir / n) for n in files])
        g["agent_kind"] = kind
        groups.append(g)
        for p in sorted(Path(g["dir"]).glob("specwright-*.md")):
            if p.is_file() and p.name not in files:
                orphans.append({"group": g["id"], "dir": g["dir"], "name": p.name})
    groups.append(mk_group("schema", "schema", f"{o['root']}/openspec/schemas", [("specwright", "dir", dl / "schemas" / "specwright")]))
    return groups, orphans


def make_plan(o, check=False):
    """The plan document and groups. check=True (cmd_plan) also collects and validates the changes in flight of a
    workflow update against the download's schema; every other caller (stage, ops) reuses the verdict."""
    refusals, warnings = [], []
    inst, exists = read_version(state_dir(o) / "VERSION")
    if exists and not (inst and SEMVER.match(inst)):
        refusals.append({"code": "installed_version_invalid", "message": f"openspec/.specwright/VERSION holds {inst!r}, not MAJOR.MINOR.PATCH"})
        inst = None
    to, _ = read_version(Path(o["download"]) / "VERSION")
    if not (to and SEMVER.match(to)):
        refusals.append({"code": "download_version_invalid", "message": f"the download's VERSION holds {to!r}, not MAJOR.MINOR.PATCH"})
        to = None
    journal = None
    try:
        j = load_journal(o)
        if j is not None:
            journal = {"from": j.get("from"), "to": j.get("to"), "phase": j.get("phase"), "format": j.get("format")}
    except ValueError as e:
        refusals.append({"code": "journal_unreadable", "message": str(e)})
    groups, orphans = build_groups(o, refusals)
    inflight, checked = [], False
    if check and to and not refusals and workflow_update(inst, to):
        checked = True
        entries, found = inflight_entries(o, to, Path(o["download"]) / "schemas" / "specwright")
        warnings.extend(found)
        for e in entries:
            if e["status"] == "invalid":
                where = "" if e["source"] == "working tree" else f" on {e['source']}"
                refusals.append({"code": "change_invalid", "change": e["name"], "ref": None if not where else e["source"],
                                 "message": f"change {e['name']}{where or ' (working tree)'} fails validation against {to}: {e['error']}"})
            else:
                inflight.append(e)
    doc = base_doc(o, not refusals)
    doc.update({"from": inst, "to": to, "ref": o.get("ref"), "kind": kind_of(inst, to) if to else None, "role": "none",
                "targets": [{"group": g["id"], "kind": g["kind"], "dir": g["dir"], "name": it["name"], "installed": it["installed"]}
                            for g in groups for it in g["items"]],
                "orphans": orphans, "journal": journal, "inflight_checked": checked, "inflight": inflight,
                "refusals": refusals, "warnings": warnings})
    if refusals:
        doc.update({"error": "refused", "message": refusals[0]["message"], "unchanged": True})
    return doc, groups


def cmd_plan(o, pos):
    doc, _ = make_plan(o, check=True)
    if o.get("extra"):
        doc.update(json.loads(o["extra"]))
    emit(doc, 0 if doc["ok"] else 1)


def expected_manifest(groups):
    out = []
    for g in groups:
        for it in g["items"]:
            src = Path(it["src"])
            if it["type"] == "dir":
                for f in sorted(p for p in src.rglob("*") if p.is_file()):
                    out.append({"group": g["id"], "path": f"{it['name']}/{f.relative_to(src).as_posix()}", "sha256": sha(f.read_bytes())})
            else:
                data = carry_model(src.read_bytes(), Path(g["dir"]) / it["name"]) if g["kind"] == "agents" else src.read_bytes()
                out.append({"group": g["id"], "path": it["name"], "sha256": sha(data)})
    return out


def cmd_journal_new(o, pos):
    """Write the new journal text to the path in pos[0]. One group, target and manifest entry per line, so that the
    shell can change a state with sed (the swap writes the journal before every rename)."""
    doc, groups = make_plan(o)
    if not doc["ok"]:
        emit(doc, 1)
    plan = json.loads(o["plan"]) if o.get("plan") else {}
    inflight = {"checked": plan.get("inflight_checked", False), "changes": plan.get("inflight", []),
                "warnings": [w for w in plan.get("warnings", []) if w.get("code") == "in_flight_elsewhere"]}
    head = {"format": 1, "from": doc["from"], "to": doc["to"], "ref": o.get("ref"), "kind": doc["kind"], "role": "none",
            "code": o["code"], "root": o["root"], "inflight": inflight}
    lines = ["{"] + [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}," for k, v in head.items()] + ['  "phase": "staging",']
    groups_j = [{k: v for k, v in g.items() if k != "items"} for g in groups]
    targets = [{"gid": g["id"], "name": it["name"], "type": it["type"], "dir": g["dir"], "staging": g["staging"],
                "installed": it["installed"], "state": "pending"} for g in groups for it in g["items"]]
    for key, items, last in (("groups", groups_j, False), ("targets", targets, False), ("manifest", expected_manifest(groups), True)):
        lines.append(f'  "{key}": [')
        lines.append(",\n".join("    " + json.dumps(x, ensure_ascii=False) for x in items))
        lines.append("  ]" + ("" if last else ","))
    lines.append("}")
    Path(pos[0]).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def cmd_ops(o, pos):
    """Shell lines for stage: `mkdir <dir>` and `cp <flag|-> <src> <dest dir>`, then the staging directories."""
    doc, groups = make_plan(o)
    if not doc["ok"]:
        emit(doc, 1)
    for g in groups:
        new = g["staging"] + "/new"
        print(f"mkdir\t{new}")
        for it in g["items"]:
            print(f"cp\t{'-R' if it['type'] == 'dir' else '-'}\t{it['src'].as_posix()}\t{new}")


def cmd_staging(o, pos):
    """The staging directories: of the journal when there is one, else of the plan."""
    j = load_journal(o)
    for g in (j["groups"] if j else make_plan(o)[1]):
        print(g["staging"])


def cmd_carry(o, pos):
    """Put the installed `model:` line into each staged agent file (in staging only)."""
    j = load_journal(o)
    groups = {g["id"]: g for g in j["groups"]}
    for t in j["targets"]:
        g = groups[t["gid"]]
        if g["kind"] != "agents":
            continue
        staged = Path(t["staging"]) / "new" / t["name"]
        if staged.is_file():
            data = staged.read_bytes()
            out = carry_model(data, Path(t["dir"]) / t["name"])
            if out != data:
                staged.write_bytes(out)


def cmd_verify(o, pos):
    j = load_journal(o)
    want = {(m["group"], m["path"]): m["sha256"] for m in j["manifest"]}
    mism = []
    for g in j["groups"]:
        new = Path(g["staging"]) / "new"
        for m in (m for m in j["manifest"] if m["group"] == g["id"]):
            f = new / m["path"]
            if not f.is_file():
                mism.append({"group": g["id"], "path": m["path"], "file": f.as_posix(), "problem": "missing"})
            elif sha(f.read_bytes()) != m["sha256"]:
                mism.append({"group": g["id"], "path": m["path"], "file": f.as_posix(), "problem": "changed"})
        if new.is_dir():
            for f in sorted(p for p in new.rglob("*") if p.is_file()):
                rel = f.relative_to(new).as_posix()
                if (g["id"], rel) not in want:
                    mism.append({"group": g["id"], "path": rel, "file": f.as_posix(), "problem": "unexpected"})
    if not mism:
        print(json.dumps({"ok": True, "files": len(j["manifest"])}))
        return
    names = ", ".join(f"{m['path']} ({m['problem']})" for m in mism[:5]) + (f" and {len(mism) - 5} more" if len(mism) > 5 else "")
    doc = base_doc(o, False)
    doc.update({"error": "verification_failed", "message": f"the staged copy differs from the download: {names}", "mismatches": mism})
    emit(doc, 1)


def cmd_verify_swap(o, pos):
    """Exit 0 when every staged file matches the manifest, wherever the swap left it (in new/ or already swapped in)."""
    j = load_journal(o)
    groups = {g["id"]: g for g in j["groups"]}
    want = {(m["group"], m["path"]) for m in j["manifest"]}
    bad = []
    for m in j["manifest"]:
        g = groups[m["group"]]
        top = m["path"].split("/")[0]
        f = Path(g["staging"]) / "new" / m["path"]
        if not (Path(g["staging"]) / "new" / top).exists():
            f = Path(g["dir"]) / m["path"]
        if not f.is_file() or sha(f.read_bytes()) != m["sha256"]:
            bad.append(m["path"])
    for g in j["groups"]:
        new = Path(g["staging"]) / "new"
        if new.is_dir():
            for f in new.rglob("*"):
                if f.is_file() and (g["id"], f.relative_to(new).as_posix()) not in want:
                    bad.append(f.relative_to(new).as_posix())
    print(json.dumps({"ok": not bad, "bad": bad}))
    sys.exit(1 if bad else 0)


def cmd_swap_check(o, pos):
    """Before the first rename of a workflow update: collect and validate again, against the staged schema, and stop
    when the set of changes in flight or any result differs from what stage recorded in the journal."""
    j = load_journal(o)
    rec = j.get("inflight") or {}
    if not rec.get("checked"):
        print(json.dumps({"ok": True, "checked": False}))
        return
    schema = next(g for g in j["groups"] if g["kind"] == "schema")["staging"] + "/new/specwright"
    entries, _ = inflight_entries(o, j["to"], schema)
    was, now = {entry_key(e): e for e in rec.get("changes", [])}, {entry_key(e): e for e in entries}
    diffs = []
    for k, e in now.items():
        if k not in was:
            if e["status"] == "invalid":
                diffs.append(f"{e['name']} ({e['source']}) fails validation against {j['to']}: {e['error']}")
            else:
                diffs.append(f"{e['name']} ({e['source']}) was not in flight when the update was planned")
    for k, e in was.items():
        if k not in now:
            diffs.append(f"{e['name']} ({e['source']}) was in flight when the update was planned and is not now")
    if not diffs:
        print(json.dumps({"ok": True, "checked": True, "changes": len(entries)}))
        return
    doc = base_doc(o, False)
    doc.update({"error": "inflight_changed", "differences": diffs,
                "message": "the changes in flight differ from the plan, so nothing was swapped: " + "; ".join(diffs)})
    emit(doc, 1)


def cmd_err(o, pos):
    doc = base_doc(o, False)
    doc.update({"error": o["error"], "message": o["message"]})
    if o.get("extra"):
        doc.update(json.loads(o["extra"]))
    emit(doc, 1)


def cmd_report(o, pos):
    """The success document of stage / swap / finish, from the journal (and --extra)."""
    sub = pos[0]
    j = load_journal(o)
    doc = base_doc(o, True)
    doc.update({"subcommand": sub, "state": j["phase"], "from": j["from"], "to": j["to"], "ref": j.get("ref"), "kind": j.get("kind"),
                "role": j.get("role"), "files": len(j["manifest"]),
                "inflight_checked": (j.get("inflight") or {}).get("checked", False),
                "inflight": (j.get("inflight") or {}).get("changes", []),
                "warnings": (j.get("inflight") or {}).get("warnings", []),
                "groups": [{"id": g["id"], "kind": g["kind"], "dir": g["dir"], "staging": g["staging"],
                            "targets": sum(1 for t in j["targets"] if t["gid"] == g["id"])} for g in j["groups"]]})
    if sub == "swap":
        doc["store_written"] = False
        if j["from"]:
            doc["restart"] = (f"Agent sessions started before this update still run {j['from']}; restart them before they "
                              f"continue a change on {j['to']}.")
    if o.get("extra"):
        doc.update(json.loads(o["extra"]))
    emit(doc)


COMMANDS = {n[4:]: f for n, f in list(globals().items()) if n.startswith("cmd_")}
if __name__ == "__main__":
    opts, positional = parse(sys.argv[2:])
    try:
        COMMANDS[sys.argv[1].replace("-", "_")](opts, positional)
    except ValueError as e:
        doc = {"ok": False, "interface": INTERFACE, "error": "journal_unreadable", "message": str(e)}
        emit(doc, 1)
PYSRC_EOF
