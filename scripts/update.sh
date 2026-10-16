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
#                     root for a project that uses a store: a root in a git repo other than the code checkout's)
#   --skills DIR      a chosen skills directory (e.g. <code>/.claude/skills); repeat for each one. Only the
#                     specwright-* directories in it are touched
#   --agents KIND=DIR a chosen agents directory and the agent kind of the files it gets: claude (agents/claude/*.md
#                     from the download) or omp (agents/omp/*.md); repeat for each one. Only specwright-*.md files
#   --download DIR    the download tree (default: the directory above this script). Its VERSION is the target version
#   --ref REF         the ref the download came from (e.g. v0.6.0 or main); recorded in the journal and the reports
#   --rollback        recover only: roll the swapped update back instead of resuming it (the prompt's Step 7 failed)
# The installed version is read from <code>/openspec/.specwright/VERSION (missing = a fresh install).
#
# Subcommands:
#   plan     read only. Prints interface (1), from, to, ref, kind (fresh | patch | workflow | reinstall | downgrade),
#            role, store, inflight_checked, inflight, targets (every directory or file that stage will replace), orphans
#            (installed specwright-* names with no downloaded counterpart; never touched), journal (a pending
#            update.json: {from, to, phase, format} or null), refusals and warnings. Writes nothing outside
#            <download>/.update-scratch/ (removed before plan returns), with one exception: when a journal is pending, plan
#            first runs recover (below) and adds recovered: {action, message, from, to, store_written} to its document; journal then
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
#            Store roles (design D5), from <root>/openspec/.specwright/STORE (two lines, `version: <x.y.z>` and `owner: <id>`)
#            and this project's id (its origin fetch URL as host/owner/repo: scheme, userinfo, port, `.git` and a
#            trailing dot on the host dropped; with no origin, or an origin without a host, `path:<code toplevel>`):
#              - none: the root is in the code checkout's own git repo (repo-local). Nothing below applies.
#              - claim: the root is a store and has no STORE. This project's swap writes the record and owns the schema.
#              - owner: STORE names this project's id. Its swap replaces the store's schema (on a free store).
#              - other: STORE names another project. Only the code-side files are staged (no schema target), the changes
#                in flight are not collected, and the update is refused when its target's major or minor version differs
#                from STORE's version: the refusal (code store_version) names the store's version, its owner and the
#                highest vMAJOR.MINOR.* tag that `git ls-remote --tags` lists on the download's origin.
#            store is {root, version, owner, id} for claim, owner and other (version and owner are null for claim). A STORE
#            with no version or no owner is a refusal (code store_record_unreadable) naming the file and the field: plan and
#            stage stop before any write. For claim and owner on a workflow update every change in flight in the store is
#            attributed: it is this project's when the code repo has a local branch <prefix>/<name> (feat, bugfix,
#            refactor, docs, chore); otherwise it is another project's and refuses the update (code other_project_change,
#            the change named). This project's changes are validated as above.
#            The planning main of the collection is the configured one first: planning_store.main_branch (a store) or
#            main_branch (repo-local) in <code>/openspec/specwright.yaml, else the detection above.
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
#            new/<name> -> target. The journal records each step before it runs. Prints store_written and a restart
#            notice. A swap that was started and interrupted is finished or undone by recover, not by swap.
#            For claim and owner, before its first rename, swap takes the store's gate lock (the lock of
#            skills/specwright-branch: $(git -C <store> rev-parse --path-format=absolute --git-common-dir)/specwright-gate.lock)
#            in this order: a random token into the journal (atomic write), then mkdir of the lock, then the lock's owner
#            file (time, `change: specwright-update <from> -> <to>`, `code: <--code>`, `token: <token>`). Under the lock:
#              1. STORE is read again: a record naming another project stops the swap (error store_claimed when this
#                 project was to claim it, else store_owner_changed), naming that owner;
#              2. the store must be free: on its main (the configured one, else main, else master) with `git status
#                 --porcelain` empty apart from this update's staging directories. A busy store (a change branch, or
#                 dirty) lets a patch update (the same major.minor) whose staged schema is byte-identical to the installed
#                 one swap its code side only: the store targets and the record leave the journal, the staging in the store
#                 is removed, the lock is released at once and store.message says `store schema already current`
#                 (store_written false). Any other update stops with error store_busy naming the branch or the dirty
#                 paths and saying to finish that change first;
#              3. the staged copy is verified and the changes in flight are collected, attributed and validated again
#                 (error inflight_changed on a difference);
#              4. the store's current config.yaml and STORE (or their absence) are saved under <schema staging>/prev/ and
#                 recorded in the journal (prev_config, prev_store: present | absent); the code side is swapped, then the
#                 schema, then STORE is written (version: <to>, owner: <id>; never committed) and store_state becomes
#                 written;
#              5. the lock is released.
#            A stop at 1-3 releases the lock and has written nothing installed. The document has store_written (true when
#            the schema and STORE were replaced, so the prompt's Step 5 merges the store's config.yaml) and, for claim,
#            owner and other, store: {role, id, owner, version, written, claimed, uncommitted[], message}; uncommitted
#            lists the STORE record and the schema directory, relative to the store's repo. For other the message is
#            `store config managed by owner <id>` (Step 5 is skipped, Step 7 reports that instead of failing).
#   note-config  right after the prompt's Step 5 (journal phase swapped): records the sha256 of the merged
#            <root>/openspec/config.yaml in the journal (config_sha), so that a rollback accepts that file as written by this
#            update. Prints config and sha256 besides the usual fields. Error config_missing when there is no file.
#   finish   once VERSION reads the target version (the prompt's Step 7 stamp): removes old/, the staging directories
#            and the journal. Rerunning it is safe.
#   recover  decides from the journal and the disk (design D3), and prints action, message, from, to and store_written:
#              - swap not started (no target old-moved or swapped)  -> discarded: staging and journal removed;
#                message `discarded unfinished update to <to>`
#              - phase swapped and VERSION already reads <to>        -> finished: staging and journal removed
#              - every staged file (in new/ or already swapped in) matches the manifest -> resumed: the rest of the
#                swap runs; message `resumed update to <to>`. The journal stays (phase swapped) for the prompt's
#                Step 7 stamp and finish, unless the update is not the download's own version (the download's VERSION
#                differs from <to>) or VERSION already reads <to>: then VERSION is written as <to> and the update is
#                finished, so that the download's own update can start from it
#              - otherwise -> rolled back: each old/ is moved back, each swapped-in new copy is removed, staging and
#                journal removed, VERSION untouched; message `rolled back to <from>`. recover --rollback chooses this outcome
#                for a swap that completed (the prompt's Step 7 failed), unless VERSION already reads <to> (error
#                rollback_stamped).
#            Store gate lock (claim and owner): in every outcome recover releases the lock when its owner file names
#            `specwright-update`, this checkout (`code:`) and the journal's token (a journal with a token and no lock needs
#            no takeover). A lock whose owner file is missing or empty stops recover with error gate_lock_unverified, naming
#            the lock for the user's confirm-then-remove, and changes nothing. Another holder is named (error store_locked)
#            whenever recover needs the lock. Resuming takes the lock over to write STORE when the interruption came
#            before it; a rollback restores the saved config.yaml and STORE (or removes STORE after a claim) with the
#            schema. A rollback after the swap released the lock takes the lock again and repeats steps 1-2 for the
#            recovery: the store must be on its main, STORE must still read what this update wrote, and `git status`
#            may list only this update's staging, the swapped-in schema, STORE and the config.yaml noted by note-config,
#            each with the recorded content. Otherwise it stops before any rename (error store_busy, naming the branch or
#            the paths; store_owner_changed for STORE), releases the lock and keeps the swapped state and the journal.
#            Also removes a leftover update.json.tmp. With no journal it reports action none. plan calls it first.
# Journal (openspec/.specwright/update.json, written to update.json.tmp and renamed): format 1, from, to, ref, kind,
# role, code, root, inflight, owner_id, store_owner, store_version, store_record, store_lock, store_staging,
# store_state (none | pending | written | current), token, prev_config, prev_store, config_sha, phase (staging | staged |
# swapping | swapped), groups, targets (state pending | staged | old-moved | swapped), manifest ({group, path, sha256}
# for every staged file).
# Lock: openspec/.specwright/update.lock (a directory made with mkdir) holds `pid:` and `host:`. A lock held by a dead pid
# on this host is replaced and reported as lock_replaced; any other holder stops the run (error locked).
# File operations use the external mv, cp and rm only (never builtins or Python), so the evals can put counting shims
# first on PATH and see every step (design: Testing the interruption criterion).
# Exit: 0 done, 1 stop (the JSON has "ok": false, "error" and "message"), 2 usage.
# Needs bash, mkdir, date and Python 3.8+ (hostname when $HOSTNAME is unset); git for the store checks.
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

