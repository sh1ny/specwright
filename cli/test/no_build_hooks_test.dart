// Enforces constraint C3 (ADR 0027): no dependency declares build hooks.
import 'dart:convert';
import 'dart:io';

import 'package:test/test.dart';

import '../tool/hooks_scan.dart';

void main() {
  group('packagesWithHooks', () {
    late Directory tmp;
    setUp(() => tmp = Directory.systemTemp.createTempSync('sw-hooks-'));
    tearDown(() => tmp.deleteSync(recursive: true));

    String config(Map<String, String?> packages) {
      final entries = <Map<String, Object?>>[];
      packages.forEach((name, pubspec) {
        final root = Directory('${tmp.path}/$name')..createSync();
        if (pubspec != null) {
          File('${root.path}/pubspec.yaml').writeAsStringSync(pubspec);
        }
        entries.add({
          'name': name,
          'rootUri': root.uri.toString(),
          'packageUri': 'lib/',
        });
      });
      final file = File('${tmp.path}/package_config.json')
        ..writeAsStringSync(
          jsonEncode({'configVersion': 2, 'packages': entries}),
        );
      return file.path;
    }

    test('reports a package whose pubspec has a top-level hooks key', () {
      final path = config({
        'clean': 'name: clean\nenvironment:\n  sdk: ^3.0.0\n',
        'hooked': 'name: hooked\nhooks:\n  user_defines:\n    x: 1\n',
        'nested': 'name: nested\nflutter:\n  hooks: not-top-level\n',
      });
      expect(packagesWithHooks(path), ['hooked']);
    });

    test('reports a package that ships hook/build.dart', () {
      final path = config({'native': 'name: native\n'});
      Directory('${tmp.path}/native/hook').createSync();
      File('${tmp.path}/native/hook/build.dart').writeAsStringSync('');
      expect(packagesWithHooks(path), ['native']);
    });
  });

  test('no locked package declares build hooks', () {
    final config = File('.dart_tool/package_config.json');
    expect(config.existsSync(), isTrue, reason: 'run dart pub get first');
    expect(packagesWithHooks(config.path), isEmpty);
  });
}
