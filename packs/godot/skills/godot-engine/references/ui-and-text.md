# UI, pixel art and text

Turning a UX spec or HTML prototype into Godot scenes, and the project settings that decide how it looks on screen. Read the project's current settings first; never assume them.

## Tokens to a Theme

- Design tokens become one `Theme` resource: colours, fonts, font sizes and constants.
- Panels and buttons use `StyleBoxFlat`, or `StyleBoxTexture` for pixel-art nine-slices, with one box per state: normal, hover, focus, pressed, disabled.
- Where practical, name theme type variations after the tokens (for example `HeadingLabel`, `DangerButton`), so a design name and a theme name match.
- The focus StyleBox should match the prototype's focus ring, not the engine default.

## Screens as Control scenes

- Each screen is its own `Control` scene, instanced by a small scene-switching service.
- Overlays such as pause or a dialog sit on a `CanvasLayer`.
- Use containers and anchors, not hand-placed pixel positions. A layout that survives a different window size and longer text is the goal.
- Set `mouse_filter` to ignore on decorations laid over buttons, or they swallow clicks.

## Focus and gamepad navigation

- The built-in actions are `ui_up`, `ui_down`, `ui_left`, `ui_right`, `ui_accept`, `ui_cancel`, plus `ui_focus_next` and `ui_focus_prev`. Check they are mapped to the gamepad in the Input Map.
- Godot picks the closest control in each direction by itself. Where that guess is wrong, set the `focus_neighbor_*` properties, and `focus_next` / `focus_previous` for the tab order.
- When a screen opens, give focus to its default control: `$StartButton.grab_focus.call_deferred()` in `_ready`. A control that becomes hidden loses focus, so re-grab it when a panel reopens.
- Focus gained by mouse or touch is not drawn; keyboard and gamepad focus is. Check the focus visuals both ways. (`grab_focus()` takes an optional `hide_focus` argument to suppress the highlight.) Newer engine releases changed how mouse and keyboard focus are tracked; look at the project's version before relying on either.
- Test every menu with a gamepad alone: reach every control, activate it, and back out with `ui_cancel`.

## Pixel-art scaling

Project Settings, Display > Window:

- **Base size:** `display/window/size/viewport_width` and `viewport_height` — the resolution the art is drawn at.
- **Stretch mode** (`display/window/stretch/mode`): `viewport` renders the scene at exactly the base size and scales the finished image; it is the documented choice for pixel art. `canvas_items` stretches the base size to the window, which keeps UI and fonts crisp at high resolution. `disabled` does no stretching.
- **Aspect** (`display/window/stretch/aspect`): `keep` adds bars to preserve the ratio; `expand` keeps the ratio but lets the viewport grow in either direction; `keep_width` and `keep_height` grow one axis.
- **Scale mode** `integer` (since 4.2) rounds the scale down to a whole number and fills the rest with black bars. It prevents uneven pixels.
- Projects created from 4.7 on default to `canvas_items` and `expand` (before: `disabled` and `keep`). Read what the project holds.

Filtering and snapping:

- Set the texture filter to Nearest for the whole project at Rendering > Textures > Canvas Textures > Default Texture Filter, or per node with `texture_filter`.
- Leave mipmap generation off on pixel-art textures.
- Consider `rendering/2d/snap/snap_2d_transforms_to_pixel`: positions snap to whole pixels, which looks crisper but makes slow movement and smoothed cameras less smooth.
- Check text at the base resolution, not only scaled up.

## Localization

- Keep text in a CSV or gettext PO file keyed by stable ids (`MENU_START`, `LEVEL_5_NAME`); register the files under Project Settings > Localization. In a CSV, the first column holds the keys and each other column header is a locale.
- Never key by the English sentence, and never glue sentences from fragments (word order differs). Use placeholders: `tr("DAMAGE_DEALT").format({"amount": 12})`.
- Use `tr()` in scripts. Controls such as `Label` translate their text automatically through their `auto_translate_mode` (a `Node` property).
- Switch language with `TranslationServer.set_locale("de")`.
- Plurals: `tr_n("APPLE", "APPLES", n)`. CSV plurals (a `?plural` column) exist from 4.6; before that, use PO. Automatic Control translation does not apply to plural strings, so call `tr_n()` yourself.
- A `?context` column or the context argument separates identical keys that need different translations.

### Text-fit test

For each shipped locale, and with pseudolocalization on, set the locale, await a frame, then assert that no label overflows its container. Leave room for roughly 30% longer text than English.

- Pseudolocalization: the project setting `internationalization/pseudolocalization/use_pseudolocalization` (read at start-up), or toggle `TranslationServer.pseudolocalization_enabled` at run time.
- Run it as a scene test or a scripted run (`automated-checks.md`); a still screenshot (`evidence-runs.md`) can accompany it.

## Screen readers

Godot has screen-reader support through the AccessKit library, controlled by the project setting `accessibility/general/accessibility_support`. It switches on automatically when a screen reader is running. If the UX spec asks for screen-reader use, check that the project's engine version has it before promising it.
