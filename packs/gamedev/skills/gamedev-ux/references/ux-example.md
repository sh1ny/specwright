# Worked example: a filled `ux.md` (abridged)

Premise: a small 2D harbour-delivery game, pixel art at 320x180, gamepad first with keyboard support, played on a handheld and on a TV. All names and values are invented for this example; every number is a starting guess.

## 2. Play context
Handheld at arm's length, TV at about 2.5 m. Base stage 320x180, integer scaling. Devices: gamepad (primary), keyboard. The engine's UI layer is used; the game departs from its defaults only in focus (single focus, no mouse hover on pad).

## 3. Screen map
| Screen | Entry | Arrival state | First focus | Back | Exits | Coverage |
|---|---|---|---|---|---|---|
| Pause | open pause | mid-delivery, wants to resume or check the route | Resume | resume | Route, Options, Quit (confirm) | prototyped (`prototypes/pause.html`) |
| Cargo | from Pause or at the dock | just loaded or unloaded crates | first crate | previous screen | Pause | prototyped |
| Tide chart | from Route | planning the next trip | today's tide | Route | Route | spec-only (confirmed 03 Nov) |

Overlays sit on top of the paused game and do not replace it.

## 4 and 5. HUD ranking and by context
Ranked: 1 boat damage, 2 cargo time left, 3 coins, 4 route marker.

| Element | Sailing | Docking | Dialogue | Menu open |
|---|---|---|---|---|
| Boat damage | shown | shown | faded | hidden |
| Cargo timer | shown | shown | hidden | hidden |
| Coins | faded | shown | hidden | hidden |

Default rule: any unlisted context behaves like Sailing. Boat damage hidden in Menu open: replaced by "nothing, accepted by the user" because play is paused.

## 6. Element data (one row)
| Element | Owner | Update event | Missing data |
|---|---|---|---|
| Cargo timer | delivery system | `delivery_tick` | dash and greyed icon |

## 8. Controls (excerpt)
| Action | Gamepad | Keyboard | Hold / toggle |
|---|---|---|---|
| Confirm | south button | Enter | tap |
| Back | east button | Esc | tap |
| Steer | left stick | A / D | hold |

Prompts switch on a deliberate button press; stick values under the dead-zone (0.25, a starting guess) are ignored.

## 9. Building blocks
- **move focus**: D-pad or stick (pad), arrows (keyboard); stops at list ends.
- **confirm**: tap; costly actions use the confirm step.
- **back**: closes the top overlay; never quits.

## 10. Component: Crate row
Behaviour: shows one crate; confirm picks it up; back leaves the list; states are normal, focused, locked (not yet unlocked). Confirmation: none, since the move is reversible.
Look: normal uses `surface`; focused adds the `--color-game-interact` outline; locked uses a padlock icon at 50% contrast (checked against the backdrop, see Readability).

## 18. Story: Mira loses her pad
Mira is on a fast delivery with 40 seconds left.
1. She steers into the canal.
2. Her pad battery dies.
3. The game pauses and shows "Controller disconnected" with the generic prompt set.
4. She plugs in the keyboard; prompts switch to keyboard labels after her first key press.

Moment that matters: step 3, the pause must happen before the next collision. Failure branch: if no device returns, the Pause screen offers Quit with a confirm step; the delivery is saved and resumes at the dock.

## 16. Audits (one row each)
| Colour-only signal | Backup |
|---|---|
| Low timer turns red | Icon gains a notch and ticks once a second |

| Sound the player must act on | Visual cue |
|---|---|
| Foghorn warning | Edge flash of fixed shape, reduced to a static band under reduced motion |

| Left out | Risk | Affects |
|---|---|---|
| Text-to-speech for menus | Blind players cannot navigate menus | blind and low-vision players |

## 17. Concern scan (two lines)
- Localization: not in scope for the demo; string keys are stable so it can be added.
- Motion sensitivity: wave sway on the world layer only, and a setting turns it off.

## 19. Look (three tokens)
| Token | Value | Fallback role | Carried also by |
|---|---|---|---|
| `--color-game-health-low` | `#d94b3a` | `negative` | notch in the hull icon |
| `--color-game-currency` | `#e8c24a` | `accent` | coin icon |
| `--color-game-interact` | `#7fd1c4` | `focus` | outline shape |

## 20. Open questions
- Should the cargo timer fade during dialogue or pause? (section 5, user)
- Tide chart is spec-only until the route design is settled.
