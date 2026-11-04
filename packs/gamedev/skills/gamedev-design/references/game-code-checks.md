# Game code checks

A checklist for design review, when a design implies one of these areas, and for implementers reviewing game code. It is guidance, not a script: apply each item by reading the code and the measurements, and report what you could and could not assess. A check whose input is missing is "not assessed", never pass.

For each item: what to check, why, and a neutral way to measure it. All numbers are starting hypotheses.

## Frame budget

- **Check.** The time per frame at the project's target rate, split across systems. At 60 Hz the whole frame is about 16.6 ms; at 30 Hz about 33.3 ms. Give each system a share (simulation, rendering, audio, UI) as a hypothesis and keep headroom.
- **Why.** A game that exceeds its budget drops frames, and the player feels it before they can name it.
- **Measure.** On the minimum target device, not the development machine. Record both the average frame time and the worst frames over a representative stretch of play, including the heaviest scene the design allows.
- **When it applies.** A design with many entities, heavy simulation or large effects, or any change to a per-frame or hot path.

## Allocations in per-frame loops

- **Check.** Whether code that runs every frame creates garbage or churns the heap: new objects, strings, lists, closures.
- **Why.** Collection or allocation pauses show up as spikes, not as a higher average.
- **Measure.** Count allocations per frame over a stretch of play, and watch the worst frame, not the mean. Prefer pooling or pre-allocating what is reused.

## Input latency

- **Check.** The time from the input event to a visible response, and the point in the frame where input is read.
- **Why.** Late or early-read input adds felt delay. Buffered inputs and their windows are design numbers, not code details: state each in the GDD as a hypothesis and keep it in data.
- **Measure.** Count frames between the input and the first visible change at a stated tick rate (for example 3 frames at 60 Hz is 50 ms). Read input as late as is useful in the frame.

## Fixed timestep and determinism

- **Check.** That simulation steps at a fixed rate, apart from rendering. No logic that must repeat is scaled by variable frame time. Randomness is seeded. Where determinism is required, watch float behaviour and the order in which things update.
- **Why.** Variable steps make results depend on the machine. Replays, rollback, lockstep and fair tests all need the same result from the same input.
- **Measure.** Run the same input sequence twice, and on two machines when cross-machine matters, and compare the final state.

## Physics in the right step

- **Check.** Movement and forces run in the physics step. Visuals are interpolated in the render step. No mixing that causes jitter or rate-dependent results.
- **Why.** A character that moves differently at 30 Hz and 144 Hz is a bug. Visible jitter points to the wrong step.
- **Measure.** Run the same movement at two frame rates and compare distance and timing. Look for stutter on slow-moving objects.

## Save compatibility

- **Check.** Every save carries a version. Each change to the format ships a migration and a test that loads an old save. Unknown fields are never silently dropped.
- **Why.** Players lose progress when a new build cannot read their old save, and the loss cannot be undone.
- **Measure.** A test that loads a save from each previous version and checks that the loaded state is the same as intended.
- **When it applies.** Any change to what persists. See `references/game-architecture.md` for the questions.

## Idle does not win

- **Check.** When a fail state is added or changed, an automated check proves that doing nothing does not win.
- **Why.** A fail state that only triggers on action can be passed by waiting, and a changed one can quietly stop failing anyone.
- **Measure.** A test that runs the scenario with no input for the whole time and asserts a failed outcome (or, where the design allows idling, the intended one).
- **When it applies.** Every fail-state change flagged during triage, and every encounter sheet's fail state.

## Debug and test hooks stay out of shipped builds

- **Check.** Cheats, debug overlays, test switches and skip-ahead tools are absent or disabled in a shipped build.
- **Why.** A hook left in can be found and used, and can change save data or balance.
- **Measure.** Build the release configuration and search for the hooks by name; run its start-up path and confirm none is reachable.
