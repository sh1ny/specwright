# GDD guide

One entry per GDD heading, in the order the GDD uses. Each entry says what the section must hold, then gives pressure questions. Ask them in small batches, each with a suggested answer and a reason. Skip a question when the answer is already on paper. Every number you suggest is a starting hypothesis to tune; the live value belongs in data the game loads.

Implied systems (saving, menus, persistence, AI, input remapping, localisation) come up during the scope check. They land in Mechanics, Out of Scope or Open Questions. They never get a new heading.

## Pitch

**Must hold.** A short paragraph: what the game is, who plays it, and what they do. A stranger should be able to repeat it.

**Pressure questions.**
- What does the player do most of the time, in one sentence with a verb?
- Who is this for, narrower than "everyone"?
- If you could show only ten seconds of play, which ten?

### Genre and References

**Must hold.** The game type id on its own line, then optional secondary ids for hybrids, then free text. Format:

```
Game type: roguelike
Also: deckbuilder
```

Ids come from `references/genre-guide.md`; use `general` when nothing fits. Say which signals in the pitch matched the id and confirm with the user. For hybrids, raise the tensions early because they shape the loop. Then list each reference with what is borrowed and what is refused.

**Pressure questions.**
- Which words in your pitch point to this id, and is there a stronger competing id?
- For each reference: what exactly do you take, and what do you leave out on purpose?
- Does a reference carry a convention your players will expect that you do not plan to meet?
- Would looking at a comparable game change a decision here? If not, skip the research.

### Core Fantasy and Pillars

**Must hold.** The fantasy in one sentence (the feeling of being someone doing something). Two to four pillars, a starting hypothesis, in priority order. Two or three anti-pillars: things the game is not, chosen because this genre makes them tempting.

**Pressure questions.**
- Name a feature someone might propose. Which pillar rejects it? A pillar that rejects nothing is a slogan.
- Do any two pillars reject the same things? Then they are one pillar.
- When pillar A and pillar B conflict, which wins?
- What would a fan of this genre expect that an anti-pillar refuses?

**Worked example (invented).** Premise: a lighthouse keeper climbs a drowned tower at night with a limited lantern.

- Weak pillar: "Atmospheric and tense." It rejects nothing; every feature fits.
- Sharper pillar: "Light is a debt." Every source of light costs oil, and oil is the only clock. This rejects a regenerating lantern, a pickup that restores oil for free, and a safe room that never darkens. It can win a conflict: when "light is a debt" and "generous exploration rewards" collide, the debt wins and rewards are priced in oil.
- Anti-pillars: not a combat game (the lantern is not a weapon); not a puzzle box with one answer per room.

## Core Loop

**Must hold.** The loop at three time scales: the moment (act, result, reason to act again), the session, and the long arc. How each scale feeds the next. What ends a session cleanly and what brings the player back. Target session length. Which parts repeat (loops) and which are consumed once (arcs).

**Pressure questions.**
- Take away progression and story. Is the moment-to-moment act still worth doing?
- What is the result of the act, and what does the result change or reward?
- What makes the player act again straight away?
- Where does a session end without the player feeling cut off? Where do they stop and why do they return?
- What is the target session length, and does the save spacing fit it (see Platforms and Input)?
- Which parts of the long arc are one-time arcs that will run out, and what replaces them?

**Worked example.** Moment: step into a dark room, spend oil to light it, read what is revealed, decide whether to press on. Session: descend three to five floors on one flask budget (hypothesis), then return to the surface. Long arc: each return unlocks a deeper stairwell. The moment feeds the session through oil left; the session feeds the arc through what the keeper carries up.

## Mechanics

**Must hold.** One `###` subsection per mechanic. Each one names the pillar or loop step it serves, the decision it gives the player, its skill floor and ceiling, its numbers (each marked as a hypothesis kept in data), and its edge cases with resolutions. Prefer a general system that combines with others (weight, heat, noise, light) over a hard-coded special case; a special case is a finding unless the user wants it.

**Pressure questions per mechanic.**
- Which pillar or loop step does it serve? If none, it is a cut candidate.
- What real decision does it give? Is any option always best? If so, it is a cut candidate or needs a cost.
- What can a new player do with it, and what can an expert do?
- Is this a general system, or a special case for one situation?
- Edge cases: what happens at zero, at the cap, when two triggers fire at once, and with a known exploit? An unresolved one becomes an Open Question.
- Which implied systems does it need that are not named yet?

**Worked example (invented, all figures are hypotheses for data).** Mechanic: lantern oil. Serves the pillar "light is a debt".

- Burn: 1 unit per 4 s while lit (hypothesis).
- A full flask holds 30 units, so it lasts 120 s of continuous light. Check: 30 x 4 s = 120 s.
- Relighting costs 2 units. Dousing for t seconds saves t / 4 units, so dousing for less than 8 s loses oil, and at exactly 8 s it breaks even (8 / 4 = 2).
- Decision: stay lit and safe, or douse to save oil and risk the dark.
- Skill floor: leave the lantern on. Ceiling: douse in lit corridors and read the room by sound.
- Edge cases: at 0 oil the lantern goes out and cannot be relit until refilled (resolved: the dark is the penalty, not death). A refill at the cap wastes the excess (resolved: the pickup stays in the world). Dousing and being hit in one tick: the hit resolves first (to confirm in a playtest).
- Live values: in the data the game loads, not here.

