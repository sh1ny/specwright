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
# The ship step that pushes each repo. The push itself is a script call (vcs.sh push) whose behaviour the evals/vcs tests own;
# this anchor only orders the step among the others.
PUSH = re.compile(r"Push each repo once its validate passed")
NEGATION = re.compile(r"\b(not|never|instead|rather than|without|no longer|don't|do not)\b", re.I)


def watch_step1():
    w = SECTIONS["watch"][1]
    return w[w.index("1. Wait in the background"):w.index("\n2. On wake")]


def watch_step3():
    w = SECTIONS["watch"][1]
    return w[w.index("\n3. Ready, per PR"):w.index("\n4. Stop and report")]


def step3_bullet(start):
    step = watch_step3()
    at = step.find("\n   - " + start)
    assert at != -1, f"watch step 3 has no '- {start}' bullet"
    end = step.find("\n   - ", at + 1)
    return step[at:end if end != -1 else len(step)]


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

    def test_watch_waits_until_attention(self):
        watch = self.section("watch")
        step1 = watch[watch.index("1. Wait in the background"):watch.index("\n2. On wake")]
        cmd = next((c for c in re.findall(r"`([^`]*pr-snapshot\.sh[^`]*)`", step1) if "--wait" in c), "")
        self.assertTrue(cmd, "watch step 1 has no `pr-snapshot.sh ... --wait` command")
        self.assertIn("--until attention", cmd, "the watch wait is not run with `--until attention`")
        self.assertIn("--reviewer-config", cmd, "the watch wait is not given `--reviewer-config`")
        self.assertIn("filtered", step1, "step 1 does not name the `filtered` field of the wake")
        for token, cond in (("--timeout 1800", r"short of ready[^.]*but the quiet window"),
                            ("--timeout <pr.settle in seconds>", r"every ready condition[^.]*but the quiet window"),
                            ("--timeout <rest of pr.settle since the push>", r"archive head[^.]*carry-over[^.]*before it is judged")):
            self.assertIn(token, step1, f"step 1 does not name `{token}`")
            ats = [m.start() for m in re.finditer(re.escape(token), step1)]
            self.assertTrue(any(re.search("(?is)" + cond, step1[at:at + 420]) for at in ats),
                            f"step 1 does not give the condition for `{token}`")

    def test_watch_timeout_wake_is_quiet_window(self):
        ready = watch_step3()
        self.assertRegex(ready, r"(?is)`timeout` wake[^.]*quiet window[^.]*filtered",
                         "the ready rule does not count any `timeout` wake as the quiet window, even with filtered polls")
        self.assertRegex(ready, r"(?is)1800 wait[^.]*wakes `timeout`.{0,300}without a further `pr\.settle` wait",
                         "a 1800 wait that wakes `timeout` with every other condition met is not ready without a further wait")
        self.assertNotRegex(ready, r"full wait", "the ready rule still says 'full wait'")

    def test_watch_ready_accepts_unstable_without_ci_pending(self):
        self.assertRegex(watch_step3(), r"(?is)`merge_state` CLEAN, or UNSTABLE when no check fails and `checks\.ci_pending` is 0",
                         "ready does not accept UNSTABLE when no check fails and ci_pending is 0")

    def test_watch_uses_1800_until_otherwise_ready(self):
        self.assertRegex(watch_step1(), r"(?is)CI running, a required reviewer waiting[^.]*1800, not `?pr\.settle",
                         "step 1 does not say a not-yet-ready PR (CI running, a required reviewer waiting) waits 1800, not pr.settle")

    def test_watch_stops_on_settings_problem(self):
        w = self.section("watch")
        start = w[:w.index("--wait")]
        self.assertIn("`settings_problem`", start, "the start of watch never reads `settings_problem`")
        self.assertIn("line N: why", start, "`settings_problem` is not described as `line N: why`")
        self.assertRegex(start, r"(?is)`pr\.settle`.{0,100}too many reviewers|too many reviewers.{0,100}`pr\.settle`",
                         "`settings_problem` does not name `pr.settle` and too many reviewers")
        self.assertRegex(start, r"(?is)`settings_problem`.{0,700}before its first wait", "`settings_problem` does not stop watch before its first wait")
        self.assertRegex(start, r"(?is)ship, finish and cleanup ignore it", "ship, finish and cleanup are not said to ignore `settings_problem`")

    def announce(self):
        step = watch_step3()
        at = step.find("\n   - **Announced review")
        self.assertNotEqual(at, -1, "watch step 3 has no '- **Announced review' bullet")
        end = step.find("\n   - ", at + 1)
        return step[at:end if end != -1 else len(step)]

    def test_watch_announcement_only_waits(self):
        a = self.announce()
        self.assertRegex(a, r"(?is)`reported` only `by: output`", "an output-only report is not the case")
        self.assertRegex(a, r"(?is)`evidence` reads as an announcement", "the judgment is not made from `evidence`")
        self.assertRegex(a, r"(?is)treated as `waiting` until its `timeout` has passed by the snapshot's `now`", "an announcement does not wait until its timeout by `now`")
        self.assertRegex(a, r"(?is)never treats? a `waiting` or `timed_out` reviewer as reported", "watch may treat waiting or timed_out as reported")

    def test_watch_announcement_timeout_reports_and_asks(self):
        a = self.announce()
        self.assertRegex(a, r"(?is)then as `timed_out`", "after the timeout the reviewer is not treated as timed out")
        self.assertIn("`<login> announced a review on <head> but posted no result`", a)
        self.assertRegex(a, r"(?is)a required one[^.]*not ready", "a required announcer that timed out is not 'not ready'")
        self.assertRegex(a, r"(?is)\bask\b", "watch does not ask")
        self.assertRegex(a, r"(?is)no merge request", "a merge request may still be sent")

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

    def after_limit(self):
        fb = self.section("feedback")
        at = fb.index("**After the limit**")
        return fb[at:]

    def lookup_bullet(self):
        text = self.after_limit()
        calls = positions(sub("item-issues"), text)
        self.assertTrue(calls, "After the limit never runs `pr-pair.sh item-issues`")
        start = text.rfind("\n- ", 0, calls[0]) + 1
        end = text.find("\n- ", calls[0])
        return text[start:end if end != -1 else len(text)]

    def test_after_limit_issues_one_lookup_per_repo(self):
        text = self.after_limit()
        b = self.lookup_bullet()
        self.assertEqual(len(positions(sub("item-issues"), text)), 1, "the lookup is written once, not per item")
        self.assertRegex(b, r"\[as\][^`]*pr-pair\.sh item-issues", "the lookup does not run under `[as]`")
        self.assertRegex(b, r"--repo <owner>/<name>", "the lookup is not given the repository")
        self.assertRegex(b, r"--item", "the lookup is not given the items")
        self.assertRegex(b, r"(?i)once per repositor(y|ies)", "the text never says one lookup per repository")
        self.assertRegex(b, r"(?i)repo-local[^.;]*(one call|once)", "repo-local is not one lookup")
        self.assertRegex(b, r"(?i)at most twice|two[^.]*store-backed|store-backed[^.]*two", "store-backed is not at most two lookups")
        self.assertRegex(b, r"(?i)only (that|the) PR's items|items (of|from) (that|its) (repository's )?PR", "each call is not limited to its PR's items")
        self.assertRegex(b, r"(?i)store login", "the store's lookup does not run as the store login")
        self.assertRegex(b, r"(?i)run login", "the code lookup does not run as the run login")
        self.assertRegex(b, r"(?i)before (filing|creating)", "the lookup does not come before filing")
        self.assertRegex(b, r"(?i)search", "the text drops the rationale against the search API")
        self.assertNotIn("--paginate", text, "the skill still pages the issue list by hand")
        create = text.index("gh issue create")
        self.assertLess(text.index("item-issues"), create, "the lookup comes after `gh issue create`")

    def test_after_limit_issues_files_nothing_on_lookup_failure(self):
        b = self.lookup_bullet()
        m = re.search(r"(?i)exit 3.*", b)
        self.assertTrue(m, "the lookup bullet never handles exit 3")
        self.assertRegex(m.group(0), r"(?i)files? nothing|no issue", "exit 3 does not stop filing")
        self.assertRegex(m.group(0), r"(?i)not done", "exit 3 does not report the lookup as not done")
        self.assertRegex(m.group(0), r"(?i)error name|`error`", "the report does not carry the error name")


