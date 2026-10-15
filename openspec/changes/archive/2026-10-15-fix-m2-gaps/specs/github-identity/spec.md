# Spec Delta

## ADDED Requirements

### Requirement: The trailing-dot host is github.com
Every github.com test of the fence and the PR scripts SHALL treat `github.com.` (the absolute DNS name, in any letter case) as github.com: the userinfo refusal, the credential helper, and the split between fenced GitHub remotes and unfenced other remotes. A host that only begins with `github.com.` (such as `github.com.example.org`) SHALL NOT be github.com.

#### Scenario: Token in a trailing-dot URL
- **WHEN** `origin` is `https://user:tok@github.com./o/r.git` and a fenced `git fetch origin main` runs
- **THEN** the fence exits 3 before any request, with `tok` masked, and the remote URL is unchanged

#### Scenario: Trailing-dot URL argument or rewrite
- **WHEN** a fenced git command gets the argument `https://u:tok@GitHub.COM./o/r.git`, or a rule `url.https://u:tok@github.com./.insteadOf` applies
- **THEN** the fence exits 3 before the command runs

#### Scenario: Credential-free trailing-dot URL
- **WHEN** a fenced git command asks git's credential system for protocol `https` and host `github.com.`
- **THEN** git receives username `x-access-token` and the run login's verified token

#### Scenario: Look-alike host
- **WHEN** a fenced git command asks the credential helper for host `github.com.example.org`, or a remote is `https://u:tok@github.com.example.org/o/r.git`
- **THEN** the helper gives no credential, and the URL is not refused as a github.com URL

#### Scenario: Trailing-dot store remote
- **WHEN** a store's fetch URL is `https://github.com./o/s.git` and `pr-pair.sh` reads it
- **THEN** the read runs fenced as a GitHub remote, never with the user's unfenced git

### Requirement: Unfenced git keeps the caller's enterprise host settings
When a fenced script runs plain git for a remote that is not on github.com, that git SHALL see the caller's own `GH_HOST`, `GH_ENTERPRISE_TOKEN` and `GITHUB_ENTERPRISE_TOKEN`, the values they had before the fence unset them. No fenced `gh` or git command, and no fenced identity check, SHALL see them.

#### Scenario: Enterprise store read by rounds
- **WHEN** the caller has `GH_HOST=ghe.example` and `GH_ENTERPRISE_TOKEN=enttok`, the store's origin is on `ghe.example` with the credential helper `gh auth git-credential`, and `pr-pair.sh rounds` runs under `as.sh`
- **THEN** the store's git network call runs with `GH_HOST` and `GH_ENTERPRISE_TOKEN` set to the caller's values, and the read succeeds

#### Scenario: Variables were unset
- **WHEN** the caller had none of the three variables and a non-GitHub store is read under `as.sh`
- **THEN** the store's git runs without them, none is set to an empty string, and nothing is left from the fence

#### Scenario: Fenced calls stay on github.com
- **WHEN** the caller has `GH_HOST=ghe.example` and `GH_ENTERPRISE_TOKEN=enttok`, and in the same run a fenced `gh api` call and a fenced git fetch of a github.com remote are made
- **THEN** neither sees `GH_HOST`, `GH_ENTERPRISE_TOKEN` or `GITHUB_ENTERPRISE_TOKEN`, and both go to github.com with the run login's verified token
