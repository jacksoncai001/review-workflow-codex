# Review Workflow Codex

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

Review Workflow Codex is a local-first Codex plugin, Skill, MCP server, and Python harness for turning a small or large collection of local PDFs plus one or more draft manuscripts into a traceable narrative, critical, or technical review in engineering or natural science.

It is built for the awkward real case: the draft is long, figures and tables matter, some references are irrelevant or duplicated, the intended reader is unclear, nearby reviews already exist, and rewriting everything in one long model context would destroy provenance. The workflow stores durable source identities, reusable extraction, reciprocal scoping decisions, competing architectures, claim-level evidence, citation audits, and targeted repair history in a portable workspace.

It does **not** implement a systematic review or meta-analysis protocol and must not be used to make either claim.

## What is different

- The operator and Codex conduct at least three reciprocal scoping rounds. Each side asks 3–5 questions per round.
- Literature recommendations are selected for complementary roles—Anchor, Contrast, and Bridge—not merely highest text similarity.
- Each recommendation receives an auditable acquisition route: licensed open PDFs are downloaded automatically, while inaccessible items become operator requests that must be supplied or dismissed with a rationale.
- New search lanes discovered during reciprocal dialogue durably return to Phase 0; resolved files are merged with—not substituted for—the original corpus before the exact Phase 2A step resumes.
- Download completion never impersonates reading completion: the workflow waits for operator reading notes before initial scoping or a refreshed Phase 2A round continues.
- Review architectures compete on the actual audience, nearest-review differentiation, unresolved value, evidence feasibility, newcomer accessibility, and publication fit.
- Claims are linked to source identity and page/section locators before prose is polished.
- Rework returns to the earliest causal phase and invalidates only dependent artifacts.
- Full text and draft prose remain local unless destination-specific explicit consent is recorded.
- `state.json` and immutable extraction records support exact resume and transfer to another computer or Codex account.

## Components

```text
Codex conversation
  └─ build-evidence-grounded-review Skill (scientific orchestration)
      └─ local review-workflow-codex MCP (small deterministic tools)
          └─ Python harness (state, loops, provenance, privacy, adapters)
              └─ generated review workspace (all durable project knowledge)
```

The repository never needs the user's literature or manuscript. Original documents are read in place and are not modified or copied automatically.

## Profiles

- `windows-lite`: supported end-to-end on Windows without WSL2 or GROBID. MarkItDown/python-docx/pypdf provide local extraction. Phase 5 requires manual bibliography and in-text citation-structure inspection.
- `full`: adds Docling for layout-aware extraction and expects the pinned `grobid/grobid:0.9.0-full` service for TEI bibliography/citation structure. WSL2 plus Docker Engine is recommended, but WSL2 is not a logical requirement of the workflow.

See [Windows installation](docs/install-windows.md).

## Quick start

Clone the repository and enter it:

```powershell
git clone https://github.com/jacksoncai001/review-workflow-codex.git
Set-Location review-workflow-codex
```

Preview the installer:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1 -WhatIf
```

Install globally:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1 -Profile windows-lite
```

Then ask Codex:

> Use `$build-evidence-grounded-review` to start a technical review from my local PDFs and draft. Keep the originals unchanged and create a new review workspace.

The normal path is Preflight → Phase 0 discovery/acquisition → Phase 1 extraction → Phase 2 reciprocal scope and architecture competition → Phase 3 claim evidence → Phase 4 drafting → Phase 5 citation audit → Phase 6 bounded review → Phase 7 reproducibility bundle.

## Development

```powershell
uv sync --locked --extra dev --extra extract --extra discovery
uv run ruff check .
uv run pytest -q
```

The full Docling environment is optional for routine tests:

```powershell
uv sync --locked --extra dev --extra full
```

The GROBID integration smoke test runs only against an explicitly available local service:

```powershell
uv run pytest tests/integration/test_grobid_health.py --run-grobid -v
```

## Privacy, migration, and design

- [Architecture and phase model](docs/architecture.md)
- [Privacy model](docs/privacy.md)
- [Moving a workspace](docs/migration.md)
- [Third-party boundaries](docs/third-party-notices.md)
- [Release checklist](docs/release-checklist.md)

Eligible original project code, prompts, schemas, configuration, and documentation in this repository are licensed under the Apache License 2.0 unless a file or third-party notice says otherwise. Upstream dependencies and explicitly identified third-party material retain their own licenses and terms. No user manuscript, PDF, extracted private corpus, credential, or domain-specific private conclusion belongs in this source repository.

## License

Review Workflow Codex is licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for copyright attribution and [third-party boundaries](docs/third-party-notices.md) for material governed by upstream terms.

## Support

For normal usage questions, contact `1259081855@qq.com`. Support is provided on a best effort basis, with no response-time commitment. Please do not send PDFs, manuscripts, credentials, unpublished results, or other sensitive material unless the maintainer has agreed in advance. Issues, Discussions, Projects, and Wiki are intentionally disabled to keep maintenance sustainable; focused pull requests remain welcome.
