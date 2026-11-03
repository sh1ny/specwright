# Data, scene files and saves

Hand-editing `.tscn` and `.tres`, tunables as custom Resources, and the rule for saves.

## Hand-editing scene and resource text

Prefer the editor, or a script that builds the resource and calls `ResourceSaver.save()`. When a text edit is the right tool:

- **Never invent a `uid://` value.** Copy it from the target's `.uid` file or from an existing reference. If you cannot, leave the `uid` attribute out and let the editor add it.
- **Ids must not collide.** Each `[ext_resource]` and `[sub_resource]` carries an `id`, and `ExtResource("id")` / `SubResource("id")` point at it. The two kinds are looked up separately, so an external and an internal resource may technically share an id, but do not rely on that: keep every id in the file unique, and never reuse one.
- **Declare before use.** An external resource goes at the top of the file. A sub-resource that refers to another sub-resource must come after the one it refers to.
- **Values are data.** Property values hold literals and resource references, not script syntax. Typed arrays keep their type.
- **Keep the header line** (`[gd_scene ... format=3 ...]` or `[gd_resource ...]`) as it is.
- **Node ids, 4.6 and later.** Scene files store a unique id per node and no longer write `load_steps`. Never copy a node block, with its unique id, into another node. Opening and saving in 4.6 a scene last saved in 4.5 produces large diffs in version control; they are expected and not a sign of damage. Saving the whole project's files in the new format once keeps later diffs small.
- **A scene stores only values that differ from the default.** Do not add every property to a node block; do not read a missing property as "unset".
- **Leave tile-map cell data alone.** The packed cell arrays are the editor's job.
- **Scripts and shaders have `.uid` files beside them.** Do not delete them or write them by hand. Commit them with the file they describe once the project's version creates them; the check is whether the project already tracks them.
- **Prove it after editing.** Run the import (`evidence-runs.md`), then load the file once, by a headless run that instantiates it or by a test, and scan the output.

## Tunables as custom Resources

A tunable is any number a playtest might change: speeds, costs, damage, spawn rates. Keep them in data, not in code.

```gdscript
class_name EnemyStats
extends Resource

@export var speed: float = 120.0            # pixels per second
@export_range(1, 999) var max_health: int = 10
@export_enum("melee", "ranged") var attack_kind: String = "melee"
@export var drops: Array[ItemStats] = []
```

- Create instances in the editor, or from a script with `ResourceSaver.save()`; load them with `preload` or `load` and read the fields at run time.
- Text `.tres` files diff well and are preferred over binary `.res` in the repository.
- If the class defines `_init()` with parameters, give every parameter a default, or the editor and the loader cannot create it.
- Use `@export_range`, `@export_enum`, typed arrays and nested Resources for tables.
- State units next to the field (pixels, tiles, seconds, or frames at the physics tick), so changing a value after a playtest is a data edit.
- Register data classes with `class_name`; the inspector only supports global classes for exported resource properties.
- Thresholds used by invariant checks come from the same data (`automated-checks.md`).

### A loaded Resource is shared

Everyone who loads the same path gets the same object. Changing a field of one changes it for all. Before mutating per-instance state, copy:

| Call | Result |
|---|---|
| `duplicate()` | Shallow: nested sub-resources stay shared with the original |
| `duplicate(true)` | From 4.5: duplicates only the sub-resources that live inside that same file. In 4.4 it also duplicated external ones |
| `duplicate_deep(Resource.DEEP_DUPLICATE_ALL)` | 4.5 and later: copies every sub-resource |

Pick by what the code will change. On 4.4 or older, use `duplicate(true)` for a full copy.

## Saves and settings: never `.tres` or `.res`

**Do not use `.tres` or `.res` as a player save or mod format, and do not call `ResourceLoader` on files a player supplied.** A loaded resource can embed a script and run it, so a save file shared between players, or edited on disk, becomes code execution.

Use data-only formats:

- JSON through `JSON.stringify()` and `JSON.parse_string()`, with `FileAccess` at a `user://` path; or `ConfigFile` for settings.
- Avoid `bytes_to_var_with_objects` and any API that decodes objects out of data you did not produce: the engine's own docs warn that decoded objects can contain code that runs.

Save rules:

1. Every save has a `version` field.
2. Loading migrates old versions one step at a time and rejects an unknown, newer version with a clear message.
3. Write to a temporary file, then rename it over the real one, so a crash cannot leave a half-written save. Check each `FileAccess` result.
4. Validate types and ranges on load; treat the file as untrusted.
5. Test the round trip: save, load, compare. Add a test per migration step.
