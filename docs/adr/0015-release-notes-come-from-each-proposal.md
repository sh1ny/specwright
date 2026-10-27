# 0015. Release notes come from each change's proposal

- Status: accepted
- Date: 2026-10-27

## Context
ADR 0010 makes a release an annotated tag created once, with the notes as its message and the GitHub release body taken from it, so a tag's notes are permanent. `release.sh` built those notes from one line per archived change, the first sentence of its proposal's `## Why`. That says why a change was needed, not what it shipped: v0.8.1 read "fix-m4-gaps (#129): M4 closed with eight known gaps filed as issues", and a reader had to open the PR and every issue to learn what was fixed (#130). ADR 0003 requires the notes to be rebuilt from the repo alone, and ADR 0002 keeps the deterministic part in the thin script.

## Decision
- **A `## Release Notes` section in `proposal.md` is the source of release notes.** It holds a summary of at most 600 characters, then `### Added`, `### Changed`, `### Fixed` and `### Removed` lists (each at most once, items of at most 500 characters). HTML comments are ignored and indented lines continue an item. `release.sh` reads it from the archived proposal at the release commit (store-backed: the store's main), for the last 1 000 changes of the range, sizes checked first so no blob over 64 KB is read for its section.
- **The release summary is the bumping change's.** It comes from the change whose archived `tasks.md` has the ticked `release.sh bump --to <V>` task and a valid section, else from the last change with a valid section. The bump task rewrites that summary to describe the whole release and checks it with `release.sh notes --proposal`.
- **Items are grouped across changes.** The notes are the summary, then `Added:`, `Changed:`, `Fixed:` and `Removed:` with every change's items in main's first-parent order, at most 150 items with a count line past them. An item naming no issue or PR gets its change's PR appended.
- **An invalid, oversized or missing section falls back to the Why line.** That change is listed under `Changes:` as before, and `status` and `publish` name it in `warnings`; a release never stops on a section. A release in which no change has a valid section gets the notes it had before sections existed, byte for byte, so backfills do not change.
- **Section-only edits keep the design review verdict.** Apply keeps the items current in each task commit, and every commit that edits the section runs `notes --proposal`; any other proposal, spec or design edit still voids the verdict. With `release.enabled` true, the pre-ship review checks the section against the diff.

**Rejected: a new schema artifact (`release-notes.md`)**, because it adds a node every status, tasks precheck and archive must carry, for one paragraph and a list. **Rejected: a `CHANGELOG.md` edited by each change**, because parallel branches conflict on the same lines and the notes are no longer tied to the archived change the range already finds. **Rejected: a summary passed to `publish` on the command line**, because the tag message could then not be rebuilt from the repo. **Rejected: a lenient parser**, because it would silently misfile items in a permanent tag.

## Consequences
- Release notes say what shipped, with references, and a tag's message reads as plain text (`Fixed:`, not `###`).
- The section format is read from archives forever: changing it is a workflow change, and a later format must keep reading this one.
- A wrong item is permanent once tagged, so the pre-ship review treats an item the diff does not ship as P1.
- Reversal cost: medium. Archived proposals keep their sections; only the reader and the instructions change.
