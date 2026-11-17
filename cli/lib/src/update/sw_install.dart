import 'dart:convert';
import 'dart:ffi' show Abi;
import 'dart:io';
import 'dart:math';

import 'package:path/path.dart' as p;

import '../process/launch.dart';
import 'chmod.dart';
import 'download.dart';
import 'file_ops.dart';
import 'options.dart';
import 'place.dart';
import 'stop.dart';

/// The five hosts a release carries a binary for.
const List<String> swTargets = [
  'linux-x64',
  'linux-arm64',
  'windows-x64',
  'macos-arm64',
  'macos-x64',
];

const String _noticeName = 'THIRD_PARTY_NOTICES.txt';
const Duration _partAge = Duration(hours: 1);

final RegExp _tag = RegExp(r'^v\d+\.\d+\.\d+$');
final RegExp _semver = RegExp(r'^(\d+)\.(\d+)\.(\d+)$');

/// `<home>` of ADR 0027: `SPECWRIGHT_HOME`, else the user's home
/// (`USERPROFILE` on Windows, `HOME` elsewhere).
String swHome(Map<String, String> env) {
  final set = env['SPECWRIGHT_HOME'];
  if (set != null && set.isNotEmpty) return set;
  final home = Platform.isWindows
      ? (env['USERPROFILE'] ?? env['HOME'])
      : env['HOME'];
  return home ?? '';
}

