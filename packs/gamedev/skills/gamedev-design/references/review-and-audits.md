# Review and audits

Guidance you apply by reading the documents. There is no script to run and no score. Creative areas get findings and questions, never a mandatory fix.

## Reviewing the GDD

Run it over the GDD, and over `brief.md` if present. Skip checks that do not fit the agreed scope; say which you skipped.

Each finding has:

- a status: pass, fail, warn, n/a, not assessed;
- a severity in words (high, medium, low), never colour alone;
- the GDD section it points at;
- a one-line note.

Show findings in chat, ranked by severity. Write no report file. On request, apply the fixes in place and log them.

### Intent holds together

- The pitch states a core fantasy in one sentence and a few pillars (two to four is a starting hypothesis) in priority order, each able to veto a feature, with tempting anti-pillars named.
- The loop closes at moment, session and long-arc scale, and each step maps to a pillar.
- Every mechanic, progression element and First Playable item traces back to a pillar or a loop step.
- First Playable is the smallest build that tests the riskiest assumption. A list of more than about seven items (a starting hypothesis) gets push-back. The riskiest item is built first.

### Concrete and testable

- Mechanics carry numbers, each marked as a tuning hypothesis kept in data. Edge cases have resolutions.
- Look, Sound and Feel uses words a playtest can judge, with anti-references, commitment profiles and failure textures.
- Platforms and Input names devices and the minimum input set.
- The Accessibility Floor lists concrete commitments, not intentions.
- Vague quantities ("many", "lots") are replaced by counts or ranges.
- No live values and no acceptance criteria sit in the GDD.

### Holism

- No competing progression loops pull the player two ways; there is one player identity.
- The attention budget at the busiest moment is stated and plausible.
- No dominant strategy. Each currency has sources and sinks. Scaling curves do not diverge unchecked.
- Cross-system moment walk (see `references/systems-and-balance.md`): pick three to five moments where several systems fire at once.
- Difficulty: the axes used, which the player can lower, a frustration stance, the cost of a retry.
- The reward ethics check passes, or its findings are listed.

### Scope is honest

- Out of Scope names what is cut and what is deferred. Parked cuts have their one-line reason.
- Nothing from the brief, the init answers or the user's inputs vanished without a cut or a logged change.
- Scope fits the stated team and time, including implied systems.
- Target session length and save spacing agree.

### Genre

- The game type id and any secondary ids exist in `references/genre-guide.md`.
- The pitch's actual content matches the id. Flag a stronger competing id.
- The questions the table marks high-stakes for that genre are answered or listed as Open Questions. An unanswered high-stakes question is a high-severity finding.
- Hybrid tensions are resolved or listed.

### Hygiene

- Terms are used the same way everywhere. Watch for synonym drift and contradictions between sections.
- No template placeholders remain. A section that does not apply says so and why.
- The GDD agrees with the latest lines in `decisions.md`.
- The open-item load is reasonable for the scope, and none blocks the next step unacknowledged.

### Leakage

Engine terms or code identifiers in the GDD freeze a "how" into the "what". The check is a reading, not a pattern search. Look for:

- a type or class name in CamelCase or in code font;
- a function or callback name with parentheses, especially a per-frame update hook;
- a source file path or a file extension;
- an engine's scene, component, prefab or object-tree vocabulary used as design language;
- a named physics body, collider or joint type instead of the behaviour it gives;
- a shader, render-pass or material setting instead of the look it produces;
- a networking library or transport name instead of the latency and fairness promise;
- a serialisation or data-format detail instead of what must persist.

Allowed: target platforms, hard platform constraints and units of measure. The fix is always to restate the player-facing behaviour and move the how to the architecture questions (`references/game-architecture.md`).

## Reconciliation pass

Run it after the GDD is created or substantially changed.

1. Collect the inputs: `brief.md`, the init answers, notes, earlier chats and reference lists the user supplied.
2. Take each item from them and place it in one of three states: present in the GDD, explicitly cut (Out of Scope), or deliberately changed (with a log line).
3. Check mood, tone and feel ideas on purpose. They are the ones most often lost.
4. Show the user anything that fits none of the three states and let them choose.
5. When brief and GDD disagree, the GDD is current. Offer to update the brief or mark it historical. Do not leave two truths.

## Doc drift audit

Run it on request or before a milestone close.

1. Compare the GDD with the build as the user or the repo shows it: playable state, data files, notes the user gives.
2. List each mismatch as one of:
   - stale: the build moved on and the GDD did not;
   - aspirational: the GDD describes something not built yet;
   - contradiction: both exist and disagree.
3. The user decides each one. For stale, update the GDD and log it. For aspirational, keep it, move it to First Playable or Out of Scope, or cut it. For a contradiction, the user picks which side is right.
4. Never change the design to match the build without the user's call.
5. A check whose input is missing (no build, no data) reports "not assessed", never pass.

## Open-item triage before "ready"

1. List every Open Question and every unconfirmed assumption in the GDD.
2. Sort each into: blocks the next planned change; blocks First Playable; can wait.
3. Resolve the blockers one at a time with the user.
4. Leave the rest listed, each with an owner or a trigger ("decide after first playtest").
5. If blockers are many relative to the scope, say plainly that the design is not ready, and why.

Readiness is advice. It is not a mandatory gate and it never labels a design invalid.
