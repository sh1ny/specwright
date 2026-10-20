"""Run one command under a deadline and a byte bound on its stdout and its stderr. Stdlib only, Python 3.8+.

The pr scripts run every network command (gh, git fetch/push/ls-remote) through here, so a stuck network or a huge
response ends as a named limit instead of a hang or an out-of-memory.

Limits (defaults live here only; the environment lowers them for tests):
  120 s            per command                         SPECWRIGHT_NET_DEADLINE
  300 s            per paginated read (paged=True)     SPECWRIGHT_NET_PAGED_DEADLINE
  32 MiB           of stdout, and of stderr, per command  SPECWRIGHT_NET_MAX_BYTES
  50 pages         in a cursor loop a script drives    MAX_PAGES (constant)
  SPECWRIGHT_NET_DEADLINE_AT (epoch seconds) caps each deadline to the time left until then.

Use as a library:  run_bounded(cmd, deadline, max_bytes, env, cwd, paged=False, secret=False) -> Result(rc, stdout, stderr, limit)
  limit is None, "deadline_exceeded" or "response_too_large" (rc is None then); deadline and max_bytes default (None) to the
  values above. stdout and stderr are text (UTF-8, undecodable bytes replaced).
Use as a CLI:      python bounded.py [--paged] [--secret] -- cmd...
  Copies the command's stdout and stderr through after it ends and exits with its status. On a limit it prints
  `bounded: <limit>: <cmd[0]> <cmd[1]>` on stderr
  (for `sh -c script name args...`, the wrapped command: `name args[0]`) and exits 124 (deadline) or 125 (too large).

Windows argument transport: a native command line cuts an argument with spaces at 8186 characters when bash.exe parses it, so
for `bash -c script $0 args...` the arguments after $0 are not put on the command line. They go to the child's stdin as UTF-8,
each followed by a NUL, then an end marker; a prelude in front of the script reads them back into "$@" and empties stdin. Nothing
reaches disk. A missing marker (a runner that died mid-write, a bash older than 4.4) exits 126 without running the script.

Output is read from pipes as the command writes it and kept in memory, never on disk: a stream stops being read once it passes
the byte bound, so neither memory nor disk can grow past it between two checks, and the tree is stopped at once. Secret mode
(--secret, secret=True), for commands that print a credential, runs the same way. After a limit a survivor holding a pipe is
let go after 5 s. A command that exits while a process it started still holds a pipe gets 2 s for its readers, then that
tree is stopped and the command's own status and output are returned. The process tree is stopped by PID only, never by name.
"""
import os
import signal
import subprocess
import sys
import threading
import time
from collections import namedtuple

DEADLINE = 120
PAGED_DEADLINE = 300
MAX_BYTES = 32 * 1024 * 1024
MAX_PAGES = 50
GRACE = 2  # seconds the readers get to reach EOF after the command exits

DEADLINE_EXCEEDED = "deadline_exceeded"
RESPONSE_TOO_LARGE = "response_too_large"

Result = namedtuple("Result", "rc stdout stderr limit")


