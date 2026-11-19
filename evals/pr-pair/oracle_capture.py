"""The frozen side's runs as records, and the normalization both ways (native-cli-retire-scripts D14, tasks 6.5 and 7.2).

Task 6.5 ran the frozen scripts once on each OS and kept one record per run (the records are in oracle/records; the
capture is gone with the scripts it ran, and no code here writes one).

Machine paths are replaced by placeholders, so the records of three machines compare equal. oracle/check_records.py compares the
sets of three OSes (it is how the records were checked).

From the cutover on the parity evals run only `sw` and compare each run with the record of the running OS (`recorded`, `compare`):
`document` turns a run into the same normalized form a record has, so both sides are normalized by one function.
"""
import json
import platform
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "oracle"))
import check_records  # noqa: E402  the OS-dependent allowances of the three-OS agreement check

ROOT = Path(__file__).resolve().parents[2]
RECORDS = Path(__file__).resolve().parent / "oracle" / "records"
OS_DIRS = {"Linux": "Linux", "Windows": "Windows", "Darwin": "macOS"}
# Fixture commits take this author, committer and date, so their ids repeat in every run and on every OS (D14).
PINNED_IDENTITY = {"GIT_AUTHOR_NAME": "Eval Bot", "GIT_AUTHOR_EMAIL": "eval@example.invalid", "GIT_AUTHOR_DATE": "2026-10-01T12:00:00+0000",
                   "GIT_COMMITTER_NAME": "Eval Bot", "GIT_COMMITTER_EMAIL": "eval@example.invalid", "GIT_COMMITTER_DATE": "2026-10-01T12:00:00+0000"}
TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


def said(stderr):
    """stderr with bash's `<script path>: line N:` prefix cut to the script's name: the path and the line differ by design."""
    return re.sub(rb"(?m)^.*?([a-z-]+\.sh): line \d+: ", rb"\1: line N: ", stderr)


def fixed_prefix(text):
    """The stable leading part of a free-text line: `line N:`, `merge policy unknown:`, else the text up to and including its
    first `: `, else None (nothing to compare)."""
    for pat in (r"line \d+:", r"merge policy unknown:"):
        m = re.match(pat, text)
        if m:
            return m.group()
    i = text.find(": ")
    return text[:i + 2] if i >= 0 else None


def _forms(path):
    """The spellings of a directory a tool may print: as given, resolved, with slashes, and Git Bash's `/c/...`."""
    found = set()
    for p in {str(path), str(Path(path).resolve())}:
        for q in (p, p.replace("\\", "/"), p.replace("\\", "\\\\")):  # the last: a path inside a Python repr
            found.add(q)
            m = re.match(r"^([A-Za-z]):/(.*)$", q)
            if m:
                found.add("/" + m.group(1).lower() + "/" + m.group(2))
    return found


class Paths:
    """Replaces the machine's directories in text: the test's own directory, the checkout and the temp directory."""

    def __init__(self, test):
        named = [("tmp", getattr(test, "tmp", None)), ("root", ROOT), ("temp", tempfile.gettempdir())]
        forms = sorted(((form, f"<{name}>") for name, path in named if path for form in _forms(path)), key=lambda x: -len(x[0]))
        self.pattern = re.compile("(?:" + "|".join(re.escape(form) for form, _ in forms) + ")(?![A-Za-z0-9_.-])", re.IGNORECASE) if forms else None
        self.names = {form.lower(): name for form, name in forms}

    def text(self, value):
        if self.pattern:
            value = self.pattern.sub(lambda m: self.names[m.group().lower()], value)
            value = re.sub(r"(<[a-z]+>)([^\s\"']*)", lambda m: m.group(1) + re.sub(r"\\+", "/", m.group(2)), value)
        value = re.sub(r"(?<=<temp>/)[^/\s\"']+", "<name>", value)  # a random directory under the temp directory
        # sw writes a gh `--input` request (`render.json`, `body.json`, ...) in its own private temp directory; the recorded
        # script wrote it to a bare temp file. Both are "a temp path": only the file's place in the temp directory differs.
        value = re.sub(r"<temp>/<name>/[A-Za-z0-9_-]+\.json(?![^\s\"'])", "<temp>/<name>", value)
        value = re.sub(r"(?<=[/\\])sw\.exe\b", "sw", value)  # the executable suffix is Windows' own
        return re.sub(r"tmp\.[A-Za-z0-9]{6,}", "tmp.X", value)  # an mktemp name

    def node(self, node):
        if isinstance(node, dict):
            return {self.text(k): self.node(v) for k, v in node.items()}
        if isinstance(node, (list, tuple)):
            return [self.node(v) for v in node]
        return self.text(node) if isinstance(node, str) else node


def parsed(stdout):
    """stdout as the JSON document it holds (NaN and Infinity read as their names), else its text."""
    text = stdout.decode("utf-8", "replace")
    try:
        return json.loads(text, parse_constant=lambda name: name)
    except ValueError:
        return text


def env_lines(dump):
    """The variables of an environment dump (bytes) that the fence sets or keeps, as sorted `NAME=value` lines, the other
    variables (the machine's own) left out. The proxy port is random and the null device is OS-named: both are replaced."""
    lines = []
    for line in dump.decode("utf-8", "replace").splitlines():
        name, _, value = line.partition("=")
        if name.startswith(("AS_SH_", "GH_", "GIT_")):
            value = re.sub(r"127\.0\.0\.1:\d+", "127.0.0.1:<port>", value)
            lines.append(f"{name}={'<devnull>' if value in ('/dev/null', 'nul') else value}")
    return chr(10).join(sorted(lines)).encode("utf-8")


