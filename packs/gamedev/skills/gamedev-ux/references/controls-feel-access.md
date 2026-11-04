# Controls, feel and access

Working knowledge for the controls, feedback and accessibility side of `ux.md`. Figures are starting hypotheses; name the source and let the user change them.

## Control table

Cover menu actions as well as play, for every declared device. For each action record the binding per device, whether it is hold or toggle, and whether it can be remapped. Record the glyph families (one per device family, plus a generic set), how the prompts switch live when the device changes, and how remap conflicts are handled (swap, refuse, or warn).

Regional conventions change which button confirms and which goes back on some platforms. Decide whether the game follows the platform's convention or one fixed layout, and record that choice in the concern scan.

## Prompts that follow bindings

- A prompt always shows the current binding, including remaps.
- Tap, hold and repeated-press prompts look different from each other (a plain glyph, a glyph with a fill ring, a glyph with a count).
- Every glyph has a text label that a screen reader or a caption can use.
- An unrecognised device gets the generic glyph set, never a wrong brand set.

### The flicker guard

Switching glyph sets on every stray input makes prompts flicker. Guard it:

- switch only on deliberate input (a button press, a key press, a pointer click, a deliberate move);
- ignore stick drift and small analogue noise below a dead-zone you declare;
- do not switch back until the other device has had a deliberate input, with a short settle time if needed;
- never change the set in the middle of showing one prompt.

Record the dead-zone and settle values as starting guesses and have them tested with a worn controller.

## Per-device completeness

For each declared device check these items, and record the result per device:

- Back never quits the game from a screen. Quitting is an explicit choice with its own confirmation.
- Focus is trapped inside modals; it cannot escape to the screen behind.
- On a gamepad the directional pad alone reaches everything.
- For a mouse, right-click and scroll are defined (even if the definition is "does nothing").
- Pointer and touch targets meet a stated minimum size. Start from public platform guidance and record the source.
- A device unplugged mid-screen pauses the game and prompts the player to reconnect.

## Building blocks

Define a short set of interaction building blocks once, and refer to them from components and flows rather than re-describing input each time.

Typical set: move focus, confirm, back, switch tab, page, hold to confirm, quick action, open pause. Add or drop per game. For each block record the action on each device and what happens at an edge (does focus wrap, stop, or leave the list?).

## Component behaviour apart from component look

Keep two lists. Behaviour says what a component does, which inputs act on it, its states and its rules. Look says which tokens it uses in each state. Each component name appears in both places, spelled the same, so a builder can join them.

When the game uses the engine's UI layer, name it and record only where the game departs from that layer's defaults: focus behaviour, navigation, theming. When a stack pack is enabled, its skill owns the actual handoff.

## Transitions as a frequency budget

The more often the player passes through a transition, the shorter it should be.

| Frequency | Treatment |
|---|---|
| Constantly (menu tab, focus move) | Almost instant; feedback only |
| Often (opening inventory, dialogue) | Short |
| Occasionally (entering a level) | May be longer, with a purpose |
| Rarely (chapter break) | May be ceremonial |

Pause opens at once. Name the audio for each transition: cut, fade, duck, or switch on a beat. Music cut only because a menu opened is a finding.

## Audio roles

Define the mix roles (for example music, effects, voice, UI, ambience). State which role ducks which, and when. Give each role its own volume control in the options. Sounds that the player must act on need a visual cue as well (see the audits below).

## Feedback and restraint

- Timing and intensity numbers (transition length, shake, hit-pause, flash) are starting guesses for a playtest. Keep them in data the game loads, not in code, so they can be retuned without a rebuild.
- Each flash or shake row names its reduced-motion behaviour in the same row.
- Motion serves information. There is no constant ambient motion: no idle wobble on buttons, no endless pulsing. A pulse that repeats a few times and settles is fine.
- Feedback names what happened: confirm, deny, error, new, level-up. Differences between them come from more than colour.
- An HTML prototype cannot judge timing or feel. Questions about them go to an in-engine check or a playtest through `gamedev-playtest`.

## Readability and flash minimums

State in `ux.md` the reference resolution and the viewing distance. At that reference, record:

- minimum text height;
- minimum icon size;
- caption format (about two lines, with a speaker label);
- the flash limit (fewer than three flashes in any one second, which follows WCAG's general guidance on flashing).

Re-derive each figure from public guidelines, for example WCAG, published platform guidance and published game-accessibility guidelines. Name the source beside the number and treat it as a starting hypothesis. A figure for a couch at three metres is not the figure for a handheld at arm's length.

Contrast starting points from WCAG: 4.5:1 for normal text, 3:1 for large text and for the shapes that carry meaning. Check them over real gameplay backgrounds, not flat panels.

### Shrink check

View the mock-up or captured screen at about a third of its size. The ranked HUD information must still read. Record the result in *Readability*. If it fails, the ranking or the sizes are wrong.

## Accessibility floor

Size each item with the user by audience and stakes. Each is either met or deferred by a recorded decision.

- Remapping on every declared device.
- No meaning by colour alone.
- Contrast.
- Text and HUD scale.
- Subtitles and captions with speaker labels.
- Reduced motion, reduced shake and reduced flash.
- Hold versus toggle, and adjustable timing.
- Full play and menus without a pointer.
- A volume control per audio role.
- Options reachable before first play, and persisted.
- Pause wherever it is safe.

## Three audit tables

Keep these in the *Accessibility* section of `ux.md`.

| Table | Columns |
|---|---|
| Colour-only signals | Signal, backup (shape, icon, text, pattern) |
| Sounds the player must act on | Sound, visual cue |
| Features deliberately left out | Feature, risk, who it affects |

An empty table is only acceptable with a line saying why.

## Concern scan

Before a spec is called complete, walk this list and record a decision or "not in scope" for each.

| Concern | Prompts to ask |
|---|---|
| Localization and text expansion | Longer languages, other scripts, fallback fonts, stable string keys, layouts that survive 30-50% longer text |
| Button-prompt localization | Regional confirm and back swaps, glyph sets per platform family, order of words around a glyph |
| Performance | HUD and menu cost on the weakest target, effect counts, texture memory for glyph sets |
| Motion sensitivity | Shake, flashes, camera bob, parallax, rapid flicker |
| Cultural elements | Symbols, colours, gestures and icons whose meaning changes by region |

The text-expansion allowance above is a starting guess; check it against the real target languages.
