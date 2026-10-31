"""Run the eval suites in parallel, one process per test file. Stdlib only, Python 3.8+.

A suite is a subdirectory of the evals directory that holds test_*.py files (`fakes` holds none, so it is not one). Each file runs
as `python -m unittest discover -s <root>/<suite> -t <root>/<suite> -p <file>`, so sibling imports resolve as they do for
`python -m unittest discover evals/<suite>`. Files start through bounded.spawn (skills/specwright-pr/scripts/bounded.py), so each
file's tree lives in a job object (Windows) or session (POSIX); a file past --timeout is stopped with bounded.kill. On POSIX a
session a file's own bounded.spawn starts is not part of that one: each spawn records its pid in the file's
SPECWRIGHT_TEST_SPAWN_DIR (<workdir>/spawns/<n>/), and the runner kills every recorded group after bounded.kill.

Usage:  python evals/run.py [--jobs N] [--timeout S] [--root DIR] [suite ...]
        python evals/run.py --ids [--root DIR] [suite ...]
        python evals/run.py --list-suites [--root DIR]
        python evals/run.py --changed BASE [--jobs N] [--timeout S] [--root DIR]
  --jobs N     files run at once (default: the CPU count)
  --timeout S  seconds a file may run before its tree is stopped (default 7200)
  --root DIR   the directory whose subdirectories are the suites (default: the directory of this script)
  --ids        print every test id of the named suites as `suite:test.id`, run no test, exit 0
  --list-suites  print every suite as a JSON array, run no test, exit 0 (not combined with suite names or --ids)
  --changed BASE  run only what <root>/suites.json maps the changed paths to: the paths that differ between the merge base of BASE
                  and HEAD and the working tree (untracked files included). Prints each selected target with the paths that
                  selected it first; a path the map does not cover is printed as `uncovered` and selects every suite; when
                  nothing needs an eval it prints `no eval suite covers these changes` and exits 0. Not combined with suite
                  names, --ids or --list-suites. Git runs in the repository that holds --root.
  No suite named means every suite. Files in SERIAL run one at a time, after the parallel batch.

Output: one line per suite `suite: F files, T tests, K skipped, S.Ss` (T from unittest's `Ran N tests` line, K from `skipped=N` on its closing `OK (...)`/`FAILED (...)` line; S from the suite's first file
start to its last file end, so with several suites named it includes their files too: time a suite by naming it alone). Each failed or timed-out file
prints `FAILED suite/file (exit code N)` or `FAILED suite/file (timeout after S s)`, the last 200 lines of its output (stderr
included) and `full output: <path>`; that log is kept after the run, the logs of passed files are removed.

Exit codes: 0 every file passed; 1 a file failed, crashed or timed out; 2 an unknown suite, bad arguments or an invalid suite map (nothing runs);
with --changed also a suite-map target that does not exist, or a BASE git cannot resolve (unknown, or no merge base with HEAD).
"""
import argparse
import importlib.util
import itertools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TAIL_LINES = 200
DEFAULT_TIMEOUT = 7200
POLL = 0.5  # seconds between checks while a file runs, so an interrupt is seen at once (a plain Windows wait is not interruptible)

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


# The suite map (<root>/suites.json) says which suites a changed path selects:
#   {"rules": [{"paths": ["skills/x/**"], "suites": ["release", "git-workflow/test_specs_strict.py"]}], "no_eval": ["docs/adr/**"]}
# A path selects the union of the targets of every rule it matches (explicit and built-in). A target is a suite or one test file
# `suite/test_*.py`. no_eval applies only to a path no rule matches. A path nothing covers is "uncovered" (the caller runs everything).
SHARED_HARNESS = ("run.py", "fixturecache.py")  # relative to the evals directory; with fakes/** they select every suite


def map_error(path, why):
    sys.stderr.write("run.py: %s: %s\n" % (path, why))
    sys.exit(2)


def load_map(root):
    """Read <root>/suites.json; exit 2 naming the file when it is unreadable, not JSON or not shaped as documented."""
    path = Path(root) / "suites.json"
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError) as e:
        map_error(path, "cannot read the suite map: %s" % e)

    def strings(v):
        return isinstance(v, list) and all(isinstance(x, str) for x in v)

    if not isinstance(data, dict) or not isinstance(data.get("rules"), list) or not strings(data.get("no_eval")):
        map_error(path, 'the suite map must be {"rules": [...], "no_eval": [...]}')
    for rule in data["rules"]:
        if not isinstance(rule, dict) or not strings(rule.get("paths")) or not strings(rule.get("suites")):
            map_error(path, 'every rule must be {"paths": [...], "suites": [...]}: %s' % json.dumps(rule))
    return data


