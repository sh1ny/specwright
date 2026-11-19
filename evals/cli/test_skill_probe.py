"""The skills' version probe against two binaries in one test home (native-cli-retire-scripts D5, task 7.7).

A skill reads the project's `openspec/.specwright/VERSION`, takes `<home>/.specwright/bin/<VERSION>/sw`, and runs `<sw> version
--json` with a 10-second timeout before any other `sw` command. It goes on only when the command exits 0 in time, prints one
JSON object, and that object's `version` is the project's and its `interface` is the one the skills require (the one
`interface <n>` line of skills/specwright-pr/SKILL.md). `probe` below does what that text tells the agent to do.

The home holds a stand-in for 0.37.0 (it reports interface 1 and knows only `version --json`: any other call is a refusal
the stand-in logs) and the built sw. A project on 0.37.0 served by these skills stops at the probe and no other command
reaches the stand-in; a project on the built version passes it.

Needs the binary named by SPECWRIGHT_SW (skips as `sw not built` otherwise; fails under SPECWRIGHT_REQUIRE_SW=1), and a tree
whose VERSION is past 0.37.0 (the cutover bumps it to 0.38.0).

Run: SPECWRIGHT_SW=<path> python -m unittest evals/cli/test_skill_probe.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS = HERE.parent
ROOT = EVALS.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EVALS))
import fakeexe  # noqa: E402
import swcall  # noqa: E402
import swharness  # noqa: E402

SKILL = ROOT / "skills" / "specwright-pr" / "SKILL.md"
OLDER = "0.37.0"
LOG = "SW_PROBE_LOG"

# The 0.37.0 stand-in: interface 1; it answers `version --json` and refuses every other call, logging each call it gets.
OLDER_SW = '''import json, os, sys
args = sys.argv[1:]
with open(os.environ[%r], "a") as log:
    log.write(" ".join(args) + "\\n")
if args == ["version", "--json"]:
    print(json.dumps({"version": %r, "interface": 1}))
    sys.exit(0)
sys.stderr.write("sw: unknown option: %%s\\n" %% (args[:1] or [""])[0])
sys.exit(64)
''' % (LOG, OLDER)


def required_interface():
    found = re.findall(r"^interface (\d+)\s*$", SKILL.read_text(encoding="utf-8"), re.M)
    assert len(found) == 1, "an `interface <n>` line not found exactly once in %s" % SKILL
    return int(found[0])


class SkillProbe(unittest.TestCase):
    def setUp(self):
        self.built = swharness.require_sw()
        self.temp = tempfile.TemporaryDirectory(prefix="sw-skill-probe-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.log = self.root / "older.log"
        self.home = self.root / "home"
        self.version = swcall.version()
        self.assertNotEqual(self.version, OLDER, "the tree is past 0.37.0 (the cutover bumps VERSION): the two binaries "
                                                  "need two version directories")
        self.older_sw = self.install(OLDER, None)
        self.newer_sw = self.install(self.version, self.built)

    def install(self, version, binary):
        """`<home>/.specwright/bin/<version>/sw[.exe]`: the built sw, or the 0.37.0 stand-in when `binary` is None."""
        directory = self.home / ".specwright" / "bin" / version
        directory.mkdir(parents=True)
        name = "sw.exe" if os.name == "nt" else "sw"
        if binary is None:
            made = Path(fakeexe.write_python_fake(directory / "sw", OLDER_SW))  # `sw.exe` on Windows
            self.assertEqual(made.name, name)
            return made
        target = directory / name
        shutil.copy2(binary, target)
        target.chmod(0o755)
        return target

    def project(self, name, version):
        project = self.root / name
        swcall.stamp(project, version)
        return project

    def sw_of(self, project):
        """The `<sw>` a skill builds from the project's VERSION."""
        version = (project / "openspec" / ".specwright" / "VERSION").read_text(encoding="utf-8").strip()
        return self.home / ".specwright" / "bin" / version / ("sw.exe" if os.name == "nt" else "sw")

    def probe(self, project):
        """What the skill text has the agent do: True when it may run another `<sw>` command, else False."""
        wanted = (project / "openspec" / ".specwright" / "VERSION").read_text(encoding="utf-8").strip()
        env = dict(os.environ, **{LOG: self.log.resolve().as_posix()})
        try:
            done = subprocess.run([str(self.sw_of(project)), "version", "--json"], env=env, capture_output=True, text=True,
                                  encoding="utf-8", timeout=10)
        except subprocess.TimeoutExpired:
            return False
        if done.returncode != 0:
            return False
        try:
            document = json.loads(done.stdout)
        except ValueError:
            return False
        return (isinstance(document, dict) and document.get("version") == wanted
                and document.get("interface") == required_interface())

    def older_calls(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def test_older_project_with_newer_skills_stops(self):
        older = self.project("older", OLDER)
        self.assertFalse(self.probe(older), "interface 1 does not satisfy the skills' interface")
        self.assertEqual(self.older_calls(), ["version --json"],
                         "the probe is the only call that reaches the interface-1 binary; the skill runs nothing after it")

    def test_project_on_the_built_version_passes_its_probe(self):
        newer = self.project("newer", self.version)
        self.assertTrue(self.probe(newer))
        self.assertEqual(self.older_calls(), [], "the 0.37.0 binary is not the one this project names")
        document = json.loads(subprocess.run([str(self.sw_of(newer)), "version", "--json"], capture_output=True, text=True,
                                             encoding="utf-8", timeout=60).stdout)
        self.assertEqual((document["version"], document["interface"]), (self.version, required_interface()))

    def test_built_sw_refuses_an_older_project(self):
        """The control: the built binary named for a project on 0.37.0 stops at its own entry check."""
        older = self.project("older", OLDER)
        done = subprocess.run([str(self.newer_sw), "--project", str(older), "gate", "show", "--store", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(json.loads(done.stdout)["error"], "sw_mismatch", done.stdout)


if __name__ == "__main__":
    unittest.main()
