import 'dart:io';

import '../vcs/document.dart' show decodeJson, decodeJsonBytes, readBounded;
import 'lifecycle.dart';
import 'options.dart';
import 'packs.dart';

// pack-docs of `scripts/update.sh`: reads the enabled packs' resolved document
// paths from `<code>/openspec/.specwright/packs.json` and the templates from
// the download (`<download>/packs/<name>/<template>`), creates each missing
// document (parents too), never overwrites one. It needs no journal and no
// lock. A path that is absolute, has `..`, leaves the code toplevel or names a
// directory, or a template the download lacks, is a refusal found before the
// first write.

final RegExp _unsafe = RegExp(r'^([/\\]|[A-Za-z]:)');

Map<String, Object?> _doc(
  String error,
  String message,
  List<Object?> documents, [
  Map<String, Object?> extra = const {},
]) => {
  'ok': false,
  'interface': updateInterface,
  'subcommand': 'pack-docs',
  'error': error,
  'message': message,
  ...extra,
  'documents': documents,
};

/// `sw update pack-docs`: the document and its exit status.
Future<(Map<String, Object?>, int)> packDocs(UpdateRun r) async {
  final download = r.download;
  final top = await r.repo.codeTop();
  final recordFile = '${r.state}/packs.json';
  var data = <String, Object?>{};
  if (File(recordFile).existsSync()) {
    try {
      final decoded = decodeJson(
        decodeJsonBytes(readBounded(recordFile), recordFile),
      );
      if (decoded is! Map || decoded['packs'] is! Map) {
        throw const FormatException('not a record with a packs object');
      }
      data = Map<String, Object?>.from(decoded);
    } on FormatException catch (e) {
      return (
        _doc(
          'packs_record_unreadable',
          'openspec/.specwright/packs.json is not readable (${e.message})',
          const [],
        ),
        1,
      );
    } on FileSystemException catch (e) {
      return (
        _doc(
          'packs_record_unreadable',
          'openspec/.specwright/packs.json is not readable (${e.message})',
          const [],
        ),
        1,
      );
    }
  }
  final refusals = <Map<String, Object?>>[];
  final work = <(String, String, String, String)>[];
  final packs = (data['packs'] as Map?) ?? const {};
  for (final e in packs.entries) {
    final n = '${e.key}';
    final entry = e.value;
    final docs = entry is Map ? entry['documents'] : null;
    if (!isPackName(n) || docs is! Map || docs.isEmpty) continue;
    final manifest = readManifest('$download/packs/$n').data;
    final declared = manifest?['documents'];
    for (final d in docs.entries) {
      final did = '${d.key}';
      final path = d.value;
      final decl = declared is Map ? declared[did] : null;
      final tpl = decl is Map ? decl['template'] : null;
      final why = path is String
          ? docPathProblem(top, path)
          : 'is not a string';
      if (why != null) {
        refusals.add({
          'code': 'pack_doc_path',
          'pack': n,
          'document': did,
          'path': path,
          'message':
              'document $did of pack $n: the path $path $why. Nothing was '
              'written',
        });
      } else if (!(tpl is String &&
          !_unsafe.hasMatch(tpl) &&
          !tpl.split(RegExp(r'[/\\]')).contains('..') &&
          File('$download/packs/$n/$tpl').existsSync())) {
        refusals.add({
          'code': 'pack_doc_template',
          'pack': n,
          'document': did,
          'path': path,
          'message':
              'document $did of pack $n: the download has no template for '
              'it. Nothing was written',
        });
      } else {
        work.add((n, did, path as String, '$download/packs/$n/$tpl'));
      }
    }
  }
  if (refusals.isNotEmpty) {
    return (
      _doc('refused', '${refusals.first['message']}', const [], {
        'refusals': refusals,
      }),
      1,
    );
  }
  final out = <Map<String, Object?>>[];
  for (final (n, did, path, tpl) in work) {
    final target = '$top/$path';
    var status = 'kept';
    if (FileSystemEntity.typeSync(target) == FileSystemEntityType.notFound) {
      try {
        final bytes = File(tpl).readAsBytesSync();
        // a regular file in the way throws: a failure, never `kept`
        Directory(File(target).parent.path).createSync(recursive: true);
        try {
          // an exclusive create never replaces a document made since the check
          File(target).createSync(exclusive: true);
        } on FileSystemException {
          if (File(target).existsSync()) {
            out.add({'pack': n, 'id': did, 'path': path, 'status': 'kept'});
            continue;
          }
          rethrow;
        }
        try {
          File(target).writeAsBytesSync(bytes, flush: true);
        } on FileSystemException {
          File(target).deleteSync(); // never a partial document
          rethrow;
        }
        status = 'created';
      } on FileSystemException catch (e) {
        final os = e.osError;
        return (
          _doc(
            'pack_doc_write_failed',
            'document $did of pack $n: could not write $path '
                '(${e.message}${os == null ? '' : ': ${os.message}'}). No '
                'partial document was left; rerun pack-docs once the cause is '
                'fixed',
            out,
          ),
          1,
        );
      }
    }
    out.add({'pack': n, 'id': did, 'path': path, 'status': status});
  }
  return (
    {
      'ok': true,
      'interface': updateInterface,
      'subcommand': 'pack-docs',
      'documents': out,
    },
    0,
  );
}
