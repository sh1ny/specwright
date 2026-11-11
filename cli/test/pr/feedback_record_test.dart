import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:isolate';

import 'package:test/test.dart';
import 'package:specwright_cli/src/fs/link.dart';
import 'package:specwright_cli/src/pr/feedback_record.dart';
import 'package:specwright_cli/src/pr/pair.dart';
import 'package:specwright_cli/src/pr/context.dart';
import 'package:specwright_cli/src/process/limits.dart';
import 'package:specwright_cli/src/vcs/codec.dart';

class FaultFiles implements RecordFiles {
  FaultFiles({RecordFiles? actual}) : actual = actual ?? RecordFiles.native();
  final RecordFiles actual;
  bool noLinks = false,
      failWrite = false,
      failClose = false,
      failRmdir = false,
      failReplace = false,
      removeLinkedSource = false;
  String? deniedRead;
  @override
  void acquireLock(String p) => actual.acquireLock(p);
  @override
  List<int> readBytes(String p, {int? limit}) {
    if (p == deniedRead) throw FileSystemException('permission denied', p);
    return actual.readBytes(p, limit: limit);
  }

  @override
  void releaseLock(String p) {
    if (failRmdir) throw FileSystemException('denied', p);
    actual.releaseLock(p);
  }

  @override
  void link(String a, String b) {
    if (noLinks) throw FileSystemException('links unavailable');
    actual.link(a, b);
    if (removeLinkedSource) actual.delete(a);
  }

  @override
  RecordOutput createExclusive(String p) =>
      FaultOutput(actual.createExclusive(p), this);
  @override
  void replace(String a, String b) {
    if (failReplace) throw FileSystemException('replace denied');
    actual.replace(a, b);
  }

  @override
  void delete(String p) => actual.delete(p);
}

class FaultOutput implements RecordOutput {
  FaultOutput(this.actual, this.faults);
  final RecordOutput actual;
  final FaultFiles faults;
  @override
  void writeAll(List<int> b) {
    if (faults.failWrite) throw FileSystemException('disk full');
    actual.writeAll(b);
  }

  @override
  void close() {
    actual.close();
    if (faults.failClose) throw FileSystemException('close failed');
  }
}

Future<void> lockCaller((String, SendPort) input) async {
  final gate = ReceivePort();
  try {
    final store = FeedbackRecordStore(File(input.$1).parent.path);
    await store.withLock(input.$1, () async {
      input.$2.send(['held', gate.sendPort]);
      await gate.first;
    });
  } on PairStop catch (e) {
    input.$2.send([e.error, null]);
  } on Object catch (e) {
    input.$2.send(['unexpected: $e', null]);
  } finally {
    gate.close();
  }
}

void publishCaller((String, SendPort) input) {
  try {
    FeedbackRecordStore(File(input.$1).parent.path).writeNew(input.$1, {
      'version': 2,
      'owner': Isolate.current.hashCode,
      'text': 'é\n${'x' * 20000}',
    });
    input.$2.send('won');
  } on PairStop catch (e) {
    input.$2.send(e.error);
  }
}

void replacementReader((String, SendPort) input) {
  var reads = 0;
  var sharingRefusals = 0;
  String? lastSharingError;
  try {
    while (!File('${input.$1}.finished').existsSync()) {
      Map<dynamic, dynamic> document;
      try {
        document = jsonDecode(
          File(input.$1).readAsStringSync(),
        ) as Map<dynamic, dynamic>;
      } on FileSystemException catch (error) {
        if (Platform.isWindows && error.osError?.errorCode == 32) {
          sharingRefusals++;
          lastSharingError = '$error';
          continue;
        }
        rethrow;
      }
      final owner = document['owner'] as String;
      if (document['text'] != owner * 100000) {
        throw StateError('incomplete replacement document');
      }
      reads++;
      if (reads == 1) input.$2.send('ready');
    }
    input.$2.send({
      'reads': reads,
      'sharing_refusals': sharingRefusals,
      'last_sharing_error': lastSharingError,
    });
  } on Object catch (e) {
    input.$2.send('reader failed: $e');
  }
}

