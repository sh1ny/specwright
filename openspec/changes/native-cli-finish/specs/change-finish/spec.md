# Spec Delta

## ADDED Requirements

### Requirement: The undo plan runs in the project's sw
`finish.sh` SHALL keep its path, arguments and output contract, and SHALL build the undo plan by resolving the project's `sw` with the shared resolver and running `sw finish undo-archive-plan` with the same arguments. Its stdout, stderr and exit status SHALL be those of `sw`, and no other implementation of the plan SHALL remain in the script.

#### Scenario: Plan through a matching sw
- **WHEN** the project's `VERSION` reads `0.27.0`, the resolver finds a matching `sw` 0.27.0, and `finish.sh undo-archive-plan --change add-x --archived-name 2026-11-07-add-x --prefix openspec --main main` runs on a branch whose last commit archived `add-x`
- **THEN** stdout is the one JSON document `sw finish undo-archive-plan` printed, with `"ok": true`, `"mode": "committed"` and a `script` that begins with `set -euo pipefail`, and the exit status is 0

#### Scenario: Arguments reach sw unchanged
- **WHEN** `finish.sh undo-archive-plan` runs with `--prefix "my plans/openspec"` and a `--change` name holding a non-ASCII letter, both archived on the branch
- **THEN** `sw finish undo-archive-plan` receives both values byte for byte, and the document's member `name` and the printed undo subject name the change as given

#### Scenario: A refusal keeps its exit status
- **WHEN** the plan runs for a change with no archive directory in the working tree and no add commit on the branch
- **THEN** the exit status is 1 and stdout is one JSON document with `"error": "no_archive"`, as before this change

#### Scenario: Git Bash path on Windows
- **WHEN** on Windows `finish.sh --dir /c/<repo> undo-archive-plan ...` runs
- **THEN** the document equals the one for the same call with `--dir C:/<repo>`, and no `not_a_repo` is reported

#### Scenario: Path conversion fails on Windows
- **WHEN** on Windows `cygpath -m` fails for `finish.sh --dir /c/<repo> undo-archive-plan ...`
- **THEN** it exits 2 with `"error": "bad_path"` naming `/c/<repo>`, no Git command ran, and no script is printed

### Requirement: finish.sh finds the project from --code, then --dir
A relative `--code` SHALL be read from the planning repo (the first directory holding a `.git` entry at or above `--dir`, else at or above the current directory), as before this change. The project whose `sw` runs SHALL be the first directory holding a `.git` entry at or above `--code` when it names a directory, else at or above `--dir` when it names a directory, else at or above the current directory, found with no Git command. `--code` SHALL keep its existing meaning for the plan.

#### Scenario: Store-backed plan finds the code checkout's sw
- **WHEN** `finish.sh --dir <store> undo-archive-plan ... --code <code>` runs from inside the store, whose checkout has no `openspec/.specwright/VERSION`, and `<code>` holds a matching one
- **THEN** the resolver reads `<code>/openspec/.specwright/VERSION`, and the plan probes the store's own backend as before this change

#### Scenario: Store-backed call without --code
- **WHEN** `finish.sh --dir <store> undo-archive-plan ...` runs from inside the store with no `--code`, and the store has no `openspec/.specwright/VERSION`
- **THEN** it exits 1 with `"error": "sw_missing"` and a message saying no installed version was found, and no Git command ran

#### Scenario: Relative --code is read from the planning repo
- **WHEN** `finish.sh --dir <store> undo-archive-plan ... --code ../code` runs from a directory other than the store, where `<store>/../code` is the code checkout and `../code` from the caller is another checkout with other settings
- **THEN** the plan probes with `<store>/../code`'s settings, and its `sw` is the one that checkout's `VERSION` names, as before this change

### Requirement: A missing or mismatched sw stops the undo plan
When the resolver stops, `finish.sh` SHALL print one JSON document on stdout with `"ok": false`, `"error": "sw_missing"` and a `message` that starts with `sw missing or mismatched: rerun the install prompt`, copy the resolver's detail to stderr, and exit 1. It SHALL run no `git` command and print no script, and SHALL never fall back to another implementation, another version's binary or an `sw` on `PATH`.

#### Scenario: Binary missing
- **WHEN** the project's `VERSION` reads `0.27.0` and `<home>/.specwright/bin/0.27.0/` holds no `sw`
- **THEN** `finish.sh undo-archive-plan ...` exits 1, stdout is one JSON document with `"error": "sw_missing"` and no `script`, and no Git command ran

