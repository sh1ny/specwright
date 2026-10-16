"""Script tests for skills/specwright-release/scripts/release.sh.

Every test runs the real script against a real git repo built by fixtures.py. One JSON
document on stdout per call; exit 0 = done, 1 = stop (the JSON has "error" and "message"),
2 = usage, 3 = a git or gh network call failed.

Run: python -m unittest discover evals/release
"""
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = Path(os.environ.get("RELEASE_SH") or ROOT / "skills" / "specwright-release" / "scripts" / "release.sh")

_spec = importlib.util.spec_from_file_location("release_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

VERSION_FILES = ["VERSION", "README.md", "skills/specwright-pr/SKILL.md", "skills/specwright-debug/SKILL.md"]


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, self.tmp)

    def repo(self, **kw):
        self.work = fx.make_repo(self.tmp, **kw)
        return self.work

    def release(self, *args, cwd=None, env=None):
        """Run release.sh; returns (exit code, parsed JSON, raw stdout)."""
        r = subprocess.run(["bash", str(SCRIPT), *args], cwd=cwd or self.work, capture_output=True, text=True,
                           encoding="utf-8", env=env)
        try:
            doc = json.loads(r.stdout)
        except ValueError:
            doc = None
        return r.returncode, doc, r.stdout + r.stderr

    def assertStops(self, out, *needles):
        code, doc, raw = out
        self.assertEqual(code, 1, raw)
        self.assertIs(doc["ok"], False, raw)
        self.assertIn("error", doc)
        for n in needles:
            self.assertIn(n, doc["message"], raw)


class TestOptIn(Base):
    def test_enabled_runs(self):
        # enabled=true means check, status, publish and bump all get past the opt-in gate.
        self.repo()
        code, doc, raw = self.release("check")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")
        fx.squash_merge(self.work, "add-x", "0.5.0", 7)
        self.assertEqual(self.release("status", "--version", "0.5.0")[0], 0)
        code, doc, raw = self.release("publish", "--version", "0.5.0")  # origin is a plain path: no GitHub release
        self.assertEqual(code, 0, raw)
        self.assertEqual(fx.git(self.work, "cat-file", "-t", "v0.5.0"), "tag")
        self.assertEqual(self.release("bump", "--to", "0.6.0")[0], 0)

    def test_missing_block_refuses(self):
        self.repo(with_release_block=False)
        before = fx.snapshot(self.work)
        for args in (("bump", "--to", "0.5.0"), ("publish", "--version", "0.4.2"), ("check",)):
            self.assertStops(self.release(*args), "release.enabled")
        self.assertEqual(fx.snapshot(self.work), before)
        self.assertEqual(fx.git(self.work, "tag"), "")

    def test_disabled_refuses(self):
        self.repo(enabled=False)
        before = fx.snapshot(self.work)
        self.assertStops(self.release("bump", "--to", "0.5.0"), "release.enabled")
        self.assertEqual(fx.snapshot(self.work), before)

    def test_rebase_method_refused(self):
        self.repo(merge_method="rebase")
        before = fx.snapshot(self.work)
        for args in (("bump", "--to", "0.5.0"), ("publish", "--version", "0.4.2")):
            self.assertStops(self.release(*args), "release.enabled", "pr.merge_method")
        self.assertEqual(fx.snapshot(self.work), before)
        self.assertEqual(fx.git(self.work, "tag"), "")

    def test_usage_errors_exit_2(self):
        self.repo()
        self.assertEqual(self.release("nonsense")[0], 2)
        self.assertEqual(self.release("bump")[0], 2)


