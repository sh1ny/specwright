// Run by file_ops_test.dart as a real process: makes the directories named by
// the arguments through UpdateFileOps with the real exit function, so the test
// sees the process end with 137.
import 'package:specwright_cli/src/update/file_ops.dart';

void main(List<String> args) {
  final ops = UpdateFileOps();
  for (final path in args) {
    ops.mkdir(path);
  }
}
