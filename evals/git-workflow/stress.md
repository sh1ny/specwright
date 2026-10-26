# Stress tier record

Each section records one run of the stress-marked evals (`"stress"` in `evals.json`) on two configurations, compared by `tiers.py`, plus a dispatch trial of the cheap tier. The stress tier is a wording diagnostic, not a CI gate: a difference is either fixed in the skill or agent text and re-run, or recorded here as a model limit with its evidence. A later run adds a new dated section above this one's.

## 2026-10-26: add-cheap-tier (0.8.0)

### Models

- `base`: the default tier, `claude-opus-5-5` (the session model; its subagents ran without a model override).
- `haiku`: the same prompts with the subagent model set to `haiku`. In the dispatch trial, the Haiku subagent messages report `claude-haiku-5-5`.

Each run built its fixture with `python evals/git-workflow/fixtures.py <eval> <run>/repo` and got the same prompt in both configurations: the skill paths, the working directory, `source eval.env`, no human available (questions go in the report), and the final message saved to `outputs/report.md`.

The harness refused some subagent writes of `outputs/report.md` ("subagents should return findings as text"). In those runs the agent returned the message as its reply, and it was saved verbatim as `report.md`: four Haiku runs (implementer packet, apply, watch with `merge: user`, release-auto in iteration 1) and one `base` run (release-auto in iteration 2).

### Pass rates

Final state, with each eval taken from its last iteration:

| Eval | Stress kind | Iteration | base | haiku |
|---|---|---|---|---|
| `eval-apply-three-tasks` | light-apply | 1 | 11/11 | 11/11 |
| `eval-implementer-light-packet` | implementer | 1 | 8/8 | 8/8 |
| `eval-watch-merge-default-user` | watch | 1 | 6/6 | 6/6 |
| `eval-watch-agent-merge` | watch | 2 | 9/9 | 9/9 |
| `eval-agent-merge-release-auto` | watch | 3 | 16/16 | 16/16 |

The iterations:

1. All five evals. Graded first with the grader as committed:
   - apply: 11/11 in both configurations;
   - implementer packet: base 7/8, haiku 8/8;
   - watch, `merge: user`: 6/6 in both;
   - watch-agent-merge: 8/9 in both;
   - release-auto: 3/16 in both.

   After the two grader fixes below, the implementer packet is 8/8 in both configurations and watch-agent-merge is base 9/9, haiku 8/9.
2. watch-agent-merge and release-auto re-run, after the wording fix and a first fixture attempt:
   - watch-agent-merge: 9/9 in both;
   - release-auto: still 3/16 in both, because the first fixture attempt was wrong (see below).
3. release-auto re-run on the corrected fixture: 16/16 in both.

### `tiers.py`

Iteration 1, as first graded (exit 1):

```json
{
  "base_config": "base",
  "cheap_config": "haiku",
  "evals": {
    "eval-apply-three-tasks": {"base": 1.0, "cheap": 1.0},
    "eval-watch-agent-merge": {"base": 0.89, "cheap": 0.89},
    "eval-watch-merge-default-user": {"base": 1.0, "cheap": 1.0},
    "eval-agent-merge-release-auto": {"base": 0.19, "cheap": 0.19},
    "eval-implementer-light-packet": {"base": 0.88, "cheap": 1.0}
  },
  "differences": [
    {
      "eval": "eval-implementer-light-packet",
      "base": 0.88,
      "cheap": 1.0,
      "pass_only_base": [],
      "pass_only_cheap": ["The report gives red evidence: a failing run before the implementation"]
    }
  ],
  "missing": []
}
```

Final, over the last iteration of each eval (exit 0):

```json
{
  "base_config": "base",
  "cheap_config": "haiku",
  "evals": {
    "eval-apply-three-tasks": {"base": 1.0, "cheap": 1.0},
    "eval-watch-agent-merge": {"base": 1.0, "cheap": 1.0},
    "eval-watch-merge-default-user": {"base": 1.0, "cheap": 1.0},
    "eval-agent-merge-release-auto": {"base": 1.0, "cheap": 1.0},
    "eval-implementer-light-packet": {"base": 1.0, "cheap": 1.0}
  },
  "differences": [],
  "missing": []
}
```

### Differences and failures, accounted for

- **`eval-implementer-light-packet`: red evidence, base only (the one difference `tiers.py` listed). A grader false negative.** The base report did give red evidence:

  > `python -m unittest -q` after adding test_greet_named and test_greet_empty → FAILED (errors=2): `AttributeError: module 'greet' has no attribute 'greet'`

  The negation filter matched the "no" inside the quoted error. Fix: `grade.py`'s `evidence_lines` ignores negations inside backticked spans. Test: `test_negation_inside_quoted_error_text_still_counts_as_red`.

