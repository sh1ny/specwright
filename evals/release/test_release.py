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
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = Path(os.environ.get("RELEASE_SH") or ROOT / "skills" / "specwright-release" / "scripts" / "release.sh")

_spec = importlib.util.spec_from_file_location("release_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)
import bashexe  # noqa: E402

VERSION_FILES = ["VERSION", "README.md", "skills/specwright-pr/SKILL.md", "skills/specwright-debug/SKILL.md"]


def section(summary, **groups):
    """A `## Release Notes` section: a summary, then the non-empty groups (added, changed, fixed, removed) as list items."""
    out = f"## Release Notes\n\n{summary}\n"
    for h in ("Added", "Changed", "Fixed", "Removed"):
        if groups.get(h.lower()):
            out += f"\n### {h}\n\n" + "".join(f"- {i}\n" for i in groups[h.lower()])
    return out


def change_files(change, sec=None, tasks=None, date=fx.DATE, pad=0):
    """The archived files of one change: a proposal with a Why (and the section `sec`), and a tasks.md when `tasks` is given."""
    base = f"openspec/changes/archive/{date}-{change}/"
    text = f"## Why\n\nWhy of {change}.\n\n## What Changes\n\n- {change}\n" + (f"\n{sec}" if sec else "")
    if pad:
        text += "\n## Appendix\n\n" + "filler line\n" * pad
    files = {base + "proposal.md": text}
    if tasks is not None:
        files[base + "tasks.md"] = tasks
    return files


def bump_task(version):
    return f"## 3. Release\n\n- [x] 3.1 Run `release.sh bump --to {version}` and commit\n"


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
        r = subprocess.run([bashexe.bash(), str(SCRIPT), *args], cwd=cwd or self.work, capture_output=True, text=True,
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

    def test_tag_template_without_version_refused(self):
        # A template with no {version} maps every version to one tag: after one publish, every older version would read
        # as published and never be offered. Every subcommand stops before any read or write.
        self.repo()
        fx.write(self.work, "openspec/specwright.yaml",
                 fx.settings_text(fx.DEFAULT_VERSION_FILES, extra_release='  tag: "release"\n'))
        before = fx.snapshot(self.work)
        for args in (("check",), ("bump", "--to", "0.5.0"), ("untagged",), ("publish", "--version", "0.4.2")):
            out = self.release(*args)
            self.assertStops(out, "release.tag", "{version}")
            self.assertEqual(out[1]["error"], "bad_tag_template")
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

    def test_glob_primary_merge_diffs_first_parent_on_any_git(self):
        # A merge's first-parent diff carries the files its branch added, whatever log.diffMerges says, and without
        # --diff-merges (git 2.31+ only): the merge adds a stale SKILL.md, so it is not the release commit of 0.5.0.
        self.repo(version="0.4.0", version_files={"skills/*/SKILL.md": r"^  version: (\S+)$",
                                                  "VERSION": r"^(\d+\.\d+\.\d+)$"})
        fx.git(self.work, "config", "log.diffMerges", "combined")
        fx.git(self.work, "checkout", "-q", "-b", "feat/add-n")
        fx.set_version(self.work, "0.5.0")
        fx.commit(self.work, "feat(add-n): do add-n", {"skills/specwright-new/SKILL.md": fx.skill_text("specwright-new", "0.4.9")})
        fx.git(self.work, "checkout", "-q", "main")
        fx.git(self.work, "merge", "-q", "--no-ff", "-m", "Merge pull request #3 from acme/feat/add-n", "feat/add-n")
        fixed = fx.commit(self.work, "fix: new skill version (#4)",
                          {"skills/specwright-new/SKILL.md": fx.skill_text("specwright-new", "0.5.0")})
        self.assertEqual(self.release("status", "--version", "0.5.0")[1]["release_commit"], fixed)
        self.assertNotIn("--diff-merges", SCRIPT.read_text(encoding="utf-8"))


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

    def test_symlinked_version_file_refused(self):
        # A version file that is a link, or reached through a linked directory, inside the repository: git would store
        # the link text, so status and publish could not read it. Check and bump stop and change nothing.
        rx = r"^(\d+\.\d+\.\d+)$"
        for entry, make in (("pkg/VERSION", lambda: os.symlink(os.path.join("..", "VERSION"), self.work / "pkg" / "VERSION")),
                            ("alias/*/VERSION", lambda: os.symlink("pkg", self.work / "alias", target_is_directory=True))):
            with self.subTest(entry=entry):
                self.work = fx.make_repo(self.tmp / entry.split("/")[0], version_files={"VERSION": rx, entry: rx})
                (self.work / "pkg").mkdir()
                if entry.startswith("alias"):
                    fx.write(self.work, "pkg/x/VERSION", "0.4.2\n")
                try:
                    make()
                except (OSError, NotImplementedError) as e:
                    self.skipTest(f"no symlinks here: {e}")
                before = fx.snapshot(self.work)
                for sub in (["check"], ["bump", "--to", "0.5.0"]):
                    out = self.release(*sub)
                    self.assertStops(out, "through a symlink;", "List the file the link points to")
                    self.assertEqual(out[1]["error"], "bad_version_files")
                self.assertEqual(fx.snapshot(self.work), before)
                self.assertEqual(self.read("VERSION"), b"0.4.2\n")

    def test_symlink_at_release_commit_refused(self):
        # A link committed as a version file (mode 120000, the blob is the link text) stops status, naming it.
        rx = r"^(\d+\.\d+\.\d+)$"
        self.repo(version="0.4.0", version_files={"VERSION": rx, "pkg/VERSION": rx})
        fx.set_version(self.work, "0.5.0")
        fx.git(self.work, "add", "-A")
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.work, input="../VERSION", capture_output=True,
                              text=True, check=True).stdout.strip()
        fx.git(self.work, "update-index", "--add", "--cacheinfo", f"120000,{blob},pkg/VERSION")
        fx.git(self.work, "commit", "-q", "-m", "feat(add-l): link the version (#5)")
        out = self.release("status", "--version", "0.5.0")
        self.assertStops(out, "pkg/VERSION", "a symlink at commit")
        self.assertEqual(out[1]["error"], "bad_version_files")

    def test_overlapping_entries_bump_every_capture(self):
        # Two entries match pkg.txt and capture different lines; a third captures the same span as the first. Bump
        # rewrites both lines once. A partly overlapping capture reads another value, so it stops before any write.
        rx = r"^(\d+\.\d+\.\d+)$"
        self.repo(version_files={"VERSION": rx, "pkg.txt": r"^version = (\S+)$", "*.txt": r"^min = (\S+)$",
                                 "p*.txt": r"^version = (\S+)$"})
        fx.commit(self.work, "pkg", {"pkg.txt": "version = 0.4.2\nmin = 0.4.2\n"})
        code, doc, raw = self.release("bump", "--to", "0.5.0")
        self.assertEqual(code, 0, raw)
        self.assertEqual(self.read("pkg.txt"), b"version = 0.5.0\nmin = 0.5.0\n")
        self.assertEqual(self.release("check")[1]["version"], "0.5.0")
        self.work = fx.make_repo(self.tmp / "partial", version_files={"VERSION": rx, "pkg.txt": r"^v = (\S+)$",
                                                                      "*.txt": r"^v = (\d+\.\d+)"})
        fx.commit(self.work, "pkg", {"pkg.txt": "v = 0.4.2\n"})
        before = fx.snapshot(self.work)
        out = self.release("bump", "--to", "0.5.0")
        self.assertEqual(out[0], 1, out[2])
        self.assertEqual(out[1]["error"], "version_files_disagree")
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


class Notes(Base):
    """Helpers: run `release.sh notes --proposal <file>` on a temp file outside any repository."""

    def notes_cmd(self, text, raw=None):
        path = self.tmp / "proposal.md"
        path.write_bytes(raw if raw is not None else text.encode("utf-8"))
        return self.release("notes", "--proposal", str(path), cwd=self.tmp)

    def invalid(self, text):
        code, doc, raw = self.notes_cmd(text)
        self.assertEqual(code, 1, raw)
        self.assertEqual((doc["ok"], doc["error"]), (False, "release_notes_invalid"), raw)
        return doc["errors"]

    def valid(self, text):
        code, doc, raw = self.notes_cmd(text)
        self.assertEqual(code, 0, raw)
        return doc


def texts(doc, heading):
    return [i["text"] for i in doc["items"].get(heading, [])]


class TestReleaseNotesParse(Notes):
    def test_valid_section(self):
        doc = self.valid("## Why\n\nx\n\n## Release Notes\n\nOne sentence.\n\n### Fixed\n\n- F1\n- F2\n\n### Added\n\n- A1\n")
        self.assertEqual(doc["summary"], "One sentence.")
        self.assertEqual(texts(doc, "fixed"), ["F1", "F2"])
        self.assertEqual(texts(doc, "added"), ["A1"])
        self.assertNotIn("changed", doc["items"])

    def test_unknown_heading_invalid(self):
        errors = self.invalid("## Release Notes\n\nS.\n\n### Security\n\n- x\n")
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("Security", errors[0]["message"])
        self.assertEqual(errors[0]["line"], 5)

    def test_prose_under_heading_invalid(self):
        errors = self.invalid("## Release Notes\n\nS.\n\n### Changed\n\nSome prose here.\n- ok\n")
        self.assertEqual([e["line"] for e in errors], [7])

    def test_missing_summary_or_items_invalid(self):
        errors = self.invalid("## Release Notes\n\n### Added\n\n- a\n")
        self.assertIn("summary", errors[0]["message"])
        errors = self.invalid("## Release Notes\n\nA summary.\n")
        self.assertIn("item", errors[0]["message"])

    def test_item_over_500_invalid(self):
        self.valid("## Release Notes\n\nS.\n\n### Added\n\n- " + "x" * 500 + "\n")
        errors = self.invalid("## Release Notes\n\nS.\n\n### Added\n\n- ok\n- " + "x" * 501 + "\n")
        self.assertEqual([e["line"] for e in errors], [8])

    def test_template_comments_ignored(self):
        doc = self.valid("## Release Notes\n\n<!-- guidance\nover two lines -->\nS.\n\n### Added\n\n<!-- items go here -->\n- A\n")
        self.assertEqual(doc["summary"], "S.")
        self.assertEqual(texts(doc, "added"), ["A"])

    def test_comment_only_section_has_no_summary(self):
        errors = self.invalid("## Release Notes\n\n<!-- only the template comment -->\n")
        self.assertIn("summary", errors[0]["message"])

    def test_indented_continuation_joined(self):
        doc = self.valid("## Release Notes\n\nS.\n\n### Added\n\n- first part\n  second part\n+ plus item\n* star item\n")
        self.assertEqual(texts(doc, "added"), ["first part second part", "plus item", "star item"])

    def test_unindented_line_after_item_invalid(self):
        errors = self.invalid("## Release Notes\n\nS.\n\n### Fixed\n\n- item\nstray line\n")
        self.assertEqual([e["line"] for e in errors], [8])

    def test_two_paragraph_summary_joined(self):
        doc = self.valid("## Release Notes\n\nFirst sentence.\n\nSecond   sentence.\n\n### Added\n\n- A\n")
        self.assertEqual(doc["summary"], "First sentence. Second sentence.")


class TestNotesCommand(Notes):
    def test_valid_section_exit_0(self):
        # runs from a directory that is no git repository: no git call, and no opt-in needed
        doc = self.valid("## Release Notes\n\nS.\n\n### Added\n\n- New --dry-run flag\n- Bounded push (#111)\n")
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["summary"], "S.")
        self.assertEqual(doc["items"]["added"], [{"text": "New --dry-run flag", "line": "- New --dry-run flag (#<pr>)"},
                                                 {"text": "Bounded push (#111)", "line": "- Bounded push (#111)"}])

    def test_two_errors_exit_1(self):
        errors = self.invalid("## Release Notes\n\nS.\n\n### Security\n\n- a\n\n### Added\n\n- " + "x" * 501 + "\n")
        self.assertEqual(len(errors), 2, errors)
        self.assertIn("Security", errors[0]["message"])
        self.assertEqual([e["line"] for e in errors], [5, 11])

    def test_no_section_exit_1(self):
        code, doc, raw = self.notes_cmd("## Why\n\nx\n")
        self.assertEqual(code, 1, raw)
        self.assertEqual((doc["ok"], doc["error"]), (False, "no_release_notes"))

    def test_missing_file_exit_2(self):
        missing = self.tmp / "nope" / "proposal.md"
        code, doc, raw = self.release("notes", "--proposal", str(missing), cwd=self.tmp)
        self.assertEqual(code, 2, raw)
        self.assertIn(str(missing), doc["message"])

    def test_file_over_64kb_invalid(self):
        body = b"## Release Notes\n\nS.\n\n### Added\n\n- A\n" + b"x" * (70 * 1024)
        code, doc, raw = self.notes_cmd("", raw=body)
        self.assertEqual(code, 1, raw)
        self.assertEqual(doc["error"], "release_notes_invalid")
        self.assertIn("64 KB", json.dumps(doc["errors"]))


