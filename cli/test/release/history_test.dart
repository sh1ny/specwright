// Tests of the primary file's history and the gates built on it (cli/lib/src/
// release/history.dart): the first-parent read, Releases, the bump-detection
// walk of `check --main`, the release-commit shape and the older-untagged gate.
// The walk cases come from the TestCheckMain evals; each runs real git.
import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:specwright_cli/src/release/git.dart';
import 'package:specwright_cli/src/release/history.dart';
import 'package:specwright_cli/src/release/settings.dart';
import 'package:specwright_cli/src/release/stop.dart';
import 'package:test/test.dart';

const _plain = r'^(\d+\.\d+\.\d+)$';

Matcher stops(String error, [List<String> parts = const []]) => throwsA(
  isA<ReleaseStop>()
      .having((e) => e.error, 'error', error)
      .having((e) => e.message, 'message', allOf(parts.map(contains).toList())),
);

void main() {
  late Directory root;
  late ReleaseGit rg;
  late List<VersionEntry> entries;

  String git(List<String> args) {
    final r = Process.runSync('git', [
      '-c',
      'user.name=t',
      '-c',
      'user.email=t@t.invalid',
      '-c',
      'commit.gpgsign=false',
      '-c',
      'core.autocrlf=false',
      ...args,
    ], workingDirectory: root.path);
    expect(r.exitCode, 0, reason: '${r.stderr}');
    return (r.stdout as String).trim();
  }

  void write(String rel, String content) {
    final file = File(p.join(root.path, rel))
      ..parent.createSync(recursive: true);
    file.writeAsBytesSync(utf8.encode(content));
  }

  String commit(String subject, [Map<String, String> files = const {}]) {
    files.forEach(write);
    git(['add', '-A']);
    git(['commit', '-q', '--allow-empty', '-m', subject]);
    return git(['rev-parse', 'HEAD']);
  }

  String bump(String version, [String subject = 'feat(b): bump']) =>
      commit(subject, {'VERSION': '$version\n'});

  List<VersionEntry> entriesFor(Map<String, String> files) {
    final yaml = StringBuffer('release:\n  enabled: true\n  version_files:\n');
    files.forEach((k, v) => yaml.writeln("    \"$k\": '$v'"));
    write('openspec/specwright.yaml', yaml.toString());
    return readReleaseSettings(root.path).entries();
  }

  setUp(() {
    root = Directory.systemTemp.createTempSync('sw-history-');
    git(['init', '-q', '-b', 'main']);
    entries = entriesFor({'VERSION': _plain});
    commit('initial', {'VERSION': '0.4.2\n'});
    rg = ReleaseGit(root.path);
  });
  tearDown(() => root.deleteSync(recursive: true));

  group('primaryHistory and Releases', () {
    test(
      'reads the primary file at each first-parent commit that touches it',
      () async {
        final first = git(['rev-parse', 'HEAD']);
        commit('chore: other file', {'other.txt': 'x\n'});
        final second = bump('0.5.0');
        git(['checkout', '-q', '-b', 'feat/x']);
        bump('0.6.0');
        git(['checkout', '-q', 'main']);
        git(['merge', '-q', '--no-ff', '--no-edit', 'feat/x']);
        final merge = git(['rev-parse', 'HEAD']);
        final hist = await primaryHistory(rg, entries, 'main');
        expect(hist, [(first, '0.4.2'), (second, '0.5.0'), (merge, '0.6.0')]);
      },
    );

    test('a file that reads none or two versions is null', () async {
      final twice = commit('twice', {'VERSION': '0.7.0\n0.8.0\n'});
      final none = commit('none', {'VERSION': 'no version\n'});
      final hist = await primaryHistory(rg, entries, 'main');
      expect(hist.skip(1), [(twice, null), (none, null)]);
    });

    test('a glob tracks which matching files exist at each commit', () async {
      final globbed = entriesFor({'pkg/*/VERSION': _plain});
      final a = commit('a and b', {
        'pkg/a/VERSION': '0.1.0\n',
        'pkg/b/VERSION': '0.1.0\n',
      });
      final both = commit('a only', {'pkg/a/VERSION': '0.2.0\n'});
      git(['rm', '-q', 'pkg/b/VERSION']);
      final gone = commit('drop b');
      final hist = await primaryHistory(rg, globbed, 'main');
      expect(hist, [(a, '0.1.0'), (both, null), (gone, '0.2.0')]);
    });

    test('Releases records each value at its first appearance', () {
      final rel = Releases([
        ('a', '0.1.0'),
        ('b', null),
        ('c', '0.2.0'),
        ('d', '0.1.0'),
        ('e', '0.3.0'),
      ]);
      expect(rel.first, {'0.1.0': 'a', '0.2.0': 'c', '0.3.0': 'e'});
      expect(rel.order, ['0.1.0', '0.2.0', '0.3.0']);
      expect(rel.before, {'0.1.0': null, '0.2.0': '0.1.0', '0.3.0': '0.1.0'});
      expect(rel.current, '0.3.0');
      expect(Releases(const []).current, isNull);
    });
  });

  group('tags', () {
    final rel = Releases([
      ('a', '0.1.0'),
      ('b', '0.2.0'),
      ('c', '0.3.0'),
      ('d', '0.4.0'),
    ]);

    test('the previous release is the highest lower tagged version', () {
      final prev = previousRelease('v{version}', rel, '0.3.0', {
        'v0.1.0',
        'v0.4.0',
      });
      expect((prev!.version, prev.sha, prev.basis), ('0.1.0', 'a', 'tag'));
    });

    test('with no lower tag it is the value read just before', () {
      final prev = previousRelease('v{version}', rel, '0.3.0', {'v0.4.0'});
      expect((prev!.version, prev.sha, prev.basis), ('0.2.0', 'b', 'history'));
      expect(previousRelease('v{version}', rel, '0.1.0', {}), isNull);
    });

    test('untagged versions follow the latest tagged one', () {
      final r = untaggedSinceLatest('v{version}', rel, {'v0.2.0'});
      expect(r.latest, '0.2.0');
      expect(r.versions, ['0.3.0', '0.4.0']);
    });

    test('with no tag only the current version is untagged', () {
      final r = untaggedSinceLatest('v{version}', rel, {});
      expect(r.latest, isNull);
      expect(r.versions, ['0.4.0']);
    });

    test('a local tag whose push failed is listed whatever the anchor', () {
      final r = untaggedSinceLatest(
        'v{version}',
        rel,
        {'v0.3.0'},
        local: {'v0.1.0'},
      );
      expect(r.latest, '0.3.0');
      expect(r.versions, ['0.1.0', '0.4.0']);
    });
  });

  group('the older-untagged gate', () {
    final rel = Releases([('a', '0.4.0'), ('b', '0.5.0'), ('c', '0.6.0')]);

    test('an older untagged version stops the newer one', () {
      expect(
        () => refuseOlderUntagged('v{version}', rel, {'v0.4.0'}, {}, '0.6.0'),
        stops('older_untagged', [
          '0.5.0',
          'publish 0.5.0 (tag v0.5.0) before 0.6.0',
        ]),
      );
    });

    test('the oldest untagged version itself passes', () {
      refuseOlderUntagged('v{version}', rel, {'v0.4.0'}, {}, '0.5.0');
    });

    test('everything tagged passes', () {
      refuseOlderUntagged(
        'v{version}',
        rel,
        {'v0.4.0', 'v0.5.0', 'v0.6.0'},
        {},
        '0.6.0',
      );
    });
  });

  group('the release commit shape', () {
    test('a squash commit ending (#n) passes', () async {
      await requireReleaseShape(rg, commit('feat(x): do x (#11)'));
    });

    test('a merge commit passes', () async {
      git(['checkout', '-q', '-b', 'feat/y']);
      commit('feat(y): do y');
      git(['checkout', '-q', 'main']);
      git([
        'merge',
        '-q',
        '--no-ff',
        '-m',
        'Merge pull request #12 from a/b',
        'feat/y',
      ]);
      await requireReleaseShape(rg, git(['rev-parse', 'HEAD']));
    });

    test('a replayed bump is rebase_release_commit', () async {
      final sha = commit('feat(x): task 2');
      await expectLater(
        requireReleaseShape(rg, sha),
        stops('rebase_release_commit', [
          sha.substring(0, 12),
          'merge or squash',
        ]),
      );
    });
  });

  group('the bump-detection walk', () {
    String head() => git(['rev-parse', 'HEAD']);
    void branch([String name = 'feat/b', String? at]) =>
        git(['checkout', '-q', '-b', name, ?at]);
    void squashOnMain(String version) {
      bump(version, 'feat(a): do a (#1)');
    }

    // feat/a merged to main at [mainVersion]; feat/b (from the initial
    // commit) bumped to [branchVersion].
    void twoBumps({
      String branchVersion = '0.5.0',
      String mainVersion = '0.5.0',
    }) {
      final base = head();
      squashOnMain(mainVersion);
      branch('feat/b', base);
      bump(branchVersion);
    }

    Future<void> ahead(String version) =>
        checkAheadOf(rg, entries, 'main', version);

    // The merge base's VERSION holds 0.4.2 twice (unreadable); main then
    // moves to 0.5.0 and feat/b starts at the base.
    void unreadableBase() {
      commit('chore: VERSION twice', {'VERSION': '0.4.2\n0.4.2\n'});
      final base = head();
      squashOnMain('0.5.0');
      branch('feat/b', base);
    }

    // origin/main and the merge base read [version]; feat/b starts there.
    void atMain([String version = '0.5.0', String? mainVersion]) {
      bump(version, 'chore: set version');
      final base = head();
      if (mainVersion != null) squashOnMain(mainVersion);
      branch('feat/b', base);
    }

    Matcher notAhead(List<String> parts) =>
        stops('version_not_ahead_of_main', ['bump', ...parts]);

    test('a duplicate bump is refused, naming both versions', () async {
      twoBumps();
      await expectLater(ahead('0.5.0'), notAhead(['0.5.0', 'main']));
      try {
        await ahead('0.5.0');
      } on ReleaseStop catch (e) {
        expect(e.extra, {
          'version': '0.5.0',
          'main_version': '0.5.0',
          'main': 'main',
        });
      }
    });

    test('main ahead of the bump is refused', () async {
      twoBumps(mainVersion: '0.6.0');
      await expectLater(ahead('0.5.0'), notAhead(['0.5.0', '0.6.0']));
    });

    test('a bump ahead of main passes', () async {
      branch();
      bump('0.5.0');
      await ahead('0.5.0');
    });

    test('a branch that did not bump passes', () async {
      final base = head();
      squashOnMain('0.5.0');
      branch('feat/b', base);
      commit('feat(b): work', {'src/b.txt': 'b\n'});
      await ahead('0.4.2');
    });

    test('an edit that keeps the version is no bump', () async {
      final base = head();
      squashOnMain('0.5.0');
      branch('feat/b', base);
      commit('feat(b): note', {'VERSION': '0.4.2\nchannel: stable\n'});
      await ahead('0.4.2');
    });

    test('a bump reverted on the branch is no bump', () async {
      final base = head();
      squashOnMain('0.5.0');
      branch('feat/b', base);
      bump('0.5.0');
      bump('0.4.2', 'feat(b): drop the bump');
      await ahead('0.4.2');
    });

    test('a duplicate stays refused after main is merged in', () async {
      twoBumps();
      git(['merge', '-q', '--no-edit', 'main']);
      await expectLater(ahead('0.5.0'), notAhead(['0.5.0']));
    });

    test('a main with no version passes', () async {
      git(['rm', '-q', 'VERSION']);
      commit('drop VERSION');
      branch();
      bump('0.1.0');
      await ahead('0.1.0');
    });

    test('a main whose file matches twice has no readable version', () async {
      final base = head();
      commit('chore: VERSION twice', {'VERSION': '0.5.0\n0.5.0\n'});
      branch('feat/b', base);
      bump('0.5.0');
      await ahead('0.5.0');
    });

    test('an unreadable base repaired by dedupe is no bump', () async {
      unreadableBase();
      commit('fix(b): drop the duplicate', {'VERSION': '0.4.2\n'});
      await ahead('0.4.2');
    });

    test('a repair then a bump is refused when main is level', () async {
      unreadableBase();
      commit('fix(b): drop the duplicate', {'VERSION': '0.4.2\n'});
      bump('0.5.0');
      await expectLater(ahead('0.5.0'), notAhead(['0.5.0']));
    });

    test('a repair and bump in one commit is refused', () async {
      unreadableBase();
      bump('0.5.0');
      await expectLater(ahead('0.5.0'), notAhead(['0.5.0']));
    });

    test('a bump reverted through an unreadable version is no bump', () async {
      final base = head();
      squashOnMain('0.5.0');
      branch('feat/b', base);
      bump('0.5.0');
      commit('feat(b): drop the bump, VERSION twice', {
        'VERSION': '0.4.2\n0.4.2\n',
      });
      commit('fix(b): drop the duplicate', {'VERSION': '0.4.2\n'});
      await ahead('0.4.2');
    });

    test(
      'a bump reverted between two unreadable versions is no bump',
      () async {
        atMain();
        commit('feat(b): VERSION twice', {'VERSION': '0.6.0\n0.6.0\n'});
        commit('feat(b): revert, VERSION twice', {'VERSION': '0.5.0\n0.5.0\n'});
        commit('fix(b): drop the duplicate', {'VERSION': '0.5.0\n'});
        await ahead('0.5.0');
      },
    );

    test(
      'an unreadable bump reverted by a readable version is no bump',
      () async {
        atMain();
        commit('feat(b): VERSION twice', {'VERSION': '0.6.0\n0.6.0\n'});
        commit('feat(b): revert', {'VERSION': '0.5.0\n'});
        await ahead('0.5.0');
      },
    );

    test(
      'unreadable edits that keep the matched versions still bump',
      () async {
        atMain('0.5.0', '0.6.0');
        commit('feat(b): VERSION twice', {'VERSION': '0.6.0\n0.6.0\n'});
        commit('feat(b): VERSION three times', {
          'VERSION': '0.6.0\n0.6.0\n0.6.0\n',
        });
        commit('fix(b): one line', {'VERSION': '0.6.0\n'});
        git(['merge', '-q', '--no-edit', 'main']);
        await expectLater(ahead('0.6.0'), notAhead(['0.6.0', 'main']));
      },
    );

    test('keeping the lower of the parent versions drops the bump', () async {
      commit('chore: VERSION lists two', {'VERSION': '0.4.2\n0.5.0\n'});
      final base = head();
      squashOnMain('0.5.0');
      branch('feat/b', base);
      bump('0.6.0');
      commit('feat(b): VERSION lists two', {'VERSION': '0.6.0\n0.5.0\n'});
      bump('0.5.0', 'feat(b): keep 0.5.0');
      await ahead('0.5.0');
    });

    test('a dedupe to the highest of the versions keeps the bump', () async {
      final base = head();
      squashOnMain('0.6.0');
      branch('feat/b', base);
      bump('0.6.0');
      commit('feat(b): VERSION lists two', {'VERSION': '0.6.0\n0.5.0\n'});
      commit('fix(b): drop the duplicate', {'VERSION': '0.6.0\n'});
      await expectLater(ahead('0.6.0'), notAhead([]));
    });

    test('a bump made through an unreadable version is refused after main merges in', () async {
      final base = head();
      squashOnMain('0.5.0');
      branch('feat/b', base);
      commit('feat(b): VERSION lists two', {'VERSION': '0.4.2\n0.5.0\n'});
      commit('fix(b): keep 0.5.0', {'VERSION': '0.5.0\n'});
      git(['merge', '-q', '--no-edit', 'main']);
      await expectLater(ahead('0.5.0'), notAhead(['0.5.0']));
    });

    test('a base repaired the same way on both sides passes', () async {
      commit('chore: VERSION lists two', {'VERSION': '0.4.2\n0.5.0\n'});
      final base = head();
      bump('0.5.0', 'fix: keep 0.5.0');
      branch('feat/b', base);
      bump('0.5.0', 'fix(b): keep 0.5.0');
      await ahead('0.5.0');
    });

    test('a stray version line added and removed is no bump', () async {
      atMain();
      commit('chore(b): stray line', {'VERSION': '0.5.0\n0.4.2\n'});
      commit('fix(b): drop the stray line', {'VERSION': '0.5.0\n'});
      await ahead('0.5.0');
    });

    test('a commit that removes the file ends the walk with no bump', () async {
      final base = head();
      squashOnMain('0.5.0');
      branch('feat/b', base);
      bump('0.5.0');
      git(['rm', '-q', 'VERSION']);
      commit('feat(b): drop VERSION');
      await ahead('0.4.2');
    });

    test('a missing main ref is no_main', () async {
      await expectLater(
        checkAheadOf(rg, entries, 'origin/nope', '0.4.2'),
        stops('no_main', ['origin/nope']),
      );
    });
  });

  group('ref helpers', () {
    test('detectMain prefers the settings, then main, then master', () async {
      expect(await detectMain(rg, null), 'main');
      expect(await detectMain(rg, 'trunk'), 'trunk');
      git(['branch', 'trunk']);
      expect(await detectMain(rg, 'trunk'), 'trunk');
    });

    test('subjectPr reads a squash suffix or a merge subject', () {
      expect(subjectPr('feat(x): do x (#11)'), 11);
      expect(subjectPr('Merge pull request #12 from a/b'), 12);
      expect(subjectPr('merge: x'), isNull);
    });
  });
}