class TestCheck(Base):
    def test_all_agree(self):
        self.repo()
        code, doc, raw = self.release("check")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")
        self.assertEqual(sorted(doc["files"]), sorted(VERSION_FILES))

    def test_one_disagrees(self):
        self.repo()
        fx.write(self.work, "skills/specwright-debug/SKILL.md", fx.skill_text("specwright-debug", "0.4.1"))
        before = fx.snapshot(self.work)
        out = self.release("check")
        self.assertStops(out, "skills/specwright-debug/SKILL.md", "0.4.1", "0.4.2")
        self.assertEqual(fx.snapshot(self.work), before)

    def test_crlf_file_with_anchored_pattern(self):
        # A Windows checkout (core.autocrlf) gives VERSION CRLF line ends; `$` must still match, and bump keeps the CRLF.
        self.repo()
        with open(os.path.join(self.work, "VERSION"), "wb") as f:
            f.write(b"0.4.2\r\n")
        code, doc, raw = self.release("check")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")
        code, doc, raw = self.release("bump", "--to", "0.5.0")
        self.assertEqual(code, 0, raw)
        with open(os.path.join(self.work, "VERSION"), "rb") as f:
            self.assertEqual(f.read(), b"0.5.0\r\n")

    def test_zero_or_two_matches(self):
        self.repo()
        fx.write(self.work, "README.md", "# Demo\n\nno badge here\n")
        self.assertStops(self.release("check"), "README.md", fx.DEFAULT_VERSION_FILES["README.md"], "0")
        fx.write(self.work, "README.md", fx.readme_text("0.4.2") + fx.readme_text("0.4.2"))
        self.assertStops(self.release("check"), "README.md", fx.DEFAULT_VERSION_FILES["README.md"], "2")

    def test_status_reads_release_commit(self):
        # 0.4.1 was released when fewer SKILL.md files existed; HEAD is at 0.5.0 with one more.
        self.repo(version="0.4.0", skills=("specwright-pr",))
        fx.squash_merge(self.work, "add-a", "0.4.1", 11)
        fx.squash_merge(self.work, "add-b", "0.5.0", 12, extra_files={
            "skills/specwright-new/SKILL.md": fx.skill_text("specwright-new", "0.5.0")})
        code, doc, raw = self.release("status", "--version", "0.4.1")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.1")
        self.assertEqual(sorted(doc["files"]), ["README.md", "VERSION", "skills/specwright-pr/SKILL.md"])
        self.assertEqual(doc["release_commit"], fx.git(self.work, "rev-parse", "HEAD~1"))
        code, doc, raw = self.release("status", "--version", "0.5.0")
        self.assertEqual(code, 0, raw)
        self.assertEqual(len(doc["files"]), 4)
        # a version that no commit carries
        self.assertStops(self.release("status", "--version", "0.9.9"), "0.9.9")

    def test_status_stops_when_release_commit_disagrees(self):
        self.repo(version="0.4.0")
        fx.set_version(self.work, "0.4.1", skills=("specwright-pr",))  # specwright-debug stays 0.4.0
        fx.commit(self.work, "feat: half bump (#3)")
        self.assertStops(self.release("status", "--version", "0.4.1"), "skills/specwright-debug/SKILL.md", "0.4.0", "0.4.1")

    def test_empty_glob(self):
        self.repo(version_files={"VERSION": r"^(\d+\.\d+\.\d+)$", "pkg/*/VERSION": r"^(\d+\.\d+\.\d+)$"})
        self.assertStops(self.release("check"), "pkg/*/VERSION")

    def test_paths_outside_the_repo_refused(self):
        outside = self.tmp / "outside.txt"
        outside.write_text("0.4.2\n", encoding="utf-8")
        for i, entry in enumerate(("../outside.txt", outside.as_posix(), "skills/../../outside.txt", "/etc/VERSION")):
            with self.subTest(entry=entry):
                self.work = fx.make_repo(self.tmp / str(i), version_files={"VERSION": r"^(\d+\.\d+\.\d+)$",
                                                                          entry: r"^(\d+\.\d+\.\d+)$"})
                for sub in (["check"], ["bump", "--to", "0.5.0"]):
                    out = self.release(*sub)
                    self.assertStops(out, entry, "inside the repository")
                    self.assertEqual(out[1]["error"], "bad_version_files")
                self.assertEqual(outside.read_text(encoding="utf-8"), "0.4.2\n")
                self.assertEqual(fx.git(self.work, "status", "--porcelain"), "")

    def test_symlinked_directory_outside_refused(self):
        outside = self.tmp / "elsewhere"
        outside.mkdir()
        (outside / "SKILL.md").write_text(fx.skill_text("x", "0.4.2"), encoding="utf-8")
        self.repo()
        try:
            os.symlink(outside, self.work / "skills" / "linked", target_is_directory=True)
        except (OSError, NotImplementedError) as e:
            self.skipTest(f"no symlinks here: {e}")
        for sub in (["check"], ["bump", "--to", "0.5.0"]):
            out = self.release(*sub)
            self.assertStops(out, "skills/linked/SKILL.md", "outside the repository")
            self.assertEqual(out[1]["error"], "bad_version_files")
        self.assertEqual((outside / "SKILL.md").read_text(encoding="utf-8"), fx.skill_text("x", "0.4.2"))

    def test_glob_primary_reads_every_file_present(self):
        # The primary glob reads every matching file at each commit, not only the ones the commit changed.
        self.repo(version="0.4.0", version_files={"skills/*/SKILL.md": r"^  version: (\S+)$",
                                                  "VERSION": r"^(\d+\.\d+\.\d+)$"})
        c1 = fx.squash_merge(self.work, "add-a", "0.4.1", 1)
        fx.git(self.work, "rm", "-q", "skills/specwright-debug/SKILL.md")
        fx.commit(self.work, "chore: drop debug (#2)")
        c3 = fx.squash_merge(self.work, "add-b", "0.5.0", 3)
        fx.commit(self.work, "chore: add stale (#4)", {"skills/specwright-new/SKILL.md": fx.skill_text("specwright-new", "0.4.9")})
        fx.set_version(self.work, "0.6.0", skills=("specwright-pr",))
        fx.commit(self.work, "feat: half bump (#5)")  # pr reads 0.6.0, new still 0.4.9: no single version
        self.assertEqual(self.release("status", "--version", "0.4.1")[1]["release_commit"], c1)
        self.assertEqual(self.release("status", "--version", "0.5.0")[1]["release_commit"], c3)
        out = self.release("status", "--version", "0.6.0")
        self.assertStops(out, "0.6.0")
        self.assertEqual(out[1]["error"], "no_release_commit")
        code, doc, raw = self.release("untagged")
        self.assertEqual(code, 0, raw)
        self.assertEqual([u["version"] for u in doc["untagged"]], ["0.5.0"])


class TestBump(Base):
    def read(self, rel):
        return (self.work / rel).read_bytes()

    def test_minor_bump_rewrites_only_versions(self):
        self.repo()
        # CRLF in one file must survive: only the captured version changes
        fx.write(self.work, "README.md", fx.readme_text("0.4.2").replace("\n", "\r\n"))
        fx.git(self.work, "add", "-A")
        fx.git(self.work, "commit", "-q", "-m", "crlf")
        before = fx.snapshot(self.work)
        code, doc, raw = self.release("bump", "--to", "0.5.0")
        self.assertEqual(code, 0, raw)
        self.assertEqual((doc["from"], doc["to"]), ("0.4.2", "0.5.0"))
        after = fx.snapshot(self.work)
        self.assertEqual(sorted(after), sorted(before))  # no stray temp files
        for rel in VERSION_FILES:
            self.assertEqual(after[rel], before[rel].replace(b"0.4.2", b"0.5.0"), rel)
        self.assertEqual(after["README.md"], fx.readme_text("0.5.0").replace("\n", "\r\n").encode())
        self.assertEqual({k for k in after if after[k] != before[k]}, set(VERSION_FILES))
        self.assertEqual(self.release("check")[1]["version"], "0.5.0")
        self.assertEqual(len(fx.git(self.work, "log", "--oneline").splitlines()), 2)  # bump never commits

    def test_target_not_greater(self):
        self.repo()
        before = fx.snapshot(self.work)
        for target in ("0.4.2", "0.4.1"):
            self.assertStops(self.release("bump", "--to", target), "0.4.2", target)
        self.assertEqual(fx.snapshot(self.work), before)

    def test_interrupted_bump_completes(self):
        self.repo()
        fx.write(self.work, "VERSION", "0.5.0\n")  # the first rename happened, the rest did not
        out = self.release("bump", "--to", "0.6.0")
        self.assertStops(out, "0.5.0", "0.4.2", "VERSION")
        self.assertEqual(self.read("VERSION"), b"0.5.0\n")
        self.assertEqual(self.read("README.md"), fx.readme_text("0.4.2").encode())
        code, doc, raw = self.release("bump", "--to", "0.5.0")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["changed"], ["README.md", "skills/specwright-debug/SKILL.md", "skills/specwright-pr/SKILL.md"])
        self.assertEqual(self.release("check")[1]["version"], "0.5.0")
        self.assertEqual(self.read("VERSION"), b"0.5.0\n")

    def test_interrupted_bump_to_lower_target_refused(self):
        self.repo()
        fx.write(self.work, "VERSION", "0.4.9\n")  # split {0.4.9, 0.4.2}: the lower one is no completion target
        before = fx.snapshot(self.work)
        self.assertStops(self.release("bump", "--to", "0.4.2"), "0.4.9", "0.4.2")
        self.assertEqual(fx.snapshot(self.work), before)

    def test_malformed_target(self):
        self.repo()
        before = fx.snapshot(self.work)
        for target in ("v0.5", "0.5.0-beta", "0.5", "0.5.0.1", " 0.5.0"):
            self.assertStops(self.release("bump", "--to", target), "MAJOR.MINOR.PATCH")
        self.assertEqual(fx.snapshot(self.work), before)

    def test_bump_refuses_when_a_file_does_not_match(self):
        self.repo()
        fx.write(self.work, "README.md", "# Demo\n")
        before = fx.snapshot(self.work)
        self.assertStops(self.release("bump", "--to", "0.5.0"), "README.md")
        self.assertEqual(fx.snapshot(self.work), before)


