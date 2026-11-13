import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:specwright_cli/src/review/records.dart';
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
}
