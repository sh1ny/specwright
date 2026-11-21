"""The interface number the skills require must equal the one the binary reports (constraint C2, design D5).

Reads the one `interface <n>` line of skills/specwright-pr/SKILL.md and `const int interfaceVersion = <n>;` from
cli/lib/src/commands/version.dart, and requires both to be 2. Needs no binary.

Run: python -m unittest evals/cli/test_sw_interface_pin.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILL = ROOT / "skills" / "specwright-pr" / "SKILL.md"
DART = ROOT / "cli" / "lib" / "src" / "commands" / "version.dart"
INTERFACE = ["3"]


class InterfacePin(unittest.TestCase):
    def test_skills_and_binary_agree_on_the_interface(self):
        skill = re.findall(r"^interface (\d+)\s*$", SKILL.read_text(encoding="utf-8"), re.M)
        dart = re.findall(r"^const int interfaceVersion = (\d+);", DART.read_text(encoding="utf-8"), re.M)
        self.assertEqual(len(skill), 1, "an `interface <n>` line not found exactly once in %s" % SKILL)
        self.assertEqual(len(dart), 1, "interfaceVersion not found exactly once in %s" % DART)
        self.assertEqual(skill, dart, "the skill's interface and interfaceVersion differ")

    def test_the_interface_is_3(self):
        dart = re.findall(r"^const int interfaceVersion = (\d+);", DART.read_text(encoding="utf-8"), re.M)
        self.assertEqual(dart, INTERFACE, "the binary's interface is 3 (design D10 of fix-sw-port-gaps)")


if __name__ == "__main__":
    unittest.main()
