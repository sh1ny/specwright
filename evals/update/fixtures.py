"""Scratch layouts for the update.sh evals (scripts/update.sh).

Builders:
  make_download      a download tree for one version, made from this repo's skills/, agents/, schemas/ and scripts/
                     with VERSION rewritten and an optional edit of the schema
  make_checkout      a scratch code checkout (git, openspec/config.yaml, openspec/.specwright/VERSION, the chosen
                     skills and agents directories) with one version installed from a download
  make_store_pair    a store repo with its own root plus two code repos A and B that declare it; the OpenSpec
                     registry and config live in the scratch directory, so the user's real ones are never touched
Change helpers (a change in flight lives in the working tree, on a local branch or on a remote-tracking ref):
  add_change_worktree, add_change_branch, add_change_remote, archive_change
Run helpers: install_shims (the mv/cp/rm shims of evals/update/shims, copied somewhere executable),
run_update (runs `bash <download>/scripts/update.sh`, optionally killed at the N-th shim call), tree, snapshot.

Paths handed to update.sh are posix(): forward slashes, which Git Bash and Python both read.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # the specwright repo
SHIMS = Path(__file__).resolve().parent / "shims"
if str(ROOT / "evals") not in sys.path:
    sys.path.append(str(ROOT / "evals"))
import fixturecache  # noqa: E402  per-process cache: a path-independent repo is built once and copied
import bashexe  # noqa: E402
NAME, EMAIL = "Eval Bot", "eval@example.invalid"
STORE_ID = "team-plans"
PREFIXES = ("feat", "bugfix", "refactor", "docs", "chore")


def rmtree(path):
    """shutil.rmtree that also removes read-only entries (git marks its objects read-only)."""
    def again(func, p, _exc):
        try:
            if os.path.islink(p):
                raise OSError
            os.chmod(p, 0o700)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, **({"onexc": again} if sys.version_info >= (3, 12) else {"onerror": again}))


def posix(p):
    return Path(p).resolve().as_posix()


def write(base, rel, text):
    p = Path(base) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:  # exact bytes
        f.write(text)
    return p


def git(repo, *args, check=True):
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr}")
    return r.stdout.strip()


def _build_init(repo):
    Path(repo).mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q", "-b", "main")
    for k, v in (("user.name", NAME), ("user.email", EMAIL), ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
        git(repo, "config", k, v)


def init_repo(repo):
    """An empty configured repo on main at `repo`: a copy of one built once per process (its config holds no path).
    `repo` may already exist as an empty directory."""
    repo = Path(repo)
    if repo.exists():
        if any(repo.iterdir()):
            return _build_init(repo)  # init in place, as before
        repo.rmdir()
    fixturecache.copy(("update.init_repo",), _build_init, repo)


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return git(repo, "rev-parse", "HEAD")


# --- download trees ---------------------------------------------------------------------------------------------

def schema_edit_comment(schema_dir):
    """A harmless schema edit: the downloaded schema then differs from the installed one."""
    p = Path(schema_dir) / "schema.yaml"
    p.write_text(p.read_text(encoding="utf-8") + "\n# edited for the update eval\n", encoding="utf-8", newline="")


def schema_edit_dependency(new_artifact="research", ahead_of="specs"):
    """A schema edit that adds artifact `new_artifact` (no requirements) and makes `ahead_of` require it. An existing
    change that has `ahead_of` but not `new_artifact` shows `ahead_of` done beside a dependency that is missing
    (`openspec status` stays exit 0). Returns the edit callable for make_download(schema_edit=...)."""
    def edit(schema_dir):
        p = Path(schema_dir) / "schema.yaml"
        text = p.read_text(encoding="utf-8")
        marker = f"  - id: {ahead_of}\n"
        head, sep, tail = text.partition(marker)
        assert sep, f"artifact {ahead_of} not in schema"
        old_req = "    requires:\n      - proposal\n"
        assert old_req in tail
        tail = tail.replace(old_req, old_req + f"      - {new_artifact}\n", 1)
        added = (f"  - id: {new_artifact}\n    generates: {new_artifact}.md\n    description: Added by the update eval\n"
                 f"    template: proposal.md\n    instruction: |\n      Write {new_artifact}.\n    requires: []\n\n")
        p.write_text(head + added + sep + tail, encoding="utf-8", newline="")
    return edit


def make_download(dest, version, schema_edit=None, stamp_skills=True, drop_skills=(), add_skills=None):
    """A download tree at `dest` (a path that does not exist yet): this repo's skills/, agents/, schemas/, scripts/
    and templates/, with VERSION = version.

    schema_edit: callable(schema_dir) applied to the copied schemas/specwright (see schema_edit_comment).
    stamp_skills: append a `<!-- v{version} -->` line to every SKILL.md, so two versions differ byte for byte.
    drop_skills / add_skills {name: SKILL.md text}: change the set of skill directories.
    Returns the path."""
    dest = Path(dest)
    dest.mkdir(parents=True)
    for d in ("skills", "agents", "schemas", "scripts", "templates"):
        if (ROOT / d).is_dir():
            shutil.copytree(ROOT / d, dest / d, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            (dest / d).mkdir()
    for name in drop_skills:
        rmtree(dest / "skills" / name)
    for name, text in (add_skills or {}).items():
        write(dest, f"skills/{name}/SKILL.md", text)
    if stamp_skills:
        for p in sorted((dest / "skills").glob("*/SKILL.md")):
            with open(p, "a", encoding="utf-8", newline="") as f:
                f.write(f"\n<!-- v{version} -->\n")
    if schema_edit:
        schema_edit(dest / "schemas" / "specwright")
    write(dest, "VERSION", version + "\n")
    return dest


def make_mini_download(dest, version, skills=1, schema_edit=None):
    """make_download with only the first `skills` specwright-* directories and one claude agent file: the same flow
    with a handful of file operations, for the evals that run update.sh many times (the interruption matrix)."""
    names = sorted(p.name for p in (ROOT / "skills").glob("specwright-*") if p.is_dir())
    dl = make_download(dest, version, drop_skills=names[skills:], schema_edit=schema_edit)
    agents = sorted((dl / "agents" / "claude").glob("*.md"))
    for p in agents[1:]:
        p.unlink()
    return dl


# --- checkouts and stores ---------------------------------------------------------------------------------------

class Checkout:
    """A scratch code checkout. Fields: code (Path), root (planning root, Path), skills (list of Path),
    agents ({kind: Path}), version (installed version or None), download (the tree it was installed from)."""

    def __init__(self, code, root, skills, agents, version, download):
        self.code, self.root, self.skills, self.agents = Path(code), Path(root), skills, agents
        self.version, self.download = version, download

    def args(self):
        """The update.sh options that describe this checkout (everything before the subcommand)."""
        out = ["--code", posix(self.code), "--root", posix(self.root)]
        for s in self.skills:
            out += ["--skills", posix(s)]
        for kind, d in self.agents.items():
            out += ["--agents", f"{kind}={posix(d)}"]
        return out

    @property
    def version_file(self):
        return self.code / "openspec" / ".specwright" / "VERSION"

    @property
    def journal(self):
        return self.code / "openspec" / ".specwright" / "update.json"

    @property
    def lock(self):
        return self.code / "openspec" / ".specwright" / "update.lock"

    @property
    def schema(self):
        return self.root / "openspec" / "schemas" / "specwright"


def install_from(download, checkout_paths, write_version=True):
    """Copy what the install prompt installs (Step 4 and the stamp) from `download` into a checkout layout."""
    download = Path(download)
    for sd in checkout_paths.skills:
        sd.mkdir(parents=True, exist_ok=True)
        for p in sorted((download / "skills").glob("specwright-*")):
            if p.is_dir():
                shutil.copytree(p, sd / p.name, ignore=shutil.ignore_patterns("__pycache__"))
    for kind, ad in checkout_paths.agents.items():
        ad.mkdir(parents=True, exist_ok=True)
        for p in sorted((download / "agents" / kind).glob("*.md")):
            shutil.copy(p, ad / p.name)
    schema = checkout_paths.root / "openspec" / "schemas" / "specwright"
    if not schema.exists():  # a store's root already holds its schema
        schema.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(download / "schemas" / "specwright", schema)
    if write_version:
        write(checkout_paths.code, "openspec/.specwright/VERSION", (download / "VERSION").read_text(encoding="utf-8"))


def make_checkout(tmp, version="0.5.0", skills_dirs=(".claude/skills",), agents=(("claude", ".claude/agents"),),
                  download=None, root=None, name="code", commit=True, stamp=True):
    """A code checkout `tmp/<name>` on main with git, openspec/config.yaml (schema: specwright), the chosen skills
    and agents directories and `version` installed from `download` (default: a fresh download tree
    `tmp/dl-<version>`). version=None installs nothing and writes no VERSION (a fresh install).
    root: the planning root (default: the checkout). skills_dirs / agents: paths relative to the checkout.
    Everything is committed (commit=False leaves it untracked). Returns a Checkout."""
    tmp = Path(tmp)
    code = tmp / name
    init_repo(code)
    root = Path(root) if root else code
    if download is None and version is not None:
        download = make_download(tmp / f"dl-{version}-{name}", version)
    shutil.copy(ROOT / "templates" / "openspec" / "config.yaml", _mk(code / "openspec" / "config.yaml"))
    write(code, "README.md", "# scratch project\n")
    co = Checkout(code, root, [code / s for s in skills_dirs], {k: code / v for k, v in agents}, version, download)
    if version is not None:
        install_from(download, co, write_version=stamp)
    if commit:
        commit_all(code, "chore: initial")
    return co


def _mk(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


class StorePair:
    """store (repo with its own root), a and b (Checkouts that declare the store), env (the isolated registry)."""

    def __init__(self, tmp, store, a, b, env):
        self.tmp, self.store, self.a, self.b, self.env = tmp, store, a, b, env


def openspec_env(tmp):
    tmp = Path(tmp)
    return {**os.environ, "XDG_DATA_HOME": posix(tmp / "xdg-data"), "XDG_CONFIG_HOME": posix(tmp / "xdg-config"),
            "OPENSPEC_TELEMETRY": "0"}


def openspec(args, cwd, env=None):
    """Run the real openspec CLI; returns CompletedProcess (text)."""
    return subprocess.run([shutil.which("openspec") or "openspec", *args], cwd=cwd, env=env or {**os.environ, "OPENSPEC_TELEMETRY": "0"},
                          capture_output=True, text=True, encoding="utf-8")


def make_store_pair(tmp, version="0.5.0", store_id=STORE_ID, download=None):
    """tmp/store (a git repo on main: its own root with the installed schema, config.yaml and specs), tmp/code-a and
    tmp/code-b (checkouts whose openspec/config.yaml points at the store, `version` installed, root = the store).
    The store is registered with the real openspec CLI in an isolated registry (XDG_* under tmp). All clean on main.
    download: the tree `version` is installed from (default: a full download tree)."""
    tmp = Path(tmp)
    env = openspec_env(tmp)
    if download is None:
        download = make_download(tmp / f"dl-{version}", version)
    store = tmp / "store"
    init_repo(store)
    shutil.copy(ROOT / "templates" / "openspec" / "config.yaml", _mk(store / "openspec" / "config.yaml"))
    write(store, "openspec/specs/.gitkeep", "")
    schema = store / "openspec" / "schemas" / "specwright"
    schema.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(download / "schemas" / "specwright", schema)
    commit_all(store, "chore: initial store")
    r = openspec(["store", "register", posix(store), "--id", store_id, "--yes"], cwd=tmp, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"openspec store register failed: {r.stderr}{r.stdout}")
    commit_all(store, "chore: register store")  # registration wrote .openspec-store/store.yaml
    checkouts = []
    for n in ("code-a", "code-b"):
        co = make_checkout(tmp, version, download=download, root=store, name=n, commit=False)
        write(co.code, "openspec/config.yaml", f"store: {store_id}\n")  # declares the store
        commit_all(co.code, "chore: initial")
        checkouts.append(co)
    return StorePair(tmp, store, checkouts[0], checkouts[1], env)


def owner_id(co):
    """The owner id update.sh derives for a checkout without an `origin` remote: path:<code toplevel>."""
    return "path:" + posix(co.code)


def store_record_path(store):
    return Path(store) / "openspec" / ".specwright" / "STORE"


def record_text(version, owner):
    return f"version: {version}\nowner: {owner}\n"


def write_store_record(store, version, owner, commit=True, text=None):
    """<store>/openspec/.specwright/STORE (two key: value lines, or `text` as given), committed by default."""
    write(store, "openspec/.specwright/STORE", record_text(version, owner) if text is None else text)
    if commit:
        commit_all(store, "chore: record the store version")


def make_tag_origin(dest, tags):
    """A git repo at `dest` with one commit and a lightweight tag for each of `tags`; returns its posix path (a stand-in
    for the release repository whose tags `git ls-remote --tags` lists)."""
    def build(d):  # init and the one commit: a copy of one built once; the tags follow
        _build_init(d)
        write(d, "README.md", "# releases\n")
        commit_all(d, "chore: initial")
    dest = Path(dest)
    if dest.exists():
        build(dest)
    else:
        fixturecache.copy(("update.tag_origin",), build, dest)
    for t in tags:
        git(dest, "tag", t)
    return posix(dest)


def give_origin(download, url):
    """Make a download tree a git repo whose `origin` is url (what a `git clone` of the release repo looks like)."""
    git(download, "init", "-q")
    git(download, "remote", "add", "origin", url)


# --- changes in flight ------------------------------------------------------------------------------------------

PROPOSAL = ("## Why\n\nUsers need friendly greetings.\n\n## What Changes\n\n- Add `greet`.\n\n## Capabilities\n\n"
            "### New Capabilities\n- `greeting`: greeting messages\n\n## Impact\n\n`greet.py`.\n")
SPEC = ("# Spec Delta\n\n## Purpose\n\nProduces greeting messages for a named person.\n\n## ADDED Requirements\n\n"
        "### Requirement: Greeting\nThe system SHALL return `Hello, <name>!` for a non-empty name.\n\n"
        "#### Scenario: Named greeting\n- **WHEN** greet is called with `Ada`\n- **THEN** it returns `Hello, Ada!`\n")


def change_files(name, schema="specwright", files=None):
    """{relative path under the change dir: text} for a small valid change. `files` adds or replaces entries
    (a value of None drops one)."""
    out = {".openspec.yaml": f"schema: {schema}\ncreated: 2026-10-07\n", "proposal.md": PROPOSAL,
           "specs/greeting/spec.md": SPEC}
    for k, v in (files or {}).items():
        if v is None:
            out.pop(k, None)
        else:
            out[k] = v
    return out


def _write_change(repo, name, planning, schema, files):
    for rel, text in change_files(name, schema, files).items():
        write(repo, f"{planning}/changes/{name}/{rel}", text)


def add_change_worktree(repo, name, planning="openspec", schema="specwright", files=None):
    """A change directory in the working tree of `repo` (left untracked and uncommitted)."""
    _write_change(repo, name, planning, schema, files)


def add_change_branch(repo, name, prefix="feat", planning="openspec", schema="specwright", files=None, base="main"):
    """Local branch `<prefix>/<name>` holding the change, committed; the checkout returns to `base`, so main and the
    working tree hold no change directory (what specwright-branch leaves behind)."""
    branch = f"{prefix}/{name}"
    git(repo, "checkout", "-q", "-b", branch, base)
    _write_change(repo, name, planning, schema, files)
    commit_all(repo, f"feat({name}): scaffold")
    git(repo, "checkout", "-q", base)
    return branch


def add_change_remote(repo, name, prefix="feat", planning="openspec", schema="specwright", files=None, remote="origin",
                      base="main"):
    """`refs/remotes/<remote>/<prefix>/<name>` holding the change, with no local branch and no real remote."""
    tmp_branch = f"tmp-remote-{name}"
    git(repo, "checkout", "-q", "-b", tmp_branch, base)
    _write_change(repo, name, planning, schema, files)
    sha = commit_all(repo, f"feat({name}): scaffold")
    git(repo, "checkout", "-q", base)
    git(repo, "branch", "-q", "-D", tmp_branch)
    ref = f"refs/remotes/{remote}/{prefix}/{name}"
    git(repo, "update-ref", ref, sha)
    return ref


def archive_change(repo, name, date="2026-10-01", planning="openspec"):
    """Commit `<planning>/changes/archive/<date>-<name>/` on the current branch (main)."""
    write(repo, f"{planning}/changes/archive/{date}-{name}/proposal.md", PROPOSAL)
    return commit_all(repo, f"chore: archive {name}")


# --- running ----------------------------------------------------------------------------------------------------

def install_shims(dest):
    """Copy the mv/cp/rm shims to `dest` (made executable; the checkout does not need the mode bit). Returns the dir."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for n in ("mv", "cp", "rm"):
        target = dest / n
        shutil.copy(SHIMS / n, target)
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def run_update(download, args, cwd=None, env=None, shim_dir=None, count_file=None, kill_at=None, timeout=300):
    """Run `bash <download>/scripts/update.sh <args>`; returns (exit code, parsed JSON or None, stdout, stderr).

    shim_dir (from install_shims) goes first on PATH. count_file: UPDATE_SHIM_COUNT. kill_at: UPDATE_KILL_AT; the
    script is started through `bash -c 'UPDATE_KILL_PID=$$ exec bash ...'`, so the shims kill the script's own process.
    """
    script = Path(download) / "scripts" / "update.sh"
    env = dict(env or os.environ)
    env.setdefault("OPENSPEC_TELEMETRY", "0")
    if shim_dir:
        env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    if count_file:
        env["UPDATE_SHIM_COUNT"] = posix(count_file)
    if kill_at is not None:
        env["UPDATE_KILL_AT"] = str(kill_at)
    argv = [bashexe.bash(), "-c", 'export UPDATE_KILL_PID=$$; exec bash "$@"', "update-eval", posix(script), *map(str, args)]
    r = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    doc = None
    out = r.stdout.strip()
    if out:
        try:
            doc = json.loads(out)
        except ValueError:
            doc = None
    return r.returncode, doc, r.stdout, r.stderr


def tree(path):
    """{relative posix path: bytes} of every file under path (empty dict when it does not exist). Directories are
    listed as `<path>/` with empty bytes, so an empty directory counts."""
    path, out = Path(path), {}
    if not path.exists():
        return out
    for p in sorted(path.rglob("*")):
        rel = p.relative_to(path).as_posix()
        out[rel + "/" if p.is_dir() else rel] = b"" if p.is_dir() else p.read_bytes()
    return out


def snapshot(repo):
    """tree() of a checkout without .git: proves a call changed nothing."""
    return {k: v for k, v in tree(repo).items() if k.split("/")[0] != ".git"}


def scratch_dir():
    return Path(tempfile.mkdtemp())