class TestNotes(Flow):
    def test_no_sections_gives_todays_notes_byte_for_byte(self):
        self.repo(version="0.4.0")
        self.tag("v0.4.0")
        fx.squash_merge(self.work, "zeta", "0.4.1", 1, why="Zeta first.", date="2026-10-11")
        fx.merge_commit(self.work, "alpha", "0.4.2", 2, why="Alpha second.", date="2026-10-09")
        doc = self.status("0.4.2")
        self.assertEqual(doc["notes"], "Changes in v0.4.2:\n\n- zeta (#1): Zeta first.\n- alpha (#2): Alpha second.")

    def test_backfill_boundary_counts_origin_only_tags(self):
        # A fresh clone that never fetched tags: v0.1.0 and v0.4.0 are only on origin. Backfilling 0.3.0 starts its range
        # at the highest lower tag, 0.1.0, not at the 0.2.0 value just before it.
        self.repo(version="0.0.9")
        c1 = fx.squash_merge(self.work, "add-a", "0.1.0", 1)
        fx.squash_merge(self.work, "add-b", "0.2.0", 2)
        fx.squash_merge(self.work, "add-c", "0.3.0", 3)
        c4 = fx.squash_merge(self.work, "add-d", "0.4.0", 4)
        fx.push(self.work)
        for name, at in (("v0.1.0", c1), ("v0.4.0", c4)):
            fx.git(self.work, "tag", "-a", name, "-m", name, at)
            fx.git(self.work, "push", "-q", "origin", f"refs/tags/{name}:refs/tags/{name}")
            fx.git(self.work, "tag", "-d", name)
        doc = self.status("0.3.0")
        self.assertEqual((doc["previous"]["version"], doc["previous"]["basis"]), ("0.1.0", "tag"))
        self.assertEqual([c["name"] for c in doc["changes"]], ["add-b", "add-c"])

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


