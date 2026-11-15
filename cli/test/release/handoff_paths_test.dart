// Tests of the release handoff's path conversion (nativeReleaseArgs in
// cli/lib/src/commands/release.dart): the stdin handoff skips Git Bash's own
// argument conversion, so sw converts each path option's value itself.
import 'package:specwright_cli/src/commands/release.dart';
import 'package:specwright_cli/src/commit/paths.dart';
import 'package:test/test.dart';

const bash = r'C:\Program Files\Git\usr\bin\bash.exe';

Future<List<String>> convert(List<String> argv, {bool windows = true}) =>
    nativeReleaseArgs(argv, bash, windows: windows, environment: const {});

void main() {
  test('converts --dir, --store and --proposal values on Windows', () async {
    expect(
      await convert(['--dir', '/f/Dev/app', 'status', '--store', '/f/plans']),
      ['--dir', 'F:/Dev/app', 'status', '--store', 'F:/plans'],
    );
    expect(await convert(['notes', '--proposal', '/c/x/proposal.md']), [
      'notes',
      '--proposal',
      'C:/x/proposal.md',
    ]);
  });

  test('leaves other options, drive forms and relative paths alone', () async {
    final argv = [
      'publish',
      '--main',
      '/c/not-a-path',
      '--store',
      'D:/plans',
      '--store-prefix',
      '/c/prefix',
      '--version',
      '1.0.0',
    ];
    expect(await convert(argv), argv);
    expect(await convert(['notes', '--proposal', 'p.md']), [
      'notes',
      '--proposal',
      'p.md',
    ]);
  });

  test('changes nothing off Windows', () async {
    final argv = ['--dir', '/f/Dev/app', 'check'];
    expect(await convert(argv, windows: false), argv);
  });

  test('an unconvertible path throws', () async {
    expect(
      () => convert(['notes', '--proposal', '/tmp/p.md']),
      throwsA(isA<BadPathException>()),
    );
  });
}
