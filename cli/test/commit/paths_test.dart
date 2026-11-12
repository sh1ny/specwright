import 'package:specwright_cli/src/commit/paths.dart';
import 'package:test/test.dart';

/// The bash a Windows shim hands over, in its Windows form (`cygpath -w "$BASH"`).
const String _bash = r'C:\Program Files\Git\usr\bin\bash.exe';
const Map<String, String> _temp = {
  'TEMP': r'C:\Users\x\AppData\Local\Temp',
  'PATH': r'C:\nowhere',
};

void main() {
  Future<String> convert(
    String path, {
    String bash = _bash,
    Map<String, String> environment = _temp,
    bool windows = true,
  }) => nativePath(path, bash, windows: windows, environment: environment);

  Matcher badPath(String path) =>
      throwsA(isA<BadPathException>().having((e) => e.path, 'path', path));

  group('nativePath: drive and UNC forms (D7)', () {
    test('drive and UNC MSYS paths convert without cygpath', () async {
      expect(await convert('/c/Users/x/m.txt'), 'C:/Users/x/m.txt');
      expect(await convert('/D/work/m.txt'), 'D:/work/m.txt');
      expect(await convert('/c'), 'C:/');
      expect(await convert('/c/'), 'C:/');
      expect(await convert('//server/share/m.txt'), '//server/share/m.txt');
    });

    test('a drive-form or relative path is returned as it is', () async {
      expect(await convert('C:/x/m.txt'), 'C:/x/m.txt');
      expect(await convert(r'C:\x\m.txt'), r'C:\x\m.txt');
      expect(await convert('m.txt'), 'm.txt');
      expect(await convert('./a/m.txt'), './a/m.txt');
    });

    test('a POSIX path off Windows is returned as it is', () async {
      expect(await convert('/tmp/m.txt', windows: false), '/tmp/m.txt');
      expect(await convert('/etc/m.txt', windows: false), '/etc/m.txt');
    });
  });

  group('nativePath: /tmp (D7)', () {
    test('/tmp maps under TEMP', () async {
      expect(
        await convert('/tmp/m.txt'),
        'C:/Users/x/AppData/Local/Temp/m.txt',
      );
      expect(await convert('/tmp'), 'C:/Users/x/AppData/Local/Temp');
      expect(await convert('/tmp/a/b/m.txt'), endsWith('/Temp/a/b/m.txt'));
    });

    test('a trailing separator on TEMP does not double', () async {
      expect(
        await convert('/tmp/m.txt', environment: {'TEMP': r'C:\Users\x\Temp\'}),
        'C:/Users/x/Temp/m.txt',
      );
    });

    test('TMP is used when TEMP is not set or empty', () async {
      expect(
        await convert('/tmp/m.txt', environment: {'TMP': r'D:\tmp'}),
        'D:/tmp/m.txt',
      );
      expect(
        await convert(
          '/tmp/m.txt',
          environment: {'TEMP': '', 'TMP': r'D:\tmp'},
        ),
        'D:/tmp/m.txt',
      );
    });

    test('/tmp without TEMP or TMP is bad_path', () async {
      await expectLater(
        convert('/tmp/m.txt', environment: {'PATH': r'C:\nowhere'}),
        badPath('/tmp/m.txt'),
      );
      await expectLater(
        convert('/tmp/m.txt', environment: {'TEMP': '', 'TMP': ''}),
        badPath('/tmp/m.txt'),
      );
    });

    test('/tmpfile is not /tmp: it goes under the Git root', () async {
      expect(await convert('/tmpfile'), 'C:/Program Files/Git/tmpfile');
    });
  });

  group('nativePath: under the Git root (D7)', () {
    test('the root comes from ...\\usr\\bin\\bash.exe', () async {
      expect(
        await convert(
          '/etc/m.txt',
          bash: r'C:\Program Files\Git\usr\bin\bash.exe',
        ),
        'C:/Program Files/Git/etc/m.txt',
      );
      expect(
        await convert(
          '/etc/m.txt',
          bash: 'C:/Program Files/Git/usr/bin/bash.exe',
        ),
        'C:/Program Files/Git/etc/m.txt',
      );
    });

    test('the root comes from ...\\bin\\bash.exe', () async {
      expect(
        await convert('/etc/m.txt', bash: r'C:\Program Files\Git\bin\bash.exe'),
        'C:/Program Files/Git/etc/m.txt',
      );
    });

    test('the suffix is matched without regard to case', () async {
      expect(
        await convert('/usr/share/x', bash: r'D:\GIT\BIN\BASH.EXE'),
        'D:/GIT/usr/share/x',
      );
    });

    test(
      'a bash path that holds no Git root makes /etc/m.txt bad_path',
      () async {
        for (final bash in [
          r'C:\tools\bash.exe',
          '/usr/bin/bash',
          '',
          r'C:\Program Files\Git\mingw64\bin\git.exe',
        ]) {
          await expectLater(
            convert('/etc/m.txt', bash: bash),
            badPath('/etc/m.txt'),
          );
        }
      },
    );

    test('//host with no share is bad_path', () async {
      await expectLater(convert('//'), badPath('//'));
      await expectLater(convert('///x'), badPath('///x'));
    });
  });
}
