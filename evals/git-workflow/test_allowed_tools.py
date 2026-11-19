"""The `sw` invocations the skills prescribe are preapproved under Claude Code's permission rules.

A skill's `allowed-tools` field lists the tools it may use without a prompt. This module reads each skill's grants
and the `<sw> ...` command lines its text prescribes, with `<sw>` expanded to a concrete version-pinned path
(`<home>/.specwright/bin/<VERSION>/sw`), then evaluates them with the documented `Bash(...)` rule
matching (https://code.claude.com/docs/en/permissions): the `*` stands for any text, a trailing ` *` also matches the
bare command and requires the space, and a rule must match every subcommand of a compound command on its own
(separators `&&`, `||`, `;`, `|`, `|&`, `&` and newlines). It proves the grants cover the invocations, which a regex over
the frontmatter cannot: a skill that grants only `Bash(git *)` fails here when its text runs `<sw> vcs`.

A skill with no `allowed-tools` field does not restrict tools: it inherits the session's permissions, so its
`sw` calls are decided by the user's normal permission mode and not by the skill. It is not a restrictive allowlist,
and nothing here treats its absence as a grant or as a failure.

This does not prove a live agent runs the commands; the live evals do that.

Run: python -m unittest discover evals/git-workflow -p "test_allowed_tools.py"
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
CUTOVER = ("branch", "commit", "finish", "pr", "roadmap", "review", "release", "debug")
# skills whose text runs `<sw> vcs` (debug reads the backend and the changed paths with `state`)
RUNS_VCS = CUTOVER
GRANTED = ("branch", "commit", "finish")  # carry an explicit allowed-tools field today
SEPARATORS = re.compile(r"&&|\|\||\|&|[;|&\n]")
SW = "/home/eval/.specwright/bin/1.2.3/sw"
# The skills name `sw.exe` on Windows: every grant must cover that spelling too.
SW_EXE = "C:/Users/eval/.specwright/bin/1.2.3/sw.exe"
GRANT = "*/.specwright/bin/*/sw *"
GRANT_EXE = "*/.specwright/bin/*/sw.exe *"


def skill_text(name):
    return (SKILLS / f"specwright-{name}" / "SKILL.md").read_text(encoding="utf-8")


def grants(name):
    """The Bash rules of the skill's `allowed-tools` field as pattern strings, or None when it has no such field."""
    fm = re.match(r"---\n(.*?)\n---\n", skill_text(name), re.S).group(1)
    line = re.search(r"(?m)^allowed-tools:\s*(.*)$", fm)
    return None if line is None else re.findall(r"Bash\(([^)]*)\)", line.group(1))


def rule_matches(rule, command):
    """One documented `Bash(rule)` against one simple command."""
    if rule.endswith(" *") and "*" not in rule[:-2]:
        prefix = rule[:-2]
        return command == prefix or command.startswith(prefix + " ")
    return re.fullmatch(".*".join(map(re.escape, rule.split("*"))), command, re.S) is not None


def allowed(rules, command):
    """Claude Code approves a compound command only when a rule matches each subcommand independently."""
    subs = [s.strip() for s in SEPARATORS.split(command) if s.strip()]
    return bool(subs) and all(any(rule_matches(r, s) for r in rules) for s in subs)


def prescribed_script_commands(name, sw=SW):
    """Each `<sw> ...` command line the skill's text prescribes in an inline code span or a code block, with `<sw>`
    expanded to a concrete version-pinned path."""
    text = skill_text(name)
    blocks = re.findall(r"```\n(.*?)```", text, re.S)
    spans = re.findall(r"`([^`\n]+)`", text) + [line for block in blocks for line in block.splitlines()]
    out = []
    for span in spans:
        span = span.strip().replace("<sw>", sw)
        for sub in SEPARATORS.split(span):
            sub = sub.strip()
            if sub.startswith(sw + " "):
                out.append(sub)
    return out


