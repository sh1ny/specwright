// The launch-site allowlist (D7 of native-cli-internal-calls).
//
// A scan over `lib/src` lists every call that starts a process and every
// caller of the process runners, and fails on:
//   * a launch site missing from [launchAllowlist] (or a count that moved);
//   * a `Process.start` / `Process.run` inside a function that is not a listed
//     runner (the runner list is closed);
//   * a self-launch (`Platform.resolvedExecutable`) other than the process
//     helper (`'__exec'`) and the reviewer evaluator (`'pr', 'reviewers'`
//     under `PrContext.bounded`), including a changed head, a list that is not
//     a literal, or an evaluator run without its bound;
//   * a shipped script name (`as.sh`, `vcs.sh`, ..., or any `.py`) in a launch's
//     arguments, or written anywhere under `lib/src` outside a listed
//     printed-command, message or label site.
//
// Registering a new launch (constraints C1 and C2): add the file and runner
// symbol to `calls` in [launchAllowlist] with its count and one of the kinds
// (external tool, process helper, reviewer evaluator, binary check). A
// `Process.start` / `Process.run` also names its enclosing `function`. A launch
// of `sw`'s own binary is never added for a shipped script or Python: only the
// two self-launches below exist. A new site that writes a shipped script's name
// in a message, a printed command or a label is added to `scriptNames` with its
// reason and count. The scanner is a pure function over a map of path to
// source, so the negative fixtures below run it on in-memory sources.
import 'dart:io';

import 'package:test/test.dart';

/// What a launch site is for.
enum LaunchKind {
  externalTool('external tool'),
  processHelper('process helper'),
  reviewerEvaluator('reviewer evaluator'),
  binaryCheck('binary check');

  const LaunchKind(this.label);
  final String label;
}

/// One runner symbol in one file: how many calls, of what kind.
class Call {
  const Call(this.count, this.kind, {this.function, this.labels = const {}});
  final int count;
  final LaunchKind kind;

  /// For `Process.start` and `Process.run`: the function that holds the call.
  final String? function;

  /// Script names a call's arguments may hold as a label (the `$0` of the
  /// fence prelude), not as a launched script.
  final Set<String> labels;
}

/// A permitted self-launch list: the literal head after the executable, and
/// the text that must stand right before the `[` of the list.
class SelfLaunch {
  const SelfLaunch(this.count, this.head, this.before, this.kind);
  final int count;
  final List<String> head;
  final String before;
  final LaunchKind kind;
}

/// A listed non-launch site for a script name: how many times, and why.
class ScriptSite {
  const ScriptSite(this.count, this.reason);
  final int count;
  final String reason;
}

class Allowlist {
  const Allowlist({
    required this.calls,
    required this.selfLaunches,
    required this.scriptNames,
  });

  /// file -> runner symbol -> call.
  final Map<String, Map<String, Call>> calls;

  /// file -> permitted self-launch.
  final Map<String, SelfLaunch> selfLaunches;

  /// file -> script name -> listed site.
  final Map<String, Map<String, ScriptSite>> scriptNames;
}

// ---------------------------------------------------------------------------
// The scanner: a pure function over path -> source and the allowlist.
// ---------------------------------------------------------------------------

/// The source with comments blanked ([code]: strings intact, so literals can
/// be read) and with string contents blanked as well ([skeleton]: only the
/// structure is left, so brackets and calls cannot be fooled by text). Both
/// keep the offsets of the original.
class _Stripped {
  _Stripped(this.code, this.skeleton);
  final String code;
  final String skeleton;
}

bool _isIdent(String c) => RegExp(r'[A-Za-z0-9_$]').hasMatch(c);