class Flow(Base):
    """Helpers shared by the release-commit, notes and untagged groups."""

    def sha(self, rev="HEAD"):
        return fx.git(self.work, "rev-parse", rev)

    def tag(self, name, rev="HEAD"):
        fx.git(self.work, "tag", name, rev)

    def status(self, version, *extra):
        code, doc, raw = self.release("status", "--version", version, *extra)
        self.assertEqual(code, 0, raw)
        return doc


class TestReleaseCommit(Flow):
    def test_squash(self):
        self.repo(version="0.4.1")
        fx.squash_merge(self.work, "add-x", "0.4.2", 11)
        doc = self.status("0.4.2")
        self.assertEqual(doc["release_commit"], self.sha())
        self.assertEqual((doc["version"], doc["tag"]), ("0.4.2", "v0.4.2"))

    def test_merge_commit(self):
        self.repo(version="0.4.0")
        merge = fx.merge_commit(self.work, "add-y", "0.4.1", 12)
        bump_on_branch = self.sha(f"{merge}^2")
        doc = self.status("0.4.1")
        self.assertEqual(doc["release_commit"], merge)
        self.assertNotEqual(doc["release_commit"], bump_on_branch)

    def test_not_on_main(self):
        self.repo(version="0.4.1")
        fx.git(self.work, "checkout", "-q", "-b", "feat/add-z")
        fx.squash_merge(self.work, "add-z", "0.5.0", 13)
        fx.git(self.work, "checkout", "-q", "main")
        out = self.release("status", "--version", "0.5.0")
        self.assertStops(out, "no commit", "0.5.0", "main")
        self.assertEqual(out[1]["error"], "no_release_commit")

    def test_rebase_commit_refused(self):
        self.repo(version="0.5.0")
        shas = fx.rebase_style(self.work, "x", "0.6.0", tasks=2)
        out = self.release("status", "--version", "0.6.0")
        self.assertStops(out, shas[-1][:12], "merge or squash")
        self.assertEqual(out[1]["error"], "rebase_release_commit")
        out = self.release("publish", "--version", "0.6.0")
        self.assertStops(out, shas[-1][:12], "merge or squash")
        self.assertEqual(fx.git(self.work, "tag"), "")

    def test_local_merge_commit_after_push(self):
        self.repo(version="0.4.0")
        merge = fx.local_merge(self.work, "add-w", "0.4.1")
        self.assertEqual(len(fx.git(self.work, "rev-list", "--parents", "-n1", merge).split()), 3)
        fx.push(self.work)
        fx.git(self.work, "fetch", "-q", "origin")
        doc = self.status("0.4.1", "--main", "origin/main")
        self.assertEqual(doc["release_commit"], merge)
        self.assertEqual(doc["main"], "origin/main")


