# KalArts world supporters

Automatic Patreon recognition feed for KalArts VRChat worlds.

The scheduled job runs about every 15 minutes; GitHub may delay scheduled jobs.
World boards refresh their cached list every 10 minutes.

Public output contains display names, tier labels, tier colors and an update time.
Only active paid supporters are included. No emails, member IDs, payment amounts,
access tokens or client secrets are published in the feed.

## Credentials

`.state/patreon.enc` is an authenticated AES-256-GCM encrypted session. Its
random 256-bit key is stored separately in the repository's **Actions secret**
`KALARTS_STATE_KEY`. The key must never be committed to this repository.

The encrypted session lets the job retain rotated refresh tokens without
granting it access to manage other GitHub secrets or repositories. Plaintext
exists only in an ephemeral runner temp file, deleted when the process finishes.
Credentials are renewed at least weekly and the encrypted state is saved before
publishing. The job runs only from this repository's trusted main branch; it does
not run pull request code or expose secrets to forks.

The workflow's write access is restricted to this repository's contents and
GitHub Pages deployment. Third-party actions are pinned to exact revisions.

## Failures and maintenance

A failed fetch or validation does not replace the last deployed feed. A failed
state push creates an **encrypted-session-RUN_ID** recovery artifact; restore
its `patreon.enc` to `.state/patreon.enc` before retrying if a token rotated.
The existing `KALARTS_STATE_KEY` decrypts that artifact. Never publish a decrypted
session. GitHub Actions shows job failures in the repository's Actions tab.

Use **Actions → Refresh KalArts supporters → Run workflow** to refresh manually.
If GitHub disables scheduled runs for repository inactivity, re-enable the
workflow there. A weekly credential renewal normally commits new encrypted state.

## Unity

Set the board's public feed URL to the GitHub Pages `supporters.json` URL after
the first successful deployment. Keep Preview Mode off. Native VRChat Credits
purchase integration is separate and is not enabled by this feed.

This is a recognition list, not proof that a VRChat account owns a Patreon
membership. Do not use display-name matching to grant paid access.
