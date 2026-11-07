import 'dart:convert';

import 'context.dart';

/// Placeholder for `fit-subject`; group 4 of native-cli-commit replaces it.
Future<int> runFitSubject(List<String> args, CommitContext ctx) async {
  ctx.writeErr(utf8.encode('fit-subject.sh: not ported yet\n'));
  return 1;
}
