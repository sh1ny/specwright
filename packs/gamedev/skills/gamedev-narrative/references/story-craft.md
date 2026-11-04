# Story craft for games

The sections follow roughly the order in which decisions come up in a project: the idea, the
world and people, the shape of the story, what the player does with it, the lines themselves,
and finally the checks. Load the part you need. Every number here is a starting hypothesis to
tune in playtest, not a rule. Ideas offered are proposals until the user accepts them.

## Contents

The idea and its form
1. Premise and themes
2. Tone
3. Structure choices
4. Play and meaning fit

World and people
5. World building
6. Mysteries and canon status
7. Characters and arcs
8. Cast roles and earning a slot

Shape of the story
9. Beats and pacing
10. The causal-chain test
11. Sizing the text
12. Endings

What the player does and meets
13. Choices, consequence, gates and agency
14. Objectives and quests
15. Urgency
16. Delivery channels
17. Environmental clues
18. Storylets

The lines
19. Barks
20. Dialogue and voice
21. Keys, status and localization readiness
22. Translator brief

Checks
23. Consistency passes
24. Review checklist

---

## 1. Premise and themes

A premise in one breath: someone wants something, something opposes them, and failure costs
something specific. If any of the three is missing the premise is a setting, not a story.

Offer the user three or four distinct premise shapes drawn from their genre and pillars, each with
what it makes easy and what it makes hard. Example in a made-up game, a lighthouse-keeper sim: (a)
the keeper wants to keep the light lit through a winter, the storm opposes, and the lost ships are
the cost; (b) the keeper wants to find who extinguished the light, the town's silence opposes; (c)
the keeper wants to leave, and the light's pull opposes. Each implies different loops and tone.

Themes work best as questions or tensions ("is loyalty owed to people or to promises?"), not as
statements. The ending then answers the question or leaves it open on purpose. A theme that
nothing in play ever touches is decoration; ask where the player will feel it.

The player's story (what they did and felt) differs from the designer's story (what was written).
Ask which one the game is built to tell, because it changes how much authored text is needed.

## 2. Tone

Tone is carried by image, sound and pacing more than by adjectives in dialogue. Take the GDD's feel
and tone words and ask, for each, where the player will perceive it: a palette, a recurring sound,
how long a scene is allowed to breathe, how often the game interrupts a quiet moment. Offer two or
three concrete readings of a vague word ("cosy" as domestic routine, as safety after danger, or as
small stakes) and let the user choose or blend.

Check that tone agrees with art and audio direction in the GDD. A grim script over bright, bouncy
presentation is a conflict to name; the user may intend it as contrast.

## 3. Structure choices

Pick a structure because of how the game is played, not because it is familiar.

| Structure | Fits when | Watch for |
|---|---|---|
| Act-based (setup, confrontation, resolution) | Linear or mostly linear games with a clear antagonist | Middle sagging; a confrontation the player can skip by play style |
| Journey (departure, trials, return) | Travel, progression by regions, growth of a hero | Trials that are interchangeable; no sense of return |
| Four-part without a central conflict (introduction, development, twist, reconciliation) | Quiet, observational or puzzle-driven games | A twist that is only a reveal, not a re-reading of earlier parts |
| Episodic | Self-contained chapters, release in parts, anthology feel | Recap burden; the through-line fading between episodes |
| Branching | Choice-driven games with budget for it | Text cost multiplying faster than meaning |
| Emergent / systemic | Simulations, sandboxes, strategy | Required beats that never fire; see Storylets |
| Looping / run-based | Repeated attempts are the core | Death with no fictional status; see `order-and-repetition.md` |

To choose, ask three things: how much control does the player have over order, how long is one
session, and what happens to the story when the player fails. Combinations are normal, such as a
journey spine with episodic side stories.

## 4. Play and meaning fit

Every core mechanic should have an in-world meaning. Walk the GDD's loop and list each mechanic
beside what it means in the fiction. Where there is a gap, name it and let the user choose to keep
it; a gap kept on purpose is fine. Story that fights the mechanics (a gentle hero who must clear
rooms by violence) is a tension to record, with whether it is intended.

If a story decision implies a mechanic change, do not make it here: hand it to `gamedev-design`.
Gates and agency (what blocks story, what opens it, what the player decides) are covered with
choices in section 13.

## 5. World building

Size depth to what the player can meet or infer. Private backstory stays small. A lore encyclopedia
the player never touches is a cost, not an asset.

