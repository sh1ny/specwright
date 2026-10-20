"""Scratch git repos for the finish.sh evals (skills/specwright-finish/scripts/finish.sh).

make_repo builds a work tree on `main` with a baseline main spec `<P>/specs/a/spec.md`, `src/app.py` and
`README.md`. make_change adds a change directory (`review.md` with DEFERRED or APPROVE, delta specs).
archive() simulates `openspec archive`: it moves the change directory to `changes/archive/<date>-<name>/`,
syncs each delta into its main spec (modify or create), optionally writes `specwright-change.yaml`, and
leaves the result uncommitted or commits it as A. commit(), edit(), revert() and the git() helper build
later history. run_plan() runs finish.sh; run_scripts() runs the printed `script` and `after_rerun` with
bash (a fake `openspec archive <name> --yes` is on PATH for the after-rerun script).

This module is also the fake `openspec` CLI: `python fixtures.py archive <name> --yes` (FIXTURE_PREFIX
names the openspec root, default `openspec`).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = Path(os.environ.get("FINISH_SH") or ROOT / "skills" / "specwright-finish" / "scripts" / "finish.sh")
DATE = "2026-10-19"
NAME, EMAIL = "Eval Bot", "eval@example.invalid"


def rmtree(path):
    """shutil.rmtree that also removes read-only entries (git marks its objects read-only)."""
    def again(func, p, _exc):
        try:
            os.chmod(p, 0o700)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, **({"onexc": again} if sys.version_info >= (3, 12) else {"onerror": again}))


def git(repo, *args, check=True):
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr}")
    return r.stdout.strip()


def write(repo, rel, text):
    p = Path(repo) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:  # exact bytes: tests control line endings
        f.write(text)


def read(repo, rel):
    return (Path(repo) / rel).read_text(encoding="utf-8")


def edit(repo, rel, old, new):
    text = read(repo, rel)
    assert old in text, f"{old!r} not in {rel}"
    write(repo, rel, text.replace(old, new, 1))


def base_spec(cap):
    return (f"# {cap} Specification\n\n## Purpose\nBaseline purpose of {cap}.\n\n## Requirements\n\n"
            f"### Requirement: Old thing\nThe system SHALL do old.\n\n#### Scenario: Old\n- **WHEN** x\n- **THEN** y\n")


def delta_text(req):
    return (f"## ADDED Requirements\n\n### Requirement: {req}\nThe system SHALL do {req.lower()}.\n\n"
            f"#### Scenario: {req}\n- **WHEN** a\n- **THEN** b\n")


def make_repo(tmp, prefix="openspec", caps=("a",)):
    """A work tree `tmp/work` on main, one commit: README.md, src/app.py and a baseline spec per cap."""
    work = Path(tmp) / "work"
    work.mkdir(parents=True)
    git(work, "init", "-q", "-b", "main")
    for k, v in (("user.name", NAME), ("user.email", EMAIL), ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
        git(work, "config", k, v)
    write(work, "README.md", "# demo\n")
    write(work, "src/app.py", "print('v1')\n")
    for cap in caps:
        write(work, f"{prefix}/specs/{cap}/spec.md", base_spec(cap))
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "initial")
    return work


def commit(repo, subject, files=None):
    """Write files {rel: text}, stage everything, commit; returns the new sha."""
    for rel, text in (files or {}).items():
        write(repo, rel, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", subject)
    return git(repo, "rev-parse", "HEAD")


def make_change(repo, name, verdict="DEFERRED", deltas=None, prefix="openspec", commit_it=True):
    """<prefix>/changes/<name>/ with proposal, design, tasks, review.md and one delta spec per {cap: requirement title}."""
    base = f"{prefix}/changes/{name}"
    write(repo, f"{base}/.openspec.yaml", "schema: specwright\n")
    write(repo, f"{base}/proposal.md", f"## Why\n\nBecause {name}.\n")
    write(repo, f"{base}/design.md", "# Design\n\nOriginal design.\n")
    write(repo, f"{base}/tasks.md", "# Tasks\n\n- [ ] 1.1 do it\n")
    write(repo, f"{base}/review.md", f"# Review\n\n## Verdict\n\nVERDICT: {verdict}\n")
    for cap, req in (deltas or {}).items():
        write(repo, f"{base}/specs/{cap}/spec.md", delta_text(req))
    if commit_it:
        return commit(repo, f"docs({name}): add planning artifacts")


def sync_delta(repo, cap, delta, prefix="openspec"):
    """What `openspec archive` does to the main spec: append the delta's requirements, creating the spec when absent."""
    body = "".join(ln for ln in delta.splitlines(True) if not ln.startswith("## ")).strip("\n")
    rel = f"{prefix}/specs/{cap}/spec.md"
    p = Path(repo) / rel
    if p.exists():
        write(repo, rel, p.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + body + "\n")
    else:
        write(repo, rel, f"# {cap} Specification\n\n## Requirements\n\n{body}\n")


