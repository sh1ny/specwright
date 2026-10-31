"""A `but` on PATH for tests: it runs the real `but`, logs every call, and can fake what the 0.23.1 CLI cannot make.

GitButler 0.23.1 has no CLI way to assign uncommitted changes to a branch (`but rub` is retired, `but move` refuses
uncommitted files, and `hunk_assignments` rows written to `but.sqlite` are never read; checked on 2026-10-30), so a
test that needs `stacks[].assignedChanges` states the assignments here and the wrapper moves those paths from
`uncommittedChanges` into the named branch's stack in `but status --json`. Every other output is the real one.
"""
import json
import sys
from pathlib import Path

from butenv import find_but, require_but

WRAPPER = r'''
import json, os, subprocess, sys
args = sys.argv[1:]
with open(os.environ["BUT_WRAP_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
result = subprocess.run([os.environ["BUT_WRAP_REAL"]] + args, capture_output=True, text=True, encoding="utf-8")
out = result.stdout
assign = os.environ.get("BUT_WRAP_ASSIGN")
if assign and args[:2] == ["status", "--json"] and result.returncode == 0:
    wanted = json.loads(open(assign, encoding="utf-8").read())
    status = json.loads(out)
    changes = status["uncommittedChanges"]
    for stack in status["stacks"]:
        names = [b["name"] for b in stack["branches"]]
        for branch, paths in wanted.items():
            if branch in names:
                moved = [c for c in changes if c["filePath"] in paths]
                stack["assignedChanges"].extend(moved)
                changes = [c for c in changes if c not in moved]
    status["uncommittedChanges"] = changes
    out = json.dumps(status, indent=2)
sys.stdout.write(out)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
'''


class ButWrap:
    """Install the wrapper under a scratch root. `env()` is the environment to hand to `invoke(env=...)`."""
    def __init__(self, scratch, assign=None):
        require_but()
        self.dir = scratch.root / "wrap-bin"
        self.dir.mkdir(exist_ok=True)
        self.log = scratch.root / "but-wrap-calls.jsonl"
        self.assign = scratch.root / "but-wrap-assign.json"
        self.assign.write_text(json.dumps(assign or {}), encoding="utf-8")
        (self.dir / "wrap.py").write_text(WRAPPER, encoding="utf-8")
        shim = self.dir / "but"
        shim.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (Path(sys.executable).as_posix(), (self.dir / "wrap.py").as_posix()),
                        encoding="utf-8", newline="\n")
        shim.chmod(0o755)

    def set_assignments(self, assign):
        self.assign.write_text(json.dumps(assign), encoding="utf-8")

    def env(self, scratch):
        from vcs_test_support import bash_path_env
        isolated = {key: value for key, value in scratch.env.items() if key != "PATH"}
        return {**bash_path_env(extra_path=(self.dir,)), **isolated, "BUT_WRAP_REAL": str(find_but()),
                "BUT_WRAP_LOG": str(self.log), "BUT_WRAP_ASSIGN": str(self.assign)}

    def calls(self):
        """Every `but` argument list the code under test ran, in order (the probe's `--version` included)."""
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def writes(self):
        """The calls that are not reads: only `--version` and `status` are reads."""
        return [call for call in self.calls() if call[:1] not in (["--version"], ["status"])]
