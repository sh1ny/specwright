<p align="center">
  <a href="https://github.com/sh1ny/specwright">
    <img src="docs/assets/banner.jpg" alt="Specwright: spec-driven development for AI coding agents" width="100%">
  </a>
</p>

<p align="center">
  <img alt="version" src="https://img.shields.io/badge/version-0.40.0-blue">
  <img alt="OpenSpec" src="https://img.shields.io/badge/OpenSpec-1.16.0-8A2BE2">
  <img alt="agents" src="https://img.shields.io/badge/agents-Claude%20Code%20%7C%20Codex%20%7C%20OMP-555">
  <a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green"></a>
</p>

A lightweight spec-driven development bundle for AI coding agents, built on [OpenSpec](https://github.com/Fission-AI/OpenSpec). It keeps OpenSpec's small artifact set and adds what OpenSpec leaves out — **architecture reasoning scaled to the change**, test discipline, a git and GitHub PR workflow, and project-level planning — as one custom schema plus a handful of auto-activating skills. No OpenSpec core changes.

## ✨ What it adds

- 🏗️ **Architecture reasoning, scaled to the change.** Every design starts with a six-trigger triage. No trigger → a few lines. Any trigger → state ownership, failure visibility, resource bounds, flow gaps and a mechanism ledger, then a fresh-context, ideally cross-model review that gates the tasks.
- 🔍 **Pre-ship review.** Before the first PR or a local merge, a reviewer CLI other than the harness you run in (Codex, Claude Code or OMP, read-only and isolated) reviews the finished change. Blocking findings are fixed, or waived by you, before anything ships.
- 🧪 **Test discipline.** Every requirement needs a failure scenario; every scenario maps to a named test that goes red → green during apply.
- 📜 **Durable decisions.** Immutable, supersedable ADRs, indexed in the project's architecture file.
- 🌿 **Git workflow.** A branch per change, one commit per task (or per task group with `commit_granularity: group`), and a finish step that merges locally or goes through a GitHub PR.
- 🔁 **PR tooling.** Ship a PR with a useful description, resolve review feedback, watch CI and reviews in the background — with a few `sw` commands instead of dozens of tool calls.
- 💸 **Cheap delegation.** The main agent plans and verifies; a cheaper implementer model does the tasks from a focused packet.
- 🗺️ **Project planning.** A big idea becomes a one-page strategy, an architecture baseline and a milestone roadmap; each milestone is a handful of OpenSpec changes.

## 🔄 How it fits together

```mermaid
flowchart LR
    R["specwright-roadmap<br/>init · next · close"] -.-> P
    B["specwright-branch"] --> P[proposal] --> S[specs] --> D["design<br/>LIGHT | FULL"] --> V[review] --> T[tasks]
    T --> A["apply<br/>specwright-commit"] --> Q["pre-ship review<br/>specwright-review"] --> F["archive<br/>specwright-finish"]
    Q -. "finish: pr" .-> PR["specwright-pr<br/>ship · feedback · watch"]
    PR -.-> F
    F -.-> R
```

| Phase | Owned by | What happens |
|---|---|---|
| Start a change | [`specwright-branch`](skills/specwright-branch/SKILL.md) | Clean `main` check, then `<prefix>/<change-name>` branch |
| proposal → specs → design → review → tasks | [`schemas/specwright`](schemas/specwright/schema.yaml) | Artifacts with architecture triage and a review gate |
| Apply | [`specwright-commit`](skills/specwright-commit/SKILL.md) + [`specwright-implementer`](agents/claude/specwright-implementer.md) (or [`specwright-implementer-light`](agents/claude/specwright-implementer-light.md) for LIGHT changes with `cheap_tier.enabled`) | One commit per task (or per task group with `commit_granularity: group`), orchestrator re-verifies delegated work |
| Pre-ship review | [`specwright-review`](skills/specwright-review/SKILL.md) | Cross-model review of the finished change; ship and the local merge wait for a pass |
| PR | [`specwright-pr`](skills/specwright-pr/SKILL.md) | Ship, address feedback, watch CI (`finish: pr`) |
| Archive | [`specwright-finish`](skills/specwright-finish/SKILL.md) | Archive commit, then local `--no-ff` merge or push to the PR |
| Release (opt-in) | [`specwright-release`](skills/specwright-release/SKILL.md) | Version bump as the last task, tag and GitHub release after merge |
| Across changes | [`specwright-roadmap`](skills/specwright-roadmap/SKILL.md) | Strategy, architecture baseline, milestones |

**Decisions while planning.** `decision_making` chooses how far you are kept in the loop. With `autonomous` (the default, and what an unset key means) the agent decides and shows a decision summary table at the end of planning without waiting. With `important` it puts the important decisions to you, each with options and a recommended one: those that are costly to reverse, bind future changes, change what users see, or rest on weak evidence. With `all` it puts every decision to you. Questions go through the harness's ask tool, at most 4 at a time. An instruction you give when a change starts overrides the setting for that change and is recorded in the proposal's Decision Making section. A decision you chose is never changed without you.

---

## ⚡ Install / Update

> **Prerequisites:** core: the OpenSpec CLI at the pinned version (`npm i -g @fission-ai/openspec@1.16.0`, which needs Node.js 22.12 or later), `openspec init` run in the project, `git`, `curl` (`curl.exe` on Windows) and a SHA-256 tool (`Get-FileHash` in PowerShell on Windows, `sha256sum` or `shasum` elsewhere). The install needs no bash and no Python: the agent fetches the first `sw` with `curl` and checks it with the hash tool, and every later step is `sw update`. A `main` install also needs `mise`, which builds `sw` from the clone. The installed skills run `sw` directly: they need no `bash` and no Python, and review operations invoke no Node. The PR skills also need `gh` 2.48 or later; without it the install still completes and reports `PR workflow not ready`.

> **OpenSpec version:** the install compares `openspec --version` with the version Specwright is pinned to (`OPENSPEC_VERSION`, 1.16.0) and stops on any other version, newer patch releases included, before it writes a file. To install with another version anyway, say so in your own words, naming the version you have: `continue with OpenSpec <version>` (for example `continue with OpenSpec 1.15.0`). The override covers that one run, the agent never offers it, and the report marks it `(pinned 1.16.0, override)`.

> **Releases and interruptions:** the update installs the latest release tag (`v<version>`) unless you name a version or ask for `main`, and reports the ref it installed. It stages the new files, swaps them in with a journal (`openspec/.specwright/update.json`) and stamps `VERSION` last, so an interrupted run is resumed or rolled back by the next one. The staging directories are named `.specwright-update-*/` (next to the skills, agents and schema they replace) and are removed when the update finishes. You may add `.specwright-update-*/` to your `.gitignore` so an interrupted update never shows up in a commit.

Copy the prompt below and paste it into your coding agent. **The same prompt installs and updates.**

```text
Install/Update Specwright

Install or update Specwright from https://github.com/sh1ny/specwright into the
current project. Follow the steps in order. Ask the user where indicated - do
not assume answers. Every step is safe to repeat, so re-running this prompt
also repairs an interrupted or partial install.

Step 1 - Check prerequisites
- Run `openspec --version` and record its output (Step 3 checks it). If
  it fails, tell the user to install the pinned version
  (`npm i -g @fission-ai/openspec@1.16.0`) and STOP.
- Core: run `git --version` and `curl --version` (`curl.exe --version` on
  Windows). If either fails, tell the user to install it, naming the tool,
  and STOP before any download.
- Core: find a SHA-256 tool for checking downloads. On Windows run
  `Get-Command Get-FileHash` in PowerShell. On Linux and macOS run
  `sha256sum --version`, and if that fails `shasum --version`. If none runs,
  tell the user to install `sha256sum` or `shasum` (name both on Linux and
  macOS), write no file, and STOP before any download.
- PR workflow (`specwright-pr`): run `gh --version` and check
  it is 2.48 or later. If not, record `gh 2.48+` for Step 8 and continue:
  it does not block the install or the version stamp.
- Undo (`specwright-finish`): a Git undo that resumes the archive branch
  needs Git 2.40 or later. An older Git does not block the install or the
  version stamp; only that undo refuses, saying so.
- Run `openspec list --json` in the code checkout and read `root`.
  - `"root": null`: if the error names this project's `openspec/config.yaml`
    (it starts with `Declared in` or `Invalid store declaration in`), show
    its message and fix and STOP. Otherwise, if the version recorded
    above (the first
    `\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?` token in
    the output, as Step 3 takes it) is not 1.16.0 (the pin this prompt
    installs) or is unreadable by Step 3's rule, an unpinned OpenSpec may
    not resolve a store: name the version found (or unreadable), tell the user to run
    `npm i -g @fission-ai/openspec@1.16.0` and rerun this prompt, write
    no file, and STOP. Do not suggest `openspec init` then:
    in a store-backed project it would create a root that overrides the
    store. Only with the pinned version, tell the user to run
    `openspec init` first and STOP.
  - Otherwise `<root>` below means `root.path`. It is the code checkout
    for a repo-local project, or a store checkout (OpenSpec stores, with the
    pinned OpenSpec) elsewhere. Say which.
- The schema and `config.yaml` go in `<root>/openspec/`. `specwright.yaml`,
  `.specwright/VERSION`, skills and agents go in the code checkout. When
  `<root>` is not the code checkout, never create `openspec/specs/`,
  `openspec/changes/` or `openspec/schemas/` in the code checkout (a real
  `openspec/` root there would override the store), and leave its
  `openspec/config.yaml` (the `store:` pointer) as it is.

Step 2 - Choose targets
Ask which agents this project uses (several may apply) and confirm the paths:
- Claude Code: skills → `.claude/skills/`, agents → `.claude/agents/`
- OMP: skills → `.claude/skills/` (OMP reads it), agents → `.omp/agents/`
- Codex: skills → `.agents/skills/`
- Other: ask for the skills directory.
- On every backend, offer the in-repo directories above or the user-level ones:
  `~/.claude/skills/` and `~/.claude/agents/` (Claude Code; OMP skills),
  `~/.agents/skills/` (Codex), `~/.omp/agents/` (OMP agents). Warn once that a
  user-level install is shared by every project on the machine (one Specwright
  version; an update from one project updates all) and that Claude Code runs a
  user-level `specwright-*` skill instead of an in-repo one of the same name.
  When the user moves a project from user level to in repo, say to update the
  user-level `specwright-*` copies to 0.14.0 or newer, or remove them once no
  other project on the machine relies on them, and to restart agent sessions;
  an older user-level copy stops every `vcs.sh` call with
  `scripts_in_workspace` once in-repo copies exist (that is a copy from before
  0.14.0, a version that still had `vcs.sh`).
  This is a warning only: install where the user chooses.
- GitButler (`vcs: gitbutler`, already set in `openspec/specwright.yaml` or
  chosen now; ask when unsure): every applied branch shares the work tree, so
  a branch that changes in-repo skills changes them for every applied branch.
  Warn once that keeping them consistent is the user's job, and that a
  user-level install avoids it (not for packs: when `packs:` in
  `openspec/specwright.yaml` enables a pack, `plan` refuses a user-level
  target with `packs_user_level`).
- Packs: when `packs:` in `openspec/specwright.yaml` enables a pack, packs need
  in-repo skills directories, and `plan` refuses a user-level target with
  `packs_user_level`. Say so before the user chooses. The core install location
  stays the user's choice (ADR 0021); only packs narrow it (ADR 0023).

Step 3 - Choose the version, download and compare versions
- Choose the ref to install. This prompt needs release 0.37.0 as its minimum
  and drives `sw update` interface 3 (Step 4).
  - Default: the latest release tag. Run
    `git ls-remote --tags --refs https://github.com/sh1ny/specwright 'v*'`,
    keep the tags of the form `v<major>.<minor>.<patch>` and take the highest
    by semver (semantic version order, not text order).
  - A version the user named (say `0.37.1`) is the tag `v0.37.1`. If that tag
    does not exist, STOP before Step 4: name it and list the tags that exist,
    and write no file.
  - `main` only when the user asks for it, or when the repository has no
    release tag: then install `main` and record `main (no release tag)` for
    Step 8.
  - Minimum release, named version: if the user's tag is below 0.37.0 (the
    first release with `sw update`), STOP before Step 4: name the tag and the
    minimum release 0.37.0, say versions before 0.37.0 cannot be installed by
    this prompt and that the README prompt of that tag installs it
    (`https://github.com/sh1ny/specwright/blob/<tag>/README.md`), and write no
    file.
  - Minimum release, latest tag: if the highest tag is below 0.37.0, STOP
    before Step 4: name it and the minimum release 0.37.0, offer to install
    `main` instead, and write no file. Install `main` only if the user then
    says so.
