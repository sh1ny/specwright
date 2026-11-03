# UX review

Use this when the user asks you to review `ux.md`, a prototype, or a captured in-game screen. You report; you change only what the user approves. You do not take over Specwright's review or verification; this is a domain check of the interface.

## Severity

Write severity as a word in the report, never by colour alone.

| Severity | Meaning |
|---|---|
| blocking | A builder would have to guess, or a player is locked out |
| major | A flow, a state or an audit row is missing |
| minor | Naming, links, polish |

## Checklist

Grouped by what a builder trips over first.

### 1. Can it be built?

- Play context is complete: platform, distance, reference resolution, devices.
- Every screen has an entry, an arrival state, a first focus, a back behaviour and exits.
- Behaviour rows and look rows match by component name.
- Every element has an owner, an update event and a missing-data state, and no screen writes game state.
- Building blocks are defined once and referenced.

### 2. Does it hold together?

- Every need and every screen reach each other (no orphan need, no unreachable screen).
- Key flows have failure paths.
- The HUD-by-context table has a default rule.
- Every hidden element has a replacement or a recorded "accepted by the user".
- The notification queue exists, and critical messages bypass it.
- Confirmation effort matches the stakes.
- Tokens are defined, no stray hex values, and game roles map onto generic roles.

### 3. Can every player use it?

- Floor items are met or deferred by a decision.
- The three audit tables are filled.
- Nothing is carried by colour alone.
- Contrast is 4.5:1 for text and 3:1 for large text and key shapes, over real gameplay backgrounds.
- Readability and flash minimums are present and sourced.
- The shrink check passed.
- The HUD stays still under shake.
- Prompts follow bindings, resist flicker and carry labels.
- Per-device completeness holds.
- Options are available before play, and there is one volume per audio role.

### 4. Is it learnable and findable?

- A teaching row exists per core verb.
- The hint stance and the wayfinding stance are recorded.
- Usable things look usable, and nothing looks usable that is not.

### 5. Is it seen?

- Mock coverage is done: each screen is marked prototyped (with link) or spec-only, and the user confirmed the spec-only list.
- The concern scan is answered.

### 6. Is it honest?

- Numbers are labelled as starting guesses with sources.
- Unconfirmed items are marked in place and listed under open questions.
- Findings are classified.
- The document holds decisions, not session history.

## Classifying each finding

Every finding carries two tags.

- Kind: *usability* (the player cannot do what they mean to) or *engagement* (they can, but are not drawn in).
- Friction, if any: *accidental* (fix it in the UX) or *intended* (never softened by a UX change; if the user questions it, hand it to `gamedev-design`).

## Mock coverage

Walk the screen map. Mark each screen *prototyped* with a link, or *spec-only*. Present the spec-only list to the user for confirmation and record it in the map. Flag if every screen is prototyped (probably waste) or none is, with nothing recorded.

## Report shape

```
UX review: <document or screen>, <date>

Summary: <two or three lines: what is solid, what is risky>

Findings
1. [blocking] <short title>
   Where: <section or screen>
   Kind: usability | engagement      Friction: accidental | intended | none
   What: <what is wrong, with the evidence>
   Suggested change: <one line, for the user to approve>
2. [major] ...

Open questions for the user
- <question>

Not checked
- <anything you could not check, and why>
```

Order findings by severity, then by checklist group. Keep the suggested change small and specific. Do not edit the document until the user says which suggestions to apply, and log approved decisions in the decision log if one exists.
