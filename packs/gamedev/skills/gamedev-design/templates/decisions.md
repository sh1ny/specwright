# Design decisions

Append-only log, newest last, one line per decision. Open questions stay in the GDD, not here.

Line format:

`- YYYY-MM-DD <area>: <decision> (why: <reason>; affects: <doc>#<section>)`

Tuning-only lines use the area `tuning` and let `affects` name the data, not a GDD section. Playtest verdicts are appended here by `gamedev-playtest` in the same format.

Examples with invented content:

- 2026-03-02 pillars: tension over power; a lantern that never runs dry is out (why: the pillar must be able to veto a feature; affects: gdd.md#Core Fantasy and Pillars)
- 2026-03-09 tuning: lantern burn rate is raised, intent is that a full flask lasts about two rooms (why: runs felt safe; affects: data/lantern.json)
- 2026-03-15 narrative-weight: story stays light, carried by found notes (why: the loop must stand alone; affects: gdd.md#Narrative Weight)

Delete these examples when the first real line is added.
