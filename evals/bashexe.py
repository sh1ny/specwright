"""Resolve the bash the evals start. On Windows, CreateProcess looks in the caller's directory and System32 before
PATH, so a bare "bash" runs System32's bash.exe (the WSL launcher). Evals start `bashexe.bash()` instead.

On Windows it is Git for Windows' usr/bin/bash.exe, not bin/bash.exe: that one is a launcher that puts /mingw64/bin and
/usr/bin before the caller's PATH, which hides the shims a test puts first."""
import os
import shutil
from pathlib import Path


def _under(path, folder):
    path = os.path.normcase(os.path.abspath(path))
    folder = os.path.normcase(os.path.abspath(folder)).rstrip("\\/")
    return path == folder or path.startswith(folder + os.sep)


def bash():
    """Git Bash's path (usr/bin/bash.exe; any bash off Windows), or None when none is installed."""
    if os.name != "nt":
        return shutil.which("bash")
    roots = []
    scoop = os.environ.get("SCOOP")
    if scoop:
        roots.append(Path(scoop) / "apps" / "git" / "current")
    profile = os.environ.get("USERPROFILE")
    if profile:
        roots.append(Path(profile) / "scoop" / "apps" / "git" / "current")
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(variable)
        if root:
            roots.append(Path(root) / "Git")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "Programs" / "Git")
    candidates = [os.environ.get("GIT_BASH")] + [str(root / "usr" / "bin" / "bash.exe") for root in roots]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    found = shutil.which("bash")
    if not found:
        return None
    system_root = os.environ.get("SystemRoot")
    if (system_root and _under(found, system_root)) or "windowsapps" in (p.lower() for p in Path(found).parts):
        return None
    return found
