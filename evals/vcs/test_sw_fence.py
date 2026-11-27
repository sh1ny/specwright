"""sw vcs fences identity in its own process (native-cli-internal-calls D1, D2, D8).

Every test runs the built `sw` (SPECWRIGHT_SW) through evals/swcall.py (direct argument entry) with failing
recording `python` and `python3` first on PATH. An interpreter that recorded a run fails the test before anything else is read. The fake `gh` and a `git` shim that answers `git remote get-url origin` with a
github.com URL (every real fetch and push still goes to the local bare origin) stand in for GitHub.

A store has no installed Specwright version: its calls name the code checkout with --code, or --project.

Run: python -m unittest evals/vcs/test_sw_fence.py
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import gbnet
import jjenv
import fakeexe  # after jjenv, which puts evals/ on sys.path
import sentinels
from butenv import Scratch as ButScratch
from butenv import require_but
from jjenv import require_jj
from vcs_test_support import ROOT, STAMP, bash_path_env, native_path, stamp_version, sw_home

sys.path.append(str(ROOT / "evals" / "cli"))
import swharness  # noqa: E402
import swcall  # noqa: E402  (vcs_test_support puts evals/ on sys.path)

GITHUB = "https://github.com/o/r.git"
LOGIN = "KintsugiBot"
TOKENS = {LOGIN: "tok-k", "store-bot": "tok-store", "sh1ny": "tok-sh1ny"}

# Pretend the real, local origin has GitHub URLs while logging actual Git launches.
# Fetch and push URL overrides can differ. A cutoff is injected as an exit status.
GIT_SHIM = r"""#!/bin/sh
case "$*" in
  "remote get-url origin"|"remote get-url --all origin")
    if [ -n "${SWF_ORIGIN_URL:-}" ]; then printf '%s\n' "$SWF_ORIGIN_URL"; exit 0; fi ;;
  "remote get-url --push --all origin")
    if [ "${SWF_PUSH_URLS+x}" = x ]; then printf '%s\n' "$SWF_PUSH_URLS"; exit 0; fi
    if [ -n "${SWF_ORIGIN_URL:-}" ] && ! "$SWF_REAL_GIT" config --get remote.origin.pushurl >/dev/null; then
      printf '%s\n' "$SWF_ORIGIN_URL"; exit 0
    fi ;;
  "ls-remote --get-url")
    if [ -n "${SWF_UPSTREAM_URL:-}" ]; then printf '%s\n' "$SWF_UPSTREAM_URL"; exit 0; fi
    branch=$("$SWF_REAL_GIT" symbolic-ref --short HEAD 2>/dev/null)
    upstream=$("$SWF_REAL_GIT" config --get "branch.$branch.remote" 2>/dev/null)
    if [ "${upstream:-origin}" = origin ] && [ -n "${SWF_ORIGIN_URL:-}" ]; then
      printf '%s\n' "$SWF_ORIGIN_URL"; exit 0
    fi ;;
esac
here=$PWD
if command -v cygpath >/dev/null 2>&1; then here=$(cygpath -m "$PWD"); fi
{
  printf 'cwd=%s|token=%s|prompt=%s|ssh=%s|host=%s|ent=%s|ent2=%s|args=' \
      "$here" "${GH_TOKEN-unset}" "${GIT_TERMINAL_PROMPT-unset}" "${GIT_SSH_COMMAND:+set}" \
      "${GH_HOST-unset}" "${GH_ENTERPRISE_TOKEN-unset}" "${GITHUB_ENTERPRISE_TOKEN-unset}"
  for a in "$@"; do printf '%s\037' "$a"; done
  printf '\n'
} >> "$SWF_GIT_LOG"
if [ -n "${SWF_FETCH_EXIT:-}" ] && [ "$1" = fetch ]; then exit "$SWF_FETCH_EXIT"; fi
exec "$SWF_REAL_GIT" "$@"
"""
# A `gh` that needs no Python (a failing `python` is first on PATH, and a Python start is slow): it logs the token it saw and its
# arguments, serves `auth token`/`api user`, and can inject a lookup exit result.
GH_SHIM = r"""#!/bin/sh
{ printf 'token=%s|argv=' "${GH_TOKEN-unset}"; for a in "$@"; do printf '%s\037' "$a"; done; printf '\n'; } >> "$SWF_GH_LOG"
if [ "$1 $2 $3" = "auth token --help" ]; then echo "--user"; exit 0; fi
if [ "$1 $2" = "auth token" ]; then
  user=; prev=
  for a in "$@"; do if [ "$prev" = --user ]; then user=$a; fi; prev=$a; done
  if [ -n "${SWF_TEST_RETARGET_PUSH:-}" ] && [ -n "$user" ]; then
    "$SWF_REAL_GIT" config --local remote.origin.pushurl "$SWF_TEST_RETARGET_PUSH" || exit 2
  fi
  if [ -n "${SWF_GH_EXIT:-}" ]; then exit "$SWF_GH_EXIT"; fi
  for pair in $SWF_GH_TOKENS; do if [ "${pair%%=*}" = "$user" ]; then echo "${pair#*=}"; exit 0; fi; done
  echo "no oauth token found for $user" >&2; exit 1
