# Proposal

## Why

`review-run.sh` is the last large Python program behind the design and pre-ship reviews. It embeds 1,600 lines of Python, carries its own YAML reader and a copy of `bounded.py`, and reaches the VCS backend by starting `bash pr-pair.sh vcs`. This change serves M8, Complete the native CLI migration (#148). It advances these exit criteria: the review operations use `sw` with their JSON, exit-code and workflow contracts covered on the three CI platforms; `sw` never starts a shipped script or Python for its own work; and `sw` starts no bash or sh. It is change 7 of M8. Its scope on the roadmap is the `review-run.sh` port.

The reviewer command lines are also fixed in code, and the CLIs they drive have moved under them. On OMP 18.19 and Codex 0.166, the current lines no longer give a read-only reviewer:

- **OMP.** `find` is now a semantic search that makes its own paid model calls. Users of other projects have had to edit `review-run.sh` by hand to drop it. OMP also offers `learn` and `manage_skill` despite `--tools read,grep,find,glob` and `--no-skills`. Both write outside the checkout, to OMP's long-term memory and to `~/.omp/agent/managed-skills`. Retained `read` and `grep` tools also accept network targets; disabling memory alone does not restrict those targets.
- **Codex.** Under `exec -s read-only --ignore-user-config`, Codex still exposes web access, image generation, `spawn_agent`, plugin installation, memories and hooks.

These were observed on 2026-11-12, with the tool lists the CLIs reported for the route's current command line. Each CLI release can change them again, so the user needs a way to adjust each route without editing a shipped script.

This proposal amends the scope listed for change 7 in `openspec/roadmap.md`: the per-reviewer settings and the isolation fixes join the port, because the port rewrites the command-line builder anyway.

## What Changes

- **Port.** `review-run.sh` and all of its subcommands move to `sw review`: `select`, `preflight`, `run`, `record`, `waive`, `gate`, `archive-only` and `rounds`. Each keeps its JSON documents, exit codes (0, 1, 2, 3), records, state directory and receipts. `review-run.sh` becomes an ADR 0028 shim that resolves the project's `sw`. Its embedded Python and its YAML reader go. The `bounded.py` copy in `skills/specwright-review/scripts/` also goes, because no shipped caller uses it once `review-run.sh` is a shim.
- **In-process calls.** The VCS backend and the settings come from the ported Dart interfaces, not from `bash pr-pair.sh vcs`. Reviewer CLIs, `git` and the probes start through the native launcher (ADR 0034), under the existing deadline and stream bounds.
- **Per-route settings.** A new optional `review.routes.<route>` block lets the user change each reviewer's command line without editing a script:
  - `tools`: the tool list passed to claude and OMP.
  - `disable`: Codex features to turn off.
  - `args`: extra flags.

  Specwright keeps its isolating flags fixed and refuses a setting that would drop or weaken them: the read-only sandbox, `--restricted`, a fresh session, and no user skills, rules or extensions. OMP has one explicit exception: a fixed Specwright-owned trusted module enforces local tool targets; user settings cannot replace or add trusted modules. The refusal is a named stop before any reviewer starts. **BREAKING** for anyone who edited `review-run.sh` by hand: those edits are lost in the update and move into `review.routes`.
- **Isolation defaults.** Shipped defaults close the gaps found above:
  - OMP's default tools become `read,grep,glob`; memory, auto-learn and web fetching are switched off for the run. One fixed trusted local-target gate blocks remote URI/resource targets, including SSH and opaque MCP URIs, before tool execution.
  - Codex turns off the features behind its web, image-generation, plugin-install, memory, hook and goal tools. Its agent tools (`spawn_agent` and the rest of `collaboration.*`) remain even with `multi_agent` off, and no Codex 0.166 switch removing them was found. They stay under the read-only sandbox.
  - Claude's existing line is kept. It gains only what the experiment finds missing.
- **Receipts.** The receipt records the effective tool list, the disabled features and the extra arguments used, so a review shows what the reviewer could do. OMP also records its fixed local-target policy identity and module digest.
- **Documentation.** `specwright-review`, the settings template and the docs describe `review.routes`. They also give a short procedure for checking a new CLI version's tool list. There is no runtime discovery: help text and feature lists are not stable contracts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-routes`: reviewer routes run in `sw` with their contracts kept. Each route's tools, disabled features and extra flags become settings within fixed isolation. The shipped defaults close the observed mutation and remote-tool gaps: OMP denies remote tool targets, and Codex disables its dedicated network and other unsafe features while retaining its read-only sandbox. This is not an OS-wide network sandbox; model-provider transport remains necessary. The receipt records the effective controls.

## Impact

- **Code:** new `cli/lib/src/review/` modules and an `sw review` command in `cli/lib/src/cli.dart`; reuse of `cli/lib/src/process/` (bounded runs, launcher, tree stop) and of `cli/lib/src/settings/` and `readVcsSettings`. OMP's trusted policy is emitted from Dart-owned source into the private run directory and executed inside OMP, not by a separate script/interpreter process.
- **Scripts:** `skills/specwright-review/scripts/review-run.sh` becomes a shim; `skills/specwright-review/scripts/bounded.py` is removed.
- **Skills and docs:** `skills/specwright-review/SKILL.md` and the settings template (`review.routes`); unchanged call sites in `specwright-commit`, `specwright-pr`, `specwright-finish`, `specwright-roadmap` and the `specwright-reviewer` agents keep working through the shim.
- **Evals:** `evals/review-routes/test_review_run.py` runs against the shim and `sw`. New cases cover per-route settings, refusal of weakening values, the new defaults and script-absent and interpreter-absent runs. Dart unit tests go under `cli/test/review/`.
- **Settings:** a new optional `review.routes` key. Nothing existing changes meaning.
- **Dependencies:** `toml` 0.18.0 and its reviewed runtime closure parse Codex's `windows.sandbox` value. The OMP policy uses OMP's existing JavaScript runtime; Node 22 is a development-only host for tests of the emitted policy, following the existing eval CI runtime.
- **Roadmap:** change 7's entry is reworded to include the settings and isolation fixes.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: How per-reviewer parameters are configured

- **Choice:** Typed keys under `review.routes.<route>`: `tools`, `disable` and `args`. Fixed isolating flags are kept, and a value that would drop or weaken them is refused. The shipped defaults are updated for today's CLIs. The sole trusted-code exception is the fixed OMP local-target module in S5; user extensions remain disabled.
- **Rejected:** Free-form `args` only, because a typo or a copied flag could remove read-only isolation without notice. Fixed defaults with no settings, because each CLI change would again need a Specwright release or a hand edit.
- **Reversal cost:** medium (a new settings key that users write into their configs)
- **Important:** yes: binds future changes (a config key) and changes settings users see
- **Chosen by:** user

### S2: Close the isolation gaps found in the experiment within this change

- **Choice:** The new defaults drop OMP's `find`, switch off `learn`, `manage_skill` and web fetching, and enforce local tool targets with the fixed trusted gate in S5. Codex's network, image, plugin, memory, hook and goal features are disabled. Evals check the effective controls; native trials must show actual tool denials and no fixture requests, not merely absent tool names.
- **Rejected:** Filing the gaps as a separate known-gap issue, because the port already rewrites these command lines and the gaps break the "read-only" requirement today.
- **Reversal cost:** low
- **Important:** yes: changes behaviour users see, and was found on observed rather than documented evidence
- **Chosen by:** user

### S3: No runtime discovery of each CLI's tools

- **Choice:** Defaults plus user settings. The receipt records what was used, and the docs give a manual check for a new CLI version.
- **Rejected:** Parsing `omp --help` and `codex features list` at select time. Their format is not a contract, so the probe would break on a CLI update.
- **Reversal cost:** low
- **Important:** yes: chosen on weak evidence (two CLI versions observed)
- **Chosen by:** user

### S4: The settings and isolation fixes land in the port change

- **Choice:** One change, `native-cli-review`. The roadmap entry for change 7 is reworded.
- **Rejected:** A separate change after the port, because it would build the command-line builder twice.
- **Reversal cost:** low
- **Important:** yes: changes the milestone's scope
- **Chosen by:** user

### S5: One fixed trusted OMP local-target gate

- **Choice:** Keep the ban on reviewer-directed remote targets. Use OMP's supported `fetch.enabled: false` plus one fixed `--trusted-extension` local-target gate while retaining `--no-extensions`. The module is Specwright-owned, private to the run, and cannot be replaced through settings. Local review operations and model API transport remain available. This is a tool-target policy, not an OS-wide network or filesystem sandbox.
- **Rejected:** Native web-fetch disable alone, because SSH and MCP resources bypass it. Allowing other remote resources and narrowing the promise, because the user chose to preserve the remote-target ban. Enabling ambient user extensions, because a policy module does not justify running user extension code.
- **Reversal cost:** medium (an additional reviewer-runtime policy and its compatibility tests)
- **Important:** yes: changes the fixed extension boundary and privacy guarantee
- **Chosen by:** user (apply-time network-boundary decision after round 5)

### S6: Canonicalize bare open-ended read selectors before native dispatch

- **Choice:** Preserve single-path local selector support by having the fixed hook schema-replace a bare extensionless open-ended read target with its explicit `./` local form, then validate the effective input. Keep compound/remote ambiguity fail-closed.
- **Rejected:** Widening only the policy regex, because OMP 18.19.0 can still route the input through its opaque MCP-resource fallback. Requiring users to add `./` and narrowing the compatibility promise, because the user chose canonicalization.
- **Reversal cost:** low (fixed-hook normalization and its native replay)
- **Important:** yes: resolves an upstream URI/selector ambiguity at the trusted boundary
- **Chosen by:** user (pre-ship round 2 selector-routing decision)

## Release Notes

`sw review` now runs the design and pre-ship reviews, replacing the Python in `review-run.sh`. Each reviewer CLI can be tuned in `review.routes` while Specwright keeps its isolation controls fixed. OMP's defaults disable memory and web fetching and enforce local tool targets through one fixed trusted gate. Codex disables its dedicated web, image, plugin, memory, hook and goal features under the read-only sandbox. Model-provider traffic is not blocked.

### Added

- `review.routes.<route>` settings (`tools`, `disable`, `args`) for the codex, claude and omp reviewer routes, with named stops for unsafe tools, protected flags and their aliases; receipts record effective controls and OMP's fixed policy identity and module digest (#148).
- A reviewer-CLI upgrade checklist requires native tool inventories, protected-flag alias checks, direct child write-denial evidence and actual remote-target errors with zero fixture connections; model refusals alone do not pass (#148).

### Changed

- `review-run.sh` is a shim over native `sw review --args-stdin`. Its subcommands, JSON documents, exit codes and record paths remain compatible, including Windows MSYS filesystem paths. Review operations run without interpreter subprocesses; the compatibility shim and shared resolver still require Bash and Python (#148).
- Reviewer output stays bounded in memory, and branch-tip snapshots stream each Git blob in at most 64 KiB chunks rather than buffering tree contents. Snapshotting still has no deadline (#148).
- The OMP reviewer's default tools are `read,grep,glob`, with memory, auto-learn and web fetching off and a fixed trusted local-target gate. User extensions remain disabled. The Codex reviewer turns off its web, image, plugin, memory, hook and goal features (#148).
- An OMP older than 18.19.0 is skipped as a reviewer, because its memory could not be turned off reliably (#148).
- The CLI ships `toml` to parse Codex's Windows `windows.sandbox` value as TOML (#148).
- A review stops with `bad_settings`, naming the line, when `openspec/specwright.yaml` has a line the settings reader would misread; `review-run.sh` used to read it leniently (#148).

### Removed

- `skills/specwright-review/scripts/bounded.py` (#148).
