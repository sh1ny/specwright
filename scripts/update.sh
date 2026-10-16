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
#            role (none: no store handling yet), targets (every directory or file that stage will replace), orphans
#            (installed specwright-* names with no downloaded counterpart; never touched), journal (a pending
#            update.json: {from, to, phase, format} or null), refusals and warnings. Writes nothing outside
#            <download>/.update-scratch/ (nothing at all today). A refusal is exit 1, error "refused".
#   stage    copies every new skill directory, agent file and the schema into a staging directory beside its target
#            (D2): <parent>/.specwright-update-<basename>/new/. Agent files carry the user's `model:` line over.
#            Writes the journal (format 1) first, verifies the staged copy against a SHA-256 manifest and stops with
#            error verification_failed (naming each file, staging and journal removed) when a file differs. Installed
#            files are untouched. Refuses while a journal is pending (run recover first).
#   swap     re-verifies the staged copy, then replaces each target with two renames: target -> old/<name>, then
#            new/<name> -> target. The journal records each step before it runs. Prints store_written (false:
#            this script never writes a store) and a restart notice. Rerunning after an interruption goes on from
#            the journal and the disk.
#   finish   once VERSION reads the target version (the prompt's Step 7 stamp): removes old/, the staging directories
#            and the journal. Rerunning it is safe.
#   (recover resumes or rolls back a pending journal; it is not part of this script yet.)
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
[ -n "$sub" ] || usage "a subcommand is required: plan, stage, swap or finish"
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

# --- subcommands ------------------------------------------------------------------------------------------------

do_plan() { pyx plan "${PYARGS[@]}"; }

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
  pyx journal-new "${PYARGS[@]}" "$jtmp"
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
  fi
  [ "$phase" = swapped ] || jwrite_phase swapping
  local l gid name type dir staging state new old tgt
  local made=" "  # directories already created in this run
  local re='^    \{"gid": "([^"]*)", "name": "([^"]*)", "type": "([^"]*)", "dir": "([^"]*)", "staging": "([^"]*)", "installed": (true|false), "state": "([a-z-]+)"\}'
  local targets=()
  for l in "${JL[@]}"; do
    if [[ "$l" == '    {"gid": '* ]]; then
      [[ "$l" =~ $re ]] || die journal_unreadable "update.json has a target line this script cannot read"
      targets+=("${BASH_REMATCH[1]}|${BASH_REMATCH[2]}|${BASH_REMATCH[3]}|${BASH_REMATCH[4]}|${BASH_REMATCH[5]}|${BASH_REMATCH[7]}")
    fi
  done
  for l in "${targets[@]}"; do
    IFS='|' read -r gid name type dir staging state <<< "$l"
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
  recover) die not_implemented "recover is not part of this version of update.sh" ;;
  *) usage "unknown subcommand $sub (plan, stage, swap, finish)" ;;
esac
exit "$?"

: <<'PYSRC_EOF'
#---PYSRC---
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(newline="\n")  # no CRLF on Windows: the shell reads these lines
INTERFACE = 1
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
STATE_REL = "openspec/.specwright"
VALUE_OPTS = ("code", "root", "download", "ref", "error", "message", "extra")


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


def make_plan(o):
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
    doc = base_doc(o, not refusals)
    doc.update({"from": inst, "to": to, "ref": o.get("ref"), "kind": kind_of(inst, to) if to else None, "role": "none",
                "targets": [{"group": g["id"], "kind": g["kind"], "dir": g["dir"], "name": it["name"], "installed": it["installed"]}
                            for g in groups for it in g["items"]],
                "orphans": orphans, "journal": journal, "refusals": refusals, "warnings": warnings})
    if refusals:
        doc.update({"error": "refused", "message": refusals[0]["message"], "unchanged": True})
    return doc, groups


def cmd_plan(o, pos):
    doc, _ = make_plan(o)
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
    head = {"format": 1, "from": doc["from"], "to": doc["to"], "ref": o.get("ref"), "kind": doc["kind"], "role": "none",
            "code": o["code"], "root": o["root"]}
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
