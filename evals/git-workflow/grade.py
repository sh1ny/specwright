"""Grade git-workflow eval runs by inspecting each run's repo and report.

Usage: python grade.py <iteration-dir>
Writes <run-dir>/grading.json for every eval-*/<config>/run-*/ that has a repo.
A store run's repo/ holds code/ (and usually store/) plus gh-log.jsonl from the
fake gh; those runs are graded by check_store().
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fakes"))
import gqlops  # noqa: E402  reads the operations of a GraphQL document

INITIAL = "chore: initial project"
STORE_MAIN = ["chore: register store", "chore: initial store"]  # newest first, as a fixture store leaves its main
STORE_PR_BODY = "Plans for add-greeting."  # the open store PR #3 of eval-store-ship-code-push-rejected-store-pr-open
PLAN_SUBJECT = "feat(add-greeting): add planning artifacts"
TASKS = ("1.1", "1.2", "2.1")
CHANGE = "openspec/changes/add-greeting"


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8")
    # rstrip only: porcelain status lines start with a meaningful space.
    return r.stdout.rstrip() if r.returncode == 0 else None


def subjects(repo, rng):
    out = git(repo, "log", "--format=%s", rng)
    return out.splitlines() if out else []


def status_of(repo):
    """Porcelain status lines, ignoring __pycache__ from running tests."""
    return [l for l in (git(repo, "status", "--porcelain", "--untracked-files=all") or "").splitlines()
            if "__pycache__" not in l]


def gh_calls(repo):
    """Calls the fake gh logged for this run, oldest first; [] if it was never used."""
    p = repo / "gh-log.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def is_store_run(repo):
    """Store layouts hold repo/code; repo/store is absent in the nested and unregistered ones."""
    return (repo / "code").is_dir()


def files_of(repo, rev):
    """Paths a commit touches, renames listed as a delete plus an add."""
    return [l for l in (git(repo, "show", "--name-only", "--no-renames", "--format=", rev) or "").splitlines() if l]


def find_commit(repo, subject, rng="--all"):
    """Newest commit whose subject is exactly `subject`, or None."""
    for line in (git(repo, "log", "--format=%H%x09%s", rng) or "").splitlines():
        h, _, s = line.partition("\t")
        if s == subject:
            return h
    return None


def history_paths(repo):
    return [l for l in (git(repo, "log", "--all", "--name-only", "--format=") or "").splitlines() if l]


def amends(repo):
    return [l for l in (git(repo, "reflog", "--all") or "").splitlines() if "(amend)" in l]


def registry_root(repo):
    """The planning root `openspec list --json` resolves from repo, with an empty registry
    (throwaway XDG dirs) so the user's own stores cannot interfere. Returns (Path|None, evidence)."""
    exe = shutil.which("openspec")
    if not exe:
        return None, "openspec not on PATH"
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "XDG_DATA_HOME": tmp, "XDG_CONFIG_HOME": tmp, "OPENSPEC_TELEMETRY": "0"}
        r = subprocess.run([exe, "list", "--json"], cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8")
    try:
        root = (json.loads(r.stdout).get("root") or {}).get("path")
    except ValueError:
        return None, f"not JSON: {(r.stdout or r.stderr)[:120]!r}"
    return (Path(root).resolve() if root else None), f"root={root}"


def only_code_repo(repo, run, expected):
    """The "Only the code repo changed" assertion: no git repository under the run dir other
    than repo itself, the planning root resolves to repo, and the commits in the repo are
    exactly `expected` (a list of subjects, or a predicate over the subjects of `git log --all`)."""
    others = []
    for d, dirs, files in os.walk(run):
        here = Path(d)
        if (".git" in dirs or ".git" in files) and here.resolve() != repo.resolve():
            others.append(str(here))
        if ".git" in dirs:
            dirs.remove(".git")
    root, ev = registry_root(repo)
    allsubs = subjects(repo, "--all")
    ok = expected(allsubs) if callable(expected) else sorted(allsubs) == sorted(expected)
    return ("Only the code repo changed", not others and root == repo.resolve() and ok,
            f"other repos={others} {ev} commits={allsubs}")


FEAT = "feat/add-greeting"
SUBJ = {"1.1": "feat(add-greeting): task 1.1 Add greet(name)", "1.2": "feat(add-greeting): task 1.2 Add farewell(name)",
        "2.1": "feat(add-greeting): task 2.1 Document greet and farewell"}  # the fixtures' original task subjects
NOOP_ASK = r"no-op\?|was [^.\n]*a no-op|did [^.\n]* change (any )?code|whether [^.\n]*no-op"


def count_all(repo):
    return int(git(repo, "rev-list", "--count", "--all") or -1)


def ticked_tasks(store):
    """Task numbers ticked in the store's live tasks.md."""
    p = store / CHANGE / "tasks.md"
    return re.findall(r"^- \[x\] (\d+\.\d+) ", p.read_text(encoding="utf-8"), re.M) if p.exists() else []


def diff_ticks(store, *args):
    """Task numbers a diff (`git diff` or `git show`) in the store ticks."""
    return re.findall(r"^\+- \[x\] (\d+\.\d+) ", git(store, *args) or "", re.M)


def untouched(code, store, ccount, scount, tips):
    """No new commit in either repo: commit counts over --all and each repo's HEAD subject match the fixture."""
    cc, sc = count_all(code), count_all(store)
    head = lambda r: (subjects(r, "-1") or [None])[0]
    return (cc == ccount and sc == scount and head(code) == tips[0] and head(store) == tips[1],
            f"code commits={cc} (want {ccount}) store commits={sc} (want {scount}) heads={head(code)!r} / {head(store)!r}")


def completion_by_repo(rep):
    """What the report gives per repo: a task-commit count and a clean tree. A line (or ';' part) naming
    only one repo sets the context for the lines after it, so headings, bullets and tables all work."""
    found = {"code": set(), "store": set()}
    ctx = None
    for line in rep.splitlines():
        for seg in line.split(";"):
            c, s_ = re.search(r"\bcode\b", seg), re.search(r"\bstore\b", seg)
            if c and not s_:
                ctx = "code"
            elif s_ and not c:
                ctx = "store"
            if ctx is None or (c and s_):
                continue  # names both repos: cannot be attributed
            if "task commit" in seg:
                found[ctx].add("commits")
            if re.search(r"(?<!not )(?<!un)clean", seg):
                found[ctx].add("clean")
    return found


def asks_about(rep, topic):
    """One sentence of the report both names `topic` (a regex) and asks (a question mark, 'whether' or 'confirm')."""
    ask = r"\?|whether|confirm|let me know|please (tell|say|advise)"
    return any(re.search(topic, s) and re.search(ask, s) for s in re.split(r"(?<=[.?!])\s+|\n", rep))


def offers(rep, topic):
    """asks_about, or one paragraph block (text between blank lines) names `topic` and has a question: an offer whose
    question and option list sit on adjacent lines, such as "Shall I create the branch?" over "- Yes: git checkout -b <topic>"."""
    return asks_about(rep, topic) or any(re.search(topic, b) and "?" in b for b in re.split(r"\n\s*\n", rep))


MARK = r"[\s*`_]*"  # whitespace or markup: all that may sit between a connector and a coordinated mode
COORD = re.compile(MARK + r"(?:,[\s*`_]*(?:or|and)\b|\b(?:or|and)\b|[/,])" + MARK + r"(next|close)\b")
BOUND = (re.compile(r"roadmap[^\w.!?\n]{0,3}?(next|close)\b"), re.compile(r"`(next|close)`"))  # never across a sentence end


def roadmap_offer(rep):
    """The roadmap modes (next, close) the report offers. Only a sentence that asks (asks_about), or a paragraph block with a
    question (as in offers), and names the roadmap counts. In it a mode counts when it is bound to the command: `specwright-roadmap
    close`, `roadmap: close` (up to three non-word characters between), or a backticked `close`; a mode coordinated with a bound
    one (or, and, / or a comma, then only whitespace or markup) is bound too. A bare next or close elsewhere does not count."""
    rep = rep.lower()
    units = [s for s in sentences(rep) if asks_about(s, "roadmap")] + [b for b in re.split(r"\n\s*\n", rep) if "roadmap" in b and "?" in b]
    found = set()
    for u in units:
        for rx in BOUND:
            for m in rx.finditer(u):
                found.add(m.group(1))
                pos = m.end()
                while True:
                    c = COORD.match(u, pos)
                    if not c:
                        break
                    found.add(c.group(1))
                    pos = c.end()
    return found


def report(run):
    p = run / "outputs" / "report.md"
    return p.read_text(encoding="utf-8").lower() if p.exists() else ""


def main_unchanged(repo):
    return subjects(repo, "main") == [INITIAL]


def check(name, repo, run):
    branch = git(repo, "branch", "--show-current")
    branches = (git(repo, "branch", "--format=%(refname:short)") or "").splitlines()
    # __pycache__ comes from running the tests; the fixture has no .gitignore.
    status = status_of(repo)
    rep = report(run)
    R = []  # (text, passed, evidence)

    if name == "eval-branch-dirty-main":
        R.append(("Still on main", branch == "main", f"branch={branch}"))
        R.append(("No new branch was created", branches == ["main"], f"branches={branches}"))
        d = repo / "openspec/changes/add-csv-export"
        R.append(("No change directory openspec/changes/add-csv-export was created", not d.exists(), f"exists={d.exists()}"))
        stash = git(repo, "stash", "list") or ""
        R.append(("The uncommitted README edit is still uncommitted and unstashed",
                  " M README.md" in status and main_unchanged(repo) and not stash, f"status={status} stash={stash!r}"))
        hit = re.search(r"uncommitted|not clean|dirty|local changes|modified", rep)
        R.append(("The report tells the user the tree is not clean", bool(hit), f"match={hit.group(0) if hit else None}"))

    elif name == "eval-branch-clean-main":
        R.append(("Branch bugfix/fix-login-timeout exists and is checked out",
                  branch == "bugfix/fix-login-timeout", f"branch={branch} branches={branches}"))
        tip = git(repo, "rev-parse", "bugfix/fix-login-timeout")
        R.append(("The branch starts at main's HEAD with no new commits",
                  tip is not None and tip == git(repo, "rev-parse", "main"), f"branch tip={tip}"))
        d = repo / "openspec/changes/fix-login-timeout"
        R.append(("The change directory openspec/changes/fix-login-timeout exists", d.is_dir(), f"exists={d.is_dir()}"))
        R.append(("main is unchanged", main_unchanged(repo), f"main log={subjects(repo, 'main')}"))
        R.append(only_code_repo(repo, run, [INITIAL]))

    elif name == "eval-apply-three-tasks":
        R.append(("Still on feat/add-greeting and main is unchanged",
                  branch == "feat/add-greeting" and main_unchanged(repo), f"branch={branch} main={subjects(repo, 'main')}"))
        subs = subjects(repo, "main..HEAD")
        R.append(("A planning-artifacts commit exists: feat(add-greeting): add planning artifacts",
                  PLAN_SUBJECT in subs, f"subjects={subs}"))
        per = {t: [s for s in subs if s.startswith(f"feat(add-greeting): task {t}")] for t in TASKS}
        R.append(("Exactly one commit per task, subjects start with feat(add-greeting): task 1.1 / 1.2 / 2.1",
                  all(len(v) == 1 for v in per.values()), f"per-task={per}"))
        long_ = [s for s in subs if len(s) > 72]
        R.append(("Every commit subject is 72 characters or fewer", bool(subs) and not long_, f"too long={long_}"))
        ever = git(repo, "log", "--all", "--format=%h", "--", "scratch-notes.txt") or ""
        R.append(("scratch-notes.txt was never committed and is still untracked",
                  not ever and "?? scratch-notes.txt" in status, f"commits touching it={ever!r} status={status}"))
        tasks = repo / "openspec/changes/add-greeting/tasks.md"
        if not tasks.exists():
            arch = list(repo.glob("openspec/changes/archive/*add-greeting/tasks.md"))
            tasks = arch[0] if arch else tasks
        t = tasks.read_text(encoding="utf-8") if tasks.exists() else ""
        R.append(("All tasks in tasks.md are ticked", bool(t) and "- [ ]" not in t and t.count("- [x]") == 3,
                  f"unticked={t.count('- [ ]')} ticked={t.count('- [x]')}"))
        tr = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=repo, capture_output=True, text=True)
        R.append(("The test suite passes", tr.returncode == 0, (tr.stderr or tr.stdout).strip().splitlines()[-1:] or ["no output"]))
        R.append(("Working tree is clean apart from scratch-notes.txt",
                  status == ["?? scratch-notes.txt"], f"status={status}"))
        R.append(("The report does not treat the pre-existing scratch-notes.txt as blocking",
                  bool(rep) and not re.search(r"not clean|tree is dirty|until then", rep), f"report excerpt={rep[-160:]!r}"))

    elif name == "eval-finish-local":
        allsubs = subjects(repo, "--all")
        R.append(("Archive commit on the branch: feat(add-greeting): archive change",
                  "feat(add-greeting): archive change" in allsubs, f"subjects={allsubs}"))
        R.append(("Now on main", branch == "main", f"branch={branch}"))
        parents = (git(repo, "log", "-1", "--format=%P", "main") or "").split()
        head = (subjects(repo, "-1") or [None])[0]
        R.append(("main HEAD is a merge commit with two parents and subject merge: add-greeting",
                  len(parents) == 2 and head == "merge: add-greeting", f"parents={len(parents)} subject={head}"))
        R.append(("Branch feat/add-greeting was deleted", "feat/add-greeting" not in branches, f"branches={branches}"))
        R.append(("Working tree is clean", not status, f"status={status}"))
        tr = lambda rev: sorted(l for l in (git(repo, "log", "-1", "--format=%(trailers:only,unfold)", rev) or "").splitlines() if l)
        arch = git(repo, "log", "--all", "--format=%H", "--grep=archive change", "-1")
        R.append(("The merge commit carries the same trailers as the branch's archive commit",
                  bool(arch) and tr("main") == tr(arch), f"merge={tr('main')} archive={tr(arch) if arch else None}"))

    elif name in ("eval-finish-resume-after-archive-commit", "eval-finish-resume-from-main"):
        allsubs = subjects(repo, "--all")
        archive = [s for s in allsubs if s == "feat(add-greeting): archive change"]
        R.append(("Exactly one archive commit feat(add-greeting): archive change exists, the one the earlier attempt made",
                  len(archive) == 1, f"archive commits={len(archive)}"))
        merges = [s for s in (git(repo, "log", "--first-parent", "--format=%s", "main") or "").splitlines() if s == "merge: add-greeting"]
        parents = (git(repo, "log", "-1", "--format=%P", "main") or "").split()
        head = git(repo, "log", "-1", "--format=%s", "main")
        R.append(("main has exactly one merge: add-greeting commit with two parents, at its HEAD",
                  len(merges) == 1 and len(parents) == 2 and head == "merge: add-greeting", f"merges={len(merges)} parents={len(parents)} head={head}"))
        R.append(("Branch feat/add-greeting was deleted and the repo is on main",
                  branch == "main" and branches == ["main"], f"branch={branch} branches={branches}"))
        remotes = git(repo, "remote") or ""
        R.append(("Nothing was pushed: the repo has no remote and no gh call was made",
                  not remotes and not gh_calls(repo), f"remotes={remotes!r} gh calls={len(gh_calls(repo))}"))
        R.append(("Working tree is clean", not status, f"status={status}"))
        if name == "eval-finish-resume-from-main":
            R.append(("The report does not give the Nothing to finish stop line", "nothing to finish - archive is on" not in rep, f"report excerpt={rep[-240:]!r}"))
        R.append(("No commit was amended", not amends(repo), f"amend entries={amends(repo)}"))
        R.append(only_code_repo(repo, run, [INITIAL, PLAN_SUBJECT, "feat(add-greeting): implement tasks 1.1-2.1",
                                            "feat(add-greeting): archive change", "merge: add-greeting"]))

    elif name in ("eval-finish-resume-squash-merged", "eval-finish-resume-merged-branch-gone", "eval-finish-resume-stale-main"):
        R.extend(check_finish_resume_merged(name, repo, branch, branches, status, rep))

    elif name in ("eval-watch-agent-merge", "eval-watch-merge-default-user", "eval-agent-merge-release-auto"):
        R.extend(check_watch_merge(name, repo, branch, branches, status, rep))

    elif name in ("eval-finish-release-offer", "eval-finish-release-auto", "eval-finish-release-disabled"):
        R.extend(check_finish_release(name, repo, branch, branches, status, rep))

    elif name == "eval-finish-local-release-reported":
        R.extend(check_finish_local_release(repo, branch, branches, status, rep, run))

    elif name in ("eval-roadmap-next-gap", "eval-roadmap-next-gap-dirty-main"):
        fx = json.loads((repo / ".git" / "fixture-state.json").read_text(encoding="utf-8"))
        rm = "openspec/roadmap.md"
        roadmap_commits = (git(repo, "log", "--all", "--format=%H", "--", rm) or "").splitlines()
        if name == "eval-roadmap-next-gap":
            R.append(("main is unchanged", git(repo, "rev-parse", "main") == fx["main"], f"main={git(repo, 'rev-parse', 'main')}"))
            on = git(repo, "rev-parse", "--verify", "-q", "feat/add-farewell")
            new = (git(repo, "log", "--format=%H", "main..feat/add-farewell") or "").splitlines() if on else []
            files = files_of(repo, new[0]) if len(new) == 1 else None
            added = git(repo, "show", "--format=", new[0], "--", rm) if len(new) == 1 else ""
            R.append(("Branch feat/add-farewell has exactly one commit, which changes only the roadmap file and adds add-farewell",
                      len(new) == 1 and files == [rm] and bool(re.search(r"^\+.*add-farewell", added or "", re.M)),
                      f"branch={bool(on)} commits={len(new)} files={files}"))
            d = repo / "openspec/changes/add-farewell"
            R.append(("The change directory openspec/changes/add-farewell exists", d.is_dir(), f"exists={d.is_dir()}"))
        else:
            text = (repo / rm).read_text(encoding="utf-8") if (repo / rm).exists() else None
            R.append(("The roadmap file is unchanged", text == fx["roadmap"], f"same={text == fx['roadmap']}"))
            R.append(("No roadmap commit exists on any branch beyond the fixture's",
                      roadmap_commits == [fx["roadmap_commit"]], f"roadmap commits={roadmap_commits}"))
            R.append(("main is unchanged and the README edit is still uncommitted",
                      git(repo, "rev-parse", "main") == fx["main"] and " M README.md" in status, f"status={status}"))
        R.append(("No commit was amended", not amends(repo), f"amend entries={amends(repo)}"))

    elif name == "eval-roadmap-next-milestone-end":
        R.extend(check_roadmap_milestone_end(repo, branch, branches, status, rep))

    elif name == "eval-roadmap-close-agreed-split":
        R.extend(check_roadmap_close_agreed_split(repo, branch, branches, status))
        R.append(("No commit was amended", not amends(repo), f"amend entries={amends(repo)}"))

    elif name == "eval-apply-on-main":
        R.append(("No commit was added to main", main_unchanged(repo), f"main log={subjects(repo, 'main')}"))
        hit = re.search(r"on (the )?main|feature branch|create (a |the )?branch|specwright-branch", rep)
        R.append(("The report flags that apply started on main and offers to create a branch",
                  bool(hit), f"match={hit.group(0) if hit else None}"))
    if name in ("eval-apply-three-tasks", "eval-finish-local"):
        R.append(("No commit was amended", not amends(repo), f"amend entries={amends(repo)}"))
    if name == "eval-apply-three-tasks":
        def expected_apply(subs):
            return len(subs) == 5 and INITIAL in subs and PLAN_SUBJECT in subs and all(
                len([s for s in subs if s.startswith(f"feat(add-greeting): task {t}")]) == 1 for t in TASKS)
        R.append(only_code_repo(repo, run, expected_apply))
    elif name == "eval-finish-local":
        R.append(only_code_repo(repo, run, [INITIAL, PLAN_SUBJECT, "feat(add-greeting): implement tasks 1.1-2.1",
                                            "feat(add-greeting): archive change", "merge: add-greeting"]))
    return R