- **`eval-watch-agent-merge`: the roadmap offer. Base: a grader false negative.** The base report asked:

  > Shall I run `specwright-roadmap` **close** for M2 (run login: eval-bot)?

  The emphasis put four characters between `roadmap` and `close`, one more than the binding allows. Fix: `roadmap_offer` drops emphasis markup first. Test: `test_mode_in_emphasis_after_the_backticked_command_is_bound`.

- **`eval-watch-agent-merge`: the roadmap offer. Haiku: a wording gap, fixed.** Haiku read "offer one `specwright-roadmap` mode" as a label and wrote a statement, not a question:

  > Next: offer `specwright-roadmap` close for milestone M2 (Now: "Friendly greetings") ...

  Fix in `skills/specwright-pr/SKILL.md`, cleanup's **Next step**: "Ask the user as a question (`Run specwright-roadmap close for M2?`); a line that only names the mode is not an offer." Test: `test_cleanup_offers_one_roadmap_mode_after_an_agent_merge`. In the iteration-2 re-run, both configurations passed. Haiku's report now ends:

  > Question for the user (not run, since no human is available): Run specwright-roadmap close for M2?

- **`eval-agent-merge-release-auto`: 3/16 in both configurations. A fixture defect, older than this change.**
  - The cause: #102 added watch's version check, `git fetch --no-tags origin main` before a merge request. But the release fixture (#92) held `fetch` back until the merge was logged, and its bare origin already holds the squash. Both models stopped at the failed fetch and correctly did not merge.
  - The first attempt ungated `fetch` (iteration 2). It exposed the squash on origin's main before the merge: the check refused (`version_not_ahead_of_main`), and both models again correctly stopped.
  - The fix: `fixtures.py` gives the gated fixture `ob-pre.git`, origin before the merge, and the shim serves a pre-merge `fetch` from it. Test: `test_agent_fixture_serves_the_pre_merge_main_to_the_version_checks_fetch`.
  - Iteration 3: 16/16 in both configurations.

No model limit was recorded: after these fixes, no difference remains.

### Dispatch trial

Two scratch projects, `trial/on` and `trial/off`, were built from the `eval-apply-three-tasks` fixture: a LIGHT `add-greeting` change with 3 tasks in 2 groups. Specwright was installed from this branch into each project's `.claude/`. `trial/on` set `cheap_tier.enabled: true`, and `trial/off` left it unset. Each ran `claude -p "/opsx:apply add-greeting" --output-format stream-json --verbose` as a new session. Both projects were deleted afterwards.

**Tier on.** Parent model `claude-opus-5-5`.

- The tier call:

  ```
  bash .claude/skills/specwright-pr/scripts/pr-pair.sh tier --code "$(pwd)"
  → {"ok": true, "cheap_tier": true}
  ```

- Dispatches (parent `Agent` tool uses):

  ```
  subagent_type: specwright-implementer-light   description: Group 1 greeting functions
  subagent_type: specwright-implementer-light   description: Group 2 README docs
  ```

- Every subagent message (parent_tool_use_id set) reports `"model": "claude-haiku-5-5"`: 24 of 24 messages.
- The orchestrator re-verified before each commit:
  - before 1.1: `python -m unittest -q test_greet.GreetTests.test_greet_named test_greet.GreetTests.test_greet_empty`, then `python -m unittest -q`;
  - before 1.2: `python -m unittest -q`;
  - before 2.1: `grep -n -E 'greet\(|farewell\(' README.md`.
- Result: 3/3 tasks done; commits for the plan, 1.1, 1.2 and 2.1; tree clean; pre-ship review (codex) found nothing. The 1.1 commit only ticks the task, because 1.1 and 1.2 change the same files, which go with the later task.

**Tier unset.** Parent model `claude-opus-5-5` throughout.

- The tier call returned `{"ok": true, "cheap_tier": false}`.
- No `Agent` tool use: the small-group clause (tier off) let the orchestrator implement the three small groups inline. In its words:

  > The cheap-model implementer was off, so I did these small edits myself.

- Dispatch is unchanged from before this change: no light agent and no Haiku model. For larger groups the unchanged rule dispatches `specwright-implementer`; this change has none.

**Watch wakes.** No real watch ran during the trial (`finish: local`), so there are no wake counts with and without the filter. The filter's behaviour is covered by `evals/pr-pair/test_pr_snapshot.py` (`TestUntilAttention`).