_Stripped _strip(String s) {
  final code = StringBuffer();
  final skel = StringBuffer();
  final n = s.length;
  // A string being read: its quote, whether it is triple-quoted and raw.
  String? quote;
  var triple = false;
  var raw = false;
  // Strings waiting while a `${...}` runs, and the brace depth inside it.
  final suspended = <(String, bool, bool)>[];
  final depths = <int>[];

  void both(String c) {
    code.write(c);
    skel.write(c);
  }

  void body(String c) {
    code.write(c);
    skel.write(c == '\n' ? '\n' : ' ');
  }

  var i = 0;
  while (i < n) {
    final c = s[i];
    if (quote != null) {
      if (!raw && c == r'\' && i + 1 < n) {
        body(c);
        body(s[i + 1]);
        i += 2;
        continue;
      }
      if (!raw && c == r'$' && i + 1 < n && s[i + 1] == '{') {
        suspended.add((quote, triple, raw));
        depths.add(0);
        quote = null;
        both(r'${');
        i += 2;
        continue;
      }
      if (triple ? s.startsWith(quote * 3, i) : c == quote) {
        final length = triple ? 3 : 1;
        both(s.substring(i, i + length));
        quote = null;
        i += length;
        continue;
      }
      body(c);
      i++;
      continue;
    }
    if (c == '/' && i + 1 < n && s[i + 1] == '/') {
      while (i < n && s[i] != '\n') {
        code.write(' ');
        skel.write(' ');
        i++;
      }
      continue;
    }
    if (c == '/' && i + 1 < n && s[i + 1] == '*') {
      var depth = 0;
      while (i < n) {
        if (s.startsWith('/*', i)) {
          depth++;
          code.write('  ');
          skel.write('  ');
          i += 2;
        } else if (s.startsWith('*/', i)) {
          depth--;
          code.write('  ');
          skel.write('  ');
          i += 2;
          if (depth == 0) break;
        } else {
          final keep = s[i] == '\n' ? '\n' : ' ';
          code.write(keep);
          skel.write(keep);
          i++;
        }
      }
      continue;
    }
    if (c == "'" || c == '"') {
      raw = i > 0 && s[i - 1] == 'r' && (i < 2 || !_isIdent(s[i - 2]));
      triple = s.startsWith(c * 3, i);
      quote = c;
      final length = triple ? 3 : 1;
      both(s.substring(i, i + length));
      i += length;
      continue;
    }
    if (suspended.isNotEmpty) {
      if (c == '{') {
        depths[depths.length - 1]++;
      } else if (c == '}') {
        if (depths.last == 0) {
          depths.removeLast();
          (quote, triple, raw) = suspended.removeLast();
          both('}');
          i++;
          continue;
        }
        depths[depths.length - 1]--;
      }
    }
    both(c);
    i++;
  }
  return _Stripped(code.toString(), skel.toString());
}

RegExp _fn(String name) =>
    RegExp('(?<![\\w\$])(?<![\\w>]>\\s)${RegExp.escape(name)}\\(');

/// Is the match at [start] (its `(` at [open]) a declaration, not a call?
/// Decided by what follows the parameter list: a body (`{`, `=>`, `async`,
/// `sync*`), or, for a name that starts its line, a constructor's
/// initializer list (`:`). Indentation decides nothing.
bool _isDeclaration(String skeleton, int start, int open) {
  final rest = skeleton.substring(_closeOf(skeleton, open) + 1).trimLeft();
  if (rest.startsWith('{') ||
      rest.startsWith('=>') ||
      RegExp(r'^(?:async|sync)\b').hasMatch(rest)) {
    return true;
  }
  final lineStart = skeleton.lastIndexOf('\n', start - 1) + 1;
  return rest.startsWith(':') &&
      skeleton.substring(lineStart, start).trim().isEmpty;
}

