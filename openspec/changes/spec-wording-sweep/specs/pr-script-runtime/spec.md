# Spec Delta

## MODIFIED Requirements

### Requirement: Unexpected failures keep the JSON error contract
Each of the `sw pr` subcommands that `pr-pair.sh` carried (`identity`, `context`, `tier`, `vcs`, `discover`, `expected`, `ensure-pr`, `closing-check`, `closed-check`, `link`, `pair-state`, `rounds`, `pass`, `cleanup-plan`, `branch-check`, `merge`, `delete-remote`, `policy` and `item-issues`) SHALL report any unexpected exception as one JSON line on stdout with `"ok": false`, `"error": "internal_error"` and a `message` naming the exception type, and SHALL exit 1. Existing structured stops SHALL keep their own error codes and exit statuses.

#### Scenario: Filesystem error during pass write
- **WHEN** `pass write` runs and the record's parent directory path is an existing regular file
- **THEN** stdout is a single JSON line with `"error": "internal_error"`, the exit status is 1, and stderr contains no `Traceback`

#### Scenario: Existing structured stop
- **WHEN** `pass write` runs for a round whose record already exists
- **THEN** it reports the same error code and exit status as before this change

#### Scenario: Unexpected failure in a ported subcommand
- **WHEN** `sw pr context` meets an unexpected exception while it writes the reviewer config
- **THEN** stdout is a single JSON line with `"error": "internal_error"` and a message naming the exception type, the exit status is 1, and stderr holds no Dart stack trace

### Requirement: PR scripts remove their temp files on every exit
Every temp file a `sw pr` command creates SHALL be removed when the command exits, whether it succeeds, fails or stops on a structured error. A skill step that tells the agent to write a body or message to a temp file SHALL also tell it to remove that file once the command that reads it has run, whatever that command's outcome.

#### Scenario: Reply posted
- **WHEN** `sw pr reply` posts a reply and exits 0
- **THEN** no temp file it created remains

#### Scenario: Post fails
- **WHEN** `sw pr reply` has written its reply temp file and the GitHub call that posts it fails
- **THEN** the command exits non-zero and no temp file it created remains

#### Scenario: Pending review stop after the reply
- **WHEN** a thread reply was posted and the following pending-review check exits 2
- **THEN** no temp file it created remains

#### Scenario: Skill steps that write body files
- **WHEN** the `specwright-pr` text tells the agent to write a PR description, review request, reply or issue body to a temp file
- **THEN** the same step tells the agent to remove that file after the command that reads it

### Requirement: Network commands have a deadline
Every `gh` or `git` network command run by the `sw pr` pair subcommands, `sw pr snapshot` or `sw pr reply`, and every credential or identity lookup `sw as` makes before it runs the command it fences, SHALL run under a deadline: 120 seconds, or 300 seconds for a paginated read. When the deadline passes, the command and every process it started SHALL be stopped, and `sw` SHALL report `deadline_exceeded`, naming the command. It SHALL NOT wait for the command.

#### Scenario: GitHub answers in time
- **WHEN** `sw pr closing-check` runs and every `gh` call answers within its deadline
- **THEN** the check reports its result as before this change, and no `deadline_exceeded` appears

#### Scenario: Hung gh call in pr-pair.sh
- **WHEN** `sw pr discover` runs and its `gh api` call never answers
- **THEN** the command exits 3 within the deadline plus 10 seconds, with one JSON line holding `"error": "deadline_exceeded"` and a message naming `gh api`, and no `gh` process it started is still running

#### Scenario: Hung gh call in a bash PR script
- **WHEN** `sw pr reply` posts a reply and its `gh api` call never answers
- **THEN** the command exits non-zero within the deadline plus 10 seconds, stderr names `deadline_exceeded` and the command, and no temp file it created remains

#### Scenario: Hung credential lookup in as.sh
- **WHEN** `sw as <login> gh ...` runs and its `gh auth token` lookup never answers
- **THEN** `sw as` exits 3 within the deadline plus 10 seconds, names `deadline_exceeded` on stderr, and does not run the fenced command

### Requirement: GitHub responses are bounded
The `sw pr` pair subcommands, `sw pr snapshot` and `sw pr reply` SHALL read at most 32 MiB from any one `gh` or `git` network command they run, paginated reads included, and `sw as` at most 32 MiB from any credential or identity lookup it makes; the `sw pr` commands SHALL read at most 50 pages in any cursor loop they drive themselves. Passing either bound SHALL stop the command and be reported as `response_too_large`, naming the command. It SHALL NOT yield a partial result.

