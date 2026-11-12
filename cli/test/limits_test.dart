import 'package:specwright_cli/src/process/limits.dart';
import 'package:test/test.dart';

void main() {
  RunLimits resolve(
    Map<String, String> env, {
    bool paged = false,
    double now = 1000,
  }) => resolveLimits(env, paged: paged, epochSeconds: () => now);

  test('RunLimits with no argument has no deadline and no byte bound', () {
    const limits = RunLimits();
    expect(limits.deadline, isNull);
    expect(limits.maxBytes, isNull);
    expect(limits.stdoutCap, isNull);
  });

  test('a stdout cap is its own bound, apart from the byte bound', () {
    const capped = RunLimits(stdoutCap: 1024);
    expect(capped.stdoutCap, 1024);
    expect(capped.maxBytes, isNull);
    expect(capped.deadline, isNull);
    // resolved limits (a bounded caller) carry both a deadline and a bound
    // and no separate stdout cap
    final resolved = resolve({});
    expect(resolved.deadline, isNotNull);
    expect(resolved.maxBytes, isNotNull);
    expect(resolved.stdoutCap, isNull);
  });

  test('defaults are 120 s, 300 s paged and 32 MiB', () {
    expect(resolve({}).deadline, const Duration(seconds: 120));
    expect(resolve({}, paged: true).deadline, const Duration(seconds: 300));
    expect(resolve({}).maxBytes, 32 * 1024 * 1024);
  });

  test('the environment lowers each limit', () {
    final limits = resolve({
      'SPECWRIGHT_NET_DEADLINE': '1.5',
      'SPECWRIGHT_NET_MAX_BYTES': '5000',
    });
    expect(limits.deadline, const Duration(milliseconds: 1500));
    expect(limits.maxBytes, 5000);
    expect(
      resolve({
        'SPECWRIGHT_NET_PAGED_DEADLINE': '7',
        'SPECWRIGHT_NET_DEADLINE': '1',
      }, paged: true).deadline,
      const Duration(seconds: 7),
    );
  });

  test('the environment never raises a limit', () {
    final limits = resolve({
      'SPECWRIGHT_NET_DEADLINE': '1000',
      'SPECWRIGHT_NET_PAGED_DEADLINE': '1000',
      'SPECWRIGHT_NET_MAX_BYTES': '${1 << 40}',
    });
    expect(limits.deadline, const Duration(seconds: 120));
    expect(limits.maxBytes, 32 * 1024 * 1024);
    expect(
      resolve({'SPECWRIGHT_NET_PAGED_DEADLINE': '1000'}, paged: true).deadline,
      const Duration(seconds: 300),
    );
    expect(
      resolve({'SPECWRIGHT_NET_DEADLINE': 'Infinity'}).deadline,
      const Duration(seconds: 120),
    );
  });

  test('a value that is not a non-negative number leaves the default', () {
    for (final bad in ['abc', '', '-5', 'NaN', '1.5x']) {
      final limits = resolve({
        'SPECWRIGHT_NET_DEADLINE': bad,
        'SPECWRIGHT_NET_MAX_BYTES': bad,
        'SPECWRIGHT_NET_DEADLINE_AT': bad,
      });
      expect(limits.deadline, const Duration(seconds: 120), reason: bad);
      expect(limits.maxBytes, 32 * 1024 * 1024, reason: bad);
    }
    // the byte bound takes whole numbers only
    expect(
      resolve({'SPECWRIGHT_NET_MAX_BYTES': '1.5'}).maxBytes,
      32 * 1024 * 1024,
    );
  });

  test('zero is a valid override', () {
    expect(resolve({'SPECWRIGHT_NET_MAX_BYTES': '0'}).maxBytes, 0);
    expect(resolve({'SPECWRIGHT_NET_DEADLINE': '0'}).deadline, Duration.zero);
  });

  test('DEADLINE_AT caps the deadline to the time left', () {
    final env = {'SPECWRIGHT_NET_DEADLINE_AT': '1003.5'};
    expect(resolve(env).deadline, const Duration(milliseconds: 3500));
    // never raises: a far future time leaves the default
    expect(
      resolve({'SPECWRIGHT_NET_DEADLINE_AT': '999999'}).deadline,
      const Duration(seconds: 120),
    );
    // the lower of the two wins
    expect(
      resolve({...env, 'SPECWRIGHT_NET_DEADLINE': '2'}).deadline,
      const Duration(seconds: 2),
    );
  });

  test('DEADLINE_AT in the past leaves no time', () {
    expect(
      resolve({'SPECWRIGHT_NET_DEADLINE_AT': '900'}).deadline,
      Duration.zero,
    );
  });
}