- Create a temporary directory `<tmp>`. Clone the chosen ref to
  `<download>`, which is `<tmp>/download`:
  `git clone --depth 1 --branch <tag> https://github.com/sh1ny/specwright <download>`
  (`--branch main` for `main`; any other method that gets exactly that ref
  works). Record the ref installed (`v0.37.0`, `main`, or
  `main (no release tag)`) for Step 8.
- Read the downloaded `VERSION` and `OPENSPEC_VERSION` (`<pin>`, the
  OpenSpec version this release is checked against) and the installed
  `openspec/.specwright/VERSION` (missing = fresh install, or an earlier
  install that did not finish). Tell the user which applies: fresh install,
  update from <old> to <new>, or reinstall of <new>.
- Check OpenSpec against the pin, before Step 4 writes anything: run
  `openspec --version` again and take `<found>`, the first token in its
  output matching `\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?`.
  Compare the whole token, pre-release suffix and build metadata included,
  with `<pin>` as strings: only an exact match passes.
  Against a pin of 1.16.0, 1.16.1, 1.16.0-beta.1 and 1.16.0+vendor.1 are
  each a mismatch.
  A token directly followed by a digit, letter, `.`, `+` or `-` (for
  example `1.16.0.0` or `1.16.0vendor`) is unreadable output, not a match on
  its first part.
  - Exact match: record `OpenSpec <found> (pinned)` for Step 8 and
    continue.
  - Mismatch: unless the override below applies, STOP before Step 4.
    Name `<found>` and `<pin>`, and tell the user to run
    `npm i -g @fission-ai/openspec@<pin>` and rerun this prompt. Say that
    the documented override exists (`continue with OpenSpec <found>`)
    without recommending it. Delete the temporary directory and write no
    file.
  - Output with no version number in it, or an unreadable token: show the raw output, then handle
    it as a mismatch that no override can apply to (STOP before Step 4,
    with `<found>` as unreadable, `<pin>` and
    `npm i -g @fission-ai/openspec@<pin>`; delete the temporary directory
    and write no file).
  - No `OPENSPEC_VERSION` in the downloaded copy, or an empty one: say
    the downloaded copy names no pinned OpenSpec version, and STOP before
    Step 4, with no override (name `<found>`, `<pin>` as unknown and
    `npm i -g @fission-ai/openspec@<pin>` with the pin from Step 1's
    install command; delete the temporary directory and write no file).
- Override: after a mismatch, continue to Step 4 only if the user has
  said in their own words, in the request or in a reply,
  `continue with OpenSpec <found>`, naming the version found. Never offer
  it as a default or recommend it, and never infer it. A plain or general
  confirmation ("yes, go ahead") is not an override: write no file, and
  ask the user to install <pin> or to state the override with the found
  version. An override naming a different version is not an override:
  STOP as on a mismatch, naming `<found>`. An override given in a reply
  after the mismatch stop comes after the temporary directory was deleted:
  clone the repository again at the same ref, and run this
  step's checks on the new copy with the override in force. The override holds
  for this run only: nothing is stored, and the next run checks again. With
  it, record `OpenSpec <found> (pinned <pin>, override)` for Step 8.
- Get `sw`, before Step 4 stages anything. Every later step runs
  `sw update` with the binary this bullet places, called `<sw>` below
  (`<home>/.specwright/bin/<version>/sw`, `sw.exe` on Windows; `<home>` is
  `SPECWRIGHT_HOME`, else your home directory). A release tag takes the fetch
  below, and `main` takes the build after it.
  - Release tag: `<boot>` is `<tmp>/boot`, `<release>` is
    `https://github.com/sh1ny/specwright/releases/download/<tag>`, and
    `<asset>` is the host's binary: `sw-linux-x64`, `sw-linux-arm64`,
    `sw-macos-arm64`, `sw-macos-x64` or `sw-windows-x64.exe`. On any other
    host, STOP before Step 4, naming the host and these five assets. Use the
    commands of the host's shell as they stand, PowerShell on Windows and the
    POSIX ones on Linux and macOS, with a path in quotes when it holds spaces.
    In PowerShell a command whose path is in quotes runs only through the
    call operator, as `& "<path>" <arguments>`: use it for every run of
    `<boot>` files and of `<sw>`.
  - Fetch `<asset>`, `THIRD_PARTY_NOTICES.txt` and `SHA256SUMS` into `<boot>`,
    each with this command, `<file>` set to the file's name. It accepts https
    only, on the first URL and on every redirect, and stops at 120 seconds or
    64 MiB. Its first option, `-q`, skips the user's curl config file, so a
    setting there such as `insecure` cannot weaken these checks:
    - POSIX fetch: `curl -q -fL --proto =https --proto-redir =https --max-time 120 --max-filesize 64M -o <boot>/<file> <release>/<file>`
    - PowerShell fetch: `curl.exe -q -fL --proto =https --proto-redir =https --max-time 120 --max-filesize 64M -o <boot>\<file> <release>/<file>`
    A fetch that fails or passes a bound is a stop: STOP before Step 4, name
    the file and the cause, delete its partial file and `<tmp>`, run nothing
    and write no file. A release with no `THIRD_PARTY_NOTICES.txt` or no
    `SHA256SUMS` stops the same way, naming the file and the release.
  - Check both hashes, the asset's and the notice's, before anything runs.
    Run the hash command on each file and compare the first word of its
    output, in any letter case, with that file's line in `SHA256SUMS`
    (`<hash>  <name>`). On Linux and macOS use the `sha256sum` line, or the
    `shasum` line when `sha256sum` is not installed:
    - POSIX hash: `sha256sum <boot>/<file>`
    - POSIX hash fallback: `shasum -a 256 <boot>/<file>`
    - PowerShell hash: `(Get-FileHash -Algorithm SHA256 <boot>\<file>).Hash`
    A hash that differs from its line, or a file with no line, is a stop:
    STOP before Step 4, name the file and both hashes, delete the file
    without running it, delete `<tmp>` and write no file.
  - Only when both hashes match, on Linux and macOS make the asset executable
    (a fresh download is not), and on macOS clear quarantine when the check
    lists `com.apple.quarantine`. Windows has no such step:
    - POSIX chmod: `chmod 0755 <boot>/<asset>`
    - POSIX quarantine check: `xattr <boot>/<asset>`
    - POSIX quarantine: `xattr -d com.apple.quarantine <boot>/<asset>`
  - Run the checked file. Its `version` must be the tag's version without
    the `v`; if not, STOP before Step 4, name both versions, delete `<tmp>`
    and write no file:
    - POSIX run: `<boot>/<asset> version --json`
    - PowerShell run: `<boot>\<asset> version --json`
  - Check the interface: run `<boot>/<asset> update interface` (the same path
    with `update interface` in place of `version --json`). It reads and
    writes nothing and must print `"interface":3`. If the run fails (a
    release with no `update` command) or prints another number, STOP before
    Step 4: name the ref, the interface found (or that there is none) and
    interface 3 (the one this prompt drives), delete `<tmp>` and write no
    file. Nothing is recovered, placed or written first.
  - Place it: run `<boot>/<asset> update sw-install --code <code checkout>
    --root <root.path> --download <download> --ref <tag>`. It downloads the
    host's binary, `SHA256SUMS` and the notice again, checks them, places the
    notice and then the binary at `<sw>`, and never moves the copy it runs
    from. It writes nothing in the project. Record its `path` (that is
    `<sw>`) and `action` (installed, replaced or kept) for Step 8.
    `"ok": false` is a stop: STOP before Step 4, name its `error` and show
    its `message`. With `assets_not_uploaded`, say the release's binaries
    are not uploaded yet and to rerun this prompt once they are. Delete
    `<tmp>` and write no file.
  - `main`: no release carries a binary, so build it from the clone. Run
    `mise --version`; if it fails, STOP before Step 4, say a `main` install
    builds `sw` with `mise run install-sw`, name `mise`, delete `<tmp>` and
    write no file. Then run `mise run install-sw -- --expect-update-interface 3`
    in `<download>`. The task builds `sw`, checks that its `update interface`
    is 3 before placing anything, places it at `<sw>` and prints that path.
    A failed build, or an interface other than 3 (or none), is a stop: STOP
    before Step 4, name `main`, the failure or the interface found (or that
    there is none) and interface 3, delete `<tmp>` and write no file. Record
    `sw built from main` and the path for Step 8.

