# project-planning Specification

## Purpose
Defines how `specwright-roadmap` records architecture decisions, reviews the project baseline, and commits roadmap edits, so project-level planning never needs a manual rescue.

## Requirements

### Requirement: ADRs stay proposed until the review gate passes
Roadmap **init** SHALL write baseline ADRs, and **close** any superseding ADR, with `Status: proposed`. Each SHALL be changed to `Status: accepted` with the acceptance date only after the baseline review gate passes for the content being accepted. The architecture's in-force ADR index SHALL list only accepted ADRs. An accepted ADR SHALL NOT be edited once it is on main; a later decision change SHALL be a new superseding ADR.

#### Scenario: Baseline passes review
- **WHEN** init writes ADRs 0001-0004 and the baseline review returns `VERDICT: APPROVE`
- **THEN** the committed ADRs read `Status: accepted` with that day's date, the roadmap is written only after that, and no further review round runs because of the acceptance edit

#### Scenario: Review asks to change a decision
- **WHEN** the baseline review returns `VERDICT: REVISE` with a finding against ADR 0002
- **THEN** ADR 0002 is edited in place while it still reads `Status: proposed`, and no superseding ADR is created

#### Scenario: Close supersedes an accepted ADR
- **WHEN** close finds that the decision in ADR 0003, accepted and on main, no longer holds
- **THEN** close writes a new ADR with `Status: proposed` and `Supersedes: 0003`, reviews it as the baseline is reviewed, accepts it only after that gate passes, and leaves ADR 0003's file unchanged

### Requirement: Baseline review rounds follow the schema's escalation rule
The baseline review SHALL escalate to the user after 2 consecutive `VERDICT: REVISE` rounds, and SHALL have no lifetime round cap. A pass covers only the content reviewed: a later edit to strategy, architecture or ADRs voids it and SHALL get a new round, except an edit confined to the strategy's decision summary. The acceptance edit (a reviewed ADR's status set to accepted with its date, plus its in-force index row) is part of passing and does not void it. A pass ends a run of REVISE rounds.

#### Scenario: Two consecutive revise verdicts
- **WHEN** rounds 1 and 2 of the baseline review both return `VERDICT: REVISE` in `important` or `all` mode
- **THEN** roadmap stops and asks the user, and writes no roadmap until the user decides (recorded as `VERDICT: USER_OVERRIDE` if they choose to proceed)

#### Scenario: Edit after a passing verdict
- **WHEN** round 2 approved the baseline and a PR fix round then edits `openspec/architecture.md`
- **THEN** a round 3 review of the edited content runs without asking the user, and a REVISE in round 3 alone does not escalate

### Requirement: Gap-closing roadmap edit is committed on the new change's branch
When no planned change of the Now milestone is left and an exit criterion fails, as found by roadmap **close** or reported by the user, roadmap **next** SHALL leave the roadmap untouched until the branch gate has created the gap-closing change's branch. It SHALL then add the change to the roadmap and commit only the roadmap file by name on that branch, before any planning artifact commit. Main SHALL stay unchanged.

#### Scenario: Criterion fails with no change left
- **WHEN** every change of M1 is done, close finds the agent-verified criterion "evals/pr-pair passes" failing, and the user accepts the proposed change `fix-pr-pair-suite`
- **THEN** branch `bugfix/fix-pr-pair-suite` holds a commit that changes only the roadmap file and adds `fix-pr-pair-suite` to M1, main has no new commit, and the branch gate did not stop on a dirty tree

#### Scenario: Branch gate stops
- **WHEN** the branch gate for the gap-closing change stops, for example because main is not clean
- **THEN** the roadmap file is unchanged and no roadmap commit exists on any branch

#### Scenario: No criterion shown failing
- **WHEN** every change of M1 is done and neither close nor the user has shown an exit criterion failing
- **THEN** next proposes no gap-closing change and offers close instead

### Requirement: A milestone end offers close, not a new change
When every change of the Now milestone is done, roadmap **next** SHALL report a milestone end, offer **close** and start no change, create no branch and edit no file, unless an exit criterion was shown failing by **close** or reported failing by the user: then the gap-closing requirement applies. **next** SHALL start only changes of the Now milestone. A change that is not done keeps the milestone open: next reports what it waits for.

