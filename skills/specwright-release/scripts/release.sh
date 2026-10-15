#!/usr/bin/env bash
# Release decisions for a project that opted in (release.enabled in openspec/specwright.yaml): do the version
# files agree, bump them to a target, and which release commit carries a version. Every subcommand prints ONE
# JSON document.
#
# Usage: bash release.sh [--dir <repo>] <subcommand> [options]
#   check                             read the version files in the working tree: exactly one match per file, one shared
#                                     version -> version + the files read
#   bump --to MAJOR.MINOR.PATCH       rewrite only the captured version in every version file (temp file + rename each);
#                                     the target must be greater than the current version. Never commits. Rerunning an
#                                     interrupted bump to the same target completes it
#   status --version V [--main <ref>] V's release commit (first commit on <ref>'s first-parent history whose primary file
#                                     reads V); its version files must all read V
#   publish --version V               opt-in and merge-method gates only for now
# Settings (openspec/specwright.yaml): release.enabled (default false), release.version_files (path or glob ->
# regex with one capture group; the first entry is the primary file), release.tag (v{version}),
# release.github_release (true), release.auto (false), pr.merge_method (rebase is refused with releases on).
# Exit: 0 done, 1 stop (the JSON has "ok": false, "error" and "message"), 2 usage, 3 a git or gh network call failed.
# Needs bash, git and Python 3.8+.
set -euo pipefail

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
[ -n "$py" ] || { echo '{"ok":false,"error":"no_python","message":"release.sh needs python 3.8+"}'; exit 2; }

exec "$py" -I -X utf8 - "$@" <<'PYSRC'
import glob as globmod
import json
import os
import re
import subprocess
import sys
import tempfile

ENV = dict(os.environ)


class Stop(Exception):
    def __init__(self, error, message="", code=1, **extra):
        super().__init__(message or error)
        self.error, self.message, self.code, self.extra = error, message or error, code, extra

    def obj(self):
        return {"ok": False, "error": self.error, "message": self.message, **self.extra}


def usage(msg):
    raise Stop("usage", msg, code=2)


def emit(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    sys.exit(code)


def run(cmd, cwd=None, data=None):
    try:
        return subprocess.run(cmd, cwd=cwd, env=ENV, input=data, capture_output=True)
    except OSError as e:
        return subprocess.CompletedProcess(cmd, 127, b"", str(e).encode())


def git(d, *args, data=None):
    return run(["git", *args], cwd=d, data=data)


def text_of(r):
    return r.stdout.decode("utf-8", "replace").strip()


def err_of(r):
    return r.stderr.decode("utf-8", "replace").strip()


def parse_args(argv, spec):
    a, pos, i = {}, [], 0
    while i < len(argv):
        t = argv[i]
        if t in spec:
            if i + 1 >= len(argv):
                usage(f"{t} needs a value")
            a[spec[t]] = argv[i + 1]
            i += 2
        elif t.startswith("--"):
            usage(f"unknown option {t}")
        else:
            pos.append(t)
            i += 1
    return a, pos


# ---- a small YAML reader: maps, scalars, flow maps/lists, comments (all specwright.yaml uses) ------------------
def strip_comment(s):
    q, esc = None, False
    for i, ch in enumerate(s):
        if esc:
            esc = False
        elif q:
            if q == '"' and ch == "\\":
                esc = True
            elif ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i]
    return s


