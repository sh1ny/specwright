"""Locate and run the built `sw` binary for the cli eval suite.

SPECWRIGHT_SW names the binary. Unset, or naming no file: tests skip as `sw not built`, unless SPECWRIGHT_REQUIRE_SW=1 (CI),
which makes them fail naming the missing binary.
"""
import os
import subprocess
import unittest
from pathlib import Path

SKIP_REASON = "sw not built"


def sw_path():
    """Return the path of the sw binary, or None when SPECWRIGHT_SW is unset or names no file."""
    value = os.environ.get("SPECWRIGHT_SW")
    if value and Path(value).is_file():
        return str(Path(value))
    return None


def require_sw():
    """Return the sw binary path, honoring the local-skip / CI-required contract."""
    path = sw_path()
    if path:
        return path
    if os.environ.get("SPECWRIGHT_REQUIRE_SW") == "1":
        value = os.environ.get("SPECWRIGHT_SW")
        raise AssertionError("sw binary missing: %s (SPECWRIGHT_REQUIRE_SW=1)" % (
            value if value else "SPECWRIGHT_SW unset"))
    raise unittest.SkipTest(SKIP_REASON)


SPAWN_DIR = "SPECWRIGHT_TEST_SPAWN_DIR"


def fixture_env(**extra):
    """os.environ without SPECWRIGHT_NET_* and SPECWRIGHT_TEST_* overrides, plus `extra` (values as strings).

    SPECWRIGHT_TEST_SPAWN_DIR is kept: evals/run.py sets it so its sweep can stop the sessions sw starts when it stops
    a test file. A test that needs it unset or different passes its own value or pops it.
    """
    env = {k: v for k, v in os.environ.items()
           if k == SPAWN_DIR or not k.startswith(("SPECWRIGHT_NET_", "SPECWRIGHT_TEST_"))}
    env.update({k: str(v) for k, v in extra.items()})
    return env


def run_sw(*args, cwd=None, env=None, input=None, timeout=60):
    """Run sw with args; return the CompletedProcess (text mode, stdout and stderr captured). Raises on timeout."""
    return subprocess.run([require_sw(), *map(str, args)], cwd=cwd, env=env, input=input, capture_output=True,
                          text=True, timeout=timeout)