#### Scenario: Large but bounded list
- **WHEN** `sw pr discover` reads a paginated list whose pages total 2 MiB
- **THEN** the command reads all of it and answers as before this change

#### Scenario: Oversized paginated read
- **WHEN** a paginated `gh api` read in a `sw pr` pair subcommand prints more than 32 MiB
- **THEN** the command exits 3 with `"error": "response_too_large"` naming the command, and reports no partial list as the answer

#### Scenario: Reaction loop past its page cap
- **WHEN** `pass plan` looks for a reaction, and the reactions it pages through never contain it and have more than 50 pages
- **THEN** the command exits 3 with `"error": "response_too_large"`, and does not report the reaction as absent

### Requirement: Watch claims and head records stay shared across implementations
`sw pr snapshot` SHALL read and write watch claims under `<state>/watch/v2/<owner>/<name>/<pr>/` (lower case) and head records under `<state>/heads/`, where `<state>` is `SPECWRIGHT_STATE_DIR`, else `$HOME/.cache/specwright`, with the file names and contents `pr-snapshot.sh` used before this change, so `sw pr` and a watcher of either implementation see each other's claims and records.

#### Scenario: A newer sw watcher takes over an older script watcher
- **WHEN** a watcher run by the `pr-snapshot.sh` from before this change waits on PR 12, and a `sw pr snapshot 12 --wait` watcher starts for the same PR
- **THEN** the older watcher exits 4 before its next poll, and the new watcher owns the PR

#### Scenario: Equal claim numbers across implementations (accepted gap)
- **WHEN** an old-script watcher and an `sw` watcher create claims with the same number on PR 12 within one directory listing
- **THEN** `sw` picks the owner by comparing the nonces as bytes, the old script compares them by the locale's collation, and the two may each see themselves as owner. This is accepted and is not a parity failure. If a duplicate owner is ever seen in a run, the gap is reconsidered

#### Scenario: State directory cannot be created
- **WHEN** `SPECWRIGHT_STATE_DIR` names a path under a regular file and `sw pr snapshot 12 --wait` runs
- **THEN** stderr says `pr-snapshot: cannot create the watch state directory; ownership is off for PR 12 (this watcher polls unowned)` and the watch goes on unowned

### Requirement: The ported pr-pair subcommands keep the script's contracts
`sw pr identity`, `vcs`, `tier`, `context` and `policy` SHALL accept the argument forms shipped callers use, print a JSON line with the same parsed fields and values, and exit with the same status for the same settings files, repositories and GitHub answers, apart from the native-cli JSON, input and option differences. That covers the settings problems, the reviewer-config bytes (apart from `"format": 2`), path and digest, the GitButler pin, and the policy checks.

#### Scenario: Policy's remote settings read is strict
- **WHEN** `policy` reads a settings file from the remote and the settings reader refuses it, or it holds a duplicate key, or a section has the wrong shape
- **THEN** `policy` stops with `lookup_failed` and merges nothing, and never decides from a best-effort parse

#### Scenario: Git Bash path forms
- **WHEN** on Windows Git Bash runs a subcommand with a directory or snapshot file given as `/c/work/repo`
- **THEN** `sw` receives `C:/work/repo`, converted by Git Bash, reads that repository or file, and a path it reports is in the `C:/` form

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the `evals/pr-pair` and `evals/vcs` tests that run these five subcommands run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from the format migration (D10): the expected `"format"` value, the reviewer-config digests and content-addressed paths derived from it, and the format refused by the config check; the regex dialect cases (pr-evidence); assertions on free text, which check its prefix instead (see the message-text requirement); assertions on stdout bytes, which compare the parsed value instead; and the settings cases `native-cli-yaml-settings` changed, which assert the value read or the stop reported. The native-cli JSON/input and option differences have explicit outcome tests; every other field, error code and exit status is compared exactly

#### Scenario: Differential run against the frozen script
- **WHEN** the parity eval runs each case of each subcommand through `sw pr`, against the repositories and fake-gh state the case builds, and compares it with the record the frozen `pr-pair.sh` produced for that case, captured in the commit before the scripts were removed
- **THEN** `sw pr` exits with the recorded status and makes the recorded `gh` calls for inputs retained by the native-cli contract; documented JSON/input and option refusals keep their explicit difference tests. Stderr lines match the record up to each line's prefix, and stdout parses to the recorded JSON value apart from free text compared by its prefix, `reviewer_config` digests and paths, which name `sw pr`'s own `"format": 2` file, the listed settings differences with their own outcome tests, and `cleanup-plan`'s printed commands, which this change moves from `bash .../as.sh`, `vcs.sh` and `pr-pair.sh` to `<sw> --project <code> ...`: their decisions, guards, order and `gh` calls match the record, and their argv, working directory and project selection are asserted on their own. Records hold no paths of the machine that made them. A run-generated feedback owner id in `pass write` stdout is checked to equal the owner in the record that run wrote and is then replaced by a placeholder before the comparison, and persisted write and adopt times are checked against the run, as the live matrix did. Fixture commits are made with a pinned author, committer and dates, so their ids repeat across runs and `lacking[].sha` is compared exactly; the final fake-gh state and each written comment body are recorded and compared byte for byte

