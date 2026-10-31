"""A fake `codex`, `claude` and `omp` for review-run.sh tests. Pure stdlib; no network.

Run as `python reviewcli.py <codex|claude|omp> <args...>`; the test's bin dir holds a `.cmd` and a POSIX shim per CLI.
Environment (U = the CLI name in capitals):
  FAKE_U_ARGV_LOG      append one JSON line per call: {argv, stdin, prompt_file_text (omp), session_dir_before (omp)}
  FAKE_U_READ          log [is_link, text] of this path (relative to the cwd) in the ARGV_LOG entry
  FAKE_U_VERSION_EXIT  exit code of `--version` (default 0; `--version` prints a version line)
  FAKE_U_EXIT          exit code of a review call (default 0)
  FAKE_U_STDOUT        file whose content a review call prints (codex: the text of one completed `agent_message` item, as
                       `{"type":"item.completed","item":{"type":"agent_message","text":...}}`, then `turn.completed`)
  FAKE_CODEX_EVENTS    codex only: file whose lines are printed as they are, in place of FAKE_CODEX_STDOUT's one event
                       (several agent_message items, or a stream with none)
  FAKE_U_DELAY         seconds a review call sleeps before answering
  FAKE_U_PID_FILE      a review call writes its PID here first
  FAKE_U_STDERR_BYTES  a review call writes this many bytes to stderr, then carries on normally
  FAKE_U_FLOOD_STDOUT  a review call writes this many bytes of lines to stdout (codex: its event stream), then keeps running
                       until killed
  FAKE_U_FLOOD_STDERR  the same on stderr
  FAKE_U_FLOOD_EXIT    set: after the flood, answer normally and exit instead of running until killed
  FAKE_U_EXIT_AT       absolute time (epoch seconds): a review call waits until then to answer and exit;
                       FAKE_U_EXIT_TIME_FILE gets the time.time() it exits at
  FAKE_U_LINGER        a review call starts a child that inherits stdout and stderr and sleeps this many seconds,
                       then answers normally and exits; FAKE_U_LINGER_PID_FILE gets the child's PID, and
                       FAKE_U_LINGER_GRANDCHILD_PID_FILE (when set) makes that child start a grandchild and gets its PID
  FAKE_U_FREEZE_PARENT POSIX only: 0.5 s in, a review call stops its parent (review-run.sh's capture loop) with SIGSTOP
                       and has a detached helper resume it this many seconds later
  FAKE_U_SPY          after each stdout/stderr flood returns, write here the size of the largest file under
                       <tempdir>/specwright-run-*/ (review-run.sh's capture files)
  FAKE_OMP_ROLES       file with the JSON `omp config get modelRoles --json` prints (default: roles default and slow)
  FAKE_OMP_MODELS      file with the JSON `omp models find <id> --json` prints (default {"models": []})
  FAKE_OMP_SESSION     file whose content a review call writes to <--session-dir>/session.jsonl
  FAKE_OMP_FIND_EXIT   exit code of `omp config get` / `omp models find` (default 0)
"""
import json
import os
import sys
import time
from pathlib import Path


