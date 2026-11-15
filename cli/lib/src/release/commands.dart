import 'dart:io';

import 'package:path/path.dart' as p;

import '../pr/context.dart';
import '../pr/pair.dart' show PairStop;
import '../pr/settings_commands.dart' show readVcsSettings;
import '../settings/rules.dart' show SettingsStop;
import 'git.dart';
import 'history.dart';
import 'notes.dart';
import 'publish.dart';
import 'settings.dart';
import 'status.dart';
import 'stop.dart';
import 'versions.dart';

const String _usageText =
    'usage: sw release [--dir <repo>] check [--main ref] [--branch name] | '
    'bump --to V | status --version V [--main ref] [--store dir] | '
    'untagged [--main ref] [--local] | publish --version V | '
    'notes --proposal <file>';

/// One release call's answer: the one JSON [document] and the exit [code]
/// (0 done, 1 a stop, 2 usage, 3 a git or network call failed).
typedef ReleaseOutcome = ({Map<String, Object?> document, int code});

/// Runs one `sw release` call from its arguments (`[--dir <repo>] <sub>
/// [options]`) in [cwd]. A stop, a bound that cut a network command and an
/// uncaught error each become the one document the caller prints; nothing is
/// thrown.
Future<ReleaseOutcome> releaseOutcome(
  List<String> argv, {
  required String cwd,
}) async {
  try {
    return (document: await _run(argv, cwd), code: 0);
  } on ReleaseStop catch (stop) {
    return (document: stop.toJson(), code: stop.code);
  } on ReleaseCut catch (cut) {
    return (document: cutStop(cut).toJson(), code: 3);
  } on SettingsStop catch (stop) {
    return (
      document: ReleaseStop(stop.error, stop.message).toJson(),
      code: stop.code,
    );
  } on PairStop catch (stop) {
    return (
      document: ReleaseStop(
        stop.error,
        stop.message,
        extra: stop.extra,
      ).toJson(),
      code: stop.code,
    );
  } on Object catch (error) {
    final message = error is StateError ? error.message : error;
    return (
      document: {
        'ok': false,
        'error': 'internal_error',
        'message': '${error.runtimeType}: $message',
      },
      code: 1,
    );
  }
}

ReleaseStop _usage(String message) => ReleaseStop('usage', message, code: 2);

/// Splits [argv] into option values and flags by the [options] spec (option
/// name to key); a name in [flags] takes no value.
Map<String, String> _options(
  List<String> argv,
  Map<String, String> options, {
  Set<String> flags = const {},
}) {
  final found = <String, String>{};
  var i = 0;
  while (i < argv.length) {
    final t = argv[i];
    if (flags.contains(t)) {
      found[options[t]!] = 'true';
      i++;
    } else if (options.containsKey(t)) {
      if (i + 1 >= argv.length) throw _usage('$t needs a value');
      found[options[t]!] = argv[i + 1];
      i += 2;
    } else if (t.startsWith('--')) {
      throw _usage('unknown option $t');
    } else {
      throw _usage('unexpected argument $t');
    }
  }
  return found;
}

const _storeOptions = {
  '--store': 'store',
  '--store-main': 'store-main',
  '--store-prefix': 'store-prefix',
};

const _commands = {
  'check': {'--main': 'main', '--branch': 'branch'},
  'bump': {'--to': 'to'},
  'status': {
    '--version': 'version',
    '--main': 'main',
    '--base': 'base',
    ..._storeOptions,
  },
  'untagged': {'--main': 'main', '--local': 'local'},
  'publish': {
    '--version': 'version',
    '--main': 'main',
    '--base': 'base',
    ..._storeOptions,
  },
};

String? _value(Map<String, String> a, String key) {
  final v = a[key];
  return v == null || v.isEmpty ? null : v;
}

