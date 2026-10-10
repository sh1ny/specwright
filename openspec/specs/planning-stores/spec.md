# planning-stores Specification

## Purpose
Lets Specwright's git workflow (branching, planning, task and archive commits, finishing, pull requests and roadmap status) work when a project keeps its OpenSpec planning in a standalone store repo rather than in the code repo.

## Requirements

### Requirement: Planning root comes from OpenSpec
Every Specwright skill SHALL take the planning root from OpenSpec's resolved root (`root.path` in `--json` output), resolved by a command that stays valid after the change is archived, not from a fixed `./openspec/` path. A root in a different git repository from the code repo SHALL count as a store. A root inside the code repo's own checkout SHALL count as repo-local.

#### Scenario: Store selected by a project pointer
- **WHEN** the code repo's `openspec/config.yaml` declares `store: team-plans` and that store is registered at a path in another git repository
- **THEN** Specwright treats the change as store-backed and reads and writes planning files under the store's path

#### Scenario: Repo-local project is unchanged
- **WHEN** the resolved root is the code repo itself
- **THEN** Specwright runs every git step in the code repo only, with the same branches and commit subjects it produced before this change

#### Scenario: Root found after archive
- **WHEN** finish starts in a fresh session after `openspec archive` moved the change directory into the archive
- **THEN** Specwright still resolves the planning root and finds the archived directory `openspec/changes/archive/<archived-name>/` under it

#### Scenario: Date-prefixed change name found after archive
- **WHEN** a fresh finish session starts after `openspec archive` archived the change `2026-10-07-add-greeting`
- **THEN** Specwright finds `<root>/openspec/changes/archive/2026-10-07-add-greeting/` and does not look for a second date prefix

#### Scenario: Declared store cannot be resolved
- **WHEN** the project declares a store that is not registered on this machine, so OpenSpec reports an error starting with `Declared in` or `Invalid store declaration in`
- **THEN** Specwright stops before any git or file write and shows the user OpenSpec's `message` and `fix`

#### Scenario: Root in another worktree of the code repo
- **WHEN** the resolved root is in a different worktree of the code repo's git repository than the current checkout
- **THEN** Specwright stops before any write, names both worktrees, and no planning commit lands on either worktree's branch

### Requirement: Planning paths are relative to the resolved root
Specwright SHALL build every planning path (changes, archive, main specs, schema, config) from the resolved root, and convert it to a path relative to the checkout that holds it before staging or reading git trees. A root nested inside the code repo's checkout SHALL be handled as one repository with its root-relative paths. An archived change SHALL be found under `<archived-name>`, the name OpenSpec assigns: the change name if it starts with `YYYY-MM-DD-`, else `YYYY-MM-DD-<change-name>`.

#### Scenario: Root nested in the code repo
- **WHEN** a registered store resolves to `<code repo>/planning/` and is committed in the code repo's checkout
- **THEN** the archive commit stages `planning/openspec/changes/archive/...` paths in the code repo, one branch and one PR exist, and roadmap status finds archives under `planning/openspec/changes/archive/`

#### Scenario: Path outside every repository
- **WHEN** the resolved root is not inside any git work tree
- **THEN** Specwright stops before any write and asks whether to initialise git there or to abort

### Requirement: Store branch mirrors the code branch
When a new change will live in a store, `specwright-branch` SHALL run its gate on the store as well as the code repo: each must be a git work tree on its main branch with a clean tree. Only after both pass SHALL it create `<prefix>/<change-name>` in both, before any change file exists. If either check fails, it SHALL create neither branch.

#### Scenario: Both repos clean on main
- **WHEN** a change starts for a store-backed project and both the code repo and the store are clean and on their main branches
- **THEN** both repos are switched to a new branch `<prefix>/<change-name>` with the same name, and the announcement names both repos

#### Scenario: Store is dirty
- **WHEN** the code repo is clean but the store has uncommitted changes outside `openspec/changes/<change-name>/`
- **THEN** Specwright stops, shows the store's `git status --short`, offers commit, stash or abort, and leaves both repos on their original branches