def flood(stream, n):
    """Write n bytes of newline-terminated lines to a binary stream and flush."""
    line = b"x" * 1023 + b"\n"
    left = n
    while left > 0:
        chunk = line * min(64, -(-left // len(line)))
        stream.write(chunk)
        left -= len(chunk)
    stream.flush()


def main(argv):
    name, args = argv[0], argv[1:]
    u = name.upper()
    env = os.environ.get
    entry = {"cli": name, "argv": args, "cwd": os.getcwd(), "cwd_files": sorted(os.listdir("."))}
    if env(f"FAKE_{u}_READ"):  # what the reviewer sees at this path: (is a link, text), or None when missing
        seen = env(f"FAKE_{u}_READ")
        entry["read"] = [os.path.islink(seen), open(seen, encoding="utf-8").read()] if os.path.exists(seen) else None
    log = env(f"FAKE_{u}_ARGV_LOG")

    def write_log():
        if log:
            with open(log, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(entry) + "\n")

    if args == ["--version"]:
        write_log()
        print(f"{name} 0.0.0-fake")
        return int(env(f"FAKE_{u}_VERSION_EXIT", "0"))
    if name == "omp" and args[:1] in (["config"], ["models"]):
        write_log()
        code = int(env("FAKE_OMP_FIND_EXIT", "0"))
        if code:
            print("omp: lookup failed", file=sys.stderr)
            return code
        if args[0] == "config":
            default = {"key": "modelRoles", "value": {"default": "openai-codex/gpt-6.1-sol:high", "slow": "openai-codex/gpt-6.1-sol:max"}}
            path = env("FAKE_OMP_ROLES")
            print(Path(path).read_text(encoding="utf-8") if path else json.dumps(default))
        else:
            path = env("FAKE_OMP_MODELS")
            print(Path(path).read_text(encoding="utf-8") if path else json.dumps({"models": []}))
        return 0

    pid_file = env(f"FAKE_{u}_PID_FILE")
    if pid_file:
        Path(pid_file).write_text(str(os.getpid()), encoding="utf-8")
    sess = None
    if name == "omp":
        for i, a in enumerate(args):
            if a == "--session-dir" and i + 1 < len(args):
                sess = Path(args[i + 1])
        if sess is not None:
            entry["session_dir_before"] = sorted(str(p.relative_to(sess)) for p in sess.rglob("*")) if sess.is_dir() else None
        for i, a in enumerate(args):
            if a.startswith("@") and args[i - 1] != "--model":
                entry["prompt_file_text"] = Path(a[1:]).read_text(encoding="utf-8")
        entry["stdin"] = ""
    else:
        entry["stdin"] = sys.stdin.buffer.read().decode("utf-8", "replace")
    write_log()
    freeze = env(f"FAKE_{u}_FREEZE_PARENT")
    if freeze:  # POSIX only: a detached helper that holds none of our pipes resumes the parent later
        import signal
        import subprocess
        time.sleep(0.5)  # let the parent set its deadline first
        ppid = os.getppid()
        subprocess.Popen(["sh", "-c", f"sleep {float(freeze)}; kill -CONT {ppid}"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        os.kill(ppid, signal.SIGSTOP)
    if env(f"FAKE_{u}_LINGER"):
        import subprocess
        secs, grand = float(env(f"FAKE_{u}_LINGER")), env(f"FAKE_{u}_LINGER_GRANDCHILD_PID_FILE")
        code = f"import time; time.sleep({secs})"
        if grand:  # the child starts a grandchild of its own, so the tree is three deep
            code = (f"import subprocess, sys, time; g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep({secs})']); "
                    f"open({grand!r}, 'w').write(str(g.pid)); time.sleep({secs})")
        kid = subprocess.Popen([sys.executable, "-c", code])
        if env(f"FAKE_{u}_LINGER_PID_FILE"):
            Path(env(f"FAKE_{u}_LINGER_PID_FILE")).write_text(str(kid.pid))
    delay = float(env(f"FAKE_{u}_DELAY", "0"))
    if delay:
        time.sleep(delay)
    n = int(env(f"FAKE_{u}_STDERR_BYTES", "0"))
    if n:
        flood(sys.stderr.buffer, n)
    floods = [(int(env(f"FAKE_{u}_FLOOD_{k}", "0")), k) for k in ("STDOUT", "STDERR")]
    if any(n for n, _ in floods):
        for n, k in floods:
            if not n:
                continue
            flood(sys.stdout.buffer if k == "STDOUT" else sys.stderr.buffer, n)
            if env(f"FAKE_{u}_SPY"):
                import glob
                import tempfile
                files = glob.glob(os.path.join(tempfile.gettempdir(), "specwright-run-*", "*"))
                Path(env(f"FAKE_{u}_SPY")).write_text(str(max((os.path.getsize(f) for f in files), default=0)))
        while not env(f"FAKE_{u}_FLOOD_EXIT"):  # keep running until killed
            time.sleep(0.2)
    src = env(f"FAKE_{u}_STDOUT")
    text = Path(src).read_text(encoding="utf-8") if src else ""
    if name == "omp" and sess is not None:
        session = env("FAKE_OMP_SESSION")
        sess.mkdir(parents=True, exist_ok=True)
        if session:
            (sess / "session.jsonl").write_text(Path(session).read_text(encoding="utf-8"), encoding="utf-8")
    if name == "codex":
        events = env("FAKE_CODEX_EVENTS")
        out = sys.stdout.buffer
        out.write(json.dumps({"type": "thread.started", "thread_id": "t1"}).encode("utf-8") + b"\n")
        if events:
            out.write(Path(events).read_bytes())
        else:
            item = {"id": "item_0", "type": "agent_message", "text": text}
            out.write(json.dumps({"type": "item.completed", "item": item}, ensure_ascii=False).encode("utf-8") + b"\n")
        out.write(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}).encode("utf-8") + b"\n")
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.flush()
    exit_at = env(f"FAKE_{u}_EXIT_AT")
    if exit_at:
        while time.time() < float(exit_at):
            time.sleep(0.01)
        if env(f"FAKE_{u}_EXIT_TIME_FILE"):
            Path(env(f"FAKE_{u}_EXIT_TIME_FILE")).write_text(repr(time.time()), encoding="utf-8")
    return int(env(f"FAKE_{u}_EXIT", "0"))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
