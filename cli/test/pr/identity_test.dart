import 'package:specwright_cli/src/pr/identity.dart';
import 'package:test/test.dart';

import '../vcs/bash_support.dart';
import 'pair_support.dart';

// `sw pr identity` against `pr-pair.sh identity` (pr-pair.sh:180-182, 800-820, 1132-1136).

void main() {
  final skip = findBash() == null ? 'needs a bash' : null;
  late Scratch tmp;
  setUp(() => tmp = Scratch());
  tearDown(() => tmp.dispose());

  group('parseRepo', () {
    const forms = {
      'https://github.com/o/n': 'o/n',
      'https://github.com/o/n.git': 'o/n',
      'https://github.com/o/n/': 'o/n',
      'http://github.com/o/n': 'o/n',
      'https://user@github.com/o/n.git': 'o/n',
      'https://github.com:443/o/n': 'o/n',
      'ssh://git@github.com/o/n.git': 'o/n',
      'ssh://git@ssh.github.com:443/o/n.git': 'o/n',
      'git://github.com/o/n': 'o/n',
      'git@github.com:o/n.git': 'o/n',
      'github.com:o/n': 'o/n',
      'git@ssh.github.com:o/n': 'o/n',
      'https://GitHub.com./Owner/Name.git': 'Owner/Name',
      '  https://github.com/o/n  ': 'o/n',
      'https://github.com/o/n.git.git': 'o/n.git',
    };
    forms.forEach((url, repo) {
      test('reads ${url.trim()}', () => expect(parseRepo(url), repo));
    });

    for (final url in [
      'https://gitlab.com/o/n',
      'https://github.com/o',
      'https://github.com/o/n/extra',
      'https://github.com/o/n x',
      'https://evilgithub.com/o/n',
      'ftp://github.com/o/n',
      '',
      '/some/path',
    ]) {
      test('refuses "$url"', () => expect(parseRepo(url), isNull));
    }
  });

  group('the stops', () {
    Future<Ran> run(List<String> argv) async {
      final r = PairRun();
      return r.result(await runIdentity(r.ctx, argv));
    }

    test(
      'not-a-repo: no such directory, and a directory without git',
      () async {
        for (final d in ['${tmp.path}/missing', tmp.sub('plain').path]) {
          final r = await run([d]);
          expect(r.code, 1, reason: d);
          expect(r.json['ok'], false);
          expect(r.json['error'], 'not-a-repo');
          expect(r.json['message'], startsWith(d));
        }
      },
      skip: skip,
    );

    test('no-origin', () async {
      initRepo('${tmp.path}/r');
      final r = await run(['${tmp.path}/r']);
      expect(r.code, 1);
      expect(r.json['error'], 'no-origin');
      expect(r.json.keys, ['ok', 'error', 'message']);
    }, skip: skip);

    test('not-github names the fetch URL and every push URL', () async {
      initRepo('${tmp.path}/r', origin: 'https://gitlab.com/o/n');
      final r = await run(['${tmp.path}/r']);
      expect(r.code, 1);
      expect(r.json['error'], 'not-github');
      expect(r.json['fetch_url'], 'https://gitlab.com/o/n');
      expect(r.json['push_urls'], ['https://gitlab.com/o/n']);
      expect(r.json.keys, ['ok', 'error', 'message', 'fetch_url', 'push_urls']);
    }, skip: skip);

    test('a push URL that is not GitHub is not-github too', () async {
      initRepo('${tmp.path}/r', origin: 'https://github.com/o/n');
      git('${tmp.path}/r', [
        'remote',
        'set-url',
        '--push',
        'origin',
        'https://example.org/o/n',
      ]);
      final r = await run(['${tmp.path}/r']);
      expect(r.json['error'], 'not-github');
      expect(r.json['push_urls'], ['https://example.org/o/n']);
    }, skip: skip);

    test('mismatch: forks and mirrors as push targets', () async {
      initRepo('${tmp.path}/r', origin: 'https://github.com/o/n');
      git('${tmp.path}/r', [
        'remote',
        'set-url',
        '--push',
        'origin',
        'git@github.com:fork/n.git',
      ]);
      final r = await run(['${tmp.path}/r']);
      expect(r.code, 1);
      expect(r.json['error'], 'mismatch');
      expect(r.json['fetch'], 'o/n');
      expect(r.json['push'], ['fork/n']);
    }, skip: skip);

    test('a different case in a push URL is not a mismatch', () async {
      initRepo('${tmp.path}/r', origin: 'https://github.com/O/N');
      git('${tmp.path}/r', [
        'remote',
        'set-url',
        '--push',
        'origin',
        'git@github.com:o/n.git',
      ]);
      final r = await run(['${tmp.path}/r']);
      expect(r.code, 0);
      expect(r.json['repo'], 'O/N');
      expect(r.json['push'], ['o/n']);
    }, skip: skip);
  });

  group('the answer', () {
    test('owner, name, fetch and push in the script order', () async {
      initRepo('${tmp.path}/r', origin: 'git@github.com:acme/widgets.git');
      final r = PairRun();
      final code = await runIdentity(r.ctx, ['${tmp.path}/r']);
      final ran = r.result(code);
      expect(ran.code, 0);
      expect(ran.stdout.endsWith('\n'), isTrue);
      expect(ran.stdout.trimRight().contains('\n'), isFalse);
      expect(ran.json, {
        'ok': true,
        'repo': 'acme/widgets',
        'owner': 'acme',
        'name': 'widgets',
        'fetch': 'acme/widgets',
        'push': ['acme/widgets'],
      });
      expect(ran.json.keys, ['ok', 'repo', 'owner', 'name', 'fetch', 'push']);
    }, skip: skip);

    test('every push URL is read', () async {
      initRepo('${tmp.path}/r', origin: 'https://github.com/o/n');
      git('${tmp.path}/r', [
        'remote',
        'set-url',
        '--add',
        '--push',
        'origin',
        'https://github.com/o/n.git',
      ]);
      git('${tmp.path}/r', [
        'remote',
        'set-url',
        '--add',
        '--push',
        'origin',
        'ssh://git@github.com/o/n',
      ]);
      final r = PairRun();
      final ran = r.result(await runIdentity(r.ctx, ['${tmp.path}/r']));
      expect(ran.json['push'], ['o/n', 'o/n']);
    }, skip: skip);

    test('a directory inside the work tree is a repo too', () async {
      initRepo('${tmp.path}/r', origin: 'https://github.com/o/n');
      tmp.sub('r/deep/er');
      final r = PairRun();
      final ran = r.result(await runIdentity(r.ctx, ['${tmp.path}/r/deep/er']));
      expect(ran.json['repo'], 'o/n');
    }, skip: skip);
  });

  group('the arguments', () {
    test('exactly one directory', () async {
      for (final argv in [
        <String>[],
        ['a', 'b'],
      ]) {
        final r = PairRun();
        final ran = r.result(await runIdentity(r.ctx, argv));
        expect(ran.code, 2, reason: '$argv');
        expect(ran.json['error'], 'usage');
        expect(ran.json['message'], 'identity <dir>');
      }
    });

    test('an option is unknown', () async {
      final r = PairRun();
      final ran = r.result(await runIdentity(r.ctx, ['--x']));
      expect(ran.code, 2);
      expect(ran.json['error'], 'usage');
    });
  });
}