## Progression and Difficulty

**Must hold.** How play changes over time. Sources and sinks for every resource, currency or reward. The difficulty axes the game uses and which the player can lower. Assist style. The cost of a retry. The frustration stance. The onboarding order. Reward ethics.

**Pressure questions.**
- Does progression change how the loop plays, or does a counter just grow? If power growth is the chosen fantasy, record it as a choice.
- For each resource: where does it come from, where does it go? A source without a sink is a finding.
- Which difficulty axes exist (execution, knowledge, resource, time, decision load)? Which can the player lower?
- Are assists chosen by the player, adaptive, or granular switches? If adaptive, does the player know?
- What does a failed attempt cost: time, progress, items? How long until the player is playing again?
- Frustration stance: what failure is intended to sting, and what must never feel unfair?
- Onboarding: in what order are the core verbs taught? Is there ever a second new mechanic in one encounter? What does the player know at the first minute, the fifth, the twentieth? What is the designed first failure and the first moment of competence?
- Reward ethics: is there a reward condition the player would not enjoy meeting (appointments, paid randomness, social pressure, streaks that punish a missed day)? Is any reward variable-ratio, and what does the design want from it?

For economy, curves, feedback loops and randomness see `references/systems-and-balance.md`. For teaching order see `references/levels-and-encounters.md`.

## World and Story

**Must hold.** The setting and tone, a few lines. Details live in `narrative.md`.

**Pressure questions.**
- What does the world need to be so the mechanics make sense?
- Does the tone match the feel words below?
- Is anything here a story question? If so, hand it to `gamedev-narrative`.

### Narrative Weight

**Must hold.** One value for how much the story matters to play, with a one-line reason, and a link to `narrative.md` when it exists. Nothing more: story design belongs to `gamedev-narrative`.

**Pressure questions.**
- If the story were removed, would the player lose reasons to act or only flavour?
- Is the story told by play, by text, by cutscenes, or by found material?
- Does the story survive repetition if the loop repeats?

## Look, Sound and Feel

**Must hold.** Feel words a playtester can judge yes or no. For each: an anti-reference (what it must not feel like), a commitment profile (can the action be cancelled mid-way; does the response start instantly or ramp), and a failure texture (can the player tell why they failed). Startup, active and recovery timing per action is optional detail. A flashing or shaking effect names its reduced-motion behaviour (hand to `gamedev-ux`).

**Pressure questions.**
- Can a playtester say "yes" or "no" to this word after five minutes? "Fun" and "polished" cannot be judged.
- What must it not feel like?
- Once started, can the action be cancelled? Does the response begin at once or build up?
- When the player fails, how do they know why?
- What sound or look would make this word true at a glance?

**Worked example (invented).** Feel word: "the winch pull reads heavy". Anti-reference: not floaty, not a light tap. Commitment: once the pull starts it cannot be cancelled for the first 0.4 s (hypothesis), then it can; the rope's response ramps over 0.2 s rather than snapping. Failure texture: a missed catch shows the hook swinging past the ledge and the sound drops, so the player sees the miss was their timing, not the controls.

## Platforms and Input

**Must hold.** Target devices, the minimum input set, and how save or checkpoint spacing fits the target session length. Names the devices that input evidence will be gathered on.

**Pressure questions.**
- Which devices must work on day one, and which are deferred?
- What is the smallest input set that lets someone finish the game?
- Does any action need precise timing that one device makes harder?
- How long is a session, and how far apart are saves or checkpoints? Does a player who stops at any time lose more than they will tolerate?
- Does anything need frame-rate or load-time commitments (see `references/game-code-checks.md`)?

## Accessibility Floor

**Must hold.** Concrete commitments, not intentions. Examples to offer as candidates: remappable controls, subtitle defaults, no colour-only signals, adjustable speed or assist options where the genre allows. Detail beyond the floor goes to `gamedev-ux`.

**Pressure questions.**
- Which commitments are non-negotiable from the first build?
- Which difficulty axes have an assist the player can switch on?
- Is any signal carried by colour, sound or timing alone?
- Which commitments does the genre make hard, and what is the fallback?

## First Playable

**Must hold.** The riskiest assumption, the smallest build that tests it, and which item is built first. Not a feature list.

**Pressure questions.**
- What is the one thing that, if false, sinks the game?
- What is the smallest build that would show it holds?
- Does the list exceed about seven items (a starting hypothesis)? Which could go?
- Is the riskiest item first?
- Does each item trace back to a pillar or loop step?
- What does a pass look like, and which of that is judged by the designer's playtest?

## Out of Scope

**Must hold.** What is cut, what is deferred, and why. A parked cut gets one line: what it was and why it went. Reopening needs new evidence.

**Pressure questions.**
- What did you drop, and which pillar or constraint dropped it?
- What is deferred until after First Playable?
- Which implied systems did you decide not to build?
- Do cuts keep colliding with the same pillar? Then question the pillar.
- Does the scope fit the team and the time, including the implied systems?

## Open Questions

**Must hold.** Unresolved edge cases, deferred asks, unconfirmed assumptions. Each has an owner or a trigger ("decide after first playtest").

**Pressure questions.**
- Which items block the next planned change? First Playable? Which can wait?
- Does each item have an owner or a trigger?
- Is anything here a hidden default that someone chose silently?
- Is the open-item load reasonable for the scope?
