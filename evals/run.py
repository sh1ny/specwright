"""Run the eval suites in parallel, one process per test file. Stdlib only, Python 3.8+.

A suite is a subdirectory of the evals directory that holds test_*.py files (`fakes` holds none, so it is not one). Each file runs
as `python -m unittest discover -s <root>/<suite> -t <root>/<suite> -p <file>`, so sibling imports resolve as they do for
`python -m unittest discover evals/<suite>`. Files start through bounded.spawn (skills/specwright-pr/scripts/bounded.py), so each
file's whole process tree lives in a job object (Windows) or session (POSIX); a file past --timeout is stopped with bounded.kill.

Usage:  python evals/run.py [--jobs N] [--timeout S] [--root DIR] [suite ...]
        python evals/run.py --ids [--root DIR] [suite ...]
  --jobs N     files run at once (default: the CPU count)
  --timeout S  seconds a file may run before its tree is stopped (default 7200)
  --root DIR   the directory whose subdirectories are the suites (default: the directory of this script)
  --ids        print every test id of the named suites as `suite:test.id`, run no test, exit 0
  No suite named means every suite. Files in SERIAL run one at a time, after the parallel batch.

Output: one line per suite `suite: F files, T tests, S.Ss` (T from unittest's `Ran N tests` line). Each failed or timed-out file
prints `FAILED suite/file (exit code N)` or `FAILED suite/file (timeout after S s)`, the last 200 lines of its output (stderr
included) and `full output: <path>`; that log is kept after the run, the logs of passed files are removed.

Exit codes: 0 every file passed; 1 a file failed, crashed or timed out; 2 an unknown suite or bad arguments (nothing runs).
"""
import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TAIL_LINES = 200
DEFAULT_TIMEOUT = 7200

# Files that run one at a time after the parallel batch: their tests assert deadlines of a few seconds, which CPU load could slip.
SERIAL = {
    "pr-pair/test_bounded.py",  # asserts the deadline and byte bound of bounded.py, a few seconds each
    "review-routes/test_review_run.py",  # its timeout tests assert reviewer deadlines of 2-5 s and a stop within seconds
    # The four below failed only under the parallel batch's load in the first full run (6.3) and pass alone.
    "pr-pair/test_as_sh.py",  # Bounded: a 12 s bound on a hung token lookup and a fenced command that must finish unbounded
    "pr-pair/test_pr_pair.py",  # Bounded: a hung merge PUT must write its pid file before the bound stops it
    "pr-pair/test_pr_snapshot.py",  # TestUntilAttention: watch polls must land within a short --until window
    "release/test_release.py",  # TestBoundedNetwork: a push or gh call cut off by a few-second bound must still land
}


