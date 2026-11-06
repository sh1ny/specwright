# A4: release downloads redirect only over HTTPS

Assumption A4: an anonymous download of a GitHub release asset, `https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>`, redirects only to `https` URLs, so D3's rule of refusing any redirect to another scheme does not break a real download.

## Method

A `python -I` script that uses only the standard library ran on 2026-11-06 from this machine. It sent `HEAD` with `urllib` under a redirect handler that follows nothing, with a 20 s timeout per hop and at most 6 hops. It printed each hop's scheme, host and status and took the next URL from `Location`. The requests carried no authentication.

## Observations

An existing asset of a public release (`cli/cli` `v2.63.0`, `gh_2.63.0_checksums.txt`):

```
hop 0: https github.com -> 302
hop 1: https release-assets.githubusercontent.com -> 200
```

A missing asset on the same release (`.../v2.63.0/no-such-asset`):

```
hop 0: https github.com -> 404
```

A tag of this repository that has no assets (`sh1ny/specwright` `v0.23.0`, `SHA256SUMS`):

```
hop 0: https github.com -> 404
```

## Result

A4 holds. The download takes one redirect, from `github.com` to `release-assets.githubusercontent.com`, and both hops are `https`. The https-only redirect rule (C15) accepts it.

A missing asset answers 404 directly, with no redirect. D3 maps that to `asset_missing`, or to `assets_not_uploaded` when the request was for `SHA256SUMS`. Both observations match D3 as designed, so there is no drift.
