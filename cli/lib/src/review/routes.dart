import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:toml/toml.dart';

import 'omp_policy.dart';
import 'stop.dart';

/// Codex features always disabled for a review, even when a user adds more.
///
/// Codex 0.166 exposes `collaboration.*` agent tools without a known switch;
/// they remain under the fixed read-only sandbox (C3).
const List<String> codexDefaultDisable = [
  'apps',
  'browser_use',
  'browser_use_external',
  'computer_use',
  'in_app_browser',
  'image_generation',
  'memories',
  'hooks',
  'plugins',
  'remote_plugin',
  'tool_suggest',
  'skill_search',
  'skill_mcp_dependency_install',
  'goals',
  'sleep_tool',
];

/// Minimum OMP version whose review overlay was verified to disable memory
/// and auto-learning; older versions must not be used for a review (C10).
const String ompMinVersion = '18.19.0';

const List<String> _routeNames = ['codex', 'claude', 'omp'];
const List<String> _claudeDefaultTools = ['Read', 'Grep', 'Glob'];
const List<String> _ompDefaultTools = ['read', 'grep', 'glob'];
const Map<String, List<String>> _routeKeys = {
  'codex': ['disable', 'args'],
  'claude': ['tools', 'args'],
  'omp': ['tools', 'args'],
};

const Set<String> _claudeUnsafeTools = {
  'bash',
  'powershell',
  'edit',
  'multiedit',
  'write',
  'notebookedit',
  'webfetch',
  'websearch',
  'task',
  'agent',
};

const Map<String, Set<String>> _unsafeFlags = {
  'claude': {
    '-p',
    '--print',
    '--tools',
    '--allowedTools',
    '--allowed-tools',
    '--disallowedTools',
    '--disallowed-tools',
    '--permission-mode',
    '--dangerously-skip-permissions',
    '--add-dir',
    '--settings',
    '--setting-sources',
    '--mcp-config',
    '--plugin-dir',
    '--agents',
    '--restricted',
    '--safe-mode',
    '--disable-slash-commands',
    '--output-format',
    '--json-schema',
    '--model',
    '--effort',
    '-c',
    '--continue',
    '-r',
    '--resume',
    '--fork-session',
  },
  'omp': {
    '-p',
    '--print',
    '--tools',
    '--no-tools',
    '--no-skills',
    '--no-extensions',
    '--no-rules',
    '--session-dir',
    '--no-session',
    '-c',
    '--continue',
    '-r',
    '--resume',
    '--restore',
    '-e',
    '--extension',
    '--trusted-extension',
    '--hook',
    '--skills',
    '--config',
    '--profile',
    '--mode',
    '--model',
    '--thinking',
    '--goal',
    '--plan-yolo',
    '--prewalk',
    '--prewalk-into',
  },
  'codex': {
    '-s',
    '--sandbox',
    '--dangerously-bypass-approvals-and-sandbox',
    '--yolo',
    '--dangerously-bypass-hook-trust',
    '--approve-for-me',
    '--not-so-yolo',
    '--full-auto',
    '--enable',
    '-p',
    '--profile',
    '--add-dir',
    '-C',
    '--cd',
    '--worktree',
    '--ephemeral',
    '--ignore-rules',
    '--ignore-user-config',
    '--output-schema',
    '-o',
    '--output-last-message',
    '--json',
    '-m',
    '--model',
  },
};

const Map<String, String> _settingAlternatives = {
  '--tools': 'review.routes.<route>.tools',
  '--model': 'review.models.<route>',
  '-m': 'review.models.<route>',
  '--effort': 'review.thinking.<route>',
  '--thinking': 'review.thinking.<route>',
};

/// The immutable, checked settings for one reviewer route.
class RouteConfig {
  RouteConfig({
    List<String>? tools,
    List<String> disabled = const [],
    List<String> args = const [],
  }) : tools = tools == null ? null : List.unmodifiable(tools),
       disabled = List.unmodifiable(disabled),
       args = List.unmodifiable(args);