def git_trace(repo):
    """Argument lists of the git commands the run made, from the GIT_TRACE file the fixture's eval.env sets (git-trace.log in the
    run's repo): one entry per `trace: built-in: git ...` line. None if the file is missing or holds no command."""
    p = repo / "git-trace.log"
    if not p.exists():
        return None
    cmds = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"trace: built-in: git (.*)$", line)
        if m:
            try:
                cmds.append(shlex.split(m.group(1)))
            except ValueError:
                cmds.append(m.group(1).replace("'", "").split())
    return cmds or None


BRANCH_READ = {"--list", "-l", "--contains", "--merged", "--no-merged", "--points-at", "--show-current"}
BRANCH_VALUE = {"--format", "--sort"}  # options whose separate argument is a value, not a branch name (neither forces list mode)
BRANCH_WRITE = {"-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy", "-f", "--force", "-u", "--set-upstream-to",
                "--unset-upstream", "--edit-description", "-t", "--track"}
# Read-only git (design D2): everything else, including subcommands this table does not know, is a change.
READ_ALWAYS = {"status", "log", "show", "diff", "diff-tree", "diff-index", "diff-files", "rev-parse", "rev-list", "ls-tree", "ls-files",
               "ls-remote", "cat-file", "merge-base", "for-each-ref", "show-ref", "describe", "name-rev", "grep", "blame", "shortlog",
               "cherry", "check-ignore", "check-ref-format", "count-objects", "var", "version", "help",
               # children git starts itself for fetch, pull, push and ls-remote; the parent command is judged, not these
               "upload-pack", "receive-pack", "pack-objects", "index-pack", "unpack-objects", "fetch-pack"}


def branch_deletes(cmds):
    return [c for c in cmds if c[:1] == ["branch"] and {"-d", "-D", "--delete"} & set(c[1:])]


def git_read_only(c):
    """True if the traced git command `c` (argv after `git`) only reads: its subcommand and arguments are on the read-only table.
    `--opt=value` is split into `--opt value` first, so attached values match like separate ones."""
    if not c:
        return False
    sub = c[0]
    rest = [p for a in c[1:] for p in (a.split("=", 1) if a.startswith("--") and "=" in a else [a])]
    pos = [a for a in rest if not a.startswith("-")]
    if sub in READ_ALWAYS:
        return True
    if sub in ("gc", "maintenance"):
        return "--auto" in rest and (sub == "gc" or rest[:1] == ["run"])
    if sub == "fetch":  # a refspec that writes outside refs/remotes/ (`tag v1` is refs/tags/v1:refs/tags/v1), or forces with +
        refspecs = [a for a in c[1:] if not a.startswith("-")][1:]
        return not any(a.startswith("+") for a in rest) and "tag" not in refspecs and all(
            ":" not in r or r.split(":", 1)[1].startswith("refs/remotes/") for r in refspecs)
    if sub == "reflog":
        # show, list or exists, or a ref plainly named (`HEAD`, `refs/...`, `main@{1}`); any other word may be a subcommand (write, drop)
        pos = [a for i, a in enumerate(rest) if not a.startswith("-") and not (i and rest[i - 1] in ("-n", "--max-count", "--format", "--pretty", "--date"))]
        return not pos or pos[0] in ("show", "list", "exists") or pos[0] == "HEAD" or "/" in pos[0] or "@{" in pos[0]
    if sub == "branch":
        positional = [a for i, a in enumerate(rest) if not a.startswith("-") and not (i and rest[i - 1] in BRANCH_VALUE)]
        return not (BRANCH_WRITE & set(rest) or (positional and not BRANCH_READ & set(rest)))
    if sub in ("checkout", "switch"):
        return not rest
    if sub == "tag":
        return not tag_writes([c])
    if sub == "config":
        return any(a.startswith("--get") or a in ("--list", "-l") for a in rest) or pos[:1] in (["get"], ["list"])
    if sub == "remote":
        return rest[:1] in ([], ["-v"], ["--verbose"], ["get-url"], ["show"])
    if sub == "stash":
        return rest[:1] in (["list"], ["show"])
    if sub == "worktree":
        return rest[:1] == ["list"]
    if sub == "symbolic-ref":
        return len(pos) == 1 and not {"-d", "--delete"} & set(rest)
    return False


def changing_git(cmds):
    """The git commands that are not on the read-only table (`git_read_only`): commits, merges, pulls, pushes, ref and branch changes,
    `checkout`/`switch` with any argument, a fetch into a local branch, and any subcommand the table does not know."""
    return [c for c in cmds if not git_read_only(c)]


def gql_queries(a):
    """The query texts a `gh api graphql` call passes: `query=...` on its own (after -f/-F) or attached (-fquery=, --field=query=)."""
    return [m.group(1) for x in a for m in [re.match(r"(?:-[fF]|--(?:raw-)?field=)?query=(.*)", x, re.S)] if m]


GH_READ = {"pr": {"view", "list", "checks", "diff", "status"}, "issue": {"view", "list", "status"}, "repo": {"view"},
           "release": {"view", "list"}, "auth": {"status", "token"}}


API_VALUE = {"-X", "--method", "-f", "-F", "--field", "--raw-field", "--input", "-H", "--header", "-q", "--jq", "-t", "--template",
             "--hostname", "-p", "--preview", "--cache"}  # gh api options whose separate argument is a value, not the endpoint


def api_endpoint(a):
    """The endpoint of the `gh api` call `a`: its first argument after `api` that is neither an option nor an option's value."""
    return next((x for i, x in enumerate(a[1:], 1) if not x.startswith("-") and a[i - 1] not in API_VALUE), "")


def rest_read_only(a):
    """True if the `gh api` REST call `a` changes nothing: sent as GET, or a POST to GitHub's markdown render endpoint."""
    # the method comes from its own argv token: `-X GET`, `--method GET`, `-XGET`, `--method=GET`; never from inside a path
    method = None
    for i, x in enumerate(a):
        if x in ("-X", "--method") and i + 1 < len(a):
            method = a[i + 1].upper()
        elif x.startswith("--method="):
            method = x.split("=", 1)[1].upper()
        elif re.fullmatch(r"-X\w+", x):
            method = x[2:].upper()
    # fields or a body make gh send a POST unless the method is forced: --method GET sends them as a query string
    body = any(re.match(r"-[fF]|--(?:raw-)?field\b|--input\b", x) for x in a)
    if method in (None, "POST") and api_endpoint(a).lstrip("/") in ("markdown", "markdown/raw"):
        return True  # renders text and changes nothing
    return method == "GET" or (method is None and not body)


def graphql_read_only(a):
    """True if the `gh api graphql` call `a` holds only queries; a query read from a file or --input, one that does not parse, holds no
    operation, or holds a mutation or subscription among its top-level definitions is not."""
    qs = gql_queries(a)
    opaque = any(x == "--input" or x.startswith("--input=") for x in a) or any(q.startswith("@") for q in qs)
    parsed = [gqlops.operations(q) for q in qs]
    return not (opaque or any(not p or any(k != "query" for k, _ in p) for p in parsed))


def gh_read_only(a):
    """True if the traced gh call `a` (argv after `gh`) is on the read-only allowlist: `pr view|list|checks|diff|status`, `issue view|list|
    status`, `repo view`, `release view|list`, `auth status|token`, `search`, a REST `api` call sent as GET, a POST to markdown, or a
    GraphQL read. `-R/--repo` is ignored."""
    a = [x for i, x in enumerate(a) if x not in ("-R", "--repo") and not x.startswith("--repo=") and not (i and a[i - 1] in ("-R", "--repo"))]
    if not a:
        return False
    if a[0] == "search":
        return True
    if a[0] == "api":
        return graphql_read_only(a) if "graphql" in a[1:2] else rest_read_only(a)
    return a[1:2] != [] and a[1] in GH_READ.get(a[0], ())


def gh_writes(calls):
    """The gh calls (joined argv) that are not on the read-only allowlist (`gh_read_only`): every pr, issue, release, label or other
    write, a GraphQL call that is not a plain query, a REST call with a non-GET method, and any subcommand the list does not know."""
    return [" ".join(c.get("argv", [])) for c in calls if not gh_read_only(c.get("argv", []))]


changing_gh = gh_writes


def without_one(writes, pattern):
    """`writes` without the first entry matching `pattern`: the one write a correct run is expected to make; a second identical stays."""
    for i, w in enumerate(writes):
        if re.match(pattern, w):
            return writes[:i] + writes[i + 1:]
    return writes


def rest_method(argv):
    """The HTTP method of a `gh api` call: its own -X/--method token (-X PUT, --method PUT, -XPUT, --method=PUT), else None."""
    method = None
    for i, x in enumerate(argv):
        if x in ("-X", "--method") and i + 1 < len(argv):
            method = argv[i + 1].upper()
        elif x.startswith("--method="):
            method = x.split("=", 1)[1].upper()
        elif re.fullmatch(r"-X\w+", x):
            method = x[2:].upper()
    return method


def merge_puts(calls, repo_slug="acme/greeter", pr=7):
    """The merge requests (PUT repos/<slug>/pulls/<pr>/merge) among the fake gh's calls, as (method, sha) pairs from their fields."""
    out = []
    for c in calls:
        a = c.get("argv", [])
        if a[:1] == ["api"] and rest_method(a) == "PUT" and any(x.strip("/").endswith(f"repos/{repo_slug}/pulls/{pr}/merge") for x in a):
            j = " ".join(a)
            m, h = re.search(r"merge_method=(\w+)", j), re.search(r"\bsha=([0-9a-fA-F]+)", j)
            out.append((m.group(1) if m else None, h.group(1) if h else None))
    return out


def ref_deletes(calls, repo_slug="acme/greeter"):
    """The remote branch deletions (DELETE repos/<slug>/git/refs/heads/<branch>) among the fake gh's calls, as the branch names."""
    out = []
    for c in calls:
        a = c.get("argv", [])
        if a[:1] == ["api"] and rest_method(a) == "DELETE":
            for x in a:
                m = re.fullmatch(rf"/?repos/{re.escape(repo_slug)}/git/refs/heads/(.+)", x)
                if m:
                    out.append(m.group(1))
    return out


def check_watch_merge(name, repo, branch, branches, status, rep):
    """watch on a ready PR #7 (finish: pr, required reviewer reported, change archived on feat/add-greeting). eval-watch-agent-merge
    (pr.merge agent, squash): one merge request with squash and the ready head, PR merged, back on main holding the squash commit, the
    local branch and the remote ref deleted, next/close offered. eval-watch-merge-default-user (no pr.merge): nothing merged or
    deleted, still on the branch, the report says ready. .git/fixture-state.json has main's tip, the branch tip and the squash commit;
    gh-state.json is the fake gh's state after the run."""
    fx = json.loads((repo / ".git" / "fixture-state.json").read_text(encoding="utf-8"))
    st = json.loads((repo / "gh-state.json").read_text(encoding="utf-8"))
    gh_repo = st["repos"]["acme/greeter"]
    pull = next(p for p in gh_repo["pulls"] if p["number"] == 7)
    calls = gh_calls(repo)
    puts, dels = merge_puts(calls), ref_deletes(calls)
    R = []
    if name in ("eval-watch-agent-merge", "eval-agent-merge-release-auto"):
        R.append(("Exactly one merge request was sent, with squash and the ready head",
                  len(puts) == 1 and puts[0][0] == "squash" and bool(puts[0][1]) and fx["tip"].startswith(puts[0][1]),
                  f"merge requests={puts} ready head={fx['tip']}"))
        R.append(("PR #7 is MERGED in the fake gh", pull.get("state") == "closed" and bool(pull.get("merged_at")),
                  f"state={pull.get('state')} merged_at={pull.get('merged_at')}"))
        R.append(("The repo is on main and main holds the merge (the squash commit Add greeting (#7)), with a clean tree",
                  branch == "main" and git(repo, "rev-parse", "main") == fx["squash"] and not status,
                  f"branch={branch} main={git(repo, 'rev-parse', 'main')} squash={fx['squash']} status={status}"))
        R.append(("The local branch feat/add-greeting was deleted", "feat/add-greeting" not in branches, f"branches={branches}"))
        R.append(("The remote branch was deleted: one ref DELETE for feat/add-greeting, and the fake gh no longer has it",
                  dels == ["feat/add-greeting"] and "feat/add-greeting" not in gh_repo.get("branches", {}),
                  f"ref deletions={dels} remote branches={sorted(gh_repo.get('branches', {}))}"))
        kinds = []
        for c in calls:
            a = c.get("argv", [])
            if a[:1] == ["api"] and rest_method(a) == "PUT" and any(x.endswith("pulls/7/merge") for x in a):
                kinds.append("merge")
            elif a[:1] == ["api"] and rest_method(a) == "DELETE" and any("git/refs/heads/" in x for x in a):
                kinds.append("delete")
        R.append(("The remote branch was deleted after the merge, not before", kinds[:1] == ["merge"] and kinds.count("delete") == 1, f"order={kinds}"))
        other = [c for c in gh_writes(calls) if not re.search(r"pulls/7/merge|git/refs/heads/feat/add-greeting", c)]
        if name == "eval-agent-merge-release-auto":  # the one gh release create v0.5.0 this run expects
            other = without_one(other, rf"release create {re.escape(RELEASE_TAG)}(\s|$)")
        R.append(("No other gh call created or changed anything (no gh pr merge, auto-merge or comment)", not other, f"other changing gh calls={other}"))
        want, got = fx["expected_mode"], roadmap_offer(rep)
        R.append((f"The report offers the prescribed next step: specwright-roadmap {want}", got == {want},
                  f"expected {want}, offered {sorted(got)}, excerpt={rep[-240:]!r}"))
        if name == "eval-agent-merge-release-auto":
            R.extend(check_release_published(repo, fx["squash"], st, calls, git_trace(repo) or [], rep, "squash merge commit", after_cleanup=True))
    else:
        R.append(("No merge request and no ref DELETE reached the gh log",
                  not puts and not dels and not [c for c in calls if "pulls/7/merge" in " ".join(c.get("argv", []))],
                  f"merge requests={puts} ref deletions={dels}"))
        R.append(("Still on feat/add-greeting with main unchanged, the branch present and the tree clean",
                  branch == "feat/add-greeting" and git(repo, "rev-parse", "main") == fx["main"] and "feat/add-greeting" in branches and not status,
                  f"branch={branch} main={git(repo, 'rev-parse', 'main')} status={status}"))
        R.append(("PR #7 is still open and the remote branch is still there",
                  pull.get("state") == "open" and not pull.get("merged_at") and "feat/add-greeting" in gh_repo.get("branches", {}),
                  f"state={pull.get('state')} remote branches={sorted(gh_repo.get('branches', {}))}"))
        ch = changing_gh(calls)
        R.append(("No gh call created or changed a pull request, issue or comment", not ch, f"changing gh calls={ch}"))
        R.append(("The report says the PR is ready", bool(re.search(r"\bready\b", rep)) and not re.search(r"\bnot (yet )?ready\b", rep),
                  f"excerpt={rep[-240:]!r}"))
    R.append(("No commit was amended", not amends(repo), f"amend entries={amends(repo)}"))
    return R


def refresh_exceptions(cmds):
    """`changing_git(cmds)` without the guarded refresh the finish skill allows: exactly `checkout main` and `pull --ff-only`, plus the
    `merge --ff-only FETCH_HEAD` that pull itself runs (traced as its own command) when a `pull --ff-only` is there. `-q`/`--quiet` is
    ignored in each. Commit, any other merge, push, `pull` with other options and branch deletion stay."""
    pulled = ["pull", "--ff-only"] in [unquiet(c) for c in cmds]
    allowed = [["checkout", "main"], ["pull", "--ff-only"]] + ([["merge", "--ff-only", "FETCH_HEAD"]] if pulled else [])
    return [c for c in changing_git(cmds) if unquiet(c) not in allowed]


def unquiet(cmd):
    """A git argument list without `-q`/`--quiet`, which changes only what git prints."""
    return [a for a in cmd if a not in ("-q", "--quiet")]


def check_finish_resume_merged(name, repo, branch, branches, status, rep):
    """finish: pr resume where the change's PR #7 is merged and the local branch is gone (squash merge, or a merge commit with the
    branch already deleted; eval-finish-resume-stale-main: local main is behind origin, whose main holds the merge of PR #7): only the
    issues-left-open backstop (one closed-check read of PR #7) runs, after the guarded refresh that each of these evals requires
    (status --porcelain, then checkout main, then pull --ff-only from the fixture's local bare origin); no commit, other merge,
    push or branch command, and the report says Nothing to finish.
    .git/fixture-state.json has main's tip (for the stale-main eval, origin's tip after the pull) and the commit count."""
    fx = json.loads((repo / ".git" / "fixture-state.json").read_text(encoding="utf-8"))
    cmds = git_trace(repo)
    R = []
    if name.endswith("stale-main"):
        pulled = ["pull", "--ff-only"] in [unquiet(c) for c in cmds or []]
        R.append(("Still on main with only main, a clean tree, and main fast-forwarded to origin's tip by the pull",
                  branch == "main" and branches == ["main"] and git(repo, "rev-parse", "main") == fx["main"] and not status and pulled,
                  f"branch={branch} branches={branches} main={git(repo, 'rev-parse', 'main')} expected={fx['main']} pulled={pulled} status={status}"))
        arch = repo / "openspec" / "changes" / "archive" / "2026-10-14-add-greeting"
        R.append(("The pull brought the archive of PR #7 (2026-10-14-add-greeting) onto main", arch.is_dir(), f"exists={arch.is_dir()}"))
    else:
        R.append(("Still on main with only main, main is unchanged and the working tree is clean",
                  branch == "main" and branches == ["main"] and git(repo, "rev-parse", "main") == fx["main"] and count_all(repo) == fx["commits"] and not status,
                  f"branch={branch} branches={branches} main={git(repo, 'rev-parse', 'main')} commits={count_all(repo)} status={status}"))
    cl = cmds or []
    guard = next((i for i, c in enumerate(cl) if c[:1] == ["status"] and any(a.startswith("--porcelain") for a in c[1:])), None)
    pull = next((i for i, c in enumerate(cl) if unquiet(c) == ["pull", "--ff-only"]), None)
    # the checkout must come between the guard and the pull: off main, a pull first would update the current branch, not main
    co = next((i for i, c in enumerate(cl) if unquiet(c) == ["checkout", "main"] and guard is not None and i > guard
               and (pull is None or i < pull)), None)
    R.append(("The guarded refresh ran: git status --porcelain, then git checkout main, then git pull --ff-only (the git trace)",
              None not in (guard, co, pull), f"status at={guard} checkout main at={co} pull --ff-only at={pull} trace recorded={cmds is not None}"))
    bad = refresh_exceptions(cl)
    R.append(("No git commit, merge, push or branch-changing command ran (the git trace)",
              cmds is not None and not bad, f"trace commands={len(cmds) if cmds else 'none recorded'} changing={bad}"))
    if name.endswith(("merged-branch-gone", "stale-main")):
        R.append(("No git branch -d or -D was attempted (the git trace holds none)",
                  cmds is not None and not branch_deletes(cmds), f"deletions={branch_deletes(cmds or [])} trace recorded={cmds is not None}"))
    calls = gh_calls(repo)
    blob = lambda c: " ".join(c.get("argv", []))
    prs = [c for c in calls if "pullRequest(number" in blob(c) and "mergedAt" in blob(c) and "closingIssuesReferences" not in blob(c)]
    on7 = [c for c in prs if "number=7" in blob(c)]
    R.append(("Exactly one closed-check read of PR #7 was made (the issues-left-open backstop ran once)",
              len(prs) == 1 and len(on7) == 1, f"closed-check PR reads={len(prs)} for #7={len(on7)} gh calls={len(calls)}"))
    ch = changing_gh(calls)
    R.append(("No gh call created or changed a pull request, issue or comment", not ch, f"changing gh calls={ch}"))
    hit = re.search(r"nothing (is )?(left )?to finish\W+(the )?archive is (already )?on\b", rep)
    R.append(("The report says Nothing to finish - archive is on main", bool(hit), f"match={hit.group(0) if hit else None} excerpt={rep[-200:]!r}"))
    nf = re.search(r"no archive (was )?found|archive (was )?not found|(could|did) not find (the |an |any )?archive|found no archive", rep)
    R.append(("The report does not say the archive was not found", not nf, f"match={nf.group(0) if nf else None}"))
    R.append(("No commit was amended", not amends(repo), f"amend entries={amends(repo)}"))
    return R


