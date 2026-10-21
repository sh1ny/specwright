# pr-descriptions Specification

## Purpose
Makes the issues a PR says it fixes the issues GitHub closes when it merges: closing references are written one per issue, checked against GitHub's closing list after ship, and any intended issue still open after the merge is closed at cleanup.

## Requirements

### Requirement: One closing keyword per issue
A PR description written by Specwright SHALL give each issue the PR fully resolves its own closing keyword on its own line (`Fixes #N`). An issue the PR does not fully resolve SHALL be named with `Related: #N`. In a store-backed change, closing lines SHALL go on the PR in the repository that holds the issues; when no PR is expected there, the existing PR SHALL carry them as `Fixes <owner>/<repo>#N`.

#### Scenario: PR fixing three issues
- **WHEN** ship writes the description of a PR that fully resolves issues 21, 24 and 43
- **THEN** the description has the three lines `Fixes #21`, `Fixes #24` and `Fixes #43`, and no line names two issues after one keyword

#### Scenario: Partly resolved issue
- **WHEN** the PR resolves issue 21 fully and issue 52 only in part
- **THEN** the description has `Fixes #21` and `Related: #52`, and no closing keyword names 52

#### Scenario: Planning-only store-backed change
- **WHEN** a planning-only store-backed change fully resolves issue 21 of the code repository, so only the store PR exists
- **THEN** the store PR's description has `Fixes <code owner>/<code repo>#21` on its own line

### Requirement: Closing references are checked after ship
After ship creates or finds a PR, Specwright SHALL compare the issues its description's closing lines name with the issues GitHub reports it will close. On a PR ship just created, a mismatch SHALL be fixed by rewriting the description with one keyword per issue and checked once more. On an existing PR, a mismatch SHALL be reported and the description left unchanged unless the user asks.

#### Scenario: Description matches
- **WHEN** ship creates a PR whose description has `Fixes #21` and `Fixes #24`, and GitHub reports issues 21 and 24 as closing
- **THEN** the check reports a match, and the description is not edited

#### Scenario: Several issues after one keyword on a new PR
- **WHEN** ship creates a PR whose description has `Fixes #24, #21, #43`, and GitHub reports only issue 24 as closing
- **THEN** the check names 21 and 43 as missing, the description is rewritten with one `Fixes` line per issue, and a second check reports a match

#### Scenario: Mismatch on an existing PR
- **WHEN** ship finds an existing PR whose description names issue 43 on a closing line and GitHub does not report 43 as closing
- **THEN** ship reports 43 as missing, leaves the description unchanged, and asks the user whether to rewrite it

#### Scenario: Still missing after the rewrite
- **WHEN** after the rewrite GitHub still does not report an issue named on a closing line, for example because the issue number does not exist
- **THEN** ship stops, names that issue, and does not report the PR as ready

#### Scenario: Issue linked by hand only
- **WHEN** an existing PR's closing lines name issue 21, and GitHub reports issues 21 and 30 as closing because 30 was linked in the sidebar
- **THEN** the check reports a match with 30 listed as extra, and ship asks nothing

#### Scenario: Closing list cannot be read
- **WHEN** the GitHub lookup for the PR's closing issues fails
- **THEN** the check exits with GitHub state unknown, and ship reports the check as not done rather than as a match

#### Scenario: Closing keyword inside code
- **WHEN** a description shows ``` ``Fixes #21`` ``` as an inline code example, or inside a fenced block
- **THEN** the check does not count issue 21 as intended

#### Scenario: Numbered closing line
- **WHEN** a description has the line `1. Fixes #24, #21, #43`, and GitHub reports only issue 24 as closing
- **THEN** the check names 21 and 43 as missing

#### Scenario: Unmatched backtick
- **WHEN** a description has the line ``Fixes #21 (see `notes)`` whose single backtick is never closed
- **THEN** the backtick is literal text, and the check counts issue 21 as intended

### Requirement: Closing references need the default branch
When a PR's base is not its repository's default branch, the check SHALL report that GitHub will not close the issues its closing lines name. Ship SHALL NOT rewrite the description and SHALL NOT stop for that reason.

#### Scenario: PR into a branch other than the default
- **WHEN** ship creates a PR into a branch other than the repository's default branch, and its description has `Fixes #21`
- **THEN** the check reports that the base is not the default branch, the description is not edited, and ship reports that #21 will not be closed by this PR

#### Scenario: Default branch cannot be read
- **WHEN** the lookup of the repository's default branch fails
- **THEN** the check exits with GitHub state unknown, and ship reports the check as not done

### Requirement: Issues a merged PR left open are closed at cleanup
When Specwright cleans up after a PR merged into its repository's default branch, it SHALL read the issues the PR's closing lines name in the change's repositories and close each confirmed one that is open with no close since the merge, with a comment naming the PR, as the issue's repository's identity. Issues outside the change's repositories, and issues a person reopened after the merge, SHALL be reported and not closed. Issues named only by `Related:` SHALL NOT be closed.

#### Scenario: Merged PR left an issue open
- **WHEN** a merged PR's closing lines name issues 21 and 24, issue 21 is closed and issue 24 is still open
- **THEN** cleanup asks the user to confirm closing 24, then closes it with a comment naming the PR, and does not touch 21