def kill_tree(pid):
    """Stop a process and everything it started, BY PID. Never by name or pattern."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
        return
    try:
        os.killpg(pid, signal.SIGKILL)  # the command is its own session and group leader
    except OSError:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _number(env, name, default, cast=float):
    try:
        v = cast((env if env is not None else os.environ).get(name, ""))
        return v if v >= 0 else default
    except (TypeError, ValueError):
        return default


def resolve(deadline, max_bytes, env, paged):
    """The deadline in seconds and the byte bound: arguments first, then the environment, then the defaults. A deadline is
    capped to the time left until SPECWRIGHT_NET_DEADLINE_AT."""
    if deadline is None:
        deadline = _number(env, "SPECWRIGHT_NET_PAGED_DEADLINE" if paged else "SPECWRIGHT_NET_DEADLINE",
                           PAGED_DEADLINE if paged else DEADLINE)
    if max_bytes is None:
        max_bytes = _number(env, "SPECWRIGHT_NET_MAX_BYTES", MAX_BYTES, int)
    at = _number(env, "SPECWRIGHT_NET_DEADLINE_AT", None)
    if at is not None:
        deadline = min(deadline, max(0.0, at - time.time()))
    return deadline, max_bytes


ARGV_END = "__SW_ARGV_END__"
ARGV_PRELUDE = (
    'mapfile -d "" -t __sw_argv; '
    '[ ${#__sw_argv[@]} -gt 0 ] && [ "${__sw_argv[${#__sw_argv[@]}-1]}" = %s ] || '
    '{ echo "bounded: argument transport failed" >&2; exit 126; }; '
    'unset "__sw_argv[${#__sw_argv[@]}-1]"; set -- "${__sw_argv[@]}"; unset __sw_argv; exec </dev/null' % ARGV_END)


def _transport(cmd):
    """(cmd, stdin bytes or None). On Windows a `bash -c script $0 args...` keeps its script and $0 on the command line and
    sends the arguments after $0 on stdin."""
    if os.name != "nt" or len(cmd) < 4 or cmd[1] != "-c" or os.path.basename(cmd[0]).lower().split(".")[0] != "bash":
        return cmd, None
    data = b"".join(a.encode("utf-8") + b"\0" for a in cmd[4:]) + ARGV_END.encode("ascii") + b"\0"
    return [cmd[0], "-c", ARGV_PRELUDE + "; " + cmd[2], cmd[3]], data


def _spawn(cmd, data, **kw):
    """Popen, plus a daemon thread that writes `data` to the child's stdin and closes it. A closed pipe ends the write quietly;
    killing the child unblocks it. Returns the process with p.stdin None: only the writer thread owns stdin."""
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL if data is None else subprocess.PIPE, bufsize=0, **kw)
    if data is not None:
        stream, p.stdin = p.stdin, None

        def write():
            try:
                stream.write(data)
            except (OSError, ValueError):
                pass
            finally:
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
        threading.Thread(target=write, daemon=True).start()
    return p


def _popen_kw():
    return {} if os.name == "nt" else {"start_new_session": True}


def _piped(cmd, data, deadline, max_bytes, env, cwd):
    try:
        p = _spawn(cmd, data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=env, **_popen_kw())
    except OSError as e:
        return 127, b"", str(e).encode("utf-8", "replace"), None
    bufs, over = (bytearray(), bytearray()), threading.Event()

    def drain(stream, buf):  # reads as the command writes, so the bound holds in memory while it runs
        try:
            fd = stream.fileno()
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    return
                buf += chunk
                if len(buf) > max_bytes:
                    over.set()
                    return
        except (OSError, ValueError):
            pass

    readers = [threading.Thread(target=drain, args=(s, b), daemon=True) for s, b in zip((p.stdout, p.stderr), bufs)]
    for t in readers:
        t.start()
    try:
        end, limit, exited = time.monotonic() + deadline, None, None  # monotonic: a stepped clock cannot move a deadline
        while True:
            if over.is_set():
                limit = RESPONSE_TOO_LARGE
                break
            if exited is None and p.poll() is not None:
                exited = time.monotonic()
            if exited is not None and (not any(t.is_alive() for t in readers) or time.monotonic() - exited >= GRACE):
                break  # a finished command is never reported as a deadline
            left = end - time.monotonic()
            if left <= 0:
                if exited is None:
                    limit = DEADLINE_EXCEEDED
                break
            over.wait(min(0.02, left))
        if limit is None and any(t.is_alive() for t in readers):
            kill_tree(p.pid)  # a process the command started still holds a pipe: stop it; the command's own result stands
            for t in readers:
                t.join(1)
        if limit is None and over.is_set():  # a bound passed between the loop's checks, just before the exit
            limit = RESPONSE_TOO_LARGE
        if limit:
            kill_tree(p.pid)
            stop = time.monotonic() + 5  # collect what the killed tree left; a survivor holding a pipe is let go after 5 s
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            for t in readers:
                t.join(max(0, stop - time.monotonic()))
            return None, b"", b"", limit
        return p.returncode, bytes(bufs[0]), bytes(bufs[1]), None
    finally:
        if p.poll() is None:
            kill_tree(p.pid)
        for s, t in zip((p.stdout, p.stderr), readers):
            if s and not t.is_alive():  # a reader still blocked on a survivor's pipe keeps its end
                try:
                    s.close()
                except (OSError, ValueError):
                    pass


def _run(cmd, deadline, max_bytes, env, cwd, paged, secret):
    deadline, max_bytes = resolve(deadline, max_bytes, env, paged)
    cmd, data = _transport(list(cmd))
    return _piped(cmd, data, deadline, max_bytes, env, cwd)  # secret mode reads the same way; the flag stays for callers


def run_bounded(cmd, deadline=None, max_bytes=None, env=None, cwd=None, paged=False, secret=False):
    rc, out, err, limit = _run(cmd, deadline, max_bytes, env, cwd, paged, secret)
    return Result(rc, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), limit)


def main(argv):
    flags = []
    while argv and argv[0] != "--":
        flags.append(argv.pop(0))
    cmd = argv[1:]
    if not cmd or any(f not in ("--paged", "--secret") for f in flags):
        sys.stderr.write("usage: bounded.py [--paged] [--secret] -- cmd...\n")
        return 2
    rc, out, err, limit = _run(cmd, None, None, None, None, "--paged" in flags, "--secret" in flags)
    if limit:
        shell = os.path.basename(cmd[0]).lower().split(".")[0] in ("sh", "bash")
        named = cmd[3:5] if shell and len(cmd) > 3 and cmd[1] == "-c" else cmd[:2]  # sh -c 'exec gh "$@"' gh api: name gh api
        sys.stderr.write("bounded: %s: %s\n" % (limit, " ".join(named)))
        return 124 if limit == DEADLINE_EXCEEDED else 125
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(err)
    sys.stderr.buffer.flush()
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
