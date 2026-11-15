/// A `RegExpMatch` in Dart reports the text of a group but not where it lies.
/// The version bump needs that place, so [locatingPattern] marks it: the
/// returned pattern matches exactly what [pattern] matches, and in each match
/// group 1 is the version, and the lengths of groups 2 and 3 are its start and
/// end offsets. Each of the two marker groups is a look-behind that captures
/// all the text before its position.
///
/// [pattern] must be a valid Unicode-mode pattern with exactly one capture
/// group. The markers sit inside that group, so its number and every
/// back-reference to it stay as written.
String locatingPattern(String pattern) {
  final open = _openOfCapture(pattern);
  final close = _closeOf(pattern, open);
  final body = pattern.startsWith('(?<', open)
      ? pattern.indexOf('>', open) + 1
      : open + 1;
  const mark = r'(?<=([\s\S]*))';
  return '${pattern.substring(0, body)}$mark'
      '${pattern.substring(body, close)}$mark${pattern.substring(close)}';
}

// The `(` of the capture group: not `(?:`, `(?=`, `(?!`, `(?<=` or `(?<!`.
int _openOfCapture(String pattern) {
  for (var i = 0; i < pattern.length; i++) {
    final skipped = _skip(pattern, i);
    if (skipped != i) {
      i = skipped;
      continue;
    }
    if (pattern[i] != '(') continue;
    if (!pattern.startsWith('(?', i)) return i;
    if (pattern.startsWith('(?<', i) &&
        !pattern.startsWith('(?<=', i) &&
        !pattern.startsWith('(?<!', i)) {
      return i;
    }
  }
  throw StateError('no capture group');
}

// The `)` that closes the group opened at [open].
int _closeOf(String pattern, int open) {
  var depth = 0;
  for (var i = open; i < pattern.length; i++) {
    final skipped = _skip(pattern, i);
    if (skipped != i) {
      i = skipped;
      continue;
    }
    if (pattern[i] == '(') depth++;
    if (pattern[i] == ')' && --depth == 0) return i;
  }
  throw StateError('unbalanced pattern');
}

// The index of the last character of the escape or class that starts at [i],
// or [i] itself when none starts there.
int _skip(String pattern, int i) {
  if (pattern[i] == r'\') return i + 1;
  if (pattern[i] != '[') return i;
  for (var j = i + 1; j < pattern.length; j++) {
    if (pattern[j] == r'\') {
      j++;
    } else if (pattern[j] == ']') {
      return j;
    }
  }
  throw StateError('unbalanced class');
}
