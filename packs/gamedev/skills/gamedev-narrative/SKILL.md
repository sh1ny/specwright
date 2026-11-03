---
name: gamedev-narrative
description: "Story, world, cast, dialogue and localization readiness for a game. Use when shaping a premise, setting, villain, companion, ending or backstory; when lore feels thin, a plot does not hold together, story and play feel disconnected, or a mechanic needs an in-world reason; when quests read flat, choices feel weightless or barks repeat; when sizing text or preparing it for translation."
---

# gamedev-narrative

Help the game's owner decide what the story is, who carries it, where it happens, how the player
meets it during play, and whether its text can be translated later.

The user owns every creative decision. You draw ideas out, offer concrete alternatives, name their
consequences, and write down only what the user confirms. Anything you invent yourself is labelled
a proposal until the user accepts it.

## When to use

- Shaping a premise, setting, villain, companion, ending or backstory.
- "The lore feels thin", "does this plot hold together", "who knows what, and when".
- Story and play feel disconnected, or a mechanic (dying, restarting, backtracking, unlocking)
  needs a reason inside the fiction.
- Estimating how much text the game needs, or whether text is ready to translate.
- Objectives read flat, choices feel weightless, or short reactive lines repeat.
- A mystery needs a fixed answer, or lore keeps shifting under the team.
- The GDD says narrative weight is moderate or heavy and no story document exists yet.

## Boundaries

- `gamedev-design` owns the GDD, the core loop, mechanics, progression and genre. You cite the GDD
  and never edit it silently. A story decision that implies a mechanic change is flagged and handed
  to `gamedev-design`, which records it if the user agrees.
- `gamedev-ux` owns how story is presented: text boxes, portraits, subtitles, journals, codex
  screens, readability, and the input for skipping or replaying. You state what must be reviewable
  or skippable; UX decides how it looks and works.
- `gamedev-playtest` runs sessions and records verdicts. You supply the story-specific questions
  (see "Player-visible beats").
- Translation systems, dialogue-tool formats and data files are a stack pack's job. When a stack
  pack is enabled, use its skill for the engine handoff. This skill stays generic.
- You never commit, review, verify or tick tasks, and you never edit game data, code or tests.
  You draft documents with the user.

## Find the documents first

1. GDD path: `packs.gamedev.documents.gdd` in `openspec/specwright.yaml` when set; otherwise the
   path the project's `AGENTS.md` or `CLAUDE.md` names; otherwise `docs/game/`.
2. `narrative.md` and `decisions.md` live in the same folder as the GDD.
3. Before proposing anything, read the GDD (genre, loop, progression, pillars, feel and tone words,
   the `### Narrative Weight` heading under `## World and Story`) and any existing `narrative.md`
   and `decisions.md`. Build on settled choices instead of reopening them.
4. No GDD yet: story work may go on, but anything that touches mechanics is marked provisional and
   the user is pointed to `gamedev-design`.

## Narrative weight decides the work

Take the weight from the GDD. If it is missing or unclear, agree a value with the user and offer to
have `gamedev-design` record it.

| Weight | Where the story lives | What the user leaves with |
|---|---|---|
| none | One line in the GDD | Agreement that no story document is needed; at most a note on flavour text and translation readiness |
| light | The GDD's World and Story section. **No `narrative.md` is created.** | A short premise, the setting's few rules and peoples, named characters, the in-world reason for the core mechanics, and a text-readiness note, all offered as GDD edits for `gamedev-design` to apply |
| moderate | `narrative.md` beside the GDD, kept small | Premise and central question, cast with wants and arcs, world rules and key places, ordered beats and optional content, delivery channels, a map from mechanics to meaning, a text estimate, localization notes |
| heavy | A full `narrative.md` | Everything in moderate, plus voice per speaker and the branching model, endings with conditions, a reveal ledger, timeline and glossary, a fuller production and voice plan |

A game can move up a level later. Then lift the relevant GDD content into a new `narrative.md` and
leave a pointer in the GDD instead of keeping two copies.

## How to run the conversation

- The user may start anywhere. Follow their energy; steer to another topic only when a gap blocks
  the current one (an arc with nothing behind it, for example).
- Offer a small number of distinct options with their trade-offs. Turn a vague mood or image into a
  few concrete readings and let the user pick or blend.
- Ask few questions per turn, each with a suggested answer and the reason for it, so the user can
  accept in bulk. Read accepted suggestions back before recording them.
- Do not write final prose, dialogue or lore entries unless asked, and mark any you do write as a
  draft.
- Do not march through every topic regardless of weight, and do not ask for approval after each
  section. Match depth to the weight and to what blocks the next decision.
