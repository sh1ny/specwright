import 'dart:convert';

import 'package:specwright_cli/src/process/frame.dart';
import 'package:test/test.dart';

List<int> bytes(String s) => latin1.encode(s);

const _hello = '\x00sw-hello 133800000000000000\n';
const _ready = '\x00sw-ready ok\n';

void main() {
  test('the hello then the ready frame are consumed, nothing is returned', () {
    final parser = FrameParser();
    expect(parser.add(bytes(_hello)), isEmpty);
    expect(parser.state, FrameState.awaitingReady);
    expect(parser.hello!.id, '133800000000000000');
    expect(parser.hello!.creationTime, 133800000000000000);
    expect(parser.add(bytes(_ready)), isEmpty);
    expect(parser.state, FrameState.ready);
    expect(parser.ready!.hasJob, isTrue);
  });

  test('a hello with no creation time is a dash', () {
    final parser = FrameParser()..add(bytes('\x00sw-hello -\n'));
    expect(parser.state, FrameState.awaitingReady);
    expect(parser.hello!.creationTime, isNull);
  });

  test('a nojob frame carries its reason', () {
    final parser = FrameParser()
      ..add(bytes('$_hello\x00sw-ready nojob access denied\n'));
    expect(parser.state, FrameState.ready);
    expect(parser.ready!.jobReason, 'access denied');
  });

  test('frames split across chunks are assembled', () {
    final parser = FrameParser();
    final whole = bytes(_hello + _ready);
    for (var i = 0; i < whole.length - 1; i++) {
      expect(parser.add([whole[i]]), isEmpty);
      expect(parser.state, isNot(FrameState.ready));
      expect(parser.state, isNot(FrameState.malformed));
    }
    expect(parser.add([whole.last]), isEmpty);
    expect(parser.state, FrameState.ready);
  });

  test('the hello is available before the ready frame arrives', () {
    final parser = FrameParser()..add(bytes('$_hello\x00sw-rea'));
    expect(parser.hello, isNotNull);
    expect(parser.ready, isNull);
    expect(parser.state, FrameState.awaitingReady);
  });

  test('bytes after the frames in the same chunk are returned', () {
    final parser = FrameParser();
    final rest = parser.add(
      bytes(
        '$_hello$_ready'
        'hello err',
      ),
    );
    expect(latin1.decode(rest), 'hello err');
    // later chunks pass through untouched
    expect(latin1.decode(parser.add(bytes('more'))), 'more');
  });

  test('the frames it encodes are the frames it parses', () {
    for (final frame in [
      const ReadyFrame.ok(),
      const ReadyFrame.noJob('setsid failed'),
    ]) {
      final parser = FrameParser()
        ..add(const HelloFrame('42').encode())
        ..add(frame.encode());
      expect(parser.state, FrameState.ready);
      expect(parser.hello!.id, '42');
      expect(parser.ready!.jobReason, frame.jobReason);
    }
  });

  test('text that is not a hello frame is malformed', () {
    final parser = FrameParser();
    expect(parser.add(bytes('hello from another binary\n')), isEmpty);
    expect(parser.state, FrameState.malformed);
    expect(parser.hello, isNull);
    expect(parser.received, startsWith('h'));
    expect(parser.add(bytes('more')), isEmpty);
  });

  test('a ready frame in place of the hello is malformed', () {
    final parser = FrameParser()..add(bytes(_ready));
    expect(parser.state, FrameState.malformed);
  });

  test('a hello id that is not a number or a dash is malformed', () {
    final parser = FrameParser()..add(bytes('\x00sw-hello later\n'));
    expect(parser.state, FrameState.malformed);
  });

  test('an unknown ready kind is malformed, the hello stays', () {
    final parser = FrameParser()..add(bytes('$_hello\x00sw-ready later\n'));
    expect(parser.state, FrameState.malformed);
    expect(parser.hello, isNotNull);
  });

  test('a stream that ends with no frame is missing the hello', () {
    final parser = FrameParser()..close();
    expect(parser.state, FrameState.malformed);
    expect(parser.problem, 'no hello frame');
  });

  test('a stream that ends after the hello is missing the ready frame', () {
    final parser = FrameParser()
      ..add(bytes(_hello))
      ..close();
    expect(parser.state, FrameState.malformed);
    expect(parser.problem, 'no ready frame');
    expect(parser.hello, isNotNull);
  });

  test('a stream that ends inside a frame is malformed', () {
    final parser = FrameParser()..add(bytes('\x00sw-hel'));
    expect(parser.state, FrameState.awaitingHello);
    parser.close();
    expect(parser.state, FrameState.malformed);
  });

  test('a frame that never ends is cut off', () {
    final parser = FrameParser()
      ..add(bytes('$_hello\x00sw-ready ${'x' * 2000}'));
    expect(parser.state, FrameState.malformed);
  });

  test('close after good frames changes nothing', () {
    final parser = FrameParser()..add(bytes(_hello + _ready));
    parser.close();
    expect(parser.state, FrameState.ready);
  });
}
