import 'dart:async';
import 'dart:io';

import '../process/limits.dart';
import 'stop.dart';

/// The longest a release file may take (`scripts/update.sh` `SW_DEADLINE`).
const Duration defaultDownloadDeadline = Duration(seconds: 120);

/// The largest release file taken (`scripts/update.sh` `SW_MAX_BYTES`).
const int defaultDownloadMaxBytes = 64 * 1024 * 1024;

const int _maxRedirects = 10;

/// How long a stopped download waits for its cancellation and its close
/// before it reports what it latched.
const Duration _shutdownGrace = Duration(seconds: 10);

/// Where a download's body goes: one chunk at a time, then closed once.
abstract class PartWriter {
  Future<void> write(List<int> chunk);
  Future<void> close();
}

/// The production [PartWriter]: one open `RandomAccessFile`.
class RandomAccessPartWriter implements PartWriter {
  RandomAccessPartWriter(this._file);

  /// Opens [path] for writing, synchronously.
  factory RandomAccessPartWriter.open(String path) =>
      RandomAccessPartWriter(File(path).openSync(mode: FileMode.write));

  final RandomAccessFile _file;

  @override
  Future<void> write(List<int> chunk) => _file.writeFrom(chunk).then((_) {});

  @override
  Future<void> close() => _file.close().then((_) {});
}

/// The bounds of one download.
class DownloadBounds {
  DownloadBounds(this.deadline, this.maxBytes);

  final Duration deadline;
  final int maxBytes;
}

/// The bounds from [env]: 120 seconds and 64 MiB, which `SPECWRIGHT_NET_DEADLINE`
/// and `SPECWRIGHT_NET_MAX_BYTES` can only lower (constraint C11 of
/// native-cli-distribution; the evals make them short this way).
DownloadBounds downloadBounds(Map<String, String> env) {
  final limits = resolveLimits(env, paged: false);
  final deadline = limits.deadline < defaultDownloadDeadline
      ? limits.deadline
      : defaultDownloadDeadline;
  final lowered = int.tryParse((env['SPECWRIGHT_NET_MAX_BYTES'] ?? '').trim());
  final maxBytes =
      lowered != null && lowered >= 0 && lowered < defaultDownloadMaxBytes
      ? lowered
      : defaultDownloadMaxBytes;
  return DownloadBounds(deadline, maxBytes);
}