code="" root="" download="" ref="" sub="" ROLLBACK=0
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
    --rollback) ROLLBACK=1; shift ;;
    -*) usage "unknown option $1" ;;
    *) [ -z "$sub" ] || usage "one subcommand only"; sub=$1; shift ;;
  esac
done
[ -n "$sub" ] || usage "a subcommand is required: plan, stage, swap, note-config, finish or recover"
[ "$ROLLBACK" = 0 ] || [ "$sub" = recover ] || usage "--rollback belongs to the recover subcommand"
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

jstr() {  # jstr KEY: a top-level member as text; "" when null or missing. Unlike jfield it keeps commas and quotes inside
  local l v
  for l in "${JL[@]}"; do
    if [[ "$l" == "  \"$1\": "* ]]; then
      v=${l#*\": }
      v=${v%,}
      case "$v" in null) v="" ;; \"*\") v=${v#\"}; v=${v%\"} ;; esac
      printf '%s' "$v"
      return 0
    fi
  done
}

jset_field() {  # jset_field KEY JSON: replace a top-level member in memory (jflush writes it)
  local i
  for i in "${!JL[@]}"; do
    if [[ "${JL[i]}" == "  \"$1\": "* ]]; then JL[i]="  \"$1\": $2,"; return 0; fi
  done
  die journal_unreadable "update.json has no $1 member"
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

REC_ACTION="" REC_MSG="" REC_FROM="" REC_TO="" REC_SW=false

recover_cleanup() {  # staging first, journal last
  remove_staging
  rm -f "$jtmp"
  rm -f "$journal"
}

# Store gate lock (design D5). It is the lock of skills/specwright-branch: a directory made with mkdir in the store's git
# common dir. Its owner file names this update (`change: specwright-update <from> -> <to>`), this checkout (`code:`) and
# the journal's token. Only a run from that checkout, with that token, takes it over.
GATE="" GATE_HELD=0 GATE_STATE=none
G_CHANGE="" G_CODE="" G_TOKEN="" G_TIME=""

gate_read() {  # gate_read DIR: the fields of DIR/owner
  local l
  G_CHANGE="" G_CODE="" G_TOKEN="" G_TIME=""
  [ -f "$1/owner" ] || return 0
  while IFS= read -r l || [ -n "$l" ]; do
    l=${l%$'\r'}
    case "$l" in
      "change: "*) G_CHANGE=${l#change: } ;;
      "code: "*) G_CODE=${l#code: } ;;
      "token: "*) G_TOKEN=${l#token: } ;;
      "time: "*) G_TIME=${l#time: } ;;
    esac
  done < "$1/owner"
}

gate_holder() { printf '%s' "${G_CHANGE:-an unknown holder}${G_CODE:+ (from $G_CODE)}${G_TIME:+, taken $G_TIME}"; }

gate_release() {
  if [ "$GATE_HELD" = 1 ]; then
    GATE_HELD=0
    rm -rf "$GATE" || die gate_release_failed "could not remove the store gate lock $GATE"
  fi
}

gate_write_owner() {  # gate_write_owner FROM TO TOKEN
  printf 'time: %s\nchange: specwright-update %s -> %s\ncode: %s\ntoken: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" "$code" "$3" > "$GATE/owner"
}

gate_stop_locked() {  # the gate lock is held by someone else: stop, naming the holder
  gate_read "$GATE"
  case "$G_CHANGE" in
    specwright-update*)
      if [ "$G_CODE" = "$code" ]; then
        die store_locked "the store gate lock $GATE is held by an earlier swap of this checkout ($(gate_holder)); run recover from this checkout, it takes the lock over and releases it"
      fi
      die store_locked "the store gate lock $GATE is held by an update from ${G_CODE:-another checkout} ($(gate_holder)); rerun the update there" ;;
  esac
  die store_locked "the store gate lock $GATE is held by $(gate_holder); another session is in its gate or roadmap step for this store. Nothing was written. Wait for it, or when it is stale confirm that no session uses the store and remove it with rm -r"
}

