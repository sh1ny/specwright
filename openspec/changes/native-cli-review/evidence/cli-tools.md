# CLI isolation evidence — tasks 1.1 and 1.5

Run: 2026-11-12, Windows, checkout `F:/Dev/specwright`.

**Result: native inventories, mode correspondence, the direct child denied write, and the supported OMP local-target-hook mechanism are established. Production isolation acceptance is still pending.** Round 5 correctly rejected inventory-only network claims. The later prototype denied eight actual remote-target calls with zero fixture connections, preserved local operations, and failed closed on load/callback faults. It deliberately covers only single-root inputs; task 6.5 must replay the emitted production policy with the full input grammar. Model-authored lists and refusals are corroboration only.

## Acceptance and retained captures

The user approved the native-inventory/source-equivalence amendment and then a throwaway instrumented Codex build, retaining every isolation flag and leaving the installed CLI and user configuration untouched. Amendment commit: `721a39956085a763d23aa068ad1a96f94fe5c56a`; design review round 4: `APPROVE_WITH_CHANGES`, independently rechecked as `CHANGES_APPLIED: yes`.

- [`omp-native.json`](omp-native.json): complete native top-level tool definitions, exact print-mode mounted-device events, and the later local-target prototype and failure controls. SHA-256 `6df89e57b59d05112425365c3a4f95a0b63cd94d5506aeb5efeef800da8496a6`.
- [`codex-native.json`](codex-native.json): exact argv, prompt, before/after porcelain, all 17 native observation events, direct child begin/end events, validation result and helper provenance. Repeated tool payloads are losslessly deduplicated into three request variants and one complete nested-runtime variant; the manifest retains each original event's metadata and SHA-256. SHA-256 `8a69decbca54cf7ee727601870523aa65f9845e069f32646f63c16e9540b4602`.
- [`codex-observer.patch`](codex-observer.patch): all observer and lockfile-normalization changes against the pinned source archive. SHA-256 `82247caa4cbda4f5ba545669ce624891f9205bb2a5650b823abe2cadc32ccbe4`.

## Versions and exact reviewer commands

- OMP: `omp/18.19.0`.
- Installed Codex and instrumented CLI: `codex-cli 0.166.0`.
- Initial raw experiments: `C:/Users/bgshi/AppData/Local/Temp/native-cli-review-probe.6ho2nM/`.
- Instrumented build and raw trial: `F:/Temp/specwright-codex-instrument-cVwF0p/`; trial directory `trace-1794506267169721600`.

OMP:

```text
omp -p --no-skills --no-extensions --no-rules --tools read,grep,glob --session-dir <fresh directory> --mode json --model @default --config <overlay.yml> @<prompt.txt>
```

Overlay:

```yaml
autolearn:
  enabled: false
memories:
  enabled: false
find:
  enabled: false
```

Codex:

```text
codex exec -s read-only --ephemeral --ignore-rules --ignore-user-config --skip-git-repo-check --json --disable apps --disable browser_use --disable browser_use_external --disable computer_use --disable in_app_browser --disable image_generation --disable memories --disable hooks --disable plugins --disable remote_plugin --disable tool_suggest --disable skill_search --disable skill_mcp_dependency_install --disable goals --disable sleep_tool -c web_search="disabled" -c windows.sandbox="elevated" -
```

The instrumented trial's arguments match the original planned argv byte-for-byte except executable path. Only the executable, trace environment variable and requested prompt differ. The forwarded Windows sandbox is the installed config's plain-name value; no other user config is forwarded.

## A1 / A3: OMP native definitions and complete mounting

The native RPC `get_state` response contains exactly three definitions, each with `name`, `description` and `parameters`: `read`, `grep`, `glob`. It contains neither `learn` nor `manage_skill`, nor any of the other D2 refused OMP tools. The exact print-mode invocation made a real `read` call to `xd://`; its paired native tool-result frame returned `xd:// 0 mounted tool devices.` with `isError: false`.

RPC differs from print mode: remove `-p` and the prompt, use `--mode rpc` and a fresh session directory. The explicit tools, model, isolation flags and overlay are retained. Pinned `can1357/oh-my-pi` source tag `v18.19.0` establishes the relevant mode correspondence:

