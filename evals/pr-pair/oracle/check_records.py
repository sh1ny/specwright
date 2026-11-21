"""Check the oracle records of three OSes (native-cli-retire-scripts D14, task 6.5).

    python evals/pr-pair/oracle/check_records.py <dir> <dir> <dir>

Each directory is one OS's capture (the capture of task 6.5, which ran the frozen scripts and is deleted with them). The check
reads files only and starts nothing. It fails, printing every problem, unless:

  1. each set is complete: it has outcomes.json with no failed or errored test, the three sets ran the same tests, and every
     case that has records in one set has them in all three (a set may lack a case its own outcomes mark as skipped);
  2. the three sets agree: the same file names per case, and equal records after the capture's normalization;
  3. each feedback record kept as bytes and each frozen-reader fixture is UTF-8 with LF line ends and a version-2 record. These
     carry generated fields (owner id, times, checkout), so they are checked for form and not compared across OSes.

No frozen record under evals/pr-pair/oracle/records/ is edited or regenerated. A case that a fix changes becomes a listed
difference with its own outcome test, so the comparison evidence survives.
"""
import json
import re
import sys
from pathlib import Path


def without_gcm(value):
    """A value without Git Credential Manager's `GCM_INTERACTIVE`: a Windows runner has it in its environment."""
    if isinstance(value, str):
        kept = [line for line in value.split(chr(10)) if not line.startswith("AS_SH_ORIG_GCM_INTERACTIVE=")]
        return re.sub(r" GCM_INTERACTIVE\b", "", chr(10).join(kept))
    return value


def without_errno(value):
    """A message without the number and text of the `[Errno N] text:` Python prints."""
    return re.sub(r"\[Errno \d+\] [^:]*:", "[Errno] :", value) if isinstance(value, str) else value


# The known differences between OSes that the frozen scripts really show, and nothing else: (case suffix, JSON path, why, the
# value with the OS part removed). A listed path may differ only by that part; every other path must agree.
OS_DEPENDENT = [
    ("AsParity.test_nested_fence_keeps_the_outer_originals", "$.stdout",
     "Git Credential Manager sets GCM_INTERACTIVE on the Windows runner, and the fence keeps it among the originals", without_gcm),
    ("AsParity.test_env_under_the_fence_with_the_token_masked", "$.stdout",
     "Git Credential Manager sets GCM_INTERACTIVE on the Windows runner, and the fence keeps it among the originals", without_gcm),
    ("WorkflowRecords.test_directory_record_is_occupied_and_unreadable", "$.stdout.message",
     "Python's errno text for reading a directory is the OS's own: EISDIR on Linux and macOS, EACCES on Windows", without_errno),
]


def case_name(test_id):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", test_id)


def load(directory):
    """({case: {file name: path}}, {case name: outcome}) of one capture directory."""
    root = Path(directory)
    outcomes = json.loads((root / "outcomes.json").read_text(encoding="utf-8")) if (root / "outcomes.json").is_file() else None
    cases = {d.name: {f.name: f for f in sorted(d.iterdir())} for d in sorted(root.iterdir()) if d.is_dir()}
    return cases, outcomes


def first_difference(a, b, path="$", allow=None, seen=None):
    """The first path where a and b differ, or None. A path in `allow` {path: (reason, fn)} may differ by what `fn` removes;
    such a difference is added to `seen`."""
    if allow and path in allow and a != b:
        reason, fn = allow[path]
        if fn(a) == fn(b):
            seen.append((path, reason))
            return None
    if type(a) is not type(b):
        return f"{path}: {a!r} != {b!r}"
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                return f"{path}.{key}: present on one side only"
            found = first_difference(a[key], b[key], f"{path}.{key}", allow, seen)
            if found:
                return found
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: {len(a)} items != {len(b)} items"
        for i, (x, y) in enumerate(zip(a, b)):
            found = first_difference(x, y, f"{path}[{i}]", allow, seen)
            if found:
                return found
        return None
    return None if a == b else f"{path}: {a!r} != {b!r}"