class TestSectionedNotes(Flow):
    """Notes built from the `## Release Notes` sections of the archived proposals (specs/releases)."""

    def merge(self, change, version, pr, sec=None, tasks=None, date=fx.DATE, extra=None):
        files = change_files(change, sec, tasks, date)
        files.update(extra or {})
        return fx.squash_merge(self.work, change, version, pr, date=date, extra_files=files)

    def start(self, version="0.4.0"):
        self.repo(version=version)
        self.tag(f"v{version}")

    def test_one_change_with_section(self):
        self.start("0.4.0")
        self.merge("fix-m4-gaps", "0.4.1", 129, section("Closes the M4 gaps.", fixed=[f"Fix {i}" for i in range(1, 9)]))
        doc = self.status("0.4.1")
        self.assertEqual(doc["notes"], "Closes the M4 gaps.\n\nFixed:\n" + "\n".join(f"- Fix {i} (#129)" for i in range(1, 9)))
        self.assertEqual(doc["warnings"], [])

    def test_exact_layout_of_several_groups(self):
        self.start("0.4.0")
        self.merge("old-x", "0.4.1", 7)
        self.merge("new-y", "0.4.2", 8, section("S.", fixed=["F (#5)"], added=["A"]))
        doc = self.status("0.4.2")
        self.assertEqual(doc["notes"], "S.\n\nAdded:\n- A (#8)\n\nFixed:\n- F (#5)\n\nChanges:\n- old-x (#7): Why of old-x.")

    def test_two_changes_items_in_change_order(self):
        self.start("0.4.0")
        self.merge("add-a", "0.4.1", 1, section("Summary a.", added=["A1", "A2"]))
        self.merge("add-b", "0.4.2", 2, section("Summary b.", added=["B1"], removed=["R1"]))
        doc = self.status("0.4.2")
        self.assertEqual(doc["notes"], "Summary b.\n\nAdded:\n- A1 (#1)\n- A2 (#1)\n- B1 (#2)\n\nRemoved:\n- R1 (#2)")

    def test_mixed_section_and_why_line(self):
        self.start("0.4.0")
        self.merge("old-x", "0.4.1", 7)
        self.merge("new-y", "0.4.2", 8, section("Y.", changed=["C"]))
        doc = self.status("0.4.2")
        self.assertEqual(doc["notes"], "Y.\n\nChanged:\n- C (#8)\n\nChanges:\n- old-x (#7): Why of old-x.")
        self.assertEqual([c["name"] for c in doc["changes"]], ["old-x", "new-y"])

    def test_over_150_items_count_line(self):
        self.start("0.4.0")
        self.merge("old-x", "0.4.1", 7)
        sec = section("S.", added=[f"a{i} (#1)" for i in range(100)], fixed=[f"f{i} (#1)" for i in range(50)],
                      removed=[f"r{i} (#1)" for i in range(20)])
        self.merge("big", "0.4.2", 8, sec)
        notes = self.status("0.4.2")["notes"]
        want = ("S.\n\nAdded:\n" + "\n".join(f"- a{i} (#1)" for i in range(100)) + "\n\nFixed:\n"
                + "\n".join(f"- f{i} (#1)" for i in range(50)) + "\n…and 20 more items\n\nChanges:\n- old-x (#7): Why of old-x.")
        self.assertEqual(notes, want)
        self.assertNotIn("Removed:", notes)

    def test_over_100_changes_keeps_bumping_summary(self):
        self.start("0.4.0")
        extra = {}
        for i in range(119):
            extra.update(fx.archive_files(f"c{i:03d}", f"Reason {i}."))
        self.merge("z-bump", "0.4.1", 9, section("Bump summary.", fixed=["Z item (#2)"]), bump_task("0.4.1"), extra=extra)
        doc = self.status("0.4.1")
        self.assertEqual(len(doc["changes"]), 120)
        notes = doc["notes"]
        self.assertTrue(notes.startswith("Bump summary.\n\nFixed:\n- Z item (#2)\n\nChanges:\n- c000\n"), notes[:120])
        self.assertIn("\n- c099\n", notes)
        self.assertNotIn("c100", notes)
        self.assertNotIn("Reason", notes)
        self.assertTrue(notes.endswith("\n- c099\n…and 19 more"), notes[-60:])

    def test_summary_from_bump_task_in_same_commit(self):
        self.start("0.8.0")
        extra = {**change_files("b-bump", section("Bump summary.", added=["B item"]), bump_task("0.9.0")),
                 **change_files("c-other", section("Other summary.", added=["C item"]))}
        fx.squash_merge(self.work, "a-first", "0.9.0", 5, extra_files=extra)
        notes = self.status("0.9.0")["notes"]
        self.assertTrue(notes.startswith("Bump summary.\n\nAdded:\n"), notes)
        self.assertNotIn("Other summary.", notes)
        self.assertIn("- B item (#5)\n- C item (#5)", notes)

    def test_summary_from_last_section_without_bump_task(self):
        # an unticked bump task and one for another version do not count; the last valid section wins
        self.start("0.8.0")
        self.merge("add-a", "0.8.5", 1, section("Summary a.", added=["A"]), "- [ ] 3.1 `release.sh bump --to 0.9.0`\n")
        self.merge("add-b", "0.9.0", 2, section("Summary b.", added=["B"]), bump_task("0.8.5"))
        self.assertTrue(self.status("0.9.0")["notes"].startswith("Summary b.\n"))

    def test_summary_from_earlier_when_bumper_has_none(self):
        self.start("0.8.0")
        self.merge("add-a", "0.8.5", 1, section("Summary a.", added=["A"]))
        self.merge("b-bump", "0.9.0", 2, None, bump_task("0.9.0"))
        self.assertEqual(self.status("0.9.0")["notes"], "Summary a.\n\nAdded:\n- A (#1)\n\nChanges:\n- b-bump (#2): Why of b-bump.")

    def item_notes(self, item, pr=140):
        self.start("0.4.0")
        self.merge("add-a", "0.4.1", pr, section("S.", added=[item]))
        return self.status("0.4.1")["notes"]

    def test_unreferenced_item_gets_pr(self):
        self.assertEqual(self.item_notes("New --dry-run flag"), "S.\n\nAdded:\n- New --dry-run flag (#140)")

    def test_referenced_item_unchanged(self):
        self.assertEqual(self.item_notes("Bounded tag push (#111)"), "S.\n\nAdded:\n- Bounded tag push (#111)")

    def test_other_repo_reference_unchanged(self):
        self.assertEqual(self.item_notes("Thanks to acme/tool#12"), "S.\n\nAdded:\n- Thanks to acme/tool#12")

    def test_code_span_reference_does_not_count(self):
        self.assertEqual(self.item_notes("Parse `#123` comments"), "S.\n\nAdded:\n- Parse `#123` comments (#140)")

    def test_no_pr_item_as_written(self):
        self.start("0.4.0")
        fx.git(self.work, "checkout", "-q", "-b", "feat/add-a")
        fx.set_version(self.work, "0.4.1")
        fx.commit(self.work, "feat(add-a): do add-a", change_files("add-a", section("S.", added=["New --dry-run flag"])))
        fx.git(self.work, "checkout", "-q", "main")
        fx.git(self.work, "merge", "-q", "--no-ff", "-m", "merge: add-a", "feat/add-a")
        self.assertEqual(self.status("0.4.1")["notes"], "S.\n\nAdded:\n- New --dry-run flag")

    def test_valid_sections_empty_warnings(self):
        self.start("0.4.0")
        self.merge("add-a", "0.4.1", 1, section("S.", added=["A"]))
        self.assertEqual(self.status("0.4.1")["warnings"], [])

    def test_proposal_over_64kb_falls_back_keeps_why(self):
        self.repo(version="0.4.1")
        files = change_files("add-x", section("S.", added=["A"]), pad=6000)
        self.assertGreater(len(files["openspec/changes/archive/2026-10-10-add-x/proposal.md"]), 70 * 1024)
        fx.squash_merge(self.work, "add-x", "0.4.2", 9, extra_files=files)
        doc = self.status("0.4.2")
        self.assertEqual(doc["notes"], "Changes in v0.4.2:\n\n- add-x (#9): Why of add-x.")
        self.assertEqual([w["change"] for w in doc["warnings"]], ["add-x"])
        self.assertIn("64 KB", doc["warnings"][0]["error"])


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

    def test_local_flag_reads_no_remote(self):
        # origin is unreachable and git traces every process it starts: --local exits 0 and no ls-remote ran
        self.repo(version="0.4.2")
        self.tag("v0.4.2", push=False)
        fx.squash_merge(self.work, "a", "0.5.0", 1)
        fx.git(self.work, "config", "remote.origin.url", str(self.tmp / "does-not-exist.git"))
        trace = self.tmp / "trace.log"
        env = {**os.environ, "GIT_TRACE": str(trace)}
        code, doc, raw = self.release("untagged", "--local", env=env)
        self.assertEqual(code, 0, raw)
        self.assertEqual([u["version"] for u in doc["untagged"]], ["0.5.0"])
        self.assertEqual(doc["tags"], "local")
        self.assertTrue(trace.is_file() and trace.stat().st_size > 0, "git trace is empty: the test would prove nothing")
        self.assertNotIn("ls-remote", trace.read_text(encoding="utf-8", errors="replace"))

    def test_local_flag_counts_local_tag_and_says_so(self):
        # v0.5.0 exists only locally (its push failed): --local counts it, and the output says the list is from local tags
        self.repo(version="0.4.2")
        self.tag("v0.4.2")
        fx.squash_merge(self.work, "a", "0.5.0", 1)
        self.tag("v0.5.0", push=False)
        doc = self.untagged("--local")
        self.assertEqual(doc["untagged"], [])
        self.assertEqual(doc["latest_tagged"], "0.5.0")
        self.assertEqual(doc["tags"], "local")
        self.assertEqual(self.untagged()["tags"], "origin")
        self.assertEqual([u["version"] for u in self.untagged()["untagged"]], ["0.5.0"])

    def test_without_origin_reports_local_tags(self):
        self.repo(version="0.5.0")
        fx.git(self.work, "remote", "remove", "origin")
        self.tag("v0.5.0", push=False)
        self.assertEqual(self.untagged()["tags"], "local")


