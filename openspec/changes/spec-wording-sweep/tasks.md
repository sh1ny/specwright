# Tasks

## Test map

The 18 wording-only capabilities and the reworded `install-update` and `native-cli` blocks keep their behaviour. Their scenarios start `green` on the tests that already cover them, and task 5.1 confirms them on PR CI. The new and changed `install-update` scenarios start `red` in one new README test module. The `native-cli` reading rule has no code path and maps to strict validation. The sweep guard of design D1 checks the exit criterion and has no scenario row.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| change-finish → Finish offers a release once the change is on main | Untagged version after a PR merge | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → Finish offers a release once the change is on main | Auto release | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → Finish offers a release once the change is on main | An earlier version was left untagged | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → Finish offers a release once the change is on main | Version already tagged | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → Finish offers a release once the change is on main | Releases disabled | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → Finish offers a release once the change is on main | Auto publish fails | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → Local finish lists untagged versions from local tags | Local finish with a github.com origin and no login | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → A deferred archive's undo is planned by a script that runs nothing | Deferred archive found | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → A deferred archive's undo is planned by a script that runs nothing | Plan run on a dirty unrelated path in a resume on main | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → A deferred archive's undo is planned by a script that runs nothing | No archive of the change | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → A deferred archive's undo is planned by a script that runs nothing | Branch moved after the plan | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → A deferred archive's undo is planned by a script that runs nothing | A jj plan with an unsnapshotted edit | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → A deferred archive's undo is planned by a script that runs nothing | A jj plan with a pending Git ref import | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → An archive-only push skips the code validate | Archive of a reviewed head | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → An archive-only push skips the code validate | Store-backed archive | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → An archive-only push skips the code validate | Archive commit with other files | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → An archive-only push skips the code validate | No ready head | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| change-finish → An archive-only push skips the code validate | Check fails to run | evals/finish/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| cost-tiers → The cheap tier is off unless enabled | Unset leaves dispatch unchanged | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| cost-tiers → The cheap tier is off unless enabled | An unrecognised value is off and reported | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| cost-tiers → The cheap tier is off unless enabled | The section is not a map | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| cost-tiers → The cheap tier is off unless enabled | Another setting is invalid | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| cost-tiers → The cheap tier is off unless enabled | A yes is off and reported | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| cost-tiers → The cheap tier is off unless enabled | The setting cannot be read | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| cost-tiers → Reviews and orchestration never move to the cheap tier | Design review with the tier on | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| cost-tiers → Reviews and orchestration never move to the cheap tier | A LIGHT change's pre-ship review | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| design-review-gate → A deferred review never ships code | Apply on a deferred change | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| design-review-gate → A deferred review never ships code | Archive on a deferred change | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| design-review-gate → A deferred review never ships code | Archive ran anyway | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| design-review-gate → A deferred review never ships code | Deferred archive already committed | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| design-review-gate → A deferred review never ships code | Bulk archive that included a deferred change | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| design-review-gate → A deferred review never ships code | Deferral with no target | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| domain-packs → The download ships the ui-prototyping, gamedev and godot packs | The shipped packs pass pack-check | evals/packs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| domain-packs → The download ships the ui-prototyping, gamedev and godot packs | gamedev without its shared pack | evals/packs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| domain-packs → The download ships the ui-prototyping, gamedev and godot packs | godot on its own | evals/packs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| eval-grading → Every seeded PR body for an issue check has a recorded rendering | Finish fixtures' body | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| eval-grading → Every seeded PR body for an issue check has a recorded rendering | A new fixture body without a recording | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → Main refreshes and pulls from GitHub are fenced | Cleanup pull after merge | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → Main refreshes and pulls from GitHub are fenced | Branch gate fetch over SSH | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → Main refreshes and pulls from GitHub are fenced | Origin that pushes to a fork | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → Main refreshes and pulls from GitHub are fenced | Post-merge pull refused | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → The trailing-dot host is github.com | Token in a trailing-dot URL | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → The trailing-dot host is github.com | Trailing-dot URL argument or rewrite | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → The trailing-dot host is github.com | Credential-free trailing-dot URL | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → The trailing-dot host is github.com | Look-alike host | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → The trailing-dot host is github.com | Trailing-dot store remote | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → Unfenced git keeps the caller's enterprise host settings | Enterprise store read by rounds | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → Unfenced git keeps the caller's enterprise host settings | Variables were unset | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| github-identity → Unfenced git keeps the caller's enterprise host settings | Fenced calls stay on github.com | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Every backend takes in-repo and user-level targets | In-repo target for a GitButler project | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Every backend takes in-repo and user-level targets | User-level target for a GitButler project | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Enabled packs' skills are installed with Specwright's own | A pack's skills are installed | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Enabled packs' skills are installed with Specwright's own | An interrupted pack install is recovered | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Enabled packs' skills are installed with Specwright's own | An interrupted pack removal is recovered | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Enabled packs' skills are installed with Specwright's own | A pack that fails its checks installs nothing | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Pack lines are merged by prefix and verified through OpenSpec | Lines reach their artifacts | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Pack lines are merged by prefix and verified through OpenSpec | A missing, duplicated or stale line | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Pack lines are merged by prefix and verified through OpenSpec | A removed pack's lines after a rerun past the swap | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Pack lines are merged by prefix and verified through OpenSpec | Hand-written lines of a pack the project never enabled | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Pack documents are created by an idempotent step after the stamp | Documents after a finished install | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Pack documents are created by an idempotent step after the stamp | Interrupted document creation | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → An install whose VCS steps need a missing sw says so | A binary of the right version and an old interface | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → An install whose VCS steps need a missing sw says so | An older supported tag | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → An install whose VCS steps need a missing sw says so | The interface named in prose and on its own line | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → An install whose VCS steps need a missing sw says so | main install with no binary | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → An install whose VCS steps need a missing sw says so | Binary of another version at the path | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → An install whose VCS steps need a missing sw says so | main install with a matching binary already placed | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → An install whose VCS steps need a missing sw says so | Older tag whose scripts need no sw | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → An install whose VCS steps need a missing sw says so | Tagged install with sw placed | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → An install whose VCS steps need a missing sw says so | Tagged install whose binary then fails the final check | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → sw update carries every update subcommand | A workflow update through sw update | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → sw update carries every update subcommand | A refusal keeps its code | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → sw update carries every update subcommand | A usage error | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → sw update needs no bash or Python | Install and update with failing interpreters first on PATH | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → sw update needs no bash or Python | Interrupted swap recovered with failing interpreters | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → sw update needs no bash or Python | A jj store read in process | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Update stages the new version before it swaps it in | Update completes | evals/git-workflow/test_install_prompt_242.py | test_update_completes_allows_kept_orphans | green |
| install-update → Update stages the new version before it swaps it in | Interrupted before the swap | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → Update stages the new version before it swaps it in | Staged copy fails verification | evals/update/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| install-update → The settings merge treats version-file entries as user data | A project's own version files survive an update | evals/git-workflow/test_install_prompt_242.py | test_step6_version_files_entries_are_user_data | green |
| install-update → The settings merge treats version-file entries as user data | A project without the template's entry | evals/git-workflow/test_install_prompt_242.py | test_step7_key_check_skips_version_files_entries | green |
| install-update → The settings merge treats version-file entries as user data | A project without version_files accepts the default | evals/git-workflow/test_install_prompt_242.py | test_step6_offers_version_files_mapping_whole | green |
| install-update → The settings merge treats version-file entries as user data | A project without version_files declines the default | evals/git-workflow/test_install_prompt_242.py | test_step7_passes_declined_version_files | green |
| install-update → The settings merge never rewrites a comment | A stale comment on a kept key | evals/git-workflow/test_install_prompt_242.py | test_step6_keeps_comments_of_kept_keys | green |
| install-update → The settings merge never rewrites a comment | A missing key is added with its comment | evals/git-workflow/test_install_prompt_242.py | test_step6_copies_comment_for_accepted_key | green |
| install-update → The settings merge never rewrites a comment | A key removed upstream still needs consent | evals/git-workflow/test_install_prompt_242.py | test_step6_obsolete_key_needs_consent | green |
| install-update → Step 7 checks only Specwright's skill directories | OpenSpec skills beside Specwright's | evals/git-workflow/test_install_prompt_242.py | test_step7_skills_check_ignores_other_directories | green |
| install-update → Step 7 checks only Specwright's skill directories | An extra file inside a Specwright directory | evals/git-workflow/test_install_prompt_242.py | test_step7_skills_check_fails_on_extra_file | green |
| install-update → Step 7 checks only Specwright's skill directories | An orphan the user kept | evals/git-workflow/test_install_prompt_242.py | test_step7_kept_orphan_passes | green |
| install-update → Step 7 checks only Specwright's skill directories | An orphan the user agreed to remove is still there | evals/git-workflow/test_install_prompt_242.py | test_step7_approved_orphan_still_present_blocks_stamp | green |
| install-update → Step 4 settles the plan's orphans on every path | A rerun that removes an orphan kept before | evals/git-workflow/test_install_prompt_242.py | test_step4_resume_removes_orphan_before_step5 | green |
| install-update → Step 4 settles the plan's orphans on every path | A rerun that keeps it again | evals/git-workflow/test_install_prompt_242.py | test_step4_resume_kept_orphan_reported | green |
| native-cli → sw starts external tools without a shell | Ported commands with failing shells first on PATH | evals/cli/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| native-cli → sw starts external tools without a shell | An absolute-path shell is not used either | evals/cli/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| native-cli → sw starts external tools without a shell | A fenced shell command the caller asked for | evals/cli/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| native-cli → Tool lookup, exit status and stdin keep their contract | A tool found on PATH gets its stdin | evals/cli/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| native-cli → Tool lookup, exit status and stdin keep their contract | A relative lookup resolves in the call's directory | evals/cli/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| native-cli → Tool lookup, exit status and stdin keep their contract | A fenced batch command keeps the caller's stdio | evals/cli/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| native-cli → Tool lookup, exit status and stdin keep their contract | A missing tool | evals/cli/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| native-cli → Tool lookup, exit status and stdin keep their contract | A tool ended by a signal | evals/cli/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| native-cli → A command shown without its required options means the workflow's call | A shortened call | n/a | `openspec validate spec-wording-sweep --strict` | n/a: a rule for reading spec text; no code path runs it, and strict validation checks its form |
| native-cli → A command shown without its required options means the workflow's call | A missing option named on purpose | n/a | `openspec validate spec-wording-sweep --strict` | n/a: a rule for reading spec text; no code path runs it, and strict validation checks its form |
| packs → A pack is a directory with a JSON manifest | A valid manifest is accepted | evals/packs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| packs → A pack is a directory with a JSON manifest | Malformed or unsupported manifests are refused | evals/packs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| packs → pack-check reports in one JSON document | All packs pass | evals/packs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| packs → pack-check reports in one JSON document | A named pack is missing | evals/packs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| packs → Packs are refused on a planning store in v1 | Repo-local project with packs | evals/packs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| packs → Packs are refused on a planning store in v1 | Store-backed project with packs | evals/packs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A reply is posted only for the revision that was judged | Item unchanged | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A reply is posted only for the revision that was judged | Reviewer edited the finding during the fix | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A reply is posted only for the revision that was judged | Item cannot be read | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A reply is posted only for the revision that was judged | Reply from an older session | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → Clipped items are read in full before they are judged | Finding after the cut | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → Clipped items are read in full before they are judged | Full body cannot be read | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → Clipped items are read in full before they are judged | Unknown item id | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A reply is never posted without its body | Body file present | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A reply is never posted without its body | Body file missing | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A reply is never posted without its body | Body file empty | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A reply is never posted without its body | Body file unreadable | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A bad report rule stops the snapshot | Bad rule | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A bad report rule stops the snapshot | Unknown key | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A bad report rule stops the snapshot | Python-only syntax is refused | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A bad report rule stops the snapshot | Sha pattern without a capture group | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → Reviewer settings reach the snapshot as a file | Policy writes main's reviewers | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → Reviewer settings reach the snapshot as a file | Old flag | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → Reviewer settings reach the snapshot as a file | Missing file | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → Reviewer settings reach the snapshot as a file | Unwritable state directory | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → Reviewer settings reach the snapshot as a file | Regex characters in a rule | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A snapshot names the reviewer rules it used | Wait started with the work tree's rules | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A snapshot names the reviewer rules it used | Same rules | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A snapshot names the reviewer rules it used | Snapshot from before the dialect change | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-evidence → A snapshot names the reviewer rules it used | Config of the earlier format | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-merge → Watch offers a release after an agent merge | Unattended agent merge with auto release | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-merge → Watch offers a release after an agent merge | Offer without auto | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-merge → Watch offers a release after an agent merge | An earlier version was left untagged | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-merge → Watch offers a release after an agent merge | Cleanup stopped | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-merge → Watch offers a release after an agent merge | Publish fails after the merge | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Unexpected failures keep the JSON error contract | Filesystem error during pass write | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Unexpected failures keep the JSON error contract | Existing structured stop | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Unexpected failures keep the JSON error contract | Unexpected failure in a ported subcommand | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → PR scripts remove their temp files on every exit | Reply posted | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → PR scripts remove their temp files on every exit | Post fails | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → PR scripts remove their temp files on every exit | Pending review stop after the reply | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → PR scripts remove their temp files on every exit | Skill steps that write body files | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Network commands have a deadline | GitHub answers in time | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Network commands have a deadline | Hung gh call in pr-pair.sh | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Network commands have a deadline | Hung gh call in a bash PR script | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Network commands have a deadline | Hung credential lookup in as.sh | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → GitHub responses are bounded | Large but bounded list | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → GitHub responses are bounded | Oversized paginated read | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → GitHub responses are bounded | Reaction loop past its page cap | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Watch claims and head records stay shared across implementations | A newer sw watcher takes over an older script watcher | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Watch claims and head records stay shared across implementations | Equal claim numbers across implementations (accepted gap) | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Watch claims and head records stay shared across implementations | State directory cannot be created | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Policy's remote settings read is strict | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Git Bash path forms | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Unchanged black-box evals pass on sw | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Differential run against the frozen script | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | A malformed settings file names its line | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Settings not pinned on GitButler | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Message text of the ported subcommands may be reworded | A reworded stop keeps its code | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Message text of the ported subcommands may be reworded | Workflow error keeps structured values | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Settings are read by one YAML parser | The same file read locally and remotely | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Settings are read by one YAML parser | A file the parser refuses | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Settings are read by one YAML parser | A comment-only file | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Settings are read by one YAML parser | A top level that is not a mapping | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A refused settings file stops each reader | Ship stops on a refused file | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A refused settings file stops each reader | A VCS write stops on a refused file | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A refused settings file stops each reader | The cheap tier on a refused file | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A refused settings file stops each reader | No settings file | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Commands that read no settings keep their behaviour | Identity on a refused file | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Commands that read no settings keep their behaviour | Identity on a missing directory | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A boolean written yes or no is refused | true and false | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A boolean written yes or no is refused | A yes boolean | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A boolean written yes or no is refused | A capitalised no | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A boolean written yes or no is refused | A quoted yes | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Settings constructs a settings file never needs are refused | A non-finite number | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Settings constructs a settings file never needs are refused | A quoted empty value in a message | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Settings constructs a settings file never needs are refused | A duplicate key in a reviewer | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Settings constructs a settings file never needs are refused | An alias | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Settings constructs a settings file never needs are refused | A block sequence | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A settings value of the wrong shape stops each reader | A reviewer written as a list | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A settings value of the wrong shape stops each reader | A reviewer written as a list, remotely | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A settings value of the wrong shape stops each reader | A report that is not a mapping | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A settings value of the wrong shape stops each reader | The cheap tier on a wrong shape | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A settings value of the wrong shape stops each reader | A review section that is not a mapping | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A settings value of the wrong shape stops each reader | A release or pr section that is not a mapping | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → A settings value of the wrong shape stops each reader | A flow list in a message | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Deeply nested settings stop without a crash | Ordinary nesting | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Deeply nested settings stop without a crash | A local file nested 100,000 levels | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Deeply nested settings stop without a crash | A remote file nested 100,000 levels | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Snapshots evaluate reviewers through sw | Reviewer states decided in sw | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Snapshots evaluate reviewers through sw | A pattern that backtracks past the deadline | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Snapshots evaluate reviewers through sw | Bad reviewer config | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Snapshots evaluate reviewers through sw | No Python on PATH | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-script-runtime → Snapshots evaluate reviewers through sw | Evaluator output that is not a document | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → The newest watcher owns a PR | Newer watcher takes over | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → The newest watcher owns a PR | Cleanup interleaved with a takeover | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → The newest watcher owns a PR | Two watchers claim at once | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → The newest watcher owns a PR | Owner crashed | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → The watch timeout is elapsed time | Slow polls count toward the timeout | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → The watch timeout is elapsed time | Poll hangs during the watch | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → The watch timeout is elapsed time | Takeover after a hung poll | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → The watch timeout is elapsed time | First snapshot hangs | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → A wait can skip wakes that are only check progress | A check passes while others run | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → A wait can skip wakes that are only check progress | The last check finishes | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → A wait can skip wakes that are only check progress | CI finishes before the reviewer's check | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → A wait can skip wakes that are only check progress | Only a reviewer's check is pending | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → A wait can skip wakes that are only check progress | A check fails | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → A wait can skip wakes that are only check progress | Feedback arrives during check progress | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → A wait can skip wakes that are only check progress | A conflict appears | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → A wait can skip wakes that are only check progress | Unknown mode or no wait | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → Watch waits for attention | Watch's wait command | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → Watch waits for attention | Ready after a quiet wait with a check re-run | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → Watch waits for attention | Default settle window | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → Watch waits for attention | Long wait ends quiet | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → Watch waits for attention | Not yet ready | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → Watch waits for attention | Bad settle value | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → The quiet window is main's | PR shortens the window | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → The quiet window is main's | Default written out | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → Ready accepts an unstable merge state once CI is done | Pending check makes the merge state unstable | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| pr-watch → Ready accepts an unstable merge state once CI is done | Snapshot without ci_pending | evals/pr-pair/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| preship-review → The pre-ship review checks the Release Notes section against the diff | Item the diff does not ship | evals/review-routes/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| preship-review → The pre-ship review checks the Release Notes section against the diff | Shipped change with no item | evals/review-routes/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| preship-review → The pre-ship review checks the Release Notes section against the diff | Section missing with releases on | evals/review-routes/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| preship-review → The pre-ship review checks the Release Notes section against the diff | Section breaks the format | evals/review-routes/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| preship-review → The pre-ship review checks the Release Notes section against the diff | Releases off | evals/review-routes/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| project-planning → Close offers untagged releases | Versions left untagged | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| project-planning → Close offers untagged releases | Everything tagged | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| project-planning → Close offers untagged releases | No tag yet | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| project-planning → Close offers untagged releases | User declines | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| project-planning → Close offers untagged releases | Releases disabled | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Publish creates and pushes an annotated tag | New release | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Publish creates and pushes an annotated tag | Tag template without the version | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Publish creates and pushes an annotated tag | Push refused by the fence | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Publish creates and pushes an annotated tag | Store-backed project | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Older untagged versions are published first | Older version untagged | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Older untagged versions are published first | Tag push failed earlier | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Older untagged versions are published first | First release's tag push failed | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Older untagged versions are published first | Backfill below the latest tag | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Untagged versions can be read from local tags only | Local tags only | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Untagged versions can be read from local tags only | Local read with a local-only tag | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A bumped version is greater than main's before it merges | Two changes bump to the same version | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A bumped version is greater than main's before it merges | Main moved past the bump | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A bumped version is greater than main's before it merges | Bump still ahead | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A bumped version is greater than main's before it merges | Version file edited without a bump | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A bumped version is greater than main's before it merges | Bump reverted on the branch | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A bumped version is greater than main's before it merges | Branch did not bump | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A bumped version is greater than main's before it merges | Main was merged into the branch after the duplicate landed | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A bumped version is greater than main's before it merges | Main has no version yet | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → An unreadable version is not absent | Merge base repeats the version | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → An unreadable version is not absent | Bump after a repair of an unreadable version | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → An unreadable version is not absent | One commit repairs and bumps | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → An unreadable version is not absent | Bump made through an unreadable version | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → An unreadable version is not absent | Broken main version repaired on both sides | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → An unreadable version is not absent | Stray version line added and removed | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Publish's network commands are bounded | Remote tags answer in time | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Publish's network commands are bounded | Hung tag lookup | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Publish's network commands are bounded | Oversized closed-PR read | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → One proposal's section can be checked before it merges | Valid section | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → One proposal's section can be checked before it merges | Two errors | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → One proposal's section can be checked before it merges | No section | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → One proposal's section can be checked before it merges | Missing file | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → One proposal's section can be checked before it merges | File over the read bound | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → The bump task writes the release summary | Bump task in a project with releases | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → The bump task writes the release summary | Releases off | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → The release skill names the proposal in the planning repo | Store-backed project | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → The release skill names the proposal in the planning repo | A hardcoded path comes back | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Release operations run in the project's sw | Publish without Python or bash | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Release operations run in the project's sw | Check reads the GitButler backend in process | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Release operations run in the project's sw | Status keeps its document | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Release operations run in the project's sw | No matching sw | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Version file patterns are JavaScript regular expressions | Shipped patterns read the version | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Version file patterns are JavaScript regular expressions | CRLF line ends | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Version file patterns are JavaScript regular expressions | Python-only syntax | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A misreadable settings line stops a release | Settings read as written | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A misreadable settings line stops a release | Misreadable line | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A misreadable settings line stops a release | A yes for enabled | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → A misreadable settings line stops a release | Notes ignores the settings | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Bump refuses a version file that is not UTF-8 | Valid UTF-8 files | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Bump refuses a version file that is not UTF-8 | A malformed file after a valid one | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| releases → Bump refuses a version file that is not UTF-8 | Check reads the malformed file | evals/release/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| review-routes → Review operations run in the project's sw | Pre-ship run without Python or bash | evals/review-routes/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| review-routes → Review operations run in the project's sw | Gate reads a record written before the port | evals/review-routes/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| review-routes → Review operations run in the project's sw | VCS backend read in process | evals/review-routes/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| review-routes → Review operations run in the project's sw | No matching sw | evals/review-routes/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| task-commits → A repeated task id stops the coverage check | Ticked line followed by a draft line with the same id | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| task-commits → A repeated task id stops the coverage check | Unique ids | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| task-commits → A repeated task id stops the coverage check | Repeated id in an untracked line | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| user-tasks → A task can be marked as the user's | Kinds are reported | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| user-tasks → A task can be marked as the user's | Marker not at the start of the text | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| user-tasks → A task can be marked as the user's | Ticked user task | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| user-tasks → An evidence task is ticked only with its evidence | Evidence present | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| user-tasks → An evidence task is ticked only with its evidence | Evidence file missing | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| user-tasks → An evidence task is ticked only with its evidence | Evidence only in the working tree | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| user-tasks → An evidence task is ticked only with its evidence | Store-backed evidence | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| user-tasks → An evidence task is ticked only with its evidence | No evidence path named | evals/git-workflow/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On jj a change branch is a bookmark at the parent of the working copy | Git reads after a jj commit | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On jj a change branch is a bookmark at the parent of the working copy | Working copy left with other edits | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → Release tags are the one Git write on jj | Publish on jj | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → Release tags are the one Git write on jj | Tag at another commit | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → Change ranges read the change branch tip | Other applied branches | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → Change ranges read the change branch tip | Gate after the archive commit | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → Change ranges read the change branch tip | Version check ignores other branches | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → Change ranges read the change branch tip | Branch not given | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → Change ranges read the change branch tip | Branch moved after the review | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → Change ranges read the change branch tip | Git unchanged | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Unassigned edit before ship | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Watch reads merge settings | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Push with an unpinned edit | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Context without the branch | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Feedback or CI fix push in a repo-local project | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Cleanup after the merge | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Cleanup with an unpinned edit | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Cleanup after a skipped pull | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Settings never committed on the branch | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | The change commits its own settings edit | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Branch already deleted | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Pinned settings | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → On GitButler the settings are those the change branch committed | Git backend | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs keeps vcs.sh's output and exit-code contract | Unchanged black-box evals pass on sw | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs keeps vcs.sh's output and exit-code contract | Unknown subcommand | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Settings read through pr-pair.sh | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Unknown backend in the settings | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Scripts installed under a non-UTF-8 directory | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Unpinned settings stop a GitButler push | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Fenced push | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Refused fence | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Login resolved in process | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs reads settings and fences identity in process | No gh account to resolve | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Store without a Specwright version | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Fenced commands stay unbounded | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Non-GitHub remote runs unfenced | evals/vcs/ | existing test of this scenario, unchanged: wording-only rewrite | green |

