# Design

## Triage

| Trigger | Applies? | Evidence |
|---|---|---|
| T1 Components (new component, or 3+ with directed relationships) | no | One new README test module. The README prompt and the specs are existing text. |
| T2 State (persistent state, caches, 3+ state machine) | no | No state. |
| T3 Concurrency (background work, workers/isolates, async, retries) | no | None. |
| T4 Boundaries (data format, migration, shared interface, IPC, external) | yes | The settings merge's user-data rule is a contract with every project's `openspec/specwright.yaml`: README.md:432-436, openspec/specs/install-update/spec.md:347-348. |
| T5 Volume (grows without a fixed bound) | no | Nothing reads input that grows. |
| T6 Risk (security, money, data loss, unrecoverable user data) | no | Treating `release.version_files` entries as user data removes a prompt that could delete them. No new write. |

TIER: FULL

## Context

- **The name map.** The native-cli requirement "Retired script names map to sw commands" gives each retired script its `sw` command: openspec/specs/native-cli/spec.md:799-812. ADR 0040 calls it the reference for people who scripted the old names: docs/adr/0040-skills-call-the-projects-sw-directly.md:33.
- **Scale.** Before this change, 109 requirements in 21 capabilities named a retired script, about 292 times (counted with one regex over the 14 names of the name map). The deltas rewrite 77 of them in 20 capabilities. `install-update` changes one more (its update-completion scenario now allows kept orphans) and adds 4 requirements, and `native-cli` adds 1.
- **The removed-script check.** evals/runner/test_oracle_migration.py fails on any eval file whose string literals name a removed script, and skips only itself (eval-runner "Frozen-oracle evals are migrated before the cutover"). An eval that searches spec text for the retired names has to hold them as literals. The guard first built for this change did, and the PR CI run failed the `runner` suite on all three OSes for that reason (S8).
- **Strings `sw` still prints.** Some retired names are part of the output contract and are not stale wording:
  - `as.sh: unrepresentable …`: cli/lib/src/fence/fence.dart:588
  - `fit-subject.sh: could not rewrite …`: cli/lib/src/commit/fit_subject.dart:111
  - the `reviewers.py:` stderr prefix: cli/lib/src/pr/reviewers.dart:26
- **Header names are match keys.** `openspec validate` matches MODIFIED requirements and their scenarios by header. Renaming a `#### Scenario:` header failed validation during drafting, so every header keeps its old text, script names included.
- **Step 6 user data.** The README lists `pr.reviewers.`, `planning_store.reviewers.` and `packs.` as user data (README.md:432-436). The real key is `release.version_files`, not the `release.files` that #242 names. The template ships the entry `VERSION` (templates/openspec/specwright.yaml:216-217), and this repository adds `README.md` and `skills/*/SKILL.md` (openspec/specwright.yaml:136-139).
- **Step 7 skills check.** It requires that "nothing else is in them" (README.md:457-460). OpenSpec installs its own `openspec-*` skills into the same directories.
- **Step 8 interface line.** The line already exists, holding only `interface 3` (skills/specwright-pr/SKILL.md:14). The build and the evals read it as the single `interface <n>` line: evals/cli/test_sw_interface_pin.py:22, evals/cli/test_skill_probe.py:61. The README names "the `interface <n>` line" (README.md:520), and evals/git-workflow/test_install_sw_warning.py:37 pins that phrase.
- **The `vcs.sh` warning.** README.md:129-130 and README.md:549 describe what an older user-level copy does. The README tests pin the sentence: evals/git-workflow/test_instructions.py:2437 and :2449-2470, which also strips the exact phrase at :2466.
- **Pinned Step 6 and Step 7 wording.** Only the README evals pin the wording this change edits: test_instructions.py:2591-2594 pins "never compared, added or listed as removed" for `packs.`, and :1295-1298 pins the Step 7 uncommented-path wording. The tasks revise both so they check the general compared-path rule and its user-data and consent exemptions.
- **CI.** README edits run the `git-workflow`, `release` and `update/test_bootstrap.py` suites (evals/suites.json:17).