#### Scenario: All changes done, criteria not yet walked
- **WHEN** every change of M1 is done, M1 has a user-verified exit criterion with no recorded result, and the user runs next
- **THEN** next reports that M1 is at its end and offers close, no branch or change directory is created, and the roadmap file is unchanged

#### Scenario: Next milestone already split
- **WHEN** every change of M1 is done and Next (M2) lists agreed changes, and the user runs next
- **THEN** next offers close and does not start M2's first change

#### Scenario: Last change archived but code pending
- **WHEN** M1's last change is archived on the store's main but its code PR is still open
- **THEN** next does not offer close: it reports the change as planning merged, code pending, and names the code PR it waits for

#### Scenario: Close found a criterion failing
- **WHEN** every change of M1 is done, close found an exit criterion failing and routed to next
- **THEN** next proposes a gap-closing change instead of offering close again, and follows the gap-closing requirement

### Requirement: Status names a milestone end
Roadmap **status** SHALL name `milestone end: run close` as what **next** would do when every change of the Now milestone is done, unless an exit criterion was shown failing by **close** or reported failing by the user: then it SHALL name the gap-closing change next would propose. Otherwise it SHALL name the change next would start, or what next waits for when no change is ready to start.

#### Scenario: Status at a milestone end
- **WHEN** every change of M1 is done and the user asks for roadmap status
- **THEN** status reports each change as done and names `milestone end: run close` as what next would do, instead of a change

#### Scenario: Status after close found a criterion failing
- **WHEN** every change of M1 is done, close found an exit criterion failing, and the user asks for roadmap status
- **THEN** status names the gap-closing change next would propose, not `milestone end: run close`

#### Scenario: Status with a change left
- **WHEN** M1 has a planned change whose prerequisites are done and the user asks for roadmap status
- **THEN** status names that change as what next would start and does not report a milestone end

#### Scenario: Status while a change's code is pending
- **WHEN** M1's only change left is archived on main but its code PR is still open, and the user asks for roadmap status
- **THEN** status names the code PR next waits for, names no change to start, and does not report a milestone end

### Requirement: Finish offers close after the milestone's last change
When the roadmap exists and a change reaches main, `specwright-finish` SHALL offer roadmap **close** when every change of the Now milestone is then done, and **next** otherwise. It SHALL NOT offer both as alternatives.

#### Scenario: Last change of the milestone merged
- **WHEN** the PR of M1's last planned change is merged and finish cleans up
- **THEN** finish offers close for M1 and does not offer next

#### Scenario: Changes left in the milestone
- **WHEN** the PR of M1's first of three changes is merged and finish cleans up
- **THEN** finish offers next and does not offer close

### Requirement: An agreed Next split is recorded
Roadmap **init** and **close** SHALL split only the Now milestone into changes, unless the author explicitly agrees a split for Next. A Next milestone with an agreed split SHALL list its changes and record the agreement with its date in a `Split agreed: <YYYY-MM-DD>` line, which close drops when it promotes that milestone to Now.

#### Scenario: Author agrees a Next split at init
- **WHEN** during init the author explicitly agrees that M2 is split into three named changes
- **THEN** the roadmap's Next (M2) lists those three changes and a `Split agreed:` line with that day's date

#### Scenario: Close records a split agreed for the new Next
- **WHEN** close promotes M2 to Now and the author explicitly agrees that M3, the new Next, is split into two named changes
- **THEN** the closed roadmap's Next (M3) lists those two changes and a `Split agreed:` line with that day's date

#### Scenario: Init without an agreed Next split
- **WHEN** init writes a roadmap and the author did not agree a split for Next
- **THEN** only Now lists changes, and Next is a paragraph with no `Split agreed:` line

### Requirement: Close keeps an agreed Next split
When **close** promotes a Next milestone with a `Split agreed:` line, it SHALL keep those changes, their names and their order, and SHALL propose any amendment the finished milestone suggests to the user instead of applying it. In `important` and `all` mode close SHALL ask the user before re-splitting a Next that lists changes without that line; in `autonomous` mode it SHALL promote that listing as it stands and record the choice. A Next without changes SHALL be split as before.