- Rules: every rule states what it costs. Free magic or free technology removes stakes.
- Cultures: for any people the player meets, record customs, beliefs, language habits and daily
  life. Two or three concrete details beat a page of abstract description.
- History: an ordered list of the few events that still shape the present.
- Belief versus truth: what people say happened and what happened. The gap is useful story fuel
  and must be recorded so clues stay consistent.
- Factions: aim, method, what they would trade, and their relation to the player.
- Places: each place carries a story purpose as well as a layout purpose. If a place only exists
  for layout, say so and keep its text small.
- Glossary discipline: one spelling per name; introduce few coined terms early; define each when
  the player first needs it, not before.

## 6. Mysteries and canon status

Every mystery has a recorded true answer, even if the player never learns it. Clues are written
against that answer, so they stay consistent when several people write them.

Mark each lore item:

- Settled: changes only by a logged decision.
- Provisional: may change without a log line.

Treating provisional lore as canon makes writers afraid to improve it; treating settled lore as
provisional lets it drift. When a writer wants to change settled lore, raise it as a question and
log the decision if the user agrees.

## 7. Characters and arcs

For each major character record: what they want (the goal they chase), what they need (the
lack they cannot yet see), and how they change or refuse to.

Common arc shapes, offered as options rather than a menu to fill in:

- Positive: the character grows past the lack and gets, or gives up, the want.
- Negative: the character cannot face the lack and is worse off.
- Flat: the character is steady and changes the world around them.
- Transformative: the character's whole outlook is replaced by something unexpected.

Actions must follow from motive. An antagonist is understandable when you can state, in a
sentence, what they believe they are protecting. If a character acts against their motive, either
the motive or the action needs a reason the player can learn.

Voice per character is covered in section 20.

## 8. Cast roles and earning a slot

Each cast member states what they give the player in play: a service (shop, repair, healing), a
mechanic (a skill, an ability), information, a reason to return to a place, or pressure (a
pursuer, a rival). A character who gives nothing in play has to earn the slot through story alone,
and the user decides whether that is worth the text and production cost.

Keep a compact table for minor cast and full entries only for characters who carry beats. Note
who wants what from whom; the pulls between characters generate scenes more reliably than solo
backstories.

## 9. Beats and pacing

A beat is a unit of change: something becomes known, someone decides, a relationship shifts. List
beats in order, mark each as spine (required) or floating (optional or order-free), and for floating
ones record the unlock condition.

Pacing: follow a peak with rest. Quiet beats let the player absorb a reveal and let a later peak
land. Stretches of constant intensity flatten. When beats rely on an order, check that the level
layout or run structure actually enforces that order; if it does not, rework the beats so they
stand alone.

Required story never sits only in content that is optional, missable or luck-gated. If a reveal is
needed to understand the ending, a player who skips side content must still receive it.

## 10. The causal-chain test

Join consecutive beats with "therefore" or "but". If the only honest link is "and then", the beat
merely follows in time. Report it as a finding with two possible fixes: add a cause (what earlier
event now forces this one) or add a complication (what turns it against the character), or cut the
beat.

Example chain: the keeper relights the lamp, therefore a boat answers the signal, but the boat's
crew will not say where they sailed from, therefore the keeper searches the logbook.

## 11. Sizing the text

Once beats exist, estimate volume honestly: count branches, variants and repeat-facing lines, not
only the main path. Approximate starting ranges by weight, to be revised as beats settle:

| Weight | Typical total text (approximate) |
|---|---|
| none | Flavour text only, from a few hundred up to roughly 2,000 words |
| light | Roughly 2,000 to 10,000 words |
| moderate | Roughly 10,000 to 60,000 words |
| heavy | Roughly 60,000 words and up, often several times that with branching and voice |

Worked example: a game with 40 conversations averaging 120 words, each with two reply branches
that add 40 words, gives 40 x (120 + 2 x 40) = 40 x 200 = 8,000 words, before barks, items and
journal text. Add those separately.

An estimate that ignores variants and repetition is the usual way scope is understated. If the
estimate looks too large, cut branches that change nothing the player cares about before cutting
beats.

## 12. Endings

Record each ending's conditions, the theme question it answers or leaves open, and what the player
carries out. Check that endings follow from the choices and values the game actually tracks. Layered
or earned endings need the reveal ledger to show where the player learns what each ending depends
on. Ending conditions are content data with stable keys, not hard-coded checks in prose.

## 13. Choices, consequence, gates and agency

