"""Recording sentinels for the paths where `sw` must start no shipped script and no Python interpreter.

`install` writes recording `as.sh`, `vcs.sh`, `pr-pair.sh` and `sw-path.sh` into the scripts directory a test hands to `sw`
(each appends its own name to a log file, prints `unexpected-script` and exits 92) and failing recording `python` and
`python3` into a separate directory that the test puts first on PATH (each appends its name and exits 97). A probe runs every
sentinel directly and checks that it records, so a test that later finds the log absent knows nothing was started, rather
than that a sentinel cannot record. The pattern is the one of `evals/pr-pair/test_workflow_transport.py`, shared so that
`evals/pr-pair/` reuses it:

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vcs"))
    import sentinels

Importable from any suite: it needs only the standard library and `evals/bashexe.py`.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bashexe  # noqa: E402

SCRIPT_NAMES = ("as.sh", "vcs.sh", "pr-pair.sh", "sw-path.sh")
INTERPRETER_NAMES = ("python", "python3")
SCRIPT_STATUS = 92
INTERPRETER_STATUS = 97
LOG_VARIABLE = "SW_SENTINEL_LOG"

_SCRIPT = '#!/bin/sh\nprintf "%s\\n" {name} >> "{log}"\necho unexpected-script >&2\nexit {status}\n'
_INTERPRETER = '#!/bin/sh\nprintf "%s\\n" {name} >> "{log}"\necho unexpected-interpreter >&2\nexit {status}\n'


def _write(path, text):
    with Path(path).open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    Path(path).chmod(0o755)


class Sentinels:
    """The installed sentinels: `scripts` is the handoff scripts directory, `bin` the directory for PATH, `log` the record."""

    def __init__(self, scripts, bin_dir, log):
        self.scripts = Path(scripts)
        self.bin = Path(bin_dir)
        self.log = Path(log)

    @property
    def env(self):
        """The variable every sentinel reads to find the log (an absolute path with `/` separators)."""
        return {LOG_VARIABLE: self.log.resolve().as_posix()}

    def recorded(self):
        """The names that ran since the last `clear`, in order; empty while the log is absent."""
        if not self.log.exists():
            return []
        return self.log.read_text(encoding="utf-8").splitlines()

    def clear(self):
        self.log.unlink(missing_ok=True)

    def probe(self, test, env=None):
        """Run each sentinel directly and assert that it records its own name and exits with its status; then clear the log.

        `test` is the unittest case whose assertions report a sentinel that cannot record: the later assertion that the
        log stays absent would otherwise hold for the wrong reason."""
        bash = bashexe.bash()
        test.assertTrue(bash, "the sentinels need bash")
        self.clear()
        run_env = {**os.environ, **(env or {}), **self.env}
        wanted = []
        for names, folder, status in ((SCRIPT_NAMES, self.scripts, SCRIPT_STATUS),
                                      (INTERPRETER_NAMES, self.bin, INTERPRETER_STATUS)):
            for name in names:
                done = subprocess.run([bash, str(folder / name)], env=run_env, capture_output=True, timeout=30)
                test.assertEqual(done.returncode, status, "%s: %r" % (name, done.stderr))
                wanted.append(name)
                test.assertEqual(self.recorded(), wanted, "the %s sentinel did not record its run" % name)
        self.clear()


def install(scripts, bin_dir, log):
    """Write the sentinels (both directories are created) and return the `Sentinels` that name them."""
    scripts, bin_dir = Path(scripts), Path(bin_dir)
    scripts.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in SCRIPT_NAMES:
        _write(scripts / name, _SCRIPT.format(name=name, status=SCRIPT_STATUS, log="$" + LOG_VARIABLE))
    for name in INTERPRETER_NAMES:
        _write(bin_dir / name, _INTERPRETER.format(name=name, status=INTERPRETER_STATUS, log="$" + LOG_VARIABLE))
    return Sentinels(scripts, bin_dir, log)
