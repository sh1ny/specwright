# Review

## Metadata

- **Round:** 2, new full review.
- **Prior round:** Installation coverage and engine-neutrality findings were addressed; this round assesses the substantially revised plan.
- **Reviewer:** Codex.
- **Reviewed:** Proposal, delta spec, design, tasks, prior review, schema review template and workflow instructions; ADRs 0005, 0016, 0023 and 0024; pack authoring rules, pack eval helpers and checks, update installer harness, `scripts/update.sh` pack validation, CI configuration and roadmap M6.
- **Validation:** Read-only design review. No files changed or tests run.

## Findings

### Critical (blocking)

None.

### Moderate

**M1 — Tuning triage can be read as permission to bypass the core workflow.**

The gamedev-design writer instructions direct tuning-only requests to “Edit the data, log one tuning line,” while tweak and new-behaviour requests explicitly proceed toward a proposal. It later says the skill never plans code, commits or opens PRs.

This creates two competing execution paths. A writer can reasonably implement direct data editing for tuning, bypassing proposal, triage, test-first implementation and the player-visible playtest requirement. `pack-check` cannot catch this: it checks manifest lines, not instructions inside skill files. ADR 0023 requires pack skills to preserve core workflow ownership.

Classification should determine the required GDD work, without creating an implementation exemption.

**M2 — Writer instructions disagree on the templates to ship.**

The [tasks](/F:/Dev/specwright/openspec/changes/gamedev-pack/tasks.md:81) require `templates/brief.md` and `templates/decisions.md`, but the gamedev-design writer instructions specify `assets/brief-template.md` and `assets/decisions-template.md`. The playtest instructions also identify the latter asset as their template source.

Similarly, task 2.4 requires `templates/ux.md`, while the UX instructions specify `templates/ux-template.md` and a separate worked-example reference.

The delta spec expressly requires these document templates under `templates/`. Following the supposedly authoritative instructions can therefore violate the spec or create duplicate templates. Deferring filenames to apply does not resolve conflicting instructions inside the constrained writer packets.

**M3 — Installer tests are scheduled after implementation, and the caller contract has only a token-level assertion.**

[Task 4.1](/F:/Dev/specwright/openspec/changes/gamedev-pack/tasks.md:150) creates the installer tests after all three packs exist and instructs the implementer to “see the rows pass.” Rows 2–4, 21 and 27–29 start red, but have no planned failing run before implementation. This conflicts with the schema’s explicit test-first requirement.

Separately, row 23’s scenario checks only that `gamedev-ux/SKILL.md` names the shared skill and save folder. D6’s corresponding static check likewise emphasizes the folder. Those checks can pass while the caller omits stage, scaling, font or input settings—the central new D9 interface.

The scenario map covers all 30 named scenarios, but name coverage alone does not establish either test-first execution or the complete parameter contract.

**M4 — The check of the written content has no recorded task.**

The plan reviews the written skills, but no task records that review or its pass condition. Findings should go back to the writers as requirement-level correction requests.

**M5 — Specs/design rule placement remains ambiguous enough to produce incompatible tests.**

[Design D10](/F:/Dev/specwright/openspec/changes/gamedev-pack/design.md:218) places each shared concern under one artifact, where it acts first. The [delivery scenario](/F:/Dev/specwright/openspec/changes/gamedev-pack/specs/domain-packs/spec.md:105) says “each output” contains its artifact’s lines, “including” frame budget, previous saves and doing nothing.

This leaves unclear whether all three named concerns must appear in both outputs or are distributed across them. Task 2.6 repeats “specs and design” without fixing the allocation. A test can consequently assert only whatever the manifest happens to contain and miss a required concern entirely.

### Suggestions

- The planned content comfortably fits the **40-line** limit, even if the five shared concerns were duplicated across specs and design. The existing validator enforces **500 characters per line** and **2048 UTF-8 bytes of context**; the existing context eval includes managed prefixes and newlines against OpenSpec’s aggregate limit. Final wording still needs those checks.
- Preserve the playtest instructions’ correct distinction: low confidence adds follow-up guidance; it does not excuse an unticked `[user]` task or override an explicitly required fresh-player check.
- Correct roadmap Later’s stale dogfood release reference from 0.19.0 to 0.20.0.

## Verdict

The revised architecture and installer coverage are coherent. The remaining issues are bounded planning corrections that should be resolved before implementation.

## Required Changes

1. Amend tuning triage to hand implementation to core Specwright. State explicitly that tuning classification changes GDD obligations only and grants no exemption from core triage, review, tests, task coverage or applicable playtests.
2. Reconcile template paths across tasks and all writer instructions. Select one canonical path under each owning skill’s `templates/`; update the playtest handoff accordingly and preserve skill-name-only cross-skill references.
3. Schedule installer tests before the pack content they validate, with expected red runs and later green runs. Extend D9 checks to cover the caller’s stage, scaling, font, input and save-folder settings, including a deliberately missing or mismatched setting.
4. Add tasks that review the written skills' wording and structure, with fresh-context writers and findings returned as requirement-level requests.
5. Add an explicit concern-to-artifact table for the five specs/design rules. Align the delta scenario, D6 assertions and task 2.6 with that table; assert required semantic content independently of the manifest being tested.

## Changes Applied

1. **Tuning triage (M1).** The gamedev-design request triage: the class sets only the GDD work before the proposal; every class, tuning included, goes through the normal change (proposal, triage, review, tests, tasks, the playtest when player-visible), and the skill never edits data, code or tests. Design failure modes and task 2.1 say the same.
2. **Template paths (M2).** One canonical path per document under the owning skill's `templates/`: `gamedev-design/templates/brief.md` and `templates/decisions.md`, `gamedev-ux/templates/ux.md` (worked example in `references/ux-example.md`), `gamedev-narrative/templates/narrative.md`. The design, UX and playtest instructions now name these; playtest still refers to the decisions template by skill name only.
3. **Test-first and the D9 contract (M3).** Both test modules are written in group 1 (tasks 1.2 and 1.3) and run red before any pack content; task 4.1 only turns U green. The "Game settings passed" scenario now requires a value for `stage`, `scaling`, `font`, `input model` and `save folder` in `gamedev-ux`, and the same five names with neutral defaults in `ui-prototyping-html`; a new scenario, "A missing game setting", fails on an omitted or unknown setting (test map row 25, D6 d).
4. **Content review (M4).** Tasks 4.2 and 4.3 review the written skills' wording and structure; findings go back to the writer as requirement-level requests, and implementers are fresh-context subagents.
5. **Concern allocation (M5).** The requirement is split into "gamedev specs lines" (save compatibility, feel vs layout, idle doesn't win) and "gamedev design lines" (tuning in data, frame budget), each with its own scenario asserting its lines and the absence of the other's. D10 carries the concern-to-artifact table with the fixed test keywords; D6 and task 2.5 follow it.

Suggestions: the roadmap's deferred dogfood line now says 0.20.0. The playtest confidence-mark wording is kept as is.

`openspec validate gamedev-pack --strict` passes (32 scenarios).

## Rebuttals

None.

VERDICT: APPROVE_WITH_CHANGES
CHANGES_APPLIED: yes