#### Scenario: Close promotes an agreed split
- **WHEN** M1 is done, its exit criteria pass, and Next (M2) lists five changes with `Split agreed: 2026-10-01`
- **THEN** after close, Now is M2 with the same five changes in the same order and with the same names and no `Split agreed:` line, and M1 is in Done

#### Scenario: Close finds a reason to amend the agreed split
- **WHEN** M1 taught that one of M2's agreed changes is no longer needed and close runs in `important` or `all` mode
- **THEN** close proposes removing it and asks the user; without the user's agreement the roadmap keeps all five changes

#### Scenario: Amendment to an agreed split in autonomous mode
- **WHEN** M1 taught that one of M2's agreed changes is no longer needed and close runs in `autonomous` mode
- **THEN** close asks nothing, the roadmap keeps all five changes, and the decision summary holds a row awaiting the owner that proposes removing it

#### Scenario: Next without a split
- **WHEN** Next (M2) is one paragraph with no changes
- **THEN** close splits M2 into changes when it promotes it, as before

#### Scenario: Next lists changes without a recorded agreement
- **WHEN** Next (M2) lists four changes but has no `Split agreed:` line and close runs in `important` mode
- **THEN** close asks the user whether that split is agreed; on yes Now is M2 with those four changes in the same order, and on no close splits M2 as before

#### Scenario: Unagreed listing in autonomous mode
- **WHEN** Next (M2) lists four changes but has no `Split agreed:` line and close runs in `autonomous` mode
- **THEN** close asks nothing, Now is M2 with those four changes in the same order, and the decision summary holds an agent row recording that choice

### Requirement: Close offers untagged releases
With `release.enabled` true, roadmap **close** SHALL list the versions `release.sh untagged` lists (run fenced with the run login; a version is published when its tag is on origin, or with no origin remote a local tag), and offer to publish them oldest first. It SHALL NOT publish without the user's yes, and a refused or failed publish SHALL NOT block the close.

#### Scenario: Versions left untagged
- **WHEN** close runs, `v0.5.0` is the latest tag on origin and main's version history reads 0.5.0, 0.5.1, 0.6.0 with no tag on origin for the last two
- **THEN** close lists 0.5.1 and 0.6.0 and offers to publish them in that order

#### Scenario: Everything tagged
- **WHEN** every version since the latest published tag has its tag on origin, and no local tag is missing from origin
- **THEN** close offers no release

#### Scenario: No tag yet
- **WHEN** close runs in a project with no tag on origin and none locally, and main's version is 0.3.0
- **THEN** close offers to publish 0.3.0 only

#### Scenario: User declines
- **WHEN** close offers 0.6.0 and the user declines
- **THEN** no tag is created and close continues with the milestone move

#### Scenario: Releases disabled
- **WHEN** `release.enabled` is false
- **THEN** close lists no versions and offers no release

### Requirement: A parked change is never resumed
Roadmap **next** SHALL NOT offer to resume an active change whose `review.md` holds `VERDICT: DEFERRED`: it is a parked change, never applied. **next** SHALL go on to pick the milestone's next change as if the parked change were not active, and **status** SHALL list it as `parked` with its `Deferred to:` targets. Every other active change SHALL still be offered for resume.

#### Scenario: Only a parking change is active
- **WHEN** `openspec list --json` shows only `platform-backlog`, whose `review.md` holds `VERDICT: DEFERRED`, and the Now milestone's first planned change has no archive and no unmet prerequisite
- **THEN** next does not offer to resume `platform-backlog` and starts the first planned change

#### Scenario: Status shows the parked change
- **WHEN** the user runs status while `platform-backlog` is active with `VERDICT: DEFERRED` and `Deferred to: M2 changes, M3 changes`
- **THEN** status lists `platform-backlog` as `parked`, with those targets, and not as active

#### Scenario: Parking change and a change in progress
- **WHEN** `platform-backlog` is parked and `add-sync`, whose `review.md` holds `VERDICT: APPROVE`, is also active
- **THEN** next offers to resume `add-sync`, not `platform-backlog`

