import '../settings/rules.dart'
    show
        GitHubConnection,
        githubConnection,
        loadSettings,
        readSettingsText,
        RemoteSelection,
        selectedRemote,
        SettingsStop,
        settingSection;
import '../settings/values.dart' show pyStr;
import 'pattern.dart';
import 'stop.dart';

/// One `release.version_files` entry: the path or glob, its pattern as
/// written and the compiled pattern (JavaScript dialect, Unicode and multiline
/// mode; ADR 0037), which has exactly one capture group.
class VersionEntry {
  VersionEntry(this.path, this.pattern, this.regex);

  final String path;
  final String pattern;
  final RegExp regex;

  /// [regex] with the version's place marked, for `VersionFile` (see
  /// `locatingPattern`).
  late final RegExp located = RegExp(
    locatingPattern(pattern),
    multiLine: true,
    unicode: true,
  );
}

/// The release settings of `openspec/specwright.yaml`.
class ReleaseSettings {
  ReleaseSettings._(Map<String, Object?> doc) {
    final release = settingSection(doc, 'release', 'release');
    final pr = settingSection(doc, 'pr', 'pr');
    final github = settingSection(doc, 'github', 'github');
    final store = settingSection(doc, 'planning_store', 'planning_store');
    connection = githubConnection(doc);
    remote = selectedRemote(doc);
    storeRemote = selectedRemote(doc, store: true);
    final login = github['login'];
    githubLogin = login is String ? login.trim() : '';
    final storeMain = store['main_branch'];
    storeMainBranch = storeMain is String && storeMain.isNotEmpty
        ? storeMain
        : null;
    enabled = release['enabled'] == true;
    versionFiles = release['version_files'];
    final template = release['tag'];
    tag = template is String && template.isNotEmpty ? template : 'v{version}';
    githubRelease = release['github_release'] != false;
    auto = release['auto'] == true;
    final method = pr['merge_method'];
    mergeMethod = method == null || method == false || method == ''
        ? ''
        : pyStr(method).trim().toLowerCase();
    final finishMode = doc['finish'];
    finish = finishMode is String ? finishMode : null;
    final main = doc['main_branch'];
    mainBranch = main is String ? main : null;
  }

  /// `release.enabled`, true only when the file says `true`.
  late final bool enabled;

  /// The raw `release.version_files` value; [entries] checks it.
  late final Object? versionFiles;

  /// `release.tag`, `v{version}` unless set.
  late final String tag;

  /// `release.github_release`, true unless it says `false`.
  late final bool githubRelease;

  /// `release.auto`, true only when the file says `true`.
  late final bool auto;

  /// `pr.merge_method`, trimmed and lower case; empty when unset.
  late final String mergeMethod;

  /// The top-level `finish` mode, or null.
  late final String? finish;

  /// The top-level `main_branch`, or null.
  late final String? mainBranch;

  late final GitHubConnection connection;
  late final RemoteSelection remote;
  late final RemoteSelection storeRemote;
  late final String githubLogin;
  late final String? storeMainBranch;

  /// Stops before any write unless releases are enabled and the tag template
  /// names `{version}`; with [rebase] (bump and publish) also when pull
  /// requests merge by rebase, which leaves no single release commit.
  void gate({bool rebase = false}) {
    if (!enabled) {
      throw ReleaseStop(
        'release_disabled',
        'releases are off: set release.enabled: true in openspec/specwright.yaml',
      );
    }
    if (!tag.contains('{version}')) {
      throw ReleaseStop(
        'bad_tag_template',
        "release.tag '$tag' has no {version} placeholder: every version would map "
            'to one tag, and later versions would read as published; use a '
            'template such as v{version}',
      );
    }
    if (rebase && mergeMethod == 'rebase') {
      throw ReleaseStop(
        'rebase_merge',
        'release.enabled cannot be used with pr.merge_method: rebase: a rebase '
            'merge leaves no single release commit; change pr.merge_method or '
            'set release.enabled to false',
      );
    }
  }

  /// The checked `release.version_files` entries, in file order; the first is
  /// the primary file. Stops with `no_version_files` or `bad_version_files`
  /// naming the entry.
  List<VersionEntry> entries() {
    final files = versionFiles;
    if (files is! Map || files.isEmpty) {
      throw ReleaseStop(
        'no_version_files',
        'release.version_files must map each path or glob to a regular expression',
      );
    }
    final out = <VersionEntry>[];
    files.forEach((key, value) {
      final path = '$key';
      final parts = path.replaceAll(r'\', '/').split('/');
      if (parts.first.isEmpty ||
          RegExp(r'^[A-Za-z]:').hasMatch(path) ||
          parts.contains('..')) {
        throw ReleaseStop(
          'bad_version_files',
          "release.version_files entry '$path' must be a relative path inside "
              "the repository (not absolute, no '..')",
        );
      }
      if (value is! String || value.isEmpty) {
        throw ReleaseStop(
          'bad_version_files',
          "release.version_files entry '$path' needs a regular expression",
        );
      }
      final RegExp regex;
      try {
        regex = RegExp(value, multiLine: true, unicode: true);
      } on FormatException catch (e) {
        throw ReleaseStop(
          'bad_version_files',
          "release.version_files entry '$path': invalid pattern '$value': "
              '${e.message} (patterns are JavaScript regular expressions in '
              'Unicode mode)',
        );
      }
      // An empty alternative always matches, so the match reports every group.
      final groups = RegExp(
        '(?:$value)|',
        multiLine: true,
        unicode: true,
      ).firstMatch('')!.groupCount;
      if (groups != 1) {
        throw ReleaseStop(
          'bad_version_files',
          "release.version_files entry '$path': pattern '$value' must have "
              'exactly one capture group (has $groups)',
        );
      }
      out.add(VersionEntry(path, value, regex));
    });
    return out;
  }
}

/// Reads the release settings of the repository at [root]. A refused file, or a `release` or `pr` that is not a
/// mapping, stops with `bad_settings` naming the line or the key, before any git or write (D4). A missing file reads as
/// empty.
ReleaseSettings readReleaseSettings(String root) {
  final text = readSettingsText([root]);
  try {
    return ReleaseSettings._(loadSettings(text));
  } on SettingsStop catch (e) {
    if (e.error == 'bad_setting' &&
        (e.message.startsWith('github.') ||
            e.message.startsWith('remote:') ||
            e.message.startsWith('planning_store.'))) {
      throw ReleaseStop(e.error, e.message, code: e.code);
    }
    throw ReleaseStop('bad_settings', e.message);
  }
}
