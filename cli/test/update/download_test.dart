import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/update/download.dart';
import 'package:specwright_cli/src/update/stop.dart';
import 'package:test/test.dart';

// Design D4 and constraint C5 of native-cli-update: a release file is fetched
// in process over https only (the start URL and every redirect), file:// is a
// mirror, a deadline and a size cap stop it, and the proxy comes from the
// environment. Design D8 of fix-sw-port-gaps: the downloader opens its part
// file first, deletes nothing (the install owns every part), counts every body
// against one budget and leaves through one stop slot. The server is a local
// TLS server with a self-signed certificate (fixtures/); the client under test
// trusts only it.

const _cert = 'test/update/fixtures/test_cert.pem';
const _key = 'test/update/fixtures/test_key.pem';

void main() {
  late Directory temp;
  late HttpServer server;
  late String base;
  late String dest;
  final handlers = <String, FutureOr<void> Function(HttpRequest)>{};
  late _Clock clock;
  late _Timers timers;

  String squash(String pem) => pem.replaceAll(RegExp(r'\s'), '');

  HttpClient Function() trusting() => () {
    final pem = File(_cert).readAsStringSync();
    final context = SecurityContext(withTrustedRoots: false)
      ..setTrustedCertificatesBytes(utf8.encode(pem));
    // macOS refuses a self-signed server certificate whose lifetime passes
    // 825 days even when the context trusts it; this exact fixture is still
    // the only certificate the client accepts
    return HttpClient(context: context)
      ..badCertificateCallback = (cert, host, port) =>
          squash(cert.pem) == squash(pem);
  };

  Future<bool> fetch(
    String path, {
    Duration deadline = const Duration(seconds: 20),
    int maxBytes = 1 << 20,
    Map<String, String> environment = const {},
    HttpClient Function()? factory,
    String? url,
    bool fake = false,
    PartWriter? writer,
    PartWriter Function(String path)? open,
  }) => downloadReleaseFile(
    url: url ?? '$base$path',
    dest: dest,
    name: 'sw-linux-x64',
    tag: 'v0.37.0',
    deadline: deadline,
    maxBytes: maxBytes,
    clientFactory: factory ?? trusting(),
    environment: environment,
    clock: fake ? clock.call : null,
    timerFactory: fake ? timers.create : null,
    openPart: open ?? (writer == null ? null : (_) => writer),
  );

  Future<UpdateStop> stopOf(Future<Object?> run) async {
    try {
      await run;
    } on UpdateStop catch (e) {
      return e;
    }
    fail('expected an UpdateStop');
  }

  setUp(() async {
    clock = _Clock();
    timers = _Timers();
    temp = Directory.systemTemp.createTempSync('sw-download-');
    dest = '${temp.path}/part';
    final context = SecurityContext()
      ..useCertificateChainBytes(File(_cert).readAsBytesSync())
      ..usePrivateKeyBytes(File(_key).readAsBytesSync());
    server = await HttpServer.bindSecure(
      InternetAddress.loopbackIPv4,
      0,
      context,
    );
    base = 'https://127.0.0.1:${server.port}';
    handlers.clear();
    server.listen((request) async {
      final handler = handlers[request.uri.path];
      if (handler == null) {
        request.response.statusCode = 404;
        await request.response.close();
        return;
      }
      // a stall must hold back what is not sent yet, not what was written
      request.response.bufferOutput = false;
      try {
        await handler(request);
      } on Object {
        // the client went away
      }
    });
  });

  tearDown(() async {
    await server.close(force: true);
    temp.deleteSync(recursive: true);
  });

  group('https', () {
    test('writes the body to the destination and returns true', () async {
      handlers['/a'] = (r) async {
        r.response.add(utf8.encode('hello'));
        await r.response.close();
      };
      expect(await fetch('/a'), isTrue);
      expect(File(dest).readAsStringSync(), 'hello');
    });

    test('a 404 is false and writes nothing', () async {
      expect(await fetch('/missing'), isFalse);
      expect(File(dest).lengthSync(), 0, reason: 'no response byte written');
    });

    test('another HTTP status is download_failed', () async {
      handlers['/boom'] = (r) async {
        r.response.statusCode = 500;
        await r.response.close();
      };
      final stop = await stopOf(fetch('/boom'));
      expect(stop.code, 'download_failed');
      expect(stop.message, contains('sw-linux-x64 of release v0.37.0'));
      expect(stop.message, contains('HTTP 500'));
      expect(File(dest).lengthSync(), 0, reason: 'no response byte written');
    });

    test('follows an https redirect, by hand, to the file', () async {
      handlers['/old'] = (r) async {
        r.response
          ..statusCode = 302
          ..headers.set('location', '/new');
        await r.response.close();
      };
      handlers['/new'] = (r) async {
        r.response.add(utf8.encode('moved'));
        await r.response.close();
      };
      expect(await fetch('/old'), isTrue);
      expect(File(dest).readAsStringSync(), 'moved');
    });

    test('a redirect to http is refused and nothing is fetched', () async {
      final plain = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      var plainRequests = 0;
      plain.listen((r) async {
        plainRequests++;
        r.response.add(utf8.encode('plain'));
        await r.response.close();
      });
      addTearDown(() => plain.close(force: true));
      handlers['/old'] = (r) async {
        r.response
          ..statusCode = 301
          ..headers.set('location', 'http://127.0.0.1:${plain.port}/x');
        await r.response.close();
      };
      final stop = await stopOf(fetch('/old'));
      expect(stop.code, 'download_failed');
      expect(stop.message, contains('not https'));
      expect(plainRequests, 0);
      expect(File(dest).lengthSync(), 0, reason: 'no response byte written');
    });

    test('a redirect to file:// is refused', () async {
      handlers['/old'] = (r) async {
        r.response
          ..statusCode = 302
          ..headers.set('location', 'file:///etc/passwd');
        await r.response.close();
      };
      final stop = await stopOf(fetch('/old'));
      expect(stop.code, 'download_failed');
      expect(stop.message, contains('not https'));
    });

    test('a redirect loop stops at ten hops', () async {
      handlers['/loop'] = (r) async {
        r.response
          ..statusCode = 302
          ..headers.set('location', '/loop');
        await r.response.close();
      };
      final stop = await stopOf(fetch('/loop'));
      expect(stop.code, 'download_failed');
      expect(stop.message, contains('redirect'));
    });

    test(
      'a certificate the client does not trust is download_failed',
      () async {
        handlers['/a'] = (r) async => r.response.close();
        final stop = await stopOf(fetch('/a', factory: HttpClient.new));
        expect(stop.code, 'download_failed');
        expect(stop.message, contains('from $base/a failed'));
      },
    );
  });

  group('http', () {
    test('an http start URL is refused before any connection', () async {
      final plain = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      var seen = 0;
      plain.listen((r) async {
        seen++;
        await r.response.close();
      });
      addTearDown(() => plain.close(force: true));
      final stop = await stopOf(
        fetch('', url: 'http://127.0.0.1:${plain.port}/a'),
      );
      expect(stop.code, 'download_failed');
      expect(stop.message, contains('not https'));
      expect(seen, 0);
    });
  });

  group('file://', () {
    test('a file under a mirror is copied', () async {
      final source = File('${temp.path}/asset')..writeAsStringSync('mirror');
      expect(await fetch('', url: source.uri.toString()), isTrue);
      expect(File(dest).readAsStringSync(), 'mirror');
    });

    test('a missing file is false', () async {
      expect(
        await fetch('', url: File('${temp.path}/none').uri.toString()),
        isFalse,
      );
    });

    test('a file:// copy over 64 MiB is response_too_large', () async {
      // the cap is lowered so the fixture stays small
      final source = File('${temp.path}/big')
        ..writeAsBytesSync(List.filled(5000, 0));
      final writer = _Writer();
      final stop = await stopOf(
        fetch(
          '',
          url: source.uri.toString(),
          maxBytes: 1000,
          fake: true,
          writer: writer,
        ),
      );
      expect(stop.code, 'response_too_large');
      expect(writer.bytes, isEmpty, reason: 'no response byte written');
      expect(writer.closes, 1);
    });

    test('a late file:// copy is deadline_exceeded', () async {
      final source = File('${temp.path}/late')..writeAsStringSync('mirror');
      final writer = _Writer()
        ..onWrite = (chunk) async {
          clock.now = const Duration(seconds: 200); // the copy ends late
        };
      final stop = await stopOf(
        fetch(
          '',
          url: source.uri.toString(),
          deadline: const Duration(seconds: 120),
          fake: true,
          writer: writer,
        ),
      );
      expect(stop.code, 'deadline_exceeded');
      expect(stop.message, contains('sw-linux-x64 of release v0.37.0'));
      // the deadline interrupts HTTP(S) only (C20): no timer for a copy
      expect(timers.list.where((t) => t.duration == _deadline), isEmpty);
    });
  });

  group('bounds', () {
    test('the deadline stops a stalled body', () async {
      handlers['/stall'] = (r) async {
        r.response.headers.contentLength = 100;
        r.response.add(utf8.encode('start'));
        await r.response.flush();
        await Completer<void>().future; // never finishes
      };
      final stop = await stopOf(
        fetch('/stall', deadline: const Duration(milliseconds: 400)),
      );
      expect(stop.code, 'deadline_exceeded');
      expect(stop.message, contains('sw-linux-x64 of release v0.37.0'));
      expect(stop.message, contains('0.4 s'));
      expect(stop.message, contains('nothing was installed'));
    });

    test('a body over the cap is response_too_large', () async {
      handlers['/big'] = (r) async {
        r.response.add(List.filled(5000, 1));
        await r.response.close();
      };
      final stop = await stopOf(fetch('/big', maxBytes: 1000));
      expect(stop.code, 'response_too_large');
      expect(stop.message, contains('1000 bytes'));
      expect(File(dest).lengthSync(), 0, reason: 'no response byte written');
    });

    test('a chunked body over the cap is refused too', () async {
      handlers['/chunks'] = (r) async {
        r.response.headers.chunkedTransferEncoding = true;
        for (var i = 0; i < 10; i++) {
          r.response.add(List.filled(500, 1));
          await r.response.flush();
        }
        await r.response.close();
      };
      final stop = await stopOf(fetch('/chunks', maxBytes: 1000));
      expect(stop.code, 'response_too_large');
      expect(File(dest).lengthSync(), lessThanOrEqualTo(1000));
    });

    test('the environment can lower the bounds, never raise them', () {
      var bounds = downloadBounds(const {});
      expect(bounds.deadline, const Duration(seconds: 120));
      expect(bounds.maxBytes, 64 * 1024 * 1024);
      bounds = downloadBounds(const {
        'SPECWRIGHT_NET_DEADLINE': '2',
        'SPECWRIGHT_NET_MAX_BYTES': '10',
      });
      expect(bounds.deadline, const Duration(seconds: 2));
      expect(bounds.maxBytes, 10);
      bounds = downloadBounds(const {
        'SPECWRIGHT_NET_DEADLINE': '9999',
        'SPECWRIGHT_NET_MAX_BYTES': '999999999999',
      });
      expect(bounds.deadline, const Duration(seconds: 120));
      expect(bounds.maxBytes, 64 * 1024 * 1024);
    });
  });

  group('the part file and the stop slot (D8)', () {
    const deadline = Duration(seconds: 120);
    const past = Duration(seconds: 500);

    Future<void> until(bool Function() done) async {
      for (var i = 0; i < 500 && !done(); i++) {
        await Future<void>.delayed(const Duration(milliseconds: 10));
      }
      expect(done(), isTrue, reason: 'condition never held');
    }

    Future<void> pause([int ms = 150]) =>
        Future<void>.delayed(Duration(milliseconds: ms));

    /// Runs [run] and records whether it has settled.
    ({Future<Object?> outcome, bool Function() settled}) track(
      Future<bool> run,
    ) {
      var settled = false;
      final outcome = run.then<Object?>((v) => v, onError: (Object e) => e)
        ..whenComplete(() => settled = true);
      return (outcome: outcome, settled: () => settled);
    }

    test('the deadline clock starts after the part is open', () async {
      final order = <String>[];
      handlers['/a'] = (r) async {
        order.add('request');
        r.response.add(utf8.encode('hello'));
        await r.response.close();
      };
      final writer = _Writer();
      final ok = await fetch(
        '/a',
        deadline: deadline,
        fake: true,
        open: (path) {
          order.add('open');
          clock.now = past; // a slow open is not part of the 120 seconds
          return writer;
        },
      );
      expect(ok, isTrue);
      expect(order, ['open', 'request']);
      expect(writer.text, 'hello');
      expect(timers.list.first.duration, deadline);
    });

    test('an open failure is download_failed with no request', () async {
      var requests = 0;
      handlers['/a'] = (r) async {
        requests++;
        r.response.add(utf8.encode('x'));
        await r.response.close();
      };
      final stop = await stopOf(
        fetch(
          '/a',
          open: (path) => throw FileSystemException(
            'open',
            path,
            const OSError('injected reason', 13),
          ),
        ),
      );
      expect(stop.code, 'download_failed');
      expect(stop.message, contains(dest));
      expect(stop.message, contains('injected reason'));
      expect(requests, 0);
    });

    test(
      'a 404 or redirect body over the budget is response_too_large',
      () async {
        handlers['/gone'] = (r) async {
          r.response
            ..statusCode = 404
            ..headers.chunkedTransferEncoding = true;
          for (var i = 0; i < 10; i++) {
            r.response.add(List.filled(500, 1));
            await r.response.flush();
          }
          await r.response.close();
        };
        handlers['/old'] = (r) async {
          r.response
            ..statusCode = 302
            ..headers.set('location', '/new')
            ..headers.chunkedTransferEncoding = true;
          for (var i = 0; i < 10; i++) {
            r.response.add(List.filled(500, 1));
            await r.response.flush();
          }
          await r.response.close();
        };
        for (final path in ['/gone', '/old']) {
          final writer = _Writer();
          final stop = await stopOf(
            fetch(path, maxBytes: 1000, fake: true, writer: writer),
          );
          expect(stop.code, 'response_too_large', reason: path);
          expect(stop.message, contains('sw-linux-x64'), reason: path);
          expect(writer.bytes, isEmpty, reason: path);
          expect(writer.closes, 1, reason: path);
        }
      },
    );

    test('a 40 MiB redirect body and a 40 MiB asset share one budget', () async {
      // the cap is lowered: 600 bytes of redirect body, 600 of asset, cap 1000
      handlers['/old'] = (r) async {
        r.response
          ..statusCode = 302
          ..headers.set('location', '/new')
          ..headers.contentLength = 600;
        r.response.add(List.filled(600, 1));
        await r.response.close();
      };
      handlers['/new'] = (r) async {
        r.response.headers.contentLength = 600;
        r.response.add(List.filled(600, 2));
        await r.response.close();
      };
      handlers['/newer'] = (r) async {
        r.response.headers.chunkedTransferEncoding = true;
        for (var i = 0; i < 3; i++) {
          r.response.add(List.filled(200, 2));
          await r.response.flush();
        }
        await r.response.close();
      };
      handlers['/old2'] = (r) async {
        r.response
          ..statusCode = 302
          ..headers.set('location', '/newer')
          ..headers.contentLength = 600;
        r.response.add(List.filled(600, 1));
        await r.response.close();
      };
      for (final path in ['/old', '/old2']) {
        final writer = _Writer();
        final stop = await stopOf(
          fetch(path, maxBytes: 1000, fake: true, writer: writer),
        );
        expect(stop.code, 'response_too_large', reason: path);
        expect(stop.message, contains('sw-linux-x64'), reason: path);
        expect(writer.bytes.length, lessThan(600), reason: path);
      }
    });

    test('a failing or held close keeps response_too_large', () async {
      handlers['/big'] = (r) async {
        r.response.add(List.filled(5000, 1));
        await r.response.close();
      };
      final failing = _Writer()..failClose = true;
      var stop = await stopOf(
        fetch('/big', maxBytes: 1000, fake: true, writer: failing),
      );
      expect(stop.code, 'response_too_large');
      expect(failing.closes, 1);

      timers = _Timers();
      final held = _Writer()..holdClose = true;
      final run = track(
        fetch('/big', maxBytes: 1000, fake: true, writer: held),
      );
      await until(() => timers.graces.isNotEmpty);
      await pause();
      expect(run.settled(), isFalse, reason: 'the grace period is running');
      timers.graces.single.fire();
      final result = await run.outcome;
      expect(result, isA<UpdateStop>());
      stop = result as UpdateStop;
      expect(stop.code, 'response_too_large');
      expect(timers.deadlineTimer.fired, isFalse);
      expect(held.closes, 1);
    });

    test(
      'an oversized chunk after the deadline is deadline_exceeded',
      () async {
        handlers['/big'] = (r) async {
          r.response.headers.chunkedTransferEncoding = true;
          r.response.add(List.filled(10, 1));
          await r.response.flush();
          await pause();
          clock.now = past; // the isolate has not run the overdue timer
          r.response.add(List.filled(5000, 1));
          await r.response.close();
        };
        final writer = _Writer();
        final stop = await stopOf(
          fetch(
            '/big',
            maxBytes: 1000,
            deadline: deadline,
            fake: true,
            writer: writer,
          ),
        );
        expect(stop.code, 'deadline_exceeded');
        expect(
          writer.bytes,
          hasLength(10),
          reason: 'the late chunk is dropped',
        );
        expect(timers.deadlineTimer.fired, isFalse);
      },
    );

    test('an oversized Content-Length ends at once', () async {
      handlers['/stall'] = (r) async {
        r.response.headers.contentLength = 5000;
        r.response.add(utf8.encode('start'));
        await r.response.flush();
        await Completer<void>().future;
      };
      final writer = _Writer();
      final stop = await stopOf(
        fetch('/stall', maxBytes: 1000, fake: true, writer: writer),
      );
      expect(stop.code, 'response_too_large');
      expect(writer.bytes, isEmpty);
      expect(writer.closes, 1);
      expect(timers.deadlineTimer.fired, isFalse);
    });

    test('a write failure during a stall is download_failed', () async {
      late RandomAccessFile raf;
      handlers['/stall'] = (r) async {
        r.response.headers.contentLength = 100;
        r.response.add(utf8.encode('start'));
        await r.response.flush();
        await pause();
        raf.closeSync(); // the next real write fails
        r.response.add(utf8.encode('more'));
        await r.response.flush();
        await Completer<void>().future;
      };
      final stop = await stopOf(
        fetch(
          '/stall',
          deadline: const Duration(seconds: 3),
          fake: true,
          open: (path) {
            raf = File(path).openSync(mode: FileMode.write);
            return RandomAccessPartWriter(raf);
          },
        ),
      );
      expect(stop.code, 'download_failed');
      expect(timers.deadlineTimer.cancelled, isTrue);
      expect(timers.deadlineTimer.fired, isFalse);
    });

    test('a write failing just before the deadline is not a timeout', () async {
      handlers['/stall'] = (r) async {
        r.response.headers.contentLength = 100;
        r.response.add(utf8.encode('start'));
        await r.response.flush();
        await Completer<void>().future;
      };
      final gate = Completer<void>();
      final started = Completer<void>();
      final writer = _Writer()
        ..holdClose = true
        ..onWrite = (chunk) {
          started.complete();
          return gate.future;
        };
      final run = track(
        fetch('/stall', deadline: deadline, fake: true, writer: writer),
      );
      await started.future;
      clock.now = const Duration(seconds: 119);
      gate.completeError(const FileSystemException('disk full'));
      await until(() => writer.closes == 1 && timers.graces.isNotEmpty);
      clock.now = const Duration(seconds: 125);
      timers.graces.single.fire();
      final result = await run.outcome;
      expect(result, isA<UpdateStop>());
      expect((result as UpdateStop).code, 'download_failed');
    });

    test(
      'a getUrl or write failure after the deadline is deadline_exceeded',
      () async {
        handlers['/a'] = (r) async => r.response.close();
        // the handshake fails after the clock has passed the deadline
        var stop = await stopOf(
          fetch(
            '/a',
            deadline: deadline,
            fake: true,
            writer: _Writer(),
            factory: () =>
                HttpClient()
                  ..badCertificateCallback = (cert, host, port) {
                    clock.now = past;
                    return false;
                  },
          ),
        );
        expect(stop.code, 'deadline_exceeded');

        // a write that fails once the clock is past the deadline
        handlers['/b'] = (r) async {
          r.response.headers.contentLength = 100;
          r.response.add(utf8.encode('start'));
          await r.response.flush();
          await Completer<void>().future;
        };
        clock.now = Duration.zero;
        final gate = Completer<void>();
        final started = Completer<void>();
        final writer = _Writer()
          ..onWrite = (chunk) {
            started.complete();
            return gate.future;
          };
        timers = _Timers();
        final run = track(
          fetch('/b', deadline: deadline, fake: true, writer: writer),
        );
        await started.future;
        clock.now = past;
        gate.completeError(const FileSystemException('disk full'));
        final result = await run.outcome;
        expect(result, isA<UpdateStop>());
        stop = result as UpdateStop;
        expect(stop.code, 'deadline_exceeded');
      },
    );

    test(
      'no request is sent when getUrl completes after the deadline',
      () async {
        var requests = 0;
        handlers['/a'] = (r) async {
          requests++;
          await r.response.close();
        };
        final pem = File(_cert).readAsStringSync();
        final stop = await stopOf(
          fetch(
            '/a',
            deadline: deadline,
            fake: true,
            writer: _Writer(),
            factory: () =>
                HttpClient(context: SecurityContext(withTrustedRoots: false))
                  ..badCertificateCallback = (cert, host, port) {
                    clock.now = past;
                    return squash(cert.pem) == squash(pem);
                  },
          ),
        );
        expect(stop.code, 'deadline_exceeded');
        expect(requests, 0);
      },
    );

    test('a gzip 200 is download_failed naming the encoding', () async {
      handlers['/gz'] = (r) async {
        r.response.headers.set('content-encoding', 'gzip');
        r.response.add(utf8.encode('xx'));
        await r.response.close();
      };
      handlers['/gz-chunked'] = (r) async {
        r.response.headers
          ..set('content-encoding', 'gzip')
          ..chunkedTransferEncoding = true;
        r.response.add(utf8.encode('xx'));
        await r.response.close();
      };
      handlers['/gz-big'] = (r) async {
        r.response.headers
          ..set('content-encoding', 'gzip')
          ..contentLength = 5000;
        r.response.add([1]);
        await r.response.flush();
        await Completer<void>().future;
      };
      for (final path in ['/gz', '/gz-chunked', '/gz-big']) {
        final writer = _Writer();
        final stop = await stopOf(
          fetch(path, maxBytes: 1000, fake: true, writer: writer),
        );
        expect(stop.code, 'download_failed', reason: path);
        expect(stop.message, contains('gzip'), reason: path);
        expect(writer.bytes, isEmpty, reason: path);
      }
    });

    test('an identity asset over the budget is response_too_large', () async {
      handlers['/len'] = (r) async {
        r.response.headers.contentLength = 5000;
        r.response.add(List.filled(5000, 1));
        await r.response.close();
      };
      handlers['/nolen'] = (r) async {
        r.response.headers.chunkedTransferEncoding = true;
        r.response.add(List.filled(5000, 1));
        await r.response.close();
      };
      for (final path in ['/len', '/nolen']) {
        final writer = _Writer();
        final stop = await stopOf(
          fetch(path, maxBytes: 1000, fake: true, writer: writer),
        );
        expect(stop.code, 'response_too_large', reason: path);
        expect(writer.bytes, isEmpty, reason: path);
        expect(writer.closes, 1, reason: path);
      }
    });

    test('an identity 206 is download_failed', () async {
      handlers['/part'] = (r) async {
        r.response
          ..statusCode = 206
          ..add(utf8.encode('abc'));
        await r.response.close();
      };
      final writer = _Writer();
      final stop = await stopOf(fetch('/part', fake: true, writer: writer));
      expect(stop.code, 'download_failed');
      expect(stop.message, contains('HTTP 206'));
      expect(writer.bytes, isEmpty, reason: 'nothing of the body is kept');
      expect(writer.closes, 1);
    });

    test('a small gzip 404 is the missing asset', () async {
      handlers['/gz404'] = (r) async {
        r.response
          ..statusCode = 404
          ..headers.set('content-encoding', 'gzip')
          ..add(List.filled(20, 7));
        await r.response.close();
      };
      final writer = _Writer()..holdClose = true;
      final run = track(fetch('/gz404', fake: true, writer: writer));
      await until(() => timers.graces.isNotEmpty);
      timers.graces.single.fire();
      expect(await run.outcome, isFalse);
      expect(writer.closes, 1);
      expect(writer.closeDone, isFalse, reason: 'the handle is still held');
    });

    test(
      'gzip headers handled after the deadline are deadline_exceeded',
      () async {
        handlers['/gz'] = (r) async {
          clock.now = past;
          r.response.headers.set('content-encoding', 'gzip');
          r.response.add(utf8.encode('xx'));
          await r.response.close();
        };
        final stop = await stopOf(
          fetch('/gz', deadline: deadline, fake: true, writer: _Writer()),
        );
        expect(stop.code, 'deadline_exceeded');
      },
    );

    test('a body of exactly maxBytes succeeds', () async {
      handlers['/exact'] = (r) async {
        r.response.headers.chunkedTransferEncoding = true;
        for (var i = 0; i < 2; i++) {
          r.response.add(List.filled(500, 1));
          await r.response.flush();
        }
        await r.response.close();
      };
      final writer = _Writer();
      expect(
        await fetch('/exact', maxBytes: 1000, fake: true, writer: writer),
        isTrue,
      );
      expect(writer.bytes, hasLength(1000));
      expect(writer.closes, 1);
    });

    test('a close settling after the deadline is deadline_exceeded', () async {
      handlers['/exact'] = (r) async {
        r.response.headers.chunkedTransferEncoding = true;
        r.response.add(List.filled(1000, 1));
        await r.response.close();
      };
      final held = _Writer()..holdClose = true;
      final run = track(
        fetch(
          '/exact',
          maxBytes: 1000,
          deadline: deadline,
          fake: true,
          writer: held,
        ),
      );
      await until(() => held.closes == 1);
      timers.deadlineTimer.fire();
      await until(() => timers.graces.isNotEmpty);
      timers.graces.single.fire();
      final result = await run.outcome;
      expect(result, isA<UpdateStop>());
      expect((result as UpdateStop).code, 'deadline_exceeded');
      expect(held.closes, 1, reason: 'the close is issued once');

      // a close that settles after the clock passed the deadline
      timers = _Timers();
      final late = _Writer()
        ..onClose = () async {
          clock.now = past;
        };
      final stop = await stopOf(
        fetch(
          '/exact',
          maxBytes: 1000,
          deadline: deadline,
          fake: true,
          writer: late,
        ),
      );
      expect(stop.code, 'deadline_exceeded');
    });

    test(
      'a write held past the grace period is closed once, after it',
      () async {
        handlers['/stall'] = (r) async {
          r.response.headers.contentLength = 100;
          r.response.add(utf8.encode('start'));
          await r.response.flush();
          await Completer<void>().future;
        };
        final gate = Completer<void>();
        final started = Completer<void>();
        final writer = _Writer()
          ..onWrite = (chunk) {
            started.complete();
            return gate.future;
          };
        final run = track(
          fetch('/stall', deadline: deadline, fake: true, writer: writer),
        );
        await started.future;
        timers.deadlineTimer.fire();
        await until(() => timers.graces.isNotEmpty);
        expect(writer.closes, 0, reason: 'no close while a write is pending');
        timers.graces.single.fire();
        final result = await run.outcome;
        expect((result as UpdateStop).code, 'deadline_exceeded');
        expect(writer.closes, 0);
        gate.complete();
        await until(() => writer.closes == 1);
        await pause();
        expect(writer.closes, 1);
      },
    );
  });

  group('proxy from the environment', () {
    late ServerSocket proxy;
    late List<String> firstLines;

    setUp(() async {
      proxy = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
      firstLines = [];
      proxy.listen((socket) {
        socket.listen((data) {
          firstLines.add(latin1.decode(data).split('\r\n').first);
          socket.destroy();
        }, onError: (Object _) {});
      });
    });

    tearDown(() => proxy.close());

    test('HTTPS_PROXY receives the CONNECT', () async {
      handlers['/a'] = (r) async => r.response.close();
      final stop = await stopOf(
        fetch(
          '/a',
          environment: {'HTTPS_PROXY': 'http://127.0.0.1:${proxy.port}'},
        ),
      );
      expect(stop.code, 'download_failed');
      expect(firstLines, ['CONNECT 127.0.0.1:${server.port} HTTP/1.1']);
    });

    test('NO_PROXY keeps a host off the proxy', () async {
      handlers['/a'] = (r) async {
        r.response.add(utf8.encode('direct'));
        await r.response.close();
      };
      final ok = await fetch(
        '/a',
        environment: {
          'HTTPS_PROXY': 'http://127.0.0.1:${proxy.port}',
          'NO_PROXY': '127.0.0.1',
        },
      );
      expect(ok, isTrue);
      expect(firstLines, isEmpty);
    });
  });
}

