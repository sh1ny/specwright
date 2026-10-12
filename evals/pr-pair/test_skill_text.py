"""skills/specwright-pr/SKILL.md calls the pr-pair.sh subcommands in the right places.

The script's decisions (identity, discovery, links, pair state, pass records, cleanup) are tested in
test_pr_pair.py; these checks make sure the skill actually uses them, by position in the text and not
by exact wording:

- `pr-pair.sh identity` comes before any push command;
- change PRs are found with `discover`, never with `gh pr list`;
- `link` runs after both PRs exist (after `ensure-pr`, and after the pushes);
- watch uses `pair-state`, feedback uses `pass` and `rounds`, cleanup uses `cleanup-plan`.

Run: python -m unittest discover evals/pr-pair
"""
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "skills" / "specwright-pr" / "SKILL.md"
TEXT = SKILL.read_text(encoding="utf-8")


def sub(name):
    """Pattern for `pr-pair.sh <name>` however the path before it is written (bash scripts/..., a variable)."""
    return re.compile(r"pr-pair\.sh[`\"']?\s+" + name + r"\b")


def sections(text):
    """{lowercased '## ' heading: (start offset, section text)}."""
    marks = [(m.start(), m.group(1).strip().lower()) for m in re.finditer(r"^## (.+)$", text, re.M)]
    out = {}
    for i, (start, title) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out[title] = (start, text[start:end])
    return out


SECTIONS = sections(TEXT)
# A push command, not prose that mentions pushing: `git push -u origin HEAD`, `git push origin <branch>`.
PUSH = re.compile(r"git push\s+(?:-\S+\s+)*origin")
NEGATION = re.compile(r"\b(not|never|instead|rather than|without|no longer|don't|do not)\b", re.I)


def positions(pattern, text=TEXT):
    return [m.start() for m in pattern.finditer(text)]


