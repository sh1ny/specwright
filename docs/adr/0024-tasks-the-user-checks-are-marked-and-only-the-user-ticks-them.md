# 0024. Tasks the user checks are marked in tasks.md and only the user ticks them

- Status: accepted
- Date: 2026-11-03
- Adds to: 0016 (a new trailer counts as task evidence, for user tasks only), 0009 and 0020 (the agent merge gains a stop; neither is relaxed)

## Context

Some checks only a person can make: a playtest verdict, a UX sign-off, an owner agreeing with what a real system shows. `tasks.md` had no way to say a task is the user's, so an agent either ticked it on its own judgement or the check stayed outside the change and nothing waited for it. Packs (ADR 0023), the gamedev pack first, need such tasks in core, and projects already tag milestone exit criteria `[user]` by hand.

`tasks.md` is read by OpenSpec (done or undone) and by `task-cover.sh` (ADR 0016), which reads nothing after the task id. A commit stages `tasks.md` as a whole file, and partial staging is not available on every backend `vcs.sh` drives (ADR 0018).

## Decision

- **The kind is marked right after the id (D1).** `- [ ] X.Y [user] <text>` is a user task and `- [ ] X.Y [evidence] <text> → evidence/<file>` an evidence task: the marker is the first token after the id, lowercase and exact. Every other task is an agent task. A marker anywhere else, or in another case, changes nothing. A separate section was rejected because group membership, coverage and order all key on the id.
- **Only the user writes the tick (D2).** An agent never ticks, implements or dispatches a user task to any implementer or worker; apply skips it and lists it as waiting on the user. A user reporting a result in chat is asked to tick the box in `tasks.md` themselves. Ticking on the user's quoted words was rejected: a quoted line is easy for an agent to produce on its own.
- **The user's tick rides the next `tasks.md` commit (D3).** A ticked user task is covered by a `Specwright-User-Task: X.Y` trailer, which counts as evidence for user tasks only and is never cross-group. Every commit that stages `tasks.md` carries one for each user tick it brings in that no earlier commit covers. With no agent work pending the agent commits `tasks.md` alone as `<type>(<change>): record user checks <ids>`. A group commit does not wait for its group's user tasks, and a user tick never makes a group pending.
- **`task-cover.sh` is the one reader of kinds.** It reports `kind`, `waiting_on_user`, `user_uncommitted` and `evidence_missing`, and with `--rev <sha>` reads `tasks.md` as committed at that revision. An evidence task is ticked only when its one `evidence/` file under the change folder exists, is not empty and is committed with it; the script reads that file from the index of the repository holding `tasks.md` (the planning repo) or the revision's tree, never through the working tree.
- **The gates sit next to the DEFERRED gates (D6).** Archive and finish stop on an unticked user task and name it; verify reports it as waiting on the user, never as done. Before it archives and before every merge request, watch reads the change's `tasks.md` (active, else archived) at the ready head of the planning repo, never the working tree: an unticked user task reports the PR `ready, waiting on the user` and stops both, and an unreadable file is an unknown check that merges nothing.

## Consequences

Packs and projects can carry person-judged checks inside a change, and an agent cannot archive or merge the change until the user has made them. The task line format and the `Specwright-User-Task` trailer are parsed by later runs, so changing either is a workflow change (minor version).

Git cannot tell the user's edit from the agent's in a working tree, so "only the user ticks" rests on the instructions and on review: the tick lands in an ordinary reviewable commit. A tick pushed after watch reported the PR ready gets a normal review round. Milestone close still asks the user for each user-verified exit criterion; a ticked user task is not read as the criterion's result. Reversal cost: medium for the marker, which packs and projects will write; low for the rest.
