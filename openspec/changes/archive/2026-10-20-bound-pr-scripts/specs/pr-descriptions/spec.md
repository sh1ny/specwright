# Spec Delta

## ADDED Requirements

### Requirement: Closing references are read from GitHub's rendering
The closing-reference check at ship and the issue backstop at cleanup SHALL read a PR description's closing lines from GitHub's own GFM rendering of it, in the PR's repository as context. Text GitHub renders as code SHALL NOT be read, and text it renders as prose SHALL be. When the rendering cannot be read, the check SHALL exit with GitHub state unknown.

#### Scenario: Continued list paragraph
- **WHEN** a description has the line `- Notes`, a blank line, then `    Fixes #21` indented four columns, which GitHub renders as a paragraph of the list item
- **THEN** 21 is an intended issue

#### Scenario: Quote-marked fence line inside a fence
- **WHEN** a description opens a fence outside any blockquote, then has the lines `> ```` and `Fixes #12`, then closes the fence, so GitHub renders `Fixes #12` as code
- **THEN** 12 is not an intended issue

#### Scenario: Code span inside a word, rendered
- **WHEN** a description has the text ``Fi`x`xes #52``, which GitHub renders with `x` as code inside the word
- **THEN** the text on either side of the code does not join into `Fixes`, and 52 is not an intended issue

#### Scenario: Reference on the next source line
- **WHEN** a description has the line `Fixes #21` followed directly by the line `#22 is unrelated` in the same paragraph
- **THEN** 21 is an intended issue and 22 is not

#### Scenario: Issue URL on a closing line
- **WHEN** a PR in `acme/widget` has the description line `Fixes https://github.com/acme/widget/issues/21`
- **THEN** issue 21 of `acme/widget` is an intended issue

#### Scenario: Reference to another repository
- **WHEN** a merged PR in `acme/widget` has the description line `Fixes other/tool#5`, and `other/tool` is not one of the change's repositories
- **THEN** `other/tool#5` is reported as outside the change, and cleanup neither reads nor closes it

#### Scenario: Rendering fails
- **WHEN** the GitHub call that renders the description fails, or passes its deadline or size bound
- **THEN** the check exits 3 with GitHub state unknown, ship reports the check as not done, and cleanup closes no issue