gate_inspect() {  # gate_inspect DIR TOKEN: GATE_STATE = none | ours | unverified | other (ours also sets GATE_HELD)
  GATE_STATE=none
  [ -d "$1" ] || return 0
  if [ ! -s "$1/owner" ]; then
    if [ -n "$2" ]; then GATE_STATE=unverified; else GATE_STATE=other; fi
    return 0
  fi
  gate_read "$1"
  if [ -n "$2" ] && [ "${G_CHANGE#specwright-update}" != "$G_CHANGE" ] && [ "$G_CODE" = "$code" ] && [ "$G_TOKEN" = "$2" ]; then
    GATE_STATE=ours
    GATE_HELD=1
  else
    GATE_STATE=other
  fi
}

recover_gate() {  # recover_gate resume|rollback: hold the store gate lock before the store is touched
  local out rc=0 from
  case "$GATE_STATE" in
    ours) return 0 ;;  # held since the interrupted swap: nobody else could have changed the store
    other) gate_stop_locked ;;
  esac
  mkdir "$GATE" 2>/dev/null || gate_stop_locked  # none: the swap released it, so the recovery takes it again
  GATE_HELD=1
  from=$(jfield from)
  gate_write_owner "${from/#null/none}" "$(jfield to)" "$(jstr token)"
  if [ "$1" = rollback ]; then  # design D5: repeat the store checks; a failure releases the lock and keeps everything
    out=$(pyx store-check "${PYARGS[@]}" --mode rollback) || rc=$?
    if [ "$rc" != 0 ]; then gate_release; printf '%s\n' "$out"; exit 1; fi
  fi
}

store_finish() {  # after swap_loop: write the STORE record (once), then release the gate lock
  if [ "$(jstr store_state)" = pending ]; then
    local staging rec
    staging=$(jstr store_staging) rec=$(jstr store_record)
    mkdir -p "${rec%/*}"
    printf 'version: %s\nowner: %s\n' "$(jfield to)" "$(jstr owner_id)" > "$staging/STORE.new"
    mv -f "$staging/STORE.new" "$rec" || die rename_failed "could not write $rec"
    jset_field store_state '"written"'
    jflush
  fi
  gate_release
}

restore_store_files() {  # the store's previous config.yaml and STORE (or their absence), saved in the schema staging
  local prev cfg rec
  prev="$(jstr store_staging)/prev" cfg="$root/openspec/config.yaml" rec=$(jstr store_record)
  if [ "$(jstr prev_config)" = present ]; then
    if [ -f "$prev/config.yaml" ]; then cp "$prev/config.yaml" "$cfg" || die rename_failed "could not restore $cfg"; fi
  elif [ -n "$(jstr config_sha)" ] && [ -e "$cfg" ]; then  # absent before the update: the merge created it
    rm -f "$cfg"
  fi
  if [ "$(jstr prev_store)" = present ]; then
    if [ -f "$prev/STORE" ]; then cp "$prev/STORE" "$rec" || die rename_failed "could not restore $rec"; fi
  else
    rm -f "$rec"
  fi
}

recover_after() {  # runs after every outcome: the update's own store gate lock is released in all of them
  gate_release
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
  case "$(jstr role)/$(jstr store_state)" in owner/pending|owner/written|claim/pending|claim/written) restore_store_files ;; esac
  recover_cleanup
}

recover_core() {
  REC_ACTION=none REC_MSG="no unfinished update" REC_FROM="" REC_TO="" REC_SW=false
  if [ ! -f "$journal" ]; then rm -f "$jtmp"; return 0; fi
  jload
  [ "$(jfield format)" = 1 ] || die journal_unreadable "update.json has format '$(jfield format)', not 1"
  local phase to from now="" dlv="" l started=0 vrc=0 storeful=0 sst
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
  sst=$(jstr store_state)
  case "$(jstr role)" in owner|claim) storeful=1 ;; esac
  GATE_STATE=none GATE=""
  if [ "$storeful" = 1 ] && [ -n "$(jstr store_lock)" ]; then  # is the store's gate lock this update's own?
    GATE=$(jstr store_lock)
    gate_inspect "$GATE" "$(jstr token)"
    [ "$GATE_STATE" != unverified ] || die gate_lock_unverified "the store gate lock $GATE has no owner information (a swap killed right after creating it, or another session's gate midway through taking it), so this checkout cannot tell whose it is. Confirm that no session is in a gate or roadmap step on the store, remove it with rm -r, then rerun the update. The journal and the staging are kept"
  fi
  if [ "$phase" = swapped ] && [ "$now" = "$to" ]; then
    [ "$ROLLBACK" = 0 ] || die rollback_stamped "VERSION already reads $to: the update is complete and cannot be rolled back"
    [ "$sst" != written ] || REC_SW=true
    recover_cleanup
    REC_ACTION=finished REC_MSG="finished update to $to"
  elif [ "$started" = 0 ]; then
    recover_cleanup
    REC_ACTION=discarded REC_MSG="discarded unfinished update to $to"
  else
    if [ "$ROLLBACK" = 1 ]; then vrc=1; else pyx verify-swap "${PYARGS[@]}" >/dev/null || vrc=$?; fi
    if [ "$vrc" = 0 ]; then
      if [ "$storeful" = 1 ] && [ "$sst" = pending ]; then recover_gate resume; fi
      swap_loop
      store_finish
      [ "$(jstr store_state)" != written ] || REC_SW=true
      [ ! -f "$download/VERSION" ] || read -r dlv < "$download/VERSION" || true
      dlv=${dlv//$'\r'/}
      if [ "$now" = "$to" ] || [ "$dlv" != "$to" ]; then  # nobody will stamp this update: do it here, then finish
        [ "$now" = "$to" ] || printf '%s\n' "$to" > "$state_dir/VERSION"
        recover_cleanup
      fi
      REC_ACTION=resumed REC_MSG="resumed update to $to"
    else
      if [ "$storeful" = 1 ] && { [ "$sst" = pending ] || [ "$sst" = written ]; }; then recover_gate rollback; fi
      recover_rollback
      REC_ACTION=rolled-back REC_MSG="rolled back to ${from:-the state before the first install}"
    fi
  fi
  recover_after
}