## Decisions

### D1: Check the sweep by search at the milestone close

- **Choice:** no eval guards the sweep. At the milestone close the agent searches the main specs for the 14 names of the name map and checks that every block it finds is in the **Allowlist inventory** below. The roadmap's exit criterion points to this inventory and names its five deferred entries (#244 to #248). The README half of the criterion is checked by evals/git-workflow/test_install_prompt_242.py on CI. An allowlist eval was built in group 2 and is removed in task 5.1 (S8).
- **Rejected:** the allowlist eval, `evals/runner/test_spec_retired_names.py`. It read the main specs, overlaid the active changes' deltas in archive order and compared every block naming a retired script with a fixed list of exact lines. It needs an exemption in the removed-script check, which two review rounds found still let an executable use through. It also makes every later change to a listed block update the list by hand, to protect wording only.
- **Reversal cost:** low. The eval is one file in the branch history.
- **Important:** no. It binds no later change.
- **Chosen by:** user during apply, reversing the planning-round choice of the allowlist eval

### D2: Fix #242 in the README prompt and keep its pinned phrases

- **Choice:**
  - Step 6 adds `release.version_files.` to the user-data list, keeping the entries' order. It also says the merge keeps the user's values and the comments of every key it keeps.
  - Step 7's key check names the user-data prefixes. It checks `release.version_files` by the rules of any compared key and none of its entries, so a project that maps only `package.json` passes (README.md:472-474), and so does one that declined the default in Step 6.
  - Step 7's skills check replaces "nothing else is in them" with the per-directory rule from the install-update delta. An orphan the user chose to keep in Step 4 (README.md:341-343) passes and is reported in Step 8 (README.md:490-493).
  - Step 4 asks about the plan's `specwright-*` skill orphans that this update does not install, on every path: after a new swap, and on a rerun that confirms a completed swap and skips `stage` and `swap`. It does so before Step 5, so an orphan the user now agrees to remove is gone before Step 7. Both resume directions change: README.md:322-325 (go on with Steps 5-7) and README.md:484-485 ("it goes straight to Steps 5-7") now go through the orphan question first.
  - The completion scenario of "Update stages the new version before it swaps it in" allows the orphans the user kept, so it no longer contradicts the Step 7 rule.
  - Step 8 says the interface is the line that holds only `interface <n>` and nothing else, below the paragraph in the installed `specwright-pr/SKILL.md`. It gives no number as an example, because evals/git-workflow/test_install_sw_warning.py:68-73 refuses a hard-coded `interface 3` in the check. The pinned phrase "`interface <n>` line in the installed `specwright-pr/SKILL.md`" stays as a substring.
  - The README evals add checks for the coupled rules:
    - a custom `release.version_files` mapping passes Step 7 without the template's entry;
    - a missing `release.version_files` gets the default, and a declined default still passes Step 7;
    - a kept key's comment is unchanged;
    - an obsolete key still needs consent before removal;
    - a kept orphan passes Step 7;
    - both swap paths, a new swap and a confirmed completed one, reach the orphan question before Step 5;
    - an orphan approved for removal that is still present blocks the stamp.
  - Two existing pins change with this wording, and the tasks revise them in the same commit: test_instructions.py:2591-2594 ("never compared, added or listed as removed" for `packs.`) and :1295-1298 (the Step 7 uncommented-path wording).
  - Both `vcs.sh` sentences say this happens with an older user-level copy from before 0.14.0, a version that still had `vcs.sh`. The phrase "older user-level copy stops every `vcs.sh` call with `scripts_in_workspace`" stays, because test_instructions.py:2466 strips it.
