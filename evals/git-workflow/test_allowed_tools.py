"""Script invocations the cutover skills prescribe are preapproved under Claude Code's permission rules.

A skill's `allowed-tools` field lists the tools it may use without a prompt. This module reads each skill's grants
and the `bash ...` command lines its text prescribes, then evaluates them with the documented `Bash(...)` rule
matching (https://code.claude.com/docs/en/permissions): the `*` stands for any text, a trailing ` *` also matches the
bare command and requires the space, and a rule must match every subcommand of a compound command on its own
(separators `&&`, `||`, `;`, `|`, `|&`, `&` and newlines). It proves the grants cover the invocations, which a regex over
the frontmatter cannot: a skill that grants only `Bash(git *)` fails here when its text runs `bash .../vcs.sh`.

A skill with no `allowed-tools` field does not restrict tools: it inherits the session's permissions, so its
script calls are decided by the user's normal permission mode and not by the skill. It is not a restrictive allowlist,
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
# skills whose text runs vcs.sh (debug reads the backend and the changed paths with `state`)
RUNS_VCS = CUTOVER
GRANTED = ("branch", "commit", "finish")  # carry an explicit allowed-tools field today
SEPARATORS = re.compile(r"&&|\|\||\|&|[;|&\n]")
PLACEHOLDERS = {
    "${CLAUDE_SKILL_DIR}": "/skills/self",
    "<specwright-pr>": "/skills/specwright-pr",
    "<specwright-finish>": "/skills/specwright-finish",
    "<specwright-release>": "/skills/specwright-release",
    "<specwright-review>": "/skills/specwright-review",
    "<skill dir>": "/skills/self",
}
AS = "bash /skills/specwright-pr/scripts/as.sh eval-bot "


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


def prescribed_script_commands(name):
    """Each `bash ...` command line the skill's text prescribes in an inline code span, `[as]` expanded as the skill
    defines it and `<specwright-...>` folders replaced by a concrete path."""
    out = []
    for span in re.findall(r"`([^`\n]+)`", skill_text(name)):
        for ph, path in PLACEHOLDERS.items():
            span = span.replace(ph, path)
        span = span.replace("[as] ", AS)
        for sub in SEPARATORS.split(span):
            sub = sub.strip()
            if re.match(r"bash \S+\.sh\b", sub) or sub.startswith(AS):
                out.append(sub)
    return out


class RuleMatching(unittest.TestCase):
    """The matcher itself, against the rows of the permissions documentation."""

    def test_trailing_star_needs_the_space_and_matches_bare_command(self):
        self.assertTrue(rule_matches("ls *", "ls -la"))
        self.assertTrue(rule_matches("ls *", "ls"))
        self.assertFalse(rule_matches("ls *", "lsof"))
        self.assertTrue(rule_matches("ls*", "lsof"))

    def test_git_grant_does_not_cover_a_bash_script(self):
        self.assertFalse(allowed(["git *", "openspec *"], "bash /skills/specwright-pr/scripts/vcs.sh state --repo ."))
        self.assertTrue(allowed(["git *", "openspec *", "bash *"], "bash /skills/specwright-pr/scripts/vcs.sh state --repo ."))

    def test_compound_command_needs_every_subcommand_matched(self):
        self.assertFalse(allowed(["bash *"], "bash /x/vcs.sh state && rm -r /tmp/x"))
        self.assertTrue(allowed(["bash *", "rm *"], "bash /x/vcs.sh state && rm -r /tmp/x"))

    def test_middle_wildcard(self):
        self.assertTrue(rule_matches("git * main", "git push origin main"))
        self.assertFalse(rule_matches("git * main", "git push origin dev"))


class SkillScriptPermissions(unittest.TestCase):
    def test_skills_with_a_grant_cover_every_script_invocation_they_prescribe(self):
        for name in GRANTED:
            rules = grants(name)
            self.assertIsNotNone(rules, f"specwright-{name} lost its allowed-tools field")
            for cmd in prescribed_script_commands(name):
                self.assertTrue(allowed(rules, cmd), f"specwright-{name} grants {rules} but prescribes: {cmd}")

    def test_every_vcs_call_is_covered_where_the_skill_has_a_grant(self):
        for name in RUNS_VCS:
            calls = [c for c in prescribed_script_commands(name) if "scripts/vcs.sh" in c]
            self.assertTrue(calls, f"specwright-{name} prescribes no vcs.sh call")
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
            self.assertIn("bash *", rules, name)

    def test_skills_without_a_grant_field_stay_unrestricted(self):
        for name in CUTOVER:
            if name not in GRANTED:
                self.assertIsNone(grants(name), f"specwright-{name} gained a restrictive allowed-tools field; cover its scripts")


if __name__ == "__main__":
    unittest.main()
