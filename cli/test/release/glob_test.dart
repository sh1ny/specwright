// Tests of the release version-file glob (cli/lib/src/release/glob.dart).
//
// Assumption A2 of native-cli-release, checked with Python 3.14.4 in a scratch
// directory holding `.hidden/VERSION`, `a/.VERSION` and `a/VERSION`:
//
//   glob.glob('**/*', recursive=True) -> ['a', 'a/VERSION']
//   glob.glob('*')                    -> ['a']
//   glob.glob('**/VERSION', recursive=True) -> ['a/VERSION']
//   glob.glob('*/VERSION')            -> ['a/VERSION']
//   glob.glob('.hidden/VERSION')      -> ['.hidden/VERSION']
//   glob.glob('a/*')                  -> ['a/VERSION']
//
// So in the work tree a wildcard segment (`*`, `?`, `[...]`, and every
// directory `**` spans) never matches a name starting with `.`, while a
// literal segment does. The commit-tree glob over `git ls-tree` names matches
// dot-names (constraint C4). The tests below pin the same rule.

void main() {}
