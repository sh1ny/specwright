---
name: gamedev-playtest
description: "Plan and record player playtests for a game change. Use when player-visible work needs the user's judgment: state the decision, question and hypothesis, write the [user] playtest task in tasks.md (build, who plays, what tests already prove, what to judge), map feel words to tuning values, and record the verdict, findings by severity and route, and tuning changes in decisions.md. Covers session shapes, tester bias, accessibility, input-device and online playtests, retrospectives. Never ticks the [user] task."
---

# Game playtest

A gameplay change is finished when a person has played it and said whether it does what the design intended. Running code does not settle that. This skill turns the playtest into a small, answerable check and keeps a record of what came out of it.

It does four things:

1. names the decision the playtest feeds (keep, tune, rework or cut something);
2. asks one question with a hypothesis and an observable signal;
3. writes the `[user]` task that makes the user play and judge, listing what automated checks already prove;
4. records the verdict, who played, the findings and the tuning changes in `decisions.md`.

## When to use

- Writing `tasks.md` for a change with player-visible work.
- "Plan a playtest", "what should I test when I play this", "write the playtest task".
- The user reports how a build played: "the jump feels floaty", "I got lost in level 2", "it was fine".
- "Record the verdict", "log what changed after the playtest".
- A tuning question reasoning cannot settle ("is 0.4 s of coyote time enough?").
- A feel complaint that must become values ("sluggish", "that boss is unfair").
- Difficulty or learnability ("is this too hard", "will a new player get it").
- Accessibility, gamepad or other input-device checks; online feel ("does it feel laggy").
- A milestone close, or "how did playtesting go this milestone".

## Boundaries

| Not this skill | Goes to |
|---|---|
| Designing the mechanic, difficulty, pacing, level layout, the GDD itself | `gamedev-design` |
| Story, dialogue, beat pacing | `gamedev-narrative` |
| Screens, HUD, input maps, wayfinding, the accessibility floor | `gamedev-ux` |
| Clickable prototypes (they prove layout and flow, not feel) | `ui-prototyping-html` |
| Automated tests; screenshots and logs from a run of the engine | The project's stack pack, or ordinary agent tasks |
| Root cause of a crash or softlock | `specwright-debug` |

This skill never edits the GDD, game data, code or tests. It drafts the task and the record with the user. When a verdict contradicts the GDD, say so and hand the edit to `gamedev-design`.

Specwright keeps ownership of commits, reviews and verification. This skill adds domain knowledge to them and bypasses none.

## Hard rules

- The agent never ticks, implements or delegates a `[user]` task. Only the user ticks it, and the agent never writes the `x`. "Looks good" in chat is a verdict to record, not a tick. After recording, ask the user to tick the task themselves. An unticked `[user]` task holds back archive and agent merge; that is intended.
- The agent never scores the play or the feel ("I'd say 7/10") and never counts its own run as a playtest. An agent screenshot or log is evidence, not a playtest.
- Never invent a verdict, a session or a player. No play, no entry.
- When a stack pack is enabled, its evidence task comes before the playtest. The playtest never replaces it and never produces evidence files.
- Nothing here is a gate. The low-confidence mark (step 6) never excuses an unticked `[user]` task, never overrides a required fresh-player check, and never makes the agent refuse to record a designer verdict.

## Where the documents live

Look up the GDD in this order: `packs.gamedev.documents.gdd` in `openspec/specwright.yaml` when set; else the paths the project's AGENTS.md or CLAUDE.md names; else `docs/game/`. `decisions.md` sits beside the GDD. Do not hard-code any other path.

If `decisions.md` does not exist, create it from the decisions template that `gamedev-design` ships, then append. Do not invent a layout.

## Workflow

Ask before writing when the decision or the feel words are unclear. Offer a recommended default with a one-line reason so the user can accept quickly.

### 1. Find the decision

What will the team do differently depending on the answer? If nothing, there is no playtest to write; say so. "Play it and tell me what you think" is not a playtest.

### 2. Ask one question, with a hypothesis

- One main question, at most two more ranked behind it. More than three means split the playtest or cut.
- A good question is answerable in one session by this user, names the behaviour, and says what good looks like.
- Carry the GDD's feel words into it: the judgeable adjectives in its look, sound and feel section, plus any in its core fantasy and pillars. Example, with GDD words "snappy, weighty": "Does the dash feel snappy at the start and weighty on landing, or does either end feel off?" If the GDD has no feel words for the area, ask the user for two or three and suggest adding them through `gamedev-design`. If none applies, the entry says why.
- Add a hypothesis with a signal someone can see: "Players clear the second gap within three tries; signal: deaths at the gap, time to first clear." After play it is marked confirmed, partly or refuted. That mark sits beside the verdict and never replaces it.
- Name the tuning values under test, where they live (the data file the game loads) and their current values, so the verdict can change them without a code edit. The feel-word map in `references/playtest-craft.md` shows which values a feel word points at.

### 3. Choose who plays and the session shape

