# HTML dependency and standalone notice check

Checked on Windows, 2026-11-09. Tasks 4.4, the notice-delivery part of 4.5, and final integration in 9.1.

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
| Embedded Dart runtime | 3.13.7 | SDK BSD-3-Clause plus bundled runtime notices below | SDK, not a pub hook | standalone sidecar |

Sources: [args](https://pub.dev/packages/args/versions/2.7.0), [ffi](https://pub.dev/packages/ffi/versions/2.2.0), [html](https://pub.dev/packages/html/versions/0.15.7), [csslib](https://pub.dev/packages/csslib/versions/1.0.2), [source_span](https://pub.dev/packages/source_span/versions/1.10.2), [collection](https://pub.dev/packages/collection/versions/1.19.1), [path](https://pub.dev/packages/path/versions/1.9.1), [term_glyph](https://pub.dev/packages/term_glyph/versions/1.2.2), [Dart SDK](https://github.com/dart-lang/sdk).

`mise which dart` resolved `C:/Users/bgshi/AppData/Local/mise/installs/dart/3.13.7/bin/dart.exe`. The pinned SDK's `version`, `revision` and `LICENSE` were read. The SDK revision is `416e33b0ffaef062a60ec966bb8c82ed2b83f128`. The initial SDK-archive check found its root LICENSE and DevTools notices, but that archive inventory did not establish notice completeness for the embedded runtime. The source/build and licence-pointer check below corrected that omission before release. DevTools assets are not part of the standalone executable.

The root project is MIT (`LICENSE`). MIT and BSD-3-Clause permit distribution with this project while retaining notices; the sidecar also includes Specwright's MIT licence. No package implementation was copied. The approved html archive SHA-256 is `43b67b8f43321ab066817dfac5619596c98bb1b61624e77203bb4351785f9699`. Its MIT notice includes all named contributors. Original licence wording is retained, with trailing whitespace normalized.

The coordinator's `mise exec -- dart test test/no_build_hooks_test.dart` passed all 3 tests on this graph. This worker also inspected all eight runtime roots for `hook/build.dart`; none exists. The hook test was not repeated because packaging did not change the graph.

## Embedded runtime source and notice inventory

This is a source/build and licence-metadata review of the pinned official SDK, not a link-map inspection of every release artifact. Official source archives were inspected in memory; no checkout, source archive or implementation body was saved or copied into this project. Only licence and attribution text was added to the sidecar. All eight pub-package notices and the SDK root licence remain intact.

The exact revision's [standalone executable writer](https://github.com/dart-lang/sdk/blob/416e33b0ffaef062a60ec966bb8c82ed2b83f128/pkg/dart2native/lib/dart2native.dart#L63-L78) embeds the AOT runtime bytes. Its [runtime executable targets](https://github.com/dart-lang/sdk/blob/416e33b0ffaef062a60ec966bb8c82ed2b83f128/runtime/bin/BUILD.gn) use the `dart_executable` template, which includes BoringSSL, ICU common code and embedded data, and zlib. [libdart's configuration](https://github.com/dart-lang/sdk/blob/416e33b0ffaef062a60ec966bb8c82ed2b83f128/runtime/BUILD.gn) adds double-conversion and the configured VM, core and platform targets. Those targets and their conditional dependencies were followed through `runtime/configs.gni`, `runtime/vm/BUILD.gn` and `runtime/platform/BUILD.gn`.

The untruncated runtime and SDK source-tree metadata contains no separate LICENSE.V8 or runtime NOTICE file. All runtime and SDK C/C++/assembly/Dart source and source-list files were scanned for copyright/licence/permission pointers, including notices below their initial headers. A further 711 runtime text files outside those extensions were checked; their additional non-Dart attributions belong to profiler tooling and its profile schema, not embedded runtime targets. The additional runtime attributions were V8-derived regular-expression code and the VM-shared BigInt implementation. JavaScript-only BigInt copies were excluded. The sidecar reproduces the V8 copyright headers with the SDK BSD licence referenced by those sources, and retains the BigInt notice and disclaimer intact. This scan covers embedded/core sources as well as separate GN link targets.

| Runtime component | Pinned provenance and applicable text | Sidecar result |
|---|---|---|
| Dart VM, core libraries and platform implementation | SDK revision above, root BSD-3-Clause LICENSE | retained complete SDK licence |
| double-conversion | SDK `third_party/double-conversion/LICENSE` and COPYING; `runtime/BUILD.gn` links its source-set | added complete V8-project BSD notice |
| V8-derived regular expressions | SDK `runtime/vm/regexp/` source headers, SDK root LICENSE | added original copyright lines and referenced BSD licence; generator-only source excluded |
| BigInt | SDK `sdk/lib/_internal/vm_shared/lib/bigint_patch.dart` | added Tom Wu/Adam Singer permission notice and its additional intact-notice condition |
| BoringSSL | SDK DEPS: `c7eb007fd10627f1abb41a3e368b85e24cd20af9`; [LICENSE](https://boringssl.googlesource.com/boringssl/+/c7eb007fd10627f1abb41a3e368b85e24cd20af9/LICENSE), SDK `third_party/boringssl/BUILD.gn` and upstream `gen/sources.gni` | added Apache-2.0 licence; no NOTICE file exists in that pinned source archive |
| fiat-crypto within BoringSSL | same BoringSSL revision, `third_party/fiat/LICENSE`; headers/assembly appear in the linked generated source lists | added its Apache-2.0 copyright and licence notice, referring to the complete licence above |
| ICU common library and embedded data | SDK DEPS: `a86a32e67b8d1384b33f8fa48c83a6079b86f8cd`; [LICENSE](https://chromium.googlesource.com/chromium/deps/icu/+/a86a32e67b8d1384b33f8fa48c83a6079b86f8cd/LICENSE), `BUILD.gn` common/data targets | added Unicode-3.0 permission/disclaimer and bundled runtime/data notices through its double-conversion section, including dictionary and timezone notices |
| zlib and Chromium optimizations | SDK DEPS: `3008c4b3a06bd65392c31db8846000a21e3d03c5`; [LICENSE](https://chromium.googlesource.com/chromium/src/third_party/zlib/+/3008c4b3a06bd65392c31db8846000a21e3d03c5/LICENSE), `BUILD.gn`, linked root source headers | added zlib acknowledgement/licence and 2024 header attribution; added Chromium BSD conditions and 2017/2018/2022 optimization copyrights |

The Chromium optimization headers explicitly point to the Chromium repository LICENSE, rather than zlib's root LICENSE. That licence was read from official Chromium revision `a1e55e229ab766b2aab4fec15f2e0810d4124e45`; its immutable source URL is in the sidecar. This is an explicit licence-pointer resolution, not a claim that Chromium's whole source tree or that revision is linked into `sw`. The zlib root licence describes an older upstream version while its compiled headers and README identify 1.3.1; both the pinned licence text and current header attribution are retained rather than silently changing the licence text.

The full pinned BoringSSL archive's licence-file inventory contains root LICENSE and licences for fiat, benchmark, googletest and wycheproof vectors; no NOTICE file was found. Benchmark, googletest and vector files are outside the production source-set. Its root LICENSE explicitly excludes the Go TLS test-suite licence from linked-library distribution, so that test-only section is excluded. ICU's following nlohmann/json, Autoconf macro, config.guess and install-sh sections concern build tooling outside `icuuc` and the embedded data, and are excluded. Their GPL tool licences are not represented as linked runtime licences. No incompatible runtime licence was found in this review.

The [runtime feature defaults](https://github.com/dart-lang/sdk/blob/416e33b0ffaef062a60ec966bb8c82ed2b83f128/runtime/runtime_args.gni) disable Crashpad by default and Perfetto in release mode. Their dependencies and Fuchsia/Android/iOS-only branches are not asserted to ship in the five desktop targets. Desktop non-sanitized [build configuration](https://github.com/dart-lang/sdk/blob/416e33b0ffaef062a60ec966bb8c82ed2b83f128/build/config/BUILDCONFIG.gn) does not enable the `use_flutter_cxx` override; no Flutter, compiler, sanitizer or arbitrary LLVM dependency notice is inferred from a DEPS entry alone. Platform system/CRT libraries are named in the runtime/compiler build configuration (including Windows static CRT); no independent SDK-bundled licence/NOTICE pointer was found there. This review does not independently certify platform CRT redistribution terms or nondefault SDK build flags. It does establish and correct the required bundled-runtime notice omissions visible in the pinned production build and source metadata. Dependency/SDK or build-flag changes require another inventory; binary hashes alone cannot prove attribution completeness.

## Delivered locations

Source: `cli/THIRD_PARTY_NOTICES.txt`, pinned to LF by `.gitattributes`. From numeric version 0.30.0, all five target artifacts carry identical notice bytes and `THIRD_PARTY_NOTICES.txt.sha256`. The release carries the notice and its hash in the sorted six-line `SHA256SUMS`, uploaded last after every required asset is read back and verified. Five binary names remain unchanged. Older tags need no notice source or retrospective release mutation.

Both install paths deliver `<home>/.specwright/bin/<version>/THIRD_PARTY_NOTICES.txt` beside the binary. Release installation verifies notice and binary hashes before quarantine removal or execution, checks the part binary, then places the notice before keeping/replacing the binary. Matching notices retain their mtime. A failed notice rename accepts only a concurrent final file with the expected hash. Source installation checks the build, places the tree notice, renames the binary, then resolves the final file. Dependency changes must update the source notice (ADR 0032, C14). SDK-pin or build-flag changes require a new runtime inventory, carried by C18 at `mise.toml`'s Dart pin; hashes cannot detect stale attribution.

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

## Final 0.30.0 integration

The coordinator rebuilt the finished source with the pinned SDK and `--define=SW_VERSION=0.30.0`; the binary reports version 0.30.0 and interface 1. The corrected 58,573-byte notice retains the earlier package/SDK-root inventory and uses LF throughout. C18 is present beside the unchanged Dart 3.13.7 pin in `mise.toml`, including its default-desktop-build inventory, SDK/build-flag trigger and hash limitation.

With this final binary and the corrected notice, the coordinator reran the changed delivery modules individually: `evals/cli/test_attach_release.py` passed 11 tests, `evals/cli/test_workflows.py` passed 10, `evals/cli/test_install_sw.py` passed 3, and `evals/update/test_sw_install.py` ran 40 successfully with one explicit Windows executable-bit skip. This verifies the independent old/new fixture manifest selection after the version bump as well as notice delivery. No broad suite or complete Dart test set ran locally.

All 81 delta scenarios have delivered map entries; the map's platform/runtime skip limits remain explicit. Strict change validation and the Specwright schema check pass. Full operating-system matrices remain CI's responsibility.
