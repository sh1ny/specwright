"""Per-process cache of fixture repos: build a shape once, hand out independent copies.

Building a git fixture repo costs many subprocess calls; the suites rebuild identical repos per test.
This module builds each distinct fixture once per test process and copies it for every caller.

API
    cached(key, build) -> Path
        Ensure `build(dest)` has run for `key` and return the cache directory. `build` receives the
        destination Path (it may not exist yet) and builds the fixture into it. Callers must never
        modify the returned directory; use copy() for a working repo.
    copy(key, build, dest) -> Path
        cached(), then shutil.copytree(cache, dest, symlinks=True). `dest` must not exist, like the
        fresh directory a builder gets today. Returns dest.

Keys are any hashable value: pass the builder name plus its shape arguments, never the destination
path. Keys need not be path-safe; each maps to a counter-named subdirectory.

Lifetime: one cache root per process (tempfile.mkdtemp, prefix "sw-fixture-cache-"), created lazily
and removed at exit (read-only safe: git marks object files read-only on Windows). A build that
raises removes its partial directory and re-raises, leaving the key missing so the next call rebuilds.
A build runs with maintenance.auto=false (GIT_CONFIG_COUNT/KEY/VALUE, restored after): otherwise a commit starts
`git maintenance run --auto --detach`, which can still hold objects/maintenance.lock in the cache while copy() reads it.
A builder's git calls must inherit those variables: one that builds its env from a whitelist keeps every GIT_CONFIG_* key.
Not safe across threads or processes by design: each process has its own cache.

Only path-independent stages may be cached. A builder that writes absolute paths (remotes, config,
hooks, worktree links) must do that part after copy(), against the copy's own path.
"""
import atexit
import contextlib
import itertools
import os
import shutil
import sys
import tempfile
from pathlib import Path

_root = None
_entries = {}
_counter = itertools.count()


def _rmtree(path):
    """shutil.rmtree that also removes read-only entries (git marks its objects read-only)."""
    def again(func, p, _exc):
        try:
            os.chmod(p, 0o700)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, **({"onexc": again} if sys.version_info >= (3, 12) else {"onerror": again}))


def _cache_root():
    global _root
    if _root is None:
        _root = Path(tempfile.mkdtemp(prefix="sw-fixture-cache-"))
        atexit.register(_rmtree, _root)
    return _root


@contextlib.contextmanager
def _no_auto_maintenance():
    """Add maintenance.auto=false to the GIT_CONFIG_* variables git reads, then restore them."""
    keys = [k for k in os.environ if k.startswith("GIT_CONFIG_")]
    saved = {k: os.environ[k] for k in keys}
    n = int(os.environ.get("GIT_CONFIG_COUNT") or 0)
    os.environ.update({"GIT_CONFIG_COUNT": str(n + 1), "GIT_CONFIG_KEY_%d" % n: "maintenance.auto",
                       "GIT_CONFIG_VALUE_%d" % n: "false"})
    try:
        yield
    finally:
        for k in [k for k in os.environ if k.startswith("GIT_CONFIG_")]:
            del os.environ[k]
        os.environ.update(saved)


def cached(key, build):
    if key in _entries:
        return _entries[key]
    path = _cache_root() / str(next(_counter))
    try:
        with _no_auto_maintenance():
            build(path)
    except BaseException:
        if path.exists():
            _rmtree(path)
        raise
    _entries[key] = path
    return path


def copy(key, build, dest):
    src = cached(key, build)
    shutil.copytree(src, dest, symlinks=True)
    return Path(dest)
