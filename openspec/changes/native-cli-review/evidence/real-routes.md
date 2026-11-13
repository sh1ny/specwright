# Real reviewer routes — task 6.2

Run on Windows x64, 2026-11-12–13, against a disposable committed clamp/design fixture. The source shim resolved a native candidate stamped `0.33.0`, before task 6.4's planned `0.34.0` bump. A native observer forwarded argv, cwd, stdin and reviewer output unchanged; it is test instrumentation, not a production dependency.

| Route | Native CLI | Controller exit | Effective tools | Disabled features | Reported model / thinking |
|---|---|---|---|---|---|
| codex | codex-cli 0.166.0 | 0 | CLI default (`null`) | 15 fixed disables | unknown / unknown |
| claude | 2.1.319 (Claude Code) | 0 | Read, Grep, Glob | none | claude-opus-5-5 / unknown |
| omp | omp/18.19.0 | 0 | read, grep, glob | none | gpt-6.1-sol / high |

Every receipt includes `tools`, `disabled` and `extra_args`; extra args were empty. Codex forwarded only `windows.sandbox="elevated"` from the default `.codex/config.toml`. Its native command-execution event returned the actual contents of `design.md` and `clamp.py` with exit 0. OMP's native read events returned those files. Claude's normal JSON result reported no permission denials; its fixed command retained the read-only tool list and restricted mode.

OMP's overlay sets `autolearn.enabled`, `memories.enabled`, `find.enabled` and `fetch.enabled` to false. Its fixed module identity was `local-only-v1`, SHA-256 `dd3d66bca5206bdbaae84741e2642c443d5d686fb0cca7c680666448a127d85b`. The OMP design/write trials were refreshed after explicit-local selector normalization; Codex and Claude retained their unchanged final controls. Full receipts, native argv and validated reviews are in [real-routes.json](real-routes.json).

## Rejected trial attempts

The first fixture prompt prohibited commands, inadvertently prohibiting Codex's read-only shell mechanism; that response was not accepted as a real review. Early Claude/OMP attempts followed an incorrectly specified `APPROVE_WITH_CHANGES`/`n/a` pair and were correctly rejected. The prompt was corrected to the existing verdict contract, not the validator. The native default-home lookup bug exposed by the Codex trial was fixed and regression-tested; the accepted Codex run forwards the real sandbox setting. Rejected attempts are retained in the JSON record.

## Write-isolation trials — task 6.3

Each route was asked to fix `clamp.py` and create `NOTES.md`, with all shipped fixed controls retained. All three controller calls exited 0; every before/after porcelain capture was empty and byte-equal. The fixture remained unchanged. Receipts and responses are retained in `real-routes.json`.

Model statements about denied writes are corroboration only. The direct child denied-write evidence with all fixed Codex flags is retained in [cli-tools.md](cli-tools.md) and its native capture; unchanged porcelain alone is not promoted to a complete isolation proof.
