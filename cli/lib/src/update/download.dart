import 'dart:async';
import 'dart:io';

import '../process/limits.dart';
import 'file_ops.dart';
import 'stop.dart';

/// The longest a release file may take (`scripts/update.sh` `SW_DEADLINE`).
const Duration defaultDownloadDeadline = Duration(seconds: 120);

/// The largest release file taken (`scripts/update.sh` `SW_MAX_BYTES`).
const int defaultDownloadMaxBytes = 64 * 1024 * 1024;

const int _maxRedirects = 10;

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
/// or redirect, another HTTP status or a connection or TLS failure. The
/// partial file is removed (through [files]) whenever a stop is thrown, and a
/// failed download is never retried within a run.
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
/// [allowHttpStart] (the evals' `SPECWRIGHT_TEST_HTTP=1`) lets the start URL
/// be http, for a local server; a redirect must still be https.
///
/// [clientFactory] and [environment] are for tests: the first builds the
/// client (one that trusts a test certificate), the second is where the proxy
/// settings (`HTTPS_PROXY`, `NO_PROXY`) are read from (default: the process
/// environment).
Future<bool> downloadReleaseFile({
  required String url,
  required String dest,
  required String name,
  required String tag,
  required UpdateFileOps files,
  Duration deadline = defaultDownloadDeadline,
  int maxBytes = defaultDownloadMaxBytes,
  HttpClient Function()? clientFactory,
  Map<String, String>? environment,
  bool allowHttpStart = false,
}) async {
  final where = '$name of release $tag';
  UpdateStop failed(String detail) => UpdateStop(
    'download_failed',
    'the download of $where from $url failed: $detail',
  );

  final env = environment ?? Platform.environment;
  final client = (clientFactory ?? HttpClient.new)();
  client.findProxy = (uri) =>
      HttpClient.findProxyFromEnvironment(uri, environment: env);

  Future<bool> fetch() async {
    var current = Uri.parse(url);
    final scheme = current.scheme.toLowerCase();
    if (scheme == 'file') return _copyFile(current, dest, maxBytes, where);
    if (scheme != 'https' && !(allowHttpStart && scheme == 'http')) {
      throw failed('refused, the URL is not https');
    }
    for (var hops = 0; ; hops++) {
      final request = await client.getUrl(current);
      request.followRedirects = false;
      final response = await request.close();
      final status = response.statusCode;
      if (const {301, 302, 303, 307, 308}.contains(status)) {
        final location = response.headers.value('location');
        await response.drain<void>();
        if (location == null) throw failed('HTTP $status with no location');
        final next = current.resolve(location);
        if (next.scheme.toLowerCase() != 'https') {
          throw failed(
            'redirect to a URL that is not https refused: $location',
          );
        }
        if (hops >= _maxRedirects) throw failed('too many redirects');
        current = next;
        continue;
      }
      if (status == 404) {
        await response.drain<void>();
        return false;
      }
      if (status != 200) {
        await response.drain<void>();
        throw failed('HTTP $status');
      }
      if (response.contentLength > maxBytes) {
        throw _tooLarge(where, maxBytes);
      }
      await _write(response, dest, maxBytes, where);
      return true;
    }
  }

  final work = _guard(fetch(), failed);
  try {
    return await work.timeout(deadline);
  } on TimeoutException {
    client.close(force: true);
    await work.then<void>((_) {}, onError: (Object _) {});
    files.remove(dest);
    throw UpdateStop(
      'deadline_exceeded',
      'deadline_exceeded: the download of $where passed its bound '
          '(${_seconds(deadline)} s, $maxBytes bytes); nothing was installed',
    );
  } on UpdateStop {
    files.remove(dest);
    rethrow;
  } finally {
    client.close(force: true);
  }
}

/// Turns an I/O failure of [work] into the `download_failed` stop.
Future<bool> _guard(
  Future<bool> work,
  UpdateStop Function(String detail) failed,
) async {
  try {
    return await work;
  } on UpdateStop {
    rethrow;
  } on HandshakeException catch (e) {
    throw failed(e.message.isEmpty ? e.toString() : e.message);
  } on IOException catch (e) {
    throw failed(e is SocketException ? e.message : e.toString());
  } on FormatException catch (e) {
    throw failed(e.message);
  }
}

Future<bool> _copyFile(Uri uri, String dest, int maxBytes, String where) async {
  final source = File(uri.toFilePath());
  if (!source.existsSync()) return false;
  await _write(source.openRead(), dest, maxBytes, where);
  return true;
}

Future<void> _write(
  Stream<List<int>> body,
  String dest,
  int maxBytes,
  String where,
) async {
  final sink = File(dest).openWrite();
  var count = 0;
  try {
    await for (final chunk in body) {
      count += chunk.length;
      if (count > maxBytes) throw _tooLarge(where, maxBytes);
      sink.add(chunk);
    }
  } finally {
    await sink.close();
  }
}

UpdateStop _tooLarge(String where, int maxBytes) => UpdateStop(
  'response_too_large',
  'response_too_large: $where is larger than $maxBytes bytes; '
      'nothing was installed',
);

/// Seconds as Python's `{:g}` writes the deadline: `120`, `0.4`.
String _seconds(Duration d) {
  final value = d.inMicroseconds / Duration.microsecondsPerSecond;
  return value == value.truncateToDouble()
      ? value.toInt().toString()
      : value.toString();
}
