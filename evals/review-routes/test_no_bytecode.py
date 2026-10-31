"""#157: the skill scripts never write Python bytecode (__pycache__) next to an installed copy.

An installed skill sits inside the project's working tree, so a cache file there dirties clean-tree gates (on jj it is
snapshotted as an added file at once). The scripts that load their sibling bounded.py by path set
sys.dont_write_bytecode before loading it.

Run: python -m unittest discover evals/review-routes -p test_no_bytecode.py
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"


class NoBytecode(unittest.TestCase):
    def test_review_run_select_writes_no_pycache(self):
        tmp = Path(tempfile.mkdtemp(prefix="sw157-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        scripts = tmp / "scripts"
        scripts.mkdir()
        for name in ("review-run.sh", "bounded.py"):
            shutil.copy2(SKILLS / "specwright-review" / "scripts" / name, scripts / name)
        repo = tmp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}
        r = subprocess.run(["bash", str(scripts / "review-run.sh"), "select", "--runtime", "claude"],
                           cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(p.name for p in scripts.iterdir()), ["bounded.py", "review-run.sh"])

    def test_every_by_path_loader_disables_bytecode(self):
        loaders = []
        for path in sorted(SKILLS.glob("*/scripts/*")):
            if not path.is_file() or path.suffix not in (".sh", ".py"):
                continue
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"spec_from_file_location\(", text):
                loaders.append(path.relative_to(ROOT).as_posix())
                self.assertIn("sys.dont_write_bytecode = True", text[:match.start()],
                              "%s loads a module by path without disabling bytecode first" % path)
        self.assertTrue(loaders, "no by-path loader found; update this test")


if __name__ == "__main__":
    unittest.main()