class TestNotes(Flow):
    def test_one_change(self):
        self.repo(version="0.4.1")
        fx.squash_merge(self.work, "add-x", "0.4.2", 90, why="Operators cannot tell which build they run. More detail.")
        doc = self.status("0.4.2")
        self.assertEqual(doc["changes"], [{"name": "add-x", "why": "Operators cannot tell which build they run.", "pr": 90}])
        self.assertIn("- add-x (#90): Operators cannot tell which build they run.", doc["notes"])
        self.assertNotIn("More detail", doc["notes"])
        self.assertEqual(doc["previous"]["version"], "0.4.1")
        self.assertEqual(doc["range"]["from"], doc["previous"]["commit"])
        self.assertEqual(doc["range"]["to"], doc["release_commit"])

    def test_several_changes_in_order(self):
        self.repo(version="0.4.0")
        self.tag("v0.4.0")
        fx.squash_merge(self.work, "zeta", "0.4.1", 1, why="Zeta first.", date="2026-10-11")
        fx.merge_commit(self.work, "alpha", "0.4.2", 2, why="Alpha second.", date="2026-10-09")
        doc = self.status("0.4.2")
        self.assertEqual([(c["name"], c["pr"]) for c in doc["changes"]], [("zeta", 1), ("alpha", 2)])
        self.assertEqual(doc["previous"], {"commit": self.sha("v0.4.0"), "version": "0.4.0", "basis": "tag"})
        self.assertLess(doc["notes"].index("zeta"), doc["notes"].index("alpha"))

    def test_empty_range(self):
        self.repo(version="0.4.1")
        fx.git(self.work, "checkout", "-q", "-b", "docs/close-m1")
        fx.commit(self.work, "docs: close m1", {"docs/m1.md": "done\n"})
        fx.git(self.work, "checkout", "-q", "main")
        fx.git(self.work, "merge", "-q", "--no-ff", "-m", "Merge pull request #5 from acme/docs/close-m1", "docs/close-m1")
        fx.set_version(self.work, "0.4.2")
        fx.commit(self.work, "chore: bump to 0.4.2 (#6)")
        doc = self.status("0.4.2")
        self.assertEqual(doc["changes"], [])
        self.assertIn("No change was archived in this release", doc["notes"])

    def test_backfill_no_tag(self):
        self.repo(version="0.4.0")
        initial = self.sha()
        fx.merge_commit(self.work, "fix-m2-gaps", "0.4.1", 89, date="2026-10-15")
        fx.squash_merge(self.work, "later", "0.5.0", 95)  # HEAD is newer than the release being backfilled
        self.assertEqual(fx.git(self.work, "tag"), "")
        doc = self.status("0.4.1")
        self.assertEqual(doc["previous"], {"commit": initial, "version": "0.4.0", "basis": "history"})
        self.assertEqual([(c["name"], c["pr"]) for c in doc["changes"]], [("fix-m2-gaps", 89)])
        self.assertIsNone(doc["tag_local"])

    def test_tag_local_reports_the_tag_target(self):
        self.repo(version="0.4.1")
        fx.squash_merge(self.work, "add-x", "0.4.2", 3)
        self.tag("v0.4.2")
        self.assertEqual(self.status("0.4.2")["tag_local"], self.sha())

    def test_why_sentence_rule(self):
        # First sentence of the first paragraph under `## Why`: a leading list marker is dropped, whitespace
        # collapses, a `.`/`!`/`?` ends it only when followed by whitespace or the end and outside a code span
        # (and not after e.g/i.e/vs); clipped to 300 characters with an ellipsis.
        self.repo(version="0.4.1")
        cases = {
            "a-code": ("`release.sh` is missing. It matters.", "`release.sh` is missing."),
            "b-list": ("- First item. Second sentence.\n- other item", "First item."),
            "c-abbr": ("Cost is high (e.g. v1.2 vs. 1.3) today. Next.", "Cost is high (e.g. v1.2 vs. 1.3) today."),
            "d-wrap": ("Operators cannot\ntell   which build\nthey run. Next one.", "Operators cannot tell which build they run."),
            "e-long": ("word " * 80, None),
            "f-span": ("Run `a. b` now. Done.", "Run `a. b` now."),
            "g-bang": ("Stop it! Then go.", "Stop it!"),
        }
        extra = {}
        for name, (why, _) in cases.items():
            extra.update(fx.archive_files(name, why))
        extra[f"openspec/changes/archive/{fx.DATE}-h-nowhy/proposal.md"] = "## What Changes\n\n- x\n"
        fx.squash_merge(self.work, "big", "0.4.2", 5, extra_files=extra)
        got = {c["name"]: c["why"] for c in self.status("0.4.2")["changes"]}
        for name, (_, want) in cases.items():
            if want is not None:
                self.assertEqual(got[name], want, name)
        self.assertEqual(len(got["e-long"]), 300)
        self.assertTrue(got["e-long"].endswith("…"))
        self.assertIsNone(got["h-nowhy"])

    def test_over_100_lists_names_only(self):
        self.repo(version="0.4.1")
        extra = {}
        for i in range(105):
            extra.update(fx.archive_files(f"c{i:03d}", f"Reason {i}."))
        fx.squash_merge(self.work, "c-first", "0.4.2", 9, extra_files=extra)
        doc = self.status("0.4.2")
        self.assertEqual(len(doc["changes"]), 106)
        self.assertIn("- c000\n", doc["notes"])
        self.assertNotIn("Reason 3", doc["notes"])
        self.assertTrue(doc["notes"].rstrip().endswith("…and 6 more"), doc["notes"][-80:])


class TestUntagged(Flow):
    def tag(self, name, rev="HEAD", push=True):
        """A published tag reaches origin; push=False leaves it local, as a failed tag push does."""
        fx.git(self.work, "tag", "-a", name, "-m", name, rev)
        if push:
            fx.git(self.work, "push", "-q", "origin", f"refs/tags/{name}:refs/tags/{name}")

    def untagged(self, *extra):
        code, doc, raw = self.release("untagged", *extra)
        self.assertEqual(code, 0, raw)
        return doc

    def test_older_blocks_newer(self):
        self.repo(version="0.4.2")
        self.tag("v0.4.2")
        fx.squash_merge(self.work, "a", "0.5.0", 1)
        fx.squash_merge(self.work, "b", "0.5.1", 2)
        out = self.release("publish", "--version", "0.5.1")
        self.assertStops(out, "0.5.0")
        self.assertEqual(out[1]["error"], "older_untagged")
        self.assertEqual(fx.git(self.work, "tag", "-l", "v0.5.1"), "")

    def test_backfill_below_latest(self):
        self.repo(version="0.4.0")
        initial = self.sha()
        fx.squash_merge(self.work, "a", "0.4.1", 1)
        fx.squash_merge(self.work, "b", "0.5.0", 2)
        self.tag("v0.5.0")
        out = self.release("publish", "--version", "0.4.1")
        self.assertNotEqual((out[1] or {}).get("error"), "older_untagged", out[2])
        doc = self.status("0.4.1")
        self.assertEqual(doc["previous"]["commit"], initial)
        self.assertEqual(doc["previous"]["version"], "0.4.0")

    def test_lists_since_latest_tag(self):
        self.repo(version="0.5.0")
        self.tag("v0.5.0")
        c1 = fx.squash_merge(self.work, "a", "0.5.1", 1)
        c2 = fx.squash_merge(self.work, "b", "0.6.0", 2)
        doc = self.untagged()
        self.assertEqual([(u["version"], u["tag"], u["release_commit"]) for u in doc["untagged"]],
                         [("0.5.1", "v0.5.1", c1), ("0.6.0", "v0.6.0", c2)])
        self.assertEqual(doc["latest_tagged"], "0.5.0")

    def test_all_tagged_empty(self):
        self.repo(version="0.5.0")
        self.tag("v0.5.0")
        fx.squash_merge(self.work, "a", "0.5.1", 1)
        self.tag("v0.5.1")
        self.assertEqual(self.untagged()["untagged"], [])

    def test_local_only_tag_is_not_published(self):
        # 0.5.1's tag push failed: the local tag stays, but the version is still offered and blocks 0.6.0.
        self.repo(version="0.5.0")
        self.tag("v0.5.0")
        c1 = fx.squash_merge(self.work, "a", "0.5.1", 1)
        self.tag("v0.5.1", push=False)
        fx.squash_merge(self.work, "b", "0.6.0", 2)
        doc = self.untagged()
        self.assertEqual([(u["version"], u["release_commit"]) for u in doc["untagged"]][0], ("0.5.1", c1))
        self.assertEqual(doc["latest_tagged"], "0.5.0")
        out = self.release("publish", "--version", "0.6.0")
        self.assertStops(out, "0.5.1")
        self.assertEqual(out[1]["error"], "older_untagged")
        self.assertEqual(fx.git(self.tmp / "origin.git", "tag"), "v0.5.0")

    def test_first_release_push_failed(self):
        # nothing on origin and v0.3.0 only local: 0.3.0 is still listed before 0.3.1, and blocks it
        self.repo(version="0.3.0")
        c0 = self.sha()
        self.tag("v0.3.0", push=False)
        c1 = fx.squash_merge(self.work, "a", "0.3.1", 1)
        doc = self.untagged()
        self.assertEqual([(u["version"], u["release_commit"]) for u in doc["untagged"]], [("0.3.0", c0), ("0.3.1", c1)])
        self.assertIsNone(doc["latest_tagged"])
        out = self.release("publish", "--version", "0.3.1")
        self.assertStops(out, "0.3.0")
        self.assertEqual(out[1]["error"], "older_untagged")
        self.assertEqual(fx.git(self.tmp / "origin.git", "tag"), "")

    def test_without_origin_local_tags_count(self):
        self.repo(version="0.5.0")
        fx.git(self.work, "remote", "remove", "origin")
        self.tag("v0.5.0", push=False)
        fx.squash_merge(self.work, "a", "0.5.1", 1)
        self.assertEqual([u["version"] for u in self.untagged()["untagged"]], ["0.5.1"])

    def test_origin_unreadable(self):
        self.repo(version="0.5.0")
        fx.git(self.work, "config", "remote.origin.url", str(self.tmp / "does-not-exist.git"))
        code, doc, raw = self.release("untagged")
        self.assertEqual(code, 3, raw)
        self.assertEqual(doc["error"], "remote_tags_unreadable")

    def test_no_tag_current_only(self):
        self.repo(version="0.2.0")
        fx.squash_merge(self.work, "a", "0.3.0", 1)
        doc = self.untagged()
        self.assertEqual([u["version"] for u in doc["untagged"]], ["0.3.0"])
        self.assertIsNone(doc["latest_tagged"])


