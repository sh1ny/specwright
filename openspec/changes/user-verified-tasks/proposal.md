# Proposal

## Why

Some checks only a person can make: a playtest verdict, a UX sign-off, an owner pointing a real Alertmanager at a dev instance and agreeing with the incidents it raises. Today `tasks.md` has no way to say a task is the user's, so an agent either ticks it on its own judgement or the check stays outside the change and nothing waits for it. The gamedev pack (#68) needs this in core first, and correlia already tags its milestone exit criteria `[agent]` or `[user]` by hand with nothing to carry them into the changes that serve them.

This change serves M6 (Packs), exit criterion: "A task marked as the user's is never ticked by an agent, and verify and archive wait until the user ticks it." It lands before `gamedev-pack`, which builds its playtest tasks on it.

## What Changes

- A tracked task can be marked as the user's: `- [ ] 4.3 [user] <what the user checks>`. An agent never ticks it, never dispatches it to an implementer (a subagent or any other worker), and apply skips it and lists it as waiting on the user.
- An evidence task, `- [ ] 4.2 [evidence] <what to capture> → evidence/<file>`, is an agent task that saves what a user check needs (a build note, a capture, a log) under the change's `evidence/` folder. It is ticked only when that file exists and is committed with it.
- The test map can map a scenario that only a person can judge to its `[user]` task, with state `user` until the user ticks it. That is the user's recorded check, not prose sign-off by the agent.
- When the proposal names a user-verified exit criterion of its milestone, tasks carry it as a `[user]` task, or the proposal says why it can only be judged at the milestone close.
- Apply and the commit check finish when every agent task is done; user tasks wait. A group commit does not wait for its group's user tasks. Once the user ticks one, the next commit that stages `tasks.md` names it in a `Specwright-User-Task` trailer (a `record user checks` commit when no agent work is pending).
- Verify reports unticked user tasks as waiting on the user, never as done. Archive refuses while any `[user]` task is unticked and names them; watch reports the PR ready but waiting on the user and does not archive or merge it.
- `task-cover.sh` reports each task's kind, `waiting_on_user` and uncommitted user ticks, flags a ticked evidence task whose file is missing, and can read `tasks.md` at a given commit, so watch checks the reviewed head before it archives or merges.

## Capabilities

### New Capabilities
- `user-tasks`: tasks only the user ticks and evidence tasks: their markers, how apply, the test map, verify, archive and watch treat them, and how a user-verified milestone criterion reaches them.

### Modified Capabilities
- `task-commits`: a group commit, the end-of-apply check and group recovery no longer wait for or trip on `[user]` tasks; a user task's tick is covered by a `Specwright-User-Task` trailer.

## Impact

- `schemas/specwright/schema.yaml`: tasks instruction (markers, test map state `user`, exit-criterion carry-through) and apply instruction (skip and list user tasks, never dispatch them, evidence rule).
- `schemas/specwright/templates/tasks.md`: marker examples.
- `skills/specwright-commit/SKILL.md` and `scripts/task-cover.sh`: task kinds, `waiting_on_user`, `evidence_missing`, group completeness without user tasks.
- `skills/specwright-finish/SKILL.md` and `skills/specwright-pr/SKILL.md`: the archive gate and watch's waiting-on-user report.
- `templates/openspec/config.yaml`: the archive and verify context lines.
- `agents/claude/*` and `agents/omp/*` implementer definitions: refuse a `[user]` task in a packet.
- `README.md`, `openspec/architecture.md`, evals under `evals/`.
- Packs can ask for `[user]` and `[evidence]` tasks through their rules; nothing in the pack format changes.

## Decision Making

DECISION_MAKING: autonomous
- **Source:** setting (no `decision_making` in openspec/specwright.yaml)

### S1: The user's tick after the PR is ready is a normal push

- **Choice:** a user tick committed after watch reported the PR ready is pushed like any other commit and gets the usual review; the archive-only carry-over is not extended to ticks.
- **Rejected:** treating a tick-only commit like the archive commit (no new review) because it adds a second carry-over rule to `review-run.sh` before any project has shown the extra review round hurts; it can follow as its own issue.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

### S2: Milestone close is unchanged

- **Choice:** roadmap close keeps asking the user for each user-verified exit criterion; ticked user tasks are not read as the criterion's result.
- **Rejected:** close counting a ticked `[user]` task as the criterion passed because a task checks one change's slice while a criterion can span the milestone, and close must never record a pass on the user's behalf.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

### S3: Evidence tasks ship in this change

- **Choice:** `[evidence]` tasks are part of this change, next to `[user]` tasks.
- **Rejected:** user tasks only, evidence later, because the gamedev playtest flow and correlia's owner checks both need something captured for the user to judge, and the roadmap entry names both.
- **Reversal cost:** medium
- **Important:** no
- **Chosen by:** agent

## Release Notes

Tasks can now belong to you. A `[user]` task in `tasks.md` (a playtest verdict, a UX sign-off, an owner's check against a real system) is never ticked or delegated by an agent: apply skips it and lists it as waiting on you, and verify, archive and the agent merge wait until you tick it. An `[evidence]` task captures what your check needs under the change's `evidence/` folder.

### Added
- `[user]` and `[evidence]` task markers: agents never tick or dispatch user tasks, the test map can point a scenario at its user task, and archive and the agent merge wait for your tick (#68).

### Changed
- With `commit_granularity: group`, a group commit no longer waits for the group's user tasks, and the end-of-apply check hands off with user tasks still open (#68).
