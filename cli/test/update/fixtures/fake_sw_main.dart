// A stand-in for a downloaded sw: answers `version --json` as the file
// `fake_sw.txt` next to the executable says. Its first line is the mode:
// `print` (the rest of the file is written to stdout), `hang`, `big` (more
// than 1 MiB on stdout) or `exit N`. Without that file, which a placed copy
// does not have, it reports FAKE_VERSION and FAKE_INTERFACE, compiled in with
// --define. See fake_sw.dart.
import 'dart:io';

const _version = String.fromEnvironment('FAKE_VERSION', defaultValue: '0.37.0');
const _interface = int.fromEnvironment('FAKE_INTERFACE', defaultValue: 1);

Future<void> main(List<String> args) async {
  final dir = File(Platform.resolvedExecutable).parent.path;
  final file = File('$dir/fake_sw.txt');
  final config = file.existsSync()
      ? file.readAsStringSync()
      : 'print\n{"version":"$_version","interface":$_interface}\n';
  final newline = config.indexOf('\n');
  final mode = (newline < 0 ? config : config.substring(0, newline)).trim();
  final rest = newline < 0 ? '' : config.substring(newline + 1);
  if (args.length != 2 || args[0] != 'version' || args[1] != '--json') {
    stderr.write('unexpected arguments: $args\n');
    exit(2);
  }
  if (mode == 'hang') {
    await Future<void>.delayed(const Duration(minutes: 5));
  } else if (mode == 'big') {
    stdout.write('x' * (1024 * 1024 + 10));
  } else if (mode.startsWith('exit ')) {
    exit(int.parse(mode.substring(5)));
  } else {
    stdout.write(rest);
  }
}