GH_SCRIPT = '#!/bin/sh\nexec python "{}" "$@"\n'
CODE_SLUG = "acme/code"


class GhFlow(Flow):
    """A `gh` shim on PATH backed by evals/fakes/gh.py, and a code repo whose origin looks like github.com but reaches a
    local bare repository through `url.<bare>.insteadOf`."""

    def setUp(self):
        super().setUp()
        (self.tmp / "bin").mkdir()
        gh = self.tmp / "bin" / "gh"
        gh.write_text(GH_SCRIPT.format((ROOT / "evals" / "fakes" / "gh.py").resolve().as_posix()), encoding="utf-8", newline="\n")
        gh.chmod(0o755)
        self.state = {"user": "KintsugiBot", "tokens": {"KintsugiBot": "tok"}, "repos": {CODE_SLUG: {"pulls": []}}}
        self.gh_state, self.gh_log = self.tmp / "gh-state.json", self.tmp / "gh-log.jsonl"

    def env(self):
        e = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST")}
        e.update({"PATH": str(self.tmp / "bin") + os.pathsep + e.get("PATH", ""), "FAKE_GH_STATE": str(self.gh_state),
                  "FAKE_GH_LOG": str(self.gh_log), "GH_REPO": "someone/else"})  # an inherited GH_REPO must not reach gh
        return e

    def save(self):
        self.gh_state.write_text(json.dumps(self.state), encoding="utf-8")

    def connect(self):
        """origin keeps a GitHub-form URL (release.sh derives the gh repo from it); git reaches the local bare repo."""
        url = f"https://github.com/{CODE_SLUG}.git"
        fx.git(self.work, "config", "remote.origin.url", url)
        fx.git(self.work, "config", f"url.{(self.tmp / 'origin.git').as_posix()}.insteadOf", url)
        return self.tmp / "origin.git"

    def gh_calls(self):
        if not self.gh_log.exists():
            return []
        return [json.loads(l) for l in self.gh_log.read_text(encoding="utf-8").splitlines()]


