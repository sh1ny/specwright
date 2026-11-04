# Game architecture questions

Use this when the design mentions one of the triggers below. The architecture baseline belongs to `specwright-roadmap`. This skill only raises questions for it. Frame everything as a question, never as a decision, and put unanswered ones in the GDD's Open Questions with an owner or a trigger. Capture the player-facing need in the GDD; move the "how" here.

When a stack pack is enabled, its skill owns the engine-side details.

Each trigger lists the design signal, why it is expensive to add late, and the questions to bring to the baseline.

## Multiplayer

**Signal.** Co-op, versus, shared world, leaderboards with live play, "play with friends".

**Why late is expensive.** Who decides what is true shapes every system. Adding it after the fact usually means rewriting movement, combat and saves.

**Questions.**
- Which machine is the authority on what happened: one player, a server, or each in turn?
- What latency can the design tolerate before play feels wrong, and what does the game do beyond it?
- What is the stance on cheating, and what does it cost to enforce?
- Can a player drop in, drop out and reconnect mid-session? What do the others see?

## Procedural generation

**Signal.** Random levels, generated worlds, runs that differ, seeds.

**Why late is expensive.** Guarantees such as "the exit is reachable" must be built into the generator from the start, and testing generated content is a different job from testing authored content.

**Questions.**
- What does a seed reproduce: the layout, the loot, the whole run? Must a seed give the same result on every build?
- What guarantees must the generator always keep (a reachable exit, a fair first room, no softlock)?
- What happens when generation produces something invalid: generate, validate, then fall back (retry, a safe template) rather than ship a broken level?
- How are failures found: a batch of seeds checked automatically?

## Mods and user content

**Signal.** Level editors, user-made content, workshop, "players can add".

**Why late is expensive.** What is exposed becomes a promise. Data that was private must be documented and versioned.

**Questions.**
- What does the game expose to creators, and what stays private?
- How are content formats versioned, and what happens to old content?
- What is the trust model: can user content run code, and what can it touch?
- Who supports broken content?

## Replays, rollback and lockstep

**Signal.** Replays, kill-cams, rollback netcode, lockstep strategy, deterministic puzzles, "share a run".

**Why late is expensive.** Replays and rollback need the simulation to produce the same result from the same inputs. That requires a fixed step and care with randomness and ordering from the first line of gameplay code.

**Questions.**
- Must the simulation be deterministic? On the same machine, or across machines?
- Is the simulation stepped at a fixed rate independent of rendering? At what rate?
- Are random numbers seeded and drawn in a stable order?
- What must be stored to replay: inputs only, or periodic snapshots?

## Cloud saves

**Signal.** Play on more than one device, "continue anywhere", account-linked progress.

**Why late is expensive.** Conflicts and offline play change what a save is: a record that can be merged, not a file that is overwritten.

**Questions.**
- What happens when two devices changed the same save? Which wins, or can they merge?
- Is the game fully playable offline, and how does it catch up later?
- Which platform services does it depend on, and what happens when they are unavailable?
- What does the player see when a conflict is found?

## Save-format versioning and migration

**Signal.** Anything that persists: progress, unlocks, settings, user-made content. Any change to what persists.

**Why late is expensive.** Every released save format is a promise. Without a version number from the first release, old saves cannot be told apart from new ones.

**Questions.**
- Will old saves load forever, or is there a stated policy on breaking them, and who is told?
- Does each save carry a version, and does each change to the format ship a migration?
- What happens to fields the current build does not know (kept, never silently dropped)?
- How is migration tested: is there an old save in the test set?

## When the design has none of these

Do nothing. Do not raise architecture questions for a design that does not imply them. Raise them when a design first mentions one of the triggers, or when a change to what persists is proposed.