/// The runner symbols: every function that starts a process, and the wrappers
/// whose callers are launch sites (D7).
final Map<String, RegExp> _symbols = {
  'Process.start': RegExp(r'\bProcess\.start\('),
  'Process.run': RegExp(r'\bProcess\.run(?:Sync)?\('),
  'runFramed': _fn('runFramed'),
  'runTool': _fn('runTool'),
  'runToolCapped': _fn('runToolCapped'),
  'runText': _fn('runText'),
  'runGh': _fn('runGh'),
  'runBoundedCommand': _fn('runBoundedCommand'),
  'runFenced': _fn('runFenced'),
  'fencedText': _fn('fencedText'),
  'BoundedRun': _fn('BoundedRun'),
  'runExecHelper': _fn('runExecHelper'),
  'PrContext.tool': _fn('tool'),
  'PrContext.bounded': _fn('bounded'),
  'WorkflowTransport.runner': _fn('runner'),
};

final RegExp _selfToken = RegExp(
  r'\bPlatform\.(?:resolvedExecutable|executable)\b',
);

final RegExp _scriptName = RegExp(
  r'(?<![\w.-])(?:as|vcs|pr-pair|pr-snapshot|pr-reply|review-run|release|sw-path|finish)\.sh\b'
  r'|(?<![\w-])[\w-]+\.py\b',
);

const _notFunction = {
  'if', 'for', 'while', 'switch', 'catch', 'return', 'await', 'throw', //
  'else', 'yield', 'assert', 'super', 'this',
};

/// The name of the function whose declaration line (at indent 0 or 2) is the
/// nearest one above [offset] in [skeleton].
String? _enclosingFunction(String skeleton, int offset) {
  final lines = skeleton.substring(0, offset).split('\n');
  final decl = RegExp(
    r'^ {0,2}(?:@\w+\s+)?(?:static\s+)?((?:[\w<>?,.][\w<>?,. ]*\s)?)(_?[A-Za-z]\w*)\s*\(',
  );
  for (var i = lines.length - 1; i >= 0; i--) {
    final m = decl.firstMatch(lines[i]);
    if (m == null) continue;
    final first = m.group(1)!.trim().split(RegExp(r'\s+')).first;
    if (_notFunction.contains(first) || _notFunction.contains(m.group(2))) {
      continue;
    }
    return m.group(2);
  }
  return null;
}

/// The end of the parenthesis group opened at [open] in [skeleton].
int _closeOf(String skeleton, int open) {
  var depth = 0;
  for (var i = open; i < skeleton.length; i++) {
    final c = skeleton[i];
    if (c == '(') depth++;
    if (c == ')' && --depth == 0) return i;
  }
  return skeleton.length;
}

