#!/usr/bin/env bash
# Decisions for a change that lives in two repos (code + planning store): which
# PRs are expected, how they link, what watch does, and how an interrupted
# feedback pass resumes. Every subcommand prints ONE JSON line.
#
# Every subcommand runs `sw pr <sub> --args-stdin` through the matching project's sw (ADR 0028), found with
# sw-path.sh (no sw: one `sw_missing` JSON document, exit 1), including missing/unknown calls. The Python probe stays first:
# without Python 3.8+ every call is exit 2 `no_python`. Bash/Python handoffs remain until native-cli-retire-scripts.
# Usage: bash pr-pair.sh [--project <code-checkout>] <subcommand> [options]
#   identity <dir>                    fetch URL + every push URL of origin -> owner/name
#   context --code <dir> [--store <dir>] [--only repos] [--branch b [--after-merge]]
#                                     per-repo login, main, validate, reviewers (role, timeout, request, report), reviewer_config,
#                                     merge_ready (specwright.yaml + planning_store:); settle (pr.settle in seconds, default 300, strictly
#                                     <int><s|m|h>, 1m to 1h);
#                                     reviewer_config is the path of the repo's reviewer set written as canonical JSON
#                                     {"format":2,"reviewers":[{login,role,timeout,report}]} (sorted keys and logins, no request) to
#                                     <state dir>/reviewers/<sha256 of the bytes>.json, else <system temp>/specwright/reviewers/ when the
#                                     state dir is unwritable (null only if neither is); equal settings give the same file, so the name
#                                     is the digest of the rules;
#                                     settings_problem (only when set; the first one, never an exit): the strict reader's `line N: why`
#                                     for the whole settings file, else a bad pr.settle, a reviewer `report` that is not a mapping of
#                                     strings, or more than 20 reviewers in a set (too_many_reviewers), each naming its key;
#                                     merge (user|agent), merge_method, delete_branch (bad value = exit 2 bad_setting;
#                                     --only repos skips that check, for callers that never merge, such as vcs.sh)
#                                     With `vcs: gitbutler` the settings must be those the change branch committed (the shared work tree
#                                     can hold a sibling branch's or an unassigned edit): --branch b compares git hash-object
#                                     --path=openspec/specwright.yaml <work-tree file> (the repo's clean and eol filters apply, so CRLF
#                                     checkouts compare equal) with refs/heads/b:openspec/specwright.yaml. A difference, or the file on one
#                                     side only, is exit 1 settings_not_pinned (names the file and the ref; commit the edit on b); a git
#                                     failure is exit 1 git_error. --after-merge --branch b, for cleanup after its pull and delete,
#                                     compares with the tip of refs/heads/b while that branch exists (pull skipped or left applied), else
#                                     with gitbutler.project.targetRef; its message names that ref and says to run `but pull` or undo the
#                                     work-tree edit. A merge-settings call (anything but --only repos) without --branch is exit 2 usage
#                                     on GitButler. GitButler here means `vcs: gitbutler` in the work-tree file or a GitButler-managed
#                                     repo (gitbutler/ in the common git dir and gitbutler.project.targetRef set, as vcs.sh decides),
#                                     so an unpinned edit of the vcs line cannot turn the check off. Other Git and jj repos (a leftover
#                                     target ref alone included) never pin; they accept and ignore --branch.
#   vcs --code <dir>                  independent backend settings -> {"ok":true,"code":"git|jj|gitbutler","store":"git|jj"};
#                                     absent settings default independently to git; unknown values stop with unknown_vcs; gitbutler is code-repo only and needs finish: pr
#   tier --code <dir>                 cheap_tier.enabled: {"ok": true, "cheap_tier": bool} (true only for a parsed true; anything else
#                                     is false, with a "note" when the value or the section is not true/false/a map). Reads no other
#                                     setting, so a bad pr.merge_method cannot change it; exit 0 for any readable settings file
#   merge --repo o/n --pr N --method merge|squash|rebase --head sha
#                                     one PUT repos/o/n/pulls/N/merge (merge_method, sha), then always a read-back: merged (also when a
#                                     person merged first), refused (reason head_changed on 409, else refused; exit 1) or, when the state
#                                     cannot be read or the PUT got a 5xx, unknown (exit 3). Never a second PUT, auto-merge or a queue call; bad input = exit 2
#   policy --repo o/n --head sha --snapshot code=f [--reviewed-head code=sha] [--store --snapshot store=f --reviewed-head store=sha]
#                                     the merge policy from GitHub, never the work tree: default_branch (repos/o/n), then openspec/specwright.yaml
#                                     read through the contents API at the default branch and at the PR head, both as the run login. Prints
#                                     main and head (pr.merge, pr.merge_method, pr.delete_branch, pr.reviewers; with --store also
#                                     planning_store.reviewers), compared normalized, never as bytes, drift [{key, main, head}] and, from
#                                     main alone: merge, merge_method, delete_branch, merge_ready {code[, store]}, merge_reason, merge_note.
#                                     No file on main is user mode; a bad merge_method/delete_branch on main with merge: agent is exit 2
#                                     bad_setting (a bad head value is only drift). A failed, cut-off or unreadable read (not a file, not
#                                     base64, or YAML the reader would skip or misread: block sequences, anchors, tags, duplicate keys,
#                                     tabs in indentation), or no file at the head, is exit 3 lookup_failed "merge policy unknown:
#                                     <reason>"; a malformed file names its first bad line.
#                                     Also reported.{main,head}.{code[,store]} {ok, missing, head_mismatch, rules_mismatch, snapshot_head, reviewed_head}:
#                                     ok when the snapshot is of that repository's reviewed head (code: --head, or --reviewed-head code= for
#                                     the archive carry-over; store: --reviewed-head store=, required) and every required reviewer of that
#                                     side's authorizing set (store: planning_store.reviewers, else pr.reviewers) is reported in it; a set
#                                     with no required reviewer is never ok. Heads match when equal or one is a prefix of the other.
#                                     rules_mismatch is true when the snapshot's reviewer_config digest differs from the digest of that
#                                     set's config (the wait ran with other rules); then ok is false. Each side's snapshot is checked
#                                     against that side's set; digests are compared, never paths.
#                                     reviewer_config.{main,head}.{code[,store]}: the path of each set's config file, written as for
#                                     `context` (null if no place is writable), for pr-snapshot.sh --reviewer-config. A reviewer's
#                                     report is part of the pr.reviewers value, so a changed rule is drift.
#                                     On main, a bad pr.settle, a reviewer report that is not a mapping of strings (exit 2 bad_setting)
#                                     and more than 20 reviewers in a set (exit 2 too_many_reviewers) stop the call; the head's go to invalid.
#                                     --store without --snapshot store= and --reviewed-head store= is exit 2; an unreadable snapshot exits 2.
#                                     A pr.reviewers that is not a mapping (a string, a list) reads as no reviewers, so it authorizes
#                                     nothing, and is listed in invalid [{side, key, value}]
#   delete-remote --repo o/n --branch b --head sha
#                                     delete the remote branch only when it is still at the full 40-hex merged head and no open PR is
#                                     based on it: deleted | gone (404, or 422 gone meanwhile) | moved (sha) | based_on (prs) |
#                                     kept (DELETE refused, GitHub's message; exit 1); a failed read is unknown (exit 3), nothing deleted
#   discover --repo o/n --branch b [--base main] [--state all|open|closed|merged[,..]]
#                                     every PR from o/n's own branch b, paginated; failure = unknown (exit 3)
#   expected --code <dir> --store <dir> --branch b
#                                     the expected PR set: store (GitHub origin) and code (PR in any state, or commits)
#   ensure-pr --repo o/n --branch b --base main --title t --body-file f
#                                     find the open PR or create it; stops on a wrong base; never edits a description
#   closing-check --repo o/n --pr N   the issues the description's closing lines name vs what GitHub will close
#                                     status match | mismatch | not_default_base (one GraphQL read, then GitHub's rendering of the description read as lines; a failure = unknown, exit 3)
#   closed-check --repo o/n --pr N --repos o/n[,o/n] [--login o/n=L ...]
#                                     at cleanup: which issues the merged PR's closing lines name are still open (lines read from GitHub's rendering)
#                                     status merged | not_merged | not_default_base; open, reopened, closed, outside (a failed read = unknown, exit 3)
#                                     --login: the login that reads o/n when it is not the one the call runs as
#   link --repo o/n --pr N --kind store|code --peer-url URL [--login L]
#                                     one marker comment <!-- specwright:link KIND URL -->; edits its own on a new peer
#   pair-state --code d --store d --branch b [--snapshot code=f] [--snapshot store=f] [--dropped id@rev]...
#              [--carry-over code|store]...
#                                     watch action: ship | wait | ready | split_hand_off | cleanup | no_watch;
#                                     --carry-over: that side is an archive head whose reviewers' reports carry over
#   rounds --code d [--store d] --branch b
#                                     highest Feedback-Round across both branches (+ legacy subject count, unpushed)
#   pass write --code d [--store d] --code-repo o/n --change c --intent file [--store-prefix openspec]
#   pass plan --code d [--store d] --code-repo o/n --change c --snapshot code=f [--snapshot store=f] [--owner id]
#   pass done --code d [--store d] --code-repo o/n --change c --snapshot code=f [--snapshot store=f] --owner id
#   pass adopt --code d [--store d] --code-repo o/n --change c --owner new-id --from shown-id|none
#                                     the intent record of a feedback pass (write returns the owner id); the evidence-based
#                                     resume plan (owned: true|false|null); delete, by its owner; hand over, naming the owner shown
#                                     (no --store: a repo-local change, code repo only)
#                                     plan's rerequest row counts a request done when it was posted at or after the cutoff:
#                                     the head's push time (cutoff_source push), else the time a snapshot first saw the head
#                                     (first_seen), else, only with no such record, when the record was written (pass_written;
#                                     written_at, or the owner's at in an older record); none = no cutoff, the row stays todo
#   cleanup-plan --code d --store d --branch b
#                                     post-merge commands per repo whose expected PR is MERGED: checkout, a pull fenced as
#                                     that repo's login (bash <as.sh> <login> git pull --ff-only), then
#                                     branch-check (--head: the merged PR's head); `delete` (git branch -D) runs only on delete: true
#   branch-check --dir d --branch b --main m [--head sha]
#                                     delete true when the branch tip is on main (on_main) or is the merged head or an ancestor of
#                                     it (pr_head); else false with reason lacking | head_unknown and the commits "lacking" (sha,
#                                     subject). Read-only, no network; a git error stops (ok false, exit 1)
# Exit: 0 answered, 1 stop (the JSON has "error" and "message"; an unexpected failure is
#       error "internal_error"), 2 usage or missing input,
#       3 GitHub state unknown (a lookup failed; never read it as "no PR").
# Every gh call names its repository (--repo or repos/<o>/<n>/...) and runs with GH_REPO unset, so an
# inherited override cannot redirect a store lookup to the code repo. Wrap with as.sh to pin the
# GitHub identity, started inside the repository it acts on (its header scrub is per working directory).
# Needs bash, git, gh 2.40+ and Python 3.8+.
set -euo pipefail

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
[ -n "$py" ] || { echo '{"ok":false,"error":"no_python","message":"pr-pair.sh needs python 3.8+"}'; exit 2; }
unset GH_REPO
# Absolute script directory for native helper calls from any working directory
# (-m: forward slashes both Git Bash and native Windows tools accept).
PR_PAIR_DIR=$(cd "$(dirname "$0")" && pwd -P)
if command -v cygpath >/dev/null 2>&1; then PR_PAIR_DIR=$(cygpath -m "$PR_PAIR_DIR"); fi
export PR_PAIR_DIR

