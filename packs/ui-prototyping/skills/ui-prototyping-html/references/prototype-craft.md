# Prototype craft

How to build, show and review a clickable single-file prototype. `SKILL.md` has the outline; this
file holds the detail. Tokens and contrast live in `design-tokens.md`.

## Question and fidelity

- Write the question in one sentence the viewer can see in the control bar. "Which of these two
  list layouts makes the newest item easiest to find?" is a question. "Does it feel good?" is not,
  and "is the fade too slow?" is a timing question that goes back to the caller.
- Two questions are two files. Mixed feedback cannot be read.
- Match fidelity to the question:
  - flow or structure: boxes, labels, real wording, no colour decisions;
  - hierarchy or density: real type sizes and spacing from tokens, flat colour;
  - look: full token set, type, depth and texture, still marked as a prototype.
- A prototype that looks finished invites comments on polish. Keep placeholder boxes and the dashed
  stage edge visible unless the question is about the final look.

## Should the screen exist?

Before drawing anything, ask and write down:

1. Could this screen be removed, or merged into the one before or after it?
2. What was the user doing just before they arrived here?
3. What do they do next, and how do they get there?

If the honest answer is "it should not exist", say so and do not prototype it. Record the answer in
the settings block's comment so the reason stays with the file.

## Content and placeholders

- Use real labels and figures from the conversation or the spec. Names, counts and messages should be
  ones the project would show.
- Where content is undecided, use a believable stand-in and mark it: the template's `placeholder`
  tag, or a labelled `.ph` box. A marked stand-in is honest; an unmarked one gets mistaken for a
  decision.
- No filler text, no emoji used as art, no screens copied from well-known products. Draw art as
  labelled boxes or the template's inline-SVG silhouette.
- Placeholder sizes: neutral boxes by default. When the caller asks for base-pixel multiples, size
  boxes in whole multiples of the base unit so alignment questions are honest.

## Surfaces

Pick 2-4 surfaces that carry the decision. For each, name where the eye should land first and make
that element the visually dominant one. If a fifth surface seems necessary, split into a second
file with its own question. Counts like "2-4" are starting values, not laws: the real limit is
whether the viewer can still answer the question.

## States and the switcher

- Each surface offers its states through the bar's state switcher and the `S` key. The default set is
  empty, loading, error and full. Callers add more, such as locked.
- In the markup, a state is a variant block marked `data-state="empty"`; a block may list several
  states separated by spaces. Only the active state shows. The switcher reaches every state the
  settings name, and tells the viewer in the note line when a screen has no variant yet. Fill the gap
  before showing.
- Prefer showing a hard state to building a second happy path. An empty list and a failed load teach
  more than a second list full of items.
- Status and severity (error, warning, success) carry an icon or a word plus colour. The template's
  `.status` block has all three.

## Options

- Put 2-3 options in the same file when a direction is open. Name each with a short register
  ("airy and rounded", "dense and square").
- Options differ in personality: density, weight, shape, motion, depth. Two options that differ only
  by hue are one option.
- Tokens are overridden per option with an attribute selector on `:root[data-option="b"]`. Elements
  that exist in only one option carry `data-only="b"` and are hidden in the others.
- Toggle from the bar or the `O` key. After the user picks, delete the losing option's overrides and
  `data-only` elements unless they ask to keep them.

## Focus, keyboard and the input model

Every model keeps these true: nothing is hover-only, every control is reachable from the bar and the
keyboard, focus is never lost, and the first focus matches the spec (mark it `data-first-focus`).

- **pointer-keyboard** (default): native tab order, click, Enter, Escape for back. No custom key
  handling beyond the bar shortcuts.
- **single-focus**: arrows move one focus through the active screen (or the top modal) and wrap;
  Enter or Space confirms; Escape or Backspace goes back; hovering with the pointer moves the same
  focus. The caller names the confirm and back keys if they differ.
- **touch**: larger targets via `--target-min`, no hover-only affordances, no reliance on right-click
  or long press.

Focus marker: draw it with `outline` and `outline-offset`, not with borders or padding. Changing box
size on focus shifts grid and flex rows, which makes the marker itself look like a layout bug. The
template also adds a halo ring so the marker is a shape, not only a colour.

## Modals

- Open modals live inside the stage so they scale with it.
- Focus moves into the modal on open and returns to the opener on close. Tab and Shift+Tab wrap
  inside the topmost modal. If something else grabs focus, it goes back.
- Escape closes only the topmost modal. The back key (Backspace in single-focus) does the same. When
  no modal is open and the history is empty, back does nothing: it never leaves the prototype and
  never jumps out of a nested modal.
- Test with a nested pair: open the first, open the second from inside it, press Escape once, and
  confirm only the second closed.

## Motion

Motion is optional and purposeful: showing a sequence, not decorating. No constant ambient motion; it
pulls the eye from the question. All motion durations come from `--motion-*` tokens. The bar's
"Reduce motion" button (and the `R` key) sets every duration to zero. The template starts that
button from the system's `prefers-reduced-motion` setting and follows later changes to it, so the
reduced path can be seen without changing system settings. Remember that a browser cannot judge timing; motion here shows order, not speed.