class TestCheckMain(Flow):
    """check --main <ref>: a bumped branch must be greater than <ref>'s version (design D3)."""

    def branch(self, name="feat/b", at=None):
        fx.git(self.work, "checkout", "-q", "-b", name, *([at] if at else []))

    def bump_branch(self, version, change="b"):
        fx.set_version(self.work, version)
        fx.commit(self.work, f"feat({change}): bump", fx.archive_files(change))

    def two_bumps(self, branch_version="0.5.0", main_version="0.5.0"):
        """feat/a merged to main at main_version and pushed; feat/b (from the initial commit) bumped to branch_version."""
        self.repo(version="0.4.2")
        base = self.sha()
        fx.squash_merge(self.work, "a", main_version, 1)
        fx.push(self.work)
        self.branch("feat/b", base)
        self.bump_branch(branch_version)

    def check(self, *extra):
        return self.release("check", "--main", "origin/main", *extra)

    def test_duplicate_bump_refused(self):
        self.two_bumps()
        out = self.check()
        self.assertStops(out, "0.5.0", "bump")
        self.assertEqual(out[1]["error"], "version_not_ahead_of_main")
        self.assertIn("origin/main", out[1]["message"])

    def test_main_ahead_refused(self):
        self.two_bumps(branch_version="0.5.0", main_version="0.6.0")
        out = self.check()
        self.assertStops(out, "0.5.0", "0.6.0")
        self.assertEqual(out[1]["error"], "version_not_ahead_of_main")

    def test_bump_ahead_passes(self):
        self.repo(version="0.4.2")
        self.branch()
        self.bump_branch("0.5.0")
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual((doc["ok"], doc["version"]), (True, "0.5.0"))

    def test_no_bump_passes(self):
        self.repo(version="0.4.2")
        base = self.sha()
        fx.squash_merge(self.work, "a", "0.5.0", 1)
        fx.push(self.work)
        self.branch("feat/b", base)
        fx.commit(self.work, "feat(b): work", {"src/b.txt": "b\n"})
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")

    def test_version_file_edit_without_bump_passes(self):
        self.repo(version="0.4.2")
        base = self.sha()
        fx.squash_merge(self.work, "a", "0.5.0", 1)
        fx.push(self.work)
        self.branch("feat/b", base)
        fx.commit(self.work, "feat(b): note in VERSION", {"VERSION": "0.4.2\nchannel: stable\n"})
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")

    def test_bump_reverted_on_branch_passes(self):
        self.repo(version="0.4.2")
        base = self.sha()
        fx.squash_merge(self.work, "a", "0.5.0", 1)
        fx.push(self.work)
        self.branch("feat/b", base)
        self.bump_branch("0.5.0")
        fx.set_version(self.work, "0.4.2")
        fx.git(self.work, "commit", "-q", "-am", "feat(b): drop the bump")
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")

    def test_duplicate_after_main_merged_in_refused(self):
        self.two_bumps()
        fx.git(self.work, "merge", "-q", "--no-edit", "origin/main")
        self.assertEqual(fx.git(self.work, "rev-list", "--min-parents=2", "-n1", "HEAD").strip() != "", True)
        out = self.check()
        self.assertStops(out, "0.5.0", "bump")
        self.assertEqual(out[1]["error"], "version_not_ahead_of_main")

    def test_main_without_version_passes(self):
        self.repo(version="0.4.2")
        fx.git(self.work, "rm", "-q", "VERSION")
        fx.git(self.work, "commit", "-q", "-m", "drop VERSION")
        fx.push(self.work)
        self.branch()
        self.bump_branch("0.1.0")
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.1.0")

    def test_main_with_duplicate_version_match_passes(self):
        # main's primary file matches its pattern twice: not exactly one match, so main has no readable version
        self.repo(version="0.4.2")
        base = self.sha()
        fx.commit(self.work, "chore: VERSION twice", {"VERSION": "0.5.0\n0.5.0\n"})
        fx.push(self.work)
        self.branch("feat/b", base)
        self.bump_branch("0.5.0")
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.5.0")

    def unreadable_base(self):
        """The merge base's VERSION holds 0.4.2 twice (unreadable); main then moves to 0.5.0 and feat/b starts at the base."""
        self.repo(version="0.4.2")
        fx.commit(self.work, "chore: VERSION twice", {"VERSION": "0.4.2\n0.4.2\n"})
        base = self.sha()
        fx.squash_merge(self.work, "a", "0.5.0", 1)
        fx.push(self.work)
        self.branch("feat/b", base)

    def test_unreadable_base_dedupe_is_no_bump(self):
        self.unreadable_base()
        fx.commit(self.work, "fix(b): drop the duplicate", {"VERSION": "0.4.2\n"})
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")

    def test_repair_then_bump_refused_when_behind(self):
        self.unreadable_base()
        fx.commit(self.work, "fix(b): drop the duplicate", {"VERSION": "0.4.2\n"})
        self.bump_branch("0.5.0")
        out = self.check()
        self.assertStops(out, "0.5.0", "bump")
        self.assertEqual(out[1]["error"], "version_not_ahead_of_main")
        self.assertEqual((out[1]["version"], out[1]["main_version"]), ("0.5.0", "0.5.0"))

    def test_repair_and_bump_in_one_commit_refused(self):
        self.unreadable_base()
        self.bump_branch("0.5.0")
        out = self.check()
        self.assertStops(out, "0.5.0", "bump")
        self.assertEqual(out[1]["error"], "version_not_ahead_of_main")
        self.assertEqual((out[1]["version"], out[1]["main_version"]), ("0.5.0", "0.5.0"))

    def test_bump_reverted_through_unreadable_passes(self):
        # Review round 2, M1: a hand revert that leaves VERSION unreadable still changed the version, so the walk must not
        # skip it and count the older bump.
        self.repo(version="0.4.2")
        base = self.sha()
        fx.squash_merge(self.work, "a", "0.5.0", 1)
        fx.push(self.work)
        self.branch("feat/b", base)
        self.bump_branch("0.5.0")
        fx.set_version(self.work, "0.4.2")
        fx.write(self.work, "VERSION", "0.4.2\n0.4.2\n")
        fx.git(self.work, "commit", "-q", "-am", "feat(b): drop the bump, VERSION twice")
        fx.commit(self.work, "fix(b): drop the duplicate", {"VERSION": "0.4.2\n"})
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")

    def at_main(self, version="0.5.0", main_version=None):
        """origin/main and the merge base read `version`; feat/b starts there. With main_version, main then moves to it."""
        self.repo(version=version)
        base = self.sha()
        if main_version:
            fx.squash_merge(self.work, "a", main_version, 1)
        fx.push(self.work)
        self.branch("feat/b", base)

    def test_bump_reverted_between_two_unreadable_passes(self):
        # D9: 0.6.0 twice, then 0.5.0 twice, then one 0.5.0: the middle commit reverted the bump through an unreadable version.
        self.at_main()
        fx.commit(self.work, "feat(b): VERSION twice", {"VERSION": "0.6.0\n0.6.0\n"})
        fx.commit(self.work, "feat(b): revert, VERSION twice", {"VERSION": "0.5.0\n0.5.0\n"})
        fx.commit(self.work, "fix(b): drop the duplicate", {"VERSION": "0.5.0\n"})
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.5.0")

    def test_unreadable_bump_reverted_by_readable_passes(self):
        # D9: 0.6.0 twice (unreadable), then a readable 0.5.0: a change judged against 0.5.0, so no bump.
        self.at_main()
        fx.commit(self.work, "feat(b): VERSION twice", {"VERSION": "0.6.0\n0.6.0\n"})
        fx.commit(self.work, "feat(b): revert", {"VERSION": "0.5.0\n"})
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.5.0")

    def test_unreadable_edit_keeping_versions_still_bumps(self):
        # D9: an unreadable edit that keeps the matched versions is no change; the bump to 0.6.0 stands and main has 0.6.0.
        self.at_main("0.5.0", "0.6.0")
        fx.commit(self.work, "feat(b): VERSION twice", {"VERSION": "0.6.0\n0.6.0\n"})
        fx.commit(self.work, "feat(b): VERSION three times", {"VERSION": "0.6.0\n0.6.0\n0.6.0\n"})
        fx.commit(self.work, "fix(b): one line", {"VERSION": "0.6.0\n"})
        fx.git(self.work, "merge", "-q", "--no-edit", "origin/main")
        out = self.check()
        self.assertStops(out, "0.6.0", "origin/main")
        self.assertEqual(out[1]["error"], "version_not_ahead_of_main")

    def test_bump_reverted_by_lower_of_unreadable_set(self):
        # PR #108, Codex P2: from a merge base reading 0.4.2 and 0.5.0, the branch bumps to 0.6.0, lists 0.6.0 and 0.5.0,
        # then keeps 0.5.0: keeping the lower of its parent's versions drops the bump, so the older bump must not count.
        self.repo(version="0.4.2")
        fx.commit(self.work, "chore: VERSION lists two", {"VERSION": "0.4.2\n0.5.0\n"})
        base = self.sha()
        fx.squash_merge(self.work, "a", "0.5.0", 1)
        fx.push(self.work)
        self.branch("feat/b", base)
        self.bump_branch("0.6.0")
        fx.commit(self.work, "feat(b): VERSION lists two", {"VERSION": "0.6.0\n0.5.0\n"})
        fx.set_version(self.work, "0.5.0")
        fx.git(self.work, "commit", "-q", "-am", "feat(b): keep 0.5.0")
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.5.0")

    def test_dedupe_to_highest_of_unreadable_set_keeps_bump(self):
        # The same walk still counts a bump that a later dedupe keeps: 0.6.0 is the highest of 0.6.0 and 0.5.0.
        self.repo(version="0.4.2")
        base = self.sha()
        fx.squash_merge(self.work, "a", "0.6.0", 1)
        fx.push(self.work)
        self.branch("feat/b", base)
        self.bump_branch("0.6.0")
        fx.commit(self.work, "feat(b): VERSION lists two", {"VERSION": "0.6.0\n0.5.0\n"})
        fx.commit(self.work, "fix(b): drop the duplicate", {"VERSION": "0.6.0\n"})
        out = self.check()
        self.assertEqual(out[1]["error"], "version_not_ahead_of_main", out[2])

    def test_bump_through_unreadable_then_main_merged_refused(self):
        # PR #108, Codex P2 (round 5): 0.4.2 -> 0.4.2 and 0.5.0 -> 0.5.0 is a bump made through an unreadable version;
        # after main, already at 0.5.0, is merged in, the duplicate must still be refused.
        self.repo(version="0.4.2")
        base = self.sha()
        fx.squash_merge(self.work, "a", "0.5.0", 1)
        fx.push(self.work)
        self.branch("feat/b", base)
        fx.commit(self.work, "feat(b): VERSION lists two", {"VERSION": "0.4.2\n0.5.0\n"})
        fx.commit(self.work, "fix(b): keep 0.5.0", {"VERSION": "0.5.0\n"})
        fx.git(self.work, "merge", "-q", "--no-edit", "origin/main")
        out = self.check()
        self.assertStops(out, "0.5.0", "bump")
        self.assertEqual(out[1]["error"], "version_not_ahead_of_main")

    def test_main_base_repaired_on_both_sides_passes(self):
        # Design review round 3, M1: the branch repairs main's broken VERSION to 0.5.0, as main later does: no release.
        self.repo(version="0.4.2")
        fx.commit(self.work, "chore: VERSION lists two", {"VERSION": "0.4.2\n0.5.0\n"})
        base = self.sha()
        fx.set_version(self.work, "0.5.0")
        fx.git(self.work, "commit", "-q", "-am", "fix: keep 0.5.0")
        fx.push(self.work)
        self.branch("feat/b", base)
        fx.set_version(self.work, "0.5.0")
        fx.git(self.work, "commit", "-q", "-am", "fix(b): keep 0.5.0")
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.5.0")

    def test_stray_version_line_removed_passes(self):
        # Design review round 3, M1: a stray 0.4.2 line added and then removed on a branch at 0.5.0 is no bump.
        self.repo(version="0.5.0")
        fx.push(self.work)
        self.branch("feat/b", self.sha())
        fx.commit(self.work, "chore(b): stray line", {"VERSION": "0.5.0\n0.4.2\n"})
        fx.commit(self.work, "fix(b): drop the stray line", {"VERSION": "0.5.0\n"})
        code, doc, raw = self.check()
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.5.0")

    def test_without_main_unchanged(self):
        self.two_bumps()
        code, doc, raw = self.release("check")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.5.0")

    def test_agreement_checked_first(self):
        self.two_bumps()
        fx.write(self.work, "README.md", fx.readme_text("0.9.9"))
        out = self.check()
        self.assertEqual(out[1]["error"], "version_files_disagree", out[2])

    def test_missing_ref(self):
        self.repo()
        self.assertEqual(self.release("check", "--main", "origin/nope")[1]["error"], "no_main")


