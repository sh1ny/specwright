"""Captured Windows-style jj diff output is normalized by the backend."""

from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase, bash_path_env
from fakeexe import write_python_fake # after jjenv, which puts evals/ on sys.path


class TestPathNormalization(VcsTestCase):
    def test_backslash_paths_normalised(self):
        with Scratch() as scratch:
            repo = scratch.tracked_repo().path
            settings = repo / "openspec" / "specwright.yaml"
            settings.parent.mkdir(exist_ok=True)
            settings.write_text("vcs: jj\n", encoding="utf-8")

            shim_dir = self.root / "jj-shim"
            shim_dir.mkdir()
            script = shim_dir / "jj"
            # sw passes jj templates that hold double quotes, which a `.cmd` wrapper cannot take (D9): a Python fake.
            write_python_fake(
                script,
                r"""import os, subprocess, sys
if sys.argv[1:3] == ["diff", "--summary"]:
    sys.stdout.buffer.write(b"A openspec\\changes\\probe-path\\nested.txt\n")
    sys.exit(0)
sys.exit(subprocess.call([os.environ["SPECWRIGHT_REAL_JJ"], *sys.argv[1:]]))
""",
            )
            env = {
                **bash_path_env(extra_path=(shim_dir,)),
                "SPECWRIGHT_REAL_JJ": require_jj(),
            }

            state, _ = self.invoke("state", repo=repo, env=env)
            self.assertIn("openspec/changes/probe-path/nested.txt", state["dirty_paths"])
            self.assertTrue(all("\\" not in path for path in state["dirty_paths"]))
