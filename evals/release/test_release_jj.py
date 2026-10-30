"""release.sh on a colocated jj repo (real jj): publish keeps the annotated tag as its one Git write, names the GitHub base
branch by `--base` when the main ref it reads is a fetched commit, and moves no bookmark.

Run: python -m unittest test_release_jj   (from evals/release)
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = Path(os.environ.get("RELEASE_SH") or ROOT / "skills" / "specwright-release" / "scripts" / "release.sh")
sys.path.insert(0, str(ROOT / "evals" / "vcs"))
import gitlog  # noqa: E402
import jjenv  # noqa: E402

_spec = importlib.util.spec_from_file_location("release_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

CODE_SLUG = "acme/code"
TAG = "v0.5.0"
GH_SCRIPT = '#!/bin/sh\nexec "{}" "{}" "$@"\n'


class JjRelease(unittest.TestCase):
    """A code repo at 0.5.0 (release commit `self.rc`), origin a GitHub-form URL over a local bare repo, then made a
    colocated jj repo. `gh` is the fake from evals/fakes/gh.py."""

    maxDiff = None

    def setUp(self):
        self.jj = jjenv.require_jj()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, self.tmp)
        (self.tmp / "bin").mkdir()
        gh = self.tmp / "bin" / "gh"
        gh.write_text(GH_SCRIPT.format(Path(sys.executable).resolve().as_posix(), (ROOT / "evals" / "fakes" / "gh.py").resolve().as_posix()),
                      encoding="utf-8", newline="\n")
        gh.chmod(0o755)
        self.state = {"user": "KintsugiBot", "tokens": {"KintsugiBot": "tok"}, "repos": {CODE_SLUG: {"pulls": [], "releases": {}}}}
        self.gh_state, self.gh_log = self.tmp / "gh-state.json", self.tmp / "gh-log.jsonl"
        self.trace = self.tmp / "git-trace.jsonl"
        self.work = fx.make_repo(self.tmp, version="0.4.0")
        url = f"https://github.com/{CODE_SLUG}.git"
        self.bare = self.tmp / "origin.git"
        fx.git(self.work, "config", "remote.origin.url", url)
        fx.git(self.work, "config", f"url.{self.bare.as_posix()}.insteadOf", url)
        fx.push(self.work)
        self.base = fx.git(self.work, "rev-parse", "HEAD")
        self.rc = fx.squash_merge(self.work, "add-x", "0.5.0", 7)

    def to_jj(self):
        r = subprocess.run([self.jj, "git", "init", "--colocate"], cwd=self.work, env=self.env(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def env(self):
        e = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST")}
        e.update({"PATH": str(self.tmp / "bin") + os.pathsep + e.get("PATH", ""), "FAKE_GH_STATE": str(self.gh_state),
                  "FAKE_GH_LOG": str(self.gh_log), "GIT_TRACE2_EVENT": str(self.trace),
                  "JJ_USER": jjenv.FIXTURE_NAME, "JJ_EMAIL": jjenv.FIXTURE_EMAIL})
        return e

    def release(self, *args):
        self.gh_state.write_text(json.dumps(self.state), encoding="utf-8")
        r = subprocess.run(["bash", str(SCRIPT), *args], cwd=self.work, capture_output=True, text=True, encoding="utf-8", env=self.env())
        try:
            doc = json.loads(r.stdout)
        except ValueError:
            doc = None
        return r.returncode, doc, r.stdout + r.stderr

    def gh_calls(self):
        if not self.gh_log.exists():
            return []
        return [json.loads(line) for line in self.gh_log.read_text(encoding="utf-8").splitlines()]

    def git_calls(self):
        """Every git process of the run (release.sh's and its children's), from GIT_TRACE2_EVENT, with gitlog's write class."""
        calls = []
        if self.trace.exists():
            for line in self.trace.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("event") == "start" and len(ev.get("argv", [])) > 1:
                    calls.append({"argv": ev["argv"][1:], **gitlog.classify(ev["argv"][1:])})
        return calls

    def repo_state(self):
        return {"refs": fx.git(self.work, "for-each-ref"), "origin": fx.git(self.bare, "for-each-ref"),
                "head": fx.git(self.work, "rev-parse", "HEAD"), "files": fx.snapshot(self.work),
                "bookmarks": subprocess.run([self.jj, "bookmark", "list", "--all-remotes", "--ignore-working-copy"], cwd=self.work,
                                            env=self.env(), capture_output=True, text=True).stdout}

    def assert_writes_only_tag(self, calls, tag=TAG):
        for c in calls:
            if c["write"]:
                names_tag = c["exception"] == "annotated release tag" or any(f"refs/tags/{tag}" in a for a in c["argv"])
                self.assertTrue(names_tag, f"a Git write that is not the release tag: {c['argv']}")