fi
if [ "$1" = api ]; then
  if [ -n "${GH_TOKEN:-}" ]; then
    for pair in $SWF_GH_TOKENS; do if [ "${pair#*=}" = "$GH_TOKEN" ]; then echo "${pair%%=*}"; exit 0; fi; done
    echo "bad credentials" >&2; exit 1
  fi
  if [ -n "${SWF_GH_USER:-}" ]; then echo "$SWF_GH_USER"; exit 0; fi
  echo "To get started with GitHub CLI, please run:  gh auth login" >&2; exit 1
fi
echo "unsupported: $*" >&2; exit 2
"""
READS = {"status", "for-each-ref", "symbolic-ref", "branch", "log"}


def write_tool(path, text):
    """A fake tool: the script, and on Windows its `.cmd` wrapper (`sw` starts nothing without an extension there, D9)."""
    fakeexe.write_fake(path, text)


def posix(path):
    return Path(path).resolve().as_posix()


class Harness:
    """The sentinels, the fake gh, the git shim and the way to run `sw vcs` with them."""
    probed = False

    def __init__(self, case):
        self.case = case
        root = case.root
        self.sent = sentinels.install(root / "pybin", root / "sentinels.log")
        self.tools = root / "tools"
        self.tools.mkdir()
        write_tool(self.tools / "git", GIT_SHIM)
        write_tool(self.tools / "gh", GH_SHIM)
        self.gh_log = root / "gh-log.txt"
        self.git_log = root / "git-calls.log"
        self.world_env = {}
        self.origin_url = GITHUB
        self.set_gh(user=LOGIN)
        if not Harness.probed:  # the sentinels are the same everywhere: one probe per process shows that they record
            self.sent.probe(case)
            Harness.probed = True

    def set_gh(self, user=None, lookup_exit=None):
        self.gh_user, self.gh_exit = user, lookup_exit

    def env(self, extra=None):
        env = swharness.fixture_env()
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN"):
            env.pop(name, None)
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
        env.update({key: value for key, value in self.world_env.items() if key != "PATH"})
        env.update(self.sent.env)
        env.update({"SWF_GH_LOG": posix(self.gh_log), "SWF_GH_USER": self.gh_user or "", "SWF_GH_EXIT": self.gh_exit or "",
                    "SWF_GH_TOKENS": " ".join("%s=%s" % pair for pair in TOKENS.items()),
                    "SWF_GIT_LOG": posix(self.git_log), "SWF_REAL_GIT": jjenv.real_git(),
                    "SWF_ORIGIN_URL": self.origin_url or ""})
        env.update(extra or {})
        env.setdefault("SPECWRIGHT_HOME", str(sw_home()))
        env["PATH"] = bash_path_env(self.sent.bin, extra_path=(self.tools,))["PATH"]
        return env

    def run(self, command, *options, repo, role="code", code=None, env=None, expected=0, project=None, cwd=None):
        """`sw vcs <command>` entered directly (evals/swcall.py); returns (document, process). The sentinels are read first.
        `project` is the leading --project of a call started outside the checkout that carries the VERSION."""
        args = ["vcs", command, "--repo", str(repo), "--role", role]
        for stamped in (repo if role == "code" else None, code):  # a store carries no VERSION: its code checkout does
            if stamped is not None and not (Path(stamped) / STAMP).exists():
                stamp_version(stamped)
        if code is not None:
            args += ["--code", str(code)]
        args += list(map(str, options))
        run_env = self.env(env)
        run_env["PATH"] = native_path(run_env["PATH"])
        done = swcall.run(args, project=project, cwd=str(cwd or repo), env=run_env, timeout=180, text=False)
        out = done.stdout.decode("utf-8", "surrogateescape")
        err = done.stderr.decode("utf-8", "surrogateescape")
        self.case.assertEqual(self.sent.recorded(), [],
                              "a Python interpreter ran: %s %s" % (out, err))
        self.case.assertEqual(done.returncode, expected, out + err)
        try:
            doc = json.loads(out)
        except ValueError as e:
            self.case.fail("sw vcs did not print one JSON document: %r %r (%s)" % (out, err, e))
        return doc, done

    def git_calls(self):
        calls = []
        if not self.git_log.exists():
            return calls
        for line in self.git_log.read_bytes().decode("utf-8", "surrogateescape").splitlines():
            head, args = line.split("|args=", 1)
            fields = dict(part.split("=", 1) for part in head.split("|"))
            calls.append({**fields, "argv": args.split("\x1f")[:-1]})
        return calls

    def gh_calls(self):
        if not self.gh_log.exists():
            return []
        calls = []
        for line in self.gh_log.read_text(encoding="utf-8").splitlines():
            head, args = line.split("|argv=", 1)
            calls.append({"token": head.split("=", 1)[1], "argv": args.split("\x1f")[:-1]})
        return calls


class World:
    """One repository of one backend with a local bare origin the shim presents as github.com."""
    count = 0

    def __init__(self, case, kind, repo, origin, env):
        self.case, self.kind, self.repo, self.origin, self.env = case, kind, Path(repo), Path(origin), env

    def real(self, cwd, *args):
        done = subprocess.run([jjenv.real_git(), *map(str, args)], cwd=str(cwd), capture_output=True, text=True,
                              env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                                   "GIT_AUTHOR_NAME": "Fence Test", "GIT_AUTHOR_EMAIL": "fence@example.invalid",
                                   "GIT_COMMITTER_NAME": "Fence Test", "GIT_COMMITTER_EMAIL": "fence@example.invalid",
                                   **self.env})
        self.case.assertEqual(done.returncode, 0, "git %s: %s" % (" ".join(map(str, args)), done.stderr))
        return done.stdout.strip()

    def side(self):
        """A fresh clone of the origin (another work tree acting as the remote's side)."""
        World.count += 1
        side = self.case.root / ("side-%d" % World.count)
        self.real(self.case.root, "clone", "-q", self.origin.as_posix(), side.as_posix())
        return side

    def merge(self, branch):
        """The merge button with delete-branch: a merge commit on the origin's main, then the head branch deleted."""
        side = self.side()
        self.real(side, "fetch", "-q", "origin", branch)
        self.real(side, "merge", "--no-ff", "-m", "Merge pull request #1 from o/" + branch, "FETCH_HEAD")
        self.real(side, "push", "-q", "origin", "HEAD:refs/heads/main")
        self.real(side, "push", "-q", "origin", ":refs/heads/" + branch)
        return self.real(side, "rev-parse", "HEAD")

    def advance(self, name):
        """A new commit on the origin's main, made in a side clone; returns its id."""
        side = self.side()
        name = "%s-%d" % (name, World.count)
        (side / (name + ".txt")).write_text(name + "\n", encoding="utf-8")
        self.real(side, "add", name + ".txt")
        self.real(side, "commit", "-q", "-m", "origin " + name)
        self.real(side, "push", "-q", "origin", "HEAD:refs/heads/main")
        return self.real(side, "rev-parse", "HEAD")

    def origin_refs(self):
        out = self.real(self.origin, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads")
        return dict(line.split() for line in out.splitlines())


class FenceCase(gbnet.GitButlerNetworkCase):
    def setUp(self):
        swharness.require_sw()
        super().setUp()
        self.h = Harness(self)

    # ---- the repositories ---------------------------------------------------------------------------------------------

    def git_world(self):
        """The default Git repository on branch feat/a (one commit past main), main pushed to a local bare origin."""
        repo = self.repo
        self.set_settings(repo, "main_branch: main\n")
        origin = self.root / "origin.git"
        self.git(self.root, "init", "-q", "--bare", "-b", "main", str(origin))
        self.git(repo, "remote", "add", "origin", origin.as_posix())
        self.assertEqual(self.git(repo, "push", "-q", "-u", "origin", "main").returncode, 0)
        self.git(repo, "checkout", "-q", "-b", "feat/a")
        (repo / "feat.txt").write_text("feat\n", encoding="utf-8")
        self.git(repo, "add", "feat.txt")
        self.git(repo, "commit", "-q", "-m", "feat: a")
        return World(self, "git", repo, origin, {})

    def jj_world(self):
        jj = require_jj()
        scratch = jjenv.Scratch()
        self.addCleanup(scratch.close)
        fixture = scratch.tracked_repo()
        repo = fixture.path
        self.set_settings(repo, "vcs: jj\nmain_branch: main\n")
        fixture.run(jj, "commit", "-m", "fixture Specwright settings")
        fixture.run(jj, "bookmark", "set", "main", "-r", "@-")
        fixture.run(jj, "git", "push", "--bookmark", "main")
        fixture.run(jj, "bookmark", "create", "feat/a", "-r", "@-")
        (repo / "feat.txt").write_text("feat\n", encoding="utf-8")
        fixture.run(jj, "commit", "-m", "feat: a")
        fixture.run(jj, "bookmark", "set", "feat/a", "-r", "@-")
        world = World(self, "jj", repo, scratch.origin, dict(scratch.env))
        self.h.world_env = world.env
        world.fixture, world.jj = fixture, jj
        return world

    def gitbutler_world(self):
        require_but()
        scratch = ButScratch()
        self.addCleanup(scratch.close)
        repo = self.workspace(scratch, ["feat/a"])
        world = World(self, "gitbutler", repo.path, scratch.origin, dict(scratch.env))
        self.h.world_env = world.env
        world.scratch = scratch
        return world

    # ---- Git, jj and GitButler through the same steps -------------------------------------------------------------------

    def arrange(self, world, step):
        """The state `step` (fetch-main, push or pull) acts on; returns what its check needs."""
        if step == "fetch-main":
            return world.advance("fetch")
        if step == "push":
            if world.kind == "git":
                self.git(world.repo, "checkout", "-q", "feat/a")
            elif world.kind == "jj":
                (world.repo / "more.txt").write_text("more\n", encoding="utf-8")
                world.fixture.run(world.jj, "commit", "-m", "feat: more")
                world.fixture.run(world.jj, "bookmark", "set", "feat/a", "-r", "@-")
            return None
        if world.kind == "git":
            self.git(world.repo, "checkout", "-q", "main")
            return world.advance("pull")
        if world.kind == "gitbutler":
            if not world.real(world.repo, "for-each-ref", "refs/heads/feat/a"):  # the earlier pull took the merged branch
                return world.advance("pull")
            world.real(world.repo, "push", "-q", "origin", "refs/heads/feat/a:refs/heads/feat/a")
            return world.merge("feat/a")
        return world.advance("pull")

    @staticmethod
    def expected_argv(world, step, quiet):
        flags = ["-q", "--no-tags"] if quiet else []
        if step == "fetch-main":
            if world.kind == "git":
                return ["fetch", *flags, "origin", "main"]
            return ["fetch", *flags, "--refmap=", "origin", "refs/heads/main"]
        if step == "push":
            return {"git": ["push", "-u", "origin", "HEAD"],
                    "gitbutler": ["push", "--no-follow-tags", "origin", "refs/heads/feat/a:refs/heads/feat/a"]}.get(world.kind)
        return {"git": ["pull", "--ff-only"], "jj": ["fetch", "--refmap=", "origin", "refs/heads/main"]}.get(world.kind)

    def run_steps(self, world, login_variants=((True, True), (False, False))):
        """Each of fetch-main, push and pull with and without --login; every call must start no script and no Python."""
        for step in ("fetch-main", "push", "pull"):
            for with_login, quiet in login_variants:
                label = "%s %s %s" % (world.kind, step, "with --login" if with_login else "resolving the login")
                with self.subTest(label):
                    self.h.sent.clear()
                    arranged = self.arrange(world, step)
                    seen_git, seen_gh = len(self.h.git_calls()), len(self.h.gh_calls())
                    options = []
                    if step == "fetch-main" and quiet:
                        options += ["--quiet", "--no-tags"]
                    if step in ("push", "pull") and (step == "push" or world.kind == "gitbutler"):
                        options += ["--branch", "feat/a"]
                    if with_login:
                        options += ["--login", LOGIN]
                    doc, _ = self.h.run(step, *options, repo=world.repo)

                    self.assertTrue(doc.get("ok"), doc)
                    gh = [call["argv"] for call in self.h.gh_calls()[seen_gh:]]
                    self.assertTrue(any(argv[:2] == ["auth", "token"] and argv[-2:] == ["--user", LOGIN] for argv in gh), gh)
                    # the active account is looked up (without a token) only when no login was given
                    looked_up = [call for call in self.h.gh_calls()[seen_gh:]
                                 if call["argv"][0] == "api" and call["token"] == "unset"]
                    self.assertEqual(bool(looked_up), not with_login, gh)
                    expected = self.expected_argv(world, step, quiet)
                    calls = self.h.git_calls()[seen_git:]
                    if expected is not None:
                        ran = [call for call in calls if call["argv"] == expected]
                        self.assertEqual(len(ran), 1, "%s not among %s" % (expected, [c["argv"] for c in calls]))
                        self.assertEqual(ran[0]["token"], TOKENS[LOGIN])
                        self.assertEqual(ran[0]["prompt"], "0")
                        self.assertEqual(ran[0]["ssh"], "set")
                        self.assertEqual(Path(ran[0]["cwd"]).resolve(), world.repo.resolve())
                    for call in calls:
                        if call["argv"][0] in READS:
                            self.assertEqual(call["token"], "unset", "the token reached a read of sw: %s" % call)
                    if step == "fetch-main" and world.kind == "git":
                        self.assertEqual((doc["ref"], doc["commit"]), ("origin/main", arranged), doc)
                    if step == "push" and world.kind != "gitbutler":
                        self.assertIn("refs/heads/feat/a", world.origin_refs())
                    if step == "pull" and world.kind == "git":
                        self.assertEqual(world.real(world.repo, "rev-parse", "HEAD"), arranged)

    # ---- tests ------------------------------------------------------------------------------------------------------------

    def test_fenced_push_runs_in_process(self):
        world = self.git_world()
        done, _ = self.h.run("push", "--branch", "feat/a", "--login", LOGIN, repo=world.repo)
        self.assertEqual(done, {"ok": True, "backend": "git", "branch": "feat/a"})
        self.assertEqual(world.origin_refs()["refs/heads/feat/a"], world.real(world.repo, "rev-parse", "HEAD"))
        pushes = [call for call in self.h.git_calls() if call["argv"][:1] == ["push"]]
        self.assertEqual([call["argv"] for call in pushes], [["push", "-u", "origin", "HEAD"]])
        push = pushes[0]
        self.assertEqual((push["token"], push["prompt"], push["ssh"]), (TOKENS[LOGIN], "0", "set"))
        self.assertEqual(Path(push["cwd"]).resolve(), world.repo.resolve())

    def test_refused_fence_maps_to_fence_failed(self):
        for name in ("git", "jj", "gitbutler"):
            with self.subTest(name):
                self.h.sent.clear()
                self.h.git_log.unlink(missing_ok=True)
                world = getattr(self, name + "_world")()
                world.real(world.repo, "remote", "set-url", "--push", "origin", "https://tok@github.com/o/r.git")
                before = world.origin_refs()

                doc, _ = self.h.run("push", "--branch", "feat/a", "--login", LOGIN, repo=world.repo, expected=3)

                self.assertEqual(doc["error"], "fence_failed", doc)
                self.assertRegex(doc["message"], r"^as\.sh:", doc)
                self.assertIn("***", doc["message"])
                self.assertNotIn("tok@", doc["message"])
                self.assertEqual(world.origin_refs(), before, "a push ran")
                self.assertEqual([c for c in self.h.git_calls() if c["argv"][:1] == ["push"]], [])

    def test_login_resolved_in_process(self):
        world = self.git_world()
        doc, _ = self.h.run("fetch-main", repo=world.repo)
        self.assertTrue(doc["ok"], doc)
        self.assertEqual(doc["ref"], "origin/main")
        fetches = [call for call in self.h.git_calls() if call["argv"][:1] == ["fetch"]]
        self.assertEqual([call["token"] for call in fetches], [TOKENS[LOGIN]])
        self.assertEqual(Path(fetches[0]["cwd"]).resolve(), world.repo.resolve())
        users = [call for call in self.h.gh_calls() if call["argv"][0] == "api" and call["token"] == "unset"]
        self.assertEqual(len(users), 1, "the active account was looked up once, with no token")

    def test_no_gh_account_is_fence_failed(self):
        world = self.git_world()
        self.h.set_gh(user=None)
        doc, _ = self.h.run("fetch-main", repo=world.repo, expected=3)
        self.assertEqual(doc["error"], "fence_failed", doc)
        self.assertRegex(doc["message"], r"^as\.sh: no active gh account for github\.com", doc)
        self.assertEqual([c for c in self.h.git_calls() if c["argv"][:1] == ["fetch"]], [], "a fetch ran")

    def store_world(self):
        """A planning store with a local bare origin and no installed Specwright version; self.repo is its code checkout."""
        self.set_settings(self.repo, "main_branch: main\n")
        store = self.root / "store"
        self._init_git(store)
        origin = self.root / "store-origin.git"
        self.git(self.root, "init", "-q", "--bare", "-b", "main", str(origin))
        self.git(store, "remote", "add", "origin", origin.as_posix())
        self.assertEqual(self.git(store, "push", "-q", "-u", "origin", "main").returncode, 0)
        self.assertFalse((store / "openspec" / ".specwright" / "VERSION").exists(), "the store has no Specwright version")
        return World(self, "git", store, origin, {})

    def test_store_without_version_pulls(self):
        """A store call names the code checkout (--code), whose VERSION the entry check reads."""
        world = self.store_world()
        store = world.repo
        advanced = world.advance("store")
        self.h.set_gh(user="sh1ny")

        doc, _ = self.h.run("pull", "--branch", "main", "--login", "store-bot", repo=store, role="store", code=self.repo)
        self.assertTrue(doc["ok"], doc)

        self.assertEqual(self.git(store, "rev-parse", "HEAD").stdout.strip(), advanced)
        pulls = [call for call in self.h.git_calls() if call["argv"][:1] == ["pull"]]
        self.assertEqual([call["token"] for call in pulls], [TOKENS["store-bot"]])
        self.assertEqual(Path(pulls[0]["cwd"]).resolve(), store.resolve())

    def test_store_push_with_project_passes_check(self):
        """A store push started in the store, which has no VERSION, passes the entry check with --project <code checkout>."""
        world = self.store_world()
        store = world.repo
        self.git(store, "checkout", "-q", "-b", "feat/a")
        (store / "plan.txt").write_text("plan\n", encoding="utf-8")
        self.git(store, "add", "plan.txt")
        self.git(store, "commit", "-q", "-m", "docs: plan")
        self.h.set_gh(user="sh1ny")

        refused, _ = self.h.run("push", "--branch", "feat/a", "--login", "store-bot", repo=store, role="store", expected=1)
        self.assertEqual(refused["error"], "sw_mismatch", refused)
        self.assertEqual(self.h.git_calls(), [], "git ran before the entry check")

        doc, _ = self.h.run("push", "--branch", "feat/a", "--login", "store-bot", repo=store, role="store",
                            code=self.repo, project=self.repo)

        self.assertTrue(doc["ok"], doc)
        self.assertIn("refs/heads/feat/a", world.origin_refs())
        pushes = [call for call in self.h.git_calls() if call["argv"][:1] == ["push"]]
        self.assertEqual([call["token"] for call in pushes], [TOKENS["store-bot"]])

    def test_fenced_command_has_no_deadline(self):
        world = self.git_world()
        doc, _ = self.h.run("fetch-main", "--login", LOGIN, repo=world.repo,
                            env={"SWF_FETCH_EXIT": "124"}, expected=3)
        self.assertEqual(doc["error"], "git_network_error", doc)
        self.assertNotIn("deadline_exceeded", doc["message"])
        self.assertEqual(len([c for c in self.h.git_calls() if c["argv"][:1] == ["fetch"]]), 1)
        self.h.git_log.unlink()
        self.h.set_gh(user=LOGIN, lookup_exit="124")
        doc, _ = self.h.run("fetch-main", "--login", LOGIN, repo=world.repo, expected=3)
        self.assertEqual(doc["error"], "fence_failed", doc)
        self.assertIn("deadline_exceeded", doc["message"])
        self.assertEqual([c for c in self.h.git_calls() if c["argv"][:1] == ["fetch"]], [])

    def test_push_fences_effective_github_target_with_off_host_fetch(self):
        world = self.git_world()
        self.h.origin_url = "https://git.example.org/team/mirror.git"
        self.h.run("push", "--branch", "feat/a", "--login", LOGIN, repo=world.repo,
                   env={"SWF_PUSH_URLS": GITHUB})
        push, = [c for c in self.h.git_calls() if c["argv"][:1] == ["push"]]
        self.assertEqual(push["token"], TOKENS[LOGIN])
        self.assertIn("refs/heads/feat/a", world.origin_refs())

    def test_push_uses_ambient_credentials_for_off_host_push_urls(self):
        world = self.git_world()
        self.h.run("push", "--branch", "feat/a", repo=world.repo,
                   env={"SWF_PUSH_URLS": world.origin.as_posix(), "GH_TOKEN": "caller-token"})
        push, = [c for c in self.h.git_calls() if c["argv"][:1] == ["push"]]
        self.assertEqual(push["token"], "caller-token")
        self.assertEqual(self.h.gh_calls(), [])
        self.assertIn("refs/heads/feat/a", world.origin_refs())

    def test_mixed_effective_push_hosts_launch_nothing(self):
        world = self.git_world()
        before = world.origin_refs()
        doc, _ = self.h.run("push", "--branch", "feat/a", repo=world.repo, expected=3,
                            env={"SWF_PUSH_URLS": GITHUB + "\n" + world.origin.as_posix()})
        self.assertEqual(doc["error"], "mixed_push_transport", doc)
        self.assertEqual(self.h.gh_calls(), [])
        self.assertFalse([c for c in self.h.git_calls() if c["argv"][:1] == ["push"]])
        self.assertEqual(world.origin_refs(), before)

    def test_standalone_push_refuses_changed_effective_destination(self):
        world = self.git_world()
        another = self.root / "another.git"
        self.git(self.root, "init", "-q", "--bare", str(another))
        before = world.origin_refs()
        doc, _ = self.h.run("push", "--branch", "feat/a", "--login", LOGIN, repo=world.repo, expected=3,
                            env={"SWF_TEST_RETARGET_PUSH": another.as_posix()})
        self.assertEqual(doc["error"], "push_destination_changed", doc)
        self.assertEqual(world.origin_refs(), before)
        self.assertEqual(self.git(another, "for-each-ref").stdout, "")
        self.assertFalse(any(c["argv"][:1] == ["push"] for c in self.h.git_calls()))

    def test_standalone_fenced_push_refuses_indexed_routing_drift(self):
        world = self.git_world()
        self.h.origin_url = ""
        before = world.origin_refs()
        doc, _ = self.h.run("push", "--branch", "feat/a", "--login", LOGIN, repo=world.repo, expected=3, env={
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "remote.origin.pushurl",
            "GIT_CONFIG_VALUE_0": GITHUB,
        })
        self.assertIn("destinations changed", doc["message"])
        self.assertTrue(any("--user" in c["argv"] for c in self.h.gh_calls()))
        self.assertEqual(world.origin_refs(), before)
        self.assertFalse(any(c["argv"][:1] == ["push"] for c in self.h.git_calls()))

    def check_pull_environment(self, url, token):
        world = self.git_world()
        world.real(world.repo, "checkout", "main")
        world.real(world.repo, "remote", "rename", "origin", "tracking")
        advanced = world.advance("pull")
        self.h.run("pull", "--login", LOGIN, repo=world.repo, env={"SWF_UPSTREAM_URL": url})
        pull, = [c for c in self.h.git_calls() if c["argv"][:1] == ["pull"]]
        self.assertEqual(pull["argv"], ["pull", "--ff-only"])
        self.assertEqual(pull["token"], token)
        self.assertEqual(world.real(world.repo, "rev-parse", "HEAD"), advanced)
        self.assertEqual(bool(self.h.gh_calls()), token != "unset")

    def test_legacy_pull_fences_effective_upstream(self):
        self.h.origin_url = "https://git.example.org/team/unused.git"
        self.check_pull_environment(GITHUB, TOKENS[LOGIN])

    def test_legacy_pull_does_not_fence_off_host_upstream(self):
        self.check_pull_environment("https://git.example.org/team/app.git", "unset")

    def test_legacy_pull_refuses_upstream_drift_in_fenced_environment(self):
        world = self.git_world()
        self.git(world.repo, "checkout", "main")
        self.git(world.repo, "remote", "add", "tracking", str(world.origin))
        self.git(world.repo, "config", "branch.main.remote", "tracking")
        before = world.real(world.repo, "rev-parse", "HEAD")
        world.advance("pull")
        doc, _ = self.h.run("pull", "--login", LOGIN, repo=world.repo, expected=3, env={
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "branch.main.remote",
            "GIT_CONFIG_VALUE_0": "origin",
        })
        self.assertEqual(doc["error"], "fence_failed", doc)
        self.assertIn("pull upstream changed", doc["message"])
        self.assertEqual(world.real(world.repo, "rev-parse", "HEAD"), before)
        self.assertFalse(any(c["argv"][:1] == ["pull"] for c in self.h.git_calls()))

    def check_off_host_fetch_environment(self, extra, want):
        world = self.git_world()
        self.h.origin_url = "https://github.example.com/team/app.git"
        wanted = world.advance("fetch")
        doc, _ = self.h.run("fetch-main", repo=world.repo, env=extra)
        fetch, = [c for c in self.h.git_calls() if c["argv"][:1] == ["fetch"]]
        self.assertEqual([fetch[key] for key in ("host", "ent", "ent2")], want)
        self.assertEqual(self.h.gh_calls(), [])
        self.assertEqual(doc["commit"], wanted)

    def test_off_host_fetch_preserves_original_enterprise_environment(self):
        self.check_off_host_fetch_environment(
            {"GH_HOST": "github.example.com", "GH_ENTERPRISE_TOKEN": "caller", "GITHUB_ENTERPRISE_TOKEN": "other"},
            ["github.example.com", "caller", "other"])

    def test_off_host_fetch_keeps_absent_enterprise_environment(self):
        self.check_off_host_fetch_environment({}, ["unset", "unset", "unset"])

    def test_main_fetch_auth_uses_fetch_url_not_fork_push_url(self):
        world = self.git_world()
        wanted = world.advance("fetch")
        self.git(world.repo, "remote", "set-url", "--push", "origin", "https://github.com/fork/app.git")
        doc, _ = self.h.run("fetch-main", "--login", LOGIN, repo=world.repo)
        fetch, = [c for c in self.h.git_calls() if c["argv"][:1] == ["fetch"]]
        self.assertEqual((doc["commit"], fetch["token"]), (wanted, TOKENS[LOGIN]))

    def test_fenced_store_fetch_refuses_userinfo_with_empty_logins(self):
        world = self.store_world()
        self.h.origin_url = "https://private-userinfo@github.com/team/plans.git"
        doc, done = self.h.run("fetch-main", repo=world.repo, role="store", code=self.repo, expected=3)
        self.assertEqual(doc["error"], "fence_failed")
        self.assertNotIn(b"private-userinfo", done.stdout + done.stderr)
        self.assertIn("***", doc["message"])
        self.assertFalse(any(c["argv"][:1] == ["fetch"] for c in self.h.git_calls()))

    def check_ssh_refusal(self, operation, *options):
        world = self.git_world()
        ssh_url = "git@github.com:team/app.git"
        world.real(world.repo, "remote", "set-url", "origin", ssh_url)
        self.h.origin_url = ssh_url
        before = world.origin_refs()
        doc, _ = self.h.run(operation, *options, repo=world.repo, expected=3,
                            env={"GIT_SSH_COMMAND": "sh -c 'echo ambient-ssh-should-not-run >&2; exit 99'"})
        self.assertIn("SSH is disabled", doc["message"])
        self.assertNotIn("ambient-ssh-should-not-run", doc["message"])
        self.assertEqual(world.origin_refs(), before)

    def test_fenced_ssh_main_refresh_cannot_use_ambient_key(self):
        self.check_ssh_refusal("fetch-main")

    def test_github_ssh_still_refused_by_default_fenced_push(self):
        self.check_ssh_refusal("push", "--branch", "feat/a")

    def test_no_account_leaves_local_main_available(self):
        world = self.git_world()
        before = world.real(world.repo, "rev-parse", "main")
        self.h.set_gh(user=None)
        doc, _ = self.h.run("fetch-main", repo=world.repo, expected=3)
        self.assertEqual(doc["error"], "fence_failed")
        self.assertIn("gh auth login", doc["message"])
        self.assertFalse(any(c["argv"][:1] == ["fetch"] for c in self.h.git_calls()))
        self.assertEqual(world.real(world.repo, "rev-parse", "main"), before)

    def test_refused_pull_leaves_branch_and_refs_unchanged(self):
        world = self.git_world()
        world.real(world.repo, "checkout", "main")
        world.advance("pull")
        branch = world.real(world.repo, "symbolic-ref", "HEAD")
        refs = world.real(world.repo, "show-ref")
        self.h.set_gh(user=None)
        doc, _ = self.h.run("pull", repo=world.repo, expected=3)
        self.assertEqual(doc["error"], "fence_failed")
        self.assertFalse(any(c["argv"][:1] == ["pull"] for c in self.h.git_calls()))
        self.assertEqual((world.real(world.repo, "symbolic-ref", "HEAD"), world.real(world.repo, "show-ref")), (branch, refs))

    def test_non_github_remote_runs_unfenced(self):
        world = self.git_world()
        self.h.origin_url = ""
        done, _ = self.h.run("push", "--branch", "feat/a", repo=world.repo)
        self.assertEqual(done, {"ok": True, "backend": "git", "branch": "feat/a"})
        pushes = [call for call in self.h.git_calls() if call["argv"][:1] == ["push"]]
        self.assertEqual([call["argv"] for call in pushes], [["push", "-u", "origin", "HEAD"]])
        self.assertEqual((pushes[0]["token"], pushes[0]["ssh"]), ("unset", ""), "the caller's environment")
        self.assertEqual(self.h.gh_calls(), [], "no fence lookup")
        with self.subTest("a failure is git_network_error with exit 3"):
            self.git(world.repo, "remote", "set-url", "origin", (self.root / "missing.git").as_posix())
            (world.repo / "again.txt").write_text("again\n", encoding="utf-8")
            self.git(world.repo, "add", "again.txt")
            self.git(world.repo, "commit", "-q", "-m", "feat: again")
            failed, _ = self.h.run("push", "--branch", "feat/a", repo=world.repo, expected=3)
            self.assertEqual(failed["error"], "git_network_error", failed)
            self.assertEqual(self.h.gh_calls(), [])

    def test_retrofitted_vcs_paths_run_no_script_or_python(self):
        for name in ("git", "jj", "gitbutler"):
            with self.subTest(name):
                self.h.sent.clear()
                self.h.git_log.unlink(missing_ok=True)
                self.h.gh_log.unlink(missing_ok=True)
                self.run_steps(getattr(self, name + "_world")())

    def test_printed_plan_commands_are_not_launched(self):
        world = self.git_world()
        doc, _ = self.h.run("plan", "--operation", "pull", "--branch", "feat/a", "--login", LOGIN, repo=world.repo)
        (command,) = doc["commands"]
        # D4: the printed command is the running `sw` with `--project`, never the script
        self.assertIn(Path(swharness.require_sw()).name, command)
        self.assertIn(" --project ", command)
        self.assertIn(" vcs pull ", command)
        self.assertNotRegex(command, r"vcs\.sh")
        self.assertEqual(self.h.sent.recorded(), [])


if __name__ == "__main__":
    unittest.main()
