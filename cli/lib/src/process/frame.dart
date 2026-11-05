import 'dart:convert';
import 'dart:typed_data';

/// The identity frame, the very first bytes on the helper's stderr:
/// `\x00sw-hello <id>\n`. On Windows [id] is the helper's own creation time
/// (the 64-bit FILETIME in decimal), which together with its PID names one
/// process; on POSIX it is `-`. The NUL prefix keeps it from matching any text
/// a command could have written, since the command has not started yet.
class HelloFrame {
  const HelloFrame(this.id);

  /// The frame for a helper with no creation time to report (POSIX).
  const HelloFrame.none() : id = '-';

  final String id;

  /// The creation time, or null when the helper reported none (`-`).
  int? get creationTime => int.tryParse(id);

  List<int> encode() => utf8.encode('\x00sw-hello $id\n');
}

/// The ready frame, the next bytes on the helper's stderr:
/// `\x00sw-ready ok\n` or `\x00sw-ready nojob <reason>\n`. It says the helper
/// has set up its containment (`setsid()` on POSIX) or why it could not.
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

/// Where [FrameParser] is: waiting for the hello frame, for the ready frame,
/// done, or given up on a frame that is missing or malformed.
enum FrameState { awaitingHello, awaitingReady, ready, malformed }

/// Reads the hello and ready frames off the front of the helper's stderr.
///
/// [add] consumes the frame bytes and returns the bytes after the frames,
/// which belong to the command's stderr. Bytes of a frame are never returned,
/// so they are neither counted nor passed on. [hello] is set as soon as its
/// frame is complete, before the ready frame is.
class FrameParser {
  static const _helloPrefix = '\x00sw-hello ';
  static const _readyPrefix = '\x00sw-ready ';
  static const _maxLength = 1024;

  final List<int> _buffer = [];
  FrameState _state = FrameState.awaitingHello;
  HelloFrame? _hello;
  ReadyFrame? _ready;
  String? _problem;

  FrameState get state => _state;

  /// The hello frame once it has been read.
  HelloFrame? get hello => _hello;

  /// The ready frame once [state] is [FrameState.ready].
  ReadyFrame? get ready => _ready;

  /// Why the frame is malformed once [state] is [FrameState.malformed].
  String? get problem => _problem;

  /// Whether the stream ended cleanly between frames: no byte of the
  /// pending frame arrived, so the writer stopped rather than sent a bad one.
  bool get missing => _missing;
  bool _missing = false;

  /// What was read of a malformed frame, printable, for the reason line.
  String get received => latin1
      .decode(_buffer.take(120).toList(), allowInvalid: true)
      .replaceAll(RegExp(r'[^\x20-\x7e]'), '?');

  String get _prefix =>
      _state == FrameState.awaitingHello ? _helloPrefix : _readyPrefix;

  List<int> add(List<int> chunk) {
    if (_state == FrameState.ready) return chunk;
    if (_state == FrameState.malformed) return const [];
    var consumed = 0;
    while (consumed < chunk.length) {
      final byte = chunk[consumed++];
      _buffer.add(byte);
      if (_buffer.length <= _prefix.length) {
        if (byte != _prefix.codeUnitAt(_buffer.length - 1)) {
          return _fail(
            _state == FrameState.awaitingHello
                ? 'not a hello frame'
                : 'not a ready frame',
          );
        }
      } else if (byte == 0x0a) {
        _finish();
        if (_state == FrameState.malformed) return const [];
        if (_state == FrameState.ready) {
          final bytes = chunk is Uint8List ? chunk : Uint8List.fromList(chunk);
          return Uint8List.sublistView(bytes, consumed);
        }
      } else if (_buffer.length > _maxLength) {
        return _fail('frame too long');
      }
    }
    return const [];
  }

  /// The stream ended: a frame still pending is missing.
  void close() {
    if (_state == FrameState.awaitingHello ||
        _state == FrameState.awaitingReady) {
      final what = _state == FrameState.awaitingHello ? 'hello' : 'ready';
      _missing = _buffer.isEmpty;
      _problem = _missing ? 'no $what frame' : 'the $what frame ended early';
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
    if (_state == FrameState.awaitingHello) {
      if (text == '-' || RegExp(r'^[0-9]{1,20}$').hasMatch(text)) {
        _hello = HelloFrame(text);
        _state = FrameState.awaitingReady;
        _buffer.clear();
      } else {
        _fail('unknown hello frame');
      }
    } else if (text == 'ok') {
      _ready = const ReadyFrame.ok();
      _state = FrameState.ready;
    } else if (text.startsWith('nojob ')) {
      _ready = ReadyFrame.noJob(text.substring('nojob '.length));
      _state = FrameState.ready;
    } else {
      _fail('unknown ready frame');
    }
  }
}