q() { if [ -n "$1" ]; then printf '"%s"' "$1"; else printf null; fi; }  # a JSON string or null

rec_json() {  # the recovered object: action, message, from, to
  printf '{"action": "%s", "message": "%s", "from": %s, "to": %s, "store_written": %s}' "$REC_ACTION" "$REC_MSG" "$(q "$REC_FROM")" "$(q "$REC_TO")" "$REC_SW"
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
  printf '{"ok": true, "interface": 1, "subcommand": "recover", "installed": %s, "action": "%s", "message": "%s", "from": %s, "to": %s, "store_written": %s%s}\n' \
    "$(q "$now")" "$REC_ACTION" "$REC_MSG" "$(q "$REC_FROM")" "$(q "$REC_TO")" "$REC_SW" "${lx:+, $lx}"
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

swap_store_prepare() {  # the store half of the swap (design D5) up to the first rename; every stop releases the gate lock
  local from to gate tok out rc=0 vout vrc=0 staging cfg rec prevc=absent prevs=absent
  from=$(jfield from) to=$(jfield to) gate=$(jstr store_lock)
  [ "$from" != null ] || from=none
  [ -n "$gate" ] || die store_unavailable "the store's git directory could not be found when the update was staged"
  printf -v tok '%08x%08x%08x' $(( (RANDOM << 15) | RANDOM )) $(( (RANDOM << 15) | RANDOM )) "$$"
  jset_field token "\"$tok\""  # the token reaches the journal first, then the lock, then the lock's owner file
  jflush
  GATE=$gate
  mkdir "$gate" 2>/dev/null || gate_stop_locked
  GATE_HELD=1
  gate_write_owner "$from" "$to" "$tok"
  # under the lock: 1. STORE read again, 2. the store is free
  out=$(pyx store-check "${PYARGS[@]}" --mode swap) || rc=$?
  if [ "$rc" != 0 ]; then gate_release; printf '%s\n' "$out"; exit 1; fi
  vout=$(pyx verify "${PYARGS[@]}") || vrc=$?
  if [ "$vrc" != 0 ]; then gate_release; printf '%s\n' "$vout"; exit 1; fi
  case "$out" in
    *'"mode": "code-only"'*)  # busy store, schema unchanged: leave the store alone, swap the code side only
      staging=$(jstr store_staging)
      rm -rf "$staging" || die rename_failed "could not remove $staging"
      pyx journal-drop-store "${PYARGS[@]}" "$jtmp"
      mv -f "$jtmp" "$journal"
      jload
      gate_release
      return 0 ;;
  esac
  # 3. the changes in flight again, 4. the store's current config.yaml and STORE saved for a rollback
  vrc=0
  vout=$(pyx swap-check "${PYARGS[@]}") || vrc=$?
  if [ "$vrc" != 0 ]; then gate_release; printf '%s\n' "$vout"; exit 1; fi
  staging=$(jstr store_staging) cfg="$root/openspec/config.yaml" rec=$(jstr store_record)
  mkdir -p "$staging/prev"
  if [ -f "$cfg" ]; then cp "$cfg" "$staging/prev/config.yaml"; prevc=present; fi
  if [ -f "$rec" ]; then cp "$rec" "$staging/prev/STORE"; prevs=present; fi
  jset_field prev_config "\"$prevc\""
  jset_field prev_store "\"$prevs\""
}

do_swap() {
  acquire_lock
  [ -f "$journal" ] || die no_journal "no staged update is recorded in $journal; run stage first"
  jload
  [ "$(jfield format)" = 1 ] || die journal_unreadable "update.json has format '$(jfield format)', not 1"
  local phase storeful=0
  phase=$(jfield phase)
  case "$phase" in
    staged|swapping|swapped) ;;
    *) die not_staged "the recorded update is in phase '$phase', not staged; run recover first" ;;
  esac
  case "$(jstr role)" in owner|claim) storeful=1 ;; esac
  if [ "$storeful" = 1 ] && [ "$phase" != staged ]; then  # a started store swap is finished or undone by recover
    die swap_interrupted "this update's swap was started (phase $phase); run recover from this checkout to finish or undo it"
  fi
  if [ "$phase" = staged ] && [ "$storeful" = 1 ]; then
    swap_store_prepare
  elif [ "$phase" = staged ]; then
    local vout vrc=0
    vout=$(pyx verify "${PYARGS[@]}") || vrc=$?
    if [ "$vrc" != 0 ]; then printf '%s\n' "$vout"; exit 1; fi
    vrc=0  # a workflow update: the changes in flight must still be the ones the plan validated (before any rename)
    vout=$(pyx swap-check "${PYARGS[@]}") || vrc=$?
    if [ "$vrc" != 0 ]; then printf '%s\n' "$vout"; exit 1; fi
  fi
  [ "$phase" = swapped ] || jwrite_phase swapping
  swap_loop
  [ "$storeful" = 0 ] || store_finish
  pyx report "${PYARGS[@]}" swap --extra "$LOCK_EXTRA"
}