/// `sw update sw-install`: downloads the host's `sw` for a release tag, or
/// takes the binary named by `--build`, checks it and places it at
/// `<home>/.specwright/bin/<version>/sw[.exe]` with the notice beside it.
/// Returns the success document; throws [UpdateStop] for a stop and
/// [UpdateUsage] for a missing option.
///
/// The tag form follows `scripts/update.sh`'s `sw_install` (D4, D6, D9 of
/// native-cli-update): `SHA256SUMS`, the asset and (from 0.30.0) the notice
/// are fetched into `.sw-<token>` part files in the version directory, each
/// hash is checked before anything runs, quarantine is cleared on macOS and
/// the mode set only then, [checkBinary] runs the part, the notice is placed,
/// and the part is renamed onto the final path. A `--build FILE` form (D7)
/// copies FILE into a part directory instead of downloading, takes the notice
/// from `<download>/cli/THIRD_PARTY_NOTICES.txt`, and does everything else the
/// same; FILE itself is never renamed.
///
/// [environment] is where `SPECWRIGHT_HOME`, the proxy variables, the network
/// bounds, `SPECWRIGHT_TEST_HOST` and the kill seam are read from (default:
/// the process environment). [clientFactory] builds the download client.
Future<Map<String, Object?>> swInstall(
  UpdateOptions options, {
  Map<String, String>? environment,
  HttpClient Function()? clientFactory,
  void Function(int code)? exitProcess,
}) async {
  final env = environment ?? Platform.environment;
  final build = options.build;
  final ref = options.ref ?? '';
  if (build == null && !_tag.hasMatch(ref)) {
    final why = ref == 'main'
        ? '$ref has no release binaries'
        : '${ref.isEmpty ? 'this ref' : ref} is not a release tag';
    return {
      'ok': true,
      'interface': updateInterface,
      'subcommand': 'sw-install',
      'action': 'skipped',
      'ref': ref.isEmpty ? null : ref,
      'message': 'sw not installed: $why',
    };
  }
  final download = options.download;
  if (download == null) {
    throw UpdateUsage(
      build == null
          ? 'sw-install needs --download DIR'
          : '--build needs --download DIR, the tree whose VERSION and '
                '$_noticeName go with the binary',
    );
  }
  final version = _readVersion('$download/VERSION');
  if (version == null || !_semver.hasMatch(version)) {
    throw UpdateStop(
      'download_version_invalid',
      "the download's VERSION holds ${_quote(version)}, not MAJOR.MINOR.PATCH",
    );
  }
  if (build == null && version != ref.substring(1)) {
    throw UpdateStop(
      'download_version_invalid',
      "the download's VERSION holds $version, but the ref is $ref: the binary "
          "must report the tag's version ${ref.substring(1)}; nothing was "
          'downloaded or placed',
    );
  }
  final host = _host(env);
  final files = UpdateFileOps(environment: env);
  final home = swHome(env);
  final vdir = '$home/.specwright/bin/$version'.replaceAll(r'\', '/');
  final finalPath = '$vdir/${Platform.isWindows ? 'sw.exe' : 'sw'}';

  if (build != null) {
    return _placeBuild(
      files: files,
      build: build,
      tree: download,
      version: version,
      vdir: vdir,
      finalPath: finalPath,
      ref: options.ref,
      env: env,
      exitProcess: exitProcess,
    );
  }

  if (host.target == null) {
    throw UpdateStop(
      'unsupported_platform',
      'this host (${host.system} ${host.machine}) has no sw binary for '
          'release $ref; the release ships ${swTargets.join(', ')}',
    );
  }
  final asset = _assetName(host.target!);
  final withNotice = _atLeast(version, 0, 30, 0);
  final testHttp = env['SPECWRIGHT_TEST_HTTP'] == '1';
  final base = await _releaseBase(options, download, testHttp);
  final bounds = downloadBounds(env);

  files.mkdir(vdir);
  _cleanStale(files, vdir);
  final token = _token();
  final binaryPart = '$vdir/.sw-$token.part${Platform.isWindows ? '.exe' : ''}';
  final sumsPart = '$vdir/.sw-$token.sums.part';
  final noticePart = '$vdir/.sw-$token.notice.part';
  final url = '$base/releases/download/$ref/';

  Future<bool> fetch(String name, String dest) => downloadReleaseFile(
    url: '$url$name',
    dest: dest,
    name: name,
    tag: ref,
    files: files,
    deadline: bounds.deadline,
    maxBytes: bounds.maxBytes,
    clientFactory: clientFactory,
    environment: env,
    allowHttpStart: testHttp,
  );

  try {
    if (!await fetch('SHA256SUMS', sumsPart)) {
      throw UpdateStop(
        'assets_not_uploaded',
        'the binaries of release $ref are not uploaded yet (no SHA256SUMS): '
            'rerun the install once the release workflow has attached them',
      );
    }
    final sums = _parseSums(File(sumsPart).readAsBytesSync(), withNotice);
    if (sums == null) {
      throw UpdateStop(
        'sums_invalid',
        'SHA256SUMS of release $ref is not made of lines `<64 lowercase hex '
            'digits>  <asset name>` for the five binary assets'
            '${withNotice ? ' and $_noticeName' : ''}; no hash is used from it',
      );
    }
    final wanted = sums[asset];
    if (wanted == null) {
      throw UpdateStop(
        'assets_not_uploaded',
        'SHA256SUMS of release $ref has no line for $asset: rerun the '
            'install once the release workflow has attached the binaries',
      );
    }
    if (!await fetch(asset, binaryPart)) {
      throw UpdateStop(
        'asset_missing',
        'release $ref has SHA256SUMS but no $asset; the sealed release needs '
            'its owner',
      );
    }
    final got = fileSha(binaryPart);
    if (got != wanted) {
      throw UpdateStop(
        'checksum_mismatch',
        '$asset of release $ref: SHA-256 $got differs from the SHA256SUMS '
            'line $wanted; the file was not run and nothing was placed',
      );
    }
    if (withNotice) {
      if (!await fetch(_noticeName, noticePart)) {
        throw UpdateStop(
          'asset_missing',
          'release $ref has SHA256SUMS but no $_noticeName; the sealed '
              'release needs its owner',
        );
      }
      final gotNotice = fileSha(noticePart);
      if (gotNotice != sums[_noticeName]) {
        throw UpdateStop(
          'checksum_mismatch',
          '$_noticeName of release $ref: SHA-256 $gotNotice differs from the '
              'SHA256SUMS line ${sums[_noticeName]}; the binary was not run '
              'and nothing was placed',
        );
      }
    }
    // only now: the file has the release's hash
    if (host.system.toLowerCase() == 'darwin') {
      await _unquarantine(binaryPart, asset, ref, vdir);
    }
    makeExecutable(binaryPart);
    final check = await checkBinary(binaryPart, version: version);
    if (!check.ok) {
      throw UpdateStop(
        'sw_check_failed',
        '$asset of release $ref did not pass the version check: '
            '${check.detail}',
      );
    }
    final action = await placeChecked(
      files: files,
      part: binaryPart,
      finalPath: finalPath,
      partSha: wanted,
      version: version,
      asset: asset,
      ref: ref,
      noticePart: withNotice ? noticePart : null,
      noticeFinal: '$vdir/$_noticeName',
      noticeSha: sums[_noticeName],
      renameHook: env['SPECWRIGHT_TEST_RENAME'],
      noticeRenameHook: env['SPECWRIGHT_TEST_NOTICE_RENAME'],
      exitProcess: exitProcess,
    );
    return _installed(action, finalPath, asset, version, ref);
  } finally {
    for (final part in [binaryPart, sumsPart, noticePart]) {
      if (FileSystemEntity.typeSync(part, followLinks: false) !=
          FileSystemEntityType.notFound) {
        files.remove(part);
      }
    }
  }
}

Future<Map<String, Object?>> _placeBuild({
  required UpdateFileOps files,
  required String build,
  required String tree,
  required String version,
  required String vdir,
  required String finalPath,
  required String? ref,
  required Map<String, String> env,
  void Function(int code)? exitProcess,
}) async {
  final asset = p.basename(build);
  final noticeSource = '$tree/cli/$_noticeName';
  if (!File(noticeSource).existsSync()) {
    throw UpdateStop(
      'download_incomplete',
      'the download has no cli/$_noticeName',
    );
  }
  if (!File(build).existsSync()) {
    throw UpdateStop(
      'sw_check_failed',
      '$asset (--build) did not pass the version check: ${p.absolute(build)} '
          'does not exist (expected sw $version)',
    );
  }
  files.mkdir(vdir);
  _cleanStale(files, vdir);
  final stage = '$vdir/.sw-${_token()}.stage';
  files.mkdir(stage);
  try {
    // copies, so the file named by --build is never the one that is renamed
    files.copy(build, stage);
    files.copy(noticeSource, stage);
    final part = '$stage/$asset';
    makeExecutable(part);
    final check = await checkBinary(part, version: version);
    if (!check.ok) {
      throw UpdateStop(
        'sw_check_failed',
        '$asset (--build) did not pass the version check: ${check.detail}',
      );
    }
    final noticePart = '$stage/$_noticeName';
    final action = await placeChecked(
      files: files,
      part: part,
      finalPath: finalPath,
      partSha: fileSha(part),
      version: version,
      asset: asset,
      ref: ref ?? 'the build',
      noticePart: noticePart,
      noticeFinal: '$vdir/$_noticeName',
      noticeSha: fileSha(noticePart),
      renameHook: env['SPECWRIGHT_TEST_RENAME'],
      noticeRenameHook: env['SPECWRIGHT_TEST_NOTICE_RENAME'],
      exitProcess: exitProcess,
    );
    return _installed(action, finalPath, asset, version, ref);
  } finally {
    files.remove(stage);
  }
}

Map<String, Object?> _installed(
  String action,
  String finalPath,
  String asset,
  String version,
  String? ref,
) => {
  'ok': true,
  'interface': updateInterface,
  'subcommand': 'sw-install',
  'action': action,
  'path': finalPath,
  'asset': asset,
  'version': version,
  'ref': ref,
};

/// A killed run's leftovers in [vdir]; a part younger than an hour belongs to
/// a run still going (a run lasts minutes).
void _cleanStale(UpdateFileOps files, String vdir) {
  final now = DateTime.now();
  for (final entry in Directory(vdir).listSync(followLinks: false)) {
    final name = p.basename(entry.path);
    if (!name.startsWith('.sw-') ||
        !(name.contains('.part') || name.endsWith('.stage'))) {
      continue;
    }
    try {
      if (now.difference(entry.statSync().modified) > _partAge) {
        files.remove(entry.path);
      }
    } on FileSystemException {
      // gone already, or not ours to remove
    }
  }
}

String _token() {
  final random = Random.secure();
  return List.generate(
    6,
    (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
}

String? _readVersion(String path) {
  try {
    return File(path).readAsStringSync().trim();
  } on FileSystemException {
    return null;
  }
}

String _quote(String? text) =>
    text == null ? 'None' : "'${text.replaceAll("'", r"\'")}'";

bool _atLeast(String version, int major, int minor, int patch) {
  final m = _semver.firstMatch(version)!;
  final parts = [1, 2, 3].map((i) => int.parse(m.group(i)!)).toList();
  final want = [major, minor, patch];
  for (var i = 0; i < 3; i++) {
    if (parts[i] != want[i]) return parts[i] > want[i];
  }
  return true;
}

String _assetName(String target) =>
    'sw-$target${target.startsWith('windows') ? '.exe' : ''}';

class _Host {
  _Host(this.system, this.machine, this.target);
  final String system;
  final String machine;
  final String? target;
}

/// This host's system, machine and release target. `SPECWRIGHT_TEST_HOST` as
/// `<system>/<machine>` replaces the real host (the evals use it).
_Host _host(Map<String, String> env) {
  final forced = env['SPECWRIGHT_TEST_HOST'];
  String system, machine;
  if (forced != null && forced.contains('/')) {
    final at = forced.indexOf('/');
    system = forced.substring(0, at);
    machine = forced.substring(at + 1);
  } else {
    final parts = Abi.current().toString().split('_');
    system =
        const {
          'linux': 'Linux',
          'macos': 'Darwin',
          'windows': 'Windows',
        }[parts.first] ??
        parts.first;
    machine = parts.length > 1 ? parts.sublist(1).join('_') : '';
  }
  final os = const {
    'linux': 'linux',
    'darwin': 'macos',
    'macos': 'macos',
    'windows': 'windows',
  }[system.toLowerCase()];
  final arch = const {
    'x86_64': 'x64',
    'amd64': 'x64',
    'x64': 'x64',
    'aarch64': 'arm64',
    'arm64': 'arm64',
  }[machine.toLowerCase()];
  final target = os != null && arch != null ? '$os-$arch' : null;
  return _Host(system, machine, swTargets.contains(target) ? target : null);
}

/// The lines of `SHA256SUMS`, as a map from asset name to hash; null when a
/// line is malformed, duplicated or names an unknown file, or when the notice
/// is wanted and missing.
Map<String, String>? _parseSums(List<int> bytes, bool withNotice) {
  final String text;
  try {
    text = const Utf8Decoder(allowMalformed: false).convert(bytes);
  } on FormatException {
    return null;
  }
  final known = {
    for (final t in swTargets) _assetName(t),
    if (withNotice) _noticeName,
  };
  final lines = text.split('\n');
  if (lines.isNotEmpty && lines.last.isEmpty) lines.removeLast();
  final line = RegExp(r'^([0-9a-f]{64})  (\S+)$');
  final out = <String, String>{};
  for (final entry in lines) {
    final m = line.firstMatch(entry);
    if (m == null ||
        !known.contains(m.group(2)) ||
        out.containsKey(m.group(2))) {
      return null;
    }
    out[m.group(2)!] = m.group(1)!;
  }
  if (withNotice && !out.containsKey(_noticeName)) return null;
  return out.isEmpty ? null : out;
}

/// The release base URL: `--release-url`, else
/// `https://github.com/<owner>/<repo>` from the download's origin.
Future<String> _releaseBase(
  UpdateOptions options,
  String download,
  bool testHttp,
) async {
  final given = options.releaseUrl;
  if (given != null && given.isNotEmpty) {
    var url = given;
    while (url.endsWith('/')) {
      url = url.substring(0, url.length - 1);
    }
    final scheme = Uri.tryParse(url)?.scheme.toLowerCase();
    // SHA256SUMS comes over the same channel as the binary, so a plaintext
    // mirror could swap both: https, or a local file:// tree.
    if (scheme != 'https' &&
        scheme != 'file' &&
        !(scheme == 'http' && testHttp)) {
      throw UpdateStop(
        'release_url_not_https',
        '--release-url $url is not an https:// URL: the checksums and the '
            'binary would come over a channel anyone on the path can rewrite; '
            'nothing was downloaded or placed',
      );
    }
    return url;
  }
  final result = await launch([
    'git',
    'remote',
    'get-url',
    'origin',
  ], cwd: download);
  final origin = result.exitCode == 0
      ? String.fromCharCodes(result.stdout).trim()
      : '';
  final m = RegExp(r'^https://github\.com/([^/@\s]+)/([^/@\s]+?)(?:\.git)?/?$')
      .firstMatch(origin);
  if (m == null) {
    throw UpdateStop(
      'no_github_origin',
      "the download's origin is not an https://github.com/<owner>/<repo> "
          "URL, so the release's binaries cannot be located; install from the "
          'GitHub repository, or pass --release-url for a mirror',
    );
  }
  return 'https://github.com/${m.group(1)}/${m.group(2)}';
}

/// Removes `com.apple.quarantine` from the checked part file and confirms it
/// is gone, or stops before the file first runs (C16 of native-cli-
/// distribution).
Future<void> _unquarantine(
  String part,
  String asset,
  String ref,
  String cwd,
) async {
  const flag = 'com.apple.quarantine';
  Future<LaunchResult> xattr(List<String> args) => launch(
    ['xattr', ...args, part],
    cwd: cwd,
    deadline: const Duration(seconds: 30),
  );

  final probe = await xattr(['-p', flag]);
  if (probe.startFailed) {
    throw UpdateStop(
      'quarantine_not_cleared',
      '$asset of release $ref: xattr was not found, so the quarantine flag '
          'cannot be cleared; the file was not run and nothing was placed',
    );
  }
  if (probe.exitCode != 0) return; // no quarantine flag on the file
  final removed = await xattr(['-d', flag]);
  if (removed.exitCode != 0 || (await xattr(['-p', flag])).exitCode == 0) {
    final said = String.fromCharCodes(removed.stderr).trim();
    final detail = said.isEmpty ? 'exit ${removed.exitCode}' : said;
    throw UpdateStop(
      'quarantine_not_cleared',
      '$asset of release $ref: removing com.apple.quarantine failed '
          '($detail); the file was not run and nothing was placed',
    );
  }
}
