"""Guard: retired script names stay out of the main specs except in the ALLOWED blocks.

The test reads openspec/specs/*/spec.md, lays the active changes' deltas over them in the order
OpenSpec applies them at archive (RENAMED, REMOVED, MODIFIED, ADDED), and finds the 14 retired
script names of the native-cli name map. Every block that names one must equal an ALLOWED entry:
same capability, requirement header, scenario header (or the requirement description) and the
same lines, in the same order.

Run: python -m unittest evals/runner/test_spec_retired_names.py
"""
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

NAMES = [
    "vcs.sh", "as.sh", "pr-pair.sh", "pr-snapshot.sh", "pr-reply.sh", "sw-path.sh",
    "task-cover.sh", "fit-subject.sh", "finish.sh", "review-run.sh", "release.sh",
    "update.sh", "bounded.py", "reviewers.py",
]
# Whole names only: no word character, dash or dot before, no word character, dash or ".x" after.
NAME_RE = re.compile(
    r"(?<![\w.\-])(" + "|".join(re.escape(n) for n in NAMES) + r")(?![\w\-]|\.\w)"
)

# C1 invariant: retired script names may stay in the main specs only in the blocks listed here:
# kept history, the name map, output strings `sw` still prints, and headers kept as match keys
# (`openspec validate` matches MODIFIED requirements and scenarios by header).
# Five entries are deferred contract work, not history. Each leaves the list when its issue is fixed:
#   change-finish "finish.sh runs no network command"                                  -> #244
#   eval-runner "Changed paths select the suites"                                      -> #245
#   pr-script-runtime "sw pr snapshot and sw pr reply keep the scripts' contracts"     -> #246
#   vcs-backends "The archive undo plan uses jj on a jj repo"                          -> #247
#   vcs-backends "The archive undo plan uses GitButler on a GitButler repo"            -> #248
# A new mention of a retired name needs an entry here and a reason. A removed mention needs its
# entry shrunk. Key: (capability, requirement header text, scenario header text or "" for the
# requirement description). Value: (reason, the exact lines that hold a name, in order).
ALLOWED = {
    ("change-finish", "Fixed undo-plan defects are exceptions to the script's refusals", ""): (
        "kept history",
        [
            "The undo-plan requirements above change `finish.sh`'s refusals, exit codes, guards and warnings: usage errors exit 2, failed reads stop with `vcs_error`, paths are whole, guards see what configuration hid, and the plan warns about the index. Where these differ from \"The undo plan runs in the project's sw\", \"Undo steps do what the old script did\" or \"Undo requirements that say script mean the steps\", they SHALL take precedence; all else follows those.",
        ],
    ),
    ("change-finish", "Fixed undo-plan defects are exceptions to the script's refusals", "A guard that now refuses"): (
        "kept history",
        [
            "- **WHEN** the index holds a staged gitlink hidden by `diff.ignoreSubmodules=all`, which `finish.sh` let through",
        ],
    ),
    ("change-finish", "Fixed undo-plan defects are exceptions to the script's refusals", "A plan carries the new index warning"): (
        "kept history",
        [
            "- **THEN** its warnings hold the new index warning beside the warnings `finish.sh` gave",
        ],
    ),
    ("change-finish", "Fixed undo-plan defects are exceptions to the script's refusals", "A usage error from the state read"): (
        "kept history",
        [
            "- **WHEN** the planner's state read fails with a usage error, which `finish.sh` reported with exit 1",
        ],
    ),
    ("change-finish", "Fixed undo-plan defects are exceptions to the script's refusals", "Any other refusal"): (
        "kept history",
        [
            "- **THEN** its error and exit status are as `finish.sh` gave them",
        ],
    ),
    ("change-finish", "The undo plan runs in the project's sw", ""): (
        "kept history",
        [
            "The skills SHALL run `sw finish undo-archive-plan` directly; it SHALL keep `finish.sh`'s arguments, refusals and exit codes and print its undo as `steps` and `after_rerun_steps`, and no other implementation SHALL remain. A malformed argument SHALL be refused as native-cli \"Arguments sw cannot represent are refused\" states; an archived name that is not valid UTF-8 SHALL stop the plan with `\"error\": \"not_utf8\"` and exit 1. Neither prints a plan.",
        ],
    ),
    ("change-finish", "Undo steps do what the old script did", ""): (
        "kept history",
        [
            "`steps` SHALL run the old script's operations in its order, with its backups and warnings; each `sw` step carries `--project <code toplevel>`. File operations, `git cat-file --filters` writes and the message write SHALL be `sw finish undo-step` steps (`move`, `remove`, `copy`, `mkdir`, `rmdir-if-empty`, `write-blob`, `write-text`); `vcs.sh` calls become `sw vcs` steps. A failing step stops the runner as `set -e` did; recovery is the plan's `warnings`.",
        ],
    ),
    ("change-finish", "finish.sh finds the project from --code, then --dir", ""): (
        "header match key",
        [
            "### Requirement: finish.sh finds the project from --code, then --dir",
        ],
    ),
    ("change-finish", "finish.sh runs no network command", ""): (
        "deferred #244",
        [
            "### Requirement: finish.sh runs no network command",
            "`finish.sh` and `sw finish undo-archive-plan` SHALL run only local `git` reads and SHALL NOT run a `git` network command (`fetch`, `pull`, `push`, `ls-remote`) or `gh`. Every network step of finish SHALL be one the agent runs through `as.sh`, under that script's bounds.",
        ],
    ),
    ("change-finish", "finish.sh runs no network command", "A network command added to finish.sh"): (
        "deferred #244",
        [
            "#### Scenario: A network command added to finish.sh",
            "- **WHEN** `finish.sh` holds a call to `git fetch`, `git pull`, `git push`, `git ls-remote` or `gh`",
        ],
    ),
    ("change-finish", "finish.sh runs no network command", "Plan with an unreachable origin"): (
        "deferred #244",
        [
            "- **WHEN** `finish.sh undo-archive-plan` runs for a committed bulk archive in a repo whose `origin` URL points nowhere, with a `gh` on `PATH` that never answers",
        ],
    ),
    ("eval-runner", "A stopped test file's nested sessions are stopped too", "No shipped bounded.py"): (
        "header match key, kept history",
        [
            "#### Scenario: No shipped bounded.py",
            "- **WHEN** the runner runs a suite in a tree with no `skills/specwright-pr/scripts/bounded.py`",
        ],
    ),
    ("eval-runner", "Changed paths select the suites", "A change to one skill script"): (
        "deferred #245",
        [
            "- **WHEN** the only changed path is `skills/specwright-release/scripts/release.sh`",
        ],
    ),
    ("eval-runner", "Changed paths select the suites", "An uncommitted file counts"): (
        "deferred #245",
        [
            "- **WHEN** the branch has no commit since `<base>` and `skills/specwright-finish/scripts/finish.sh` is modified but not staged",
        ],
    ),
    ("eval-runner", "Frozen-oracle evals are migrated before the cutover", "An eval left on a removed script"): (
        "kept history",
        [
            "- **WHEN** after the cutover an eval still copies or runs `vcs.sh`, `as.sh`, `sw-path.sh`, `bounded.py` or a frozen script that needs them",
        ],
    ),
    ("github-identity", "sw as keeps as.sh's contract", ""): (
        "header match key, kept history",
        [
            "### Requirement: sw as keeps as.sh's contract",
            "`sw as` SHALL accept what `as.sh` accepted and SHALL keep its refusals, messages, exit codes, environment rules, the saved `AS_SH_ORIG_*` values, the git transport settings and the credential helper. Its own `gh` lookups SHALL keep their deadline and size bound, report `deadline_exceeded` or `response_too_large` with exit 3, and hold the token only in memory.",
        ],
    ),
    ("github-identity", "sw as keeps as.sh's contract", "A hung token lookup"): (
        "sw output string",
        [
            "- **THEN** `<sw> as sh1ny gh api user` exits 3 with `as.sh: deadline_exceeded: gh auth token --user sh1ny` on stderr, and the fenced command did not run",
        ],
    ),
    ("github-identity", "sw as keeps as.sh's contract", "Exit codes"): (
        "kept history",
        [
            "- **THEN** the exit statuses are 1, 2, 2 and 3, as `as.sh` gave",
        ],
    ),
    ("github-identity", "sw as keeps as.sh's contract", "Unchanged black-box evals pass on sw"): (
        "kept history",
        [
            "- **THEN** every test passes with its stdout, stderr and exit-status assertions as they were for `as.sh`, apart from the removed `sw_missing`, `no_python` and handoff cases",
        ],
    ),
    ("github-identity", "sw as verifies the token for its login", "A token that belongs to another login"): (
        "sw output string",
        [
            "- **THEN** `<sw> as sh1ny gh api user` exits 3 with `as.sh: token resolves to 'KintsugiBot', expected 'sh1ny'; refusing` on stderr, and the fenced command did not run",
        ],
    ),
    ("install-update", "An install whose VCS steps need a missing sw says so", "An older supported tag"): (
        "kept history",
        [
            "- **WHEN** the new install prompt selects `v0.37.0`, whose installed skills pin interface 1 in `sw-path.sh`, its `sw-install` returns `installed`, and at Step 8 the pinned binary exits 0 reporting `0.37.0` and interface 1",
        ],
    ),
    ("install-update", "An install whose VCS steps need a missing sw says so", "Older tag whose scripts need no sw"): (
        "kept history",
        [
            "- **WHEN** the user asks for `v0.23.0`, whose `vcs.sh` runs no `sw`",
        ],
    ),
    ("install-update", "sw update recovers journals that older update scripts left", ""): (
        "kept history",
        [
            "`sw update recover`, and the recovery `plan` runs first, SHALL read and recover a pending journal of format 1 or format 2 written by an older `update.sh`, with the same outcomes as for its own journal. A journal of an unknown format, or one that does not parse as a whole, SHALL be refused as `journal_unreadable`, and nothing SHALL be touched.",
        ],
    ),
    ("install-update", "sw update recovers journals that older update scripts left", "A format-2 journal from update.sh"): (
        "header match key, kept history",
        [
            "#### Scenario: A format-2 journal from update.sh",
            "- **WHEN** an update by the 0.36.0 `update.sh` was interrupted mid-swap with a complete staged copy, and the 0.37.0 prompt then runs `sw update plan`",
        ],
    ),
    ("native-cli", "A launch-site allowlist guards process starts", "A script in launch arguments fails"): (
        "kept history",
        [
            "- **WHEN** a listed launch site passes `as.sh`, `vcs.sh`, `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh`, `review-run.sh`, `release.sh`, `update.sh`, `install-sw.sh` or a `.py` file as a launch argument",
        ],
    ),
    ("native-cli", "A launch-site allowlist guards process starts", "A script name built away from the launch fails"): (
        "kept history",
        [
            "- **WHEN** a source file under `cli/lib/src` writes `vcs.sh`, `as.sh` or another retired script name into a printed command",
        ],
    ),
    ("native-cli", "Arguments reach native executables unchanged", ""): (
        "kept history",
        [
            "A native executable (anything but a `.cmd` or `.bat` file) SHALL start with no shell before it and receive every argument value unchanged, as UTF-8 on Linux and macOS, up to the OS command-line limit (32,767 UTF-16 units on Windows). Input the launcher cannot represent SHALL be refused by name before any start. On Windows, for `bash -c <script> <name> <args...>`, the arguments after `<name>` SHALL travel on stdin as in `bounded.py`, so Git Bash's 8,186-character cut cannot shorten them.",
        ],
    ),
    ("native-cli", "JSON input that is not plain JSON is refused", "Non-finite number"): (
        "sw output string",
        [
            "- **THEN** the command exits 1, prints one stderr line prefixed `reviewers.py:` naming the file, and prints nothing on stdout",
        ],
    ),
    ("native-cli", "Long Windows arguments reach native tools whole", "An inherited batch launch through the identity fence"): (
        "sw output string",
        [
            "- **THEN** it exits 2 with `as.sh: unrepresentable` naming the command, and neither `cmd.exe` nor `tool.cmd` starts",
        ],
    ),
    ("native-cli", "Printed commands name sw", "A cleanup plan that pulls under the fence"): (
        "kept history",
        [
            "- **THEN** that step starts with the running binary's absolute path followed by `--project <code> as <login> git pull --ff-only`, and no step names `as.sh`",
        ],
    ),
    ("native-cli", "Printed commands name sw", "An undo-archive plan"): (
        "kept history",
        [
            "- **THEN** each step the old script ran through `vcs.sh` has an argv of the running binary's absolute path, `--project <code>`, `vcs` and the old subcommand with its arguments, a state check the old script made by text becomes an `undo-step check` step, the `git` and `jj` steps the old script ran directly stay `git` and `jj` steps, and no step names `vcs.sh` or `bash`",
        ],
    ),
    ("native-cli", "Retired script names map to sw commands", ""): (
        "name map",
        [
            "Where a requirement names a retired script, it SHALL mean the matching `sw` command with the same arguments and contract: `vcs.sh` is `sw vcs`, `as.sh` is `sw as`, `pr-pair.sh` is `sw pr`, `pr-snapshot.sh` and `pr-reply.sh` are `sw pr snapshot` and `sw pr reply`, `task-cover.sh` and `fit-subject.sh` are `sw commit task-cover` and `fit-subject`, `finish.sh` is `sw finish`, and `review-run.sh`, `release.sh` and `update.sh` are `sw review`, `sw release` and `sw update`.",
        ],
    ),
    ("native-cli", "Retired script names map to sw commands", "A requirement naming a script"): (
        "name map",
        [
            "- **WHEN** a requirement says `vcs.sh fetch-main` prints a `ref`",
        ],
    ),
    ("native-cli", "Retired script names map to sw commands", "The Python helpers"): (
        "name map",
        [
            "- **WHEN** a requirement names `bounded.py` or `reviewers.py`",
        ],
    ),
    ("native-cli", "Skills run sw directly", "A skill step names sw"): (
        "kept history",
        [
            "- **THEN** each Specwright command starts with `<sw>`, and no command names `vcs.sh`, `as.sh`, `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh`, `sw-path.sh`, `task-cover.sh`, `fit-subject.sh`, `finish.sh`, `review-run.sh`, `release.sh`, `update.sh` or a `.py` file",
        ],
    ),
    ("native-cli", "sw run --bounded keeps bounded.py's command-line contract", ""): (
        "header match key",
        [
            "### Requirement: sw run --bounded keeps bounded.py's command-line contract",
        ],
    ),
    ("native-cli", "sw run --bounded keeps bounded.py's command-line contract", "Limit line names the command a shell wraps"): (
        "kept history",
        [
            "- **THEN** stderr is `bounded: deadline_exceeded: gh api`: for `sh` or `bash` with `-c` and more than three arguments, the line names the two arguments after the script, as `bounded.py` does",
        ],
    ),
    ("pr-evidence", "A snapshot names the reviewer rules it used", "Config of the earlier format"): (
        "sw output string",
        [
            "- **THEN** it exits 2 with `reviewers.py: cfg.json: format must be 2` on stderr, and `sw pr snapshot --reviewer-config cfg.json` exits 2 before any `gh` call",
        ],
    ),
    ("pr-script-runtime", "Fixed snapshot defects are exceptions to the scripts' contract", ""): (
        "kept history",
        [
            "The three requirements below fix defects `sw pr snapshot` kept from `pr-snapshot.sh`. Where they differ from \"sw pr snapshot and sw pr reply keep the scripts' contracts\" or from \"PR snapshots and replies run in the project's sw\", they SHALL take precedence for `sw pr snapshot` only. Every other output, except the new helper refusal above, still follows both requirements and the frozen oracle records.",
        ],
    ),
    ("pr-script-runtime", "Network commands have a deadline", "Hung credential lookup in as.sh"): (
        "header match key",
        [
            "#### Scenario: Hung credential lookup in as.sh",
        ],
    ),
    ("pr-script-runtime", "Network commands have a deadline", "Hung gh call in pr-pair.sh"): (
        "header match key",
        [
            "#### Scenario: Hung gh call in pr-pair.sh",
        ],
    ),
    ("pr-script-runtime", "Snapshots evaluate reviewers through sw", ""): (
        "kept history",
        [
            "`sw pr snapshot` SHALL check the `--reviewer-config` file in its own process before any `gh` call. It SHALL decide reviewer states by running its own binary as `sw pr reviewers` under the deadline, byte bound and temp-file rules `reviewers.py` ran under, and SHALL read that child's document by parsing it. It SHALL start no Python evaluator and run no interpreter probe.",
        ],
    ),
    ("pr-script-runtime", "Snapshots evaluate reviewers through sw", "A pattern that backtracks past the deadline"): (
        "kept history",
        [
            "- **THEN** the evaluation is stopped at the deadline, stderr holds the line `bounded: deadline_exceeded: reviewers.py python3`, the poll fails, and no evaluator process or material file is left",
        ],
    ),
    ("pr-script-runtime", "Snapshots evaluate reviewers through sw", "Bad reviewer config"): (
        "sw output string",
        [
            "- **THEN** the exit status is 2, stderr holds one line prefixed `reviewers.py:` that says the file is not valid JSON, no `gh` call was made, and no child `sw` was started for the check",
        ],
    ),
    ("pr-script-runtime", "Snapshots evaluate reviewers through sw", "Reviewer states decided in sw"): (
        "kept history",
        [
            "- **THEN** that login's `reviewers` entry has the state `reviewers.py` decided before this change, `reviewer_config` holds the file's digest, and the evaluation ran as the bounded `sw pr reviewers` child, with no Python interpreter started",
        ],
    ),
    ("pr-script-runtime", "The ported pr-pair subcommands keep the script's contracts", "Differential run against the frozen script"): (
        "kept history",
        [
            "- **WHEN** the parity eval runs each case of each subcommand through `sw pr`, against the repositories and fake-gh state the case builds, and compares it with the record the frozen `pr-pair.sh` produced for that case, captured in the commit before the scripts were removed",
            "- **THEN** `sw pr` exits with the recorded status and makes the recorded `gh` calls for inputs retained by the native-cli contract; documented JSON/input and option refusals keep their explicit difference tests. Stderr lines match the record up to each line's prefix, and stdout parses to the recorded JSON value apart from free text compared by its prefix, `reviewer_config` digests and paths, which name `sw pr`'s own `\"format\": 2` file, the listed settings differences with their own outcome tests, and `cleanup-plan`'s printed commands, which this change moves from `bash .../as.sh`, `vcs.sh` and `pr-pair.sh` to `<sw> --project <code> ...`: their decisions, guards, order and `gh` calls match the record, and their argv, working directory and project selection are asserted on their own. Records hold no paths of the machine that made them. A run-generated feedback owner id in `pass write` stdout is checked to equal the owner in the record that run wrote and is then replaced by a placeholder before the comparison, and persisted write and adopt times are checked against the run, as the live matrix did. Fixture commits are made with a pinned author, committer and dates, so their ids repeat across runs and `lacking[].sha` is compared exactly; the final fake-gh state and each written comment body are recorded and compared byte for byte",
        ],
    ),
    ("pr-script-runtime", "Unexpected failures keep the JSON error contract", ""): (
        "kept history",
        [
            "Each `sw pr` subcommand from `pr-pair.sh` (`identity`, `context`, `tier`, `vcs`, `discover`, `expected`, `ensure-pr`, `closing-check`, `closed-check`, `link`, `pair-state`, `rounds`, `pass`, `cleanup-plan`, `branch-check`, `merge`, `delete-remote`, `policy` and `item-issues`) SHALL report an unexpected exception as one stdout JSON line with `\"ok\": false`, `\"error\": \"internal_error\"` and a `message` naming its type, and exit 1. Structured stops SHALL keep their own codes and exit statuses.",
        ],
    ),
    ("pr-script-runtime", "Watch claims and head records stay shared across implementations", ""): (
        "kept history",
        [
            "`sw pr snapshot` SHALL read and write watch claims under `<state>/watch/v2/<owner>/<name>/<pr>/` (lower case) and head records under `<state>/heads/`, where `<state>` is `SPECWRIGHT_STATE_DIR`, else `$HOME/.cache/specwright`, with the file names and contents `pr-snapshot.sh` used before this change, so `sw pr` and a watcher of either implementation see each other's claims and records.",
        ],
    ),
    ("pr-script-runtime", "Watch claims and head records stay shared across implementations", "A newer sw watcher takes over an older script watcher"): (
        "kept history",
        [
            "- **WHEN** a watcher run by the `pr-snapshot.sh` from before this change waits on PR 12, and a `sw pr snapshot 12 --wait` watcher starts for the same PR",
        ],
    ),
    ("pr-script-runtime", "sw pr ignores an inherited GH_REPO", ""): (
        "kept history",
        [
            "Every `gh` call that one of the nineteen `sw pr` subcommands makes, account-scoped calls such as `gh api user` and `gh auth token` included, SHALL run with `GH_REPO` removed from its environment. Each repository-scoped call SHALL also name its repository (`--repo` or `repos/<owner>/<name>/...`), so an inherited `GH_REPO` never picks the repository. `sw` does this itself, as the `pr-pair.sh` shim's `unset GH_REPO` did.",
        ],
    ),
    ("pr-script-runtime", "sw pr reviewers keeps the evaluator's contract", ""): (
        "sw output string",
        [
            "`sw pr reviewers --check-config FILE` and `sw pr reviewers --config FILE --material FILE --head OID` SHALL print the same parsed output fields, one stderr line prefixed `reviewers.py:` where `reviewers.py` printed one, naming the same reviewer and key, and exit with the same status as `reviewers.py` did, except where a report pattern compiles differently, the config's format is not 2 (see pr-evidence), or the native-cli JSON/input or option contract explicitly changes an accepted form.",
        ],
    ),
    ("pr-script-runtime", "sw pr reviewers keeps the evaluator's contract", "Material that is not its head"): (
        "kept history",
        [
            "- **THEN** it exits 1 with nothing on stdout, as `reviewers.py` did",
        ],
    ),
    ("pr-script-runtime", "sw pr snapshot and sw pr reply keep the scripts' contracts", ""): (
        "deferred #246",
        [
            "`sw pr snapshot` and `sw pr reply`, run through the scripts' shims, SHALL take the scripts' arguments and print the same stdout bytes, stderr messages and exit statuses for the same GitHub answers: the snapshot line, `--full`, `--wait` wake documents, markers, revision checks, reactions and resolutions included. `sw pr snapshot` has two exceptions: its `reviewer_config` digest is that of the format 2 config, and an evaluator line it relays keeps its `reviewers.py:` prefix, its wording free.",
        ],
    ),
    ("pr-script-runtime", "sw pr snapshot and sw pr reply keep the scripts' contracts", "Removed reviewer flag"): (
        "deferred #246",
        [
            "- **WHEN** `pr-snapshot.sh 12 --reviewer bot:review:600` runs",
        ],
    ),
    ("pr-script-runtime", "sw pr snapshot and sw pr reply keep the scripts' contracts", "Stale revision posts nothing"): (
        "deferred #246",
        [
            "- **WHEN** `pr-reply.sh 12 thread <t> <r> body.md --rev 900@2026-11-01T10:00:00Z` runs and the thread's revision is now `901@2026-11-02T09:00:00Z`",
        ],
    ),
    ("pr-script-runtime", "sw pr snapshot and sw pr reply keep the scripts' contracts", "Unchanged black-box evals pass on sw"): (
        "deferred #246",
        [
            "- **THEN** every test passes with its assertions unchanged from before this change, apart from the format 2 digest and the wording of relayed `reviewers.py:` lines; every other byte of stdout, stderr and the exit status is compared as before",
        ],
    ),
    ("releases", "Release operations run in the project's sw", ""): (
        "kept history",
        [
            "Each `release.sh` subcommand SHALL run as `sw release`, called directly, keeping its options, JSON fields, error names and exits 0/1/2/3. The operations SHALL NOT start Python, bash, sh or a shipped script for their own work, and SHALL read the code repo's VCS backend in process. When the project's `VERSION` is missing or differs from the running `sw`'s version, the command SHALL print one `sw_mismatch` JSON document and exit 1, with no fallback.",
        ],
    ),
    ("releases", "Release operations run in the project's sw", "Status keeps its document"): (
        "kept history",
        [
            "- **WHEN** `sw release status --version 0.5.0` runs on a repository where the Python `release.sh` printed a status document before the port",
        ],
    ),
    ("releases", "The release summary comes from the bumping change", ""): (
        "kept history",
        [
            "The release summary SHALL be the summary of the change in V's range whose archived `tasks.md` has a ticked task running `release.sh bump --to <V>` or `sw release bump --to <V>` (the form skills write from this change on; the older form stays recognised for earlier releases and backfills) and whose section is valid. When no change or more than one matches, it SHALL be the summary of the last change with a valid section in the notes' order.",
        ],
    ),
    ("releases", "The release summary comes from the bumping change", "Bumping change archived with another in the same commit"): (
        "kept history",
        [
            "- **WHEN** the release commit adds the archives `2026-11-02-b-bump` (its `tasks.md` has `- [x] 3.1 release.sh bump --to 0.9.0`) and `2026-11-02-c-other`, both with valid sections, and `c-other` sorts last",
        ],
    ),
    ("releases", "The release summary comes from the bumping change", "No change has a bump task"): (
        "kept history",
        [
            "- **WHEN** no archived `tasks.md` in the range has a ticked `release.sh bump --to 0.9.0` task, and `add-a` then `add-b` have valid sections",
        ],
    ),
    ("review-routes", "Review operations run in the project's sw", ""): (
        "kept history",
        [
            "Each `review-run.sh` subcommand SHALL run as `sw review`, called directly, preserving options, JSON, exits 0/1/2/3, records and state directory. Operations SHALL NOT start Python, bash or shipped scripts for their own work. When the project's `VERSION` is missing or differs from the running `sw`'s version, the command SHALL print one `sw_mismatch` JSON document and exit 1, before any probe and with no fallback. The fixed OMP policy SHALL run inside OMP, not in a separate interpreter process.",
        ],
    ),
    ("review-routes", "Review operations run in the project's sw", "Gate reads a record written before the port"): (
        "kept history",
        [
            "- **WHEN** a pre-ship record written by the Python `review-run.sh` exists for the change's current heads, and `sw review gate` runs",
        ],
    ),
    ("task-commits", "Commit tooling runs in the project's sw", ""): (
        "kept history",
        [
            "The skills SHALL run `sw commit task-cover` and `sw commit fit-subject` directly, and these SHALL keep the arguments and output contracts of `task-cover.sh` and `fit-subject.sh`. No other implementation of the commit tooling SHALL remain. An argument that is not well-formed Unicode SHALL be refused before any file is read, as native-cli \"Arguments sw cannot represent are refused\" states.",
        ],
    ),
    ("task-commits", "sw commit fit-subject keeps fit-subject.sh's contract", ""): (
        "header match key, kept history",
        [
            "### Requirement: sw commit fit-subject keeps fit-subject.sh's contract",
            "`sw commit fit-subject` SHALL accept the one message-file argument and produce the same file bytes, stdout, stderr and exit codes 0 to 2 as `fit-subject.sh` for the same file. An unexpected failure SHALL print one line on stderr, leave the file untouched and exit 2, never a stack trace on stdout.",
        ],
    ),
    ("task-commits", "sw commit fit-subject keeps fit-subject.sh's contract", "Rewrite fails"): (
        "sw output string",
        [
            "- **THEN** it exits 2 with `fit-subject.sh: could not rewrite <msg>` on stderr, `<msg>` is byte for byte as it was, and no temporary file is left",
        ],
    ),
    ("task-commits", "sw commit fit-subject keeps fit-subject.sh's contract", "Unchanged fit-subject evals pass on sw"): (
        "kept history",
        [
            "- **WHEN** the `evals/git-workflow` tests of `fit-subject.sh` run in CI on Linux, Windows and macOS against the `sw` built from the tree",
        ],
    ),
    ("task-commits", "sw commit task-cover keeps task-cover.sh's contract", ""): (
        "header match key, kept history",
        [
            "### Requirement: sw commit task-cover keeps task-cover.sh's contract",
            "`sw commit task-cover` SHALL accept `task-cover.sh`'s options, honour `TASK_COVER_MAX_COMMITS`, and print JSON that parses to the same keys, key order and values for the same inputs, with the same error codes and exit codes 0 to 3. Differences: task and group ids are ASCII digits only, and a task, commit subject, trailer or numbered heading with a group number beyond 64 bits is ignored. An unexpected failure SHALL print the document `\"error\": \"internal_error\"` and exit 1, never a stack trace.",
        ],
    ),
    ("task-commits", "sw commit task-cover keeps task-cover.sh's contract", "Unchanged task-cover evals pass on sw"): (
        "kept history",
        [
            "- **WHEN** the `evals/git-workflow` tests of `task-cover.sh` and the `evals/vcs` coverage test run in CI on Linux, Windows and macOS against the `sw` built from the tree",
        ],
    ),
    ("task-commits", "sw commit task-cover keeps task-cover.sh's contract", "Usage error"): (
        "kept history",
        [
            "- **THEN** it exits 2 and stdout is one JSON document with `\"error\": \"usage\"` and the usage line `task-cover.sh` printed before this change, with ` [--code <dir>]` added at its end",
        ],
    ),
    ("task-commits", "task-cover.sh finds the project from --code", ""): (
        "header match key",
        [
            "### Requirement: task-cover.sh finds the project from --code",
        ],
    ),
    ("vcs-backends", "Fixed commit defects are exceptions to the backends' unchanged outputs", ""): (
        "kept history",
        [
            "The requirements above change results: GitButler CR read as LF and relative message paths read where `sw` runs, LF on jj, the real `but` line counted, a Windows VCS line of exactly 32,767 units refused before start, and a fixed `git_commit_failed` message for a Windows `git.cmd` line over the limit. Where they differ from the three `sw vcs` parity requirements (settings and fencing, vcs.sh's output and exit codes, document values), they SHALL take precedence.",
        ],
    ),
    ("vcs-backends", "The archive undo plan uses GitButler on a GitButler repo", ""): (
        "deferred #248",
        [
            "On a GitButler repo, `finish.sh`'s undo plan SHALL emit a script that stops unless the touched paths have no uncommitted change, moves the archived directories back, restores the main specs from the pre-archive commit by writing each file from `git cat-file --filters`, and commits exactly those paths to the change branch with `but commit -b <branch>`. The script SHALL run no Git write.",
        ],
    ),
    ("vcs-backends", "The archive undo plan uses jj on a jj repo", ""): (
        "deferred #247",
        [
            "On a jj repo, `finish.sh`'s undo plan SHALL emit a script that:",
        ],
    ),
    ("vcs-backends", "The archive undo plan uses jj on a jj repo", "Wrong branch"): (
        "deferred #247",
        [
            "- **THEN** finish.sh exits with its wrong-branch error and emits no script",
        ],
    ),
    ("vcs-backends", "sw vcs documents keep their values and refuse non-UTF-8 names", ""): (
        "kept history",
        [
            "Each `sw vcs` document SHALL parse to the keys, order and values `vcs.sh` printed. A malformed argument SHALL be refused as native-cli \"Arguments sw cannot represent are refused\" states. A name that is not valid UTF-8, met in a listing or `git` or `jj` output that `sw vcs` reports or acts on, SHALL stop it before any write: `\"error\": \"not_utf8\"`, exit 1, a `message` showing each invalid byte as `\\xHH` (U+FFFD for a walk-found name) and asking for a rename. `but` output is read as before.",
        ],
    ),
    ("vcs-backends", "sw vcs keeps vcs.sh's output and exit-code contract", ""): (
        "header match key, kept history",
        [
            "### Requirement: sw vcs keeps vcs.sh's output and exit-code contract",
            "`sw vcs <sub>` SHALL accept the subcommands and options shipped callers pass and SHALL print exactly one JSON document on stdout for each run, with the same parsed fields, error codes and messages as `vcs.sh` for the same inputs, except that the wording of a usage error is free. It SHALL exit 0 on success, 1 on a stop, 2 on a usage error and 3 on a network or fence refusal. An unexpected failure SHALL be the document `\"error\": \"internal_error\"` with exit 1, never a stack trace on stdout.",
        ],
    ),
    ("vcs-backends", "sw vcs reads settings and fences identity in process", "Refused fence"): (
        "sw output string",
        [
            "- **THEN** the document has `\"error\": \"fence_failed\"`, a `message` that starts with `as.sh:` and masks the userinfo as `***`, the exit status is 3, and no push ran",
        ],
    ),
    ("vcs-backends", "sw vcs reads settings and fences identity in process", "Settings read through pr-pair.sh"): (
        "header match key",
        [
            "#### Scenario: Settings read through pr-pair.sh",
        ],
    ),
}

