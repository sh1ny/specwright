"""Shipped skills, the schema, the agents and the docs tell the agent to run `<sw>` directly (native-cli-retire-scripts D11, D13, C3).

These are mechanical checks of the delivered text, in the style of test_instructions.py: where a rule sits and its key
terms. They prove the rule is in the instructions, not that a live agent follows it; the binary's side of each rule
(`sw_mismatch`, the version probe's interface) has its own black-box evals in evals/cli.

Run: python -m unittest evals/git-workflow/test_skill_sw_calls.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_NAMES = ("branch", "commit", "debug", "finish", "pr", "release", "review", "roadmap")
SKILLS = {n: ROOT / "skills" / f"specwright-{n}" / "SKILL.md" for n in SKILL_NAMES}
SHIPPED = (list(SKILLS.values())
           + sorted((ROOT / "skills").glob("*/references/*.md"))
           + sorted((ROOT / "agents").glob("*/*.md"))
           + [ROOT / "schemas" / "specwright" / "schema.yaml"]
           + sorted((ROOT / "schemas" / "specwright" / "templates").glob("*.md"))
           + sorted((ROOT / "templates" / "openspec").glob("*.yaml")))
# the README and CONTRIBUTING name every command the same way, but also tell the story of the old scripts
DOCS = [ROOT / "README.md", ROOT / "CONTRIBUTING.md"]

SCRIPT_NAMES = ("vcs", "as", "pr-pair", "pr-snapshot", "pr-reply", "sw-path", "task-cover", "fit-subject", "finish",
                "review-run", "release", "update")
SCRIPT = re.compile(r"\b(?:" + "|".join(SCRIPT_NAMES) + r")\.sh\b|\bbounded\.py\b|\breviewers\.py\b|\bscripts/[\w-]+\.(?:sh|py)\b")
SUBCOMMANDS = ("vcs", "as", "pr", "commit", "finish", "review", "release", "gate", "version", "run", "update")
VERSION_RE = r"x\.y\.z"


def read(p):
    return p.read_text(encoding="utf-8")


def spans(text):
    """Every inline code span and every fenced-block line of `text`."""
    out = re.findall(r"`([^`\n]+)`", text)
    for block in re.findall(r"```[^\n]*\n(.*?)```", text, re.S):
        out += [ln.strip() for ln in block.splitlines() if ln.strip()]
    return out


def paragraphs(text):
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def find_block(text, *patterns):
    for p in paragraphs(text):
        if all(re.search(pat, p, re.I | re.S) for pat in patterns):
            return p
    return None


def definition(text):
    """The paragraph that defines `<sw>`: the version-pinned path built from the project's VERSION."""
    return find_block(text, r"<sw>", r"\.specwright/bin/<VERSION>/sw", r"VERSION")