## 1. Issues for the requirements left out of the sweep

- [x] 1.1 File the five D3 issues as `KintsugiBot` through `sw as KintsugiBot gh issue create --repo sh1ny/specwright`, one for each requirement: change-finish "finish.sh runs no network command", eval-runner "Changed paths select the suites", pr-script-runtime "sw pr snapshot and sw pr reply keep the scripts' contracts", vcs-backends "The archive undo plan uses jj on a jj repo" and vcs-backends "The archive undo plan uses GitButler on a GitButler repo". Each issue says why rewording would change what the requirement asserts (design D3). Verify: `sw as KintsugiBot gh issue view <n> --repo sh1ny/specwright` shows each one open; note the five numbers for task 2.2.

## 2. Sweep guard (design D1)

- [x] 2.1 Write `evals/runner/test_spec_retired_names.py`. It reads the main specs, overlays the active changes' deltas in archive order (RENAMED, REMOVED, MODIFIED, ADDED), and skips archived changes and parked ones (a `review.md` line exactly `VERDICT: DEFERRED`). It matches the 14 names of the name map and compares every block that names one with an `ALLOWED` table. Each table entry is keyed by capability, requirement header and scenario header (or the requirement's description) and lists the exact lines that hold a name. Add fixture tests against a temp tree: a new mention fails, a second mention in an allowed block fails, a moved line fails, a removed mention fails, a two-change collision fails and names both changes (MODIFIED, REMOVED, RENAMED source or destination), a parked change is skipped, and one change with RENAMED and MODIFIED entries gives the text archive would write. Run `python -m unittest evals/runner/test_spec_retired_names.py` with an empty `ALLOWED` table first: the fixture tests pass, and the real-tree test fails and lists the 43 blocks of the design's Allowlist inventory.
- [x] 2.2 C1: fill `ALLOWED` from the real tree. Its doc comment states the C1 invariant: retired names stay only in the listed blocks (history, the name map, output strings `sw` still prints, headers kept as match keys). It also names the five deferred entries with their issue numbers from task 1.1, which leave the list when those issues are fixed, and says that a new mention needs an entry and a reason. Verify: the module passes, and every row's counts match the Allowlist inventory in design.md.
- [x] 2.3 Add `runner/test_spec_retired_names.py` to the suites of the `openspec/**` rule in `evals/suites.json`. Verify: `python -m unittest evals/runner/test_suite_map.py` passes.