do_note_config() {  # right after the prompt's Step 5: record the merged config.yaml, so a rollback accepts it
  acquire_lock
  [ -f "$journal" ] || die no_journal "no update is recorded in $journal; run stage and swap first"
  jload
  [ "$(jfield format)" = 1 ] || die journal_unreadable "update.json has format '$(jfield format)', not 1"
  [ "$(jfield phase)" = swapped ] || die not_swapped "the recorded update is in phase '$(jfield phase)', not swapped; note-config runs after swap, right after Step 5"
  local cfg="$root/openspec/config.yaml" sum
  [ -f "$cfg" ] || die config_missing "$cfg does not exist; run Step 5 first"
  sum=$(pyx sha-file "$cfg")
  jset_field config_sha "\"$sum\""
  jflush
  pyx report "${PYARGS[@]}" note-config --extra "{\"config\": \"$cfg\", \"sha256\": \"$sum\"}"
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
  note-config) do_note_config ;;
  finish) do_finish ;;
  recover) do_recover ;;
  *) usage "unknown subcommand $sub (plan, stage, swap, note-config, finish, recover)" ;;
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
VALUE_OPTS = ("code", "root", "download", "ref", "error", "message", "extra", "plan", "mode")
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


def yaml_setting(text, keys):
    """The scalar at `keys` ((k,) or (parent, k)) in a settings file; a comment and quotes are dropped. Only the shapes
    of openspec/specwright.yaml are read: a top-level key, or a key one block down."""
    inside = len(keys) == 1
    for line in text.splitlines():
        bare = line.strip()
        if not bare or bare.startswith("#"):
            continue
        indented = line[0] in " \t"
        if not indented:
            m = re.match(r"^([A-Za-z_][\w-]*):[ \t]*(.*)$", line)
            if not m:
                inside = len(keys) == 1
                continue
            inside = len(keys) == 2 and m.group(1) == keys[0]
            name, value = m.group(1), m.group(2)
            if len(keys) == 1 and name == keys[0]:
                return re.sub(r"[ \t]+#.*$", "", value).strip().strip("'\"") or None
        elif inside and len(keys) == 2:
            m = re.match(r"^[ \t]+" + re.escape(keys[1]) + r":[ \t]*(.*)$", line)
            if m:
                return re.sub(r"[ \t]+#.*$", "", m.group(1)).strip().strip("'\"") or None
    return None


def code_top(o):
    """The code checkout's git toplevel (the --code directory when it is not in a repo)."""
    rc, out = git(o["code"], "rev-parse", "--show-toplevel")
    return Path(out.decode("utf-8", "replace").strip() if rc == 0 and out.strip() else o["code"]).resolve()


def is_store(o):
    """True when the planning root lives in a git repo other than the code checkout's (a planning store)."""
    top, _ = planning_repo(o)
    return top is not None and top != code_top(o)


def configured_main(o):
    """The main branch named in the code repo's openspec/specwright.yaml: planning_store.main_branch for a store,
    else main_branch. None when unset."""
    try:
        text = (Path(o["code"]) / "openspec" / "specwright.yaml").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return yaml_setting(text, ("planning_store", "main_branch") if is_store(o) else ("main_branch",))


def planning_main(top, o):
    """The planning main: the configured one first, else origin/main, main, origin/master, master. The ref
    (origin/<main> when present, else the local branch), or None."""
    configured = configured_main(o)
    for c in ([configured] if configured else []) + ["main", "master"]:
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
    main = planning_main(top, o)
    archived =git_lines(top, "ls-tree", "--name-only", f"{main}:{planning}/changes/archive") if main else []

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


def own_change(o, name, branches):
    """True when this project's code repo has a local branch <prefix>/<name> for one of the gate's prefixes."""
    return any(f"{p}/{name}" in branches for p in PREFIXES)


def inflight_entries(o, to, schema_dir, role="none"):
    """(entries, warnings) for a workflow update: every change in flight, validated against schema_dir in its own
    scratch root under <download>/.update-scratch/ (removed on the way out). An entry has name, source, status
    (validated | not on specwright | invalid | other project), validated_against and, when invalid, error. In a store
    (role owner or claim) a change this project has no branch for belongs to another project: status other project,
    not validated."""
    items, warnings = collect(o)
    base = Path(o["download"]) / SCRATCH
    entries = []
    branches = set(git_lines(code_top(o), "for-each-ref", "--format=%(refname:short)", "refs/heads/")) if role in ("owner", "claim") else set()
    try:
        for i, it in enumerate(items, 1):
            scratch = base / f"{i}-{it['name']}"
            e = {"name": it["name"], "source": it["source"], "status": "validated", "validated_against": to}
            if role in ("owner", "claim") and not own_change(o, it["name"], branches):
                e.update({"status": "other project", "validated_against": None})
                entries.append(e)
                continue
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


# --- planning stores (design D5) ------------------------------------------------------------------------------------

def normalise_origin(url):
    """`host/owner/repo` from an origin fetch URL: scheme, userinfo, port, `.git` and a trailing dot on the host are
    dropped. None for an origin with no host (a local path, file://)."""
    u = url.strip()
    m = re.match(r"^[A-Za-z][A-Za-z0-9+.\-]*://(?:[^/@]*@)?([^/:]+)(?::\d*)?/(.+)$", u)
    if not m and "://" not in u and not re.match(r"^([A-Za-z]:[\\/]|[/.~])", u):
        m = re.match(r"^(?:[^/@:\s]+@)?([^/:\s]{2,}):(.+)$", u)  # scp-like: git@host:owner/repo.git
    if not m:
        return None
    host, path = m.group(1).rstrip("."), re.sub(r"\.git$", "", m.group(2).strip("/"))
    return f"{host}/{path}" if host and path else None


