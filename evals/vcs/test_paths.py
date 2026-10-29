"""Captured Windows-style jj diff output is normalized by the backend."""

from jjenv import Scratch, require_jj
from vcs_test_support import VcsTestCase, bash_path_env


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
            script.write_bytes(
                r"""#!/bin/sh
if [ "$1" = diff ] && [ "$2" = --summary ]; then
  printf '%s\n' 'A openspec\changes\probe-path\nested.txt'
  exit 0
fi
exec "$SPECWRIGHT_REAL_JJ" "$@"
""".encode("utf-8"),
            )
            script.chmod(0o755)
            env = {
                **bash_path_env(extra_path=(shim_dir,)),
                "SPECWRIGHT_REAL_JJ": require_jj(),
            }

            state, _ = self.invoke("state", repo=repo, env=env)
            self.assertIn("openspec/changes/probe-path/nested.txt", state["dirty_paths"])
            self.assertTrue(all("\\" not in path for path in state["dirty_paths"]))