class RunLogin(unittest.TestCase):
    """The run login: resolved once at a user-started step, handed on, never re-resolved (default-identity-fencing)."""

    def ident(self):
        m = re.search(r"^\*\*Run login\.?\*\*.*$", TEXT, re.M)
        self.assertTrue(m, "Settings and identity has no **Run login** paragraph")
        return m.group(0)

    def test_identity_paragraph_defines_the_run_login(self):
        p = self.ident()
        self.assertRegex(p, r"as\.sh`?\s+--resolve", "the identity paragraph never resolves with `as.sh --resolve`")
        self.assertRegex(p, r"(?i)\bonce\b", "the login is not resolved once")
        self.assertRegex(p, r"(?i)user-started", "only a user-started step may resolve: not said")
        self.assertRegex(p, r"(?i)hand(s|ed)? (it )?(off|on|over)|handed", "the run login is not handed off")
        self.assertRegex(p, r"(?i)never (re-?)?resolves?", "a handed-off step may resolve again")
        self.assertRegex(p, r"bash scripts/as\.sh <run login>", "`[as]` is not defined as as.sh with the run login")

    def test_no_drop_it_or_ambient_fallback(self):
        self.assertNotRegex(TEXT, r"(?i)drop it when", "SKILL.md still drops `[as]` when github.login is empty")
        self.assertNotRegex(TEXT, r"(?i)\bambient\b", "SKILL.md still falls back to the ambient account")
        self.assertNotRegex(TEXT, r"(?i)plain `gh", "SKILL.md still posts with plain `gh`")

    def test_handed_off_step_without_login_stops_and_asks(self):
        p = self.ident()
        self.assertRegex(p, r"(?is)(cannot|can't) find[^.]*\bstops?\b", "the receiving step does not stop")
        self.assertRegex(p, r"(?is)\bstops?\b[^.]*\bask", "the receiving step does not ask the user")
        self.assertRegex(p, r"(?is)before any (GitHub|`gh`) call", "it may call GitHub before asking")

    def test_every_gh_and_git_network_call_carries_as(self):
        # a call has arguments; a bare name in prose (`gh pr edit`, `gh api`) is a mention
        call = re.compile(r"\bgh (pr|issue|run|repo|auth) \w+\s+\S|\bgh api\s+\S|\bgit (push|fetch|pull)\s+\S")
        bad = []
        for m in re.finditer(r"`([^`\n]+)`", TEXT):
            span = m.group(1)
            line = TEXT[TEXT.rfind("\n", 0, m.start()) + 1:TEXT.find("\n", m.end())]
            if not call.search(span) or re.search(r"as\.sh|\[as\]", span):
                continue
            if "gh pr list" in span and NEGATION.search(line):
                continue
            if "gh auth switch" in span and re.search(r"(?i)never", line):
                continue
            if "gh auth token" in span and re.search(r"(?i)never `gh auth switch`", line):
                continue
            bad.append(span[:80])
        self.assertFalse(bad, f"calls without `[as]`: {bad}")

    def test_pr_pair_github_reads_carry_as(self):
        # pass, rounds, pair-state and cleanup-plan read GitHub (and the remote they start in) as the fenced
        # login, and cleanup-plan names that login in the pulls it emits; only the local calls run bare
        local = {"identity", "context", "branch-check"}
        bad = [m.group(0) for m in re.finditer(r"(\[as\] )?bash scripts/pr-pair\.sh ([a-z-]+)", TEXT)
               if not m.group(1) and m.group(2) not in local]
        self.assertFalse(bad, f"pr-pair.sh calls without `[as]`: {bad}")

    def watch_bullets(self):
        return SECTIONS["watch"][1].split("\n   - ")

    def test_run_login_handed_to_watch_feedback_archive(self):
        ship, watch = SECTIONS["ship"][1], SECTIONS["watch"][1]
        step7 = re.search(r"^7\. .*$", ship, re.M).group(0)
        self.assertRegex(step7, r"(?i)run login", "ship's hand-off to watch does not pass the run login")
        feedback = next((b for b in self.watch_bullets() if b.startswith("New feedback")), "")
        self.assertRegex(feedback, r"(?i)run login", "watch -> feedback does not pass the run login")
        archive = next((b for b in self.watch_bullets() if b.startswith("**Archive before merge:**")), "")
        self.assertRegex(archive, r"(?i)run login", "watch -> archive/finish does not pass the run login")
        ship_bullet = next((b for b in self.watch_bullets() if "`ship` → an expected PR" in b), "")
        self.assertRegex(ship_bullet, r"(?i)run login", "watch -> ship does not pass the run login")
        w1 = watch[watch.index("1. Wait in the background"):watch.index("\n2. On wake")]
        self.assertRegex(w1, r"(?i)run login", "the --wait watcher is not given the run login")
        self.assertRegex(w1, r"\[as\][^`]*--wait", "the --wait command line does not run under `[as]`")
        fb9 = re.search(r"^9\. .*$", SECTIONS["feedback"][1], re.M).group(0)
        self.assertRegex(fb9, r"(?i)run login", "feedback's ship hand-off does not pass the run login")

    def test_review_request_poster_falls_back_to_run_login_fenced(self):
        m = re.search(r"^\*\*Review requests\*\*.*$", TEXT, re.M)
        self.assertTrue(m, "no **Review requests** paragraph")
        p = m.group(0)
        self.assertRegex(p, r"request_as[^.]*review_request\.login[^.]*run login", "the poster chain does not end at the run login")
        self.assertRegex(p, r"(?i)fenced|as\.sh", "the request is not posted fenced")
        self.assertRegex(p, r"exits? 3", "a poster without a credential does not stop on exit 3")
        self.assertRegex(p, r"(?i)never[^.]*(another|other|active) account", "the poster may fall back to another account")
        ship6 = re.search(r"^6\. .*$", SECTIONS["ship"][1], re.M).group(0)
        self.assertRegex(ship6, r"as\.sh <poster>", "ship step 6 does not post through as.sh with the poster")
        self.assertNotRegex(ship6, r"(?i)plain|ambient", "ship step 6 still posts plain for the ambient account")

    def test_cleanup_pulls_are_fenced_and_stop(self):
        local = re.search(r"^- Repo-local: .*$", SECTIONS["cleanup after merge"][1], re.M).group(0)
        self.assertRegex(local, r"(?is)non-zero[^.;]*stop|stop[^.;]*non-zero", "a failed pull does not stop")
        self.assertRegex(local, r"(?i)delete no branch", "a failed pull may still delete a branch")