- **Rejected:** a second interface line or a changed format in `specwright-pr/SKILL.md`, because the build, the install and two evals read the current line.
- **Reversal cost:** low
- **Important:** yes, it changes behaviour users see in the install prompt.
- **Chosen by:** agent, carrying out S3 to S6

### D3: File the five requirements that cannot be swept as issues

- **Choice:** one issue each for the five requirements whose meaning would change. Their mentions stay in the main specs, listed as deferred in the Allowlist inventory, until those issues are fixed.
  - change-finish "finish.sh runs no network command": it scans a file `sw` does not have.
  - eval-runner "Changed paths select the suites": it uses example paths under `skills/*/scripts/`, which no longer exist.
  - pr-script-runtime "sw pr snapshot and sw pr reply keep the scripts' contracts": it runs the commands through shims that are gone.
  - vcs-backends "The archive undo plan uses jj on a jj repo" and "The archive undo plan uses GitButler on a GitButler repo": they assert commands that `finish.sh` ran, while `sw finish` prints `steps` and `after_rerun_steps` for the agent to run (openspec/specs/change-finish/spec.md:394-403). Saying steps changes what they assert, so they leave the sweep (D6).
- **Rejected:** rewriting them here, which would turn a wording sweep into behaviour changes that the proposal's S2 rules out.
- **Reversal cost:** low
- **Important:** no. Nothing changes for users, and the five are tracked.
- **Chosen by:** agent

### D4: Release as a patch

- **Choice:** bump to 0.39.1. The wording is unchanged in meaning, and the install prompt changes are fixes.
- **Rejected:** a minor bump. No feature, setting or workflow is added.
- **Reversal cost:** low
- **Important:** no. It follows the project's recorded versioning rule.
- **Chosen by:** agent

### D5: Where swept wording no longer matched sw, say what sw does

- **Choice:** some blocks named a script whose replacement differs in a way the old wording hides. Those blocks now state `sw`'s behaviour, which exists today and is tested:
  - The undo plan prints `steps` and `after_rerun_steps` (openspec/specs/change-finish/spec.md:394-403), so the touched change-finish block says steps.
  - The subcommands that read the download need `--download` (cli/lib/src/commands/update.dart:18-29).
  - The JSON error contract covers only the `sw pr` subcommands that `pr-pair.sh` carried (cli/lib/src/commands/pr.dart:49-70).
  - `--dir` comes before the `sw release` subcommand (cli/lib/src/release/commands.dart:127-134).
- **Rejected:** a literal name swap. It would make those requirements describe commands `sw` refuses, or a contract it never had.
- **Reversal cost:** low
- **Important:** no. It describes what `sw` already does, and users see no change.
- **Chosen by:** agent

### D6: Read a shortened command as the workflow's call, and narrow the sweep

- **Choice:** two rounds of the design review found reworded scenarios that show an `sw` command without an option it needs, so read literally they assert a usage stop. Each fix turned up the next. The change adds one `native-cli` requirement instead: a command shown without its required options (`--download`, `--code`, `--repo`/`--role`, the task and change options) means the call the workflow makes with them, and a usage stop is meant only where the text says the option is missing. The jj and GitButler undo blocks leave the sweep (D3).
- **Rejected:** spelling every option out in every reworded block, which grows the delta, drifts from the main text and kept finding new gaps. Rewriting the undo blocks here, which changes what they assert.
- **Reversal cost:** low. It is one requirement, and spelling the options out later stays possible.
- **Important:** yes, it binds future changes: every spec that shows a shortened `sw` call is read by it.
- **Chosen by:** user ("Narrow + map")

### D7: Pre-ship findings that changed what the specs say