A weighted choice costs something real on each side. An option that is plainly best is not a
choice; a free option is a finding.

- Signal the stakes before the choice without spoiling the outcome: who is affected and what kind
  of thing is at risk.
- Track moral or social consequence as several relationships or values (trust with this faction,
  a character's regard, a reputation), never one morality meter.
- Promised consequences must happen. If the game says "they will remember this", something
  observable must follow.
- Gates: state what blocks story and what opens it. Every check or gate (a persuasion attempt, a
  skill test, a hidden roll) is stated as retryable or final, and the player can tell which
  before committing.
- Agency: state what the player decides and what is fixed. Pretending a fixed outcome is a choice
  costs trust.
- Choices whose outcomes change nothing the player cares about should be cut or made flavour.
- A story reward from a choice (item, currency, reputation) is flagged to `gamedev-design` so its
  sources and sinks are recorded. A mechanic change implied by a gate is handed over likewise.

## 14. Objectives and quests

An objective starts with a verb, carries its stakes (what happens if the player ignores it), and
pairs an open goal with sub-steps the player can check off. An objective may change as the player
learns more; show the change, never swap it silently.

Example, in a made-up game: "Find who put out the harbour light" with sub-steps "Read the keeper's
logbook", "Ask the ferryman about the night boat". Stakes: until it is answered, the harbour stays
closed to trade.

Ownership: the quest's structure (the decision it poses, its reward against the economy, its
prerequisites) belongs to `gamedev-design`. This skill owns wording, stakes and fit with places,
cast and timeline. That fit check is advisory and never a gate.

## 15. Urgency

A story that claims a deadline either enforces it in play or does not promise one. A "hurry" beside
a world that waits is false urgency. Fixes, in the order the user may prefer: enforce the deadline
in play, soften the wording, or state in the fiction that the world waits. A deadline or failed
final check is a fail state; flag it to `gamedev-design`.

## 16. Delivery channels

Ways the player meets story, roughly from most to least intrusive: cutscenes and scripted scenes,
conversations, interactive moments, objectives and journal text, item and found text, environment,
ambient chatter.

- Show versus tell: prefer what the player can see or do over what they are told. Telling is fine
  for information that cannot be shown cheaply, but should be short.
- Interruption tolerance: decide what happens to a delivery when play interrupts it (an enemy
  appears, the player walks away). Does it pause, finish in the background, or restart? Ask
  whether the world keeps running while the player reads, and hand the answer to `gamedev-ux`.
- Review and skip: record what the player must be able to re-read (a journal, a recap) and what
  they must be able to skip. How that looks and which input does it belongs to `gamedev-ux`.
- Required story is never carried by the environment alone; see Environmental clues.

## 17. Environmental clues

Story told by the environment gets redundant clues: more than one object, sound or space points to
the same fact, so one missed detail does not lose it. Aftermath scenes, set dressing and symbols
carry meaning without words. Required story is never carried by the environment alone; pair it with
a channel the player cannot miss. More on layered depth and placing found text in
`order-and-repetition.md`.

## 18. Storylets

For systemic or nonlinear games, offer storylets: small units of content selected by world state.
Each has preconditions (what must be true to appear) and effects (what changes when it plays).

Record the state variables the storylets read and write in the narrative document, and make sure
required beats have a route that cannot be starved by state. Persisting storylet state belongs in
the save data; flag it to `gamedev-design` so the save version covers it.

## 19. Barks

Barks are short reactive lines. Their first job is system readability: they tell the player the
state of the game (spotted, low health, reloading, the companion found something). Character
colour comes second.

For each bark type record: what state it signals, a cooldown, a no-repeat rule, and a variant
count sized to how often it fires. Starting hypotheses, to tune in playtest:

- Fires several times a minute: many variants and a long no-repeat window, or the player will
  tire of it quickly.
- Fires once per encounter: a handful of variants is usually enough.
- Fires once per playthrough: one line, written with care.

Example in a made-up stealth game, "guard noticed something": if it can fire roughly six times in
a 20-minute level, ten variants with a no-repeat window of the last three gives the player enough
variety to hear no line twice in a row. Treat these as a first guess.

Barks multiply text quickly, so count them in the estimate (section 11).

## 20. Dialogue and voice

- Voice per speaker: rhythm, vocabulary, what they avoid saying, and an emotional range that
  includes what they never sound like. A line should be recognisable without its name tag.
- Skimmable lines: put the useful part first, keep lines short, and let players who read quickly
  lose nothing important.