# ---- release evals (add-release-workflow) -----------------------------------------------------------------------
RELEASE_TAG = "v0.5.0"
TAG_REF = f"refs/tags/{RELEASE_TAG}"
RELEASE_WORDS = r"publish\w*|releas\w*|\btag(?:s|ged|ging)?\b"
RELEASE_ASK = (r"\?|whether|confirm|let me know|please (?:tell|say|advise)|say (?:the word|so|yes|go)|"
               r"if you (?:want|would like|'d like|wish)|when you(?:'re| are)? ready|on your go")
TAG_WRITE_SHORT = set("asufdmFe")
TAG_READ = {"-l", "--list", "--contains", "--no-contains", "--merged", "--no-merged", "--points-at"}


def ref_lines(repo, *namespaces):
    """The ref names under `namespaces` in `repo` (a work tree or a bare repository)."""
    return (git(repo, "for-each-ref", "--format=%(refname)", *namespaces) or "").splitlines()


def sentence_spans(rep):
    """(offset, text) of each sentence or line of the report: split after . ? ! plus whitespace, and at line ends (a version such as
    0.5.0 does not split)."""
    out, pos = [], 0
    for m in re.finditer(r"(?<=[.?!])\s+|\n", rep):
        out.append((pos, rep[pos:m.start()]))
        pos = m.end()
    out.append((pos, rep[pos:]))
    return [(p, t) for p, t in out if t.strip()]


def near(rep, *pats):
    """One sentence, or two consecutive ones, of the report matches every regex in `pats`."""
    sp = [t for _, t in sentence_spans(rep)]
    return any(all(re.search(p, w) for p in pats) for w in sp + [a + " " + b for a, b in zip(sp, sp[1:])])


def release_pos(rep):
    """Offset of the first sentence that names 0.5.0 with a release word (publish, release, tag), or None."""
    return next((p for p, t in sentence_spans(rep) if re.search(r"0\.5\.0", t) and re.search(RELEASE_WORDS, t)), None)


def roadmap_pos(rep):
    """Offset of the first sentence that offers a roadmap mode (names the roadmap and next or close), or None."""
    return next((p for p, t in sentence_spans(rep) if "roadmap" in t and re.search(r"\b(?:next|close)\b", t)), None)


def release_offered(rep):
    """The report asks whether to publish 0.5.0: a sentence names 0.5.0 and a release word and asks, or a paragraph with both has a question."""
    ask = any(re.search(r"0\.5\.0", t) and re.search(RELEASE_WORDS, t) and re.search(RELEASE_ASK, t) for _, t in sentence_spans(rep))
    return ask or any(re.search(r"0\.5\.0", b) and re.search(RELEASE_WORDS, b) and "?" in b for b in re.split(r"\n\s*\n", rep))


def tag_writes(cmds):
    """git tag commands that create, change or delete a tag (-a, -s, -u, -f, -d, -m, -F, -e, --annotate, --sign, --force, --delete,
    or a name with no listing option); `git tag`, `-l`, `--contains` and the like only read."""
    out = []
    for c in cmds:
        if c[:1] != ["tag"]:
            continue
        rest = c[1:]
        flags = [a for a in rest if a.startswith("-")]
        write = any(a in ("--annotate", "--sign", "--force", "--delete", "--local-user", "--message", "--file", "--edit")
                    or a.startswith(("--local-user=", "--message=", "--file="))
                    or (re.fullmatch(r"-[A-Za-z]+", a) and TAG_WRITE_SHORT & set(a[1:])) for a in flags)
        positional = [a for i, a in enumerate(rest) if not a.startswith("-") and not (i and rest[i - 1] in ("-m", "-F", "-u", "--format", "--sort"))]
        if write or (positional and not TAG_READ & set(flags)):
            out.append(c)
    return out


def pushes(cmds):
    return [c for c in cmds if c[:1] == ["push"]]


def push_refspecs(c):
    """The refspecs of a git push command: the positionals after the remote name."""
    pos = [a for a in c[1:] if not a.startswith("-")]
    return pos[1:]


def force_like(argv):
    """Options or refspecs that force, mirror, delete or push every tag or branch: --force, -f, --force-with-lease, --tags, --mirror,
    --all, --delete, -d, a combined short option holding f, a leading + on a refspec."""
    bad = []
    for a in argv:
        if a in ("--force", "-f", "--tags", "--mirror", "--all", "--delete", "-d", "--prune") or a.startswith(("--force-with-lease", "+")):
            bad.append(a)
        elif re.fullmatch(r"-[A-Za-z]*f[A-Za-z]*", a):
            bad.append(a)
    return bad


def release_gh(calls, sub=None):
    """The fake gh's `release` calls (optionally only `view` or `create`)."""
    return [c for c in calls if c.get("argv", [])[:1] == ["release"] and (sub is None or c["argv"][1:2] == [sub])]


def refresh_ran(cl):
    """(ok, evidence): git status --porcelain, then git checkout main, then git pull --ff-only is in the trace, in that order."""
    guard = next((i for i, c in enumerate(cl) if c[:1] == ["status"] and any(a.startswith("--porcelain") for a in c[1:])), None)
    pull = next((i for i, c in enumerate(cl) if unquiet(c) == ["pull", "--ff-only"]), None)
    co = next((i for i, c in enumerate(cl) if unquiet(c) == ["checkout", "main"] and guard is not None and i > guard
               and (pull is None or i < pull)), None)
    return None not in (guard, co, pull), f"status at={guard} checkout main at={co} pull --ff-only at={pull}"


def other_changes(cmds):
    """The git commands that commit, merge, checkout, branch or pull beyond the guarded refresh; `git tag` and `git push` are judged apart."""
    return [c for c in refresh_exceptions(cmds) if c[:1] not in (["tag"], ["push"])]


def check_release_published(repo, commit, st, calls, cmds, rep, what, after_cleanup=False):
    """What a run with release.auto leaves: the annotated tag v0.5.0 on `commit` locally and on origin (the bare <repo>/ob.git), one gh
    release create with --verify-tag whose body is the tag's message, only the tag pushed and nothing forced, and a report that names the
    release before the roadmap offer. after_cleanup: the gh log holds the merge PUT, then the ref DELETE, then the release create, and
    the tag push follows the pull and the local branch deletion in the git trace."""
    bare = repo / "ob.git"
    R = []
    seen = {w: (git(r, "cat-file", "-t", TAG_REF), git(r, "rev-parse", f"{TAG_REF}^{{commit}}"), ref_lines(r, "refs/tags"))
            for w, r in (("locally", repo), ("on origin", bare))}
    R.append((f"An annotated tag {RELEASE_TAG} on the {what} exists locally and on origin, and it is the only tag in either",
              all(t == "tag" and c == commit and tags == [TAG_REF] for t, c, tags in seen.values()), f"expected {commit}; seen={seen}"))
    creates = release_gh(calls, "create")
    ok = len(creates) == 1 and creates[0]["argv"][2:3] == [RELEASE_TAG] and "--verify-tag" in creates[0]["argv"]
    R.append((f"Exactly one gh release create {RELEASE_TAG} was made, with --verify-tag", ok, f"release creates={[c['argv'] for c in creates]}"))
    body = ((st.get("repos", {}).get("acme/greeter", {}).get("releases") or {}).get(RELEASE_TAG) or {}).get("body")
    msg = git(repo, "for-each-ref", "--format=%(contents)", TAG_REF)
    norm = lambda t: (t or "").replace("\r\n", "\n").strip()
    R.append(("The fake gh holds the release, and its body equals the tag's message",
              bool(norm(msg)) and norm(body) == norm(msg), f"body={body!r} tag message={msg!r}"))
    heads = ref_lines(bare, "refs/heads")
    refspecs = [r for c in pushes(cmds) for r in push_refspecs(c)]
    only_tag = bool(refspecs) and all(r in (RELEASE_TAG, TAG_REF, f"{TAG_REF}:{TAG_REF}") for r in refspecs)
    R.append(("The release step pushed only the tag: every git push names only refs/tags/v0.5.0, and origin holds no other new ref",
              bool(pushes(cmds)) and only_tag and heads == ["refs/heads/main"],
              f"pushes={pushes(cmds)} refspecs={refspecs} origin heads={heads}"))
    forced = [f for c in pushes(cmds) for f in force_like(c[1:])] + [f for c in release_gh(calls) for f in force_like(c["argv"])]
    R.append(("No git push or gh release call used --force, -f, --force-with-lease, --tags, --mirror, --all or --delete, or a + refspec", not forced,
              f"forcing options={forced}"))
    rp, mp = release_pos(rep), roadmap_pos(rep)
    R.append(("The report names the release of 0.5.0, then offers the roadmap mode (next or close), the release first",
              rp is not None and mp is not None and rp < mp, f"release at={rp} roadmap offer at={mp} excerpt={rep[-300:]!r}"))
    if after_cleanup:
        kinds = []
        for c in calls:
            a = c.get("argv", [])
            if a[:1] == ["api"] and rest_method(a) == "PUT" and any(x.endswith("pulls/7/merge") for x in a):
                kinds.append("merge")
            elif a[:1] == ["api"] and rest_method(a) == "DELETE" and any("git/refs/heads/" in x for x in a):
                kinds.append("delete")
            elif a[:2] == ["release", "create"]:
                kinds.append("release")
        pull = next((i for i, c in enumerate(cmds) if unquiet(c) == ["pull", "--ff-only"]), None)
        bdel = next((i for i, c in enumerate(cmds) if c[:1] == ["branch"] and {"-d", "-D"} & set(c[1:])), None)
        push = next((i for i, c in enumerate(cmds) if c[:1] == ["push"]), None)
        R.append(("The release came after the cleanup: the gh log has the merge, the remote branch DELETE, then the release create, and the tag push "
                  "follows the pull and the local branch deletion (the git trace)",
                  kinds == ["merge", "delete", "release"] and None not in (pull, bdel, push) and push > max(pull, bdel),
                  f"gh order={kinds} pull at={pull} branch deletion at={bdel} push at={push}"))
    return R


def check_finish_release(name, repo, branch, branches, status, rep):
    """finish: pr, the change's PR #7 merged on GitHub and squashed onto origin's main (Add greeting (#7), VERSION 0.4.0 -> 0.5.0), the
    local branch gone, a roadmap, no tag anywhere. eval-finish-release-offer (release.auto false): cleanup as usual, the report offers
    publishing 0.5.0 before the roadmap offer, and nothing is tagged or pushed. eval-finish-release-auto: the tag and the GitHub release
    are published (check_release_published). eval-finish-release-disabled (release.enabled false, auto true): no release step at all.
    .git/fixture-state.json has main's tip (the squash commit)."""
    fx = json.loads((repo / ".git" / "fixture-state.json").read_text(encoding="utf-8"))
    st = json.loads((repo / "gh-state.json").read_text(encoding="utf-8"))
    cmds, calls = git_trace(repo) or [], gh_calls(repo)
    R = []
    R.append(("Still on main with only main, main unchanged and the working tree clean",
              branch == "main" and branches == ["main"] and git(repo, "rev-parse", "main") == fx["main"] and not status,
              f"branch={branch} branches={branches} main={git(repo, 'rev-parse', 'main')} expected={fx['main']} status={status}"))
    ok, ev = refresh_ran(cmds)
    R.append(("The guarded refresh ran: git status --porcelain, then git checkout main, then git pull --ff-only (the git trace)", ok, ev))
    bad = other_changes(cmds)
    R.append(("No git commit, other merge or branch-changing command ran (the git trace)", bool(cmds) and not bad, f"changing={bad}"))
    ch = gh_writes(calls)
    if name == "eval-finish-release-auto":  # the one gh release create v0.5.0 this run expects
        ch = without_one(ch, rf"release create {re.escape(RELEASE_TAG)}(\s|$)")
    R.append(("No gh call created or changed a pull request, issue or comment", not ch, f"changing gh calls={ch}"))
    if name == "eval-finish-release-auto":
        R.extend(check_release_published(repo, fx["main"], st, calls, cmds, rep, "squash merge commit"))
    else:
        tags = {"locally": ref_lines(repo, "refs/tags"), "on origin": ref_lines(repo / "ob.git", "refs/tags")}
        R.append(("No tag exists locally or on origin, and no git tag write or git push ran",
                  not any(tags.values()) and not tag_writes(cmds) and not pushes(cmds),
                  f"tags={tags} tag writes={tag_writes(cmds)} pushes={pushes(cmds)}"))
        rc = release_gh(calls)
        R.append(("No gh release call was made (no create, no view)", not rc, f"release calls={[c['argv'] for c in rc]}"))
    if name == "eval-finish-release-offer":
        R.append(("The report offers to publish 0.5.0 (asks, naming the version and publish, release or tag)", release_offered(rep), f"excerpt={rep[-300:]!r}"))
        rp, mp = release_pos(rep), roadmap_pos(rep)
        R.append(("The release offer comes before the roadmap offer (specwright-roadmap next or close)",
                  rp is not None and mp is not None and rp < mp, f"release at={rp} roadmap offer at={mp}"))
    if name == "eval-finish-release-disabled":
        hit = re.search(r"\bpublish\w*|\buntagged\b|specwright-release|release\.sh|\bv?0\.5\.0\b|\breleases?\b|\btag(?:s|ged|ging)?\b", rep)
        R.append(("The report has no release step: no publish, untagged, release, tag or 0.5.0", not hit,
                  f"match={hit.group(0) if hit else None} excerpt={rep[-300:]!r}"))
        R.append(("The report offers the roadmap mode (next or close): finish went on as usual", roadmap_pos(rep) is not None, f"excerpt={rep[-200:]!r}"))
        extra = [c for c in cmds if c[:1] in (["tag"], ["ls-remote"])]
        R.append(("No git tag or ls-remote command ran (the git trace)", not extra, f"commands={extra}"))
    R.append(("No commit was amended", not amends(repo), f"amend entries={amends(repo)}"))
    return R


def check_finish_local_release(repo, branch, branches, status, rep, run):
    """finish: local with release.auto, the change's branch bumped VERSION to 0.5.0: the local merge is done as eval-finish-local does it, but
    no tag is made and nothing is pushed (origin, a bare repo behind the github.com URL, keeps its main and has no tag; no push, no gh
    release call), and the report says v0.5.0 can be published after main is pushed. .git/fixture-state.json has origin's main."""
    fx = json.loads((repo / ".git" / "fixture-state.json").read_text(encoding="utf-8"))
    cmds, calls = git_trace(repo) or [], gh_calls(repo)
    bare = repo / "ob.git"
    R = []
    allsubs = subjects(repo, "--all")
    R.append(("Archive commit on the branch: feat(add-greeting): archive change", "feat(add-greeting): archive change" in allsubs, f"subjects={allsubs}"))
    parents = (git(repo, "log", "-1", "--format=%P", "main") or "").split()
    head = git(repo, "log", "-1", "--format=%s", "main")
    R.append(("Now on main, and main HEAD is a merge commit with two parents and subject merge: add-greeting",
              branch == "main" and len(parents) == 2 and head == "merge: add-greeting", f"branch={branch} parents={len(parents)} subject={head}"))
    R.append(("Branch feat/add-greeting was deleted and the working tree is clean",
              "feat/add-greeting" not in branches and not status, f"branches={branches} status={status}"))
    version = (git(repo, "show", "main:VERSION") or "").strip()
    R.append(("main reads VERSION 0.5.0 after the merge", version == "0.5.0", f"VERSION={version!r}"))
    tags = ref_lines(repo, "refs/tags")
    R.append(("No tag was created", not tags and not tag_writes(cmds), f"tags={tags} tag writes={tag_writes(cmds)}"))
    heads, otags = ref_lines(bare, "refs/heads"), ref_lines(bare, "refs/tags")
    omain = git(bare, "rev-parse", "refs/heads/main")
    R.append(("Nothing was pushed: origin keeps its main and has no tag, no git push ran, and no gh release call was made",
              heads == ["refs/heads/main"] and omain == fx["main"] and not otags and not pushes(cmds) and not release_gh(calls),
              f"origin heads={heads} main={omain} expected={fx['main']} origin tags={otags} pushes={pushes(cmds)} release calls={release_gh(calls)}"))
    ch = changing_gh(calls)
    R.append(("No gh call created or changed anything", not ch, f"changing gh calls={ch}"))
    R.append(("The report says v0.5.0 can be published after main is pushed", near(rep, r"0\.5\.0", r"push", RELEASE_WORDS), f"excerpt={rep[-300:]!r}"))
    R.append(("No commit was amended", not amends(repo), f"amend entries={amends(repo)}"))
    want = {INITIAL, "chore: release settings", PLAN_SUBJECT, "feat(add-greeting): implement tasks 1.1-2.1",
            "feat(add-greeting): bump version to 0.5.0", "feat(add-greeting): archive change", "merge: add-greeting"}
    R.append(only_code_repo(repo, run, lambda subs: set(subs) == want and len(subs) == len(want)))
    return R


STARTING = r"\b(start|starts|starting|started|propos\w*|branch\w*|scaffold\w*|creat\w*|begin\w*|open\w*)\b"