# All nineteen public entries use the original NUL stdin handoff (ADR 0028).
# Python remains a compatibility prerequisite until native-cli-retire-scripts;
# only its probe and the resolver's JSON diagnostic use it here.
SW_DIR=$PR_PAIR_DIR
SW_BASH=${BASH:-bash}
if command -v cygpath >/dev/null 2>&1; then SW_BASH=$(cygpath -w "$SW_BASH"); fi

# Binary selection never changes the target cwd or login. Explicit selection
# wins over --code/cwd discovery, and never falls back to another project.
if [ "${1:-}" = --project ]; then
  if [ $# -lt 2 ] || [ -z "${2:-}" ]; then
    echo '{"ok":false,"error":"usage","message":"--project needs a nonempty code checkout"}'
    exit 2
  fi
  proj=$2
  shift 2
  if [ "${1:-}" = --project ]; then
    echo '{"ok":false,"error":"usage","message":"only one leading --project is allowed"}'
    exit 2
  fi
else
  # Existing discovery: --code when it names a directory, else cwd, then up to
  # its first .git entry. identity's positional target is never a binary project.
  dir=
  prev=
  for a in "$@"; do
    if [ "$prev" = --code ] && [ -d "$a" ]; then dir=$(cd "$a" && pwd -P); break; fi
    prev=$a
  done
  [ -n "$dir" ] || dir=$(pwd -P)
  proj=$dir
  while [ ! -e "$proj/.git" ] && [ "$proj" != / ]; do proj=$(dirname "$proj"); done
  [ -e "$proj/.git" ] || proj=$dir
fi

# Resolve before command usage too: no Python workflow or usage fallback.
if ! sw=$("$BASH" "$SW_DIR/sw-path.sh" --code "$proj" 2>/dev/null); then
  err=$("$BASH" "$SW_DIR/sw-path.sh" --code "$proj" 2>&1 >/dev/null || true)
  printf '%s' "$err" | "$py" -I -X utf8 -c 'import json, sys; print(json.dumps({"ok": False, "error": "sw_missing", "message": sys.stdin.read().rstrip("\r\n")}, ensure_ascii=False))'
  printf '%s\n' "$err" >&2
  exit 1
fi

case "${1:-}" in
  identity|vcs|tier|context|policy|discover|expected|ensure-pr|closing-check|closed-check|link|pair-state|rounds|pass|cleanup-plan|branch-check|merge|delete-remote|item-issues)
    sub=$1
    shift
    ;;
  *)
    # Internal invalid-call dispatch retains all the original argument records.
    sub=pair
    ;;
esac
exec "$sw" pr "$sub" --args-stdin < <(printf '%s\0' "$SW_DIR" "$SW_BASH" "$@")
