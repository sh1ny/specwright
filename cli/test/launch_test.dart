// Verifies assumptions A2 (what `Process.start` does with a NUL or a lone
// surrogate in an argument) and A4 (Windows argument quoting round-trips for
// a native executable) of the native-cli-launcher design.
@Tags(['process'])
library;

import 'dart:convert';
import 'dart:io';

import 'package:test/test.dart';

const _recorder =
    'import sys, json; sys.stdout.buffer.write('
    "json.dumps(sys.argv[1:]).encode('ascii'))";

String get _python => Platform.isWindows ? 'python' : 'python3';

/// Starts the native recorder with [args] and returns what it recorded.
Future<List<String>> _record(List<String> args) async {
  final process = await Process.start(_python, ['-c', _recorder, ...args]);
  final out = process.stdout.transform(utf8.decoder).join();
  final err = process.stderr.transform(utf8.decoder).join();
  final code = await process.exitCode;
  expect(code, 0, reason: await err);
  return (jsonDecode(await out) as List<dynamic>).cast<String>();
}

void main() {
  group('A2: unrepresentable arguments', () {
    for (final entry in {
      'a NUL': 'a\u0000b',
      'a lone surrogate': 'a\uD800b',
    }.entries) {
      test('Process.start with ${entry.key} either throws or starts', () async {
        final String outcome;
        try {
          final recorded = await _record([entry.value]);
          // Recorded, not guessed: the child got one argument.
          expect(recorded, hasLength(1));
          outcome = 'child received ${jsonEncode(recorded.single)}';
        } on ProcessException {
          // D5 refuses such input before the start whatever Dart does.
          // ignore: avoid_print
          print(
            'A2 ${entry.key} on ${Platform.operatingSystem}: '
            'threw ProcessException',
          );
          return;
        } on ArgumentError catch (e) {
          // ignore: avoid_print
          print(
            'A2 ${entry.key} on ${Platform.operatingSystem}: '
            'threw ArgumentError: $e',
          );
          return;
        }
        // ignore: avoid_print
        print('A2 ${entry.key} on ${Platform.operatingSystem}: $outcome');
      });
    }
  });

  group('A4: Windows quoting round-trips', () {
    final values = <String, String>{
      'empty': '',
      'quotes': 'say "hi" and \'bye\'',
      'trailing backslashes': r'C:\dir with space\',
      'doubled trailing backslashes': r'path\',
      'backslashes before a quote': r'a\\"b',
      'spaces': 'two  spaces and a tab\there',
      '20,000 characters': List.filled(20000, 'x').join(),
    };

    for (final entry in values.entries) {
      test('${entry.key} reaches a native executable unchanged', () async {
        expect(await _record([entry.value]), [entry.value]);
      }, testOn: 'windows');
    }

    test('all values together reach a native executable unchanged', () async {
      final all = values.values.toList();
      expect(await _record(all), all);
    }, testOn: 'windows');
  });
}