def check_roadmap_milestone_end(repo, branch, branches, status, rep):
    """next at a milestone's end (all changes done, a user-verified criterion with no result): offer close, start nothing,
    not even the Next milestone's agreed changes. fixture-state.json (in .git) has main's tip and the roadmap text."""
    R = []
    fx = json.loads((repo / ".git" / "fixture-state.json").read_text(encoding="utf-8"))
    R.append(("Still on main and main is unchanged", branch == "main" and git(repo, "rev-parse", "main") == fx["main"],
              f"branch={branch} main={git(repo, 'rev-parse', 'main')}"))
    R.append(("No branch other than main exists", branches == ["main"], f"branches={branches}"))
    changes = repo / "openspec/changes"
    dirs = sorted(d.name for d in changes.iterdir() if d.is_dir() and d.name != "archive") if changes.is_dir() else []
    R.append(("No change directory exists under openspec/changes (apart from archive)", not dirs, f"dirs={dirs}"))
    R.append(("The working tree is clean", not status, f"status={status}"))
    rm = repo / "openspec/roadmap.md"
    text = rm.read_text(encoding="utf-8") if rm.exists() else None
    R.append(("The roadmap file is unchanged", text == fx["roadmap"], f"same={text == fx['roadmap']}"))
    hit = re.search(r"\bclose\b", rep)
    R.append(("The report offers to close the milestone", bool(hit), f"match={hit.group(0) if hit else None}"))
    # "After close, next will start add-farewell" describes the step after close, not a start now.
    began = [x.strip() for x in sentences(rep)
             if re.search(r"add-farewell|add-shout", x) and re.search(STARTING, x) and not re.search(NEGATION, x)
             and not re.search(r"\bafter\b|\bonce\b|\bclose[sd]?\b", x)]
    R.append(("The report does not say it is starting or proposing an M2 change", not began, f"sentences={began}"))
    R.append(("No commit was amended", not amends(repo), f"amend entries={amends(repo)}"))
    return R


def section(text, heading):
    """Body of the `## ` section whose heading starts with `heading`, up to the next `## ` heading; None if absent."""
    m = re.search(rf"^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else None


def check_roadmap_close_agreed_split(repo, branch, branches, status):
    """close with an agreed Next split (M2: add-farewell, add-shout): merged as docs/close-m1; Now becomes M2 with the same
    changes in the same order and no Split agreed line; M1 is in Done with a date."""
    R = []
    merges = (git(repo, "log", "--first-parent", "--format=%s", "main") or "").splitlines()
    R.append(("main's first-parent history has merge: docs/close-m1", "merge: docs/close-m1" in merges, f"first-parent={merges}"))
    R.append(("Branch docs/close-m1 was deleted and the repo is on main",
              branch == "main" and "docs/close-m1" not in branches, f"branch={branch} branches={branches}"))
    R.append(("The working tree is clean", not status, f"status={status}"))
    rm = repo / "openspec/roadmap.md"
    text = rm.read_text(encoding="utf-8") if rm.exists() else ""
    now = re.search(r"^## Now[^\n]*", text, re.M)
    body = section(text, "Now") or ""
    R.append(("Now is M2", bool(now) and "M2" in now.group(0), f"heading={now.group(0) if now else None}"))
    names = re.findall(r"^\s*\d+\.\s+`([^`]+)`", body, re.M)
    R.append(("Now lists the same two changes in the same order: add-farewell, add-shout",
              names == ["add-farewell", "add-shout"], f"changes={names}"))
    marker = bool(re.search(r"split agreed", body, re.I))
    R.append(("Now has no Split agreed line", bool(body) and not marker, f"now has line={marker}"))
    done = section(text, "Done") or ""
    R.append(("M1 is in Done with a date", "M1" in done and bool(re.search(DATE, done)), f"done={done.strip()[:160]!r}"))
    return R


def check_store(name, repo, run):
    """Grade a store run: code, store = repo/code, repo/store; helpers: subjects, status_of, gh_calls."""
    code, store = repo / "code", repo / "store"
    branch = git(code, "branch", "--show-current")
    branches = (git(code, "branch", "--format=%(refname:short)") or "").splitlines()
    rep = report(run).replace("\\", "/")
    R = []  # (text, passed, evidence)

    if name == "eval-store-apply":
        on = lambda r: git(r, "branch", "--show-current")
        R.append(("Both repos are still on feat/add-greeting and both mains are unchanged",
                  on(code) == on(store) == "feat/add-greeting" and subjects(code, "main") == [INITIAL] and subjects(store, "main") == STORE_MAIN,
                  f"code={on(code)} store={on(store)} code main={subjects(code, 'main')} store main={subjects(store, 'main')}"))
        plan = find_commit(store, PLAN_SUBJECT, "main..HEAD")
        pf = files_of(store, plan) if plan else []
        R.append(("The store has a planning-artifacts commit feat(add-greeting): add planning artifacts touching only openspec/changes/add-greeting/ paths",
                  bool(pf) and all(f.startswith(CHANGE + "/") for f in pf), f"commit={plan} files={pf}"))
        csubs, ssubs = subjects(code, "main..HEAD"), subjects(store, "main..HEAD")
        bad = [f for f in history_paths(code) if "openspec/changes" in f]
        R.append(("The code repo has no planning commit and no openspec/changes path in its history",
                  PLAN_SUBJECT not in subjects(code, "--all") and not bad, f"code subjects={csubs} planning paths={bad[:5]}"))
        per = {t: ([s for s in csubs if s.startswith(f"feat(add-greeting): task {t} ")],
                   [s for s in ssubs if s.startswith(f"feat(add-greeting): task {t} ")]) for t in TASKS}
        R.append(("Exactly one code commit and one store commit per task, with identical subjects starting feat(add-greeting): task 1.1 / 1.2 / 2.1",
                  all(len(c) == 1 and c == st for c, st in per.values()), f"per-task (code, store)={per}"))
        ev, ok = {}, True
        for t in TASKS:
            h = find_commit(store, (per[t][1] or [""])[0], "main..HEAD")
            files = files_of(store, h) if h else []
            ticked = [l for l in (git(store, "show", "--format=", h) or "").splitlines() if l.startswith("+- [x]")] if h else []
            ok = ok and files == [f"{CHANGE}/tasks.md"] and len(ticked) == 1 and ticked[0].startswith(f"+- [x] {t} ")
            ev[t] = (files, ticked)
        R.append(("Each store task commit touches only tasks.md and its diff ticks only its own task", ok, f"{ev}"))
        long_ = [s for s in csubs + ssubs if len(s) > 72]
        R.append(("Every commit subject in both repos is 72 characters or fewer", bool(csubs) and bool(ssubs) and not long_, f"too long={long_}"))
        tasks = store / CHANGE / "tasks.md"
        if not tasks.exists():
            arch = list(store.glob("openspec/changes/archive/*add-greeting/tasks.md"))
            tasks = arch[0] if arch else tasks
        t = tasks.read_text(encoding="utf-8") if tasks.exists() else ""
        R.append(("All tasks in the store's tasks.md are ticked", bool(t) and "- [ ]" not in t and t.count("- [x]") == 3,
                  f"unticked={t.count('- [ ]')} ticked={t.count('- [x]')}"))
        tr = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=code, capture_output=True, text=True)
        R.append(("The test suite passes in the code repo", tr.returncode == 0, (tr.stderr or tr.stdout).strip().splitlines()[-1:] or ["no output"]))
        R.append(("Both working trees are clean, the code repo apart from scratch-notes.txt",
                  status_of(code) == ["?? scratch-notes.txt"] and not status_of(store), f"code={status_of(code)} store={status_of(store)}"))
        ever = git(code, "log", "--all", "--format=%h", "--", "scratch-notes.txt") or ""
        R.append(("scratch-notes.txt was never committed", not ever, f"commits touching it={ever!r}"))
        hit = re.search(r"no-op\?|was [^.\n]*a no-op|did [^.\n]* change (any )?code|whether [^.\n]*no-op", rep)
        R.append(("The report does not ask whether any task was a no-op", bool(rep) and not hit, f"match={hit.group(0) if hit else None}"))
        per_repo = bool(re.search(r"tree clean|task commits", rep)) and "code" in rep and "store" in rep
        R.append(("The report gives per-repo completion for the code repo and the store", per_repo, f"report excerpt={rep[-200:]!r}"))
        by = completion_by_repo(rep)
        R.append(("The report's completion check gives the task commits and a clean tree separately for the code repo and the store",
                  all(by[r] == {"commits", "clean"} for r in by), f"by repo={by}"))
        am = amends(code) + amends(store)
        R.append(("No commit was amended in either repo", not am, f"amend entries={am}"))

    elif name == "eval-store-apply-wrong-branch":
        st = status_of(store)
        on_store = git(store, "branch", "--show-current")
        ok, ev = untouched(code, store, 1, 2, (INITIAL, STORE_MAIN[0]))
        R.append(("No new commit in either repo: the code repo and the store are at their fixture tips", ok, ev))
        sbranches = (git(store, "branch", "--format=%(refname:short)") or "").splitlines()
        R.append(("The store is still on main, the code repo on feat/add-greeting, and no branch was created in either",
                  on_store == "main" and branch == FEAT and sorted(branches) == [FEAT, "main"] and sbranches == ["main"],
                  f"store={on_store} {sbranches} code={branch} {branches}"))
        R.append(("The planning artifacts are still uncommitted in the store and the code repo is clean",
                  bool(st) and all(l.startswith(f"?? {CHANGE}/") for l in st) and not status_of(code), f"store={st} code={status_of(code)}"))
        hit = re.search(r"store[^.\n]{0,100}\bmain\b|\bmain\b[^.\n]{0,100}store", rep)
        R.append(("The report names the store's current branch main and the change branch feat/add-greeting", bool(hit) and FEAT in rep,
                  f"match={hit.group(0) if hit else None}"))
        stopped = re.search(r"stop|halt|abort|refus|did not|didn't|not proceed|not continu|won't|cannot|can't|without|no commit|nothing", rep)
        R.append(("The report says it stopped without committing", bool(stopped), f"match={stopped.group(0) if stopped else None}"))

    elif name == "eval-store-apply-reconcile":
        csubs, ssubs = subjects(code, "main..HEAD"), subjects(store, "main..HEAD")
        R.append(("Both repos are still on feat/add-greeting and both mains are unchanged",
                  git(code, "branch", "--show-current") == git(store, "branch", "--show-current") == FEAT
                  and subjects(code, "main") == [INITIAL] and subjects(store, "main") == STORE_MAIN,
                  f"code main={subjects(code, 'main')} store main={subjects(store, 'main')}"))
        pair = {t: ([s for s in csubs if s.startswith(f"feat(add-greeting): task {t} ")],
                    [s for s in ssubs if s.startswith(f"feat(add-greeting): task {t} ")]) for t in TASKS}
        R.append(("Exactly one code commit and one store commit per task, with identical subjects, and task 1.1 keeps its original subject",
                  all(len(c) == 1 and c == st for c, st in pair.values()) and pair["1.1"][1] == [SUBJ["1.1"]], f"per-task (code, store)={pair}"))
        ok, ev = True, {}
        for t in TASKS:
            hh = find_commit(store, (pair[t][1] or [""])[0], "main..HEAD")
            ev[t] = (files_of(store, hh), diff_ticks(store, "show", "--format=", hh)) if hh else None
            ok = ok and ev[t] == ([f"{CHANGE}/tasks.md"], [t])
        R.append(("Each store task commit touches only tasks.md and its diff ticks only its own task, including the reconcile commit for 1.1", ok, f"{ev}"))
        i11 = ssubs.index(SUBJ["1.1"]) if SUBJ["1.1"] in ssubs else -1
        later = [i for i, x in enumerate(ssubs) if x.startswith(("feat(add-greeting): task 1.2 ", "feat(add-greeting): task 2.1 "))]
        R.append(("The store's task 1.1 commit comes before any task 1.2 or 2.1 commit in the store",
                  i11 >= 0 and len(later) == 2 and all(i11 > i for i in later), f"store log (newest first)={ssubs}"))
        long_ = [x for x in csubs + ssubs if len(x) > 72]
        R.append(("Every commit subject in both repos is 72 characters or fewer", bool(csubs) and bool(ssubs) and not long_, f"too long={long_}"))
        R.append(("All tasks in the store's tasks.md are ticked", sorted(ticked_tasks(store)) == list(TASKS), f"ticked={ticked_tasks(store)}"))
        tr = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=code, capture_output=True, text=True)
        R.append(("The test suite passes in the code repo", tr.returncode == 0, (tr.stderr or tr.stdout).strip().splitlines()[-1:] or ["no output"]))
        R.append(("Both working trees are clean", not status_of(code) and not status_of(store), f"code={status_of(code)} store={status_of(store)}"))
        hit = re.search(NOOP_ASK, rep)
        R.append(("The report does not ask whether any task was a no-op", bool(rep) and not hit, f"match={hit.group(0) if hit else None}"))
        by = completion_by_repo(rep)
        R.append(("The report's completion check gives the task commits and a clean tree separately for the code repo and the store",
                  all(by[r] == {"commits", "clean"} for r in by), f"by repo={by}"))
        am = amends(code) + amends(store)
        R.append(("No commit was amended in either repo", not am, f"amend entries={am}"))

    elif name == "eval-store-apply-multi-gap":
        ok, ev = untouched(code, store, 3, 3, (SUBJ["1.2"], PLAN_SUBJECT))
        R.append(("No new commit in either repo", ok, ev))
        R.append(("The store's tasks.md still has both ticks uncommitted and nothing else changed, and the code repo is clean",
                  status_of(store) == [f" M {CHANGE}/tasks.md"] and diff_ticks(store, "diff") == ["1.1", "1.2"]
                  and sorted(ticked_tasks(store)) == ["1.1", "1.2"] and not status_of(code),
                  f"store={status_of(store)} diff ticks={diff_ticks(store, 'diff')} code={status_of(code)}"))
        R.append(("The report lists tasks 1.1 and 1.2 as ticked without a store commit",
                  "1.1" in rep and "1.2" in rep and "store" in rep, f"report excerpt={rep[-200:]!r}"))
        hit = re.search(r"\?|how (do|would|should|to|you)|which|let me know|please (tell|say|advise|confirm)", rep)
        R.append(("The report asks the user how to record them", bool(hit), f"match={hit.group(0) if hit else None}"))
        am = amends(code) + amends(store)
        R.append(("No commit was amended in either repo", not am, f"amend entries={am}"))

    elif name in ("eval-store-apply-orphan-tick", "eval-store-apply-noop-gap"):
        orphan = name.endswith("orphan-tick")
        t = "1.2" if orphan else "2.1"
        heads = (SUBJ["1.1"], SUBJ["1.1"]) if orphan else (SUBJ["1.2"], SUBJ["1.2"])
        ok, ev = untouched(code, store, 2 if orphan else 3, 4 if orphan else 5, heads)
        R.append(("No new commit in either repo", ok, ev))
        R.append((f"Task {t} is the only uncommitted tick in the store and nothing further is ticked",
                  status_of(store) == [f" M {CHANGE}/tasks.md"] and diff_ticks(store, "diff") == [t] and sorted(ticked_tasks(store)) == (["1.1", t] if orphan else ["1.1", "1.2", t]),
                  f"store={status_of(store)} diff ticks={diff_ticks(store, 'diff')} ticked={ticked_tasks(store)}"))
        R.append(("The code repo is exactly as the fixture left it: " + ("task 1.2's code changes are still uncommitted" if orphan else "clean"),
                  status_of(code) == ([" M greet.py", " M test_greet.py"] if orphan else []), f"code={status_of(code)}"))
        R.append((f"The report names task {t} and asks whether it changed code",
                  t in rep and asks_about(rep, r"no-op|changed (any )?code|change (any )?code|no code|code (change|commit)"),
                  f"report excerpt={rep[-240:]!r}"))
        am = amends(code) + amends(store)
        R.append(("No commit was amended in either repo", not am, f"amend entries={am}"))

    elif name == "eval-store-complete-gap":
        # Spec: "reconciles it as above, or reports the gap, and does not hand off". Either path passes (OR logic below).
        ssubs, csubs = subjects(store, "main..HEAD"), subjects(code, "main..HEAD")
        h = find_commit(store, SUBJ["2.1"], "main..HEAD")
        reconciled = bool(h) and files_of(store, h) == [f"{CHANGE}/tasks.md"] and diff_ticks(store, "show", "--format=", h) == ["2.1"]
        gap = "2.1" in rep and bool(re.search(r"uncommitted|not committed|no store commit|missing|gap|unrecorded|not recorded", rep))
        stop = bool(re.search(r"not (yet )?(hand|ready|complete|done)|no hand|did not hand|won't hand|will not hand|before (archiv|hand|open|pr)|until|hold|block|not proceed|stop", rep))
        claims = bool(re.search(r"ready (for|to) (archive|pr\b|pull)|proceed(ing)? to (archive|pr\b)|hand(ing)? off to (archive|pr\b)", rep)) and not stop
        R.append(("Both repos are still on feat/add-greeting and both mains are unchanged",
                  git(code, "branch", "--show-current") == git(store, "branch", "--show-current") == FEAT
                  and subjects(code, "main") == [INITIAL] and subjects(store, "main") == STORE_MAIN,
                  f"code main={subjects(code, 'main')} store main={subjects(store, 'main')}"))
        R.append(("The store has a commit for task 2.1 that touches only tasks.md and ticks only 2.1, or no commit was made and the report names the gap",
                  reconciled or (not h and count_all(store) == 5 and gap), f"reconciled={reconciled} commit={h} gap named={gap}"))
        pair = {t: ([x for x in csubs if x.startswith(f"feat(add-greeting): task {t} ")], [x for x in ssubs if x.startswith(f"feat(add-greeting): task {t} ")]) for t in TASKS}
        R.append(("Tasks 1.1 and 1.2 keep exactly one code and one store commit, and task 2.1 has one code commit and at most one store commit",
                  all(len(pair[t][0]) == 1 and pair[t][0] == pair[t][1] for t in ("1.1", "1.2"))
                  and len(pair["2.1"][0]) == 1 and pair["2.1"][1] in ([], pair["2.1"][0]) and len(csubs) == 3 and len(ssubs) in (3, 4),
                  f"per-task (code, store)={pair}"))
        st, cs = status_of(store), status_of(code)
        R.append(("Either both trees are clean, or only the store's tasks.md tick of 2.1 is uncommitted",
                  (not st and not cs) or (not reconciled and st == [f" M {CHANGE}/tasks.md"] and diff_ticks(store, "diff") == ["2.1"] and not cs),
                  f"store={st} code={cs}"))
        by = completion_by_repo(rep)
        R.append(("If reconciled, the report gives the task commits and a clean tree separately for the code repo and the store; if not, it states a stop and does not hand off",
                  all(by[r] == {"commits", "clean"} for r in by) if reconciled else (gap and stop and not claims),
                  f"reconciled={reconciled} by repo={by} gap={gap} stop={stop} claims handoff={claims}"))
        tr = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=code, capture_output=True, text=True)
        R.append(("The test suite passes in the code repo", tr.returncode == 0, (tr.stderr or tr.stdout).strip().splitlines()[-1:] or ["no output"]))
        hit = re.search(NOOP_ASK, rep)
        R.append(("The report does not ask whether any task was a no-op", bool(rep) and not hit, f"match={hit.group(0) if hit else None}"))
        am = amends(code) + amends(store)
        R.append(("No commit was amended in either repo", not am, f"amend entries={am}"))

    elif name == "eval-store-unregistered":
        R.append(("Still on main with no new branch or commit in the code repo",
                  branch == "main" and branches == ["main"] and main_unchanged(code), f"branch={branch} branches={branches} main={subjects(code, 'main')}"))
        d = code / "openspec/changes"
        R.append(("The code repo has no new files and no openspec/changes directory",
                  not status_of(code) and not d.exists(), f"status={status_of(code)} changes dir exists={d.exists()}"))
        R.append(("No store directory was created next to the code repo", not store.exists(), f"exists={store.exists()}"))
        hit = re.search(r"declared in|team-plans", rep)
        R.append(("The report quotes OpenSpec's error about the declared store team-plans", bool(hit), f"match={hit.group(0) if hit else None}"))
        hit = re.search(r"store register|store setup|register", rep)
        R.append(("The report gives OpenSpec's fix: register the store", bool(hit), f"match={hit.group(0) if hit else None}"))

    elif name == "eval-store-other-worktree":
        main_tip = git(code, "rev-parse", "main")
        R.append(("No new commit on any branch: main, feat/add-greeting and plans are at their fixture tips",
                  subjects(code, "main") == [INITIAL] and git(code, "rev-parse", "feat/add-greeting") == main_tip and subjects(code, "plans") == STORE_MAIN,
                  f"main={subjects(code, 'main')} feat tip={git(code, 'rev-parse', 'feat/add-greeting')} main tip={main_tip} plans={subjects(code, 'plans')}"))
        st = status_of(store)
        tasks = store / CHANGE / "tasks.md"
        R.append(("The planning artifacts are still uncommitted in the worktree",
                  bool(st) and all(l.startswith(f"?? {CHANGE}/") for l in st) and tasks.exists() and "- [x]" not in tasks.read_text(encoding="utf-8"),
                  f"status={st}"))
        R.append(("The code checkout is unchanged", branch == "feat/add-greeting" and not status_of(code), f"branch={branch} status={status_of(code)}"))
        paths = "repo/code" in rep and "repo/store" in rep
        names = "worktree" in rep and "feat/add-greeting" in rep and "plans" in rep
        stopped = re.search(r"stop|halt|abort|refus|did not|didn't|not proceed|not continu|won't|cannot|can't", rep)
        R.append(("The report names both worktrees and says it stopped", bool(rep) and (paths or names) and bool(stopped),
                  f"paths={paths} names={names} stopped={stopped.group(0) if stopped else None}"))

    elif name == "eval-nested-root-finish":
        arch = find_commit(code, "feat(add-greeting): archive change")
        af = files_of(code, arch) if arch else []
        spec = "planning/openspec/specs/greeting/spec.md"
        R.append(("The archive commit feat(add-greeting): archive change stages only planning/openspec/changes/ paths and planning/openspec/specs/greeting/spec.md",
                  bool(af) and all(f.startswith("planning/openspec/changes/") or f == spec for f in af)
                  and any(f.startswith("planning/openspec/changes/archive/") for f in af) and spec in af,
                  f"commit={arch} files={af}"))
        R.append(("Now on main", branch == "main", f"branch={branch}"))
        parents = (git(code, "log", "-1", "--format=%P", "main") or "").split()
        head = (subjects(code, "-1") or [None])[0]
        R.append(("main HEAD is a merge commit with two parents and subject merge: add-greeting",
                  len(parents) == 2 and head == "merge: add-greeting", f"parents={len(parents)} subject={head}"))
        R.append(("Branch feat/add-greeting was deleted", "feat/add-greeting" not in branches, f"branches={branches}"))
        R.append(("Working tree is clean", not status_of(code), f"status={status_of(code)}"))
        R.append(("Only the code repo's main branch remains and no gh call was made",
                  branches == ["main"] and not gh_calls(repo), f"branches={branches} gh calls={len(gh_calls(repo))}"))
        R.append(("No commit was amended", not amends(code), f"amend entries={amends(code)}"))

    elif name == "eval-root-outside-git":
        R.append(("No commit was added in the code repo and its tree is clean",
                  main_unchanged(code) and git(code, "rev-parse", "feat/add-greeting") == git(code, "rev-parse", "main") and not status_of(code),
                  f"main={subjects(code, 'main')} status={status_of(code)}"))
        R.append(("The store directory is still not a git repository", store.is_dir() and not (store / ".git").exists(),
                  f".git exists={(store / '.git').exists()}"))
        ask = re.search(r"git init|initiali[sz]e", rep) and re.search(r"abort", rep)
        R.append(("The report asks whether to initialise git there or abort", bool(ask), f"report excerpt={rep[-200:]!r}"))

    elif name.startswith("eval-install-"):
        R.extend(check_install(name, repo, code, store, rep))
    elif name.startswith("eval-references-"):
        R.extend(check_references(name, repo, code, rep))
    elif name.startswith("eval-store-branch-"):
        R.extend(check_store_branch(name, code, store, rep))
    elif name.startswith("eval-branch-store-"):
        R.extend(check_branch_store(name, code, store, rep))
    elif name.startswith(("eval-store-finish-", "eval-store-archive-on-main")):
        R.extend(check_store_finish(name, repo, code, store, rep))
    elif name in ("eval-store-ship-push-rejected", "eval-store-ship-code-push-rejected",
                  "eval-store-ship-code-push-rejected-store-pr-open", "eval-store-archive-before-merge-local-store"):
        R.extend(check_store_pr(name, repo, code, store, rep))
    elif name == "eval-store-roadmap-close-locked":
        R.extend(check_store_roadmap_locked(repo, code, store, rep))
    elif name == "eval-store-roadmap-close-hook-fail":
        R.extend(check_store_roadmap_hook_fail(repo, code, store, rep))
    elif name.startswith("eval-store-roadmap-"):
        R.extend(check_store_roadmap(name, repo, code, store, rep))
    return R


