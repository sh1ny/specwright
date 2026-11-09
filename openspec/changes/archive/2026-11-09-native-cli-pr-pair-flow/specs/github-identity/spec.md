## MODIFIED Requirements

### Requirement: The fence runs in the project's sw
`as.sh` SHALL retain its path and existing arguments and add one optional leading `--project <code-checkout>` prefix for exact-version binary selection. The prefix SHALL be consumed before the existing handoff. Without it, discovery SHALL walk from cwd to the first .git entry as before. Selection SHALL NOT change cwd, target repo, login or stdin. All calls, including --resolve, SHALL still run sw as through the shared resolver with no fallback fence implementation.

#### Scenario: Fenced gh call with a matching sw
- **WHEN** the project's VERSION reads 0.28.0, the resolver finds a matching sw 0.28.0, sh1ny has a gh credential, and as.sh sh1ny gh api user --jq .login runs inside the project
- **THEN** stdout is sh1ny, exit status is 0, and gh saw GH_TOKEN set to sh1ny's token

#### Scenario: Resolve through sw
- **WHEN** the active github.com account is KintsugiBot and as.sh --resolve runs
- **THEN** stdout is exactly KintsugiBot and a newline, and exit status is 0

#### Scenario: A refusal keeps its exit status
- **WHEN** as.sh sh1ny git push runs in a repo whose origin push URL is https://tok@github.com/o/r.git
- **THEN** exit status is 3, stderr names the remote with userinfo masked as ***, and git push did not run

#### Scenario: Fenced store call selects the code project
- **WHEN** a store without VERSION runs as.sh --project <code> store-bot git credential fill with caller input and a matching code-project binary
- **THEN** the command starts in the store, receives the same input, and uses store-bot's verified token; project selection is not forwarded as a login or command argument

#### Scenario: Selected project does not change target validation
- **WHEN** the selected code project has safe remotes but the caller's store has a github.com remote containing credentials
- **THEN** the fence refuses before the command runs, naming the store remote with credentials masked

#### Scenario: Missing selected binary refuses without fallback
- **WHEN** as.sh --project <code> names a project with no usable matching sw, but cwd or PATH offers another binary
- **THEN** it returns sw_missing with exit 1, without identity lookup or command execution, and does not use the other binary

#### Scenario: Malformed fence project prefix is refused
- **WHEN** the leading --project prefix lacks a nonempty value or is repeated as a leading selector
- **THEN** after the existing Python prerequisite check, as.sh exits 2 with usage stderr before resolution, credential lookup or command execution