class RuleMatching(unittest.TestCase):
    """The matcher itself, against the rows of the permissions documentation."""

    def test_trailing_star_needs_the_space_and_matches_bare_command(self):
        self.assertTrue(rule_matches("ls *", "ls -la"))
        self.assertTrue(rule_matches("ls *", "ls"))
        self.assertFalse(rule_matches("ls *", "lsof"))
        self.assertTrue(rule_matches("ls*", "lsof"))

    def test_git_grant_does_not_cover_sw(self):
        self.assertFalse(allowed(["git *", "openspec *"], SW + " vcs state --repo ."))
        self.assertTrue(allowed(["git *", "openspec *", GRANT], SW + " vcs state --repo ."))

    def test_sw_grant_covers_only_a_version_pinned_sw(self):
        self.assertTrue(allowed([GRANT], "/home/u/.specwright/bin/0.38.0-rc.1+b2/sw version --json"))
        self.assertTrue(allowed([GRANT], "C:/Users/u/.specwright/bin/0.38.0/sw version --json"))
        self.assertFalse(allowed([GRANT], "C:/Users/u/.specwright/bin/0.38.0/sw.exe version --json"))
        self.assertTrue(allowed([GRANT_EXE], "C:/Users/u/.specwright/bin/0.38.0/sw.exe version --json"))
        self.assertFalse(allowed([GRANT_EXE], "C:/Users/u/bin/sw.exe version --json"))
        self.assertFalse(allowed([GRANT], "sw vcs state"))
        self.assertFalse(allowed([GRANT], "/usr/local/bin/sw vcs state"))

    def test_compound_command_needs_every_subcommand_matched(self):
        self.assertFalse(allowed([GRANT], SW + " vcs state && rm -r /tmp/x"))
        self.assertTrue(allowed([GRANT, "rm *"], SW + " vcs state && rm -r /tmp/x"))

    def test_middle_wildcard(self):
        self.assertTrue(rule_matches("git * main", "git push origin main"))
        self.assertFalse(rule_matches("git * main", "git push origin dev"))


class SkillScriptPermissions(unittest.TestCase):
    def test_skills_with_a_grant_cover_every_script_invocation_they_prescribe(self):
        for name in GRANTED:
            rules = grants(name)
            self.assertIsNotNone(rules, f"specwright-{name} lost its allowed-tools field")
            for sw in (SW, SW_EXE):
                cmds = prescribed_script_commands(name, sw)
                self.assertTrue(cmds, f"specwright-{name} prescribes no `<sw>` call")
                for cmd in cmds:
                    self.assertTrue(allowed(rules, cmd), f"specwright-{name} grants {rules} but prescribes: {cmd}")

    def test_every_vcs_call_is_covered_where_the_skill_has_a_grant(self):
        for name in RUNS_VCS:
            calls = [c for c in prescribed_script_commands(name) if c.startswith(SW + " vcs ")]
            self.assertTrue(calls, f"specwright-{name} prescribes no `<sw> vcs` call")
            rules = grants(name)
            if rules is None:
                continue  # no allowed-tools field: the skill does not restrict tools
            for cmd in calls:
                self.assertTrue(allowed(rules, cmd), f"specwright-{name} grants {rules}; not covered: {cmd}")

    def test_branch_commit_and_finish_keep_their_git_and_openspec_grants(self):
        for name in GRANTED:
            rules = grants(name)
            self.assertIn("git *", rules, name)
            self.assertIn("openspec *", rules, name)
            self.assertIn(GRANT, rules, name)
            self.assertIn(GRANT_EXE, rules, name)
            self.assertNotIn("bash *", rules, name)

    def test_skills_without_a_grant_field_stay_unrestricted(self):
        for name in CUTOVER:
            if name not in GRANTED:
                self.assertIsNone(grants(name), f"specwright-{name} gained a restrictive allowed-tools field; cover its scripts")


if __name__ == "__main__":
    unittest.main()