class AgentMerge(unittest.TestCase):
    """pr.merge: agent lets watch merge a ready PR at its ready head and clean up (add-agent-merge, ADR 0009)."""

    def watch(self):
        return SECTIONS["watch"][1]

    def step3(self):
        w = self.watch()
        return w[w.index("\n3. Ready, per PR"):w.index("\n4. Stop and report")]

    def bullet(self, start):
        step = self.step3()
        at = step.find("\n   - " + start)
        self.assertNotEqual(at, -1, f"watch step 3 has no '- {start}' bullet")
        end = step.find("\n   - ", at + 1)
        return step[at:end if end != -1 else len(step)]

    def merge(self):
        return self.bullet("**Merge:**")

    def archive(self):
        return self.bullet("**Archive before merge:**")

    def cleanup(self):
        return SECTIONS["cleanup after merge"][1]

    def never(self):
        return SECTIONS["never"][1]

    def remote_bullet(self):
        c = self.cleanup()
        at = c.find("delete-remote")
        self.assertNotEqual(at, -1, "Cleanup after merge never runs `pr-pair.sh delete-remote`")
        start = c.rfind("\n- ", 0, at) + 1
        end = c.find("\n- ", at)
        return c[start:end if end != -1 else len(c)]

    def test_settings_block_lists_the_merge_keys(self):
        block = TEXT[TEXT.index("```yaml"):TEXT.index("```", TEXT.index("```yaml") + 8)]
        for key in ("merge:", "merge_method:", "delete_branch:"):
            self.assertIn(key, block, f"the settings block has no `{key}`")
        self.assertRegex(block, r"merge:\s*user", "pr.merge does not default to user in the settings block")

    def test_watch_merges_only_with_pr_merge_agent(self):
        w = self.watch()
        ctx = positions(sub("context"), w)
        self.assertTrue(ctx, "watch never reads `pr-pair.sh context`")
        self.assertLess(ctx[0], w.index("--wait"), "watch reads `context` after it starts waiting")
        start = w[:w.index("--wait")]
        for token in ("merge_method", "delete_branch", "bad_setting", "merge_note"):
            self.assertIn(token, start, f"the start of watch never reads `{token}`")
        self.assertRegex(start, r"(?is)bad_setting[^.]*exit 2|exit 2[^.]*bad_setting", "`bad_setting` is not tied to exit 2")
        self.assertRegex(start, r"(?is)bad_setting.{0,200}before any wait", "`bad_setting` does not stop before any wait")
        self.assertRegex(start, r"(?is)merge_note.{0,100}report|report.{0,100}merge_note", "a `merge_note` is not reported")
        m = self.merge()
        self.assertRegex(m, r"`merge` is `agent`", "the merge bullet does not require `merge` to be `agent`")
        self.assertRegex(m, r"`finish` is `pr`", "the merge bullet does not require `finish: pr`")
        self.assertRegex(m, r"merge_ready", "the merge bullet does not read `merge_ready`")
        self.assertRegex(m, r"agent merge needs a required reviewer in pr\.reviewers", "a missing required reviewer is not reported")
        self.assertLess(m.index("merge_ready"), m.index("pr-pair.sh merge"), "the merge runs before `merge_ready` is checked")
        step = self.step3()
        self.assertLess(step.index("**Merge:**"), step.index("\n   - Otherwise"), "the user-mode fallback comes before the merge rule")
        other = step[step.index("\n   - Otherwise"):]
        self.assertRegex(other, r"report ready and stop; the user merges", "user mode lost 'report ready and stop; the user merges'")

    def test_agent_mode_archives_without_asking(self):
        a = self.archive()
        self.assertRegex(a, r"(?is)`merge` is `agent`.{0,200}without asking", "agent mode does not archive without asking")
        self.assertRegex(a, r"Ready\. Archive <change-name> on this branch now\?", "user mode lost the archive question")
        self.assertRegex(a, r"(?is)`merge` is `user`.{0,200}ask", "user mode no longer asks before archiving")

    def test_agent_mode_archive_failure_stops_no_merge(self):
        a = self.archive()
        self.assertRegex(a, r"(?is)\bfails?\b[^.]*\bstop\b[^.]*\bno merge", "an archive failure does not stop with no merge request")
        self.assertRegex(a, r"(?is)archive workflow[^.]*\bor its push\b[^.]*\bfails?\b", "the failure covers neither the archive workflow nor its push")
        self.assertRegex(a, r"(?i)report[^.]*error", "the archive error is not reported")
        self.assertIn("archive head needs a fresh approval", a)
        self.assertRegex(a, r"(?is)agent mode[^.]*question", "the fresh-approval question is not kept in agent mode")

    def test_reviewerless_archive_head_merged_only_if_unchanged(self):
        m = self.merge()
        self.assertRegex(m, r"(?is)head judged under the archive carry-over[^.]*merged only when the ready head is the archive head `archive-only` judged",
                         "a carry-over head is not merged only when it is the archive head `archive-only` judged")
        self.assertNotRegex(m, r"(?i)watched without reviewers", "the merge step still says 'watched without reviewers'")
        self.assertRegex(m, r"(?is)archive-only --base <ready head[^`]*> --head <current head>", "another head is not sent back through `archive-only`")
        self.assertRegex(m, r"(?is)archive_only: true", "the re-run's `archive_only` result is not read")
        self.assertRegex(m, r"(?is)returns? to watching with (the )?reviewers", "another head does not go back to watching with reviewers")

    def test_merge_command_and_outcomes(self):
        m = self.merge()
        cmd = re.search(r"`\[as\] bash scripts/pr-pair\.sh merge --repo <owner>/<name> --pr <n> --method <merge_method> --head <ready head>`", m)
        self.assertTrue(cmd, "the merge command is not `[as] bash scripts/pr-pair.sh merge --repo <owner>/<name> --pr <n> --method <merge_method> --head <ready head>`")
        tail = m[cmd.end():]
        self.assertRegex(tail, r"(?is)`merged`[^;.]*Cleanup after merge", "`merged` does not lead to Cleanup after merge")
        self.assertRegex(tail, r"(?is)`reason`[^;.]*`head_changed`[^;.]*watch(es|ing)? again[^;.]*repo-local",
                         "`reason` `head_changed` (the script's status is `refused`) does not go back to watching (repo-local)")
        self.assertRegex(tail, r"(?is)any other refusal[^;.]*stop[^;.]*GitHub's message", "another refusal does not stop with GitHub's message")
        self.assertRegex(tail, r"(?is)exit 3[^;.]*unknown[^;.]*no deletion", "exit 3 is not unknown with no deletion")

    def test_archived_means_archive_dir_on_the_branch(self):
        m = self.merge()
        self.assertRegex(m, r"(?is)archived[^.]*`<P>/changes/archive/<archived-name>/`[^.]*branch",
                         "the merge step does not define archived as the archive directory on the branch")
        self.assertRegex(m, r"(?is)`<P>/changes/<change-name>/`[^.]*(gone|no longer|does not exist)",
                         "the merge step does not require the change directory to be gone")

    def test_merge_ready_checked_for_every_expected_pr_first(self):
        m = self.merge()
        self.assertRegex(m, r"(?is)`merge_ready`[^.]*every expected PR[^.]*before (the first|any) merge request",
                         "`merge_ready` is not checked for every expected PR before the first merge request")

    def test_store_pair_merges_store_then_code_on_pair_ready(self):
        m = self.merge()
        at = m.find("Store-backed")
        self.assertNotEqual(at, -1, "the merge bullet has no store-backed rule")
        rule = m[at:]
        self.assertRegex(rule, r"`pair-state` `ready`", "a store-backed merge is not tied to `pair-state` `ready`")
        self.assertRegex(rule, r"(?is)store PR first, then the code PR", "the pair does not merge store first, then code")
        self.assertRegex(rule, r"(?is)its own login and ready head", "each merge does not use its own repo's login and ready head")

    def test_store_split_reports_planning_merged_code_pending(self):
        m = self.merge()
        rule = m[m.find("Store-backed"):]
        self.assertRegex(rule, r"(?is)non-`merged` code result[^.]*`planning merged, code pending`", "a non-`merged` code result does not report `planning merged, code pending`")
        self.assertRegex(rule, r"(?is)cleans? up the store only", "the split does not clean up the store only")
        self.assertRegex(rule, r"(?is)GitHub's message", "the split report omits GitHub's message")
        self.assertRegex(rule, r"(?is)user merges the code PR", "the split does not hand the code PR to the user")
        self.assertRegex(self.cleanup(), r"(?is)store only", "Cleanup after merge has no store-only path for a split")

    def test_agent_merge_branch_kinds(self):
        m = self.merge()
        for kind in ("`<prefix>/<change-name>`", "`docs/project-baseline`", "`docs/close-*`"):
            self.assertIn(kind, m, f"the merge bullet does not name {kind}")
        self.assertRegex(m, r"(?is)any other branch[^.]*report[^.]*ready", "other branches are not reported ready and left unmerged")
        self.assertRegex(m, r"(?is)nothing to archive", "a roadmap branch is not merged with nothing to archive first")

    def test_agent_cleanup_pull_failure_deletes_nothing(self):
        b = self.remote_bullet()
        self.assertRegex(b, r"(?is)after the pull succeeded", "remote deletion is not tied to a successful pull")
        self.assertRegex(b, r"(?is)failed pull deletes nothing", "a failed pull may still delete a branch")

    def test_delete_remote_only_in_agent_mode(self):
        b = self.remote_bullet()
        self.assertRegex(b, r"`merge` is `agent`", "remote deletion is not tied to `merge: agent`")
        self.assertRegex(b, r"`delete_branch`", "remote deletion ignores `delete_branch`")
        self.assertRegex(b, r"(?is)\bwhoever merged", "remote deletion is limited to the agent's own merge")
        self.assertRegex(b, r"\[as\] bash scripts/pr-pair\.sh delete-remote --repo <owner>/<name> --branch <branch> --head <merged head", "the delete-remote call is wrong or not fenced")
        self.assertRegex(b, r"(?is)`merge` is `user`[^.]*never delete", "user mode may delete a remote branch")
        for status in ("deleted", "gone", "moved", "based_on", "kept"):
            self.assertIn(f"`{status}`", b, f"delete-remote's `{status}` is not handled")
        self.assertRegex(b, r"(?is)exit 3[^.;]*keep", "an unknown remote branch state may be deleted")
        for name, (_, body) in SECTIONS.items():
            if name != "cleanup after merge":
                self.assertFalse(positions(sub("delete-remote"), body), f"delete-remote is also run in '{name}'")

    def test_cleanup_offers_one_roadmap_mode_after_an_agent_merge(self):
        self.assertRegex(self.cleanup(), r"(?is)specwright-roadmap[^.]*\*\*close\*\*[^.]*\*\*next\*\*", "no roadmap close/next offer after an agent merge")
        self.assertRegex(self.cleanup(), r"(?is)next step\*\*.{0,300}?\bask the user as a question\b", "the roadmap offer is not phrased as a question to the user")

    def test_never_admin_auto_queue_or_other_method(self):
        never = self.never()
        self.assertRegex(never, r"(?i)\bmerge\b", "the Never list lost 'merge'")
        self.assertRegex(never, r"(?is)except[^.]*agent merge", "the merge ban has no exception for the agent merge path")
        for term, pat in (("admin rights", r"admin rights"), ("auto-merge", r"auto-merge"), ("a merge queue", r"merge queue"),
                          ("another method", r"another method"), ("review dismissal", r"dismiss")):
            self.assertRegex(never, "(?i)" + pat, f"the Never list does not name {term}")

    def test_merge_report_repeats_share_by_hand_reminder(self):
        m = self.merge()
        self.assertRegex(m, r"(?is)merge report[^.]*share[^.]*by hand", "the merge report omits the share-by-hand reminder")
        self.assertRegex(m, r"(?is)only the code PR is expected", "the reminder is not tied to a store shared by hand")

    # trust-main-merge-policy: main's policy decides the archive and the merge (ADR 0020)

    def policy_read(self):
        w = self.watch()
        return w[:w.index("\nLoop until")]

    def sub_bullet(self, start):
        m = self.merge()
        at = m.find("\n     - " + start)
        self.assertNotEqual(at, -1, f"the merge bullet has no '- {start}' sub-bullet")
        end = m.find("\n     - ", at + 1)
        return m[at:end if end != -1 else len(m)]

    def test_context_merge_is_only_the_start_of_watch_read(self):
        p = self.policy_read()
        self.assertRegex(p, r"(?is)start-of-watch read[^.]*only|only[^.]*start-of-watch read", "`context` is not limited to the start-of-watch read")
        self.assertRegex(p, r"(?is)never decides an archive or a merge", "`context`'s merge may still decide the archive or the merge")
        self.assertRegex(p, r"(?is)\[as\] bash scripts/pr-pair\.sh policy --repo <owner>/<name> --head <ready head> --snapshot code=<file>",
                         "watch has no fenced `policy` call")
        self.assertRegex(p, r"(?is)default branch[^.]*never[^.]*work tree", "the policy is not read from the default branch")
        self.assertRegex(p, r"(?is)for every change or roadmap branch[^.]*whatever `context`'s `merge` says", "the read is skipped when `context` says `user`")

    def test_merge_decided_by_policy_not_context(self):
        m = self.merge()
        self.assertRegex(m, r"(?is)`policy`[^.]*again[^.]*version check|version check[^.]*then `policy`", "`policy` does not run again after the Version check")
        self.assertLess(m.index("**Version check**"), m.index("`policy`"), "`policy` runs before the Version check")
        self.assertRegex(m, r"(?is)main's `merge` is `agent`[^.]*never[^.]*`context`", "the merge is not decided by main's `merge` from `policy`")
        self.assertRegex(m, r"(?is)`merge_ready`[^.]*from `policy`[^.]*every expected PR[^.]*before (the first|any) merge request",
                         "`merge_ready` is not taken from `policy` for every expected PR")
        self.assertRegex(m, r"(?is)`reported\.main`[^.]*`ok`[^.]*every expected PR", "`reported.main` is not required ok for every expected PR")
        self.assertRegex(m, r"(?is)empty `drift`|no `drift`", "the no-drift condition is missing")
        self.assertLess(m.index("`policy`"), m.index("pr-pair.sh merge"), "the merge runs before `policy` is read")

    def test_unknown_policy_merges_nothing(self):
        o = self.sub_bullet("**Policy outcome.**")
        self.assertRegex(o, r"(?is)exit 3[^.]*`merge policy unknown: <reason>`", "exit 3 does not report `merge policy unknown`")
        self.assertRegex(o, r"(?is)merge nothing", "an unknown policy may still merge")
        self.assertRegex(o, r"(?is)next time watch reaches this step[^.]*again", "an unknown policy is not read again")
        self.assertRegex(o, r"(?is)`bad_setting`[^.]*stop", "`bad_setting` from `policy` does not stop")

    def test_drift_yes_merges_with_head_method(self):
        d = self.sub_bullet("**Drift**")
        self.assertRegex(d, r"(?is)list each `\{key, main, head\}`", "the drift is not listed")
        self.assertIn("`Merge PR #<n> at <head> with the head's policy (<method>)?`", d)
        self.assertRegex(d, r"(?is)`agent` with `reported\.head` `ok`[^.]*ask", "the question is not tied to a head that is `agent` and reported ok")
        self.assertRegex(d, r"(?is)On yes, merge with the head's `pr\.merge_method` at that head once `reported\.head` is `ok`",
                         "a yes does not merge with the head's method at that head")

    def test_drift_rules_mismatch_alone_still_reaches_the_question(self):
        # PR #174 review: a reviewer-setting drift always makes the digests differ, so a head judged under main's rules
        # must still reach the question, and the yes waits again under the head's rules before merging.
        d = self.sub_bullet("**Drift**")
        self.assertRegex(d, r"(?is)not `ok` only through `rules_mismatch` \(no `missing`, no `head_mismatch`", "rules_mismatch alone blocks the question")
        self.assertRegex(d, r"(?is)on `rules_mismatch` the \*\*Reviewer check\*\* first waits again with the head's `reviewer_config`",
                         "a yes on a rules_mismatch merges without waiting under the head's rules")

    def test_pair_state_takes_the_archive_carry_over(self):
        # PR #174 review: a store archive head keeps --reviewer-config, so its request-driven reviewer is waiting;
        # pair-state must be told about the carry-over or the pair is never ready.
        w = SECTIONS["watch"][1]
        self.assertRegex(w, r"(?is)pr-pair\.sh pair-state [^\n]*`--carry-over <side>` for a side whose archive head is under the carry-over",
                         "watch does not pass --carry-over to pair-state for an archive head under the carry-over")

    def test_drift_with_main_user_still_reaches_the_question(self):
        # "Branch turns on agent merge": main `user`, head `agent` -> ask, not stop as for `user`.
        o = self.sub_bullet("**Policy outcome.**")
        self.assertRegex(o, r"(?is)with `drift` go by \*\*Drift\*\*[^;]*main's `merge` is `user`", "drift with main `user` stops before the question")
        self.assertRegex(o, r"(?is)with no `drift` main's `merge` must be `agent`", "the main-`agent` gate is not limited to no drift")
        self.assertRegex(self.merge(), r"(?is)main's `merge` is `agent` \(from `policy`[^)]*\) or the user confirmed a drift", "the merge gate does not admit a confirmed drift")

    def test_drift_no_reports_ready_without_merge(self):
        d = self.sub_bullet("**Drift**")
        self.assertRegex(d, r"(?is)on no report ready and send no merge request", "a no still merges or does not report ready")

    def test_drift_without_head_agent_asks_nothing(self):
        d = self.sub_bullet("**Drift**")
        self.assertRegex(d, r"(?is)not `agent`[^.]*list the drift, report ready, ask nothing and merge nothing", "a head that is not `agent` is not left unmerged without a question")

    def test_drift_head_agent_but_reviewers_missing_merges_nothing(self):
        d = self.sub_bullet("**Drift**")
        self.assertRegex(d, r"(?is)`agent` but `reported\.head` not `ok`[^.]*list the drift and the `missing` reviewers[^.]*merge nothing",
                         "a head set short of reviewers is not reported with its missing reviewers")
        # Pre-ship round 2: no wait may restart with the head's set before a yes, so this case must end the pass.
        self.assertRegex(d, r"(?is)`agent` but `reported\.head` not `ok`[^.]*report ready and stop",
                         "a head set short of reviewers does not report ready and stop")

    def test_drift_answer_covers_one_head(self):
        d = self.sub_bullet("**Drift**")
        self.assertRegex(d, r"(?is)a yes covers that head only[^.]*new head[^.]*`policy` again[^.]*ask(ed)? again", "a yes is not limited to one head")

    def test_unsatisfied_reviewer_set_restarts_the_wait_with_its_reviewer_config(self):
        r = self.sub_bullet("**Reviewer check.**")
        self.assertIn("`rules_mismatch`", r, "the Reviewer check never names `rules_mismatch`")
        self.assertNotIn("reviewer_args", r)
        self.assertRegex(r, r"(?is)main's \(no drift\) or the head's \(after a yes\), never the head's before a yes", "the authorizing set is not main's or the head's after a yes")
        self.assertRegex(r, r"(?is)not `ok`[^.]*merge nothing", "a set that is not ok may still merge")
        self.assertRegex(r, r"(?is)restart that PR's wait with that set's `reviewer_config` \(`--reviewer-config`\)", "the wait is not restarted with the set's `reviewer_config`")
        self.assertRegex(r, r"(?is)post the requests that set names[^.]*re-request review", "the set's requests are not posted as on a re-request")

    def test_store_pair_reads_policy_once_with_both_snapshots(self):
        p = self.policy_read()
        self.assertRegex(p, r"(?is)one call[^.]*`--store --snapshot code=<file> --snapshot store=<file> --reviewed-head store=<store ready head>`",
                         "the store pair is not read in one `policy --store` call with both snapshots")
        self.assertRegex(p, r"(?is)`merge_ready\.store` and `reported\.<side>\.store` replace `context`'s", "the store PR's readiness does not come from `policy`")
        self.assertRegex(p, r"(?is)drift question covers the pair", "a drift question does not cover the pair")

    def test_archive_without_asking_needs_policy_from_main(self):
        a = self.archive()
        self.assertRegex(a, r"(?is)`policy`[^.]*ready head[^.]*snapshot", "the archive decision does not run `policy` at the ready head with its snapshot")
        self.assertRegex(a, r"(?is)main's `merge` is `agent`[^.]*no `drift`[^.]*`reported\.main` `ok`[^.]*every expected PR[^.]*archive without asking",
                         "agent archive without asking is not tied to main's policy, no drift and `reported.main` ok")
        self.assertRegex(a, r"(?is)otherwise.{0,300}Ready\. Archive <change-name> on this branch now\?", "anything else does not ask")
        self.assertRegex(a, r"(?is)exit 3[^.]*ask", "an unknown policy does not ask before archiving")
        self.assertLess(a.index("`policy`"), a.index("without asking"), "the archive decision comes before the policy read")

    def test_archive_decision_rules_mismatch_waits_without_asking(self):
        a = self.archive()
        self.assertRegex(a, r"(?is)`rules_mismatch`[^.]*archive nothing, ask nothing and wait on the ready head with main's reviewer config",
                         "a rules_mismatch at the archive decision does not archive nothing, ask nothing and wait with main's config")
        self.assertRegex(a, r"(?is)`rules_mismatch`.{0,400}`reviewer_config\.main", "the wait is not restarted with main's `reviewer_config`")
        self.assertRegex(a, r"(?is)main's `merge` is `agent` with no `drift` and `policy` reports `rules_mismatch`",
                         "the rules_mismatch wait is not limited to agent mode with no drift (user mode would wait needlessly)")
        self.assertRegex(a, r"(?is)not `ok` for another reason", "the generic 'not ok' case still asks even for a rules_mismatch")

    def test_policy_read_gives_reviewer_config_not_reviewer_args(self):
        p = self.policy_read()
        self.assertNotIn("reviewer_args", p, "the policy read still names `reviewer_args`")
        self.assertIn("`reviewer_config.{main,head}.{code[,store]}`", p, "the policy read does not name its `reviewer_config`")
        self.assertIn("`rules_mismatch`", p, "the policy read never names `rules_mismatch`")
        self.assertRegex(p, r"(?is)`rules_mismatch`[^.]*other rules", "`rules_mismatch` is not explained")

    def test_snapshot_commands_take_reviewer_config(self):
        self.assertNotRegex(TEXT, r"--reviewer\b(?!-)", "SKILL.md still names the removed `--reviewer` argument")
        self.assertNotIn("<reviewers>", TEXT, "SKILL.md still uses the `<reviewers>` placeholder")
        calls = [m.group(1) for m in re.finditer(r"`([^`]*pr-snapshot\.sh <pr>[^`]*)`", TEXT) if "--full" not in m.group(1)]
        self.assertGreaterEqual(len(calls), 2, "found too few snapshot commands")
        for c in calls:
            self.assertIn("--reviewer-config", c, f"a snapshot command lacks `--reviewer-config`: {c[:90]!r}")
        fb1 = re.search(r"^1\. \*\*Snapshots\.\*\*.*$", SECTIONS["feedback"][1], re.M).group(0)
        self.assertIn("--reviewer-config <config file>", fb1, "feedback step 1 does not pass its repo's `--reviewer-config`")

    def test_reviewers_paragraph_is_generic(self):
        m = re.search(r"^\*\*Reviewers\.\*\*.*$", TEXT, re.M)
        self.assertTrue(m, "no **Reviewers** paragraph")
        p = m.group(0)
        for key in ("report", "sha_pattern", "check", "marker", "ignore", "by", "evidence", "now", "reviewer_config", "pr.settle"):
            self.assertIn(f"`{key}`", p, f"the Reviewers paragraph never names `{key}`")
        self.assertRegex(p, r"(?i)review on the head commit", "generic detection by a review on the head commit is not described")
        self.assertRegex(TEXT, r"(?i)single quotes", "patterns in YAML single quotes are not mentioned")
        self.assertNotRegex(TEXT, r"(?i)\b(codex|kody|mira)\b", "SKILL.md still names a review bot")

    def test_settings_block_has_report_example_and_settle(self):
        block = TEXT[TEXT.index("```yaml"):TEXT.index("```", TEXT.index("```yaml") + 8)]
        self.assertRegex(block, r"(?m)^\s+report:", "the settings block has no `report:` example")
        self.assertRegex(block, r"(?m)^\s+settle:", "the settings block has no `settle:`")
        self.assertRegex(block, r"sha_pattern: '", "the example pattern is not in YAML single quotes")

    def test_archive_only_carry_over_checks_the_snapshot_against_the_ready_head(self):
        a = self.archive()
        self.assertRegex(a, r"(?is)--reviewed-head <repo>=<ready head before the archive>[^.]*(store in a store-backed change|store-backed)",
                         "the carry-over does not pass the pre-archive ready head for the repository that got the archive commit")
        self.assertRegex(self.merge(), r"(?is)--reviewed-head <repo>=<ready head before the archive>", "the merge step does not pass --reviewed-head on the carry-over")

    def test_archive_keeps_the_pre_archive_snapshot_for_the_carry_over(self):
        # Pre-ship round 3 F2: step 1 keeps only the latest snapshot, so the ready head's must be saved before archiving.
        a = self.archive()
        self.assertRegex(a, r"(?is)before (it )?archiv\w*[^.]*copy[^.]*latest snapshot[^.]*own file",
                         "the ready head's snapshot is not kept before the archive replaces it")
        self.assertRegex(a, r"(?is)--reviewed-head <repo>=<ready head before the archive>[^.]*that saved snapshot",
                         "the carry-over read does not pass the saved pre-archive snapshot")

    def test_policy_store_flag_only_with_a_store_pr(self):
        # Pre-ship round 3 F1: no store PR (shared by hand) or no code PR (store-only) must not end in a usage error.
        p = self.policy_read()
        self.assertRegex(p, r"(?is)`--store`[^.]*only when a store PR is expected", "`--store` is not limited to an expected store PR")
        self.assertRegex(p, r"(?is)shared by hand[^.]*without `--store`", "a store shared by hand is not read without `--store`")
        self.assertRegex(p, r"(?is)no code PR[^.]*report ready[^.]*merge nothing", "a store-only change has no defined policy outcome")


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
            self.assertRegex(b, r"delete: true", f"the {name} bullet does not delete only on `delete: true`")
            self.assertRegex(b, r"(?i)otherwise[^.]*keep[^.]*branch|keep[^.]*branch[^.]*otherwise", f"the {name} bullet does not keep the branch otherwise")
            self.assertRegex(b, r"`lacking`", f"the {name} bullet does not report the `lacking` commits")
            self.assertRegex(b, r"`head_unknown`", f"the {name} bullet does not report `head_unknown`")
        local = self.bullets()["repo-local"]
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
        self.assertRegex(rule, r"(?is)archive_only: true.{0,600}`--reviewer-config`", "the archive head is not watched with `--reviewer-config`")
        self.assertRegex(rule, r"(?is)archive_only: true.{0,900}carry-over", "the archive head is not said to be under the carry-over")
        self.assertRegex(rule, r"(?is)does not wait for the carried-over reviewers, only CI, mergeability and new feedback",
                         "readiness still waits for the carried-over reviewers")
        self.assertNotRegex(rule, r"--reviewer\b(?!-)", "the archive rule still names `--reviewer` arguments")
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