- **Choice:** two reworded change-finish requirements now state what the workflow does, after the pre-ship review and design review round 8:
  - The undo plan's JSON always holds `steps` and `after_rerun_steps`, which may be empty (openspec/specs/change-finish/spec.md:395). Finish shows the `steps`, a non-empty `after_rerun_steps` and the warnings, as skills/specwright-finish/SKILL.md:74 does, not all the plan prints. The user approved this as a behaviour change.
  - `sw review archive-only` runs from the code checkout with `--dir` naming the planning repo, and a failure exits 1 with `git_error` (evals/review-routes/test_review_run.py:1619-1626), not 3. Ship runs `pr.validate` on any non-zero exit. The main text and skills/specwright-pr/SKILL.md said exit 3, so the skill line changes in task 6.1.
  - The test map names the tests that prove each part: the skill-text tests for ship's decision and finish's display, the classifier and planner tests for `sw`.
- **Rejected:** leaving the skill on exit 3. An agent following it would stop on exit 1 where the spec says validate runs.
- **Reversal cost:** low
- **Important:** no. Both match what `sw` and the skills already do, apart from the one skill line.
- **Chosen by:** user (the display), agent (the exit code, from the design review)

### Decision summary

| # | Decision | Choice | Rejected | Reversal cost | Important | Chosen by |
|---|---|---|---|---|---|---|
| S1 | Name-map requirement | Keep it and the history it records | Remove it | low | yes | agent |
| S2 | Sweep boundary | Current-component mentions only; keep history, output strings, real and example file names | Blind replace; fixing changed-meaning requirements | low | no | agent |
| S3 | Widen to #242 | Take all five items | A separate change | low | yes | user |
| S4 | Stale settings comments | Step 6 says comments are never rewritten | A comment refresh; a separate issue | low | yes | user |
| S5 | Specify #242 in install-update | README plus install-update requirements | README only | low | yes | user |
| S6 | Step 8 interface line | Reword the README only | Change the skill | low | no | agent |
| S7 | Narrow the sweep | Add a reading rule; move the undo blocks out | Spell every option out | low | yes | user |
| S8 | Sweep guard | No guard eval; search at the milestone close | Guard with an exemption in the older check; names in JSON data | low | no | user |
| D1 | Checking the sweep | Search the main specs at the milestone close | Allowlist eval with active-delta overlay | low | no | user |
| D2 | README #242 wording | Edit Steps 6-8 and the warnings, keeping pinned phrases | A new interface line in the skill | low | yes | agent |
| D3 | Unsweepable requirements | File five issues and list them as deferred | Rewrite them here | low | no | agent |
| D4 | Release | Patch 0.39.1 | Minor | low | no | agent |
| D5 | Swept wording that hid a difference | State sw's actual behaviour | Literal name swap | low | no | agent |
| D6 | Shortened commands | native-cli reading rule; undo blocks out of the sweep | Spell every option out; rewrite the undo blocks | low | yes | user |
| D7 | Pre-ship spec findings | State finish's display and any non-zero archive-only exit; fix the skill line | Keep exit 3 in the skill | low | no | user, agent |

## Assumptions

None. The pins on the edited Step 6 and Step 7 wording were checked by searching the repository (see Context).

## Carried constraints

- **C2:** Entries under `release.version_files.` are user data in the settings merge, while the `release.version_files` key itself is still compared. Kind: invariant. Destination: spec: specs/install-update/spec.md → Requirement: The settings merge treats version-file entries as user data

<!-- ===== LIGHT tier ends here. ===== -->

## Diagrams (FULL)

```mermaid
flowchart LR
  U[user specwright.yaml] --> M{Step 6 merge}
  T[downloaded template] --> M
  M -->|compared key, missing| A[add with default and comment]
  M -->|compared key, gone upstream| Q[ask before removing]
  M -->|"pr.reviewers.*, planning_store.reviewers.*, packs.*, release.version_files.*"| K[keep as is, never listed]
  M -->|existing key's comment| C[keep the user's comment]
```

## State & Ownership (FULL)

| State | Owner (sole writer) | Lifetime | Invalidation / rebuild | Authoritative copy |
|---|---|---|---|---|
| The user's `openspec/specwright.yaml` | The user, plus the Step 6 merge for added keys only | Permanent | Never rebuilt | The user's file |

