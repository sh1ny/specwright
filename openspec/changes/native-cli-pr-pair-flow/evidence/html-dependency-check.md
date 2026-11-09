# HTML dependency and standalone notice check

Checked on Windows, 2026-11-09. Tasks 4.4 and the notice-delivery part of 4.5.

## Runtime graph and licences

`cli/pubspec.lock` and `.dart_tool/package_config.json` identify these compiled runtime dependencies. Each installed package LICENSE was read and compared with the prepared inventory; complete copyright, permission/conditions and disclaimer text is retained in `cli/THIRD_PARTY_NOTICES.txt`, with source URL and version. Development-only packages are not compiled into `sw`.

| Package | Version | Licence | Build hook | Delivery |
|---|---|---|---|---|
| args | 2.7.0 | BSD-3-Clause | none | standalone sidecar |
| ffi | 2.2.0 | BSD-3-Clause | none | standalone sidecar |
| html | 0.15.7 | MIT | none | standalone sidecar |
| csslib | 1.0.2 | BSD-3-Clause | none | standalone sidecar |
| source_span | 1.10.2 | BSD-3-Clause | none | standalone sidecar |
| collection | 1.19.1 | BSD-3-Clause | none | standalone sidecar |
| path | 1.9.1 | BSD-3-Clause | none | standalone sidecar |
| term_glyph | 1.2.2 | BSD-3-Clause | none | standalone sidecar |
| Embedded Dart runtime | 3.13.7 | BSD-3-Clause, SDK LICENSE | SDK, not a pub hook | standalone sidecar |

Sources: [args](https://pub.dev/packages/args/versions/2.7.0), [ffi](https://pub.dev/packages/ffi/versions/2.2.0), [html](https://pub.dev/packages/html/versions/0.15.7), [csslib](https://pub.dev/packages/csslib/versions/1.0.2), [source_span](https://pub.dev/packages/source_span/versions/1.10.2), [collection](https://pub.dev/packages/collection/versions/1.19.1), [path](https://pub.dev/packages/path/versions/1.9.1), [term_glyph](https://pub.dev/packages/term_glyph/versions/1.2.2), [Dart SDK](https://github.com/dart-lang/sdk).

`mise which dart` resolved `C:/Users/bgshi/AppData/Local/mise/installs/dart/3.13.7/bin/dart.exe`. The pinned SDK's `version` and `LICENSE` were read. Its binary-redistribution condition requires attribution, conditions and disclaimer in accompanying materials; its complete bundled licence is included. DevTools assets are not part of the standalone executable.

The root project is MIT (`LICENSE`). MIT and BSD-3-Clause permit distribution with this project while retaining notices; the sidecar also includes Specwright's MIT licence. No package implementation was copied. The approved html archive SHA-256 is `43b67b8f43321ab066817dfac5619596c98bb1b61624e77203bb4351785f9699`. Its MIT notice includes all named contributors. Original licence wording is retained, with trailing whitespace normalized.

The coordinator's `mise exec -- dart test test/no_build_hooks_test.dart` passed all 3 tests on this graph. This worker also inspected all eight runtime roots for `hook/build.dart`; none exists. The hook test was not repeated because packaging did not change the graph.

## Delivered locations

Source: `cli/THIRD_PARTY_NOTICES.txt`, pinned to LF by `.gitattributes`. From numeric version 0.30.0, all five target artifacts carry identical notice bytes and `THIRD_PARTY_NOTICES.txt.sha256`. The release carries the notice and its hash in the sorted six-line `SHA256SUMS`, uploaded last after every required asset is read back and verified. Five binary names remain unchanged. Older tags need no notice source or retrospective release mutation.

Both install paths deliver `<home>/.specwright/bin/<version>/THIRD_PARTY_NOTICES.txt` beside the binary. Release installation verifies notice and binary hashes before quarantine removal or execution, checks the part binary, then places the notice before keeping/replacing the binary. Matching notices retain their mtime. A failed notice rename accepts only a concurrent final file with the expected hash. Source installation checks the build, places the tree notice, renames the binary, then resolves the final file. Dependency/SDK changes must update the source notice (ADR 0032, C14); hashes cannot detect stale attribution.

## Verification

Red before implementation:

- `python -m unittest evals/cli/test_attach_release.py`: 11 tests, 2 failures and 1 error in the new notice cases.
- `python -m unittest evals/cli/test_workflows.py`: 10 tests, missing source-notice error.
- `python -m unittest evals/cli/test_install_sw.py`: 3 tests, new notice missing-file error; existing two passed outside sandbox.
- `python -m unittest evals/update/test_sw_install.py`: 40 tests, 8 failures (new notices plus independently selected future-tag version check), 1 platform skip.

Green after implementation:

- `python -m unittest evals/cli/test_attach_release.py`: 11 passed.
- `python -m unittest evals/cli/test_workflows.py`: 10 passed, including artifact packaging for all five target names, numeric older-tag gating and missing-source rejection.
- `python -m unittest evals/cli/test_install_sw.py`: 3 passed.
- `python -m unittest evals/update/test_sw_install.py`: 40 run, 39 passed and 1 Windows executable-bit skip. Covers all four notice stop codes, pre-execution verification, notice placement before binary rename, crash recovery, kept-binary repair, untouched matching notice, concurrent installs/replacement and old-format support.
- `python -m unittest evals.update.test_sw_install.TestPlacement.test_only_old_part_files_are_cleaned`: passed after extending it to old/fresh `.notice.part` files.
- `git diff --check`: passed; `git check-attr text eol -- cli/THIRD_PARTY_NOTICES.txt` confirms text and LF.

The installer modules used an independently compiled real `sw` at version 0.29.0, plus a tiny test-owned AOT executable reporting the selected fixture version through the unmodified production resolver. This preserves strict version/interface failure checks while selecting 0.29.0 and 0.30.0 manifests independently of the repository version bump. Temporary fixtures clean up at module completion. No broad suite ran. New-file map routing and its post-tracking check belong to the coordinator.

These checks run on Windows; CI owns the Linux/macOS matrix.
