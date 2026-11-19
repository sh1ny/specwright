import 'dart:io';

import 'package:specwright_cli/src/review/references.g.dart';
import 'package:test/test.dart';

import '../../tool/references.dart';

// Run from cli/, as `dart test` does: the checkout is its parent.
final Directory _tree = Directory.current.parent;

void main() {
  test('built-in references equal skills/specwright-review/references', () {
    expect(reviewBrief, readReference(_tree, 'brief.md'));
    expect(findingsSchema, readReference(_tree, 'findings.schema.json'));
  });

  test('the committed file is what the build tool generates', () {
    final generated = File('${_tree.path}/cli/lib/src/review/references.g.dart')
        .readAsStringSync()
        .replaceAll('\r\n', '\n');
    expect(
      generated,
      renderReferences(
        brief: readReference(_tree, 'brief.md'),
        schema: readReference(_tree, 'findings.schema.json'),
      ),
    );
  });

  test('reviewBrief carries constraint C4 as its doc comment', () {
    final generated = File('${_tree.path}/cli/lib/src/review/references.g.dart')
        .readAsStringSync()
        .replaceAll('\r\n', '\n');
    expect(
      generated,
      contains(
        '/// C4: The built-in brief and schema must equal\n'
        '/// `skills/specwright-review/references/`; the drift test guards it.\n'
        'const String reviewBrief =',
      ),
    );
  });
}