  /// Replacement tool list, or null for Codex which does not accept one.
  final List<String>? tools;

  /// Effective Codex feature disables, including the fixed defaults.
  final List<String> disabled;

  /// Checked extra CLI arguments, kept after the fixed command controls.
  final List<String> args;
}

/// Parses `review.routes`, rejecting unknown keys, wrong types and unsafe
/// settings before callers probe or start a reviewer.
Map<String, RouteConfig> parseReviewRoutes(Object? raw) {
  if (raw != null && raw is! Map) {
    _badRouteSetting(
      'review.routes',
      'must be a map keyed by ${_routeNames.join(', ')}',
    );
  }

  final settings = <String, Map<String, Object?>>{};
  if (raw is Map) {
    for (final entry in raw.entries) {
      final routeKey = entry.key;
      if (routeKey is! String || !_routeNames.contains(routeKey)) {
        final key = routeKey is String
            ? 'review.routes.$routeKey'
            : 'review.routes.${routeKey ?? '<null>'}';
        _badRouteSetting(
          key,
          'is not a supported route; accepted routes: ${_routeNames.join(', ')}',
        );
      }
      final route = routeKey as String;
      final accepted = _routeKeys[route]!;
      final value = entry.value;
      if (value is! Map) {
        _badRouteSetting(
          'review.routes.$route',
          'must be a map with accepted keys: ${accepted.join(', ')}',
        );
      }

      final fields = <String, Object?>{};
      for (final fieldEntry in (value as Map).entries) {
        final fieldKey = fieldEntry.key;
        final key = fieldKey is String
            ? 'review.routes.$route.$fieldKey'
            : 'review.routes.$route.${fieldKey ?? '<null>'}';
        if (fieldKey is! String || !accepted.contains(fieldKey)) {
          _badRouteSetting(
            key,
            'is not accepted; accepted keys: ${accepted.join(', ')}',
          );
        }
        fields[fieldKey] = fieldEntry.value;
      }
      settings[route] = fields;
    }
  }

  final result = <String, RouteConfig>{};
  for (final route in _routeNames) {
    final fields = settings[route] ?? const <String, Object?>{};
    final args = fields.containsKey('args')
        ? _stringList(fields['args'], 'review.routes.$route.args')
        : const <String>[];
    final tools = route == 'codex'
        ? null
        : fields.containsKey('tools')
        ? _stringList(fields['tools'], 'review.routes.$route.tools')
        : route == 'claude'
        ? _claudeDefaultTools
        : _ompDefaultTools;
    final disabled = route == 'codex'
        ? _effectiveDisables(
            fields.containsKey('disable')
                ? _stringList(fields['disable'], 'review.routes.codex.disable')
                : const <String>[],
          )
        : const <String>[];

    if (tools != null) _validateTools(route, tools);
    _validateArgs(route, args);
    result[route] = RouteConfig(tools: tools, disabled: disabled, args: args);
  }
  return Map.unmodifiable(result);
}

List<String> _stringList(Object? raw, String key) {
  if (raw is! List) {
    _badRouteSetting(key, 'must be a list of names or arguments');
  }
  final values = <String>[];
  for (final value in raw as List) {
    if (value is! String) {
      _badRouteSetting(key, 'must be a list of strings');
    }
    if ((value as String).contains('\u0000')) {
      _badRouteSetting(key, 'must not contain NUL characters');
    }
    values.add(value);
  }
  return List.unmodifiable(values);
}

List<String> _effectiveDisables(List<String> extra) {
  final result = <String>[...codexDefaultDisable];
  final seen = result.toSet();
  for (final feature in extra) {
    if (seen.add(feature)) result.add(feature);
  }
  return List.unmodifiable(result);
}

final RegExp _safeName = RegExp(r'^[A-Za-z0-9_][A-Za-z0-9_.-]*$');