Future<Map<String, Object?>> _run(List<String> argv, String cwd) async {
  var rest = [...argv];
  String? dir;
  if (rest.isNotEmpty && rest.first == '--dir') {
    if (rest.length < 2) throw _usage('--dir needs a value');
    dir = rest[1];
    rest = rest.sublist(2);
  }
  // before the repository and the opt-in gate: one file, no git, no network
  if (rest.isNotEmpty && rest.first == 'notes') {
    return notesDocument(
      _options(rest.sublist(1), {'--proposal': 'proposal'}),
      cwd,
    );
  }
  if (rest.isEmpty || !_commands.containsKey(rest.first)) {
    throw _usage(_usageText);
  }
  final command = rest.first;
  final a = _options(
    rest.sublist(1),
    _commands[command]!,
    flags: {if (command == 'untagged') '--local'},
  );
  final start = dir ?? cwd;
  // the settings at the nearest `.git` are checked before git starts, so a
  // misread line stops with bad_settings before any git call
  final candidate = _nearestRepo(p.absolute(start));
  if (candidate != null) readReleaseSettings(candidate);
  final top = await ReleaseGit(start).run(['rev-parse', '--show-toplevel']);
  if (top.exitCode != 0 || trimmed(top.stdout).isEmpty) {
    throw ReleaseStop('not_a_repo', '$start is not inside a git work tree');
  }
  final root = p.normalize(trimmed(top.stdout));
  final settings = readReleaseSettings(root)..gate();
  final git = ReleaseGit(root);
  return switch (command) {
    'check' => checkDocument(git, settings, a),
    'bump' => bumpDocument(git, settings, a),
    'status' => statusDocument(git, settings, statusArgs(a)),
    'untagged' => untaggedDocument(git, settings, a),
    _ => publishDocument(git, settings, statusArgs(a)),
  };
}

/// The nearest directory at or above [start] that holds a `.git` entry (a
/// directory, or the file of a worktree or submodule), or null.
String? _nearestRepo(String start) {
  var dir = p.normalize(start);
  while (true) {
    if (FileSystemEntity.typeSync(p.join(dir, '.git'), followLinks: false) !=
        FileSystemEntityType.notFound) {
      return dir;
    }
    final parent = p.dirname(dir);
    if (parent == dir) return null;
    dir = parent;
  }
}

/// The status options of the parsed arguments [a].
StatusArgs statusArgs(Map<String, String> a) => StatusArgs(
  version: _value(a, 'version'),
  main: _value(a, 'main'),
  base: _value(a, 'base'),
  store: _value(a, 'store'),
  storeMain: _value(a, 'store-main'),
  storePrefix: _value(a, 'store-prefix'),
);

/// `check [--main ref] [--branch name]`: the version files in the working
/// tree (with a branch: at its tip, resolved now), and with `--main` that a
/// bumped branch is greater than the main ref's version. On GitButler the
/// workspace commit is HEAD, so `--main` without `--branch` is a usage stop.
Future<Map<String, Object?>> checkDocument(
  ReleaseGit git,
  ReleaseSettings settings,
  Map<String, String> a,
) async {
  final branch = _value(a, 'branch');
  final main = _value(a, 'main');
  // --main compares the change branch with main: on GitButler HEAD is the
  // workspace commit, so it needs the branch. A plain check (the bump task's
  // verification) reads the working tree, as on Git.
  if (branch == null && main != null) {
    final vcs = await readVcsSettings(
      PrContext(
        scriptsDir: '',
        bash: '',
        writeOut: (_) {},
        writeErr: (_) {},
        cwd: git.root,
      ),
      code: git.root,
      repo: git.root,
      role: 'code',
    );
    if (vcs.backend == 'gitbutler') {
      throw _usage(
        'vcs: gitbutler needs --branch <prefix>/<change-name> with --main: HEAD is the workspace commit, not the change branch',
      );
    }
  }
  final entries = settings.entries();
  var tip = 'HEAD';
  if (branch != null) {
    // resolved now, on every call: never a SHA from the caller, never HEAD
    final r = await git.run([
      'rev-parse',
      '--verify',
      '--quiet',
      'refs/heads/$branch^{commit}',
    ]);
    if (r.exitCode != 0 || trimmed(r.stdout).isEmpty) {
      throw ReleaseStop(
        'branch_not_found',
        '${git.root} has no local branch $branch',
      );
    }
    tip = trimmed(r.stdout);
  }
  final read = await agree(
    branch != null ? CommitTree(git.root, tip) : WorkTree(git.root),
    entries,
  );
  if (main != null) {
    await checkAheadOf(git, entries, main, read.version, tip: tip);
  }
  return {'ok': true, 'version': read.version, 'files': read.files};
}

