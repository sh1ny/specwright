"""as.sh: header scrub, the run login (--resolve), github.com-only host variables, and credential URLs.

Header scrub: as.sh scrubs inherited http extraHeaders for the repository it starts in only.
This is why a store push must run `as.sh` from inside the store (design D1): a
repository-local, URL-scoped Authorization header in the store would otherwise
authenticate the push as someone else. The test serves HTTP on localhost,
records the headers `git ls-remote` sends, and compares plain git, as.sh started
inside the store, and as.sh started in the code repo with `git -C <store>`.

Identity, host and URL tests (change default-identity-fencing, D1-D3) run as.sh against the fake gh. Requests to
https://github.com go through `http.proxy` to the local recorder, so a request that was not refused shows up as a CONNECT.

Run: python -m unittest discover evals/pr-pair
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AS_SH = ROOT / "skills" / "specwright-pr" / "scripts" / "as.sh"
sys.path.insert(0, str(ROOT / "evals" / "git-workflow"))
import fixtures  # noqa: E402

sys.path.append(str(ROOT / "evals"))
import fixturecache  # noqa: E402  per-process cache: the empty repo is built once and copied



def fixtures_kill(pid_file):
    """Stop a hung fake gh a test started, by the PID it wrote. Never by name."""
    try:
        pid = int(Path(pid_file).read_text())
    except (OSError, ValueError):
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


LEAK = "X-Store-Secret: leaked-store-header"
SECRET = "ghp_SECRETtoken123"


class Recorder(BaseHTTPRequestHandler):
    seen = []

    def do_GET(self):
        Recorder.seen.append({k.lower(): v for k, v in self.headers.items()})
        self.send_response(404)
        self.end_headers()

    def do_CONNECT(self):  # an https request sent through http.proxy = this server
        Recorder.seen.append({"method": "CONNECT", "path": self.path})
        self.send_response(502)
        self.end_headers()

    def log_message(self, *args):
        pass


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class AsShCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fixtures.rmtree, self.tmp)
        Recorder.seen = []
        self.server = HTTPServer(("127.0.0.1", 0), Recorder)
        self.base = f"http://127.0.0.1:{self.server.server_port}/"
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        # the fake gh answers `auth token`, `auth token --help` and `api user` for as.sh
        (self.tmp / "bin").mkdir()
        fixtures.install_fake_gh(self.tmp)
        self.state(user="sh1ny", tokens={"sh1ny": "tok-s", "KintsugiBot": "tok-k"})
        self.code = self.repo("code")
        self.store = self.repo("store", header=True)

    def state(self, **st):
        (self.tmp / "gh-state.json").write_text(json.dumps(st), encoding="utf-8")

    def gh_calls(self):
        p = self.tmp / "gh-log.jsonl"
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []

    def repo(self, name, header=False):
        d = self.tmp / name
        fixturecache.copy(("as-sh.repo",), self._init_repo, d)  # the remote URL names this test's server port: added after the copy
        self.git(d, "remote", "add", "origin", f"{self.base}o/{name}.git")
        if header:  # repository-local and URL-scoped: only the store has it
            self.git(d, "config", f"http.{self.base}.extraheader", LEAK)
        return d

    @staticmethod
    def _init_repo(dest):
        dest.mkdir()
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}  # as every git call of these tests
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dest, check=True, capture_output=True, text=True, env=env)

    def env(self):
        e = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO")}
        e.update({"PATH": str(self.tmp / "bin") + os.pathsep + e.get("PATH", ""),
                  "FAKE_GH_STATE": str(self.tmp / "gh-state.json"), "FAKE_GH_LOG": str(self.tmp / "gh-log.jsonl"),
                  "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
                  "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"})
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
            e.pop(k, None)
        return e

    def git(self, cwd, *args):
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=self.env())

    def ls_remote(self, cwd, argv):
        """Run `argv` (git ls-remote ...) from `cwd`; return the headers the server saw."""
        Recorder.seen = []
        subprocess.run(argv, cwd=cwd, capture_output=True, text=True, env=self.env(), timeout=60)
        return Recorder.seen

    def leaked(self, seen):
        return any("x-store-secret" in h for h in seen)

    def as_sh(self, cwd, *args, env=None, stdin=None):
        """Run `bash as.sh <args>` from `cwd`; the recorder is cleared first."""
        Recorder.seen = []
        e = self.env()
        e.update(env or {})
        return subprocess.run(["bash", str(AS_SH), *args], cwd=cwd, capture_output=True, text=True, env=e, input=stdin, timeout=60)


class AsShHeaderScrub(AsShCase):
    def test_control_plain_git_sends_the_store_header(self):
        seen = self.ls_remote(self.store, ["git", "ls-remote", "origin"])
        self.assertTrue(seen, "git made no request")
        self.assertTrue(self.leaked(seen), "the fixture header must reach the server without as.sh")

    def test_scrubs_header_local_to_the_store(self):
        # planning_store.login unset, github.login = sh1ny: the store push is wrapped as sh1ny, from inside the store
        seen = self.ls_remote(self.store, ["bash", str(AS_SH), "sh1ny", "git", "ls-remote", "origin"])
        self.assertTrue(seen, "git made no request through as.sh")
        self.assertFalse(self.leaked(seen), f"as.sh started in the store must scrub its local header: {seen}")

    def test_git_dash_c_into_the_store_refused(self):
        # as.sh in the code repo cannot fence a `git -C <store>` command (it scrubs only the repository it starts in),
        # so it refuses it: no request, so the store's header is never sent (PR #82)
        seen = self.ls_remote(self.code, ["bash", str(AS_SH), "sh1ny", "git", "-C", str(self.store), "ls-remote", "origin"])
        self.assertFalse(seen, f"as.sh must refuse a git command pointed at another repository: {seen}")


class AsShIdentity(AsShCase):
    """The run login (D1): --resolve, the login's own token, refusals."""

    def marker_cmd(self):
        return ["bash", "-c", f"touch '{(self.tmp / 'ran').as_posix()}'"]

    def test_configured_login_pins_its_token_not_the_active_one(self):
        r = self.as_sh(self.code, "KintsugiBot", "gh", "api", "user", "--jq", ".login")  # the active account is sh1ny
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "KintsugiBot"), r.stderr)
        api = [c for c in self.gh_calls() if c["argv"][0] == "api"]
        self.assertTrue(api)
        self.assertEqual({c["env"]["GH_TOKEN"] for c in api}, {"tok-k"}, "every gh call authenticates with the run login's token")

    def test_token_for_other_login_exits_3_command_not_run(self):
        self.state(user="sh1ny", tokens={"sh1ny": "tok-s", "KintsugiBot": "tok-s"})  # KintsugiBot's token is sh1ny's
        r = self.as_sh(self.code, "KintsugiBot", *self.marker_cmd())
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("sh1ny", r.stderr)
        self.assertIn("KintsugiBot", r.stderr)
        self.assertFalse((self.tmp / "ran").exists(), "the command must not run")

    def test_resolve_prints_the_active_login_only(self):
        r = self.as_sh(self.code, "--resolve")
        self.assertEqual((r.returncode, r.stdout), (0, "sh1ny\n"), r.stderr)
        self.assertEqual(self.as_sh(self.code, "--resolve", "extra").returncode, 2)

    def test_resolved_login_survives_auth_switch(self):
        r = self.as_sh(self.code, "--resolve")
        self.assertEqual(r.stdout.strip(), "sh1ny", r.stderr)
        self.state(user="KintsugiBot", tokens={"sh1ny": "tok-s", "KintsugiBot": "tok-k"})  # another process: gh auth switch
        before = len(self.gh_calls())
        r = self.as_sh(self.code, "sh1ny", "gh", "api", "user", "--jq", ".login")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "sh1ny"), r.stderr)
        later = [c for c in self.gh_calls()[before:] if c["argv"][0] == "api"]
        self.assertTrue(later)
        self.assertEqual({c["env"]["GH_TOKEN"] for c in later}, {"tok-s"})

    def test_resolve_without_account_exits_3_message(self):
        self.state(tokens={})
        r = self.as_sh(self.code, "--resolve")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(r.stdout, "")
        for text in ("gh auth login", "github.login", "GH_TOKEN", "GITHUB_TOKEN"):
            self.assertIn(text, r.stderr)
        self.assertTrue(all(c["argv"][0] in ("auth", "api") and "repos" not in " ".join(c["argv"]) for c in self.gh_calls()),
                        "no GitHub call beyond the account lookup")

    def test_resolve_ignores_gh_token_env(self):
        self.state(user="sh1ny", tokens={"sh1ny": "tok-s", "env-bot": "tok-e"})
        r = self.as_sh(self.code, "--resolve", env={"GH_TOKEN": "tok-e", "GITHUB_TOKEN": "tok-e"})
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "sh1ny"), r.stderr)
        api = [c for c in self.gh_calls() if c["argv"][0] == "api"]
        self.assertTrue(api)
        self.assertEqual({c["env"]["GH_TOKEN"] for c in api}, {None}, "no call authenticates with the ambient token")
        self.assertEqual({c["env"]["GITHUB_TOKEN"] for c in api}, {None})

    def test_request_as_without_credential_exits_3(self):
        self.state(user="KintsugiBot", tokens={"KintsugiBot": "tok-k"})  # no token for sh1ny
        r = self.as_sh(self.code, "sh1ny", *self.marker_cmd())
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("sh1ny", r.stderr)
        self.assertFalse((self.tmp / "ran").exists())


