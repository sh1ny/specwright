# Writing a pack

A pack is a bundle of skills, rules, context lines, project documents and init questions that a project opts in to under `packs:` in `openspec/specwright.yaml`. A pack **adds** to Specwright's workflow. It never removes a step and never relaxes a gate. Packs ship inside the Specwright download (v1 has no external packs) and are installed from the same tag as Specwright.

`update.sh pack-check` reads every pack in `packs/` (or only those named with `--pack <name>`) and prints one JSON document: `{"ok", "packs": [{"name", "ok"}], "refusals": [{"code", "pack", "field", "message", ...}]}`. It exits 0 when every pack passes and 1 otherwise, and writes nothing. This repo's CI runs it over `packs/` on every pull request, so a broken pack fails here and never in a user's install.

## Layout

```
packs/<name>/
  pack.json                       the manifest (required)
  skills/<skill>/SKILL.md         one directory per listed skill
  documents/<template>.md         templates for the pack's project documents
```

## pack.json

A JSON object. `format`, `name` and `description` are required; every other field is optional. Any field not listed here is refused (`manifest_invalid`), and `source` is refused (`external_pack_unsupported`).

| Field | Meaning |
|---|---|
| `format` | `1`. Any other value is refused (`format_unsupported`). |
| `name` | Equal to the directory name (`name_mismatch` otherwise). |
| `description` | One line: what the pack is for. |
| `requires` | A list of pack names, without versions. See [Requires](#requires). |
| `skills` | A list of skill names. See [Names and prefixes](#names-and-prefixes). |
| `context` | A list of lines added to the project's `context:`, which every artifact receives. |
| `rules` | An object: artifact id -> list of lines. Each key is an artifact id of the downloaded `schemas/specwright/schema.yaml` (`unknown_artifact` otherwise). |
| `operations` | An object: `apply` or `archive` -> `{"guidance": [lines]}` (`unknown_operation` otherwise). |
| `documents` | An object: document id -> `{"path": default relative path, "template": file in the pack}`. See [Documents and init questions](#documents-and-init-questions). |
| `init` | `{"questions": [single-line strings]}`: asked by roadmap init and `pack`. |
| `signals` | A list of glob patterns, relative to the project, that suggest the pack. See [Signals](#signals). |

## Names and prefixes

A pack name matches `^[a-z][a-z0-9-]*$` and is not `specwright`, `openspec` or `opsx`, and does not start with one of them followed by `-`. These names belong to the core.

Every skill of a pack is named `<pack>-<something>` and lives in `skills/<skill>/` with a `SKILL.md`. Every directory under `skills/` must be listed in `skills`, and every listed skill must exist (`skill_name`, `skill_missing`, `skill_unlisted`).

The **longest prefix** wins. A skill belongs to the pack whose `<pack>-` prefix is the longest match among all the packs in the download. With packs `react` and `react-native`, the skill `react-native-nav` belongs to `react-native`, and `react` that lists it is refused. Choose names so that a pack's name is not the start of another pack's skill names, or give the longer pack the skill.

A pack's skills never take over Specwright's commit, review or verify ownership. Specwright's own skills (`specwright-commit`, `specwright-review`, `specwright-pr`, ...) decide when a change is committed, reviewed and verified. A pack skill may add domain knowledge that those flows name as "the installed project skills that apply", and may never replace or bypass one of them.

Skill descriptions load into every session of a project that enables the pack. Keep them short; put the guidance in the skill body, which loads on demand.

## Lines

`context`, each `rules` list and each `operations.<op>.guidance` list hold **lines**. Each line is a non-empty, single-line string of at most 500 characters. A pack has at most 40 lines in total, and its `context` lines at most 2048 bytes in UTF-8. A line must not start with `[pack:`: the installer adds the prefix `[pack:<name>] ` that marks the line as the pack's, and removes and re-adds those lines on every install (`line_invalid`, `too_many_lines`, `context_too_large`).

Write rules with **conditional wording**: "A change to gameplay ends with a playtest task." instead of "Always add a playtest task." A rule that applies only when the change touches the pack's domain costs nothing on other changes, and a pack's lines stay short because most guidance belongs in a skill that loads on demand.

## Additive only

The guarantee is **structural**. A pack has no field that replaces an artifact's instruction, template or dependencies, a skill of the core, or a gate: it can only add lines, skills, documents and questions. Rules attach only to known artifact ids, skills carry the pack's prefix, and a document template must exist with a safe default path, so nothing is silently dropped by OpenSpec or written outside the project.

On top of that structure, `pack-check` refuses a line that contains **both** a gate term and a relaxing term (`relaxes_gate`). Words are matched on word boundaries.

- Gate terms (any case): `triage`, `t1`, `t2`, `t3`, `t4`, `t5`, `t6`, `tier`, `verdict`, `review`, `verify`, `verification`, `gate`, `pre-ship`, `preship`, `test-first`
- Gate terms (capitals only): `LIGHT`, `FULL`
- Relaxing terms: `skip`, `skips`, `skipped`, `waive`, `waived`, `relax`, `bypass`, `exempt`, `ignore`, `omit`, `downgrade`, `optional`, `not required`, `need not`, `no need`
- Relaxing only when negated: `trip`
- Negators: `not`, `never`, `n't`

`trip` counts as a relaxing term only right after a negator, so `A change to the save format must trip T4.` passes and `Actor-local state machines do not trip T2 on their own.` is refused. The tier names `LIGHT` and `FULL` match in capitals only, so `Skip full-screen effects on the title screen.` passes. `Never skip the playtest task.` (a relaxing term, no gate term) and `The review checks contrast ratios.` (a gate term, no relaxing term) pass too.

This check is **deliberately crude**. It does no negation-scope analysis and knows no synonyms, because every reviewer would find another phrasing and the list would never be done. A false positive costs the author a rewording; a false negative is caught by the structural rules above and by review of the pack's pull request. An eval keeps these lists equal to the ones in `scripts/update.sh`.

## Requires

`requires` lists pack names. Every required pack must exist in the download (`pack_requires`) and must be enabled in the project too: the installer never enables a required pack on its own. A cycle is refused (`pack_cycle`). Packs install dependencies first, then by name, and their lines follow that order.

## Documents and init questions

A `documents` entry names a template in the pack (`documents/gdd.md`, which must exist) and a default path relative to the project (`docs/game/gdd.md`, without `..`, not absolute, not a directory). The install creates the file from the template only when it does not exist, never overwrites it, and keeps it when the pack is removed. A project can override the path under `packs.<name>.documents` in `specwright.yaml`.

`init.questions` and `signals` are lists of non-empty single-line strings. A broken entry is refused with `document_invalid`, `init_invalid` or `signals_invalid`.

Documents are review context, never gated content: editing one never voids a baseline.

## Signals

`signals` are glob patterns relative to the code toplevel, matched against the files git lists (tracked, and untracked but not ignored). Roadmap init suggests a pack when a pattern matches, together with the packs it requires. A signal is only a suggestion: the project enables a pack by editing `packs:`, and only on the user's yes.

## What v1 refuses

- **Planning stores.** When the planning root is a store, an install with any pack enabled stops with `packs_on_store`: pack lines in a store's `config.yaml` would apply to every project that uses the store.
- **User-level skills directories.** When a chosen skills directory is outside the code checkout (for example `~/.claude/skills`), an install with any pack enabled stops with `packs_user_level`: several projects would share, and remove, the same pack skills.
- **External packs.** `source` is reserved and refused.

## Check a pack

```
bash scripts/update.sh pack-check                  # every pack
bash scripts/update.sh pack-check --pack gamedev   # one pack
```

Refusal codes: `manifest_invalid`, `format_unsupported`, `name_mismatch`, `external_pack_unsupported`, `document_invalid`, `init_invalid`, `signals_invalid`, `skill_name`, `skill_missing`, `skill_unlisted`, `unknown_artifact`, `unknown_operation`, `line_invalid`, `too_many_lines`, `context_too_large`, `relaxes_gate`, `pack_requires`, `pack_cycle`, `pack_unknown`.
