# Spec Delta

## ADDED Requirements

### Requirement: A failed store gate branch leaves no new branch
When a store gate's `git checkout -b <branch>` errors in either repo (`specwright-branch`, or roadmap **init** or **close**), the gate SHALL, in each repo where it ran `git checkout -b` and `<branch>` exists, switch back to that repo's main and delete `<branch>`. It SHALL judge the switch by the repo's current branch, not by the command's exit status. It SHALL then release the gate lock it took and stop with the error.

#### Scenario: Store hook fails after the branch is created
- **WHEN** close runs store-backed with project files in both repos, and the store's `post-checkout` hook exits non-zero, so `git checkout -b docs/close-m1` errors after creating and switching to the branch
- **THEN** both repos are on their main, `docs/close-m1` exists in neither, the gate lock no longer exists, nothing is committed, and the report shows the hook's error

#### Scenario: Store hook fails after the code branch exists
- **WHEN** `specwright-branch` has created `feat/add-csv-export` in the code repo, and the store's `post-checkout` hook exits non-zero on the store's `git checkout -b`
- **THEN** both repos are on their main, `feat/add-csv-export` exists in neither, the gate lock no longer exists, no change directory exists, and the report shows the hook's error

#### Scenario: Code hook fails after the store branch exists
- **WHEN** close runs store-backed with project files in both repos, has created `docs/close-m1` in the store, and the code repo's `post-checkout` hook exits non-zero on its `git checkout -b docs/close-m1`
- **THEN** both repos are on their main, `docs/close-m1` exists in neither, the gate lock no longer exists, nothing is committed, and the report shows the hook's error

#### Scenario: Branch creation refused outright
- **WHEN** the store's `git checkout -b docs/close-m1` errors without creating the branch
- **THEN** no repo holds `docs/close-m1`, both repos are on their main, and the gate lock no longer exists

#### Scenario: One repo cannot switch back
- **WHEN** after a hook failure the code repo is still on `docs/close-m1` after `git checkout main`, and the store is on `docs/close-m1` too
- **THEN** the store is switched to its main and its `docs/close-m1` deleted, the code repo's `docs/close-m1` is kept, the gate lock no longer exists, and the report names the code repo, `docs/close-m1` and its main

#### Scenario: Gate passes without errors
- **WHEN** both repos' `git checkout -b docs/close-m1` succeed
- **THEN** both repos are on `docs/close-m1` and no rollback runs

### Requirement: Git network reads authenticate as each repo's login
Git network reads of the store (`ls-remote`, `fetch`) made by the PR scripts SHALL authenticate as the resolved store login, and those of the code repo as the code login.

#### Scenario: Store and code logins differ
- **WHEN** `planning_store.login` is `plans-bot`, `github.login` is `code-bot`, and `rounds` reads both remotes
- **THEN** the store's `ls-remote` authenticates as `plans-bot` and the code repo's as `code-bot`

#### Scenario: Code remote accepts only the code login
- **WHEN** `planning_store.login` differs from `github.login`, and the code remote accepts only `github.login`'s credential
- **THEN** the code repo's `ls-remote` authenticates as `github.login` and reports the code branch's real state, never as `planning_store.login`

### Requirement: A snapshot counts only for the PR and head discovery reports
A snapshot SHALL count toward readiness only when its repository, PR number and head commit match the PR that discovery reports at that call.

#### Scenario: Snapshot matches discovery
- **WHEN** the code snapshot is of PR 9 at head B and passes every readiness check, and discovery reports the code PR as PR 9 at head B
- **THEN** `pair-state` counts the code PR as ready

#### Scenario: Code snapshot of an old head
- **WHEN** the code snapshot is of PR 9 at head A and passes every readiness check, while discovery reports PR 9 at head B
- **THEN** `pair-state` reports `wait` with a `refresh` blocker for the code PR naming heads A and B

### Requirement: Fix rounds are counted across both branches
Each fix commit SHALL carry the trailer `Feedback-Round: <n>`. The round limit SHALL count the highest `n` across both branches and SHALL apply only to starting a new pass. Fix commits without a trailer SHALL be counted by their `address review feedback` subject only when neither branch has a `Feedback-Round` trailer.

#### Scenario: Round below the limit
- **WHEN** `max_fix_rounds` is 2 and only the store branch has a fix commit, with `Feedback-Round: 1`
- **THEN** the next pass is round 2, and each of its fix commits carries `Feedback-Round: 2`

#### Scenario: Trailer and legacy commits mixed
- **WHEN** the store branch has a fix commit with `Feedback-Round: 1` and the code branch has two `address review feedback` commits without a trailer
- **THEN** the round count is 1: the commits without a trailer are not counted

### Requirement: A pass record is removed only when its pass is done
A feedback pass's record SHALL be removed once every applicable step of the pass is done, as limited by the settings and each finding's disposition. A reaction counts as done only when GitHub shows it; a code PR adopted by the pass counts as linked only when both PRs link each other.

#### Scenario: Every step done
- **WHEN** pass 2's fixes are pushed in both repos, review is re-requested on both PRs, and every finding of pass 2 is answered and resolved as recorded
- **THEN** `pass done` removes the pass record

#### Scenario: Reply posted, push missing
- **WHEN** pass 2's replies are posted but its store fix commit is not on the store's remote
- **THEN** `pass done` keeps the record, and the next plan lists the store push as to do

## MODIFIED Requirements

### Requirement: Commands run where they resolve correctly
Every git or `gh` command that acts on the store SHALL run with the store's checkout toplevel as the working directory. OpenSpec commands without root selection (`openspec templates`, `openspec schema validate`) SHALL run with the resolved root as the working directory. Authenticated pushes SHALL go through the identity wrapper started inside the target checkout, as the resolved store login.

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

### Requirement: Watch covers the expected PR set
For a store-backed change in `pr` mode, watch SHALL run one wait per expected PR and report ready only when every expected PR is open and ready. When an expected PR merges or closes while another expected PR is open, watch SHALL stop all waits and hand off to the user. Archive-before-merge SHALL publish the store archive commit only when a store PR is expected.

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
For a store-backed change, one feedback pass SHALL cover every expected PR. A fix to `<root>/openspec/**` SHALL be committed on the store branch, and any other fix on the code branch, whichever PR the finding came from.

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
A feedback pass SHALL record its round, findings, their destination repos, the edits each fix needs and each finding's intended disposition before its first fix. A run that finds a record SHALL finish that pass under its original round before any new fix, even at the round limit, reading each step's progress from git and GitHub so that no action is repeated.

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
