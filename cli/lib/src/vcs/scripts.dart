import '../pr/context.dart';
import '../pr/pair.dart';
import '../pr/settings_commands.dart';
import '../settings/rules.dart';
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
  VcsScripts(this.dir, this.bash, {this.fenceProject});

  // Only the temporary non-Git branch-check fetch carries a binary selector.
  final String? fenceProject;
  List<String> get fencePrefix =>
      fenceProject == null ? [] : ['--project', fenceProject!];

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

/// `vcs.sh`'s `get_settings`, read in process (design D6): the backend the
/// settings choose for [role] and the main branch and login of that role's
/// repo, by the rules `sw pr vcs` and `sw pr context --only repos` use. No
/// `pr-pair.sh` process starts, no reviewer config is written and no identity
/// is looked up. A refusal keeps its error code and its exit status, capped
/// at 3.
Future<VcsSettings> readSettings(
  VcsScripts scripts, {
  required String code,
  required String repo,
  required String role,
}) async {
  try {
    final read = await readVcsSettings(
      _settingsContext(scripts),
      code: code,
      repo: repo,
      role: role,
    );
    return VcsSettings(read.backend, read.main, read.login);
  } on SettingsStop catch (e) {
    throw VcsStop(e.error, e.message, code: _cap(e.code));
  }
}

/// `context --only repos --branch <branch>` as the GitButler push runs it: the
/// work-tree settings must be those of the change branch. The stop keeps its
/// error code, its `file` and `ref`, and its exit status capped at 3.
Future<void> requirePinnedSettings(
  VcsScripts scripts,
  String code,
  String branch,
) async {
  try {
    await requireSettingsPinnedTo(_settingsContext(scripts), code, branch);
  } on SettingsStop catch (e) {
    throw VcsStop(e.error, e.message, code: _cap(e.code));
  } on PairStop catch (e) {
    throw VcsStop(
      e.error,
      e.message,
      code: _cap(e.code),
      extra: {
        for (final f in e.extra.entries)
          if (f.key == 'file' || f.key == 'ref') f.key: f.value,
      },
    );
  }
}

/// A `PrContext` for the in-process settings module: only its `git` runs.
PrContext _settingsContext(VcsScripts scripts) => PrContext(
  scriptsDir: scripts.dir,
  bash: scripts.bash,
  writeOut: (_) {},
  writeErr: (_) {},
);

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
    final resolved = await scripts.run(repo, 'as.sh', [
      ...scripts.fencePrefix,
      '--resolve',
    ]);
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
) => scripts.run(repo, 'as.sh', [...scripts.fencePrefix, who, ...command]);

int _cap(int code) => code < 3 ? code : 3;
