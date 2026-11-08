import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/pr/context.dart';

import '../vcs/bash_support.dart';

/// A fresh temp directory for one test, removed by [dispose].
class Scratch {
  Scratch() : dir = Directory.systemTemp.createTempSync('sw-pair-test-');

  final Directory dir;

  void dispose() {
    try {
      dir.deleteSync(recursive: true);
    } on FileSystemException {
      // git may still hold a file on Windows; the system temp cleaner gets it
    }
  }

  String get path => dir.path.replaceAll(r'\', '/');

  Directory sub(String name) =>
      Directory('$path/$name')..createSync(recursive: true);
}

/// `git <args>` in [dir], failing the test setup when it fails.
String git(String dir, List<String> args) {
  final r = Process.runSync(
    'git',
    [
      '-c',
      'user.name=t',
      '-c',
      'user.email=t@example.com',
      '-c',
      'commit.gpgsign=false',
      ...args,
    ],
    workingDirectory: dir,
    stdoutEncoding: utf8,
    stderrEncoding: utf8,
  );
  if (r.exitCode != 0) {
    throw StateError('git ${args.join(' ')} failed: ${r.stderr}');
  }
  return (r.stdout as String).trim();
}

/// An initialized repo in [dir] on branch `main`.
void initRepo(String dir, {String? origin}) {
  Directory(dir).createSync(recursive: true);
  git(dir, ['init', '-q', '-b', 'main']);
  if (origin != null) git(dir, ['remote', 'add', 'origin', origin]);
}

void commitFile(String dir, String rel, String text, [String msg = 'c']) {
  final f = File('$dir/$rel')..createSync(recursive: true);
  f.writeAsBytesSync(utf8.encode(text));
  git(dir, ['add', '--', rel]);
  git(dir, ['commit', '-q', '-m', msg]);
}

/// What one command printed: its exit status, the parsed JSON line and the raw text.
class Ran {
  Ran(this.code, this.stdout, this.stderr);

  final int code;
  final String stdout;
  final String stderr;

  Map<String, Object?> get json =>
      jsonDecode(stdout.trim()) as Map<String, Object?>;
}

/// A [PrContext] over real git (through Git Bash), recording what the command printed. [env] is the environment the
/// command reads (default: this process's).
class PairRun {
  PairRun({Map<String, String>? env, PrGh? gh}) {
    ctx = PrContext(
      scriptsDir: 'scripts',
      bash: findBash() ?? 'bash',
      writeOut: out.addAll,
      writeErr: err.addAll,
      environment: env,
      gh: gh,
    );
  }

  final List<int> out = [];
  final List<int> err = [];
  late final PrContext ctx;

  Ran result(int code) => Ran(code, utf8.decode(out), utf8.decode(err));
}