def owner_id(o):
    """This project's id: its origin fetch URL normalised to host/owner/repo, else path:<code toplevel>."""
    rc, out = git(o["code"], "remote", "get-url", "origin")
    if rc == 0:
        n = normalise_origin(out.decode("utf-8", "replace"))
        if n:
            return n
    return "path:" + code_top(o).as_posix()


def record_path(o):
    return Path(o["root"]) / "openspec" / ".specwright" / "STORE"


def read_record(path):
    """(record, problem): record {version, owner}, None when the file is absent or unreadable; problem is the text."""
    path = Path(path)
    if not path.is_file():
        return None, None
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r", "")
    v = re.search(r"^version:[ \t]*(\S+)[ \t]*$", text, re.M)
    w = re.search(r"^owner:[ \t]*(\S.*?)[ \t]*$", text, re.M)
    missing = [k for k, m in (("version", v), ("owner", w)) if not m]
    if missing:
        return None, f"{path.as_posix()} has no {' and no '.join(missing)}"
    if not SEMVER.match(v.group(1)):
        return None, f"{path.as_posix()} has the version {v.group(1)!r}, not MAJOR.MINOR.PATCH (field version)"
    return {"version": v.group(1), "owner": w.group(1)}, None


def store_info(o):
    """{role, record, problem, id}: role none (repo-local), claim (no STORE), owner (STORE names this project),
    other, or None when the STORE record is unreadable (problem says why)."""
    if not is_store(o):
        return {"role": "none", "record": None, "problem": None, "id": None}
    rec, problem = read_record(record_path(o))
    me = owner_id(o)
    role = None if problem else "claim" if rec is None else "owner" if rec["owner"] == me else "other"
    return {"role": role, "record": rec, "problem": problem, "id": me}