A question about difficulty or learnability needs a player who does not already know the answer. Pick the shape (solo feel check, guided, unguided, first-minutes, focused, regression replay and others) from `references/playtest-craft.md`. For accessibility, input-device, online and regression playtests, read `references/playtest-kinds.md`.

### 4. Write the `[user]` task

Format, exactly: `- [ ] X.Y [user] <text>`, with `[user]` right after the id in lower case. A marker anywhere else is not read.

The text says:

- what to play: the build (commit or branch holding this change), the scene, level or menu path, the start state, any setting to change;
- who plays: the user as designer, or a fresh player. For difficulty or learnability the task must state which;
- for how long or until what point, and the session shape;
- what to judge: the question in the feel words, and the signal to watch;
- what is already proven, in one short line (for example "the level loads, the jump triggers, the score counts"), so the user judges only what a person can;
- how to report: reply in chat with the verdict; the agent records it.

Keep it one task. Put long instructions in a short block under it, or in the proposal. Use several `[user]` tasks only for genuinely separate sessions, such as one per device or a designer pass and a fresh-player pass. Place the task last in its group, after any `[evidence]` task for the same work.

Mapping scenarios: a scenario about timing or feel ("the boss telegraph reads in time") maps to this task with state `user`. A scenario about layout or presence ("the pause menu shows three buttons") may map to the `[evidence]` task. A scenario an automated test can check is never mapped to a user task.

### 5. Confirm the build, then record

When the user reports back, confirm they played the current build that contains the change. If it is not clear, ask which build, commit or date they ran. If it was an older build, record nothing for this task and ask for a replay: that verdict may describe a bug already fixed or miss the change entirely.

Then append to `decisions.md` as described under "The entry" below, route every finding, and ask the user to tick the task.

### 6. Mark confidence

When only the designer judged difficulty or learnability, record confidence `low`: the person who built the game cannot tell whether it is hard or clear to someone who did not. In that entry's follow-ups, say a fresh player should play the same question before the milestone containing the change closes, and list the entry in the milestone retrospective. Feel questions the designer can judge against their own feel words do not take the mark. A handicap test (see the craft reference) does not lift it.

### 7. Route every finding

Each finding gets exactly one route, written in the entry:

- **Crash, softlock or defect** (the game breaks, the player cannot go on, a rule works against its spec): a new bug task for the agent, worked with `specwright-debug`. Never a tuning change.
- **Feel** (feel words missed, timing off): a tuning change when a value in the data can fix it; otherwise a design change through `gamedev-design`.
- **Polish** (minor, cosmetic, nice to have): a later list, either the GDD's open questions or the project backlog. Never dropped silently.
- Findings of the four player-failure kinds (lost, stuck, bored, missed content) also name their owner skill; the craft reference lists the owners.
- A blocker means the question could not be answered. The verdict cannot be keep, and the playtest is repeated after the fix.

## The entry

`decisions.md` is shared with `gamedev-design` and `gamedev-ux`. Its line format is fixed and must not change:

`- YYYY-MM-DD <area>: <decision> (why: <reason>; affects: <doc>#<section>)`

One line per decision, newest last, append only. Never rewrite an older line; a later line may supersede it and say which.

Per playtest append:

- one line with area `playtest`: the verdict and the question in short, the deciding facts as the reason, the GDD section affected;
- one line per changed value with area `tuning`: `<value>: <old> -> <new> in <data file>`;
- everything else as indented sub-bullets under the playtest line, so the top level stays one line per decision.

Sub-bullets, in this order:

1. change name and task id; the decision, question and hypothesis;
2. what was played: build or commit, scene or level, device, network conditions if online;
3. who played (designer or fresh player, how many sessions, any bias) and confidence;
4. verdict: keep, tune, rework or cut;
5. hypothesis result (confirmed, partly, refuted) with the observed signal;
6. findings, each with severity (blocker, major, minor, note), a fact or opinion mark, and a route;
7. notes seen outside the question, kept as notes and not folded into the verdict;
8. regression: whether an earlier accepted mechanic got worse (yes, no, not checked);
9. follow-ups: new tasks, a GDD section to revise, the next playtest's question.

The tuning edit itself is an ordinary agent task, in this change or the next, committed with its own task. The entry records it. Tuning values stay hypotheses in the game's data, never fixed numbers in specs.

## Quality bar

- From the task alone, a reader knows in under a minute what to launch, who plays, what to do, what is already proven and what to judge.
- Every entry has a hypothesis result, who played, and a regression answer.
- Every finding has a severity, a fact or opinion mark, and a route.
- Every tuning change names old value, new value and data file.
- No "healthy numbers" from a table: values come from the project's data and its playtests.

## References

| File | Read it when |
|---|---|
| `references/playtest-craft.md` | Writing the question, choosing a session shape, observing play, grading findings, mapping a feel word to values, judging tester bias |
| `references/playtest-kinds.md` | Planning an accessibility, input-device or online playtest; a regression replay; deferring global balance; writing the milestone retrospective |
