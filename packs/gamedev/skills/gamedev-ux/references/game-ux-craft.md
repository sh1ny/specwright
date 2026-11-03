# Game UX craft

Working knowledge for the screen and HUD side of `ux.md`. Every figure here is a starting hypothesis for the user to change, not a rule.

## Where information lives: four presentation categories

Pick a category per element and record it.

| Category | Meaning | Good for | Watch for |
|---|---|---|---|
| Overlay | Drawn on the screen, outside the game world | Numbers, lists, menus, anything that must stay still | Crowding the action area |
| In-world | Part of the world the characters could also see | Dials on a vehicle, a lit door, a wall map | Readability at distance and from odd angles |
| World-anchored | Drawn in screen space but pinned to something in the world | Names, health over an enemy, interact prompts | Overlap, jitter, occlusion, clutter at crowd sizes |
| Screen effect | Alters the whole picture | Low health vignette, damage direction, focus blur | Motion sensitivity, hiding the action |

A single fact can use two categories at once: a gauge in the corner and a vignette at the edge. The second one is the escalation, not a duplicate.

## Ranking the HUD

1. List every fact the player might want during play.
2. Rank by how often they need it and how costly missing it is. Frequent and costly goes first.
3. Give each element an anchor (corner, edge, centre, world-pinned), a category, and a rule for when it fades or hides.
4. Information vital in active play is never hidden without the user's explicit decision.
5. Placing the most-glanced items near where the eyes already rest (usually near the action, but outside it) costs less than far corners. On a large screen viewed from a sofa, corners are slow to reach by eye.

Ask the user for their own ranking before proposing one. Present your ranking as a draft.

## HUD by context

Games change what the player needs from moment to moment. Build a table with the user's own list of contexts across the top (for example exploring, fighting, dialogue, cut-scene, menu open, death or fail, loading) and the elements down the side. Each cell is *shown*, *faded* or *hidden*. Add one default rule for any context the table does not name ("unlisted contexts show the exploring column", or whatever the user picks).

Keep the table small enough to read. If a cell is hard to decide, that is a question for the user, not a cell to fill with a guess.

## Urgency and replacements

An element that can become urgent defines three states: normal, warning, critical. For each, say how it escalates through shape, motion or sound as well as colour. Examples: a gauge outline thickens and gets a notch; an icon gains a border and a short tone; a pulse runs a few times and then stops.

If an element is hidden in some context, record what replaces it. Options: an in-world cue, a sound, a screen-edge effect, or "nothing, accepted by the user". An empty replacement cell is a gap.

## Numbers, meters and icons

| Form | Best when | Cost |
|---|---|---|
| Number | Exact values drive decisions (ammunition, currency) | Slow to read at a glance |
| Meter | Proportion and trend matter (stamina) | Imprecise; needs a scale or markers for thresholds |
| Icon or pip row | Small counts (lives, charges) | Breaks down when the count grows |
| Combination | Both a glance and an exact value matter | More space |

Choose per element, and say why in one line.

## Screen-space budget and the action area

- Decide, with the user, how much of the screen the HUD may take per context. This is a recorded decision, not a universal cap. A calm exploration view may allow more than a hectic fight.
- Mark the action area, the part of the screen where play happens (the character, immediate threats, targets). Keep persistent HUD and notifications out of it.
- Check the budget with the shrink test in `controls-feel-access.md`.

## Two safe areas

Keep two tighter rectangles inside the full frame.

- **Action-safe**: everything the player must see lives inside it, because some displays crop or round the edge.
- **Text and static HUD**: tighter still, for text and persistent widgets.

Derive starting margins from the declared displays and public platform guidance (platform holders publish title-safe guidance; broadcast practice is a familiar reference). Record them as percentages or reference-pixels with their source. Offer the player a margin adjustment in options if any declared display is a television.

## Shake, hit-pause and text over the play field

- Shake, hit-pause, zoom and other camera effects act on the world layer only. The HUD and text stay still. A shaking HUD reads as a bug and is hard on motion-sensitive players.
- Text over the play field needs a plate, outline or shadow so it reads over any background. Check against the lightest and darkest real backgrounds the game shows, not a flat mock.