class SkillText(unittest.TestCase):
    def section(self, title):
        self.assertIn(title, SECTIONS, f"SKILL.md has no '## {title}' section; found {sorted(SECTIONS)}")
        return SECTIONS[title][1]

    def test_identity_before_any_push(self):
        ident, pushes = positions(sub("identity")), positions(PUSH)
        self.assertTrue(ident, "SKILL.md never runs `pr-pair.sh identity`")
        self.assertTrue(pushes, "SKILL.md has no push command; the check below would be vacuous")
        self.assertLess(ident[0], pushes[0], "the first `git push` comes before the first `pr-pair.sh identity`")
        ship = self.section("ship")
        s_ident, s_push = positions(sub("identity"), ship), positions(PUSH, ship)
        self.assertTrue(s_ident, "the ship section never runs `pr-pair.sh identity`")
        self.assertTrue(s_push, "the ship section has no push command")
        self.assertLess(s_ident[0], s_push[0], "ship pushes before it runs `pr-pair.sh identity`")

    def test_ship_pushes_every_repo_before_any_pr(self):
        ship = self.section("ship")
        a, b = re.search(r"^4a\. ", ship, re.M), re.search(r"^4b\. ", ship, re.M)
        self.assertTrue(a, "ship has no step 4a (validate and push each repo)")
        self.assertTrue(b, "ship has no step 4b (find or open each PR)")
        self.assertLess(a.start(), b.start(), "ship step 4b comes before step 4a")
        end = re.search(r"^5\. ", ship[b.end():], re.M)
        s4a, s4b = ship[a.start():b.start()], ship[b.start():b.end() + (end.start() if end else len(ship))]
        pushes, ensures = positions(PUSH, ship), positions(sub("ensure-pr"), ship)
        self.assertTrue(pushes and ensures)
        self.assertLess(max(pushes), min(ensures), "a push comes after the first `ensure-pr`")
        self.assertTrue(positions(PUSH, s4a), "step 4a has no push command")
        self.assertFalse(positions(PUSH, s4b), "step 4b pushes: every push belongs in 4a")
        self.assertFalse(positions(sub("ensure-pr"), s4a), "step 4a finds or opens a PR: that belongs in 4b")
        self.assertTrue(positions(sub("ensure-pr"), s4b), "step 4b never runs `pr-pair.sh ensure-pr`")
        self.assertRegex(s4a, r"(?i)store first", "step 4a does not push the store first")
        self.assertRegex(s4a, r"(?is)validate", "step 4a does not validate before it pushes")
        self.assertLess(re.search(r"(?i)validate", s4a).start(), positions(PUSH, s4a)[0], "4a pushes before it validates")
        stop = re.search(r"(?is)\b(validate|push)\b[^.]*\bfail[^.]*\bstop\b", s4a)
        self.assertTrue(stop, "step 4a does not say a failed validate or push stops")
        self.assertRegex(s4a, r"(?i)(open|update)s? no PR in either repo", "4a does not say that no PR is opened or updated in either repo")
        self.assertRegex(s4a, r"(?i)never report the change ready", "4a does not forbid reporting the change ready")
        self.assertRegex(s4a, r"(?i)which repo's push failed and its error", "4a does not report which push failed and its error")
        self.assertRegex(s4b, r"(?i)only (when|after|once) (every|all)[^.]*push", "step 4b does not wait for every push")

    def test_discover_replaces_gh_pr_list_for_change_prs(self):
        self.assertTrue(positions(sub("discover")), "SKILL.md never runs `pr-pair.sh discover`")
        ship = self.section("ship")
        self.assertTrue(positions(sub("discover"), ship), "the ship section does not use `discover` to find a change's PR")
        for m in re.finditer(r"gh pr list", TEXT):
            line = TEXT[TEXT.rfind("\n", 0, m.start()) + 1:TEXT.find("\n", m.end())]
            self.assertRegex(line, NEGATION, f"SKILL.md still finds change PRs with `gh pr list`: {line.strip()[:120]!r}")

    def test_link_after_both_prs_exist(self):
        ship = self.section("ship")
        links, ensures, pushes = positions(sub("link"), ship), positions(sub("ensure-pr"), ship), positions(PUSH, ship)
        self.assertTrue(links, "the ship section never runs `pr-pair.sh link`")
        self.assertTrue(ensures, "the ship section never runs `pr-pair.sh ensure-pr`")
        self.assertLess(max(ensures), links[0], "`link` runs before the last PR is found or created (`ensure-pr`)")
        self.assertTrue(pushes, "the ship section has no push command")
        self.assertLess(pushes[0], links[0], "`link` runs before the first push")

    def test_watch_uses_pair_state_and_cleanup_plan(self):
        watch = self.section("watch")
        self.assertTrue(positions(sub("pair-state"), watch), "the watch section never runs `pr-pair.sh pair-state`")
        plans = positions(sub("cleanup-plan"))
        self.assertTrue(plans, "SKILL.md never runs `pr-pair.sh cleanup-plan`")
        homes = [t for t, (_, body) in SECTIONS.items() if positions(sub("cleanup-plan"), body)]
        self.assertTrue(set(homes) & {"watch"} or any("cleanup" in h for h in homes),
                        f"`cleanup-plan` is in {homes}, neither watch nor a cleanup section")
        self.assertLess(positions(sub("pair-state"))[0], plans[0], "`cleanup-plan` is described before `pair-state`")

    def refresh_bullet(self):
        watch = self.section("watch")
        at = watch.find("refresh:head")
        self.assertNotEqual(at, -1, "the watch section never reads a `refresh:head` blocker")
        start = watch.rfind("\n   - ", 0, at) + 1
        end = watch.find("\n   - ", at)
        return watch[start:end if end != -1 else len(watch)]

    def test_watch_refreshes_on_a_refresh_blocker(self):
        watch = self.section("watch")
        b = self.refresh_bullet()
        self.assertLess(positions(sub("pair-state"), watch)[0], watch.index("refresh:head"), "`refresh:head` is described before `pair-state`")
        self.assertRegex(b, r"`refresh`", "the bullet never reads the `refresh` field of `pair-state`")
        head = re.search(r"`refresh:head[^`]*`[^;]*", b)
        self.assertTrue(head, "`refresh:head` has no rule")
        self.assertRegex(head.group(0), r"(?i)one-off snapshot", "`refresh:head` does not take a one-off snapshot")
        self.assertRegex(head.group(0), r"same PR", "`refresh:head` does not snapshot the same PR")
        self.assertRegex(b, r"(?i)once per wake", "the refresh is not limited to once per wake")
        self.assertRegex(b, r"(?is)`pair-state` again", "`pair-state` is not called again after the refresh")

    def test_watch_moves_its_wait_to_the_replaced_pr(self):
        b = self.refresh_bullet()
        pr = re.search(r"`refresh:pr[^`]*`[^;]*", b)
        self.assertTrue(pr, "`refresh:pr` has no rule")
        rule = pr.group(0)
        stop, snap, restart = (re.search(p, rule) for p in (r"(?i)stop that side's wait", r"`prs\.<side>`", r"(?i)restart[^.;,]*wait[^.;]*number"))
        self.assertTrue(stop, "`refresh:pr` does not stop that side's wait")
        self.assertTrue(snap, "`refresh:pr` does not take the PR number from `prs.<side>`")
        self.assertTrue(restart, "`refresh:pr` does not restart the wait on that number")
        self.assertLess(stop.start(), snap.start(), "the snapshot is taken before the old wait is stopped")
        self.assertLess(snap.start(), restart.start(), "the wait is restarted before the snapshot")
        self.assertRegex(b, r"(?is)still mismatched[^;.]*back to waiting", "a still-mismatched snapshot does not go back to waiting")
        self.assertRegex(b[b.index("still mismatched"):], r"`prs\.<side>`", "the wait after a mismatch is not on the PR `prs.<side>` names")

    def test_feedback_uses_pass_record_and_rounds(self):
        fb = self.section("feedback")
        for verb in ("write", "plan", "done"):
            self.assertTrue(positions(sub("pass\\s+" + verb), fb), f"the feedback section never runs `pr-pair.sh pass {verb}`")
        self.assertTrue(positions(sub("rounds"), fb), "the feedback section never runs `pr-pair.sh rounds`")
        w = positions(sub("pass\\s+write"), fb)[0]
        self.assertLess(positions(sub("pass\\s+plan"), fb)[0], positions(sub("pass\\s+done"), fb)[0],
                        "`pass done` comes before `pass plan`")
        self.assertLess(positions(sub("rounds"), fb)[0], w, "`rounds` should be read before the pass record is written")
        # the `resume` bullet of step 2 runs the rows the plan reads from GitHub: reactions (#25) and the pair link (#30)
        resume = next((l for l in fb.splitlines() if l.lstrip().startswith("- `resume`")), "")
        self.assertTrue(resume, "feedback step 2 has no `resume` bullet")
        self.assertRegex(resume, r"`todo` `?react`? rows?[^.;]*pr-reply\.sh[^.;]*react",
                         "`resume` does not run `todo` react rows with `pr-reply.sh react`")
        self.assertRegex(resume, r"ship step 5[^.;]*`link` row", "`resume` does not run ship step 5 for a `todo` link row")
        for token in ("code.url", "store.url", "--peer-url"):
            self.assertIn(token, resume, f"`resume` does not pass the link row's {token}")
        self.assertLess(resume.index("react"), resume.rindex("plan again"), "`resume` does not plan again after the react and link rows")
        self.assertNotRegex(TEXT, r"(?<!gh run )\brerun\b", "SKILL.md still mentions the removed `rerun` reaction state")  # `gh run rerun` is unrelated

    def feedback_steps(self):
        fb = self.section("feedback")
        return {int(m.group(1)): fb[m.start():(nxt.start() if (nxt := re.compile(r"^\d+\. ", re.M).search(fb, m.end())) else len(fb))]
                for m in re.finditer(r"^(\d+)\. ", fb, re.M)}

    def test_feedback_judges_rebound_threads(self):
        step = self.feedback_steps()[4]
        at = step.find("`rebound: true`")
        self.assertNotEqual(at, -1, "feedback step 4 never reads `rebound: true`")
        rule = step[at:at + 600]
        self.assertRegex(rule, r"(?is)edited by the reviewer before your reply", "the rebound rule does not say the edit came before the reply")
        self.assertRegex(rule, r"(?is)answered an older text", "the rebound rule does not say the reply answered older text")
        self.assertRegex(rule, r"(?is)judge its current comments as a new finding", "a rebound thread is not judged as a new finding")
        self.assertRegex(rule, r"(?is)without `--resolve` if it is already resolved", "a resolved rebound thread is not replied to without `--resolve`")
        self.assertRegex(rule, r"(?is)never re-open", "the rebound rule never says not to re-open the thread")

    def test_feedback_reads_clipped_items_in_full(self):
        step = self.feedback_steps()[1]
        at = step.find("`clipped: true`")
        self.assertNotEqual(at, -1, "feedback step 1 never reads `clipped: true`")
        rule = step[max(0, at - 80):at + 600]
        self.assertRegex(rule, r"(?i)\bevery\b", "step 1 does not read every clipped item")
        self.assertRegex(rule, r"pr-snapshot\.sh[^`]*--full", "step 1 does not read clipped items with `pr-snapshot.sh --full`")
        self.assertRegex(rule, r"(?is)before[^.;]*step 5", "step 1 does not put the full read before step 5 judges")
        self.assertRegex(rule, r"(?is)full body", "step 1 does not judge on the full body")

    def test_feedback_hands_over_an_unreadable_clipped_item(self):
        step = self.feedback_steps()[1]
        at = step.find("`clipped: true`")
        self.assertNotEqual(at, -1, "feedback step 1 never reads `clipped: true`")
        rule = step[at:]
        fail = re.search(r"(?is)(fails|cannot be read|exits? non-zero|unreadable)[^.]*\.", rule)
        self.assertTrue(fail, "step 1 never says what a failed `--full` read does")
        self.assertRegex(rule, r"(?i)manual read", "an unreadable clipped item is not reported as needing a manual read")
        self.assertRegex(rule, r"(?is)neither (drop|answer)[^.]*(drop|answer)|not (drop|answer)[^.]*(or|nor)[^.]*(drop|answer)",
                         "an unreadable clipped item may still be dropped or answered")
        self.assertRegex(rule, r"(?i)report", "an unreadable clipped item is not reported to the user")

    def test_feedback_step_8_passes_rev(self):
        steps = self.feedback_steps()
        step = steps[8]
        for line in (l for l in step.splitlines() if "pr-reply.sh" in l and re.search(r"pr-reply\.sh <pr> (thread|comment)", l)):
            self.assertIn("--rev", line, f"step 8 does not pass `--rev` on: {line.strip()[:100]!r}")
        self.assertRegex(step, r"`--rev <[^>`]*rev[^>`]*>`", "step 8 never says what `--rev` takes")
        exit5 = re.search(r"(?i)exit 5[^.;]*", step)
        self.assertTrue(exit5, "step 8 never handles exit 5")
        self.assertRegex(exit5.group(0), r"(?i)fresh snapshots", "exit 5 does not send the pass back to fresh snapshots")
        self.assertRegex(exit5.group(0), r"(?i)judge[^.;]*again", "exit 5 does not judge the item again")
        exit3 = re.search(r"(?i)exit 3[^.;]*", step)
        self.assertTrue(exit3, "step 8 never handles exit 3")
        self.assertRegex(exit3.group(0), r"(?i)stop", "exit 3 does not stop")
        self.assertRegex(exit3.group(0), r"(?i)report", "exit 3 does not report")
        self.assertRegex(step, r"(?i)--rev.*every `pr-reply\.sh [a-z|]*resolve", "step 8 does not pass `--rev` to `resolve`")
        self.assertRegex(step, r"(?is)never[^.]*`--full`", "step 8 does not forbid taking `--rev` from `--full`")
        self.assertRegex(step, r"revision\.rev", "step 8 does not name the pass record's `revision.rev`")
        resume = next((l for l in self.section("feedback").splitlines() if l.lstrip().startswith("- `resume`")), "")
        self.assertRegex(resume, r"`revision\.rev`", "`resume` does not pass the finding's recorded `revision.rev`")
        self.assertRegex(resume, r"--rev", "`resume` does not pass it as `--rev`")

    def test_resolution_retry_takes_a_fresh_rev(self):
        # the reply is part of the thread's rev: a resolution retried after it needs the rev as it stands after the reply
        step = self.feedback_steps()[8]
        m = re.search(r"(?i)exit 1 after a posted reply[^\n]*", step)
        self.assertTrue(m, "step 8 never handles exit 1 after a posted reply")
        self.assertRegex(m.group(0), r"(?i)fresh snapshot", "a resolution retry does not take a fresh snapshot")
        self.assertRegex(m.group(0), r"resolve_pending", "a resolution retry does not require `resolve_pending`")
        self.assertRegex(m.group(0), r"(?i)never[^.]*(judged|revision\.rev)", "a resolution retry may reuse the pre-reply rev")
        resume = next((l for l in self.section("feedback").splitlines() if l.lstrip().startswith("- `resume`")), "")
        self.assertRegex(resume, r"(?i)resol[^.]*fresh snapshot", "`resume` retries a resolution with the recorded rev")

    def test_feedback_uses_pass_record_for_repo_local(self):
        # a repo-local change (no store) uses the same pass record and rounds, with `--store` left out
        repos = self.section("the repos and prs of a change")
        local = next((l for l in repos.splitlines() if l.lstrip("- ").startswith("**Repo-local changes**")), "")
        self.assertTrue(local, "the repos section has no repo-local bullet")
        tail = local.rpartition(";")[2]  # the list of subcommands for store-backed changes only
        for sub_name in ("expected", "pair-state", "cleanup-plan"):
            self.assertIn(f"`{sub_name}`", tail, f"the store-backed-only list does not name `{sub_name}`: {local!r}")
        for sub_name in ("pass", "rounds"):
            self.assertNotIn(f"`{sub_name}`", tail, f"`{sub_name}` is still listed as store-backed only: {local!r}")
        fb = self.section("feedback")
        steps = {int(m.group(1)): fb[m.start():(nxt.start() if (nxt := re.compile(r"^\d+\. ", re.M).search(fb, m.end())) else len(fb))]
                 for m in re.finditer(r"^(\d+)\. ", fb, re.M)}
        for n in (2, 3, 6, 10):
            self.assertIn(n, steps, f"feedback has no step {n}")
            self.assertRegex(steps[n], r"[Rr]epo-local[^\n]{0,120}without\s+`--store`",
                             f"feedback step {n} does not run its pass/rounds call for repo-local changes without `--store`")
        for n in (2, 6):
            self.assertNotIn("(store-backed)", steps[n], f"feedback step {n} is still store-backed only")
        self.assertFalse(steps[10].startswith("10. Store-backed"), "feedback step 10 is still store-backed only")
        self.assertNotIn("repo-local the trailers in `git log", steps[3], "step 3 still reads repo-local rounds from git log by hand")

    def test_feedback_asks_before_adopting_a_foreign_record(self):
        fb = self.section("feedback")
        plan, adopt, done = (positions(sub("pass\\s+" + v), fb) for v in ("plan", "adopt", "done"))
        self.assertTrue(adopt, "the feedback section never runs `pr-pair.sh pass adopt`")
        w = positions(sub("pass\\s+write"), fb)[0]
        for name, at in (("plan", plan[0]), ("done", done[0]), ("adopt", adopt[0])):
            self.assertIn("--owner", fb[at:fb.index("`", at)], f"`pass {name}` is not given `--owner`")
        self.assertLess(plan[0], adopt[0], "`pass adopt` comes before `pass plan`")
        before = fb[plan[0]:adopt[0]]
        self.assertRegex(before, r"\bowned\b", "the text before `pass adopt` never reads `owned`")
        self.assertRegex(before, r"\bask", "the text before `pass adopt` never asks the user")
        self.assertRegex(before, r"\bgone\b", "the text before `pass adopt` never asks whether the owner is gone")
        none = re.search(r"`record: false`|`record` is `false`", before)
        gate = re.search(r"If `owned` is", before)
        self.assertTrue(none, "step 2 never says what to do with a plan that has `record: false` (a first pass has no `owned` field)")
        self.assertLess(none.start(), gate.start(), "`record: false` is handled after the `owned` gate, so a first pass has no instruction to proceed")
        self.assertRegex(before[none.start():gate.start()], r"\bnone\b", "the `record: false` case does not name `status: none`")
        self.assertRegex(before[none.start():gate.start()], r"carry on|proceed|start", "the `record: false` case does not say to proceed")
        self.assertIn("--from", fb[adopt[0]:fb.index("`", adopt[0])], "`pass adopt` is not given `--from`")
        self.assertRegex(fb, r"\bnot_owner\b")
        self.assertRegex(fb, r"\brecord_busy\b")
        self.assertRegex(fb, r"never remove a lock", "the lock rule is missing")
        self.assertRegex(fb[w:w + 700], r"owner", "the text after `pass write` never says to keep the owner id it returns")


