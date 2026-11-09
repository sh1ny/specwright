import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/pr/context.dart';
import 'package:specwright_cli/src/pr/feedback_pass.dart';
import 'package:specwright_cli/src/pr/feedback_record.dart';
import 'package:specwright_cli/src/pr/pair.dart';
import 'package:specwright_cli/src/pr/workflow.dart';
import 'package:test/test.dart';

class LockCleanupFailure implements RecordFiles {
  final actual = RecordFiles.native();
  @override
  void acquireLock(String path) => actual.acquireLock(path);
  @override
  void releaseLock(String path) =>
      throw FileSystemException('lock cleanup denied', path);
  @override
  List<int> readBytes(String path) => actual.readBytes(path);
  @override
  RecordOutput createExclusive(String path) => actual.createExclusive(path);
  @override
  void delete(String path) => actual.delete(path);
  @override
  void link(String source, String destination) =>
      actual.link(source, destination);
  @override
  void replace(String source, String destination) =>
      actual.replace(source, destination);
}

class UnexpectedReplacement extends FeedbackRecordStore {
  UnexpectedReplacement(super.directory, {super.files});
  @override
  void replaceRecord(String path, Map<String, Object?> record) =>
      throw StateError('primary replacement failure');
}

void main() {
  FeedbackPass configured(Map<String, String> environment) => FeedbackPass(
    Workflow(
      PrContext(
        scriptsDir: '.',
        bash: 'bash',
        writeOut: (_) {},
        writeErr: (_) {},
        environment: environment,
      ),
    ),
  );
  test('explicit feedback state directory does not need a home', () {
    expect(
      configured({'SPECWRIGHT_STATE_DIR': '/chosen-state'}).records.directory,
      '/chosen-state/feedback',
    );
  });
  test('injected feedback environment remains authoritative', () async {
    final tmp = Directory.systemTemp.createTempSync('sw-feedback-env-');
    addTearDown(() => tmp.deleteSync(recursive: true));
    final cli = Directory.current.uri;
    final script = File('${tmp.path}/injected.dart');
    script.writeAsStringSync('''
import 'dart:convert';
import 'dart:io';
import ${jsonEncode(cli.resolve('lib/src/pr/context.dart').toString())};
import ${jsonEncode(cli.resolve('lib/src/pr/feedback_pass.dart').toString())};
import ${jsonEncode(cli.resolve('lib/src/pr/pair.dart').toString())};
import ${jsonEncode(cli.resolve('lib/src/pr/workflow.dart').toString())};
FeedbackPass configured(Map<String,String> env) => FeedbackPass(Workflow(PrContext(
  scriptsDir: '.', bash: 'bash', writeOut: (_) {}, writeErr: (_) {}, environment: env)));
String directory(Map<String,String> env) => configured(env).records.directory;
Future<void> main() async {
  final result = <String,Object?>{
    'home': Platform.environment['HOME'],
    'absent': directory({'HOME':'/injected-home', 'USERPROFILE':'/injected-home'}),
    'empty': directory({'SPECWRIGHT_STATE_DIR':'', 'HOME':'/injected-home', 'USERPROFILE':'/injected-home'}),
    'explicit': directory({'SPECWRIGHT_STATE_DIR':'/injected-state'}),
  };
  try { directory({}); result['missing'] = 'accepted'; }
  catch (_) { result['missing'] = 'refused'; }
  try { await configured({}).run(['unknown']); result['usage'] = 0; }
  on PairStop catch (e) { result['usage'] = e.code; }
  catch (_) { result['usage'] = 1; }
  stdout.write(jsonEncode(result));
}
''');
    final home = Directory('${tmp.path}/ambient-home')..createSync();
    final result = await Process.run(
      Platform.resolvedExecutable,
      [
        '--packages=${File('.dart_tool/package_config.json').absolute.path}',
        script.path,
      ],
      environment: {
        ...Platform.environment,
        'HOME': home.path,
        'USERPROFILE': home.path,
        'SPECWRIGHT_STATE_DIR': '${tmp.path}/ambient-state',
      },
    );
    expect(result.exitCode, 0, reason: '${result.stdout}\n${result.stderr}');
    expect(jsonDecode(result.stdout as String), {
      'home': home.path,
      'absent': '/injected-home/.cache/specwright/feedback',
      'empty': '/injected-home/.cache/specwright/feedback',
      'explicit': '/injected-state/feedback',
      'missing': 'refused',
      'usage': 2,
    });
  });
  test('Windows home uses profile then drive and path', () {
    expect(
      configured({
        'USERPROFILE': r'C:\profile',
        'HOMEDRIVE': 'D:',
        'HOMEPATH': r'\fallback',
      }).records.directory.replaceAll(r'\', '/'),
      'C:/profile/.cache/specwright/feedback',
    );
    expect(
      configured({
        'USERPROFILE': '',
        'HOMEDRIVE': 'D:',
        'HOMEPATH': r'\fallback',
      }).records.directory.replaceAll(r'\', '/'),
      'D:/fallback/.cache/specwright/feedback',
    );
  }, skip: !Platform.isWindows);
  test('Windows missing home refuses instead of using a root cache', () {
    expect(() => configured({}).records.directory, throwsStateError);
    expect(
      () =>
          configured({'USERPROFILE': '', 'HOMEDRIVE': 'D:'}).records.directory,
      throwsStateError,
    );
  }, skip: !Platform.isWindows);
  test(
    'missing feedback record allows a new pass without evidence reads',
    () async {
      final tmp = Directory.systemTemp.createTempSync('sw-feedback-pass-');
      addTearDown(() => tmp.deleteSync(recursive: true));
      final ctx = PrContext(
        scriptsDir: tmp.path,
        bash: 'bash',
        writeOut: (_) {},
        writeErr: (_) {},
        environment: {'SPECWRIGHT_STATE_DIR': tmp.path},
      );
      final result = await FeedbackPass(Workflow(ctx)).run([
        'plan',
        '--code',
        tmp.path,
        '--code-repo',
        'o/r',
        '--change',
        'change',
      ]);
      expect(result, {
        'ok': true,
        'record': false,
        'new_pass_allowed': true,
        'status': 'none',
        'rows': <Object?>[],
        'stops': <Object?>[],
        'delete_record': false,
        'needs_user': false,
      });
    },
  );
  for (final outcome in ['success', 'structured', 'unexpected']) {
    test('request-owned lock cleanup reporting preserves $outcome', () async {
      final tmp = Directory.systemTemp.createTempSync('sw-feedback-pass-');
      addTearDown(() => tmp.deleteSync(recursive: true));
      final files = LockCleanupFailure();
      final records = outcome == 'unexpected'
          ? UnexpectedReplacement(tmp.path, files: files)
          : FeedbackRecordStore(tmp.path, files: files);
      final path = records.recordPath('o/r', 'change');
      records.writeNew(path, {
        'version': 2,
        'owner': {'id': 'old', 'at': '2026-01-01T00:00:00Z'},
      });
      final ctx = PrContext(
        scriptsDir: tmp.path,
        bash: 'bash',
        writeOut: (_) {},
        writeErr: (_) {},
      );
      final pass = FeedbackPass(Workflow(ctx), records: records);
      final call = pass.run([
        'adopt',
        '--code',
        tmp.path,
        '--code-repo',
        'o/r',
        '--change',
        'change',
        '--owner',
        'new',
        '--from',
        outcome == 'structured' ? 'stale' : 'old',
      ]);
      final lock = '${path.replaceAll(r'\', '/')}.lock';
      if (outcome == 'success') {
        final result = await call;
        expect(result['owner'], 'new');
        expect(result['lock_left'], [lock]);
      } else {
        await expectLater(
          call,
          throwsA(
            isA<PairStop>()
                .having(
                  (e) => e.error,
                  'primary error',
                  outcome == 'structured' ? 'not_owner' : 'internal_error',
                )
                .having((e) => e.extra['lock_left'], 'owned lock', [lock]),
          ),
        );
      }
      expect(FeedbackRecordStore(tmp.path).leftLocks, isEmpty);
    });
  }
}