OPS = ("RENAMED", "REMOVED", "MODIFIED", "ADDED")
REQ_PREFIX = "### Requirement:"
SCEN_PREFIX = "#### Scenario:"


def split_blocks(lines):
    """Split lines into ordered (header text, block lines) requirement blocks."""
    blocks = []
    cur = None
    for line in lines:
        s = line.rstrip()
        if s.startswith(REQ_PREFIX):
            cur = (s[len(REQ_PREFIX):].strip(), [s])
            blocks.append(cur)
        elif s.startswith("## ") or (s.startswith("### ") and not s.startswith(REQ_PREFIX)):
            cur = None
        elif cur is not None:
            cur[1].append(s)
    return blocks


def parse_main(path):
    return split_blocks(path.read_text(encoding="utf-8").splitlines())


def _clean(s):
    return s.strip().strip("`").strip()


def parse_delta(path):
    """Return {op: [...]}: block lists for MODIFIED/ADDED, header names for REMOVED, pairs for RENAMED."""
    lines = path.read_text(encoding="utf-8").splitlines()
    sections = {}
    op = None
    sect = {}
    for line in lines:
        m = re.match(r"##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements", line.strip())
        if m:
            op = m.group(1)
            sect[op] = []
        elif line.startswith("## "):
            op = None
        elif op is not None:
            sect[op].append(line)
    out = {"ADDED": [], "MODIFIED": [], "REMOVED": [], "RENAMED": []}
    for op, body in sect.items():
        if op in ("ADDED", "MODIFIED"):
            out[op] = split_blocks(body)
        elif op == "REMOVED":
            out[op] = [h for h, _ in split_blocks(body)]
            if not out[op]:
                out[op] = [_clean(l.split(":", 1)[1])[len("### Requirement:"):].strip()
                           for l in body if l.strip().startswith("- ") and "Requirement:" in l]
        else:
            frm = None
            for l in body:
                t = l.strip()
                if t.startswith("- FROM:"):
                    frm = _clean(t[len("- FROM:"):])
                elif t.startswith("- TO:") and frm is not None:
                    out[op].append((_strip_req(frm), _strip_req(_clean(t[len("- TO:"):]))))
                    frm = None
    return out


