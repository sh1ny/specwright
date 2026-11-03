---
name: godot-engine
description: "Godot 4 engine practice for projects with project.godot. Use for the in-engine [evidence] check (a headless run gives a log; a screenshot needs a windowed run or --write-movie), safe headless runs (import first, timeout, scan for errors), state dumps and invariant checks, hand-editing .tscn/.tres, tunables as custom Resources, safe saves, Theme and Control screens, focus, pixel-art scaling, localization, signals, GUT or GdUnit4 in CI, Godot 3 versus 4.x API differences."
---

# Godot engine practice

Models remember a lot of Godot 3, and even Godot 4 moved under them between minor releases. This skill carries the Godot 4 habits a Specwright project needs: proving that a change runs in the engine, keeping tunables in data, editing scene and resource files without corrupting them, turning a UI design into Themes and Control scenes, and writing code and tests that stay maintainable.

It stands alone. A Godot tool that is not a game is a valid user, so nothing here may depend on the game-design skills.

## When to use it

- Any work in a repository with a `project.godot` (at the root or nested).
- Writing the `[evidence]` task, or producing its file: "run the game and check", "screenshot the menu".
- A fresh clone whose first headless run fails; "which Godot version or renderer is this".
- Tunables, balance tables, item or enemy data, "make this tweakable".
- Editing a `.tscn` or `.tres` by hand; save games and settings files.
- Building a screen, menu or HUD from a UX spec or an HTML prototype; gamepad menu navigation.
- Blurry or uneven pixel art; window scaling; translations, `tr()`, text that overflows.
- Signals, autoloads, node paths, `_ready` order, `await`; GUT or GdUnit4 tests; CI; input in tests; scripted input runs; frame time.
- Godot 3 code, or code for an older 4.x, in the project or in your own draft.
- Export presets and builds (low priority).

## Boundaries

- This skill owns the engine side only. If the `gamedev` pack is installed, its skills (`gamedev-design`, `gamedev-ux`, `gamedev-narrative`, `gamedev-playtest`) and `ui-prototyping-html` own design, UX, narrative and the human playtest. Use them when present; never require them.
- Feel, timing and creative quality are judged by the user. A screenshot, a log or an invariant never proves them, and you never score creative work.
- You never write or tick a `[user]` task. You only make sure the evidence task comes before the user's playtest task.
- Specwright still owns commits, reviews, verification and task ticking. This skill adds engine knowledge and drafts; the orchestrating flow does the rest.
- You do not install plugins, MCP servers, test addons or export templates on your own. Propose them; the user decides.
- A check that could not run reports "not assessed" with the reason. It never reports pass.

## Step 1: read the project

Do this before anything else, every time.

1. Read `project.godot`. Find the engine version and the renderer.
   - Version: `[application]` `config/features` usually lists a version such as `"4.3"` plus a renderer label. Treat it as a hint and confirm with the binary (`godot --version`). A very old looking project file, or GDScript using `KinematicBody2D`, `yield` or `export var`, means Godot 3.
   - Renderer: `[rendering]` `renderer/rendering_method` is `forward_plus`, `mobile` or `gl_compatibility`; when it is absent, the default (Forward+) applies. Per-platform overrides (for example a `.mobile` suffixed key) can differ.
   - Also note: `run/main_scene`, `[autoload]`, `[input]` actions, `display/window/stretch/*`, localization files, and which test addon sits under `addons/` (`gut` or `gdUnit4`).
2. **Trust the project's version over any table in this skill.** Apply a version-specific row only when the project's minor version is at or past it. See `references/version-changes.md`.
3. If it is a Godot 3 project, say so. Do not apply Godot 4 advice blindly; read the Godot 3 to 4 table backwards.
4. Find the binary: the project's own docs, the `GODOT` or `GODOT_BIN` environment variable, or `godot` on the PATH. If none exists, ask. Never guess a download.
5. To search GDScript, glob for `*.gd`; the search tool may have no GDScript file type.

## Step 2: run the engine safely

These rules apply to every run in this skill. The full commands are in `references/evidence-runs.md`.

1. **Import first on a fresh clone.** A new checkout has no `.godot/` cache, so class names and imported assets are missing. Run `godot --headless --path . --import` once before any other headless run. `--import` opens the editor, waits for resources to import and quits. Repeat it after adding assets or hand-editing scene or resource files.
2. **Always run under a timeout** (the shell's `timeout`, or the CI step's limit). A run that hits trouble can wait forever.
3. **Do not trust the exit code.** Capture the output and scan it for `ERROR`, `SCRIPT ERROR`, `Parse Error` and `Failed to load`. Any hit fails the run.
4. **Cheapest check: parse only.** `godot --headless --path . --check-only --script res://file.gd` parses a script and quits. A script that leans on an autoload or other project classes may report a false error here; treat that as "not assessed" and fall back to a short headless run.
5. **Leave out `-d`.** It attaches the local command-line debugger, an interactive tool. Pass it only if a test runner's own docs say to.
6. **Missing inputs mean not assessed:** no binary, no display, no tests found.

