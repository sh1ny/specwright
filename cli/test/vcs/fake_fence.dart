import 'dart:io';

import 'package:specwright_cli/src/vcs/scripts.dart';

/// A stand-in for the in-process fence ([VcsScripts.fence]): it logs the
/// arguments of each call to `<prefix>.log` in [dir] (every argument followed
/// by `|`, one line per call) and answers from `<prefix>.out`, `<prefix>.err`
/// and `<prefix>.rc` there, as the `as.sh` stand-ins of these tests did.
FencedRun fakeFence(Directory dir, {String prefix = 'as'}) =>
    (repo, argv) async {
      File('${dir.path}/$prefix.log').writeAsStringSync(
        '${argv.map((a) => '$a|').join()}\n',
        mode: FileMode.append,
      );
      String read(String ext) {
        final f = File('${dir.path}/$prefix.$ext');
        return f.existsSync() ? f.readAsStringSync() : '';
      }

      final rc = File('${dir.path}/$prefix.rc');
      return TextResult(
        rc.existsSync() ? int.parse(rc.readAsStringSync().trim()) : 0,
        read('out'),
        read('err'),
      );
    };