def blob_problem(path):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
        record = json.loads(text)
    except ValueError as error:
        return f"is not UTF-8 JSON ({error})"
    if b"\r" in raw:
        return "has CR line ends"
    if not isinstance(record, dict) or record.get("version") != 2 or not isinstance(record.get("owner"), dict):
        return "is not a version-2 feedback record"
    return None


def check(directories):
    """(problems, summary) for the capture directories of the OSes."""
    names = [Path(d).name for d in directories]
    sets = [load(d) for d in directories]
    problems = []
    for name, (cases, outcomes) in zip(names, sets):
        if outcomes is None:
            problems.append(f"{name}: no outcomes.json")
        elif not cases:
            problems.append(f"{name}: no records")
    if problems:
        return problems, ""
    for name, (_, outcomes) in zip(names, sets):
        for test, outcome in sorted(outcomes.items()):
            if outcome["status"] in ("failed", "error"):
                problems.append(f"{name}: {test} {outcome['status']}")
    ran = [set(outcomes) for _, outcomes in sets]
    for name, tests in zip(names, ran):
        for test in sorted(set.union(*ran) - tests):
            problems.append(f"{name}: did not run {test}")
    skipped = [{case_name(t) for t, o in outcomes.items() if o["status"] == "skipped"} for _, outcomes in sets]
    every = sorted(set().union(*(set(cases) for cases, _ in sets)))
    files = 0
    blobs = 0
    allowed = {}
    for case in every:
        have = [(name, cases[case], skips) for name, (cases, _), skips in zip(names, sets, skipped) if case in cases]
        for name, (cases, _), skips in zip(names, sets, skipped):
            if case not in cases and case not in skips:
                problems.append(f"{name}: no records for {case}")
        if not have:
            continue
        reference_name, reference, _ = have[0]
        for name, listing, _ in have[1:]:
            if sorted(listing) != sorted(reference):
                problems.append(f"{case}: {name} has {sorted(listing)}, {reference_name} has {sorted(reference)}")
        for file_name, path in reference.items():
            if file_name.endswith(".json"):
                files += 1
                parsed = json.loads(path.read_text(encoding="utf-8"))
                for name, listing, _ in have[1:]:
                    other = listing.get(file_name)
                    if other is not None:
                        allow = {path_: (why, fn) for suffix, path_, why, fn in OS_DEPENDENT if case.endswith(suffix)}
                        seen = []
                        found = first_difference(parsed, json.loads(other.read_text(encoding="utf-8")), "$", allow, seen)
                        for where, why in seen:
                            allowed[(case, where, why)] = allowed.get((case, where, why), 0) + 1
                        if found:
                            problems.append(f"{case}/{file_name}: {reference_name} and {name} differ at {found}")
        for name, listing, _ in have:
            for file_name, path in listing.items():
                if not file_name.endswith(".json"):
                    blobs += 1
                    found = blob_problem(path)
                    if found:
                        problems.append(f"{name}: {case}/{file_name} {found}")
    summary = (f"{len(every)} cases, {files} records compared across {len(directories)} sets ({', '.join(names)}), "
               f"{blobs} feedback records checked for form, {sum(len(s) for s in skipped)} platform skips")
    for (case, where, why), count in sorted(allowed.items()):
        summary += chr(10) + f"OS-dependent, allowed: {case} {where} ({count} comparisons): {why}"
    return problems, summary


def main(argv):
    if len(argv) != 4:
        print(__doc__.split("\n\n")[0], file=sys.stderr)
        return 2
    problems, summary = check(argv[1:])
    if problems:
        for problem in problems[:100]:
            print("FAIL", problem)
        print(f"{len(problems)} problems" + (" (first 100 shown)" if len(problems) > 100 else ""))
        return 1
    print("OK", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