SRC = Path(__file__).resolve().parents[2]  # the Specwright checkout the install copies from
NEGATION = r"\bnot\b|n't|\bno\b|\bnever\b|without|until|before|unless|\bif\b|whether|would|should|\bcan\b|\bmay\b|\bor\b|keep|kept|left|unchanged|decline|\?"


def tree(d):
    """{relative path: bytes with LF endings} of every file under d; {} if d is missing."""
    d = Path(d)
    return {f.relative_to(d).as_posix(): f.read_bytes().replace(b"\r\n", b"\n") for f in sorted(d.rglob("*")) if f.is_file()} if d.is_dir() else {}


def openspec_in(cwd, *args, xdg=None):
    """Run the openspec CLI in cwd with throwaway (or the run's own) XDG dirs; returns (returncode, stdout+stderr)."""
    exe = shutil.which("openspec")
    if not exe:
        return None, "openspec not on PATH"
    with tempfile.TemporaryDirectory() as tmp:
        d, c = xdg or (tmp, tmp)
        env = {**os.environ, "XDG_DATA_HOME": str(Path(d).resolve()), "XDG_CONFIG_HOME": str(Path(c).resolve()), "OPENSPEC_TELEMETRY": "0"}
        r = subprocess.run([exe, *args], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout + r.stderr).strip()


def check_stale_tag(repo, code, store, rep):
    """eval-install-latest-tag-predates-script: the Specwright source repo (<run>/specwright-src) has only the tag v0.5.0, so the
    install stops before staging, names the tag and the minimum release 0.6.0 and offers main. The shared install checks
    cover the project; these cover the staging, the source and the report."""
    R = []
    staged = [p.relative_to(r).as_posix() for r in (code, store) if r.is_dir() for p in r.rglob(".specwright-update-*")]
    R.append(("No staging directory (.specwright-update-*) exists in either repo", not staged, f"staging={staged}"))
    src = repo / "specwright-src"
    tags = (git(src, "tag", "--list") or "").split()
    R.append(("The Specwright source repo is unchanged: its only tag is still v0.5.0 and its tree is clean",
              tags == ["v0.5.0"] and not status_of(src), f"tags={tags} status={status_of(src)}"))
    named = [x for x in ("v0.5.0", "0.6.0") if x not in rep]
    R.append(("The report names the latest tag v0.5.0 and the minimum release 0.6.0", bool(rep) and not named, f"missing={named}"))
    offer = [x for x in sentences(rep) if re.search(r"\bmain\b", x)
             and re.search(r"\?|offer|would you|do you want|shall i|want me|let me know|if you (want|like|prefer)|say the word", x)]
    R.append(("The report offers to install main", bool(offer), f"matching sentences={offer[:2]}"))
    return R


def check_install(name, repo, code, store, rep):
    """Install evals: the README install prompt runs in a code repo whose planning root is a registered store
    (the store repo's top level, or planning/ inside it). Schema and config.yaml belong under <root.path>/openspec/;
    specwright.yaml, skills and agents in the code repo; nothing is committed; the report lists the store's uncommitted files."""
    R = []
    nested = name == "eval-install-nested-store"
    other = name == "eval-install-store-other-schema"
    stale_tag = name == "eval-install-latest-tag-predates-script"  # the highest release tag is v0.5.0, below the minimum release 0.6.0
    refused = name == "eval-install-openspec-mismatch" or stale_tag  # the fake openspec reports 1.15.0 against the 1.14.1 pin
    root = store / "planning" if nested else store
    rel = "planning/openspec/" if nested else "openspec/"
    cfg_p = root / "openspec" / "config.yaml"
    cfg = cfg_p.read_text(encoding="utf-8").replace("\r\n", "\n") if cfg_p.exists() else ""
    tpl = (SRC / "templates/openspec/config.yaml").read_text(encoding="utf-8").replace("\r\n", "\n")
    ctx = [l.strip() for l in tpl.split("context: |\n", 1)[1].splitlines() if l.strip()]
    cfg_lines = [l.strip() for l in cfg.splitlines()]
    cfg_lines_nc = [l for l in cfg_lines if not l.startswith("#")]
    where = "planning" if nested else "store"
    place = "planning/" if nested else "the store"

    if refused:
        written = [p for p in ("openspec/specwright.yaml", ".claude/skills", ".claude/agents", ".agents/skills", ".omp/agents")
                   if (code / p).exists()] + [f"store/{p}" for p in ("openspec/schemas/specwright",) if (store / p).exists()]
        R.append(("No skill, agent, schema or specwright.yaml was written in either repo, and both trees are unchanged",
                  not written and not status_of(code) and not status_of(store),
                  f"written={written} code status={status_of(code)} store status={status_of(store)}"))
        stamp = code / "openspec/.specwright/VERSION"
        R.append(("openspec/.specwright/VERSION is absent", not stamp.exists(), f"exists={stamp.exists()}"))
        if stale_tag:
            R.extend(check_stale_tag(repo, code, store, rep))
        else:
            named = [x for x in ("1.15.0", "1.14.1", "npm i -g @fission-ai/openspec@1.14.1") if x not in rep]
            R.append(("The report names 1.15.0, 1.14.1 and npm i -g @fission-ai/openspec@1.14.1", bool(rep) and not named, f"missing={named}"))
        claims = [x for x in sentences(rep)
                  if re.search(r"install(ation)? (is |was )?(complete|done|finished|successful)|successfully installed|specwright (is )?installed", x)
                  and not re.search(NEGATION, x)]
        R.append(("The report does not say the install completed", bool(rep) and not claims, f"claims={claims[:2]}"))
    elif not other:
        R.append((f"{rel}schemas/specwright/ in the store is identical to the downloaded schemas/specwright/",
                  bool(tree(SRC / "schemas/specwright")) and tree(root / "openspec/schemas/specwright") == tree(SRC / "schemas/specwright"),
                  f"files in store={sorted(tree(root / 'openspec/schemas/specwright'))}"))
        missing = [l for l in ctx if cfg_lines_nc.count(l) != 1]
        R.append((f"The store's {rel}config.yaml has schema: specwright and every Specwright context line exactly once",
                  "schema: specwright" in cfg_lines_nc and not missing and "schema: spec-driven" not in cfg_lines_nc,
                  f"schema lines={[l for l in cfg_lines_nc if l.startswith('schema:')]} context lines not exactly once={[l[:40] for l in missing]}"))
        if nested:
            R.append(("The store repo's top level has no openspec directory", not (store / "openspec").exists(),
                      f"store/openspec exists={(store / 'openspec').exists()} entries={sorted(x.name for x in store.iterdir() if x.name != '.git')}"))
        tp = (SRC / "templates/openspec/specwright.yaml").read_text(encoding="utf-8")
        keys = re.findall(r"^([A-Za-z_]+):", tp, re.M)
        sw = code / "openspec/specwright.yaml"
        have = set(re.findall(r"^([A-Za-z_]+):", sw.read_text(encoding="utf-8"), re.M)) if sw.exists() else set()
        skills = sorted(d.name for d in (SRC / "skills").glob("specwright-*") if d.is_dir())
        agents = sorted(f.name for f in (SRC / "agents/claude").glob("*.md"))
        sk_dir, ag_dir = code / ".claude/skills", code / ".claude/agents"
        bad_skills = [n for n in skills if tree(sk_dir / n) != tree(SRC / "skills" / n)]
        extra = sorted(x.name for x in sk_dir.iterdir()) if sk_dir.is_dir() else []
        miss_agents = [a for a in agents if not (ag_dir / a).is_file()]
        R.append(("The code repo has openspec/specwright.yaml with every key of the template, every specwright-* skill in .claude/skills/ and both agents in .claude/agents/",
                  sw.exists() and not (set(keys) - have) and not bad_skills and set(extra) <= set(skills) and not miss_agents,
                  f"missing keys={sorted(set(keys) - have)} skills differing/missing={bad_skills} other entries={sorted(set(extra) - set(skills))} agents missing={miss_agents}"))
        st = status_of(store)
        R.append((f"Every new or changed file in the store is under {rel}", bool(st) and all(l[3:].startswith(rel) for l in st), f"status={st}"))
    else:
        R.append(("The store's openspec/config.yaml still names schema: team-flow and keeps the team's own context line",
                  "schema: team-flow" in cfg_lines_nc and "schema: specwright" not in cfg_lines_nc
                  and "Team convention: write every spec in British English." in cfg_lines,
                  f"config={cfg!r}"))
        tf = tree(root / "openspec/schemas/team-flow")
        st = status_of(store)
        R.append(("The store's team-flow schema is untouched and nothing in the store outside openspec/ changed",
                  sorted(tf) == ["schema.yaml", "templates/proposal.md", "templates/tasks.md"]
                  and not [l for l in st if "schemas/team-flow" in l] and all(l[3:].startswith("openspec/") for l in st),
                  f"team-flow files={sorted(tf)} status={st}"))

    # the same in every install eval
    gone = [p for p in ("specs", "changes", "schemas") if (code / "openspec" / p).exists()]
    R.append(("The code repo has no openspec/specs, openspec/changes or openspec/schemas directory", not gone, f"present={gone}"))
    cc = code / "openspec/config.yaml"
    ctext = cc.read_text(encoding="utf-8") if cc.exists() else ""
    R.append(("The code repo's openspec/config.yaml still points at the store (store: team-plans) and holds no Specwright context",
              "store: team-plans" in ctext and "specwright-" not in ctext and "context:" not in ctext, f"config={ctext!r}"))
    branches = [(git(r, "branch", "--format=%(refname:short)") or "").splitlines() for r in (code, store)]
    stash = [git(r, "stash", "list") or "" for r in (code, store)]
    R.append(("Nothing was committed, branched, stashed or pushed in either repo, and no gh call was made",
              subjects(code, "--all") == [INITIAL] and subjects(store, "--all") == STORE_MAIN
              and branches == [["main"], ["main"]] and not any(stash) and not gh_calls(repo),
              f"code commits={subjects(code, '--all')} store commits={subjects(store, '--all')} branches={branches} stash={stash} gh calls={len(gh_calls(repo))}"))
    if refused:
        return R
    if other:
        # the question may follow the sentence that names team-flow ("... sets schema: team-flow. Should it change?")
        allsents = sentences(rep)
        sents = [x for i, x in enumerate(allsents) if any("team-flow" in y for y in allsents[max(0, i - 2):i + 1])]
        ask = [x for x in sents if re.search(r"\?|whether|confirm|let me know|please (tell|say|advise)|your (call|choice)|decide", x)
               and re.search(r"specwright|replace|chang|switch|overwrit", x)]
        R.append(("The report asks the user whether to change the schema from team-flow to specwright", bool(ask), f"matching sentences={ask[:2]}"))
        claims = [x for x in sentences(rep)
                  if re.search(r"schema[^.\n]{0,40}specwright|specwright[^.\n]{0,40}schema|install(ation)? (is |was )?(complete|done|finished|successful)|successfully installed", x)
                  and re.search(r"\bset\b|changed|switched|replaced|updated|now (uses|names|has)|is `?specwright|complete|done|finished|successful", x)
                  and not re.search(NEGATION, x)]
        R.append(("The report does not say the schema was set to specwright or that the install completed", bool(rep) and not claims, f"claims={claims[:2]}"))
        return R

    # the registry the fixture built: the code repo's planning root is still the root
    rc, out = openspec_in(code, "list", "--json", xdg=(repo / "xdg-data", repo / "xdg-config"))
    try:
        got = Path(json.JSONDecoder().raw_decode(out[out.index("{"):])[0]["root"]["path"]).resolve()
    except (ValueError, KeyError, TypeError):
        got = None
    R.append((f"openspec list --json from the code repo still reports {place} as the root", got == root.resolve(), f"root={got} want={root.resolve()}"))
    rc, out = openspec_in(root, "schema", "validate", "specwright")
    R.append((f"openspec schema validate specwright passes when run in {place}", rc == 0, f"exit={rc} output={out[-160:]!r}"))
    listed = all(x in rep for x in ("schemas/specwright", "config.yaml", where)) and re.search(
        r"uncommitted|not (been )?committed|isn't committed|aren't committed|untracked|(did not|didn't|haven't|have not|not) commit", rep)
    R.append((f"The report lists the store's uncommitted files (schemas/specwright and config.yaml{' under planning/' if nested else ''}) and says they are not committed",
              bool(listed), f"report excerpt={rep[-240:]!r}"))
    # the README install prompt names the root `<root>`, so a report may say "in <root>" instead of naming the folder
    val = [x for x in sentences(rep) if "schema validate" in x and (where in x or "<root>" in x)
           and re.search(r"\bpass(ed|es)?\b|\bvalid\b|success|\bok\b|no errors", x) and not re.search(r"\bfail|\berror[^s]|not valid|invalid", x)]
    R.append((f"The report says openspec schema validate specwright was run in {place} and passed", bool(val), f"matching sentences={val[:2]}"))
    if name == "eval-install-openspec-override":
        line = "openspec 1.15.0 (pinned 1.14.1, override)"  # report() lowercases
        R.append(("The report shows OpenSpec 1.15.0 (pinned 1.14.1, override)", line in rep, f"found={line in rep}"))
    return R


REF_ID = "team-plans"
REF_MAIN = {"eval-references-apply": STORE_MAIN, "eval-references-unregistered": ["chore: initial store"]}  # the referenced store's main, as the fixture leaves it (newest first)
UNRESOLVED = r"unresolved|not registered|isn't registered|is not registered|unregistered|could not (be )?(resolve|find|read)|couldn't (resolve|find|read)|cannot be resolved|not available|missing"


