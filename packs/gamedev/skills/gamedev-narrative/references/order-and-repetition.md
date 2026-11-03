# Order and repetition

How the way a game is played changes how its story must be delivered. Load the section matching
the game. Each ends with decisions to record in the narrative document and common traps. All
numbers are starting hypotheses.

## Contents

1. Environmental storytelling
2. Run-based and roguelike story
3. Nonlinear and backtracking story
4. Emergent and systemic story
5. Episodic release (brief)

## 1. Environmental storytelling

The space tells the story: what happened here, who lived here, what they feared.

- Aftermath scenes: show the result of an event and let the player reconstruct it. A table set
  for four with one chair overturned says more than a note explaining the argument.
- Set dressing and symbols: repeated motifs mark a group, a belief or a place's history. Keep the
  vocabulary small enough that the player learns to read it.
- Light and sound as carriers: warmth, silence, a distant repeated noise. They set mood and can
  point at a thing without a word.
- Layered depth: the casual player gets the headline (a ruined home, a battle happened here); the
  attentive player finds the detail that recasts it (the barricade was built from inside).
- Found text: place notes, logs and signs where the player is already stopped or looking, not in
  the middle of a hazard. Keep each short; a long document is a journal entry and belongs in
  the journal channel (presentation is `gamedev-ux`'s call).
- Redundancy: point at each important fact from more than one object, sound or space.
- Required story is never carried by the environment alone.

Decisions to record: which facts the environment carries; which of those also have a second
channel; where found text sits and how long it may be.

Traps: one clue carrying a required fact; found text as a wall of prose; symbols that mean three
different things; set dressing that contradicts the timeline.

## 2. Run-based and roguelike story

A run ends and the next begins. The story must decide what that means.

- The fiction of death: pick a stated status. The character is revived, replaced, relives the
  day, was never alive, or is a different person each time. The choice shapes tone and what
  other characters can say. If the game says nothing, the player invents something, so offer
  options and let the user choose.
- Persistence classes: for every story element, record whether it resets each run, persists
  across runs, or accumulates. Elements include knowledge, relationships, unlocked lore, hub
  state, items and the world's own change.
- Who remembers: the player, the protagonist, other characters, or only the world. Each answer
  changes dialogue; characters that remember make repetition feel inhabited.
- Protecting a mystery across clears: if a clear is possible, the mystery's answer may be reached
  by only some runs. Record the true answer, the clues per run depth, and the earliest clear that
  can reveal each piece, so clues are not spent in the first run.
- Small per-run arcs inside a slow meta arc: each run can have its own opening, tension and
  close, while the meta story advances by what persists. A run with no story shape is easy to
  forget; a run that must carry the whole story is hard to repeat.
- A hub that changes between runs: new characters, changed lines, a different mood after a bad
  run. Visible change in the hub is the cheapest way to show the story moving.
- Respecting the hundredth repetition: sample the text the player sees every run (the opening,
  the first room, the death line) and size variants to the expected play length. A line seen
  every run needs more variety than a line seen once per playthrough. A starting hypothesis:
  for a run of 20 minutes played about 50 times, a repeat-facing line fires 50 times, so a pool
  of about 10 with a no-repeat window of the last 3 avoids obvious repeats for the first
  several runs; plan to rotate in new lines as the meta arc advances.
- Run-aware dialogue: lines can acknowledge the run count, previous causes of death or progress.
  Keep it light; every acknowledgement is a variant to write.
- Layered endings: a first clear, a true ending, and later endings reachable only with specific
  knowledge. Record what each requires so the ledger shows the order.

Decisions to record: fictional status of death; persistence class per story element; who
remembers; the meta arc's steps; the hub's changes; expected repetitions and the variant plan.

Traps: death that is only a game-over screen with the fiction silent; story that resets so the
player learns nothing across runs; rare reveals gated behind luck alone; barks with too few
variants; a mystery solved by the second run.

## 3. Nonlinear and backtracking story

The player chooses the order, or returns to places with new abilities.

- A short ordered spine versus floating content: keep the required spine short and build the rest
  as floating content that works in any order. The spine is what the ending depends on.
- Self-contained fragments: each fragment (a note, a scene, a character beat) makes sense on its
  own and does not assume that the player saw another. Where a fragment adds to another, write it
  so the earlier one is not needed to follow it, only enriched.
- Ability-gated reveals: tie a reveal to a place the player cannot reach until they have an
  ability. The gate gives the reveal weight, and gives the ability narrative meaning. Check that
  the path to every required reveal is reachable.
- Payoffs for returning: a place visited again with new ability or knowledge should say something
  new (a changed line, a newly legible sign). Returning for nothing teaches the player not to.
- Sequence-break policy: decide what happens when the player gets somewhere early. Options:
  prevent it, tolerate it with graceful lines, or reward it. Record the choice; do not leave it
  to chance.
- Reveal ledger: for each reveal record the earliest and latest points it can arrive, whether it
  is required, and what it depends on, then walk the shortest, slowest and a sequence-broken order.

Decisions to record: the spine; the floating content and its unlock conditions; the sequence-break
policy; which reveals are required.

Traps: beats that assume an order the layout does not enforce; a required reveal that sits behind
an optional ability; a fragment that spoils another; callbacks to scenes the player may not have
seen.

## 4. Emergent and systemic story

Content is chosen by world state, not by a script.

- Storylets: small units, each with preconditions and effects. The game picks among those whose
  preconditions hold, often weighted or ranked.
- State variables: record each variable the storylets read and write, its range, and what changes
  it. Treat this list as part of the design. Persisted values go into the save data (flag to
  `gamedev-design`).
- Keeping required beats reachable: give every required beat at least one storylet whose
  preconditions the player's progress will eventually meet, and add a fallback that fires if
  too long has passed. Without one, required story can starve.
- Variety control: avoid back-to-back repeats with a cooldown on each storylet, and record
  starting values to tune in playtest.
- Authorial voice: storylets assembled out of order still need consistent voice, so settle the
  house style and glossary before writing many.

Decisions to record: state variables and their ranges; required beats and their fallback; cooldown
policy.

Traps: storylets that all depend on the same variable; hidden preconditions nobody can test;
required content that never fires; so many storylets that voice drifts.

## 5. Episodic release (brief)

When the story is released in parts, give each part its own opening, tension and close, plus a
small recap path for returning players. Decide early which state carries between episodes
(choices, relationships, items) and record it, because it constrains later writing. Do not promise
consequences the later episodes cannot afford. Keep the through-line visible in each part so it is
not forgotten between releases.

Decisions to record: state carried across episodes; the recap approach; the minimum a new player
needs to start mid-series.

Traps: promises of consequence that later episodes cannot honour; a recap that repeats the whole
story; pacing that depends on the next episode to feel resolved.
