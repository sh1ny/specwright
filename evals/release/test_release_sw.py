"""release.sh runs in the project's `sw` (native-cli-release): the Test map of openspec/changes/native-cli-release.

Every test runs `skills/specwright-release/scripts/release.sh` (RELEASE_SH overrides the path, as in test_release.py) on the
fixtures of fixtures.py. Each fixture repository carries the version stamp and the environment names SPECWRIGHT_HOME, so the
script's `sw` resolves; the script itself is started by an explicit real bash.

Needs the binary named by SPECWRIGHT_SW (skips as `sw not built` otherwise; fails under SPECWRIGHT_REQUIRE_SW=1).

Run: SPECWRIGHT_SW=<path> python -m unittest evals/release/test_release_sw.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "evals"))
sys.path.insert(0, str(ROOT / "evals" / "cli"))
import bashexe  # noqa: E402
import fakeexe  # noqa: E402
import test_no_shell  # noqa: E402  write_recorders
import test_release as tr  # noqa: E402  Base, PubFlow and the fake gh; the classes stay in that module

fx = tr.fx
LOG = test_no_shell.LOG  # the recorders append the name they were started as to $SW_NO_SHELL_LOG
DOT = r"^(\d+\.\d+\.\d+)$"

# The program of a python/python3 recorder. `sw-path.sh` (which the script runs to find `sw`) uses Python itself for its
# bounded version check (`-c ...` and `-I ...`); those calls pass through to the real interpreter. Any other start of
# Python, such as the old script's `python -I -X utf8 -`, is logged and fails.
PY_RECORDER = '''import os, subprocess, sys

args = sys.argv[1:]
if args[:1] == ["-c"] or (args[:1] == ["-I"] and args[1:2] != ["-X"]):
    sys.exit(subprocess.call([%r] + args))
with open(os.environ[%r], "a") as log:
    log.write(%r + "\\n")
sys.exit(1)
'''


def doc_of(stdout):
    try:
        return json.loads(stdout)
    except ValueError:
        return None


class Sw(tr.Base):
    def stop(self, *args, **kw):
        """A call that must stop with `bad_version_files` or `bad_settings`: returns the document."""
        out = self.release(*args, **kw)
        self.assertEqual(out[0], 1, out[2])
        self.assertIs(out[1]["ok"], False, out[2])
        return out[1]

    def tags(self):
        return fx.git(self.work, "tag"), fx.git(self.tmp / "origin.git", "tag")


class TestRunsInSw(tr.PubFlow):
    """Publish with no Python, bash or sh for `sw` to start."""

    def recorders(self):
        directory = self.tmp / "failing"
        test_no_shell.write_recorders(directory, ("bash", "sh"))  # bare-bash: not started
        for name in ("python", "python3"):
            fakeexe.write_python_fake(directory / name, PY_RECORDER % (sys.executable, LOG, name))
        return directory

    def test_publish_runs_without_python_or_bash(self):
        directory = self.recorders()
        log = self.tmp / "started.log"
        # a probe first: every recorder records when started directly, so an empty log below means none started
        for name in ("bash", "sh", "python", "python3"):  # bare-bash: not started
            exe = directory / (name + (".cmd" if os.name == "nt" and name in ("bash", "sh") else ".exe" if os.name == "nt" else ""))  # bare-bash: not started
            r = subprocess.run([str(exe), "probe"], env={**os.environ, LOG: str(log)}, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1, f"{name}: {r.stdout}{r.stderr}")
        self.assertEqual(sorted(log.read_text(encoding="ascii").split()), ["bash", "python", "python3", "sh"])  # bare-bash: not started
        log.unlink()
        env = {**self.env(), LOG: str(log)}
        env["PATH"] = str(directory) + os.pathsep + env["PATH"]
        code, doc, raw = self.publish(env=env)
        started = log.read_text(encoding="ascii").split() if log.exists() else []
        self.assertEqual(started, [], "started: " + raw)
        self.assertEqual(code, 0, raw)
        self.assertEqual((doc["tag_local"], doc["tag_remote"], doc["github_release"]), ("created", "pushed", "created"), raw)
        self.assertEqual(fx.git(self.bare, "rev-parse", f"{self.TAG}^{{commit}}"), self.rc)
        self.assertEqual(len(self.creates()), 1, self.gh_calls())  # the fake gh made the release


class TestSwResolution(Sw):
    def test_gitbutler_backend_read_without_pr_pair(self):
        # a copy of the install without pr-pair.sh (and vcs.sh): the backend is read in process, so nothing looks for them
        self.repo()
        fx.write(self.work, "openspec/specwright.yaml", fx.settings_text(fx.DEFAULT_VERSION_FILES, extra="vcs: gitbutler\n"))
        skills = tr.SCRIPT.parents[2]
        copy = self.tmp / "install"
        for name in ("specwright-release", "specwright-pr"):
            shutil.copytree(skills / name / "scripts", copy / name / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        for gone in ("pr-pair.sh", "vcs.sh"):
            (copy / "specwright-pr" / "scripts" / gone).unlink()
        self.assertTrue((copy / "specwright-pr" / "scripts" / "sw-path.sh").is_file())
        r = subprocess.run([bashexe.bash(), str(copy / "specwright-release" / "scripts" / tr.SCRIPT.name), "check", "--main", "origin/main"],
                           cwd=self.work, capture_output=True, text=True, encoding="utf-8", env=fx.sw_env())
        doc = doc_of(r.stdout)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(doc["error"], "usage", r.stdout)
        self.assertIn("--branch", doc["message"])

    def test_status_matches_preport_document(self):
        # the document the Python script printed before the port (task 1.3): same fields, same values, apart from message wording
        fixture = json.loads((HERE / "fixtures" / "preport-status.json").read_text(encoding="utf-8"))
        self.work, commits = fx.preport_status_repo(self.tmp)
        self.assertEqual(commits, fixture["commits"])
        code, doc, raw = self.release("status", "--version", "0.5.0")
        self.assertEqual(code, 0, raw)
        want = dict(fixture["document"])
        for key in ("repo", "tag_repo"):  # `<work>` stands for the work tree
            self.assertEqual(Path(doc.pop(key)).resolve(), self.work.resolve())
            self.assertEqual(want.pop(key), "<work>")
        doc.pop("message", None)
        want.pop("message", None)
        self.assertEqual(doc, want)

    def test_untagged_sw_missing_starts_no_network(self):
        self.repo()
        log = self.tmp / "network.log"
        fakes = self.tmp / "recording"
        fakes.mkdir()
        for name in ("git", "gh"):
            fakeexe.write_fake(fakes / name, f'#!/bin/sh\necho "{name} $*" >> "$SW_FAKE_LOG"\nexit 1\n')
        probe = subprocess.run([str(fakes / ("git.cmd" if os.name == "nt" else "git")), "ls-remote", "probe"],
                               env={**os.environ, "SW_FAKE_LOG": str(log)}, capture_output=True, text=True)
        self.assertEqual(probe.returncode, 1, probe.stdout + probe.stderr)
        self.assertEqual(log.read_text(encoding="utf-8").strip(), "git ls-remote probe")  # the recorder records
        log.unlink()
        empty = self.tmp / "empty-home"
        empty.mkdir()
        for label, home, version in (("no sw in the home", empty, None), ("a stamp naming another version", None, "9.9.9")):
            with self.subTest(label):
                if version:
                    stamp = self.work / "openspec" / ".specwright" / "VERSION"
                    stamp.write_text(version + "\n", encoding="utf-8")
                env = {**os.environ, "SW_FAKE_LOG": str(log), "SPECWRIGHT_HOME": str(home or fx.sw_env()["SPECWRIGHT_HOME"])}
                env["PATH"] = str(fakes) + os.pathsep + env["PATH"]
                code, doc, raw = self.release("untagged", env=env)
                self.assertEqual(code, 1, raw)
                self.assertEqual((doc["ok"], doc["error"]), (False, "sw_missing"), raw)
                self.assertEqual(raw.count('"error"'), 1, raw)  # one document
                started = log.read_text(encoding="utf-8") if log.exists() else ""
                self.assertEqual(started.strip(), "", "started: " + started)


class TestVersionPatterns(Sw):
    def test_shipped_patterns_read_version(self):
        self.repo()
        code, doc, raw = self.release("check")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")
        self.assertEqual(sorted(doc["files"]), sorted(tr.VERSION_FILES))

    def test_crlf_version_read_and_bump_keeps_crlf(self):
        self.repo()
        (self.work / "VERSION").write_bytes(b"0.4.2\r\n")
        code, doc, raw = self.release("check")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")
        code, doc, raw = self.release("bump", "--to", "0.4.3")
        self.assertEqual(code, 0, raw)
        self.assertEqual((self.work / "VERSION").read_bytes(), b"0.4.3\r\n")

    def test_python_only_pattern_bad_version_files(self):
        calls = (("check",), ("bump", "--to", "0.4.3"), ("status", "--version", "0.4.2"), ("untagged",),
                 ("publish", "--version", "0.4.2"))
        for pattern in (r"(?P<v>\d+\.\d+\.\d+)", r"\A(\d+\.\d+\.\d+)", r"(\d+\.\d+\.\d+)\Z", r"(?i)^(\d+\.\d+\.\d+)$"):
            self.work = fx.make_repo(self.tmp / re.sub(r"\W", "_", pattern), version_files={"VERSION": pattern})
            before = fx.snapshot(self.work)
            tags = fx.git(self.work, "tag")
            for args in calls:
                with self.subTest(pattern=pattern, call=args[0]):
                    doc = self.stop(*args)
                    self.assertEqual(doc["error"], "bad_version_files", doc)
                    self.assertIn("VERSION", doc["message"])
                    self.assertEqual(fx.snapshot(self.work), before)
                    self.assertEqual(fx.git(self.work, "tag"), tags)
                    self.assertEqual(fx.git(self.tmp / re.sub(r"\W", "_", pattern) / "origin.git", "tag"), "")


class SettingsRows:
    BAD = {"a tab-indented line under release:": ("extra_release", "\tnote: x\n"),
           "a release: key given twice": ("extra", "release:\n  enabled: true\n")}

    def settings(self, how):
        field, text = self.BAD[how]
        fx.write(self.work, "openspec/specwright.yaml", fx.settings_text(fx.DEFAULT_VERSION_FILES, **{field: text}))
        lines = (self.work / "openspec" / "specwright.yaml").read_text(encoding="utf-8").split("\n")
        return lines.index(text.split("\n")[0]) + 1 if field == "extra_release" else len(lines) - 2  # the repeated key's line



class TestSettingsRows(Sw, SettingsRows):
    def test_shipped_settings_check_passes(self):
        self.repo()
        text = (self.work / "openspec" / "specwright.yaml").read_text(encoding="utf-8")
        self.assertIn("release:\n  enabled: true\n", text)
        code, doc, raw = self.release("check")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")

    def test_misreadable_settings_stop_before_git(self):
        self.repo()
        directory = self.tmp / "git-recorder"
        directory.mkdir()
        fakeexe.write_python_fake(directory / "git", 'import os, sys\nwith open(os.environ[%r], "a") as log:\n'
                                  '    log.write("git\\n")\nsys.exit(1)\n' % LOG)
        log = self.tmp / "git.log"
        env = {**os.environ, LOG: str(log), "PATH": str(directory) + os.pathsep + os.environ.get("PATH", "")}
        for how in self.BAD:
            for call in (("check",), ("bump", "--to", "0.4.3"), ("untagged", "--local")):
                with self.subTest(how=how, call=call):
                    line = self.settings(how)
                    code, doc, raw = self.release(*call, env=env)
                    self.assertEqual((code, doc and doc.get("error")), (1, "bad_settings"), raw)
                    self.assertIn("line %d" % line, doc["message"], raw)
                    self.assertFalse(log.exists() and log.read_text(encoding="ascii"), "git started: " + raw)

    def test_notes_ignores_misreadable_settings(self):
        self.repo()
        proposal = self.tmp / "proposal.md"
        proposal.write_text("## Why\n\nx\n\n## Release Notes\n\nS.\n\n### Added\n\n- New --dry-run flag\n", encoding="utf-8")
        for how in self.BAD:
            with self.subTest(how):
                self.settings(how)
                code, doc, raw = self.release("notes", "--proposal", str(proposal))
                self.assertEqual(code, 0, raw)
                self.assertEqual(doc["summary"], "S.")
                self.assertEqual([i["text"] for i in doc["items"]["added"]], ["New --dry-run flag"])


class TestPublishSettings(Sw, tr.PubFlow, SettingsRows):
    def test_misreadable_settings_publish_bad_settings(self):
        for how in self.BAD:
            with self.subTest(how):
                line = self.settings(how)
                code, doc, raw = self.publish()
                self.assertEqual(code, 1, raw)
                self.assertEqual((doc["ok"], doc["error"]), (False, "bad_settings"), raw)
                self.assertRegex(doc["message"], rf"(?<!\d){line}(?!\d)|{re.escape(self.BAD[how][1].strip().split(chr(10))[0])}")
                self.assertEqual(self.tags(), ("", ""))
                self.assertEqual(self.releases(), {})
                self.assertEqual(self.gh_calls(), [], "no network call before the settings are read")


class TestUtf8Rows(Sw):
    def malformed(self):
        self.repo()
        readme = fx.readme_text("0.4.2").encode("utf-8") + b"\xff\n"  # 0xFF outside the badge
        (self.work / "README.md").write_bytes(readme)
        return readme

    def test_bump_valid_utf8_files(self):
        self.repo()
        readme = (fx.readme_text("0.4.2") + "café ✓ naïve\n").encode("utf-8")
        (self.work / "README.md").write_bytes(readme)
        code, doc, raw = self.release("bump", "--to", "0.4.3")
        self.assertEqual(code, 0, raw)
        self.assertEqual((self.work / "README.md").read_bytes(), readme.replace(b"version-0.4.2-blue", b"version-0.4.3-blue"))
        code, doc, raw = self.release("check")
        self.assertEqual((code, doc["version"]), (0, "0.4.3"), raw)

    def test_bump_malformed_file_changes_nothing(self):
        readme = self.malformed()
        before = fx.snapshot(self.work)
        doc = self.stop("bump", "--to", "0.4.3")
        self.assertEqual(doc["error"], "bad_version_files", doc)
        self.assertIn("README.md", doc["message"])
        self.assertEqual((self.work / "README.md").read_bytes(), readme)
        self.assertEqual((self.work / "VERSION").read_bytes(), b"0.4.2\n")
        self.assertEqual(fx.snapshot(self.work), before)

    def test_check_reads_malformed_file(self):
        self.malformed()
        code, doc, raw = self.release("check")
        self.assertEqual(code, 0, raw)
        self.assertEqual(doc["version"], "0.4.2")


def msys(path):
    """`C:\\x\\y` as Git Bash writes it, `/c/x/y`."""
    text = str(Path(path).resolve()).replace("\\", "/")
    return "/" + text[0].lower() + text[2:]


@unittest.skipUnless(os.name == "nt", "Git Bash path forms exist on Windows only")
class TestMsysPaths(Sw):
    """The handoff skips Git Bash's argument conversion, so `sw` converts a `/c/...` path option itself."""

    def test_dir_and_proposal_in_msys_form(self):
        self.repo()
        code, doc, raw = self.release("--dir", msys(self.work), "check", cwd=self.tmp)
        self.assertEqual((code, doc and doc.get("version")), (0, "0.4.2"), raw)
        proposal = self.tmp / "proposal.md"
        proposal.write_text("## Why\n\nx\n\n## Release Notes\n\nS.\n\n### Added\n\n- New flag (#1)\n", encoding="utf-8")
        code, doc, raw = self.release("notes", "--proposal", msys(proposal))
        self.assertEqual((code, doc and doc.get("summary")), (0, "S."), raw)


if __name__ == "__main__":
    unittest.main()
