# Spec Delta

## MODIFIED Requirements

### Requirement: A pack is a directory with a JSON manifest
A pack SHALL be a directory `packs/<name>/` in the Specwright download holding `pack.json`. The manifest SHALL be a JSON object with `format: 1`, `name` equal to the directory name, and `description`; the optional fields SHALL be `requires`, `skills`, `context`, `rules`, `operations`, `documents`, `init` and `signals`. Any other field, or `source`, SHALL be refused: v1 installs only packs shipped in the download.

#### Scenario: A valid manifest is accepted
- **WHEN** `sw update pack-check --download <tree>` reads `packs/web/pack.json` with `format: 1`, `name: "web"`, a description and a `rules.proposal` list
- **THEN** it reports pack `web` with `"ok": true` and no refusal

#### Scenario: Malformed or unsupported manifests are refused
- **WHEN** a manifest is not valid JSON, has `format: 2`, names `webapp` in `packs/web/`, or sets `source`
- **THEN** pack-check exits 1 with a refusal naming the pack and the code `manifest_invalid`, `format_unsupported`, `name_mismatch` or `external_pack_unsupported`

### Requirement: pack-check reports in one JSON document
`sw update pack-check --download <tree>` SHALL read every pack in that download, or only those named with `--pack`, and SHALL print one JSON document with `ok`, `packs` (each with `name` and `ok`) and `refusals` (each with `code`, `pack`, `field` when it applies, `message`). It SHALL exit 0 when every pack passes and 1 otherwise, and SHALL write no file.

#### Scenario: All packs pass
- **WHEN** pack-check runs on a download whose packs are all valid
- **THEN** it exits 0 with `"ok": true` and an empty `refusals`

#### Scenario: A named pack is missing
- **WHEN** pack-check runs with `--pack mobile` and `packs/mobile/` does not exist
- **THEN** it exits 1 with refusal `pack_unknown` naming `mobile`, and lists the packs the download has

### Requirement: Packs are refused on a planning store in v1
When the planning root is a store (`sw update` role `claim`, `owner` or `other`), an install with any pack enabled SHALL stop before any write with refusal `packs_on_store`, because pack lines in a store's `config.yaml` would apply to every project that uses the store.

#### Scenario: Repo-local project with packs
- **WHEN** role is `none` and `packs:` enables `web`
- **THEN** plan reports no `packs_on_store` refusal

#### Scenario: Store-backed project with packs
- **WHEN** role is `owner` and `packs:` enables `web`
- **THEN** plan exits 1 with refusal `packs_on_store`, and no installed file changes
