import 'package:specwright_cli/src/process/limit_line.dart';
import 'package:test/test.dart';

void main() {
  String line(BoundedLimit limit, List<String> cmd, {bool windows = false}) =>
      limitLine(limit, cmd, windows: windows);

  test('names the command and its first argument', () {
    expect(
      line(BoundedLimit.deadlineExceeded, ['git', 'fetch', 'origin']),
      'bounded: deadline_exceeded: git fetch\n',
    );
    expect(
      line(BoundedLimit.responseTooLarge, ['gh']),
      'bounded: response_too_large: gh\n',
    );
  });

  test('exit codes are 124 and 125', () {
    expect(BoundedLimit.deadlineExceeded.exitCode, 124);
    expect(BoundedLimit.responseTooLarge.exitCode, 125);
  });

  test('a shell wrapper names the wrapped command', () {
    for (final shell in ['bash', 'sh', '/usr/bin/bash', '/bin/sh']) {
      expect(
        line(BoundedLimit.deadlineExceeded, [
          shell,
          '-c',
          r'exec gh "$@"',
          'gh',
          'api',
          'user',
        ]),
        'bounded: deadline_exceeded: gh api\n',
        reason: shell,
      );
    }
  });

  test('a shell wrapper with one wrapped word names just it', () {
    expect(
      line(BoundedLimit.deadlineExceeded, ['bash', '-c', 'sleep 9', 'gh']),
      'bounded: deadline_exceeded: gh\n',
    );
  });

  test('a shell with three or fewer arguments names itself', () {
    expect(
      line(BoundedLimit.deadlineExceeded, ['bash', '-c', 'sleep 9']),
      'bounded: deadline_exceeded: bash -c\n',
    );
  });

  test('a shell without -c names itself', () {
    expect(
      line(BoundedLimit.deadlineExceeded, ['bash', 'script.sh', 'a', 'b']),
      'bounded: deadline_exceeded: bash script.sh\n',
    );
  });

  test('Windows paths and extensions are recognised', () {
    expect(
      line(BoundedLimit.deadlineExceeded, [
        r'C:\Program Files\Git\usr\bin\BASH.EXE',
        '-c',
        'sleep 9',
        'gh',
        'api',
      ], windows: true),
      'bounded: deadline_exceeded: gh api\n',
    );
  });
}
