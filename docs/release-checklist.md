# Release checklist

## Product verification

- [ ] `uv lock --check`
- [ ] `uv run ruff check .`
- [ ] `uv run pytest -q`
- [ ] official Skill validator passes with `PYTHONUTF8=1` on Windows
- [ ] official plugin validator passes
- [ ] `scripts/install-windows.ps1 -WhatIf` succeeds
- [ ] local global-command install succeeds in a clean tool environment
- [ ] local marketplace/plugin install succeeds
- [ ] `review-flow-mcp` starts and Codex lists its tools
- [ ] optional GROBID smoke test passes when the full profile is claimed

## Scientific workflow verification

- [ ] synthetic review completes three reciprocal rounds
- [ ] a scoping search lane durably returns to Phase 0, downloads licensed open PDFs, waits for one unavailable item, merges the supplied file with the original corpus, waits for reading notes, and resumes the exact Phase 2A step
- [ ] Phase 2B rejects fewer than three completed reciprocal rounds
- [ ] architecture and evidence gates reject ineligible inputs
- [ ] citation defect returns to its causal phase and resumes exactly
- [ ] every return requires a resolution note and fresh evidence matching its stored stop condition
- [ ] stale descendants block return resume and final bundle
- [ ] final bundle covers source manifest, extraction, scope, architecture, claims, manuscript, citation audit, and review report
- [ ] narrative, critical, and technical are the only accepted review types
- [ ] systematic review and meta-analysis claims are explicitly rejected

## Privacy and contamination scan

- [ ] no PDF, DOCX, manuscript excerpt, private extraction, or real project workspace is tracked
- [ ] no API key, email credential, token, `.env`, or local Codex configuration is tracked
- [ ] no user-specific absolute path or username is present
- [ ] no private domain conclusion or manuscript title is present
- [ ] no ARS-Codex prompt/schema/code block was copied
- [ ] only synthetic test content is included

## Human publication decisions

- [ ] repository owner and repository name confirmed
- [ ] public or private visibility confirmed
- [ ] MIT or Apache-2.0 selected by the owner
- [ ] author/contact and repository URLs placed in plugin metadata
- [ ] Git identity configured for commits
- [ ] clean install from the remote URL verified
- [ ] tag `v0.1.0` created only after remote install verification
