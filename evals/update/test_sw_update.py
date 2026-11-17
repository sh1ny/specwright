"""Black-box tests of `sw update` (native-cli-update).

Run: SPECWRIGHT_SW=<path> python -m unittest evals/update/test_sw_update.py
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evals" / "cli"))
import swharness  # noqa: E402


def snapshot(path):
    """{relative posix path: bytes (None for a directory)} of everything under path."""
    out = {}
    for p in sorted(Path(path).rglob("*")):
        out[p.relative_to(path).as_posix()] = None if p.is_dir() else p.read_bytes()
    return out


class TestInterface(unittest.TestCase):
    def test_interface_reports_3_and_writes_nothing(self):
        """D11: `sw update interface` reads and writes nothing else: no journal recovery, no lock, no settings."""
        with tempfile.TemporaryDirectory(prefix="sw-update-iface-") as tmp:
            tmp = Path(tmp)
            code = tmp / "code"
            home = tmp / "home"
            state = code / "openspec" / ".specwright"
            state.mkdir(parents=True)
            home.mkdir()
            (state / "update.json").write_text('{"format": 9}\n', encoding="utf-8", newline="\n")
            (state / "update.lock").mkdir()
            (code / "openspec" / "specwright.yaml").write_text("vcs: yes\n", encoding="utf-8", newline="\n")
            before = snapshot(tmp)
            env = swharness.fixture_env(SPECWRIGHT_HOME=str(home))
            proc = swharness.run_sw("update", "interface", cwd=code, env=env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(proc.stdout, '{"ok":true,"interface":3}\n')
            self.assertEqual(proc.stderr, "")
            self.assertEqual(snapshot(tmp), before)


if __name__ == "__main__":
    unittest.main()
