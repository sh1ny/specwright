"""The interface number the resolver expects must equal the one the binary reports (constraint C2).

Reads SW_INTERFACE=<n> from skills/specwright-pr/scripts/sw-path.sh and `const int interfaceVersion = <n>;` from
cli/lib/src/commands/version.dart. Needs no binary.

Run: python -m unittest evals/cli/test_sw_interface_pin.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "skills" / "specwright-pr" / "scripts" / "sw-path.sh"
DART = ROOT / "cli" / "lib" / "src" / "commands" / "version.dart"


class InterfacePin(unittest.TestCase):
    def test_resolver_and_binary_agree_on_the_interface(self):
        script = re.findall(r"^SW_INTERFACE=(\d+)\s*$", SCRIPT.read_text(encoding="utf-8"), re.M)
        dart = re.findall(r"^const int interfaceVersion = (\d+);", DART.read_text(encoding="utf-8"), re.M)
        self.assertEqual(len(script), 1, "SW_INTERFACE=<n> not found exactly once in %s" % SCRIPT)
        self.assertEqual(len(dart), 1, "interfaceVersion not found exactly once in %s" % DART)
        self.assertEqual(script, dart, "SW_INTERFACE and interfaceVersion differ")


if __name__ == "__main__":
    unittest.main()
