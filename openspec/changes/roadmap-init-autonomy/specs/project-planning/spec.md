# Spec Delta

## ADDED Requirements

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
In any mode the agent SHALL NOT pass a gate meant for the owner. It SHALL NOT:
- mark a user-verified exit criterion passed;
- write a `Split agreed` line;
- apply an amendment to an agreed split;
- enable a pack;
- publish a release without the owner's yes.

In `autonomous` mode each such item SHALL be recorded as a row awaiting the owner, and the run SHALL go on where the step allows it or stop as the step says.

#### Scenario: Autonomous close with an agreed split and an amendment
- **WHEN** autonomous close promotes a Next with a `Split agreed` line and the milestone suggests dropping one of its changes
- **THEN** the agreed changes are promoted unchanged and in order, and the suggested drop is recorded as a row awaiting the owner

#### Scenario: Autonomous close with an unagreed listing
- **WHEN** autonomous close promotes a Next that lists changes without a `Split agreed` line
- **THEN** the listed changes are promoted in their order, an agent row records that choice, and the new Next is a paragraph with no `Split agreed` line

#### Scenario: Autonomous close with an unverified user criterion
- **WHEN** autonomous close reaches a user-verified exit criterion with no recorded result
- **THEN** the criterion is recorded unverified, the milestone stays in Now, and close stops as it does today

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

## MODIFIED Requirements

### Requirement: Baseline review rounds follow the schema's escalation rule
The baseline review SHALL escalate to the user after 2 consecutive `VERDICT: REVISE` rounds, and SHALL have no lifetime round cap. A pass covers only the content reviewed: a later edit to strategy, architecture or ADRs voids it and SHALL get a new round, except an edit confined to the strategy's decision summary. The acceptance edit (a reviewed ADR's status set to accepted with its date, plus its in-force index row) is part of passing and does not void it. A pass ends a run of REVISE rounds.

#### Scenario: Two consecutive revise verdicts
- **WHEN** rounds 1 and 2 of the baseline review both return `VERDICT: REVISE` in `important` or `all` mode
- **THEN** roadmap stops and asks the user, and writes no roadmap until the user decides (recorded as `VERDICT: USER_OVERRIDE` if they choose to proceed)

#### Scenario: Edit after a passing verdict
- **WHEN** round 2 approved the baseline and a PR fix round then edits `openspec/architecture.md`
- **THEN** a round 3 review of the edited content runs without asking the user, and a REVISE in round 3 alone does not escalate

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