def check_references(name, repo, code, rep):
    """Grade eval-references-*: the code repo keeps its own openspec/ root and lists team-plans under
    references:. Apply must land every commit in the code repo and leave <run>/repo/team-plans exactly
    as the fixture built it; when the reference is not registered the report names it and apply goes on."""
    ref = repo / REF_ID
    R = []  # (text, passed, evidence)
    want = REF_MAIN[name]
    refs = (git(ref, "for-each-ref", "--format=%(refname)") or "").splitlines()
    wts = (git(ref, "worktree", "list", "--porcelain") or "").count("worktree ")
    R.append((f"The referenced store {REF_ID} has no new commit, branch, stash or worktree and no remote",
              subjects(ref, "--all") == want and refs == ["refs/heads/main"] and git(ref, "branch", "--show-current") == "main"
              and not git(ref, "stash", "list") and not git(ref, "remote") and wts == 1,
              f"commits={subjects(ref, '--all')} refs={refs} branch={git(ref, 'branch', '--show-current')} worktrees={wts}"))
    R.append((f"The referenced store {REF_ID} has no staged, modified or untracked file",
              not status_of(ref) and (ref / "openspec/specs/audit/spec.md").is_file(), f"status={status_of(ref)}"))
    base = ["chore: declare references", INITIAL]
    csubs = subjects(code, "main..HEAD")
    R.append(("The code repo is on feat/add-greeting and main is unchanged",
              git(code, "branch", "--show-current") == FEAT and subjects(code, "main") == base,
              f"branch={git(code, 'branch', '--show-current')} main={subjects(code, 'main')}"))
    R.append(("A planning-artifacts commit exists in the code repo: feat(add-greeting): add planning artifacts",
              PLAN_SUBJECT in csubs, f"subjects={csubs}"))
    per = {t: [s for s in csubs if s.startswith(f"feat(add-greeting): task {t} ")] for t in TASKS}
    R.append(("Exactly one code commit per task, subjects start with feat(add-greeting): task 1.1 / 1.2 / 2.1, and nothing else was committed",
              all(len(v) == 1 for v in per.values()) and len(csubs) == 4, f"per-task={per} all={csubs}"))
    # no subject-length check here: eval-apply-three-tasks covers it, and this fixture's task 1.1 text trips a known
    # cut flake (issue #21) that has nothing to do with references
    R.append(("All tasks in the code repo's tasks.md are ticked", sorted(ticked_tasks(code)) == list(TASKS), f"ticked={ticked_tasks(code)}"))
    tr = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=code, capture_output=True, text=True)
    R.append(("The test suite passes in the code repo", tr.returncode == 0, (tr.stderr or tr.stdout).strip().splitlines()[-1:] or ["no output"]))
    ever = git(code, "log", "--all", "--format=%h", "--", "scratch-notes.txt") or ""
    R.append(("The code repo's working tree is clean apart from scratch-notes.txt, which was never committed",
              status_of(code) == ["?? scratch-notes.txt"] and not ever, f"status={status_of(code)} commits touching scratch-notes.txt={ever!r}"))
    am = amends(code)
    R.append(("No commit was amended", not am, f"amend entries={am}"))
    if name == "eval-references-unregistered":
        pat = rf"{REF_ID}[^.\n]{{0,160}}({UNRESOLVED})|({UNRESOLVED})[^.\n]{{0,160}}{REF_ID}"
        hit = re.search(pat, rep)
        R.append((f"The report names the unresolved reference {REF_ID} and says it is not registered",
                  bool(hit), f"match={hit.group(0) if hit else None} report excerpt={rep[-200:]!r}"))
        R.append(("The task continued: the report does not say it stopped or is waiting for the reference",
                  bool(rep) and not re.search(r"(stopp(ed|ing)|blocked|cannot continue|can't continue|unable to proceed|waiting for)[^.\n]{0,80}(reference|team-plans|register)", rep),
                  f"report excerpt={rep[-200:]!r}"))
    return R


DATE = r"\d{4}-\d\d-\d\d"
MARKER = "specwright-change.yaml"
CONFLICT_COMMIT = {"store": "docs(greeting): add greeting spec on main", "code": "feat: add formal greeting"}  # fixtures.py CONFLICT_STORE / CONFLICT_CODE


def merge_head(repo):
    """(parent count, subject) of main's tip."""
    return len((git(repo, "log", "-1", "--format=%P", "main") or "").split()), (git(repo, "log", "-1", "--format=%s", "main") or None)


def is_merge_of(repo, name):
    n, subj = merge_head(repo)
    return n == 2 and subj == f"merge: {name}"


def code_tree_kept(code, fx):
    """(passed, evidence): the code main's tree is the tree the fixture recorded for the code branch's tip. A merge commit with the
    right subject and two parents is not enough: `git merge -s ours` makes one and keeps none of the branch's code."""
    want, got = fx.get("code_tree"), git(code, "rev-parse", "main^{tree}")
    return bool(want) and got == want, f"main tree={got} code branch tip tree={want}"


def archive_dirs(store, rev):
    """Names of the directories under openspec/changes/archive/ at rev."""
    out = git(store, "ls-tree", "--name-only", rev, "openspec/changes/archive/") or ""
    return sorted(l.rsplit("/", 1)[-1] for l in out.splitlines() if l)


def archive_commit_ok(store, commit, name, archived, marker):
    """The archive commit stages exactly: the removed change directory, the archive directory (plus the
    marker when `marker`) and the main spec - by file, so nothing else (a stray user file) is in it.
    `archived` is a regex for the archive directory name. Returns (ok, evidence)."""
    if not commit:
        return False, "no archive commit"
    files = files_of(store, commit)
    orig = [f for f in (git(store, "ls-tree", "-r", "--name-only", f"{commit}^", f"openspec/changes/{name}/") or "").splitlines() if f]
    arch = [f for f in files if re.fullmatch(rf"openspec/changes/archive/{archived}/.+", f)]
    spec = "openspec/specs/greeting/spec.md"
    extra = [f for f in files if f not in orig and f not in arch and f != spec]
    has = any(f.endswith("/" + MARKER) for f in arch)
    ok = bool(orig) and set(orig) <= set(files) and len(arch) == len(orig) + (1 if marker else 0) and spec in files and not extra and has == marker
    return ok, f"commit={commit} files={files} removed originals={len(orig)} archive files={len(arch)} marker={has} extra={extra}"


def marker_text(store, commit):
    for f in files_of(store, commit):
        if f.endswith("/" + MARKER):
            return git(store, "cat-file", "-p", f"{commit}:{f}") or ""  # not `show`: git on Windows fails with "Filename too long" on long sha:path names
    return None


def conflict_left(repo, files):
    """A merge conflict handed to the user: the merge is in progress with exactly `files` unmerged, or it was
    aborted (nothing unmerged); either way no conflict markers were committed to main."""
    in_progress = git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD") is not None
    unmerged = sorted((git(repo, "diff", "--name-only", "--diff-filter=U") or "").splitlines())
    marked = [f for f in files if "<<<<<<<" in (git(repo, "cat-file", "-p", f"main:{f}") or "")]
    return (unmerged == sorted(files) if in_progress else not unmerged) and not marked, \
        f"merge in progress={in_progress} unmerged={unmerged} markers committed on main={marked}"


def pr_mutations(repo):
    """gh calls that create or change something on GitHub (anything off the read-only allowlist)."""
    return gh_writes(gh_calls(repo))


def sentences(rep):
    return re.split(r"(?<=[.?!])\s+|\n", rep)


def check_store_finish(name, repo, code, store, rep):
    """Store finish evals: the change is fully applied in both repos and the archive ran in the store, uncommitted."""
    R = []
    on = lambda r: git(r, "branch", "--show-current")
    bs = lambda r: (git(r, "branch", "--format=%(refname:short)") or "").splitlines()
    am = amends(code) + amends(store)
    no_amend = ("No commit was amended in either repo", not am, f"amend entries={am}")
    bad_code = [f for f in history_paths(code) if f.startswith(("openspec/changes", "openspec/specs"))]
    marker_paths = [f for f in history_paths(store) if f.endswith(MARKER)]
    cn = "add-greeting"
    no_planning_in_code = ("The code repo has no archive or planning path in its history and no archive commit",
                           not bad_code and not find_commit(code, f"feat({cn}): archive change"), f"planning paths={bad_code[:5]}")

    if name == "eval-store-finish-local":
        arch = find_commit(store, f"feat({cn}): archive change")
        ok, ev = archive_commit_ok(store, arch, cn, rf"{DATE}-{cn}", False)
        R.append(("The store has an archive commit feat(add-greeting): archive change that stages only the removed change directory, the archive directory and openspec/specs/greeting/spec.md", ok, ev))
        dirs = archive_dirs(store, "main")
        R.append(("The archive directory openspec/changes/archive/<date>-add-greeting/ exists on the store's main and the original change directory is gone",
                  len(dirs) == 1 and bool(re.fullmatch(rf"{DATE}-{cn}", dirs[0])) and git(store, "ls-tree", "main", f"openspec/changes/{cn}") == "",
                  f"archive dirs={dirs}"))
        R.append(no_planning_in_code)
        R.append(("The store's main HEAD is a merge commit with two parents and subject merge: add-greeting",
                  is_merge_of(store, cn), f"store main={merge_head(store)}"))
        ts = [int(git(r, "log", "-1", "--format=%ct", "main") or 0) for r in (store, code)]
        R.append(("The code repo's main HEAD is a merge commit with two parents and subject merge: add-greeting, made after the store's merge",
                  is_merge_of(code, cn) and ts[1] >= ts[0] > 0, f"code main={merge_head(code)} committer times store/code={ts}"))
        R.append(("Both repos are on main with only main left, so feat/add-greeting was deleted in each",
                  on(code) == on(store) == "main" and bs(code) == bs(store) == ["main"], f"code={on(code)} {bs(code)} store={on(store)} {bs(store)}"))
        ever = git(store, "log", "--all", "--format=%h", "--", "store-notes.txt") or ""
        R.append(("store-notes.txt was never committed and is still untracked, and the code repo is clean",
                  not ever and status_of(store) == ["?? store-notes.txt"] and not status_of(code), f"commits={ever!r} store={status_of(store)} code={status_of(code)}"))
        R.append(("No specwright-change.yaml was written, because the code branch has commits", not marker_paths, f"marker paths={marker_paths}"))
        hashes = [(git(r, "rev-parse", "--short=7", "main") or "?") for r in (code, store)]
        pushed = re.search(r"nothing (was )?pushed|not pushed|never push|no push|local only|push [^.\n]*when ready|without push", rep)
        R.append(("The report names the code repo and the store, both merge commits, and says nothing was pushed",
                  "code" in rep and "store" in rep and all(h in rep for h in hashes) and bool(pushed),
                  f"hashes={hashes} pushed={pushed.group(0) if pushed else None} report excerpt={rep[-240:]!r}"))
        R.append(no_amend)

    elif name in ("eval-store-finish-planning-only", "eval-store-finish-dated"):
        dated = name.endswith("dated")
        cn = "2026-10-07-add-greeting" if dated else "add-greeting"
        arch = find_commit(store, f"feat({cn}): archive change")
        ok, ev = archive_commit_ok(store, arch, cn, re.escape(cn) if dated else rf"{DATE}-{cn}", True)
        text = marker_text(store, arch) if arch else None
        has = text is not None and bool(re.search(r"^code_changes:\s*none\s*$", text, re.M))
        R.append((f"The store's archive commit feat({cn}): archive change stages only archive paths and includes {MARKER} with code_changes: none inside the archive directory",
                  ok and has, f"{ev} marker text={text!r}"))
        dirs = archive_dirs(store, "main")
        gone = git(store, "ls-tree", "main", f"openspec/changes/{cn}") == ""
        if dated:
            R.append(("The archive directory is exactly openspec/changes/archive/2026-10-07-add-greeting/ with no second date prefix, and the original change directory is gone",
                      dirs == [cn] and gone, f"archive dirs={dirs}"))
        else:
            R.append(("The archive directory openspec/changes/archive/<date>-add-greeting/ exists on the store's main and the original change directory is gone",
                      len(dirs) == 1 and bool(re.fullmatch(rf"{DATE}-{cn}", dirs[0])) and gone, f"archive dirs={dirs}"))
        R.append((f"The store's main HEAD is a merge commit with two parents and subject merge: {cn}, and the store is on main with only main left",
                  is_merge_of(store, cn) and on(store) == "main" and bs(store) == ["main"], f"store main={merge_head(store)} {on(store)} {bs(store)}"))
        R.append(("The code repo's main is unchanged: no merge commit and no new commit",
                  subjects(code, "--all") == [INITIAL], f"code commits={subjects(code, '--all')}"))
        R.append((f"The empty code branch feat/{cn} was deleted and the code repo is on main",
                  on(code) == "main" and bs(code) == ["main"], f"code={on(code)} {bs(code)}"))
        R.append(("Both working trees are clean", not status_of(code) and not status_of(store), f"code={status_of(code)} store={status_of(store)}"))
        if dated:
            doubled = re.search(rf"{DATE}-2026-10-07", rep) or [p for p in history_paths(store) if re.search(rf"archive/{DATE}-2026-10-07", p)]
            R.append(("The report names the archive directory 2026-10-07-add-greeting and no doubled date prefix",
                      "2026-10-07-add-greeting" in rep and not doubled, f"doubled={doubled!r}"))
        else:
            R.append(no_planning_in_code)
            nocode = re.search(r"no code (changes|commits|work)|planning-only|planning only|without code|had no code", rep)
            R.append(("The report says the change had no code changes and names the store's merge commit",
                      bool(nocode) and (git(store, "rev-parse", "--short=7", "main") or "?") in rep,
                      f"match={nocode.group(0) if nocode else None} report excerpt={rep[-240:]!r}"))
        R.append(no_amend)

    elif name in ("eval-store-finish-resume-code-merge", "eval-store-finish-resume-code-merge-from-main"):
        fx = json.loads((repo / "fixture-state.json").read_text(encoding="utf-8"))
        R.append(("The store gets no new commit: its history and main are exactly as the fixture left them, with one archive commit",
                  git(store, "rev-parse", "main") == fx["store_main"] and count_all(store) == fx["store_commits"]
                  and len([s for s in subjects(store, "--all") if s == f"feat({cn}): archive change"]) == 1 and is_merge_of(store, cn),
                  f"store main={git(store, 'rev-parse', 'main')} commits={count_all(store)} (want {fx['store_commits']})"))
        R.append(("The code repo's main HEAD is a merge commit with two parents and subject merge: add-greeting",
                  is_merge_of(code, cn), f"code main={merge_head(code)}"))
        R.append(("The code branch feat/add-greeting was deleted and the code repo is on main with only main left",
                  on(code) == "main" and bs(code) == ["main"], f"code={on(code)} {bs(code)}"))
        R.append(("The code repo's main tree equals the code branch's tip tree, so the merge kept the code",) + code_tree_kept(code, fx))
        R.append(("Both working trees are clean", not status_of(code) and not status_of(store), f"code={status_of(code)} store={status_of(store)}"))
        R.append(("The report does not give the Nothing to finish stop line", "nothing to finish - archive is on" not in rep, f"report excerpt={rep[-240:]!r}"))
        R.append(no_amend)

    elif name == "eval-store-finish-store-conflict":
        spec = "openspec/specs/greeting/spec.md"
        arch = find_commit(store, f"feat({cn}): archive change", "main..feat/add-greeting")
        ok, ev = archive_commit_ok(store, arch, cn, rf"{DATE}-{cn}", False)
        R.append(("The store's archive commit feat(add-greeting): archive change is on feat/add-greeting, staged by file, and not on main", ok, ev))
        R.append(("The store's main still ends at the conflicting commit docs(greeting): add greeting spec on main with no merge commit, and feat/add-greeting still exists in the store",
                  merge_head(store) == (1, CONFLICT_COMMIT["store"]) and "feat/add-greeting" in bs(store), f"store main={merge_head(store)} branches={bs(store)}"))
        ok, ev = conflict_left(store, [spec])
        R.append((f"The conflict was left for the user: the store merge is in progress with only {spec} unmerged, or it was aborted, and no conflict markers were committed", ok, ev))
        R.append(("The code repo is not merged: it is still on feat/add-greeting, main has only the initial commit and no merge commit, and the tree is clean",
                  on(code) == "feat/add-greeting" and subjects(code, "main") == [INITIAL] and not status_of(code),
                  f"code={on(code)} main={subjects(code, 'main')} status={status_of(code)}"))
        R.append(("The report lists openspec/specs/greeting/spec.md as conflicting and offers manual resolution or git merge --abort",
                  spec in rep and "abort" in rep and "resol" in rep, f"report excerpt={rep[-240:]!r}"))
        left = any("code" in x and re.search(r"not (been )?(yet )?merged|unmerged|no merge|not merge|left|untouched|stopp|did not|didn't|nothing", x) for x in sentences(rep))
        R.append(("The report says the code repo was left unmerged on feat/add-greeting", left and "feat/add-greeting" in rep, f"left={left}"))
        R.append(no_amend)

    elif name == "eval-store-finish-code-conflict":
        arch = find_commit(store, f"feat({cn}): archive change", "main")
        ok, ev = archive_commit_ok(store, arch, cn, rf"{DATE}-{cn}", False)
        R.append(("The store's archive commit feat(add-greeting): archive change is on the store's main, staged by file", ok, ev))
        R.append(("The store's main HEAD is a merge commit with two parents and subject merge: add-greeting, and the store's working tree is clean",
                  is_merge_of(store, cn) and not status_of(store), f"store main={merge_head(store)} status={status_of(store)}"))
        R.append(("The code repo's main still ends at the conflicting commit feat: add formal greeting with no merge commit, and feat/add-greeting still exists in the code repo",
                  merge_head(code) == (1, CONFLICT_COMMIT["code"]) and "feat/add-greeting" in bs(code), f"code main={merge_head(code)} branches={bs(code)}"))
        ok, ev = conflict_left(code, ["greet.py"])
        R.append(("The conflict was left for the user: the code merge is in progress with only greet.py unmerged, or it was aborted, and no conflict markers were committed", ok, ev))
        sents = sentences(rep)
        store_has = any("store" in x and re.search(r"merged|has the change|contains the change|landed", x) for x in sents)
        code_not = any("code" in x and re.search(r"not (yet )?(been )?merged|unmerged|does not (have|contain)|doesn't (have|contain)|without the change|conflict", x) for x in sents)
        R.append(("The report lists greet.py as conflicting and says the store's main has the change while the code repo does not",
                  "greet.py" in rep and store_has and code_not, f"greet.py={'greet.py' in rep} store has change={store_has} code does not={code_not} report excerpt={rep[-300:]!r}"))
        R.append(no_amend)

    else:  # eval-store-archive-on-main, eval-store-archive-on-main-pr-open
        pr_open = name.endswith("pr-open")
        branch = "chore/archive-add-greeting"
        direct = (git(store, "log", "--first-parent", "--no-merges", "--format=%s", "main") or "").splitlines()
        R.append(("No commit was made directly on the store's main: its non-merge commits are the fixture's",
                  direct == STORE_MAIN, f"main non-merge first-parent commits={direct}"))
        arch = None
        for line in (git(store, "log", "--all", "--format=%H%x09%s") or "").splitlines():
            h, _, subj = line.partition("\t")
            if re.fullmatch(rf"\w+\({cn}\): archive change", subj):
                arch = h
                break
        if arch:
            ok, ev = archive_commit_ok(store, arch, cn, rf"{DATE}-{cn}", False)
            ev = f"branches containing it={git(store, 'branch', '--all', '--contains', arch)!r}; {ev}"
        else:
            pending = status_of(store)
            ok = any(l.startswith("?? openspec/changes/archive/") for l in pending) and offers(rep, re.escape(branch)) and on(store) == "main"
            ev = f"no archive commit; store on {on(store)} status={pending[:3]}"
        R.append((f"The archive is carried on {branch} in the store, staged by file, or is still uncommitted on main with the report offering that branch", ok, ev))
        R.append(("No specwright-change.yaml was written in the store, in history or in the working tree",
                  not marker_paths and not list(store.glob(f"openspec/changes/archive/*/{MARKER}")), f"marker paths={marker_paths}"))
        if pr_open:
            R.append(("The code repo is untouched: still on feat/add-greeting with its task commits, main has only the initial commit, and the tree is clean",
                      on(code) == "feat/add-greeting" and bs(code) == ["feat/add-greeting", "main"] and subjects(code, "main") == [INITIAL]
                      and count_all(code) == 4 and not status_of(code), f"code={on(code)} {bs(code)} commits={count_all(code)} status={status_of(code)}"))
            try:
                pulls = json.loads((repo / "gh-state.json").read_text(encoding="utf-8"))["repos"]["acme/greeter"]["pulls"]
            except (OSError, ValueError, KeyError):
                pulls = None
            R.append(("No gh call created or changed a pull request, and the open code PR is still the only PR, open and unchanged",
                      not pr_mutations(repo) and pulls is not None and len(pulls) == 1 and pulls[0]["state"] == "open" and pulls[0]["body"] == "Adds greet and farewell.",
                      f"mutating calls={pr_mutations(repo)} pulls={[(p['number'], p['state']) for p in pulls or []]}"))
            R.append(("The report says the code PR is still open",
                      any(re.search(r"\bpr\b|pull request|#7", x) and "open" in x for x in sentences(rep)), f"report excerpt={rep[-240:]!r}"))
        else:
            R.append(("The code repo is untouched: on main with only main, no new commit, and the tree is clean",
                      on(code) == "main" and bs(code) == ["main"] and count_all(code) == 5 and is_merge_of(code, cn) and not status_of(code),
                      f"code={on(code)} {bs(code)} commits={count_all(code)} status={status_of(code)}"))
        R.append((f"The report names the recovery branch {branch}", branch in rep, f"report excerpt={rep[-240:]!r}"))
        R.append(no_amend)
    return R