#### Scenario: Fence-like line inside a fenced block
- **WHEN** a merged PR's description has a fenced block holding a line of three backticks followed by other text, then `Fixes #52`, and issue 52 is open
- **THEN** the block is not closed by that line, 52 is not an intended issue, and cleanup does not close it

#### Scenario: Code span inside a word
- **WHEN** a merged PR's description has the text ``Fi`x`xes #52``, and issue 52 is open
- **THEN** 52 is not an intended issue

#### Scenario: Comment opener inside a code span
- **WHEN** a description has the line ``Shows `<!--` in the docs``, followed by the line `Fixes #21`
- **THEN** 21 is an intended issue

#### Scenario: Every intended issue closed
- **WHEN** every issue a merged PR's closing lines name is closed
- **THEN** cleanup closes nothing and posts no comment

#### Scenario: Related issue still open
- **WHEN** a merged PR's description has `Related: #52`, and issue 52 is open
- **THEN** cleanup does not close 52

#### Scenario: Related reference on a closing line
- **WHEN** a merged PR's description has the line `Fixes #21; Related: #52`, issue 21 is closed and issue 52 is open
- **THEN** 52 is not an intended issue, and cleanup does not close it

#### Scenario: Closing line without a closing list
- **WHEN** a merged PR's description has the line `Fixes the crash; Related: #52`, and issue 52 is open
- **THEN** 52 is not an intended issue, and cleanup does not close it

#### Scenario: Closing keyword hidden from the rendered description
- **WHEN** a merged PR's description shows `Fixes #52` only in an indented code block (also one directly after a heading), a code span that continues onto the next line, or an HTML comment, and issue 52 is open
- **THEN** 52 is not an intended issue, and cleanup does not close it

#### Scenario: Issue in another repository
- **WHEN** a merged PR's closing line names `other/tool#5`, which is not one of the change's repositories
- **THEN** cleanup does not read or close that issue, and reports it as outside the change

#### Scenario: PR not merged
- **WHEN** cleanup runs for a PR that was closed without merging
- **THEN** no issue is closed

#### Scenario: PR into a branch other than the default, at cleanup
- **WHEN** cleanup runs for a merged PR whose base is not its repository's default branch, and its closing lines name open issue 21
- **THEN** cleanup does not close 21 and reports that it stays open until the fix reaches the default branch

#### Scenario: Issue reopened after it was closed
- **WHEN** issue 24, named on a merged PR's closing line, was closed at or after the merge and then reopened by a person
- **THEN** cleanup does not close 24 again and reports it as reopened

#### Scenario: Issue closed and reopened before the merge
- **WHEN** issue 24, named on a merged PR's closing line, was closed and reopened before the PR merged, and is still open
- **THEN** cleanup lists 24 as open and asks the user to confirm closing it

#### Scenario: Closing an issue fails
- **WHEN** cleanup closes issue 21 and then fails to close issue 24
- **THEN** cleanup reports 21 as closed and 24 as still open, continues its branch cleanup, and a later cleanup asks about and closes only 24

#### Scenario: Issue state cannot be read
- **WHEN** the lookup of the PR, or of an intended issue in the change's repositories, fails
- **THEN** the check exits with GitHub state unknown, cleanup reports the backstop as not done, closes nothing, and continues its branch cleanup

### Requirement: Cleanup asks before closing issues
Before cleanup closes any issue, it SHALL list the open intended issues of the change's merged PRs and ask the user once to confirm them. A declined issue SHALL stay open and be reported.

#### Scenario: User declines a close
- **WHEN** cleanup lists open issue 24 for closing and the user declines it
- **THEN** 24 stays open and is reported as left open

### Requirement: The description lists spec amendments and open review findings
A PR description written by Specwright SHALL list each spec amendment made in response to the pre-ship review (each commit with an `Amendment:` trailer, with its class: clarification or user-approved behaviour change), each P2 or P3 pre-ship finding left unfixed, and each P0 or P1 finding the user waived, with the user's reason. A change with none of these SHALL have no such section.

#### Scenario: Clarification after pre-ship review
- **WHEN** the change has one `<type>(<change>): amend specs` commit with the trailer `Amendment: clarification`
- **THEN** the description's spec amendments section names that commit and says `clarification`

#### Scenario: Open P3 finding
- **WHEN** the passing pre-ship review left a P3 finding unfixed
- **THEN** the description lists that finding with its file and summary

#### Scenario: Waived P1 finding
- **WHEN** the user waived P1 finding `f2` with the reason `out of scope, tracked as #90`
- **THEN** the description lists `f2` as waived with that reason

#### Scenario: Drift amendment during apply
- **WHEN** the change's only `amend specs` commit was made during apply under the drift rule and has no `Amendment:` trailer
- **THEN** the description lists no spec amendment

#### Scenario: Nothing to list
- **WHEN** the change has no commit with an `Amendment:` trailer, no unfixed P2 or P3 finding and no waived finding
- **THEN** the description has no spec amendments or open findings section

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
