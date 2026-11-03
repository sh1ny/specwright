# Levels and encounters

Use this when designing a level, an encounter, a quest structure or the onboarding order. No other skill owns space design. All figures here are starting hypotheses; the live values come from the movement and combat data the game loads.

## Space derives from movement

Every spatial measurement comes from the movement numbers, not from taste. Jump height and distance, run speed, reach, sight lines and reaction time set gap widths, ledge heights, corridor widths and safe distances.

**Worked example (invented, all hypotheses).** A courier character runs at 6 m/s and can clear a gap of 3 m in a jump. A level designer wants a gap that is hard but fair:

- A comfortable gap leaves margin: 2 m is two thirds of the maximum.
- A hard gap sits near the limit: 2.7 m is 90 per cent of 3 m.
- A gap above 3 m is impossible without a power-up.
- A turret that fires with a 0.5 s warning needs at least 0.5 s x 6 m/s = 3 m of cover-to-cover distance for the player to cross after the cue.

Level specs cite the movement values they depend on. When a movement value changes, those specs are flagged for a recheck. A level that has never been cited to a number cannot be rechecked.

## Greybox first

Prove the space with plain shapes before art. Check routes, sight lines, timing and scale with boxes and placeholder markers. Art never hides a layout fault, and replacing art later is cheap only if the layout was right.

Keep a record of what each room is meant to do, so a greybox pass can compare intent to result.

## The intensity curve

Alternate tension and rest. For each level, chart intensity along the route (a simple list of rooms with a low, medium or high mark is enough). Peaks are followed by rests. A level that stays at one intensity feels flat or exhausting. Mark where the player can stop, restock and think. Compare sessions: does the curve also rise across levels, with a rest between?

## Orientation and structure

- **Landmarks.** Give the player something recognisable to navigate by: a shape on the skyline, a light, a sound. A player should be able to answer "where was I heading?".
- **Critical path and optional content.** Keep the critical path obvious. Put optional content off the main route, so choosing it is a decision.
- **Barriers with a reason.** A locked door, a collapsed bridge or a missing item needs a reason in the fiction, and the player should be able to see what removes it.
- **Secrets that do not punish.** A secret never costs the player who finds it: no trap for curiosity, no loss of progress.

## Teaching in four steps

A teaching pattern in the style of Kishotenketsu:

1. **Introduce** the mechanic safely. No penalty for failing to understand it.
2. **Develop** it with guidance. Vary the situation a little and let the player apply it.
3. **Twist** by combining it with something the player already knows.
4. **Test** it. Now the player must use it with consequence.

Rules for teaching:

- Never break a learned pattern without signalling it.
- Never introduce two new mechanics in one encounter.
- State the order of the core verbs in the GDD.
- Design the first failure and the first moment of competence on purpose.

Teaching is designed work. A tutorial is not evidence that the design failed.

## Softlock checks

A softlock is a state the player cannot leave. Check each of these:

- **One-way passage.** Can the player enter a place they cannot leave, with no route forward?
- **Consumable key.** Can the player spend a key, item or resource on the wrong thing and be unable to progress?
- **Destructible path.** Can the player destroy or alter something that was the only route?
- **Ordering.** Can the player reach a point before obtaining something needed there?

For each, name the state that makes it safe: a respawn, a replacement source, a way back.

## Encounter sheet

Each encounter states:

- **What it teaches or tests.** One thing.
- **Place on the intensity curve.** Peak, rise, rest or release.
- **Approaches.** More than one way through, where the genre allows.
- **Fail state.** What counts as failing. If the fail state is changed or added, an automated check must prove that doing nothing does not win (see `references/game-code-checks.md`).
- **Recovery.** Where the player returns, what is lost, and how long the retry takes. A cheap retry allows a harder encounter.

**Worked example (invented).** Encounter: the flooded stairwell. Teaches: dousing the lantern to cross a lit patch unseen. Curve: rise after a rest room. Approaches: sneak along the wall in the dark (cheap in oil, high risk), or burn bright and run (cheap in risk, costly in oil). Fail state: caught in the light for more than the alarm window (a hypothesis, 2 s). Recovery: back at the stair top, oil as it was on entry, retry in about 10 s.

## Quests and objectives as structure

Treat a quest as structure here. The wording and story fit go to `gamedev-narrative`.

- **The decision it poses.** A quest with no decision is a chore list.
- **Reward against the economy.** Price the reward in the same currency as other sources (see `references/systems-and-balance.md`). A quest that pays far above its effort distorts the economy.
- **Visible prerequisites.** The player can see what a quest needs before starting it.
- **Two solutions for major quests,** where the genre allows.
- **Softlocks.** A quest cannot be failed by an action elsewhere without the player being told.

A check against existing places, cast and timeline is advisory. It is a prompt to the user, not a gate.

## Build the full content map late

Do not list every level, item and enemy until First Playable has proved the loop. A full content map made early is thrown away when the loop changes. Until then, hold a few examples that show the range.