Step 4 - Install files (`sw update` stages, then swaps)
`sw update` below is `<sw> update`, the binary Step 3 placed for the
downloaded version (or built from `main`), never an `sw` found on `PATH` or one
of another version. Every call takes the same
options: `--code <code checkout>`, `--root <root.path>`, `--skills <dir>` for
each chosen skills directory, `--agents claude=<dir>` and `--agents omp=<dir>`
for each chosen agents directory, `--download <download>` and `--ref <ref>`.
Pass each pack that `packs:` enables as `--pack <name>`, and each of its
documents as `--pack-doc <pack>.<id>=<path>`, where `<path>` is the
`packs.<name>.documents.<id>` override in `openspec/specwright.yaml`, else the
manifest's default path. It prints one JSON document; `"ok": false` with an `error` is a stop. It
replaces every `specwright-*` skill directory, the agent files and
`<root>/openspec/schemas/specwright/` with the downloaded ones, so files
removed upstream do not linger, and keeps the user's `model:` value in an
installed agent file (say so in Step 8).
- Run `sw update` `plan`. Read `from`, `to`, `kind` (fresh, patch,
  workflow, reinstall or downgrade), `role`, `orphans`, `journal`, `warnings`,
  the changes in flight with their validation result, `refusals`, the adopted
  pack skills and `packs_previous` (the packs enabled before this update,
  from a pending journal, else from `packs.json`; Step 5 and `pack-verify`
  use it, never the `packs.json` the swap wrote).
  - An earlier update that did not finish: the first `plan` of this run
    runs `recover` on its journal before anything else and
    reports a `recovered` object. Tell the user its `message`:
    `discarded unfinished update to <to>`, `resumed update to <to>` or
    `rolled back to <prev>`, followed by its `sw_note` when that is not null
    (no `sw` binary serves `<prev>`). A `journal` still listed afterwards in phase
    `swapped` with this download's `to` is a swap that finished before the
    stamp: set `swapped` to true, skip `stage` and `swap`, and, when this
    `plan` lists no `refusals`, ask the orphan question below and go on with
    Steps 5-7; a refusal is handled as below first, removing nothing. No `swap` report exists then:
    take `store_written` from `recovered.store_written` in `plan`'s document,
    in place of `swap`'s.
  - A refusal (exit 1, `"error": "refused"`, listed in `refusals`): a change
    in flight that fails validation against the new schema, a store another
    project owns, a busy store, and so on. Tell the user each refusal as
    `sw update` words it and STOP. Pack refusals are `pack_unknown`,
    `pack_requires`, `pack_cycle`, `packs_on_store`, `packs_user_level`,
    `unmanaged_skill`, `pack_doc_path` and the pack-check codes: report each
    one; no installed file changes.
    - With `"unchanged": true`, report that the installed version is
      unchanged (Step 8). Nothing was changed, so only the temporary directory
      is left to delete.
    - With `"unchanged": false`, a resumed swap is pending: the new files are
      in place, but VERSION is not stamped. Do not report the installation as
      unchanged. Say that `<to>`'s files are installed but not stamped, give
      the restart notice (Step 8), and say that rerunning this prompt once the
      refusal is resolved completes the update.
  - `orphans` lists what is installed with no downloaded counterpart:
    `specwright-*` skill directories, `specwright-*.md` agent files and the
    skills an enabled pack installed before and no longer ships (`sw update`
    never touches them; a disabled pack's skills are a `swap` removal, not
    orphans):
    list them all and ask before removing them, as the orphan question below
    says.
  - Keep `warnings` for Step 8 (a change in flight found only on a remote
    branch is not validated), and the changes validated against `<to>`.
  - Keep the adopted pack skills (an identical hand copy that the install now
    records) for Step 8.
- Run `sw update` `stage`: it copies every new skill directory, agent file and
  the schema into a staging directory next to its target
  (`.specwright-update-*/`) and verifies the copy. On `verification_failed`
  (it names the files and removes the staging) STOP and report that the
  installed version is unchanged. Until the swap, every installed file keeps
  its previous content.
- Run `sw update` `swap`. When it reports `ok`, set `swapped` to true and keep
  its `store_written` value and its `restart` notice. When it refuses (the
  changes in flight differ from the plan, the store is busy, ...), `swapped`
  stays false: STOP and report that the installed version is unchanged. When
  it fails part-way (an error that is not a refusal), tell the user to rerun
  this prompt: `recover` resumes or rolls back the swap.
- Orphan skills, settled before Step 5: ask about each `specwright-*` skill
  directory among the current plan's `orphans` that this update does not
  install, after a new `swap` and on a rerun whose plan shows a completed swap
  (once that swap is confirmed, as above). Remove only those the user agrees to
  remove. A declined orphan stays, passes Step 7 as kept, and Step 8 lists it
  as an orphan kept. List the other `orphans` entries this update does not
  install (agent files, pack
  skills) too, ask before removing them, and remove only those the user
  agrees to, after `swap`; Step 7 does not check them.
- Legacy openspec-git-flow: if `openspec-git-branch`, `openspec-git-commit` or
  `openspec-git-merge` skill directories exist in a chosen skills directory,
  or `openspec/.git-flow/` exists, list them and ask before removing them.
- Do not write `openspec/.specwright/VERSION` yet; Step 7 does, last.

Step 5 - Merge <root>/openspec/config.yaml (never remove unrelated content)
- Run this step only when `plan` reported role `none` (a repo-local project)
  or `swap` reported `store_written: true` (this project owns the store, or
  has just claimed it). When `plan` resumed the swap and no `swap` ran, use
  `recovered.store_written` from `plan` instead. Otherwise skip it: another
  project owns the store's config.yaml, so leave `config.yaml` as it is and
  carry the owner `<id>` from `plan` to Step 7.
- If it does not exist, copy the downloaded `templates/openspec/config.yaml`.
- Otherwise:
  - `schema:` - if it is missing or `spec-driven`, set it to `specwright`. If
    it names another schema, ask the user before changing it (in a store,
    say the change applies to everyone who uses that store); if they
    decline, keep it.
  - `context:` - if there is no `context:` key, add `context: |` holding the
    lines from the downloaded `templates/openspec/config.yaml` (leave any
    commented-out example alone). Otherwise, a
    line is Specwright-managed when it starts with
    `MANDATORY: Invoke the 'specwright-`, `MANDATORY: Before archiving a change`,
    `Project-level planning (strategy` or `Specwright settings (`. Remove
    every managed line (older wordings and duplicates alike), then append
    each downloaded context line once. Remove any line naming `openspec-git-branch`, `openspec-git-commit` or
    `openspec-git-merge`. Leave every other line alone, including the
    project's own lines that mention Specwright.
- Pack lines, after the copy or the merge above (a copied template has none
  yet): remove each line starting `[pack:<name>] ` from `context:`,
  from every `rules.<artifact>` list and from every
  `operations.<op>.guidance` list, only for a `<name>` enabled now or in
  `packs_previous` (never decided from the current `packs.json`). Keep
  every other `[pack:` line and report it as not managed (enable the pack to
  have it managed). Then append each enabled pack's lines, prefixed
  `[pack:<name>] `, in pack order (dependencies first, then by name) and in
  manifest order. Write each list entry as a double-quoted YAML scalar
  (escape `"` and backslash): an unquoted entry starting `[` is a YAML flow
  sequence, and OpenSpec 1.16.0 then drops that artifact's whole rules list.
  `context:` stays a block scalar.
- After the merge (or the copy), run `sw update` `note-config`: it records the
  merged config.yaml's hash in the journal, so a later rollback knows what this
  install wrote. On `"ok": false` (or if it was interrupted), report it and
  stop: run `note-config` again once its error is resolved, and go on only
  when it reports `"ok": true`. Without that record a later rollback cannot
  tell the merged config.yaml from the user's own.
- Then run `sw update` `pack-verify`, with
  `--previous <name>` for each name in `packs_previous`. On failure (`missing`,
  `duplicate` or `not_enabled`), report each line and do not stamp `VERSION`.

Step 6 - Settings (openspec/specwright.yaml in the code checkout)
- If it does not exist, copy the downloaded
  `templates/openspec/specwright.yaml`, then ask the user for:
  finish mode (`local` merges to main locally; `pr` goes through GitHub PRs),
  the GitHub login for pushes/PRs/replies, an optional review-request comment
  and the login that posts it, whether design reviews may call a different
  model's CLI (`review.cross_model`), whether to review each finished change
  before its first PR or local merge (`review.preship`), and an optional
  pre-push validation command.
  If the project already has strategy, architecture or roadmap documents
  (e.g. STRATEGY.md, docs/architecture*, a roadmap or milestone plan), ask
  whether to point the `project:` paths at them instead of the defaults.
  Write their answers into the file.
- If it exists, keep the user's values and add only keys that are missing,
  with the downloaded defaults. Compare keys by dotted path (`pr.request_as`,
  `planning_store.login`), never by bare name: `github.login` and
  `planning_store.login` are different keys.
  - A commented-out template line `#  key:` gets its path from its
    indentation after the `#`, under the nearest parent above it (commented
    or not). A path the template has only commented out is optional and
    still supported: never list it as removed when the user's file sets it,
    and never add it when the user's file lacks it.
  - Entries under `pr.reviewers.` and `planning_store.reviewers.` are
    user data (one per reviewer login): never compared, added or listed as
    removed.
  - Every key under `packs.` and every entry under `release.version_files.`
    is user data too: never compared, added or listed as removed, never merged
    into an existing mapping, and kept in order. The template holds only a
    commented `packs:` example.
  - `release.version_files` itself is compared like any key. When the user's
    file lacks it and the template sets it, offer the template's whole
    mapping, in order, as one default, and list it as added when the user
    keeps it. The user may keep or decline it; a declined mapping is not
    written.
  List each added key with its default and its comment from the downloaded
  `templates/openspec/specwright.yaml`, and ask whether to keep the default.
  If the user's file has keys the downloaded file no longer has (uncommented
  or commented out), list them and ask before removing them. A key removed
  with the user's consent may take its comment with it. When the user
  declines, the key and its comment stay unchanged, and Step 8 lists it
  neither as added nor as removed.
  The merge keeps the user's values and the comments of every key it keeps: it
  never rewrites, adds or removes a comment on a key the user's file keeps, and
  asks nothing about a comment that differs from the template's. It copies the
  template's comment only with a key it adds, when the user accepts that key's
  default.
- GitButler's agent skill, only when `vcs: gitbutler` is set in
  `openspec/specwright.yaml` (just chosen, or already there). It is GitButler's
  own skill and the tool guidance on that backend; Specwright ships none. For
  each chosen skills directory (Step 2), offer
  `but skill install --path <skills dir>/gitbutler`, run in the code checkout.
  Run it only on the user's yes. If the user declines or does not answer, run
  no `but skill install` and change no skills directory. Always pass `--path`
  (without a terminal `but` picks a directory of its own), and never install it
  silently or anywhere but a skills directory the user chose in Step 2. This
  rule is about GitButler's skill only; it does not change where Specwright's
  own skills and agents go (Step 2). With `but` not on PATH, skip the offer and
  say so.