def highest_tag(o, major, minor):
    """(tag, problem): the highest vMAJOR.MINOR.PATCH tag on the download's origin (git ls-remote --tags)."""
    rc, out = git(o["download"], "remote", "get-url", "origin")
    if rc != 0 or not out.strip():
        return None, "the download has no origin to list tags from"
    try:
        r = subprocess.run(["git", "ls-remote", "--tags", "--refs", out.decode("utf-8", "replace").strip()], capture_output=True,
                           timeout=60, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"git ls-remote failed: {e}"
    if r.returncode != 0:
        return None, "git ls-remote --tags failed: " + (r.stderr.decode("utf-8", "replace").strip().splitlines() or ["no output"])[0]
    best = None
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        m = re.search(r"refs/tags/v(\d+)\.(\d+)\.(\d+)$", line.strip())
        if m and (int(m.group(1)), int(m.group(2))) == (major, minor):
            v = tuple(int(x) for x in m.groups())
            best = v if best is None or v > best else best
    return ("v" + ".".join(map(str, best)) if best else None), (None if best else f"no tag v{major}.{minor}.* exists")


def gate_lock_path(o):
    """<store git common dir>/specwright-gate.lock (the lock of skills/specwright-branch), None outside a repo."""
    top, _ = planning_repo(o)
    if top is None:
        return None
    rc, out = git(top, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if rc != 0 or not out.strip():
        return None
    return (top / out.decode("utf-8", "replace").strip()).resolve().joinpath("specwright-gate.lock").as_posix()


def trees_equal(a, b):
    a, b = Path(a), Path(b)
    if not (a.is_dir() and b.is_dir()):
        return False
    files = lambda d: {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}
    return files(a) == files(b)


def store_main_name(o, top):
    """The store's main branch (a local branch name): the configured one, else main, else master; None when none exists."""
    cfg = configured_main(o)
    if cfg:
        return cfg
    for c in ("main", "master"):
        if git(top, "rev-parse", "--verify", "-q", f"refs/heads/{c}")[0] == 0:
            return c
    return None


def dirty_paths(top):
    """The paths `git status --porcelain` lists in the store (every untracked file by name)."""
    rc, out = git(top, "status", "--porcelain", "-z", "--untracked-files=all")
    parts, found, i = out.decode("utf-8", "replace").split("\0"), [], 0
    while i < len(parts):
        e, i = parts[i], i + 1
        if len(e) < 4:
            continue
        if e[0] in "RC":
            i += 1  # the original path follows
        found.append(e[3:])
    return found


def under(path, prefixes):
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def rel_to(top, p):
    try:
        return Path(p).resolve().relative_to(top).as_posix()
    except ValueError:
        return None


def store_busy_reason(o, top, allowed):
    """Why the store is not free (design D5), or None: it must be on its main, and `git status` may list only paths
    for which allowed(path) is true. Returns (reason, branch)."""
    branch = git(top, "branch", "--show-current")[1].decode("utf-8", "replace").strip()
    main = store_main_name(o, top)
    if not branch:
        return "the store has a detached HEAD", branch
    if branch != main:
        return f"the store is on {branch}, not on its main ({main or 'no main branch found'})", branch
    dirty = [p for p in dirty_paths(top) if not allowed(p)]
    if dirty:
        shown = ", ".join(dirty[:5]) + (f" and {len(dirty) - 5} more" if len(dirty) > 5 else "")
        return f"the store has uncommitted changes: {shown}", branch
    return None, branch


def written_by_update(j, top):
    """allowed(path) for a recovery run: the update's staging, the schema it swapped in (each file as the manifest has
    it), the STORE it wrote and the config.yaml the prompt merged and noted, each still with the recorded content."""
    groups = {g["id"]: g for g in j["groups"]}
    staging = [p for p in (rel_to(top, g["staging"]) for g in j["groups"]) if p]
    schema = groups.get("schema")
    schema_rel = rel_to(top, Path(schema["dir"]) / "specwright") if schema else None
    manifest = {m["path"]: m["sha256"] for m in j["manifest"] if m["group"] == "schema"}
    record_rel = rel_to(top, j["store_record"])
    config = Path(j["root"]) / "openspec" / "config.yaml"
    config_rel = rel_to(top, config)
    want_record = f"version: {j['to']}\nowner: {j['owner_id']}\n"
    prev = Path(j["store_staging"]) / "prev" / "config.yaml" if j.get("store_staging") else None
    config_ok = {x for x in (j.get("config_sha"), sha(prev.read_bytes()) if prev and prev.is_file() else None) if x}

    def allowed(path):
        if under(path, staging):
            return True
        if schema_rel and under(path, [schema_rel]):
            sub = "specwright/" + path[len(schema_rel) + 1:]
            f = top / path
            return sha(f.read_bytes()) == manifest.get(sub) if f.is_file() else sub not in manifest
        if path == record_rel:
            f = top / path
            return f.is_file() and f.read_text(encoding="utf-8", errors="replace").replace("\r", "") == want_record
        if path == config_rel:
            f = top / path
            return f.is_file() and sha(f.read_bytes()) in config_ok
        return False
    return allowed


def cmd_store_check(o, pos):
    """Under the store gate lock (design D5 steps 1-2). --mode swap: STORE must not name another owner now, and the
    store must be free (on its main, nothing in `git status` but this update's staging); a busy store allows a patch
    whose staged schema is byte-identical (prints mode code-only). --mode rollback: the recovery rule, STORE must be
    what this update wrote and the store may hold only what the journal records. Exit 0 prints mode; 1 is a stop."""
    j = load_journal(o)
    top, _ = planning_repo(o)
    doc = base_doc(o, False)

    def stop(code, message):
        doc.update({"error": code, "message": message})
        emit(doc, 1)

    me, mode = j["owner_id"], o.get("mode", "swap")
    rec, problem = read_record(j["store_record"])
    if problem:
        stop("store_record_unreadable", f"the store's record is unreadable: {problem}")
    if mode == "swap":
        if rec is not None and rec["owner"] != me:
            if j["role"] == "claim":
                stop("store_claimed", f"the store was claimed by {rec['owner']} (version {rec['version']}) after this update was planned: "
                     f"only the owner replaces its schema, and nothing was written. Rerun the update to plan it again")
            stop("store_owner_changed", f"the store's schema is now owned by {rec['owner']} (version {rec['version']}), not by {me}; "
                 f"nothing was written. Rerun the update to plan it again")
        staging = [p for p in (rel_to(top, g["staging"]) for g in j["groups"]) if p]
        reason, _ = store_busy_reason(o, top, lambda p: under(p, staging))
        if reason is None:
            emit({"ok": True, "mode": "write"})
        if not workflow_update(j["from"], j["to"]):
            sg = next(g for g in j["groups"] if g["kind"] == "schema")
            if trees_equal(Path(sg["staging"]) / "new" / "specwright", Path(sg["dir"]) / "specwright"):
                emit({"ok": True, "mode": "code-only", "reason": reason})
        stop("store_busy", f"{reason}. A store schema is swapped only on a free store: finish that change first (merge or archive "
             f"it, so the store is back on its main with nothing uncommitted), then rerun the update. Nothing was written")
    if rec is not None and rec["owner"] != me:
        stop("store_owner_changed", f"the store's schema is now owned by {rec['owner']}, not by {me}; the swapped state and the journal are kept")
    if j.get("store_state") == "written" and (rec is None or rec["version"] != j["to"]):
        stop("store_owner_changed", f"the store's record no longer reads version: {j['to']} owned by {me}; the swapped state and the journal are kept")
    reason, _ = store_busy_reason(o, top, written_by_update(j, top))
    if reason:
        stop("store_busy", f"{reason}. The rollback stops before any rename and the swapped state and the journal are kept; "
             f"the store stays on {j['to']}. Finish that change, then run the rollback again")
    emit({"ok": True, "mode": "rollback"})


def cmd_journal_drop_store(o, pos):
    """Write to pos[0] the journal without the store targets and the STORE record (a busy store, schema unchanged)."""
    j = load_journal(o)
    j["groups"] = [g for g in j["groups"] if g["kind"] != "schema"]
    j["targets"] = [t for t in j["targets"] if t["gid"] != "schema"]
    j["manifest"] = [m for m in j["manifest"] if m["group"] != "schema"]
    j["store_state"] = "current"
    Path(pos[0]).write_text(format_journal(j), encoding="utf-8", newline="\n")


def cmd_sha_file(o, pos):
    print(sha(Path(pos[0]).read_bytes()))


def store_report(o, j):
    """The `store` object of the swap document: what happened to the store, for the prompt's Steps 5 and 7."""
    role = j.get("role")
    if role in (None, "none"):
        return None
    state, me, top = j.get("store_state"), j.get("owner_id"), planning_repo(o)[0]
    r = {"role": role, "id": me, "owner": j.get("store_owner"), "version": j.get("store_version"),
         "written": state == "written", "claimed": role == "claim" and state == "written"}
    if state == "written":
        r["owner"], r["version"] = me, j["to"]
        sg = next((g for g in j["groups"] if g["kind"] == "schema"), None)
        r["uncommitted"] = [x for x in (rel_to(top, j["store_record"]), rel_to(top, Path(sg["dir"]) / "specwright") if sg else None) if x]
        if r["claimed"]:
            r["message"] = (f"{me} now owns the store's schema (version {j['to']}); STORE and the new schema are left uncommitted in "
                            f"the store, commit them there")
        else:
            r["message"] = f"the store's schema and STORE now read {j['to']} (owner {me}); they are left uncommitted in the store"
    elif state == "current":
        r["message"] = "store schema already current"
    elif role == "other":
        r["message"] = f"store config managed by owner {j.get('store_owner')}"
    else:
        r["message"] = "the store schema has not been swapped"
    return r


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


def build_groups(o, refusals, with_schema=True):
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
    if with_schema:  # another project's update leaves the store's schema alone
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
    info = store_info(o)
    role, rec = info["role"], info["record"]
    if info["problem"]:
        refusals.append({"code": "store_record_unreadable", "message": f"the store's record is unreadable: {info['problem']}. "
                         "Fix or remove it, then rerun the update; nothing was written"})
    if role == "other" and to:
        sv = vtuple(rec["version"])
        if vtuple(to)[:2] != sv[:2]:
            tag, why = highest_tag(o, sv[0], sv[1])
            named = f"the highest {sv[0]}.{sv[1]} release is {tag}" if tag else f"the highest {sv[0]}.{sv[1]} release could not be named ({why})"
            refusals.append({"code": "store_version", "message": (
                f"the store records version {rec['version']} and its schema is owned by {rec['owner']}, so this project's update to {to} "
                f"would leave that version, and only the owner replaces the store's schema. Nothing was written. {named[0].upper()}{named[1:]}: "
                f"update this project to {tag or 'it'} instead, or have {rec['owner']} update the store first")})
    groups, orphans = build_groups(o, refusals, with_schema=role != "other")
    inflight, checked = [], False
    if check and to and not refusals and workflow_update(inst, to) and role != "other":
        checked = True
        entries, found = inflight_entries(o, to, Path(o["download"]) / "schemas" / "specwright", role)
        warnings.extend(found)
        for e in entries:
            if e["status"] == "other project":
                refusals.append({"code": "other_project_change", "change": e["name"], "ref": e["source"],
                                 "message": f"change {e['name']} ({e['source']}) in flight in the store belongs to another project (this project "
                                            f"has no local branch <prefix>/{e['name']}), so the store's schema is not replaced until it is archived"})
            elif e["status"] == "invalid":
                where = "" if e["source"] == "working tree" else f" on {e['source']}"
                refusals.append({"code": "change_invalid", "change": e["name"], "ref": None if not where else e["source"],
                                 "message": f"change {e['name']}{where or ' (working tree)'} fails validation against {to}: {e['error']}"})
            else:
                inflight.append(e)
    doc = base_doc(o, not refusals)
    doc.update({"from": inst, "to": to, "ref": o.get("ref"), "kind": kind_of(inst, to) if to else None, "role": role,
                "targets": [{"group": g["id"], "kind": g["kind"], "dir": g["dir"], "name": it["name"], "installed": it["installed"]}
                            for g in groups for it in g["items"]],
                "orphans": orphans, "journal": journal, "inflight_checked": checked, "inflight": inflight,
                "refusals": refusals, "warnings": warnings})
    if role in ("claim", "owner", "other"):
        doc["store"] = {"root": o["root"], "version": rec["version"] if rec else None, "owner": rec["owner"] if rec else None, "id": info["id"]}
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


def format_journal(d):
    """The journal text: the scalar members one per line, then groups, targets and the manifest with one entry per line,
    so that the shell can change a state with plain string work (the swap writes the journal before every rename)."""
    lists = ("groups", "targets", "manifest")
    lines = ["{"] + [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}," for k, v in d.items() if k not in lists]
    for key in lists:
        lines.append(f'  "{key}": [')
        lines.append(",\n".join("    " + json.dumps(x, ensure_ascii=False) for x in d[key]))
        lines.append("  ]" + ("" if key == lists[-1] else ","))
    lines.append("}")
    return "\n".join(lines) + "\n"


def cmd_journal_new(o, pos):
    """Write the new journal text to the path in pos[0]. One group, target and manifest entry per line, so that the
    shell can change a state with sed (the swap writes the journal before every rename)."""
    doc, groups = make_plan(o)
    if not doc["ok"]:
        emit(doc, 1)
    plan = json.loads(o["plan"]) if o.get("plan") else {}
    inflight = {"checked": plan.get("inflight_checked", False), "changes": plan.get("inflight", []),
                "warnings": [w for w in plan.get("warnings", []) if w.get("code") == "in_flight_elsewhere"]}
    role = doc["role"]
    storeful = role in ("owner", "claim")
    store = doc.get("store") or {}
    head = {"format": 1, "from": doc["from"], "to": doc["to"], "ref": o.get("ref"), "kind": doc["kind"], "role": role,
            "code": o["code"], "root": o["root"], "inflight": inflight,
            "owner_id": store.get("id"), "store_owner": store.get("owner"), "store_version": store.get("version"),
            "store_record": record_path(o).as_posix() if storeful else None,
            "store_lock": gate_lock_path(o) if storeful else None,
            "store_staging": next((g["staging"] for g in groups if g["kind"] == "schema"), None) if storeful else None,
            "store_state": "pending" if storeful else "none", "token": None, "prev_config": None, "prev_store": None,
            "config_sha": None, "phase": "staging"}
    groups_j = [{k: v for k, v in g.items() if k != "items"} for g in groups]
    targets = [{"gid": g["id"], "name": it["name"], "type": it["type"], "dir": g["dir"], "staging": g["staging"],
                "installed": it["installed"], "state": "pending"} for g in groups for it in g["items"]]
    journal = {**head, "groups": groups_j, "targets": targets, "manifest": expected_manifest(groups)}
    Path(pos[0]).write_text(format_journal(journal), encoding="utf-8", newline="\n")


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
    entries, _ = inflight_entries(o, j["to"], schema, j.get("role") or "none")
    was, now = {entry_key(e): e for e in rec.get("changes", [])}, {entry_key(e): e for e in entries}
    diffs = []
    for k, e in now.items():
        if k not in was:
            if e["status"] == "invalid":
                diffs.append(f"{e['name']} ({e['source']}) fails validation against {j['to']}: {e['error']}")
            elif e["status"] == "other project":
                diffs.append(f"{e['name']} ({e['source']}) belongs to another project and is in flight in the store")
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
        doc["store_written"] = j.get("store_state") == "written"
        store = store_report(o, j)
        if store:
            doc["store"] = store
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
