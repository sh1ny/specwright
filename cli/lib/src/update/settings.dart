import '../settings/reader.dart';
import '../settings/rules.dart' show readSettingsText;
import '../settings/values.dart' show settingText;
import 'stop.dart';

/// The four settings of `openspec/specwright.yaml` that `sw update` reads
/// (design D5 of native-cli-update): `main_branch`, `planning_store.main_branch`,
/// `planning_store.vcs` and `vcs`. Each is the text the user wrote, or null
/// when the key is missing, empty, or not a plain value.
class UpdateSettings {
  const UpdateSettings({
    this.mainBranch,
    this.planningStoreMainBranch,
    this.planningStoreVcs,
    this.vcs,
  });

  /// No settings: what a missing file reads as.
  static const UpdateSettings none = UpdateSettings();

  final String? mainBranch;
  final String? planningStoreMainBranch;
  final String? planningStoreVcs;
  final String? vcs;

  /// The main branch the settings name for a planning root that [isStore]
  /// (`planning_store.main_branch`) or lives in the code repo (`main_branch`).
  String? configuredMain({required bool isStore}) =>
      isStore ? planningStoreMainBranch : mainBranch;

  /// The store's backend is jj (`planning_store.vcs: jj`); git when unset.
  bool get storeIsJj => planningStoreVcs == 'jj';
}

/// Reads the four settings from `<code>/openspec/specwright.yaml` through the
/// shared fail-closed reader. A missing file reads as [UpdateSettings.none]. A
/// file the reader refuses stops with `settings_invalid`, naming the file, the
/// line and the problem and saying to fix the file and rerun the update.
UpdateSettings loadUpdateSettings(String code) {
  final text = readSettingsText([code]);
  if (text == null) return UpdateSettings.none;
  final Map<String, Object?> map;
  try {
    map = readSettingsYaml(text);
  } on SettingsRefused catch (refused) {
    throw UpdateStop(
      'settings_invalid',
      'openspec/specwright.yaml line ${refused.line}: ${refused.why}. Fix the '
          'file, then rerun the update; nothing was written',
    );
  }
  final store = map['planning_store'];
  return UpdateSettings(
    mainBranch: _text(map, 'main_branch'),
    planningStoreMainBranch: store is Map<String, Object?>
        ? _text(store, 'main_branch')
        : null,
    planningStoreVcs: store is Map<String, Object?>
        ? _text(store, 'vcs')
        : null,
    vcs: _text(map, 'vcs'),
  );
}

/// The scalar at [key] as text: text trimmed (empty is null), another scalar
/// as the user wrote it; a mapping, a list and a null are null.
String? _text(Map<String, Object?> map, String key) {
  final value = map[key];
  if (value == null || value is Map || value is List) return null;
  final text = value is String ? value.trim() : settingText(map, key).trim();
  return text.isEmpty ? null : text;
}
