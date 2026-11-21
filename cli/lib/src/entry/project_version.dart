// The project version check at the entry (ADR 0040, design D1 and D2): every
// project command checks the project's openspec/.specwright/VERSION against
// this binary's own version before any other work, and stops with
// `sw_mismatch` naming the binary it expected.
import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;

import '../commands/version.dart';
import '../update/sw_install.dart' show swHome;
import 'regular_file.dart';

/// The commands that check the project's version (native-cli "Project
/// commands check the project's version"). `version`, `run`, `update`,
/// `pr reviewers` and the process helper check nothing.
const projectCommands = {
  'vcs',
  'pr',
  'as',
  'commit',
  'finish',
  'review',
  'release',
  'gate',
};

const _maxVersionBytes = 4096;
final _version = RegExp(r'^\d+\.\d+\.\d+([-+][0-9A-Za-z.+-]+)?$');

/// The version [root]'s VERSION file holds, or the reason it holds none. The
/// stamp is read through [readRegularFile], so a FIFO, device, socket or
/// directory in its place is refused as not a regular file without being
/// opened.
({String? version, String? problem}) readProjectVersion(String root) {
  final path = p.join(root, 'openspec', '.specwright', 'VERSION');
  final List<int> bytes;
  try {
    final read = readRegularFile(path, limit: _maxVersionBytes + 1);
    if (read == null) {
      return (
        version: null,
        problem: 'no installed version found in $root: $path does not exist',
      );
    }
    bytes = read;
  } on NotRegularFile {
    return (version: null, problem: '$path is not a regular file');
  } on FileSystemException {
    return (
      version: null,
      problem: 'no installed version found in $root: $path does not exist',
    );
  }
  String text;
  try {
    text = const Utf8Decoder(allowMalformed: false).convert(bytes).trim();
  } on FormatException {
    text = '';
  }
  if (bytes.length > _maxVersionBytes || !_version.hasMatch(text)) {
    final shown = text.isEmpty || text.length > 60 || text.contains('\n')
        ? 'the VERSION file'
        : text;
    return (
      version: null,
      problem: '$shown is not a version (expected x.y.z) in $path',
    );
  }
  return (version: text, problem: null);
}

/// The first directory at or above [start] that holds `.git` (a directory or,
/// in a linked worktree, a file); [start] itself when there is none.
///
/// C47: an existing [start] is resolved physically first (symbolic links
/// resolved on its absolute path, so a `link/..` names the directory above the
/// link's target) before the walk for `.git`, for every project command's
/// version check. `--project` stays version-only (ADR 0040), so the repository
/// a command acts on is still chosen by its own options; a start that does not
/// exist keeps its lexical form.
String projectRoot(String start) {
  final absolute = p.absolute(start);
  var from = p.normalize(absolute);
  if (FileSystemEntity.typeSync(absolute) != FileSystemEntityType.notFound) {
    try {
      from = File(absolute).resolveSymbolicLinksSync();
    } on FileSystemException {
      // not resolvable after all: keep the lexical form
    }
  }
  for (var dir = from; ; dir = p.dirname(dir)) {
    if (FileSystemEntity.typeSync(p.join(dir, '.git')) !=
        FileSystemEntityType.notFound) {
      return dir;
    }
    if (p.dirname(dir) == dir) return from;
  }
}

/// The `sw_mismatch` document when the project at [start] does not match
/// [version]; null when it does. [environment] is where `SPECWRIGHT_HOME` is
/// read from (default: the process environment).
Map<String, Object?>? versionMismatch(
  String start, {
  String version = buildVersion,
  Map<String, String>? environment,
}) {
  final found = readProjectVersion(projectRoot(start));
  if (found.version == version) return null;
  return mismatchDocument(
    found: found.version,
    problem: found.problem,
    version: version,
    environment: environment,
  );
}

/// The `sw_mismatch` document for a project that holds [found] (a version that
/// differs from [version]) or, when [found] is null, no usable version for the
/// reason [problem].
Map<String, Object?> mismatchDocument({
  String? found,
  String? problem,
  String version = buildVersion,
  Map<String, String>? environment,
}) {
  final String message;
  if (found == null) {
    message =
        'sw $version cannot check this project: $problem; rerun the install prompt';
  } else {
    final home = swHome(environment ?? Platform.environment)
        .replaceAll(r'\', '/');
    final binary =
        '$home/.specwright/bin/$found/sw${Platform.isWindows ? '.exe' : ''}';
    message =
        'sw $version does not match this project, which is at $found; '
        'run $binary, or rerun the install prompt';
  }
  return {'ok': false, 'error': 'sw_mismatch', 'message': message};
}

/// Whether [version] is a version the stamp may hold (x.y.z, an optional
/// pre-release or build suffix).
bool isVersionText(String version) => _version.hasMatch(version);

/// The most bytes the VERSION reader accepts.
const maxVersionBytes = _maxVersionBytes;

/// What the leading `--project` and the command's own arguments choose.
class ProjectChoice {
  ProjectChoice(this.dir, this.rest, {this.project});

  /// The directory to start the VERSION search from.
  final String dir;

  /// The leading `--project <dir>` the call gave, null when it gave none.
  final String? project;

  /// The arguments after a leading `--project <dir>`, which is dropped.
  final List<String> rest;
}

/// Thrown for two leading `--project` options, or one without a value.
class ProjectUsage implements Exception {
  ProjectUsage(this.message);
  final String message;
}

/// Splits a leading `--project <dir>` off [args] and picks the directory
/// `<command> ...` is checked from (design D2): `--project`, else the
/// command's own `--code`, `--repo` for `vcs`, `--dir` for `release` and
/// `finish`, else [cwd].
ProjectChoice chooseProject(List<String> args, String cwd) {
  bool isProject(String a) => a == '--project' || a.startsWith('--project=');
  String? project;
  var rest = args;
  if (rest.isNotEmpty && isProject(rest.first)) {
    if (rest.first.startsWith('--project=')) {
      project = rest.first.substring('--project='.length);
      rest = rest.sublist(1);
    } else if (rest.length < 2) {
      throw ProjectUsage('--project needs a value');
    } else {
      project = rest[1];
      rest = rest.sublist(2);
    }
    if (project.isEmpty) throw ProjectUsage('--project needs a value');
    if (rest.isNotEmpty && isProject(rest.first)) {
      throw ProjectUsage('--project is given twice');
    }
  }
  if (project != null) return ProjectChoice(project, rest, project: project);
  if (rest.isEmpty) return ProjectChoice(cwd, rest);
  final command = rest.first;
  final tail = rest.sublist(1);
  final own =
      _optionValue(tail, '--code') ??
      (command == 'vcs' ? _optionValue(tail, '--repo') : null) ??
      (command == 'release' || command == 'finish'
          ? _optionValue(tail, '--dir')
          : null);
  // A value that names no directory (a root-relative path on Windows from a
  // caller that is not Git Bash, say) chooses nothing: the plan reports it.
  final named = own != null && Directory(own).existsSync();
  return ProjectChoice(named ? own : cwd, rest);
}

/// The last value of [name] among the options before a `--`.
String? _optionValue(List<String> args, String name) {
  String? value;
  for (var i = 0; i < args.length; i++) {
    final a = args[i];
    if (a == '--') break;
    if (a == name && i + 1 < args.length) {
      value = args[++i];
    } else if (a.startsWith('$name=')) {
      value = a.substring(name.length + 1);
    }
  }
  return value;
}