void _validateTools(String route, List<String> tools) {
  for (final tool in tools) {
    final lower = tool.toLowerCase();
    final refused = route == 'claude'
        ? _claudeUnsafeTools.contains(lower) || lower.startsWith('mcp__')
        : OmpLocalPolicy.isUnsafeTool(tool);
    if (refused || !_safeName.hasMatch(tool)) {
      _unsafeRouteSetting(
        route,
        'tools',
        tool,
        alternative: 'use only individual safe tool names',
      );
    }
  }
}

void _validateArgs(String route, List<String> args) {
  for (var index = 0; index < args.length; index++) {
    final arg = args[index];
    if (route == 'codex' && _isCodexConfigOption(arg)) {
      String assignment;
      if (arg == '-c' || arg == '--config') {
        if (index + 1 >= args.length) {
          _unsafeRouteSetting(
            route,
            'args',
            arg,
            alternative: 'use -c only with an unprotected key=value setting',
          );
        }
        assignment = args[++index];
      } else if (arg.startsWith('--config=')) {
        assignment = arg.substring('--config='.length);
      } else {
        assignment = arg.substring(2);
      }
      if (_protectedCodexKey(assignment)) {
        _unsafeRouteSetting(
          route,
          'args',
          assignment,
          alternative:
              'use review.routes.codex.disable for additive feature disabling',
        );
      }
      continue;
    }

    final refused = _refusedFlag(route, arg);
    if (refused != null) {
      final alternative = _settingAlternatives[refused];
      _unsafeRouteSetting(
        route,
        'args',
        arg,
        alternative: alternative == null ? null : 'use $alternative instead',
      );
    }
  }
}

bool _isCodexConfigOption(String arg) =>
    arg == '--config' ||
    arg.startsWith('--config=') ||
    arg == '-c' ||
    (arg.startsWith('-c') && !arg.startsWith('--'));

bool _protectedCodexKey(String assignment) {
  final equals = assignment.indexOf('=');
  if (equals <= 0) return true;
  final key = assignment
      .substring(0, equals)
      .replaceAll(RegExp(r'''["']'''), '')
      .replaceAll(RegExp(r'\s*\.\s*'), '.')
      .replaceAll(RegExp(r'\s+'), '')
      .toLowerCase();
  if (key.isEmpty) return true;

  if (key.startsWith('permissions') || key.startsWith('hooks')) return true;
  const protected = [
    'sandbox_mode',
    'sandbox_workspace_write',
    'approval_policy',
    'features',
    'tools',
    'web_search',
    'mcp_servers',
    'model',
    'model_reasoning_effort',
    'windows.sandbox',
  ];
  for (final path in protected) {
    if (key == path || key.startsWith('$path.')) return true;
    if (path.startsWith('$key.')) return true;
  }
  return false;
}

String? _refusedFlag(String route, String arg) {
  for (final flag in _unsafeFlags[route]!) {
    if (arg == flag || arg.startsWith('$flag=')) return flag;
    if (flag.length == 2 && flag.startsWith('-') && !flag.startsWith('--')) {
      if (arg.startsWith(flag)) return flag;
    }
  }
  return null;
}

Never _badRouteSetting(String key, String message) =>
    throw ReviewStop('bad_route_setting', '$key $message');

Never _unsafeRouteSetting(
  String route,
  String field,
  String value, {
  String? alternative,
}) => throw ReviewStop(
  'route_setting_unsafe',
  'review.routes.$route.$field contains unsafe value ${jsonEncode(value)}'
      '${alternative == null ? '' : '; $alternative'}',
);

