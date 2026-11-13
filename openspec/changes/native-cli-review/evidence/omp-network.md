# Production OMP local-target acceptance — task 6.5

Run on Windows x64, 2026-11-12–13, with installed `omp/18.19.0`; requested `@default`, reported `gpt-6.1-sol`, `high`. The candidate `sw` was stamped `0.33.0` before the planned release bump. The actual source shim and native command builder produced the reviewer invocation.

## Identity and observations

The exact emitted module was `local-only-v1`, SHA-256 `dd3d66bca5206bdbaae84741e2642c443d5d686fb0cca7c680666448a127d85b`. Every normal capture and receipt matches those actual module bytes. [omp-network.json](omp-network.json) retains its full UTF-8 source, exact native argv, private overlay, controller receipts and paired native request/result events.

| Control | Native calls | Observed outcome |
|---|---|---|
| Remote or ambiguous targets | 29 | Every paired result has `isError: true` and the fixed policy marker |
| Local inputs (including bare selectors) | 15 | Successful reads/searches/globs with actual nonce-bearing content or expected names |
| Bare-selector subset | 4 | Provider requests retain bare paths; native execution starts show the hook’s explicit `./` replacement |
| Raw read selector | 1 | Exactly fixture lines 2–3, without contextual lines |
| Read-only LSP | 2 | status/capabilities succeed, reporting no configured servers |
| Mutating/remote LSP | 6 | Every paired result is a policy error |
| Throwing callback | 2 | Both paired native results are errors with the injected fault marker |
| Invalid trusted module | 0 | Native exit 1, controller exit 3; no agent/tool start or result file |

Remote cases cover HTTP(S), SSH, opaque targets, slash/backslash UNC, embedded aliases, semicolon/comma/whitespace compounds, exclusions, JSON lists, Unicode-escaped schemes/slashes and mixed forms. Local cases cover Unicode/spaces, absolute/relative targets, contextual/raw selectors, literal delimiters, multiple roots and remote-looking grep content.

The loopback fixture counted every accepted TCP connection, including incomplete/non-HTTP attempts: zero accepted connections and zero requests. Its service was closed after the trials. Every captured before/after porcelain was empty and unchanged. Native tool-call ids pair the requests and results; final model claims were not used as the oracle.

## Explicit-local selector proof

The provider’s `toolcall_end` records contain the original bare `README` selectors; matching native `tool_execution_start` ids contain their `./` forms. Native results return the actual nonce-bearing local contents, including an exact raw open-ended read. Separate mixed-HTTP, JSON/opaque and compound-ambiguity controls remain policy errors. The guard’s native URI-detection regex was not widened. The fixed hook instead uses schema-revalidated input replacement before checking effective targets.

The pinned source’s `internal-urls/parse.ts:14-45`, `internal-urls/router.ts:234-241,450-455` and `tools/read.ts:1995-2038` explain why a guard-only relaxation could enter opaque-resource routing; the tracked [foundation evidence](cli-tools.md) retains that distinction.

## Fail-closed controls

The observer copied the original module before deliberately replacing its private file for each fault control. Invalid syntax fails before agent startup. A wrapper that throws from the registered callback yields actual errors for a local read and a remote grep, with no backend dispatch. The latter OMP/controller exits are 0 after a valid negative-test acknowledgement; the affected calls still failed. Fault-module bytes and digests are retained separately and are not misrepresented as matching the original receipt digest. No policy-free retry was used.

## D11 invocation/inventory correspondence

The [foundation capture](cli-tools.md) uses this same pinned OMP version, print mode (`-p`), JSON output, explicit default tool list, private session and no-skills/extensions/rules flags. Its native definitions and complete mounted-device inventory remain the inventory evidence. This replay adds fetch-disable and the sole fixed trusted hook; it does not replace those inventories with a model-authored list.

The pinned source archive is `v18.19.0`, SHA-256 `c358af6dc72536f614079bf7737d6391bc53da13160d6dec50e7de5942eb0be6` ([archive](https://codeload.github.com/can1357/oh-my-pi/tar.gz/refs/tags/v18.19.0)). Source correspondence:

- Explicit trusted paths disable ambient discovery; failed trusted loading is fatal before agent startup: `packages/coding-agent/src/main.ts:1783-1810,2526-2551`.
- The native `tool_call` bridge and extension API accept blocking and schema-revalidated input replacement: `src/extensibility/shared-events.ts:339-365`, `src/extensibility/extensions/types.ts:1546-1599`.
- Fetch-disable is applied before HTTP work: `src/tools/settings.ts:768-779`, `src/tools/read.ts:1963-1985`, `src/tools/fetch.ts:1839-1850`.
- The actual retained module only registers the tool-call hook; it registers no extra tool/device. The default selection remains read/grep/glob. The optional-LSP invocation changes only that explicit tool list and is retained separately.

Those paths are relative to `packages/coding-agent/` except the fully written `main.ts` path. Exact bytes and live native events, not an unequated diagnostic mode, establish the correspondence. The single-root prototype from task 1.5 is not used as production grammar evidence.

## Boundary

This is a lexical tool-target/operation policy, not an OS network/filesystem sandbox. Provider transport, underlying filesystem mounts, trusted native tool implementations and language servers remain outside it. User extensions stay disabled; the single first-party module is fixed, private and not replaceable through route settings. Node is development-only test tooling; production runs the module inside OMP.
