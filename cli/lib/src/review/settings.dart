import 'dart:io';

import 'package:path/path.dart' as p;

import '../settings/rules.dart'
    show SettingsStop, loadSettings, readSettingsText, settingSection;
import '../settings/values.dart' show pyUtf8Decode;
import 'routes.dart';
import 'stop.dart';

class ReviewSettings {
  const ReviewSettings(this.values, this.review, this.routes);

  final Map<String, Object?> values;
  final Map<String, Object?> review;
  final Map<String, RouteConfig> routes;
}

/// Reads cwd then toplevel settings; validates the whole routes block before a
/// caller may probe any reviewer. An explicit file replaces that search.
ReviewSettings readReviewSettings({
  required Iterable<String> bases,
  String? settingsPath,
}) {
  String? text;
  if (settingsPath == null) {
    text = readSettingsText(bases);
  } else {
    final path = p.isAbsolute(settingsPath)
        ? settingsPath
        : p.join(
            bases.isEmpty ? Directory.current.path : bases.first,
            settingsPath,
          );
    final file = File(path);
    if (!file.existsSync()) {
      throw ReviewStop(
        'usage',
        'settings file not found: $settingsPath',
        code: 2,
      );
    }
    text = pyUtf8Decode(file.readAsBytesSync())
        .replaceAll('\r\n', '\n')
        .replaceAll('\r', '\n');
  }
  return parseReviewSettings(text);
}

ReviewSettings parseReviewSettings(String? text) {
  // D4: this reader's stop is bad_settings, exit 1, whatever the reason
  try {
    final values = loadSettings(text);
    final review = settingSection(values, 'review', 'review');
    return ReviewSettings(values, review, parseReviewRoutes(review['routes']));
  } on SettingsStop catch (e) {
    throw ReviewStop('bad_settings', e.message);
  }
}
