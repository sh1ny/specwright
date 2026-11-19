import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;

import '../commands/vcs.dart';
import '../vcs/args.dart';
import '../vcs/codec.dart';
import '../vcs/document.dart';
import '../vcs/stop.dart';
import '../vcs/tool_runner.dart';

/// Answers the state read of a `check branch` step instead of the in-process
/// state operation, so that a test can check a jj or GitButler branch without
/// that tool. Tests only.
typedef UndoStateReader = Future<Map<String, Object?>> Function(
  String repo,
  String? code,
  String? branch,
);

VcsStop _usage(String message) => VcsStop('usage', message, code: 2);

VcsStop _failed(String message) => VcsStop('undo_step_failed', message);

/// `sw finish undo-step <kind> ...`: one primitive of an undo plan, run in
/// [cwd] (default: the current directory), which prints nothing and exits 0 on
/// success. A failure prints one stop document and exits 1 (a bad call, 2), so
/// the runner stops at the step.
///
/// C5: The undo primitives exist so a plan stays something the user runs step
/// by step; no command may run a whole undo. Only the kinds below exist (a new
/// kind needs a design change): `check` (`branch`, `tip`, `index`, `clean`,
/// `unchanged`, `absent`), `mkdir`, `copy`, `move`, `remove`, `rmdir-if-empty`, `write-blob`,
/// `write-text` and `merge-back`. A whole-undo command was rejected because it
/// would turn a plan the user reviews into an action the agent runs.
Future<int> runUndoStep(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  String? cwd,
  UndoStateReader? stateReader,
  void Function(String line)? writeErr,
}) async {
  // the old script's guards said why on stderr; the stop document goes to
  // stdout as every `sw` stop does
  final say = writeErr ?? stderr.writeln;
  try {
    await _UndoStep(cwd ?? Directory.current.path, stateReader).run(args);
    return 0;
  } on VcsStop catch (stop) {
    writeOut(documentBytes(stop.object()));
    say(stop.message);
    return stop.code;
  } on FileSystemException catch (e) {
    final stop = _failed('${e.message}: ${e.path ?? ''}'.trim());
    writeOut(documentBytes(stop.object()));
    say(stop.message);
    return 1;
  }
}

class _UndoStep {
  _UndoStep(this.cwd, this.stateReader);

  final String cwd;
  final UndoStateReader? stateReader;

  String at(String path) => p.isAbsolute(path) ? path : p.join(cwd, path);

  Future<ToolResult> _spawn(List<String> command) {
    final env = {...Platform.environment}
      ..putIfAbsent('GIT_TERMINAL_PROMPT', () => '0');
    return runTool(cwd, command, environment: env);
  }

  Future<void> run(List<String> args) async {
    if (args.isEmpty) throw _usage('undo-step needs a kind');
    final kind = args.first;
    final rest = args.sublist(1);
    switch (kind) {
      case 'check':
        return check(rest);
      case 'mkdir':
        for (final d in rest) {
          Directory(at(d)).createSync(recursive: true);
        }
      case 'copy':
        _count(kind, rest, 2);
        File(at(rest[0])).copySync(at(rest[1]));
      case 'move':
        _count(kind, rest, 2);
        final from = at(rest[0]);
        if (FileSystemEntity.isDirectorySync(from)) {
          Directory(from).renameSync(at(rest[1]));
        } else {
          File(from).renameSync(at(rest[1]));
        }
      case 'remove':
        for (final f in rest) {
          if (FileSystemEntity.typeSync(at(f), followLinks: false) !=
              FileSystemEntityType.notFound) {
            File(at(f)).deleteSync();
          }
        }
      case 'rmdir-if-empty':
        for (final d in rest) {
          try {
            Directory(at(d)).deleteSync();
          } on FileSystemException {
            // never fails: the directory may be missing or still hold a file
          }
        }
      case 'write-blob':
        _count(kind, rest, 3);
        final r = await _spawn([
          'git',
          'cat-file',
          '--filters',
          '${rest[0]}:${rest[1]}',
        ]);
        if (r.exitCode != 0) {
          throw _failed(
            'cannot read ${rest[0]}:${rest[1]}: ${decodeText(r.stderr).trim()}',
          );
        }
        File(at(rest[2])).writeAsBytesSync(r.stdout);
      case 'write-text':
        _count(kind, rest, 2);
        File(at(rest[0])).writeAsBytesSync(utf8.encode('${rest[1]}\n'));
      case 'merge-back':
        _count(kind, rest, 3);
        final r = await _spawn([
          'git',
          'merge-file',
          '-L',
          'rerun',
          '-L',
          'archived',
          '-L',
          'amended',
          rest[0],
          rest[1],
          rest[2],
        ]);
        if (r.exitCode != 0) {
          throw _failed(
            'merging ${rest[2]} into ${rest[0]} stopped (exit ${r.exitCode}); '
            'conflict markers are in the file and both copies stay saved',
          );
        }
      default:
        throw _usage('unknown undo-step kind $kind');
    }
  }