/// Whether an OMP version string meets the version whose overlay was verified.
bool ompVersionSupported(String version) {
  final match = RegExp(
    r'^(?:omp/)?v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$',
    caseSensitive: false,
  ).firstMatch(version.trim());
  if (match == null) return false;

  final major = int.tryParse(match.group(1)!);
  final minor = int.tryParse(match.group(2)!);
  final patch = int.tryParse(match.group(3)!);
  if (major == null || minor == null || patch == null) return false;
  if (major != 18) return major > 18;
  if (minor != 19) return minor > 19;
  if (patch != 0) return patch > 0;
  return match.group(4) == null;
}

/// Reads only a plain-name `windows.sandbox` value from Codex's TOML config.
/// The file is consulted only on Windows; read and parse failures are ignored.
String? readWindowsSandbox({bool? windows, Map<String, String>? environment}) {
  if (!(windows ?? Platform.isWindows)) return null;

  final env = environment ?? Platform.environment;
  var home = env['CODEX_HOME'];
  if (home == null || home.isEmpty) {
    home = env['USERPROFILE'];
    if (home == null || home.isEmpty) home = env['HOME'];
    if ((home == null || home.isEmpty) &&
        (env['HOMEDRIVE']?.isNotEmpty ?? false) &&
        (env['HOMEPATH']?.isNotEmpty ?? false)) {
      home = '${env['HOMEDRIVE']}${env['HOMEPATH']}';
    }
    if (home != null && home.isNotEmpty) home = p.join(home, '.codex');
  }
  if (home == null || home.isEmpty) return null;

  try {
    final text = File(p.join(home, 'config.toml')).readAsStringSync();
    final data = TomlDocument.parse(text).toMap();
    final windowsTable = data['windows'];
    if (windowsTable is! Map) return null;
    final sandbox = windowsTable['sandbox'];
    if (sandbox is! String || !RegExp(r'^[a-z][a-z0-9-]*$').hasMatch(sandbox)) {
      return null;
    }
    return sandbox;
  } on Object {
    return null;
  }
}

/// An immutable reviewer command and the effective route controls it uses.
class ReviewCommand {
  ReviewCommand._({
    required List<String> argv,
    required this.stdinPath,
    required Map<String, bool> overlay,
    required this.policyPath,
    required this.policyId,
    required this.policySha256,
    required this.sessionDir,
  }) : argv = List.unmodifiable(argv),
       overlay = Map.unmodifiable(overlay);

  /// Full child argv, with the prompt sentinel or `@prompt` as the last value.
  final List<String> argv;

  /// Prompt file forwarded through stdin, or null for OMP's `@prompt` form.
  final String? stdinPath;

  /// Flattened effective OMP overlay values, empty on other routes.
  final Map<String, bool> overlay;

  /// Private fixed OMP policy path and identity; null on other routes.
  final String? policyPath;
  final String? policyId;
  final String? policySha256;

  /// Fresh private OMP session directory; null on other routes.
  final String? sessionDir;
}