def load_bounded():
    spec = importlib.util.spec_from_file_location("bounded", str(REPO / "skills" / "specwright-pr" / "scripts" / "bounded.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_suites(root):
    return sorted(d.name for d in root.iterdir() if d.is_dir() and any(d.glob("test_*.py")))


def tail(path, lines=TAIL_LINES):
    text = Path(path).read_bytes().decode("utf-8", "replace")
    return "\n".join(text.splitlines()[-lines:])


def tests_run(path):
    data = Path(path).read_bytes()[-65536:].decode("utf-8", "replace")
    found = re.findall(r"^Ran (\d+) tests? in ", data, re.M)
    return int(found[-1]) if found else 0


class Run:
    """The state of one run: the bounded module, the log directory, and the Popens that are running (for the finally)."""

    def __init__(self, root, timeout, bounded, workdir):
        self.root, self.timeout, self.bounded, self.workdir = root, timeout, bounded, workdir
        self.lock = threading.Lock()
        self.running = set()

    def run_file(self, suite, fname):
        """Run one file; returns a dict with its status (rc, or timed_out), tests, start/end times and log path."""
        sdir = self.root / suite
        log = self.workdir / ("%s__%s.log" % (suite, fname))
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(sdir), "-t", str(sdir), "-p", fname]
        res = {"suite": suite, "file": fname, "log": log, "rc": None, "timed_out": False, "tests": 0}
        res["start"] = time.monotonic()
        with open(str(log), "wb") as out:
            p = None
            try:
                p = self.bounded.spawn(cmd, stdout=out, stderr=subprocess.STDOUT, cwd=str(REPO))
                with self.lock:
                    self.running.add(p)
                try:
                    res["rc"] = p.wait(timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    res["timed_out"] = True
                    self.bounded.kill(p)
                    p.wait()
            except OSError as e:
                out.write(("runner: cannot start the file: %s\n" % e).encode("utf-8", "replace"))
                res["rc"] = 127
            finally:
                if p is not None:
                    with self.lock:
                        self.running.discard(p)
                    self.bounded.close_job(p)
        res["end"] = time.monotonic()
        res["tests"] = tests_run(log)
        return res

    def stop_all(self):
        with self.lock:
            procs = list(self.running)
        for p in procs:
            try:
                self.bounded.kill(p)
            finally:
                self.bounded.close_job(p)


def passed(r):
    return not r["timed_out"] and r["rc"] == 0


LIST_IDS = (
    "import sys, unittest\n"
    "d = sys.argv[1]\n"
    "def walk(s):\n"
    "    for t in s:\n"
    "        if isinstance(t, unittest.TestSuite):\n"
    "            for i in walk(t):\n"
    "                yield i\n"
    "        else:\n"
    "            yield t.id()\n"
    "for i in walk(unittest.TestLoader().discover(d, top_level_dir=d)):\n"
    "    print(i)\n")


def list_ids(root, suites):
    for suite in suites:  # one process per suite: suites share module names such as fixtures and test_skill_text
        r = subprocess.run([sys.executable, "-c", LIST_IDS, str(root / suite)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           cwd=str(REPO))
        sys.stderr.write(r.stderr.decode("utf-8", "replace"))
        if r.returncode != 0:
            sys.stderr.write("run.py: listing the ids of %s failed (exit code %d)\n" % (suite, r.returncode))
            return 1
        for line in r.stdout.decode("utf-8", "replace").splitlines():
            print("%s:%s" % (suite, line))
    return 0


def parse(argv):
    ap = argparse.ArgumentParser(prog="run.py", description="Run the eval suites in parallel, one process per test file.")
    ap.add_argument("suites", nargs="*", help="suites to run (default: every suite)")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument("--root", default=str(HERE))
    ap.add_argument("--ids", action="store_true")
    a = ap.parse_args(argv)
    if a.jobs < 1:
        ap.error("--jobs must be at least 1")
    if a.timeout <= 0:
        ap.error("--timeout must be positive")
    return a


def main(argv):
    a = parse(argv)
    root = Path(a.root).resolve()
    if not root.is_dir():
        sys.stderr.write("run.py: --root %s is not a directory\n" % root)
        return 2
    existing = find_suites(root)
    unknown = [s for s in a.suites if s not in existing]
    if unknown:
        sys.stderr.write("run.py: unknown suite %s; the suites that exist: %s\n" % (", ".join(unknown), ", ".join(existing)))
        return 2
    suites = a.suites or existing
    if a.ids:
        return list_ids(root, suites)

    files = [(s, f.name) for s in suites for f in sorted((root / s).glob("test_*.py"))]
    parallel = [x for x in files if "%s/%s" % x not in SERIAL]
    serial = [x for x in files if "%s/%s" % x in SERIAL]
    workdir = Path(tempfile.mkdtemp(prefix="evals-run-"))
    run = Run(root, a.timeout, load_bounded(), workdir)
    results, keep = [], False
    try:
        with ThreadPoolExecutor(max_workers=a.jobs) as pool:
            results.extend(pool.map(lambda x: run.run_file(*x), parallel))
        for x in serial:
            results.append(run.run_file(*x))
        failed = [r for r in results if not passed(r)]
        for suite in suites:
            rs = [r for r in results if r["suite"] == suite]
            wall = (max(r["end"] for r in rs) - min(r["start"] for r in rs)) if rs else 0.0
            print("%s: %d files, %d tests, %.1fs" % (suite, len(rs), sum(r["tests"] for r in rs), wall))
        for r in failed:
            status = "timeout after %g s" % a.timeout if r["timed_out"] else "exit code %d" % r["rc"]
            print("\nFAILED %s/%s (%s)" % (r["suite"], r["file"], status))
            print("--- last %d lines ---" % TAIL_LINES)
            print(tail(r["log"]))
            print("--- end ---")
            print("full output: %s" % r["log"])
        for r in results:
            if passed(r):
                try:
                    r["log"].unlink()
                except OSError:
                    pass
        keep = bool(failed)
        if failed:
            print("\n%d of %d files failed" % (len(failed), len(results)))
        return 1 if failed else 0
    finally:
        run.stop_all()  # an interrupt or an error: no test tree outlives the runner
        if not keep:
            shutil.rmtree(str(workdir), ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.stderr.write("run.py: interrupted\n")
        sys.exit(130)