List<String> scanLaunchSites(Map<String, String> sources, Allowlist allow) {
  final findings = <String>[];
  final files = sources.keys.toList()..sort();
  for (final file in [
    ...allow.calls.keys,
    ...allow.selfLaunches.keys,
    ...allow.scriptNames.keys,
  ]) {
    if (!sources.containsKey(file)) {
      findings.add(
        '$file: listed in the allowlist but not found under lib/src',
      );
    }
  }
  for (final file in files) {
    final stripped = _strip(sources[file]!);
    final code = stripped.code;
    final skeleton = stripped.skeleton;
    final listed = allow.calls[file] ?? const <String, Call>{};

    // 1. runner calls: counts, closed runner list, launch arguments
    for (final entry in _symbols.entries) {
      final symbol = entry.key;
      final matches = [
        for (final m in entry.value.allMatches(skeleton))
          if (!_isDeclaration(skeleton, m.start, m.end - 1)) m,
      ];
      final call = listed[symbol];
      if (call == null) {
        if (matches.isNotEmpty) {
          findings.add(
            '$file: $symbol call is not on the allowlist (${matches.length} found)',
          );
        }
        continue;
      }
      if (matches.length != call.count) {
        findings.add(
          '$file: $symbol call count ${matches.length}, the allowlist lists ${call.count}',
        );
      }
      for (final m in matches) {
        if (symbol.startsWith('Process.')) {
          final function = _enclosingFunction(skeleton, m.start);
          if (function != call.function) {
            findings.add(
              '$file: $symbol in `$function` is not a listed runner (the allowlist names `${call.function}`)',
            );
          }
        }
        final open = m.end - 1;
        final close = _closeOf(skeleton, open);
        for (final name in _scriptName.allMatches(code, open)) {
          if (name.start > close) break;
          if (call.labels.contains(name.group(0))) continue;
          findings.add(
            '$file: $symbol launch argument names shipped script ${name.group(0)}',
          );
        }
      }
    }
    for (final symbol in listed.keys) {
      if (!_symbols.containsKey(symbol)) {
        findings.add(
          '$file: the allowlist names unknown runner symbol $symbol',
        );
      }
    }

    // 2. self-launches
    final selves = _selfToken.allMatches(skeleton).toList();
    final self = allow.selfLaunches[file];
    if (selves.isNotEmpty && self == null) {
      findings.add(
        '$file: self-launch of `sw` is not allowed here (${selves.length} found); only the process helper and the reviewer evaluator may start it',
      );
    } else if (self != null) {
      if (selves.length != self.count) {
        findings.add(
          '$file: self-launch count ${selves.length}, the allowlist lists ${self.count}',
        );
      }
      for (final m in selves) {
        _checkSelfLaunch(findings, file, code, skeleton, m, self);
      }
    }

    // 3. script names anywhere
    final counts = <String, int>{};
    for (final m in _scriptName.allMatches(code)) {
      counts.update(m.group(0)!, (v) => v + 1, ifAbsent: () => 1);
    }
    final sites = allow.scriptNames[file] ?? const <String, ScriptSite>{};
    for (final name in {...counts.keys, ...sites.keys}) {
      final found = counts[name] ?? 0;
      final expected = sites[name]?.count ?? 0;
      if (found != expected) {
        findings.add(
          '$file: shipped script name $name written $found times outside a listed site (listed: $expected)',
        );
      }
    }
  }
  return findings;
}

void _checkSelfLaunch(
  List<String> findings,
  String file,
  String code,
  String skeleton,
  RegExpMatch m,
  SelfLaunch self,
) {
  // the executable must be the first element of a list literal
  var i = m.start - 1;
  while (i >= 0 && skeleton[i].trim().isEmpty) {
    i--;
  }
  if (i < 0 || skeleton[i] != '[') {
    findings.add(
      '$file: self-launch list is not a literal that starts with the executable',
    );
    return;
  }
  final before = skeleton.substring(0, i).trimRight();
  if (!before.endsWith(self.before)) {
    findings.add(
      '$file: self-launch is not passed to `${self.before}` (it must run under its bound), found `${before.substring(before.length > 24 ? before.length - 24 : 0)}`',
    );
  }
  final head = <String>[];
  final item = RegExp(r"\s*,\s*'([^'\\]*)'");
  var at = m.end;
  while (true) {
    final next = item.matchAsPrefix(code, at);
    if (next == null) break;
    head.add(next.group(1)!);
    at = next.end;
  }
  final wanted = self.head;
  final same =
      head.length >= wanted.length &&
      [for (var k = 0; k < wanted.length; k++) head[k] == wanted[k]]
          .every((b) => b);
  if (!same) {
    findings.add(
      "$file: self-launch argument head [${head.map((h) => "'$h'").join(', ')}] differs from the allowed [${wanted.map((h) => "'$h'").join(', ')}]",
    );
  }
}

// ---------------------------------------------------------------------------
// The synthetic world the negative fixtures mutate.
// ---------------------------------------------------------------------------

const _miniAllow = Allowlist(
  calls: {
    'run.dart': {'runTool': Call(1, LaunchKind.externalTool)},
    'helper.dart': {
      'Process.start': Call(
        1,
        LaunchKind.processHelper,
        function: 'startHelper',
      ),
    },
    'snap.dart': {'PrContext.bounded': Call(1, LaunchKind.reviewerEvaluator)},
  },
  selfLaunches: {
    'helper.dart': SelfLaunch(
      1,
      ['__exec'],
      'helperCommand ??',
      LaunchKind.processHelper,
    ),
    'snap.dart': SelfLaunch(
      1,
      ['pr', 'reviewers'],
      '.bounded(',
      LaunchKind.reviewerEvaluator,
    ),
  },
  scriptNames: {
    'msg.dart': {'as.sh': ScriptSite(1, 'message prefix')},
  },
);

