#!/usr/bin/env bash
# Single branch-read and write boundary for Git and colocated jj repositories.
set -euo pipefail

py=
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then py=$c; break; fi
done
[ -n "$py" ] || { echo '{"ok":false,"error":"no_python","message":"vcs.sh needs python 3.8+"}'; exit 2; }
VCS_DIR=$(cd "$(dirname "$0")" && pwd -P)
VCS_BASH=${BASH:-bash}
if command -v cygpath >/dev/null 2>&1; then VCS_DIR=$(cygpath -m "$VCS_DIR"); VCS_BASH=$(cygpath -w "$VCS_BASH"); fi
export VCS_DIR VCS_BASH
exec "$py" -I -X utf8 - "$@" <<'PYSRC'
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

VCS_DIR = Path(os.environ["VCS_DIR"])
BASH = os.environ.get("VCS_BASH") or shutil.which("bash") or "bash"
PR_PAIR = VCS_DIR / "pr-pair.sh"
AS_SH = VCS_DIR / "as.sh"


class Stop(Exception):
    def __init__(self, error, message, code=1, **extra):
        super().__init__(message)
        self.error, self.message, self.code, self.extra = error, message, code, extra

    def object(self):
        return {"ok": False, "error": self.error, "message": self.message, **self.extra}


def emit(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    raise SystemExit(code)


def usage(message):
    raise Stop("usage", message, 2)


def process_arguments(argv):
    args = list(map(str, argv))
    if os.name != "nt":
        return args
    # MSYS expands unquoted braces and wildcards in native Windows argv.
    # Quote every argument, including those list2cmdline leaves unquoted.
    quoted = []
    for arg in args:
        arg = re.sub(r'(\\*)"', lambda match: "\\" * (2 * len(match.group(1)) + 1) + '"', arg)
        arg = re.sub(r'(\\+)$', lambda match: match.group(1) * 2, arg)
        quoted.append('"' + arg + '"')
    return " ".join(quoted)


def run(argv, cwd=None, env=None):
    try:
        return subprocess.run(process_arguments(argv), cwd=str(cwd) if cwd else None,
                              env=env or os.environ.copy(), capture_output=True, text=True)
    except OSError as exc:
        return subprocess.CompletedProcess(argv, 127, "", str(exc))


def bash_command(repo, *args, env=None):
    return run([BASH, "-c", 'exec "$@"', "vcs", *args], cwd=repo, env=env)


def bash_script(repo, script, *args, env=None):
    return run([BASH, str(script), *args], cwd=repo, env=env)


def git(repo, *args, env=None):
    return bash_command(repo, "git", *args, env=env)


def jj(repo, *args):
    return bash_command(repo, "jj", *args)


def path_text(path):
    return str(path).replace("\\", "/")


def parse_porcelain(out):
    paths, entries = [], []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        status, name = line[:2], path_text(line[3:])
        paths.append(name)
        entries.append({"status": status, "path": name})
    return paths, entries


def git_root(repo):
    result = git(repo, "rev-parse", "--show-toplevel")
    if result.returncode:
        raise Stop("not_repository", "not inside a Git work tree: " + result.stderr.strip())
    return Path(result.stdout.strip()).resolve()


def get_settings(code, repo, role):
    result = bash_script(None, PR_PAIR, "vcs", "--code", str(code))
    if result.returncode:
        try:
            data = json.loads(result.stdout)
        except ValueError:
            data = {"error": "settings_error", "message": result.stderr.strip() or result.stdout.strip()}
        raise Stop(data.get("error", "settings_error"), data.get("message", "could not read VCS settings"),
                   min(result.returncode, 3))
    try:
        choices = json.loads(result.stdout)
    except ValueError:
        raise Stop("settings_error", "pr-pair.sh vcs returned invalid JSON")
    backend = choices.get("code" if role == "code" else "store")
    if backend not in ("git", "jj"):
        raise Stop("settings_error", "pr-pair.sh vcs did not return a valid backend")
    context_args = ["context", "--code", str(code)]
    if role == "store":
        context_args.extend(("--store", str(repo)))
    context = bash_script(None, PR_PAIR, *context_args)
    try:
        ctx = json.loads(context.stdout)
    except ValueError:
        raise Stop("settings_error", "pr-pair.sh context returned invalid JSON")
    if context.returncode:
        raise Stop(ctx.get("error", "settings_error"), ctx.get("message", "could not read repository settings"),
                   min(context.returncode, 3))
    item = (ctx.get("store") if role == "store" else ctx.get("code")) or {}
    main = str(item.get("main") or "")
    return backend, main, {"login": str(item.get("login") or "")}


def detect_main(repo, configured):
    if configured:
        return configured
    for name in ("main", "master"):
        if git(repo, "show-ref", "--verify", "--quiet", "refs/heads/" + name).returncode == 0:
            return name
    return "main"


def probe(repo, code, role):
    backend, configured_main, settings = get_settings(code, repo, role)
    if backend == "jj":
        version = jj(repo, "--version")
        if version.returncode == 127:
            raise Stop("tool_missing", "jj is selected but jj is not installed or not on PATH: jj")
        found = re.search(r"\b(\d+)\.(\d+)\.(\d+)", version.stdout + version.stderr)
        if version.returncode or not found:
            raise Stop("tool_version_unknown", "could not determine jj version from jj --version")
        current = tuple(map(int, found.groups()))
        if current < (0, 46, 0):
            raise Stop("tool_too_old", "jj version %s.%s.%s is too old; minimum supported version is 0.46" % current)
        try:
            root = git_root(repo)
        except Stop:
            if (repo / ".jj").exists():
                raise Stop("not_colocated", "jj workspace has no Git work tree at the same toplevel")
            raise Stop("not_managed", "vcs: jj selected, but no .jj/ metadata was found")
        if not (root / ".jj").exists():
            raise Stop("not_managed", "vcs: jj selected, but the Git work tree has no .jj/ metadata")
        main = detect_main(root, configured_main)
        jroot = jj(repo, "root")
        if jroot.returncode or Path(jroot.stdout.strip()).resolve() != root:
            raise Stop("not_colocated", "jj workspace and Git work tree do not share the same toplevel")
        return {"backend": "jj", "main": main, "repo": str(root), "login": settings["login"]}
    root = git_root(repo)
    main = detect_main(root, configured_main)
    if backend == "git":
        return {"backend": "git", "main": main, "repo": str(root), "login": settings["login"],
                "jj_present": (root / ".jj").exists()}


def context(argv):
    if len(argv) < 1:
        usage("missing command")
    command, args = argv[0], argv[1:]
    allowed = {"--repo": "repo", "--role": "role", "--code": "code", "--branch": "branch",
               "--message-file": "message_file", "--scope": "scope", "--operation": "operation",
               "--login": "login", "--main": "main"}
    flags = {"--force": "force", "--no-tags": "no_tags", "--quiet": "quiet", "--remote-branch": "remote_branch"}
    opts, paths, after = {}, [], False
    i = 0
    while i < len(args):
        value = args[i]
        if after:
            paths.append(value)
            i += 1
        elif value == "--":
            after = True
            i += 1
        elif value in allowed:
            if i + 1 >= len(args):
                usage(value + " requires a value")
            opts[allowed[value]] = args[i + 1]
            i += 2
        elif value in flags:
            opts[flags[value]] = True
            i += 1
        else:
            usage("unknown option: " + value)
    if command not in {"probe", "state", "branch-create", "switch", "commit", "merge", "delete-branch",
                       "fetch-main", "pull", "push", "advance", "plan"}:
        usage("unknown command: " + command)
    if not opts.get("repo") or opts.get("role") not in ("code", "store"):
        usage("usage: vcs.sh <command> --repo <dir> --role code|store [--code <dir>] [options] [-- paths...]")
    if opts["role"] == "store" and not opts.get("code"):
        usage("--code is required when --role store")
    if opts["role"] == "code" and not opts.get("code"):
        opts["code"] = opts["repo"]
    if not Path(opts["repo"]).is_dir() or not Path(opts["code"]).is_dir():
        raise Stop("not_repository", "--repo and --code must name existing directories")
    return command, opts, paths


def require_branch(opts):
    if not opts.get("branch"):
        usage("missing --branch")
    return opts["branch"]


def git_current(repo):
    result = git(repo, "branch", "--show-current")
    if result.returncode:
        raise Stop("git_error", result.stderr.strip() or "git branch --show-current failed")
    return result.stdout.strip()


def git_state(repo, info, scope=None):
    branch = git_current(repo)
    status = git(repo, "status", "--porcelain")
    if status.returncode:
        raise Stop("git_error", status.stderr.strip() or "git status --porcelain failed")
    paths, entries = parse_porcelain(status.stdout)
    return {"ok": True, "backend": "git", "main": info["main"], "branch": branch,
            "on_main": branch == info["main"], "clean": not paths, "dirty_paths": paths,
            "dirty": entries, "behind": [], "behind_truncated": False,
            **({"jj_present": True} if info.get("jj_present") else {})}


def jj_result(repo, *args):
    result = jj(repo, *args)
    if result.returncode:
        raise Stop("jj_error", result.stderr.strip() or result.stdout.strip() or "jj command failed")
    return result.stdout


def jj_log(repo, revset, template, limit=None):
    args = ["log", "--no-graph", "--color=never", "-r", revset, "-T", template]
    if limit is not None:
        args.extend(("-n", str(limit)))
    return jj_result(repo, *args)


def jj_state(repo, info, scope=None):
    parent_text = jj_log(repo, "@", 'parents.map(|c| json(c.commit_id())).join("\\t") ++ "\\n"').strip()
    parent_ids = [json.loads(item) for item in parent_text.split("\\t")] if parent_text else []
    if len(parent_ids) != 1:
        raise Stop("ambiguous_branch", "working copy @ must have exactly one parent; found %d" % len(parent_ids))
    parent = parent_ids[0]
    template = 'if(remote, "", json({"name" => name, "conflict" => conflict, "target" => if(normal_target, normal_target.commit_id(), "")})) ++ "\\n"'
    bookmarks_raw = jj_result(repo, "bookmark", "list", "--revision", "@-", "-T", template)
    bookmarks = []
    for line in bookmarks_raw.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            raise Stop("jj_error", "jj bookmark list returned invalid JSON")
        if item.get("name"):
            bookmarks.append(item)
    main_names = {info["main"]}
    candidates = [b["name"] for b in bookmarks if b.get("name") != info["main"]]
    main_at_parent = any(b.get("name") == info["main"] for b in bookmarks)
    relevant_names = set(candidates) | main_names
    scoped = []
    if scope:
        scoped_raw = jj_result(repo, "bookmark", "list", scope, "glob:**/" + scope, "-T", template)
        scoped = [json.loads(line) for line in scoped_raw.splitlines() if line.strip()]
        scoped = [b for b in scoped if b.get("name") == scope or b.get("name", "").endswith("/" + scope)]
        relevant_names.update(b["name"] for b in scoped)
    conflicts = []
    for name in sorted(relevant_names):
        conflicted = jj_result(repo, "bookmark", "list", "--conflicted", name, "-T", template)
        conflicts.extend(json.loads(line)["name"] for line in conflicted.splitlines() if line.strip())
    if conflicts:
        raise Stop("ambiguous_branch", "conflicted local bookmark(s): " + ", ".join(sorted(set(conflicts))))
    if len(candidates) > 1:
        raise Stop("ambiguous_branch", "multiple local bookmarks point at @-: " + ", ".join(sorted(candidates)))
    branch = candidates[0] if candidates else ""
    selected = next((b for b in bookmarks if b.get("name") == branch), None)
    behind, truncated = [], False
    if not branch and scope:
        scoped = [b for b in scoped if b.get("target") and b["name"] != info["main"]]
        if len(scoped) == 1:
            selected = scoped[0]
            branch = selected["name"]
    if branch and scope and selected and selected.get("target") and selected["target"] != parent:
        template = 'json({"commit" => commit_id, "subject" => description.first_line(), "parents" => parents.len()}) ++ "\\n"'
        revset = selected["target"] + ".." + parent
        record = jj_log(repo, revset, template, limit=51)
        behind = [json.loads(line) for line in record.splitlines() if line.strip()]
        if len(behind) > 50:
            behind, truncated = behind[:50], True
        if any(item.get("parents", 0) != 1 for item in behind):
            raise Stop("ambiguous_branch", "bookmark recovery range is not linear")
    status = jj_result(repo, "diff", "--summary", "-r", "@")
    entries = []
    for line in status.splitlines():
        if len(line) >= 3 and line[0] in "AMDRC" and line[1].isspace():
            entries.append({"status": line[0], "path": path_text(line[2:])})
    paths = [entry["path"] for entry in entries]
    return {"ok": True, "backend": "jj", "main": info["main"], "branch": branch,
            "on_main": not branch and main_at_parent, "clean": not paths,
            "dirty_paths": paths, "dirty": entries, "behind": behind, "behind_truncated": truncated}



def main_and_context(info, opts):
    if opts.get("main"):
        info["main"] = opts["main"]
    return info["main"]


def current_state(repo, info, opts):
    if info["backend"] == "git":
        return git_state(repo, info, opts.get("scope"))
    return jj_state(repo, info, opts.get("scope"))


def git_checked(repo, *args, env=None, error="git_error"):
    result = git(repo, *args, env=env)
    if result.returncode:
        raise Stop(error, (result.stderr or result.stdout).strip() or "git " + " ".join(args) + " failed")
    return result


def remote_url(repo, remote="origin"):
    result = git(repo, "remote", "get-url", remote)
    return result.stdout.strip() if result.returncode == 0 else ""


def is_github_url(url):
    if re.match(r"^[A-Za-z]:[\\\\/]", url):
        return False
    if "://" in url:
        host = urlsplit(url).hostname
    else:
        match = re.match(r"^(?:[^@/]+@)?([^/:]+):", url)
        host = match.group(1) if match else None
    return host is not None and host.lower().rstrip(".") in ("github.com", "ssh.github.com")


def network_git(repo, args, login):
    github = is_github_url(remote_url(repo))
    who = login or ""
    if github and not who:
        resolved = bash_script(repo, AS_SH, "--resolve")
        if resolved.returncode:
            raise Stop("fence_failed", resolved.stderr.strip() or "as.sh could not resolve GitHub login", 3)
        who = resolved.stdout.strip()
    result = (bash_script(repo, AS_SH, who, "git", *args) if github
              else git(repo, *args))
    if result.returncode:
        message = (result.stderr or result.stdout).strip() or "Git network operation failed"
        if args[0] == "pull" and re.search(r"not possible to fast-forward|divergent branches", message, re.I):
            raise Stop("not_fast_forward", message)
        error = "fence_failed" if github and result.returncode == 3 else "git_network_error"
        raise Stop(error, message, 3)
    return result


def check_branch(repo, expected):
    current = git_current(repo)
    if current != expected:
        raise Stop("wrong_branch", "expected branch %r, currently on %r" % (expected, current))
    return current


def run_git_operation(command, repo, info, opts, paths, ctx):
    main = main_and_context(info, opts)
    backend = info["backend"]
    branch = opts.get("branch")
    if command == "branch-create":
        branch = require_branch(opts)
        result = git_checked(repo, "checkout", "-b", branch)
        return {"ok": True, "backend": backend, "branch": branch, "output": result.stdout.strip()}
    if command == "switch":
        branch = require_branch(opts)
        result = git_checked(repo, "checkout", branch)
        return {"ok": True, "backend": backend, "branch": branch, "output": result.stdout.strip()}
    if command == "commit":
        branch = require_branch(opts)
        if not opts.get("message_file") or not paths:
            usage("commit requires --message-file and at least one path after --")
        if os.name == "nt" and sum(len(os.fsencode(path)) + 1 for path in paths) + len(os.fsencode(opts["message_file"])) > 32000:
            raise Stop("too_many_paths", "named Git paths exceed the Windows command-line limit; name a containing directory instead")
        check_branch(repo, branch)
        args = ["add", "--", *paths]
        git_checked(repo, *args)
        result = git(repo, "commit", "-F", opts["message_file"], "--", *paths)
        if result.returncode:
            raise Stop("git_commit_failed", (result.stderr or result.stdout).strip() or "git commit failed")
        head = git_checked(repo, "rev-parse", "HEAD").stdout.strip()
        return {"ok": True, "backend": backend, "branch": branch, "commit": head}
    if command == "merge":
        branch = require_branch(opts)
        if not opts.get("message_file"):
            usage("merge requires --message-file")
        check_branch(repo, main)
        result = git_checked(repo, "merge", "--no-ff", branch, "-F", opts["message_file"], error="merge_failed")
        return {"ok": True, "backend": backend, "branch": branch, "commit": git_checked(repo, "rev-parse", "HEAD").stdout.strip()}
    if command == "delete-branch":
        branch = require_branch(opts)
        if opts.get("force") and git_current(repo) == branch:
            raise Stop("branch_is_current", "refusing to force-delete the currently checked out branch")
        flag = "-D" if opts.get("force") else "-d"
        result = git_checked(repo, "branch", flag, branch, error="branch_delete_failed")
        return {"ok": True, "backend": backend, "branch": branch}
    if command == "fetch-main":
        args = ["fetch"]
        if opts.get("quiet"):
            args.append("-q")
        if opts.get("no_tags"):
            args.append("--no-tags")
        args.extend(("origin", main))
        result = network_git(repo, args, opts.get("login") or ctx.get("login"))
        ref = "refs/remotes/origin/" + main
        commit = git_checked(repo, "rev-parse", "--verify", ref + "^{commit}", error="fetch_failed").stdout.strip()
        return {"ok": True, "backend": backend, "ref": "origin/" + main, "commit": commit}
    if command == "pull":
        args = ["pull", "--ff-only"]
        if opts.get("remote_branch"):
            args.extend(("origin", main))
        network_git(repo, args, opts.get("login") or ctx.get("login"))
        return {"ok": True, "backend": backend, "branch": git_current(repo)}
    if command == "push":
        branch = require_branch(opts)
        check_branch(repo, branch)
        network_git(repo, ["push", "-u", "origin", "HEAD"], opts.get("login") or ctx.get("login"))
        return {"ok": True, "backend": backend, "branch": branch}
    if command == "advance":
        if opts.get("scope") is None:
            usage("advance requires --scope")
        return {"ok": True, "backend": backend, "branch": git_current(repo), "advanced": False}
    usage(command + " is not implemented for the Git backend")


def plan(repo, code, role, info, opts):
    operation = opts.get("operation")
    if operation not in ("switch", "pull", "delete-branch"):
        usage("plan --operation must be switch, pull or delete-branch")
    branch = require_branch(opts)
    subcommand = "delete-branch" if operation == "delete-branch" else operation
    args = ["bash", str(VCS_DIR / "vcs.sh"), subcommand, "--repo", str(repo), "--role", role, "--code", str(code),
            "--branch", branch]
    if opts.get("force"):
        args.append("--force")
    if opts.get("remote_branch"):
        args.append("--remote-branch")
    if opts.get("login"):
        args.extend(("--login", opts["login"]))
    return {"ok": True, "backend": info["backend"], "commands": [" ".join(map(shlex.quote, args))]}


def main(argv):
    command, opts, paths = context(argv)
    repo = Path(opts["repo"]).resolve()
    code = Path(opts["code"]).resolve()
    role = opts["role"]
    info = probe(repo, code, role)
    if opts.get("main"):
        info["main"] = opts["main"]
    if command == "probe":
        result = {"ok": True, "backend": info["backend"], "main": info["main"]}
        if info["backend"] == "git" and info.get("jj_present"):
            result["jj_present"] = True
        return result
    if command == "state":
        return current_state(repo, info, opts)
    if command == "plan":
        return plan(repo, code, role, info, opts)
    if info["backend"] == "git":
        return run_git_operation(command, repo, info, opts, paths, {"login": info.get("login", "")})
    # Group 2 supplies jj probing and state only. Later groups own jj writes.
    if command in {"branch-create", "switch", "commit", "merge", "delete-branch", "fetch-main", "pull", "push", "advance", "plan"}:
        usage("the jj %s operation is implemented by a later backend task" % command)
    usage("unknown command: " + command)


try:
    emit(main(sys.argv[1:]))
except Stop as exc:
    emit(exc.object(), exc.code)
except SystemExit:
    raise
except Exception as exc:
    emit({"ok": False, "error": "internal_error", "message": str(exc)}, 1)
PYSRC