class AsShHost(AsShCase):
    """Fenced calls target github.com only (D3)."""
    SHOW = ["bash", "-c", 'printf "%s|%s|%s" "${GH_HOST-unset}" "${GH_ENTERPRISE_TOKEN-unset}" "${GITHUB_ENTERPRISE_TOKEN-unset}"']

    def test_gh_host_and_enterprise_tokens_unset(self):
        env = {"GH_HOST": "enterprise.example", "GH_ENTERPRISE_TOKEN": "ent-tok", "GITHUB_ENTERPRISE_TOKEN": "ent-tok2"}
        r = self.as_sh(self.code, "KintsugiBot", "gh", "api", "repos/o/r/pulls", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)  # the fake serves github.com only
        calls = self.gh_calls()
        self.assertTrue(calls)
        for c in calls:
            self.assertEqual((c["env"]["GH_HOST"], c["env"]["GH_ENTERPRISE_TOKEN"], c["env"]["GITHUB_ENTERPRISE_TOKEN"]),
                             (None, None, None), c["argv"])
        r = self.as_sh(self.code, "KintsugiBot", *self.SHOW, env=env)
        self.assertEqual(r.stdout, "unset|unset|unset", r.stderr)
        r = self.as_sh(self.code, "--resolve", env=env)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "sh1ny"), r.stderr)

    def test_enterprise_vars_saved_but_not_in_fence(self):
        env = {"GH_HOST": "enterprise.example", "GH_ENTERPRISE_TOKEN": "ent-tok", "GITHUB_ENTERPRISE_TOKEN": "ent-tok2"}
        r = self.as_sh(self.code, "KintsugiBot", "gh", "api", "user", "--jq", ".login", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        for c in self.gh_calls():
            self.assertEqual((c["env"]["GH_HOST"], c["env"]["GH_ENTERPRISE_TOKEN"], c["env"]["GITHUB_ENTERPRISE_TOKEN"]),
                             (None, None, None), c["argv"])
        # a fenced git call (a shell alias) sees none of them, nor the token variables
        r = self.as_sh(self.code, "KintsugiBot", "git", "-c", "alias.envdump=!env", "envdump", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        names = {l.split("=", 1)[0] for l in r.stdout.splitlines()}
        for v in ("GH_HOST", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN"):
            self.assertNotIn(v, names)
        # the originals are kept for the unfenced restore
        r = self.as_sh(self.code, "KintsugiBot", "bash", "-c",
                       'printf "%s|%s|%s|%s|%s|%s" "$AS_SH_ORIG_SET" "$AS_SH_ORIG_GH_HOST" "$AS_SH_ORIG_GH_ENTERPRISE_TOKEN" '
                       '"$AS_SH_ORIG_GITHUB_ENTERPRISE_TOKEN" "${AS_SH_ORIG_GH_TOKEN-unset}" "${AS_SH_ORIG_GITHUB_TOKEN-unset}"',
                       env={**env, "GH_TOKEN": "amb", "GITHUB_TOKEN": "amb"})
        parts = r.stdout.split("|")
        self.assertEqual(parts[1:], ["enterprise.example", "ent-tok", "ent-tok2", "unset", "unset"], r.stdout + r.stderr)
        for v in ("GH_HOST", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN"):
            self.assertIn(v, parts[0].split())
        self.assertNotIn("GH_TOKEN", parts[0].split())

    def test_empty_gh_host_targets_github(self):
        r = self.as_sh(self.code, "KintsugiBot", "gh", "api", "user", "--jq", ".login", env={"GH_HOST": ""})
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "KintsugiBot"), r.stderr)
        self.assertTrue(all(c["env"]["GH_HOST"] is None for c in self.gh_calls()), "an empty GH_HOST is unset too")
        r = self.as_sh(self.code, "KintsugiBot", *self.SHOW, env={"GH_HOST": ""})
        self.assertEqual(r.stdout, "unset|unset|unset")


class AsShUrls(AsShCase):
    """Credentials in a github.com URL are refused (D2)."""

    def setUp(self):
        super().setUp()
        self.work = self.repo("work")
        self.git(self.work, "remote", "set-url", "origin", "https://github.com/o/r.git")
        self.git(self.work, "config", "http.proxy", self.base.rstrip("/"))

    def config(self, cwd):
        return subprocess.run(["git", "config", "--local", "--list"], cwd=cwd, capture_output=True, text=True, env=self.env()).stdout

    def refused(self, r, *words):
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(Recorder.seen, [], "no request may reach the server")
        self.assertNotIn(SECRET, r.stdout + r.stderr)
        self.assertIn("***", r.stderr)
        for w in words:
            self.assertIn(w, r.stderr)

    def test_control_url_reaches_the_server_without_the_check(self):
        self.git(self.work, "remote", "set-url", "origin", f"https://x-access-token:{SECRET}@github.com/o/r.git")
        Recorder.seen = []
        subprocess.run(["git", "fetch", "origin", "main"], cwd=self.work, capture_output=True, text=True, env=self.env(), timeout=60)
        self.assertTrue(Recorder.seen, "plain git must send the request, or the refusal tests prove nothing")

    def test_credential_fill_returns_verified_token(self):
        r = self.as_sh(self.work, "sh1ny", "git", "credential", "fill", stdin="protocol=https\nhost=github.com\n\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("username=x-access-token", r.stdout)
        self.assertIn("password=tok-s", r.stdout)

    def test_token_in_fetch_url_refused_no_request(self):
        self.git(self.work, "remote", "set-url", "origin", f"https://x-access-token:{SECRET}@github.com/o/r.git")
        before = self.config(self.work)
        r = self.as_sh(self.work, "sh1ny", "git", "fetch", "origin", "main")
        self.refused(r, "origin", "fetch", "https://***@github.com/o/r.git")
        self.assertEqual(self.config(self.work), before, "the remote is unchanged")

    def test_token_in_second_push_url_refused(self):
        self.git(self.work, "config", "--add", "remote.origin.pushurl", "https://github.com/o/r.git")
        self.git(self.work, "config", "--add", "remote.origin.pushurl", f"https://u:{SECRET}@github.com/o/r.git")
        before = self.config(self.work)
        r = self.as_sh(self.work, "sh1ny", "git", "push", "origin", "HEAD")
        self.refused(r, "origin", "push", "https://***@github.com/o/r.git")
        self.assertEqual(self.config(self.work), before)

    def test_insteadof_rule_with_token_refused(self):
        self.git(self.work, "config", f"url.https://u:{SECRET}@github.com/.insteadOf", "https://github.com/")
        before = self.config(self.work)
        r = self.as_sh(self.work, "sh1ny", "git", "fetch", "origin", "main")
        self.refused(r)
        self.assertEqual(self.config(self.work), before)

    def test_insteadof_rule_with_token_refused_without_a_matching_remote(self):
        self.git(self.work, "remote", "set-url", "origin", "https://git.example.com/o/r.git")
        self.git(self.work, "config", f"url.https://u:{SECRET}@github.com/.insteadOf", "https://github.com/")
        r = self.as_sh(self.work, "sh1ny", "git", "status")
        self.refused(r, "rewrite")

    def test_token_in_username_slot_refused_masked(self):
        self.git(self.work, "remote", "set-url", "origin", f"https://{SECRET}@github.com/o/r.git")
        r = self.as_sh(self.work, "sh1ny", "git", "fetch", "origin", "main")
        self.refused(r, "https://***@github.com/o/r.git")

    def test_bare_username_refused(self):
        self.git(self.work, "remote", "set-url", "origin", "https://someone@github.com/o/r.git")
        r = self.as_sh(self.work, "sh1ny", "git", "fetch", "origin", "main")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(Recorder.seen, [])
        self.assertIn("remove the userinfo", r.stderr)
        self.assertNotIn("someone", r.stderr)

    def test_git_selecting_another_repo_refused(self):
        # PR #82: the URL check scans the repo as.sh starts in, so git may not be pointed at another one
        other = self.repo("other")
        self.git(other, "remote", "set-url", "origin", f"https://x-access-token:{SECRET}@github.com/o/r.git")
        self.git(other, "config", "http.proxy", self.base.rstrip("/"))
        gitdir = str(Path(other) / ".git")
        for argv in (["-C", str(other), "fetch", "origin", "main"], [f"--git-dir={gitdir}", "fetch", "origin", "main"],
                     ["--git-dir", gitdir, "fetch", "origin", "main"], ["--work-tree", str(other), "fetch", "origin", "main"],
                     ["-c", "core.quotepath=false", "-C", str(other), "fetch", "origin", "main"]):
            Recorder.seen = []
            r = self.as_sh(self.work, "sh1ny", "git", *argv)
            self.assertEqual(r.returncode, 3, f"{argv}: {r.stderr}")
            self.assertEqual(Recorder.seen, [], f"{argv}: no request may reach the server")
            self.assertNotIn(SECRET, r.stdout + r.stderr)
            self.assertIn("inside", r.stderr, "the refusal says to run as.sh from inside the repository")
        # options after the subcommand are the subcommand's own, not a repository selection
        r = self.as_sh(self.work, "sh1ny", "git", "log", "-C", "-1")
        self.assertNotEqual(r.returncode, 3, r.stderr)

    def test_refusal_covers_commands_other_than_git(self):
        self.git(self.work, "remote", "set-url", "origin", f"https://{SECRET}@github.com/o/r.git")
        r = self.as_sh(self.work, "sh1ny", "gh", "api", "repos/o/r/pulls")
        self.refused(r)
        self.assertFalse([c for c in self.gh_calls() if "repos" in " ".join(c["argv"])], "the command did not run")

    def test_gitlab_token_rule_ignored(self):
        self.git(self.work, "config", f"url.https://oauth2:{SECRET}@gitlab.com/.insteadOf", "https://gitlab.com/")
        r = self.as_sh(self.work, "sh1ny", "gh", "api", "repos/o/r/pulls")
        self.assertEqual(r.returncode, 0, r.stderr)
        api = [c for c in self.gh_calls() if c["argv"][0] == "api"]
        self.assertEqual({c["env"]["GH_TOKEN"] for c in api}, {"tok-s"})
        r = self.as_sh(self.work, "sh1ny", "git", "fetch", "origin", "main")
        self.assertNotEqual(r.returncode, 3, r.stderr)
        self.assertTrue(Recorder.seen, "the fetch ran and reached the (proxy) server")

    def test_dash_c_url_with_userinfo_refused(self):
        r = self.as_sh(self.work, "sh1ny", "git", "-c", f"remote.origin.url=https://u:{SECRET}@github.com/o/r.git", "fetch", "origin", "main")
        self.refused(r, "argument")
        r = self.as_sh(self.work, "sh1ny", "git", "-c", f"url.https://u:{SECRET}@github.com/.insteadOf=https://github.com/",
                       "fetch", "origin", "main")
        self.refused(r, "argument")

    def test_url_argument_with_userinfo_refused(self):
        r = self.as_sh(self.work, "sh1ny", "git", "ls-remote", f"https://u:{SECRET}@github.com/o/r.git")
        self.refused(r, "argument")

    # ---- the trailing-dot host is github.com (fix-m2-gaps D4) ----
    def test_trailing_dot_token_in_fetch_url_refused(self):
        self.git(self.work, "remote", "set-url", "origin", f"https://x-access-token:{SECRET}@github.com./o/r.git")
        before = self.config(self.work)
        r = self.as_sh(self.work, "sh1ny", "git", "fetch", "origin", "main")
        self.refused(r, "origin", "fetch", "https://***@github.com./o/r.git")
        self.assertEqual(self.config(self.work), before, "the URL is not rewritten")

    def test_trailing_dot_argument_and_rewrite_refused(self):
        r = self.as_sh(self.work, "sh1ny", "git", "ls-remote", f"https://u:{SECRET}@GitHub.COM./o/r.git")
        self.refused(r, "argument")
        self.git(self.work, "remote", "set-url", "origin", "https://git.example.com/o/r.git")
        self.git(self.work, "config", f"url.https://u:{SECRET}@github.com./.insteadOf", "https://github.com/")
        r = self.as_sh(self.work, "sh1ny", "git", "status")
        self.refused(r, "rewrite")
        r = self.as_sh(self.work, "sh1ny", "git", "-c", f"url.https://u:{SECRET}@GitHub.COM./.insteadOf=https://github.com/",
                       "status")
        self.refused(r, "argument")

    def test_credential_fill_trailing_dot_returns_verified_token(self):
        for host in ("github.com.", "GitHub.COM."):
            r = self.as_sh(self.work, "sh1ny", "git", "credential", "fill", stdin=f"protocol=https\nhost={host}\n\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("username=x-access-token", r.stdout)
            self.assertIn("password=tok-s", r.stdout)

    def test_credential_fill_with_an_explicit_port_returns_verified_token(self):
        # git passes the port in host= (https://github.com.:443/o/r.git -> host=github.com.:443); the URL checks accept it as GitHub
        for host in ("github.com:443", "github.com.:443", "GitHub.COM.:443"):
            r = self.as_sh(self.work, "sh1ny", "git", "credential", "fill", stdin=f"protocol=https\nhost={host}\n\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("username=x-access-token", r.stdout, host)
            self.assertIn("password=tok-s", r.stdout, host)

    def test_lookalike_host_not_github(self):
        for host in ("github.com.example.org", "github.com.example.org:443"):
            r = self.as_sh(self.work, "sh1ny", "git", "credential", "fill", stdin=f"protocol=https\nhost={host}\n\n")
            self.assertNotIn("tok-s", r.stdout + r.stderr, host)
            self.assertNotIn("x-access-token", r.stdout, host)
        self.git(self.work, "remote", "set-url", "origin", f"https://u:{SECRET}@github.com.example.org/o/r.git")
        r = self.as_sh(self.work, "sh1ny", "gh", "api", "user", "--jq", ".login")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "sh1ny"), r.stderr)

    def test_outside_a_work_tree_the_command_runs(self):
        r = self.as_sh(self.tmp, "sh1ny", "gh", "api", "user", "--jq", ".login")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "sh1ny"), r.stderr)


class Bounded(AsShCase):
    """bound-pr-scripts D1/D3: as.sh's own gh lookups run under a deadline; the fenced command does not."""

    DEADLINE = 2
    BOUND = DEADLINE + 10  # the spec: the deadline plus 10 s for process start and kill

    def marker_cmd(self):
        return ["bash", "-c", f"touch '{(self.tmp / 'ran').as_posix()}'"]

    def hang(self, match):
        pidf = self.tmp / "hang.pid"
        self.addCleanup(fixtures_kill, pidf)
        st = json.loads((self.tmp / "gh-state.json").read_text(encoding="utf-8"))
        st["hang"] = [{"match": match, "pid_file": str(pidf)}]
        self.state(**st)

    def timed(self, *args, env=None):
        """as.sh from the code repo; (CompletedProcess, seconds). Output goes to files, so a hung fake gh that outlives the
        run (the red step) cannot hold a pipe open; the run is stopped at 45 s."""
        e = {**self.env(), "SPECWRIGHT_NET_DEADLINE": str(self.DEADLINE), **(env or {})}
        out, err = self.tmp / "as.out", self.tmp / "as.err"
        t = time.time()
        with open(out, "wb") as fo, open(err, "wb") as fe:
            p = subprocess.Popen(["bash", str(AS_SH), *args], cwd=self.code, stdout=fo, stderr=fe, env=e)
            try:
                rc = p.wait(timeout=45)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True) if os.name == "nt" else p.kill()
                p.wait()
                rc = -9
        took = time.time() - t
        return subprocess.CompletedProcess(args, rc, out.read_text(errors="replace"), err.read_text(errors="replace")), took

    def test_token_lookup_hung_exits_3_named(self):
        self.hang(r"auth token --hostname")
        r, took = self.timed("KintsugiBot", *self.marker_cmd())
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("deadline_exceeded", r.stderr)
        self.assertIn("as.sh:", r.stderr)
        self.assertLess(took, self.BOUND)
        self.assertFalse((self.tmp / "ran").exists(), "the fenced command must not run")

    def test_resolve_token_lookup_hung_exits_3_named(self):
        self.hang(r"auth token --hostname")  # `api user` answers; the credential check never does
        r, took = self.timed("--resolve")
        self.assertEqual((r.returncode, r.stdout), (3, ""), r.stderr)
        self.assertIn("deadline_exceeded", r.stderr)
        self.assertLess(took, self.BOUND)

    def test_resolve_login_lookup_hung_exits_3_named(self):
        self.hang(r"api --hostname github.com user")
        r, took = self.timed("--resolve")
        self.assertEqual((r.returncode, r.stdout), (3, ""), r.stderr)
        self.assertIn("deadline_exceeded", r.stderr)
        self.assertLess(took, self.BOUND)

    def test_identity_check_hung_exits_3_named(self):
        self.hang(r"api --hostname github.com user")
        r, took = self.timed("KintsugiBot", *self.marker_cmd())
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("deadline_exceeded", r.stderr)
        self.assertLess(took, self.BOUND)
        self.assertFalse((self.tmp / "ran").exists())

    def test_help_probe_hung_exits_3_named(self):
        self.hang(r"auth token --help")
        r, took = self.timed("KintsugiBot", *self.marker_cmd())
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("deadline_exceeded", r.stderr)
        self.assertLess(took, self.BOUND)
        self.assertFalse((self.tmp / "ran").exists())

    def test_token_lookup_leaves_no_file_in_temp(self):
        # secret mode: the token never reaches a file, so a fresh TEMP stays empty during the lookups
        temp = self.tmp / "fresh-temp"
        temp.mkdir()
        probe = f"ls -A '{temp.as_posix()}' > '{(self.tmp / 'temp-listing').as_posix()}'"
        env = {"TEMP": str(temp), "TMP": str(temp), "TMPDIR": str(temp)}
        r, _ = self.timed("KintsugiBot", "bash", "-c", probe, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.tmp / "temp-listing").read_text(), "", "a lookup left a file under TEMP while it ran")
        self.assertEqual(list(temp.iterdir()), [])

    def test_fenced_command_is_not_bounded(self):
        r, took = self.timed("KintsugiBot", "bash", "-c", "sleep 4; echo done", env={"SPECWRIGHT_NET_DEADLINE": "1"})
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "done"), r.stderr)
        self.assertGreaterEqual(took, 4)


if __name__ == "__main__":
    unittest.main()