Map<String, String> _miniSources() => {
  'run.dart': '''
Future<void> go(String bash) async {
  // runTool(bash, '.', ['as.sh']) in a comment is not a call
  await runTool(bash, '.', ['git', 'status']);
}
''',
  'helper.dart': '''
class Helper {
  Helper({List<String>? helperCommand})
    : helperCommand = helperCommand ?? [Platform.resolvedExecutable, '__exec'];
  final List<String> helperCommand;
}

Future<void> startHelper(List<String> command) async {
  await Process.start(command.first, command.sublist(1));
}
''',
  'snap.dart': '''
Future<void> evaluate(ctx) async {
  final r = await ctx.bounded([
    Platform.resolvedExecutable,
    'pr',
    'reviewers',
    '--head',
    'x',
  ]);
}
''',
  'msg.dart': '''
void refuse(void Function(String) err) {
  err('as.sh: refused');
}
''',
};

bool _mentions(List<String> findings, List<String> parts) =>
    findings.any((f) => parts.every((p) => f.contains(p)));

void main() {
  group('the scanner on the synthetic world', () {
    test('the baseline is clean', () {
      expect(scanLaunchSites(_miniSources(), _miniAllow), isEmpty);
    });

    test('an unlisted runner call fails naming the file', () {
      // (a) a runner call in a file the allowlist does not name
      final a = _miniSources()
        ..['extra.dart'] = '''
Future<void> sneak(String bash) async {
  await runTool(bash, '.', ['rm', '-rf']);
}
''';
      final findings = scanLaunchSites(a, _miniAllow);
      expect(findings, isNotEmpty);
      expect(
        _mentions(findings, ['extra.dart', 'runTool', 'not on the allowlist']),
        isTrue,
        reason: findings.join('\n'),
      );

      // (j) an unawaited runner call at the start of a two-space-indented
      // statement: indentation does not make it a declaration
      final j = _miniSources()
        ..['indent.dart'] = '''
void go(String bash) {
  runTool(bash, '.', ['git', 'status']);
}
''';
      final jFindings = scanLaunchSites(j, _miniAllow);
      expect(
        _mentions(jFindings, [
          'indent.dart',
          'runTool',
          'not on the allowlist',
        ]),
        isTrue,
        reason: jFindings.join('\n'),
      );

      // (k) a declaration is not a call: a constructor with an initializer
      // list, a block body and an arrow body add no finding
      final k = _miniSources()
        ..['decl.dart'] = '''
class BoundedRun {
  BoundedRun({this.a}) : b = 1;
  final int? a;
  final int b;
}
class Runner {
  Future<void> runner(String x) async {}
  int tool(int x) => x;
}
''';
      expect(scanLaunchSites(k, _miniAllow), isEmpty);

      // (g) an unlisted Process.start caller
      final g = _miniSources()
        ..['spawn.dart'] = '''
Future<void> spawn() async {
  await Process.start('x', []);
}
''';
      final gFindings = scanLaunchSites(g, _miniAllow);
      expect(
        _mentions(gFindings, [
          'spawn.dart',
          'Process.start',
          'not on the allowlist',
        ]),
        isTrue,
        reason: gFindings.join('\n'),
      );

      // a Process.start in a function that is not the listed runner
      final h = _miniSources();
      h['helper.dart'] = h['helper.dart']!.replaceFirst(
        'startHelper',
        'somethingElse',
      );
      final hFindings = scanLaunchSites(h, _miniAllow);
      expect(
        _mentions(hFindings, [
          'helper.dart',
          'Process.start',
          'somethingElse',
          'not a listed runner',
        ]),
        isTrue,
        reason: hFindings.join('\n'),
      );

      // a call count that moved, with the listed file unchanged otherwise
      final i = _miniSources();
      i['run.dart'] =
          '${i['run.dart']!}\n'
          'Future<void> more(String bash) => runTool(bash, ".", ["ls"]);\n';
      final iFindings = scanLaunchSites(i, _miniAllow);
      expect(
        _mentions(iFindings, ['run.dart', 'runTool', 'count 2']),
        isTrue,
        reason: iFindings.join('\n'),
      );
    });

    test('a script name in launch arguments fails', () {
      // (b) the call count and the listed sites are unchanged
      for (final name in [
        'as.sh',
        'vcs.sh',
        'pr-pair.sh',
        'pr-snapshot.sh',
        'pr-reply.sh',
        'review-run.sh',
        'release.sh',
        'tool.py',
      ]) {
        final b = _miniSources();
        b['run.dart'] = b['run.dart']!.replaceFirst(
          "['git', 'status']",
          "['bash', '$name']",
        );
        final findings = scanLaunchSites(b, _miniAllow);
        expect(
          _mentions(findings, ['run.dart', 'runTool', 'launch argument', name]),
          isTrue,
          reason: '$name: ${findings.join('\n')}',
        );
      }
    });

    test('a changed, non-literal or unbounded self-launch fails', () {
      // (c) the evaluator's head is 'pr', 'snapshot'; every count is equal
      final c = _miniSources();
      c['snap.dart'] = c['snap.dart']!.replaceFirst(
        "'reviewers'",
        "'snapshot'",
      );
      final cFindings = scanLaunchSites(c, _miniAllow);
      expect(
        _mentions(cFindings, ['snap.dart', 'self-launch', 'head']),
        isTrue,
        reason: cFindings.join('\n'),
      );

      // (d) the evaluator runs through the unbounded PrContext.tool
      final d = _miniSources();
      d['snap.dart'] = d['snap.dart']!.replaceFirst('.bounded(', '.tool(');
      final dFindings = scanLaunchSites(d, _miniAllow);
      expect(
        _mentions(dFindings, ['snap.dart', 'self-launch', 'bound']),
        isTrue,
        reason: dFindings.join('\n'),
      );

      // (e) the self-launch list is not a literal
      final e = _miniSources();
      e['snap.dart'] = '''
Future<void> evaluate(ctx, List<String> argv) async {
  final exe = Platform.resolvedExecutable;
  final r = await ctx.bounded([exe, ...argv]);
}
''';
      final eFindings = scanLaunchSites(e, _miniAllow);
      expect(
        _mentions(eFindings, ['snap.dart', 'self-launch', 'literal']),
        isTrue,
        reason: eFindings.join('\n'),
      );

      // a self-launch in a file the allowlist does not name
      final f = _miniSources()
        ..['own.dart'] = '''
Future<void> again(ctx) async {
  await ctx.bounded([Platform.resolvedExecutable, 'vcs', 'plan']);
}
''';
      final fFindings = scanLaunchSites(f, _miniAllow);
      expect(
        _mentions(fFindings, ['own.dart', 'self-launch', 'not allowed']),
        isTrue,
        reason: fFindings.join('\n'),
      );
    });

    test('a script name built away from the launch fails', () {
      // (f) as.sh is assigned to a variable in an unlisted file and the
      // variable is passed to a listed runTool call
      final f = _miniSources()..['name.dart'] = "const script = 'as.sh';\n";
      f['run.dart'] = f['run.dart']!.replaceFirst(
        "['git', 'status']",
        '[script]',
      );
      final findings = scanLaunchSites(f, _miniAllow);
      expect(
        _mentions(findings, ['name.dart', 'as.sh', 'outside a listed site']),
        isTrue,
        reason: findings.join('\n'),
      );

      // a listed message file that grows a second mention
      final g = _miniSources();
      g['msg.dart'] = "${g['msg.dart']!}\nconst more = 'as.sh: again';\n";
      final gFindings = scanLaunchSites(g, _miniAllow);
      expect(
        _mentions(gFindings, ['msg.dart', 'as.sh', 'outside a listed site']),
        isTrue,
        reason: gFindings.join('\n'),
      );
    });

    test('comments and string contents are not launches', () {
      final s = _miniSources();
      s['run.dart'] = '''
/// Mentions runTool(a), Process.start(b) and as.sh in a doc comment.
// Platform.resolvedExecutable, vcs.sh
/* block runFramed(x) /* nested */ still a comment as.sh */
Future<void> go(String bash) async {
  final text = 'Process.start( and runFramed( and // not a comment';
  await runTool(bash, '.', ['git', 'status']);
}
''';
      expect(scanLaunchSites(s, _miniAllow), isEmpty);
    });
  });

  test('the tree matches the allowlist', () {
    final sources = _readTree();
    expect(sources, isNotEmpty);
    final findings = scanLaunchSites(sources, launchAllowlist);
    expect(findings, isEmpty, reason: findings.join('\n'));
  });
}

