"""The main specs pass `openspec validate --specs --strict` once every active change is archived.

A scratch copy of openspec/ gets each active change archived into it, so the check covers the specs as
they will be after merge, without touching this checkout. Skips when the openspec CLI is not on PATH.

Run: python -m unittest discover evals/git-workflow -p "test_specs_strict.py"
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fixtures import rmtree

ROOT = Path(__file__).resolve().parents[2]
OPENSPEC = shutil.which("openspec")


def run(cwd, *args):
    r = subprocess.run([OPENSPEC, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout + r.stderr).strip()


def active_changes():
    code, out = run(ROOT, "list", "--json")
    assert code == 0, f"openspec list --json failed:\n{out}"
    return [c["name"] for c in json.loads(out)["changes"]]


def validate_after_archive(changes):
    """Archive `changes` into a scratch copy of openspec/, then validate its specs strictly: (exit code, output)."""
    tmp = Path(tempfile.mkdtemp(prefix="specwright-strict-"))
    try:
        shutil.copytree(ROOT / "openspec", tmp / "openspec")
        for name in changes:
            code, out = run(tmp, "archive", name, "--yes")
            if code != 0:
                return code, f"openspec archive {name} --yes failed:\n{out}"
        return run(tmp, "validate", "--specs", "--strict")
    finally:
        rmtree(tmp)


@unittest.skipUnless(OPENSPEC, "openspec CLI not on PATH")
class SpecsStrict(unittest.TestCase):
    def test_main_specs_pass_strict_validation_after_active_changes(self):
        code, out = validate_after_archive(active_changes())
        self.assertEqual(code, 0, f"openspec validate --specs --strict failed:\n{out}")


if __name__ == "__main__":
    unittest.main()
