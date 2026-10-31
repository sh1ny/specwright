"""Resolve the bash the evals start. On Windows, CreateProcess looks in the caller's directory and System32 before
PATH, so a bare "bash" runs System32's bash.exe (the WSL launcher). Evals start `bashexe.bash()` instead."""
import os
import shutil
from pathlib import Path


def _under(path, folder):
    path = os.path.normcase(os.path.abspath(path))
    folder = os.path.normcase(os.path.abspath(folder)).rstrip("\\/")
    return path == folder or path.startswith(folder + os.sep)


def bash():
    """Git Bash's path (any bash off Windows), or None when none is installed."""
    if os.name != "nt":
        return shutil.which("bash")
    candidates = [os.environ.get("GIT_BASH")]
    scoop = os.environ.get("SCOOP")
    if scoop:
        candidates.append(str(Path(scoop) / "apps" / "git" / "current" / "bin" / "bash.exe"))
    profile = os.environ.get("USERPROFILE")
    if profile:
        candidates.append(str(Path(profile) / "scoop" / "apps" / "git" / "current" / "bin" / "bash.exe"))
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(variable)
        if root:
            candidates.append(str(Path(root) / "Git" / "bin" / "bash.exe"))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(str(Path(local) / "Programs" / "Git" / "bin" / "bash.exe"))
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