def _strip_req(h):
    return h[len(REQ_PREFIX):].strip() if h.startswith(REQ_PREFIX) else h.strip()


def is_parked(change_dir):
    review = change_dir / "review.md"
    if not review.is_file():
        return False
    return any(l.strip("\r") == "VERDICT: DEFERRED"
               for l in review.read_text(encoding="utf-8").splitlines())


def active_changes(root):
    base = root / "openspec" / "changes"
    if not base.is_dir():
        return []
    return sorted(d for d in base.iterdir()
                  if d.is_dir() and d.name != "archive" and not is_parked(d))


def overlay(root):
    """Return ({cap: {header: lines}}, problems): main specs with the active deltas applied."""
    root = Path(root)
    caps = {}
    specs = root / "openspec" / "specs"
    if specs.is_dir():
        for d in sorted(specs.iterdir()):
            f = d / "spec.md"
            if f.is_file():
                caps[d.name] = dict(parse_main(f))
    problems = []
    touched = {}  # (cap, header) -> change name
    deltas = []
    for ch in active_changes(root):
        cdir = ch / "specs"
        if not cdir.is_dir():
            continue
        for d in sorted(cdir.iterdir()):
            f = d / "spec.md"
            if f.is_file():
                deltas.append((ch.name, d.name, parse_delta(f)))
    for change, cap, delta in deltas:
        headers = ([h for _, h in delta["RENAMED"]] + [h for h, _ in delta["RENAMED"]]
                   + delta["REMOVED"] + [h for h, _ in delta["MODIFIED"]])
        for h in headers:
            key = (cap, h)
            prev = touched.get(key)
            if prev is not None and prev != change:
                problems.append(
                    "%s: requirement %r is touched by two active changes: %s and %s"
                    % (cap, h, prev, change))
            touched.setdefault(key, change)
    for change, cap, delta in deltas:
        reqs = caps.setdefault(cap, {})
        for old, new in delta["RENAMED"]:
            if old not in reqs:
                problems.append("%s: change %s renames %r, which does not exist" % (cap, change, old))
                continue
            block = reqs.pop(old)
            block[0] = "%s %s" % (REQ_PREFIX, new)
            reqs[new] = block
        for h in delta["REMOVED"]:
            if reqs.pop(h, None) is None:
                problems.append("%s: change %s removes %r, which does not exist" % (cap, change, h))
        for h, block in delta["MODIFIED"]:
            if h not in reqs:
                problems.append("%s: change %s modifies %r, which does not exist" % (cap, change, h))
            reqs[h] = block
        for h, block in delta["ADDED"]:
            reqs[h] = block
    return caps, problems