#### Scenario: Next run on the parking change's branch
- **WHEN** the user runs next while the checkout is on `feat/platform-backlog`, whose change is parked
- **THEN** next says the parking change is on its own branch and next starts from main once it has merged, and creates no branch and no change

#### Scenario: Active change with no review yet
- **WHEN** an active change has no `review.md`
- **THEN** next offers to resume it as before, since it is not parked

### Requirement: The baseline gate passes only a review or an escalation
Roadmap **init** SHALL write the roadmap, and **init** or **close** SHALL accept a reviewed ADR, only when `openspec/architecture-review.md` holds `VERDICT: APPROVE`, `VERDICT: APPROVE_WITH_CHANGES` with `CHANGES_APPLIED: yes`, or `VERDICT: USER_OVERRIDE` after escalation. `DEFERRED`, `WAIVED` and `SKIPPED_LIGHT` SHALL NOT pass the baseline gate.

#### Scenario: Baseline passes review
- **WHEN** the baseline review returns `VERDICT: APPROVE`
- **THEN** init accepts the reviewed ADRs and writes the roadmap

#### Scenario: Baseline recorded as waived or deferred
- **WHEN** `openspec/architecture-review.md` holds `VERDICT: WAIVED` or `VERDICT: DEFERRED`
- **THEN** init writes no roadmap, every ADR stays `Status: proposed`, and the user is told the baseline needs a review

### Requirement: A parking change is never a milestone change
A parking change SHALL NOT be listed in a milestone's Changes, since it is never archived and so never done. When **next**, **close** or **status** find a listed change that is parked, they SHALL report it as parked and listed in error, SHALL neither start it nor count it done, and SHALL say that removing it from Changes is the user's planning edit. **next** and **close** SHALL then stop. The skill SHALL NOT edit the roadmap to remove it.

#### Scenario: Close with a parked change listed
- **WHEN** the Now milestone lists `platform-backlog`, whose `review.md` holds `VERDICT: DEFERRED`, and every other listed change is done
- **THEN** close reports `platform-backlog` as parked and listed in error, says removing it from Changes is the user's edit, does not close the milestone, and leaves `openspec/roadmap.md` unchanged

#### Scenario: Next reaches a parked listed change
- **WHEN** the first Now change with no archive is `platform-backlog`, which is parked
- **THEN** next does not start it, creates no branch and no change, and reports it as parked and listed in error

#### Scenario: Status with a parked listed change
- **WHEN** status runs while the Now milestone lists the parked `platform-backlog`
- **THEN** status lists it as `parked (listed in error)`, and does not report `milestone end: run close`

#### Scenario: Parking change not listed
- **WHEN** `platform-backlog` is parked, it is not listed in any milestone, and every listed change of Now is done
- **THEN** next reports `milestone end: run close` as before

### Requirement: Roadmap init suggests packs and never enables one by itself
Roadmap **init** SHALL compare the code checkout's tracked and untracked, non-ignored files with the `signals` of every pack in the catalogue of `openspec/.specwright/packs.json` and offer each matching pack that is not enabled, with the signal and the packs it requires, as one offer. Only on the user's yes SHALL it add the pack under `packs:` in `openspec/specwright.yaml`, and it SHALL then tell the user to rerun the install prompt and run roadmap **pack** `<name>`.

#### Scenario: A Godot project is offered the game packs
- **WHEN** init runs in a checkout holding `project.godot` and no pack is enabled
- **THEN** init offers `gamedev` and `godot`, naming `project.godot` as the signal and `ui-prototyping` as required by `gamedev`, even when `project.godot` is not committed yet, says that packs install only into in-repo skills directories and that a user-level install refuses them, and `specwright.yaml` is unchanged until the user answers

#### Scenario: The user declines
- **WHEN** the user declines an offered pack
- **THEN** `packs:` is unchanged and init continues with its core interview

### Requirement: Roadmap init's pack offer names the in-repo install need
Every pack offer roadmap **init** makes SHALL say that packs install only into in-repo skills directories and that an install at user level refuses them (`packs_user_level`).

#### Scenario: A pack offer in a project that installs at user level
- **WHEN** init offers any catalogued pack whose signal matches the checkout
- **THEN** the offer says that packs install only into in-repo skills directories and that a user-level install refuses them with `packs_user_level`