#### Scenario: A malformed settings file names its line
- **WHEN** `openspec/specwright.yaml` holds a tab in its indentation on line 7 and `sw pr context --code <code>` runs
- **THEN** it exits 2 with `"error": "bad_setting"` and a `message` naming `line 7`, and prints no settings values

#### Scenario: Settings not pinned on GitButler
- **WHEN** `vcs` is `gitbutler`, the work-tree `openspec/specwright.yaml` differs from the one committed on `feat/a`, and `sw pr context --code <code> --branch feat/a` runs
- **THEN** it exits 1 with `"error": "settings_not_pinned"`, naming the file and the ref, as before this change

### Requirement: Message text of the ported subcommands may be reworded
Free text in dispatched `sw pr` commands and `reviewers` MAY be reworded after stable prefixes. Other representations MAY change with their consuming skills when explicit contract tests prove the same workflow outcomes. Identity, mutation guards, ownership and recovery SHALL remain intact. Retained interfaces keep their existing values/statuses; persisted records remain interoperable. Incidental Python formatting and parser quirks SHALL NOT require byte-for-byte replicas.

#### Scenario: A reworded stop keeps its code
- **WHEN** `sw pr policy` reads a default-branch settings file whose content is not valid base64
- **THEN** stdout has `"error": "lookup_failed"` and the exit status is 3, as before this change, and `message` starts with `merge policy unknown: unreadable openspec/specwright.yaml at <ref>:`

#### Scenario: Workflow error keeps structured values
- **WHEN** native `ensure-pr` finds an open PR targeting another base
- **THEN** it returns `wrong_base` with the same PR and base values and exit status as the frozen script, without creating a PR

### Requirement: Settings are read by one YAML parser
Every Specwright command that reads `openspec/specwright.yaml`, from the work tree, a committed ref or GitHub, SHALL read it with one YAML parser and apply the same refusals to every read. A file the reader refuses SHALL give no values: no command decides from part of a file. A refusal SHALL name the 1-based line it found and why. An empty, whitespace-only or comment-only file SHALL read as an empty mapping; any other top level that is not a mapping SHALL be refused.

#### Scenario: The same file read locally and remotely
- **WHEN** main's `openspec/specwright.yaml` is this repository's settings file and `sw pr context` reads the work-tree copy while `policy` reads the copy on GitHub
- **THEN** both read the same values for `pr.merge`, `pr.merge_method`, `pr.delete_branch` and `pr.reviewers`, and `policy` reports no difference

#### Scenario: A file the parser refuses
- **WHEN** `openspec/specwright.yaml` holds a tab in its indentation on line 7
- **THEN** every reader refuses it naming `line 7`, and none of them reads a value from the lines before or after it

#### Scenario: A comment-only file
- **WHEN** the work-tree settings hold only comments and blank lines and `sw pr context --code <code>` runs, and main's settings on GitHub are the same file when `policy` reads them
- **THEN** `context` exits 0 with the defaults, and `policy` reads main's policy as `pr.merge: user`

#### Scenario: A top level that is not a mapping
- **WHEN** the settings file holds only `- pr`, a list, in the work tree and at the ready head
- **THEN** `sw pr context` exits 2 with `bad_setting` naming `line 1`, and `policy` exits 3 with `lookup_failed`

### Requirement: A refused settings file stops each reader
A local read of a settings file the reader refuses SHALL stop the command before any git write, network call or file write: the `sw pr` subcommands that read the settings and `sw vcs` with `bad_setting` and exit 2, the review runner and the release subcommands with `bad_settings` and exit 1, and `policy`'s remote read with `lookup_failed` and exit 3. `tier` SHALL instead exit 0 with the cheap tier off and a `note` naming the line. A missing file SHALL stay an empty settings file.

#### Scenario: Ship stops on a refused file
- **WHEN** the work-tree settings hold a duplicate `pr:` key on line 30 and ship runs `sw pr context --code <code>`
- **THEN** it exits 2 with `"error": "bad_setting"` and a `message` naming `openspec/specwright.yaml` and `line 30`, and ship pushes nothing

