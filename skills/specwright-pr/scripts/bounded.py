"""Run one command under a deadline and a stdout byte bound. Stdlib only, Python 3.8+.

The pr scripts run every network command (gh, git fetch/push/ls-remote) through here, so a stuck network or a huge
response ends as a named limit instead of a hang or an out-of-memory.

Limits (defaults live here only; the environment lowers them for tests):
  120 s            per command                         SPECWRIGHT_NET_DEADLINE
  300 s            per paginated read (paged=True)     SPECWRIGHT_NET_PAGED_DEADLINE
  32 MiB           of stdout per command               SPECWRIGHT_NET_MAX_BYTES
  50 pages         in a cursor loop a script drives    MAX_PAGES (constant)
  SPECWRIGHT_NET_DEADLINE_AT (epoch seconds) caps each deadline to the time left until then.

Use as a library:  run_bounded(cmd, deadline, max_bytes, env, cwd, paged=False, secret=False) -> Result(rc, stdout, stderr, limit)
  limit is None, "deadline_exceeded" or "response_too_large" (rc is None then); deadline and max_bytes default (None) to the
  values above. stdout and stderr are text (UTF-8, undecodable bytes replaced).
Use as a CLI:      python bounded.py [--paged] [--secret] -- cmd...
  Copies the command's stdout and stderr through after it ends and exits with its status. On a limit it prints
  `bounded: <limit>: <cmd[0]> <cmd[1]>` on stderr
  (for `sh -c script name args...`, the wrapped command: `name args[0]`) and exits 124 (deadline) or 125 (too large).

Normal mode sends stdout and stderr to files in a fresh temp dir (removed at the end), so a huge output costs disk, not memory.
Secret mode (--secret, secret=True) is for commands that print a credential: nothing reaches disk, the output is captured
through pipes, and a lookup never waits past its deadline plus 5 s. The process tree is stopped by PID only, never by name.
"""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import namedtuple

DEADLINE = 120
PAGED_DEADLINE = 300
MAX_BYTES = 32 * 1024 * 1024
MAX_PAGES = 50
POLL = 0.1

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


def _popen_kw():
    return {} if os.name == "nt" else {"start_new_session": True}


def _file_backed(cmd, deadline, max_bytes, env, cwd):
    work = tempfile.mkdtemp(prefix="specwright-net-")
    p = None
    try:
        out_path, err_path = os.path.join(work, "out"), os.path.join(work, "err")
        with open(out_path, "wb") as fo, open(err_path, "wb") as fe:
            try:
                p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=fo, stderr=fe, cwd=cwd, env=env, **_popen_kw())
            except OSError as e:
                return 127, b"", str(e).encode("utf-8", "replace"), None
            end, limit, rc = time.time() + deadline, None, None
            while True:
                rc = p.poll()  # exit is checked first: a finished command is never reported as a limit
                if rc is not None:
                    break
                if time.time() >= end:
                    limit = DEADLINE_EXCEEDED
                elif os.path.getsize(out_path) > max_bytes:
                    limit = RESPONSE_TOO_LARGE
                if limit:
                    kill_tree(p.pid)
                    try:
                        p.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        pass
                    break
                time.sleep(POLL)
        size = os.path.getsize(out_path)
        if limit is None and size > max_bytes:
            limit = RESPONSE_TOO_LARGE
        with open(out_path, "rb") as f:
            out = f.read(max_bytes + 1 if limit else size)
        with open(err_path, "rb") as f:
            err = f.read()
        return (None if limit else rc), out, err, limit
    finally:
        if p is not None and p.poll() is None:
            kill_tree(p.pid)
        shutil.rmtree(work, ignore_errors=True)


def _secret(cmd, deadline, max_bytes, env, cwd):
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=env,
                             **_popen_kw())
    except OSError as e:
        return 127, b"", str(e).encode("utf-8", "replace"), None
    try:
        try:
            out, err = p.communicate(timeout=deadline)
        except subprocess.TimeoutExpired:
            kill_tree(p.pid)
            try:
                p.communicate(timeout=5)
            except subprocess.TimeoutExpired:  # a survivor still holds a pipe: let go of our ends and stop waiting
                for s in (p.stdout, p.stderr):
                    try:
                        if s:
                            s.close()
                    except (OSError, ValueError):
                        pass
            return None, b"", b"", DEADLINE_EXCEEDED
        if len(out) > max_bytes:
            return None, b"", b"", RESPONSE_TOO_LARGE
        return p.returncode, out, err, None
    finally:
        if p.poll() is None:
            kill_tree(p.pid)


def _run(cmd, deadline, max_bytes, env, cwd, paged, secret):
    deadline, max_bytes = resolve(deadline, max_bytes, env, paged)
    return (_secret if secret else _file_backed)(list(cmd), deadline, max_bytes, env, cwd)


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