def sub_blocks(header, lines):
    """Yield (scenario header text or "", lines) sub-blocks of one requirement block."""
    subs = [("", [])]
    for line in lines:
        if line.startswith(SCEN_PREFIX):
            subs.append((line[len(SCEN_PREFIX):].strip(), [line]))
        else:
            subs[-1][1].append(line)
    return subs


def found_blocks(root):
    """Return ({(cap, req, scenario): [lines naming a retired name]}, problems)."""
    caps, problems = overlay(root)
    found = {}
    for cap in sorted(caps):
        for header, lines in caps[cap].items():
            for scen, sub in sub_blocks(header, lines):
                hits = [l for l in sub if NAME_RE.search(l)]
                if hits:
                    found[(cap, header, scen)] = hits
    return found, problems


def check(root, allowed):
    """Return problem messages: overlay faults plus every block that differs from `allowed`."""
    found, problems = found_blocks(root)
    problems = list(problems)
    for key in sorted(set(found) | set(allowed)):
        cap, req, scen = key
        where = "%s / %s%s" % (cap, req, " / scenario: %s" % scen if scen else " (description)")
        have = found.get(key, [])
        want = list(allowed[key][1]) if key in allowed else []
        if have == want:
            continue
        if key not in allowed:
            problems.append("%s: new mention, add an ALLOWED entry with a reason or reword:\n%s"
                            % (where, "\n".join("    + " + l for l in have)))
        elif not have:
            problems.append("%s: allowed block no longer names a retired name, remove its ALLOWED entry"
                            % where)
        else:
            lines = ["    - " + l for l in want if l not in have]
            lines += ["    + " + l for l in have if l not in want]
            if not lines:
                lines = ["    (same lines, different count or order)"]
            problems.append("%s: lines differ from ALLOWED (- allowed only, + found only):\n%s"
                            % (where, "\n".join(lines)))
    return problems