DESCRIPTION = SKILL.parent / "references" / "description.md"


class ClosingReferences(unittest.TestCase):
    """description.md and the ship section carry the closing-reference rules (#61)."""

    desc = DESCRIPTION.read_text(encoding="utf-8")

    def test_description_requires_one_closing_keyword_per_issue(self):
        self.assertRegex(self.desc, r"(?i)one (closing )?keyword per issue")
        self.assertRegex(self.desc, r"(?i)own line")
        self.assertRegex(self.desc, r"Fixes #N")

    def test_description_keeps_related_for_partial_fixes(self):
        self.assertRegex(self.desc, r"Related: #N")
        self.assertRegex(self.desc, r"(?i)(only in part|partly|not fully)")

    def test_description_uses_cross_repo_form_without_a_pr_in_the_issue_repo(self):
        self.assertRegex(self.desc, r"Fixes <owner>/<repo>#N")
        self.assertRegex(self.desc, r"Related: <owner>/<repo>#N")
        self.assertRegex(self.desc, r"(?i)no PR is expected")
        self.assertRegex(self.desc, r"(?i)repository that holds the issue")

    def ship_43(self):
        ship = SECTIONS["ship"][1]
        m = re.search(r"^4b\. .*$", ship, re.M)
        self.assertTrue(m, "ship step 4b not found")
        end = re.search(r"^5\. ", ship[m.end():], re.M)
        return ship[m.start():m.end() + (end.start() if end else len(ship))]

    def test_ship_runs_closing_check_after_ensure_pr(self):
        step = self.ship_43()
        checks, ensures = positions(sub("closing-check"), step), positions(sub("ensure-pr"), step)
        self.assertTrue(checks, "ship step 4.3 never runs `pr-pair.sh closing-check`")
        self.assertTrue(ensures)
        self.assertLess(ensures[0], checks[0], "`closing-check` runs before `ensure-pr`")
        self.assertRegex(step, r"\bnot_default_base\b")
        self.assertRegex(step, r"(?i)not done", "an unreadable check (exit 3) is not reported as not done")

    def test_ship_never_rewrites_a_found_pr_description_on_mismatch(self):
        step = self.ship_43()
        tail = step[step.find("closing-check"):]
        self.assertNotEqual(step.find("closing-check"), -1)
        self.assertRegex(tail, r"(?is)mismatch`? on a `found` PR[^.;]*(report|ask)")
        self.assertRegex(tail, r"(?i)never (edit|rewrite)[^.]*unprompted")
        self.assertRegex(tail, r"(?is)mismatch`? on a `created` PR[^.;]*rewrite")
        self.assertRegex(tail, r"(?i)nothing but a keyword and references")

    def test_ship_stops_after_a_second_mismatch(self):
        step = self.ship_43()
        tail = step[step.find("closing-check"):]
        self.assertNotEqual(step.find("closing-check"), -1)
        self.assertRegex(tail, r"gh pr edit[^.]*--body-file")
        self.assertRegex(tail, r"(?is)second mismatch[^.]*stop|stop[^.]*second mismatch")
        self.assertRegex(tail, r"(?i)names? the `?missing`? issues")