class TestStoreNotes(GhFlow):
    """Store-backed notes (design D5): candidates come from the store's main, the proof from the code repo."""

    def pull(self, number, change, sha=None, merged=True, repo=CODE_SLUG, prefix="feat"):
        self.state["repos"][CODE_SLUG]["pulls"].append({
            "number": number, "state": "closed" if merged else "open", "merged_at": "2026-10-12T00:00:00Z" if merged else None,
            "merge_commit_sha": sha, "html_url": f"https://github.com/{CODE_SLUG}/pull/{number}",
            "head": {"ref": f"{prefix}/{change}", "label": f"{repo.split('/')[0]}:{prefix}/{change}", "repo": {"full_name": repo}},
            "base": {"ref": "main"}})

    def code(self, finish="pr", version="0.4.1"):
        self.repo(version=version, finish=finish)
        self.connect()
        return self.work

    def store_status(self, store, version, *extra, expect=0):
        self.save()
        code, doc, raw = self.release("status", "--version", version, "--store", str(store), *extra, env=self.env())
        self.assertEqual(code, expect, raw)
        return doc

    def test_other_prefix_is_not_proof(self):
        # add-x's branch is feat/add-x, so a merged docs/add-x PR is no proof; fix-y's branch is bugfix/fix-y.
        self.code()
        store = fx.make_store(self.tmp, [("add-x", "X reason.", False), ("fix-y", "Y reason.", False)])
        sha = fx.squash_merge(self.work, "add-x", "0.4.2", 90)
        self.pull(90, "add-x", sha, prefix="docs")
        self.pull(91, "fix-y", sha, prefix="bugfix")
        doc = self.store_status(store, "0.4.2")
        self.assertEqual([(c["name"], c["pr"]) for c in doc["changes"]], [("fix-y", 91)])

    def test_merged_pr_in_range(self):
        self.code()
        store = fx.make_store(self.tmp, [("add-x", "Store reason for x. Extra.", False), ("add-p", "Planning only.", True),
                                         ("add-z", "From a fork.", False)])
        sha = fx.squash_merge(self.work, "add-x", "0.4.2", 90, why="Code archive reason (ignored).")
        self.pull(90, "add-x", sha)
        self.pull(91, "add-p", sha)  # planning-only: left out whatever its PRs say
        self.pull(92, "add-z", sha, repo="fork/code")  # not the code repo's own branch
        doc = self.store_status(store, "0.4.2")
        self.assertEqual(doc["changes"], [{"name": "add-x", "why": "Store reason for x.", "pr": 90}])
        calls = [json.loads(l) for l in self.gh_log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([c["argv"][0] for c in calls].count("api"), 1, calls)  # one pulls call (status also views the release)
        api = [c for c in calls if c["argv"][0] == "api"][0]
        self.assertIn("--paginate", api["argv"])
        self.assertTrue(any(a.startswith(f"repos/{CODE_SLUG}/pulls?state=closed&base=main") for a in api["argv"]), api)
        self.assertTrue(all(c["gh_repo"] is None for c in calls), calls)

    def test_pending_left_out(self):
        self.code()
        store = fx.make_store(self.tmp, [("add-x", "X reason.", False), ("add-y", "Y reason.", False)])
        sx = fx.squash_merge(self.work, "add-x", "0.4.2", 90)
        self.pull(90, "add-x", sx)
        self.pull(93, "add-y", None, merged=False)
        doc = self.store_status(store, "0.4.2")
        self.assertEqual([c["name"] for c in doc["changes"]], ["add-x"])
        # y's PR merges, then a later release lists it (and not x again)
        sy = fx.squash_merge(self.work, "add-y", "0.4.3", 93)
        self.state["repos"][CODE_SLUG]["pulls"] = [p for p in self.state["repos"][CODE_SLUG]["pulls"] if p["number"] != 93]
        self.pull(93, "add-y", sy)
        doc = self.store_status(store, "0.4.3")
        self.assertEqual([(c["name"], c["pr"]) for c in doc["changes"]], [("add-y", 93)])

    def test_discovery_failure_stops(self):
        self.code()
        store = fx.make_store(self.tmp, [("add-x", "X reason.", False)])
        fx.squash_merge(self.work, "add-x", "0.4.2", 90)
        self.state["fail"] = [{"match": "api .*pulls", "stderr": "gh: connection reset"}]
        self.save()
        code, doc, raw = self.release("status", "--version", "0.4.2", "--store", str(store), env=self.env())
        self.assertEqual(code, 3, raw)
        self.assertEqual(doc["error"], "pr_discovery_failed")
        self.assertIn("gh api", doc["message"])
        self.assertIn("pulls", doc["message"])
        self.assertEqual(fx.git(self.work, "tag"), "")

    def test_store_not_tagged(self):
        # A full publish with --store: the tag lands in the code repo (and its origin) only.
        self.code()
        store = fx.make_store(self.tmp, [("add-x", "X reason.", False)])
        sha = fx.squash_merge(self.work, "add-x", "0.4.2", 90)
        self.pull(90, "add-x", sha)
        doc = self.store_status(store, "0.4.2")
        self.assertEqual(Path(doc["tag_repo"]).resolve(), self.work.resolve())
        self.assertEqual(fx.git(store, "tag"), "")
        self.assertEqual(fx.git(self.work, "tag"), "")
        self.save()
        code, doc, raw = self.release("publish", "--version", "0.4.2", "--store", str(store), env=self.env())
        self.assertEqual(code, 0, raw)
        self.assertEqual(Path(doc["tag_repo"]).resolve(), self.work.resolve())
        self.assertEqual(fx.git(self.work, "tag"), "v0.4.2")
        self.assertEqual(fx.git(self.work, "rev-parse", "v0.4.2^{commit}"), sha)
        self.assertEqual(fx.git(self.tmp / "origin.git", "tag"), "v0.4.2")
        self.assertEqual(fx.git(store, "tag"), "")
        self.assertIn("X reason.", fx.git(self.work, "tag", "-l", "--format=%(contents)", "v0.4.2"))

    def test_local_mode_uses_merge_subject(self):
        self.code(finish="local", version="0.4.0")
        store = fx.make_store(self.tmp, [("add-w", "W reason.", False), ("add-v", "V reason.", False)])
        fx.local_merge(self.work, "add-w", "0.4.1")
        doc = self.store_status(store, "0.4.1")
        self.assertEqual(doc["changes"], [{"name": "add-w", "why": "W reason.", "pr": None}])
        self.assertFalse([c for c in self.gh_calls() if c["argv"][0] == "api"])  # no PR discovery in local mode



class PubFlow(GhFlow):
    """A code repo at 0.5.0 (release commit `self.rc`) whose origin is a GitHub-form URL over a local bare repo."""

    TAG = "v0.5.0"

    def setUp(self):
        super().setUp()
        self.repo(version="0.4.0")
        self.base = self.sha()
        self.state["repos"][CODE_SLUG].update({"releases": {}})
        self.bare = self.connect()
        fx.push(self.work)
        self.rc = fx.squash_merge(self.work, "add-x", "0.5.0", 7)

    def publish(self, version="0.5.0", *extra, env=None):
        self.save()
        return self.release("publish", "--version", version, *extra, env=env or self.env())

    def remote(self, tag=None):
        """`git ls-remote` lines of origin's tags (tag object and peeled commit)."""
        return fx.git(self.work, "ls-remote", "--tags", "origin", *([f"refs/tags/{tag}*"] if tag else []))

    def obj(self, tag=None):
        return fx.git(self.work, "rev-parse", f"refs/tags/{tag or self.TAG}")

    def seed_tag(self, commit=None, message="Seeded notes\n", name=None, local=True, push=True):
        name = name or self.TAG
        fx.git(self.work, "tag", "-a", name, "-m", message, commit or self.rc)
        if push:
            fx.git(self.work, "push", "-q", "origin", f"refs/tags/{name}:refs/tags/{name}")
        if not local:
            fx.git(self.work, "tag", "-d", name)

    def releases(self):
        return json.loads(self.gh_state.read_text(encoding="utf-8"))["repos"][CODE_SLUG].get("releases", {})

    def creates(self):
        return [c for c in self.gh_calls() if c["argv"][:2] == ["release", "create"]]

    def contents(self, tag=None):
        return fx.git(self.work, "tag", "-l", "--format=%(contents)", tag or self.TAG)


class TestPublish(PubFlow):
    def test_new_release(self):
        code, doc, raw = self.publish()
        self.assertEqual(code, 0, raw)
        self.assertEqual(fx.git(self.work, "cat-file", "-t", self.TAG), "tag")
        self.assertEqual(fx.git(self.work, "rev-parse", f"{self.TAG}^{{commit}}"), self.rc)
        self.assertIn(f"refs/tags/{self.TAG}", self.remote(self.TAG))
        self.assertEqual(fx.git(self.bare, "rev-parse", f"{self.TAG}^{{commit}}"), self.rc)
        self.assertIn("add-x", self.contents())
        self.assertEqual((doc["ok"], doc["version"], doc["tag"], doc["release_commit"]), (True, "0.5.0", self.TAG, self.rc))
        self.assertEqual((doc["tag_local"], doc["tag_remote"], doc["github_release"]), ("created", "pushed", "created"))

    def test_only_the_tag_ref_is_pushed(self):
        # a local branch commit and an extra local tag stay local
        fx.git(self.work, "tag", "other", self.base)
        fx.commit(self.work, "wip", {"wip.txt": "x\n"})
        head_before = fx.git(self.bare, "rev-parse", "main")
        self.assertEqual(self.publish()[0], 0)
        self.assertEqual(fx.git(self.bare, "rev-parse", "main"), head_before)
        self.assertEqual(fx.git(self.bare, "tag"), self.TAG)

    def test_push_failure(self):
        hook = self.bare / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho 'tag push rejected by hook' >&2\nexit 1\n", encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        code, doc, raw = self.publish()
        self.assertEqual(code, 3, raw)
        self.assertIs(doc["ok"], False)
        self.assertIn("re-run", doc["message"])
        self.assertIn("local tag", doc["message"])
        self.assertIn("git push", doc["message"])
        self.assertEqual(fx.git(self.work, "cat-file", "-t", self.TAG), "tag")  # the local tag stays
        self.assertEqual(fx.git(self.bare, "tag"), "")
        self.assertEqual(self.creates(), [])
        self.assertEqual(self.gh_calls(), [])  # no GitHub call before the tag is on origin

    def test_rerun_creates_only_release(self):
        self.seed_tag()
        before = self.obj()
        remote_before = self.remote()
        code, doc, raw = self.publish()
        self.assertEqual(code, 0, raw)
        self.assertEqual((doc["tag_local"], doc["tag_remote"], doc["github_release"]), ("existing", "existing", "created"))
        self.assertEqual(self.obj(), before)
        self.assertEqual(self.remote(), remote_before)
        self.assertEqual(self.releases()[self.TAG]["body"].strip(), "Seeded notes")
        self.assertEqual(len(self.creates()), 1)
        self.state = json.loads(self.gh_state.read_text(encoding="utf-8"))  # keep the fake's release
        again = self.publish()
        self.assertEqual(again[0], 0, again[2])
        self.assertEqual(len(self.creates()), 1)  # nothing is created twice
        self.assertEqual(again[1]["github_release"], "existing")

    def test_origin_only_tag_fetched(self):
        self.seed_tag(local=False, message="Origin notes only\n")
        self.assertEqual(fx.git(self.work, "tag"), "")
        origin_obj = self.remote(self.TAG).splitlines()[0].split()[0]
        code, doc, raw = self.publish()
        self.assertEqual(code, 0, raw)
        self.assertEqual(self.obj(), origin_obj)  # fetched, not created again
        self.assertEqual((doc["tag_local"], doc["tag_remote"]), ("fetched", "existing"))
        self.assertEqual(self.releases()[self.TAG]["body"].strip(), "Origin notes only")

    def test_conflicting_tag_stops(self):
        # the tag sits at another commit, on origin only and then locally only
        for local in (False, True):
            with self.subTest(local=local):
                self.seed_tag(commit=self.base, local=local, push=not local)
                tags_before, remote_before = fx.git(self.work, "tag"), self.remote()
                code, doc, raw = self.publish()
                self.assertEqual(code, 1, raw)
                self.assertEqual(doc["error"], "tag_conflict")
                self.assertIn(self.base, doc["message"])
                self.assertIn(self.rc, doc["message"])
                self.assertEqual(fx.git(self.work, "tag"), tags_before)
                self.assertEqual(self.remote(), remote_before)
                self.assertEqual(self.gh_calls(), [])
                self.assertEqual(self.releases(), {})
                if local:
                    fx.git(self.work, "tag", "-d", self.TAG)
                else:
                    fx.git(self.bare, "tag", "-d", self.TAG)

    def test_lightweight_tag_stops(self):
        # a lightweight tag at the release commit, on origin only and then locally only
        for local in (False, True):
            with self.subTest(local=local):
                fx.git(self.work, "tag", self.TAG, self.rc)
                if not local:
                    fx.git(self.work, "push", "-q", "origin", f"refs/tags/{self.TAG}:refs/tags/{self.TAG}")
                    fx.git(self.work, "tag", "-d", self.TAG)
                tags_before, remote_before = fx.git(self.work, "tag"), self.remote()
                code, doc, raw = self.publish()
                self.assertEqual(code, 1, raw)
                self.assertEqual(doc["error"], "lightweight_tag")
                self.assertIn("locally" if local else "on origin", doc["message"])
                self.assertEqual(fx.git(self.work, "tag"), tags_before)
                self.assertEqual(self.remote(), remote_before)
                self.assertEqual(self.creates(), [])
                if local:
                    fx.git(self.work, "tag", "-d", self.TAG)
                else:
                    fx.git(self.bare, "tag", "-d", self.TAG)

    def test_ls_remote_failure(self):
        fx.git(self.work, "config", "remote.origin.url", str(self.tmp / "does-not-exist.git"))
        code, doc, raw = self.publish()
        self.assertEqual(code, 3, raw)
        self.assertIn("git ls-remote", doc["message"])
        self.assertEqual(fx.git(self.work, "tag"), "")
        self.assertEqual(self.gh_calls(), [])


class TestGithubRelease(PubFlow):
    def test_status_reports_release_state(self):
        def state():
            self.save()
            code, doc, raw = self.release("status", "--version", "0.5.0", env=self.env())
            self.assertEqual(code, 0, raw)
            return doc["github_release"]
        self.assertEqual(state(), "absent")
        self.state["repos"][CODE_SLUG]["releases"] = {self.TAG: {"tag_name": self.TAG, "name": self.TAG, "body": "x",
                                                                  "created_at": "2026-10-10T00:00:00Z"}}
        self.assertEqual(state(), "existing")
        self.assertEqual(self.creates(), [])
        self.state["fail"] = [{"match": "release view", "stderr": "gh: connection reset"}]
        self.save()
        code, doc, raw = self.release("status", "--version", "0.5.0", env=self.env())
        self.assertEqual((code, doc["error"]), (3, "release_view_failed"), raw)
        del self.state["fail"]
        fx.write(self.work, "openspec/specwright.yaml",
                 fx.settings_text(fx.DEFAULT_VERSION_FILES, extra_release="  github_release: false\n"))
        self.assertEqual(state(), "disabled")
        fx.write(self.work, "openspec/specwright.yaml", fx.settings_text(fx.DEFAULT_VERSION_FILES))
        fx.git(self.work, "config", "remote.origin.url", self.bare.as_posix())
        self.assertEqual(state(), "not_github")

    def test_created_with_tag_message(self):
        code, doc, raw = self.publish()
        self.assertEqual(code, 0, raw)
        rel = self.releases()[self.TAG]
        self.assertEqual(rel["body"].strip(), self.contents().strip())
        self.assertIn("add-x", rel["body"])
        self.assertEqual(rel["name"], self.TAG)
        create = self.creates()[0]["argv"]
        self.assertIn("--verify-tag", create)
        self.assertEqual(create[create.index("--repo") + 1], CODE_SLUG)
        self.assertEqual(doc["release_url"], f"https://github.com/{CODE_SLUG}/releases/tag/{self.TAG}")

    def test_existing_left_alone(self):
        self.state["repos"][CODE_SLUG]["releases"] = {self.TAG: {"tag_name": self.TAG, "name": "by hand", "body": "hand-written",
                                                                  "created_at": "2026-10-10T00:00:00Z"}}
        before = json.loads(json.dumps(self.state["repos"][CODE_SLUG]["releases"]))
        code, doc, raw = self.publish()
        self.assertEqual(code, 0, raw)
        self.assertEqual(self.releases(), before)
        self.assertEqual(self.creates(), [])
        self.assertEqual(doc["github_release"], "existing")
        self.assertEqual(fx.git(self.bare, "tag"), self.TAG)

    def test_create_failure_resumable(self):
        self.state["fail"] = [{"match": "release create", "stderr": "gh: connection reset"}]
        code, doc, raw = self.publish()
        self.assertEqual(code, 3, raw)
        self.assertIs(doc["ok"], False)
        self.assertIn("gh release create", doc["message"])
        self.assertEqual(fx.git(self.bare, "rev-parse", f"{self.TAG}^{{commit}}"), self.rc)  # the tag stays on origin
        self.assertEqual(self.releases(), {})
        obj, remote = self.obj(), self.remote()
        del self.state["fail"]
        self.gh_log.unlink()
        code, doc, raw = self.publish()
        self.assertEqual(code, 0, raw)
        self.assertEqual((doc["tag_local"], doc["tag_remote"], doc["github_release"]), ("existing", "existing", "created"))
        self.assertEqual(len(self.creates()), 1)
        self.assertEqual((self.obj(), self.remote()), (obj, remote))  # no second tag, no second push
        self.assertIn(self.TAG, self.releases())

    def test_disabled_and_not_github(self):
        fx.write(self.work, "openspec/specwright.yaml",
                 fx.settings_text(fx.DEFAULT_VERSION_FILES, extra_release="  github_release: false\n"))
        code, doc, raw = self.publish()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["github_release"], "disabled")
        self.assertEqual(self.gh_calls(), [])
        # origin off github.com: the tag is pushed, no release is attempted
        fx.git(self.work, "tag", "-d", self.TAG)
        fx.git(self.bare, "tag", "-d", self.TAG)
        fx.write(self.work, "openspec/specwright.yaml", fx.settings_text(fx.DEFAULT_VERSION_FILES))
        fx.git(self.work, "config", "remote.origin.url", self.bare.as_posix())
        code, doc, raw = self.publish()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["github_release"], "not_github")
        self.assertEqual(self.gh_calls(), [])
        self.assertEqual(fx.git(self.bare, "tag"), self.TAG)