class SkillCommands(unittest.TestCase):
    def test_every_skill_command_starts_with_sw(self):
        for path in SHIPPED + DOCS:
            text = read(path)
            with self.subTest(file=path.relative_to(ROOT).as_posix()):
                names = sorted(set(SCRIPT.findall(text)))
                if path in DOCS:
                    # the docs may name a retired script when they say what replaced it; never as a command to run
                    names = [n for n in names
                             if any(re.search(r"(?:bash|sh)\s+\S*" + re.escape(n), s) for s in spans(text))]
                self.assertEqual(names, [], f"{path.name} still names a script or Python helper")
                self.assertNotRegex(text, r"\[vcs\]|\[as\]", f"{path.name} still uses the [vcs] or [as] shorthand")
                bad = []
                for span in spans(text):
                    first = re.sub(r"^(?:bash|sh)\s+", "", span).split()
                    if not first:
                        continue
                    if path not in DOCS and first[0] == "sw" and len(first) > 1:
                        bad.append(span)  # a bare `sw ...` command: an `sw` on PATH is never used
                    if re.match(r"(?:bash|sh)\s", span) and re.search(r"\bscripts?/", span):
                        bad.append(span)
                    if first[0] in SUBCOMMANDS and first[0] not in ("run", "update", "version", "finish", "review",
                                                                   "release", "commit") and len(first) > 1 and not span.startswith("<sw>"):
                        # `vcs state ...`, `as <login> ...`, `pr snapshot ...`, `gate lock ...` as a command
                        if first[0] in ("vcs", "gate") or (first[0] in ("as", "pr") and len(first) > 2 and "<" in first[1]):
                            bad.append(span)
                self.assertEqual(bad, [], f"{path.name} gives a Specwright command that does not start with <sw>")

    def test_no_bash_syntax_in_skill_commands(self):
        for path in SHIPPED:
            with self.subTest(file=path.relative_to(ROOT).as_posix()):
                for span in spans(read(path)):
                    self.assertNotRegex(span, r"&&|\$\(|\$L\b|\bprintf\b|\btest -[a-z]\b|\bmkdir\b|\brm -r\b|\benv -u\b|2>/dev/null|<<",
                                        f"{path.name} gives a command that needs bash syntax: {span}")
                self.assertNotRegex(read(path), r"\bGH_REPO\b.{0,40}\bunset\b|\bunset\b.{0,40}\bGH_REPO\b|env -u GH_REPO",
                                    f"{path.name} still tells the agent to unset GH_REPO (sw keeps it out itself)")

    def test_gh_api_paths_have_no_leading_slash(self):
        for path in SHIPPED + DOCS:
            with self.subTest(file=path.relative_to(ROOT).as_posix()):
                self.assertNotRegex(read(path), r"gh api\s+(?:--[\w-]+(?:\s+(?!\")[^\s\"/][^\s]*)?\s+)*[\"']?/",
                                    f"{path.name} writes a gh api path with a leading slash (Git Bash converts it)")

    def test_sw_is_defined_once_per_skill(self):
        for name, path in SKILLS.items():
            text = read(path)
            with self.subTest(skill=name):
                d = definition(text)
                self.assertTrue(d, f"specwright-{name} never defines <sw> from the project's VERSION")
                self.assertEqual(len(re.findall(r"\.specwright/bin/<VERSION>/sw", text)), 1,
                                 f"specwright-{name} defines the sw path more than once")
                self.assertRegex(d, r"sw\.exe", "the definition omits the Windows name")
                self.assertRegex(d, r"SPECWRIGHT_HOME", "the definition omits <home> and SPECWRIGHT_HOME")
                self.assertRegex(text, r"<sw> (vcs|as|pr|commit|finish|review|release|gate|version)\b",
                                 f"specwright-{name} defines <sw> and never runs it")

    def test_missing_binary_says_rerun_install(self):
        for name, path in SKILLS.items():
            d = definition(read(path)) or ""
            with self.subTest(skill=name):
                self.assertRegex(d, r"(?is)holds? no `?sw`?|does not exist|is missing|no file at",
                                 "the definition does not say what a missing binary is")
                self.assertRegex(d, r"(?is)rerun the install prompt", "a missing binary does not say to rerun the install prompt")
                self.assertRegex(d, r"(?is)never.{0,120}(another version|`?PATH`?)",
                                 "the definition does not forbid another version's binary or one on PATH")
                self.assertRegex(d, r"(?is)never.{0,200}`?PATH`?", "the definition does not forbid an sw on PATH")

    def test_skills_validate_version_before_building_path(self):
        for name, path in SKILLS.items():
            text = read(path)
            d = definition(text) or ""
            with self.subTest(skill=name):
                check = re.search(r"(?is)(?:x\.y\.z|major\.minor\.patch)", d)
                self.assertTrue(check, "the definition does not check VERSION against x.y.z")
                build = d.find(".specwright/bin/<VERSION>/sw")
                self.assertLess(check.start(), build, "VERSION is checked after the path is built")
                self.assertRegex(d, r"(?is)optional pre-release|-<pre-release>|pre-release", "the check ignores the pre-release suffix")
                self.assertRegex(d, r"(?is)\bstop\b.{0,200}before building (any|the) path.{0,200}rerun the install prompt|"
                                    r"rerun the install prompt.{0,200}before building (any|the) path",
                                 "a VERSION that is not a version does not stop before any path is built")

    def test_probe_has_10_second_timeout_and_one_object(self):
        for name, path in SKILLS.items():
            d = definition(read(path)) or ""
            with self.subTest(skill=name):
                self.assertIn("<sw> version --json", d)
                self.assertRegex(d, r"(?i)10-second (tool )?timeout", "the probe has no 10-second timeout")
                self.assertRegex(d, r"(?is)exits? 0", "the probe does not require exit 0")
                self.assertRegex(d, r"(?is)one JSON object", "the probe does not require one JSON object")
                self.assertRegex(d, r"(?is)interface 3", "the probe does not require interface 3")
                self.assertRegex(d, r"(?is)before the first other", "the probe does not run before the first other sw command")
                self.assertRegex(d, r"(?is)no other `?<sw>`? command", "a failed probe does not stop every other sw command")

    def test_older_project_is_told_to_update(self):
        for name, path in SKILLS.items():
            d = definition(read(path)) or ""
            with self.subTest(skill=name):
                self.assertRegex(d, r"(?is)interface (2 or )?1|older project|reports? (another|an older) interface",
                                 "an older project served by newer skills is not told to update")
                self.assertRegex(d, r"(?is)update this project", "an older project is not told to update this project")
                self.assertRegex(d, r"(?is)reports? interface 2 or 1", "a binary reporting interface 2 or 1 is not named")

    def test_sw_mismatch_stop_is_handled(self):
        for name, path in SKILLS.items():
            d = definition(read(path)) or ""
            with self.subTest(skill=name):
                self.assertIn("sw_mismatch", d)
                self.assertRegex(d, r"(?is)sw_mismatch.{0,300}(stop|rerun the install prompt)",
                                 "a sw_mismatch document does not stop the step")

    def test_pr_skill_has_exactly_one_interface_line(self):
        text = read(SKILLS["pr"])
        self.assertEqual(re.findall(r"^interface (\d+)\s*$", text, re.M), ["3"])
        for name, path in SKILLS.items():
            if name != "pr":
                self.assertNotRegex(read(path), r"(?m)^interface \d+\s*$", f"specwright-{name} carries a second interface line")

    def test_store_gate_lock_runs_through_sw_gate(self):
        for name in ("branch", "roadmap"):
            text = read(SKILLS[name])
            with self.subTest(skill=name):
                for sub in ("lock", "show", "unlock"):
                    self.assertRegex(text, r"<sw> --project [\"`]?<code toplevel>[\"`]? gate " + sub,
                                     f"specwright-{name} never runs `<sw> --project <code toplevel> gate {sub}`")
                self.assertNotIn("specwright-gate.lock\"", text)
                self.assertRegex(text, r"gate unlock --stale", "a stale lock is not removed through `gate unlock --stale`")

    def test_undo_plan_steps_replace_the_script(self):
        text = read(SKILLS["finish"])
        self.assertRegex(text, r"`steps`.{0,200}`after_rerun_steps`|`after_rerun_steps`.{0,200}`steps`")
        self.assertNotRegex(text, r"`script`|`after_rerun`\b|bash <file>")

    def test_release_instructions_name_sw_release(self):
        schema = read(ROOT / "schemas" / "specwright" / "schema.yaml")
        skill = read(SKILLS["release"])
        for label, text in (("schema", schema), ("specwright-release", skill)):
            for sub in ("bump", "check", "notes"):
                self.assertRegex(text, r"<sw> release (?:--dir \S+ )?" + sub + r"\b", f"{label} never names `<sw> release {sub}`")
        self.assertRegex(schema, r"\.specwright/bin/<project VERSION>/sw|<sw> is the project's sw|`<sw>`", "the schema never says what <sw> is")


if __name__ == "__main__":
    unittest.main()
