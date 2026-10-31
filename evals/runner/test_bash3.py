"""Shipped bash scripts run on bash 3.2, the /bin/bash of macOS: no bash-4-only features.

Scans `scripts/*.sh` and `skills/*/scripts/*.sh` line by line (comment lines skipped) for `mapfile`/`readarray`,
associative arrays and namerefs (`declare -A`, `local -n`, ...), case modification (`${x,,}`, `${x^}`, ...), `@`
transformations (`${x@Q}`), `coproc`, `|&`, `&>>`, `wait -n` and `[[ -v`, and fails naming `<file>:<line>`.

Run: python -m unittest evals/runner/test_bash3.py
"""
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = r"[A-Za-z_][A-Za-z0-9_]*(?:\[[^]]*\])?"
FEATURES = (
    (re.compile(r"\b(?:mapfile|readarray)\b"), "mapfile/readarray"),
    (re.compile(r"\b(?:declare|local|typeset)\s+-[A-Za-z]*[An]"), "associative array or nameref"),
    (re.compile(r"\$\{" + NAME + r"(?:,,?|\^\^?)\}"), "case modification"),
    (re.compile(r"\$\{" + NAME + r"@[QEPAaUuLK]\}"), "@ transformation"),
    (re.compile(r"\bcoproc\b"), "coproc"),
    (re.compile(r"\|&"), "|&"),
    (re.compile(r"&>>"), "&>>"),
    (re.compile(r"\bwait\s+-n\b"), "wait -n"),
    (re.compile(r"\[\[\s+-v\s"), "[[ -v"),
)


def scan_text(text):
    """(line, feature) for every bash-4-only feature outside a comment line."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        found.extend((number, name) for pattern, name in FEATURES if pattern.search(line))
    return found


def scan(root):
    """`<path>:<line> <feature>` for the shipped scripts under root, paths relative to root."""
    root = Path(root)
    paths = sorted(set(root.glob("scripts/*.sh")) | set(root.glob("skills/*/scripts/*.sh")))
    return ["%s:%d %s" % (p.relative_to(root).as_posix(), n, name)
            for p in paths for n, name in scan_text(p.read_text(encoding="utf-8"))]


class Bash3(unittest.TestCase):
    def test_each_feature_is_named(self):
        cases = {
            "mapfile -t lines < f": "mapfile/readarray",
            "declare -A seen": "associative array or nameref",
            "local -n ref=$1": "associative array or nameref",
            'echo "${name,,}"': "case modification",
            'echo "${list[0]^}"': "case modification",
            'printf %s "${x@Q}"': "@ transformation",
            "coproc cat": "coproc",
            "cmd |& tee log": "|&",
            "cmd &>> log": "&>>",
            "wait -n": "wait -n",
            "if [[ -v name ]]; then :; fi": "[[ -v",
        }
        for line, name in cases.items():
            with self.subTest(line=line):
                with tempfile.TemporaryDirectory() as d:
                    (Path(d) / "scripts").mkdir()
                    (Path(d) / "scripts" / "x.sh").write_text("#!/usr/bin/env bash\n" + line + "\n", encoding="utf-8")
                    self.assertEqual(scan(d), ["scripts/x.sh:2 " + name])

    def test_bash3_forms_pass(self):
        text = ('#!/usr/bin/env bash\n# mapfile is bash 4\nwhile IFS= read -r l; do a+=("$l"); done < f\n'
                'local -a list=()\ndeclare -r x=1\necho "${x:-y}" "${#list[@]}" "${list[@]}" "$@"\ncmd >> log 2>&1\n')
        self.assertEqual(scan_text(text), [])

    def test_shipped_scripts_run_on_bash_3_2(self):
        self.assertEqual(scan(ROOT), [], "macOS /bin/bash is 3.2")


if __name__ == "__main__":
    unittest.main()
