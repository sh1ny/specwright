/// The Specwright version this binary was built from, compiled in with
/// `--define=SW_VERSION=<VERSION file>` (see tool/build.dart).
const String buildVersion = String.fromEnvironment(
  'SW_VERSION',
  defaultValue: '0.0.0-dev',
);

/// Changes whenever a command's arguments, JSON output or exit codes change
/// incompatibly.
const int interfaceVersion = 1;

Map<String, Object> versionReport({String version = buildVersion}) => {
  'version': version,
  'interface': interfaceVersion,
};
