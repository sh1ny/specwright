# Spec Delta

## ADDED Requirements

### Requirement: A store without a PR is a manual handoff
In the PR workflow, a proven local-only store SHALL hand off its named branch for manual sharing and archiving. `pair-state` SHALL report a manual handoff rather than readiness; watch and finish SHALL stop the store's part before archive prompts or edits. Feedback SHALL NOT read store history or ancestry or count store rounds. A handoff SHALL NOT authorize automated archive or merge, and SHALL leave the store unchanged.

#### Scenario: Feedback rounds with an off-host store
- **WHEN** the local store branch has a committed fix trailer, but its selected remote is outside the configured GitHub host
- **THEN** feedback and `rounds` report the named manual handoff without emitting a round decision, reading store trailers, contacting the store remote or its credential helper, committing a store fix or treating the store portion as complete

#### Scenario: PR finish with a local-only store
- **WHEN** PR finish identifies a local-only planning store before archive has run
- **THEN** it reports the planning branch to share and archive by hand without prompting for archive, invoking `openspec archive`, starting a store watch, or making any store write

#### Scenario: Archive edits already exist at PR finish
- **WHEN** PR finish identifies a local-only planning store with archive edits already in its worktree
- **THEN** it reports the same handoff, preserves the edits, and creates no archive commit, recovery branch, push or PR

## MODIFIED Requirements

### Requirement: A change name is used once
`specwright-branch` SHALL stop before creating any branch when the planning repo's main branch, or its selected remote's copy after a fetch, already holds an archive of a change with the same name (`<P>/changes/archive/<change-name>/` or `<P>/changes/archive/YYYY-MM-DD-<change-name>/`), and offer another name or abort. PR discovery, the planning-only marker and roadmap merge proofs match a change by its name, so an earlier change of the same name would otherwise count as this one's PR, marker or merge.

#### Scenario: Name of an archived change
- **WHEN** a store-backed change `add-csv-export` starts and the store's main holds `openspec/changes/archive/2026-09-01-add-csv-export/`
- **THEN** Specwright creates no branch in either repo, scaffolds nothing, leaves no gate lock, says the name was already used by an archived change and offers another name or abort

#### Scenario: Archived from another checkout
- **WHEN** the store uses `planning_store.remote: plans` and only `plans/main` holds the earlier archive because it was merged from another checkout
- **THEN** Specwright fetches main from `plans`, finds the archive there and stops the same way, without moving the local main

### Requirement: The expected PR set follows the change's work and transport
For a store-backed change in `pr` mode, Specwright SHALL expect a code PR when one exists in any state or the code branch has commits after main. It SHALL expect a store PR when its selected remote's fetch and all push destinations identify one repo on the configured host, distinct from the required code identity. Only a proven absent or entirely off-host store remote is local-only; mixed, unclassifiable or unreadable destinations SHALL stop. Ship SHALL inspect local work and transport first and validate, push and watch only the expected set. Later PR phases SHALL recompute the set subject to manual handoff; an existing PR remains expected after merge or branch deletion.

#### Scenario: Planning-only change with a GitHub store
- **WHEN** ship runs, the code branch has no commits and has a usable GitHub identity, and the selected planning remote is on the configured GitHub host
- **THEN** only the store PR is opened, and its description says the change has no code changes

#### Scenario: Planning-only change with no GitHub store
- **WHEN** ship runs, the code branch has no commits and the store's selected remote is absent or not on the configured GitHub host
- **THEN** no PR is opened, and the report names the store branch to be shared by hand and says nothing is watched

#### Scenario: Local-only store with code to ship
- **WHEN** the code branch has commits and a usable GitHub remote but the planning store has no `origin` and no explicitly selected remote
- **THEN** ship opens only the code PR, reports that the store is local and to share the planning branch by hand, and sends no store validate, push, PR or watch request

#### Scenario: Code PR required but the code remote is missing
- **WHEN** the code branch has commits and the code repository has no selected remote, even if the store has a usable GitHub remote
- **THEN** ship stops before either push and names the missing code remote

#### Scenario: Store publication still requires code identity
- **WHEN** the code branch has no commits after main and no usable GitHub remote, but the store has a usable GitHub remote
- **THEN** ship stops before either push and reports the missing or unusable code target

#### Scenario: Code fix turns a planning-only change into a pair
- **WHEN** a feedback fix adds the first commit to the code branch of a change whose only PR is the store PR
- **THEN** the next ship step opens the code PR with a link to the store PR, and watch waits on both PRs from then on