#### Scenario: Store checkout busy with another change
- **WHEN** the store's checkout is on another change's branch because a second change is in progress against the same store
- **THEN** Specwright stops, names the branch the store is on, says that one store holds one change in progress at a time on this machine, does not switch the store off that branch (the other change's work would be lost) and leaves both repos on their original branches; the user finishes or abandons that change first

### Requirement: A change name is used once
`specwright-branch` SHALL stop before creating any branch when the planning repo's main branch, or its `origin` copy after a fetch, already holds an archive of a change with the same name (`<P>/changes/archive/<change-name>/` or `<P>/changes/archive/YYYY-MM-DD-<change-name>/`), and offer another name or abort. PR discovery, the planning-only marker and roadmap merge proofs match a change by its name, so an earlier change of the same name would otherwise count as this one's PR, marker or merge.

#### Scenario: Name of an archived change
- **WHEN** a store-backed change `add-csv-export` starts and the store's main holds `openspec/changes/archive/2026-09-01-add-csv-export/`
- **THEN** Specwright creates no branch in either repo, scaffolds nothing, leaves no gate lock, says the name was already used by an archived change and offers another name or abort

#### Scenario: Archived from another checkout
- **WHEN** the earlier `add-csv-export` was archived and merged from another checkout, so only the store's `origin/main` holds its archive and the local main has not been pulled
- **THEN** Specwright fetches the store's main, finds the archive on `origin/main` and stops the same way, without moving the local main

### Requirement: The store gate is exclusive
`specwright-branch` SHALL run the store checks and the branch creation while holding an exclusive gate lock on the store, so two sessions cannot both pass against the same store checkout. A lock left by an interrupted session SHALL be removed only with the user's confirmation.

#### Scenario: Two sessions start changes against one store at once
- **WHEN** two sessions in separate code checkouts run the branch gate for different changes against the same store at the same time, with the store clean on main
- **THEN** exactly one session creates its branches, and the other stops before creating any branch in either repo, reporting the store as busy or locked

#### Scenario: Gate lock left by an interrupted session
- **WHEN** the branch gate finds the store's gate lock held and no Specwright session is running its gate
- **THEN** Specwright creates no branch, shows when the lock was taken, and removes it only after the user confirms

### Requirement: Planning commits go to the store
For a store-backed change, `specwright-commit` SHALL commit planning artifacts and drift amendments in the store, on the store's change branch, staging only the change's directory. Task code SHALL be committed in the code repo. It SHALL NOT stop because the planning root is in another repository.

#### Scenario: Planning artifacts committed before the first task
- **WHEN** apply starts on a store-backed change with uncommitted artifacts under `<store>/openspec/changes/<change-name>/`
- **THEN** the store has a commit `<type>(<change-name>): add planning artifacts` on its change branch containing only those paths, and the code repo has no planning commit

#### Scenario: Task commit for a store-backed change
- **WHEN** a task is ticked `[x]` in `<store>/openspec/changes/<change-name>/tasks.md` after code files changed
- **THEN** the code files are committed in the code repo as `<type>(<change-name>): task X.Y ...`, and the `tasks.md` update is committed in the store with the same subject

#### Scenario: Store on the wrong branch
- **WHEN** a planning or task commit is due and the store's current branch is not `<prefix>/<change-name>`
- **THEN** Specwright makes no commit in either repo and stops, naming the store's current branch

### Requirement: Task commit pairs are reconciled before new work
Before ticking or committing another task, and before any planning commit, `specwright-commit` SHALL find every ticked task that has no store task commit, other than the task this session ticked and is committing now. When the task has a code commit, it SHALL commit that task's `tasks.md` change in the store with the original task subject. A store commit SHALL never include the tick of a task other than its own.

#### Scenario: Normal code task
- **WHEN** this session ticks task 1.2 after changing code files and commits it
- **THEN** the code commit and the store commit for 1.2 are made without asking whether 1.2 was a no-op

#### Scenario: Store commit failed, apply resumes
- **WHEN** task 1.1's code commit succeeded, its tick is uncommitted in the store after the store commit failed, and apply restarts
- **THEN** before task 1.2 is ticked, the store gets a commit whose subject contains `task 1.1 ` and whose `tasks.md` diff ticks only 1.1

#### Scenario: Reconciliation cannot isolate the tick
- **WHEN** the uncommitted `tasks.md` ticks more than one task that lacks a store commit
- **THEN** Specwright makes no commit, lists the tasks involved and asks the user how to record them

### Requirement: A tick without a code commit is confirmed
When reconciliation finds a ticked task with no store task commit and no code commit, and the task was not ticked by the current session, Specwright SHALL NOT infer that the task changed no code. It SHALL stop and ask whether the task was a code no-op before making any commit or tick.

#### Scenario: Restart before a task's code commit
- **WHEN** task 1.3 was ticked, the session stopped before its code commit, and apply restarts in a fresh session
- **THEN** Specwright makes no commit until the user says whether 1.3 changed code; if it did, the code files are committed first and then the tick in the store

#### Scenario: No-op task's store commit failed
- **WHEN** a verification-only task 2.3 was ticked with no code commit, its store commit failed, and apply restarts in a fresh session
- **THEN** Specwright makes no commit and ticks nothing until the user confirms whether task 2.3 changed no code, then commits the tick in the store with the original subject and `Code-Changes: none`

### Requirement: Completion check covers both repos
For a store-backed change, the "every task is `[x]`" check SHALL require, for every ticked task, a code-repo commit or a recorded code no-op, and a store commit containing `task X.Y `. It SHALL also require clean trees in both repos, apart from files that were already there before apply.

#### Scenario: All tasks committed in both repos
- **WHEN** every task is ticked and each has a matching commit in both repos and both trees are clean
- **THEN** Specwright reports `<N> tasks, <M> task commits, tree clean` separately for the code repo and the store

#### Scenario: Store has uncommitted tasks.md
- **WHEN** every task is ticked but the store still has an uncommitted `tasks.md` change
- **THEN** Specwright reconciles it as above, or reports the gap, and does not hand off to archive or PR until it is closed

### Requirement: Planning-only changes are recorded in the archive
When a store-backed change is planning-only at archive time, `specwright-finish` SHALL write `specwright-change.yaml` with `code_changes: none` into the archived change directory, as part of the archive commit. A change is planning-only when its code branch has no commits after the code main branch and no code PR from that branch into the code main branch exists in any state. Specwright SHALL NOT write the file otherwise, including on an archive recovery branch.

#### Scenario: Planning-only archive
- **WHEN** finish commits the archive of a store-backed change whose code branch has no commits
- **THEN** the store's archive commit contains `openspec/changes/archive/<archived-name>/specwright-change.yaml` with `code_changes: none`

#### Scenario: Planning-only archive of a date-prefixed change
- **WHEN** finish commits the archive of the planning-only change `2026-10-07-add-greeting`
- **THEN** the archive commit contains `openspec/changes/archive/2026-10-07-add-greeting/specwright-change.yaml`

#### Scenario: Old PR into another base
- **WHEN** finish archives a store-backed change whose code branch has no commits and whose only code PR from that branch targets `integration`, not the code main branch
- **THEN** the change is planning-only and the archive commit contains `specwright-change.yaml`

#### Scenario: Code work appears after the marker
- **WHEN** a feedback fix adds a code commit to a change whose archived directory already has `specwright-change.yaml`
- **THEN** the same feedback pass deletes `specwright-change.yaml` in a store commit before the code fix is pushed

### Requirement: Archive commit goes to the store
For a store-backed change, `specwright-finish` SHALL make the archive commit in the store, on the store's change branch. That commit SHALL hold the removed change directory, the archive directory and each main spec file the archive touched, staged by file. It SHALL NOT stage these paths in the code repo.

#### Scenario: Archive committed in the store
- **WHEN** `openspec archive` succeeds for a store-backed change
- **THEN** the store has a commit `<type>(<change-name>): archive change` containing exactly the archive paths, and the code repo's `git status --porcelain` shows no archive path

#### Scenario: Archive ran with the store on main
- **WHEN** archive ran while the store was on its main branch and the archive is uncommitted there
- **THEN** Specwright makes no commit on the store's main branch and offers to create `chore/archive-<change-name>` in the store to carry the archive, with no code branch or code PR for it

#### Scenario: Archive recovery while the code PR is open
- **WHEN** archive ran with the store on main and the change's code PR is still open
- **THEN** the archive commit on `chore/archive-<change-name>` contains no `specwright-change.yaml`, and roadmap status keeps reporting the change as code pending

### Requirement: Local finish merges the repos that have work
With `finish: local`, a store-backed change SHALL be merged into main with `--no-ff` in the store, then in the code repo if its branch has commits, and each merged branch deleted with `git branch -d`. An empty code branch SHALL be deleted unmerged with `-d`. If the store merge conflicts, the code repo SHALL be left unmerged. Nothing SHALL be pushed.

#### Scenario: Both merges succeed
- **WHEN** finish runs in local mode, the code branch has commits, and neither repo has a merge conflict
- **THEN** each repo's main has a merge commit `merge: <change-name>`, both change branches are deleted, and the report names both merge commits and says nothing was pushed

#### Scenario: Planning-only change in local mode
- **WHEN** finish runs in local mode and the code branch has no commits
- **THEN** only the store's main gets `merge: <change-name>`, the code branch is deleted, and the report says the change had no code changes

#### Scenario: Store merge conflicts
- **WHEN** the store's merge into main conflicts
- **THEN** Specwright stops, lists the conflicting store files, offers manual resolution or `git merge --abort`, and leaves the code repo on its change branch with no merge commit

#### Scenario: Code merge conflicts after the store merged
- **WHEN** the store merge succeeded and the code merge then conflicts
- **THEN** Specwright stops, lists the conflicting code files, and reports that the store's main has the change while the code repo does not

#### Scenario: Interrupted between the store merge and the code merge
- **WHEN** the store's main has `merge: <change-name>` and the store branch is deleted, the code branch has commits after main, the code main has no `merge: <change-name>`, and finish runs again
- **THEN** finish does not report `Nothing to finish`, makes no store commit or merge, merges the code branch into the code main as `merge: <change-name>`, and deletes the code branch

### Requirement: Commands run where they resolve correctly
Every git or `gh` command that acts on the store SHALL run with the store's checkout toplevel as the working directory. OpenSpec commands without root selection (`openspec templates`, `openspec schema validate`) SHALL run with the resolved root as the working directory. Authenticated pushes SHALL go through the identity wrapper started inside the target checkout, as the resolved store login. Git network reads of the store (`ls-remote`, `fetch`) made by the PR scripts SHALL authenticate as the resolved store login too, and those of the code repo as the code login.

#### Scenario: Store push with a repository-local auth header
- **WHEN** the store has a repository-local URL-scoped `http.extraHeader` that the code repo lacks, and `planning_store.login` is unset while `github.login` is set
- **THEN** the store push runs the identity wrapper from inside the store, the header is scrubbed, and the push authenticates as `github.login`

#### Scenario: Store login override
- **WHEN** `planning_store.login` names a different account from `github.login`
- **THEN** store pushes and store PR operations authenticate as `planning_store.login`, and code pushes authenticate as `github.login`

#### Scenario: Schema lookup with a root nested in the store repo
- **WHEN** the resolved root is `<store checkout>/planning/`, and the `specwright` schema exists only under `<store checkout>/planning/openspec/schemas/specwright/`
- **THEN** the reviewer's template lookup and the install's schema validation run in `<store checkout>/planning/` and return paths under that directory

#### Scenario: Private store readable only by the store login
- **WHEN** `planning_store.login` differs from `github.login`, the store remote accepts only the store login's credential, and `rounds` or `pass plan` checks whether a store fix commit is on the remote
- **THEN** the store's `ls-remote` and `fetch` authenticate as `planning_store.login`, the check reports the commit's real state, and no `remote_unreadable` is reported for the store

#### Scenario: Store login has no credential
- **WHEN** `planning_store.login` differs from `github.login` and no `gh` credential exists for it
- **THEN** the call stops with `no_credential` (exit 3) before any store git network command runs, and never retries with the code login

### Requirement: The expected PR set follows the change's work and transport
For a store-backed change in `pr` mode, Specwright SHALL expect a code PR when a code PR from `<prefix>/<change-name>` into the code main exists in any state, or, before one exists, when the code branch has commits after main. It SHALL expect a store PR exactly when the store has a GitHub `origin`. It SHALL recompute this set at every ship, watch, feedback, archive and cleanup step and use it for each; merging a PR, advancing main or deleting a branch SHALL NOT remove that PR from the set.

#### Scenario: Planning-only change with a GitHub store
- **WHEN** ship runs and the code branch has no commits while the store has a GitHub `origin`
- **THEN** only the store PR is opened, and its description says the change has no code changes

#### Scenario: Planning-only change with no GitHub store
- **WHEN** ship runs, the code branch has no commits and the store has no GitHub `origin`
- **THEN** no PR is opened, and the report names the store branch to be shared by hand and says nothing is watched

#### Scenario: Code fix turns a planning-only change into a pair
- **WHEN** a feedback fix adds the first commit to the code branch of a change whose only PR is the store PR
- **THEN** the next ship step opens the code PR with a link to the store PR, and watch waits on both PRs from then on

#### Scenario: Fresh watch after the code PR merged
- **WHEN** a fresh session runs watch after the code PR was merged and the code main was pulled, so the code branch has no commits after main, while the store PR is still open
- **THEN** the expected set still holds both PRs, and watch reports the split and hands off without archiving or reporting ready

### Requirement: PR finish pairs the store PR with the code PR
When both PRs are expected, each SHALL link the other: in its description when the other PR's URL is known as it is created, otherwise by one marker comment that names the peer PR. When the peer PR changes, Specwright SHALL update its own marker comment rather than add another. Specwright SHALL NOT rewrite an existing description. An existing PR whose base is not that repo's main SHALL stop ship. It SHALL push and validate each repo with that repo's settings and SHALL never merge either PR.

#### Scenario: Ship opens both PRs
- **WHEN** ship runs for a store-backed change, both PRs are expected and neither exists
- **THEN** the store PR is created first and gets one Specwright link comment with the code PR URL, and the code PR's description contains the store PR URL

#### Scenario: Code PR already open without the link
- **WHEN** ship runs and the code PR already exists with a description that has no store PR link
- **THEN** the code PR's description is unchanged, and the code PR has exactly one Specwright link comment containing the store PR URL

#### Scenario: Ship re-run after an interrupted first run
- **WHEN** ship runs again after a run that opened the store PR but stopped before opening the code PR
- **THEN** no second store PR is created, the code PR is created, and each PR has exactly one link to the other

#### Scenario: Code PR replaced after closing unmerged
- **WHEN** the linked code PR was closed unmerged and ship opens a replacement code PR from the same branch while the store PR is open
- **THEN** the store PR's Specwright link comment names the replacement code PR, and the store PR has exactly one Specwright link comment

#### Scenario: Existing code PR targets another branch
- **WHEN** ship finds an open code PR from `<prefix>/<change-name>` whose base is `integration` rather than the code main
- **THEN** Specwright stops, names the PR and its base, and opens or links no PR

#### Scenario: Fetch and push URLs name different repositories
- **WHEN** the store's `origin` fetches from `team/plans` but pushes to `publishing/plans`
- **THEN** Specwright stops before pushing the store branch, names both repositories, and opens or looks up no store PR

#### Scenario: Matching PR beyond the first page
- **WHEN** thirty newer PRs from forks share the change's branch name and base, and the change's own code PR is older and merged
- **THEN** the code PR is still found, stays in the expected set, and counts as merged-code proof for roadmap status

#### Scenario: Inherited GH_REPO names the code repo
- **WHEN** ship and watch run for a store-backed change with `GH_REPO` set to the code repo, or with a `gh` default repository other than the store's `origin`
- **THEN** every store PR lookup, creation, wait and reply targets the store's `origin` repository, and the store PR and code PR are never the same PR

#### Scenario: Store push rejected
- **WHEN** pushing the store branch fails, for example because of a missing permission or a non-fast-forward rejection
- **THEN** Specwright reports the store push error, does not open or update the store PR, and does not report the change as ready

### Requirement: Watch covers the expected PR set
For a store-backed change in `pr` mode, watch SHALL run one wait per expected PR and report ready only when every expected PR is open and ready. A snapshot SHALL count toward readiness only when its repository, PR number and head commit match the PR that discovery reports at that call. When an expected PR merges or closes while another expected PR is open, watch SHALL stop all waits and hand off to the user. Archive-before-merge SHALL publish the store archive commit only when a store PR is expected.

#### Scenario: Code PR green, store PR waiting
- **WHEN** the code PR's checks and required reviews pass but the store PR still has an unresolved required review
- **THEN** watch does not report the change as ready and keeps waiting on the store PR

#### Scenario: Store PR alone is ready
- **WHEN** the change is planning-only and its store PR passes the readiness checks
- **THEN** watch reports the change ready

#### Scenario: One PR of the pair merged
- **WHEN** the store PR is merged while the code PR is still open
- **THEN** watch stops all background waits and reports which PR merged and which is still open, without archiving or re-requesting review

#### Scenario: Archive before merge with no store PR
- **WHEN** the code PR is ready, the store has no GitHub `origin`, and the user agrees to archive
- **THEN** the archive commit is made on the store branch without a push or review request, and the report names the store branch to be shared by hand

#### Scenario: Store snapshot of an old head
- **WHEN** the store snapshot passes every readiness check for head A, while discovery reports the store PR's head as B
- **THEN** `pair-state` reports `wait`, not `ready`, with a `refresh` blocker for the store naming heads A and B

#### Scenario: Snapshot of another PR
- **WHEN** the code snapshot file holds a ready snapshot of PR 7, while discovery reports the code PR as PR 9
- **THEN** `pair-state` reports `wait` with a `refresh` blocker for the code PR naming PRs 7 and 9

#### Scenario: Snapshot without a head
- **WHEN** a snapshot has no `head_oid` or no `number`
- **THEN** `pair-state` treats it as not matching and reports a `refresh` blocker, never `ready`

### Requirement: Feedback rounds span the PR pair
For a store-backed change, one feedback pass SHALL cover every expected PR. A fix to `<root>/openspec/**` SHALL be committed on the store branch, and any other fix on the code branch, whichever PR the finding came from. Each fix commit SHALL carry the trailer `Feedback-Round: <n>`. The round limit SHALL count the highest `n` across both branches and SHALL apply only to starting a new pass. Fix commits without a trailer SHALL be counted by their `address review feedback` subject only when neither branch has a `Feedback-Round` trailer.

#### Scenario: Spec fix requested on the code PR
- **WHEN** a reviewer on the code PR asks for a change to a requirement in the change's spec delta
- **THEN** the fix is committed with `Feedback-Round: <n>` and pushed on the store branch, review is re-requested on the store PR, and the reply on the code PR links the store commit

#### Scenario: Round limit across both repos
- **WHEN** `max_fix_rounds` is 2, earlier passes committed `Feedback-Round: 1` on the store branch and `Feedback-Round: 2` on the code branch, and both branches are pushed
- **THEN** the next pass makes no fix in either repo and answers findings per `after_limit`

#### Scenario: Finishing an interrupted final pass
- **WHEN** `max_fix_rounds` is 2 and pass 2 committed in both repos but the store push failed
- **THEN** the next run pushes the store commit, re-requests review on the store PR and answers that pass's findings, without counting a new round or taking the after-limit path

#### Scenario: Recovered partial fix
- **WHEN** `max_fix_rounds` is 2 and round 1 was finished after an interruption by a second `address review feedback` commit carrying `Feedback-Round: 1`
- **THEN** the round count is 1, the limit is not reached, and the next pass is round 2

#### Scenario: Legacy branch without trailers
- **WHEN** neither branch has a `Feedback-Round` trailer and the code branch has two `address review feedback` commits
- **THEN** the round count is 2

### Requirement: An interrupted feedback pass is completed first
A feedback pass SHALL record its round, findings, their destination repos, the edits each fix needs and each finding's intended disposition before its first fix. A run that finds a record SHALL finish that pass under its original round before any new fix, even at the round limit, reading each step's progress from git and GitHub so that no action is repeated. The record SHALL be removed once every applicable step of the pass is done, as limited by the settings and each finding's disposition. A reaction counts as done only when GitHub shows it; a code PR adopted by the pass counts as linked only when both PRs link each other.

#### Scenario: Interrupted between the two fix commits
- **WHEN** `max_fix_rounds` is 2 and pass 2 committed its code fix but stopped before committing its store fix
- **THEN** the next run makes the store fix recorded for pass 2 with `Feedback-Round: 2`, publishes both, and answers pass 2's findings, without starting pass 3

#### Scenario: Interrupted after both pushes
- **WHEN** pass 2 pushed both fix commits and stopped before re-requesting review and replying
- **THEN** the next run re-requests review on both PRs and posts pass 2's replies, and no new fix is made

#### Scenario: Commit made but not recorded
- **WHEN** pass 2's code fix commit exists on the code branch but the run stopped before anything else
- **THEN** the next run makes no second code fix commit, and pushes and answers pass 2 from that commit

#### Scenario: Reply posted, then its resolution failed
- **WHEN** pass 2's reply to a thread was posted, and resolving the thread failed before the run stopped
- **THEN** the next run posts no second reply to that thread, and lists the thread's pending resolution for the user

#### Scenario: Reviewer follow-up during the interruption
- **WHEN** pass 2 pushed its fixes and stopped before its first reply, and the reviewer then added a follow-up to a pass 2 thread or edited its finding
- **THEN** the next run posts no reply or resolution for that thread from the old pass, and lists the new activity and asks the user

#### Scenario: Interrupted halfway through a spec fix
- **WHEN** a pass 2 fix needs edits to an archived spec delta and its main spec, and the run stopped after editing only the archived delta
- **THEN** the next run edits the main spec as recorded before committing, and answers the finding only after the commit contains both edits

#### Scenario: Review requests disabled
- **WHEN** `github.review_request.body` is empty, `pr.reviewers` is unset, and pass 2's fixes are pushed and its findings answered
- **THEN** the pass record is removed and no review request is posted

#### Scenario: Pass with an open question thread
- **WHEN** pass 2 answered one thread with a question back to the reviewer, without resolving it, and finished its other steps
- **THEN** the pass record is removed and that thread stays unresolved

#### Scenario: Reply posted, reaction not sent
- **WHEN** `pr.react` is true, pass 2's reply to a finding was posted, and the run stopped before its recorded reaction was added
- **THEN** the next plan lists that reaction as to do, `pass done` keeps the record, and the record is removed only after GitHub shows the reaction on the finding

#### Scenario: Reaction already present
- **WHEN** pass 2's reply and its recorded reaction are both on GitHub
- **THEN** the plan lists the reaction as done and adds no second reaction

#### Scenario: Code PR adopted before the pair was linked
- **WHEN** a store-only change's pass 2 made the first code fix, ship opened the code PR, and the run stopped before linking the PRs
- **THEN** the next plan lists a link step as to do, the pass does not complete until each PR links the other, and each PR then has exactly one link to its peer

### Requirement: Cleanup after merge covers every expected PR
After the PRs are merged, `specwright-finish` SHALL, for each repo whose expected PR is MERGED, check out its main, pull with `--ff-only`, and delete the change branch under the existing merged-head rule. It SHALL delete an empty code branch with `-d`. It SHALL leave the branch of any repo whose expected PR is not merged and report it.

#### Scenario: Both PRs merged
- **WHEN** both expected PRs are MERGED
- **THEN** both checkouts are on an updated main, both change branches are deleted, and the next branch gate does not report the store as busy

#### Scenario: Only one PR merged
- **WHEN** the code PR is MERGED and the store PR is still open
- **THEN** only the code checkout is cleaned up, the store stays on its change branch, and the report names the open store PR

#### Scenario: Cleanup re-run after the store PR merges
- **WHEN** cleanup runs again after the split above, once the store PR is MERGED and the code branch is already deleted
- **THEN** the store checkout is cleaned up and the code PR is still counted as merged, not as missing

### Requirement: Roadmap status needs proof that the whole change merged
`specwright-roadmap` SHALL count a store-backed change as done only when the store's main holds its archive directory and either that directory holds `specwright-change.yaml` with `code_changes: none`, or the code side merged as a whole: a `merge: <change-name>` commit on the code main's first-parent history in `local` mode, or a MERGED code PR whose head is `<prefix>/<change-name>` in the code repo itself and whose base is the code main in `pr` mode.

#### Scenario: Both repos merged
- **WHEN** the store's main has `openspec/changes/archive/<archived-name>/` and the change's code PR is MERGED (pr mode) or code main's first-parent history has `merge: <change-name>` (local mode)
- **THEN** roadmap status reports the change as done

#### Scenario: Date-prefixed change merged
- **WHEN** the store's main has `openspec/changes/archive/2026-10-07-add-greeting/` and the code-side proof for `2026-10-07-add-greeting` holds
- **THEN** roadmap status reports the change as done, and `next` accepts it as a completed prerequisite

#### Scenario: Code partly integrated
- **WHEN** the store's main has the archive and one task commit of the change was cherry-picked onto code main, but the code PR is still open
- **THEN** status reports the change as "planning merged, code pending", and `next` does not treat it as a done prerequisite

#### Scenario: Same branch name merged from a fork
- **WHEN** the change's code PR is open, and a PR from a fork's branch with the same name was merged into the code main
- **THEN** status reports the change as "planning merged, code pending", and ship and watch never treat the fork's PR as the change's code PR

#### Scenario: Code PR merged into another branch
- **WHEN** the store's main has the archive and the change's code PR was merged into `integration`, not the code main
- **THEN** status reports the change as "planning merged, code pending"

#### Scenario: Planning-only change squash-merged
- **WHEN** a planning-only change's store PR was squash-merged and its branch deleted
- **THEN** the store's main still has `specwright-change.yaml` with `code_changes: none` in the archived directory, and status reports the change as done

#### Scenario: Store fetch fails
- **WHEN** roadmap status runs in `pr` mode and `git fetch` in the store fails
- **THEN** status reads the store's local main and says that the store status may be stale

### Requirement: Referenced stores are read-only
When a repo keeps its own `openspec/` root and lists stores under `references:`, Specwright SHALL treat the repo as repo-local. It SHALL NOT branch, commit, push or open PRs in a referenced store. Design and review steps MAY read specs from a referenced store as context.

#### Scenario: Apply in a repo with references
- **WHEN** apply runs in a repo whose `config.yaml` has `references: [team-plans]` and the change lives in the repo's own `openspec/`
- **THEN** every commit lands in the code repo and the `team-plans` store's branch and `git status` are the same as before apply

#### Scenario: Referenced store is not registered
- **WHEN** a design step tries to read a referenced store that is not registered on this machine
- **THEN** the step continues without that context and the artifact or report names the unresolved reference

### Requirement: Install targets the resolved root
The install/update procedure SHALL put the `specwright` schema and the skill-trigger `context:` under the resolved root's `openspec/`, and `specwright.yaml` in the code repo's `openspec/`. It SHALL NOT create `openspec/specs/` or `openspec/changes/` in the code repo when the root is elsewhere, since those would take precedence over the store.

#### Scenario: Install into a store-backed project
- **WHEN** the install prompt runs in a code repo whose planning resolves to a registered store
- **THEN** the store has `openspec/schemas/specwright/` and a `config.yaml` with `schema: specwright` and the trigger `context:`, `openspec schema validate specwright` run in the resolved root passes, and `openspec list --json` from the code repo still reports the store as root

#### Scenario: Store already uses another schema
- **WHEN** the store's `config.yaml` names a schema other than `spec-driven` or `specwright`
- **THEN** the install asks the user before changing it and, if they decline, reports "installed, but not the default schema"

### Requirement: Roadmap branches in a store go through the gate lock
When roadmap **init** or **close** creates its project-file branch in a store, it SHALL take the store's exclusive gate lock (the one `specwright-branch` uses) before checking the store, and SHALL release only the lock it took, right after the branch exists. A lock held by another session SHALL stop it before any branch or write.

#### Scenario: Store is free
- **WHEN** close runs against a store that is clean on main with no gate lock
- **THEN** it creates `docs/close-m1` in the store while holding the lock, and the lock no longer exists after the branch is created

#### Scenario: Another session holds the lock
- **WHEN** close runs while the store's gate lock exists, owned by another session's change
- **THEN** close creates no branch in either repo, writes no project file, leaves the lock and its owner file unchanged, and shows the owner

### Requirement: Roadmap store writes check the branch
For store-backed roadmap **init** and **close**, each step that writes project files in the store SHALL first confirm, in a shell call, that the store is on the expected branch. Each store commit SHALL run that check in the same shell call as the commit. On a mismatch it SHALL stop without further writes or commits and name both branches.

#### Scenario: Store stays on the roadmap branch
- **WHEN** the store is on `docs/project-baseline` throughout init
- **THEN** every project-file commit lands on `docs/project-baseline` in the store

#### Scenario: Store switched before a commit
- **WHEN** another session switches the store to `feat/add-csv-export` after close wrote its files but before it commits
- **THEN** close makes no commit, `feat/add-csv-export` gains no commit, and the report names `docs/close-m1` as expected and `feat/add-csv-export` as found
