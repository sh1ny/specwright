import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:path/path.dart' as p;

import '../commands/version.dart';
import '../process/launch.dart';
import 'chmod.dart';
import 'file_ops.dart';
import 'stop.dart';

const int _oneMiB = 1024 * 1024;

/// The outcome of [checkBinary]: [detail] says what failed when [ok] is false.
class BinaryCheck {
  BinaryCheck(this.ok, this.detail);

  final bool ok;
  final String detail;
}

/// The SHA-256 of the file at [path], as 64 lowercase hex digits.
String fileSha(String path) {
  final out = _DigestSink();
  final input = sha256.startChunkedConversion(out);
  final file = File(path).openSync();
  try {
    while (true) {
      final chunk = file.readSync(_oneMiB);
      if (chunk.isEmpty) break;
      input.add(chunk);
    }
  } finally {
    file.closeSync();
  }
  input.close();
  return out.digest.toString();
}

class _DigestSink implements Sink<Digest> {
  late Digest digest;

  @override
  void add(Digest data) => digest = data;

  @override
  void close() {}
}

/// Runs [file] as `<file> version --json` and decides whether it is the `sw`
/// of [version]: it must exit 0 within [deadline] (10 s) with at most [cap]
/// (1 MiB) on each of stdout and stderr, and print one JSON object whose
/// `version` is [version] and whose `interface` is [expectedInterface]. The
/// run is the one self-check a downloaded or placed binary gets, and nothing
/// else of it runs before its hash has matched (D6 of native-cli-update).
///
/// A downloaded binary is checked against the running binary's
/// interfaceVersion, never by reading a script. The default for
/// [expectedInterface] is that constant, which the pin test keeps equal to
/// `SW_INTERFACE` of the same commit; reading `SW_INTERFACE` out of the
/// download's `sw-path.sh` text was rejected, because it ties `sw` to a script
/// that `native-cli-retire-scripts` removes (constraint C6).
Future<BinaryCheck> checkBinary(
  String file, {
  required String version,
  int expectedInterface = interfaceVersion,
  Duration deadline = const Duration(seconds: 10),
  int cap = _oneMiB,
}) async {
  BinaryCheck fail(String detail) => BinaryCheck(false, detail);
  final path = p.absolute(file);
  if (!File(path).existsSync()) {
    return fail('$path does not exist (expected sw $version)');
  }
  final LaunchResult result;
  try {
    result = await launch(
      [path, 'version', '--json'],
      cwd: p.dirname(path),
      stdoutCap: cap,
      deadline: deadline,
    );
  } on Object catch (e) {
    return fail('$path cannot be run: $e');
  }
  if (result.startFailed) {
    return fail('$path cannot be run: ${_text(result.stderr).trim()}');
  }
  if (result.timedOut) {
    return fail(
      '$path version --json passed its deadline (${deadline.inSeconds} s)',
    );
  }
  if (result.outputTooLarge || result.stderr.length > cap) {
    return fail('$path version --json wrote more than 1 MiB');
  }
  if (result.exitCode != 0) {
    return fail('$path version --json exited ${result.exitCode}');
  }
  final Object? report;
  try {
    report = jsonDecode(utf8.decode(result.stdout));
  } on FormatException {
    return fail('$path version --json did not print one JSON object');
  }
  if (report is! Map) {
    return fail('$path version --json did not print one JSON object');
  }
  final reported = report['version'];
  final reportedInterface = report['interface'];
  if (reported is! String || reportedInterface is! int) {
    return fail('$path version --json has no version or interface field');
  }
  if (reported != version) {
    return fail('$path reports version $reported, not $version');
  }
  if (reportedInterface != expectedInterface) {
    return fail(
      '$path reports interface $reportedInterface, '
      'not interface $expectedInterface of the running sw',
    );
  }
  return BinaryCheck(true, '');
}

String _text(List<int> bytes) => utf8.decode(bytes, allowMalformed: true);