const Duration _deadline = Duration(seconds: 120);
const Duration _grace = Duration(seconds: 10);

/// The downloader's monotonic clock, moved by hand.
class _Clock {
  Duration now = Duration.zero;
  Duration call() => now;
}

class _FakeTimer implements Timer {
  _FakeTimer(this.duration, this._callback);

  final Duration duration;
  final void Function() _callback;
  bool cancelled = false;
  bool fired = false;

  void fire() {
    if (cancelled || fired) return;
    fired = true;
    _callback();
  }

  @override
  void cancel() => cancelled = true;

  @override
  bool get isActive => !cancelled && !fired;

  @override
  int get tick => fired ? 1 : 0;
}

/// The timer factory the downloader is given: nothing fires unless a test says.
class _Timers {
  final List<_FakeTimer> list = [];

  Timer create(Duration duration, void Function() callback) {
    final timer = _FakeTimer(duration, callback);
    list.add(timer);
    return timer;
  }

  Iterable<_FakeTimer> get graces => list.where((t) => t.duration == _grace);

  _FakeTimer get deadlineTimer => list.firstWhere((t) => t.duration != _grace);
}

/// A [PartWriter] that records, and fails or holds when told to.
class _Writer implements PartWriter {
  final List<int> bytes = [];
  int closes = 0;
  bool closeDone = false;
  bool failClose = false;
  bool holdClose = false;
  Future<void> Function(List<int> chunk)? onWrite;
  Future<void> Function()? onClose;

  String get text => utf8.decode(bytes);

  @override
  Future<void> write(List<int> chunk) async {
    final hook = onWrite;
    if (hook != null) await hook(chunk);
    bytes.addAll(chunk);
  }

  @override
  Future<void> close() async {
    closes++;
    if (holdClose) await Completer<void>().future;
    if (failClose) throw const FileSystemException('close failed');
    final hook = onClose;
    if (hook != null) await hook();
    closeDone = true;
  }
}
