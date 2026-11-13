import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:specwright_cli/src/review/records.dart';
import 'package:specwright_cli/src/review/stop.dart';
import 'package:test/test.dart';

void main() {
  late Directory work;
  late Map<String, Object?> fixture;
  setUp(() {
    work = Directory.systemTemp.createTempSync('sw-review-records-');
    fixture = (jsonDecode(
      File('../evals/review-routes/fixtures/preport-record.json')
          .readAsStringSync(),
    ) as Map).cast<String, Object?>();
  });
  tearDown(() => work.deleteSync(recursive: true));

  test(
    'pre-port path hashes the exact common-dir bytes and keeps code-only heads',
    () {
      final record = (fixture['record'] as Map).cast<String, Object?>();
      final actual = recordPath(
        stateDir: work.path,
        commonDir: fixture['common_dir'] as String,
        change: record['change'] as String,
        heads: (record['heads'] as Map).cast<String, Object?>(),
      );
      expect(
        p.relative(actual, from: work.path).replaceAll('\\', '/'),
        fixture['relative_record_path'],
      );
    },
  );

  test(
    'native write preserves the Python record fields and stores no outcome',
    () {
      final record = (fixture['record'] as Map).cast<String, Object?>();
      final path = writeReviewRecord(
        stateDir: work.path,
        commonDir: fixture['common_dir'] as String,
        record: {...record, 'outcome': 'must not persist'},
      );
      expect(jsonDecode(File(path).readAsStringSync()), record);
      expect(
        p.relative(path, from: work.path).replaceAll('\\', '/'),
        fixture['relative_record_path'],
      );
    },
  );

  test('store-backed heads remain part of the record key', () {
    final record = (fixture['record'] as Map).cast<String, Object?>();
    final heads = {
      ...(record['heads'] as Map).cast<String, Object?>(),
      'store': 'abc123',
    };
    final path = recordPath(
      stateDir: work.path,
      commonDir: fixture['common_dir'] as String,
      change: 'preport-record',
      heads: heads,
    );
    expect(p.basename(path), '${heads['code']}+abc123.json');
  });

  for (final change in [
    '',
    '.',
    '..',
    '../outside',
    'nested/../../outside',
    '/outside',
    r'C:\outside',
    r'C:outside',
    r'\\server\outside',
    r'nested\..\outside',
  ]) {
    test('record paths reject unsafe change ${jsonEncode(change)}', () {
      final record = (fixture['record'] as Map).cast<String, Object?>();
      expect(
        () => recordPath(
          stateDir: work.path,
          commonDir: fixture['common_dir'] as String,
          change: change,
          heads: (record['heads'] as Map).cast<String, Object?>(),
        ),
        throwsA(
          isA<ReviewStop>().having((e) => e.error, 'error', 'bad_change'),
        ),
      );
    });
  }

  test('record write cannot escape its state directory', () {
    final record = (fixture['record'] as Map).cast<String, Object?>();
    final heads = (record['heads'] as Map).cast<String, Object?>();
    final sentinel = File(
      p.join(work.path, 'outside', '${heads['code']}.json'),
    );
    sentinel.parent.createSync();
    sentinel.writeAsStringSync('must not overwrite');
    final state = Directory(p.join(work.path, 'state'));
    expect(
      () => writeReviewRecord(
        stateDir: state.path,
        commonDir: fixture['common_dir'] as String,
        record: {...record, 'change': '../../../outside'},
      ),
      throwsA(isA<ReviewStop>().having((e) => e.error, 'error', 'bad_change')),
    );
    expect(sentinel.readAsStringSync(), 'must not overwrite');
    expect(state.existsSync(), isFalse);
  });
}