FINISH = SKILL.parents[1] / "specwright-finish" / "SKILL.md"


class CleanupClosingReferences(unittest.TestCase):
    """Cleanup after merge closes the issues a merged PR's closing lines named and GitHub left open (#61 part 3)."""

    def cleanup(self):
        self.assertIn("cleanup after merge", SECTIONS, f"SKILL.md has no '## Cleanup after merge' section; found {sorted(SECTIONS)}")
        return SECTIONS["cleanup after merge"][1]

    def closing_bullet(self):
        text = self.cleanup()
        at = text.find("closed-check")
        self.assertNotEqual(at, -1, "Cleanup after merge never runs `pr-pair.sh closed-check`")
        start = text.rfind("\n- ", 0, at) + 1
        end = text.find("\n- ", at)
        return text[start:end if end != -1 else len(text)]

    def test_cleanup_closes_open_intended_issues(self):
        text = self.cleanup()
        self.assertTrue(positions(sub("closed-check"), text), "Cleanup after merge never runs `pr-pair.sh closed-check`")
        b = self.closing_bullet()
        self.assertRegex(b, r"--repos", "`closed-check` is not given the change's repositories as `--repos`")
        self.assertRegex(b, r"(?i)each merged PR", "the check does not run for each merged PR")
        close = re.search(r"gh issue close <n> --repo <owner>/<name> --comment", b)
        self.assertTrue(close, "an `open` issue is not closed with `gh issue close <n> --repo ... --comment`")
        self.assertRegex(b, r"<pr_url>", "the closing comment does not name the PR")
        self.assertRegex(b[close.start() - 12:close.start()], r"\[as\]", "the close does not run under the repository's identity")
        self.assertRegex(b, r"(?i)each `open` issue", "only `open` issues are closed")
        self.assertRegex(b, r"(?i)Related", "the text never says a `Related:` issue is not closed")
        fin = FINISH.read_text(encoding="utf-8")
        merged = fin[fin.index("- **After the PR is merged**"):]
        merged = merged[:merged.index("\n\n")]
        self.assertRegex(merged, r"specwright-pr\W+\*\*Cleanup after merge\*\*", "finish does not point to `specwright-pr` Cleanup after merge")
        self.assertRegex(merged, r"closed-check|closing|issues", "finish's After the PR is merged never mentions the issue backstop")
        self.assertNotIn("Store-backed: follow `specwright-pr` **Cleanup after merge** instead", merged,
                         "finish still sends only store-backed changes to Cleanup after merge")

    def test_cleanup_asks_before_closing(self):
        b = self.closing_bullet()
        ask = re.search(r"(?i)list(?:s)? them all with their PRs", b)
        self.assertTrue(ask, "the bullet never lists every `open` issue with its PR before closing")
        self.assertRegex(b, r"(?i)when any merged PR of the change has `open` issues", "the question is not tied to the merged PRs' `open` issues")
        self.assertRegex(b, r"(?i)one question for the change", "the user is not asked one question for the whole change")
        self.assertRegex(b, r"(?i)(ask|asks) nothing", "the text never says nothing is asked when there are no `open` issues")
        close = b.find("gh issue close")
        self.assertTrue(0 <= ask.start() < close, "the question must come before `gh issue close`")
        self.assertRegex(b, r"(?i)each `open` issue (the user )?confirmed|only (the )?confirmed", "only confirmed issues are closed")
        self.assertRegex(b, r"(?is)declined[^.]*left open|left open[^.]*declined", "declined issues are not reported as left open")

    def test_cleanup_reports_issues_outside_the_change(self):
        b = self.closing_bullet()
        m = re.search(r"`outside`[^.;]*", b)
        self.assertTrue(m, "the closing bullet never handles `outside` issues")
        self.assertRegex(b, r"(?is)`outside`.{0,200}never close|never close.{0,200}`outside`", "`outside` issues may be closed")
        self.assertRegex(b, r"(?i)outside[^.]{0,120}(report|list)|(report|list)[^.]{0,120}outside")

    def test_cleanup_reports_backstop_not_done(self):
        b = self.closing_bullet()
        m = re.search(r"(?i)exit 3[^.;]*", b)
        self.assertTrue(m, "the closing bullet never handles exit 3")
        self.assertRegex(m.group(0), r"(?i)not done")
        self.assertRegex(m.group(0), r"(?i)continue|branch cleanup")
        self.assertRegex(b, r"(?i)close nothing|closes nothing|nothing is closed")

    def test_cleanup_closes_nothing_off_the_default_branch(self):
        b = self.closing_bullet()
        m = re.search(r"`not_default_base`[^.]*\.", b)
        self.assertTrue(m, "the closing bullet never handles `not_default_base`")
        self.assertRegex(m.group(0), r"(?i)close nothing")
        self.assertRegex(m.group(0), r"default branch")
        self.assertRegex(b, r"`not_merged`[^.]*nothing")

    def test_cleanup_never_recloses_reopened(self):
        b = self.closing_bullet()
        m = re.search(r"`reopened`[^.]*\.", b)
        self.assertTrue(m, "the closing bullet never handles `reopened`")
        self.assertRegex(b, r"(?is)`reopened`.{0,200}never close|never close.{0,200}`reopened`", "a `reopened` issue may be closed again")
        self.assertRegex(b, r"(?i)reopened by a person|a person reopened|person reopened")

    def test_cleanup_reports_a_failed_close_and_continues(self):
        b = self.closing_bullet()
        m = re.search(r"(?i)a failed close[^;]*(;[^.]*)?\.", b)
        self.assertTrue(m, "the closing bullet never handles a failed close")
        self.assertRegex(m.group(0), r"(?i)closed")
        self.assertRegex(m.group(0), r"(?i)still open")
        self.assertRegex(m.group(0), r"(?i)continue")
        self.assertRegex(m.group(0), r"(?i)later cleanup")


