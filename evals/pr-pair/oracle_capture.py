"""Capture of the frozen side's runs (native-cli-retire-scripts D14, task 6.5).

The parity evals run a frozen script (the oracle) beside the tree's. When SPECWRIGHT_ORACLE_RECORDS names a directory, each
frozen run also writes one record there, under a directory named by the test and a number in call order:

    <dir>/<test id>/<nn>-<label>.json   exit status, gh calls, stderr prefixes, parsed stdout, final fake-gh state, comment bodies
    <dir>/<test id>/<nn>-<label>.record the feedback record the frozen writer left, as bytes
    <dir>/<test id>/fixture.bin         the record a native writer wrote and the frozen reader accepted

Machine paths are replaced by placeholders, so the records of three machines compare equal. Without the variable nothing is
written. oracle/capture.py runs the parity files with it set; oracle/check_records.py compares the sets of three OSes.
"""
import json
import os
import re
import tempfile
from pathlib import Path

ENV = "SPECWRIGHT_ORACLE_RECORDS"
ROOT = Path(__file__).resolve().parents[2]
_counts = {}
# Fixture commits take this author, committer and date, so their ids repeat in every run and on every OS (D14).
PINNED_IDENTITY = {"GIT_AUTHOR_NAME": "Eval Bot", "GIT_AUTHOR_EMAIL": "eval@example.invalid", "GIT_AUTHOR_DATE": "2026-10-01T12:00:00+0000",
                   "GIT_COMMITTER_NAME": "Eval Bot", "GIT_COMMITTER_EMAIL": "eval@example.invalid", "GIT_COMMITTER_DATE": "2026-10-01T12:00:00+0000"}
TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


def enabled():
    return bool(os.environ.get(ENV))


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


def _place(test, label, text=None, blob=None, name="json"):
    """The next file of this test's directory: `<nn>-<label>.<name>`."""
    case = re.sub(r"[^A-Za-z0-9_.-]", "_", test.id())
    n = _counts[case] = _counts.get(case, 0) + 1
    directory = Path(os.environ[ENV]) / case
    directory.mkdir(parents=True, exist_ok=True)
    return directory, f"{n:02d}-{label}.{name}"


def record(test, label, side, owner_record=None, **extra):
    """Write one frozen run. `side` holds `code`, `stdout`, `stderr` and, when the eval has them, `calls`, `state` (bytes of
    the fake-gh state) and `doc` (ignored). `owner_record` is the feedback record's bytes after a `pass write`: the owner id
    printed on stdout must equal the one in it and is then replaced by a placeholder; the bytes are kept beside the record."""
    if not enabled():
        return
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
    state =json.loads(side["state"]) if side.get("state") else None
    lines = said(side["stderr"]).decode("utf-8", "replace").splitlines()
    doc = {"case": test.id(), "label": label, "exit": side["code"],
           "calls": paths.node(side.get("calls")),
           "stderr": {"lines": len(lines), "prefixes": [paths.text(fixed_prefix(line) or "") for line in lines]},
           "stdout": paths.node(stdout),
           "state": paths.node(state),
           "comment_bodies": paths.node(comment_bodies(state) if state else {}),
           **paths.node(extra)}
    directory, name = _place(test, label)
    (directory / name).write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    if owner_record is not None:
        (directory / name.replace(".json", ".record")).write_bytes(owner_record)


def fixture(test, data):
    """The bytes of a record a native writer wrote and the frozen reader accepted."""
    if not enabled():
        return
    directory, _ = _place(test, "fixture")
    (directory / "fixture.bin").write_bytes(data)
