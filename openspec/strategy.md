# Specwright Strategy

## Purpose
Specwright is a spec-driven development bundle for AI coding agents, built on unmodified OpenSpec. It takes a change from idea to merged PR with architecture reasoning scaled to the change, test discipline, review gates and a safe git and GitHub workflow. It removes the manual rescue work that agents otherwise leave behind: broken branches, unverifiable commits, missed review findings and half-finished PRs.

## Users
- **Primary: the maintainer**, who runs 4-5 projects at once with several agents in parallel (Claude Code, Codex, OMP), often unattended. They need changes that finish without hand-fixing git or PR state, reviews that catch problems before PR bots do, and updates that never break work in progress. Their workflow decides trade-offs.
- **Secondary: public adopters** who install through the README prompt. The install prompt and the documented settings stay usable and safe to re-run for them, but they do not get extra compatibility promises before 1.0.

## Boundaries
- No OpenSpec core changes: only a custom schema, skills, agents and templates.
- First-class host agents: Claude Code, Codex and OMP. Others are best-effort.
- Runtime dependencies of shipped skills and scripts: `bash` with a POSIX userland (`sed`, `grep`, `mktemp` and similar; Git Bash on Windows), `git`, `gh` (2.40+), `python3` (standard library; the scripts accept 3.8+, but store-backed feedback needs 3.10+ until #46) and the OpenSpec CLI. No Node runtime of our own, no daemons, no hosted service.
- Specwright never merges a PR on GitHub, pushes `main`, rewrites published history or acts as another GitHub account unless a documented, opt-in setting says so. Known exceptions to the account boundary are tracked in #38: the empty default login, unfenced `git fetch`/`git pull` on main and one post-merge `gh pr view`, and credentials embedded in a remote URL, which can make a push authenticate as another account (see the architecture's GitHub identity contract). The only merges it makes are local, with `--no-ff`, and never pushed: with `finish: local` (the default), `specwright-finish` merges the change branch (store-backed: the store branch, then the code branch), and `specwright-roadmap` merges its `docs/` branch.
- Cross-model review sends the change and the repo files the reviewer reads to another model provider. It is on by default and documented in the settings; `review.cross_model: false` turns it off.
- Not a package publisher (npm, crates.io, PyPI) and not a CI system.

## Success measures
1. The evals (`evals/git-workflow`, `evals/pr-pair`) pass on every first-class harness, including a cheaper-model stress tier.
2. A change goes from branch to merged PR with no manual git, commit or PR-state rescue.
3. Reviews catch defects before PR review bots do. Measured over the maintainer's merged PRs, compared with the PRs merged before the pre-ship review shipped (0.2.0): the number of actionable bot findings per PR, and the findings still open or filed as issues at hand-off. Fewer fix rounds alone does not count, because the rounds are capped.
4. Re-running the install prompt never loses local settings or breaks a change in flight. Local settings are kept today; keeping changes in flight safe is a target, not yet met (sh1ny/specwright#36).

## Tracks
- **Workflow reliability:** branch, commit, finish and PR steps that recover from interruption and fail closed.
- **Review quality:** design review, pre-ship review and PR feedback handling across models.
- **Cost:** cheaper model tiers for bounded work, without losing quality.
- **VCS backends:** Git first; jj and GitButler as selectable backends.
- **Distribution:** versioning, tags, releases and safe updates.

## Assumptions
- Versions follow pre-1.0 semver: minor for a feature, a config key or a workflow change; patch for a fix. 1.0.0 is the maintainer's deliberate call (see sh1ny/specwright#28).
- GitHub is the only forge supported.
- OpenSpec stays pinned (1.16.0 today) and is upgraded deliberately, in its own change.