class BodyFiles(unittest.TestCase):
    """A step that writes a body or message to a temp file also removes it once the command that reads it has run."""

    REMOVE = r"(?i)remove (the|that|each|this) (body |temp(orary)? )?files?\b.{0,120}\bwhatever (its|the|that command's) outcome"

    def step(self, section, label, nxt):
        body = SECTIONS[section][1]
        m = re.search(r"^%s " % re.escape(label), body, re.M)
        self.assertTrue(m, f"the {section} section has no step {label}")
        end = re.search(r"^%s " % re.escape(nxt), body[m.end():], re.M) if nxt else None
        return body[m.start():m.end() + end.start()] if end else body[m.start():]

    def test_every_body_file_step_removes_its_file(self):
        passages = {
            "ship 4b (description and closing-line rewrite)": self.step("ship", "4b.", "5."),
            "ship 6 (review request)": self.step("ship", "6.", "7."),
            "feedback 8 (replies)": self.step("feedback", "8.", "9."),
        }
        limit = SECTIONS["feedback"][1]
        at = limit.index("**After the limit**")
        passages["after the limit (issue bodies)"] = limit[at:]
        for name, text in passages.items():
            self.assertRegex(text, r"(?i)\b(temp file|body file|--body-file|<file>)", f"{name}: no file is written; the test is stale")
            self.assertRegex(text, self.REMOVE, f"{name} does not tell the agent to remove the file whatever the command's outcome")
        ship4b = passages["ship 4b (description and closing-line rewrite)"]
        self.assertGreaterEqual(len(re.findall(self.REMOVE, ship4b)), 2, "ship 4b removes only one of its description and closing-line rewrite files")

    def test_every_mktemp_in_a_script_has_a_failure_path_cleanup(self):
        scripts = sorted(SKILL.parents[1].glob("*/scripts/*.sh"))
        self.assertTrue(scripts, "found no skills/*/scripts/*.sh")
        seen = 0
        for path in scripts:
            text = path.read_text(encoding="utf-8")
            if "mktemp" not in text:
                continue
            seen += 1
            self.assertRegex(text, r"""trap\s+'[^']*rm -f[^']*'\s+\S*EXIT|rm -f "\$tmp\"""",
                             f"{path.name} calls mktemp but has neither an EXIT trap nor an `rm -f \"$tmp\"` that removes the file")
        self.assertTrue(seen, "no script calls mktemp; the check is vacuous")


