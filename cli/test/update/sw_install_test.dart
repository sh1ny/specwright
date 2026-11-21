import 'dart:async';
import 'dart:convert';
import 'dart:ffi' show Abi;
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:specwright_cli/src/update/options.dart'
    show parseUpdateOptions, updateInterface;
import 'package:specwright_cli/src/update/place.dart' show fileSha;
import 'package:specwright_cli/src/update/stop.dart';
import 'package:specwright_cli/src/update/sw_install.dart' show swInstall;
import 'package:specwright_cli/src/commands/update.dart';
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

import 'fake_sw.dart';

// `sw update sw-install` (design D4, D6, D7 and D9 of native-cli-update; the
// scenarios of "A tagged install places a checked sw for the host", "An
// install without release binaries says so" and "Contributors place a
// tree-built sw with one task"). A fake sw stands for the downloaded or built
// binary; the release is a file:// mirror.

final _exe = Platform.isWindows ? 'sw.exe' : 'sw';
const _notice = 'THIRD_PARTY_NOTICES.txt';
const _noticeText = 'Fixture third-party notice\n';
const _targets = [
  'linux-x64',
  'linux-arm64',
  'windows-x64',
  'macos-arm64',
  'macos-x64',
];

String _asset(String target) =>
    'sw-$target${target.startsWith('windows') ? '.exe' : ''}';

String _hostTarget() {
  final parts = Abi.current().toString().split('_');
  final os = const {
    'linux': 'linux',
    'macos': 'macos',
    'windows': 'windows',
  }[parts.first];
  return '$os-${parts.last}';
}

String _sha(List<int> bytes) => sha256.convert(bytes).toString();

final RegExp _partName = RegExp(
  r'^\.sw-[0-9a-f]+\.(sums\.part|notice\.part|part(\.exe)?|stage)$',
);

bool _isPart(String path) => _partName.hasMatch(p.basename(path));

bool _isStage(String path) => p.basename(path).endsWith('.stage');

/// File operations whose `remove` fails for the paths [failRemove] names (as a
/// held file does) and whose `rename` fails for those [failRename] names;
/// everything else is the counted wrapper. [renamed] lists every rename's
/// target, [refused] every refused removal.
class _Ops extends UpdateFileOps {
  _Ops(Map<String, String> env, {this.failRemove, this.failRename})
    : super(environment: env);

  final bool Function(String path)? failRemove;
  final bool Function(String to)? failRename;
  final List<String> renamed = [];
  final List<String> refused = [];

  @override
  void remove(String path) {
    if (failRemove?.call(path) ?? false) {
      refused.add(path);
      throw FileSystemException('injected: the file is held', path);
    }
    super.remove(path);
  }

  @override
  void rename(String from, String to) {
    renamed.add(to);
    if (failRename?.call(to) ?? false) {
      throw FileSystemException('injected: rename refused', to);
    }
    super.rename(from, to);
  }
}

bool get _canDenyAccess {
  if (Platform.isWindows) return false;
  return Process.runSync('id', ['-u']).stdout.toString().trim() != '0';
}

Future<UpdateStop> _stopOf(Future<Object?> run) async {
  try {
    await run;
  } on UpdateStop catch (e) {
    return e;
  }
  fail('expected an UpdateStop');
}

