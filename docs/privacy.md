# Privacy model

Review Workflow Codex is local-first. Source PDFs, Word drafts, extracted full
text, and manuscript prose remain in the configured local workspace unless the
operator records a destination-specific disclosure decision.

Bibliographic metadata, search queries, and short search snippets may be sent
to OpenAlex, Crossref, Unpaywall, DOI/publisher, or repository endpoints needed
for discovery and identity verification. Full text and draft prose require an
active consent record that identifies the destination, payload class, purpose,
operator, approval time, and optional expiry.

Credentials are never valid workflow payloads and must not be written into
project files, command arguments, logs, question packets, or chat messages.
Local tools read credentials from the process environment when an official API
requires them.

Every external disclosure decision is append-only and auditable. Revocation
does not delete history; it adds a new decision or marks the active record as
revoked in canonical state.