/// Places the checked file [part] at [finalPath] and returns the action:
/// `installed`, `replaced` (another file was there) or `kept` (the same file,
/// whose own check still passes, was there).
///
/// The caller has checked [part] (its SHA-256 [partSha] against the release,
/// then [checkBinary]) and owns every part file it made: a stop leaves them
/// for its cleanup. The notice, when [noticePart] is given, goes first: it is
/// renamed to [noticeFinal] unless that already holds [noticeSha] (a
/// concurrent run placed it), and a failure there is `notice_write_failed`
/// with the binary untouched (ADR 0032). A binary is replaced only by a rename
/// of the checked part; a rename that fails is `sw_in_use` unless another run
/// has placed the same file meanwhile.
///
/// The running file ([running], default `Platform.resolvedExecutable`) is
/// never renamed or moved: a [part] that is it is refused (D7 of
/// native-cli-update). Every file operation goes through [files].
///
/// [renameHook] and [noticeRenameHook] are the evals' test seams
/// (`SPECWRIGHT_TEST_RENAME` = `die` | `fail` | `race`, and
/// `SPECWRIGHT_TEST_NOTICE_RENAME` = `fail` | `race`), as `update.sh` had
/// them: `die` ends the process with status 9 through [exitProcess] between
/// the checks and the binary rename, `fail` makes the rename fail, and `race`
/// first copies the part to the final path (as another run would) and then
/// makes the rename fail. The copy is not a counted operation: it stands for
/// another process.
Future<String> placeChecked({
  required UpdateFileOps files,
  required String part,
  required String finalPath,
  required String partSha,
  required String version,
  required String asset,
  required String ref,
  String? noticePart,
  String? noticeFinal,
  String? noticeSha,
  String? running,
  int expectedInterface = interfaceVersion,
  String? renameHook,
  String? noticeRenameHook,
  void Function(int code)? exitProcess,
}) async {
  if (_sameFile(part, running ?? Platform.resolvedExecutable)) {
    throw UpdateStop(
      'sw_in_use',
      '${_posix(part)} is the running sw, which is never moved; run '
          'sw-install from a copy and rerun the install',
    );
  }
  if (noticePart != null && noticeFinal != null && noticeSha != null) {
    _placeNotice(
      files,
      noticePart,
      noticeFinal,
      noticeSha,
      ref,
      noticeRenameHook,
    );
  }
  Future<bool> sameAndRunnable() async =>
      File(finalPath).existsSync() &&
      fileSha(finalPath) == partSha &&
      (await checkBinary(
        finalPath,
        version: version,
        expectedInterface: expectedInterface,
      )).ok;

  var action = 'installed';
  if (File(finalPath).existsSync()) {
    action = 'replaced';
    if (await sameAndRunnable()) return 'kept';
  }
  if (renameHook == 'die') {
    (exitProcess ?? exit)(9);
    throw StateError('the process did not end');
  }
  try {
    if (renameHook == 'fail' || renameHook == 'race') {
      if (renameHook == 'race') {
        File(part).copySync(finalPath);
        makeExecutable(finalPath);
      }
      throw const FileSystemException('rename blocked');
    }
    files.rename(part, finalPath);
  } on FileSystemException {
    files.remove(part);
    if (await sameAndRunnable()) return 'kept';
    throw UpdateStop(
      'sw_in_use',
      '${_posix(finalPath)} cannot be replaced by the checked $asset of '
          'release $ref; stop the program running it and rerun the install',
    );
  }
  return action;
}

/// Places the notice once, after the binary's checks: a matching notice that
/// is there already (a concurrent run's) is success.
void _placeNotice(
  UpdateFileOps files,
  String part,
  String finalPath,
  String expected,
  String ref,
  String? hook,
) {
  bool matches() {
    try {
      return File(finalPath).existsSync() && fileSha(finalPath) == expected;
    } on FileSystemException {
      return false;
    }
  }

  if (matches()) return;
  try {
    if (hook == 'fail' || hook == 'race') {
      if (hook == 'race') File(part).copySync(finalPath);
      throw const FileSystemException('notice rename blocked');
    }
    files.rename(part, finalPath);
  } on FileSystemException catch (e) {
    if (!matches()) {
      throw UpdateStop(
        'notice_write_failed',
        'THIRD_PARTY_NOTICES.txt of release $ref cannot be placed at '
            '${_posix(finalPath)}: ${e.osError?.message ?? e.message}; '
            'the binary was not replaced',
      );
    }
  }
}

bool _sameFile(String a, String b) {
  if (p.equals(p.absolute(a), p.absolute(b))) return true;
  try {
    return p.equals(
      File(a).resolveSymbolicLinksSync(),
      File(b).resolveSymbolicLinksSync(),
    );
  } on FileSystemException {
    return false;
  }
}

String _posix(String path) => path.replaceAll(r'\', '/');
