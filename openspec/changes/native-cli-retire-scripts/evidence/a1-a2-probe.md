# A1/A2 decision gate (task 1.1)

The probe build reads the raw argument list in `cli/bin/sw.dart` before dispatch (`cli/lib/src/entry/raw_arguments.dart`: `/proc/self/cmdline` on Linux, `_NSGetArgv` on macOS, `GetCommandLineW` and `CommandLineToArgvW` on Windows) and prints `bad_argument` with exit 2 for an argument that is not well-formed Unicode. `evals/cli/test_sw_entry.py` drives the compiled binary. Each run was dispatched with `workflow_dispatch` on the throwaway branch `tmp/retire-scripts-a1a2-probe`, since deleted.

## Run 1: the gate

https://github.com/sh1ny/specwright/actions/runs/44410098089 (cli jobs read; the run was later cancelled by the next dispatch on the same ref)

| OS | Case | Result |
|---|---|---|
| Windows | lone surrogate (`m\udc80x.md`) | `bad_argument` document naming argument 4, exit 2: **passes A2** |
| Windows | valid U+FFFD | taken as a character; no `bad_argument` |
| Linux | bytes `m\xffx.md` | exit 255, empty stdout, stderr `Dart_NewStringFromUTF8 expects argument 'str' to be valid UTF-8.`: **fails A1** (the runtime refuses before `main`) |
| Linux | valid U+FFFD | taken as a character; no `bad_argument` |
| macOS | bytes `m\xffx.md` | exit 255, empty stdout, same stderr: **fails A1** |
| macOS | valid U+FFFD | taken as a character; no `bad_argument` |

## Decision

A1 differs on Linux and macOS, so apply stopped before group 2. The user chose to accept the runtime's refusal: on Linux and macOS a non-UTF-8 argument gives a non-zero exit, an empty stdout and no work, with the runtime's exit code and text unpinned; Windows keeps the `bad_argument` document and exit 2. Every requirement naming `bad_argument` for a non-UTF-8 argument was amended together (native-cli, change-finish, task-commits, vcs-backends, github-identity, pr-script-runtime), the loss is recorded under C6 in design.md and ADR 0040, and the amended contract passed design review rounds 12 (REVISE) and 13 (APPROVE_WITH_CHANGES, changes applied).

## Run 2: the amended probes on three OSes

https://github.com/sh1ny/specwright/actions/runs/44414056318: conclusion **success**, every suite green on ubuntu-24.04, windows-latest and macos-latest. The probe cases now assert the accepted contract: on Linux and macOS `test_non_utf8_bytes_on_posix_are_refused_before_sw_runs` (non-zero exit and empty stdout, with a valid-path control that prints a document); on Windows `test_lone_surrogate_on_windows_is_bad_argument`; everywhere `test_valid_replacement_character_is_a_character`.
