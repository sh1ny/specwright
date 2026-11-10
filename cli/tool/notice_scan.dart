import 'dart:convert';

/// Returns the runtime closure from the output of `dart pub deps --json`: the
/// packages reachable from the root's direct (non-dev) dependencies, sorted.
List<String> runtimeClosure(String depsJson) {
  final packages = {
    for (final p
        in (jsonDecode(depsJson) as Map<String, dynamic>)['packages']
            as List<dynamic>)
      (p as Map<String, dynamic>)['name'] as String: p,
  };
  final root = packages.values.firstWhere((p) => p['kind'] == 'root');
  final seen = <String>{};
  final pending = [...(root['directDependencies'] as List<dynamic>)];
  while (pending.isNotEmpty) {
    final name = pending.removeLast() as String;
    if (seen.add(name)) {
      pending.addAll(packages[name]!['dependencies'] as List<dynamic>);
    }
  }
  return seen.toList()..sort();
}

/// Returns the names in [packages] that [noticeText] does not name. A notice
/// entry is the package name on a line, then its pub.dev URL on the next line.
List<String> packagesWithoutNotice(
  Iterable<String> packages,
  String noticeText,
) {
  final lines = noticeText.split(RegExp(r'\r?\n'));
  final named = <String>{
    for (var i = 0; i + 1 < lines.length; i++)
      if (lines[i + 1] == 'https://pub.dev/packages/${lines[i]}') lines[i],
  };
  return [
    for (final name in packages)
      if (!named.contains(name)) name,
  ];
}