GH_SCRIPT = '#!/bin/sh\nexec "{}" "{}" "$@"\n'  # this interpreter runs the fake: a POSIX host may have no `python`
CODE_SLUG = "acme/code"


class GhFlow(Flow):
    """A `gh` shim on PATH backed by evals/fakes/gh.py, and a code repo whose origin looks like github.com but reaches a
    local bare repository through `url.<bare>.insteadOf`."""

    def setUp(self):
        super().setUp()
        (self.tmp / "bin").mkdir()
        gh = self.tmp / "bin" / "gh"
        gh.write_text(GH_SCRIPT.format(Path(sys.executable).resolve().as_posix(), (ROOT / "evals" / "fakes" / "gh.py").resolve().as_posix()),
                      encoding="utf-8", newline="\n")
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



class TestSectionedStoreNotes(GhFlow):
    def test_store_backed_sections(self):
        self.repo(version="0.4.1")
        self.connect()
        store = fx.make_store(self.tmp, [])
        for rel, text in change_files("add-x", section("Store summary.", added=["Store item"]), bump_task("0.4.2")).items():
            fx.write(store, rel, text)
        fx.git(store, "add", "-A")
        fx.git(store, "commit", "-q", "-m", "archive add-x")
        sha = fx.squash_merge(self.work, "add-x", "0.4.2", 90)
        TestStoreNotes.pull(self, 90, "add-x", sha)
        self.save()
        code, doc, raw = self.release("status", "--version", "0.4.2", "--store", str(store), env=self.env())
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["notes"], "Store summary.\n\nAdded:\n- Store item (#90)")
        self.assertEqual(doc["warnings"], [])


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

    def test_push_url_elsewhere_stops(self):
        # A push URL naming another repository (an upstream/fork setup) would put the tag where publish never checked it.
        fork = self.tmp / "fork.git"
        fx.git(self.tmp, "init", "-q", "--bare", str(fork))
        fx.git(self.work, "config", "remote.origin.pushurl", "https://github.com/someone/fork.git")
        fx.git(self.work, "config", f"url.{fork.as_posix()}.insteadOf", "https://github.com/someone/fork.git")
        code, doc, raw = self.publish()
        self.assertEqual(code, 1, raw)
        self.assertEqual(doc["error"], "push_url_mismatch")
        self.assertIn("pushes to", doc["message"])
        self.assertEqual(fx.git(self.work, "tag"), "")
        self.assertEqual(fx.git(self.bare, "tag"), "")
        self.assertEqual(fx.git(fork, "tag"), "")
        self.assertEqual(self.gh_calls(), [])
        # a push URL that names origin itself is fine
        fx.git(self.work, "config", "remote.origin.pushurl", f"https://github.com/{CODE_SLUG}.git")
        code, doc, raw = self.publish()
        self.assertEqual(code, 0, raw)
        self.assertEqual(fx.git(self.bare, "rev-parse", f"{self.TAG}^{{commit}}"), self.rc)

    def test_rewrite_to_another_github_repo_stops(self):
        # insteadOf turns acme/ into me/: the tag would go to me/code while the release names acme/code. Publish stops
        # before any network read.
        fx.git(self.work, "config", "--unset", f"url.{self.bare.as_posix()}.insteadOf")
        fx.git(self.work, "config", "url.https://github.com/me/.insteadOf", "https://github.com/acme/")
        code, doc, raw = self.publish()
        self.assertEqual(code, 1, raw)
        self.assertEqual(doc["error"], "push_url_mismatch")
        self.assertIn("github.com/me/code", doc["message"])
        self.assertEqual(fx.git(self.work, "tag"), "")
        self.assertEqual(self.gh_calls(), [])

    def test_lost_push_race_stops(self):
        # Origin holds another clone's tag object at the release commit; the local one lost the push. Publish stops
        # rather than release with the local message, and after `git tag -d` a re-run fetches origin's tag.
        self.seed_tag(local=False, message="Origin notes\n")
        origin_obj = self.remote(self.TAG).splitlines()[0].split()[0]
        fx.git(self.work, "tag", "-a", self.TAG, "-m", "Local notes", self.rc)
        local_obj = self.obj()
        code, doc, raw = self.publish()
        self.assertEqual(code, 1, raw)
        self.assertEqual(doc["error"], "tag_mismatch")
        for needle in (local_obj[:12], origin_obj[:12], f"git tag -d {self.TAG}"):
            self.assertIn(needle, doc["message"])
        self.assertEqual(self.obj(), local_obj)
        self.assertEqual(self.gh_calls(), [])
        self.assertEqual(self.releases(), {})
        fx.git(self.work, "tag", "-d", self.TAG)
        code, doc, raw = self.publish()
        self.assertEqual(code, 0, raw)
        self.assertEqual((doc["tag_local"], doc["tag_remote"]), ("fetched", "existing"))
        self.assertEqual(self.releases()[self.TAG]["body"].strip(), "Origin notes")

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


