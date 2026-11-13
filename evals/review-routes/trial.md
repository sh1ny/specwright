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

## Native production-policy replay (native-cli-review)

Run on 2026-11-12–13, Windows x64, from a disposable committed fixture. The source candidate was built as `sw` 0.33.0 before the planned 0.34.0 release bump. OMP was `omp/18.19.0`, requested `@default`, reported `gpt-6.1-sol` with `high` thinking.

The source `review-run.sh` resolved the candidate binary and built every fixed flag. A throwaway native observer forwarded argv, cwd, stdin and output unchanged to the installed reviewer; it retained native events and copied the exact private overlay/module before cleanup. This observer is test instrumentation, not a production dependency.

The final production module's SHA-256 was `dd3d66bca5206bdbaae84741e2642c443d5d686fb0cca7c680666448a127d85b`, matching `receipt.policy_sha256`; `policy_id` was `local-only-v1`. The overlay disabled `autolearn.enabled`, `memories.enabled`, `find.enabled` and `fetch.enabled`. `--no-skills`, `--no-extensions` and `--no-rules` remained set; exactly one fixed `--trusted-extension` was loaded. The default tools remained `read,grep,glob`; the separate optional-LSP run added only `lsp`.

| Control | Actual native observations |
|---|---|
| Remote targets | 29 paired tool-call/error events, all with `SPECWRIGHT_OMP_LOCAL_ONLY`: 26 network-matrix cases plus three negative selector cases cover HTTP(S), SSH, opaque targets, both UNC spellings, embedded aliases, semicolon/comma/whitespace compounds, exclusions, JSON lists, Unicode-escaped schemes/slashes and mixed forms |
| Local compatibility | 15 successful calls: Unicode/spaced relative and absolute reads, contextual/raw selectors, literal delimiter filenames, grep roots and JSON roots, remote-looking search content, local globs and multiple-root globs. Four bare extensionless open-ended reads have paired original provider inputs, effective `./` native inputs and local contents |
| Exact raw selectors | The open-ended raw read returned exactly fixture lines 2–80; the separate optional-LSP run's raw read returned exactly lines 2–3, without contextual lines |
| Read-only LSP | 2 successful `status`/`capabilities` calls reported no configured servers |
| Mutating or remote LSP | 6 paired errors: rename, rename_file, applied code_actions, raw request, remote definition and opaque symbols |
| Malformed trusted module | Native exit 1, controller exit 3, no agent/tool start, no result file |
| Throwing callback | 2 paired native tool errors with the injected callback marker; no backend dispatch. OMP and the controller exited 0 after a valid acknowledgement, which is not a successful tool call |

The controlled loopback fixture counted every accepted TCP connection, not merely HTTP requests: zero connections and zero requests across these runs. Each before/after porcelain capture was empty and unchanged. Local output contained a nonce absent from the prompts; native event ids paired requests with results. Final model claims were not used as proof.

The load/callback controls deliberately replaced the private module after recording its original bytes. Their injected module bytes differ from the receipt's original production digest; they test native loader/callback failure handling, not normal-module identity.

For a new OMP version, repeat this matrix with the actual emitted module and all fixed flags. Retain the native request/result pairs, original and fault-injected module bytes, overlay, controller receipt, all-TCP fixture counts and before/after porcelain. Establish the inventory/print-mode correspondence from the version-matched source and the [foundation captures](../../openspec/changes/native-cli-review/evidence/cli-tools.md); do not substitute a policy mirror, inventory alone or a model-authored refusal.

This is a lexical tool-target/operation boundary, not an OS network or filesystem sandbox. Provider transport, underlying mounts, trusted native implementations and language servers remain outside it.

## Current-default three-route recheck (native-cli-review)

The [real-route evidence](../../openspec/changes/native-cli-review/evidence/real-routes.md) and its JSON companion retain the complete receipts (`tools`, `disabled`, `extra_args`), exact argv, native results and before/after porcelain for Codex 0.166.0, Claude 2.1.319 and OMP 18.19.0. Each route's real design review and write trial exited 0; each write trial's before/after porcelain was empty and byte-equal. Codex retained Windows `sandbox="elevated"` and every fixed feature disable. The direct child denied-write capture in the foundation evidence retains every isolation flag; model-authored refusal text is not the oracle.

The [final production-policy evidence](../../openspec/changes/native-cli-review/evidence/omp-network.md) and JSON companion retain the exact module/overlay bytes, all native request/result pairs, original bare-selector requests, loader/callback fault bytes, pinned-source inventory/mode correspondence and zero-connection fixture counters. Earlier prototype captures remain immutable and are not the production acceptance result.
