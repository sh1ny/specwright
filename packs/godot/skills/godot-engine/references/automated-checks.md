# Automated checks beyond a smoke run

A smoke run says the build starts. These checks say it reached a state, behaved the same twice, and did not win by doing nothing. All of them run under the rules in `evidence-runs.md` (import, timeout, error scan).

## Gate every debug hook

State dumps, scene jumps and scripted input exist for the agent and CI. They must be inert in a shipped build, whatever arguments or tags that build is given. Two conditions must both hold before a hook switches on:

1. The build is a debug build: `OS.is_debug_build()` returns true. A release export fails this test and stays off, full stop.
2. The run also opts in explicitly, by either of:
   - a custom feature tag: `OS.has_feature("qa_hooks")` (tag names are case-sensitive and set in the run or export configuration);
   - a user argument after the double dash: `"--qa-run" in OS.get_cmdline_user_args()`. Arguments before `--` belong to the engine; those after it are reserved for the project.

```gdscript
var qa_enabled: bool = OS.is_debug_build() and (
    OS.has_feature("qa_hooks") or "--qa-run" in OS.get_cmdline_user_args())
```

Neither the tag nor the argument is enough alone. Put the gate in one place (a single debug node or autoload), and have everything else ask it. Run the export job's build once, with the opt-in argument supplied, and confirm the hooks still do nothing there.

## State dump

A debug-only function that prints the part of the state the change touches, as one JSON line per step, behind a fixed prefix that can be grepped.

```gdscript
func dump_state(step: int) -> void:
    if not _qa_enabled:
        return
    var state := {
        "step": step,
        "screen": get_tree().current_scene.name,
        "player_pos": [player.position.x, player.position.y],
        "health": player.health,
        "score": score,
    }
    print("QA_STATE ", JSON.stringify(state))
```

Save the matching lines into the evidence log (`grep QA_STATE out.log > evidence.log`, with the command line and engine version added at the top). This turns "the game ran" into "the game reached this state". Pick fields the change actually touches; a dump of everything drowns the signal.

## Scripted input runs

A scripted run is a list of steps, each `(actions, frames)`: hold those actions for that many physics frames, then dump the state.

```gdscript
const STEPS := [
    {"actions": ["move_right"], "frames": 30},
    {"actions": ["jump"], "frames": 12},
    {"actions": [], "frames": 60},
]

func run_script() -> void:
    for i in STEPS.size():
        for a in STEPS[i].actions:
            Input.action_press(a)
        for _f in STEPS[i].frames:
            await get_tree().physics_frame
        for a in STEPS[i].actions:
            Input.action_release(a)
        dump_state(i)
```

Rules:

- Start the engine with a fixed frame rate (`--fixed-fps <N>`) and seed the random generators at the start of the run (`seed(1234)` and any `RandomNumberGenerator.seed` you own), so the same input produces a comparable log.
- Stop at the first new error line and report the step that was running.
- Keep the step list in a data file or a constant next to the check, not inside the engine code that is under test.
- Keep a short fixed list of edge-case seeds. Log the seed with every report so a failure can be replayed.

## Restart cleanliness

Run the same scripted steps several times, either by restarting the scene or by starting the engine again, and compare the state dumps for the same step. A difference means leaked state: autoload fields, static variables, signals left connected, or a shared Resource that was mutated (see `data-and-saves.md`).

## Invariants

For a change that adds or alters a fail state or a win state, add an automated check:

- a run with no input does not win, and does not score;
- a scripted active run can win;
- required labels and HUD elements are present on the screen;
- muting then unmuting restores the volume.

Thresholds come from the tuning data the game loads, not from numbers pasted into the test. This is a code check, never a manual step and never a `[user]` task.

## Visual regression, still screens only

Compare menus, a HUD in a paused state, or other static screens against a committed baseline image. Never compare animated or physics-driven frames: they differ run to run for reasons that are not defects. A baseline changes only as a deliberate, reviewed change, never to make a test pass. Capturing the images follows `evidence-runs.md`.

## Frame-time sampling

Sample over a fixed number of frames N and record the average and the worst frame, plus a description of the machine.

- Measure with real elapsed time: `Time.get_ticks_usec()` read once per frame and differenced. Do not use `delta` for this: under `--fixed-fps` and in Movie Maker mode `delta` is the same every frame whatever the frame cost.
- `Performance.get_monitor(Performance.TIME_FPS)` counts frames in the last second and updates only once per second; it is a coarse figure.
- `Performance.TIME_PROCESS` is the process step alone, not the whole frame with rendering. Never report it as frame time.
- For render cost, enable per-viewport measurement with `RenderingServer.viewport_set_measure_render_time(viewport_rid, true)`, then read `viewport_get_measured_render_time_cpu()` and `..._gpu()` (milliseconds). They return 0 until measuring is on, and the CPU figure covers rendering work only, not scripts.

Log format, one line per run:

```
QA_PERF machine="<cpu/gpu/os>" frames=600 avg_ms=7.9 worst_ms=19.4 version=<engine version>
```

Frame time from a headless run is meaningless for rendering. Use a windowed run.

## A fixed report shape for evidence logs

Put these at the top of any evidence log: the run command, the engine version, the seed, the steps, then the state dumps, then any errors, then a verdict of `pass`, `fail` or `not assessed`.

## Actions with no way back

A cheap review aid: list the actions that cannot be undone or left (a menu with no cancel, a door that locks behind the player). The agent lists them; a person decides whether each is intended.