/// Fetches one release file (`SHA256SUMS`, the binary or the notice) from
/// [url] to [dest]. Returns true when the file is there, false when the
/// server has no such file (HTTP 404, or a missing `file://` path). Throws an
/// [UpdateStop] for anything else: `deadline_exceeded` after [deadline],
/// `response_too_large` past [maxBytes], `download_failed` for a refused URL
/// or redirect, a part file that cannot be created, a body in another
/// encoding, another HTTP status or a connection, TLS or write failure. A
/// failed download is never retried within a run.
///
/// The downloader never deletes anything: [dest] is opened first (so a part
/// that cannot be created fails before any request) and stays for the caller,
/// whose cleanup owns it (design D8 of fix-sw-port-gaps, constraint C15).
///
/// Downloads use Dart's TLS and the environment's proxy settings, not the OS's
/// curl. A host whose trust store Dart cannot read fails download_failed, and
/// the fix is a mirror (--release-url) or the host's CA setup, never an http
/// URL.
///
/// Constraint C15 of native-cli-distribution, kept by design D4: the start
/// URL must be https, and so must every redirect, followed by hand (a redirect
/// to http, to `file://` or to anything else is refused before anything is
/// fetched from it). `file://` is accepted as the start URL only, for a
/// mirror tree and the evals; `http://` is refused.
///
/// Constraint C27 of fix-sw-port-gaps: the download counts one kind of byte.
/// It asks for the identity encoding with automatic decompression off, so the
/// body carries the bytes `Content-Length` counts and the bytes that are
/// written and hashed; a final 200 in another `Content-Encoding` is
/// `download_failed` naming it. Redirect, error and final bodies draw on one
/// budget of [maxBytes], in those wire bytes. The separate limit of ten
/// redirects stays, with its own `download_failed` (`too many redirects`): an
/// empty redirect costs no budget, and the eleventh redirect is refused
/// without a twelfth request.
///
/// Constraint C21 of fix-sw-port-gaps: a download leaves through one settle
/// path, around a single slot that keeps the first outcome. While the slot is
/// empty the monotonic clock is read before each body event is admitted and
/// when the slot is filled; past the deadline the outcome becomes
/// `deadline_exceeded`. Once the slot holds anything (a size stop, a write
/// failure, a 404, the deadline) it is returned as is and the clock is not
/// read again. The timer only wakes a stalled fetch. Every write's error is
/// observed from the moment the write is issued. One grace period of at most
/// ten seconds starts at the stop; within it the subscription's cancel, the
/// client close and the part's close (chained after any pending write, with
/// its handlers attached before the wait, and owning the handle after it) are
/// started, and none is awaited past it, so the downloader reports whatever is
/// still pending.
///
/// [allowHttpStart] (the evals' `SPECWRIGHT_TEST_HTTP=1`) lets the start URL
/// be http, for a local server; a redirect must still be https.
///
/// [clientFactory] and [environment] are for tests: the first builds the
/// client (one that trusts a test certificate), the second is where the proxy
/// settings (`HTTPS_PROXY`, `NO_PROXY`) are read from (default: the process
/// environment). [clock] (monotonic time, default a stopwatch), [timerFactory]
/// (default [Timer.new]) and [openPart] (default: [dest] as one
/// `RandomAccessFile`) are the other test seams.
Future<bool> downloadReleaseFile({
  required String url,
  required String dest,
  required String name,
  required String tag,
  Duration deadline = defaultDownloadDeadline,
  int maxBytes = defaultDownloadMaxBytes,
  HttpClient Function()? clientFactory,
  Map<String, String>? environment,
  bool allowHttpStart = false,
  Duration Function()? clock,
  Timer Function(Duration, void Function())? timerFactory,
  PartWriter Function(String path)? openPart,
}) {
  final watch = Stopwatch()..start();
  return _Fetch(
    url: url,
    dest: dest,
    where: '$name of release $tag',
    deadline: deadline,
    maxBytes: maxBytes,
    clientFactory: clientFactory ?? HttpClient.new,
    environment: environment ?? Platform.environment,
    allowHttpStart: allowHttpStart,
    clock: clock ?? () => watch.elapsed,
    timers: timerFactory ?? Timer.new,
    openPart: openPart ?? RandomAccessPartWriter.open,
  ).run();
}

/// What a fetch ended with: [stop] is a thrown stop, otherwise [value] is the
/// return (true: the file is there, false: the server has none).
class _Outcome {
  _Outcome.stop(UpdateStop this.stop, {this.isDeadline = false}) : value = null;
  _Outcome.value(bool this.value) : stop = null, isDeadline = false;

  final UpdateStop? stop;
  final bool? value;
  final bool isDeadline;
}

/// One fetch of one release file. Everything that ends it goes through
/// [_latch]; the first outcome stays.
class _Fetch {
  _Fetch({
    required this.url,
    required this.dest,
    required this.where,
    required this.deadline,
    required this.maxBytes,
    required this.clientFactory,
    required this.environment,
    required this.allowHttpStart,
    required this.clock,
    required this.timers,
    required this.openPart,
  }) : _budget = maxBytes;

  final String url;
  final String dest;
  final String where;
  final Duration deadline;
  final int maxBytes;
  final HttpClient Function() clientFactory;
  final Map<String, String> environment;
  final bool allowHttpStart;
  final Duration Function() clock;
  final Timer Function(Duration, void Function()) timers;
  final PartWriter Function(String path) openPart;

  /// The one stop slot.
  _Outcome? _outcome;
  final Completer<_Outcome> _done = Completer<_Outcome>();
  late final PartWriter _writer;
  Duration _deadlineAt = Duration.zero;
  Timer? _timer;
  HttpClient? _client;
  StreamSubscription<List<int>>? _sub;
  Completer<void>? _bodyEnd;
  Future<void>? _pendingWrite;
  Future<void>? _close;
  int _budget;

  UpdateStop _failed(String detail) => UpdateStop(
    'download_failed',
    'the download of $where from $url failed: $detail',
  );

  UpdateStop _tooLarge() => UpdateStop(
    'response_too_large',
    'response_too_large: $where is larger than $maxBytes bytes; '
        'nothing was installed',
  );

  _Outcome _late() => _Outcome.stop(
    UpdateStop(
      'deadline_exceeded',
      'deadline_exceeded: the download of $where passed its bound '
          '(${_seconds(deadline)} s, $maxBytes bytes); nothing was installed',
    ),
    isDeadline: true,
  );

  bool get _pastDeadline => clock() >= _deadlineAt;