## 3. Install prompt (#242), README.md

- [x] 3.1 Write `evals/git-workflow/test_install_prompt_242.py` with the 14 `red` test-map rows. It reads README Steps 4, 6, 7 and 8 with the `step()` helper the README evals use. Add its rule to `evals/suites.json` (suite `git-workflow`, with the `README.md` rule's coverage). Verify: `python -m unittest evals/git-workflow/test_install_prompt_242.py` fails on each new test because the README lacks the wording, and `python -m unittest evals/runner/test_suite_map.py` passes.
- [x] 3.2 Revise the two pins on the edited wording (design Context). `test_readme_step6_packs_are_user_data` (evals/git-workflow/test_instructions.py:2591) now accepts the user-data sentence that also names `release.version_files.`. `test_install_step7_uncommented_only` (:1295) checks the compared-path rule and its user-data and consent exemptions. Verify: both tests fail against the current README for the new wording only.
- [x] 3.3 Edit README Step 6. Add `release.version_files.` to the user-data prefixes. Offer an absent `release.version_files` as the template's whole mapping, which the user may keep or decline. Say the merge keeps the user's values and the comments of every key it keeps, and copies the template's comment only with a key it adds on the user's accepted default. C2: confirm that the delta requirement "The settings merge treats version-file entries as user data" (specs/install-update/spec.md) says entries are user data while `release.version_files` stays compared. Verify: the Step 6 tests of task 3.1 and test_readme_step6_packs_are_user_data pass, and the row states flip to green.
- [x] 3.4 Edit README Steps 4 and 7. Step 7's skills check replaces "nothing else is in them" with the per-directory rule: `specwright-*` directories with a downloaded counterpart have no extra file, a kept orphan passes, an approved orphan that is still present fails, and other directories don't count. Its key check checks `release.version_files` like any compared key and skips its entries. Step 4 asks about `specwright-*` skill orphans that this update does not install, on a new swap and on a confirmed completed swap, before Step 5. Both resume directions (README.md:322-325 and :484-485) now go through that question. Verify: the Step 4 and Step 7 tests of task 3.1 and test_install_step7_uncommented_only pass, and the row states flip to green.
- [x] 3.5 Edit README Step 8 to say the interface is the line holding only `interface <n>` in the installed `specwright-pr/SKILL.md`, with no number given and the pinned phrase "`interface <n>` line in the installed `specwright-pr/SKILL.md`" kept. Edit the `vcs.sh` sentences at README.md:129 and :549 so they describe an older user-level copy from before 0.14.0, keeping the phrase "older user-level copy stops every `vcs.sh` call with `scripts_in_workspace`". Verify: `python -m unittest evals/git-workflow/test_install_sw_warning.py` passes and so does test_install_prompt_242.py.

## 4. Spec checks

- [ ] 4.1 Run `openspec validate spec-wording-sweep --strict` and `python -m unittest evals/git-workflow/test_specs_strict.py`. Verify: both pass.

## 5. Integration and release

- [ ] 5.1 Confirm on the PR's CI run (`.github/workflows/evals.yml`, three OSes) that the suites holding the `green` rows pass: finish, git-workflow, packs, pr-pair, release, review-routes, runner, update, vcs and cli. Verify: the run is green, its URL is noted in the PR description, and no row needed a code change.
- [ ] 5.2 Run `sw release bump --to 0.39.1` and rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify: `sw release check` reports `0.39.1` for every version file, and `sw release notes --proposal openspec/changes/spec-wording-sweep/proposal.md` prints the notes.