def check_store_pr(name, repo, code, store, rep):
    """PR-pair evals: the change is finished in both repos on feat/add-greeting (4 code and 6 store commits), finish: pr as
    eval-bot, fake gh, git pushes dying at an unreachable proxy. Calls to the fake gh are in repo/gh-log.jsonl."""
    R = []
    on = lambda r: git(r, "branch", "--show-current")
    bs = lambda r: (git(r, "branch", "--format=%(refname:short)") or "").splitlines()
    cn = "add-greeting"
    try:
        repos = json.loads((repo / "gh-state.json").read_text(encoding="utf-8"))["repos"]
    except (OSError, ValueError, KeyError):
        repos = None
    pulls = {k: v.get("pulls", []) for k, v in (repos or {}).items()}
    comments = [c for v in (repos or {}).values() for lst in v.get("comments", {}).values() for c in lst]
    muts = pr_mutations(repo)
    no_amend = ("No commit was amended in either repo", not (amends(code) + amends(store)), f"amend entries={amends(code) + amends(store)}")
    code_untouched = (on(code) == FEAT and bs(code) == [FEAT, "main"] and subjects(code, "main") == [INITIAL]
                      and count_all(code) == 4 and not status_of(code))
    code_ev = f"code={on(code)} {bs(code)} commits={count_all(code)} status={status_of(code)}"

    if name == "eval-store-ship-push-rejected":
        R.append(("No gh call created or changed a pull request or a comment in either repo, and neither fake repo has a pull request",
                  repos is not None and not muts and not any(pulls.values()) and not comments,
                  f"mutating calls={muts} pulls={ {k: len(v) for k, v in pulls.items()} } comments={len(comments)}"))
        calls = [c["argv"] for c in gh_calls(repo)]
        users = {a[a.index("--user") + 1] for a in calls if "--user" in a[:-1]}
        R.append(("No gh call switched accounts (gh auth switch) or asked for another login's token; only the configured account eval-bot was used",
                  bool(calls) and not any(a[:2] == ["auth", "switch"] for a in calls) and users <= {"eval-bot"},
                  f"gh calls={len(calls)} token users={sorted(users)}"))
        R.append(("Both repos are still on feat/add-greeting with no new commit, no new branch and a clean tree, and both mains are unchanged",
                  code_untouched and on(store) == FEAT and bs(store) == [FEAT, "main"] and subjects(store, "main") == STORE_MAIN
                  and count_all(store) == 6 and not status_of(store),
                  f"{code_ev}; store={on(store)} {bs(store)} commits={count_all(store)} status={status_of(store)}"))
        R.append(no_amend)
        hit = [x for x in sentences(rep) if re.search(r"\bpush", x) and re.search(r"\bstore\b|plans", x)
               and re.search(r"fail|reject|error|unreachable|could not|unable|proxy|refused|denied", x)]
        R.append(("The report names the store push as the step that failed and shows its error (unreachable, could not connect, proxy or rejected)",
                  bool(hit), f"matching sentences={hit[:2]}"))
        none = [x for x in sentences(rep) if re.search(r"pull request|\bprs?\b", x)
                and re.search(r"\b(no|not|neither|nothing|never|without)\b|n't|stopp|did not|didn't", x)]
        R.append(("The report says no pull request was opened (for the store, and the code PR was not opened without it)",
                  bool(none), f"matching sentences={none[:2]}"))
        urls = re.findall(r"github\.com/\S+/pull/\d+", rep)
        ready = [x for x in sentences(rep) if re.search(r"\bready\b", x) and not re.search(r"\bnot\b|n't|\bnever\b|\bno\b|until|isn't|before", x)]
        R.append(("The report does not call the change ready or give a pull request URL", not urls and not ready,
                  f"urls={urls} ready sentences={ready[:2]}"))
    elif name.startswith("eval-store-ship-code-push-rejected"):
        # the git shim lets the store push through to the local bare repo <repo>/so.git; the code push dies at the proxy
        with_pr = name.endswith("store-pr-open")
        code_pulls, store_pulls = pulls.get("acme/greeter", []), pulls.get("acme/greeter-plans", [])
        if with_pr:
            R.append(("No gh call created or changed a pull request or a comment in either repo, and the code repo has no pull request",
                      repos is not None and not muts and not comments and not code_pulls,
                      f"mutating calls={muts} comments={len(comments)} code pulls={len(code_pulls)}"))
            R.append(("Store PR #3 is still the only store PR, open, with its description unchanged and no comment, link marker or review request added",
                      len(store_pulls) == 1 and store_pulls[0]["number"] == 3 and store_pulls[0]["state"] == "open"
                      and store_pulls[0]["body"] == STORE_PR_BODY and not comments and not muts,
                      f"store pulls={[(p['number'], p['state'], p['body']) for p in store_pulls]} comments={len(comments)} mutating calls={muts}"))
        else:
            R.append(("No gh call created or changed a pull request or a comment in either repo, and neither fake repo has a pull request",
                      repos is not None and not muts and not any(pulls.values()) and not comments,
                      f"mutating calls={muts} pulls={ {k: len(v) for k, v in pulls.items()} } comments={len(comments)}"))
        calls = [c["argv"] for c in gh_calls(repo)]
        users = {a[a.index("--user") + 1] for a in calls if "--user" in a[:-1]}
        R.append(("No gh call switched accounts (gh auth switch) or asked for another login's token; only the configured account eval-bot was used",
                  bool(calls) and not any(a[:2] == ["auth", "switch"] for a in calls) and users <= {"eval-bot"},
                  f"gh calls={len(calls)} token users={sorted(users)}"))
        tip = git(store, "rev-parse", "HEAD")
        bare_tip = git(repo / "so.git", "rev-parse", f"refs/heads/{FEAT}")
        R.append(("The store branch feat/add-greeting is on the local bare repo at the store's tip, and the store's origin still points at GitHub",
                  bool(tip) and bare_tip == tip and (git(store, "remote", "get-url", "origin") or "").startswith("https://github.com/"),
                  f"store tip={tip} bare tip={bare_tip} origin={git(store, 'remote', 'get-url', 'origin')}"))
        R.append(("Both repos are still on feat/add-greeting with no new commit and a clean tree, both mains are unchanged, and the code repo has no remote-tracking branch",
                  code_untouched and not git(code, "for-each-ref", "refs/remotes") and on(store) == FEAT and bs(store) == [FEAT, "main"]
                  and subjects(store, "main") == STORE_MAIN and count_all(store) == 6 and not status_of(store),
                  f"{code_ev} remotes={git(code, 'for-each-ref', 'refs/remotes')!r}; store={on(store)} {bs(store)} commits={count_all(store)} status={status_of(store)}"))
        R.append(no_amend)
        hit = [x for x in sentences(rep) if re.search(r"\bpush", x) and re.search(r"\bcode\b|acme/greeter(?!-)", x)
               and re.search(r"fail|reject|error|unreachable|could not|unable|proxy|refused|denied", x)]
        R.append(("The report names the code push as the step that failed and shows its error (unreachable, could not connect, proxy or rejected)",
                  bool(hit), f"matching sentences={hit[:2]}"))
        ready = [x for x in sentences(rep) if re.search(r"\bready\b", x) and not re.search(r"\bnot\b|n't|\bnever\b|\bno\b|until|isn't|before", x)]
        R.append(("The report does not call the change ready", not ready, f"ready sentences={ready[:2]}"))
        if not with_pr:
            none = [x for x in sentences(rep) if re.search(r"pull request|\bprs?\b", x)
                    and re.search(r"\b(no|not|neither|nothing|never|without)\b|n't|stopp|did not|didn't", x)]
            R.append(("The report says no pull request was opened in either repo", bool(none), f"matching sentences={none[:2]}"))
    else:  # eval-store-archive-before-merge-local-store
        arch = find_commit(store, f"feat({cn}): archive change")
        ok, ev = archive_commit_ok(store, arch, cn, rf"{DATE}-{cn}", False)
        on_branch = bool(arch) and (git(store, "branch", "--format=%(refname:short)", "--contains", arch) or "").split() == [FEAT]
        R.append(("The store has an archive commit feat(add-greeting): archive change on feat/add-greeting that stages only the removed change directory, the archive directory and openspec/specs/greeting/spec.md, and no specwright-change.yaml was written",
                  ok and on_branch and not [f for f in history_paths(store) if f.endswith(MARKER)],
                  f"on feat/add-greeting only={on_branch}; {ev}"))
        R.append(("The store is still on feat/add-greeting, its main is unchanged, it has no remote and no remote-tracking branch, and its tree is clean",
                  on(store) == FEAT and bs(store) == [FEAT, "main"] and subjects(store, "main") == STORE_MAIN
                  and not git(store, "remote") and not git(store, "for-each-ref", "refs/remotes") and not status_of(store),
                  f"store={on(store)} {bs(store)} remotes={git(store, 'remote')!r} status={status_of(store)}"))
        R.append(("The code repo is untouched: still on feat/add-greeting with its task commits, main has only the initial commit, and the tree is clean",
                  code_untouched, code_ev))
        ps = pulls.get("acme/greeter", [])
        R.append(("No gh call created or changed a pull request or a comment, and code PR #7 is still the only PR, open and unchanged (no review request was posted)",
                  repos is not None and not muts and not comments and len(ps) == 1 and ps[0]["number"] == 7
                  and ps[0]["state"] == "open" and ps[0]["body"] == "Adds greet and farewell.",
                  f"mutating calls={muts} comments={len(comments)} pulls={[(p['number'], p['state']) for p in ps]}"))
        hand = [x for x in sentences(rep) if FEAT in x and re.search(r"by hand|manual|share|yourself|hand off|hand over|push it", x)]
        why = [x for x in sentences(rep) if re.search(r"no (github )?(origin|remote)|no store pr|without a (github )?(origin|remote)|not (pushed|published)|no (push|pull request)", x)]
        R.append(("The report names the store branch feat/add-greeting and says it must be shared by hand because there is no store PR or GitHub remote",
                  bool(hand) and bool(why), f"hand sentences={hand[:2]} why sentences={why[:2]}"))
        R.append(no_amend)
    return R


# Roadmap evals (fixtures.build_roadmap). status: done | pending ("planning merged, code pending") | open (not done: planned, no archive).
ROADMAP = {
    "eval-store-roadmap-local": {
        "add-greeting": "done",                # merge: add-greeting on code main's first-parent history
        "2026-10-08-add-logging": "done",      # date-prefixed change name: archive dir and merge subject carry the name as is
        "add-farewell": "pending",             # archived, but only task 1.1 was cherry-picked; the branch is unmerged
        "add-shout": "open",                   # planned, after add-farewell (pending)
        "add-metrics": "open",                 # planned, after the done add-logging: the only change next may start
    },
    "eval-store-roadmap-pr": {
        "add-greeting": "done",                # code PR #1 merged into main
        "add-farewell": "pending",             # task 1.1 cherry-picked, code PR #2 open
        "add-shout": "pending",                # own PR #3 open; PR #4 (fork, same branch name) merged: not proof
        "add-metrics": "pending",              # PR #5 merged into integration: not proof
        "plan-release": "done",                # planning-only: specwright-change.yaml code_changes: none on the store's main
        "add-share": "open",                   # planned, after add-shout (pending)
        "add-report": "open",                  # planned, after add-metrics (pending)
        "add-export": "open",                  # planned, after plan-release (done): the only change next may start
    },
}
ROADMAP_BLOCKED = {"eval-store-roadmap-local": ("add-shout",), "eval-store-roadmap-pr": ("add-share", "add-report")}
ROADMAP_STARTABLE = {"eval-store-roadmap-local": ("add-metrics",), "eval-store-roadmap-pr": ("add-export",)}
ROADMAP_COMMITS = {"eval-store-roadmap-local": (12, 5), "eval-store-roadmap-pr": (7, 7)}  # (code, store) commits over --all, as the fixture leaves them
PENDING = r"planning merged[^|\n]*code[^|\n]{0,30}pending|code[^|\n]{0,30}pending[^|\n]*planning merged"
ROADMAP_WHY = {
    "add-greeting": "its archive is on the store's main and its code side merged as a whole",
    "2026-10-08-add-logging": "its archive 2026-10-08-add-logging (no second date prefix) is on the store's main and code main has merge: 2026-10-08-add-logging",
    "add-farewell": "only task 1.1 was cherry-picked onto code main; the rest of the change is unmerged",
    "add-shout": "its own code PR #3 is open; the merged PR #4 is a fork's same-named branch",
    "add-metrics": "its code PR #5 was merged into integration, not main",
    "plan-release": "its archive holds specwright-change.yaml with code_changes: none and there is no code PR",
}


def name_re(n):
    return rf"(?<![\w-]){re.escape(n)}(?![\w-])"


def roadmap_rows(rep, names):
    """name -> the report lines that give that change's status: the lines that start with its name (after list or table
    markup), or, when there are none, the lines that name only that change. A clause that says another roadmap change is
    done ("its prerequisite x is done", within one table cell or sentence) is removed, so it is not read as this one's."""
    lead_rows, sole_rows = {n: [] for n in names}, {n: [] for n in names}
    for line in rep.splitlines():
        hit = [n for n in names if re.search(name_re(n), line)]
        # strip markup and a list or table number ("1.", "2)", "| 3 |"), but not the date of a dated change name
        lead = re.sub(r"^[\s|*\-+>#`(\[\]]*(?:\d+(?:[.)]|\s*\|)[\s|*`(\[\]]*)?", "", line)
        for n in hit:
            cut = line
            for o in hit:
                if o != n:
                    cut = re.sub(name_re(o) + r"[^|.;\n]*?\bdone\b", " ", cut)
            if re.match(name_re(n), lead):
                lead_rows[n].append(cut)
            elif len(hit) == 1:
                sole_rows[n].append(cut)
    return {n: lead_rows[n] or sole_rows[n] for n in names}


def says_done(line):
    return bool(re.search(r"\bdone\b", line)) and not re.search(
        r"planning merged|\b(not|isn't|never)\b[^|.\n]{0,15}\bdone\b|pending|unverified|unknown", line)


def says_pending(line):
    return bool(re.search(PENDING, line))


def says_open(line):
    return not says_done(line) and "planning merged" not in line and bool(re.search(
        r"planned|not (yet )?(done|archived|started|merged)|no archive|to ?do|blocked|waiting|active|upcoming|queued|in progress|open", line))