  Future<bool> run() async {
    final Uri start;
    try {
      start = Uri.parse(url);
    } on FormatException catch (e) {
      throw _failed(e.message);
    }
    final scheme = start.scheme.toLowerCase();
    if (scheme != 'file' &&
        scheme != 'https' &&
        !(allowHttpStart && scheme == 'http')) {
      throw _failed('refused, the URL is not https');
    }
    // the part is opened before the deadline starts and before any request
    try {
      _writer = openPart(dest);
    } on FileSystemException catch (e) {
      throw _failed(
        'the part file $dest cannot be created: '
        '${e.osError?.message ?? e.message}',
      );
    }
    _deadlineAt = clock() + deadline;
    if (scheme != 'file') {
      _timer = timers(deadline, () => _latch(_late()));
    }
    unawaited(_start(start, scheme == 'file'));
    final outcome = await _done.future;
    final stop = outcome.stop;
    if (stop != null) throw stop;
    return outcome.value!;
  }

  Future<void> _start(Uri start, bool file) async {
    try {
      if (file) {
        _copyFile(start);
      } else {
        await _http(start);
      }
    } on Object catch (e) {
      _latch(_Outcome.stop(_stopFor(e)));
    }
  }

  UpdateStop _stopFor(Object e) {
    if (e is UpdateStop) return e;
    if (e is HandshakeException) {
      return _failed(e.message.isEmpty ? e.toString() : e.message);
    }
    if (e is IOException) {
      return _failed(e is SocketException ? e.message : e.toString());
    }
    if (e is FormatException) return _failed(e.message);
    return _failed(e.toString());
  }

  String _reason(Object e) =>
      e is FileSystemException ? (e.osError?.message ?? e.message) : '$e';

  /// Fills the slot with [outcome] unless it is filled, then starts the
  /// bounded shutdown. An empty slot reads the clock: past the deadline the
  /// outcome is `deadline_exceeded` whatever [outcome] was.
  void _latch(_Outcome outcome) {
    if (_outcome != null) return;
    _outcome = !outcome.isDeadline && _pastDeadline ? _late() : outcome;
    _timer?.cancel();
    final end = _bodyEnd;
    if (end != null && !end.isCompleted) end.complete();
    _shutdown();
  }

  Future<void> _http(Uri start) async {
    final client = clientFactory();
    _client = client;
    client.findProxy = (uri) =>
        HttpClient.findProxyFromEnvironment(uri, environment: environment);
    client.autoUncompress = false;
    var current = start;
    for (var hops = 0; ; hops++) {
      if (_outcome != null) return;
      if (_pastDeadline) {
        _latch(_late());
        return;
      }
      final request = await client.getUrl(current);
      if (_outcome != null) return;
      request.followRedirects = false;
      request.headers.set(HttpHeaders.acceptEncodingHeader, 'identity');
      if (_pastDeadline) {
        _latch(_late());
        return;
      }
      final response = await request.close();
      if (_outcome != null) return; // late: no subscription, no drain
      final status = response.statusCode;
      if (const {301, 302, 303, 307, 308}.contains(status)) {
        final location = response.headers.value('location');
        await _consume(response, keep: false);
        if (_outcome != null) return;
        if (location == null) throw _failed('HTTP $status with no location');
        final next = current.resolve(location);
        if (next.scheme.toLowerCase() != 'https') {
          throw _failed(
            'redirect to a URL that is not https refused: $location',
          );
        }
        if (hops >= _maxRedirects) throw _failed('too many redirects');
        current = next;
        continue;
      }
      if (status == 404) {
        await _consume(response, keep: false);
        if (_outcome == null) _latch(_Outcome.value(false));
        return;
      }
      if (status != 200) {
        await _consume(response, keep: false);
        if (_outcome == null) _latch(_Outcome.stop(_failed('HTTP $status')));
        return;
      }
      // the final response: the deadline (in the latch), then the encoding,
      // then the advertised length
      final encoding = response.headers
          .value(HttpHeaders.contentEncodingHeader)
          ?.trim()
          .toLowerCase();
      if (encoding != null && encoding.isNotEmpty && encoding != 'identity') {
        _latch(
          _Outcome.stop(
            _failed(
              'the server answered with Content-Encoding $encoding; only the '
              'identity encoding is accepted',
            ),
          ),
        );
        return;
      }
      if (response.contentLength > _budget) {
        _latch(_Outcome.stop(_tooLarge()));
        return;
      }
      unawaited(_consume(response, keep: true));
      return;
    }
  }

