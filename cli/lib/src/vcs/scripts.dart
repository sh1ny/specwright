import '../fence/fenced_text.dart';
import '../pr/context.dart';
import '../pr/pair.dart';
import '../pr/settings_commands.dart';
import '../settings/rules.dart';
import 'codec.dart';
import 'stop.dart';
import 'text_result.dart';
import 'tool_runner.dart';

export 'text_result.dart';

/// Runs [command] (tool name first) in [cwd] without a shell and decodes its output
/// as text. This is `vcs.sh`'s `run`.
Future<TextResult> runText(String cwd, List<String> command) async {
  final r = await runTool(cwd, command);
  return TextResult(r.exitCode, decodeText(r.stdout), decodeText(r.stderr));
}

/// The identity fence, run in process: `as.sh`'s argument list in, the
/// [fencedText] result out. A test replaces it ([VcsScripts.fence]).
typedef FencedRun = Future<TextResult> Function(String repo, List<String> argv);

/// Where `sw vcs` was started from (design D2, S2): the directory of the
/// `vcs.sh` that started it, which printed commands name, and the bash that ran
/// that shim. No script in it is run.
class VcsScripts {
  VcsScripts(this.dir, this.bash, {this.fence});

  final String dir;
  final String bash;

  /// Replaces the in-process fence in a test; null runs [fencedText].
  final FencedRun? fence;

  String path(String name) {
    final base = dir.length > 1 && dir.endsWith('/')
        ? dir.substring(0, dir.length - 1)
        : dir;
    return '$base/$name';
  }

  /// `as.sh <argv...>` in [repo], run in this process.
  Future<TextResult> fenced(String repo, List<String> argv) {
    final run = fence;
    return run != null ? run(repo, argv) : fencedText(repo, argv);
  }
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
/// when it is not empty; for a GitHub remote without one, the account the
/// fence's `--resolve` finds, in this process ([fencedText]); otherwise empty.
/// A refused resolve is the `fence_failed` stop with exit 3.
Future<String> fenceLogin(
  VcsScripts scripts,
  String repo, {
  required bool github,
  String? login,
}) async {
  var who = login ?? '';
  if (github && who.isEmpty) {
    final resolved = await scripts.fenced(repo, ['--resolve']);
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

/// `as.sh <who> <command...>` in [repo], run in this process ([fencedText]): a
/// fenced network command. The caller maps a non-zero exit (3 is a refused
/// fence) as `network_git` does.
///
/// Constraint C7: the fence keeps `as.sh`'s messages and statuses (the
/// `as.sh:` prefix and exit 3 of a refusal), which the exit-3 and prefix
/// mapping of the callers depends on.
Future<TextResult> runAs(
  VcsScripts scripts,
  String repo,
  String who,
  List<String> command,
) => scripts.fenced(repo, [who, ...command]);

int _cap(int code) => code < 3 ? code : 3;
