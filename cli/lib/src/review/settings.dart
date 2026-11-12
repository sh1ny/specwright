import 'dart:io';

import 'package:path/path.dart' as p;

import '../settings/rules.dart' show loadSettings, readSettingsText;
import '../settings/yaml.dart' show pyTruthy, pyUtf8Decode, yamlProblem;
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
  if (text != null) {
    final problem = yamlProblem(text);
    if (problem != null) throw ReviewStop('bad_settings', problem);
  }
  final values = loadSettings(text);
  final review = _reviewSection(values['review']);
  return ReviewSettings(values, review, parseReviewRoutes(review['routes']));
}

// Preserve the shared reader's `s.get(k) or {}` section/error semantics.
Map<String, Object?> _reviewSection(Object? value) {
  if (!pyTruthy(value)) return const {};
  if (value is Map<String, Object?>) return value;
  if (value is Map) return value.cast<String, Object?>();
  final type = switch (value) {
    String() => 'str',
    bool() => 'bool',
    int() || BigInt() => 'int',
    double() => 'float',
    List() => 'list',
    _ => value.runtimeType.toString(),
  };
  throw ReviewStop(
    'internal_error',
    "AttributeError: '$type' object has no attribute 'get'",
  );
}
