"""Write a fake tool that `sw` can start on Windows as well (native-cli-launcher D9).

`sw` looks a command up by PATHEXT on Windows, so an extensionless `#!/bin/sh` fake named `git`, `gh` or `jj` is not found
there. `write_fake` writes the script as before (LF, executable) and, on Windows only, a `<name>.cmd` beside it that starts
the script through Git Bash with the arguments it was given: `@"<bash>" "<script>" %*`. The script path is baked in, so the
wrapper sets no variable and the fake sees the environment its caller gave.

What `sw` hands such a wrapper: it runs a `.cmd` through cmd.exe with every argument in double quotes, and refuses before
any start an argument that holds `%`, `!`, a double quote, CR or LF (`bounded: unsafe batch argument`, which a document
caller reports as `internal_error`). A fake behind a `.cmd` therefore never receives those characters. A fake that sw
calls with one (`git log --format=%H`, a jj template with quotes) is written with `exe=True` (a bash
script) or `write_python_fake` (Python source): a `<name>.exe` that receives the command line as given.

The `.exe` is the console launcher that pip vendors for its own script wrappers: the launcher, a `#!` line naming this
interpreter, then a zip holding `__main__.py`. It needs the Python that runs the evals to have pip, as the CI Pythons do.

Git Bash (MSYS) rewrites glob characters in the arguments it is started with (it halves backslashes before `[` and drops
braces), so the bash `.exe` hands the script its arguments through the environment instead of bash's command line. A
`.cmd` wrapper starts bash with `%*` and so carries that risk: use `exe=True` for a fake that gets such arguments.
evals/vcs/test_fakeexe.py pins the round trip.

Bash is `bashexe.bash()`; with none installed no wrapper is written and the tests that need bash fail on that.

Importable from any suite: it needs only the standard library and `evals/bashexe.py`.
"""
import io
import os
import platform
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bashexe  # noqa: E402


def write_script(path, text):
    """The script [text] at [path]: UTF-8, LF line ends, mode 0755."""
    path = Path(path)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    path.chmod(0o755)
    return path


def write_wrapper(script):
    """`<script>.cmd` beside the extensionless [script] on Windows; nothing elsewhere. Returns the wrapper or None."""
    if os.name != "nt":
        return None
    bash = bashexe.bash()
    if not bash:
        return None
    wrapper = Path(str(script) + ".cmd")
    line = '@"%s" "%s" %%*\r\n' % (Path(bash).as_posix(), Path(os.path.abspath(script)).as_posix())
    wrapper.write_bytes(line.encode("utf-8"))
    return wrapper


def _write_exe(path, main_source):
    """`<path>.exe` on Windows: pip's console launcher, a `#!` line naming this interpreter and a zip of `__main__.py`."""
    import pip
    path = Path(path)
    launchers = Path(pip.__file__).parent / "_vendor" / "distlib"
    name = "t64-arm.exe" if platform.machine().upper() == "ARM64" else "t64.exe"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("__main__.py", main_source)
    exe = path.with_name(path.name + ".exe")
    exe.write_bytes((launchers / name).read_bytes() + b"#!" + sys.executable.encode("utf-8") + b"\r\n" + archive.getvalue())
    return exe


def write_python_fake(path, source):
    """A fake tool written in Python, for one that must receive arguments a `.cmd` cannot carry.

    On Windows this writes `<path>.exe` (see the module text) whose program is [source], exiting with the status the script
    gives. Elsewhere it writes an executable `#!` script. Returns the path written."""
    if os.name != "nt":
        return write_script(path, "#!%s\n%s" % (sys.executable, source))
    return _write_exe(path, source)


# The program of an `.exe` fake that runs a script under bash. Git Bash (MSYS) rewrites the arguments it is started with
# when they hold glob characters: it drops `{` and `}` (`HEAD^{commit}` arrives as `HEAD^commit`) and halves backslashes
# before `[` (two backslashes and `[` arrive as one), whatever the quoting. So no argument goes on bash's command line. They travel
# in one environment variable, quoted for sh, which a fixed prologue evaluates into the positional parameters and
# removes before it runs the script.
_EXE_MAIN = '''import os, shlex, subprocess, sys

env = dict(os.environ)
env["SW_FAKE_ARGS"] = " ".join(shlex.quote(arg) for arg in sys.argv[1:])
prologue = 'eval "set -- $SW_FAKE_ARGS"; unset SW_FAKE_ARGS; exec "$BASH" "$0" "$@"'
sys.exit(subprocess.call([%r, "-c", prologue, %r], env=env))
'''


def write_fake(path, text, exe=False):
    """The fake tool [path] with source [text] (a `#!/bin/sh` or bash script); returns [path] as a Path.

    The script is written, then `add_launcher` gives it what `sw` needs on Windows."""
    script = write_script(path, text)
    add_launcher(script, exe=exe)
    return script


def add_launcher(script, exe=False):
    """What `sw` needs beside the extensionless fake [script] that a test has already written; nothing off Windows.

    On Windows it writes `<script>.cmd`. A fake that gets `%`, `!`, a quote, CR or LF (see the module text) takes [exe]
    instead: `<script>.exe`, which starts bash on the script and passes its arguments on. Both launchers run the script
    at its path, so a test may rewrite or rename the script after this call and the launcher follows it. The extensionless
    script stays what POSIX and `sh <script>` run. Returns [script] as a Path."""
    script = Path(script)
    if os.name != "nt":
        return script
    if exe:
        bash = bashexe.bash()
        if bash:
            _write_exe(script, _EXE_MAIN % (Path(bash).as_posix(), Path(os.path.abspath(script)).as_posix()))
    else:
        write_wrapper(script)
    return script
