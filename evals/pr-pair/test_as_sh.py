"""as.sh scrubs inherited http extraHeaders for the repository it starts in only.

This is why a store push must run `as.sh` from inside the store (design D1): a
repository-local, URL-scoped Authorization header in the store would otherwise
authenticate the push as someone else. The test serves HTTP on localhost,
records the headers `git ls-remote` sends, and compares plain git, as.sh started
inside the store, and as.sh started in the code repo with `git -C <store>`.

Run: python -m unittest discover evals/pr-pair
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AS_SH = ROOT / "skills" / "specwright-pr" / "scripts" / "as.sh"
sys.path.insert(0, str(ROOT / "evals" / "git-workflow"))
import fixtures  # noqa: E402

LEAK = "X-Store-Secret: leaked-store-header"


class Recorder(BaseHTTPRequestHandler):
    seen = []

    def do_GET(self):
        Recorder.seen.append({k.lower(): v for k, v in self.headers.items()})
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class AsShHeaderScrub(unittest.TestCase):
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
        (self.tmp / "gh-state.json").write_text(
            json.dumps({"user": "sh1ny", "tokens": {"sh1ny": "tok-s", "KintsugiBot": "tok-k"}}), encoding="utf-8")
        self.code = self.repo("code")
        self.store = self.repo("store", header=True)

    def repo(self, name, header=False):
        d = self.tmp / name
        d.mkdir()
        self.git(d, "init", "-q", "-b", "main")
        self.git(d, "remote", "add", "origin", f"{self.base}o/{name}.git")
        if header:  # repository-local and URL-scoped: only the store has it
            self.git(d, "config", f"http.{self.base}.extraheader", LEAK)
        return d

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

    def test_control_plain_git_sends_the_store_header(self):
        seen = self.ls_remote(self.store, ["git", "ls-remote", "origin"])
        self.assertTrue(seen, "git made no request")
        self.assertTrue(self.leaked(seen), "the fixture header must reach the server without as.sh")

    def test_scrubs_header_local_to_the_store(self):
        # planning_store.login unset, github.login = sh1ny: the store push is wrapped as sh1ny, from inside the store
        seen = self.ls_remote(self.store, ["bash", str(AS_SH), "sh1ny", "git", "ls-remote", "origin"])
        self.assertTrue(seen, "git made no request through as.sh")
        self.assertFalse(self.leaked(seen), f"as.sh started in the store must scrub its local header: {seen}")

    def test_header_survives_when_as_sh_starts_outside_the_store(self):
        # the D1 requirement in reverse: as.sh in the code repo cannot fence a `git -C <store>` command
        seen = self.ls_remote(self.code, ["bash", str(AS_SH), "sh1ny", "git", "-C", str(self.store), "ls-remote", "origin"])
        self.assertTrue(seen, "git made no request")
        self.assertTrue(self.leaked(seen), "as.sh only scrubs the repository it starts in")


if __name__ == "__main__":
    unittest.main()