## Stage and scaling

- **Responsive** (default): the stage fills the window up to a readable maximum width. Its CSS sets no
  fixed pixel size.
- **Fixed**: the settings give a base width and height. The script computes the size, scales the stage
  by the available room, and centres it. With `scaling: "whole"` the factor is a whole number of
  steps (never below 1) and the stage is letterboxed by the page. With `crisp: true`, images and
  shapes render with nearest-neighbour sampling so edges stay sharp.
- Check a fixed stage by resizing the window: it must rescale, stay centred, stay crisp, and never
  show a fractional scale when whole steps were asked for.
- Safe-area guide: off by default. One switch shows two labelled rectangles: the outer action-safe
  area (dashed; default inset `--space-edge`, 1.5rem) and the tighter text-safe area (dotted; default
  inset `--space-6`, 2.5rem). A caller that names safe areas sets `safeArea.actionInset` and
  `safeArea.textInset` in the settings block (any CSS length or `var(--...)`) and turns the guide on;
  the bar and the `G` key toggle both together. Keep text and static overlays inside the inner
  rectangle.
- Do not assume small screens or touch. If the caller wants a narrow layout, they pass it.

## Where the eye lands

For each surface, view it at about a third of its size, or blurred. The element named as the first
landing point should still dominate. If something else wins, adjust weight, size, contrast or
position before showing. This is a quick check, not a measurement.

## Opening and deep links

- Open with the platform's default opener: `start "" "<path>"` on Windows (from a command prompt),
  `open "<path>"` on macOS, `xdg-open "<path>"` on Linux. If it fails, print the absolute path.
- A hash link reaches screens other than the first: `file.html#detail/full/b` opens screen `detail`
  in state `full` with option `b`. Give the user the links for the hard states you built.

## Scripted walkthrough (optional)

When a headless browser is available, a script may:

1. open the file from disk and read `window.proto` (screen, state, option, focus, model, open modals,
   errors);
2. press the keys through every screen, state and option, reading `window.proto` after each step;
3. take a screenshot at each step, collect `window.proto.errors`, and stop at the first new error.

Besides the read-only fields (also `guide`, `reducedMotion`, `glyphSet`), `window.proto` offers the same
switches as the bar: `go`, `back`, `setState`, `setOption`, `setModel`, `setMotion`, `setSafeArea`,
`setGlyphs` and `refit`. Each setter is idempotent, and switching A to B and back to A restores
exactly what A showed.

It is a pre-show aid that finds breakage. It is never the verdict, and an agent's screenshots are
not a playtest. Only the user's look and choice decide.

## Pre-show list

**Opens anywhere**
- No `http` or `https` in any `src` or `href`; no `@import`; no web font; no external image.
- The file parses; no script error on load or after any key action.

**Answers its question**
- The question is visible and is not about timing or feel.
- Only the agreed surfaces. The reason each screen exists is recorded.
- Content is real or marked as placeholder. Each option is named and distinct.

**Shows the hard states**
- The state switcher reaches every state the settings name, on every surface.

**Navigable**
- Every screen, state and option is reachable from the bar and the keyboard.
- The declared input model works on every screen; focus is never lost; first focus matches the spec.
- Nothing is hover-only. Modals trap focus; Escape never leaves the prototype.

**Faithful**
- Every colour, size, corner and shadow is a token variable; tokens match the spec.
- Any new value is flagged as a proposal. No component the spec lacks.

**Readable**
- Text contrast at least 4.5:1; large text and key shapes at least 3:1.
- Status never by colour alone. The shrink or blur check passes.
- A fixed stage scales as the settings say and stays crisp.

## Reviewing against a spec

1. Run the pre-show list on the existing file.
2. Compare with the spec: tokens in sync (names and values), screens and states present, flows match,
   settings header matches what the caller expects.
3. Report each difference with a severity written as a word (blocker, major, minor, note) and say
   which side it is on.
4. Ask which side should change. The spec wins unless the user decides otherwise.

## Coverage pass

1. List every screen the spec defines.
2. Mark each *prototyped* (name the file and the question it answered) or *spec-only*.
3. Show the list to the user. They confirm the spec-only screens; do not decide for them.
4. If the calling skill keeps a coverage table, hand the result back for it to record.

## Failure modes to watch for

- A prototype that needs a server, the network or a build to open.
- Several questions in one file; only the happy path shown; a second happy path where a hard state was
  needed.
- Prototyping a screen that should have been removed or merged.
- Using a prototype to judge timing or feel.
- Treating the walkthrough or screenshots as the verdict.
- Invented layout, components or content later mistaken for decisions.
- Options that differ only by hue; status by colour alone; constant motion.
- Domain assumptions leaking into the defaults (pixel fonts, a fixed stage, single-focus input,
  mobile-first layout) when no caller asked.
- Hover-only controls; Escape leaving the prototype from a nested modal; focus leaking out of a modal.
- The caller's settings lost on a later edit.
- Token names drifting between the spec and the CSS.
- Numeric caps stated as rules rather than starting values with a source.
- Versioned copies piling up beside the real file.
