import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart' as crypto;
import 'package:path/path.dart' as p;

/// C1: the pre-ship record's key and JSON fields are the Python format, so
/// records already on disk remain readable by `gate`, `waive` and `rounds`.
String recordPath({
  required String stateDir,
  required String commonDir,
  required String change,
  required Map<String, Object?> heads,
}) {
  final repoKey = crypto.sha256.convert(utf8.encode(commonDir)).toString();
  final code = heads['code'] as String;
  final store = heads['store'];
  final name = '$code${_hasTime(store) ? '+$store' : ''}';
  return p.join(
    stateDir,
    'reviews',
    repoKey.substring(0, 16),
    change,
    '$name.json',
  );
}

/// Atomically writes one record with the historical field set and returns its
/// native filesystem path. Unknown fields, including any cached outcome, are
/// intentionally not persisted.
String writeReviewRecord({
  required String stateDir,
  required String commonDir,
  required Map<String, Object?> record,
}) {
  final rec = <String, Object?>{
    'kind': record['kind'],
    'change': record['change'],
    'heads': record['heads'],
    'base': record['base'],
    'route': record['route'],
    'receipt': record['receipt'],
    'findings': record['findings'],
    'waivers': record['waivers'] ?? <Object?>[],
    'at': _hasTime(record['at']) ? record['at'] : _now(),
  };
  final path = recordPath(
    stateDir: stateDir,
    commonDir: commonDir,
    change: rec['change'] as String,
    heads: (rec['heads'] as Map).cast<String, Object?>(),
  );
  final target = File(path);
  target.parent.createSync(recursive: true);
  final temp = File('$path.${_token()}.tmp');
  try {
    temp.createSync(exclusive: true);
    temp.writeAsStringSync(
      '${const JsonEncoder.withIndent('  ').convert(rec)}\n',
      encoding: utf8,
      flush: true,
    );
    temp.renameSync(path);
  } on Object {
    try {
      if (temp.existsSync()) temp.deleteSync();
    } on FileSystemException {
      // Preserve the original write/rename failure.
    }
    rethrow;
  }
  return path;
}

bool _hasTime(Object? value) => switch (value) {
  null => false,
  bool value => value,
  num value => value != 0,
  String value => value.isNotEmpty,
  List<dynamic> value => value.isNotEmpty,
  Map<dynamic, dynamic> value => value.isNotEmpty,
  _ => true,
};

String _now() => DateTime.now().toUtc().toIso8601String().replaceFirst(
  RegExp(r'\.\d{3}Z$'),
  'Z',
);

String _token() {
  final random = Random.secure();
  return List.generate(
    12,
    (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
}