### Requirement: Roadmap init offers no pack where the install refuses packs
Roadmap **init** SHALL offer no pack when the planning root is a store, where the install refuses packs in v1, and SHALL say that packs are not supported there yet.

#### Scenario: A project where packs cannot be installed
- **WHEN** init runs with a store-backed planning root, in a checkout holding `project.godot`
- **THEN** init offers no pack, says that packs are not supported there yet, and `specwright.yaml` gains no `packs:` key

#### Scenario: A repo-local Git project
- **WHEN** init runs with `vcs: git`, a repo-local planning root and `project.godot`
- **THEN** init offers the matching packs as above

### Requirement: Roadmap init includes enabled packs' questions and documents
When packs are enabled in `openspec/.specwright/packs.json`, roadmap **init** SHALL treat their init questions like its own gaps under the run's decision mode (in `important` and `all` mode, within its at most two batched rounds, each with a recommended default), write the answers into each pack document, and name those documents in the baseline review request as context. Pack documents SHALL NOT be gated content: editing one never voids a baseline verdict.

#### Scenario: Pack questions join the interview
- **WHEN** `gamedev` is installed with four init questions and init interviews the user
- **THEN** the four questions are asked in init's batched rounds, no third round is added, and the baseline review request names `docs/game/gdd.md` as context

#### Scenario: Pack questions in an autonomous init
- **WHEN** `gamedev` is installed with four init questions and init runs in `autonomous` mode
- **THEN** no question is asked, the four answers are written into `docs/game/gdd.md`, and each is a row of the strategy's decision summary with `Chosen by: agent`

#### Scenario: A pack document edited after the baseline passed
- **WHEN** the baseline holds `VERDICT: APPROVE` and a later change edits `docs/game/gdd.md`
- **THEN** the baseline verdict stands and no new baseline round is started

#### Scenario: A pack document is missing at init
- **WHEN** `packs.json` lists `docs/game/gdd.md` and the file does not exist
- **THEN** init tells the user to rerun the install prompt to create it, and does not create it from memory

### Requirement: Roadmap pack mode sets up a pack enabled later
Roadmap **pack** `<name>` SHALL run for an enabled, installed pack. It SHALL take the pack's init questions under the run's decision mode (one batched round with recommended defaults in `important` and `all` mode, answered by the agent and recorded in `autonomous` mode), write the answers into the pack's documents without removing user content, run no review round, change no baseline verdict, and commit what it wrote on `docs/pack-<name>`, never on main.

#### Scenario: Setting up a pack after the baseline
- **WHEN** a project with an approved baseline installs `web` and runs roadmap **pack** `web`
- **THEN** the web questions are asked once, the web documents hold the answers in a commit on `docs/pack-web` finished per the `finish` setting, main's working tree is clean, and `openspec/architecture-review.md` is unchanged

#### Scenario: The pack is not installed
- **WHEN** roadmap **pack** `web` runs and `packs.json` does not list `web`
- **THEN** it writes no file and says to add `web` under `packs:` and rerun the install prompt

### Requirement: Roadmap runs read their decision mode from the project setting
Roadmap **init**, **close** and **pack** SHALL read `project.decision_making` from `openspec/specwright.yaml` in the code repo: `autonomous`, `important` or `all`. An unset key SHALL mean `important`. Any other value SHALL stop the run before any file is written or branch created, naming the value and the three valid values. The top-level `decision_making` SHALL NOT set the roadmap mode.

#### Scenario: Key unset
- **WHEN** init runs in a project whose `specwright.yaml` has no `project.decision_making` and sets `decision_making: autonomous`
- **THEN** init runs in `important` mode: it asks the gaps that would change the architecture or the first milestone, in at most two batched rounds, each with a recommended default

#### Scenario: Unknown value
- **WHEN** `project.decision_making` is `ask`
- **THEN** the run stops before any branch or file write, and the message names `ask` and `autonomous`, `important` and `all`

#### Scenario: Change planning keeps its own setting
- **WHEN** `project.decision_making` is `autonomous`, `decision_making` is `all`, and **next** starts a change
- **THEN** the change's `proposal.md` records `DECISION_MAKING: all` with source `setting`, and its decisions are put to the user