class ArchiveCarryOverReady(unittest.TestCase):
    """An archive head under the carry-over is judged ready without a further quiet window (D7)."""

    def bullet(self):
        return step3_bullet("**Archive head under the carry-over")

    def test_archive_head_ready_after_settle_unstable(self):
        b = self.bullet()
        self.assertRegex(b, r"(?is)`now` is at least `pr\.settle` after the head's cutoff \(`head_cutoff\.at`\)", "the settle test is not `now` against `head_cutoff.at`")
        self.assertRegex(b, r"(?is)mergeable.{0,40}CLEAN or UNSTABLE.{0,80}`checks\.ci_pending` 0.{0,80}no check fails.{0,80}no feedback is new",
                         "the ready conditions are incomplete")
        self.assertRegex(b, r"(?is)ready and start no further wait", "a ready archive head starts a further wait")
        self.assertRegex(b, r"(?is)no further quiet window", "the archive head still has a quiet window")

    def test_archive_head_waits_rest_of_settle_before_judging(self):
        self.assertRegex(self.bullet(), r"(?is)before `now` reaches[^`]*wait `--until attention --timeout <rest of pr\.settle since the push>`, then judge",
                         "the wait for the rest of pr.settle is missing")

    def test_archive_head_ready_on_ci_pending_zero_wake(self):
        b = self.bullet()
        self.assertRegex(b, r"(?is)CI is still pending after `pr\.settle`[^.]*wait \(`--timeout 1800`\)", "pending CI after pr.settle does not wait 1800")
        self.assertRegex(b, r"(?is)ready on the wake where `ci_pending` reached 0 with no failure and no new feedback", "the ci_pending 0 wake is not ready")
        self.assertRegex(b, r"(?is)judging each wake, `timeout` included, by (this|the same) rule", "each wake is not judged by the same rule")

    def test_archive_head_feedback_runs_feedback(self):
        self.assertRegex(self.bullet(), r"(?is)new feedback[^.]*not ready[^.]*run \*\*feedback\*\* as for any head", "feedback on the archive head does not run feedback")

    def test_archive_head_ci_failure_handled_as_any_head(self):
        self.assertRegex(self.bullet(), r"(?is)failing check[^.]*not ready[^.]*as for any head", "a CI failure on the archive head is not handled as for any head")