def pattern_regex(pattern):
    """`**` matches any run of characters including `/`, `*` any run within one path segment, `?` one character of a segment."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def matches(patterns, path):
    return next((p for p in patterns if pattern_regex(p).match(path)), None)


def missing_targets(smap, root):
    """One message per target of the map that is no suite of `root` and no test file of one."""
    suites, out = find_suites(Path(root)), []
    for rule in smap["rules"]:
        for t in rule["suites"]:
            suite, _, fname = t.partition("/")
            if suite not in suites or (fname and not (fname.startswith("test_") and fname.endswith(".py")
                                                       and (Path(root) / suite / fname).is_file())):
                out.append("missing target: %s (named by a rule for %s)" % (t, ", ".join(rule["paths"])))
    return out


def classify(smap, root, prefix, paths):
    """Sort repo-relative `paths` (forward slashes) by the map. `prefix` is the root's path in the repo ("evals"; "" when the
    root is the repo top). Returns (selected, uncovered, no_eval): selected maps each target (a suite or `suite/test_x.py`) to
    the paths that selected it; uncovered lists the paths nothing covers; no_eval the paths only the no_eval list covers."""
    suites = find_suites(Path(root))
    base = prefix.strip("/") + "/" if prefix.strip("/") else ""
    selected, uncovered, no_eval = {}, [], []
    for path in paths:
        targets, rest = [], path[len(base):] if path.startswith(base) else None
        if rest is not None:
            head = rest.split("/")[0]
            if "/" in rest and head in suites:
                targets.append(head)
            elif rest in SHARED_HARNESS or rest.startswith("fakes/"):
                targets.extend(suites)
                targets.append(None)  # covered even when no suite exists
        for rule in smap["rules"]:
            if matches(rule["paths"], path):
                targets.extend(rule["suites"])
        if targets:
            for t in targets:
                if t is not None and path not in selected.setdefault(t, []):
                    selected[t].append(path)
        elif matches(smap["no_eval"], path):
            no_eval.append(path)
        else:
            uncovered.append(path)
    return selected, uncovered, no_eval


def check_map(smap, root, prefix, paths):
    """The problems of the map for the file list `paths`, as messages: each uncovered file, each missing target, each file a
    no_eval pattern shares with a rule. An empty list means the map is sound."""
    problems = missing_targets(smap, root)
    selected, uncovered, _ = classify(smap, root, prefix, paths)
    problems.extend("uncovered file: %s (no rule or no_eval pattern matches it)" % p for p in uncovered)
    selecting = set(p for ps in selected.values() for p in ps)
    for p in paths:
        pat = matches(smap["no_eval"], p)
        if pat and p in selecting:
            problems.append("no_eval overlap: %s matches the no_eval pattern %s and a rule" % (p, pat))
    return problems


def dedupe_targets(targets):
    """Drop repeats, and a file target whose whole suite is also a target (the file runs once, as part of the suite)."""
    out = []
    for t in targets:
        if t not in out and not ("/" in t and t.split("/")[0] in targets):
            out.append(t)
    return out


def tail(path, lines=TAIL_LINES):
    text = Path(path).read_bytes().decode("utf-8", "replace")
    return "\n".join(text.splitlines()[-lines:])


def tests_run(path):
    data = Path(path).read_bytes()[-65536:].decode("utf-8", "replace")
    found = re.findall(r"^Ran (\d+) tests? in ", data, re.M)
    return int(found[-1]) if found else 0


def tests_skipped(path):
    data = Path(path).read_bytes()[-65536:].decode("utf-8", "replace")
    found = re.findall(r"^(?:OK|FAILED) \((?:[^)]*, )?skipped=(\d+)", data, re.M)
    return int(found[-1]) if found else 0


class Run:
    """The state of one run: the bounded module, the log directory, the Popens that are running and whether the run is
    stopping (an interrupt or an error: no file starts after it, and every running tree is stopped)."""

    def __init__(self, root, timeout, bounded, workdir):
        self.root, self.timeout, self.bounded, self.workdir = root, timeout, bounded, workdir
        self.lock = threading.Lock()
        self.running = set()
        self.stopping = False
        self.counter = itertools.count(1)

    def stop(self, p):
        """bounded.kill(p), then (POSIX) a killpg of every pid the file's nested bounded.spawn calls recorded: those sessions
        are not in p's group. Windows job objects nest, so bounded.kill reaches them."""
        self.bounded.kill(p)
        d = getattr(p, "spawn_dir", None)
        if d is None or os.name == "nt":
            return
        try:
            names = os.listdir(str(d))
        except OSError:
            return
        for name in names:
            if not name.isdigit():
                continue
            try:
                os.killpg(int(name), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            except OSError:
                pass

    def run_file(self, suite, fname):
        """Run one file; returns a dict with its status (rc, or timed_out), tests, start/end times and log path."""
        sdir = self.root / suite
        log = self.workdir / ("%s__%s.log" % (suite, fname))
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(sdir), "-t", str(sdir), "-p", fname]
        res = {"suite": suite, "file": fname, "log": log, "rc": None, "timed_out": False, "tests": 0, "skipped": 0}
        res["start"] = time.monotonic()
        with self.lock:
            if self.stopping:  # a queued file after an interrupt: never started
                res.update(rc=130, end=res["start"])
                return res
        with open(str(log), "wb") as out:
            p = None
            try:
                spawn_dir = self.workdir / "spawns" / str(next(self.counter))
                spawn_dir.mkdir(parents=True, exist_ok=True)
                env = {**os.environ, "SPECWRIGHT_TEST_SPAWN_DIR": str(spawn_dir)}
                p = self.bounded.spawn(cmd, stdout=out, stderr=subprocess.STDOUT, cwd=str(REPO), env=env)
                p.spawn_dir = spawn_dir
                with self.lock:
                    self.running.add(p)
                    stopping = self.stopping
                if stopping:  # stop_all ran between the check above and the spawn
                    self.stop(p)
                deadline = res["start"] + self.timeout
                try:
                    while res["rc"] is None:
                        left = deadline - time.monotonic()
                        if left <= 0:
                            res["timed_out"] = True
                            self.stop(p)
                            p.wait()
                            break
                        try:
                            res["rc"] = p.wait(timeout=min(POLL, left))
                        except subprocess.TimeoutExpired:
                            pass
                except BaseException:  # an interrupt in the serial phase lands here: stop the tree before the finally drops it
                    self.stop(p)
                    raise
            except OSError as e:
                out.write(("runner: cannot start the file: %s\n" % e).encode("utf-8", "replace"))
                res["rc"] = 127
            finally:
                if p is not None:
                    with self.lock:
                        self.running.discard(p)
                    self.stop(p)  # a leftover of the file, and every session its nested bounded.spawn calls started, dies here
                    self.bounded.close_job(p)
        res["end"] = time.monotonic()
        res["tests"] = tests_run(log)
        res["skipped"] = tests_skipped(log)
        return res

    def stop_all(self):
        with self.lock:
            self.stopping = True
            procs = list(self.running)
        for p in procs:
            try:
                self.stop(p)
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


