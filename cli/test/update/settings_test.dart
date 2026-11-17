import 'dart:io';

import 'package:specwright_cli/src/update/settings.dart';
import 'package:specwright_cli/src/update/stop.dart';
import 'package:test/test.dart';

void main() {
  late Directory code;

  setUp(() {
    code = Directory.systemTemp.createTempSync('sw-update-settings-');
  });

  tearDown(() {
    code.deleteSync(recursive: true);
  });

  void write(String text) {
    File('${code.path}/openspec/specwright.yaml')
      ..createSync(recursive: true)
      ..writeAsStringSync(text);
  }

  test('a missing file reads as no settings', () {
    final settings = loadUpdateSettings(code.path);
    expect(settings.mainBranch, isNull);
    expect(settings.planningStoreMainBranch, isNull);
    expect(settings.planningStoreVcs, isNull);
    expect(settings.vcs, isNull);
    expect(settings.storeIsJj, isFalse);
    expect(settings.configuredMain(isStore: true), isNull);
  });

  test('reads the four settings, quoted and commented', () {
    write(
      "main_branch: trunk # the code repo's\n"
      'vcs: "jj"\n'
      'planning_store:\n'
      "  main_branch: 'plans'\n"
      '  vcs: jj\n',
    );
    final settings = loadUpdateSettings(code.path);
    expect(settings.mainBranch, 'trunk');
    expect(settings.vcs, 'jj');
    expect(settings.planningStoreMainBranch, 'plans');
    expect(settings.planningStoreVcs, 'jj');
    expect(settings.storeIsJj, isTrue);
    expect(settings.configuredMain(isStore: true), 'plans');
    expect(settings.configuredMain(isStore: false), 'trunk');
  });

  test('a flow-map planning_store is read', () {
    write('planning_store: {vcs: jj, main_branch: plans}\n');
    final settings = loadUpdateSettings(code.path);
    expect(settings.storeIsJj, isTrue);
    expect(settings.planningStoreMainBranch, 'plans');
  });

  test('empty and non-scalar values read as unset', () {
    write('main_branch:\nvcs: [a]\nplanning_store: git\n');
    final settings = loadUpdateSettings(code.path);
    expect(settings.mainBranch, isNull);
    expect(settings.vcs, isNull);
    expect(settings.planningStoreVcs, isNull);
  });

  test('a file the reader refuses stops with settings_invalid', () {
    write('main_branch: main\nreview:\n  preship: yes\n');
    try {
      loadUpdateSettings(code.path);
      fail('expected a stop');
    } on UpdateStop catch (stop) {
      expect(stop.code, 'settings_invalid');
      expect(stop.message, contains('openspec/specwright.yaml line 3'));
      expect(stop.message, contains('write true or false'));
      expect(stop.message.toLowerCase(), contains('fix the file'));
      expect(stop.message.toLowerCase(), contains('rerun the update'));
    }
  });
}
