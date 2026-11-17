import 'dart:io';

import '../process/limits.dart';
import '../pr/gh.dart' show runBoundedCommand;
import '../settings/values.dart' show pyUtf8Decode;
import 'git.dart';
import 'options.dart';
import 'repo.dart';
import 'text.dart';

final RegExp semver = RegExp(r'^(\d+)\.(\d+)\.(\d+)$');

/// `(major, minor, patch)` of a `MAJOR.MINOR.PATCH` text.
(int, int, int) versionTuple(String version) {
  final m = semver.firstMatch(version)!;
  return (
    int.parse(m.group(1)!),
    int.parse(m.group(2)!),
    int.parse(m.group(3)!),
  );
}

/// -1, 0 or 1 as [a] is below, equal to or above [b].
int compareVersions((int, int, int) a, (int, int, int) b) {
  if (a.$1 != b.$1) return a.$1.compareTo(b.$1);
  if (a.$2 != b.$2) return a.$2.compareTo(b.$2);
  return a.$3.compareTo(b.$3);
}

/// What a store's `openspec/.specwright/STORE` records: the version of the
/// schema in the store and the project that owns it.
class StoreRecord {
  const StoreRecord(this.version, this.owner);

  final String version;
  final String owner;
}

/// `<root>/openspec/.specwright/STORE`.
String storeRecordPath(String root) => '$root/openspec/.specwright/STORE';

/// Reads a store record (two lines, `version: <x.y.z>` and `owner: <id>`).
/// The record is null when the file is absent or unreadable; the problem
/// (text) is set for an unreadable one.
({StoreRecord? record, String? problem}) readStoreRecord(String path) {
  final file = File(path);
  if (!file.existsSync()) return (record: null, problem: null);
  final text = pyUtf8Decode(file.readAsBytesSync()).replaceAll('\r', '');
  final v = RegExp(
    r'^version:[ \t]*(\S+)[ \t]*$',
    multiLine: true,
  ).firstMatch(text);
  final w = RegExp(
    r'^owner:[ \t]*(\S.*?)[ \t]*$',
    multiLine: true,
  ).firstMatch(text);
  final missing = [if (v == null) 'version', if (w == null) 'owner'];
  if (missing.isNotEmpty) {
    return (record: null, problem: '$path has no ${missing.join(' and no ')}');
  }
  if (!semver.hasMatch(v!.group(1)!)) {
    return (
      record: null,
      problem:
          "$path has the version ${_repr(v.group(1)!)}, not MAJOR.MINOR.PATCH "
          '(field version)',
    );
  }
  return (record: StoreRecord(v.group(1)!, w!.group(1)!), problem: null);
}

String _repr(String s) {
  final quote = s.contains("'") && !s.contains('"') ? '"' : "'";
  return '$quote${s.replaceAll(r'\', r'\\').replaceAll(quote, '\\$quote')}$quote';
}

/// A project's relation to its planning root (design D5 of the update's
/// store roles): `none` (the root is in the code checkout's own repo),
/// `claim` (a store with no STORE record), `owner` (STORE names this
/// project), `other` (STORE names another project), or null when the record
/// is unreadable ([problem] says why).
class StoreInfo {
  const StoreInfo(this.role, this.record, this.problem, this.id);

  final String? role;
  final StoreRecord? record;
  final String? problem;
  final String? id;
}

/// Works out the store role of the project (`store_info`).
Future<StoreInfo> storeInfo(UpdateRepo repo) async {
  if (!await repo.isStore()) return const StoreInfo('none', null, null, null);
  final read = readStoreRecord(storeRecordPath(repo.root));
  final me = await repo.ownerId();
  final record = read.record;
  final role = read.problem != null
      ? null
      : record == null
      ? 'claim'
      : record.owner == me
      ? 'owner'
      : 'other';
  return StoreInfo(role, record, read.problem, me);
}

/// The most time `git ls-remote --tags` may take, and the most it may print.
const Duration tagLookupDeadline = Duration(seconds: 60);

/// The highest `vMAJOR.MINOR.PATCH` tag of the download's origin with the
/// given [major] and [minor], from `git ls-remote --tags --refs`. The tag is
/// null when none is named, and then the problem says why (design D8,
/// native-cli-update: the lookup is bounded).
///
/// The run is bounded: [tagLookupDeadline] (lowered by the network deadline
/// variables of [environment], never raised), 32 MiB of stdout, and the whole
/// process tree is stopped at either bound; the problem is then
/// `deadline_exceeded: git ls-remote --tags` or
/// `response_too_large: git ls-remote --tags`, and no tag is named from a
/// partial list. [helperCommand] replaces the helper's command line (tests).
Future<({String? tag, String? problem})> highestTag(
  UpdateOptions options,
  int major,
  int minor, {
  GitRunner? git,
  Map<String, String>? environment,
  List<String>? helperCommand,
}) async {
  final download = options.download ?? options.code;
  final origin = await (git ?? runUpdateGit)(download, [
    'remote',
    'get-url',
    'origin',
  ]);
  final url = pyStrip(origin.text);
  if (!origin.ok || url.isEmpty) {
    return (tag: null, problem: 'the download has no origin to list tags from');
  }
  final env = {
    ...(environment ?? Platform.environment),
    'GIT_TERMINAL_PROMPT': '0',
  };
  final resolved = resolveLimits(env, paged: false);
  final limits = ResolvedLimits(
    deadline: resolved.deadline < tagLookupDeadline
        ? resolved.deadline
        : tagLookupDeadline,
    maxBytes: resolved.maxBytes,
  );
  final result = await runBoundedCommand(
    download,
    ['git', 'ls-remote', '--tags', '--refs', url],
    environment: env,
    limits: limits,
    helperCommand: helperCommand,
  );
  final limit = result.limit;
  if (limit != null) {
    return (tag: null, problem: '${limit.label}: git ls-remote --tags');
  }
  if (result.exitCode != 0) {
    final said = pyStrip(decodeLossy(result.stderr))
        .split(RegExp(r'\r\n|\n|\r'));
    final first = said.first.isEmpty ? 'no output' : said.first;
    return (tag: null, problem: 'git ls-remote --tags failed: $first');
  }
  (int, int, int)? best;
  final pattern = RegExp(r'refs/tags/v(\d+)\.(\d+)\.(\d+)$');
  for (final line in decodeLossy(result.stdout).split(RegExp(r'\r\n|\n|\r'))) {
    final m = pattern.firstMatch(pyStrip(line));
    if (m == null) continue;
    final v = (
      int.parse(m.group(1)!),
      int.parse(m.group(2)!),
      int.parse(m.group(3)!),
    );
    if (v.$1 == major && v.$2 == minor) {
      if (best == null || compareVersions(v, best) > 0) best = v;
    }
  }
  if (best == null) {
    return (tag: null, problem: 'no tag v$major.$minor.* exists');
  }
  return (tag: 'v${best.$1}.${best.$2}.${best.$3}', problem: null);
}