#### Scenario: A VCS write stops on a refused file
- **WHEN** the settings hold a tab in their indentation and `sw vcs commit --branch feat/a --message-file m -- a.txt` runs
- **THEN** it exits 2 with `"error": "bad_setting"` naming the line, and no commit is made

#### Scenario: The cheap tier on a refused file
- **WHEN** the settings hold a tab in their indentation and `sw pr tier --code <code>` runs
- **THEN** it exits 0 with `"cheap_tier": false` and a `note` naming the line

#### Scenario: No settings file
- **WHEN** the code checkout has no `openspec/specwright.yaml` and `sw pr context --code <code>` runs
- **THEN** it exits 0 with the defaults it gave before this change

### Requirement: Commands that read no settings keep their behaviour
A command that reads no settings today, such as `sw pr identity`, SHALL keep its behaviour when the settings file is refused, and SHALL NOT start reading the settings in this change.

#### Scenario: Identity on a refused file
- **WHEN** the settings hold a tab in their indentation and `sw pr identity <code>` runs
- **THEN** it prints the repository identity it printed before this change and exits 0

#### Scenario: Identity on a missing directory
- **WHEN** `sw pr identity` is given a directory that does not exist
- **THEN** it stops with the error it gave before this change, and names no settings problem

### Requirement: A boolean written yes or no is refused
The reader SHALL refuse any unquoted value `yes` or `no`, in any letter case, anywhere in the file, naming its line and saying to write `true` or `false`. A quoted `'yes'` or `"no"` SHALL be read as a string, and `on`, `off`, `y` and `n` SHALL stay strings as before this change.

#### Scenario: true and false
- **WHEN** the settings hold `review:` with `preship: false` and `pr:` with `react: true`
- **THEN** every reader reads `preship` as false and `react` as true

#### Scenario: A yes boolean
- **WHEN** line 12 of the settings is `  react: yes` and `sw pr context --code <code>` runs
- **THEN** it exits 2 with `"error": "bad_setting"` and a `message` naming `line 12`, `yes`, `true` and `false`

#### Scenario: A capitalised no
- **WHEN** a settings line is `  enabled: No` under `release:` and `sw release check` runs
- **THEN** it exits 1 with `error: bad_settings` naming the line, `true` and `false`, and no git call is made

#### Scenario: A quoted yes
- **WHEN** a reviewer's `request` is written `'yes'`
- **THEN** the settings are read and the request comment is the string `yes`

### Requirement: Settings constructs a settings file never needs are refused
The reader SHALL refuse a duplicate key in any mapping, an anchor, an alias, a tag, a non-finite number (`.nan`, `.inf`, `-.inf` in any case YAML reads as one) and a second document, naming the line of the first. Block sequences, flow collections, and quoted, plain and `|`/`>` block scalars SHALL read as YAML 1.2 defines them, including valid YAML the old reader skipped, misread or refused. Messages SHALL show each plain or quoted scalar (quotes kept) and each flow collection as written.

#### Scenario: A non-finite number
- **WHEN** a settings line is `  delete_branch: .inf`
- **THEN** every reader refuses the file naming that line

#### Scenario: A quoted empty value in a message
- **WHEN** the settings hold `merge: agent` and `merge_method: ''` under `pr:` and `sw pr context --code <code>` runs
- **THEN** it exits 2 with `bad_setting`, and its message names `pr.merge_method: ''`, the value as written

#### Scenario: A duplicate key in a reviewer
- **WHEN** a reviewer under `pr.reviewers` gives `role:` twice, the second time on line 41
- **THEN** every reader refuses the file naming `line 41`

#### Scenario: An alias
- **WHEN** the settings define `&r` on one reviewer and use `*r` for another
- **THEN** every reader refuses the file naming the line of the anchor or the alias

#### Scenario: A block sequence
- **WHEN** `review.order` is written as a block sequence of `codex`, `claude` and `omp`, one `- ` item per line
- **THEN** the review route order is `codex`, `claude`, `omp`, as for `order: [codex, claude, omp]`

### Requirement: A settings value of the wrong shape stops each reader
Wherever a reader expects a mapping (the top level, `pr`, `planning_store`, `github`, `github.review_request`, `cheap_tier`, `review`, `release`, `pr.reviewers`, `planning_store.reviewers`, each reviewer entry and its `report`), a present key with another value SHALL stop the read with that reader's settings error naming the key, never coerced. An absent or null key SHALL keep its default; only an absent or null `planning_store.reviewers` SHALL inherit the code reviewer set.

