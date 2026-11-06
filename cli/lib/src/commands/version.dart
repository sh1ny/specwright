/// The Specwright version this binary was built from, compiled in with
/// `--define=SW_VERSION=<VERSION file>` (see tool/build.dart).
const String buildVersion = String.fromEnvironment(
  'SW_VERSION',
  defaultValue: '0.0.0-dev',
);

/// Changes whenever a command's arguments, JSON output or exit codes change
/// incompatibly. It must change together with `SW_INTERFACE` in
/// skills/specwright-pr/scripts/sw-path.sh, pinned by
/// evals/cli/test_sw_interface_pin.py.
const int interfaceVersion = 1;

Map<String, Object> versionReport({String version = buildVersion}) => {
  'version': version,
  'interface': interfaceVersion,
};
