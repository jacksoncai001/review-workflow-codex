# Moving a review to another computer or Codex account

The reusable unit is the generated review workspace, not the chat transcript. The workspace's `state.json`, audit events, immutable extractions, local index, decisions, evidence matrices, manuscripts, and acquisition provenance make continuation deterministic.

## Best handoff point

The earliest useful package is after Phase 1, when all currently available PDFs and drafts have stable source hashes, extracted Markdown/JSON/TEI, and an FTS index. A later package is better because it also retains scoping rounds, architecture scorecards, claim matrices, audits, and manuscript versions. Do not wait for Phase 7 if another computer needs to continue work now.

## What to copy

Copy the entire generated workspace directory. Keep at minimum:

- `state.json` and `audit/`;
- `inputs/manifest.jsonl`;
- `corpus/extractions/` and `corpus/index/`;
- `phases/`, `decisions/`, `acquisitions/`, and `manuscripts/`;
- any operator-supplied source files that were deliberately placed inside the workspace.

Original sources inventoried from elsewhere are not copied automatically. This prevents pollution and accidental redistribution. If they are lawful and portable, copy them separately or re-import them on the destination computer. Existing extractions and evidence search remain usable without those originals; rerunning extraction requires the source files.

Do not package API keys, Codex configuration, `.env` files, unrelated caches, or the product repository's `.venv`.

## Destination procedure

1. Install the same tagged Review Workflow Codex version with `scripts/install-windows.ps1`.
2. Copy the workspace to its destination path.
3. Explicitly rebind the copied state:

   ```powershell
   review-flow relocate D:\path\to\copied-review-workspace
   ```

   In Codex, the equivalent MCP action is `project_relocate`.

4. Run `review-flow status D:\path\to\copied-review-workspace` and `preflight_check` through Codex.
5. Reconfigure API environment variables locally. Start GROBID only if using `full`.
6. Ask Codex to resume from the workspace. It must obey the persisted phase, step, outstanding packet, gate, and resume action.

Relocation changes only the copied workspace and appends a `workspace_relocated` event. It never changes the original package. Re-inventorying a relocated source with the same file hash and parser configuration reuses its immutable extraction.

## Integrity check before and after transfer

Archive tools can preserve the directory, but the workflow itself relies on the SHA-256 values recorded for sources and artifacts. Compare the archive hash or transfer checksum, open the copied state with `review-flow status`, and keep the original archive until the destination run has been verified.