## Step 3: in-engine evidence

A Specwright `[evidence]` task names one file in the change's `evidence/` folder (`<what>.log` or `<what>.png`). It is ticked only when that file is non-empty and committed with the task. Never fake the file or reuse an old one; if no route works, leave the task unticked and say why.

**The task names the state.** Write which screen or game state the evidence shows and how the run reaches it: a scene argument, a debug flag, or a scripted input run. "Screenshot of the game" is too vague; "the pause menu after pressing Escape in level 1" works.

Pick the evidence by the kind of change:

| Change | Evidence |
|---|---|
| Logic | A unit-test run log |
| UI or layout | A still screenshot |
| Data or content | A smoke-run log that loads it |
| Feel or timing | The user's playtest (`[user]` task). The evidence task proves only that the build runs and reaches the state |

**A `--headless` run renders nothing, so it can never produce a screenshot.** It gives a log. A picture needs a real display: a windowed or editor run, or Movie Maker (`--write-movie`). In a CI runner without a display on Linux, use a virtual display, or say the screenshot was not assessed.

Routes, cheapest first:

1. **Log.** `timeout 60 godot --headless --path <project> --quit-after <N> > out.log 2>&1` runs the main scene with no window. Pass when the error scan is clean and the expected prints or state-dump lines appear.
2. **Screenshot through Movie Maker.** Write frames, keep the last, rename it to the task's path, delete the rest and the `.wav`. Details in `references/evidence-runs.md`.
3. **In-script capture.** A debug-only helper that waits for `RenderingServer.frame_post_draw` and saves the viewport image. Same display need.
4. **A configured Godot MCP server,** when the project has one: its run, screenshot and log tools may be used. Never require one, and never name a paid product. Many projects have none.

After capturing a picture, open the PNG and compare it with the task's criteria, then report what you see. A still shows layout and presence only.

## Pack lines this skill backs

- **Evidence names state:** see Step 3 and `references/evidence-runs.md`.
- **Idle doesn't win:** a change that adds or alters a fail or win state gets an automated check that doing nothing does not win. Never leave it as a manual step or a `[user]` task. See `references/automated-checks.md`.
- **Tool-neutral evidence:** a headless run gives a log; a screenshot needs a windowed or editor run, or `--write-movie`; an MCP server is an optional route.

## Short rules for the rest

**Automated checks** (`references/automated-checks.md`). A debug-only state dump (one JSON line per step, fixed prefix) turns "the game ran" into "the game reached this state". Scripted input runs use a fixed frame rate and seed. Debug hooks switch on only in a debug build (`OS.is_debug_build()`) that also carries an explicit opt-in, a feature tag or a user argument after `--`; a release export never enables them, whatever its arguments. Compare images only for still screens. Measure frame time with real elapsed time, not `delta`.

**Hand-editing `.tscn` and `.tres`** (`references/data-and-saves.md`). Prefer the editor or a `ResourceSaver` script. Never invent a `uid://`; copy it or leave the attribute out. Keep ids unique, declare resources before use, keep the header line, and never copy a node block together with its unique node id (4.6+). Re-import and load the file once afterwards.

**Tunables** (`references/data-and-saves.md`). Put them in custom `Resource` classes saved as text `.tres`, in stated units. A loaded Resource is shared by everyone who loads that path: copy before changing per-instance state, and pick the duplicate call by what the code mutates.

**Saves never use `.tres` or `.res`.** A loaded resource can carry a script, so a shared save file becomes code execution. Use JSON or `ConfigFile` under `user://`, with a `version` field.

**UI** (`references/ui-and-text.md`). Tokens go to a `Theme`, each screen is its own `Control` scene, overlays sit on a `CanvasLayer`. Test the whole menu with only a gamepad. Read the project's stretch settings before touching pixel-art scaling. Text lives under stable keys, translated with `tr()`.

**Code and tests** (`references/code-and-tests.md`). Typed signals connected in `_ready`; autoloads only for app-wide services; scene-unique names or relative paths rather than `/root/...`. Use the test runner the project already has, never add a second, and treat "no tests found" as a failure.

**Export** (low priority). Commit `export_presets.cfg`, match the templates to the exact engine version, and add a CI export job once a first playable exists. Details in `references/code-and-tests.md`.

## Where to read next

| File | Read it when |
|---|---|
| `references/evidence-runs.md` | You run the engine, write an `[evidence]` task, capture a screenshot or log, or set up CI with no display |
| `references/automated-checks.md` | You add a state dump, scripted input run, invariant, visual baseline or frame-time sample |
| `references/data-and-saves.md` | You edit scene or resource text, add tunables, or touch save and settings files |
| `references/ui-and-text.md` | You build a Theme or Control screen, handle focus, scale pixel art, or localize |
| `references/code-and-tests.md` | You write signals, autoloads or node access, pick naming, run GUT or GdUnit4, simulate input, or set up export |
| `references/version-changes.md` | The code looks like Godot 3, or a feature depends on the project's 4.x minor version |

Check every API against the project's engine version before suggesting it.
