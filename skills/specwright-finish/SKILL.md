---
name: specwright-finish
description: "MANDATORY after the OpenSpec archive workflow completes: /opsx:archive, /opsx:bulk-archive, openspec-archive-change, `openspec archive`, or the user asks to archive/finish a change. Commits the archive move, then merges locally (finish: local) or pushes to the PR (finish: pr). Also handles 'the PR was merged' cleanup."
metadata:
  version: 0.1.13
user-invocable: false
allowed-tools: Bash(git *) Bash(openspec *)
---

# Specwright Finish

Start only after the vanilla archive workflow reports success (for bulk archive: after all of it). If it failed, do nothing. Then resolve the **Planning repo** (below); a stop there writes nothing.

Commit type: the branch prefix, except `bugfix` → `fix`. Archive paths, in the planning repo: `<P>/changes/<change-name>/` (now removed), `<P>/changes/archive/<archived-name>/`, and for each delta `specs/<capability-path>/spec.md` inside the archived change, the main spec `<P>/specs/<capability-path>/spec.md` it updated or created - by file, never the whole `<P>/specs/` directory. Other files are the user's: never stage them.

## Resume

Applies when the change directory is gone and finish runs again: the user asks to finish it, or the archive workflow reports the change already archived. Resolve the **Planning repo** first. On any branch, a repo where A (below) is found resumes here instead of running steps 1-3. Never repeat a done step.

For each repo of the change (repo-local: one; store-backed: the store, then the code repo), find `<branch>` from `<main>`: `<prefix>/<change-name>` by the prefix rule of `specwright-branch` step 6, else a local `chore/archive-<change-name>`, else the one local branch matching `*/<change-name>`; several candidates → list them and ask. Then read three facts:
- **A** - an archive commit: a subject matching `^[a-z]+\(<change-name>\): archive change$` in `git log --format=%s <main>..<branch>`, or on `<main>`; or, on `<main>`, the archive directory: `git ls-tree -d --name-only <main> -- <P>/changes/archive/` lists `<archived-name>` (the **Archive name** rule), even with no such subject (an archive squash-merged or bulk-archived). `ls-tree` prints full paths, so match the last path component: a change name without a date matches exactly `^\d{4}-\d{2}-\d{2}-<change-name>$`, a dated name the dated name itself, never a substring. The directory is planning repo only (repo-local: the one repo; store-backed: the store) and never gives the code repo an A.
- **M** - the exact subject `merge: <change-name>` in `git log --first-parent --format=%s <main>`, and, when B, the branch tip is on `<main>` (`git merge-base --is-ancestor <branch> <main>`): an archive-recovery branch made after the change merged holds a new archive commit, so the earlier merge does not count for it.
- **B** - `<branch>` exists.

None of A, M, B in any repo → in `pr` mode, first look up each repo's PR (`discover`, below), since a cleanup can delete the branch before main is pulled; for each repo whose newest PR is merged, run `git status --porcelain` before any checkout or pull (any output → stop, list the files and ask the user; check out, pull and merge nothing), then `git checkout <main> && git pull --ff-only` and read the three facts again, then continue with the table. Still none (or `local` mode) → report that no archive of `<change-name>` was found, and do nothing. `git status --porcelain` showing changes under `<P>/changes/<change-name>/` or the archive directory (with A found) → stop, list the files and ask the user; merge nothing. Otherwise continue at the first step not done, per repo. Rows are checked top to bottom, and the first match wins:

| Facts | Next |
|---|---|
| archive paths uncommitted, no A | steps 1-3 in order (branch check and recovery branch, planning-only test, archive commit) |
| A on branch, not M, B, `local` | merge (`## local`) |
| code repo, the newest store A's body has the line `Archive-Scope: store-only` | out of scope: report the code branch and its PR state, touch nothing; the repo counts as done |
| `pr`, the branch's PR merged, B | **After the PR is merged** cleanup, not ship |
| `pr`, the branch's PR merged, not B | only the issues-left-open backstop (`closed-check`, `specwright-pr` **Cleanup after merge**), no branch deletion; repo done. `closed-check` exits 3 → repo not done, report that the backstop did not run |
| M and B | `git checkout <main> && git branch -d <branch>`, no merge. In `pr` mode (reached only with no merged PR, since the merged-PR rows come first: the change was merged locally) `git checkout <main> && git pull --ff-only`, then `[as] bash scripts/pr-pair.sh branch-check --dir <toplevel> --branch <branch> --main <main>` without `--head`, since M already puts the tip on main; `delete: true` → `git branch -D <branch>`, otherwise keep the branch and report its `lacking` commits. No merge, and no `closed-check`: no PR merged |
| M, not B | repo done |
| `local`, A on main through the archive directory, not M, not B | a reused change name can match an older change's archive, so show the directory and the commit that added it (`git log -1 --format='%h %ad %s' --date=short <main> -- <P>/changes/archive/<archived-name>/`) and ask whether it is this change's archive: yes → repo done (another change's merge carried the archive); no → report that this change's archive is not on main and touch nothing |
| code repo with no A, M or B; store done; the store's archive is marked `code_changes: none` | repo done (a planning-only change) |
| code repo with no A, M or B; store done; no such marker | report and ask; touch nothing |
| store done; code branch with commits, code not M, `local` | code merge (`## local` store-backed step 2) |
| store done; code branch without commits | `git checkout <main> && git branch -d <branch>`, no merge |
| `pr`, A on branch, PR not merged | `## pr` ship; push and PR are idempotent |
| `pr`, store done; code branch with commits, code not M, no PR or an open PR | `## pr` ship for the code branch; push and PR are idempotent. Merge nothing, delete nothing |
| `pr`, store done; code branch with commits, its PR closed unmerged | report the closed PR and ask. Merge nothing, delete nothing |

The branch's PR is the `newest` one from `[as] bash scripts/pr-pair.sh discover --repo <owner>/<name> --branch <branch> --base <main>` (no `--state`, so every state counts; the `specwright-pr` conventions), and the rows' "the branch's PR merged" means that newest PR is merged. An older merged PR from the branch with a newer open or closed-unmerged one means the branch name was reused: report both PRs and ask, touch nothing, and never `closed-check` the older PR. This is checked before the table, so a reused branch name never reaches a merged-PR row, a done row or the no-archive report; only when B holds and the newest PR is open do the ship rows apply as usual, since that open PR is the current change's. Report `Nothing to finish - archive is on <main>` only when every repo is done; a backstop `closed-check` exit 3 is not done.

- **Planning-only test:** it runs only before an archive commit. A resume that finds archive paths uncommitted and no A runs steps 1-3 in order, the test included; once A exists, a resume never writes the marker.
- **Store-only recovery:** step 3 writes the body line `Archive-Scope: store-only` when the change is store-backed and the store is on `chore/archive-<change-name>`. Read it from the newest store A: `git log -1 --format=%B <A>`, matching that exact line. When it is there, the code repo is out of scope: no code merge, ship or branch deletion; report the code branch's state and leave it to its own PR or finish. This counts as done for `Nothing to finish`.
- **Planning-only, already finished:** a local finish of a planning-only change deletes the empty code branch and merges nothing, so the code repo shows no A, M or B. The marker's path comes from the store's A: `git show --name-only --format= <A>` lists `<P>/changes/archive/<archived-name>/specwright-change.yaml` when one was written. With the store done, the code repo is done when `git show <main>:<that path>` (in the store) has a line matching `^code_changes:\s*none\s*$`; otherwise report and ask.

## Steps

1. **Branch:** `git branch --show-current`. If the branch's change name differs from the archived change, confirm with the user. On main:
   - No archive changes left uncommitted (the archive already reached main) → **Resume**; report `Nothing to finish - archive is on <main>` only when it finds every repo done.
   - Otherwise (the PR merged before archive ran; normally `specwright-pr` **watch** archives on the PR branch first) → offer `git checkout -b chore/archive-<change-name>`; the uncommitted archive carries over. Continue from step 2 on that branch, or stop if the user declines. Never commit on main.
   - Store-backed: check each repo. The archive lives in the store, so the recovery branch is created there only (`cd "<store toplevel>" && git checkout -b chore/archive-<change-name>`), never a code branch or code PR for it; the code repo stays as it is. Step 3 then marks the archive commit with the body line `Archive-Scope: store-only`, so a later resume leaves the code repo alone. It carries only the archive: the planning-only test below still decides the marker, and step 4 then finishes only the store branch - the code repo's branch and PR go their own way.
2. **Planning-only test** (store-backed only), before the archive commit, with `<prefix>/<change-name>` as the code branch (on a recovery branch, the code repo's local branch ending in `/<change-name>`, if any). The change has code work when any of these holds, and is planning-only otherwise:
   - `git -C "<code toplevel>" log --oneline <main>..<prefix>/<change-name>` lists a commit (an absent branch lists none);
   - `git -C "<code toplevel>" log --first-parent --format=%s <main>` has the exact subject `merge: <change-name>` - this change's own merge, so the code was already merged, as on a recovery branch. A subject that merely contains `(<change-name>): ` is not proof: another change or branch can carry that scope;
   - `pr` mode only: a code PR from that branch into the code main branch exists in any state (a PR into another base, such as `integration`, is not this change's code PR). Parse `<owner>/<repo>` from the code checkout's `git remote get-url origin`, then from the code checkout with `GH_REPO` unset: `[as] gh api --paginate "repos/<owner>/<repo>/pulls?state=all&head=<owner>:<prefix>/<change-name>&per_page=100" --jq '.[] | select(.head.repo.full_name == "<owner>/<repo>" and .base.ref == "<main>") | .number'` (`[as]` as in `specwright-pr`). A non-zero exit means unknown: stop, write no marker and say why. `local` mode skips this lookup.

   Planning-only → write `<P>/changes/archive/<archived-name>/specwright-change.yaml` containing `code_changes: none` and add it to the archive paths. Otherwise never write it, on the change branch or a `chore/archive-<change-name>` branch alike.
3. **Archive commit**, one call in the planning repo (store-backed: start it with `cd "<store toplevel>" && test "$(git branch --show-current)" = <branch> &&`): `git add -- <archive paths> && git commit -F <msgfile> -- <archive paths>` with `<type>(<change-name>): archive change`. Store-backed with the store on `chore/archive-<change-name>`: add the body line `Archive-Scope: store-only` after a blank line (it is written on a first run and on a resume alike). Then `git status --porcelain`: nothing may be left under `<P>/changes/<change-name>/` or the archive directory, and none of the listed spec files (else stop and list it); other leftovers, including other files under `<P>/`, are the user's - list them and continue. Bulk archive of several changes on one branch → one archive commit naming them all.
4. **Finish** per `finish` in `openspec/specwright.yaml` (default `local`). Main branch: `main_branch` setting, else `main`, else `master`, else ask.

## local
- Write the merge message to a file first - subject `merge: <change-name>` plus any trailers the user's commit rules require - because fixing a commit afterwards means amending, which this workflow never does unprompted. Then one call: `git checkout <main> && git merge --no-ff <branch> -F <msgfile>`. On conflict: stop, list the files, offer manual resolution or `git merge --abort`. Never resolve conflicts yourself.
- `git branch -d <branch>` (never `-D`). Report the merge commit and `Local only - push <main> when ready.` Never push.
- **Store-backed:** the store first, then the code repo, each with the steps above run in that repo (store: one call starting `cd "<store toplevel>" &&`, main from `planning_store.main_branch`, else main, else master):
  1. Merge and delete the store branch. On conflict, stop there: list the store files, offer manual resolution or `git merge --abort`, and report that the code repo was left unmerged on `<branch>`.
  2. Code branch with commits after `<main>` → merge and delete it the same way. On conflict, stop: list the code files, offer manual resolution or `git merge --abort`, and report the split state - the store's main has the change, the code repo's main does not.
  3. Code branch with no commits → `git checkout <main> && git branch -d <branch>`, no merge. Report that the change had no code changes.
  4. Report both repos: each merge commit (or "no code changes"), the deleted branches, and `Local only - push <main> when ready.`

## pr
- Run `specwright-pr` **ship**: it pushes the archive commit (pinning the GitHub identity and running `pr.validate`) and opens the PR if there is none, leaving an existing PR's description alone.
- If `specwright-pr` **watch** started this archive, hand back to it: it waits for CI and reviews on the archive head before reporting ready. Otherwise report the PR URL and `Ready to merge on GitHub once checks and reviews are green.`, and offer **watch**. Never merge the PR.
- **After the PR is merged** (the user says so, or `gh pr view <branch> --json state` shows MERGED): `git checkout <main> && git pull --ff-only`, then `[as] bash scripts/pr-pair.sh branch-check --dir <toplevel> --branch <branch> --main <main> --head <head_sha>`, with `<head_sha>` from the merged PR's `head_sha` in `discover ... --state merged` (several merged PRs: the `newest` one's), never from `gh pr view`. `delete: true` → `git branch -D <branch>`; otherwise keep the branch and report its `lacking` commits, or `head_unknown`. Then follow `specwright-pr` **Cleanup after merge** for the issues the merged PR's closing lines name: its `closed-check` lists any that GitHub left open and closes the ones the user confirms. Store-backed: that section also cleans both repos, so follow it instead of the commands above.

If the roadmap (`project.roadmap`) exists, once the change is on main (after the local merge, or after the PR is merged), offer exactly one `specwright-roadmap` mode: **close** when every change of the Now milestone is then done, derived as `specwright-roadmap` derives it; otherwise **next**. Never offer both.

## Planning repo

OpenSpec decides where planning lives: in this repo, in a folder nested in it, or in a store (a separate git repo). Resolve it at the start of every run, before any write; never assume `./openspec/`.

1. **Root:** `openspec list --json` from the code checkout, plus `--store <id>` when the session selected a store. It needs no change name, writes nothing and still works after archive. `root` null with an error whose `message` starts with `Declared in` or `Invalid store declaration in` → stop before any git or file write and show that `message` and `fix`.
2. **Repo**, in one call: `git rev-parse --path-format=absolute --git-common-dir --show-toplevel && git -C "<root.path>" rev-parse --path-format=absolute --git-common-dir --show-toplevel`.
   - The second fails (root not in a git work tree) → stop and ask: initialise git there, or abort.
   - Different common dir → **store-backed**: the planning repo is the store checkout at its toplevel.
   - Same common dir and toplevel → **repo-local** (including a root nested in this checkout, such as `planning/`): one repo, as before.
   - Same common dir, different toplevel → the root is in another worktree of this repo, where a commit would land on that worktree's branch. Stop before any write, name both worktrees (path and branch) and ask.
3. Announce once: `Code repo: <toplevel>; planning repo: <toplevel> (store <root.store_id>)` or `(same repo)`.

**Paths.** `<P>` is `<root.path>/openspec` made relative to the planning repo's toplevel (`openspec` in the usual layout, `planning/openspec` for a nested root). Stage and `ls-tree` planning files as `<P>/...` in the planning repo.

**Where commands run.** Git, `gh` and `as.sh` commands on the store run in one shell call that starts with `cd "<store toplevel>" &&` (`as.sh` only fences the repo it starts in). `openspec templates` and `openspec schema validate` have no root selection: run them with `cd "<root.path>" &&`. `git -C` is for read-only queries only (`rev-parse`, `status`, `log`, `ls-tree`).

**Archive name.** Use `archivedAs` from the archive output when you have it. Otherwise it is the change name if that starts with `YYYY-MM-DD-`, else `YYYY-MM-DD-<change-name>`: `<P>/changes/archive/<archived-name>/`.

**Referenced stores.** A `references:` list in the root's `config.yaml` does not move the planning root: a repo with its own root stays repo-local. Referenced stores are read-only: never branch, commit, stash, push, open a PR or write a file in one. Read them only through `openspec context --json` (each `members` entry with `role: referenced_store` gives its `path` and a `fetch` command such as `openspec show <spec-id> --type spec --store <id>`). A member whose `status` has `reference_unresolved` (the store is not registered on this machine) is named in the report as `unresolved reference: <id>` with its `fix`, and the step continues without it; never guess its path.