## Failure & Visibility (FULL)

| Component | Fails / dies mid-operation → | Recovery | Retry safe? | Who finds out |
|---|---|---|---|---|
| Step 6 merge | The agent lists a user-data entry as removed | The user declines the removal | yes | The user, at the Step 6 question |
| Step 7 check | A stale `specwright-*` file or directory is found | The install stops before the stamp | yes | The user, in the Step 7 report |

## Resource Bounds (FULL)

| Queue / buffer / cache / transfer | Bound | At the bound | Timeout | At 10x / 100x |
|---|---|---|---|---|
| None | Not applicable | Not applicable | Not applicable | Not applicable |

## Flow & State Gaps (FULL)

- **A later change adds a retired name to a spec.** No check fails. Pre-ship review, PR review and the milestone-close search (D1) can catch it, and the name map still defines it.

## Mechanism Ledger (FULL)

| Mechanism | Built? | Why (harm nobody catches / expensive later) | Evidence that would change the call |
|---|---|---|---|
| Allowlist guard | no | The scripts are gone and the removed-script check keeps every eval off them, so a retired name in a later spec misleads a reader but breaks nothing; review and the milestone-close search can catch it (S8) | A later change ships a retired name in a spec that review missed |
| Check of README, skills and archived changes for retired names | no | History and upgrade notes are meant to name them; the scope is the main specs | A retired name reported as a current part outside the specs |
| Check of the Step 7 wording in code | no | The install prompt is text an agent follows, and the README evals pin it | An `sw update` subcommand that runs the Step 7 check |

## Allowlist inventory

Each block that keeps a retired name after this change, with the number of times each name occurs in it, headers included. The milestone close checks the main specs against this list (D1). `kept` entries are history, the name map, an output string `sw` still prints, a real file name, or a header kept as a match key.

