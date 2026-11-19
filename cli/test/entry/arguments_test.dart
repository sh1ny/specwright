import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/cli.dart';
import 'package:test/test.dart';

void main() {
  late Directory project;
  setUp(() {
    project = Directory.systemTemp.createTempSync('sw-arguments-');
    Directory('${project.path}/.git').createSync();
    Directory('${project.path}/openspec/.specwright')
        .createSync(recursive: true);
    // the version of a test build (no SW_VERSION defined)
    File('${project.path}/openspec/.specwright/VERSION')
        .writeAsStringSync('0.0.0-dev\n');
  });
  tearDown(() => project.deleteSync(recursive: true));

  Future<(int, Map<String, Object?>)> run(List<String> args) async {
    final out = <int>[];
    final code = await runCli(
      args,
      out: StringBuffer(),
      err: StringBuffer(),
      outBytes: out.addAll,
    );
    return (code, jsonDecode(utf8.decode(out)) as Map<String, Object?>);
  }

  test('a well-formed argument passes unchanged', () async {
    final name = '日本語-😀.md';
    final (code, doc) = await run([
      '--project',
      project.path,
      'release',
      'notes',
      '--proposal',
      '${project.path}/$name',
    ]);
    expect(doc['error'], isNot('bad_argument'));
    expect(doc['error'], isNot('sw_mismatch'));
    expect(doc['message'], contains(name));
    expect(code, isNot(0));
  });

  test('a lone surrogate is bad_argument naming its position, exit 2, '
      'before dispatch', () async {
    final (code, doc) = await run([
      '--project',
      project.path,
      'release',
      'notes',
      '--proposal',
      'm\udc80x.md',
    ]);
    expect(code, 2);
    expect(doc, {
      'ok': false,
      'error': 'bad_argument',
      'message': 'argument 6 is not well-formed Unicode',
    });
  });

  test('a valid U+FFFD is just a character', () async {
    final (_, doc) = await run([
      '--project',
      project.path,
      'release',
      'notes',
      '--proposal',
      '${project.path}/m\u{FFFD}x.md',
    ]);
    expect(doc['error'], isNot('bad_argument'));
    expect(doc['message'], contains('m\u{FFFD}x.md'));
  });
}
