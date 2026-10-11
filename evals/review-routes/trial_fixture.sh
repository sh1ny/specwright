#!/usr/bin/env bash
# Build the reviewer-CLI trial fixture (add-preship-review task 2.1).
#
# Usage: bash trial_fixture.sh [<parent dir>]
# Creates, under <parent dir> (default: a new temp dir):
#   code/  - a git repo whose branch feat/trial-change has two commits on top
#            of main; the range main...HEAD holds one known defect
#            (clamp() returns the upper bound when value < low).
#   store/ - a planning store repo whose branch feat/trial-change has one
#            planning commit on top of main.
# Prints `code=<path>` and `store=<path>`.
set -eu

parent=${1:-}
if [ -z "$parent" ]; then
  parent=$(mktemp -d "${TMPDIR:-/tmp}/specwright-trial.XXXXXX")
fi
mkdir -p "$parent"
code="$parent/code"
store="$parent/store"
if [ -e "$code" ] || [ -e "$store" ]; then
  echo "trial_fixture.sh: $parent already holds code/ or store/" >&2
  exit 2
fi

g() { git -C "$1" -c user.name=Trial -c user.email=trial@example.invalid -c commit.gpgsign=false -c core.autocrlf=false "${@:2}"; }

git init -q -b main "$code"
cat > "$code/mathutil.py" <<'EOF'
"""Small numeric helpers."""


def mean(values):
    return sum(values) / len(values)
EOF
g "$code" add mathutil.py
g "$code" commit -q -m "chore: initial helpers"
g "$code" checkout -q -b feat/trial-change

cat >> "$code/mathutil.py" <<'EOF'


def clamp(value, low, high):
    """Return value limited to the range [low, high]."""
    if value < low:
        return high
    if value > high:
        return high
    return value
EOF
g "$code" add mathutil.py
g "$code" commit -q -m "feat(trial-change): task 1.1 add clamp"

cat > "$code/test_mathutil.py" <<'EOF'
import unittest

from mathutil import clamp


class ClampTest(unittest.TestCase):
    def test_inside(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_above(self):
        self.assertEqual(clamp(15, 0, 10), 10)


if __name__ == "__main__":
    unittest.main()
EOF
g "$code" add test_mathutil.py
g "$code" commit -q -m "feat(trial-change): task 1.2 test clamp"

git init -q -b main "$store"
mkdir -p "$store/openspec/specs/clamp"
cat > "$store/openspec/specs/clamp/spec.md" <<'EOF'
# clamp

Numeric clamping helpers.
EOF
g "$store" add openspec
g "$store" commit -q -m "chore: initial store"
g "$store" checkout -q -b feat/trial-change
mkdir -p "$store/openspec/changes/trial-change/specs/clamp"
cat > "$store/openspec/changes/trial-change/specs/clamp/spec.md" <<'EOF'
## ADDED Requirements

### Requirement: clamp limits a value to a range
`clamp(value, low, high)` SHALL return `low` when `value < low`, `high` when `value > high`, and `value` otherwise.

#### Scenario: Below the range
- **WHEN** `clamp(-3, 0, 10)` is called
- **THEN** it returns `0`
EOF
g "$store" add openspec
g "$store" commit -q -m "feat(trial-change): add planning artifacts"

echo "code=$code"
echo "store=$store"