### Requirement: A user instruction overrides the roadmap mode for one run
An instruction from the user when a roadmap run starts, naming a mode or saying how much to be asked ("decide yourself for this roadmap"), SHALL set the mode for that run only and SHALL NOT change `openspec/specwright.yaml`. The run SHALL record the mode in force and its source, `setting` or `user` with the user's words, in the strategy's decision summary.

#### Scenario: Override at init
- **WHEN** the key is unset and the user starts init saying "decide yourself for this roadmap"
- **THEN** init asks nothing, the strategy's decision summary records the mode `autonomous` with source `user` and those words, and `specwright.yaml` is unchanged

#### Scenario: Next run without an instruction
- **WHEN** close runs later with no instruction from the user and the key is unset
- **THEN** close runs in `important` mode with source `setting`, whatever mode init ran in

### Requirement: An autonomous roadmap run asks nothing and records every answer
In `autonomous` mode init, close and pack SHALL put no question to the user. Each interview gap, pack question, foundational ADR choice and re-plan choice SHALL be taken by the agent and recorded as a row of the strategy's decision summary with `Chosen by: agent` and the reason it was chosen. The run SHALL show the rows it added at its end without waiting for an answer.

#### Scenario: Autonomous init
- **WHEN** init runs with `project.decision_making: autonomous` and the brief leaves the platform and the data sensitivity open
- **THEN** no question is asked, the decision summary holds a row for each with the chosen answer, the reason and `Chosen by: agent`, and the rows are shown at the end of the run

#### Scenario: Autonomous pack setup
- **WHEN** roadmap **pack** `gamedev` runs in `autonomous` mode
- **THEN** no question is asked, each pack question's answer is written into the pack document, and each is recorded as an agent row

#### Scenario: Pack offer at an autonomous init
- **WHEN** autonomous init finds `project.godot` and `gamedev` is not enabled
- **THEN** init does not enable the pack, records the offer as a row awaiting the owner, and `specwright.yaml` gains no `packs:` entry

### Requirement: A question round may span several ask-tool calls
A roadmap question round SHALL be one set of questions put to the user together, before any answer of that set is written. It MAY take several ask-tool calls when the usable tool takes fewer questions per call than the round holds. No question of a round SHALL be dropped or taken by the agent to fit a tool's limit in `important` or `all` mode.

#### Scenario: Init round larger than the ask tool
- **WHEN** init in `important` mode has six gaps and four pack questions and the usable ask tool takes at most 3 questions per call
- **THEN** the ten questions are asked in at most two rounds, through as many calls as needed, every question is asked, and no third round is added

#### Scenario: Pack round larger than the ask tool
- **WHEN** roadmap **pack** has four questions and the usable ask tool takes at most 3 questions per call
- **THEN** the four questions form one round asked through two calls, and the documents are written only after both calls are answered

### Requirement: In all mode every roadmap decision goes to the user
In `all` mode init, close and pack SHALL put every interview gap, pack question, foundational ADR choice and re-plan choice to the user, each with options and a recommended one, before the file that holds it is written. The gap interview SHALL keep its two-round cap; the ADR and re-plan choices SHALL go in further batches of at most 4 questions, or fewer when the usable ask tool takes fewer.

#### Scenario: ADR choices in all mode
- **WHEN** init runs in `all` mode and drafts five foundational ADR choices after a two-round interview
- **THEN** the five choices are put to the user in batches of at most 4 before the ADRs are written, and each row records `Chosen by: user`

#### Scenario: Session ends before the answers
- **WHEN** an `all`-mode init session ends after a batch of ADR choices is asked and before it is answered
- **THEN** no ADR for those choices exists, and the next session asks them again

### Requirement: The strategy carries the roadmap's decision summary
The strategy SHALL hold a `## Decision summary` section in place of the free-form Assumptions list: a mode line with its source, then one row per decision taken in a roadmap run (decision, choice, rejected alternatives, reason, important, chosen by), in every mode. An edit confined to that section SHALL NOT void a baseline verdict. A strategy with an older `## Assumptions` list SHALL be read as it is and SHALL NOT be rewritten.

