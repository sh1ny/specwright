"""Stress-tier tooling for the git-workflow evals: the marks in evals.json and the base/cheap comparison.

Usage: python tiers.py <iteration-dir> --base <config> --cheap <config> [--evals evals.json]

Prints one JSON document on stdout:
  evals        stress eval name -> {"base": mean pass rate, "cheap": mean pass rate} (null when missing)
  differences  one entry per eval whose configurations differ: the two rates and the assertions that
               pass in one configuration only (pass_only_base, pass_only_cheap)
  missing      {"eval", "config"} for each eval/config without a readable grading
Exit 0 only when nothing differs and nothing is missing, 1 otherwise, 2 for a usage error.

Layout read: <iteration-dir>/<eval-name>/<config>/run-*/grading.json (written by grade.py), with
summary.pass_rate and the per-assertion expectations. Rules:
  - Only evals carrying a valid "stress" mark in evals.json are compared; unmarked evals are skipped.
  - A configuration's rate is the mean of summary.pass_rate over its runs.
  - An assertion "passes" in a configuration when it passed in every run of it; it passes "in one
    configuration only" when it passes there and not in the other (failing or absent counts as not passing).
  - A configuration is missing when it has no run-* directory or any run's grading.json is absent,
    not valid JSON, or lacks summary.pass_rate or a list of expectations. A missing configuration is
    never reported as the same grade.
  - An eval differs when its mean rates differ or an assertion passes in one configuration only.
This is a diagnostic for the cheap-tier record, not a CI gate.
"""
import argparse
import json
import sys
from pathlib import Path

KINDS = ("watch", "light-apply", "implementer")


def check_marks(doc):
    """Problems with the stress marks in an evals.json document; [] when every mark is valid and each kind is covered."""
    problems = []
    seen = set()
    for e in doc.get("evals", []):
        if "stress" not in e:
            continue
        v = e["stress"]
        if isinstance(v, str) and v in KINDS:
            seen.add(v)
        else:
            problems.append(f"{e.get('name', e.get('id'))}: stress mark {v!r} is not one of {', '.join(KINDS)}")
    problems += [f"no stress eval covers {k}" for k in KINDS if k not in seen]
    return problems


def stress_evals(doc):
    return [e["name"] for e in doc.get("evals", []) if isinstance(e.get("stress"), str) and e["stress"] in KINDS]


def read_grading(path):
    """(pass_rate, {assertion text: passed}) of a grading.json, or None when it is absent or unusable."""
    try:
        g = json.loads(path.read_text(encoding="utf-8"))
        rate = g["summary"]["pass_rate"]
        exp = g["expectations"]
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not isinstance(exp, list):
            return None
        return float(rate), {x["text"]: bool(x["passed"]) for x in exp}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_config(iteration, name, config):
    """(mean rate, {assertion: passed in every run}) over the runs of an eval's configuration, or None when missing."""
    runs = sorted(p for p in (iteration / name / config).glob("run-*") if p.is_dir())
    graded = [read_grading(r / "grading.json") for r in runs]
    if not runs or any(g is None for g in graded):
        return None
    texts = {t for _, a in graded for t in a}
    return (sum(r for r, _ in graded) / len(graded),
            {t: all(a.get(t, False) for _, a in graded) for t in texts})


def compare(iteration, base, cheap, doc):
    out = {"base_config": base, "cheap_config": cheap, "evals": {}, "differences": [], "missing": []}
    for name in stress_evals(doc):
        got = {"base": load_config(iteration, name, base), "cheap": load_config(iteration, name, cheap)}
        out["evals"][name] = {k: (None if v is None else round(v[0], 4)) for k, v in got.items()}
        gone = [(k, c) for k, c in (("base", base), ("cheap", cheap)) if got[k] is None]
        out["missing"] += [{"eval": name, "config": c} for _, c in gone]
        if gone:
            continue
        (rb, ab), (rc, ac) = got["base"], got["cheap"]
        only_base = sorted(t for t, p in ab.items() if p and not ac.get(t, False))
        only_cheap = sorted(t for t, p in ac.items() if p and not ab.get(t, False))
        if round(rb, 4) != round(rc, 4) or only_base or only_cheap:
            out["differences"].append({"eval": name, "base": round(rb, 4), "cheap": round(rc, 4),
                                       "pass_only_base": only_base, "pass_only_cheap": only_cheap})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compare stress-eval grades between two configurations.")
    ap.add_argument("iteration")
    ap.add_argument("--base", required=True)
    ap.add_argument("--cheap", required=True)
    ap.add_argument("--evals", default=str(Path(__file__).resolve().parent / "evals.json"))
    a = ap.parse_args(argv)  # a usage error exits 2
    it = Path(a.iteration)
    if not it.is_dir():
        ap.error(f"iteration directory not found: {it}")
    try:
        doc = json.loads(Path(a.evals).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        ap.error(f"cannot read {a.evals}: {e}")
    out = compare(it, a.base, a.cheap, doc)
    print(json.dumps(out, indent=2))
    return 1 if out["differences"] or out["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
