# TOML package evidence — task 2.1

Checked 2026-11-12 against pub.dev package metadata and the downloaded hosted archives. The SHA-256 of each archive matched the value published by pub.dev. `mise exec -- dart pub get` from `cli/` resolved the runtime closure below.

## Resolved closure and provenance

`toml` 0.18.0 declares `petitparser: ^7.0.1`, `collection: ^1.16.0`, `meta: ^1.16.0` and `web: ^1.1.1`. `petitparser` 7.1.0 additionally constrains `collection: ^1.19.1` and `meta: ^1.19.0`. The resolved versions are:

| Package | Resolved version | License | Source repository | Hosted archive SHA-256 |
| --- | --- | --- | --- | --- |
| toml | 0.18.0 | MIT | https://github.com/just95/toml.dart | `35a35f782228656a2af31e8c73d1353cc4ef3d683fd68af1111b44631879c05e` |
| petitparser | 7.1.0 | MIT | https://github.com/petitparser/dart-petitparser | `2f1564aadb14215e478563b5406cb80729d022158c01dc50c96013c2f7eb4790` |
| collection | 1.19.1 | BSD 3-Clause | https://github.com/dart-lang/core/tree/main/pkgs/collection | `2f5709ae4d3d59dd8f7cd309b4e023046b57d8a6c82130785d2b0e5868084e76` |
| meta | 1.19.0 | BSD 3-Clause | https://github.com/dart-lang/sdk/tree/main/pkg/meta | `307249ce4ff29d58a18e97f6345f539382eb9c9c29ecda628900f31de0443dd9` |
| web | 1.1.2 | BSD 3-Clause | https://github.com/dart-lang/web | `e119e82ac4795c7925103b7cf3768191f33941b99e7ccffbd6c645201d9f606b` |

All five resolved packages are hosted from `https://pub.dev`; their archive URLs are `https://pub.dev/api/archives/<name>-<version>.tar.gz`, and their lockfile sources are `pub.dev/<name>-<version>`. The package metadata used for the root package and each resolved dependency is available at:

- https://pub.dev/api/packages/toml/versions/0.18.0
- https://pub.dev/api/packages/petitparser/versions/7.1.0
- https://pub.dev/api/packages/collection/versions/1.19.1
- https://pub.dev/api/packages/meta/versions/1.19.0
- https://pub.dev/api/packages/web/versions/1.1.2

## Hook and notice review

Inspected each resolved archive's member list and `LICENSE`. None has a top-level `hook/` or `hooks/` tree, `hook/build.dart` or `hooks/build.dart`; none declares a build hook in its package metadata. The `toml` archive includes `tool/`, but no hook/build entry. No package has an unacceptable license under ADR 0033; the exact license texts are shipped in `cli/THIRD_PARTY_NOTICES.txt`.

Before this change the notices file already had one `collection` 1.19.1 entry. It had no `meta` 1.19.0, `web` 1.1.2, `petitparser` 7.1.0 or `toml` 0.18.0 package section. Added each missing section once and retained the existing collection entry without duplication.

## Parent verification

- `mise exec -- dart test test/bounded_run_test.dart test/launch_test.dart test/no_build_hooks_test.dart` passed: 43 tests, with 3 POSIX-only launch checks skipped on Windows.
- All five runtime-closure packages have exactly one notice section. Each resolved package's full `LICENSE` matches its section, ignoring trailing whitespace only; the existing collection notice differs solely by a trailing space on its copyright line.
- `release.sh notes --proposal openspec/changes/native-cli-review/proposal.md` accepted the updated release notes.