#### Scenario: Close adds rows after the baseline passed
- **WHEN** the baseline holds `VERDICT: APPROVE` and an autonomous close adds two rows to the decision summary
- **THEN** the verdict stands and no new baseline round runs

#### Scenario: PR feedback fixes only summary rows
- **WHEN** a PR fix round on `docs/close-m2` edits only rows of the strategy's `## Decision summary`
- **THEN** the fix is committed and reported done without a new baseline review round, and `openspec/architecture-review.md` is unchanged

#### Scenario: Edit outside the section
- **WHEN** a close also edits the strategy's Boundaries section
- **THEN** that edit voids the baseline verdict and a new round runs as before

#### Scenario: Pending rows at the next close
- **WHEN** the summary holds two `pending` rows from an autonomous init and close runs in `important` mode
- **THEN** close lists both rows at its start and puts them to the owner, and each answered row reads `Chosen by: user` with the answer

#### Scenario: Strategy written before this change
- **WHEN** close runs on a project whose strategy has `## Assumptions` and no decision summary
- **THEN** the Assumptions list is unchanged and close adds a `## Decision summary` section for its own rows

### Requirement: Autonomy never passes a gate meant for the owner
In any mode the agent SHALL NOT supply the owner's agreement itself. Without the owner's explicit agreement it SHALL NOT:
- mark a user-verified exit criterion passed;
- write a `Split agreed` line;
- apply an amendment to an agreed split;
- enable a pack;
- publish a release.

In `autonomous` mode each such item SHALL be a row awaiting the owner, and the run SHALL go on where the step allows. A step that stops before its branch exists SHALL write nothing and report the item.

#### Scenario: Autonomous close with an agreed split and an amendment
- **WHEN** autonomous close promotes a Next with a `Split agreed` line and the milestone suggests dropping one of its changes
- **THEN** the agreed changes are promoted unchanged and in order, and the suggested drop is recorded as a row awaiting the owner

#### Scenario: Autonomous close with an unagreed listing
- **WHEN** autonomous close promotes a Next that lists changes without a `Split agreed` line
- **THEN** the listed changes are promoted in their order, an agent row records that choice, and the new Next is a paragraph with no `Split agreed` line

#### Scenario: Autonomous close with an unverified user criterion
- **WHEN** autonomous close reaches a user-verified exit criterion with no recorded result
- **THEN** close stops before it creates `docs/close-<milestone>`: no branch is created, no file is written and main stays clean, the milestone stays in Now, and the run's report lists the criterion as unverified; the next close walks the criteria again and finds it

#### Scenario: Owner agrees in an interactive run
- **WHEN** init runs in `important` mode, offers `gamedev` for a found `project.godot`, and the user answers yes
- **THEN** `gamedev` is added under `packs:` in `openspec/specwright.yaml`, as the owner agreed it

#### Scenario: Autonomous close with untagged versions
- **WHEN** autonomous close finds versions with no tag on origin and `release.enabled` is true
- **THEN** nothing is published, and the versions are listed as a row awaiting the owner

### Requirement: An autonomous baseline escalation stops the run
In `autonomous` mode, 2 consecutive `VERDICT: REVISE` baseline rounds SHALL stop the run instead of asking: no roadmap is written, every reviewed ADR stays `Status: proposed`, no `VERDICT: USER_OVERRIDE` is written, and the escalation is recorded as a row awaiting the owner. Before a round replaces `openspec/architecture-review.md`, an autonomous run SHALL copy the earlier round's findings into its summary rows.

#### Scenario: Round 1 findings kept when round 2 replaces the file
- **WHEN** an autonomous init gets `VERDICT: REVISE` in round 1 and is about to run round 2
- **THEN** the decision summary already holds round 1's findings, each with its severity and one line, before round 2's review replaces `openspec/architecture-review.md`

#### Scenario: Two consecutive revise verdicts in autonomous mode
- **WHEN** an autonomous init gets `VERDICT: REVISE` in rounds 1 and 2
- **THEN** the run stops without asking, `openspec/roadmap.md` is not written, every ADR reads `Status: proposed`, no `VERDICT: USER_OVERRIDE` is written, `openspec/architecture-review.md` holds round 2's review, and the decision summary holds a row awaiting the owner that lists round 1's findings, each with its severity and one line