def check_store_roadmap(name, repo, code, store, rep):
    """Roadmap evals: several archived changes on the store's main, one per status row of D9. Read-only: the report holds
    one status per change, `next` only starts a change whose prerequisites are done, and nothing in either repo changed."""
    R = []
    want = ROADMAP[name]
    pr = name.endswith("pr")
    rows = roadmap_rows(rep, list(want))
    check = {"done": says_done, "pending": says_pending}
    label = {"done": "done", "pending": "planning merged, code pending"}
    # a row may add detail without repeating the status, but none may give the change another status
    contra = {"done": lambda l: says_pending(l) or bool(re.search(r"\b(not|isn't|never)\b[^|.\n]{0,15}\bdone\b", l)),
              "pending": says_done}
    for n, st in want.items():
        if st != "open":
            R.append((f"The report gives {n} the status {label[st]}: {ROADMAP_WHY[n]}",
                      any(check[st](l) for l in rows[n]) and not any(contra[st](l) for l in rows[n]), f"lines={rows[n]}"))
    planned = [n for n, st in want.items() if st == "open"]
    R.append((f"The report does not call {', '.join(planned)} done: they are planned and have no archive",
              all(any(says_open(l) for l in rows[n]) and not any(says_done(l) for l in rows[n]) for n in planned), f"lines={ {n: rows[n] for n in planned} }"))
    sents = [x for x in sentences(rep) if re.search(r"\bnext\b|\bstart\b|\bbegin\b|\bpropose\b", x)]
    neg = r"\bnot\b|n't|blocked|until|wait|\bafter\b|cannot|can't|prerequisite|depend|behind|once|unless|rather than|instead"
    blocked = [(n, x) for n in ROADMAP_BLOCKED[name] for x in sents if re.search(name_re(n), x) and not re.search(neg, x)]
    started = [n for n in ROADMAP_STARTABLE[name] if any(re.search(name_re(n), x) for x in sents)]
    R.append((f"`next` uses only done changes as prerequisites: it names {', '.join(ROADMAP_STARTABLE[name])} and does not recommend {' or '.join(ROADMAP_BLOCKED[name])}",
              bool(started) and not blocked, f"startable named={started} blocked recommended={blocked}"))
    if pr:
        stale = [x for x in sentences(rep) if re.search(r"stale|out[- ]of[- ]date", x) and re.search(r"fetch|store|origin|remote|local", x)]
        R.append(("The report says the store status may be stale because the fetch failed", bool(stale), f"matching sentences={stale[:2]}"))
        calls = gh_calls(repo)
        R.append(("The code-side proof came from gh: the fake gh was asked for the code repo's pull requests",
                  any(c["argv"][:1] == ["api"] and any("repos/acme/greeter/pulls" in a for a in c["argv"]) for c in calls),
                  f"gh calls={[' '.join(c['argv'])[:90] for c in calls][:6]}"))
        try:
            ps = json.loads((repo / "gh-state.json").read_text(encoding="utf-8"))["repos"]["acme/greeter"]["pulls"]
        except (OSError, ValueError, KeyError):
            ps = None
        R.append(("No gh call created or changed anything: the five fixture pull requests are as they were",
                  not pr_mutations(repo) and ps is not None and [(p["number"], p["state"], bool(p["merged_at"]), p["base"]["ref"]) for p in ps]
                  == [(1, "closed", True, "main"), (2, "open", False, "main"), (3, "open", False, "main"), (4, "closed", True, "main"), (5, "closed", True, "integration")],
                  f"mutating calls={pr_mutations(repo)} pulls={[(p['number'], p['state']) for p in ps or []]}"))
    cc, sc = ROADMAP_COMMITS[name]
    cbr = (git(code, "branch", "--format=%(refname:short)") or "").splitlines()
    sbr = (git(store, "branch", "--format=%(refname:short)") or "").splitlines()
    R.append(("No repo was modified: both repos are on main with no new commit, branch or stash and a clean tree, and code main still ends at the roadmap commit",
              git(code, "branch", "--show-current") == git(store, "branch", "--show-current") == "main"
              and count_all(code) == cc and count_all(store) == sc and sorted(cbr) == ["feat/add-farewell", "main"] and sbr == ["main"]
              and not status_of(code) and not status_of(store) and not git(code, "stash", "list") and not git(store, "stash", "list")
              and (subjects(code, "-1") or [None])[0] == "docs: add project roadmap",
              f"commits code={count_all(code)}/{cc} store={count_all(store)}/{sc} branches={cbr} {sbr} status={status_of(code)} {status_of(store)}"))
    R.append(("No commit was amended in either repo", not (amends(code) + amends(store)), f"amend entries={amends(code) + amends(store)}"))
    return R



def check_store_roadmap_locked(repo, code, store, rep):
    """Roadmap close in a store-backed project while another session holds the store's gate lock (#43): close must stop
    before any branch or write, and leave the lock exactly as it found it. fixture-state.json has the starting state."""
    R = []
    fx = json.loads((repo / "fixture-state.json").read_text(encoding="utf-8"))
    on = lambda r: git(r, "branch", "--show-current")
    # The reflog also catches a close branch that was made, merged and deleted.
    close = {r.name: [b for b in ((git(r, "branch", "--all", "--format=%(refname:short)") or "").splitlines()
                                  + (git(r, "reflog", "--format=%gs") or "").splitlines()) if "close-" in b]
             for r in (code, store)}
    R.append(("No docs/close-* branch was ever made in either repo", not any(close.values()), f"close branches={close}"))
    cd = git(store, "rev-parse", "--path-format=absolute", "--git-common-dir")
    owner = Path(cd) / "specwright-gate.lock" / "owner" if cd else None
    text = owner.read_text(encoding="utf-8") if owner and owner.is_file() else None
    extra = sorted(p.name for p in owner.parent.iterdir()) if owner and owner.parent.is_dir() else None
    R.append(("The gate lock directory and its owner file are byte-identical to the fixture's",
              text == fx["owner"] and extra == ["owner"], f"owner={text!r} lock contents={extra}"))
    tips = {"code": git(code, "rev-parse", "main"), "store": git(store, "rev-parse", "main")}
    R.append(("Both repos are on main, and the code and store mains are unchanged",
              on(code) == on(store) == "main" and tips == {"code": fx["code_main"], "store": fx["store_main"]},
              f"code={on(code)} store={on(store)} tips={tips} fixture={fx['code_main'], fx['store_main']}"))
    st = {"code": status_of(code), "store": status_of(store)}
    R.append(("No project file was written: both working trees are clean", not st["code"] and not st["store"], f"status={st}"))
    hit = re.search(r"lock|busy|another session", rep)
    stop = re.search(r"STOPPED|stopped|did not close|not closed|cannot close|can't close|did not (start|create)", rep)
    R.append(("The report says close stopped because the store's gate is locked or busy, and names the owning change add-csv-export",
              bool(hit) and bool(stop) and "add-csv-export" in rep,
              f"match={hit.group(0) if hit else None} stop={stop.group(0) if stop else None}"))
    R.append(("No commit was amended in either repo", not amends(code) and not amends(store),
              f"amends={amends(code) + amends(store)}"))
    return R


def hook_fail_common(code, store, rep, scope):
    """Checks shared by the hook-failure evals: both repos on main with no branch of the gate's, no gate lock left, no amend,
    and the report quotes the hook's failure. `scope` is the branch-name prefix that must exist in neither repo."""
    R = []
    on = lambda r: git(r, "branch", "--show-current")
    allb = {r.name: (git(r, "branch", "--all", "--format=%(refname:short)") or "").splitlines() for r in (code, store)}
    R.append(("Both repos are on main", on(code) == on(store) == "main", f"code={on(code)} store={on(store)}"))
    left = {k: [b for b in v if b.startswith(scope)] for k, v in allb.items()}
    R.append((f"No {scope}* branch exists in either repo", not any(left.values()), f"branches={left}"))
    cd = git(store, "rev-parse", "--path-format=absolute", "--git-common-dir")
    lock = Path(cd) / "specwright-gate.lock" if cd else None
    R.append(("No gate lock is left in the store", lock is not None and not lock.exists(), f"lock={lock} exists={lock.exists() if lock else None}"))
    hit = re.search(r"post-checkout|hook failed", rep)
    R.append(("The report quotes the hook failure", bool(hit), f"match={hit.group(0) if hit else None}"))
    R.append(("No commit was amended in either repo", not amends(code) and not amends(store), f"amends={amends(code) + amends(store)}"))
    return R


def check_store_roadmap_hook_fail(repo, code, store, rep):
    """Roadmap close when the code repo's post-checkout hook fails after docs/close-m1 exists in the store (and the code
    branch was created): the gate rolls both repos back and stops. fixture-state.json has the starting tips."""
    fx = json.loads((repo / "fixture-state.json").read_text(encoding="utf-8"))
    R = hook_fail_common(code, store, rep, "docs/close-")
    tips = {"code": git(code, "rev-parse", "main"), "store": git(store, "rev-parse", "main")}
    R.append(("Both mains are unchanged", tips == {"code": fx["code_main"], "store": fx["store_main"]}, f"tips={tips} fixture={fx}"))
    st = {"code": status_of(code), "store": status_of(store)}
    R.append(("No project file was written: both working trees are clean", not st["code"] and not st["store"], f"status={st}"))
    return R


def check_store_branch(name, code, store, rep):
    """Store-branch evals: the gate runs on the code repo and the store; its lock is in the store's git common dir."""
    R = []
    on = lambda r: git(r, "branch", "--show-current")
    bs = lambda r: (git(r, "branch", "--format=%(refname:short)") or "").splitlines()
    cd = git(store, "rev-parse", "--path-format=absolute", "--git-common-dir")
    lock = Path(cd) / "specwright-gate.lock" if cd else None
    no_lock = ("No gate lock is left in the store", lock is not None and not lock.exists(),
               f"lock={lock} exists={lock.exists() if lock else None}")
    dirs = [r / "openspec/changes/add-csv-export" for r in (code, store) if (r / "openspec/changes/add-csv-export").exists()]
    mains = subjects(code, "main") == [INITIAL] and subjects(store, "main") == STORE_MAIN
    new = "feat/add-csv-export"
    if name == "eval-store-branch-clean":
        tips = [git(r, "rev-parse", new) for r in (code, store)]
        mtips = [git(r, "rev-parse", "main") for r in (code, store)]
        R.append(("The code repo and the store are both on feat/add-csv-export",
                  on(code) == on(store) == new, f"code={on(code)} store={on(store)}"))
        R.append(("Each new branch starts at its repo's main with no new commits",
                  all(tips) and tips == mtips, f"tips={tips} mains={mtips}"))
        R.append(("Both mains are unchanged", mains, f"code main={subjects(code, 'main')} store main={subjects(store, 'main')}"))
        d = store / "openspec/changes/add-csv-export"
        R.append(("The change directory is scaffolded in the store and the code repo has no openspec/changes",
                  d.is_dir() and not (code / "openspec/changes").exists(),
                  f"store dir={d.is_dir()} code changes dir={(code / 'openspec/changes').exists()}"))
        R.append(no_lock)
        R.append(("The report names both repos", "code" in rep and "store" in rep, f"report excerpt={rep[-200:]!r}"))
    elif name == "eval-store-branch-dirty":
        stash = [git(r, "stash", "list") or "" for r in (code, store)]
        R.append(("Both repos are still on main with only the main branch",
                  on(code) == on(store) == "main" and bs(code) == bs(store) == ["main"],
                  f"code={on(code)} {bs(code)} store={on(store)} {bs(store)}"))
        st = status_of(store)
        R.append(("The store's uncommitted edit is still there and unstashed",
                  st == [" M openspec/config.yaml"] and not any(stash) and not status_of(code),
                  f"store status={st} code status={status_of(code)} stash={stash}"))
        R.append(("No change directory was created in either repo", not dirs, f"dirs={dirs}"))
        R.append(no_lock)
        hit = re.search(r"uncommitted|not clean|dirty|local changes|modified", rep)
        opts = re.search(r"stash", rep) and re.search(r"commit", rep) and re.search(r"abort", rep)
        R.append(("The report shows the store is not clean and offers commit, stash or abort",
                  bool(hit) and bool(opts) and "store" in rep, f"match={hit.group(0) if hit else None} options={bool(opts)}"))
    elif name == "eval-store-branch-busy":
        R.append(("The code repo is still on main with only the main branch and no new commit",
                  on(code) == "main" and bs(code) == ["main"] and subjects(code, "main") == [INITIAL],
                  f"code={on(code)} {bs(code)}"))
        R.append(("The store is still on feat/other-change and no new branch was created in it",
                  on(store) == "feat/other-change" and sorted(bs(store)) == ["feat/other-change", "main"],
                  f"store={on(store)} {bs(store)}"))
        R.append(("No change directory add-csv-export was created in either repo", not dirs, f"dirs={dirs}"))
        R.append(no_lock)
        one = re.search(r"one (change|store)|at a time|in progress|busy", rep)
        R.append(("The report names feat/other-change and says one store holds one change in progress at a time",
                  "feat/other-change" in rep and bool(one), f"match={one.group(0) if one else None}"))
    elif name == "eval-store-branch-hook-fail":
        # the store's post-checkout hook fails after git created feat/add-csv-export there: the gate rolls both repos back
        R.extend(hook_fail_common(code, store, rep, "feat/add-csv-export"))
        R.append(("Both mains are unchanged", mains, f"code main={subjects(code, 'main')} store main={subjects(store, 'main')}"))
        R.append(("No change directory add-csv-export exists in either repo", not dirs, f"dirs={dirs}"))
    elif name in ("eval-store-branch-reused-name", "eval-store-branch-reused-name-origin"):
        # local: the earlier archive is on the store's main; origin: on origin/main only, and a fetch moves origin/main only
        store_main = STORE_MAIN if name.endswith("-origin") else ["merge: add-csv-export", *STORE_MAIN]
        R.append(("Both repos are still on main with only the main branch and no new commit",
                  on(code) == on(store) == "main" and bs(code) == bs(store) == ["main"] and subjects(code, "main") == [INITIAL]
                  and subjects(store, "main") == store_main,
                  f"code={on(code)} {bs(code)} store={on(store)} {bs(store)} store main={subjects(store, 'main')}"))
        R.append(("No change directory add-csv-export was created in either repo", not dirs, f"dirs={dirs}"))
        R.append(no_lock)
        used = re.search(r"already (been )?(used|archived)|archived|used before|reuse", rep)
        other = re.search(r"another name|different name|new name|rename|add-csv-export-2", rep)
        R.append(("The report says the name belongs to an archived change and offers another name",
                  bool(used) and bool(other), f"used={used.group(0) if used else None} other={other.group(0) if other else None}"))
    else:  # eval-store-branch-locked, eval-store-branch-stale-lock
        R.append(("Both repos are still on main with only the main branch and no new commit",
                  on(code) == on(store) == "main" and bs(code) == bs(store) == ["main"] and mains,
                  f"code={on(code)} {bs(code)} store={on(store)} {bs(store)}"))
        R.append(("No change directory was created in either repo", not dirs, f"dirs={dirs}"))
        owner = lock / "owner" if lock else None
        text = owner.read_text(encoding="utf-8") if owner and owner.is_file() else None
        R.append(("The gate lock and its owner file are still there, unchanged",
                  text is not None and "change: other-change" in text and "checkout: C:/elsewhere/code" in text, f"owner={text!r}"))
        if name == "eval-store-branch-locked":
            hit = re.search(r"lock|busy|another session", rep)
            R.append(("The report says the gate is locked or busy and names the owning change other-change",
                      bool(hit) and "other-change" in rep, f"match={hit.group(0) if hit else None}"))
        else:
            date = (re.search(r"time: (\d{4}-\d\d-\d\d)", text or "") or [None, ""])[1]
            R.append(("The report shows the date the lock was taken", bool(date) and date in rep, f"date={date!r}"))
            hit = re.search(r"confirm|remove the lock|stale", rep)
            R.append(("The report asks the user to confirm before removing the lock", bool(hit), f"match={hit.group(0) if hit else None}"))
    return R


def check_branch_store(name, code, store, rep):
    """eval-branch-store-*: the change gate's store-version check and the update lock (specwright-branch store steps 1 and 2)."""
    R = []
    on = lambda r: git(r, "branch", "--show-current")
    bs = lambda r: (git(r, "branch", "--format=%(refname:short)") or "").splitlines()
    cd = git(store, "rev-parse", "--path-format=absolute", "--git-common-dir")
    lock = Path(cd) / "specwright-gate.lock" if cd else None
    new = "feat/add-csv-export"
    dirs = [r / "openspec/changes/add-csv-export" for r in (code, store) if (r / "openspec/changes/add-csv-export").exists()]
    code_main = ["chore: record install version", INITIAL]
    store_main = ["chore: record store version", *STORE_MAIN]
    no_lock = ("No gate lock is left in the store", lock is not None and not lock.exists(), f"lock={lock}")
    if name == "eval-branch-store-version-match":
        # project 0.6.1 against store 0.6.0: the same major.minor, so the gate continues
        tips = [git(r, "rev-parse", new) for r in (code, store)]
        mtips = [git(r, "rev-parse", "main") for r in (code, store)]
        R.append(("Both repos are on feat/add-csv-export, each branch at its repo's main with no new commits",
                  on(code) == on(store) == new and all(tips) and tips == mtips,
                  f"code={on(code)} store={on(store)} tips={tips} mains={mtips}"))
        R.append(("Both mains are unchanged",
                  subjects(code, "main") == code_main and subjects(store, "main") == store_main,
                  f"code main={subjects(code, 'main')} store main={subjects(store, 'main')}"))
        R.append(no_lock)
        stopped = re.search(r"mismatch|behind|update (this project|the store)", rep)
        R.append(("The report does not stop on a version mismatch", not stopped, f"match={stopped.group(0) if stopped else None}"))
    elif name == "eval-branch-store-version-behind":
        # project 0.5.0 against store 0.6.0 owned by alice-laptop: the gate stops before any branch
        R.append(("Both repos are still on main with only the main branch and no new commit",
                  on(code) == on(store) == "main" and bs(code) == bs(store) == ["main"]
                  and subjects(code, "main") == code_main and subjects(store, "main") == store_main,
                  f"code={on(code)} {bs(code)} store={on(store)} {bs(store)}"))
        R.append(("No change directory was created in either repo", not dirs, f"dirs={dirs}"))
        R.append(no_lock)
        have = [v for v in ("0.5.0", "0.6.0", "alice-laptop") if v in rep]
        R.append(("The report names this project's version 0.5.0, the store's version 0.6.0 and the store's owner alice-laptop",
                  len(have) == 3, f"found={have}"))
        up = re.search(r"updat(?:e|ing)[^.\n]{0,60}(this project|code repo|project)[^.\n]{0,60}0\.6|"
                       r"(this project|code repo)[^.\n]{0,60}updat(?:e|ing)[^.\n]{0,40}0\.6", rep)
        R.append(("The report says to update this project to 0.6", bool(up), f"match={up.group(0) if up else None}"))
    else:  # eval-branch-store-update-lock
        R.append(("Both repos are still on main with only the main branch and no new commit",
                  on(code) == on(store) == "main" and bs(code) == bs(store) == ["main"]
                  and subjects(code, "main") == [INITIAL] and subjects(store, "main") == STORE_MAIN,
                  f"code={on(code)} {bs(code)} store={on(store)} {bs(store)}"))
        R.append(("No change directory was created in either repo", not dirs, f"dirs={dirs}"))
        owner = lock / "owner" if lock else None
        text = owner.read_text(encoding="utf-8") if owner and owner.is_file() else None
        R.append(("The update's gate lock and its owner file are still there, unchanged",
                  text is not None and "change: specwright-update 0.5.0 -> 0.6.0" in text and "code: C:/elsewhere/code" in text,
                  f"owner={text!r}"))
        R.append(("The report names the update and its checkout C:/elsewhere/code",
                  "update" in rep and "c:/elsewhere/code" in rep, f"report excerpt={rep[-200:]!r}"))
        rerun = re.search(r"re-?run[^.\n]{0,80}update|update[^.\n]{0,80}re-?run|run the update again", rep)
        R.append(("The report says to rerun the update from that checkout", bool(rerun), f"match={rerun.group(0) if rerun else None}"))
        offers = [x for x in re.split(r"(?<=[.!?\n])\s+", rep)
                  if re.search(r"remov|delet|rm -r|clear", x) and re.search(r"lock", x)
                  and not re.search(r"\bnot\b|n't|\bnever\b|\bno\b|without", x)]
        R.append(("The report does not offer to remove the lock", not offers, f"offers={offers}"))
    return R


def main(it):
    for run in sorted(Path(it).glob("eval-*/*/run-*")):
        repo = run / "repo"
        if not repo.exists():
            continue
        res = (check_store if is_store_run(repo) else check)(run.parents[1].name, repo, run)
        exp = [{"text": t, "passed": bool(p), "evidence": str(e)} for t, p, e in res]
        n = sum(x["passed"] for x in exp)
        g = {"expectations": exp, "summary": {"passed": n, "failed": len(exp) - n, "total": len(exp),
                                              "pass_rate": round(n / len(exp), 2) if exp else 0}}
        (run / "grading.json").write_text(json.dumps(g, indent=2), encoding="utf-8")
        print(f"{run.parents[1].name:28s} {run.parent.name:14s} {n}/{len(exp)}")


if __name__ == "__main__":
    main(sys.argv[1])