- Branching shapes and cost:
  - Linear with flavour replies: cheapest; replies change tone, not outcome.
  - Hub-and-spoke: a topic list the player works through; cost grows with topics, and the
    player should be able to leave before exhausting it.
  - Branch-and-bottleneck: branches diverge and rejoin at fixed points; the common way to keep
    choice meaningful without multiplying everything.
  - Fully branching: expensive; justify it by the outcomes the player cares about.
- A branch that multiplies text without changing something the player cares about should be merged.
- Run-aware lines (for repeated attempts) are covered in `order-and-repetition.md`.
- Voice acting plan: state it even as "not planned". If planned, voiced lines fit one breath and
  carry a short actor note; note length limits, and remember that recorded lines are costly to
  change once the text freezes.

## 21. Keys, status and localization readiness

Decide these when the first lines are written, because retrofitting is expensive.

- Write placeholder-first: put in the key and a short stand-in, then replace as the beat settles.
- Give every line a stable key never derived from its text, and a status (placeholder, draft,
  final, frozen).
- Store text as keyed data, not in code or in specs. For the file format and loading, when a
  stack pack is enabled, use its skill for the engine handoff.

Localization readiness is generic and worth stating even when no translation is planned:

- Stable string keys, never derived from the source text.
- Room for text expansion in layouts and limits (many languages run longer than the source).
- Full-sentence templates with named placeholders, not strings joined from fragments.
- Plural, gender and case forms planned for any string that varies by count or person.
- Font and glyph coverage for every target script. Right-to-left scripts are a readiness check
  for the team, not a plan this skill writes.
- Wordplay and culture-bound references flagged for translators.

## 22. Translator brief

Needed when localization is planned. Contents:

- A glossary with do-not-translate terms.
- A list of every placeholder and what it can hold.
- Context per key: who speaks, to whom, where it shows, length limit.
- A text freeze point, and the process source changes follow after it.

## 23. Consistency passes

Run on request, after a large story change, or before a story-heavy milestone. Method:

1. Motive: for each major action, what motive explains it? List actions with none.
2. Timeline: order events; check presence (no one in two places) and knowledge (no one acts on
   something not yet learned).
3. Player knowledge: for each reveal, can some reachable play order show it too early, too late
   or not at all? Walk the shortest, the slowest and one odd order.
4. Glossary: one spelling per name; no term used before it is introduced.
5. Mysteries: each has a recorded answer, and every clue agrees with it.

Report issues as a question or a suggested fix. Never rewrite canon on your own.

## 24. Review checklist

Tick each in words; none is a score. "Not assessed" when the input is missing.

Coherence of the story:
- The premise names someone who wants something, what opposes them, and what is lost on failure.
- Themes are questions or tensions; the ending answers or deliberately leaves them.
- Each major character's actions follow from their motive; the antagonist is understandable.
- Timeline and glossary hold: one spelling per name; no impossible presence or knowledge.
- Every beat links to the previous by "therefore" or "but".
- Every mystery has a recorded true answer; lore items are marked settled or provisional.

Fit with play:
- Every core mechanic has an in-world meaning, or the gap is named and kept by choice.
- Tone agrees with the GDD's feel and tone words and with art and audio direction.
- Required story never sits only in optional, missable or luck-gated content.
- Gates and the degree of agency are stated; promised choices have real effects.
- Weighted choices cost something on each side; stakes are signalled without spoilers; there is
  no single morality meter; each check is marked retryable or final.
- Objectives start with a verb, state stakes, and have checkable sub-steps.
- Every stated deadline is enforced, or the urgency is removed.
- Barks serve system readability and have cooldown, no-repeat rule and variant count.
- Environmental story has redundant clues; no required story is environment-only.
- Each cast member's contribution in play is stated.

World depth, sized to use:
- Rules state their cost; cultures are present for any people the player meets; places carry
  story purpose.
- Lore depth matches what the player can meet or infer; private backstory stays small.

Order and repetition (only when relevant):
- Reveals work in every reachable order; fragments stand alone.
- For repeated runs: death has a stated fictional status; each story element has a persistence
  rule; repeat-facing text has enough variety for the expected play length.

Production honesty:
- A text estimate counts branches, variants and repeat lines.
- Text lives as keyed data; localization and voice plans are stated, even as "not planned".
- When localization is planned, the translator brief exists.

Blocking before story features are built: no premise; no beats; story that contradicts the GDD's
mechanics or progression; required story reachable only by chance.
