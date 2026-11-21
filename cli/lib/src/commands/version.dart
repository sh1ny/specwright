/// The Specwright version this binary was built from, compiled in with
/// `--define=SW_VERSION=<VERSION file>` (see tool/build.dart).
const String buildVersion = String.fromEnvironment(
  'SW_VERSION',
  defaultValue: '0.0.0-dev',
);

/// Changes whenever a command's arguments, JSON output or exit codes change
/// incompatibly. It must change together with the `interface <n>` line of
/// skills/specwright-pr/SKILL.md, pinned by evals/cli/test_sw_interface_pin.py.
///
/// C35: this change raises `interface` to 3 (D10, S5), because it changes
/// command results callers could rely on: strict `--timeout` validation (D7),
/// exit 2 for a `usage` stop of `undo-archive-plan` (#209), selection skipping
/// an over-long `omp.cmd` probe (D5), the shared `--logs` cap (D4), `sw as`
/// exiting 2 for an `Unrepresentable` `.cmd` line (D5), the identity-encoding
/// and pre-request download stops (D8), and the Git 2.40 floor for a Git
/// resume undo (D2). The interface number and the skills' required interface
/// change together (`evals/cli/test_sw_interface_pin.py`); a later change that
/// alters a command result incompatibly raises it again rather than listing
/// exceptions. Rejected: keeping interface 2 with a closed list of exceptions.
const int interfaceVersion = 3;

Map<String, Object> versionReport({String version = buildVersion}) => {
  'version': version,
  'interface': interfaceVersion,
};
