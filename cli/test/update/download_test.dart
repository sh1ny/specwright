import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/update/download.dart';
import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:specwright_cli/src/update/stop.dart';
import 'package:test/test.dart';

// Design D4 and constraint C5 of native-cli-update: a release file is fetched
// in process over https only (the start URL and every redirect), file:// is a
// mirror, a deadline and a size cap stop it and delete the partial file, and
// the proxy comes from the environment. The server is a local TLS server with
// a self-signed certificate (fixtures/); the client under test trusts only it.

const _cert = 'test/update/fixtures/test_cert.pem';
const _key = 'test/update/fixtures/test_key.pem';

void main() {
  late Directory temp;
  late HttpServer server;
  late String base;
  late String dest;
  final handlers = <String, FutureOr<void> Function(HttpRequest)>{};
  final files = UpdateFileOps(environment: const {});

  HttpClient Function() trusting() => () {
    final context = SecurityContext(withTrustedRoots: false)
      ..setTrustedCertificatesBytes(File(_cert).readAsBytesSync());
    return HttpClient(context: context);
  };

  Future<bool> fetch(
    String path, {
    Duration deadline = const Duration(seconds: 20),
    int maxBytes = 1 << 20,
    Map<String, String> environment = const {},
    HttpClient Function()? factory,
    String? url,
  }) => downloadReleaseFile(
    url: url ?? '$base$path',
    dest: dest,
    name: 'sw-linux-x64',
    tag: 'v0.37.0',
    files: files,
    deadline: deadline,
    maxBytes: maxBytes,
    clientFactory: factory ?? trusting(),
    environment: environment,
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
      expect(File(dest).existsSync(), isFalse);
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
      expect(File(dest).existsSync(), isFalse);
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
      expect(File(dest).existsSync(), isFalse);
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

    test('a file over the cap is response_too_large, no part stays', () async {
      final source = File('${temp.path}/big')
        ..writeAsBytesSync(List.filled(5000, 0));
      final stop = await stopOf(
        fetch('', url: source.uri.toString(), maxBytes: 1000),
      );
      expect(stop.code, 'response_too_large');
      expect(File(dest).existsSync(), isFalse);
    });
  });

  group('bounds', () {
    test('the deadline stops a stalled body and deletes the part', () async {
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
      expect(File(dest).existsSync(), isFalse);
    });

    test('a body over the cap is response_too_large, part deleted', () async {
      handlers['/big'] = (r) async {
        r.response.add(List.filled(5000, 1));
        await r.response.close();
      };
      final stop = await stopOf(fetch('/big', maxBytes: 1000));
      expect(stop.code, 'response_too_large');
      expect(stop.message, contains('1000 bytes'));
      expect(File(dest).existsSync(), isFalse);
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
      expect(File(dest).existsSync(), isFalse);
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