class TestSectionedPublish(PubFlow):
    def bad_release(self):
        """v0.5.0 is published; 0.5.1 merges `bad-y` with an unknown `### Security` heading."""
        self.seed_tag()
        files = change_files("bad-y", section("Y.", added=["A"]).replace("### Added", "### Security"))
        fx.squash_merge(self.work, "bad-y", "0.5.1", 8, extra_files=files)

    def test_invalid_section_falls_back_with_warning(self):
        self.bad_release()
        code, doc, raw = self.publish("0.5.1")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["tag_local"], "created")
        self.assertEqual(doc["notes"], "Changes in v0.5.1:\n\n- bad-y (#8): Why of bad-y.")
        self.assertEqual([w["change"] for w in doc["warnings"]], ["bad-y"])
        self.assertIn("Security", doc["warnings"][0]["error"])
        self.assertEqual(self.contents("v0.5.1").strip(), doc["notes"])

    def test_rerun_after_tag_reports_no_warnings(self):
        self.bad_release()
        self.assertEqual(self.publish("0.5.1")[0], 0)
        code, doc, raw = self.publish("0.5.1")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["tag_local"], "existing")
        self.assertEqual(doc["warnings"], [])
        self.assertEqual(doc["notes"], "Changes in v0.5.1:\n\n- bad-y (#8): Why of bad-y.")


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

    def test_shorthand_rewritten_to_github_creates_release(self):
        # origin is a non-GitHub shorthand that insteadOf expands to github.com: git reaches GitHub, so the release is
        # created there and not skipped as not_github. A fake ssh serves the github.com URL from the local bare repo.
        fx.git(self.work, "config", "--unset", f"url.{self.bare.as_posix()}.insteadOf")
        fx.git(self.work, "config", "remote.origin.url", "corp:acme/code")
        fx.git(self.work, "config", "url.ssh://git@github.com/.insteadOf", "corp:")
        ssh = self.tmp / "fake-ssh"
        ssh.write_text('#!/bin/sh\nfor last; do :; done\ncase "$last" in\n'
                       f'  git-upload-pack*) exec git upload-pack "{self.bare.as_posix()}";;\n'
                       f'  git-receive-pack*) exec git receive-pack "{self.bare.as_posix()}";;\nesac\nexit 1\n',
                       encoding="utf-8", newline="\n")
        env = {**self.env(), "GIT_SSH_COMMAND": f'sh "{ssh.as_posix()}"', "GIT_SSH_VARIANT": "ssh"}
        code, doc, raw = self.publish(env=env)
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["github_release"], "created")
        create = self.creates()[0]["argv"]
        self.assertEqual(create[create.index("--repo") + 1], CODE_SLUG)
        self.assertEqual(fx.git(self.bare, "rev-parse", f"{self.TAG}^{{commit}}"), self.rc)