def comment_bodies(node, path="", inside=False):
    """{path: body} of every `body` string under a `comments` key of the fake-gh state."""
    found = {}
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "body" and inside and isinstance(value, str):
                found[path] = value
            else:
                found.update(comment_bodies(value, f"{path}/{key}", inside or key == "comments"))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found.update(comment_bodies(value, f"{path}/{i}", inside))
    return found


def document(test, side, owner_record=None, label="", **extra):
    """One run of a program as the normalized document a record holds. `side` holds `code`, `stdout`, `stderr` and, when the eval
    has them, `calls`, `state` (bytes of the fake-gh state) and `doc` (ignored). `owner_record` is the feedback record's bytes
    after a `pass write`: the owner id printed on stdout must equal the one in it and is then replaced by a placeholder."""
    paths = Paths(test)
    stdout = parsed(side["stdout"])
    if owner_record is not None:
        written = json.loads(owner_record.decode("utf-8"))["owner"]["id"]
        if isinstance(stdout, dict) and isinstance(stdout.get("owner"), str):
            if stdout["owner"] != written:
                raise AssertionError(f"owner {stdout['owner']!r} is not the record's {written!r}")
            stdout["owner"] = "<owner>"
    if isinstance(stdout, dict):  # write times the frozen side generated: checked for form, then replaced
        for holder, key in ((stdout.get("owner"), "at"), (stdout, "written_at")):
            if isinstance(holder, dict) and key in holder:
                if not TIME.match(str(holder[key])):
                    raise AssertionError(f"{key} {holder[key]!r} is not an ISO-8601 UTC time")
                holder[key] = "<time>"
        owner = stdout.get("owner")  # the host and the owner id the frozen side generated: checked, then replaced
        if isinstance(owner, dict) and "host" in owner:
            if not str(owner["host"]).strip():
                raise AssertionError("owner host is empty")
            owner["host"] = "<host>"
        # A generated owner id is 32 hex digits; an id the fixture chose (such as `matrix-owner`) is kept as it is.
        if isinstance(owner, dict) and re.fullmatch(r"[0-9a-f]{32}", str(owner.get("id", ""))):
            owner["id"] = "<owner>"
    state = json.loads(side["state"]) if side.get("state") else None
    lines = said(side["stderr"]).decode("utf-8", "replace").splitlines()
    return {"case": test.id(), "label": label, "exit": side["code"],
            "calls": paths.node(side.get("calls")),
            "stderr": {"lines": len(lines), "prefixes": [paths.text(fixed_prefix(line) or "") for line in lines]},
            "stdout": paths.node(stdout),
            "state": paths.node(state),
            "comment_bodies": paths.node(comment_bodies(state) if state else {}),
            **paths.node(extra)}


# ---- the recorded runs, read back (task 7.2) ----------------------------------------------------------------------------------

def records_dir():
    """The record set of the running OS: the frozen scripts' own per-OS behaviour is in it (check_records.OS_DEPENDENT)."""
    return RECORDS / OS_DIRS[platform.system()]


# Cases whose test was renamed when the frozen side stopped running: the name the capture gave their records.
CAPTURED_AS = {
    "test_native_plan_resumes_a_recorded_frozen_record": "test_native_plan_resumes_an_existing_record",
    "test_native_record_matches_frozen_reader_fixture": "test_script_plan_reads_a_native_record",
}


def case_name(test):
    """The directory name a test's records have: `<file>.<Class>.<method>`, as the capture named it."""
    module = type(test).__module__.rsplit(".", 1)[-1]
    method = CAPTURED_AS.get(test._testMethodName, test._testMethodName)
    return re.sub(r"[^A-Za-z0-9_.-]", "_", f"{module}.{type(test).__qualname__}.{method}")


def recorded(test, case=None):
    """(document, feedback record bytes or None) of the next recorded frozen run of this test (or of `case`, a directory name),
    in call order. The count is kept on the test per case, so a case that makes its runs in the order the capture saw them reads
    the matching records."""
    case = case or case_name(test)
    counts = test.__dict__.setdefault("_oracle_counts", {})
    n = counts[case] = counts.get(case, 0) + 1
    found = sorted((records_dir() / case).glob(f"{n:02d}-*.json"))
    if len(found) != 1:
        raise AssertionError(f"no recorded run {n} of {case} in {records_dir()}: {[f.name for f in found]}")
    kept = found[0].with_suffix(".record")
    return json.loads(found[0].read_text(encoding="utf-8")), (kept.read_bytes() if kept.is_file() else None)


def recorded_fixture(test, case=None):
    """The bytes of the record a native writer wrote and the frozen reader accepted, for this test (or for `case`)."""
    return (records_dir() / (case or case_name(test)) / "fixture.bin").read_bytes()


_SIDE = re.compile(r"(?<=[-_/\\])(?:old|new)(?=[-_/\\.]|$)|cfg-format[12]")


def canon(node):
    """A document with the names the two runs gave their own directories (`state-old`, `state-new`, `cfg-format1`) made equal: the
    frozen and the native run of one case never shared a name, and a recorded run has the frozen side's."""
    if isinstance(node, dict):
        return {canon(k): canon(v) for k, v in node.items()}
    if isinstance(node, list):
        return [canon(v) for v in node]
    return _SIDE.sub("SIDE", node) if isinstance(node, str) else node


def compare(test, got, want):
    """The first difference between a normalized run `got` and a recorded one `want`, or None. The case and label are not
    compared; a path that differs between OSes by the frozen script's own behaviour is allowed as check_records lists it."""
    case = case_name(test)
    allow = {path: (why, fn) for suffix, path, why, fn in check_records.OS_DEPENDENT if case.endswith(suffix)}
    drop = lambda doc: {k: v for k, v in canon(doc).items() if k not in ("case", "label")}
    return check_records.first_difference(drop(got), drop(want), "$", allow, [])
