import 'dart:convert';
import 'dart:typed_data';

/// The ready frame the helper writes as the first bytes of its stderr, before
/// it starts the command: `\x00sw-ready ok\n` or
/// `\x00sw-ready nojob <reason>\n`. The NUL prefix keeps it from matching any
/// text a command could have written, since the command has not started yet.
class ReadyFrame {
  const ReadyFrame.ok() : jobReason = null;
  const ReadyFrame.noJob(String this.jobReason);

  /// Null when containment succeeded; the reason when it did not.
  final String? jobReason;

  bool get hasJob => jobReason == null;

  /// The bytes the helper writes.
  List<int> encode() => utf8.encode(
    hasJob
        ? '\x00sw-ready ok\n'
        : '\x00sw-ready nojob ${_oneLine(jobReason!)}\n',
  );

  static String _oneLine(String s) => s.replaceAll(RegExp(r'[\r\n\x00]+'), ' ');
}

enum FrameState { pending, ready, malformed }

/// Reads the ready frame off the front of the helper's stderr.
///
/// [add] consumes the frame bytes and returns the bytes after the frame, which
/// belong to the command's stderr. Bytes of the frame are never returned, so
/// they are neither counted nor passed on.
class ReadyFrameParser {
  static const _prefix = '\x00sw-ready ';
  static const _maxLength = 1024;

  final List<int> _buffer = [];
  FrameState _state = FrameState.pending;
  ReadyFrame? _frame;
  String? _problem;

  FrameState get state => _state;

  /// The parsed frame once [state] is [FrameState.ready].
  ReadyFrame? get frame => _frame;

  /// Why the frame is malformed once [state] is [FrameState.malformed].
  String? get problem => _problem;

  /// What was read of a malformed frame, printable, for the reason line.
  String get received => latin1
      .decode(_buffer.take(120).toList(), allowInvalid: true)
      .replaceAll(RegExp(r'[^\x20-\x7e]'), '?');

  List<int> add(List<int> chunk) {
    if (_state == FrameState.ready) return chunk;
    if (_state == FrameState.malformed) return const [];
    var consumed = 0;
    while (consumed < chunk.length) {
      final byte = chunk[consumed++];
      _buffer.add(byte);
      if (_buffer.length <= _prefix.length) {
        if (byte != _prefix.codeUnitAt(_buffer.length - 1)) {
          return _fail('not a ready frame');
        }
      } else if (byte == 0x0a) {
        _finish();
        if (_state != FrameState.ready) return const [];
        final bytes = chunk is Uint8List ? chunk : Uint8List.fromList(chunk);
        return Uint8List.sublistView(bytes, consumed);
      } else if (_buffer.length > _maxLength) {
        return _fail('ready frame too long');
      }
    }
    return const [];
  }

  /// The stream ended: a frame still pending is missing.
  void close() {
    if (_state == FrameState.pending) {
      _problem = _buffer.isEmpty
          ? 'no ready frame'
          : 'the ready frame ended early';
      _state = FrameState.malformed;
    }
  }

  List<int> _fail(String why) {
    _problem = why;
    _state = FrameState.malformed;
    return const [];
  }

  void _finish() {
    final text = latin1.decode(
      _buffer.sublist(_prefix.length, _buffer.length - 1),
      allowInvalid: true,
    );
    if (text == 'ok') {
      _frame = const ReadyFrame.ok();
      _state = FrameState.ready;
    } else if (text.startsWith('nojob ')) {
      _frame = ReadyFrame.noJob(text.substring('nojob '.length));
      _state = FrameState.ready;
    } else {
      _fail('unknown ready frame');
    }
  }
}
