// Shared scaffolding of the stage, swap, recover and pack tests of `sw update`:
// a download tree per version, a code checkout with one version installed, the
// command runner and a file-operation seam that dies as a killed process does.
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart' show sha256;
import 'package:specwright_cli/src/commands/update.dart';
import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:specwright_cli/src/update/openspec.dart';
import 'package:test/test.dart';

String fwd(String path) => path.replaceAll(r'\', '/');

void git(String dir, List<String> args) {
  final r = Process.runSync('git', [
    '-C',
    dir,
    '-c',
    'user.name=t',
    '-c',
    'user.email=t@example.com',
    '-c',
    'commit.gpgsign=false',
    ...args,
  ]);
  expect(r.exitCode, 0, reason: '${r.stdout}${r.stderr}');
}

String sha(List<int> bytes) => sha256.convert(bytes).toString();

/// `{relative posix path: bytes}` of every file under [dir], and an entry of
/// `null` for each directory, as the evals' `snapshot` does.
Map<String, List<int>?> snapshot(String dir) {
  final out = <String, List<int>?>{};
  final root = Directory(dir);
  if (!root.existsSync()) return out;
  for (final e in root.listSync(recursive: true, followLinks: false)) {
    final rel = fwd(e.path).substring(fwd(dir).length + 1);
    if (e is! File) {
      out[rel] = null;
      continue;
    }
    try {
      out[rel] = e.readAsBytesSync();
    } on PathNotFoundException {
      // gone between the listing and the read: git's background maintenance
      // makes and removes .git/objects/maintenance.lock on macOS
    }
  }
  return out;
}

/// [snapshot] with file contents as text, for readable failures.
Map<String, String?> textSnapshot(String dir) => {
  for (final e in snapshot(dir).entries)
    e.key: e.value == null ? null : utf8.decode(e.value!, allowMalformed: true),
};

void put(String base, String rel, String text, {bool executable = false}) {
  final file = File('$base/$rel')..createSync(recursive: true);
  file.writeAsStringSync(text);
  if (executable && !Platform.isWindows) {
    Process.runSync('chmod', ['755', file.path]);
  }
}

/// One version's download tree: two skills (one holds a script), one agent
/// file with a `model:` line, the schema, `VERSION`.
String makeDownload(String dir, String version) {
  put(dir, 'VERSION', '$version\n');
  put(dir, 'skills/specwright-alpha/SKILL.md', 'alpha $version\n');
  put(
    dir,
    'skills/specwright-alpha/scripts/run.sh',
    '#!/bin/sh\necho $version\n',
    executable: true,
  );
  put(dir, 'skills/specwright-beta/SKILL.md', 'beta $version\n');
  put(
    dir,
    'agents/claude/specwright-impl.md',
    '---\nname: impl\nmodel: sonnet\n---\nbody $version\n',
  );
  put(
    dir,
    'schemas/specwright/schema.yaml',
    'name: specwright\nartifacts:\n  - id: proposal\n# $version\n',
  );
  return dir;
}

/// A scratch code checkout (a git repo) with the paths `sw update` is given.
class Layout {
  Layout(this.tmp, {String? root})
    : code = '${fwd(tmp.path)}/code',
      root = root ?? '${fwd(tmp.path)}/code';

  final Directory tmp;
  final String code;
  final String root;

  String get skills => '$code/.claude/skills';
  String get agents => '$code/.claude/agents';
  String get schema => '$root/openspec/schemas/specwright';
  String get state => '$code/openspec/.specwright';
  String get journal => '$state/update.json';
  String get lock => '$state/update.lock';
  String get versionFile => '$state/VERSION';
  String get config => '$root/openspec/config.yaml';

  /// The options of this checkout, before the subcommand.
  List<String> args(String download, {List<String> more = const []}) => [
    '--code',
    code,
    '--root',
    root,
    '--skills',
    skills,
    '--agents',
    'claude=$agents',
    '--download',
    download,
    ...more,
  ];

  /// Makes the checkout: a git repo that has [version] installed from a
  /// download made here (none: a fresh install).
  void init({String? version, bool commit = true}) {
    Directory(code).createSync(recursive: true);
    git(code, ['init', '-q', '-b', 'main']);
    put(code, 'README', 'x\n');
    if (version != null) {
      final from = makeDownload('${fwd(tmp.path)}/dl-$version', version);
      installFrom(from);
    }
    git(code, ['add', '-A']);
    if (commit) git(code, ['commit', '-q', '-m', 'first']);
  }

  /// What the install prompt installs, from [download].
  void installFrom(String download) {
    for (final name in ['specwright-alpha', 'specwright-beta']) {
      copyTree('$download/skills/$name', '$skills/$name');
    }
    copyTree('$download/agents/claude', agents);
    copyTree('$download/schemas/specwright', schema);
    put(state, 'VERSION', File('$download/VERSION').readAsStringSync());
    put(root, 'openspec/config.yaml', 'schema: specwright\n');
  }

  /// The staging directories under the checkout, relative, sorted.
  List<String> stagingDirs() => [
    for (final e in Directory(code).listSync(recursive: true))
      if (e is Directory &&
          fwd(e.path).split('/').last.startsWith('.specwright-update-'))
        fwd(e.path).substring(fwd(code).length + 1),
  ]..sort();

  /// What is installed: skills, agents, schema and the version stamp.
  Map<String, Object?> installed() => {
    'skills': textSnapshot(skills),
    'agents': textSnapshot(agents),
    'schema': textSnapshot(schema),
    'version': File(versionFile).existsSync()
        ? File(versionFile).readAsStringSync()
        : null,
  };
}

void copyTree(String from, String to) {
  Directory(to).createSync(recursive: true);
  for (final e in Directory(from).listSync(followLinks: false)) {
    final name = fwd(e.path).split('/').last;
    if (e is Directory) {
      copyTree(e.path, '$to/$name');
    } else if (e is File) {
      e.copySync('$to/$name');
    }
  }
}

/// A file-operation seam for the interruption tests: once the process "dies"
/// (the kill operation was reached) every later operation throws [Killed], so
/// nothing a `finally` block does afterwards reaches the disk.
class KillableOps extends UpdateFileOps {
  KillableOps._(Map<String, String> env, this._kill)
    : super(environment: env, exitProcess: _kill.call);

  /// Counts into [countFile] and dies at operation [killAt] (never when null).
  factory KillableOps(String countFile, {int? killAt}) {
    final kill = _Kill();
    return KillableOps._({
      'SPECWRIGHT_UPDATE_COUNT': countFile,
      if (killAt != null) 'SPECWRIGHT_UPDATE_KILL_AT': '$killAt',
    }, kill);
  }

  final _Kill _kill;

  bool get dead => _kill.dead;

  void _alive() {
    if (_kill.dead) throw Killed();
  }

  @override
  void mkdir(String path) {
    _alive();
    super.mkdir(path);
  }

  @override
  bool mkdirExclusive(String path) {
    _alive();
    return super.mkdirExclusive(path);
  }

  @override
  void copy(String source, String destDir) {
    _alive();
    super.copy(source, destDir);
  }

  @override
  void rename(String from, String to) {
    _alive();
    super.rename(from, to);
  }

  @override
  void remove(String path) {
    _alive();
    super.remove(path);
  }
}

class _Kill {
  bool dead = false;

  void call(int code) {
    dead = true;
    throw Killed();
  }
}

/// The process was killed at the seam.
class Killed implements Exception {}

/// Runs `sw update [args]`: the exit status and the one document it printed.
/// [env] is the process environment the command sees (the kill-seam and home
/// variables); [ops] and [openspec] replace the file-operation wrapper and the
/// `openspec` runner.
Future<(int, Map<String, Object?>)> update(
  List<String> args, {
  Map<String, String>? env,
  UpdateFileOps? ops,
  OpenspecRunner? openspec,
  String? cwd,
}) async {
  final out = <int>[];
  final code = await runUpdateCommand(
    args,
    writeOut: out.addAll,
    cwd: cwd,
    environment: env ?? const {},
    fileOps: ops,
    openspec: openspec,
  );
  final text = utf8.decode(out);
  Object? doc;
  try {
    doc = jsonDecode(text);
  } on FormatException {
    fail('no JSON document (exit $code): $text');
  }
  return (code, doc as Map<String, Object?>);
}

/// Runs [args] with a seam that dies at operation [killAt]; true when it did
/// (the disk then holds what a killed process leaves).
Future<bool> runKilled(
  List<String> args,
  String countFile,
  int killAt, {
  OpenspecRunner? openspec,
}) async {
  final ops = KillableOps(countFile, killAt: killAt);
  try {
    await update(args, ops: ops, openspec: openspec);
  } on Killed {
    return true;
  }
  return ops.dead;
}

/// The lines of a count file.
List<String> countLog(String countFile) => File(countFile).existsSync()
    ? File(countFile).readAsLinesSync().where((l) => l.isNotEmpty).toList()
    : [];

Map<String, Object?> readJournal(String path) =>
    jsonDecode(File(path).readAsStringSync()) as Map<String, Object?>;

/// An `openspec` runner that finds every change valid.
Future<OpenspecResult> passingOpenspec(
  List<String> args,
  String cwd, {
  Duration? timeout,
}) async => const OpenspecResult(0, '{"items":[{"valid":true}]}', '');
