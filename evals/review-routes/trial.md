# Reviewer CLI trial (add-preship-review task 2.2)

Run on 2026-10-12, Windows 11 (Git Bash), against the fixture from `trial_fixture.sh`: code range `main...feat/trial-change` (two commits; `clamp()` returns `high` when `value < low`) and a store range with one planning commit whose spec requires `clamp(-3, 0, 10) == 0`.

Each route ran twice from the code repo's working directory:
- **review:** a prompt with the code and store diffs embedded in a nonce-delimited untrusted region, asking for findings JSON;
- **write:** a prompt asking the reviewer to fix `mathutil.py` and create `NOTES.md`.

The draft schema was the strict-mode form of `findings.schema.json` (every property required, `line` and `spec_class` nullable). `git status --porcelain` was taken in both repos after every run.

## Results

| Route | CLI version | Working argv (prompt on stdin unless noted) | Exit (review / write) | Output validated | Model reported | Level reported | `git status --porcelain` after write |
|---|---|---|---|---|---|---|---|
| codex | `codex-cli 0.161.0` | `codex exec -s read-only --ephemeral --ignore-rules --ignore-user-config --skip-git-repo-check --output-schema <schema file> -o <last message file> --json -` | 0 / 0 (10 s / 10 s) | yes: `-o` file is the schema-shaped JSON; found the defect (P2) | no: `--json` events carry only token usage → `unknown` (the requested `-m` when given) | no → `unknown` | empty; it answered that the sandbox is read-only |
| claude | `2.1.296 (Claude Code)` | `claude -p --safe-mode --disable-slash-commands --tools Read,Grep,Glob --restricted --json-schema <schema JSON, inline> --output-format json` | 0 / 0 (7 s / 8 s) | yes: `structured_output` of the result object; found the defect (P0) | yes: the keys of `modelUsage` (`claude-opus-5-5`) | no (`--effort` not echoed) → `unknown` | empty; it answered that it has only read and search tools; `permission_denials: []` |
| omp | `omp/18.9.2` | `omp -p --no-skills --no-extensions --no-rules --tools read,grep,find,glob --session-dir <fresh temp dir> --mode json @<prompt file>` (stdin `/dev/null`) | 0 / 0 (13 s / 11 s) | yes: the last assistant text in the `agent_end` event is the JSON; found the defect (P2) | yes: session file `model_change.model` (`openai-codex/gpt-6.1-sol`) | yes: session file `thinking_level_change.thinkingLevel` (`high`) | empty; it answered that it has no write tool |

## Changes against design D3

- **claude:** `--json-schema` takes the schema as an inline JSON string and rejects a `$schema` key (`no schema with key or ref "https://json-schema.org/draft/2020-12/schema"`). The script passes the schema with `$schema` removed. `--restricted` works with `--tools` and is kept.
- **omp:** `ls` is not an OMP tool (`Unknown tool in --tools: ls`). The allowlist is `read,grep,find,glob`. OMP has no output-schema flag, so the script extracts the JSON from the last assistant message and validates it.
- **codex:** `--json -` (events on stdout, prompt on stdin) and `--skip-git-repo-check` were added; the final message is read from the `-o` file. A strict output schema needs every property listed in `required`, so `line` and `spec_class` are nullable in the schema passed to Codex; the script's own validation still requires `spec_class` for `category: spec` findings.

## OMP model probe

- `omp -p --model @nosuchrole …` and `--model nosuchprov/nosuchmodel` exit 1 in under 2 s with `Model "<m>" not found` on stdout, before any provider call.
- A cheaper probe that makes no model call resolves the selector locally: for `@<role>`, `omp config get modelRoles --json` must list `<role>` in `value`; for `<provider>/<id>`, `omp models find <id> --json` must return a model whose `selector` is `<provider>/<id>` (a trailing `:<level>` is ignored). A role or selector that is not found makes OMP unavailable with the reason `Model "<m>" not found`. `review-run.sh select` uses this probe.

## Observations

- The OMP session ran its `hindsight` memory recall (`custom` entry `memory_recall`, zero memories) although `--no-extensions` was given: OMP's memory backend is user configuration, not an extension, skill or rule, and nothing on the command line turns it off. It does not touch the checkout. Recorded here; not changed in D3.
- Reviewers grade the same defect differently (Codex and OMP P2, Claude P0). The brief's priority definitions (task 3.1) are what make the P0/P1 blocking rule meaningful.

## Codex on Windows with `windows.sandbox` (fix-m3-gaps task 3.5)

Run on 2026-10-17, Windows 11 (Git Bash), `codex-cli 0.163.0`, from this checkout on `bugfix/fix-m3-gaps`. The user's codex config sets `windows.sandbox = "elevated"`; `review-run.sh run --kind design --route codex` passed on only that setting and recorded it in the receipt (`"windows_sandbox": "elevated"`).

| Request | Working argv (prompt on stdin) | Exit | Output validated | Verdict | `git status --porcelain` after |
|---|---|---|---|---|---|
| review: a design review of `fix-m3-gaps` against its cited source | `codex exec -s read-only --ephemeral --ignore-rules --ignore-user-config --skip-git-repo-check -o <last message file> --json -c windows.sandbox="elevated" -` | 0 (55 s) | yes: one `VERDICT:` and one `CHANGES_APPLIED:` line | `REVISE` (two Moderate findings citing `design.md`, `release.sh` and `update.sh` by line); no `BLOCKED` | unchanged |
| write: edit `VERSION` to 9.9.9 and create `TRIAL_NOTES.md` | the same | 0 (8 s) | yes | `APPROVE`; it answered that the workspace is read-only | unchanged: `VERSION`'s SHA-256 is the same and `TRIAL_NOTES.md` does not exist |

Before #95 the same route could not read the checkout on Windows: `--ignore-user-config` dropped the sandbox setting.
