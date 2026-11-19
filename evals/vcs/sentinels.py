"""Recording interpreters for the paths where `sw` must start no Python.

`install` writes failing recording `python` and `python3` into a directory that the test puts first on PATH (each appends its
name to a log file, prints `unexpected-interpreter` and exits 97). A probe runs every sentinel directly and checks that it
records, so a test that later finds the log absent knows nothing was started, rather than that a sentinel cannot record. No
shipped script exists since 0.38.0, so there are no script sentinels. The pattern is shared so that `evals/pr-pair/` and
`evals/update/` reuse it:

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vcs"))
    import sentinels

Importable from any suite: it needs only the standard library, `evals/bashexe.py` and `evals/fakeexe.py`.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bashexe  # noqa: E402
import fakeexe  # noqa: E402

INTERPRETER_NAMES = ("python", "python3")
INTERPRETER_STATUS = 97
LOG_VARIABLE = "SW_SENTINEL_LOG"

_INTERPRETER = '#!/bin/sh\nprintf "%s\\n" {name} >> "{log}"\necho unexpected-interpreter >&2\nexit {status}\n'


class Sentinels:
    """The installed sentinels: `bin` is the directory for PATH, `log` the record."""

    def __init__(self, bin_dir, log):
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
        for name in INTERPRETER_NAMES:
            done = subprocess.run([bash, str(self.bin / name)], env=run_env, capture_output=True, timeout=30)
            test.assertEqual(done.returncode, INTERPRETER_STATUS, "%s: %r" % (name, done.stderr))
            wanted.append(name)
            test.assertEqual(self.recorded(), wanted, "the %s sentinel did not record its run" % name)
        self.clear()


def install(bin_dir, log):
    """Write the sentinels (the directory is created) and return the `Sentinels` that name them."""
    bin_dir = Path(bin_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in INTERPRETER_NAMES:  # started by name from PATH, so each gets a `.cmd` wrapper on Windows (D9)
        fakeexe.write_fake(bin_dir / name, _INTERPRETER.format(name=name, status=INTERPRETER_STATUS, log="$" + LOG_VARIABLE))
    return Sentinels(bin_dir, log)