class FeedbackRerequest(unittest.TestCase):
    """Feedback re-requests from a fresh snapshot of the pushed head, planned by `pass plan`; the Settings rule is scoped."""

    def feedback(self):
        return SECTIONS["feedback"][1]

    def step9(self):
        m = re.search(r"^9\. .*$", self.feedback(), re.M)
        self.assertTrue(m, "feedback has no step 9")
        return m.group(0)

    def resume_bullet(self):
        fb = self.feedback()
        at = fb.index("   - `resume`")
        return fb[at:fb.index("\n   - `stop`", at)]

    def settings_rule(self):
        m = re.search(r"^\*\*Re-request review\*\*.*$", TEXT, re.M)
        self.assertTrue(m, "SKILL.md has no **Re-request review** paragraph")
        return m.group(0)

    def test_feedback_snapshots_pushed_head_before_rerequest(self):
        step9 = self.step9()
        for where, text in (("feedback step 9", step9), ("the resume `rerequest` row", self.resume_bullet())):
            snap = re.search(r"(?i)fresh snapshot of each pushed PR", text)
            self.assertTrue(snap, f"{where} does not take a fresh snapshot of each pushed PR")
            plan = re.search(r"`pass plan`", text[snap.end():])
            self.assertTrue(plan, f"{where} does not run `pass plan` with the fresh snapshots after taking them")
            self.assertRegex(text, r"(?i)before posting any request", f"{where} does not plan before posting any request")
            self.assertRegex(text, r"(?i)only the requests whose `?rerequest`? row is not `done`", f"{where} posts requests whose row is done")
            self.assertRegex(text, r"\breport (a |an )?`cutoff_source: pass_written`|`cutoff_source: pass_written`[^;]*\breport", f"{where} does not report a `cutoff_source: pass_written` row to the user")
        self.assertRegex(step9, r"(?i)step 1[^.]*snapshots[^.]*(predate|have not seen|not seen)", "step 9 does not say why the step 1 snapshots are not used")

    def test_rerequest_rule_is_scoped_to_inside_and_outside_a_pass(self):
        rule = self.settings_rule()
        inside = re.search(r"(?i)inside a feedback pass", rule)
        outside = re.search(r"(?i)outside a (feedback )?pass", rule)
        self.assertTrue(inside and outside, "the Re-request review paragraph does not split into inside and outside a feedback pass")
        self.assertLess(inside.start(), outside.start(), "the outside-a-pass rule comes before the inside rule")
        ins, out = rule[inside.start():outside.start()], rule[outside.start():]
        self.assertRegex(ins, r"`pass plan`[^.]*`rerequest` row[^.]*decides", "inside a pass the `pass plan` row does not decide")
        self.assertRegex(ins, r"(?i)post anyway[^.]*(does not|doesn't) apply", "inside a pass 'post anyway' is not ruled out")
        self.assertRegex(out, r"(?i)watch", "the outside rule does not name watch's CI-fix push")
        self.assertRegex(out, r"(?i)archive", "the outside rule does not name the archive-before-merge push")
        self.assertRegex(out, r"(?i)post anyway", "the outside rule lost 'post anyway when the push time is not found'")
        self.assertRegex(out, r"(?i)at most once per pushed head", "the outside rule lost the once-per-pushed-head rule")
        self.assertNotRegex(ins, r"(?i)at most once per pushed head", "the pass rule still carries the once-per-pushed-head rule")


