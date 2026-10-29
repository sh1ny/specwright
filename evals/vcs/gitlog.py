"""Install a Git shim which records calls from Specwright and marks state-changing commands."""
import json
import os
import shutil
from pathlib import Path


_WRITE_COMMANDS = {
    "add", "am", "apply", "branch", "checkout", "cherry-pick", "clean", "clone", "commit", "init",
    "merge", "mv", "pull", "push", "rebase", "reset", "restore", "rm", "stash", "switch", "tag",
    "update-ref", "worktree", "fetch",
}
_READ_ONLY_CONFIG = {"--get", "--get-all", "--get-regexp", "--list", "-l", "--show-origin", "--show-scope"}
_TAG_READS = {"-l", "--list", "-n", "--contains", "--no-contains", "--merged", "--no-merged", "--points-at", "--sort", "--format"}
_TAG_WRITES = {"-a", "-d", "-f", "-s", "-u", "-m", "-F", "--delete", "--force", "--annotate", "--sign"}
_BRANCH_READS = {"--show-current", "--list", "-l", "--contains", "--no-contains", "--merged", "--no-merged", "--points-at", "--remotes"}


def classify(argv):
    """Return action/write/exception metadata for a Git argument vector."""
    args = list(map(str, argv))
    command_index = 0
    while command_index < len(args):
        value = args[command_index]
        if value in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"):
            command_index += 2
        elif value.startswith("-"):
            command_index += 1
        else:
            break
    command = args[command_index] if command_index < len(args) else ""
    tail = args[command_index + 1:]
    write = command in _WRITE_COMMANDS
    exception = None
    if command == "branch" and (not tail or tail[0] in _BRANCH_READS or any(arg in _BRANCH_READS for arg in tail)):
        write = False
    if command == "tag" and (not tail or any(arg in _TAG_READS or arg.startswith(("--format=", "--sort=", "--points-at=", "--contains="))
                                              for arg in tail)) and not any(arg in _TAG_WRITES for arg in tail):
        write = False  # listing tags reads
    if command == "fetch" and any(arg == "--refmap=" for arg in tail):
        write = False
        exception = "FETCH_HEAD-only read fetch"
    elif command == "tag" and "-a" in tail:
        write = True
        exception = "annotated release tag"
    elif command == "config":
        write = not any(flag in tail for flag in _READ_ONLY_CONFIG)
    return {"action": command, "write": write, "exception": exception}


class GitShim:
    def __init__(self, directory, log_path, executable):
        self.path = Path(directory)
        self.log_path = Path(log_path)
        self.real_git = str(executable)

    @property
    def env(self):
        return {
            "PATH": str(self.path) + os.pathsep + os.environ.get("PATH", ""),
            "SPECWRIGHT_GIT_LOG": str(self.log_path),
            "SPECWRIGHT_REAL_GIT": self.real_git,
            "SPECWRIGHT_PYTHON": shutil.which("python") or shutil.which("python3") or "python",
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get("PYTHONPATH", ""),
        }

    def calls(self):
        return read_calls(self.log_path)

    def assert_no_writes(self, allowed=()):
        allowed = set(allowed)
        bad = [call for call in self.calls() if call["write"] and call.get("exception") not in allowed]
        if bad:
            raise AssertionError("unexpected Git writes: " + json.dumps(bad, sort_keys=True))


def install(directory, real_git=None, log_path=None):
    """Create an executable `git` shim; jj itself should use the real executable via repo config."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    real_git = str(real_git or shutil.which("git") or "")
    if not real_git:
        raise AssertionError("git not installed")
    log_path = Path(log_path or directory / "git-calls.jsonl")
    script = directory / "git"
    script.write_text(
        "#!/bin/sh\n"
        "set -e\n"
        "\"${SPECWRIGHT_PYTHON:-python}\" -c '"
        "import json,os,sys; a=sys.argv[1:]; c=__import__(\"vcs.gitlog\",fromlist=[\"classify\"]).classify(a); "
        "open(os.environ[\"SPECWRIGHT_GIT_LOG\"],\"a\",encoding=\"utf-8\").write(json.dumps({\"argv\":a,**c},ensure_ascii=False)+\"\\n\")' \"$@\"\n"
        "exec \"$SPECWRIGHT_REAL_GIT\" \"$@\"\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return GitShim(directory, log_path, real_git)


def read_calls(log_path):
    path = Path(log_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