class TestPublishJj(JjRelease):
    def test_publish_jj_base_by_name_no_bookmark_moves(self):
        """Local main is behind origin's: the skill reads the fetched commit (`--main <sha>`) and names the base branch."""
        fx.push(self.work)  # origin's main holds the release commit
        fx.git(self.work, "reset", "-q", "--hard", self.base)  # local main is behind it
        self.to_jj()
        store = fx.make_store(self.tmp, [("add-x", "Store reason for x.", False)])
        store_main = fx.git(store, "rev-parse", "HEAD")
        self.state["repos"][CODE_SLUG]["pulls"].append({
            "number": 7, "state": "closed", "merged_at": "2026-10-12T00:00:00Z", "merge_commit_sha": self.rc,
            "html_url": f"https://github.com/{CODE_SLUG}/pull/7",
            "head": {"ref": "feat/add-x", "label": "acme:feat/add-x", "repo": {"full_name": CODE_SLUG}}, "base": {"ref": "main"}})
        before = self.repo_state()
        code, doc, raw = self.release("publish", "--version", "0.5.0", "--main", self.rc, "--store", str(store),
                                      "--store-main", store_main, "--base", "main")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["store"]["main"], store_main, raw)
        api = [c for c in self.gh_calls() if c["argv"][0] == "api"]
        self.assertEqual(len(api), 1, api)
        self.assertTrue(any(a.startswith(f"repos/{CODE_SLUG}/pulls?state=closed&base=main&") for a in api[0]["argv"]), api)
        after = self.repo_state()
        for key in ("bookmarks", "head", "files"):
            self.assertEqual(after[key], before[key], key)
        self.assertEqual(set(before["refs"].splitlines()) - set(after["refs"].splitlines()), set())
        added = set(after["refs"].splitlines()) - set(before["refs"].splitlines())
        self.assertTrue(all(line.endswith(f"refs/tags/{TAG}") for line in added), added)  # only the tag was written
        self.assert_writes_only_tag(self.git_calls())

    def test_publish_jj_only_tag_writes(self):
        self.to_jj()
        before = self.repo_state()
        code, doc, raw = self.release("publish", "--version", "0.5.0")
        self.assertEqual(code, 0, raw)
        self.assertEqual((doc["tag_local"], doc["tag_remote"]), ("created", "pushed"), raw)
        self.assertEqual(fx.git(self.bare, "cat-file", "-t", TAG), "tag")
        self.assertEqual(fx.git(self.bare, "rev-parse", f"{TAG}^{{commit}}"), self.rc)
        self.assertTrue(any(c["write"] for c in self.git_calls()), "no git write seen: the trace did not run")
        self.assert_writes_only_tag(self.git_calls())
        after = self.repo_state()
        self.assertEqual(after["head"], before["head"])
        self.assertEqual(after["files"], before["files"])
        self.assertEqual(after["bookmarks"], before["bookmarks"])
        changed = set(after["refs"].splitlines()) ^ set(before["refs"].splitlines())
        self.assertTrue(all(f"refs/tags/{TAG}" in line for line in changed), changed)
        self.assertEqual(sorted(l.split()[-1] for l in set(after["origin"].splitlines()) - set(before["origin"].splitlines())),
                         [f"refs/tags/{TAG}"])

    def test_publish_jj_tag_elsewhere_exit_1(self):
        fx.git(self.work, "tag", "-a", TAG, "-m", "elsewhere", self.base)  # v0.5.0 at another commit
        self.to_jj()
        before = self.repo_state()
        code, doc, raw = self.release("publish", "--version", "0.5.0")
        self.assertEqual(code, 1, raw)
        self.assertEqual(doc["error"], "tag_conflict", raw)
        self.assertEqual(self.repo_state(), before)
        self.assertEqual([c for c in self.git_calls() if c["write"]], [])
        self.assertEqual([c for c in self.gh_calls() if c["argv"][:2] == ["release", "create"]], [])

    def test_publish_jj_tag_fetch_names_tag_only(self):
        """The tag exists on origin only: publish fetches `refs/tags/<tag>` and nothing else."""
        fx.git(self.work, "tag", "-a", TAG, "-m", "Seeded notes", self.rc)
        fx.git(self.work, "push", "-q", "origin", f"refs/tags/{TAG}:refs/tags/{TAG}")
        fx.git(self.work, "tag", "-d", TAG)
        self.to_jj()
        before = self.repo_state()
        code, doc, raw = self.release("publish", "--version", "0.5.0")
        self.assertEqual(code, 0, raw)
        self.assertEqual((doc["tag_local"], doc["tag_remote"]), ("fetched", "existing"), raw)
        fetches = [c["argv"] for c in self.git_calls() if c["action"] == "fetch"]
        self.assertEqual(len(fetches), 1, fetches)
        self.assertEqual(fetches[0][-2:], ["origin", f"refs/tags/{TAG}:refs/tags/{TAG}"])
        self.assert_writes_only_tag(self.git_calls())
        after = self.repo_state()
        self.assertEqual(after["bookmarks"], before["bookmarks"])
        self.assertEqual(after["head"], before["head"])


if __name__ == "__main__":
    unittest.main()