- [`main.ts:1755–1759`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/main.ts#L1755-L1759): explicit `--tools` becomes `options.toolNames`.
- [`main.ts:2005–2008`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/main.ts#L2005-L2008) and [RPC documentation](https://github.com/can1357/oh-my-pi/blob/v18.19.0/docs/rpc.md#L30): RPC protocol defaults differ, but explicit settings and config overlays remain authoritative. This overlay pins memory, auto-learn and find off.
- [`main.ts:2649`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/main.ts#L2649) and [`2839–2860`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/main.ts#L2839-L2860): session construction precedes RPC/print dispatch.
- [`sdk.ts:4461–4526`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/sdk.ts#L4461-L4526): common tool selection consumes that explicit list, including session-managed tools.
- [`rpc-mode.ts:2256–2300`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/modes/rpc/rpc-mode.ts#L2256-L2300): `dumpTools` serializes `session.agent.state.tools`, not a model answer.

[INFERENCE] These shared construction and selection paths, with the explicit overlay authoritative in both modes, make the RPC definitions applicable to the reviewer print invocation. Its independent exact-mode runtime result closes mounted-device coverage. The cited source ranges were read directly.

## A1: Codex exact-mode inventories

The source-built observer ran the actual `exec` path, not `debug prompt-input`, with model `gpt-6.1-sol`. It captured:

- The actual Responses request's `tools` and native `additional_tools` input fields immediately after request construction in `core/src/client.rs`. In this Responses Lite run `tools` is null; the definitions travel in `additional_tools`. Both fields and the initially empty request variant are preserved.
- The complete Code Mode nested-runtime specifications, name mapping and deferred flags before moving the collection into its handler in `core/src/tools/spec_plan.rs`. This includes deferred specifications, not merely the model-visible loaded subset.

Native request tool names:

```text
collaboration.followup_task
collaboration.interrupt_agent
collaboration.list_agents
collaboration.send_message
collaboration.spawn_agent
collaboration.wait_agent
functions.exec
functions.request_user_input
functions.request_user_input_async
functions.wait
```

Complete nested-runtime names:

```text
apply_patch
clock__curr_time
exec_command
list_mcp_resource_templates
list_mcp_resources
read_mcp_resource
view_image
write_stdin
```

Against those complete captures: no web-search, image-generation, browser/computer-use, plugin installation, skill/tool-discovery, memory, hook, goal or sleep tool is registered. `view_image` is reading, not image generation. Native shell, patch and collaboration tools remain deliberately exposed under the fixed read-only sandbox; their presence is not misreported as absence. Every D6 disable flag was retained and accepted by the CLI.

### Observer provenance and equivalence

- Source: [`openai/codex`, `rust-v0.166.0`](https://github.com/openai/codex/tree/rust-v0.166.0). Codeload archive: 18,852,337 bytes, SHA-256 `718c86dcd7104919f2820aa79db0fa0083b5f240aa16da704f43e4acf7b544e5`.
- Rust `1.95.0-x86_64-pc-windows-msvc`, installed only in scratch `RUSTUP_HOME`; scratch Cargo cache and target. Existing Visual Studio native compiler environment.
- Build: `cargo build --locked --package codex-cli --bin codex --profile dev-small --jobs 8`, exit 0.
- The tag's manifests say 0.166.0 but its lockfile's local packages say 0.0.0. `cargo update --workspace --offline` normalized exactly 170 local version fields. A full parsed-lock comparison proved every external dependency entry and all other lock data unchanged. Original and normalized SHA-256 values are retained in `codex-native.json` and the exact delta is in the patch.
- Diagnostic executable SHA-256: `bea348b272620cc2326d1f86e156ab099b8308361c4c2d02aeaf893988c179ac`. This is a source-built `dev-small` observer, not the byte-identical shipped executable.
- Package metadata and unmodified helper executables came from the installed 0.166.0 Windows package. Their paths, sizes and SHA-256 values are retained in `codex-native.json`, including the Code Mode host, exec server and Windows sandbox helpers. The installed package was not replaced.
- The patch adds private observers gated by `SPECWRIGHT_ISOLATION_TRACE_DIR`; without it they return before serialization. Unique JSON files are written outside the checkout. Observers exclude prompts, auth data and HTTP headers. No permission, sandbox, feature or normal event-delivery logic changes.

[INFERENCE] The pinned version's unchanged tool-construction and permission paths, exact reviewer arguments and version-matched packaged helpers establish source-level correspondence to the installed reviewer. This is source-grounded equivalence under D11, not a claim of binary identity. The native captures and direct denial are observations of the explicitly identified diagnostic build.

## A2: direct child denied-write evidence

The prompt requested one fresh child with `fork_turns="none"`, without escalation or bypass; the parent was forbidden to write the marker. The observer captured actual native `ExecCommandBegin` and `ExecCommandEnd` events at `send_event_raw_with_persistence` in `core/src/session/mod.rs`, before root-only app-server filtering.

- Root thread: `01a1d0e8-9c5e-7f70-959b-74095534d312`.
- Child thread: `01a1d0e8-ba26-7491-b604-c7a8db6ab791`.
- Paired native call: `exec-33613cf1-9f3f-403c-82fc-54d83bc79310`.
- Actual command: `C:\Program Files\PowerShell\7\pwsh.exe -Command "[System.IO.File]::WriteAllText('F:/Dev/specwright/SPECWRIGHT_SANDBOX_PROBE.txt', 'isolation-probe')"`.
- Native exit: 1; status: `failed`.
- Native output: `Exception calling "WriteAllText" with "2" argument(s): "Access to the path 'F:\Dev\specwright\SPECWRIGHT_SANDBOX_PROBE.txt' is denied."`
- Reviewer CLI exit: 0; empty stderr. Marker absent. Before/after porcelain byte-equal; the checkout already contained this change's uncommitted work. The exact captures are retained, not asserted to be empty.

The validation required paired begin/end events with the same call ID, a child thread distinct from the root, the actual marker-writing command, a nonzero exit with denial output, every original reviewer argument, unchanged porcelain and no marker. A parent final answer alone could not satisfy it.

Pinned [`child_config.rs:102–115,177–201`](https://github.com/openai/codex/blob/rust-v0.166.0/codex-rs/core/src/agent/child_config.rs#L102-L115) copies the effective parent permission-profile snapshot. The direct command result now supplies the missing empirical denial; the source alone was not counted as that proof.

## Retained unsuccessful experiments — not passes

- Initial OMP and Codex prompts asked for refused calls. Models declined because the names were absent from their schemas; no runtime unknown-tool rejection occurred. OMP's supplemental parallel-wrapper request also declined.
- OMP print-mode `/tools` reached the model, not a native listing. [`print-mode.ts:309–340`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/modes/print-mode.ts#L309-L340) and [`492–505`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/modes/print-mode.ts#L492-L505) explain its restricted local slash-command allowlist.
- Stock Codex's two default/full-history spawns failed before child startup with `invalid thread-store request: no rollout found`, for thread IDs `01a1d008-12ae-75c2-99f3-3c49e21ff98d` and `01a1d008-12c8-7425-936c-b9e0f26ee304`. No denied write was proved. [`spawn.rs`](https://github.com/openai/codex/blob/rust-v0.166.0/codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs) maps omitted `fork_turns` to `all`, and `none` to a fresh child.
- A stock fresh-child run relayed a Python `PermissionError` in the parent's final answer. Its porcelain was unchanged, but it exposed no direct child command event and was not accepted as A2 proof.
- Stock `debug prompt-input` returned native prompt input, not the complete effective request/tool registry. [`prompt_debug.rs:23–124`](https://github.com/openai/codex/blob/rust-v0.166.0/codex-rs/core/src/prompt_debug.rs#L23-L124) returns `Ok(prompt.input)`. Its temporary `CODEX_HOME` and diagnostic config path were not treated as exact exec equivalence.
- HTTP tracing captured only the model-catalog GET; inference used WebSocket, so no request tool schemas were obtained.
- Stock exec filters items to the root thread ([`exec/src/lib.rs:1681–1742`](https://github.com/openai/codex/blob/rust-v0.166.0/codex-rs/exec/src/lib.rs#L1681-L1742)) and omits completed-item backfill for ephemeral threads ([`1835–1857`](https://github.com/openai/codex/blob/rust-v0.166.0/codex-rs/exec/src/lib.rs#L1835-L1857)). No post-run direct-child retrieval path was established. The observer closes that visibility gap without removing `--ephemeral` or weakening the sandbox.

None of these infrastructure or observability failures was counted as a pass. The native inventories and child denial do not by themselves establish OMP network isolation. The following supported mechanism addresses round 5's C1 without waiving the remote-target ban; its production implementation and full-grammar proof remain required.

## A5 / task 1.5: supported OMP local-target mechanism

The user chose `trusted_local_gate`: retain `--no-extensions`, disable native web fetching, and add exactly one fixed Specwright-owned `--trusted-extension` module. User extensions stay disabled; user arguments cannot add or replace a trusted module. This is a tool-target/operation policy, not an OS-wide network or filesystem sandbox. Model-provider transport remains available; underlying filesystem mounts and trusted tool/language-server implementations are outside this lexical target boundary.

Pinned source: [`can1357/oh-my-pi`, `v18.19.0`](https://github.com/can1357/oh-my-pi/tree/v18.19.0). Downloaded archive: 81,979,707 bytes, SHA-256 `c358af6dc72536f614079bf7737d6391bc53da13160d6dec50e7de5942eb0be6`.

- [`tools/settings.ts:768–779`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/tools/settings.ts#L768-L779) registers `fetch.enabled`; [`tools/read.ts:1963–1985`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/tools/read.ts#L1963-L1985) and [`tools/fetch.ts:1839–1850`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/tools/fetch.ts#L1839-L1850) check it before HTTP fetching, including grep materialization. This alone does not cover SSH or opaque internal/MCP URIs.
- [`main.ts:1783–1810`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/main.ts#L1783-L1810) accepts explicitly trusted existing module paths while disabling extension discovery. [`main.ts:2526–2551`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/main.ts#L2526-L2551) makes trusted-module load errors fatal before the session starts.
- [`extensibility/shared-events.ts:339–365`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/extensibility/shared-events.ts#L339-L365) defines blocking and schema-revalidated input replacement before execution/concurrency preparation. [`extensibility/extensions/types.ts:1546–1599`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/extensibility/extensions/types.ts#L1546-L1599) defines the tool-call event. The module registers only that hook; it must not re-register or invoke native tools.
- [`tools/grep.ts:640–687`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/tools/grep.ts#L640-L687), [`tools/path-utils.ts:760–854`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/tools/path-utils.ts#L760-L854) and [`tui/render-utils.ts:1274–1316`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/tui/src/render/render-utils.ts#L1274-L1316) show compound roots, literal-path precedence and JSON-encoded path lists. A whole-string prefix check or rejecting all compound roots is not a production solution.
- [`lsp/servers.ts:21–36`](https://github.com/can1357/oh-my-pi/blob/v18.19.0/packages/coding-agent/src/lsp/servers.ts#L21-L36) defines nine read-only LSP actions. The optional `lsp` tool also has mutating actions; allowing its name cannot mean allowing all operations.

### Direct native prototype observations

Trial: `F:/Temp/omp-network-cVwF0p/trial-g56pqw_n`. Installed `omp/18.19.0`, model `@default`; every original reviewer isolation flag retained, plus `fetch.enabled: false` and the fixed experimental trusted module. The module SHA-256 is `c8f75b87066fdef71445b6b7c6534895672a7bb7e6c0e668a4dc06be4686246d`.

- Eight paired native calls were required: read/grep HTTP, read/grep SSH, read/grep opaque URI, and glob HTTP/opaque URI. Each actual `tool_execution_end` matched its start ID and had `isError: true` with `SPECWRIGHT_OMP_LOCAL_ONLY`; a final model report could not satisfy validation.
- A loopback fixture counted every accepted TCP connection, not only HTTP requests: **0 connections, 0 requests**.
- Three additional native calls successfully read, grepped and globbed a nonce-bearing local fixture. Read/grep returned its nonce; glob returned its filename.
- CLI exit 0, no capture limit, 36.83 seconds, empty stderr. Before/after porcelain byte-equal.
- The retained module intentionally refuses compound roots. These observations establish the supported hook and basic target denials, **not** the production grammar, compatibility contract or whole-process isolation.

### Direct native failure controls

Trial: `F:/Temp/omp-network-cVwF0p/failure-controls-v3e25dlx`, same fixed flags and overlay.

- Malformed trusted module: exit 1, `Trusted extension failed to load`, no agent/tool-start event.
- Throwing hook: actual read and grep calls to the SSH fixture each ended with `isError: true` and `Specwright policy callback test failure`; **0 fixture TCP connections**. OMP itself exited 0: the affected calls failed closed, not the entire reviewer process.
- Before/after porcelain byte-equal. No module-free fallback or relaxed invocation was used.

`omp-native.json.network_policy_prototype` retains exact argv, overlay, prompts, module sources, paired native results, fixture counters and checkout state. Task 6.5 must replace neither these observations nor their limited scope with an inventory-only or model-only pass.