#### Scenario: No Python
- **WHEN** no `python3` or `python` 3.8+ is on `PATH`
- **THEN** `finish.sh` exits 2 and stdout is `{"ok":false,"error":"no_python","message":"finish.sh needs python 3.8+"}` as before this change, and `sw` did not run

#### Scenario: vcs.sh missing beside a working resolver
- **WHEN** `finish.sh` and the resolver are installed, a matching `sw` is found, and `specwright-pr/scripts/vcs.sh` is absent
- **THEN** it exits 2 with `"error": "vcs_script_missing"` and a message naming `specwright-pr/scripts/vcs.sh`, as before this change

### Requirement: sw finish undo-archive-plan keeps finish.sh's contract
`sw finish undo-archive-plan` SHALL accept `finish.sh`'s options and print the same JSON document byte for byte for the same repo state and arguments, including the `script` and `after_rerun` texts on Git, jj and GitButler, with the same exit codes 0 to 2. Differences: task ids and archive date prefixes match ASCII digits only, and on Windows an unconvertible `/` path stops with `bad_path`. An unexpected failure SHALL print `internal_error` and exit 1.

#### Scenario: Unchanged finish evals pass on sw
- **WHEN** the `evals/finish` tests run in CI on Linux, Windows and macOS, and the `evals/vcs` GitButler undo tests run on Linux, against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change

#### Scenario: Output bytes equal the old script's
- **WHEN** the frozen copy of the old `finish.sh` and the shim plan the same committed, uncommitted and bulk archives, on Git and jj, on GitButler where `but` is installed, and for a refusal such as `target_exists`
- **THEN** both print the same stdout bytes and exit with the same code

#### Scenario: Printed scripts still call vcs.sh by path
- **WHEN** the plan runs on a GitButler repo for a committed archive
- **THEN** `script` calls `bash <specwright-pr>/scripts/vcs.sh state` and `commit` by the same absolute path `finish.sh` printed before this change, and names no `sw` binary

#### Scenario: Usage error
- **WHEN** `sw finish undo-archive-plan` is run without `--main`
- **THEN** it exits 2 and stdout is one JSON document with `"error": "usage"` and the message `undo-archive-plan needs --main`

#### Scenario: User-task ids are ASCII digits
- **WHEN** an archived `tasks.md` holds `- [ ] ١.١ [user] Check it` (Arabic-Indic digits) and no other user task
- **THEN** that member's `waiting_on_user` is `[]`

### Requirement: Finish stops on a missing sw
When `finish.sh undo-archive-plan` reports `sw_missing`, `specwright-finish` SHALL stop with the message and the instruction to rerun the install prompt. It SHALL make no commit, merge or push, run no restore, and SHALL NOT present the answer as an undo plan.

#### Scenario: Missing sw at the deferred check
- **WHEN** the deferred check stops on `VERDICT: DEFERRED` and `finish.sh undo-archive-plan` exits 1 with a `sw_missing` document
- **THEN** finish reports `sw missing or mismatched: rerun the install prompt`, shows no undo script, and every ref, the index and the working tree are as they were

## MODIFIED Requirements

### Requirement: finish.sh runs no network command
`finish.sh` and `sw finish undo-archive-plan` SHALL run only local `git` reads and SHALL NOT run a `git` network command (`fetch`, `pull`, `push`, `ls-remote`) or `gh`. Every network step of finish SHALL be one the agent runs through `as.sh`, under that script's bounds.

#### Scenario: Plan with an unreachable origin
- **WHEN** `finish.sh undo-archive-plan` runs for a committed bulk archive in a repo whose `origin` URL points nowhere, with a `gh` on `PATH` that never answers
- **THEN** it exits 0 within 30 seconds with its usual plan, and the fake `gh` logged no call

#### Scenario: A network command added to finish.sh
- **WHEN** `finish.sh` holds a call to `git fetch`, `git pull`, `git push`, `git ls-remote` or `gh`
- **THEN** the eval that scans the script fails, naming the line

#### Scenario: A network command added to the sw finish source
- **WHEN** a non-comment line of a Dart file under `cli/lib/src/finish/` names `fetch`, `pull`, `push`, `ls-remote` or `gh` as a command word
- **THEN** the eval that scans those files fails, naming the file and the line