  /// The copy of a `file://` mirror: the same body path as a download, with
  /// the same size bound.
  ///
  /// Constraint C20 of fix-sw-port-gaps: the download deadline interrupts
  /// HTTP(S) only. A `file://` copy has no deadline timer: it keeps the 64 MiB
  /// bound and is refused with `deadline_exceeded` when it finishes late, but
  /// a stalled mounted mirror is not interrupted and can hold the install. The
  /// time bounds also leave out the install's own cleanup, which deletes the
  /// partial file with synchronous file operations, so a stalled destination
  /// filesystem can delay the report. Opening the partial file is synchronous
  /// and happens before the deadline starts, so a stalled open is not bounded
  /// either, and a failed open takes precedence over every HTTP outcome: no
  /// request is sent, and the download reports `download_failed` naming the
  /// part path and the OS error, so a version directory that denies file
  /// creation reports that, never `assets_not_uploaded` for a release that
  /// would answer 404.
  void _copyFile(Uri uri) {
    final source = File(uri.toFilePath());
    if (!source.existsSync()) {
      _latch(_Outcome.value(false));
      return;
    }
    unawaited(_consume(source.openRead(), keep: true));
  }

  /// Reads [body] under the one budget. A kept body goes to the part, one
  /// chunk at a time; any other is counted and dropped. The returned future
  /// completes when the body ends or the slot fills.
  Future<void> _consume(Stream<List<int>> body, {required bool keep}) {
    final end = Completer<void>();
    _bodyEnd = end;
    late final StreamSubscription<List<int>> sub;
    sub = body.listen(
      (chunk) {
        if (_outcome != null) return;
        if (_pastDeadline) {
          _latch(_late());
          return;
        }
        if (chunk.length > _budget) {
          _latch(_Outcome.stop(_tooLarge()));
          return;
        }
        _budget -= chunk.length;
        if (!keep) return;
        sub.pause();
        final write = Future<void>.sync(() => _writer.write(chunk));
        _pendingWrite = write;
        write.then(
          (_) {
            if (_outcome == null) sub.resume();
          },
          onError: (Object e) => _latch(
            _Outcome.stop(
              _failed('writing the part file $dest failed: ${_reason(e)}'),
            ),
          ),
        );
      },
      onError: (Object e) => _latch(_Outcome.stop(_stopFor(e))),
      onDone: () {
        if (_outcome != null) return;
        if (keep) {
          _finishBody();
        } else if (!end.isCompleted) {
          end.complete();
        }
      },
      cancelOnError: true,
    );
    _sub = sub;
    return end.future;
  }

  /// The body ended with the slot empty: close the part once and succeed only
  /// if the close settles in time.
  void _finishBody() {
    _closeOnce().then(
      (_) => _latch(_Outcome.value(true)),
      onError: (Object e) => _latch(
        _Outcome.stop(
          _failed('closing the part file $dest failed: ${_reason(e)}'),
        ),
      ),
    );
  }

  /// The handle's one close, shared by normal completion and the shutdown.
  Future<void> _closeOnce() => _close ??= Future<void>.sync(_writer.close);

  /// Starts the cancellation, the client close and the part's close, and
  /// reports once they settle or the grace period ends, whichever is first.
  void _shutdown() {
    final grace = Completer<void>();
    final graceTimer = timers(_shutdownGrace, () {
      if (!grace.isCompleted) grace.complete();
    });
    final sub = _sub;
    final cancel = sub == null
        ? Future<void>.value()
        : Future<void>.sync(sub.cancel).then((_) {}, onError: (Object _) {});
    try {
      _client?.close(force: true);
    } on Object {
      // a client that is closing already
    }
    final pending = _pendingWrite ?? Future<void>.value();
    final close = pending
        .then((_) {}, onError: (Object _) {})
        .then((_) => _closeOnce())
        .then((_) {}, onError: (Object _) {});
    Future.any<void>([
      Future.wait([cancel, close]),
      grace.future,
    ]).then((_) {
      graceTimer.cancel();
      _done.complete(_outcome!);
    });
  }
}

/// Seconds as Python's `{:g}` writes the deadline: `120`, `0.4`.
String _seconds(Duration d) {
  final value = d.inMicroseconds / Duration.microsecondsPerSecond;
  return value == value.truncateToDouble()
      ? value.toInt().toString()
      : value.toString();
}
