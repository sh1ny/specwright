# decision-making Specification

## Purpose

Lets a project choose how far the user is kept in the loop on the decisions made while a change is planned: the agent decides and reports, only important decisions go to the user, or every decision does.

## Requirements

### Requirement: The decision mode comes from the setting
Planning SHALL read `decision_making` from `openspec/specwright.yaml` in the code repo. `autonomous`, `important` and `all` are the valid values; no setting means `autonomous`. Any other value SHALL stop planning before a decision is written, naming the value and the three valid values.

#### Scenario: Setting unset
- **WHEN** a change is planned in a project whose `openspec/specwright.yaml` has no `decision_making` key
- **THEN** the change's `proposal.md` records the mode `autonomous` from the setting, and no decision is put to the user

#### Scenario: Setting has an unknown value
- **WHEN** `decision_making` is `ask`
- **THEN** planning stops before any Decisions entry is written, and the message names `ask` and `autonomous`, `important` and `all`

### Requirement: A user instruction overrides the mode for one change
An instruction from the user when a change starts, naming a mode or saying how much to be asked, SHALL set the mode for that change only. `proposal.md`, the first artifact written, SHALL record the mode in force and its source: `setting`, or `user` with the user's words. Later sessions of the change SHALL use the recorded mode; a `proposal.md` with no recorded mode SHALL use the setting.

#### Scenario: Override recorded
- **WHEN** the setting is `autonomous` and the user starts a change saying "ask me everything for this one"
- **THEN** that change's `proposal.md` records the mode `all` with source `user` and the user's words, and the setting file is unchanged

#### Scenario: Session resumes after the proposal, without the conversation
- **WHEN** the setting is `autonomous`, the user overrode it to `all` and answered two scope decisions, and the session ended after `proposal.md` was written and before `design.md`
- **THEN** a new session with no conversation history reads the mode `all` and both scope decisions as `Chosen by: user` from `proposal.md`, and puts every design decision to the user

#### Scenario: Next change after an override
- **WHEN** the next change starts with no instruction from the user
- **THEN** its `proposal.md` records the mode from the setting with source `setting`

#### Scenario: Change planned before this feature
- **WHEN** apply or a review fix round runs on a change whose `proposal.md` has no recorded mode
- **THEN** the mode is read from the setting, and no artifact is rewritten for the missing line

### Requirement: Every decision records its importance and who chose it
A decision SHALL be each `design.md` Decisions entry, and each scope or non-goal choice, recorded in `proposal.md`'s Decision Making section. Each SHALL record whether it is important and who chose it: `user` when the user chose or stated it, in any mode, else `agent`. A decision SHALL be important when it has high reversal cost, binds future changes (contract, data format, config key, boundary), changes behaviour or settings users see, or is chosen on weak evidence.

#### Scenario: Config key decision
- **WHEN** a design decision adds a configuration key
- **THEN** its entry records `Important: yes` and names the criterion it meets

#### Scenario: Tactical decision
- **WHEN** a decision has low reversal cost, binds no later change, changes nothing users see and rests on code evidence
- **THEN** its entry records `Important: no`

#### Scenario: Not a decision
- **WHEN** planning chooses the wording of a message, the order of tasks or the layout of a test
- **THEN** no Decisions entry is written for it

### Requirement: Every change carries a decision summary
`design.md` SHALL hold a decision summary table with one row per decision, scope decisions from `proposal.md` included: the decision, the choice, the rejected alternatives, the reversal cost, whether it is important and who chose it. At the end of planning, before apply, the same table SHALL be shown to the user. In `autonomous` mode planning SHALL NOT wait for an answer to it.

#### Scenario: Autonomous planning ends
- **WHEN** a change is planned in `autonomous` mode and the user stated no choice beforehand
- **THEN** every decision is chosen by the agent, `design.md` holds the summary table with each row `agent`, the table is shown to the user at the end of planning, and planning ends without a question

#### Scenario: Autonomous with a choice the user stated
- **WHEN** a change is planned in `autonomous` mode and the user named the setting key before planning began
- **THEN** that decision is recorded `Chosen by: user` without a question, the other decisions `Chosen by: agent`, and planning ends without a question

#### Scenario: Summary out of step with the decisions
- **WHEN** a Decisions entry is added, removed or changed after the summary was written
- **THEN** the summary table is updated in the same edit, so its rows match the Decisions entries one to one

### Requirement: Decisions go to the user per the mode
In `important` mode each important decision, and in `all` mode every decision, SHALL be put to the user before it is written: 2 to 4 options, one marked recommended, and an option to discuss. Questions SHALL go in batches of at most 4, or the usable ask tool's lower limit, through that tool; options fit its limit, keeping the recommended one and a way to discuss. Plain text is only the fallback when no ask tool is usable in the session or mode. Other decisions are taken by the agent.

