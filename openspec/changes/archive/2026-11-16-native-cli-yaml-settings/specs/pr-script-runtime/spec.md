# Spec Delta

## ADDED Requirements

### Requirement: Settings are read by one YAML parser
Every Specwright command that reads `openspec/specwright.yaml`, from the work tree, a committed ref or GitHub, SHALL read it with one YAML parser and apply the same refusals to every read. A file the reader refuses SHALL give no values: no command decides from part of a file. A refusal SHALL name the 1-based line it found and why. An empty, whitespace-only or comment-only file SHALL read as an empty mapping; any other top level that is not a mapping SHALL be refused.

#### Scenario: The same file read locally and remotely
- **WHEN** main's `openspec/specwright.yaml` is this repository's settings file and `pr-pair.sh context` reads the work-tree copy while `policy` reads the copy on GitHub
- **THEN** both read the same values for `pr.merge`, `pr.merge_method`, `pr.delete_branch` and `pr.reviewers`, and `policy` reports no difference

#### Scenario: A file the parser refuses
- **WHEN** `openspec/specwright.yaml` holds a tab in its indentation on line 7
- **THEN** every reader refuses it naming `line 7`, and none of them reads a value from the lines before or after it

#### Scenario: A comment-only file
- **WHEN** the work-tree settings hold only comments and blank lines and `pr-pair.sh context --code <code>` runs, and main's settings on GitHub are the same file when `policy` reads them
- **THEN** `context` exits 0 with the defaults, and `policy` reads main's policy as `pr.merge: user`

#### Scenario: A top level that is not a mapping
- **WHEN** the settings file holds only `- pr`, a list, in the work tree and at the ready head
- **THEN** `pr-pair.sh context` exits 2 with `bad_setting` naming `line 1`, and `policy` exits 3 with `lookup_failed`

### Requirement: A refused settings file stops each reader
A local read of a settings file the reader refuses SHALL stop the command before any git write, network call or file write: the `pr-pair.sh` subcommands that read the settings and `sw vcs` with `bad_setting` and exit 2, the review runner and the release subcommands with `bad_settings` and exit 1, and `policy`'s remote read with `lookup_failed` and exit 3. `tier` SHALL instead exit 0 with the cheap tier off and a `note` naming the line. A missing file SHALL stay an empty settings file.

#### Scenario: Ship stops on a refused file
- **WHEN** the work-tree settings hold a duplicate `pr:` key on line 30 and ship runs `pr-pair.sh context --code <code>`
- **THEN** it exits 2 with `"error": "bad_setting"` and a `message` naming `openspec/specwright.yaml` and `line 30`, and ship pushes nothing

#### Scenario: A VCS write stops on a refused file
- **WHEN** the settings hold a tab in their indentation and `vcs.sh commit --branch feat/a --message-file m -- a.txt` runs
- **THEN** it exits 2 with `"error": "bad_setting"` naming the line, and no commit is made

#### Scenario: The cheap tier on a refused file
- **WHEN** the settings hold a tab in their indentation and `pr-pair.sh tier --code <code>` runs
- **THEN** it exits 0 with `"cheap_tier": false` and a `note` naming the line

#### Scenario: No settings file
- **WHEN** the code checkout has no `openspec/specwright.yaml` and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 0 with the defaults it gave before this change

### Requirement: Commands that read no settings keep their behaviour
A command that reads no settings today, such as `pr-pair.sh identity`, SHALL keep its behaviour when the settings file is refused, and SHALL NOT start reading the settings in this change.

#### Scenario: Identity on a refused file
- **WHEN** the settings hold a tab in their indentation and `pr-pair.sh identity <code>` runs
- **THEN** it prints the repository identity it printed before this change and exits 0

#### Scenario: Identity on a missing directory
- **WHEN** `pr-pair.sh identity` is given a directory that does not exist
- **THEN** it stops with the error it gave before this change, and names no settings problem

### Requirement: A boolean written yes or no is refused
The reader SHALL refuse any unquoted value `yes` or `no`, in any letter case, anywhere in the file, naming its line and saying to write `true` or `false`. A quoted `'yes'` or `"no"` SHALL be read as a string, and `on`, `off`, `y` and `n` SHALL stay strings as before this change.

#### Scenario: true and false
- **WHEN** the settings hold `review:` with `preship: false` and `pr:` with `react: true`
- **THEN** every reader reads `preship` as false and `react` as true

#### Scenario: A yes boolean
- **WHEN** line 12 of the settings is `  react: yes` and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `"error": "bad_setting"` and a `message` naming `line 12`, `yes`, `true` and `false`

#### Scenario: A capitalised no
- **WHEN** a settings line is `  enabled: No` under `release:` and `release.sh check` runs
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
- **WHEN** the settings hold `merge: agent` and `merge_method: ''` under `pr:` and `pr-pair.sh context --code <code>` runs
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
- **WHEN** a reviewer under `pr.reviewers` is written as a block list (`guard:` followed by `- role: required`) and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `bad_setting` naming `pr.reviewers.guard`, and no reviewer config is written

#### Scenario: A reviewer written as a list, remotely
- **WHEN** main's and the head's settings both hold a reviewer written as a block or flow list, under `pr.reviewers` or `planning_store.reviewers`, and `policy` reads them
- **THEN** `policy` exits 3 with `lookup_failed` naming the key, writes no reviewer config, and authorizes no merge