#### Scenario: A reviewer written as a list
- **WHEN** a reviewer under `pr.reviewers` is written as a block list (`guard:` followed by `- role: required`) and `sw pr context --code <code>` runs
- **THEN** it exits 2 with `bad_setting` naming `pr.reviewers.guard`, and no reviewer config is written

#### Scenario: A reviewer written as a list, remotely
- **WHEN** main's and the head's settings both hold a reviewer written as a block or flow list, under `pr.reviewers` or `planning_store.reviewers`, and `policy` reads them
- **THEN** `policy` exits 3 with `lookup_failed` naming the key, writes no reviewer config, and authorizes no merge

#### Scenario: A report that is not a mapping
- **WHEN** a reviewer's `report` is `[check, x]`
- **THEN** every reader stops with its settings error naming `report`

#### Scenario: The cheap tier on a wrong shape
- **WHEN** `pr:` is a list and `sw pr tier --code <code>` runs
- **THEN** it exits 0 with `"cheap_tier": false` and a `note` naming `pr`

#### Scenario: A review section that is not a mapping
- **WHEN** `review:` is written as a block list, a flow list, a scalar or an empty string `''`, and the review runner starts
- **THEN** it exits 1 with `bad_settings` naming `review`, before any reviewer CLI is probed or run

#### Scenario: A release or pr section that is not a mapping
- **WHEN** `release:` or `pr:` is written as a block list, a flow list, a scalar or an empty string `''`, and `sw release check` runs
- **THEN** it exits 1 with `bad_settings` naming the key, and no git call is made

#### Scenario: A flow list in a message
- **WHEN** the settings hold `reviewers: [a, b]` under `pr:` and `sw pr context --code <code>` runs
- **THEN** it exits 2 with `bad_setting`, and its message names `pr.reviewers` and `[a, b]`, as written

### Requirement: Deeply nested settings stop without a crash
A settings file nested beyond any depth a reader can hold SHALL be refused with the reader's settings error naming a line, and SHALL never crash a command, print a stack trace or pass as valid.

#### Scenario: Ordinary nesting
- **WHEN** the settings nest `pr.reviewers.<login>.report.check` four levels deep
- **THEN** every reader reads the value

#### Scenario: A local file nested 100,000 levels
- **WHEN** the work-tree settings hold a flow mapping nested 100,000 levels deep and `sw pr context --code <code>` runs
- **THEN** it exits 2 with `"error": "bad_setting"` naming a line, and no stack trace is printed

#### Scenario: A remote file nested 100,000 levels
- **WHEN** the ready head's settings file on GitHub is nested 100,000 levels deep and `policy` reads it
- **THEN** `policy` exits 3 with `"error": "lookup_failed"` and merges nothing

### Requirement: Snapshots evaluate reviewers through sw
`sw pr snapshot` SHALL check the `--reviewer-config` file in its own process before any `gh` call. It SHALL decide reviewer states by running its own binary as `sw pr reviewers` under the deadline, byte bound and temp-file rules `reviewers.py` ran under, and SHALL read that child's document by parsing it. It SHALL start no Python evaluator and run no interpreter probe.

#### Scenario: Reviewer states decided in sw
- **WHEN** `<sw> pr snapshot 12 --reviewer-config cfg.json` runs and `cfg.json` lists `chatgpt-codex-connector[bot]` as a reviewer that has posted its report
- **THEN** that login's `reviewers` entry has the state `reviewers.py` decided before this change, `reviewer_config` holds the file's digest, and the evaluation ran as the bounded `sw pr reviewers` child, with no Python interpreter started

#### Scenario: A pattern that backtracks past the deadline
- **WHEN** a reviewer's `report.ignore` backtracks on a comment body for longer than the evaluator's deadline
- **THEN** the evaluation is stopped at the deadline, stderr holds the line `bounded: deadline_exceeded: reviewers.py python3`, the poll fails, and no evaluator process or material file is left

#### Scenario: Bad reviewer config
- **WHEN** `cfg.json` is not valid JSON and `<sw> pr snapshot 12 --reviewer-config cfg.json` runs
- **THEN** the exit status is 2, stderr holds one line prefixed `reviewers.py:` that says the file is not valid JSON, no `gh` call was made, and no child `sw` was started for the check

#### Scenario: No Python on PATH
- **WHEN** `<sw> pr snapshot` runs directly with failing `python` and `python3` first on `PATH` and a reviewer config
- **THEN** the snapshot and its reviewer states are printed with exit 0, neither interpreter ran, and stderr holds no `no_python` line

#### Scenario: Evaluator output that is not a document
- **WHEN** the `sw pr reviewers` child exits 0 but its stdout does not parse as one JSON document
- **THEN** the poll fails with exit 1 and prints no snapshot built from that output