class TestThisRepo(Base):
    def test_backfill_ranges(self):
        # The 0.4.1 and 0.4.2 releases of this repository, backfilled from its history (no tags exist). The
        # repository's own specwright.yaml is local, so the entries are pinned in a clone.
        if fx.git(ROOT, "rev-parse", "--is-shallow-repository", check=False) == "true":
            self.skipTest("shallow clone")
        for sha in ("9b33ec5", "4f9b823"):
            if subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=ROOT, capture_output=True).returncode != 0:
                self.skipTest(f"{sha} is not in this history")
        clone = self.tmp / "clone"
        r = subprocess.run(["git", "clone", "-q", "--no-checkout", str(ROOT), str(clone)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        if subprocess.run(["git", "rev-parse", "--verify", "--quiet", "origin/main"], cwd=clone, capture_output=True).returncode != 0:
            self.skipTest("no main branch in this checkout")
        fx.write(clone, "openspec/specwright.yaml", fx.settings_text(fx.DEFAULT_VERSION_FILES))
        for version, prefix, name, pr in (("0.4.1", "9b33ec5", "fix-m2-gaps", 89), ("0.4.2", "4f9b823", "pin-openspec-version", 90)):
            code, doc, raw = self.release("status", "--version", version, "--main", "origin/main", cwd=clone)
            self.assertEqual(code, 0, raw)
            self.assertTrue(doc["release_commit"].startswith(prefix), doc["release_commit"])
            self.assertEqual([(c["name"], c["pr"]) for c in doc["changes"]], [(name, pr)])
            self.assertIn(name, doc["notes"])
            self.assertEqual(doc["version"], version)


class TestVersionFiles(Base):
    def test_repo_version_files_agree(self):
        # This repo's version files, read from its working tree with its `release.version_files` entries. Its own
        # openspec/specwright.yaml is local (gitignored), so the entries are pinned here and the files are copied
        # into a scratch repo: drift in any of them fails the suite in every checkout.
        work = self.tmp / "this"
        rels = ["VERSION", "README.md"] + sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob("skills/*/SKILL.md"))
        for rel in rels:
            dst = work / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((ROOT / rel).read_bytes())
        fx.write(work, "openspec/specwright.yaml", fx.settings_text(fx.DEFAULT_VERSION_FILES))
        fx.git(work, "init", "-q", "-b", "main")
        code, doc, raw = self.release("check", cwd=work)
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], (ROOT / "VERSION").read_text(encoding="utf-8").strip())
        self.assertEqual(sorted(doc["files"]), sorted(rels))
        self.assertEqual(len(rels), 10)


if __name__ == "__main__":
    unittest.main()