void main() {
  late Directory temp;
  late String fake;
  late String fakeOld;
  late String fakeIface9;
  late Directory work;
  late String home;
  late String log;
  var n = 0;

  setUpAll(() async {
    temp = Directory.systemTemp.createTempSync('sw-install-');
    fake = await compileFakeSw(temp);
    fakeOld = await compileFakeSw(temp, name: 'fake-old', version: '0.36.0');
    fakeIface9 = await compileFakeSw(temp, name: 'fake-9', interface: 9);
  });

  tearDownAll(() => temp.deleteSync(recursive: true));

  setUp(() {
    work = Directory('${temp.path}/case-${n++}')..createSync();
    home = '${work.path.replaceAll(r'\', '/')}/home';
    Directory(home).createSync();
    log = '${work.path}/ops.log';
  });

  String bin([String version = '0.37.0']) => '$home/.specwright/bin/$version';

  /// A tree with `VERSION` and `cli/THIRD_PARTY_NOTICES.txt`.
  String tree({String version = '0.37.0', bool notice = true}) {
    final dir = '${work.path}/tree';
    Directory('$dir/cli').createSync(recursive: true);
    File('$dir/VERSION').writeAsStringSync('$version\n');
    if (notice) File('$dir/cli/$_notice').writeAsStringSync(_noticeText);
    return dir;
  }

  Future<(int, Map<String, Object?>)> run(
    List<String> args, {
    Map<String, String> env = const {},
    void Function(int code)? exitProcess,
    UpdateFileOps? fileOps,
  }) async {
    final out = <int>[];
    final code = await runUpdateCommand(
      args,
      writeOut: out.addAll,
      cwd: work.path,
      exitProcess: exitProcess,
      fileOps: fileOps,
      environment: {
        'SPECWRIGHT_HOME': home,
        'SPECWRIGHT_UPDATE_COUNT': log,
        ...env,
      },
    );
    final text = utf8.decode(out);
    expect(text.endsWith('\n'), isTrue);
    return (code, jsonDecode(text) as Map<String, Object?>);
  }

  List<String> ops() => File(log).existsSync()
      ? File(log).readAsLinesSync().where((l) => l.isNotEmpty).toList()
      : <String>[];

  Map<String, List<int>> filesUnder(String dir) => {
    for (final e
        in Directory(dir).existsSync()
            ? Directory(dir).listSync(recursive: true).whereType<File>()
            : <File>[])
      e.path: e.readAsBytesSync(),
  };

  group('--build FILE --download TREE', () {
    Future<(int, Map<String, Object?>)> build(
      String file, {
      String? tree_,
      List<String> more = const [],
    }) => run([
      '--code',
      work.path,
      '--download',
      tree_ ?? tree(),
      '--build',
      file,
      ...more,
      'sw-install',
    ]);

    test('places the binary and the notice, notice first', () async {
      final source = copyFakeSw(fake, '${work.path}/build', _exe);
      final bytes = File(source).readAsBytesSync();
      final (code, doc) = await build(source);
      expect(code, 0, reason: '$doc');
      expect(doc['ok'], isTrue);
      expect(doc['subcommand'], 'sw-install');
      expect(doc['action'], 'installed');
      expect(doc['interface'], updateInterface);
      expect(doc['version'], '0.37.0');
      expect(doc['path'], '${bin()}/$_exe');
      expect(File('${bin()}/$_exe').readAsBytesSync(), bytes);
      expect(File('${bin()}/$_notice').readAsStringSync(), _noticeText);
      // nothing else is left under the version directory
      expect(
        Directory(bin()).listSync().map((e) => p.basename(e.path)).toList()
          ..sort(),
        [_exe, _notice]..sort(),
      );
      final moves = ops().where((l) => l.contains(' mv ')).toList();
      final noticeAt = moves.indexWhere((l) => l.contains(_notice));
      final binaryAt = moves.indexWhere((l) => l.endsWith('${bin()}/$_exe'));
      expect(noticeAt, greaterThanOrEqualTo(0), reason: '$moves');
      expect(binaryAt, greaterThan(noticeAt), reason: '$moves');
    });

    test('the source file is left where it is, never moved', () async {
      final source = copyFakeSw(fake, '${work.path}/build', _exe);
      final (code, _) = await build(source);
      expect(code, 0);
      expect(File(source).existsSync(), isTrue);
      for (final line in ops().where((l) => l.contains(' mv '))) {
        expect(line.split(' ')[2], isNot(source), reason: line);
      }
    });

    test('a binary reporting another version changes nothing', () async {
      final source = copyFakeSw(fakeOld, '${work.path}/build', _exe);
      Directory(bin()).createSync(recursive: true);
      File('${bin()}/$_exe').writeAsStringSync('existing');
      final before = filesUnder(home);
      final (code, doc) = await build(source);
      expect(code, 1);
      expect(doc['ok'], isFalse);
      expect(doc['error'], 'sw_check_failed');
      expect(doc['message'], allOf(contains('0.36.0'), contains('0.37.0')));
      expect(filesUnder(home), before);
      expect(File('${bin()}/$_exe').readAsStringSync(), 'existing');
    });

    test('another interface changes nothing', () async {
      final source = copyFakeSw(fakeIface9, '${work.path}/build', _exe);
      final (code, doc) = await build(source);
      expect(code, 1);
      expect(doc['error'], 'sw_check_failed');
      expect(doc['message'], contains('interface 9'));
      expect(filesUnder(home), isEmpty);
    });

    test('an existing different file is replaced by a rename', () async {
      final source = copyFakeSw(fake, '${work.path}/build', _exe);
      Directory(bin()).createSync(recursive: true);
      File('${bin()}/$_exe').writeAsStringSync('older build');
      final (code, doc) = await build(source);
      expect(code, 0);
      expect(doc['action'], 'replaced');
      expect(
        File('${bin()}/$_exe').readAsBytesSync(),
        File(source).readAsBytesSync(),
      );
    });

    test('the same file again is kept', () async {
      final source = copyFakeSw(fake, '${work.path}/build', _exe);
      await build(source);
      final before = filesUnder(home);
      final (code, doc) = await build(source);
      expect(code, 0);
      expect(doc['action'], 'kept');
      expect(filesUnder(home), before);
    });

    test('a tree without the notice stops before any placement', () async {
      final source = copyFakeSw(fake, '${work.path}/build', _exe);
      final (code, doc) = await build(source, tree_: tree(notice: false));
      expect(code, 1);
      expect(doc['error'], 'download_incomplete');
      expect(doc['message'], contains('cli/$_notice'));
      expect(filesUnder(home), isEmpty);
    });

    test('a failed .stage delete keeps the build result', () async {
      final source = copyFakeSw(fake, '${work.path}/build', _exe);
      final ops = _Ops({'SPECWRIGHT_UPDATE_COUNT': log}, failRemove: _isStage);
      List<String> stages() =>
          Directory(bin())
              .listSync()
              .map((e) => p.basename(e.path))
              .where((n) => n.endsWith('.stage'))
              .toList();
      final (code, doc) = await run([
        '--code',
        work.path,
        '--download',
        tree(),
        '--build',
        source,
        'sw-install',
      ], fileOps: ops);
      expect(code, 0, reason: '$doc');
      expect(doc['action'], 'installed');
      expect(
        File('${bin()}/$_exe').readAsBytesSync(),
        File(source).readAsBytesSync(),
      );
      expect(ops.refused, hasLength(1));
      expect(stages(), hasLength(1), reason: 'the stage directory remains');
    });

    test('a missing file stops', () async {
      final (code, doc) = await build('${work.path}/none/$_exe');
      expect(code, 1);
      expect(doc['error'], 'sw_check_failed');
      expect(filesUnder(home), isEmpty);
    });

    test('a VERSION that is not MAJOR.MINOR.PATCH stops', () async {
      final source = copyFakeSw(fake, '${work.path}/build', _exe);
      final (code, doc) = await build(source, tree_: tree(version: 'abc'));
      expect(code, 1);
      expect(doc['error'], 'download_version_invalid');
    });

    test('--build without --download is a usage error', () async {
      final source = copyFakeSw(fake, '${work.path}/build', _exe);
      final (code, doc) = await run(['--build', source, 'sw-install']);
      expect(code, 2);
      expect(doc['error'], 'usage');
      expect(filesUnder(home), isEmpty);
    });
  });

  group('a release tag', () {
    late String rel;
    late String dl;
    late List<int> binary;

    setUp(() {
      dl = tree();
      rel = '${work.path}/rel';
      final source = copyFakeSw(fake, '${work.path}/built', _exe);
      binary = File(source).readAsBytesSync();
    });

    /// The mirror's `releases/download/<tag>/` with the host's asset, the
    /// notice and `SHA256SUMS`.
    void release({
      String tag = 'v0.37.0',
      String? hash,
      bool sums = true,
      bool asset = true,
      String? target_,
    }) {
      final target = target_ ?? _hostTarget();
      final dir = Directory('$rel/releases/download/$tag')
        ..createSync(recursive: true);
      if (asset) File('${dir.path}/${_asset(target)}').writeAsBytesSync(binary);
      File('${dir.path}/$_notice').writeAsStringSync(_noticeText);
      if (sums) {
        final lines = [
          for (final t in _targets)
            '${t == target ? (hash ?? _sha(binary)) : _sha(utf8.encode(t))}  '
                '${_asset(t)}',
          '${_sha(utf8.encode(_noticeText))}  $_notice',
        ]..sort((a, b) => a.split('  ')[1].compareTo(b.split('  ')[1]));
        File('${dir.path}/SHA256SUMS')
            .writeAsStringSync('${lines.join('\n')}\n');
      }
    }

    Future<(int, Map<String, Object?>)> install({
      String ref = 'v0.37.0',
      String? mirror,
      Map<String, String> env = const {},
      UpdateFileOps? ops,
    }) => run(
      [
        '--code',
        work.path,
        '--download',
        dl,
        '--ref',
        ref,
        '--release-url',
        mirror ?? Directory(rel).uri.toString(),
        'sw-install',
      ],
      env: env,
      fileOps: ops,
    );

    test(
      'installs the host asset after the hash check, notice first',
      () async {
        release();
        final (code, doc) = await install();
        expect(code, 0, reason: '$doc');
        expect(doc['action'], 'installed');
        expect(doc['asset'], _asset(_hostTarget()));
        expect(doc['version'], '0.37.0');
        expect(doc['ref'], 'v0.37.0');
        expect(doc['path'], '${bin()}/$_exe');
        expect(File('${bin()}/$_exe').readAsBytesSync(), binary);
        expect(File('${bin()}/$_notice').readAsStringSync(), _noticeText);
        final moves = ops().where((l) => l.contains(' mv ')).toList();
        expect(moves.first, contains(_notice), reason: '$moves');
        expect(moves.last, endsWith('${bin()}/$_exe'), reason: '$moves');
        expect(
          Directory(bin()).listSync().length,
          2,
          reason: 'no part file is left',
        );
      },
    );

    test('a rerun keeps the file', () async {
      release();
      await install();
      final (code, doc) = await install();
      expect(code, 0);
      expect(doc['action'], 'kept');
    });

    test('a hash that differs stops before the file runs', () async {
      release(hash: 'f' * 64);
      final (code, doc) = await install();
      expect(code, 1);
      expect(doc['error'], 'checksum_mismatch');
      expect(
        doc['message'],
        allOf(
          contains(_asset(_hostTarget())),
          contains('f' * 64),
          contains(_sha(binary)),
        ),
      );
      expect(filesUnder(home), isEmpty);
    });

    test(
      'a mismatch on a macOS host never reaches the quarantine step',
      () async {
        release(hash: 'f' * 64, target_: 'macos-arm64');
        final (code, doc) = await install(
          env: {'SPECWRIGHT_TEST_HOST': 'Darwin/arm64'},
        );
        expect(code, 1);
        expect(doc['error'], 'checksum_mismatch');
      },
    );

    test('no SHA256SUMS is assets_not_uploaded', () async {
      release(sums: false);
      final (code, doc) = await install();
      expect(code, 1);
      expect(doc['error'], 'assets_not_uploaded');
      expect(doc['message'], contains('v0.37.0'));
    });

    test('a missing host asset is asset_missing', () async {
      release(asset: false);
      final (code, doc) = await install();
      expect(code, 1);
      expect(doc['error'], 'asset_missing');
    });

    test('a tag other than the download VERSION stops', () async {
      release(tag: 'v9.9.9');
      final (code, doc) = await install(ref: 'v9.9.9');
      expect(code, 1);
      expect(doc['error'], 'download_version_invalid');
      expect(doc['message'], allOf(contains('v9.9.9'), contains('0.37.0')));
    });

    test('a host with no target names it and the five targets', () async {
      release();
      final (code, doc) = await install(
        env: {'SPECWRIGHT_TEST_HOST': 'Windows/ARM64'},
      );
      expect(code, 1);
      expect(doc['error'], 'unsupported_platform');
      expect(
        doc['message'],
        allOf(
          contains('Windows'),
          contains('ARM64'),
          contains(_targets.join(', ')),
        ),
      );
      expect(filesUnder(home), isEmpty);
    });

    test('an http release URL is refused before any download', () async {
      release();
      final (code, doc) = await install(mirror: 'http://127.0.0.1:9');
      expect(code, 1);
      expect(doc['error'], 'release_url_not_https');
      expect(filesUnder(home), isEmpty);
    });

    test('SPECWRIGHT_HOME is the root', () async {
      release();
      final other = '$home/../elsewhere';
      Directory(other).createSync();
      final (code, doc) = await install(env: {'SPECWRIGHT_HOME': other});
      expect(code, 0);
      expect(doc['path'], '$other/.specwright/bin/0.37.0/$_exe');
      expect(filesUnder(home), isEmpty);
    });

    test('only old part files are cleaned', () async {
      release();
      Directory(bin()).createSync(recursive: true);
      final old = File('${bin()}/.sw-aaaa.part')..writeAsStringSync('x');
      final fresh = File('${bin()}/.sw-bbbb.part')..writeAsStringSync('x');
      final other = File('${bin()}/notes.txt')..writeAsStringSync('x');
      final twoHours = DateTime.now().subtract(const Duration(hours: 2));
      old.setLastModifiedSync(twoHours);
      other.setLastModifiedSync(twoHours);
      final (code, _) = await install();
      expect(code, 0);
      expect(old.existsSync(), isFalse);
      expect(fresh.existsSync(), isTrue);
      expect(other.existsSync(), isTrue);
    });

    test('main reports skipped and touches nothing under bin', () async {
      Directory(bin('0.36.0')).createSync(recursive: true);
      final previous = File('${bin('0.36.0')}/$_exe')
        ..writeAsStringSync('previous sw');
      final stamp = previous.statSync().modified;
      final (code, doc) = await install(ref: 'main');
      expect(code, 0);
      expect(doc, {
        'ok': true,
        'interface': updateInterface,
        'subcommand': 'sw-install',
        'action': 'skipped',
        'ref': 'main',
        'message': 'sw not installed: main has no release binaries',
      });
      expect(previous.readAsStringSync(), 'previous sw');
      expect(previous.statSync().modified, stamp);
      expect(ops(), isEmpty);
      expect(Directory(bin()).existsSync(), isFalse);
    });

    test('a ref that is no release tag is skipped too', () async {
      final (code, doc) = await install(ref: 'feature');
      expect(code, 0);
      expect(doc['action'], 'skipped');
      expect(doc['message'], 'sw not installed: feature is not a release tag');
    });

    group('a part that cannot be deleted (D8)', () {
      _Ops held() =>
          _Ops({'SPECWRIGHT_UPDATE_COUNT': log}, failRemove: _isPart);

      List<String> parts() =>
          Directory(bin())
              .listSync()
              .map((e) => p.basename(e.path))
              .where(_partName.hasMatch)
              .toList();

      bool hasBinaryPart() => parts().any(
        (n) =>
            n.endsWith(Platform.isWindows ? '.part.exe' : '.part') &&
            !n.contains('.sums.') &&
            !n.contains('.notice.'),
      );

      test('notice_write_failed survives a failed part delete', () async {
        release();
        Directory(bin()).createSync(recursive: true);
        File('${bin()}/$_exe').writeAsStringSync('existing');
        final (code, doc) = await install(
          env: {'SPECWRIGHT_TEST_NOTICE_RENAME': 'fail'},
          ops: held(),
        );
        expect(code, 1);
        expect(doc['error'], 'notice_write_failed');
        expect(File('${bin()}/$_exe').readAsStringSync(), 'existing');
        expect(hasBinaryPart(), isTrue, reason: '${parts()}');
      });

      test('race hook: kept, part left', () async {
        release();
        Directory(bin()).createSync(recursive: true);
        File('${bin()}/$_exe').writeAsStringSync('stale');
        final (code, doc) = await install(
          env: {'SPECWRIGHT_TEST_RENAME': 'race'},
          ops: held(),
        );
        expect(code, 0, reason: '$doc');
        expect(doc['action'], 'kept');
        expect(File('${bin()}/$_exe').readAsBytesSync(), binary);
        expect(hasBinaryPart(), isTrue, reason: '${parts()}');
      });

      test('fail hook: sw_in_use, part left', () async {
        release();
        Directory(bin()).createSync(recursive: true);
        File('${bin()}/$_exe').writeAsStringSync('stale');
        final (code, doc) = await install(
          env: {'SPECWRIGHT_TEST_RENAME': 'fail'},
          ops: held(),
        );
        expect(code, 1);
        expect(doc['error'], 'sw_in_use');
        expect(File('${bin()}/$_exe').readAsStringSync(), 'stale');
        expect(hasBinaryPart(), isTrue, reason: '${parts()}');
      });

      test('checksum mismatch survives a failed part delete', () async {
        release(hash: 'f' * 64);
        final (code, doc) = await install(ops: held());
        expect(code, 1);
        expect(doc['error'], 'checksum_mismatch');
        expect(hasBinaryPart(), isTrue, reason: '${parts()}');
        expect(
          Directory(bin()).listSync().map((e) => p.basename(e.path)),
          everyElement(matches(_partName)),
          reason: 'only part files are left',
        );
      });

      test('deadline_exceeded survives a failed part delete', () async {
        release();
        final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
        addTearDown(() => server.close(force: true));
        server.listen((r) async {
          r.response
            ..bufferOutput = false
            ..headers.contentLength = 100
            ..add(utf8.encode('start'));
          await r.response.flush();
          await Completer<void>().future; // never finishes
        });
        final (code, doc) = await install(
          mirror: 'http://127.0.0.1:${server.port}',
          env: {'SPECWRIGHT_TEST_HTTP': '1', 'SPECWRIGHT_NET_DEADLINE': '1'},
          ops: held(),
        );
        expect(code, 1);
        expect(doc['error'], 'deadline_exceeded', reason: '$doc');
        expect(parts(), hasLength(1), reason: 'the partial download remains');
      });

      test('no SHA256SUMS: assets_not_uploaded, the part left', () async {
        release(sums: false);
        final (code, doc) = await install(ops: held());
        expect(code, 1);
        expect(doc['error'], 'assets_not_uploaded');
        expect(parts(), hasLength(1));
      });

      test('success removes only this run\'s parts', () async {
        release();
        Directory(bin()).createSync(recursive: true);
        File('${bin()}/.sw-bbbb.part').writeAsStringSync('another run');
        File('${bin()}/.sw-bbbb.notice.part').writeAsStringSync('another run');
        final ops = _Ops({'SPECWRIGHT_UPDATE_COUNT': log});
        final (code, doc) = await install(ops: ops);
        expect(code, 0, reason: '$doc');
        expect(
          Directory(bin()).listSync().map((e) => p.basename(e.path)).toList()
            ..sort(),
          ['.sw-bbbb.notice.part', '.sw-bbbb.part', _exe, _notice]..sort(),
        );
      });
    });

    group('the destination on a failed rename (C14)', () {
      Future<Map<String, Object?>> direct({
        required _Ops ops,
        required String Function(String path) hash,
      }) {
        final env = {'SPECWRIGHT_HOME': home, 'SPECWRIGHT_UPDATE_COUNT': log};
        return swInstall(
          parseUpdateOptions([
            '--code',
            work.path,
            '--download',
            dl,
            '--ref',
            'v0.37.0',
            '--release-url',
            Directory(rel).uri.toString(),
            'sw-install',
          ], cwd: work.path),
          environment: env,
          fileOps: ops,
          destinationHash: hash,
        );
      }

      bool isFinal(String to) => p.basename(to) == _exe;

      test('an unreadable final file on recovery is sw_in_use', () async {
        release();
        Directory(bin()).createSync(recursive: true);
        File('${bin()}/$_exe').writeAsStringSync('stale');
        final ops = _Ops({'SPECWRIGHT_UPDATE_COUNT': log}, failRename: isFinal);
        var reads = 0;
        final stop = await _stopOf(
          direct(
            ops: ops,
            hash: (path) {
              if (++reads > 1) {
                throw FileSystemException('injected: unreadable', path);
              }
              return fileSha(path);
            },
          ),
        );
        expect(stop.code, 'sw_in_use');
        expect(reads, 2, reason: 'the first check, then the recovery');
        expect(ops.renamed.where(isFinal), hasLength(1));
      });

      test('a matching hash with the wrong interface is sw_in_use', () async {
        release();
        // the final file reports interface 9; the injected hash says it is
        // the release's file, so only the interface check can refuse it
        copyFakeSw(fakeIface9, bin(), _exe);
        final ops = _Ops({'SPECWRIGHT_UPDATE_COUNT': log}, failRename: isFinal);
        final stop = await _stopOf(
          direct(ops: ops, hash: (path) => _sha(binary)),
        );
        expect(stop.code, 'sw_in_use');
        expect(ops.renamed.where(isFinal), hasLength(1));
      });

      test('a hash that fails on the first check makes no rename', () async {
        release();
        Directory(bin()).createSync(recursive: true);
        File('${bin()}/$_exe').writeAsStringSync('stale');
        final ops = _Ops({'SPECWRIGHT_UPDATE_COUNT': log});
        await expectLater(
          direct(
            ops: ops,
            hash: (path) =>
                throw FileSystemException('injected: unreadable', path),
          ),
          throwsA(isA<FileSystemException>()),
        );
        expect(ops.renamed.where(isFinal), isEmpty);
      });
    });

    group('the version directory (D8)', () {
      test(
        'an uncreatable part is download_failed before any request',
        () async {
          if (!_canDenyAccess) {
            markTestSkipped('needs a non-root POSIX user');
            return;
          }
          release();
          Directory(bin()).createSync(recursive: true);
          addTearDown(() => Process.runSync('chmod', ['755', bin()]));
          Process.runSync('chmod', ['555', bin()]);
          var requests = 0;
          final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
          addTearDown(() => server.close(force: true));
          server.listen((r) async {
            requests++;
            r.response.statusCode = 404;
            await r.response.close();
          });
          final (code, doc) = await install(
            mirror: 'http://127.0.0.1:${server.port}',
            env: {'SPECWRIGHT_TEST_HTTP': '1'},
          );
          expect(code, 1);
          expect(doc['error'], 'download_failed', reason: '$doc');
          expect(doc['message'], contains('.sw-'));
          expect(requests, 0);
        },
      );

      test('an unlistable version directory skips the sweep', () async {
        if (!_canDenyAccess) {
          markTestSkipped('needs a non-root POSIX user');
          return;
        }
        release();
        Directory(bin()).createSync(recursive: true);
        addTearDown(() => Process.runSync('chmod', ['755', bin()]));
        Process.runSync('chmod', ['333', bin()]); // writable, not listable
        final (code, doc) = await install();
        expect(code, 0, reason: '$doc');
        expect(doc['action'], 'installed');
      });
    });

    group('the evals\' test hooks', () {
      List<String> inBin() =>
          Directory(bin()).listSync().map((e) => p.basename(e.path)).toList()
            ..sort();

      test('SPECWRIGHT_TEST_HTTP=1 lets an http mirror stand in', () async {
        release();
        final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
        addTearDown(() => server.close(force: true));
        server.listen((r) async {
          final f = File('$rel${r.uri.path}');
          if (f.existsSync()) {
            r.response.add(f.readAsBytesSync());
          } else {
            r.response.statusCode = 404;
          }
          await r.response.close();
        });
        final mirror = 'http://127.0.0.1:${server.port}';
        final (code, doc) = await install(
          mirror: mirror,
          env: {'SPECWRIGHT_TEST_HTTP': '1'},
        );
        expect(code, 0, reason: '$doc');
        expect(doc['action'], 'installed');
        expect(File('${bin()}/$_exe').readAsBytesSync(), binary);
        // without the variable the same mirror is refused
        final (refused, refusal) = await install(mirror: mirror);
        expect(refused, 1);
        expect(refusal['error'], 'release_url_not_https');
      });

      test('under the hook a redirect must still be https', () async {
        release();
        final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
        addTearDown(() => server.close(force: true));
        server.listen((r) async {
          r.response
            ..statusCode = 302
            ..headers.set('location', 'http://127.0.0.1:9/elsewhere');
          await r.response.close();
        });
        final (code, doc) = await install(
          mirror: 'http://127.0.0.1:${server.port}',
          env: {'SPECWRIGHT_TEST_HTTP': '1'},
        );
        expect(code, 1);
        expect(doc['error'], 'download_failed');
        expect(doc['message'], contains('redirect'));
      });

      test(
        'RENAME=die ends with 9 after the notice, before the binary',
        () async {
          release();
          var died = -1;
          await expectLater(
            run(
              [
                '--code',
                work.path,
                '--download',
                dl,
                '--ref',
                'v0.37.0',
                '--release-url',
                Directory(rel).uri.toString(),
                'sw-install',
              ],
              env: {'SPECWRIGHT_TEST_RENAME': 'die'},
              exitProcess: (c) {
                died = c;
                throw StateError('died');
              },
            ),
            throwsStateError,
          );
          expect(died, 9);
          expect(File('${bin()}/$_exe').existsSync(), isFalse);
          expect(File('${bin()}/$_notice').readAsStringSync(), _noticeText);
          final (code, doc) = await install();
          expect(code, 0);
          expect(doc['action'], 'installed');
        },
      );

      test('RENAME=fail with another file there is sw_in_use', () async {
        release();
        Directory(bin()).createSync(recursive: true);
        File('${bin()}/$_exe').writeAsStringSync('stale');
        final (code, doc) = await install(
          env: {'SPECWRIGHT_TEST_RENAME': 'fail'},
        );
        expect(code, 1);
        expect(doc['error'], 'sw_in_use');
        expect(doc['message'], contains(_exe));
        expect(File('${bin()}/$_exe').readAsStringSync(), 'stale');
        expect(inBin(), [_exe, _notice]..sort());
      });

      test('RENAME=race with another run\'s file is kept', () async {
        release();
        Directory(bin()).createSync(recursive: true);
        File('${bin()}/$_exe').writeAsStringSync('stale');
        final (code, doc) = await install(
          env: {'SPECWRIGHT_TEST_RENAME': 'race'},
        );
        expect(code, 0, reason: '$doc');
        expect(doc['action'], 'kept');
        expect(File('${bin()}/$_exe').readAsBytesSync(), binary);
        expect(inBin(), [_exe, _notice]..sort(), reason: 'the part is gone');
      });

      test('NOTICE_RENAME=fail stops and keeps the existing binary', () async {
        release();
        Directory(bin()).createSync(recursive: true);
        File('${bin()}/$_exe').writeAsStringSync('existing');
        final (code, doc) = await install(
          env: {'SPECWRIGHT_TEST_NOTICE_RENAME': 'fail'},
        );
        expect(code, 1);
        expect(doc['error'], 'notice_write_failed');
        expect(doc['message'], allOf(contains(_notice), contains('v0.37.0')));
        expect(File('${bin()}/$_exe').readAsStringSync(), 'existing');
        expect(inBin(), [_exe]);
      });

      test('NOTICE_RENAME=race counts as success', () async {
        release();
        final (code, doc) = await install(
          env: {'SPECWRIGHT_TEST_NOTICE_RENAME': 'race'},
        );
        expect(code, 0, reason: '$doc');
        expect(File('${bin()}/$_notice').readAsStringSync(), _noticeText);
      });
    });
  });
}
