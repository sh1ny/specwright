import 'dart:convert';

import 'codec.dart';
import 'stop.dart';
import 'tool_runner.dart';

/// What a tool run printed, decoded as `vcs.sh`'s `run` read it: UTF-8 with
/// surrogate escapes and universal newlines ([decodeText]).
class TextResult {
  TextResult(this.code, this.stdout, this.stderr);

  final int code;
  final String stdout;
  final String stderr;
}

/// Runs [command] (tool name first) in [cwd] through the transport and decodes
/// its output as text. This is `vcs.sh`'s `run` with `bash -c 'exec "$@"'`.
Future<TextResult> runText(
  String bash,
  String cwd,
  List<String> command,
) async {
  final r = await runTool(bash, cwd, command);
  return TextResult(r.exitCode, decodeText(r.stdout), decodeText(r.stderr));
}

/// The scripts `sw vcs` calls until they are ported (design D2, S2): the
/// directory of the `vcs.sh` that started it and the bash running that shim.
class VcsScripts {
  VcsScripts(this.dir, this.bash);

  final String dir;
  final String bash;

  String path(String name) {
    final base = dir.length > 1 && dir.endsWith('/')
        ? dir.substring(0, dir.length - 1)
        : dir;
    return '$base/$name';
  }

  /// `vcs.sh`'s `bash_script`: `bash <dir>/<name> args...` in [cwd], or in the
  /// directory `sw` was started in when [cwd] is null (`.` is that directory,
  /// and travels as bytes like any other record).
  Future<TextResult> run(String? cwd, String name, List<String> args) =>
      runText(bash, cwd ?? '.', [bash, path(name), ...args]);
}

/// The backend, main branch and login `vcs.sh`'s `get_settings` returns.
class VcsSettings {
  VcsSettings(this.backend, this.main, this.login);

  final String backend;
  final String main;
  final String login;
}

/// `vcs.sh`'s `get_settings`: `pr-pair.sh vcs --code <code>` for the backend,
/// then `pr-pair.sh context --code <code> --only repos` (`--store <repo>` for
/// the store role) for the main branch and login. Every failure maps to the
/// same stop: exit codes are capped at 3.
Future<VcsSettings> readSettings(
  VcsScripts scripts, {
  required String code,
  required String repo,
  required String role,
}) async {
  final result = await scripts.run(null, 'pr-pair.sh', ['vcs', '--code', code]);
  if (result.code != 0) {
    Object? data;
    try {
      data = jsonDecode(result.stdout);
    } on FormatException {
      final said = result.stderr.trim();
      data = {
        'error': 'settings_error',
        'message': said.isNotEmpty ? said : result.stdout.trim(),
      };
    }
    throw VcsStop(
      _text(_get(data, 'error') ?? 'settings_error'),
      _text(_get(data, 'message') ?? 'could not read VCS settings'),
      code: _cap(result.code),
    );
  }
  final Object? choices;
  try {
    choices = jsonDecode(result.stdout);
  } on FormatException {
    throw VcsStop('settings_error', 'pr-pair.sh vcs returned invalid JSON');
  }
  final backend = _get(choices, role == 'code' ? 'code' : 'store');
  if (backend is! String ||
      !const {'git', 'jj', 'gitbutler'}.contains(backend) ||
      (backend == 'gitbutler' && role != 'code')) {
    throw VcsStop(
      'settings_error',
      'pr-pair.sh vcs did not return a valid backend',
    );
  }
  // login and main only: merge settings are not validated
  final contextArgs = ['context', '--code', code, '--only', 'repos'];
  if (role == 'store') contextArgs.addAll(['--store', repo]);
  final context = await scripts.run(null, 'pr-pair.sh', contextArgs);
  final Object? ctx;
  try {
    ctx = jsonDecode(context.stdout);
  } on FormatException {
    throw VcsStop('settings_error', 'pr-pair.sh context returned invalid JSON');
  }
  if (context.code != 0) {
    throw VcsStop(
      _text(_get(ctx, 'error') ?? 'settings_error'),
      _text(_get(ctx, 'message') ?? 'could not read repository settings'),
      code: _cap(context.code),
    );
  }
  final item = _truthy(_get(ctx, role == 'store' ? 'store' : 'code'))
      ? _get(ctx, role == 'store' ? 'store' : 'code')
      : const <String, Object?>{};
  return VcsSettings(
    backend,
    _str(_get(item, 'main')),
    _str(_get(item, 'login')),
  );
}

/// The login a network command runs as (`fence_login`, `network_git`): [login]
/// when it is not empty; for a GitHub remote without one, the account
/// `as.sh --resolve` prints; otherwise empty. A refused resolve is the
/// `fence_failed` stop with exit 3.
Future<String> fenceLogin(
  VcsScripts scripts,
  String repo, {
  required bool github,
  String? login,
}) async {
  var who = login ?? '';
  if (github && who.isEmpty) {
    final resolved = await scripts.run(repo, 'as.sh', ['--resolve']);
    if (resolved.code != 0) {
      final said = resolved.stderr.trim();
      throw VcsStop(
        'fence_failed',
        said.isNotEmpty ? said : 'as.sh could not resolve GitHub login',
        code: 3,
      );
    }
    who = resolved.stdout.trim();
  }
  return who;
}

/// `as.sh <who> <command...>` in [repo]: a fenced network command. The caller
/// maps a non-zero exit (3 is a refused fence) as `network_git` does.
///
/// Constraint C7: this reaches the fence through the `as.sh` shim, which hands
/// the call to `sw as`, until `native-cli-retire-scripts` calls `sw as`
/// directly. The exit-3 and `as.sh:` prefix mapping of the callers depends on
/// that shim: the fence keeps `as.sh`'s messages and statuses, and a direct
/// call would have to keep them too.
Future<TextResult> runAs(
  VcsScripts scripts,
  String repo,
  String who,
  List<String> command,
) => scripts.run(repo, 'as.sh', [who, ...command]);

int _cap(int code) => code < 3 ? code : 3;

/// Python's `data.get(key)` on a decoded JSON value: anything but an object is
/// the `AttributeError` that becomes `internal_error`.
Object? _get(Object? data, String key) {
  if (data is Map) return data[key];
  final type = switch (data) {
    null => 'NoneType',
    List() => 'list',
    String() => 'str',
    int() => 'int',
    double() => 'float',
    bool() => 'bool',
    _ => data.runtimeType.toString(),
  };
  throw StateError("'$type' object has no attribute 'get'");
}

bool _truthy(Object? v) =>
    !(v == null ||
        v == false ||
        v == 0 ||
        v == '' ||
        (v is List && v.isEmpty) ||
        (v is Map && v.isEmpty));

/// `str(value or "")`.
String _str(Object? v) => _truthy(v) ? _text(v) : '';

String _text(Object? v) => v is String ? v : '$v';
