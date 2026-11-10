"""Static scan of every caller of `sw` (native-cli-library-foundations D3, task 3.2). Needs no built `sw`.

Two checks over the shipped skills (skills/**), scripts (scripts/**, skills/*/scripts/**) and `sw`'s own launches in cli/lib:

- every `--option` word given to `sw vcs`, `sw pr`, `sw finish` or `sw commit` (directly, or through the shim that forwards
  to it) is a whole option name that command's source defines, so the one option rule (no abbreviations) cannot break a
  caller;
- no caller matches text on an `sw` document (a `grep`, `sed` or `awk` pipe in a shipped script, a regex or substring over
  a compact `"key":` in Dart), but for the one documented, temporary exception C13 (the `branchPattern` guard printed by
  cli/lib/src/finish/undo_plan.dart), which native-cli-retire-scripts removes. C12 (`sw pr snapshot` reading `sw pr
  reviewers` documents by regex) closed in native-cli-internal-calls: snapshot parses them now. The one compact key line
  left in snapshot.dart is the wait document it prints, not one it reads.

The option sets come from the Dart sources: an `addOption/addFlag/addMultiOption('name'` declaration or a `'--name'` literal
in the command's own files. A command's set is the union over its files, so this checks whole names, not which subcommand
takes which.

Run: python -m unittest evals/cli/test_option_callers.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "cli" / "lib" / "src"

DECL = re.compile(r"""add(?:Option|Flag|MultiOption)\(\s*['"]([a-z][a-z0-9-]*)['"]""")
# a `'--name'` literal in a spec map key, a comparison or a `case`, which is how the hand-written readers name an option
LITERAL = re.compile(r"""(?:[!=]=\s*|case\s+)'--([a-z][a-z0-9-]*)'|'--([a-z][a-z0-9-]*)'\s*:""")
OPTION = re.compile(r"(?<![\w-])--([A-Za-z][A-Za-z0-9-]*)")

# a list of bare names handed to the option helper (`values: const [...]`) or kept in a `_...Options = [...]` constant
NAME_LIST = re.compile(r"(?:_\w*[Oo]ptions\w*\s*=|(?:values|lists|flags):\s*const)\s*\[([^\]]*)\]")

# command family -> the files whose options it defines
SOURCES = {
    "vcs": ["vcs/args.dart", "commands/vcs.dart"],
    "finish": ["commands/finish.dart"],
    "pr": ["pr/pair.dart", "pr/workflow.dart", "pr/policy.dart", "pr/settings_commands.dart", "pr/identity.dart",
           "pr/feedback_pass.dart", "pr/reviewers.dart", "pr/reply.dart", "pr/snapshot.dart", "commands/pr.dart"],
    "commit": ["commands/commit.dart", "commit/task_cover.dart", "commit/fit_subject.dart"],
}

# how a caller names a command: the shim, `sw <command>`, or the skills' `[vcs]` shorthand
INVOKERS = [
    ("vcs", re.compile(r"\bvcs\.sh\b|\bsw vcs\b|\[vcs\]")),
    ("finish", re.compile(r"\bfinish\.sh\b|\bsw finish\b")),
    ("pr", re.compile(r"\bpr-pair\.sh\b|\bpr-snapshot\.sh\b|\bpr-reply\.sh\b|\bsw pr\b")),
    ("commit", re.compile(r"\btask-cover\.sh\b|\bfit-subject\.sh\b|\bsw commit\b")),
]
# the same words a pipe into a text tool would follow
ANY_INVOKER = re.compile("|".join(p.pattern for _, p in INVOKERS))
TEXT_PIPE = re.compile(r"\|\s*(?:grep|egrep|fgrep|sed|awk|cut)\b|\b(?:grep|egrep|fgrep|sed|awk)\b[^|\n]*<<<")

# a compact JSON key inside a Dart string or regex: `"branch":`
DOCUMENT_KEY = re.compile(r'"[a-z_]+":')
# Lines that build a document sw prints: data written, not text matched.
PRINTED = {("cli/lib/src/pr/snapshot.dart", '{"wake":"$wake"')}
C13_MARK = "branchPattern"
C13_FILE = "cli/lib/src/finish/undo_plan.dart"


# options a shim reads itself before it hands the rest to `sw`: pr-pair.sh's leading `--project <code checkout>`
SHIM_OPTIONS = {"pr": {"project": "skills/specwright-pr/scripts/pr-pair.sh"}}


def defined_options():
    found = {}
    for family, files in SOURCES.items():
        names = set()
        for rel in files:
            path = LIB / rel
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            names.update(DECL.findall(text))
            names.update(a or b for a, b in LITERAL.findall(text))
            for body in NAME_LIST.findall(text):
                names.update(re.findall(r"'([a-z][a-z0-9-]*)'", body))
        names.update(SHIM_OPTIONS.get(family, {}))
        found[family] = names
    return found


def tracked(*patterns):
    out = []
    for pattern in patterns:
        out.extend(p for p in ROOT.glob(pattern) if p.is_file() and "__pycache__" not in p.parts)
    return sorted(set(out))


def shipped_caller_files():
    return tracked("skills/**/*.md", "skills/**/*.sh", "skills/**/*.py", "scripts/**/*.sh", "scripts/**/*.py")


def segments(path, text):
    """The pieces of a file that can be a command line: backtick spans and fenced lines in Markdown, every line of a script."""
    if path.suffix != ".md":
        for n, line in enumerate(text.splitlines(), 1):
            if not line.lstrip().startswith("#"):
                yield n, line
        return
    fenced = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            yield n, line
        else:
            for span in re.findall(r"`([^`]+)`", line):
                yield n, span


def option_words(segment):
    """(family, [option words]) when [segment] runs an `sw` command: the options after the first invoker on the line."""
    best = None
    for family, pattern in INVOKERS:
        m = pattern.search(segment)
        if m and (best is None or m.start() < best[1]):
            best = (family, m.start(), m.end())
    if best is None:
        return None
    return best[0], OPTION.findall(segment[best[2]:])


def check_options(path, text, defined):
    """The (file:line, word, family) of every option word that is not a whole name its command defines."""
    bad = []
    for n, segment in segments(path, text):
        got = option_words(segment)
        if got is None:
            continue
        family, words = got
        for word in words:
            if word not in defined[family]:
                bad.append((f"{path.relative_to(ROOT).as_posix() if path.is_absolute() and ROOT in path.parents else path}:{n}",
                            "--" + word, family))
    return bad


def own_launches(text):
    """(family, [option words]) of each `sw` launch in a Dart file: from `Platform.resolvedExecutable, '<command>'` to the line
    that starts with the list's closing bracket."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "Platform.resolvedExecutable" not in line:
            continue
        window = []
        for follower in lines[i + 1:i + 40]:
            if follower.lstrip().startswith("]"):
                break
            window.append(follower)
        joined = " ".join(window)
        m = re.match(r"\s*'(vcs|pr|finish|commit)'", joined)
        if m:
            yield m.group(1), re.findall(r"'--([a-z][a-z0-9-]*)'", joined)


def check_own_launches(path, text, defined):
    return [(path.relative_to(ROOT).as_posix(), "--" + word, family)
            for family, words in own_launches(text) for word in words if word not in defined[family]]


def check_text_matching_scripts(path, text):
    """The file:line of every shipped script line that pipes an `sw` command into a text tool."""
    bad = []
    if path.suffix == ".md":
        return bad
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        if ANY_INVOKER.search(line) and TEXT_PIPE.search(line):
            bad.append(f"{path.name}:{n}")
    return bad


def dart_document_matches():
    """(relative path, line number, line) of every Dart line that matches a compact `"key":` of a document, less C13 and
    the printed documents."""
    bad = []
    for path in sorted(LIB.rglob("*.dart")):
        rel = path.relative_to(ROOT).as_posix()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith(("//", "#")) or not DOCUMENT_KEY.search(line):
                continue
            if any(rel == file and mark in line for file, mark in PRINTED) or (rel == C13_FILE and C13_MARK in line):
                continue
            bad.append((rel, n, stripped))
    return bad


class OptionCallers(unittest.TestCase):
    def test_shipped_callers_use_whole_names(self):
        defined = defined_options()
        for family, names in defined.items():
            self.assertTrue(names, f"no option names read from the {family} sources")
        bad = []
        for path in shipped_caller_files():
            bad.extend(check_options(path, path.read_text(encoding="utf-8"), defined))
        # sw's own launches of sw: the literals between `Platform.resolvedExecutable, '<command>'` and the line that closes the list
        for path in sorted(LIB.rglob("*.dart")):
            bad.extend(check_own_launches(path, path.read_text(encoding="utf-8"), defined))
        self.assertEqual(bad, [], "option words that no command defines as a whole name (abbreviations are refused)")

    def test_sw_launches_are_found(self):
        """The scan of `sw`'s own launches sees the one it must (a scan that finds nothing proves nothing). The config
        check runs in process since native-cli-internal-calls, so the reviewer evaluator is snapshot's only launch."""
        text = (LIB / "pr" / "snapshot.dart").read_text(encoding="utf-8")
        launches = [words for family, words in own_launches(text) if family == "pr"]
        self.assertEqual(launches, [["config", "material", "head"]])

    def test_shim_options_are_the_shims_own(self):
        for names in SHIM_OPTIONS.values():
            for name, rel in names.items():
                self.assertIn(f"= --{name}", (ROOT / rel).read_text(encoding="utf-8"), rel)

    def test_scan_refuses_an_abbreviation(self):
        defined = {"vcs": {"repo", "role"}, "pr": {"material", "head"}, "finish": set(), "commit": set()}
        path = ROOT / "skills" / "x" / "SKILL.md"
        bad = check_options(path, "run `sw pr reviewers --mat m.json --head x`\n", defined)
        self.assertEqual([(w, f) for _, w, f in bad], [("--mat", "pr")])
        self.assertEqual(check_options(path, "run `bash vcs.sh state --repo r --role code`\n", defined), [])

    def test_no_script_matches_text_on_an_sw_document(self):
        bad = []
        for path in shipped_caller_files():
            bad.extend(check_text_matching_scripts(path, path.read_text(encoding="utf-8")))
        self.assertEqual(bad, [], "a shipped script pipes sw output into grep, sed or awk")

    def test_dart_consumers_match_documents_only_for_c12_and_c13(self):
        bad = dart_document_matches()
        self.assertEqual(bad, [], "Dart text matching on a compact sw document outside C13")

    def test_the_documented_exceptions_still_exist(self):
        """C13 and the printed documents are listed only while the code is there: a removed one must leave this list."""
        self.assertIn(C13_MARK, (ROOT / C13_FILE).read_text(encoding="utf-8"))
        for rel, mark in PRINTED:
            self.assertIn(mark, (ROOT / rel).read_text(encoding="utf-8"), rel)


if __name__ == "__main__":
    unittest.main()