// ---------------------------------------------------------------------------
// The allowlist for the current tree. Files are keyed by their path below
// `lib/src`; sites by the runner symbol or the script name and a count, never
// by a line number, so ordinary edits do not break it.
// ---------------------------------------------------------------------------

const _tool = LaunchKind.externalTool;
const _helper = LaunchKind.processHelper;

const launchAllowlist = Allowlist(
  calls: {
    'cli.dart': {'runExecHelper': Call(1, _helper)},
    'commands/run.dart': {'BoundedRun': Call(1, _tool)},
    'commit/task_cover.dart': {'runTool': Call(1, _tool)},
    'fence/as_command.dart': {
      'runTool': Call(1, _tool),
      'runGh': Call(1, _tool),
      'runFenced': Call(1, _tool),
    },
    'fence/exec_inherit.dart': {
      // the fenced command starts directly with the caller's stdio, no shell
      'Process.start': Call(1, _tool, function: '_inherit'),
    },
    'fence/fenced_text.dart': {
      'runTool': Call(2, _tool),
      'runGh': Call(1, _tool),
    },
    'finish/undo_plan.dart': {'runTool': Call(1, _tool)},
    'pr/context.dart': {
      'runText': Call(1, _tool),
      'runGh': Call(1, _tool),
      'runBoundedCommand': Call(1, _tool),
    },
    'pr/gh.dart': {'BoundedRun': Call(1, _tool)},
    'pr/snapshot.dart': {
      'PrContext.bounded': Call(1, LaunchKind.reviewerEvaluator),
    },
    'pr/workflow.dart': {'runBoundedCommand': Call(1, _tool)},
    'pr/workflow_transport.dart': {
      'runTool': Call(1, _tool),
      'runBoundedCommand': Call(1, _tool),
      'WorkflowTransport.runner': Call(1, _tool),
    },
    'process/bounded_run.dart': {
      'Process.start': Call(1, _helper, function: 'run'),
    },
    'process/launch.dart': {
      // external tools start directly, without a shell; a batch file goes
      // through the bounded helper
      'Process.start': Call(1, _tool, function: '_native'),
      'BoundedRun': Call(1, _tool),
    },
    'process/exec_helper.dart': {
      'Process.start': Call(1, _helper, function: '_run'),
    },
    'process/windows_tree.dart': {
      'Process.start': Call(1, _tool, function: 'killTree'),
    },
    'vcs/git_common.dart': {'runText': Call(1, _tool)},
    'vcs/gitbutler_backend.dart': {
      'runTool': Call(1, _tool),
      'runToolCapped': Call(1, _tool),
    },
    'vcs/jj_backend.dart': {
      'runTool': Call(1, _tool),
      'runText': Call(1, _tool),
    },
    'vcs/probe.dart': {'runText': Call(7, _tool)},
    'vcs/scripts.dart': {
      'runTool': Call(1, _tool),
      'fencedText': Call(1, _tool),
    },
  },
  selfLaunches: {
    // the bounded process helper: `sw __exec -- <command>`
    'process/bounded_run.dart': SelfLaunch(
      1,
      ['__exec'],
      'helperCommand ??',
      _helper,
    ),
    // the reviewer evaluator, always under the poll deadline (ADR 0022)
    'pr/snapshot.dart': SelfLaunch(
      1,
      ['pr', 'reviewers'],
      '.bounded(',
      LaunchKind.reviewerEvaluator,
    ),
  },
  scriptNames: {
    'cli.dart': {'as.sh': ScriptSite(1, 'message: usage line of `sw as`')},
    'commands/finish.dart': {
      'finish.sh': ScriptSite(2, 'message: usage and argument text'),
    },
    'fence/as_command.dart': {
      'as.sh': ScriptSite(4, 'message: `as.sh:` refusal prefix'),
    },
    'fence/exec_inherit.dart': {
      'as.sh': ScriptSite(
        4,
        'message: `as.sh:` prefixes of the start refusals',
      ),
    },
    'fence/fence.dart': {
      'as.sh': ScriptSite(23, 'message: `as.sh:` refusal text'),
    },
    'finish/undo_plan.dart': {
      'vcs.sh': ScriptSite(3, 'printed command and message text'),
      'finish.sh': ScriptSite(1, 'message text'),
    },
    'pr/queries.dart': {
      'pr-reply.sh': ScriptSite(2, 'comment text inside a jq program'),
      'reviewers.py': ScriptSite(4, 'comment text inside a jq program'),
    },
    'pr/reply.dart': {
      'pr-reply.sh': ScriptSite(8, 'message and printed command text'),
    },
    'pr/reviewers.dart': {
      'reviewers.py': ScriptSite(1, 'label: the name in messages'),
    },
    'pr/snapshot.dart': {
      'pr-snapshot.sh': ScriptSite(1, 'message prefix'),
      'pr-pair.sh': ScriptSite(1, 'message text'),
      'reviewers.py': ScriptSite(1, 'label of the limit line'),
    },
    'pr/workflow.dart': {
      'pr-pair.sh': ScriptSite(1, 'printed command'),
      'as.sh': ScriptSite(1, 'printed command'),
    },
    'pr/workflow_transport.dart': {'as.sh': ScriptSite(1, 'message text')},
    'vcs/args.dart': {'vcs.sh': ScriptSite(1, 'message: usage line')},
    'vcs/gitbutler_backend.dart': {
      'as.sh': ScriptSite(1, 'message prefix compared, not launched'),
    },
    'vcs/plan.dart': {'vcs.sh': ScriptSite(1, 'printed command')},
    'vcs/scripts.dart': {'as.sh': ScriptSite(1, 'message text')},
  },
);

/// Every `.dart` file under the package's `lib/src`, keyed by its path below
/// `lib/src` with `/` separators. The package root is found from the working
/// directory (`cli/`, or the repository root), so the scan does not depend on
/// where `dart test` was started or on the OS.
Map<String, String> _readTree() {
  Directory? root;
  for (var dir = Directory.current.absolute; ; dir = dir.parent) {
    for (final candidate in [
      Directory(
        '${dir.path}${Platform.pathSeparator}lib${Platform.pathSeparator}src',
      ),
      Directory(
        '${dir.path}${Platform.pathSeparator}cli${Platform.pathSeparator}lib${Platform.pathSeparator}src',
      ),
    ]) {
      if (File('${candidate.path}${Platform.pathSeparator}cli.dart')
          .existsSync()) {
        root = candidate;
      }
    }
    if (root != null || dir.parent.path == dir.path) break;
  }
  if (root == null) fail('lib/src not found from ${Directory.current.path}');
  final base = root.path.replaceAll(r'\', '/');
  return {
    for (final entity in root.listSync(recursive: true))
      if (entity is File && entity.path.endsWith('.dart'))
        entity.path.replaceAll(r'\', '/').substring(base.length + 1): entity
            .readAsStringSync(),
  };
}
