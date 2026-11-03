# Version tables

Two tables: Godot 3 to 4, and changes inside Godot 4. Rows were checked against the engine's published docs; the notes say where a version number could not be pinned down.

## Godot 3 to 4

Use this table forwards to modernise a model's stale draft, and backwards if step 1 of `SKILL.md` found a Godot 3 project. Do not mix the two: in a Godot 3 project, keep Godot 3 syntax.

| Godot 3 | Godot 4 |
|---|---|
| `KinematicBody2D`, `KinematicBody` | `CharacterBody2D`, `CharacterBody3D` |
| `Spatial` | `Node3D` |
| `Sprite`, `AnimatedSprite` | `Sprite2D`, `AnimatedSprite2D` |
| `Position2D`, `Position3D` | `Marker2D`, `Marker3D` |
| `Particles2D`, `Particles` | `GPUParticles2D`, `GPUParticles3D` |
| `VisualServer` | `RenderingServer` |
| `yield(obj, "signal")` | `await obj.signal` (no function-state object to hold) |
| `connect("sig", self, "_method")` | `sig.connect(_method)`, using a `Callable` |
| `export var`, `onready var` | `@export var`, `@onready var` |
| `setget` | `get:` and `set(value):` blocks on the variable, always called, even inside the class |
| `instance()` | `instantiate()` |
| `File`, `Directory` | `FileAccess`, `DirAccess` (some methods are static) |
| `update()` on a canvas item | `queue_redraw()` |
| `OS` time and date methods | the `Time` singleton |
| `OS.get_screen_size()` and other screen or window methods | `DisplayServer` (`DisplayServer.screen_get_size()`) |
| `get_tree().change_scene(path)` | `get_tree().change_scene_to_file(path)` |
| a `Tween` node | `create_tween()` on a node or the tree |
| `Array.empty()`, `invert()`, `remove()` | `is_empty()`, `reverse()`, `remove_at()` |
| `Control.get_stylebox()` | `get_theme_stylebox()` |

The editor's upgrade tool (`--convert-3to4`, described in the engine's migration guide) renames many of these automatically; it does not catch every case, so search the result. The migration guide lists the full set of renamed classes and methods; read it for anything not in this table.

## Changes within Godot 4

**Trust the version in `project.godot` (or `godot --version`) over this table.** Apply a row only when the project's minor version is at or past it.

| Version | Change | What to do |
|---|---|---|
| 4.4 | `@export_file` stores a `uid://` reference, not a `res://` path, when a value is assigned from the inspector | Expect a mix of `uid://` and `res://` in exported file arrays; do not parse them as plain paths |
| 4.5 | `duplicate(true)` copies only the sub-resources internal to that file; `duplicate_deep()` is new | `duplicate_deep(Resource.DEEP_DUPLICATE_ALL)` for the old full copy |
| 4.5 | `@export_file_path` keeps the raw `res://` path | Use it where code needs a path string |
| 4.6 | Scene files store a unique id per node and no longer write `load_steps` | Do not copy a node block with its id; expect diffs on the first save of an older scene |
| 4.6 | CSV translation files accept plural forms (a `?plural` column) | PO is no longer needed just for plurals; call `tr_n()` |
| 4.7 | New projects default to stretch mode `canvas_items` and aspect `expand` | Read the project's setting; never assume |
| 4.7 | Mouse and keyboard events use `InputEvent.DEVICE_ID_MOUSE` / `DEVICE_ID_KEYBOARD`, not device 0 | Filter by event type or the constants |
| 4.7 | A method that overrides one with a declared return type now takes on that type, so a body without a `return` statement is an error | End the body with a `return` of a fitting value (for example `return null`) |

Features whose version this pass could not pin down. They exist in current docs; check the project's engine version before relying on them:

- `TileMap` is deprecated in favour of `TileMapLayer` nodes, one per layer. Use `TileMapLayer` for new work when the project's version has it.
- Sidecar `.uid` files are generated beside scripts, shaders and other resources, and hold the file's unique id. Where the project has them, commit them and never delete them.
- Screen-reader support through AccessKit.
- Mouse and touch focus is not drawn while keyboard and gamepad focus is. Whether an engine release tracks the two separately is not confirmed here.
- Automatic translation of Control text through `auto_translate_mode`.
