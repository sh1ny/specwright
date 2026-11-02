# 0023. Packs are additive bundles shipped in the Specwright release

- Status: accepted
- Date: 2026-11-02
- Adds to: 0021 (narrows it for packs only: an install with a pack enabled refuses a user-level skills target)

## Context

Specwright's workflow is domain-neutral. Real projects need domain knowledge on top of it: a game needs a GDD and a playtest, a web app accessibility and a browser check. The only way to add that today is by hand, as Tower of Lament does: hand-copied `gamedev-*` skills and hand-written `[pack:gamedev]` lines in `openspec/config.yaml` that no update knows about and nothing checks (#68). Many packs are expected (gamedev, web, cli/tui, desktop, and stack packs such as godot or react), so the mechanism has to scale without each pack becoming its own release, its own installer or its own exception to the gates.

OpenSpec 1.16.0 already delivers what a pack needs: `config.yaml` `rules:` keyed by artifact id, `operations:` guidance for `apply` and `archive`, and `context:` (ignored whole over 50 KB). ADR 0001 keeps OpenSpec unmodified, ADR 0011 already installs skills through a journaled, recoverable `update.sh`, and ADR 0021 lets the user install skills where they choose.

## Decision

- **First-party packs ship inside the download (D1).** A pack is `packs/<name>/` in this repo, installed from the same release tag as Specwright and checked by the same CI. `pack.json` reserves `source` for external packs; v1 refuses it (`external_pack_unsupported`).
- **The manifest is JSON (D2).** `pack.json` is read with Python's `json` module, so no script needs a second hand-written YAML reader.
- **Ownership comes from a record, never from a name prefix (D4).** `openspec/.specwright/packs.json` (format 1) records each enabled pack's version, skill names, document paths and init questions, plus a catalogue of every pack in the download. It is written on every install, staged and swapped under the journal, so a rollback restores it or its absence. A skill directory named like an enabled pack's skill that the record does not list is adopted only when it equals the download's copy byte for byte, else the install stops (`unmanaged_skill`). An unrecorded hand copy of a pack that is not enabled is never listed or touched.
- **`packs.json` is a third departure from ADR 0003**, after ADR 0011's journal and `STORE`: a durable per-project ownership record. Which skill directories Specwright installed cannot be derived from git or from the directory names (Tower of Lament already holds a hand-copied `gamedev-design`). The README says to treat it like `VERSION`: commit both or ignore both.
- **The prompt merges pack lines; a script verifies them through OpenSpec (D5).** The install prompt removes each `[pack:<name>] ` line of a pack enabled now or before this install (`packs_previous`, read from the journal's `prev_packs` or the record as it was when the update started) and appends each enabled pack's lines with that prefix, as double-quoted YAML scalars. Every other `[pack:` line is kept and reported as not managed. `update.sh pack-verify` runs `openspec instructions` in a scratch root and checks that each line arrives exactly once, that no removed pack's line remains, and that every core context line is still delivered.
- **Additive-only is structural first, a crude text check second (D6).** A pack has no field that replaces an instruction, template, dependency, skill or gate; rules attach only to the schema's artifact ids, operations only to `apply` and `archive`, and skill names carry the pack's prefix (longest prefix wins). On top, `update.sh pack-check` refuses a line pairing a gate term with a relaxing term (`relaxes_gate`). The term lists live in `packs/README.md` and the script, kept equal by an eval, and are deliberately simple.
- **Packs are refused wherever several projects would share them (D9).** Plan refuses a pack before any write on a planning store (`packs_on_store`) and when any skills directory is outside the code checkout (`packs_user_level`), on every backend.
- **This narrows ADR 0021 for packs only.** ADR 0021 lets the user choose where skills install and never refuses because of the location. Packs need per-project ownership, so an install with a pack enabled refuses a user-level skills target (`packs_user_level`). Specwright's core skills and agents still install wherever the user chooses, and an install with no pack enabled is unchanged. README Step 2 warns about this when `packs:` enables a pack.
- **Roadmap reads packs from the record (D10).** `specwright-roadmap` init suggests packs from the catalogue's `signals` over tracked and untracked files, never enables one without the user's yes, offers none on a store, and says that packs install only into in-repo skills directories. Pack documents are review context, never gated content: editing a GDD never voids the baseline.

## Consequences

A project opts in under `packs:` in `openspec/specwright.yaml`; with no packs it installs nothing extra and no pack line reaches OpenSpec. Install, update and removal of pack skills share the existing journal and recovery (journal format 2, update-script interface 2), so an interrupted install still ends at exactly the old or the new state.

Every first-party pack is checked by `pack-check` on every pull request, so a broken or gate-relaxing pack fails this repo's CI instead of a user's install. The text check has false positives (a first-party author rewords) and false negatives (caught by the structural rules and review of the pack's PR).

Packs on stores and with user-level skills directories wait for a follow-up issue; supporting them needs a second ownership protocol (owner-only lines, per-directory reference counts) that M7's CLI is the better place for. Reversal cost: low for the format and the refusals, medium for the record and the journal format.
