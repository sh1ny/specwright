# Code structure, tests and export

Check every API here against the project's engine version before using it.

## Signals

- Declare typed signals: `signal health_changed(new_value: int)`. Connect with `health_changed.connect(_on_health_changed)`. Never use the Godot 3 form that passes the target object and a method name as strings.
- Connect in `_ready`, not `_init` or `_enter_tree`, where the other nodes may not exist yet.
- Call down to children; signal up to parents. Siblings talk through their parent, or by signal, not by path.
- A freed node is gone: nodes are freed explicitly (`queue_free()`), never garbage collected, and a connection does not keep one alive. If you connect a lambda that captures variables, or connect to a long-lived emitter, disconnect on exit anyway so a stale callback cannot fire.

## Autoloads

Use an autoload only for a true app-wide service: settings, save, audio, scene switching. Do not use one to pass references around. A growing autoload is a smell. Autoload fields also survive a scene restart, which is the first place leaked state shows up (`automated-checks.md`).

## Reaching nodes

- `@onready var hp_bar: ProgressBar = %HpBar` uses a scene-unique name and only works inside the owning scene. Or use a relative `$Child` path.
- No `get_node("/root/...")` lookups for scene nodes.
- Prefer `uid://` references to path strings in `preload` and `load`, so moving a file does not break them. Take the uid from the file's `.uid` or existing references (`data-and-saves.md`).

## Naming

From the engine's style guide: files and folders `snake_case`; `class_name` and node names `PascalCase`; functions and variables `snake_case`; constants and enum values `CONSTANT_CASE`; signals in the past tense (`door_opened`, `score_changed`); a leading `_` for private members and virtual methods. Use static typing throughout.

## Lambdas

A lambda captures local variables by value when it is created, so assigning to a captured local inside the lambda does not change the outer one, and the lambda does not see later outer changes. To share mutable state, capture an Array or Dictionary and change its contents.

## Lifecycle pitfalls

- `_enter_tree` runs parent first. `_ready` runs children first, then the parent, once all have entered the tree. Do not read a child's state from the parent's `_enter_tree`.
- Do not put `@export` and `@onready` on one variable: the onready assignment runs later and overwrites the exported value (the engine warns, and treats it as an error by default).
- If the signal you `await` is never emitted, the code after it never runs and the caller waits forever. When that is possible, also wait on a timer (`get_tree().create_timer(2.0).timeout`) and continue with whichever comes first.
- Once an input event is consumed, call `get_viewport().set_input_as_handled()` so nodes further up do not act on it too.
- `_process` and `_physics_process` run by `process_priority` (lower first), then tree order. Set the priority when order matters; do not reshuffle nodes.
- Loading a big scene or resource during play stalls the frame. Use `ResourceLoader.load_threaded_request(path)` and poll `load_threaded_get_status(path)` from `_process` over several frames, not in a loop.

## Tests

- Use the runner the project already has: GUT (`addons/gut/`) or GdUnit4 (`addons/gdUnit4/`). Do not add a second one. Do not add one without asking.
- Read the addon's own command-line docs for its flags. Both run from the command line with the engine, after the import step and under a timeout (`evidence-runs.md`).
- GUT's command-line script is `addons/gut/gut_cmdln.gd`; its exit status is 0 when all tests pass and 1 when any fails. GdUnit4 ships `GdUnitCmdTool.gd` and a `runtest` script; its codes are 0 for success, 100 for failures and 101 for warnings. It may refuse to run headless unless its documented headless flag is passed; read its docs for the name.
- Treat "no tests found" or a zero test count as a failure, whatever the exit code.
- What to test first: pure rules, data loading and save round trips; then a few scene tests. Check outcomes (state, signals), not pixels.
- Input in tests: `Input.parse_input_event()` with an `InputEventAction` (set `action` and `pressed`) or a key event, which reaches `_input()` and `_unhandled_input()`. `Input.action_press("jump")` changes only the polled state (`is_action_pressed` and friends) and causes no `_input()` calls, so use it only for code that polls. After sending input, `await get_tree().process_frame` (or `physics_frame` for physics code) before asserting; then release. Reset input between tests so one test cannot leak a held key into the next.
- From 4.7, mouse and keyboard events carry `InputEvent.DEVICE_ID_MOUSE` / `DEVICE_ID_KEYBOARD` rather than device 0. Test helpers that build events or filter by device should use those constants or the event type.
- Main-scene smoke test: launch the main scene headless for N frames and fail on any error line. It is the cheapest `[evidence]` log and a good first CI job (`evidence-runs.md`).

## Export (low priority)

- Commit `export_presets.cfg`, and keep secrets out of it.
- Install export templates that match the exact engine version.
- Add a CI job once the first playable exists, so platform problems appear early: `godot --headless --export-release "<preset>" <path>`. The binary must be an editor binary, with templates installed or a custom template set in the preset. A relative output path is relative to the folder holding `project.godot`, not the shell's directory.
- Confirm the debug hooks in `automated-checks.md` do nothing in that build, even when it is launched with the opt-in argument.
