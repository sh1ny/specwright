import 'dart:convert';
import 'dart:io';

/// Returns the names of the packages listed in [packageConfigPath]
/// (`.dart_tool/package_config.json`) that declare build hooks: a top-level
/// `hooks:` key in their pubspec.yaml, or a `hook/build.dart` file.
List<String> packagesWithHooks(String packageConfigPath) {
  final configFile = File(packageConfigPath);
  final config =
      jsonDecode(configFile.readAsStringSync()) as Map<String, dynamic>;
  final found = <String>[];
  for (final entry in config['packages'] as List<dynamic>) {
    final package = entry as Map<String, dynamic>;
    final root = configFile.uri.resolve('${package['rootUri']}/');
    if (_declaresHooks(root)) found.add(package['name'] as String);
  }
  return found;
}

bool _declaresHooks(Uri root) {
  if (File.fromUri(root.resolve('hook/build.dart')).existsSync()) return true;
  final pubspec = File.fromUri(root.resolve('pubspec.yaml'));
  if (!pubspec.existsSync()) return false;
  // A top-level key starts in column 0; line scan avoids a YAML dependency.
  return pubspec.readAsLinesSync().any(
    (line) => RegExp(r'''^["']?hooks["']?\s*:''').hasMatch(line),
  );
}
