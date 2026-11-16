# Spec Delta

## MODIFIED Requirements

### Requirement: The cheap tier is off unless enabled
`cheap_tier.enabled` SHALL turn the cheap tier on only when it reads as `true`. Missing or `false` SHALL leave it off. Any other value, or a `cheap_tier` that is not a map, SHALL leave it off with a note. A settings file the reader refuses, a plain `yes` or `no` included, SHALL leave it off with a note naming the line. `pr-pair.sh tier --code <toplevel>` SHALL print `{"ok": true, "cheap_tier": bool}` plus any `note`, and exit 0 whatever other settings hold. The template SHALL ship `false`.

#### Scenario: Unset leaves dispatch unchanged
- **WHEN** `openspec/specwright.yaml` has no `cheap_tier` key and apply delegates a task group of a LIGHT change
- **THEN** `pr-pair.sh tier` prints `"cheap_tier": false`, and the group goes to `specwright-implementer`

#### Scenario: An unrecognised value is off and reported
- **WHEN** `cheap_tier.enabled` is `on`
- **THEN** `pr-pair.sh tier` prints `"cheap_tier": false` and a `note` naming `on`, and apply's report repeats that note once

#### Scenario: The section is not a map
- **WHEN** the settings hold `cheap_tier: true` instead of `cheap_tier: { enabled: true }`
- **THEN** `pr-pair.sh tier` prints `"cheap_tier": false` and a `note` saying `cheap_tier` must hold `enabled`

#### Scenario: Another setting is invalid
- **WHEN** `pr.merge` is `agent`, `pr.merge_method` is `fast`, and `cheap_tier.enabled` is `true`
- **THEN** `pr-pair.sh tier` exits 0 and prints `"cheap_tier": true`

#### Scenario: A yes is off and reported
- **WHEN** `cheap_tier.enabled` is written `yes` on line 88
- **THEN** `pr-pair.sh tier` exits 0 with `"cheap_tier": false` and a `note` naming `line 88`, `true` and `false`

#### Scenario: The setting cannot be read
- **WHEN** `pr-pair.sh tier` exits non-zero, or its output has no `cheap_tier` field
- **THEN** apply treats the cheap tier as off and says once that the setting could not be read