void main() {
  linkTests();
  late Directory tmp;
  late String path;
  setUp(() {
    tmp = Directory.systemTemp.createTempSync('sw-feedback-record-');
    path = '${tmp.path}/record.json';
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  test(
    'record publication and replacement preserve surrogate string values',
    () {
      final store = FeedbackRecordStore(tmp.path);
      final record = <String, Object?>{
        'owner': {'checkout': '/checkout/\uDCFF'},
        'nested': {
          '\uDC81': ['\uDC80', 'é', '😀'],
        },
      };
      store.writeNew(path, record);
      expect(utf8.decode(File(path).readAsBytesSync()), contains(r'\udcff'));
      expect(store.load(path), record);
      record['owner'] = {'checkout': '/other/\uDCFE'};
      record['high'] = '\uD800';
      store.replaceRecord(path, record);
      expect(utf8.decode(File(path).readAsBytesSync()), contains(r'\udcfe'));
      expect(store.load(path), record);
    },
  );

  test(
    'record keys distinguish identities and keep bounded readable names',
    () {
      final store = FeedbackRecordStore(tmp.path);
      final a = store.recordPath('acme-tools/widget', 'a' * 500);
      final b = store.recordPath('acme/tools-widget', 'a' * 500);
      expect(a, isNot(b));
      expect(File(a).uri.pathSegments.last.length, lessThanOrEqualTo(158));
      expect(store.recordPath('ACME-TOOLS/WIDGET', 'a' * 500), a);
    },
  );
  test(
    'concurrent OS locks have one holder and never remove its file',
    () async {
      final receive = ReceivePort();
      final workers = <Isolate>[];
      final release = <SendPort>[];
      final exits = ReceivePort();
      try {
        for (var i = 0; i < 8; i++) {
          workers.add(
            await Isolate.spawn(lockCaller, (
              path,
              receive.sendPort,
            ), onExit: exits.sendPort),
          );
        }
        final iterator = StreamIterator(receive);
        var busy = 0;
        for (var i = 0; i < 8; i++) {
          expect(
            await iterator.moveNext().timeout(const Duration(seconds: 20)),
            true,
          );
          final message = iterator.current as List;
          if (message[0] == 'held') {
            release.add(message[1] as SendPort);
          } else if (message[0] == 'record_busy') {
            busy++;
          }
        }
        expect(release.length, 1);
        expect(busy, 7);
        expect(File('$path.lock').existsSync(), true);
        for (final p in release) {
          p.send(null);
        }
        await exits.take(8).toList().timeout(const Duration(seconds: 20));
        workers.clear();
        expect(File('$path.lock').existsSync(), false);
      } finally {
        for (final p in release) {
          p.send(null);
        }
        for (final worker in workers) {
          worker.kill(priority: Isolate.immediate);
        }
        receive.close();
        exits.close();
      }
    },
  );
  test('existing hardlink destination is never overwritten by fallback', () {
    final store = FeedbackRecordStore(tmp.path);
    final source = File('${tmp.path}/source')..writeAsStringSync('new');
    File(path).writeAsStringSync('old');
    expect(
      () => store.publish(source.path, path),
      throwsA(isA<RecordAlreadyExists>()),
    );
    expect(File(path).readAsStringSync(), 'old');
  });
  test('native and legacy locks exclude each other', () async {
    final lock = '$path.lock';
    final python = Platform.isWindows ? 'python' : 'python3';
    final legacy = await Process.run(python, [
      '-c',
      'import os,sys; os.mkdir(sys.argv[1])',
      lock,
    ]);
    expect(legacy.exitCode, 0, reason: '${legacy.stderr}');
    final store = FeedbackRecordStore(tmp.path);
    await expectLater(
      store.withLock(path, () => fail('legacy lock was ignored')),
      throwsA(isA<PairStop>().having((e) => e.error, 'error', 'record_busy')),
    );
    expect(Directory(lock).existsSync(), true);
    Directory(lock).deleteSync();
    await store.withLock(path, () async {
      expect(File(lock).existsSync(), true);
      final refused = await Process.run(python, [
        '-c',
        'import os,sys\ntry: os.mkdir(sys.argv[1])\nexcept FileExistsError: sys.exit(7)\n',
        lock,
      ]);
      expect(refused.exitCode, 7, reason: '${refused.stderr}');
      expect(File(lock).existsSync(), true);
    });
    expect(File(lock).existsSync(), false);
  });
  test('interrupted SDK publication stays recoverable', () {
    final store = FeedbackRecordStore(tmp.path);
    for (final content in ['', '{"version":2,"owner":']) {
      File(path).writeAsStringSync(content);
      expect(
        () => store.writeNew(path, {'version': 2, 'owner': 'new'}),
        throwsA(
          isA<PairStop>().having((e) => e.error, 'error', 'record_exists'),
        ),
      );
      expect(File(path).readAsStringSync(), content);
      expect(
        () => store.load(path),
        throwsA(
          isA<PairStop>().having((e) => e.error, 'error', 'record_unreadable'),
        ),
      );
      File(path).deleteSync();
    }
  });
  test('fallback exclusive create cleans failed writes and closes', () {
    final faults = FaultFiles()..noLinks = true;
    final store = FeedbackRecordStore(tmp.path, files: faults);
    final source = File('${tmp.path}/source')..writeAsStringSync('complete');
    for (final close in [false, true]) {
      faults.failWrite = !close;
      faults.failClose = close;
      expect(
        () => store.publish(source.path, path),
        throwsA(isA<FileSystemException>()),
      );
      expect(File(path).existsSync(), false);
    }
    faults.failWrite = false;
    faults.failClose = false;
    store.publish(source.path, path);
    expect(File(path).readAsStringSync(), 'complete');
    expect(
      () => store.publish(source.path, path),
      throwsA(isA<RecordAlreadyExists>()),
    );
  });
  test('fallback permission failure leaves no record', () {
    var opened = false;
    final native = RecordFiles.native(
      makePrivate: (created) {
        expect(File(created).existsSync(), true);
        throw FileSystemException('permission adapter failed', created);
      },
      openCreated: (file) {
        opened = true;
        return file.openSync(mode: FileMode.write);
      },
    );
    final source = File('${tmp.path}/source')..writeAsStringSync('complete');
    final store = FeedbackRecordStore(
      tmp.path,
      files: FaultFiles(actual: native)..noLinks = true,
    );
    expect(
      () => store.publish(source.path, path),
      throwsA(isA<FileSystemException>()),
    );
    expect(opened, false);
    expect(File(path).existsSync(), false);
  });
  test('fallback open failure leaves no record', () {
    final native = RecordFiles.native(
      openCreated: (file) {
        expect(file.existsSync(), true);
        throw FileSystemException('open failed', file.path);
      },
    );
    final source = File('${tmp.path}/source')..writeAsStringSync('complete');
    final store = FeedbackRecordStore(
      tmp.path,
      files: FaultFiles(actual: native)..noLinks = true,
    );
    expect(
      () => store.publish(source.path, path),
      throwsA(isA<FileSystemException>()),
    );
    expect(File(path).existsSync(), false);
  });
  test('fallback write failure leaves no record', () {
    final source = File('${tmp.path}/source')..writeAsStringSync('complete');
    final faults = FaultFiles()
      ..noLinks = true
      ..failWrite = true;
    final store = FeedbackRecordStore(tmp.path, files: faults);
    expect(
      () => store.publish(source.path, path),
      throwsA(isA<FileSystemException>()),
    );
    expect(File(path).existsSync(), false);
    faults.failWrite = false;
    store.publish(source.path, path);
    expect(File(path).readAsBytesSync(), source.readAsBytesSync());
  });
  test('too-long legacy filename is absent without losing the bounded key', () {
    final store = FeedbackRecordStore(tmp.path);
    final repo = 'org/${List.filled(100, 'repo').join()}';
    final change = List.filled(120, 'd').join();
    final old = store.legacyPath(repo, change);
    expect(FileSystemEntity.isFileSync(old), false);
    final location = store.locate(repo, change);
    expect(location.path, store.recordPath(repo, change));
    expect(location.ignoredLegacy, isNull);
    expect(File(location.path).existsSync(), false);
  });
  test('legacy migration tolerates another caller removing the source after publication', () {
    final faults = FaultFiles()..removeLinkedSource = true;
    final store = FeedbackRecordStore(tmp.path, files: faults);
    final old = File(store.legacyPath('o/r', 'change'));
    final bytes = utf8.encode(
      '{"code_repo":"o/r","change":"change","version":1}',
    );
    old.writeAsBytesSync(bytes);
    final location = store.locate('o/r', 'change');
    expect(location.path, store.recordPath('o/r', 'change'));
    expect(location.ignoredLegacy, isNull);
    expect(File(location.path).readAsBytesSync(), bytes);
    expect(old.existsSync(), false);
  });
  test(
    'denied legacy reads refuse alone and are ignored beside a valid record',
    () {
      final faults = FaultFiles();
      final store = FeedbackRecordStore(tmp.path, files: faults);
      final old = File(store.legacyPath('o/r', 'change'))
        ..writeAsStringSync('{}');
      faults.deniedRead = old.path;
      expect(
        () => store.locate('o/r', 'change'),
        throwsA(
          isA<PairStop>()
              .having((e) => e.error, 'error', 'record_unreadable')
              .having((e) => e.message, 'message', contains(old.path)),
        ),
      );
      final path = store.recordPath('o/r', 'change');
      expect(File(path).existsSync(), false);
      store.writeNew(path, {
        'version': 2,
        'code_repo': 'o/r',
        'change': 'change',
      });
      final before = File(path).readAsBytesSync();
      final location = store.locate('o/r', 'change');
      expect(location.path, path);
      expect(location.ignoredLegacy, old.path.replaceAll(r'\', '/'));
      expect(File(path).readAsBytesSync(), before);
      expect(old.readAsStringSync(), '{}');
    },
  );
  test('a close failure never replaces the primary write failure', () {
    final source = File('${tmp.path}/source')..writeAsStringSync('complete');
    final faults = FaultFiles()
      ..noLinks = true
      ..failWrite = true
      ..failClose = true;
    final store = FeedbackRecordStore(tmp.path, files: faults);
    expect(
      () => store.publish(source.path, path),
      throwsA(
        isA<FileSystemException>().having(
          (e) => e.message,
          'message',
          'disk full',
        ),
      ),
    );
    expect(File(path).existsSync(), false);
  });
  test('failed lock cleanup retains success and primary error with request-owned reporting', () async {
    final faults = FaultFiles()..failRmdir = true;
    final store = FeedbackRecordStore(tmp.path, files: faults);
    expect(await store.withLock(path, () => 42), 42);
    expect(store.leftLocks, ['${path.replaceAll(r'\', '/')}.lock']);
    await expectLater(
      store.withLock(path, () => 0),
      throwsA(isA<PairStop>().having((e) => e.error, 'error', 'record_busy')),
    );
    final other = '$path.other';
    await expectLater(
      store.withLock(other, () => throw PairStop('not_owner', 'foreign')),
      throwsA(isA<PairStop>().having((e) => e.error, 'error', 'not_owner')),
    );
    expect(store.leftLocks.length, 2);
    expect(FeedbackRecordStore(tmp.path).leftLocks, isEmpty);
  });
  test('native records use UTF8 LF and replacement is a complete document', () {
    final store = FeedbackRecordStore(tmp.path);
    store.writeNew(path, {
      'version': 2,
      'owner': {'id': 'one'},
      'text': 'é\nline',
    });
    final bytes = File(path).readAsBytesSync();
    expect(bytes, isNot(contains(13)));
    expect(jsonDecode(utf8.decode(bytes)), {
      'version': 2,
      'owner': {'id': 'one'},
      'text': 'é\nline',
    });
    store.replaceRecord(path, {
      'version': 2,
      'owner': {'id': 'two'},
    });
    expect((store.load(path) as Map)['owner'], {'id': 'two'});
    expect(tmp.listSync().where((f) => f.path.contains('.tmp-')), isEmpty);
  });
  test(
    'legacy migration copies bytes and unreadable records block new work',
    () {
      final store = FeedbackRecordStore(tmp.path);
      final old = File(store.legacyPath('o/r', 'change'));
      final original = utf8.encode(
        '{\n "code_repo":"o/r", "change":"change", "version":2\n}',
      );
      old.writeAsBytesSync(original);
      final location = store.locate('o/r', 'change');
      expect(File(location.path).readAsBytesSync(), original);
      expect(old.existsSync(), false);
      File(location.path).deleteSync();
      old.writeAsStringSync('{cut off');
      expect(
        () => store.locate('o/r', 'change'),
        throwsA(
          isA<PairStop>().having((e) => e.error, 'error', 'record_unreadable'),
        ),
      );
      expect(old.existsSync(), true);
    },
  );
  test('concurrent publication has exactly one complete winner', () async {
    final receive = ReceivePort();
    final workers = <Isolate>[];
    final exits = ReceivePort();
    try {
      for (var i = 0; i < 8; i++) {
        workers.add(
          await Isolate.spawn(publishCaller, (
            path,
            receive.sendPort,
          ), onExit: exits.sendPort),
        );
      }
      final messages = await receive
          .take(8)
          .toList()
          .timeout(const Duration(seconds: 20));
      expect(messages.where((m) => m == 'won').length, 1);
      expect(messages.where((m) => m == 'record_exists').length, 7);
      expect((FeedbackRecordStore(tmp.path).load(path) as Map)['version'], 2);
      expect(tmp.listSync().where((f) => f.path.contains('.tmp-')), isEmpty);
      await exits.take(8).toList().timeout(const Duration(seconds: 20));
      workers.clear();
    } finally {
      for (final worker in workers) {
        worker.kill(priority: Isolate.immediate);
      }
      receive.close();
      exits.close();
    }
  });
  test('replacement failure preserves old record and removes owned temp', () {
    final faults = FaultFiles();
    final store = FeedbackRecordStore(tmp.path, files: faults);
    store.writeNew(path, {'version': 2, 'owner': 'before'});
    faults.failReplace = true;
    expect(
      () => store.replaceRecord(path, {'version': 2, 'owner': 'after'}),
      throwsA(isA<FileSystemException>()),
    );
    expect((store.load(path) as Map)['owner'], 'before');
    expect(tmp.listSync().where((f) => f.path.contains('.tmp-')), isEmpty);
  });
  test('concurrent readers see complete atomic replacements', () async {
    final store = FeedbackRecordStore(tmp.path);
    store.writeNew(path, {'owner': 'a', 'text': 'a' * 100000});
    final receive = ReceivePort(), exits = ReceivePort();
    final messages = StreamIterator(receive);
    final worker = await Isolate.spawn(replacementReader, (
      path,
      receive.sendPort,
    ), onExit: exits.sendPort);
    var exited = false;
    try {
      expect(
        await messages.moveNext().timeout(const Duration(seconds: 20)),
        true,
      );
      expect(messages.current, 'ready');
      for (var i = 0; i < 32; i++) {
        final owner = i.isEven ? 'a' : 'b';
        final before = File(path).readAsBytesSync();
        try {
          store.replaceRecord(path, {'owner': owner, 'text': owner * 100000});
        } on FileSystemException {
          // Windows can refuse replacement while the reader's handle is open.
          // Refusal must preserve the prior complete record and clean our temp.
          expect(File(path).readAsBytesSync(), before);
          expect(
            tmp.listSync().where((f) => f.path.contains('.tmp-')),
            isEmpty,
          );
        }
      }
      File('$path.finished').writeAsStringSync('done');
      expect(
        await messages.moveNext().timeout(const Duration(seconds: 20)),
        true,
      );
      expect(messages.current, isA<Map<dynamic, dynamic>>());
      final observed = messages.current as Map<dynamic, dynamic>;
      expect(observed['reads'], greaterThan(0));
      if ((observed['sharing_refusals'] as int) > 0) {
        expect(Platform.isWindows, true);
        expect(observed['last_sharing_error'], contains('errno = 32'));
      }
      await exits.first.timeout(const Duration(seconds: 20));
      exited = true;
      store.replaceRecord(path, {'owner': 'c', 'text': 'c' * 100000});
      expect((store.load(path) as Map)['text'], 'c' * 100000);
      expect(tmp.listSync().where((f) => f.path.contains('.tmp-')), isEmpty);
    } finally {
      if (!exited) {
        File('$path.finished').writeAsStringSync('stop');
        worker.kill(priority: Isolate.immediate);
      }
      await messages.cancel();
      receive.close();
      exits.close();
    }
  });
  test('Windows open-reader replacement refusal matches Python', () {
    final store = FeedbackRecordStore(tmp.path);
    store.writeNew(path, {'owner': 'before'});
    final source = File('${tmp.path}/replacement.json')
      ..writeAsStringSync('{"owner":"after"}');
    final reader = File(path).openSync(mode: FileMode.read);
    try {
      final python = Process.runSync('python', [
        '-c',
        'import os,sys; os.replace(sys.argv[1],sys.argv[2])',
        source.path,
        path,
      ]);
      expect(
        python.exitCode,
        isNot(0),
        reason: 'the equivalent Python replacement unexpectedly succeeded',
      );
      expect((store.load(path) as Map)['owner'], 'before');
      expect(source.existsSync(), true);
      expect(
        () => store.replaceRecord(path, {'owner': 'after'}),
        throwsA(isA<FileSystemException>()),
      );
      expect((store.load(path) as Map)['owner'], 'before');
      expect(tmp.listSync().where((f) => f.path.contains('.tmp-')), isEmpty);
    } finally {
      reader.closeSync();
    }
    store.replaceRecord(path, {'owner': 'after'});
    expect((store.load(path) as Map)['owner'], 'after');
    expect(tmp.listSync().where((f) => f.path.contains('.tmp-')), isEmpty);
  }, skip: Platform.isWindows ? false : 'Windows handle-sharing refusal');
  test('private POSIX permissions precede opening record content', () {
    var opens = 0;
    final files = RecordFiles.native(
      openCreated: (file) {
        expect(file.lengthSync(), 0);
        expect(file.statSync().mode & 0x1ff, 0x180);
        opens++;
        return file.openSync(mode: FileMode.write);
      },
    );
    final store = FeedbackRecordStore(
      tmp.path,
      files: FaultFiles(actual: files)..noLinks = true,
    );
    store.writeNew(path, {'version': 2});
    expect(opens, 2);
    expect(File(path).statSync().mode & 0x1ff, 0x180);
  }, skip: Platform.isWindows ? 'POSIX permission bits' : false);
  test('raw POSIX parent bytes survive locking publication and replacement', () async {
    // Probe the filesystem with actual Python bytes first. A successful OS
    // probe must still be followed by the Dart assertions below; never turn
    // an SDK path-handling failure into a skip.
    final probe = await Process.run('python3', [
      '-c',
      r'''
import json, os, sys
path = os.fsencode(sys.argv[1]) + b'/\xff'
try:
    os.mkdir(path)
except OSError as error:
    print(json.dumps({'ok': False, 'error': str(error)}))
else:
    os.rmdir(path)
    print(json.dumps({'ok': True}))
''',
      tmp.path,
    ]);
    expect(probe.exitCode, 0, reason: '${probe.stdout}\n${probe.stderr}');
    final capability =
        jsonDecode(probe.stdout as String) as Map<String, dynamic>;
    if (capability['ok'] != true) {
      if (Platform.isLinux) {
        fail('Linux raw-path probe must succeed: ${capability['error']}');
      }
      markTestSkipped(
        '${Platform.operatingSystem} filesystem refuses raw path bytes: ${capability['error']}',
      );
      return;
    }
    final directory = decodeEscaped([...utf8.encode(tmp.path), 47, 0xff]);
    rawDirectory(directory).createSync();
    final store = FeedbackRecordStore('$directory/new/nested');
    final record = store.recordPath('o/r', 'raw-path');
    store.writeNew(record, {'version': 2, 'owner': 'before'});
    await store.withLock(record, () {
      expect(rawFile('$record.lock').existsSync(), true);
      store.replaceRecord(record, {'version': 2, 'owner': 'after'});
    });
    expect(rawFile('$record.lock').existsSync(), false);
    expect((store.load(record) as Map)['owner'], 'after');
    rawFile(record).deleteSync();
    rawDirectory(directory).deleteSync(recursive: true);
  }, skip: Platform.isWindows ? 'POSIX filename bytes' : false);
  test('missing records differ from unreadable files and directories', () {
    final store = FeedbackRecordStore(tmp.path);
    expect(store.load(path), null);
    File(path).writeAsStringSync('{partial');
    expect(
      () => store.load(path),
      throwsA(
        isA<PairStop>().having((e) => e.error, 'error', 'record_unreadable'),
      ),
    );
    File(path).deleteSync();
    Directory(path).createSync();
    expect(
      () => store.load(path),
      throwsA(
        isA<PairStop>().having((e) => e.error, 'error', 'record_unreadable'),
      ),
    );
  });

  test('an oversized record blocks replacement', () {
    // the record is read through the 32 MiB bound; a longer file stays as it is
    final store = FeedbackRecordStore(tmp.path);
    File(path).openSync(mode: FileMode.write)
      ..truncateSync(defaultMaxBytes + 1)
      ..closeSync();
    expect(File(path).lengthSync(), defaultMaxBytes + 1);
    expect(
      () => store.load(path),
      throwsA(
        isA<PairStop>()
            .having((e) => e.error, 'error', 'record_unreadable')
            .having((e) => e.message, 'message', contains('32 MiB')),
      ),
    );
    expect(
      () => store.writeNew(path, {'version': 2, 'owner': 'new'}),
      throwsA(isA<PairStop>()),
    );
    expect(File(path).lengthSync(), defaultMaxBytes + 1);
  });

  test('a store with another RecordFiles reads under the same bound', () {
    // a fake that honours the limit it is given, as the SDK files do
    final seen = <int?>[];
    final files = _Limited(seen, defaultMaxBytes + 1);
    final store = FeedbackRecordStore(tmp.path, files: files);
    expect(
      () => store.load(path),
      throwsA(
        isA<PairStop>().having((e) => e.error, 'error', 'record_unreadable'),
      ),
    );
    expect(seen, [defaultMaxBytes]);
  });
}

/// A record file that holds [size] bytes and records the limit each read asks for.
class _Limited extends FaultFiles {
  _Limited(this.seen, this.size);
  final List<int?> seen;
  final int size;
  @override
  List<int> readBytes(String p, {int? limit}) {
    seen.add(limit);
    return List<int>.filled(limit == null ? size : limit + 1, 0x20);
  }
}

void linkTests() {
  group('fs/link.dart (D8: the link and rename of ln and mv -f)', () {
    late Directory dir;
    setUp(() => dir = Directory.systemTemp.createTempSync('sw-link-'));
    tearDown(() => dir.deleteSync(recursive: true));

    test('hardLink makes a second name for the same bytes', () {
      final a = File('${dir.path}/a')..writeAsStringSync('one');
      hardLink(a.path, '${dir.path}/b');
      expect(File('${dir.path}/b').readAsStringSync(), 'one');
      a.deleteSync();
      expect(File('${dir.path}/b').readAsStringSync(), 'one');
    });

    test('hardLink never replaces an existing destination', () {
      File('${dir.path}/a').writeAsStringSync('new');
      File('${dir.path}/b').writeAsStringSync('first');
      expect(
        () => hardLink('${dir.path}/a', '${dir.path}/b'),
        throwsA(isA<FileSystemException>()),
      );
      expect(File('${dir.path}/b').readAsStringSync(), 'first');
    });

    test('replaceFile replaces the destination and removes the source', () {
      File('${dir.path}/a').writeAsStringSync('new');
      File('${dir.path}/b').writeAsStringSync('old');
      replaceFile('${dir.path}/a', '${dir.path}/b');
      expect(File('${dir.path}/b').readAsStringSync(), 'new');
      expect(File('${dir.path}/a').existsSync(), isFalse);
    });

    test('a missing source is a FileSystemException', () {
      expect(
        () => replaceFile('${dir.path}/none', '${dir.path}/b'),
        throwsA(isA<FileSystemException>()),
      );
      expect(
        () => hardLink('${dir.path}/none', '${dir.path}/b'),
        throwsA(isA<FileSystemException>()),
      );
    });
  });
}
