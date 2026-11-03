# Design tokens

Visual identity is a set of named roles first and values second. This skill owns the schema below
and its CSS mapping. A domain skill extends it with its own roles but does not change the base.

## Where tokens live

- In the spec (or the document the caller names): a block of YAML, roles with values.
- In the prototype: CSS custom properties on `:root`, one per role, with the names below.
- The two are kept in sync. A name that differs between them is a defect.

Pick the roles first. Then give each option its own values. Component rules in CSS reference
variables only; a literal colour, size, corner radius or shadow inside a component rule is a defect.
The one exception is the control bar, which is tooling and carries its own `--bar-*` variables.

## Schema

| Group | Roles | CSS custom property |
|---|---|---|
| color | `canvas`, `surface`, `surface-raised`, `ink`, `ink-subtle`, `line`, `accent`, `on-accent`, `focus`, `positive`, `warning`, `negative`, `scrim` | `--color-<role>` |
| type | `display`, `heading`, `body`, `label`, `numeric`; each has family, size, weight, line height | `--font-<role>`, `--size-<role>`, `--weight-<role>`, `--leading-<role>` |
| space | steps `0` to `6`; `edge` (safe margin); `gap` | `--space-<step>`, `--space-edge`, `--space-gap` |
| shape | `corner-none`, `corner-small`, `corner-large`, `corner-round`, `stroke-thin`, `stroke-thick` | `--shape-<role>` |
| depth | `flat`, `raised`, `overlay`, `modal`; each is a shadow or tone plus a layer order | `--depth-<role>`, `--layer-<role>` |
| motion | `quick`, `standard`, `slow`, `ease` | `--motion-<role>` |

Role meanings in one line each:

- `canvas` is the page behind everything; `surface` holds content; `surface-raised` sits above it.
- `ink` is body text; `ink-subtle` is secondary text. `line` is borders and dividers.
- `accent` marks the primary action; `on-accent` is text or icons placed on it.
- `focus` is the focus marker. `positive`, `warning` and `negative` are statuses.
- `scrim` dims what lies behind a modal.
- `edge` is the safe margin around a screen; `gap` is the default spacing between siblings.

## Rules

1. **Names are kebab-case.** Group, then role: `color.surface-raised`.
2. **A token may refer to another** with `$<group>.<role>`, for example `$color.accent`. The CSS
   mapping turns a reference into `var(--color-accent)`.
3. **Component visuals map component and state to tokens**, so the spec can say what a control looks
   like without a stylesheet:
   ```yaml
   button:
     default.fill: $color.surface
     default.outline: $color.line
     focused.outline: $color.focus
     pressed.fill: $color.accent
   ```
4. **Domains add roles** as `<group>.<domain>-<role>`, mapped to `--<group>-<domain>-<role>`. A game
   skill might add `color.game-health`, which becomes `--color-game-health`. Each domain role names a
   generic fallback (`color.game-health` falls back to `$color.negative`), so a prototype with no
   domain support still renders.
5. **Do not rename or remove base roles** to suit one domain. Add instead.
6. **Figures with a source.** Contrast ratios are WCAG's. Any other figure (a spacing step, a
   duration, a size) is a starting value; record where it came from or mark it as a proposal.

## Mapping example

Spec side:

```yaml
color:
  canvas: "#f4f5f7"
  ink: "#1b1f24"
  accent: "#1d4ed8"
  on-accent: "#ffffff"
  focus: "#b45309"
space:
  edge: 1.5rem
  gap: $space.4
shape:
  corner-small: 0.25rem
```

Prototype side:

```css
:root {
  --color-canvas: #f4f5f7;
  --color-ink: #1b1f24;
  --color-accent: #1d4ed8;
  --color-on-accent: #ffffff;
  --color-focus: #b45309;
  --space-edge: 1.5rem;
  --space-gap: var(--space-4);
  --shape-corner-small: 0.25rem;
}
:root[data-option="b"] { --shape-corner-small: 0; }
```

The template defines every base role, so start from its `:root` block and change values, not names.

## Contrast checks

- Check every text role against the background it actually sits on: `ink` and `ink-subtle` on
  `canvas`, `surface` and `surface-raised`; `on-accent` on `accent`; status colours on `surface`.
- Body text and small text: at least 4.5:1. Large text (about 24px, or 19px bold, and up) and key
  shapes such as the focus marker, strokes that separate regions, and icons that carry meaning: at
  least 3:1. These are WCAG figures.
- Compute the ratio from relative luminance rather than judging by eye. Record the pairs checked and
  their ratios next to the tokens.
- Colour never carries status alone: pair it with an icon, a word or a shape.
- Check each option separately; a darker option can fail where the light one passes.

## Depth and shape (lower priority, supported)

Layers, shadows and scrims, and corners and strokes, are part of identity. Record them as
tokens so options can differ in personality: flat and outlined versus soft and raised, square versus
rounded. `--layer-*` values order the stacking (flat, raised, overlay, modal); modals sit above
overlays. A depth token may be a shadow or a tone change; when shadows are removed, make sure
something else still separates the layers.

## Cultural notes

When the audience is wide, flag colours, symbols and gestures whose meaning varies by region (for
example a colour read as celebratory in one place and mournful in another, or a hand gesture that is
friendly in one place and rude in another). Put the flag in the notes beside the token or component,
and ask the user to confirm; do not decide on their behalf.

## Intake of user references (lower priority)

When the user brings reference images, products or styles:

1. Summarise each as what to take (for example "tight spacing, strong headings") and what to avoid
   ("heavy drop shadows").
2. Translate the take-aways into token values and option registers.
3. Never paste a reference's art, logos or text into a prototype. Describe it in words and build
   original shapes.

## Recording the result

After the user picks an option, write the chosen token values into the document the caller or the
project names, using the schema above, plus the contrast pairs you checked. If no document is named,
show the tokens in the prototype and ask where to record them. Do not create a new document yourself.