def split_top(s, sep=","):
    parts, depth, q, esc, cur = [], 0, None, False, ""
    for ch in s:
        if esc:
            esc = False
        elif q:
            if q == '"' and ch == "\\":
                esc = True
            elif ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append(cur)
            cur = ""
            continue
        cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def scalar(v):
    v = v.strip()
    if v == "":
        return None
    if v[0] == "{" and v[-1] == "}":
        out = {}
        for part in split_top(v[1:-1]):
            k, _, val = part.partition(":")
            out[unquote(k.strip())] = scalar(val)
        return out
    if v[0] == "[" and v[-1] == "]":
        return [scalar(p) for p in split_top(v[1:-1])]
    if v[0] in "\"'" and v[-1] == v[0] and len(v) >= 2:
        return unquote(v)
    if v.lower() in ("true", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    if v in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


YAML_ESCAPES = {"0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r",
                "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0", "L": "\u2028", "P": "\u2029"}


def unquote(k):
    """Strip a scalar's quotes and decode them as YAML does: `''` in single quotes, backslash escapes in double."""
    if len(k) < 2 or k[0] not in "\"'" or k[-1] != k[0]:
        return k
    body = k[1:-1]
    if k[0] == "'":
        return body.replace("''", "'")

    def esc(m):
        e = m.group(1)
        return chr(int(e[1:], 16)) if len(e) > 1 else YAML_ESCAPES.get(e, m.group(0))
    return re.sub(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)", esc, body)


BLOCK_HEADER = re.compile(r"^([|>])([+-]?)\d*$")


def block_scalar(raw, start, indent, style, chomp):
    """Read a `|` or `>` block scalar from raw lines after a key at `indent`; returns (value, next raw index)."""
    end = start
    while end < len(raw) and (not raw[end].strip() or len(raw[end]) - len(raw[end].lstrip(" ")) > indent):
        end += 1
    body = [l.rstrip("\r") for l in raw[start:end]]
    filled = [l for l in body if l.strip()]
    pad = len(filled[0]) - len(filled[0].lstrip(" ")) if filled else 0
    lines = [l[pad:] if l.strip() else "" for l in body]
    trailing = 0
    while lines and lines[-1] == "":
        lines.pop()
        trailing += 1
    if style == "|":
        text = "\n".join(lines)
    else:
        text, prev = "", None
        for l in lines:
            text += "\n" if l == "" else (" " + l if prev else l)
            prev = l != ""
    if not lines or chomp == "-":
        return text, end
    return text + "\n" + ("\n" * trailing if chomp == "+" else ""), end


class Map(dict):
    """A YAML mapping that also keeps each plain scalar's text as written (`yes` stays `yes` in messages)."""
    def __init__(self):
        super().__init__()
        self.text = {}


def parse_yaml(text):
    raw = text.splitlines()
    lines = []
    for n, r in enumerate(raw):
        s = strip_comment(r).rstrip()
        if s.strip():
            lines.append((len(s) - len(s.lstrip(" ")), s.strip(), n))

    def block(i, indent):
        d = Map()
        while i < len(lines) and lines[i][0] == indent:
            body = lines[i][1]
            m = re.match(r"^((?:\"(?:[^\"\\]|\\.)*\"|'(?:[^']|'')*'|[^:\s][^:]*?)):(?:\s+(.*))?$", body)
            if not m:
                i += 1
                continue
            key, val = unquote(m.group(1).strip()), m.group(2)
            row = lines[i][2]
            i += 1
            header = BLOCK_HEADER.match(val.strip()) if val else None
            if header:
                d[key], end = block_scalar(raw, row + 1, indent, header.group(1), header.group(2))
                while i < len(lines) and lines[i][2] < end:
                    i += 1
            elif val is None or val.strip() == "":
                if i < len(lines) and lines[i][0] > indent:
                    d[key], i = block(i, lines[i][0])
                else:
                    d[key] = None
            else:
                d[key] = scalar(val)
                d.text[key] = val.strip()
        return d, i

    return block(0, lines[0][0])[0] if lines else {}


# ---- settings ---------------------------------------------------------------------------------------------------
class Settings:
    def __init__(self, root):
        self.root = root
        p = os.path.join(root, "openspec", "specwright.yaml")
        try:
            with open(p, encoding="utf-8") as f:
                doc = parse_yaml(f.read())
        except FileNotFoundError:
            doc = {}
        rel = doc.get("release") if isinstance(doc.get("release"), dict) else {}
        pr = doc.get("pr") if isinstance(doc.get("pr"), dict) else {}
        self.enabled = rel.get("enabled") is True
        self.version_files = rel.get("version_files")
        self.tag = rel.get("tag") if isinstance(rel.get("tag"), str) and rel.get("tag") else "v{version}"
        self.github_release = rel.get("github_release") is not False
        self.auto = rel.get("auto") is True
        self.merge_method = str(pr.get("merge_method") or "").strip().lower()
        self.main_branch = doc.get("main_branch") if isinstance(doc.get("main_branch"), str) else None

    def gate(self, rebase=False):
        """Stop before any write unless releases are enabled (and, for bump and publish, not with rebase merges)."""
        if not self.enabled:
            raise Stop("release_disabled", "releases are off: set release.enabled: true in openspec/specwright.yaml")
        if rebase and self.merge_method == "rebase":
            raise Stop("rebase_merge", "release.enabled cannot be used with pr.merge_method: rebase: a rebase merge "
                       "leaves no single release commit; change pr.merge_method or set release.enabled to false")

    def entries(self):
        vf = self.version_files
        if not isinstance(vf, dict) or not vf:
            raise Stop("no_version_files", "release.version_files must map each path or glob to a regular expression")
        out = []
        for path, rx in vf.items():
            if not isinstance(rx, str) or not rx:
                raise Stop("bad_version_files", f"release.version_files entry '{path}' needs a regular expression")
            try:
                c = re.compile(rx, re.M)
            except re.error as e:
                raise Stop("bad_version_files", f"release.version_files entry '{path}': invalid pattern '{rx}': {e}")
            if c.groups != 1:
                raise Stop("bad_version_files", f"release.version_files entry '{path}': pattern '{rx}' must have exactly one "
                           f"capture group (has {c.groups})")
            out.append((str(path), rx, c))
        return out


# ---- version files: the working tree and a commit ---------------------------------------------------------------
def glob_regex(pat):
    """A git-path glob as a regex: `*` and `?` stop at `/`, `**/` spans directories."""
    out, i = "", 0
    while i < len(pat):
        c = pat[i]
        if pat.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        elif c == "[" and pat.find("]", i + 2) > 0:
            j = pat.find("]", i + 2)
            body = pat[i + 1:j]
            neg = body[:1] in ("!", "^")
            out += "[" + ("^" if neg else "") + (body[1:] if neg else body).replace("\\", "\\\\") + "]"
            i = j
        else:
            out += re.escape(c)
        i += 1
    return re.compile(out + r"\Z")


def has_glob(p):
    return any(ch in p for ch in "*?[")


class WorkTree:
    label = "the working tree"

    def __init__(self, root):
        self.root = root

    def files(self, pattern):
        if has_glob(pattern):
            hits = globmod.glob(os.path.join(globmod.escape(self.root), pattern), recursive=True)
        else:
            hits = [os.path.join(self.root, pattern)]
        return sorted({os.path.relpath(h, self.root).replace(os.sep, "/") for h in hits if os.path.isfile(h)})

    def read_all(self, paths):
        out = {}
        for p in paths:
            with open(os.path.join(self.root, p), "rb") as f:
                out[p] = f.read()
        return out


def cat_batch(root, specs):
    """Contents for `<commit>:<path>` specs through one `git cat-file --batch`; None for a missing object."""
    if not specs:
        return []
    r = git(root, "cat-file", "--batch", data=("\n".join(specs) + "\n").encode("utf-8", "surrogateescape"))
    if r.returncode != 0:
        raise Stop("git_failed", f"git cat-file failed: {err_of(r)}", code=3)
    buf, pos, out = r.stdout, 0, []
    for _ in specs:
        nl = buf.index(b"\n", pos)
        head = buf[pos:nl].decode("utf-8", "replace").split(" ")
        pos = nl + 1
        if head[-1] == "missing" or len(head) < 3:
            out.append(None)
            continue
        size = int(head[2])
        out.append(buf[pos:pos + size])
        pos += size + 1
    return out


class CommitTree:
    def __init__(self, root, commit):
        self.root, self.commit = root, commit
        self.label = f"commit {commit[:12]}"
        self._names = None

    def names(self):
        if self._names is None:
            r = git(self.root, "ls-tree", "-r", "--name-only", "-z", self.commit)
            if r.returncode != 0:
                raise Stop("git_failed", f"git ls-tree failed at {self.commit}: {err_of(r)}", code=3)
            self._names = [n for n in r.stdout.decode("utf-8", "surrogateescape").split("\0") if n]
        return self._names

    def files(self, pattern):
        if not has_glob(pattern):
            return [pattern] if pattern in self.names() else []
        rx = glob_regex(pattern)
        return sorted(n for n in self.names() if rx.match(n))

    def read_all(self, paths):
        paths = list(paths)
        got = cat_batch(self.root, [f"{self.commit}:{p}" for p in paths])
        return {p: (b if b is not None else b"") for p, b in zip(paths, got)}


def decode(raw):
    return raw.decode("utf-8", "surrogateescape")


def read_versions(tree, entries):
    """Apply every entry to `tree`. Returns (matches, problems); matches: [(file, [re.Match], raw bytes)]."""
    problems, per_entry = [], []
    for path, rx, c in entries:
        fs = tree.files(path)
        if not fs:
            problems.append({"kind": "no_file", "entry": path,
                             "text": f"version_files entry '{path}' matches no file in {tree.label}"})
        per_entry.append((path, rx, c, fs))
    data = tree.read_all(sorted({f for _, _, _, fs in per_entry for f in fs}))
    matches = []
    for path, rx, c, fs in per_entry:
        for f in fs:
            ms = list(c.finditer(decode(data[f])))
            matches.append((f, ms, data[f]))
            if len(ms) != 1:
                problems.append({"kind": "match_count", "file": f, "entry": path, "pattern": rx, "count": len(ms),
                                 "text": f"{f}: pattern '{rx}' (entry '{path}') matches {len(ms)} times, expected exactly 1"})
    return matches, problems


def invalid(tree, matches, problems):
    return Stop("version_files_invalid", f"version files are not readable in {tree.label}: " + "; ".join(p["text"] for p in problems),
                problems=[{k: v for k, v in p.items() if k != "text"} for p in problems],
                files=sorted({m[0] for m in matches}))


def disagree(tree, by, files):
    split = "; ".join(f"{v} in {', '.join(fs)}" for v, fs in by.items())
    return Stop("version_files_disagree", f"version files disagree in {tree.label}: {split}", versions=by, files=files)


def group(matches):
    by = {}
    for f, ms, _ in matches:
        by.setdefault(ms[0].group(1), []).append(f)
    return by


def agree(tree, entries):
    """Exactly one match per file and one shared version, else stop naming each offending file.
    Returns (version, files read)."""
    matches, problems = read_versions(tree, entries)
    if problems:
        raise invalid(tree, matches, problems)
    by, files = group(matches), sorted({m[0] for m in matches})
    if len(by) > 1:
        raise disagree(tree, by, files)
    return next(iter(by)), files


# ---- semver -----------------------------------------------------------------------------------------------------
def sv(v):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", v)
    return tuple(int(x) for x in m.groups()) if m else None


# ---- subcommands ------------------------------------------------------------------------------------------------
def cmd_check(st, a):
    version, files = agree(WorkTree(st.root), st.entries())
    return {"ok": True, "version": version, "files": files}


def cmd_bump(st, a):
    st.gate(rebase=True)
    target = a.get("to")
    if not target:
        usage("bump needs --to MAJOR.MINOR.PATCH")
    if not re.fullmatch(r"\d+\.\d+\.\d+", target):
        raise Stop("bad_target", f"the target version must be MAJOR.MINOR.PATCH (digits only, e.g. 0.5.0), got '{target}'")
    tree = WorkTree(st.root)
    matches, problems = read_versions(tree, st.entries())
    if problems:
        raise invalid(tree, matches, problems)
    by, files = group(matches), sorted({m[0] for m in matches})
    present = sorted(by, key=lambda v: (sv(v) is None, sv(v) or (0, 0, 0), v))
    if len(present) == 1:
        current = present[0]
        if sv(current) is None:
            raise Stop("bad_current", f"the current version '{current}' is not MAJOR.MINOR.PATCH, so {target} cannot be compared")
        if sv(target) <= sv(current):
            raise Stop("target_not_greater", f"the target {target} must be greater than the current version {current}")
    elif len(present) == 2 and present[1] == target and sv(present[0]) is not None and sv(present[0]) < sv(target):
        current = present[0]  # an interrupted bump to this same target: complete it (D7)
    else:
        raise disagree(tree, by, files)
    # every replacement in memory first, then one temp file + rename per file
    plan = {}
    for f, ms, raw in matches:
        m = ms[0]
        if m.group(1) != target:
            plan[f] = (decode(raw)[:m.start(1)] + target + decode(raw)[m.end(1):]).encode("utf-8", "surrogateescape")
    changed, pending = [], sorted(plan)
    for f in sorted(plan):
        full = os.path.join(st.root, f)
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(prefix=".release-", dir=os.path.dirname(full))
            with os.fdopen(fd, "wb") as out:
                out.write(plan[f])
            try:
                os.chmod(tmp, os.stat(full).st_mode & 0o7777)
            except OSError:
                pass
            os.replace(tmp, full)
            tmp = None
            changed.append(f)
            pending.remove(f)
        except OSError as e:
            raise Stop("write_failed", f"writing {f} failed: {e}; written: {', '.join(changed) or 'none'}; not written: "
                       f"{', '.join(pending)}. Rerun bump --to {target} to complete it", written=changed, pending=pending)
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    return {"ok": True, "from": current, "to": target, "changed": changed, "files": files}


def detect_main(st):
    names = [st.main_branch] if st.main_branch else ["main", "master"]
    for n in names:
        if git(st.root, "show-ref", "--verify", "--quiet", f"refs/heads/{n}").returncode == 0:
            return n
    return names[0]


def release_commit(st, entries, ref, version):
    """First commit on ref's first-parent history whose primary file reads `version`, or None."""
    path, _, c = entries[0]
    spec = f":(glob){path}" if has_glob(path) else f":(literal){path}"
    r = git(st.root, "log", "--first-parent", "--format=%H", "--reverse", ref, "--", spec)
    if r.returncode != 0:
        raise Stop("git_failed", f"git log failed: {err_of(r)}", code=3)
    for sha in text_of(r).split():
        tree = CommitTree(st.root, sha)
        fs = tree.files(path)
        if not fs:
            continue
        data = tree.read_all(fs)
        if {m.group(1) for f in fs for m in c.finditer(decode(data[f]))} == {version}:
            return sha
    return None


def cmd_status(st, a):
    v = a.get("version")
    if not v:
        usage("status needs --version")
    entries = st.entries()
    ref = a.get("main") or detect_main(st)
    if git(st.root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
        raise Stop("no_main", f"main ref '{ref}' does not exist")
    sha = release_commit(st, entries, ref, v)
    if not sha:
        raise Stop("no_release_commit", f"no commit on {ref}'s first-parent history has {v} in the primary file '{entries[0][0]}'")
    shared, files = agree(CommitTree(st.root, sha), entries)
    if shared != v:
        raise Stop("version_mismatch", f"version files at release commit {sha[:12]} read {shared}, not {v}")
    return {"ok": True, "version": v, "release_commit": sha, "main": ref, "files": files}


def cmd_publish(st, a):
    st.gate(rebase=True)
    if not a.get("version"):
        usage("publish needs --version")
    raise Stop("not_implemented", "publish is not implemented yet")


COMMANDS = {
    "check": (cmd_check, {}),
    "bump": (cmd_bump, {"--to": "to"}),
    "status": (cmd_status, {"--version": "version", "--main": "main"}),
    "publish": (cmd_publish, {"--version": "version", "--main": "main"}),
}


def main(argv):
    rest, d = list(argv), None
    if rest[:1] == ["--dir"]:
        if len(rest) < 2:
            usage("--dir needs a value")
        d, rest = rest[1], rest[2:]
    if not rest or rest[0] not in COMMANDS:
        usage("usage: release.sh [--dir <repo>] check | bump --to V | status --version V [--main ref] | publish --version V")
    fn, spec = COMMANDS[rest[0]]
    a, pos = parse_args(rest[1:], spec)
    if pos:
        usage(f"unexpected argument {pos[0]}")
    d = d or os.getcwd()
    r = git(d, "rev-parse", "--show-toplevel")
    if r.returncode != 0 or not text_of(r):
        raise Stop("not_a_repo", f"{d} is not inside a git work tree")
    st = Settings(os.path.normpath(text_of(r)))
    st.gate()
    emit(fn(st, a))


try:
    main(sys.argv[1:])
except Stop as e:
    emit(e.obj(), e.code)
except SystemExit:
    raise
except Exception as e:  # a bug must still answer with one JSON document
    emit({"ok": False, "error": "internal_error", "message": f"{type(e).__name__}: {e}"}, 1)
PYSRC
