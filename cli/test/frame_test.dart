import 'dart:convert';

import 'package:specwright_cli/src/process/frame.dart';
import 'package:test/test.dart';

List<int> bytes(String s) => latin1.encode(s);

void main() {
  test('an ok frame is consumed and nothing is returned', () {
    final parser = ReadyFrameParser();
    expect(parser.add(bytes('\x00sw-ready ok\n')), isEmpty);
    expect(parser.state, FrameState.ready);
    expect(parser.frame!.hasJob, isTrue);
  });

  test('a nojob frame carries its reason', () {
    final parser = ReadyFrameParser();
    parser.add(bytes('\x00sw-ready nojob access denied\n'));
    expect(parser.state, FrameState.ready);
    expect(parser.frame!.jobReason, 'access denied');
  });

  test('a frame split across chunks is assembled', () {
    final parser = ReadyFrameParser();
    final whole = bytes('\x00sw-ready ok\n');
    for (var i = 0; i < whole.length - 1; i++) {
      expect(parser.add([whole[i]]), isEmpty);
      expect(parser.state, FrameState.pending);
    }
    expect(parser.add([whole.last]), isEmpty);
    expect(parser.state, FrameState.ready);
  });

  test('bytes after the frame in the same chunk are returned', () {
    final parser = ReadyFrameParser();
    final rest = parser.add(bytes('\x00sw-ready ok\nhello err'));
    expect(latin1.decode(rest), 'hello err');
    // later chunks pass through untouched
    expect(latin1.decode(parser.add(bytes('more'))), 'more');
  });

  test('the frame it encodes is the frame it parses', () {
    for (final frame in [
      const ReadyFrame.ok(),
      const ReadyFrame.noJob('SPECWRIGHT_TEST_NO_JOB is set'),
    ]) {
      final parser = ReadyFrameParser()..add(frame.encode());
      expect(parser.state, FrameState.ready);
      expect(parser.frame!.jobReason, frame.jobReason);
    }
  });

  test('text that is not a frame is malformed', () {
    final parser = ReadyFrameParser();
    expect(parser.add(bytes('hello from another binary\n')), isEmpty);
    expect(parser.state, FrameState.malformed);
    expect(parser.received, startsWith('h'));
    expect(parser.add(bytes('more')), isEmpty);
  });

  test('an unknown frame kind is malformed', () {
    final parser = ReadyFrameParser()..add(bytes('\x00sw-ready later\n'));
    expect(parser.state, FrameState.malformed);
  });

  test('a stream that ends with no frame is missing the frame', () {
    final parser = ReadyFrameParser()..close();
    expect(parser.state, FrameState.malformed);
    expect(parser.problem, 'no ready frame');
  });

  test('a stream that ends inside the frame is malformed', () {
    final parser = ReadyFrameParser()..add(bytes('\x00sw-rea'));
    expect(parser.state, FrameState.pending);
    parser.close();
    expect(parser.state, FrameState.malformed);
  });

  test('a frame that never ends is cut off', () {
    final parser = ReadyFrameParser()..add(bytes('\x00sw-ready ${'x' * 2000}'));
    expect(parser.state, FrameState.malformed);
  });

  test('close after a good frame changes nothing', () {
    final parser = ReadyFrameParser()..add(bytes('\x00sw-ready ok\n'));
    parser.close();
    expect(parser.state, FrameState.ready);
  });
}
