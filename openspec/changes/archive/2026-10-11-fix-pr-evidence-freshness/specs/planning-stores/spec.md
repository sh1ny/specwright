# Spec Delta

## MODIFIED Requirements

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
