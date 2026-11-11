"""sw vcs fences identity in its own process (native-cli-internal-calls D1, D2, D8).

Every test hands the built `sw` (SPECWRIGHT_SW) the scripts-directory handoff directly (`sw vcs --args-stdin`, the stdin
records `vcs.sh` writes) and a directory holding recording sentinels for `as.sh`, `vcs.sh`, `pr-pair.sh` and `sw-path.sh`;
failing recording `python` and `python3` are first on PATH. A sentinel that recorded a run, or an interpreter that ran,
fails the test before anything else is read. The fake `gh` and a `git` shim that answers `git remote get-url origin` with a
github.com URL (every real fetch and push still goes to the local bare origin) stand in for GitHub.

Only `test_store_without_version_pulls` goes through the shipped `vcs.sh`: it needs the real shim to start from a store that
has no installed Specwright version.

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
from vcs_test_support import ROOT, SCRIPTS, bash_path_env, bash_run

sys.path.append(str(ROOT / "evals" / "cli"))
import swharness  # noqa: E402

GITHUB = "https://github.com/o/r.git"
LOGIN = "KintsugiBot"
TOKENS = {LOGIN: "tok-k", "store-bot": "tok-store", "sh1ny": "tok-sh1ny"}

# Answers `git remote get-url origin` with $SWF_ORIGIN_URL when that is set, and logs every other call: where it ran, the
# token and transport variables it saw, and its arguments (separated by 0x1f, so their bytes are exact). $SWF_SLEEP slows a fetch.
GIT_SHIM = r"""#!/bin/sh
if [ "$*" = "remote get-url origin" ] && [ -n "${SWF_ORIGIN_URL:-}" ]; then printf '%s\n' "$SWF_ORIGIN_URL"; exit 0; fi
here=$PWD
if command -v cygpath >/dev/null 2>&1; then here=$(cygpath -m "$PWD"); fi
{
  printf 'cwd=%s|token=%s|prompt=%s|ssh=%s|args=' "$here" "${GH_TOKEN-unset}" "${GIT_TERMINAL_PROMPT-unset}" "${GIT_SSH_COMMAND:+set}"
  for a in "$@"; do printf '%s\037' "$a"; done
  printf '\n'
} >> "$SWF_GIT_LOG"
if [ -n "${SWF_SLEEP:-}" ] && [ "$1" = fetch ]; then sleep "$SWF_SLEEP"; fi
exec "$SWF_REAL_GIT" "$@"
"""
# A `gh` that needs no Python (a failing `python` is first on PATH, and a Python start is slow): it logs the token it saw and its
# arguments, answers `auth token --help` and `auth token --user <login>` (tokens: $SWF_GH_TOKENS, `login=token` pairs;
# $SWF_GH_SLEEP slows the token lookup) and `api user` (the login of GH_TOKEN when set, else $SWF_GH_USER; none: no account).
GH_SHIM = r"""#!/bin/sh
{ printf 'token=%s|argv=' "${GH_TOKEN-unset}"; for a in "$@"; do printf '%s\037' "$a"; done; printf '\n'; } >> "$SWF_GH_LOG"
if [ "$1 $2 $3" = "auth token --help" ]; then echo "--user"; exit 0; fi
if [ "$1 $2" = "auth token" ]; then
  user=; prev=
  for a in "$@"; do if [ "$prev" = --user ]; then user=$a; fi; prev=$a; done
  if [ -n "${SWF_GH_SLEEP:-}" ]; then sleep "$SWF_GH_SLEEP"; fi
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
        self.sent = sentinels.install(root / "scripts", root / "pybin", root / "sentinels.log")
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

    def set_gh(self, user=None, sleep=None):
        """The active gh account (none for None) and how long a token lookup takes."""
        self.gh_user, self.gh_sleep = user, sleep

    def env(self, extra=None):
        env = swharness.fixture_env()
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST"):
            env.pop(name, None)
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
        env.update({key: value for key, value in self.world_env.items() if key != "PATH"})
        env.update(self.sent.env)
        env.update({"SWF_GH_LOG": posix(self.gh_log), "SWF_GH_USER": self.gh_user or "", "SWF_GH_SLEEP": self.gh_sleep or "",
                    "SWF_GH_TOKENS": " ".join("%s=%s" % pair for pair in TOKENS.items()),
                    "SWF_GIT_LOG": posix(self.git_log), "SWF_REAL_GIT": jjenv.real_git(),
                    "SWF_ORIGIN_URL": self.origin_url or ""})
        env.update(extra or {})
        env["PATH"] = bash_path_env(self.sent.bin, extra_path=(self.tools,))["PATH"]
        return env

    def run(self, command, *options, repo, role="code", code=None, env=None, expected=0):
        """`sw vcs <command>` with the handoff records; returns (document, process). The sentinels are read first."""
        bash = jjenv.find_bash()
        args = [posix(self.sent.scripts), bash, command, "--repo", str(repo), "--role", role]
        if code is not None:
            args += ["--code", str(code)]
        args += list(map(str, options))
        shell_env = self.env(env)
        shell_env["SWF_SEARCH"] = shell_env["PATH"]
        shell_env["SWF_SW"] = swharness.require_sw()
        done = subprocess.run([bash, "-c", 'export PATH="$SWF_SEARCH"; exec "$SWF_SW" vcs --args-stdin'],
                              input=b"".join(arg.encode("utf-8", "surrogateescape") + b"\0" for arg in args),
                              cwd=str(repo), env=shell_env, capture_output=True, timeout=180)
        out = done.stdout.decode("utf-8", "surrogateescape")
        err = done.stderr.decode("utf-8", "surrogateescape")
        self.case.assertEqual(self.sent.recorded(), [],
                              "a shipped script or a Python interpreter ran: %s %s" % (out, err))
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
                self.assertTrue(doc["message"].startswith("as.sh:"), doc)
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
        self.assertTrue(doc["message"].startswith("as.sh: no active gh account for github.com"), doc)
        self.assertEqual([c for c in self.h.git_calls() if c["argv"][:1] == ["fetch"]], [], "a fetch ran")

    def test_store_without_version_pulls(self):
        code = self.repo
        self.set_settings(code, "main_branch: main\n")
        store = self.root / "store"
        self._init_git(store)
        origin = self.root / "store-origin.git"
        self.git(self.root, "init", "-q", "--bare", "-b", "main", str(origin))
        self.git(store, "remote", "add", "origin", origin.as_posix())
        self.assertEqual(self.git(store, "push", "-q", "-u", "origin", "main").returncode, 0)
        world = World(self, "git", store, origin, {})
        advanced = world.advance("store")
        self.assertFalse((store / "openspec" / ".specwright" / "VERSION").exists(), "the store has no Specwright version")
        self.h.set_gh(user="sh1ny")

        done = bash_run([(SCRIPTS / "vcs.sh").as_posix(), "pull", "--repo", str(store), "--role", "store", "--code", str(code),
                         "--branch", "main", "--login", "store-bot"], cwd=store, env=self.h.env(), shim=self.h.tools,
                        stamp=False)

        doc = json.loads(done.stdout)
        self.assertNotEqual(doc.get("error"), "sw_missing", doc)
        self.assertEqual((done.returncode, doc.get("ok")), (0, True), doc)
        self.assertEqual(self.git(store, "rev-parse", "HEAD").stdout.strip(), advanced)
        pulls = [call for call in self.h.git_calls() if call["argv"][:1] == ["pull"]]
        self.assertEqual([call["token"] for call in pulls], [TOKENS["store-bot"]])
        self.assertEqual(Path(pulls[0]["cwd"]).resolve(), store.resolve())

    def test_fenced_command_has_no_deadline(self):
        world = self.git_world()
        deadline = {"SPECWRIGHT_NET_DEADLINE": "1"}
        with self.subTest("a fenced fetch that takes 3 seconds against a deadline of 1"):
            doc, _ = self.h.run("fetch-main", "--login", LOGIN, repo=world.repo, env={**deadline, "SWF_SLEEP": "3"})
            self.assertTrue(doc["ok"], doc)
            self.assertNotEqual(doc.get("error"), "deadline_exceeded")
        with self.subTest("the fence's own gh lookups keep the deadline"):
            self.h.git_log.unlink(missing_ok=True)
            self.h.set_gh(user=LOGIN, sleep="3")
            doc, _ = self.h.run("fetch-main", "--login", LOGIN, repo=world.repo, env=deadline, expected=3)
            self.assertEqual(doc["error"], "fence_failed", doc)
            self.assertIn("deadline_exceeded", doc["message"])
            self.assertTrue(doc["message"].startswith("as.sh:"), doc)
            self.assertEqual([c for c in self.h.git_calls() if c["argv"][:1] == ["fetch"]], [], "a fetch ran")

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
        self.assertIn(posix(self.h.sent.scripts) + "/vcs.sh", command)
        self.assertEqual(self.h.sent.recorded(), [])


if __name__ == "__main__":
    unittest.main()