Step 7 - Verify, stamp the version, finish, clean up
- Run `openspec schema validate specwright` inside `<root>`.
- Every file of the downloaded `skills/specwright-*` directories exists,
  with the same content, in every chosen skills directory. Check each
  `specwright-*` directory there by itself. One with a downloaded counterpart
  holds no extra file: a file the download lacks fails the check, naming it.
  One with no downloaded counterpart (an orphan) passes when the user kept it
  in Step 4, and Step 8 reports it as an orphan kept. An orphan the user agreed
  in Step 4 to remove that is still there fails the check, naming it, and no
  stamp is written. The check allows no other `specwright-*` directory than the
  downloaded ones and the orphans the user kept. Other directories (OpenSpec's
  `openspec-*`, the user's own, and a `gitbutler` directory that `but skill
  install` created at the user's yes in Step 6) do not count: leave them and
  report nothing about them.
- The pack skills of every enabled pack exist in every chosen skills
  directory, and `sw update` `pack-verify` passes. Skip the `pack-verify`
  check when Step 5 was skipped (no pack is enabled on a store, and the
  config.yaml is another project's).
- Every downloaded agent file exists in each chosen agents directory (the
  `model:` line may differ, per Step 4).
- `<root>/openspec/config.yaml` has `schema: specwright` (or the schema the user
  chose to keep - then report "installed, but not the default schema"),
  every downloaded context line exactly once, and no other managed line.
  When Step 5 was skipped this check is another project's file: do not count
  it as a failure, report it as `store config managed by owner <id>`, and the
  version is still stamped.
- `openspec/specwright.yaml` has every uncommented dotted path in the
  downloaded `templates/openspec/specwright.yaml` (commented-out paths are
  optional), unless the user chose otherwise in Step 6: a template default the
  user declined is not added, and the check passes without it. Skip every entry
  under `pr.reviewers.`, `planning_store.reviewers.`, `packs.` and
  `release.version_files.`: those are user data. Check `release.version_files`
  itself like any other key.
- If every check passes, copy `VERSION` to `openspec/.specwright/VERSION` (the
  stamp), then run `sw update` `finish`: it removes the previous copies, the
  staging directories and the journal (run it again if it was interrupted).
  After the stamp, run `sw update` `pack-docs`: it creates each missing pack
  document from its template, never overwrites one, and reports each as
  `created` or `kept`. It needs no journal, so run it again if it was
  interrupted.
  If any check fails, do not write the stamp: report each failed check and how
  to fix it, and never claim success. Say the update is swapped but not
  stamped: after the fix, rerun this prompt (it goes to Step 4's orphan
  question, then to Steps 5-7),
  or roll back with `sw update` `recover --rollback` (it reports
  `rolled back to <prev>`, plus an `sw_note` when no `sw` serves `<prev>`, and
  stops when the store is busy or no longer this project's).
- Delete `<tmp>`.

Step 8 - Report briefly: the ref installed (`v0.37.0`, `main` as asked, or
`main (no release tag)`), version change (fresh, <old> → <new>, or reinstall),
directories used, skills and agents installed (new vs updated, models kept),
orphans removed or kept, config and settings created/merged/unchanged (keys
added or removed), legacy files removed, and the result of each Step 7 check
(the config.yaml check may read `store config managed by owner <id>`). In a
workflow update, list each change in flight that `plan` validated against
<new>. Report the packs installed or removed, the adopted skills, the
`[pack:` lines not managed and the documents created or kept. Give the store role (none, claim, owner or other) and, in a store, the
owner (after a claim: this project now owns the store's schema), and list each
`warnings` entry: a change in flight found only on a remote branch (name and
ref) is in flight elsewhere, not validated. When `<root>` is a store, list the
files this install left uncommitted there (by path, from
`git status --porcelain` in the store, `openspec/.specwright/STORE` included)
and say the user commits them in the store; this prompt never commits.
- Restart notice, only after a swap (`swapped` is true): say that agent
  sessions started before this update still run the <old> skills and must be
  restarted before they continue a change on <new> (after a fresh install,
  sessions started before the install). New skills and agent definitions load
  only in a new agent session started after this install: start one before
  relying on them.
- Without a swap (a refused, stopped or failed update that changed no installed
  file): no restart notice. Say that the installed version is unchanged.
Report the `sw` binary as recorded in Step 3: for a tag, its path and whether
it was installed, replaced or kept; for `main`, `sw built from main` and its
path.
Then check whether the installed skills can run: the file
`<home>/.specwright/bin/<installed VERSION>/sw` (`sw.exe` on Windows) must exist, and
running it with `version --json` and a 10-second timeout must exit 0, print one
JSON object, report the installed `VERSION`, and report the interface the
installed skills require. That interface is the `interface <n>` line in the
installed `specwright-pr/SKILL.md`: the line that holds only `interface <n>`
and nothing else, with `<n>` the number. A sentence that mentions an interface
inside a paragraph is not that line. For a tag whose skills carry no such line,
it is the `SW_INTERFACE=` value in the installed `scripts/sw-path.sh`. If the
file is missing, the command does not exit 0 in time, or the version or the
interface differs (as after a `main` install whose build was removed, or
whose workflow interface is not the one the skills require), add the line
`sw_mismatch: every branch, commit and finish step stops until a matching sw
is placed`, and say to use a tagged install, or, from a Specwright checkout,
the `CONTRIBUTING.md` bootstrap. Another version's `sw` never serves the
project: its steps stop with `sw_mismatch`. Report the install as not ready
while the check fails. Otherwise add no such warning. A matching binary already
placed gets no warning. A tagged install whose `sw-install` returned installed,
replaced or kept, with the check passing, gets no warning. A ref older than
0.37.0 never reaches this step (Step 3 stops it before any write), so it gets
no warning.
Report the OpenSpec version as recorded in Step 3: `OpenSpec <found> (pinned)`,
or `OpenSpec <found> (pinned <pin>, override)` after an override. If Step 1
recorded a missing PR prerequisite, add the line
`PR workflow not ready: <missing>` (for example
`PR workflow not ready: gh 2.48+`).
```

Treat `openspec/.specwright/packs.json` like `VERSION`: commit both or ignore both.

### Where the skills live

Step 2 offers the repo (`.claude/skills/`, `.agents/skills/`) or your user directory (`~/.claude/skills/`, `~/.agents/skills/`, and the matching agents directories), on every backend. Specwright installs where you choose and never refuses to run because of it. It is a warning, not a check: Specwright neither detects nor refuses a mixed install.

- **User level.** A user-level install is shared by every project on the machine: one Specwright version, and an update from one project updates all. In Claude Code a user-level `specwright-*` skill overrides an in-repo skill of the same name (personal over project), while agents resolve project over user. For Claude Code the skills' location is in effect a per-machine choice, and a mixed install runs the user-level skills.
- **Moving to an in-repo install.** Update the user-level `specwright-*` copies to 0.14.0 or newer, or remove them once no other project on the machine relies on them, then restart your agent sessions. An older user-level copy stops every `vcs.sh` call with `scripts_in_workspace` once in-repo copies exist; that message is the symptom. Such a copy is from before 0.14.0, a version that still had `vcs.sh`.
- **OpenSpec's own files.** OpenSpec's `openspec-*` skills and `/opsx:*` commands are always in the repo: `openspec init` has no user-level option.
- **GitButler.** Every applied branch shares the work tree, so a branch that changes in-repo skills changes them for every applied branch, and keeping them consistent is your job. An in-repo install leaves its files as unassigned changes in that tree: commit them through a GitButler branch of your own. The branch gate's "commit on main" offer does not apply there.

## ⚡ First Steps After Install

1. **Start a change** — `specwright-branch` checks for a clean `main` and creates the branch first:
   - `/opsx:propose <idea>` or `/opsx:ff <name>` writes every artifact in one go;
   - `/opsx:new <name>` scaffolds it, then `/opsx:continue` writes one artifact per run.
2. **Review gate:** the design triage picks LIGHT or FULL; FULL designs are reviewed in a fresh context (by a different model unless `review.cross_model: false`) before tasks can be written. Every claim a design makes about existing code cites the `path:line` that shows it, and claims nobody checked are listed as numbered `## Assumptions`. The review re-reads each citation (the LIGHT re-check does too), and tasks verify each assumption that work depends on before relying on it. Facts a later change must respect (invariants, deliberate gaps, rejected alternatives) are listed as `## Carried constraints`, each with one destination: a doc comment on the code, a spec requirement or an ADR. Apply writes each one there, the design review flags a fact left off the list, and the pre-ship review blocks ship when one is missing at its destination. Once a change is archived its design is history only: no step reads it again.
3. **Apply** with `/opsx:apply` — task groups go to `specwright-implementer` (`specwright-implementer-light` for a LIGHT change with `cheap_tier.enabled: true`), each verified task becomes its own commit.
   - **Pre-ship review:** once every task is committed, `specwright-review` has another model's CLI review the whole change (`review.order`, skipping the harness you run in; the `specwright-reviewer` agent when none is available). P0/P1 findings block: fix them (commits `address pre-ship review`; after two rounds it asks you) or waive them with your reason. `specwright-pr` ship and the local merge first check for a pass on the current head. Opt out with `review.preship: false`.
   - **BREAKING (0.2.0):** the pre-ship review is on by default, so apply ends with a review that can take up to `review.timeout` (20m). Set `review.preship: false` to keep the 0.1.x flow.
4. **PR mode:** the PR opens when apply finishes; `specwright-pr` **watch** handles reviews and CI, and once it is green offers to archive on the branch. Then merge on GitHub, or let watch merge it with `pr.merge: agent`.
5. **Archive** with `/opsx:archive` — `specwright-finish` merges locally or pushes the archive commit to the PR.

**Several agents at once?** Give each change its own `git worktree`: the skills switch branches in the checkout they run in.

**A whole project instead of one change?** Give the idea to `specwright-roadmap` **init**, then use **next** to start each change and **close** to finish a milestone: once every change of the milestone is done, **next** offers **close** instead of starting anything. Only the current milestone is split into changes, unless you explicitly agree a split for the next one; **close** then keeps it.

How much **init**, **close** and **pack** ask you is set by `project.decision_making` (`autonomous`, `important` or `all`; unset means `important`, the usual short interview). It is separate from the top-level `decision_making`, which the roadmap never reads. Tell the agent when a run starts ("decide yourself for this roadmap") to override the mode for that run only; `specwright.yaml` stays unchanged and the run records your words.

---

## 🧩 What's Inside

### Schema

[`schemas/specwright/`](schemas/specwright/schema.yaml) — forked from OpenSpec's `spec-driven` (1.16.0). `proposal` and `specs` stay close to upstream so archive and validate keep working.

| Artifact | Template | Adds over `spec-driven` |
|---|---|---|
| `proposal` | [proposal.md](schemas/specwright/templates/proposal.md) | Names its roadmap milestone when one exists |
| `specs` | [spec.md](schemas/specwright/templates/spec.md) | A failure/edge scenario per requirement; assertable THENs |
| `design` | [design.md](schemas/specwright/templates/design.md) | Six-trigger triage → `TIER: LIGHT \| FULL`; FULL sections; ADR rules |
| `review` | [review.md](schemas/specwright/templates/review.md) | **New.** Fresh-context, cross-model review; machine-readable `VERDICT:` |
| `tasks` | [tasks.md](schemas/specwright/templates/tasks.md) | Verdict precheck; scenario → test map; failing test first |

### Skills

| Skill | Activates on | Owns |
|---|---|---|
| [`specwright-branch`](skills/specwright-branch/SKILL.md) | New change (`/opsx:new`, `/opsx:propose`, `/opsx:ff`) | Clean-main gate, prefix, feature branch |
| [`specwright-commit`](skills/specwright-commit/SKILL.md) | Apply (`/opsx:apply`) | Planning commit, one commit per task or task group, end-of-apply check, PR handoff |
| [`specwright-finish`](skills/specwright-finish/SKILL.md) | Archive (`/opsx:archive`) | Archive commit, local merge or PR push, post-merge cleanup (a branch is deleted only when main or the merged PR's head holds its commits) |
| [`specwright-review`](skills/specwright-review/SKILL.md) | End of apply, ship and local merge (pre-ship); design reviews | `sw review`; validated route controls, effective receipts, pre-ship fixes and waivers — see the [brief](skills/specwright-review/references/brief.md) and [findings schema](skills/specwright-review/references/findings.schema.json). |
| [`specwright-pr`](skills/specwright-pr/SKILL.md) | "open a PR", "address review comments", "watch the PR" | `ship` / `feedback` / `watch` — see [description guide](skills/specwright-pr/references/description.md) and [feedback rubric](skills/specwright-pr/references/rubric.md) |
| [`specwright-debug`](skills/specwright-debug/SKILL.md) | Unexpected failures, bug reports, failing CI | Reproduce → trace → hypothesis → test-first fix; CI mode |
| [`specwright-release`](skills/specwright-release/SKILL.md) | "release", "tag", "publish v0.5.0" (with `release.enabled`); offered by finish, watch and roadmap close | `bump` (a tracked task) and `publish`: the annotated tag on the merged main commit and the optional GitHub release, via `sw release` |
| [`specwright-roadmap`](skills/specwright-roadmap/SKILL.md) | "plan this project", "what's next on the roadmap", "close the milestone" | `init` / `next` / `close` / `status` — templates for [strategy](skills/specwright-roadmap/references/strategy.md), [architecture](skills/specwright-roadmap/references/architecture.md), [roadmap](skills/specwright-roadmap/references/roadmap.md) |

#### Reviewer route controls

`review.routes` is validated before any CLI probe: malformed controls stop with `bad_route_setting`, known unsafe tools/flags with `route_setting_unsafe`. Unsupported YAML stops with `bad_settings`, naming its line. Extra `args` never override fixed isolation. Receipts expose effective `tools`, `disabled`, `extra_args` and `overlay`; OMP adds `policy_id` and `policy_sha256`.

| Route | Fixed/default controls | Optional settings |
|---|---|---|
| `codex` | Fixed read-only isolation; disables `apps`, `browser_use`, `browser_use_external`, `computer_use`, `in_app_browser`, `image_generation`, `memories`, `hooks`, `plugins`, `remote_plugin`, `tool_suggest`, `skill_search`, `skill_mcp_dependency_install`, `goals`, `sleep_tool` | `disable` adds features; `args` adds unprotected tokens. `profile`/`profiles` sources, `model_provider`/`model_providers` auth sources and out-of-sandbox `notify` commands are refused. No `tools` key. |
| `claude` | Restricted invocation; default tools `Read`, `Grep`, `Glob` | `tools` replaces the list (`[]` = none); `args` adds unprotected tokens. |
| `omp` | ≥18.19.0; default `read`, `grep`, `glob`; private session; memory/auto-learning/find/fetch disabled; exactly one fixed trusted local-target module, user extensions disabled; bare open-ended reads forced explicitly local | `tools` replaces the list (`[]` = none); `args` adds unprotected tokens. Network `fetch` is refused in settings and the hook, not only disabled by the overlay. Optional LSP permits nine read-only actions. The policy is not an OS sandbox: provider transport, filesystem mounts, trusted native tools and language servers are outside its lexical target boundary. |


### Agents

| Agent | Claude Code | OMP | Role |
|---|---|---|---|
| `specwright-implementer` | [`sonnet`](agents/claude/specwright-implementer.md) | [`pi/smol`](agents/omp/specwright-implementer.md) | Implements one task group test-first from a packet; never commits |
| `specwright-implementer-light` | [`haiku`](agents/claude/specwright-implementer-light.md) | [`pi/smol`](agents/omp/specwright-implementer-light.md) | The implementer word for word on a cheaper model; with `cheap_tier.enabled: true` it gets every group of a LIGHT change (ADR 0013). Never used for reviews, watch or FULL changes |
| `specwright-reviewer` | [`inherit`](agents/claude/specwright-reviewer.md) | [`pi/slow`](agents/omp/specwright-reviewer.md) | Read-only reviewer for design and pre-ship reviews; used when no reviewer CLI is available or `review.cross_model: false` |

Change the model in each file's `model:` line (Claude Code), or map the role aliases in `~/.omp/agent/config.yml` (OMP). On OMP both implementers use the `pi/smol` role, so the cheap tier changes nothing there unless you point the installed `specwright-implementer.md`'s `model:` line at a stronger role (remapping `pi/smol` would move both); update keeps that edit.

### Commands

These commands are in the `sw` binary (`sw --help` lists them); the skills run them as `<sw> ...`, defined in each skill. Review operations need git, no `gh` and no production Node interpreter.

| Command | Does |
|---|---|
| `sw as` | Runs a command as one GitHub login: pins the token per process, verifies it, and feeds it to both `gh` and `git push` (HTTPS to github.com only; SSH, prompts and inherited `http.extraHeader` auth are disabled inside it; run git from inside the target repo, since extraHeaders are scrubbed for the current repository only). Safe against a concurrent `gh auth switch`. `sw as --resolve` reads the active github.com account once (ignoring `GH_TOKEN`/`GITHUB_TOKEN`) and prints it as the run login. Inside, `GH_HOST` and the enterprise token variables are unset so `gh` targets github.com, and a github.com URL with userinfo (token, password or bare username) in a remote, push URL, `insteadOf` rule or argument is refused with exit 3, masked, before anything runs. |
| `sw pr snapshot` | One GraphQL call → the whole PR as JSON (checks, unresolved threads and resolved ones with an unanswered reviewer comment, unhandled or edited comments, stale `CHANGES_REQUESTED` verdicts, and a `complete` flag when a list was cut off). `--reviewer-config <file>` (written by `sw pr context` and `policy`) adds whether each reviewer has reported on the current head (`reported` / `waiting` / `timed_out`, with `by` and `evidence`), counting reports from the head's push, or from when a snapshot first saw the head if the push is not in the activity log (`head_cutoff` says which). Bodies cut for length are marked `clipped: true`; `--full <id>` prints one item whole. `--wait` polls in-process and wakes once (at once if the snapshot is already incomplete); one watcher per PR: a newer `--wait` on the same PR takes over and the older one exits 4, and a watcher's exit never ends a newer one's ownership; `--wait --until attention` (what watch runs) keeps waiting while the only change is check progress (a CI check still pending, `checks.ci_pending` above 0, no new failing check, merge state not `DIRTY`) and reports the skipped polls as `filtered`; `--logs` appends failed CI logs. |
| `sw pr` | The deterministic half of ship, feedback, watch and cleanup for one PR or a code/store pair: settings (`context`), PR discovery and linking, fix-round counts, the agent merge with read-back, and the cleanup plan; one JSON document per subcommand. `tier --code <dir>` reads `cheap_tier.enabled` for apply: `{"ok": true, "cheap_tier": bool}`, true only for a boolean true, anything else false with a `note`, and no other setting can change it. |
| `sw review` | All eight commands: `select`, `preflight`, `run`, `record`, `gate`, `waive`, `rounds`, `archive-only`. Native route controls are validated before probes; reviewer output is bounded in memory and fails closed (exit 3, never the next route). Machine-local records retain pre-port paths and fields, including Windows profile-home lookup rather than a customized Bash `HOME`, so existing gates and waivers still work. For state safety, record change names must be single directory components. Native batch launches reject held output pipes instead of returning incomplete output as success. Snapshots preserve safe cyclic symlinks when supported, with target-byte fallbacks otherwise. A missing or mismatched `sw` stops before any reviewer starts. |
| `sw pr reply` | Replies over REST, checks for a pending review, resolves the thread, optionally adds a 👍/👎 (`--react`), and marks the item handled on GitHub itself. `--rev` binds the reply to the revision that was judged: the item is read again first and nothing is posted if it changed (exit 5), and the marker counts only while the item keeps that revision. `react` answers a follow-up with a reaction only; `--waiting` marks a "waiting on owner" reply, which keeps the item listed; `resolve` retries only a failed resolution. A missing, unreadable or empty body file is refused before any GitHub call, and the temp file is removed on every exit. |

---

## ⚙️ Settings

`openspec/specwright.yaml` (template: [`templates/openspec/specwright.yaml`](templates/openspec/specwright.yaml)) — read by the skills; OpenSpec ignores it.

```yaml
finish: pr                      # local = merge to main locally, pr = GitHub PR
# main_branch: main             # omit to detect main / master
# commit_granularity: task      # task (default) = one commit per task; group = one commit per task group, evidence in Specwright-Task trailers; any other value stops apply
decision_making: autonomous     # autonomous (default; unset means autonomous) = the agent decides and shows a decision summary | important = important decisions are put to you with options | all = every decision is
# vcs: git                      # git (default) | jj = branch reads and writes go through a colocated Jujutsu repo | gitbutler = GitButler (code repo, finish: pr only); never inferred from .jj/ or .git/gitbutler/

github:
  login: my-bot-account         # pushes, PRs, replies; empty = the active gh account, resolved once per run and fenced
  review_request:
    body: "@codex review"       # posted once per new PR; empty = none
    login: my-account
    after_fixes: true           # post again after each pushed fix round (reviewers that only run when tagged)

review:
  cross_model: true             # false = design and pre-ship reviews use the specwright-reviewer agent, never another model's CLI
  order: [codex, claude, omp]   # reviewer CLIs tried in order; the harness you run in is skipped
  models: { omp: "@slow" }      # per route; omit = the CLI's default (OMP: @default)
  thinking: { codex: high }     # per route; omp only with a provider/id model
  timeout: 20m                  # a review still running after this fails
  max_diff_kb: 1024             # pre-ship input bound (code + store diff); over it no review runs
  preship: true                 # false = no pre-ship review and no ship / local-merge gate
  standing_rules: []            # committed code-repo-relative files; FULL change-design review only
  design_max_rounds: 3          # positive integer; owner checkpoint for unresolved FULL design rounds
  routes:
    codex: { disable: [], args: [] } # disables are additive; fixed isolation stays
    claude: { tools: [Read, Grep, Glob], args: [] }
    omp: { tools: [read, grep, glob], args: [] } # optional lsp remains read-only

project:                        # point at existing docs instead of duplicating them
  strategy: openspec/strategy.md
  architecture: openspec/architecture.md
  roadmap: openspec/roadmap.md
  adr_dir: docs/adr
  # decision_making: important    # roadmap init / close / pack only: autonomous | important (default; unset means important) | all; the top-level decision_making covers changes only

pr:
  validate: "npm test"          # must pass before every push; empty = none
  max_fix_rounds: 2             # address-review-feedback commits allowed per PR
  after_limit: ask              # at the limit: ask = reply "waiting on owner" and stop, issues = file each new finding as an issue and reply with the link, stop = like ask, without offering more rounds
  # FULL design reviews instead use review.design_max_rounds (above).
  react: true                   # 👍/👎 on every finding answered (right / wrong); default false
  poll_interval: 5m             # how often watch polls GitHub; default 5m
  review_after_archive: false   # true = re-request review on the archive head too; false = reviews of the head before it carry over
  settle: 5m                    # quiet window before a PR that is otherwise ready counts as ready; 1m to 1h, default 5m
  reviewers:                    # keyed by login, without [bot]; replaces github.review_request
    tagged-bot: { role: required, request: "@tagged-bot review" }   # example: a reviewer that runs only when tagged
    my-review-bot: { role: advisory, timeout: 15m }   # any other login; without request, it reviews on its own
  # request_as: my-account      # posts the requests; default review_request.login, else github.login, else the run login
  merge: user                   # user = you merge on GitHub; agent = watch merges a ready PR (finish: pr, a required reviewer)
  merge_method: merge           # agent merge: merge | squash | rebase
  delete_branch: true           # agent mode: delete the merged remote branch, only at the merged head

cheap_tier:
  enabled: false                # true = apply sends every group of a TIER: LIGHT change to specwright-implementer-light (cheaper model); FULL changes, reviews, watch and the orchestrator never change

release:                        # opt-in; refused with pr.merge_method: rebase
  enabled: false                # true = opt in
  auto: false                   # true = finish / watch publish without asking (never after a local merge)
  github_release: true          # also create the GitHub release from the tag's message
  tag: "v{version}"
  version_files:                # path or glob -> regex with one capture group; the first is the primary; every file must match once and agree
    VERSION: '^(\d+\.\d+\.\d+)$'
    package.json: '^  "version": "(\d+\.\d+\.\d+)",$'
```

**Jujutsu (`vcs: jj`).** Set `vcs: jj` in `openspec/specwright.yaml` to have the skills read the branch and write commits, branches, merges and deletes through [Jujutsu](https://github.com/jj-vcs/jj) instead of Git. Unset (or `git`) keeps the Git commands unchanged.

- **Setup.** Install jj 0.46 or newer, make the repository a colocated one (`jj git init --colocate`: `.git/` and `.jj/` at the same top level), and set `vcs: jj`. The choice is explicit and per repository; the presence of `.jj/` alone never switches the backend. A Git repository that also holds `.jj/` metadata stays on Git, and the branch gate says so once instead of stopping.
- **What the check stops on.** A missing or older jj, a repository without `.jj/`, and a jj workspace that is not colocated stop the skill before any write, naming the problem. Specwright does not convert a Git repository for you, and it never runs `jj git init` (no conversion; do it yourself and review the result).
- **What changes.** The change branch is a jj bookmark that sits on the parent of the working copy, so Git still sees an ordinary branch (`git log`, `git diff main...HEAD`, PR tooling). A commit takes only the files it names, the working copy keeps your other edits, and nothing is stashed: on a dirty working copy the gate and `specwright-debug` show the changed paths and ask you to commit or set the edits aside, never offering a stash. A local merge keeps the `merge: <change-name>` commit and deletes the bookmark locally; a push publishes only the change bookmark.
- **The one Git write.** The annotated release tag (`specwright-release`) is still created and pushed with Git. Every other write on a jj repository goes through jj, and reads such as `git log` stay as they are.
- **Your own jj skill is optional.** Specwright never installs a jj skill or a jj configuration. If you keep a personal one (for identity, trailers or push rules), it works beside Specwright; the skills do not need it.
- **Stores.** `planning_store.vcs` sets the store's backend on its own and does not inherit `vcs`: a jj code repository can have a Git store and the other way round. Each repository needs its own colocated checkout under the same rules.

**GitButler (`vcs: gitbutler`).** Set `vcs: gitbutler` to have the skills write through [GitButler](https://gitbutler.com)'s `but` CLI, so the change branch is applied beside the branches other agents or you have applied, instead of taking over the working tree. It is for the code repository only and needs `finish: pr`.

- **Setup.** Install `but` 0.23 or newer, open the repository with GitButler yourself (the app, or `but status`), and set `vcs: gitbutler` and `finish: pr`. Specwright never sets GitButler up or tears it down: a repo GitButler does not manage yet stops with `not_managed`, and a GitButler target other than your main branch stops with `target_mismatch`, before any write.
- **Only code repo, only PR.** `planning_store.vcs: gitbutler` stops with `unsupported_vcs` (a store accepts `git` or `jj`), and `vcs: gitbutler` without `finish: pr` (an absent `finish` counts as `local`) stops with `unsupported_combination`.
- **Git backend in a GitButler repo.** With `vcs` unset or `git`, a repo that GitButler manages stops with `gitbutler_workspace`, whatever HEAD is: set `vcs: gitbutler`, or take the repo out of GitButler first. The Git backend never writes in a GitButler workspace.
- **Commits and hooks.** Each commit names its paths and goes in with `but commit -b <branch>`, which runs no `pre-commit` or `commit-msg` hook; Specwright writes its trailers into the message itself, and `pr.validate` still runs before each push. A path another applied branch owns stops the commit with `path_owned_elsewhere`; edits you did not name stay uncommitted, and a file that two agents edit unassigned is committed whole.
- **GitButler's skill is offered, never installed silently.** Specwright ships no GitButler skill; GitButler's own is the tool guidance. With `vcs: gitbutler` the install prompt offers `but skill install --path <skills dir>/gitbutler` for each skills directory you chose and runs it only on your yes (a no changes nothing, and no directory you did not choose is touched). This is about GitButler's skill only: Specwright's own skills and agents go where you chose in Step 2, in the repo or at user level (see "Where the skills live"). The branch gate runs `but skill check` and adds a note, never a stop, when the skill is missing or out of date in the project.
- **What the skills do differently.** Commits, pushes and the PR are for the change branch alone, and cleanup pulls only when no other branch is applied (`pull_skipped` otherwise), so a merge that main already holds is read on the fetched main. `specwright-debug` never stashes on GitButler: it shows the changed paths and asks you to set your edits aside. A deferred archive's undo steps move the archive back, rewrites the main specs from `git cat-file --filters` and commits exactly those paths with `but commit -b <branch>`, with no Git write.
- **Limits.** With `core.autocrlf=true` (the Git for Windows default), GitButler checkouts can conflict on line endings: `but branch delete` has been seen failing, and `but pull` is untested.

Reviewers: `role` is `required` (default) or `advisory`, `timeout` defaults to 20m. Watch waits until every reviewer has reported on the head or timed out before a fix round, so one round covers all their findings. Ready needs every required reviewer to have reported; an advisory one stops blocking once it has reported or timed out. Once a PR meets every other ready condition, watch waits `pr.settle` (default 5m) with nothing new before it reports it ready.

Specwright names no review bot in `sw`. A reviewer counts as reported on the head by a review it submitted on the head commit, else by anything it posts after the push. Check runs never count on their own, because CI and a review action can share an app. For a bot whose finished review needs a more exact signal, add `report:` to its entry; with any of `sha_pattern`, `check` or `marker` set, only those (and a review on the head commit) count for that bot:

- `sha_pattern`: a JavaScript regular expression in Unicode mode (ADR 0030), case-sensitive, whose first group is the reviewed commit, 7 to 40 hex digits; it counts when that commit is the head.
- `check`: the exact name of the check run the bot completes; only a check run from the bot's own GitHub App (its slug is the login) counts, never a commit status or another app's check. That check stops holding up an advisory bot's PR once the bot has reported or timed out; every other pending check counts as CI.
- `marker`: literal text in a comment the bot edits in place; it counts when that comment was last edited after the push.
- `ignore`: a regular expression; comments and review bodies it matches never count, for bots that post an in-progress note first.

Write patterns in single quotes so backslashes stay as written. Three common shapes to copy, with placeholder logins:

```yaml
pr:
  reviewers:
    sha-bot:                    # posts "**Reviewed commit:** `<sha>`" when done
      role: required
      report:
        sha_pattern: 'Reviewed commit:\*\* `([0-9a-f]{7,40})`'
    check-bot:                  # finishes a check run named after itself
      role: advisory
      timeout: 15m
      report:
        check: 'Bot Code Review'
    marker-bot:                 # edits one walkthrough comment, first with an in-progress note
      role: advisory
      report:
        marker: '<!-- bot-walkthrough -->'
        ignore: 'Reviewing this PR|Code review in progress'
```

`report` is part of the merge policy (ADR 0020, 0022): a PR that changes it needs your yes before an agent merge, and a merge counts only reports judged under the default branch's rules. Each snapshot shows every reviewer's `by` (the rule that matched) and `evidence`, so watch can keep waiting for a bot whose only output reads as an announcement, until its timeout.

**Upgrading from 0.14.** `pr-snapshot.sh --reviewer login:role:seconds` is gone: the snapshot reads `--reviewer-config <file>`, which `sw pr context` and `policy` write from your settings. Bots that relied on the built-in rules of earlier versions get the generic rule above unless you add a `report:` block like those shown.

**Upgrading to 0.36.0.** Settings are now read by one YAML parser. After updating, find `yes` and `no` boolean values in `openspec/specwright.yaml` and rewrite them as `true` and `false`; a settings read stops naming the line until you do. A section of the wrong shape (a list or a plain value where a mapping goes) now stops the read too.

**Upgrading to 0.38.0.** The shipped bash scripts and `bounded.py` are gone: skills call `sw` directly, and neither bash nor Python is needed. Anything you scripted by hand that runs `vcs.sh` (or another retired script) must call `sw <command>` instead, such as `sw vcs`, `sw as` or `sw pr`. The undo-archive plan from `sw finish undo-archive-plan` lists `steps` and `after_rerun_steps` to run in order, in place of the bash `script` field. User-level skills of 0.38.0 stop in a project still on an older version and ask you to update that project first.

**Agent merge (0.4.0).** With `pr.merge: agent` and `finish: pr`, **watch** finishes the job you used to do by hand: once the PR is ready it archives the change without asking, waits for the archive head, merges the PR through GitHub's REST merge at the head it reported ready (a push in between makes GitHub refuse), reads the PR back, then cleans up: main pulled, the local branch deleted under the usual check, the remote branch deleted with `pr.delete_branch` while it is still at the merged head and no open PR is based on it, and the roadmap **next** or **close** offered (ADR 0009). It needs at least one `required` reviewer, else it reports ready and merges nothing. A refusal (branch protection, a merge queue, a disallowed method) stops with GitHub's message; Specwright never uses admin rights, auto-merge, a merge queue, another method or a review dismissal. GitHub records the run login as the merger. The default, `user`, keeps the earlier behaviour.

Since 0.13.0 the default branch decides (ADR 0020). Before it archives and before each merge request, watch reads `pr.merge`, `pr.merge_method`, `pr.delete_branch` and the reviewers (`pr.reviewers`, `planning_store.reviewers`) from GitHub, on the default branch and at the head it would merge, never from your checkout. It archives and merges without asking only when main has `pr.merge: agent`, the PR leaves those settings alone, and main's required reviewers reported on that head. A PR that changes them, including one that turns agent merge on for itself, gets the differences listed and is merged only after your yes for that head (asked only when the head has `pr.merge: agent` and its own required reviewers reported); otherwise watch reports ready and stops. When the policy cannot be read, watch merges nothing.

**Releases.** Opt-in with `release.enabled`. The version bump is a tracked task in the change's last task group (`sw release bump --to <version>`, checked with `sw release check`). After the change is on main, `publish` tags the merged main commit with an annotated `v<version>` tag, with notes taken from the archived changes, pushes only that tag and optionally creates the GitHub release. Tags are never moved, deleted or forced, and a rebase-merged release is refused. A store-backed project tags the code repo only.
- **BREAKING (0.35.0):** `release.version_files` patterns are JavaScript regexes in Unicode and multiline mode (ADR 0037), so rewrite any pattern with Python-only syntax (`(?P<name>`, `\A`, `\Z`, `(?i)`); such a pattern stops with `bad_version_files`. A line in `openspec/specwright.yaml` that the settings reader would misread (a tab indent, a key given twice) stops release with `bad_settings`, naming the line. Bump refuses a version file that is not valid UTF-8, before writing any file.

**GitHub identity (0.3.0).** Every `gh` call and every git fetch, pull and push to a github.com remote runs through `sw as` as one verified login (ADR 0008). With `github.login` empty, the first step you start resolves the active `gh` account once and hands it to every step it runs (ship, watch, feedback, archive, finish), so another agent's `gh auth switch` cannot redirect the run. A new request in a later session resolves again: if you switch `gh` accounts between sessions, set `github.login`. Remotes on other hosts are not fenced.
- **BREAKING:** with `github.login` empty, an environment that has only `GH_TOKEN` and no stored `gh` login (CI, containers, cloud agents) now stops before its first GitHub call; environment tokens never pick the login. Run `gh auth login --with-token` (and optionally set `github.login`).
- **BREAKING:** a github.com remote URL or `insteadOf` rule with userinfo (`https://user:token@github.com/...`, `https://<token>@github.com/...`, even a bare username) makes every fenced command exit 3, since git would use it before the fence's credential. Remove the userinfo; `gh auth login` supplies the credential. Nothing is rewritten for you.
- An SSH GitHub origin (`git@github.com:...`) cannot be fenced, so the branch gate's main refresh and roadmap status fall back to local refs and say so; use an HTTPS origin to keep them current.

`openspec/config.yaml` (template: [`templates/openspec/config.yaml`](templates/openspec/config.yaml)) carries the `context:` lines that make the git skills fire at the right phase.

---

## 📦 Packs

A pack is an optional bundle of skills, config lines and documents that ships in the Specwright release and adds to the core workflow without relaxing a gate. Its skills add domain knowledge; its lines reach the agent through `openspec instructions` for the artifacts, apply and archive; its documents are created once and then belong to the project.

To enable packs, list them under `packs:` in `openspec/specwright.yaml`, keyed by pack name, with optional document path overrides, then rerun the install prompt:

```yaml
packs:
  ui-prototyping: {}
```

A pack that requires another needs both listed; the install never enables one on its own. Removing a pack from `packs:` and rerunning the install removes its skills and lines and keeps its documents. In v1 packs are refused on a planning store and for skills directories outside the project (user-level). See [packs/README.md](packs/README.md).

| Pack | Requires | What it adds |
|---|---|---|
| `ui-prototyping` | none | `ui-prototyping-html`: clickable single-file HTML prototypes that settle an undecided layout or flow before it is specified, and visual identity as design tokens. Creates no document. |
| `gamedev` | `ui-prototyping` | Engine-neutral game development: `gamedev-design` (ideation, the brief, the GDD, genres, systems and balance, levels and encounters, game code checks), `gamedev-narrative`, `gamedev-ux` and `gamedev-playtest`. Creates `docs/game/gdd.md`, asks six init questions, and adds lines that make gameplay changes cite the GDD, state their frame budgets and end with a `[user]` playtest task. |
| `godot` | none | `godot-engine`: in-engine evidence (a log from a headless run, a screenshot from a windowed run or `--write-movie`), Resources as data, hand-editing `.tscn`/`.tres`, Theme and focus, pixel-art scaling, localization, test runners and the Godot 4 changes. Adds a design line for `.tres` tunables and an `[evidence]` task before any playtest. Usable with or without `gamedev`. |

## 🗄️ Stores

Specwright works with [OpenSpec stores](https://github.com/Fission-AI/OpenSpec) (with the pinned OpenSpec, 1.16.0): planning kept in a standalone repo registered on the machine (`openspec store setup` / `openspec store register <path> --id <id>`), while the code lives in its own repo.

- **Which root is used.** Every skill reads `root.path` from `openspec list --json` and never assumes `./openspec/`. OpenSpec resolves it from a `store: <id>` pointer in the code repo's `openspec/config.yaml`, the global `defaultStore` (`openspec config set defaultStore <id>`), or `--store <id>` on a command. Prefer the pointer or `defaultStore`: a `--store`-only session is not seen by a later session without the flag. A root in another git repository is a store; a root in the code repo (top level or a nested folder) is repo-local and works as before.
- **One change in progress per store per machine.** OpenSpec registers one checkout per store, so a store on another change's branch is busy: the branch gate stops and names that branch. Finish or archive that change first. The gate itself holds a lock (`specwright-gate.lock` in the store's git dir) while it creates both branches; a lock left by an interrupted session is removed only after you confirm no other session is in its gate.
- **The PR pair.** A store-backed change has the same branch name in both repos and, in `finish: pr`, up to two PRs: the store PR (planning) and the code PR, linked to each other. The expected PR set is the PRs the change can have: a planning-only change (no code commits, marked with `specwright-change.yaml`) expects only the store PR. Watch, feedback and cleanup act on the expected PRs only, and the roadmap counts a store-backed change done only with proof that its code is merged too, or that it is planning-only; otherwise it shows "planning merged, code pending".
- **Store settings.** `planning_store:` in the code repo's `openspec/specwright.yaml` holds the store's `vcs` (`git` default, or `jj` for a colocated store; see **Jujutsu** above), `main_branch`, `login`, `validate` (runs in `<root.path>`; `pr.validate` never runs in the store) and `reviewers`. Each but `vcs` defaults to the code repo's value; `vcs` is never inherited. See the commented block in the template.
- **Install.** The install prompt (through `sw update`, see below) puts the schema and the `context:` lines in `<root.path>/openspec/` only for the store's owner, and leaves those files uncommitted in the store for you to commit; `specwright.yaml`, skills and agents go in the code repo. The install never commits.
- **Owner and `STORE`.** `<root.path>/openspec/.specwright/STORE` records the store's schema `version:` and its `owner:` (the code repo's `origin` as `host/owner/repo`, else `path:<checkout>`). The first project to update a store without one claims it, and the report says so. The report gives this project's role: `none` (repo-local), `claim`, `owner` or `other`. Commit `STORE` in the store, as the install leaves it uncommitted.
- **Only the owner updates the store's schema.** Only the owner writes the store's schema and the `context:` lines of its `config.yaml`, and only while the store is free: on its main with nothing uncommitted except this update's staging. Another project installs its code-side files only (skills, agents, `VERSION`) and is refused, before any write, when its target differs from the store's recorded version in major or minor: the report names the store's version, its owner and the highest release tag with the store's major and minor version, and says the owner updates the store first.
- **Busy store.** When the store is on a change branch or dirty, a patch update whose staged schema is byte-identical to the installed one swaps the code side only (the report says the store schema was already current); any other update is refused, naming the store's branch: finish that change first. An owner's workflow update is also refused while another project's change is in flight in the store, naming each.
- **Transferring ownership.** There is no command: change `owner:` in `STORE` by a manual commit in the store, then the new owner runs the update.
- **An interrupted store swap** holds the store's gate lock (`change: specwright-update <from> -> <to>`, with its checkout) until the update is rerun from that checkout, which resumes or rolls back and releases it. Another project's change gate stops, names that checkout and does not offer to remove the lock. The gate also compares the project's installed version with the store's record before it creates a branch.
- **References.** Stores listed under `references:` in a project's `config.yaml` are read-only: the skills may read their specs (`openspec context --json`) but never branch, commit or push there. An unresolved reference is named in the report, and the work goes on.
- **`Feedback-Round` trailer.** Review-fix commits now carry a `Feedback-Round: <n>` trailer, in repo-local projects too, so the round limit counts the same in one repo or two. Branches from before this count their `address review feedback` commits as before.
- **`cleanup-plan` contract (0.1.13).** `pr-pair.sh cleanup-plan` no longer returns `force_delete` or `force_delete_allowed`. Each repo's plan now lists `checkout`, `pull`, a `branch-check` command and `delete: ["git", "branch", "-D", <branch>]`; run the delete only when `branch-check` answers `delete: true` (the branch tip is on main, or is the merged PR's head or an ancestor of it). A script that read the removed fields must call `branch-check` instead.

---

## 📖 Behavior Reference

<details>
<summary><b>Design triage</b> — which changes get the full architecture treatment</summary>

| Trigger | Applies when the change… |
|---|---|
| T1 Components | adds a component, or touches 3+ with directed relationships |
| T2 State | adds or changes persistent state, caches, or a 3+ state machine |
| T3 Concurrency | adds background work, workers/isolates, async pipelines, retries |
| T4 Boundaries | touches a data format, migration, shared interface, IPC or external system |
| T5 Volume | handles data or work that can grow without a fixed bound |
| T6 Risk | involves security, money, data loss, or unrecoverable user data |

No trigger → **LIGHT** (triage, context, decisions). Any trigger → **FULL**: diagrams, state & ownership, failure & visibility, resource bounds, flow & state gaps, mechanism ledger. When unsure, a trigger applies.
</details>

<details>
<summary><b>Review verdicts</b></summary>

| Verdict | Means |
|---|---|
| `SKIPPED_LIGHT` | LIGHT tier; triage re-checked, no review needed |
| `APPROVE` | Tasks may be written |
| `APPROVE_WITH_CHANGES` | Apply the listed changes; tasks wait for `CHANGES_APPLIED: yes` |
| `REVISE` | Fix and re-review until the configured owner checkpoint; the verdict stays in force there |
| `USER_OVERRIDE` | Historical change-design override or a separate roadmap baseline disposition; not issued by the change-design checkpoint |
| `DEFERRED` | The user declared a FULL-tier change a parking change that is never applied; `Deferred to:` names where its parts get reviewed. Tasks may be written; apply refuses it |
| `WAIVED` | The user explicitly decided to apply with no design review; their quoted words and `No design review ran.` are recorded. The pre-ship review still runs |

The agent never offers `DEFERRED` or `WAIVED`. A project that recorded a deferral as `USER_OVERRIDE` may rewrite it as `DEFERRED`.

A verdict covers only what was reviewed; the existing Required Changes confirmation and Release Notes exemption are unchanged.
</details>

### Standing requirements and design checkpoint

Create a rules file for your project, such as `rules/review-criteria.md`. Commit it to the code branch and list its repository-relative path under `review.standing_rules` in the **code repository's** `openspec/specwright.yaml`:

```yaml
review:
  standing_rules:
    - rules/review-criteria.md
  design_max_rounds: 3
```

Rules must be UTF-8 text in regular Git blobs, not links. Paths use `/` and are relative to the code repo root. The FULL brief includes the whole text in declaration order (up to 32 paths and 256 KiB total; it stops rather than truncating), including instructions to check existing tests the design preserves. These files are sent to the selected reviewer; do not list secrets or unrelated policy. Empty or omitted `standing_rules` adds no criteria to the brief. LIGHT, roadmap baseline and pre-ship do not use this section.

`review.design_max_rounds` defaults to **3** for projects that set nothing, replacing the old two-consecutive-`REVISE` change-design escalation. At the limit, the report shows open findings and repairs, then waits for the owner to authorize one scoped pass, record a scope change with a reason, or stop. None of those choices grants approval. `pr.max_fix_rounds` and `pr.after_limit` still govern PR feedback only; their defaults and project values are unchanged.

<details>
<summary><b>Branch prefixes and commit messages</b></summary>

| Change name starts with | Branch |
|---|---|
| `add`, `feat`, `feature`, `implement`, `introduce` | `feat/` |
| `fix`, `bugfix`, `hotfix`, `patch`, `resolve` | `bugfix/` |
| `refactor`, `restructure`, `cleanup` | `refactor/` |
| `docs`, `doc`, `document` | `docs/` |
| `chore`, `bump`, `deps`, `ci`, `build` | `chore/` |
| anything else | `feat/` |

| When | Message |
|---|---|
| Apply start | `<type>(<change>): add planning artifacts` (`<type>` = branch prefix, `bugfix` → `fix`) |
| Each task | `<type>(<change>): task X.Y <task text>` (≤ 72 chars) |
| Each task group (`commit_granularity: group`) | `<type>(<change>): group N <group heading>` (≤ 72 chars), plus one `Specwright-Task: X.Y` trailer per covered task, in the final trailer block before `Co-authored-by` |
| User ticks with no agent work pending | `<type>(<change>): record user checks <ids>` (≤ 72 chars); every commit that stages `tasks.md` carries a `Specwright-User-Task: X.Y` trailer per user tick it brings in |
| After archive | `<type>(<change>): archive change` |
| Local merge | `merge: <change>` |

Files are always staged by name — never `git add -A`, never all of `openspec/` — and pre-existing untracked files are left alone.
</details>

<details>
<summary><b>PR modes</b></summary>

| Mode | Does | Never |
|---|---|---|
| `ship` | Before the change's first PR, check for a pre-ship review pass on the head; push every repo of the change (store first), then create/update the PRs with `--body-file`, post the review request | Push the default branch; open or update a PR when a push failed |
| `feedback` | One snapshot → judge all items → fix → validate once → one commit → one reply (and 👍/👎) per finding, resolve; acknowledgement follow-ups get a reaction only (and resolve the thread if it was still open) | Resolve needs-human threads; go past `max_fix_rounds` |
| `watch` | Background wait → wait for every reviewer on the head → feedback first → ignore CI for stale heads → fix all failing checks in one pass → at ready, offer the archive on the branch (an archive-only head gets no new review requests unless `pr.review_after_archive: true`); report stale `CHANGES_REQUESTED` verdicts; with `pr.merge: agent` on the default branch, archive without asking, merge at the ready head and clean up; a PR that changes the merge policy needs your yes (ADR 0020) | Merge (except the opt-in agent merge), rebase, force-push, approve workflow runs, dismiss reviews |
</details>

<details>
<summary><b>Tasks only you can tick</b> — playtests, sign-offs, checks against a real system</summary>

Mark a task as yours with `[user]` right after its id, lowercase: `- [ ] 4.3 [user] Play the first level and judge the jump`. An `[evidence]` task is the agent's: it saves what your check needs to one file under the change's `evidence/` folder (`- [ ] 4.2 [evidence] Save the build note → evidence/build.md`), ticked only once that file is committed (ADR 0024).

- **Apply** never ticks, implements or delegates a `[user]` task. It skips it, lists it as waiting on you, and a group commit does not wait for it. Telling the agent in chat that the check passed is not enough: it asks you to tick the box.
- **Tick it yourself** in `tasks.md`. The agent commits your tick with a `Specwright-User-Task` trailer.
- **Verify and archive** wait: verify reports the task as waiting on you, and archive moves nothing while any `[user]` task is unticked.
- **The agent merge** (`pr.merge: agent`) reads `tasks.md` at the ready head before it archives and before every merge request, reports `ready, waiting on the user: <ids>` and merges nothing until your tick is pushed and the new head is ready.
</details>

---

## 🧪 Evals

[`evals/git-workflow/`](evals/git-workflow/) holds scripted evals for the git skills: [`fixtures.py`](evals/git-workflow/fixtures.py) builds scratch repos, [`evals.json`](evals/git-workflow/evals.json) lists the cases, and [`grade.py`](evals/git-workflow/grade.py) checks the resulting git state. Run with [skill-creator](https://github.com/anthropics/skills) (with-skill vs. baseline runs), then `python evals/git-workflow/grade.py <iteration-dir>`.

**Stress tier.** Evals marked `"stress"` in `evals.json` (`watch`, `light-apply`, `implementer`) are a wording diagnostic: run them through skill-creator twice, with the executor on the default model (config `base`) and on Haiku (config `haiku`), grade with `python evals/git-workflow/grade.py <iteration-dir>`, then compare with `python evals/git-workflow/tiers.py <iteration-dir> --base base --cheap haiku`. It prints each stress eval's pass rate per configuration and names every difference (with the assertions that pass in one configuration only) and every missing grading; exit 0 only when nothing differs. Where Haiku misses a rule, the skill text is vague: fix the wording (never with model-specific text) and re-run. It is not a configuration Specwright ships (Haiku never runs the orchestrator) and not a CI gate. Results are recorded in [`evals/git-workflow/stress.md`](evals/git-workflow/stress.md).

Store evals (`eval-store-*`) need two repos, so the fixture is a directory, not a repo: `code/` is the project, `store/` is its OpenSpec store. The fixture also writes `eval.env`. The agent under test must run `source <repo>/eval.env` first and work from `<repo>/code`. The file points the OpenSpec registry and config (`XDG_DATA_HOME`, `XDG_CONFIG_HOME`) and Specwright's watch state (`SPECWRIGHT_STATE_DIR`) at the run directory, and puts a fake `gh` first on `PATH`. Your own registry and state are never touched. The fake `gh` ([`evals/fakes/gh.py`](evals/fakes/gh.py)) keeps its state in `gh-state.json` and logs every call to `gh-log.jsonl`; `grade.py` reads both repos and that log.

CI ([`.github/workflows/evals.yml`](.github/workflows/evals.yml)) runs every suite on Linux, Windows and macOS for each pull request, so do not run a whole suite locally. Run only the test module you are writing (`python -m unittest evals/<suite>/test_<x>.py`), and after adding a tracked file the map test (`python -m unittest evals/runner/test_suite_map.py`). The suites cover the fake `gh` (`evals/pr-pair`), the reviewer routes (`evals/review-routes`, against fake `codex`, `claude` and `omp` executables), `sw release` (`evals/release`, against scratch repos and the fake `gh`) and `sw update` (`evals/update`, run directly: the staged swap, journal and recovery, against scratch repos). At a milestone close, rely on a green `gh workflow run evals.yml --ref main` run on the closing head of `main`. [`evals/suites.json`](evals/suites.json) maps each tracked path to its suites. `evals/run.py` runs the suites in parallel, one process per test file; CI uses it. [`evals/timings.md`](evals/timings.md) records the suite wall times before and after the runner.

To check that delegated agents can load skills, start a new session after the install, dispatch `specwright-implementer` (and `specwright-implementer-light`, if you use the cheap tier) with a small packet that names one installed skill (with its `SKILL.md` path) and look for its `Skill` call before any edit. A session that was already running before the install still has the old agent definitions, so a check there proves nothing: start a new session and run it again.

---

## 🔧 Manual Installation

1. `git clone --depth 1 https://github.com/sh1ny/specwright.git /tmp/specwright`
2. Copy `skills/specwright-*` into your agent's skills directory, and `agents/claude/*` into `.claude/agents/` and/or `agents/omp/*` into `.omp/agents/`.
3. Copy `schemas/specwright/` to `openspec/schemas/specwright/` and `VERSION` to `openspec/.specwright/VERSION`.
4. Set `schema: specwright` and append the `context:` lines from [`templates/openspec/config.yaml`](templates/openspec/config.yaml) to your `openspec/config.yaml`; copy [`templates/openspec/specwright.yaml`](templates/openspec/specwright.yaml) to `openspec/specwright.yaml` and fill it in.
5. `openspec schema validate specwright`, then restart your agent.

## 🛠️ Contributing

Specwright is developed with Specwright. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, the source vs. installed layout, conventions and releases.

## 🗑️ Uninstall

1. Delete the `specwright-*` skill directories and the two `specwright-*` agent files.
2. Delete `openspec/schemas/specwright/`, `openspec/.specwright/` and `openspec/specwright.yaml`.
3. Remove the Specwright lines from `openspec/config.yaml` and set `schema:` back to `spec-driven`.
4. Restart your agent.

## 💡 Credits

- Schema forked from OpenSpec's `spec-driven` ([MIT](schemas/specwright/LICENSE-OpenSpec)).
- Planning and PR workflow ideas from [Compound Engineering](https://github.com/EveryInc/compound-engineering-plugin).
- Review gate and test plan from the [anvil](https://github.com/jikkujoyce/openspec-schemas) schema; ADRs from [intent-driven](https://github.com/intent-driven-dev/openspec-schemas).
- Pre-ship reviewer brief and findings format from compound-engineering's [`ce-code-review`](https://github.com/EveryInc/compound-engineering-plugin) and oh-my-pi's [`reviewer.md`](https://github.com/can1357/oh-my-pi).
- Git workflow from [openspec-git-flow](https://github.com/sh1ny/openspec-git-flow), which Specwright replaces.
