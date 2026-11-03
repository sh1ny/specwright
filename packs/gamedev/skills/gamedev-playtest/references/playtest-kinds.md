# Kinds of playtest

Load this for accessibility, input-device and online playtests, regression replays, balance timing and the milestone retrospective.

## Accessibility playtest

Driven by the accessibility floor the project declared in `ux.md` (owned by `gamedev-ux`; read it, do not restate it). Judge with each setting on, against the same question as the base playtest. Checklist, keeping only what the floor declares:

- remapping works for every action;
- hold versus toggle, where offered;
- subtitles are present, and their size is readable;
- colour-blind safety: nothing important rests on colour alone;
- reduced motion and screen-shake settings are honoured;
- text size settings hold up in menus and HUD;
- one-handed play, where declared.

Record each setting tested in the entry's "what was played" bullet. A gap in the floor itself is a design finding for `gamedev-ux`; a setting that does not work is a bug task.

## Input-device playtest

One session per declared device (keyboard and mouse, gamepad, touch, handheld). For each:

- glyphs match the device in use;
- menus work without a mouse;
- the feel words hold; analogue dead zones and aiming differ between devices;
- the task text names the device, so the entry says which was played.

Separate sessions are the case where several `[user]` tasks are justified.

## Network feel

Online or multiplayer feel is judged under real latency, or simulated delay and packet loss, stated in the entry. A local-only session says nothing about how online play feels, so do not record a feel verdict from one. For multiplayer, run one session per supported player count; a mode that works for two can fail for four.

## Regression line

Every playtest after the first asks one short question about an earlier accepted mechanic ("did the dash still feel right?"). The entry records the answer as yes, no or not checked, where yes means it got worse. After a tuning change, a regression replay runs the same earlier question on the changed build.

## Defer global balance

Economy curves, overall difficulty and progression pacing are balanced once most content exists. Earlier playtests tune locally, one mechanic or one level, and record global concerns as notes. Do not retune the whole game from one early level.

## Larger tests (optional)

For bigger tests, group players into rounds and state in advance what ends a round, for example "three of four players clear the tutorial unaided".

## Milestone retrospective

Run on request, or at a milestone close. Low priority.

1. Read the milestone's entries in `decisions.md`.
2. Summarise: questions asked; verdicts; hypotheses confirmed, partly or refuted; values that moved more than once (unstable tuning); findings still open, by severity and route; feel words that keep failing; regressions seen; low-confidence verdicts still waiting for a fresh player.
3. Suggest the next milestone's playtest focus.
4. Append it as one line with area `retrospective` and indented sub-bullets, in the shared line format. Do not edit earlier lines.

Low-confidence entries are listed, not enforced: they never block the close.
