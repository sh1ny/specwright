# Evidence runs

Commands and conventions for running Godot to prove a change works. Read the run rules first, then pick a route.

`<project>` is the folder holding `project.godot`; `$GODOT` is the binary found in step 1 of `SKILL.md`. Paths below use a POSIX shell; adapt the timeout wrapper in CI.

## Run rules (before any route)

### Import before the first run

A fresh checkout has no `.godot/` cache. Without it, `class_name` lookups and imported assets fail in ways that look like code bugs.

```
timeout 300 "$GODOT" --headless --path <project> --import
```

`--import` starts the editor, waits for resources to import and quits (it implies `--editor` and `--quit`). Run it again after adding assets, after hand-editing `.tscn` or `.tres` files, and after pulling changes that add either. Export commands imply it.

### Timeout

Wrap every run in the shell's `timeout` (or the CI step's time limit). Pick a limit a few times longer than a healthy run needs. A timeout hit is a failed run, not a pass.

### Both checks: exit status and output scan

A run passes only when two things hold: the engine command ended with a successful exit status, and the captured output is clean. Neither alone is enough. A zero exit status does not show the log is clean, and a clean log can come from a run that was cut off.

Capture stdout and stderr, keep the exit status, then scan:

```
timeout 60 "$GODOT" --headless --path <project> --quit-after 120 > out.log 2>&1
status=$?
if [ "$status" -eq 124 ]; then echo "FAIL: timed out"; exit 1; fi
if [ "$status" -ne 0 ]; then echo "FAIL: engine exited with $status"; exit 1; fi
if grep -E "ERROR|SCRIPT ERROR|Parse Error|Failed to load" out.log; then echo "FAIL: errors in log"; exit 1; fi
echo "clean"
```

`timeout` returns 124 when it had to stop the command. Any error hit fails the run. An empty log from a run that should have printed something is also a failure, not a pass. Do not rely on the exit status alone, and do not rely on the scan alone.

`--log-file <path>` writes the engine log to a file instead; scan that file the same way. The scan covers what the engine prints, so a state-dump line you expect (see `automated-checks.md`) must also be present.

### Leave `-d` out

`-d` (`--debug`) attaches the local command-line debugger, which is meant for a person at a terminal. Do not add it to your own commands. A test runner whose docs include it in its sample command is a separate case: follow that runner's docs.

### Parse-only check

```
timeout 60 "$GODOT" --headless --path <project> --check-only --script res://path/to/file.gd
```

`--check-only` parses for errors and quits; it works together with `--script` (`-s`). It is the cheapest syntax check. A script that refers to an autoload or to other project classes can report an error that a real run would not. Treat such a hit as "not assessed" and confirm with a short headless run.

### Not assessed

No binary, no display for a screenshot, no tests found: write "not assessed" and the reason in the evidence file or the report. Never write pass.

## Route 1: log (cheapest)

```
timeout 60 "$GODOT" --headless --path <project> --quit-after 120 > out.log 2>&1
```

- `--headless` means `--display-driver headless --audio-driver Dummy`: no window, no sound.
- `--quit-after <N>` stops after N main-loop iterations (0 disables it). Choose N large enough for the scene to reach the state, with margin.
- Pass when the error scan is clean and the lines you expect appear: your own `print` markers, or state-dump lines.
- To start in the state under test, pass the scene as a positional argument: `"$GODOT" --headless --path <project> res://ui/pause_menu.tscn --quit-after 60`. Or use a debug flag after `--` (see `automated-checks.md`), or a scripted input run.

The evidence file for the task is then `out.log` (or a trimmed version of it) saved as `openspec/changes/<change>/evidence/<what>.log`. Keep the command line and the engine version at the top.

## A headless run cannot take a screenshot

**Rendering is switched off under `--headless`.** A capture there is empty or fails. For a picture, one of these needs a real display: a normal windowed run, an editor run, or Movie Maker. On a Linux CI runner with no display, start the run through a virtual display tool (for example `xvfb-run`) and say so in the report; if that is not available, report the screenshot as not assessed.

## Route 2: screenshot through Movie Maker

```
timeout 120 "$GODOT" --path <project> --write-movie /abs/path/work/shot.png --quit-after 30 res://ui/pause_menu.tscn
```

- The file extension picks the writer: `.png` writes an image sequence plus a WAV, `.avi` and `.ogv` write video.
- `--fixed-fps` is forced by Movie Maker and may be set explicitly (for example `--fixed-fps 60`).
- `--quit-after` sets how many frames are written. Leave a few frames for the scene to settle; the first frames can show an unfinished layout.
- A `.png` target writes one file per frame with an eight-digit, zero-padded number appended to the name, starting at zero: `shot.png` gives `shot00000000.png`, `shot00000001.png`, and so on. The audio goes to `shot.wav` beside them.
- Write into a scratch folder, not into `evidence/`.

Then clean up: keep the last frame, move it to the exact path the task names (`openspec/changes/<change>/evidence/<what>.png`), delete the other frames and the `.wav`. Leftover frames must not end up committed.

Input during a Movie Maker run: it is a normal run, so a scripted input run or a debug flag (see `automated-checks.md`) is how you reach states that need input. That runner sends `InputEventAction` events, so menus and other `_input`-driven code respond to it as well as polling code.

### Frame size

Movie Maker writes frames at the root viewport's size, and `--resolution WxH` changes the window size at start-up. Do not promise a frame size from `--resolution` alone: the stretch settings can decide what the root viewport measures. Read the project's stretch mode (`ui-and-text.md`), then open the PNG and check its real dimensions before describing it.

## Route 3: in-script capture

When Movie Maker does not fit (for example, you want one frame after an exact event), add a debug-only helper, gated as described in `automated-checks.md`:

```gdscript
func capture(path: String) -> void:
    await RenderingServer.frame_post_draw
    get_viewport().get_texture().get_image().save_png(path)
```

Wait for the state to be reached first (a signal, a frame count), then call it. Waiting only for `process_frame` can capture a frame that has not been drawn yet; `frame_post_draw` is the signal that guarantees the texture is current. The viewport texture can otherwise be black or stale, especially in `_ready`. The same display requirement applies.

## Route 4: a configured Godot MCP server

If the project already has an MCP server for Godot configured, use its run, screenshot and log tools as another way to get the same evidence. Do not require one, do not install one on your own, and do not name a paid product. Free servers exist, but check a server's licence before recommending it as an example; many projects have none.

## Reading the picture

After capture, open the PNG, then compare it with the task's criteria: what must be visible and where. Report what you actually see, element by element. A still proves layout and presence. It never proves feel, timing, animation quality or whether something is fun.

## Main-scene smoke test

The cheapest `[evidence]` log and a good first CI job: run the main scene headless for N frames and fail on a bad exit status, a timeout, or any error line from the scan above. In CI, with every step failing explicitly:

```
timeout 300 godot --headless --path . --import || { echo "FAIL: import (status $?)"; exit 1; }
timeout 120 godot --headless --path . --quit-after 120 > smoke.log 2>&1
status=$?
[ "$status" -eq 0 ] || { echo "FAIL: engine status $status (124 means timeout)"; exit 1; }
if grep -E "ERROR|SCRIPT ERROR|Parse Error|Failed to load" smoke.log; then echo "FAIL: errors in log"; exit 1; fi
echo "smoke clean"
```

## Which version and renderer is this?

Ask the binary: `godot --version`. Read the project's renderer setting as described in `SKILL.md` step 1. To try another renderer on the command line, the engine accepts a `--rendering-method <method>` override, which does not edit `project.godot`.
