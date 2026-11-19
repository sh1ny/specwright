// The project version check at the entry (ADR 0040, design D1 and D2): every
// project command checks the project's openspec/.specwright/VERSION against
// this binary's own version before any other work, and stops with
// `sw_mismatch` naming the binary it expected.
import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;

import '../commands/version.dart';
import '../update/sw_install.dart' show swHome;

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

/// The version [root]'s VERSION file holds, or the reason it holds none.
({String? version, String? problem}) readProjectVersion(String root) {
  final file = File(p.join(root, 'openspec', '.specwright', 'VERSION'));
  final List<int> bytes;
  try {
    final handle = file.openSync();
    try {
      bytes = handle.readSync(_maxVersionBytes + 1);
    } finally {
      handle.closeSync();
    }
  } on FileSystemException {
    return (
      version: null,
      problem:
          'no installed version found in $root: ${file.path} does not exist',
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
      problem: '$shown is not a version (expected x.y.z) in ${file.path}',
    );
  }
  return (version: text, problem: null);
}

/// The first directory at or above [start] that holds `.git` (a directory or,
/// in a linked worktree, a file); [start] itself when there is none.
String projectRoot(String start) {
  final from = p.normalize(p.absolute(start));
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
  final root = projectRoot(start);
  final found = readProjectVersion(root);
  final String message;
  if (found.version == version) return null;
  if (found.version == null) {
    message =
        'sw $version cannot check this project: ${found.problem}; rerun the install prompt';
  } else {
    final home = swHome(environment ?? Platform.environment)
        .replaceAll('\\', '/');
    final binary =
        '$home/.specwright/bin/${found.version}/sw${Platform.isWindows ? '.exe' : ''}';
    message =
        'sw $version does not match this project, which is at ${found.version}; '
        'run $binary, or rerun the install prompt';
  }
  return {'ok': false, 'error': 'sw_mismatch', 'message': message};
}

/// What the leading `--project` and the command's own arguments choose.
class ProjectChoice {
  ProjectChoice(this.dir, this.rest);

  /// The directory to start the VERSION search from.
  final String dir;

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
    if (rest.isNotEmpty && isProject(rest.first)) {
      throw ProjectUsage('--project is given twice');
    }
  }
  if (project != null) return ProjectChoice(project, rest);
  if (rest.isEmpty) return ProjectChoice(cwd, rest);
  final command = rest.first;
  final tail = rest.sublist(1);
  final own =
      _optionValue(tail, '--code') ??
      (command == 'vcs' ? _optionValue(tail, '--repo') : null) ??
      (command == 'release' || command == 'finish'
          ? _optionValue(tail, '--dir')
          : null);
  return ProjectChoice(own ?? cwd, rest);
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
