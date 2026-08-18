# Public Low-Interruption Release Design

## Decision

Publish `jacksoncai001/review-workflow-codex` as a public repository while keeping
maintenance demand intentionally low. Ordinary support requests go to
`1259081855@qq.com` on a best-effort basis.

## Repository settings

- Visibility: public.
- Issues: disabled.
- Projects: disabled.
- Discussions: disabled.
- Wiki: disabled.
- Pull requests: remain available; this design does not promise review or merge.
- License: remain absent until the owner separately selects one. Public visibility
  permits reading and forking on GitHub but does not itself grant an open-source
  license.

## Public support contract

The README and `.github/SUPPORT.md` provide the support email, state that replies
are best effort with no response-time commitment, and direct users not to send
manuscripts, PDFs, credentials, unpublished data, or other sensitive material
without prior agreement.

## Privacy boundary

The source repository continues to exclude user manuscripts, PDFs, extracted
corpora, credentials, local workspaces, and domain-specific private conclusions.
The email address is intentionally public by explicit owner authorization.

## Verification

Static tests require the public support contract and canonical repository URL.
Before the visibility change, lint and relevant tests must pass and documentation
changes must be pushed. After the browser settings change, the public repository
page and GitHub repository metadata must both report public visibility and the four
features disabled. The existing QR code must still decode to the canonical URL.