| Capability | Requirement | Names (count) | Kind |
|---|---|---|---|
| change-finish | finish.sh runs no network command | as.sh 1, finish.sh 5 | deferred (#244) |
| change-finish | The undo plan runs in the project's sw | finish.sh 1 | kept |
| change-finish | finish.sh finds the project from --code, then --dir | finish.sh 1 | kept |
| change-finish | Undo steps do what the old script did | vcs.sh 1 | kept |
| change-finish | Fixed undo-plan defects are exceptions to the script's refusals | finish.sh 5 | kept |
| eval-runner | Changed paths select the suites | finish.sh 1, release.sh 1 | deferred (#245) |
| eval-runner | A stopped test file's nested sessions are stopped too | bounded.py 2 | kept |
| eval-runner | Frozen-oracle evals are migrated before the cutover | as.sh 1, bounded.py 1, sw-path.sh 1, vcs.sh 1 | kept |
| github-identity | sw as keeps as.sh's contract | as.sh 5 | kept |
| github-identity | sw as verifies the token for its login | as.sh 1 | kept |
| install-update | An install whose VCS steps need a missing sw says so | sw-path.sh 1, vcs.sh 1 | kept |
| install-update | sw update recovers journals that older update scripts left | update.sh 3 | kept |
| native-cli | sw run --bounded keeps bounded.py's command-line contract | bounded.py 2 | kept |
| native-cli | Arguments reach native executables unchanged | bounded.py 1 | kept |
| native-cli | JSON input that is not plain JSON is refused | reviewers.py 1 | kept |
| native-cli | A launch-site allowlist guards process starts | as.sh 2, pr-pair.sh 1, pr-reply.sh 1, pr-snapshot.sh 1, release.sh 1, review-run.sh 1, update.sh 1, vcs.sh 2 | kept |
| native-cli | Long Windows arguments reach native tools whole | as.sh 1 | kept |
| native-cli | Skills run sw directly | as.sh 1, finish.sh 1, fit-subject.sh 1, pr-pair.sh 1, pr-reply.sh 1, pr-snapshot.sh 1, release.sh 1, review-run.sh 1, sw-path.sh 1, task-cover.sh 1, update.sh 1, vcs.sh 1 | kept |
| native-cli | Retired script names map to sw commands | as.sh 1, bounded.py 1, finish.sh 1, fit-subject.sh 1, pr-pair.sh 1, pr-reply.sh 1, pr-snapshot.sh 1, release.sh 1, review-run.sh 1, reviewers.py 1, task-cover.sh 1, update.sh 1, vcs.sh 2 | kept |
| native-cli | Printed commands name sw | as.sh 1, vcs.sh 2 | kept |
| pr-evidence | A snapshot names the reviewer rules it used | reviewers.py 1 | kept |
| pr-script-runtime | Unexpected failures keep the JSON error contract | pr-pair.sh 1 | kept |
| pr-script-runtime | Network commands have a deadline | as.sh 1, pr-pair.sh 1 | kept |
| pr-script-runtime | sw pr snapshot and sw pr reply keep the scripts' contracts | pr-reply.sh 1, pr-snapshot.sh 1, reviewers.py 2 | deferred (#246) |
| pr-script-runtime | Watch claims and head records stay shared across implementations | pr-snapshot.sh 2 | kept |
| pr-script-runtime | The ported pr-pair subcommands keep the script's contracts | as.sh 1, pr-pair.sh 2, vcs.sh 1 | kept |
| pr-script-runtime | sw pr reviewers keeps the evaluator's contract | reviewers.py 4 | kept |
| pr-script-runtime | Snapshots evaluate reviewers through sw | reviewers.py 4 | kept |
| pr-script-runtime | sw pr ignores an inherited GH_REPO | pr-pair.sh 1 | kept |
| pr-script-runtime | Fixed snapshot defects are exceptions to the scripts' contract | pr-snapshot.sh 1 | kept |
| releases | The release summary comes from the bumping change | release.sh 3 | kept |
| releases | Release operations run in the project's sw | release.sh 2 | kept |
| review-routes | Review operations run in the project's sw | review-run.sh 2 | kept |
| task-commits | Commit tooling runs in the project's sw | fit-subject.sh 1, task-cover.sh 1 | kept |
| task-commits | task-cover.sh finds the project from --code | task-cover.sh 1 | kept |
| task-commits | sw commit task-cover keeps task-cover.sh's contract | task-cover.sh 4 | kept |
| task-commits | sw commit fit-subject keeps fit-subject.sh's contract | fit-subject.sh 4 | kept |
| vcs-backends | sw vcs keeps vcs.sh's output and exit-code contract | vcs.sh 2 | kept |
| vcs-backends | sw vcs reads settings and fences identity in process | as.sh 1, pr-pair.sh 1 | kept |
| vcs-backends | sw vcs documents keep their values and refuse non-UTF-8 names | vcs.sh 1 | kept |
| vcs-backends | Fixed commit defects are exceptions to the backends' unchanged outputs | vcs.sh 1 | kept |
| vcs-backends | The archive undo plan uses jj on a jj repo | finish.sh 2 | deferred (#247) |
| vcs-backends | The archive undo plan uses GitButler on a GitButler repo | finish.sh 1 | deferred (#248) |

## Risks / Trade-offs

- [The swept wording drifts from what `sw` accepts] → Every rewritten command was checked against cli/lib/src during drafting. Pre-ship review sees the whole delta.
- [78 MODIFIED blocks make a large diff] → Wording only. `openspec validate --strict` covers structure, and `review.max_diff_kb` is 1400.
- [README phrase pins break] → D2 keeps the pinned phrases, and the README tasks update the regexes in the same group.

## ADRs

- **In force, constraining this change:** 0040 (skills call `sw` directly; the name map), 0027 (one native binary), 0042 (interface 3).
- **To record during apply:** none.