class TestBoundedNetwork(PubFlow):
    """Publish's network commands run under a deadline and a byte bound; a cut-off write is decided by a read-back."""

    DEADLINE = 5  # for the tests where a hook or the fake gh must get its work done before the cut-off, on a loaded machine
    LIMIT = 40  # seconds a red test may take before it fails instead of hanging the suite

    def setUp(self):
        super().setUp()
        self.beat = self.tmp / "beat"
        self.hang = self.tmp / "hang.sh"  # beats a counter for at most 30 s: a process that was not stopped keeps it moving
        self.script(self.hang, f"i=0\nwhile [ $i -lt 100 ]; do echo $i > '{self.beat.as_posix()}'; sleep 0.3; i=$((i+1)); done\n")

    # a pre-receive hook may not update refs inside git's quarantine environment; another clone's push did not run in it
    UNQUARANTINE = "unset GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES\n"

    def script(self, path, body):
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8", newline="\n")
        path.chmod(0o755)

    def hook(self, name, body):
        self.script(self.bare / "hooks" / name, body)

    def run_publish(self, *extra, env=None, deadline=None):
        """publish under SPECWRIGHT_NET_DEADLINE (DEADLINE seconds) and a timeout of its own; returns (code, doc, raw, seconds)."""
        self.save()
        e = {**self.env(), "SPECWRIGHT_NET_DEADLINE": str(deadline or self.DEADLINE), **(env or {})}
        t0 = time.time()
        try:
            r = subprocess.run([bashexe.bash(), str(SCRIPT), "publish", "--version", "0.5.0", *extra], cwd=self.work, env=e,
                               capture_output=True, text=True, encoding="utf-8", timeout=self.LIMIT)
        except subprocess.TimeoutExpired:
            self.fail(f"publish still running after {self.LIMIT} s: a bound did not stop it")
        try:
            doc = json.loads(r.stdout)
        except ValueError:
            doc = None
        return r.returncode, doc, r.stdout + r.stderr, time.time() - t0

    def assertNothingRunning(self):
        time.sleep(1.0)
        first = self.beat.read_text() if self.beat.exists() else None
        time.sleep(1.0)
        self.assertEqual(first, self.beat.read_text() if self.beat.exists() else None, "a hung process was left running")

    def other_object(self, commit):
        """A tag object at `commit` that exists in origin's object store (under a non-tag ref) and not in the work tree."""
        fx.git(self.work, "tag", "-a", "other-clone", "-m", "another clone notes", commit)
        obj = self.obj("other-clone")
        fx.git(self.work, "push", "-q", "origin", "refs/tags/other-clone:refs/holder/other")
        fx.git(self.work, "tag", "-d", "other-clone")
        return obj

    def test_untagged_within_deadline_names_no_limit(self):
        self.save()
        r = subprocess.run([bashexe.bash(), str(SCRIPT), "untagged"], cwd=self.work, capture_output=True, text=True, encoding="utf-8",
                           env={**self.env(), "SPECWRIGHT_NET_DEADLINE": "30"}, timeout=self.LIMIT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual([u["version"] for u in doc["untagged"]], ["0.5.0"])
        self.assertNotIn("deadline_exceeded", r.stdout + r.stderr)
        self.assertNotIn("response_too_large", r.stdout + r.stderr)

    def test_publish_hung_ls_remote_deadline_exceeded(self):
        fx.git(self.work, "config", "remote.origin.uploadpack", f"sh {self.hang.as_posix()}")
        code, doc, raw, took = self.run_publish(deadline=1)
        self.assertEqual(code, 3, raw)
        self.assertEqual((doc["ok"], doc["error"]), (False, "deadline_exceeded"), raw)
        self.assertIn("git ls-remote", doc["message"])
        self.assertLess(took, 1 + 10)
        self.assertEqual(fx.git(self.work, "tag", "-l"), "")
        self.assertEqual(fx.git(self.bare, "tag", "-l"), "")
        self.assertEqual(self.gh_calls(), [])
        self.assertNothingRunning()

    def test_publish_oversized_pr_read_response_too_large(self):
        store = fx.make_store(self.tmp, [("add-x", "X reason.", False)])
        self.state["flood"] = [{"match": "api --paginate", "bytes": 300000}]
        code, doc, raw, _ = self.run_publish("--store", str(store),
                                             env={"SPECWRIGHT_NET_MAX_BYTES": "100000", "SPECWRIGHT_NET_DEADLINE": "30"})
        self.assertEqual(code, 3, raw)
        self.assertEqual((doc["ok"], doc["error"]), (False, "response_too_large"), raw)
        self.assertIn("gh api", doc["message"])
        self.assertEqual(fx.git(self.work, "tag", "-l"), "")
        self.assertEqual(fx.git(self.bare, "tag", "-l"), "")
        self.assertEqual(self.creates(), [])

    def test_push_cut_off_after_landing_counts_done(self):
        self.hook("post-receive", f"sh '{self.hang.as_posix()}'\n")  # the ref is updated, then the push never ends
        code, doc, raw, took = self.run_publish()
        self.assertEqual(code, 0, raw)
        self.assertEqual((doc["tag_local"], doc["tag_remote"], doc["github_release"]), ("created", "pushed", "created"))
        self.assertEqual(fx.git(self.bare, "rev-parse", f"{self.TAG}^{{commit}}"), self.rc)
        self.assertEqual(fx.git(self.bare, "rev-parse", self.TAG), self.obj())
        self.assertEqual(len(self.creates()), 1)
        self.assertNothingRunning()

    def test_push_cut_off_other_tag_object_is_tag_mismatch(self):
        other = self.other_object(self.rc)
        self.hook("pre-receive", f"{self.UNQUARANTINE}git update-ref refs/tags/{self.TAG} {other}\nsh '{self.hang.as_posix()}'\n")
        code, doc, raw, _ = self.run_publish()
        self.assertEqual(code, 1, raw)
        self.assertEqual((doc["ok"], doc["error"]), (False, "tag_mismatch"), raw)
        self.assertIn(other[:12], doc["message"])
        self.assertIn(self.obj()[:12], doc["message"])
        self.assertEqual(self.gh_calls(), [])
        self.assertNothingRunning()

    def test_push_cut_off_other_commit_is_tag_conflict(self):
        other = self.other_object(self.base)
        self.hook("pre-receive", f"{self.UNQUARANTINE}git update-ref refs/tags/{self.TAG} {other}\nsh '{self.hang.as_posix()}'\n")
        code, doc, raw, _ = self.run_publish()
        self.assertEqual(code, 1, raw)
        self.assertEqual((doc["ok"], doc["error"]), (False, "tag_conflict"), raw)
        self.assertIn(self.base, doc["message"])
        self.assertIn(self.rc, doc["message"])
        self.assertEqual(self.gh_calls(), [])
        self.assertNothingRunning()

    def test_release_create_cut_off_not_found(self):
        self.state["hang"] = [{"match": "release create", "pid_file": str(self.tmp / "gh.pid")}]
        code, doc, raw, took = self.run_publish()
        self.assertEqual(code, 3, raw)
        self.assertEqual((doc["ok"], doc["error"]), (False, "deadline_exceeded"), raw)
        self.assertIn("gh release create", doc["message"])
        self.assertIn("on origin", doc["message"])
        self.assertIn("re-run", doc["message"])
        self.assertIn(self.TAG, fx.git(self.bare, "tag", "-l"))
        self.assertTrue([c for c in self.gh_calls() if c["argv"][:2] == ["release", "view"]])  # the read-back
        self.assertEqual(self.releases(), {})

    def test_push_cut_off_read_back_fails_state_unknown(self):
        fail = self.tmp / "fail.sh"
        self.script(fail, "echo 'fatal: remote unreachable' >&2\nexit 1\n")
        self.hook("post-receive", f"unset GIT_DIR\ngit -C '{self.work.as_posix()}' config remote.origin.uploadpack 'sh {fail.as_posix()}'\n"
                  f"sh '{self.hang.as_posix()}'\n")
        code, doc, raw, _ = self.run_publish()
        self.assertEqual(code, 3, raw)
        self.assertEqual((doc["ok"], doc["error"], doc.get("state")), (False, "deadline_exceeded", "unknown"), raw)
        self.assertIn("unknown", doc["message"])
        self.assertIn("git push", doc["message"])
        self.assertEqual(self.gh_calls(), [])
        self.assertNothingRunning()


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