  void _count(String kind, List<String> rest, int n) {
    if (rest.length != n) throw _usage('undo-step $kind takes $n arguments');
  }

  Future<void> check(List<String> args) async {
    if (args.isEmpty) throw _usage('undo-step check needs a kind');
    final positional = <String>[];
    final paths = <String>[];
    final options = <String, String>{};
    var jj = false;
    for (var i = 1; i < args.length; i++) {
      final a = args[i];
      if (a == '--') {
        paths.addAll(args.sublist(i + 1));
        break;
      } else if (a == '--jj') {
        jj = true;
      } else if (const ['--backend', '--code', '--message'].contains(a) &&
          i + 1 < args.length) {
        options[a] = args[++i];
      } else {
        positional.add(a);
      }
    }
    switch (args.first) {
      case 'branch':
        _count('check branch', positional, 1);
        return checkBranch(
          positional[0],
          options['--backend'] ?? 'git',
          options['--code'],
        );
      case 'tip':
        _count('check tip', positional, 2);
        final r = await _spawn(['git', 'rev-parse', positional[0]]);
        final now = decodeText(r.stdout).trim();
        if (r.exitCode != 0 || now != positional[1]) {
          throw _failed(
            '${positional[0]} is at ${now.isEmpty ? '(nothing)' : now}, not '
            'at ${positional[1]} the plan was made for',
          );
        }
      case 'index':
        final r = await _spawn(['git', 'diff', '--cached', '--quiet']);
        if (r.exitCode != 0) {
          throw _failed('The index differs from HEAD; unstage or commit it');
        }
      case 'clean':
        final r = jj
            ? await _spawn(['jj', 'diff', '-r', '@', '--name-only', ...paths])
            : await _spawn([
                'git',
                '--no-optional-locks',
                'status',
                '--porcelain',
                '--untracked-files=all',
                if (paths.isNotEmpty) '--',
                ...paths,
              ]);
        final dirty = decodeText(r.stdout).trim();
        if (r.exitCode != 0 || dirty.isNotEmpty) {
          throw _failed(
            'Not clean${paths.isEmpty ? '' : ' under ${paths.join(' ')}'}: $dirty',
          );
        }
      case 'unchanged':
        _count('check unchanged', positional, 1);
        final r = await _spawn([
          'git',
          'diff',
          '--quiet',
          positional[0],
          'HEAD',
          if (paths.isNotEmpty) '--',
          ...paths,
        ]);
        if (r.exitCode != 0) {
          throw _failed(
            options['--message'] ??
                'HEAD differs from ${positional[0]} under ${paths.join(' ')}',
          );
        }
      case 'absent':
        _count('check absent', positional, 1);
        final path = positional[0];
        if (FileSystemEntity.typeSync(at(path), followLinks: false) !=
            FileSystemEntityType.notFound) {
          throw _failed(options['--message'] ?? '$path exists');
        }
      default:
        throw _usage('unknown undo-step check ${args.first}');
    }
  }

  /// The backend's own branch value, read in process: git's current branch,
  /// jj's role branch, or the named GitButler branch when it is applied.
  Future<void> checkBranch(
    String expected,
    String backend,
    String? code,
  ) async {
    final String now;
    if (backend == 'git') {
      final r = await _spawn(['git', 'branch', '--show-current']);
      now = decodeText(r.stdout).trim();
    } else {
      final repo = cwd;
      final branch = backend == 'gitbutler' ? expected : null;
      final reader = stateReader;
      final Map<String, Object?> state;
      if (reader != null) {
        state = await reader(repo, code, branch);
      } else {
        final role = code != null
            ? ['--role', 'store', '--code', at(code)]
            : ['--role', 'code'];
        if (branch != null) role.addAll(['--branch', branch]);
        final parsed = parseVcsArguments(['state', '--repo', repo, ...role]);
        state = (await stateDocument(
          await openSession(VcsContext(parsed, '', '')),
        )).cast();
      }
      now = '${state['branch'] ?? ''}';
    }
    if (now != expected) {
      throw _failed(
        'On branch ${now.isEmpty ? '(none)' : now}, but the plan is for '
        '$expected',
      );
    }
  }
}
