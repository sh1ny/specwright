"""The one helper evals use to run Specwright: start the binary named by SPECWRIGHT_SW with a list of arguments.

Evals start no shipped script (design D1, D2). A project command checks the project's `openspec/.specwright/VERSION`
against the binary's own version, so a fixture that runs one carries a matching VERSION and, when the command is started
outside that checkout (a planning store, a bare temp directory), names it with `project=`: the helper puts a leading
`--project <dir>` in front of the arguments.

  run(args, project=None, cwd=None, env=None, input=None, timeout=120, text=True) -> CompletedProcess
      text=True decodes stdout and stderr as UTF-8 (undecodable bytes become surrogate escapes); text=False keeps the bytes.
      An argument may be bytes on POSIX, for a name that is not UTF-8.
  argv(args, project=None) -> list    the command line `run` starts, for a test that starts the process itself.
  version() -> str                     the version `sw version --json` reports (once per process).
  stamp(repo, value=None)              write that version (or `value`) to <repo>/openspec/.specwright/VERSION.

Skips as `sw not built` without the binary, or fails when SPECWRIGHT_REQUIRE_SW=1 (cli/swharness.py).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "cli"))
import swharness  # noqa: E402

STAMP = "openspec/.specwright/VERSION"
_VERSION = {}


def argv(args, project=None):
    prefix = [] if project is None else ["--project", str(project)]
    return [swharness.require_sw(), *prefix, *(a if isinstance(a, bytes) else str(a) for a in args)]


def run(args, project=None, cwd=None, env=None, input=None, timeout=120, text=True):
    kw = {"encoding": "utf-8", "errors": "surrogateescape"} if text else {}
    return subprocess.run(argv(args, project), cwd=cwd, env=env, input=input, capture_output=True, timeout=timeout, **kw)


def version():
    sw = swharness.require_sw()
    if sw not in _VERSION:
        done = subprocess.run([sw, "version", "--json"], capture_output=True, text=True, encoding="utf-8", timeout=60)
        _VERSION[sw] = json.loads(done.stdout)["version"]
    return _VERSION[sw]


def stamp(repo, value=None):
    path = Path(repo) / STAMP
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(((value or version()) + "\n").encode("utf-8"))
    return path