def archive_one(repo, name, prefix="openspec", date=DATE, marker=False):
    src = Path(repo) / prefix / "changes" / name
    dated = name[:4].isdigit() and name[4:5] == "-"  # an already-dated name is archived as it is
    dst = Path(repo) / prefix / "changes" / "archive" / (name if dated else f"{date}-{name}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    specs = dst / "specs"
    if specs.is_dir():
        for p in sorted(specs.rglob("spec.md")):  # nested capabilities: specs/<area>/<id>/spec.md
            if p.parent != specs:
                sync_delta(repo, p.parent.relative_to(specs).as_posix(), p.read_text(encoding="utf-8"), prefix)
    if marker:
        write(repo, f"{prefix}/changes/archive/{dst.name}/specwright-change.yaml", "code_changes: none\n")


def archive(repo, names, prefix="openspec", date=DATE, marker=False, commit_it=False):
    """Simulate the archive of one change or a bulk archive of several; commit it as A when asked. Returns A or None."""
    names = [names] if isinstance(names, str) else list(names)
    for n in names:
        archive_one(repo, n, prefix, date, marker)
    if not commit_it:
        return None
    git(repo, "add", "-A", "--", prefix)
    git(repo, "commit", "-q", "-m", f"chore({', '.join(names)}): archive change")
    return git(repo, "rev-parse", "HEAD")


def revert(repo, sha):
    git(repo, "revert", "--no-edit", sha)
    return git(repo, "rev-parse", "HEAD")


def tree_files(repo, rel):
    """{path relative to rel: text} of the files under rel in the working tree ({} when absent)."""
    base = Path(repo) / rel
    out = {}
    if base.is_dir():
        for p in sorted(base.rglob("*")):
            if p.is_file():
                out[p.relative_to(base).as_posix()] = p.read_text(encoding="utf-8")
    return out


def snapshot(repo):
    """{relative path: bytes} of every file outside .git."""
    repo, out = Path(repo), {}
    for p in repo.rglob("*"):
        if p.is_file() and ".git" not in p.relative_to(repo).parts:
            out[p.relative_to(repo).as_posix()] = p.read_bytes()
    return out


def state(repo):
    """Everything a read-only call must leave alone: HEAD, every ref, the porcelain status, the index, the files."""
    return {"head": git(repo, "rev-parse", "HEAD"), "refs": git(repo, "for-each-ref"),
            "status": git(repo, "status", "--porcelain=v1", "--untracked-files=all"),
            "index": git(repo, "ls-files", "--stage"), "files": snapshot(repo)}


# ---- running finish.sh and the printed scripts ------------------------------------------------------------------
def fake_bin(tmp):
    """A directory whose `openspec` is this module: only `archive <name> --yes` is implemented."""
    d = Path(tmp) / "bin"
    d.mkdir(exist_ok=True)
    f = d / "openspec"
    f.write_text(f'#!/usr/bin/env bash\nexec "{Path(sys.executable).as_posix()}" -X utf8 "{Path(__file__).resolve().as_posix()}" "$@"\n',
                 encoding="utf-8", newline="\n")
    f.chmod(0o755)
    return d


def run_finish(work, *args, cwd=None):
    """Run finish.sh; returns (exit code, parsed JSON, raw stdout + stderr)."""
    r = subprocess.run(["bash", str(SCRIPT), *args], cwd=cwd or work, capture_output=True, text=True, encoding="utf-8")
    try:
        doc = json.loads(r.stdout)
    except ValueError:
        doc = None
    return r.returncode, doc, r.stdout + r.stderr


def run_plan(work, change, archived=None, prefix="openspec", main="main", branch=None, typ=None, cwd=None, dir_=None):
    args = (["--dir", str(dir_)] if dir_ else []) + ["undo-archive-plan", "--change", change,
            "--archived-name", archived or f"{DATE}-{change}", "--prefix", prefix, "--main", main]
    if branch:
        args += ["--branch", branch]
    if typ:
        args += ["--type", typ]
    return run_finish(work, *args, cwd=cwd)


def run_bash(work, tmp, text, name, prefix="openspec"):
    """Save a printed script to a file outside the repo and run it with bash from the work tree."""
    path = Path(tmp) / f"{name}.sh"
    path.write_text(text, encoding="utf-8", newline="\n")
    env = dict(os.environ, PATH=str(fake_bin(tmp)) + os.pathsep + os.environ.get("PATH", ""), FIXTURE_PREFIX=prefix)
    return subprocess.run(["bash", str(path)], cwd=work, capture_output=True, text=True, encoding="utf-8", env=env)


def run_scripts(work, tmp, change, prefix="openspec", between=None, rerun=True, **plan_kw):
    """run_plan, then `script`, then (optionally `between(result)` and, unless rerun is False) `after_rerun` when the plan
    printed one."""
    out = SimpleNamespace(plan=run_plan(work, change, prefix=prefix, **plan_kw), script=None, after=None)
    doc = out.plan[1]
    if doc and doc.get("ok") and doc.get("script"):
        out.script = run_bash(work, tmp, doc["script"], "undo", prefix)
        if between:
            between(out)
        if rerun and doc.get("after_rerun") and out.script.returncode == 0:
            out.after = run_bash(work, tmp, doc["after_rerun"], "after_rerun", prefix)
    return out


def main(argv):
    """The fake openspec CLI."""
    prefix = os.environ.get("FIXTURE_PREFIX", "openspec")
    if len(argv) >= 2 and argv[0] == "archive":
        archive_one(os.getcwd(), argv[1], prefix)
        print(f"Change '{argv[1]}' archived as '{DATE}-{argv[1]}'.")
        return 0
    print("fake openspec: only `archive <name> --yes`", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