class ShipArchiveOnly(unittest.TestCase):
    """Ship skips pr.validate for an archive-only push of a handed ready head (D8, change-finish)."""

    def s4a(self):
        ship = SECTIONS["ship"][1]
        a, b = re.search(r"^4a\. ", ship, re.M), re.search(r"^4b\. ", ship, re.M)
        return ship[a.start():b.start()]

    def test_ship_skips_validate_for_archive_only_push(self):
        a = self.s4a()
        self.assertIn("ready head: <repo>=<sha>", a, "ship never reads the handed `ready head: <repo>=<sha>`")
        run = re.search(r"review-run\.sh[`\"']?\s+archive-only", a)
        self.assertTrue(run, "ship never runs `review-run.sh archive-only`")
        self.assertRegex(a, r"(?is)archive-only.{0,300}planning repo", "archive-only is not run in the planning repo")
        self.assertLess(run.start(), positions(PUSH, a)[0], "archive-only runs after the push")
        self.assertRegex(a, r"(?is)`archive_only: true`.{0,40}skip `pr\.validate` for the planning repo and for a code repo[^.]*still (at|its)[^.]*ready head",
                         "archive_only true does not skip pr.validate for the planning repo and an unchanged code repo")
        self.assertRegex(a, r"(?is)validate was skipped for an archive-only push", "the skip is not reported")

    def test_ship_store_archive_runs_store_validate_only(self):
        a = self.s4a()
        self.assertRegex(a, r"(?is)`planning_store\.validate` still runs[^.]*store", "planning_store.validate does not still run in the store")
        self.assertRegex(a, r"(?is)`planning_store\.validate` still runs.{0,120}failure stops the push", "a failing store validate does not stop the push")
        self.assertRegex(a, r"(?is)store-backed[^.]*both repos", "a store-backed change does not carry both ready heads")

    def test_ship_runs_validate_when_not_archive_only(self):
        self.assertRegex(self.s4a(), r"(?is)`archive_only: false`.{0,200}`pr\.validate` runs", "archive_only false does not run pr.validate")

    def test_ship_runs_validate_without_ready_head(self):
        self.assertRegex(self.s4a(), r"(?is)no ready head.{0,200}`pr\.validate` runs", "no ready head does not run pr.validate")

    def test_ship_runs_validate_and_names_archive_only_error(self):
        a = self.s4a()
        self.assertRegex(a, r"(?is)exit 3.{0,200}`pr\.validate` runs", "an archive-only error does not run pr.validate")
        self.assertRegex(a, r"(?is)names? the `archive-only` error", "the report does not name the archive-only error")

    def test_watch_and_finish_hand_the_ready_head_on(self):
        archive = step3_bullet("**Archive before merge:**")
        self.assertRegex(archive, r"(?is)`ready head: <repo>=<sha>`[^.]*both repos when store-backed", "watch does not hand `ready head: <repo>=<sha>` to finish")
        fin = FINISH.read_text(encoding="utf-8")
        pr = fin[fin.index("\n## pr\n"):fin.index("\n**Release.**")]
        self.assertIn("ready head: <repo>=<sha>", pr, "finish never passes `ready head: <repo>=<sha>` on to ship")
        self.assertRegex(pr, r"(?is)both repos when store-backed", "finish does not hand both repos' ready heads when store-backed")
        self.assertRegex(pr, r"(?is)ship.{0,300}ready head", "finish does not hand the ready head to ship")


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