/// Builds one fixed reviewer command plus its checked settings without starting
/// a child process. OMP artifacts are written only under [workDir].
ReviewCommand buildReviewCommand({
  required String route,
  required String executable,
  required RouteConfig config,
  required String kind,
  required Directory workDir,
  required String promptPath,
  String? model,
  String? thinking,
  String? schemaPath,
  String? windowsSandbox,
  List<String> allowedDirs = const [],
}) {
  if (!_routeNames.contains(route)) {
    throw ArgumentError.value(route, 'route', 'must be codex, claude, or omp');
  }

  final copied = <String>[];
  switch (route) {
    case 'codex':
      copied.addAll([
        executable,
        'exec',
        '-s',
        'read-only',
        '--ephemeral',
        '--ignore-rules',
        '--ignore-user-config',
        '--skip-git-repo-check',
      ]);
      for (final feature in config.disabled) {
        copied.addAll(['--disable', feature]);
      }
      copied.addAll(['-c', 'web_search="disabled"']);
      if (kind == 'preship' && schemaPath != null) {
        copied.addAll(['--output-schema', schemaPath]);
      }
      copied.add('--json');
      if (model != null && model.isNotEmpty) copied.addAll(['-m', model]);
      if (thinking != null && thinking.isNotEmpty) {
        copied.addAll(['-c', 'model_reasoning_effort="$thinking"']);
      }
      if (windowsSandbox != null &&
          RegExp(r'^[a-z][a-z0-9-]*$').hasMatch(windowsSandbox)) {
        copied.addAll(['-c', 'windows.sandbox="$windowsSandbox"']);
      }
      copied.addAll(config.args);
      copied.add('-');
      return ReviewCommand._(
        argv: copied,
        stdinPath: promptPath,
        overlay: const {},
        policyPath: null,
        policyId: null,
        policySha256: null,
        sessionDir: null,
      );

    case 'claude':
      copied.addAll([
        executable,
        '-p',
        '--safe-mode',
        '--disable-slash-commands',
        '--tools',
        (config.tools ?? _claudeDefaultTools).join(','),
        '--restricted',
      ]);
      if (kind == 'preship' && schemaPath != null) {
        final decoded = jsonDecode(File(schemaPath).readAsStringSync());
        if (decoded is! Map) {
          throw const FormatException('Claude JSON schema must be an object');
        }
        final schema = Map<String, Object?>.from(decoded)..remove(r'$schema');
        copied.addAll(['--json-schema', jsonEncode(schema)]);
      }
      if (allowedDirs.isNotEmpty) {
        copied.addAll(['--add-dir', ...allowedDirs]);
      }
      copied.addAll(['--output-format', 'json']);
      if (model != null && model.isNotEmpty) {
        copied.addAll(['--model', model]);
      }
      if (thinking != null && thinking.isNotEmpty) {
        copied.addAll(['--effort', thinking]);
      }
      copied.addAll(config.args);
      return ReviewCommand._(
        argv: copied,
        stdinPath: promptPath,
        overlay: const {},
        policyPath: null,
        policyId: null,
        policySha256: null,
        sessionDir: null,
      );

    case 'omp':
      final workPath = workDir.absolute.path;
      final work = Directory(workPath)..createSync(recursive: true);
      final overlay = const <String, bool>{
        'autolearn.enabled': false,
        'memories.enabled': false,
        'find.enabled': false,
        'fetch.enabled': false,
      };
      final overlayFile = File(p.join(workPath, 'omp-overlay.yml'))
        ..writeAsStringSync(
          'autolearn:\n'
          '  enabled: false\n'
          'memories:\n'
          '  enabled: false\n'
          'find:\n'
          '  enabled: false\n'
          'fetch:\n'
          '  enabled: false\n',
        );
      final session = work.createTempSync('omp-session-').absolute.path;
      final policyFile = OmpLocalPolicy.writeTo(work);
      copied.addAll([
        executable,
        '-p',
        '--no-skills',
        '--no-extensions',
        '--no-rules',
      ]);
      final tools = config.tools ?? _ompDefaultTools;
      if (tools.isEmpty) {
        copied.add('--no-tools');
      } else {
        copied.addAll(['--tools', tools.join(',')]);
      }
      copied.addAll([
        '--session-dir',
        session,
        '--mode',
        'json',
        '--config',
        overlayFile.absolute.path,
        '--trusted-extension',
        policyFile.absolute.path,
      ]);
      if (model != null && model.isNotEmpty) {
        copied.addAll(['--model', model]);
      }
      if (thinking != null &&
          thinking.isNotEmpty &&
          model != null &&
          !model.startsWith('@')) {
        copied.addAll(['--thinking', thinking]);
      }
      copied.addAll(config.args);
      copied.add('@$promptPath');
      return ReviewCommand._(
        argv: copied,
        stdinPath: null,
        overlay: overlay,
        policyPath: policyFile.absolute.path,
        policyId: OmpLocalPolicy.id,
        policySha256: OmpLocalPolicy.sha256,
        sessionDir: session,
      );
  }

  throw StateError('unreachable route: $route');
}
