# Proposal

## Why

`native-cli-retire-scripts` (#233) removed the shipped scripts. To keep that change small, it left the main specs naming them and added one requirement, "Retired script names map to sw commands", that gives the old names a meaning. Today 109 requirements in 21 capabilities still name a retired script 292 times. A reader, or the agent planning a later M9 change, meets `vcs.sh fetch-main` and has to translate it through the name map first. This change rewrites that wording now, so the other four M9 changes after it edit the new text.

The README install prompt has the same problem, and worse (#242). Three of its instructions can stop, ask or fail on an install that is correct when read literally:
- Step 7's "nothing else is in them" fails in every project that also holds OpenSpec's `openspec-*` skills.
- Step 6 lists a project's own `release.version_files` entries as keys to remove.
- Step 8 names "the `interface <n>` line" in a way a strict reader can miss.

It also still describes `vcs.sh` as if it were a current part.

This change serves M9 (Adoption and configuration). It advances these exit criteria:
- "The main specs name `sw` commands instead of retired scripts, apart from the name-map requirement and the history it records (#234), and the README install prompt no longer stops, asks or fails a correct install on its Step 6 user-data list, its Step 7 file check or its Step 8 interface line (#242)". This one is agent-verified: at the milestone close the agent searches the main specs for the 14 retired names and checks each hit against the design's Allowlist inventory.
- "All M9 changes are archived on main and their releases are published".

## What Changes

- **Spec wording sweep (#234).** In each main-spec requirement and scenario that names a retired script (`vcs.sh`, `as.sh`, `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh`, `sw-path.sh`, `task-cover.sh`, `fit-subject.sh`, `finish.sh`, `review-run.sh`, `release.sh`, `update.sh`, `bounded.py`, `reviewers.py`), replace the name with the `sw` command that the name map gives it. Behaviour stays the same. Each delta is a MODIFIED requirement whose meaning is unchanged.
- The name-map requirement stays. So do passages that record history: what an older version or an older user-level copy did, and what the retirement removed.
- File names that are still real stay as they are: eval modules and helpers such as `evals/run.py` and `bashexe.py`, test file names, `cli/tool/*.py`, and example file names inside scenarios such as `a.sh` or `greet.py`.
- A requirement whose meaning would change if reworded is left out of the sweep and filed as its own issue. Five are: three found while drafting, and the two `vcs-backends` archive-undo requirements for jj and GitButler (design D3).
- One `native-cli` requirement is added: where a reworded requirement shows an `sw` command without the options it needs (`--download`, `--code`, `--repo`/`--role`), it means the call the workflow makes with them. This keeps the rewritten scenarios short and still exact.
- **Install prompt (#242), README.md:**
  - Step 7 checks each `specwright-*` directory that has a downloaded counterpart for extra files. A `specwright-*` orphan passes only when the user chose in Step 4 to keep it, and Step 4 asks about the plan's `specwright-*` skill orphans on every path, a rerun after a completed swap included. Other directories in a skills directory (OpenSpec's `openspec-*`, `gitbutler`) are not Specwright's, and the check leaves them out.
  - Step 6 treats entries under `release.version_files.` as user data, like `pr.reviewers.` and `packs.`. `release.version_files` itself stays a compared key, offered whole when absent. The issue calls this key `release.files`, but the real key is `release.version_files`.
  - Step 6 says it keeps the user's values and comments as they are. It never rewrites a comment, so an older file can keep comments the template has since changed.
  - Step 8 says the interface is the line that holds only `interface <n>` in the installed `specwright-pr/SKILL.md`, and names no number, so the wording cannot go stale. That line already exists (`skills/specwright-pr/SKILL.md:14`), so the skill does not change.
  - The `vcs.sh` / `scripts_in_workspace` warning (README.md:129, README.md:549) says this is how an older user-level copy behaves. It no longer reads as a current part.
- Evals cover the #242 wording. No eval guards the sweep itself (S8).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

Wording only, retired script names replaced by `sw` commands:
- `change-finish`, `cost-tiers`, `design-review-gate`, `domain-packs`, `eval-grading`, `github-identity`, `packs`, `pr-evidence`, `pr-merge`, `pr-script-runtime`, `pr-watch`, `preship-review`, `project-planning`, `releases`, `review-routes`, `task-commits`, `user-tasks` and `vcs-backends`.

Wording and one added reading rule:
- `native-cli`: the retired-name wording is swept, and one requirement says how a command shown without its required options is read.

Wording and behaviour:
- `install-update`: the retired-name wording is swept. Entries under `release.version_files` become user data in the settings merge. Step 7's skills-directory check covers only `specwright-*` directories, and Step 4 settles orphans on every path. The settings merge says it never rewrites a comment.

## Impact

- `openspec/specs/**`: 77 reworded, 1 changed and 5 added requirements across 20 capabilities, through deltas that are synced at archive. Five requirements that cannot be reworded without changing what they assert are filed as issues instead (design D3).
- `README.md`: install prompt Steps 6, 7 and 8, plus the in-repo migration warning at lines 129 and 549.
- `evals/`: a new README test module, the README regexes that pin the edited wording (`evals/git-workflow/test_install_sw_warning.py`, `evals/git-workflow/test_instructions.py`), and `evals/suites.json` for the new test file.
- No code, skill or binary changes. Skills, the `sw` CLI and the settings template stay as they are.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Keep the name-map requirement

- **Choice:** keep "Retired script names map to sw commands" in `native-cli`, along with the history passages it supports.
- **Rejected:** removing it once the sweep is done. Archived changes, the README upgrade notes and older user-level copies still use the old names, and the map is what defines them.
- **Reversal cost:** low
- **Important:** yes, it binds future changes: the requirement is a contract later specs may lean on. The roadmap's exit criterion already settles it ("apart from the name-map requirement and the history it records").
- **Chosen by:** agent, following the roadmap exit criterion

### S2: Sweep boundary

- **Choice:** replace a retired name only where it is used as a current component. Keep the name map, history passages, real file names (eval modules, test files, `cli/tool/*.py`) and example file names in scenarios. A requirement whose meaning would change is filed as an issue and left out.
- **Rejected:** a blind textual replace, which would rewrite history and real file names. Fixing changed-meaning requirements here, which would turn a wording sweep into behaviour changes.
- **Reversal cost:** low
- **Important:** no. The wording stays equivalent through the name map, so nothing users see changes.
- **Chosen by:** agent

### S3: Widen the change to #242

- **Choice:** take in all five #242 items in this change.
- **Rejected:** a separate change. The sweep already edits the same install-update requirements and README wording.
- **Reversal cost:** low
- **Important:** yes, it changes behaviour users see in the install prompt.
- **Chosen by:** user ("widen the scope to include https://github.com/sh1ny/specwright/issues/242")

### S4: Stale settings comments (#242 item 5)

- **Choice:** Step 6 says it keeps the user's values and comments as they are and never rewrites a comment. This is wording only.
- **Rejected:** an opt-in comment refresh, which is new install behaviour that needs its own evals. Filing the item separately, which leaves the question open.
- **Reversal cost:** low
- **Important:** yes, it changes behaviour users see in the install prompt.
- **Chosen by:** user

### S5: Specify the #242 behaviour in install-update

- **Choice:** change the README prompt and add install-update requirements for the `release.version_files` user data, the Step 7 directory scope and the comments rule, with evals.
- **Rejected:** README wording only, which would leave the spec silent on rules the prompt follows.
- **Reversal cost:** low
- **Important:** yes, it binds future changes: settings-merge rules are a contract.
- **Chosen by:** user

### S6: Step 8 interface line

- **Choice:** reword README Step 8 only. The dedicated `interface 3` line already exists in `skills/specwright-pr/SKILL.md:14`, and `evals/cli/test_sw_interface_pin.py` reads it.
- **Rejected:** changing the skill, which would change a line the build and the evals read.
- **Reversal cost:** low
- **Important:** no. The interface contract stays the same, and only the prompt's description of it changes.
- **Chosen by:** agent

### S7: Narrow the sweep and add a reading rule

- **Choice:** after two REVISE rounds of the design review, add one `native-cli` requirement saying that a command shown without its required options means the workflow's call with them, and take the jj and GitButler archive-undo requirements out of the sweep as an issue.
- **Rejected:** spelling every required option out in each reworded scenario, which made the wording drift from the main text and kept the review finding new gaps. Rewriting the undo requirements here, which changes what they assert.
- **Reversal cost:** low
- **Important:** yes, it binds future changes: the reading rule applies to every spec that shows a shortened `sw` call.
- **Chosen by:** user ("Narrow + map")

### S8: No eval guards the sweep

- **Choice:** drop the sweep guard of D1 (`evals/runner/test_spec_retired_names.py`, built in group 2) and the exemption it needed in the older removed-script check. The milestone close checks the exit criterion by search instead. Found during apply: the guard holds the retired names as string literals, so the PR CI run failed the `runner` suite on all three OSes on `evals/runner/test_oracle_migration.py`.
- **Rejected:** keeping the guard and exempting it from the older check, which two design-review rounds found still let an executable use of a retired name through. Moving the names to JSON data files, which keeps a 900-line test and an allowlist every later change to a listed block must update by hand.
- **Reversal cost:** low. The guard is one file in the branch history.
- **Important:** no. The scripts are gone and the older check keeps every eval off them, so a retired name in a later spec misleads a reader but breaks nothing. Review can still catch it.
- **Chosen by:** user ("why do we need the new guard? To protect from something that doesn't exist anymore?"), reversing the planning-round choice in D1

## Release Notes

A patch release that updates wording and fixes the install prompt. The main specs now name the `sw` commands that replaced the retired shell scripts. The README install prompt no longer stops, asks or fails on a correct install. The skills and `sw` behave as before.

### Changed
- The main specs name `sw` commands (`sw vcs`, `sw as`, `sw pr`, `sw release` and others) where they named retired scripts. Behaviour is unchanged (#234).

### Fixed
- Step 7 of the install prompt checks only `specwright-*` skill directories, and Step 4 asks about orphaned `specwright-*` skills on every path, a rerun included. Step 6 treats `release.version_files` entries as user data and keeps the user's comments as they are. Step 8 names the interface line exactly. The in-repo migration warning now says `vcs.sh` is how an older copy behaves (#242).
