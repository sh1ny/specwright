import 'dart:io' show Platform;

import 'package:specwright_cli/src/native/libc.dart';
import 'package:test/test.dart';

/// The constants `faccessat` takes differ by OS (D6, C22). They are pinned per
/// OS, so a wrong value shows here and not as a lookup that quietly checks the
/// real IDs.
void main() {
  test('Linux AT_FDCWD is -100 and AT_EACCESS is 0x200', () {
    expect(atFdcwdFor(macos: false), -100);
    expect(atEaccessFor(macos: false), 0x200);
  });

  test('macOS AT_FDCWD is -2 and AT_EACCESS is 0x10', () {
    expect(atFdcwdFor(macos: true), -2);
    expect(atEaccessFor(macos: true), 0x10);
  });

  test('the running OS uses its own pair', () {
    expect(atFdcwd, atFdcwdFor(macos: Platform.isMacOS));
    expect(atEaccess, atEaccessFor(macos: Platform.isMacOS));
  });
}
