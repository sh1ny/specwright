"""The eval runner's own process helper: start a test file in a tree it can stop, and stop that tree. Stdlib only, Python 3.8+.

The runner (evals/run.py) must not depend on the binary or the shipped files it tests, so it keeps this small copy of the
process handling instead of loading anything from skills/ or starting `sw run --bounded` (design D10).

  spawn(cmd, **popen_kw) -> Popen  starts the command in its own process group (POSIX: new session; Windows: suspended,
      assigned to a job object, then resumed, so nothing it starts escapes). The job handle is p.job (None when there is none).
      stdin is DEVNULL. Raises OSError when the command cannot start. On Windows without a job object it goes on without one.
  kill(p)             stops every process the command started, also when the command itself has already exited. Windows:
      TerminateJobObject, or `taskkill /T /F /PID` for a run without a job; POSIX: killpg. By PID or job only, never by name.
  close_job(p)        closes the job handle (the job has no kill-on-close: a finished command's detached helpers live on).
"""
import os
import signal
import subprocess

CREATE_SUSPENDED = 0x00000004
_K32 = _NT = None


def _win_api():
    """kernel32 and ntdll with typed signatures (handles are pointer-sized; a bare int would be cut to 32 bits)."""
    global _K32, _NT
    if _K32 is None:
        import ctypes
        from ctypes import wintypes
        k, nt = ctypes.WinDLL("kernel32", use_last_error=True), ctypes.WinDLL("ntdll")
        k.CreateJobObjectW.argtypes, k.CreateJobObjectW.restype = [ctypes.c_void_p, wintypes.LPCWSTR], ctypes.c_void_p
        k.AssignProcessToJobObject.argtypes, k.AssignProcessToJobObject.restype = [ctypes.c_void_p, ctypes.c_void_p], wintypes.BOOL
        k.TerminateJobObject.argtypes, k.TerminateJobObject.restype = [ctypes.c_void_p, wintypes.UINT], wintypes.BOOL
        k.CloseHandle.argtypes, k.CloseHandle.restype = [ctypes.c_void_p], wintypes.BOOL
        nt.NtResumeProcess.argtypes, nt.NtResumeProcess.restype = [ctypes.c_void_p], ctypes.c_long
        _K32, _NT = k, nt
    return _K32, _NT


def _make_job(p):
    """A job object holding process p, or OSError. No kill-on-close limit: a command that finished normally keeps the
    detached helpers it left (git's background maintenance), as it does on POSIX."""
    import ctypes
    k, _ = _win_api()
    job = k.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    if not k.AssignProcessToJobObject(job, int(p._handle)):
        err = ctypes.WinError(ctypes.get_last_error())
        k.CloseHandle(job)
        raise err
    return job


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


def spawn(cmd, **kw):
    if os.name == "nt":
        kw["creationflags"] = kw.get("creationflags", 0) | CREATE_SUSPENDED
    else:
        kw.setdefault("start_new_session", True)
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, bufsize=0, **kw)
    p.job = None
    if os.name == "nt":
        try:
            p.job = _make_job(p)
        except OSError:
            pass  # no job object: kill falls back to taskkill /T by PID
        status = _win_api()[1].NtResumeProcess(int(p._handle))
        if status != 0:
            kill(p)
            p.wait()
            close_job(p)
            raise OSError("NtResumeProcess failed: NTSTATUS 0x%08x" % (status & 0xFFFFFFFF))
    return p


def kill(p):
    job = getattr(p, "job", None)
    if job is not None and os.name == "nt":
        if _win_api()[0].TerminateJobObject(job, 1):
            try:
                p.kill()  # the job holds it too; this only makes sure a failed assignment race cannot leave it
            except OSError:
                pass
            return
    kill_tree(p.pid)


def close_job(p):
    job, p.job = getattr(p, "job", None), None
    if job is not None and os.name == "nt":
        _win_api()[0].CloseHandle(job)
