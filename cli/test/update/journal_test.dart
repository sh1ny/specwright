import 'dart:io';

import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:specwright_cli/src/update/journal.dart';
import 'package:test/test.dart';

// A format 2 journal exactly as update.sh's `format_journal` lays it out: the
// scalar members one per line with ", " and ": " separators, then the groups,
// targets and manifest with one entry per line. The empty list leaves an empty
// line, as `",\n".join([])` does.
const _format2 = '''{
  "format": 2,
  "from": "0.5.0",
  "to": "0.6.0",
  "ref": "v0.6.0",
  "kind": "workflow",
  "role": "none",
  "code": "C:/p/code",
  "root": "C:/p/code",
  "inflight": {"checked": true, "changes": [{"name": "caf\u00e9", "source": "working tree", "status": "valid", "validated_against": "the new schema"}], "warnings": []},
  "owner_id": null,
  "store_owner": null,
  "store_version": null,
  "store_record": null,
  "store_lock": null,
  "store_staging": null,
  "store_state": "none",
  "token": null,
  "prev_config": null,
  "prev_store": null,
  "config_sha": null,
  "prev_packs": ["gamedev"],
  "phase": "staged",
  "groups": [
    {"id": "skills0", "kind": "skills", "dir": "C:/p/code/.claude/skills", "staging": "C:/p/code/.claude/.specwright-update-skills"},
    {"id": "record", "kind": "record", "dir": "C:/p/code/openspec/.specwright", "staging": "C:/p/code/openspec/.specwright-update-record"}
  ],
  "targets": [
    {"gid": "skills0", "name": "specwright-pr", "type": "dir", "dir": "C:/p/code/.claude/skills", "staging": "C:/p/code/.claude/.specwright-update-skills", "installed": true, "state": "pending"},
    {"gid": "skills0", "name": "gamedev-old", "type": "remove", "dir": "C:/p/code/.claude/skills", "staging": "C:/p/code/.claude/.specwright-update-skills", "installed": true, "state": "old-moved"},
    {"gid": "record", "name": "packs.json", "type": "file", "dir": "C:/p/code/openspec/.specwright", "staging": "C:/p/code/openspec/.specwright-update-record", "installed": false, "state": "swapped"}
  ],
  "manifest": [
    {"group": "skills0", "path": "specwright-pr/SKILL.md", "sha256": "00ff"},
    {"group": "record", "path": "packs.json", "sha256": "aa"}
  ]
}
''';

// Format 1: no prev_packs, no remove target, and an empty manifest.
const _format1 = '''{
  "format": 1,
  "from": null,
  "to": "0.4.0",
  "ref": null,
  "kind": "fresh",
  "role": "claim",
  "code": "/p/code",
  "root": "/s",
  "inflight": {"checked": false, "changes": [], "warnings": []},
  "owner_id": "github.com/o/r",
  "store_owner": null,
  "store_version": null,
  "store_record": "/s/openspec/.specwright/STORE",
  "store_lock": "/g/specwright-gate.lock",
  "store_staging": "/s/openspec/.specwright-update-schemas",
  "store_state": "pending",
  "token": null,
  "prev_config": null,
  "prev_store": null,
  "config_sha": null,
  "phase": "staging",
  "groups": [
    {"id": "schema", "kind": "schema", "dir": "/s/openspec/schemas", "staging": "/s/openspec/.specwright-update-schemas"}
  ],
  "targets": [
    {"gid": "schema", "name": "specwright", "type": "dir", "dir": "/s/openspec/schemas", "staging": "/s/openspec/.specwright-update-schemas", "installed": false, "state": "pending"}
  ],
  "manifest": [

  ]
}
''';

