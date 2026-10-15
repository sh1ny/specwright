"""Scratch git repos for the release.sh evals (skills/specwright-release/scripts/release.sh).

make_repo builds a work tree on `main` with version files like Specwright's own (VERSION, a README
badge, skills/*/SKILL.md frontmatter), `openspec/specwright.yaml` with a `release:` block, and a local
bare `origin`. History helpers add one release each in the three merge shapes a project can use:
squash_merge (single parent, subject ends `(#n)`), merge_commit (two parents, `Merge pull request #n
from ...`) and rebase_style (single-parent task commits with no `(#n)`).

Later test groups (release commit, notes, publish) reuse these helpers.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_VERSION_FILES = {
    "VERSION": r"^(\d+\.\d+\.\d+)$",
    "README.md": r"badge/version-(\d+\.\d+\.\d+)-blue",
    "skills/*/SKILL.md": r"^  version: (\S+)$",
}
DEFAULT_SKILLS = ("specwright-pr", "specwright-debug")
DATE = "2026-10-10"
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


def yaml_quote(s):
    return "'" + s.replace("'", "''") + "'"


def settings_text(version_files, enabled=True, merge_method=None, extra_release="", extra=""):
    """openspec/specwright.yaml text. version_files None = no `release:` block at all."""
    out = "finish: pr\n"
    if merge_method:
        out += f"pr:\n  merge_method: {merge_method}\n"
    if version_files is not None:
        out += f"release:\n  enabled: {'true' if enabled else 'false'}\n  version_files:\n"
        for path, rx in version_files.items():
            out += f"    {yaml_quote(path)}: {yaml_quote(rx)}\n"
        out += extra_release
    return out + extra


def skill_text(name, version):
    return f"---\nname: {name}\ndescription: \"x\"\nmetadata:\n  version: {version}\n---\n\n# {name}\n"


def readme_text(version):
    return f"# Demo\n\n![version](https://img.shields.io/badge/version-{version}-blue) ![x](https://img.shields.io/badge/x-1-red)\n"


def make_repo(tmp, version="0.4.2", version_files="default", skills=DEFAULT_SKILLS, enabled=True,
              merge_method=None, extra_release="", with_release_block=True):
    """A work tree `tmp/work` on main with a bare origin `tmp/origin.git`, one commit pushed.

    version_files: "default" (the three Specwright-like entries), a dict path-or-glob -> regex, or None.
    with_release_block False writes a specwright.yaml with no `release:` block. Returns the work tree path."""
    tmp = Path(tmp)
    work, origin = tmp / "work", tmp / "origin.git"
    origin.mkdir(parents=True)
    git(origin, "init", "-q", "--bare", "-b", "main")
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    for k, v in (("user.name", NAME), ("user.email", EMAIL), ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
        git(work, "config", k, v)
    vf = DEFAULT_VERSION_FILES if version_files == "default" else version_files
    write(work, "VERSION", version + "\n")
    write(work, "README.md", readme_text(version))
    for s in skills:
        write(work, f"skills/{s}/SKILL.md", skill_text(s, version))
    write(work, "openspec/specwright.yaml",
          settings_text(vf if with_release_block else None, enabled, merge_method, extra_release))
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "initial")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "origin", "main")
    return work


def commit(repo, subject, files=None, body="", allow_empty=False):
    """Write files {rel: text}, stage everything, commit; returns the new sha."""
    for rel, text in (files or {}).items():
        write(repo, rel, text)
    git(repo, "add", "-A")
    msg = subject + (f"\n\n{body}" if body else "")
    git(repo, "commit", "-q", *(["--allow-empty"] if allow_empty else []), "-m", msg)
    return git(repo, "rev-parse", "HEAD")


def set_version(repo, version, skills=None):
    """Rewrite the version in the default fixture files (and any SKILL.md in `skills`, default all present)."""
    repo = Path(repo)
    files = {"VERSION": version + "\n", "README.md": readme_text(version)}
    for p in sorted((repo / "skills").glob("*/SKILL.md")):
        if skills is None or p.parent.name in skills:
            files[p.relative_to(repo).as_posix()] = skill_text(p.parent.name, version)
    for rel, text in files.items():
        write(repo, rel, text)


def archive_files(change, why="Operators cannot tell which build they run.", date=DATE):
    return {f"openspec/changes/archive/{date}-{change}/proposal.md":
            f"## Why\n\n{why}\n\n## What Changes\n\n- {change}\n"}


def squash_merge(repo, change, version, pr, why="Operators cannot tell which build they run.", date=DATE,
                 skills=None, extra_files=None):
    """One single-parent commit on main, subject ending `(#pr)`, carrying the bump and the archived proposal."""
    set_version(repo, version, skills)
    files = archive_files(change, why, date)
    files.update(extra_files or {})
    return commit(repo, f"feat({change}): do {change} (#{pr})", files)


def merge_commit(repo, change, version, pr, owner="acme", why="Operators cannot tell which build they run.",
                 date=DATE, skills=None):
    """A two-parent `Merge pull request #pr from owner/feat/change` commit on main; the branch holds the bump."""
    branch = f"feat/{change}"
    git(repo, "checkout", "-q", "-b", branch)
    set_version(repo, version, skills)
    commit(repo, f"feat({change}): do {change}", archive_files(change, why, date))
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "-m", f"Merge pull request #{pr} from {owner}/{branch}", branch)
    return git(repo, "rev-parse", "HEAD")


def rebase_style(repo, change, version, tasks=2, why="Operators cannot tell which build they run.", date=DATE):
    """Single-parent task commits straight on main (a rebase merge): none ends `(#n)`; the last carries the bump.
    Returns the shas, oldest first."""
    shas = []
    for i in range(1, tasks):
        shas.append(commit(repo, f"feat({change}): task {i}", {f"src/{change}-{i}.txt": f"{i}\n"}))
    set_version(repo, version)
    shas.append(commit(repo, f"feat({change}): task {tasks}", archive_files(change, why, date)))
    return shas


def push(repo, ref="main"):
    git(repo, "push", "-q", "origin", ref)


def versions_in(repo, rels):
    """The first line's text of each file, for before/after comparisons."""
    return {r: (Path(repo) / r).read_bytes() for r in rels}


def snapshot(repo):
    """{relative path: bytes} of every tracked-or-not file outside .git, to prove a call changed nothing."""
    repo, out = Path(repo), {}
    for p in repo.rglob("*"):
        if p.is_file() and ".git" not in p.relative_to(repo).parts:
            out[p.relative_to(repo).as_posix()] = p.read_bytes()
    return out