class CleanupBranchCheck(unittest.TestCase):
    """Cleanup deletes a merged change branch only when `branch-check` says main has its work."""

    def bullets(self):
        cleanup = SECTIONS["cleanup after merge"][1]
        store = re.search(r"^- Store-backed: .*$", cleanup, re.M)
        local = re.search(r"^- Repo-local: .*$", cleanup, re.M)
        self.assertTrue(store and local, "Cleanup after merge lacks its store-backed or repo-local bullet")
        return {"store-backed": store.group(0), "repo-local": local.group(0)}

    def test_cleanup_runs_branch_check_before_deleting(self):
        for name, b in self.bullets().items():
            check = re.search(r"branch-check", b)
            self.assertTrue(check, f"the {name} cleanup bullet never runs `branch-check`")
            pull = b.find("pull --ff-only")
            self.assertTrue(0 <= pull < check.start(), f"the {name} bullet does not run `branch-check` after `pull --ff-only`")
            for m in re.finditer(r"branch -D", b):
                self.assertLess(check.start(), m.start(), f"the {name} bullet deletes with -D before `branch-check`")
            self.assertRegex(b, r"delete: true", f"the {name} bullet does not delete only on `delete: true`")
            self.assertRegex(b, r"(?i)otherwise[^.]*keep[^.]*branch|keep[^.]*branch[^.]*otherwise", f"the {name} bullet does not keep the branch otherwise")
            self.assertRegex(b, r"`lacking`", f"the {name} bullet does not report the `lacking` commits")
            self.assertRegex(b, r"`head_unknown`", f"the {name} bullet does not report `head_unknown`")
        local = self.bullets()["repo-local"]
        self.assertRegex(local, r"branch -D", "the repo-local bullet never deletes with -D on `delete: true`")
        self.assertRegex(local, r"--head <head_sha>", "the repo-local `branch-check` is not given `--head`")
        self.assertRegex(local, r"discover[^`]*--state merged", "the repo-local `--head` does not come from `discover --state merged`")
        self.assertRegex(local, r"`head_sha`", "the repo-local `--head` is not `discover`'s `head_sha`")
        self.assertRegex(local, r"`newest`", "the repo-local text does not pick `newest` when several PRs merged")
        self.assertNotRegex(local, r"(?i)\bpr view\b[^.]*headRefOid", "the repo-local `--head` comes from `gh pr view`")
        text = SECTIONS["cleanup after merge"][1]
        self.assertNotRegex(text, r"force_delete_allowed", "the cleanup text still mentions `force_delete_allowed`")
        self.assertNotRegex(text, r"-D` only when the PR is MERGED and its `headRefOid` equals the local branch tip",
                            "the cleanup text still deletes with -D when headRefOid equals the local tip")