/// `bump --to MAJOR.MINOR.PATCH`: rewrites the captured version in every
/// version file. Never commits.
Future<Map<String, Object?>> bumpDocument(
  ReleaseGit git,
  ReleaseSettings settings,
  Map<String, String> a,
) async {
  settings.gate(rebase: true);
  final target = _value(a, 'to');
  if (target == null) throw _usage('bump needs --to MAJOR.MINOR.PATCH');
  return (await bump(git.root, settings.entries(), target)).toJson();
}

/// `untagged [--main ref] [--local]`: the versions in main's history of the
/// primary file after the latest tagged one that are not published, oldest
/// first. Published is a tag on origin; `--local`, or no origin remote, counts
/// a local tag and makes no network call.
Future<Map<String, Object?>> untaggedDocument(
  ReleaseGit git,
  ReleaseSettings settings,
  Map<String, String> a,
) async {
  final main = await loadMain(git, settings, _value(a, 'main'));
  final local = a.containsKey('local') || await git.originUrl() == null;
  final tags = local ? await git.localTags() : await git.publishedTags();
  final r = untaggedSinceLatest(
    settings.tag,
    main.rel,
    tags,
    local: await git.localTags(),
  );
  return {
    'ok': true,
    'main': main.ref,
    'tags': local ? 'local' : 'origin',
    'latest_tagged': r.latest,
    'untagged': [
      for (final u in r.versions)
        {
          'version': u,
          'tag': tagFor(settings.tag, u),
          'release_commit': main.rel.first[u],
        },
    ],
  };
}

/// `notes --proposal <file>`: parses one proposal's `## Release Notes`
/// section. No repository, no git or network call, and no `release.enabled`.
/// A relative path is read from [cwd].
Map<String, Object?> notesDocument(Map<String, String> a, String cwd) {
  final path = _value(a, 'proposal');
  if (path == null) throw _usage('notes needs --proposal <file>');
  final file = File(p.join(cwd, path));
  if (!file.existsSync()) throw _usage('--proposal file not found: $path');
  final size = file.lengthSync();
  const limit = '${maxProposal ~/ 1024} KB';
  if (size > maxProposal) {
    throw ReleaseStop(
      'release_notes_invalid',
      '$path is $size bytes, over the $limit limit',
      extra: {
        'errors': [
          {'line': null, 'message': 'the proposal is over the $limit limit'},
        ],
      },
    );
  }
  final parsed = parseReleaseNotes(lossy(file.readAsBytesSync()));
  if (parsed == null) {
    throw ReleaseStop(
      'no_release_notes',
      "$path has no '## Release Notes' section",
    );
  }
  if (parsed.errors.isNotEmpty) {
    throw ReleaseStop(
      'release_notes_invalid',
      '$path: ${parsed.errors.map((e) => 'line ${e.line}: ${e.message}').join('; ')}',
      extra: {
        'errors': [
          for (final e in parsed.errors) {'line': e.line, 'message': e.message},
        ],
      },
    );
  }
  return {
    'ok': true,
    'summary': parsed.summary,
    'items': {
      for (final h in noteHeadings)
        if (parsed.items.containsKey(h))
          h: [
            for (final i in parsed.items[h]!)
              {'text': i.text, 'line': itemLine(i.text, '<pr>')},
          ],
    },
  };
}