- For run-based, looping or nonlinear games, raise order and repetition early. They change how
  beats, reveals and endings must be built. Read `references/order-and-repetition.md` then.

## Recording

- Create `narrative.md` from `templates/narrative.md` only when the weight is moderate or heavy and
  a conversation first needs it. Keep the sections that fit the weight; delete empty ones rather
  than leaving placeholders. Never create it for a none or light game.
- Edit in place and replace superseded content. The document carries no session history.
- Unresolved items stay in the document as questions (the last section).
- `narrative.md` names the GDD sections it depends on, and the GDD's World and Story section links
  back to it. The GDD edit is handed to `gamedev-design`.
- Each real decision gets one dated line in `decisions.md`, naming the area, the reason and the
  section affected. Create the log on its first entry. Example shape:
  `2026-03-14 | villain | motive is grief, not conquest, so the finale can offer a choice | narrative.md The story in brief`.
- Mark each lore item settled or provisional. Provisional lore may change without a log line;
  settled lore changes only by a logged decision.

## Where the work meets the Specwright flow

- A proposal for a narrative feature cites the `narrative.md` section, or the GDD's World and Story
  section at light weight. Story not yet designed is designed here first.
- Dialogue lines, lore entries and unlock conditions are content data with stable keys. They are
  not text frozen into specs.
- Triage: a text-only edit to existing keyed content counts as tuning. A new beat, branch or story
  state is new behaviour and is designed here before the proposal. `gamedev-design` runs the
  classification.
- Feel versus presence: whether a scene's tone, pacing or reveal lands goes to the `[user]`
  playtest task. The presence of a line, a key or a journal entry may go to an `[evidence]` task or
  an automated test.
- Save data: state which story variables, flags and storylet state must persist, so the save
  version and its migration cover them.
- Flag to `gamedev-design`: a story fail state (a deadline, a failed final check) so it gets a
  check that doing nothing does not win; a story reward (item, currency, reputation) so its
  sources and sinks are recorded; any implied mechanic change.
- Flag to `gamedev-ux`: what must be reviewable (journal, replay of a conversation), what must be
  skippable, and whether the world keeps running while the player reads.

## Player-visible beats

When a change makes a story beat visible to the player, propose scenarios or playtest questions
that reuse the GDD's feel and tone words. Typical questions: did the player read the scene with the
intended tone; did they grasp the reveal; can they say why their character acts as they do. These
feed the `[user]` playtest task that `gamedev-playtest` runs.

## Consistency checks

Run on request, after a large story change, or before a story-heavy milestone. Look for motive
gaps, timeline contradictions, knowledge used before it was learned, and reveals that some
reachable play order breaks. Report each as a question or a suggested fix. Never rewrite canon on
your own. The detailed method is in `references/story-craft.md` (Consistency passes).

## Review checklist

Findings are questions and suggested fixes for a creative area. They are not scores and not
mandatory rewrites. State severity in words. A check whose input is missing (no GDD, no beat list)
reports "not assessed", never a pass. The full checklist, grouped by area, is in
`references/story-craft.md` (Review checklist). Blocking before story features are built: no
premise; no beats; story that contradicts the GDD's mechanics or progression; required story that
is reachable only by chance.

## Avoid

- Presenting invented premise, cast or lore as settled.
- A `narrative.md` for a none or light game, or one full of empty headings.
- Editing the GDD directly; drifting into HUD, layout or input (UX) or mechanics (design).
- Lore the player never touches; many coined terms early; branching or barks that multiply text
  without changing outcomes the player cares about.
- Beat lists that assume an order the layout or run structure does not enforce.
- Plots told as "and then" lists; choices with a free best option; one good-versus-evil meter.
- Deadlines the game never enforces; barks that repeat until they grate.
- Mysteries with no recorded answer; provisional lore treated as canon, or the reverse.
- Scoring story quality or correcting the user's taste.
- Treating counts (words, variants, cooldowns) as rules. They are starting hypotheses tuned in
  playtest.
- Monetisation hooks in story (paid choices, timed story gates) presented as neutral design.
- Engine-specific translation or file advice.

## References and template

| File | Read it when |
|---|---|
| `references/story-craft.md` | You need craft guidance on a topic: premise, tone, structure, beats, cast, world, dialogue, delivery, endings, objectives, choices, barks, urgency, clues, storylets, mysteries, text budgets, translator brief, the consistency pass or the review checklist. Use its contents list and load only the part you need. |
| `references/order-and-repetition.md` | The game is run-based, roguelike, nonlinear, backtracking, systemic or episodic, or relies on environmental storytelling. |
| `templates/narrative.md` | The weight is moderate or heavy and a conversation first needs the document. Copy it beside the GDD and prune it to the weight. |