#### Scenario: Important mode
- **WHEN** a change in `important` mode has one important and two tactical decisions
- **THEN** only the important one is put to the user with options and a recommended one, its entry records `Chosen by: user`, and the two tactical ones record `Chosen by: agent`

#### Scenario: All mode
- **WHEN** a change in `all` mode has three decisions
- **THEN** all three are put to the user before `design.md` is written, and each entry records `Chosen by: user`

#### Scenario: Ask tool that takes four questions
- **WHEN** a change in `all` mode has six decisions and the usable ask tool takes up to 4 questions per call
- **THEN** the questions go through that tool in batches of at most 4, and all six are asked

#### Scenario: Ask tool that takes three questions
- **WHEN** a change in `all` mode has six decisions and the usable ask tool takes at most 3 questions per call
- **THEN** the questions go through that tool in batches of at most 3, and all six are asked

#### Scenario: Ask tool with a smaller option limit
- **WHEN** a decision has three alternatives and the usable ask tool takes at most 3 options per question
- **THEN** the question fits the limit, keeps the recommended option marked, and still offers a way to discuss, through the tool's free-text answer when it has one, else as one of the options

#### Scenario: Ask tool not usable in the current mode
- **WHEN** the harness has an ask tool that the current session or mode does not allow
- **THEN** the batch is printed as plain text with lettered options, the recommended one marked and a discuss option, and planning waits for the answer before writing the decisions

#### Scenario: Harness without an ask tool
- **WHEN** the harness offers no ask tool
- **THEN** the batch is printed as plain text with lettered options, the recommended one marked and a discuss option, and planning waits for the answer before writing the decisions

#### Scenario: User asks to discuss
- **WHEN** the user picks the option to discuss for a decision
- **THEN** that decision is not written until the discussion ends with a choice, and the choice is recorded `Chosen by: user`

#### Scenario: User hands the decision back
- **WHEN** the user answers a decision with "you decide"
- **THEN** the agent takes the recommended option and records `Chosen by: agent`, noting that the user handed it back

### Requirement: A user-chosen decision changes only with the user
A decision recorded `Chosen by: user` SHALL NOT be changed without the user, in any mode. When a design review's required change, a review fix round or apply drift would change it, the agent SHALL put the change to the user first, with options and a recommended one.

#### Scenario: Reviewer asks to change a user choice
- **WHEN** a design review returns `APPROVE_WITH_CHANGES` with a required change that reverses a `Chosen by: user` decision
- **THEN** the agent asks the user before editing that decision, and the decision stays as the user chose it until they answer

#### Scenario: Autonomous mode, review or drift would replace a user choice
- **WHEN** a change in `autonomous` mode holds a `Chosen by: user` decision and a review's required change or drift found during apply would replace it
- **THEN** the agent asks the user first, and the decision, its entry and its summary row stay unchanged until the user answers

#### Scenario: Reviewer changes only agent choices
- **WHEN** every required change touches only `Chosen by: agent` decisions in `autonomous` mode
- **THEN** the agent applies them without asking and updates the summary table

### Requirement: Decisions changed after planning follow the mode
A decision added or changed after planning, by a review fix round or by drift found during apply, SHALL follow the change's mode: put to the user in `all` mode, put to the user in `important` mode when it is important, and taken by the agent and recorded otherwise. Each SHALL update the Decisions entry and the summary table.

#### Scenario: Drift in important mode
- **WHEN** apply finds an important design decision wrong in a change in `important` mode
- **THEN** that work stops and the replacement decision is put to the user before the design is amended

#### Scenario: Drift in autonomous mode
- **WHEN** apply finds a `Chosen by: agent` design decision wrong in a change in `autonomous` mode
- **THEN** the agent amends the decision, keeps `Chosen by: agent` and updates the summary table without asking, and the review step runs again as drift requires

### Requirement: The setting is documented where it is set
The installed `openspec/specwright.yaml` template SHALL carry `decision_making: autonomous` with a comment naming the three values, and the README settings block SHALL describe it. Init SHALL NOT ask about it.

#### Scenario: Fresh install
- **WHEN** Specwright is installed into a project
- **THEN** the project's `openspec/specwright.yaml` names `decision_making` with the value `autonomous` and a comment naming `autonomous`, `important` and `all`

#### Scenario: Existing project updated
- **WHEN** an existing project without the key is updated
- **THEN** planning behaves as `autonomous`, and the update does not stop for the missing key