#### Scenario: Fresh watch after the code PR merged
- **WHEN** a fresh session runs watch after the code PR was merged and the code main was pulled, so the code branch has no commits after main, while the store PR is still open
- **THEN** the expected set still holds both PRs, and watch reports the split and hands off without archiving or reporting ready

#### Scenario: An unreadable code range is not an empty range
- **WHEN** a change branch exists, its base or range cannot be read, and the store would otherwise be publishable
- **THEN** the workflow reports that the expected set could not be established and sends no push to either repository

#### Scenario: A merged code PR remains expected without a local change branch
- **WHEN** the local code change branch was deleted after merge, but discovery finds its matching merged PR
- **THEN** the code PR remains expected and cleanup does not infer that there was no code PR

#### Scenario: A failed remote lookup does not make the store local
- **WHEN** Git reports an error enumerating remotes or reading the selected store remote's fetch or applicable push URLs
- **THEN** the workflow reports the read error, opens no PR, attempts no push, and does not report the store as local

#### Scenario: Fetch and push disagree about the GitHub host
- **WHEN** the selected planning remote fetches from an off-host mirror and pushes to the configured GitHub host, or fetches from that host and has any off-host push URL
- **THEN** ship reports the disagreement rather than manual sharing and stops before discovery or either push

#### Scenario: Code and store select the same repository
- **WHEN** the two roles select different remote names whose effective URLs identify the same canonical host and case-insensitive owner/name
- **THEN** PR planning reports the role collision before discovery or push and opens no PR

#### Scenario: No GitHub operation is needed
- **WHEN** local checks prove neither repo has a GitHub PR to look up or open and neither side needs publication
- **THEN** ship reports the manual-share outcome without resolving a stored GitHub account

### Requirement: PR finish pairs the store PR with the code PR
When both PRs are expected, each SHALL link the other: in its description when the other PR's URL is known as it is created, otherwise by one marker comment that names the peer PR. When the peer PR changes, Specwright SHALL update its own marker comment rather than add another. Specwright SHALL NOT rewrite an existing description. An existing PR whose base is not that repo's main SHALL stop ship. It SHALL push and validate each repo with that repo's settings and SHALL never merge either PR in ship.

#### Scenario: Ship opens both PRs
- **WHEN** ship runs for a store-backed change, both PRs are expected and neither exists
- **THEN** the store PR is created first and gets one Specwright link comment with the code PR URL, and the code PR's description contains the store PR URL

#### Scenario: Code PR already open without the link
- **WHEN** the code PR already exists with a description that has no store PR link
- **THEN** the code PR's description is unchanged, and the code PR has exactly one Specwright link comment containing the store PR URL

#### Scenario: Ship re-run after an interrupted first run
- **WHEN** ship runs again after a run that opened the store PR but stopped before opening the code PR
- **THEN** no second store PR is created, the code PR is created, and each PR has exactly one link to the other

#### Scenario: Code PR replaced after closing unmerged
- **WHEN** the linked code PR was closed unmerged and ship opens a replacement code PR from the same branch while the store PR is open
- **THEN** the store PR's Specwright link comment names the replacement code PR, and the store PR has exactly one link to its peer

#### Scenario: Existing code PR targets another branch
- **WHEN** ship finds an open code PR whose base is `integration` rather than the code main
- **THEN** Specwright stops, names the PR and its base, and opens or links no PR

#### Scenario: Fetch and push URLs name different repositories
- **WHEN** `planning_store.remote: plans` selects a remote that fetches from `team/plans` but pushes to `publishing/plans`
- **THEN** Specwright stops before pushing either branch, names both repositories, and opens or looks up no store PR

#### Scenario: Matching PR beyond the first page
- **WHEN** thirty newer PRs from forks share the change's branch name and base, and the change's own code PR is older and merged
- **THEN** the code PR is still found, stays in the expected set, and counts as merged-code proof for roadmap status

#### Scenario: Inherited GH_REPO names the code repo
- **WHEN** ship and watch run for a store-backed change with `GH_REPO` set to the code repo or a `gh` default repository other than the selected store remote
- **THEN** every store PR lookup, creation, wait and reply targets the selected store remote's repository, and the store PR and code PR are never the same PR

#### Scenario: Store push rejected
- **WHEN** pushing the store branch fails, for example because of a missing permission or a non-fast-forward rejection
- **THEN** Specwright reports the store push error, does not open or update the store PR, and does not report the change as ready