def summary(problems):
    return "%d problem(s):\n%s" % (len(problems), "\n".join(problems))


class RealTreeTests(unittest.TestCase):
    def test_retired_names_only_in_allowed_blocks(self):
        problems = check(ROOT, ALLOWED)
        if problems:
            reqs = sorted({(c, r) for (c, r, _) in found_blocks(ROOT)[0]})
            listing = "\n".join("  %s / %s" % cr for cr in reqs)
            self.fail("%s\n\nrequirements naming a retired name: %d\n%s"
                      % (summary(problems), len(reqs), listing))


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def spec(*reqs):
    return "# cap\n\n## Requirements\n\n" + "\n".join(reqs)


def req(name, body="Text.", scenarios=()):
    out = "### Requirement: %s\n%s\n" % (name, body)
    for s, b in scenarios:
        out += "\n#### Scenario: %s\n- %s\n" % (s, b)
    return out


def delta(**sections):
    out = ""
    for op in OPS:
        if op in sections:
            out += "## %s Requirements\n\n%s\n" % (op, sections[op])
    return out


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def main(self, cap, *reqs):
        write(self.root, "openspec/specs/%s/spec.md" % cap, spec(*reqs))

    def change(self, name, cap, **sections):
        write(self.root, "openspec/changes/%s/specs/%s/spec.md" % (name, cap), delta(**sections))

    ALLOW = {("c", "A", ""): ("kept history", ["Runs `vcs.sh` here."])}

    def base(self):
        self.main("c", req("A", "Runs `vcs.sh` here."), req("B", "Clean."))

    def test_allowed_block_passes(self):
        self.base()
        self.assertEqual(check(self.root, self.ALLOW), [])

    def test_new_mention_fails(self):
        self.main("c", req("A", "Runs `vcs.sh` here."), req("B", "Calls finish.sh now."))
        msgs = check(self.root, self.ALLOW)
        self.assertEqual(len(msgs), 1)
        self.assertIn("c / B", msgs[0])
        self.assertIn("finish.sh", msgs[0])

    def test_new_mention_in_scenario_fails(self):
        self.main("c", req("A", "Runs `vcs.sh` here.", [("S", "uses as.sh")]))
        msgs = check(self.root, self.ALLOW)
        self.assertEqual(len(msgs), 1)
        self.assertIn("scenario: S", msgs[0])

    def test_second_mention_in_allowed_block_fails(self):
        self.main("c", req("A", "Runs `vcs.sh` here.\nAlso `vcs.sh` again."))
        msgs = check(self.root, self.ALLOW)
        self.assertEqual(len(msgs), 1)
        self.assertIn("Also `vcs.sh` again.", msgs[0])

    def test_moved_line_fails(self):
        self.main("c", req("A", "Intro.", [("S", "Runs `vcs.sh` here.")]))
        msgs = check(self.root, self.ALLOW)
        self.assertEqual(len(msgs), 2)  # the description entry is gone, the scenario is new
        self.assertTrue(any("remove its ALLOWED entry" in m for m in msgs))
        self.assertTrue(any("scenario: S" in m and "new mention" in m for m in msgs))

    def test_changed_wording_fails(self):
        self.main("c", req("A", "Runs `vcs.sh` there."))
        msgs = check(self.root, self.ALLOW)
        self.assertEqual(len(msgs), 1)
        self.assertIn("- Runs `vcs.sh` here.", msgs[0])
        self.assertIn("+ Runs `vcs.sh` there.", msgs[0])

    def test_removed_mention_fails(self):
        self.main("c", req("A", "Runs `sw vcs` here."))
        msgs = check(self.root, self.ALLOW)
        self.assertEqual(len(msgs), 1)
        self.assertIn("c / A", msgs[0])
        self.assertIn("remove its ALLOWED entry", msgs[0])

    def test_whole_names_only(self):
        self.main("c", req("A", "Has alias.sh, sw-as.sh, my.vcs.sh, release.sh.bak and `as.sh:` and skills/x/scripts/finish.sh."))
        found, _ = found_blocks(self.root)
        (line,) = found[("c", "A", "")]
        hits = NAME_RE.findall(line)
        self.assertEqual(hits, ["as.sh", "finish.sh"])

    def test_active_change_deltas_are_overlaid(self):
        self.base()
        self.change("ch1", "c", ADDED=req("D", "Calls `release.sh`."),
                    MODIFIED=req("A", "Runs `sw vcs` here."))
        found, problems = found_blocks(self.root)
        self.assertEqual(problems, [])
        self.assertEqual(set(found), {("c", "D", "")})

    def test_removed_and_renamed_overlay(self):
        self.main("c", req("A", "Runs `vcs.sh` here."), req("B", "Fine."))
        self.change("ch1", "c", RENAMED="- FROM: `### Requirement: A`\n- TO: `### Requirement: A2`",
                    REMOVED="### Requirement: B\n")
        found, problems = found_blocks(self.root)
        self.assertEqual(problems, [])
        self.assertEqual(set(found), {("c", "A2", "")})
        self.assertEqual(found[("c", "A2", "")], ["Runs `vcs.sh` here."])

    def test_archived_change_is_skipped(self):
        self.base()
        self.change("archive/2026-01-01-old", "c", ADDED=req("D", "Calls `release.sh`."))
        self.assertEqual(check(self.root, self.ALLOW), [])

    def test_parked_change_is_skipped(self):
        self.base()
        self.change("parked", "c", ADDED=req("D", "Calls `release.sh`."))
        write(self.root, "openspec/changes/parked/review.md", "# Review\n\nVERDICT: DEFERRED\n")
        self.assertEqual(check(self.root, self.ALLOW), [])

    def test_review_without_exact_deferred_line_is_not_parked(self):
        self.base()
        self.change("live", "c", ADDED=req("D", "Calls `release.sh`."))
        write(self.root, "openspec/changes/live/review.md", "VERDICT: DEFERRED later\n")
        self.assertEqual(len(check(self.root, self.ALLOW)), 1)

    def _collision(self, first, second):
        self.base()
        self.change("ch1", "c", **first)
        self.change("ch2", "c", **second)
        msgs = check(self.root, self.ALLOW)
        coll = [m for m in msgs if "two active changes" in m]
        self.assertEqual(len(coll), 1, msgs)
        self.assertIn("ch1", coll[0])
        self.assertIn("ch2", coll[0])

    def test_collision_modified_modified(self):
        self._collision({"MODIFIED": req("B", "One.")}, {"MODIFIED": req("B", "Two.")})

    def test_collision_modified_removed(self):
        self._collision({"MODIFIED": req("B", "One.")}, {"REMOVED": "### Requirement: B\n"})

    def test_collision_removed_removed(self):
        self._collision({"REMOVED": "### Requirement: B\n"}, {"REMOVED": "### Requirement: B\n"})

    def test_collision_renamed_source_and_modified(self):
        self._collision({"RENAMED": "- FROM: `### Requirement: B`\n- TO: `### Requirement: B2`"},
                        {"MODIFIED": req("B", "Two.")})

    def test_collision_renamed_destination_and_modified(self):
        self._collision({"RENAMED": "- FROM: `### Requirement: B`\n- TO: `### Requirement: B2`"},
                        {"MODIFIED": req("B2", "Two.")})

    def test_collision_renamed_destinations(self):
        self._collision({"RENAMED": "- FROM: `### Requirement: B`\n- TO: `### Requirement: Z`"},
                        {"RENAMED": "- FROM: `### Requirement: A`\n- TO: `### Requirement: Z`"})

    def test_collision_renamed_source_and_removed(self):
        self._collision({"RENAMED": "- FROM: `### Requirement: B`\n- TO: `### Requirement: B2`"},
                        {"REMOVED": "### Requirement: B\n"})

    def test_one_change_renamed_and_modified_gives_archive_text(self):
        self.main("c", req("A", "Old `vcs.sh` text."), req("B", "Keep."))
        self.change("ch1", "c",
                    RENAMED="- FROM: `### Requirement: A`\n- TO: `### Requirement: A2`",
                    MODIFIED=req("A2", "New `sw vcs` text.", [("S", "then")]))
        caps, problems = overlay(self.root)
        self.assertEqual(problems, [])
        self.assertEqual(list(caps["c"]), ["B", "A2"])
        self.assertEqual(
            caps["c"]["A2"],
            ["### Requirement: A2", "New `sw vcs` text.", "", "#### Scenario: S", "- then", ""])


if __name__ == "__main__":
    unittest.main()
