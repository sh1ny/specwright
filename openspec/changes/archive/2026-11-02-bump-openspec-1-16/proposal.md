# Proposal

## Why

OpenSpec 1.16.0 is out, and Specwright pins 1.14.1: the install and update stop on any other version, so a machine that upgrades OpenSpec can no longer install or update Specwright without the per-run override (#164). Checked against 1.16.0, every OpenSpec output Specwright parses is unchanged and all 22 specs pass `validate --strict`, so the pin can move. This serves milestone M6 as a maintenance change outside its planned list, released as 0.14.1; it advances no M6 exit criterion beyond "each change ships as its own release".

## What Changes

- Move the OpenSpec pin from 1.14.1 to 1.16.0 everywhere the upgrade rule in `CONTRIBUTING.md` names: `OPENSPEC_VERSION`, the README badge, the versioned install commands (prerequisites, install Step 1, `CONTRIBUTING.md`), every README line that spells out the pin (version note, Step 1 comparison, Step 3 example, the "forked from `spec-driven`" note, the Stores note), the OpenSpec-pin evals (`grade.py`, `test_grade.py`, `evals.json`) and `openspec/strategy.md`.
- Name the new Node.js requirement: since 1.16.0 the npm package needs Node.js 22.12 or later, so the README prerequisites and `CONTRIBUTING.md` say so next to the `npm i -g` command.
- Port the one instruction line upstream added to `spec-driven`'s specs artifact in 1.16.0 (every scenario needs a WHEN/GIVEN and a THEN step, or `validate --strict` fails) into `schemas/specwright/schema.yaml`.
- Record the change in the M6 section of `openspec/roadmap.md` and its release list (0.14.1).

No behavior changes: the version check, the override and the error messages work as before, only with a different pinned value.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The `install-update` requirements describe the pin check with example versions (1.14.1, 1.14.2, 1.15.0) that stay valid examples; no requirement changes, so this change sets `skip_specs: true`.

## Impact

- Users and dogfood projects need OpenSpec 1.16.0 installed before they install or update to this release (or state the override for one run). An npm install of 1.16.0 needs Node.js 22.12 or later.
- CI installs OpenSpec from `OPENSPEC_VERSION`, so every suite runs on 1.16.0 from this change on.
- Files: `OPENSPEC_VERSION`, `README.md`, `CONTRIBUTING.md`, `schemas/specwright/schema.yaml`, `openspec/strategy.md`, `openspec/roadmap.md`, `evals/git-workflow/{grade.py,test_grade.py,evals.json,test_instructions.py}`, and the release's version files.

## Release Notes

Specwright now pins OpenSpec 1.16.0 instead of 1.14.1. Install or update OpenSpec to 1.16.0 before updating Specwright (an npm install of 1.16.0 needs Node.js 22.12 or later). Nothing Specwright reads from OpenSpec changed between the two versions.

### Changed

- The OpenSpec pin moves from 1.14.1 to 1.16.0: the install and update now expect `openspec --version` to print 1.16.0, and the README and CONTRIBUTING install commands name `@fission-ai/openspec@1.16.0` with its Node.js 22.12 requirement (#164).
- The `specwright` schema's specs instructions now say every scenario needs a WHEN/GIVEN and a THEN step, which OpenSpec 1.16.0's `validate --strict` enforces (#164).
- Under the new pin, `openspec validate --strict` also fails on delta-spec text that archive would drop, and `validate` exits 1 on an unreadable or invalid `openspec/config.yaml`; check those first if a change that passed before now fails (#164).
