import 'package:args/args.dart';
import 'package:specwright_cli/src/options.dart';
import 'package:test/test.dart';

class _Usage implements Exception {
  _Usage(this.message);
  final String message;
}

Never _usage(String message) => throw _Usage(message);

ArgResults _parse(List<String> argv) => parseOptions(
  argv,
  values: const ['name', 'repo'],
  lists: const ['item'],
  flags: const ['force'],
  usage: _usage,
);

void main() {
  // A5, checked by running package:args 2.7 `ArgParser` on 2026-11-10 (task 3.1):
  //  - a repeated single option keeps the last value: `--name a --name b` -> b.
  //  - `--` is a value when an option takes it: `--name --` and `--name=--` -> '--'; the next word is the value whatever
  //    it looks like (`--name --force`, `--name -5`), the flag stays unset.
  //  - a single-dash word is a FormatException (`-x`: could not find an option); a lone `-` is a plain word (rest).
  //  - an unknown or abbreviated long option (`--na`) is a FormatException; a missing value (`--name` last) is one.
  //  - `--` that is not a value ends option parsing and is dropped: `x -- --name` leaves rest [x, --name].
  //  - `--force=1` and `--no-force` are FormatExceptions with `negatable: false`.
  // The tests below pin the rules `parseOptions` builds on top of that.
  group('parseOptions', () {
    test('equals form matches the two-word form', () {
      final two = _parse(['--repo', '/r', '--name', 'n', '--item', 'a']);
      final eq = _parse(['--repo=/r', '--name=n', '--item=a']);
      expect(eq['repo'], two['repo']);
      expect(eq['name'], two['name']);
      expect(eq['item'], two['item']);
      expect(eq['repo'], '/r');
      expect(_parse(['--name=']).option('name'), '');
    });

    test('the next word is the value', () {
      expect(_parse(['--name', '--force'])['name'], '--force');
      expect(_parse(['--name', '--force'])['force'], isFalse);
      expect(_parse(['--name', '--'])['name'], '--');
      expect(_parse(['--name', '-5'])['name'], '-5');
      expect(_parse(['--name', 'a', '--name', 'b'])['name'], 'b');
    });

    test('repeated values keep their commas', () {
      expect(_parse(['--item', 'a,b', '--item', 'c'])['item'], ['a,b', 'c']);
    });

    test(
      'an unknown, abbreviated, single-dash or incomplete option is usage',
      () {
        for (final argv in [
          ['--bogus'],
          ['--na', 'v'],
          ['-x'],
          ['--name'],
          ['--force=1'],
          ['--no-force'],
        ]) {
          expect(() => _parse(argv), throwsA(isA<_Usage>()), reason: '$argv');
        }
      },
    );

    test('words that are not options are the rest', () {
      final r = _parse(['a', '--force', 'b', '--', '--name', 'c']);
      expect(r.rest, ['a', 'b', '--name', 'c']);
      expect(r['force'], isTrue);
    });
  });
}
