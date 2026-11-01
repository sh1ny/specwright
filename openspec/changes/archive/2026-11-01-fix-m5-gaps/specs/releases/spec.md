# Spec Delta

## ADDED Requirements

### Requirement: The release skill names the proposal in the planning repo
`specwright-release` SHALL tell the bump task to check the section with `release.sh notes --proposal <proposal.md>`. It SHALL say that `<proposal.md>` is the change's proposal in the planning repo: in the store when the project is store-backed. No Specwright skill text SHALL pass `--proposal` a path fixed under the code checkout's `openspec/`.

#### Scenario: Store-backed project
- **WHEN** an agent follows the release skill's notes check for change `add-a` in a project whose planning lives in a store at `../plans`
- **THEN** the command it is told to run names the proposal as `<proposal.md>`, the skill says that file is in the store, and the skill's notes section does not contain `openspec/changes/<change>/proposal.md`

#### Scenario: A hardcoded path comes back
- **WHEN** any `skills/*/SKILL.md` contains `--proposal openspec/`
- **THEN** the release skill-text test fails and names that file
