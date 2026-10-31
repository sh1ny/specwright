# Review

## Metadata

- **Round:** 6
- **Prior round:** Round 5: APPROVE_WITH_CHANGES (no Critical, 1 Moderate on `core.autocrlf=true`). Its 3 Required Changes were re-checked and recorded as applied. That verdict was voided during apply, when `openspec validate --specs --strict` (evals/git-workflow/test_specs_strict.py) failed on the main specs after archive because the MODIFIED requirement "The backend is chosen per repo" was over 500 characters. The author split the requirement. This is a new full round.
- **Reviewer:** fresh-context subagent (Claude Code specwright-reviewer)
- **Reviewed:**
  - The amendment since round 5: `git diff -- openspec/changes/add-gitbutler-backend/specs openspec/changes/add-gitbutler-backend/tasks.md`.
  - Current artifacts under `openspec/changes/add-gitbutler-backend/`: specs/vcs-backends/spec.md (full read of the split region and every requirement's body length), tasks.md (Test map and group 3), proposal.md and design.md (every mention of `unsupported_vcs`, `unsupported_combination` and the requirement names), review.md (round 5 record).
  - Main spec `openspec/specs/vcs-backends/spec.md` (the requirement headers and the current text of "The backend is chosen per repo", lines 9-23).
  - `evals/git-workflow/test_specs_strict.py` (what the failing check validates).
  - `openspec validate add-gitbutler-backend --strict`: valid.
  - Excluded as instructed: `openspec/architecture.md` and `docs/adr/0018-*.md` in the working tree (task 1.5's implementation).
  - Project skills named in the request: none.

### The split, checked for behaviour change

- **Normative text is unchanged.** The removed sentence from the MODIFIED requirement ("`planning_store.vcs: gitbutler` SHALL stop with `unsupported_vcs`, and `vcs: gitbutler` with `finish` other than `pr` (absent included, since it defaults to `local`) SHALL stop with `unsupported_combination`; both stops SHALL come from the first step that reads the branch or writes, before any write in either repo.") reappears word for word as the new ADDED requirement's body. The only edit is that the semicolon became a full stop and "both" became "Both". No SHALL was dropped, weakened or added.
- **No scenario was lost or edited.** The three scenarios "GitButler store", "GitButler with a local finish" and "GitButler with no finish setting" moved under the new requirement with identical WHEN and THEN lines. The MODIFIED requirement keeps "Unset means Git", "Store keeps its own backend", "GitButler code repo with a Git store" and "Unknown value". The seven scenarios are the same as round 5. Each requirement still has a failure scenario: "Unknown value" for the MODIFIED one, and all three for the ADDED one.
- **The MODIFIED requirement still replaces the main one correctly.** The header matches `openspec/specs/vcs-backends/spec.md:9` exactly. Against the main text, it widens `vcs` to `gitbutler`, keeps the store at `git | jj`, and updates "Unknown value" to name `gitbutler` among the accepted values. That is the round 5 content.
- **No name collision.** No main-spec requirement is titled "GitButler runs only for the code repo with `finish: pr`", so archive appends it without conflict.
- **The strict-validation cause is fixed.** Every requirement body in the delta is now at or under 469 characters. The two halves of the split are 324 and 316. The change validates with `--strict`.

### The rest of the artifacts against the split

- **tasks.md.** The three Test map rows now name the new requirement. Test files, test names and the red status are unchanged. Task 3.1 lists the new requirement among the red rows to write. Task 3.2 still implements both stops, and its text was unchanged and stays correct. No other row or task names the old requirement for these scenarios.
- **proposal.md (lines 16-17) and design.md (lines 69-70, 361-362, 391)** describe the two stops by behaviour and error code, not by requirement title. Their wording ("a `finish` other than `pr`", "unless `finish` is exactly `pr`", absent counts as `local`, `planning_store.vcs: gitbutler` → `unsupported_vcs`) matches the ADDED requirement. Nothing disagrees.
- **Round 5's conclusions** (D5 steps 6-8, D8's base, the pull fence, the autocrlf Risk and its three applied Required Changes) depend on design.md and the other tasks, which this amendment did not touch. They stand as recorded.

## Findings

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

None. (A wording nit carried over from earlier rounds, not introduced here: the "GitButler store" scenario says "reads a branch" while the requirement says "reads the branch". It has no behavioural consequence.)

## Verdict

The split is a pure restructuring. The normative sentence and its three scenarios move intact to a new ADDED requirement, the MODIFIED requirement keeps its failure scenario, both fit the 500-character limit, and the Test map and task 3.1 follow the new name. Proposal and design describe the same behaviour and still agree. Round 5's findings were resolved and nothing they depend on changed.

VERDICT: APPROVE

## Required Changes

None.

CHANGES_APPLIED: n/a

## Rebuttals