### Requirement: Watch covers the expected PR set
For a store-backed change in `pr` mode, watch SHALL run one wait per expected open PR and report change readiness only when every expected PR is ready and the planning gates are satisfied. When one expected PR merges or closes while another is open, watch SHALL stop all waits and hand off. A missing expected PR SHALL lead to ship, not manual handoff. Archive-before-merge SHALL publish the store archive only when its PR is expected.

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
- **WHEN** all code PR checks and reviews pass under `pr.merge: agent` but the store's selected remote is absent
- **THEN** `pair-state` returns `manual_store_handoff`, not `ready`; watch names the planning branch to share and archive by hand and does not read planning task evidence, prompt for archive, start a store wait, claim change readiness or request merge

#### Scenario: A publishable store PR has not been opened
- **WHEN** the selected store remote is publishable but its expected PR is missing beside a green code PR
- **THEN** `pair-state` returns `ship`, not `manual_store_handoff` or `ready`

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
For a store-backed change with a store PR, one feedback pass SHALL cover every expected PR. A fix to `<root>/openspec/**` SHALL be committed on the store branch, and any other fix on the code branch, whichever PR the finding came from. Without a store PR, store feedback SHALL use the manual handoff.

#### Scenario: Spec fix requested on the code PR
- **WHEN** a reviewer on the code PR of a pair asks for a change to a requirement in the change's spec delta
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
- **WHEN** the store PR is expected, neither branch has a `Feedback-Round` trailer and the code branch has two `address review feedback` commits
- **THEN** the round count is 2

### Requirement: Fix rounds are counted across both branches
With a store PR expected, each fix commit SHALL carry the trailer `Feedback-Round: <n>`. The round limit SHALL count the highest `n` across both branches and SHALL apply only to starting a new pass. Fix commits without a trailer SHALL be counted by their `address review feedback` subject only when neither branch has a `Feedback-Round` trailer.

#### Scenario: Round below the limit
- **WHEN** the store PR is expected, `max_fix_rounds` is 2 and only the store branch has a fix commit, with `Feedback-Round: 1`
- **THEN** the next pass is round 2, and each of its fix commits carries `Feedback-Round: 2`

#### Scenario: Trailer and legacy commits mixed
- **WHEN** the store PR is expected, its branch has a fix commit with `Feedback-Round: 1` and the code branch has two `address review feedback` commits without a trailer
- **THEN** the round count is 1: the commits without a trailer are not counted

### Requirement: Ship pushes every expected repo before it opens a PR
For a store-backed change, ship SHALL discover existing PRs to determine the expected set and first-PR gate, then validate and push every repo of the set, store first, before opening or updating a PR in either repo. When any push fails, ship SHALL open or update no PR in either repo, SHALL report which repo's push failed with its error, and SHALL NOT report the change ready.

#### Scenario: Both pushes succeed
- **WHEN** ship runs for a store-backed change, both PRs are expected and neither exists
- **THEN** both branches are pushed before the first PR is created, and both PRs exist and are linked at the end

#### Scenario: Code push rejected after the store push
- **WHEN** ship runs for a store-backed change with both PRs expected and neither existing, the store push succeeds and the code push is rejected
- **THEN** no PR exists in either repo, the report names the code repo's push and its error, and the change is not reported ready

#### Scenario: Code push rejected with an existing store PR
- **WHEN** the store PR already exists from an earlier ship, a new store commit is pushed, and the code push is rejected
- **THEN** no PR is opened in the code repo, no description, link comment or review request is added to the store PR, and the report names the code push failure

#### Scenario: Store push rejected
- **WHEN** the store push is rejected
- **THEN** the code repo is not pushed, no PR is opened or updated in either repo, and the report names the store push and its error

### Requirement: Cleanup after merge covers every expected PR
After the PRs are merged, `specwright-finish` SHALL, for each repo whose expected PR is MERGED, check out and pull its main under the backend's pull rules, and delete the change branch under the existing merged-head rule. It SHALL delete an empty code branch with `-d`. It SHALL leave the branch of any repo whose expected PR is not merged and report it. Without a store PR, it SHALL leave the store checkout untouched and report the manual handoff.

#### Scenario: Both PRs merged
- **WHEN** both expected PRs are MERGED
- **THEN** both checkouts are on an updated main, both change branches are deleted, and the next branch gate does not report the store as busy

#### Scenario: Only one PR merged
- **WHEN** the code PR is MERGED and the store PR is still open
- **THEN** only the code checkout is cleaned up, the store stays on its change branch, and the report names the open store PR

#### Scenario: Cleanup re-run after the store PR merges
- **WHEN** cleanup runs again after the split above, once the store PR is MERGED and the code branch is already deleted
- **THEN** the store checkout is cleaned up from its selected remote and the code PR is still counted as merged, not as missing

#### Scenario: Code PR merged beside a local-only store
- **WHEN** only the code PR was expected and it has merged
- **THEN** cleanup updates only the code checkout and reports the unchanged planning branch to share and archive by hand