void main() {
  late Directory temp;

  setUp(() {
    temp = Directory.systemTemp.createTempSync('sw-journal-');
  });

  tearDown(() {
    temp.deleteSync(recursive: true);
  });

  group('Journal.parse', () {
    test('reads a format 2 journal', () {
      final journal = Journal.parse(_format2);
      expect(journal.format, 2);
      expect(journal.data['from'], '0.5.0');
      expect(journal.data['phase'], 'staged');
      expect(journal.data['prev_packs'], ['gamedev']);
      expect((journal.data['targets'] as List).length, 3);
      expect(((journal.data['targets'] as List)[1] as Map)['type'], 'remove');
      expect(
        ((journal.data['inflight'] as Map)['changes'] as List).single,
        containsPair('name', 'caf\u00e9'),
      );
    });

    test('reads a format 1 journal', () {
      final journal = Journal.parse(_format1);
      expect(journal.format, 1);
      expect(journal.data['role'], 'claim');
      expect(journal.data.containsKey('prev_packs'), isFalse);
      expect(journal.data['manifest'], isEmpty);
    });
  });

  group('byte-compatible text', () {
    test('a format 2 journal is written back byte for byte', () {
      expect(Journal.parse(_format2).toText(), _format2);
    });

    test('a format 1 journal is written back byte for byte', () {
      expect(Journal.parse(_format1).toText(), _format1);
    });

    test('a new format 2 journal gets the same keys, order and shapes', () {
      final journal = Journal({
        'format': 2,
        'from': null,
        'to': '0.6.0',
        'ref': 'main',
        'kind': 'fresh',
        'role': 'none',
        'code': '/c',
        'root': '/c',
        'inflight': {
          'checked': false,
          'changes': <Object?>[],
          'warnings': <Object?>[],
        },
        'owner_id': null,
        'store_owner': null,
        'store_version': null,
        'store_record': null,
        'store_lock': null,
        'store_staging': null,
        'store_state': 'none',
        'token': null,
        'prev_config': null,
        'prev_store': null,
        'config_sha': null,
        'prev_packs': <Object?>[],
        'phase': 'staging',
        'groups': <Object?>[],
        'targets': [
          {'gid': 'g', 'name': 'n', 'type': 'dir', 'installed': false},
        ],
        'manifest': <Object?>[],
      });
      expect(journal.toText(), '''{
  "format": 2,
  "from": null,
  "to": "0.6.0",
  "ref": "main",
  "kind": "fresh",
  "role": "none",
  "code": "/c",
  "root": "/c",
  "inflight": {"checked": false, "changes": [], "warnings": []},
  "owner_id": null,
  "store_owner": null,
  "store_version": null,
  "store_record": null,
  "store_lock": null,
  "store_staging": null,
  "store_state": "none",
  "token": null,
  "prev_config": null,
  "prev_store": null,
  "config_sha": null,
  "prev_packs": [],
  "phase": "staging",
  "groups": [

  ],
  "targets": [
    {"gid": "g", "name": "n", "type": "dir", "installed": false}
  ],
  "manifest": [

  ]
}
''');
    });

    test('strings are escaped as Python json.dumps does with '
        'ensure_ascii=False', () {
      final journal = Journal({
        'format': 2,
        'note': 'q"b\\n\n\r\t\b\f\u0001\u007f\u00e9\u2028\u{1F600}',
        'groups': <Object?>[],
        'targets': <Object?>[],
        'manifest': <Object?>[],
      });
      expect(
        journal.toText().split('\n')[2],
        r'  "note": "q\"b\\n\n\r\t\b\f\u0001'
        '\u007f\u00e9\u2028\u{1F600}",',
      );
    });
  });

  group('refusals are journal_unreadable', () {
    void expectUnreadable(String text, String message) {
      try {
        Journal.parse(text);
        fail('parsed: $text');
      } on JournalUnreadable catch (e) {
        expect(e.code, 'journal_unreadable');
        expect(e.message, message);
      }
    }

    test('format 9', () {
      expectUnreadable(
        '{"format": 9, "groups": []}\n',
        'update.json has format 9, not 1 or 2',
      );
    });

    test('a missing, null, boolean or text format', () {
      expectUnreadable('{}\n', 'update.json has format None, not 1 or 2');
      expectUnreadable(
        '{"format": null}\n',
        'update.json has format None, not 1 or 2',
      );
      expectUnreadable(
        '{"format": true}\n',
        'update.json has format True, not 1 or 2',
      );
      expectUnreadable(
        '{"format": "2"}\n',
        "update.json has format '2', not 1 or 2",
      );
    });

    test('a document that is not an object', () {
      expectUnreadable('[1, 2]\n', 'update.json has format None, not 1 or 2');
    });

    test('trailing garbage', () {
      final text = '$_format2{"format": 2}\n';
      try {
        Journal.parse(text);
        fail('parsed trailing garbage');
      } on JournalUnreadable catch (e) {
        expect(e.message, startsWith('update.json is not readable JSON ('));
      }
      try {
        Journal.parse('${_format2}garbage');
        fail('parsed trailing garbage');
      } on JournalUnreadable catch (e) {
        expect(e.message, startsWith('update.json is not readable JSON ('));
      }
    });

    test('an empty file and a truncated one', () {
      for (final text in ['', _format2.substring(0, _format2.length ~/ 2)]) {
        try {
          Journal.parse(text);
          fail('parsed: $text');
        } on JournalUnreadable catch (e) {
          expect(e.message, startsWith('update.json is not readable JSON ('));
        }
      }
    });
  });

  group('JournalFile', () {
    late Directory state;
    late String countLog;

    setUp(() {
      state = Directory('${temp.path}/openspec/.specwright')
        ..createSync(recursive: true);
      countLog = '${temp.path}/count.log';
    });

    JournalFile file({int? killAt}) => JournalFile(
      state.path,
      UpdateFileOps(
        environment: {
          'SPECWRIGHT_UPDATE_COUNT': countLog,
          if (killAt != null) 'SPECWRIGHT_UPDATE_KILL_AT': '$killAt',
        },
        exitProcess: (code) => throw StateError('exit $code'),
      ),
    );

    test('lives at update.json with update.json.tmp beside it', () {
      final f = file();
      expect(f.path, '${state.path}/update.json');
      expect(f.tempPath, '${state.path}/update.json.tmp');
    });

    test('reads nothing when there is no journal', () {
      expect(file().read(), isNull);
    });

    test('write goes to the temp file, then a counted rename', () {
      final f = file();
      f.write(Journal.parse(_format2));
      expect(File(f.path).readAsStringSync(), _format2);
      expect(File(f.tempPath).existsSync(), isFalse);
      expect(File(countLog).readAsLinesSync(), [
        '1 mv ${f.tempPath} ${f.path}',
      ]);
      expect(f.read()!.data['phase'], 'staged');
    });

    test('write uses LF and UTF-8 only', () {
      final f = file();
      f.write(Journal.parse(_format2));
      final bytes = File(f.path).readAsBytesSync();
      expect(bytes.contains(13), isFalse);
      expect(
        String.fromCharCodes(bytes).contains('caf\u00c3\u00a9'),
        isTrue,
        reason: 'é as two UTF-8 bytes',
      );
    });

    test('a kill at the rename leaves the old journal and the temp file', () {
      final f = file();
      f.write(Journal.parse(_format1));
      final next = Journal.parse(_format2);
      expect(() => file(killAt: 2).write(next), throwsA(isA<StateError>()));
      expect(File(f.path).readAsStringSync(), _format1);
      expect(File(f.tempPath).readAsStringSync(), _format2);
    });

    test('read refuses a file with trailing garbage', () {
      File('${state.path}/update.json').writeAsStringSync('${_format2}x');
      expect(() => file().read(), throwsA(isA<JournalUnreadable>()));
    });

    test('read refuses format 9', () {
      File('${state.path}/update.json').writeAsStringSync('{"format": 9}\n');
      expect(() => file().read(), throwsA(isA<JournalUnreadable>()));
    });
  });
}