#### Scenario: A report that is not a mapping
- **WHEN** a reviewer's `report` is `[check, x]`
- **THEN** every reader stops with its settings error naming `report`

#### Scenario: The cheap tier on a wrong shape
- **WHEN** `pr:` is a list and `pr-pair.sh tier --code <code>` runs
- **THEN** it exits 0 with `"cheap_tier": false` and a `note` naming `pr`

#### Scenario: A review section that is not a mapping
- **WHEN** `review:` is written as a block list, a flow list, a scalar or an empty string `''`, and the review runner starts
- **THEN** it exits 1 with `bad_settings` naming `review`, before any reviewer CLI is probed or run

#### Scenario: A release or pr section that is not a mapping
- **WHEN** `release:` or `pr:` is written as a block list, a flow list, a scalar or an empty string `''`, and `release.sh check` runs
- **THEN** it exits 1 with `bad_settings` naming the key, and no git call is made

#### Scenario: A flow list in a message
- **WHEN** the settings hold `reviewers: [a, b]` under `pr:` and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `bad_setting`, and its message names `pr.reviewers` and `[a, b]`, as written

### Requirement: Deeply nested settings stop without a crash
A settings file nested beyond any depth a reader can hold SHALL be refused with the reader's settings error naming a line, and SHALL never crash a command, print a stack trace or pass as valid.

#### Scenario: Ordinary nesting
- **WHEN** the settings nest `pr.reviewers.<login>.report.check` four levels deep
- **THEN** every reader reads the value

#### Scenario: A local file nested 100,000 levels
- **WHEN** the work-tree settings hold a flow mapping nested 100,000 levels deep and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `"error": "bad_setting"` naming a line, and no stack trace is printed

#### Scenario: A remote file nested 100,000 levels
- **WHEN** the ready head's settings file on GitHub is nested 100,000 levels deep and `policy` reads it
- **THEN** `policy` exits 3 with `"error": "lookup_failed"` and merges nothing

## MODIFIED Requirements

### Requirement: The ported pr-pair subcommands keep the script's contracts
`sw pr identity`, `vcs`, `tier`, `context` and `policy`, run through the shim, SHALL accept the argument forms shipped callers use, print a JSON line with the same parsed fields and values, and exit with the same status for the same settings files, repositories and GitHub answers, apart from the native-cli JSON, input and option differences. That covers the settings problems, the reviewer-config bytes (apart from `"format": 2`), path and digest, the GitButler pin, and the policy checks.

#### Scenario: Policy's remote settings read is strict
- **WHEN** `policy` reads a settings file from the remote and the settings reader refuses it, or it holds a duplicate key, or a section has the wrong shape
- **THEN** `policy` stops with `lookup_failed` and merges nothing, and never decides from a best-effort parse

#### Scenario: Git Bash path forms
- **WHEN** on Windows a subcommand is given a directory or snapshot file as a Git Bash path such as `/c/work/repo`
- **THEN** it reads the same repository or file as with `C:/work/repo`, and a path it reports is in the `C:/` form

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the `evals/pr-pair` and `evals/vcs` tests that run these five subcommands run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from the format migration (D10): the expected `"format"` value, the reviewer-config digests and content-addressed paths derived from it, and the format refused by the config check; the regex dialect cases (pr-evidence); assertions on free text, which check its prefix instead (see the message-text requirement); assertions on stdout bytes, which compare the parsed value instead; and the settings cases `native-cli-yaml-settings` changed, which assert the value read or the stop reported. The native-cli JSON/input and option differences have explicit outcome tests; every other field, error code and exit status is compared exactly

#### Scenario: Differential run against the frozen script
- **WHEN** the parity eval runs a case of each subcommand through the frozen copy of `pr-pair.sh` and through the shim, against the same repositories and fake-gh state
- **THEN** both exit with the same status and make the same `gh` calls for inputs retained by the native-cli contract; documented JSON/input and option refusals have explicit difference tests. For retained inputs they print stderr with the same lines up to each line's prefix. Their stdout parses to the same JSON value, apart from free text compared by its prefix and except that each `reviewer_config` digest and config path names that side's own file. Each side writes a reviewer config whose bytes are checked exactly on their own: the frozen script's with `"format": 1`, the shim's the same with `"format": 2`. Each file is named by the digest of its own bytes, and each digest field in stdout equals that digest. A settings file the one reader refuses, one holding a plain `yes` or `no`, or valid YAML the frozen script skipped, misread or refused only for that reason (a block sequence, a trailing flow comma), is a listed difference with its own outcome test

#### Scenario: A malformed settings file names its line
- **WHEN** `openspec/specwright.yaml` holds a tab in its indentation on line 7 and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `"error": "bad_setting"` and a `message` naming `line 7`, and prints no settings values

#### Scenario: Settings not pinned on GitButler
- **WHEN** `vcs` is `gitbutler`, the work-tree `openspec/specwright.yaml` differs from the one committed on `feat/a`, and `pr-pair.sh context --code <code> --branch feat/a` runs
- **THEN** it exits 1 with `"error": "settings_not_pinned"`, naming the file and the ref, as before this change
