---
name: ui-prototyping-html
description: "Builds clickable single-file HTML prototypes that settle an undecided layout or flow before it is specified, and captures visual identity as design tokens (owns the token schema and its CSS custom-property mapping). Neutral by default: system font, window-following stage, mouse and keyboard; a calling skill can pass stage, font, input model and save folder. Use for \"mock this up\", \"can I see it\", comparing layouts or styles, or checking a prototype against its spec."
---

# UI prototyping in HTML

You build small, throwaway design aids: one `.html` file the user opens by double-click, offline, to
answer one question about a layout, a flow or a look. You also own the shared vocabulary for visual
identity: design tokens, named by role, mapped to CSS custom properties.

## When to use it

- "Mock this up", "can I see it", "sketch the settings screen", "compare these two layouts", "try a
  darker look", "which style reads better", "what does it look like when it's empty".
- "Check this prototype against the spec."
- A domain skill hands over a prototype request together with its settings.
- A proposal has an undecided layout or flow: settle it with a prototype first, then link the
  prototype from the document it illustrates.

## What it is not

- **Not the spec.** The spec wins. A prototype illustrates a spec and decides nothing by being
  pretty. This skill creates no document of its own: chosen values go to the document the calling
  skill or the project names. With none named, show the tokens in the prototype and ask the user
  where to record them.
- **Not a judge of timing or feel.** A browser has uneven frame timing and different input latency.
  A question about timing, responsiveness or feel is declined and handed back to the caller for a
  check in the real product or a playtest. Motion in a prototype only shows sequence.
- **Not product code.** It builds design aids and writes no shipped UI. When a stack pack is enabled,
  use its skill for the handoff from a settled prototype to real UI.
- **Not domain-aware.** Defaults carry no domain vocabulary. Domain skills (a game UX skill, later
  web or desktop ones) own the spec, their token roles, what each prototype must answer and domain
  review. They pass settings in.
- **Not a gate.** Commit, review and verification stay with Specwright's own workflow. You never tick
  a task.

## Settings

The caller passes these; anything missing takes the neutral default. Say which defaults you used.

| Setting | Neutral default | Meaning |
|---|---|---|
| `question` | required, no default | The one question the prototype answers, in the user's words. Shown in the file. |
| `surfaces` | required, no default (2-4) | The screens that carry the decision. Never every screen. |
| `states` | empty, loading, error, full | States each surface can show; callers may add others, such as locked. |
| `stage` | responsive, fills the window up to a readable width | `fixed` instead takes a base width and height. |
| `scaling` | fluid | For a fixed stage: `fluid` fits the window in both dimensions; `whole` scales in whole-number steps (never below 1) and centres; `crisp` asks for nearest-neighbour rendering. |
| `font` | system UI stack (`system-ui` first) | A caller font stack always keeps offline fallbacks; never a web font. |
| `input model` | pointer-keyboard, native tab order | Or `single-focus` (arrows move, confirm and back keys, hover moves the same focus), or `touch`. |
| `prompt glyphs` | none | Labelled placeholder glyph sets, switchable from the bar. |
| `placeholders` | neutral labelled boxes | A caller may ask for shapes sized to a base-pixel multiple. |
| `safe-area guide` | off | One switch that shows two labelled overlays: an outer action-safe area (default inset: the edge token) and a tighter inner text-safe area (default inset: space step 6). The caller sets either inset; on when the caller names safe areas. |
| `token extensions` | none | Domain roles added as `<group>.<domain>-<role>` with a generic fallback each. |
| `save folder` | the calling skill's or project's folder, else `docs/prototypes/` | Where the file is written. |
| `spec link` | none | The spec sections the prototype illustrates; written into the file header. |

Write the received settings into the settings block at the top of the file, so a later edit keeps
them. Resolve the save folder in this order: the caller's folder, the folder the project's
instructions name, then `docs/prototypes/`. File names are short, lower-case and hyphenated.

## Workflow

### 1. Before building

1. **Should this screen exist?** Ask whether it could be removed or merged into another, what the
   user was doing just before it, and what they do next. Record the answer. A screen that should
   not exist is not prototyped.
2. **One question per prototype**, written where the viewer sees it. Several questions mean several
   files. Decline timing and feel questions.
3. Agree the **surfaces** (usually 2-4) and, for each, where the eye should land first.
4. Read the settings, fill gaps with the neutral defaults, resolve the save folder.
5. If the look is open, choose 2-3 **options** that differ in personality (density, weight, shape,
   motion, depth), not hue alone. Give each a short register name.

### 2. Build

Start from `assets/prototype-template.html`. It carries the control bar, the screen history, the
state switcher, option toggles, input models, modal handling, stage modes and the exposed state
object. Keep its mechanics; replace its sample screens.

- One file: inline CSS and script, no network, no CDN, no framework, no build step, no web fonts,
  no external images. It must work from `file://` with the network off.
- Content is real: labels and figures from the conversation or spec. Undecided content gets a
  plausible stand-in, visibly marked as a placeholder. No filler text, no emoji as art, no examples
  borrowed from well-known products.
- Fidelity follows the question: flow questions need boxes and labels; look questions need tokens,
  type and texture. Do not look like finished art, or viewers judge polish instead of the question.
- Show hard states (empty, loading, error, full or locked), not just the happy path. A hard state
  beats a second happy path.
- Everything is reachable from the bar and the keyboard. Nothing is hover-only. Focus is always
  visible and not signalled by colour alone. Status and severity carry an icon or word as well as
  colour.
- Every colour, size, corner and shadow comes from a token variable. See
  `references/design-tokens.md`.

### 3. Show and iterate

1. Run the pre-show list in `references/prototype-craft.md` and fix failures first.
2. Optionally, when a headless browser is available, run the scripted walkthrough described there.
   It catches breakage; it never decides anything. Only the user's look and choice decide.
3. Open the file with the platform's default opener. If that fails, give the path.
4. Tell the user what to try: the keys, the states, the options, and the question.
5. Iterate the same file. No versioned copies; repository history keeps old versions.
6. After the pick, hand the chosen values back to the caller or the named document, link the
   prototype from the section it illustrates, and remove losing options unless the user wants them.

## Anti-patterns

A prototype must not:

- invent layout beyond the spec. What is not under question follows the spec; what is under
  question appears as a named, labelled option;
- grow past the agreed surfaces. Split into a second file instead;
- add a component the spec lacks. Stop, ask, and have it added to the spec first;
- hard-code colours or sizes in component rules;
- assume a mobile-first or touch-first layout when the caller did not pass one;
- let a fixed stage, pixel font or single-focus input into the defaults when nobody asked.

## Coverage pass

On request, or when a calling skill reviews, list every screen in the spec and mark it
*prototyped* (with the file) or *spec-only*. The user confirms the spec-only list. Details are in
`references/prototype-craft.md`.

## Reviewing an existing prototype

Run the same pre-show list, compare against the spec (tokens in sync, screens and states present,
flows matching), report differences with severity written as a word, and ask which side should
change. The spec wins unless the user decides otherwise.

## Files

| File | Read it when |
|---|---|
| `assets/prototype-template.html` | You start any prototype. Copy it to the save folder and edit its settings block first. |
| `references/prototype-craft.md` | You build, show or review a prototype: fidelity, states, focus, modals, input models, scaling, the eye check, the walkthrough, the pre-show list, the coverage pass. |
| `references/design-tokens.md` | You name roles, pick values, extend the schema for a domain, check contrast, or record the tokens in a spec. |
