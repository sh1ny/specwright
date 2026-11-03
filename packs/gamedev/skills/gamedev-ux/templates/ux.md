# UX: <game title>

<!-- Created by gamedev-ux. Omit sections that do not apply. Mark anything unconfirmed with
"(unconfirmed)" in place and repeat it under Open questions. Every number is a starting
hypothesis: name its source. Link the GDD; do not copy it. -->

## 1. Reading this document

This document is the source of truth for the interface. Prototypes linked below illustrate it; where they disagree, this document wins. GDD: <link>. Narrative: <link>. Decision log: <link, if any>.

## 2. Play context

- Platforms: <...>
- Viewing distance per platform: <...>
- Reference resolution (base stage): <...>
- Input devices, primary first: <...>
- The engine's UI layer, and only where the game departs from its defaults (focus, navigation, theming): <...>

## 3. Screen map

| Screen | Entry from | Arrival state (what the player was doing, what they want next) | First focus | Back does | Exits | Coverage |
|---|---|---|---|---|---|---|
| <name> | <...> | <...> | <...> | <...> | <...> | prototyped (<link>) / spec-only |

Stacking rule (does an overlay replace the screen below or sit on top): <decided once here>

Confirmed spec-only screens: <list, confirmed by the user on <date>>

## 4. During play

- Ranked information (most needed first): <...>
- Per element: anchor, presentation category (overlay, in-world, world-anchored, screen effect), fade or hide rule.
- Screen-space budget per context (a user decision): <...>
- Action area (kept clear of persistent HUD and notifications): <...>
- Action-safe area: <margins, source>. Text and static-HUD area: <margins, source>.

| Element | Rank | Anchor | Category | Fades or hides when |
|---|---|---|---|---|
| <...> | <...> | <...> | <...> | <...> |

## 5. HUD by context

| Element | <context 1> | <context 2> | <context 3> |
|---|---|---|---|
| <...> | shown / faded / hidden | <...> | <...> |

Default rule for contexts not listed: <...>

Urgency states (normal, warning, critical) and how each escalates by shape, motion or sound as well as colour:

| Element | Warning | Critical |
|---|---|---|

Replacement for each element hidden somewhere: <in-world cue, sound, screen-edge effect, or "nothing, accepted by the user">

## 6. Element data

| Element or widget | Owning game system | Update event | Shown while data is missing |
|---|---|---|---|

Screens send events or requests; they never write game state directly.

## 7. Notifications

- Priority levels: <...>
- Merge rule for repeats: <...>
- Shown at once (starting value, user decision): <...>
- During intense contexts: <defer or compact>
- Critical messages (save failed, device lost, progress about to be lost) skip the queue.
- Message log the player can reopen: <where>

## 8. Controls and prompts

| Action | <device 1> | <device 2> | Hold / toggle | Remappable |
|---|---|---|---|---|
| <menu and play actions> | <...> | <...> | <...> | <...> |

- Glyph families and generic set: <...>
- Device switching guard (deliberate input only, stick-drift threshold, no flicker): <...>
- Conflict handling on remap: <...>

Per-device completeness (back never quits, focus trapped in modals, D-pad reaches everything, mouse right-click and scroll, minimum target size, unplug pauses):

| Device | Checked items and decisions |
|---|---|

## 9. Building blocks

| Block | Meaning | Per device |
|---|---|---|
| move focus | <...> | <...> |
| confirm | | |
| back | | |
| open pause | | |

## 10. Component behaviour

| Component | What it does | Inputs that act on it | States | Rules | Confirmation effort |
|---|---|---|---|---|---|

Confirmation effort: none for cheap reversible actions; confirm step with focus on the safe option for costly ones; a hold for irreversible ones. Prefer undo.

## 11. States and failure paths

| Screen or element | Empty | Loading | Locked | New | Danger | Error | Device lost |
|---|---|---|---|---|---|---|---|

## 12. Teaching, hints and wayfinding

| Core verb (GDD link) | First taught by | Prompt retires when |
|---|---|---|

- Hint stance (user decision): <opt-in staged hints / stuck detection / none>
- Assisted completion is marked as such: <how>
- Wayfinding stance (user decision): <in-world signposting / markers / compass / mix>. Markers can be turned off: <yes / n/a>

## 13. Feedback, transitions and audio

All values are starting guesses for a playtest, kept in data the game loads.

| Effect or transition | Value | Reduced-motion behaviour | Audio | Frequency |
|---|---|---|---|---|

- Playtest question: <...>
- Audio roles, which ducks which, and a volume control per role: <...>

## 14. Words on screen

Tone: <...>. Naming: <...>. String keys: <stable scheme>. Text expansion allowance: <...>. Caption format: <speaker label, line count>.

## 15. Readability

| Minimum | Value at the reference resolution | Source |
|---|---|---|
| Text height | | |
| Icon size | | |
| Flash limit | | |

Shrink check at about one third size: <result>

## 16. Accessibility

Floor items (met, or deferred by decision): <list>

Colour-only signals:

| Signal | Backup (shape, icon, text, pattern) |
|---|---|

Sounds the player must act on:

| Sound | Visual cue |
|---|---|

Features deliberately left out:

| Feature | Risk | Who it affects |
|---|---|---|

## 17. Concern scan

| Concern | Decision or "not in scope" |
|---|---|
| Localization and text expansion | |
| Button-prompt localization | |
| Performance | |
| Motion sensitivity | |
| Cultural elements | |

## 18. Play-through stories

### <Name>: <situation>

1. <step>
2. <step>

Moment that matters most: <...>

Failure branch: <what goes wrong, and where it leaves the player>

## 19. Look

- Register (the overall feel in a sentence): <...>
- Tokens (game roles; each names a fallback generic role and a non-colour carrier):

| Token | Value | Fallback generic role | Carried also by |
|---|---|---|---|
| `--color-game-<role>` | | | |

- Component visuals per state (same component names as section 10):

| Component | Default | Focused | Disabled | Danger |
|---|---|---|---|---|

- Depth, shape, type: <...>
- Cultural notes: <...>
- References (what each adds, what to avoid): <...>

## 20. Open questions

- [ ] <question> (section, who decides)
