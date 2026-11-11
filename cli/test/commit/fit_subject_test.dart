import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/commit/context.dart';
import 'package:specwright_cli/src/commit/fit_subject.dart';
import 'package:test/test.dart';

/// The bash a Windows shim hands over; its Git root is `C:\Program Files\Git`.
const String _gitBash = r'C:\Program Files\Git\usr\bin\bash.exe';

class _Run {
  _Run(this.code, this.out, this.err);

  final int code;
  final List<int> out;
  final List<int> err;

  String get outText => utf8.decode(out, allowMalformed: true);
  String get errText => utf8.decode(err, allowMalformed: true);
}

void main() {
  late Directory dir;
  late String msg;
  setUp(() {
    dir = Directory.systemTemp.createTempSync('claude-ncc-g4-fit-');
    msg = '${dir.path}/m.txt'.replaceAll(r'\', '/');
  });
  tearDown(() => dir.deleteSync(recursive: true));

  Future<_Run> run(
    List<String> args, {
    bool? windows,
    Map<String, String>? environment,
    bool entry = false,
    String bash = _gitBash,
  }) async {
    final out = BytesBuilder();
    final err = BytesBuilder();
    final ctx = CommitContext(
      scriptsDir: dir.path,
      bash: bash,
      writeOut: out.add,
      writeErr: err.add,
    );
    final code = entry
        ? await runFitSubject(args, ctx)
        : await fitSubject(
            args,
            ctx,
            windows: windows,
            environment: environment,
          );
    return _Run(code, out.toBytes(), err.toBytes());
  }

  Future<_Run> fit(List<int> content) async {
    File(msg).writeAsBytesSync(content);
    return run([msg]);
  }

  List<int> bytesOf(String s) => utf8.encode(s);
  List<int> file() => File(msg).readAsBytesSync();
  List<String> names() =>
      dir
          .listSync()
          .map((e) => e.path.replaceAll(r'\', '/').split('/').last)
          .toList()
        ..sort();

  const prefix = 'feat(x): task 1.2 ';
  const fiveWords =
      'aaaaaaaaaa bbbbbbbbbb cccccccccc dddddddddd eeeeeeeeee'; // 54
  const fitted = '$prefix$fiveWords'; // 72

  group('fitSubject: what fits', () {
    test('a subject within 72 characters leaves the file untouched', () async {
      final content = bytesOf('$fitted\n\nbody line\n');
      final r = await fit(content);
      expect(r.code, 0);
      expect(r.outText, '$fitted\n');
      expect(r.err, isEmpty);
      expect(file(), content);
      expect(names(), ['m.txt']);
    });

    test('multi-byte subject within 72 characters is untouched', () async {
      final subject = '$prefix${'é' * 54}'; // 72 characters, 126 bytes
      expect(subject.runes.length, 72);
      expect(utf8.encode(subject).length, greaterThan(72));
      final content = bytesOf('$subject\nbody\n');
      final r = await fit(content);
      expect(r.code, 0);
      expect(r.out, [...utf8.encode(subject), 0x0a]);
      expect(r.err, isEmpty);
      expect(file(), content);
    });

    test('bytes 0x80-0xBF are not counted, whatever follows', () async {
      // 72 ASCII characters plus five lone continuation bytes.
      final content = [...bytesOf(fitted), 0x80, 0x81, 0xbf, 0x90, 0xa0, 0x0a];
      final r = await fit(content);
      expect(r.code, 0);
      expect(r.out, [...content.sublist(0, content.length - 1), 0x0a]);
      expect(file(), content);
    });

    test('a byte outside 0x80-0xBF counts as one', () async {
      // 0xC3 and 0xFF each count: 73 characters, so the last word goes.
      final content = [...bytesOf('$fitted '), 0xc3, 0xff, 0x0a];
      final r = await fit(content);
      expect(r.code, 0);
      expect(r.outText, '$fitted\n');
      expect(file(), [...bytesOf(fitted), 0x0a]);
    });
  });

  group('fitSubject: the cut', () {
    test('a task subject is cut to the longest run of whole words', () async {
      const longer = '$fitted ffffffffff';
      final r = await fit(bytesOf('$longer\nbody\n'));
      expect(r.code, 0);
      expect(r.outText, '$fitted\n');
      expect(r.err, isEmpty);
      expect(file(), bytesOf('$fitted\nbody\n'));
      expect(names(), ['m.txt']);
    });

    test('a group subject is cut the same way', () async {
      const gp = 'docs(y): group 12 ';
      final r = await fit(bytesOf('$gp$fiveWords ffffffffff\n'));
      expect(r.code, 0);
      expect(r.outText, '$gp$fiveWords\n');
      expect(file(), bytesOf('$gp$fiveWords\n'));
    });

    test('spaces before the cut are removed', () async {
      final r = await fit(bytesOf('$fitted  ffffffffff\n'));
      expect(r.code, 0);
      expect(r.outText, '$fitted\n');
      expect(file(), bytesOf('$fitted\n'));
    });

    test('a shorter fit is taken when the last word does not fit', () async {
      final r = await fit(
        bytesOf('${prefix}aaaaaaaaaa bbbbbbbbbb ${'c' * 70}\n'),
      );
      expect(r.code, 0);
      expect(r.outText, '${prefix}aaaaaaaaaa bbbbbbbbbb\n');
    });

    test('only 0x20 cuts: a tab or a no-break space does not', () async {
      final tab = '$prefix${'a' * 30}\t${'b' * 30}';
      final r = await fit(bytesOf('$tab\n'));
      expect(r.code, 1);
      expect(
        r.errText,
        'fit-subject.sh: no word of the task or group text fits in 72 '
        'characters: $tab\n',
      );
      final nbsp = '$prefix${'a' * 30}\u00a0${'b' * 30}';
      final r2 = await fit(bytesOf('$nbsp\n'));
      expect(r2.code, 1);
    });

    test('invalid UTF-8 bytes in line 1 and later are kept', () async {
      final content = [
        ...bytesOf('${prefix}aaaa '),
        0xff,
        0xfe,
        ...bytesOf(' ${'b' * 70}\n'),
        0xc3,
        0x28,
        0x0a,
        0xff,
      ];
      final r = await fit(content);
      expect(r.code, 0);
      final expected = [...bytesOf('${prefix}aaaa '), 0xff, 0xfe];
      expect(r.out, [...expected, 0x0a]);
      expect(file(), [...expected, 0x0a, 0xc3, 0x28, 0x0a, 0xff]);
    });
  });

  group('fitSubject: line endings and the end of the file', () {
    test('CRLF file keeps its CRs', () async {
      final content = bytesOf('$fitted ffffffffff\r\n\r\nbody\r\nmore\r\n');
      final r = await fit(content);
      expect(r.code, 0);
      expect(r.outText, '$fitted\n');
      expect(file(), bytesOf('$fitted\r\n\r\nbody\r\nmore\r\n'));
    });

    test(
      'a CR at the end of a fitting line 1 leaves the file untouched',
      () async {
        final content = bytesOf('$fitted\r\nbody\r\n');
        final r = await fit(content);
        expect(r.code, 0);
        expect(r.outText, '$fitted\n');
        expect(file(), content);
      },
    );

    test('a file with no newline stays without one', () async {
      final r = await fit(bytesOf('$fitted ffffffffff'));
      expect(r.code, 0);
      expect(r.outText, '$fitted\n');
      expect(file(), bytesOf(fitted));
    });

    test('a file with no newline and a final CR keeps the CR', () async {
      final r = await fit(bytesOf('$fitted ffffffffff\r'));
      expect(r.code, 0);
      expect(file(), bytesOf('$fitted\r'));
    });

    test('the temporary file is gone after a rewrite', () async {
      await fit(bytesOf('$fitted ffffffffff\nbody\n'));
      expect(names(), ['m.txt']);
    });
  });

  group('fitSubject: exits 1 and 2', () {
    test('exit 1 when not even the first word fits', () async {
      final line = '$prefix${'a' * 60} b';
      final content = bytesOf('$line\nbody\n');
      final r = await fit(content);
      expect(r.code, 1);
      expect(r.out, isEmpty);
      expect(
        r.errText,
        'fit-subject.sh: no word of the task or group text fits in 72 '
        'characters: $line\n',
      );
      expect(file(), content);
    });

    test('exit 1 prints line 1 without its CR', () async {
      final line = '$prefix${'a' * 60}';
      final r = await fit(bytesOf('$line\r\nbody\r\n'));
      expect(r.code, 1);
      expect(
        r.errText,
        'fit-subject.sh: no word of the task or group text fits in 72 '
        'characters: $line\n',
      );
    });

    const shape =
        "fit-subject.sh: line 1 is not '<type>(<scope>): task X.Y <task "
        "text>' or '<type>(<scope>): group N <group heading>': ";

    test('exit 2 when line 1 has no task or group prefix', () async {
      final content = bytesOf('feat(x): just a subject\nbody\n');
      final r = await fit(content);
      expect(r.code, 2);
      expect(r.out, isEmpty);
      expect(r.errText, '${shape}feat(x): just a subject\n');
      expect(file(), content);
    });

    test('exit 2 for non-ASCII digits in the prefix', () async {
      for (final line in [
        'feat(x): task ٣.٢ text',
        'feat(x): task １.２ text',
        'feat(x): group ٣ text',
      ]) {
        final content = bytesOf('$line\n');
        final r = await fit(content);
        expect(r.code, 2, reason: line);
        expect(r.errText, '$shape$line\n', reason: line);
        expect(file(), content);
      }
    });

    test('exit 2 for a prefix without the space after the number', () async {
      final r = await fit(bytesOf('feat(x): task 1.2\n'));
      expect(r.code, 2);
      final r2 = await fit(bytesOf('feat(x): group 3\n'));
      expect(r2.code, 2);
    });

    test('exit 2 for an empty file', () async {
      final r = await fit(<int>[]);
      expect(r.code, 2);
      expect(r.errText, '$shape\n');
    });

    test('exit 2 for a missing file', () async {
      final r = await run([msg]);
      expect(r.code, 2);
      expect(r.out, isEmpty);
      expect(r.errText, "fit-subject.sh: no message file: '$msg'\n");
    });

    test('exit 2 for a directory, no argument and an empty argument', () async {
      final r = await run([dir.path]);
      expect(r.code, 2);
      expect(r.errText, "fit-subject.sh: no message file: '${dir.path}'\n");
      final r2 = await run([]);
      expect(r2.code, 2);
      expect(r2.errText, "fit-subject.sh: no message file: ''\n");
      final r3 = await run(['']);
      expect(r3.code, 2);
      expect(r3.errText, "fit-subject.sh: no message file: ''\n");
    });

    test('extra arguments are ignored', () async {
      File(msg).writeAsBytesSync(bytesOf('$fitted ffffffffff\n'));
      final r = await run([msg, 'extra']);
      expect(r.code, 0);
      expect(file(), bytesOf('$fitted\n'));
    });

    test('an unexpected failure is one stderr line and exit 2', () async {
      // A lone surrogate cannot be turned into a path.
      final r = await run(['\ud800'], entry: true);
      expect(r.code, 2);
      expect(r.out, isEmpty);
      expect(r.errText, startsWith('fit-subject.sh: '));
      expect(r.errText.trimRight().contains('\n'), isFalse);
      expect(r.errText.endsWith('\n'), isTrue);
    });
  });

  group('fitSubject: failures leave the file alone', () {
    test('failed temp write leaves the file and no temp', () async {
      final content = bytesOf('$fitted ffffffffff\nbody\r\n');
      File(msg).writeAsBytesSync(content);
      // A directory where the temporary file belongs makes its write fail.
      final tmp = Directory('$msg.fit.$pid')..createSync();
      final r = await run([msg]);
      expect(r.code, 2);
      expect(r.out, isEmpty);
      expect(r.errText, 'fit-subject.sh: could not rewrite $msg\n');
      expect(file(), content);
      expect(FileSystemEntity.isFileSync(tmp.path), isFalse);
      expect(names(), ['m.txt', 'm.txt.fit.$pid']);
    });

    test(
      'a path that does not convert gives exit 2 and touches nothing',
      () async {
        final content = bytesOf('$fitted ffffffffff\nbody\n');
        File(msg).writeAsBytesSync(content);
        final before = names();
        // a bash path that holds no Git root: /etc/m.txt has nowhere to go
        final r = await run(
          ['/etc/m.txt'],
          windows: true,
          bash: r'C:\tools\bash.exe',
        );
        expect(r.code, 2);
        expect(r.out, isEmpty);
        expect(
          r.errText,
          'fit-subject.sh: could not convert path: /etc/m.txt\n',
        );
        expect(file(), content);
        expect(names(), before);
      },
    );

    test('/tmp/m.txt on Windows is fitted under TEMP', () async {
      File(msg).writeAsBytesSync(bytesOf('$fitted ffffffffff\nbody\n'));
      final r = await run(
        ['/tmp/m.txt'],
        windows: true,
        environment: {'TEMP': dir.path},
      );
      expect(r.code, 0, reason: r.errText);
      expect(file(), bytesOf('$fitted\nbody\n'));
    });

    test('/tmp/m.txt on Windows with no TEMP or TMP gives exit 2', () async {
      final r = await run(['/tmp/m.txt'], windows: true, environment: {});
      expect(r.code, 2);
      expect(r.errText, 'fit-subject.sh: could not convert path: /tmp/m.txt\n');
    });
  });
}