## Element data ownership

For each HUD element and each widget on a screen, record:

- the game system that owns the data;
- the event that updates it (the player changed weapon; the timer ticked; the inventory changed);
- what it shows while the data is missing or absent (a dash, a greyed icon, nothing).

Screens send events or requests ("use item", "equip"). They never write game state directly. This keeps the interface replaceable and testable.

## Notification queue

One queue for transient messages, with these decisions recorded:

- Priority levels (for example info, reward, warning, critical).
- Merge rule for repeats ("+1 coin" ×3 becomes "+3 coin").
- How many may show at once. This is a user decision; start from a small number and playtest it.
- Behaviour in intense contexts: defer them, or compact them to icons.
- Critical messages (save failed, device lost, progress about to be lost) never wait in the queue.
- Every message also lands in a log the player can reopen, so a missed message is not lost.

Too many pop-ups usually means one of three things: nothing merges, nothing is deferred in action, or low-value events were promoted to messages. Look at those before cutting content.

## Things that look usable

Anything the player can use should look usable, in one consistent visual language (the same highlight, shimmer, outline or marker everywhere). Anything that looks usable but is not is a finding: either make it usable or restyle it to read as scenery. Record the language once and reuse it in the *Look* section.

## Wayfinding

How the player finds their way is a user decision. Options:

- in-world signposting (light, landmarks, paths, colour coding of space);
- markers on screen or on a map;
- a compass or bearing strip;
- a mix.

If markers exist, the player can switch them off. If the complaint is "players do not find the door", look at in-world cues first, and then ask which stance the user wants before adding a marker.

## Teaching and hints

- For each core verb in the GDD, record how it is first taught: a safe in-world situation, a prompt, a practice space, or text. Record when its prompt retires.
- Learning by doing is a good default where it works. Explicit teaching is also a valid choice; it is not evidence the design failed.
- Record one hint stance as a user decision: opt-in staged hints, stuck detection, or none.
- Assisted completion (skips, assist modes) is labelled as such, without erasing the player's achievement.

## Confirmation by stakes

| Stakes | Treatment |
|---|---|
| Cheap and reversible | No confirmation |
| Costly | A confirm step; focus starts on the safe option |
| Irreversible | A hold, or an equally deliberate act |

Prefer undo over confirmation wherever the game can offer it.

## Arrival state

For each key screen (pause, inventory, shop, map, death or fail, results), record what the player was just doing and what they most likely want next. That decides first focus and what the screen shows first. Returning from a fight, the inventory may open on consumables; returning from a shop, on the item just bought.

## Stories and failure paths

- A play-through story is a named player in a concrete situation, with numbered steps, and the moment that matters most.
- Every key flow names at least one failure path (device unplugged, save fails, not enough currency, death while a menu is open, lost connection) and says where it leaves the player.
- Reachability: every player need lands on a screen, HUD element or in-world prompt, and every screen is reached by some story. A gap is asked about, never filled by invention.

## Screens games often need

Use this to spot gaps; take only what applies and ask about the rest.

- Lifecycle: logo or splash (skippable), title, first-run options, load, save, quit.
- Play: HUD, pause, map, inventory or loadout, quest or goal list, dialogue, shop or trade, crafting or upgrade.
- Outcomes: death or fail, retry, results, reward, credits.
- Meta: options (controls, video, audio, accessibility), profile or slots, achievements, help or controls reference, message log, language.
- Edge cases: device lost, save failed, connection lost, error, empty list, age or content notices.
- Optional extras: damage numbers, cooldown displays, radial menus, photo mode.

Notes: long menus and many simultaneous choices strain working memory; group or page them. Logos should be skippable, options should be reachable before the intro, and a retry should never force a replayed cut-scene. For handheld targets, check legibility at that size and what suspend and resume do mid-screen. Offer player-adjustable HUD settings (scale, opacity, element toggles) where the user wants them.