def git_out(top, *args):
    """Run git in `top`; returns (stdout bytes, "") or (None, the error text)."""
    try:
        r = subprocess.run(["git", "-C", str(top)] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        return None, str(e)
    if r.returncode != 0:
        return None, r.stderr.decode("utf-8", "replace").strip() or "git exited with code %d" % r.returncode
    return r.stdout, ""


def changed_paths(root, base):
    """The paths that differ between the merge base of `base` and HEAD and the working tree (untracked files included), as
    (prefix, paths): prefix is the root's place in the repository, paths are repo-relative with forward slashes. Exits 2 when git
    cannot answer (an unknown base, no merge base, not a repository)."""
    def fail(why):
        sys.stderr.write("run.py: --changed %s: %s\n" % (base, why))
        sys.exit(2)

    out, err = git_out(root, "rev-parse", "--show-toplevel")
    if out is None:
        fail("cannot find the git repository of %s: %s" % (root, err))
    top = Path(out.decode("utf-8", "replace").strip()).resolve()
    try:
        prefix = Path(root).resolve().relative_to(top).as_posix()
    except ValueError:
        fail("%s is not inside the git repository %s" % (root, top))
    prefix = "" if prefix == "." else prefix
    out, err = git_out(top, "merge-base", base, "HEAD")
    if out is None or not out.strip():
        fail("no merge base of %s and HEAD%s" % (base, ": " + err if err else ""))
    mb = out.decode("utf-8", "replace").strip()
    paths = []
    for args in (("diff", "--name-only", "-z", "--no-renames", mb, "--"), ("ls-files", "-z", "--others", "--exclude-standard")):
        out, err = git_out(top, *args)
        if out is None:
            fail("git %s failed: %s" % (args[0], err))
        paths.extend(p for p in out.decode("utf-8", "replace").split("\0") if p)
    return prefix, sorted(set(paths))


def select_changed(root, base):
    """Resolve `--changed base` into the (suite, file) pairs to run; None when no suite covers the changes. Prints what selected
    them. Exits 2 on an invalid map, a missing target or a git failure, before anything runs."""
    smap = load_map(root)
    missing = missing_targets(smap, root)
    if missing:
        for m in missing:
            sys.stderr.write("run.py: %s\n" % m)
        sys.exit(2)
    prefix, paths = changed_paths(root, base)
    selected, uncovered, _ = classify(smap, root, prefix, paths)
    if not selected and not uncovered:
        print("no eval suite covers these changes")
        return None
    for target, why in selected.items():
        print("%s: %s" % (target, ", ".join(why)))
    for p in uncovered:
        print("uncovered: %s (running every suite)" % p)
    if uncovered:
        targets = find_suites(Path(root))
    else:
        targets = dedupe_targets(list(selected))
    files = []
    for t in targets:
        suite, _, fname = t.partition("/")
        for f in ([fname] if fname else [x.name for x in sorted((Path(root) / suite).glob("test_*.py"))]):
            if (suite, f) not in files:
                files.append((suite, f))
    return files


def parse(argv):
    ap = argparse.ArgumentParser(prog="run.py", description="Run the eval suites in parallel, one process per test file.")
    ap.add_argument("suites", nargs="*", help="suites to run (default: every suite)")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument("--root", default=str(HERE))
    ap.add_argument("--ids", action="store_true")
    ap.add_argument("--list-suites", action="store_true")
    ap.add_argument("--changed", metavar="BASE")
    a = ap.parse_args(argv)
    if a.changed is not None:
        if a.suites:
            ap.error("--changed and suite names cannot be combined")
        if a.ids or a.list_suites:
            ap.error("--changed cannot be combined with --ids or --list-suites")
        if not a.changed or a.changed.startswith("-"):
            ap.error("--changed needs a git ref, not %r" % a.changed)
    if a.jobs < 1:
        ap.error("--jobs must be at least 1")
    if a.timeout <= 0:
        ap.error("--timeout must be positive")
    if a.list_suites and (a.suites or a.ids):
        ap.error("--list-suites is not combined with suite names or --ids")
    return a


def main(argv):
    a = parse(argv)
    root = Path(a.root).resolve()
    if not root.is_dir():
        sys.stderr.write("run.py: --root %s is not a directory\n" % root)
        return 2
    existing = find_suites(root)
    if a.list_suites:
        print(json.dumps(existing))
        return 0
    if a.changed is not None:
        files = select_changed(root, a.changed)
        if files is None:
            return 0
        suites = list(dict.fromkeys(s for s, _ in files))
    else:
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
        pool, pending = ThreadPoolExecutor(max_workers=a.jobs), set()
        try:
            futures = [pool.submit(run.run_file, *x) for x in parallel]
            pending = set(futures)
            while pending:  # short waits, so an interrupt reaches the finally below while files still run
                pending = wait(pending, timeout=POLL, return_when=FIRST_COMPLETED)[1]
            results.extend(f.result() for f in futures)
        finally:
            if pending:
                run.stop_all()  # before the shutdown below waits for the workers: their trees stop, queued files never start
            pool.shutdown(wait=True)
        for x in serial:
            results.append(run.run_file(*x))
        failed = [r for r in results if not passed(r)]
        for suite in suites:
            rs = [r for r in results if r["suite"] == suite]
            wall = (max(r["end"] for r in rs) - min(r["start"] for r in rs)) if rs else 0.0
            print("%s: %d files, %d tests, %d skipped, %.1fs" % (
                suite, len(rs), sum(r["tests"] for r in rs), sum(r["skipped"] for r in rs), wall))
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
        run.stop_all()  # an interrupt or an error: no test tree outlives the runner (a no-op after a clean run)
        if not keep:
            shutil.rmtree(str(workdir), ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.stderr.write("run.py: interrupted\n")
        sys.exit(130)