class ArchiveHeadReview(unittest.TestCase):
    """Watch gives the archive head no new review round unless pr.review_after_archive is true (#69)."""

    def archive_rule(self):
        watch = SECTIONS["watch"][1]
        m = re.search(r"\*\*Archive before merge:\*\*", watch)
        self.assertTrue(m, "watch has no 'Archive before merge' rule")
        end = re.search(r"(?m)^   - Otherwise", watch[m.end():])
        return watch[m.start():m.end() + (end.start() if end else len(watch))]

    def test_watch_archive_head_no_request_no_reviewers(self):
        rule = self.archive_rule()
        self.assertRegex(rule, r"review-run\.sh[`\"']?\s+archive-only", "watch does not run `review-run.sh archive-only`")
        self.assertRegex(rule, r"(?is)archive_only: true.{0,400}no review request", "an archive-only head still gets a review request")
        self.assertRegex(rule, r"(?is)archive_only: true.{0,600}(no|without) `--reviewer`",
                         "an archive-only head is still watched with --reviewer arguments")
        self.assertRegex(rule, r"(?i)ready head", "the archive-only base is not the head watch last reported ready")
        self.assertRegex(rule, r"(?is)archive_only: false.{0,300}re-request", "a non-archive-only head is not re-requested")

    def test_watch_review_after_archive_true_rerequests(self):
        rule = self.archive_rule()
        self.assertRegex(rule, r"(?is)pr\.review_after_archive: true.{0,300}(re-request|0\.1\.13)",
                         "pr.review_after_archive: true does not keep the 0.1.13 behaviour")

    def test_watch_archive_review_required_asks_once(self):
        rule = self.archive_rule()
        self.assertRegex(rule, r"REVIEW_REQUIRED")
        self.assertIn("archive head needs a fresh approval", rule)
        self.assertRegex(rule, r"(?is)REVIEW_REQUIRED.{0,400}ask(s)? once", "watch does not ask once")
        self.assertRegex(rule, r"(?is)(on no|no →|declin).{0,200}(ready.{0,20}except|stop)",
                         "a declined request does not end in a ready-except-approval report")


class DescriptionReviewSection(unittest.TestCase):
    """description.md's Review section: amendments by trailer, open P2/P3 findings and waivers (D9)."""

    def review_block(self):
        text = DESCRIPTION.read_text(encoding="utf-8")
        m = re.search(r"(?m)^\*\*Review\b.*$", text)
        self.assertTrue(m, "description.md has no **Review** paragraph")
        end = re.search(r"(?m)^\*\*(?!Review)", text[m.end():])
        return text[m.start():m.end() + (end.start() if end else len(text))]

    def test_description_lists_amendment_trailers(self):
        block = self.review_block()
        self.assertRegex(block, r"Amendment:", "amendments are not identified by their trailer")
        self.assertRegex(block, r"<main>\.\.HEAD", "the trailers are not read from <main>..HEAD")
        self.assertRegex(block, r"(?i)clarification.{0,80}behaviour[- ]change|class", "the amendment's class is not given")

    def test_description_lists_open_p2_p3(self):
        block = self.review_block()
        self.assertRegex(block, r"(?is)P2.{0,20}P3.{0,200}(open|unfixed|left)", "open P2/P3 findings are not listed")
        self.assertRegex(block, r"(?i)file", "an open finding is not listed with its file")

    def test_description_lists_waivers(self):
        block = self.review_block()
        self.assertRegex(block, r"(?is)waive.{0,200}reason", "waived findings are not listed with the user's reason")
        self.assertRegex(block, r"review-run\.sh[`\"']?\s+gate", "the findings and waivers do not come from the record gate matched")

    def test_description_ignores_untrailered_amendments(self):
        block = self.review_block()
        self.assertRegex(block, r"(?is)(no|without) (an )?`?Amendment:`? trailer.{0,200}not listed|not listed.{0,200}(no|without) (an )?`?Amendment:`? trailer",
                         "drift amendments without a trailer are not excluded")

    def test_description_review_section_only_with_content(self):
        block = self.review_block()
        self.assertRegex(block, r"(?i)only when it has content|omit it when|none of these.{0,40}no (such )?section",
                         "the Review section is not omitted when empty")


if __name__ == "__main__":
    unittest.main()
