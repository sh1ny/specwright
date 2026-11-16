# 0038. Settings are read by one fail-closed YAML reader

- Status: proposed
- Date: 2026-11-16
- Supersedes: —
- Adds to: 0020 (an unknown policy merges nothing) and 0033 (`yaml` approved once the `native-cli-yaml-settings` experiment passes)

## Context

`sw` read `openspec/specwright.yaml` in two ways. A lenient line reader, ported from the Python scripts, skipped what it could not read, and local callers used it. A strict check, `yamlProblem`, refused what the lenient reader would misread, and only some callers ran it: review and release stopped on it, `context` reported it and went on with the lenient values, `policy` used it for remote files, and `vcs`, `tier` and `sw vcs` never ran it. One file could then mean different things to different commands, and a local read could decide from part of a file. The lenient reader also read `yes` and `no` as booleans, a rule the `yaml` package does not share.

## Decision

- **One reader.** Every read of `openspec/specwright.yaml`, from the work tree, a committed ref or GitHub, goes through one reader in `cli/lib/src/settings/` built on `package:yaml`. No lenient or partial read exists: a file the reader refuses gives no values, and no command decides from part of it. Nothing else in `cli/` imports `package:yaml`.
- **Refusals.** The reader refuses an unquoted `yes` or `no` in any letter case (naming `true` and `false`), anchors, aliases and tags, duplicate keys, more than one document, non-string keys, a top level that is not a mapping, and flow nesting beyond 64 levels. A stack overflow in the package is caught and refused too. Each refusal names its 1-based line and why. An empty, whitespace-only or comment-only file is an empty mapping; a missing file is an empty settings file.
- **Each reader keeps its own stop.** A refused file stops each reader with its own code, before any git write, network call or file write: the `pr-pair` settings subcommands and `sw vcs` with `bad_setting` (exit 2), review and release with `bad_settings` (exit 1), and `policy`'s remote read with `lookup_failed` (exit 3), which merges nothing under 0020. `tier` alone exits 0 with the cheap tier off and a note naming the line.

**Rejected: each caller loads YAML and applies shared checks,** because a new caller could skip a refusal and read leniently again. **Rejected: a separate strict check for remote reads,** because two readers are what let local and remote reads disagree. **Rejected: keeping `yes`/`no` as booleans through a local conversion,** because it keeps a Python rule on top of YAML's.

## Consequences

- A project with a boolean written `yes` or `no` stops at its first settings read after upgrading, until the value is rewritten as `true` or `false`; the release note says so.
- A later port that reads the settings (`native-cli-update`, `native-cli-retire-scripts`) calls this reader and maps its refusal to that command's stop; it adds no reader of its own.
- `context` stops on a refused file instead of reporting `settings_problem`; `settings_problem` keeps covering problems with a value that was read.
- Reversal cost: low for the package, which sits behind one module; medium for the one-reader rule, because later ports are written against it.
